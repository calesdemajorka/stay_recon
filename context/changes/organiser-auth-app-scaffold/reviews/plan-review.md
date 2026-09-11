<!-- PLAN-REVIEW-REPORT -->
# Plan Review: Organiser Auth & Django App Scaffold

- **Plan**: `context/changes/organiser-auth-app-scaffold/plan.md`
- **Mode**: Deep
- **Date**: 2026-09-11
- **Verdict**: REVISE (all findings fixed during triage — see Decisions below)
- **Findings**: 1 critical, 1 warning, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | FAIL (pre-fix) |
| Lean Execution | PASS |
| Architectural Fitness | PASS |
| Blind Spots | WARNING (pre-fix) |
| Plan Completeness | WARNING (pre-fix) |

## Grounding

Grounding: 5/5 paths ✓, 4/4 symbols ✓, brief↔plan ✓. Deep verification done directly (this session built the entire current codebase) rather than via sub-agent; the one high-value check — Django 6.1's actual email-settings API — was verified live against official Django docs.

## Findings

### F1 — Phase 4 uses deprecated EMAIL_* settings that hard-conflict with the already-present MAILERS config

- **Severity**: ❌ CRITICAL
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: End-State Alignment
- **Location**: Phase 4 — Password reset via Resend, Change #1 (Email settings)
- **Detail**: `stay_recon/settings.py` already defines a `MAILERS` dict (console backend) from the original scaffold. Django 6.1 (this project's exact version) introduced `MAILERS` as the replacement for `EMAIL_BACKEND`/`EMAIL_HOST`/`EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD`/`EMAIL_PORT`/`EMAIL_USE_TLS`. Per Django's official mailers-migration docs (fetched live during review): when `MAILERS` is defined, accessing any deprecated `EMAIL_*` setting raises `AttributeError` — the two are mutually exclusive, `MAILERS` wins. Phase 4's original Contract set exactly those deprecated flat settings alongside the pre-existing `MAILERS` dict, which would crash the moment any code sends mail — exactly when Phase 4's own automated Success Criteria try to verify it.
- **Fix**: Rewrite Phase 4 Change #1's Contract to configure `MAILERS['default']` directly (env-gated console vs SMTP via `OPTIONS`: host/port/username/password/use_tls) instead of flat `EMAIL_*` settings. Unit tests asserting on `mail.outbox` must override `MAILERS`, not `EMAIL_BACKEND`.
- **Decision**: FIXED — applied to plan.md (Phase 4 Contract, Success Criteria, and Current State Analysis updated).

### F2 — No documented recovery if Phase 1's post-reset deploy migration fails

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Migration Notes
- **Detail**: The human resets the production schema before Phase 1's commit is pushed. If the subsequent deploy's `migrate` step fails, Render keeps serving the previous release, but that release's code expects the now-deleted old schema — the site would be briefly broken with no documented next step.
- **Fix**: Add one sentence to Migration Notes — since zero real data exists, a failed Phase 1 deploy is safe to retry from scratch (re-run the schema reset, re-push/redeploy).
- **Decision**: FIXED — applied to plan.md (Migration Notes).

### F3 — Phase 2's manual step doesn't specify how to reach production to run createsuperuser

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 2 — Manual Verification
- **Detail**: "createsuperuser against production" didn't say how. Render web services expose SSH (`srv-dah8hr1t0dsc73f1cvd0@ssh.oregon.render.com`, confirmed this session).
- **Fix**: Name the mechanism explicitly — `render ssh stay-recon` (or plain `ssh <sshAddress>`), then run the command inside the container.
- **Decision**: FIXED — applied to plan.md (Phase 2 Manual Verification).
