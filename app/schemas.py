from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OpenAIResponsesRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str | None = Field(default=None, min_length=1, max_length=100)
    input: list[dict[str, Any]] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_input(self) -> "OpenAIResponsesRequest":
        if not self.input:
            raise ValueError("input must not be empty")
        return self

    def to_openai_payload(self, default_model: str) -> dict[str, Any]:
        payload = self.model_dump(exclude_none=True)
        if not payload.get("model"):
            payload["model"] = default_model
        return payload


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
