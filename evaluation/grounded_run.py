"""Bounded grounded-workflow evaluation; report outcomes for manual semantic grading."""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dotenv import load_dotenv
from llm_pipeline.models import Recipe, Review
from llm_pipeline.tweak_extractor import TweakExtractor
from llm_pipeline.workflow import enhance_review


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="gpt-3.5-turbo")
    parser.add_argument("--output", required=True)
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--cases", type=Path, help="Run exactly this JSON case list instead of the default suite")
    args = parser.parse_args()
    output = ROOT / "evaluation" / args.output
    if output.exists():
        raise SystemExit("Refusing to overwrite evaluation evidence")
    cases = json.loads((ROOT / "evaluation/cases.json").read_text(encoding="utf-8"))
    cases += [
        {"id": "heldout_soup_salt", "recipe": {"recipe_id": "salt", "title": "Vegetable soup", "ingredients": ["1 teaspoon salt", "2 cups broth"], "instructions": ["Heat broth and stir in salt."]},
         "review_text": "I used 1/2 teaspoon of salt instead of 1 teaspoon. Everything else stayed the same.", "expected": ["Salt 1/2 teaspoon; broth and instruction preserved; applied."]},
        {"id": "heldout_negation", "recipe": {"recipe_id": "nuts", "title": "Nut batter", "ingredients": ["1 cup walnuts", "1 cup flour"], "instructions": ["Mix walnuts and flour."]},
         "review_text": "I did not remove the walnuts. I made it exactly as written.", "expected": ["Skipped; no edits."]},
        {"id": "heldout_mixed_timing", "recipe": {"recipe_id": "batter", "title": "Plain batter", "ingredients": ["2 eggs", "1 cup sugar"], "instructions": ["Beat eggs and sugar."]},
         "review_text": "I used 3 eggs instead of 2. Next time I might halve the sugar.", "expected": ["Eggs 3; sugar remains 1 cup; future suggestion unapplied."]},
    ]
    cases += [{**cases[2], "id": "repeat_two_changes"}, {**cases[-3], "id": "repeat_soup_salt"}]
    if args.cases:
        cases = json.loads(args.cases.read_text(encoding="utf-8"))
    if args.only:
        cases = [case for case in cases if case["id"] in args.only]
    load_dotenv(ROOT / ".env")
    os.environ["INTERPRETATION_MODEL"] = args.model
    extractor = TweakExtractor(model=args.model)
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "interpretation_model": args.model,
              "fidelity_model": os.getenv("FIDELITY_MODEL", "gpt-4.1"),
              "consistency_model": os.getenv("CONSISTENCY_MODEL", "gpt-4.1"),
              "repair_model": os.getenv("REPAIR_MODEL", "gpt-4.1"), "cases": []}
    try:
        for case in cases[:args.limit]:
            outcome = enhance_review(Recipe.model_validate(case["recipe"]), Review(text=case["review_text"], has_modification=True), extractor)
            serialized = {key: value.model_dump() if hasattr(value, "model_dump") else value for key, value in outcome.items()}
            report["cases"].append({"id": case["id"], "expected": case["expected"], "outcome": serialized})
            output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(case["id"], outcome["status"], outcome["planning"].issues, flush=True)
    finally:
        extractor.client.close()


if __name__ == "__main__":
    main()
