from functools import lru_cache
from typing import Optional

from fastapi import Depends
from pydantic_settings import BaseSettings
from pydantic import Field

import logging

from app.service.driver_watcher import DriveWatcher

logger = logging.getLogger(__name__)

# Global DriveWatcher instance
drive_watcher: Optional[DriveWatcher] = None


class Settings(BaseSettings):
    """Application settings and configuration."""

    # API Keys
    tavily_api_key: str = Field(..., alias="TAVILY_API_KEY")
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")

    # Database Configuration
    db_host: str = Field("localhost", alias="DB_HOST")
    db_port: str = Field("5432", alias="DB_PORT")
    db_name: str = Field(..., alias="DB_NAME")
    db_user: str = Field(..., alias="DB_USER")
    db_password: str = Field(..., alias="DB_PASSWORD")
    db_pool_size: int = Field(5, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(10, alias="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(30, alias="DB_POOL_TIMEOUT")

    # Environment
    environment: str = Field("development", alias="ENVIRONMENT")

    # Google Drive Configuration
    team_drive_folder_id: str = Field(..., alias="TEAM_DRIVE_FOLDER_ID")
    google_application_credentials: str = Field(..., alias="GOOGLE_APPLICATION_CREDENTIALS")

    @property
    def database_url(self) -> str:
        """Get the database URL."""
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def async_database_url(self) -> str:
        """Get the async database URL."""
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        populate_by_name = True
        # Allow aliased names for environment variables
        allow_population_by_field_name = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def get_drive_watcher(settings: Settings = Depends(get_settings)) -> DriveWatcher:
    """Get or create DriveWatcher instance.

    Args:
        settings: Application settings

    Returns:
        DriveWatcher instance
    """
    global drive_watcher
    if drive_watcher is None:
        drive_watcher = DriveWatcher(
            folder_id=settings.team_drive_folder_id,
            credentials_path=settings.google_application_credentials
        )
        logger.info("DriveWatcher initialized successfully")
    return drive_watcher
