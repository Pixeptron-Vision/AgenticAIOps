"""
SageMaker training script for NER fine-tuning.

This script is executed inside the SageMaker training container.
"""

import argparse
import logging
import os
from pathlib import Path

import mlflow
import torch
from datasets import load_from_disk
from peft import LoraConfig, TaskType, get_peft_model
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    DataCollatorForTokenClassification,
    Trainer,
    TrainingArguments,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser()

    # Model arguments
    parser.add_argument("--model_id", type=str, required=True)
    parser.add_argument("--use_peft", type=lambda x: x.lower() == 'true', default=True)

    # Training arguments
    parser.add_argument("--learning_rate", type=float, default=2e-5)
    parser.add_argument("--num_train_epochs", type=int, default=3)
    parser.add_argument("--per_device_train_batch_size", type=int, default=16)
    parser.add_argument("--warmup_steps", type=int, default=500)

    # LoRA arguments
    parser.add_argument("--lora_r", type=int, default=8)
    parser.add_argument("--lora_alpha", type=int, default=16)
    parser.add_argument("--lora_dropout", type=float, default=0.1)

    # SageMaker arguments
    parser.add_argument("--output_data_dir", type=str, default=os.environ.get("SM_OUTPUT_DATA_DIR"))
    parser.add_argument("--model_dir", type=str, default=os.environ.get("SM_MODEL_DIR"))
    parser.add_argument("--train", type=str, default=os.environ.get("SM_CHANNEL_TRAIN"))

    return parser.parse_args()


def main():
    """Main training function."""
    args = parse_args()

    logger.info("=" * 70)
    logger.info("LLMOps Agent - NER Training")
    logger.info("=" * 70)
    logger.info(f"Model: {args.model_id}")
    logger.info(f"Use PEFT: {args.use_peft}")
    logger.info(f"Learning Rate: {args.learning_rate}")
    logger.info(f"Epochs: {args.num_train_epochs}")
    logger.info("=" * 70)

    # Initialize MLflow
    mlflow_uri = os.environ.get("MLFLOW_TRACKING_URI")
    if mlflow_uri:
        mlflow.set_tracking_uri(mlflow_uri)
        mlflow.set_experiment(os.environ.get("MLFLOW_EXPERIMENT_NAME", "ner-training"))
        mlflow.start_run()

    # Load dataset
    logger.info(f"Loading dataset from {args.train}")
    train_path = Path(args.train)
    logger.info(f"Train path exists: {train_path.exists()}")
    logger.info(f"Train path is dir: {train_path.is_dir()}")

    # List contents of train path for debugging
    if train_path.exists():
        logger.info(f"Contents of {train_path}:")
        for item in train_path.iterdir():
            logger.info(f"  - {item.name} ({item.stat().st_size} bytes)")

    # Check if it's JSONL files first (most common case)
    train_jsonl = train_path / "train.jsonl"
    dataset_info = train_path / "dataset_info.json"

    if train_jsonl.exists():
        # JSONL files - load them directly
        logger.info("Loading dataset from JSONL files")
        data_files = {
            "train": str(train_jsonl),
        }
        dev_jsonl = train_path / "dev.jsonl"
        test_jsonl = train_path / "test.jsonl"

        if dev_jsonl.exists():
            data_files["validation"] = str(dev_jsonl)
            logger.info(f"Found validation file: {dev_jsonl}")
        if test_jsonl.exists():
            data_files["test"] = str(test_jsonl)
            logger.info(f"Found test file: {test_jsonl}")

        from datasets import load_dataset
        logger.info(f"Loading with data_files: {data_files}")
        dataset = load_dataset("json", data_files=data_files)
        logger.info("✅ Dataset loaded successfully from JSONL")

    elif dataset_info.exists():
        # HuggingFace dataset format
        logger.info("Loading dataset from HuggingFace format (dataset_info.json found)")
        dataset = load_from_disk(args.train)
        logger.info("✅ Dataset loaded successfully from HuggingFace format")

    else:
        # Neither format found - error
        error_msg = f"No valid dataset found at {args.train}. Expected either:\n"
        error_msg += f"  - JSONL files (train.jsonl, dev.jsonl, test.jsonl)\n"
        error_msg += f"  - HuggingFace dataset (dataset_info.json)\n"
        error_msg += f"Contents: {list(train_path.iterdir()) if train_path.exists() else 'directory does not exist'}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    logger.info(f"Train samples: {len(dataset['train'])}")

    # Load tokenizer and model
    logger.info(f"Loading model: {args.model_id}")
    tokenizer = AutoTokenizer.from_pretrained(args.model_id)

    # Determine number of labels
    # Check if labels exist in the dataset
    label_field = None
    for field in ["labels", "ner_tags", "tags"]:
        if field in dataset["train"].features:
            label_field = field
            break

    if label_field:
        # Get all unique labels from the dataset
        all_labels = set()
        for example in dataset["train"]:
            if isinstance(example[label_field], list):
                all_labels.update(example[label_field])
            else:
                all_labels.add(example[label_field])
        num_labels = len(all_labels)
        logger.info(f"Number of labels ({label_field}): {num_labels}")
    else:
        # Default for BIO tagging: O, B-*, I-* for common entities
        num_labels = 7  # O, B-PER, I-PER, B-ORG, I-ORG, B-LOC, I-LOC
        logger.info(f"No label field found, using default num_labels: {num_labels}")

    model = AutoModelForTokenClassification.from_pretrained(
        args.model_id,
        num_labels=num_labels,
    )

    # Tokenize dataset
    def tokenize_and_align_labels(examples):
        """Tokenize tokens and align NER tags with subword tokens."""
        tokenized_inputs = tokenizer(
            examples["tokens"],
            truncation=True,
            is_split_into_words=True,
            padding=False,  # Padding will be done by data collator
        )

        labels = []
        for i, label in enumerate(examples[label_field]):
            word_ids = tokenized_inputs.word_ids(batch_index=i)
            previous_word_idx = None
            label_ids = []
            for word_idx in word_ids:
                # Special tokens have word_id = None
                if word_idx is None:
                    label_ids.append(-100)
                # First subword of a word gets the label
                elif word_idx != previous_word_idx:
                    label_ids.append(label[word_idx])
                # Other subwords get -100 (ignored in loss)
                else:
                    label_ids.append(-100)
                previous_word_idx = word_idx
            labels.append(label_ids)

        tokenized_inputs["labels"] = labels
        return tokenized_inputs

    logger.info("Tokenizing dataset...")
    tokenized_dataset = dataset.map(
        tokenize_and_align_labels,
        batched=True,
        remove_columns=dataset["train"].column_names,
    )
    logger.info(f"✅ Dataset tokenized. Train samples: {len(tokenized_dataset['train'])}")

    # Apply LoRA if enabled
    if args.use_peft:
        logger.info("Applying LoRA configuration")

        # Determine target modules based on model architecture
        if "distilbert" in args.model_id.lower():
            target_modules = ["q_lin", "v_lin"]  # DistilBERT uses q_lin, k_lin, v_lin
        else:
            target_modules = ["query", "value"]  # Standard BERT/RoBERTa use query, key, value

        logger.info(f"LoRA target modules: {target_modules}")

        peft_config = LoraConfig(
            task_type=TaskType.TOKEN_CLS,
            inference_mode=False,
            r=args.lora_r,
            lora_alpha=args.lora_alpha,
            lora_dropout=args.lora_dropout,
            target_modules=target_modules,
        )
        model = get_peft_model(model, peft_config)
        model.print_trainable_parameters()

    # Data collator (tokenizer needed for padding)
    data_collator = DataCollatorForTokenClassification(tokenizer=tokenizer)

    # Training arguments
    training_args = TrainingArguments(
        output_dir=args.model_dir,
        learning_rate=args.learning_rate,
        num_train_epochs=args.num_train_epochs,
        per_device_train_batch_size=args.per_device_train_batch_size,
        warmup_steps=args.warmup_steps,
        logging_dir=f"{args.output_data_dir}/logs",
        logging_steps=10,
        save_strategy="epoch",
        evaluation_strategy="epoch" if "validation" in tokenized_dataset else "no",
        load_best_model_at_end=True if "validation" in tokenized_dataset else False,
        report_to="none",  # MLflow logging handled separately
    )

    # Create trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset["train"],
        eval_dataset=tokenized_dataset.get("validation"),
        tokenizer=tokenizer,
        data_collator=data_collator,
    )

    # Train
    logger.info("Starting training...")
    train_result = trainer.train()

    # Log metrics to MLflow
    if mlflow_uri:
        mlflow.log_params({
            "model_id": args.model_id,
            "use_peft": args.use_peft,
            "learning_rate": args.learning_rate,
            "num_epochs": args.num_train_epochs,
            "batch_size": args.per_device_train_batch_size,
        })

        mlflow.log_metrics({
            "train_loss": train_result.training_loss,
        })

    # Save model
    logger.info(f"Saving model to {args.model_dir}")
    trainer.save_model(args.model_dir)
    tokenizer.save_pretrained(args.model_dir)

    # Save training metrics
    metrics = trainer.evaluate() if "validation" in tokenized_dataset else {}

    logger.info("=" * 70)
    logger.info("Training Complete!")
    logger.info(f"Train Loss: {train_result.training_loss:.4f}")
    if metrics:
        logger.info(f"Val Loss: {metrics.get('eval_loss', 0):.4f}")
    logger.info("=" * 70)

    # End MLflow run
    if mlflow_uri:
        mlflow.end_run()


if __name__ == "__main__":
    main()
