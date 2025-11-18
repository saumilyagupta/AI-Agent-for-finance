"""Simple script to run the FastAPI application."""

import os
import uvicorn
from app.utils.config import settings

if __name__ == "__main__":
    # Get port from environment variable (Render provides this) or default to 8000
    port = int(os.environ.get("PORT", 8000))
    
    # Use uvicorn.run() directly for better compatibility with Render
    # This ensures the port is properly bound and detected
    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        access_log=True,
    )

