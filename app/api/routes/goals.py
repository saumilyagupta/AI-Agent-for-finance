"""Goal execution routes."""

from typing import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.api.schemas import ExecutionDetailResponse, ExecutionStatusResponse, GoalRequest, GoalResponse
from app.core.agent import agent
from app.core.models import ExecutionEvent
from app.database.crud import (
    create_execution,
    delete_execution,
    get_execution,
    get_tasks_by_execution,
    update_execution,
)
from app.database.database import get_db
from app.utils.logger import logger

router = APIRouter(prefix="/goals", tags=["goals"])


@router.post("", response_model=GoalResponse, status_code=201)
async def create_goal(request: GoalRequest):
    """Create a new goal execution."""
    try:
        db = next(get_db())
        execution = create_execution(db, request.goal)
        logger.info(f"Created execution {execution.id} for goal: {request.goal}")

        return GoalResponse(
            execution_id=execution.id,
            message="Execution created successfully",
        )
    except Exception as e:
        logger.error(f"Failed to create execution: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{execution_id}", response_model=ExecutionStatusResponse)
async def get_goal_status(execution_id: UUID):
    """Get execution status."""
    db = next(get_db())
    execution = get_execution(db, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    # Format dates with UTC timezone indicator
    def format_utc_date(dt):
        if dt is None:
            return None
        return dt.isoformat() + 'Z' if dt.tzinfo is None else dt.isoformat()
    
    return ExecutionStatusResponse(
        execution_id=execution.id,
        goal=execution.goal,
        status=execution.status,
        created_at=format_utc_date(execution.created_at),
        updated_at=format_utc_date(execution.updated_at),
        completed_at=format_utc_date(execution.completed_at),
        cost=execution.cost or 0.0,
        tokens_used=execution.tokens_used or 0,
        error_message=execution.error_message,
    )


@router.get("/{execution_id}/details", response_model=ExecutionDetailResponse)
async def get_goal_details(execution_id: UUID):
    """Get detailed execution information including tasks."""
    db = next(get_db())
    execution = get_execution(db, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    # Format dates with UTC timezone indicator
    def format_utc_date(dt):
        if dt is None:
            return None
        return dt.isoformat() + 'Z' if dt.tzinfo is None else dt.isoformat()
    
    tasks = get_tasks_by_execution(db, execution_id)
    task_responses = [
        {
            "id": task.id,
            "name": task.name,
            "description": task.description,
            "tool_name": task.tool_name,
            "status": task.status,
            "result": task.result,
            "error_message": task.error_message,
            "started_at": format_utc_date(task.started_at),
            "completed_at": format_utc_date(task.completed_at),
        }
        for task in tasks
    ]
    
    return ExecutionDetailResponse(
        execution={
            "execution_id": execution.id,
            "goal": execution.goal,
            "status": execution.status,
            "created_at": format_utc_date(execution.created_at),
            "updated_at": format_utc_date(execution.updated_at),
            "completed_at": format_utc_date(execution.completed_at),
            "cost": execution.cost or 0.0,
            "tokens_used": execution.tokens_used or 0,
            "error_message": execution.error_message,
        },
        tasks=task_responses,
    )


@router.delete("/{execution_id}", status_code=204)
async def delete_goal(execution_id: UUID):
    """Delete/cancel an execution."""
    db = next(get_db())
    success = delete_execution(db, execution_id)
    if not success:
        raise HTTPException(status_code=404, detail="Execution not found")
    return None


@router.websocket("/{execution_id}/stream")
async def stream_execution(websocket: WebSocket, execution_id: UUID):
    """WebSocket endpoint for real-time execution streaming."""
    await websocket.accept()
    logger.info(f"WebSocket connection opened for execution {execution_id}")

    try:
        # Get execution goal
        db = next(get_db())
        execution = get_execution(db, execution_id)
        if not execution:
            await websocket.send_json({"error": "Execution not found"})
            await websocket.close()
            return

            # Start execution if not already started
        if execution.status == "pending":
            # Update status to running
            update_execution(db, execution_id, status="running")
            
            # Execute goal and stream events (use existing execution_id)
            async for event in agent.execute_goal(execution.goal, execution_id=execution_id):
                event_dict = event.dict()
                # Add execution_id to event
                event_dict["execution_id"] = str(execution_id)
                await websocket.send_json(event_dict)

                # Close connection if execution completed or failed
                if event.type in ["execution_completed", "execution_failed"]:
                    break

        else:
            # Execution already in progress or completed - send current status
            await websocket.send_json({
                "type": "status",
                "message": f"Execution status: {execution.status}",
                "execution_id": str(execution_id),
            })
            # If completed, send final result
            if execution.status == "completed" and execution.final_result:
                await websocket.send_json({
                    "type": "execution_completed",
                    "message": "Execution already completed",
                    "data": {"result": execution.final_result},
                    "execution_id": str(execution_id),
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for execution {execution_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"error": str(e), "type": "error"})
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass

