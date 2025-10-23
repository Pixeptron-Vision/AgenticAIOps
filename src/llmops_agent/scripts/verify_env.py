#!/usr/bin/env python3
"""
LLMOps Agent - Environment Configuration Verification Script

This script verifies that all required environment variables are set correctly
and tests basic AWS connectivity.

Usage:
    python verify_env.py
"""

import os
import sys
from pathlib import Path


def load_env():
    """Load environment variables from .env file."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ Successfully loaded .env file\n")
        return True
    except ImportError:
        print("❌ python-dotenv not installed. Install with: pip install python-dotenv")
        return False


def check_required_vars():
    """Check if all required environment variables are set."""
    required_vars = {
        'Core AWS': [
            'AWS_REGION',
            'AWS_ACCOUNT_ID',
            'AWS_ACCESS_KEY_ID',
            'AWS_SECRET_ACCESS_KEY',
        ],
        'S3 Buckets': [
            'S3_BUCKET_DATASETS',
            'S3_BUCKET_MODELS',
            'S3_BUCKET_ARTIFACTS',
        ],
        'DynamoDB Tables': [
            'DYNAMODB_TABLE_JOBS',
            'DYNAMODB_TABLE_SESSIONS',
            'DYNAMODB_TABLE_MODELS',
        ],
        'Bedrock Configuration': [
            'BEDROCK_MODEL_ID',
            'BEDROCK_MODEL_REGION',
        ],
        'SageMaker Configuration': [
            'SAGEMAKER_INSTANCE_TYPE',
            'SAGEMAKER_TRANSFORMERS_VERSION',
        ],
    }

    optional_vars = {
        'IAM Roles (update after creation)': [
            'SAGEMAKER_EXECUTION_ROLE_ARN',
            'LAMBDA_EXECUTION_ROLE_ARN',
            'BEDROCK_AGENT_ROLE_ARN',
        ],
        'Bedrock Agent (update after creation)': [
            'BEDROCK_AGENT_ID',
            'BEDROCK_AGENT_ALIAS_ID',
        ],
        'MLflow (update after deployment)': [
            'MLFLOW_TRACKING_URI',
        ],
    }

    all_ok = True
    missing_required = []

    # Check required variables
    for category, vars_list in required_vars.items():
        print(f"📋 {category}:")
        for var in vars_list:
            value = os.getenv(var)
            if value:
                # Mask sensitive values
                if 'KEY' in var or 'SECRET' in var:
                    display_value = value[:8] + '...' + value[-4:] if len(value) > 12 else '***'
                else:
                    display_value = value
                print(f"  ✅ {var}: {display_value}")
            else:
                print(f"  ❌ {var}: NOT SET")
                missing_required.append(var)
                all_ok = False
        print()

    # Check optional variables (warnings only)
    for category, vars_list in optional_vars.items():
        print(f"📋 {category}:")
        for var in vars_list:
            value = os.getenv(var)
            if value:
                print(f"  ✅ {var}: {value}")
            else:
                print(f"  ⚠️  {var}: Not set (update later)")
        print()

    return all_ok, missing_required


def test_aws_connection():
    """Test AWS connection using boto3."""
    print("🔌 Testing AWS Connection...")

    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
    except ImportError:
        print("❌ boto3 not installed. Install with: pip install boto3")
        return False

    try:
        # Test STS (Identity)
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()

        print(f"  ✅ AWS Credentials Valid")
        print(f"     Account: {identity['Account']}")
        print(f"     User ARN: {identity['Arn']}")
        print(f"     User ID: {identity['UserId']}")

        # Verify account ID matches
        env_account = os.getenv('AWS_ACCOUNT_ID')
        if env_account and env_account != identity['Account']:
            print(f"  ⚠️  Warning: Account ID mismatch!")
            print(f"     .env: {env_account}")
            print(f"     AWS: {identity['Account']}")

        print()
        return True

    except NoCredentialsError:
        print("  ❌ No AWS credentials found")
        print("     Check AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env")
        return False
    except ClientError as e:
        print(f"  ❌ AWS Error: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")
        return False


def check_s3_buckets():
    """Check if S3 buckets exist."""
    print("🪣 Checking S3 Buckets...")

    try:
        import boto3
        from botocore.exceptions import ClientError
    except ImportError:
        print("❌ boto3 not installed")
        return False

    s3 = boto3.client('s3')
    buckets = [
        os.getenv('S3_BUCKET_DATASETS'),
        os.getenv('S3_BUCKET_MODELS'),
        os.getenv('S3_BUCKET_ARTIFACTS'),
    ]

    all_exist = True
    for bucket in buckets:
        if not bucket:
            continue

        try:
            s3.head_bucket(Bucket=bucket)
            print(f"  ✅ {bucket} - exists")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                print(f"  ❌ {bucket} - does not exist")
                all_exist = False
            elif error_code == '403':
                print(f"  ⚠️  {bucket} - exists but access denied")
            else:
                print(f"  ❌ {bucket} - error: {error_code}")
                all_exist = False

    print()
    return all_exist


def check_dynamodb_tables():
    """Check if DynamoDB tables exist."""
    print("🗄️  Checking DynamoDB Tables...")

    try:
        import boto3
        from botocore.exceptions import ClientError
    except ImportError:
        print("❌ boto3 not installed")
        return False

    dynamodb = boto3.client('dynamodb')
    tables = [
        os.getenv('DYNAMODB_TABLE_JOBS'),
        os.getenv('DYNAMODB_TABLE_SESSIONS'),
        os.getenv('DYNAMODB_TABLE_MODELS'),
    ]

    all_exist = True
    for table in tables:
        if not table:
            continue

        try:
            response = dynamodb.describe_table(TableName=table)
            status = response['Table']['TableStatus']
            print(f"  ✅ {table} - {status}")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ResourceNotFoundException':
                print(f"  ❌ {table} - does not exist")
                all_exist = False
            else:
                print(f"  ❌ {table} - error: {error_code}")
                all_exist = False

    print()
    return all_exist


def check_bedrock_access():
    """Check Bedrock access and model availability."""
    print("🤖 Checking Bedrock Access...")

    try:
        import boto3
        from botocore.exceptions import ClientError
    except ImportError:
        print("❌ boto3 not installed")
        return False

    try:
        bedrock = boto3.client('bedrock', region_name=os.getenv('AWS_REGION'))

        # List foundation models
        response = bedrock.list_foundation_models()
        models = response.get('modelSummaries', [])

        # Check if Claude 3.5 Sonnet is available
        model_id = os.getenv('BEDROCK_MODEL_ID', 'anthropic.claude-3-5-sonnet-20241022-v2:0')
        claude_available = any(model_id in model.get('modelId', '') for model in models)

        if claude_available:
            print(f"  ✅ Bedrock access confirmed")
            print(f"  ✅ Claude 3.5 Sonnet available")
        else:
            print(f"  ⚠️  Bedrock access confirmed")
            print(f"  ⚠️  Claude 3.5 Sonnet not found - may need to request access")

        print()
        return True

    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'AccessDeniedException':
            print("  ❌ Bedrock access denied")
            print("     Enable Bedrock in AWS Console: https://console.aws.amazon.com/bedrock/")
        else:
            print(f"  ❌ Error: {error_code}")
        print()
        return False
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")
        print()
        return False


def main():
    """Main verification flow."""
    print("=" * 70)
    print("LLMOps Agent - Environment Configuration Verification")
    print("=" * 70)
    print()

    # Step 1: Load .env
    if not load_env():
        sys.exit(1)

    # Step 2: Check required variables
    vars_ok, missing = check_required_vars()
    if not vars_ok:
        print(f"\n❌ Missing required variables: {', '.join(missing)}")
        print("\nPlease check your .env file and ensure all required variables are set.")
        sys.exit(1)

    # Step 3: Test AWS connection
    if not test_aws_connection():
        print("\n❌ AWS connection test failed")
        print("\nCheck your AWS credentials in .env file.")
        sys.exit(1)

    # Step 4: Check S3 buckets (optional - may not exist yet)
    s3_ok = check_s3_buckets()
    if not s3_ok:
        print("⚠️  Some S3 buckets don't exist yet - create them following docs/setup/aws-setup.md")

    # Step 5: Check DynamoDB tables (optional - may not exist yet)
    dynamo_ok = check_dynamodb_tables()
    if not dynamo_ok:
        print("⚠️  Some DynamoDB tables don't exist yet - create them following docs/setup/aws-setup.md")

    # Step 6: Check Bedrock access (optional)
    bedrock_ok = check_bedrock_access()
    if not bedrock_ok:
        print("⚠️  Bedrock access not confirmed - enable it in AWS Console")

    # Summary
    print("=" * 70)
    print("Summary:")
    print("=" * 70)
    print(f"  Environment Variables:  {'✅ OK' if vars_ok else '❌ FAILED'}")
    print(f"  AWS Connection:         ✅ OK")
    print(f"  S3 Buckets:             {'✅ OK' if s3_ok else '⚠️  Not created yet'}")
    print(f"  DynamoDB Tables:        {'✅ OK' if dynamo_ok else '⚠️  Not created yet'}")
    print(f"  Bedrock Access:         {'✅ OK' if bedrock_ok else '⚠️  Not enabled yet'}")
    print()

    if vars_ok and s3_ok and dynamo_ok and bedrock_ok:
        print("✅ All checks passed! Your environment is ready for development.")
        sys.exit(0)
    else:
        print("⚠️  Some checks failed or resources not created yet.")
        print("   Review the output above and follow docs/setup/aws-setup.md for next steps.")
        sys.exit(0)


if __name__ == "__main__":
    main()
