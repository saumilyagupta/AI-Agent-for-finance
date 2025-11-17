"""Base MCP server class following Model Context Protocol specification."""

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.utils.logger import logger


class MCPTool:
    """Represents an MCP tool definition."""

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
    ):
        self.name = name
        self.description = description
        self.input_schema = input_schema

    def to_dict(self) -> Dict[str, Any]:
        """Convert to MCP tool format."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


class MCPServerBase(ABC):
    """Base class for MCP servers."""

    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.tools: Dict[str, MCPTool] = {}

    def register_tool(self, tool: MCPTool):
        """Register a tool with this server."""
        self.tools[tool.name] = tool
        logger.info(f"MCP Server '{self.name}' registered tool: {tool.name}")

    @abstractmethod
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool with given arguments.
        
        Returns:
            Dict with 'content' (list of content items) or 'error'
        """
        pass

    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle an MCP protocol request."""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        try:
            if method == "initialize":
                return await self._handle_initialize(request_id, params)
            elif method == "tools/list":
                return await self._handle_list_tools(request_id)
            elif method == "tools/call":
                return await self._handle_call_tool(request_id, params)
            else:
                return self._error_response(
                    request_id, -32601, f"Method not found: {method}"
                )
        except Exception as e:
            logger.error(f"Error handling request: {e}")
            return self._error_response(request_id, -32603, str(e))

    async def _handle_initialize(self, request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {
                    "name": self.name,
                    "version": self.version,
                },
                "capabilities": {
                    "tools": {},
                },
            },
        }

    async def _handle_list_tools(self, request_id: Any) -> Dict[str, Any]:
        """Handle tools/list request."""
        tools_list = [tool.to_dict() for tool in self.tools.values()]
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": tools_list,
            },
        }

    async def _handle_call_tool(self, request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name not in self.tools:
            return self._error_response(
                request_id, -32602, f"Tool not found: {tool_name}"
            )

        try:
            result = await self.execute_tool(tool_name, arguments)
            
            # Format result as MCP content
            if "error" in result:
                return self._error_response(request_id, -32603, result["error"])
            
            # Convert result to MCP content format
            content = result.get("content", [])
            if not isinstance(content, list):
                # Wrap simple results in content array
                content = [{"type": "text", "text": str(content)}]
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": content,
                },
            }
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return self._error_response(request_id, -32603, str(e))

    def _error_response(self, request_id: Any, code: int, message: str) -> Dict[str, Any]:
        """Create an error response."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message,
            },
        }








