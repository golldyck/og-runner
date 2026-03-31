"""Application configuration using Pydantic Settings."""

import json

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # API
    api_title: str = "OG Runner API"
    api_version: str = "0.1.0"

    # CORS
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]

    # OpenGradient live inference
    og_private_key: str | None = None
    og_enable_live_inference: bool = True
    og_enable_live_llm: bool = True
    og_rpc_url: str = "https://ogevmdevnet.opengradient.ai"
    og_api_url: str = "https://sdk-devnet.opengradient.ai"
    og_inference_contract_address: str = "0x8383C9bD7462F12Eb996DD02F78234C0421A6FaE"
    og_tee_llm_model: str = "GPT_5_MINI"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            if value.startswith("["):
                return json.loads(value)
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


settings = Settings()
