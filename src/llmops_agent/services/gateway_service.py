"""
AgentCore Gateway client service.

This module provides a client for interacting with AgentCore Gateway,
which transforms Lambda functions into agent-compatible tools with
semantic search capabilities.

FALLBACK MODE: If Gateway API is not available, this client falls back to
direct Lambda invocation while maintaining the same interface.
"""
import json
import logging
from functools import lru_cache
from typing import Any, Dict, List, Optional

import boto3

from llmops_agent.config import settings

logger = logging.getLogger(__name__)


class GatewayClient:
    """
    Client for AgentCore Gateway tool invocation.

    The Gateway client provides:
    1. Tool registration - Register Lambda functions as tools
    2. Semantic search - Find relevant tools based on user query
    3. Tool invocation - Execute tools via Gateway

    FALLBACK MODE: If gateway_id is 'gtw-local-fallback', tools are invoked
    directly via Lambda, maintaining the same interface.
    """

    # Tool registry for fallback mode
    _TOOL_REGISTRY = {
        "check_gpu_availability": {
            "lambda_function_name": "llmops-tool-check-gpu",
            "description": "Check GPU availability on the cluster",
        },
        "check_sagemaker_quotas": {
            "lambda_function_name": "llmops-tool-check-sagemaker-quotas",
            "description": "Check AWS SageMaker instance quotas and availability for GPU instances (ml.g4dn.xlarge, ml.g5.xlarge, ml.p3.2xlarge, etc.). Returns available instances, costs per hour, and quota limits.",
        },
        "launch_sagemaker_training": {
            "lambda_function_name": "llmops-tool-launch-training",
            "description": "Launch a SageMaker training job",
        },
        "list_s3_datasets": {
            "lambda_function_name": "llmops-tool-list-datasets",
            "description": "List all available datasets in S3 bucket",
        },
        "prepare_dataset": {
            "lambda_function_name": "llmops-tool-prepare-dataset",
            "description": "Prepare and validate dataset for ML training. Checks data format, normalizes annotations, removes invalid records, and tracks preparation status to avoid redundant work. Use force_prepare=true to re-prepare already prepared datasets.",
        },
    }

    def __init__(self, gateway_id: Optional[str] = None):
        """
        Initialize Gateway client.

        Args:
            gateway_id: Gateway ID (defaults to settings.agentcore_gateway_id)
        """
        self.gateway_id = gateway_id or settings.agentcore_gateway_id

        if not self.gateway_id:
            logger.warning(
                "Gateway ID not configured. Gateway features will be disabled. "
                "Set AGENTCORE_GATEWAY_ID environment variable or use fallback mode."
            )
            self._enabled = False
            self._fallback_mode = False
        elif self.gateway_id == "gtw-local-fallback":
            self._enabled = True
            self._fallback_mode = True
            self._lambda_client = boto3.client('lambda', region_name=settings.aws_region)
            logger.info("Gateway client initialized in FALLBACK mode (direct Lambda invocation)")
        else:
            self._enabled = True
            self._fallback_mode = False
            logger.info(f"Gateway client initialized with ID: {self.gateway_id}")

    @property
    def enabled(self) -> bool:
        """Check if Gateway is enabled and configured."""
        return self._enabled

    def register_tool(
        self,
        tool_name: str,
        tool_type: str,
        description: str,
        parameters: Dict[str, Any],
        lambda_arn: Optional[str] = None,
        api_endpoint: Optional[str] = None,
        http_method: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Register a tool with the Gateway.

        Args:
            tool_name: Unique name for the tool
            tool_type: Type of tool ('lambda', 'api', or 'mcp')
            description: Detailed description for semantic search
            parameters: JSON schema for tool parameters
            lambda_arn: ARN of Lambda function (required for type='lambda')
            api_endpoint: API endpoint URL (required for type='api')
            http_method: HTTP method (required for type='api')

        Returns:
            Registration response
        """
        if not self.enabled:
            raise RuntimeError("Gateway is not configured")

        try:
            from bedrock_agentcore.gateway import GatewayClient as AGCGatewayClient

            gateway = AGCGatewayClient(gateway_id=self.gateway_id)

            if tool_type == "lambda":
                if not lambda_arn:
                    raise ValueError("lambda_arn is required for lambda tools")

                result = gateway.register_tool(
                    tool_name=tool_name,
                    tool_type="lambda",
                    lambda_arn=lambda_arn,
                    description=description,
                    parameters=parameters,
                )

            elif tool_type == "api":
                if not api_endpoint or not http_method:
                    raise ValueError("api_endpoint and http_method are required for api tools")

                result = gateway.register_tool(
                    tool_name=tool_name,
                    tool_type="api",
                    api_endpoint=api_endpoint,
                    http_method=http_method,
                    description=description,
                    parameters=parameters,
                )

            else:
                raise ValueError(f"Unsupported tool type: {tool_type}")

            logger.info(f"Successfully registered tool: {tool_name}")
            return result

        except Exception as e:
            logger.error(f"Failed to register tool {tool_name}: {e}")
            raise

    def search_tools(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for relevant tools using semantic search.

        Args:
            query: Natural language query
            top_k: Number of top results to return

        Returns:
            List of tools with relevance scores
        """
        if not self.enabled:
            logger.warning("Gateway is disabled, returning empty tool list")
            return []

        try:
            from bedrock_agentcore.gateway import GatewayClient as AGCGatewayClient

            gateway = AGCGatewayClient(gateway_id=self.gateway_id)

            results = gateway.search_tools(query=query, top_k=top_k)

            logger.info(f"Found {len(results)} relevant tools for query: {query}")
            return results

        except Exception as e:
            logger.error(f"Failed to search tools: {e}")
            return []

    def invoke_tool(
        self,
        tool_name: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Invoke a registered tool via Gateway.

        Args:
            tool_name: Name of the tool to invoke
            parameters: Tool parameters

        Returns:
            Tool execution result
        """
        if not self.enabled:
            raise RuntimeError("Gateway is not configured")

        if parameters is None:
            parameters = {}

        # FALLBACK MODE: Direct Lambda invocation
        if self._fallback_mode:
            return self._invoke_lambda_directly(tool_name, parameters)

        # STANDARD MODE: Use Gateway API
        try:
            from bedrock_agentcore.gateway import GatewayClient as AGCGatewayClient

            gateway = AGCGatewayClient(gateway_id=self.gateway_id)

            logger.info(f"Invoking tool via Gateway: {tool_name}")

            result = gateway.invoke_tool(
                tool_name=tool_name,
                parameters=parameters,
            )

            logger.info(f"Tool {tool_name} executed successfully")
            return result

        except Exception as e:
            logger.error(f"Failed to invoke tool {tool_name}: {e}")
            raise

    def _invoke_lambda_directly(
        self,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Invoke Lambda function directly (fallback mode).

        Args:
            tool_name: Name of the tool
            parameters: Tool parameters

        Returns:
            Lambda invocation result
        """
        if tool_name not in self._TOOL_REGISTRY:
            raise ValueError(f"Unknown tool: {tool_name}")

        function_name = self._TOOL_REGISTRY[tool_name]["lambda_function_name"]

        logger.info(f"Invoking Lambda directly: {function_name} (tool: {tool_name})")

        try:
            response = self._lambda_client.invoke(
                FunctionName=function_name,
                InvocationType='RequestResponse',
                Payload=json.dumps(parameters)
            )

            # Parse Lambda response
            payload = json.loads(response['Payload'].read())

            # Handle Lambda error
            if 'FunctionError' in response:
                error_msg = payload.get('errorMessage', 'Unknown error')
                raise RuntimeError(f"Lambda error: {error_msg}")

            # Extract body from Lambda response
            if isinstance(payload, dict) and 'body' in payload:
                body = payload['body']
                if isinstance(body, str):
                    return json.loads(body)
                return body

            return payload

        except Exception as e:
            logger.error(f"Failed to invoke Lambda {function_name}: {e}")
            raise

    def list_tools(self) -> List[Dict[str, Any]]:
        """
        List all registered tools in the Gateway.

        Returns:
            List of registered tools
        """
        if not self.enabled:
            logger.warning("Gateway is disabled, returning empty tool list")
            return []

        # FALLBACK MODE: Return local registry
        if self._fallback_mode:
            tools = []
            for tool_name, tool_config in self._TOOL_REGISTRY.items():
                tools.append({
                    "name": tool_name,
                    "description": tool_config["description"],
                    "lambda_function": tool_config["lambda_function_name"]
                })
            return tools

        # STANDARD MODE: Use Gateway API
        try:
            from bedrock_agentcore.gateway import GatewayClient as AGCGatewayClient

            gateway = AGCGatewayClient(gateway_id=self.gateway_id)

            tools = gateway.list_tools()

            logger.info(f"Found {len(tools)} registered tools")
            return tools

        except Exception as e:
            logger.error(f"Failed to list tools: {e}")
            return []


@lru_cache
def get_gateway_client() -> GatewayClient:
    """
    Get cached Gateway client instance.

    Returns:
        Singleton Gateway client
    """
    return GatewayClient()


# Module-level convenience functions
def invoke_tool(tool_name: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Convenience function to invoke a tool via Gateway.

    Args:
        tool_name: Name of the tool to invoke
        parameters: Tool parameters

    Returns:
        Tool execution result
    """
    client = get_gateway_client()
    return client.invoke_tool(tool_name, parameters)


def search_tools(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Convenience function to search for relevant tools.

    Args:
        query: Natural language query
        top_k: Number of top results to return

    Returns:
        List of tools with relevance scores
    """
    client = get_gateway_client()
    return client.search_tools(query, top_k)
