from __future__ import annotations

import logging
from time import perf_counter
from uuid import uuid4

import sentry_sdk
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import Settings, get_settings
from app.errors import BadRequestError, GatewayError, RateLimitError, UnauthorizedError
from app.logging_utils import configure_logging
from app.metrics import MetricsService
from app.openai_client import OpenAIRelayClient
from app.rate_limit import InMemoryRateLimiter
from app.schemas import ErrorResponse, OpenAIResponsesRequest
from app.service import OpenAIRelayService

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") if self.settings.trust_x_request_id else None
        request.state.request_id = request_id or str(uuid4())
        started_at = perf_counter()

        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id

        logger.info(
            "Запрос обработан.",
            extra={
                "request_id": request.state.request_id,
                "status_code": response.status_code,
                "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                "path": request.url.path,
                "method": request.method,
            },
        )
        return response


class PayloadLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.settings.request_payload_limit_bytes:
            return JSONResponse(
                status_code=400,
                content=ErrorResponse(
                    error={"code": "payload_too_large", "message": "Payload is too large"}
                ).model_dump(),
            )
        return await call_next(request)


def create_app(
    settings: Settings | None = None,
    metrics: MetricsService | None = None,
    openai_client: OpenAIRelayClient | None = None,
) -> FastAPI:
    current_settings = settings or get_settings()
    configure_logging(current_settings.log_level)
    _configure_sentry(current_settings)

    app = FastAPI(title="LLM Gateway", version="1.2.0")
    app.state.settings = current_settings
    app.state.metrics = metrics or MetricsService()
    app.state.rate_limiter = InMemoryRateLimiter(
        limit=current_settings.rate_limit_requests,
        window_seconds=current_settings.rate_limit_window_seconds,
    )
    app.state.openai_client = openai_client or OpenAIRelayClient(current_settings)
    app.state.relay_service = OpenAIRelayService(app.state.openai_client, app.state.metrics)

    app.add_middleware(RequestContextMiddleware, settings=current_settings)
    app.add_middleware(PayloadLimitMiddleware, settings=current_settings)

    @app.exception_handler(GatewayError)
    async def gateway_error_handler(request: Request, exc: GatewayError) -> JSONResponse:
        app.state.metrics.requests_failed_total.inc()
        if exc.status_code in (502, 504):
            app.state.metrics.upstream_openai_errors_total.inc()
        logger.warning(
            "Запрос завершился ошибкой gateway.",
            extra={"request_id": getattr(request.state, "request_id", None), "status_code": exc.status_code},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(error={"code": exc.code, "message": exc.message}).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        app.state.metrics.requests_failed_total.inc()
        logger.warning(
            "Запрос не прошел валидацию.",
            extra={"request_id": getattr(request.state, "request_id", None), "status_code": 400},
        )
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                error={"code": "invalid_request", "message": "Invalid request payload"}
            ).model_dump(),
        )

    def get_service(request: Request) -> OpenAIRelayService:
        return request.app.state.relay_service

    @app.get("/health")
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def readiness() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/metrics")
    async def metrics_endpoint(request: Request):
        if not request.app.state.settings.metrics_enabled:
            raise BadRequestError("Metrics endpoint is disabled", code="metrics_disabled")
        return request.app.state.metrics.render()

    @app.post("/v1/openai/responses")
    async def relay_responses(
        payload: OpenAIResponsesRequest,
        request: Request,
        service: OpenAIRelayService = Depends(get_service),
    ):
        _authorize_request(request)
        _enforce_rate_limit(request)
        request.app.state.metrics.requests_total.inc()
        _log_sanitized_payload(request, payload)
        result = await service.relay_responses(payload)
        return JSONResponse(status_code=200, content=result)

    return app


def _authorize_request(request: Request) -> None:
    settings: Settings = request.app.state.settings
    auth_header = request.headers.get("Authorization", "")
    if auth_header != f"Bearer {settings.gateway_auth_token}":
        raise UnauthorizedError("Invalid or missing bearer token")


def _enforce_rate_limit(request: Request) -> None:
    settings: Settings = request.app.state.settings
    client_ip = request.client.host if request.client else "unknown"

    if settings.allowed_source_ip_list and client_ip not in settings.allowed_source_ip_list:
        raise UnauthorizedError("Source IP is not allowed")

    if not request.app.state.rate_limiter.allow(client_ip):
        raise RateLimitError()


def _log_sanitized_payload(request: Request, payload: OpenAIResponsesRequest) -> None:
    settings: Settings = request.app.state.settings
    logger.info(
        "Получен запрос на relay responses.",
        extra={
            "request_id": getattr(request.state, "request_id", None),
            "model": payload.model or settings.default_openai_model,
            "input_items": len(payload.input),
        },
    )

    if settings.log_level.upper() == "DEBUG":
        logger.debug(
            "Отладочные данные relay-запроса: input_items=%s",
            len(payload.input),
            extra={"request_id": getattr(request.state, "request_id", None)},
        )


def _configure_sentry(settings: Settings) -> None:
    if settings.sentry_dsn:
        sentry_sdk.init(dsn=settings.sentry_dsn)


app = create_app()
