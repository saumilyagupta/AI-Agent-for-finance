"""Tests for VisualizerTool."""

import pytest
from app.tools.visualizer import VisualizerTool


@pytest.fixture
def visualizer():
    """Create a VisualizerTool instance."""
    return VisualizerTool()


@pytest.fixture
def sample_data():
    """Sample data for visualization."""
    return {
        "x": [1, 2, 3, 4, 5],
        "y": [10, 20, 30, 40, 50]
    }


@pytest.fixture
def sample_list_data():
    """Sample list data for visualization."""
    return [
        {"x": 1, "y": 10},
        {"x": 2, "y": 20},
        {"x": 3, "y": 30},
        {"x": 4, "y": 40},
        {"x": 5, "y": 50}
    ]


@pytest.fixture
def sample_ohlc_data():
    """Sample OHLC data for candlestick."""
    return [
        {"Date": "2024-01-01", "Open": 100, "High": 105, "Low": 98, "Close": 103},
        {"Date": "2024-01-02", "Open": 103, "High": 108, "Low": 101, "Close": 106},
        {"Date": "2024-01-03", "Open": 106, "High": 110, "Low": 104, "Close": 109}
    ]


@pytest.mark.asyncio
async def test_visualizer_line_chart(visualizer, sample_data):
    """Test creating line chart."""
    result = await visualizer.run(
        chart_type="line",
        data=sample_data,
        title="Test Line Chart",
        x_label="X Axis",
        y_label="Y Axis"
    )

    assert result["success"] is True
    assert result["result"]["format"] == "json"
    assert "figure" in result["result"]


@pytest.mark.asyncio
async def test_visualizer_bar_chart(visualizer, sample_data):
    """Test creating bar chart."""
    result = await visualizer.run(
        chart_type="bar",
        data=sample_data,
        title="Test Bar Chart"
    )

    assert result["success"] is True
    assert result["result"]["format"] == "json"
    assert "figure" in result["result"]


@pytest.mark.asyncio
async def test_visualizer_scatter_chart(visualizer, sample_data):
    """Test creating scatter chart."""
    result = await visualizer.run(
        chart_type="scatter",
        data=sample_data
    )

    assert result["success"] is True
    assert result["result"]["format"] == "json"


@pytest.mark.asyncio
async def test_visualizer_candlestick_chart(visualizer, sample_ohlc_data):
    """Test creating candlestick chart."""
    result = await visualizer.run(
        chart_type="candlestick",
        data=sample_ohlc_data,
        title="Stock Price Chart"
    )

    assert result["success"] is True
    assert result["result"]["format"] == "json"


@pytest.mark.asyncio
async def test_visualizer_pie_chart(visualizer, sample_data):
    """Test creating pie chart."""
    result = await visualizer.run(
        chart_type="pie",
        data=sample_data
    )

    assert result["success"] is True
    assert result["result"]["format"] == "json"


@pytest.mark.asyncio
async def test_visualizer_html_output(visualizer, sample_data):
    """Test HTML output format."""
    result = await visualizer.run(
        chart_type="line",
        data=sample_data,
        output_format="html"
    )

    assert result["success"] is True
    assert result["result"]["format"] == "html"
    assert "html" in result["result"]


@pytest.mark.asyncio
async def test_visualizer_list_data(visualizer, sample_list_data):
    """Test with list data format."""
    result = await visualizer.run(
        chart_type="line",
        data=sample_list_data
    )

    assert result["success"] is True
    assert result["result"]["format"] == "json"


@pytest.mark.asyncio
async def test_visualizer_missing_data(visualizer):
    """Test handling of missing data."""
    result = await visualizer.run(
        chart_type="line",
        data={}
    )

    assert result["success"] is False
    assert "error" in result


@pytest.mark.asyncio
async def test_visualizer_empty_data(visualizer):
    """Test handling of empty data."""
    result = await visualizer.run(
        chart_type="line",
        data={"x": [], "y": []}
    )

    assert result["success"] is False
    assert "error" in result


@pytest.mark.asyncio
async def test_visualizer_invalid_chart_type(visualizer, sample_data):
    """Test handling of invalid chart type."""
    result = await visualizer.run(
        chart_type="invalid",
        data=sample_data
    )

    # Should handle gracefully
    assert "success" in result


@pytest.mark.asyncio
async def test_visualizer_missing_parameters(visualizer):
    """Test handling of missing parameters."""
    result = await visualizer.run(chart_type="line")

    assert result["success"] is False
    assert "error" in result


@pytest.mark.asyncio
async def test_visualizer_default_title(visualizer, sample_data):
    """Test default title generation."""
    result = await visualizer.run(
        chart_type="line",
        data=sample_data
    )

    assert result["success"] is True
    # Should have a default title
    assert "figure" in result["result"]


@pytest.mark.asyncio
async def test_visualizer_input_schema(visualizer):
    """Test input schema."""
    schema = visualizer.input_schema
    assert schema["type"] == "object"
    assert "properties" in schema
    assert "chart_type" in schema["properties"]
    assert "data" in schema["properties"]
    assert "chart_type" in schema["required"]


@pytest.mark.asyncio
async def test_visualizer_stats_tracking(visualizer, sample_data):
    """Test usage statistics tracking."""
    initial_stats = visualizer.get_stats()
    assert initial_stats["usage_count"] == 0

    await visualizer.run(chart_type="line", data=sample_data)
    stats = visualizer.get_stats()
    assert stats["usage_count"] == 1











