from __future__ import annotations

import asyncio
from typing import Any, Protocol

from openai import APITimeoutError, AsyncOpenAI, OpenAIError, RateLimitError as OpenAIRateLimitError

from app.config import Settings
from app.errors import UpstreamError, UpstreamTimeoutError
from app.schemas import OpenAIChatCompletionsRequest


class OpenAIClientProtocol(Protocol):
    async def relay_chat_completions(
        self,
        payload: OpenAIChatCompletionsRequest,
    ) -> tuple[dict[str, Any], str]:
        ...


class OpenAIRelayClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds)

    async def relay_chat_completions(
        self,
        payload: OpenAIChatCompletionsRequest,
    ) -> tuple[dict[str, Any], str]:
        target_payload = payload.to_openai_payload(self.settings.default_openai_model)
        target_model = str(target_payload["model"])
        last_error: Exception | None = None

        for attempt in range(self.settings.openai_max_retries):
            try:
                response = await self.client.chat.completions.create(**target_payload)
                return response.model_dump(mode="json"), target_model
            except APITimeoutError as error:
                last_error = error
                if attempt + 1 >= self.settings.openai_max_retries:
                    raise UpstreamTimeoutError() from error
                await asyncio.sleep(self.settings.retry_backoff_schedule[attempt])
            except OpenAIRateLimitError as error:
                last_error = error
                if attempt + 1 >= self.settings.openai_max_retries:
                    raise UpstreamError("OpenAI rate limit exceeded") from error
                await asyncio.sleep(self.settings.retry_backoff_schedule[attempt])
            except OpenAIError as error:
                last_error = error
                if attempt + 1 >= self.settings.openai_max_retries:
                    raise UpstreamError("OpenAI returned an upstream error") from error
                await asyncio.sleep(self.settings.retry_backoff_schedule[attempt])
            except ValueError as error:
                raise UpstreamError("OpenAI returned an invalid response") from error

        raise UpstreamError(str(last_error) if last_error else "Unknown upstream error")
