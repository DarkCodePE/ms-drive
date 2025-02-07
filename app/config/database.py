from functools import lru_cache
from typing import Optional, Generator

from pydantic.v1 import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
import os
from dotenv import load_dotenv
from psycopg2 import connect, sql

import logging

from app.config.base import Base
from app.config.config import get_settings

logger = logging.getLogger(__name__)


def create_database_if_not_exists() -> None:
    """Create the database if it doesn't exist."""
    settings = get_settings()

    try:
        conn = connect(
            dbname="postgres",
            user=settings.db_user,
            password=settings.db_password,
            host=settings.db_host,
            port=settings.db_port
        )
        conn.autocommit = True
        cursor = conn.cursor()

        cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{settings.db_name}'")
        exists = cursor.fetchone()

        if not exists:
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(
                sql.Identifier(settings.db_name)
            ))
            logger.info(f"Database '{settings.db_name}' created successfully")
        else:
            logger.info(f"Database '{settings.db_name}' already exists")

    except Exception as e:
        logger.error(f"Error creating database: {str(e)}")
        raise
    finally:
        cursor.close()
        conn.close()


class Database:
    def __init__(self):
        """Initialize database connections."""
        self.settings = get_settings()

        # Sync engine
        self.engine = create_engine(
            self.settings.database_url,
            pool_size=self.settings.db_pool_size,
            max_overflow=self.settings.db_max_overflow,
            pool_timeout=self.settings.db_pool_timeout,
            pool_pre_ping=True
        )

        # Async engine
        self.async_engine = create_async_engine(
            self.settings.async_database_url,
            echo=True
        )

        # Session factories
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

        self.AsyncSessionLocal = async_sessionmaker(
            self.async_engine,
            expire_on_commit=False,
            class_=AsyncSession
        )

    def init_db(self) -> None:
        """Initialize the database."""
        create_database_if_not_exists()

        Base.metadata.create_all(bind=self.engine)
        logger.info("Database initialized successfully")

    def get_db(self) -> Generator[Session, None, None]:
        """Get database session."""
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    async def get_async_db(self) -> AsyncSession:
        """Get async database session."""
        async with self.AsyncSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()


# Global database instance
db = Database()