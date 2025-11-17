"""Calculator tool for mathematical operations."""

import math
from typing import Any, Dict, List, Union

import numpy as np
import sympy as sp

from app.tools.base import BaseTool
from app.utils.logger import logger


class CalculatorTool(BaseTool):
    """Tool for mathematical calculations and statistical operations."""

    def __init__(self):
        super().__init__(
            name="calculator",
            description="Perform mathematical calculations, statistical operations, and data transformations. Supports basic math, statistics, and symbolic math.",
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "description": "Type of operation: 'evaluate' (math expression), 'statistics' (mean, median, etc), 'transform' (data transformations)",
                },
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to evaluate (for 'evaluate' operation)",
                },
                "data": {
                    "type": "array",
                    "description": "List of numbers for statistical operations",
                    "items": {"type": "number"},
                },
                "stat_op": {
                    "type": "string",
                    "description": "Statistical operation: 'mean', 'median', 'std', 'var', 'min', 'max', 'sum'",
                },
            },
            "required": [],  # Made optional - will auto-detect from expression or data
        }

    async def execute(
        self,
        operation: Union[str, None] = None,
        expression: Union[str, None] = None,
        data: Union[List[float], None] = None,
        stat_op: Union[str, None] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute calculator operation."""
        try:
            # Auto-detect operation if not provided
            if not operation:
                if expression:
                    operation = "evaluate"
                elif data:
                    operation = "statistics"
                else:
                    return {
                        "success": False,
                        "error": "Either 'operation' or 'expression'/'data' must be provided",
                        "result": None,
                    }
            
            if operation == "evaluate":
                if not expression:
                    return {
                        "success": False,
                        "error": "Expression required for evaluate operation",
                        "result": None,
                    }

                # Use sympy for safe evaluation
                try:
                    # Parse and evaluate expression
                    expr = sp.sympify(expression)
                    result = float(expr.evalf())
                except Exception as e:
                    # Fallback to eval with restricted globals
                    safe_dict = {
                        "__builtins__": {},
                        "abs": abs,
                        "round": round,
                        "min": min,
                        "max": max,
                        "sum": sum,
                        "pow": pow,
                        "math": math,
                    }
                    result = eval(expression, safe_dict)

                return {
                    "success": True,
                    "result": {
                        "expression": expression,
                        "result": result,
                    },
                }

            elif operation == "statistics":
                if not data:
                    return {
                        "success": False,
                        "error": "Data array required for statistics operation",
                        "result": None,
                    }

                if not stat_op:
                    # Return all statistics
                    arr = np.array(data)
                    return {
                        "success": True,
                        "result": {
                            "mean": float(np.mean(arr)),
                            "median": float(np.median(arr)),
                            "std": float(np.std(arr)),
                            "var": float(np.var(arr)),
                            "min": float(np.min(arr)),
                            "max": float(np.max(arr)),
                            "sum": float(np.sum(arr)),
                            "count": len(data),
                        },
                    }

                # Single statistic
                arr = np.array(data)
                stat_map = {
                    "mean": np.mean,
                    "median": np.median,
                    "std": np.std,
                    "var": np.var,
                    "min": np.min,
                    "max": np.max,
                    "sum": np.sum,
                }

                if stat_op not in stat_map:
                    return {
                        "success": False,
                        "error": f"Unknown statistical operation: {stat_op}",
                        "result": None,
                    }

                result = stat_map[stat_op](arr)
                return {
                    "success": True,
                    "result": {
                        "operation": stat_op,
                        "value": float(result),
                    },
                }

            else:
                return {
                    "success": False,
                    "error": f"Unknown operation: {operation}",
                    "result": None,
                }

        except Exception as e:
            logger.error(f"Calculator operation failed: {e}")
            return {
                "success": False,
                "error": f"Calculation failed: {str(e)}",
                "result": None,
            }

