"""
Agent interaction endpoints.

Handles chat requests, SSE streaming, and agent orchestration.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import AsyncGenerator, List, Optional
from uuid import uuid4

import boto3
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from llmops_agent.config import settings
from llmops_agent.services.bedrock_service import get_bedrock_service
from llmops_agent.agents.orchestrator import OrchestratorAgent

router = APIRouter()
logger = logging.getLogger(__name__)

# DynamoDB client for storing chat history
dynamodb = boto3.resource("dynamodb")

# Initialize orchestrator (uses LangGraph + Bedrock)
orchestrator = OrchestratorAgent()


# ================================================================
# Request/Response Models
# ================================================================


class ChatMessage(BaseModel):
    """Chat message model."""

    role: str = Field(..., description="Message role (user/assistant/system)")
    content: str = Field(..., description="Message content")
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)


class ChatRequest(BaseModel):
    """Chat request from user."""

    message: str = Field(..., description="User message")
    session_id: Optional[str] = Field(default=None, description="Session ID")
    stream: bool = Field(default=True, description="Enable SSE streaming")


class ChatResponse(BaseModel):
    """Chat response to user."""

    session_id: str
    message: str
    job_id: Optional[str] = None
    status: str = Field(default="processing")
    metadata: Optional[dict] = None


class StreamEvent(BaseModel):
    """Server-Sent Event model."""

    event: str = Field(..., description="Event type")
    data: dict = Field(..., description="Event data")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ================================================================
# Endpoints
# ================================================================


@router.post("/chat", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat(request: ChatRequest):
    """
    Process chat message and initiate agent workflow.

    This endpoint receives a user message, creates/retrieves a session,
    and invokes the Bedrock Agent orchestrator to handle the request.

    The agent will:
    1. Reason about the user's request
    2. Extract constraints (budget, time, F1 score)
    3. Call tools (select_model, launch_training, get_job_status)
    4. Return a comprehensive response

    For streaming responses with real-time updates, use the /stream endpoint.
    """
    try:
        # Generate session ID if not provided
        session_id = request.session_id or f"session-{uuid4().hex[:8]}"

        logger.info(f"Received chat request for session {session_id}")
        logger.debug(f"Message: {request.message}")

        # Save user message to DynamoDB
        save_message_to_dynamodb(
            session_id=session_id,
            role="user",
            content=request.message,
        )

        # Check if Bedrock Agent is configured
        if not settings.bedrock_agent_id or not settings.bedrock_agent_alias_id:
            logger.warning("Bedrock Agent not configured, returning mock response")
            return ChatResponse(
                session_id=session_id,
                message=(
                    "Bedrock Agent is not configured yet. "
                    "Please run the setup script and update your .env file with "
                    "BEDROCK_AGENT_ID and BEDROCK_AGENT_ALIAS_ID."
                ),
                status="not_configured",
                metadata={"mode": "mock"},
            )

        # Invoke Bedrock Agent
        bedrock = get_bedrock_service()

        logger.info(f"Invoking Bedrock Agent {settings.bedrock_agent_id}")
        agent_response = await bedrock.invoke_agent(
            agent_id=settings.bedrock_agent_id,
            agent_alias_id=settings.bedrock_agent_alias_id,
            session_id=session_id,
            input_text=request.message,
            enable_trace=settings.debug,  # Enable trace in debug mode
        )

        # Extract response and metadata
        response_message = agent_response.get("completion", "No response from agent")
        trace = agent_response.get("trace", [])

        # Extract job_id if agent launched a training job
        job_id = None
        for trace_item in trace:
            if "tool_result" in trace_item:
                result = trace_item["tool_result"]
                if isinstance(result, dict) and "job_id" in result:
                    job_id = result["job_id"]
                    break

        logger.info(f"Agent response received for session {session_id}")
        if job_id:
            logger.info(f"Training job launched: {job_id}")

        # Save agent response to DynamoDB
        agent_metadata = {
            "mode": "bedrock_agent",
            "agent_id": settings.bedrock_agent_id,
            "tool_calls": len(trace),
            "environment": settings.environment,
        }
        if job_id:
            agent_metadata["job_id"] = job_id

        save_message_to_dynamodb(
            session_id=session_id,
            role="assistant",
            content=response_message,
            metadata=agent_metadata,
        )

        return ChatResponse(
            session_id=session_id,
            message=response_message,
            job_id=job_id,
            status="success",
            metadata=agent_metadata,
        )

    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process chat request: {str(e)}",
        )


@router.get("/chat/history/{session_id}")
async def get_chat_history(session_id: str):
    """
    Retrieve chat history for a session.

    Returns all messages exchanged in the specified session.
    """
    try:
        logger.info(f"Retrieving chat history for session {session_id}")

        messages = get_session_messages(session_id)

        return {
            "session_id": session_id,
            "messages": messages,
            "total": len(messages),
        }

    except Exception as e:
        logger.error(f"Error retrieving chat history: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve chat history: {str(e)}",
        )


@router.post("/chat-stream")
async def chat_stream(request: ChatRequest):
    """
    Process chat message with Server-Sent Events (SSE) streaming.

    Routes requests in priority order:
    1. AgentCore Runtime (if USE_AGENTCORE_RUNTIME=true and AGENTCORE_RUNTIME_ARN is set)
    2. AgentCore Lambda (if USE_AGENTCORE_LAMBDA=true)
    3. Local LangGraph (fallback)

    Environment variables:
    - USE_AGENTCORE_RUNTIME: Enable AgentCore Runtime routing (default: true)
    - AGENTCORE_RUNTIME_ARN: ARN of deployed AgentCore Runtime
    - USE_AGENTCORE_LAMBDA: Enable Lambda routing (default: false, deprecated)

    Streams real-time updates from workflow:
    - connected: Connection established
    - workflow_step: Current workflow step (parse, search, select, train, etc.)
    - candidates_found: Model candidates identified
    - jobs_launched: Training jobs started
    - evaluation_complete: Model evaluation finished
    - recommendations_ready: Final recommendations available
    - conversational_response: Agent response message
    - warning: Fallback or non-critical issue
    - done: Stream complete
    - error: An error occurred
    """
    # Generate session ID if not provided
    session_id = request.session_id or f"session-{uuid4().hex[:8]}"

    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events from AgentCore Lambda or local LangGraph."""
        try:
            logger.info(f"Starting SSE stream for session {session_id}")

            # Save user message to DynamoDB ONCE at the beginning
            save_message_to_dynamodb(
                session_id=session_id,
                role="user",
                content=request.message,
            )
            logger.info(f"[SAVE] User message saved to DynamoDB for session {session_id}")

            # Send initial connection event
            if settings.use_agentcore_runtime and settings.agentcore_runtime_arn:
                mode = "AgentCore Runtime"
            elif settings.use_agentcore_lambda:
                mode = "AgentCore Lambda"
            else:
                mode = "Local LangGraph"

            yield format_sse_event(
                StreamEvent(
                    event="connected",
                    data={
                        "session_id": session_id,
                        "message": f"Connected to LLMOps Agent ({mode})",
                        "mode": mode,
                    },
                )
            )

            # Route to AgentCore Runtime, Lambda, or local orchestrator
            if settings.use_agentcore_runtime and settings.agentcore_runtime_arn:
                logger.info(f"Routing to AgentCore Runtime: {settings.agentcore_runtime_arn}")
                try:
                    async for event in invoke_agentcore_runtime(request.message, session_id):
                        yield format_sse_event(
                            StreamEvent(
                                event=event.get("event", "unknown"),
                                data=event.get("data", {}),
                            )
                        )
                except Exception as runtime_error:
                    logger.error(f"AgentCore Runtime invocation failed: {runtime_error}, falling back to local", exc_info=True)
                    yield format_sse_event(
                        StreamEvent(
                            event="warning",
                            data={"message": "AgentCore Runtime unavailable, switching to local execution"},
                        )
                    )
                    # Fallback to local orchestrator
                    async for event in process_with_local_orchestrator(request.message, session_id):
                        yield format_sse_event(
                            StreamEvent(
                                event=event.get("event", "unknown"),
                                data=event.get("data", {}),
                            )
                        )
            elif settings.use_agentcore_lambda:
                logger.info(f"Routing to AgentCore Lambda: {settings.agentcore_lambda_function_name}")
                try:
                    async for event in invoke_agentcore_lambda(request.message, session_id):
                        yield format_sse_event(
                            StreamEvent(
                                event=event.get("event", "unknown"),
                                data=event.get("data", {}),
                            )
                        )
                except Exception as lambda_error:
                    logger.error(f"Lambda invocation failed: {lambda_error}, falling back to local", exc_info=True)
                    yield format_sse_event(
                        StreamEvent(
                            event="warning",
                            data={"message": "Lambda unavailable, switching to local execution"},
                        )
                    )
                    # Fallback to local orchestrator
                    async for event in process_with_local_orchestrator(request.message, session_id):
                        yield format_sse_event(
                            StreamEvent(
                                event=event.get("event", "unknown"),
                                data=event.get("data", {}),
                            )
                        )
            else:
                logger.info("Using local LangGraph orchestrator")
                # Use local orchestrator (LangGraph + Bedrock)
                async for event in process_with_local_orchestrator(request.message, session_id):
                    yield format_sse_event(
                        StreamEvent(
                            event=event.get("event", "unknown"),
                            data=event.get("data", {}),
                        )
                    )

            # Send completion event
            yield format_sse_event(
                StreamEvent(
                    event="done",
                    data={"session_id": session_id},
                )
            )

        except asyncio.CancelledError:
            logger.info(f"SSE stream cancelled for session {session_id}")
            yield format_sse_event(
                StreamEvent(event="cancelled", data={"message": "Stream cancelled by client"})
            )
        except Exception as e:
            logger.error(f"Error in SSE stream: {e}", exc_info=True)
            yield format_sse_event(
                StreamEvent(
                    event="error",
                    data={"message": str(e), "type": type(e).__name__},
                )
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


# ================================================================
# Helper Functions
# ================================================================


async def process_with_local_orchestrator(user_message: str, session_id: str) -> AsyncGenerator[dict, None]:
    """
    Process request with local LangGraph orchestrator.

    NOTE: User message saving is handled by the calling endpoint (chat-stream),
    not by this function.
    """
    try:
        logger.info(f"[DEBUG] Starting local orchestrator for session {session_id}")
        logger.info(f"[DEBUG] User message: {user_message[:100]}...")

        # Track the agent's response message and all events
        response_message = ""
        event_count = 0
        thinking_steps = []
        tool_calls = []
        workflow_steps = []

        # Process request and yield events
        logger.info(f"[DEBUG] Calling orchestrator.process_request()...")
        async for event in orchestrator.process_request(user_message, session_id):
            event_count += 1
            event_type = event.get("event", "unknown")
            event_data = event.get("data", {})
            logger.info(f"[DEBUG] Event {event_count}: type={event_type}")

            # Capture different event types for metadata
            if event_type == "agent_thinking":
                thinking_step = event_data.get("message", "")
                if thinking_step:
                    thinking_steps.append(thinking_step)
                    logger.info(f"[DEBUG] Captured thinking step: {thinking_step[:50]}...")

            elif event_type == "workflow_step":
                step_info = {
                    "step": event_data.get("step", ""),
                    "message": event_data.get("message", "")
                }
                workflow_steps.append(step_info)
                logger.info(f"[DEBUG] Captured workflow step: {step_info['step']}")

            elif event_type == "conversational_response":
                msg = event_data.get("message", "")
                logger.info(f"[DEBUG] Accumulating conversational_response: {msg[:50]}...")
                response_message += msg

            yield event

        logger.info(f"[DEBUG] Orchestrator complete. Total events: {event_count}, Response length: {len(response_message)}")
        logger.info(f"[DEBUG] Captured {len(thinking_steps)} thinking steps, {len(workflow_steps)} workflow steps")

        # Save assistant response to DynamoDB with rich metadata
        if response_message:
            logger.info(f"[DEBUG] Saving response to DynamoDB: {response_message[:100]}...")
            save_message_to_dynamodb(
                session_id=session_id,
                role="assistant",
                content=response_message,
                metadata={
                    "mode": "local_langgraph",
                    "environment": settings.environment,
                    "thinking_steps": thinking_steps if thinking_steps else None,
                    "workflow_steps": workflow_steps if workflow_steps else None,
                    "event_count": event_count,
                }
            )
            logger.info(f"[DEBUG] Response saved successfully with metadata")
        else:
            logger.warning(f"[DEBUG] No response message to save for session {session_id}")

    except Exception as e:
        logger.error(f"[DEBUG] Error in local orchestrator: {e}", exc_info=True)
        raise


async def invoke_agentcore_runtime(user_message: str, session_id: str) -> AsyncGenerator[dict, None]:
    """
    Invoke AgentCore Runtime and convert response to SSE events.

    Uses bedrock-agentcore API to invoke the deployed agent.

    NOTE: User message saving is handled by the calling endpoint (chat-stream),
    not by this function.
    """
    bedrock_agentcore = boto3.client('bedrock-agentcore', region_name=settings.aws_region)

    try:
        # Extract runtime ID from ARN
        # ARN format: arn:aws:bedrock-agentcore:region:account:runtime/runtime-id
        runtime_id = settings.agentcore_runtime_arn.split('/')[-1] if settings.agentcore_runtime_arn else None

        if not runtime_id:
            raise ValueError("AgentCore Runtime ARN not configured")

        logger.info(f"Invoking AgentCore Runtime {runtime_id}")

        # Invoke AgentCore Runtime
        response = bedrock_agentcore.invoke_agent_runtime(
            runtimeId=runtime_id,
            sessionId=session_id,
            inputText=user_message,
        )

        # Parse response
        response_body = json.loads(response['body'].read()) if 'body' in response else response
        logger.info(f"AgentCore Runtime response: {response_body.get('status')}")

        # Check for errors
        if response_body.get('status') == 'error':
            yield {
                "event": "error",
                "data": {
                    "message": response_body.get('message', 'AgentCore Runtime execution failed'),
                }
            }
            return

        # Extract response details
        response_message = response_body.get('message', '')
        job_id = response_body.get('job_id')
        selected_model = response_body.get('selected_model')
        response_type = response_body.get('type', 'unknown')

        # Emit workflow events based on response type
        if response_type == 'training_started':
            # Emit workflow progress
            yield {
                "event": "workflow_step",
                "data": {
                    "step": "complete",
                    "message": "Training workflow completed",
                }
            }

            # Emit job launched
            if job_id:
                yield {
                    "event": "jobs_launched",
                    "data": {
                        "count": 1,
                        "job_ids": [job_id],
                        "model": selected_model,
                    }
                }

        # Emit conversational response
        yield {
            "event": "conversational_response",
            "data": {
                "message": response_message,
                "job_id": job_id,
                "model": selected_model,
            }
        }

        # Save assistant response to DynamoDB
        save_message_to_dynamodb(
            session_id=session_id,
            role="assistant",
            content=response_message,
            metadata={
                "mode": "agentcore_runtime",
                "runtime_arn": settings.agentcore_runtime_arn,
                "runtime_id": runtime_id,
                "response_type": response_type,
                "job_id": job_id,
                "selected_model": selected_model,
            }
        )

    except Exception as e:
        logger.error(f"Error invoking AgentCore Runtime: {e}", exc_info=True)
        raise  # Re-raise to trigger fallback


async def invoke_agentcore_lambda(user_message: str, session_id: str) -> AsyncGenerator[dict, None]:
    """
    Invoke AgentCore Lambda and convert response to SSE events.

    The Lambda returns structured response, we convert it to SSE event stream.

    NOTE: User message saving is handled by the calling endpoint (chat-stream),
    not by this function.
    """
    lambda_client = boto3.client('lambda', region_name=settings.aws_region)

    try:
        # Invoke Lambda
        logger.info(f"Invoking Lambda {settings.agentcore_lambda_function_name}")
        response = lambda_client.invoke(
            FunctionName=settings.agentcore_lambda_function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'prompt': user_message,
                'session_id': session_id,
            }),
        )

        # Parse Lambda response
        payload = json.loads(response['Payload'].read())
        logger.info(f"Lambda response: {payload.get('status')}")

        # Check for errors
        if payload.get('status') == 'error':
            yield {
                "event": "error",
                "data": {
                    "message": payload.get('message', 'Lambda execution failed'),
                }
            }
            return

        # Extract response type
        response_type = payload.get('type', 'unknown')
        response_message = payload.get('response', '')

        # For conversational responses
        if response_type == 'conversational':
            yield {
                "event": "conversational_response",
                "data": {
                    "message": response_message,
                }
            }

        # For training workflow responses
        elif response_type == 'training_completed':
            # Emit workflow progress events
            yield {
                "event": "workflow_step",
                "data": {
                    "step": "complete",
                    "message": "Training workflow completed",
                }
            }

            # Emit recommendations if available
            recommendations = payload.get('recommendations', [])
            if recommendations:
                yield {
                    "event": "recommendations_ready",
                    "data": {
                        "count": len(recommendations),
                        "top_model": recommendations[0].get('model_name') if recommendations else None,
                        "recommendations": recommendations,
                    }
                }

            # Emit jobs launched
            training_jobs = payload.get('training_jobs', [])
            if training_jobs:
                yield {
                    "event": "jobs_launched",
                    "data": {
                        "count": len(training_jobs),
                        "job_ids": [j.get('job_id') for j in training_jobs],
                    }
                }

            yield {
                "event": "conversational_response",
                "data": {
                    "message": response_message,
                }
            }

        # For in-progress workflows
        elif response_type == 'workflow_in_progress':
            current_step = payload.get('current_step', 'unknown')
            yield {
                "event": "workflow_step",
                "data": {
                    "step": current_step,
                    "message": response_message,
                }
            }

        # Save assistant response
        save_message_to_dynamodb(
            session_id=session_id,
            role="assistant",
            content=response_message,
            metadata={
                "mode": "agentcore_lambda",
                "lambda_function": settings.agentcore_lambda_function_name,
                "response_type": response_type,
            }
        )

    except Exception as e:
        logger.error(f"Error invoking Lambda: {e}", exc_info=True)
        raise  # Re-raise to trigger fallback


def format_sse_event(event: StreamEvent) -> str:
    """
    Format a StreamEvent as a Server-Sent Event.

    SSE format:
    event: event_name
    data: {"key": "value"}

    """
    event_str = f"event: {event.event}\n"
    event_str += f"data: {json.dumps(event.data)}\n\n"
    return event_str


def save_message_to_dynamodb(session_id: str, role: str, content: str, metadata: Optional[dict] = None) -> None:
    """
    Save a chat message to DynamoDB sessions table.

    Messages are stored as a list in the 'messages' attribute.
    """
    try:
        table = dynamodb.Table("llmops-sessions")

        # Get current session or create new one
        response = table.get_item(Key={"session_id": session_id})

        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if metadata:
            message["metadata"] = metadata

        if "Item" in response:
            # Update existing session
            messages = response["Item"].get("messages", [])
            messages.append(message)

            table.update_item(
                Key={"session_id": session_id},
                UpdateExpression="SET messages = :messages, updated_at = :updated_at, updated_at_iso = :updated_at_iso",
                ExpressionAttributeValues={
                    ":messages": messages,
                    ":updated_at": int(datetime.utcnow().timestamp()),
                    ":updated_at_iso": datetime.utcnow().isoformat(),
                },
            )
        else:
            # Create new session
            table.put_item(
                Item={
                    "session_id": session_id,
                    "messages": [message],
                    "created_at": int(datetime.utcnow().timestamp()),
                    "updated_at": int(datetime.utcnow().timestamp()),
                    "updated_at_iso": datetime.utcnow().isoformat(),
                }
            )

        logger.debug(f"Saved message to session {session_id}")

    except Exception as e:
        logger.error(f"Failed to save message to DynamoDB: {e}", exc_info=True)


def get_session_messages(session_id: str) -> List[dict]:
    """
    Retrieve all messages for a session from DynamoDB.

    Returns a list of message dictionaries.
    """
    try:
        table = dynamodb.Table("llmops-sessions")
        response = table.get_item(Key={"session_id": session_id})

        if "Item" in response:
            return response["Item"].get("messages", [])
        return []

    except Exception as e:
        logger.error(f"Failed to retrieve messages from DynamoDB: {e}", exc_info=True)
        return []
