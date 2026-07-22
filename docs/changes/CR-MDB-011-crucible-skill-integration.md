# CR-MDB-011 — crucible skill integration: route to Crucible-bundled skill docs

**Status:** COMPLETED
**Type:** docs
**Priority:** P1 (final-contract sync; last doc CR before the 014/013 execution arc)
**Depends on:** CR-MDB-003, CR-MDB-009 (external dependency DELIVERED: CR-CRU-030 #1330 + CR-CRU-036 #1332, crucible develop `949a2f4`)
**Labels:** crucible, skills, contracts, axi
**Phase:** Wave 3
**Design reference:** PRD §D7 (delivery status + rescope 2026-07-22) · `contracts/crucible-envelope.md` TRACKS header · queue note 2026-07-22

## Context

CR-CRU-030 + CR-CRU-036 shipped the final client contract: fleet-wide TOON-AXI envelope via shared `_crucible_axi.py`; **`WORKFLOW_CYCLE_ID` removed** — clients resolve the open plan's single `status:"active"` cycle FROM THE SERVER (`resolve_attach_cycle`) and auto-attach; no active cycle on an open plan ⇒ `no-active-cycle` warning + WITHHOLD (ok:false, non-zero exit, no run posted); tolerant when no open plan; plan verbs + `pre-merge-gate` + `regression --coverage` fleet-wide incl. arduino; `pre-merge-gate` STREAMS. Crucible now also BUNDLES + maintains per-stack skill docs at `crucible:clients/skills/crucible-report-*/` (+ `crucible-register`, `agent-protocol`).

**Rescope (user 2026-07-22):** Model B never re-documents their surfaces — the local `crucible` skill INTEGRATES and ROUTES to the bundled docs, keeping only Model B workflow deltas.

**Consumer constraint (gap-analysis):** 22 agent definitions + `refactorer-rust`/`refactorer-java` reference `crucible/references/{rust,java,bun,python,vscode}.md` — these paths MUST keep resolving; the files become thin routers, never deleted.

**Authoring model (user 2026-07-22, supersedes §S6 as first written): ALL work happens on a REPO-LOCAL copy — `skills-src/crucible/` (baseline imported from the deployed CR-MDB-003 state). `~/.claude` is NEVER written by this CR; deploying the updated skill into user space is EXCLUSIVELY the universal installer's job (014). No chezmoi step.**

## Scope

### §S1 — AC gate tests (RED first)
Amend `tests/test_crucible_skill.py` + `tests/test_contracts.py` to the FINAL contract (sanctioned test edits: 009/003 gates pin the superseded "incoming/REFUSED-400" anchors); add the new assertions in §AC. Wrapper-run with wave-3 cycle context.

### §S2 — `skills-src/crucible/SKILL.md` sync (repo-local copy)
(a) Workflow-classification section: DELETE the `WORKFLOW_CYCLE_ID` row/mandate; document server-driven cycle attach + `no-active-cycle` warn/withhold semantics + tolerance without an open plan; the orchestrator's only cycle input is `cycle-activate`. `WORKFLOW_CYCLE` (label) / `WORKFLOW_WAVE` / `WORKFLOW_ROLE` survive. (b) Envelope section: SHIPPED (stdout TOON envelope, stderr human line, `warnings[]` always present); drop "INCOMING"/CR-024-refusal text. (c) Plan verbs: universal fleet-wide. (d) Per-stack table: ADD arduino row (full surface); vscode row keeps its "no client" marker (upstream unscheduled) but routes to bundled `crucible-report-vscode`; every Reference cell routes to the bundled skill. (e) Routing note: `crucible:clients/skills/crucible-report-*/` is the per-stack authority (managed + updated by Crucible; deployed placement arrives with Crucible's installer, invoked by 014).

### §S3 — `skills-src/crucible/references/{rust,java,bun,python,vscode}.md` → thin routers
Each keeps ONLY Model B deltas (wrapper usage, agent naming, project-vendored client-path rule) + routes to its `crucible-report-<stack>` bundle. Zero `WORKFLOW_CYCLE_ID` occurrences. Paths unchanged (consumer constraint).

### §S4 — `contracts/crucible-envelope.md` mirror sync
Status → DELIVERED (CR-CRU-030 + 036, `949a2f4`). Envelope = current state. Classification context: `cycleId` is server-resolved (`resolve_attach_cycle`); replace the `no-cycle-id`/CR-024-refusal sections with the `no-active-cycle` + withhold semantics. Plan verbs fleet-wide. Zero `WORKFLOW_CYCLE_ID`.

### §S5 — wrapper + project conventions
Recreate `/tmp/claude-1000/modelb-crucible` post-036 (project key + agent-id derivation + optional `WORKFLOW_CYCLE` label/`WORKFLOW_WAVE`; NO cycle-id injection); update the repo `AGENTS.md` wrapper sentence to match.

### §S6 — user-space invariant (replaces the original chezmoi step)
`~/.claude` is untouched by this CR — `chezmoi diff` stays clean on `~/.claude/skills/crucible/`; deployment of the `skills-src/crucible/` copy rides the installer (014). Additionally (user directive): every client-path mention routes to the Crucible repo's own `clients/` directory — zero `~/.claude/scripts` + crucible pairings in the authored copy.

## Acceptance criteria

- [ ] AC1: zero `WORKFLOW_CYCLE_ID` occurrences under `skills-src/crucible/` (SKILL.md + all references) and in `contracts/crucible-envelope.md`.
- [ ] AC2: SKILL.md contains `no-active-cycle`, "withhold", and `cycle-activate` named as the orchestrator's only cycle input.
- [ ] AC3: SKILL.md contains `clients/skills/crucible-report-` (bundled-doc route) and an `arduino-crucible.py` row.
- [ ] AC4: each of the five `references/*.md` contains `crucible-report-` (its bundle route); `references/vscode.md` keeps a "no client" marker.
- [ ] AC5: `contracts/crucible-envelope.md` contains `resolve_attach_cycle` and `no-active-cycle` and "DELIVERED"; the REFUSED/400 rule is gone.
- [ ] AC6: all five `skills-src/crucible/references/{stack}.md` files exist (the deployed `~/.claude` paths keep resolving untouched until 014 deploys — consumer constraint, 22 agents + 2 refactorer skills).
- [ ] AC7: repo `AGENTS.md` wrapper sentence no longer claims `WORKFLOW_CYCLE_ID` injection.
- [ ] AC8: `~/.claude` untouched — `chezmoi diff` clean on `~/.claude/skills/crucible/`; zero `~/.claude/scripts`+crucible client-path mentions in `skills-src/crucible/`.
