---
bootstrapped_at: 2026-09-04T12:04:57Z
starter_id: django
starter_name: Django
project_name: stay-recon
language_family: python
package_manager: uv
cwd_strategy: native-cwd
bootstrapper_confidence: verified
phase_3_status: ok
audit_command: pip-audit --format json
---

## Hand-off

```yaml
starter_id: django
package_manager: uv
project_name: stay-recon
hints:
  language_family: python
  team_size: solo
  deployment_target: render
  ci_provider: github-actions
  ci_default_flow: auto-deploy-on-merge
  bootstrapper_confidence: verified
  path_taken: standard
  quality_override: false
  self_check_answers: null
  has_auth: true
  has_payments: false
  has_realtime: false
  has_ai: false
  has_background_jobs: true
```

StayRecon is a solo-built, 2-week MVP that needs multi-role login (organiser, staff), an admin-style CRUD surface for events/rooms/bookings, and scheduled work (link expiry, GDPR retention checks) — exactly what Django's batteries-included model (ORM, auth, admin, migrations) covers out of the box. `django` is the verified recommended default for `(web, python)`, so the standard path was taken with no custom framework comparison. Deployment targets Render (chosen over the starter's Fly.io default) with CI on GitHub Actions and auto-deploy-on-merge. Payments, realtime, and AI features are out of scope per the PRD's Non-Goals, so those flags are unset.

## Pre-scaffold verification

| Signal      | Value    | Severity | Notes                                                                 |
| ----------- | -------- | -------- | ---------------------------------------------------------------------- |
| npm package | not run  | n/a      | non-JS starter; cmd_template does not invoke an npm-distributed CLI    |
| GitHub repo | not run  | n/a      | card `docs_url` is `https://docs.djangoproject.com`, not a GitHub URL  |

## Scaffold log

**Resolved invocation**: `uv run django-admin startproject stay_recon .` (preceded by `uv venv` + `uv pip install django` to bootstrap the toolchain — neither `uv` nor `pip` were present on this machine; `uv` was installed via `pipx install uv`)
**Strategy**: native-cwd
**Exit code**: 0
**Pre-flight files-to-touch**: manage.py, stay_recon/__init__.py, stay_recon/settings.py, stay_recon/urls.py, stay_recon/asgi.py, stay_recon/wsgi.py
**Files written by CLI**: 6
**Pre-existing files preserved**: .claude/, CLAUDE.md, context/ (none touched by the scaffold)

Note: `.venv/` was also created in cwd to host the `uv`-managed Django install. It is not part of the starter's own file set but is a necessary companion for running `django-admin` and `pip-audit` below.

## Post-scaffold audit

**Tool**: pip-audit --format json
**Summary**: 0 CRITICAL, 0 HIGH, 0 MODERATE, 0 LOW
**Direct vs transitive**: not distinguished by this tool

No findings. Project dependencies (django 6.1.1, asgiref 3.12.1, sqlparse 0.6.0) are clean.

## Hints recorded but not acted on

| Hint                     | Value          |
| ------------------------ | -------------- |
| bootstrapper_confidence  | verified       |
| quality_override         | false          |
| path_taken               | standard       |
| self_check_answers       | null           |
| team_size                | solo           |
| deployment_target        | render         |
| ci_provider               | github-actions |
| ci_default_flow          | auto-deploy-on-merge |
| has_auth                 | true           |
| has_payments             | false          |
| has_realtime             | false          |
| has_ai                   | false          |
| has_background_jobs      | true           |

## Next steps

Next: a future skill will set up agent context (CLAUDE.md, AGENTS.md). For now, your project is scaffolded and verified — happy hacking.

Useful manual steps in the meantime:
- `git init` (if you have not already) to start your own repo history.
- Review any `.scaffold` siblings the conflict policy created and decide which version of each file to keep. (None were created this run — no conflicts.)
- Address audit findings per your project's risk tolerance — the full breakdown is in this log. (Clean tree this run.)
- `.venv/` was created to install Django via `uv`; add it to `.gitignore` before committing (Django's `startproject` did not generate a `.gitignore` in this Django version).
