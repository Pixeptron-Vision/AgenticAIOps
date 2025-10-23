"""
Orchestrator Agent - Central coordinator using Bedrock AgentCore.

The Orchestrator Agent is responsible for:
1. Parsing user requests and extracting constraints
2. Coordinating specialized agents (data, model, compute, training)
3. Managing workflow state
4. Streaming updates to the frontend
5. Handling errors and constraint conflicts
"""

import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
from uuid import uuid4

from llmops_agent.config import settings
from llmops_agent.models.agent_models import AgentResponse, ToolCall, ToolResult, ToolType
from llmops_agent.services.bedrock_service import get_bedrock_service
from llmops_agent.services.dynamodb_service import get_dynamodb_service

logger = logging.getLogger(__name__)


# System prompt for the Orchestrator Agent
ORCHESTRATOR_SYSTEM_PROMPT = """You are an expert MLOps Orchestrator Agent. Your role is to coordinate specialized
agents to fulfill user requests for training ML models efficiently and cost-effectively.

## Your Capabilities:
- Parse user requests to extract constraints (budget, time, performance targets)
- Break down complex workflows into sub-tasks
- Call specialized agents (Data, Model Selection, Compute, Training, Evaluation)
- Handle constraint conflicts by negotiating with the user
- Track job state and costs in real-time
- Provide clear status updates to the user

## Constraints You Must Respect:
- **Budget**: Never exceed user's budget limit
- **Time**: Select strategies that fit within time constraints
- **Performance**: Ensure model meets minimum quality targets (F1, accuracy, etc.)
- **Compute**: Choose appropriate instance types (consider VRAM, cost, availability)

## Decision-Making Process:
1. Parse user request → Extract constraints
2. Call Model Selection Agent → Get ranked model candidates
3. Call Compute Agent → Estimate cost and time for each candidate
4. Select best option (cheapest that meets constraints)
5. Call Data Agent → Download and preprocess dataset
6. Call Training Agent → Launch training job
7. Monitor progress → Stream updates to user
8. Call Evaluation Agent → Validate model performance
9. Return results to user with model card

## Important:
- Always explain your reasoning to the user
- If constraints conflict (e.g., budget too low for target F1), present alternatives
- Track cumulative costs to stay within session budget
- Use LoRA/PEFT when possible to reduce costs

## Available Tools:
{tools}

Use the tools above to fulfill user requests. Think step-by-step and explain your reasoning."""


class OrchestratorAgent:
    """
    Orchestrator Agent using Bedrock AgentCore.

    Coordinates the entire ML training workflow.
    """

    def __init__(self):
        """Initialize the orchestrator."""
        self.bedrock = get_bedrock_service()
        self.dynamodb = get_dynamodb_service()
        self.agent_name = "Orchestrator"

    async def process_request(
        self,
        user_message: str,
        session_id: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process user request through LangGraph state machine.

        Args:
            user_message: User's natural language request
            session_id: Session ID for conversation continuity

        Yields:
            Events for streaming to frontend (SSE)
        """
        try:
            logger.info(f"Orchestrator processing request for session {session_id}")

            # Yield initial thinking event
            yield {
                "event": "agent_thinking",
                "data": {
                    "agent": self.agent_name,
                    "message": "Analyzing your request...",
                },
            }

            # Use LangGraph state machine for orchestration
            async for event in self._process_with_langgraph(user_message, session_id):
                yield event

        except Exception as e:
            logger.error(f"Error in orchestrator: {e}", exc_info=True)
            yield {
                "event": "error",
                "data": {"message": str(e)},
            }

    async def _process_with_langgraph(
        self,
        user_message: str,
        session_id: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process request through LangGraph state machine.

        Streams state transitions as SSE events.
        """
        from llmops_agent.agents.state_graph import get_compiled_graph
        from llmops_agent.models.state_models import create_initial_state, WorkflowStep
        from llmops_agent.api.routes.agent import get_session_messages

        try:
            # Get compiled graph
            graph = get_compiled_graph()

            # Load conversation history for context
            all_messages = get_session_messages(session_id)

            # Exclude ONLY the last occurrence of the current user message (to avoid duplication)
            # The current message is saved to DB before invoking the agent, so we need to filter it out
            # But we keep earlier occurrences for context
            conversation_history = []
            found_current_message = False

            # Iterate in reverse to find and skip only the LAST matching message
            for msg in reversed(all_messages):
                if (not found_current_message and
                    msg.get("role") == "user" and
                    msg.get("content") == user_message):
                    # Skip only the first match when going backwards (which is the last in forward order)
                    found_current_message = True
                    continue
                conversation_history.insert(0, msg)  # Insert at beginning to maintain order

            logger.info(f"Loaded {len(conversation_history)} previous messages for session {session_id} (excluding current request)")
            logger.debug(f"[{session_id}] Conversation history content: {[msg.get('content', '')[:50] + '...' if msg.get('content') else '' for msg in conversation_history]}")

            # Create initial state with conversation history
            initial_state = create_initial_state(
                user_request=user_message,
                session_id=session_id,
                conversation_history=conversation_history,
            )

            logger.debug(f"[{session_id}] Initial state messages count: {len(initial_state.messages)}")
            logger.debug(f"[{session_id}] Initial state messages: {[msg.get('content', '')[:50] + '...' if msg.get('content') else '' for msg in initial_state.messages]}")

            # Stream events from graph execution
            current_step = WorkflowStep.INIT
            thinking_count = 0  # Track thinking messages we've already emitted
            message_count = len(conversation_history)  # Start from conversation history length to only emit NEW messages
            has_training_jobs = False  # Track if this is a training workflow

            # Execute graph with streaming
            async for state_update in graph.astream(initial_state.dict()):
                # state_update is a dict like {'node_name': <state>}
                # Extract the actual state from the node update
                if not isinstance(state_update, dict):
                    continue

                # Get the actual state (value of the first key)
                node_name = list(state_update.keys())[0] if state_update else None
                if not node_name:
                    continue

                actual_state = state_update[node_name]
                logger.info(f"[{session_id}] Processing update from node: {node_name}")

                # DEBUG: Log state messages count
                state_messages = actual_state.get("messages", [])
                logger.debug(f"[{session_id}] Node '{node_name}' state has {len(state_messages)} messages")
                if len(state_messages) > 0:
                    logger.debug(f"[{session_id}] Last 3 message previews: {[msg.get('content', '')[:50] + '...' if msg.get('content') else '' for msg in state_messages[-3:]]}")

                # Emit any new thinking messages
                thinking_messages = actual_state.get("thinking_messages", [])
                if len(thinking_messages) > thinking_count:
                    # Emit new thinking messages
                    for thinking_msg in thinking_messages[thinking_count:]:
                        yield {
                            "event": "agent_thinking",
                            "data": {
                                "message": thinking_msg,
                            },
                        }
                    thinking_count = len(thinking_messages)

                # Extract current step
                new_step = actual_state.get("current_step", current_step)

                # Only yield event if step changed
                if new_step != current_step:
                    current_step = new_step

                    # Map workflow steps to SSE events
                    step_messages = {
                        WorkflowStep.PARSING.value: "Extracting constraints from your request...",
                        WorkflowStep.SEARCHING.value: "Searching for suitable models...",
                        WorkflowStep.ESTIMATING.value: "Estimating training costs and time...",
                        WorkflowStep.SELECTING.value: "Selecting top candidates for training...",
                        WorkflowStep.TRAINING.value: "Launching training jobs...",
                        WorkflowStep.MONITORING.value: "Monitoring training progress...",
                        WorkflowStep.EVALUATING.value: "Evaluating trained models...",
                        WorkflowStep.PRESENTING.value: "Generating recommendations...",
                        WorkflowStep.COMPLETE.value: "Workflow complete!",
                        WorkflowStep.ERROR.value: "An error occurred.",
                    }

                    message = step_messages.get(new_step, f"Processing: {new_step}")

                    yield {
                        "event": "workflow_step",
                        "data": {
                            "step": new_step,
                            "message": message,
                        },
                    }

                # Yield progress updates
                if "candidates" in actual_state and actual_state.get("candidates"):
                    candidates = actual_state["candidates"]
                    yield {
                        "event": "candidates_found",
                        "data": {
                            "count": len(candidates),
                            "models": [c.get("model_id") for c in candidates[:3]],
                        },
                    }

                if "training_jobs" in actual_state and actual_state.get("training_jobs"):
                    jobs = actual_state["training_jobs"]
                    has_training_jobs = True  # Mark as training workflow
                    yield {
                        "event": "jobs_launched",
                        "data": {
                            "count": len(jobs),
                            "job_ids": [j.get("job_id") for j in jobs],
                        },
                    }

                if "evaluation_results" in actual_state and actual_state.get("evaluation_results"):
                    results = actual_state["evaluation_results"]
                    yield {
                        "event": "evaluation_complete",
                        "data": {
                            "count": len(results),
                            "best_f1": results[0].get("metrics", {}).get("f1") if results else None,
                        },
                    }

                if "recommendations" in actual_state and actual_state.get("recommendations"):
                    recommendations = actual_state["recommendations"]
                    yield {
                        "event": "recommendations_ready",
                        "data": {
                            "count": len(recommendations),
                            "top_model": recommendations[0].get("model_id") if recommendations else None,
                        },
                    }

                # Emit any new conversational messages (from routing node)
                messages = actual_state.get("messages", [])
                logger.debug(f"[{session_id}] message_count={message_count}, len(messages)={len(messages)}")
                if len(messages) > message_count:
                    # Emit only NEW messages
                    new_messages = messages[message_count:]
                    logger.debug(f"[{session_id}] Emitting {len(new_messages)} new messages")
                    for idx, msg in enumerate(new_messages):
                        if msg.get("role") == "assistant" and msg.get("content"):
                            content_preview = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
                            logger.debug(f"[{session_id}] Emitting message {idx+1}/{len(new_messages)}: {content_preview}")
                            yield {
                                "event": "conversational_response",
                                "data": {
                                    "message": msg["content"],
                                },
                            }
                    message_count = len(messages)
                    logger.debug(f"[{session_id}] Updated message_count to {message_count}")

            # Final completion event - ONLY for training workflows
            if has_training_jobs:
                yield {
                    "event": "workflow_complete",
                    "data": {
                        "session_id": session_id,
                        "message": "Training workflow completed successfully",
                    },
                }

        except Exception as e:
            logger.error(f"Error in LangGraph workflow: {e}", exc_info=True)
            yield {
                "event": "error",
                "data": {
                    "message": str(e),
                    "step": current_step.value if isinstance(current_step, WorkflowStep) else str(current_step),
                },
            }

    def _get_tools_description(self) -> str:
        """Get description of available tools."""
        tools = [
            {
                "name": "search_datasets",
                "description": "Search for datasets on Hugging Face by task type",
                "parameters": {
                    "task_type": "string (e.g., 'token-classification')",
                    "keywords": "string (optional)",
                },
            },
            {
                "name": "select_model",
                "description": "Select optimal model based on constraints",
                "parameters": {
                    "task_type": "string",
                    "budget_usd": "number",
                    "max_time_hours": "number (optional)",
                    "min_f1": "number (optional, 0.0-1.0)",
                },
            },
            {
                "name": "estimate_training_cost",
                "description": "Estimate training cost and time",
                "parameters": {
                    "model_id": "string",
                    "dataset_size": "number",
                    "use_peft": "boolean",
                },
            },
            {
                "name": "launch_training_job",
                "description": "Start a SageMaker training job",
                "parameters": {
                    "job_name": "string",
                    "model_id": "string",
                    "dataset_s3_uri": "string",
                    "instance_type": "string",
                },
            },
        ]

        return json.dumps(tools, indent=2)
