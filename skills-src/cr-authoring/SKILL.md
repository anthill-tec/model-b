---
name: cr-authoring
description: Authoring and lifecycle conventions for CR (Change Request), PRD, and DN documents — spec structure, AC precision, filing a CR on the Crucible board (which holds the queue), waves, the release-is-not-a-CR boundary rule, and the CReq/CRes library-communication pattern. Triggers: CR, PRD, DN, acceptance criteria, spec, queue, CReq, CRes.
---

# CR / PRD / DN Authoring — the universal doc model

The matured cross-stack doc model, backported as the standard.
Stack-agnostic — Rust, Java/Quarkus, Bun/TS, Python, GitOps. Stack orchestration files
reference this skill; they do not restate it.

## Three document types — clear separation
| Doc | Lives in | Answers | Authority |
|---|---|---|---|
| **PRD** | `docs/research/PRD-*.md` | WHY + WHAT — the design contract | Authoritative design source. CRs cite it; never re-derive design. |
| **DN** (Design Note) | `docs/research/DN-*.md` | a design rationale / decision / spike larger than one CR | Where design reasoning, options-considered, open questions live. |
| **CR** (Change Request) | `docs/changes/CR-<PROJ>-NNN-*.md`, filed on the Crucible board (which holds the queue) | HOW at code level — the implementation contract | Execution scope only. Cites PRD/DN for design; hosts the precise spec + ACs. |

- **CRs implement; PRDs/DNs justify.** No design rationale, options-considered, or "what exists today" narrative in a CR. A CR carries a header line `**Design reference:** <PRD/DN path> §<section>` when it needs one.
- **Authorship (user directive 2026-07-03): the human user is the PRIMARY author of every document**; the orchestrator is CO-AUTHOR only (`**Author:** <user>` + `**Co-author:** <orchestrator id> (<role — project>)`). Never credit the orchestrator as sole/primary author.
- **Design gaps larger than current scope → a DN** (or PRD section), NOT a memory file, NOT inline CR prose.
- Legacy `Architecture.md`/`Implementation.md` remain fine for system overview + phase tracking, but design rationale belongs in PRDs/DNs and implementation specs in CRs — don't duplicate.

## Two-phase workflow (universal) + where work commits
- **Design phase → the integration branch (`develop`/`main`).** Gap analysis, then the spec pre-review; spec authoring, filing on the board, PRD/DN updates. No feature branch.
- **Execution phase → a feature branch.** RED+GREEN cycles, VERIFY, FIX, regression+merge.
- **Where an edit commits:** free-standing spec/PRD/DN/memory edits → integration branch. Edits **caused by** an in-flight CR's RED/GREEN/VERIFY (PRD revisions surfaced by RED, new DNs, corrections of defects against the CR's own contracts) → the **feature branch**, landing atomically with the implementation. Test: if the edit makes no sense without the implementation it's tied to, it's on the feature branch.

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
- **No `## Cycle Plan`** — cycle breakdown lives in the Crucible plan on the board, not the spec.
- **No `## Resolved design decisions` / `## Open questions`** unless the original spec had them — inline resolutions into the relevant scope section.
- **No version-number bumps** ("v1.1") inside the spec — git history is the version control; use date-stamped inline notes.
- No architectural-baseline / discovery narrative — that's PRD/DN material.
- **Front matter stays succinct (~6–8 lines).** No `file:line` "surfaces" blocks in the header — those go into the relevant `### §S` section (a short `**Surfaces (verified <date>):**` line). The `Design reference` line doubles as the gap-analysis pointer — name the exact PRD/DN + sections to read.

## Citing code — by symbol, never by line

- **Code is cited by symbol and file** — `` `handleCrPlan` (src/v2.ts) `` — never by `path:line`: a line number moves with every edit, a symbol does not. The rule holds in specs, PRDs, DNs, comments, docstrings and reports alike.

## CRs are TECHNICAL docs — no process pollution (RECURRING mistake)
Process, workflow, and rescheduling state never go in a CR file. FORBIDDEN in specs:
- `## Gap-analysis findings` report sections (DRIFT-N tables, dimension narratives) — spec CHANGES fold silently into Scope/ACs; the findings REPORT lives in chat + (if needed) a project-memory note.
- `## Close-out` cycle logs (commit hashes, agent names, verdicts, gate numbers, orchestrator identity).
- Decision/provenance labels inline in Scope (`DEC-A`, `DRIFT-3`, "user-decided") — state the requirement plainly; git carries provenance.
- Rescheduling narration ("moved from CR-X…") — each CR states only its CURRENT truth.
- Struck-through resolved risks — delete resolved items; keep live ones.

Where that content DOES go: a ruling to the PRD or a DN; a merge to `cr-close` and a milestone label on the board; a follow-up to a new CR filed on the board (see the queue idiom below); statuses to the board, derived; temporary orchestration state to project memory, pruned when the wave ships. New CRs are filed at the SCRUM between implementation runs — emergent requirements become new CRs filed on the board, not mid-implementation spec edits.

## CR IDs + canonical status
- IDs: `CR-<PROJ>-NNN`, unique **numeric**, never letter-suffixed. Allocate the next free number from the board's `queue` and the spec files in `docs/changes/` (see the queue idiom below).
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
A **CR has a design surface** (new types/API/architecture, PRD coupling) → spec + filed on the board + feature branch + RED/GREEN/VERIFY. A **task does not** (lint cleanup, dead code, dep bumps, doc typos, test hygiene) → just do it, no spec doc. Ask "does this need a spec doc?" — if no, it's a task.

## The CR queue — structure only (queue idiom, 2026-07-20)
The **Crucible board holds the queue** and every CR's execution state; `docs/changes/` holds the
specs. A CR is filed on the board with the queue verbs (flags and semantics: the `crucible`
skill's queue-verbs section) — never in a table in a file.
- **Filing a CR:** write the spec and commit it, then `cr-plan` (its title, release and wave),
  `cr-depends` (its whole dependency set), and `wave-sequence` with the wave's full order — the
  new CR placed among the CRs already in the wave, since each call replaces the whole set.
- **Allocating an id:** the next free number is allocated from the board's `queue` and the spec
  files in `docs/changes/` together — a number either one holds is taken.
- **Titles stay in parity:** a spec's H1 and its board title agree. When a spec's H1 changes,
  re-post its title with `cr-plan` in the same session. Measured 2026-09-21: a CR rewritten to
  drop one harness for another kept its old board title for three days because only the repo
  side was corrected.
- **Superseding and voiding:** `cr-supersede` moves a CR's work to its successor, `cr-void` ends
  a CR whose work is not happening, with the reason; the spec's `**Status:**` follows.
- **Statuses are DERIVED on the Crucible board** (plans / cycles / milestones), never
  hand-maintained in a spec or any other file.
- **Release membership is the user's call.** Never decide which release a CR belongs to (a
  priority may be proposed). In a project with no release yet, the first filing asks the user
  for a label and a target date and records it with `release-propose`, then files the CR into it.
- **Header slots:** Design contract, Evidence base and Ontology are lines of the project's
  `AGENTS.md`; the target release lives on the board, as the release's proposal.
- **Wave** = a **grouping of CRs** marking an execution boundary (solo: a redesign point between groups); its order is its `wave-sequence` on the board. Setup tasks and the release are NOT waves.
- **A release is NOT a CR** (user ruling 2026-09-21, correcting the earlier "release CR bundles the final gates" model). A release is a **boundary event**: the wave carrying it drains its queue on the board, a human approves starting it, it is executed per the `git-workflow` skill, and only then recorded. **Never author a release CR, never express "the wave must finish" as dependency edges on one, and never put the release procedure in a spec** — the procedure lives in `git-workflow` §Releases and is loaded at release time. Work the release genuinely needs (an archive mapping, a doc sweep) is an ordinary CR in the wave, named for what it builds.
- **Crucible absent:** filing is the spec file alone, with the id allocated from the spec files;
  the board steps are skipped, never imitated in a file.
- **Unregistered** (an empty `CRUCIBLE_PROJECT_KEY` in `.env`): do the Setup section of the root
  project's `AGENTS.md` first when it has one, and otherwise (a project scaffolded before the
  board held the queue) its README's setup tasks; then file.
- **A project scaffolded before the board held the queue** (its `docs/changes/` still carries a
  README table): the trigger is the board's `queue` missing a CR whose spec exists in
  `docs/changes/` with no merge recorded (no `cr-close`, the spec's `**Status:**` not
  `COMPLETED`). Only those CRs are filed, with `cr-plan`, `cr-depends` and `wave-sequence`; a CR
  `queue` already lists is never re-filed, and a wave's order is re-sent in full. The release is
  the user's call, with the README's Target release slot proposed as the default. The README then
  stays as history.

## Closing a CR
- **Board-tracked projects:** before the merge, the CR spec file's top `**Status:**` flip: `COMPLETED (shipped YYYY-MM-DD on <branch>)`. Date-only ship refs, never a merge-commit hash. After it, `cr-close --commit <merge sha> --agent <id>` closes the CR on the board (the board carries the status) and posts the `cr-merged` milestone; it takes the merge's sha, so it waits for the merge commit.
- **Where board-tracking is absent:** close-out is the spec's `**Status:**` flip alone, made on ship before the merge ceremony; the regression-merge diff touches the spec.

## Spec updates during execution — orchestrator authority vs VERIFY's
**A scope change found mid-implementation goes into a patch CR** (its own spec and ACs, filed on the board and sequenced after the parent with `cr-depends`), never an inline spec edit. On the feature branch the executing orchestrator edits its own CR's spec only for status and for defects against that CR's own contracts, plus an `## Implementation Notes` section (decisions, deferred items, follow-up pointers). Mainline never edits an IN_PROGRESS CR's spec on develop. The orchestrator MUST NOT touch the **AC checkboxes** (`- [ ]`) — those are **VERIFY's authority**; pre-marking short-circuits review. Deferred items needing a record → a follow-up CR/DN referenced from Implementation Notes.

## PRD conventions
- **Every PRD opens with front matter** (Version / Date / Status / Authors, Builds on / Related) followed by a `## Change Control` table, one row per revision.
- `docs/research/PRD-*.md` is the authoritative design contract. Read the relevant PRD section COMPLETELY before implementing a CR derived from it.
- A CR introducing a design concept not yet in the PRD: UPDATE the PRD section first, then cite it via `**Design reference:**`. Don't inline new design rationale in the CR.
- PRD revisions surfaced mid-cycle commit on the feature branch.
- **NO CR-breakdown section in a PRD** (user directive 2026-06-12) — decomposition into CRs is the orchestrator's recommendation, approved at wave-open, captured as CRs filed on the board, never pre-written into the design contract.

## DN conventions
- A DN captures a design decision/rationale/spike too large or cross-cutting for a single CR. Reference the DN from the CR(s) it informs.
- **Investigation sub-phase output is a findings document, NOT code edits** — write findings into the CR spec under a new `### S{N} Findings` section; code fixes ship in the subsequent implementation sub-phase.

## docs/ layout
```
docs/
  changes/
    CR-<PROJ>-NNN-<slug>.md    # one file per CR (flat; no feature-area subdirs) — specs only; the queue is on the board
  research/
    PRD-<topic>.md             # design contracts
    DN-<topic>.md              # design notes
```

## CReq/CRes — library ↔ consumer communication
For shared-library projects (INBOX/OUTBOX pattern: consumers write CReq to the library's
`Migration.md`, the library answers with CRes in `Implementation.md`):
see [references/creq-cres.md](references/creq-cres.md).
