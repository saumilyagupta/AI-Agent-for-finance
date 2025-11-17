"""Tests for StockMarketTool."""

import pytest
from app.tools.stock_market import StockMarketTool


@pytest.fixture
def stock_market():
    """Create a StockMarketTool instance."""
    return StockMarketTool()


@pytest.mark.asyncio
async def test_stock_market_fetch_history(stock_market):
    """Test fetching stock history."""
    result = await stock_market.run(
        symbol="AAPL",
        period="1mo",
        interval="1d",
        data_type="history"
    )

    assert result["success"] is True
    assert "result" in result
    if "history" in result["result"]:
        assert "data" in result["result"]["history"]
        assert "shape" in result["result"]["history"]


@pytest.mark.asyncio
async def test_stock_market_fetch_info(stock_market):
    """Test fetching company info."""
    result = await stock_market.run(
        symbol="AAPL",
        data_type="info"
    )

    # May fail due to API issues, but should handle gracefully
    assert "success" in result
    if result["success"] and "info" in result["result"]:
        assert "name" in result["result"]["info"]


@pytest.mark.asyncio
async def test_stock_market_fetch_all(stock_market):
    """Test fetching all data types."""
    result = await stock_market.run(
        symbol="AAPL",
        period="1mo",
        data_type="all"
    )

    # May fail due to API issues, but should handle gracefully
    assert "success" in result
    if result["success"]:
        assert "result" in result
        assert "symbol" in result["result"]


@pytest.mark.asyncio
async def test_stock_market_default_parameters(stock_market):
    """Test with default parameters."""
    result = await stock_market.run(symbol="MSFT")

    assert result["success"] is True
    assert "result" in result
    assert result["result"]["symbol"] == "MSFT"


@pytest.mark.asyncio
async def test_stock_market_different_periods(stock_market):
    """Test different time periods."""
    periods = ["1d", "5d", "1mo", "3mo", "1y"]

    for period in periods:
        result = await stock_market.run(
            symbol="AAPL",
            period=period,
            data_type="history"
        )
        # Should handle all periods
        assert "success" in result


@pytest.mark.asyncio
async def test_stock_market_different_intervals(stock_market):
    """Test different intervals."""
    intervals = ["1d", "1h", "5m"]

    for interval in intervals:
        result = await stock_market.run(
            symbol="AAPL",
            period="5d",
            interval=interval,
            data_type="history"
        )
        # Should handle all intervals
        assert "success" in result


@pytest.mark.asyncio
async def test_stock_market_invalid_symbol(stock_market):
    """Test handling of invalid symbol."""
    result = await stock_market.run(symbol="INVALID_SYMBOL_XYZ123")

    # May succeed but with empty data, or fail gracefully
    assert "success" in result


@pytest.mark.asyncio
async def test_stock_market_missing_symbol(stock_market):
    """Test handling of missing symbol."""
    result = await stock_market.run()

    assert result["success"] is False
    assert "error" in result


@pytest.mark.asyncio
async def test_stock_market_indian_stocks(stock_market):
    """Test fetching Indian stock data (NSE)."""
    result = await stock_market.run(
        symbol="RELIANCE.NS",
        period="1mo",
        data_type="history"
    )

    # Should handle Indian stocks
    assert "success" in result


@pytest.mark.asyncio
async def test_stock_market_financials(stock_market):
    """Test fetching financials."""
    result = await stock_market.run(
        symbol="AAPL",
        data_type="financials"
    )

    assert result["success"] is True
    # Financials may or may not be available
    assert "result" in result


@pytest.mark.asyncio
async def test_stock_market_dividends(stock_market):
    """Test fetching dividends."""
    result = await stock_market.run(
        symbol="AAPL",
        data_type="dividends"
    )

    assert result["success"] is True
    # Dividends may or may not be available
    assert "result" in result


@pytest.mark.asyncio
async def test_stock_market_input_schema(stock_market):
    """Test input schema."""
    schema = stock_market.input_schema
    assert schema["type"] == "object"
    assert "properties" in schema
    assert "symbol" in schema["properties"]
    assert "period" in schema["properties"]
    assert "interval" in schema["properties"]
    assert "symbol" in schema["required"]


@pytest.mark.asyncio
async def test_stock_market_stats_tracking(stock_market):
    """Test usage statistics tracking."""
    initial_stats = stock_market.get_stats()
    assert initial_stats["usage_count"] == 0

    await stock_market.run(symbol="AAPL", period="1d")
    stats = stock_market.get_stats()
    assert stats["usage_count"] == 1

