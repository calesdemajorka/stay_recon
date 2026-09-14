<!-- PLAN-REVIEW-REPORT -->
# Plan Review: CSV Upload & Room Mapping

- **Plan**: context/changes/csv-upload-room-mapping/plan.md
- **Mode**: Deep
- **Date**: 2026-09-14
- **Verdict**: REVISE
- **Findings**: 1 critical, 2 warnings, 0 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | PASS |
| Lean Execution | PASS |
| Architectural Fitness | PASS |
| Blind Spots | FAIL |
| Plan Completeness | PASS |

## Grounding

Grounding: 6/6 paths ✓, 3/3 symbols ✓, brief↔plan ✓. Deep verification via sub-agent confirmed: `bulk_create()` genuinely skips `save()`/signals/`clean()` (Django 6.1 source, `django/db/models/query.py`), `JSONField` works natively on both Postgres (psycopg3, confirmed in `uv.lock`) and SQLite, `utf-8-sig` correctly strips a BOM before `csv.DictReader` (verified by direct execution), no existing multi-step/formset pattern exists to reuse (genuinely new territory, architecturally justified), no naming/import collisions from the new `rooms` app.

## Findings

### F1 — Formset page/TOTAL_FORMS mismatch fails silently, not with an error

- **Severity**: ❌ CRITICAL
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 4 — Preview/edit/confirm view Contract
- **Detail**: Verified against Django 6.1's actual formset source: on POST, a formset's `total_form_count()`/`initial_form_count()` are read from the POSTed `TOTAL_FORMS`/`INITIAL_FORMS` management-form fields, not from the `initial=` list passed at construction. If the view's page-slicing logic and the submitted `TOTAL_FORMS` don't agree (e.g. a subtle off-by-one in the page-boundary math), `_construct_form` wraps `self.initial[i]` in a `try/except IndexError` that **silently drops the mismatch** rather than raising — forms render without their expected initial values instead of erroring. This is exactly the kind of silent data-integrity gap that risks the PRD's "reconciliation report must be data-accurate" guardrail, and the plan's Contract doesn't mention guarding against it.
- **Fix**: Add an explicit server-side check in the Phase 4 Contract: before trusting the submitted formset on any POST, assert `int(request.POST.get('form-TOTAL_FORMS', -1)) == len(expected_page_slice)`; on mismatch, reject and re-render the page fresh from `PendingUpload.mapped_rows` rather than proceeding — don't rely on Django's formset machinery to catch this itself, since it won't.
- **Decision**: FIXED — added to Phase 4's Critical Implementation Detail and Contract; test 4.9 added to Success Criteria/Progress.

### F2 — Empty CSV (zero data rows) behavior undefined

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 3/Phase 4 — no phase addresses this case
- **Detail**: If the uploaded CSV has a header row but zero data rows (or `mapped_rows` ends up empty after mapping), nothing in the plan says whether Confirm is allowed to proceed and create zero `Room` rows, or should be blocked. As written, an organiser could "confirm" an accidentally-empty CSV with no feedback that nothing was actually imported.
- **Fix**: Add a named edge case: if `mapped_rows` is empty at the preview step, show a "No rows found in this CSV" message and disable/redirect away from Confirm rather than silently allowing a zero-room confirmation. Add a corresponding unit test.
- **Decision**: FIXED — added to Phase 4's Confirm Contract; test 4.10 added.

### F3 — No upfront sanity check that the uploaded file is plausibly a CSV, or bounded in size

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Blind Spots
- **Location**: Phase 2 — Upload form & view Contract
- **Detail**: The `latin-1` decode fallback *always* succeeds, even on a binary or wrong-file-type upload (an organiser easily could upload an `.xlsx` renamed `.csv`, or the wrong file entirely — hotels commonly work in Excel). A non-CSV file would decode "successfully" into garbage text, and `csv.DictReader` would produce nonsense headers/rows with no clear error — the organiser lands on a confusing mapping form full of gibberish instead of a helpful "this doesn't look like a CSV" message. Separately, there's no upper bound on row/column count — an accidentally-huge or wrong file could produce an oversized `PendingUpload` JSON blob and an impractical number of preview pages.
- **Fix**: After parsing in Phase 2, add a sanity check before creating the `PendingUpload`: reject (with a friendly error) if `headers` is empty, if any header looks implausibly long (a hallmark of misdecoded binary content), or if the row count exceeds a generous cap (e.g. 5,000, well above any realistic hotel room count). This is cheap defense-in-depth, not full file-type validation.
- **Decision**: FIXED — added to Phase 2's upload Contract; test 2.8 added.
