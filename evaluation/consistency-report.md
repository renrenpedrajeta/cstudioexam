# Ingredient/instruction consistency gate

## What changed

Both the CLI and live API now withhold enhanced recipes until consistency validation
passes. Rejection returns the original recipe, no applied change records, and an
explanation. Invalid JSON, timeout, provider failure and uncertain verdicts also
block publication. The validator does not attempt automatic repair.

Simple explicit additions/removals receive conservative lexical checks for missing
use or obsolete references. Remaining cases receive an audit of final ingredients
and instructions using `gpt-4o-mini`. Sending before/after history confused both
models tested, so the final model input omits original recipe text. Audit failures
do not leak provider bodies through API responses. Offline preview remains a
mechanical tool and explicitly reports consistency as not checked.

## Evaluation evidence

The seven candidate recipes were fixed before testing: four previously observed
bad recipes/controls and three valid controls. Inputs and expected labels are saved
in each report. No fresh extraction calls were made for this experiment.

| Iteration | Evidence | Correct decisions |
| --- | --- | --- |
| Original/candidate history, gpt-3.5-turbo | consistency-results.json | 4/7; rejected every valid control |
| Clarified history, gpt-4o-mini | consistency-v2-results.json | 4/7; rejected every valid control |
| Final recipe only, gpt-4o-mini | consistency-final-results.json | 6/7; missed water/cream-of-tartar inconsistency |
| Explicit added/removed context in model payload | consistency-gated-results.json | 5/7; false rejections returned |
| Lexical addition/removal checks + final-recipe audit | consistency-verified-results.json | 7/7 |

The first four iterations made seven audit calls each. The final iteration used
three local rejections and four audit calls: **32 audit calls total**.

Final results:

- Removed walnuts still used in mixing: blocked locally.
- Walnuts removed from both ingredients and mixing: accepted by audit.
- Added cinnamon with no preparation step: blocked locally.
- Removed water still used to dissolve baking soda, added cream of tartar unused: blocked locally.
- Changed sugar/egg quantities with generic preparation language: accepted by audit.
- Ingredient quantity 0.5 cup, instruction still 1 cup: blocked by audit.
- Ingredient quantity 0.5 cup, instruction 1/2 cup: accepted by audit.

These are single observations on a development set, not held-out generalization
evidence. A gate can err both ways. Seven correct decisions are not proof that the
blocker is universally solved. Extraction still has source-fidelity, ambiguity,
and completeness errors documented in the earlier evaluation.

## Limitations and next verification

The lexical check handles simple quantity/unit/name lines, not a general ingredient
grammar. Aliases, compound ingredients, negation, split quantities, garnishes, and
collective preparation can require model interpretation and can cause false alarms.
Full final-recipe auditing may also flag pre-existing issues. The model is not a
culinary safety authority and does not verify that edits follow a source review.

Before broad use, add held-out recipes covering those cases and repeat the audit to
measure false acceptance/rejection. No actual enhanced-recipe files were overwritten.
Run `evaluation/check_consistency.py --model gpt-4o-mini --output NEW-NAME.json` for
a fresh paid run; the runner refuses to overwrite evidence. All phase reports use
the code at their run time; output labels do not restore historical code.
