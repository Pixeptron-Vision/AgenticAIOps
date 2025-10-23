"""
Quota Management Service.

Handles SageMaker instance quota tracking in DynamoDB.
"""

import logging
from typing import Dict, Any, Optional

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

from llmops_agent.config import settings

logger = logging.getLogger(__name__)


class QuotaService:
    """Service for managing instance quotas."""

    def __init__(self):
        """Initialize quota service."""
        self.dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
        self.table = self.dynamodb.Table("llmops-instance-quotas")

    async def reserve_instance(self, instance_type: str, job_id: str) -> Dict[str, Any]:
        """
        Reserve an instance for a training job (decrement available).

        Uses DynamoDB atomic updates to prevent race conditions.

        Args:
            instance_type: Instance type to reserve
            job_id: Training job ID (for tracking)

        Returns:
            Success status and updated quota info
        """
        try:
            # Atomic update: decrement available, increment in_use
            response = self.table.update_item(
                Key={"instance_type": instance_type},
                UpdateExpression="SET in_use = in_use + :inc, available = available - :dec",
                ConditionExpression="available > :zero",  # Only if available > 0
                ExpressionAttributeValues={
                    ":inc": 1,
                    ":dec": 1,
                    ":zero": 0,
                },
                ReturnValues="ALL_NEW",
            )

            updated = response["Attributes"]
            logger.info(
                f"Reserved {instance_type} for job {job_id}: "
                f"{updated['available']}/{updated['total_quota']} remaining"
            )

            return {
                "success": True,
                "instance_type": instance_type,
                "available": int(updated["available"]),
                "in_use": int(updated["in_use"]),
                "total": int(updated["total_quota"]),
            }

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning(f"No quota available for {instance_type} (job {job_id})")
                return {
                    "success": False,
                    "error": "No quota available",
                    "instance_type": instance_type,
                }
            else:
                logger.error(f"Error reserving {instance_type}: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "instance_type": instance_type,
                }

    async def release_instance(self, instance_type: str, job_id: str) -> Dict[str, Any]:
        """
        Release an instance after job completes (increment available).

        Args:
            instance_type: Instance type to release
            job_id: Training job ID (for tracking)

        Returns:
            Success status and updated quota info
        """
        try:
            # Atomic update: increment available, decrement in_use
            response = self.table.update_item(
                Key={"instance_type": instance_type},
                UpdateExpression="SET available = available + :inc, in_use = in_use - :dec",
                ConditionExpression="in_use > :zero",  # Only if in_use > 0
                ExpressionAttributeValues={
                    ":inc": 1,
                    ":dec": 1,
                    ":zero": 0,
                },
                ReturnValues="ALL_NEW",
            )

            updated = response["Attributes"]
            logger.info(
                f"Released {instance_type} from job {job_id}: "
                f"{updated['available']}/{updated['total_quota']} now available"
            )

            return {
                "success": True,
                "instance_type": instance_type,
                "available": int(updated["available"]),
                "in_use": int(updated["in_use"]),
                "total": int(updated["total_quota"]),
            }

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning(f"Cannot release {instance_type} - already at 0 in_use")
                return {
                    "success": False,
                    "error": "No instances to release",
                    "instance_type": instance_type,
                }
            else:
                logger.error(f"Error releasing {instance_type}: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "instance_type": instance_type,
                }

    async def get_quota_info(self, instance_type: str) -> Optional[Dict[str, Any]]:
        """Get current quota information for an instance type."""
        try:
            response = self.table.get_item(Key={"instance_type": instance_type})

            if "Item" not in response:
                return None

            item = response["Item"]
            return {
                "instance_type": instance_type,
                "total_quota": int(item["total_quota"]),
                "in_use": int(item["in_use"]),
                "available": int(item["available"]),
                "hourly_rate_usd": float(item["hourly_rate_usd"]),
                "vram_gb": int(item.get("vram_gb", 0)),
            }

        except Exception as e:
            logger.error(f"Error getting quota for {instance_type}: {e}")
            return None

    async def sync_with_sagemaker(self) -> Dict[str, Any]:
        """
        Sync quota table with actual SageMaker job states.

        This is a safety mechanism to ensure quotas stay in sync.
        Should be called periodically or after system restart.

        Returns:
            Sync results with corrections made
        """
        logger.info("Syncing quota table with SageMaker...")

        # Get all running jobs from SageMaker
        sagemaker = boto3.client("sagemaker", region_name=settings.aws_region)

        try:
            response = sagemaker.list_training_jobs(
                StatusEquals="InProgress",
                MaxResults=100,
            )

            running_jobs = response.get("TrainingJobSummaries", [])

            # Count jobs by instance type
            instance_counts = {}
            for job in running_jobs:
                instance_type = job.get("ResourceConfig", {}).get("InstanceType")
                if instance_type:
                    instance_counts[instance_type] = instance_counts.get(instance_type, 0) + 1

            logger.info(f"Found {len(running_jobs)} running SageMaker jobs")
            logger.info(f"Instance usage from SageMaker: {instance_counts}")

            # Update quota table to match reality
            corrections = []
            for instance_type, actual_in_use in instance_counts.items():
                quota_info = await self.get_quota_info(instance_type)

                if quota_info:
                    current_in_use = quota_info["in_use"]
                    if current_in_use != actual_in_use:
                        # Correct the mismatch
                        total = quota_info["total_quota"]
                        new_available = total - actual_in_use

                        self.table.update_item(
                            Key={"instance_type": instance_type},
                            UpdateExpression="SET in_use = :in_use, available = :available",
                            ExpressionAttributeValues={
                                ":in_use": actual_in_use,
                                ":available": new_available,
                            },
                        )

                        corrections.append({
                            "instance_type": instance_type,
                            "old_in_use": current_in_use,
                            "new_in_use": actual_in_use,
                            "corrected": True,
                        })

                        logger.warning(
                            f"Corrected quota for {instance_type}: "
                            f"{current_in_use} -> {actual_in_use} in_use"
                        )

            return {
                "success": True,
                "running_jobs": len(running_jobs),
                "corrections": corrections,
            }

        except Exception as e:
            logger.error(f"Error syncing with SageMaker: {e}")
            return {
                "success": False,
                "error": str(e),
            }


# Singleton instance
_quota_service = None


def get_quota_service() -> QuotaService:
    """Get or create quota service singleton."""
    global _quota_service
    if _quota_service is None:
        _quota_service = QuotaService()
    return _quota_service
