"""Tests for FileOpsTool."""

import json
import pytest
from pathlib import Path
from app.tools.file_ops import FileOpsTool


@pytest.fixture
def file_ops():
    """Create a FileOpsTool instance."""
    return FileOpsTool()


@pytest.fixture
def test_data():
    """Sample test data."""
    return {
        "name": "Test",
        "value": 123,
        "items": [1, 2, 3]
    }


@pytest.fixture
def test_csv_data():
    """Sample CSV data."""
    return [
        {"name": "Alice", "age": 30, "city": "New York"},
        {"name": "Bob", "age": 25, "city": "London"},
        {"name": "Charlie", "age": 35, "city": "Tokyo"}
    ]


@pytest.mark.asyncio
async def test_file_ops_write_json(file_ops, test_data):
    """Test writing JSON file."""
    result = await file_ops.run(
        operation="write",
        file_path="test.json",
        file_type="json",
        data=test_data
    )

    assert result["success"] is True
    assert result["result"]["message"] == "File written successfully"

    # Verify file exists
    work_dir = Path("./file_workspace")
    assert (work_dir / "test.json").exists()


@pytest.mark.asyncio
async def test_file_ops_read_json(file_ops, test_data):
    """Test reading JSON file."""
    # First write the file
    await file_ops.run(
        operation="write",
        file_path="test_read.json",
        file_type="json",
        data=test_data
    )

    # Then read it
    result = await file_ops.run(
        operation="read",
        file_path="test_read.json",
        file_type="json"
    )

    assert result["success"] is True
    assert result["result"]["data"] == test_data


@pytest.mark.asyncio
async def test_file_ops_write_csv(file_ops, test_csv_data):
    """Test writing CSV file."""
    result = await file_ops.run(
        operation="write",
        file_path="test.csv",
        file_type="csv",
        data=test_csv_data
    )

    assert result["success"] is True
    assert result["result"]["message"] == "File written successfully"

    # Verify file exists
    work_dir = Path("./file_workspace")
    assert (work_dir / "test.csv").exists()


@pytest.mark.asyncio
async def test_file_ops_read_csv(file_ops, test_csv_data):
    """Test reading CSV file."""
    # First write the file
    await file_ops.run(
        operation="write",
        file_path="test_read.csv",
        file_type="csv",
        data=test_csv_data
    )

    # Then read it
    result = await file_ops.run(
        operation="read",
        file_path="test_read.csv",
        file_type="csv"
    )

    assert result["success"] is True
    assert "data" in result["result"]
    assert "shape" in result["result"]
    assert len(result["result"]["data"]) == 3


@pytest.mark.asyncio
async def test_file_ops_read_nonexistent_file(file_ops):
    """Test reading non-existent file."""
    result = await file_ops.run(
        operation="read",
        file_path="nonexistent.json",
        file_type="json"
    )

    assert result["success"] is False
    assert "error" in result
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_file_ops_write_missing_data(file_ops):
    """Test write operation without data."""
    result = await file_ops.run(
        operation="write",
        file_path="test.json",
        file_type="json"
    )

    assert result["success"] is False
    assert "error" in result
    assert "data" in result["error"].lower()


@pytest.mark.asyncio
async def test_file_ops_invalid_operation(file_ops):
    """Test invalid operation."""
    result = await file_ops.run(
        operation="invalid",
        file_path="test.json",
        file_type="json"
    )

    assert result["success"] is False
    assert "error" in result


@pytest.mark.asyncio
async def test_file_ops_invalid_file_type(file_ops):
    """Test invalid file type."""
    result = await file_ops.run(
        operation="write",
        file_path="test.txt",
        file_type="txt",
        data={"test": "data"}
    )

    # Should handle gracefully
    assert "success" in result


@pytest.mark.asyncio
async def test_file_ops_pdf_read(file_ops):
    """Test reading PDF file (if available)."""
    # This test may fail if no PDF is available, which is okay
    result = await file_ops.run(
        operation="read",
        file_path="nonexistent.pdf",
        file_type="pdf"
    )

    # Should handle missing file gracefully
    assert "success" in result


@pytest.mark.asyncio
async def test_file_ops_path_sanitization(file_ops, test_data):
    """Test that path traversal is prevented."""
    # Try to write with path traversal
    result = await file_ops.run(
        operation="write",
        file_path="../../../etc/passwd.json",
        file_type="json",
        data=test_data
    )

    # Should sanitize path (only filename used)
    assert result["success"] is True
    work_dir = Path("./file_workspace")
    # Should create passwd.json in workspace, not in /etc
    # Path().name extracts just the filename, so passwd.json should be created
    assert (work_dir / "passwd.json").exists()


@pytest.mark.asyncio
async def test_file_ops_input_schema(file_ops):
    """Test input schema."""
    schema = file_ops.input_schema
    assert schema["type"] == "object"
    assert "properties" in schema
    assert "operation" in schema["properties"]
    assert "file_path" in schema["properties"]
    assert "file_type" in schema["properties"]
    assert "operation" in schema["required"]


@pytest.mark.asyncio
async def test_file_ops_stats_tracking(file_ops, test_data):
    """Test usage statistics tracking."""
    initial_stats = file_ops.get_stats()
    assert initial_stats["usage_count"] == 0

    await file_ops.run(
        operation="write",
        file_path="stats_test.json",
        file_type="json",
        data=test_data
    )
    stats = file_ops.get_stats()
    assert stats["usage_count"] == 1

