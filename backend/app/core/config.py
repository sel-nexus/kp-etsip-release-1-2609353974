"""Load validated runtime settings for the API service."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Provide environment-backed application configuration."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    MONGODB_URI: str = "mongodb://127.0.0.1:27017"
    MONGODB_DB: str = "ketsip"
    CORS_ALLOWED_ORIGINS: str = "http://localhost:5173"
    SEED_ON_STARTUP: bool = True
    SEED_ADMIN_PASSWORD: str = Field(min_length=12)
    SEED_DEMO_PASSWORD: str = Field(default="KetsipDemo2025!", min_length=12)
    PORT: int = Field(default=8000, ge=1, le=65535)

    @property
    def cors_origins(self) -> list[str]:
        """Return configured browser origins without blank entries."""
        return [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS.split(",") if origin.strip()]


settings = Settings()
