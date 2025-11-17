# Test Suite for AI Agent Tools

This directory contains comprehensive tests for all tools in the AI agent system.

## Test Files

### Core Tests
- **test_basic.py** - Integration tests and basic system tests
- **test_base_and_registry.py** - Tests for BaseTool class and ToolRegistry

### Tool Tests
- **test_calculator.py** - Tests for CalculatorTool (math operations, statistics)
- **test_code_executor.py** - Tests for CodeExecutorTool (Python code execution)
- **test_api_client.py** - Tests for APIClientTool (HTTP requests, web scraping)
- **test_file_ops.py** - Tests for FileOpsTool (file read/write operations)
- **test_stock_calculator.py** - Tests for StockCalculatorTool (technical indicators)
- **test_stock_market.py** - Tests for StockMarketTool (stock data fetching)
- **test_visualizer.py** - Tests for VisualizerTool (chart generation)
- **test_web_search.py** - Tests for WebSearchTool (web search functionality)

## Running Tests

### Run all tests
```bash
pytest
```

### Run specific test file
```bash
pytest tests/test_calculator.py
```

### Run specific test
```bash
pytest tests/test_calculator.py::test_calculator_basic_arithmetic
```

### Run with coverage
```bash
pytest --cov=app --cov-report=html
```

### Run in verbose mode
```bash
pytest -v
```

## Test Coverage

Each tool test file includes:
- ✅ Basic functionality tests
- ✅ Edge case handling
- ✅ Error handling
- ✅ Input validation
- ✅ Schema validation
- ✅ Statistics tracking
- ✅ Integration with BaseTool

## Notes

- All async tests use `@pytest.mark.asyncio`
- Tests use fixtures for tool instances
- Some tests may require network access (web_search, api_client, stock_market)
- File operations use a safe workspace directory (`./file_workspace`)









