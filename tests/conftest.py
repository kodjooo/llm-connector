from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.metrics import MetricsService
from app.schemas import OpenAIResponsesRequest


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.response_payload: dict[str, Any] = {
            "id": "resp-test",
            "object": "response",
            "model": "gpt-5-mini",
            "output_text": (
                '{"site_verdict":"official_real_estate_agency_site","detected_city":"Краснодар",'
                '"confidence":0.94,"reason":"ok"}'
            ),
        }
        self.model_name = "gpt-5-mini"
        self.exception: Exception | None = None

    async def relay_responses(
        self,
        payload: OpenAIResponsesRequest,
    ) -> tuple[dict[str, Any], str]:
        if self.exception is not None:
            raise self.exception
        return self.response_payload, self.model_name


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        OPENAI_API_KEY="test-openai-key",
        GATEWAY_AUTH_TOKEN="test-gateway-token",
        DEFAULT_OPENAI_MODEL="gpt-5-mini",
        LOG_LEVEL="DEBUG",
        REQUEST_PAYLOAD_LIMIT_BYTES=32768,
        RATE_LIMIT_REQUESTS=100,
        RATE_LIMIT_WINDOW_SECONDS=60,
        METRICS_ENABLED=True,
    )


@pytest.fixture()
def fake_openai_client() -> FakeOpenAIClient:
    return FakeOpenAIClient()


@pytest.fixture()
def client(settings: Settings, fake_openai_client: FakeOpenAIClient) -> Iterator[TestClient]:
    app = create_app(settings=settings, metrics=MetricsService(), openai_client=fake_openai_client)
    with TestClient(app) as test_client:
        yield test_client
