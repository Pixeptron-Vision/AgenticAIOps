"""
Dataset Processor Registry

This module provides a registry pattern for dataset-specific preprocessing.
Each dataset can have its own processor with custom validation and transformation logic.
"""
from typing import Dict, Type, Optional
from .base_processor import BaseProcessor
from .default_processor import DefaultProcessor
from .cier_processor import CIERProcessor
from .cier_hf_processor import CIERHFProcessor


# Registry mapping dataset names to processor classes
_PROCESSOR_REGISTRY: Dict[str, Type[BaseProcessor]] = {
    "cier": CIERHFProcessor,  # Use HuggingFace-compatible format for training
    # Add more dataset-specific processors here
    # "conll2003": CoNLL2003Processor,
    # "squad": SQuADProcessor,
}


def get_processor(dataset_name: str, task_type: str = "token-classification") -> BaseProcessor:
    """
    Get the appropriate processor for a dataset.

    Args:
        dataset_name: Name of the dataset
        task_type: ML task type (token-classification, text-classification, etc.)

    Returns:
        Processor instance for the dataset
    """
    # Check if dataset has a custom processor
    processor_class = _PROCESSOR_REGISTRY.get(dataset_name.lower())

    if processor_class:
        print(f"📦 Using custom processor: {processor_class.__name__}")
        return processor_class(task_type=task_type)
    else:
        print(f"📦 Using default processor for task: {task_type}")
        return DefaultProcessor(task_type=task_type)


def register_processor(dataset_name: str, processor_class: Type[BaseProcessor]):
    """
    Register a custom processor for a dataset.

    Args:
        dataset_name: Name of the dataset
        processor_class: Processor class to register
    """
    _PROCESSOR_REGISTRY[dataset_name.lower()] = processor_class
    print(f"✅ Registered processor: {dataset_name} -> {processor_class.__name__}")


def list_processors() -> Dict[str, str]:
    """
    List all registered processors.

    Returns:
        Dictionary mapping dataset names to processor class names
    """
    return {
        dataset: processor.__name__
        for dataset, processor in _PROCESSOR_REGISTRY.items()
    }
