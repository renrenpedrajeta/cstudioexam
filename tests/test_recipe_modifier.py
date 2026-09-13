import sys
import unittest
from pathlib import Path

from pydantic import ValidationError

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
from llm_pipeline.models import ModificationEdit, ModificationObject, Recipe
from llm_pipeline.recipe_modifier import EditApplicationError, RecipeModifier


class ReplacementTests(unittest.TestCase):
    def setUp(self):
        self.modifier = RecipeModifier()

    def edit(self, find, replacement, target="ingredients"):
        return ModificationEdit(target=target, find=find, replace=replacement)

    def test_exact_line(self):
        original = ["1 cup white sugar", "2 eggs"]
        result, records = self.modifier.apply_edit(
            self.edit(original[0], "0.5 cup white sugar"), original
        )
        self.assertEqual(result, ["0.5 cup white sugar", "2 eggs"])
        self.assertEqual(original, ["1 cup white sugar", "2 eggs"])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].from_text, original[0])
        self.assertEqual(records[0].to_text, result[0])

    def test_substring_preserves_instruction(self):
        original = ["Bake for 10 minutes, then cool on a rack."]
        result, records = self.modifier.apply_edit(
            self.edit("10 minutes", "8 minutes", "instructions"), original
        )
        self.assertEqual(result, ["Bake for 8 minutes, then cool on a rack."])
        self.assertEqual(records[0].type, "instruction")

    def test_whole_line_takes_priority(self):
        result, _ = self.modifier.apply_edit(
            self.edit("1 cup sugar", "0.5 cup sugar"),
            ["1 cup sugar", "Mix 1 cup sugar with flour."],
        )
        self.assertEqual(result, ["0.5 cup sugar", "Mix 1 cup sugar with flour."])

    def test_rejected_replacements(self):
        cases = [
            (["1 cup white sugar"], "1 cup White Sugar", "0.5 cup white sugar", "target_not_found"),
            (["1 cup white sugar"], "1 cup sugar", "0.5 cup sugar", "target_not_found"),
            (["1 cup sugar", "1 cup sugar"], "1 cup sugar", "0.5 cup sugar", "ambiguous_target"),
            (["Mix sugar", "Add sugar"], "sugar", "honey", "ambiguous_target"),
            (["sugar and sugar"], "sugar", "honey", "ambiguous_target"),
            (["aaa"], "aa", "b", "ambiguous_target"),
            (["1 cup sugar"], "1 cup sugar", "1 cup sugar", "no_change"),
        ]
        for lines, find, replacement, reason in cases:
            with self.subTest(lines=lines, find=find):
                before = list(lines)
                with self.assertRaisesRegex(EditApplicationError, reason):
                    self.modifier.apply_edit(self.edit(find, replacement), lines)
                self.assertEqual(lines, before)

    def test_invalid_edit_fields(self):
        for replacement in [None, "", "   "]:
            with self.subTest(replacement=replacement):
                with self.assertRaises(ValidationError):
                    self.edit("1 cup sugar", replacement)
        with self.assertRaises(ValidationError):
            self.edit("   ", "sugar")
        with self.assertRaises(ValidationError):
            ModificationEdit(target="ingredients", operation="add_after", find="sugar")

    def test_failed_plan_rolls_back(self):
        recipe = Recipe(recipe_id="test", title="Fixture", ingredients=["1 cup sugar"], instructions=[])
        for failed in [self.edit("missing", "replacement"),
                       ModificationEdit(target="instructions", operation="remove", find="missing")]:
            with self.subTest(failed=failed):
                plan = ModificationObject(modification_type="quantity_adjustment", reasoning="Test", edits=[
                    self.edit("1 cup sugar", "0.5 cup sugar"), failed,
                ])
                result = self.modifier.apply_modification(recipe, plan)
                self.assertEqual(result.status, "failed")
                self.assertEqual(result.reason, "target_not_found")
                self.assertEqual(result.failed_edit, failed)
                self.assertEqual(result.recipe, recipe)
                self.assertEqual(result.changes, [])
                self.assertEqual(recipe.ingredients, ["1 cup sugar"])

    def test_empty_and_reversing_plans_are_not_enhancements(self):
        recipe = Recipe(recipe_id="test", title="Fixture", ingredients=["1 cup sugar"], instructions=[])
        for edits, reason in [([], "no_edits"), ([
            self.edit("1 cup sugar", "0.5 cup sugar"),
            self.edit("0.5 cup sugar", "1 cup sugar"),
        ], "no_change")]:
            with self.subTest(reason=reason):
                result = self.modifier.apply_modification(recipe, ModificationObject(
                    modification_type="quantity_adjustment", reasoning="Test", edits=edits))
                self.assertEqual(result.reason, reason)
                self.assertEqual(result.status, "failed")
                self.assertEqual(result.changes, [])

    def test_batch_uses_application_results(self):
        recipe = Recipe(recipe_id="test", title="Fixture", ingredients=["1 cup sugar"], instructions=[])
        plan = ModificationObject(modification_type="quantity_adjustment", reasoning="Test",
                                  edits=[self.edit("1 cup sugar", "0.5 cup sugar")])
        result, records = self.modifier.apply_modifications_batch(recipe, [plan])
        self.assertEqual(result.ingredients, ["0.5 cup sugar"])
        self.assertEqual(len(records[0]), 1)
        with self.assertRaisesRegex(EditApplicationError, "target_not_found"):
            self.modifier.apply_modifications_batch(recipe, [plan, plan])

    def test_insert_and_remove_require_unique_whole_lines(self):
        for operation in ["add_after", "remove"]:
            for lines, target, reason in [
                (["1 cup white sugar", "1 cup brown sugar"], "1 cup sugar", "target_not_found"),
                (["1 cup sugar", "1 cup sugar"], "1 cup sugar", "ambiguous_target"),
                (["1 cup sugar"], "1 cup Sugar", "target_not_found"),
                (["Mix flour, sugar, and walnuts."], "sugar, and walnuts.", "target_not_found"),
            ]:
                with self.subTest(operation=operation, target=target):
                    edit = ModificationEdit(target="ingredients", operation=operation,
                                            find=target, add="1 egg" if operation == "add_after" else None)
                    original = list(lines)
                    with self.assertRaisesRegex(EditApplicationError, reason):
                        self.modifier.apply_edit(edit, lines)
                    self.assertEqual(lines, original)

    def test_exact_insertion_and_removal_preserve_other_lines(self):
        original = ["1 cup flour", "1 cup walnuts"]
        inserted, records = self.modifier.apply_edit(ModificationEdit(
            target="ingredients", operation="add_after", find="1 cup flour", add="1 egg"), original)
        self.assertEqual(inserted, ["1 cup flour", "1 egg", "1 cup walnuts"])
        self.assertEqual((records[0].from_text, records[0].to_text), ("", "1 egg"))
        removed, records = self.modifier.apply_edit(ModificationEdit(
            target="ingredients", operation="remove", find="1 cup walnuts"), inserted)
        self.assertEqual(removed, ["1 cup flour", "1 egg"])
        self.assertEqual((records[0].from_text, records[0].to_text), ("1 cup walnuts", ""))
        self.assertEqual(original, ["1 cup flour", "1 cup walnuts"])

    def test_dependent_nut_removal_preserves_instruction_actions(self):
        recipe = Recipe(recipe_id="nuts", title="Cookies", ingredients=["1 cup walnuts", "1 cup flour"],
                        instructions=["Mix flour and walnuts. Bake for 10 minutes."])
        plan = ModificationObject(modification_type="removal", reasoning="Omit nuts", edits=[
            ModificationEdit(target="ingredients", operation="remove", find="1 cup walnuts"),
            self.edit("Mix flour and walnuts.", "Mix flour.", "instructions"),
        ])
        result = self.modifier.apply_modification(recipe, plan)
        self.assertEqual(result.status, "applied")
        self.assertEqual(result.recipe.ingredients, ["1 cup flour"])
        self.assertEqual(result.recipe.instructions, ["Mix flour. Bake for 10 minutes."])


if __name__ == "__main__":
    unittest.main()
