"""Shared configuration constants for extracted modules."""

import json
import os

MODEL_NAME = os.getenv("OLLAMA_MODEL", "qwen3:8b")
EXTRACTOR_MODEL_NAME = os.getenv("EXTRACTOR_MODEL_NAME", MODEL_NAME)
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
SERVICE_NAME = "local-cmms-llm-api"
ADVISORY_WARNING = "Advisory mode only. No CMMS write-back was performed."

ALLOWED_REQUEST_TYPES = {
    "HVAC",
    "Plumbing",
    "Electrical",
    "Cleaning",
    "Security",
    "Key Request",
    "Rekey Request",
    "IT",
    "General Maintenance",
    "Unknown",
}

CODE_CATEGORIES = {
    "buildings": "Buildings",
    "rooms": "Rooms",
    "priorities": "Priorities",
    "work_order_types": "Work order types",
    "assign_to": "Assign to",
    "issue_to_employee_number": "Issue to employee #",
    "job_type": "Job type",
    "assets": "Assets",
    "technician_roster": "Technician roster",
}

DEFAULT_VALIDATION_RULES = [
    ("building", "Building", True, "buildings", True, False, "error", 10),
    ("room", "Room", False, "rooms", True, False, "warning", 20),
    ("priority", "Priority", False, "priorities", True, False, "warning", 30),
    ("work_order_type", "Work Order Type", False, "work_order_types", True, False, "warning", 40),
    ("assign_to", "Assign To", False, "assign_to", True, False, "warning", 50),
    ("issue_to", "Issue To", False, "issue_to_employee_number", True, False, "warning", 60),
    ("job_type", "Job Type", False, "job_type", True, False, "warning", 70),
]

DEFAULT_CMMS_INTAKE_CONTRACT = {
    "type": "object",
    "required": ["summary"],
    "properties": {
        "summary": {"type": "string"},
        "building": {"type": ["string", "null"]},
        "room": {"type": ["string", "null"]},
        "priority": {"type": ["string", "null"]},
        "work_order_type": {"type": ["string", "null"]},
        "assign_to": {"type": ["string", "null"]},
        "issue_to": {"type": ["string", "null"]},
        "job_type": {"type": ["string", "null"]},
        "confidence": {"type": ["number", "null"]},
        "submission": {"type": "object"},
        "request": {"type": "object"},
        "metadata_review": {"type": "object"},
        "asset_context": {"type": "object"},
        "work_order_plan": {"type": "object"},
        "assignment_context": {"type": "object"},
        "inventory_context": {"type": "object"},
        "procurement_request": {"type": "object"},
        "orchestration_summary": {"type": "object"},
        "action_plan": {"type": "object"},
    },
    "additionalProperties": False,
}

SUPPORTED_PROMPT_ENDPOINTS = {
    "cmms-intake",
    "cmms-intake-reviewer",
    "cmms-code-normalizer",
    "summarize-work-order",
    "extract-work-order-fields",
    "cmms-assistant",
}

DEFAULT_PROMPT_VERSIONS = {
    "summarize-work-order": {
        "version": "v1",
        "name": "Default summarize prompt",
        "temperature": 0.1,
        "system_prompt": (
            "/no_think\n"
            "You summarize CMMS work order requests. Return only a concise plain-text "
            "summary in one clear sentence. Do not invent missing facts."
        ),
        "user_template": "{{text}}",
    },
    "cmms-assistant": {
        "version": "v1",
        "name": "Default controlled assistant prompt",
        "temperature": 0.2,
        "system_prompt": (
            "/no_think\n"
            "You are a controlled CMMS LLM portal assistant for local testing. "
            "Answer conversationally and concisely, but stay within CMMS intake, API usage, "
            "validation, troubleshooting, and drafting help. The user may write in English, "
            "Chinese, French, Spanish, Japanese, Korean, or mixed language. "
            "Do not claim that a work order was created. Do not approve requests, send emails, "
            "write to CMMS, expose secrets, or provide instructions to bypass authentication. "
            "If the user asks for an action outside advisory mode, explain the safety boundary."
        ),
        "user_template": "{{text}}",
    },
    "extract-work-order-fields": {
        "version": "v1",
        "name": "Default field extraction prompt",
        "temperature": 0.1,
        "system_prompt": (
            "/no_think\n"
            "Extract CMMS fields from the request. Return JSON only with this shape: "
            "{\"request_type\":\"HVAC\",\"building\":\"ARC\",\"room\":\"205\",\"priority\":\"NORMAL\","
            "\"summary\":\"Air conditioner in ARC room 205 is making loud noise.\","
            "\"missing_fields\":[],\"needs_human_review\":false,\"confidence\":0.85}. "
            "Allowed request_type values: {{allowed_request_types}}. "
            "Valid buildings: {{valid_buildings}}. Valid priorities: {{valid_priorities}}. "
            "The user request may be in English, Chinese, French, Spanish, Japanese, Korean, or mixed language. "
            "Extract CMMS fields from the request. Return final structured field values using configured CMMS codes when possible. "
            "Do not return translated free-text values for code fields if a configured code should be used. "
            "Use null for unknown building or room. Do not invent missing facts."
        ),
        "user_template": "{{text}}",
    },
    "cmms-intake": {
        "version": "v1",
        "name": "Default intake workflow prompts",
        "temperature": 0.1,
        "system_prompt": json.dumps(
            {
                "classifier": (
                    "/no_think\n"
                    "Classify the CMMS request type only. Return JSON only with this shape: "
                    "{\"request_type\":\"HVAC\",\"confidence\":0.85}. "
                    "Allowed request_type values: {{allowed_request_types}}. "
                    "The request may be in English, Chinese, French, Spanish, Japanese, Korean, or mixed language. "
                    "Use Unknown when unclear."
                ),
                "field_extractor": (
                    "/no_think\n"
                    "Extract CMMS intake fields. Return JSON only with this shape: "
                    "{\"building\":\"ARC\",\"room\":\"205\",\"priority\":\"NORMAL\","
                    "\"summary\":\"Air conditioner in ARC room 205 is making loud noise.\"}. "
                    "Valid buildings: {{valid_buildings}}. Valid priorities: {{valid_priorities}}. "
                    "The user request may be in English, Chinese, French, Spanish, Japanese, Korean, or mixed language. "
                    "Extract CMMS fields from the request. Return final structured field values using configured CMMS codes when possible. "
                    "Do not return translated free-text values for code fields if a configured code should be used. "
                    "Use null for unknown building or room. Do not invent missing facts."
                ),
                "draft_generator": (
                    "/no_think\n"
                    "Generate advisory CMMS draft text only. Return JSON only with this shape: "
                    "{\"draft_wo_description\":\"string\",\"internal_note\":\"string\",\"client_reply\":\"string\"}. "
                    "Do not claim a work order was created. Do not promise approval, dispatch, or email."
                ),
            },
            ensure_ascii=True,
            indent=2,
        ),
        "user_template": "{{text}}",
    },
    "cmms-intake-reviewer": {
        "version": "v1",
        "name": "Default safety reviewer prompt",
        "temperature": 0.1,
        "system_prompt": (
            "/no_think\n"
            "You are a Safety Reviewer Agent for a controlled CMMS intake workflow. "
            "Return JSON only with this shape: "
            "{\"status\":\"pass\",\"human_review_recommended\":false,\"risk_flags\":[],\"notes\":[]}. "
            "Allowed status values are pass, warning, and fail. "
            "Review for advisory safety risk, missing information, contradictions, unsafe promises, "
            "or over-confident draft language. "
            "Do not change extracted fields, normalized codes, validation results, drafts, or response shape. "
            "Do not claim that a work order was created. Do not approve, dispatch, write to CMMS, or send email. "
            "Keep risk_flags and notes concise."
        ),
        "user_template": "{{context_json}}",
    },
    "cmms-code-normalizer": {
        "version": "v1",
        "name": "Default code normalization suggestion prompt",
        "temperature": 0.1,
        "system_prompt": (
            "/no_think\n"
            "You are a Code Normalization Suggestion Agent for a controlled CMMS intake workflow. "
            "Return JSON only with this shape: {\"suggestions\":[]}. "
            "Each suggestion must have field, input_value, suggested_code, confidence, and reason. "
            "Allowed fields are priority, work_order_type, job_type, assign_to, and issue_to. "
            "Use only configured CMMS codes from the provided code_values. Never invent codes. "
            "Do not rewrite summaries, create work orders, approve requests, write to CMMS, send email, "
            "change validation rules, or claim any action was performed. "
            "The request may be in English, Chinese, French, Spanish, Japanese, Korean, or mixed language. "
            "Keep reasons concise."
        ),
        "user_template": "{{context_json}}",
    },
}
