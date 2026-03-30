import pytest

from app.errors import UpstreamError, UpstreamTimeoutError
from app.main import create_app
from app.metrics import MetricsService


def build_payload(domain: str = "verno.pro") -> dict:
    return {
        "model": "gpt-5-mini",
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "SiteClassification",
                "schema": {
                    "type": "object",
                    "properties": {
                        "site_verdict": {"type": ["string", "null"]},
                        "detected_city": {"type": ["string", "null"]},
                        "confidence": {"type": "number"},
                        "reason": {"type": ["string", "null"]},
                    },
                    "required": ["site_verdict", "detected_city", "confidence", "reason"],
                },
            },
        },
        "messages": [
            {
                "role": "system",
                "content": (
                    "Определи тип сайта и фактический город по ограниченному контексту. "
                    "Если уверенности нет, верни verdict=uncertain."
                ),
            },
            {
                "role": "user",
                "content": (
                    '{"expected_city":"Краснодар","expected_entity_type":"real_estate_agency",'
                    f'"domain":"{domain}","homepage_excerpt":"Каталог объектов и контакты."}}'
                ),
            },
        ],
    }


def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-gateway-token", "X-Request-ID": "test-request-id"}


def test_healthcheck(client) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_relay_chat_completions_success(client) -> None:
    response = client.post("/v1/openai/chat-completions", headers=auth_headers(), json=build_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["model"] == "gpt-5-mini"
    assert body["choices"][0]["message"]["role"] == "assistant"


def test_relay_chat_completions_requires_token(client) -> None:
    response = client.post("/v1/openai/chat-completions", json=build_payload())

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_relay_chat_completions_returns_400_for_invalid_payload(client) -> None:
    response = client.post(
        "/v1/openai/chat-completions",
        headers=auth_headers(),
        json={"model": "gpt-5-mini", "messages": []},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_relay_chat_completions_returns_400_for_large_payload(client) -> None:
    response = client.post(
        "/v1/openai/chat-completions",
        headers={**auth_headers(), "content-length": "999999"},
        content=b"{}",
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "payload_too_large"


def test_relay_chat_completions_returns_502_for_upstream_error(client, fake_openai_client) -> None:
    fake_openai_client.exception = UpstreamError()

    response = client.post("/v1/openai/chat-completions", headers=auth_headers(), json=build_payload())

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "upstream_invalid_response"


def test_relay_chat_completions_returns_504_for_timeout(client, fake_openai_client) -> None:
    fake_openai_client.exception = UpstreamTimeoutError()

    response = client.post("/v1/openai/chat-completions", headers=auth_headers(), json=build_payload())

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "upstream_timeout"


def test_relay_chat_completions_returns_429_when_rate_limited(settings, fake_openai_client) -> None:
    settings.rate_limit_requests = 1
    app = create_app(settings=settings, metrics=MetricsService(), openai_client=fake_openai_client)

    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        first = test_client.post("/v1/openai/chat-completions", headers=auth_headers(), json=build_payload())
        second = test_client.post(
            "/v1/openai/chat-completions",
            headers=auth_headers(),
            json=build_payload("second.example"),
        )

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "rate_limit_exceeded"


def test_relay_uses_default_model_when_missing(client, fake_openai_client) -> None:
    payload = build_payload()
    payload.pop("model")

    response = client.post("/v1/openai/chat-completions", headers=auth_headers(), json=payload)

    assert response.status_code == 200
    assert response.json()["model"] == "gpt-5-mini"


def test_metrics_endpoint(client) -> None:
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "requests_total" in response.text
