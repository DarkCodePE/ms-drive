from typing import Generator, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from psycopg2 import connect, sql
import logging
from contextlib import contextmanager

from app.config.base import Base
from app.config.config import get_settings, Settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.settings = get_settings()
        self._setup_engines()
        self._setup_sessions()
        self._initialized = True

    def _setup_engines(self):
        """Initialize database engines"""
        # Sync engine
        self.engine = create_engine(
            self.settings.database_url,
            pool_size=self.settings.DB_POOL_SIZE,
            max_overflow=self.settings.DB_MAX_OVERFLOW,
            pool_timeout=self.settings.DB_POOL_TIMEOUT,
            pool_pre_ping=True
        )

        # Async engine
        self.async_engine = create_async_engine(
            self.settings.async_database_url,
            echo=True
        )

    def _setup_sessions(self):
        """Initialize session factories"""
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

    def create_database(self) -> None:
        """Create database if it doesn't exist"""
        try:
            # Connect to default postgres database
            conn = connect(
                dbname="postgres",
                user=self.settings.DB_USER,
                password=self.settings.DB_PASSWORD,
                host=self.settings.DB_HOST,
                port=self.settings.DB_PORT
            )
            conn.autocommit = True
            cursor = conn.cursor()

            # Check if database exists
            cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{self.settings.DB_NAME}'")
            exists = cursor.fetchone()

            if not exists:
                # Create database if it doesn't exist
                cursor.execute(sql.SQL("CREATE DATABASE {}").format(
                    sql.Identifier(self.settings.DB_NAME)
                ))
                logger.info(f"Database '{self.settings.DB_NAME}' created successfully")
            else:
                logger.info(f"Database '{self.settings.DB_NAME}' already exists")

        except Exception as e:
            logger.error(f"Error creating database: {str(e)}")
            raise
        finally:
            cursor.close()
            conn.close()

    def init_db(self) -> None:
        """Initialize database schema"""
        try:
            # Create database if doesn't exist
            self.create_database()

            # Create all tables
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database schema initialized successfully")

        except Exception as e:
            logger.error(f"Error initializing database: {str(e)}")
            raise

    @contextmanager
    def get_db(self) -> Generator[Session, None, None]:
        """Get database session with context management"""
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    async def get_async_db(self) -> AsyncSession:
        """Get async database session"""
        async with self.AsyncSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()


# Global instance
db_manager = DatabaseManager()