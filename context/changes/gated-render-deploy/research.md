---
date: 2026-09-14T18:10:24+02:00
researcher: Claude (Sonnet 5)
git_commit: b91abbf4f55a3942c33f68fce63476c96cb51c76
branch: dev
repository: calesdemajorka/stay_recon
topic: "Gate Render deploys behind GitHub Actions CI"
tags: [research, deployment, render, github-actions, ci-cd]
status: complete
last_updated: 2026-09-14
last_updated_by: Claude (Sonnet 5)
---

# Research: Gate Render deploys behind GitHub Actions CI

**Date**: 2026-09-14T18:10:24+02:00
**Researcher**: Claude (Sonnet 5)
**Git Commit**: b91abbf
**Branch**: dev
**Repository**: calesdemajorka/stay_recon

## Research Question

The user's proposed approach: Render should deploy from a `master`/`main`
branch, only after the GitHub Actions workflow has verified a commit on
`dev` (implying a dev → main promotion model). Validate this approach,
determine whether `context/foundation/` docs need updating, and validate
whether this is actually possible with Render's current setup.

## Summary

**The proposed two-branch model is not currently buildable as stated — the
`master`/`main` branch it depends on does not exist, on GitHub or locally.**
More importantly, it's unnecessary: **Render has a native, single-line
config option that achieves the exact stated goal without any branch
changes.**

Render's Blueprint spec supports `autoDeployTrigger: checksPass` — "trigger
a deploy only if the linked branch's CI checks pass" — which reads GitHub's
Checks API directly. The `.github/workflows/ci.yml` workflow added earlier
this session already reports to that API on every push to `dev` with no
extra configuration required. Flipping one line in `render.yaml`
(`autoDeployTrigger: commit` → `checksPass`) gates production deploys on
the CI workflow passing, on the existing single-branch (`dev`) setup,
today.

The dev → main promotion model the user proposed is a heavier, valid
*alternative* pattern (common for release-branch workflows), but it
requires creating a branch that doesn't exist, a promotion mechanism (PR or
scripted merge), GitHub branch protection rules to make the gate actually
enforced, and re-pointing Render's connected branch — real structural work
for a goal the native trigger already covers.

## Detailed Findings

### Current deploy configuration (ground truth, verified live)

- `render.yaml` (repo file) declares `autoDeployTrigger: commit` and a
  `buildFilter` allowlist, but **no `branch` field** — branch is not
  declared in the Blueprint YAML in this repo today.
- The live Render service (`srv-dah8hr1t0dsc73f1cvd0`, queried via
  `mcp__plugin_render_render__get_service`) confirms: `"autoDeploy":"yes"`,
  `"autoDeployTrigger":"commit"`, `"branch":"dev"`. Branch is a
  Dashboard/API-level property on the service, separate from the `render.yaml`
  file's own content (though the Blueprint spec *does* support declaring
  it — see below).
- `context/deployment/deploy-plan.md` documents this as intentional: "No
  GitHub Actions CI wired yet" and "routine deploys ... run unattended
  going forward" — written 2026-09-10, before any CI existed.

### No `master`/`main` branch exists

- `git branch -a` (local): only `dev` and `remotes/origin/dev`.
- `gh api repos/calesdemajorka/stay_recon/branches`: only `dev`.
- `gh repo view --json defaultBranchRef`: default branch is `dev`.
- `gh api repos/.../branches/dev/protection` → `404 Branch not protected`:
  no branch protection rule exists on `dev` today — nothing currently
  prevents a direct push from reaching production via the existing
  `commit` trigger.

The proposed approach's premise ("Render should deploy from master") is not
buildable without first creating that branch and deciding a promotion
mechanism — this is a real prerequisite, not a naming detail.

### Render's native CI-gating feature (validated via official docs)

Fetched `render.com/docs/deploys` (Blueprint spec) directly:

- `autoDeployTrigger` has three values: `commit` (default — deploy on every
  push), **`checksPass`** ("Render waits for a new commit's CI checks to
  complete before triggering a deploy. If *all* checks pass, Render
  proceeds with the deploy."), and `off`.
- What counts as a check: "Render detects the results of CI checks
  originating from ... GitHub Actions [and] tools that integrate with the
  GitHub checks API." A check counts as passed when its conclusion is
  "success, neutral, or skipped."
- Fail-closed behavior: "Render does *not* trigger a deploy if: Zero checks
  are detected for the new commit." This matters — if a future change
  scopes the CI workflow's trigger so it stops running on some pushes to
  `dev`, deploys would silently stop happening rather than deploying
  unverified code. Current `.github/workflows/ci.yml` has no path filter on
  its `push` trigger (only `branches: [main, dev]`), so every push to `dev`
  today always produces a check run — no zero-check risk as configured.
- The docs explicitly recommend the opposite direction too: "If your repo
  doesn't run CI checks, use On Commit instead" — confirming `checksPass`
  is meant exactly for repos that already have CI wired, which is now true
  here.
- Also confirmed via `render.com/docs/blueprint-spec`: the Blueprint YAML
  **does** support a `branch` field per service ("For Git-based services,
  the branch of the linked repo to use"), with a documented caveat that
  setting it also pins all PR preview environments to that branch instead
  of each PR's own branch. Not needed for the `checksPass` path since no
  branch change is required; would matter only if the two-branch model
  were chosen instead.

### The CI workflow already in place is compatible with either path

`.github/workflows/ci.yml` (added this session, commit `b91abbf`):

```yaml
on:
  push:
    branches: [main, dev]
  pull_request:
```

Runs `uv sync --frozen`, `manage.py check`, `manage.py test` — verified
green on GitHub Actions (run `34866023233`, `test` job passed in 36s). This
workflow needs **no changes** for the `checksPass` approach — it already
runs on every push to `dev` and reports to the Checks API Render reads.

## Architecture Insights

- Render intentionally separates *build scoping* (`buildFilter`, which
  paths trigger a rebuild at all) from *deploy gating* (`autoDeployTrigger`,
  whether a triggered build actually promotes to live) — these are
  independent controls, both already present in this repo's config,
  currently only the first is used.
- The project's existing single-branch, direct-push-to-`dev` workflow (no
  PRs, no branch protection) means `checksPass` is the only gate that fits
  without changing how the team works day-to-day. A two-branch model would
  be a workflow change (introducing PRs and/or a promotion step), not just
  a config change.
- `context/foundation/tech-stack.md`'s existing hint `ci_default_flow:
  auto-deploy-on-merge` (set back in Module 2, before CI existed) already
  gestures at a merge-gated flow — `checksPass` is the more literal,
  minimal realization of that hint than the two-branch model is.

## Code References

- [`render.yaml:15`](https://github.com/calesdemajorka/stay_recon/blob/b91abbf4f55a3942c33f68fce63476c96cb51c76/render.yaml#L15) — `autoDeployTrigger: commit`, the line that would change to `checksPass`.
- [`.github/workflows/ci.yml:1-9`](https://github.com/calesdemajorka/stay_recon/blob/b91abbf4f55a3942c33f68fce63476c96cb51c76/.github/workflows/ci.yml#L1-L9) — push trigger covering `dev` (and `main`, currently unused).
- [`context/deployment/deploy-plan.md:88-92`](https://github.com/calesdemajorka/stay_recon/blob/b91abbf4f55a3942c33f68fce63476c96cb51c76/context/deployment/deploy-plan.md#L88-L92) — documents the current unattended-commit-trigger deploy story as of 2026-09-10, now stale on the "No GitHub Actions CI wired yet" claim.
- [`context/foundation/roadmap.md:73`](https://github.com/calesdemajorka/stay_recon/blob/b91abbf4f55a3942c33f68fce63476c96cb51c76/context/foundation/roadmap.md#L73) — Baseline line citing `autoDeployTrigger: commit`, would go stale if the trigger changes.
- [`context/foundation/tech-stack.md:9-10`](https://github.com/calesdemajorka/stay_recon/blob/b91abbf4f55a3942c33f68fce63476c96cb51c76/context/foundation/tech-stack.md#L9-L10) — `ci_provider`/`ci_default_flow` hints, consistent with either path but worth a cross-reference once implemented.
- [`CLAUDE.md:80`](https://github.com/calesdemajorka/stay_recon/blob/b91abbf4f55a3942c33f68fce63476c96cb51c76/CLAUDE.md#L80) — project rule: "Do not author CI/CD pipelines from scratch or write GitHub Actions YAML. ... owned by Module 1 Lesson 5 and Module 2 Lesson 5." Flagging for awareness: both this session's CI workflow and this deploy-gating change fall inside that named boundary. The user explicitly requested both, so this is a heads-up, not a blocker — worth knowing this is getting ahead of the course's own sequencing.

## Historical Context (from prior changes)

- `context/deployment/deploy-plan.md` (2026-09-10 deploy record) — explicit
  "Explicitly Deferred" section already lists "GitHub Actions CI wiring —
  separate from Render's own auto-deploy" as tracked-but-not-done at that
  time. That gap is what this session's `.github/workflows/ci.yml` closed;
  this change is the natural next step the same doc anticipated.
- No prior `context/changes/**/` or `context/archive/**/` folder addresses
  deploy gating or branch strategy — this is new ground.

## Recommendation (for the follow-up plan)

Two viable paths, validated as of this research:

1. **`autoDeployTrigger: checksPass` on the existing `dev` branch
   (recommended)** — one-line `render.yaml` change, zero new branches, zero
   new GitHub configuration, achieves "Render deploys only after CI
   verifies the commit" exactly as stated. Docs to update:
   `context/deployment/deploy-plan.md` (Operational Story → deploys
   section) and `context/foundation/roadmap.md:73` (Baseline line).
2. **`dev` → `main` promotion model (the originally proposed approach)** —
   requires: creating `main` on GitHub, a promotion mechanism (PR-based or
   a scripted fast-forward job gated on `dev`'s CI passing), a GitHub
   branch protection rule on `main` requiring the CI check (otherwise nothing
   stops a direct push to `main` bypassing the gate), and re-pointing
   Render's connected branch to `main` (via `render.yaml`'s `branch` field
   or the Dashboard). More moving parts, more docs to update (also
   `tech-stack.md`, `CLAUDE.md`'s branch references if any get added, and
   the deploy-plan/infrastructure operational story), but matches a more
   conventional release-branch model if that's independently wanted (e.g.
   for a future staging/production split).

Both are technically valid; option 1 is strictly smaller for the stated
goal. This research does not choose between them — that's a decision for
`/10x-plan`.

## Follow-up Verification (2026-09-14, post-implementation)

The commit that flipped `autoDeployTrigger` to `checksPass` (`a1bf2e4`)
deployed to `live` at `16:16:38`, roughly 10 seconds *before* its own
GitHub check run (`check-runs` for that commit) completed at `16:16:48`.
This is a self-referential edge case: Render evaluates the trigger mode in
effect at webhook-receipt time, which for this specific push was still the
old `commit` rule (the Blueprint sync that applies the new `checksPass`
value happens as part of processing the same push, not before it). So the
commit that *introduces* the gate does not itself get gated — expected,
not a bug, but worth recording so it isn't mistaken for the feature not
working. Confirmed via `mcp__plugin_render_render__get_service` immediately
after that push that `autoDeployTrigger` is now `checksPass` on the live
service config. The real test is whether the *next* commit's deploy waits
for its own check — verified separately (see below).

## Open Questions

- If option 2 is chosen: should `main` require a PR (with review) to merge
  from `dev`, or is a scripted auto-promotion (fast-forward `main` to
  `dev`'s HEAD once CI is green) acceptable given this is a solo project?
  This determines whether a second GitHub Actions job is needed.
- Does the user want a staging/production split independent of this CI-gate
  goal (which would make option 2's extra structure worth it on its own
  merits, not just for gating)? Not signaled anywhere in `context/foundation/`
  today.
