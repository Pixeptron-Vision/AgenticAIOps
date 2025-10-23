"""
FastAPI application entry point.

This module creates and configures the FastAPI application with
routes, middleware, and event handlers.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from llmops_agent import __version__
from llmops_agent.api.error_handlers import register_error_handlers
from llmops_agent.config import settings

# Import routes
from llmops_agent.api.routes import agent, budgets, data, health, jobs, models, sessions, tools

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting LLMOps Agent API...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"AWS Region: {settings.aws_region}")
    logger.info(f"Bedrock Model: {settings.bedrock_model_id}")

    # TODO: Initialize AWS clients, database connections, etc.

    yield

    # Shutdown
    logger.info("Shutting down LLMOps Agent API...")
    # TODO: Cleanup resources


# Create FastAPI application
app = FastAPI(
    title="LLMOps Agent API",
    description="Multi-agent platform for autonomous ML training with AWS Bedrock and SageMaker",
    version=__version__,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register error handlers
register_error_handlers(app)

# Include routers
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(agent.router, prefix="/api/agent", tags=["Agent"])
app.include_router(sessions.router, prefix="/api", tags=["Sessions"])
app.include_router(budgets.router, prefix="/api", tags=["Budgets"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(models.router, prefix="/api/models", tags=["Models"])
app.include_router(data.router, prefix="/api/data", tags=["Data"])
app.include_router(tools.router, prefix="/api/tools", tags=["Tools"])


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handle uncaught exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.debug else "An error occurred",
        },
    )


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "LLMOps Agent API",
        "version": __version__,
        "status": "running",
        "docs": "/docs" if settings.debug else None,
    }


def start_server():
    """Start the FastAPI server using uvicorn."""
    import uvicorn

    uvicorn.run(
        "llmops_agent.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        workers=1 if settings.debug else settings.api_workers,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    start_server()
