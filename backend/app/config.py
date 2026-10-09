"""
Configuration management using Pydantic Settings.

Loads configuration from environment variables (or a .env file) with validation.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="UPSC Interview Transcripts", alias="APP_NAME")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    cors_origins: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")

    # Database (Postgres with the pgvector extension)
    database_url: str = Field(
        default="postgresql://upsc:upsc@localhost:5432/upsc", alias="DATABASE_URL"
    )

    # Embeddings (computed locally with fastembed; no API key needed)
    embed_model: str = Field(
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", alias="EMBED_MODEL"
    )
    embed_dim: int = Field(default=384, alias="EMBED_DIM")
    embed_cache_dir: str | None = Field(default=None, alias="EMBED_CACHE_DIR")

    # LLMs via OpenRouter. Which model each flow uses is set in models.toml (model_1, model_2, ...).
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    models_file: str | None = Field(default=None, alias="MODELS_FILE")     # default: backend/models.toml
    sources_file: str | None = Field(default=None, alias="SOURCES_FILE")   # default: backend/sources.toml

    # Load backend/seed/ automatically when the database has no transcripts
    seed_on_empty: bool = Field(default=True, alias="SEED_ON_EMPTY")

    # Enables /api/admin (upload a Telegram export to re-ingest). Leave empty to disable.
    admin_token: str = Field(default="", alias="ADMIN_TOKEN")

    # Source channel, used to link each transcript back to its Telegram post
    telegram_channel: str = Field(default="https://t.me/csetranscripts", alias="TELEGRAM_CHANNEL")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
