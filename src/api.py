"""Local Postman API. Run: python -m uvicorn api:app --app-dir src."""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from llm_pipeline.models import ModificationObject, Recipe, Review
from llm_pipeline.recipe_modifier import RecipeModifier
from llm_pipeline.tweak_extractor import TweakExtractor
from llm_pipeline.consistency import enforce_consistency
from llm_pipeline.workflow import enhance_review

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


class EnhancementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    review_index: int | None = Field(default=None, ge=0, strict=True)
    review_text: str | None = Field(default=None, min_length=1, max_length=10000)

    @model_validator(mode="after")
    def require_one_source(self):
        if (self.review_index is None) == (self.review_text is None):
            raise ValueError("Provide exactly one of review_index or review_text")
        if self.review_text is not None and not self.review_text.strip():
            raise ValueError("review_text must not be blank")
        return self


def get_extractor():
    """Instantiate lazily so health, browsing and preview need no API key."""
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(503, detail={"code": "api_key_missing", "message": "Set OPENAI_API_KEY in the server environment or root .env, then restart."})
    extractor = TweakExtractor()
    try:
        yield extractor
    finally:
        extractor.client.close()


def create_app(data_dir: Path = ROOT / "data") -> FastAPI:
    app = FastAPI(
        title="Recipe Enhancement API",
        version="1.0.0",
        description="Local demonstration API. Preview is offline; enhance calls OpenAI. Responses are not saved to disk.",
    )

    def recipes():
        return [json.loads(path.read_text(encoding="utf-8"))
                for path in sorted(data_dir.glob("recipe_*.json"))]

    def find_recipe(recipe_id: str):
        # IDs are compared against catalog data, never interpolated into paths.
        for raw in recipes():
            if raw.get("recipe_id") == recipe_id:
                return raw
        raise HTTPException(404, detail={"code": "recipe_not_found"})

    @app.get("/health")
    def health():
        return {"status": "ok", "api_key_configured": bool(os.getenv("OPENAI_API_KEY"))}

    @app.get("/recipes")
    def list_recipes():
        return {"recipes": [{"recipe_id": raw["recipe_id"], "title": raw["title"],
                             "review_count": len(raw.get("reviews", []))} for raw in recipes()]}

    @app.get("/recipes/{recipe_id}")
    def get_recipe(recipe_id: str):
        raw = find_recipe(recipe_id)
        return {"recipe": Recipe.model_validate(raw),
                "reviews": [{"review_index": i, **review} for i, review in enumerate(raw.get("reviews", []))]}

    @app.post("/recipes/{recipe_id}/preview")
    def preview(recipe_id: str, plan: ModificationObject):
        """Apply caller-supplied edits offline. This does not evaluate review fidelity."""
        original = Recipe.model_validate(find_recipe(recipe_id))
        result = RecipeModifier().apply_modification(original, plan)
        return {"mode": "preview", "original": original, "result": result,
                "consistency_check": {"status": "not_checked", "issues": []}}

    @app.post("/recipes/{recipe_id}/enhance")
    def enhance(recipe_id: str, request: EnhancementRequest, extractor=Depends(get_extractor)):
        """Select a specific review, extract with OpenAI, and apply all edits or none."""
        raw = find_recipe(recipe_id)
        original = Recipe.model_validate(raw)
        if request.review_index is not None:
            reviews = raw.get("reviews", [])
            if request.review_index >= len(reviews):
                raise HTTPException(404, detail={"code": "review_not_found"})
            review = Review.model_validate(reviews[request.review_index])
        else:
            review = Review(text=request.review_text)
        # An explicit caller selection bypasses the scraper's heuristic flag.
        review = review.model_copy(update={"has_modification": True})
        response = enhance_review(original, review, extractor)
        if response["planning"].status == "failed":
            raise HTTPException(502, detail={"code": "planning_failed", "issues": response["planning"].issues})
        return response

    @app.post("/recipes/{recipe_id}/validate")
    def validate_plan(recipe_id: str, plan: ModificationObject, extractor=Depends(get_extractor)):
        """Apply supplied edits to a copy and audit consistency (one metered model check)."""
        original = Recipe.model_validate(find_recipe(recipe_id))
        result = RecipeModifier().apply_modification(original, plan)
        result, check = enforce_consistency(original, result, extractor)
        return {"mode": "validation", "status": result.status, "original": original,
                "result": result, "consistency_check": check}

    return app


app = create_app()
