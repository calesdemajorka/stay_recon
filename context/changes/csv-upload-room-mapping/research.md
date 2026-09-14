---
date: 2026-09-14T13:48:15+0000
researcher: Claude
git_commit: 3afd66b8d43ba89a6b394746157c222bd1a9f62a
branch: dev
repository: calesdemajorka/stay_recon
topic: "CSV upload + room mapping (S-02 / FR-002): library choice, storage architecture, UI flow"
tags: [research, codebase, events, csv, file-upload, storage, django-forms]
status: complete
last_updated: 2026-09-14
last_updated_by: Claude
---

# Research: CSV upload + room mapping (S-02 / FR-002)

**Date**: 2026-09-14T13:48:15+0000
**Researcher**: Claude
**Git Commit**: 3afd66b8d43ba89a6b394746157c222bd1a9f62a
**Branch**: dev
**Repository**: calesdemajorka/stay_recon

## Research Question

What do we need to know to plan S-02 (`csv-upload-room-mapping`, roadmap ID `S-02`, PRD `FR-002`): "Organiser can upload a hotel's room CSV and manually map its columns (room number, type, capacity), with a preview/confirm step showing parsed rooms before they're saved."

Deep-dive requested on two fronts: (1) CSV-parsing library choice and robustness to real-world hotel-export variance, and (2) file-upload/storage architecture given this codebase's conventions and Render's hosting constraints, plus how a multi-step upload→map→preview→confirm flow fits the project's plain server-rendered-template style.

## Summary

- **No file-upload code exists anywhere in the codebase yet.** This is genuinely new ground — no `FileField`, no `request.FILES`, no precedent to extend.
- **Render's free-tier web service has no persistent disk, and none is provisioned in `render.yaml`.** This is a hard platform restriction (confirmed via Render's own docs, same class of constraint as the SMTP-port block found during `F-01`), not a soft default — the free compute plan doesn't support attaching a Disk at all.
- **The raw CSV file does not need to persist long-term** — only the final, organiser-confirmed, normalized `Room` rows need to survive, and those belong in Postgres (already provisioned) like every other model in this project. This means the disk constraint is avoidable by architecture, not by paying for a disk or standing up S3/R2.
- **Recommended architecture**: a 3-step, session-token-scoped flow (upload+preview-headers → map columns+preview rows → confirm+save), backed by a short-lived `PendingUpload` Postgres model (not raw Django session storage) holding the parsed CSV as JSON between steps, deleted on confirm.
- **Recommended library**: Python's stdlib `csv` module (`DictReader` for header discovery, `reader` for the mapped re-parse) with a manual `utf-8-sig` → `cp1252` → `latin-1` decode fallback chain. No new dependency. `pandas` is the wrong tool (unwanted type inference); `django-import-export` implements a similar-shaped flow but assumes code-time field mappings, not a runtime human-chosen mapping — adapting it would be more work than hand-rolling.
- **This contradicts an existing risk-register entry** (`context/foundation/infrastructure.md:59,90`) that recommends wiring external S3-compatible storage "before FR-002 ships." That recommendation appears to have been made without considering the in-memory/DB-token architecture below, which avoids the need for object storage in v1 entirely. Worth flagging explicitly in the plan and, ideally, updating that risk entry once the plan is settled.
- **Existing codebase conventions are strong and directly reusable**: `ModelForm` + `clean()` cross-field validation + `save(commit=False)` stamping pattern (`events/forms.py`), function-based `@login_required` views with a shared `_save_or_duplicate_error()`-style IntegrityError-race guard (`events/views.py`), `get_object_or_404(Event, pk=pk, organiser=request.user)` for object-level per-organiser scoping, `templates/<app>/<name>.html` extending `base.html` with `{{ form.as_p }}`, all with no per-app `urls.py` (routes go directly in `stay_recon/urls.py`).

## Detailed Findings

### File upload — no precedent, greenfield

- `grep -rn "FileField\|ImageField\|request\.FILES\|forms\.FileField\|multipart" accounts/ events/ stay_recon/` → zero hits. Confirmed: no file-upload handling exists anywhere in the codebase today.
- `STORAGES` in [`stay_recon/settings.py:146-153`](https://github.com/calesdemajorka/stay_recon/blob/3afd66b8d43ba89a6b394746157c222bd1a9f62a/stay_recon/settings.py#L146-L153) is plain `FileSystemStorage` for `default`, whitenoise's compressed manifest storage for `staticfiles`. No `MEDIA_ROOT`/`MEDIA_URL` configured anywhere.
- `SESSION_ENGINE` is unset (Django default `django.contrib.sessions.backends.db` applies) — `django.contrib.sessions` is installed and `SessionMiddleware` active ([`stay_recon/settings.py:53,65`](https://github.com/calesdemajorka/stay_recon/blob/3afd66b8d43ba89a6b394746157c222bd1a9f62a/stay_recon/settings.py#L53)).
- `DATABASES` uses `dj_database_url.config()` — Postgres in production via `DATABASE_URL`, SQLite locally ([`stay_recon/settings.py:100-106`](https://github.com/calesdemajorka/stay_recon/blob/3afd66b8d43ba89a6b394746157c222bd1a9f62a/stay_recon/settings.py#L100-L106)).

### Render storage constraints — confirmed hard limit

- Render's free-tier web services have **no persistent disk, period** — filesystem changes are lost on every redeploy/restart/spin-down, and the Free compute plan does not support attaching a Disk at all (not a soft default). Source: [Render Disks docs](https://render.com/docs/disks), [Render Free tier docs](https://render.com/docs/free).
- `render.yaml` confirms no `disk:` key is present for the `stay-recon` web service.
- **Render Disks** exist as a paid add-on ($0.25/GB/month), available only on paid instance types, and attaching one pins the service to a single non-scalable instance and **disables zero-downtime deploys**. Overkill for transient upload bytes that don't need to outlive a request flow. Source: [Render Disks docs](https://render.com/docs/disks).
- Render's own guidance: durable data belongs in Postgres, already provisioned here.

### Existing infrastructure risk-register entry (worth revisiting)

- [`context/foundation/infrastructure.md:59`](): "No first-party object storage — the hotel CSV uploads (FR-002) need external S3-compatible storage wired up from day one; Render doesn't provide this itself."
- [`context/foundation/infrastructure.md:90`](): Risk register row — "No first-party object storage for CSV/booking uploads | Devil's advocate | H | M | Wire an external S3-compatible bucket (e.g. Cloudflare R2, AWS S3) before FR-002 (CSV upload) ships."
- This research's finding: **that recommendation is avoidable** if the raw CSV is never persisted to disk/object storage at all — only parsed, mapped `Room` rows need to survive, and those go to Postgres like everything else. The risk register's premise (uploaded files need durable storage) doesn't hold once the architecture treats the CSV as transient, in-flight data rather than a stored asset. Recommend the plan explicitly note this and treat the S3/R2 wiring as deferred/unnecessary for v1, not silently dropped.

### Multi-step flow architecture — recommended: token-scoped `PendingUpload` model

Three real options were evaluated (Django Forum precedent: [multi-step form data storage](https://forum.djangoproject.com/t/creating-a-multi-steps-form-and-storing-data-effectively-till-the-final-step-and-saving-all-data-in-a-single-db-table/20493)):

1. **Re-upload the file every step** — rejected. Forces the organiser to re-select the file repeatedly (bad UX), duplicates parsing logic, and gains nothing since there's no disk to persist the original anyway.
2. **Single combined step** (sniff headers client-side, submit file + mapping together) — rejected. This project has no JS framework (confirmed: `templates/base.html` has no script/extrahead hooks), and column mapping is a genuine human decision that benefits from seeing headers first — collapsing steps removes the preview/confirm safety value FR-002 explicitly asks for.
3. **Session/token-based 3-step flow** (recommended) — Step 1 uploads the CSV, parses headers (`csv.DictReader`), renders the column-mapping form. Step 2 posts the mapping, re-parses the stored CSV text applying the mapping, renders a preview. Step 3 confirms and writes `Room` rows to Postgres.

For where the parsed/raw CSV data lives *between* those steps: **don't use raw `request.session` storage** for the parsed rows. Django's DB-backed session (`django_session` table, `TextField`) has no hard size cap and would technically work, but a dedicated short-lived `PendingUpload` model (CSV text or parsed rows in a field, `created_at`, FK to the organiser and target `Event`) is cleaner — avoids bloating the shared session table, survives session-cookie edge cases, is trivially inspectable in Postgres if a row gets stuck, and costs almost nothing extra given Postgres is already provisioned. Delete the row on confirm; a periodic/manual cleanup handles abandoned uploads.

### CSV library choice — stdlib `csv`, no new dependency

- **`csv.DictReader`/`csv.reader` (stdlib) is the right-sized tool.** Pandas' main value — automatic dtype inference — is unwanted here (it would silently coerce a room number like `"007"` to `7`, or misinterpret dates); pandas is built for *analysis*, stdlib `csv` for *streaming reads without a full DataFrame*, which matches this "read headers, human maps, re-parse as strings" flow exactly.
- **Delimiter variance** (comma/semicolon/tab): `csv.Sniffer().sniff()` can detect dialect from a sample, or simply let the organiser pick a delimiter alongside the column mapping — either is trivial with stdlib, no extra dependency.
- **Quoted-field edge cases**: stdlib `csv` handles RFC-4180 quoting correctly by default; open with `newline=''` per Python's own docs to avoid embedded-newline corruption.
- **BOM handling**: open with `encoding='utf-8-sig'`, which transparently strips a leading UTF-8 BOM that would otherwise corrupt the first header name.
- **`polars`/`csvkit`**: both are heavier, analytics/CLI-oriented tools with no advantage here — net-new dependencies for capability not needed.
- **`django-import-export`**: genuinely implements a similar upload→preview→confirm shape, but its column-mapping model assumes *code-time declared* field↔header mappings via a `Resource` class — not a *runtime, per-upload, human-chosen* mapping UI, which is the actual requirement here. Adapting it to dynamic mapping means fighting its Resource/widget abstraction plus pulling in its `tablib` dependency. A ~100-150 line hand-rolled view is simpler than bending this package to an unintended use. Source: [django-import-export docs](https://django-import-export.readthedocs.io/en/3.3.6/advanced_usage.html), [related upstream issue on dynamic column mapping](https://github.com/django-import-export/django-import-export/issues/772).
- **Encoding detection**: `charset-normalizer` (MIT, actively maintained, the default detector behind `requests`) is a reasonable future upgrade, but for v1 a manual fallback-decode chain (`utf-8-sig` → `cp1252` → `latin-1`, the last of which never raises since it maps every byte 1:1) covers essentially all real-world hotel/legacy CSV exports without a new dependency.

**Recommendation**: hand-roll with stdlib `csv` + a manual decode-fallback chain. Zero new dependencies, matches `pyproject.toml`'s existing minimal-dependency posture (`django`, `dj-database-url`, `gunicorn`, `psycopg`, `whitenoise` only).

## Code References

- [`events/models.py:7-45`](https://github.com/calesdemajorka/stay_recon/blob/3afd66b8d43ba89a6b394746157c222bd1a9f62a/events/models.py#L7-L45) — `Event` model: no explicit PK (implicit `id`/`pk`), `organiser` FK to `accounts.User`, functional `UniqueConstraint` + `clean()` pattern a future `Room` model / `PendingUpload` model can mirror.
- [`events/forms.py:11-86`](https://github.com/calesdemajorka/stay_recon/blob/3afd66b8d43ba89a6b394746157c222bd1a9f62a/events/forms.py#L11-L86) — `EventForm`: `ModelForm` + injected `organiser` kwarg + `clean()` cross-field validation + `save(commit=False)` stamping — the pattern to replicate for a `RoomMappingForm`/`RoomConfirmForm`.
- [`events/views.py:9-43`](https://github.com/calesdemajorka/stay_recon/blob/3afd66b8d43ba89a6b394746157c222bd1a9f62a/events/views.py#L9-L43) — `_save_or_duplicate_error()` helper (transaction.atomic + IntegrityError→friendly-error), `event_create`/`event_edit` view shape, `get_object_or_404(Event, pk=pk, organiser=request.user)` object-level scoping to replicate for any Room-upload view scoped to a parent `Event`.
- [`accounts/views.py:8-23`](https://github.com/calesdemajorka/stay_recon/blob/3afd66b8d43ba89a6b394746157c222bd1a9f62a/accounts/views.py#L8-L23) — `dashboard`/`signup` view shape (POST/else branching, `login_required`, redirect-on-success).
- [`stay_recon/settings.py:100-153`](https://github.com/calesdemajorka/stay_recon/blob/3afd66b8d43ba89a6b394746157c222bd1a9f62a/stay_recon/settings.py#L100-L153) — `DATABASES`, `STORAGES` (no `MEDIA_ROOT`), no `SESSION_ENGINE` override.
- [`render.yaml`](https://github.com/calesdemajorka/stay_recon/blob/3afd66b8d43ba89a6b394746157c222bd1a9f62a/render.yaml) — no `disk:` key; `buildFilter.paths` will need an entry for any new app this feature adds (following the pattern already established for `accounts/**`, `events/**`, `templates/**`).
- `templates/events/event_form.html`, `templates/accounts/dashboard.html`, `templates/base.html` — template conventions (`{% extends "base.html" %}`, `{{ form.as_p }}`, no CSS framework, no JS hooks currently).

## Architecture Insights

- This codebase's established pattern for "guardrail that must survive a race condition" (duplicate-name-and-date on `Event`) is: DB-level `UniqueConstraint` + form-level pre-check + view-level `IntegrityError` catch converting to a friendly error. The same three-layer pattern is directly reusable for room-number uniqueness within an event once `Room` exists.
- Every model so far uses Django's implicit auto `id` PK — no custom PK convention to break from.
- No JS framework anywhere in this project — any "live preview" or "dynamic column-mapping" UI must be achievable via plain server round-trips (which the 3-step flow above is designed around) or the plan needs to explicitly introduce a JS dependency (not recommended given the "no new dependency" pattern held so far).
- Per-organiser data scoping is always enforced at the query/view level (`get_object_or_404(..., organiser=request.user)` or `request.user.<related_name>`), never left to template-level filtering — the same must apply to any Room CSV upload view (scope to the parent `Event`, which is itself already organiser-scoped).

## Historical Context (from prior changes)

- `context/changes/csv-upload-room-mapping/change.md` — this change's own folder, currently just scaffolding (created via `/10x-new` this session, no plan yet).
- [`context/archive/2026-09-14-create-event/plan.md:37`](): "CSV upload, room data, or any hotel-inventory concept — that's `S-02`, a separate change; `Event` here has no fields for room/venue inventory." — confirms `S-02` starts from a clean `Event` model with no anticipatory fields to work around.
- [`context/archive/2026-09-14-create-event/plan-brief.md:7,33`](): reiterates the same boundary — `S-01` deliberately left CSV/room data entirely out of scope, and the "CSV upload, participants, bookings" phrase recurs as the next-up heavy work.
- [`context/archive/2026-09-11-organiser-auth-app-scaffold/plan-brief.md:7`](): "every other roadmap slice (creating events, uploading CSVs, everything) needs an app to live in" — confirms the original intent that CSV upload gets its own app/model, consistent with this research's assumption of a new `Room` (and likely `PendingUpload`) model, probably in a new app or added to `events`.

## Related Research

None — this is the first research document for this change and the first CSV/file-upload-focused research in this project.

## Open Questions

1. **New app vs. extend `events`?** Should `Room`/`PendingUpload` live in a new app (e.g. `rooms` or `inventory`) or inside the existing `events` app? Not resolved here — this is a `/10x-plan` decision, not a research question, since it's a judgment call with no external-research answer (the codebase has exactly one precedent so far: `events` was a new app because it's a new domain concept; `Room` is arguably a sub-concept of `Event` rather than a peer).
2. **`PendingUpload` cleanup mechanics**: should abandoned uploads (organiser uploads a CSV, never completes mapping/confirm) be cleaned up via a scheduled job, on next-login sweep, or simply left until the organiser starts a new upload (overwriting/replacing the pending one)? No FR mandates this; worth a `/10x-plan` decision given `top_blocker: time`.
3. **Should `context/foundation/infrastructure.md`'s risk-register entry be updated** once the plan confirms the no-object-storage architecture, so future readers don't re-flag S3/R2 as blocking? Recommend yes, but that's a plan/implementation follow-up, not this research document's job.
