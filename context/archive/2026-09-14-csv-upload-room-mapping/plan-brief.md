# CSV Upload & Room Mapping — Plan Brief

> Full plan: `context/changes/csv-upload-room-mapping/plan.md`
> Research: `context/changes/csv-upload-room-mapping/research.md`

## What & Why

StayRecon has events but no room inventory yet. This change lets an organiser upload a hotel's room CSV, map its arbitrary columns to room number/type/capacity, review and correct a paginated preview, and confirm to save normalized `Room` records — the CSV-variance-to-clean-data step the whole product exists to solve. It's roadmap item `S-02` (`FR-002`).

## Starting Point

`events.Event` exists with no room fields (deliberately — S-01 kept it minimal). No file-upload code exists anywhere in the codebase. No object storage or persistent disk is provisioned on Render.

## Desired End State

An organiser, editing one of their events, uploads a CSV, maps columns, pages through an editable preview fixing any flagged rows, and confirms — creating `Room` records for that event. Re-uploading after rooms already exist warns first, then replaces them entirely if confirmed.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| CSV library | Python stdlib `csv` (`DictReader`), no new dependency | Matches "human maps columns, no type inference needed" exactly; pandas' auto-typing is actively unwanted (would mangle room numbers like `"007"`). | Research |
| Storage architecture | `PendingUpload` Postgres model, not raw session storage or S3/R2 | Raw CSV never needs to persist past the request cycle it arrives in; Render's free tier has no disk anyway. | Research |
| App placement | New `rooms` app, not extending `events` | `Room` will be heavily referenced by later slices (`S-04`, `S-08`, `S-09`) — keeping it separate now avoids `events` becoming a dumping ground. | Plan |
| Duplicate room numbers (same CSV) | Reject at confirm, name the collision | Matches the codebase's established "guard, don't silently merge" pattern (`Event`'s own duplicate guard); silent merge would risk the PRD's reconciliation-accuracy guardrail. | Plan |
| Malformed rows | Flag in preview, block confirm until fixed/excluded | The preview *is* FR-002's validation surface — no partial-garbage data should reach Postgres. | Plan |
| Column-mapping UI | One dropdown per target field (3 fixed fields), not per CSV column | Simpler and less error-prone than mapping an unpredictable number of arbitrary CSV columns. | Plan |
| Preview | Paginated (25/page), inline-editable | User's explicit choice over the simpler "show all, no edit" default — lets the organiser fix a typo without re-uploading. | Plan |
| Cross-page validation timing | Per-page field validation on every save; the one cross-page duplicate scan runs only at Confirm | Explicit simplification — re-scanning the full set after every page navigation was unnecessary complexity. | Plan |
| Re-upload with existing rooms | Warn with room count, require explicit confirmation, then wipe-and-replace | Prevents silently destroying inventory once bookings could reference it; no FR asks for a separate edit feature. | Plan |
| PendingUpload cleanup | None scheduled — a new upload just overwrites the old pending row | Zero new infra for a problem that doesn't matter at `data_volume: small`. | Plan |

## Scope

**In scope:** `rooms` app (`Room`, `PendingUpload` models), 4-step upload→map→preview→confirm flow, encoding-robust CSV parsing, per-row and cross-row validation, atomic wipe-and-replace re-upload.

**Out of scope:** standalone Room edit/delete UI, a dedicated room-list page, object storage/S3/R2, scheduled `PendingUpload` cleanup, real-time cross-page duplicate warnings while editing, async/background CSV processing, updating `infrastructure.md`'s now-superseded S3/R2 risk note.

## Architecture / Approach

New `rooms` app, `Room` FK'd to `Event`. A `PendingUpload` row (JSON fields for headers/raw rows/column mapping/mapped rows) holds all in-flight state between the upload, mapping, and preview/confirm steps — no raw file ever touches disk or object storage. The preview/confirm screen is one view handling pagination, per-page-save validation, and the final confirm action together, since they share the same formset and template.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. `rooms` app scaffold | `Room`/`PendingUpload` models, constraints, admin | Constraint expressions must correctly scope duplicates per-event/per-(organiser,event) |
| 2. CSV upload | Upload view, decode fallback chain, re-upload warning gate | Encoding edge cases (BOM, non-UTF-8) |
| 3. Column mapping | Mapping form, `mapped_rows` computation + initial validation | None significant — small, well-scoped step |
| 4. Preview, edit, confirm | Paginated editable formset, confirm-time duplicate scan, atomic wipe-and-replace | `bulk_create()` skips model validation — confirm view's own checks are the only safety net |

**Prerequisites:** `S-01` (done), `F-01` (done).
**Estimated effort:** not estimated (roadmap convention — no time units; sequence, not schedule).

## Open Risks & Assumptions

- No dedicated room-list view is built here — an organiser's only way to see confirmed rooms post-upload is `/admin/` or the confirm success message's count, until a later slice needs a real view.
- `context/foundation/infrastructure.md`'s risk-register entry recommending S3/R2 "before FR-002 ships" is superseded by this plan's architecture but not edited as part of this change — worth a follow-up note so it doesn't mislead future readers.
- Realistic hotel CSV sizes are assumed well under a few hundred rows (`data_volume: small`); if that assumption is wrong, JSON-in-Postgres and 25-row pagination may need revisiting.

## Success Criteria (Summary)

- An organiser can upload, map, review/correct, and confirm a hotel CSV into normalized `Room` records entirely on the live Render deploy.
- Malformed and duplicate rows are always caught before reaching Postgres, with a locatable (not generic) error.
- Re-uploading for an event with existing rooms never silently destroys data — it warns first.
- One organiser can never see or affect another organiser's pending upload or rooms.
