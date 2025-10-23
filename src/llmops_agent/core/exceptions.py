"""
Custom exceptions for LLMOps Agent.

Provides a hierarchy of exceptions for better error handling and user feedback.
"""

from typing import Any, Dict, Optional


# ================================================================
# Base Exceptions
# ================================================================


class LLMOpsException(Exception):
    """Base exception for all LLMOps Agent errors."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize exception.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            details: Additional error details
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
        }


# ================================================================
# Configuration Exceptions
# ================================================================


class ConfigurationError(LLMOpsException):
    """Configuration error (missing env vars, invalid settings)."""

    pass


class AWSCredentialsError(ConfigurationError):
    """AWS credentials not found or invalid."""

    def __init__(self, message: str = "AWS credentials not configured or invalid"):
        super().__init__(
            message=message,
            error_code="AWS_CREDENTIALS_ERROR",
            details={"hint": "Check AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env"},
        )


# ================================================================
# AWS Service Exceptions
# ================================================================


class AWSServiceError(LLMOpsException):
    """Base exception for AWS service errors."""

    pass


class BedrockError(AWSServiceError):
    """Bedrock service error."""

    pass


class BedrockQuotaExceeded(BedrockError):
    """Bedrock quota exceeded."""

    def __init__(self, model_id: str, quota_type: str = "requests"):
        super().__init__(
            message=f"Bedrock quota exceeded for model {model_id}",
            error_code="BEDROCK_QUOTA_EXCEEDED",
            details={
                "model_id": model_id,
                "quota_type": quota_type,
                "hint": "Wait a few minutes or request quota increase",
            },
        )


class SageMakerError(AWSServiceError):
    """SageMaker service error."""

    pass


class SageMakerQuotaExceeded(SageMakerError):
    """SageMaker instance quota exceeded."""

    def __init__(self, instance_type: str, current_limit: int = 0):
        super().__init__(
            message=f"SageMaker quota exceeded for instance type {instance_type}",
            error_code="SAGEMAKER_QUOTA_EXCEEDED",
            details={
                "instance_type": instance_type,
                "current_limit": current_limit,
                "hint": "Request quota increase in AWS Service Quotas console",
            },
        )


class TrainingJobFailed(SageMakerError):
    """Training job failed."""

    def __init__(self, job_name: str, failure_reason: str):
        super().__init__(
            message=f"Training job {job_name} failed: {failure_reason}",
            error_code="TRAINING_JOB_FAILED",
            details={"job_name": job_name, "failure_reason": failure_reason},
        )


class DynamoDBError(AWSServiceError):
    """DynamoDB service error."""

    pass


class DynamoDBConnectionError(DynamoDBError):
    """Cannot connect to DynamoDB."""

    def __init__(self, table_name: str, reason: str = "Connection timeout"):
        super().__init__(
            message=f"Cannot connect to DynamoDB table {table_name}: {reason}",
            error_code="DYNAMODB_CONNECTION_ERROR",
            details={
                "table_name": table_name,
                "reason": reason,
                "hint": "Check AWS maintenance status or VPC configuration",
            },
        )


class S3Error(AWSServiceError):
    """S3 service error."""

    pass


class S3BucketNotFound(S3Error):
    """S3 bucket not found."""

    def __init__(self, bucket_name: str):
        super().__init__(
            message=f"S3 bucket not found: {bucket_name}",
            error_code="S3_BUCKET_NOT_FOUND",
            details={"bucket_name": bucket_name, "hint": "Create bucket or check bucket name"},
        )


# ================================================================
# Agent Exceptions
# ================================================================


class AgentError(LLMOpsException):
    """Base exception for agent errors."""

    pass


class ConstraintViolation(AgentError):
    """User constraints cannot be satisfied."""

    def __init__(
        self,
        message: str,
        violated_constraints: Dict[str, Any],
        suggestions: Optional[list] = None,
    ):
        super().__init__(
            message=message,
            error_code="CONSTRAINT_VIOLATION",
            details={
                "violated_constraints": violated_constraints,
                "suggestions": suggestions or [],
            },
        )
        self.violated_constraints = violated_constraints
        self.suggestions = suggestions or []


class NoModelsFound(ConstraintViolation):
    """No models match the given constraints."""

    def __init__(self, constraints: Dict[str, Any]):
        super().__init__(
            message="No models found matching your constraints",
            violated_constraints=constraints,
            suggestions=[
                "Increase budget",
                "Relax F1 score requirement",
                "Allow more training time",
            ],
        )


class BudgetExceeded(ConstraintViolation):
    """Training cost exceeds budget."""

    def __init__(self, estimated_cost: float, budget: float):
        super().__init__(
            message=f"Estimated cost ${estimated_cost:.2f} exceeds budget ${budget:.2f}",
            violated_constraints={"estimated_cost": estimated_cost, "budget": budget},
            suggestions=[
                "Increase budget",
                "Use smaller model",
                "Reduce dataset size",
            ],
        )


class ParsingError(AgentError):
    """Failed to parse user request."""

    def __init__(self, user_request: str, parse_error: str):
        super().__init__(
            message=f"Failed to parse request: {parse_error}",
            error_code="PARSING_ERROR",
            details={"user_request": user_request, "parse_error": parse_error},
        )


# ================================================================
# Data Exceptions
# ================================================================


class DataError(LLMOpsException):
    """Base exception for data errors."""

    pass


class DatasetNotFound(DataError):
    """Dataset not found."""

    def __init__(self, dataset_name: str, source: str = "Hugging Face"):
        super().__init__(
            message=f"Dataset not found: {dataset_name}",
            error_code="DATASET_NOT_FOUND",
            details={
                "dataset_name": dataset_name,
                "source": source,
                "hint": "Check dataset name or use different dataset",
            },
        )


class DataValidationError(DataError):
    """Data validation failed."""

    def __init__(self, message: str, validation_errors: list):
        super().__init__(
            message=message,
            error_code="DATA_VALIDATION_ERROR",
            details={"validation_errors": validation_errors},
        )


# ================================================================
# Model Exceptions
# ================================================================


class ModelError(LLMOpsException):
    """Base exception for model errors."""

    pass


class ModelNotFound(ModelError):
    """Model not found in registry."""

    def __init__(self, model_id: str):
        super().__init__(
            message=f"Model not found: {model_id}",
            error_code="MODEL_NOT_FOUND",
            details={"model_id": model_id, "hint": "Check model ID or update registry"},
        )


class ModelLoadError(ModelError):
    """Failed to load model."""

    def __init__(self, model_id: str, reason: str):
        super().__init__(
            message=f"Failed to load model {model_id}: {reason}",
            error_code="MODEL_LOAD_ERROR",
            details={"model_id": model_id, "reason": reason},
        )


# ================================================================
# Validation Exceptions
# ================================================================


class ValidationError(LLMOpsException):
    """Input validation failed."""

    def __init__(self, field: str, message: str, value: Any = None):
        super().__init__(
            message=f"Validation error for {field}: {message}",
            error_code="VALIDATION_ERROR",
            details={"field": field, "message": message, "value": value},
        )


class InvalidBudget(ValidationError):
    """Budget value is invalid."""

    def __init__(self, budget: float):
        super().__init__(
            field="budget_usd",
            message=f"Budget must be positive, got {budget}",
            value=budget,
        )


class InvalidF1Score(ValidationError):
    """F1 score value is invalid."""

    def __init__(self, f1: float):
        super().__init__(
            field="min_f1",
            message=f"F1 score must be between 0 and 1, got {f1}",
            value=f1,
        )


# ================================================================
# Session Exceptions
# ================================================================


class SessionError(LLMOpsException):
    """Session management error."""

    pass


class SessionNotFound(SessionError):
    """Session not found."""

    def __init__(self, session_id: str):
        super().__init__(
            message=f"Session not found: {session_id}",
            error_code="SESSION_NOT_FOUND",
            details={"session_id": session_id},
        )


class SessionExpired(SessionError):
    """Session has expired."""

    def __init__(self, session_id: str, expired_at: str):
        super().__init__(
            message=f"Session expired: {session_id}",
            error_code="SESSION_EXPIRED",
            details={"session_id": session_id, "expired_at": expired_at},
        )


# ================================================================
# External Service Exceptions
# ================================================================


class ExternalServiceError(LLMOpsException):
    """External service error (Hugging Face, MLflow, etc.)."""

    pass


class HuggingFaceError(ExternalServiceError):
    """Hugging Face API error."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(
            message=f"Hugging Face error: {message}",
            error_code="HUGGINGFACE_ERROR",
            details={"message": message, "status_code": status_code},
        )


class MLflowError(ExternalServiceError):
    """MLflow service error."""

    def __init__(self, message: str, operation: str):
        super().__init__(
            message=f"MLflow {operation} error: {message}",
            error_code="MLFLOW_ERROR",
            details={"operation": operation, "message": message},
        )
