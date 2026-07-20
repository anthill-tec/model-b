# CR / PRD / DN — Design & Implementation Doc Conventions (UNIVERSAL)

The matured doc model (evolved in the NAI project, backported as the cross-stack standard).
Stack-agnostic — applies to Rust, Java/Quarkus, Bun/TS, GitOps. Stack files
(`rust-orchestration.md`, `java-orchestration.md`) reference this; do not restate it there.

## Three document types — clear separation
| Doc | Lives in | Answers | Authority |
|---|---|---|---|
| **PRD** (Product/Project Requirements) | `docs/research/PRD-*.md` | WHY + WHAT — the design contract | Authoritative design source. CRs cite it; they never re-derive design. |
| **DN** (Design Note) | `docs/research/DN-*.md` | a design rationale / decision / spike larger than one CR | Where design reasoning, options-considered, and open questions live. |
| **CR** (Change Request) | `docs/changes/CR-<PROJ>-NNN-*.md` + `docs/changes/README.md` queue | HOW at code level — the implementation contract | Execution scope only. Cites PRD/DN for design; hosts the precise spec + ACs. |

- **CRs implement; PRDs/DNs justify.** No design rationale, options-considered, or "what exists today" narrative in a CR — those go in the PRD or a DN. A CR carries a header line `**Design reference:** <PRD/DN path> §<section>` when it needs one.
- **Authorship (user directive 2026-07-03): the human user is the PRIMARY author of every document** (PRD/DN/CR and any other doc); the orchestrator is CO-AUTHOR only. Front matter: `**Author:** <user>` + `**Co-author:** <orchestrator id> (<role — project>)`. Never credit the orchestrator as sole/primary author.
- **Design gaps / issues larger than current scope → a DN** (or a PRD section), NOT a memory file and NOT inline CR prose.
- Relationship to legacy `Architecture.md` / `Implementation.md`: those remain fine for system overview + phase/status tracking, but **design rationale belongs in PRDs/DNs** and **implementation specs belong in CRs** — don't duplicate.

## Two-phase workflow (universal) + where work commits
- **Design phase → the integration branch (`develop`/`main`).** Gap analysis, spec authoring, queue/PRD/DN updates. No feature branch.
- **Execution phase → a feature branch.** RED+GREEN cycles, VERIFY, FIX, regression+merge.
- **Where an edit commits:** free-standing spec/PRD/DN/queue/memory edits → the integration branch. Edits **caused by** an in-flight CR's RED/GREEN/VERIFY (PRD revisions surfaced by RED, new DNs, AC tightening, error-shape changes) → the **feature branch** (land atomically with the implementation). Test: if the edit makes no sense without the implementation it's tied to, it's on the feature branch.

## CR spec structure — DO NOT invent sections
Standard order:
1. **Front matter** — `**Status:**`, `**Type:**` (feature | maintenance | bugfix | docs — MUST mirror the schedule-DB `cr_type`; user directive 2026-07-03), `**Priority:**`, `**Depends on:**`, `**Labels:**`, `**Phase:**`, optional `**Design reference:**`.
2. `## Context` — background, current defects.
3. `## Scope` with `### §S1`, `### §S2`, … — one sub-section per deliverable.
4. `## Acceptance criteria` — a checklist per §S.
5. `## Estimated size`.
6. `## Risk` (or `## Risks / open questions`).
7. `## Non-goals` / `## Out of scope`.

Rules:
- **No `## Cycle Plan` section** — cycle breakdown lives in the orchestrator's task list, not the spec.
- **No `## Resolved design decisions` / `## Open questions`** unless the original spec already had them — inline resolutions into the relevant scope section.
- **No version-number bumps** ("v1.1", "v2.0") inside the spec — git history is the version control; add date-stamped inline notes where decisions change.
- No architectural-baseline / discovery / "what exists today" narrative — that's PRD/DN material.
- **Front matter stays succinct (~6–8 lines):** `Status` / `Priority` / `Depends on` / `Labels` / `Phase` / a ONE-LINE `Design reference`. Do NOT pile verified `file:line` "surfaces" blocks or mechanism detail into the header — those go into the relevant `### §S` Scope section (a short `**Surfaces (verified <date>):**` line per section). The `Design reference` line doubles as the track's **gap-analysis pointer** — name the exact PRD/DN + sections the track must read.

## CRs are TECHNICAL docs — no process pollution (user directive; a RECURRING orchestrator mistake)
A CR is the implementation contract a future reader uses to understand WHAT shipped. **Process,
workflow, and rescheduling state never go in a CR file.** Specifically FORBIDDEN in CR specs:
- `## Gap-analysis findings` report sections (DRIFT-N tables, dimension narratives). Gap-analysis
  SPEC CHANGES are folded silently into Scope/ACs in plain technical wording; the findings REPORT
  lives in the chat message to the user + (if needed across sessions) a project-memory note.
- `## Close-out` cycle logs (per-cycle commit hashes, agent names, VERIFY verdicts, gate/coverage
  numbers, orchestrator identity). Closing a CR = the two status edits ("Closing a CR" below), no more.
- Decision/provenance labels inline in Scope (`DEC-A`, `DRIFT-3`, "user-decided", "verified at
  gap-analysis") — state the requirement plainly; git history carries provenance.
- Rescheduling narration ("moved from CR-X by decision Y", "pulled forward from …") — each CR states
  only its CURRENT truth.
- Struck-through resolved risks narrating their own resolution — delete resolved items; keep live ones.

**Where that content DOES go:**
- **`docs/changes/README.md` (the queue) IS the process doc** — and it carries each CR's
  **process-control state for the CR's whole life once filed**: the status transitions
  (`PENDING → IN_PROGRESS → COMPLETED`/`SUPERSEDED`/`DEFERRED`), dependency edges, wave membership,
  ordering, and scheduling notes (scope moved between CRs, fold-ins, supersessions, user-approved
  breaking changes — in the wave footer notes). When process state about a CR needs recording, the
  queue row/footer is the home, never the CR file.
- **New CRs are filed at the SCRUM between implementation runs** (the deferred-items triage in
  `orchestration-mainline.md`) — emergent requirements become new queue entries there, not
  mid-implementation spec edits.
- **Project memory** holds orchestration state for the orchestrator itself (implementation log:
  cycle commits, gate numbers, verdicts; the deferred-items register) — as TEMPORARY notes, pruned
  once their purpose is served (e.g. when the wave ships).

## CR IDs + canonical status
- IDs: `CR-<PROJ>-NNN`, unique **numeric**, never letter-suffixed (no `-160a`). Allocate the next free number — check the queue first.
- **Canonical states (text, not emoji):** `PENDING` / `IN_PROGRESS` / `COMPLETED` / `SUPERSEDED` / `DEFERRED`. Use `COMPLETED`, never `DONE`/`COMPLETE`. (Emoji are optional decoration only; the canonical NAME is the text state.)

## ACs are precise testing gates (MANDATORY)
Each AC must be directly translatable to a test assertion — exact field names/types/numbers, exact enum variant names + values, exact method signatures, exact observable outcomes. Test: *"Can I write the assertion directly from this AC?"* If no, it's too vague.
- **Packaging/artifact ACs are verified by BUILDING the artifact and inspecting its contents** (build
  the wheel/jar/tarball, open it, assert the members) — never by parsing build-config keys. A static
  config assertion can pass while the package is unbuildable.
- BAD: "StreamSchema message defined." GOOD: "StreamSchema has `type_name: string` at field 1 and `fields: repeated FieldSchema` at field 2."
- BAD: "CheckpointAction enum defined." GOOD: "CheckpointAction has `COMMIT=0` and `ROLLBACK=1` (exactly 2 variants)."

## Integration ACs are MANDATORY for any API-additive CR (non-negotiable)
Unit-only ACs ship half-features: the API exists, the unit test constructs it, the test passes, the CR is marked COMPLETED — and production never calls the API. For **every** new public method/function/type/config field, ship:
1. **Unit AC** — the API exists, behaves, has the right signature.
2. **Integration requirement** — names the EXACT production path that will invoke it: "After this CR, `<file>:<fn>` invokes `<API>` with `<actual data source>`." If no production path will call it in this CR, file a stub-only CR or defer the API.
3. **Integration test** — exercises the PRODUCTION DATA PATH (construct the real entry point, drive data, observe the API fired). MUST NOT construct the new API directly (that's a unit test).
4. **Caller-existence AC (mechanically auditable)** — a grep that returns ≥1 non-test caller by VERIFY time. Zero non-test callers ⇒ stub ⇒ not complete. VERIFY runs the grep itself.

## CR vs task — do NOT file cleanup as a CR
A **CR has a design surface** (new types/API/architecture, PRD coupling — something a reviewer must understand before the code lands) → warrants a spec + queue row + feature branch + RED/GREEN/VERIFY cycles. A **task does not** (lint cleanup, dead-code removal, dep bumps, doc typos, test hygiene) → just do it (inline or as a queue task), no spec doc. Ask "does this need a spec doc?" — if no, it's a task.

## Closing a CR — TWO files, always
On ship (before the merge ceremony, never after): (1) `docs/changes/README.md` queue row → `COMPLETED` + shipped-date; (2) the CR spec file's top `**Status:**` → `COMPLETED (shipped YYYY-MM-DD on <branch>)`. Use **date-only** ship refs, never a merge-commit hash (unknowable pre-finish). The regression-merge diff must touch BOTH files.

## Spec updates during execution — orchestrator authority vs VERIFY's
The orchestrator MAY add (on the feature branch): a dated scope-reconciliation note, an `## Implementation Notes` section (decisions, PRD refs, deferred items + follow-up CR pointers), inline annotations. The orchestrator MUST NOT touch the **AC checkboxes** (`- [ ]`) — those are **VERIFY's authority** (VERIFY checks ACs against the code and renders the verdict; pre-marking short-circuits review). Don't invent status conventions. Deferred items needing a record → a follow-up CR/DN referenced from Implementation Notes.

## PRD conventions
- `docs/research/PRD-*.md` is the authoritative design contract. Read the relevant PRD section COMPLETELY before implementing a CR derived from it.
- When a CR introduces a design concept not yet in the PRD (a new lifecycle state, error class, wire format): UPDATE the PRD section first, then the CR cites it via `**Design reference:**`. Don't inline new design rationale in the CR.
- PRD revisions surfaced mid-cycle commit on the feature branch (see "where work commits").
- **NO CR-breakdown section in a PRD** (user directive 2026-06-12: "don't predict and capture CR
  breakdown — you cannot presuppose the implementation"). The PRD is the design contract (WHY + WHAT);
  the decomposition into CRs is the ORCHESTRATOR'S RECOMMENDATION, presented dynamically to the user at
  wave-open, approved there, and then captured in the TRACKING docs (queue rows + footer) — never
  pre-written into the design contract.

## DN conventions
- `docs/research/DN-*.md` captures a design decision/rationale/spike too large or cross-cutting for a single CR. Reference the DN from the CR(s) it informs.
- **Investigation sub-phase output is a findings document, NOT code edits** — write findings directly into the CR spec under a new `### S{N} Findings` section (not a separate companion file); code fixes ship in the subsequent implementation sub-phase.

## docs/ layout
```
docs/
  changes/
    README.md                 # the CR queue — single source of truth; pick next PENDING by phase + deps
    CR-<PROJ>-NNN-<slug>.md    # one file per CR (flat; no feature-area subdirs)
  research/
    PRD-<topic>.md            # design contracts
    DN-<topic>.md             # design notes
```
