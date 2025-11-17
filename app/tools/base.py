"""Base tool interface."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from app.utils.logger import logger


class BaseTool(ABC):
    """Abstract base class for all tools."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.usage_count = 0
        self.error_count = 0

    @property
    @abstractmethod
    def input_schema(self) -> Dict[str, Any]:
        """Return JSON schema for tool inputs."""
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute the tool with given parameters.

        Returns:
            Dict with 'success' (bool), 'result' (Any), and optional 'error' (str)
        """
        pass

    def validate_input(self, **kwargs) -> bool:
        """Validate input parameters against schema."""
        schema = self.input_schema
        required = schema.get("required", [])

        # Check required fields
        for field in required:
            if field not in kwargs:
                logger.error(f"Missing required field: {field} for tool {self.name}")
                return False

        # Check field types (basic validation)
        properties = schema.get("properties", {})
        for field, value in kwargs.items():
            if field in properties:
                expected_type = properties[field].get("type")
                if expected_type and not isinstance(value, self._get_python_type(expected_type)):
                    logger.warning(
                        f"Type mismatch for {field}: expected {expected_type}, got {type(value).__name__}"
                    )

        return True

    @staticmethod
    def _get_python_type(json_type: str) -> type:
        """Convert JSON schema type to Python type."""
        type_map = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        return type_map.get(json_type, str)

    async def run(self, **kwargs) -> Dict[str, Any]:
        """Run tool with validation and error handling."""
        self.usage_count += 1

        if not self.validate_input(**kwargs):
            self.error_count += 1
            return {
                "success": False,
                "error": "Invalid input parameters",
                "result": None,
            }

        try:
            result = await self.execute(**kwargs)
            if result.get("success"):
                logger.info(f"Tool {self.name} executed successfully")
            else:
                self.error_count += 1
                logger.error(f"Tool {self.name} failed: {result.get('error')}")
            return result
        except Exception as e:
            self.error_count += 1
            logger.exception(f"Tool {self.name} raised exception: {e}")
            return {
                "success": False,
                "error": str(e),
                "result": None,
            }

    def get_stats(self) -> Dict[str, Any]:
        """Get tool usage statistics."""
        return {
            "name": self.name,
            "usage_count": self.usage_count,
            "error_count": self.error_count,
            "success_rate": (self.usage_count - self.error_count) / self.usage_count
            if self.usage_count > 0
            else 0.0,
        }

