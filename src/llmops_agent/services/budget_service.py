"""
Budget Service

Handles all budget-related operations:
- Get/update global budget
- Get/update session budgets
- Track spending from jobs
- Calculate remaining budgets

Created: October 22, 2025
"""

import boto3
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class BudgetService:
    """Service for managing global and session budgets."""

    def __init__(self, region_name: str = "us-east-1"):
        """Initialize budget service with DynamoDB client."""
        self.dynamodb = boto3.resource("dynamodb", region_name=region_name)
        self.budgets_table = self.dynamodb.Table("llmops-budgets")
        self.sessions_table = self.dynamodb.Table("llmops-sessions")

    # ========== Global Budget Operations ==========

    def get_global_budget(self) -> Dict:
        """
        Get global budget.

        Returns:
            {
                "id": "global",
                "type": "global",
                "limit": 500.00,
                "spent": 125.50,
                "remaining": 374.50,
                ...
            }
        """
        try:
            response = self.budgets_table.get_item(Key={"id": "global"})
            budget = response.get("Item")

            if not budget:
                # Initialize global budget if doesn't exist
                logger.warning("Global budget not found, initializing...")
                return self._initialize_global_budget()

            return self._convert_decimals(budget)
        except Exception as e:
            logger.error(f"Error getting global budget: {e}")
            raise

    def update_global_budget_limit(self, new_limit: float) -> Dict:
        """
        Update global budget limit.

        Args:
            new_limit: New budget limit in USD

        Returns:
            Updated budget record
        """
        try:
            now = int(datetime.now().timestamp())
            now_iso = datetime.now().isoformat()

            # Get current spent to recalculate remaining
            current_budget = self.get_global_budget()
            spent = Decimal(str(current_budget.get("spent", 0)))
            new_limit_decimal = Decimal(str(new_limit))
            remaining = new_limit_decimal - spent

            response = self.budgets_table.update_item(
                Key={"id": "global"},
                UpdateExpression="SET #limit = :limit, remaining = :remaining, updated_at = :updated, updated_at_iso = :updated_iso",
                ExpressionAttributeNames={"#limit": "limit"},
                ExpressionAttributeValues={
                    ":limit": new_limit_decimal,
                    ":remaining": remaining,
                    ":updated": now,
                    ":updated_iso": now_iso,
                },
                ReturnValues="ALL_NEW",
            )

            return self._convert_decimals(response["Attributes"])
        except Exception as e:
            logger.error(f"Error updating global budget limit: {e}")
            raise

    def add_to_global_spent(self, amount: float) -> Dict:
        """
        Add to global spent amount (called when job completes).

        Args:
            amount: Amount to add to spent

        Returns:
            Updated budget record
        """
        try:
            now = int(datetime.now().timestamp())
            now_iso = datetime.now().isoformat()
            amount_decimal = Decimal(str(amount))

            response = self.budgets_table.update_item(
                Key={"id": "global"},
                UpdateExpression="SET spent = spent + :amount, remaining = #limit - spent, updated_at = :updated, updated_at_iso = :updated_iso",
                ExpressionAttributeNames={"#limit": "limit"},
                ExpressionAttributeValues={
                    ":amount": amount_decimal,
                    ":updated": now,
                    ":updated_iso": now_iso,
                },
                ReturnValues="ALL_NEW",
            )

            logger.info(f"Added ${amount} to global budget spent")
            return self._convert_decimals(response["Attributes"])
        except Exception as e:
            logger.error(f"Error adding to global spent: {e}")
            raise

    # ========== Session Budget Operations ==========

    def get_session_budget(self, session_id: str) -> Optional[Dict]:
        """
        Get budget for a specific session.

        Args:
            session_id: Session ID

        Returns:
            Budget record or None if not found
        """
        try:
            response = self.budgets_table.get_item(Key={"id": session_id})
            budget = response.get("Item")

            if budget:
                return self._convert_decimals(budget)
            else:
                logger.warning(f"Budget not found for session {session_id}")
                return None
        except Exception as e:
            logger.error(f"Error getting session budget for {session_id}: {e}")
            raise

    def create_session_budget(
        self, session_id: str, session_name: str, limit: float = 50.0
    ) -> Dict:
        """
        Create a new session budget.

        Args:
            session_id: Session ID
            session_name: User-friendly session name
            limit: Budget limit (default: $50)

        Returns:
            Created budget record
        """
        try:
            now = int(datetime.now().timestamp())
            now_iso = datetime.now().isoformat()
            limit_decimal = Decimal(str(limit))

            budget_item = {
                "id": session_id,
                "type": "session",
                "session_id": session_id,
                "session_name": session_name,
                "limit": limit_decimal,
                "spent": Decimal("0.00"),
                "remaining": limit_decimal,
                "created_at": now,
                "updated_at": now,
                "updated_at_iso": now_iso,
            }

            self.budgets_table.put_item(Item=budget_item)
            logger.info(f"Created budget for session {session_id} with limit ${limit}")

            return self._convert_decimals(budget_item)
        except Exception as e:
            logger.error(f"Error creating session budget: {e}")
            raise

    def update_session_budget_limit(self, session_id: str, new_limit: float) -> Dict:
        """
        Update session budget limit.

        Args:
            session_id: Session ID
            new_limit: New budget limit in USD

        Returns:
            Updated budget record
        """
        try:
            now = int(datetime.now().timestamp())
            now_iso = datetime.now().isoformat()

            # Get current spent to recalculate remaining
            current_budget = self.get_session_budget(session_id)
            if not current_budget:
                raise ValueError(f"Session budget not found: {session_id}")

            spent = Decimal(str(current_budget.get("spent", 0)))
            new_limit_decimal = Decimal(str(new_limit))
            remaining = new_limit_decimal - spent

            response = self.budgets_table.update_item(
                Key={"id": session_id},
                UpdateExpression="SET #limit = :limit, remaining = :remaining, updated_at = :updated, updated_at_iso = :updated_iso",
                ExpressionAttributeNames={"#limit": "limit"},
                ExpressionAttributeValues={
                    ":limit": new_limit_decimal,
                    ":remaining": remaining,
                    ":updated": now,
                    ":updated_iso": now_iso,
                },
                ReturnValues="ALL_NEW",
            )

            # Also update session table
            self.sessions_table.update_item(
                Key={"session_id": session_id},
                UpdateExpression="SET budget_limit = :limit, updated_at = :updated, updated_at_iso = :updated_iso",
                ExpressionAttributeValues={
                    ":limit": new_limit_decimal,
                    ":updated": now,
                    ":updated_iso": now_iso,
                },
            )

            logger.info(f"Updated budget limit for session {session_id} to ${new_limit}")
            return self._convert_decimals(response["Attributes"])
        except Exception as e:
            logger.error(f"Error updating session budget limit: {e}")
            raise

    def add_to_session_spent(self, session_id: str, amount: float) -> Dict:
        """
        Add to session spent amount (called when job completes).

        Args:
            session_id: Session ID
            amount: Amount to add to spent

        Returns:
            Updated budget record
        """
        try:
            now = int(datetime.now().timestamp())
            now_iso = datetime.now().isoformat()
            amount_decimal = Decimal(str(amount))

            response = self.budgets_table.update_item(
                Key={"id": session_id},
                UpdateExpression="SET spent = spent + :amount, remaining = #limit - spent, updated_at = :updated, updated_at_iso = :updated_iso",
                ExpressionAttributeNames={"#limit": "limit"},
                ExpressionAttributeValues={
                    ":amount": amount_decimal,
                    ":updated": now,
                    ":updated_iso": now_iso,
                },
                ReturnValues="ALL_NEW",
            )

            logger.info(f"Added ${amount} to session {session_id} spent")
            return self._convert_decimals(response["Attributes"])
        except Exception as e:
            logger.error(f"Error adding to session spent: {e}")
            raise

    def delete_session_budget(self, session_id: str) -> None:
        """
        Delete a session's budget record (permanent deletion).

        Args:
            session_id: Session ID

        Returns:
            None
        """
        try:
            self.budgets_table.delete_item(Key={"id": session_id})
            logger.info(f"Deleted budget record for session {session_id}")
        except Exception as e:
            logger.error(f"Error deleting session budget: {e}")
            raise

    def list_session_budgets(self) -> List[Dict]:
        """
        List all session budgets.

        Returns:
            List of session budget records
        """
        try:
            response = self.budgets_table.scan(
                FilterExpression="#type = :type",
                ExpressionAttributeNames={"#type": "type"},
                ExpressionAttributeValues={":type": "session"},
            )

            budgets = response.get("Items", [])

            # Handle pagination
            while "LastEvaluatedKey" in response:
                response = self.budgets_table.scan(
                    FilterExpression="#type = :type",
                    ExpressionAttributeNames={"#type": "type"},
                    ExpressionAttributeValues={":type": "session"},
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                )
                budgets.extend(response.get("Items", []))

            return [self._convert_decimals(b) for b in budgets]
        except Exception as e:
            logger.error(f"Error listing session budgets: {e}")
            raise

    # ========== Job Integration ==========

    def update_budgets_for_job(self, session_id: str, job_cost: float) -> Dict:
        """
        Update both session and global budgets when a job completes.

        Args:
            session_id: Session ID
            job_cost: Cost of the completed job

        Returns:
            {
                "session_budget": {...},
                "global_budget": {...}
            }
        """
        try:
            # Update session budget
            session_budget = self.add_to_session_spent(session_id, job_cost)

            # Update global budget
            global_budget = self.add_to_global_spent(job_cost)

            logger.info(
                f"Updated budgets for job: session={session_id}, cost=${job_cost}"
            )

            return {
                "session_budget": session_budget,
                "global_budget": global_budget,
            }
        except Exception as e:
            logger.error(f"Error updating budgets for job: {e}")
            raise

    # ========== Helper Methods ==========

    def _initialize_global_budget(self, limit: float = 500.0) -> Dict:
        """Initialize global budget if it doesn't exist."""
        now = int(datetime.now().timestamp())
        now_iso = datetime.now().isoformat()
        limit_decimal = Decimal(str(limit))

        budget_item = {
            "id": "global",
            "type": "global",
            "limit": limit_decimal,
            "spent": Decimal("0.00"),
            "remaining": limit_decimal,
            "created_at": now,
            "updated_at": now,
            "updated_at_iso": now_iso,
        }

        self.budgets_table.put_item(Item=budget_item)
        logger.info(f"Initialized global budget with limit ${limit}")

        return self._convert_decimals(budget_item)

    @staticmethod
    def _convert_decimals(obj):
        """Convert DynamoDB Decimal objects to float for JSON serialization."""
        if isinstance(obj, list):
            return [BudgetService._convert_decimals(item) for item in obj]
        elif isinstance(obj, dict):
            return {
                key: BudgetService._convert_decimals(value)
                for key, value in obj.items()
            }
        elif isinstance(obj, Decimal):
            return float(obj)
        else:
            return obj


# Singleton instance
_budget_service = None


def get_budget_service() -> BudgetService:
    """Get or create budget service singleton."""
    global _budget_service
    if _budget_service is None:
        _budget_service = BudgetService()
    return _budget_service
