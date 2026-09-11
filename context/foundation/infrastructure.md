---
project: stay-recon
researched_at: 2026-09-07
recommended_platform: Render
runner_up: Railway
context_type: mvp
tech_stack:
  language: python
  framework: django
  runtime: python3.12 (uv-managed)
---

## Recommendation

**Deploy on Render.**

Render scored 5/5 on the agent-friendly criteria — the only candidate to do so — with an official first-party Django deployment guide, native GA cron jobs that map directly onto the PRD's link-expiry and GDPR-retention sweeps, co-located managed Postgres, and an MCP server with a native Claude Code plugin. This independently confirms (via fresh research, not a carried-over assumption) the `deployment_target: render` hint already recorded in `context/foundation/tech-stack.md` from Lesson 2. It also fits the interview constraints: no persistent-connection requirement to fight, lowest realistic cost among the viable Django-native platforms, and co-located Postgres for the "co-location preferred" answer.

## Platform Comparison

Two candidates were dropped by hard filter before scoring — Django needs a persistent WSGI process with native Postgres drivers (psycopg2), which neither platform provides:

- **Cloudflare Workers/Pages** — dropped. Python Workers are still in open beta; Pyodide cannot load native-extension DB drivers like psycopg2; no persistent process model. Confirmed via Cloudflare's own docs/changelog (checked 2026-09-07).
- **Netlify** — dropped. No native Python function runtime (Python is a build-step language only); 10–30s function timeouts; no true background-worker product. Research explicitly characterized Django on Netlify as "a poor fit."

| Platform | CLI-first | Managed/Serverless | Agent-readable docs | Stable deploy API | MCP/Integration | Total |
|---|---|---|---|---|---|---|
| Render | Pass | Pass | Pass | Pass | Pass | 5 Pass |
| Railway | Pass | Pass | Pass | Pass | Partial | 4 Pass, 1 Partial |
| Fly.io | Pass | Partial | Pass | Pass | Pass | 4 Pass, 1 Partial |
| Vercel | Pass | Pass | Partial | Pass | Pass | 4 Pass, 1 Partial |

Notes per platform:
- **Render**: `render` CLI (v2.26.0) covers deploy, log tailing, `psql`, SSH one-off jobs; `render.yaml` Blueprints for IaC. Docs published as `render.com/llms.txt` and `llms-full.txt`. MCP server (GA, Aug 2025) ships a native Claude Code plugin.
- **Railway**: Nixpacks auto-detects Django, no Dockerfile required. `railway.com/llms.txt` confirmed live. MCP server exists (`railwayapp/railway-mcp-server`) but Railway's own docs don't label its maturity (GA/beta unstated) — scored Partial on that criterion.
- **Fly.io**: `flyctl` covers the full lifecycle; docs live as Markdown in the open-source `superfly/docs` repo. Scored Partial on "managed/serverless" because Postgres is mid-migration — the legacy unmanaged offering is deprecated, and the replacement (Fly Managed Postgres) is still rolling out region by region.
- **Vercel**: Django is officially, zero-config supported — not hard-filtered — but the execution model (stateless function, read-only filesystem outside `/tmp`, Hobby cron capped at 1 run/day) is structurally at odds with Django's assumptions. Reliable cron and longer functions require the $20/user/mo Pro tier, the most expensive option evaluated against a cost-minimizing preference.

### Shortlisted Platforms

#### 1. Render (Recommended)

Only platform to pass all five criteria. First-party Django guide (`render.com/docs/deploy-django`) covering `build.sh`, Gunicorn, WhiteNoise, and `DATABASE_URL` wiring. Native GA Cron Jobs (standard cron syntax, up to 12h runtime) are a direct fit for the PRD's link-expiry and GDPR-retention background work. MCP server ships a native Claude Code plugin, which is directly relevant to this project's agent-driven workflow.

#### 2. Railway

Near-tie with Render. Best-in-class co-located managed services — one-click Postgres/Redis/MongoDB templates on private networking, which best serves the "co-location preferred" interview answer. Cron jobs are GA but have a 5-minute minimum interval (not a real constraint for this project's link-expiry/retention cadence). The gap versus Render is the unstated maturity of its MCP server and no first-party Django-specific guide (relies on Nixpacks auto-detection + community templates instead).

#### 3. Fly.io

Strong CLI (`flyctl`) and GitHub-hosted Markdown docs, with an official Django support track (`fly launch` auto-detects Django). The gap versus Render/Railway: no free tier at all since October 2024, and the managed-Postgres story is actively mid-migration (legacy "Fly Postgres" deprecated, replacement "Managed Postgres" rolling out region by region) — a real risk against the "co-location preferred" and "single region is fine" answers if the target region isn't yet covered.

## Anti-Bias Cross-Check: Render

### Devil's Advocate — Weaknesses

1. Render's free-tier Postgres **expires after 30 days** (tightened from 90 days, changelog dated 2024-05-20) — for a project with a hard MVP deadline and ongoing organiser/participant data, staying on free tier past that window risks silent data loss.
2. Free web services **spin down after 15 minutes of idle** (tightened from 30 minutes, effective Sept 2025) — the first participant opening an access link after a quiet period eats a cold-start delay, directly risking the PRD's "suggested room within 2 seconds" NFR.
3. No first-party object storage — the hotel CSV uploads (FR-002) need external S3-compatible storage wired up from day one; Render doesn't provide this itself.
4. No Heroku-style "release phase" hook — migrations must be scripted into `build.sh` or run manually via Shell/one-off job, creating a real race risk between a new deploy's code and its schema.
5. Render Cron Jobs have no persistent disk and a 12-hour max runtime — sufficient for link-expiry sweeps today, but a constraint if a future retention job needs to process large exports to disk.

### Pre-Mortem — How This Could Fail

The team deployed StayRecon on Render's free tier to hit the two-week deadline without needing a credit card. The Postgres free tier's 30-day expiry wasn't on anyone's calendar — it was buried in a changelog entry, not surfaced during initial setup. Three weeks after the first live event, the free database was purged; a week's worth of bookings and the GDPR-retention audit trail were gone, with no automated backup because nobody had upgraded to a paid instance yet. Separately, the free web service's 15-minute spin-down meant early testers occasionally saw a blank or slow-loading booking page and assumed the product was broken, souring first impressions during the exact window the team needed positive word-of-mouth. By the time anyone upgraded to a paid plan, trust with the first pilot client organiser was already damaged, and the PRD's "reconciliation report is data-accurate" guardrail had already been silently violated once.

### Unknown Unknowns

- Render's pricing was **restructured in April 2026** (flat tiers replacing the old per-member Professional plan) — cost assumptions from older tutorials or blog posts may already be stale.
- The `render` CLI has no dedicated `rollback` verb; "rollback" means redeploying an older deploy, which behaves differently if a migration ran between the two deploys (the redeployed code may not match the current schema).
- Render's MCP server is recent (GA since August 2025) — the Claude Code plugin is unlikely to have deep community battle-testing yet; expect to hit undocumented edges during the deploy step.
- Render's free-tier Redis/Key-Value is **non-persistent** (data lost on restart) — if any future feature assumes Redis as a durability layer rather than pure cache, this is an easy trap.

**Decision**: proceed with Render, risks absorbed into the register below (primarily: skip free tier for anything beyond initial smoke-testing, and script migrations carefully into the deploy step).

## Operational Story

- **Preview deploys**: Render creates preview environments from PRs when enabled per-service in `render.yaml`; each preview gets its own URL and (optionally) its own ephemeral database. No extra protection layer by default — treat preview URLs as unauthenticated-reachable unless access control is added at the app layer.
- **Secrets**: Environment variables and secrets are set per-service in the Render dashboard or via `render.yaml` env groups; the `render` CLI can pull/push env vars for scripting. Not committed to the repo — matches the project's existing `.env`/`.env.*` gitignore convention.
- **Rollback**: No dedicated rollback command — redeploy an earlier deploy from the dashboard's deploy history or via `render deploys create` pointed at a prior commit. Caveat: if a migration ran between the two deploys, the redeployed code may not match the current schema — verify manually before rolling back across a migration boundary.
- **Approval**: Creating/deleting services, upgrading plans, and rotating the Postgres connection string are dashboard actions requiring a human. Routine deploys (`git push` → auto-deploy, matching the `ci_default_flow: auto-deploy-on-merge` hint already recorded in `tech-stack.md`) can run unattended once CI is wired up.
- **Logs**: `render logs` streams build/deploy/runtime logs from the CLI; the MCP server additionally exposes log/metrics reads as structured tool calls for an agent session, plus read-only SQL against the database.

## Risk Register

| Risk | Source | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| Free-tier Postgres expires after 30 days, silently deleting live data | Devil's advocate | M | H | Provision a paid Postgres instance before any real user data is created; do not rely on free tier past initial smoke-testing |
| Free-tier web service cold-starts after 15 min idle, breaking the 2s suggested-room NFR | Devil's advocate | H | M | Use a paid Starter instance (no spin-down) for any environment participants actually use |
| No first-party object storage for CSV/booking uploads | Devil's advocate | H | M | Wire an external S3-compatible bucket (e.g. Cloudflare R2, AWS S3) before FR-002 (CSV upload) ships |
| No release-phase hook — migration/deploy race risk | Devil's advocate | M | H | Script `migrate` explicitly and idempotently into `build.sh`, ahead of `collectstatic`, and monitor first request after each deploy |
| Render pricing restructured April 2026 — stale cost assumptions | Unknown unknowns | M | L | Re-check `render.com/pricing` before committing to a paid tier, don't trust older tutorials |
| Rollback via redeploy can desync code and schema across a migration boundary | Unknown unknowns | L | H | Treat any rollback that crosses a migration as a manual, schema-checked operation, not a one-click action |
| Render MCP server is new (GA Aug 2025); Claude Code plugin integration under-battle-tested | Unknown unknowns | M | L | Fall back to the `render` CLI directly if the MCP plugin misbehaves during the deploy step |
| Free-tier Redis/KV is non-persistent | Unknown unknowns | L | M | If Redis is added later, confirm it's used as pure cache, not a durability layer, or provision the paid tier |
| No Django app has been created yet; no `pyproject.toml`/`uv.lock` committed | Research finding | H | M | Resolve before deploying — Render's build step needs a resolvable dependency manifest (see Getting Started) |

## Getting Started

Specific to this project's actual state: a bare `django-admin startproject` scaffold (Django 6.1.1, Python 3.12.3), managed with `uv`, with **no `pyproject.toml`/`uv.lock` committed yet** (flagged as a Hard Rule in `AGENTS.md`) and no app created yet.

1. Pin the dependency set before deploying: `uv init --no-readme --python 3.12` (or manually add a `pyproject.toml`) then `uv add django==6.1.1 gunicorn whitenoise psycopg[binary]`, committing the resulting `pyproject.toml` and `uv.lock`.
2. Create `build.sh` that installs `uv` and syncs the locked environment, then runs Django's build steps: `curl -LsSf https://astral.sh/uv/install.sh | sh && uv sync --frozen && uv run manage.py collectstatic --no-input && uv run manage.py migrate`.
3. Set the start command to `uv run gunicorn stay_recon.wsgi:application`, and add WhiteNoise to `MIDDLEWARE` in `stay_recon/settings.py` for static files (Render has no default static-file CDN).
4. Move `SECRET_KEY`, `DEBUG`, and `ALLOWED_HOSTS` to environment variables read via `os.environ` in `settings.py` (already flagged as a Hard Rule in `AGENTS.md` — this is a prerequisite for any deploy, not optional).
5. Provision Render Postgres as a **paid** instance from the start (per the risk register above), wire `DATABASE_URL` via `dj-database-url`, and create a Render Cron Job for the link-expiry and GDPR-retention sweeps once those management commands exist.

## Out of Scope

The following were not evaluated in this research:
- Docker image configuration
- CI/CD pipeline setup (GitHub Actions wiring is a `tech-stack.md` hint, not yet implemented)
- Production-scale architecture (multi-region, HA, DR)
