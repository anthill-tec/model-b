# Model B — CR queue

**Project:** Model B (solo orchestrator) · **Crucible projectKey:** `019f7eb8-8cad-7000-9838-854eca8e7c20` · **Design contract:** `docs/research/PRD-model-b-rationalization.md`
**Naming standard (canonical token `MODELB`/`modelb`, user-set 2026-07-20):** CR ids `CR-MODELB-NNN` · Crucible agentId per agent-protocol `<agent-type>-<project>` = **`python-modelb`** (ONE identity; the client's `--phase RED|GREEN|VERIFY|REGRESSION` field carries the role — NEVER embed the phase in the id) · Sandesh project/address `ModelB` / `Mainline - ModelB` · repo dir `model-b`.

Single source of truth for CR process state. Pick the next `PENDING` by wave + `Depends on`.

## Queue

| CR | Title | Wave | Type | Status | Depends on | Notes |
|---|---|---|---|---|---|---|
| CR-MODELB-001 | Core split — frugal AGENTS.md + procedure relocation + shim removal | 1 | maintenance | COMPLETED | — | spec: `CR-MODELB-001-core-split.md` · shipped 2026-07-20 |

## Wave 0 — Safety rails (tasks, no CR)

- [x] `git init` + `git flow init` (master/develop; on develop) — 2026-07-20
- [x] Workspace scaffold (`audits/ contracts/ generator/ skills-src/ archive/ scripts/ plans/ docs/`) — 2026-07-20
- [x] Persist the three audit reports into `audits/` — 2026-07-20
- [x] Register project in Crucible (`Model B`, key above) — 2026-07-20
- [x] Record chezmoi source baseline commit → `archive/BASELINE.md` — 2026-07-20
- [x] Prove chezmoi delete round-trip on a scratch file — PASSED 2026-07-20 (see `archive/BASELINE.md`)

## Planned decomposition (orchestrator recommendation — CRs filed at each wave-open)

Approved wave plan (lavish review, 2026-07-20). Spec files are authored at wave-open, not upfront.

- **Wave 2 — Model B + consolidation:** model-b skill (role param + references incl. sandesh + sub-agent procedure) · crucible skill rewrite (real surfaces + envelope contract, absorbs report skills + agent-protocol) · cr-authoring skill (+ project-management split) · git-workflow + chezmoi skills (+ git-multi-account / chezmoi-integration / devops merges, orphan wiring, deletions) · "Plan B"→"Model B" sweep.
- **Wave 3 — Generator:** templates + stack params + build.py; regenerate 16 agents; side-by-side diff review; `--check` drift gate wired to `skill-release-gate.py`.
- **Wave 4 — AXI tooling:** ALL `*-crucible.py` client work is **CRUCIBLE's responsibility — REQUESTED of Mainline - Crucible 2026-07-20 (thread #1322, request #1325); external dependency, awaiting their if/when scheduling answer**: fleet TOON-AXI envelope conversion (python/rust/mvn/arduino), NEW `vscode-crucible.py`, arduino verb-surface extension, universal plan/cycle verb adoption. Model-B-retained scope: `worktree-flow.py` AXI output; `contracts/` specs (crucible-envelope, sandesh-cli, mail-axi, lean-ctx); the crucible-skill rewrite documents whatever Crucible ships.
- **Wave 5 — Close-out (tasks):** `archive/mapping.md`; chezmoi source commits; full verification suite (PRD §4).

## Footer notes

- 2026-07-20 — Naming standard set (header). CR-MB-001 renamed CR-MODELB-001 (spec file, branch, Crucible plan). Crucible plan 14 (filed under the old id) is SUPERSEDED by plan 15; plan 14 is inert (no close verb without a commit).
- 2026-07-20 — DEFERRED items (triage at next SCRUM): (a) chezmoi v2.71 `diff <dir>` silently emits nothing for drifted files inside (makes dir-arg diff checks weak; the scoped `apply --dry-run` gate covers recursion) — candidate upstream report + test hardening; (b) pre-existing SOURCE-AHEAD chezmoi drift on 6 agent defs (`bun-fix/bun-red/python-fix/vscode-fix/vscode-green/vscode-red`) + `orchestration-common/track.md`, `project-management.md` — reconcile deliberately, NEVER via blind apply; (c) `bun-fix-agent.md` 2-line source delta (same family as b).

- 2026-07-20 — Queue opened. Wave plan + 11 design decisions locked via lavish review of `plans/2026-07-20-rationalization-plan.md`; PRD filed. Structural waves (1–3) run with no live Model B orchestrator sessions elsewhere.
- 2026-07-20 — CORRECTED (supersedes the earlier "handoff accepted" note): the crucible-client work was never Model B's to own. Model B REQUESTED Crucible perform all `*-crucible.py` client work (request #1325 withdrawing the erroneous acceptance #1324); Crucible consults its execution plan and informs if/when it will deliver. Wave 4 tracks it as an external dependency.
- 2026-07-20 — Crucible ANSWERED (#1326): ownership confirmed theirs; scheduled AFTER their 0.1.0 defect-patch cluster (CR-024/025/028/029). Mapping: fleet conversion = CR-CRU-030 (+ new client READ verb plans/status); vscode client = its own CR, not yet scheduled; arduino extension listed; plan verbs shipped server-side in CR-008, per-client coverage rides CR-030. No firm dates — OPEN ETA; they intimate per delivery (threaded #1322) with the envelope schema + reference paths. Wave-4 crucible-skill documentation waits on those intimations.
