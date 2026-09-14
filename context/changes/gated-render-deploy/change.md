---
change_id: gated-render-deploy
title: Gate Render deploys behind GitHub Actions CI
status: implemented
created: 2026-09-14
updated: 2026-09-14
archived_at: null
---

## Notes

Render currently auto-deploys on every commit to `dev` with no CI gate
(`autoDeployTrigger: commit`). User wants deploys gated on the GitHub
Actions workflow (`.github/workflows/ci.yml`, added this session) passing
first, originally proposed as a dev → master branch promotion model.
Research requested to validate the approach, check whether it's actually
possible with Render, and identify which `context/foundation/` docs need
updating.

**Resolution**: research.md found the proposed `master` branch doesn't
exist and is unnecessary — Render's native `autoDeployTrigger: checksPass`
achieves the goal on the existing single-branch `dev` setup. User picked
this option (1) over the two-branch promotion model (2). Implemented
directly (no `/10x-plan` — a one-line `render.yaml` change plus two doc
corrections didn't warrant the full phase-based ceremony): `render.yaml`
flipped to `checksPass`, `context/deployment/deploy-plan.md` and
`context/foundation/roadmap.md`'s Baseline line corrected.
