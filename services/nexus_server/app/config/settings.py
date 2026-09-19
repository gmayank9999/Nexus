from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded only on the trusted backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://nexus:nexus@localhost:5432/nexus"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    nexus_llm_provider: str = "ollama"
    nexus_ollama_base_url: str = "http://localhost:11434"
    nexus_ollama_model: str = ""
    nexus_llm_base_url: str = ""
    nexus_llm_api_key: SecretStr | None = None
    nexus_llm_model: str = ""
    nexus_max_agent_iterations: int = Field(default=12, ge=1, le=100)

    nexus_enable_web_search: bool = False
    nexus_enable_voice: bool = False
    nexus_voice_provider: Literal["whisper_cpp", "mock"] = "whisper_cpp"
    nexus_whisper_base_url: AnyHttpUrl = AnyHttpUrl("http://localhost:8080")
    nexus_voice_max_seconds: int = Field(default=60, ge=1, le=120)
    nexus_voice_timeout_seconds: float = Field(default=60, gt=0, le=180)
    nexus_voice_max_sessions: int = Field(default=4, ge=1, le=16)
    nexus_enable_code_execution: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
