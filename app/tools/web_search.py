"""Web search tool using Tavily API only."""

import asyncio
from typing import Any, Dict, List, Optional

from app.tools.base import BaseTool
from app.utils.config import settings
from app.utils.logger import logger


class WebSearchTool(BaseTool):
    """Tool for searching the web using Tavily API (optimized for AI/LLMs)."""

    def __init__(self):
        super().__init__(
            name="web_search",
            description="Search the web using Tavily API - an AI-optimized search engine. Returns relevant, filtered search results with titles, snippets, URLs, AI-generated answers, and relevance scores.",
        )
        
        # Initialize Tavily client from settings
        self.tavily_api_key = settings.tavily_api_key
        
        if not self.tavily_api_key:
            logger.error("TAVILY_API_KEY not found in .env file! Web search will not work.")
            logger.error("Add to .env: TAVILY_API_KEY=your-key-here")
            logger.error("Get your free API key at: https://app.tavily.com (1,000 free searches/month)")
            self.tavily_client = None
        else:
            # Lazy import - import TavilyClient only when needed to avoid startup issues
            try:
                from tavily import TavilyClient
                self.tavily_client = TavilyClient(api_key=self.tavily_api_key)
                logger.info("[OK] Tavily API initialized successfully")
            except ImportError:
                # Try to add global site-packages to path as fallback
                import sys
                import os
                
                # Find global Python site-packages
                if sys.executable and ('venv' in sys.executable.lower() or '.venv' in sys.executable.lower()):
                    # We're in a venv, try to find global Python
                    python_exe = sys.executable
                    # Try common locations
                    possible_paths = [
                        os.path.join(os.path.dirname(os.path.dirname(python_exe)), 'Lib', 'site-packages'),
                        r'C:\Python312\Lib\site-packages',
                        r'C:\Python311\Lib\site-packages',
                        r'C:\Python310\Lib\site-packages',
                    ]
                    
                    for path in possible_paths:
                        if os.path.exists(path):
                            try:
                                # Check if tavily exists in this path
                                tavily_path = os.path.join(path, 'tavily')
                                if os.path.exists(tavily_path) or os.path.exists(os.path.join(path, 'tavily.py')):
                                    if path not in sys.path:
                                        sys.path.insert(0, path)
                                    try:
                                        from tavily import TavilyClient
                                        self.tavily_client = TavilyClient(api_key=self.tavily_api_key)
                                        logger.info("[OK] Tavily API initialized successfully (from global site-packages)")
                                        break
                                    except (ImportError, Exception) as e:
                                        logger.debug(f"Failed to import from {path}: {e}")
                                        continue
                            except (OSError, PermissionError):
                                # Skip if we can't access the directory
                                continue
                
                if not self.tavily_client:
                    logger.error("tavily-python package not installed! Run: pip install tavily-python")
                    logger.error("If using venv, ensure tavily-python is installed in the venv")
                    self.tavily_client = None
            except Exception as e:
                logger.error(f"Failed to initialize Tavily client: {e}")
                logger.error("Check if your TAVILY_API_KEY in .env is correct")
                self.tavily_client = None

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query string",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 5)",
                    "default": 5,
                },
                "search_depth": {
                    "type": "string",
                    "description": "Search depth: 'basic' (faster) or 'advanced' (more thorough). Default: 'basic'",
                    "enum": ["basic", "advanced"],
                    "default": "basic",
                },
                "include_domains": {
                    "type": "array",
                    "description": "List of domains to specifically include (e.g., ['gov.in', 'nic.in'])",
                    "items": {"type": "string"},
                },
                "exclude_domains": {
                    "type": "array",
                    "description": "List of domains to exclude",
                    "items": {"type": "string"},
                },
                "include_answer": {
                    "type": "boolean",
                    "description": "Include AI-generated answer (default: true)",
                    "default": True,
                },
            },
            "required": ["query"],
        }

    async def execute(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        include_answer: bool = True,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute web search using Tavily API."""
        
        # Check if Tavily is available
        if not self.tavily_client:
            error_msg = (
                "Tavily API not available. "
                "Please set TAVILY_API_KEY environment variable. "
                "Get your free API key at: https://app.tavily.com (1,000 free searches/month)"
            )
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "result": {
                    "query": query,
                    "results": [],
                    "count": 0,
                },
            }
        
        try:
            logger.info(f"Searching with Tavily API: '{query}' (depth: {search_depth}, max_results: {max_results})")
            
            # Prepare search parameters
            search_params = {
                "query": query,
                "search_depth": search_depth,
                "max_results": max_results,
                "include_answer": include_answer,
                "include_raw_content": False,  # Don't need raw HTML
            }
            
            # Add domain filters if provided
            if include_domains:
                search_params["include_domains"] = include_domains
                logger.info(f"Including domains: {include_domains}")
            
            if exclude_domains:
                search_params["exclude_domains"] = exclude_domains
                logger.info(f"Excluding domains: {exclude_domains}")
            
            # Run Tavily search in executor (it's synchronous)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.tavily_client.search(**search_params)
            )
            
            # Parse Tavily response
            results = response.get("results", [])
            answer = response.get("answer", "")
            
            if not results:
                logger.warning(f"Tavily returned no results for query: {query}")
                return {
                    "success": False,
                    "error": "No results found for your query",
                    "result": {
                        "query": query,
                        "results": [],
                        "count": 0,
                        "answer": answer if answer else None,
                    },
                }
            
            # Format results
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "snippet": result.get("content", ""),  # Tavily provides extracted content
                    "score": result.get("score", 0.0),  # Relevance score (0.0 to 1.0)
                })
            
            logger.info(f"[OK] Tavily search successful: Found {len(formatted_results)} results")
            
            return {
                "success": True,
                "result": {
                    "query": query,
                    "results": formatted_results,
                    "count": len(formatted_results),
                    "source": "tavily",
                    "answer": answer if answer else None,  # AI-generated answer
                    "search_depth": search_depth,
                },
            }
        
        except Exception as e:
            error_msg = f"Tavily search failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # Check if it's an API key error
            if "api key" in str(e).lower() or "unauthorized" in str(e).lower():
                error_msg = (
                    f"Tavily API authentication failed: {str(e)}. "
                    "Please check your TAVILY_API_KEY. "
                    "Get a free key at: https://app.tavily.com"
                )
            
            return {
                "success": False,
                "error": error_msg,
                "result": {
                    "query": query,
                    "results": [],
                    "count": 0,
                },
            }
