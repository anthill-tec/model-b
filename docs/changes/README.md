# Model B — CR queue

**Project:** Model B (acronym: MDB · solo orchestrator: `vidushi-mdb`) · **Crucible projectKey:** `019f7eb8-8cad-7000-9838-854eca8e7c20` · **Design contract:** `docs/research/PRD-model-b-rationalization.md` · **Evidence base:** `audits/2026-07-20-*.md` + `docs/research/DN-rationalization-plan-review.md` · **Ontology:** `crucible:docs/research/DN-model-b-language.md` · **Target release:** 0.1.0
**Naming standard (canonical token `MODELB`/`modelb`, user-set 2026-07-20):** CR ids `CR-MDB-NNN` · Crucible agentId per agent-protocol `<agent-type>-<project>` = **`python-modelb`** (ONE identity; the client's `--phase RED|GREEN|VERIFY|REGRESSION` field carries the role — NEVER embed the phase in the id) · Sandesh project/address `ModelB` / `Mainline - ModelB` · repo dir `model-b`.

Queue rows enumerate the whole delivery (structure only). **Live status lives on the Crucible board** (plans/cycles/milestones — we file every run and transition there); `Type` lives in each spec's front matter. Pick the next CR by wave + `Depends on` against the board. Spec files are authored at wave-open.

## Queue

| CR | Title | Wave | Depends on |
|---|---|---|---|
| CR-MDB-001 | Core split: frugal AGENTS.md + procedure relocation + shim removal | 1 | — |
| CR-MDB-002 | model-b skill body: orchestration trio + sandesh + canonical Model B definition | 2 | 001 |
| CR-MDB-003 | crucible skill rewrite: real client surfaces, absorb report skills + agent-protocol | 2 | 001 |
| CR-MDB-004 | cr-authoring skill: cr-prd-dn-conventions + project-management split | 2 | 001 |
| CR-MDB-005 | git-workflow + chezmoi skills: memory-twin merges + delete/rename procedure | 2 | 001 |
| CR-MDB-006 | Memory consolidation: devops→java-testing merge, orphan wiring, stale deletions | 2 | 002, 003, 004, 005 |
| CR-MDB-007 | "Plan B" → "Model B" naming sweep across skills + memory | 2 | 002 |
| CR-MDB-008 | Agent generator: role templates + stack params + build.py --check gate; regenerate 16 agents | 3 | 002, 006 |
| CR-MDB-009 | contracts/: crucible-envelope mirror, sandesh-cli, mail-axi, lean-ctx specs | 3 | — |
| CR-MDB-010 | worktree-flow.py AXI output: TOON envelope for status/next/finish + lane boards | 3 | 009 |
| CR-MDB-011 | crucible skill final docs: shipped client surfaces (fleet envelope, vscode, arduino, plan verbs) | 3 | 003, 009 + EXTERNAL (Crucible deliveries, thread #1322) |
| CR-MDB-012 | Release 0.1.0: full verification suite (PRD §4) + archive/mapping.md + master tag | — | 006, 007, 008, 010, 011 |

**— v0.1.0 ships here —** (release CR bundles the final gates; no close-out wave)

## Setup tasks (pre-wave — not a wave; a wave is a grouping of CRs)

- [x] `git init` + `git flow init` (master/develop; on develop) — 2026-07-20
- [x] Workspace scaffold — 2026-07-20
- [x] Persist the three audit reports into `audits/` — 2026-07-20
- [x] Register project in Crucible (`Model B`, key above) — 2026-07-20
- [x] Record chezmoi source baseline commit → `archive/BASELINE.md` — 2026-07-20
- [x] Prove chezmoi delete round-trip on a scratch file — PASSED 2026-07-20 (see `archive/BASELINE.md`)

**Wave (definition, user 2026-07-20):** a grouping of CRs marking an execution boundary — in single-orchestrator projects, where major redesign can take place between groups; in multi-orchestrator projects, the sync boundary of CRs. Setup tasks and the release are not waves.

## External dependency (Wave 3)

ALL `*-crucible.py` client implementation is CRUCIBLE's (requested #1325; answered #1326): fleet TOON-AXI conversion = CR-CRU-030 (+ client READ verb), NEW vscode client (own CR, unscheduled), arduino verb extension, plan-verb client coverage — scheduled after their 0.1.0 patch cluster, OPEN ETA, per-delivery intimations threaded under #1322. CR-MDB-011 closes only as those land.

## Footer notes

- 2026-07-20 — Queue opened; wave plan + 11 design decisions locked via lavish review; PRD filed. Structural waves (1–3) run with no other live orchestrator sessions.
- 2026-07-20 — Crucible-client ownership corrected: never Model B's; requested of Crucible (#1325 superseding erroneous #1324); their scheduling answer recorded (#1326).
- 2026-07-20 — Naming standard set (header). CR-MB-001 → CR-MDB-001 (spec, branch, Crucible plan 15; plan 14 superseded, both plans now closed at merge `4fd2fca`).
- 2026-07-20 — CR-MDB-001 shipped: RED 3/11/14 → GREEN 14/14 → VERIFY(FIX_REQUIRED→APPROVE) → regression 14/14; core 621→42 lines; chezmoi source `b89f936`+`efe71e6`.
- 2026-07-20 — Full CR decomposition enumerated in the queue (user directive: the queue lists the whole delivery with dependency edges upfront; spec files still authored at wave-open). `plans/` folder removed — the standard PRD/CR model under `docs/` is the delivery model; the lavish-reviewed plan record moved to `docs/research/DN-rationalization-plan-review.md`.
- 2026-07-20 — Waves 3 and 4 COMBINED into wave 3 (user directive via lavish): generator + AXI tooling + contracts ship together. There is NO close-out wave — delivery ends in a standard git-flow RELEASE (verification suite + archive/mapping.md ride the release; master tagged).
- 2026-07-20 — DEFERRED (next SCRUM): (a) chezmoi v2.71 `diff <dir>` silently empty for drifted children (dry-run gate covers recursion); (b) pre-existing SOURCE-AHEAD chezmoi drift on 6 agent defs + `orchestration-common/track.md`, `project-management.md` — reconcile deliberately, never blind apply; (c) `bun-fix-agent.md` 2-line source delta.
