"""
Job management endpoints.

Provides CRUD operations for training jobs and job monitoring.
"""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from llmops_agent.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# AWS clients
dynamodb = boto3.resource("dynamodb")
sagemaker = boto3.client("sagemaker")


# ================================================================
# Models
# ================================================================


class JobConfig(BaseModel):
    """Training job configuration."""

    model_id: str = Field(..., description="Hugging Face model ID")
    dataset: str = Field(..., description="Dataset name or ID")
    task_type: str = Field(..., description="Task type (e.g., token-classification)")
    instance_type: str = Field(default="ml.g5.xlarge")
    use_peft: bool = Field(default=True, description="Use LoRA/PEFT")
    hyperparameters: Optional[dict] = Field(default=None)


class JobMetrics(BaseModel):
    """Training job metrics."""

    train_loss: Optional[float] = None
    val_loss: Optional[float] = None
    f1: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None


class Job(BaseModel):
    """Training job model."""

    job_id: str
    session_id: str
    status: str = Field(..., description="Job status (pending/running/completed/failed)")
    progress: int = Field(default=0, ge=0, le=100)
    config: JobConfig
    metrics: Optional[JobMetrics] = None
    cost_so_far: float = Field(default=0.0)
    sagemaker_job_name: Optional[str] = None
    created_at: str
    updated_at: str


class JobListResponse(BaseModel):
    """List of jobs response."""

    jobs: List[Job]
    total: int
    page: int
    page_size: int


# ================================================================
# Endpoints
# ================================================================


@router.get("", response_model=JobListResponse)
async def list_jobs(
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    List all training jobs.

    Supports filtering by session_id and status, with pagination.
    """
    try:
        logger.info(f"Listing jobs: session_id={session_id}, status={status_filter}")

        # Query DynamoDB for actual jobs
        jobs = await fetch_jobs_from_dynamodb(session_id=session_id, status_filter=status_filter)

        # Pagination
        total = len(jobs)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_jobs = jobs[start:end]

        return JobListResponse(
            jobs=paginated_jobs,
            total=total,
            page=page,
            page_size=page_size,
        )

    except Exception as e:
        logger.error(f"Error listing jobs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list jobs: {str(e)}",
        )


@router.get("/{job_id}", response_model=Job)
async def get_job(job_id: str):
    """
    Get details of a specific training job.
    """
    try:
        logger.info(f"Getting job details for {job_id}")

        # TODO: Query DynamoDB for actual job
        # For now, return mock data

        mock_job = Job(
            job_id=job_id,
            session_id=f"session-{uuid4().hex[:8]}",
            status="running",
            progress=65,
            config=JobConfig(
                model_id="distilbert-base-cased",
                dataset="ciER",
                task_type="token-classification",
                instance_type="ml.g5.xlarge",
                use_peft=True,
            ),
            metrics=JobMetrics(
                train_loss=0.32,
                val_loss=0.35,
            ),
            cost_so_far=2.80,
            sagemaker_job_name="huggingface-training-2025-01-20-14-22-10",
            created_at="2025-01-20T14:22:10Z",
            updated_at="2025-01-20T14:52:30Z",
        )

        return mock_job

    except Exception as e:
        logger.error(f"Error getting job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get job: {str(e)}",
        )


@router.get("/budget/session", status_code=status.HTTP_200_OK)
async def get_session_budget(
    session_id: Optional[str] = Query(None, description="Session ID (optional)")
):
    """
    Get budget information for a session or all sessions.
    """
    try:
        logger.info(f"Getting budget for session: {session_id or 'all'}")

        # Get all jobs (filtered by session if provided)
        jobs = await fetch_jobs_from_dynamodb(session_id=session_id)

        # Calculate totals
        total_cost = sum(job.cost_so_far for job in jobs)
        budget_limit = 50.0  # TODO: Get from settings or session config
        remaining = budget_limit - total_cost

        # Count jobs by status
        completed_jobs = len([j for j in jobs if j.status == "completed"])
        running_jobs = len([j for j in jobs if j.status == "running"])
        failed_jobs = len([j for j in jobs if j.status == "failed"])

        return {
            "spent": round(total_cost, 2),
            "limit": budget_limit,
            "remaining": round(remaining, 2),
            "percentage_used": round((total_cost / budget_limit * 100), 1) if budget_limit > 0 else 0,
            "jobs": {
                "total": len(jobs),
                "completed": completed_jobs,
                "running": running_jobs,
                "failed": failed_jobs,
            },
            "session_id": session_id or "all",
        }

    except Exception as e:
        logger.error(f"Error getting budget: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get budget: {str(e)}",
        )


@router.delete("/{job_id}", status_code=status.HTTP_200_OK)
async def cancel_job(job_id: str):
    """
    Cancel a running training job.
    """
    try:
        logger.info(f"Cancelling job {job_id}")

        # TODO: Call SageMaker to stop the training job

        return {
            "job_id": job_id,
            "status": "cancelled",
            "message": "Job cancellation requested",
        }

    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel job: {str(e)}",
        )


# ================================================================
# Helper Functions
# ================================================================


async def fetch_jobs_from_dynamodb(
    session_id: Optional[str] = None,
    status_filter: Optional[str] = None
) -> List[Job]:
    """
    Fetch training jobs from DynamoDB or fallback to SageMaker.

    Returns a list of Job objects with enriched data from SageMaker.
    """
    try:
        # Check if DynamoDB is available
        import socket
        dynamodb_available = False
        try:
            socket.setdefaulttimeout(1)
            socket.getaddrinfo("dynamodb.us-east-1.amazonaws.com", 443)
            dynamodb_available = True
        except (socket.gaierror, socket.timeout):
            logger.warning("DynamoDB endpoint unreachable, fetching directly from SageMaker")
        finally:
            socket.setdefaulttimeout(None)

        # If DynamoDB is unavailable, fetch directly from SageMaker
        if not dynamodb_available:
            return await fetch_jobs_from_sagemaker(status_filter)

        table = dynamodb.Table("llmops-jobs")

        # Use GSI for efficient session_id filtering
        if session_id:
            response = table.query(
                IndexName='session-index',
                KeyConditionExpression='session_id = :sid',
                ExpressionAttributeValues={':sid': session_id},
                ScanIndexForward=False  # Sort by created_at descending
            )
            items = response.get("Items", [])
        else:
            # Scan all jobs if no session filter
            response = table.scan()
            items = response.get("Items", [])

        jobs = []
        for item in items:
            try:
                # Enrich job data with SageMaker status and metrics
                job = await enrich_job_from_sagemaker(item)

                # Filter by status if provided
                if status_filter and job.status != status_filter:
                    continue

                jobs.append(job)
            except Exception as e:
                logger.warning(f"Failed to process job {item.get('job_id')}: {e}")
                continue

        # Sort by created_at descending (newest first)
        jobs.sort(key=lambda j: j.created_at, reverse=True)

        return jobs

    except Exception as e:
        logger.error(f"Error fetching jobs from DynamoDB: {e}", exc_info=True)
        return []


async def enrich_job_from_sagemaker(item: dict) -> Job:
    """
    Enrich a DynamoDB job item with SageMaker training job details.

    Fetches current status, metrics, and calculates cost.
    Also updates DynamoDB with the latest status from SageMaker.
    """
    job_id = item.get("job_id", "unknown")
    sagemaker_job_name = item.get("sagemaker_job_name")

    # Default values from DynamoDB
    status = item.get("status", "pending")
    # Convert Decimal to int (DynamoDB returns Decimal for numbers)
    progress_value = item.get("progress", 0)
    progress = int(float(progress_value)) if progress_value is not None else 0
    metrics = None
    cost_so_far = 0.0

    # Track if status changed to update DynamoDB
    status_changed = False
    original_status = status

    # Try to get SageMaker job details
    if sagemaker_job_name:
        try:
            sm_response = sagemaker.describe_training_job(TrainingJobName=sagemaker_job_name)

            # Update status
            sm_status = sm_response.get("TrainingJobStatus", "Unknown")
            status = map_sagemaker_status(sm_status)

            # Check if status changed
            if status != original_status:
                status_changed = True

            # Calculate progress
            if status == "completed":
                progress = 100
            elif status == "running":
                # Estimate progress based on time elapsed
                creation_time = sm_response.get("CreationTime")
                if creation_time:
                    elapsed_seconds = (datetime.now(creation_time.tzinfo) - creation_time).total_seconds()
                    # Assume 15 minutes average
                    progress = min(int((elapsed_seconds / 900) * 100), 95)

            # Extract metrics from SageMaker
            final_metrics = sm_response.get("FinalMetricDataList", [])
            if final_metrics:
                metrics = parse_sagemaker_metrics(final_metrics)

            # Calculate cost
            instance_type = sm_response.get("ResourceConfig", {}).get("InstanceType", "ml.g5.xlarge")
            training_time_seconds = sm_response.get("TrainingTimeInSeconds", 0)
            billable_time_seconds = sm_response.get("BillableTimeInSeconds", training_time_seconds)

            cost_so_far = calculate_training_cost(instance_type, billable_time_seconds)

            # Update DynamoDB if status changed
            if status_changed:
                try:
                    table = dynamodb.Table("llmops-jobs")
                    update_expression = "SET #status = :status, #progress = :progress, updated_at = :updated_at, updated_at_iso = :updated_at_iso"
                    expression_attribute_names = {
                        "#status": "status",
                        "#progress": "progress"
                    }
                    expression_attribute_values = {
                        ":status": status,
                        ":progress": progress,
                        ":updated_at": int(datetime.now().timestamp()),
                        ":updated_at_iso": datetime.now().isoformat()
                    }

                    # Add cost if available
                    if cost_so_far > 0:
                        update_expression += ", cost_so_far = :cost"
                        expression_attribute_values[":cost"] = cost_so_far

                    table.update_item(
                        Key={"job_id": job_id},
                        UpdateExpression=update_expression,
                        ExpressionAttributeNames=expression_attribute_names,
                        ExpressionAttributeValues=expression_attribute_values
                    )
                    logger.info(f"Updated job {job_id} status from {original_status} to {status}")
                except Exception as e:
                    logger.error(f"Failed to update DynamoDB for job {job_id}: {e}")

        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                logger.warning(f"Error fetching SageMaker job {sagemaker_job_name}: {e}")
        except Exception as e:
            logger.warning(f"Error processing SageMaker job {sagemaker_job_name}: {e}")

    # Build Job object
    job = Job(
        job_id=job_id,
        session_id=item.get("session_id", "unknown"),
        status=status,
        progress=progress,
        config=JobConfig(
            model_id=item.get("model_id", "distilbert-base-cased"),
            dataset=item.get("dataset", "unknown"),
            task_type=item.get("task_type", "token-classification"),
            instance_type=item.get("instance_type", "ml.g5.xlarge"),
            use_peft=item.get("use_peft", "true") == "true",
            hyperparameters=item.get("hyperparameters"),
        ),
        metrics=metrics,
        cost_so_far=cost_so_far,
        sagemaker_job_name=sagemaker_job_name,
        created_at=item.get("created_at_iso", datetime.fromtimestamp(float(item.get("created_at", 0))).isoformat()),
        updated_at=item.get("updated_at_iso", datetime.fromtimestamp(float(item.get("updated_at", 0))).isoformat()),
    )

    return job


def map_sagemaker_status(sm_status: str) -> str:
    """Map SageMaker training job status to our status."""
    status_map = {
        "InProgress": "running",
        "Completed": "completed",
        "Failed": "failed",
        "Stopping": "running",
        "Stopped": "failed",
    }
    return status_map.get(sm_status, "pending")


def parse_sagemaker_metrics(metrics_list: List[dict]) -> Optional[JobMetrics]:
    """Parse SageMaker final metrics into JobMetrics model."""
    metrics_dict = {}

    for metric in metrics_list:
        metric_name = metric.get("MetricName", "").lower()
        metric_value = metric.get("Value", 0.0)

        if "loss" in metric_name and "train" in metric_name:
            metrics_dict["train_loss"] = metric_value
        elif "loss" in metric_name and ("val" in metric_name or "eval" in metric_name):
            metrics_dict["val_loss"] = metric_value
        elif "f1" in metric_name:
            metrics_dict["f1"] = metric_value
        elif "precision" in metric_name:
            metrics_dict["precision"] = metric_value
        elif "recall" in metric_name:
            metrics_dict["recall"] = metric_value

    if metrics_dict:
        return JobMetrics(**metrics_dict)
    return None


def calculate_training_cost(instance_type: str, duration_seconds: int) -> float:
    """
    Calculate training cost based on instance type and duration.

    Returns cost in USD.
    """
    # SageMaker instance pricing (as of 2025, us-east-1)
    hourly_rates = {
        "ml.g5.xlarge": 1.006,
        "ml.g5.2xlarge": 1.515,
        "ml.g5.4xlarge": 2.033,
        "ml.g4dn.xlarge": 0.736,
        "ml.g4dn.2xlarge": 0.941,
        "ml.p3.2xlarge": 3.825,
        "ml.p3.8xlarge": 14.688,
        "ml.m5.large": 0.115,
        "ml.m5.xlarge": 0.230,
    }

    hourly_rate = hourly_rates.get(instance_type, 1.0)  # Default to $1/hour
    hours = duration_seconds / 3600
    cost = hourly_rate * hours

    return round(cost, 2)


async def fetch_jobs_from_sagemaker(status_filter: Optional[str] = None) -> List[Job]:
    """
    Fetch training jobs directly from SageMaker (fallback when DynamoDB is unavailable).

    Returns a list of Job objects built from list_training_jobs summary data.
    Avoids describe_training_job calls which may fail with 500 errors.
    """
    try:
        # List training jobs from SageMaker
        response = sagemaker.list_training_jobs(
            SortBy='CreationTime',
            SortOrder='Descending',
            MaxResults=100
        )

        jobs = []
        for job_summary in response.get('TrainingJobSummaries', []):
            try:
                job_name = job_summary['TrainingJobName']

                # Use summary data instead of describe_training_job
                sm_status = job_summary['TrainingJobStatus']
                status = map_sagemaker_status(sm_status)

                # Filter by status if provided
                if status_filter and status != status_filter:
                    continue

                # Calculate progress from summary
                progress = 0
                if status == "completed":
                    progress = 100
                elif status == "running":
                    creation_time = job_summary.get("CreationTime")
                    if creation_time:
                        elapsed_seconds = (datetime.now(creation_time.tzinfo) - creation_time).total_seconds()
                        progress = min(int((elapsed_seconds / 900) * 100), 95)

                # Estimate cost from summary (training time may not be available)
                training_time = job_summary.get("TrainingTimeInSeconds", 0)
                # Default to g4dn.xlarge if we don't have resource config
                cost_so_far = calculate_training_cost("ml.g4dn.xlarge", training_time)

                # Create Job object from summary data
                job = Job(
                    job_id=f"job-{job_name.split('-')[-1]}" if '-' in job_name else job_name,
                    session_id="unknown",  # No DynamoDB, so no session info
                    status=status,
                    progress=progress,
                    config=JobConfig(
                        model_id="distilbert-base-cased",  # Default - can't get from summary
                        dataset="ciER",
                        task_type="token-classification",
                        instance_type="ml.g4dn.xlarge",  # Default - summary doesn't have ResourceConfig
                        use_peft=True,
                    ),
                    metrics=None,  # Metrics not available in summary
                    cost_so_far=cost_so_far,
                    sagemaker_job_name=job_name,
                    created_at=job_summary['CreationTime'].isoformat(),
                    updated_at=job_summary.get('LastModifiedTime', job_summary['CreationTime']).isoformat(),
                )

                jobs.append(job)

            except Exception as e:
                logger.warning(f"Failed to process SageMaker job {job_summary.get('TrainingJobName')}: {e}")
                continue

        return jobs

    except Exception as e:
        logger.error(f"Error fetching jobs from SageMaker: {e}", exc_info=True)
        return []
