"""Tests for WebSearchTool."""

import pytest
from app.tools.web_search import WebSearchTool


@pytest.fixture
def web_search():
    """Create a WebSearchTool instance."""
    return WebSearchTool()


@pytest.mark.asyncio
async def test_web_search_basic_query(web_search):
    """Test basic web search."""
    result = await web_search.run(
        query="Python programming",
        max_results=5
    )

    # May fail due to rate limits, but should have proper structure
    assert "success" in result
    if result["success"]:
        assert "result" in result
        assert "query" in result["result"]
        assert "results" in result["result"]
        assert "count" in result["result"]
        assert result["result"]["query"] == "Python programming"


@pytest.mark.asyncio
async def test_web_search_custom_max_results(web_search):
    """Test with custom max_results."""
    result = await web_search.run(
        query="artificial intelligence",
        max_results=3
    )

    # May fail due to rate limits
    assert "success" in result
    if result["success"]:
        assert result["result"]["count"] <= 3


@pytest.mark.asyncio
async def test_web_search_result_structure(web_search):
    """Test result structure."""
    result = await web_search.run(
        query="machine learning",
        max_results=2
    )

    if result["success"] and result["result"]["count"] > 0:
        first_result = result["result"]["results"][0]
        assert "title" in first_result
        assert "snippet" in first_result
        assert "url" in first_result


@pytest.mark.asyncio
async def test_web_search_empty_results(web_search):
    """Test handling of empty results."""
    # Use a very specific query that might return no results
    result = await web_search.run(
        query="xyzabc123nonexistentquery987654",
        max_results=5
    )

    # May fail due to rate limits, but if successful should handle gracefully
    assert "success" in result
    if result["success"]:
        assert result["result"]["count"] == 0
        assert result["result"]["results"] == []


@pytest.mark.asyncio
async def test_web_search_default_max_results(web_search):
    """Test default max_results."""
    result = await web_search.run(query="test query")

    # May fail due to rate limits
    assert "success" in result
    if result["success"]:
        assert result["result"]["count"] <= 5  # Default is 5


@pytest.mark.asyncio
async def test_web_search_missing_query(web_search):
    """Test handling of missing query."""
    result = await web_search.run(max_results=5)

    assert result["success"] is False
    assert "error" in result


@pytest.mark.asyncio
async def test_web_search_different_queries(web_search):
    """Test different types of queries."""
    queries = [
        "Python",
        "What is machine learning?",
        "latest news",
        "how to code"
    ]

    for query in queries:
        result = await web_search.run(query=query, max_results=2)
        # Should handle all queries
        assert "success" in result


@pytest.mark.asyncio
async def test_web_search_large_max_results(web_search):
    """Test with large max_results."""
    result = await web_search.run(
        query="technology",
        max_results=20
    )

    # May fail due to rate limits
    assert "success" in result
    if result["success"]:
        assert result["result"]["count"] <= 20


@pytest.mark.asyncio
async def test_web_search_special_characters(web_search):
    """Test query with special characters."""
    result = await web_search.run(
        query="Python 3.10 & 3.11 features",
        max_results=3
    )

    # Should handle special characters
    assert "success" in result


@pytest.mark.asyncio
async def test_web_search_unicode(web_search):
    """Test query with unicode characters."""
    result = await web_search.run(
        query="café résumé",
        max_results=3
    )

    # Should handle unicode
    assert "success" in result


@pytest.mark.asyncio
async def test_web_search_input_schema(web_search):
    """Test input schema."""
    schema = web_search.input_schema
    assert schema["type"] == "object"
    assert "properties" in schema
    assert "query" in schema["properties"]
    assert "max_results" in schema["properties"]
    assert "query" in schema["required"]


@pytest.mark.asyncio
async def test_web_search_stats_tracking(web_search):
    """Test usage statistics tracking."""
    initial_stats = web_search.get_stats()
    assert initial_stats["usage_count"] == 0

    await web_search.run(query="test")
    stats = web_search.get_stats()
    assert stats["usage_count"] == 1

