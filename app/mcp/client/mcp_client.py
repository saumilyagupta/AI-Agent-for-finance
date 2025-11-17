"""MCP client for communicating with MCP servers."""

import asyncio
import json
import uuid
from typing import Any, Dict, List, Optional

from app.utils.logger import logger


class MCPClient:
    """Client for communicating with MCP servers via STDIO."""

    def __init__(self, server_name: str, command: List[str]):
        self.server_name = server_name
        self.command = command
        self.process: Optional[asyncio.subprocess.Process] = None
        self.request_id = 0
        self.initialized = False
        self.tools: List[Dict[str, Any]] = []

    async def start(self):
        """Start the MCP server process."""
        try:
            logger.debug(f"Creating subprocess for {self.server_name}: {' '.join(self.command)}")
            
            # Increase buffer limit for large responses (e.g., from stock_calculator)
            # Default is 64KB, we increase to 10MB
            limit = 10 * 1024 * 1024  # 10MB
            
            self.process = await asyncio.create_subprocess_exec(
                *self.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=limit,
            )
            
            logger.debug(f"Subprocess created for {self.server_name}, PID: {self.process.pid}")
            
            # Wait a moment for process to start
            await asyncio.sleep(0.1)
            
            # Check if process is still running
            if self.process.returncode is not None:
                # Process died immediately
                stderr = await self.process.stderr.read()
                error_msg = stderr.decode() if stderr else "No error message"
                raise RuntimeError(f"Server process died immediately: {error_msg}")
            
            logger.info(f"Started MCP server process: {self.server_name}")
            
            # Initialize the server
            await self.initialize()
            
            # List available tools
            await self.list_tools()
            
        except Exception as e:
            logger.error(f"Failed to start MCP server {self.server_name}: {e}", exc_info=True)
            if self.process and self.process.stderr:
                try:
                    stderr = await asyncio.wait_for(self.process.stderr.read(), timeout=1.0)
                    if stderr:
                        logger.error(f"Server stderr: {stderr.decode()}")
                except:
                    pass
            raise

    async def initialize(self):
        """Initialize the MCP server."""
        response = await self._send_request({
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {
                    "name": "autonomous-agent",
                    "version": "1.0.0",
                },
            },
        })
        
        if "error" in response:
            raise RuntimeError(f"Initialization failed: {response['error']}")
        
        self.initialized = True
        logger.info(f"MCP server {self.server_name} initialized")

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from the server."""
        response = await self._send_request({
            "method": "tools/list",
            "params": {},
        })
        
        if "error" in response:
            raise RuntimeError(f"Failed to list tools: {response['error']}")
        
        self.tools = response.get("result", {}).get("tools", [])
        logger.info(f"MCP server {self.server_name} has {len(self.tools)} tools")
        return self.tools

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the MCP server."""
        if not self.initialized:
            raise RuntimeError("MCP client not initialized")
        
        response = await self._send_request({
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        })
        
        if "error" in response:
            error_msg = response["error"].get("message", "Unknown error")
            logger.error(f"Tool call failed: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "result": None,
            }
        
        # Extract content from MCP response
        result = response.get("result", {})
        content = result.get("content", [])
        
        # Convert MCP content to our format
        if content:
            # Combine all text content
            text_parts = []
            for item in content:
                if item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
            
            result_text = "\n".join(text_parts) if text_parts else str(content)
            
            return {
                "success": True,
                "result": result_text,
                "raw_content": content,
            }
        
        return {
            "success": True,
            "result": result,
        }

    async def _send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send a request to the MCP server and wait for response."""
        if not self.process or self.process.stdin is None or self.process.stdout is None:
            raise RuntimeError("MCP server process not running")
        
        # Add JSON-RPC fields
        self.request_id += 1
        full_request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            **request,
        }
        
        # Send request
        request_json = json.dumps(full_request) + "\n"
        self.process.stdin.write(request_json.encode())
        await self.process.stdin.drain()
        
        # Read response
        response_line = await self.process.stdout.readline()
        if not response_line:
            raise RuntimeError("MCP server closed connection")
        
        response_text = response_line.decode().strip()
        logger.debug(f"Received from {self.server_name}: {response_text[:200]}")
        
        try:
            response = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from {self.server_name}: {response_text[:500]}")
            raise
        
        return response

    async def stop(self):
        """Stop the MCP server process."""
        if self.process:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
            logger.info(f"Stopped MCP server: {self.server_name}")

    def get_tools_for_llm(self) -> List[Dict[str, Any]]:
        """Get tools formatted for LLM function calling."""
        llm_tools = []
        for tool in self.tools:
            # Don't prefix with server name if it's the unified server
            tool_name = tool['name']
            if self.server_name == "unified_tools":
                # Use tool name directly
                function_name = tool_name
            else:
                # Prefix with server name
                function_name = f"{self.server_name}_{tool_name}"
            
            llm_tools.append({
                "type": "function",
                "function": {
                    "name": function_name,
                    "description": tool.get("description", ""),
                    "parameters": tool.get("inputSchema", {}),
                },
            })
        return llm_tools


