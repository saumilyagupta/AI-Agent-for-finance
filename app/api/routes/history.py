"""Execution history routes."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.api.schemas import ExecutionStatusResponse, HistoryResponse
from app.core.memory import memory_system
from app.database.crud import get_execution, list_executions
from app.database.database import get_db
from app.utils.logger import logger

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=HistoryResponse)
async def get_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    """Get execution history with pagination and filters."""
    try:
        db = next(get_db())
        executions = list_executions(db, skip=skip, limit=limit, status=status, search=search)

        # Format dates with UTC timezone indicator
        def format_utc_date(dt):
            if dt is None:
                return None
            return dt.isoformat() + 'Z' if dt.tzinfo is None else dt.isoformat()
        
        execution_responses = [
            ExecutionStatusResponse(
                execution_id=ex.id,
                goal=ex.goal,
                status=ex.status,
                created_at=format_utc_date(ex.created_at),
                updated_at=format_utc_date(ex.updated_at),
                completed_at=format_utc_date(ex.completed_at),
                cost=ex.cost or 0.0,
                tokens_used=ex.tokens_used or 0,
                error_message=ex.error_message,
            )
            for ex in executions
        ]

        # Get total count (simplified - in production, use a separate count query)
        total = len(execution_responses)  # This is approximate

        return HistoryResponse(
            executions=execution_responses,
            total=total,
            skip=skip,
            limit=limit,
        )
    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_history_semantic(query: str = Query(..., min_length=1), k: int = Query(5, ge=1, le=20)):
    """Semantic search through execution history using A-MEM."""
    try:
        results = await memory_system.search_similar_executions(query, k=k)
        return {
            "query": query,
            "results": results,
            "count": len(results),
        }
    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{execution_id}")
async def get_execution_history(execution_id: UUID):
    """Get detailed execution history."""
    db = next(get_db())
    execution = get_execution(db, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    # Get memory context if available
    memory_context = await memory_system.get_execution_context(execution_id)

    # Format dates with UTC timezone indicator
    def format_utc_date(dt):
        if dt is None:
            return None
        return dt.isoformat() + 'Z' if dt.tzinfo is None else dt.isoformat()
    
    return {
        "execution": {
            "id": str(execution.id),
            "goal": execution.goal,
            "status": execution.status,
            "created_at": format_utc_date(execution.created_at),
            "completed_at": format_utc_date(execution.completed_at),
            "cost": execution.cost or 0.0,
            "tokens_used": execution.tokens_used or 0,
        },
        "memory_context": memory_context,
    }

