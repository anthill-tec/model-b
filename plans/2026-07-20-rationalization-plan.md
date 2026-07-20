# Claude Memory Rationalization — Model B unification, dynamic skill tree, AXI migration

## Context

`~/.claude` grew organically into 24 memory files (7 orphaned from the index), ~50 skills, 29 agent definitions, and ~20 scripts. Three audits (memory duplication, Crucible-2 doc drift, skills/agents inventory) found:

- `CLAUDE.md` is a **symlink to `AGENTS.md`** — one 621-line file is both the always-loaded config AND the "lean" sub-agent procedure, so every session and every dispatched sub-agent ingests all of it.
- The Model B workflow model has **no canonical home**: `plan_b_workflow_model.md` is a broken mis-paste (verbatim copy of `project-management.md` L1–95); the real definition is scattered across `orchestration-common/mainline/track`, `sandesh.md`, and four skills. Naming is split "Plan B" vs "Model-B".
- Two legacy redirect shims (`agent-baseline.md`, `orchestration-universal.md`) have 5+ dangling inbound refs; **17 agents still cite the legacy alias**.
- Crucible 2 doc drift: the `crucible` skill claims clients emit a TOON-AXI envelope (they don't — TOON is server-side only); `agent-protocol` documents a phantom `/agents/heartbeat` endpoint + nonexistent `heartbeat.sh`; `java-orchestration.md` uses dead `/api/ingest/*` paths. **vscode has no crucible client** (skill hand-rolls inline Python); **arduino has only `unit`/`compile`**.
- Per-stack duplication: fix/verify agents are 52–54% verbatim-identical across small stacks; rust (470–814 lines) and vscode agents are bespoke outliers.
- MCP holdouts: mail cluster (Fastmail/Gmail/Calendar via `mail-tracking-core`), sandesh message verbs (wake + admin already CLI), lean-ctx (already dual). `sys-toolbox-mcp` referenced by nothing.
- `~/.claude` is **chezmoi-managed**; the documented workflow covers only add/apply — **no delete/rename procedure**, so deletions resurrect on next `chezmoi apply`. Must fix first.

**User decisions (locked):**
1. Scope: everything, phased with review gates.
2. Per-stack agents/skills: **generated from templates** + per-stack parameter files kept in this repo (`model-b`, formerly `claude-optimization`).
3. MCP holdouts: **docs + AXI CLI contract only**; server rewrites happen in their own repos.
4. Legacy files: **archive in this repo, then delete via chezmoi**.
5. Canonical name: **Model B** (all "Plan B" occurrences renamed).
6. Lagging Crucible clients: **build both** (new `vscode-crucible.py`, extend `arduino-crucible.py`).
7. AXI envelope: **upgrade clients** to emit the TOON-AXI envelope (verb, ok, counts, `warnings[]`, `help`) so the skill's contract becomes true.
8. Memory: **big reference docs stay as memory files**; procedural content moves to skills.
9. **Language/stack references are NOT skills** — a skill's description leaks into every project's session. Stack refs stay in `memory/`; stack-scoped skills and per-project CLAUDE.md files reference them, containing context per project.
10. **CLAUDE.md is ALWAYS a symlink to AGENTS.md** (lavish review) — no de-symlink. One frugal ~100-line core file serves both entrypoints; the sub-agent procedure moves to `model-b` references.
11. **Crucible V2 plan/cycle verbs are universal API** (lavish review) — `bun-crucible.py` is the reference implementation; ALL stack clients adopt the same API + AXI standards. `worktree-flow.py` also migrates to AXI output. Verified live on :3849 — `/api/v2/plans` active (TOON via `?fmt=toon`), `/agents/heartbeat` 404 (phantom confirmed), `/api/ingest/*` 404 (dead paths confirmed).

## Target architecture

### Always-loaded core (frugal)
- `AGENTS.md` — THE core file, rewritten to ~100 lines: non-negotiables as one-liners (no attribution, import hygiene, TDD, clean-build-before-commit, destructive-op confirmation, lean-ctx preference) + the **topic → skill/memory trigger table** + project-classification pointers.
- `CLAUDE.md` — **stays a symlink → AGENTS.md** (always; decision 10).
- The universal sub-agent procedure (worktree boundary, Crucible lifecycle, TDD steps, report-every-run, scope, quality — today's AGENTS.md tail) moves to `model-b/references/sub-agent-procedure.md`, loaded by dispatched agents.

### Dynamic tree (three loading tiers)
1. Skill descriptions (global list, per-session cost) — kept lean and stack-neutral.
2. `SKILL.md` bodies — load on keyword trigger, parameterized by args (stack, role).
3. Skill `references/` + `memory/` reference library — read only when the loaded skill routes to them; stack content contained per project.

### Skills (global = workflow-scoped, stack-neutral descriptions)
- **`model-b` (NEW)** — canonical Model B definition, role-parameterized (`mainline` | `track` | `solo`). Absorbs: `orchestration-common/mainline/track.md`, rewritten Model B overview (replacing broken `plan_b_workflow_model.md`), single- vs multi-track variation, `sandesh.md` usage, AND the universal sub-agent procedure as reference files. `bootstrap`/`shutdown`/`code-health`/`status-report` repoint here.
- **`crucible` (REWRITE)** — stack-parameterized; absorbs `crucible-report-{rust,java,bun,python,vscode}` (5 skills), `agent-protocol` skill, `memory/crucible-ingest.md`. Documents the REAL per-stack CLI surfaces (incl. bun's plan/cycle verbs, rust's clippy/smoke/workspace gates) + the TOON-AXI envelope contract. Heartbeat = the `register` verb; phantom `/agents/heartbeat` + `heartbeat.sh` removed.
- **`cr-authoring` (NEW)** — from `cr-prd-dn-conventions.md` + CR/CReq/CRes half of `project-management.md` + AC-precision rules from old CLAUDE.md. Companions `gap-analysis`/`check-cr-close` unchanged.
- **`git-workflow` (REWRITE skill)** — absorbs `memory/git-workflow.md` + `memory/git-multi-account.md` procedural content. `git-flow-release`/`git-flow-develop-gitops` stay.
- **`chezmoi` (NEW)** — rewritten from `chezmoi-integration.md`: add/apply + **delete/rename/forget procedure** + refreshed inventory.
- Deleted skills: `crucible-report-*` ×5, `agent-protocol`, `bun-red-testing`, `bun-green-testing`, `bun-regression-testing`, `quarkus-regression-testing` (content → `crucible` skill + generated agents).

### memory/ end-state (reference library only, loaded per-project)
Keep: `java-modern-syntax.md`, `java-coding-standards.md` (trimmed of modern-syntax overlap), `java-testing-practices.md` (absorbs `devops-environment.md`), `maven-best-practices.md` (trimmed of release overlap), `quarkus-patterns.md`, `rust-orchestration.md` + `java-orchestration.md` (stack mechanics, endpoints fixed, repointed to model-b/AGENTS.md), `convex-client-server.md`, `operational-commands.md` (trimmed; hand-rolled curl-ingest removed).
Delete (content relocated per above): `agent-baseline.md`, `orchestration-universal.md`, `orchestration-common/mainline/track.md`, `plan_b_workflow_model.md`, `crucible-ingest.md`, `QUICK_REFERENCE.md`, `git-workflow.md`, `git-multi-account.md`, `devops-environment.md`, `chezmoi-integration.md`, `stack-detection.md` (routing → crucible/model-b), `cr-prd-dn-conventions.md`, `project-management.md` (split: CR content → cr-authoring; practices → CLAUDE.md one-liners), `sandesh.md` (→ model-b references).

### Workspace structure (this repo — the STANDING workshop, per lavish review)
This repo (`~/Documents/side_projects/model-b`) is the permanent authoring workspace: as Crucible V2 and Model B evolve, changes are authored here first, then built/synced into the chezmoi source and applied to `~/.claude`. Single-source rule: generated or contract-derived files are authored here (chezmoi source is a deployment target for them); hand-authored one-offs (bespoke agents, big memory refs) keep the classic edit-in-place → `chezmoi add` flow.
```
model-b/
├── audits/                      # audit reports + re-audit snapshots (drift watch)
├── contracts/                   # AXI contracts — the evolution interface
│   ├── crucible-envelope.md     #   TOON-AXI envelope + universal verb set (incl. plan/cycle) — tracks Crucible V2
│   ├── sandesh-cli.md           #   message-verb CLI spec (implemented in sandesh repo)
│   ├── mail-axi.md              #   Fastmail/Gmail/Calendar CLI spec
│   └── lean-ctx.md              #   CLI-preference contract
├── generator/
│   ├── templates/{red,green,verify,fix}.md.tmpl   # SE principles written ONCE
│   ├── stacks/{arduino,bun,python,quarkus}.yaml   # test cmd, crucible client, gotchas, memory refs
│   └── build.py                                   # emit into chezmoi source; --check = drift gate
├── skills-src/                  # authored sources of maintained skills (model-b, crucible, cr-authoring, git-workflow, chezmoi)
├── archive/                     # legacy content + mapping.md (old path → new home)
├── scripts/                     # sync + verification (chezmoi round-trip, grep gates, token budget)
├── plans/                       # wave plans + close-out reports
└── .lavish/                     # review artifacts
```
Generated: arduino/bun/python/quarkus × red/green/verify/fix (16 agents). Bespoke kept: rust ×4, vscode ×4, electronics ×4, `inbox-analyst`. ALL agents repointed `memory/agent-baseline.md` → `AGENTS.md`.

### Scripts / AXI wave
- `bun-crucible.py` is the **reference implementation** for the Crucible V2 client API (decision 11); all clients converge on it.
- Shared envelope helper (e.g. `scripts/axi_envelope.py`): TOON-AXI envelope on stdout for all `*-crucible.py` clients (verb, ok, counts, `warnings[]`, `help` next-step).
- ALL clients gain the universal plan/cycle verbs (`plan-file`, `cycle-activate`, `cycle-done`, `cr-close`) against `/api/v2/plans` (verified live).
- NEW `vscode-crucible.py`: register/unregister, `test --tests`, `regression --coverage`, `check` (tsc), auto-ingest, pre-merge-gate, plan verbs; Vitest+Mocha JUnit + lcov → `/api/v2/runs/parsed`, tsc → `/runs/compile`.
- EXTEND `arduino-crucible.py`: regression, auto-ingest, check, pre-merge-gate, plan verbs (as applicable to firmware flow).
- `worktree-flow.py` migrates to AXI output: TOON envelope for `status`/`next`/`finish` + machine-readable lane boards.
- `hw-crucible.py` stays a shim to anthill-forge (`forge crucible …`); the forge client must conform to the same V2 API + envelope contract.
- Universal verb aliases added where missing (keep stack-specific extras; no breaking renames).
- `contracts/`: crucible-envelope spec, sandesh message-verb CLI spec (send/reply/fetch/inbox/addressbook/register/unregister), `mail-axi` spec (Fastmail+Gmail+Calendar), lean-ctx CLI-preference note.

## Waves (review gate after each — lavish recap)

- **Wave 0 — Safety rails**: `git init` this repo; `archive/` scaffold + record chezmoi source commit hash; write + validate the chezmoi delete/rename procedure on a scratch file (prove a deletion survives `chezmoi apply`).
- **Wave 1 — Core split**: rewrite `AGENTS.md` as the frugal ~100-line core (CLAUDE.md symlink KEPT); move sub-agent procedure → model-b references; mechanically repoint ALL inbound refs (17 agents, `rust-orchestration.md` L3, `java-orchestration.md` L3, `cr-prd-dn-conventions.md` ~L63, old core L70/L73/L354); delete both shims.
- **Wave 2 — Model B + consolidation**: `model-b`, `crucible` rewrite, `cr-authoring`, `git-workflow` merge, `chezmoi` skill; memory merges/deletes; "Plan B"→"Model B" sweep (incl. `agent-protocol`→crucible merge, bootstrap/shutdown/code-health wording).
- **Wave 3 — Generator**: build generator + stack params; regenerate 16 agents; side-by-side diff review vs originals; install via chezmoi; wire `build.py --check` as drift gate (hook into `skill-release-gate.py`).
- **Wave 4 — Tooling/AXI**: envelope helper; align ALL clients to the bun-crucible reference API (plan/cycle verbs + envelope); `vscode-crucible.py`; arduino extension; worktree-flow AXI migration; final crucible-skill envelope docs; `contracts/` specs.
- **Wave 5 — Close-out**: `archive/mapping.md`; chezmoi source commits; full verification.

## Verification

- **Token budget**: always-loaded set 621 lines → ≤100 lines single AGENTS.md core (`wc -l` + token estimate) — measure before/after.
- **Chezmoi round-trip**: `chezmoi diff` clean after apply; deleted files STAY deleted after a fresh `chezmoi apply`.
- **Grep gates** (zero hits outside `archive/`): `agent-baseline.md`, `orchestration-universal.md`, `Plan B`, `/api/ingest/`, `heartbeat.sh`, `/agents/heartbeat`.
- **Crucible smoke** per stack: client `register → test → unregister` against `localhost:3849` in a sample project; envelope parses; run visible server-side.
- **Generator**: `build.py --check` idempotent (second run = no diff); generated agent frontmatter valid.
- **Skill loads**: `/model-b`, `/crucible <stack>`, `/cr-authoring`, `/chezmoi` load and every referenced memory/reference path exists.

## Critical files (representative)

- `~/.claude/CLAUDE.md`, `~/.claude/AGENTS.md` (de-symlink + rewrite)
- `~/.claude/memory/*` per end-state table above
- `~/.claude/skills/{model-b,crucible,cr-authoring,git-workflow,chezmoi}/SKILL.md` (+ references/)
- `~/.claude/agents/*.md` (16 regenerated, 17 repointed)
- `~/.claude/scripts/{axi_envelope.py,vscode-crucible.py,arduino-crucible.py,rust-crucible.py,mvn-crucible.py,bun-crucible.py,python-crucible.py}`
- `~/.local/share/chezmoi/**` (every change mirrored; deletions via chezmoi source)
- This repo: `generator/`, `contracts/`, `archive/`
