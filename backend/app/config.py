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

    # webhook = own server (Docker); serverless = Vercel-style functions (no long-lived process);
    # polling = local development without a public URL; off = tests.
    bot_mode: Literal["webhook", "serverless", "polling", "off"] = "webhook"

    # Set automatically by the platform; used when PUBLIC_URL is not given.
    vercel_project_production_url: str | None = None  # Vercel: "finuchet.vercel.app"
    railway_public_domain: str | None = None  # Railway: "finuchet-production.up.railway.app"

    # Single-container hosting (Railway): the backend also serves the built Mini App from here.
    static_dir: str | None = None

    # Dev only: lets the Mini App run in a normal browser as a fake user.
    dev_fake_tg_id: int | None = None

    @model_validator(mode="after")
    def _forbid_dev_shortcuts_in_prod(self) -> Settings:
        platform_host = self.vercel_project_production_url or self.railway_public_domain
        if self.public_url == "https://example.com" and platform_host:
            self.public_url = "https://" + platform_host.removeprefix("https://")
        if self.env == "prod" and self.dev_fake_tg_id is not None:
            raise ValueError("DEV_FAKE_TG_ID must not be set when ENV=prod")
        if self.env == "prod" and not self.public_url.startswith("https://"):
            raise ValueError("PUBLIC_URL must be https in prod")
        return self

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"

    @property
    def serverless(self) -> bool:
        return self.bot_mode == "serverless"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
