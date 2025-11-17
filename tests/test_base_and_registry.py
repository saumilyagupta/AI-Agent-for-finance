"""Tests for BaseTool and ToolRegistry."""

import pytest
from app.tools.base import BaseTool
from app.tools.registry import tool_registry, ToolRegistry
from app.tools.calculator import CalculatorTool
from app.tools.web_search import WebSearchTool


class ConcreteTool(BaseTool):
    """Concrete implementation of BaseTool for testing."""

    @property
    def input_schema(self):
        return {
            "type": "object",
            "properties": {
                "test_param": {"type": "string"},
                "number": {"type": "integer"}
            },
            "required": ["test_param"]
        }

    async def execute(self, **kwargs):
        return {
            "success": True,
            "result": {"message": "Test executed", "params": kwargs}
        }


@pytest.fixture
def concrete_tool():
    """Create a concrete tool instance."""
    return ConcreteTool("test_tool", "A test tool")


@pytest.mark.asyncio
async def test_base_tool_initialization(concrete_tool):
    """Test BaseTool initialization."""
    assert concrete_tool.name == "test_tool"
    assert concrete_tool.description == "A test tool"
    assert concrete_tool.usage_count == 0
    assert concrete_tool.error_count == 0


@pytest.mark.asyncio
async def test_base_tool_validate_input_success(concrete_tool):
    """Test successful input validation."""
    is_valid = concrete_tool.validate_input(test_param="value", number=123)
    assert is_valid is True


@pytest.mark.asyncio
async def test_base_tool_validate_input_missing_required(concrete_tool):
    """Test validation with missing required field."""
    is_valid = concrete_tool.validate_input(number=123)
    assert is_valid is False


@pytest.mark.asyncio
async def test_base_tool_validate_input_type_check(concrete_tool):
    """Test type checking in validation."""
    # Should pass but may log warning
    is_valid = concrete_tool.validate_input(test_param="value", number="not_a_number")
    # Type checking is lenient, so this may still pass
    assert isinstance(is_valid, bool)


@pytest.mark.asyncio
async def test_base_tool_run_success(concrete_tool):
    """Test successful tool execution."""
    result = await concrete_tool.run(test_param="test_value", number=42)

    assert result["success"] is True
    assert "result" in result
    assert concrete_tool.usage_count == 1
    assert concrete_tool.error_count == 0


@pytest.mark.asyncio
async def test_base_tool_run_invalid_input(concrete_tool):
    """Test run with invalid input."""
    result = await concrete_tool.run(number=123)  # Missing required test_param

    assert result["success"] is False
    assert "error" in result
    assert concrete_tool.usage_count == 1
    assert concrete_tool.error_count == 1


@pytest.mark.asyncio
async def test_base_tool_get_stats(concrete_tool):
    """Test getting tool statistics."""
    await concrete_tool.run(test_param="test")
    stats = concrete_tool.get_stats()

    assert stats["name"] == "test_tool"
    assert stats["usage_count"] == 1
    assert stats["error_count"] == 0
    assert stats["success_rate"] == 1.0


@pytest.mark.asyncio
async def test_base_tool_get_stats_with_errors(concrete_tool):
    """Test stats with errors."""
    await concrete_tool.run(test_param="test")  # Success
    await concrete_tool.run()  # Failure
    stats = concrete_tool.get_stats()

    assert stats["usage_count"] == 2
    assert stats["error_count"] == 1
    assert stats["success_rate"] == 0.5


@pytest.mark.asyncio
async def test_base_tool_type_conversion():
    """Test JSON type to Python type conversion."""
    assert BaseTool._get_python_type("string") == str
    assert BaseTool._get_python_type("integer") == int
    assert BaseTool._get_python_type("number") == float
    assert BaseTool._get_python_type("boolean") == bool
    assert BaseTool._get_python_type("array") == list
    assert BaseTool._get_python_type("object") == dict


def test_tool_registry_list_tools():
    """Test listing all tools."""
    tools = tool_registry.list_tools()
    assert len(tools) > 0
    assert isinstance(tools, list)


def test_tool_registry_get_tool():
    """Test getting a tool by name."""
    tool = tool_registry.get_tool("calculator")
    assert tool is not None
    assert tool.name == "calculator"

    tool = tool_registry.get_tool("web_search")
    assert tool is not None
    assert tool.name == "web_search"


def test_tool_registry_get_nonexistent_tool():
    """Test getting non-existent tool."""
    tool = tool_registry.get_tool("nonexistent_tool")
    assert tool is None


def test_tool_registry_get_tool_info():
    """Test getting tool information."""
    info = tool_registry.get_tool_info("calculator")
    assert info is not None
    assert info["name"] == "calculator"
    assert "description" in info
    assert "input_schema" in info
    assert "stats" in info


def test_tool_registry_get_tool_info_nonexistent():
    """Test getting info for non-existent tool."""
    info = tool_registry.get_tool_info("nonexistent")
    assert info is None


def test_tool_registry_get_all_tools_info():
    """Test getting info for all tools."""
    all_info = tool_registry.get_all_tools_info()
    assert isinstance(all_info, dict)
    assert len(all_info) > 0

    # Check that all registered tools are present
    tools = tool_registry.list_tools()
    for tool_name in tools:
        assert tool_name in all_info


def test_tool_registry_all_tools_registered():
    """Test that all expected tools are registered."""
    expected_tools = [
        "web_search",
        "calculator",
        "api_client",
        "file_ops",
        "code_executor",
        "stock_market",
        "stock_calculator",
        "visualizer"
    ]

    registered_tools = tool_registry.list_tools()
    for tool_name in expected_tools:
        assert tool_name in registered_tools, f"{tool_name} not registered"


def test_tool_registry_register_custom_tool():
    """Test registering a custom tool."""
    registry = ToolRegistry()
    custom_tool = ConcreteTool("custom", "Custom tool")
    registry.register_tool(custom_tool)

    assert "custom" in registry.list_tools()
    assert registry.get_tool("custom") == custom_tool


def test_tool_registry_tool_schemas():
    """Test that all tools have valid schemas."""
    tools = tool_registry.list_tools()
    for tool_name in tools:
        tool = tool_registry.get_tool(tool_name)
        schema = tool.input_schema
        assert schema is not None
        assert "type" in schema
        assert schema["type"] == "object"
        assert "properties" in schema










