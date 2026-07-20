# Orchestration — universal (SPLIT 2026-06-18 → role files)

The monolithic universal discipline is now **role-split + lean**. Read by role:
- **`orchestration-common.md`** — every orchestrator (any project/stack). A **solo** single-orchestrator project reads Common + Mainline.
- **`orchestration-mainline.md`** — the main orchestrator (Mainline): queue/CR-gen/scheduling, proxy-for-approvals, deferred-items + SCRUM filing, memory stewardship.
- **`orchestration-track.md`** — a track-level (worker) orchestrator.

Sub-agent procedure → `~/.claude/AGENTS.md`. Stack mechanics → `rust-orchestration.md` / `java-orchestration.md`. Doc model → `cr-prd-dn-conventions.md`.
