---
project: StayRecon
version: 1
status: draft
created: 2026-09-11
updated: 2026-09-11
prd_version: 1
main_goal: speed
top_blocker: time
milestone_id: v1-mvp-launch
milestone_seq: 1
milestone_status: open
---

# Roadmap: StayRecon

> Derived from `context/foundation/prd.md` (v1) + auto-researched codebase baseline.
> Edit-in-place; archive when superseded.
> Slices below are listed in dependency order. The "At a glance" table is the index.

## Milestone

**M-1: StayRecon v1 MVP** — Status: open

- **Intent:** Ship the PRD's full scoped v1 flow end-to-end — organiser creates an event, uploads and maps a hotel CSV, participants book via access links, staff check in and hand over starter packs, organiser gets an accurate reconciliation report.
- **Source materials:** `context/foundation/prd.md` (v1)
- **Done when:** every F-NN and S-NN below is `done`.

## Vision recap

Independent event organisers reconcile participant room bookings against a hotel-supplied CSV that looks different for every hotel — today done by hand in spreadsheets, both during booking and again for post-event invoicing. The product's core bet is that solving the CSV-variance-to-invoice-accuracy chain (not another generic booking/RSVP tool) is what actually saves organisers time and prevents costly reconciliation disputes.

## North star

**S-04: Participant views and books a room via their access link, with one room suggested** — the smallest end-to-end flow that proves the core hypothesis: an organiser's event + CSV + links actually work for a real participant.

> "North star" here means the smallest end-to-end slice whose successful delivery would prove the core product idea — placed as early as its prerequisites allow, because everything else (change-booking, staff check-in, the reconciliation report) only matters if this works first.

## At a glance

| ID   | Change ID                            | Outcome (user can …)                                                        | Prerequisites        | PRD refs                  | Status   |
| ---- | ------------------------------------- | ----------------------------------------------------------------------------- | --------------------- | -------------------------- | -------- |
| F-01 | organiser-auth-app-scaffold           | (foundation) Django app scaffold exists; organiser can log in                 | —                      | Access Control (Organiser) | planning |
| F-02 | access-link-staff-session-scaffold    | (foundation) participant token-link verification + staff scoped-session mechanism | F-01               | Access Control (Participant, Event staff), FR-004 | proposed |
| S-01 | create-event                          | Organiser can create a new event (duplicate name+date blocked)                | F-01                  | FR-001                     | proposed |
| S-02 | csv-upload-room-mapping               | Organiser can upload a hotel CSV, map columns, and confirm a normalized room list | S-01, F-01          | FR-002                     | proposed |
| S-03 | participant-staff-lists-and-links     | Organiser can add validated participant/staff lists and get a unique access link per person | S-01, F-01, F-02 | FR-003, FR-004             | proposed |
| S-04 | participant-books-via-link            | Participant sees available rooms (one suggested) via their link and books one | S-02, S-03, F-02      | US-01, FR-007, FR-014, FR-008 | proposed |
| S-05 | change-booking-capped                 | Participant can change their booking, up to 3 times, within the window        | S-04                  | FR-009                     | proposed |
| S-06 | readonly-status-after-window          | Participant sees a read-only booking status once the window closes            | S-04                  | FR-010                     | proposed |
| S-07 | organiser-edit-booking-anytime        | Organiser can edit any booking or participant info at any time                | S-03, S-04             | FR-005                     | proposed |
| S-08 | staff-checkin-edit-pack-handoff       | Event staff can check in a participant, edit their booking same-day, and mark starter pack handed over | S-03, S-04, F-02 | FR-011, FR-012, FR-013  | proposed |
| S-09 | reconciliation-report                 | Organiser can generate and regenerate a rooms-used-vs-booked report           | S-04, S-08             | FR-006                     | proposed |

## Streams

Navigation aid — groups items that share a Prerequisites chain. Canonical ordering still lives in the dependency graph below; this table is the proposed reading order across parallel tracks.

| Stream | Theme                                   | Chain                                                          | Note                                                                 |
| ------ | ---------------------------------------- | --------------------------------------------------------------- | --------------------------------------------------------------------- |
| A      | Event setup, booking core & closeout     | `F-01` → `S-01` → `S-02` → `S-04` → `S-05` → `S-06` → `S-07` → `S-09` | Primary organiser+participant loop; carries the north star (`S-04`).  |
| B      | Access & on-site staff ops               | `F-02` → `S-03` → `S-08`                                        | Joins Stream A at `S-04` (both `S-03` and `S-08` feed the booking flow). |

## Baseline

What's already in place in the codebase as of `2026-09-11` (auto-researched + user-confirmed).
Foundations below assume these are present and do NOT re-scaffold them.

- **Frontend:** absent — no template directory, no static assets beyond Django admin, no component library. `stay_recon/views.py` has one inline-HTML placeholder view at `/`.
- **Backend / API:** partial — Django 6.1 project scaffold exists (`manage.py`, `stay_recon/` config package), but no domain app has been created yet; `INSTALLED_APPS` is Django defaults only.
- **Data:** partial — Postgres is live on Render (free tier); `DATABASE_URL` wired via `dj-database-url`. Only Django's own built-in migrations (`admin`, `auth`, `contenttypes`, `sessions`) have run — no domain schema exists.
- **Auth:** absent — `django.contrib.auth` is installed (Django default) but unused: no custom login flow, no OAuth/passwordless, no participant access-link/token model, no staff role scoping. None of the PRD's three-role access model is implemented.
- **Deploy / infra:** present — Render web service + Postgres live and verified (`https://stay-recon.onrender.com`), `build.sh`, `render.yaml` (with `buildFilter` and `autoDeployTrigger: commit`). See `context/deployment/deploy-plan.md` for full operational detail, including a tracked free-tier-to-paid-tier upgrade trigger (before any real participant/organiser data or usage).
- **Observability:** absent — no logging/error-tracking/metrics library beyond Django and Render's own platform logs. Not currently required by any PRD signal.

## Foundations

### F-01: Organiser auth & app scaffold

- **Outcome:** (foundation) A Django app exists to hold domain models/views, and an organiser can log in with a single auth method and reach an empty, account-scoped dashboard.
- **Change ID:** `organiser-auth-app-scaffold`
- **PRD refs:** Access Control §Organiser
- **Unlocks:** S-01, S-02, S-03 (and transitively everything downstream — no other work can start without this)
- **Prerequisites:** —
- **Parallel with:** —
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Nothing else can be built until an app exists and organisers can log in — sequenced first because every other item transitively depends on it. Main risk is scope-creeping into a full auth system (OAuth + passwordless) when a single login method is enough to unblock downstream work; that choice belongs to `/10x-plan`, not this roadmap.
- **Status:** planning

### F-02: Access-link & staff-session scaffold

- **Outcome:** (foundation) A no-account, token-based link-verification mechanism for participants, and a scoped staff-login session mechanism, both usable by any route that needs them.
- **Change ID:** `access-link-staff-session-scaffold`
- **PRD refs:** Access Control §Participant, §Event staff; FR-004 (link expiry behavior)
- **Unlocks:** S-03 (link generation consumes this), S-04 (north star — participant authenticates via link), S-06 (read-only post-window view), S-08 (staff scoped session)
- **Prerequisites:** F-01
- **Parallel with:** S-01
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Participant and staff routes need a working verification mechanism before either can be demoed. Keeping this to verification-only (not the link-generation UI, which stays user-visible in S-03) avoids re-absorbing S-03's work into a foundation.
- **Status:** proposed

## Slices

### S-01: Organiser creates an event

- **Outcome:** Organiser can create a new event; creating a duplicate (same name + date) is blocked, editing an existing event is never blocking.
- **Change ID:** `create-event`
- **PRD refs:** FR-001
- **Prerequisites:** F-01
- **Parallel with:** F-02
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Smallest possible first vertical slice (single FR, no downstream data yet) — proves F-01's login + app scaffold actually works end-to-end before anything heavier is built on top.
- **Status:** proposed

### S-02: Organiser uploads and maps a hotel CSV

- **Outcome:** Organiser can upload a hotel's room CSV, manually map its columns (room number, type, capacity), and confirm a preview of parsed rooms before they're saved.
- **Change ID:** `csv-upload-room-mapping`
- **PRD refs:** FR-002
- **Prerequisites:** S-01, F-01
- **Parallel with:** S-03
- **Blockers:** —
- **Unknowns:** —
- **Risk:** CSV variance is the PRD's stated core differentiator. Running this in parallel with S-03 tests the riskiest technical assumption (arbitrary per-hotel CSV shapes) early, rather than leaving it for late in the 3-day runway.
- **Status:** proposed

### S-03: Organiser adds participant/staff lists and generates access links

- **Outcome:** Organiser can add participant and staff lists (malformed emails rejected, duplicates flagged) and receive a unique access link per person, expiring when the event's check-in window closes.
- **Change ID:** `participant-staff-lists-and-links`
- **PRD refs:** FR-003, FR-004
- **Prerequisites:** S-01, F-01, F-02
- **Parallel with:** S-02
- **Blockers:** —
- **Unknowns:** —
- **Risk:** The links generated here are what S-04 (north star) and S-08 (staff check-in) both consume. Running in parallel with S-02 is the single biggest time-saving opportunity in this roadmap, given `top_blocker: time`.
- **Status:** proposed

### S-04: Participant views and books a room via access link

- **Outcome:** Participant opens their link, sees available rooms with one highlighted suggestion (based on stated preferences, minimizing total rooms used), and books it; if the selected room was taken in the meantime, they see it's unavailable and their current status instead.
- **Change ID:** `participant-books-via-link`
- **PRD refs:** US-01, FR-007, FR-014, FR-008
- **Prerequisites:** S-02, S-03, F-02
- **Parallel with:** —
- **Blockers:** —
- **Unknowns:** —
- **Risk:** This is the north star — placed as early as its two prerequisite branches (S-02, S-03) allow, not deferred for symmetry. If this doesn't work, nothing downstream matters. FR-014's suggestion/consolidation logic is the one piece here with real algorithmic risk and deserves explicit verification, not just an assumed side effect of "booking works."
- **Status:** proposed

### S-05: Participant changes their booking

- **Outcome:** Participant can change their booked room while the window is open, capped at 3 changes total.
- **Change ID:** `change-booking-capped`
- **PRD refs:** FR-009
- **Prerequisites:** S-04
- **Parallel with:** S-06, S-07, S-08
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Builds directly on S-04's booking flow. The 3-change cap is a small but real edge case (off-by-one on the 3rd change) worth a named test.
- **Status:** proposed

### S-06: Participant sees read-only status after window closes

- **Outcome:** Once the booking window closes, the participant's access link becomes a read-only status view — no further changes possible.
- **Change ID:** `readonly-status-after-window`
- **PRD refs:** FR-010
- **Prerequisites:** S-04
- **Parallel with:** S-05, S-07, S-08
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Read-only enforcement at window close is a state-transition edge case (a participant's tab open exactly at the boundary) — worth explicit verification, not just an assumed side effect of S-04's window logic.
- **Status:** proposed

### S-07: Organiser edits booking or participant info anytime

- **Outcome:** Organiser can edit any booking or participant record, unrestricted by booking-window state.
- **Change ID:** `organiser-edit-booking-anytime`
- **PRD refs:** FR-005
- **Prerequisites:** S-03, S-04
- **Parallel with:** S-05, S-06, S-08
- **Blockers:** —
- **Unknowns:**
  - Precedence when the organiser (this slice, FR-005) and event staff (S-08, FR-012) edit the same booking simultaneously on event day — Owner: user. Block: no (PRD notes last-write-wins as an acceptable fallback; should be confirmed before `/10x-plan` on S-07 or S-08). See also `## Open Roadmap Questions` #1.
- **Risk:** Overlaps in scope with staff's on-day edit (S-08/FR-012) — see the Unknown above. Sequencing this before S-08 lets the simpler, organiser-only edit path get proven first.
- **Status:** proposed

### S-08: Event staff check in, edit, and hand off starter packs

- **Outcome:** Event staff, scoped to one event, can check in a participant on event day, edit their booking info same-day (including walk-ins with no prior booking), and mark their starter pack as handed over.
- **Change ID:** `staff-checkin-edit-pack-handoff`
- **PRD refs:** FR-011, FR-012, FR-013
- **Prerequisites:** S-03, S-04, F-02
- **Parallel with:** S-05, S-06, S-07
- **Blockers:** —
- **Unknowns:**
  - See S-07's Unknown (organiser/staff simultaneous-edit precedence) — Owner: user. Block: no.
- **Risk:** Combines check-in, on-day edit, and pack hand-off into one on-site workflow, matching the PRD's own success-criteria narration ("staff check in and hand over starter packs on-site"). The walk-in case (FR-012 resolving FR-011's gap) is the trickiest edge case here.
- **Status:** proposed

### S-09: Organiser generates the reconciliation report

- **Outcome:** Organiser can generate a rooms-used-vs-booked report after the event, and regenerate it anytime afterward as data is corrected.
- **Change ID:** `reconciliation-report`
- **PRD refs:** FR-006
- **Prerequisites:** S-04, S-08
- **Parallel with:** —
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Depends on S-08's actual check-in data to make "used" meaningful, not just "booked." This is the guardrail deliverable — the report must be data-accurate for the organiser's hotel invoicing — so it's sequenced last, after every data-producing slice exists, on purpose.
- **Status:** proposed

## Backlog Handoff

| Roadmap ID | Change ID                          | Suggested issue title                                              | Ready for `/10x-plan` | Notes |
| ---------- | ------------------------------------ | ---------------------------------------------------------------------- | ---------------------- | ----- |
| F-01       | `organiser-auth-app-scaffold`        | Scaffold first Django app + organiser login                            | yes                    | Run `/10x-plan organiser-auth-app-scaffold` |
| F-02       | `access-link-staff-session-scaffold` | Access-link token verification + staff scoped session                 | no                     | Waits on F-01 |
| S-01       | `create-event`                       | Organiser: create event (duplicate name+date blocked)                  | no                     | Waits on F-01 |
| S-02       | `csv-upload-room-mapping`            | Organiser: upload + map hotel room CSV                                 | no                     | Waits on S-01, F-01 |
| S-03       | `participant-staff-lists-and-links`  | Organiser: add participant/staff lists + generate access links         | no                     | Waits on S-01, F-01, F-02 |
| S-04       | `participant-books-via-link`         | Participant: view + book a room via access link (north star)          | no                     | Waits on S-02, S-03, F-02 |
| S-05       | `change-booking-capped`              | Participant: change booking (max 3 times)                              | no                     | Waits on S-04 |
| S-06       | `readonly-status-after-window`       | Participant: read-only status after window closes                      | no                     | Waits on S-04 |
| S-07       | `organiser-edit-booking-anytime`     | Organiser: edit booking/participant info anytime                       | no                     | Waits on S-03, S-04; precedence Unknown vs S-08 |
| S-08       | `staff-checkin-edit-pack-handoff`    | Event staff: check-in, on-day edit, starter pack hand-off              | no                     | Waits on S-03, S-04, F-02; precedence Unknown vs S-07 |
| S-09       | `reconciliation-report`              | Organiser: rooms-used-vs-booked reconciliation report                  | no                     | Waits on S-04, S-08 |

## Open Roadmap Questions

1. **What happens when the organiser (S-07/FR-005) and event staff (S-08/FR-012) edit the same booking simultaneously on event day?** — Owner: user. Block: none (last-write-wins is a safe fallback per the PRD, but should be confirmed before `/10x-plan` on either S-07 or S-08). Carried verbatim from PRD's own Open Questions.
2. **Is the full 9-slice v1 scope still realistically achievable in the remaining runway?** — Owner: user. Block: none, but strategic. As of this roadmap's creation (2026-09-11), the PRD's hard deadline is 2026-09-14 (3 days out) and zero domain code exists yet (confirmed in `## Baseline`). Worth an explicit go/cut decision now rather than discovering the gap mid-sprint.
3. **Will the GDPR data-retention NFR (notify organiser + offer deletion once the retention period elapses) be implemented for the 2026-09-14 deadline, or explicitly deferred like the audit-trail and flag/note features already were?** — Owner: user. Block: none, but affects the data model S-03 and S-04 create. Deciding this before those slices are planned avoids silently dropping a stated NFR under time pressure.

## Parked

- **No automated CSV format auto-detection** — Why parked: PRD Non-Goals; organiser always manually maps columns.
- **No automated invitation emails** — Why parked: PRD Non-Goals; organiser shares access links manually.
- **No multi-organiser / team collaboration on one event** — Why parked: PRD Non-Goals; each event has exactly one owning organiser.
- **No starter-pack inventory tracking** — Why parked: PRD Non-Goals; pure hand-off marking only, no stock count or low-stock warning.
- **No audit trail / change history** — Why parked: PRD Non-Goals; deferred past the 2026-09-14 deadline per the PRD's own prior scope cut.
- **No participant flag/note feature** — Why parked: PRD Non-Goals; deferred past the deadline; participants contact the organiser outside the app.
- **No native mobile app / offline support** — Why parked: PRD Non-Goals; web-only, requires connectivity.

## Milestone History

(Empty — this is the first milestone.)

## Done

(Empty — no slices have shipped yet.)
