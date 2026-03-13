"""
Health Check Router
"""
import time
from fastapi import APIRouter
from app.core.config import get_settings

router = APIRouter()
settings = get_settings()
_start_time = time.time()


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "uptime_seconds": round(time.time() - _start_time, 1),
    }


@router.get("/health/ready")
async def readiness_check():
    checks = {}

    # Check OpenAI key is set
    checks["openai_configured"] = bool(settings.OPENAI_API_KEY)
    checks["github_app_configured"] = bool(settings.GITHUB_APP_ID and settings.GITHUB_PRIVATE_KEY)

    all_ok = all(checks.values())
    return {
        "status": "ready" if all_ok else "not_ready",
        "checks": checks,
    }
