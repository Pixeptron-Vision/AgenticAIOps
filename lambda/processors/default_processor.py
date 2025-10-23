"""
Default Processor for Generic Datasets

This processor provides generic validation logic for common ML tasks.
Used as fallback when no dataset-specific processor is registered.
"""
from typing import Dict, Any, Tuple
from .base_processor import BaseProcessor


class DefaultProcessor(BaseProcessor):
    """
    Default processor for generic token classification and text classification tasks.

    Supports:
    - Token classification: Validates doc_tokens and NER annotations
    - Text classification: Validates text and label fields
    """

    def validate_record(self, record: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate a single JSONL record.

        Args:
            record: JSONL record to validate

        Returns:
            (is_valid, error_message)
        """
        # Common validation
        if not isinstance(record, dict):
            return False, "Record must be a JSON object"

        if self.task_type == "token-classification":
            return self._validate_token_classification(record)
        elif self.task_type == "text-classification":
            return self._validate_text_classification(record)
        else:
            return False, f"Unsupported task type: {self.task_type}"

    def _validate_token_classification(self, record: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate token classification (NER) record."""
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

        # Validate each span
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

            if start > end:
                return False, f"NER span {i}: start must be <= end, got start={start} end={end}"

            # For single-token spans [start, start], normalize to [start, start+1]
            if start == end:
                end = start + 1
                span[1] = end

            if end > len(record["doc_tokens"]):
                return False, f"NER span {i}: end {end} exceeds doc length {len(record['doc_tokens'])}"

            # Normalize span (convert to int)
            span[0] = int(start)
            span[1] = int(end)

        return True, ""

    def _validate_text_classification(self, record: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate text classification record."""
        required_fields = ["text", "label"]

        for field in required_fields:
            if field not in record:
                return False, f"Missing required field: {field}"

        if not isinstance(record["text"], str):
            return False, "text must be a string"

        if not isinstance(record["label"], (str, int)):
            return False, "label must be a string or integer"

        return True, ""
