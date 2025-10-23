"""
CIER Dataset Processor

This processor handles the specific format requirements of the CIER dataset.

CIER Format Specifics:
- Nested NER annotations organized by sentence
- Format: [[[2, 2, "Method"], [8, 9, "Task"]], [[45, 45, "Method"]]]
- Needs flattening before standard validation
- Contains "sentences" field with sentence boundaries
- Contains "relations" field for entity relationships
"""
from typing import Dict, Any, Tuple
from .default_processor import DefaultProcessor


class CIERProcessor(DefaultProcessor):
    """
    Processor for CIER (Computer Science Information Extraction Resource) dataset.

    Extends DefaultProcessor with CIER-specific preprocessing:
    - Detects and flattens nested sentence-level NER annotations
    - Preserves additional CIER-specific fields (sentences, relations)
    - Handles single-token entity spans
    """

    def preprocess_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Preprocess CIER record by flattening nested NER annotations.

        Args:
            record: CIER JSONL record

        Returns:
            Preprocessed record with flattened NER annotations
        """
        # Check if NER annotations need flattening
        if "ner" in record and isinstance(record["ner"], list):
            # Detect format: nested (sentence-level) vs flat
            # Nested: [[[2, 2, "Method"], [8, 9, "Task"]], [[45, 45, "Method"]]]
            # Flat: [[0, 3, "METHOD"], [5, 8, "METRIC"]]
            is_nested = False
            if len(record["ner"]) > 0 and isinstance(record["ner"][0], list):
                # Check if first element is a list of spans (nested) or a single span (flat)
                if len(record["ner"][0]) > 0 and isinstance(record["ner"][0][0], list):
                    is_nested = True

            # Flatten nested format if needed
            if is_nested:
                flattened_ner = []
                for sentence_spans in record["ner"]:
                    if isinstance(sentence_spans, list):
                        for span in sentence_spans:
                            if isinstance(span, list):
                                flattened_ner.append(span)
                record["ner"] = flattened_ner
                print(f"   🔄 Flattened nested NER: {len(flattened_ner)} entities")

        return record

    def get_required_fields(self):
        """
        Get required fields for CIER dataset.

        Returns:
            List of required field names
        """
        # CIER requires doc_tokens and ner, but also has optional fields
        return ["doc_tokens", "ner"]

    def get_processor_info(self) -> Dict[str, Any]:
        """
        Get information about this processor.

        Returns:
            Dictionary with processor metadata
        """
        info = super().get_processor_info()
        info.update({
            "dataset": "CIER",
            "format_features": [
                "Nested sentence-level NER annotations",
                "Single-token entity spans",
                "Sentence boundaries",
                "Entity relations"
            ],
            "preprocessing": [
                "Flatten nested NER annotations",
                "Normalize single-token spans"
            ]
        })
        return info
