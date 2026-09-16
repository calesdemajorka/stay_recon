# Landing Page — Plan Brief

> Full plan: `context/changes/landing-page/plan.md`
> Research: `context/changes/landing-page/research.md`

## What & Why

StayRecon's public `/` route is currently a hardcoded placeholder HTML string that says, verbatim, "the real product experience isn't built yet." This plan replaces it with a real, template-rendered landing page for the app's only public audience — prospective/returning organisers — explaining the CSV-reconciliation problem StayRecon solves and routing them to Sign up or Log in.

## Starting Point

`stay_recon/views.py::index` returns `HttpResponse(INDEX_HTML)`, not a template. The entire app shares one minimal design system defined in `templates/base.html`'s inline `<style>` (narrow column, system font, no nav, no CSS framework, no static asset pipeline in active use, no branding assets anywhere in the repo).

## Desired End State

Visiting `/` shows a header (brand + Log in/Sign up nav), a hero with a specific value-prop headline and CTA, a problem/solution section, a 3-step how-it-works section, a repeated CTA, and a minimal footer — styled with a deliberately richer, distinct look while sharing the rest of the app's font. Both CTAs route correctly and are guarded by one automated test.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
|---|---|---|---|
| Styling mechanism | Extend `base.html`'s existing inline `<style>`, scoped under `.landing` | Zero new infra (no static pipeline), stays inside the app's one existing design system | Plan (user Q&A) |
| Visual direction | Distinct, richer identity vs. the rest of the app | User chose the strongest first-impression option for a marketing entry point | Plan (user Q&A) |
| Copy source | Fresh marketing copy, not adapted from README.md | User wants copy tuned for a visitor's first 10 seconds, not documentation tone | Plan (user Q&A) |
| Testing | One `accounts/tests.py` route/content test | Matches existing project test convention; cheap regression guard on the only functional risk (broken CTA link) | Plan (user Q&A) |
| Roadmap placement | Added as new slice S-10 in `roadmap.md` | User wants all shipped work tracked in the roadmap, even though it's not a named PRD FR | Plan (user Q&A) |
| Trust signals | None (no testimonials/logos/stats) | Research: fake social proof is detectable and erodes trust at this stage; none exist yet | Research |
| Test discovery | New test lives in `accounts/tests.py`, not a new `stay_recon/tests.py` | `stay_recon` isn't in `INSTALLED_APPS` — a project-level `tests.py` would be silently skipped by CI's `manage.py test` | Plan (codebase check) |

## Scope

**In scope:** template conversion of `index()`, new `templates/landing.html`, scoped CSS additions to `base.html`, fresh hero/problem-solution/how-it-works/CTA copy, one automated test, roadmap slice S-10.

**Out of scope:** new static asset pipeline, logo/favicon/screenshot, pricing/testimonials, any participant- or staff-facing content, changes to any other template's visual style.

## Architecture / Approach

Pure Django template + inline-CSS change, no new dependencies, no data model. `base.html` gains one new `{% block body_class %}` hook so `landing.html` can scope its own richer styling (`.landing` selector) without affecting any other page. The view swaps a raw `HttpResponse` for `render(request, 'landing.html')`.

## Phases at a Glance

| Phase | What it delivers | Key risk |
|---|---|---|
| 1. Landing page template, styling, copy, and test | Full landing page live at `/`, CTAs wired, one regression test | Low — content/markup only; main risk was test-discovery (`stay_recon` not in `INSTALLED_APPS`), already resolved by placing the test in `accounts/tests.py` |

**Prerequisites:** none beyond what's already shipped (F-01 login/signup exist).
**Estimated effort:** single session, one phase.

## Open Risks & Assumptions

- The chosen accent color (`~#0f6a5c`) is a planning-time suggestion for AA contrast and visual distinctness — the implementer should verify actual contrast once rendered, not just trust the hex value.
- "Distinct richer identity" is scoped to this one page; if the rest of the app is redesigned later, `.landing`'s CSS may need to be promoted into a shared system rather than staying page-scoped.

## Success Criteria (Summary)

- A visitor to `/` immediately understands what StayRecon does and who it's for, without scrolling past a wall of text.
- Sign up and Log in are both reachable in one click from the landing page.
- No regressions: full test suite and Django system check still pass.
