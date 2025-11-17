"""Code executor tool with sandboxed Python execution."""

import asyncio
import io
import sys
from contextlib import redirect_stdout, redirect_stderr
from typing import Any, Dict

from app.tools.base import BaseTool
from app.utils.logger import logger


class CodeExecutorTool(BaseTool):
    """Tool for executing Python code in a sandboxed environment."""

    def __init__(self):
        super().__init__(
            name="code_executor",
            description="Execute Python code snippets safely. Supports basic Python operations with restricted builtins for security.",
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Execution timeout in seconds (default: 10)",
                    "default": 10,
                },
            },
            "required": ["code"],
        }

    async def execute(self, code: str, timeout: int = 10, **kwargs) -> Dict[str, Any]:
        """Execute Python code in sandbox."""
        try:
            # Restricted builtins for security
            # Allow __import__ but with restrictions on what can be imported
            def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
                """Safe import that only allows whitelisted modules."""
                # Common safe Python standard library modules
                allowed_modules = {
                    # Math and numeric
                    'math', 'statistics', 'decimal', 'fractions', 'numbers',
                    # Data structures and utilities
                    'collections', 'itertools', 'functools', 'operator', 'string',
                    # Date and time
                    'datetime', 'time', 'calendar',
                    # JSON and data formats
                    'json', 'csv', 'base64',
                    # Text processing
                    're', 'textwrap', 'unicodedata',
                    # System (limited)
                    # 'os', 'sys', 'pathlib', 'tempfile',
                    # Random and hashing
                    'random', 'secrets', 'hashlib',
                    # Data science libraries
                    'numpy', 'pandas', 'sympy',
                    # Additional utilities
                    'copy', 'enum', 'typing', 'dataclasses', 'uuid',
                }
                if name in allowed_modules:
                    return __import__(name, globals, locals, fromlist, level)
                else:
                    raise ImportError(f"Import of '{name}' is not allowed for security reasons. Allowed modules: {', '.join(sorted(allowed_modules))}")
            
            # Safe file operations - restrict to a safe working directory
            import os
            from pathlib import Path
            
            # Use a consistent safe directory for code execution
            safe_file_dir = Path("./code_exec_workspace")
            safe_file_dir.mkdir(exist_ok=True)
            safe_dir_abs = os.path.abspath(str(safe_file_dir))
            
            def safe_open(file, mode='r', *args, **kwargs):
                """Safe file open that restricts access to safe directory."""
                # Only allow opening files in the safe directory
                file_path = os.path.abspath(os.path.expanduser(str(file)))
                
                # Ensure file is within safe directory
                if not file_path.startswith(safe_dir_abs):
                    # If file is not in safe dir, create it there
                    filename = os.path.basename(file_path)
                    file_path = os.path.join(safe_dir_abs, filename)
                
                # Ensure parent directory exists (handle case where file_path is just a filename)
                parent_dir = os.path.dirname(file_path)
                if parent_dir and parent_dir != safe_dir_abs:
                    # Only create subdirectories within safe_dir
                    if parent_dir.startswith(safe_dir_abs):
                        os.makedirs(parent_dir, exist_ok=True)
                    else:
                        # Fallback to safe_dir if parent is outside
                        file_path = os.path.join(safe_dir_abs, os.path.basename(file_path))
                
                return open(file_path, mode, *args, **kwargs)
            
            safe_builtins = {
                "__builtins__": {
                    "abs": abs,
                    "all": all,
                    "any": any,
                    "bool": bool,
                    "dict": dict,
                    "enumerate": enumerate,
                    "float": float,
                    "int": int,
                    "len": len,
                    "list": list,
                    "max": max,
                    "min": min,
                    "range": range,
                    "round": round,
                    "set": set,
                    "sorted": sorted,
                    "str": str,
                    "sum": sum,
                    "tuple": tuple,
                    "zip": zip,
                    "ImportError": ImportError,
                    "Exception": Exception,
                    "__import__": safe_import,
                    "open": safe_open,
                },
                "print": print,
            }

            # Create restricted globals
            # Start with builtins directly accessible (not nested in __builtins__)
            restricted_globals = safe_builtins["__builtins__"].copy()
            
            # Add print function
            restricted_globals["print"] = print
            
            # Ensure __builtins__ dict is also available for compatibility
            restricted_globals["__builtins__"] = safe_builtins["__builtins__"]
            
            # Inject any dependency results passed via kwargs
            # This allows code to access results from previous tasks
            if 'dep_results' in kwargs:
                dep_results = kwargs['dep_results']
                if isinstance(dep_results, dict):
                    for key, value in dep_results.items():
                        # Add all dependency results as variables
                        restricted_globals[key] = value
            
            # Also allow accessing common variable names from previous tasks
            # Extract any variables from kwargs that might be task results
            for key, value in kwargs.items():
                if key not in ['code', 'timeout', 'dep_results']:
                    # Add all non-reserved kwargs as variables
                    restricted_globals[key] = value
            
            # If input_params is provided, make it available
            if 'input_params' in kwargs:
                restricted_globals['input_params'] = kwargs['input_params']

            # Capture stdout and stderr
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()

            async def run_code():
                try:
                    with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                        # Execute code
                        exec_globals = restricted_globals.copy()
                        exec(code, exec_globals)
                        return exec_globals
                except Exception as e:
                    raise e

            # Run with timeout
            try:
                result_globals = await asyncio.wait_for(run_code(), timeout=timeout)
            except asyncio.TimeoutError:
                return {
                    "success": False,
                    "error": f"Code execution timed out after {timeout} seconds",
                    "result": None,
                }

            stdout_output = stdout_capture.getvalue()
            stderr_output = stderr_capture.getvalue()

            # Extract result (look for 'result' variable or last expression)
            result = None
            if "result" in result_globals:
                result = result_globals["result"]
            elif stdout_output:
                result = stdout_output.strip()

            return {
                "success": True,
                "result": {
                    "output": stdout_output,
                    "result": result,
                    "error": stderr_output if stderr_output else None,
                },
            }

        except Exception as e:
            logger.error(f"Code execution failed: {e}")
            return {
                "success": False,
                "error": f"Execution failed: {str(e)}",
                "result": None,
            }

