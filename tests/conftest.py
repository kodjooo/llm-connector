from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.metrics import MetricsService
from app.schemas import OpenAIResult, SiteClassificationRequest


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.result = OpenAIResult(
            site_verdict="official_real_estate_agency_site",
            detected_city="Краснодар",
            confidence=0.94,
            reason="Сайт агентства недвижимости с каталогом объектов и контактами.",
        )
        self.model_name = "gpt-5-mini"
        self.exception: Exception | None = None

    async def classify_site(self, payload: SiteClassificationRequest) -> tuple[OpenAIResult, str]:
        if self.exception is not None:
            raise self.exception
        return self.result, self.model_name


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
