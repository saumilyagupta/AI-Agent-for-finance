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
            description="Read and write files. Supports CSV, JSON, PDF, and plain text formats. Reading can target any file inside the project root; writes stay confined to file_workspace/ for safety.",
        )
        self.project_root = Path(".").resolve()
        self.work_dir = (self.project_root / "file_workspace").resolve()
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
                    "description": "File type: 'csv', 'json', 'pdf', or 'text'",
                    "enum": ["csv", "json", "pdf", "text"],
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
            # Resolve file path safely
            requested_path = Path(file_path)
            if operation == "write":
                # Writes stay confined to file_workspace
                full_path = (self.work_dir / requested_path.name).resolve()
            else:
                if requested_path.is_absolute():
                    full_path = requested_path.resolve()
                else:
                    full_path = (self.project_root / requested_path).resolve()

                # Fallback to file_workspace if file is located there
                if not full_path.exists():
                    workspace_candidate = (self.work_dir / requested_path.name).resolve()
                    if workspace_candidate.exists():
                        full_path = workspace_candidate

            # Enforce that resolved path stays under project root or workspace
            if not str(full_path).startswith(str(self.project_root)):
                return {
                    "success": False,
                    "error": "Access denied: file path escapes project workspace",
                    "result": None,
                }

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

                elif file_type == "text":
                    with open(full_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    return {
                        "success": True,
                        "result": {
                            "file_path": file_path,
                            "text": content,
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

                elif file_type == "text":
                    with open(full_path, "w", encoding="utf-8") as f:
                        if isinstance(data, str):
                            f.write(data)
                        else:
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

