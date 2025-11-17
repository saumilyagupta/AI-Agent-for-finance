"""Unified MCP server exposing all tools."""

import asyncio
import sys
import logging
import io
from pathlib import Path

# Add project root to path for subprocess execution
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Load .env file for environment variables (TAVILY_API_KEY, etc.)
try:
    from dotenv import load_dotenv
    env_path = project_root / ".env"
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass  # dotenv not required if env vars are set elsewhere

# CRITICAL: Redirect stdout during imports to prevent log contamination
# Save original stdout
_original_stdout = sys.stdout
# Temporarily redirect stdout to stderr during imports
sys.stdout = sys.stderr

# Configure all logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr,
    force=True
)

# Import with stdout redirected
from app.mcp.server.base import MCPServerBase, MCPTool
from app.tools.registry import tool_registry

# Restore stdout for JSON-RPC communication
sys.stdout = _original_stdout

# Re-configure any loggers that were set up during imports to use stderr
for name in logging.Logger.manager.loggerDict:
    log = logging.getLogger(name)
    if log.handlers:
        for handler in log.handlers[:]:
            log.removeHandler(handler)
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        log.addHandler(stderr_handler)
        log.propagate = False

logger = logging.getLogger("unified_mcp")


class UnifiedToolsServer(MCPServerBase):
    """Single MCP server that exposes all existing tools."""

    def __init__(self):
        super().__init__(name="unified_tools", version="1.0.0")
        self._register_all_tools()

    def _register_all_tools(self):
        """Register all tools from the tool registry."""
        # Get all tools from registry
        all_tools_info = tool_registry.get_all_tools_info()
        
        logger.info(f"Registering {len(all_tools_info)} tools in unified server")
        
        for tool_name, tool_info in all_tools_info.items():
            # Convert to MCP tool format
            mcp_tool = MCPTool(
                name=tool_name,
                description=tool_info['description'],
                input_schema=self._convert_schema(tool_info['input_schema']),
            )
            self.register_tool(mcp_tool)

    def _convert_schema(self, schema: dict) -> dict:
        """Convert tool schema to MCP JSON Schema format."""
        return {
            "type": "object",
            "properties": schema.get("properties", {}),
            "required": schema.get("required", []),
        }

    async def execute_tool(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool from the registry."""
        try:
            logger.info(f"Executing tool: {tool_name}")
            
            # Get tool from registry
            tool = tool_registry.get_tool(tool_name)
            if not tool:
                return {"error": f"Tool not found: {tool_name}"}
            
            # Execute the tool
            result = await tool.run(**arguments)
            
            # Convert to MCP content format
            if result.get("success"):
                # Format the result
                result_text = self._format_result(result.get("result"))
                content = [
                    {
                        "type": "text",
                        "text": result_text,
                    }
                ]
                return {"content": content}
            else:
                return {"error": result.get("error", "Unknown error")}
                
        except Exception as e:
            logger.error(f"Tool execution error: {e}", exc_info=True)
            return {"error": str(e)}

    def _format_result(self, result) -> str:
        """Format tool result as string."""
        if isinstance(result, str):
            return result
        elif isinstance(result, (dict, list)):
            import json
            return json.dumps(result, indent=2)
        else:
            return str(result)


async def main():
    """Run the unified MCP server."""
    from app.mcp.server.stdio_server import StdioMCPServer
    
    server_impl = UnifiedToolsServer()
    server = StdioMCPServer(server_impl)
    await server.start()


if __name__ == "__main__":
    asyncio.run(main())

