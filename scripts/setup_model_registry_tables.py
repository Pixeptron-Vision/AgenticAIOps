#!/usr/bin/env python3
"""
Setup DynamoDB tables for model registry and instance quotas.

Run this script to create the required tables:
    poetry run python scripts/setup_model_registry_tables.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import boto3
from botocore.exceptions import ClientError

from llmops_agent.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_model_registry_table():
    """
    Create model registry table.

    Schema:
    - PK: model_id (e.g., "distilbert-base-cased")
    - Attributes: task_type, params, vram_gb, baseline_f1, instance_type, training_image, etc.
    """
    dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
    table_name = "llmops-model-registry"

    try:
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": "model_id", "KeyType": "HASH"},  # Partition key
            ],
            AttributeDefinitions=[
                {"AttributeName": "model_id", "AttributeType": "S"},
                {"AttributeName": "task_type", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "task_type-index",
                    "KeySchema": [
                        {"AttributeName": "task_type", "KeyType": "HASH"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {
                        "ReadCapacityUnits": 5,
                        "WriteCapacityUnits": 5,
                    },
                }
            ],
            ProvisionedThroughput={
                "ReadCapacityUnits": 5,
                "WriteCapacityUnits": 5,
            },
        )

        # Wait for table to be created
        logger.info(f"Creating table {table_name}...")
        table.wait_until_exists()
        logger.info(f"✓ Table {table_name} created successfully")
        return True

    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            logger.info(f"✓ Table {table_name} already exists")
            return True
        else:
            logger.error(f"Error creating table {table_name}: {e}")
            return False


def create_instance_quotas_table():
    """
    Create instance quotas table.

    Schema:
    - PK: instance_type (e.g., "ml.g5.xlarge")
    - Attributes: total_quota, in_use, available, hourly_rate_usd
    """
    dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
    table_name = "llmops-instance-quotas"

    try:
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": "instance_type", "KeyType": "HASH"},  # Partition key
            ],
            AttributeDefinitions=[
                {"AttributeName": "instance_type", "AttributeType": "S"},
            ],
            ProvisionedThroughput={
                "ReadCapacityUnits": 5,
                "WriteCapacityUnits": 5,
            },
        )

        # Wait for table to be created
        logger.info(f"Creating table {table_name}...")
        table.wait_until_exists()
        logger.info(f"✓ Table {table_name} created successfully")
        return True

    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            logger.info(f"✓ Table {table_name} already exists")
            return True
        else:
            logger.error(f"Error creating table {table_name}: {e}")
            return False


def seed_instance_quotas():
    """Seed instance quotas table with default values."""
    dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
    table = dynamodb.Table("llmops-instance-quotas")

    quotas = [
        {
            "instance_type": "ml.g4dn.xlarge",
            "total_quota": 2,  # We have 2x g4dn.xlarge quota
            "in_use": 0,
            "available": 2,
            "hourly_rate_usd": 0.736,
            "vram_gb": 16,
        },
        {
            "instance_type": "ml.g5.xlarge",
            "total_quota": 1,  # Assume 1 for now
            "in_use": 0,
            "available": 1,
            "hourly_rate_usd": 1.21,
            "vram_gb": 24,
        },
        {
            "instance_type": "ml.g5.2xlarge",
            "total_quota": 0,  # Not available yet
            "in_use": 0,
            "available": 0,
            "hourly_rate_usd": 1.52,
            "vram_gb": 24,
        },
        {
            "instance_type": "ml.g5.4xlarge",
            "total_quota": 0,  # Not available yet
            "in_use": 0,
            "available": 0,
            "hourly_rate_usd": 2.03,
            "vram_gb": 96,
        },
    ]

    logger.info("Seeding instance quotas...")
    for quota in quotas:
        table.put_item(Item=quota)
        logger.info(f"  ✓ {quota['instance_type']}: {quota['available']}/{quota['total_quota']} available")

    logger.info("✓ Instance quotas seeded successfully")


def main():
    """Setup all tables."""
    logger.info("Setting up DynamoDB tables for model registry...")

    # Create tables
    success1 = create_model_registry_table()
    success2 = create_instance_quotas_table()

    if not (success1 and success2):
        logger.error("Failed to create tables")
        sys.exit(1)

    # Seed quotas
    seed_instance_quotas()

    logger.info("\n✓ All tables created successfully!")
    logger.info("\nNext steps:")
    logger.info("  1. Run migration script: poetry run python scripts/migrate_csv_to_dynamodb.py")
    logger.info("  2. Restart the API server")


if __name__ == "__main__":
    main()
