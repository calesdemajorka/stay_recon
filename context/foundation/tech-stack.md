---
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
---

## Why this stack

StayRecon is a solo-built, 2-week MVP that needs multi-role login (organiser, staff), an admin-style CRUD surface for events/rooms/bookings, and scheduled work (link expiry, GDPR retention checks) — exactly what Django's batteries-included model (ORM, auth, admin, migrations) covers out of the box. `django` is the verified recommended default for `(web, python)`, so the standard path was taken with no custom framework comparison. Deployment targets Render (chosen over the starter's Fly.io default) with CI on GitHub Actions and auto-deploy-on-merge. Payments, realtime, and AI features are out of scope per the PRD's Non-Goals, so those flags are unset.
