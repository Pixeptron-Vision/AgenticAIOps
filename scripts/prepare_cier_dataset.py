#!/usr/bin/env python3
"""
Download and prepare the ciER dataset for SageMaker training.

This script:
1. Downloads the ciER dataset from Hugging Face
2. Preprocesses it for NER training
3. Saves it in the format expected by SageMaker
4. Uploads to S3
"""

import json
import os
import sys
from pathlib import Path

import boto3
from datasets import load_dataset

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from llmops_agent.config import settings


def download_cier_dataset():
    """Download ciER dataset from Hugging Face."""
    print("=" * 70)
    print("Downloading ciER Dataset from Hugging Face")
    print("=" * 70)
    print()

    try:
        print("Loading dataset: DFKI-SLT/ciER...")
        dataset = load_dataset("DFKI-SLT/ciER")

        print(f"✅ Dataset loaded successfully!")
        print(f"   Splits: {list(dataset.keys())}")

        if 'train' in dataset:
            print(f"   Train examples: {len(dataset['train'])}")
        if 'test' in dataset:
            print(f"   Test examples: {len(dataset['test'])}")
        if 'validation' in dataset:
            print(f"   Validation examples: {len(dataset['validation'])}")

        return dataset

    except Exception as e:
        print(f"❌ Error loading dataset: {e}")
        print("\nTrying alternative dataset name...")
        try:
            dataset = load_dataset("dfki-slt/cier")
            print(f"✅ Dataset loaded successfully!")
            return dataset
        except Exception as e2:
            print(f"❌ Error: {e2}")
            raise


def save_dataset_locally(dataset, output_dir="data/cier"):
    """Save dataset to local directory."""
    print()
    print("=" * 70)
    print("Saving Dataset Locally")
    print("=" * 70)
    print()

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Save train split
    if 'train' in dataset:
        train_file = output_path / "train.jsonl"
        print(f"Saving train split to {train_file}...")

        with open(train_file, 'w') as f:
            for example in dataset['train']:
                f.write(json.dumps(example) + '\n')

        print(f"✅ Saved {len(dataset['train'])} training examples")

    # Save test split
    if 'test' in dataset:
        test_file = output_path / "test.jsonl"
        print(f"Saving test split to {test_file}...")

        with open(test_file, 'w') as f:
            for example in dataset['test']:
                f.write(json.dumps(example) + '\n')

        print(f"✅ Saved {len(dataset['test'])} test examples")

    # Save validation split (if exists)
    if 'validation' in dataset:
        val_file = output_path / "validation.jsonl"
        print(f"Saving validation split to {val_file}...")

        with open(val_file, 'w') as f:
            for example in dataset['validation']:
                f.write(json.dumps(example) + '\n')

        print(f"✅ Saved {len(dataset['validation'])} validation examples")

    print(f"\n✅ Dataset saved to: {output_path.absolute()}")
    return output_path


def upload_to_s3(local_dir, s3_bucket, s3_prefix="processed/cier/"):
    """Upload dataset to S3."""
    print()
    print("=" * 70)
    print("Uploading Dataset to S3")
    print("=" * 70)
    print()

    s3_client = boto3.client('s3', region_name=settings.aws_region)

    local_path = Path(local_dir)
    files_uploaded = 0

    for file_path in local_path.glob("*.jsonl"):
        s3_key = f"{s3_prefix}{file_path.name}"

        print(f"Uploading {file_path.name} to s3://{s3_bucket}/{s3_key}...")

        try:
            s3_client.upload_file(
                str(file_path),
                s3_bucket,
                s3_key
            )
            files_uploaded += 1
            print(f"✅ Uploaded: s3://{s3_bucket}/{s3_key}")

        except Exception as e:
            print(f"❌ Error uploading {file_path.name}: {e}")
            raise

    print(f"\n✅ Uploaded {files_uploaded} files to S3")
    print(f"   S3 location: s3://{s3_bucket}/{s3_prefix}")

    return f"s3://{s3_bucket}/{s3_prefix}"


def verify_s3_upload(s3_bucket, s3_prefix="processed/cier/"):
    """Verify files were uploaded correctly."""
    print()
    print("=" * 70)
    print("Verifying S3 Upload")
    print("=" * 70)
    print()

    s3_client = boto3.client('s3', region_name=settings.aws_region)

    try:
        response = s3_client.list_objects_v2(
            Bucket=s3_bucket,
            Prefix=s3_prefix
        )

        if 'Contents' not in response:
            print(f"❌ No files found at s3://{s3_bucket}/{s3_prefix}")
            return False

        print(f"Files in S3:")
        for obj in response['Contents']:
            size_kb = obj['Size'] / 1024
            print(f"  - {obj['Key']} ({size_kb:.2f} KB)")

        print(f"\n✅ Verification successful! {len(response['Contents'])} files found")
        return True

    except Exception as e:
        print(f"❌ Error verifying S3: {e}")
        return False


def main():
    """Main execution."""
    print("\n" + "=" * 70)
    print("ciER Dataset Preparation for SageMaker")
    print("=" * 70)
    print()
    print(f"S3 Bucket: {settings.s3_bucket_datasets}")
    print(f"S3 Prefix: processed/cier/")
    print(f"AWS Region: {settings.aws_region}")
    print()

    # Step 1: Download dataset
    dataset = download_cier_dataset()

    # Step 2: Save locally
    local_dir = save_dataset_locally(dataset)

    # Step 3: Upload to S3
    s3_uri = upload_to_s3(
        local_dir,
        settings.s3_bucket_datasets,
        s3_prefix="processed/cier/"
    )

    # Step 4: Verify
    success = verify_s3_upload(
        settings.s3_bucket_datasets,
        s3_prefix="processed/cier/"
    )

    if success:
        print()
        print("=" * 70)
        print("✅ Dataset Preparation Complete!")
        print("=" * 70)
        print()
        print("Dataset is ready for SageMaker training at:")
        print(f"  {s3_uri}")
        print()
        print("You can now test the agent with:")
        print("  poetry run python scripts/test_bedrock_agent.py")
        print()
    else:
        print()
        print("❌ Dataset preparation failed. Please check errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
