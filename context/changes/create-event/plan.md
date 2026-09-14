# Create Event Implementation Plan

## Overview

StayRecon has one app (`accounts`) and no domain models yet. This plan adds the project's second app, `events`, with an `Event` model scoped per-organiser, and the create/edit flow an organiser uses to open a new event. This is roadmap item `S-01` — the smallest first vertical slice, proving `F-01`'s login + app scaffold works end-to-end before anything heavier (CSV upload, participants, bookings) is built on top.

## Current State Analysis

- No `Event` model or `events` app exists (`code`, confirmed directly — no `class Event` anywhere in the repo).
- `accounts.User` is the only domain model; it's the organiser identity (per F-01's plan `Definitions` table). `AUTH_USER_MODEL = 'accounts.User'` is already set.
- `templates/accounts/dashboard.html` is a placeholder ("Your account-scoped dashboard. Nothing to show yet.") — the natural home for an event list.
- `render.yaml`'s `buildFilter.paths` lists `accounts/**` and `templates/**` but not `events/**` — needs the same fix Phase 1 of F-01 applied for `accounts/**`, or a new `events` app's changes won't trigger a Render rebuild.
- `accounts/forms.py`'s `SignupForm.clean_email` is the established pattern for a friendly pre-save duplicate check (query first, raise `ValidationError` on the field, before Django's own DB constraint would raise `IntegrityError`) — this plan's duplicate-name check follows the same shape.
- `stay_recon/urls.py` wires app views directly with `path(...)` — no per-app `urls.py` include exists for `accounts`. This plan follows the same convention for `events`.

## Definitions

| Term | Decided meaning | Origin | On degenerate data | Verified by |
| ---- | --------------- | ------ | ------------------- | ----------- |
| Duplicate event | Same organiser, same normalized name (trimmed, case-insensitive), same `start_date`, same `end_date` | user (this session) | `"Team Offsite"` and `"team offsite "` on the same dates, same organiser, must collide as a duplicate | Phase 1 DB constraint (`Lower(Trim('name'))` + dates + organiser); Phase 2 unit test |
| Booking window | `window_start`/`window_end` date fields on `Event`, defaulted to `start_date - 14 days` / `start_date - 3 days` when left blank at creation, organiser-overridable | user (this session, per FR-008's "configured at creation time") | Organiser leaves both blank → computed from `start_date`; organiser supplies one or both → those values are kept as-is | Phase 2 unit test: default computation; explicit override honored |

## Desired End State

An organiser, logged in, can create an event (name, start/end date, optional description, booking window), see it in a list on their dashboard, and edit any field of an existing event they own — with the duplicate-name-and-date guardrail enforced on create (and on edit, if the edited values would collide with a *different* existing event) but never blocking a no-op edit of the same event. An organiser can only ever see or edit their own events.

Verification: `uv run manage.py check` passes with no errors; the live create → see-in-list → edit loop works end-to-end on Render; a second organiser account cannot see or edit the first organiser's events.

### Key Discoveries:

- Django's `UniqueConstraint` supports expressions (`Lower`, `Trim`) directly since Django 2.1/4.0 — a true DB-level constraint can enforce the normalized-duplicate rule, not just a form-level check, closing the same race-condition class F-01's `accounts.User.email` uniqueness already closes.
- Because the duplicate rule is scoped per-organiser (PRD Access Control: organisers "can only see and manage their own events"), the constraint includes `organiser` — two different organisers can have identically-named events on the same dates without conflict.
- `django.contrib.auth.decorators.login_required` (already used by `accounts.views.dashboard`) is sufficient for both new views — there's no separate "event staff" or "participant" role touching this slice.

## What We're NOT Doing

- CSV upload, room data, or any hotel-inventory concept — that's `S-02`, a separate change; `Event` here has no fields for room/venue inventory.
- Participant or staff lists, access links — that's `S-03`/`F-02`.
- Deleting events — no FR asks for it; organisers can rename/redate an event but not remove it in this slice.
- Validating that `start_date` (or the booking window) isn't in the past — no FR asks for this, and blocking it would be an invented guardrail with no product requirement behind it.
- Any UI framework/JS for dynamic booking-window preview as the organiser types the event date — the default is computed server-side on submit, not live in the browser.
- A dedicated `events/urls.py` include — following the existing `accounts` convention of wiring views directly in `stay_recon/urls.py`.
- Multi-day-aware duplicate semantics beyond exact `(start_date, end_date)` equality — two events with overlapping-but-not-identical ranges are not treated as duplicates; no FR asks for overlap detection.

## Implementation Approach

Three phases, each independently testable: the data layer first (model, constraint, admin — nothing that can be exercised via the UI yet), then the create flow (form, view, template, the duplicate guardrail and window defaults), then the list + edit flow (dashboard integration, edit view, and the object-level scoping check that stops one organiser from editing another's event). Sequencing this way means Phase 1's schema is locked in before any view code depends on it, and Phase 2's create flow is fully working and tested before Phase 3 reuses its form for editing.

## Phase 1: Events app scaffold & Event model

### Overview

Creates the `events` app and the `Event` model with its per-organiser uniqueness constraint, and registers it with the admin.

### Changes Required:

#### 1. New app: `events`

**File**: `events/__init__.py`, `events/apps.py`, `events/models.py`, `events/admin.py`, `events/migrations/0001_initial.py`

**Intent**: Give the project its second domain app, holding the `Event` model.

**Contract**: `events/models.py` defines `Event(models.Model)` with `organiser` (`ForeignKey` to `accounts.User`, `on_delete=CASCADE`, `related_name='events'`), `name` (`CharField`, max_length 200), `start_date`/`end_date` (`DateField`), `description` (`TextField`, `blank=True`, default `''`), `window_start`/`window_end` (`DateField`). `Meta.constraints` includes a `UniqueConstraint` over `(Lower(Trim('name')), 'start_date', 'end_date', 'organiser')`. `Event.clean()` raises `ValidationError` if `end_date < start_date` or if `window_start > window_end` or `window_end > start_date`. `events/admin.py` registers `Event` with `list_display = ['name', 'organiser', 'start_date', 'end_date']`. `0001_initial.py` is Django-generated via `makemigrations events` — do not hand-write it.

#### 2. Project settings

**File**: `stay_recon/settings.py`

**Intent**: Register the new app.

**Contract**: `INSTALLED_APPS` gains `'events'`.

#### 3. Deploy build filter

**File**: `render.yaml`

**Intent**: Without this, pushes touching only `events/**` won't trigger a Render rebuild — the same gap Phase 1 of F-01 fixed for `accounts/**`.

**Contract**: Add `events/**` to `buildFilter.paths`.

### Success Criteria:

#### Automated Verification:

- `uv run manage.py makemigrations --check --dry-run` reports no missing migrations
- `uv run manage.py migrate` applies cleanly against a freshly deleted local `db.sqlite3`
- `uv run manage.py check` passes with no errors
- Unit test: creating two events with the same organiser, normalized name (`"Team Offsite"` vs `"team offsite "`), and dates raises `IntegrityError` (or is caught by `full_clean()`) — the DB constraint fires
- Unit test: creating events with the same name/dates but different organisers succeeds for both

#### Manual Verification:

- `python manage.py shell` (or admin) confirms `Event` appears in `/admin/` with the expected list columns

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 2: Create event

### Overview

The form, view, and template an organiser uses to create an event — including the friendly duplicate-name error and the booking-window default computation.

### Changes Required:

#### 1. Event form

**File**: `events/forms.py` (new)

**Intent**: Collect event fields from the organiser, compute booking-window defaults when left blank, and reject a duplicate (organiser, normalized name, dates) with a friendly error rather than a database `IntegrityError` — mirroring `accounts.forms.SignupForm.clean_email`'s established pattern in this codebase.

**Contract**: `EventForm(forms.ModelForm)` with `Meta.model = Event`, `Meta.fields = ('name', 'start_date', 'end_date', 'description', 'window_start', 'window_end')`; `window_start`/`window_end` are `required=False` on the form. The form is constructed with an `organiser` kwarg (not a model field) used for the duplicate-scoping query and to exclude the instance's own pk on edit. `clean()`: if `window_start`/`window_end` weren't supplied, compute them as `start_date - timedelta(days=14)` / `start_date - timedelta(days=3)`; validate `end_date >= start_date` and `window_start <= window_end <= start_date`; check for an existing `Event` with the same `organiser`, normalized `name`, `start_date`, `end_date` (excluding `self.instance.pk`) and raise a field error on `name` if found.

#### 2. Create view

**File**: `events/views.py` (new)

**Intent**: Render the form, inject the logged-in organiser, save, and redirect to the dashboard where the new event now appears.

**Contract**: `event_create` view, `@login_required`; instantiates `EventForm(organiser=request.user)`; on valid POST, sets `event.organiser = request.user` before saving (`form.save(commit=False)`), redirects to `dashboard`.

#### 3. URL + template

**File**: `stay_recon/urls.py`, `templates/events/event_form.html` (new)

**Intent**: Expose the new view, following the existing direct-`path()` convention (no `events/urls.py`).

**Contract**: `path('events/create/', event_create, name='event_create')`; template extends `base.html` with the event form.

### Success Criteria:

#### Automated Verification:

- Unit test: valid submission (name, dates, no window fields) creates an `Event` with `window_start`/`window_end` computed from `start_date`
- Unit test: valid submission with explicit `window_start`/`window_end` keeps those values, not the computed defaults
- Unit test: submitting a duplicate (same organiser, normalized name, dates) shows a field validation error and creates no new row
- Unit test: submitting `end_date` before `start_date` is rejected by form validation
- Unit test: submitting a `window_end` after `start_date` is rejected by form validation

#### Manual Verification:

- On the live Render deploy: create an event, confirm no error and a redirect to the dashboard

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 3: Event list & edit

### Overview

The dashboard now shows the organiser's own events; each links to an edit view that reuses Phase 2's form, scoped so one organiser can never reach another's event.

### Changes Required:

#### 1. Dashboard view & template

**File**: `accounts/views.py`, `templates/accounts/dashboard.html`

**Intent**: Replace the "nothing to show yet" placeholder with the organiser's actual events, and a link to create a new one.

**Contract**: `dashboard` view's context gains `events = request.user.events.order_by('start_date')`. Template lists each event's name and dates, linking to its edit view; includes a link to `event_create`.

#### 2. Edit view

**File**: `events/views.py`

**Intent**: Let an organiser edit any field of an event they own; the duplicate check still applies (against *other* events, not itself), matching FR-001's "editing an existing event is never blocking" — i.e., saving an edit unchanged, or changed but non-colliding, always succeeds.

**Contract**: `event_edit` view, `@login_required`; fetches the event via `get_object_or_404(Event, pk=pk, organiser=request.user)` — this is the object-level scoping check: a mismatched organiser produces a 404, not a 403, so the URL leaks no information about whether the event exists under another account. Reuses `EventForm`, passing `instance=event, organiser=request.user`. On valid POST, saves and redirects to `dashboard`.

#### 3. URL + template

**File**: `stay_recon/urls.py`, `templates/events/event_form.html`

**Intent**: Expose the new view; the create template becomes shared.

**Contract**: `path('events/<int:pk>/edit/', event_edit, name='event_edit')`. `event_form.html` gains a conditional heading ("Create event" vs "Edit event") based on whether `form.instance.pk` is set.

### Success Criteria:

#### Automated Verification:

- Unit test: dashboard response for an organiser with two events shows both, ordered by `start_date`
- Unit test: dashboard response for an organiser with no events shows none of another organiser's events
- Unit test: `GET /events/<pk>/edit/` for an event owned by a different organiser returns 404
- Unit test: editing an event's description only (name/dates unchanged) succeeds — the duplicate check against itself doesn't block a no-op-on-uniqueness edit
- Unit test: editing an event's name/dates to collide with a *different* existing event of the same organiser is rejected

#### Manual Verification:

- On the live Render deploy: create two events, confirm both appear on the dashboard, edit one, confirm the change persists
- Log in as a second organiser (or the bootstrapped superuser vs. a signed-up account), confirm their dashboard shows no events from the first organiser

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Testing Strategy

### Unit Tests:

- DB-level duplicate constraint fires on normalized name+dates+organiser match, not across organisers (Phase 1)
- Form-level duplicate check, window-default computation, window-override honored, date-order validation (Phase 2)
- Dashboard event list scoping, edit-view object-level scoping (404 on cross-organiser access), edit success/duplicate-on-edit (Phase 3)

### Integration Tests:

- Full create → dashboard-list → edit → dashboard-list round trip via Django's test client, single organiser

### Manual Testing Steps:

1. On the live Render deploy, log in, create an event with a booking window left blank, confirm it appears on the dashboard with the computed window dates (visible via `/admin/` or the edit form).
2. Attempt to create a second event with the same name (different case/whitespace) and dates — confirm the friendly duplicate error, not a 500.
3. Edit the first event's description, confirm it saves and the dashboard still shows it correctly.
4. Sign up a second organiser account, confirm their dashboard shows no events from the first account, and that navigating directly to the first organiser's edit URL returns a 404.

## Performance Considerations

None specific to this change — list/edit views are simple per-organiser queries with no meaningful load yet (PRD's `target_scale.qps: low`).

## Migration Notes

Purely additive: a new app and a new table, no existing data affected. No production schema reset needed (unlike F-01's `AUTH_USER_MODEL` swap) — this is a normal `migrate` on top of the existing schema.

## References

- Roadmap: `context/foundation/roadmap.md` (`S-01: Organiser creates an event`)
- PRD: `context/foundation/prd.md` (`FR-001`, `FR-008` for the booking-window default rule, `## Access Control §Organiser`)
- Prior pattern: `context/archive/2026-09-11-organiser-auth-app-scaffold/plan.md` (`accounts.forms.SignupForm.clean_email` — the duplicate-check pattern this plan follows)

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Events app scaffold & Event model

#### Automated

- [x] 1.1 `makemigrations --check --dry-run` reports no missing migrations — b4fb3a1
- [x] 1.2 `migrate` applies cleanly against a freshly deleted local `db.sqlite3` — b4fb3a1
- [x] 1.3 `manage.py check` passes — b4fb3a1
- [x] 1.4 Duplicate constraint fires for same organiser, normalized name, dates — b4fb3a1
- [x] 1.5 Same name/dates across different organisers succeeds for both — b4fb3a1

#### Manual

- [x] 1.6 `Event` appears in `/admin/` with expected columns — b4fb3a1

### Phase 2: Create event

#### Automated

- [x] 2.1 Valid submission with blank window fields computes defaults from `start_date` — bb09e4e
- [x] 2.2 Valid submission with explicit window fields keeps those values — bb09e4e
- [x] 2.3 Duplicate submission shows field error, creates no row — bb09e4e
- [x] 2.4 `end_date` before `start_date` rejected — bb09e4e
- [x] 2.5 `window_end` after `start_date` rejected — bb09e4e

#### Manual

- [x] 2.6 Live event creation on Render, redirects to dashboard

### Phase 3: Event list & edit

#### Automated

- [x] 3.1 Dashboard shows organiser's own events, ordered by `start_date` — f5114f6
- [x] 3.2 Dashboard shows none of another organiser's events — f5114f6
- [x] 3.3 Edit view 404s for a non-owned event — f5114f6
- [x] 3.4 No-op-on-uniqueness edit succeeds — f5114f6
- [x] 3.5 Edit colliding with a different existing event is rejected — f5114f6

#### Manual

- [x] 3.6 Live create + list + edit round trip on Render
- [x] 3.7 Second organiser sees no cross-account events, edit URL 404s
