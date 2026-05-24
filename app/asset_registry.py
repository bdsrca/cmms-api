"""Deterministic asset lookup and advisory planning helpers."""

from __future__ import annotations

import json
import re
from typing import Any

from .db import db_fetchall

ASSET_CATEGORY = "assets"


def clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def compact_identifier(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[^A-Z0-9]+", "", value.upper())


def split_aliases(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    aliases: list[str] = []
    seen: set[str] = set()
    for alias in value.split(","):
        cleaned = alias.strip()
        key = compact_identifier(cleaned)
        if cleaned and key and key not in seen:
            aliases.append(cleaned)
            seen.add(key)
    return aliases


def parse_metadata(value: Any) -> dict[str, Any]:
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def normalized_parts(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    parts = metadata.get("parts")
    normalized: list[dict[str, Any]] = []
    for part in parts if isinstance(parts, list) else []:
        if not isinstance(part, dict):
            continue
        part_number = clean_text(part.get("part_number") or part.get("sku") or part.get("code"))
        description = clean_text(part.get("description") or part.get("label"))
        if not part_number and not description:
            continue
        normalized.append(
            {
                "part_number": part_number,
                "description": description,
                "quantity": part.get("quantity"),
                "unit": clean_text(part.get("unit")),
                "planning_only": True,
            }
        )
    return normalized


def asset_rows(environment_code: str) -> list[Any]:
    return db_fetchall(
        """
        SELECT code, label, aliases, metadata_json
        FROM code_values
        WHERE environment_code = ? AND category = ? AND enabled = 1
        ORDER BY code
        """,
        (environment_code.upper(), ASSET_CATEGORY),
    )


def asset_from_row(row: Any) -> dict[str, Any]:
    metadata = parse_metadata(row["metadata_json"])
    return {
        "code": row["code"],
        "label": row["label"],
        "aliases": split_aliases(row["aliases"]),
        "asset_type": clean_text(metadata.get("asset_type") or metadata.get("type")),
        "building": clean_text(metadata.get("building")),
        "room": clean_text(metadata.get("room")),
        "trade": clean_text(metadata.get("trade")),
        "work_order_type": clean_text(metadata.get("work_order_type")),
        "parts": normalized_parts(metadata),
    }


def match_asset(asset: dict[str, Any], request_text: str) -> tuple[bool, str | None]:
    compact_text = compact_identifier(request_text)
    labels = [asset.get("code"), *asset.get("aliases", []), asset.get("label")]
    for label in labels:
        compact_label = compact_identifier(label)
        if compact_label and compact_label in compact_text:
            return True, clean_text(label)
    return False, None


def base_asset_context(environment_code: str | None) -> dict[str, Any]:
    return {
        "schema": "cmms_asset_context_v1",
        "environment_code": environment_code.upper() if isinstance(environment_code, str) and environment_code.strip() else None,
        "enabled": False,
        "status": "skipped",
        "requires_review": False,
        "asset": None,
        "candidates": [],
        "planning_hints": {"trade": None, "work_order_type": None, "likely_parts": []},
        "reasons": [],
    }


def planning_hints_for_asset(asset: dict[str, Any] | None) -> dict[str, Any]:
    if not asset:
        return {"trade": None, "work_order_type": None, "likely_parts": []}
    return {
        "trade": asset.get("trade"),
        "work_order_type": asset.get("work_order_type"),
        "likely_parts": asset.get("parts") if isinstance(asset.get("parts"), list) else [],
    }


def public_asset_candidate(asset: dict[str, Any], matched_on: str | None = None) -> dict[str, Any]:
    return {
        "code": asset.get("code"),
        "label": asset.get("label"),
        "aliases": asset.get("aliases") if isinstance(asset.get("aliases"), list) else [],
        "asset_type": asset.get("asset_type"),
        "building": asset.get("building"),
        "room": asset.get("room"),
        "matched_on": matched_on,
    }


def resolve_asset_context(request_text: str, environment_code: str | None) -> dict[str, Any]:
    context = base_asset_context(environment_code)
    if not context["environment_code"]:
        context["reasons"].append("No environment_code was supplied; asset resolution was skipped.")
        return context

    assets = [asset_from_row(row) for row in asset_rows(context["environment_code"])]
    if not assets:
        context["status"] = "not_configured"
        context["requires_review"] = True
        context["reasons"].append(f"No asset records are configured for environment {context['environment_code']}.")
        return context

    matches: list[tuple[dict[str, Any], str | None]] = []
    for asset in assets:
        matched, matched_on = match_asset(asset, request_text)
        if matched:
            matches.append((asset, matched_on))

    context["enabled"] = True
    if not matches:
        context["status"] = "not_found"
        context["requires_review"] = True
        context["reasons"].append("No configured asset matched the request text.")
        return context

    context["candidates"] = [public_asset_candidate(asset, matched_on) for asset, matched_on in matches]
    if len(matches) > 1:
        context["status"] = "ambiguous"
        context["requires_review"] = True
        context["reasons"].append("Multiple configured assets matched the request text.")
        return context

    asset, matched_on = matches[0]
    context["status"] = "resolved"
    context["asset"] = public_asset_candidate(asset, matched_on)
    context["planning_hints"] = planning_hints_for_asset(asset)
    context["reasons"].append(f"Matched configured asset {asset['code']}.")
    return context


def build_work_order_plan(asset_context: dict[str, Any]) -> dict[str, Any]:
    status = "planned" if asset_context.get("status") == "resolved" else "needs_review"
    return {
        "schema": "cmms_work_order_plan_v1",
        "status": status,
        "advisory_only": True,
        "asset_code": (asset_context.get("asset") or {}).get("code") if isinstance(asset_context.get("asset"), dict) else None,
        "trade": (asset_context.get("planning_hints") or {}).get("trade") if isinstance(asset_context.get("planning_hints"), dict) else None,
        "work_order_type": (asset_context.get("planning_hints") or {}).get("work_order_type")
        if isinstance(asset_context.get("planning_hints"), dict)
        else None,
        "likely_parts": (asset_context.get("planning_hints") or {}).get("likely_parts", [])
        if isinstance(asset_context.get("planning_hints"), dict)
        else [],
        "requires_review": bool(asset_context.get("requires_review")),
        "reasons": list(asset_context.get("reasons") or []),
    }
