"""Unified stock analysis tool with technical indicators and trend prediction."""

from datetime import datetime
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import ta
import yfinance as yf

from app.tools.base import BaseTool
from app.utils.logger import logger


class StockAnalysisTool(BaseTool):
    """Comprehensive stock analysis tool that fetches data and computes technical indicators."""

    def __init__(self):
        super().__init__(
            name="stock_analysis",
            description="Analyze a stock with technical indicators (RSI, MACD, Bollinger Bands, etc.) and predict trend direction. Fetches data and computes all indicators in one call.",
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock symbol (e.g., 'TSLA', 'AAPL', 'RELIANCE.NS')",
                },
                "period": {
                    "type": "string",
                    "description": "Data period: '1mo', '3mo', '6mo', '1y', '2y' (default: '3mo')",
                    "default": "3mo",
                },
                "include_prediction": {
                    "type": "boolean",
                    "description": "Whether to include trend prediction based on indicators (default: true)",
                    "default": True,
                },
            },
            "required": ["symbol"],
        }

    async def execute(
        self,
        symbol: str,
        period: str = "3mo",
        include_prediction: bool = True,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute comprehensive stock analysis."""
        try:
            logger.info(f"Analyzing stock {symbol} with period {period}")

            # Fetch stock data with retry logic
            import time
            max_retries = 3
            hist = None
            
            for attempt in range(max_retries):
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period=period)
                    
                    if not hist.empty:
                        logger.info(f"Fetched {len(hist)} data points for {symbol}")
                        break
                    else:
                        logger.warning(f"Attempt {attempt + 1}/{max_retries}: No data returned for {symbol}")
                        if attempt < max_retries - 1:
                            wait_time = 2 * (attempt + 1)  # 2s, 4s, 6s
                            logger.info(f"Waiting {wait_time}s before retry...")
                            time.sleep(wait_time)
                        
                except Exception as fetch_error:
                    logger.error(f"Attempt {attempt + 1}/{max_retries}: Failed to fetch data for {symbol}: {fetch_error}")
                    if attempt < max_retries - 1:
                        wait_time = 2 * (attempt + 1)
                        logger.info(f"Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                    else:
                        return {
                            "success": False,
                            "error": f"Failed to fetch stock data after {max_retries} attempts: {str(fetch_error)}. This might be due to: 1) Network issues, 2) Yahoo Finance API problems, 3) Invalid symbol.",
                            "result": None,
                        }

            if hist is None or hist.empty:
                logger.error(f"Failed to fetch data for {symbol} after {max_retries} attempts")
                return {
                    "success": False,
                    "error": f"No data found for symbol {symbol} after {max_retries} retries. This could mean: 1) Yahoo Finance API is temporarily unavailable, 2) Symbol is invalid or delisted, 3) Network connectivity issues. The symbol '{symbol}' appears valid, so this is likely a temporary API issue. Please try again in a few moments.",
                    "result": None,
                }

            # Get company info
            try:
                info = ticker.info
                company_name = info.get("longName", info.get("shortName", symbol))
                current_price = info.get("currentPrice", hist["Close"].iloc[-1])
                market_cap = info.get("marketCap")
            except:
                company_name = symbol
                current_price = hist["Close"].iloc[-1]
                market_cap = None

            # Calculate technical indicators
            df = hist.copy()
            
            # Basic price info
            latest_close = df["Close"].iloc[-1]
            prev_close = df["Close"].iloc[-2]
            price_change = latest_close - prev_close
            price_change_pct = (price_change / prev_close) * 100

            # Moving Averages
            df["SMA_20"] = df["Close"].rolling(window=20).mean()
            df["SMA_50"] = df["Close"].rolling(window=50).mean()
            df["EMA_12"] = df["Close"].ewm(span=12, adjust=False).mean()
            df["EMA_26"] = df["Close"].ewm(span=26, adjust=False).mean()

            # RSI
            rsi_indicator = ta.momentum.RSIIndicator(df["Close"], window=14)
            df["RSI"] = rsi_indicator.rsi()
            current_rsi = df["RSI"].iloc[-1]

            # MACD
            macd = ta.trend.MACD(df["Close"])
            df["MACD"] = macd.macd()
            df["MACD_Signal"] = macd.macd_signal()
            df["MACD_Diff"] = macd.macd_diff()
            current_macd = df["MACD"].iloc[-1]
            current_macd_signal = df["MACD_Signal"].iloc[-1]
            current_macd_diff = df["MACD_Diff"].iloc[-1]

            # Bollinger Bands
            bb = ta.volatility.BollingerBands(df["Close"], window=20, window_dev=2)
            df["BB_Upper"] = bb.bollinger_hband()
            df["BB_Middle"] = bb.bollinger_mavg()
            df["BB_Lower"] = bb.bollinger_lband()
            current_bb_upper = df["BB_Upper"].iloc[-1]
            current_bb_lower = df["BB_Lower"].iloc[-1]
            current_bb_middle = df["BB_Middle"].iloc[-1]

            # ATR (Average True Range)
            atr = ta.volatility.AverageTrueRange(df["High"], df["Low"], df["Close"], window=14)
            df["ATR"] = atr.average_true_range()
            current_atr = df["ATR"].iloc[-1]

            # Stochastic Oscillator
            stoch = ta.momentum.StochasticOscillator(df["High"], df["Low"], df["Close"], window=14, smooth_window=3)
            df["Stoch_K"] = stoch.stoch()
            df["Stoch_D"] = stoch.stoch_signal()
            current_stoch_k = df["Stoch_K"].iloc[-1]
            current_stoch_d = df["Stoch_D"].iloc[-1]

            # Volume indicators
            df["Volume_MA_20"] = df["Volume"].rolling(window=20).mean()
            volume_ratio = df["Volume"].iloc[-1] / df["Volume_MA_20"].iloc[-1] if df["Volume_MA_20"].iloc[-1] > 0 else 0

            # OBV (On-Balance Volume)
            obv = ta.volume.OnBalanceVolumeIndicator(df["Close"], df["Volume"])
            df["OBV"] = obv.on_balance_volume()

            # Compile current indicators
            current_indicators = {
                "price": round(float(latest_close), 2),
                "price_change": round(float(price_change), 2),
                "price_change_pct": round(float(price_change_pct), 2),
                "sma_20": round(float(df["SMA_20"].iloc[-1]), 2) if not np.isnan(df["SMA_20"].iloc[-1]) else None,
                "sma_50": round(float(df["SMA_50"].iloc[-1]), 2) if not np.isnan(df["SMA_50"].iloc[-1]) else None,
                "ema_12": round(float(df["EMA_12"].iloc[-1]), 2),
                "ema_26": round(float(df["EMA_26"].iloc[-1]), 2),
                "rsi_14": round(float(current_rsi), 2),
                "macd": round(float(current_macd), 4),
                "macd_signal": round(float(current_macd_signal), 4),
                "macd_diff": round(float(current_macd_diff), 4),
                "bb_upper": round(float(current_bb_upper), 2),
                "bb_middle": round(float(current_bb_middle), 2),
                "bb_lower": round(float(current_bb_lower), 2),
                "atr_14": round(float(current_atr), 2),
                "stoch_k": round(float(current_stoch_k), 2),
                "stoch_d": round(float(current_stoch_d), 2),
                "volume_ratio": round(float(volume_ratio), 2),
            }

            # Trend prediction
            prediction = None
            if include_prediction:
                prediction = self._predict_trend(df, current_indicators)

            # Create summary
            summary = self._create_summary(
                symbol, company_name, current_indicators, prediction
            )

            return {
                "success": True,
                "result": {
                    "symbol": symbol,
                    "company_name": company_name,
                    "market_cap": market_cap,
                    "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "data_period": period,
                    "data_points": len(df),
                    "current_indicators": current_indicators,
                    "prediction": prediction,
                    "summary": summary,
                },
            }

        except Exception as e:
            logger.error(f"Stock analysis failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Analysis failed: {str(e)}",
                "result": None,
            }

    def _predict_trend(self, df: pd.DataFrame, indicators: Dict) -> Dict[str, Any]:
        """Predict trend based on technical indicators."""
        signals = []
        bullish_count = 0
        bearish_count = 0
        neutral_count = 0

        # RSI Analysis
        rsi = indicators["rsi_14"]
        if rsi < 30:
            signals.append("RSI oversold (< 30) - BULLISH signal")
            bullish_count += 2
        elif rsi > 70:
            signals.append("RSI overbought (> 70) - BEARISH signal")
            bearish_count += 2
        elif 40 <= rsi <= 60:
            signals.append("RSI neutral (40-60)")
            neutral_count += 1
        else:
            neutral_count += 1

        # MACD Analysis
        if indicators["macd_diff"] > 0:
            signals.append("MACD above signal line - BULLISH")
            bullish_count += 1
        else:
            signals.append("MACD below signal line - BEARISH")
            bearish_count += 1

        # Moving Average Analysis
        price = indicators["price"]
        sma_20 = indicators["sma_20"]
        sma_50 = indicators["sma_50"]
        
        if sma_20 and sma_50:
            if price > sma_20 > sma_50:
                signals.append("Price > SMA20 > SMA50 - Strong BULLISH")
                bullish_count += 2
            elif price < sma_20 < sma_50:
                signals.append("Price < SMA20 < SMA50 - Strong BEARISH")
                bearish_count += 2
            elif price > sma_20:
                signals.append("Price > SMA20 - BULLISH")
                bullish_count += 1
            else:
                signals.append("Price < SMA20 - BEARISH")
                bearish_count += 1

        # Bollinger Bands Analysis
        bb_position = (price - indicators["bb_lower"]) / (indicators["bb_upper"] - indicators["bb_lower"])
        if bb_position < 0.2:
            signals.append("Price near lower Bollinger Band - BULLISH")
            bullish_count += 1
        elif bb_position > 0.8:
            signals.append("Price near upper Bollinger Band - BEARISH")
            bearish_count += 1

        # Stochastic Analysis
        stoch_k = indicators["stoch_k"]
        if stoch_k < 20:
            signals.append("Stochastic oversold (< 20) - BULLISH")
            bullish_count += 1
        elif stoch_k > 80:
            signals.append("Stochastic overbought (> 80) - BEARISH")
            bearish_count += 1

        # Volume Analysis
        if indicators["volume_ratio"] > 1.5:
            signals.append("High volume (1.5x average) - Strong momentum")
        elif indicators["volume_ratio"] < 0.5:
            signals.append("Low volume - Weak momentum")

        # Determine overall trend
        total_signals = bullish_count + bearish_count + neutral_count
        if total_signals > 0:
            bullish_pct = (bullish_count / (bullish_count + bearish_count)) * 100 if (bullish_count + bearish_count) > 0 else 50
        else:
            bullish_pct = 50

        if bullish_pct >= 65:
            trend = "BULLISH"
            confidence = "High" if bullish_pct >= 75 else "Medium"
            recommendation = "BUY"
        elif bullish_pct <= 35:
            trend = "BEARISH"
            confidence = "High" if bullish_pct <= 25 else "Medium"
            recommendation = "SELL"
        else:
            trend = "NEUTRAL"
            confidence = "Low"
            recommendation = "HOLD"

        return {
            "trend": trend,
            "confidence": confidence,
            "recommendation": recommendation,
            "bullish_signals": bullish_count,
            "bearish_signals": bearish_count,
            "signals": signals,
            "bullish_percentage": round(bullish_pct, 1),
        }

    def _create_summary(
        self, symbol: str, company_name: str, indicators: Dict, prediction: Optional[Dict]
    ) -> str:
        """Create a human-readable summary."""
        lines = [
            f"Stock Analysis for {company_name} ({symbol})",
            f"=" * 60,
            f"",
            f"Current Price: ${indicators['price']:.2f} ({indicators['price_change_pct']:+.2f}%)",
            f"",
            f"Technical Indicators:",
            f"  RSI (14): {indicators['rsi_14']:.2f} - {'Oversold' if indicators['rsi_14'] < 30 else 'Overbought' if indicators['rsi_14'] > 70 else 'Neutral'}",
            f"  MACD: {indicators['macd']:.4f} (Signal: {indicators['macd_signal']:.4f})",
        ]

        if indicators['sma_20']:
            lines.append(f"  SMA (20): ${indicators['sma_20']:.2f}")
        if indicators['sma_50']:
            lines.append(f"  SMA (50): ${indicators['sma_50']:.2f}")

        lines.extend([
            f"  Bollinger Bands: ${indicators['bb_lower']:.2f} - ${indicators['bb_middle']:.2f} - ${indicators['bb_upper']:.2f}",
            f"  Stochastic: {indicators['stoch_k']:.2f}% (K) / {indicators['stoch_d']:.2f}% (D)",
            f"  ATR (14): {indicators['atr_14']:.2f}",
            f"  Volume Ratio: {indicators['volume_ratio']:.2f}x average",
        ])

        if prediction:
            lines.extend([
                f"",
                f"Trend Prediction:",
                f"  Overall Trend: {prediction['trend']}",
                f"  Confidence: {prediction['confidence']}",
                f"  Recommendation: {prediction['recommendation']}",
                f"  Bullish Signals: {prediction['bullish_signals']} | Bearish Signals: {prediction['bearish_signals']}",
                f"  Bullish Percentage: {prediction['bullish_percentage']:.1f}%",
                f"",
                f"Key Signals:",
            ])
            for signal in prediction['signals']:
                lines.append(f"  • {signal}")

        return "\n".join(lines)

