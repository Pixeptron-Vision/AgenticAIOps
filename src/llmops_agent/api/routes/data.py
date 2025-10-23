"""
Data management endpoints.

Provides access to datasets stored in S3.
"""

import logging
from datetime import datetime
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

router = APIRouter()
logger = logging.getLogger(__name__)

# AWS clients
s3 = boto3.client("s3")


# ================================================================
# Models
# ================================================================


class DatasetFile(BaseModel):
    """Dataset file information."""

    name: str
    size_bytes: int
    size_human: str
    last_modified: str


class Dataset(BaseModel):
    """Dataset information."""

    name: str
    path: str
    files: List[DatasetFile]
    total_size_bytes: int
    total_size_human: str
    file_count: int
    last_modified: str


class DatasetListResponse(BaseModel):
    """List of datasets response."""

    datasets: List[Dataset]
    total: int


# ================================================================
# Endpoints
# ================================================================


@router.get("/datasets", response_model=DatasetListResponse)
async def list_datasets():
    """
    List all datasets from S3.

    Scans the llmops-agent-datasets bucket for processed datasets.
    """
    try:
        logger.info("Listing datasets from S3")

        datasets = load_datasets_from_s3()

        return DatasetListResponse(
            datasets=datasets,
            total=len(datasets),
        )

    except Exception as e:
        logger.error(f"Error listing datasets: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list datasets: {str(e)}",
        )


@router.get("/datasets/{dataset_name}")
async def get_dataset(dataset_name: str):
    """
    Get details of a specific dataset.
    """
    try:
        logger.info(f"Getting dataset details for {dataset_name}")

        datasets = load_datasets_from_s3()
        dataset = next((d for d in datasets if d.name == dataset_name), None)

        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset '{dataset_name}' not found",
            )

        return dataset

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dataset {dataset_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dataset: {str(e)}",
        )


# ================================================================
# Helper Functions
# ================================================================


def load_datasets_from_s3() -> List[Dataset]:
    """
    Load datasets from S3 bucket.

    Returns a list of Dataset objects.
    """
    datasets = []
    bucket = "llmops-agent-datasets"
    prefix = "processed/"

    try:
        # List all objects under processed/
        paginator = s3.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

        # Group files by dataset (first level folder after processed/)
        dataset_files = {}

        for page in pages:
            for obj in page.get('Contents', []):
                key = obj['Key']

                # Skip the prefix itself
                if key == prefix:
                    continue

                # Extract dataset name (folder after processed/)
                parts = key[len(prefix):].split('/')
                if not parts[0]:
                    continue

                dataset_name = parts[0]

                # Only include actual files (not just folders)
                if len(parts) > 1 and parts[-1]:  # Has a filename
                    if dataset_name not in dataset_files:
                        dataset_files[dataset_name] = []

                    dataset_files[dataset_name].append({
                        'name': parts[-1],
                        'size': obj['Size'],
                        'modified': obj['LastModified'],
                    })

        # Create Dataset objects
        for dataset_name, files in dataset_files.items():
            total_size = sum(f['size'] for f in files)
            last_modified = max(f['modified'] for f in files)

            dataset_file_objects = [
                DatasetFile(
                    name=f['name'],
                    size_bytes=f['size'],
                    size_human=format_bytes(f['size']),
                    last_modified=f['modified'].isoformat(),
                )
                for f in files
            ]

            datasets.append(
                Dataset(
                    name=dataset_name,
                    path=f"s3://{bucket}/{prefix}{dataset_name}/",
                    files=dataset_file_objects,
                    total_size_bytes=total_size,
                    total_size_human=format_bytes(total_size),
                    file_count=len(files),
                    last_modified=last_modified.isoformat(),
                )
            )

        logger.info(f"Loaded {len(datasets)} datasets from S3")

    except ClientError as e:
        logger.error(f"Error accessing S3: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Error loading datasets from S3: {e}", exc_info=True)

    return datasets


def format_bytes(bytes_value: int) -> str:
    """
    Format bytes to human-readable string.

    Examples:
        1024 -> "1.0 KB"
        1048576 -> "1.0 MB"
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"
