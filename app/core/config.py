"""Application configuration settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    app_name: str = "Cacau Show API"
    app_version: str = "1.0.0"
    debug: bool = False

    class Config:
        env_file = ".env"


settings = Settings()
