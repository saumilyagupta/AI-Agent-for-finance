"""Statistics routes."""

from fastapi import APIRouter

from app.api.schemas import StatsResponse, ToolStatsResponse
from app.database.crud import get_execution_stats
from app.database.database import get_db
from app.tools.registry import tool_registry
from app.utils.logger import logger

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/overview", response_model=StatsResponse)
async def get_overview_stats():
    """Get overall usage statistics."""
    try:
        db = next(get_db())
        stats = get_execution_stats(db)
        return StatsResponse(**stats)
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise


@router.get("/costs")
async def get_cost_stats():
    """Get cost breakdown by LLM provider."""
    # This would query database for cost breakdown
    # For now, return placeholder
    return {
        "total_cost": 0.0,
        "by_provider": {
            "google": 0.0,
            "openai": 0.0,
        },
    }


@router.get("/tools", response_model=list[ToolStatsResponse])
async def get_tool_stats():
    """Get tool usage statistics."""
    try:
        tools = tool_registry.list_tools()
        stats = []
        for tool_name in tools:
            tool = tool_registry.get_tool(tool_name)
            if tool:
                tool_stats = tool.get_stats()
                stats.append(
                    ToolStatsResponse(
                        tool_name=tool_stats["name"],
                        usage_count=tool_stats["usage_count"],
                        error_count=tool_stats["error_count"],
                        success_rate=tool_stats["success_rate"],
                    )
                )
        return stats
    except Exception as e:
        logger.error(f"Failed to get tool stats: {e}")
        raise

