"""Health check routes."""

from fastapi import APIRouter, HTTPException

from app.core.llm_provider import llm_manager
from sqlalchemy import text
from app.database.database import engine, get_db_session
from app.database.models import Base, Execution, Task, TaskLog, MemoryEntry
from app.utils.logger import logger

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check():
    """Basic health check."""
    return {"status": "healthy", "service": "autonomous-ai-agent"}


@router.get("/database")
async def database_health():
    """Database connectivity check."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Database unavailable: {str(e)}")


@router.get("/llm")
async def llm_health():
    """LLM provider availability check."""
    try:
        # Try a simple generation
        response = await llm_manager.generate("test", max_tokens=5)
        return {
            "status": "healthy",
            "primary_provider": "available" if llm_manager.primary_provider else "unavailable",
            "fallback_provider": "available" if llm_manager.fallback_provider else "unavailable",
        }
    except Exception as e:
        logger.error(f"LLM health check failed: {e}")
        return {
            "status": "degraded",
            "error": str(e),
        }


@router.delete("/database/clear", status_code=200)
async def clear_database():
    """Clear all database data (executions, tasks, logs, memory)."""
    db = None
    try:
        db = next(get_db_session())
        
        # Delete all data (in correct order due to foreign keys)
        deleted_counts = {}
        
        # Delete task logs first (has foreign key to tasks)
        deleted_counts["task_logs"] = db.query(TaskLog).delete()
        
        # Delete tasks (has foreign key to executions)
        deleted_counts["tasks"] = db.query(Task).delete()
        
        # Delete memory entries
        deleted_counts["memory_entries"] = db.query(MemoryEntry).delete()
        
        # Delete executions last
        deleted_counts["executions"] = db.query(Execution).delete()
        
        db.commit()
        
        logger.info(f"Database cleared: {deleted_counts}")
        
        return {
            "status": "success",
            "message": "All database data cleared",
            "deleted": deleted_counts,
        }
    except Exception as e:
        logger.error(f"Failed to clear database: {e}")
        if db:
            db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to clear database: {str(e)}")
    finally:
        if db:
            db.close()

