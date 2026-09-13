import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
from api import create_app, get_extractor
from llm_pipeline.models import ModificationObject
from llm_pipeline.consistency import ConsistencyCheck


class ApiTests(unittest.TestCase):
    def setUp(self):
        audit_patch = patch("llm_pipeline.consistency.check_consistency",
                            return_value=ConsistencyCheck(status="consistent"))
        self.audit = audit_patch.start()
        self.addCleanup(audit_patch.stop)
        self.app = create_app()
        self.extractor = Mock()
        self.app.dependency_overrides[get_extractor] = lambda: self.extractor
        self.client = TestClient(self.app)
        self.plan = {"modification_type": "quantity_adjustment", "reasoning": "Less sugar",
                     "edits": [{"target": "ingredients", "operation": "replace",
                                "find": "1 cup white sugar", "replace": "0.5 cup white sugar"}]}

    def tearDown(self):
        self.client.close()

    def test_catalog_and_unknown_recipe(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(len(self.client.get("/recipes").json()["recipes"]), 6)
        detail = self.client.get("/recipes/10813").json()
        self.assertEqual(detail["reviews"][0]["review_index"], 0)
        self.assertEqual(self.client.get("/recipes/unknown").status_code, 404)
        self.extractor.extract_modification.assert_not_called()

    def test_preview_and_noop_rejection(self):
        response = self.client.post("/recipes/10813/preview", json=self.plan)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"]["recipe"]["ingredients"][1], "0.5 cup white sugar")
        self.plan["edits"][0]["find"] = "1 cup White Sugar"
        rejected = self.client.post("/recipes/10813/preview", json=self.plan).json()
        self.assertEqual(rejected["result"]["reason"], "target_not_found")
        self.assertEqual(rejected["result"]["changes"], [])
        self.assertEqual(rejected["original"], rejected["result"]["recipe"])
        self.extractor.extract_modification.assert_not_called()

    def test_live_success_with_mock_provider(self):
        self.extractor.extract_modification.return_value = ModificationObject(**self.plan)
        response = self.client.post("/recipes/10813/enhance", json={"review_text": "I halved the white sugar."})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "applied")
        self.assertEqual(body["enhanced_recipe"]["enhancement_summary"]["total_changes"], 1)
        self.assertEqual(body["source_review"]["text"], "I halved the white sugar.")

    def test_live_rejection_not_published(self):
        self.plan["edits"][0]["find"] = "1 cup White Sugar"
        self.extractor.extract_modification.return_value = ModificationObject(**self.plan)
        body = self.client.post("/recipes/10813/enhance", json={"review_index": 0}).json()
        self.assertEqual(body["status"], "failed")
        self.assertIsNone(body["enhanced_recipe"])
        self.assertEqual(body["result"]["changes"], [])
        self.audit.assert_not_called()

    def test_inconsistency_withholds_enhancement_and_changes(self):
        self.extractor.extract_modification.return_value = ModificationObject(**self.plan)
        for status, reason in [("inconsistent", "recipe_inconsistent"), ("unverified", "consistency_unverified")]:
            with self.subTest(status=status):
                self.audit.return_value = ConsistencyCheck(status=status, issues=["Preparation cannot be verified"])
                body = self.client.post("/recipes/10813/enhance", json={"review_index": 0}).json()
                self.assertEqual(body["status"], "failed")
                self.assertEqual(body["result"]["reason"], reason)
                self.assertIsNone(body["enhanced_recipe"])
                self.assertEqual(body["original"], body["result"]["recipe"])
                self.assertEqual(body["result"]["changes"], [])
                self.assertEqual(body["consistency_check"]["status"], status)

    def test_validate_endpoint_and_preview_scope(self):
        self.audit.return_value = ConsistencyCheck(status="inconsistent", issues=["Missing mixing step"])
        body = self.client.post("/recipes/10813/validate", json=self.plan).json()
        self.assertEqual(body["result"]["reason"], "recipe_inconsistent")
        self.audit.reset_mock()
        body = self.client.post("/recipes/10813/preview", json=self.plan).json()
        self.assertEqual(body["consistency_check"]["status"], "not_checked")
        self.audit.assert_not_called()

    def test_validation_and_missing_review(self):
        for body in [{}, {"review_index": -1}, {"review_index": 0, "review_text": "x"}, {"review_text": " "}]:
            self.assertEqual(self.client.post("/recipes/10813/enhance", json=body).status_code, 422)
        self.assertEqual(self.client.post("/recipes/284494/enhance", json={"review_index": 0}).status_code, 404)
        self.plan["edits"][0].pop("replace")
        self.assertEqual(self.client.post("/recipes/10813/preview", json=self.plan).status_code, 422)
        self.extractor.extract_modification.assert_not_called()

    def test_provider_failure(self):
        self.extractor.extract_modification.return_value = None
        response = self.client.post("/recipes/10813/enhance", json={"review_index": 0})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"]["code"], "extraction_failed")

    def test_key_missing_only_blocks_live_endpoint(self):
        self.app.dependency_overrides.clear()
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(self.client.get("/health").json()["api_key_configured"])
            self.assertEqual(self.client.post("/recipes/10813/enhance", json={"review_index": 0}).status_code, 503)
            self.assertEqual(self.client.post("/recipes/10813/preview", json=self.plan).status_code, 200)


if __name__ == "__main__":
    unittest.main()
