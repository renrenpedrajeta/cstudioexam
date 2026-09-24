import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
import json
from unittest.mock import Mock

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
from llm_pipeline.grounded import (GroundedPlanner, Intent, Interpretation, EditPlan,
                                  FidelityVerdict, quantity_edit)
from llm_pipeline.models import Recipe, Review


class GroundedTests(unittest.TestCase):
    def setUp(self):
        self.recipe = Recipe(recipe_id="test", title="Batter", ingredients=["3/4 cup sugar", "2 eggs"],
                             instructions=["Beat eggs and sugar for 2 minutes."])
        self.review = Review(text="I halved the sugar.", has_modification=True)
        self.intent = Intent(id="sugar", source_quote=self.review.text, action="quantity", timing="performed",
                             target="sugar", amount_mode="multiply", amount="1/2", description="Halve sugar")
        self.planner = GroundedPlanner(SimpleNamespace(client=Mock(), model="mock"))

    def test_exact_fraction_arithmetic_and_units(self):
        self.assertEqual(quantity_edit(self.intent, self.recipe).replace, "3/8 cup sugar")
        egg = self.intent.model_copy(update={"target": "eggs", "amount_mode": "add", "amount": "1", "unit": "count", "source_quote": "I added one egg."})
        self.assertEqual(quantity_edit(egg, self.recipe).replace, "3 eggs")
        subtract = self.intent.model_copy(update={"amount_mode": "subtract", "unit": "cup", "amount": "1/4", "source_quote": "I used 1/4 cup less sugar."})
        self.assertEqual(quantity_edit(subtract, self.recipe).replace, "1/2 cup sugar")
        for changes in [{"unit": "gram", "amount_mode": "absolute"}, {"amount": "0"}, {"amount": "1/0"}]:
            with self.subTest(changes=changes), self.assertRaises((ValueError, ZeroDivisionError)):
                quantity_edit(self.intent.model_copy(update={**changes, "source_quote": "I changed the sugar amount."}), self.recipe)

    def test_ambiguous_sugar_is_not_guessed(self):
        recipe = self.recipe.model_copy(update={"ingredients": ["1 cup white sugar", "1 cup brown sugar"]})
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            quantity_edit(self.intent, recipe)

    def test_quantity_noop_and_mixed_fraction_format(self):
        same = self.intent.model_copy(update={"amount_mode": "absolute", "amount": "3/4", "unit": "cup", "source_quote": "I used 3/4 cup sugar."})
        self.assertIsNone(quantity_edit(same, self.recipe))
        recipe = self.recipe.model_copy(update={"ingredients": ["3 cups sugar"]})
        less = self.intent.model_copy(update={"amount_mode": "subtract", "amount": "1/2", "unit": "cup", "source_quote": "I used 1/2 cup less sugar."})
        self.assertEqual(quantity_edit(less, recipe).replace, "2 1/2 cups sugar")

    def test_unmatched_quote_and_future_misclassification_block_early(self):
        for quote, text in [("not actually in review", self.review.text), ("Next time I will halve sugar.", "Next time I will halve sugar.")]:
            self.planner.request = Mock(return_value=Interpretation(changes=[self.intent.model_copy(update={"source_quote": quote})], unresolved=[]))
            result = self.planner.plan(Review(text=text), self.recipe)
            self.assertEqual(result.status, "needs_review")
            self.assertEqual(self.planner.request.call_count, 1)

    def test_future_only_requires_fidelity_check_before_skip(self):
        future = self.intent.model_copy(update={"source_quote": "Next time I will halve sugar.", "timing": "future"})
        self.planner.request = Mock(side_effect=[Interpretation(changes=[future], unresolved=[]), FidelityVerdict(status="faithful", issues=[])])
        result = self.planner.plan(Review(text=future.source_quote), self.recipe)
        self.assertEqual(result.status, "skipped")
        self.assertIsNone(result.modification)
        self.assertEqual(self.planner.request.call_count, 2)

    def test_success_preserves_grounding_and_calculated_edit(self):
        edit = {**quantity_edit(self.intent, self.recipe).model_dump(), "intent_ids": ["sugar"]}
        self.planner.request = Mock(side_effect=[Interpretation(changes=[self.intent], unresolved=[]),
                                               EditPlan(edits=[edit]), FidelityVerdict(status="faithful", issues=[])])
        result = self.planner.plan(self.review, self.recipe)
        self.assertEqual(result.status, "ready")
        self.assertEqual(result.modification.edits[0].replace, "3/8 cup sugar")
        self.assertEqual(result.edit_sources, [["sugar"]])

    def test_python_inserts_quantity_when_model_omits_it(self):
        self.planner.request = Mock(side_effect=[Interpretation(changes=[self.intent], unresolved=[]),
            EditPlan(edits=[]), FidelityVerdict(status="faithful", issues=[])])
        result = self.planner.plan(self.review, self.recipe)
        self.assertEqual(result.status, "ready")
        self.assertEqual(result.modification.edits[0].replace, "3/8 cup sugar")

    def test_quantity_only_generic_instructions_need_no_generated_edits(self):
        recipe = self.recipe.model_copy(update={"instructions": ["Beat eggs and sugar."]})
        self.planner.request = Mock(side_effect=[Interpretation(changes=[self.intent], unresolved=[]),
            FidelityVerdict(status="faithful", issues=[])])
        result = self.planner.plan(self.review, recipe)
        self.assertEqual(result.status, "ready")
        self.assertEqual([call.args[0] for call in self.planner.request.call_args_list], ["interpret", "fidelity"])

    def test_unchanged_quantity_is_not_sent_as_actionable_to_auditor(self):
        review = Review(text="I used 3/4 cup sugar.")
        same = self.intent.model_copy(update={"source_quote": review.text, "amount_mode": "absolute", "amount": "3/4", "unit": "cup"})
        self.planner.request = Mock(side_effect=[Interpretation(changes=[same], unresolved=[]),
            FidelityVerdict(status="faithful", issues=[])])
        result = self.planner.plan(review, self.recipe)
        self.assertEqual(result.status, "skipped")
        data = self.planner.request.call_args.args[2]
        self.assertNotIn("performed_changes", data)
        self.assertNotIn("plan", data)
        self.assertEqual(data["review"], review.text)
        self.assertEqual(data["candidate"], self.recipe.model_dump())

    def test_altered_calculation_is_rejected_after_one_repair(self):
        bad = EditPlan(edits=[{"target": "ingredients", "find": "3/8 cup sugar", "replace": "1/4 cup sugar", "intent_ids": ["sugar"]}])
        self.planner.request = Mock(side_effect=[Interpretation(changes=[self.intent], unresolved=[]), bad, bad])
        result = self.planner.plan(self.review, self.recipe)
        self.assertEqual(result.status, "needs_review")
        self.assertIsNone(result.modification)
        self.assertEqual([call.args[0] for call in self.planner.request.call_args_list], ["interpret", "edits", "repair"])

    def test_unrelated_intent_reference_is_rejected(self):
        edit = {**quantity_edit(self.intent, self.recipe).model_dump(), "intent_ids": ["unsupported"]}
        self.planner.request = Mock(side_effect=[Interpretation(changes=[self.intent], unresolved=[]), EditPlan(edits=[edit]), EditPlan(edits=[edit])])
        self.assertEqual(self.planner.plan(self.review, self.recipe).status, "needs_review")

    def test_historical_complex_failures_are_repaired_and_revalidated(self):
        from llm_pipeline.recipe_modifier import RecipeModifier
        from llm_pipeline.dependencies import dependency_issues
        report = json.loads((Path(__file__).resolve().parents[1] / "evaluation/grounded-verified.json").read_text(encoding="utf-8"))
        for case in report["cases"]:
            if case["id"] not in {"cookie_cinnamon", "cookie_numbered"}:
                continue
            with self.subTest(case=case["id"]):
                outcome = case["outcome"]
                recipe = Recipe.model_validate(outcome["original"])
                interpretation = Interpretation.model_validate(outcome["planning"]["interpretation"])
                bad = EditPlan.model_validate_json(next(call["raw_output"] for call in outcome["planning"]["calls"] if call["stage"] == "edits"))
                fixed = bad.model_copy(deep=True)
                if case["id"] == "cookie_cinnamon":
                    fixed.edits[-1].replace = "Stir in 2 1/2 cups all-purpose flour, a tiny dash of cinnamon, chocolate chips, and walnuts."
                    fixed.edits[-1].intent_ids.append("4")
                else:
                    fixed.edits[1].replace = "Add baking soda and salt to the batter."
                    fixed.edits[-1].operation = "replace"
                    fixed.edits[-1].replace = "Refrigerate the batter for at least an hour. " + fixed.edits[-1].find
                    fixed.edits[-1].add = None
                self.planner.request = Mock(side_effect=[interpretation, bad, fixed, FidelityVerdict(status="faithful", issues=[])])
                result = self.planner.plan(Review.model_validate(outcome["source_review"]), recipe)
                self.assertEqual(result.status, "ready", result.issues)
                self.assertTrue(result.repair_feedback)
                self.assertEqual([call.args[0] for call in self.planner.request.call_args_list], ["interpret", "edits", "repair", "fidelity"])
                candidate = RecipeModifier().apply_modification(recipe, result.modification)
                self.assertEqual(dependency_issues(recipe, candidate, interpretation.changes), [])
                if case["id"] == "cookie_numbered":
                    self.assertIn("1/2 cup white sugar", candidate.recipe.ingredients)
                    self.assertIn("1 1/2 cup packed brown sugar", candidate.recipe.ingredients)
                    text = " ".join(candidate.recipe.instructions)
                    self.assertLess(text.index("Refrigerate"), text.index("Drop spoonfuls"))
                self.assertEqual(recipe.model_dump(), outcome["original"])

    def test_failed_repair_keeps_original_unpublished_in_workflow(self):
        from llm_pipeline.workflow import enhance_review
        bad = EditPlan(edits=[{"target": "ingredients", "find": "3/8 cup sugar", "replace": "1/4 cup sugar", "intent_ids": ["sugar"]}])
        self.planner.request = Mock(side_effect=[Interpretation(changes=[self.intent], unresolved=[]), bad, bad])
        result = enhance_review(self.recipe, self.review, SimpleNamespace(plan_review=self.planner.plan))
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["result"].recipe, self.recipe)
        self.assertEqual(result["result"].changes, [])
        self.assertIsNone(result["enhanced_recipe"])

    def test_fidelity_rejection_gets_one_repair_and_fresh_audit(self):
        self.planner.request = Mock(side_effect=[Interpretation(changes=[self.intent], unresolved=[]), EditPlan(edits=[]),
            FidelityVerdict(status="needs_review", issues=["Check source coverage"]), EditPlan(edits=[]),
            FidelityVerdict(status="faithful", issues=[])])
        result = self.planner.plan(self.review, self.recipe)
        self.assertEqual(result.status, "ready")
        self.assertEqual([call.args[0] for call in self.planner.request.call_args_list], ["interpret", "edits", "fidelity", "repair", "fidelity"])

    def test_fidelity_failure_catches_unmodeled_source_changes(self):
        self.planner.request = Mock(side_effect=[Interpretation(changes=[], unresolved=[]),
                                               FidelityVerdict(status="needs_review", issues=["Sugar change was omitted"])])
        result = self.planner.plan(self.review, self.recipe)
        self.assertEqual(result.status, "needs_review")
        self.assertIsNone(result.modification)

    def test_provider_failure_is_not_a_skip(self):
        self.planner.request = Mock(side_effect=TimeoutError("provider details"))
        result = self.planner.plan(self.review, self.recipe)
        self.assertEqual(result.status, "failed")
        self.assertNotIn("provider details", str(result.issues))

    def test_schema_repair_is_bounded_and_preserves_valid_result(self):
        invalid = {"changes": [], "unresolved": [], "unexpected": True}
        valid = {"changes": [], "unresolved": []}
        def response(data):
            return SimpleNamespace(usage=None, choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=json.dumps(data)))])
        call = self.planner.client.with_options.return_value.chat.completions.create
        call.side_effect = [response(invalid), response(valid)]
        result = self.planner.request("interpret", "rules", {}, Interpretation)
        self.assertEqual(result.changes, [])
        self.assertEqual(call.call_count, 2)
        self.assertEqual(len(self.planner.calls), 2)
        call.reset_mock()
        call.side_effect = [response(invalid), response(invalid)]
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            self.planner.request("interpret", "rules", {}, Interpretation)
        self.assertEqual(call.call_count, 2)

    def test_halving_source_overrides_incorrect_subtraction_interpretation(self):
        mistaken = self.intent.model_copy(update={"amount_mode": "subtract", "amount": "1/2", "unit": "cup"})
        self.assertEqual(quantity_edit(mistaken, self.recipe).replace, "3/8 cup sugar")
