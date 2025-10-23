"""
Pytest configuration and shared fixtures.

Provides common fixtures for testing the LLMOps Agent application.
"""

import os
from typing import Generator

import pytest
from dotenv import load_dotenv

# Load environment variables for tests
load_dotenv()


@pytest.fixture(scope="session")
def aws_credentials():
    """Mock AWS credentials for tests."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def settings():
    """Get application settings."""
    from llmops_agent.config import get_settings

    return get_settings()


@pytest.fixture
def mock_s3(aws_credentials):
    """Mock S3 service using moto."""
    from moto import mock_s3

    with mock_s3():
        yield


@pytest.fixture
def mock_dynamodb(aws_credentials):
    """Mock DynamoDB service using moto."""
    from moto import mock_dynamodb

    with mock_dynamodb():
        yield


@pytest.fixture
def mock_sagemaker(aws_credentials):
    """Mock SageMaker service using moto."""
    from moto import mock_sagemaker

    with mock_sagemaker():
        yield
