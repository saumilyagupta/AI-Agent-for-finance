# General-purpose AI Agent – Technical Documentation

> This document complements `README.md` by diving deeper into architecture, configuration, and market-analysis workflows. Treat it as the internal guide for maintainers and contributors.

---

## 1. Product Narrative

- **Mission**: Provide a reusable AI co-worker that can research, analyze, and report on any quantitative or qualitative task with a special focus on capital markets.
- **Primary users**: Financial analysts, founders building AI copilots, and operations teams who need autonomous workflows instead of prompt-by-prompt chat.
- **Differentiators**:
  - Stock-market aware from day one (dedicated tools, indicators, visualization, calculator).
  - Model Context Protocol (MCP) servers that expose deterministic capabilities (file system, browser, API clients, calculators) to any LLM.
  - Streaming-first UX so both humans and headless clients see real-time DAG execution.

---

## 2. Key Components

| Area           | Modules                                                                                       | Notes                                                                                                                         |
| -------------- | --------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| API surface    | `app/api/main.py`, `app/api/routes/*`, `app/api/schemas.py`                                   | FastAPI router per domain (goals, history, stats, health).                                                                    |
| Agent brain    | `app/core/agent.py`, `planner.py`, `executor.py`, `models.py`, `memory.py`, `llm_provider.py` | Planner emits DAGs, executor runs dependency levels in parallel, memory stores embeddings/results in Supabase/SQLite.         |
| Tools & MCP    | `app/tools/*`, `app/mcp/*`                                                                    | Registry auto-loads tools; MCP servers wrap file ops, browser automation, calculators, and stock utilities for cross-LLM use. |
| Persistence    | `app/database/*`, `alembic/`, `agent.db`                                                      | SQLAlchemy models + migrations; default SQLite for local dev.                                                                 |
| Frontend stubs | `static/*.html`, `static/*.js`, `static/chat.css`                                             | Lightweight diagnostic UI to test streams and visualize history/stats.                                                        |

---

## 3. Data & Control Flow

1. **Goal submission** (`POST /api/v1/goals`):
   - Payload validated via `ExecutionRequest` schema.
   - Planner builds `ExecutionPlan` referencing registered tools.
   - Plan stored in DB + pushed to WebSocket stream.
2. **Execution**:
   - Executor groups tasks by dependency depth (topological sort).
   - Worker fan-out calls specific tool classes (async) and records outputs.
   - Failures trigger retries (tenacity) and circuit breakers per tool.
3. **Memory & History**:
   - Results, logs, artifacts saved through `app/database/crud.py`.
   - Embedding writer (`memory.py`) pushes summaries into Supabase (or local vector fallback) for semantic search endpoints.
4. **Observability**:
   - Stats service aggregates run counts, tool usage, LLM spend proxies.
   - Health routes ping DB, LLM providers, and MCP servers for readiness.

---

## 4. Tool Reference

| Tool                | Path                            | Typical Inputs                | Outputs                                                     |
| ------------------- | ------------------------------- | ----------------------------- | ----------------------------------------------------------- |
| WebSearchTool       | `app/tools/web_search.py`       | query, max_results            | Ranked snippets with source URLs.                           |
| CalculatorTool      | `app/tools/calculator.py`       | expression, data frame        | Scalar result or transformed dataset.                       |
| ApiClientTool       | `app/tools/api_client.py`       | method, url, headers, payload | Raw JSON response.                                          |
| FileOpsTool         | `app/tools/file_ops.py`         | path, mode, format            | File contents or write confirmation.                        |
| CodeExecutorTool    | `app/tools/code_executor.py`    | python code, timeout          | Captured stdout/stderr, return value.                       |
| StockMarketTool     | `app/tools/stock_market.py`     | ticker(s), interval, range    | Price series from yfinance.                                 |
| StockCalculatorTool | `app/tools/stock_calculator.py` | OHLCV frame, indicator config | Indicators (RSI, EMA, MACD, CAGR, drawdown).                |
| StockAnalysisTool   | `app/tools/stock_analysis.py`   | combined config               | Higher-level research summary (news, catalysts, valuation). |
| VisualizerTool      | `app/tools/visualizer.py`       | data frame, chart spec        | Plotly figure saved to static asset.                        |

Each tool inherits from `BaseTool` and registers itself through `app/tools/registry.py`, ensuring planner prompts can reference canonical names.

---

## 5. Stock Market Workflows (Deep Dive)

### 5.1 Comparative Return Study

- **Input**: “Benchmark NVDA vs QQQ over 6 months; include max drawdown and a scatter of daily returns.”
- **Plan nodes**:
  1. Fetch price history (StockMarketTool).
  2. Compute pct change, drawdown, beta (StockCalculatorTool).
  3. Generate comparison chart (VisualizerTool).
  4. Summarize catalysts (WebSearchTool + ApiClientTool).
- **Artifacts**: CSV export saved through FileOpsTool and chart accessible at `/static/test_plotly.html`.

### 5.2 Earnings Prep Packet

- Pulls latest price, analyst consensus (via ApiClientTool), calculates implied move (calculator), and formats bullet memo with CodeExecutorTool for custom Python summarization.

### 5.3 Risk Monitoring

- Scheduler (future roadmap) could enqueue daily goals; until then, trigger manually via `POST /api/v1/goals` with templates saved in your client code.

---

## 6. Configuration Cheat Sheet

| Variable                          | Description                                                                       |
| --------------------------------- | --------------------------------------------------------------------------------- |
| `PRIMARY_LLM_PROVIDER` / `_MODEL` | `google` + `gemini-2.0-flash-exp` recommended for cost/speed; fallback to OpenAI. |
| `SUPABASE_URL` / `SUPABASE_KEY`   | Needed for persistent memory and history search. Leave unset to stay local.       |
| `DATABASE_URL`                    | Postgres connection string. Defaults to SQLite `agent.db` when omitted.           |
| `EMBEDDING_MODEL`                 | Any sentence-transformers model accessible via `sentence_transformers`.           |
| `STOCK_DATA_PROVIDER` (optional)  | Future toggle when multiple providers are added.                                  |

Set these values in `.env` and ensure your process loads them via `python-dotenv` (already wired in `app/utils/config.py`).

---

## 7. MCP Servers

The `app/mcp/servers` directory exposes deterministic functions to LLMs via the Model Context Protocol:

- `browser_server.py`: headless browser control for scraping dashboards.
- `file_ops_server.py`: restricted read/write operations to the workspace.
- `code_executor_server.py`: sandboxed Python runner (mirrors CodeExecutorTool).
- `stock_market_server.py`, `stock_analysis_server.py`, `stock_calculator_server.py`: specialized finance endpoints.
- `visualizer_server.py`: create charts and return URLs.

Use `app/mcp/server_manager.py` to bootstrap servers and feed their schemas into your preferred LLM runtime.

---

## 8. Deployment Topology

1. **Backend**: Containerize with the provided `Dockerfile`. Publish image to GHCR/ECR and run with environment variables supplied through your platform.
2. **Database**: Use managed Postgres (Supabase, Neon, RDS). Run `alembic upgrade head` on deploy.
3. **Static assets**: Served directly by FastAPI under `/static`. For custom frontends, point them at the same API base.
4. **Secrets**: Use platform-specific secret managers; never commit `.env`.

---

## 9. Troubleshooting

| Symptom                                     | Likely Cause                                                     | Fix                                                                                              |
| ------------------------------------------- | ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `LLM provider unavailable` in `/health/llm` | Missing API key or wrong model name                              | Confirm `.env`, restart service.                                                                 |
| Tasks stuck in `pending`                    | Planner produced unreachable nodes (bad dependency)              | Inspect execution via `/history/{id}`; adjust planner prompt templates in `app/core/planner.py`. |
| Stock data empty                            | Market closed or ticker invalid                                  | Validate ticker; ensure yfinance dependency up to date.                                          |
| WebSocket closes immediately                | Browser blocked mixed content when using HTTPS over HTTP backend | Match schemes or use a tunnel (ngrok, Cloudflare).                                               |

---

## 10. Contribution Checklist

- Add/modify tests under `tests/`.
- Run `ruff`, `black`, and `pytest`.
- Update README/docs when surfacing new capabilities or environment variables.
- Submit PR with a clear description plus example goal/output.

---

## 11. Glossary

- **Goal**: User-specified objective captured via API/UI.
- **ExecutionPlan**: Structured DAG produced by planner describing tasks, dependencies, and target tools.
- **Task Level**: All tasks without unmet dependencies can run concurrently.
- **Artifact**: Files, charts, or JSON blobs created during execution and stored in `/file_workspace` or `/static`.

Happy building! Reach out via issues/PRs if you extend the toolset or integrate new data providers.\*\*\* End Patch
