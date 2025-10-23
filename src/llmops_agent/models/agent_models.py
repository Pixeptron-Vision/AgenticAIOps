"""
Data models for agent interactions.

Defines the structure for tool calls, agent responses, and workflows.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ToolType(str, Enum):
    """Available tools for agents."""

    SEARCH_DATASETS = "search_datasets"
    DOWNLOAD_DATASET = "download_dataset"
    SELECT_MODEL = "select_model"
    ESTIMATE_COST = "estimate_training_cost"
    LAUNCH_TRAINING = "launch_training_job"
    GET_JOB_STATUS = "get_training_job_status"
    EVALUATE_MODEL = "evaluate_model"


class ToolCall(BaseModel):
    """Tool call from agent."""

    tool: ToolType
    parameters: Dict[str, Any]
    call_id: str = Field(default_factory=lambda: f"call-{datetime.utcnow().timestamp()}")


class ToolResult(BaseModel):
    """Result from tool execution."""

    call_id: str
    tool: ToolType
    result: Any
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentThought(BaseModel):
    """Agent reasoning step."""

    thought: str
    reasoning: str
    next_action: Optional[str] = None


class AgentResponse(BaseModel):
    """Response from an agent."""

    agent_name: str
    thought: Optional[AgentThought] = None
    tool_calls: List[ToolCall] = Field(default_factory=list)
    message: Optional[str] = None
    completed: bool = False
