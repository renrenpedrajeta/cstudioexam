import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
from llm_pipeline.consistency import check_consistency, enforce_consistency, explicit_change_issues
from llm_pipeline.models import ChangeRecord, ModificationResult, Recipe


class ConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.original = Recipe(recipe_id="fixture", title="Batter", ingredients=["1 cup walnuts"], instructions=["Mix in walnuts."])
        self.candidate = ModificationResult(status="applied", recipe=self.original.model_copy(update={"ingredients": []}))
        self.client = Mock()
        self.call = self.client.with_options.return_value.chat.completions.create

    def respond(self, payload, finish_reason="stop"):
        self.call.return_value = SimpleNamespace(choices=[SimpleNamespace(
            finish_reason=finish_reason, message=SimpleNamespace(content=payload))])

    def test_bad_or_incomplete_verdicts_block(self):
        for payload, finish in [
            ('{"status":"consistent","issues":[]}', "length"),
            ("not json", "stop"),
            ('{"status":"consistent","issues":["Walnuts remain"]}', "stop"),
            ('{"status":"inconsistent","issues":[]}', "stop"),
            ('{"status":"consistent","unexpected":true}', "stop"),
        ]:
            with self.subTest(payload=payload, finish=finish):
                self.respond(payload, finish)
                report = check_consistency(self.client, "mock", self.original, self.candidate)
                self.assertEqual(report.status, "unverified")

    def test_provider_failure_blocks_without_leaking_error(self):
        self.call.side_effect = RuntimeError("sensitive provider detail")
        report = check_consistency(self.client, "mock", self.original, self.candidate)
        self.assertEqual(report.status, "unverified")
        self.assertNotIn("sensitive", str(report.issues))
        self.assertEqual(self.call.call_count, 1)

    def test_consistent_verdict_preserves_candidate(self):
        self.respond(json.dumps({"status": "consistent", "issues": []}))
        result, report = enforce_consistency(self.original, self.candidate, SimpleNamespace(client=self.client, model="mock"))
        self.assertEqual(report.status, "consistent")
        self.assertEqual(result, self.candidate)

    def test_inconsistent_verdict_returns_original(self):
        self.respond(json.dumps({"status": "inconsistent", "issues": ["Walnuts remain in preparation."]}))
        result, report = enforce_consistency(self.original, self.candidate, SimpleNamespace(client=self.client, model="mock"))
        self.assertEqual(report.status, "inconsistent")
        self.assertEqual(result.reason, "recipe_inconsistent")
        self.assertEqual(result.recipe, self.original)
        self.assertEqual(result.changes, [])

    def test_failed_edits_do_not_call_model(self):
        failed = ModificationResult(status="failed", recipe=self.original, reason="no_edits")
        result, report = enforce_consistency(self.original, failed, SimpleNamespace(client=self.client, model="mock"))
        self.assertEqual(result, failed)
        self.assertIsNone(report)
        self.client.with_options.assert_not_called()

    def test_removed_water_and_added_cream_block_without_model(self):
        candidate = ModificationResult(status="applied", recipe=self.original.model_copy(update={
            "ingredients": ["1 teaspoon baking soda", "1 teaspoon cream of tartar"],
            "instructions": ["Dissolve baking soda in hot water. Add to batter."],
        }), changes=[
            ChangeRecord(type="ingredient", operation="remove", from_text="2 teaspoons hot water", to_text=""),
            ChangeRecord(type="ingredient", operation="add", from_text="", to_text="1 teaspoon cream of tartar"),
        ])
        report = check_consistency(self.client, "mock", self.original, candidate)
        self.assertEqual(report.status, "inconsistent")
        self.assertEqual(len(report.issues), 2)
        self.client.with_options.assert_not_called()

    def test_removed_nuts_with_updated_step_does_not_trigger_lexical_rejection(self):
        candidate = ModificationResult(status="applied", recipe=self.original.model_copy(update={
            "ingredients": ["1 cup flour"], "instructions": ["Mix flour into the batter."],
        }), changes=[ChangeRecord(type="ingredient", operation="remove", from_text="1 cup chopped walnuts", to_text="")])
        self.assertEqual(explicit_change_issues(candidate), [])

    def test_collective_preparation_is_left_to_audit(self):
        candidate = ModificationResult(status="applied", recipe=self.original.model_copy(update={
            "ingredients": ["1 teaspoon cinnamon"], "instructions": ["Mix all ingredients."],
        }), changes=[ChangeRecord(type="ingredient", operation="add", from_text="", to_text="1 teaspoon cinnamon")])
        self.assertEqual(explicit_change_issues(candidate), [])
        self.respond(json.dumps({"status": "consistent", "issues": []}))
        self.assertEqual(check_consistency(self.client, "mock", self.original, candidate).status, "consistent")
        self.assertEqual(self.call.call_count, 1)
