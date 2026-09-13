import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
from llm_pipeline.models import Recipe, Review
from llm_pipeline.tweak_extractor import TweakExtractor


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.extractor = TweakExtractor.__new__(TweakExtractor)
        self.extractor.client = Mock()
        self.extractor.model = "mock"
        self.recipe = Recipe(recipe_id="fixture", title="Batter", ingredients=["2 eggs", "1 cup sugar"], instructions=[])
        self.review = Review(text="I used 3 eggs and half the sugar.", has_modification=True)
        self.plan = {"modification_type": "quantity_adjustment", "reasoning": "Reported quantities", "edits": [
            {"target": "ingredients", "find": "2 eggs", "replace": "3 eggs"},
            {"target": "ingredients", "find": "1 cup sugar", "replace": "0.5 cup sugar"},
        ]}

    def response(self, content, finish_reason="stop"):
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish_reason,
                                                       message=SimpleNamespace(content=json.dumps(content)))])

    def test_multiple_edits_survive_parsing(self):
        self.extractor.client.chat.completions.create.return_value = self.response(self.plan)
        result = self.extractor.extract_modification(self.review, self.recipe, max_retries=0)
        self.assertEqual(len(result.edits), 2)
        self.assertEqual(result.edits[1].replace, "0.5 cup sugar")

    def test_incomplete_response_never_applied_even_if_json_parses(self):
        self.extractor.client.chat.completions.create.return_value = self.response(self.plan, "length")
        self.assertIsNone(self.extractor.extract_modification(self.review, self.recipe, max_retries=0))
        self.assertEqual(self.extractor.client.chat.completions.create.call_count, 1)

    def test_invalid_payload_retry_is_bounded(self):
        self.plan["edits"][0].pop("replace")
        self.extractor.client.chat.completions.create.return_value = self.response(self.plan)
        self.assertIsNone(self.extractor.extract_modification(self.review, self.recipe, max_retries=1))
        self.assertEqual(self.extractor.client.chat.completions.create.call_count, 2)
