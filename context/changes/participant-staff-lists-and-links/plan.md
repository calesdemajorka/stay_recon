# Participant & Staff Lists + Access-Link Generation (S-03) Implementation Plan

## Overview

Organiser uploads a participant list and a staff list (separately) as two-column CSVs (name, email), reviews/edits a paginated preview, and on confirm gets normalized `Participant`/`StaffMember` records plus a generated `AccessLink` per person, created atomically. Staff additionally get a manual "add one" form for small events where a full CSV is overkill. A links list + CSV export view lets the organiser retrieve the generated links to share manually (no automated invitation emails, per PRD Non-Goals). This is roadmap item `S-03` (`FR-003`, `FR-004`).

## Current State Analysis

- `access.AccessLink` (from the now-archived F-02) exists but cannot satisfy FR-003 alone: no `Meta.constraints` at all — only `token` is `unique=True` — and `label` is an unvalidated `CharField`. No function anywhere creates an `AccessLink` row or a token; F-02 deliberately left this to S-03 (`context/archive/2026-09-16-access-link-staff-session-scaffold/plan.md:36`).
- `access/models.py:6-22` — exact `AccessLink` contract: `event` FK, `role` (`ROLE_PARTICIPANT`/`ROLE_STAFF` choices), `label`, `token` (`unique=True, db_index=True`), `is_revoked`, `created_at`.
- This codebase has a twice-established convention for exactly the "reject duplicate string per scope" requirement FR-003 needs: `UniqueConstraint(Lower(Trim(<field>)), <scope>)` — `events/models.py:21-29` and `rooms/models.py:15-21`.
- The `rooms` app's CSV upload flow is the closest architectural precedent, but its column-mapping step (`ColumnMappingForm`, `csv_map_columns`) exists specifically because hotel CSVs vary unpredictably per third party (`prd.md:20-22,110`) — participant/staff lists are organiser-authored with a fixed shape, so no mapping step is needed here.
- Patterns from `rooms` that transfer directly: the `PendingUpload`-style staging model (`rooms/models.py:27-42`), "flag at parse, block confirm until fixed" validation timing (`rooms/forms.py:78-102`'s `full_set_problems()`, checked only at confirm), the encoding-fallback chain (`rooms/views.py:28-39`), the `organiser=request.user` object-scoping convention, and the upload-size-cap pattern (`MAX_UPLOAD_BYTES`/`MAX_ROWS`, added to `rooms/forms.py` during its own impl-review — now an established convention to apply from the start here, not discover via review).
- The PRD is silent on how the organiser retrieves generated links to share manually — `prd.md:111` (Non-Goals) only rules out automated invitation email.
- Full research: `context/changes/participant-staff-lists-and-links/research.md`.

## Desired End State

An organiser, viewing one of their events, can:
- Upload a participant CSV (name, email), review a paginated editable preview, and confirm — creating `Participant` + `AccessLink` rows atomically, one link per row.
- Upload a staff CSV the same way, **or** add one staff member at a time via a simple form — creating `StaffMember` + `AccessLink` rows atomically.
- View a links list for the event (both roles), with a CSV export, to retrieve links for manual sharing.

Re-uploading a list for an event that already has participants/staff is append-only: new rows are added, and any row whose normalized email already exists for that event (across *either* role — dual-role is disallowed) is rejected as a duplicate, never silently replaced.

**Verification**: `uv run manage.py test access` passes; `uv run manage.py check` passes; on the live Render deploy, a full participant-list upload→preview→confirm cycle and a full staff-list upload→preview→confirm cycle both produce the expected `Participant`/`StaffMember` + `AccessLink` rows, links are visible/exportable from the links list, and a re-upload correctly rejects a duplicate email without touching existing rows.

### Key Discoveries

- `AccessLink.label` (`access/models.py:16`) exists specifically for this purpose — F-02's own plan says "an identifying string such as an email or name; S-03 owns its exact semantics." This plan populates it with the person's email at creation time, preserving F-02's already-built placeholder views (`participant_link.html`, `staff_dashboard.html`) unchanged.
- Since dual-role is disallowed, an email must be unique per-event across `Participant` and `StaffMember` **combined** — Django can't express a cross-table `UniqueConstraint`, so each model keeps its own `Lower(Trim(email))`-per-event DB constraint, and an application-level check against the *other* table is added at confirm time.
- `rooms/forms.py`'s `MAX_UPLOAD_BYTES`/`MAX_ROWS` constants and the size-check-before-read pattern were added to `rooms` during its own implementation review (not from the start) — this plan applies that same pattern proactively from Phase 2 onward rather than waiting to discover the gap.

## What We're NOT Doing

- No manual "add one" form for participants — CSV upload only, per the PRD's "lists" framing (participant lists are expected to be much larger than staff lists).
- No edit/delete UI for already-created `Participant`/`StaffMember`/`AccessLink` rows beyond what append-only re-upload naturally provides — that's a future slice's job if needed.
- No automated invitation email — organiser retrieves links via the list view/export and shares them manually (PRD Non-Goals).
- No revocation UI — `AccessLink.is_revoked` exists (from F-02) but nothing in this slice sets it; `/admin/` remains the only way to revoke until a future slice needs it.
- No booking-state fields (preferences, booked room, change-count) on `Participant`, and no check-in/pack-handoff fields on `StaffMember` — those belong to S-04 and S-08 respectively (per this change's own research forward-trace), which will extend these models with their own FKs/fields when picked up.
- No changes to `events.Event`'s schema.

## Implementation Approach

Four phases. Phase 1 builds both `Participant` and `StaffMember` together (a shared foundational data layer, since cross-role dedup checks both tables from the start regardless of which role is being uploaded). Phases 2 and 3 then build each role's upload→preview→confirm flow **fully separately** — participant first, then staff (which additionally gets a manual one-at-a-time add form) — rather than interleaving both roles through shared views, so each flow gets full, undivided attention rather than being hidden behind a role parameter. Both phases call into small shared helper functions (email normalization, cross-table dedup check, encoding fallback) to avoid true duplication without hiding the two flows behind shared views. Phase 4 is a read-only aggregate view over both roles' links, naturally shared since it's not part of the two-parallel-flows concern.

## Critical Implementation Details

- **Cross-role dedup is a two-layer check.** The DB-level `UniqueConstraint(Lower(Trim('email')), 'event')` on each of `Participant` and `StaffMember` only prevents duplicates *within* the same table. Since dual-role is disallowed, the confirm-time full-set validation for a participant upload must ALSO query `StaffMember` for the same event (and vice versa for staff uploads) — implement this as one shared `email_taken_for_event(email, event)` helper called from both flows' validation, not duplicated per-role.
- **Links need absolute URLs, not relative paths.** The links list/export must build full URLs (`request.build_absolute_uri(reverse('participant_access', args=[token]))` or equivalent) since the organiser will copy/export these to share outside the app — a relative path pasted into an email is useless.
- **Atomic creation order matters.** On confirm, `Participant`/`StaffMember` and `AccessLink` rows must be created inside one `transaction.atomic()` block (mirroring `rooms`' wipe-and-replace pattern) — generate the token, create the `AccessLink`, then create the `Participant`/`StaffMember` row pointing at it (or vice versa, whichever order the FK direction requires), so a failure partway through never leaves an orphaned identity with no link or a link with no owner.
- **`Participant`/`StaffMember` and their `access_link` must agree on event, role, AND label — nothing enforces this automatically at the DB level.** The `access_link` `OneToOneField` has no DB-level link tying its `event`, `role`, or `label` to the owning row — an admin operator (or careless application code) could point a `Participant` at a `StaffMember`-role `AccessLink`, one belonging to a different event, or one whose `label` doesn't match the person's email. `Participant.clean()`/`StaffMember.clean()` catch all three in any `ModelForm`-based path (e.g. the admin), but plain `.create()`/`.save()` calls never trigger `clean()` — so Phases 2 and 3's confirm-time creation code must always derive `event`/`role`/`label` (from `email`) from the row being created (never accept an independently-picked `AccessLink`), and should still call `full_clean()` explicitly before saving as a defense-in-depth check.

## Phase 1: Data layer — Participant, StaffMember, PendingListUpload

### Overview

Adds the identity models both upload flows depend on, plus the shared staging model, to the existing `access` app.

### Changes Required

#### 1. Identity models

**File**: `access/models.py`, `access/admin.py`, `access/migrations/000X_....py`

**Intent**: Give each role its own identity record, FK'd to its `AccessLink`, so `Participant` and `StaffMember` can each grow their own role-specific fields later (S-04, S-08) without a shared table becoming awkward.

**Contract**: `Participant(models.Model)`: `event` (FK `Event`, `CASCADE`, `related_name='participants'`), `access_link` (`OneToOneField(AccessLink, on_delete=CASCADE)`), `name` (`CharField`, max_length 255), `email` (`EmailField`). `Meta.constraints`: `UniqueConstraint(Lower(Trim('email')), 'event', name='unique_participant_email_per_event')`, mirroring `Room`'s/`Event`'s existing pattern. `StaffMember(models.Model)`: identical shape (`event`, `access_link` as `OneToOneField`, `name`, `email`), its own `unique_staff_member_email_per_event` constraint. Both registered in `access/admin.py` with `list_display = ['event', 'name', 'email']`.

#### 2. Staging model for list uploads

**File**: `access/models.py`, `access/admin.py`, migration

**Intent**: Hold parsed-but-unconfirmed rows between upload and confirm, mirroring `rooms.PendingUpload`'s role in that flow — but simpler, since no column mapping exists to stage.

**Contract**: `PendingListUpload(models.Model)`: `organiser` (FK `accounts.User`, `CASCADE`), `event` (FK `Event`, `CASCADE`), `role` (same choices as `AccessLink.role`), `rows` (`JSONField`, default `list` — list of `{'name', 'email', 'errors'}` dicts), `created_at` (`auto_now_add`). `Meta.constraints`: `UniqueConstraint('organiser', 'event', 'role', name='unique_pending_list_upload_per_organiser_event_role')` — at most one in-flight pending upload per organiser+event+role, allowing participant and staff staged uploads to coexist independently. Registered in admin with `list_display = ['event', 'organiser', 'role', 'created_at']`.

### Success Criteria

#### Automated Verification

- `uv run manage.py makemigrations --check --dry-run` reports no missing migrations
- `uv run manage.py migrate` applies cleanly against a freshly deleted local `db.sqlite3`
- `uv run manage.py check` passes with no errors
- Unit test: two `Participant` rows with the same event and normalized email (e.g. `"a@x.com"` vs `"A@X.com "`) raise `IntegrityError`; the same email on two different events succeeds for both
- Unit test: same duplicate-constraint behavior for `StaffMember`
- Unit test: two `PendingListUpload` rows for the same `(organiser, event, role)` raise `IntegrityError`; different `role` values for the same `(organiser, event)` succeed independently
- Unit test: `Participant.clean()`/`StaffMember.clean()` raise `ValidationError` when `access_link.event` differs from the row's own `event`
- Unit test: `Participant.clean()`/`StaffMember.clean()` raise `ValidationError` when `access_link.role` doesn't match the row's own role (a `Participant` with a staff-role link, and vice versa)
- Unit test: `Participant.clean()`/`StaffMember.clean()` raise `ValidationError` when `access_link.label` doesn't match the row's `email`

#### Manual Verification

- `Participant`, `StaffMember`, and `PendingListUpload` all appear in `/admin/` with the expected columns

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 2: Participant list — upload, preview, atomic confirm

### Overview

The full participant-list flow: CSV upload → staged parse → paginated editable preview → atomic confirm creating `Participant` + `AccessLink` rows with generated tokens.

### Changes Required

#### 1. Shared helpers

**File**: `access/services.py`

**Intent**: Small, role-agnostic helpers both this phase and Phase 3 call, avoiding duplicated dedup/token logic between the two flows.

**Contract**: `generate_token()` — returns `secrets.token_urlsafe(32)`, matching F-02's own entropy convention. `email_taken_for_event(email, event, *, exclude_role=None)` — normalizes (`strip().lower()`) and checks both `Participant` and `StaffMember` for that event, returning `True` if found in either (the cross-role dedup check named in Critical Implementation Details); `exclude_role` lets a caller skip re-checking its own table when it's about to do that check separately with row-level context (which page/row) for a better error message.

#### 2. Upload form & view

**File**: `access/forms.py` (new), `access/views.py`

**Intent**: Accept a two-column CSV, decode it robustly, parse into staged rows with per-row validation, ready for preview.

**Contract**: `ParticipantListUploadForm(forms.Form)` with a `csv_file` (`forms.FileField`). `participant_list_upload(request, event_pk)` view, `@login_required`, scoped via `get_object_or_404(Event, pk=event_pk, organiser=request.user)`. Reuses `rooms`' decode-fallback chain (`utf-8-sig` → `cp1252` → `latin-1`) and its `MAX_UPLOAD_BYTES`/`MAX_ROWS` size-check-before-read pattern (new constants in `access/forms.py`, same values as `rooms/forms.py`'s). Parses fixed `name,email` headers (case-insensitive header match; reject with a friendly error if either column is missing). Per-row validation: `email` must pass Django's `EmailValidator`; blank `name` is flagged. Deletes any existing `PendingListUpload` for `(request.user, event, 'participant')` and creates a fresh one with the parsed rows; redirects to preview.

#### 3. Preview, edit, and confirm

**File**: `access/forms.py`, `access/views.py`, `templates/access/participant_list_preview.html` (new)

**Intent**: Let the organiser review/correct parsed rows across pages, then commit them as `Participant` + `AccessLink` rows in one atomic action.

**Contract**: `ParticipantRowForm(forms.Form)` (`name`, `email` `CharField`s) via `forms.formset_factory(..., extra=0)`, one form per row on the current page — mirrors `rooms.RoomRowForm`'s shape and its "read raw `request.POST` values directly, re-validate via a shared row-validator function, don't trust `formset.is_valid()`" pattern (established during `csv-upload-room-mapping`'s own impl-review). `participant_list_preview(request, event_pk)` view, paginated (25/page, matching `rooms.PAGE_SIZE`). **Save & Next/Previous**: per-page field validation only (email format, blank name), writes corrected values back into `PendingListUpload.rows`. **Confirm**: re-validates the current page, then runs one full-set pass over all staged rows checking (a) per-row errors, (b) duplicate emails *within this upload* (`strip().lower()` + `seen` set, mirroring `rooms.full_set_problems()`), (c) duplicate emails against existing `Participant` rows for this event (append-only — reject, don't replace), (d) duplicate emails against existing `StaffMember` rows for this event (cross-role check via `email_taken_for_event()`). If clean: inside `transaction.atomic()`, for each row generate a token, create the `AccessLink` (`role='participant'`, `label=row['email']`), create the `Participant` row pointing at it, then delete the `PendingListUpload`; redirect to the event's edit page with a success message naming the count created.

#### 4. URLs

**File**: `stay_recon/urls.py`

**Contract**: `path('events/<int:event_pk>/participants/upload/', participant_list_upload, name='participant_list_upload')`, `path('events/<int:event_pk>/participants/preview/', participant_list_preview, name='participant_list_preview')`.

### Success Criteria

#### Automated Verification

- Unit test: valid UTF-8 CSV with `name,email` headers creates a `PendingListUpload` with matching rows
- Unit test: CSV missing the `email` (or `name`) column is rejected with a friendly error, no `PendingListUpload` created
- Unit test: cp1252/latin-1 CSV decoded via the fallback chain
- Unit test: oversized upload rejected before reading (mirrors `rooms`' `test_oversized_upload_rejected`)
- Unit test: malformed email flagged per-row after parsing
- Unit test: second upload for the same `(organiser, event, 'participant')` replaces the pending (not confirmed) rows, not duplicates them
- Unit test: page 1/page 2 show correct row slices for a >25-row upload
- Unit test: correcting a row's email on page-save clears its error and persists
- Unit test: confirm blocks on a remaining per-row error, creates no `Participant`/`AccessLink` rows
- Unit test: confirm blocks on a duplicate email *within* the uploaded list, names the colliding rows
- Unit test: confirm blocks on a duplicate email against an *existing* `Participant` for this event (append-only), creates no new row for that email, other valid rows still succeed
- Unit test: confirm blocks when an uploaded participant email already belongs to an existing `StaffMember` for this event (cross-role rejection)
- Unit test: confirm with a fully valid set creates matching `Participant` + `AccessLink` rows (role=`participant`, `label`=email), deletes the `PendingListUpload`
- Unit test: upload/preview/confirm for another organiser's event returns 404

#### Manual Verification

- On the live Render deploy: upload a small real participant CSV, page through the preview, confirm, verify `Participant`/`AccessLink` rows exist (via `/admin/`)
- Deliberately upload a CSV with a malformed email and a duplicate; verify both are caught with locatable messages, not a 500
- Re-upload additional participants for the same event; verify existing participants are untouched and a duplicate email across the two uploads is rejected

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 3: Staff list — CSV upload, manual add, preview, atomic confirm

### Overview

The staff-list flow, mirroring Phase 2's pattern, plus a manual "add one staff member" form for events where a full CSV is unnecessary overhead.

### Changes Required

#### 1. Upload form & view (CSV path)

**File**: `access/forms.py`, `access/views.py`

**Intent**: Same shape as Phase 2's participant upload, targeting `StaffMember`/`role='staff'`.

**Contract**: `StaffListUploadForm` (mirrors `ParticipantListUploadForm`). `staff_list_upload(request, event_pk)` view — same decode/size-cap/parsing contract as `participant_list_upload`, staged into a `PendingListUpload` with `role='staff'`.

#### 2. Manual "add one" form

**File**: `access/forms.py`, `access/views.py`, `templates/access/staff_add_one.html` (new)

**Intent**: Let an organiser with a small staff roster skip the CSV/preview flow entirely and add one person directly.

**Contract**: `StaffAddOneForm(forms.Form)` (`name`, `email`). `staff_add_one(request, event_pk)` view, `@login_required`, scoped via `organiser=request.user`. On valid POST, runs the same validation `email_taken_for_event()` check used by the batch flow (rejecting a duplicate against existing `Participant` or `StaffMember` rows for this event) — if clean, creates the `AccessLink` + `StaffMember` row atomically (same creation order as the batch confirm path), same success messaging. On a duplicate/invalid email, re-renders the form with the error inline — no staging model involved, this is a direct single-row create-or-reject.

#### 3. Preview, edit, and confirm (CSV path)

**File**: `access/forms.py`, `access/views.py`, `templates/access/staff_list_preview.html` (new)

**Intent**: Same shape as Phase 2's participant preview/confirm, targeting `StaffMember`.

**Contract**: `StaffRowForm` (mirrors `ParticipantRowForm`). `staff_list_preview(request, event_pk)` view — identical pagination/save/confirm contract as `participant_list_preview`, with the cross-role check pointed the other direction (checks against existing `Participant` rows, not `StaffMember`), creating `AccessLink` (`role='staff'`) + `StaffMember` rows atomically on confirm.

#### 4. URLs

**File**: `stay_recon/urls.py`

**Contract**: `path('events/<int:event_pk>/staff/upload/', staff_list_upload, name='staff_list_upload')`, `path('events/<int:event_pk>/staff/add/', staff_add_one, name='staff_add_one')`, `path('events/<int:event_pk>/staff/preview/', staff_list_preview, name='staff_list_preview')`.

### Success Criteria

#### Automated Verification

- Unit test: the full CSV upload→preview→confirm success/failure matrix from Phase 2, repeated for staff (valid CSV, missing column, malformed email, within-upload duplicate, cross-upload duplicate append-only, cross-role duplicate against an existing `Participant`, confirm creates `StaffMember`+`AccessLink` with `role='staff'`)
- Unit test: `staff_add_one` with a fresh valid email creates one `StaffMember` + `AccessLink` immediately (no `PendingListUpload` involved)
- Unit test: `staff_add_one` with an email already used by an existing `Participant` for this event is rejected with an inline form error, creates nothing
- Unit test: `staff_add_one` with an email already used by an existing `StaffMember` for this event is rejected the same way
- Unit test: upload/add/preview for another organiser's event returns 404

#### Manual Verification

- On the live Render deploy: upload a small staff CSV, confirm, verify `StaffMember`/`AccessLink` rows exist
- Use the manual "add one" form to add a single staff member; verify it appears without going through any CSV/preview step
- Attempt to manually add a staff member whose email already belongs to an existing participant for the same event; verify it's rejected with a clear inline message

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 4: Links list + CSV export

### Overview

A read-only view listing every generated `AccessLink` (both roles) for an event, with a CSV export, so the organiser can retrieve links to share manually.

### Changes Required

#### 1. Links list view

**File**: `access/views.py`, `templates/access/event_links.html` (new)

**Intent**: Give the organiser one place to see every link generated for their event.

**Contract**: `event_links(request, event_pk)` view, `@login_required`, scoped via `organiser=request.user`. Queries `AccessLink.objects.filter(event=event).select_related(...)` for both roles (joins to `Participant`/`StaffMember` as needed to show name), builds each row's absolute URL via `request.build_absolute_uri(reverse(...))` (participant vs staff URL depending on `role`), renders a table: role, name, email, full link URL. A link to the CSV export sits above the table.

#### 2. CSV export

**File**: `access/views.py`

**Intent**: Bulk-retrieve links for pasting into an external distribution workflow.

**Contract**: `event_links_export(request, event_pk)` view, same scoping, returns a `text/csv` `HttpResponse` (`Content-Disposition: attachment`) with columns `role,name,email,link` for every `AccessLink` on the event, same absolute-URL construction as the list view.

#### 3. URLs

**File**: `stay_recon/urls.py`

**Contract**: `path('events/<int:event_pk>/links/', event_links, name='event_links')`, `path('events/<int:event_pk>/links/export/', event_links_export, name='event_links_export')`.

### Success Criteria

#### Automated Verification

- Unit test: links list shows both participant and staff links for an event, with correct absolute URLs
- Unit test: CSV export returns the expected columns and row count, `Content-Type: text/csv`
- Unit test: links list/export for another organiser's event returns 404

#### Manual Verification

- On the live Render deploy: after creating some participants and staff, open the links list, confirm every link is shown correctly and each URL is copyable/clickable
- Download the CSV export, confirm it opens correctly in a spreadsheet app with the right columns

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before considering this change complete.

---

## Testing Strategy

### Unit Tests

- `Participant`/`StaffMember`/`PendingListUpload` uniqueness/cascade behavior (Phase 1)
- Upload decode-fallback chain, size caps, per-row validation (Phases 2, 3)
- Full-set duplicate detection: within-upload, cross-upload (append-only), cross-role (Phases 2, 3)
- Atomic confirm creating identity + link rows together (Phases 2, 3)
- Manual add-one success/rejection paths (Phase 3)
- Links list/export correctness and object-level scoping (Phase 4)

### Integration Tests

- Full participant flow: upload → preview (multi-page) → confirm → links list shows the new links
- Full staff flow: upload → preview → confirm, and separately: manual add-one → links list shows it
- Cross-role: upload a participant, then attempt to add the same email as staff (CSV and manual) — both rejected

### Manual Testing Steps

1. On the live Render deploy, upload a small participant CSV; page through preview; confirm; verify via `/admin/` and the links list.
2. Upload a staff CSV for the same event; confirm; verify.
3. Use the manual add-one staff form to add one more staff member.
4. Attempt to add a staff member (CSV or manual) using an email already registered as a participant for this event; confirm it's rejected.
5. Re-upload an additional participant CSV containing one brand-new email and one already-registered email; confirm the new one is added and the duplicate is rejected, with existing participants untouched.
6. Open the links list, confirm all links render correctly; download the CSV export and confirm it opens correctly.

## Performance Considerations

None specific to this change — `data_volume: small` per the PRD, and token/email lookups are indexed (`token` already `db_index=True`; the new `Lower(Trim(email))` constraints are backed by their own indexes).

## Migration Notes

Purely additive: two new models plus the staging model in the existing `access` app, no existing data affected.

## References

- Research: `context/changes/participant-staff-lists-and-links/research.md`
- Prior CSV-upload precedent: `context/archive/2026-09-14-csv-upload-room-mapping/plan.md` (staging model, validation timing, size-cap lesson)
- Prior access-link foundation: `context/archive/2026-09-16-access-link-staff-session-scaffold/plan.md` (`AccessLink` contract, token entropy convention)

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles.

### Phase 1: Data layer — Participant, StaffMember, PendingListUpload

#### Automated

- [x] 1.1 `makemigrations --check --dry-run` reports no missing migrations — c3ea4e9
- [x] 1.2 `migrate` applies cleanly against a freshly deleted local `db.sqlite3` — c3ea4e9
- [x] 1.3 `manage.py check` passes — c3ea4e9
- [x] 1.4 Participant duplicate-email-per-event constraint enforced — c3ea4e9
- [x] 1.5 StaffMember duplicate-email-per-event constraint enforced — c3ea4e9
- [x] 1.6 PendingListUpload unique-per-(organiser,event,role) constraint enforced; different roles coexist — c3ea4e9
- [x] 1.8 Participant/StaffMember clean() rejects a mismatched access_link event — c3ea4e9
- [x] 1.9 Participant/StaffMember clean() rejects a mismatched access_link role — c3ea4e9
- [x] 1.10 Participant/StaffMember clean() rejects an access_link label not matching email — c3ea4e9

#### Manual

- [x] 1.7 Participant, StaffMember, PendingListUpload appear in `/admin/` with expected columns — c3ea4e9

### Phase 2: Participant list — upload, preview, atomic confirm

#### Automated

- [ ] 2.1 Valid CSV creates PendingListUpload with matching rows
- [ ] 2.2 CSV missing a required column rejected, no PendingListUpload created
- [ ] 2.3 cp1252/latin-1 CSV decoded via fallback chain
- [ ] 2.4 Oversized upload rejected before reading
- [ ] 2.5 Malformed email flagged per-row
- [ ] 2.6 Second upload replaces pending (unconfirmed) rows, not duplicates
- [ ] 2.7 Pagination shows correct row slices
- [ ] 2.8 Correcting a row on page-save clears its error and persists
- [ ] 2.9 Confirm blocks on remaining per-row error
- [ ] 2.10 Confirm blocks on within-upload duplicate email
- [ ] 2.11 Confirm blocks on duplicate against existing Participant (append-only)
- [ ] 2.12 Confirm blocks on duplicate against existing StaffMember (cross-role)
- [ ] 2.13 Confirm with valid data creates Participant + AccessLink rows, deletes PendingListUpload
- [ ] 2.14 Upload/preview/confirm for another organiser's event returns 404

#### Manual

- [ ] 2.15 Live: upload, page through preview, confirm; verify rows via /admin/
- [ ] 2.16 Live: malformed email + duplicate both caught with locatable messages, no 500
- [ ] 2.17 Live: re-upload adds new participants, existing untouched, duplicate rejected

### Phase 3: Staff list — CSV upload, manual add, preview, atomic confirm

#### Automated

- [ ] 3.1 Valid staff CSV creates PendingListUpload with matching rows
- [ ] 3.2 CSV missing a required column rejected
- [ ] 3.3 Malformed email flagged per-row
- [ ] 3.4 Confirm blocks on within-upload duplicate
- [ ] 3.5 Confirm blocks on duplicate against existing StaffMember (append-only)
- [ ] 3.6 Confirm blocks on duplicate against existing Participant (cross-role)
- [ ] 3.7 Confirm with valid data creates StaffMember + AccessLink rows with role='staff'
- [ ] 3.8 staff_add_one with a fresh email creates one StaffMember + AccessLink immediately
- [ ] 3.9 staff_add_one rejects an email already used by an existing Participant
- [ ] 3.10 staff_add_one rejects an email already used by an existing StaffMember
- [ ] 3.11 Upload/add/preview for another organiser's event returns 404

#### Manual

- [ ] 3.12 Live: upload staff CSV, confirm, verify rows
- [ ] 3.13 Live: manual add-one form adds a single staff member
- [ ] 3.14 Live: manual add rejects an email already used by a participant, with a clear message

### Phase 4: Links list + CSV export

#### Automated

- [ ] 4.1 Links list shows both participant and staff links with correct absolute URLs
- [ ] 4.2 CSV export returns expected columns/row count and Content-Type
- [ ] 4.3 Links list/export for another organiser's event returns 404

#### Manual

- [ ] 4.4 Live: links list renders all links correctly, each URL copyable/clickable
- [ ] 4.5 Live: CSV export downloads and opens correctly with the right columns
