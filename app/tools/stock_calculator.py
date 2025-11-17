"""Stock market parameter calculator with comprehensive technical indicators."""

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import ta

from app.tools.base import BaseTool
from app.utils.logger import logger


class StockCalculatorTool(BaseTool):
    """Tool for calculating comprehensive stock market technical indicators and features."""

    def __init__(self):
        super().__init__(
            name="stock_calculator",
            description="Calculate 30-40 stock market features including price-based, volume-based, momentum, volatility, and statistical indicators. Returns DataFrame with all computed features.",
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "data": {
                    "type": "object",
                    "description": "OHLCV data as dict with 'Date', 'Open', 'High', 'Low', 'Close', 'Volume' keys, or list of records",
                },
                "features": {
                    "type": "array",
                    "description": "List of feature categories to compute: 'price', 'volume', 'momentum', 'volatility', 'statistical', 'all' (default: 'all')",
                    "items": {"type": "string"},
                    "default": ["all"],
                },
            },
            "required": ["data"],
        }

    async def execute(
        self,
        data: Dict[str, Any],
        features: Optional[list] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Calculate stock market features."""
        try:
            if features is None:
                features = ["all"]

            # Convert data to DataFrame
            if isinstance(data, list):
                df = pd.DataFrame(data)
            elif isinstance(data, dict):
                if "Date" in data:
                    df = pd.DataFrame(data)
                else:
                    # Assume it's a dict with column names as keys
                    df = pd.DataFrame([data])
            else:
                return {
                    "success": False,
                    "error": "Invalid data format",
                    "result": None,
                }

            # Ensure Date is datetime
            if "Date" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"])
                df.set_index("Date", inplace=True)

            # Ensure required columns exist
            required_cols = ["Open", "High", "Low", "Close", "Volume"]
            for col in required_cols:
                if col not in df.columns:
                    return {
                        "success": False,
                        "error": f"Missing required column: {col}",
                        "result": None,
                    }

            result_df = df.copy()

            # Always create daily_return as it's needed by other features
            result_df["daily_return"] = df["Close"].pct_change()
            result_df["log_return"] = np.log(df["Close"] / df["Close"].shift(1))

            # Price-based features
            if "all" in features or "price" in features:
                result_df["price_change_pct"] = ((df["Close"] - df["Open"]) / df["Open"]) * 100
                result_df["range_ratio"] = (df["High"] - df["Low"]) / df["Close"]
                result_df["close_open_gap"] = (df["Open"] - df["Close"].shift(1)) / df["Close"].shift(1)

                # Moving averages
                for period in [5, 10, 20, 50, 200]:
                    result_df[f"sma_{period}"] = df["Close"].rolling(window=period).mean()
                    result_df[f"ema_{period}"] = df["Close"].ewm(span=period, adjust=False).mean()
                    result_df[f"price_ratio_sma_{period}"] = df["Close"] / result_df[f"sma_{period}"]

                # Bollinger Bands
                bb = ta.volatility.BollingerBands(df["Close"], window=20, window_dev=2)
                result_df["bb_upper"] = bb.bollinger_hband()
                result_df["bb_lower"] = bb.bollinger_lband()
                result_df["bb_middle"] = bb.bollinger_mavg()
                result_df["bb_percent"] = (df["Close"] - result_df["bb_lower"]) / (
                    result_df["bb_upper"] - result_df["bb_lower"]
                )
                result_df["bb_width"] = (result_df["bb_upper"] - result_df["bb_lower"]) / result_df["bb_middle"]

                # Volatility
                result_df["volatility_20d"] = result_df["log_return"].rolling(window=20).std()
                result_df["volatility_252d"] = result_df["log_return"].rolling(window=252).std() * np.sqrt(252)

            # Volume-based features
            if "all" in features or "volume" in features:
                result_df["volume_change_pct"] = df["Volume"].pct_change()
                result_df["volume_ma_20"] = df["Volume"].rolling(window=20).mean()
                result_df["volume_ratio"] = df["Volume"] / result_df["volume_ma_20"]

                # On-Balance Volume (OBV)
                result_df["obv"] = ta.volume.OnBalanceVolumeIndicator(
                    df["Close"], df["Volume"]
                ).on_balance_volume()

                # Money Flow Index
                result_df["mfi"] = ta.volume.MFIIndicator(
                    df["High"], df["Low"], df["Close"], df["Volume"]
                ).money_flow_index()

            # Momentum indicators
            if "all" in features or "momentum" in features:
                # RSI
                result_df["rsi_14"] = ta.momentum.RSIIndicator(df["Close"], window=14).rsi()
                result_df["rsi_7"] = ta.momentum.RSIIndicator(df["Close"], window=7).rsi()
                result_df["rsi_diff"] = result_df["rsi_7"] - result_df["rsi_14"]

                # MACD
                macd = ta.trend.MACD(df["Close"])
                result_df["macd"] = macd.macd()
                result_df["macd_signal"] = macd.macd_signal()
                result_df["macd_diff"] = macd.macd_diff()

                # Rate of Change
                result_df["roc_10"] = ta.momentum.ROCIndicator(df["Close"], window=10).roc()
                result_df["roc_20"] = ta.momentum.ROCIndicator(df["Close"], window=20).roc()

                # Stochastic
                stoch = ta.momentum.StochasticOscillator(
                    df["High"], df["Low"], df["Close"], window=14, smooth_window=3
                )
                result_df["stoch_k"] = stoch.stoch()
                result_df["stoch_d"] = stoch.stoch_signal()

                # Williams %R
                result_df["williams_r"] = ta.momentum.WilliamsRIndicator(
                    df["High"], df["Low"], df["Close"]
                ).williams_r()

                # Momentum Oscillator
                result_df["momentum_10"] = df["Close"] - df["Close"].shift(10)

            # Volatility indicators
            if "all" in features or "volatility" in features:
                # ATR
                result_df["atr_14"] = ta.volatility.AverageTrueRange(
                    df["High"], df["Low"], df["Close"], window=14
                ).average_true_range()

                # Donchian Channel
                result_df["donchian_high"] = df["High"].rolling(window=20).max()
                result_df["donchian_low"] = df["Low"].rolling(window=20).min()
                result_df["donchian_width"] = (
                    result_df["donchian_high"] - result_df["donchian_low"]
                ) / df["Close"]

                # Coefficient of Variation
                result_df["cv_20"] = (
                    df["Close"].rolling(window=20).std() / df["Close"].rolling(window=20).mean()
                )

            # Statistical features
            if "all" in features or "statistical" in features:
                for period in [5, 10, 20]:
                    result_df[f"mean_{period}d"] = df["Close"].rolling(window=period).mean()
                    result_df[f"std_{period}d"] = df["Close"].rolling(window=period).std()
                    result_df[f"skew_{period}d"] = df["Close"].rolling(window=period).skew()
                    # Calculate kurtosis manually since it's not available on Rolling object in all pandas versions
                    # Use apply with a lambda that handles the calculation
                    rolling_series = df["Close"].rolling(window=period)
                    result_df[f"kurtosis_{period}d"] = rolling_series.apply(
                        lambda x: np.nan if len(x) < period or x.std() == 0 else (((x - x.mean()) / x.std()) ** 4).mean() - 3,
                        raw=True
                    )

                # Z-score
                result_df["z_score_20"] = (df["Close"] - result_df["mean_20d"]) / result_df["std_20d"]

                # Sharpe Ratio
                result_df["sharpe_20"] = (
                    result_df["daily_return"].rolling(window=20).mean()
                    / result_df["daily_return"].rolling(window=20).std()
                    * np.sqrt(252)
                )

                # Drawdown
                result_df["cumulative_return"] = (1 + result_df["daily_return"]).cumprod()
                result_df["running_max"] = result_df["cumulative_return"].expanding().max()
                result_df["drawdown"] = (
                    result_df["cumulative_return"] - result_df["running_max"]
                ) / result_df["running_max"]

                # Autocorrelation
                result_df["autocorr_1"] = result_df["daily_return"].autocorr(lag=1)
                result_df["autocorr_5"] = result_df["daily_return"].autocorr(lag=5)

            # Lagged features
            for lag in [1, 2, 3, 5]:
                result_df[f"close_lag_{lag}"] = df["Close"].shift(lag)

            # Convert to dict for JSON serialization
            result_df = result_df.fillna(0)  # Replace NaN with 0
            
            # Reset index and convert Date to string for JSON serialization
            result_with_date = result_df.reset_index()
            if "Date" in result_with_date.columns:
                result_with_date["Date"] = result_with_date["Date"].astype(str)
            
            result_data = result_with_date.to_dict("records")

            return {
                "success": True,
                "result": {
                    "features": list(result_df.columns),
                    "data": result_data,
                    "shape": list(result_df.shape),
                    "feature_count": len(result_df.columns),
                },
            }

        except Exception as e:
            logger.error(f"Stock calculation failed: {e}")
            return {
                "success": False,
                "error": f"Calculation failed: {str(e)}",
                "result": None,
            }

