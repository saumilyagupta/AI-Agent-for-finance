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
    
    # Use uvicorn.run() directly for better compatibility with Render
    # According to Render docs: Bind host to 0.0.0.0 and use PORT env var
    # This ensures the port is properly bound and detected by Render's port scanner
    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",  # Required by Render - bind to all interfaces
        port=port,  # Use PORT env var (Render sets this)
        reload=reload_enabled,  # Disable reload in production for Render
        log_level=settings.log_level.lower(),
        access_log=True,
        loop="asyncio",
    )

