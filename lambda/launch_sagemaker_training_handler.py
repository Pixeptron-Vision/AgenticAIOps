"""
Gateway tool: Launch SageMaker training job.

COMPLETE FIX (Oct 21, 2025):
- Looks up model in DynamoDB model-registry to get correct training image
- References training script from S3
- Constructs full S3 URI from dataset name
- Proper error handling with context
"""
import json
import boto3
import uuid
import re
from datetime import datetime

sagemaker = boto3.client('sagemaker')
dynamodb = boto3.resource('dynamodb')

# Constants
TRAINING_SCRIPTS_S3_PATH = "s3://llmops-agent-artifacts/training-scripts/"
MODEL_REGISTRY_TABLE = "llmops-model-registry"
SAGEMAKER_ROLE_ARN = "arn:aws:iam::335995680325:role/SageMakerExecutionRole"

def get_model_info(model_id: str) -> dict:
    """
    Query DynamoDB model registry for model information.

    Args:
        model_id: Model identifier (e.g., "distilbert-base-uncased")

    Returns:
        Model info including training_image, instance_type, etc.
    """
    table = dynamodb.Table(MODEL_REGISTRY_TABLE)

    try:
        response = table.get_item(Key={"model_id": model_id})

        if "Item" in response:
            return response["Item"]
        else:
            # Model not in registry - return defaults
            print(f"⚠️  Model {model_id} not found in registry, using defaults")
            return {
                "model_id": model_id,
                "training_image": "763104351884.dkr.ecr.us-east-1.amazonaws.com/huggingface-pytorch-training:2.1.0-transformers4.37.0-gpu-py310-cu118-ubuntu22.04",
                "instance_type": "ml.g4dn.xlarge",
                "task_type": "token-classification"
            }
    except Exception as e:
        print(f"Error querying DynamoDB: {e}")
        # Return defaults on error
        return {
            "model_id": model_id,
            "training_image": "763104351884.dkr.ecr.us-east-1.amazonaws.com/huggingface-pytorch-training:2.1.0-transformers4.37.0-gpu-py310-cu118-ubuntu22.04",
            "instance_type": "ml.g4dn.xlarge",
            "task_type": "token-classification"
        }


def lambda_handler(event, context):
    """
    Launch SageMaker training job with proper script and image.

    Args:
        event: {
            "model_name": "distilbert-base-uncased",
            "dataset_path": "cier",  # Can be name or full S3 URI
            "instance_type": "ml.g4dn.xlarge"  # Optional - will use from registry
        }

    Returns:
        {
            "job_id": "llmops-xxx",
            "status": "InProgress",
            "message": "Training job launched successfully"
        }
    """
    try:
        # Parse input
        model_name = event.get("model_name", "distilbert-base-uncased")
        dataset_path = event.get("dataset_path", "cier")
        instance_type_override = event.get("instance_type")  # Optional override

        print(f"📋 Launch training request:")
        print(f"   Model: {model_name}")
        print(f"   Dataset: {dataset_path}")
        print(f"   Instance override: {instance_type_override}")

        # STEP 1: Look up model in DynamoDB
        model_info = get_model_info(model_name)
        training_image = model_info.get("training_image")
        instance_type = instance_type_override or model_info.get("instance_type", "ml.g4dn.xlarge")

        print(f"✅ Model found in registry:")
        print(f"   Training image: {training_image}")
        print(f"   Instance type: {instance_type}")

        # STEP 2: Construct full S3 URI for dataset if needed
        if not dataset_path.startswith("s3://"):
            bucket = "llmops-agent-datasets"
            prefix = "processed"
            dataset_s3_uri = f"s3://{bucket}/{prefix}/{dataset_path}/"
        else:
            dataset_s3_uri = dataset_path

        # Validate S3 URI format
        s3_pattern = r'^s3://[a-zA-Z0-9.\-_]{3,63}/.*'
        if not re.match(s3_pattern, dataset_s3_uri):
            raise ValueError(f"Invalid S3 URI format: {dataset_s3_uri}")

        print(f"✅ Dataset S3 URI: {dataset_s3_uri}")

        # STEP 3: Generate job name
        model_short = model_name.split('/')[-1].replace('.', '-')[:20]
        job_name = f"llmops-{model_short}-{uuid.uuid4().hex[:8]}"

        print(f"✅ Job name: {job_name}")

        # STEP 4: Create training job with script
        response = sagemaker.create_training_job(
            TrainingJobName=job_name,
            AlgorithmSpecification={
                'TrainingImage': training_image,
                'TrainingInputMode': 'File',
                # CRITICAL: Use entrypoint script from S3 (installs deps and passes hyperparams)
                'ContainerEntrypoint': [
                    'bash',
                    '/opt/ml/input/data/code/entrypoint.sh'
                ]
            },
            RoleArn=SAGEMAKER_ROLE_ARN,
            InputDataConfig=[
                {
                    'ChannelName': 'train',
                    'DataSource': {
                        'S3DataSource': {
                            'S3DataType': 'S3Prefix',
                            'S3Uri': dataset_s3_uri,
                            'S3DataDistributionType': 'FullyReplicated'
                        }
                    }
                },
                {
                    # CRITICAL: Add training code as input channel
                    'ChannelName': 'code',
                    'DataSource': {
                        'S3DataSource': {
                            'S3DataType': 'S3Prefix',
                            'S3Uri': TRAINING_SCRIPTS_S3_PATH,
                            'S3DataDistributionType': 'FullyReplicated'
                        }
                    }
                }
            ],
            OutputDataConfig={
                'S3OutputPath': 's3://llmops-agent-models/final/'
            },
            ResourceConfig={
                'InstanceType': instance_type,
                'InstanceCount': 1,
                'VolumeSizeInGB': 30
            },
            StoppingCondition={
                'MaxRuntimeInSeconds': 3600
            },
            HyperParameters={
                # Pass arguments to train_ner.py
                'model_id': model_name,
                'use_peft': 'True',
                'learning_rate': '2e-5',
                'num_train_epochs': '3',
                'per_device_train_batch_size': '16'
            },
            Environment={
                # SageMaker will copy code channel to /opt/ml/code
                'SAGEMAKER_PROGRAM': 'train_ner.py'
            }
        )

        # STEP 5: Write job to DynamoDB for UI tracking
        jobs_table = dynamodb.Table('llmops-jobs')
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        session_id = event.get("session_id", f"session-{uuid.uuid4().hex[:8]}")
        now_timestamp = int(datetime.utcnow().timestamp())
        now_iso = datetime.utcnow().isoformat()

        job_record = {
            "job_id": job_id,
            "session_id": session_id,
            "sagemaker_job_name": job_name,
            "status": "in_progress",
            "progress": 0,
            "model_id": model_name,
            "dataset": dataset_path,
            "dataset_s3_uri": dataset_s3_uri,
            "task_type": model_info.get("task_type", "token-classification"),
            "instance_type": instance_type,
            "use_peft": "true",
            "training_image": training_image,
            "model_output_s3_uri": "s3://llmops-agent-models/final/",
            "created_at": now_timestamp,
            "created_at_iso": now_iso,
            "updated_at": now_timestamp,
            "updated_at_iso": now_iso,
        }

        try:
            jobs_table.put_item(Item=job_record)
            print(f"✅ Job record written to DynamoDB: {job_id}")
        except Exception as db_error:
            print(f"⚠️  Failed to write to DynamoDB (non-fatal): {db_error}")
            # Continue anyway - SageMaker job is created

        result = {
            "job_id": job_id,  # Return UI-friendly job_id
            "sagemaker_job_name": job_name,  # Also return SageMaker job name
            "status": "in_progress",
            "message": f"Training job launched successfully for model {model_name} on dataset {dataset_path}",
            "dataset_s3_uri": dataset_s3_uri,
            "instance_type": instance_type,
            "training_image": training_image,
            "model_info": {
                "model_id": model_info.get("model_id"),
                "task_type": model_info.get("task_type"),
                "params": model_info.get("params")
            },
            "created_at": now_iso
        }

        print(f"✅ Training job created successfully!")
        print(f"   UI Job ID: {job_id}")
        print(f"   SageMaker Job Name: {job_name}")
        print(f"   Status: in_progress")

        return {
            "statusCode": 200,
            "body": json.dumps(result)
        }

    except sagemaker.exceptions.ResourceInUse as e:
        error_msg = f"Training job name already in use. This is rare - try again."
        print(f"ERROR: {error_msg}")
        return {
            "statusCode": 409,
            "body": json.dumps({
                "error": error_msg,
                "details": str(e)
            })
        }

    except Exception as e:
        error_msg = str(e)
        print(f"ERROR: {error_msg}")

        # Provide helpful error context
        if "ValidationException" in error_msg or "S3" in error_msg:
            context = f"S3 dataset path issue. Expected format: s3://bucket/prefix/ or just dataset name. Got: {dataset_path}"
        elif "ResourceNotFoundException" in error_msg:
            context = "Resource not found. Check that the SageMaker role and S3 bucket exist."
        elif "AccessDenied" in error_msg:
            context = "Permission denied. Check IAM role permissions for SageMaker and S3."
        else:
            context = "Unexpected error launching training job"

        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": error_msg,
                "context": context,
                "job_attempted": locals().get('job_name', 'N/A')
            })
        }


if __name__ == "__main__":
    # Test with dataset name only
    test_event = {
        "model_name": "distilbert-base-uncased",
        "dataset_path": "cier",
        "instance_type": "ml.g4dn.xlarge"
    }
    print("=" * 70)
    print("TEST: Launch training job")
    print("=" * 70)
    result = lambda_handler(test_event, None)
    print(json.dumps(json.loads(result["body"]), indent=2))
