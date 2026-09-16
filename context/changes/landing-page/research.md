---
date: 2026-09-16T11:48:20+02:00
researcher: Michal Zajaczkowski
git_commit: 0993f35a69751fb53c953ca9a1c7f832f95ae0f3
branch: dev
repository: stay_recon
topic: "Landing page — organizing an informative, functional landing page (UX best practices)"
tags: [research, codebase, landing-page, ux, django, templates]
status: complete
last_updated: 2026-09-16
last_updated_by: Michal Zajaczkowski
---

# Research: Landing page — UX best practices for an informative, functional landing page

**Date**: 2026-09-16T11:48:20+02:00
**Researcher**: Michal Zajaczkowski
**Git Commit**: 0993f35a69751fb53c953ca9a1c7f832f95ae0f3
**Branch**: dev
**Repository**: stay_recon

## Research Question

How should StayRecon's landing page be organized from a UX-designer perspective — what makes a landing page informative and functional — given the app's current state (a placeholder inline-HTML view) and its product context (organiser-only signup surface for a CSV-reconciliation tool)?

Scope agreed with user: the page should do **lean marketing** (value prop + CTA), not a placeholder and not a full conversion-funnel page. Best-practices research targeted a **focused, actionable checklist**, not a comprehensive dissertation.

## Summary

The current `/` route is an explicitly-labeled placeholder (`stay_recon/views.py:4-25`) — literal copy: *"This is a placeholder landing page — the real product experience isn't built yet."* It is not yet a template, has no CSS framework, no static asset pipeline in use, and no branding assets (no logo/favicon) anywhere in the repo. The only visual language in the app is `templates/base.html`'s minimal inline `<style>` block (narrow centered column, system font, gray body text), which every other template inherits with zero additional CSS.

The landing page is **not a named roadmap slice or FR** — it exists only implicitly via `prd.md:105`'s Access Control clause: *"A visitor with no link sees a generic landing page — no event or booking data is exposed."* No prior UX/branding decisions exist anywhere in `context/`.

Best-practices research converged on a lean, ~4–5-section structure (hero → problem/solution → how-it-works → CTA → minimal footer), organiser-only copy with no participant-facing content (participants/staff never reach this page — they arrive via per-event access links), honest/minimal trust signals appropriate to a solo-built MVP, one clearly-weighted primary CTA (Sign up) vs. a lighter secondary (Log in), and accessibility/mobile basics achievable in plain semantic HTML + CSS with no framework adoption required.

## Detailed Findings

### Current landing page implementation

- `stay_recon/views.py:4-25` — `index()` returns a raw `HttpResponse(INDEX_HTML)`, not a Django template. `INDEX_HTML` is a full inline HTML document: `<title>StayRecon</title>`, an inline `<style>` (system-ui font, `max-width: 32rem`, `margin: 4rem auto`, body text `#1a1a1a`, paragraph text `#555`), an `<h1>StayRecon</h1>`, and the one placeholder paragraph.
- `stay_recon/urls.py:27` — `path('', index, name='index')` is the only route mounted at `/`. Sibling routes confirmed for future landing-page CTAs: `signup` → `/signup/` (`urls.py:32`), `login` → `/accounts/login/` (via `django.contrib.auth.urls` include at `urls.py:30`, standard name `login`), `dashboard` → `/dashboard/` (`urls.py:31`). No separate `accounts/urls.py` exists.
- `stay_recon/views.py:28-31` — sibling `health()` view returns JSON at `/healthz/`; unrelated to the landing page but confirms the file's role as the project's top-level view module.

### Visual system to stay consistent with

- `templates/base.html:1-27` is the **only** source of styling in the entire app; every other template extends it and adds no CSS of its own. Its inline `<style>` (lines 6-14) closely mirrors `INDEX_HTML`'s rules, plus form styling (`label`, `input`, `button`, `ul.errorlist`).
- All child templates (`accounts/dashboard.html`, `accounts/signup.html`, `registration/*.html`, `events/event_form.html`, `events/event_confirm_delete.html`, `rooms/csv_upload.html`, `csv_preview.html`, `csv_map_columns.html`) follow an identical minimal pattern: `{% extends "base.html" %}`, one `{% block title %}`, one `<h1>`, a plain `<form method="post">{% csrf_token %}{{ form.as_p }}<button>` block. No color/spacing system beyond `base.html`, no images, no icons.
- This is a **deliberately minimal, near-unstyled design system**: single narrow centered column, system font, gray secondary text. A redesigned landing page should either extend this system (recommended, since every other screen shares it) or deliberately introduce a slightly richer style that the rest of the app would eventually adopt too — that's a design decision for `/10x-plan`, not settled here.

### Static assets / tech constraints

- No `static/` directory exists anywhere in the project. `STATIC_URL = 'static/'` and `STATIC_ROOT = BASE_DIR / 'staticfiles'` are configured (WhiteNoise-backed), but `STATICFILES_DIRS` is unset and no template references `<link rel="stylesheet">`.
- No CSS framework or CDN reference (no Bootstrap/Tailwind) anywhere in the repo. Any landing-page redesign should be feasible in plain semantic HTML + CSS, with no JS build step — confirmed by the UX research agent as achievable for this scope (single `@media` breakpoint, flexbox/grid, no framework needed).

### Branding assets

- No logo, favicon, or image files exist anywhere in the repo. The only branding is the plain-text name "StayRecon" in page titles/headings and `README.md:1,28`. No product screenshot exists to reuse as a trust signal.

### UX best-practices checklist (focused, MVP-proportional)

Full checklist with sources is preserved in the sub-agent's report; key points relevant to `/10x-plan`:

- **Structure**: hero (value prop + 1-line sub + primary CTA, fully visible above the fold) → problem/solution framing (1 short section) → how-it-works (3-4 steps max) → CTA repeat → minimal footer (login link, contact, copyright). ~4-5 sections total, not 8-10.
- **Hero copy**: lead with the organiser's specific pain ("reconcile room bookings against a hotel's CSV") over generic SaaS language; name the actual mechanism (CSVs differ per hotel, manual matching is error-prone) rather than a vague efficiency claim; no participant-facing copy anywhere, since that audience never lands here.
- **Trust signals**: skip fake testimonials/logos/stats; realistic alternatives are an honest "who this is for" statement, a working product screenshot (once one exists), transparent "what's included"/beta framing, a real contact channel.
- **CTA**: one primary CTA ("Sign up", strong visual weight) vs. one secondary ("Log in", lighter weight) — don't give them equal visual weight. Repeat primary in header, hero, and page end.
- **Accessibility**: semantic tags (`<header>`, `<nav>`, `<main>`, `<section>`, `<footer>`, single `<h1>`) — free in Django templates; WCAG AA contrast (4.5:1 body, 3:1 large text); visible focus outlines; alt text on any meaningful image.
- **Mobile**: single-column fluid layout, flexbox/grid + `max-width` container instead of fixed widths, one `@media` breakpoint usually sufficient, ~44px touch targets, `rem` font sizing.
- **Avoid**: hero image/video/carousels/parallax, feature-dump sections, pricing tables not yet real, FAQ walls, marketing buzzwords, dark patterns (forced opt-ins, fake urgency), and any participant/staff-facing content (scope creep — that traffic never arrives via this page).
- **Sources cited by the research agent**: NN/g-grounded above-the-fold eyetracking data (via cxl.com, nudgenow.com summaries), Userlist's SaaS landing-page copy guidance (Josh Garofalo), WebAIM's WCAG 2 checklist and contrast guidance, Nerdcow's CTA-hierarchy writeup, geeksforgrowth's early-stage trust-building guidance.

## Code References

- `stay_recon/views.py:1-31` — current `index()` view, `INDEX_HTML` constant, sibling `health()` view
- `stay_recon/urls.py:27` — `/` route registration; `urls.py:30-32` — auth/signup/dashboard route names for CTA targets
- `templates/base.html:1-27` — the app's only shared styling/layout, `{% block title %}` / `{% block content %}` structure
- `templates/accounts/signup.html`, `templates/registration/login.html` — CTA destinations a landing page would link to
- `stay_recon/settings.py:143-153` — `STATIC_URL`, `STATIC_ROOT`, WhiteNoise storage backend (no `STATICFILES_DIRS`)

## Architecture Insights

- The whole app currently uses a single, consistent, deliberately minimal design system defined entirely in `templates/base.html`'s inline `<style>` — there is no per-page CSS anywhere. A landing-page redesign is the first opportunity to either reinforce or deliberately diverge from that system; this decision should be made explicitly in `/10x-plan` since it has knock-on effects for every other template.
- No static asset pipeline is in active use despite being configured (WhiteNoise + `STATIC_ROOT` present, `STATICFILES_DIRS` absent, zero files under any `static/` directory). Introducing even one external CSS file would be new territory for this codebase, not just new content — worth flagging as a scope/complexity decision for planning.
- The three-role access model (`prd.md:100-106`) means the landing page's *only* functional audience is prospective/returning **organisers**; participants and staff never see it. This narrows the page's job considerably (no need to explain participant/staff flows) and was treated as a hard constraint by the UX research.

## Historical Context (from prior changes)

- `prd.md:105` (Access Control, Participant role) — the sole PRD reference to the landing page: *"A visitor with no link sees a generic landing page — no event or booking data is exposed."*
- `shape-notes.md:19,56` — same decision, carried from the PRD's source shaping notes; no additional detail.
- `context/archive/2026-09-11-organiser-auth-app-scaffold/plan-brief.md:44` and `plan.md:126` mention an "empty landing page" — but this refers to the **post-login organiser dashboard**, a different surface from the public `/` route (terminology overlap only, not a prior decision about this page).
- `context/changes/csv-upload-room-mapping/research.md:90` and `plan.md:14` confirm the "no CSS framework, no JS hooks" convention already observed directly in the templates.
- `context/foundation/test-plan.md:153-155` (§7, what's deliberately not tested) excludes "Template/HTML markup and CSS details" from testing as fragile/low-signal — applies to a redesigned landing page too, unless rendering correctness becomes a named risk later.
- The landing page does **not** appear anywhere in `roadmap.md`'s slice table (F-01, F-02, S-01–S-09) as a named deliverable — it has no `FR-NN` of its own and is purely an implicit consequence of the Access Control model. This `landing-page` change folder is the first artifact in `context/` to name it directly.

## Related Research

None — this is the first research artifact for this change, and no other `context/changes/**/research.md` or `context/archive/**/research.md` addresses the landing page.

## Open Questions

1. **Should this change get a roadmap entry?** It currently has no `FR-NN`/slice ID and sits outside the F-01…S-09 dependency chain. Worth deciding before `/10x-plan` whether to fold it into the roadmap (e.g. as a small foundation-adjacent slice) or treat it as an out-of-band polish change, given `top_blocker: time` on the MVP deadline.
2. **Extend `base.html`'s existing minimal style, or introduce something new for the landing page specifically?** Since no static asset pipeline is exercised yet, adding one is a real scope decision, not just content — needs to be made explicitly in planning, not implicitly during implementation.
3. **Is a product screenshot available/creatable** to use as a trust signal, or should the hero ship without one for now (text-only, per the "avoid heavy hero media" guidance)?
