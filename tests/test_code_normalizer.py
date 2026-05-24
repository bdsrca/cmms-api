import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import db
from app.environments import seed_default_environment
from app.validation_rules import get_validation_rules


class CodeNormalizerConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_patcher = patch.object(db, "DB_FILE", Path(self.tmp.name) / "test.db")
        self.db_patcher.start()
        db.init_db()
        seed_default_environment()

    def tearDown(self) -> None:
        self.db_patcher.stop()
        self.tmp.cleanup()

    def test_default_issue_to_rule_uses_employee_number_category(self) -> None:
        rules = get_validation_rules("DEFAULT")
        issue_to = next(rule for rule in rules if rule["field_name"] == "issue_to")

        self.assertEqual(issue_to["code_category"], "issue_to_employee_number")


from app.ai_endpoints import validate_extracted_fields


class CodeNormalizerExtractionTests(unittest.TestCase):
    def test_invalid_priority_preserves_raw_value_and_candidate(self) -> None:
        result = validate_extracted_fields(
            {
                "request_type": "Plumbing",
                "building": "ARC",
                "room": "205",
                "priority": "urgent phrase",
                "summary": "Water leak in ARC 205.",
                "missing_fields": [],
                "needs_human_review": False,
                "confidence": 0.9,
            },
            valid_buildings=["ARC"],
            valid_priorities=["LOW", "NORMAL", "URGENT"],
        )

        self.assertEqual(result["priority"], "NORMAL")
        self.assertEqual(result["raw_extracted_fields"]["priority"], "urgent phrase")
        self.assertEqual(result["validated_fields"]["priority"], "NORMAL")
        self.assertEqual(result["invalid_code_candidates"]["priority"], "urgent phrase")

    def test_valid_priority_does_not_create_invalid_candidate(self) -> None:
        result = validate_extracted_fields(
            {
                "request_type": "HVAC",
                "building": "ARC",
                "room": "205",
                "priority": "URGENT",
                "summary": "ARC 205 is too hot.",
                "missing_fields": [],
                "needs_human_review": False,
                "confidence": 0.8,
            },
            valid_buildings=["ARC"],
            valid_priorities=["LOW", "NORMAL", "URGENT"],
        )

        self.assertEqual(result["priority"], "URGENT")
        self.assertEqual(result["raw_extracted_fields"]["priority"], "URGENT")
        self.assertEqual(result["validated_fields"]["priority"], "URGENT")
        self.assertNotIn("priority", result["invalid_code_candidates"])


class CodeNormalizerPureFunctionTests(unittest.TestCase):
    def test_skipped_block_is_stable(self) -> None:
        from app.code_normalizer import skipped_code_normalization_block

        block = skipped_code_normalization_block("Skipped because output contract validation failed.")

        self.assertEqual(block["enabled"], False)
        self.assertEqual(block["status"], "skipped")
        self.assertEqual(block["suggestions"], [])
        self.assertEqual(block["applied"], {})
        self.assertEqual(block["rejected"], [])
        self.assertEqual(block["message"], "Skipped because output contract validation failed.")

    def test_failed_block_is_stable(self) -> None:
        from app.code_normalizer import failed_code_normalization_block

        block = failed_code_normalization_block("Model returned invalid JSON")

        self.assertEqual(block["enabled"], True)
        self.assertEqual(block["status"], "failed")
        self.assertIn("Model returned invalid JSON", block["message"])

    def test_context_includes_raw_fields_candidates_and_configured_codes(self) -> None:
        from app.code_normalizer import build_code_normalizer_context

        context = build_code_normalizer_context(
            text="This is urgent.",
            environment_code="DEFAULT",
            result={"priority": "NORMAL", "summary": "Leak."},
            raw_extracted_fields={"priority": "urgent phrase"},
            invalid_code_candidates={"priority": "urgent phrase"},
            code_values={"priorities": [{"code": "URGENT", "label": "Urgent", "aliases": "asap"}]},
        )

        self.assertEqual(context["environment_code"], "DEFAULT")
        self.assertEqual(context["raw_extracted_fields"]["priority"], "urgent phrase")
        self.assertEqual(context["invalid_code_candidates"]["priority"], "urgent phrase")
        self.assertEqual(context["code_values"]["priorities"][0]["code"], "URGENT")
        self.assertLessEqual(len(context["text"]), 500)

    def test_normalize_model_output_rejects_unknown_fields_and_bad_codes(self) -> None:
        from app.code_normalizer import normalize_code_normalizer_output

        normalized = normalize_code_normalizer_output(
            {
                "suggestions": [
                    {"field": "priority", "input_value": "urgent phrase", "suggested_code": "URGENT", "confidence": 0.91, "reason": "Urgent wording."},
                    {"field": "building", "input_value": "arc", "suggested_code": "ARC", "confidence": 0.99, "reason": "Unsupported in v1."},
                    {"field": "priority", "input_value": "urgent phrase", "suggested_code": "NOT_CONFIGURED", "confidence": 0.9, "reason": "Bad code."},
                ]
            },
            enabled_codes_by_field={"priority": {"URGENT", "NORMAL", "LOW"}},
        )

        self.assertEqual(len(normalized["suggestions"]), 1)
        self.assertEqual(normalized["suggestions"][0]["field"], "priority")
        self.assertEqual(normalized["suggestions"][0]["suggested_code"], "URGENT")
        self.assertEqual(len(normalized["rejected"]), 2)

    def test_apply_accepts_configured_high_confidence_invalid_priority(self) -> None:
        from app.code_normalizer import apply_code_normalization_suggestions

        block = apply_code_normalization_suggestions(
            result={"priority": "NORMAL", "summary": "Leak."},
            invalid_code_candidates={"priority": "urgent phrase"},
            normalized_model_output={
                "suggestions": [
                    {"field": "priority", "input_value": "urgent phrase", "suggested_code": "URGENT", "confidence": 0.86, "reason": "Urgent wording."}
                ],
                "rejected": [],
            },
            threshold=0.8,
        )

        self.assertEqual(block["status"], "applied")
        self.assertEqual(block["applied"], {"priority": "URGENT"})
        self.assertEqual(block["suggestions"][0]["decision"], "accepted")

    def test_apply_rejects_low_confidence_and_already_valid_field(self) -> None:
        from app.code_normalizer import apply_code_normalization_suggestions

        low = apply_code_normalization_suggestions(
            result={"priority": "NORMAL"},
            invalid_code_candidates={"priority": "urgent phrase"},
            normalized_model_output={
                "suggestions": [
                    {"field": "priority", "input_value": "urgent phrase", "suggested_code": "URGENT", "confidence": 0.4, "reason": "Weak."}
                ],
                "rejected": [],
            },
            threshold=0.8,
        )
        already_valid = apply_code_normalization_suggestions(
            result={"priority": "URGENT"},
            invalid_code_candidates={},
            normalized_model_output={
                "suggestions": [
                    {"field": "priority", "input_value": "urgent phrase", "suggested_code": "NORMAL", "confidence": 0.9, "reason": "Wrong."}
                ],
                "rejected": [],
            },
            threshold=0.8,
        )

        self.assertEqual(low["status"], "rejected")
        self.assertEqual(low["rejected"][0]["reason_code"], "confidence_below_threshold")
        self.assertEqual(already_valid["rejected"][0]["reason_code"], "field_already_valid")


class CodeNormalizerPromptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_patcher = patch.object(db, "DB_FILE", Path(self.tmp.name) / "test.db")
        self.db_patcher.start()
        db.init_db()

    def tearDown(self) -> None:
        self.db_patcher.stop()
        self.tmp.cleanup()

    def test_code_normalizer_prompt_endpoint_is_supported_and_seeded(self) -> None:
        from app.config import DEFAULT_PROMPT_VERSIONS, SUPPORTED_PROMPT_ENDPOINTS
        from app.prompts import active_prompt_version

        self.assertIn("cmms-code-normalizer", SUPPORTED_PROMPT_ENDPOINTS)
        self.assertIn("cmms-code-normalizer", DEFAULT_PROMPT_VERSIONS)

        row = active_prompt_version("cmms-code-normalizer")

        self.assertEqual(row["endpoint"], "cmms-code-normalizer")
        self.assertEqual(row["status"], "active")
        self.assertIn("/no_think", row["system_prompt"])
        self.assertIn('"suggestions"', row["system_prompt"])


class CodeNormalizerCodeValueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_patcher = patch.object(db, "DB_FILE", Path(self.tmp.name) / "test.db")
        self.db_patcher.start()
        db.init_db()
        seed_default_environment()
        db.db_execute(
            """
            INSERT OR REPLACE INTO code_values
            (environment_code, category, code, label, aliases, metadata_json, source, enabled, created_at, updated_at)
            VALUES ('DEFAULT', 'priorities', 'URGENT', 'Urgent', 'asap', NULL, 'Manual', 1, 'now', 'now')
            """
        )

    def tearDown(self) -> None:
        self.db_patcher.stop()
        self.tmp.cleanup()

    def test_load_code_values_and_enabled_codes_by_field(self) -> None:
        from app.code_normalizer import enabled_codes_by_field, load_code_values_for_normalizer

        values = load_code_values_for_normalizer("DEFAULT")
        codes = enabled_codes_by_field(values)

        self.assertIn("URGENT", {row["code"] for row in values["priorities"]})
        self.assertEqual(codes["priority"], {"LOW", "NORMAL", "URGENT"})


if __name__ == "__main__":
    unittest.main()
