"""Stock market data fetcher using yfinance."""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import yfinance as yf

from app.tools.base import BaseTool
from app.utils.logger import logger


class StockMarketTool(BaseTool):
    """Tool for fetching stock market data using yfinance."""

    def __init__(self):
        super().__init__(
            name="stock_market",
            description="Fetch stock market data including historical OHLCV, company info, financials, dividends, and splits. Supports both Indian (NSE/BSE) and international stocks.",
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock symbol (e.g., 'AAPL', 'MSFT', 'RELIANCE.NS' for NSE, 'RELIANCE.BO' for BSE)",
                },
                "period": {
                    "type": "string",
                    "description": "Data period: '1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max' (default: '1y')",
                    "default": "1y",
                },
                "interval": {
                    "type": "string",
                    "description": "Data interval: '1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '1d', '5d', '1wk', '1mo', '3mo' (default: '1d')",
                    "default": "1d",
                },
                "data_type": {
                    "type": "string",
                    "description": "Type of data to fetch: 'history' (OHLCV), 'info' (company info), 'financials', 'dividends', 'splits', 'all' (default: 'history')",
                    "enum": ["history", "info", "financials", "dividends", "splits", "all"],
                    "default": "history",
                },
            },
            "required": ["symbol"],
        }

    async def execute(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
        data_type: str = "history",
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute stock data fetch."""
        try:
            logger.info(f"Fetching stock data for {symbol}")

            ticker = yf.Ticker(symbol)

            result = {"symbol": symbol}

            if data_type in ["history", "all"]:
                try:
                    hist = ticker.history(period=period, interval=interval)
                    if not hist.empty:
                        # Convert index to string safely
                        start_date = hist.index[0]
                        end_date = hist.index[-1]
                        if hasattr(start_date, 'strftime'):
                            start_str = start_date.strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            start_str = str(start_date)
                        if hasattr(end_date, 'strftime'):
                            end_str = end_date.strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            end_str = str(end_date)
                        
                        result["history"] = {
                            "data": hist.reset_index().to_dict("records"),
                            "columns": list(hist.columns),
                            "shape": list(hist.shape),
                            "date_range": {
                                "start": start_str,
                                "end": end_str,
                            },
                        }
                except Exception as e:
                    logger.warning(f"Could not fetch history: {e}")

            if data_type in ["info", "all"]:
                try:
                    info = ticker.info
                    if info:
                        # Extract key info
                        result["info"] = {
                            "name": info.get("longName", info.get("shortName", "")),
                            "sector": info.get("sector", ""),
                            "industry": info.get("industry", ""),
                            "market_cap": info.get("marketCap"),
                            "current_price": info.get("currentPrice"),
                            "currency": info.get("currency", ""),
                            "exchange": info.get("exchange", ""),
                        }
                except Exception as e:
                    logger.warning(f"Could not fetch info: {e}")

            if data_type in ["financials", "all"]:
                try:
                    financials = ticker.financials
                    if not financials.empty:
                        result["financials"] = financials.to_dict()
                except Exception as e:
                    logger.warning(f"Could not fetch financials: {e}")

            if data_type in ["dividends", "all"]:
                try:
                    dividends = ticker.dividends
                    if not dividends.empty:
                        result["dividends"] = dividends.to_dict()
                except Exception as e:
                    logger.warning(f"Could not fetch dividends: {e}")

            if data_type in ["splits", "all"]:
                try:
                    splits = ticker.splits
                    if not splits.empty:
                        result["splits"] = splits.to_dict()
                except Exception as e:
                    logger.warning(f"Could not fetch splits: {e}")

            return {
                "success": True,
                "result": result,
            }

        except Exception as e:
            logger.error(f"Stock data fetch failed: {e}")
            return {
                "success": False,
                "error": f"Failed to fetch stock data: {str(e)}",
                "result": None,
            }

