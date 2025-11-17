"""Configuration management using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # LLM Providers
    google_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None

    # Search API
    tavily_api_key: Optional[str] = None

    # Weather API
    openweather_api_key: Optional[str] = None

    # Supabase Database
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None
    database_url: Optional[str] = None

    # Application Settings
    secret_key: str = "dev-secret-key-change-in-production"
    debug: bool = True
    log_level: str = "DEBUG"  # Changed to DEBUG for better logging

    # Memory System (Embeddings for semantic search)
    embedding_model: str = "all-MiniLM-L6-v2"

    # LLM Configuration
    primary_llm_provider: str = "openai"  # google or openai (using openai for function calling)
    primary_llm_model: str = "gpt-3.5-turbo"
    fallback_llm_provider: str = "google"
    fallback_llm_model: str = "gemini-2.0-flash-exp"

    # Cost Tracking
    track_costs: bool = True

    # MCP Configuration
    mcp_max_iterations: int = 20
    mcp_server_timeout: int = 30
    browser_mcp_enabled: bool = True
    
    # ReAct Agent Settings
    react_agent_mode: bool = True  # Use ReAct agent instead of planner/executor
    react_temperature: float = 0.7

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Global settings instance
settings = Settings()

