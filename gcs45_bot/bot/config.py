from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Telegram
    bot_token: str
    payment_provider_token: str = ""
    admin_ids: list[int] = []

    # AI
    anthropic_api_key: str = ""  # не используется, оставлено для совместимости
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

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def use_webhook(self) -> bool:
        return bool(self.webhook_url)


settings = Settings()
