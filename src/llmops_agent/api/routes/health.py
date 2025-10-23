"""
Health check endpoints.

Provides endpoints for monitoring application health and readiness.
"""

from fastapi import APIRouter, status
from pydantic import BaseModel

from llmops_agent import __version__
from llmops_agent.config import settings

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    version: str
    environment: str


class ReadinessResponse(BaseModel):
    """Readiness check response model."""

    ready: bool
    aws_region: str
    bedrock_configured: bool
    sagemaker_configured: bool


@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def health_check():
    """
    Health check endpoint.

    Returns basic application health status.
    """
    return HealthResponse(
        status="healthy",
        version=__version__,
        environment=settings.environment,
    )


@router.get("/ready", response_model=ReadinessResponse, status_code=status.HTTP_200_OK)
async def readiness_check():
    """
    Readiness check endpoint.

    Checks if the application is ready to serve requests.
    """
    # TODO: Add actual AWS service checks
    bedrock_configured = bool(settings.bedrock_agent_role_arn)
    sagemaker_configured = bool(settings.sagemaker_execution_role_arn)

    ready = bedrock_configured and sagemaker_configured

    return ReadinessResponse(
        ready=ready,
        aws_region=settings.aws_region,
        bedrock_configured=bedrock_configured,
        sagemaker_configured=sagemaker_configured,
    )
