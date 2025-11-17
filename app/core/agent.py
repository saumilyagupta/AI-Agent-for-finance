"""Main autonomous agent orchestrator."""

from typing import AsyncGenerator, Optional
from uuid import UUID

from app.core.memory import memory_system
from app.core.models import ExecutionEvent, ExecutionResult
from app.core.react_agent_direct import react_agent_direct
from app.database.crud import get_execution, get_tasks_by_execution
from app.database.database import get_db_session
from app.utils.logger import logger


class AutonomousAgent:
    """Main orchestrator for autonomous agent system using ReAct loop."""

    def __init__(self):
        # Use direct ReAct agent (no MCP overhead)
        self.react_agent = react_agent_direct

    async def execute_goal(
        self, goal: str, execution_id: Optional[UUID] = None
    ) -> AsyncGenerator[ExecutionEvent, None]:
        """Execute a user goal using ReAct agent."""
        try:
            # Delegate to ReAct agent which handles the entire loop
            async for event in self.react_agent.execute_goal(goal, execution_id):
                yield event

        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            yield ExecutionEvent(
                type="execution_failed",
                message=f"Execution failed: {str(e)}",
                timestamp=__import__("datetime").datetime.utcnow().isoformat(),
            )

    async def get_execution_result(self, execution_id: UUID) -> ExecutionResult:
        """Get execution result."""
        with get_db_session() as db:
            execution = get_execution(db, execution_id)
            if not execution:
                raise ValueError(f"Execution {execution_id} not found")

            # For ReAct agent, tasks may not be used the same way
            # Check if tasks exist (legacy executions)
            tasks = get_tasks_by_execution(db, execution_id)
            completed = sum(1 for t in tasks if t.status == "completed")
            failed = sum(1 for t in tasks if t.status == "failed")
            
            # For ReAct executions, use iterations from final_result
            if execution.final_result and isinstance(execution.final_result, dict):
                iterations = execution.final_result.get("iterations", 0)
                if iterations > 0:
                    # ReAct execution
                    return ExecutionResult(
                        execution_id=execution_id,
                        status=execution.status,
                        goal=execution.goal,
                        tasks_completed=iterations,  # Use iterations as completed count
                        tasks_failed=0,
                        total_tasks=iterations,
                        cost=execution.cost or 0.0,
                        tokens_used=execution.tokens_used or 0,
                        final_result=execution.final_result,
                        error_message=execution.error_message,
                    )

            # Legacy planner/executor execution
            return ExecutionResult(
                execution_id=execution_id,
                status=execution.status,
                goal=execution.goal,
                tasks_completed=completed,
                tasks_failed=failed,
                total_tasks=len(tasks),
                cost=execution.cost or 0.0,
                tokens_used=execution.tokens_used or 0,
                final_result=execution.final_result,
                error_message=execution.error_message,
            )


# Global agent instance
agent = AutonomousAgent()

