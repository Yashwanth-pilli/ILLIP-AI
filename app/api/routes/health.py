"""
Health check endpoints
"""

from fastapi import APIRouter
from app.core import HealthResponse
from app.providers import get_provider
from app.utils import logger, get_current_timestamp

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint
    Returns system status and connectivity
    """
    try:
        # The starter health check is intentionally small: if the configured
        # provider is available, the backend is ready for local use.
        provider = await get_provider()
        provider_ok = await provider.health_check()

        status = "ok" if provider_ok else "degraded"
        
        logger.info(f"Health check: {status}")
        
        return HealthResponse(
            status=status,
            message=f"System healthy. Provider: {provider.name}",
            timestamp=get_current_timestamp()
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="error",
            message=str(e),
            timestamp=get_current_timestamp()
        )
