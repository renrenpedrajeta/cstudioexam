"""
Step 2: Recipe Modification

This module applies structured modifications to recipes using search-and-replace operations.
It takes ModificationObject instances and applies their edits to recipe ingredients and instructions.
"""

import copy
from typing import List, Tuple

from loguru import logger

from .models import (
    ModificationObject,
    ModificationEdit,
    Recipe,
    ChangeRecord,
    ModificationResult,
)


class EditApplicationError(ValueError):
    """An edit cannot be applied without guessing or producing a no-op."""


class RecipeModifier:
    """Applies structured modifications to recipes using search-and-replace operations."""

    @staticmethod
    def resolve_line(target: str, lines: List[str]) -> int:
        """Insertion anchors and removals must identify one entire line exactly."""
        matches = [index for index, line in enumerate(lines) if line == target]
        if not matches:
            raise EditApplicationError("target_not_found")
        if len(matches) > 1:
            raise EditApplicationError("ambiguous_target")
        return matches[0]

    def apply_edit(
        self,
        edit: ModificationEdit,
        recipe_content: List[str]
    ) -> Tuple[List[str], List[ChangeRecord]]:
        """
        Apply a single edit to a recipe content list.

        Args:
            edit: The edit operation to apply
            recipe_content: List of ingredients or instructions

        Returns:
            Tuple of (modified_content, change_records)
        """
        modified_content = copy.deepcopy(recipe_content)
        change_records = []

        logger.debug(f"Applying {edit.operation} edit: find='{edit.find}'")

        if edit.operation == "replace":
            index, start, end = self.resolve_replacement(edit.find, modified_content)
            original_text = modified_content[index]
            new_text = original_text[:start] + edit.replace + original_text[end:]
            if new_text == original_text:
                raise EditApplicationError("no_change")
            modified_content[index] = new_text
            change_records.append(ChangeRecord(
                type="ingredient" if edit.target == "ingredients" else "instruction",
                from_text=original_text,
                to_text=new_text,
                operation="replace",
            ))

        elif edit.operation == "add_after":
            index = self.resolve_line(edit.find, modified_content)
            modified_content.insert(index + 1, edit.add)
            change_records.append(ChangeRecord(
                type="ingredient" if edit.target == "ingredients" else "instruction",
                from_text="", to_text=edit.add, operation="add",
            ))

        elif edit.operation == "remove":
            index = self.resolve_line(edit.find, modified_content)
            removed_text = modified_content.pop(index)
            change_records.append(ChangeRecord(
                type="ingredient" if edit.target == "ingredients" else "instruction",
                from_text=removed_text, to_text="", operation="remove",
            ))

        if not change_records:
            raise EditApplicationError("target_not_found")
        return modified_content, change_records

    def resolve_replacement(self, target: str, lines: List[str]) -> Tuple[int, int, int]:
        """Prefer one exact whole line; otherwise require one exact occurrence."""
        if not target.strip():
            raise EditApplicationError("empty_target")
        whole_lines = [i for i, line in enumerate(lines) if line == target]
        if len(whole_lines) > 1:
            raise EditApplicationError("ambiguous_target")
        if whole_lines:
            return whole_lines[0], 0, len(target)

        occurrences = []
        for index, line in enumerate(lines):
            start = line.find(target)
            while start != -1:
                occurrences.append((index, start, start + len(target)))
                # Count overlapping occurrences too: none may be chosen arbitrarily.
                start = line.find(target, start + 1)
        if not occurrences:
            raise EditApplicationError("target_not_found")
        if len(occurrences) > 1:
            raise EditApplicationError("ambiguous_target")
        return occurrences[0]

    def apply_modification(
        self, recipe: Recipe, modification: ModificationObject
    ) -> ModificationResult:
        """Apply all edits to a copy, returning the original on any failure."""
        if not modification.edits:
            return ModificationResult(status="failed", recipe=recipe, reason="no_edits")
        modified_recipe = recipe.model_copy(deep=True)
        modified_recipe.recipe_id = f"{recipe.recipe_id}_modified"
        records = []
        for edit in modification.edits:
            try:
                content, changes = self.apply_edit(edit, getattr(modified_recipe, edit.target))
            except EditApplicationError as error:
                return ModificationResult(
                    status="failed", recipe=recipe, reason=str(error), failed_edit=edit
                )
            setattr(modified_recipe, edit.target, content)
            records.extend(changes)
        if (modified_recipe.ingredients == recipe.ingredients
                and modified_recipe.instructions == recipe.instructions):
            return ModificationResult(status="failed", recipe=recipe, reason="no_change")
        return ModificationResult(status="applied", recipe=modified_recipe, changes=records)

    def apply_modifications_batch(
        self,
        recipe: Recipe,
        modifications: List[ModificationObject]
    ) -> Tuple[Recipe, List[List[ChangeRecord]]]:
        """
        Apply multiple modifications to a recipe sequentially.

        Args:
            recipe: Original recipe to modify
            modifications: List of modifications to apply

        Returns:
            Tuple of (final_modified_recipe, list_of_change_records_per_modification)
        """
        current_recipe = recipe
        all_change_records = []

        logger.info(f"Applying {len(modifications)} modifications sequentially")

        for i, modification in enumerate(modifications):
            logger.info(f"Applying modification {i + 1}/{len(modifications)}: {modification.modification_type}")

            result = self.apply_modification(current_recipe, modification)
            if result.status == "failed":
                raise EditApplicationError(result.reason)
            current_recipe = result.recipe
            all_change_records.append(result.changes)

        logger.info(f"Applied all modifications. Final recipe has {len(current_recipe.ingredients)} ingredients and {len(current_recipe.instructions)} instructions")
        return current_recipe, all_change_records

    def validate_modification_safety(
        self,
        modification: ModificationObject,
        recipe: Recipe
    ) -> Tuple[bool, List[str]]:
        """
        Check mechanical applicability on a copy, not culinary safety or review fidelity.

        Args:
            modification: Modification to validate
            recipe: Recipe being modified

        Returns:
            Tuple of (is_safe, list_of_warnings)
        """
        result = self.apply_modification(recipe, modification)
        return result.status == "applied", [result.reason] if result.reason else []
