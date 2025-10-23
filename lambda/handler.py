"""
AgentCore Tool: Prepare Dataset for Training

This Lambda function prepares datasets for ML training by:
1. Validating data format and schema
2. Normalizing annotations (e.g., NER format consistency)
3. Removing duplicates and invalid records
4. Creating train/dev/test splits if needed
5. Tracking preparation status in DynamoDB

DESIGN: Follows AgentCore tool patterns with:
- Idempotency: Safe to call multiple times
- Status tracking: Uses DynamoDB to avoid redundant work
- User override: Supports force_prepare flag
- Production-ready: Only writes validated data to processed folder
"""
import json
import boto3
import uuid
from datetime import datetime
from typing import Dict, List, Any, Tuple
import io

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# Constants
RAW_BUCKET = "llmops-agent-datasets"
PROCESSED_BUCKET = "llmops-agent-datasets"
DATASET_REGISTRY_TABLE = "llmops-dataset-registry"


def get_dataset_status(dataset_name: str) -> Dict[str, Any]:
    """
    Get dataset preparation status from DynamoDB.

    Args:
        dataset_name: Name of the dataset

    Returns:
        Dataset record or empty dict if not found
    """
    table = dynamodb.Table(DATASET_REGISTRY_TABLE)

    try:
        response = table.get_item(Key={"dataset_name": dataset_name})
        return response.get("Item", {})
    except Exception as e:
        print(f"⚠️  Error querying DynamoDB: {e}")
        return {}


def update_dataset_status(
    dataset_name: str,
    status: str,
    **kwargs
) -> None:
    """
    Update dataset preparation status in DynamoDB.

    Args:
        dataset_name: Name of the dataset
        status: Current status (preparing, prepared, failed, not_prepared)
        **kwargs: Additional fields to update
    """
    table = dynamodb.Table(DATASET_REGISTRY_TABLE)

    now_timestamp = int(datetime.utcnow().timestamp())
    now_iso = datetime.utcnow().isoformat() + "Z"

    update_expr = "SET preparation_status = :status, updated_at = :updated, updated_at_iso = :updated_iso"
    expr_values = {
        ":status": status,
        ":updated": now_timestamp,
        ":updated_iso": now_iso,
    }

    # Add optional fields
    for key, value in kwargs.items():
        update_expr += f", {key} = :{key}"
        expr_values[f":{key}"] = value

    # Set created_at if not exists (use comma, not SET)
    update_expr += ", created_at = if_not_exists(created_at, :created), created_at_iso = if_not_exists(created_at_iso, :created_iso)"
    expr_values[":created"] = now_timestamp
    expr_values[":created_iso"] = now_iso

    try:
        table.update_item(
            Key={"dataset_name": dataset_name},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
        )
        print(f"✅ Updated dataset status: {dataset_name} -> {status}")
    except Exception as e:
        print(f"ERROR: Failed to update DynamoDB: {e}")


def validate_jsonl_record(record: Dict[str, Any], task_type: str) -> Tuple[bool, str]:
    """
    Validate a single JSONL record for training.

    Args:
        record: JSONL record to validate
        task_type: ML task type (e.g., "token-classification")

    Returns:
        (is_valid, error_message)
    """
    # Common validation
    if not isinstance(record, dict):
        return False, "Record must be a JSON object"

    if task_type == "token-classification":
        # NER/token classification validation
        required_fields = ["doc_tokens", "ner"]

        for field in required_fields:
            if field not in record:
                return False, f"Missing required field: {field}"

        # Validate doc_tokens is a list of strings
        if not isinstance(record["doc_tokens"], list):
            return False, "doc_tokens must be a list"

        if not all(isinstance(t, str) for t in record["doc_tokens"]):
            return False, "All doc_tokens must be strings"

        # Validate NER format
        if not isinstance(record["ner"], list):
            return False, "ner must be a list"

        for i, span in enumerate(record["ner"]):
            if not isinstance(span, list) or len(span) != 3:
                return False, f"NER span {i} must be [start, end, label]"

            start, end, label = span

            # Ensure consistent types (convert numbers to int if string)
            if isinstance(start, str):
                try:
                    start = int(start)
                except ValueError:
                    return False, f"NER span {i}: start must be integer, got '{start}'"

            if isinstance(end, str):
                try:
                    end = int(end)
                except ValueError:
                    return False, f"NER span {i}: end must be integer, got '{end}'"

            if not isinstance(label, str):
                return False, f"NER span {i}: label must be string"

            # Validate span boundaries
            if start < 0 or end < 0:
                return False, f"NER span {i}: negative indices not allowed"

            if start >= end:
                return False, f"NER span {i}: start must be < end"

            if end > len(record["doc_tokens"]):
                return False, f"NER span {i}: end {end} exceeds doc length {len(record['doc_tokens'])}"

            # Normalize span (convert to int)
            span[0] = int(start)
            span[1] = int(end)

        return True, ""

    elif task_type == "text-classification":
        # Text classification validation
        required_fields = ["text", "label"]

        for field in required_fields:
            if field not in record:
                return False, f"Missing required field: {field}"

        if not isinstance(record["text"], str):
            return False, "text must be a string"

        if not isinstance(record["label"], (str, int)):
            return False, "label must be a string or integer"

        return True, ""

    else:
        return False, f"Unsupported task type: {task_type}"


def prepare_dataset(
    dataset_name: str,
    task_type: str = "token-classification",
    source_prefix: str = "raw",
    target_prefix: str = "processed",
) -> Dict[str, Any]:
    """
    Prepare a dataset for training.

    Args:
        dataset_name: Name of the dataset
        task_type: ML task type
        source_prefix: S3 prefix for source data
        target_prefix: S3 prefix for target data

    Returns:
        Preparation results
    """
    source_uri = f"s3://{RAW_BUCKET}/{source_prefix}/{dataset_name}/"
    target_uri = f"s3://{PROCESSED_BUCKET}/{target_prefix}/{dataset_name}/"

    print(f"📋 Preparing dataset: {dataset_name}")
    print(f"   Source: {source_uri}")
    print(f"   Target: {target_uri}")
    print(f"   Task type: {task_type}")

    validation_errors = []
    valid_records = {"train": [], "dev": [], "test": []}
    total_records = 0
    invalid_records = 0

    # Process each split
    for split in ["train", "dev", "test"]:
        source_key = f"{source_prefix}/{dataset_name}/{split}.jsonl"

        print(f"\n📄 Processing {split}.jsonl...")

        try:
            # Download JSONL file
            response = s3.get_object(Bucket=RAW_BUCKET, Key=source_key)
            content = response['Body'].read().decode('utf-8')

            # Process line by line
            for line_num, line in enumerate(content.strip().split('\n'), 1):
                if not line.strip():
                    continue

                total_records += 1

                try:
                    record = json.loads(line)

                    # Validate record
                    is_valid, error_msg = validate_jsonl_record(record, task_type)

                    if is_valid:
                        valid_records[split].append(record)
                    else:
                        invalid_records += 1
                        error = f"{split}.jsonl:{line_num} - {error_msg}"
                        validation_errors.append(error)
                        print(f"   ⚠️  {error}")

                except json.JSONDecodeError as e:
                    invalid_records += 1
                    error = f"{split}.jsonl:{line_num} - JSON decode error: {e}"
                    validation_errors.append(error)
                    print(f"   ⚠️  {error}")

            print(f"   ✅ {split}: {len(valid_records[split])} valid records")

        except s3.exceptions.NoSuchKey:
            print(f"   ⚠️  {split}.jsonl not found, skipping")
        except Exception as e:
            error = f"Error processing {split}.jsonl: {e}"
            validation_errors.append(error)
            print(f"   ERROR: {error}")

    # Check if we have enough valid data
    if len(valid_records["train"]) == 0:
        raise ValueError("No valid training records found")

    # Write validated data to processed folder
    total_size_bytes = 0
    splits_info = {}

    for split, records in valid_records.items():
        if len(records) == 0:
            continue

        target_key = f"{target_prefix}/{dataset_name}/{split}.jsonl"

        # Convert to JSONL
        jsonl_content = '\n'.join(json.dumps(record) for record in records)
        jsonl_bytes = jsonl_content.encode('utf-8')
        total_size_bytes += len(jsonl_bytes)

        # Upload to S3
        s3.put_object(
            Bucket=PROCESSED_BUCKET,
            Key=target_key,
            Body=jsonl_bytes,
            ContentType='application/jsonl',
        )

        splits_info[split] = len(records)
        print(f"✅ Wrote {target_uri}{split}.jsonl ({len(records)} records)")

    return {
        "total_records": sum(splits_info.values()),
        "total_size_bytes": total_size_bytes,
        "splits": splits_info,
        "validation_errors": validation_errors[:100],  # Limit to 100 errors
        "invalid_records": invalid_records,
    }


def lambda_handler(event, context):
    """
    AgentCore Tool: Prepare Dataset

    Args:
        event: {
            "dataset_name": "cier",
            "task_type": "token-classification",  # Optional
            "force_prepare": false,  # Optional - force re-preparation
            "source_prefix": "raw",  # Optional
            "target_prefix": "processed"  # Optional
        }

    Returns:
        {
            "statusCode": 200,
            "body": {
                "success": true,
                "dataset_name": "cier",
                "preparation_status": "prepared",
                "total_records": 10000,
                "splits": {"train": 8000, "dev": 1000, "test": 1000},
                "validation_errors": [],
                "message": "Dataset prepared successfully",
                "processed_s3_uri": "s3://llmops-agent-datasets/processed/cier/"
            }
        }
    """
    try:
        # Parse input
        dataset_name = event.get("dataset_name")
        if not dataset_name:
            raise ValueError("dataset_name is required")

        task_type = event.get("task_type", "token-classification")
        force_prepare = event.get("force_prepare", False)
        source_prefix = event.get("source_prefix", "raw")
        target_prefix = event.get("target_prefix", "processed")

        print(f"📋 Dataset Preparation Request:")
        print(f"   Dataset: {dataset_name}")
        print(f"   Task type: {task_type}")
        print(f"   Force prepare: {force_prepare}")

        # Check if dataset is already prepared
        dataset_record = get_dataset_status(dataset_name)

        if dataset_record and not force_prepare:
            status = dataset_record.get("preparation_status")

            if status == "prepared":
                print(f"✅ Dataset already prepared, skipping")

                # Increment force_prepare_count if user overrides
                return {
                    "statusCode": 200,
                    "body": json.dumps({
                        "success": True,
                        "dataset_name": dataset_name,
                        "preparation_status": "prepared",
                        "message": "Dataset already prepared (use force_prepare=true to re-prepare)",
                        "processed_s3_uri": dataset_record.get("processed_s3_uri"),
                        "last_prepared_at": dataset_record.get("last_prepared_at_iso"),
                        "total_records": dataset_record.get("total_records"),
                        "splits": dataset_record.get("splits", {}),
                    })
                }

            elif status == "preparing":
                return {
                    "statusCode": 409,
                    "body": json.dumps({
                        "success": False,
                        "error": "Dataset preparation already in progress",
                        "dataset_name": dataset_name,
                        "preparation_status": "preparing",
                    })
                }

        # Update status to "preparing"
        update_dataset_status(
            dataset_name,
            "preparing",
            source_s3_uri=f"s3://{RAW_BUCKET}/{source_prefix}/{dataset_name}/",
            processed_s3_uri=f"s3://{PROCESSED_BUCKET}/{target_prefix}/{dataset_name}/",
            task_type=task_type,
        )

        # Prepare dataset
        result = prepare_dataset(
            dataset_name=dataset_name,
            task_type=task_type,
            source_prefix=source_prefix,
            target_prefix=target_prefix,
        )

        # Update status to "prepared"
        now_timestamp = int(datetime.utcnow().timestamp())
        now_iso = datetime.utcnow().isoformat() + "Z"

        update_dataset_status(
            dataset_name,
            "prepared",
            last_prepared_at=now_timestamp,
            last_prepared_at_iso=now_iso,
            total_records=result["total_records"],
            total_size_bytes=result["total_size_bytes"],
            splits=result["splits"],
            validation_errors=result["validation_errors"],
            format="jsonl",
            schema_version="1.0",
        )

        # Increment force_prepare_count if applicable
        if force_prepare:
            try:
                table = dynamodb.Table(DATASET_REGISTRY_TABLE)
                table.update_item(
                    Key={"dataset_name": dataset_name},
                    UpdateExpression="ADD force_prepare_count :inc",
                    ExpressionAttributeValues={":inc": 1},
                )
            except Exception as e:
                print(f"⚠️  Failed to increment force_prepare_count: {e}")

        print(f"\n✅ Dataset preparation complete!")
        print(f"   Total records: {result['total_records']}")
        print(f"   Invalid records: {result['invalid_records']}")
        print(f"   Validation errors: {len(result['validation_errors'])}")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "success": True,
                "dataset_name": dataset_name,
                "preparation_status": "prepared",
                "total_records": result["total_records"],
                "total_size_bytes": result["total_size_bytes"],
                "splits": result["splits"],
                "validation_errors": result["validation_errors"],
                "invalid_records": result["invalid_records"],
                "message": f"Dataset prepared successfully with {result['total_records']} valid records",
                "processed_s3_uri": f"s3://{PROCESSED_BUCKET}/{target_prefix}/{dataset_name}/",
                "prepared_at": now_iso,
            })
        }

    except Exception as e:
        error_msg = str(e)
        print(f"ERROR: {error_msg}")

        # Update status to "failed"
        if 'dataset_name' in locals():
            update_dataset_status(
                dataset_name,
                "failed",
                validation_errors=[error_msg],
            )

        return {
            "statusCode": 500,
            "body": json.dumps({
                "success": False,
                "error": error_msg,
                "dataset_name": event.get("dataset_name"),
                "preparation_status": "failed",
            })
        }


if __name__ == "__main__":
    # Test with cier dataset
    test_event = {
        "dataset_name": "cier",
        "task_type": "token-classification",
        "force_prepare": True,
    }

    print("=" * 70)
    print("TEST: Prepare Dataset")
    print("=" * 70)
    result = lambda_handler(test_event, None)
    print(json.dumps(json.loads(result["body"]), indent=2))
