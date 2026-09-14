# Create Event — Plan Brief

> Full plan: `context/changes/create-event/plan.md`

## What & Why

StayRecon has no domain models yet — only `accounts` (auth). This change adds the project's first real domain feature: an organiser creates an event (name, dates, description, booking window), sees their events on the dashboard, and can edit them. It's roadmap item `S-01`, the smallest first vertical slice, proving the auth scaffold (`F-01`) actually works end-to-end before CSV upload, participants, or bookings are built on top.

## Starting Point

No `Event` model, no second app. `templates/accounts/dashboard.html` is a placeholder ("nothing to show yet"). `accounts.User` is the only domain model and the organiser identity.

## Desired End State

A logged-in organiser can create an event, see it listed on their dashboard, and edit it. Creating a duplicate (same normalized name + dates, same organiser) is blocked with a friendly error; editing never trips that guardrail on a no-op change. One organiser can never see or edit another's events.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) |
| --- | --- | --- |
| Duplicate match semantics | Normalized: trimmed + case-insensitive name, exact date match | Matches the case-insensitive-email precedent already in this codebase; catches the realistic accidental-recreate case. |
| Event date shape | Date range (`start_date`/`end_date`) | User's call — supports multi-day events, not just single-day. |
| Extra fields | Optional `description` field added | User's call — gives organisers a place for context beyond name/date. |
| Booking window | Included now on `Event` (`window_start`/`window_end`), required, defaulted to `start_date -14d`/`-3d`, organiser-overridable | User's call — FR-008 says the window is "configured at creation time," so the field belongs on the model from the start rather than a later migration. |
| Edit scope | Full edit — all fields, same form as create | User's call — matches FR-001's explicit "editing is never blocking" requirement; trivial given the small field set. |
| List view | Dashboard shows the organiser's own events | User's call — without it, "edit" is unreachable; replaces the existing placeholder. |
| Duplicate check scope | Per-organiser, not global | Matches PRD Access Control: organisers "can only see and manage their own events" — two organisers can coincidentally share a name+date pair without conflict. |

## Scope

**In scope:** `events` app, `Event` model with per-organiser duplicate constraint, create form/view, dashboard event list, edit form/view with object-level scoping (404 on cross-organiser access).

**Out of scope:** CSV/room data (`S-02`), participant/staff lists and access links (`S-03`/`F-02`), deleting events, past-date validation, any JS-driven live window preview, a dedicated `events/urls.py` (follows `accounts`'s direct-`path()` convention), overlap-based duplicate detection.

## Architecture / Approach

New Django app `events`, mirroring `accounts`'s existing shape (models/admin/forms/views, no per-app `urls.py`). The duplicate guardrail is enforced twice: a DB-level `UniqueConstraint` using `Lower(Trim('name'))` + dates + organiser (closes the race-condition class, same pattern as `accounts.User.email`), and a form-level `clean()` check that surfaces a friendly error before that constraint would raise `IntegrityError` — directly copying `SignupForm.clean_email`'s established shape. The booking-window default is computed server-side in the form's `clean()` when left blank.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Events app scaffold & Event model | `events` app, `Event` model, DB constraint, admin | Constraint expression (`Lower(Trim(...))`) must actually enforce cross-organiser independence correctly |
| 2. Create event | Form, view, template, duplicate guardrail, window defaults | Window default math and validation ordering (`window_start <= window_end <= start_date`) |
| 3. Event list & edit | Dashboard integration, edit view, object-level scoping | 404-not-403 on cross-organiser access — must leak no information |

**Prerequisites:** `F-01` (done).
**Estimated effort:** not estimated (roadmap convention — no time units; sequence, not schedule).

## Open Risks & Assumptions

- Scope grew beyond the roadmap's original `S-01` outcome (`FR-001` only) to include the date-range shape, optional description, and the booking-window fields (`FR-008`) — all explicit user decisions this session, not silent creep. Worth a quick roadmap note if `S-04`'s later plan expected to introduce these fields itself.
- No past-date validation on `start_date` or the booking window — an organiser can create an event dated in the past; no FR asks for a guardrail here, but worth revisiting if it becomes a real support issue.

## Success Criteria (Summary)

- An organiser can create, list, and edit their own events entirely on the live Render deploy.
- Duplicate creation (same organiser, normalized name, dates) is blocked with a friendly error, not a 500.
- One organiser can never see or edit another organiser's events (404, not 403, on a guessed edit URL).
