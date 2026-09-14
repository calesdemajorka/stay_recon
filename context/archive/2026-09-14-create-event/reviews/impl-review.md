<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Create Event

- **Plan**: context/changes/create-event/plan.md
- **Scope**: Full plan (Phases 1-3)
- **Date**: 2026-09-14
- **Verdict**: APPROVED
- **Findings**: 0 critical, 2 warnings, 3 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | PASS |
| Safety & Quality | WARNING |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

## Success criteria verification (fresh run)

Automated: `makemigrations --check --dry-run` — no changes; `migrate` against a freshly deleted local db — applies cleanly; `manage.py check` — clean; full suite — 22/22 pass.

Manual (Progress): 1.6, 2.6, 3.6, 3.7 all `[x]`. **Note on evidence**: this change was implemented via an autonomous `/goal` run with no human in the loop, so "manual" verification was self-performed via live `curl`-based HTTP requests against `https://stay-recon.onrender.com` (two throwaway test organiser accounts, full create/list/edit/cross-organiser-404 round trip) rather than human browser testing. Not rubber-stamped — each item has observable evidence in the session transcript (HTTP status codes, response bodies) — but flagged here since it's a different verification method than this project's norm.

## Findings

### F1 — Organiser assignment happens in EventForm.save(), not the view, per plan Contract

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: events/views.py:12-13 (event_create), events/forms.py:59-65 (EventForm.save)
- **Detail**: Phase 2's Contract says the view sets `event.organiser = request.user` before saving via `form.save(commit=False)`. The actual code has `EventForm.save()` do this itself (`if self.organiser is not None: event.organiser = self.organiser`), and the view just calls `form.save()`. Functionally identical — verified correct by both review agents — but the plan's Contract text no longer describes where the logic lives.
- **Fix**: Update plan.md's Phase 2 Contract to describe the actual implementation (organiser assignment centralized in `EventForm.save()`, reused identically by both create and edit) rather than changing working code to match stale contract text.
- **Decision**: PENDING

### F2 — Duplicate-check race: concurrent submission can surface as an unhandled 500

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality (reliability)
- **Location**: events/forms.py:46-57, events/views.py:12-13/25-26
- **Detail**: The duplicate-name check is a SELECT-then-later-INSERT, not atomic with the DB-level `UniqueConstraint`. Two concurrent submissions for the same organiser/name/dates could both pass `form.is_valid()`, and the second `form.save()` would hit an unhandled `IntegrityError`, surfacing as a 500 instead of the friendly field error the plan's guardrail is meant to guarantee. The plan's own Key Discoveries claims the DB constraint "clos[es] the same race-condition class F-01's accounts.User.email uniqueness already closes" — but F-01's SignupForm has the same gap; neither actually catches the race.
- **Fix A ⭐ Recommended**: Wrap `form.save()` in `try/except IntegrityError` in both views, re-rendering the form with the same "already exists" field error on catch.
  - Strength: Closes the actual race window completely; a few lines per view; matches the plan's own stated intent.
  - Tradeoff: Slightly unusual control flow (adding a form error after `is_valid()` already returned True).
  - Confidence: HIGH — standard, well-known Django pattern for this exact scenario.
  - Blind spot: None significant.
- **Fix B**: Accept as a documented known limitation, not fixed now.
  - Strength: Zero code cost; PRD's `target_scale.qps: low` and single-organiser-per-event usage make true concurrent duplicate submission unlikely in practice (would need the same organiser double-submitting from two tabs at once).
  - Tradeoff: A real, if rare, path to an ugly 500 error page remains — and the same gap exists in `accounts.SignupForm`, so this would be a recurring pattern, not a one-off.
  - Confidence: MEDIUM — depends on whether double-tab submission actually happens.
  - Blind spot: Haven't checked whether this exact gap already bit anyone in `accounts.SignupForm` usage so far.
- **Decision**: FIXED via Fix A — added `_save_or_duplicate_error()` helper wrapping `form.save()` in `transaction.atomic()` + `try/except IntegrityError` in both `event_create`/`event_edit`; regression test `test_save_race_converts_integrity_error_to_duplicate_field_error` added.

### F3 — Missing test: `window_start > window_end` rejection

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency (test coverage)
- **Location**: events/tests.py (EventCreateViewTests)
- **Detail**: `EventForm.clean()` validates both `window_start <= window_end` and `window_end <= start_date`, but only the second half (`test_window_end_after_start_date_rejected`) has a test. The first half (`window_start` after `window_end`) is implemented but untested.
- **Fix**: Add `test_window_start_after_window_end_rejected`, mirroring the existing window-order test with `window_start`/`window_end` swapped.
- **Decision**: FIXED — added as a byproduct of F2's fix; confirmed.

### F4 — "No-op edit" test isn't actually a no-op

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency (test clarity)
- **Location**: events/tests.py, `test_noop_edit_succeeds`
- **Detail**: The test changes `description` (not literally a no-op), though it does correctly verify the duplicate check excludes the instance's own pk on unchanged name/dates — which is the behavior Phase 3's Success Criteria 3.4 actually asks for. Functionally correct, just a slightly misleading name.
- **Fix**: Rename to `test_edit_with_unchanged_name_and_dates_succeeds` for clarity.
- **Decision**: FIXED — renamed, 24/24 tests still pass.

### F5 — `DEBUG` defaults fail-open when unset (pre-existing, out of scope)

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: stay_recon/settings.py:34 — `DEBUG = os.environ.get('DEBUG', 'True') == 'True'`
- **Detail**: Defaults to `True` (debug on) if the env var is absent. `render.yaml` explicitly sets `DEBUG="False"` so production is safe today, but any alternate deploy path that forgets the var would silently run with debug on. Pre-existing from F-01, not touched by this change's diff — flagged for awareness only.
- **Fix**: None in this change — filed as GH #17 instead of an inline fix, per established preference for out-of-scope findings.
- **Decision**: FILED AS ISSUE — GH #17, not fixed inline per user preference.
