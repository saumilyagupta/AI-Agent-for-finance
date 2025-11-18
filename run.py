"""Simple script to run the FastAPI application."""

import os
import uvicorn
from app.utils.config import settings

if __name__ == "__main__":
    # Get port from environment variable (Render provides this) or default to 8000
    port = int(os.environ.get("PORT", 8000))
    
    # Configure uvicorn with proper settings
    config = uvicorn.Config(
        "app.api.main:app",
        host="0.0.0.0",
        port=port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        access_log=True,
        # Suppress CancelledError on shutdown (it's expected behavior)
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                },
            },
            "handlers": {
                "default": {
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stderr",
                },
            },
            "loggers": {
                "uvicorn": {"handlers": ["default"], "level": "INFO"},
                "uvicorn.error": {"level": "INFO"},
                "uvicorn.access": {"handlers": ["default"], "level": "INFO"},
            },
        },
    )
    server = uvicorn.Server(config)
    server.run()

