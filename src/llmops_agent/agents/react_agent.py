"""
ReAct Agent Node - Dynamic tool calling with AgentCore Gateway.

This module implements the ReAct (Reasoning + Acting) pattern for dynamic
tool selection and execution, following the AgentCore Gateway pattern.

The agent:
1. Thinks - Reasons about what tools are needed
2. Acts - Invokes Gateway tools
3. Observes - Analyzes tool results
4. Repeats - Continues until task is complete

FIXES APPLIED (Latest - Oct 21, 2025):
- Fixed conversation history bug (now passes full context to LLM)
- Improved system prompt with clearer completion signals
- Added explicit task completion detection
- Reduced temperature to 0.1 for more deterministic behavior
- Enhanced error handling with contextual suggestions
- Made prompts solution-oriented (focus on what CAN be done, not just failures)
- Added structured formatting requirements for final answers
- Improved tool failure messaging with actionable alternatives
- Optimized tool tracking (using set instead of list for O(1) lookup)
- Better handling of max iterations reached scenarios
- Added comprehensive examples for success and partial failure cases
"""
import json
import logging
from typing import Any, Dict, List, Optional

from llmops_agent.config import settings
from llmops_agent.models.state_models import AgentState, WorkflowStep, update_state_step
from llmops_agent.services.bedrock_service import get_bedrock_service
from llmops_agent.services.gateway_service import get_gateway_client

logger = logging.getLogger(__name__)

# Maximum ReAct iterations to prevent infinite loops
MAX_REACT_ITERATIONS = 10


async def react_agent_node(state: AgentState) -> AgentState:
    """
    ReAct agent node with dynamic tool calling via Gateway.

    This node implements the ReAct pattern:
    - Reasoning: LLM decides what tools to use
    - Acting: Invoke tools via Gateway
    - Observing: Process tool results
    - Loop until task is complete

    Args:
        state: Current agent state

    Returns:
        Updated state with agent response
    """
    try:
        logger.info(f"[{state.session_id}] Starting ReAct agent loop")
        state = update_state_step(state, WorkflowStep.PARSING)

        bedrock = get_bedrock_service()
        gateway = get_gateway_client()

        # Get available tools from Gateway
        available_tools = gateway.list_tools()
        tools_description = _format_tools_for_llm(available_tools)

        logger.info(f"[{state.session_id}] Available tools: {[t['name'] for t in available_tools]}")

        # Initialize conversation history and tool call tracking for ReAct loop
        conversation = []
        iteration = 0
        task_complete = False
        tools_called_successfully = set()  # Use set for O(1) lookup
        tool_results_cache = {}  # Cache tool results to reference later

        while not task_complete and iteration < MAX_REACT_ITERATIONS:
            iteration += 1
            logger.info(f"[{state.session_id}] ReAct iteration {iteration}/{MAX_REACT_ITERATIONS}")

            # Think: Ask LLM to reason and decide on tools
            thought_response = await _think_step(
                bedrock=bedrock,
                user_request=state.user_request,
                tools_description=tools_description,
                conversation_history=conversation,
                tools_already_called=tools_called_successfully,
                tool_results_cache=tool_results_cache,
                session_id=state.session_id,
                session_messages=state.messages,
            )

            # Parse LLM response for tool calls
            tool_calls = _parse_tool_calls(thought_response)

            if not tool_calls:
                # No tools needed, task is complete
                logger.info(f"[{state.session_id}] No tools called, generating final response")
                task_complete = True

                # Extract final answer from LLM response
                final_answer = _extract_final_answer(thought_response)

                state.messages.append({
                    "role": "assistant",
                    "content": final_answer
                })

                # Add thinking message to state
                state.thinking_messages.append(f"Completed task in {iteration} iterations")

                break

            # Act: Execute tool calls via Gateway
            logger.info(f"[{state.session_id}] Executing {len(tool_calls)} tool calls")

            tool_results = []
            new_info_obtained = False
            
            for tool_call in tool_calls:
                tool_name = tool_call["name"]
                parameters = tool_call.get("parameters", {})

                # Check if tool was already called successfully
                # Note: Some tools like status checks could be callable multiple times
                # but for now we enforce one call per tool to prevent loops
                if tool_name in tools_called_successfully:
                    logger.warning(f"[{state.session_id}] Skipping redundant tool call: {tool_name}")
                    # Don't add to tool_results - ignore redundant calls completely
                    continue

                logger.info(f"[{state.session_id}] Invoking tool: {tool_name}")

                state.thinking_messages.append(f"Using tool: {tool_name}")

                try:
                    result = gateway.invoke_tool(tool_name, parameters)
                    tool_results.append({
                        "tool": tool_name,
                        "success": True,
                        "result": result
                    })
                    # Track successful tool call and cache results
                    tools_called_successfully.add(tool_name)  # Add to set
                    tool_results_cache[tool_name] = result
                    new_info_obtained = True
                    logger.info(f"[{state.session_id}] Tool {tool_name} succeeded")

                except Exception as e:
                    logger.error(f"[{state.session_id}] Tool {tool_name} failed: {e}")
                    # Provide detailed error context to help LLM suggest alternatives
                    error_message = str(e)

                    # Add helpful context based on error type
                    if "ValidationException" in error_message or "S3 URI" in error_message:
                        error_context = "The S3 dataset path may be incorrect. Suggest checking the dataset name or using a different dataset."
                    elif "ResourceNotFoundException" in error_message:
                        error_context = "The requested resource was not found. The dataset or configuration may need to be set up first."
                    elif "ThrottlingException" in error_message:
                        error_context = "AWS is throttling requests. Suggest trying again in a few moments."
                    elif "QuotaExceededException" in error_message or "no available" in error_message.lower():
                        error_context = "Resource quota exceeded or no GPUs available. Suggest waiting for resources or using a different instance type."
                    else:
                        error_context = "The operation failed. Check the error details and suggest alternatives."

                    tool_results.append({
                        "tool": tool_name,
                        "success": False,
                        "error": error_message,
                        "context": error_context
                    })

            # If no new information was obtained (all calls were redundant), end the loop
            if not new_info_obtained and tool_calls:
                logger.warning(f"[{state.session_id}] All tool calls were redundant, ending loop")
                task_complete = True
                
                # Generate final answer from existing information
                final_thought = await _generate_final_answer(
                    bedrock=bedrock,
                    user_request=state.user_request,
                    tool_results_cache=tool_results_cache,
                    session_id=state.session_id,
                    session_messages=state.messages,
                )
                
                state.messages.append({
                    "role": "assistant",
                    "content": final_thought
                })
                break

            # Observe: Add tool results to conversation
            observation = _format_tool_results(tool_results)
            tools_used_str = ", ".join(sorted(tools_called_successfully)) if tools_called_successfully else "none"

            conversation.append({
                "role": "assistant",
                "content": thought_response
            })
            conversation.append({
                "role": "user",
                "content": f"""Tool Results:
{observation}

Tools already used successfully: {tools_used_str}

CRITICAL - READ CAREFULLY:
1. You have now gathered information from {len(tools_called_successfully)} tool(s).
2. Review the tool results above. Do you have enough information to answer the user's request?
3. If YES - Provide your final answer in an <answer> block NOW. Do NOT call more tools.
4. If NO - Call ONE new tool you haven't used yet. DO NOT repeat any tools from the "already used" list.

Remember: Each tool can only be called ONCE. If you've called all necessary tools, you MUST provide your final answer."""
            })

        # Handle max iterations reached
        if iteration >= MAX_REACT_ITERATIONS and not task_complete:
            logger.warning(f"[{state.session_id}] Max ReAct iterations ({MAX_REACT_ITERATIONS}) reached")

            # Try to generate a final answer from what we have
            if tool_results_cache:
                # We have some information, provide a summary
                final_answer = await _generate_final_answer(
                    bedrock=bedrock,
                    user_request=state.user_request,
                    tool_results_cache=tool_results_cache,
                    session_id=state.session_id,
                    session_messages=state.messages,
                )
            else:
                # No information gathered - provide helpful message
                final_answer = (
                    "I've reached the maximum number of reasoning steps while processing your request. "
                    "This might mean the task is more complex than expected or requires resources that are currently unavailable. "
                    "Could you please try rephrasing your request or breaking it into smaller steps?"
                )

            state.messages.append({
                "role": "assistant",
                "content": final_answer
            })

        state = update_state_step(state, WorkflowStep.COMPLETE)
        logger.info(f"[{state.session_id}] ReAct agent completed in {iteration} iterations")

        return state

    except Exception as e:
        logger.error(f"[{state.session_id}] ReAct agent error: {e}", exc_info=True)

        state.messages.append({
            "role": "assistant",
            "content": f"I encountered an error while processing your request: {str(e)}"
        })

        state.error = f"ReAct agent failed: {str(e)}"
        state = update_state_step(state, WorkflowStep.ERROR)
        return state


async def _think_step(
    bedrock,
    user_request: str,
    tools_description: str,
    conversation_history: List[Dict[str, str]],
    tools_already_called: List[str],
    tool_results_cache: Dict[str, Any],
    session_id: str,
    session_messages: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Think step: Ask LLM to reason and decide on tool usage.

    Args:
        bedrock: Bedrock service
        user_request: Original user request
        tools_description: Description of available tools
        conversation_history: Previous ReAct conversation
        tools_already_called: List of tools already called successfully
        tool_results_cache: Cache of previous tool results
        session_id: Session ID for logging
        session_messages: Full session conversation history for context

    Returns:
        LLM response with reasoning and tool calls
    """
    tools_used_str = ", ".join(tools_already_called) if tools_already_called else "none yet"
    
    # Build a summary of information gathered so far
    info_summary = ""
    if tool_results_cache:
        info_summary = "\n\nINFORMATION ALREADY GATHERED:"
        for tool_name, result in tool_results_cache.items():
            info_summary += f"\n- From {tool_name}: {json.dumps(result, indent=2)[:200]}..."

    system_prompt = f"""You are an MLOps AI assistant that helps users with machine learning tasks.

You have access to the following tools via AgentCore Gateway:

{tools_description}

Tools you have ALREADY called successfully: {tools_used_str}
{info_summary}

CRITICAL RULES - FOLLOW THESE EXACTLY:
1. Each tool can only be called ONCE per conversation
2. DO NOT call any tool that appears in the "already called successfully" list above
3. If you have enough information to answer the user's request, provide your final answer immediately
4. When a task is complete (e.g., training job launched successfully), stop calling tools and provide your final answer
5. Be solution-oriented: If a tool fails, explain what happened and suggest alternatives
6. Focus on what CAN be done, not just what failed

RESPONSE FORMAT:
1. First, write your reasoning in a <thinking> block where you:
   - Review what information you already have
   - Determine if you need more information
   - Decide whether to call a tool or provide final answer
   - If tools failed, think about alternatives or solutions

2. Then, either:
   a) Call ONE tool you haven't used yet (if you need more information):
      <tool_call>
      {{
        "name": "tool_name",
        "parameters": {{}}
      }}
      </tool_call>

   b) Provide your final answer (if you have enough information):
      <answer>
      Your complete response to the user, incorporating ALL information gathered from tools.
      - Be positive and solution-oriented
      - If something failed, explain why and provide alternatives
      - Include all relevant details (job IDs, dataset names, etc.)
      - End with clear next steps for the user
      </answer>

EXAMPLES:

Example 1 - Need information:
User: "What datasets do we have?"
<thinking>
The user wants to know about available datasets. I haven't called any tools yet, so I should use list_s3_datasets.
</thinking>
<tool_call>
{{
  "name": "list_s3_datasets",
  "parameters": {{}}
}}
</tool_call>

Example 2 - Task complete (successful):
User: "Train NER Model with cier dataset under $5"
[After calling list_s3_datasets, check_gpu_availability, and launch_sagemaker_training]
<thinking>
I have already:
- Listed datasets (found cier dataset)
- Checked GPU availability (ml.g5.xlarge available for $1.50/hr)
- Launched training job (job ID: ner-training-abc123)

All necessary actions are complete. The training job was successfully launched within budget. I should provide the final answer now.
</thinking>
<answer>
✅ Training job successfully launched!

**Job Details:**
- **Job ID:** ner-training-abc123
- **Dataset:** cier (NER dataset)
- **Instance:** ml.g5.xlarge ($1.50/hour - well under $5 budget)
- **Status:** Training started

You can monitor the job progress in the SageMaker console. The job should complete within an hour.
</answer>

Example 3 - Task with partial failures (solution-oriented):
User: "Train NER Model with cier dataset under $5"
[After calling list_s3_datasets, check_gpu_availability - both succeed, but launch_sagemaker_training fails with validation error]
<thinking>
I have gathered information:
- Listed datasets (found cier dataset in S3)
- Checked GPU availability (all GPUs currently in use)
- Attempted to launch training (failed due to GPU unavailability)

While the training couldn't be launched immediately, I have useful information to provide. I should give a solution-oriented response with alternatives.
</thinking>
<answer>
I've checked your request to train an NER model on the cier dataset under $5. Here's what I found:

**✅ Good News:**
- The **cier dataset** is available in your S3 bucket (llmops-agent-datasets)
- The ml.g5.xlarge instance type would cost $1.50/hour - well within your $5 budget

**⚠️ Current Limitation:**
- All GPU instances are currently in use (4/4 GPUs busy)

**🎯 Recommended Next Steps:**
1. **Wait and retry**: GPU resources typically free up within 30-60 minutes
2. **Use Spot Instances**: Can reduce costs by up to 70% and may have availability
3. **Schedule for later**: I can queue your training job to start when resources become available

Would you like me to set up a spot instance request, or would you prefer to wait for on-demand GPU availability?
</answer>

Example 4 - No tools needed:
User: "Hello, how are you?"
<thinking>
This is a greeting. No tools needed, just respond politely.
</thinking>
<answer>
Hello! I'm doing well, thank you. I'm here to help you with MLOps tasks like training models, checking resources, and managing datasets. How can I assist you today?
</answer>
"""

    # Build full conversation context (FIX: Previously only passed last message)
    if not conversation_history:
        # First iteration - just the user request
        full_context = user_request
    else:
        # Build full conversation context with all previous interactions
        context_parts = [f"User Request: {user_request}"]
        
        for msg in conversation_history:
            if msg["role"] == "assistant":
                context_parts.append(f"\nYour Previous Response:\n{msg['content']}")
            else:
                context_parts.append(f"\n{msg['content']}")
        
        full_context = "\n\n".join(context_parts)

    # Invoke LLM with FULL context (including session conversation history)
    response = await bedrock.invoke_claude(
        system_prompt=system_prompt,
        user_message=full_context,
        temperature=0.1,  # Lower temperature for more deterministic behavior
        conversation_history=session_messages,
    )

    logger.info(f"[{session_id}] LLM reasoning: {response[:200]}...")

    return response


async def _generate_final_answer(
    bedrock,
    user_request: str,
    tool_results_cache: Dict[str, Any],
    session_id: str,
    session_messages: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Generate a final answer based on all information gathered.

    Args:
        bedrock: Bedrock service
        user_request: Original user request
        tool_results_cache: All tool results gathered
        session_id: Session ID for logging
        session_messages: Full session conversation history for context

    Returns:
        Final answer text
    """
    # Build summary of all gathered information
    info_summary = "Information gathered from tools:\n"
    for tool_name, result in tool_results_cache.items():
        info_summary += f"\n### {tool_name}:\n{json.dumps(result, indent=2)}\n"

    system_prompt = """You are an MLOps AI assistant. Based on the information gathered from tools, provide a complete and helpful answer to the user's request.

CRITICAL REQUIREMENTS:
1. Include ALL relevant information from the tool results in your response
2. Structure your response clearly with appropriate formatting
3. If a training job was launched, include the job ID and all key details
4. If datasets were found, list them clearly
5. Use a professional but friendly, solution-oriented tone
6. If any tools failed or returned errors:
   - Explain what happened clearly
   - Provide actionable solutions or alternatives
   - Don't just list problems - focus on what CAN be done
7. Always end with clear next steps for the user
8. Do NOT include any XML tags (<thinking>, <tool_call>, etc.) in your response
9. Be encouraging and helpful, not defeatist"""

    prompt = f"""User Request: {user_request}

{info_summary}

Provide a complete, well-formatted final answer that addresses the user's request using ALL the information gathered above. Be specific and include all relevant details (job IDs, dataset names, costs, etc.)."""

    response = await bedrock.invoke_claude(
        system_prompt=system_prompt,
        user_message=prompt,
        temperature=0.2,  # Slightly higher for better formatting variety
        conversation_history=session_messages,
    )

    # Clean up any accidental XML tags
    import re
    cleaned = re.sub(r'<thinking>.*?</thinking>', '', response, flags=re.DOTALL)
    cleaned = re.sub(r'<tool_call>.*?</tool_call>', '', cleaned, flags=re.DOTALL)
    cleaned = re.sub(r'<answer>|</answer>', '', cleaned, flags=re.DOTALL)

    return cleaned.strip()


def _parse_tool_calls(llm_response: str) -> List[Dict[str, Any]]:
    """
    Parse tool calls from LLM response.

    Args:
        llm_response: LLM response text

    Returns:
        List of tool calls with name and parameters
    """
    tool_calls = []

    # Extract tool_call blocks
    import re
    pattern = r'<tool_call>(.*?)</tool_call>'
    matches = re.findall(pattern, llm_response, re.DOTALL)

    for match in matches:
        try:
            tool_call = json.loads(match.strip())
            tool_calls.append(tool_call)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse tool call: {match[:100]}... Error: {e}")

    return tool_calls


def _extract_final_answer(llm_response: str) -> str:
    """
    Extract final answer from LLM response.

    Args:
        llm_response: LLM response text

    Returns:
        Final answer text
    """
    import re

    # Try to extract <answer> block
    pattern = r'<answer>(.*?)</answer>'
    match = re.search(pattern, llm_response, re.DOTALL)

    if match:
        return match.group(1).strip()

    # Fallback: return entire response
    # Remove <thinking> blocks
    thinking_pattern = r'<thinking>.*?</thinking>'
    cleaned = re.sub(thinking_pattern, '', llm_response, flags=re.DOTALL)

    # Remove <tool_call> blocks
    tool_call_pattern = r'<tool_call>.*?</tool_call>'
    cleaned = re.sub(tool_call_pattern, '', cleaned, flags=re.DOTALL)

    return cleaned.strip()


def _format_tools_for_llm(tools: List[Dict[str, Any]]) -> str:
    """
    Format tool list for LLM prompt.

    Args:
        tools: List of tool definitions

    Returns:
        Formatted tool descriptions
    """
    formatted = []

    for tool in tools:
        name = tool.get('name', 'unknown')
        description = tool.get('description', 'No description')
        formatted.append(f"- {name}: {description}")

    return '\n'.join(formatted)


def _format_tool_results(results: List[Dict[str, Any]]) -> str:
    """
    Format tool results for LLM observation.

    Args:
        results: List of tool execution results

    Returns:
        Formatted observation string
    """
    formatted = []

    for result in results:
        tool_name = result['tool']
        if result['success']:
            formatted.append(f"✓ {tool_name}: {json.dumps(result['result'], indent=2)}")
        else:
            error_msg = f"✗ {tool_name}: Error - {result['error']}"
            if 'context' in result:
                error_msg += f"\n  💡 Suggestion: {result['context']}"
            formatted.append(error_msg)

    return '\n\n'.join(formatted)
