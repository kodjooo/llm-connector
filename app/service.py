from __future__ import annotations

import logging
from time import perf_counter

from app.constants import OPENAI_PROVIDER_NAME
from app.metrics import MetricsService
from app.openai_client import OpenAIClientProtocol
from app.schemas import SiteClassificationRequest, SiteClassificationResponse

logger = logging.getLogger(__name__)


class SiteClassificationService:
    def __init__(self, openai_client: OpenAIClientProtocol, metrics: MetricsService) -> None:
        self.openai_client = openai_client
        self.metrics = metrics

    async def classify(self, payload: SiteClassificationRequest) -> SiteClassificationResponse:
        started_at = perf_counter()
        result, model_name = await self.openai_client.classify_site(payload)
        elapsed_ms = (perf_counter() - started_at) * 1000
        self.metrics.upstream_openai_latency_ms.observe(elapsed_ms)

        logger.info(
            "Классификация сайта завершена.",
            extra={"model": model_name, "duration_ms": round(elapsed_ms, 2)},
        )

        return SiteClassificationResponse(
            site_verdict=result.site_verdict,
            detected_city=result.detected_city,
            confidence=float(result.confidence),
            reason=result.reason,
            provider=OPENAI_PROVIDER_NAME,
            model=model_name,
        )
