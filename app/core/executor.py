"""Task execution engine with parallel execution and error handling."""

import asyncio
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)

from app.core.models import ExecutionEvent, ExecutionPlan, TaskDefinition
from app.database.crud import (
    create_task_log,
    get_task,
    update_task,
)
from app.database.database import get_db_session
from app.tools.registry import tool_registry
from app.utils.logger import logger


class ExecutionEngine:
    """Engine for executing tasks with parallelization and error handling."""

    def __init__(self, execution_id):
        self.execution_id = execution_id
        self.task_results: Dict[str, Any] = {}
        self.task_status: Dict[str, str] = {}
        self.circuit_breakers: Dict[str, int] = {}  # Track failures per tool
        self.max_failures = 3  # Circuit breaker threshold

    async def execute_plan(
        self, plan: ExecutionPlan
    ) -> AsyncGenerator[ExecutionEvent, None]:
        """Execute plan and stream events."""
        try:
            # Sort tasks by execution order
            sorted_tasks = sorted(plan.tasks, key=lambda t: t.execution_order or 0)

            # Group tasks by execution level (tasks that can run in parallel)
            execution_levels = self._group_by_level(sorted_tasks)

            for level, tasks in execution_levels.items():
                # Execute tasks in this level in parallel
                async for event in self._execute_level(tasks):
                    yield event

            # Final event
            yield ExecutionEvent(
                type="execution_completed",
                message="Execution completed",
                timestamp=datetime.utcnow().isoformat(),
            )

        except Exception as e:
            logger.error(f"Execution failed: {e}")
            yield ExecutionEvent(
                type="execution_failed",
                message=f"Execution failed: {str(e)}",
                timestamp=datetime.utcnow().isoformat(),
            )

    def _group_by_level(self, tasks: List[TaskDefinition]) -> Dict[int, List[TaskDefinition]]:
        """Group tasks by execution level (parallelization level)."""
        levels: Dict[int, List[TaskDefinition]] = {}
        task_levels: Dict[str, int] = {}

        for task in tasks:
            if not task.dependencies:
                level = 0
            else:
                # Level is max dependency level + 1
                level = max([task_levels.get(dep, 0) for dep in task.dependencies], default=0) + 1

            task_levels[task.id] = level
            if level not in levels:
                levels[level] = []
            levels[level].append(task)

        return levels

    async def _execute_level(
        self,
        tasks: List[TaskDefinition],
    ) -> AsyncGenerator[ExecutionEvent, None]:
        """Execute all tasks in a level in parallel."""
        # Create event queues for each task
        event_queues = [asyncio.Queue() for _ in tasks]

        # Create task coroutines
        async def run_task_with_queue(task, queue):
            async for event in self._execute_task(task):
                await queue.put(event)
            await queue.put(None)  # Sentinel

        # Start all tasks
        coroutines = [
            run_task_with_queue(task, queue)
            for task, queue in zip(tasks, event_queues)
        ]

        # Create tasks for concurrent execution
        task_tasks = [asyncio.create_task(coro) for coro in coroutines]

        # Yield events as they come
        active_queues = set(range(len(event_queues)))
        while active_queues:
            for i in list(active_queues):
                try:
                    event = await asyncio.wait_for(event_queues[i].get(), timeout=0.1)
                    if event is None:
                        active_queues.remove(i)
                    else:
                        yield event
                except asyncio.TimeoutError:
                    continue

        # Wait for all tasks to complete
        await asyncio.gather(*task_tasks, return_exceptions=True)

    async def _execute_task(
        self,
        task: TaskDefinition,
    ) -> AsyncGenerator[ExecutionEvent, None]:
        """Execute a single task."""
        task_id = task.id

        try:
            # Check circuit breaker
            if self.circuit_breakers.get(task.tool_name, 0) >= self.max_failures:
                logger.warning(f"Circuit breaker open for tool: {task.tool_name}")
                yield ExecutionEvent(
                    type="task_failed",
                    task_id=task_id,
                    task_name=task.name,
                    message=f"Tool {task.tool_name} is disabled due to repeated failures",
                    timestamp=datetime.utcnow().isoformat(),
                )
                return

            # Emit task started event
            yield ExecutionEvent(
                type="task_started",
                task_id=task_id,
                task_name=task.name,
                message=f"Starting task: {task.name}",
                timestamp=datetime.utcnow().isoformat(),
            )

            # Update task status in database
            with get_db_session() as db:
                update_task(db, task_id, status="running")

            # Resolve dependencies (inject results from previous tasks)
            resolved_params = self._resolve_dependencies(task)

            # Get tool and execute
            tool = tool_registry.get_tool(task.tool_name)
            if not tool:
                raise ValueError(f"Tool not found: {task.tool_name}")

            # For code_executor, inject all resolved params as variables
            # This makes input_params and all individual params available in the code
            if task.tool_name == "code_executor":
                # Create a copy to avoid modifying the original
                code_params = resolved_params.copy()
                # Add input_params dict for code that references it
                code_params["input_params"] = resolved_params.copy()
                resolved_params = code_params

            # Validate input parameters before execution
            if not tool.validate_input(**resolved_params):
                # Try to provide better error message
                schema = tool.input_schema
                required = schema.get("required", [])
                missing = [field for field in required if field not in resolved_params]
                if missing:
                    raise ValueError(f"Missing required parameters: {', '.join(missing)}")
                raise ValueError("Invalid input parameters")

            # Execute with retry
            result = await self._execute_with_retry(tool, resolved_params)

            # Update circuit breaker
            if result.get("success"):
                self.circuit_breakers[task.tool_name] = 0  # Reset on success
            else:
                self.circuit_breakers[task.tool_name] = self.circuit_breakers.get(task.tool_name, 0) + 1

            # Store result
            self.task_results[task_id] = result
            self.task_status[task_id] = "completed" if result.get("success") else "failed"

            # Update database
            with get_db_session() as db:
                update_task(
                    db,
                    task_id,
                    status="completed" if result.get("success") else "failed",
                    result=result,
                    error_message=result.get("error"),
                )
                create_task_log(
                    db,
                    task_id,
                    "INFO" if result.get("success") else "ERROR",
                    result.get("message", "Task completed") if result.get("success") else result.get("error", "Task failed"),
                )

            # Emit completion event
            yield ExecutionEvent(
                type="task_completed" if result.get("success") else "task_failed",
                task_id=task_id,
                task_name=task.name,
                message=result.get("message", "Task completed") if result.get("success") else result.get("error", "Task failed"),
                data={"result": result.get("result")},
                timestamp=datetime.utcnow().isoformat(),
            )

        except Exception as e:
            logger.error(f"Task {task_id} execution failed: {e}")
            self.task_status[task_id] = "failed"

            with get_db_session() as db:
                update_task(db, task_id, status="failed", error_message=str(e))
                create_task_log(db, task_id, "ERROR", str(e))

            yield ExecutionEvent(
                type="task_failed",
                task_id=task_id,
                task_name=task.name,
                message=f"Task failed: {str(e)}",
                timestamp=datetime.utcnow().isoformat(),
            )

    def _resolve_dependencies(self, task: TaskDefinition) -> Dict[str, Any]:
        """Resolve task dependencies by injecting previous task results."""
        params = task.input_params.copy()

        # Collect all dependency results
        dep_results = {}
        
        # Replace dependency references with actual results
        for dep_id in task.dependencies:
            if dep_id in self.task_results:
                dep_result = self.task_results[dep_id]
                
                # Check if dependency task failed
                if not dep_result.get("success", False):
                    # Dependency failed - mark this in params so tools can handle it
                    logger.warning(f"Dependency {dep_id} failed, task {task.id} may not work correctly")
                    params[f"dep_{dep_id}_failed"] = True
                    params[f"dep_{dep_id}_error"] = dep_result.get("error", "Unknown error")
                    continue
                
                result_data = dep_result.get("result")
                
                # Skip if result_data is None or placeholder
                if result_data is None:
                    continue
                
                # Check for placeholder values
                if isinstance(result_data, str) and result_data.upper() == "PLACEHOLDER":
                    logger.warning(f"Dependency {dep_id} returned placeholder value")
                    continue
                
                # Inject dependency result
                params[f"dep_{dep_id}"] = result_data
                dep_results[dep_id] = result_data
                
                # If result is a dict, extract common keys as variables
                # This allows code to access variables like 'celsius', 'temperature', etc.
                if isinstance(result_data, dict):
                    for key, value in result_data.items():
                        # Skip placeholder values
                        if isinstance(value, str) and value.upper() == "PLACEHOLDER":
                            continue
                        # Add common variable names to params for code executor
                        if key not in params or key not in ['code', 'timeout']:
                            params[key] = value
                            dep_results[key] = value
                # If result is a simple value, try to extract it
                elif isinstance(result_data, (int, float, str)):
                    # Skip placeholder strings
                    if isinstance(result_data, str) and result_data.upper() == "PLACEHOLDER":
                        continue
                    # For simple values, add to dep_results
                    dep_results[dep_id] = result_data
        
        # Add all dependency results as a collection for code executor
        if dep_results:
            params['dep_results'] = dep_results
        
        return params

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _execute_with_retry(self, tool, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tool with retry logic."""
        return await tool.run(**params)

    def get_final_result(self) -> Dict[str, Any]:
        """Get final execution result."""
        completed = sum(1 for status in self.task_status.values() if status == "completed")
        failed = sum(1 for status in self.task_status.values() if status == "failed")

        # Get results from last task or aggregate all
        final_result = None
        if self.task_results:
            # Use result from last completed task
            last_task_id = max(self.task_results.keys(), key=lambda k: self.task_status.get(k, ""))
            final_result = self.task_results[last_task_id].get("result")

        return {
            "tasks_completed": completed,
            "tasks_failed": failed,
            "total_tasks": len(self.task_status),
            "final_result": final_result,
            "all_results": self.task_results,
        }

