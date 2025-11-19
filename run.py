"""Simple script to run the FastAPI application."""

import os
import uvicorn
from app.utils.config import settings

if __name__ == "__main__":
    # Get port from environment variable (Render provides this) or default to 8000
    # Render's default port is 10000, but it sets PORT env var
    port = int(os.environ.get("PORT", 8000))
    
    # Log port immediately for Render port scanner
    print(f"Starting server on 0.0.0.0:{port}", flush=True)
    print(f"PORT environment variable: {os.environ.get('PORT', 'not set')}", flush=True)
    
    # Disable reload in production (Render) - reload causes port detection issues
    # Render sets PORT env var, so if PORT is set, we're in production
    is_production = "PORT" in os.environ
    reload_enabled = settings.debug and not is_production
    
    if is_production:
        print("Running in production mode (Render) - reload disabled", flush=True)
    
    # ALWAYS use string format to allow uvicorn to bind port before importing app
    # This is critical for Render's port scanner to detect the port immediately
    # When using string format, uvicorn:
    # 1. Starts the server and binds to port (fast)
    # 2. Then imports the app (slower, includes LLM initialization)
    # This ensures Render detects the port before heavy initialization
    app_instance = "app.api.main:app"
    
    # Use uvicorn.run() with string format for immediate port binding
    # According to Render docs: Bind host to 0.0.0.0 and use PORT env var
    uvicorn.run(
        app_instance,  # String format for delayed import
        host="0.0.0.0",  # Required by Render - bind to all interfaces
        port=port,  # Use PORT env var (Render sets this)
        reload=reload_enabled,  # Disable reload in production for Render
        log_level=settings.log_level.lower(),
        access_log=True,
        loop="asyncio",
    )

