"""Export a CMMS field extractor Unsloth adapter to GGUF."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a CMMS field extractor LoRA adapter to GGUF.")
    parser.add_argument("--adapter-dir", required=True, help="Path to the saved LoRA adapter directory.")
    parser.add_argument("--output-dir", required=True, help="Directory where GGUF export files will be written.")
    parser.add_argument("--max-seq-length", type=int, default=512)
    parser.add_argument("--quantization-method", default="q4_k_m")
    parser.add_argument(
        "--disable-unsloth-compile",
        action="store_true",
        help="Disable Unsloth/PyTorch compile for Phi LongRoPE compatibility.",
    )
    return parser.parse_args(argv)


def configure_runtime(disable_compile: bool) -> None:
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")
    if disable_compile:
        os.environ["UNSLOTH_COMPILE_DISABLE"] = "1"
        os.environ["TORCHDYNAMO_DISABLE"] = "1"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    adapter_dir = Path(args.adapter_dir)
    if not adapter_dir.exists():
        raise SystemExit(f"adapter_dir_not_found:{adapter_dir}")

    configure_runtime(args.disable_unsloth_compile)

    from unsloth import FastLanguageModel

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=str(adapter_dir),
        max_seq_length=args.max_seq_length,
        dtype=None,
        load_in_4bit=True,
    )
    model.save_pretrained_gguf(
        args.output_dir,
        tokenizer,
        quantization_method=args.quantization_method,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
