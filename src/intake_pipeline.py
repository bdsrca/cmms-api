"""End-to-end intake pipeline for the showcase."""

from __future__ import annotations

from typing import Any

from agent_orchestrator import build_agent_review
from contract_validator import validate_contract
from environment_validator import validate_environment
from free_token_policy import FreeToken, consume_token, verify_token
from private_llm_gateway import extract_work_request
from secure_logger import build_event


def run_text_intake(
    *,
    raw_token: str,
    token: FreeToken,
    environment: dict[str, Any],
    text: str,
) -> dict[str, Any]:
    environment_code = environment["environment_code"]
    ok, reason = verify_token(raw_token, token, scope="intake:text", environment_code=environment_code)
    if not ok:
        event = build_event(
            endpoint="intake:text",
            token_prefix=token.prefix,
            environment_code=environment_code,
            status=reason,
            payload={"text": text},
        )
        return {"ok": False, "error": reason, "audit_event": event}

    draft = extract_work_request(text)
    contract_result = validate_contract(draft)
    env_result = validate_environment(draft, environment)
    agent_review = build_agent_review(env_result["normalized"], env_result)
    consume_token(token)

    status = "ok"
    if contract_result["errors"] or env_result["errors"]:
        status = "validation_error"
    elif contract_result["warnings"] or env_result["warnings"]:
        status = "validation_warning"

    event = build_event(
        endpoint="intake:text",
        token_prefix=token.prefix,
        environment_code=environment_code,
        status=status,
        payload={"text": text, "draft": env_result["normalized"]},
    )

    return {
        "ok": status != "validation_error",
        "draft": env_result["normalized"],
        "contract_validation": contract_result,
        "environment_validation": env_result,
        "agent_review": agent_review,
        "next_action": agent_review["next_action"],
        "audit_event": event,
    }
