"""Application configuration powered by Pydantic settings."""
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central runtime configuration."""

    app_env: str = Field(default="development", alias="APP_ENV")
    api_port: int = Field(default=8000, alias="API_PORT")
    database_url: str = Field(
        default="postgresql+asyncpg://jobcopilot:jobcopilot@localhost:5432/jobcopilot",
        alias="DATABASE_URL",
    )
    sync_database_url: str = Field(
        default="postgresql+psycopg://jobcopilot:jobcopilot@localhost:5432/jobcopilot",
        alias="SYNC_DATABASE_URL",
    )
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")
    llm_provider: str = Field(default="openai", alias="LLM_PROVIDER")
    llm_model: str = Field(default="gpt-4.1-mini", alias="LLM_MODEL")
    gemini_model: str = Field(default="gemini-pro", alias="GEMINI_MODEL")
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")
    otel_exporter_otlp_endpoint: Optional[str] = Field(
        default=None, alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    otel_service_name: str = Field(default="agentic-job-copilot", alias="OTEL_SERVICE_NAME")
    pgvector_dim: int = Field(default=1536, alias="PGVECTOR_DIM")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return a cached application settings object."""

    return Settings()
