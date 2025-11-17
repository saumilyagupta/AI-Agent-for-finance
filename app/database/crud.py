"""CRUD operations for database models."""

from datetime import datetime
from typing import List, Optional, Union
from uuid import UUID

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.database.models import Execution, MemoryEntry, Task, TaskLog


# Execution CRUD
def create_execution(db: Session, goal: str) -> Execution:
    """Create a new execution."""
    execution = Execution(goal=goal, status="pending")
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


def get_execution(db: Session, execution_id: Union[UUID, str]) -> Optional[Execution]:
    """Get execution by ID."""
    execution_id_str = str(execution_id) if isinstance(execution_id, UUID) else execution_id
    return db.query(Execution).filter(Execution.id == execution_id_str, Execution.deleted_at.is_(None)).first()


def update_execution(
    db: Session,
    execution_id: Union[UUID, str],
    status: Optional[str] = None,
    cost: Optional[float] = None,
    tokens_used: Optional[int] = None,
    llm_provider: Optional[str] = None,
    error_message: Optional[str] = None,
    final_result: Optional[dict] = None,
) -> Optional[Execution]:
    """Update execution."""
    execution = get_execution(db, execution_id)
    if not execution:
        return None

    if status:
        execution.status = status
        if status in ["completed", "failed", "cancelled"]:
            execution.completed_at = datetime.utcnow()

    if cost is not None:
        execution.cost += cost
    if tokens_used is not None:
        execution.tokens_used += tokens_used
    if llm_provider:
        execution.llm_provider = llm_provider
    if error_message:
        execution.error_message = error_message
    if final_result:
        execution.final_result = final_result

    execution.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(execution)
    return execution


def list_executions(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    search: Optional[str] = None,
) -> List[Execution]:
    """List executions with pagination and filters."""
    query = db.query(Execution).filter(Execution.deleted_at.is_(None))

    if status:
        query = query.filter(Execution.status == status)
    if search:
        query = query.filter(Execution.goal.ilike(f"%{search}%"))

    return query.order_by(desc(Execution.created_at)).offset(skip).limit(limit).all()


def delete_execution(db: Session, execution_id: Union[UUID, str]) -> bool:
    """Soft delete execution."""
    execution = get_execution(db, execution_id)
    if not execution:
        return False

    execution.deleted_at = datetime.utcnow()
    execution.status = "cancelled"
    db.commit()
    return True


# Task CRUD
def create_task(
    db: Session,
    execution_id: Union[UUID, str],
    name: str,
    tool_name: str,
    description: Optional[str] = None,
    input_params: Optional[dict] = None,
    dependencies: Optional[List[str]] = None,
    execution_order: Optional[int] = None,
) -> Task:
    """Create a new task."""
    task = Task(
        execution_id=str(execution_id) if isinstance(execution_id, UUID) else execution_id,
        name=name,
        description=description,
        tool_name=tool_name,
        input_params=input_params or {},
        dependencies=dependencies or [],
        execution_order=execution_order,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_task(db: Session, task_id: Union[UUID, str]) -> Optional[Task]:
    """Get task by ID."""
    task_id_str = str(task_id) if isinstance(task_id, UUID) else task_id
    return db.query(Task).filter(Task.id == task_id_str).first()


def get_tasks_by_execution(db: Session, execution_id: Union[UUID, str]) -> List[Task]:
    """Get all tasks for an execution."""
    execution_id_str = str(execution_id) if isinstance(execution_id, UUID) else execution_id
    return db.query(Task).filter(Task.execution_id == execution_id_str).order_by(Task.execution_order).all()


def update_task(
    db: Session,
    task_id: Union[UUID, str],
    status: Optional[str] = None,
    result: Optional[dict] = None,
    error_message: Optional[str] = None,
    retry_count: Optional[int] = None,
) -> Optional[Task]:
    """Update task."""
    task = get_task(db, task_id)
    if not task:
        return None

    if status:
        task.status = status
        if status == "running" and not task.started_at:
            task.started_at = datetime.utcnow()
        elif status in ["completed", "failed", "skipped"]:
            task.completed_at = datetime.utcnow()

    if result is not None:
        task.result = result
    if error_message:
        task.error_message = error_message
    if retry_count is not None:
        task.retry_count = retry_count

    db.commit()
    db.refresh(task)
    return task


# TaskLog CRUD
def create_task_log(
    db: Session,
    task_id: Union[UUID, str],
    level: str,
    message: str,
    data: Optional[dict] = None,
) -> TaskLog:
    """Create a task log entry."""
    log = TaskLog(task_id=task_id, level=level, message=message, data=data)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def get_task_logs(db: Session, task_id: Union[UUID, str]) -> List[TaskLog]:
    """Get all logs for a task."""
    task_id_str = str(task_id) if isinstance(task_id, UUID) else task_id
    return db.query(TaskLog).filter(TaskLog.task_id == task_id_str).order_by(TaskLog.timestamp).all()


# MemoryEntry CRUD
def create_memory_entry(
    db: Session,
    content: str,
    execution_id: Optional[Union[UUID, str]] = None,
    keywords: Optional[List[str]] = None,
    context: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> MemoryEntry:
    """Create a memory entry."""
    entry = MemoryEntry(
        execution_id=str(execution_id) if isinstance(execution_id, UUID) else execution_id,
        content=content,
        keywords=keywords or [],
        context=context,
        tags=tags or [],
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_memory_entries(
    db: Session,
    execution_id: Optional[Union[UUID, str]] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[MemoryEntry]:
    """Get memory entries."""
    query = db.query(MemoryEntry).filter(MemoryEntry.deleted_at.is_(None))

    if execution_id:
        execution_id_str = str(execution_id) if isinstance(execution_id, UUID) else execution_id
        query = query.filter(MemoryEntry.execution_id == execution_id_str)

    return query.order_by(desc(MemoryEntry.timestamp)).offset(skip).limit(limit).all()


# Statistics
def get_execution_stats(db: Session) -> dict:
    """Get execution statistics."""
    total = db.query(func.count(Execution.id)).filter(Execution.deleted_at.is_(None)).scalar()
    completed = (
        db.query(func.count(Execution.id))
        .filter(Execution.status == "completed", Execution.deleted_at.is_(None))
        .scalar()
    )
    failed = (
        db.query(func.count(Execution.id))
        .filter(Execution.status == "failed", Execution.deleted_at.is_(None))
        .scalar()
    )
    total_cost = (
        db.query(func.sum(Execution.cost))
        .filter(Execution.deleted_at.is_(None))
        .scalar()
        or 0.0
    )
    total_tokens = (
        db.query(func.sum(Execution.tokens_used))
        .filter(Execution.deleted_at.is_(None))
        .scalar()
        or 0
    )

    return {
        "total_executions": total or 0,
        "completed": completed or 0,
        "failed": failed or 0,
        "total_cost": float(total_cost),
        "total_tokens": total_tokens or 0,
    }

