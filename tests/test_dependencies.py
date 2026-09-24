import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
from llm_pipeline.dependencies import dependency_issues
from llm_pipeline.models import Recipe, ModificationResult


class DependencyTests(unittest.TestCase):
    def test_qualitative_amount_preserves_tiny(self):
        original = Recipe(recipe_id="x", title="Batter", ingredients=["1 cup flour"], instructions=["Mix flour."])
        intent = SimpleNamespace(action="add", target="cinnamon", source_quote="I added a tiny dash of cinnamon.")
        for amount, blocked in [("1 dash", True), ("1 teaspoon", True), ("a tiny dash of", False)]:
            candidate = ModificationResult(status="applied", recipe=original.model_copy(update={
                "ingredients": original.ingredients + [amount + " cinnamon"], "instructions": ["Mix flour and cinnamon."]}))
            self.assertEqual(bool(dependency_issues(original, candidate, [intent])), blocked)

    def test_removing_medium_must_not_leave_incomplete_dissolve_step(self):
        original = Recipe(recipe_id="x", title="Batter", ingredients=["1 teaspoon baking soda", "2 teaspoons water"],
                          instructions=["Dissolve baking soda in water."])
        intent = SimpleNamespace(action="remove", source_quote="I omitted water.")
        for step, blocked in [("Dissolve baking soda.", True), ("Mix baking soda into the batter.", False)]:
            candidate = ModificationResult(status="applied", recipe=original.model_copy(update={
                "ingredients": ["1 teaspoon baking soda"], "instructions": [step]}))
            self.assertEqual(bool(dependency_issues(original, candidate, [intent])), blocked)

    def test_chilling_order_checks_actual_steps_not_before_word(self):
        original = Recipe(recipe_id="x", title="Dough", ingredients=[], instructions=["Scoop dough.", "Bake for 10 minutes."])
        intent = SimpleNamespace(action="technique", source_quote="I chilled the dough before scooping and baking.")
        for steps, blocked in [
            (["Scoop dough.", "Chill dough before scooping and baking.", "Bake for 10 minutes."], True),
            (["Chill dough.\nScoop dough.", "Bake for 10 minutes."], False),
            (["Chill dough, then scoop dough.", "Bake for 10 minutes."], False),
        ]:
            candidate = ModificationResult(status="applied", recipe=original.model_copy(update={"instructions": steps}))
            self.assertEqual(bool(dependency_issues(original, candidate, [intent])), blocked)
