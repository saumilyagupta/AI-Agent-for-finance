"""Pydantic schemas for API requests and responses."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class GoalRequest(BaseModel):
    """Request to create a new goal execution."""

    goal: str = Field(..., description="User goal to execute", min_length=1)


class GoalResponse(BaseModel):
    """Response after creating a goal."""

    execution_id: UUID = Field(..., description="Execution ID")
    message: str = Field(..., description="Status message")


class ExecutionStatusResponse(BaseModel):
    """Execution status response."""

    execution_id: UUID
    goal: str
    status: str
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None
    cost: float
    tokens_used: int
    error_message: Optional[str] = None


class TaskResponse(BaseModel):
    """Task information."""

    id: UUID
    name: str
    description: Optional[str]
    tool_name: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class ExecutionDetailResponse(BaseModel):
    """Detailed execution response."""

    execution: ExecutionStatusResponse
    tasks: List[TaskResponse]
    plan: Optional[Dict[str, Any]] = None


class HistoryResponse(BaseModel):
    """Execution history response."""

    executions: List[ExecutionStatusResponse]
    total: int
    skip: int
    limit: int


class StatsResponse(BaseModel):
    """Statistics response."""

    total_executions: int
    completed: int
    failed: int
    total_cost: float
    total_tokens: int


class ToolStatsResponse(BaseModel):
    """Tool usage statistics."""

    tool_name: str
    usage_count: int
    error_count: int
    success_rate: float

