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
    JWT_SECRET: str | None = Field(default=None, min_length=32)
    SEED_DEMO_PASSWORD: str = Field(default="KetsipDemo2025!", min_length=12)
    PORT: int = Field(default=8000, ge=1, le=65535)

    def require_jwt_secret(self) -> str:
        """Return the configured signing key or fail closed on missing/default values."""
        secret = (self.JWT_SECRET or "").strip()
        normalized = secret.lower()
        placeholders = ("change-me", "dev-secret", "replace-this", "your-secret", "example-secret")
        if len(secret) < 32 or any(marker in normalized for marker in placeholders):
            raise RuntimeError("JWT_SECRET must be configured with a private random value of at least 32 characters.")
        return secret

    @property
    def cors_origins(self) -> list[str]:
        """Return configured browser origins without blank entries."""
        return [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS.split(",") if origin.strip()]


settings = Settings()
