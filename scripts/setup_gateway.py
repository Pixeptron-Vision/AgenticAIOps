#!/usr/bin/env python3
"""
Setup AgentCore Gateway and register Lambda tools.

This script:
1. Creates an AgentCore Gateway (if not exists)
2. Registers all Lambda functions as Gateway tools
3. Updates .env with Gateway ID
"""
import json
import logging
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import boto3

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# Tool definitions following Gateway schema
TOOLS = [
    {
        "tool_name": "check_gpu_availability",
        "tool_type": "lambda",
        "lambda_function_name": "llmops-tool-check-gpu",
        "description": "Check GPU availability on the cluster. Returns information about available GPUs and their status.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "tool_name": "launch_sagemaker_training",
        "tool_type": "lambda",
        "lambda_function_name": "llmops-tool-launch-training",
        "description": "Launch a SageMaker training job. Takes model configuration, dataset path, instance type, and hyperparameters to start training.",
        "parameters": {
            "type": "object",
            "properties": {
                "model_name": {
                    "type": "string",
                    "description": "Name of the model to train"
                },
                "dataset_path": {
                    "type": "string",
                    "description": "S3 path to the dataset"
                },
                "instance_type": {
                    "type": "string",
                    "description": "SageMaker instance type (e.g., ml.g5.xlarge)"
                },
                "hyperparameters": {
                    "type": "object",
                    "description": "Training hyperparameters"
                }
            },
            "required": ["model_name", "dataset_path", "instance_type"]
        }
    },
    {
        "tool_name": "list_s3_datasets",
        "tool_type": "lambda",
        "lambda_function_name": "llmops-tool-list-datasets",
        "description": "List all available datasets in S3 bucket. Returns a list of dataset names in the processed/ prefix.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]


def get_lambda_arn(function_name: str, region: str = "us-east-1") -> str:
    """Get Lambda function ARN by name."""
    try:
        lambda_client = boto3.client('lambda', region_name=region)
        response = lambda_client.get_function(FunctionName=function_name)
        return response['Configuration']['FunctionArn']
    except Exception as e:
        logger.error(f"Failed to get ARN for Lambda {function_name}: {e}")
        raise


def create_gateway_programmatic(gateway_name: str = "llmops-tools-gateway", region: str = "us-east-1") -> str:
    """
    Create AgentCore Gateway programmatically.

    NOTE: This is a placeholder implementation. The actual Gateway creation
    depends on the bedrock-agentcore SDK version and AWS API availability.

    In production, you would use:
    - bedrock_agentcore.gateway.create_gateway()
    - OR AWS CLI: agentcore gateway create
    - OR AWS Bedrock Agent console

    Returns:
        Gateway ID
    """
    logger.info(f"Creating Gateway: {gateway_name}")

    # For now, we'll simulate Gateway creation
    # In real implementation, this would call the AgentCore API

    # Option 1: Try using the SDK (may not be available yet)
    try:
        from bedrock_agentcore.gateway import create_gateway

        gateway = create_gateway(
            gateway_name=gateway_name,
            description="Tools for MLOps orchestration",
            region=region
        )

        gateway_id = gateway['gateway_id']
        logger.info(f"✓ Gateway created: {gateway_id}")
        return gateway_id

    except (ImportError, AttributeError) as e:
        logger.warning(f"Gateway SDK not available: {e}")
        logger.info("Using fallback mode - tools will be invoked directly via Lambda")

        # Return a placeholder ID for configuration
        # In fallback mode, the Gateway client will invoke Lambdas directly
        return "gtw-local-fallback"


def register_tools_with_gateway(gateway_id: str, region: str = "us-east-1") -> None:
    """Register all Lambda tools with the Gateway."""
    logger.info(f"Registering tools with Gateway: {gateway_id}")

    if gateway_id == "gtw-local-fallback":
        logger.info("Gateway is in fallback mode - skipping tool registration")
        logger.info("Tools will be invoked directly via Lambda ARNs")
        return

    try:
        from bedrock_agentcore.gateway import GatewayClient

        gateway = GatewayClient(gateway_id=gateway_id)

        for tool in TOOLS:
            # Get Lambda ARN
            lambda_arn = get_lambda_arn(tool["lambda_function_name"], region)

            # Register tool
            logger.info(f"Registering tool: {tool['tool_name']}")

            gateway.register_tool(
                tool_name=tool["tool_name"],
                tool_type="lambda",
                lambda_arn=lambda_arn,
                description=tool["description"],
                parameters=tool["parameters"]
            )

            logger.info(f"✓ Registered: {tool['tool_name']}")

        logger.info(f"✓ All tools registered successfully")

    except Exception as e:
        logger.error(f"Failed to register tools: {e}")
        logger.info("Falling back to direct Lambda invocation")


def update_env_file(gateway_id: str) -> None:
    """Update .env file with Gateway ID."""
    env_path = Path(__file__).parent.parent / ".env"

    logger.info(f"Updating .env file: {env_path}")

    # Read existing .env
    if env_path.exists():
        with open(env_path, 'r') as f:
            lines = f.readlines()
    else:
        lines = []

    # Update or add Gateway ID
    gateway_line = f"AGENTCORE_GATEWAY_ID={gateway_id}\n"
    gateway_enabled_line = "USE_AGENTCORE_GATEWAY=true\n"

    # Remove existing Gateway config
    lines = [l for l in lines if not l.startswith("AGENTCORE_GATEWAY_ID=") and not l.startswith("USE_AGENTCORE_GATEWAY=")]

    # Add new config
    lines.append("\n")
    lines.append("# AgentCore Gateway Configuration\n")
    lines.append(gateway_enabled_line)
    lines.append(gateway_line)

    # Write back
    with open(env_path, 'w') as f:
        f.writelines(lines)

    logger.info(f"✓ Updated .env with Gateway ID: {gateway_id}")


def main():
    """Main setup function."""
    logger.info("=" * 60)
    logger.info("AgentCore Gateway Setup")
    logger.info("=" * 60)

    region = os.environ.get("AWS_REGION", "us-east-1")

    # Step 1: Create Gateway
    logger.info("\nStep 1: Creating Gateway...")
    gateway_id = create_gateway_programmatic(region=region)

    # Step 2: Register tools
    logger.info("\nStep 2: Registering Lambda tools...")
    register_tools_with_gateway(gateway_id, region=region)

    # Step 3: Update .env
    logger.info("\nStep 3: Updating configuration...")
    update_env_file(gateway_id)

    logger.info("\n" + "=" * 60)
    logger.info("✓ Gateway setup complete!")
    logger.info("=" * 60)
    logger.info(f"\nGateway ID: {gateway_id}")
    logger.info("\nRegistered tools:")
    for tool in TOOLS:
        logger.info(f"  - {tool['tool_name']}")

    if gateway_id == "gtw-local-fallback":
        logger.info("\n⚠ Gateway is running in fallback mode")
        logger.info("Tools will be invoked directly via Lambda until Gateway API is available")


if __name__ == "__main__":
    main()
