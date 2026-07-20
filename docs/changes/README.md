# Model B — CR queue

**Project:** Model B (solo orchestrator) · **Crucible projectKey:** `019f7eb8-8cad-7000-9838-854eca8e7c20` · **Design contract:** `docs/research/PRD-model-b-rationalization.md`
**Naming standard (canonical token `MODELB`/`modelb`, user-set 2026-07-20):** CR ids `CR-MODELB-NNN` · Crucible agentId per agent-protocol `<agent-type>-<project>` = **`python-modelb`** (ONE identity; the client's `--phase RED|GREEN|VERIFY|REGRESSION` field carries the role — NEVER embed the phase in the id) · Sandesh project/address `ModelB` / `Mainline - ModelB` · repo dir `model-b`.

Queue rows enumerate the whole delivery (structure only). **Live status lives on the Crucible board** (plans/cycles/milestones — we file every run and transition there); `Type` lives in each spec's front matter. Pick the next CR by wave + `Depends on` against the board. Spec files are authored at wave-open.

## Queue

| CR | Title | Wave | Depends on |
|---|---|---|---|
| CR-MODELB-001 | Core split: frugal AGENTS.md + procedure relocation + shim removal | 1 | — |
| CR-MODELB-002 | model-b skill body: orchestration trio + sandesh + canonical Model B definition | 2 | 001 |
| CR-MODELB-003 | crucible skill rewrite: real client surfaces, absorb report skills + agent-protocol | 2 | 001 |
| CR-MODELB-004 | cr-authoring skill: cr-prd-dn-conventions + project-management split | 2 | 001 |
| CR-MODELB-005 | git-workflow + chezmoi skills: memory-twin merges + delete/rename procedure | 2 | 001 |
| CR-MODELB-006 | Memory consolidation: devops→java-testing merge, orphan wiring, stale deletions | 2 | 002, 003, 004, 005 |
| CR-MODELB-007 | "Plan B" → "Model B" naming sweep across skills + memory | 2 | 002 |
| CR-MODELB-008 | Agent generator: role templates + stack params + build.py --check gate; regenerate 16 agents | 3 | 002, 006 |
| CR-MODELB-009 | contracts/: crucible-envelope mirror, sandesh-cli, mail-axi, lean-ctx specs | 4 | — |
| CR-MODELB-010 | worktree-flow.py AXI output: TOON envelope for status/next/finish + lane boards | 4 | 009 |
| CR-MODELB-011 | crucible skill final docs: shipped client surfaces (fleet envelope, vscode, arduino, plan verbs) | 4 | 003, 009 + EXTERNAL (Crucible deliveries, thread #1322) |

## Wave 0 — Safety rails (tasks, no CR)

- [x] `git init` + `git flow init` (master/develop; on develop) — 2026-07-20
- [x] Workspace scaffold — 2026-07-20
- [x] Persist the three audit reports into `audits/` — 2026-07-20
- [x] Register project in Crucible (`Model B`, key above) — 2026-07-20
- [x] Record chezmoi source baseline commit → `archive/BASELINE.md` — 2026-07-20
- [x] Prove chezmoi delete round-trip on a scratch file — PASSED 2026-07-20 (see `archive/BASELINE.md`)

## External dependency (Wave 4)

ALL `*-crucible.py` client implementation is CRUCIBLE's (requested #1325; answered #1326): fleet TOON-AXI conversion = CR-CRU-030 (+ client READ verb), NEW vscode client (own CR, unscheduled), arduino verb extension, plan-verb client coverage — scheduled after their 0.1.0 patch cluster, OPEN ETA, per-delivery intimations threaded under #1322. CR-MODELB-011 closes only as those land.

## Footer notes

- 2026-07-20 — Queue opened; wave plan + 11 design decisions locked via lavish review; PRD filed. Structural waves (1–3) run with no other live orchestrator sessions.
- 2026-07-20 — Crucible-client ownership corrected: never Model B's; requested of Crucible (#1325 superseding erroneous #1324); their scheduling answer recorded (#1326).
- 2026-07-20 — Naming standard set (header). CR-MB-001 → CR-MODELB-001 (spec, branch, Crucible plan 15; plan 14 superseded, both plans now closed at merge `4fd2fca`).
- 2026-07-20 — CR-MODELB-001 shipped: RED 3/11/14 → GREEN 14/14 → VERIFY(FIX_REQUIRED→APPROVE) → regression 14/14; core 621→42 lines; chezmoi source `b89f936`+`efe71e6`.
- 2026-07-20 — Full CR decomposition enumerated in the queue (user directive: the queue lists the whole delivery with dependency edges upfront; spec files still authored at wave-open). `plans/` folder removed — the standard PRD/CR model under `docs/` is the delivery model; the lavish-reviewed plan record moved to `docs/research/DN-rationalization-plan-review.md`.
- 2026-07-20 — DEFERRED (next SCRUM): (a) chezmoi v2.71 `diff <dir>` silently empty for drifted children (dry-run gate covers recursion); (b) pre-existing SOURCE-AHEAD chezmoi drift on 6 agent defs + `orchestration-common/track.md`, `project-management.md` — reconcile deliberately, never blind apply; (c) `bun-fix-agent.md` 2-line source delta.
