# StayRecon

Hotel room reconciliation and booking for independent event organisers.

## The problem

Independent event organisers run events across many different client
organisations, at a different hotel each time. Before participants can book
a room, the organiser needs a working list of what's available — and every
hotel hands that over as a CSV export in its own format: different column
names, different order, different shape from the last one.

Today that reconciliation happens by hand in spreadsheets, twice: once while
bookings are open, and again after the event, when the organiser has to
check actual room usage against the hotel's invoice — hotels only bill for
rooms that were actually used. The manual process is slow, error-prone, and
carries real financial risk: get the reconciliation wrong and you're either
disputing charges with the hotel or quietly overpaying for rooms nobody
stayed in.

Generic booking and RSVP tools don't solve this because they assume a fixed,
uniform room schema. They handle sign-ups fine; they don't handle the part
that actually costs organisers time and money — turning an arbitrary
per-hotel CSV into a normalized room list you can trust for invoicing.

## What StayRecon does

StayRecon is the tool for that normalization-to-invoice-accuracy chain, for
one specific persona: an independent organiser who runs events for many
different client organisations, each at a different hotel.

Three roles, three different entry paths:

- **Organiser** — logs in, owns their events, uploads a hotel's room CSV and
  manually maps its columns (no auto-detection — every hotel's export is
  different enough that guessing is worse than asking), shares access links
  with participants, and generates a rooms-used-vs-booked reconciliation
  report after the event, regenerable any time as data gets corrected.
- **Participant** — no account needed. Opens their unique per-event access
  link, states a room preference, and gets a single suggested room
  highlighted — chosen to fit their preference while minimizing the total
  number of rooms the event ends up using — with every other available room
  still browsable underneath. Can change their booking up to 3 times while
  the booking window is open; sees a read-only status once it closes.
- **Event staff** — logs in scoped to a single event, checks participants in
  on-site, applies last-minute booking changes on event day, and marks
  starter-pack hand-off.

The guardrails that matter most: no room ever gets double-booked to two
participants, participant data stays private, and the reconciliation report
has to be accurate — it's what the organiser hands to the hotel to settle
the bill.

## CSV format

The room-upload CSV is deliberately format-agnostic on column naming —
column headers and order don't matter, since after upload you manually map
which column is which (no auto-detection). Requirements:

- A standard CSV with a **header row** followed by data rows.
- Max **5000 data rows**; each header value under **200 characters**.
- Encoding: tries `utf-8-sig` → `cp1252` → `latin-1` in order, so UTF-8
  (with or without BOM) and common Windows exports both work.

Per-row validation, shown in the preview after mapping:

- **Room number** — required, can't be blank.
- **Capacity** — must be a whole number (digits only).
- **Room type** — no validation; any text, including blank.
- **Room numbers must be unique per event** (case/whitespace-insensitive —
  `"101"` and `" 101 "` collide), checked once at confirm across all pages.

## Scope for v1

Deliberately cut to fit a hard two-week deadline: manual CSV column mapping
(not automatic format detection), manual link sharing (not automated
invitation emails), and a simple table/CSV reconciliation report (not one
that mirrors each hotel's original format). Full detail, including what's
explicitly out of scope, lives in `context/foundation/prd.md`.

## Project status

Built via the [10xDevs](https://10xdevs.pl) planning chain — every shipped
slice has a plan and a test rollout behind it. See
`context/foundation/roadmap.md` for what's done vs. in progress, and
`context/foundation/test-plan.md` for the risk-driven test strategy.

## Running locally

```bash
uv sync
uv run manage.py migrate
uv run manage.py runserver
```

Deployed on Render — see `context/foundation/infrastructure.md` for the
deployment story.

## Foundation docs

- `context/foundation/prd.md` — full product requirements
- `context/foundation/shape-notes.md` — original discovery/shaping notes
- `context/foundation/roadmap.md` — slice-by-slice build status
- `context/foundation/tech-stack.md` — stack and why
- `context/foundation/infrastructure.md` — deployment platform and risks
- `context/foundation/test-plan.md` — risk-driven test rollout
