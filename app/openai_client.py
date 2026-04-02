from __future__ import annotations

import asyncio
from typing import Any, Protocol

import httpx

from app.config import Settings
from app.errors import UpstreamError, UpstreamTimeoutError
from app.schemas import OpenAIResponsesRequest

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


class OpenAIClientProtocol(Protocol):
    async def relay_responses(
        self,
        payload: OpenAIResponsesRequest,
    ) -> tuple[dict[str, Any], str]:
        ...


class OpenAIRelayClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def relay_responses(
        self,
        payload: OpenAIResponsesRequest,
    ) -> tuple[dict[str, Any], str]:
        target_payload = payload.to_openai_payload(self.settings.default_openai_model)
        target_model = str(target_payload["model"])
        last_error: Exception | None = None

        for attempt in range(self.settings.openai_max_retries):
            try:
                response_payload = await self._post_responses_payload(target_payload)
                return response_payload, target_model
            except httpx.TimeoutException as error:
                last_error = error
                if attempt + 1 >= self.settings.openai_max_retries:
                    raise UpstreamTimeoutError() from error
                await asyncio.sleep(self.settings.retry_backoff_schedule[attempt])
            except httpx.HTTPStatusError as error:
                last_error = error
                status_code = error.response.status_code
                if status_code == 429 and attempt + 1 < self.settings.openai_max_retries:
                    await asyncio.sleep(self.settings.retry_backoff_schedule[attempt])
                    continue
                if status_code == 429:
                    raise UpstreamError("OpenAI rate limit exceeded") from error
                if status_code >= 500 and attempt + 1 < self.settings.openai_max_retries:
                    await asyncio.sleep(self.settings.retry_backoff_schedule[attempt])
                    continue
                if status_code >= 500:
                    raise UpstreamError("OpenAI returned an upstream error") from error
                raise UpstreamError(
                    f"OpenAI request rejected with status {status_code}"
                ) from error
            except httpx.HTTPError as error:
                last_error = error
                if attempt + 1 >= self.settings.openai_max_retries:
                    raise UpstreamError("OpenAI returned an upstream error") from error
                await asyncio.sleep(self.settings.retry_backoff_schedule[attempt])
            except ValueError as error:
                raise UpstreamError("OpenAI returned an invalid response") from error

        raise UpstreamError(str(last_error) if last_error else "Unknown upstream error")

    async def _post_responses_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.settings.openai_timeout_seconds) as client:
            response = await client.post(
                OPENAI_RESPONSES_URL,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()
