"""MCP server for web search tool."""

import asyncio
import sys
from pathlib import Path

# Add project root to path for subprocess execution
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Load .env file for environment variables (TAVILY_API_KEY)
try:
    from dotenv import load_dotenv
    env_path = project_root / ".env"
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass  # dotenv not required if env vars are set elsewhere

from app.mcp.client.tool_adapter import ToolAdapter
from app.mcp.server.stdio_server import StdioMCPServer
from app.tools.web_search import WebSearchTool


async def main():
    """Run web search MCP server."""
    tool = WebSearchTool()
    adapter = ToolAdapter(tool)
    server = StdioMCPServer(adapter)
    await server.start()


if __name__ == "__main__":
    asyncio.run(main())


