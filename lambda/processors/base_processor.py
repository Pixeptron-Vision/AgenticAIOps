"""
Base Processor for Dataset Preparation

This module defines the base class that all dataset processors must inherit from.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Tuple


class BaseProcessor(ABC):
    """
    Base class for dataset processors.

    Each processor handles validation and preprocessing for a specific dataset or task type.
    Subclasses can override methods to implement dataset-specific logic.
    """

    def __init__(self, task_type: str = "token-classification"):
        """
        Initialize the processor.

        Args:
            task_type: ML task type (token-classification, text-classification, etc.)
        """
        self.task_type = task_type

    @abstractmethod
    def validate_record(self, record: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate a single JSONL record.

        Args:
            record: JSONL record to validate

        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if record is valid
            - error_message: Error description if invalid, empty string if valid
        """
        pass

    def preprocess_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Preprocess a record before validation.

        This method can be overridden to implement dataset-specific transformations
        like format conversion, field renaming, etc.

        Args:
            record: JSONL record to preprocess

        Returns:
            Preprocessed record
        """
        # Default: no preprocessing
        return record

    def postprocess_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Postprocess a valid record before writing.

        This method can be overridden to implement final transformations
        after validation passes.

        Args:
            record: Validated JSONL record

        Returns:
            Postprocessed record
        """
        # Default: no postprocessing
        return record

    def get_required_fields(self) -> List[str]:
        """
        Get list of required fields for this dataset/task.

        Returns:
            List of required field names
        """
        # Default implementation based on task type
        if self.task_type == "token-classification":
            return ["doc_tokens", "ner"]
        elif self.task_type == "text-classification":
            return ["text", "label"]
        else:
            return []

    def get_processor_info(self) -> Dict[str, Any]:
        """
        Get information about this processor.

        Returns:
            Dictionary with processor metadata
        """
        return {
            "processor_class": self.__class__.__name__,
            "task_type": self.task_type,
            "required_fields": self.get_required_fields(),
        }
