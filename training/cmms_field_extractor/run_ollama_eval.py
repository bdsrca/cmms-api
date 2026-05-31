"""Run Ollama baseline evaluation for CMMS field extractor records."""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path
from typing import Any

try:
    from .evaluate import evaluate_predictions
except ImportError:  # pragma: no cover - direct script execution fallback
    from training.cmms_field_extractor.evaluate import evaluate_predictions


DEFAULT_SYSTEM_PROMPT = (
    "/no_think\n"
    "Extract CMMS work request fields for a college/campus facilities environment. "
    "Return strict JSON only. "
    "Do not predict building or room; those are input code fields merged by the API. "
    "Return exactly these keys and no extra keys: request_type, asset_hint, "
    "priority, summary, missing_fields, human_review_recommended. "
    "Use exact CMMS code casing for request_type and priority. "
    "Allowed request_type values: Cleaning, Electrical, General Maintenance, HVAC, IT, "
    "Key Request, Plumbing, Security. "
    "Allowed priority values: P1, P2, P3, P4, P5. "
    "Use null for unknown asset_hint. "
    "Keep summary concise, at most 160 characters. "
    "missing_fields must be an array of missing field names. "
    "human_review_recommended must be a boolean. "
    "Do not invent missing facts. Never claim that a work order was created."
)


def prompt_messages_from_record(
    record: dict[str, Any],
    *,
    system_prompt: str | None = None,
) -> list[dict[str, str]]:
    messages = [
        {"role": message["role"], "content": message["content"]}
        for message in record["messages"]
        if message["role"] != "assistant"
    ]
    if system_prompt is not None:
        if messages and messages[0]["role"] == "system":
            messages[0] = {"role": "system", "content": system_prompt}
        else:
            messages.insert(0, {"role": "system", "content": system_prompt})
    return messages


def expected_payload_from_record(record: dict[str, Any]) -> dict[str, Any]:
    for message in reversed(record["messages"]):
        if message.get("role") == "assistant":
            payload = json.loads(message["content"])
            if not isinstance(payload, dict):
                raise ValueError("assistant_payload_not_object")
            return payload
    raise ValueError("assistant_payload_missing")


def build_eval_example(record: dict[str, Any], *, example_id: str, prediction: str) -> dict[str, Any]:
    return {
        "id": example_id,
        "expected": expected_payload_from_record(record),
        "prediction": prediction,
    }


def build_ollama_chat_payload(*, model: str, messages: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "model": model,
        "messages": messages,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
    }


def call_ollama_chat(*, base_url: str, payload: dict[str, Any], timeout_seconds: float) -> str:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        response_payload = json.loads(response.read().decode("utf-8"))
    message = response_payload.get("message")
    if not isinstance(message, dict):
        raise ValueError("ollama_response_message_missing")
    content = message.get("content")
    if not isinstance(content, str):
        raise ValueError("ollama_response_content_missing")
    return content


def load_records(path: Path, limit: int | None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if limit is not None and len(records) >= limit:
                break
            records.append(json.loads(line))
    return records


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def run_ollama_eval(
    *,
    data_path: Path,
    model: str,
    output_path: Path,
    report_path: Path,
    limit: int | None,
    base_url: str,
    timeout_seconds: float,
    use_record_system_prompt: bool = False,
) -> dict[str, Any]:
    records = load_records(data_path, limit)
    examples: list[dict[str, Any]] = []

    for index, record in enumerate(records):
        payload = build_ollama_chat_payload(
            model=model,
            messages=prompt_messages_from_record(
                record,
                system_prompt=None if use_record_system_prompt else DEFAULT_SYSTEM_PROMPT,
            ),
        )
        prediction = call_ollama_chat(
            base_url=base_url,
            payload=payload,
            timeout_seconds=timeout_seconds,
        )
        examples.append(build_eval_example(record, example_id=str(index), prediction=prediction))

    report = evaluate_predictions(examples)
    report["model"] = model
    report["data_path"] = str(data_path)
    report["limit"] = limit
    write_jsonl(output_path, examples)
    write_json(report_path, report)
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate an Ollama model against CMMS extractor JSONL records.")
    parser.add_argument("--data-path", default="data/cmms_field_extractor/locked_test.jsonl")
    parser.add_argument("--model", default="phi4-mini:latest")
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--report-path", required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--use-record-system-prompt", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_ollama_eval(
        data_path=Path(args.data_path),
        model=args.model,
        output_path=Path(args.output_path),
        report_path=Path(args.report_path),
        limit=args.limit,
        base_url=args.base_url,
        timeout_seconds=args.timeout_seconds,
        use_record_system_prompt=args.use_record_system_prompt,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
