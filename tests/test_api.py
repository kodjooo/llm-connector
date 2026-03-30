import pytest

from app.errors import RateLimitError, UpstreamError, UpstreamTimeoutError
from app.main import create_app
from app.metrics import MetricsService
from app.schemas import OpenAIResult


def build_payload(domain: str = "verno.pro") -> dict:
    return {
        "schema": "site_classification_v1",
        "model": "gpt-5-mini",
        "input": {
            "expected_city": "Краснодар",
            "expected_entity_type": "real_estate_agency",
            "domain": domain,
            "serp": {
                "title": "VERNO",
                "snippet": "Недвижимость в Краснодаре",
                "url": "https://verno.pro/",
                "position": 3,
            },
            "serp_screening": {
                "score": 2.5,
                "reason": "serp_needs_homepage_verification",
                "requires_verification": True,
            },
            "homepage_screening": {
                "score": 5.0,
                "reason": None,
                "requires_verification": None,
            },
            "homepage_excerpt": "Каталог объектов и контакты агентства недвижимости.",
        },
    }


def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-gateway-token", "X-Request-ID": "test-request-id"}


def test_healthcheck(client) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_site_classification_success(client) -> None:
    response = client.post("/v1/site-classification", headers=auth_headers(), json=build_payload())

    assert response.status_code == 200
    assert response.json()["site_verdict"] == "official_real_estate_agency_site"
    assert response.json()["provider"] == "openai"


def test_site_classification_requires_token(client) -> None:
    response = client.post("/v1/site-classification", json=build_payload())

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_site_classification_returns_400_for_invalid_schema(client) -> None:
    payload = build_payload()
    payload["schema"] = "unknown"

    response = client.post("/v1/site-classification", headers=auth_headers(), json=payload)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_site_classification_returns_400_for_large_payload(client) -> None:
    response = client.post(
        "/v1/site-classification",
        headers={**auth_headers(), "content-length": "999999"},
        content=b"{}",
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "payload_too_large"


def test_site_classification_returns_502_for_invalid_upstream_response(client, fake_openai_client) -> None:
    fake_openai_client.result = OpenAIResult(
        site_verdict="official_real_estate_agency_site",
        detected_city="Краснодар",
        confidence=0.2,
        reason="ok",
    )
    fake_openai_client.exception = UpstreamError()

    response = client.post("/v1/site-classification", headers=auth_headers(), json=build_payload())

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "upstream_invalid_response"


def test_site_classification_returns_504_for_timeout(client, fake_openai_client) -> None:
    fake_openai_client.exception = UpstreamTimeoutError()

    response = client.post("/v1/site-classification", headers=auth_headers(), json=build_payload())

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "upstream_timeout"


def test_site_classification_returns_429_when_rate_limited(settings, fake_openai_client) -> None:
    settings.rate_limit_requests = 1
    app = create_app(settings=settings, metrics=MetricsService(), openai_client=fake_openai_client)

    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        first = test_client.post("/v1/site-classification", headers=auth_headers(), json=build_payload())
        second = test_client.post("/v1/site-classification", headers=auth_headers(), json=build_payload("second.example"))

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "rate_limit_exceeded"


@pytest.mark.parametrize(
    ("domain", "city", "verdict"),
    [
        ("verno.pro", "Краснодар", "official_real_estate_agency_site"),
        ("mall.ru", "Москва", "official_mall_site"),
        ("tenant.example", "Казань", "mall_tenant_site"),
        ("developer.example", "Сочи", "developer_site"),
        ("listing.example", "Санкт-Петербург", "aggregator_or_directory"),
        ("media.example", "Екатеринбург", "media_or_article"),
        ("unknown.example", "Тюмень", "uncertain"),
        ("agency-1.example", "Краснодар", "official_real_estate_agency_site"),
        ("agency-2.example", "Краснодар", "official_real_estate_agency_site"),
        ("agency-3.example", "Краснодар", "official_real_estate_agency_site"),
    ],
)
def test_acceptance_sample_domains(client, fake_openai_client, domain: str, city: str, verdict: str) -> None:
    fake_openai_client.result = OpenAIResult(
        site_verdict=verdict,
        detected_city=city,
        confidence=0.91,
        reason=f"Тестовый verdict для {domain}",
    )

    response = client.post("/v1/site-classification", headers=auth_headers(), json=build_payload(domain))

    assert response.status_code == 200
    assert response.json()["site_verdict"] == verdict


def test_metrics_endpoint(client) -> None:
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "requests_total" in response.text
