"""MCP server for calculator tool."""

import asyncio
import sys
from pathlib import Path

# Add project root to path for subprocess execution
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.mcp.client.tool_adapter import ToolAdapter
from app.mcp.server.stdio_server import StdioMCPServer
from app.tools.calculator import CalculatorTool


async def main():
    """Run calculator MCP server."""
    tool = CalculatorTool()
    adapter = ToolAdapter(tool)
    server = StdioMCPServer(adapter)
    await server.start()


if __name__ == "__main__":
    asyncio.run(main())


