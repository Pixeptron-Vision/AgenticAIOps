"""
LangGraph State Machine for Multi-Agent Orchestration.

Implements a stateful workflow for model selection, training, and evaluation.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from langgraph.graph import END, StateGraph

from llmops_agent.config import settings
from llmops_agent.models.state_models import (
    AgentState,
    ConstraintConflict,
    ConstraintType,
    Constraints,
    CostEstimate,
    EvaluationMetrics,
    EvaluationResult,
    JobStatus,
    ModelCandidate,
    Recommendation,
    TrainingJob,
    WorkflowStep,
    update_state_step,
)
from llmops_agent.agents.react_agent import react_agent_node
from llmops_agent.services.bedrock_service import get_bedrock_service
from llmops_agent.services.dynamodb_service import get_dynamodb_service
from llmops_agent.services.gateway_service import get_gateway_client
from llmops_agent.services.sagemaker_service import get_sagemaker_service

logger = logging.getLogger(__name__)


# ================================================================
# Node 0: Route Request (Classify Intent)
# ================================================================


async def route_request_node(state: AgentState) -> AgentState:
    """
    Determine if the user request is a training request or conversational.

    Routes to either the training workflow or a simple conversational response.

    Args:
        state: Current agent state

    Returns:
        Updated state with intent classification
    """
    try:
        logger.info(f"[{state.session_id}] Routing user request")

        # Keyword-based pre-check for data/resource queries (more reliable than LLM for these)
        # Only trigger if it's PURELY a data listing query (not a training request)
        request_lower = state.user_request.lower()

        # Dataset listing queries (specific patterns)
        is_data_listing_query = (
            ('what' in request_lower and ('dataset' in request_lower or 'data' in request_lower)) or
            ('list' in request_lower and ('dataset' in request_lower or 'data' in request_lower or 's3' in request_lower)) or
            ('show' in request_lower and ('dataset' in request_lower or 'data' in request_lower or 's3' in request_lower)) or
            ('available' in request_lower and 'dataset' in request_lower)
        )

        # Training keywords that override data listing
        is_training_query = (
            'train' in request_lower or
            'fine-tune' in request_lower or
            'finetune' in request_lower or
            'model' in request_lower
        )

        # Only handle as data query if it's NOT a training request
        if is_data_listing_query and not is_training_query:
            logger.info(f"[{state.session_id}] Data query detected, invoking Gateway tool: list_s3_datasets")

            try:
                # Invoke Gateway tool to list datasets
                gateway = get_gateway_client()

                if settings.use_agentcore_gateway and gateway.enabled:
                    logger.info(f"[{state.session_id}] Using AgentCore Gateway to list datasets")
                    result = gateway.invoke_tool("list_s3_datasets", parameters={})

                    # Extract data from Gateway result
                    datasets = result.get('datasets', [])
                    bucket = result.get('bucket', settings.s3_bucket_datasets)
                    total_count = result.get('total_count', len(datasets))
                else:
                    # Fallback to direct S3 query if Gateway is disabled
                    logger.info(f"[{state.session_id}] Gateway disabled, using direct S3 query")
                    import boto3
                    s3_client = boto3.client('s3', region_name=settings.aws_region)
                    bucket = settings.s3_bucket_datasets
                    prefix = "processed/"

                    response = s3_client.list_objects_v2(
                        Bucket=bucket,
                        Prefix=prefix,
                        Delimiter='/'
                    )

                    datasets = []
                    if 'CommonPrefixes' in response:
                        for prefix_info in response['CommonPrefixes']:
                            prefix_path = prefix_info['Prefix']
                            dataset_name = prefix_path.rstrip('/').split('/')[-1]
                            if dataset_name:
                                datasets.append(dataset_name)
                    total_count = len(datasets)

                # Generate user-friendly response
                if datasets:
                    dataset_list = '\n'.join([f"  • {ds}" for ds in datasets])
                    response_message = f"Available datasets in S3 bucket '{bucket}':\n\n{dataset_list}\n\nTotal: {total_count} datasets found."
                else:
                    response_message = f"No datasets found in S3 bucket '{bucket}'"

                logger.info(f"[{state.session_id}] Found {total_count} datasets: {datasets}")

                # Add response to state messages (will trigger conversational_response event)
                state.messages.append({
                    "role": "assistant",
                    "content": response_message
                })

                # Mark workflow as complete
                state = update_state_step(state, WorkflowStep.COMPLETE)

                # Set metadata to indicate this was handled as a data query
                if not state.metadata:
                    state.metadata = {}
                state.metadata["intent"] = "data_query"
                state.metadata["query_type"] = "list_datasets"
                state.metadata["datasets_found"] = len(datasets)

                return state

            except Exception as e:
                logger.error(f"[{state.session_id}] Error listing datasets: {e}", exc_info=True)

                # Add error message
                error_message = f"I encountered an error while listing datasets: {str(e)}"
                state.messages.append({
                    "role": "assistant",
                    "content": error_message
                })

                state.error = f"Failed to list datasets: {str(e)}"
                state = update_state_step(state, WorkflowStep.ERROR)
                return state

        bedrock = get_bedrock_service()

        # System prompt for intent classification
        system_prompt = """You are an intent classifier. Determine if the user's message is:

        1. "training_request": User wants to fine-tune/train a model, optimize models, get ML recommendations, OR ask about datasets/S3 data/resources
           Examples:
           - "Fine-tune a sentiment analysis model"
           - "I need to train a model for NER"
           - "Help me optimize model performance"
           - "Which model should I use for text classification?"
           - "What datasets do we have?"
           - "Show me the datasets on S3"
           - "List available data"
           - "What's in our S3 bucket?"

        2. "conversation": Greetings, general questions about capabilities, help requests, or casual chat (NOT about specific data/resources)
           Examples:
           - "Hi! What can you do?"
           - "Hello"
           - "Tell me about your features"
           - "How do I use this?"

        Respond with ONLY ONE WORD: either "training_request" or "conversation"
        """

        response = await bedrock.invoke_claude(
            system_prompt=system_prompt,
            user_message=state.user_request,
            temperature=0.0,  # Deterministic classification
            conversation_history=state.messages,
        )

        # Extract first word only (Claude sometimes ignores "ONLY ONE WORD" instruction)
        raw_response = response.strip().lower()
        first_word = raw_response.split()[0] if raw_response else ""

        # Validate intent - must be exactly "training_request" or "conversation"
        if first_word in ("training_request", "conversation"):
            intent = first_word
        elif "training_request" in raw_response or "training" in raw_response:
            # If response mentions training, classify as training_request
            intent = "training_request"
            logger.warning(f"[{state.session_id}] Intent classifier returned unexpected response: {raw_response[:100]}... Defaulting to 'training_request'")
        elif "conversation" in raw_response:
            # If response mentions conversation, classify as conversation
            intent = "conversation"
            logger.warning(f"[{state.session_id}] Intent classifier returned unexpected response: {raw_response[:100]}... Defaulting to 'conversation'")
        else:
            # Default to conversation for safety
            intent = "conversation"
            logger.warning(f"[{state.session_id}] Intent classifier returned unrecognized response: {raw_response[:100]}... Defaulting to 'conversation'")

        # Store intent in state metadata
        if not state.metadata:
            state.metadata = {}
        state.metadata["intent"] = intent

        logger.info(f"[{state.session_id}] Classified intent as: {intent}")

        # If conversational, generate a friendly response
        if intent == "conversation":
            logger.info(f"[{state.session_id}] Generating conversational response...")

            conversational_prompt = """You are an AI assistant that helps ML engineers fine-tune and optimize models on AWS SageMaker.

Your capabilities:
- Recommend optimal models based on task type, budget, and constraints
- Check real-time instance quota availability in DynamoDB
- Launch multi-variation training jobs on SageMaker
- Compare model performance and costs
- Provide model recommendations with transparent reasoning

Respond to the user's message in a helpful, friendly way. Keep it concise (2-3 sentences)."""

            conversational_response = await bedrock.invoke_claude(
                system_prompt=conversational_prompt,
                user_message=state.user_request,
                temperature=0.7,  # More creative for conversation
                conversation_history=state.messages,
            )

            logger.info(f"[{state.session_id}] Generated response: {conversational_response[:100]}...")

            state.messages.append({
                "role": "assistant",
                "content": conversational_response
            })
            state = update_state_step(state, WorkflowStep.COMPLETE)
            logger.info(f"[{state.session_id}] Added conversational response to state.messages (count: {len(state.messages)})")

        return state

    except Exception as e:
        logger.error(f"[{state.session_id}] Error routing request: {e}", exc_info=True)

        # Add user-friendly error message to state.messages so UI receives it
        error_message = f"I encountered an error processing your request: {str(e)}"
        if "ThrottlingException" in str(e):
            error_message = "I'm currently experiencing high load from AWS Bedrock. Please wait a moment and try again."
        elif "ServiceQuotaExceededException" in str(e):
            error_message = "AWS service quota exceeded. Please try again later or contact your AWS administrator."

        state.messages.append({
            "role": "assistant",
            "content": error_message
        })

        state.error = f"Failed to route request: {str(e)}"
        state = update_state_step(state, WorkflowStep.ERROR)
        return state


# ================================================================
# Node 1: Parse Request
# ================================================================


async def parse_request_node(state: AgentState) -> AgentState:
    """
    Parse user request and extract constraints.

    Uses Bedrock Claude to convert natural language to structured constraints.

    Args:
        state: Current agent state

    Returns:
        Updated state with constraints extracted
    """
    try:
        logger.info(f"[{state.session_id}] Parsing user request")
        state = update_state_step(state, WorkflowStep.PARSING)

        bedrock = get_bedrock_service()

        # System prompt for constraint extraction
        system_prompt = """You are a constraint extraction expert. Parse the user's request and extract:
        - budget_usd: Maximum budget in USD (required)
        - max_time_hours: Maximum training time in hours (optional)
        - min_f1: Minimum F1 score required, as decimal 0.0-1.0 (optional)
        - task_type: ML task type (e.g., "token-classification", "text-generation")
        - dataset: Dataset name or ID (optional)

        Respond ONLY with valid JSON matching this schema:
        {
            "budget_usd": 10.0,
            "max_time_hours": 1.0,
            "min_f1": 0.85,
            "task_type": "token-classification",
            "dataset": "ciER"
        }

        If budget is not specified, default to 50.0.
        If task_type is not clear, default to "token-classification".
        """

        response = await bedrock.invoke_claude(
            system_prompt=system_prompt,
            user_message=state.user_request,
            temperature=0.0,  # Deterministic extraction
            conversation_history=state.messages,
        )

        # Parse JSON response
        import json

        constraints_dict = json.loads(response.strip())
        constraints = Constraints(**constraints_dict)

        state.constraints = constraints
        state.messages.append({
            "role": "system",
            "content": f"Extracted constraints: {constraints.dict()}"
        })

        logger.info(f"[{state.session_id}] Parsed constraints: {constraints}")
        return state

    except Exception as e:
        logger.error(f"[{state.session_id}] Error parsing request: {e}", exc_info=True)

        # Add user-friendly error message
        error_message = f"I couldn't understand your request. Please provide more details about your training requirements."

        state.messages.append({
            "role": "assistant",
            "content": error_message
        })

        state.error = f"Failed to parse request: {str(e)}"
        state = update_state_step(state, WorkflowStep.ERROR)
        return state


# ================================================================
# Node 2: Search Models
# ================================================================


async def search_models_node(state: AgentState) -> AgentState:
    """
    Search for model candidates matching constraints.

    Queries the model knowledge base (CSV for now) for suitable models.

    Args:
        state: Current agent state

    Returns:
        Updated state with model candidates
    """
    try:
        logger.info(f"[{state.session_id}] Searching for model candidates")
        state = update_state_step(state, WorkflowStep.SEARCHING)

        if not state.constraints:
            raise ValueError("Constraints not extracted yet")

        # Import ModelAgent for model search
        from llmops_agent.agents.model_agent import ModelAgent

        # Create thinking callback that appends to state
        async def thinking_callback(message: str):
            """Callback to capture ModelAgent thinking steps."""
            state.thinking_messages.append(message)

        # Create ModelAgent with thinking callback
        model_agent = ModelAgent(thinking_callback=thinking_callback)

        # Search for candidates (thinking is captured via callback)
        result = await model_agent.select_model(
            task_type=state.constraints.task_type,
            budget_usd=state.constraints.budget_usd,
            max_time_hours=state.constraints.max_time_hours,
            min_f1=state.constraints.min_f1,
            max_vram_gb=state.constraints.max_vram_gb,
        )

        if not result.get("success", False):
            # No models found - constraint conflict
            conflict = ConstraintConflict(
                constraint_types=[ConstraintType.BUDGET, ConstraintType.ACCURACY],
                message=result.get("error", "No models meet constraints"),
                suggested_alternatives=[],
            )
            state.constraint_conflicts.append(conflict)
            state.error = conflict.message
            state = update_state_step(state, WorkflowStep.ERROR)
            return state

        # Convert to ModelCandidate objects and preserve training environment config
        candidates = []
        recommended = result.get("recommended")
        if recommended:
            candidate = ModelCandidate(
                model_id=recommended["model_id"],
                model_name=recommended["model_id"],  # TODO: Get human-readable name
                task_type=state.constraints.task_type,
                params=recommended.get("params", 0),
                vram_gb=recommended.get("vram_gb", 12.0),
                baseline_f1=recommended.get("baseline_f1", 0.85),
                estimated_cost=recommended.get("estimated_cost"),
                estimated_time_hours=recommended.get("estimated_time_hours"),
                rank=1,
            )
            # Store training environment metadata for later use
            candidate.metadata = {
                "instance_type": recommended.get("instance_type", "ml.g5.xlarge"),
                "training_image": recommended.get("training_image"),
                "min_transformers_version": recommended.get("min_transformers_version"),
            }
            candidates.append(candidate)

        # Add alternatives
        for idx, alt in enumerate(result.get("alternatives", []), start=2):
            candidate = ModelCandidate(
                model_id=alt["model_id"],
                model_name=alt["model_id"],
                task_type=state.constraints.task_type,
                params=alt.get("params", 0),
                vram_gb=alt.get("vram_gb", 12.0),
                baseline_f1=alt.get("baseline_f1", 0.85),
                estimated_cost=alt.get("estimated_cost"),
                estimated_time_hours=alt.get("estimated_time_hours"),
                rank=idx,
            )
            # Store training environment metadata for later use
            candidate.metadata = {
                "instance_type": alt.get("instance_type", "ml.g5.xlarge"),
                "training_image": alt.get("training_image"),
                "min_transformers_version": alt.get("min_transformers_version"),
            }
            candidates.append(candidate)

        state.candidates = candidates
        state.messages.append({
            "role": "system",
            "content": f"Found {len(candidates)} model candidates"
        })

        logger.info(f"[{state.session_id}] Found {len(candidates)} candidates")
        return state

    except Exception as e:
        logger.error(f"[{state.session_id}] Error searching models: {e}", exc_info=True)

        # Add user-friendly error message
        error_message = f"I couldn't find suitable models for your request. Error: {str(e)}"

        state.messages.append({
            "role": "assistant",
            "content": error_message
        })

        state.error = f"Failed to search models: {str(e)}"
        state = update_state_step(state, WorkflowStep.ERROR)
        return state


# ================================================================
# Node 3: Estimate Costs
# ================================================================


async def estimate_costs_node(state: AgentState) -> AgentState:
    """
    Estimate training cost and time for each candidate.

    Args:
        state: Current agent state

    Returns:
        Updated state with cost estimates
    """
    try:
        logger.info(f"[{state.session_id}] Estimating costs for candidates")
        state = update_state_step(state, WorkflowStep.ESTIMATING)

        # Costs are already estimated in search_models_node
        # This node is a placeholder for more sophisticated cost estimation
        # based on historical data (once we have the knowledge base)

        # For now, just validate estimates exist
        for candidate in state.candidates:
            if candidate.estimated_cost is None or candidate.estimated_time_hours is None:
                logger.warning(f"Candidate {candidate.model_id} missing cost estimates")

        state.messages.append({
            "role": "system",
            "content": f"Cost estimates validated for {len(state.candidates)} candidates"
        })

        logger.info(f"[{state.session_id}] Cost estimation complete")
        return state

    except Exception as e:
        logger.error(f"[{state.session_id}] Error estimating costs: {e}", exc_info=True)

        # Add user-friendly error message
        error_message = f"I couldn't estimate training costs. Error: {str(e)}"

        state.messages.append({
            "role": "assistant",
            "content": error_message
        })

        state.error = f"Failed to estimate costs: {str(e)}"
        state = update_state_step(state, WorkflowStep.ERROR)
        return state


# ================================================================
# Node 4: Select Top Candidates
# ================================================================


async def select_candidates_node(state: AgentState) -> AgentState:
    """
    Select top 2-3 candidates for multi-variation training.

    Args:
        state: Current agent state

    Returns:
        Updated state with selected models
    """
    try:
        logger.info(f"[{state.session_id}] Selecting top candidates")
        state = update_state_step(state, WorkflowStep.SELECTING)

        # Select top 3 candidates (or all if fewer than 3)
        num_to_select = min(3, len(state.candidates))
        selected = sorted(state.candidates, key=lambda c: c.rank or 999)[:num_to_select]

        state.selected_models = [c.model_id for c in selected]
        state.messages.append({
            "role": "system",
            "content": f"Selected {len(state.selected_models)} models for training"
        })

        logger.info(f"[{state.session_id}] Selected models: {state.selected_models}")
        return state

    except Exception as e:
        logger.error(f"[{state.session_id}] Error selecting candidates: {e}", exc_info=True)

        # Add user-friendly error message
        error_message = f"I couldn't select model candidates. Error: {str(e)}"

        state.messages.append({
            "role": "assistant",
            "content": error_message
        })

        state.error = f"Failed to select candidates: {str(e)}"
        state = update_state_step(state, WorkflowStep.ERROR)
        return state


# ================================================================
# Node 5: Launch Training Jobs
# ================================================================


async def launch_training_node(state: AgentState) -> AgentState:
    """
    Launch SageMaker training jobs for selected models.

    Args:
        state: Current agent state

    Returns:
        Updated state with training jobs
    """
    try:
        logger.info(f"[{state.session_id}] Launching training jobs")
        state = update_state_step(state, WorkflowStep.TRAINING)

        sagemaker = get_sagemaker_service()

        # TODO: Launch actual SageMaker training jobs
        # For now, create placeholder job records

        jobs = []
        for model_id in state.selected_models:
            job_id = f"job-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{len(jobs)}"

            # Find the candidate to get model-specific training environment
            candidate = next((c for c in state.candidates if c.model_id == model_id), None)
            instance_type = "ml.g5.xlarge"  # Default fallback
            training_image = None

            if candidate and candidate.metadata:
                instance_type = candidate.metadata.get("instance_type", "ml.g5.xlarge")
                training_image = candidate.metadata.get("training_image")
                logger.info(
                    f"[{state.session_id}] Using model-specific env for {model_id}: "
                    f"{instance_type}, transformers {candidate.metadata.get('min_transformers_version')}"
                )

            job = TrainingJob(
                job_id=job_id,
                model_id=model_id,
                status=JobStatus.PENDING,
                instance_type=instance_type,
                created_at=datetime.utcnow(),
            )

            jobs.append(job)
            logger.info(f"[{state.session_id}] Created training job: {job_id} on {instance_type}")

        state.training_jobs = jobs
        state.messages.append({
            "role": "system",
            "content": f"Launched {len(jobs)} training jobs"
        })

        # TODO: Actually launch SageMaker jobs here
        # This requires:
        # 1. Dataset uploaded to S3
        # 2. Training script configured
        # 3. IAM roles set up
        # Log as pending test

        logger.warning(
            f"[{state.session_id}] SageMaker job launch pending (requires AWS connectivity)"
        )

        return state

    except Exception as e:
        logger.error(f"[{state.session_id}] Error launching training: {e}", exc_info=True)

        # Add user-friendly error message
        error_message = f"I couldn't launch training jobs. Error: {str(e)}"

        state.messages.append({
            "role": "assistant",
            "content": error_message
        })

        state.error = f"Failed to launch training: {str(e)}"
        state = update_state_step(state, WorkflowStep.ERROR)
        return state


# ================================================================
# Node 6: Monitor Jobs
# ================================================================


async def monitor_jobs_node(state: AgentState) -> AgentState:
    """
    Monitor training job progress.

    Polls SageMaker until all jobs complete.

    Args:
        state: Current agent state

    Returns:
        Updated state with job status
    """
    try:
        logger.info(f"[{state.session_id}] Monitoring training jobs")
        state = update_state_step(state, WorkflowStep.MONITORING)

        sagemaker = get_sagemaker_service()

        # TODO: Poll SageMaker for job status
        # For now, mark all jobs as completed (mock)

        for job in state.training_jobs:
            job.status = JobStatus.COMPLETED
            job.progress = 100
            job.completed_at = datetime.utcnow()
            job.cost_so_far = 5.0  # Mock cost

        state.messages.append({
            "role": "system",
            "content": "All training jobs completed"
        })

        logger.warning(
            f"[{state.session_id}] Job monitoring mocked (requires AWS connectivity)"
        )

        return state

    except Exception as e:
        logger.error(f"[{state.session_id}] Error monitoring jobs: {e}", exc_info=True)

        # Add user-friendly error message
        error_message = f"I couldn't monitor training jobs. Error: {str(e)}"

        state.messages.append({
            "role": "assistant",
            "content": error_message
        })

        state.error = f"Failed to monitor jobs: {str(e)}"
        state = update_state_step(state, WorkflowStep.ERROR)
        return state


# ================================================================
# Node 7: Evaluate Results
# ================================================================


async def evaluate_results_node(state: AgentState) -> AgentState:
    """
    Evaluate trained models and compare performance.

    Args:
        state: Current agent state

    Returns:
        Updated state with evaluation results
    """
    try:
        logger.info(f"[{state.session_id}] Evaluating training results")
        state = update_state_step(state, WorkflowStep.EVALUATING)

        # TODO: Get actual metrics from SageMaker
        # For now, generate mock evaluation results

        results = []
        for job in state.training_jobs:
            if job.status == JobStatus.COMPLETED:
                # Mock metrics (TODO: Get from SageMaker/MLflow)
                metrics = EvaluationMetrics(
                    f1=0.87 + (len(results) * 0.01),  # Mock varying scores
                    precision=0.88,
                    recall=0.86,
                    accuracy=0.87,
                    train_loss=0.32,
                    val_loss=0.35,
                )

                result = EvaluationResult(
                    job_id=job.job_id,
                    model_id=job.model_id,
                    metrics=metrics,
                    cost_usd=job.cost_so_far,
                    time_hours=0.7,  # Mock
                    rank=len(results) + 1,
                )

                results.append(result)

        # Sort by F1 score (best first)
        results.sort(key=lambda r: r.metrics.f1, reverse=True)

        # Mark top result as recommended
        if results:
            results[0].is_recommended = True

        state.evaluation_results = results
        state.messages.append({
            "role": "system",
            "content": f"Evaluated {len(results)} trained models"
        })

        logger.warning(
            f"[{state.session_id}] Evaluation mocked (requires AWS connectivity)"
        )

        return state

    except Exception as e:
        logger.error(f"[{state.session_id}] Error evaluating results: {e}", exc_info=True)

        # Add user-friendly error message
        error_message = f"I couldn't evaluate training results. Error: {str(e)}"

        state.messages.append({
            "role": "assistant",
            "content": error_message
        })

        state.error = f"Failed to evaluate results: {str(e)}"
        state = update_state_step(state, WorkflowStep.ERROR)
        return state


# ================================================================
# Node 8: Present Options
# ================================================================


async def present_options_node(state: AgentState) -> AgentState:
    """
    Generate final recommendations for user.

    Analyzes all results and creates human-readable recommendations.

    Args:
        state: Current agent state

    Returns:
        Updated state with recommendations
    """
    try:
        logger.info(f"[{state.session_id}] Generating recommendations")
        state = update_state_step(state, WorkflowStep.PRESENTING)

        recommendations = []

        # Generate recommendation for top model
        if state.evaluation_results:
            best_result = state.evaluation_results[0]

            recommendation = Recommendation(
                model_id=best_result.model_id,
                model_name=best_result.model_id,  # TODO: Human-readable name
                job_id=best_result.job_id,
                metrics=best_result.metrics,
                cost_usd=best_result.cost_usd,
                time_hours=best_result.time_hours,
                reasoning=(
                    f"This model achieved the highest F1 score ({best_result.metrics.f1:.3f}) "
                    f"while staying within budget (${best_result.cost_usd:.2f})."
                ),
                alternatives=[r.model_id for r in state.evaluation_results[1:3]],
            )

            recommendations.append(recommendation)

        state.recommendations = recommendations
        state = update_state_step(state, WorkflowStep.COMPLETE)
        state.messages.append({
            "role": "system",
            "content": f"Generated {len(recommendations)} recommendations"
        })

        logger.info(f"[{state.session_id}] Workflow complete")
        return state

    except Exception as e:
        logger.error(f"[{state.session_id}] Error presenting options: {e}", exc_info=True)

        # Add user-friendly error message
        error_message = f"I couldn't generate recommendations. Error: {str(e)}"

        state.messages.append({
            "role": "assistant",
            "content": error_message
        })

        state.error = f"Failed to present options: {str(e)}"
        state = update_state_step(state, WorkflowStep.ERROR)
        return state


# ================================================================
# Conditional Edges
# ================================================================


def should_continue_after_routing(state: AgentState) -> str:
    """
    Determine next step after intent routing.

    Args:
        state: Current agent state

    Returns:
        "react" (ReAct mode) or "parse" (legacy mode) for training requests,
        "end" for conversational/data queries already handled in route node
    """
    intent = state.metadata.get("intent", "conversation") if state.metadata else "conversation"

    # If already handled in route node (conversation or data_query), end
    if intent in ("conversation", "data_query"):
        return "end"

    # For training requests, route based on orchestration mode
    if intent == "training_request":
        if settings.feature_react_orchestration:
            return "react"  # Use ReAct agent
        else:
            return "parse"  # Use legacy pipeline

    # Default: end
    return "end"


def should_continue_monitoring(state: AgentState) -> str:
    """
    Determine if monitoring should continue or move to evaluation.

    Args:
        state: Current agent state

    Returns:
        "monitor" if jobs still running, "evaluate" if all complete
    """
    # Check if all jobs are complete
    all_complete = all(
        job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]
        for job in state.training_jobs
    )

    if all_complete:
        return "evaluate"
    else:
        return "monitor"


def should_continue_after_error(state: AgentState) -> str:
    """
    Check if workflow should continue or end due to error.

    Args:
        state: Current agent state

    Returns:
        "end" if error occurred, "continue" otherwise
    """
    if state.error or state.current_step == WorkflowStep.ERROR:
        return "end"
    return "continue"


# ================================================================
# Build State Graph
# ================================================================


def build_state_graph() -> StateGraph:
    """
    Build and compile the LangGraph state machine.

    Supports two modes:
    1. ReAct Pattern (feature_react_orchestration=True): Dynamic tool calling via Gateway
    2. Legacy Pipeline (feature_react_orchestration=False): Hardcoded 9-node workflow

    Returns:
        Compiled state graph
    """
    logger.info("Building LangGraph state machine")

    # Create graph
    workflow = StateGraph(AgentState)

    # Check if ReAct orchestration is enabled
    if settings.feature_react_orchestration:
        logger.info("Using ReAct pattern with dynamic tool calling")

        # Simple 2-node graph: route → react
        workflow.add_node("route", route_request_node)
        workflow.add_node("react", react_agent_node)

        # Start with routing
        workflow.set_entry_point("route")

        # Route to ReAct agent or end
        workflow.add_conditional_edges(
            "route",
            should_continue_after_routing,
            {
                "react": "react",  # Use ReAct agent for requests
                "end": END,  # End for simple conversations handled in route
            },
        )

        # ReAct agent always ends
        workflow.add_edge("react", END)

        logger.info("ReAct-based state graph built successfully")

    else:
        logger.info("Using legacy hardcoded pipeline")

        # Add nodes (route is first)
        workflow.add_node("route", route_request_node)
        workflow.add_node("parse", parse_request_node)
        workflow.add_node("search", search_models_node)
        workflow.add_node("estimate", estimate_costs_node)
        workflow.add_node("select", select_candidates_node)
        workflow.add_node("train", launch_training_node)
        workflow.add_node("monitor", monitor_jobs_node)
        workflow.add_node("evaluate", evaluate_results_node)
        workflow.add_node("present", present_options_node)

        # Define edges - start with routing
        workflow.set_entry_point("route")

        # Conditional edge after routing: conversation ends, training continues
        workflow.add_conditional_edges(
            "route",
            should_continue_after_routing,
            {
                "parse": "parse",  # Training request → continue to workflow
                "end": END,  # Conversation → end immediately
            },
        )

        # Training workflow edges with error handling - stop early if any step fails
        workflow.add_conditional_edges(
            "parse",
            should_continue_after_error,
            {
                "continue": "search",
                "end": END,
            },
        )

        workflow.add_conditional_edges(
            "search",
            should_continue_after_error,
            {
                "continue": "estimate",
                "end": END,
            },
        )

        workflow.add_conditional_edges(
            "estimate",
            should_continue_after_error,
            {
                "continue": "select",
                "end": END,
            },
        )

        workflow.add_conditional_edges(
            "select",
            should_continue_after_error,
            {
                "continue": "train",
                "end": END,
            },
        )

        workflow.add_conditional_edges(
            "train",
            should_continue_after_error,
            {
                "continue": "monitor",
                "end": END,
            },
        )

        # Conditional edge for monitoring loop
        workflow.add_conditional_edges(
            "monitor",
            should_continue_monitoring,
            {
                "monitor": "monitor",  # Loop back if jobs still running
                "evaluate": "evaluate",  # Move to evaluation if complete
            },
        )

        workflow.add_edge("evaluate", "present")
        workflow.add_edge("present", END)

        logger.info("Legacy pipeline state graph built successfully")

    return workflow


# ================================================================
# Compile Graph
# ================================================================


# Compile the graph (singleton)
compiled_graph = None


def get_compiled_graph() -> StateGraph:
    """Get or create compiled state graph."""
    global compiled_graph

    if compiled_graph is None:
        graph = build_state_graph()
        compiled_graph = graph.compile()
        logger.info("State graph compiled and ready")

    return compiled_graph
