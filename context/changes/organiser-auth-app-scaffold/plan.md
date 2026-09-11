# Organiser Auth & Django App Scaffold Implementation Plan

## Overview

StayRecon has zero domain code today — a bare Django scaffold with `django.contrib.auth` installed but unused. This plan creates the first Django app (`accounts`), a custom email-based User model, and a full organiser auth loop (signup, login, logout, password reset via Resend), plus the production security hardening that a real login form now requires. This is roadmap item `F-01` — a foundation that unlocks every other slice (`S-01` through `S-09`), since nothing else can be built until an app exists and an organiser can authenticate.

## Current State Analysis

- `stay_recon/settings.py` has `django.contrib.auth` in `INSTALLED_APPS` (Django default) but no custom app, no `AUTH_USER_MODEL`, no login/logout URLs, no templates directory, and none of `SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE`/`SECURE_SSL_REDIRECT`/`SECURE_HSTS_SECONDS` set (verified directly — `code`, not inferred).
- `stay_recon/settings.py` already defines a `MAILERS` dict (console backend) from the original scaffold — Django 6.1 introduced `MAILERS` as the replacement for `EMAIL_BACKEND`/`EMAIL_HOST`/etc, and the two are mutually exclusive (accessing the deprecated flat settings while `MAILERS` is defined raises `AttributeError`). Phase 4 configures `MAILERS` directly rather than the deprecated settings.
- `stay_recon/urls.py` wires only `/` (placeholder), `/admin/`, `/healthz/` — verified directly (`code`).
- The live Render Postgres (`stay-recon-db`) has only Django's built-in migrations applied (`admin`, `auth`, `contenttypes`, `sessions`) — zero real rows exist in any table (`code`, confirmed via `django_migrations` read-only query during the Render deploy work; no superuser or any other record was ever created).
- `render.yaml` currently wires `SECRET_KEY` (generated), `DEBUG`, `DATABASE_URL`, `PYTHON_VERSION`, `WEB_CONCURRENCY` — no email-related env vars yet.
- Deploy pipeline (`build.sh` → `uv sync` → `collectstatic` → `migrate`) is live and auto-deploys on push to `dev`, scoped by `buildFilter` to `manage.py`, `stay_recon/**`, `build.sh`, `pyproject.toml`, `uv.lock`, `.python-version`, `render.yaml` — this change's new `accounts/` app falls under `stay_recon/**`'s sibling scope and needs an explicit `buildFilter.paths` addition (`accounts/**`) or it won't trigger rebuilds.

## Definitions

| Term | Decided meaning | Origin | On degenerate data | Verified by |
| ---- | --------------- | ------ | ------------------- | ----------- |
| Organiser (identity) | Any account with an `accounts.User` record; PRD's Access Control restricts each organiser to only see/manage their own events | product (PRD §Access Control) | No `Event` model exists in this change, so "own events" scoping has nothing to enforce yet — deferred to `S-01` | Deferred — `S-01`'s tests will cover event ownership scoping |
| Login identifier | Email address, case-insensitive (normalized to lowercase before storage and comparison) | user (email/password + custom-user-model decisions, this session) | Two signups differing only in email case (`A@x.com` vs `a@x.com`) must collide as a duplicate, not create two accounts | Phase 1 unit test: case-insensitive lookup; Phase 3 unit test: duplicate-email signup rejected regardless of case |

## Desired End State

An organiser can sign up with an email + password, log in, land on an empty account-scoped dashboard, log out, and recover a forgotten password via email — all live on `https://stay-recon.onrender.com`, over a hardened HTTPS session. `AUTH_USER_MODEL` points at the new `accounts.User` from the very first migration, so every future slice (`S-01` onward) builds on a stable identity model with no later migration surgery needed.

Verification: `uv run manage.py check --deploy` shows no auth/cookie/HSTS warnings; the live signup → login → dashboard → logout → password-reset loop works end-to-end on Render; `render psql` (read-only) confirms `accounts_user` is the live user table with zero legacy `auth_user` rows to reconcile.

### Key Discoveries:

- No real data exists in the production DB (`code`, confirmed this session) — this means swapping `AUTH_USER_MODEL` can use a clean schema reset instead of the painful mid-project migration-surgery Django docs otherwise require, because there's no data to preserve across the swap.
- Render terminates TLS upstream and forwards plain HTTP with an `X-Forwarded-Proto` header — `SECURE_SSL_REDIRECT = True` without `SECURE_PROXY_SSL_HEADER` set causes an infinite redirect loop on Render specifically (confirmed via research — this is the standard PaaS-proxy gotcha, not specific to this codebase, but easy to miss).
- Resend requires a verified custom domain to deliver to anyone other than the account owner; sending from the shared `onboarding@resend.dev` address only reaches the Resend account owner's own inbox. StayRecon has no custom domain (per `context/deployment/deploy-plan.md`'s explicit "custom domain: not doing" scope).
- Django's built-in `django.contrib.auth.urls` include bundles login, logout, and all four password-reset views in one line — Phase 2 wires this include once; Phase 4 supplies the templates that make the already-wired reset URLs functional end-to-end.

## What We're NOT Doing

- OAuth or passwordless login — PRD's Access Control lists these as alternatives, not requirements; roadmap `F-01`'s own Risk line explicitly warns against this scope-creep.
- Event-staff authentication or scoped staff sessions — that's roadmap `F-02`, a separate change.
- Any `Event`/domain data model or "own events" access scoping enforcement — no `Event` model exists yet; that's `S-01`.
- Resend custom-domain verification — shipping with the shared `onboarding@resend.dev` sender, which only reliably delivers to the Resend account owner's own email. Documented as an accepted limitation (see Testing Strategy and the brief's Open Risks), not silently dropped.
- Rate-limiting or account lockout on repeated failed logins.
- Audit logging of auth events (PRD's audit-trail FR-005 note already defers this past the deadline for the whole product).
- Two-factor auth, "remember me" duration tuning beyond Django's session defaults.
- GitHub Actions CI for this change — out of scope per the project's existing deploy posture; Render's own `autoDeployTrigger: commit` covers it.

## Implementation Approach

Sequence by risk: the custom User model (Phase 1) is the one genuinely hard-to-reverse decision — it must land correctly before any other app or migration exists, so it comes first, paired with the one-time production schema reset it requires. Login/logout (Phase 2) and signup (Phase 3) build the functional loop. Password reset (Phase 4) is sequenced after the functional loop works, since it depends on Phase 1's model and introduces the one new external dependency (Resend). Security hardening (Phase 5) comes last, once there's a real login form worth hardening, and is verified separately from functional correctness so a hardening misconfiguration (e.g. the SSL-redirect-loop gotcha) doesn't get conflated with an auth bug.

## Critical Implementation Details

- **Timing & lifecycle**: The production Postgres schema reset (see Migration Notes) must happen *before* this phase's first deploy runs `migrate`, not after. If `migrate` runs first against the existing empty-but-already-migrated schema and the reset happens afterward, Django's `django_migrations` bookkeeping and the new `accounts.0001_initial` dependency ordering can diverge from what a truly fresh deploy would produce. Sequence: reset schema → push → deploy runs `migrate` fresh.

## Phase 1: Custom user model & app scaffold

### Overview

Creates the `accounts` app and a custom, email-based `User` model, sets `AUTH_USER_MODEL` before any accounts migration exists, and resets the (currently empty) production schema so the fresh migration history applies cleanly.

### Changes Required:

#### 1. New app: `accounts`

**File**: `accounts/__init__.py`, `accounts/apps.py`, `accounts/models.py`, `accounts/admin.py`, `accounts/migrations/0001_initial.py`

**Intent**: Give the project its first domain app, and replace Django's default username-based `User` with an email-based one, per this session's login-method and login-field decisions.

**Contract**: `accounts/models.py` defines `User(AbstractUser)` with `email` as `USERNAME_FIELD`, `email` unique and case-normalized (lowercased) on save, `username` removed from `REQUIRED_FIELDS`/no longer used as the identifier, and a custom manager overriding `create_user`/`create_superuser` to normalize email before lookup/creation. `accounts/admin.py` registers `User` with an admin class adapted from `django.contrib.auth.admin.UserAdmin` (drops the `username` field references). `0001_initial.py` is Django-generated via `makemigrations accounts` — do not hand-write it.

#### 2. Project settings

**File**: `stay_recon/settings.py`

**Intent**: Register the new app and point Django's auth system at it before any migration runs.

**Contract**: `INSTALLED_APPS` gains `'accounts'`; new setting `AUTH_USER_MODEL = 'accounts.User'`.

#### 3. Deploy build filter

**File**: `render.yaml`

**Intent**: The existing `buildFilter.paths` allowlist doesn't include the new app's directory — without this, pushes touching only `accounts/**` won't trigger a rebuild.

**Contract**: Add `accounts/**` to `buildFilter.paths`.

### Success Criteria:

#### Automated Verification:

- `uv run manage.py makemigrations --check --dry-run` reports no missing migrations
- `uv run manage.py migrate` applies cleanly against a freshly deleted local `db.sqlite3`
- `uv run manage.py check` passes with no errors
- Unit test: creating a user via `User.objects.create_user(email="A@Example.com", password="...")` then looking it up via `User.objects.get(email="a@example.com")` succeeds (case-insensitive identity)

#### Manual Verification:

- Human has reset the production Postgres schema (see Migration Notes) before this phase deploys
- After deploy, a read-only `django_migrations` query (via `render psql` or the Render MCP) shows `accounts.0001_initial` alongside the standard `admin`/`auth`/`contenttypes`/`sessions` migrations, with zero rows in `accounts_user`

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 2: Login, logout & dashboard

### Overview

Wires Django's built-in login/logout views (and the shared auth-urls include that Phase 4 will also depend on), plus a minimal login-gated dashboard placeholder — the first page an organiser sees after authenticating.

### Changes Required:

#### 1. URL wiring

**File**: `stay_recon/urls.py`

**Intent**: Expose login/logout (and, structurally, the password-reset URLs Phase 4 will make functional) plus the new dashboard route.

**Contract**: Add `path('accounts/', include('django.contrib.auth.urls'))` (ships `login/`, `logout/`, and all four password-reset URL names under this prefix) and `path('dashboard/', dashboard_view, name='dashboard')`.

#### 2. Dashboard view

**File**: `accounts/views.py` (new)

**Intent**: The empty, account-scoped landing page an organiser reaches after login — proves the auth wrapper works with nothing else built yet.

**Contract**: `dashboard` view decorated with `@login_required`, rendering `accounts/dashboard.html` with the current `request.user`.

#### 3. Templates

**File**: `templates/base.html`, `templates/registration/login.html`, `templates/accounts/dashboard.html` (new)

**Intent**: Minimal shared layout plus the two pages this phase needs. Django's built-in `LoginView` looks for `registration/login.html` by convention — no override needed to change that path.

**Contract**: `base.html` provides a shared `<html>` skeleton; `login.html` extends it with Django's standard login form; `dashboard.html` extends it with a placeholder ("Welcome, {{ request.user.email }}").

#### 4. Settings

**File**: `stay_recon/settings.py`

**Intent**: Point Django's auth redirects at the new routes, and register the project-level templates directory.

**Contract**: `LOGIN_URL = 'login'`, `LOGIN_REDIRECT_URL = 'dashboard'`, `LOGOUT_REDIRECT_URL = 'login'`; `TEMPLATES[0]['DIRS'] = [BASE_DIR / 'templates']`.

### Success Criteria:

#### Automated Verification:

- Unit test: `GET /accounts/login/` returns 200
- Unit test: `POST /accounts/login/` with valid credentials redirects (302) to `/dashboard/`
- Unit test: `GET /dashboard/` while unauthenticated redirects (302) to login
- Unit test: `POST /accounts/logout/` clears the session (subsequent `GET /dashboard/` redirects to login again)

#### Manual Verification:

- On the live Render deploy: create a superuser via `render ssh stay-recon` (or plain `ssh srv-dah8hr1t0dsc73f1cvd0@ssh.oregon.render.com`), then `uv run manage.py createsuperuser` inside the container; log in with it, reach the dashboard, log out

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 3: Signup

### Overview

A custom signup view and form (Django ships no built-in signup view), with duplicate-email validation, auto-logging the new organiser in on success.

### Changes Required:

#### 1. Signup form

**File**: `accounts/forms.py` (new)

**Intent**: Collect email + password for a new organiser account, rejecting a duplicate (case-insensitive) email with a friendly error rather than a database `IntegrityError`.

**Contract**: `SignupForm(UserCreationForm)` with `Meta.model = User`, `Meta.fields = ('email',)`; `clean_email` normalizes case and checks existing rows before Django's own uniqueness constraint would raise.

#### 2. Signup view

**File**: `accounts/views.py`

**Intent**: Render the form, create the account, and log the organiser straight in — matching the "public signup" decision from this session.

**Contract**: `signup` view (function-based or `CreateView`); on valid POST, saves the user, calls `django.contrib.auth.login(request, user)`, redirects to `dashboard`.

#### 3. URL + template

**File**: `stay_recon/urls.py`, `templates/accounts/signup.html` (new)

**Intent**: Expose the new view.

**Contract**: `path('signup/', signup_view, name='signup')`; template extends `base.html` with the signup form.

### Success Criteria:

#### Automated Verification:

- Unit test: valid signup creates a user and redirects (302) to `/dashboard/`, with the session authenticated
- Unit test: signup with an email that already exists (including a different case, e.g. existing `a@x.com` vs submitted `A@x.com`) shows a form validation error and creates no new row
- Unit test: signup with a malformed email is rejected by form validation

#### Manual Verification:

- On the live Render deploy: sign up with a new email, confirm landing on the dashboard already logged in

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 4: Password reset via Resend

### Overview

Wires Django's built-in password-reset flow to real email delivery through Resend's SMTP relay, using the shared `onboarding@resend.dev` sender (no custom domain exists yet — see Testing Strategy for the accepted limitation this implies).

### Changes Required:

#### 1. Email settings

**File**: `stay_recon/settings.py`

**Intent**: Send real email in production via Resend; keep local dev on Django's console backend (no behavior change locally, matching the existing `DEBUG`/`DATABASE_URL` env-gating pattern already in this file).

**Contract**: `stay_recon/settings.py` already defines a `MAILERS` dict (Django 6.1's replacement for `EMAIL_BACKEND`/`EMAIL_HOST`/`EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD`/`EMAIL_PORT`/`EMAIL_USE_TLS` — those flat settings are deprecated and, per Django's own docs, raise `AttributeError` if accessed while `MAILERS` is defined, since the two are mutually exclusive). Update `MAILERS['default']` in place, env-gated the same way as elsewhere in this file: console backend (as today) when `RESEND_API_KEY` is unset, otherwise `django.core.mail.backends.smtp.EmailBackend` with `OPTIONS = {'host': 'smtp.resend.com', 'port': 587, 'username': 'resend', 'password': os.environ['RESEND_API_KEY'], 'use_tls': True}`. `DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'onboarding@resend.dev')` is unaffected — it's a separate, still-supported top-level setting, not part of the `MAILERS` migration.

#### 2. Password-reset templates

**File**: `templates/registration/password_reset_form.html`, `password_reset_done.html`, `password_reset_email.html`, `password_reset_subject.txt`, `password_reset_confirm.html`, `password_reset_complete.html` (new)

**Intent**: Django's built-in password-reset views look up these exact template names under `registration/` by convention — supplying them is what makes the URLs Phase 2 already wired functional end-to-end.

**Contract**: Standard Django password-reset template set, each extending `base.html` where applicable (the two `.txt`/email templates do not).

#### 3. Deploy config

**File**: `render.yaml`, `.env.example`

**Intent**: Wire the new secret without ever typing or committing it.

**Contract**: `render.yaml` gains `RESEND_API_KEY` (`sync: false` — human sets the value in the Render dashboard after signing up for Resend) and `DEFAULT_FROM_EMAIL` (`value: onboarding@resend.dev`) under the web service's `envVars`. `.env.example` documents both.

### Success Criteria:

#### Automated Verification:

- Unit test (override `MAILERS` — not `EMAIL_BACKEND`, which is inaccessible once `MAILERS` is defined — to point `default` at Django's `locmem` backend): requesting a reset for an existing email produces one entry in `mail.outbox`
- Unit test: requesting a reset for a non-existent email does not error and does not reveal account existence (Django's built-in view already guarantees this — test confirms it isn't accidentally overridden)

#### Manual Verification:

- **Human step**: sign up for Resend, generate an API key, set `RESEND_API_KEY` in the Render dashboard env vars
- On the live Render deploy: request a password reset for the account-owner's own email (the only address `onboarding@resend.dev` can reliably deliver to without a verified domain), confirm the email arrives, complete the reset, log in with the new password

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 5: Production security hardening

### Overview

Sets the cookie/HSTS/SSL-redirect settings that `manage.py check --deploy` has been warning about since the first Render deploy — deferred until now because there was no real login form for them to protect. Includes the Render-specific proxy header fix that prevents an SSL-redirect loop.

### Changes Required:

#### 1. Hardening settings

**File**: `stay_recon/settings.py`

**Intent**: Protect the session/CSRF cookies now carrying real auth state, without breaking local HTTP-only dev.

**Contract**: Gated the same way `DEBUG`/`ALLOWED_HOSTS` already are (active when `RENDER_EXTERNAL_HOSTNAME` is set): `SESSION_COOKIE_SECURE = True`, `CSRF_COOKIE_SECURE = True`, `SECURE_SSL_REDIRECT = True`, `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')` — the last one is required on Render specifically, or `SECURE_SSL_REDIRECT` causes an infinite redirect loop, since Render terminates TLS upstream and forwards plain HTTP. `SECURE_HSTS_SECONDS = 3600` (a conservative one-hour starting value — HSTS is a one-way browser commitment, worth ratcheting up gradually rather than starting at the usual one-year value on a domain with no rollback plan yet).

### Success Criteria:

#### Automated Verification:

- `DEBUG=False RENDER_EXTERNAL_HOSTNAME=x SECRET_KEY=x uv run manage.py check --deploy` no longer warns on `security.W004`, `security.W008`, `security.W012`, `security.W016`
- Local `uv run manage.py check` (no `RENDER_EXTERNAL_HOSTNAME`) still passes — hardening settings inactive locally

#### Manual Verification:

- On the live Render deploy: `curl -IL https://stay-recon.onrender.com/` shows a clean response with no redirect loop (this is exactly where a missed `SECURE_PROXY_SSL_HEADER` would surface as repeated 301s)
- Browser devtools confirm the session cookie has the `Secure` flag set after logging in

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Testing Strategy

### Unit Tests:

- Custom User creation, case-insensitive email lookup (Phase 1)
- Login success/failure, logout, dashboard auth-gating (Phase 2)
- Signup success, duplicate-email (including case) rejection, malformed-email rejection (Phase 3)
- Password-reset email dispatch and non-enumeration behavior (Phase 4)

### Integration Tests:

- Full signup → auto-login → dashboard → logout → login again round trip via Django's test client

### Manual Testing Steps:

1. On the live Render deploy, sign up with a new email and confirm arrival on the dashboard, logged in.
2. Log out, log back in with the same credentials.
3. Request a password reset for the account-owner's own email (the only reliable delivery target given the no-custom-domain limitation), complete the flow, log in with the new password.
4. Confirm `curl -IL https://stay-recon.onrender.com/` shows no redirect loop and the session cookie has `Secure` set.

## Performance Considerations

None specific to this change — auth views are Django defaults with no added query complexity, and there is no meaningful load yet (PRD's `target_scale.qps: low`).

## Migration Notes

The production Postgres (`stay-recon-db`) currently has zero real rows — only the empty schema from Django's built-in `admin`/`auth`/`contenttypes`/`sessions` migrations. Because `AUTH_USER_MODEL` must be set before its app's first migration (Django's own hard constraint) and no data exists to lose, the correct move is a clean-slate reset rather than a mid-project user-model migration:

1. **Human step** (destructive action — matches this project's established human-on-destructive-actions posture from `context/deployment/deploy-plan.md`): reset the production schema via `render psql` running `DROP SCHEMA public CASCADE; CREATE SCHEMA public;`, or delete-and-recreate the `stay-recon-db` resource in the Render dashboard.
2. Push this change's Phase 1 commit. `build.sh`'s `migrate` step then applies the full migration history — including `accounts.0001_initial` — fresh, against the empty schema.
3. Locally, delete the gitignored `db.sqlite3` and re-run `uv run manage.py migrate` for the same clean-slate effect (agent-safe — no real local data exists either).

This must happen before Phase 1's deploy, not after (see Critical Implementation Details).

**If the deploy's `migrate` step fails after the reset**: since there is zero real data at stake, treat this as safe to retry from scratch — re-run the schema reset and re-push/redeploy, rather than attempting a partial recovery. The site may briefly serve the previous release against the now-empty schema (e.g. `/admin/` 500s) until the retry lands.

## References

- Roadmap: `context/foundation/roadmap.md` (`F-01: Organiser auth & app scaffold`)
- PRD: `context/foundation/prd.md` (`## Access Control §Organiser`)
- Deploy posture: `context/deployment/deploy-plan.md` (secrets/approval conventions this plan follows)

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Custom user model & app scaffold

#### Automated

- [ ] 1.1 `makemigrations --check --dry-run` reports no missing migrations
- [ ] 1.2 `migrate` applies cleanly against a freshly deleted local `db.sqlite3`
- [ ] 1.3 `manage.py check` passes
- [ ] 1.4 Case-insensitive email lookup unit test passes

#### Manual

- [ ] 1.5 Production Postgres schema reset before deploy
- [ ] 1.6 `django_migrations` confirms `accounts.0001_initial` live, zero rows in `accounts_user`

### Phase 2: Login, logout & dashboard

#### Automated

- [ ] 2.1 `GET /accounts/login/` returns 200
- [ ] 2.2 Valid login redirects to `/dashboard/`
- [ ] 2.3 Unauthenticated `/dashboard/` redirects to login
- [ ] 2.4 Logout clears session

#### Manual

- [ ] 2.5 Live login/dashboard/logout walkthrough on Render

### Phase 3: Signup

#### Automated

- [ ] 3.1 Valid signup creates user, auto-logs in, redirects to dashboard
- [ ] 3.2 Duplicate email (any case) rejected, no new row
- [ ] 3.3 Malformed email rejected

#### Manual

- [ ] 3.4 Live signup walkthrough on Render

### Phase 4: Password reset via Resend

#### Automated

- [ ] 4.1 Reset request for existing email produces one `mail.outbox` entry
- [ ] 4.2 Reset request for non-existent email doesn't error or leak existence

#### Manual

- [ ] 4.3 `RESEND_API_KEY` set in Render dashboard
- [ ] 4.4 Live password-reset walkthrough (request → email → confirm → login)

### Phase 5: Production security hardening

#### Automated

- [ ] 5.1 `check --deploy` clear of cookie/HSTS/SSL-redirect warnings with prod-like env
- [ ] 5.2 Local `check` still passes with hardening inactive

#### Manual

- [ ] 5.3 `curl -IL` on live Render URL shows no redirect loop
- [ ] 5.4 Session cookie has `Secure` flag in browser devtools
