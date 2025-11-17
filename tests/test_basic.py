"""Basic integration tests for the autonomous agent system.

This file contains high-level integration tests. For detailed tool tests,
see the individual test files:
- test_calculator.py
- test_code_executor.py
- test_api_client.py
- test_file_ops.py
- test_stock_calculator.py
- test_stock_market.py
- test_visualizer.py
- test_web_search.py
- test_base_and_registry.py
"""

import pytest
from app.tools.registry import tool_registry
from app.utils.config import settings


def test_tool_registry():
    """Test that tools are registered."""
    tools = tool_registry.list_tools()
    assert len(tools) > 0
    assert "web_search" in tools
    assert "calculator" in tools


def test_tool_info():
    """Test tool info retrieval."""
    info = tool_registry.get_tool_info("web_search")
    assert info is not None
    assert info["name"] == "web_search"
    assert "input_schema" in info


def test_config():
    """Test configuration loading."""
    assert settings is not None
    assert hasattr(settings, "log_level")


@pytest.mark.asyncio
async def test_web_search_tool():
    """Test web search tool."""
    tool = tool_registry.get_tool("web_search")
    assert tool is not None
    
    result = await tool.run(query="Python programming", max_results=3)
    assert result is not None
    assert "success" in result

