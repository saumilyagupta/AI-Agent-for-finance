"""Data visualization tool using Plotly with data processing capabilities."""

from typing import Any, Dict, List, Optional, Union

import plotly.graph_objects as go
from plotly.utils import PlotlyJSONEncoder

import json
import pandas as pd
import numpy as np

from app.tools.base import BaseTool
from app.utils.logger import logger


class VisualizerTool(BaseTool):
    """
    Tool for generating charts and visualizations using Plotly.
    
    Supports data processing/calculation before visualization:
    - Multi-series charts (multiple lines/bars on same chart)
    - Data aggregation and transformation
    - Time-series with multiple categories
    - Combined/subplot visualizations
    """

    def __init__(self):
        super().__init__(
            name="visualizer",
            description="Generate interactive charts and visualizations with data processing. Supports line, bar, scatter, pie, candlestick, and multi-series charts. Can process/calculate data before plotting. For multi-series: use data={'series': [{'name': 'Series1', 'x': [...], 'y': [...]}, ...]}. Returns HTML or JSON for embedding.",
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "chart_type": {
                    "type": "string",
                    "description": "Type of chart: 'line', 'bar', 'scatter', 'candlestick', 'pie', 'multi_line', 'multi_bar', 'grouped_bar', 'stacked_bar'",
                    "enum": ["line", "bar", "scatter", "candlestick", "pie", "multi_line", "multi_bar", "grouped_bar", "stacked_bar"],
                },
                "data": {
                    "type": "object",
                    "description": "Chart data. For single series: {'x': [...], 'y': [...]}. For multi-series: {'series': [{'name': 'Name1', 'x': [...], 'y': [...]}, ...]}. Can also be list of records.",
                },
                "title": {
                    "type": "string",
                    "description": "Chart title",
                },
                "x_label": {
                    "type": "string",
                    "description": "X-axis label",
                },
                "y_label": {
                    "type": "string",
                    "description": "Y-axis label",
                },
                "process_data": {
                    "type": "boolean",
                    "description": "Whether to process/calculate data before plotting (default: false). If true, will aggregate, transform, or calculate statistics.",
                    "default": False,
                },
                "data_operation": {
                    "type": "string",
                    "description": "Data processing operation: 'aggregate', 'transform', 'calculate_stats', 'group_by' (only if process_data=true)",
                    "enum": ["aggregate", "transform", "calculate_stats", "group_by"],
                },
                "output_format": {
                    "type": "string",
                    "description": "Output format: 'html' or 'json' (default: 'json')",
                    "enum": ["html", "json"],
                    "default": "json",
                },
            },
            "required": ["chart_type", "data"],
        }

    async def execute(
        self,
        chart_type: str,
        data: Dict[str, Any] = None,
        title: Optional[str] = None,
        x_label: Optional[str] = None,
        y_label: Optional[str] = None,
        process_data: bool = False,
        data_operation: Optional[str] = None,
        output_format: str = "json",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Generate visualization with optional data processing.
        
        Supports:
        - Single series charts (line, bar, scatter, pie, candlestick)
        - Multi-series charts (multi_line, multi_bar, grouped_bar, stacked_bar)
        - Data processing before visualization (aggregate, transform, calculate_stats)
        """
        try:
            # Validate required data parameter
            if data is None:
                return {
                    "success": False,
                    "error": "Missing required 'data' parameter. For single series: {'x': [...], 'y': [...]}. For multi-series: {'series': [{'name': 'Name1', 'x': [...], 'y': [...]}, ...]}",
                    "result": None,
                }
            
            # Process data if requested
            if process_data and data_operation:
                data = self._process_data(data, data_operation)
                logger.info(f"Processed data using operation: {data_operation}")
            
            # Check if this is a multi-series chart
            is_multi_series = chart_type in ["multi_line", "multi_bar", "grouped_bar", "stacked_bar"]
            
            if is_multi_series:
                # Handle multi-series data
                fig = self._create_multi_series_chart(chart_type, data, title, x_label, y_label)
            else:
                # Handle single series data
                fig = self._create_single_series_chart(chart_type, data, title, x_label, y_label)

            # Generate output
            if output_format == "html":
                html = fig.to_html(include_plotlyjs="cdn")
                return {
                    "success": True,
                    "result": {
                        "format": "html",
                        "html": html,
                    },
                }
            else:
                # Return JSON
                fig_json = json.loads(json.dumps(fig.to_dict(), cls=PlotlyJSONEncoder))
                return {
                    "success": True,
                    "result": {
                        "format": "json",
                        "figure": fig_json,
                    },
                }

        except Exception as e:
            logger.error(f"Visualization failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Visualization failed: {str(e)}",
                "result": None,
            }
    
    def _process_data(self, data: Union[Dict, List], operation: str) -> Dict[str, Any]:
        """Process/calculate data before visualization."""
        try:
            # Convert to DataFrame for easier processing
            if isinstance(data, list):
                df = pd.DataFrame(data)
            elif isinstance(data, dict) and "series" in data:
                # Multi-series data - process each series
                processed_series = []
                for series in data["series"]:
                    if isinstance(series.get("data"), list):
                        series_df = pd.DataFrame(series["data"])
                    else:
                        series_df = pd.DataFrame({"x": series.get("x", []), "y": series.get("y", [])})
                    
                    processed_df = self._apply_operation(series_df, operation)
                    processed_series.append({
                        "name": series.get("name", "Series"),
                        "x": processed_df["x"].tolist() if "x" in processed_df.columns else processed_df.index.tolist(),
                        "y": processed_df["y"].tolist() if "y" in processed_df.columns else processed_df.iloc[:, 0].tolist(),
                    })
                return {"series": processed_series}
            else:
                # Single series
                if "x" in data and "y" in data:
                    df = pd.DataFrame({"x": data["x"], "y": data["y"]})
                else:
                    df = pd.DataFrame([data])
            
            processed_df = self._apply_operation(df, operation)
            
            # Convert back to dict format
            if "x" in processed_df.columns and "y" in processed_df.columns:
                return {
                    "x": processed_df["x"].tolist(),
                    "y": processed_df["y"].tolist(),
                }
            else:
                return {
                    "x": processed_df.index.tolist(),
                    "y": processed_df.iloc[:, 0].tolist(),
                }
        except Exception as e:
            logger.warning(f"Data processing failed, using original data: {e}")
            return data
    
    def _apply_operation(self, df: pd.DataFrame, operation: str) -> pd.DataFrame:
        """Apply data processing operation to DataFrame."""
        if operation == "aggregate":
            # Aggregate by grouping (if categorical x) or time-based
            if "x" in df.columns:
                # Try to detect if x is numeric or categorical
                if df["x"].dtype in [np.int64, np.float64]:
                    # Numeric - create bins
                    df["x_bin"] = pd.cut(df["x"], bins=10)
                    result = df.groupby("x_bin", observed=True)["y"].mean().reset_index()
                    result["x"] = result["x_bin"].apply(lambda x: x.mid)
                    return result[["x", "y"]]
                else:
                    # Categorical - group by x
                    return df.groupby("x", observed=True)["y"].mean().reset_index()
            return df
        
        elif operation == "calculate_stats":
            # Calculate statistics (mean, std, etc.) for each group
            if "x" in df.columns:
                stats = df.groupby("x", observed=True)["y"].agg(["mean", "std", "min", "max"]).reset_index()
                stats["y"] = stats["mean"]  # Use mean as primary y value
                return stats[["x", "y"]]
            return df
        
        elif operation == "transform":
            # Apply transformations (normalize, log, etc.)
            if "y" in df.columns:
                # Normalize y values
                df["y"] = (df["y"] - df["y"].min()) / (df["y"].max() - df["y"].min() + 1e-10)
            return df
        
        elif operation == "group_by":
            # Group by a category and aggregate
            if "category" in df.columns and "y" in df.columns:
                return df.groupby("category", observed=True)["y"].sum().reset_index()
            return df
        
        return df
    
    def _create_single_series_chart(
        self, 
        chart_type: str, 
        data: Union[Dict, List], 
        title: Optional[str], 
        x_label: Optional[str], 
        y_label: Optional[str]
    ) -> go.Figure:
        """Create a single-series chart."""
        # Extract x and y data
        if isinstance(data, list):
            if len(data) == 0:
                raise ValueError("Empty data list")
            x = [item.get("x") or item.get("date") or item.get("Date") for item in data]
            y = [item.get("y") or item.get("value") or item.get("Close") for item in data]
        else:
            x = data.get("x", [])
            y = data.get("y", [])

        if not x or not y:
            raise ValueError("Missing x or y data")

        fig = go.Figure()

        if chart_type == "line":
            fig.add_trace(go.Scatter(x=x, y=y, mode="lines+markers", name="Data", line=dict(width=2)))

        elif chart_type == "bar":
            fig.add_trace(go.Bar(x=x, y=y, name="Data", marker_color="steelblue"))

        elif chart_type == "scatter":
            fig.add_trace(go.Scatter(x=x, y=y, mode="markers", name="Data", marker=dict(size=8)))

        elif chart_type == "candlestick":
            if isinstance(data, list) and len(data) > 0:
                open_prices = [item.get("Open") or item.get("open") for item in data]
                high_prices = [item.get("High") or item.get("high") for item in data]
                low_prices = [item.get("Low") or item.get("low") for item in data]
                close_prices = [item.get("Close") or item.get("close") for item in data]
                dates = [item.get("Date") or item.get("date") or x[i] for i, item in enumerate(data)]
            else:
                open_prices = data.get("open", [])
                high_prices = data.get("high", [])
                low_prices = data.get("low", [])
                close_prices = data.get("close", [])

            fig.add_trace(
                go.Candlestick(
                    x=dates if "dates" in locals() else x,
                    open=open_prices,
                    high=high_prices,
                    low=low_prices,
                    close=close_prices,
                    name="Price",
                )
            )

        elif chart_type == "pie":
            labels = x
            values = y
            fig.add_trace(go.Pie(labels=labels, values=values, hole=0.3))

        fig.update_layout(
            title=title or f"{chart_type.title()} Chart",
            xaxis_title=x_label or "X",
            yaxis_title=y_label or "Y",
            template="plotly_white",
            hovermode="closest",
        )
        
        return fig
    
    def _create_multi_series_chart(
        self,
        chart_type: str,
        data: Dict[str, Any],
        title: Optional[str],
        x_label: Optional[str],
        y_label: Optional[str]
    ) -> go.Figure:
        """Create a multi-series chart."""
        fig = go.Figure()
        
        # Extract series data
        if "series" in data:
            series_list = data["series"]
        elif isinstance(data, list):
            # Convert list to series format
            series_list = [{"name": f"Series {i+1}", "x": item.get("x", []), "y": item.get("y", [])} for i, item in enumerate(data)]
        else:
            raise ValueError("Multi-series charts require 'series' array in data")

        if not series_list:
            raise ValueError("No series data provided")

        # Color palette for multiple series
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
        
        if chart_type == "multi_line":
            for i, series in enumerate(series_list):
                x = series.get("x", [])
                y = series.get("y", [])
                name = series.get("name", f"Series {i+1}")
                fig.add_trace(go.Scatter(
                    x=x, 
                    y=y, 
                    mode="lines+markers",
                    name=name,
                    line=dict(width=2, color=colors[i % len(colors)]),
                    marker=dict(size=6)
                ))

        elif chart_type in ["multi_bar", "grouped_bar", "stacked_bar"]:
            for i, series in enumerate(series_list):
                x = series.get("x", [])
                y = series.get("y", [])
                name = series.get("name", f"Series {i+1}")
                
                if chart_type == "stacked_bar":
                    fig.add_trace(go.Bar(
                        x=x,
                        y=y,
                        name=name,
                        marker_color=colors[i % len(colors)]
                    ))
                else:  # multi_bar or grouped_bar
                    fig.add_trace(go.Bar(
                        x=x,
                        y=y,
                        name=name,
                        marker_color=colors[i % len(colors)]
                    ))
            
            if chart_type == "stacked_bar":
                fig.update_layout(barmode="stack")
            else:
                fig.update_layout(barmode="group")

        fig.update_layout(
            title=title or f"{chart_type.replace('_', ' ').title()} Chart",
            xaxis_title=x_label or "X",
            yaxis_title=y_label or "Y",
            template="plotly_white",
            hovermode="x unified",
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
        )
        
        return fig

