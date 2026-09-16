<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: CSV Upload & Room Mapping Implementation Plan

- **Plan**: context/changes/csv-upload-room-mapping/plan.md
- **Scope**: Phase 4 of 4 (full plan review)
- **Date**: 2026-09-16
- **Verdict**: APPROVED
- **Findings**: 0 critical, 2 warnings, 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | PASS |
| Safety & Quality | WARNING |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

## Findings

### F1 — Unbounded upload read before size/field-length validation

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: `rooms/views.py:56-57,71-74`
- **Detail**: `MAX_ROWS` (5000) and `MAX_HEADER_LENGTH` (200) are enforced, but only *after* the entire file is read into memory and decoded (`views.py:56-57,62-64`). There's no overall byte-size cap and no per-field value-length cap, and `stay_recon/settings.py` doesn't override Django's default `DATA_UPLOAD_MAX_MEMORY_SIZE`. An authenticated organiser could upload a file with few rows but very long field values, passing both caps while still bloating their own `PendingUpload.raw_rows` JSON. This is self-inflicted (only affects the uploading organiser's own data), not a cross-tenant risk.
- **Fix**: Reject based on `request.FILES['csv_file'].size` before reading, and/or cap individual field length in `validate_row`.
- **Decision**: FIXED — added `MAX_UPLOAD_BYTES` (2MB) checked via `csv_file.size` before any read in `csv_upload` (`rooms/views.py:56-60`), and `MAX_FIELD_VALUE_LENGTH` (200) per-field cap in `validate_row` (`rooms/forms.py`). Two new tests added (`test_oversized_upload_rejected`, `test_overlong_field_value_flagged`); full suite 61/61 passing.

### F2 — Phase 4 capacity validation built via shared helper, not the planned formset `clean_capacity`

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: `rooms/forms.py:59-62`, `rooms/views.py:172-178`
- **Detail**: The plan's contract (`plan.md:206`) specified `RoomRowForm` validating capacity via a `clean_capacity` method, with the view calling `formset.is_valid()`. The actual `RoomRowForm` has three plain `CharField(required=False)` with no field-level validation; `csv_preview` never calls `formset.is_valid()` and instead reads raw values off `request.POST` directly, re-validating via the same `validate_row()` helper Phase 3 uses. Functionally equivalent — same two checks (blank room number, non-numeric capacity), all listed unit tests pass — but the mechanism differs from the written contract.
- **Fix**: Update `plan.md`'s Phase 4 contract to describe the actual mechanism (shared `validate_row()` helper, not formset-level `clean_capacity`), so the plan reflects what was built. No code change needed — the implementation is sound and reuses Phase 3's validation logic sensibly.
- **Decision**: FIXED — `plan.md`'s Phase 4 contract text updated to describe the actual `request.POST` + `validate_row()` mechanism.

### F3 — CSV formula injection (future-proofing only)

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: `rooms/forms.py:31-53`
- **Detail**: Room field values from the CSV are stored as-is. No export/Excel-open feature exists today, so this isn't currently exploitable — flagged for whoever builds a future CSV/Excel export to sanitize leading `=`, `+`, `-`, `@`.
- **Fix**: No action needed now; revisit when an export feature is built.
- **Decision**: ACCEPTED-AS-RULE: "CSV/Excel export must sanitize formula-injection characters" (`context/foundation/lessons.md`)

### F4 — Non-atomic delete+create of `PendingUpload`

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: `rooms/views.py:79-85`
- **Detail**: `PendingUpload.objects.filter(...).delete()` followed by `.create()` isn't wrapped in `transaction.atomic()`. Low impact — a unique constraint exists, worst case is an `IntegrityError` on a same-user concurrent double-submit. This is *not* the wipe-and-replace path the plan calls out as needing atomicity; that path (`Room` delete+`bulk_create` in `csv_preview:195-206`) **is** correctly atomic and covered by `test_replace_flow_confirm_is_atomic`.
- **Fix**: No action needed — low-risk scratch-state path, not the critical data path.
- **Decision**: SKIPPED

## Notes

- Plan Drift Detection agent: all 4 phases' planned changes verified as MATCH against the actual implementation, with one DRIFT (F2 above) and two harmless, non-substantive EXTRAs (a `search_fields` addition on `RoomAdmin`; an unreachable defensive `errors='replace'` decode fallback, acknowledged in a code comment). Zero MISSING items. All of the plan's "What We're NOT Doing" boundaries (lines 38-47) were respected — verified via `git show --stat` on all 4 commits confirming `infrastructure.md` was untouched, no object storage, no cron job, no standalone Room CRUD UI.
- Safety & Pattern agent: no CRITICAL issues. Object-level authorization verified present and correct on all 3 new views (`get_object_or_404(..., organiser=request.user)`, returning 404), matching `events/views.py`'s established pattern exactly and exercised by dedicated tests. No unescaped template output anywhere. `TOTAL_FORMS` mismatch guard present and tested. The critical wipe-and-replace atomicity (Room delete+bulk_create) is correctly wrapped in `transaction.atomic()` and tested via a forced-failure test. Pattern compliance clean across views/forms/tests conventions; `context/foundation/lessons.md` does not exist, so pattern was verified directly against `events/views.py`/`events/tests.py`.
- Success criteria: all automated checks re-run and passing (`manage.py check`; `makemigrations --check --dry-run` — no changes detected; `manage.py test rooms` 29/29; `manage.py test` full suite 59/59). All 13 manual Progress checkboxes across the 4 phases carry commit SHAs and are backed by specific, named tests — no rubber-stamping concern.
