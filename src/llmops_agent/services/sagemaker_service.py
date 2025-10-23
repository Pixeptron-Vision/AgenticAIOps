"""
Amazon SageMaker service client.

Provides high-level interface for SageMaker training jobs.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError
from sagemaker.huggingface import HuggingFace

from llmops_agent.config import settings

logger = logging.getLogger(__name__)


class SageMakerService:
    """Service for interacting with Amazon SageMaker."""

    def __init__(self):
        """Initialize SageMaker client."""
        self.sagemaker = boto3.client(
            "sagemaker",
            region_name=settings.aws_region,
        )

        self.sagemaker_runtime = boto3.client(
            "sagemaker-runtime",
            region_name=settings.aws_region,
        )

    async def create_training_job(
        self,
        job_name: str,
        model_id: str,
        dataset_s3_uri: str,
        output_s3_uri: str,
        instance_type: Optional[str] = None,
        hyperparameters: Optional[Dict[str, Any]] = None,
        use_peft: bool = True,
    ) -> str:
        """
        Create a SageMaker training job using Hugging Face estimator.

        Args:
            job_name: Unique training job name
            model_id: Hugging Face model ID
            dataset_s3_uri: S3 URI of preprocessed dataset
            output_s3_uri: S3 URI for model output
            instance_type: SageMaker instance type
            hyperparameters: Training hyperparameters
            use_peft: Use LoRA/PEFT for efficient fine-tuning

        Returns:
            Training job name
        """
        try:
            instance_type = instance_type or settings.sagemaker_instance_type

            # Default hyperparameters
            hparams = {
                "model_id": model_id,
                "learning_rate": settings.default_learning_rate,
                "num_train_epochs": settings.default_num_epochs,
                "per_device_train_batch_size": settings.default_batch_size,
                "warmup_steps": settings.default_warmup_steps,
                "use_peft": use_peft,
            }

            # Add LoRA parameters if using PEFT
            if use_peft:
                hparams.update({
                    "lora_r": settings.default_lora_r,
                    "lora_alpha": settings.default_lora_alpha,
                    "lora_dropout": settings.default_lora_dropout,
                })

            # Merge with provided hyperparameters
            if hyperparameters:
                hparams.update(hyperparameters)

            logger.info(f"Creating training job: {job_name}")
            logger.debug(f"Hyperparameters: {hparams}")

            # Create Hugging Face estimator
            estimator = HuggingFace(
                entry_point="train_ner.py",
                source_dir="./scripts/training",  # TODO: Create this
                role=settings.sagemaker_execution_role_arn,
                instance_type=instance_type,
                instance_count=settings.sagemaker_instance_count,
                transformers_version=settings.sagemaker_transformers_version,
                pytorch_version=settings.sagemaker_pytorch_version,
                py_version=settings.sagemaker_python_version,
                hyperparameters=hparams,
                output_path=output_s3_uri,
                max_run=settings.sagemaker_max_runtime_seconds,
                volume_size=settings.sagemaker_volume_size_gb,
                environment={
                    "MLFLOW_TRACKING_URI": settings.mlflow_tracking_uri,
                    "MLFLOW_EXPERIMENT_NAME": settings.mlflow_experiment_name,
                },
            )

            # Start training (async)
            estimator.fit(
                inputs={"train": dataset_s3_uri},
                job_name=job_name,
                wait=False,
            )

            logger.info(f"Training job started: {job_name}")

            return job_name

        except ClientError as e:
            logger.error(f"SageMaker error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating training job: {e}", exc_info=True)
            raise

    async def get_training_job_status(self, job_name: str) -> Dict[str, Any]:
        """
        Get status of a training job.

        Args:
            job_name: Training job name

        Returns:
            Job status information
        """
        try:
            response = self.sagemaker.describe_training_job(
                TrainingJobName=job_name
            )

            status = response["TrainingJobStatus"]
            progress = self._calculate_progress(response)

            return {
                "job_name": job_name,
                "status": status.lower(),
                "progress": progress,
                "created_at": response.get("CreationTime"),
                "started_at": response.get("TrainingStartTime"),
                "ended_at": response.get("TrainingEndTime"),
                "billable_time_seconds": response.get("BillableTimeInSeconds", 0),
                "instance_type": response.get("ResourceConfig", {}).get("InstanceType"),
                "model_artifacts": response.get("ModelArtifacts", {}).get("S3ModelArtifacts"),
                "failure_reason": response.get("FailureReason"),
            }

        except ClientError as e:
            logger.error(f"Error getting training job status: {e}")
            raise

    async def stop_training_job(self, job_name: str) -> None:
        """
        Stop a running training job.

        Args:
            job_name: Training job name
        """
        try:
            logger.info(f"Stopping training job: {job_name}")

            self.sagemaker.stop_training_job(
                TrainingJobName=job_name
            )

            logger.info(f"Training job stop requested: {job_name}")

        except ClientError as e:
            logger.error(f"Error stopping training job: {e}")
            raise

    async def get_training_metrics(self, job_name: str) -> Dict[str, Any]:
        """
        Get training metrics from CloudWatch.

        Args:
            job_name: Training job name

        Returns:
            Training metrics
        """
        # TODO: Query CloudWatch for training metrics
        # For now, return mock data
        return {
            "train_loss": [0.52, 0.38, 0.24, 0.21],
            "val_loss": [0.56, 0.42, 0.28, 0.24],
            "f1": [0.76, 0.82, 0.86, 0.87],
        }

    def _calculate_progress(self, job_info: Dict[str, Any]) -> int:
        """
        Calculate training progress percentage.

        Args:
            job_info: Training job info from describe_training_job

        Returns:
            Progress percentage (0-100)
        """
        status = job_info["TrainingJobStatus"]

        if status == "Completed":
            return 100
        elif status == "Failed" or status == "Stopped":
            return 0
        elif status == "InProgress":
            # Estimate based on time
            started_at = job_info.get("TrainingStartTime")
            max_runtime = job_info.get("ResourceConfig", {}).get("MaxRuntimeInSeconds", 7200)

            if started_at:
                elapsed = (datetime.utcnow() - started_at.replace(tzinfo=None)).total_seconds()
                progress = min(int((elapsed / max_runtime) * 100), 95)
                return progress

            return 10  # Just started
        else:
            return 0


# Singleton instance
_sagemaker_service: Optional[SageMakerService] = None


def get_sagemaker_service() -> SageMakerService:
    """Get or create SageMaker service instance."""
    global _sagemaker_service

    if _sagemaker_service is None:
        _sagemaker_service = SageMakerService()

    return _sagemaker_service
