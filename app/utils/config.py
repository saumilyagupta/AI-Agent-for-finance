"""Configuration management using Pydantic Settings."""

import os
import secrets
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # LLM Providers - loaded from .env via os.environ
    google_api_key: Optional[str] = Field(
        default_factory=lambda: os.environ.get("GOOGLE_API_KEY"),
        description="Google Gemini API key from GOOGLE_API_KEY env var"
    )
    openai_api_key: Optional[str] = Field(
        default_factory=lambda: os.environ.get("OPENAI_API_KEY"),
        description="OpenAI API key from OPENAI_API_KEY env var"
    )

    # Search API - loaded from .env via os.environ
    tavily_api_key: Optional[str] = Field(
        default_factory=lambda: os.environ.get("TAVILY_API_KEY"),
        description="Tavily search API key from TAVILY_API_KEY env var"
    )

    # Weather API - loaded from .env via os.environ
    openweather_api_key: Optional[str] = Field(
        default_factory=lambda: os.environ.get("OPENWEATHER_API_KEY"),
        description="OpenWeatherMap API key from OPENWEATHER_API_KEY env var"
    )

    # Supabase Database - loaded from .env via os.environ
    supabase_url: Optional[str] = Field(
        default_factory=lambda: os.environ.get("SUPABASE_URL"),
        description="Supabase project URL from SUPABASE_URL env var"
    )
    supabase_key: Optional[str] = Field(
        default_factory=lambda: os.environ.get("SUPABASE_KEY"),
        description="Supabase API key from SUPABASE_KEY env var"
    )
    database_url: Optional[str] = Field(
        default_factory=lambda: os.environ.get("DATABASE_URL"),
        description="Database connection string from DATABASE_URL env var"
    )

    # Application Settings - loaded from .env via os.environ
    secret_key: str = Field(
        default_factory=lambda: os.environ.get("SECRET_KEY") or secrets.token_urlsafe(32),
        description="Secret key from SECRET_KEY env var, auto-generated if not set"
    )
    debug: bool = Field(
        default_factory=lambda: os.environ.get("DEBUG", "True").lower() == "true",
        description="Debug mode from DEBUG env var (default: True)"
    )
    log_level: str = Field(
        default_factory=lambda: os.environ.get("LOG_LEVEL", "DEBUG"),
        description="Logging level from LOG_LEVEL env var (default: DEBUG)"
    )

    # Memory System (Embeddings for semantic search) - loaded from .env via os.environ
    embedding_model: str = Field(
        default_factory=lambda: os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
        description="Embedding model name from EMBEDDING_MODEL env var"
    )

    # LLM Configuration - loaded from .env via os.environ
    primary_llm_provider: str = Field(
        default_factory=lambda: os.environ.get("PRIMARY_LLM_PROVIDER", "openai"),
        description="Primary LLM provider from PRIMARY_LLM_PROVIDER env var (default: openai)"
    )
    primary_llm_model: str = Field(
        default_factory=lambda: os.environ.get("PRIMARY_LLM_MODEL", "gpt-3.5-turbo"),
        description="Primary LLM model from PRIMARY_LLM_MODEL env var"
    )
    fallback_llm_provider: str = Field(
        default_factory=lambda: os.environ.get("FALLBACK_LLM_PROVIDER", "google"),
        description="Fallback LLM provider from FALLBACK_LLM_PROVIDER env var (default: google)"
    )
    fallback_llm_model: str = Field(
        default_factory=lambda: os.environ.get("FALLBACK_LLM_MODEL", "gemini-2.0-flash-exp"),
        description="Fallback LLM model from FALLBACK_LLM_MODEL env var"
    )

    # Cost Tracking - loaded from .env via os.environ
    track_costs: bool = Field(
        default_factory=lambda: os.environ.get("TRACK_COSTS", "True").lower() == "true",
        description="Enable cost tracking from TRACK_COSTS env var (default: True)"
    )

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

