"""ReAct agent using tools directly (no MCP overhead)."""

import json
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional
from uuid import UUID

from app.core.llm_provider import llm_manager
from app.core.memory import memory_system
from app.core.models import ExecutionEvent
from app.database.crud import create_execution, update_execution
from app.database.database import get_db_session
from app.tools.registry import tool_registry
from app.utils.config import settings
from app.utils.logger import logger


class ReActAgentDirect:
    """ReAct agent that uses tools directly (no MCP servers)."""

    def __init__(self, max_iterations: int = 20):
        self.max_iterations = max_iterations
        self.conversation_history: List[Dict[str, Any]] = []

    async def execute_goal(
        self, goal: str, execution_id: Optional[UUID] = None
    ) -> AsyncGenerator[ExecutionEvent, None]:
        """Execute a goal using ReAct loop with direct tool access."""
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

            # Get available tools from registry
            tools = self._get_tools_for_llm()
            logger.info(f"Loaded {len(tools)} tools from registry")

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
                for ex in similar[:2]:
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
                
                # Prepare messages for LLM
                messages = [{"role": "system", "content": system_prompt}] + self.conversation_history

                try:
                    response = await llm_manager.generate_with_tools(
                        messages=messages,
                        tools=tools,
                        temperature=0.7,
                    )
                    logger.info(f"LLM response: {len(response.get('content', ''))} chars, {len(response.get('tool_calls', []))} tool calls")
                except Exception as e:
                    logger.error(f"LLM call failed: {e}", exc_info=True)
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
                    # First, add assistant message with tool_calls to conversation
                    # This is required by OpenAI's API format
                    assistant_message = {
                        "role": "assistant",
                        "content": content if content else None,
                        "tool_calls": tool_calls,
                    }
                    self.conversation_history.append(assistant_message)
                    
                    # Now execute each tool call
                    for tool_call in tool_calls:
                        func_name = tool_call["function"]["name"]
                        func_args_str = tool_call["function"]["arguments"]
                        tool_call_id = tool_call.get("id", f"call_{iteration}")
                        
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

                        # Execute tool directly from registry
                        tool_result = await self._execute_tool(func_name, func_args)

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

                        # Add tool result to conversation with proper format
                        tool_message = {
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps(tool_result),
                        }
                        self.conversation_history.append(tool_message)

                yield ExecutionEvent(
                    type="iteration_complete",
                    message=f"Iteration {iteration} complete",
                    data={"iteration": iteration},
                    timestamp=datetime.utcnow().isoformat(),
                )

                # Safety check
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
                {"iterations": iteration},
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

    def _get_tools_for_llm(self) -> List[Dict[str, Any]]:
        """Get tools from registry formatted for LLM."""
        all_tools_info = tool_registry.get_all_tools_info()
        tools = []
        
        for tool_name, tool_info in all_tools_info.items():
            tools.append({
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool_info['description'],
                    "parameters": tool_info['input_schema'],
                },
            })
        
        return tools

    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool from the registry."""
        try:
            tool = tool_registry.get_tool(tool_name)
            if not tool:
                return {
                    "success": False,
                    "error": f"Tool not found: {tool_name}",
                }
            
            result = await tool.run(**arguments)
            return result
            
        except Exception as e:
            logger.error(f"Tool execution failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    TOOL_GUIDANCE = {
        "visualizer": (
            "Always provide 'data' with explicit x/y arrays (e.g. "
            "{\"x\": [...], \"y\": [...]}). For multi-series charts, use "
            "{\"series\": [{\"name\": \"Series1\", \"x\": [...], \"y\": [...]}]}. "
            "Never call this tool without data."
        ),
        "calculator": "Provide the exact mathematical expression in the 'expression' field.",
        "file_ops": (
            "Include 'operation' (read/write/list) and the appropriate path keys "
            "('file_path' or 'directory'). Without these the tool will fail."
        ),
        "api_client": (
            "Specify the full 'url'. For GET requests include query params in the URL. "
            "For POST provide 'method': 'POST' and a JSON-serialisable 'data' payload."
        ),
        "code_executor": (
            "Supply the Python code string in the 'code' field. Provide any required "
            "variables inside the code itself."
        ),
        "stock_market": (
            "Always include 'symbol' (ticker). Optional fields: 'interval', 'range'."
        ),
        "stock_calculator": (
            "Include 'symbol' and 'start_date'/'end_date' or a prepared price series."
        ),
        "web_search": "Pass a clear 'query' string. Optionally add 'max_results'.",
        "weather": (
            "Include either 'city' or the 'lat'/'lon' coordinates. "
            "For OpenWeather fallback ensure the API key exists."
        ),
    }

    def _build_system_prompt(self, tools: List[Dict], memory_context: str = "") -> str:
        """Build system prompt for ReAct agent."""
        tools_desc = "\n".join([
            f"- {tool['function']['name']}: {tool['function'].get('description', 'No description')}"
            for tool in tools
        ])

        tool_guidance_sections = []
        for tool in tools:
            name = tool["function"]["name"]
            guidance = self.TOOL_GUIDANCE.get(name)
            if guidance:
                tool_guidance_sections.append(f"{name}: {guidance}")

        tool_guidance_text = "\n".join(tool_guidance_sections) if tool_guidance_sections else "N/A"

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
4. If YES → Use the appropriate tool, ensure ALL required parameters are supplied, analyze results, then provide final answer
5. Be efficient - don't make unnecessary tool calls

Important:
- Tools are OPTIONAL, not mandatory - use them only when you truly need them
- For simple questions, respond immediately without tools
- ALWAYS provide ALL required parameters when calling tools (see tool-specific guidance below)
- When you have the answer (with or without tools), provide a clear final answer
- Format your final answer clearly, starting with "FINAL ANSWER:" followed by your complete response

Tool-specific guidance:
{tool_guidance_text}
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
react_agent_direct = ReActAgentDirect(max_iterations=20)

