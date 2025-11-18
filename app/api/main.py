"""FastAPI application main entry point."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import goals, health, history, stats
from app.database.database import init_db
from app.utils.config import settings
from app.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for startup and shutdown."""
    # Startup - Non-blocking initialization for Render compatibility
    # Render requires the server to start listening immediately
    logger.info("Starting Autonomous AI Agent System...")
    
    # Initialize database (non-blocking - won't prevent server from starting)
    # Database will fall back to SQLite if connection fails
    try:
        init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning(f"Database initialization had issues (will use fallback): {e}")
        # Don't raise - allow server to start even if DB init has issues
        # This ensures Render can detect the port immediately
    
    # Tools are now accessed directly from registry (no MCP servers needed)
    logger.info("Tools ready from registry (direct access, no MCP overhead)")
    logger.info("Application startup complete ✓ - Server is ready to accept connections")

    try:
        yield
    except Exception as e:
        logger.error(f"Error during application lifetime: {e}")
    finally:
        # Shutdown
        logger.info("Shutting down gracefully...")
        # Add any cleanup here if needed
        logger.info("Shutdown complete ✓")


# Create FastAPI app
app = FastAPI(
    title="Autonomous AI Agent API",
    description="API for autonomous AI agent system with task planning and execution",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers (MUST be before static files mount)
app.include_router(goals.router, prefix="/api/v1")
app.include_router(history.router, prefix="/api/v1")
app.include_router(stats.router, prefix="/api/v1")
app.include_router(health.router, prefix="/api/v1")

# Add WebSocket route at /ws for easier access (in addition to /api/v1/goals/.../stream)
from uuid import UUID
from fastapi import WebSocket, WebSocketDisconnect
from app.database.crud import get_execution, update_execution
from app.database.database import get_db
from app.core.agent import agent

@app.websocket("/ws/execute/{execution_id}")
async def websocket_execute(websocket: WebSocket, execution_id: UUID):
    """WebSocket endpoint for real-time execution streaming."""
    await websocket.accept()
    logger.info(f"WebSocket connection opened for execution {execution_id}")

    try:
        # Get execution goal
        db = next(get_db())
        execution = get_execution(db, execution_id)
        if not execution:
            await websocket.send_json({"error": "Execution not found"})
            await websocket.close()
            return

        # Start execution if not already started
        if execution.status == "pending":
            # Update status to running
            update_execution(db, execution_id, status="running")
            
            # Execute goal and stream events
            async for event in agent.execute_goal(execution.goal, execution_id=execution_id):
                event_dict = event.dict()
                event_dict["execution_id"] = str(execution_id)
                await websocket.send_json(event_dict)

                # Close connection if execution completed or failed
                if event.type in ["execution_completed", "execution_failed"]:
                    break

        else:
            # Execution already in progress or completed
            await websocket.send_json({
                "type": "status",
                "message": f"Execution status: {execution.status}",
                "execution_id": str(execution_id),
            })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for execution {execution_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({"error": str(e), "type": "error"})
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass

# Root endpoint
@app.get("/api")
async def api_root():
    """API root endpoint."""
    return {"message": "Autonomous AI Agent API", "version": "0.1.0"}

# Mount static files LAST (so they don't catch WebSocket routes)
static_dir = Path(__file__).parent.parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Redirect root to chat interface
from fastapi.responses import RedirectResponse

@app.get("/")
async def root():
    """Redirect root to chat interface."""
    return RedirectResponse(url="/static/chat.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )

