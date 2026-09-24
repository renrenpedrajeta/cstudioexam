import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
from llm_pipeline.models import ModificationObject, Review
from llm_pipeline.grounded import PlanningResult
from llm_pipeline.pipeline import LLMAnalysisPipeline
from llm_pipeline.consistency import ConsistencyCheck


class PipelineReplacementTests(unittest.TestCase):
    def test_failed_replacement_never_generates_or_saves(self):
        for find, replacement in [("1 cup White Sugar", "0.5 cup white sugar"),
                                  ("1 cup white sugar", "1 cup white sugar")]:
            with self.subTest(find=find), TemporaryDirectory() as output_dir:
                with patch("llm_pipeline.pipeline.TweakExtractor") as extractor:
                    pipeline = LLMAnalysisPipeline(output_dir=output_dir)
                    extractor.return_value.plan_review.side_effect = lambda *_: PlanningResult(
                        status="ready", modification=extractor.return_value.extract_single_modification.return_value[0])
                    extractor.return_value.extract_single_modification.return_value = (
                        ModificationObject(modification_type="quantity_adjustment", reasoning="Test", edits=[
                            {"target": "ingredients", "find": find, "replace": replacement}]),
                        Review(text="Halve the sugar", has_modification=True),
                    )
                    pipeline.load_recipe_data = Mock(return_value={
                        "recipe_id": "test", "title": "Fixture", "ingredients": ["1 cup white sugar"],
                        "instructions": [], "reviews": [{"text": "Halve the sugar", "has_modification": True}],
                    })
                    pipeline.enhanced_generator = Mock()
                    self.assertIsNone(pipeline.process_single_recipe("controlled", save_output=True))
                    pipeline.enhanced_generator.generate_enhanced_recipe.assert_not_called()
                    pipeline.enhanced_generator.save_enhanced_recipe.assert_not_called()
                    self.assertEqual(list(Path(output_dir).iterdir()), [])

    def test_successful_replacement_has_real_change_record(self):
        with TemporaryDirectory() as output_dir, patch("llm_pipeline.pipeline.TweakExtractor") as extractor, patch(
            "llm_pipeline.consistency.check_consistency", return_value=ConsistencyCheck(status="consistent")
        ):
            pipeline = LLMAnalysisPipeline(output_dir=output_dir)
            extractor.return_value.plan_review.side_effect = lambda *_: PlanningResult(
                status="ready", modification=extractor.return_value.extract_single_modification.return_value[0])
            extractor.return_value.extract_single_modification.return_value = (
                ModificationObject(modification_type="quantity_adjustment", reasoning="Less sugar", edits=[
                    {"target": "ingredients", "find": "1 cup sugar", "replace": "0.5 cup sugar"}]),
                Review(text="I halved the sugar", has_modification=True),
            )
            pipeline.load_recipe_data = Mock(return_value={
                "recipe_id": "test", "title": "Fixture", "ingredients": ["1 cup sugar"],
                "instructions": [], "reviews": [{"text": "I halved the sugar", "has_modification": True}],
            })
            result = pipeline.process_single_recipe("controlled", save_output=False)
            self.assertIsNotNone(result)
            self.assertEqual(result.ingredients, ["0.5 cup sugar"])
            self.assertEqual(result.enhancement_summary.total_changes, 1)
            record = result.modifications_applied[0].changes_made[0]
            self.assertEqual((record.from_text, record.to_text), ("1 cup sugar", "0.5 cup sugar"))

    def test_inconsistent_recipe_is_not_generated_or_saved(self):
        with TemporaryDirectory() as output_dir, patch("llm_pipeline.pipeline.TweakExtractor") as extractor, patch(
            "llm_pipeline.consistency.check_consistency",
            return_value=ConsistencyCheck(status="inconsistent", issues=["Walnuts remain in preparation"])
        ):
            pipeline = LLMAnalysisPipeline(output_dir=output_dir)
            extractor.return_value.plan_review.side_effect = lambda *_: PlanningResult(
                status="ready", modification=extractor.return_value.extract_single_modification.return_value[0])
            extractor.return_value.extract_single_modification.return_value = (
                ModificationObject(modification_type="removal", reasoning="Omit walnuts", edits=[
                    {"target": "ingredients", "operation": "remove", "find": "1 cup walnuts"}]),
                Review(text="I omitted walnuts.", has_modification=True),
            )
            pipeline.load_recipe_data = Mock(return_value={
                "recipe_id": "test", "title": "Fixture", "ingredients": ["1 cup walnuts"],
                "instructions": ["Mix in walnuts."], "reviews": [{"text": "I omitted walnuts.", "has_modification": True}],
            })
            pipeline.enhanced_generator = Mock()
            self.assertIsNone(pipeline.process_single_recipe("controlled", save_output=True))
            pipeline.enhanced_generator.generate_enhanced_recipe.assert_not_called()
            pipeline.enhanced_generator.save_enhanced_recipe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
