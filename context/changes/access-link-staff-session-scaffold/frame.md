# Frame Brief: PRD ambiguity about staff login vs. access-link

> Framing step before /10x-plan. This document captures what is *actually*
> at issue, separated from what was initially assumed.

## Reported Observation

FR-004 (`prd.md:62`) says the organiser "generates a unique access link per participant and per staff member" — the same mechanism, same verb, used for both roles. Access Control (`prd.md:106`) says event staff "login with a staff role, scoped to a single event at a time" — a login/session framing, explicitly distinct from participant's "no account" wording (`prd.md:105`). The PRD never states how these two descriptions connect.

## Initial Framing (preserved)

- **User's stated cause or approach**: This looked like the PRD conflated two different access models (link-based vs. login-based) for the staff role, rather than deliberately designing one hybrid mechanism.
- **User's proposed direction**: Resolve which reading is correct before `/10x-plan` commits to one of two mutually exclusive staff-session design options.
- **Pre-dispatch narrowing**: User confirmed "one must be wrong/imprecise" (not two steps of one flow) and "plan with a stated assumption, revisit if wrong" (doesn't need to fully block planning — needs a well-justified default).

## Dimension Map

1. **Chronology** — one wording was written earlier and never reconciled with a later addition
2. **Cross-reference consistency** — do the other staff-related FRs (FR-003, FR-011–013) and the existing Open Question lean toward login or link-only access?  ← where the tension first surfaced
3. **Terminology precision** — was "login" used with the same precision for staff as it was for organiser/participant?
4. **Product-logic/accountability** — do the actual stated requirements (scoping, the FR-012/FR-005 precedence question) need a persistent staff identity, or would a link satisfy them equally?

## Hypothesis Investigation

| Hypothesis | Evidence | Verdict |
| --- | --- | --- |
| 1. One wording added later, never reconciled (temporal) | Both `shape-notes.md` and `prd.md` land in a single commit (`0c00f90`, same day) — no version history to show authorship order. The inconsistency already exists **within `shape-notes.md` itself**, between its own "auth model" gray-area decision (`shape-notes.md:16-17`) and its own FR-004 draft (`shape-notes.md:83`) — not something `prd.md` introduced. | WEAK as stated (no temporal evidence) — but reframes cleanly as "never cross-checked," not "added later" |
| 2. Cross-reference: other staff FRs lean toward link-only (B) | FR-003 (`prd.md:60`), FR-011 (`:81-82`), FR-012 (`:83-84`), FR-013 (`:85-86`) are all silent on staff identity/attribution — none require knowing *which* staff member acted. The Open Question's proposed fallback (`prd.md:120`, "last-write-wins") is timestamp-based, not identity-based. 4 of 5 checked signals lean B or neutral; only the Access Control sentence itself leans A. | WEAK-TO-MIXED, tilts B by volume |
| 3. Terminology precision: "login" as precise as other roles' wording | Organiser's bullet names 3 concrete methods ("email/password, OAuth, or passwordless") and says "full account." Participant's bullet is maximally explicit ("no account," "access link/token"). Staff's bullet names no mechanism at all and never says "account" either way — independent analysis: "moderate confidence (60/40) toward imprecise/ambiguous over intentionally a real account." | WEAK, leans toward "loose wording" |
| 4. Product-logic: do stated requirements actually need persistent staff identity (A) over a link (B)? | Non-Goals (`prd.md:114`) explicitly defer the audit trail: "edits aren't logged for v1" — and FR-005's own Socratic note (`prd.md:65`) names exactly the capability Option A would buy ("who changed what") as out of scope. The precedence Open Question is phrased role-vs-role ("organiser and event staff"), never individual-vs-individual. FR-004's "per staff member" already gives each staff person a distinct *token*, which doesn't require a durable account. **Every stated FR is satisfiable by Option B**; Option A would build attribution capability the PRD explicitly excludes. | STRONG for B |

## Narrowing Signals

- The single strongest textual signal for Option A — the word "login" plus "(not a cross-event account)" — was independently assessed as *likely imprecise*, given the same author wrote "no account" explicitly for participants two lines earlier but never wrote "account" (either way) for staff.
- The PRD's own Non-Goals directly excludes the one capability (per-actor accountability/audit trail) that would justify Option A's added complexity — this is the most decisive single piece of evidence, because it's not inference about wording, it's an explicit scope decision already on record.
- Chronology investigation reframed the origin story usefully: this isn't "the PRD drifted between two documents," it's "one shaping-phase decision (auth model) and one FR draft (FR-004) were never cross-checked against each other" — a process gap, not a deliberate hybrid design.

## Cross-System Convention

This project's own convention, seen elsewhere in the PRD (e.g. the FR-012/FR-005 precedence question, `prd.md:120`), is to flag unresolved gaps as explicit **Open Questions** rather than silently resolving them one way. This frame follows that same convention: state the better-evidenced reading as the plan's working assumption, but flag the "login" wording as a PRD note worth a one-line clarification — consistent with how this project already handles this class of ambiguity, not inventing a new process.

## Reframed (or Confirmed) Problem Statement

> **The actual problem to plan around is**: F-02's staff mechanism should be planned as a link/token-scoped session (Option B) — the same class of mechanism as participants, reusing F-02's participant-token infrastructure — because every concrete staff-related FR and the PRD's own explicit audit-trail deferral are fully satisfied by it, while Option A (real `User` + `StaffAssignment` login) would build persistent-identity/attribution capability the PRD explicitly excludes from v1. The word "login" in Access Control is best read as imprecise reuse of the term to mean "gains authorized access," not a deliberate requirement for credentialed accounts.

This isn't "the PRD is unresolvably ambiguous, planning is blocked" — it's "the PRD has one imprecise word sitting against a clear pattern of concrete requirements that all point the same way." The plan should proceed on Option B as a documented, well-justified assumption, and separately flag the "login" wording as worth a one-line PRD clarification (not a blocking decision).

## Confidence

**MEDIUM** — the product-logic evidence (Non-Goals excluding audit trail) is strong and explicit, and three of four independent investigation angles converge on Option B. But this ultimately turns on human authorial intent behind one ambiguous word ("login"), which textual analysis can narrow but not fully settle with certainty. Recommend: state Option B as the plan's explicit assumption, and add a one-line PRD clarification note so this doesn't stay silently ambiguous for the next person who reads FR-004 or Access Control.

## What Changes for /10x-plan

`/10x-plan` should plan the staff-session mechanism as Option B (session/link-scoped, no persistent `User`/`StaffAssignment` model) by default, state this as an explicit assumption in the plan's Current State Analysis or Key Discoveries, and treat it as the same class of primitive as the participant token mechanism (likely sharing a data model, per the research's Open Question 3 about token-creation ownership). It should NOT spend planning effort designing a `StaffAssignment`/real-login flow unless the user overrides this assumption.

## References

- Research: `context/changes/access-link-staff-session-scaffold/research.md`
- Source: `context/foundation/prd.md:60-65,81-86,100-106,114,120` (FR-003/004/005/011/012/013, Access Control, Non-Goals, Open Questions)
- Source: `context/foundation/shape-notes.md:16-17,51-58,83-84` (auth-model gray-area decision, Access Control, FR-004 draft)
