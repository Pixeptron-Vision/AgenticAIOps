"""
Amazon S3 service client.

Provides high-level interface for S3 operations (upload, download, list).
"""

import logging
from pathlib import Path
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError

from llmops_agent.config import settings

logger = logging.getLogger(__name__)


class S3Service:
    """Service for interacting with Amazon S3."""

    def __init__(self):
        """Initialize S3 client."""
        self.s3 = boto3.client("s3", region_name=settings.aws_region)
        self.s3_resource = boto3.resource("s3", region_name=settings.aws_region)

    async def upload_file(
        self,
        local_path: str,
        bucket: str,
        s3_key: str,
    ) -> str:
        """
        Upload a file to S3.

        Args:
            local_path: Local file path
            bucket: S3 bucket name
            s3_key: S3 object key

        Returns:
            S3 URI (s3://bucket/key)
        """
        try:
            logger.info(f"Uploading {local_path} to s3://{bucket}/{s3_key}")

            self.s3.upload_file(local_path, bucket, s3_key)

            s3_uri = f"s3://{bucket}/{s3_key}"
            logger.info(f"Upload complete: {s3_uri}")

            return s3_uri

        except ClientError as e:
            logger.error(f"Error uploading to S3: {e}")
            raise

    async def upload_directory(
        self,
        local_dir: str,
        bucket: str,
        s3_prefix: str,
    ) -> str:
        """
        Upload entire directory to S3.

        Args:
            local_dir: Local directory path
            bucket: S3 bucket name
            s3_prefix: S3 prefix (folder)

        Returns:
            S3 URI (s3://bucket/prefix/)
        """
        try:
            local_path = Path(local_dir)

            if not local_path.exists():
                raise FileNotFoundError(f"Directory not found: {local_dir}")

            logger.info(f"Uploading directory {local_dir} to s3://{bucket}/{s3_prefix}")

            file_count = 0
            for file_path in local_path.rglob("*"):
                if file_path.is_file():
                    # Calculate relative path
                    relative_path = file_path.relative_to(local_path)
                    s3_key = f"{s3_prefix}/{relative_path}".replace("\\", "/")

                    # Upload file
                    self.s3.upload_file(str(file_path), bucket, s3_key)
                    file_count += 1

            s3_uri = f"s3://{bucket}/{s3_prefix}/"
            logger.info(f"Uploaded {file_count} files to {s3_uri}")

            return s3_uri

        except ClientError as e:
            logger.error(f"Error uploading directory to S3: {e}")
            raise

    async def download_file(
        self,
        bucket: str,
        s3_key: str,
        local_path: str,
    ) -> str:
        """
        Download a file from S3.

        Args:
            bucket: S3 bucket name
            s3_key: S3 object key
            local_path: Local file path

        Returns:
            Local file path
        """
        try:
            logger.info(f"Downloading s3://{bucket}/{s3_key} to {local_path}")

            # Create parent directory if needed
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)

            self.s3.download_file(bucket, s3_key, local_path)

            logger.info(f"Download complete: {local_path}")

            return local_path

        except ClientError as e:
            logger.error(f"Error downloading from S3: {e}")
            raise

    async def list_objects(
        self,
        bucket: str,
        prefix: str = "",
        max_keys: int = 1000,
    ) -> List[str]:
        """
        List objects in an S3 bucket.

        Args:
            bucket: S3 bucket name
            prefix: S3 prefix to filter by
            max_keys: Maximum number of keys to return

        Returns:
            List of S3 keys
        """
        try:
            logger.debug(f"Listing objects in s3://{bucket}/{prefix}")

            response = self.s3.list_objects_v2(
                Bucket=bucket,
                Prefix=prefix,
                MaxKeys=max_keys,
            )

            objects = response.get("Contents", [])
            keys = [obj["Key"] for obj in objects]

            logger.debug(f"Found {len(keys)} objects")

            return keys

        except ClientError as e:
            logger.error(f"Error listing S3 objects: {e}")
            raise

    async def delete_object(self, bucket: str, s3_key: str) -> None:
        """
        Delete an object from S3.

        Args:
            bucket: S3 bucket name
            s3_key: S3 object key
        """
        try:
            logger.info(f"Deleting s3://{bucket}/{s3_key}")

            self.s3.delete_object(Bucket=bucket, Key=s3_key)

            logger.info("Delete complete")

        except ClientError as e:
            logger.error(f"Error deleting S3 object: {e}")
            raise

    async def get_presigned_url(
        self,
        bucket: str,
        s3_key: str,
        expiration: int = 3600,
    ) -> str:
        """
        Generate a presigned URL for downloading an object.

        Args:
            bucket: S3 bucket name
            s3_key: S3 object key
            expiration: URL expiration time in seconds

        Returns:
            Presigned URL
        """
        try:
            url = self.s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": s3_key},
                ExpiresIn=expiration,
            )

            return url

        except ClientError as e:
            logger.error(f"Error generating presigned URL: {e}")
            raise


# Singleton instance
_s3_service: Optional[S3Service] = None


def get_s3_service() -> S3Service:
    """Get or create S3 service instance."""
    global _s3_service

    if _s3_service is None:
        _s3_service = S3Service()

    return _s3_service
