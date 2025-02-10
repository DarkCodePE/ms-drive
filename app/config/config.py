from functools import lru_cache
from typing import Optional

from fastapi import Depends
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv
import logging

from app.service.driver_watcher import DriveWatcher

logger = logging.getLogger(__name__)
load_dotenv()

# Global DriveWatcher instance
drive_watcher: Optional[DriveWatcher] = None


class Settings(BaseSettings):
    """Application settings and configuration."""

    """Application settings and configuration."""

    # API Keys
    TAVILY_API_KEY: str
    OPENAI_API_KEY: str

    # Database Configuration
    DB_HOST: str = "localhost"
    DB_PORT: str = "5432"
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30

    # Environment
    ENVIRONMENT: str = "development"

    # Google Drive Configuration
    TEAM_DRIVE_FOLDER_ID: str
    GOOGLE_APPLICATION_CREDENTIALS: str
    DRIVE_NOTIFICATION_URL: Optional[str] = None

    @property
    def database_url(self) -> str:
        """Get the database URL."""
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def async_database_url(self) -> str:
        """Get the async database URL."""
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    try:
        settings = Settings()
        logger.info("Settings loaded successfully")
        return settings
    except Exception as e:
        logger.error(f"Error loading settings: {str(e)}")
        raise


def get_drive_watcher(settings: Settings = Depends(get_settings)) -> DriveWatcher:
    """Get or create DriveWatcher instance."""
    global drive_watcher
    if drive_watcher is None:
        drive_watcher = DriveWatcher(
            folder_id=settings.TEAM_DRIVE_FOLDER_ID,
            credentials_path=settings.GOOGLE_APPLICATION_CREDENTIALS
        )
        logger.info("DriveWatcher initialized successfully")
    return drive_watcher
