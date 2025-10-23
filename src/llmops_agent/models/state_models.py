"""
State models for LangGraph state machine.

Defines the state schema for multi-agent orchestration workflow.
"""

import operator
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ================================================================
# Enums
# ================================================================


class WorkflowStep(str, Enum):
    """Current step in the workflow."""

    INIT = "init"
    PARSING = "parsing"
    SEARCHING = "searching"
    ESTIMATING = "estimating"
    SELECTING = "selecting"
    TRAINING = "training"
    MONITORING = "monitoring"
    EVALUATING = "evaluating"
    PRESENTING = "presenting"
    COMPLETE = "complete"
    ERROR = "error"


class ConstraintType(str, Enum):
    """Type of constraint."""

    BUDGET = "budget"
    TIME = "time"
    ACCURACY = "accuracy"
    VRAM = "vram"


class JobStatus(str, Enum):
    """Training job status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ================================================================
# Pydantic Models
# ================================================================


class Constraints(BaseModel):
    """User constraints for model selection and training."""

    budget_usd: float = Field(..., description="Maximum budget in USD", gt=0)
    max_time_hours: Optional[float] = Field(None, description="Maximum training time in hours", gt=0)
    min_f1: Optional[float] = Field(None, description="Minimum F1 score required", ge=0, le=1)
    max_vram_gb: float = Field(default=24.0, description="Maximum VRAM in GB", gt=0)
    task_type: str = Field(..., description="ML task type (e.g., token-classification)")
    dataset: Optional[str] = Field(None, description="Dataset name or ID")


class ModelCandidate(BaseModel):
    """A candidate model for training."""

    model_id: str = Field(..., description="Hugging Face model ID")
    model_name: str = Field(..., description="Human-readable model name")
    task_type: str = Field(..., description="Task type")
    params: int = Field(..., description="Number of parameters")
    vram_gb: float = Field(..., description="Required VRAM in GB")
    baseline_f1: float = Field(..., description="Baseline F1 score", ge=0, le=1)
    estimated_cost: Optional[float] = Field(None, description="Estimated training cost in USD")
    estimated_time_hours: Optional[float] = Field(None, description="Estimated training time in hours")
    rank: Optional[int] = Field(None, description="Ranking (1 = best)")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Model-specific training environment metadata (instance_type, training_image, etc.)")


class CostEstimate(BaseModel):
    """Cost and time estimate for training."""

    model_id: str
    instance_type: str = Field(default="ml.g5.xlarge")
    time_hours: float = Field(..., description="Estimated training time in hours", ge=0)
    cost_usd: float = Field(..., description="Estimated cost in USD", ge=0)
    dataset_size: int = Field(..., description="Dataset size (number of samples)", gt=0)
    use_peft: bool = Field(default=True, description="Using LoRA/PEFT")


class TrainingJob(BaseModel):
    """Training job metadata."""

    job_id: str
    model_id: str
    sagemaker_job_name: Optional[str] = None
    status: JobStatus = JobStatus.PENDING
    progress: int = Field(default=0, ge=0, le=100)
    instance_type: str = Field(default="ml.g5.xlarge")
    cost_so_far: float = Field(default=0.0, ge=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class EvaluationMetrics(BaseModel):
    """Evaluation metrics for a trained model."""

    f1: float = Field(..., description="F1 score", ge=0, le=1)
    precision: float = Field(..., description="Precision", ge=0, le=1)
    recall: float = Field(..., description="Recall", ge=0, le=1)
    accuracy: Optional[float] = Field(None, description="Accuracy", ge=0, le=1)
    train_loss: Optional[float] = Field(None, description="Training loss", ge=0)
    val_loss: Optional[float] = Field(None, description="Validation loss", ge=0)


class EvaluationResult(BaseModel):
    """Evaluation result for a trained model."""

    job_id: str
    model_id: str
    metrics: EvaluationMetrics
    cost_usd: float
    time_hours: float
    rank: Optional[int] = None  # Ranking (1 = best)
    is_recommended: bool = Field(default=False)


class Recommendation(BaseModel):
    """Final recommendation for user."""

    model_id: str
    model_name: str
    job_id: str
    metrics: EvaluationMetrics
    cost_usd: float
    time_hours: float
    reasoning: str = Field(..., description="Why this model is recommended")
    alternatives: List[str] = Field(default_factory=list, description="Alternative model IDs")


class ConstraintConflict(BaseModel):
    """Constraint conflict detected during planning."""

    constraint_types: List[ConstraintType]
    message: str = Field(..., description="Human-readable conflict description")
    suggested_alternatives: List[Dict[str, Any]] = Field(default_factory=list)


# ================================================================
# State Graph TypedDict
# ================================================================


class AgentState(BaseModel):
    """
    State for the multi-agent workflow.

    This state is shared across all nodes in the LangGraph state machine.
    """

    # Conversation history (using List[Dict] instead of BaseMessage for V2 compatibility)
    messages: Annotated[List[Dict[str, Any]], operator.add] = Field(
        default_factory=list,
        description="Conversation messages (accumulated)",
    )

    # Thinking trace (streamed to UI for transparency)
    thinking_messages: Annotated[List[str], operator.add] = Field(
        default_factory=list,
        description="Agent thinking steps (accumulated, streamed to UI)",
    )

    # User request and constraints
    user_request: str = Field(..., description="Original user request")
    constraints: Optional[Constraints] = Field(None, description="Extracted constraints")

    # Model selection
    candidates: List[ModelCandidate] = Field(
        default_factory=list,
        description="Model candidates from search",
    )
    selected_models: List[str] = Field(
        default_factory=list,
        description="Model IDs selected for training (top 2-3)",
    )

    # Training
    training_jobs: List[TrainingJob] = Field(
        default_factory=list,
        description="Launched training jobs",
    )

    # Evaluation
    evaluation_results: List[EvaluationResult] = Field(
        default_factory=list,
        description="Evaluation results from completed jobs",
    )

    # Recommendations
    recommendations: List[Recommendation] = Field(
        default_factory=list,
        description="Final recommendations for user",
    )

    # Workflow state
    current_step: WorkflowStep = Field(
        default=WorkflowStep.INIT,
        description="Current workflow step",
    )
    session_id: str = Field(..., description="Session ID for persistence")

    # Additional metadata (for intent classification, etc.)
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (intent, etc.)",
    )

    # Error handling
    error: Optional[str] = Field(None, description="Error message if workflow failed")
    constraint_conflicts: List[ConstraintConflict] = Field(
        default_factory=list,
        description="Detected constraint conflicts",
    )

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for DynamoDB storage."""
        return {
            "user_request": self.user_request,
            "constraints": self.constraints.dict() if self.constraints else None,
            "candidates": [c.dict() for c in self.candidates],
            "selected_models": self.selected_models,
            "training_jobs": [j.dict() for j in self.training_jobs],
            "evaluation_results": [r.dict() for r in self.evaluation_results],
            "recommendations": [r.dict() for r in self.recommendations],
            "current_step": self.current_step.value,
            "session_id": self.session_id,
            "metadata": self.metadata,
            "error": self.error,
            "constraint_conflicts": [c.dict() for c in self.constraint_conflicts],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentState":
        """Load state from dictionary (DynamoDB)."""
        # Convert nested dicts back to Pydantic models
        if data.get("constraints"):
            data["constraints"] = Constraints(**data["constraints"])

        if data.get("candidates"):
            data["candidates"] = [ModelCandidate(**c) for c in data["candidates"]]

        if data.get("training_jobs"):
            data["training_jobs"] = [TrainingJob(**j) for j in data["training_jobs"]]

        if data.get("evaluation_results"):
            data["evaluation_results"] = [EvaluationResult(**r) for r in data["evaluation_results"]]

        if data.get("recommendations"):
            data["recommendations"] = [Recommendation(**r) for r in data["recommendations"]]

        if data.get("constraint_conflicts"):
            data["constraint_conflicts"] = [ConstraintConflict(**c) for c in data["constraint_conflicts"]]

        if data.get("current_step"):
            data["current_step"] = WorkflowStep(data["current_step"])

        if data.get("created_at"):
            data["created_at"] = datetime.fromisoformat(data["created_at"])

        if data.get("updated_at"):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])

        return cls(**data)


# ================================================================
# Helper Functions
# ================================================================


def create_initial_state(user_request: str, session_id: str, conversation_history: Optional[List[Dict]] = None) -> AgentState:
    """
    Create initial state for a new workflow.

    Args:
        user_request: Current user message
        session_id: Session ID for tracking
        conversation_history: Previous messages in the conversation (optional)

    Returns:
        Initial agent state with conversation history
    """
    # Use provided history or start with empty list
    messages = conversation_history if conversation_history is not None else []

    return AgentState(
        user_request=user_request,
        session_id=session_id,
        current_step=WorkflowStep.INIT,
        messages=messages,
    )


def update_state_step(state: AgentState, step: WorkflowStep) -> AgentState:
    """Update workflow step and timestamp."""
    state.current_step = step
    state.updated_at = datetime.utcnow()
    return state
