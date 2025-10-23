"""
Model registry endpoints.

Provides access to the model registry for browsing and searching models.
"""

import csv
import logging
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from llmops_agent.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


# ================================================================
# Models
# ================================================================


class ModelInfo(BaseModel):
    """Model information from registry."""

    model_id: str = Field(..., description="Hugging Face model ID")
    task_type: str = Field(..., description="Task type")
    params: int = Field(..., description="Number of parameters")
    vram_gb: Optional[float] = Field(None, description="VRAM requirement (GB)")
    baseline_f1: Optional[float] = Field(None, description="Baseline F1 score")
    training_methods: List[str] = Field(default_factory=list)
    quantization_support: List[str] = Field(default_factory=list)


class ModelListResponse(BaseModel):
    """List of models response."""

    models: List[ModelInfo]
    total: int
    page: int
    page_size: int


# ================================================================
# Endpoints
# ================================================================


@router.get("", response_model=ModelListResponse)
async def list_models(
    task_type: Optional[str] = Query(None, description="Filter by task type"),
    search: Optional[str] = Query(None, description="Search in model name"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    List models from the registry.

    Supports filtering by task type and searching by name.
    """
    try:
        logger.info(f"Listing models: task_type={task_type}, search={search}")

        # Load models from CSV
        models = load_models_from_csv()

        # Filter by task type
        if task_type:
            models = [m for m in models if m.task_type == task_type]

        # Search by name
        if search:
            search_lower = search.lower()
            models = [m for m in models if search_lower in m.model_id.lower()]

        # Pagination
        total = len(models)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_models = models[start:end]

        return ModelListResponse(
            models=paginated_models,
            total=total,
            page=page,
            page_size=page_size,
        )

    except Exception as e:
        logger.error(f"Error listing models: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list models: {str(e)}",
        )


@router.get("/{model_id:path}", response_model=ModelInfo)
async def get_model(model_id: str):
    """
    Get details of a specific model.

    model_id can include slashes (e.g., "distilbert/distilbert-base-cased")
    """
    try:
        logger.info(f"Getting model details for {model_id}")

        # Load models from CSV
        models = load_models_from_csv()

        # Find the model
        model = next((m for m in models if m.model_id == model_id), None)

        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model '{model_id}' not found in registry",
            )

        return model

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting model {model_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get model: {str(e)}",
        )


# ================================================================
# Helper Functions
# ================================================================


def load_models_from_csv() -> List[ModelInfo]:
    """
    Load models from S3 and DynamoDB.

    Returns a list of ModelInfo objects for trained models.
    """
    import boto3

    models = []

    try:
        # List trained models from S3
        s3 = boto3.client("s3")
        bucket = "llmops-agent-models"

        # List objects in the models bucket
        response = s3.list_objects_v2(Bucket=bucket, Delimiter='/')

        # Get prefixes (folders) in the bucket
        prefixes = response.get('CommonPrefixes', [])

        # Add some common base models that could be used
        base_models = [
            ModelInfo(
                model_id="distilbert-base-cased",
                task_type="token-classification",
                params=66_000_000,  # 66M parameters
                vram_gb=0.5,
                baseline_f1=0.85,
                training_methods=["Full Fine-tuning", "LoRA"],
                quantization_support=["INT8", "FP16"],
            ),
            ModelInfo(
                model_id="bert-base-cased",
                task_type="token-classification",
                params=110_000_000,  # 110M parameters
                vram_gb=1.0,
                baseline_f1=0.88,
                training_methods=["Full Fine-tuning", "LoRA"],
                quantization_support=["INT8", "FP16"],
            ),
            ModelInfo(
                model_id="roberta-base",
                task_type="token-classification",
                params=125_000_000,  # 125M parameters
                vram_gb=1.2,
                baseline_f1=0.89,
                training_methods=["Full Fine-tuning", "LoRA"],
                quantization_support=["INT8", "FP16"],
            ),
        ]

        models.extend(base_models)

        # Add trained models from S3 if any exist
        for prefix in prefixes:
            prefix_name = prefix.get('Prefix', '').rstrip('/')
            if prefix_name:
                # This represents a trained model folder
                models.append(
                    ModelInfo(
                        model_id=f"trained/{prefix_name}",
                        task_type="token-classification",
                        params=66_000_000,  # Assume DistilBERT size
                        vram_gb=0.5,
                        baseline_f1=None,
                        training_methods=["LoRA"],
                        quantization_support=["FP16"],
                    )
                )

        logger.info(f"Loaded {len(models)} models (base + trained from S3)")

    except Exception as e:
        logger.warning(f"Error loading models from S3, returning base models only: {e}")
        # Return at least the base models
        models = [
            ModelInfo(
                model_id="distilbert-base-cased",
                task_type="token-classification",
                params=66_000_000,
                vram_gb=0.5,
                baseline_f1=0.85,
                training_methods=["Full Fine-tuning", "LoRA"],
                quantization_support=["INT8", "FP16"],
            )
        ]

    return models


def parse_params(params_str: str) -> int:
    """
    Parse parameter count from string (e.g., "66M", "1.5B").

    Returns the number of parameters as an integer.
    """
    if not params_str:
        return 0

    params_str = params_str.strip().upper()

    if "B" in params_str:
        # Billions
        number = float(params_str.replace("B", ""))
        return int(number * 1_000_000_000)
    elif "M" in params_str:
        # Millions
        number = float(params_str.replace("M", ""))
        return int(number * 1_000_000)
    else:
        # Raw number
        try:
            return int(params_str)
        except ValueError:
            return 0
