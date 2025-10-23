"""
FastAPI dependencies.

Provides reusable dependencies for dependency injection.
"""

from typing import Optional

from fastapi import Depends, Header, HTTPException, status

from llmops_agent.config import settings


async def verify_api_key(x_api_key: Optional[str] = Header(None)) -> None:
    """
    Verify API key if authentication is enabled.

    Usage:
        @router.get("/protected", dependencies=[Depends(verify_api_key)])
        async def protected_endpoint():
            ...
    """
    if not settings.api_key_enabled:
        return

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )


# TODO: Add more dependencies as needed:
# - get_db_session: Database session
# - get_current_user: User authentication
# - get_bedrock_client: Bedrock client
# - get_sagemaker_client: SageMaker client
