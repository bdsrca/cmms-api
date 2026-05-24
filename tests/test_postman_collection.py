import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
COLLECTION_PATH = ROOT / "docs" / "postman" / "local-cmms-llm-api.postman_collection.json"


class PostmanCollectionTests(unittest.TestCase):
    def collection(self) -> dict:
        return json.loads(COLLECTION_PATH.read_text(encoding="utf-8"))

    def test_collection_has_postman_schema_and_variables(self) -> None:
        collection = self.collection()
        variable_keys = {item["key"] for item in collection["variable"]}

        self.assertEqual(
            collection["info"]["schema"],
            "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        )
        self.assertIn("Local CMMS LLM API", collection["info"]["name"])
        self.assertTrue({"base_url", "llm_api_key", "admin_cookie", "environment_code"} <= variable_keys)

    def test_collection_covers_core_routes(self) -> None:
        collection_text = COLLECTION_PATH.read_text(encoding="utf-8")

        expected_routes = [
            "/health",
            "/ui",
            "/api/me",
            "/api/ai/cmms-intake",
            "/api/ai/intake/email",
            "/api/ai/cmms-assistant",
            "/api/ai/extract-work-order-fields",
            "/api/ai/summarize-work-order",
            "/api/environments",
            "/api/environments/{{environment_code}}/validation-rules",
            "/api/environments/{{environment_code}}/validate-sample",
            "/api/output-contracts/{{endpoint}}",
            "/api/admin/api-keys",
            "/api/admin/environments/{{environment_code}}/codes",
            "/api/admin/output-contracts",
            "/api/admin/workflow-runs",
            "/api/admin/environments/{{environment_code}}/cmms-connector",
        ]
        for route in expected_routes:
            with self.subTest(route=route):
                self.assertIn(route, collection_text)

    def test_collection_has_separate_ai_key_and_admin_cookie_headers(self) -> None:
        collection_text = COLLECTION_PATH.read_text(encoding="utf-8")

        self.assertIn('"key": "x-api-key"', collection_text)
        self.assertIn('"value": "{{llm_api_key}}"', collection_text)
        self.assertIn('"key": "Cookie"', collection_text)
        self.assertIn('"value": "{{admin_cookie}}"', collection_text)


if __name__ == "__main__":
    unittest.main()
