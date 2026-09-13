"""Seven fixed consistency checks; one metered audit per case, no extraction calls."""
import json
import argparse
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dotenv import load_dotenv
from llm_pipeline.consistency import check_consistency
from llm_pipeline.models import ModificationObject, Recipe
from llm_pipeline.recipe_modifier import RecipeModifier
from llm_pipeline.tweak_extractor import TweakExtractor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--output", default="consistency-v2-results.json")
    args = parser.parse_args()
    output = ROOT / "evaluation" / args.output
    if output.exists():
        raise SystemExit("Refusing to overwrite consistency evidence")
    source = {case["id"]: case for case in json.loads((ROOT / "evaluation/cases.json").read_text(encoding="utf-8"))}
    before = {case["id"]: case for case in json.loads((ROOT / "evaluation/baseline.json").read_text(encoding="utf-8"))["cases"]}
    after = {case["id"]: case for case in json.loads((ROOT / "evaluation/candidate-v2.json").read_text(encoding="utf-8"))["cases"]}
    cases = []
    for name, case_id, report, expected in [
        ("removed_nuts_still_in_step", "cookie_nuts", before, "inconsistent"),
        ("nuts_removed_consistently", "cookie_nuts", after, "consistent"),
        ("cinnamon_missing_preparation", "cookie_cinnamon", after, "inconsistent"),
        ("removed_water_still_required", "cookie_numbered", after, "inconsistent"),
        ("quantity_change_generic_instructions", "cookie_two_changes", after, "consistent"),
    ]:
        cases.append((name, source[case_id]["recipe"], report[case_id]["plan"], expected))
    for name, instruction, expected in [
        ("explicit_quantity_conflict", "Mix 1 cup sugar into flour.", "inconsistent"),
        ("equivalent_fraction", "Mix 1/2 cup sugar into flour.", "consistent"),
    ]:
        cases.append((name, {"recipe_id": name, "title": "Batter", "ingredients": ["1 cup sugar", "1 cup flour"],
                             "instructions": [instruction]},
                      {"modification_type": "quantity_adjustment", "reasoning": "Quantity change",
                       "edits": [{"target": "ingredients", "find": "1 cup sugar", "replace": "0.5 cup sugar"}]}, expected))
    load_dotenv(ROOT / ".env")
    extractor = TweakExtractor()
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "model": args.model,
              "scope": "consistency only, not review fidelity", "cases": []}
    try:
        for name, raw, plan, expected in cases:
            original = Recipe.model_validate(raw)
            candidate = RecipeModifier().apply_modification(original, ModificationObject(**plan))
            assert candidate.status == "applied"
            check = check_consistency(extractor.client, args.model, original, candidate)
            report["cases"].append({"id": name, "original": original.model_dump(),
                                    "candidate": candidate.model_dump(), "expected": expected,
                                    "check": check.model_dump(), "passed": check.status == expected})
            output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(name, check.status, "expected", expected, flush=True)
    finally:
        extractor.client.close()


if __name__ == "__main__":
    main()
