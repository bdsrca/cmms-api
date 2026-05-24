"""Demo environment setup for local CMMS agent workflows."""

from __future__ import annotations

import json
from typing import Any

from .cmms_connectors import public_cmms_connector, upsert_cmms_connector
from .db import db_execute, db_fetchone, now_text
from .environments import import_code_rows
from .validation_rules import ensure_validation_rules


def metadata(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True)


def ensure_environment(environment_code: str) -> str:
    env_code = str(environment_code or "DEFAULT").strip().upper()
    if not env_code:
        env_code = "DEFAULT"
    existing = db_fetchone("SELECT environment_code FROM environments WHERE environment_code = ?", (env_code,))
    if existing:
        db_execute("UPDATE environments SET enabled = 1, updated_at = ? WHERE environment_code = ?", (now_text(), env_code))
    else:
        timestamp = now_text()
        db_execute(
            """
            INSERT INTO environments (environment_code, name, enabled, default_workflow_mode, created_at, updated_at)
            VALUES (?, ?, 1, 'fast', ?, ?)
            """,
            (env_code, f"{env_code} demo environment", timestamp, timestamp),
        )
    ensure_validation_rules(env_code)
    return env_code


def demo_rows() -> dict[str, list[dict[str, str]]]:
    return {
        "buildings": [
            {"code": "ARC", "label": "ARC Building", "aliases": "Arts Research Center"},
            {"code": "CAMPUSVIEW", "label": "Campus View", "aliases": "Campus View Building"},
            {"code": "ZONE-18", "label": "Zone 18", "aliases": "Zone Eighteen"},
        ],
        "rooms": [
            {"code": "205", "label": "Room 205"},
            {"code": "301", "label": "Room 301"},
            {"code": "110", "label": "Room 110"},
            {"code": "MECH-1", "label": "Mechanical Room 1"},
            {"code": "MECH-2", "label": "Mechanical Room 2"},
            {"code": "ROOF", "label": "Roof"},
            {"code": "B1-MECH", "label": "Basement Mechanical"},
        ],
        "priorities": [
            {"code": "LOW", "label": "Low"},
            {"code": "NORMAL", "label": "Normal"},
            {"code": "URGENT", "label": "Urgent"},
        ],
        "work_order_types": [
            {"code": "HVAC", "label": "HVAC"},
            {"code": "Plumbing", "label": "Plumbing"},
            {"code": "Electrical", "label": "Electrical"},
            {"code": "General Maintenance", "label": "General Maintenance"},
        ],
        "assign_to": [
            {"code": "Nina Night", "label": "Nina Night"},
            {"code": "Omar Overnight", "label": "Omar Overnight"},
            {"code": "Priya Day", "label": "Priya Day"},
            {"code": "Marco Evening", "label": "Marco Evening"},
            {"code": "Facilities", "label": "Facilities Queue"},
        ],
        "issue_to_employee_number": [
            {"code": "100", "label": "Nina Night"},
            {"code": "200", "label": "Omar Overnight"},
            {"code": "300", "label": "Priya Day"},
            {"code": "400", "label": "Marco Evening"},
            {"code": "0000", "label": "Facilities Queue"},
        ],
        "job_type": [
            {"code": "Maintenance", "label": "Maintenance"},
            {"code": "Inspection", "label": "Inspection"},
            {"code": "Emergency", "label": "Emergency"},
        ],
        "assets": [
            {
                "code": "AHU-3",
                "label": "Air Handler Unit 3",
                "aliases": "AHU 3,Air Handler 3",
                "metadata_json": metadata(
                    {
                        "asset_type": "Air Handler Unit",
                        "building": "ARC",
                        "room": "MECH-1",
                        "trade": "HVAC",
                        "work_order_type": "HVAC",
                        "parts": [
                            {
                                "part_number": "FILTER-AHU-20X25X2",
                                "description": "20x25x2 AHU filter",
                                "quantity": 4,
                                "unit": "EA",
                            }
                        ],
                    }
                ),
            },
            {
                "code": "AHU-4",
                "label": "Air Handler Unit 4",
                "aliases": "AHU 4,Air Handler 4",
                "metadata_json": metadata(
                    {
                        "asset_type": "Air Handler Unit",
                        "building": "CAMPUSVIEW",
                        "room": "ROOF",
                        "trade": "HVAC",
                        "work_order_type": "HVAC",
                    }
                ),
            },
            {
                "code": "PUMP-2",
                "label": "Hot Water Pump 2",
                "aliases": "Pump 2,HWP-2",
                "metadata_json": metadata(
                    {
                        "asset_type": "Pump",
                        "building": "ARC",
                        "room": "B1-MECH",
                        "trade": "Plumbing",
                        "work_order_type": "Plumbing",
                    }
                ),
            },
            {
                "code": "ELEC-PNL-1",
                "label": "Electrical Panel 1",
                "aliases": "Panel 1,Electrical Panel 1",
                "metadata_json": metadata(
                    {
                        "asset_type": "Electrical Panel",
                        "building": "ZONE-18",
                        "room": "110",
                        "trade": "Electrical",
                        "work_order_type": "Electrical",
                    }
                ),
            },
            {
                "code": "FCU-12",
                "label": "Fan Coil Unit 12",
                "aliases": "FCU 12,Fan Coil 12",
                "metadata_json": metadata(
                    {
                        "asset_type": "Fan Coil Unit",
                        "building": "CAMPUSVIEW",
                        "room": "301",
                        "trade": "HVAC",
                        "work_order_type": "HVAC",
                    }
                ),
            },
        ],
        "technician_roster": [
            {
                "code": "TECH-100",
                "label": "Nina Night",
                "aliases": "Nina,Night HVAC",
                "metadata_json": metadata(
                    {
                        "shift": "night",
                        "trades": ["HVAC"],
                        "assign_to": "Nina Night",
                        "issue_to": "100",
                        "job_type": "Maintenance",
                    }
                ),
            },
            {
                "code": "TECH-200",
                "label": "Omar Overnight",
                "aliases": "Omar,Night Plumbing",
                "metadata_json": metadata(
                    {
                        "shift": "night",
                        "trades": ["Plumbing", "General Maintenance"],
                        "assign_to": "Omar Overnight",
                        "issue_to": "200",
                        "job_type": "Maintenance",
                    }
                ),
            },
            {
                "code": "TECH-300",
                "label": "Priya Day",
                "aliases": "Priya,Day HVAC",
                "metadata_json": metadata(
                    {
                        "shift": "day",
                        "trades": ["HVAC", "Electrical"],
                        "assign_to": "Priya Day",
                        "issue_to": "300",
                        "job_type": "Inspection",
                    }
                ),
            },
            {
                "code": "TECH-400",
                "label": "Marco Evening",
                "aliases": "Marco,Evening Electrical",
                "metadata_json": metadata(
                    {
                        "shift": "evening",
                        "trades": ["Electrical", "General Maintenance"],
                        "assign_to": "Marco Evening",
                        "issue_to": "400",
                        "job_type": "Maintenance",
                    }
                ),
            },
            {
                "code": "TECH-500",
                "label": "Facilities Queue",
                "aliases": "Facilities,Default Queue",
                "metadata_json": metadata(
                    {
                        "shift": "day",
                        "trades": ["General Maintenance"],
                        "assign_to": "Facilities",
                        "issue_to": "0000",
                        "job_type": "Maintenance",
                    }
                ),
            },
        ],
        "custom:inventory_parts": [
            {
                "code": "FILTER-AHU-20X25X2",
                "label": "20x25x2 AHU filter",
                "aliases": "AHU filter,20x25x2",
                "metadata_json": metadata({"quantity_on_hand": 0, "reorder_quantity": 12, "unit": "EA"}),
            },
            {
                "code": "BELT-AHU-B43",
                "label": "AHU belt B43",
                "aliases": "B43 belt",
                "metadata_json": metadata({"quantity_on_hand": 3, "reorder_quantity": 6, "unit": "EA"}),
            },
        ],
    }


def seed_demo_environment(environment_code: str = "DEFAULT") -> dict[str, Any]:
    env_code = ensure_environment(environment_code)
    counts: dict[str, int] = {}
    rows_by_category = demo_rows()
    for category, rows in rows_by_category.items():
        counts[category] = import_code_rows(env_code, category, rows, replace=True)

    connector = upsert_cmms_connector(
        env_code,
        {
            "enabled": True,
            "auto_push_enabled": True,
            "endpoint_url": "http://localhost/fake-cmms/work-orders",
            "auth_type": "bearer",
            "secret_value": "fake-demo-token",
            "timeout_seconds": 3,
            "http_method": "POST",
            "success_status_codes": "200,201,202",
            "external_id_path": "id",
            "dry_run_enabled": True,
            "require_metadata_review": False,
            "static_headers": {"X-CMMS-Demo": "true"},
            "payload_root_key": "workOrder",
            "auto_push_note": "Local fake connector. Dry-run only; no external CMMS write is performed.",
        },
    )

    return {
        "status": "ok",
        "environment_code": env_code,
        "counts": counts,
        "shifts": ["day", "evening", "night"],
        "connector": public_cmms_connector(connector),
    }
