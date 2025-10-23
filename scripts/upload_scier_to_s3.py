#!/usr/bin/env python3
"""
Upload SciER dataset to S3 for SageMaker training.
"""

import sys
from pathlib import Path

import boto3

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from llmops_agent.config import settings


def upload_to_s3():
    """Upload SciER dataset to S3."""
    print("=" * 70)
    print("Uploading SciER Dataset to S3")
    print("=" * 70)
    print()

    s3_client = boto3.client('s3', region_name=settings.aws_region)

    # Source directory
    source_dir = Path("data/scier-raw/SciER/PLM")

    # S3 configuration
    s3_bucket = settings.s3_bucket_datasets
    s3_prefix = "processed/cier/"  # Keep same name for Lambda compatibility

    print(f"Source: {source_dir.absolute()}")
    print(f"Bucket: {s3_bucket}")
    print(f"Prefix: {s3_prefix}")
    print()

    # Files to upload
    files = ["train.jsonl", "dev.jsonl", "test.jsonl"]
    uploaded = 0

    for filename in files:
        file_path = source_dir / filename

        if not file_path.exists():
            print(f"⚠️  {filename} not found, skipping...")
            continue

        s3_key = f"{s3_prefix}{filename}"
        file_size_mb = file_path.stat().st_size / (1024 * 1024)

        print(f"Uploading {filename} ({file_size_mb:.2f} MB)...")

        try:
            s3_client.upload_file(
                str(file_path),
                s3_bucket,
                s3_key
            )
            uploaded += 1
            print(f"✅ s3://{s3_bucket}/{s3_key}")

        except Exception as e:
            print(f"❌ Error: {e}")
            return False

    print()
    print("=" * 70)
    print("Verifying Upload")
    print("=" * 70)
    print()

    try:
        response = s3_client.list_objects_v2(
            Bucket=s3_bucket,
            Prefix=s3_prefix
        )

        if 'Contents' in response:
            print("Files in S3:")
            for obj in response['Contents']:
                size_mb = obj['Size'] / (1024 * 1024)
                print(f"  ✅ {obj['Key']} ({size_mb:.2f} MB)")
            print()
        else:
            print("❌ No files found in S3")
            return False

    except Exception as e:
        print(f"❌ Verification error: {e}")
        return False

    print("=" * 70)
    print(f"✅ Upload Complete! ({uploaded} files)")
    print("=" * 70)
    print()
    print(f"Dataset location: s3://{s3_bucket}/{s3_prefix}")
    print()
    print("You can now test the full agent workflow:")
    print("  poetry run python scripts/test_bedrock_agent.py")
    print()

    return True


if __name__ == "__main__":
    success = upload_to_s3()
    sys.exit(0 if success else 1)
