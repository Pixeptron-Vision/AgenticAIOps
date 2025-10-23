"""
AWS Lambda function for listing S3 datasets
Registered as Gateway tool: list_s3_datasets
"""
import boto3
import json
import os
from typing import Dict, Any


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    List available datasets from S3 bucket

    This tool is registered with AgentCore Gateway and can be invoked
    by the agent to discover available datasets.

    Returns:
        dict: Response containing list of datasets and bucket info
    """
    try:
        # Get bucket name from environment or use default
        bucket_name = os.environ.get('S3_BUCKET_DATASETS', 'llmops-agent-datasets')
        region = os.environ.get('AWS_REGION', 'us-east-1')

        # Initialize S3 client
        s3_client = boto3.client('s3', region_name=region)

        # List objects with 'processed/' prefix
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix='processed/',
            Delimiter='/'
        )

        # Extract dataset names from common prefixes
        datasets = []
        if 'CommonPrefixes' in response:
            for prefix_info in response['CommonPrefixes']:
                # Extract dataset name from path (e.g., 'processed/ciER/' -> 'ciER')
                dataset_name = prefix_info['Prefix'].rstrip('/').split('/')[-1]
                if dataset_name:
                    datasets.append(dataset_name)

        # Sort datasets alphabetically
        datasets.sort()

        return {
            'statusCode': 200,
            'body': json.dumps({
                'datasets': datasets,
                'bucket': bucket_name,
                'total_count': len(datasets),
                'prefix': 'processed/'
            })
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Failed to list S3 datasets'
            })
        }
