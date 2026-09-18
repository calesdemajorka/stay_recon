# Participant & Staff Lists + Access-Link Generation (S-03) — Plan Brief

> Full plan: `context/changes/participant-staff-lists-and-links/plan.md`
> Research: `context/changes/participant-staff-lists-and-links/research.md`

## What & Why

S-03 lets the organiser add a participant list and a staff list (separately) to an event and get a unique access link per person, generated atomically on confirm. Nothing downstream can work without this — S-04 (participant booking) and S-08 (staff check-in) both consume whatever this slice produces.

## Starting Point

`access.AccessLink` (from the now-archived F-02) exists but can't satisfy FR-003 alone — no uniqueness constraint beyond `token`, no email validation, and no creation logic anywhere. F-02 deliberately left identity/list management to this slice.

## Desired End State

An organiser can upload a participant CSV and a staff CSV (or add one staff member manually for small events), review/correct a paginated preview, confirm to atomically create identity + link records, and retrieve every generated link from a list view or CSV export to share manually.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Identity model | Two separate models (`Participant`, `StaffMember`), each 1:1 with `AccessLink` | Matches the data layer to the already-made "separate lists" UI decision; each model can grow its own role-specific fields later without a shared table getting awkward. | Plan (user Q&A) |
| List input shape | Fixed two-column CSV (name, email) | Captures name for on-site check-in (FR-011) while staying fixed-shape — no column-mapping needed, unlike hotel CSVs. | Plan (user Q&A) |
| Preview UX | Full paginated review + inline edit (mirrors `rooms`) | User's explicit choice, consistent with the existing CSV-upload precedent. | Plan (user Q&A) |
| Re-upload behavior | Append-only, reject cross-upload duplicates | Wipe-and-replace is dangerous here — a participant's link may already be shared/used once S-04 exists. | Plan (user Q&A) |
| Link retrieval | List view + CSV export | Covers both "check one link" and "bulk distribute" without over-building. | Plan (user Q&A) |
| Name field | Name + email, not email-only | FR-011 implies staff need to recognize people by name at on-site check-in. | Plan (user Q&A) |
| Link generation timing | Atomic with list confirm | Matches how FR-003/FR-004 are presented as one continuous flow in the PRD. | Plan (user Q&A) |
| Dual role (same email, both roles) | Disallowed, cross-checked at upload | User's explicit choice — adds a cross-model uniqueness check enforced at the application level. | Plan (user Q&A) |
| Phase structure | Participant and staff built as fully separate phases | User's explicit request, given the "two parallel flows" complexity concern. | Plan (user Q&A) |
| Staff-only manual add | One-at-a-time form, staff only (not participants) | User's explicit request for small-event staff rosters; participant lists stay CSV-only per the PRD's bulk "lists" framing. | Plan (user Q&A) |
| App placement | `Participant`/`StaffMember` live in the existing `access` app | They're 1:1 extensions of `AccessLink`, not a distinct bounded concept (unlike `Room` vs `Event`). | Plan |

## Scope

**In scope:** `Participant`/`StaffMember`/`PendingListUpload` models, CSV upload+preview+atomic-confirm flow for both roles, a manual add-one form for staff, a links list + CSV export view.

**Out of scope:** manual add for participants, edit/delete UI for confirmed records, automated invitation emails, link revocation UI, any booking-state fields (S-04's job) or check-in/pack-handoff fields (S-08's job), any `events.Event` schema change.

## Architecture / Approach

Phase 1 builds both identity models together (cross-role dedup needs both tables from the start). Phases 2 and 3 build the participant and staff flows fully separately — not interleaved through shared views — each calling into small shared helpers (token generation, cross-role email-dedup check) to avoid true duplication without hiding two genuinely separate flows behind a role parameter. Phase 4 is a read-only aggregate view over both roles' links.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Data layer | `Participant`, `StaffMember`, `PendingListUpload` models | Getting the cross-table dedup constraint scope right from the start |
| 2. Participant list | Upload → preview → atomic confirm, participant-only | Cross-role duplicate check (against `StaffMember`) working correctly |
| 3. Staff list | Upload → preview → atomic confirm, plus manual add-one | Same cross-role check, other direction; manual-add must reuse the same validation as the batch path |
| 4. Links list + export | Retrieve generated links for manual sharing | Absolute-URL construction (a relative path is useless once copied out of the app) |

**Prerequisites:** `S-01` (done), `F-01` (done), `F-02` (done).
**Estimated effort:** not estimated (roadmap convention — no time units; sequence, not schedule).

## Open Risks & Assumptions

- No FR explicitly asks for a links-list/export view — this fills a genuine PRD silence (Non-Goals only rules out automated email) per an explicit user decision, not a PRD requirement.
- The cross-role dedup check is enforced at the application level (Django can't express a cross-table `UniqueConstraint`) — a race between two near-simultaneous uploads across roles could theoretically slip through; acceptable given `target_scale.qps: low` and single-actor (organiser-only) uploads.

## Success Criteria (Summary)

- An organiser can fully populate an event's participant and staff rosters and retrieve every generated access link, entirely on the live Render deploy.
- Malformed and duplicate emails (within-upload, cross-upload, and cross-role) are always caught before reaching the database, with a locatable message.
- Re-uploading never silently destroys or replaces existing participants/staff.
