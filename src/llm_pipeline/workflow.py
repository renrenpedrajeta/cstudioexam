"""Shared live workflow for API and CLI; no result is published before all gates."""
from .consistency import enforce_consistency
from .enhanced_recipe_generator import EnhancedRecipeGenerator
from .models import ModificationResult
from .recipe_modifier import RecipeModifier


def enhance_review(recipe, review, extractor):
    planning = extractor.plan_review(review, recipe)
    response = {"mode": "live", "status": planning.status, "original": recipe,
                "source_review": review, "planning": planning,
                "proposed_modification": planning.modification, "consistency_check": None,
                "enhanced_recipe": None}
    if planning.status != "ready":
        response["result"] = ModificationResult(status=planning.status, recipe=recipe,
                                                reason="; ".join(planning.issues) or "No performed changes to apply")
        return response
    result = RecipeModifier().apply_modification(recipe, planning.modification)
    result, check = enforce_consistency(recipe, result, extractor)
    if check is not None and result.status == "failed":
        result = result.model_copy(update={"status": "needs_review" if check.status == "inconsistent" else "failed"})
    response.update(status=result.status, result=result, consistency_check=check)
    if result.status == "applied":
        response["enhanced_recipe"] = EnhancedRecipeGenerator().generate_enhanced_recipe(
            recipe, result.recipe, planning.modification, review, result.changes)
    return response
