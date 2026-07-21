# Model B — CR queue

**Project:** Model B (acronym: MDB · solo orchestrator: `vidushi-mdb`) · **Crucible projectKey:** `019f7eb8-8cad-7000-9838-854eca8e7c20` · **Design contract:** `docs/research/PRD-model-b-rationalization.md` · **Evidence base:** `audits/2026-07-20-*.md` + `docs/research/DN-rationalization-plan-review.md` · **Ontology:** `crucible:docs/research/DN-model-b-language.md` · **Target release:** 0.1.0
Conventions (naming, agentIds, workflow rules) live in the project `AGENTS.md` — not here.

Queue rows enumerate the whole delivery (structure only). **Live status lives on the Crucible board** (plans/cycles/milestones — we file every run and transition there); `Type` lives in each spec's front matter. Pick the next CR by wave + `Depends on` against the board. Spec files are authored at wave-open.

## Queue

| CR | Title | Wave | Depends on |
|---|---|---|---|
| CR-MDB-001 | Core split: frugal AGENTS.md + procedure relocation + shim removal | 1 | — |
| CR-MDB-002 | model-b skill body: orchestration trio + sandesh + canonical definition + universal conventions (PRD §D3) | 2 | 001 |
| CR-MDB-003 | crucible skill rewrite: real client surfaces, absorb report skills + agent-protocol | 2 | 001 |
| CR-MDB-004 | cr-authoring skill: cr-prd-dn-conventions + project-management split | 2 | 001 |
| CR-MDB-005 | git-workflow + chezmoi skills: memory-twin merges + delete/rename procedure | 2 | 001 |
| CR-MDB-006 | Memory model: global→project-level migration (D5) — only language refs stay global; merges + deletions | 2 | 002, 003, 004, 005 |
| CR-MDB-007 | "Plan B" → "Model B" naming sweep across skills + memory | 2 | 002 |
| CR-MDB-008 | Agent generator: role templates + stack params + build.py --check gate; regenerate 16 agents | 3 | 002, 006 |
| CR-MDB-009 | contracts/: crucible-envelope mirror, sandesh-cli, mail-axi, lean-ctx specs | 3 | — |
| CR-MDB-010 | worktree-flow.py AXI output: TOON envelope for status/next/finish + lane boards | 3 | 009 |
| CR-MDB-011 | crucible skill final docs: shipped client surfaces (fleet envelope, vscode, arduino, plan verbs) | 3 | 003, 009 + EXTERNAL (Crucible deliveries, thread #1322) |
| CR-MDB-013 | Model B scaffold CLI (`modelb-axi init`): project initializer per PRD §D10 | 3 | 002, 008 |
| CR-MDB-014 | Universal installer + packaging: deploy user-local files per targeted harness (DN → implementation) | 3 | 013 |
| CR-MDB-015 | Harness-agnostic hooks: neutral schema + per-harness emitters + shared script protocol (DN-harness-agnostic-hooks) | 3 | 013 |
| CR-MDB-012 | Release 0.1.0: full verification suite (PRD §4) + archive/mapping.md + master tag | — | 006, 007, 008, 010, 011, 013, 014 |

**— v0.1.0 ships here —** (release CR bundles the final gates; no close-out wave)

## Setup tasks (pre-wave — not a wave; a wave is a grouping of CRs)

- [x] `git init` + `git flow init` (master/develop; on develop) — 2026-07-20
- [x] Workspace scaffold — 2026-07-20
- [x] Persist the three audit reports into `audits/` — 2026-07-20
- [x] Register project in Crucible (`Model B`, key above) — 2026-07-20
- [x] Record chezmoi source baseline commit → `archive/BASELINE.md` — 2026-07-20
- [x] Prove chezmoi delete round-trip on a scratch file — PASSED 2026-07-20 (see `archive/BASELINE.md`)

## External dependency (Wave 3)

ALL `*-crucible.py` client implementation is CRUCIBLE's (requested #1325; answered #1326). DELIVERED (#1330, 2026-07-21): CR-CRU-030 merged — fleet-wide TOON-AXI conversion (bun/python/rust/mvn/arduino) via shared `_crucible_axi.py` + `toon.py`; streaming `pre-merge-gate`. INBOUND: CR-CRU-036 removes `WORKFLOW_CYCLE_ID` (server-resolved active cycle, warn+withhold on none) and closes the fleet coverage gap (rust/mvn/arduino `pre-merge-gate` + `regression --coverage`); Crucible intimates on merge. NEW vscode client still its own unscheduled CR. CR-MDB-011 documents the shipped surfaces AFTER 036 lands (final contract; avoids a double sync), intimations threaded under #1322.

## Footer notes

- 2026-07-20 — Queue opened; wave plan + 11 design decisions locked via lavish review; PRD filed. Structural waves (1–3) run with no other live orchestrator sessions.
- 2026-07-20 — Crucible-client ownership corrected: never Model B's; requested of Crucible (#1325 superseding erroneous #1324); their scheduling answer recorded (#1326).
- 2026-07-20 — Naming standard set (header). CR-MB-001 → CR-MDB-001 (spec, branch, Crucible plan 15; plan 14 superseded, both plans now closed at merge `4fd2fca`).
- 2026-07-20 — CR-MDB-001 shipped: RED 3/11/14 → GREEN 14/14 → VERIFY(FIX_REQUIRED→APPROVE) → regression 14/14; core 621→42 lines; chezmoi source `b89f936`+`efe71e6`.
- 2026-07-20 — Full CR decomposition enumerated in the queue (user directive: the queue lists the whole delivery with dependency edges upfront; spec files still authored at wave-open). `plans/` folder removed — the standard PRD/CR model under `docs/` is the delivery model; the lavish-reviewed plan record moved to `docs/research/DN-rationalization-plan-review.md`.
- 2026-07-20 — Waves 3 and 4 COMBINED into wave 3 (user directive via lavish): generator + AXI tooling + contracts ship together. There is NO close-out wave — delivery ends in a standard git-flow RELEASE (verification suite + archive/mapping.md ride the release; master tagged).
- 2026-07-20 — ELECTRONICS EXCLUDED (user): anthill-forge dead/deprecated; hw-crucible.py shim + 4 electronics agents + electronics skills under revision — ignored this delivery (PRD §D7 note). Wave-2/3 CRs must not touch them.
- 2026-07-20 — CR-MDB-007 SUPERSEDED (absorbed by 002–006): exact-phrase "Plan B" grep over skills/ memory/ AGENTS.md agents/ hooks/ scripts/ returns ZERO hits — the sweep happened during the moves/deletions. Permanent zero-Plan-B regression guard rides CR-MDB-012's verification suite. WAVE 2 CLOSED (002–006 shipped, 007 superseded).
- 2026-07-20 — VERIFY CR-MDB-002 routed forward: rust-orchestration.md L19 dangling ref to deleted memory/sandesh.md → fold into CR-MDB-006; agent-protocol prose roughness dies with CR-MDB-003.
- 2026-07-20 — DEFERRED (next SCRUM): (a) chezmoi v2.71 `diff <dir>` silently empty for drifted children (dry-run gate covers recursion); (b) pre-existing SOURCE-AHEAD chezmoi drift on 6 agent defs + `orchestration-common/track.md`, `project-management.md` — reconcile deliberately, never blind apply; (c) `bun-fix-agent.md` 2-line source delta.
- 2026-07-21 — Wave 3 in flight: 009 (`2328f24`), 010 (`cd21fad`), 008 (`237512d`) shipped with APPROVE verdicts; regression 81/81. CR-MDB-013 start ruled PREMATURE (user): feature branch deleted, plan-27 cycles 21/22 skipped, undo milestone posted. Installer-vs-scaffold split adopted (user): the UNIVERSAL INSTALLER (014) deploys user-local files per targeted harness; the scaffold (013) is project-specific (stack + overrides), reading the installation config. Open questions Q1–Q6 in the lavish Setup-split section; 013 re-plan, 014 DN, and the 015 deployment boundary block on their settlement. 011 still awaiting Crucible intimation (#1322).
- 2026-07-21 — Crucible intimation #1330 ADOPTED (user): CR-CRU-030 merged (fleet TOON-AXI, shared `_crucible_axi.py`/`toon.py`, streaming pre-merge-gate) — 011's external blocker lifted but HELD until CR-CRU-036 (WORKFLOW_CYCLE_ID removal → server-resolved active cycle) for a single sync against the final contract. Installer boundary: Crucible ships its OWN installer (server+clients bundle); the Model B universal installer (014) ORCHESTRATES it — depends on + invokes, never mirrors clients (PRD D10). CR-CRU-035 seam: Crucible core scripts + status contract, Model B hook templates + generation (015). No WORKFLOW_CYCLE_ID in hook templates or installer; the /tmp wrapper's cycle-id injection dies at the 013 re-plan wrapper rewrite.
