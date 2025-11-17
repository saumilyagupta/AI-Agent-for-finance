# General-purpose AI Agent

An LLM-powered planning and execution platform focused on financial and market intelligence. The General-purpose AI Agent decomposes a plain-English goal into a dependency-aware DAG, executes tasks with a curated toolset (web search, code execution, stock data, charting, etc.), and streams structured progress plus insights back to humans or downstream systems.

## Why use it?

- **Portfolio-grade stock analysis**: Fetch historical OHLCV data, compute indicators, simulate trade strategies, and summarize catalysts in one run.
- **Composed workflows**: Blend research, calculations, API calls, visualizations, and file operations in a single orchestrated plan.
- **Always-on context**: Retain execution history and semantic memory so follow-up questions reuse prior results.
- **Production-ready surface**: Async FastAPI backend, WebSocket streaming, Supabase/SQLite persistence, and HTML test harnesses for rapid demos.

## Capability Map

| Domain | What the agent can do | Backing tool(s) |
| --- | --- | --- |
| Market intelligence | Fetch quotes, fundamentals, institutional ownership, SEC fillings, and sector stats | `app/tools/stock_market.py`, `app/tools/stock_analysis.py`, `app/tools/stock_calculator.py` |
| Quant analytics | Run Python snippets, compute indicators, risk metrics, CAGR, Sharpe, rolling correlations | `app/tools/code_executor.py`, `app/tools/calculator.py` |
| Research | Search the public web, summarize news, cross-check sources | `app/tools/web_search.py`, `app/tools/api_client.py` |
| Data handling | Load/save CSV/JSON, clean tables, export summaries | `app/tools/file_ops.py`, `app/tools/visualizer.py` |
| Ops & automation | Maintain execution ledger, review stats, audit health | `app/api/routes/history.py`, `app/api/routes/stats.py`, `app/api/routes/health.py` |

## System Overview

```
User/UI → FastAPI (`app/api/main.py`)
          → Planner (`app/core/planner.py`)
          → Executor (`app/core/executor.py`)
             ↺ LLM providers (`app/core/llm_provider.py`)
             ↺ Memory (`app/core/memory.py`, Supabase/SQLite via `app/database/`)
             ↺ Tool registry (`app/tools/registry.py` + concrete tools)
          → WebSocket stream + DB persistence + stats service
```

- **ReAct-style agent loop** (`app/core/react_agent.py` & `react_agent_direct.py`) keeps reasoning traces for transparency.
- **Task graph**: Each goal becomes structured `ExecutionPlan`/`Task` models (`app/core/models.py`), enabling parallel groups.
- **MCP bridge**: `app/mcp/servers/*` exposes local capabilities (file, code, browser, stock data) through the Model Context Protocol so different LLMs can call them safely.

## Getting Started

### 1. Install prerequisites

- Python ≥ 3.11
- `uv` (recommended) or bare `pip`

```bash
pip install uv
uv venv
.venv\Scripts\activate  # or source .venv/bin/activate
uv pip install -r requirements.txt
```

### 2. Configure environment

Create `.env` in the project root:

```env
GOOGLE_API_KEY=your_google_gemini_key_here
OPENAI_API_KEY=your_openai_key_here

SUPABASE_URL=...
SUPABASE_KEY=...
# DATABASE_URL=postgresql://...
# or use SQLite:
# DATABASE_URL=sqlite:///./agent.db

SECRET_KEY=change_me
DEBUG=true
LOG_LEVEL=INFO

PRIMARY_LLM_PROVIDER=google
PRIMARY_LLM_MODEL=gemini-2.0-flash-exp
FALLBACK_LLM_PROVIDER=openai
FALLBACK_LLM_MODEL=gpt-3.5-turbo
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

### 3. Prep the database

```bash
alembic upgrade head
# or
python -c "from app.database.database import init_db; init_db()"
```

### 4. Launch services

```bash
uvicorn app.api.main:app --reload --port 8000
```

Visit:
- Test console: `http://localhost:8000/static/index.html`
- Swagger docs: `http://localhost:8000/api/v1/docs`
- Health: `http://localhost:8000/api/v1/health`

## Stock-Market-first Workflows

### 1. Performance vs benchmark
Goal: “Compare NVIDIA and AMD YTD performance, chart drawdowns, and explain current catalysts.”

Execution:
1. Stock-market tool fetches price history (`yfinance` backend).
2. Stock-calculator tool computes returns, CAGR, max drawdown.
3. Web-search tool summarizes catalysts.
4. Visualizer tool renders Plotly chart saved to `static/`.

### 2. Screener + signal validation
Goal: “Find 3 undervalued fintech stocks with RSI < 30 and check their last earnings call sentiment.”

Execution:
1. File/API tools ingest screener data.
2. Calculator filters and computes RSI.
3. Web search pulls transcript summaries.
4. Memory stores insights for future prompts.

### 3. Automated research memo
Goal: “Write a memo on Tesla including trailing 5y revenue CAGR, technical trend, and macro headwinds.”

Execution:
1. Planner composes workflow (fundamentals → technicals → macro).
2. Executor invokes stock-analysis, calculator, and weather/web tools.
3. Result is persisted to history (+ downloadable CSV/JSON via file ops).

## API Surface

- `POST /api/v1/goals`: submit a natural-language objective.
- `WS /api/v1/goals/{id}/stream`: subscribe to task-by-task updates.
- `GET /api/v1/goals/{id}` + `/details`: poll status and artifacts.
- `GET /api/v1/history`, `/history/search`: review or semantically query past runs.
- `GET /api/v1/stats/*`: usage, tool mix, cost tracking.
- `GET /api/v1/health/*`: infra diagnostics (DB, LLMs, MCP servers).

The OpenAPI schema is auto-generated; import into Postman or your favorite SDK for scripted control.

## Development & Testing

- **Unit tests**: `pytest tests/`
- **Static analysis**: `ruff check app/`
- **Formatting**: `black app/ tests/`
- **Migrations**: `alembic revision --autogenerate -m "message"`

During iterative tool development, run the lightweight static demo pages under `static/` to validate streaming behavior without a frontend build system.

## Deployment

### Docker
```bash
docker build -t general-purpose-ai-agent .
docker run -p 8000:8000 --env-file .env general-purpose-ai-agent
```

### Cloud options
- Render/Railway/Fly.io for managed FastAPI hosting.
- Supabase or Neon for Postgres.
- Attach object storage (S3, R2) if you need long-lived artifacts or charts.

## Roadmap

- [ ] Rich React dashboard with DAG visualization.
- [ ] Multi-provider data adapters (Polygon, Alpha Vantage, Tiingo).
- [ ] Portfolio backtesting module and trade order simulation.
- [ ] Advanced memory (vector DB) + retrieval-augmented planning.
- [ ] Role-based auth and organization-level usage analytics.

## License & Contributions

MIT License. Issues and PRs are welcome—please describe the scenario, inputs, and observed outputs so we can reproduce financial workflows quickly.




