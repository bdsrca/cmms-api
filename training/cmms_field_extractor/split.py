"""Deterministic train/eval/locked-test splitting."""

from __future__ import annotations

import random
from typing import Any


def split_records(
    records: list[dict[str, Any]],
    *,
    seed: int = 42,
    train_ratio: float = 0.70,
    eval_ratio: float = 0.15,
) -> dict[str, list[dict[str, Any]]]:
    if len(records) < 10:
        raise ValueError("at_least_10_records_required")

    shuffled = list(records)
    random.Random(seed).shuffle(shuffled)

    train_count = int(len(shuffled) * train_ratio)
    eval_count = int(len(shuffled) * eval_ratio)

    train = shuffled[:train_count]
    eval_records = shuffled[train_count : train_count + eval_count]
    locked_test = shuffled[train_count + eval_count :]

    return {
        "train": train,
        "eval": eval_records,
        "locked_test": locked_test,
    }
