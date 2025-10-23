"""
Configuration management using Pydantic Settings.

Loads environment variables from .env file and provides
type-safe configuration access throughout the application.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ================================================================
    # AWS Configuration
    # ================================================================
    aws_region: str = Field(default="us-east-1", description="AWS region")
    aws_account_id: str = Field(..., description="AWS account ID")
    aws_access_key_id: str = Field(..., description="AWS access key")
    aws_secret_access_key: str = Field(..., description="AWS secret key")

    # IAM Roles
    sagemaker_execution_role_arn: Optional[str] = Field(
        default=None, description="SageMaker execution role ARN"
    )
    lambda_execution_role_arn: Optional[str] = Field(
        default=None, description="Lambda execution role ARN"
    )
    bedrock_agent_role_arn: Optional[str] = Field(
        default=None, description="Bedrock agent role ARN"
    )

    # ================================================================
    # S3 Configuration
    # ================================================================
    s3_bucket_datasets: str = Field(default="llmops-agent-datasets")
    s3_bucket_models: str = Field(default="llmops-agent-models")
    s3_bucket_artifacts: str = Field(default="llmops-agent-artifacts")

    s3_prefix_raw_datasets: str = Field(default="raw/")
    s3_prefix_processed_datasets: str = Field(default="processed/")
    s3_prefix_checkpoints: str = Field(default="checkpoints/")
    s3_prefix_final_models: str = Field(default="final/")

    # ================================================================
    # DynamoDB Configuration
    # ================================================================
    dynamodb_table_jobs: str = Field(default="llmops-jobs")
    dynamodb_table_sessions: str = Field(default="llmops-sessions")
    dynamodb_table_models: str = Field(default="llmops-models")

    # ================================================================
    # Bedrock Configuration
    # ================================================================
    bedrock_model_id: str = Field(
        default="anthropic.claude-3-5-sonnet-20241022-v2:0"
    )
    bedrock_model_region: str = Field(default="us-east-1")
    bedrock_agent_id: Optional[str] = Field(default=None)
    bedrock_agent_alias_id: Optional[str] = Field(default=None)
    bedrock_max_tokens: int = Field(default=4096)
    bedrock_temperature: float = Field(default=0.7)
    bedrock_top_p: float = Field(default=0.9)

    # ================================================================
    # SageMaker Configuration
    # ================================================================
    sagemaker_instance_type: str = Field(default="ml.g5.xlarge")
    sagemaker_instance_count: int = Field(default=1)
    sagemaker_transformers_version: str = Field(default="4.37")
    sagemaker_pytorch_version: str = Field(default="2.1")
    sagemaker_python_version: str = Field(default="py310")
    sagemaker_max_runtime_seconds: int = Field(default=7200)
    sagemaker_volume_size_gb: int = Field(default=30)

    # ================================================================
    # MLflow Configuration
    # ================================================================
    mlflow_tracking_uri: str = Field(default="http://localhost:5000")
    mlflow_experiment_name: str = Field(default="llmops-ner-cier")
    mlflow_artifact_location: str = Field(
        default="s3://llmops-agent-artifacts/mlflow/"
    )

    # ================================================================
    # Application Configuration
    # ================================================================
    environment: str = Field(default="development")
    debug: bool = Field(default=True)
    log_level: str = Field(default="INFO")

    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8003)
    api_workers: int = Field(default=4)

    cors_origins: str = Field(default="http://localhost:3000,http://localhost:3001")

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    api_key_enabled: bool = Field(default=False)
    api_key: Optional[str] = Field(default=None)

    session_secret_key: str = Field(
        default="dev-secret-change-in-production"
    )
    session_timeout_hours: int = Field(default=24)

    # ================================================================
    # Training Defaults
    # ================================================================
    default_learning_rate: float = Field(default=2e-5)
    default_batch_size: int = Field(default=16)
    default_num_epochs: int = Field(default=3)
    default_warmup_steps: int = Field(default=500)

    default_use_peft: bool = Field(default=True)
    default_lora_r: int = Field(default=8)
    default_lora_alpha: int = Field(default=16)
    default_lora_dropout: float = Field(default=0.1)

    # ================================================================
    # Budget Configuration
    # ================================================================
    default_session_budget_usd: float = Field(default=10.0)
    total_budget_cap_usd: float = Field(default=100.0)
    enable_cost_tracking: bool = Field(default=True)
    cost_alert_threshold_percent: int = Field(default=80)

    # ================================================================
    # Model Registry
    # ================================================================
    model_registry_csv_path: str = Field(
        default="./huggingface_trending_model_metrics.csv",
        description="Path to model registry CSV file"
    )

    # ================================================================
    # Feature Flags
    # ================================================================
    feature_hybrid_routing: bool = Field(default=False)
    feature_on_prem_agents: bool = Field(default=False)
    feature_spot_instances: bool = Field(default=False)
    feature_react_orchestration: bool = Field(
        default=True,
        description="Use ReAct pattern with dynamic tool calling instead of hardcoded pipeline"
    )

    # ================================================================
    # AgentCore Runtime Configuration
    # ================================================================
    use_agentcore_runtime: bool = Field(
        default=True,
        description="Route requests to AgentCore Runtime instead of local LangGraph"
    )
    agentcore_runtime_arn: Optional[str] = Field(
        default=None,
        description="ARN of the deployed AgentCore Runtime (e.g., arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/agent-name-xyz)"
    )
    agentcore_timeout: int = Field(
        default=300,
        description="AgentCore invocation timeout in seconds"
    )

    # ================================================================
    # AgentCore Gateway Configuration
    # ================================================================
    use_agentcore_gateway: bool = Field(
        default=True,
        description="Use AgentCore Gateway for tool invocation in LangGraph"
    )
    agentcore_gateway_id: Optional[str] = Field(
        default=None,
        description="Gateway ID for AgentCore Gateway (e.g., gtw-xyz789abc123)"
    )

    # Legacy Lambda Configuration (deprecated - use AgentCore Runtime)
    use_agentcore_lambda: bool = Field(
        default=False,
        description="[DEPRECATED] Route requests to AgentCore Lambda"
    )
    agentcore_lambda_function_name: str = Field(
        default="llmops-agentcore",
        description="[DEPRECATED] Name of the AgentCore Lambda function"
    )

    # ================================================================
    # Mock Flags (for testing)
    # ================================================================
    mock_bedrock: bool = Field(default=False)
    mock_sagemaker: bool = Field(default=False)
    mock_s3: bool = Field(default=False)
    mock_dynamodb: bool = Field(default=False)


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Uses lru_cache to ensure settings are loaded only once.
    """
    return Settings()


# Global settings instance
settings = get_settings()
