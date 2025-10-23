"""
Model Selection Agent.

Responsible for selecting the optimal model architecture based on constraints.
"""

import csv
import json
import logging
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

import boto3
from boto3.dynamodb.conditions import Key

from llmops_agent.config import settings

logger = logging.getLogger(__name__)


class ModelAgent:
    """Agent for model selection and registry management."""

    def __init__(self, thinking_callback: Optional[Callable] = None):
        """Initialize the model agent.

        Args:
            thinking_callback: Optional callback for streaming thinking process
        """
        self.agent_name = "ModelSelection"
        self.models_cache: Optional[List[Dict[str, Any]]] = None
        self.thinking_callback = thinking_callback
        self.dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
        self.lambda_client = boto3.client("lambda", region_name=settings.aws_region)

    async def _get_best_instance_for_model(
        self,
        vram_required_gb: float,
        budget_usd: float,
        estimated_time_hours: float = 1.0
    ) -> str:
        """
        Intelligently select the best SageMaker instance type based on:
        - VRAM requirements of the model
        - Availability (quota)
        - Cost (within budget)

        Returns the recommended instance type or a safe fallback.
        """
        try:
            # Instance type VRAM capabilities (in GB)
            instance_vram = {
                "ml.g4dn.xlarge": 16,
                "ml.g4dn.2xlarge": 16,
                "ml.g5.xlarge": 24,
                "ml.g5.2xlarge": 24,
                "ml.g5.4xlarge": 24,
                "ml.p3.2xlarge": 16,
            }

            # Call the quota-checking Lambda
            response = self.lambda_client.invoke(
                FunctionName='llmops-tool-check-sagemaker-quotas',
                InvocationType='RequestResponse'
            )

            payload = json.loads(response['Payload'].read())
            body = json.loads(payload.get('body', '{}'))
            instances = body.get('instances', [])

            if not instances:
                logger.warning("No instance information available, using fallback")
                return "ml.g4dn.xlarge"

            # Filter instances that:
            # 1. Are available (recommended=True)
            # 2. Have enough VRAM for the model
            # 3. Cost within budget for estimated time
            suitable_instances = [
                inst for inst in instances
                if inst.get('recommended', False) and
                   instance_vram.get(inst['instance_type'], 0) >= vram_required_gb and
                   (inst.get('cost_per_hour', 999) * estimated_time_hours) <= budget_usd
            ]

            if not suitable_instances:
                if self.thinking_callback:
                    await self.thinking_callback(
                        f"No instances fit budget ${budget_usd} with {vram_required_gb}GB VRAM, "
                        "using cheapest available"
                    )
                # Use cheapest available instance with enough VRAM
                suitable_instances = [
                    inst for inst in instances
                    if inst.get('recommended', False) and
                       instance_vram.get(inst['instance_type'], 0) >= vram_required_gb
                ]

            if suitable_instances:
                # Return the cheapest suitable instance
                best_instance = suitable_instances[0]  # Already sorted by cost
                if self.thinking_callback:
                    await self.thinking_callback(
                        f"Selected {best_instance['instance_type']} "
                        f"(${best_instance['cost_per_hour']}/hr, {best_instance['remaining']} available)"
                    )
                return best_instance['instance_type']

            # Ultimate fallback
            logger.warning(f"Could not find instance with {vram_required_gb}GB VRAM, using fallback")
            return "ml.g4dn.xlarge"

        except Exception as e:
            logger.error(f"Error selecting instance: {e}", exc_info=True)
            return "ml.g4dn.xlarge"

    async def select_model(
        self,
        task_type: str,
        budget_usd: float,
        max_time_hours: Optional[float] = None,
        min_f1: Optional[float] = None,
        max_vram_gb: float = 24.0,
    ) -> Dict[str, Any]:
        """
        Select optimal model architecture based on constraints.

        Algorithm:
        1. Load candidates from CSV registry
        2. Filter by task type
        3. Filter by VRAM constraint
        4. Estimate cost/time for each
        5. Filter by budget and time
        6. Filter by min F1 (if specified)
        7. Rank by cost (cheapest first)
        8. Return top candidate with alternatives

        Args:
            task_type: ML task (e.g., "token-classification")
            budget_usd: Maximum budget in USD
            max_time_hours: Maximum training time in hours
            min_f1: Minimum F1 score required
            max_vram_gb: Maximum VRAM available

        Returns:
            Model selection result with recommended model and alternatives
        """
        try:
            logger.info(f"Selecting model for {task_type} with budget ${budget_usd}")

            # Load models
            models = await self._load_models()

            # Filter by task type
            candidates = [m for m in models if m.get("task_type") == task_type]
            logger.debug(f"Found {len(candidates)} models for task {task_type}")

            # Filter by VRAM
            candidates = [m for m in candidates if m.get("vram_gb", 0) <= max_vram_gb]

            # Intelligently select best instance type for each model based on current availability
            for model in candidates:
                # Always select instance dynamically based on real-time quota availability
                best_instance = await self._get_best_instance_for_model(
                    vram_required_gb=model.get("vram_gb", 16),
                    budget_usd=budget_usd,
                    estimated_time_hours=1.0  # Rough estimate for initial selection
                )
                model["instance_type"] = best_instance

                # Now estimate cost with the intelligently selected instance
                estimate = await self._estimate_model_cost(
                    model=model,
                    dataset_size=2000,  # Typical for POC
                    use_peft=True,
                )
                model["estimated_cost"] = estimate["cost_usd"]
                model["estimated_time_hours"] = estimate["time_hours"]

            # Filter by budget
            candidates = [m for m in candidates if m["estimated_cost"] <= budget_usd]

            # Filter by time
            if max_time_hours:
                candidates = [m for m in candidates if m["estimated_time_hours"] <= max_time_hours]

            # Filter by F1
            if min_f1:
                candidates = [m for m in candidates if m.get("baseline_f1", 0) >= min_f1]

            # *** NEW: Filter by instance quota availability ***
            if self.thinking_callback:
                await self.thinking_callback(f"Checking instance quotas for {len(candidates)} candidates...")

            quota_filtered = []
            for model in candidates:
                # Instance type was already intelligently selected above
                instance_type = model.get("instance_type", "ml.g4dn.xlarge")
                quota_check = await self._check_instance_quota(instance_type)

                if quota_check["available"]:
                    model["quota_status"] = "available"
                    model["quota_info"] = quota_check["quota_info"]
                    quota_filtered.append(model)

                    if self.thinking_callback:
                        quota_info = quota_check["quota_info"]
                        await self.thinking_callback(
                            f"✓ {model['model_id']}: {instance_type} available "
                            f"({quota_info['available']}/{quota_info['total']} free)"
                        )
                else:
                    if self.thinking_callback:
                        await self.thinking_callback(
                            f"✗ {model['model_id']}: {instance_type} - {quota_check['reason']}"
                        )

            candidates = quota_filtered

            # Sort by cost (cheapest first)
            candidates.sort(key=lambda x: x["estimated_cost"])

            if not candidates:
                return {
                    "success": False,
                    "error": "No models meet constraints",
                    "suggestion": "Try increasing budget or relaxing F1 requirement",
                }

            # Return top candidate with alternatives
            return {
                "success": True,
                "recommended": candidates[0],
                "alternatives": candidates[1:3] if len(candidates) > 1 else [],
                "total_candidates": len(candidates),
            }

        except Exception as e:
            logger.error(f"Error selecting model: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    async def _load_models(self) -> List[Dict[str, Any]]:
        """Load models from DynamoDB registry."""
        if self.models_cache:
            return self.models_cache

        if self.thinking_callback:
            await self.thinking_callback("Querying model registry in DynamoDB...")

        table = self.dynamodb.Table("llmops-model-registry")
        response = table.scan()

        models = []
        for item in response.get("Items", []):
            models.append({
                "model_id": item["model_id"],
                "task_type": item["task_type"],
                "params": int(item["params"]),
                "vram_gb": float(item["vram_gb"]),
                "baseline_f1": float(item["baseline_f1"]),
                "instance_type": item.get("instance_type", "ml.g5.xlarge"),
                "training_image": item.get("training_image"),
                "min_transformers_version": item.get("min_transformers_version", "4.30"),
                "description": item.get("description", ""),
            })

        self.models_cache = models
        logger.info(f"Loaded {len(models)} models from DynamoDB")

        if self.thinking_callback:
            await self.thinking_callback(f"Found {len(models)} models in registry")

        return models

    async def _check_instance_quota(self, instance_type: str) -> Dict[str, Any]:
        """Check if instance type is available.

        Returns:
            Dict with 'available' (bool) and 'quota_info' (dict)
        """
        table = self.dynamodb.Table("llmops-instance-quotas")

        try:
            response = table.get_item(Key={"instance_type": instance_type})

            if "Item" not in response:
                return {"available": False, "reason": "Instance type not in quota table"}

            item = response["Item"]
            available = int(item.get("available", 0))
            total = int(item.get("total_quota", 0))

            if available > 0:
                return {
                    "available": True,
                    "quota_info": {
                        "available": available,
                        "total": total,
                        "in_use": int(item.get("in_use", 0)),
                    }
                }
            else:
                return {
                    "available": False,
                    "reason": f"No quota available ({available}/{total} in use)",
                    "quota_info": {
                        "available": available,
                        "total": total,
                        "in_use": int(item.get("in_use", 0)),
                    }
                }
        except Exception as e:
            logger.error(f"Error checking quota for {instance_type}: {e}")
            return {"available": False, "reason": f"Error: {str(e)}"}

    async def _estimate_model_cost(
        self,
        model: Dict[str, Any],
        dataset_size: int,
        use_peft: bool = True,
    ) -> Dict[str, Any]:
        """
        Estimate training cost and time.

        Heuristics (calibrated from benchmarks):
        - LoRA: ~0.15 min per 1M params per 1k samples per epoch (efficient fine-tuning)
        - Full FT: ~0.5 min per 1M params per 1k samples per epoch

        Examples:
        - DistilBERT (66M) on 2k samples: ~0.6 hours, ~$0.73
        - BERT-base (110M) on 2k samples: ~1.0 hours, ~$1.21
        - RoBERTa-base (125M) on 2k samples: ~1.1 hours, ~$1.33
        """
        params = model.get("params", 66_000_000)
        params_millions = params / 1_000_000
        samples_thousands = dataset_size / 1000
        num_epochs = 3

        # Estimate time (more realistic for LoRA/QLoRA fine-tuning)
        if use_peft:
            minutes_per_epoch = params_millions * samples_thousands * 0.15
        else:
            minutes_per_epoch = params_millions * samples_thousands * 0.5

        total_minutes = minutes_per_epoch * num_epochs * 1.2  # 20% overhead
        total_hours = total_minutes / 60

        # Get instance-specific pricing (instance was intelligently selected in select_model)
        instance_type = model.get("instance_type", "ml.g4dn.xlarge")
        hourly_rates = {
            "ml.g4dn.xlarge": 0.736,   # 16 GB VRAM
            "ml.g5.xlarge": 1.21,       # 24 GB VRAM
            "ml.g5.2xlarge": 1.52,      # 24 GB VRAM (more compute)
            "ml.g5.4xlarge": 2.03,      # 96 GB VRAM
            "ml.g5.12xlarge": 7.09,     # 192 GB VRAM
        }
        hourly_rate = hourly_rates.get(instance_type, 1.21)
        cost_usd = total_hours * hourly_rate

        return {
            "instance_type": instance_type,
            "time_hours": round(total_hours, 2),
            "cost_usd": round(cost_usd, 2),
        }

    def _parse_params(self, params_str: str) -> int:
        """Parse parameter count from string."""
        if not params_str:
            return 0

        params_str = params_str.strip().upper()

        if "B" in params_str:
            return int(float(params_str.replace("B", "")) * 1_000_000_000)
        elif "M" in params_str:
            return int(float(params_str.replace("M", "")) * 1_000_000)
        else:
            try:
                return int(params_str)
            except ValueError:
                return 66_000_000  # Default to DistilBERT size
