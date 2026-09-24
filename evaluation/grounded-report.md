# Grounded planning: changes, evidence and remaining blockers

Historical baseline. See [complex-repair-report.md](complex-repair-report.md) for
the subsequent complex-review fixes, model defaults and current evaluation evidence.

## Implementation

Live requests now use one shared API/CLI workflow:
interpret full review -> validate quotes/targets and calculate supported quantities
-> generate linked edits -> require intent coverage and exact calculated edits
-> audit source fidelity -> apply consistency gate -> publish.

Exact quotes and intent references are necessary checks, not proof of semantics.
The fidelity model reviews the original review independently of edit-reference
coverage. Unknown interpretations, invalid plans, contradictory or unverified
recipes are withheld. Empty/future-only interpretation is audited before a skip.
Original inputs and generated historical recipe files are preserved.

Supported quantity arithmetic uses Fraction, matching one ingredient and preserving
its unit. Absolute amounts, multiplication, addition and subtraction are supported.
Clear halving language is normalized to multiplication by 1/2, independent of a
model's mistaken subtraction label. Output uses readable mixed fractions.
No general unit conversion, ingredient ontology or culinary guarantees were added.

Model defaults for the new workflow are gpt-4o-mini, separately configurable for
interpretation/edit generation, fidelity and consistency. The initial gpt-3.5-turbo
trial withheld two of three cases; the stronger-model comparison applied two of
three. Prompts also changed between trials, so this is not a controlled model-only
benchmark. The legacy extractor is retained for old evaluation scripts only.

Each planning stage makes one request, with at most one schema-correction retry.
Transport retries are disabled; timeout is 45 seconds per request. A typical success
uses three planning requests plus one consistency audit; worst case is seven calls.
Two salt cases exposed an invalid enum spelling (`substract`). Their targeted rerun
passed after a bounded schema-repair exchange; invalid output is never accepted by
silently weakening the schema.

## Fixed cases and results

Evidence: grounded-initial.json, grounded-comparison.json, grounded-final.json,
grounded-verified.json and grounded-schema-repair.json. Earlier failures and even an
incorrectly published cinnamon result in grounded-final.json are preserved.
That result motivated extending the lexical guard to recognize 'a tiny dash'.

The main verified run contains the original seven cases, three initially unseen
cases, and two repeats. Expected behavior was established before calling the model.
After diagnosis/tuning, these are development cases, not an independent held-out
estimate of generalization.

| Case | Verified run | Latest observed outcome |
| --- | --- | --- |
| Cookie cinnamon, sugar and flour | needs_review | Withheld: cinnamon missing preparation. This is a resolvable review; not a completed enhancement. |
| Omit walnuts | applied | Correct ingredient removal and mixing step |
| White sugar plus extra egg | applied | Both quantities correct |
| Soup future ginger | skipped | Original preserved; no future suggestion applied |
| Ambiguous cake sugar | needs_review | Explicit target ambiguity, no arbitrary sugar selection |
| Numbered cookie review | needs_review | Incomplete/incorrectly linked edit plan blocked; still unresolved |
| New fraction fixture | applied | 3 eggs, 3/8 cup sugar, matching instructions |
| Initially unseen soup salt | failed | Targeted schema-repair rerun: applied 1/2 tsp, broth preserved |
| Initially unseen negation | skipped | 'Did not remove' produced no removal |
| Initially unseen performed/future mixture | applied | Eggs changed; future sugar wish left unapplied |
| Repeat two changes | applied | Both quantities correct again |
| Repeat soup salt | failed | Targeted schema-repair rerun: applied correctly again |

The verified run met the expected behavior in **8/12 observations**. The subsequent
two salt reruns passed, bringing the combined latest observations to **10/12**.
This is NOT a single 10/12 run of the final code. No full-suite live rerun followed
the small schema-repair and target-specific halving refinements; offline tests cover
those changes. The two remaining failures are valid complex reviews withheld for
manual review, not misrepresented as successful enhancements.

Of the seven original development cases, three yielded complete enhancements,
two correctly abstained and two valid requests were withheld. Do not compare this
as '5/7 enhanced recipes' against the earlier 3/7 metric. Correct abstention and
successful enhancement are distinct outcomes. The latest accepted outputs inspected
here had no observed unsupported edits, but this small set cannot establish a zero
error rate. Repeats cover only two simple scenarios.

Recorded planning calls across the five reports: **81**, with **92,640 reported
planning tokens**. Additional consistency audits are not included in that token
sum. This is usage evidence, not a dollar estimate.

## Remaining work

The high-priority publication risks are now guarded, not universally eliminated.
Both fidelity and consistency audits can accept errors or reject correct recipes.
Quotes can be genuine while interpretations are wrong; lexical disambiguation is
conservative and does not resolve all contextual references. Unsupported quantity
formats/units are withheld, and qualitative additions still rely on model planning.

Next: repair incomplete complex plans with a tightly bounded, evaluated feedback
step or improve planning quality, then run a genuinely new held-out set and repeat
more cases. Do not declare all high-priority blockers closed based on these results.
Community-vote selection, time metadata and detailed provider-error categorization
remain outside this change.

## Reproduction

Offline: `.venv/Scripts/python.exe -m unittest discover -s tests -v`.
Paid evaluation: `.venv/Scripts/python.exe evaluation/grounded_run.py --model
gpt-4o-mini --output NEW-NAME.json`. Use `--only CASE_ID ...` for a targeted rerun.
The runner refuses to overwrite previous evidence. It runs the current code; a
report label does not switch historical implementations. Inspect the saved plans,
quotes, changes and final recipes instead of scoring any `applied` result as a pass.
