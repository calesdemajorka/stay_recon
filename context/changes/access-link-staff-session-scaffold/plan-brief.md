# Access-Link & Staff-Session Scaffold (F-02) — Plan Brief

> Full plan: `context/changes/access-link-staff-session-scaffold/plan.md`
> Frame brief: `context/changes/access-link-staff-session-scaffold/frame.md`
> Research: `context/changes/access-link-staff-session-scaffold/research.md`

## What & Why

F-02 builds a no-account, token-based access-link verification mechanism for participants, and a scoped staff-session mechanism — both usable by any future route that needs them. This is a foundation: nothing downstream (S-03's link generation, S-04's participant booking, S-08's staff check-in) can be demoed until a working verification mechanism exists.

## Starting Point

Fully greenfield — no token, signing, session-scoping, or participant/staff model exists anywhere in the codebase. `accounts.User` already has Django's built-in `is_staff` (admin-access) field, a naming collision this change deliberately avoids echoing. `rooms.PendingUpload` is this codebase's own precedent for DB-backed short-lived token state.

## Desired End State

A participant opening a valid link sees confirmation it's recognized for the right event; an invalid/expired/revoked link shows a clear message instead of a raw error. A staff member opening a valid staff link gets a session scoped to that one event, which persists across follow-up requests without re-presenting the token, and never grants access to a different event.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Staff access model | Link/session-scoped, not a real `User` account | PRD's own Non-Goals excludes the audit trail that would justify a credentialed account's extra complexity. | Frame |
| Token storage | DB-backed opaque token (`AccessLink` model) | Matches this codebase's own `PendingUpload` precedent; trivial revocation; simple expiry check. | Plan (user Q&A) |
| Creation interface | Model + verification only, no creation helper | Matches the roadmap's explicit "verification-only" boundary for F-02; avoids guessing S-03's not-yet-planned interface. | Plan (user Q&A) |
| Expiry source | `Event.window_end` (the existing booking window) | Only field that actually exists today; zero `events` app changes. | Plan (user Q&A) |
| Revocation | `is_revoked` flag included now | Cheap to add; keeps the door open even before S-03 builds any revoke UI. | Plan (user Q&A) |
| Data model shape | One shared `AccessLink` model (role field: participant/staff) | Structurally identical needs (token, event, expiry) — avoids duplicating verification logic across two tables. | Plan |
| App placement | New `access` app, not extending `events`/`rooms` | Will be referenced by S-03/S-04/S-08 independent of `events`' own concerns — same reasoning that gave `rooms` its own app. | Plan |
| Expiry timing | Checked live against `event.window_end`, never snapshotted | FR-005 lets the organiser edit the booking window anytime; a snapshot would go stale. | Plan |

## Scope

**In scope:** `access` app with `AccessLink` model, `verify_access_link()` function, minimal placeholder views proving both the participant and staff paths work end-to-end, staff session establishment + event-scoped session check helper.

**Out of scope:** link-generation UI or participant/staff list upload (S-03), real booking UI (S-04), real check-in/on-day-edit/pack-handoff UI (S-08), any `StaffAssignment`/real `User` account for staff, staff logout capability, any `events.Event` schema changes, a token-creation helper function.

## Architecture / Approach

A new `access` Django app holds one `AccessLink` model (event FK, role, label, token, is_revoked). `verify_access_link(token, role=...)` is the single verification primitive both participant and staff routes call. Participants re-verify their token on every request (no session — matches "no account"). Staff verification is a one-time link-consuming view that sets `request.session['staff_access_link_id']`; a companion `get_staff_access_link(request, event)` helper re-validates live on every subsequent request, checking not just validity but that the session's event matches the one being requested — the session-based analogue of the codebase's existing `organiser=request.user` scoping pattern.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. `access` app scaffold | `AccessLink` model, admin, migration | Low — straightforward, well-precedented by `rooms`' own scaffold phase |
| 2. Participant token verification | `verify_access_link()` + placeholder view proving the path works | Getting the invalid-link UX right (friendly message, not raw 404/500) |
| 3. Staff session mechanism | Link-consuming view + session, event-scoped session-check helper | Session/event-mismatch correctness — the one genuinely new scoping pattern this codebase hasn't needed before |

**Prerequisites:** `F-01` (done).
**Estimated effort:** not estimated (roadmap convention — no time units; sequence, not schedule).

## Open Risks & Assumptions

- The frame brief's staff-access reading (link/session, not real login) is a well-evidenced but not 100%-certain interpretation of the PRD's ambiguous "login with a staff role" wording — flagged as MEDIUM confidence there, worth a one-line PRD clarification note separately from this plan.
- Reusing `Event.window_end` as the link-expiry cutoff is an explicit assumption (per the frame's Open Question 2), not a confirmed PRD fact — revisit if "check-in window" is later clarified to mean something distinct.
- No revocation UI exists yet (that's S-03's job) — the `is_revoked` flag is set-able only via `/admin/` until then.

## Success Criteria (Summary)

- A participant's link, once created (via `/admin/` for now), correctly identifies their event and gracefully rejects once expired or revoked.
- A staff member's link establishes a session that survives follow-up requests without re-presenting the token, and never leaks access to a different event.
- Every future slice (S-03 onward) can now assume a working access-link verification mechanism exists.
