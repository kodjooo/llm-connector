from __future__ import annotations

import asyncio
import json
from typing import Protocol

from openai import APITimeoutError, AsyncOpenAI, OpenAIError, RateLimitError as OpenAIRateLimitError

from app.config import Settings
from app.constants import OPENAI_PROVIDER_NAME
from app.errors import UpstreamError, UpstreamTimeoutError
from app.schemas import OpenAIResult, SiteClassificationRequest


class OpenAIClientProtocol(Protocol):
    async def classify_site(self, payload: SiteClassificationRequest) -> tuple[OpenAIResult, str]:
        ...


class OpenAIClassificationClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds)

    async def classify_site(self, payload: SiteClassificationRequest) -> tuple[OpenAIResult, str]:
        target_model = payload.model or self.settings.default_openai_model
        last_error: Exception | None = None

        for attempt in range(self.settings.openai_max_retries):
            try:
                response = await self.client.responses.create(
                    model=target_model,
                    input=[
                        {
                            "role": "system",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": (
                                        "Ты сервис классификации сайтов. "
                                        "Возвращай только JSON с полями site_verdict, detected_city, confidence, reason."
                                    ),
                                }
                            ],
                        },
                        {
                            "role": "user",
                            "content": [{"type": "input_text", "text": self._build_prompt(payload)}],
                        },
                    ],
                )
                parsed = self._extract_json(response.output_text)
                return parsed, target_model
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

    def _build_prompt(self, payload: SiteClassificationRequest) -> str:
        return json.dumps(payload.model_dump(mode="json"), ensure_ascii=False)

    def _extract_json(self, output_text: str) -> OpenAIResult:
        candidate = output_text.strip()
        if candidate.startswith("```"):
            candidate = candidate.strip("`").replace("json\n", "", 1).strip()
        raw_payload = json.loads(candidate)
        result = OpenAIResult.model_validate(raw_payload)
        return result

    @staticmethod
    def provider_name() -> str:
        return OPENAI_PROVIDER_NAME
