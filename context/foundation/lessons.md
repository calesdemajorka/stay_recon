# Lessons Learned

> Append-only register of recurring rules and patterns. Re-read at start by /10x-frame, /10x-research, /10x-plan, /10x-plan-review, /10x-implement, /10x-impl-review.

## CSV/Excel export must sanitize formula-injection characters

**Context**: `rooms/forms.py:31-53` (`validate_row`/`compute_mapped_rows`) — CSV-derived room field values are stored as-is in `Room` records.

**Problem**: Room field values from an uploaded CSV are stored verbatim. No export/Excel-open feature exists today, so this isn't currently exploitable — but a future CSV/Excel export of this data would be vulnerable to formula injection unless sanitized.

**Rule**: Any future CSV/Excel export in this project must sanitize leading `=`, `+`, `-`, `@` characters in exported cell values before writing them out.

**Applies to**: Any feature that exports user-supplied/CSV-derived data to a CSV or Excel-openable format (e.g. a future reconciliation-report export, S-09).

## Always stage commits by explicit path, never bundle unrelated dirty paths

**Context**: `/10x-implement`'s phase-end commit ritual, encountered while committing `access-link-staff-session-scaffold` phase 2 — unrelated dirty paths (`.claude/settings.local.json`, `CLAUDE.md`, an unrelated in-progress change folder) were present alongside this phase's actual changes.

**Problem**: A careless `git add -A`/`git add .` would silently bundle unrelated, possibly sensitive or simply out-of-scope files into a commit meant to represent one unit of work.

**Rule**: Always stage commits with explicit file paths — only the files genuinely touched by the current unit of work. Any other dirty path in the working tree must be surfaced to the user explicitly (not silently included, not silently ignored) so they can decide what happens to it.

**Applies to**: Every commit in this project, not just `/10x-implement`'s phase-end ritual (which already does this) — this is a general git-hygiene rule for any commit authored in this repo.

## New pages must name their navigation entry point

**Context**: `templates/events/event_form.html:11` — the event edit page, where every list-flow success redirect lands, links only to the room CSV upload.

**Problem**: `participant-staff-lists-and-links` shipped four organiser-facing pages (participant upload, staff upload, staff add-one, links list) with no link from any existing template. The plan never listed navigation, so the manual verification of every phase relied on typing URLs by hand.

**Rule**: Every plan that adds a user-facing page must name where the user navigates to it from (the entry-point template/link) in its Changes Required.

**Applies to**: /10x-plan and /10x-plan-review for any change that adds a new view/URL.
