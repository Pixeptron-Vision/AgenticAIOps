"""
Budget Management API Routes

Provides endpoints for managing budgets:
- Get global budget
- Update global budget limit
- Get session budget
- Update session budget limit

Created: October 22, 2025
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from llmops_agent.services.budget_service import get_budget_service

logger = logging.getLogger(__name__)

router = APIRouter()
budget_service = get_budget_service()


# ========== Pydantic Models ==========


class BudgetInfo(BaseModel):
    """Budget information model."""

    id: str
    type: str  # "global" or "session"
    limit: float
    spent: float
    remaining: float
    session_id: Optional[str] = None
    session_name: Optional[str] = None
    updated_at: int
    updated_at_iso: str


class UpdateBudgetLimitRequest(BaseModel):
    """Request to update budget limit."""

    limit: float = Field(..., gt=0, description="New budget limit (must be > 0)")


class BudgetUpdateResponse(BaseModel):
    """Response after updating budget."""

    success: bool
    budget: BudgetInfo
    message: str


# ========== API Endpoints ==========


@router.get("/budgets/global", response_model=BudgetInfo)
async def get_global_budget() -> BudgetInfo:
    """
    Get global budget information.

    Returns:
        Global budget details
    """
    try:
        logger.info("Getting global budget")

        budget = budget_service.get_global_budget()

        return BudgetInfo(
            id=budget["id"],
            type=budget["type"],
            limit=budget["limit"],
            spent=budget["spent"],
            remaining=budget["remaining"],
            updated_at=budget["updated_at"],
            updated_at_iso=budget["updated_at_iso"],
        )

    except Exception as e:
        logger.error(f"Error getting global budget: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get global budget: {str(e)}",
        )


@router.put("/budgets/global", response_model=BudgetUpdateResponse)
async def update_global_budget(
    request: UpdateBudgetLimitRequest,
) -> BudgetUpdateResponse:
    """
    Update global budget limit.

    Args:
        request: New budget limit

    Returns:
        Updated budget information
    """
    try:
        logger.info(f"Updating global budget limit to ${request.limit}")

        updated_budget = budget_service.update_global_budget_limit(request.limit)

        return BudgetUpdateResponse(
            success=True,
            budget=BudgetInfo(
                id=updated_budget["id"],
                type=updated_budget["type"],
                limit=updated_budget["limit"],
                spent=updated_budget["spent"],
                remaining=updated_budget["remaining"],
                updated_at=updated_budget["updated_at"],
                updated_at_iso=updated_budget["updated_at_iso"],
            ),
            message=f"Global budget limit updated to ${request.limit:.2f}",
        )

    except Exception as e:
        logger.error(f"Error updating global budget: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update global budget: {str(e)}",
        )


@router.get("/budgets/session/{session_id}", response_model=BudgetInfo)
async def get_session_budget(session_id: str) -> BudgetInfo:
    """
    Get budget for a specific session.

    Args:
        session_id: Session ID

    Returns:
        Session budget details
    """
    try:
        logger.info(f"Getting budget for session: {session_id}")

        budget = budget_service.get_session_budget(session_id)

        if not budget:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Budget not found for session: {session_id}",
            )

        return BudgetInfo(
            id=budget["id"],
            type=budget["type"],
            limit=budget["limit"],
            spent=budget["spent"],
            remaining=budget["remaining"],
            session_id=budget.get("session_id"),
            session_name=budget.get("session_name"),
            updated_at=budget["updated_at"],
            updated_at_iso=budget["updated_at_iso"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session budget for {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session budget: {str(e)}",
        )


@router.put("/budgets/session/{session_id}", response_model=BudgetUpdateResponse)
async def update_session_budget(
    session_id: str, request: UpdateBudgetLimitRequest
) -> BudgetUpdateResponse:
    """
    Update budget limit for a specific session.

    Args:
        session_id: Session ID
        request: New budget limit

    Returns:
        Updated budget information
    """
    try:
        logger.info(f"Updating budget limit for session {session_id} to ${request.limit}")

        updated_budget = budget_service.update_session_budget_limit(
            session_id, request.limit
        )

        return BudgetUpdateResponse(
            success=True,
            budget=BudgetInfo(
                id=updated_budget["id"],
                type=updated_budget["type"],
                limit=updated_budget["limit"],
                spent=updated_budget["spent"],
                remaining=updated_budget["remaining"],
                session_id=updated_budget.get("session_id"),
                session_name=updated_budget.get("session_name"),
                updated_at=updated_budget["updated_at"],
                updated_at_iso=updated_budget["updated_at_iso"],
            ),
            message=f"Session budget limit updated to ${request.limit:.2f}",
        )

    except ValueError as e:
        # Session budget not found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating session budget for {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update session budget: {str(e)}",
        )


@router.get("/budgets/summary")
async def get_budgets_summary():
    """
    Get summary of all budgets (global + all sessions).

    Returns:
        Summary with global budget and list of session budgets
    """
    try:
        logger.info("Getting budgets summary")

        # Get global budget
        global_budget = budget_service.get_global_budget()

        # Get all session budgets
        session_budgets = budget_service.list_session_budgets()

        # Calculate totals
        total_sessions = len(session_budgets)
        total_session_spent = sum(b["spent"] for b in session_budgets)
        total_session_limit = sum(b["limit"] for b in session_budgets)

        return {
            "global_budget": BudgetInfo(
                id=global_budget["id"],
                type=global_budget["type"],
                limit=global_budget["limit"],
                spent=global_budget["spent"],
                remaining=global_budget["remaining"],
                updated_at=global_budget["updated_at"],
                updated_at_iso=global_budget["updated_at_iso"],
            ),
            "session_budgets_count": total_sessions,
            "session_budgets_total_limit": total_session_limit,
            "session_budgets_total_spent": total_session_spent,
            "session_budgets": [
                BudgetInfo(
                    id=b["id"],
                    type=b["type"],
                    limit=b["limit"],
                    spent=b["spent"],
                    remaining=b["remaining"],
                    session_id=b.get("session_id"),
                    session_name=b.get("session_name"),
                    updated_at=b["updated_at"],
                    updated_at_iso=b["updated_at_iso"],
                )
                for b in session_budgets
            ],
        }

    except Exception as e:
        logger.error(f"Error getting budgets summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get budgets summary: {str(e)}",
        )
