"""Optional Unsloth training entrypoint for the CMMS field extractor adapter.

This module is import-safe for normal test runs. Heavy ML dependencies are
imported inside `main` only.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def sft_dataset_kwargs() -> dict[str, bool]:
    return {"skip_prepare_dataset": True}


def configure_unsloth_compile(disable_compile: bool) -> None:
    if not disable_compile:
        return
    os.environ["UNSLOTH_COMPILE_DISABLE"] = "1"
    os.environ["TORCHDYNAMO_DISABLE"] = "1"


def fused_loss_target_gb(free_bytes: int, min_target_gb: float) -> float:
    free_gb = free_bytes / 1024 / 1024 / 1024
    return max(free_gb * 0.5, min_target_gb)


def patch_unsloth_fused_loss_min_target(min_target_gb: float) -> None:
    if min_target_gb <= 0:
        return
    import functools

    import torch
    from unsloth_zoo.fused_losses import cross_entropy_loss

    def _get_chunk_multiplier(vocab_size, target_gb=None):
        if target_gb is None:
            free, _total = torch.cuda.mem_get_info(0)
            target_gb = fused_loss_target_gb(free, min_target_gb)
        multiplier = (vocab_size * 4 / 1024 / 1024 / 1024) / target_gb
        return multiplier / 4

    cross_entropy_loss._get_chunk_multiplier = functools.cache(_get_chunk_multiplier)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train CMMS field extractor QLoRA adapter.")
    parser.add_argument("--data-path", required=True, help="Path to train JSONL.")
    parser.add_argument("--eval-path", help="Path to eval JSONL.")
    parser.add_argument("--base-model", default="unsloth/Qwen3-8B-unsloth-bnb-4bit")
    parser.add_argument("--output-dir", default="models/cmms_field_extractor/lora-v1")
    parser.add_argument("--max-seq-length", type=int, default=1024)
    parser.add_argument("--num-train-epochs", type=float, default=2.0)
    parser.add_argument("--max-steps", type=int, default=-1)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--per-device-train-batch-size", type=int, default=1)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=8)
    parser.add_argument("--dataset-num-proc", type=int)
    parser.add_argument(
        "--return-logits",
        action="store_true",
        help="Set UNSLOTH_RETURN_LOGITS=1 before importing Unsloth to bypass fused CE loss.",
    )
    parser.add_argument(
        "--disable-unsloth-compile",
        action="store_true",
        help="Disable Unsloth/PyTorch compile for models with dynamic control flow.",
    )
    parser.add_argument(
        "--min-fused-loss-gb",
        type=float,
        default=0.05,
        help="Minimum target GB used when Unsloth auto-detects no free VRAM for fused loss.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data_path = Path(args.data_path)
    if not data_path.exists():
        raise SystemExit(f"data_path_not_found:{data_path}")
    if args.return_logits:
        os.environ["UNSLOTH_RETURN_LOGITS"] = "1"
    configure_unsloth_compile(args.disable_unsloth_compile)

    try:
        from unsloth import FastLanguageModel
        from datasets import load_dataset
        from trl import SFTConfig, SFTTrainer
    except ImportError as exc:
        raise SystemExit(
            "Missing optional training dependencies. Install Unsloth, datasets, trl, "
            "and transformers in a dedicated training environment."
        ) from exc
    patch_unsloth_fused_loss_min_target(args.min_fused_loss_gb)

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.base_model,
        max_seq_length=args.max_seq_length,
        dtype=None,
        load_in_4bit=True,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_alpha=16,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    dataset_files = {"train": str(data_path)}
    if args.eval_path:
        dataset_files["validation"] = args.eval_path
    dataset = load_dataset("json", data_files=dataset_files)

    def formatting_prompts_func(batch):
        texts = []
        for messages in batch["messages"]:
            texts.append(tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False))
        return {"text": texts}

    map_kwargs = {}
    if args.dataset_num_proc is not None:
        map_kwargs["num_proc"] = args.dataset_num_proc
    dataset = dataset.map(formatting_prompts_func, batched=True, **map_kwargs)

    def tokenize_text(batch):
        return tokenizer(
            batch["text"],
            truncation=True,
            max_length=args.max_seq_length,
            return_token_type_ids=False,
        )

    tokenized_splits = {}
    for split_name, split_dataset in dataset.items():
        tokenized_splits[split_name] = split_dataset.map(
            tokenize_text,
            batched=True,
            remove_columns=split_dataset.column_names,
            **map_kwargs,
        )
    dataset = tokenized_splits
    eval_dataset = dataset["validation"] if "validation" in dataset else None

    trainer = SFTTrainer(
        model=model,
        processing_class=tokenizer,
        train_dataset=dataset["train"],
        eval_dataset=eval_dataset,
        args=SFTConfig(
            output_dir=args.output_dir,
            per_device_train_batch_size=args.per_device_train_batch_size,
            gradient_accumulation_steps=args.gradient_accumulation_steps,
            num_train_epochs=args.num_train_epochs,
            max_steps=args.max_steps,
            learning_rate=args.learning_rate,
            logging_steps=10,
            save_strategy="epoch",
            eval_strategy="epoch" if eval_dataset is not None else "no",
            report_to=[],
            dataset_text_field="text",
            max_length=args.max_seq_length,
            dataset_num_proc=args.dataset_num_proc,
            dataset_kwargs=sft_dataset_kwargs(),
            packing=False,
        ),
    )
    trainer.train()
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
