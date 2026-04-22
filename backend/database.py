"""
Database configuration and session management for FireReach.
"""

import logging
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker


load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_DATABASE_URL = "sqlite:///./firereach.db"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL).strip() or DEFAULT_DATABASE_URL

engine = None
SessionLocal = None
Base = declarative_base()


def _build_engine(database_url: str):
    """
    Creates an SQLAlchemy engine with connection arguments optimized for the dialect.
    """
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine_kwargs = {"connect_args": connect_args}
    if not database_url.startswith("sqlite"):
        engine_kwargs["pool_pre_ping"] = True
    return create_engine(database_url, **engine_kwargs)


def configure_database(database_url: str | None = None):
    """
    Initializes the database connection.
    Attempts to connect to the provided URL, falling back to a local SQLite database if connection fails.

    Args:
        database_url: Optional connection string to override environment variables.

    Returns:
        The configured SQLAlchemy engine.

    Raises:
        RuntimeError: If all connection attempts fail.
    """
    global DATABASE_URL, engine, SessionLocal

    requested_url = str(database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)).strip() or DEFAULT_DATABASE_URL
    fallback_url = DEFAULT_DATABASE_URL
    candidates = [requested_url]
    if requested_url != fallback_url:
        candidates.append(fallback_url)

    last_error = None
    for candidate_url in candidates:
        engine = _build_engine(candidate_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))

            DATABASE_URL = candidate_url
            if candidate_url != requested_url:
                logger.warning(
                    "DATABASE_URL is unavailable; using local SQLite fallback at %s.",
                    fallback_url,
                )
            return engine
        except Exception as exc:
            last_error = exc
            if candidate_url != fallback_url:
                logger.warning(
                    "Failed to connect to DATABASE_URL '%s'. Falling back to SQLite. Error: %s",
                    candidate_url,
                    exc,
                )

    raise RuntimeError(f"Unable to initialize database: {last_error}") from last_error


# Initialize the database immediately upon module load
configure_database()


def get_db():
    """
    Dependency generator that provides a database session.
    Ensures the session is closed when the request completes.

    Yields:
        An active SQLAlchemy database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
