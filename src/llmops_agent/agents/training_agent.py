"""
Training Agent.

Responsible for launching and monitoring SageMaker training jobs.
"""

import logging
from typing import Any, Dict, Optional
from uuid import uuid4

from llmops_agent.config import settings
from llmops_agent.services.dynamodb_service import get_dynamodb_service
from llmops_agent.services.sagemaker_service import get_sagemaker_service

logger = logging.getLogger(__name__)


class TrainingAgent:
    """Agent for training job management."""

    def __init__(self):
        """Initialize the training agent."""
        self.agent_name = "Training"
        self.sagemaker = get_sagemaker_service()
        self.dynamodb = get_dynamodb_service()

    async def launch_training_job(
        self,
        session_id: str,
        model_id: str,
        dataset_s3_uri: str,
        instance_type: str = "ml.g5.xlarge",
        use_peft: bool = True,
        hyperparameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Launch a SageMaker training job.

        Args:
            session_id: Session ID
            model_id: Hugging Face model ID
            dataset_s3_uri: S3 URI of preprocessed dataset
            instance_type: SageMaker instance type
            use_peft: Use LoRA/PEFT
            hyperparameters: Additional hyperparameters

        Returns:
            Job information
        """
        try:
            # Generate job name
            timestamp = uuid4().hex[:8]
            job_name = f"llmops-{model_id.split('/')[-1]}-{timestamp}"

            logger.info(f"Launching training job: {job_name}")

            # Output S3 URI
            output_s3_uri = f"s3://{settings.s3_bucket_models}/{settings.s3_prefix_checkpoints}"

            # Create training job in SageMaker
            sagemaker_job_name = await self.sagemaker.create_training_job(
                job_name=job_name,
                model_id=model_id,
                dataset_s3_uri=dataset_s3_uri,
                output_s3_uri=output_s3_uri,
                instance_type=instance_type,
                hyperparameters=hyperparameters,
                use_peft=use_peft,
            )

            # Create job record in DynamoDB
            job_id = await self.dynamodb.create_job({
                "session_id": session_id,
                "sagemaker_job_name": sagemaker_job_name,
                "model_id": model_id,
                "instance_type": instance_type,
                "dataset_s3_uri": dataset_s3_uri,
                "use_peft": use_peft,
            })

            logger.info(f"Training job created: {job_id}")

            return {
                "success": True,
                "job_id": job_id,
                "sagemaker_job_name": sagemaker_job_name,
                "status": "pending",
            }

        except Exception as e:
            logger.error(f"Error launching training job: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get training job status.

        Args:
            job_id: Job ID

        Returns:
            Job status and metrics
        """
        try:
            # Get job from DynamoDB
            job = await self.dynamodb.get_job(job_id)

            if not job:
                return {
                    "success": False,
                    "error": "Job not found",
                }

            # Get status from SageMaker
            sagemaker_job_name = job.get("sagemaker_job_name")

            if sagemaker_job_name:
                sm_status = await self.sagemaker.get_training_job_status(sagemaker_job_name)

                # Update DynamoDB with latest status
                await self.dynamodb.update_job(job_id, {
                    "status": sm_status["status"],
                    "progress": sm_status["progress"],
                })

                return {
                    "success": True,
                    "job_id": job_id,
                    **sm_status,
                }

            return {
                "success": True,
                "job_id": job_id,
                **job,
            }

        except Exception as e:
            logger.error(f"Error getting job status: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    async def stop_job(self, job_id: str) -> Dict[str, Any]:
        """
        Stop a running training job.

        Args:
            job_id: Job ID

        Returns:
            Confirmation
        """
        try:
            # Get job from DynamoDB
            job = await self.dynamodb.get_job(job_id)

            if not job:
                return {
                    "success": False,
                    "error": "Job not found",
                }

            sagemaker_job_name = job.get("sagemaker_job_name")

            if sagemaker_job_name:
                # Stop SageMaker job
                await self.sagemaker.stop_training_job(sagemaker_job_name)

                # Update DynamoDB
                await self.dynamodb.update_job(job_id, {
                    "status": "stopped",
                })

            return {
                "success": True,
                "job_id": job_id,
                "status": "stopped",
            }

        except Exception as e:
            logger.error(f"Error stopping job: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }
