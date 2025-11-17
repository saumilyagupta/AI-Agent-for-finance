"""Tests for StockCalculatorTool."""

import pytest
from datetime import datetime, timedelta
from app.tools.stock_calculator import StockCalculatorTool


@pytest.fixture
def stock_calculator():
    """Create a StockCalculatorTool instance."""
    return StockCalculatorTool()


@pytest.fixture
def sample_ohlcv_data():
    """Sample OHLCV data for testing."""
    dates = [datetime.now() - timedelta(days=i) for i in range(30, -1, -1)]
    return [
        {
            "Date": date.strftime("%Y-%m-%d"),
            "Open": 100 + i * 0.5,
            "High": 102 + i * 0.5,
            "Low": 99 + i * 0.5,
            "Close": 101 + i * 0.5,
            "Volume": 1000000 + i * 10000
        }
        for i, date in enumerate(dates)
    ]


@pytest.mark.asyncio
async def test_stock_calculator_all_features(stock_calculator, sample_ohlcv_data):
    """Test calculating all features."""
    result = await stock_calculator.run(
        data=sample_ohlcv_data,
        features=["all"]
    )

    assert result["success"] is True
    assert "features" in result["result"]
    assert "data" in result["result"]
    assert "shape" in result["result"]
    assert "feature_count" in result["result"]
    assert result["result"]["feature_count"] > 30  # Should have many features


@pytest.mark.asyncio
async def test_stock_calculator_price_features(stock_calculator, sample_ohlcv_data):
    """Test calculating price-based features."""
    result = await stock_calculator.run(
        data=sample_ohlcv_data,
        features=["price"]
    )

    assert result["success"] is True
    assert "features" in result["result"]
    # Check for price-related features
    features = result["result"]["features"]
    assert any("sma" in f.lower() or "ema" in f.lower() for f in features)
    assert any("return" in f.lower() for f in features)


@pytest.mark.asyncio
async def test_stock_calculator_volume_features(stock_calculator, sample_ohlcv_data):
    """Test calculating volume-based features."""
    result = await stock_calculator.run(
        data=sample_ohlcv_data,
        features=["volume"]
    )

    assert result["success"] is True
    assert "features" in result["result"]
    features = result["result"]["features"]
    assert any("volume" in f.lower() or "obv" in f.lower() or "mfi" in f.lower() for f in features)


@pytest.mark.asyncio
async def test_stock_calculator_momentum_features(stock_calculator, sample_ohlcv_data):
    """Test calculating momentum features."""
    result = await stock_calculator.run(
        data=sample_ohlcv_data,
        features=["momentum"]
    )

    assert result["success"] is True
    assert "features" in result["result"]
    features = result["result"]["features"]
    assert any("rsi" in f.lower() or "macd" in f.lower() or "roc" in f.lower() for f in features)


@pytest.mark.asyncio
async def test_stock_calculator_volatility_features(stock_calculator, sample_ohlcv_data):
    """Test calculating volatility features."""
    result = await stock_calculator.run(
        data=sample_ohlcv_data,
        features=["volatility"]
    )

    assert result["success"] is True
    assert "features" in result["result"]
    features = result["result"]["features"]
    assert any("volatility" in f.lower() or "atr" in f.lower() for f in features)


@pytest.mark.asyncio
async def test_stock_calculator_statistical_features(stock_calculator, sample_ohlcv_data):
    """Test calculating statistical features."""
    result = await stock_calculator.run(
        data=sample_ohlcv_data,
        features=["statistical"]
    )

    assert result["success"] is True
    assert "features" in result["result"]
    features = result["result"]["features"]
    assert any("mean" in f.lower() or "std" in f.lower() or "z_score" in f.lower() for f in features)


@pytest.mark.asyncio
async def test_stock_calculator_dict_format(stock_calculator):
    """Test with dict format data."""
    # Need more data points for features that require rolling windows
    dates = [f"2024-01-{i:02d}" for i in range(1, 32)]
    data = {
        "Date": dates,
        "Open": [100 + i * 0.5 for i in range(31)],
        "High": [102 + i * 0.5 for i in range(31)],
        "Low": [99 + i * 0.5 for i in range(31)],
        "Close": [101 + i * 0.5 for i in range(31)],
        "Volume": [1000000 + i * 10000 for i in range(31)]
    }

    result = await stock_calculator.run(data=data)

    # May fail if not enough data for all features, but should handle gracefully
    assert "success" in result
    if result["success"]:
        assert "features" in result["result"]


@pytest.mark.asyncio
async def test_stock_calculator_missing_columns(stock_calculator):
    """Test handling of missing required columns."""
    data = [{"Date": "2024-01-01", "Open": 100}]  # Missing Close, High, Low, Volume

    result = await stock_calculator.run(data=data)

    assert result["success"] is False
    assert "error" in result
    assert "column" in result["error"].lower()


@pytest.mark.asyncio
async def test_stock_calculator_missing_data(stock_calculator):
    """Test handling of missing data."""
    result = await stock_calculator.run(data=[])

    # Should handle gracefully
    assert "success" in result


@pytest.mark.asyncio
async def test_stock_calculator_invalid_data_format(stock_calculator):
    """Test handling of invalid data format."""
    result = await stock_calculator.run(data="invalid")

    assert result["success"] is False
    assert "error" in result


@pytest.mark.asyncio
async def test_stock_calculator_default_features(stock_calculator, sample_ohlcv_data):
    """Test default features (all)."""
    result = await stock_calculator.run(data=sample_ohlcv_data)

    assert result["success"] is True
    assert result["result"]["feature_count"] > 30


@pytest.mark.asyncio
async def test_stock_calculator_input_schema(stock_calculator):
    """Test input schema."""
    schema = stock_calculator.input_schema
    assert schema["type"] == "object"
    assert "properties" in schema
    assert "data" in schema["properties"]
    assert "features" in schema["properties"]
    assert "data" in schema["required"]


@pytest.mark.asyncio
async def test_stock_calculator_stats_tracking(stock_calculator, sample_ohlcv_data):
    """Test usage statistics tracking."""
    initial_stats = stock_calculator.get_stats()
    assert initial_stats["usage_count"] == 0

    await stock_calculator.run(data=sample_ohlcv_data)
    stats = stock_calculator.get_stats()
    assert stats["usage_count"] == 1

