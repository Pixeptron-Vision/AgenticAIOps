#!/usr/bin/env python3
"""
Migrate model data from CSV to DynamoDB.

Run this script after creating tables:
    poetry run python scripts/migrate_csv_to_dynamodb.py
"""

import csv
import logging
import sys
from decimal import Decimal
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import boto3

from llmops_agent.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_params(params_str: str) -> int:
    """Parse parameter count from string like '66M' or '3B'."""
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
            return 66_000_000  # Default


def migrate_models():
    """Migrate models from CSV to DynamoDB."""
    csv_path = Path(__file__).parent.parent / "huggingface_trending_model_metrics.csv"

    if not csv_path.exists():
        logger.error(f"CSV file not found: {csv_path}")
        sys.exit(1)

    dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
    table = dynamodb.Table("llmops-model-registry")

    logger.info(f"Migrating models from {csv_path}...")

    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        count = 0

        for row in reader:
            item = {
                "model_id": row["Model_Name"],
                "model_name": row["Model_Name"],  # Human-readable name (same for now)
                "task_type": row["Task_Type"],
                "params": parse_params(row["Parameters"]),
                "vram_gb": Decimal(row["VRAM_GB"]),
                "baseline_f1": Decimal(row["Baseline_F1"]),
                "open_source": row["Open_Source"] == "Yes",
                "description": row["Description"],
                "instance_type": row["Instance_Type"],
                "training_image": row["Training_Image"],
                "min_transformers_version": row["Min_Transformers_Version"],
            }

            table.put_item(Item=item)
            count += 1
            logger.info(f"  ✓ Migrated: {item['model_id']} ({item['task_type']})")

    logger.info(f"\n✓ Successfully migrated {count} models to DynamoDB!")


def main():
    """Run migration."""
    logger.info("Starting CSV → DynamoDB migration...")
    migrate_models()
    logger.info("\n✓ Migration complete!")
    logger.info("\nYou can now query models from DynamoDB instead of CSV")


if __name__ == "__main__":
    main()
