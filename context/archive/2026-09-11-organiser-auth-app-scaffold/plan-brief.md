# Organiser Auth & Django App Scaffold — Plan Brief

> Full plan: `context/changes/organiser-auth-app-scaffold/plan.md`

## What & Why

StayRecon has zero domain code — a bare Django scaffold with auth installed but unused. This change creates the first Django app and a full organiser auth loop (signup, login, logout, password reset), because every other roadmap slice (creating events, uploading CSVs, everything) needs an app to live in and an authenticated organiser to own records. It's roadmap item `F-01`, the one item currently unblocked.

## Starting Point

No app, no models, no templates, no login. The live Render Postgres has only Django's own built-in migrations applied — zero real rows anywhere, which matters a lot for how this plan handles the user-model decision below.

## Desired End State

An organiser can sign up with an email + password on `https://stay-recon.onrender.com`, land on an empty dashboard, log out, log back in, and recover a forgotten password by email — all over a hardened HTTPS session.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) |
| --- | --- | --- |
| Login method | Email/password (Django built-in) | Fastest to ship, zero new dependency, matches `top_blocker: time`. |
| Signup | Public signup form | User's call — PRD's Access Control describes a full account, not admin-provisioned only. |
| Password reset | Django's built-in email-based flow | User's call — needed despite the extra scope it pulls in. |
| Login identifier / user model | Custom `accounts.User`, email as `USERNAME_FIELD`, decided **now** | Django requires this decided before the first migration — and this genuinely is the first migration point, since the production DB has zero real rows to lose in a clean-slate reset. |
| Email delivery | Resend, SMTP relay, shared `onboarding@resend.dev` sender | Resend's free tier (3,000/mo) beats Postmark's (100/mo); no custom domain exists yet, so delivery is limited to the account owner's own inbox until one is verified — an accepted, documented limitation, not silently dropped. |
| Security hardening | Bundled into this change (Phase 5), not deferred | This is the first real login form submitting over HTTPS — exactly when the standing `check --deploy` warnings stop being theoretical. |
| Testing | Minimal automated (success/failure paths per phase) + one manual pass on Render | Matches `top_blocker: time`; still catches the likely breakage classes. |

## Scope

**In scope:** custom email-based User model, signup, login, logout, dashboard placeholder, password reset via Resend, production cookie/HSTS/SSL-redirect hardening.

**Out of scope:** OAuth/passwordless, event-staff auth (`F-02`), any `Event`/domain model or "own events" scoping (`S-01`), Resend custom-domain verification, rate-limiting/lockout, audit logging, 2FA, GitHub Actions CI.

## Architecture / Approach

One new Django app (`accounts`) holds the custom `User` model, auth views, and templates. Django's built-in `django.contrib.auth.urls` include supplies login/logout/reset URL plumbing; this plan supplies the model, the signup view Django doesn't ship, and the templates the built-in views require by convention. `SECURE_PROXY_SSL_HEADER` is set explicitly because Render terminates TLS upstream — without it, `SECURE_SSL_REDIRECT` causes an infinite redirect loop.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. User model & app scaffold | `accounts` app, email-based `User`, production schema reset | Must land before any other migration exists — this is the one hard-to-reverse phase |
| 2. Login, logout & dashboard | Functional auth loop, empty landing page | Low risk — standard Django patterns |
| 3. Signup | Public account creation, duplicate-email handling | Case-insensitive uniqueness must be enforced, not just DB-default |
| 4. Password reset via Resend | Real email delivery in production | No custom domain yet — delivery limited to the account owner's own inbox |
| 5. Security hardening | Cookie/HSTS/SSL-redirect settings | Missing `SECURE_PROXY_SSL_HEADER` causes a silent redirect loop on Render specifically |

**Prerequisites:** none — this is the roadmap's only `ready` item.
**Estimated effort:** not estimated (roadmap convention — no time units; sequence, not schedule).

## Open Risks & Assumptions

- Resend's shared sender only delivers to the account owner's own email until a custom domain is verified — fine for the immediate deadline (one real organiser), a real gap the moment a second organiser needs a live password reset.
- The production DB schema reset is a human, destructive-action step (per this project's established posture) — Phase 1 cannot fully complete without it.
- `SECURE_HSTS_SECONDS` starts conservative (3600s) rather than the usual one-year value, since there's no custom domain or rollback plan yet.

## Success Criteria (Summary)

- An organiser can sign up, log in, reach the dashboard, log out, and reset a forgotten password — entirely on the live Render deploy, not just locally.
- `manage.py check --deploy` is clear of the cookie/HSTS/SSL-redirect warnings that have been standing since the first deploy.
- Every subsequent roadmap slice (`S-01` onward) can now assume an authenticated organiser exists.
