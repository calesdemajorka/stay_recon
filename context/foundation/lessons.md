# Lessons Learned

> Append-only register of recurring rules and patterns. Re-read at start by /10x-frame, /10x-research, /10x-plan, /10x-plan-review, /10x-implement, /10x-impl-review.

## CSV/Excel export must sanitize formula-injection characters

**Context**: `rooms/forms.py:31-53` (`validate_row`/`compute_mapped_rows`) — CSV-derived room field values are stored as-is in `Room` records.

**Problem**: Room field values from an uploaded CSV are stored verbatim. No export/Excel-open feature exists today, so this isn't currently exploitable — but a future CSV/Excel export of this data would be vulnerable to formula injection unless sanitized.

**Rule**: Any future CSV/Excel export in this project must sanitize leading `=`, `+`, `-`, `@` characters in exported cell values before writing them out.

**Applies to**: Any feature that exports user-supplied/CSV-derived data to a CSV or Excel-openable format (e.g. a future reconciliation-report export, S-09).
