"""MCP server manager for lifecycle management."""

import asyncio
import sys
from pathlib import Path
from typing import Dict, List, Optional

from app.mcp.client.mcp_client import MCPClient
from app.utils.logger import logger


class MCPServerManager:
    """Manager for MCP server lifecycle and registry."""

    def __init__(self):
        self.clients: Dict[str, MCPClient] = {}
        self.server_configs = self._get_server_configs()

    def _get_server_configs(self) -> Dict[str, List[str]]:
        """Get configuration for all MCP servers."""
        python_exe = sys.executable
        base_path = Path(__file__).parent / "servers"
        
        # Single unified server for all tools
        return {
            "unified_tools": [python_exe, str(base_path / "unified_server.py")],
        }

    async def start_all_servers(self):
        """Start all MCP servers."""
        logger.info("Starting all MCP servers...")
        
        tasks = []
        for server_name, command in self.server_configs.items():
            tasks.append(self._start_server(server_name, command))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check for failures
        failed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                server_name = list(self.server_configs.keys())[i]
                logger.error(f"Failed to start server {server_name}: {result}")
                failed.append(server_name)
        
        if failed:
            logger.warning(f"Failed to start servers: {', '.join(failed)}")
        
        logger.info(f"Started {len(self.clients)} MCP servers successfully")

    async def _start_server(self, server_name: str, command: List[str]):
        """Start a single MCP server."""
        try:
            logger.debug(f"Starting {server_name} with command: {' '.join(command)}")
            client = MCPClient(server_name, command)
            await client.start()
            self.clients[server_name] = client
            logger.info(f"Started MCP server: {server_name}")
        except Exception as e:
            logger.error(f"Failed to start {server_name}: {e}", exc_info=True)
            raise

    async def stop_all_servers(self):
        """Stop all MCP servers."""
        logger.info("Stopping all MCP servers...")
        
        tasks = []
        for client in self.clients.values():
            tasks.append(client.stop())
        
        await asyncio.gather(*tasks, return_exceptions=True)
        self.clients.clear()
        logger.info("All MCP servers stopped")

    def get_client(self, server_name: str) -> Optional[MCPClient]:
        """Get an MCP client by server name."""
        return self.clients.get(server_name)

    def get_all_tools_for_llm(self) -> List[Dict]:
        """Get all tools from all servers formatted for LLM."""
        all_tools = []
        for server_name, client in self.clients.items():
            tools = client.get_tools_for_llm()
            all_tools.extend(tools)
        return all_tools

    async def call_tool(self, tool_name: str, arguments: Dict) -> Dict:
        """
        Call a tool by name.
        
        For unified server, tool_name is used directly.
        """
        # Use unified server
        client = self.get_client("unified_tools")
        if not client:
            return {
                "success": False,
                "error": "Unified tools server not found",
            }
        
        # Call the tool directly
        try:
            result = await client.call_tool(tool_name, arguments)
            return result
        except Exception as e:
            logger.error(f"Tool call failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    def get_server_health(self) -> Dict[str, bool]:
        """Check health of all servers."""
        health = {}
        for server_name, client in self.clients.items():
            # Simple check - is the process still running?
            is_healthy = (
                client.process is not None 
                and client.process.returncode is None
                and client.initialized
            )
            health[server_name] = is_healthy
        return health

    async def restart_server(self, server_name: str):
        """Restart a specific server."""
        logger.info(f"Restarting server: {server_name}")
        
        # Stop existing client
        if server_name in self.clients:
            await self.clients[server_name].stop()
            del self.clients[server_name]
        
        # Start new client
        if server_name in self.server_configs:
            command = self.server_configs[server_name]
            await self._start_server(server_name, command)
        else:
            raise ValueError(f"Unknown server: {server_name}")


# Global server manager instance
mcp_server_manager = MCPServerManager()


