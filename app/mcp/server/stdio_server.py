"""STDIO transport for MCP servers."""

import asyncio
import json
import sys
import logging
from typing import Optional

from app.mcp.server.base import MCPServerBase

# Configure logger to use stderr only for MCP STDIO servers
logger = logging.getLogger("mcp_stdio")
logger.setLevel(logging.INFO)
stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(stderr_handler)
logger.propagate = False


class StdioMCPServer:
    """MCP server using STDIO transport."""

    def __init__(self, server: MCPServerBase):
        self.server = server
        self.running = False

    async def start(self):
        """Start the STDIO server."""
        self.running = True
        logger.info(f"Starting MCP STDIO server: {self.server.name}")

        try:
            # Read from stdin, write to stdout
            while self.running:
                line = await self._read_line()
                if not line:
                    break

                try:
                    request = json.loads(line)
                    response = await self.server.handle_request(request)
                    await self._write_response(response)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {e}")
                    error_response = {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {
                            "code": -32700,
                            "message": "Parse error",
                        },
                    }
                    await self._write_response(error_response)
                except Exception as e:
                    logger.error(f"Error processing request: {e}")

        except Exception as e:
            logger.error(f"STDIO server error: {e}")
        finally:
            logger.info(f"MCP STDIO server stopped: {self.server.name}")

    async def _read_line(self) -> Optional[str]:
        """Read a line from stdin asynchronously."""
        loop = asyncio.get_event_loop()
        try:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            return line.strip() if line else None
        except Exception as e:
            logger.error(f"Error reading from stdin: {e}")
            return None

    async def _write_response(self, response: dict):
        """Write a response to stdout."""
        try:
            json_str = json.dumps(response)
            sys.stdout.write(json_str + "\n")
            sys.stdout.flush()
        except Exception as e:
            logger.error(f"Error writing to stdout: {e}")

    def stop(self):
        """Stop the server."""
        self.running = False


