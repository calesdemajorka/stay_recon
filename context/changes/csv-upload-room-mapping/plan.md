# CSV Upload & Room Mapping Implementation Plan

## Overview

StayRecon has `accounts` (auth) and `events` (Event scheduling) but no room-inventory concept yet. This plan adds a new `rooms` app with a `Room` model and a 4-step organiser flow — upload a hotel's room CSV, map its columns, review/edit a paginated preview, confirm — that turns an arbitrary hotel-export CSV into normalized `Room` records scoped to an `Event`. This is roadmap item `S-02` (`FR-002`).

## Current State Analysis

- No file-upload code exists anywhere in the codebase (`code`, confirmed — no `FileField`, `request.FILES`, or multipart handling anywhere).
- `events.Event` has an implicit auto `id`/`pk`, an `organiser` FK to `accounts.User`, and is the natural parent for `Room` (per `context/archive/2026-09-14-create-event/plan.md`: "`Event` here has no fields for room/venue inventory... that's `S-02`").
- Render's free-tier web service has no persistent disk (confirmed directly against Render's docs this session) and none is provisioned in `render.yaml`. `STORAGES['default']` is plain `FileSystemStorage`, unused by this plan.
- `events/forms.py`/`events/views.py` establish the reusable patterns this plan follows: `ModelForm` + `clean()` cross-field validation + `save(commit=False)` stamping; function-based `@login_required` views; `get_object_or_404(Event, pk=pk, organiser=request.user)` object-level scoping; a `transaction.atomic()` + `IntegrityError`-catch guard for race conditions on a uniqueness constraint (`events/views.py`'s `_save_or_duplicate_error`).
- `pyproject.toml` has only `django`, `dj-database-url`, `gunicorn`, `psycopg`, `whitenoise` as dependencies — this plan adds none (stdlib `csv` only).
- `templates/<app>/<name>.html` extending `base.html`, no per-app `urls.py` (routes go directly in `stay_recon/urls.py`), no JS framework anywhere.

## Definitions

| Term | Decided meaning | Origin | On degenerate data | Verified by |
| ---- | --------------- | ------ | ------------------- | ----------- |
| Duplicate room | Same event, same normalized room number (trimmed, case-insensitive) | user (this session), mirrors `Event`'s own duplicate-name pattern | Two rows in one CSV both mapping to room number `"101"` — rejected, not silently merged or last-wins | Phase 1 DB constraint; Phase 4 confirm-time full-set check |
| Malformed row | A mapped row with a missing room number or a non-numeric capacity | user (this session) | Flagged per-row in the preview; blocks Confirm until fixed or the row's page is corrected | Phase 3 initial validation; Phase 4 per-page re-validation |
| Cross-page duplicate check timing | Runs once, at Confirm — not after every page save/navigation | user (this session, explicit simplification) | Two rows on different pages sharing a room number are not flagged while editing, only when Confirm is clicked | Phase 4 tests |
| Re-upload with existing rooms | Allowed only after an explicit warning + confirmation; then wipes and replaces all of the event's rooms | user (this session) | Uploading a new CSV for an event that already has 5 confirmed rooms shows a warning naming the count; without checking the replace-confirmation box, the upload is refused | Phase 2 tests |

## Desired End State

An organiser, viewing one of their events, can upload a hotel's room CSV, map its columns to room number/type/capacity, review a paginated editable preview, and confirm to save the rooms — replacing any of that event's existing rooms if they choose to proceed past the warning. Malformed or duplicate rows block confirmation with a clear, locatable message. No raw CSV file is ever persisted to disk or object storage; only the final `Room` rows live in Postgres.

Verification: `uv run manage.py check` passes; the live upload → map → preview(edit across pages) → confirm loop works end-to-end on Render for a real CSV with mixed valid/invalid/duplicate rows; a second organiser cannot reach or affect another organiser's pending upload or rooms.

### Key Discoveries:

- `django.db.models.JSONField` works natively on both Postgres (`jsonb`, used in production) and SQLite (local dev) — no new dependency needed to hold `PendingUpload`'s parsed-CSV state between steps.
- `QuerySet.bulk_create()` does **not** call `Model.clean()`/`full_clean()` or per-instance `save()` — confirmed via Django's own documented behavior. This means the confirm view's explicit pre-validation is the *only* safety net before `Room` rows are written; there is no model-level backstop for a bulk-created row the way there is for a form-saved one.
- Encoding fallback (`utf-8-sig` → `cp1252` → `latin-1`) covers realistic hotel/legacy CSV exports without a new dependency — `latin-1` never raises `UnicodeDecodeError` since it maps every byte 1:1, making it a safe final fallback.
- Full research and library/architecture rationale: `context/changes/csv-upload-room-mapping/research.md`.

## What We're NOT Doing

- CSV format auto-detection — organiser always manually maps columns (PRD Non-Goal, explicit).
- Editing or deleting individual `Room` records outside the wipe-and-replace re-upload flow — no standalone Room edit/delete UI in this slice.
- A dedicated room-list/management page beyond the upload flow itself — no FR asks for one; later slices (`S-04` booking, `S-08` check-in, `S-09` reconciliation) consume `Room` data functionally, not via a CRUD list built here.
- Object storage (S3/R2) or any persistent-disk usage — avoided entirely by architecture (raw CSV never persists past the request cycle it's uploaded in; only parsed data lives in Postgres via `PendingUpload`/`Room`).
- A scheduled cleanup job for abandoned `PendingUpload` rows — a new upload simply overwrites any existing one for that (organiser, event) pair; no cron job.
- Real-time cross-page duplicate warnings while editing the preview — the duplicate scan runs once, at Confirm, not after every page save (explicit simplification this session).
- Async/background CSV processing — everything happens synchronously within the request/response cycle (PRD `target_scale.qps: low`, `data_volume: small`).
- Updating `context/foundation/infrastructure.md`'s risk-register entry (which currently recommends S3/R2 "before FR-002 ships") — flagged as superseded by this plan's architecture, but editing that document is a housekeeping follow-up, not part of this change.

## Implementation Approach

Four phases, each producing independently testable, demoable behavior: the data layer first (`Room`/`PendingUpload` models — nothing UI-reachable yet), then upload (file → parsed `PendingUpload`, with the re-upload warning gate), then column mapping (turns raw parsed rows into validated `mapped_rows`), then the preview/edit/confirm screen (the same view handles pagination, per-page editing and re-validation, and the final confirm action — these are one cohesive UI surface, not separable phases). Sequencing this way means the CSV-parsing and storage architecture is locked in before any view depends on it, and each of the three flow phases builds directly on the previous step's `PendingUpload` state.

## Critical Implementation Details

- **`bulk_create()` bypasses model-level validation entirely.** `Room.objects.bulk_create(...)` in the Phase 4 confirm view does not call `full_clean()`/`clean()` or per-instance `save()`. All validation (missing fields, non-numeric capacity, duplicate room numbers) must happen explicitly in the confirm view's own logic before `bulk_create()` runs — do not assume the model's `Meta.constraints` or `clean()` will catch a validation bug here the way they would for a form-saved `Event`.
- **Cross-page duplicate detection is confirm-time-only, by design.** Per-page saves in Phase 4 validate only that page's own rows (missing room number, non-numeric capacity) — a duplicate room number spanning two different pages is *not* flagged until Confirm is clicked, at which point the one full-set scan runs and must produce an error message that names the colliding rows/pages so the organiser can navigate back and fix them (not just "duplicates exist somewhere").
- **Wipe-and-replace must be atomic.** When re-uploading for an event with existing confirmed rooms, deleting the old `Room` rows and `bulk_create`-ing the new ones must happen inside one `transaction.atomic()` block (mirroring `events/views.py`'s `_save_or_duplicate_error` pattern) — a failure partway through must not leave the event with zero rooms.
- **A formset page/TOTAL_FORMS mismatch fails silently, not with an error.** Django's formset reads `TOTAL_FORMS`/`INITIAL_FORMS` from the *submitted* management-form POST data, not from the view's `initial=` list — if the view's page-slicing logic ever disagrees with what was submitted, Django doesn't raise; `_construct_form` catches the resulting `IndexError` internally and just renders without the expected initial values. Before trusting any submitted formset in Phase 4, explicitly assert `int(request.POST.get('form-TOTAL_FORMS', -1))` equals the expected page-slice length, and reject + re-render fresh from `PendingUpload.mapped_rows` on mismatch — do not rely on Django's formset machinery to catch this itself.

## Phase 1: `rooms` app scaffold — Room & PendingUpload models

### Overview

Creates the `rooms` app with the `Room` model (confirmed room inventory) and `PendingUpload` model (in-flight CSV state between upload and confirm), registers both with the admin.

### Changes Required:

#### 1. New app: `rooms`

**File**: `rooms/__init__.py`, `rooms/apps.py`, `rooms/models.py`, `rooms/admin.py`, `rooms/migrations/0001_initial.py`

**Intent**: Give room inventory its own app, since `Room` will be heavily referenced by later slices (`S-04`, `S-08`, `S-09`) independent of `Event`'s own scheduling concerns.

**Contract**: `rooms/models.py` defines:
- `Room(models.Model)`: `event` (`ForeignKey` to `events.Event`, `on_delete=CASCADE`, `related_name='rooms'`), `room_number` (`CharField`, max_length 50 — alphanumeric room numbers like `"12A"` are valid), `room_type` (`CharField`, max_length 100), `capacity` (`PositiveIntegerField`). `Meta.constraints` includes a `UniqueConstraint` over `(Lower(Trim('room_number')), 'event')`, mirroring `Event`'s own duplicate-guard shape.
- `PendingUpload(models.Model)`: `organiser` (`ForeignKey` to `accounts.User`, `on_delete=CASCADE`), `event` (`ForeignKey` to `events.Event`, `on_delete=CASCADE`), `headers` (`JSONField`, list of the CSV's original header strings), `raw_rows` (`JSONField`, list of dicts keyed by original headers, all string values), `column_mapping` (`JSONField`, default `dict` — `{'room_number': <header>, 'room_type': <header>, 'capacity': <header>}` once mapped), `mapped_rows` (`JSONField`, default `list` — list of `{'room_number', 'room_type', 'capacity', 'errors'}` dicts once mapped), `created_at` (`DateTimeField`, `auto_now_add=True`). `Meta.constraints` includes a `UniqueConstraint` over `('organiser', 'event')` — at most one in-flight pending upload per organiser+event at a time.

`rooms/admin.py` registers both models (`RoomAdmin` with `list_display = ['room_number', 'room_type', 'capacity', 'event']`; `PendingUploadAdmin` with `list_display = ['event', 'organiser', 'created_at']`). `0001_initial.py` is Django-generated via `makemigrations rooms` — do not hand-write it.

#### 2. Project settings & build filter

**File**: `stay_recon/settings.py`, `render.yaml`

**Intent**: Register the new app; without the build-filter entry, pushes touching only `rooms/**` won't trigger a Render rebuild (the same gap fixed for `accounts/**` and `events/**` in prior phases).

**Contract**: `INSTALLED_APPS` gains `'rooms'`. `render.yaml`'s `buildFilter.paths` gains `rooms/**`.

### Success Criteria:

#### Automated Verification:

- `uv run manage.py makemigrations --check --dry-run` reports no missing migrations
- `uv run manage.py migrate` applies cleanly against a freshly deleted local `db.sqlite3`
- `uv run manage.py check` passes with no errors
- Unit test: two `Room` rows with the same event and normalized room number (e.g. `"101"` vs `"101 "`) raise `IntegrityError`; the same room number on two different events succeeds for both
- Unit test: a `PendingUpload` round-trips `headers`/`raw_rows`/`column_mapping`/`mapped_rows` through JSON correctly
- Unit test: two `PendingUpload` rows for the same `(organiser, event)` raise `IntegrityError`

#### Manual Verification:

- `Room` and `PendingUpload` both appear in `/admin/` with the expected list columns

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 2: CSV upload

### Overview

The file-upload form and view: reads the uploaded CSV, decodes it robustly, parses headers/rows into a fresh `PendingUpload`, and gates re-upload behind an explicit warning when the event already has confirmed rooms.

### Changes Required:

#### 1. Upload form & view

**File**: `rooms/forms.py` (new), `rooms/views.py` (new)

**Intent**: Accept a CSV file, decode it despite unknown/non-UTF-8 encoding, parse it into `PendingUpload.headers`/`raw_rows`, and require explicit confirmation before overwriting an event's already-confirmed rooms.

**Contract**: `CSVUploadForm(forms.Form)` with a `csv_file` (`forms.FileField`) and a `confirm_replace` (`forms.BooleanField(required=False)`) used only when needed. `csv_upload(request, event_pk)` view, `@login_required`; scopes via `get_object_or_404(Event, pk=event_pk, organiser=request.user)`. On GET, if `event.rooms.exists()`, the template shows a warning naming the current room count and requires `confirm_replace` to be checked; on POST without it checked in that situation, re-render with a field error rather than proceeding. On a valid POST, decode the uploaded file's bytes trying `utf-8-sig`, then `cp1252`, then `latin-1` (the last always succeeds); parse with `csv.DictReader`. Before creating the `PendingUpload`, sanity-check the parse: reject with a friendly "this doesn't look like a valid CSV" field error if `headers` is empty, if any header string is implausibly long (a hallmark of misdecoded binary content — e.g. an `.xlsx` renamed `.csv`, since `latin-1` never raises even on non-text input), or if the row count exceeds a generous cap (e.g. 5,000, well above any realistic hotel room count). If the sanity check passes, delete any existing `PendingUpload` for `(request.user, event)` and create a fresh one with the parsed `headers`/`raw_rows`; redirect to the column-mapping step.

#### 2. URL + template

**File**: `stay_recon/urls.py`, `templates/rooms/csv_upload.html` (new), `templates/events/event_form.html`

**Intent**: Expose the new view and give the organiser an entry point from the event they're already editing.

**Contract**: `path('events/<int:event_pk>/rooms/upload/', csv_upload, name='rooms_upload')`. `templates/events/event_form.html` gains a link to this URL when editing an existing event (`{% if form.instance.pk %}`). Template extends `base.html`.

### Success Criteria:

#### Automated Verification:

- Unit test: uploading a valid UTF-8 CSV creates a `PendingUpload` whose `headers`/`raw_rows` match the file's content
- Unit test: uploading a CSV with a UTF-8 BOM parses the first header without a leading `﻿` artifact
- Unit test: uploading a `cp1252`- or `latin-1`-encoded CSV (invalid as UTF-8) succeeds via the decode fallback chain
- Unit test: uploading a second CSV for the same `(organiser, event)` replaces the existing `PendingUpload`, not duplicates it
- Unit test: uploading for an event that already has confirmed rooms, without checking `confirm_replace`, is rejected with a field error and creates no `PendingUpload`
- Unit test: the same upload with `confirm_replace` checked succeeds
- Unit test: uploading a non-CSV binary file (e.g. random bytes) is rejected with a friendly error rather than creating a `PendingUpload` full of garbled headers
- Unit test: `GET`/`POST` to the upload URL for an event owned by a different organiser returns 404

#### Manual Verification:

- On the live Render deploy: upload a real small CSV for one of your events, confirm redirect to the column-mapping step with no error

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 3: Column mapping

### Overview

The mapping form: one dropdown per target field (room number/type/capacity), populated with the CSV's actual header names, which applies the chosen mapping to produce `PendingUpload.mapped_rows` with initial per-row validation.

### Changes Required:

#### 1. Mapping form & view

**File**: `rooms/forms.py`, `rooms/views.py`

**Intent**: Let the organiser tell the app which CSV column is which target field, then compute the normalized row data those choices imply.

**Contract**: `ColumnMappingForm(forms.Form)` with three `ChoiceField`s (`room_number`, `room_type`, `capacity`), each `__init__`-populated with `[(h, h) for h in pending_upload.headers]`. `csv_map_columns(request, event_pk)` view, `@login_required`, scoped via the event and the organiser's `PendingUpload` for it (404 if either is missing). On valid POST, saves the mapping to `PendingUpload.column_mapping`, then computes `mapped_rows` by reading each `raw_rows` entry's mapped-column values and validating per-row: a missing/blank room number, or a non-numeric capacity, adds an entry to that row's `errors` dict (this is deliberately *not* yet checking for duplicates across rows — that's confirm-time-only, per the Critical Implementation Details). Redirects to the preview step at page 1.

#### 2. URL + template

**File**: `stay_recon/urls.py`, `templates/rooms/csv_map_columns.html` (new)

**Intent**: Expose the new view.

**Contract**: `path('events/<int:event_pk>/rooms/map/', csv_map_columns, name='rooms_map_columns')`. Template extends `base.html`.

### Success Criteria:

#### Automated Verification:

- Unit test: the mapping form's three fields are populated with the pending upload's actual CSV headers
- Unit test: submitting a mapping computes `mapped_rows` with values correctly pulled from the mapped columns
- Unit test: a row with a blank/missing room number is flagged with a per-row error after mapping
- Unit test: a row with a non-numeric capacity (e.g. `"twelve"`) is flagged with a per-row error after mapping
- Unit test: a row with valid data for all three fields has an empty `errors` dict
- Unit test: mapping for another organiser's pending upload / event returns 404

#### Manual Verification:

- On the live Render deploy: pick a mapping for the uploaded CSV, confirm redirect to preview page 1

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 4: Preview, edit, and confirm

### Overview

The paginated, editable preview screen: 25 rows per page, each page's edits validated and saved back into `PendingUpload.mapped_rows` on navigation, and a Confirm action that runs the one cross-page duplicate scan before atomically writing (or replacing) the event's `Room` records.

### Changes Required:

#### 1. Preview/edit/confirm view

**File**: `rooms/forms.py`, `rooms/views.py`

**Intent**: Let the organiser review and correct parsed rows across pages, then commit them as `Room` records.

**Contract**: `RoomRowForm(forms.Form)` with `room_number`, `room_type` (`CharField`s) and `capacity` (`CharField`, validated as a positive integer in `clean_capacity`) — a plain (non-model) formset via `forms.formset_factory(RoomRowForm, extra=0)`, one form per row on the current page. `csv_preview(request, event_pk)` view, `@login_required`, scoped via the event and the organiser's `PendingUpload`. `GET ?page=N` renders the formset for rows `[(N-1)*25 : N*25]` of `mapped_rows`, pre-filled from their current values, each row's template display including its current `errors` (if any). `POST` handles three actions distinguished by which submit button fired: **Save & Next/Previous** — validates the current page's formset (field-level only: blank room number, non-numeric capacity), writes the (possibly corrected) values and any remaining per-row errors back into the corresponding slice of `mapped_rows`, redirects to the requested page. **Confirm** — first saves the current page same as above, then runs one pass over the *entire* `mapped_rows` list: if `mapped_rows` is empty (a header-only or genuinely empty CSV), block with a "No rows found in this CSV" message rather than allowing a silent zero-room save; if any row has a per-row error, or a normalized room number collides with another row, block with a message identifying the affected page number(s)/row(s) and do not proceed. If the full set is clean: inside `transaction.atomic()`, delete all of the event's existing `Room` rows (only relevant on a replace-flow re-upload) and `bulk_create()` new ones from `mapped_rows`, then delete the `PendingUpload`, then redirect to the event's edit page with a success message naming the room count created.

#### 2. URL + template

**File**: `stay_recon/urls.py`, `templates/rooms/csv_preview.html` (new)

**Intent**: Expose the new view.

**Contract**: `path('events/<int:event_pk>/rooms/preview/', csv_preview, name='rooms_preview')` (page number via `?page=` query param, not a URL segment, since Confirm posts to this same URL regardless of current page). Template extends `base.html`, renders the formset as a table (room number / type / capacity / error columns) plus Previous/Next/Confirm buttons and a page indicator.

### Success Criteria:

#### Automated Verification:

- Unit test: page 1 shows the first 25 rows, page 2 the next 25 (for a `mapped_rows` set larger than 25)
- Unit test: correcting a row's capacity on page-save clears that row's error and persists the new value into `PendingUpload.mapped_rows`
- Unit test: editing a room number on one page to collide with a room number on a different page is *not* flagged by the page-save itself
- Unit test: Confirm with any remaining per-row error anywhere in `mapped_rows` blocks, names the affected page, creates no `Room` rows
- Unit test: Confirm with a cross-page duplicate blocks, names the colliding rows/pages, creates no `Room` rows
- Unit test: Confirm with a fully valid `mapped_rows` set creates matching `Room` rows and deletes the `PendingUpload`
- Unit test: Confirm for a replace-flow re-upload (event already had confirmed rooms) atomically deletes the old rows and creates the new ones — verify no partial state if the creation step is made to fail mid-way (e.g. via a forced exception in a test)
- Unit test: preview/confirm for another organiser's event/pending-upload returns 404
- Unit test: a POST with a `TOTAL_FORMS` value that doesn't match the expected page-slice length is rejected (re-rendered fresh), not silently accepted with misaligned data
- Unit test: Confirm with an empty `mapped_rows` (header-only CSV) is blocked with a "no rows found" message, creates no `Room` rows

#### Manual Verification:

- On the live Render deploy: full happy-path upload → map → page through a multi-page preview → confirm; verify the room count in the success message
- Deliberately upload a CSV with one malformed row and one cross-page duplicate pair; verify both are caught with locatable messages, not a 500
- Re-upload a CSV for an event with already-confirmed rooms; verify the warning, and that confirming replaces the old rooms rather than adding to them

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Testing Strategy

### Unit Tests:

- `Room`/`PendingUpload` uniqueness constraints (Phase 1)
- Upload decode-fallback chain, re-upload replace-gate, per-(organiser,event) `PendingUpload` overwrite (Phase 2)
- Column-mapping application and initial per-row validation (Phase 3)
- Pagination, per-page save/re-validation, confirm-time full-set duplicate scan, atomic wipe-and-replace, object-level scoping throughout (Phase 4)

### Integration Tests:

- Full upload → map → preview(single page) → confirm round trip via Django's test client, one organiser, clean CSV
- Full round trip with a multi-page CSV (>25 rows) including a cross-page duplicate, verifying Confirm blocks correctly

### Manual Testing Steps:

1. On the live Render deploy, upload a small, clean hotel-style CSV for one of your events; map columns; confirm; verify the rooms exist (via `/admin/` or the success message's count).
2. Upload a CSV with a malformed row (missing room number) and confirm the preview flags it and blocks Confirm until fixed.
3. Upload a larger CSV (>25 rows) with two rows sharing a room number on different pages; confirm Confirm blocks with a message naming both locations.
4. Re-upload a new CSV for the same event; confirm the warning appears, and that confirming replaces (not appends to) the existing rooms.
5. As a second organiser, confirm you cannot reach the first organiser's pending upload or rooms via direct URL (404s).

## Performance Considerations

None specific to this change — PRD's `target_scale.qps: low` and `data_volume: small` mean a hotel CSV is realistically well under a few hundred rows; storing parsed data as JSON in Postgres and paginating the preview at 25 rows keeps every request/response small.

## Migration Notes

Purely additive: a new app and two new tables, no existing data affected. No production schema reset needed — a normal `migrate` on top of the existing schema.

## References

- Research: `context/changes/csv-upload-room-mapping/research.md`
- Prior pattern: `context/archive/2026-09-14-create-event/plan.md` (duplicate-guard + `_save_or_duplicate_error` race-condition pattern this plan reuses for the wipe-and-replace atomicity)

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: `rooms` app scaffold — Room & PendingUpload models

#### Automated

- [x] 1.1 `makemigrations --check --dry-run` reports no missing migrations — 2c48819
- [x] 1.2 `migrate` applies cleanly against a freshly deleted local `db.sqlite3` — 2c48819
- [x] 1.3 `manage.py check` passes — 2c48819
- [x] 1.4 Room duplicate constraint fires per-event, not across events — 2c48819
- [x] 1.5 PendingUpload JSON fields round-trip correctly — 2c48819
- [x] 1.6 PendingUpload unique-per-(organiser,event) constraint fires — 2c48819

#### Manual

- [x] 1.7 `Room` and `PendingUpload` appear in `/admin/` with expected columns — 2c48819

### Phase 2: CSV upload

#### Automated

- [x] 2.1 Valid UTF-8 CSV creates PendingUpload with matching headers/raw_rows — 0060125
- [x] 2.2 UTF-8 BOM stripped from first header — 0060125
- [x] 2.3 cp1252/latin-1 CSV decoded via fallback chain — 0060125
- [x] 2.4 Second upload replaces existing PendingUpload, not duplicates — 0060125
- [x] 2.5 Upload for event with confirmed rooms rejected without confirm_replace — 0060125
- [x] 2.6 Same upload with confirm_replace checked succeeds — 0060125
- [x] 2.7 Upload for another organiser's event returns 404 — 0060125
- [x] 2.8 Non-CSV binary upload rejected with friendly error, no PendingUpload created — 0060125

#### Manual

- [ ] 2.9 Live CSV upload on Render, redirects to mapping step

### Phase 3: Column mapping

#### Automated

- [x] 3.1 Mapping form populated with actual CSV headers
- [x] 3.2 Submitting mapping computes mapped_rows correctly
- [x] 3.3 Missing room number flagged per-row
- [x] 3.4 Non-numeric capacity flagged per-row
- [x] 3.5 Valid row has empty errors dict
- [x] 3.6 Mapping for another organiser's data returns 404

#### Manual

- [ ] 3.7 Live column mapping on Render, redirects to preview page 1

### Phase 4: Preview, edit, and confirm

#### Automated

- [ ] 4.1 Page 1/page 2 show correct row slices
- [ ] 4.2 Correcting a row on page-save clears its error and persists
- [ ] 4.3 Cross-page duplicate not flagged by page-save itself
- [ ] 4.4 Confirm blocks on remaining per-row error, names the page, creates no Rooms
- [ ] 4.5 Confirm blocks on cross-page duplicate, names the rows/pages, creates no Rooms
- [ ] 4.6 Confirm with valid data creates matching Room rows, deletes PendingUpload
- [ ] 4.7 Replace-flow confirm is atomic (no partial state on forced failure)
- [ ] 4.8 Preview/confirm for another organiser's data returns 404
- [ ] 4.9 Mismatched TOTAL_FORMS rejected, not silently accepted
- [ ] 4.10 Confirm with empty mapped_rows blocked, no Rooms created

#### Manual

- [ ] 4.11 Full happy-path upload→map→multi-page-preview→confirm on Render
- [ ] 4.12 Malformed row + cross-page duplicate both caught with locatable messages, no 500
- [ ] 4.13 Re-upload for event with confirmed rooms: warning shown, confirm replaces not appends
