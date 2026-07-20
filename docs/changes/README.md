# Model B — CR queue

**Project:** Model B (solo orchestrator) · **Crucible projectKey:** `019f7eb8-8cad-7000-9838-854eca8e7c20` · **Design contract:** `docs/research/PRD-model-b-rationalization.md`

Single source of truth for CR process state. Pick the next `PENDING` by wave + `Depends on`.

## Queue

| CR | Title | Wave | Type | Status | Depends on | Notes |
|---|---|---|---|---|---|---|
| CR-MB-001 | Core split — frugal AGENTS.md + procedure relocation + shim removal | 1 | maintenance | PENDING | — | spec: `CR-MB-001-core-split.md` |

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
- **Wave 4 — AXI tooling:** `axi_envelope.py` + envelope on all clients; plan/cycle verbs everywhere (bun-crucible = reference impl); NEW `vscode-crucible.py`; extend `arduino-crucible.py`; `worktree-flow.py` AXI output; `contracts/` specs (crucible-envelope, sandesh-cli, mail-axi, lean-ctx).
- **Wave 5 — Close-out (tasks):** `archive/mapping.md`; chezmoi source commits; full verification suite (PRD §4).

## Footer notes

- 2026-07-20 — Queue opened. Wave plan + 11 design decisions locked via lavish review of `plans/2026-07-20-rationalization-plan.md`; PRD filed. Structural waves (1–3) run with no live Model B orchestrator sessions elsewhere.
