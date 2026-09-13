# Fixed review evaluation — September 13, 2026

## Scope and method

Seven review/recipe pairs were fixed in `cases.json` before changes. Three supplied
reviews (two cookie reviews and one soup review), three custom reviews on supplied
recipes and one new fraction fixture exercise the observed risks.
The exact case text and expected outcomes are in that file (seven cases total).
Each run made seven logical extraction calls, with no application or SDK retries,
using `gpt-3.5-turbo`, temperature 0.1. There were 21 logical calls total. This is
one observation per case/version, not a statistical reliability estimate.

`baseline.json`: prior prompt and fuzzy insertion/removal, 1,000 output-token cap.
`candidate.json`: exact insertion/removal and stricter prompt, still sent as a user
message, 1,000-token cap.
`candidate-v2.json`: same exact targeting, separate system rules and JSON user data,
full Pydantic schema in the system message, 2,400-token cap.
Thus v2 measures the combined prompt/message/token-limit change, not an isolated
variable. The later incomplete-response guard is covered by offline tests and was
not part of these live runs.

Reports preserve parsed model plans, applied content, source hashes and timestamps.
They do not contain provider usage/billing totals or verbatim raw response envelopes.
Original recipe files and historical generated recipe outputs were not overwritten.

## Manual assessment of edits

A pass requires all labeled changes, no unsupported edits, and consistent final
ingredients/instructions. Correct abstention is a pass for the two ambiguous or
future-intention cases. HTTP/application success is NOT a quality pass.

| Case | Baseline | Prompt-only candidate | Final v2 observation |
| --- | --- | --- | --- |
| cookie_cinnamon | Fail: extra white sugar, invented 1/4 tsp cinnamon, missing mixing step | Fail: combined sugars incorrectly; missing mixing step | Fail: extra white sugar still invented; cinnamon now qualitative but missing mixing step |
| cookie_nuts | Fail: instruction still includes walnuts | Fail: same | Pass: ingredient removed and mixing instruction updated |
| cookie_two_changes | Pass: both quantities changed | Pass | Pass: both quantities changed |
| soup_future | Fail: future ginger intention applied with invented amount | Fail | Fail: future intention applied, quantity dropped |
| cake_ambiguous | Fail: chose brown/white sugars without resolving frosting sugar | Fail | Fail: same |
| cookie_numbered | Fail: only two sugar edits | Fail: only two sugar edits | Fail overall: all five source intents captured, but obsolete water instruction remains and cream of tartar is absent from preparation |
| new_fraction | Pass: 3 eggs and 3/8 cup sugar | Pass | Pass |

Edit-quality passes: **2/7 baseline, 2/7 first candidate, 3/7 v2**. All seven plans
were mechanically applied in each run, illustrating why application rate alone is
misleading. Reasons are assessed separately: baseline and first candidate invented
benefits/motives. V2 is better but still includes unsupported preference/motive
language. These are not verified culinary improvements.

## Decision and limitations

Keep exact targeting: unlike a prompt, it deterministically prevents selecting an
ambiguous or merely similar line for insertion/removal. Keep system/data separation
and complete-plan instructions: nuts consistency and numbered-review completeness
improved in the observed run. Do not claim prompt changes solved interpretation.

There is still no general semantic consistency or source-fidelity gate. The API's
`applied` means operations succeeded, not that the recipe is correct. Insertion
into an empty list has no valid anchor and is rejected. Qualitative quantities
remain qualitative; no culinary quantity conversion engine was introduced.

Next work should compare another model or a source-grounded validation stage on
these same cases and a held-out set before further prompt expansion. A validation
stage must itself be evaluated; another model opinion is not proof of correctness.
Do not hide the four failed cases in the presentation.

## Reproduction

From the root, run `.venv/Scripts/python.exe -m unittest discover -s tests -v` for
offline regressions. `evaluation/run.py baseline|candidate|candidate-v2` calls the
live API and refuses to overwrite saved evidence. Those phase names are labels,
not historical-code switches: the runner always evaluates the currently checked-out
code. Preserve the existing evidence; a fresh comparison needs new output names
and the corresponding code revision. Low temperature does not guarantee identical
results across repeated model calls.
