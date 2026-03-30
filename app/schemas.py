from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.constants import ALLOWED_SITE_VERDICTS, SITE_CLASSIFICATION_SCHEMA


class SerpPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=500)
    snippet: str = Field(min_length=1, max_length=2000)
    url: HttpUrl
    position: int = Field(ge=1, le=100)


class ScreeningPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: float = Field(ge=0, le=10)
    reason: str | None = Field(default=None, max_length=500)
    requires_verification: bool | None = None


class SiteClassificationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_city: str = Field(min_length=1, max_length=200)
    expected_entity_type: str = Field(min_length=1, max_length=200)
    domain: str = Field(min_length=1, max_length=255)
    serp: SerpPayload
    serp_screening: ScreeningPayload
    homepage_screening: ScreeningPayload
    homepage_excerpt: str = Field(min_length=1, max_length=10000)

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, value: str) -> str:
        return value.strip().lower()


class SiteClassificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: str = Field(min_length=1, max_length=100)
    model: str | None = Field(default=None, min_length=1, max_length=100)
    input: SiteClassificationInput

    @model_validator(mode="before")
    @classmethod
    def remap_schema_field(cls, values):
        if isinstance(values, dict) and "schema" in values and "schema_name" not in values:
            mapped = dict(values)
            mapped["schema_name"] = mapped.pop("schema")
            return mapped
        return values

    @field_validator("schema_name")
    @classmethod
    def validate_schema(cls, value: str) -> str:
        if value != SITE_CLASSIFICATION_SCHEMA:
            raise ValueError("Unknown schema")
        return value


class SiteClassificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_verdict: str | None
    detected_city: str | None = Field(default=None, max_length=200)
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1, max_length=4000)
    provider: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_verdict(self) -> "SiteClassificationResponse":
        if self.site_verdict not in ALLOWED_SITE_VERDICTS:
            raise ValueError("Invalid site_verdict")
        return self


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class OpenAIResult(BaseModel):
    site_verdict: str | None
    detected_city: str | None = None
    confidence: float
    reason: str
