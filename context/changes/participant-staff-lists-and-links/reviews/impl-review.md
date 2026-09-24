<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Participant & Staff Lists + Access-Link Generation (S-03)

- **Plan**: context/changes/participant-staff-lists-and-links/plan.md
- **Scope**: All phases (1–4 of 4)
- **Date**: 2026-09-24
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 5 warnings, 4 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | WARNING |
| Safety & Quality | WARNING |
| Architecture | WARNING |
| Pattern Consistency | WARNING |
| Success Criteria | WARNING |

Automated: `uv run manage.py test` shows 127/127 OK; `manage.py check` is clean; `makemigrations --check` reports no changes. All 46 Progress items are `[x]`, and every manual item carries a 2026-09-24 confirmation from the user.

Known, accepted drift (not findings):
- Shared role-agnostic forms and view helpers instead of separate per-role forms and view bodies.
- No `exclude_role` parameter on `email_taken_for_event`.
- CSV formula sanitisation, per lessons.md.

Benign extras:
- Field-length caps.
- TOTAL_FORMS and empty-confirm guards.
- UTF-8 BOM on the export.
- Admin `search_fields`.

## Triage summary

- Fixed: F3 (Fix A), F4, F6, F7, F8
- Rule + fixed: F5
- Deferred to GH #20 / test-plan Phase 2: F1, F2
- GH issue: F9 (#21)

## Findings

### F1 — Concurrent or double-submitted confirm returns a 500

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: access/views.py:160-185, access/views.py:223-232
- **Detail**: `full_set_problems()` runs outside the transaction, and nothing around the confirm `atomic()` block catches `IntegrityError` or `ValidationError`. A double-click or a second tab lets both requests pass the check. The loser then fails in one of three ways:
  - `full_clean()` raises `ValidationError`, because `validate_constraints` sees the winner's rows;
  - the insert raises `IntegrityError`;
  - `pending.save(update_fields=['rows'])` raises `DatabaseError`, because the winner already deleted the pending upload.

  The transaction rolls back, so no data is corrupted, but the user sees a 500. `staff_add_one` catches only `IntegrityError`, so it misses the case where the competing add already committed before `full_clean()` ran. `events/views.py:_save_or_duplicate_error` is the established pattern for turning these errors into a form error.
- **Fix A**: Fix now. Lock the pending row with `select_for_update()` inside the transaction and re-check that it still exists. Catch `(IntegrityError, ValidationError)` and re-render with a `page_error`. Do the same in `staff_add_one`.
  - Strength: Closes a user-visible 500 before archive, and matches `events/views.py`.
  - Tradeoff: Proving it needs a `TransactionTestCase` concurrency test, which is exactly the pattern test-plan §3 Phase 2 is meant to establish.
  - Confidence: MED — the fix is straightforward; a reliable race test on SQLite is the harder part.
  - Blind spot: The Render Postgres lock behaviour hasn't been exercised locally.
- **Fix B ⭐ Recommended**: Defer to test-plan §3 Phase 2 (Concurrent-write races), which already targets "CSV upload/confirm replace flow is safe under two real concurrent requests". Add this flow to that phase's brief.
  - Strength: That phase exists for this class of bug and will add the race test that proves the fix. No data-safety impact in the meantime.
  - Tradeoff: The 500 stays live until that phase runs.
  - Confidence: HIGH — test-plan.md §3 row 2 names this exact flow.
  - Blind spot: None significant.
- **Decision**: DEFERRED via Fix B — GH #20, to be handled in test-plan §3 Phase 2

### F2 — "No dual role per event" has no database backstop

- **Severity**: ⚠️ WARNING
- **Impact**: 🔬 HIGH — architectural stakes; think carefully before deciding
- **Dimension**: Architecture
- **Location**: access/models.py:34-41, access/models.py:69-76, access/services.py (email_taken_for_event)
- **Detail**: The unique constraints are per table. The cross-role rule lives only in `email_taken_for_event()`, which checks first and acts later. A participant confirm and a staff add of the same email running at the same moment will both commit, silently breaking the invariant with no error. The plan acknowledged that Django can't express a cross-table constraint, but it didn't address the race.
- **Fix A ⭐ Recommended**: Record it as a known gap in a GitHub issue, linked to test-plan Phase 2, and fix it together with F1. The planned fix is `select_for_update()` on the Event row inside both write paths.
  - Strength: Keeps this change closed. The fix naturally shares F1's locking work and race test.
  - Tradeoff: The invariant stays unenforced under concurrency until then. That's low likelihood for a single organiser.
  - Confidence: HIGH — one organiser per event makes a real collision rare.
  - Blind spot: Collisions caused by multiple tabs haven't been measured.
- **Fix B**: Fix now by serialising writes per event with `select_for_update()` on the Event row in confirm and add-one.
  - Strength: Enforces the invariant now.
  - Tradeoff: Adds locking without the race test that proves it, and duplicates work Phase 2 will do.
  - Confidence: MED — SQLite ignores `select_for_update`, so it can only be verified on Postgres.
  - Blind spot: How the lock behaves on Render's Postgres.
- **Decision**: DEFERRED via Fix A — recorded as a known gap in GH #20, to be fixed alongside F1

### F3 — Confirm runs about 6 queries per row, roughly 30k for a 5000-row upload

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: access/forms.py (full_set_problems), access/views.py:101-113
- **Detail**: Each row costs:
  - 2 `.exists()` queries in `full_set_problems`;
  - an AccessLink INSERT;
  - 2 SELECTs from `full_clean()`, for the OneToOne uniqueness and constraint validation;
  - the member INSERT.

  At the `MAX_ROWS` of 5000 that means one long-held transaction with about 30k queries, a real timeout risk on Render's free plan. `rooms` uses a single `bulk_create`.
- **Fix A ⭐ Recommended**: Pre-fetch the event's normalised existing emails once, from both tables, into a set used by `full_set_problems`. Keep the per-row create and `full_clean()`.
  - Strength: Removes a third of the queries with a small change, and keeps the plan's required `full_clean()` defence-in-depth.
  - Tradeoff: Still about 4 queries per row at confirm.
  - Confidence: HIGH — a local change with existing tests covering the behaviour.
  - Blind spot: Real timings on Render at 5000 rows haven't been measured.
- **Fix B**: Also `bulk_create` the AccessLinks and members, replacing `full_clean()` with an in-memory invariant check.
  - Strength: Constant query count; matches `rooms`.
  - Tradeoff: Drops the `full_clean()` defence-in-depth that the plan's Critical Implementation Details require. Needs a plan amendment.
  - Confidence: MED — bulk_create returns PKs on Postgres and SQLite, but it's a larger change.
  - Blind spot: None significant.
- **Decision**: FIXED via Fix A — services.taken_emails_for_event() prefetch; full_set_problems now 2 queries total (assertNumQueries test)

### F4 — Plan contradicts itself on append-only confirm

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: context/changes/participant-staff-lists-and-links/plan.md:152
- **Detail**: One Phase 2 bullet says confirm "blocks on a duplicate against an existing Participant … other valid rows still succeed". The contract (line 130) and the code block the whole confirm, and that's the behaviour you verified in 2.17. Removing the offending row is GitHub issue #19.
- **Fix**: Amend line 152 to say that the whole confirm is blocked until the row is fixed, and reference GitHub issue #19.
- **Decision**: FIXED — plan.md Phase 2 bullet amended; references GH #19

### F5 — New pages can't be reached from the UI

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: templates/events/event_form.html:11
- **Detail**: No template links to `participant_list_upload`, `staff_list_upload`, `staff_add_one` or `event_links`. The event edit page links only to the room CSV upload, and every success redirect lands there. The plan didn't list navigation, but the feature can't be used without typing URLs.
- **Fix**: Add four links next to "Upload room CSV" on the event edit page. The plan doesn't cover this, so by default it becomes a GitHub issue unless you choose to fix it now.
- **Decision**: FIXED + ACCEPTED-AS-RULE: New pages must name their navigation entry point — links added to templates/events/event_form.html, with a navigation test

### F6 — Several tests assert less than they claim

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: access/tests.py:120, 311, 324, 390, 427, 495, 531
- **Detail**:
  - The `assertFormError(form, 'csv_file', form.errors['csv_file'])` calls compare the errors with themselves.
  - The duplicate-within-upload tests don't check that the rows are named, which the plan requires.
  - The staff event-mismatch test also has a mismatched label, so it would pass even without the event check.
  - The pagination test checks only page 2's row count.
- **Fix**: Assert the actual message text and the row/page numbers. Give the staff mismatch link `label='sam@example.com'`. Assert page 1's first row and page 2's first row.
- **Decision**: FIXED — real message/row-number assertions, staff mismatch confound removed, page 1/page 2 row checks

### F7 — Unbounded links list and error paragraph

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: access/views.py:179, access/views.py:252-283
- **Detail**: `event_links` renders every link on one page, which can exceed 5000. `page_error` joins every problem into one paragraph, up to 5000 messages. Neither is a correctness bug.
- **Fix**: Cap `page_error` at the first 10 problems plus "and K more". Paginate the links list at `PAGE_SIZE`; the CSV export covers bulk retrieval.
- **Decision**: FIXED — page_error capped at 10 problems + "…and K more"; links list paginated at PAGE_SIZE (export still full)

### F8 — Re-upload silently discards saved preview edits, and delete+create isn't atomic

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: access/views.py:66-67
- **Detail**: A new upload deletes the unconfirmed pending upload, along with any corrections already saved page by page, without a warning. Two concurrent uploads can also hit the pending-upload unique constraint and return a 500. `rooms` has the same shape (rooms/views.py:85-86).
- **Fix**: Wrap the delete+create in `transaction.atomic()`. The missing warning matches `rooms`, so it's out of scope here.
- **Decision**: FIXED — pending delete+create wrapped in transaction.atomic(); the concurrent-upload race is part of GH #20

### F9 — CSV and paging helpers copied from rooms

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: access/views.py:27-44, access/views.py:78-83
- **Detail**: `_decode_csv_bytes`, `_total_pages` and `_clamp_page` are verbatim copies from `rooms/views.py`.
- **Fix**: File a GitHub issue to extract a shared CSV/paging helper before a third copy appears. It's a pre-existing file outside this plan.
- **Decision**: FIXED via GH issue — #21 (extract shared CSV/paging helpers); no code change
