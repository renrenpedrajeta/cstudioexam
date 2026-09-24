# Complex-review repair

This report supersedes the two unresolved examples in grounded-report.md. Earlier
reports are retained, including failed trials and false rejections; filenames alone
do not establish which implementation was used.

## Changes

- Python assembles calculated ingredient changes before model-generated edits.
  Quantity-only changes with generic instructions avoid unnecessary edit generation.
- Local dependency checks cover explicit added/removed ingredient use, retained
  ingredients losing their preparation step, qualitative dash/pinch qualifiers,
  incomplete rewritten dissolution steps, and chilling before shaping/baking.
- At most one semantic repair attempt receives exact failure feedback. A replacement
  plan is applied afresh to the original, with calculated quantities protected.
  Exact targeting, intent coverage, dependency checks and source fidelity run again.
  The final consistency gate still runs before publication. Failure preserves the
  original and publishes no enhanced recipe.
- Source fidelity compares the full review, original recipe and candidate directly.
  Internal plan labels are deliberately excluded: they caused the auditor to reject
  a correct unchanged white-sugar quantity. Quotes and edit attribution remain in
  the response for inspection.
- Interpretation/edit generation defaults to gpt-4o-mini; repair, source-fidelity
  and consistency defaults are gpt-4.1. Each is independently configurable. Smaller
  model trials repeatedly omitted dependencies and falsely rejected explicit use
  steps. This is a pragmatic development comparison, not a controlled benchmark.

GPT-4.1's Chat Completions compatibility was checked against
[official model documentation](https://developers.openai.com/api/docs/models/gpt-4.1).
Account access was then verified through actual calls. No API key was changed.

## Validation

Offline: 56 tests pass, including replay of the previous failing plans, failed-repair
rollback, exact fraction arithmetic, protected quantities, fresh fidelity audit,
qualitative amounts, dependency preservation and chronological instruction order.

Final-code live evidence: complex-final-suite.json and complex-final-additional.json.
The former contains the existing 12 observations (including two repeats); the latter
contains four additional cases. Expected outcomes were specified before their first
run. Since the additional cases informed development after that first run, their
final results are regression evidence, not a fresh held-out accuracy estimate.

Final results were inspected against the expected changes, including quantities,
ingredient use, timing, preservation of unrelated content and abstentions:

| Run | Intended outcomes met | Published enhancements | Correct skips / review holds |
| --- | --- | --- | --- |
| Existing suite | 12/12 | 9 | 2 skipped, 1 ambiguous review withheld |
| Additional cases | 4/4 | 3 | 1 conflicting review withheld |
| Final localhost HTTP repeats | 2/2 | 2 | None |

The HTTP repeats are saved in complex-final-api.json and both returned HTTP 200
with status applied. Cinnamon retains its tiny-dash amount and has a use step.
The numbered case includes both sugar quantities, removes water, retains baking
soda and salt preparation, adds cream of tartar with a use step, and chills before
scooping. An output such as '1 tiny dash cinnamon' is treated as equivalent to
'a tiny dash of cinnamon'; no teaspoon quantity is invented. These narrow reproduced
failures are resolved in the final evidence. General reliability is not established.

The earlier complex-defaults-full.json / complex-defaults-new.json runs passed their
12/12 and 4/4 intended outcomes, but a subsequent HTTP repeat exposed a false
rejection on unchanged white sugar. It is preserved in complex-local-api.json. The
audit-input change above addresses that failure. Do not omit it when assessing
repeatability or present the earlier passing suite as a reliability guarantee.

## Limits and remaining work

Local dependency rules deliberately support limited English patterns, not a general
ingredient ontology or a complete culinary semantics engine. Source-fidelity and
consistency remain model judgments and can still accept errors or reject valid
requests. General unit conversion and complex ingredient quantity formats remain
unsupported and should be withheld. Genuinely uncertain source reviews still need
clarification; returning needs_review is the intended outcome for those cases.

Before claiming broad high-priority reliability closure, run a larger independently
held-out set covering substitutions, multiple preparation stages, unusual wording,
and repeated complex requests; grade final recipes, not status alone. Existing small
fixtures have now been used for tuning. Community-vote selection, time metadata and
detailed provider-error categorization remain outside this change.

Typical success uses 3 or 4 model calls total. One semantic repair plus a fresh audit
can add 2 calls. With each planning-stage schema retry, the hard request-count bound
is 11 including the consistency call. Each call has a 45-second timeout and no
transport retries; there is no overall request deadline. GPT-4.1 increases validation
cost. Raw planning usage is recorded; consistency usage is not yet included in that
ledger. No exact overall dollar cost is claimed.

## Reproduction

Offline: `.venv/Scripts/python.exe -m unittest discover -s tests -q`.

Live (metered, use new output filenames):

```
.venv/Scripts/python.exe evaluation/grounded_run.py --model gpt-4o-mini --output NEW-full.json
.venv/Scripts/python.exe evaluation/grounded_run.py --model gpt-4o-mini --cases evaluation/complex-new-cases.json --output NEW-additional.json
```

Postman requests 15 and 16 exercise the cinnamon and numbered reviews through the
live API. Inspect result.recipe, result.changes, planning.repair_feedback and
consistency_check, as well as status. A repair is conditional, so some runs will have
an empty repair_feedback list.
