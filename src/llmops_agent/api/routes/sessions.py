"""
Session Management API Routes

Provides endpoints for managing chat sessions:
- List sessions
- Create session
- Get session details
- Update session (name, budget)
- Archive session

Created: October 22, 2025
"""

import logging
from typing import List, Optional
from uuid import uuid4

import boto3
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from llmops_agent.services.budget_service import get_budget_service

logger = logging.getLogger(__name__)

router = APIRouter()

# DynamoDB client
dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
sessions_table = dynamodb.Table("llmops-sessions")
budget_service = get_budget_service()


# ========== Pydantic Models ==========


class SessionSummary(BaseModel):
    """Summary model for session list."""

    session_id: str
    session_name: str
    created_at: int
    updated_at: int
    last_message_at: Optional[int] = None
    message_count: int = 0
    budget_spent: float = 0.0
    budget_limit: float = 50.0
    is_archived: bool = False


class SessionDetail(BaseModel):
    """Detailed session model with full message history."""

    session_id: str
    session_name: str
    created_at: int
    updated_at: int
    last_message_at: Optional[int] = None
    budget_limit: float = 50.0
    is_archived: bool = False
    messages: List[dict] = []


class CreateSessionRequest(BaseModel):
    """Request to create a new session."""

    session_name: Optional[str] = Field(
        default=None, description="Optional session name"
    )
    budget_limit: Optional[float] = Field(
        default=50.0, description="Session budget limit"
    )


class CreateSessionResponse(BaseModel):
    """Response after creating a session."""

    session_id: str
    session_name: str
    budget_limit: float
    created_at: str


class UpdateSessionRequest(BaseModel):
    """Request to update a session."""

    session_name: Optional[str] = Field(default=None, description="New session name")
    budget_limit: Optional[float] = Field(
        default=None, description="New budget limit"
    )


class SessionsListResponse(BaseModel):
    """Response with list of sessions."""

    sessions: List[SessionSummary]
    total: int


# ========== Helper Functions ==========


def _get_session_from_db(session_id: str) -> Optional[dict]:
    """Get session from DynamoDB."""
    try:
        response = sessions_table.get_item(Key={"session_id": session_id})
        return response.get("Item")
    except Exception as e:
        logger.error(f"Error getting session {session_id}: {e}")
        return None


def _create_session_summary(session_item: dict, budget_info: Optional[dict] = None) -> SessionSummary:
    """Create session summary from DynamoDB item."""
    messages = session_item.get("messages", [])
    message_count = len(messages)

    # Get last message timestamp
    last_message_at = None
    if messages:
        last_msg = messages[-1]
        try:
            from datetime import datetime
            timestamp_str = last_msg.get("timestamp", "")
            if timestamp_str:
                dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                last_message_at = int(dt.timestamp())
        except:
            pass

    # Get budget info
    budget_spent = 0.0
    budget_limit = session_item.get("budget_limit", 50.0)

    if budget_info:
        budget_spent = float(budget_info.get("spent", 0))
        budget_limit = float(budget_info.get("limit", 50.0))

    return SessionSummary(
        session_id=session_item["session_id"],
        session_name=session_item.get("session_name", f"Session {session_item['session_id'][:8]}"),
        created_at=int(session_item.get("created_at", 0)),
        updated_at=int(session_item.get("updated_at", 0)),
        last_message_at=last_message_at,
        message_count=message_count,
        budget_spent=budget_spent,
        budget_limit=float(budget_limit),
        is_archived=session_item.get("is_archived", False),
    )


# ========== API Endpoints ==========


@router.get("/sessions", response_model=SessionsListResponse)
async def list_sessions(
    include_archived: bool = False, limit: int = 100
) -> SessionsListResponse:
    """
    List all sessions.

    Args:
        include_archived: Include archived sessions
        limit: Maximum number of sessions to return

    Returns:
        List of session summaries
    """
    try:
        logger.info(f"Listing sessions (include_archived={include_archived}, limit={limit})")

        # Scan sessions table
        if include_archived:
            response = sessions_table.scan(Limit=limit)
        else:
            response = sessions_table.scan(
                FilterExpression="attribute_not_exists(is_archived) OR is_archived = :false",
                ExpressionAttributeValues={":false": False},
                Limit=limit,
            )

        session_items = response.get("Items", [])

        # Get budget info for all sessions
        sessions_summaries = []
        for item in session_items:
            session_id = item["session_id"]
            budget_info = budget_service.get_session_budget(session_id)
            summary = _create_session_summary(item, budget_info)
            sessions_summaries.append(summary)

        # Sort by last_message_at (most recent first)
        sessions_summaries.sort(
            key=lambda x: x.last_message_at or x.updated_at, reverse=True
        )

        logger.info(f"Found {len(sessions_summaries)} sessions")

        return SessionsListResponse(
            sessions=sessions_summaries, total=len(sessions_summaries)
        )

    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list sessions: {str(e)}",
        )


@router.post("/sessions", response_model=CreateSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(request: CreateSessionRequest) -> CreateSessionResponse:
    """
    Create a new session.

    Args:
        request: Session creation parameters

    Returns:
        Created session details
    """
    try:
        from datetime import datetime
        from decimal import Decimal

        # Generate session ID
        session_id = f"session-{uuid4().hex[:8]}"

        # Generate session name if not provided
        session_name = request.session_name or f"New Session"

        # Timestamps
        now = int(datetime.now().timestamp())
        now_iso = datetime.now().isoformat()

        # Create session record
        session_item = {
            "session_id": session_id,
            "session_name": session_name,
            "budget_limit": Decimal(str(request.budget_limit)),
            "is_archived": False,
            "messages": [],
            "created_at": now,
            "updated_at": now,
            "updated_at_iso": now_iso,
        }

        sessions_table.put_item(Item=session_item)
        logger.info(f"Created session: {session_id}")

        # Create budget record
        budget_service.create_session_budget(
            session_id=session_id,
            session_name=session_name,
            limit=request.budget_limit,
        )
        logger.info(f"Created budget for session: {session_id}")

        return CreateSessionResponse(
            session_id=session_id,
            session_name=session_name,
            budget_limit=request.budget_limit,
            created_at=now_iso,
        )

    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {str(e)}",
        )


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str) -> SessionDetail:
    """
    Get session details with full message history.

    Args:
        session_id: Session ID

    Returns:
        Detailed session information
    """
    try:
        logger.info(f"Getting session details: {session_id}")

        session_item = _get_session_from_db(session_id)

        if not session_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session not found: {session_id}",
            )

        # Get last message timestamp
        messages = session_item.get("messages", [])
        last_message_at = None
        if messages:
            last_msg = messages[-1]
            try:
                from datetime import datetime
                timestamp_str = last_msg.get("timestamp", "")
                if timestamp_str:
                    dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                    last_message_at = int(dt.timestamp())
            except:
                pass

        return SessionDetail(
            session_id=session_item["session_id"],
            session_name=session_item.get("session_name", f"Session {session_id[:8]}"),
            created_at=int(session_item.get("created_at", 0)),
            updated_at=int(session_item.get("updated_at", 0)),
            last_message_at=last_message_at,
            budget_limit=float(session_item.get("budget_limit", 50.0)),
            is_archived=session_item.get("is_archived", False),
            messages=messages,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session: {str(e)}",
        )


@router.put("/sessions/{session_id}")
async def update_session(session_id: str, request: UpdateSessionRequest):
    """
    Update session details (name and/or budget limit).

    Args:
        session_id: Session ID
        request: Update parameters

    Returns:
        Updated session details
    """
    try:
        from datetime import datetime
        from decimal import Decimal

        logger.info(f"Updating session: {session_id}")

        # Verify session exists
        session_item = _get_session_from_db(session_id)
        if not session_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session not found: {session_id}",
            )

        # Build update expression
        update_parts = []
        expr_values = {}
        expr_names = {}

        if request.session_name is not None:
            update_parts.append("#name = :name")
            expr_names["#name"] = "session_name"
            expr_values[":name"] = request.session_name

        if request.budget_limit is not None:
            update_parts.append("budget_limit = :limit")
            expr_values[":limit"] = Decimal(str(request.budget_limit))

        if not update_parts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No update parameters provided",
            )

        # Always update timestamp
        now = int(datetime.now().timestamp())
        now_iso = datetime.now().isoformat()
        update_parts.append("updated_at = :updated")
        update_parts.append("updated_at_iso = :updated_iso")
        expr_values[":updated"] = now
        expr_values[":updated_iso"] = now_iso

        update_expression = "SET " + ", ".join(update_parts)

        # Update session
        kwargs = {
            "Key": {"session_id": session_id},
            "UpdateExpression": update_expression,
            "ExpressionAttributeValues": expr_values,
            "ReturnValues": "ALL_NEW",
        }
        if expr_names:
            kwargs["ExpressionAttributeNames"] = expr_names

        response = sessions_table.update_item(**kwargs)

        # Update budget if budget_limit changed
        if request.budget_limit is not None:
            budget_service.update_session_budget_limit(session_id, request.budget_limit)
            logger.info(f"Updated budget limit for session {session_id}")

        logger.info(f"Session updated: {session_id}")

        return {"success": True, "session": response["Attributes"]}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update session: {str(e)}",
        )


@router.delete("/sessions/{session_id}")
async def archive_session(session_id: str):
    """
    Archive a session (soft delete).

    Args:
        session_id: Session ID

    Returns:
        Success message
    """
    try:
        from datetime import datetime

        logger.info(f"Archiving session: {session_id}")

        # Verify session exists
        session_item = _get_session_from_db(session_id)
        if not session_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session not found: {session_id}",
            )

        # Mark as archived
        now = int(datetime.now().timestamp())
        now_iso = datetime.now().isoformat()

        sessions_table.update_item(
            Key={"session_id": session_id},
            UpdateExpression="SET is_archived = :true, updated_at = :updated, updated_at_iso = :updated_iso",
            ExpressionAttributeValues={
                ":true": True,
                ":updated": now,
                ":updated_iso": now_iso,
            },
        )

        logger.info(f"Session archived: {session_id}")

        return {"success": True, "message": f"Session {session_id} archived"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error archiving session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to archive session: {str(e)}",
        )


@router.delete("/sessions/{session_id}/permanent")
async def delete_session_permanent(session_id: str):
    """
    Permanently delete an archived session (hard delete).
    This removes all session data including messages and budget records.

    Args:
        session_id: Session ID

    Returns:
        Success message
    """
    try:
        logger.info(f"Permanently deleting session: {session_id}")

        # Verify session exists and is archived
        session_item = _get_session_from_db(session_id)
        if not session_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session not found: {session_id}",
            )

        # Only allow deletion of archived sessions
        if not session_item.get("is_archived", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete non-archived session. Archive it first.",
            )

        # Delete session record
        sessions_table.delete_item(Key={"session_id": session_id})
        logger.info(f"Deleted session record: {session_id}")

        # Delete budget record
        try:
            budget_service.delete_session_budget(session_id)
            logger.info(f"Deleted budget record for session: {session_id}")
        except Exception as e:
            logger.warning(f"Failed to delete budget record for {session_id}: {e}")

        logger.info(f"Session permanently deleted: {session_id}")

        return {"success": True, "message": f"Session {session_id} permanently deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete session: {str(e)}",
        )
