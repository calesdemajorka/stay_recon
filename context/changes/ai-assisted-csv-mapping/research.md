---
date: 2026-09-16T16:47:02+02:00
researcher: Michal Zajaczkowski
git_commit: 448fcdcb1c7750ec83fd9f9b1d71e2a8e23c7202
branch: dev
repository: stay_recon
topic: "Possibility of an AI-assisted CSV parser: pre-suggest column mapping, organiser confirms"
tags: [research, codebase, csv-mapping, ai, non-goal-conflict, rooms]
status: complete
last_updated: 2026-09-16
last_updated_by: Michal Zajaczkowski
---

# Research: AI-assisted CSV column mapping

**Date**: 2026-09-16T16:47:02+02:00
**Researcher**: Michal Zajaczkowski
**Git Commit**: 448fcdcb1c7750ec83fd9f9b1d71e2a8e23c7202
**Branch**: dev
**Repository**: stay_recon

## Research Question

Should StayRecon add an AI-assisted CSV parser — once the organiser uploads a hotel's CSV, the system tries to align its columns with StayRecon's room data model (room_number/room_type/capacity) and asks the organiser to confirm before saving? Scope agreed with the user: treat the PRD's existing Non-Goal against automated CSV format detection as an **open question worth revisiting now** (not just a future/v2 footnote), and compare **both** a deterministic fuzzy-matching approach and an LLM-based approach neutrally.

## Summary

This idea runs directly into an explicit, twice-recorded PRD decision: **"No automated CSV format auto-detection — organiser always manually maps columns; no smart per-hotel schema detection"** (`prd.md:110`, `shape-notes.md:135`). But the picture is more nuanced than a flat "no":

- The exclusion was a **v1 scope-down decision** made during initial shaping (`shape-notes.md:20-21`), not something added later under the emergency 10-day-runway crunch — that crunch instead cut FR-005's audit trail and FR-010's flag/note feature (`shape-notes.md:22-23`). So "manual-only mapping" reads as a deliberate simplicity/reliability choice for the reconciliation-accuracy-critical intake step, not merely a symptom of time pressure — though time pressure was clearly part of the broader environment.
- FR-002's own Socratic resolution already names the actual concern: *"manual mapping errors could go undetected"* → mitigated by *adding a preview/confirm step*, not by forcing blank dropdowns (`prd.md:59`). The organiser-facing safety net the PRD relies on is the **confirm screen**, not the absence of a suggestion.
- **The current dropdowns already have an unlabeled, arbitrary pre-fill.** `ColumnMappingForm` (`rooms/forms.py:19-28`) has no blank/placeholder choice — Django's `<select>` defaults to the CSV's first header for every field. Organisers already override a silent default today; the AI-assist idea would only make that default *meaningful* instead of arbitrary. It would not introduce a new class of "trust the default" risk that doesn't already exist.
- **This would be a genuinely new, currently untracked risk category.** `test-plan.md`'s risk map has nothing for "column mapped to wrong field" or "organiser rubber-stamps an incorrect suggestion" — its one CSV-adjacent risk (#4) is about concurrent-upload data corruption, a different failure mode entirely.
- **Timing case against doing this now is strong.** The PRD's hard deadline (2026-09-14) has passed, unrevised, with no note anywhere in `context/` that it was extended. Of the 9 core v1 slices, only `F-01` and `S-01` are `done`; `S-02` (the CSV mapping flow itself) is still `in-progress`; the other 7 — including the entire participant-booking flow (`S-04`, the PRD's own "north star") — are still `proposed` with zero code. Roadmap's own `Open Roadmap Questions #2` ("is the full 9-slice v1 scope still realistically achievable?") was never answered (`roadmap.md:250`).
- **Technically, both approaches are viable and cheap** at this CSV size (≤5000 rows, 3 target fields): a deterministic fuzzy-matcher (stdlib `difflib` or `rapidfuzz`) needs zero new heavy dependencies but structurally fails on true abbreviations ("Rm#") without a hand-built synonym list; an LLM call (e.g. Claude Haiku 4.5) handles abbreviations/semantics natively at sub-cent cost and low-single-digit-second latency, but adds the project's first AI/API dependency, non-determinism, and a new external-call failure mode. Every real-world CSV-import product researched (Flatfile, OneSchema, even simple exact-match Airtable) uses the same "suggest, always confirm before import" pattern StayRecon's PRD already commits to — so *if* this is built, the interaction pattern wouldn't be foreign to the product's own design language, and it also isn't a novel pattern within *this codebase*: FR-014 (participant room "suggested pick") is the same suggest-then-confirm shape — but it too is pure PRD intent with **zero implementation** anywhere in the codebase yet, so there's no working precedent to build on top of, only a written design intent that agrees with the shape.

## Detailed Findings

### The current manual-mapping mechanism (what an AI-assist would sit in front of)

- `rooms/forms.py:19-28` — `ColumnMappingForm`: three `ChoiceField`s (`room_number`, `room_type`, `capacity`), each populated with `[(h, h) for h in headers]` — the CSV's own header strings, no synonym/alias handling, no blank option.
- `rooms/views.py:97-116` — `csv_map_columns()`: renders the form, and on submit calls `compute_mapped_rows()` to project raw rows through the chosen mapping, then redirects to the preview/confirm screen.
- `rooms/forms.py:44-53` — `compute_mapped_rows()` + `validate_row()`: per-row validation (room number required, capacity must be digits) — this validation surface is untouched by mapping *choice*; it validates the *result* of whatever mapping was chosen, AI-assisted or not.
- `rooms/views.py:136-214` — `csv_preview()`: the paginated, editable, confirm-gated review screen — this is FR-002's actual safety net, and an AI pre-fill would feed into it exactly the same way a manual selection does today. No architectural change needed to this layer.
- **An AI-assisted pre-fill is a small, additive change**: pre-select `ColumnMappingForm`'s `initial` values instead of leaving Django's implicit first-choice default, with the exact same downstream flow (compute → preview → confirm) unchanged. This is architecturally low-risk *as a code change* — the risk is entirely in the product/trust dimension, not the engineering dimension.

### The PRD Non-Goal — origin and framing

- `prd.md:110` / `shape-notes.md:135` — verbatim: *"No automated CSV format auto-detection — organiser always manually maps columns; no smart per-hotel schema detection."*
- `shape-notes.md:20-21` (`gray_areas_resolved`, topic "v1 scope cuts") — this was decided during the *original scoping-down from the full flow to v1*, alongside "manual link sharing" and "simple table/CSV report" — a deliberate minimal-v1 choice, not a deadline-crunch casualty.
- `shape-notes.md:22-23` (topic "deadline scope cuts") — the *later*, deadline-driven cuts were specifically FR-005 (audit trail) and FR-010 (flag/note) — a different, later decision with a different, explicitly time-pressure rationale. The CSV Non-Goal predates that crunch.
- `prd.md:58-59` (FR-002 Socratic note) — the concern that shaped FR-002 was *"manual mapping errors could go undetected"*; the chosen mitigation was the preview/confirm step, not the removal of assistance. This is the load-bearing precedent for arguing a *confirmed* suggestion doesn't violate the spirit of the mitigation, even though it may violate the letter of "organiser always manually maps columns."

### Risk-register and testing implications

- `context/foundation/test-plan.md` §2 Risk Map — risk #4 (the only CSV-adjacent entry) is about **concurrent uploads corrupting data**, not mapping accuracy. No risk currently named for "wrong column mapped" or "organiser trusts a bad AI suggestion."
- `context/foundation/test-plan.md` §4 Stack — AI-native tooling is explicitly out of the current test-rollout's scope ("no critical screen was named as needing multimodal review") — this is about *testing tools*, not about whether the *product* should use AI, but it confirms AI-related tooling has had zero investment or precedent-setting in this project so far.
- `context/changes/csv-upload-room-mapping/reviews/plan-review.md` — the one existing plan review for the CSV flow raised three findings (formset TOTAL_FORMS bug, empty-CSV edge case, missing file-type sanity check) — none propose or discuss smarter/AI-assisted mapping.

### FR-014 — the closest existing "suggest + confirm" precedent, and its actual status

- `prd.md:72` — FR-014: participant states preferences; app highlights one suggested room, "minimizing the total number of rooms the event ends up using"; participant can accept or pick differently.
- `roadmap.md:144-154` (S-04) — **Status: `proposed`**. Roadmap's own risk note: *"FR-014's suggestion/consolidation logic is the one piece here with real algorithmic risk and deserves explicit verification, not just an assumed side effect of 'booking works.'"*
- Codebase search for any suggestion/ranking/scoring function in `events/` or `rooms/` — **zero matches**. This is a design-intent precedent for the "suggest, let the human confirm/override" interaction shape, not a working implementation to extend or learn operational lessons from.

### Current project state (bears directly on timing)

- `roadmap.md` "At a glance": `F-01` done, `F-02` proposed, `S-01` done, `S-02` in-progress, `S-03`–`S-09` all **proposed** (zero code), `S-10` (landing page, not a PRD FR) done.
- `roadmap.md:250` — Open Roadmap Question #2, verbatim: *"Is the full 9-slice v1 scope still realistically achievable in the remaining runway? ... Worth an explicit go/cut decision now rather than discovering the gap mid-sprint."* — never answered anywhere in `context/`.
- PRD hard deadline `2026-09-14` (`prd.md` frontmatter) has passed as of this research (2026-09-16); no document anywhere records a revised deadline or an explicit decision to extend it.
- The PRD's own "north star" slice (`S-04`, participant books via link — the smallest end-to-end proof of the core hypothesis) is still `proposed`, meaning the core booking loop this whole product exists for does not work end-to-end yet.

### Technical approaches (neutral comparison)

**Deterministic fuzzy-string matching** (stdlib `difflib`, or `rapidfuzz`/`thefuzz`):
- Zero new heavy dependencies (`difflib` is stdlib; `rapidfuzz` is a single lightweight, actively-maintained package).
- Handles typos/casing/word-order well (token-based scorers), but structurally fails on true abbreviations ("Rm#" vs "room_number" share almost no characters) without a hand-maintained synonym/alias list per target field.
- Bimodal failure mode: a low threshold risks false-confident wrong matches; a conservative threshold (commonly ~70%+) just falls back to "no suggestion" for exactly the header styles that need the most help.
- Fully deterministic, explainable, no external call, no ongoing cost, no new secrets/API-key management.

**LLM-based matching** (e.g. Anthropic API, Claude Haiku 4.5):
- Handles semantic/abbreviation cases natively ("Rm#" → room_number) without a maintained synonym list.
- Cheap at this scale: ~$1/$5 per MTok in/out, well under a cent per mapping request; realistic round-trip latency in the low single-digit seconds.
- Structured/schema-constrained output can close off "invents a field that doesn't exist," but not "confidently wrong within the valid 3-field set"; outputs aren't perfectly deterministic run-to-run unless temperature is pinned to 0.
- Introduces the project's first AI/ML dependency (`has_ai: false` today, `tech-stack.md:18,24`), a new external network call and failure mode in a previously fully-synchronous, dependency-light request path, and new secrets management (API key).

**Industry precedent**: Flatfile and OneSchema both use ML-trained matching; Airtable uses simple case/whitespace-insensitive exact matching. All three — regardless of matching sophistication — present the mapping as a **review/confirm screen before import**, never committing a mapping unseen. This matches StayRecon's own already-committed design (the preview/confirm step FR-002 already mandates), meaning the *product-fit* question is really "should the pre-fill be smarter than 'first CSV column,'" not "should we abandon the confirm step" — that step is not up for debate either way.

## Code References

- `rooms/forms.py:19-28` — `ColumnMappingForm` (no blank option, defaults to first header)
- `rooms/forms.py:31-53` — `validate_row()` / `compute_mapped_rows()` (unaffected by mapping source)
- `rooms/views.py:97-116` — `csv_map_columns()` view
- `rooms/views.py:136-214` — `csv_preview()` view (the confirm-gated safety net)
- `stay_recon/settings.py` — no AI-related config; only `RESEND_API_KEY` (transactional email, unrelated)
- `pyproject.toml` — 5 dependencies total, none AI/ML/fuzzy-matching related

## Architecture Insights

- The mapping-selection step and the validate/preview/confirm step are already cleanly separated in the code (`csv_map_columns` vs. `csv_preview`), so an AI-assisted pre-fill is architecturally a small, additive change confined to `csv_map_columns` and `ColumnMappingForm`'s `initial` values — it would not require touching the validation or confirm-gate logic at all.
- No AI/ML dependency exists anywhere in the stack today (`has_ai: false` is accurate and deliberate per the PRD's Non-Goals). Adding either fuzzy-matching (new light dependency) or an LLM call (new API dependency, secrets, network failure mode) would be a first for this codebase.

## Historical Context (from prior changes)

- `shape-notes.md:20-23` — distinguishes the *original* v1 scope-down (CSV auto-detection excluded here) from the *later* deadline-driven cuts (audit trail, flag/note) — different decisions, different rationale, made at different times.
- `context/changes/csv-upload-room-mapping/plan.md:40` — reaffirms the Non-Goal as an explicit constraint during S-02's own planning, with no counter-argument recorded.
- `context/changes/bootstrap-verification/verification.md:33,37,80` — echoes `has_ai: false` and "AI features are out of scope per the PRD's Non-Goals" verbatim, from the earlier bootstrap verification pass.
- No file anywhere in `context/changes/**` or `context/archive/**` has ever proposed or discussed smart/AI-assisted mapping before this research.

## Related Research

- `context/changes/csv-upload-room-mapping/research.md` — original research behind the manual mapping flow this idea would extend.

## Open Questions

1. **Is this the right time, strategically?** With 7 of 9 core v1 slices — including the PRD's own north-star slice (S-04) — still unbuilt and the hard deadline already passed unrevised, taking on the project's first AI/API dependency for a non-blocking enhancement to an already-shipping slice (S-02) competes directly with finishing the core booking loop. Owner: user. Not resolved by this research — this is a prioritization call, not a technical one.
2. **If pursued, does it require a PRD amendment?** The current Non-Goal wording ("organiser always manually maps columns") is arguably still satisfied by a confirm-required suggestion (the organiser still does the confirming), but the wording is closer to a plain "no" than an "as long as they confirm" carve-out. Worth an explicit PRD Non-Goals edit either way, so the decision is recorded rather than quietly overridden by an implementation. Owner: user.
3. **Deterministic or LLM-based, if built?** Both are technically cheap and viable at this scale; the real tradeoff is dependency/complexity/non-determinism (LLM) vs. maintained-synonym-list effort and an abbreviation blind spot (deterministic). Not resolved here by design — this was scoped as a neutral technical comparison, not a recommendation.
4. **Does FR-014's still-unbuilt "suggest + confirm" pattern (S-04) get built first?** If the product is going to have an AI/heuristic-assisted "suggest, let the human confirm" interaction anywhere, FR-014 is the PRD's own prior commitment to that shape and arguably a more central risk (booking-suggestion correctness affects the core hypothesis, not just an already-shipping intake step). Worth considering whether CSV-mapping-assist should follow, not precede, FR-014's implementation.
