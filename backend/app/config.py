"""
Configuration management using Pydantic Settings.

Loads configuration from environment variables (or a .env file) with validation.
"""

from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Put backend/.env into the environment, so each provider's API key variable named in models.toml
# (OPENROUTER_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, ...) is found. Real environment variables win.
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="Dholpur House", alias="APP_NAME")
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

    # LLM providers and model slots live in models.toml; API keys come from the environment / .env.
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
