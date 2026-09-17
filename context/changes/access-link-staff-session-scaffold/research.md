---
date: 2026-09-16T18:05:19+02:00
researcher: Michal Zajaczkowski
git_commit: c430dc30011d8b3362b3fd53dc4fb3af63c358c0
branch: dev
repository: stay_recon
topic: "F-02: no-account participant access-link verification + staff session scoped to one event"
tags: [research, codebase, auth, access-links, staff-session, f-02, foundation]
status: complete
last_updated: 2026-09-16
last_updated_by: Michal Zajaczkowski
---

# Research: Access-link & staff-session scaffold (F-02)

**Date**: 2026-09-16T18:05:19+02:00
**Researcher**: Michal Zajaczkowski
**Git Commit**: c430dc30011d8b3362b3fd53dc4fb3af63c358c0
**Branch**: dev
**Repository**: stay_recon

## Research Question

How should F-02 be built: a no-account, token-based link-verification mechanism for participants, and a scoped staff-login session mechanism — both usable by any downstream route that needs them (per `roadmap.md`'s own F-02 definition)? Scope agreed with the user: standard-depth Django-native technique grounding (not a deep cryptographic dive), and a brief mapping of how S-03/S-04/S-08 will actually consume this mechanism, to make sure F-02's interface fits its consumers.

## Summary

**This is genuinely greenfield.** No token/signing/UUID machinery, no participant/staff models, and no custom authentication backend exist anywhere in the codebase today (`AUTHENTICATION_BACKENDS` is unset — plain `ModelBackend` only).

**The most important finding isn't technical — it's a real tension inside the PRD itself**, present since the original shaping session, not something planning invented:
- FR-004 (`prd.md:62`) says the organiser "can generate a unique access link **per participant and per staff member**" — the *same* mechanism, same verb, for both roles.
- Access Control (`prd.md:106`, and `shape-notes.md:17` from the original shaping checkpoint) says event staff "**login** with a staff role, scoped to a single event at a time" — a login/session framing, not a link framing, and explicitly *not* worded like participant's "no account... unique access link" (`prd.md:105`).
- The PRD never states the mechanism connecting the two: does opening a staff "access link" (FR-004's wording) *establish* a login session (Access Control's wording), or are these actually meant to be two different things the PRD conflated? This needs a product decision, not an engineering guess — flagged as Open Question 1 below.

Beyond that: both participant-token and staff-session mechanisms have two well-precedented Django-native design options each (detailed below), the codebase already has a directly relevant naming collision to avoid (`User.is_staff` is Django's built-in *admin-access* flag, unrelated to "event staff"), an existing architectural precedent for DB-backed short-lived token state (`rooms.PendingUpload`), and a clear, already-decided consumer boundary: F-02 owns *verification only* — link/session *generation* UI belongs to S-03, not this change.

## Detailed Findings

### Current state — confirmed greenfield

- Repo-wide grep for `signing|TimestampSigner|uuid|secrets\.|token|get_random_string` across every `.py` file (excluding `.venv`) — **zero relevant hits**. No `django.core.signing` usage, no UUID fields, no custom token generation anywhere.
- No model in `accounts/models.py`, `events/models.py`, or `rooms/models.py` references a participant or event-scoped staff concept. Only three apps exist (`accounts`, `events`, `rooms`).
- `stay_recon/settings.py:93-95` — `LOGIN_URL = 'login'`, `LOGIN_REDIRECT_URL = 'dashboard'`, `LOGOUT_REDIRECT_URL = 'login'`. `AUTHENTICATION_BACKENDS` is not set anywhere — Django's default `ModelBackend` only, no custom backend exists yet for a token or per-event scheme.
- `stay_recon/settings.py:189` — `SESSION_COOKIE_SECURE = True` is the only session setting touched; no `SESSION_COOKIE_AGE`/`SESSION_ENGINE`/other overrides.
- `stay_recon/urls.py:27-38` — current routes, no participant/staff/token patterns exist yet.

### The `is_staff` naming collision (real, not hypothetical)

- `accounts/models.py` — `User(AbstractUser)` inherits Django's built-in `is_staff`/`is_superuser` booleans.
- `accounts/admin.py:9,13` — `UserAdmin.list_display` and fieldsets directly expose `is_staff` as "can access `/admin/`", Django's own documented semantics (https://docs.djangoproject.com/en/stable/ref/contrib/admin/#django.contrib.auth.models.User.is_staff).
- This field **already exists in this codebase** with a meaning completely unrelated to the product's "event staff" role. Reusing or naming anything close to it for F-02's staff concept would silently conflate "can access Django admin" with "is an event staff member" — a real collision to design around, not a naming nitpick.

### Two options for participant access-link tokens (neutral, Django-native, zero new dependencies)

**Option A — Opaque DB-backed token**: a dedicated model with a `token` field (`secrets.token_urlsafe(32)`, `unique=True`, `db_index=True`) FK'd to the event/participant. Lookup by exact match; expiry checked against `event.window_end` (or a denormalized `expires_at`); revocation is a trivial delete or `is_revoked` flag. Matches this codebase's own established pattern — `rooms.PendingUpload` (`rooms/models.py:27-39`) already models short-lived, token-adjacent state as a dedicated Postgres row rather than session storage, a direct in-repo precedent for this approach.

**Option B — Stateless signed token**: `django.core.signing.TimestampSigner`/`dumps()`/`loads(max_age=...)` (https://docs.djangoproject.com/en/stable/topics/signing/), encoding `participant_id`+`event_id`, no new model needed. Django's own documented limitation: a signed value **cannot be individually invalidated before it expires** — only `SECRET_KEY` rotation invalidates it, which would invalidate *every* outstanding signed value project-wide. Django's own `PasswordResetTokenGenerator` (https://docs.djangoproject.com/en/stable/topics/auth/default/#django.contrib.auth.tokens.PasswordResetTokenGenerator) shows the workaround Django itself uses: bind the signature to *mutable state on the target row* (password hash, `last_login`) so a password change effectively revokes old tokens — but this still means reading a DB field at verify time, partly collapsing Option B's "no DB read" advantage if per-participant revocation is ever needed.

### Two options for staff session scoping (neutral, Django-native)

**Option A — Real `User` + a `StaffAssignment` model**: staff authenticate via Django's normal session login (`django.contrib.auth`, `request.user`); a separate `StaffAssignment` FKs `User` + `Event` (optionally a role field); every staff view checks `StaffAssignment.objects.filter(user=request.user, event=event).exists()`. This is the option that actually matches Access Control's "login with a staff role" wording literally — it's a real login.

**Option B — Session-flag-only scoping, no `User` row**: staff use a link/token like participants; verification sets `request.session['staff_event_id'] = event.pk` (https://docs.djangoproject.com/en/stable/topics/http/sessions/ — server-side, dict-like, scoped per visitor). This matches FR-004's "generate a unique access link... per staff member" wording literally, but does **not** constitute a "login" in any conventional sense — no credential, no identity, purely possession-based, functionally identical in kind to the participant mechanism it's modeled after.

**These two options are not just implementation alternatives — they're the two different readings of the PRD's own internal tension above.** Whichever the product decides FR-004 vs. Access Control actually means determines which option is correct; this isn't resolvable by weighing engineering tradeoffs alone.

### Consumer contract — who calls what (per the user's requested scope)

- `roadmap.md:95` — F-02's own stated Outcome: "(foundation) A no-account, token-based link-verification mechanism for participants, and a scoped staff-login session mechanism, **both usable by any route that needs them**."
- `roadmap.md:103` — F-02's own stated Risk/boundary: *"Keeping this to verification-only (not the link-generation UI, which stays user-visible in S-03) avoids re-absorbing S-03's work into a foundation."* **F-02 does not build the "generate a link" UI** — it builds whatever "verify this token/session" function or view other slices call.
- `roadmap.md:132-142` (S-03, `participant-staff-lists-and-links`) — owns adding participant/staff lists and *generating* the actual links; consumes F-02's token-creation primitive (if one exists) or its data model, not just its verification logic.
- `roadmap.md:144-154` (S-04, north star) — consumes F-02 directly for participant link verification, and S-03's generated links.
- `roadmap.md:193-204` (S-08, staff check-in) — consumes F-02's staff-scoped session mechanism and S-03's generated staff links/assignments.
- **Implication for planning**: F-02's contract should expose a narrow, well-defined verification interface (e.g. "given this token, return the participant/event it authorizes, or None/expired") that S-03 can call into for generation and S-04/S-08 can call into for gating access — not a full CRUD UI.

### Existing scoping convention F-02 must extend, not replace

- `events/views.py:36,48` and `rooms/views.py` (throughout) — every organiser-facing view uses `get_object_or_404(Model, pk=pk, organiser=request.user)`, returning 404 not 403 on mismatch.
- `context/foundation/test-plan.md:45` — Risk #3, verbatim: *"One organiser's event, room, or participant data is reachable by another organiser, or by the wrong participant/staff access link"* (Impact High / Likelihood Medium) — this risk is **already tracked** and explicitly anticipates F-02's scoping surface.
- `context/foundation/test-plan.md:56` — the risk's documented response names "future access-link routes" as needing the same 404-not-403 sweep applied to organiser-scoped views today.
- `context/foundation/test-plan.md:71` (§3 Phase 1, "Authorization & scoping contract") references a change folder `context/changes/testing-authorization-scoping-contract/` with status "change opened" — **this folder does not currently exist on disk** (`ls context/changes/` confirms only `access-link-staff-session-scaffold`, `ai-assisted-csv-mapping`, `bootstrap-verification`, `design-system-refresh`, `gated-render-deploy`). Minor doc/reality mismatch worth noting, not a blocker — the authorization-contract work test-plan.md describes hasn't actually been opened as a change yet.
- **Implication**: F-02's participant/staff scoping can't key off `request.user` (participants have no User row under either staff option; staff may or may not, depending on which staff option is chosen) — it needs an analogous pattern keyed off the token/session data instead, but should preserve the same 404-on-mismatch discipline the rest of the app already established.

### The "check-in window" vs. "booking window" wording gap

- `events/models.py` — `Event` has exactly one window pair, `window_start`/`window_end`, described everywhere in code/forms as the *booking* window (FR-008: "2 weeks before to 3 days before the event").
- FR-004 (`prd.md:62`) says links expire "when the event's **check-in** window closes" — different wording from FR-008's "booking window." The PRD never defines a separate check-in window field or clarifies whether this is the same field under a different name, or a genuinely distinct concept (e.g. tied to `event.end_date` instead). Flagged as Open Question 2.

## Code References

- `accounts/models.py` — `User(AbstractUser)`, built-in `is_staff`/`is_superuser` (naming collision risk)
- `accounts/admin.py:9,13` — `is_staff` admin-access exposure
- `rooms/models.py:27-39` — `PendingUpload`, the in-repo precedent for DB-backed short-lived token state
- `events/models.py` — `Event.window_start`/`window_end` (participant booking window)
- `events/views.py:36,48` — `get_object_or_404(..., organiser=request.user)` scoping convention
- `stay_recon/settings.py:61,93-95,189` — `AUTH_USER_MODEL`, `LOGIN_URL`/`LOGIN_REDIRECT_URL`/`LOGOUT_REDIRECT_URL`, `SESSION_COOKIE_SECURE`
- `stay_recon/urls.py:27-38` — current routes

## Architecture Insights

- This codebase has a consistent pattern of preferring Django stdlib/contrib primitives over new dependencies (stdlib `csv` over pandas for CSV parsing; likely the same instinct applies here — `django.core.signing` or a plain DB-token model over any third-party auth/token library).
- The existing `PendingUpload` model is architecturally the closest precedent for "short-lived, token-like state living in Postgres rather than session storage" — worth treating as a soft convention when choosing between the two participant-token options above.
- Object-level 404-not-403 scoping is a strong, consistent convention across every existing view (`events`, `rooms`) — F-02's design should preserve this discipline even though it can't reuse `organiser=request.user` directly.

## Historical Context (from prior changes)

- `context/archive/2026-09-11-organiser-auth-app-scaffold/plan.md:39` and `plan-brief.md:33` — F-01 explicitly scoped out "event-staff authentication or scoped staff sessions — that's roadmap F-02," confirming F-02 was always meant to be a from-scratch design, not an extension of organiser auth.
- `context/archive/2026-09-14-create-event/plan.md:33,38` — S-01 confirms "no separate 'event staff' or 'participant' role touching this slice" — same greenfield confirmation from a different angle.
- `context/changes/csv-upload-room-mapping/research.md` (now archived, `context/archive/2026-09-14-csv-upload-room-mapping/research.md:33,60,66`) — establishes the `PendingUpload`-style DB-backed multi-step state precedent noted above.

## Related Research

- `context/archive/2026-09-14-csv-upload-room-mapping/research.md` — precedent for DB-backed token/state modeling in this codebase.

## Open Questions

1. **Does a staff "access link" (FR-004) establish a login session (Access Control), or are these two different things the PRD conflated?** This is the central fork: it determines whether staff sessions should be Option A (real `User` + `StaffAssignment`, a genuine login) or Option B (session-flag via a link, matching participants). Owner: user/product. Not resolvable by engineering tradeoff analysis alone — recommend settling this explicitly before or during `/10x-plan`, possibly via `/10x-frame` given it's a framing question baked into the PRD itself, not just an implementation detail.
2. **Is FR-004's "check-in window" the same field as FR-008's "booking window" (`Event.window_start`/`window_end`), or a distinct, currently-nonexistent concept?** Affects where link-expiry logic reads its cutoff from. Owner: user/product.
3. **Does F-02 need to expose a token-*creation* primitive for S-03 to call, or does S-03 own the entire creation path independently and F-02 is purely the *verification* side?** Roadmap wording leans toward "S-03 does generation," but the shared data model (if Option A/DB-backed is chosen for participants) will likely need to be defined in F-02 either way, since S-03 has to write into whatever table F-02's verification reads from. Worth clarifying the exact file/model ownership split during planning.
4. **Should the authorization-contract testing work test-plan.md references (§3 Phase 1) be opened as a real change before or alongside F-02**, since its whole purpose (sweeping the 404-not-403 pattern) directly overlaps with what F-02 needs to get right for token/session-based routes? Currently that change folder doesn't exist yet. Owner: user — a sequencing question, not resolved here.
