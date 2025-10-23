"""
Tool endpoints for Bedrock Agent action groups.

These endpoints are called by the Bedrock Agent to execute tools.
They follow the AWS Lambda proxy integration format for compatibility.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import boto3
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from llmops_agent.agents.data_agent import DataAgent
from llmops_agent.agents.model_agent import ModelAgent
from llmops_agent.agents.training_agent import TrainingAgent
from llmops_agent.services.dynamodb_service import get_dynamodb_service

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize Lambda client for instance checking
lambda_client = boto3.client('lambda', region_name='us-east-1')


async def get_best_available_instance(budget_usd: float, estimated_time_hours: float = 1.0) -> str:
    """
    Intelligently select the best available SageMaker instance based on:
    - Availability (quota)
    - Cost (within budget)
    - Performance (GPU capability)

    Returns the recommended instance type or a safe fallback.
    """
    try:
        # Call the quota-checking Lambda
        response = lambda_client.invoke(
            FunctionName='llmops-tool-check-sagemaker-quotas',
            InvocationType='RequestResponse'
        )

        payload = json.loads(response['Payload'].read())
        body = json.loads(payload.get('body', '{}'))
        instances = body.get('instances', [])

        if not instances:
            logger.warning("No instance information available, using fallback")
            return "ml.g4dn.xlarge"

        # Filter instances that:
        # 1. Are available (recommended=True)
        # 2. Cost within budget for estimated time
        affordable_instances = [
            inst for inst in instances
            if inst.get('recommended', False) and
               (inst.get('cost_per_hour', 999) * estimated_time_hours) <= budget_usd
        ]

        if not affordable_instances:
            logger.warning(f"No affordable instances for budget ${budget_usd}, using cheapest available")
            # Use the cheapest available instance even if over budget
            affordable_instances = [inst for inst in instances if inst.get('recommended', False)]

        if affordable_instances:
            # Return the cheapest affordable instance
            best_instance = affordable_instances[0]  # Already sorted by cost
            logger.info(f"Selected instance: {best_instance['instance_type']} "
                       f"(${best_instance['cost_per_hour']}/hr, {best_instance['remaining']} available)")
            return best_instance['instance_type']

        # Ultimate fallback
        logger.warning("Could not determine best instance, using fallback")
        return "ml.g4dn.xlarge"

    except Exception as e:
        logger.error(f"Error checking instance availability: {e}", exc_info=True)
        # Fallback to safe default
        return "ml.g4dn.xlarge"


# ================================================================
# Request/Response Models
# ================================================================


class SelectModelRequest(BaseModel):
    """Request for model selection tool."""

    task_type: str = Field(..., description="ML task type (e.g., token-classification)")
    budget_usd: float = Field(..., description="Maximum budget in USD", ge=0)
    max_time_hours: Optional[float] = Field(None, description="Maximum training time in hours", ge=0)
    min_f1: Optional[float] = Field(None, description="Minimum F1 score required", ge=0, le=1)
    session_id: Optional[str] = Field(None, description="Session ID for tracking")


class SelectModelResponse(BaseModel):
    """Response from model selection tool."""

    success: bool
    model_id: Optional[str] = None
    estimated_cost: Optional[float] = None
    estimated_time_hours: Optional[float] = None
    expected_f1: Optional[float] = None
    instance_type: Optional[str] = None
    error: Optional[str] = None


class GetJobStatusRequest(BaseModel):
    """Request for job status tool."""

    job_id: str = Field(..., description="Training job ID")


class GetJobStatusResponse(BaseModel):
    """Response from job status tool."""

    success: bool
    job_id: str
    status: Optional[str] = None
    progress: Optional[int] = None
    sagemaker_job_name: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class PrepareDatasetRequest(BaseModel):
    """Request for dataset preparation tool."""

    dataset_name: str = Field(..., description="Name of the dataset to prepare")
    task_type: str = Field(default="token-classification", description="ML task type")
    force_prepare: bool = Field(default=False, description="Force re-preparation even if already prepared")
    source_prefix: str = Field(default="raw", description="S3 prefix for source data")
    target_prefix: str = Field(default="processed", description="S3 prefix for prepared data")
    session_id: Optional[str] = Field(None, description="Session ID for tracking")


class PrepareDatasetResponse(BaseModel):
    """Response from dataset preparation tool."""

    success: bool
    dataset_name: str
    preparation_status: str
    total_records: Optional[int] = None
    splits: Optional[Dict[str, int]] = None
    validation_errors: Optional[List[str]] = None
    invalid_records: Optional[int] = None
    processed_s3_uri: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None


# ================================================================
# Tool Endpoints
# ================================================================


@router.post("/select-model", response_model=SelectModelResponse)
async def select_model_tool(request: SelectModelRequest):
    """
    Tool: Select optimal model based on constraints.

    This endpoint is called by the Bedrock Agent when it decides
    to select a model for training.

    Example Agent decision:
    "User wants NER training with $10 budget and F1>0.85.
     I should call select_model to find the best model."
    """
    try:
        logger.info(f"Tool called: select_model - {request.dict()}")

        # Initialize model agent
        model_agent = ModelAgent()

        # Execute model selection
        result = await model_agent.select_model(
            task_type=request.task_type,
            budget_usd=request.budget_usd,
            max_time_hours=request.max_time_hours,
            min_f1=request.min_f1,
        )

        if not result.get("success"):
            return SelectModelResponse(
                success=False,
                error=result.get("error", "Model selection failed"),
            )

        # Extract recommended model
        recommended = result.get("recommended", {})

        # Get intelligent instance selection based on budget and availability
        best_instance = await get_best_available_instance(
            budget_usd=request.budget_usd,
            estimated_time_hours=recommended.get("estimated_time_hours", 1.0)
        )

        return SelectModelResponse(
            success=True,
            model_id=recommended.get("model_id"),
            estimated_cost=recommended.get("estimated_cost"),
            estimated_time_hours=recommended.get("estimated_time_hours"),
            expected_f1=recommended.get("baseline_f1"),
            instance_type=best_instance,
        )

    except Exception as e:
        logger.error(f"Error in select_model tool: {e}", exc_info=True)
        return SelectModelResponse(
            success=False,
            error=str(e),
        )


@router.post("/get-job-status", response_model=GetJobStatusResponse)
async def get_job_status_tool(request: GetJobStatusRequest):
    """
    Tool: Get training job status.

    This endpoint is called by the Bedrock Agent to check
    the status of a training job.

    Example Agent decision:
    "Training job was launched. I should check its status
     to provide an update to the user."
    """
    try:
        logger.info(f"Tool called: get_job_status - job_id={request.job_id}")

        # Initialize training agent
        training_agent = TrainingAgent()

        # Get job status
        result = await training_agent.get_job_status(request.job_id)

        if not result.get("success"):
            return GetJobStatusResponse(
                success=False,
                job_id=request.job_id,
                error=result.get("error", "Failed to get job status"),
            )

        return GetJobStatusResponse(
            success=True,
            job_id=request.job_id,
            status=result.get("status"),
            progress=result.get("progress"),
            sagemaker_job_name=result.get("sagemaker_job_name"),
            metrics=result.get("metrics"),
        )

    except Exception as e:
        logger.error(f"Error in get_job_status tool: {e}", exc_info=True)
        return GetJobStatusResponse(
            success=False,
            job_id=request.job_id,
            error=str(e),
        )


@router.post("/prepare-dataset", response_model=PrepareDatasetResponse)
async def prepare_dataset_tool(request: PrepareDatasetRequest):
    """
    Tool: Prepare dataset for training.

    This endpoint is called by the Bedrock Agent when it needs to
    prepare or validate a dataset before training.

    Example Agent decision:
    "User wants to train on cier dataset. I should first check if
     the data is prepared and valid by calling prepare_dataset."

    The tool is intelligent:
    - Skips preparation if dataset is already prepared (unless force_prepare=true)
    - Validates data format and normalizes annotations
    - Tracks status in DynamoDB to avoid redundant work
    - Only writes production-ready data to processed folder
    """
    try:
        logger.info(f"Tool called: prepare_dataset - {request.dict()}")

        # Initialize data agent
        data_agent = DataAgent()

        # Execute dataset preparation
        result = await data_agent.prepare_dataset(
            dataset_name=request.dataset_name,
            task_type=request.task_type,
            force_prepare=request.force_prepare,
            source_prefix=request.source_prefix,
            target_prefix=request.target_prefix,
        )

        if not result.get("success"):
            return PrepareDatasetResponse(
                success=False,
                dataset_name=request.dataset_name,
                preparation_status=result.get("preparation_status", "failed"),
                error=result.get("error", "Dataset preparation failed"),
            )

        return PrepareDatasetResponse(
            success=True,
            dataset_name=request.dataset_name,
            preparation_status=result.get("preparation_status"),
            total_records=result.get("total_records"),
            splits=result.get("splits"),
            validation_errors=result.get("validation_errors", []),
            invalid_records=result.get("invalid_records"),
            processed_s3_uri=result.get("processed_s3_uri"),
            message=result.get("message"),
        )

    except Exception as e:
        logger.error(f"Error in prepare_dataset tool: {e}", exc_info=True)
        return PrepareDatasetResponse(
            success=False,
            dataset_name=request.dataset_name,
            preparation_status="failed",
            error=str(e),
        )


@router.get("/health")
async def tools_health():
    """Health check for tools API."""
    return {
        "status": "healthy",
        "tools": [
            "select_model",
            "get_job_status",
            "prepare_dataset",
            "launch_training (Lambda)",
        ],
    }
