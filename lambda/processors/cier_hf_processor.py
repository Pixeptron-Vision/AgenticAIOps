"""
CIER Dataset Processor for HuggingFace Training

This processor converts CIER's span-based NER format to HuggingFace's
BIO-tagged token classification format.

Input Format (CIER):
{
  "doc_tokens": ["We", "propose", "CornerNet", ...],
  "ner": [[2, 3, "Method"], [8, 9, "Task"], ...]  # [start, end, label] spans
}

Output Format (HuggingFace):
{
  "tokens": ["We", "propose", "CornerNet", ...],
  "ner_tags": [0, 0, 1, 0, 0, 0, 0, 0, 2, ...]  # BIO tags as integers
}
"""
from typing import Dict, Any, Tuple, List
from .cier_processor import CIERProcessor


class CIERHFProcessor(CIERProcessor):
    """
    Processor for CIER dataset that outputs HuggingFace-compatible format.

    Converts span-based NER annotations to BIO-tagged format suitable for
    HuggingFace transformers token classification.
    """

    def __init__(self, task_type: str = "token-classification"):
        super().__init__(task_type)
        # Build label vocabulary from common entity types
        self.label_to_id = {"O": 0}  # Outside any entity
        self.entity_types = set()

    def _spans_to_bio(self, tokens: List[str], spans: List[List]) -> List[int]:
        """
        Convert span-based NER annotations to BIO tags.

        Args:
            tokens: List of token strings
            spans: List of [start, end, label] spans

        Returns:
            List of BIO tag IDs (one per token)
        """
        # Initialize all tokens as "O" (outside)
        bio_tags = [0] * len(tokens)  # 0 = "O"

        # Process each span
        for span in spans:
            start, end, label = span[0], span[1], span[2]

            # Add entity type to vocabulary if not seen
            if label not in self.entity_types:
                self.entity_types.add(label)
                # Add B- and I- tags for this entity type
                b_tag = f"B-{label}"
                i_tag = f"I-{label}"
                if b_tag not in self.label_to_id:
                    self.label_to_id[b_tag] = len(self.label_to_id)
                if i_tag not in self.label_to_id:
                    self.label_to_id[i_tag] = len(self.label_to_id)

            # Get tag IDs
            b_tag_id = self.label_to_id[f"B-{label}"]
            i_tag_id = self.label_to_id[f"I-{label}"]

            # Tag tokens in span
            for i in range(start, end):
                if i < len(tokens):
                    if i == start:
                        bio_tags[i] = b_tag_id  # Beginning of entity
                    else:
                        bio_tags[i] = i_tag_id  # Inside entity

        return bio_tags

    def postprocess_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert CIER format to HuggingFace format.

        Transforms:
        - doc_tokens → tokens
        - ner (spans) → ner_tags (BIO integers)
        - Removes CIER-specific fields
        """
        # Convert spans to BIO tags
        tokens = record.get("doc_tokens", [])
        spans = record.get("ner", [])

        bio_tags = self._spans_to_bio(tokens, spans)

        # Create HuggingFace-compatible record
        hf_record = {
            "tokens": tokens,
            "ner_tags": bio_tags,
        }

        # Preserve doc_id if present
        if "doc_id" in record:
            hf_record["id"] = record["doc_id"]

        return hf_record

    def get_label_map(self) -> Dict[int, str]:
        """
        Get the label ID to label name mapping.

        Returns:
            Dictionary mapping tag IDs to tag names
        """
        return {v: k for k, v in self.label_to_id.items()}

    def get_processor_info(self) -> Dict[str, Any]:
        """
        Get information about this processor.

        Returns:
            Dictionary with processor metadata
        """
        info = super().get_processor_info()
        info.update({
            "output_format": "HuggingFace BIO-tagged",
            "output_fields": ["tokens", "ner_tags"],
            "label_vocabulary_size": len(self.label_to_id),
            "label_map": self.get_label_map(),
            "preprocessing": [
                "Flatten nested NER annotations",
                "Normalize single-token spans",
                "Convert spans to BIO tags",
                "Remove CIER-specific fields"
            ]
        })
        return info
