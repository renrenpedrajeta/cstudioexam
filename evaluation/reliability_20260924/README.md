# Reliability evaluation — 24 September 2026

The frozen suite contains 36 new reviews against five catalog recipes. Five complex
cases ran five times each, giving 56 live HTTP requests. No application code changed
during the evaluation; source hashes and the case-file hash were checked afterward.

## Results

- Correct first-run outcomes: 29/36, including 12 intended abstentions.
- Correct first-run completion of clear enhancement requests: 17/24 (70.8%).
- Across all 56 requests: 39 correct, 4 incorrect publications, 4 incomplete plans
  withheld, 5 false rejections, and 4 technical failures.
- Only M01 completed correctly in all five repetitions.
- Existing offline regression suite: 56/56 passed.
- Provider-failure injections through FastAPI TestClient: 5/5 passed, no paid calls.
- Recorded planning usage: 161 call records and 200,933 tokens. Consistency tokens
  and three HTTP 502 planning-call ledgers are unavailable, so this is partial usage.

The zero-incorrect-publication and 95%-supported-completion criteria were not met.
High-priority reliability work is reopened. H01 changes stirring parsley to garnishing;
H02 retains a peanut description after peanut removal. H03-H06 cover duration
classification, incomplete ordering/dependencies, equivalent quantity grammar, and
ingredient-name normalization. Three late responses explicitly name RateLimitError;
one other consistency validation could not complete. These do not establish the
underlying provider limit or available credit balance.

The spreadsheet is `outputs/reliability-20260924/Recipe_API_Reliability_Results.xlsx`
relative to the repository root. It contains summary formulas, cases, every run,
prioritized issues with proposed fixes, exact published changes and methodology.

## Evidence and reproducibility

`cases.json` includes the predeclared expectations, original recipe snapshots and
source hashes. `raw-results.json` preserves all API responses and request timings.
`reviewed-results.json` records semantic assessments; `analyze.py` reproduces totals
from those explicit review decisions. Review assessments are not an independent
automated oracle. `fault-results.json` and `regression-results.txt` hold offline results.

`run.py` uses two workers, localhost port 8000, and no test-run retries. It refuses to
overwrite results. Preserve this baseline; use a new evaluation directory and fresh
cases for a post-fix run. These cases must now be treated as development regressions.
