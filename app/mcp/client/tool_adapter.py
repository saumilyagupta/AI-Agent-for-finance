"""Adapter to convert existing BaseTool implementations to MCP format."""

from typing import Any, Dict

from app.mcp.server.base import MCPServerBase, MCPTool
from app.tools.base import BaseTool
from app.utils.logger import logger


class ToolAdapter(MCPServerBase):
    """Adapter that wraps a BaseTool as an MCP server."""

    def __init__(self, tool: BaseTool):
        super().__init__(name=f"{tool.name}_server", version="1.0.0")
        self.tool = tool
        
        # Convert BaseTool to MCPTool
        mcp_tool = MCPTool(
            name=tool.name,
            description=tool.description,
            input_schema=self._convert_schema(tool.input_schema),
        )
        self.register_tool(mcp_tool)

    def _convert_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Convert BaseTool schema to MCP JSON Schema format."""
        # MCP uses standard JSON Schema
        return {
            "type": "object",
            "properties": schema.get("properties", {}),
            "required": schema.get("required", []),
        }

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the wrapped tool."""
        try:
            logger.info(f"Executing tool {tool_name} with arguments: {arguments}")
            
            # Execute the BaseTool
            result = await self.tool.run(**arguments)
            
            # Convert result to MCP content format
            if result.get("success"):
                content = [
                    {
                        "type": "text",
                        "text": self._format_result(result.get("result")),
                    }
                ]
                return {"content": content}
            else:
                return {"error": result.get("error", "Unknown error")}
                
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {"error": str(e)}

    def _format_result(self, result: Any) -> str:
        """Format tool result as string."""
        if isinstance(result, str):
            return result
        elif isinstance(result, (dict, list)):
            import json
            return json.dumps(result, indent=2)
        else:
            return str(result)








