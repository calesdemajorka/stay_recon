<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Participant & Staff Lists + Access-Link Generation (S-03) Implementation Plan

- **Plan**: context/changes/participant-staff-lists-and-links/plan.md
- **Scope**: Phase 1 of 4
- **Date**: 2026-09-18
- **Verdict**: APPROVED
- **Findings**: 0 critical, 0 warnings, 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

## Findings

### F1 — Combined test class deviates from one-class-per-model convention

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: `access/tests.py:84` (`ParticipantStaffMemberModelTests`)
- **Detail**: Combines `Participant` and `StaffMember` tests into one class, deviating from `rooms/tests.py`'s one-class-per-model convention (`RoomModelTests`, `PendingUploadModelTests`). Arguably justified since the cross-field invariant tests (event/role/label) span both models symmetrically.
- **Fix**: No action needed — the combined class reads clearly given the tests are inherently paired; splitting would duplicate setup for no real benefit.
- **Decision**: SKIPPED

### F2 — No `search_fields` on Participant/StaffMember admin

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: `access/admin.py:12-13,17-18` (`ParticipantAdmin`/`StaffMemberAdmin`)
- **Detail**: Matches the plan's literal contract (list_display only), but `RoomAdmin` sets `search_fields = ['room_number']` as precedent, and `search_fields=['name','email']` would be a natural, low-cost addition once these lists grow.
- **Fix**: Add `search_fields = ['name', 'email']` to both `ParticipantAdmin` and `StaffMemberAdmin`.
- **Decision**: FIXED — `search_fields = ['name', 'email']` added to both admin classes. Verified: `uv run manage.py test access` (30/30) passing.

## Notes

- Plan Drift Detection agent: **zero drift** — exact match across all of Phase 1 (`Participant`, `StaffMember`, `PendingListUpload` models, migration, admin registrations, and every test). Confirmed the plan's Critical Implementation Details (the three `clean()` invariants: event, role, label==email) were correctly implemented in that order, with the `access_link_id` guard matching the documented caveat verbatim. All "What We're NOT Doing" boundaries respected — no `events` app changes, no booking-state or check-in/pack-handoff fields added.
- Safety & Pattern agent: no CRITICAL or WARNING findings. Explicitly verified: the `access_link_id` guard correctly prevents a `RelatedObjectDoesNotExist` crash on a partially-filled form; the three `self.access_link.X` accesses within one `clean()` call are not a real N+1 (Django's `OneToOneField` descriptor caches the related object after first access); the "plain `.create()`/`.save()` skip `clean()`" caveat is accurately documented, not overstated; the migration's `UniqueConstraint`s correctly mirror `events`/`rooms`' already-proven `Lower(Trim())` pattern with no Postgres/SQLite divergence risk.
- Success criteria: all automated checks re-run and passing (`manage.py check`; `makemigrations --check --dry-run` — no changes detected; `manage.py test access` 30/30; full suite 91/91). All 10 Progress rows (automated + manual) carry the commit SHA and are backed by specific, named tests or the confirmed admin walkthrough — no rubber-stamping concern.
