---
project: "StayRecon"
context_type: greenfield
created: 2026-09-04
updated: 2026-09-04
checkpoint:
  current_phase: 8
  phases_completed: [1, 2, 3, 4, 5, 6, 7]
  gray_areas_resolved:
    - topic: "pain category"
      decision: "workflow friction + coordination overhead + data trapped in inconsistent per-hotel CSV format"
    - topic: "core insight"
      decision: "per-hotel CSV variance is the real blocker; generic booking tools assume a fixed room schema"
    - topic: "primary persona scope"
      decision: "individuals across many orgs — independent/freelance organisers, not a single in-house role"
    - topic: "auth model"
      decision: "organiser: login (email/OAuth/passwordless); participant: unique access link per event, no account; event staff: login with staff role, scoped to one event"
    - topic: "gated access behavior"
      decision: "expired/closed booking window → read-only status view; no link/unauthenticated → generic landing page, no data exposed"
    - topic: "v1 scope cuts"
      decision: "manual CSV column mapping (not auto-detection); manual link sharing (no automated invitation emails); simple table/CSV report (not matching hotel's original schema)"
    - topic: "deadline scope cuts"
      decision: "hard deadline (2026-09-14, day-job time) conflicted with the original 3-week after-hours estimate; deferred change-log/audit trail (FR-005) and flag/note feature (FR-010) to fit the 10-day runway"
  frs_drafted: 14
  quality_check_status: accepted
product_type: web-app
target_scale:
  users: large
  qps: low
  data_volume: small
timeline_budget:
  mvp_weeks: 2
  hard_deadline: 2026-09-14
  after_hours_only: false
---

## Seed idea (verbatim)

> new project for online reservation system for hotel rooms at events. Organisers get list of rooms available for an event, in csv format, which can differ in every hotel. Then, participants, are able to book rooms, based on their preference. At the event, event staff do the check-in, apply last booking changes and hand over "starter packs".

## Vision & Problem Statement

Independent event organisers, who run events across many different client organisations, must reconcile participant room bookings against a hotel-supplied CSV of available rooms — and every hotel exports that CSV in a different format. Today this reconciliation happens by hand in spreadsheets, both during the event as bookings are made and again afterward for invoicing, since hotels bill only for rooms actually used. The manual process is slow, error-prone, and creates real financial risk: a reconciliation mistake means disputing charges with the hotel or overpaying for rooms nobody used.

Generic booking and event-management tools assume a fixed, uniform room schema and don't account for the fact that each hotel's inventory export looks different. Nobody has solved the normalization step, so organisers fall back to spreadsheets by default — the tooling that exists solves adjacent problems (RSVPs, sign-ups) but not the CSV-variance-to-invoice-accuracy chain that actually costs organisers time and money.

## User & Persona

**Primary persona:** Independent event organiser — works across many different client organisations, running events at different hotels for each. Reaches for this product whenever they receive a new hotel's room-availability CSV and need to open bookings to participants, and again at the end of the event when reconciling actual usage against the hotel's invoice.

## Access Control

Three roles, each with a different entry path:

- **Organiser** — full account via login (email/password, OAuth, or passwordless). Owns their events, uploads the hotel's room CSV, manages the booking window, and runs final reconciliation/invoicing. Can only see and manage their own events.
- **Participant** — no account. Reaches their booking via a unique access link/token tied to a specific event. Can view available rooms and make/change their booking while the window is open. After the booking window closes, the link becomes read-only (shows their booking status, no further changes). A visitor with no link sees a generic landing page — no event or booking data is exposed.
- **Event staff** — login with a staff role, scoped to a single event at a time (not a cross-event account). Can perform on-site check-in, apply last-minute booking changes, and mark starter-pack hand-off. Cannot access other events or the organiser's invoicing/reconciliation view.

## Success Criteria

### Primary
- The scoped v1 flow works end-to-end: organiser creates an event, uploads and manually maps a hotel's CSV, shares access links, participants book within the edit window, staff check in and hand over starter packs on-site, and the organiser gets a rooms-used-vs-booked report afterward.

### Secondary
- At least 75% of participants complete their own booking online before event day, without needing event staff to book on their behalf at the hotel.

### Guardrails
- The reconciliation report is data-accurate (rooms used vs. booked matches reality) — this is what the organiser hands to the hotel for invoicing.
- Participant data (bookings, contact info) stays private — not exposed to other participants or unauthenticated visitors.
- No double-allocation of a room to two participants.

v1 scope (locked after scoping down from the full flow): manual CSV column mapping instead of auto-detection, manual link sharing instead of automated invitation emails, and a simple table/CSV report instead of one matching the hotel's original schema. Timeline: 3 weeks of after-hours work.

## Functional Requirements

### Organiser
- FR-001: Organiser can create a new event. Creating an event with the same name and date as an existing one is blocked; editing an existing event is never blocking. Priority: must-have
  > Socrates: Counter-argument considered: "duplicate event creation (same name + date) could cause confusion." Resolution: block duplicate creation at creation time; edits to an existing event remain non-blocking.
- FR-002: Organiser can upload a hotel's room CSV and manually map its columns (room number, type, capacity), with a preview/confirm step showing parsed rooms before they're saved. Priority: must-have
  > Socrates: Counter-argument considered: "manual mapping errors could go undetected." Resolution: added a mapping preview/confirm step so the organiser sees parsed rooms before confirming.
- FR-003: Organiser can add participant and staff lists to an event; malformed emails are rejected and duplicates flagged at upload time. Priority: must-have
  > Socrates: Counter-argument considered: "no validation on list data could silently break link generation." Resolution: basic format validation (reject malformed, flag duplicates) added at upload time.
- FR-004: Organiser can generate a unique access link per participant and per staff member; links expire when the event's check-in window closes. Priority: must-have
  > Socrates: Counter-argument considered: "leaked links have no expiry." Resolution: links expire automatically when the event ends.
- FR-005: Organiser can edit any booking or participant info, at any time. Priority: must-have
  > Socrates: Counter-argument considered: "no audit trail makes disputes about who changed what unresolvable." Resolution: change-log/audit trail deferred past the 2026-09-14 deadline; see Non-Goals. FR stands without logging for this deadline.
- FR-006: Organiser can generate a rooms-used-vs-booked report after the event, and can regenerate it at any point afterward as data is corrected. Priority: must-have
  > Socrates: Counter-argument considered: "one-shot report generation risks the organiser invoicing off a stale report if corrections happen after generation." Resolution: report can be regenerated anytime post-event, always reflecting current data.

### Participant
- FR-007: Participant can view available rooms for their event via their unique access link, with one room highlighted as the suggested pick. Priority: must-have
  > Socrates: Counter-argument considered: "all participants seeing live availability at once could turn booking into a race for popular rooms." Resolution: kept as written — first-come-first-served is an acceptable/expected dynamic.
- FR-014: Participant can state their room preferences, which the app uses to highlight a single suggested room that fits their preferences while minimizing the total number of rooms the event ends up using; participant can accept the suggestion or pick a different available room instead. Priority: must-have
- FR-008: Participant can book a room, within a booking window the organiser configures per event (default: 2 weeks before to 3 days before the event). Priority: must-have
  > Socrates: Counter-argument considered: "a hardcoded 14/3-day window is too rigid across different organisers' needs (e.g. short-notice events)." Resolution: booking window becomes configurable per event at creation time, rather than fixed.
- FR-009: Participant can change their booking within that window, up to 3 times. Priority: must-have
  > Socrates: Counter-argument considered: "unlimited changes could let a participant repeatedly hold/release rooms, squatting a preferred room and locking out others." Resolution: cap booking changes at 3 per participant.
- FR-010: Participant sees a read-only booking status once the booking window closes. Priority: must-have
  > Socrates: Counter-argument considered: "no way to flag an error once the view becomes read-only." Resolution: flag/note feature deferred past the 2026-09-14 deadline; see Non-Goals. Participant contacts organiser outside the app for this deadline.

### Event staff
- FR-011: Event staff can check in a participant on event day. Priority: must-have
  > Socrates: Counter-argument considered: "no handling for walk-in participants who never booked online." Resolution: walk-ins are handled via FR-012 — staff books/edits their room directly using the on-event-day edit capability.
- FR-012: Event staff can modify booking info, but only on event day itself. Priority: must-have
  > Socrates: Counter-argument considered: "could conflict with FR-005 if organiser and staff edit the same booking simultaneously on event day — no defined precedence." Resolution: flagged as an Open Question (see below).
- FR-013: Event staff can mark a starter pack as handed over. Priority: must-have
  > Socrates: Counter-argument considered: "no handling for running out of starter packs on-site." Resolution: kept as written — pack inventory management is out of scope for v1.

## Business Logic

When a participant books, the app highlights a single suggested room that best matches their stated preferences while minimizing the total number of rooms the event ends up using — the participant can accept the suggestion or pick a different available room instead.

The rule consumes two user-facing inputs: the preferences a participant states before booking (e.g. desired room features/type), and the current state of everyone else's bookings for the event. Its output is a single highlighted room per participant, chosen to consolidate usage into as few rooms as possible wherever preferences allow, while every other available room stays visible and selectable. The participant encounters this as a highlighted "suggested for you" room at the top of their booking screen, with the full list of available rooms still browsable underneath.

## Non-Functional Requirements

- A participant sees their suggested room within 2 seconds of opening the booking screen.
- Participant and booking data is retained no longer than Polish GDPR requirements allow; once that retention period elapses, the organiser is notified and given the option to delete the data.
- The product is usable on the latest versions of Chrome and Firefox.

## User Stories

### US-01: Participant books a room via access link

- **Given** the event's booking window is open (default: 2 weeks to 3 days before the event, configurable per event) and the participant has their unique access link
- **When** the participant opens the link and selects an available room
- **Then** the room is booked to them and they see their confirmed booking status

#### Acceptance Criteria
- If the selected room was booked by another participant in the meantime, the participant sees a message that it's no longer available, and their current booking status is shown instead
- No two participants can end up booked into the same room (double-allocation guardrail)

## Non-Goals

- No automated CSV format auto-detection — organiser always manually maps columns; no smart per-hotel schema detection.
- No automated invitation emails — organiser shares access links manually.
- No multi-organiser / team collaboration on one event — each event has exactly one owning organiser.
- No starter-pack inventory tracking — pure hand-off marking only, no stock count or low-stock warning.
- No audit trail / change history — deferred past the 2026-09-14 deadline; edits aren't logged for v1.
- No participant flag/note feature — deferred past the deadline; participants contact the organiser outside the app.
- No native mobile app / offline support — web-only, requires connectivity.

## Open Questions

1. **What happens when the organiser and event staff edit the same booking simultaneously on event day (FR-012 vs. FR-005)?** — no conflict-resolution precedence decided yet. Owner: user. Block: no (last-write-wins is a safe fallback, but should be confirmed before implementation).
