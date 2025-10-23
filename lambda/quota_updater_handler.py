"""
Lambda Function: SageMaker Quota Updater

Triggered by EventBridge when SageMaker training job state changes.
Updates DynamoDB quota table to track instance usage in real-time.

EventBridge Rule Pattern:
{
  "source": ["aws.sagemaker"],
  "detail-type": ["SageMaker Training Job State Change"],
  "detail": {
    "TrainingJobStatus": ["InProgress", "Completed", "Failed", "Stopped"]
  }
}
"""

import json
import logging
import os
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
quota_table = dynamodb.Table(os.environ.get("QUOTA_TABLE", "llmops-instance-quotas"))


def lambda_handler(event, context):
    """
    Handle SageMaker training job state change events.

    Event structure:
    {
      "detail": {
        "TrainingJobName": "job-name",
        "TrainingJobStatus": "InProgress|Completed|Failed|Stopped",
        "ResourceConfig": {
          "InstanceType": "ml.g5.xlarge",
          "InstanceCount": 1
        }
      }
    }
    """
    try:
        detail = event.get("detail", {})
        job_name = detail.get("TrainingJobName")
        job_status = detail.get("TrainingJobStatus")
        resource_config = detail.get("ResourceConfig", {})
        instance_type = resource_config.get("InstanceType")
        instance_count = resource_config.get("InstanceCount", 1)

        logger.info(
            f"Job: {job_name}, Status: {job_status}, "
            f"Instance: {instance_type} x{instance_count}"
        )

        if not instance_type:
            logger.warning(f"No instance type in event for job {job_name}")
            return {"statusCode": 200, "body": "No instance type"}

        # InProgress = reserve instance (decrement available)
        if job_status == "InProgress":
            result = reserve_instance(instance_type, instance_count, job_name)
            logger.info(f"Reserved {instance_type}: {result}")

        # Completed/Failed/Stopped = release instance (increment available)
        elif job_status in ["Completed", "Failed", "Stopped"]:
            result = release_instance(instance_type, instance_count, job_name)
            logger.info(f"Released {instance_type}: {result}")

        else:
            logger.info(f"Ignoring status {job_status} for job {job_name}")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Quota updated successfully",
                "job_name": job_name,
                "job_status": job_status,
                "instance_type": instance_type,
            }),
        }

    except Exception as e:
        logger.error(f"Error updating quota: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }


def reserve_instance(instance_type: str, count: int, job_name: str) -> dict:
    """Reserve instance quota (decrement available, increment in_use)."""
    try:
        response = quota_table.update_item(
            Key={"instance_type": instance_type},
            UpdateExpression=(
                "SET in_use = in_use + :count, available = available - :count"
            ),
            ConditionExpression="available >= :count",
            ExpressionAttributeValues={":count": count},
            ReturnValues="ALL_NEW",
        )

        updated = response["Attributes"]
        return {
            "success": True,
            "available": int(updated["available"]),
            "in_use": int(updated["in_use"]),
        }

    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            logger.error(
                f"Cannot reserve {instance_type} for {job_name}: "
                f"insufficient quota"
            )
            return {
                "success": False,
                "error": "Insufficient quota",
            }
        else:
            raise


def release_instance(instance_type: str, count: int, job_name: str) -> dict:
    """Release instance quota (increment available, decrement in_use)."""
    try:
        response = quota_table.update_item(
            Key={"instance_type": instance_type},
            UpdateExpression=(
                "SET available = available + :count, in_use = in_use - :count"
            ),
            ConditionExpression="in_use >= :count",
            ExpressionAttributeValues={":count": count},
            ReturnValues="ALL_NEW",
        )

        updated = response["Attributes"]
        return {
            "success": True,
            "available": int(updated["available"]),
            "in_use": int(updated["in_use"]),
        }

    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            logger.warning(
                f"Cannot release {instance_type} for {job_name}: "
                f"already at 0 in_use"
            )
            return {
                "success": False,
                "error": "Nothing to release",
            }
        else:
            raise
