"""ReAct (Reasoning + Acting) agent implementation with MCP tools."""

import json
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional
from uuid import UUID

from app.core.llm_provider import llm_manager
from app.core.memory import memory_system
from app.core.models import ExecutionEvent
from app.database.crud import create_execution, update_execution
from app.database.database import get_db_session
from app.mcp.server_manager import mcp_server_manager
from app.utils.config import settings
from app.utils.logger import logger


class ReActAgent:
    """ReAct agent that iteratively calls tools until task completion."""

    def __init__(self, max_iterations: int = 20):
        self.max_iterations = max_iterations
        self.conversation_history: List[Dict[str, Any]] = []

    async def execute_goal(
        self, goal: str, execution_id: Optional[UUID] = None
    ) -> AsyncGenerator[ExecutionEvent, None]:
        """Execute a goal using ReAct loop with MCP tools."""
        total_cost = 0.0
        total_tokens = 0
        iteration = 0

        try:
            # Create or use existing execution
            if execution_id is None:
                with get_db_session() as db:
                    execution = create_execution(db, goal)
                    execution_id = execution.id
                    logger.info(f"Created execution {execution_id} for goal: {goal}")
            else:
                logger.info(f"Using existing execution {execution_id}")

            # Update status
            with get_db_session() as db:
                update_execution(db, execution_id, status="running")

            # Initialize MCP servers if not already started
            if not mcp_server_manager.clients:
                yield ExecutionEvent(
                    type="system_info",
                    message="Starting MCP servers...",
                    timestamp=datetime.utcnow().isoformat(),
                )
                await mcp_server_manager.start_all_servers()

            # Get available tools
            tools = mcp_server_manager.get_all_tools_for_llm()
            logger.info(f"Loaded {len(tools)} tools from MCP servers")

            yield ExecutionEvent(
                type="system_info",
                message=f"Loaded {len(tools)} tools: {', '.join([t['function']['name'] for t in tools])}",
                timestamp=datetime.utcnow().isoformat(),
            )

            # Query memory for similar executions
            similar = await memory_system.search_similar_executions(goal, k=3)
            memory_context = ""
            if similar:
                memory_context = "\n\nSimilar past executions:\n"
                for ex in similar[:2]:  # Limit to 2 for context size
                    memory_context += f"- {ex.get('content', '')[:200]}\n"

            # Build system prompt
            system_prompt = self._build_system_prompt(tools, memory_context)

            # Initialize conversation with user goal
            self.conversation_history = [
                {"role": "user", "content": f"Please complete the following task:\n\n{goal}"}
            ]

            # ReAct loop
            task_complete = False
            final_answer = None

            while not task_complete and iteration < self.max_iterations:
                iteration += 1

                yield ExecutionEvent(
                    type="iteration_started",
                    message=f"Iteration {iteration}/{self.max_iterations}",
                    data={"iteration": iteration},
                    timestamp=datetime.utcnow().isoformat(),
                )

                # Call LLM with tools
                logger.info(f"ReAct iteration {iteration}: Calling LLM with {len(tools)} tools")
                logger.debug(f"Conversation history has {len(self.conversation_history)} messages")
                
                # Prepare messages for LLM
                messages = [{"role": "system", "content": system_prompt}] + self.conversation_history
                logger.debug(f"Total messages being sent to LLM: {len(messages)}")

                try:
                    response = await llm_manager.generate_with_tools(
                        messages=messages,
                        tools=tools,
                        temperature=0.7,
                    )
                    logger.info(f"LLM response received: {len(response.get('content', ''))} chars, {len(response.get('tool_calls', []))} tool calls")
                except Exception as e:
                    logger.error(f"LLM call failed in iteration {iteration}: {e}", exc_info=True)
                    raise

                # Track costs
                total_cost += response.get("cost", 0)
                total_tokens += response.get("tokens_used", 0)

                # Emit model response event
                yield ExecutionEvent(
                    type="model_response",
                    message=f"Model ({response['model']}) responded",
                    data={
                        "model": response["model"],
                        "tokens_used": response["tokens_used"],
                        "cost": response["cost"],
                        "iteration": iteration,
                    },
                    timestamp=datetime.utcnow().isoformat(),
                )

                content = response.get("content", "")
                tool_calls = response.get("tool_calls", [])

                # Check if model provided thinking/reasoning
                if content and not tool_calls:
                    yield ExecutionEvent(
                        type="model_thinking",
                        message="Model is reasoning...",
                        data={"content": content, "iteration": iteration},
                        timestamp=datetime.utcnow().isoformat(),
                    )

                    # Add to conversation
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": content,
                    })

                    # Check if this is the final answer
                    if self._is_final_answer(content):
                        task_complete = True
                        final_answer = content
                        break

                # Execute tool calls
                if tool_calls:
                    for tool_call in tool_calls:
                        func_name = tool_call["function"]["name"]
                        func_args_str = tool_call["function"]["arguments"]
                        
                        try:
                            func_args = json.loads(func_args_str) if isinstance(func_args_str, str) else func_args_str
                        except json.JSONDecodeError:
                            func_args = {}

                        yield ExecutionEvent(
                            type="tool_call_initiated",
                            message=f"Calling tool: {func_name}",
                            data={
                                "tool": func_name,
                                "arguments": func_args,
                                "iteration": iteration,
                            },
                            timestamp=datetime.utcnow().isoformat(),
                        )

                        # Execute tool via MCP
                        tool_result = await mcp_server_manager.call_tool(func_name, func_args)

                        yield ExecutionEvent(
                            type="tool_result_received",
                            message=f"Tool {func_name} completed",
                            data={
                                "tool": func_name,
                                "result": tool_result,
                                "success": tool_result.get("success", False),
                                "iteration": iteration,
                            },
                            timestamp=datetime.utcnow().isoformat(),
                        )

                        # Add tool result to conversation
                        self.conversation_history.append({
                            "role": "tool",
                            "content": json.dumps(tool_result),
                            "name": func_name,
                        })

                yield ExecutionEvent(
                    type="iteration_complete",
                    message=f"Iteration {iteration} complete",
                    data={"iteration": iteration},
                    timestamp=datetime.utcnow().isoformat(),
                )

                # Safety check - if no tool calls and no final answer, prompt for conclusion
                if not tool_calls and not task_complete:
                    self.conversation_history.append({
                        "role": "user",
                        "content": "Please provide your final answer or call a tool to continue."
                    })

            # Check if max iterations reached
            if iteration >= self.max_iterations and not task_complete:
                final_answer = "Maximum iterations reached. Task may be incomplete."
                logger.warning(f"Execution {execution_id} reached max iterations")

            # Finalize
            if not final_answer:
                final_answer = "Task completed."

            # Update database
            with get_db_session() as db:
                update_execution(
                    db,
                    execution_id,
                    status="completed",
                    cost=total_cost,
                    tokens_used=total_tokens,
                    final_result={"answer": final_answer, "iterations": iteration},
                )

            # Store in memory
            await memory_system.store_execution(
                execution_id,
                goal,
                {"iterations": iteration, "tools_used": [t["function"]["name"] for t in tools]},
                final_answer,
                success=True,
            )

            yield ExecutionEvent(
                type="final_answer",
                message="Task completed with final answer",
                data={
                    "answer": final_answer,
                    "iterations": iteration,
                    "total_cost": total_cost,
                    "total_tokens": total_tokens,
                },
                timestamp=datetime.utcnow().isoformat(),
            )

            yield ExecutionEvent(
                type="execution_completed",
                message="Execution completed successfully",
                data={
                    "execution_id": str(execution_id),
                    "iterations": iteration,
                    "total_cost": total_cost,
                    "total_tokens": total_tokens,
                },
                timestamp=datetime.utcnow().isoformat(),
            )

        except Exception as e:
            logger.error(f"ReAct agent execution failed: {e}", exc_info=True)
            
            if execution_id:
                with get_db_session() as db:
                    update_execution(
                        db,
                        execution_id,
                        status="failed",
                        error_message=str(e),
                    )

            yield ExecutionEvent(
                type="execution_failed",
                message=f"Execution failed: {str(e)}",
                timestamp=datetime.utcnow().isoformat(),
            )

    def _build_system_prompt(self, tools: List[Dict], memory_context: str = "") -> str:
        """Build system prompt for ReAct agent."""
        tools_desc = "\n".join([
            f"- {tool['function']['name']}: {tool['function'].get('description', 'No description')}"
            for tool in tools
        ])

        return f"""You are an intelligent AI agent that helps users by reasoning and using tools ONLY when necessary.

Available tools (use only when needed):
{tools_desc}

Decision Making:
1. **First, think**: Can I answer this with my existing knowledge?
   - Simple questions (greetings, definitions, general knowledge) → Answer directly
   - Current information, calculations, file operations → Use appropriate tool
   
2. **Before calling any tool, ask yourself**:
   - Do I really need external data for this?
   - Can I answer with general knowledge?
   - Is a tool absolutely necessary?

3. **When to use tools**:
   ✓ Web search: For current events, real-time data, specific facts you don't know
   ✓ Calculator: For complex mathematical calculations
   ✓ File operations: When user asks to read/write files
   ✓ Code execution: When user asks to run code
   ✓ Visualizer: When user explicitly asks for charts/graphs
   
4. **When NOT to use tools**:
   ✗ Simple greetings ("hi", "hello", "how are you")
   ✗ General knowledge questions you can answer
   ✗ Explanations of concepts you know
   ✗ Simple math you can do mentally
   ✗ Questions about yourself or your capabilities

Your approach:
1. Read the user's query carefully
2. Think: "Do I need a tool for this?"
3. If NO → Answer directly with "FINAL ANSWER: [your response]"
4. If YES → Use the appropriate tool, analyze results, then provide final answer
5. Be efficient - don't make unnecessary tool calls

Important:
- Tools are OPTIONAL, not mandatory - use them only when you truly need them
- For simple questions, respond immediately without tools
- ALWAYS provide ALL required parameters when calling tools
- When you have the answer (with or without tools), provide a clear final answer
- Format your final answer clearly, starting with "FINAL ANSWER:" followed by your complete response
{memory_context}

Be smart and efficient - minimize unnecessary tool calls."""

    def _is_final_answer(self, content: str) -> bool:
        """Check if content contains a final answer."""
        indicators = [
            "FINAL ANSWER:",
            "final answer:",
            "Final Answer:",
            "In conclusion,",
            "To summarize,",
            "Here's the complete answer",
        ]
        
        content_lower = content.lower()
        return any(indicator.lower() in content_lower for indicator in indicators)


# Global ReAct agent instance
react_agent = ReActAgent(max_iterations=20)


