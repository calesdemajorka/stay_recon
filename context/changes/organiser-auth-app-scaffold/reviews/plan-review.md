<!-- PLAN-REVIEW-REPORT -->
# Plan Review: Organiser Auth & Django App Scaffold

- **Plan**: `context/changes/organiser-auth-app-scaffold/plan.md`
- **Mode**: Deep
- **Date**: 2026-09-13
- **Verdict**: REVISE (all findings fixed during triage — see Decisions below)
- **Findings**: 1 critical, 0 warnings, 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | PASS |
| Lean Execution | PASS |
| Architectural Fitness | PASS |
| Blind Spots | WARNING (pre-fix) |
| Plan Completeness | FAIL (pre-fix) |

## Grounding

Grounding: 10/10 paths ✓, 5/5 symbols ✓, brief↔plan ✓. Phases 1–3 code (already implemented) checked directly against their Contracts — `accounts/models.py`, `accounts/forms.py`, `accounts/views.py`, `stay_recon/urls.py`, `render.yaml`, `build.sh`, `accounts/management/commands/bootstrap_superuser.py` all match. Phase 4's unimplemented `MAILERS` SMTP `OPTIONS` shape (host/port/username/password/use_tls, all lowercase) was re-verified live against the official Django 6.1 email docs and matches the plan's Contract exactly.

## Findings

### F1 — Phase 2 Progress is missing a checkbox for a Manual Verification bullet

- **Severity**: ❌ CRITICAL
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 2 — Login, logout & dashboard / `## Progress` → Phase 2 → Manual
- **Detail**: Phase 2's Manual Verification lists two bullets (set `DJANGO_SUPERUSER_EMAIL`/`PASSWORD`; live login/dashboard/logout walkthrough), but Progress → Phase 2 → Manual had only one checkbox (`2.5`, the walkthrough). The env-var step had no tracked checkbox — the only phase in the plan where Success Criteria bullets and Progress checkboxes didn't map 1:1.
- **Fix**: Added `- [x] 2.5 DJANGO_SUPERUSER_EMAIL/PASSWORD set in Render dashboard — e51264b`, renumbered the walkthrough item to `2.6`.
- **Decision**: FIXED — applied to plan.md (Phase 2 Progress → Manual).

### F2 — bootstrap_superuser silently no-ops on password rotation

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 2 — Superuser bootstrap (already implemented, `accounts/management/commands/bootstrap_superuser.py`)
- **Detail**: Confirmed in the actual command: it skips creation whenever a user with that email already exists — it never updates the password on rerun. Rotating `DJANGO_SUPERUSER_PASSWORD` in the Render dashboard later is a silent no-op; the account keeps the old password. Not documented anywhere in the plan.
- **Fix**: Added a "Known limitation" line to the Phase 2 Contract explaining the no-op behavior and the recovery path (`changepassword` via `render ssh`, or delete-and-recreate the row).
- **Decision**: FIXED — applied to plan.md (Phase 2, Superuser bootstrap Contract).

### F3 — Phase 3's Progress items don't carry a commit sha, unlike Phases 1–2

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: `## Progress` → Phase 3 → Automated (3.1–3.3)
- **Detail**: The Progress convention says "append — `<commit sha>` when a step lands." Phases 1–2 follow this; Phase 3's items were checked but carried no sha, even though `git log` shows a Phase 3 commit (`e474205`).
- **Fix**: Confirmed `e474205` is the correct commit (`git show --stat` — touches `accounts/forms.py`, `accounts/views.py`, `stay_recon/urls.py`, `templates/accounts/signup.html`, `accounts/tests.py`; message "Signup (p3)"). Appended `— e474205` to Progress items 3.1–3.3.
- **Decision**: FIXED — applied to plan.md (Progress → Phase 3 → Automated).
