<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Access-Link & Staff-Session Scaffold (F-02) Implementation Plan

- **Plan**: context/changes/access-link-staff-session-scaffold/plan.md
- **Scope**: Phase 3 of 3 (full plan review)
- **Date**: 2026-09-17
- **Verdict**: APPROVED
- **Findings**: 0 critical, 1 warning, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | WARNING |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

## Findings

### F1 — Staff session not rotated on privilege elevation

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: `access/services.py:26-29` (`establish_staff_session`)
- **Detail**: `establish_staff_session` sets `request.session[STAFF_SESSION_KEY] = access_link.pk` directly, with no `request.session.cycle_key()` call. Since this flow never calls `django.contrib.auth.login()`, Django never rotates the session id here — an anonymous session that later gains staff privilege keeps the same session id/cookie value throughout. OWASP recommends rotating the session id on any privilege-elevating event, not just a traditional login. Lower-impact than a normal login flow given the plan's explicit "no User account" design, but a real, standard gap.
- **Fix**: Call `request.session.cycle_key()` at the top of `establish_staff_session`, before writing the session key.
- **Decision**: FIXED — `establish_staff_session` now calls `request.session.cycle_key()` before writing the session key. Verified: `uv run manage.py test access` (18/18) and full suite (79/79) passing.

### F2 — Event-id existence distinguishable via raw 404 on staff dashboard

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: `access/views.py:25` (`staff_dashboard`)
- **Detail**: `get_object_or_404(Event, pk=event_pk)` returns a genuine 404 for a nonexistent `event_pk`, distinguishable (different status code) from the 200 "link no longer valid" response returned for a real event with no/wrong staff session. Doesn't leak the actual credential (the token), only whether a numeric event id exists — low impact, and consistent with existing codebase precedent of 404-for-missing-object elsewhere.
- **Fix**: No action required unless byte-for-byte response parity with the invalid-link message is wanted for this route too.
- **Decision**: FIXED — `staff_dashboard` now looks up the event with `Event.objects.filter(pk=event_pk).first()` instead of `get_object_or_404`, so a nonexistent `event_pk` renders the same `link_invalid.html` (200) as any other invalid session, not a 404. New test `test_nonexistent_event_shows_invalid_message_not_404`.

## Notes

- Plan Drift Detection agent: **zero drift** across all 3 phases — every planned change (model, admin, `verify_access_link`, participant view, `establish_staff_session`/`get_staff_access_link`, staff views, URLs, settings/render.yaml) verified as exact MATCH. The `templates/access/staff_link.html` mentioned in the plan's Phase 3 file list but never created was confirmed as a correct, deliberate simplification (no view ever renders its own template there — `staff_login` only redirects or reuses `link_invalid.html`), not a missing item. All six "What We're NOT Doing" boundaries respected (no link-generation UI, no StaffAssignment/User account, no staff logout, no Event schema change, no token-creation helper) — verified via grep with zero hits.
- Safety & Pattern agent: no CRITICAL issues. Explicitly verified every design invariant from the plan's Critical Implementation Details section: exact-match-only token lookup, `unique+db_index` on `token`, wrong-role and unknown tokens indistinguishable (same template, same 200), live expiry checked on every call (no snapshotted field), `get_staff_access_link` re-validates all four conditions fresh on every call with `select_related('event')` (no N+1), no unescaped template output, no hardcoded secrets. Pattern compliance clean — `access/tests.py` follows the established `TestCase`/`make_event`-helper/`reverse()` conventions from `rooms/tests.py`/`events/tests.py`; the deliberate absence of `@login_required` on `access/views.py` (unlike every `events`/`rooms` view) is correct given the plan's explicitly different no-`request.user` threat model, not a mismatch.
- Success criteria: all automated checks re-run and passing (`manage.py check`; `makemigrations --check --dry-run` — no changes detected; `manage.py test access` 17/17; `manage.py test` full suite 78/78). All 19 manual Progress checkboxes across the 3 phases carry commit SHAs and are backed by specific, named tests or explicitly described live-deploy steps — no rubber-stamping concern.
