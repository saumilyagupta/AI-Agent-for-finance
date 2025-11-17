"""Task planning agent using LLM."""

import json
from typing import Any, Dict, List, Tuple

import networkx as nx

from app.core.llm_provider import llm_manager
from app.core.memory import memory_system
from app.core.models import ExecutionPlan, TaskDefinition
from app.tools.registry import tool_registry
from app.utils.logger import logger


class Planner:
    """Agent for planning task execution."""

    def __init__(self):
        self.tools = tool_registry.get_all_tools_info()

    async def create_plan(self, goal: str) -> Tuple[ExecutionPlan, Dict[str, Any]]:
        """Create execution plan from user goal."""
        try:
            logger.info(f"Creating plan for goal: {goal}")

            # Query memory for similar executions
            similar_executions = await memory_system.search_similar_executions(goal, k=3)
            similar_context = ""
            if similar_executions:
                similar_context = "\n\nSimilar past executions:\n"
                for ex in similar_executions:
                    similar_context += f"- {ex.get('content', '')[:200]}\n"

            # Create planning prompt
            tools_info = "\n".join(
                [
                    f"- {name}: {info['description']}"
                    for name, info in self.tools.items()
                ]
            )

            system_prompt = """You are an expert task planner for an autonomous AI agent system.
Your job is to break down user goals into actionable tasks with clear dependencies.

Available tools:
{tools}

CRITICAL: You MUST return valid JSON in EXACTLY this format. Each task MUST have these exact fields:
- id: unique identifier (e.g., "task_1", "task_2")
- name: short task name
- description: detailed description of what the task does
- tool_name: one of the available tool names from the list above
- input_params: object with tool-specific parameters
- dependencies: array of task IDs this task depends on (can be empty [])

Example format:
{{
  "tasks": [
    {{
      "id": "task_1",
      "name": "Search for weather information",
      "description": "Search the web for tomorrow's weather forecast in Tokyo",
      "tool_name": "web_search",
      "input_params": {{"query": "Tokyo weather tomorrow"}},
      "dependencies": []
    }},
    {{
      "id": "task_2",
      "name": "Convert temperature",
      "description": "Convert the temperature from Celsius to Fahrenheit",
      "tool_name": "calculator",
      "input_params": {{"expression": "(temp_c * 9/5) + 32"}},
      "dependencies": ["task_1"]
    }}
  ],
  "estimated_cost": 0.05,
  "estimated_time": 60
}}

IMPORTANT: Return ONLY the JSON object, no other text before or after."""

            user_prompt = f"""User Goal: {goal}

{similar_context}

Create a detailed execution plan. Break this goal into tasks, identify tools needed, and determine dependencies.
Return ONLY valid JSON following the exact format specified above."""

            # Generate plan using LLM
            response = await llm_manager.generate(
                prompt=user_prompt,
                system_prompt=system_prompt.format(tools=tools_info),
                temperature=0.3,  # Lower temperature for more consistent planning
            )
            
            # Store model response metadata
            model_response_meta = {
                "model": response.get("model", "unknown"),
                "tokens_used": response.get("tokens_used", 0),
                "cost": response.get("cost", 0.0),
            }
            logger.info(f"Model response received: {model_response_meta['model']}, tokens: {model_response_meta['tokens_used']}")

            # Parse JSON response
            content = response["content"].strip()
            
            # Extract JSON from markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            # Try to find JSON object in the response
            start_idx = content.find("{")
            end_idx = content.rfind("}")
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                content = content[start_idx:end_idx + 1]

            plan_data = json.loads(content)

            # Create TaskDefinition objects with validation
            tasks = []
            for idx, task_data in enumerate(plan_data.get("tasks", [])):
                # Validate and fix task data format
                if not isinstance(task_data, dict):
                    logger.warning(f"Task {idx} is not a dict, skipping")
                    continue
                
                # Ensure all required fields are present
                if "id" not in task_data:
                    task_data["id"] = f"task_{idx + 1}"
                if "name" not in task_data:
                    # Try to extract from other fields
                    task_data["name"] = task_data.get("task", task_data.get("description", f"Task {idx + 1}"))[:50]
                if "description" not in task_data:
                    task_data["description"] = task_data.get("task", task_data.get("name", f"Task {idx + 1}"))
                if "tool_name" not in task_data:
                    logger.warning(f"Task {task_data.get('id', idx)} missing tool_name, skipping")
                    continue
                if "input_params" not in task_data:
                    task_data["input_params"] = {}
                if "dependencies" not in task_data:
                    task_data["dependencies"] = []
                
                try:
                    task = TaskDefinition(**task_data)
                    tasks.append(task)
                except Exception as e:
                    logger.error(f"Failed to create task from data {task_data}: {e}")
                    continue

            # Validate dependencies and create DAG
            self._validate_dependencies(tasks)

            # Calculate execution order using topological sort
            execution_order = self._calculate_execution_order(tasks)
            for i, task in enumerate(tasks):
                task.execution_order = execution_order.get(task.id, i)

            plan = ExecutionPlan(
                tasks=tasks,
                estimated_cost=plan_data.get("estimated_cost", 0.0),
                estimated_time=plan_data.get("estimated_time", 0),
                total_tasks=len(tasks),
            )

            logger.info(f"Created plan with {len(tasks)} tasks")
            
            # Return plan and model response metadata
            model_response_meta = {
                "model": response.get("model", "unknown"),
                "tokens_used": response.get("tokens_used", 0),
                "cost": response.get("cost", 0.0),
                "content_preview": response.get("content", "")[:500] + "..." if len(response.get("content", "")) > 500 else response.get("content", ""),
            }
            return plan, model_response_meta

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse plan JSON: {e}")
            raise ValueError(f"Invalid plan format: {e}")
        except Exception as e:
            logger.error(f"Planning failed: {e}")
            raise

    def _validate_dependencies(self, tasks: List[TaskDefinition]):
        """Validate that all dependencies exist."""
        task_ids = {task.id for task in tasks}
        for task in tasks:
            for dep_id in task.dependencies:
                if dep_id not in task_ids:
                    logger.warning(f"Task {task.id} has invalid dependency: {dep_id}")
                    task.dependencies.remove(dep_id)

    def _calculate_execution_order(self, tasks: List[TaskDefinition]) -> dict:
        """Calculate execution order using topological sort."""
        # Create directed graph
        G = nx.DiGraph()
        for task in tasks:
            G.add_node(task.id)
            for dep_id in task.dependencies:
                G.add_edge(dep_id, task.id)  # Dependency -> Task

        # Check for cycles
        if not nx.is_directed_acyclic_graph(G):
            logger.warning("Plan contains cycles, attempting to resolve")
            # Remove cycles by removing some dependencies
            cycles = list(nx.simple_cycles(G))
            for cycle in cycles:
                if len(cycle) > 1:
                    # Remove last edge in cycle
                    G.remove_edge(cycle[-1], cycle[0])

        # Topological sort
        try:
            sorted_tasks = list(nx.topological_sort(G))
            order_map = {task_id: i for i, task_id in enumerate(sorted_tasks)}
            return order_map
        except Exception as e:
            logger.error(f"Topological sort failed: {e}")
            # Fallback: assign order based on dependencies count
            return {task.id: len(task.dependencies) for task in tasks}

