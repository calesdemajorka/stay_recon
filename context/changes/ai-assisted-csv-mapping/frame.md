# Frame Brief: AI-assisted CSV column mapping

> Framing step before /10x-plan. This document captures what is *actually*
> at issue, separated from what was initially assumed.

## Reported Observation

Column mapping in the shipped CSV-upload flow (`S-02`, `in-progress`) is fully manual: three dropdowns (`room_number`/`room_type`/`capacity`), no assistance, silently defaulting to the CSV's first header with no blank option (`rooms/forms.py:19-28`).

## Initial Framing (preserved)

- **User's stated cause or approach**: AI assistance (LLM or heuristic) should pre-suggest the mapping; organiser confirms before it's used.
- **User's proposed direction**: Add an AI-assisted CSV parser that aligns uploaded columns to the room data model and asks for confirmation.
- **Pre-dispatch narrowing**:
  - *Origin*: "That's a real case, where organiser could see the value in the product. Not really a pain point yet, but perfect for marketing purposes." — motivation is differentiation/perceived value, explicitly **not** a pain point.
  - *Timing*: "After the core v1 flow ships" — explicitly deferred, not urgent.
  - *PRD stance*: "A real scope change" — requires an explicit Non-Goals amendment, not a quiet override.

## Dimension Map

1. **Reliability/error-reduction** — would this fix an observed organiser mapping-error problem?
2. **Differentiation/perceived-value** — would this make the product's sophistication tangible to organisers/prospects?  ← initial motivation, once separated from the proposed mechanism
3. **Public-facing marketing surface** — should the "smart mapping" moment live on the public landing page as an anonymous interactive demo?
4. **Scope-process** — does building this require a formal PRD Non-Goals amendment first?
5. **Timing/sequencing** — before or after the still-unbuilt v1 core booking loop?

## Hypothesis Investigation

| Hypothesis | Evidence | Verdict |
| --- | --- | --- |
| 1. Reliability/error-reduction is the real driver | User: "not really a pain point yet." `test-plan.md`'s risk map has no entry for mapping errors. S-02 isn't in real organiser use yet, so no errors could have been observed. | NONE |
| 2. Differentiation/perceived-value is the real driver | User, verbatim: "organiser could see the value in the product... perfect for marketing purposes." Directly stated, not inferred. | STRONG |
| 3. Belongs as a public-facing landing-page demo | Independent pressure-test agent (reading `prd.md`, `roadmap.md`, `rooms/views.py` fresh, without seeing the marketing framing): CSV upload is `@login_required` (`rooms/views.py:41-43`), scoped to `organiser=request.user`; PRD Access Control (`prd.md:105`) restricts unauthenticated visitors to a data-free generic landing page. Zero rate-limiting/throttling/CAPTCHA anywhere in the app (`grep` for `ratelimit\|throttl\|captcha` — zero hits); zero existing outbound-third-party-API call from any view (`RESEND_API_KEY` config exists but is unused — no call sites). | NONE — ruled out as the *implementation vehicle*, though it doesn't rule out hypothesis 2 as the *motivation* |
| 4. Requires a PRD Non-Goals amendment before building | User, verbatim: "a real scope change." Corroborated by `shape-notes.md:20-21`: the Non-Goal was a deliberate v1 scope-down decision (not an incidental deadline casualty), so reversing it deserves the same deliberateness. | STRONG |
| 5. Should be sequenced after the v1 core flow | User, verbatim: "after the core v1 flow ships." Corroborated by `roadmap.md`: only `F-01`/`S-01` done, `S-02` in-progress, `S-03`–`S-09` (including north-star `S-04`) all still `proposed`; PRD hard deadline (2026-09-14) already passed, unrevised. | STRONG |

## Narrowing Signals

- The user's own words separate "value the organiser can see" from "a problem the organiser currently has" — this is the crux of the reframe. The original request's mechanism (AI-assisted parsing) was never in question; what was conflated was *why* it's worth building.
- The independent pressure-test agent, given zero knowledge of the marketing framing, converged on "this belongs in the real authenticated flow" for purely architectural reasons (login-gated upload, no public/anonymous precedent anywhere in the app) — a different route to a compatible conclusion, which raises confidence rather than lowering it.
- `templates/landing.html:45-65` already contains a **static**, `aria-hidden` CSV→room-list comparison illustration with hardcoded sample data — the marketing *narrative* ("we turn messy CSVs into trustworthy lists") is already told on the landing page today, without needing a live/interactive/public AI endpoint to tell it. This weakens any temptation to build the "wow moment" as public-facing infrastructure — the story is already being sold there; the *feature* itself is what would need to earn its keep inside the real product.

## Cross-System Convention

Every real-world CSV-import product researched (Flatfile, OneSchema, Airtable) gates smart mapping behind an authenticated import flow, always with a human confirm step before commit — none exposes mapping-suggestion as a public/anonymous capability. The leading hypothesis (differentiation feature, built into the real authenticated flow, confirm-gated) matches this convention exactly.

## Reframed (or Confirmed) Problem Statement

> **The actual problem to plan around is**: StayRecon currently has no moment where its CSV-normalization intelligence is *visible* to the organiser experiencing it — not a mapping-error problem to fix, but a differentiation-value gap to close, deliberately deferred until after the v1 core booking loop ships, and gated behind an explicit PRD Non-Goals decision.

The original framing ("add an AI-assisted CSV parser") named a mechanism, not a problem — and the research phase correctly surfaced that mechanism's tension with the PRD, but this framing pass is what surfaces *why* it's wanted, which changes what a plan should optimize for. If this had been framed as "reduce organiser mapping errors," success criteria would center on error-rate reduction and safety-under-ambiguity — but no error rate was ever observed (S-02 isn't in real use), so that metric doesn't exist to reduce. Framed correctly as a differentiation feature, success instead means: does the suggestion feel *reliably smart* to an organiser seeing it for the first time on a real, messy hotel CSV — which argues for weighting "handles genuine abbreviations well" (an LLM's structural advantage per the research) more heavily than "zero new dependency" (deterministic fuzzy-matching's structural advantage) — a trade a future /10x-plan should make explicitly, not default into.

## Confidence

**HIGH** — the motivating dimension (differentiation, not reliability) came directly from the user's own words, not inference; the implementation-surface question (real flow vs. public demo) was independently corroborated by a pressure-test agent with no knowledge of that motivation; and the timing/scope-process dimensions were both explicitly confirmed by the user. No further verification needed before planning.

## What Changes for /10x-plan

When this is picked up (explicitly not now, per the user): the plan should (1) open with — or be preceded by — an explicit PRD Non-Goals amendment recording the scope change, not fold it in as an implementation detail; (2) scope success criteria around perceived intelligence/demo-worthiness on realistic messy hotel CSV headers, not around a (nonexistent) observed error rate; (3) build entirely inside the real, authenticated `rooms` app flow — no public-facing surface, no new anonymous-endpoint/abuse-prevention infrastructure needed; (4) treat the deterministic-vs-LLM technique choice as a genuine trade to make deliberately, informed by the "must handle real abbreviations to look smart" bar this reframe establishes, not resolved by default toward the zero-dependency option.

## References

- Research: `context/changes/ai-assisted-csv-mapping/research.md`
- Source files: `rooms/forms.py:19-28`, `rooms/views.py:41-43,97-116`, `templates/landing.html:25-65`, `context/foundation/prd.md:58-59,105,110`, `context/foundation/shape-notes.md:20-23,135`, `context/foundation/roadmap.md:46,68-71,250`
