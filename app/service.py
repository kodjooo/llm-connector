from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

from app.metrics import MetricsService
from app.openai_client import OpenAIClientProtocol
from app.schemas import OpenAIResponsesRequest

logger = logging.getLogger(__name__)


class OpenAIRelayService:
    def __init__(self, openai_client: OpenAIClientProtocol, metrics: MetricsService) -> None:
        self.openai_client = openai_client
        self.metrics = metrics

    async def relay_responses(
        self,
        payload: OpenAIResponsesRequest,
    ) -> dict[str, Any]:
        started_at = perf_counter()
        response_payload, model_name = await self.openai_client.relay_responses(payload)
        elapsed_ms = (perf_counter() - started_at) * 1000
        self.metrics.upstream_openai_latency_ms.observe(elapsed_ms)

        logger.info(
            "LLM relay завершен.",
            extra={"model": model_name, "duration_ms": round(elapsed_ms, 2)},
        )
        return response_payload
