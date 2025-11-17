"""Tests for APIClientTool."""

import pytest
from app.tools.api_client import APIClientTool


@pytest.fixture
def api_client():
    """Create an APIClientTool instance."""
    return APIClientTool()


@pytest.mark.asyncio
async def test_api_client_get_request(api_client):
    """Test GET request to a public API."""
    result = await api_client.run(
        url="https://httpbin.org/get",
        method="GET"
    )

    assert result["success"] is True
    assert result["result"]["status"] == 200
    assert result["result"]["method"] == "GET"
    assert "data" in result["result"]


@pytest.mark.asyncio
async def test_api_client_post_request(api_client):
    """Test POST request to a public API."""
    test_data = {"key": "value", "number": 123}
    result = await api_client.run(
        url="https://httpbin.org/post",
        method="POST",
        data=test_data
    )

    assert result["success"] is True
    assert result["result"]["status"] == 200
    assert result["result"]["method"] == "POST"


@pytest.mark.asyncio
async def test_api_client_with_headers(api_client):
    """Test request with custom headers."""
    headers = {"User-Agent": "Test-Agent", "Accept": "application/json"}
    result = await api_client.run(
        url="https://httpbin.org/headers",
        method="GET",
        headers=headers
    )

    assert result["success"] is True
    assert result["result"]["status"] == 200


@pytest.mark.asyncio
async def test_api_client_parse_html(api_client):
    """Test HTML parsing."""
    result = await api_client.run(
        url="https://httpbin.org/html",
        method="GET",
        parse_html=True
    )

    assert result["success"] is True
    if "data" in result["result"]:
        data = result["result"]["data"]
        if isinstance(data, dict):
            # HTML parsing should extract title, text, links
            assert "text" in data or "title" in data


@pytest.mark.asyncio
async def test_api_client_invalid_url(api_client):
    """Test handling of invalid URL."""
    result = await api_client.run(
        url="https://invalid-url-that-does-not-exist-12345.com",
        method="GET"
    )

    # Should handle error gracefully
    assert "success" in result


@pytest.mark.asyncio
async def test_api_client_invalid_method(api_client):
    """Test handling of invalid HTTP method."""
    result = await api_client.run(
        url="https://httpbin.org/get",
        method="INVALID"
    )

    assert result["success"] is False
    assert "error" in result


@pytest.mark.asyncio
async def test_api_client_missing_url(api_client):
    """Test handling of missing URL."""
    result = await api_client.run(method="GET")

    assert result["success"] is False
    assert "error" in result


@pytest.mark.asyncio
async def test_api_client_default_method(api_client):
    """Test default GET method."""
    result = await api_client.run(url="https://httpbin.org/get")

    assert result["success"] is True
    assert result["result"]["method"] == "GET"


@pytest.mark.asyncio
async def test_api_client_json_response(api_client):
    """Test JSON response handling."""
    result = await api_client.run(url="https://httpbin.org/json")

    assert result["success"] is True
    assert result["result"]["status"] == 200
    assert "data" in result["result"]


@pytest.mark.asyncio
async def test_api_client_input_schema(api_client):
    """Test input schema."""
    schema = api_client.input_schema
    assert schema["type"] == "object"
    assert "properties" in schema
    assert "url" in schema["properties"]
    assert "method" in schema["properties"]
    assert "headers" in schema["properties"]
    assert "url" in schema["required"]


@pytest.mark.asyncio
async def test_api_client_stats_tracking(api_client):
    """Test usage statistics tracking."""
    initial_stats = api_client.get_stats()
    assert initial_stats["usage_count"] == 0

    await api_client.run(url="https://httpbin.org/get")
    stats = api_client.get_stats()
    assert stats["usage_count"] == 1










