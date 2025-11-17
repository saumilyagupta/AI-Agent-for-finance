"""Tool registry for managing all available tools."""

from typing import Dict, Optional

from app.tools.api_client import APIClientTool
from app.tools.calculator import CalculatorTool
from app.tools.code_executor import CodeExecutorTool
from app.tools.file_ops import FileOpsTool
from app.tools.stock_analysis import StockAnalysisTool
from app.tools.stock_calculator import StockCalculatorTool
from app.tools.stock_market import StockMarketTool
from app.tools.visualizer import VisualizerTool
from app.tools.weather import WeatherTool
from app.tools.web_search import WebSearchTool
from app.tools.base import BaseTool
from app.utils.logger import logger


class ToolRegistry:
    """Registry for managing and discovering tools."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._initialize_tools()

    def _initialize_tools(self):
        """Initialize and register all tools."""
        tools = [
            WebSearchTool(),
            WeatherTool(),
            CalculatorTool(),
            APIClientTool(),
            FileOpsTool(),
            CodeExecutorTool(),
            StockAnalysisTool(),
            StockMarketTool(),
            StockCalculatorTool(),
            VisualizerTool(),
        ]

        for tool in tools:
            self.register_tool(tool)
            logger.info(f"Registered tool: {tool.name}")

    def register_tool(self, tool: BaseTool):
        """Register a tool."""
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list:
        """List all registered tools."""
        return list(self._tools.keys())

    def get_tool_info(self, name: str) -> Optional[dict]:
        """Get tool information including schema."""
        tool = self.get_tool(name)
        if not tool:
            return None

        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
            "stats": tool.get_stats(),
        }

    def get_all_tools_info(self) -> dict:
        """Get information for all tools."""
        return {name: self.get_tool_info(name) for name in self.list_tools()}


# Global registry instance
tool_registry = ToolRegistry()

