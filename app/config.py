"""Shared configuration constants for extracted modules."""

CODE_CATEGORIES = {
    "buildings": "Buildings",
    "rooms": "Rooms",
    "priorities": "Priorities",
    "work_order_types": "Work order types",
    "assign_to": "Assign to",
    "issue_to_employee_number": "Issue to employee #",
    "job_type": "Job type",
}

DEFAULT_VALIDATION_RULES = [
    ("building", "Building", True, "buildings", True, False, "error", 10),
    ("room", "Room", False, "rooms", True, False, "warning", 20),
    ("priority", "Priority", False, "priorities", True, False, "warning", 30),
    ("work_order_type", "Work Order Type", False, "work_order_types", True, False, "warning", 40),
    ("assign_to", "Assign To", False, "assign_to", True, False, "warning", 50),
    ("issue_to", "Issue To", False, "issue_to", True, False, "warning", 60),
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
    },
    "additionalProperties": False,
}
