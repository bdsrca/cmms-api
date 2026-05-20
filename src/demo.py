from __future__ import annotations

import json
from pathlib import Path

from free_token_policy import issue_free_token
from intake_pipeline import run_text_intake

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    environment = json.loads((ROOT / "data" / "sample_environment.json").read_text())
    raw_token, token = issue_free_token(
        environment_code="DEMO",
        scopes=["intake:text", "contracts:validate", "analytics:basic-summary"],
    )
    result = run_text_intake(
        raw_token=raw_token,
        token=token,
        environment=environment,
        text="There is a water leak in ARC room 205. It looks urgent.",
    )
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
