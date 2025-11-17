"""Tests for CalculatorTool."""

import pytest
from app.tools.calculator import CalculatorTool


@pytest.fixture
def calculator():
    """Create a CalculatorTool instance."""
    return CalculatorTool()


@pytest.mark.asyncio
async def test_calculator_basic_arithmetic(calculator):
    """Test basic arithmetic operations."""
    # Addition
    result = await calculator.run(expression="2 + 3")
    assert result["success"] is True
    assert result["result"]["result"] == 5.0

    # Subtraction
    result = await calculator.run(expression="10 - 4")
    assert result["success"] is True
    assert result["result"]["result"] == 6.0

    # Multiplication
    result = await calculator.run(expression="3 * 4")
    assert result["success"] is True
    assert result["result"]["result"] == 12.0

    # Division
    result = await calculator.run(expression="15 / 3")
    assert result["success"] is True
    assert result["result"]["result"] == 5.0

    # Power
    result = await calculator.run(expression="2 ** 3")
    assert result["success"] is True
    assert result["result"]["result"] == 8.0


@pytest.mark.asyncio
async def test_calculator_complex_expressions(calculator):
    """Test complex mathematical expressions."""
    # Complex expression
    result = await calculator.run(expression="(2 + 3) * 4 - 1")
    assert result["success"] is True
    assert result["result"]["result"] == 19.0

    # With math functions
    result = await calculator.run(expression="math.sqrt(16)")
    assert result["success"] is True
    assert result["result"]["result"] == 4.0

    # Trigonometric
    result = await calculator.run(expression="math.sin(math.pi / 2)")
    assert result["success"] is True
    assert abs(result["result"]["result"] - 1.0) < 0.001


@pytest.mark.asyncio
async def test_calculator_statistics_all(calculator):
    """Test statistics operation with all stats."""
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    result = await calculator.run(operation="statistics", data=data)

    assert result["success"] is True
    assert "mean" in result["result"]
    assert "median" in result["result"]
    assert "std" in result["result"]
    assert "var" in result["result"]
    assert "min" in result["result"]
    assert "max" in result["result"]
    assert "sum" in result["result"]
    assert result["result"]["mean"] == 5.5
    assert result["result"]["min"] == 1.0
    assert result["result"]["max"] == 10.0
    assert result["result"]["sum"] == 55.0


@pytest.mark.asyncio
async def test_calculator_statistics_single(calculator):
    """Test statistics operation with single stat."""
    data = [10, 20, 30, 40, 50]

    # Test mean
    result = await calculator.run(operation="statistics", data=data, stat_op="mean")
    assert result["success"] is True
    assert result["result"]["value"] == 30.0

    # Test median
    result = await calculator.run(operation="statistics", data=data, stat_op="median")
    assert result["success"] is True
    assert result["result"]["value"] == 30.0

    # Test std
    result = await calculator.run(operation="statistics", data=data, stat_op="std")
    assert result["success"] is True
    assert result["result"]["value"] > 0

    # Test min
    result = await calculator.run(operation="statistics", data=data, stat_op="min")
    assert result["success"] is True
    assert result["result"]["value"] == 10.0

    # Test max
    result = await calculator.run(operation="statistics", data=data, stat_op="max")
    assert result["success"] is True
    assert result["result"]["value"] == 50.0

    # Test sum
    result = await calculator.run(operation="statistics", data=data, stat_op="sum")
    assert result["success"] is True
    assert result["result"]["value"] == 150.0


@pytest.mark.asyncio
async def test_calculator_auto_detect_operation(calculator):
    """Test auto-detection of operation type."""
    # Should auto-detect as evaluate
    result = await calculator.run(expression="5 + 5")
    assert result["success"] is True
    assert result["result"]["result"] == 10.0

    # Should auto-detect as statistics
    result = await calculator.run(data=[1, 2, 3])
    assert result["success"] is True
    assert "mean" in result["result"]


@pytest.mark.asyncio
async def test_calculator_invalid_expression(calculator):
    """Test handling of invalid expressions."""
    result = await calculator.run(expression="invalid expression !@#")
    # Should handle gracefully
    assert "success" in result


@pytest.mark.asyncio
async def test_calculator_missing_parameters(calculator):
    """Test handling of missing parameters."""
    result = await calculator.run()
    assert result["success"] is False
    assert "error" in result


@pytest.mark.asyncio
async def test_calculator_invalid_stat_op(calculator):
    """Test handling of invalid statistical operation."""
    result = await calculator.run(operation="statistics", data=[1, 2, 3], stat_op="invalid")
    assert result["success"] is False
    assert "error" in result


@pytest.mark.asyncio
async def test_calculator_empty_data(calculator):
    """Test handling of empty data."""
    result = await calculator.run(operation="statistics", data=[])
    # Should handle empty data gracefully
    assert "success" in result


@pytest.mark.asyncio
async def test_calculator_input_schema(calculator):
    """Test input schema."""
    schema = calculator.input_schema
    assert schema["type"] == "object"
    assert "properties" in schema
    assert "operation" in schema["properties"]
    assert "expression" in schema["properties"]
    assert "data" in schema["properties"]


@pytest.mark.asyncio
async def test_calculator_stats_tracking(calculator):
    """Test usage statistics tracking."""
    initial_stats = calculator.get_stats()
    assert initial_stats["usage_count"] == 0

    await calculator.run(expression="1 + 1")
    stats = calculator.get_stats()
    assert stats["usage_count"] == 1
    assert stats["success_rate"] == 1.0









