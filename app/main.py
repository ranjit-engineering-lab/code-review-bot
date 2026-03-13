"""
Intelligent Code Review Bot - FastAPI Application Entry Point
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api.webhook_router import router as webhook_router
from app.api.health_router import router as health_router
from app.core.config import get_settings
from app.core.logging_config import setup_logging

settings = get_settings()
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Code Review Bot starting up...")
    yield
    logger.info("🛑 Code Review Bot shutting down...")


app = FastAPI(
    title="Intelligent Code Review Bot",
    description="Automated PR reviews flagging security issues, performance anti-patterns, and style violations",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS,
)

app.include_router(health_router, prefix="/api/v1", tags=["Health"])
app.include_router(webhook_router, prefix="/api/v1", tags=["Webhooks"])
