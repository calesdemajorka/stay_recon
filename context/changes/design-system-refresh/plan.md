# Design System Refresh — Implementation Plan

## Overview

Give StayRecon a distinctive visual identity grounded in its actual subject matter — reconciling a hotel's messy CSV into a trustworthy room manifest — rather than a generic SaaS look, and make sure that identity is *shared* rather than landing-page-only. Phase 1 (this session) built the token system and the landing page. Phase 2 is the forward-looking rollout of the same visual language to the app's internal, authenticated screens.

## Current State Analysis

- Before this change: `templates/base.html` had one small inline `<style>` block (system font, `#1a1a1a`/`#555` text, no brand colors) shared by every template, and the `/` landing page used a generic teal (`#0f6a5c`) accent unrelated to any deliberate brand system.
- Every existing template (`accounts/dashboard.html`, `accounts/signup.html`, `registration/*.html`, `events/*.html`, `rooms/*.html`) extends `base.html` and adds zero CSS of its own — meaning changes to `base.html`'s shared rules apply everywhere for free, but nothing in the app currently has a persistent nav header, section banding, or any layout beyond a single narrow centered column.
- No static asset pipeline is exercised (WhiteNoise configured, unused) — token/font delivery uses a Google Fonts `<link>` (one display serif, `Domine`) rather than a new build step.

## Desired End State

**Phase 1 (done):** `templates/base.html` defines a shared token system (`--ink-navy`, `--ink-navy-deep`, `--paper`, `--brass`, `--brass-text`, `--slate`, `--charcoal`, `--font-display`, `--font-body`, `--radius-sm`) as `:root` custom properties, and the existing shared rules (`body`, `h1`, `a`, `button`, `input`, `ul.errorlist`) are repointed at those tokens — so every page in the app already shares the same button style, link color, and heading font, with zero per-template changes. The landing page (`templates/landing.html`) is fully rebuilt on this system: navy hero with a two-column layout, a CSS-only "chaos→order" room-tile grid device, a paper-toned problem/solution band with a CSV→room-list comparison visual, a connected vertical step list for "how it works", and a navy CTA-repeat band.

**Phase 2 (proposed, not started):** Extend the same token system's *layout* patterns — not just colors/buttons, which already propagated in Phase 1 — to the app's internal authenticated screens, where it makes sense: a persistent header/nav (brand + context-appropriate links) instead of no header at all, consistent page-title treatment, and deliberate use of the paper/navy section bands for visual hierarchy on longer screens (e.g. the CSV mapping/preview flow), while explicitly *not* importing the landing page's marketing devices (hero grid, chaos/order motif) into functional, data-entry-heavy screens where they'd hurt task completion rather than help it.

### Key Discoveries

- Because no template overrides `base.html`'s shared rules, Phase 1's token propagation was near-zero-risk: `uv run manage.py test` (59/59) passed unchanged, since no test asserts on styling/markup (`context/foundation/test-plan.md` §7 explicitly excludes this).
- The real remaining work for "uniform through the whole application" is **layout**, not tokens — colors/fonts/buttons are already shared; what's missing on internal screens is any structural design language (no nav, no section rhythm, no header treatment) at all.

## What We're NOT Doing (Phase 1)

- Not applying the landing page's rich navy/paper section-banding or the hero grid device to any internal screen yet — that's Phase 2, and deserves its own planning pass given the usability tradeoffs on data-entry screens.
- Not introducing a static asset build pipeline — the one external dependency added is a single Google Fonts `<link>` for the display serif.
- Not changing internal screens' backgrounds, spacing, or structure — Phase 1 only touched shared color/type/button tokens and the landing page itself.

## Implementation Approach

Phase 1: define tokens once in `base.html`, repoint shared rules at them, rebuild `landing.html` on top. Phase 2 (future): a dedicated planning pass — likely via `/10x-new design-system-refresh` continuation → `/10x-plan` — to decide, screen by screen, how much of the landing page's layout language should extend inward, informed by real usage of the functional screens (CSV mapping, event forms) rather than assumed upfront.

## Phase 1: Token system + landing page rebuild

### Overview

Already implemented and verified in this session.

### Changes Required

#### 1. `templates/base.html`

**Intent**: Define the shared design-token system and repoint every existing shared rule (`body`, `h1`, `a`, `button`, `input`, `ul.errorlist`) at it, so color/type/button consistency reaches every template automatically. Add the `.landing`-scoped rebuild of the landing page's visual system (navy/paper/brass, two-column hero, CSS-only chaos→order tile grid, CSV comparison visual, connected step list, mobile breakpoint, `prefers-reduced-motion` handling).

**Contract**: `:root` tokens as named above; global rules updated in place (no new selectors added outside `.landing` for shared elements); one Google Fonts `<link>` (`Domine`, weights 400/700) added to `<head>`.

#### 2. `templates/landing.html`

**Intent**: Rebuild the landing page markup on the new token system with the "Manifest" concept — two-column hero (headline/CTA left, chaos→order tile grid right), CSV→room-list comparison visual in the problem/solution section, connected numbered step list, navy CTA-repeat band.

**Contract**: Same section structure and `{% url %}`-based CTA links as before (`signup`, `login`); copy substance unchanged from the original landing-page change.

### Success Criteria

#### Automated Verification

- Django system check passes: `uv run manage.py check`
- Full test suite still passes (no regressions): `uv run manage.py test`

#### Manual Verification

- Visiting `/` shows the navy hero with the room-tile grid settling into order, the paper-toned problem section with the CSV comparison visual, the connected step list, and the navy CTA band
- Visiting `/dashboard/`, `/signup/`, `/accounts/login/`, and an event form all show the new brass buttons and serif `<h1>` headings, unchanged layout otherwise
- Room-tile settle animation is disabled under `prefers-reduced-motion: reduce`

---

## Phase 2: Propagate layout consistency to internal screens (proposed)

### Overview

Not started. Scope: decide and implement how much of the landing page's structural language (persistent header/nav, section banding, page-title treatment) should extend to `accounts/dashboard.html`, `accounts/signup.html`, `registration/*.html`, `events/*.html`, and `rooms/*.html`, without importing marketing-page devices into task-focused screens.

### Changes Required

Deliberately not specified in detail here — this phase should go through its own `/10x-plan` pass once picked up, so screen-by-screen layout decisions get the same interview-driven scrutiny Phase 1's landing page redesign got, rather than being pre-decided in this design-exploration session.

### Success Criteria

#### Automated Verification

- Django system check passes: `uv run manage.py check`
- Full test suite still passes: `uv run manage.py test`

#### Manual Verification

- Every authenticated screen (dashboard, event forms, CSV upload/map/preview) reads as visibly part of the same product as the landing page, without the added layout hurting task completion on data-entry-heavy screens

## Testing Strategy

### Manual Testing Steps (Phase 1)

1. Run `uv run manage.py runserver` and open `/`.
2. Confirm the hero's tile grid animates into place once on load, and is static (no animation) with the OS's reduce-motion setting on.
3. Confirm `/dashboard/`, `/signup/`, `/accounts/login/` show brass buttons and serif headings, with layout otherwise unchanged.
4. Resize to ~400px — hero collapses to one column, CSV comparison panels stack vertically.

## Performance Considerations

One external font request (Google Fonts, `Domine`) is added; no other new network dependencies. Negligible impact — a single small woff2 file, cached across visits.

## Migration Notes

Not applicable — no data model changes.

## References

- Prior landing page implementation: `context/archive/2026-09-16-landing-page/plan.md`
- Shared template system: `templates/base.html`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands.

### Phase 1: Token system + landing page rebuild

#### Automated

- [x] 1.1 Django system check passes: `uv run manage.py check`
- [x] 1.2 Full test suite still passes: `uv run manage.py test`

#### Manual

- [x] 1.3 Hero tile grid renders and animates on `/`, static under reduced motion
- [x] 1.4 Dashboard/signup/login/event forms show brass buttons and serif headings, layout unchanged
- [x] 1.5 Page reads correctly at ~400px width

### Phase 2: Propagate layout consistency to internal screens

#### Automated

- [ ] 2.1 Django system check passes: `uv run manage.py check`
- [ ] 2.2 Full test suite still passes: `uv run manage.py test`

#### Manual

- [ ] 2.3 Every authenticated screen reads as part of the same product as the landing page without hurting task completion
