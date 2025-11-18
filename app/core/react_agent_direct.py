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
            "REQUIRED: 'chart_type' (string) and 'data' (object with x/y arrays). "
            "For single series: data={'x': [...], 'y': [...]}. "
            "For multi-series: data={'series': [{'name': 'Series1', 'x': [...], 'y': [...]}, ...]}. "
            "Chart types: 'line' (for functions/equations), 'bar', 'scatter', 'pie', 'candlestick', 'multi_line', 'multi_bar', 'grouped_bar', 'stacked_bar'. "
            "OPTIONAL: 'title', 'x_label', 'y_label' (strings), 'output_format' ('html' or 'json', default: 'json'). "
            "CRITICAL for mathematical functions (e.g., 'plot y = 2^x + 10'): "
            "1) Use code_executor FIRST to calculate x/y values: generate x with np.linspace(start, end, num_points) "
            "(e.g., x = np.linspace(-5, 5, 100) for range -5 to 5 with 100 points; adjust range based on equation domain), "
            "compute y from equation (e.g., y = 2**x + 10), convert to lists: x_list = x.tolist(), y_list = y.tolist(). "
            "2) Call visualizer with chart_type='line', data={'x': x_list, 'y': y_list}, title='y = 2^x + 10', x_label='x', y_label='y'. "
            "Workflow: code_executor → visualizer. Never call visualizer without pre-calculated data arrays."
        ),
        "calculator": (
            "REQUIRED: Either 'expression' (string) OR 'data' (array of numbers) + 'stat_op' (string). "
            "For math expressions: provide 'expression' (e.g., '2**3 + 5', 'sqrt(16)', 'sin(pi/2)'). "
            "For statistics: provide 'data' array and optionally 'stat_op' ('mean', 'median', 'std', 'var', 'min', 'max', 'sum'). "
            "If 'stat_op' omitted with 'data', returns all statistics. "
            "OPTIONAL: 'operation' ('evaluate' or 'statistics') - auto-detected if omitted. "
            "Examples: {'expression': '2**10 + 5'}, {'data': [1,2,3,4,5], 'stat_op': 'mean'}, {'data': [10,20,30]}."
        ),
        "file_ops": (
            "REQUIRED: 'operation' ('read' or 'write'), 'file_path' (string), 'file_type' ('csv', 'json', 'pdf', 'text'). "
            "For 'read': provide operation='read', file_path (relative to project root or file_workspace/), file_type. "
            "For 'write': provide operation='write', file_path (writes go to file_workspace/), file_type, and 'data' (object/string). "
            "Read can access files in project root or file_workspace/. Write always saves to file_workspace/ for safety. "
            "Examples: {'operation': 'read', 'file_path': 'data.csv', 'file_type': 'csv'}, "
            "{'operation': 'write', 'file_path': 'output.json', 'file_type': 'json', 'data': {'key': 'value'}}."
        ),
        "api_client": (
            "REQUIRED: 'url' (string, full URL including protocol). "
            "OPTIONAL: 'method' ('GET' or 'POST', default: 'GET'), 'headers' (object with key-value pairs), "
            "'data' (object for POST request body), 'parse_html' (boolean, default: false), "
            "'fallback_to_search' (boolean, default: true), 'search_query' (string for fallback). "
            "For GET: include query params in URL (e.g., 'https://api.example.com/data?param=value'). "
            "For POST: set method='POST' and provide 'data' object (will be JSON-serialized). "
            "If API fails and fallback_to_search=true, automatically uses web_search. "
            "Examples: {'url': 'https://api.example.com/data'}, "
            "{'url': 'https://api.example.com/submit', 'method': 'POST', 'data': {'key': 'value'}}."
        ),
        "code_executor": (
            "REQUIRED: 'code' (string containing Python code). "
            "OPTIONAL: 'timeout' (integer seconds, default: 10). "
            "Executes Python code safely with restricted imports. Available: numpy, pandas, sympy, math, json, datetime, etc. "
            "Use this to calculate values before plotting (generate x/y arrays for visualizer), process data, or run computations. "
            "Code runs in isolated workspace (code_exec_workspace/). Returns stdout, stderr, and return value. "
            "For plotting functions: generate x with np.linspace(), compute y, convert to lists with .tolist(). "
            "Example: {'code': 'import numpy as np\\nx = np.linspace(-5, 5, 100)\\ny = 2**x + 10\\nprint({\"x\": x.tolist(), \"y\": y.tolist()})'}."
        ),
        "stock_market": (
            "REQUIRED: 'symbol' (string, ticker symbol like 'AAPL', 'MSFT', 'RELIANCE.NS' for NSE, 'RELIANCE.BO' for BSE). "
            "OPTIONAL: 'period' ('1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max', default: '1y'), "
            "'interval' ('1m', '5m', '15m', '1h', '1d', '1wk', '1mo', default: '1d'), "
            "'data_type' ('history', 'info', 'financials', 'dividends', 'splits', 'all', default: 'history'). "
            "Returns OHLCV data, company info, financials, dividends, or splits based on data_type. "
            "Examples: {'symbol': 'AAPL'}, {'symbol': 'RELIANCE.NS', 'period': '6mo', 'interval': '1d'}."
        ),
        "stock_calculator": (
            "REQUIRED: 'data' (object with OHLCV data: {'Date': [...], 'Open': [...], 'High': [...], 'Low': [...], 'Close': [...], 'Volume': [...]} or list of records). "
            "OPTIONAL: 'features' (array of strings: 'price', 'volume', 'momentum', 'volatility', 'statistical', 'all', default: ['all']). "
            "Calculates 30-40 technical indicators (RSI, MACD, Bollinger Bands, EMA, etc.). "
            "Input data typically comes from stock_market tool. Returns DataFrame with all computed features. "
            "Example: {'data': stock_data_from_stock_market, 'features': ['all']} or {'data': stock_data, 'features': ['momentum', 'volatility']}."
        ),
        "stock_analysis": (
            "REQUIRED: 'symbol' (string, ticker symbol like 'AAPL', 'TSLA', 'RELIANCE.NS'). "
            "OPTIONAL: 'period' ('1mo', '3mo', '6mo', '1y', '2y', default: '3mo'), "
            "'include_prediction' (boolean, default: true for trend prediction). "
            "Performs comprehensive stock analysis: fetches data, calculates technical indicators (RSI, MACD, Bollinger Bands, etc.), "
            "and optionally predicts trend direction. Returns analysis summary with indicators, trend prediction, and insights. "
            "Example: {'symbol': 'AAPL', 'period': '6mo', 'include_prediction': true}."
        ),
        "web_search": (
            "REQUIRED: 'query' (string, search query). "
            "OPTIONAL: 'max_results' (integer, default: 5), 'search_depth' ('basic' or 'advanced', default: 'basic'), "
            "'include_domains' (array of strings), 'exclude_domains' (array of strings), "
            "'include_answer' (boolean, default: true for AI-generated summary). "
            "Uses Tavily API for AI-optimized search. Returns ranked results with titles, snippets, URLs, relevance scores, and optional AI answer. "
            "Use for current events, real-time data, specific facts. "
            "Examples: {'query': 'latest AI developments 2024'}, {'query': 'Python best practices', 'max_results': 10, 'search_depth': 'advanced'}."
        ),
        "weather": (
            "REQUIRED: 'city' (string, city name like 'London', 'New York', 'Kanpur'). "
            "OPTIONAL: 'country' (string, country code like 'US', 'GB', 'IN'), "
            "'units' ('celsius', 'fahrenheit', 'kelvin', default: 'celsius'). "
            "Returns current weather: temperature, conditions, humidity, wind speed, pressure, visibility. "
            "Uses OpenWeatherMap API if configured, otherwise falls back to web scraping. "
            "Examples: {'city': 'London'}, {'city': 'New York', 'country': 'US', 'units': 'fahrenheit'}."
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
   ✓ Code execution: When user asks to run code OR when you need to calculate values for plotting (e.g., generate x/y arrays for mathematical functions)
   ✓ Visualizer: When user explicitly asks for charts/graphs/plots. For mathematical functions, FIRST calculate x/y values using code_executor, THEN plot with visualizer
   
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

