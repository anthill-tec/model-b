---
name: cr-authoring
description: Authoring and lifecycle conventions for CR (Change Request), PRD, and DN documents — spec structure, AC precision, the structure-only CR queue, waves, the release-is-not-a-CR boundary rule, and the CReq/CRes library-communication pattern. Triggers: CR, PRD, DN, acceptance criteria, spec, queue, CReq, CRes.
---

# CR / PRD / DN Authoring — the universal doc model

The matured cross-stack doc model (evolved in the NAI project, backported as the standard).
Stack-agnostic — Rust, Java/Quarkus, Bun/TS, Python, GitOps. Stack orchestration files
reference this skill; they do not restate it.

## Three document types — clear separation
| Doc | Lives in | Answers | Authority |
|---|---|---|---|
| **PRD** | `docs/research/PRD-*.md` | WHY + WHAT — the design contract | Authoritative design source. CRs cite it; never re-derive design. |
| **DN** (Design Note) | `docs/research/DN-*.md` | a design rationale / decision / spike larger than one CR | Where design reasoning, options-considered, open questions live. |
| **CR** (Change Request) | `docs/changes/CR-<PROJ>-NNN-*.md` + `docs/changes/README.md` queue | HOW at code level — the implementation contract | Execution scope only. Cites PRD/DN for design; hosts the precise spec + ACs. |

- **CRs implement; PRDs/DNs justify.** No design rationale, options-considered, or "what exists today" narrative in a CR. A CR carries a header line `**Design reference:** <PRD/DN path> §<section>` when it needs one.
- **Authorship (user directive 2026-07-03): the human user is the PRIMARY author of every document**; the orchestrator is CO-AUTHOR only (`**Author:** <user>` + `**Co-author:** <orchestrator id> (<role — project>)`). Never credit the orchestrator as sole/primary author.
- **Design gaps larger than current scope → a DN** (or PRD section), NOT a memory file, NOT inline CR prose.
- Legacy `Architecture.md`/`Implementation.md` remain fine for system overview + phase tracking, but design rationale belongs in PRDs/DNs and implementation specs in CRs — don't duplicate.

## Two-phase workflow (universal) + where work commits
- **Design phase → the integration branch (`develop`/`main`).** Gap analysis, spec authoring, queue/PRD/DN updates. No feature branch.
- **Execution phase → a feature branch.** RED+GREEN cycles, VERIFY, FIX, regression+merge.
- **Where an edit commits:** free-standing spec/PRD/DN/queue/memory edits → integration branch. Edits **caused by** an in-flight CR's RED/GREEN/VERIFY (PRD revisions surfaced by RED, new DNs, AC tightening) → the **feature branch**, landing atomically with the implementation. Test: if the edit makes no sense without the implementation it's tied to, it's on the feature branch.

## CR spec structure — DO NOT invent sections
Standard order:
1. **Front matter** — `**Status:**`, `**Type:**` (feature | maintenance | bugfix | docs — MUST mirror the schedule-DB `cr_type`), `**Priority:**`, `**Depends on:**`, `**Labels:**`, `**Phase:**`, optional `**Design reference:**`.
2. `## Context` — background, current defects.
3. `## Scope` with `### §S1`, `### §S2`, … — one sub-section per deliverable.
4. `## Acceptance criteria` — a checklist per §S.
5. `## Estimated size`.
6. `## Risk` (or `## Risks / open questions`).
7. `## Non-goals` / `## Out of scope`.

Rules:
- **No `## Cycle Plan`** — cycle breakdown lives in the orchestrator's task list / board, not the spec.
- **No `## Resolved design decisions` / `## Open questions`** unless the original spec had them — inline resolutions into the relevant scope section.
- **No version-number bumps** ("v1.1") inside the spec — git history is the version control; use date-stamped inline notes.
- No architectural-baseline / discovery narrative — that's PRD/DN material.
- **Front matter stays succinct (~6–8 lines).** No `file:line` "surfaces" blocks in the header — those go into the relevant `### §S` section (a short `**Surfaces (verified <date>):**` line). The `Design reference` line doubles as the gap-analysis pointer — name the exact PRD/DN + sections to read.

## CRs are TECHNICAL docs — no process pollution (RECURRING mistake)
Process, workflow, and rescheduling state never go in a CR file. FORBIDDEN in specs:
- `## Gap-analysis findings` report sections (DRIFT-N tables, dimension narratives) — spec CHANGES fold silently into Scope/ACs; the findings REPORT lives in chat + (if needed) a project-memory note.
- `## Close-out` cycle logs (commit hashes, agent names, verdicts, gate numbers, orchestrator identity).
- Decision/provenance labels inline in Scope (`DEC-A`, `DRIFT-3`, "user-decided") — state the requirement plainly; git carries provenance.
- Rescheduling narration ("moved from CR-X…") — each CR states only its CURRENT truth.
- Struck-through resolved risks — delete resolved items; keep live ones.

Where that content DOES go: the queue (structure + dated footer Notes — see queue idiom below), the tracking board (statuses), project memory (temporary orchestration state, pruned when the wave ships). New CRs are filed at the SCRUM between implementation runs — emergent requirements become new queue entries, not mid-implementation spec edits.

## CR IDs + canonical status
- IDs: `CR-<PROJ>-NNN`, unique **numeric**, never letter-suffixed. Allocate the next free number — check the queue first.
- **Canonical states (text, not emoji):** `PENDING` / `IN_PROGRESS` / `COMPLETED` / `SUPERSEDED` / `DEFERRED`. Use `COMPLETED`, never `DONE`/`COMPLETE`.

## ACs are precise testing gates (MANDATORY)
Each AC must be directly translatable to a test assertion — exact field names/types/numbers, exact enum variant names + values, exact method signatures, exact observable outcomes. Test: *"Can I write the assertion directly from this AC?"* If no, it's too vague.
- **Packaging/artifact ACs are verified by BUILDING the artifact and inspecting its contents** — never by parsing build-config keys.
- BAD: "StreamSchema message defined." GOOD: "StreamSchema has `type_name: string` at field 1 and `fields: repeated FieldSchema` at field 2."
- BAD: "CheckpointAction enum defined." GOOD: "CheckpointAction has `COMMIT=0` and `ROLLBACK=1` (exactly 2 variants)."

## Integration ACs are MANDATORY for any API-additive CR (non-negotiable)
Unit-only ACs ship half-features. For **every** new public method/function/type/config field, ship:
1. **Unit AC** — the API exists, behaves, has the right signature.
2. **Integration requirement** — names the EXACT production path: "After this CR, `<file>:<fn>` invokes `<API>` with `<actual data source>`." No production caller in this CR → file a stub-only CR or defer the API.
3. **Integration test** — exercises the PRODUCTION DATA PATH (real entry point, drive data, observe the API fired). MUST NOT construct the new API directly.
4. **Caller-existence AC (mechanically auditable)** — a grep returning ≥1 non-test caller by VERIFY time. Zero non-test callers ⇒ stub ⇒ not complete. VERIFY runs the grep itself.

## CR vs task — do NOT file cleanup as a CR
A **CR has a design surface** (new types/API/architecture, PRD coupling) → spec + queue row + feature branch + RED/GREEN/VERIFY. A **task does not** (lint cleanup, dead code, dep bumps, doc typos, test hygiene) → just do it, no spec doc. Ask "does this need a spec doc?" — if no, it's a task.

## The CR queue — structure only (queue idiom, 2026-07-20)
`docs/changes/README.md` is the queue; it holds **structure only**:
- **Row columns: CR / Title / Wave / Depends on.** Nothing else — no status column, no plan/open-plan/closed+merge bookkeeping in rows.
- **A row's title and its spec's H1 must agree — and so must the TRACKING BOARD's registered title.** Measured 2026-09-21: a CR rewritten to drop one harness for another kept its old board title for three days because the repo side was corrected and the board side was not, and the board is the authority for queue status. Where a board read-verb cannot echo titles, the parity is re-posted rather than read; either way it is checked when a spec's subject changes, not only at release.
- **Statuses are DERIVED on the Crucible board** (plans / cycles / milestones), never hand-maintained in the queue.
- **Release membership is the user's call.** Never decide which release a CR belongs to — file it at the queue default; the user sets membership (a priority may be proposed).
- **Header slots:** `Design contract` / `Evidence base` / `Ontology` / `Target release`.
- **Dated footer `Notes`** — scheduling notes, scope moves, fold-ins, supersessions, user-approved breaking changes (dated lines).
- **Release-boundary row** — a row marking the release boundary in the ordering.
- **Wave** = a **grouping of CRs** marking an execution boundary (solo: a redesign point between groups). Setup tasks and the release are NOT waves.
- **A release is NOT a CR** (user ruling 2026-09-21, correcting the earlier "release CR bundles the final gates" model). A release is a **boundary event**: the wave carrying it drains its queue, a human approves starting it, it is executed per the `git-workflow` skill, and only then recorded. **Never author a release CR, never express "the wave must finish" as dependency edges on one, and never put the release procedure in a spec** — the procedure lives in `git-workflow` §Releases and is loaded at release time. Work the release genuinely needs (an archive mapping, a doc sweep) is an ordinary CR in the wave, named for what it builds.

## Closing a CR
- **Board-tracked projects:** close via `cr-close` (board carries the status); the CR spec file's top `**Status:**` flip stays: `COMPLETED (shipped YYYY-MM-DD on <branch>)`. Date-only ship refs, never a merge-commit hash.
- **Where board-tracking is absent (legacy two-file close-out):** on ship, before the merge ceremony: (1) queue row → `COMPLETED` + shipped-date; (2) the spec's `**Status:**` flip. The regression-merge diff must touch BOTH files.

## Spec updates during execution — orchestrator authority vs VERIFY's
The orchestrator MAY add (on the feature branch): a dated scope-reconciliation note, an `## Implementation Notes` section, inline annotations. The orchestrator MUST NOT touch the **AC checkboxes** (`- [ ]`) — those are **VERIFY's authority**; pre-marking short-circuits review. Deferred items needing a record → a follow-up CR/DN referenced from Implementation Notes.

## PRD conventions
- **Every PRD opens with front matter** (Version / Date / Status / Authors, Builds on / Related) followed by a `## Change Control` table, one row per revision.
- `docs/research/PRD-*.md` is the authoritative design contract. Read the relevant PRD section COMPLETELY before implementing a CR derived from it.
- A CR introducing a design concept not yet in the PRD: UPDATE the PRD section first, then cite it via `**Design reference:**`. Don't inline new design rationale in the CR.
- PRD revisions surfaced mid-cycle commit on the feature branch.
- **NO CR-breakdown section in a PRD** (user directive 2026-06-12) — decomposition into CRs is the orchestrator's recommendation, approved at wave-open, captured in the TRACKING docs (queue + board), never pre-written into the design contract.

## DN conventions
- A DN captures a design decision/rationale/spike too large or cross-cutting for a single CR. Reference the DN from the CR(s) it informs.
- **Investigation sub-phase output is a findings document, NOT code edits** — write findings into the CR spec under a new `### S{N} Findings` section; code fixes ship in the subsequent implementation sub-phase.

## docs/ layout
```
docs/
  changes/
    README.md                  # the CR queue — structure only; pick next PENDING by phase + deps
    CR-<PROJ>-NNN-<slug>.md    # one file per CR (flat; no feature-area subdirs)
  research/
    PRD-<topic>.md             # design contracts
    DN-<topic>.md              # design notes
```

## CReq/CRes — library ↔ consumer communication
For shared-library projects (INBOX/OUTBOX pattern: consumers write CReq to the library's
`Migration.md`, the library answers with CRes in `Implementation.md`):
see [references/creq-cres.md](references/creq-cres.md).
