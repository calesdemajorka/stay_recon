<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Organiser Auth & Django App Scaffold

- **Plan**: context/changes/organiser-auth-app-scaffold/plan.md
- **Scope**: Phases 1-4 of 5
- **Date**: 2026-09-14
- **Verdict**: APPROVED
- **Findings**: 0 critical, 2 warnings, 4 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | WARNING |
| Safety & Quality | WARNING |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

## Success criteria verification

Automated (run directly): `makemigrations --check --dry-run` — no changes detected; `migrate` against a freshly deleted local db.sqlite3 — applies cleanly; `manage.py check` — no issues; full test suite — 10/10 pass.

Manual (from Progress): 1.5, 1.6, 2.5, 2.6 marked `[x]` — consistent with commit history, no rubber-stamping detected. 3.4 (Phase 3 live walkthrough), 4.3, 4.4 (Phase 4 RESEND_API_KEY + live walkthrough) correctly still `[ ]` — pending, not yet confirmed by the human. This is expected mid-flight state, not a defect.

## Findings

### F1 — templates/** missing from render.yaml's buildFilter

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality (deploy-pipeline reliability)
- **Location**: render.yaml (buildFilter.paths)
- **Detail**: Phases 2-4 added 10 template files under templates/, but buildFilter.paths never gained templates/** (only accounts/** was added, in Phase 1, for the same class of reason). Every commit so far also touched a covered path, so this hasn't bitten yet — but a future template-only commit will silently skip the Render rebuild.
- **Fix**: Add `templates/**` to render.yaml's buildFilter.paths, same pattern as Phase 1's accounts/** addition.
- **Decision**: FIXED — templates/** added to buildFilter.paths.

### F2 — git checkout * auto-allowed, not gated like git push

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: .claude/settings.local.json:9
- **Detail**: Bundled into the Phase 2 commit (pre-existing dirty state, unrelated to this plan, acknowledged in that commit's message). `Bash(git checkout *)` sits in `allow`, but `git push`/`git push *` sit in `ask`. A stray checkout could silently discard uncommitted work with no confirmation.
- **Fix**: Move `"Bash(git checkout *)"` from `allow` to `ask`, matching git push's treatment.
- **Decision**: FIXED — moved to `ask` in .claude/settings.local.json.

### F3 — Unrelated files bundled into the Phase 2 commit

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: .claude/settings.local.json, .gitignore, CLAUDE.md (in e51264b)
- **Detail**: Not in Phase 2's plan Contract. Commit message explicitly acknowledges this: "Folded in: ... (both pre-existing dirty, unrelated to this phase but bundled per request)." Transparent at commit time, not silent scope creep.
- **Fix**: None needed — already documented in the commit message.
- **Decision**: ACKNOWLEDGED — no action needed.

### F4 — Superuser create-only limitation not echoed as a code comment

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: accounts/management/commands/bootstrap_superuser.py
- **Detail**: plan.md documents (Phase 2 Contract) that rotating DJANGO_SUPERUSER_PASSWORD after the account exists has no effect on redeploy, but the code carries no comment saying so.
- **Fix**: One-line comment above the skip-if-exists check pointing to this behavior.
- **Decision**: FIXED — comment added to bootstrap_superuser.py.

### F5 — bootstrap_superuser bypasses AUTH_PASSWORD_VALIDATORS

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: accounts/management/commands/bootstrap_superuser.py:32
- **Detail**: create_superuser() skips password-strength validation — identical to Django's own createsuperuser behavior, not a new gap this plan introduced.
- **Fix**: None — standard Django behavior.
- **Decision**: ACKNOWLEDGED — no action needed.

### F6 — /healthz/ doesn't follow CLAUDE.md's error-shape rule

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: stay_recon/views.py (health()) — pre-existing, wired by urls.py
- **Detail**: A DB outage would raise Django's default HTML 500, not this project's mandated `{ error: { code, message, context } }` shape (CLAUDE.md, Project Rules). Pre-existing file, not touched by any of Phases 1-4.
- **Fix**: None in this change — filed as GH #16 instead of an inline fix (out of this plan's scope; confirmed no upcoming roadmap slice touches this file incidentally).
- **Decision**: FILED AS ISSUE — GH #16, not fixed inline per user preference.
