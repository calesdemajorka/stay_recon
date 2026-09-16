# Landing Page Implementation Plan

## Overview

Replace the current placeholder `/` route (a raw inline-HTML string returned from `stay_recon/views.py::index`) with a real, template-rendered public landing page for StayRecon. The page targets the app's only public-facing audience — prospective/returning **organisers** — with fresh marketing copy explaining the CSV-reconciliation problem StayRecon solves, a short how-it-works section, and clear Sign up / Log in calls to action. Participants and staff never reach this page (they arrive via per-event access links), so no content here is written for them.

## Current State Analysis

- `stay_recon/views.py:4-25` — `index()` returns `HttpResponse(INDEX_HTML)`, a hardcoded HTML string explicitly labeled *"This is a placeholder landing page — the real product experience isn't built yet."* Not a Django template.
- `stay_recon/urls.py:27` — `path('', index, name='index')` is the only route mounted at `/`. No `@login_required`; publicly accessible.
- `templates/base.html:1-27` is the **only** source of styling in the app. Every other template (`accounts/dashboard.html`, `accounts/signup.html`, `registration/*.html`, `events/*.html`, `rooms/*.html`) extends it and adds no CSS of its own — a single narrow centered column, system font, gray secondary text (`#555`), no framework, no images, no nav.
- No `static/` directory, no `STATICFILES_DIRS`, no CSS framework or CDN reference anywhere in the repo. WhiteNoise + `STATIC_ROOT` are configured (`stay_recon/settings.py:143-153`) but unused.
- No logo/favicon/branding asset anywhere in the repo.
- CTA targets confirmed via `stay_recon/urls.py`: `signup` → `/signup/` (line 32), `login` → `/accounts/login/` (via `django.contrib.auth.urls` include, line 30, standard Django name `login`), `dashboard` → `/dashboard/` (line 31, post-login only, not linked from the landing page).
- `stay_recon` (the project config package that owns `views.py`) is **not** in `INSTALLED_APPS` (`stay_recon/settings.py:49-59`: `admin`, `auth`, `contenttypes`, `sessions`, `messages`, `staticfiles`, `accounts`, `events`, `rooms`). Django's `manage.py test` (no args, as run in CI — `.github/workflows/ci.yml`) discovers tests per installed app; a `stay_recon/tests.py` would **not** be picked up.
- Existing test convention (`accounts/tests.py:17-27`, `LoginLogoutDashboardTests`): `TestCase` + `self.client.get(reverse(...))` + status-code/content assertions.
- `context/foundation/test-plan.md:124-132` (§6.2, "Adding an integration test — view-level") already documents this exact pattern — no cookbook update needed for this change.
- Full detail: `context/changes/landing-page/research.md`.

## Desired End State

`GET /` renders a template-based landing page with:
- A header (brand name + Log in / Sign up nav links)
- A hero section (headline, subhead, primary CTA)
- A problem/solution section explaining the CSV-reconciliation pain point
- A "how it works" section (3 steps)
- A repeated CTA section
- A minimal footer

The page shares `base.html`'s font/typography system but reads as a deliberately richer, more polished entry point than the rest of the app's utilitarian internal screens (per user decision: distinct richer identity). Sign up and Log in links route correctly. One automated test guards against a broken route or missing CTA links.

**Verification**: `uv run manage.py test accounts` passes; visiting `/` in a browser shows the sections above at both desktop and ~400px phone width.

### Key Discoveries

- `templates/base.html` has no mechanism for a template to add a body-level CSS hook (no `body_class` block) — needed to scope new landing-specific CSS without touching every other page's markup.
- The project's only accessible "installed app" surface for project-level (non-app-owned) view tests is an existing app's `tests.py` — `accounts` is the natural fit here since the page's functional job is routing to `accounts`' own `signup`/`login` views.

## What We're NOT Doing

- No new static asset pipeline (no external CSS file, no `STATICFILES_DIRS` change) — all new CSS lives inside `base.html`'s existing inline `<style>`, scoped under a `.landing` selector.
- No logo, favicon, or product screenshot — none exist yet; the hero ships text-only.
- No changes to any other template's markup or visual style — the richer treatment is scoped entirely to the landing page.
- No participant- or staff-facing content on this page.
- No pricing, testimonials, customer logos, or usage-stat claims — none would be genuine at this stage.
- No new roadmap FR on the PRD — this slice (S-10) implements the PRD's existing Access Control clause, it doesn't add a new requirement.

## Implementation Approach

Single phase: convert the view to a template, extend `base.html`'s shared stylesheet with a `.landing`-scoped block of new rules (header/hero/CTA/how-it-works, an accent color, wider container, one mobile breakpoint), write the landing page's copy directly into the new template, wire the two CTA links to existing URL names, and add one route/content test to the app that owns those URL names (`accounts`).

## Critical Implementation Details

- **Test discovery**: `stay_recon` is not in `INSTALLED_APPS`, so a `stay_recon/tests.py` would be silently skipped by CI's `uv run manage.py test`. Add the new test to `accounts/tests.py` instead, following the existing `LoginLogoutDashboardTests` pattern in the same file.
- **CSS scoping**: `base.html` is shared by every template in the app. All new landing-specific rules must be scoped under `.landing` (e.g. `body.landing`, `.landing .hero`, `.landing .cta-primary`) so they don't leak into `accounts/dashboard.html`, the CSV upload flow, or any other screen. The new `{% block body_class %}{% endblock %}` must default to empty so templates that don't override it are unaffected.

## Phase 1: Landing page template, styling, copy, and test

### Overview

Everything needed to ship the new landing page in one cohesive change: template, scoped styling, copy, CTA wiring, and a regression test.

### Landing Page Copy

The following copy is the actual content for this phase — fresh marketing copy per the planning decision, grounded in the PRD's problem statement but not copied from README.md.

- **Header nav**: brand "StayRecon"; nav links "Log in" (secondary) and "Sign up" (primary button)
- **Hero**
  - Headline: "Stop reconciling hotel rooms by hand."
  - Subhead: "Every hotel hands you a different CSV. StayRecon turns it into a bookable room list your participants can use — and a report you can trust when it's time to settle the invoice."
  - Primary CTA: "Sign up" → `{% url 'signup' %}`
  - Secondary CTA: "Log in" → `{% url 'login' %}`
- **Problem/solution section**
  - Heading: "The reconciliation problem"
  - Body: "Independent event organisers run events at a different hotel every time — and every hotel's room-availability export looks different. Today that gets reconciled by hand in spreadsheets, twice: once to open bookings, again after the event to check what was actually used against the invoice. One mistake means disputing charges or paying for rooms nobody stayed in."
  - Second paragraph: "StayRecon does the normalization step nobody else solves — map a hotel's CSV once, and get a room list you can trust for both booking and invoicing."
- **How it works** (heading: "How it works"), 3 steps:
  1. "Upload & map" — "Upload the hotel's CSV and map its columns — room number, type, capacity — once per event."
  2. "Share access links" — "Send each participant a unique link. They book their own room — no account required."
  3. "Reconcile with confidence" — "Generate a rooms-used-vs-booked report any time after the event, ready to hand to the hotel."
- **Repeated CTA section**
  - Heading: "Ready to stop reconciling by hand?"
  - Primary CTA: "Sign up" → `{% url 'signup' %}`
- **Footer**: brand name "StayRecon" + "Log in" link only. No fabricated contact info, copyright line, or social links.

### Changes Required

#### 1. `stay_recon/views.py`

**Intent**: Replace the hardcoded HTML placeholder with a template-rendered view; the `INDEX_HTML` constant becomes dead code and is removed.

**Contract**: `index(request)` returns `render(request, 'landing.html')`. `health(request)` is unchanged.

#### 2. `templates/landing.html` (new)

**Intent**: The full landing page markup, using the copy specified above.

**Contract**: `{% extends "base.html" %}`; sets `{% block title %}StayRecon — stop reconciling hotel rooms by hand{% endblock %}` and `{% block body_class %}landing{% endblock %}`; structure is `<header>` (brand + nav) → `<section class="hero">` → `<section class="problem">` → `<section class="how-it-works">` (3 items) → `<section class="cta-repeat">` → `<footer>`; CTA links use `{% url 'signup' %}` and `{% url 'login' %}`, never hardcoded paths.

#### 3. `templates/base.html`

**Intent**: (a) Let child templates opt into page-specific body styling without a new inheritance layer. (b) Extend the shared inline stylesheet with a `.landing`-scoped block giving the landing page a distinct, richer visual treatment than the rest of the app, while keeping the same font stack (`system-ui, sans-serif`).

**Contract**: `<body class="{% block body_class %}{% endblock %}">` (defaults to empty string for every existing template). New CSS is additive — appended to the existing `<style>` block, not replacing any current rule — scoped under `.landing`/`body.landing` selectors: an accent color (e.g. a dark teal, ~`#0f6a5c`, chosen for AA contrast against white) used for the primary CTA button fill and section headings; a wider content container than the app's existing `32rem` (e.g. `~60rem`) for the landing sections only; larger hero typography than `base.html`'s default `h1`; a 3-column grid for the how-it-works steps collapsing to 1 column under one `@media (max-width: 640px)` breakpoint; visible focus outlines preserved (not stripped) on the nav/CTA links.

#### 4. `accounts/tests.py`

**Intent**: Guard against a broken landing-page route or a CTA link pointing at the wrong URL.

**Contract**: New `LandingPageTests(TestCase)` class, following the existing `LoginLogoutDashboardTests` shape in the same file: one test asserting `self.client.get(reverse('index'))` returns 200, and that the response content contains both `reverse('signup')` and `reverse('login')`.

### Success Criteria

#### Automated Verification

- Django system check passes: `uv run manage.py check`
- New test passes: `uv run manage.py test accounts`
- Full test suite still passes (no regressions): `uv run manage.py test`

#### Manual Verification

- Visiting `/` shows header, hero, problem/solution, how-it-works, repeated CTA, and footer sections
- "Sign up" and "Log in" links navigate to the correct pages
- Page reads correctly at ~400px phone width with no horizontal scroll and no broken layout
- The landing page's visual style (accent color, hero typography, wider container) reads as an intentional, richer treatment distinct from the rest of the app's utilitarian screens, while still sharing the same base font

**Implementation Note**: After automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before considering this change complete.

---

## Testing Strategy

### Unit/Integration Tests

- `LandingPageTests.test_landing_page_loads_with_ctas` — `GET /` returns 200 and contains both the signup and login URLs in the response body.

### Manual Testing Steps

1. Run `uv run manage.py runserver` and open `/` in a browser.
2. Confirm all six sections render with the copy specified above.
3. Click "Sign up" — confirm it lands on `/signup/`. Click "Log in" — confirm it lands on `/accounts/login/`.
4. Resize the browser to ~400px width — confirm the how-it-works grid collapses to one column and nothing overflows horizontally.
5. Visually compare the landing page to `/dashboard/` or `/signup/` — confirm it reads as a deliberately richer, distinct entry point while still using the same font.

## Performance Considerations

No new network requests are introduced (no external CSS/fonts/images) — the page is a single server-rendered HTML response using the existing inline stylesheet, so load-time impact is negligible.

## Migration Notes

Not applicable — no data model or schema changes.

## References

- Research: `context/changes/landing-page/research.md`
- Existing test convention: `accounts/tests.py:17-27` (`LoginLogoutDashboardTests`)
- Shared template system: `templates/base.html:1-27`
- Test-plan cookbook pattern followed (no update needed): `context/foundation/test-plan.md:124-132` (§6.2)

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles.

### Phase 1: Landing page template, styling, copy, and test

#### Automated

- [x] 1.1 Django system check passes: `uv run manage.py check` — aae374c
- [x] 1.2 New test passes: `uv run manage.py test accounts` — aae374c
- [x] 1.3 Full test suite still passes: `uv run manage.py test` — aae374c

#### Manual

- [x] 1.4 Landing page shows header, hero, problem/solution, how-it-works, repeated CTA, and footer — aae374c
- [x] 1.5 Sign up and Log in links navigate to the correct pages — aae374c
- [x] 1.6 Page reads correctly at ~400px phone width, no horizontal scroll — aae374c
- [x] 1.7 Visual style reads as an intentional, richer treatment distinct from the rest of the app, same font stack — aae374c
