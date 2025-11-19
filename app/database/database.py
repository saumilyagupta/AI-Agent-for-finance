"""Database connection and session management."""

import os
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
            import urllib.parse
            
            # Parse connection URL to check port and provide guidance
            parsed = urllib.parse.urlparse(db_url)
            hostname = parsed.hostname
            port = parsed.port or 5432
            
            # Check if using pooler port (6543) - recommended for Render
            if port == 6543:
                logger.info("Using Supabase connection pooler (port 6543) - good for Render deployment")
            elif port == 5432:
                logger.warning(
                    "Using direct Supabase connection (port 5432). "
                    "For Render deployment, consider using connection pooler (port 6543) "
                    "to avoid IPv6 connectivity issues. "
                    "Update DATABASE_URL to use port 6543 and add ?pgbouncer=true"
                )
            
            # Build connection args with appropriate timeout
            # Use shorter timeout for Render (faster startup), longer for development
            is_render = "RENDER" in os.environ or "PORT" in os.environ
            timeout = 5 if is_render else 10  # 5s on Render, 10s locally
            
            connect_args = {
                "connect_timeout": timeout,
                "options": "-c statement_timeout=30000",  # 30 second statement timeout
                "sslmode": "require",  # Require SSL for Supabase
            }
            
            # Note: psycopg2/libpq will resolve DNS, and Render may resolve to IPv6
            # If IPv6 connection fails, the error will be caught and we'll fall back to SQLite
            # The best solution is to use Supabase connection pooler (port 6543) which uses IPv4
            
            # Create engine WITHOUT testing connection at import time
            # This allows uvicorn to bind to port immediately for Render compatibility
            # Connection will be validated lazily via pool_pre_ping when first used
            engine = create_engine(
                db_url,
                pool_pre_ping=True,  # Validates connections before using them
                pool_size=3,  # Reduced for Render
                max_overflow=5,  # Reduced for Render
                echo=settings.debug,
                connect_args=connect_args,
                pool_recycle=3600,
            )
            logger.info("Database engine configured (connection will be established on first use)")
        else:
            # Non-PostgreSQL database (SQLite, etc.)
            engine = create_engine(
                db_url,
                connect_args={"check_same_thread": False} if "sqlite" in db_url.lower() else {},
                echo=settings.debug,
            )
            logger.info(f"Connected to database: {db_url.split('@')[-1] if '@' in db_url else db_url}")
    except Exception as e:
        error_msg = str(e)
        logger.warning(f"Failed to connect to database: {e}")
        
        # Provide specific guidance for common errors
        if "Network is unreachable" in error_msg or "2406:da18" in error_msg:
            logger.error(
                "IPv6 connectivity issue detected. Render free-tier has IPv6 limitations.\n"
                "SOLUTION: Update your DATABASE_URL in Render environment variables:\n"
                "1. Go to Supabase Dashboard → Project Settings → Database\n"
                "2. Find 'Connection Pooling' section\n"
                "3. Copy the 'Connection string' (should use port 6543)\n"
                "4. Make sure it includes ?pgbouncer=true parameter\n"
                "5. Update DATABASE_URL in Render with this pooler URL\n"
                "Alternative: The app will continue with SQLite fallback (works fine for development)"
            )
        elif "connection to server" in error_msg.lower():
            logger.error(
                "Database connection failed. Possible causes:\n"
                "1. DATABASE_URL not set in Render environment variables\n"
                "2. Supabase project is paused (check Supabase dashboard)\n"
                "3. Network restrictions (IPv6 issue on Render)\n"
                "4. Wrong port (use 6543 for pooler, 5432 for direct)\n"
                "The app will continue with SQLite fallback."
            )
        else:
            logger.info("Falling back to SQLite database (this is normal if DATABASE_URL is not configured)")
        
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
        # Test connection first (this is where the actual connection happens)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection established successfully")
        
        # Create tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        
        # Check if Supabase is configured - if so, don't fall back to SQLite
        if settings.database_url and ("supabase" in settings.database_url.lower() or "postgres" in settings.database_url.lower()):
            logger.error(
                "PostgreSQL/Supabase connection failed. Please check:\n"
                "1. DATABASE_URL is correct in your environment\n"
                "2. Supabase project is active (not paused)\n"
                "3. Network allows outbound connections to port 6543\n"
                "4. Your IP is not blocked by Supabase firewall\n"
                "5. Try testing connection: psql 'your_database_url'"
            )
            # Re-raise the error - don't fall back to SQLite
            raise Exception(f"Database connection required but failed: {e}")
        else:
            # If no DATABASE_URL configured, raise error
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

