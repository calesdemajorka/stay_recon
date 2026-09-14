# Test Plan

> Phased test rollout for this project. Strategy is frozen at the top
> (§1–§5); cookbook patterns at the bottom (§6) fill in as phases ship.
> Read before writing any new test.
>
> Refresh: re-run `/10x-test-plan --refresh` when stale (see §8).
>
> Last updated: 2026-09-14

## 1. Strategy

Tests follow three non-negotiable principles for this project:

1. **Cost × signal.** The cheapest test that gives a real signal for the
   risk wins. Do not promote to e2e because e2e "feels safer." Do not put a
   vision model on top of a deterministic visual diff that already catches
   the regression.
2. **User concerns are first-class evidence.** Risks anchored in "the team
   is worried about X, and the failure would surface somewhere in area Y"
   carry the same weight as PRD lines or hot-spot data.
3. **Risks are scenarios, not code locations.** This plan documents *what
   could fail* and *why we believe it's likely* — drawn from documents,
   interview, and codebase *signal* (churn, structure, test base). It does
   NOT claim to know which line owns the failure. That knowledge is
   produced by `/10x-research` during each rollout phase. If the plan and
   research disagree about where the failure lives, research is the
   ground truth.

Hot-spot scope used for likelihood weighting: `accounts/`, `events/`,
`rooms/`, `stay_recon/`, `templates/` (excludes `.venv`, migrations,
build output).

## 2. Risk Map

The top failure scenarios this project must protect against, ordered by
risk = impact × likelihood. Risks are failure scenarios in user / business
terms, not test names. The Source column cites the evidence that surfaced
this risk — never a specific file as "where the failure lives."

| # | Risk (failure scenario) | Impact | Likelihood | Source (evidence — not anchor) |
|---|--------------------------|--------|------------|----------------------------------|
| 1 | A room gets booked to two participants at once under concurrent access, violating the product's core no-double-allocation guarantee | High | High | PRD Success Criteria Guardrails + US-01 acceptance criteria; interview Q1 ("worries most"), Q2 ("burned before — race condition on write"), Q4 ("biggest gap — concurrency/race paths") |
| 2 | An organiser's password-reset email silently fails to deliver, locking them out with no visible error | High | High (confirmed live) | `context/archive/2026-09-11-organiser-auth-app-scaffold/plan.md` (documents Render free-tier SMTP port block); open GitHub issue #15 |
| 3 | One organiser's event, room, or participant data is reachable by another organiser, or by the wrong participant/staff access link | High | Medium | PRD Access Control (Organiser, Participant, Event staff sections); interview Q3 (`stay_recon/urls.py`/`settings.py` named as the low-confidence area every new app wires into); archived F-01/S-01/S-02 plans' recurring 404-not-403 object-scoping pattern |
| 4 | Two near-simultaneous CSV uploads/confirms for the same event interleave and corrupt the saved room list | High | Medium | Interview Q1/Q2/Q4 concurrency theme applied to `csv-upload-room-mapping`'s (S-02) just-shipped wipe-and-replace flow; PRD data-accuracy guardrail |
| 5 | The rooms-used-vs-booked reconciliation report is inaccurate, leading the organiser to dispute or overpay a real hotel invoice | High | Medium | PRD Success Criteria Guardrails ("reconciliation report is data-accurate"); roadmap S-09 risk note ("this is the guardrail deliverable") |
| 6 | Booking-window/change-cap boundary conditions misfire — a 4th change is allowed, or a change lands after the window closed | Medium | Medium | Roadmap S-05 risk note ("off-by-one on the 3rd change") and S-06 risk note ("participant tab open exactly at the boundary") |

### Risk Response Guidance

| Risk | What would prove protection | Must challenge | Context `/10x-research` must ground | Likely cheapest layer | Anti-pattern to avoid |
|------|------------------------------|-----------------|----------------------------------------|-------------------------|--------------------------|
| #1 | Two overlapping requests for the same room resolve to exactly one success and one clean "no longer available" response, backed by a DB-level guarantee, not just application logic | That a DB unique constraint alone prevents this — it doesn't, unless the check-then-act sequence is atomic (locked or constrained) with the availability read | The exact write path S-04 will use (select-then-assign vs. constraint-first), and whether it runs inside one transaction | integration (Django `TransactionTestCase` + real concurrent requests) | Implementation mirror — asserting "no exception raised" instead of asserting the second writer actually lost |
| #2 | A reset request that can't actually deliver the email surfaces a real, observable failure (logged, or a distinct response) rather than returning success identically to a working send | That HTTP 200 from the reset view means the email sent — Django's own security convention returns success regardless of whether the address exists, so success ≠ delivery | How the current mail backend is configured, and whether Resend delivery failure is currently observable anywhere (logs, response, admin) | integration (mock the mail backend to simulate delivery failure) | Asserting only the HTTP status code, which the view already returns identically on both success and failure by design |
| #3 | For every organiser-scoped view across `accounts`, `events`, `rooms` (and future access-link routes), a request for another user's object returns 404, never 200 or a redirect leaking existence | That the existing 404-scoping pattern is applied to every view, not just the ones already tested — new views are exactly where this regresses | The full current list of organiser-facing views and whether each already uses the `get_object_or_404(..., organiser=request.user)` pattern | integration (one parametrized test sweep per app) | Testing only the views known to already be correct, rather than sweeping the full view list including the newest ones |
| #4 | Two near-simultaneous confirm requests for the same event's CSV upload leave the room table in one consistent, complete state — never partial, never double-applied | That the existing atomic delete+`bulk_create` test (which forces a single mocked failure) also proves safety under two real concurrent requests — it doesn't; that's a different failure class | Whether `PendingUpload`'s per-(organiser, event) unique constraint or the confirm view itself is the actual serialization point under concurrency | integration (`TransactionTestCase` + two threads/connections hitting confirm) | Reusing the existing single-request atomicity test as if it covered concurrency |
| #5 | A report generated from a known set of check-in and booking fixture rows exactly matches hand-computed expected totals, including a walk-in and a no-show | That "checked in" and "used" mean the same thing — the PRD ties invoicing accuracy to rooms *actually used*, which may diverge from booked or checked-in counts | The finalized data model connecting `Room`, booking, and check-in records once S-08 lands | integration, once S-08/S-09 exist | Copying the report's own aggregation logic into the test as the expected value (oracle problem) instead of computing expected totals independently from fixtures |
| #6 | The 3rd change succeeds, a 4th is rejected server-side regardless of client state; a change submitted after window-close is rejected regardless of when the page was loaded | That the cap and window are enforced client-side or via a value the client can replay — both must be re-checked server-side on every write | The server-side source of truth for change-count and window boundary once S-05/S-06 exist | unit + integration | Testing the cap/window only at exactly the boundary the implementation itself defines, not an independently reasoned boundary |

## 3. Phased Rollout

Each row is a discrete rollout phase that will open its own change folder
via `/10x-new`. Status moves left-to-right through the values below; the
orchestrator updates Status as artifacts appear on disk. Phases 1–3 are
sequenced first because they are testable against code that exists today;
Phases 4–5 trail the roadmap slices whose features they test.

| # | Phase name | Goal (one line) | Risks covered | Test types | Status | Change folder |
|---|------------|-------------------|-----------------|--------------|----------|------------------|
| 1 | Authorization & scoping contract | Sweep every existing organiser-scoped view for the 404-not-403 object-scoping pattern, establishing a reusable contract test future apps must satisfy | #3 | integration | change opened | `context/changes/testing-authorization-scoping-contract/` |
| 2 | Concurrent-write races | Prove the CSV upload/confirm replace flow is safe under two real concurrent requests, establishing the concurrency-test pattern Phase 4 reuses for booking | #4 | integration (`TransactionTestCase`) | not started | — |
| 3 | Password-reset failure visibility | Make email-delivery failure observable instead of silently identical to success | #2 | integration | not started | — |
| 4 | Booking-window & allocation guardrails | Defend the no-double-allocation guarantee and the change-cap/window boundaries once S-04/S-05/S-06 exist | #1, #6 | integration (`TransactionTestCase`), unit | not started | — |
| 5 | Reconciliation accuracy | Prove report totals match independently-computed expected values from fixture data, once S-08/S-09 exist | #5 | integration | not started | — |

**Status vocabulary** (fixed — parser literals): `not started` →
`change opened` → `researched` → `planned` → `implementing` → `complete`.

## 4. Stack

| Layer | Tool | Version | Notes |
|-------|------|---------|-------|
| unit + integration | Django `TestCase` (built-in unittest-based runner) | Django 6.1.1 | `uv run manage.py test`; no pytest — matches the existing `accounts/tests.py`, `events/tests.py`, `rooms/tests.py` convention |
| concurrency / race tests | Django `TransactionTestCase` + stdlib `threading` | Django 6.1.1 | `TestCase` wraps each test in one transaction, which hides real races; `TransactionTestCase` commits for real and allows genuine concurrent connections — required for Phases 2 and 4 |
| mail-backend mocking | Django's `django.core.mail.outbox` (locmem backend) | Django 6.1.1 | Built-in, no third-party mocking library needed for Phase 3 |
| e2e | none yet — see Phase 4 | — | Browser/e2e tooling selection and wiring is Module 4 scope per this project's own lesson boundaries; Phase 4 uses Django integration tests as the interim gate on the booking critical path |
| accessibility | not scoped | — | No PRD/NFR signal currently calls for automated a11y testing |
| AI-native | not included this rollout | — | Interview Q5 explicitly excluded template/markup testing and admin views from budget; no critical screen was named as needing multimodal review |

**Stack grounding tools (current session):**
- Docs: none available in current session (no Context7 or framework-docs MCP connected); checked: 2026-09-14
- Search: none available in current session (no Exa or web-search MCP connected); `WebSearch`/`WebFetch` exist as fallback tools but were not needed; checked: 2026-09-14
- Runtime/browser: none connected (no Playwright/browser-automation MCP); not used — e2e tooling deferred to Module 4; checked: 2026-09-14
- Provider/platform: Render MCP connected — used this session for read-only deploy/GitHub-issue verification (confirmed issue #15); relevant to future quality-gate wiring (deploy status, log inspection); checked: 2026-09-14

## 5. Quality Gates

| Gate | Where | Required? | Catches |
|------|-------|------------|---------|
| unit + integration (`uv run manage.py test`) | local | required (54 tests already passing) | logic regressions |
| authorization contract sweep | local + CI | required after §3 Phase 1 | cross-organiser/cross-participant data exposure |
| concurrency race tests | local | required after §3 Phase 2 | double-write / double-allocation races |
| pre-prod smoke on Render | between merge + prod | recommended, informal | environment-specific failures — matches the curl-based live-verification pattern already used before each `/10x-implement` manual gate |

Lint/typecheck and CI-pipeline wiring are out of this rollout's scope — no
phase above currently owns them, and authoring CI YAML from scratch is
reserved for Module 1 Lesson 5 / Module 2 Lesson 5 per this project's
`CLAUDE.md`.

## 6. Cookbook Patterns

How to add new tests in this project. Each sub-section is filled in once
the relevant rollout phase ships; before that, the sub-section reads
"TBD — see §3 Phase N."

### 6.1 Adding a unit test

- **Location**: `<app>/tests.py` — one file per app (no `tests/` package split yet).
- **Naming**: `class <Area>Tests(TestCase)`, methods `test_<scenario>`.
- **Reference test**: `rooms/tests.py` (`RoomModelTests`, `PendingUploadModelTests`).
- **Run locally**: `uv run manage.py test <app>`.

### 6.2 Adding an integration test (view-level)

- **Location**: same `<app>/tests.py` file, typically a `*ViewTests(TestCase)` class.
- **Object-scoping pattern**: any organiser-scoped view test must include a
  case where a second organiser's client requests the first organiser's
  object and asserts 404 — see `rooms/tests.py`'s "another organiser's
  event/data returns 404" tests for the canonical shape.
- **Reference test**: `rooms/tests.py` (`CSVUploadViewTests`, `PreviewConfirmViewTests`).
- **Run locally**: `uv run manage.py test <app>`.

### 6.3 Adding a concurrency/race test

- TBD — see §3 Phase 2. Will document the `TransactionTestCase` + `threading`
  pattern once the CSV-replace race test ships.

### 6.4 Adding an e2e test

- TBD — see §3 Phase 4. Tooling selection deferred to Module 4.

### 6.5 Per-rollout-phase notes

(Filled in as each phase lands — a 2-3 line note on anything surprising the
phase taught.)

## 7. What We Deliberately Don't Test

- **Django admin views** — auto-generated CRUD, framework-tested, low blast
  radius, not user-facing. Re-evaluate if admin becomes a primary organiser
  workflow. (Source: Phase 2 interview Q5.)
- **Template/HTML markup and CSS details** — fragile snapshot-style
  assertions that break on cosmetic changes and catch nothing real.
  Re-evaluate if a critical screen's rendering correctness itself becomes a
  named risk. (Source: Phase 2 interview Q5.)

## 8. Freshness Ledger

- Strategy (§1–§5) last reviewed: 2026-09-14
- Stack versions last verified: 2026-09-14
- AI-native tool references last verified: 2026-09-14 (none included this rollout)

Refresh (`/10x-test-plan --refresh`) when:

- a new top-3 risk surfaces from the roadmap or archive,
- a recommended tool's `checked:` date is older than three months,
- the project's tech stack changes (new framework, new test runner),
- §7 negative-space no longer matches what the team believes.
