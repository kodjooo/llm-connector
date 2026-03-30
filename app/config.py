from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    gateway_auth_token: str = Field(default="", alias="GATEWAY_AUTH_TOKEN")
    default_openai_model: str = Field(default="gpt-5-mini", alias="DEFAULT_OPENAI_MODEL")

    openai_timeout_seconds: int = Field(default=45, alias="OPENAI_TIMEOUT_SECONDS")
    openai_max_retries: int = Field(default=3, alias="OPENAI_MAX_RETRIES")
    openai_retry_backoff_seconds: str = Field(default="1,2,3", alias="OPENAI_RETRY_BACKOFF_SECONDS")

    request_payload_limit_bytes: int = Field(default=32768, alias="REQUEST_PAYLOAD_LIMIT_BYTES")
    rate_limit_requests: int = Field(default=60, alias="RATE_LIMIT_REQUESTS")
    rate_limit_window_seconds: int = Field(default=60, alias="RATE_LIMIT_WINDOW_SECONDS")
    trust_x_request_id: bool = Field(default=True, alias="TRUST_X_REQUEST_ID")

    metrics_enabled: bool = Field(default=True, alias="METRICS_ENABLED")
    sentry_dsn: str = Field(default="", alias="SENTRY_DSN")
    allowed_source_ips: str = Field(default="", alias="ALLOWED_SOURCE_IPS")
    debug_log_excerpt_chars: int = Field(default=500, alias="DEBUG_LOG_EXCERPT_CHARS")

    @property
    def retry_backoff_schedule(self) -> list[int]:
        raw_values = [item.strip() for item in self.openai_retry_backoff_seconds.split(",") if item.strip()]
        return [int(item) for item in raw_values[: self.openai_max_retries]]

    @property
    def allowed_source_ip_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_source_ips.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
