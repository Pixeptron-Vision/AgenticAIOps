"""
FastAPI error handlers for custom exceptions.

Provides consistent error responses across the API.
"""

import logging
from typing import Union

from fastapi import Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from llmops_agent.core.exceptions import (
    AWSServiceError,
    AgentError,
    ConfigurationError,
    ConstraintViolation,
    DataError,
    LLMOpsException,
    ModelError,
    SessionError,
    ValidationError as CustomValidationError,
)

logger = logging.getLogger(__name__)


# ================================================================
# Exception to HTTP Status Code Mapping
# ================================================================


EXCEPTION_STATUS_CODES = {
    ConfigurationError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    AWSServiceError: status.HTTP_503_SERVICE_UNAVAILABLE,
    AgentError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    ConstraintViolation: status.HTTP_422_UNPROCESSABLE_ENTITY,
    DataError: status.HTTP_404_NOT_FOUND,
    ModelError: status.HTTP_404_NOT_FOUND,
    SessionError: status.HTTP_404_NOT_FOUND,
    CustomValidationError: status.HTTP_400_BAD_REQUEST,
}


def get_status_code_for_exception(exc: Exception) -> int:
    """
    Get HTTP status code for exception.

    Args:
        exc: Exception instance

    Returns:
        HTTP status code
    """
    # Check direct match
    exc_class = exc.__class__
    if exc_class in EXCEPTION_STATUS_CODES:
        return EXCEPTION_STATUS_CODES[exc_class]

    # Check parent classes
    for parent_class, status_code in EXCEPTION_STATUS_CODES.items():
        if isinstance(exc, parent_class):
            return status_code

    # Default to 500
    return status.HTTP_500_INTERNAL_SERVER_ERROR


# ================================================================
# Error Handlers
# ================================================================


async def llmops_exception_handler(
    request: Request, exc: LLMOpsException
) -> JSONResponse:
    """
    Handle custom LLMOps exceptions.

    Args:
        request: FastAPI request
        exc: LLMOps exception

    Returns:
        JSON error response
    """
    status_code = get_status_code_for_exception(exc)

    # Log error
    logger.error(
        f"LLMOps exception: {exc.error_code}",
        extra={
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details,
            "path": request.url.path,
            "method": request.method,
        },
        exc_info=status_code >= 500,  # Log stack trace for 5xx errors
    )

    # Return structured error response
    return JSONResponse(
        status_code=status_code,
        content=exc.to_dict(),
    )


async def validation_error_handler(
    request: Request, exc: ValidationError
) -> JSONResponse:
    """
    Handle Pydantic validation errors.

    Args:
        request: FastAPI request
        exc: Pydantic ValidationError

    Returns:
        JSON error response
    """
    # Extract validation errors
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        })

    logger.warning(
        f"Validation error on {request.url.path}",
        extra={"errors": errors, "path": request.url.path, "method": request.method},
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": {"errors": errors},
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle unexpected exceptions.

    Args:
        request: FastAPI request
        exc: Any exception

    Returns:
        JSON error response
    """
    # Log full stack trace for unexpected errors
    logger.error(
        f"Unexpected error on {request.url.path}: {exc}",
        extra={"path": request.url.path, "method": request.method},
        exc_info=True,
    )

    # Return generic error (don't expose internal details)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred",
            "details": {
                "type": exc.__class__.__name__,
                # Only include message in debug mode
                "message": str(exc) if logger.level == logging.DEBUG else None,
            },
        },
    )


# ================================================================
# Error Handler Registration
# ================================================================


def register_error_handlers(app) -> None:
    """
    Register all error handlers with FastAPI app.

    Args:
        app: FastAPI application
    """
    # Custom exceptions
    app.add_exception_handler(LLMOpsException, llmops_exception_handler)

    # Pydantic validation errors
    app.add_exception_handler(ValidationError, validation_error_handler)

    # Generic exception handler (catch-all)
    app.add_exception_handler(Exception, generic_exception_handler)

    logger.info("Error handlers registered")
