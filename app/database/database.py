"""Database connection and session management."""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import Base
from app.utils.config import settings
from app.utils.logger import logger

# Create engine
if settings.database_url:
    try:
        # Test connection with a short timeout
        test_engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=1,
            max_overflow=0,
            echo=False,
            connect_args={"connect_timeout": 5} if "postgresql" in settings.database_url else {},
        )
        # Try to connect
        with test_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        # If successful, create the main engine
        engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            echo=settings.debug,
        )
        logger.info("Connected to Supabase database")
    except Exception as e:
        logger.warning(f"Failed to connect to Supabase: {e}, falling back to SQLite")
        engine = create_engine(
            "sqlite:///./agent.db",
            connect_args={"check_same_thread": False},
            echo=settings.debug,
        )
else:
    # Fallback to SQLite for development
    logger.info("No DATABASE_URL set, using SQLite for development")
    engine = create_engine(
        "sqlite:///./agent.db",
        connect_args={"check_same_thread": False},
        echo=settings.debug,
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _create_sqlite_engine():
    """Create SQLite engine as fallback."""
    return create_engine(
        "sqlite:///./agent.db",
        connect_args={"check_same_thread": False},
        echo=settings.debug,
    )


def init_db():
    """Initialize database tables."""
    global engine, SessionLocal
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        # If Supabase connection fails, fall back to SQLite
        if settings.database_url and "supabase" in settings.database_url.lower():
            logger.warning("Supabase connection failed, falling back to SQLite")
            engine = _create_sqlite_engine()
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            Base.metadata.create_all(bind=engine)
            logger.info("SQLite database initialized as fallback")
        else:
            raise


def get_db() -> Generator[Session, None, None]:
    """Dependency for FastAPI to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager for database sessions."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

