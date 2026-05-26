"""Optional Unsloth training entrypoint for the CMMS field extractor adapter.

This module is import-safe for normal test runs. Heavy ML dependencies are
imported inside `main` only.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train CMMS field extractor QLoRA adapter.")
    parser.add_argument("--data-path", required=True, help="Path to train JSONL.")
    parser.add_argument("--eval-path", help="Path to eval JSONL.")
    parser.add_argument("--base-model", default="Qwen/Qwen3-8B-Instruct")
    parser.add_argument("--output-dir", default="models/cmms_field_extractor/lora-v1")
    parser.add_argument("--max-seq-length", type=int, default=2048)
    parser.add_argument("--num-train-epochs", type=float, default=2.0)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data_path = Path(args.data_path)
    if not data_path.exists():
        raise SystemExit(f"data_path_not_found:{data_path}")

    try:
        from datasets import load_dataset
        from transformers import TrainingArguments
        from trl import SFTTrainer
        from unsloth import FastLanguageModel
    except ImportError as exc:
        raise SystemExit(
            "Missing optional training dependencies. Install Unsloth, datasets, trl, "
            "and transformers in a dedicated training environment."
        ) from exc

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

    dataset = dataset.map(formatting_prompts_func, batched=True)

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset["train"],
        eval_dataset=dataset.get("validation"),
        args=TrainingArguments(
            output_dir=args.output_dir,
            per_device_train_batch_size=2,
            gradient_accumulation_steps=8,
            num_train_epochs=args.num_train_epochs,
            learning_rate=args.learning_rate,
            logging_steps=10,
            save_strategy="epoch",
            eval_strategy="epoch" if "validation" in dataset else "no",
            report_to=[],
        ),
        dataset_text_field="text",
        max_seq_length=args.max_seq_length,
        dataset_num_proc=2,
        packing=False,
    )
    trainer.train()
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
