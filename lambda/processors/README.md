# Dataset Processor System

This directory contains the modular processor system for dataset-specific preprocessing.

## Architecture Overview

The processor system uses a **registry pattern** to support dataset-specific preprocessing logic:

```
processors/
├── __init__.py              # Processor registry
├── base_processor.py        # Base class (interface)
├── default_processor.py     # Generic fallback processor
├── cier_processor.py        # CIER dataset processor
└── README.md                # This file
```

## How It Works

1. **Registry Lookup**: When `prepare_dataset` is called, the registry checks if a custom processor exists for the dataset
2. **Processor Selection**:
   - If custom processor found → Use dataset-specific processor (e.g., `CIERProcessor`)
   - If not found → Use `DefaultProcessor` for generic validation
3. **Three-Phase Processing**:
   - **Preprocess**: Dataset-specific transformations (e.g., flatten nested NER)
   - **Validate**: Check data format and requirements
   - **Postprocess**: Final transformations before writing

## Creating a New Processor

### Step 1: Create Processor Class

Create a new file `processors/your_dataset_processor.py`:

```python
"""
YourDataset Processor

Description of your dataset's specific format requirements.
"""
from typing import Dict, Any, Tuple
from .default_processor import DefaultProcessor


class YourDatasetProcessor(DefaultProcessor):
    """
    Processor for YourDataset.

    Specific features:
    - Feature 1 description
    - Feature 2 description
    """

    def preprocess_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply dataset-specific transformations.

        Examples:
        - Convert field names (e.g., "tokens" -> "doc_tokens")
        - Normalize data types
        - Flatten nested structures
        """
        # Add your preprocessing logic here
        # Example: Convert field name
        if "tokens" in record:
            record["doc_tokens"] = record.pop("tokens")

        return record

    def validate_record(self, record: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Custom validation logic.

        Override this if your dataset has unique validation requirements
        beyond what DefaultProcessor provides.
        """
        # Use parent validation first
        is_valid, error_msg = super().validate_record(record)

        if not is_valid:
            return False, error_msg

        # Add custom validation here
        # Example: Check for dataset-specific field
        if "metadata" in record and not isinstance(record["metadata"], dict):
            return False, "metadata must be a dictionary"

        return True, ""

    def postprocess_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Final transformations after validation.

        Examples:
        - Remove temporary fields
        - Add computed fields
        - Format conversion
        """
        # Add postprocessing logic here
        return record

    def get_processor_info(self) -> Dict[str, Any]:
        """
        Metadata about this processor.
        """
        info = super().get_processor_info()
        info.update({
            "dataset": "YourDataset",
            "format_features": [
                "Feature 1",
                "Feature 2"
            ],
            "preprocessing": [
                "Step 1",
                "Step 2"
            ]
        })
        return info
```

### Step 2: Register the Processor

Edit `processors/__init__.py` and add your processor to the registry:

```python
from .your_dataset_processor import YourDatasetProcessor

# Add to registry
_PROCESSOR_REGISTRY: Dict[str, Type[BaseProcessor]] = {
    "cier": CIERProcessor,
    "yourdataset": YourDatasetProcessor,  # Add this line
}
```

### Step 3: Test the Processor

Deploy the updated Lambda and test:

```bash
# Package Lambda with new processor
zip -r prepare_dataset.zip prepare_dataset_handler.py processors/

# Deploy
aws lambda update-function-code \
  --function-name llmops-tool-prepare-dataset \
  --zip-file fileb://prepare_dataset.zip

# Test
aws lambda invoke \
  --function-name llmops-tool-prepare-dataset \
  --cli-binary-format raw-in-base64-out \
  --payload '{"dataset_name": "yourdataset", "force_prepare": true}' \
  output.json

# Check logs for processor selection
aws logs tail /aws/lambda/llmops-tool-prepare-dataset --since 2m | grep "processor"
```

## Example: CIER Processor

The CIER processor demonstrates a real-world use case:

**Problem**: CIER dataset uses nested sentence-level NER annotations:
```json
{
  "ner": [
    [[2, 2, "Method"], [8, 9, "Task"]],     // Sentence 1
    [[45, 45, "Method"], [55, 56, "Dataset"]]  // Sentence 2
  ]
}
```

**Solution**: Flatten to standard format in `preprocess_record()`:
```json
{
  "ner": [
    [2, 2, "Method"],
    [8, 9, "Task"],
    [45, 45, "Method"],
    [55, 56, "Dataset"]
  ]
}
```

**Code**:
```python
def preprocess_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
    if "ner" in record and self._is_nested(record["ner"]):
        record["ner"] = self._flatten_ner(record["ner"])
        print(f"   🔄 Flattened nested NER: {len(record['ner'])} entities")
    return record
```

## Processor Lifecycle

```
┌─────────────────┐
│   Raw Record    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  preprocess()   │  ← Dataset-specific transformations
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   validate()    │  ← Format validation
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  postprocess()  │  ← Final transformations
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Valid Record   │  → Written to S3
└─────────────────┘
```

## Best Practices

1. **Extend DefaultProcessor**: Reuse generic validation logic when possible
2. **Log transformations**: Use print statements to track preprocessing steps
3. **Preserve data**: Don't remove fields unless necessary (future processors may need them)
4. **Fail fast**: Return validation errors early with clear messages
5. **Document format**: Add comments explaining dataset-specific quirks
6. **Test edge cases**: Test with malformed data to ensure robust validation

## Common Patterns

### Pattern 1: Field Renaming
```python
def preprocess_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
    # Rename fields to standard names
    FIELD_MAP = {"text": "doc_text", "entities": "ner"}
    for old_name, new_name in FIELD_MAP.items():
        if old_name in record:
            record[new_name] = record.pop(old_name)
    return record
```

### Pattern 2: Type Normalization
```python
def preprocess_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
    # Convert string labels to integers
    if "label" in record and isinstance(record["label"], str):
        LABEL_MAP = {"positive": 0, "negative": 1, "neutral": 2}
        record["label"] = LABEL_MAP.get(record["label"], -1)
    return record
```

### Pattern 3: Custom Validation
```python
def validate_record(self, record: Dict[str, Any]) -> Tuple[bool, str]:
    # Validate parent requirements first
    is_valid, error_msg = super().validate_record(record)
    if not is_valid:
        return False, error_msg

    # Add dataset-specific checks
    if "confidence" in record:
        if not 0 <= record["confidence"] <= 1:
            return False, "confidence must be between 0 and 1"

    return True, ""
```

### Pattern 4: Computed Fields
```python
def postprocess_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
    # Add computed metadata
    record["num_tokens"] = len(record["doc_tokens"])
    record["num_entities"] = len(record["ner"])
    return record
```

## Troubleshooting

### Processor Not Found
**Symptom**: Logs show "Using default processor" instead of custom processor

**Solution**:
1. Check processor is registered in `__init__.py`
2. Verify dataset name matches registry key (case-insensitive)
3. Ensure processor class is imported in `__init__.py`

### Import Errors
**Symptom**: Lambda fails with "Unable to import module"

**Solution**:
1. Check all processor files are included in ZIP
2. Verify `processors/__init__.py` exists
3. Test locally: `python -c "from processors import get_processor"`

### Validation Failing
**Symptom**: All records marked as invalid

**Solution**:
1. Check CloudWatch logs for validation error messages
2. Download a sample record from S3 and test locally
3. Add debug print statements in `validate_record()`
4. Ensure preprocessing completes before validation

## Further Reading

- **Base Processor API**: See `base_processor.py` for method signatures
- **Default Validation**: See `default_processor.py` for standard validation rules
- **CIER Example**: See `cier_processor.py` for a complete implementation
