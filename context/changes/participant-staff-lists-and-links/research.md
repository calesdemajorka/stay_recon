---
date: 2026-09-17T12:05:10+02:00
researcher: Michal Zajaczkowski
git_commit: 7c5aa71faa2aaca9f8ecef042ee1bdb87718e28e
branch: dev
repository: stay_recon
topic: "S-03: participant/staff lists (FR-003) and access-link generation (FR-004)"
tags: [research, codebase, access-links, participant-list, staff-list, s-03, fr-003, fr-004]
status: complete
last_updated: 2026-09-17
last_updated_by: Michal Zajaczkowski
---

# Research: Participant/staff lists and access-link generation (S-03)

**Date**: 2026-09-17T12:05:10+02:00
**Researcher**: Michal Zajaczkowski
**Git Commit**: 7c5aa71faa2aaca9f8ecef042ee1bdb87718e28e
**Branch**: dev
**Repository**: stay_recon

## Research Question

How should S-03 be built: the organiser adds participant and staff lists (FR-003 — malformed emails rejected, duplicates flagged at upload time) and gets a unique access link per person (FR-004 — expiring when the event's booking window closes)? Scope agreed with the user: treat participants and staff as two genuinely separate list concepts (not one combined list with a role column), and briefly trace forward what S-04 (booking) and S-08 (check-in) will eventually need, so S-03 doesn't under- or over-build.

## Summary

**`AccessLink` (built by the now-archived F-02) cannot satisfy FR-003 on its own.** It has no `Meta.constraints` at all — only `token` is `unique=True`. Nothing currently stops two rows sharing the same `event`+`role`+`label`, and `label` is a bare `CharField` with no email-format validation. S-03 must either add a `UniqueConstraint(Lower(Trim('label')), 'event', 'role', ...)` — matching the exact convention already used by `Event` (`unique_event_name_dates_per_organiser`) and `Room` (`unique_room_number_per_event`) — and/or a dedicated `Participant`/`StaffMember` model with a real `EmailField`. F-02's own plan explicitly left this to S-03: no token-creation helper exists (`access/services.py` has only read-side functions), so S-03 must generate tokens itself (`secrets.token_urlsafe(32)`, matching F-02's own convention).

**No column-mapping is needed.** The `rooms` app's 4-step upload→map→preview→confirm flow exists specifically because *hotel* CSVs vary unpredictably per third party (that's FR-002/Non-Goals' stated rationale). Participant/staff lists are organiser-authored, not third-party exports — the PRD gives no basis for arbitrary column mapping here. A fixed-shape input (one email per line, or a two-column CSV with fixed headers) fully satisfies FR-003. However, several *other* `rooms` patterns transfer directly and should be reused: the staging-then-commit model (`PendingUpload`-style), the "flag at parse, block confirm until fixed" validation timing, the `strip().lower()` duplicate-detection pattern (`full_set_problems()`), the encoding-fallback chain, and the `organiser=request.user` object-scoping convention.

**The PRD is genuinely silent on how the organiser sees/shares the generated links.** Non-Goals rules out automated invitation emails ("organiser shares access links manually"), but nothing in the PRD, shape-notes, or any prior change specifies a links-list view, copy-to-clipboard UI, or export mechanism. This is real open ground for planning, not an oversight in this research — confirmed absent everywhere searched.

**Forward-trace of S-04/S-08 data needs** (FR-derived, not a final decision): identity fields (name, email, role) plausibly belong to S-03 itself; booking-state fields (preferences per FR-014, booked-room reference per FR-008, change-count per FR-009) plausibly belong to S-04, which the roadmap's own Risk note already claims ownership of FR-014's suggestion logic; staff-action-state fields (checked-in flag per FR-011, pack-handed-over flag per FR-013) plausibly belong to S-08. S-03's roadmap Outcome text stops at "list + link" with no mention of preferences, bookings, or check-in — unlike F-02, S-03 doesn't state this boundary explicitly as a Risk, it just doesn't mention the booking-state fields at all.

## Detailed Findings

### `AccessLink`'s exact contract and its gap against FR-003

- `access/models.py:6-22` — `AccessLink`: `event` (FK, CASCADE, `related_name='access_links'`), `role` (`CharField(max_length=20, choices=...)`, `ROLE_PARTICIPANT='participant'`/`ROLE_STAFF='staff'`), `label` (`CharField(max_length=255)`, no validation), `token` (`CharField(max_length=64, unique=True, db_index=True)` — the **only** unique constraint anywhere on the model), `is_revoked` (`BooleanField(default=False)`), `created_at` (`auto_now_add`).
- No `class Meta` / `constraints` at all — confirmed absent in `access/migrations/0001_initial.py:16-27` too. Two `AccessLink` rows can currently share the same `event`+`role`+`label` with nothing stopping it.
- Established codebase convention for exactly this "reject duplicate string per scope" requirement: `UniqueConstraint(Lower(Trim(<field>)), <scope>)` — `events/models.py:21-29` (`unique_event_name_dates_per_organiser`) and `rooms/models.py:15-21` (`unique_room_number_per_event`). S-03 should follow this same pattern for participant/staff email dedup, scoped to `event`+`role`.
- No email-format validation anywhere in `access/` (no `EmailField`, no `EmailValidator`, no `clean()` — contrast `events/models.py:31-42`'s `clean()` which does real cross-field validation).
- `access/services.py` (58 lines, read fully): `verify_access_link` (read-only), `establish_staff_session` (session write, no DB write), `get_staff_access_link` (read-only). **No function creates an `AccessLink` row or generates a token anywhere** — confirmed matches `context/archive/2026-09-16-access-link-staff-session-scaffold/plan.md:36`'s explicit "No token-creation helper function — S-03 will create AccessLink rows directly."
- Token entropy convention to follow: `secrets.token_urlsafe(32)` (per the archived F-02 plan's own design, `plan.md:25`).
- `access/admin.py:6-8` — `list_display = ['event', 'role', 'label', 'is_revoked', 'created_at']`, no `search_fields`/`list_filter`. Display-ordering hint only, no validation/dedup signal.

### Why column-mapping doesn't transfer, but other `rooms` patterns do

- FR-002 (`prd.md:58`) and its Non-Goals (`prd.md:110`, "no smart per-hotel schema detection") make explicit that column-mapping exists because "every hotel exports that CSV in a different format" (`prd.md:20-22`) — a third-party-format-variance problem.
- FR-003 (`prd.md:60-61`) says only "Organiser can add participant and staff lists to an event; malformed emails are rejected and duplicates flagged at upload time" — no CSV, no arbitrary columns, no third-party source implied. The Socratic note's concern is "no validation on list data could silently break link generation," resolved via format validation + dedup — not column ambiguity.
- **Patterns that transfer directly**: the `PendingUpload`-style staging model (`rooms/models.py:27-42`, parse into a pending row before touching the real table); "flag at parse, block confirm until fixed" timing (`rooms/forms.py:78-102`'s `full_set_problems()`, checked only at confirm — `rooms/views.py:195-200`); the encoding-fallback chain (`DECODE_ENCODINGS = ('utf-8-sig', 'cp1252', 'latin-1')`, `rooms/views.py:28-39`); the `organiser=request.user` object-scoping convention (`rooms/views.py:44,105,144`); size/row caps validated before persist (`rooms/forms.py:3-6`).
- **Patterns specific to rooms' column-mapping problem, likely not needed**: `ColumnMappingForm` + the `csv_map_columns` step (`rooms/forms.py:21-30`, `rooms/views.py:104-122`); `compute_mapped_rows()`'s column-indirection (`rooms/forms.py:50-59`). The paginated per-page-edit `RoomFormSet` UI (`rooms/forms.py:62-76`, `views.py:125-220`) is a deliberate y/n call for S-03, not an automatic carry-over — worth deciding based on expected list size, not assumed.
- **Duplicate-detection precedent, directly applicable**: `rooms/forms.py:78-102`'s single-pass `strip().lower()` normalization + `seen` dict, mirrored at the DB level by the `Lower(Trim())` constraint — maps directly onto duplicate-email detection for FR-003.

### Link distribution — the PRD's genuine silence

- `prd.md:111` (Non-Goals): "No automated invitation emails — organiser shares access links manually." No mention anywhere of a links-list view, copy-to-clipboard UI, or CSV export of generated links.
- `shape-notes.md` is near-identical to the PRD with no additional color — no description of organisers' current (pre-product) list format or link-sharing method.
- Searched all of `context/changes/**` and `context/archive/**` for "clipboard", "copy link", "links list", "export" in this context — zero hits beyond plain scope-boundary restatements (e.g. `context/archive/2026-09-16-access-link-staff-session-scaffold/plan.md:30`, "No link-generation UI or participant/staff list upload — that's S-03's job entirely").
- **This is genuinely open ground** — a real planning decision, not something this research can resolve by inference.

### Roadmap consumer contract, confirmed

- S-03's own Outcome (`roadmap.md:134`): "Organiser can add participant and staff lists (malformed emails rejected, duplicates flagged) and receive a unique access link per person, expiring when the event's check-in window closes." — stops at list + link.
- F-02's "Unlocks" line (`roadmap.md:98`) names S-03 as the consumer of link *generation*, confirming F-02 owns verification only, S-03 owns generation.
- S-04's Prerequisites (`roadmap.md:149`) and S-08's Prerequisites (`roadmap.md:198`) both list `S-03`, confirming both depend on whatever S-03 produces.
- S-04's own Risk (`roadmap.md:153`) explicitly claims FR-014's suggestion/consolidation logic as *its* algorithmic risk — a strong signal that preference-related state belongs to S-04, not S-03.

### Forward-trace: what S-04/S-08 will eventually need (FR-derived, not decided)

| FR | Implied state | Plausible owner |
| --- | --- | --- |
| FR-014 (stated preferences) | preferences field | S-04 (roadmap's own Risk claims this) |
| FR-008 (book a room) | booked-room reference | S-04 |
| FR-009 (change booking, cap 3) | per-participant change-count | S-04 |
| FR-010 (read-only after window) | derived view, not new state | S-04/S-06 |
| FR-011 (staff check-in) | checked-in flag/timestamp | S-08 |
| FR-012 (staff edit, event-day only) | reuses the booking record | S-08 (no new field) |
| FR-013 (pack handed over) | pack-handed-over boolean | S-08 |

Plausibly S-03's own fields (identity, not booking/action state): name, email, role, event association, the access-link/token record itself.

## Code References

- `access/models.py:6-22` — `AccessLink` model, no `Meta.constraints`
- `access/migrations/0001_initial.py:16-27` — confirms no DB-level dedup constraint exists
- `access/services.py` (58 lines) — confirms zero creation/token-generation logic
- `access/admin.py:6-8` — `AccessLinkAdmin` list display
- `events/models.py:21-29` — `Lower(Trim())` unique-constraint convention to mirror
- `rooms/models.py:15-21` — same convention, second example
- `rooms/forms.py:78-102` — `full_set_problems()`, the duplicate-detection precedent
- `rooms/models.py:27-42` — `PendingUpload`, the staging-model precedent
- `rooms/views.py:28-39` — encoding-fallback chain precedent

## Architecture Insights

- This codebase has a consistent, twice-established convention (`Event`, `Room`) for case-insensitive per-scope uniqueness via `UniqueConstraint(Lower(Trim(<field>)), <scope>)` — S-03 should extend this same pattern to participant/staff email dedup rather than inventing a new approach.
- The `rooms` app's column-mapping complexity is a direct response to a stated PRD constraint (third-party CSV variance) that does not apply to S-03's organiser-authored lists — reusing that complexity here would be importing a solution to a problem S-03 doesn't have, while several of its *other* patterns (staging, validation timing, encoding robustness, object-scoping) are genuinely reusable.
- F-02 deliberately left `AccessLink` schema-minimal and creation-free specifically so S-03 could shape both the identity-validation layer and the creation flow itself — this isn't a gap to route around, it's the intended handoff.

## Historical Context (from prior changes)

- `context/archive/2026-09-16-access-link-staff-session-scaffold/research.md:71` — anticipated this exact handoff: "S-03... owns adding participant/staff lists and *generating* the actual links; consumes F-02's token-creation primitive (if one exists) or its data model, not just its verification logic."
- `context/archive/2026-09-16-access-link-staff-session-scaffold/plan.md:30,36` — explicit boundary: no link-generation UI, no token-creation helper, both deferred to S-03.
- `context/archive/2026-09-14-create-event/plan.md:38` — confirms participant/staff lists were out of scope for S-01 from the start, deferred to S-03/F-02.
- `context/archive/2026-09-14-csv-upload-room-mapping/` (research.md, plan.md) — the full precedent analyzed above for what transfers vs. doesn't.

## Related Research

- `context/archive/2026-09-16-access-link-staff-session-scaffold/research.md` — F-02's own research, directly upstream of this change.
- `context/archive/2026-09-14-csv-upload-room-mapping/research.md` — the closest existing upload-flow precedent.

## Open Questions

1. **How does the organiser see/retrieve generated links to share them manually?** The PRD is silent (Non-Goals only rules out automated email). Needs a planning decision: a links-list view, copy-to-clipboard, CSV export, or something else. Owner: user.
2. **Fixed-shape list input — what exact shape?** One-email-per-line? A two-column CSV with fixed `name,email` headers? Something else? The research rules out arbitrary column-mapping but doesn't pick a specific fixed shape — that's a planning decision informed by what's easiest for an organiser to produce.
3. **Is the paginated per-page-edit preview UI (mirroring `rooms`' `RoomFormSet`) warranted for participant/staff lists, or is a simpler single-page review enough?** Depends on expected list size (dozens? hundreds?), which isn't stated anywhere in the PRD — a judgment call for planning.
4. **Should S-03 build the identity model (name/email/role) as a new dedicated `Participant`/`StaffMember` model, or extend `AccessLink` itself with a uniqueness constraint and validation?** The forward-trace suggests booking-state and staff-action-state belong to S-04/S-08 respectively, but doesn't resolve whether S-03's own identity data needs its own table (which S-04/S-08 later FK to) or can live directly on an extended `AccessLink`. Both satisfy FR-003/FR-004 on their own terms — a genuine architecture choice for planning.
