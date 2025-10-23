"""
Amazon DynamoDB service client.

Provides high-level interface for DynamoDB operations (jobs, sessions, models).
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

from llmops_agent.config import settings

logger = logging.getLogger(__name__)


class DynamoDBService:
    """Service for interacting with Amazon DynamoDB."""

    def __init__(self):
        """Initialize DynamoDB client."""
        self.dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)

        # Table references
        self.jobs_table = self.dynamodb.Table(settings.dynamodb_table_jobs)
        self.sessions_table = self.dynamodb.Table(settings.dynamodb_table_sessions)
        self.models_table = self.dynamodb.Table(settings.dynamodb_table_models)

    # ================================================================
    # Jobs Table Operations
    # ================================================================

    async def create_job(self, job_data: Dict[str, Any]) -> str:
        """
        Create a new training job record.

        Args:
            job_data: Job configuration and metadata

        Returns:
            Job ID
        """
        try:
            job_id = f"job-{uuid4().hex[:12]}"
            timestamp = datetime.utcnow().isoformat()

            item = {
                "job_id": job_id,
                "created_at": timestamp,
                "updated_at": timestamp,
                "status": "pending",
                "progress": 0,
                **job_data,
            }

            logger.info(f"Creating job: {job_id}")

            self.jobs_table.put_item(Item=item)

            return job_id

        except ClientError as e:
            logger.error(f"Error creating job: {e}")
            raise

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a job by ID.

        Args:
            job_id: Job ID

        Returns:
            Job data or None if not found
        """
        try:
            response = self.jobs_table.get_item(Key={"job_id": job_id})

            return response.get("Item")

        except ClientError as e:
            logger.error(f"Error getting job: {e}")
            raise

    async def update_job(
        self,
        job_id: str,
        updates: Dict[str, Any],
    ) -> None:
        """
        Update a job record.

        Args:
            job_id: Job ID
            updates: Fields to update
        """
        try:
            # Build update expression
            update_expr = "SET updated_at = :timestamp"
            expr_values = {":timestamp": datetime.utcnow().isoformat()}

            for key, value in updates.items():
                update_expr += f", {key} = :{key}"
                expr_values[f":{key}"] = value

            self.jobs_table.update_item(
                Key={"job_id": job_id},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_values,
            )

            logger.debug(f"Updated job {job_id}")

        except ClientError as e:
            logger.error(f"Error updating job: {e}")
            raise

    async def list_jobs(
        self,
        session_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        List jobs with optional filtering.

        Args:
            session_id: Filter by session ID
            status: Filter by status
            limit: Maximum number of jobs to return

        Returns:
            List of job records
        """
        try:
            # TODO: Add proper indexing for efficient queries
            # For now, scan the table (not efficient for large datasets)

            scan_kwargs = {"Limit": limit}

            # Add filter expression
            filter_expr = None
            if session_id:
                filter_expr = Key("session_id").eq(session_id)
            if status:
                status_filter = Key("status").eq(status)
                filter_expr = status_filter if not filter_expr else filter_expr & status_filter

            if filter_expr:
                scan_kwargs["FilterExpression"] = filter_expr

            response = self.jobs_table.scan(**scan_kwargs)

            return response.get("Items", [])

        except ClientError as e:
            logger.error(f"Error listing jobs: {e}")
            raise

    # ================================================================
    # Sessions Table Operations
    # ================================================================

    async def create_session(self, user_id: str) -> str:
        """
        Create a new session.

        Args:
            user_id: User ID

        Returns:
            Session ID
        """
        try:
            session_id = f"session-{uuid4().hex[:12]}"
            timestamp = datetime.utcnow().isoformat()

            item = {
                "session_id": session_id,
                "user_id": user_id,
                "created_at": timestamp,
                "updated_at": timestamp,
                "budget_limit": settings.default_session_budget_usd,
                "budget_spent": 0.0,
                "active_jobs": [],
            }

            self.sessions_table.put_item(Item=item)

            logger.info(f"Created session: {session_id}")

            return session_id

        except ClientError as e:
            logger.error(f"Error creating session: {e}")
            raise

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session data or None if not found
        """
        try:
            response = self.sessions_table.get_item(Key={"session_id": session_id})

            return response.get("Item")

        except ClientError as e:
            logger.error(f"Error getting session: {e}")
            raise

    async def update_session_budget(
        self,
        session_id: str,
        amount_spent: float,
    ) -> None:
        """
        Update session budget spent.

        Args:
            session_id: Session ID
            amount_spent: Amount to add to budget_spent
        """
        try:
            self.sessions_table.update_item(
                Key={"session_id": session_id},
                UpdateExpression="SET budget_spent = budget_spent + :amount, updated_at = :timestamp",
                ExpressionAttributeValues={
                    ":amount": amount_spent,
                    ":timestamp": datetime.utcnow().isoformat(),
                },
            )

        except ClientError as e:
            logger.error(f"Error updating session budget: {e}")
            raise

    # ================================================================
    # Models Table Operations
    # ================================================================

    async def add_model_to_registry(self, model_data: Dict[str, Any]) -> None:
        """
        Add a model to the registry.

        Args:
            model_data: Model metadata
        """
        try:
            timestamp = datetime.utcnow().isoformat()

            item = {
                "model_id": model_data["model_id"],
                "created_at": timestamp,
                "updated_at": timestamp,
                **model_data,
            }

            self.models_table.put_item(Item=item)

            logger.info(f"Added model to registry: {model_data['model_id']}")

        except ClientError as e:
            logger.error(f"Error adding model to registry: {e}")
            raise

    async def get_model_from_registry(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a model from the registry.

        Args:
            model_id: Model ID

        Returns:
            Model data or None if not found
        """
        try:
            response = self.models_table.get_item(Key={"model_id": model_id})

            return response.get("Item")

        except ClientError as e:
            logger.error(f"Error getting model from registry: {e}")
            raise


# Singleton instance
_dynamodb_service: Optional[DynamoDBService] = None


def get_dynamodb_service() -> DynamoDBService:
    """Get or create DynamoDB service instance."""
    global _dynamodb_service

    if _dynamodb_service is None:
        _dynamodb_service = DynamoDBService()

    return _dynamodb_service
