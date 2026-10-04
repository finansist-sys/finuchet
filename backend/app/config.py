"""Application settings. Every secret comes from the environment (.env), never from code."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: Literal["prod", "dev", "test"] = "prod"
    public_url: str = "https://example.com"

    bot_token: SecretStr
    webhook_secret: SecretStr
    webhook_path_token: SecretStr
    id_pepper: SecretStr = Field(min_length=32)
    database_url: SecretStr

    # Mini App initData lifetime and the stricter one for destructive actions.
    init_data_ttl_seconds: int = 24 * 3600
    destructive_ttl_seconds: int = 10 * 60

    # webhook = production; polling = local development without a public URL; off = tests.
    bot_mode: Literal["webhook", "polling", "off"] = "webhook"

    # Dev only: lets the Mini App run in a normal browser as a fake user.
    dev_fake_tg_id: int | None = None

    @model_validator(mode="after")
    def _forbid_dev_shortcuts_in_prod(self) -> Settings:
        if self.env == "prod" and self.dev_fake_tg_id is not None:
            raise ValueError("DEV_FAKE_TG_ID must not be set when ENV=prod")
        if self.env == "prod" and not self.public_url.startswith("https://"):
            raise ValueError("PUBLIC_URL must be https in prod")
        return self

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
