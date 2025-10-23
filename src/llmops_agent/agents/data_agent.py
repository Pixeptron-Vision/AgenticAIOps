"""
Data Agent.

Responsible for dataset discovery, download, and preprocessing.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from llmops_agent.config import settings
from llmops_agent.services.s3_service import get_s3_service

logger = logging.getLogger(__name__)


class DataAgent:
    """Agent for data discovery and management."""

    def __init__(self):
        """Initialize the data agent."""
        self.agent_name = "Data"
        self.s3 = get_s3_service()

    async def search_datasets(
        self,
        task_type: str,
        keywords: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Search for datasets on Hugging Face.

        Args:
            task_type: Task type (e.g., "token-classification")
            keywords: Search keywords

        Returns:
            List of matching datasets
        """
        try:
            from huggingface_hub import HfApi, DatasetFilter

            api = HfApi()

            # Search datasets
            datasets = api.list_datasets(
                filter=DatasetFilter(task_categories=[task_type]),
                search=keywords,
                sort="downloads",
                limit=20,
            )

            results = []
            for ds in datasets:
                try:
                    info = api.dataset_info(ds.id)
                    results.append({
                        "id": ds.id,
                        "task": task_type,
                        "downloads": info.downloads or 0,
                        "likes": info.likes or 0,
                    })
                except:
                    # Skip datasets that can't be accessed
                    continue

            logger.info(f"Found {len(results)} datasets for {task_type}")

            return {
                "success": True,
                "datasets": results[:10],  # Top 10
            }

        except Exception as e:
            logger.error(f"Error searching datasets: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    async def download_and_preprocess(
        self,
        dataset_id: str,
        task_type: str,
        subset_size: Optional[int] = 2000,
    ) -> Dict[str, Any]:
        """
        Download dataset from Hugging Face, preprocess, and upload to S3.

        Args:
            dataset_id: Hugging Face dataset ID (e.g., "DFKI-SLT/ciER")
            task_type: Task type for preprocessing
            subset_size: Limit dataset size for POC

        Returns:
            S3 URI and dataset info
        """
        try:
            from datasets import load_dataset
            from transformers import AutoTokenizer

            logger.info(f"Downloading dataset: {dataset_id}")

            # Download dataset
            dataset = load_dataset(dataset_id)

            # Subset if requested
            if subset_size and "train" in dataset:
                dataset["train"] = dataset["train"].select(range(min(subset_size, len(dataset["train"]))))

            # Preprocess based on task type
            if task_type == "token-classification":
                dataset = await self._preprocess_ner(dataset)

            # Save to local temp directory
            local_path = f"/tmp/{dataset_id.replace('/', '_')}"
            dataset.save_to_disk(local_path)

            # Upload to S3
            dataset_name = dataset_id.split("/")[-1]
            s3_prefix = f"{settings.s3_prefix_processed_datasets}{dataset_name}"

            s3_uri = await self.s3.upload_directory(
                local_dir=local_path,
                bucket=settings.s3_bucket_datasets,
                s3_prefix=s3_prefix,
            )

            # Cleanup
            import shutil
            shutil.rmtree(local_path, ignore_errors=True)

            logger.info(f"Dataset uploaded to {s3_uri}")

            return {
                "success": True,
                "s3_uri": s3_uri,
                "num_samples": len(dataset["train"]) if "train" in dataset else 0,
                "splits": list(dataset.keys()),
            }

        except Exception as e:
            logger.error(f"Error downloading dataset: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    async def _preprocess_ner(self, dataset):
        """Preprocess dataset for NER task."""
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained("distilbert-base-cased")

        def tokenize_and_align_labels(examples):
            """Tokenize and align labels for NER."""
            tokenized_inputs = tokenizer(
                examples["tokens"],
                truncation=True,
                is_split_into_words=True,
                max_length=512,
            )

            labels = []
            for i, label in enumerate(examples["ner_tags"]):
                word_ids = tokenized_inputs.word_ids(batch_index=i)
                label_ids = []
                previous_word_idx = None

                for word_idx in word_ids:
                    if word_idx is None:
                        label_ids.append(-100)
                    elif word_idx != previous_word_idx:
                        label_ids.append(label[word_idx])
                    else:
                        label_ids.append(-100)

                    previous_word_idx = word_idx

                labels.append(label_ids)

            tokenized_inputs["labels"] = labels
            return tokenized_inputs

        # Apply preprocessing
        tokenized_dataset = dataset.map(
            tokenize_and_align_labels,
            batched=True,
            remove_columns=dataset["train"].column_names,
        )

        return tokenized_dataset

    async def prepare_dataset(
        self,
        dataset_name: str,
        task_type: str = "token-classification",
        force_prepare: bool = False,
        source_prefix: str = "raw",
        target_prefix: str = "processed",
    ) -> Dict[str, Any]:
        """
        Prepare dataset for training by invoking the Lambda function.

        This method delegates to the prepare_dataset Lambda function which:
        - Validates data format and schema
        - Normalizes annotations (e.g., NER format consistency)
        - Removes duplicates and invalid records
        - Tracks preparation status in DynamoDB

        Args:
            dataset_name: Name of the dataset to prepare
            task_type: ML task type (e.g., "token-classification")
            force_prepare: Force re-preparation even if already prepared
            source_prefix: S3 prefix for source data
            target_prefix: S3 prefix for prepared data

        Returns:
            Preparation results from Lambda
        """
        try:
            import boto3
            import json

            logger.info(f"Preparing dataset: {dataset_name}")

            # Invoke Lambda function
            lambda_client = boto3.client('lambda', region_name=settings.aws_region)

            payload = {
                "dataset_name": dataset_name,
                "task_type": task_type,
                "force_prepare": force_prepare,
                "source_prefix": source_prefix,
                "target_prefix": target_prefix,
            }

            response = lambda_client.invoke(
                FunctionName="llmops-tool-prepare-dataset",
                InvocationType='RequestResponse',
                Payload=json.dumps(payload),
            )

            # Parse response
            result_payload = json.loads(response['Payload'].read())
            status_code = result_payload.get("statusCode", 500)

            if status_code == 200:
                body = json.loads(result_payload.get("body", "{}"))
                return body
            else:
                body = json.loads(result_payload.get("body", "{}"))
                return {
                    "success": False,
                    "error": body.get("error", "Dataset preparation failed"),
                    "preparation_status": body.get("preparation_status", "failed"),
                }

        except Exception as e:
            logger.error(f"Error preparing dataset: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "preparation_status": "failed",
            }
