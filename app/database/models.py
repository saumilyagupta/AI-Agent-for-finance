"""SQLAlchemy database models."""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    create_engine,
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.types import TypeDecorator, CHAR

# UUID type that works with both PostgreSQL and SQLite
class GUID(TypeDecorator):
    """Platform-independent GUID type."""
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PostgresUUID())
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, str):
                return str(value)
            return value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, str):
                return str(value)
            return value

Base = declarative_base()


class Execution(Base):
    """Execution model for storing goal executions."""

    __tablename__ = "executions"

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid4()))
    goal = Column(Text, nullable=False)
    status = Column(
        String(20),
        nullable=False,
        default="pending",
    )  # pending, planning, running, completed, failed, cancelled
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    cost = Column(Float, default=0.0)  # Total cost in USD
    tokens_used = Column(Integer, default=0)
    llm_provider = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    final_result = Column(JSON, nullable=True)
    deleted_at = Column(DateTime, nullable=True)  # Soft delete

    # Relationships
    tasks = relationship("Task", back_populates="execution", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Execution(id={self.id}, goal={self.goal[:50]}..., status={self.status})>"


class Task(Base):
    """Task model for storing individual tasks within an execution."""

    __tablename__ = "tasks"

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid4()))
    execution_id = Column(GUID(), ForeignKey("executions.id"), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    tool_name = Column(String(100), nullable=False)
    status = Column(
        String(20),
        nullable=False,
        default="queued",
    )  # queued, running, completed, failed, skipped
    input_params = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    dependencies = Column(JSON, nullable=True)  # List of task IDs this depends on
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    retry_count = Column(Integer, default=0)
    execution_order = Column(Integer, nullable=True)  # Order in execution sequence

    # Relationships
    execution = relationship("Execution", back_populates="tasks")
    logs = relationship("TaskLog", back_populates="task", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Task(id={self.id}, name={self.name}, status={self.status})>"


class TaskLog(Base):
    """Task log model for storing execution logs."""

    __tablename__ = "task_logs"

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid4()))
    task_id = Column(GUID(), ForeignKey("tasks.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    level = Column(String(20), nullable=False)  # INFO, WARNING, ERROR, DEBUG
    message = Column(Text, nullable=False)
    data = Column(JSON, nullable=True)  # Additional structured data

    # Relationships
    task = relationship("Task", back_populates="logs")

    def __repr__(self):
        return f"<TaskLog(task_id={self.task_id}, level={self.level}, message={self.message[:50]})>"


class MemoryEntry(Base):
    """Memory entry model for storing execution memories in Supabase."""

    __tablename__ = "memory_entries"

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid4()))
    execution_id = Column(GUID(), ForeignKey("executions.id"), nullable=True)
    content = Column(Text, nullable=False)
    keywords = Column(JSON, nullable=True)  # List of keywords
    context = Column(Text, nullable=True)
    tags = Column(JSON, nullable=True)  # List of tags
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    retrieval_count = Column(Integer, default=0)
    deleted_at = Column(DateTime, nullable=True)  # Soft delete

    def __repr__(self):
        return f"<MemoryEntry(id={self.id}, content={self.content[:50]}...)>"

