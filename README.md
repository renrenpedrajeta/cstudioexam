# Recipe Enhancement Platform

Automatically enhances recipes by analyzing and applying community-tested modifications from AllRecipes.com. Uses LLM processing to extract meaningful recipe tweaks and apply them with full citation tracking.

## Installation

This project uses [`uv`](https://docs.astral.sh/uv/) for fast, reliable Python package management.

### Prerequisites

- Python 3.13+
- `uv` package manager

## Setup

```bash
# Install dependencies
uv venv
source .venv/bin/activate
uv pip sync pyproject.toml
```

### Environment Variables

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your-openai-api-key-here
```

## Usage

### Local HTTP API / Postman

From the repository root on Windows:

```powershell
python -m uv sync --frozen
.\.venv\Scripts\python.exe -m uvicorn api:app --app-dir src --host 127.0.0.1 --port 8000
```

Keep that terminal running; Ctrl+C stops the server. Interactive API documentation
is at http://127.0.0.1:8000/docs. This is an API documentation page, not a recipe UI.
The server loads the root `.env`; restart after changing it. It binds to localhost
for local use and has no authentication. Do not expose it publicly as-is.

Import `docs/postman_collection.json` into Postman. Its `base_url` variable defaults
to `http://127.0.0.1:8000`. Use the desktop app or Desktop Agent for localhost access.
No OpenAI key is needed in Postman: it stays in the server's `.env`.

| Endpoint | Purpose | Model call |
| --- | --- | --- |
| `GET /health` | Server health and whether a key is configured (does not test billing/access) | No |
| `GET /recipes` | List supplied recipes and review counts | No |
| `GET /recipes/{id}` | Original recipe and zero-based review indexes | No |
| `POST /recipes/{id}/preview` | Apply a supplied ModificationObject to a copy | No |
| `POST /recipes/{id}/enhance` | Extract and apply one explicit review | Yes |
| `POST /recipes/{id}/validate` | Apply a supplied plan and check consistency, without extraction | At most one audit call |

For enhancement send exactly one of `{"review_index": 0}` or
`{"review_text": "I halved the white sugar."}`. Explicit selection bypasses the
scraper's modification flag. It does not guarantee the model will interpret the
review correctly. The CLI still selects reviews randomly.

API requests never save enhanced recipe files. Responses include original content,
application status, failure reason or actual change records. Live responses also
include the source review, proposed edits, and enhanced recipe when application
succeeds. A rejected edit plan returns HTTP 200 with `status: "failed"` in the
application result; **HTTP 200 alone does not mean an enhancement succeeded**.
Invalid bodies return 422, unknown recipes/reviews 404, a missing key 503, and
provider/invalid-output failure 502. The existing extractor retries up to three
application attempts and does not yet distinguish provider error categories.

Live enhancement now passes a consistency gate before publication. Simple explicit
addition/removal checks run locally; remaining candidates receive a model audit of
the final ingredients and instructions. The validator defaults to `gpt-4o-mini`
(override with `CONSISTENCY_MODEL` in `.env`); extraction stays on `gpt-3.5-turbo`.
This can add one model call and up to 45 seconds per live enhancement. If validation
fails, times out, or returns invalid output, no enhanced recipe is published.

Inspect `consistency_check.status` and `.issues`. A contradiction yields
`result.reason: "recipe_inconsistent"`; an unavailable/uncertain check yields
`"consistency_unverified"`. Both retain the original recipe and empty change records.
Offline preview explicitly reports `consistency_check.status: "not_checked"`.
`/validate` accepts the same body as `/preview`, allowing the Postman demonstration
to test a known inconsistent plan without depending on extraction randomness.

Insertion and removal now require a unique exact whole-line target, including
capitalization; replacement also supports a unique exact substring. If any edit
fails, the original recipe is preserved. These checks establish mechanical
application only. The additional live consistency audit is model-assisted and can
make mistakes; `applied` still does not certify source-review fidelity or culinary quality.
The fixed live evaluation found 3/7 complete, faithful results after the latest
prompt changes, versus 2/7 before. See `evaluation/README.md` for the full results,
limitations, and failed cases. Live model quality remains an open issue.
The newer gate correctly classified seven fixed consistency controls in its final
run; see `evaluation/consistency-report.md`. This is not a rerun of extraction and
does not turn the earlier 3/7 extraction result into a 7/7 recipe-quality result.

Suggested presentation: requests 1–3 to inspect the data, request 4 for a successful
offline replacement, request 5 to demonstrate rejection of a capitalization
mismatch, then request 6 or 7 for live extraction. Only the LIVE requests consume
API credits; do not run the whole collection repeatedly unless intended.

Run offline regression tests from the root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

### 1. Scrape Recipes (Optional - data already provided)

```bash
uv run python src/scraper_v2.py
```

### 2. Run Recipe Enhancement Pipeline

```bash
cd src

# Test single recipe (chocolate chip cookies)
uv run python test_pipeline.py single

# Process all recipes
uv run python test_pipeline.py all
```

## Output

### Enhanced Recipes

Enhanced recipes are saved in `src/data/enhanced/`:

- `enhanced_[recipe_id]_[recipe-name].json` - Individual enhanced recipes with modifications applied
- `pipeline_summary_report.json` - Summary of all processing results

### Data Structure

Original scraped recipes in `data/` directory contain reviews with `has_modification: true` flags. Enhanced recipes include:

```json
{
  "recipe_id": "10813_enhanced",
  "title": "Best Chocolate Chip Cookies (Community Enhanced)",
  "ingredients": ["1 cup butter", "1 additional egg yolk", ...],
  "modifications_applied": [
    {
      "source_review": {
        "text": "I added an extra egg yolk for chewier texture",
        "rating": 5
      },
      "modification_type": "addition",
      "reasoning": "Improves texture and chewiness",
      "changes_made": [...]
    }
  ],
  "enhancement_summary": {
    "total_changes": 1,
    "change_types": ["addition"],
    "expected_impact": "Chewier texture and improved consistency"
  }
}
```

## How It Works

The LLM Analysis Pipeline processes recipes in 3 steps:

1. **Tweak Extraction**: CLI selects one random review with modifications and uses GPT-3.5-turbo to extract structured changes; the API uses an explicit review selection
2. **Recipe Modification**: Applies changes to a copy using unique exact targets and rejects the entire plan if an edit fails
3. **Enhanced Recipe Generation**: Creates enhanced version with full citation tracking back to source review

Each run produces one enhanced recipe per original recipe, with complete attribution showing exactly what changed and why.

## Development

```bash
# Add dependencies
uv add <package_name>

# Run tests
cd src && uv run python test_pipeline.py single
```
