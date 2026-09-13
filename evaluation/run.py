"""Fixed-case live evaluation; saves evidence for human grading, not automatic passes."""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dotenv import load_dotenv
from loguru import logger
from llm_pipeline.models import Recipe, Review
from llm_pipeline.recipe_modifier import RecipeModifier
from llm_pipeline.tweak_extractor import TweakExtractor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["baseline", "candidate", "candidate-v2"])
    args = parser.parse_args()
    output = ROOT / "evaluation" / f"{args.phase}.json"
    if output.exists():
        parser.error(f"Refusing to overwrite evidence: {output}")
    load_dotenv(ROOT / ".env")
    logger.remove()
    logger.add(sys.stderr, level="ERROR")
    cases = json.loads((ROOT / "evaluation/cases.json").read_text(encoding="utf-8"))
    report = {"phase": args.phase, "created_at": datetime.now(timezone.utc).isoformat(),
              "model": "gpt-3.5-turbo", "temperature": 0.1,
              "application_retries": 0, "sdk_retries": 0,
              "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                for name in ["src/llm_pipeline/prompts.py", "src/llm_pipeline/recipe_modifier.py",
                                             "src/llm_pipeline/tweak_extractor.py", "evaluation/cases.json"]},
              "cases": []}
    extractor = TweakExtractor()
    # Keep the evaluation bounded, including transport-level retry behavior.
    client = extractor.client
    extractor.client = client.with_options(max_retries=0, timeout=45)
    try:
        for case in cases:
            recipe = Recipe.model_validate(case["recipe"])
            plan = extractor.extract_modification(
                Review(text=case["review_text"], has_modification=True), recipe, max_retries=0
            )
            result = RecipeModifier().apply_modification(recipe, plan) if plan else None
            report["cases"].append({"id": case["id"], "expected": case["expected"],
                                    "plan": plan.model_dump() if plan else None,
                                    "application": result.model_dump() if result else None})
            output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(case["id"], result.status if result else "extraction_failed", flush=True)
    finally:
        extractor.client.close()
        client.close()


if __name__ == "__main__":
    main()
