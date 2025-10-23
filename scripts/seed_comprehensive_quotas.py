#!/usr/bin/env python3
"""
Seed comprehensive SageMaker instance quotas.

Includes all GPU instance types available in SageMaker.
Run this to populate the quota table with realistic data.
"""

import logging
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import boto3

from llmops_agent.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_comprehensive_quotas():
    """Seed quota table with all SageMaker GPU instances."""
    dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
    table = dynamodb.Table("llmops-instance-quotas")

    # Comprehensive list of SageMaker GPU instances
    # Pricing from https://aws.amazon.com/sagemaker/pricing/
    quotas = [
        # G4dn Family (NVIDIA T4, 16GB VRAM) - Most cost-effective for training
        {
            "instance_type": "ml.g4dn.xlarge",
            "total_quota": 2,  # What we actually have
            "in_use": 0,
            "available": 2,
            "hourly_rate_usd": Decimal("0.736"),
            "vram_gb": 16,
            "gpu_count": 1,
            "gpu_type": "NVIDIA T4",
        },
        {
            "instance_type": "ml.g4dn.2xlarge",
            "total_quota": 0,
            "in_use": 0,
            "available": 0,
            "hourly_rate_usd": Decimal("0.94"),
            "vram_gb": 16,
            "gpu_count": 1,
            "gpu_type": "NVIDIA T4",
        },
        {
            "instance_type": "ml.g4dn.4xlarge",
            "total_quota": 0,
            "in_use": 0,
            "available": 0,
            "hourly_rate_usd": Decimal("1.505"),
            "vram_gb": 16,
            "gpu_count": 1,
            "gpu_type": "NVIDIA T4",
        },
        {
            "instance_type": "ml.g4dn.8xlarge",
            "total_quota": 0,
            "in_use": 0,
            "available": 0,
            "hourly_rate_usd": Decimal("2.72"),
            "vram_gb": 16,
            "gpu_count": 1,
            "gpu_type": "NVIDIA T4",
        },
        {
            "instance_type": "ml.g4dn.12xlarge",
            "total_quota": 0,
            "in_use": 0,
            "available": 0,
            "hourly_rate_usd": Decimal("4.89"),
            "vram_gb": 64,  # 4x T4
            "gpu_count": 4,
            "gpu_type": "NVIDIA T4",
        },
        {
            "instance_type": "ml.g4dn.16xlarge",
            "total_quota": 0,
            "in_use": 0,
            "available": 0,
            "hourly_rate_usd": Decimal("5.44"),
            "vram_gb": 16,
            "gpu_count": 1,
            "gpu_type": "NVIDIA T4",
        },
        # G5 Family (NVIDIA A10G, 24GB VRAM) - Best for large models
        {
            "instance_type": "ml.g5.xlarge",
            "total_quota": 1,  # What we have
            "in_use": 0,
            "available": 1,
            "hourly_rate_usd": Decimal("1.21"),
            "vram_gb": 24,
            "gpu_count": 1,
            "gpu_type": "NVIDIA A10G",
        },
        {
            "instance_type": "ml.g5.2xlarge",
            "total_quota": 0,
            "in_use": 0,
            "available": 0,
            "hourly_rate_usd": Decimal("1.52"),
            "vram_gb": 24,
            "gpu_count": 1,
            "gpu_type": "NVIDIA A10G",
        },
        {
            "instance_type": "ml.g5.4xlarge",
            "total_quota": 0,
            "in_use": 0,
            "available": 0,
            "hourly_rate_usd": Decimal("2.03"),
            "vram_gb": 24,
            "gpu_count": 1,
            "gpu_type": "NVIDIA A10G",
        },
        {
            "instance_type": "ml.g5.8xlarge",
            "total_quota": 0,
            "in_use": 0,
            "available": 0,
            "hourly_rate_usd": Decimal("3.06"),
            "vram_gb": 24,
            "gpu_count": 1,
            "gpu_type": "NVIDIA A10G",
        },
        {
            "instance_type": "ml.g5.12xlarge",
            "total_quota": 0,
            "in_use": 0,
            "available": 0,
            "hourly_rate_usd": Decimal("7.09"),
            "vram_gb": 96,  # 4x A10G
            "gpu_count": 4,
            "gpu_type": "NVIDIA A10G",
        },
        {
            "instance_type": "ml.g5.16xlarge",
            "total_quota": 0,
            "in_use": 0,
            "available": 0,
            "hourly_rate_usd": Decimal("6.12"),
            "vram_gb": 24,
            "gpu_count": 1,
            "gpu_type": "NVIDIA A10G",
        },
        {
            "instance_type": "ml.g5.24xlarge",
            "total_quota": 0,
            "in_use": 0,
            "available": 0,
            "hourly_rate_usd": Decimal("10.18"),
            "vram_gb": 96,  # 4x A10G
            "gpu_count": 4,
            "gpu_type": "NVIDIA A10G",
        },
        {
            "instance_type": "ml.g5.48xlarge",
            "total_quota": 0,
            "in_use": 0,
            "available": 0,
            "hourly_rate_usd": Decimal("20.36"),
            "vram_gb": 192,  # 8x A10G
            "gpu_count": 8,
            "gpu_type": "NVIDIA A10G",
        },
        # P3 Family (NVIDIA V100, 16GB VRAM) - Older but powerful
        {
            "instance_type": "ml.p3.2xlarge",
            "total_quota": 0,
            "in_use": 0,
            "available": 0,
            "hourly_rate_usd": Decimal("3.825"),
            "vram_gb": 16,
            "gpu_count": 1,
            "gpu_type": "NVIDIA V100",
        },
        {
            "instance_type": "ml.p3.8xlarge",
            "total_quota": 0,
            "in_use": 0,
            "available": 0,
            "hourly_rate_usd": Decimal("14.688"),
            "vram_gb": 64,  # 4x V100
            "gpu_count": 4,
            "gpu_type": "NVIDIA V100",
        },
        {
            "instance_type": "ml.p3.16xlarge",
            "total_quota": 0,
            "in_use": 0,
            "available": 0,
            "hourly_rate_usd": Decimal("28.152"),
            "vram_gb": 128,  # 8x V100
            "gpu_count": 8,
            "gpu_type": "NVIDIA V100",
        },
        # P4d Family (NVIDIA A100, 40GB VRAM) - Most powerful for training
        {
            "instance_type": "ml.p4d.24xlarge",
            "total_quota": 0,
            "in_use": 0,
            "available": 0,
            "hourly_rate_usd": Decimal("37.688"),
            "vram_gb": 320,  # 8x A100
            "gpu_count": 8,
            "gpu_type": "NVIDIA A100",
        },
        # P4de Family (NVIDIA A100, 80GB VRAM) - Ultra high memory
        {
            "instance_type": "ml.p4de.24xlarge",
            "total_quota": 0,
            "in_use": 0,
            "available": 0,
            "hourly_rate_usd": Decimal("48.178"),
            "vram_gb": 640,  # 8x A100 80GB
            "gpu_count": 8,
            "gpu_type": "NVIDIA A100 80GB",
        },
        # P5 Family (NVIDIA H100, 80GB VRAM) - Latest and most powerful
        {
            "instance_type": "ml.p5.48xlarge",
            "total_quota": 0,
            "in_use": 0,
            "available": 0,
            "hourly_rate_usd": Decimal("98.32"),
            "vram_gb": 640,  # 8x H100
            "gpu_count": 8,
            "gpu_type": "NVIDIA H100",
        },
    ]

    logger.info(f"Seeding {len(quotas)} instance types...")

    for quota in quotas:
        table.put_item(Item=quota)
        status = "✓ AVAILABLE" if quota["available"] > 0 else "✗ NO QUOTA"
        logger.info(
            f"  {status} {quota['instance_type']:25} "
            f"({quota['gpu_count']}x {quota['gpu_type']:20}) "
            f"- ${float(quota['hourly_rate_usd']):.2f}/hr, {quota['vram_gb']}GB VRAM"
        )

    logger.info(f"\n✓ Seeded {len(quotas)} instance types!")
    logger.info("\nInstances with quota:")
    for quota in quotas:
        if quota["available"] > 0:
            logger.info(f"  - {quota['instance_type']}: {quota['available']} available")


def main():
    """Run comprehensive quota seeding."""
    logger.info("Seeding comprehensive SageMaker instance quotas...")
    seed_comprehensive_quotas()
    logger.info("\n✓ Quota table is now comprehensive!")


if __name__ == "__main__":
    main()
