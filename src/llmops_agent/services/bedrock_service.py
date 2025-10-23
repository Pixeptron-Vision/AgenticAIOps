"""
Amazon Bedrock service client.

Provides high-level interface for Bedrock AgentCore and runtime interactions.
"""

import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from llmops_agent.config import settings

logger = logging.getLogger(__name__)


class BedrockService:
    """Service for interacting with Amazon Bedrock."""

    def __init__(self):
        """Initialize Bedrock clients."""
        self.bedrock_runtime = boto3.client(
            "bedrock-runtime",
            region_name=settings.bedrock_model_region,
        )

        self.bedrock_agent = boto3.client(
            "bedrock-agent",
            region_name=settings.bedrock_model_region,
        )

        self.bedrock_agent_runtime = boto3.client(
            "bedrock-agent-runtime",
            region_name=settings.bedrock_model_region,
        )

    async def invoke_claude(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        Invoke Claude model directly (without AgentCore).

        Args:
            system_prompt: System prompt for Claude
            user_message: User message
            max_tokens: Maximum tokens to generate
            temperature: Temperature for sampling
            conversation_history: Previous messages in the conversation

        Returns:
            Claude's response text
        """
        try:
            max_tokens = max_tokens or settings.bedrock_max_tokens
            temperature = temperature or settings.bedrock_temperature

            # Build messages array with conversation history
            messages = []

            # Add conversation history if provided (ensuring role alternation)
            if conversation_history:
                last_role = None
                for msg in conversation_history:
                    # Only include user and assistant messages (skip system messages)
                    role = msg.get("role")
                    if role in ["user", "assistant"]:
                        # Skip consecutive messages with the same role to ensure alternation
                        # Claude API requires strict user/assistant alternation
                        if role != last_role:
                            messages.append({
                                "role": role,
                                "content": msg.get("content", ""),
                            })
                            last_role = role

            # Add current user message (ensure it doesn't duplicate the last message)
            if not messages or messages[-1]["role"] != "user":
                messages.append({
                    "role": "user",
                    "content": user_message,
                })

            # Prepare request body
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": settings.bedrock_top_p,
                "system": system_prompt,
                "messages": messages,
            }

            logger.debug(f"Invoking Claude with message: {user_message[:100]}...")

            response = self.bedrock_runtime.invoke_model(
                modelId=settings.bedrock_model_id,
                body=json.dumps(request_body),
            )

            # Parse response
            response_body = json.loads(response["body"].read())
            content = response_body.get("content", [])

            if content and len(content) > 0:
                return content[0].get("text", "")

            return ""

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            logger.error(f"Bedrock error: {error_code} - {e}")
            raise
        except Exception as e:
            logger.error(f"Error invoking Claude: {e}", exc_info=True)
            raise

    async def invoke_agent(
        self,
        agent_id: str,
        agent_alias_id: str,
        session_id: str,
        input_text: str,
        enable_trace: bool = True,
    ) -> Dict[str, Any]:
        """
        Invoke a Bedrock Agent.

        Args:
            agent_id: Agent ID
            agent_alias_id: Agent alias ID
            session_id: Session ID for conversation continuity
            input_text: User input
            enable_trace: Enable trace for debugging

        Returns:
            Agent response with completion, trace, and session attributes
        """
        try:
            logger.info(f"Invoking agent {agent_id} for session {session_id}")

            response = self.bedrock_agent_runtime.invoke_agent(
                agentId=agent_id,
                agentAliasId=agent_alias_id,
                sessionId=session_id,
                inputText=input_text,
                enableTrace=enable_trace,
            )

            # Parse streaming response
            completion = ""
            trace_events = []

            event_stream = response.get("completion", [])

            for event in event_stream:
                if "chunk" in event:
                    chunk = event["chunk"]
                    if "bytes" in chunk:
                        completion += chunk["bytes"].decode("utf-8")

                if "trace" in event and enable_trace:
                    trace_events.append(event["trace"])

            return {
                "completion": completion,
                "trace": trace_events if enable_trace else None,
                "session_id": session_id,
            }

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            logger.error(f"Bedrock Agent error: {error_code} - {e}")
            raise
        except Exception as e:
            logger.error(f"Error invoking agent: {e}", exc_info=True)
            raise

    async def invoke_agent_stream(
        self,
        agent_id: str,
        agent_alias_id: str,
        session_id: str,
        input_text: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Invoke a Bedrock Agent with streaming.

        Yields events as they are received from the agent, enabling real-time
        updates to be sent to the client via SSE.

        Args:
            agent_id: Agent ID
            agent_alias_id: Agent alias ID
            session_id: Session ID for conversation continuity
            input_text: User input

        Yields:
            Events from the agent stream:
            - {"type": "chunk", "data": {"text": "..."}}
            - {"type": "trace", "data": {"trace_type": "...", ...}}
            - {"type": "completion", "data": {"completion": "..."}}
        """
        try:
            logger.info(f"Invoking agent {agent_id} with streaming for session {session_id}")

            response = self.bedrock_agent_runtime.invoke_agent(
                agentId=agent_id,
                agentAliasId=agent_alias_id,
                sessionId=session_id,
                inputText=input_text,
                enableTrace=True,  # Always enable trace for streaming
            )

            # Stream events from agent
            event_stream = response.get("completion", [])

            completion_text = ""

            for event in event_stream:
                # Text chunk from agent
                if "chunk" in event:
                    chunk = event["chunk"]
                    if "bytes" in chunk:
                        text = chunk["bytes"].decode("utf-8")
                        completion_text += text
                        yield {
                            "type": "chunk",
                            "data": {"text": text},
                        }

                # Trace events (reasoning, tool calls, etc.)
                if "trace" in event:
                    trace = event["trace"].get("trace", {})

                    # Orchestration trace (agent reasoning)
                    if "orchestrationTrace" in trace:
                        orch = trace["orchestrationTrace"]

                        # Rationale (agent thinking)
                        if "rationale" in orch:
                            yield {
                                "type": "trace",
                                "data": {
                                    "trace_type": "ORCHESTRATION",
                                    "rationale": orch["rationale"].get("text", ""),
                                },
                            }

                        # Model invocation (not tool-related)
                        if "modelInvocationInput" in orch:
                            yield {
                                "type": "trace",
                                "data": {
                                    "trace_type": "MODEL_INVOCATION",
                                    "input": orch["modelInvocationInput"],
                                },
                            }

                        # Observation (tool result)
                        if "observation" in orch:
                            obs = orch["observation"]

                            # Action group invocation (tool call)
                            if "actionGroupInvocationOutput" in obs:
                                tool_output = obs["actionGroupInvocationOutput"]
                                yield {
                                    "type": "trace",
                                    "data": {
                                        "trace_type": "TOOL_RESULT",
                                        "tool_name": obs.get("actionGroupInvocationInput", {}).get(
                                            "actionGroupName", "unknown"
                                        ),
                                        "result": json.loads(
                                            tool_output.get("text", "{}")
                                        ) if "text" in tool_output else {},
                                    },
                                }

                    # Pre-processing trace
                    if "preProcessingTrace" in trace:
                        prep = trace["preProcessingTrace"]
                        if "modelInvocationInput" in prep:
                            yield {
                                "type": "trace",
                                "data": {
                                    "trace_type": "PRE_PROCESSING",
                                    "input": prep["modelInvocationInput"],
                                },
                            }

                    # Post-processing trace
                    if "postProcessingTrace" in trace:
                        post = trace["postProcessingTrace"]
                        if "modelInvocationInput" in post:
                            yield {
                                "type": "trace",
                                "data": {
                                    "trace_type": "POST_PROCESSING",
                                    "input": post["modelInvocationInput"],
                                },
                            }

            # Final completion event
            yield {
                "type": "completion",
                "data": {"completion": completion_text},
            }

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            logger.error(f"Bedrock Agent streaming error: {error_code} - {e}")
            yield {
                "type": "error",
                "data": {
                    "error_code": error_code,
                    "message": str(e),
                },
            }
        except Exception as e:
            logger.error(f"Error in agent streaming: {e}", exc_info=True)
            yield {
                "type": "error",
                "data": {
                    "message": str(e),
                    "type": type(e).__name__,
                },
            }

    async def create_agent(
        self,
        agent_name: str,
        description: str,
        instruction: str,
        foundation_model: str,
        role_arn: str,
    ) -> str:
        """
        Create a new Bedrock Agent.

        Args:
            agent_name: Agent name
            description: Agent description
            instruction: System instruction for the agent
            foundation_model: Model ID (e.g., Claude 3.5 Sonnet)
            role_arn: IAM role ARN for the agent

        Returns:
            Agent ID
        """
        try:
            logger.info(f"Creating agent: {agent_name}")

            response = self.bedrock_agent.create_agent(
                agentName=agent_name,
                description=description,
                instruction=instruction,
                foundationModel=foundation_model,
                agentResourceRoleArn=role_arn,
            )

            agent_id = response["agent"]["agentId"]
            logger.info(f"Created agent with ID: {agent_id}")

            return agent_id

        except ClientError as e:
            logger.error(f"Error creating agent: {e}")
            raise

    async def create_agent_action_group(
        self,
        agent_id: str,
        agent_version: str,
        action_group_name: str,
        description: str,
        action_group_executor: Dict[str, str],
        api_schema: Dict[str, Any],
    ) -> str:
        """
        Add an action group (tools) to an agent.

        Args:
            agent_id: Agent ID
            agent_version: Agent version
            action_group_name: Action group name
            description: Description
            action_group_executor: Lambda function ARN
            api_schema: OpenAPI schema for the tools

        Returns:
            Action group ID
        """
        try:
            logger.info(f"Creating action group: {action_group_name} for agent {agent_id}")

            response = self.bedrock_agent.create_agent_action_group(
                agentId=agent_id,
                agentVersion=agent_version,
                actionGroupName=action_group_name,
                description=description,
                actionGroupExecutor=action_group_executor,
                apiSchema=api_schema,
            )

            action_group_id = response["agentActionGroup"]["actionGroupId"]
            logger.info(f"Created action group with ID: {action_group_id}")

            return action_group_id

        except ClientError as e:
            logger.error(f"Error creating action group: {e}")
            raise


# Singleton instance
_bedrock_service: Optional[BedrockService] = None


def get_bedrock_service() -> BedrockService:
    """Get or create Bedrock service instance."""
    global _bedrock_service

    if _bedrock_service is None:
        _bedrock_service = BedrockService()

    return _bedrock_service
