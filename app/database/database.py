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
        # Note: For Render deployment with Supabase, use connection pooler URL (port 6543)
        # Example: postgresql://user:pass@db.xxx.supabase.co:6543/postgres?pgbouncer=true
        # This avoids IPv6 connectivity issues on Render
        db_url = settings.database_url
        
        if "postgresql" in db_url.lower() or "postgres" in db_url.lower():
            # Build connection args with timeout settings for better reliability
            connect_args = {
                "connect_timeout": 10,
                "options": "-c statement_timeout=30000",  # 30 second statement timeout
            }
            
            # For psycopg2, we can't directly force IPv4, but we can set connection parameters
            # The issue is likely network restrictions on Render, so we'll use a longer timeout
            # and better error handling
            
            # Test connection with a short timeout
            test_engine = create_engine(
                db_url,
                pool_pre_ping=True,
                pool_size=1,
                max_overflow=0,
                echo=False,
                connect_args=connect_args,
                # Use connection pooler for better reliability
                pool_recycle=3600,  # Recycle connections after 1 hour
            )
            # Try to connect with a timeout
            with test_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            # If successful, create the main engine
            engine = create_engine(
                db_url,
                pool_pre_ping=True,
                pool_size=3,  # Reduced for Render
                max_overflow=5,  # Reduced for Render
                echo=settings.debug,
                connect_args=connect_args,
                pool_recycle=3600,
            )
            logger.info("Connected to Supabase database")
        else:
            # Non-PostgreSQL database (SQLite, etc.)
            engine = create_engine(
                db_url,
                connect_args={"check_same_thread": False} if "sqlite" in db_url.lower() else {},
                echo=settings.debug,
            )
            logger.info(f"Connected to database: {db_url.split('@')[-1] if '@' in db_url else db_url}")
    except Exception as e:
        logger.warning(f"Failed to connect to database: {e}, falling back to SQLite")
        logger.info("This is normal if DATABASE_URL is not set or network is restricted (e.g., Render IPv6 limitations)")
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

