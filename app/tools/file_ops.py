"""File operations tool."""

import json
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
from PyPDF2 import PdfReader

from app.tools.base import BaseTool
from app.utils.logger import logger


class FileOpsTool(BaseTool):
    """Tool for reading and writing files (CSV, JSON, PDF)."""

    def __init__(self):
        super().__init__(
            name="file_ops",
            description="Read and write files. Supports CSV, JSON, and PDF formats. Files are read/written relative to a safe working directory.",
        )
        self.work_dir = Path("./file_workspace")
        self.work_dir.mkdir(exist_ok=True)

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "description": "Operation: 'read' or 'write'",
                    "enum": ["read", "write"],
                },
                "file_path": {
                    "type": "string",
                    "description": "File path (relative to workspace)",
                },
                "file_type": {
                    "type": "string",
                    "description": "File type: 'csv', 'json', or 'pdf'",
                    "enum": ["csv", "json", "pdf"],
                },
                "data": {
                    "type": "object",
                    "description": "Data to write (for write operation)",
                },
            },
            "required": ["operation", "file_path", "file_type"],
        }

    async def execute(
        self,
        operation: str,
        file_path: str,
        file_type: str,
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute file operation."""
        try:
            # Handle case where data might be passed via kwargs
            if data is None and 'data' in kwargs:
                data = kwargs['data']
            # Sanitize file path
            safe_path = Path(file_path).name  # Only filename, no directory traversal
            full_path = self.work_dir / safe_path

            if operation == "read":
                if not full_path.exists():
                    return {
                        "success": False,
                        "error": f"File not found: {file_path}",
                        "result": None,
                    }

                if file_type == "csv":
                    df = pd.read_csv(full_path)
                    return {
                        "success": True,
                        "result": {
                            "file_path": file_path,
                            "data": df.to_dict("records"),
                            "shape": list(df.shape),
                        },
                    }

                elif file_type == "json":
                    with open(full_path, "r", encoding="utf-8") as f:
                        content = json.load(f)
                    return {
                        "success": True,
                        "result": {
                            "file_path": file_path,
                            "data": content,
                        },
                    }

                elif file_type == "pdf":
                    reader = PdfReader(full_path)
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text() + "\n"
                    return {
                        "success": True,
                        "result": {
                            "file_path": file_path,
                            "text": text,
                            "num_pages": len(reader.pages),
                        },
                    }

            elif operation == "write":
                if not data:
                    return {
                        "success": False,
                        "error": "Data required for write operation",
                        "result": None,
                    }

                if file_type == "csv":
                    if isinstance(data, list):
                        df = pd.DataFrame(data)
                    else:
                        df = pd.DataFrame([data])
                    df.to_csv(full_path, index=False)
                    return {
                        "success": True,
                        "result": {
                            "file_path": file_path,
                            "message": "File written successfully",
                        },
                    }

                elif file_type == "json":
                    with open(full_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                    return {
                        "success": True,
                        "result": {
                            "file_path": file_path,
                            "message": "File written successfully",
                        },
                    }

                else:
                    return {
                        "success": False,
                        "error": f"Write operation not supported for {file_type}",
                        "result": None,
                    }

            else:
                return {
                    "success": False,
                    "error": f"Unknown operation: {operation}",
                    "result": None,
                }

        except Exception as e:
            logger.error(f"File operation failed: {e}")
            return {
                "success": False,
                "error": f"File operation failed: {str(e)}",
                "result": None,
            }

