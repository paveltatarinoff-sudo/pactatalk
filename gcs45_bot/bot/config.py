import json

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Telegram
    bot_token: str
    payment_provider_token: str = ""
    admin_ids: list[int] = []
    support_inbox_ids: list[int] = []

    # AI
    openai_api_key: str = ""

    # Storage
    redis_url: str = "redis://localhost:6379/0"
    database_url: str

    # Webhook (пустой = polling mode)
    webhook_url: str = ""
    webhook_secret: str = ""

    # App
    env: str = "development"
    log_level: str = "INFO"
    enable_dev_schema_bootstrap: bool = False
    openai_timeout_seconds: int = 30
    openai_max_retries: int = 3
    openai_retry_base_delay_seconds: float = 1.5
    user_response_timeout_seconds: int = 60 * 30
    timeout_check_interval_seconds: int = 60
    post_session_survey_url: str = ""

    @classmethod
    def _parse_id_list(cls, value):
        if value in (None, "", []):
            return []
        if isinstance(value, int):
            return [value]
        if isinstance(value, list):
            return [int(item) for item in value]
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("["):
                parsed = json.loads(raw)
                return [int(item) for item in parsed]
            return [int(item.strip()) for item in raw.split(",") if item.strip()]
        return value

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value):
        return cls._parse_id_list(value)

    @field_validator("support_inbox_ids", mode="before")
    @classmethod
    def parse_support_inbox_ids(cls, value):
        return cls._parse_id_list(value)

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def use_webhook(self) -> bool:
        return bool(self.webhook_url)


settings = Settings()
