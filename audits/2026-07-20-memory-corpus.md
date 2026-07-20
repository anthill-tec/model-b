# Audit — Claude memory corpus (2026-07-20)

Scope: `~/.claude/CLAUDE.md`, `~/.claude/AGENTS.md`, all 24 files in `~/.claude/memory/`.

## Top-line structural findings
1. **`CLAUDE.md` is a symlink → `AGENTS.md`** (same inode, 621 lines). One physical file is BOTH the config index AND the appended `# AGENTS` sub-agent procedure (L578–621). A sub-agent told to "read AGENTS.md" ingests the whole 621-line config.
2. **CLAUDE.md references two competing orchestration entrypoints:** L17 → the NEW split (`orchestration-common/mainline/track`); L70/L73/L354 → the LEGACY shims (`orchestration-universal.md`, `agent-baseline.md`), which are 8–10-line redirect stubs.
3. **`plan_b_workflow_model.md` is broken, not canonical:** 14-line Plan-B stub + L16–110 are a verbatim copy of `project-management.md` L1–95. Dangling `[Agentic Protocol]{}` link. Defines nothing.
4. **"Plan B" vs "Model-B" split:** "Plan B" only in `plan_b_workflow_model.md` (memory) + agent-protocol/crucible skills; "Model-B" only in `sandesh.md` + bootstrap/shutdown/code-health skills; orchestration files use neither. No canonical doc exists — the model lives distributed.
5. **AXI = 0 mentions in memory.** `stack-detection.md`/`operational-commands.md` still teach hand-rolled `curl`/`mvn` ingest, contradicting the crucible skill.

## Model B (as reconstructed)
Stack-agnostic, spec-driven, SCRUM/XP-flavored agentic delivery. MAINLINE = single per-project coordinator (CR queue, CR-gen, scheduling, merges, memory). TRACK N = numbered workers, one CR lane each. SOLO = one orchestrator, no worktrees/tracks. Parallel CRs isolated in git worktrees (`.claude/worktrees/<cr>/`) via `worktree-flow.py`; merges to `develop` serialized. Sandesh (MCP mailbox) relays Mainline↔Track; wake is out-of-band via `sandesh notify` watcher. Crucible (`localhost:3849`) is the test-outcome + workflow dashboard; every RED/GREEN/regression ingested via per-stack `<stack>-crucible.py`; agents register-first/unregister-last. Sub-agents (RED/GREEN/VERIFY/FIX) do exact TDD inside the worktree boundary; orchestrators dispatch + diff-verify + own the regression gate. Two-phase: design on `develop` → execution on feature branch. `/bootstrap` and `/shutdown` bracket each session. Multi- vs single-track appears only in `orchestration-common.md` MODE-MAP.

## chezmoi (migration gate)
`~/.claude` is chezmoi-managed; source at `$(chezmoi source-path)`, personal gh account. Documented cycle covers only add/apply. **CRITICAL GAP: no delete/rename/forget procedure — deleting a file without removing it from the source means the next `chezmoi apply` resurrects it.** Inventory stale (Last Updated 2025-11-11).

## Targeted answers
- `agent-baseline.md`: 10-line redirect shim to AGENTS.md; 17 agents still cite it.
- `crucible-ingest.md`: 9-line stub fully subsumed by `skills/crucible/SKILL.md` + `# AGENTS` §Crucible-lifecycle.
- `orchestration-universal.md`: 8-line shim. Dangling inbound refs: CLAUDE.md L70+L354, `rust-orchestration.md` L3, `java-orchestration.md` L3, `cr-prd-dn-conventions.md` ~L63.
- Orphans (not in index): `chezmoi-integration.md`, `operational-commands.md`, `plan_b_workflow_model.md`, `stack-detection.md`, `java-modern-syntax.md`, `crucible-ingest.md`; `sandesh.md` wired only via orchestration files.

## Overlap map
- `plan_b_workflow_model.md` ⟺ `project-management.md` (verbatim L1–95)
- `project-management.md` ⟺ `cr-prd-dn-conventions.md` (CR model) ⟺ CLAUDE.md (classification, web-search) ⟺ `java-coding-standards.md` (logging) ⟺ `convex-client-server.md`
- `devops-environment.md` ⟺ `java-testing-practices.md` (TestContainers, DevServices, @Nested, Podman — heavy) ⟺ `quarkus-patterns.md` (Redis DevServices)
- `java-coding-standards.md` ⟺ `java-modern-syntax.md` (lambda `_`, records, pattern matching, switch, sealed)
- `git-workflow.md` ⟺ `maven-best-practices.md` (build-from-master, release) ⟺ CLAUDE.md (no-attribution, 10-step)
- `git-multi-account.md` ⟺ `chezmoi-integration.md` (§Multi-Account)
- `operational-commands.md` ⟺ `quarkus-patterns.md` (health/SSE, RediSearch) ⟺ `stack-detection.md` (curl ingest)

## Per-file verdicts
| File | Lines | Index? | Verdict |
|---|---|---|---|
| CLAUDE.md (symlink) | 621 | self | keep symlink (decision 10); target rewritten |
| AGENTS.md | 621 | ✓ | rewrite → frugal ~100-line core |
| agent-baseline.md | 10 | ✓ | delete-legacy (repoint 17 agents) |
| orchestration-universal.md | 8 | ✓ | delete-legacy (repoint 5 refs) |
| orchestration-common.md | 76 | ✓ | → model-b references |
| orchestration-mainline.md | 50 | ✓ | → model-b references |
| orchestration-track.md | 60 | ✓ | → model-b references |
| plan_b_workflow_model.md | 110 | orphan | delete; rewritten as model-b SKILL.md core |
| sandesh.md | 35 | orphan | → model-b references |
| cr-prd-dn-conventions.md | 120 | ✓ | → cr-authoring skill |
| rust-orchestration.md | 112 | ✓ | keep; repoint |
| java-orchestration.md | 84 | ✓ | keep; fix endpoints |
| crucible-ingest.md | 9 | orphan | delete (subsumed) |
| stack-detection.md | 93 | orphan | delete; routing → crucible/model-b |
| QUICK_REFERENCE.md | 299 | ✓ | delete (stale /mnt/project paths) |
| chezmoi-integration.md | 594 | orphan | → chezmoi skill + delete/rename proc |
| project-management.md | 877 | ✓ | split: CR → cr-authoring; practices → core |
| operational-commands.md | 374 | orphan | keep, trim curl-ingest |
| devops-environment.md | 451 | ✓ | merge → java-testing-practices |
| java-modern-syntax.md | 875 | orphan | keep; wire into index |
| java-coding-standards.md | 222 | ✓ | keep; trim |
| java-testing-practices.md | 792 | ✓ | keep; absorb devops |
| maven-best-practices.md | 919 | ✓ | keep; trim |
| git-workflow.md | 367 | ✓ | → git-workflow skill |
| git-multi-account.md | 267 | ✓ | → git-workflow/chezmoi skills |
| quarkus-patterns.md | 1253 | ✓ | keep |
| convex-client-server.md | 236 | ✓ | keep |
