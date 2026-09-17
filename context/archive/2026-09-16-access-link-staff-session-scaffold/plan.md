# Access-Link & Staff-Session Scaffold (F-02) Implementation Plan

## Overview

Builds a no-account, token-based access-link verification mechanism for participants, and a scoped staff-session mechanism — both usable by any future route that needs them, per this roadmap item's own definition (`roadmap.md:95`). This is roadmap item `F-02` (`FR-004`, Access Control §Participant/§Event staff). Per the roadmap's explicit boundary (`roadmap.md:103`), this change builds **verification only** — the link-generation UI belongs to `S-03`.

## Current State Analysis

- Fully greenfield: no token/signing/session-scoping code exists anywhere in the codebase today. `AUTHENTICATION_BACKENDS` is unset (default `ModelBackend` only). No `Participant`/`StaffAssignment`-shaped model exists in any app.
- `accounts.User` already has Django's built-in `is_staff` boolean, meaning "can access `/admin/`" (`accounts/admin.py:9,13`) — an existing naming collision this change must not reuse or echo for the product's "event staff" concept.
- `rooms.PendingUpload` (`rooms/models.py:27-39`) is this codebase's own precedent for modeling short-lived, token-adjacent state as a dedicated Postgres row rather than session storage.
- Every existing organiser-facing view scopes by `get_object_or_404(Model, pk=pk, organiser=request.user)`, returning 404 not 403 on mismatch (`events/views.py:36,48`). Access-link routes have **no `request.user`** to scope by — the token itself is the sole credential, a meaningfully different threat model (see Critical Implementation Details).
- `events.Event` has exactly one window pair, `window_start`/`window_end`, documented everywhere as the participant *booking* window (FR-008). No separate "check-in window" field exists.
- Full research and neutral technique comparison: `context/changes/access-link-staff-session-scaffold/research.md`. Framing of the staff-access ambiguity (link/session vs. real login) and its resolution: `context/changes/access-link-staff-session-scaffold/frame.md`.

## Desired End State

A new `access` app exists with an `AccessLink` model (participant or staff role, event-scoped, revocable). `verify_access_link(token)` validates a token against expiry (`event.window_end`) and revocation, returning the `AccessLink` or `None`. A participant can open a placeholder URL carrying a valid token and see confirmation their link is recognized for the correct event; an invalid/expired/revoked token shows a clear "link no longer valid" message, not a raw 404. A staff member can open a placeholder staff URL carrying a valid staff-role token, which establishes a session scoped to that one event; a companion helper lets any future staff-facing view check "is there a valid staff session for event X" the same way organiser views check `organiser=request.user`.

**Verification**: `uv run manage.py test access` passes; `uv run manage.py check` passes; manually opening a generated participant/staff link (created via `/admin/` or the Django shell, since link-generation UI is S-03's job) on the live Render deploy reaches the correct placeholder screen; an expired or revoked link shows the invalid-link message instead of a 500 or raw 404.

### Key Discoveries

- F-01's own plan ended each mechanism with a genuine, if empty, end-to-end proof ("an organiser can... reach an empty, account-scoped dashboard... proves the auth wrapper works with nothing else built yet") rather than stopping at unit-tested internals alone. This plan follows the same pattern: minimal placeholder views prove both the participant and staff mechanisms work end-to-end, without building any real business UI (that's S-03/S-04/S-08's job).
- Because access-link verification has no `request.user`, this codebase's core security invariant here is token entropy, not object-scoping — `secrets.token_urlsafe(32)` (256 bits) makes guessing infeasible regardless of URL structure.
- The booking window (`Event.window_end`) can be edited by the organiser at any time (FR-005) — expiry must be checked **live** against `access_link.event.window_end` at verification time, never snapshotted onto the `AccessLink` row at creation time, or an organiser's window edit wouldn't affect already-issued links.

## What We're NOT Doing

- No link-generation UI or participant/staff list upload — that's `S-03`'s job entirely (`roadmap.md:103`).
- No real booking UI, room list, or preferences form for participants — that's `S-04`.
- No real check-in, on-day edit, or starter-pack UI for staff — that's `S-08`.
- No `StaffAssignment`/real `User` account for staff — the frame brief (`frame.md`) resolved this: staff access is a link/session mechanism like participants, not a credentialed account, since the PRD's own Non-Goals excludes the audit trail that would justify the extra complexity.
- No staff "logout"/session-clear capability — not requested by any FR; a session simply expires the same way the token does (re-checked live against `event.window_end` on every staff-scoped request).
- No changes to `events.Event`'s schema — expiry reuses the existing `window_end` field rather than adding a new "check-in window" concept, per the decision above.
- No token-creation helper function — `S-03` will create `AccessLink` rows directly using the model this change defines, per the decision above.

## Implementation Approach

Three phases: the data layer first (`AccessLink` model — nothing UI-reachable yet), then the participant verification path (function + minimal placeholder view), then the staff session path (link-consuming view that establishes a session, plus the companion event-scoped session-check helper future staff views will reuse). Each phase ends with a genuine, if minimal, working proof — matching F-01's precedent.

## Critical Implementation Details

- **No `request.user` scoping — token entropy is the security boundary.** Every other view in this codebase scopes by `organiser=request.user`. Access-link routes have no such actor to check; `verify_access_link()` must look up by exact token match only (never partial match, never by a guessable identifier like an incrementing id), and the `token` field must be `unique=True` with `db_index=True`. Treat a wrong-role token used on the wrong route (e.g. a participant token opened at the staff URL) as invalid, the same as an unknown token — never reveal that the token was "real but wrong role."
- **Expiry is computed live, never snapshotted.** `verify_access_link()` must compare against `access_link.event.window_end` at call time (a live DB read through the FK), not a copy stored on the `AccessLink` row — otherwise an organiser's FR-005 edit to the booking window wouldn't retroactively affect already-issued links.
- **Invalid/expired/revoked tokens render a friendly message, not a raw 404.** Unlike the rest of the codebase's deliberate 404-not-403 convention (which hides whether an organiser-owned resource exists from an unauthorized viewer), a link-holder legitimately needs to know their link expired rather than getting an unexplained 404 — the token space itself is unguessable regardless of the response shape, so there's no information-disclosure cost to a clear "this link is no longer valid" page.

## Phase 1: `access` app scaffold — AccessLink model

### Overview

Creates the `access` app and the `AccessLink` model (participant or staff role, event-scoped, revocable), registers it with the admin.

### Changes Required

#### 1. New app: `access`

**File**: `access/__init__.py`, `access/apps.py`, `access/models.py`, `access/admin.py`, `access/migrations/0001_initial.py`

**Intent**: Give the access-link mechanism its own app, since it will be referenced by `S-03`, `S-04`, and `S-08` independent of `events`' own scheduling concerns — mirroring why `rooms` got its own app rather than extending `events`.

**Contract**: `access/models.py` defines `AccessLink(models.Model)`: `event` (`ForeignKey` to `events.Event`, `on_delete=CASCADE`, `related_name='access_links'`), `role` (`CharField` with `choices=[('participant', 'Participant'), ('staff', 'Staff')]`), `label` (`CharField`, max_length 255 — an identifying string such as an email or name; `S-03` owns its exact semantics), `token` (`CharField`, max_length 64, `unique=True`, `db_index=True`), `is_revoked` (`BooleanField`, default `False`), `created_at` (`DateTimeField`, `auto_now_add=True`). `access/admin.py` registers `AccessLinkAdmin` with `list_display = ['event', 'role', 'label', 'is_revoked', 'created_at']` (omit the raw `token` column from the list view; it's visible on the detail page if needed for manual testing).

#### 2. Project settings & build filter

**File**: `stay_recon/settings.py`, `render.yaml`

**Intent**: Register the new app; without the build-filter entry, pushes touching only `access/**` won't trigger a Render rebuild, the same gap fixed for every prior app.

**Contract**: `INSTALLED_APPS` gains `'access'`. `render.yaml`'s `buildFilter.paths` gains `access/**`.

### Success Criteria

#### Automated Verification

- `uv run manage.py makemigrations --check --dry-run` reports no missing migrations
- `uv run manage.py migrate` applies cleanly against a freshly deleted local `db.sqlite3`
- `uv run manage.py check` passes with no errors
- Unit test: two `AccessLink` rows may share the same `event` (multiple participants/staff per event) but `token` uniqueness is enforced globally (`IntegrityError` on a duplicate token)
- Unit test: deleting an `Event` cascades to delete its `AccessLink` rows

#### Manual Verification

- `AccessLink` appears in `/admin/` with the expected list columns, and a row can be created manually via the admin for use in Phase 2/3 manual testing

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 2: Participant token verification

### Overview

The verification function and a minimal placeholder view proving a participant's link is correctly recognized, rejected when invalid/expired/revoked, and never confused with a staff-role token.

### Changes Required

#### 1. Verification function

**File**: `access/services.py` (new)

**Intent**: A single, reusable function any future route can call to validate a token and get back the `AccessLink` it authorizes, or `None`.

**Contract**: `verify_access_link(token, *, role=None)` — looks up `AccessLink.objects.filter(token=token, is_revoked=False)`, optionally filtered by `role` when the caller only wants one kind (e.g. the staff-login view passes `role='staff'`); checks `timezone.now().date() <= access_link.event.window_end`; returns the `AccessLink` instance on success, `None` on any failure (unknown token, revoked, expired, or wrong role). Never raises for an invalid token — callers branch on `None`.

#### 2. Placeholder participant view

**File**: `access/views.py` (new), `stay_recon/urls.py`, `templates/access/participant_link.html` (new), `templates/access/link_invalid.html` (new)

**Intent**: Prove the participant verification path end-to-end without building any real booking UI — `S-04` replaces this view's content, not its URL or verification call.

**Contract**: `path('participant/<str:token>/', participant_access, name='participant_access')`. `participant_access(request, token)` calls `verify_access_link(token, role='participant')`; on success renders `templates/access/participant_link.html` showing the event's name and the participant's `label` (proving the right `AccessLink` was resolved); on failure renders `templates/access/link_invalid.html` with a "this link is no longer valid" message. Both templates extend `base.html`.

### Success Criteria

#### Automated Verification

- Unit test: a valid, unexpired, non-revoked participant token resolves via `verify_access_link()` to the correct `AccessLink`
- Unit test: an unknown token returns `None`
- Unit test: a revoked token (`is_revoked=True`) returns `None` even though otherwise valid
- Unit test: a token for an event whose `window_end` has passed returns `None`
- Unit test: a staff-role token passed to `verify_access_link(token, role='participant')` returns `None` (role mismatch rejected)
- Unit test: `GET` to the participant URL with a valid token renders 200 with the event name in the response
- Unit test: `GET` to the participant URL with an unknown/expired/revoked token renders 200 with the invalid-link message (not a 404, not a 500)

#### Manual Verification

- On the live Render deploy: create an `AccessLink` via `/admin/` for a real event, open its participant URL, confirm the event name shows correctly
- Manually expire a link (edit the event's `window_end` to the past via `/admin/` or `/events/<pk>/edit/`) and confirm re-opening the same link now shows the invalid-link message

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 3: Staff session mechanism

### Overview

A link-consuming view that verifies a staff-role token and establishes a session scoped to that one event, plus a companion helper any future staff-facing view can use to check "is there a valid staff session for this event" — the session-based analogue of `get_object_or_404(..., organiser=request.user)`.

### Changes Required

#### 1. Staff session helpers

**File**: `access/services.py`

**Intent**: Establish and check a staff session without creating any `User`/`StaffAssignment` account, per the frame's resolution.

**Contract**: `establish_staff_session(request, access_link)` — sets `request.session['staff_access_link_id'] = access_link.pk`. `get_staff_access_link(request, event)` — reads `request.session.get('staff_access_link_id')`; if present, re-fetches that `AccessLink` and re-validates it live (not revoked, not expired, `role == 'staff'`, **and** `access_link.event_id == event.pk`); returns the `AccessLink` on success, `None` otherwise (covers: no session, expired since session was set, revoked since session was set, or a session valid for a *different* event than the one being checked — the direct analogue of the existing cross-organiser 404 pattern, applied to sessions instead of `request.user`).

#### 2. Placeholder staff views

**File**: `access/views.py`, `stay_recon/urls.py`, `templates/access/staff_link.html` (new), `templates/access/staff_dashboard.html` (new)

**Intent**: Prove the staff session path end-to-end — link in, session established, a second request without the token still recognized, an event mismatch correctly rejected.

**Contract**: `path('staff/<str:token>/', staff_login, name='staff_login')` and `path('staff/events/<int:event_pk>/', staff_dashboard, name='staff_dashboard')`. `staff_login(request, token)` calls `verify_access_link(token, role='staff')`; on success calls `establish_staff_session(request, access_link)` and redirects to `staff_dashboard` for that event; on failure renders `templates/access/link_invalid.html` (same template Phase 2 introduced). `staff_dashboard(request, event_pk)` looks up the `Event` by `pk` (no `organiser` scoping — this route is staff-session-gated, not organiser-gated), calls `get_staff_access_link(request, event)`; on success renders `templates/access/staff_dashboard.html` showing the event name and the staff member's `label`; on failure renders `link_invalid.html`.

### Success Criteria

#### Automated Verification

- Unit test: opening the staff URL with a valid staff token establishes a session and redirects to that event's staff dashboard
- Unit test: opening the staff URL with a participant-role token is rejected (renders the invalid-link message, no session set)
- Unit test: after a valid staff login, a second request to the staff dashboard (no token in the URL this time) succeeds using the session alone
- Unit test: a staff session established for event A does not grant access to event B's staff dashboard (`get_staff_access_link` returns `None` for the mismatched event)
- Unit test: revoking the underlying `AccessLink` after a session was established causes the next dashboard request to fail (live re-validation, not a cached session grant)
- Unit test: a staff session request with no prior login (`staff_access_link_id` never set) renders the invalid-link message, not a 500

#### Manual Verification

- On the live Render deploy: create a staff-role `AccessLink` via `/admin/`, open its staff URL, confirm redirect to the event's staff dashboard showing the correct event name
- Reload the staff dashboard URL directly (no token) in the same browser session and confirm it still works
- Open the same staff dashboard URL in a private/incognito window (no session) and confirm it shows the invalid-link message rather than an error

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before considering this change complete.

---

## Testing Strategy

### Unit Tests

- `AccessLink` uniqueness/cascade behavior (Phase 1)
- `verify_access_link()` success/failure matrix: unknown, revoked, expired, wrong-role (Phase 2)
- Participant placeholder view rendering (Phase 2)
- Staff session establishment, cross-event rejection, live re-validation on revoke (Phase 3)

### Integration Tests

- Full participant flow: create `AccessLink` → open participant URL → see correct event
- Full staff flow: create `AccessLink` → open staff URL → session established → dashboard reachable on a follow-up request without the token → different event's dashboard still rejected

### Manual Testing Steps

1. On the live Render deploy, create a participant `AccessLink` via `/admin/` for a real event; open its URL; confirm the event name renders.
2. Edit that event's `window_end` to a past date; reopen the same link; confirm it now shows "link no longer valid."
3. Create a staff `AccessLink` for a different event; open its staff URL; confirm redirect to that event's staff dashboard.
4. Reload the staff dashboard directly (same browser) — confirm it still works via session alone.
5. Open the staff dashboard URL in a private window — confirm it shows the invalid-link message, not an error.

## Performance Considerations

None specific to this change — token lookup is a single indexed query (`unique=True`, `db_index=True` on `token`), and the PRD's own NFR requires a participant sees their suggested room within 2 seconds, well within reach of a single indexed lookup plus one FK traversal for `window_end`.

## Migration Notes

Purely additive: a new app and one new table, no existing data affected. No production schema reset needed — a normal `migrate` on top of the existing schema.

## References

- Research: `context/changes/access-link-staff-session-scaffold/research.md`
- Frame: `context/changes/access-link-staff-session-scaffold/frame.md`
- Prior app-separation precedent: `context/archive/2026-09-14-csv-upload-room-mapping/plan.md` ("App placement" decision, reused verbatim for this change's own app-placement rationale)
- Prior end-to-end-placeholder precedent: `context/archive/2026-09-11-organiser-auth-app-scaffold/plan-brief.md` ("empty, account-scoped landing page... proves the auth wrapper works with nothing else built yet")

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles.

### Phase 1: `access` app scaffold — AccessLink model

#### Automated

- [x] 1.1 `makemigrations --check --dry-run` reports no missing migrations — d1c3ece
- [x] 1.2 `migrate` applies cleanly against a freshly deleted local `db.sqlite3` — d1c3ece
- [x] 1.3 `manage.py check` passes — d1c3ece
- [x] 1.4 Token uniqueness enforced (`IntegrityError` on duplicate) — d1c3ece
- [x] 1.5 Deleting an Event cascades to delete its AccessLinks — d1c3ece

#### Manual

- [x] 1.6 AccessLink appears in `/admin/` with expected columns; a row can be created manually — d1c3ece

### Phase 2: Participant token verification

#### Automated

- [x] 2.1 Valid token resolves to the correct AccessLink — 8d46b24
- [x] 2.2 Unknown token returns None — 8d46b24
- [x] 2.3 Revoked token returns None — 8d46b24
- [x] 2.4 Expired token (window_end passed) returns None — 8d46b24
- [x] 2.5 Staff-role token rejected when role='participant' requested — 8d46b24
- [x] 2.6 Valid participant URL renders 200 with event name — 8d46b24
- [x] 2.7 Invalid participant URL renders invalid-link message, not 404/500 — 8d46b24

#### Manual

- [x] 2.8 Live: participant link shows correct event name — 8d46b24
- [x] 2.9 Live: expiring the event's window_end invalidates the link — 8d46b24

### Phase 3: Staff session mechanism

#### Automated

- [x] 3.1 Valid staff token establishes session and redirects to dashboard — 51a35e2
- [x] 3.2 Participant-role token rejected on staff URL, no session set — 51a35e2
- [x] 3.3 Second request to dashboard succeeds via session alone (no token) — 51a35e2
- [x] 3.4 Session for event A rejected on event B's dashboard — 51a35e2
- [x] 3.5 Revoking the AccessLink after session established fails the next request — 51a35e2
- [x] 3.6 No prior session renders invalid-link message, not 500 — 51a35e2

#### Manual

- [x] 3.7 Live: staff link redirects to correct event dashboard — 51a35e2
- [x] 3.8 Live: dashboard reachable on reload without token — 51a35e2
- [x] 3.9 Live: private/incognito window shows invalid-link message — 51a35e2
