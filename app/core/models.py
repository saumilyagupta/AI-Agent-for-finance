"""Pydantic models for agent components."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TaskDefinition(BaseModel):
    """Definition of a single task."""

    id: str = Field(..., description="Unique task identifier")
    name: str = Field(..., description="Task name")
    description: str = Field(..., description="Task description")
    tool_name: str = Field(..., description="Tool to use for this task")
    input_params: Dict[str, Any] = Field(default_factory=dict, description="Tool input parameters")
    dependencies: List[str] = Field(default_factory=list, description="List of task IDs this depends on")
    execution_order: Optional[int] = Field(None, description="Order in execution sequence")


class ExecutionPlan(BaseModel):
    """Complete execution plan with tasks and dependencies."""

    tasks: List[TaskDefinition] = Field(..., description="List of tasks to execute")
    estimated_cost: float = Field(0.0, description="Estimated cost in USD")
    estimated_time: int = Field(0, description="Estimated time in seconds")
    total_tasks: int = Field(..., description="Total number of tasks")


class ExecutionEvent(BaseModel):
    """Event emitted during execution."""

    type: str = Field(
        ..., 
        description="""Event type:
        - planning_started, plan_generated (legacy planner events)
        - task_started, task_completed, task_failed (legacy task events)
        - execution_completed, execution_failed (completion events)
        - system_info (system information)
        - model_response (LLM response with metadata)
        - model_thinking (model reasoning/thought process)
        - tool_call_initiated (tool being called with parameters)
        - tool_result_received (tool execution result)
        - iteration_started, iteration_complete (ReAct iteration events)
        - final_answer (model provided final answer)
        """
    )
    task_id: Optional[str] = Field(None, description="Task ID (if applicable)")
    task_name: Optional[str] = Field(None, description="Task name (if applicable)")
    message: str = Field(..., description="Event message")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional event data")
    timestamp: str = Field(..., description="Event timestamp")


class ExecutionResult(BaseModel):
    """Final execution result."""

    execution_id: UUID = Field(..., description="Execution ID")
    status: str = Field(..., description="Execution status")
    goal: str = Field(..., description="Original goal")
    tasks_completed: int = Field(..., description="Number of completed tasks")
    tasks_failed: int = Field(..., description="Number of failed tasks")
    total_tasks: int = Field(..., description="Total number of tasks")
    cost: float = Field(..., description="Total cost in USD")
    tokens_used: int = Field(..., description="Total tokens used")
    final_result: Optional[Dict[str, Any]] = Field(None, description="Final execution result")
    error_message: Optional[str] = Field(None, description="Error message if failed")

