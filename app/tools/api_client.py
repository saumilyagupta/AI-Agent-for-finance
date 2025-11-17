"""API client and web scraper tool with web search fallback."""

from typing import Any, Dict, Optional
import re

import aiohttp
from bs4 import BeautifulSoup

from app.tools.base import BaseTool
from app.utils.logger import logger


class APIClientTool(BaseTool):
    """Tool for making HTTP requests and scraping web content with web search fallback."""

    def __init__(self):
        super().__init__(
            name="api_client",
            description="Make HTTP requests to APIs or scrape web content. Supports GET and POST requests, JSON parsing, and HTML parsing. Automatically falls back to web search if API key is missing.",
        )
        self._web_search_tool = None  # Lazy load to avoid circular imports

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to request",
                },
                "method": {
                    "type": "string",
                    "description": "HTTP method: 'GET' or 'POST' (default: 'GET')",
                    "enum": ["GET", "POST"],
                    "default": "GET",
                },
                "headers": {
                    "type": "object",
                    "description": "HTTP headers as key-value pairs",
                },
                "data": {
                    "type": "object",
                    "description": "Request body data (for POST requests)",
                },
                "parse_html": {
                    "type": "boolean",
                    "description": "Whether to parse HTML content (default: false)",
                    "default": False,
                },
                "fallback_to_search": {
                    "type": "boolean",
                    "description": "If API fails due to missing API key, automatically use web search (default: true)",
                    "default": True,
                },
                "search_query": {
                    "type": "string",
                    "description": "Optional: Specific search query to use for fallback. If not provided, will extract from URL/context",
                },
            },
            "required": ["url"],
        }
    
    def _get_web_search_tool(self):
        """Lazy load web search tool to avoid circular imports."""
        if self._web_search_tool is None:
            try:
                from app.tools.web_search import WebSearchTool
                self._web_search_tool = WebSearchTool()
                logger.info("Web search fallback initialized")
            except Exception as e:
                logger.warning(f"Could not initialize web search fallback: {e}")
                self._web_search_tool = False  # Mark as unavailable
        return self._web_search_tool if self._web_search_tool is not False else None
    
    def _is_api_key_error(self, status: int, error_text: str = "") -> bool:
        """Check if error is related to missing/invalid API key."""
        # Check HTTP status codes
        if status in [401, 403]:  # Unauthorized, Forbidden
            return True
        
        # Check error text for common API key related messages
        error_keywords = [
            "api key", "api_key", "apikey",
            "unauthorized", "authentication",
            "forbidden", "invalid key",
            "missing key", "access denied",
            "authentication required"
        ]
        
        error_lower = error_text.lower()
        return any(keyword in error_lower for keyword in error_keywords)
    
    def _extract_search_query(self, url: str, data: Optional[Dict] = None) -> str:
        """Extract a meaningful search query from URL and data."""
        # Try to extract meaningful parts from URL
        # Remove protocol and domain
        query_parts = []
        
        # Get path segments (ignoring common API patterns)
        path = re.sub(r'^https?://[^/]+/', '', url)
        path = re.sub(r'[?#].*$', '', path)  # Remove query params and fragments
        
        # Split path and filter out common API terms
        segments = [s for s in path.split('/') if s and not s.startswith('v') and s not in ['api', 'rest']]
        
        # Clean up segments (replace underscores, hyphens with spaces)
        cleaned_segments = [re.sub(r'[_-]', ' ', seg) for seg in segments[:3]]  # Take first 3 meaningful segments
        query_parts.extend(cleaned_segments)
        
        # Add data keys if available (but not values for privacy)
        if data and isinstance(data, dict):
            query_parts.extend(list(data.keys())[:2])
        
        query = ' '.join(query_parts)
        
        # If query is too short or unclear, make it more generic
        if len(query) < 10:
            query = f"information about {query}" if query else "API information"
        
        return query

    async def execute(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None,
        parse_html: bool = False,
        fallback_to_search: bool = True,
        search_query: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute API request or web scraping with automatic web search fallback."""
        try:
            # Check for placeholder values
            if url and (url.upper() == "PLACEHOLDER" or url.startswith("PLACEHOLDER")):
                return {
                    "success": False,
                    "error": "URL contains placeholder value. This task likely depends on a previous task that failed.",
                    "result": None,
                }
            
            logger.info(f"Making {method} request to: {url}")

            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                if method == "GET":
                    async with session.get(url, headers=headers) as response:
                        status = response.status
                        content_type = response.headers.get("Content-Type", "")

                        if "application/json" in content_type:
                            result_data = await response.json()
                        else:
                            text = await response.text()
                            if parse_html:
                                soup = BeautifulSoup(text, "html.parser")
                                # Extract main content
                                result_data = {
                                    "title": soup.title.string if soup.title else None,
                                    "text": soup.get_text(separator=" ", strip=True)[:5000],
                                    "links": [a.get("href") for a in soup.find_all("a", href=True)][:20],
                                }
                            else:
                                result_data = {"text": text[:10000]}

                elif method == "POST":
                    async with session.post(url, headers=headers, json=data) as response:
                        status = response.status
                        content_type = response.headers.get("Content-Type", "")

                        if "application/json" in content_type:
                            result_data = await response.json()
                        else:
                            result_data = {"text": await response.text()[:10000]}

                else:
                    return {
                        "success": False,
                        "error": f"Unsupported HTTP method: {method}",
                        "result": None,
                    }

                # Check if this is an API key error
                is_api_key_error = False
                error_msg = None
                
                if status >= 400:
                    error_msg = f"HTTP {status}"
                    error_text = str(result_data) if isinstance(result_data, dict) else ""
                    is_api_key_error = self._is_api_key_error(status, error_text)
                
                # If API key error and fallback enabled, try web search
                if is_api_key_error and fallback_to_search:
                    logger.warning(f"API key error detected (HTTP {status}). Attempting web search fallback...")
                    
                    # Get or create search query
                    if not search_query:
                        search_query = self._extract_search_query(url, data)
                    
                    logger.info(f"Using web search query: {search_query}")
                    
                    # Try web search
                    web_search_tool = self._get_web_search_tool()
                    if web_search_tool:
                        try:
                            search_result = await web_search_tool.execute(
                                query=search_query,
                                max_results=5
                            )
                            
                            if search_result.get("success"):
                                logger.info("Web search fallback successful!")
                                return {
                                    "success": True,
                                    "result": {
                                        "url": url,
                                        "method": "WEB_SEARCH_FALLBACK",
                                        "original_error": error_msg,
                                        "fallback_used": True,
                                        "search_query": search_query,
                                        "data": search_result["result"],
                                    },
                                    "error": None,
                                    "warning": f"Original API call failed ({error_msg}). Used web search fallback instead.",
                                }
                            else:
                                logger.warning(f"Web search fallback also failed: {search_result.get('error')}")
                        except Exception as search_error:
                            logger.error(f"Web search fallback failed: {search_error}")
                    else:
                        logger.warning("Web search tool not available for fallback")
                
                # Return original API response (if no fallback or fallback failed)
                return {
                    "success": status < 400,
                    "result": {
                        "url": url,
                        "method": method,
                        "status": status,
                        "data": result_data,
                    },
                    "error": error_msg,
                }

        except Exception as e:
            logger.error(f"API request failed: {e}")
            error_str = str(e)
            
            # Check if exception is API key related
            is_api_key_error = self._is_api_key_error(0, error_str)
            
            # Try web search fallback for API key errors
            if is_api_key_error and fallback_to_search:
                logger.warning(f"API request failed with authentication error. Attempting web search fallback...")
                
                if not search_query:
                    search_query = self._extract_search_query(url, data)
                
                logger.info(f"Using web search query: {search_query}")
                
                web_search_tool = self._get_web_search_tool()
                if web_search_tool:
                    try:
                        search_result = await web_search_tool.execute(
                            query=search_query,
                            max_results=5
                        )
                        
                        if search_result.get("success"):
                            logger.info("Web search fallback successful!")
                            return {
                                "success": True,
                                "result": {
                                    "url": url,
                                    "method": "WEB_SEARCH_FALLBACK",
                                    "original_error": error_str,
                                    "fallback_used": True,
                                    "search_query": search_query,
                                    "data": search_result["result"],
                                },
                                "error": None,
                                "warning": f"Original API call failed ({error_str}). Used web search fallback instead.",
                            }
                    except Exception as search_error:
                        logger.error(f"Web search fallback failed: {search_error}")
            
            return {
                "success": False,
                "error": f"Request failed: {error_str}",
                "result": None,
            }

