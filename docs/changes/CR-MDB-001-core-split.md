# CR-MDB-001 — Core split: frugal AGENTS.md, procedure relocation, shim removal

**Status:** COMPLETED (shipped 2026-07-20 on develop)
**Type:** maintenance
**Priority:** P1 (unblocks all later waves)
**Depends on:** — (Wave 0 tasks: chezmoi baseline + delete-proof must be checked off first)
**Labels:** core, memory, chezmoi
**Phase:** Wave 1
**Design reference:** `docs/research/PRD-model-b-rationalization.md` §D1, §D2 (trigger table), §D9 (chezmoi round-trip)

## Context

`~/.claude/AGENTS.md` is a 621-line file (with `CLAUDE.md` symlinked to it) fusing the global config index and the sub-agent procedure; two legacy redirect shims (`memory/agent-baseline.md`, `memory/orchestration-universal.md`) still receive references from 17 agent definitions and 3 memory files. This CR produces the ≤100-line core, relocates the sub-agent procedure, repoints every inbound reference, and deletes the shims — all round-tripped through chezmoi.

## Scope

### §S1 — AC gate tests (this repo)
Executable gates in `tests/test_core_split.py` (pytest), asserting the §S2–§S5 ACs against the live `~/.claude` tree (paths resolved via `Path.home()`). Run + ingested through `python-crucible.py` under project `Model B` (RED against the current tree, GREEN after §S2–§S5 land).

### §S2 — Frugal AGENTS.md
Rewrite `~/.claude/AGENTS.md` to ≤100 lines containing exactly: (a) the non-negotiables as one-liners — no AI attribution in commits; import hygiene (no fully-qualified inline names, zero unused imports); TDD mandatory (RED→GREEN→clean→commit, never commit failing tests); clean build before commit; destructive-op confirmation; lean-ctx tool preference; (b) the topic → skill/memory trigger table (one row per topic: Model B workflow → `model-b` skill; Crucible/testing → `crucible` skill; CR/PRD/DN authoring → `cr-authoring`; git → `git-workflow`; dotfiles → `chezmoi`; per-stack references → `memory/` entries); (c) project-classification pointers (microservice / library / GitOps / Rust-crucible indicators, ≤10 lines). The `CLAUDE.md → AGENTS.md` symlink is untouched.

### §S3 — Sub-agent procedure relocation
Create `~/.claude/skills/model-b/references/sub-agent-procedure.md` carrying the current AGENTS.md `# AGENTS` tail (worktree boundary, Crucible lifecycle, exact TDD, report-every-run, scope discipline, code quality, consequences) verbatim-modulo: "Plan B" → "Model B", `agent-baseline.md` references removed. Also seed `~/.claude/skills/model-b/SKILL.md` as a MINIMAL stub — frontmatter (`name: model-b`, one-line workflow-scoped description) + a pointer to `references/` — so the skill dir is well-formed; the full SKILL.md body remains Wave 2.

### §S4 — Repoint inbound references
**Surfaces (verified 2026-07-20, gap-analysis re-verified):** 17 agent defs in `~/.claude/agents/` citing `memory/agent-baseline.md`; `memory/rust-orchestration.md` L3–L4 (both shims); `memory/java-orchestration.md` L3–L4 (both shims); `memory/cr-prd-dn-conventions.md` L63 (`orchestration-universal.md` deferred-items pointer → `orchestration-mainline.md`). Zero shim refs anywhere in `~/.claude/skills/`.
Replace: `memory/agent-baseline.md` → `AGENTS.md` + `skills/model-b/references/sub-agent-procedure.md`; `orchestration-universal.md` → the `orchestration-common.md`/`-mainline.md`/`-track.md` split (per referencing context).
(VERIFY-surfaced, added 2026-07-20) Five additional files referencing RELOCATED AGENTS.md content repoint to `skills/model-b/references/sub-agent-procedure.md`: `memory/crucible-ingest.md` L8 (§Crucible-lifecycle), `skills/crucible/SKILL.md` L54 ("step 6"), `skills/bootstrap/SKILL.md` L98 (procedure location), `memory/git-workflow.md` L29 + `memory/java-testing-practices.md` L17 (§TDD "compile failure IS a RED" attribution).

### §S5 — Shim deletion via chezmoi
Copy `memory/agent-baseline.md` + `memory/orchestration-universal.md` to `archive/wave1/` in this repo, then delete both from `~/.claude` AND the chezmoi source (`chezmoi destroy`); mirror every §S2–§S4 edit with `chezmoi add`; end state `chezmoi diff` clean.

## Acceptance criteria

### §S1
- [ ] `tests/test_core_split.py` exists; `python-crucible.py test` ingests a RED run to project `Model B` BEFORE §S2–§S5 and a GREEN run after.

### §S2
- [ ] `wc -l < ~/.claude/AGENTS.md` ≤ 100.
- [ ] `readlink ~/.claude/CLAUDE.md` == `/home/antonyj/.claude/AGENTS.md`.
- [ ] AGENTS.md contains a line matching `model-b` and a line matching `crucible` in the trigger table; contains `NEVER add Claude attribution` (or equivalent one-liner); contains zero occurrences of `worktree boundary` (procedure fully relocated).

### §S3
- [ ] `~/.claude/skills/model-b/references/sub-agent-procedure.md` exists; contains `git rev-parse --show-toplevel`, `Register immediately on startup`, and `A compile failure IS a RED`; contains zero occurrences of `Plan B` and zero of `agent-baseline`.
- [ ] `~/.claude/skills/model-b/SKILL.md` exists with frontmatter `name: model-b` and a non-empty `description:` line.

### §S4
- [ ] `grep -rl "agent-baseline" ~/.claude/agents/` returns 0 files.
- [ ] `grep -rl "orchestration-universal" ~/.claude/memory/ ~/.claude/agents/ ~/.claude/skills/` returns 0 files.

### §S5
- [ ] `~/.claude/memory/agent-baseline.md` and `~/.claude/memory/orchestration-universal.md` do not exist; copies exist under `archive/wave1/` in this repo.
- [ ] `chezmoi diff ~/.claude/AGENTS.md ~/.claude/CLAUDE.md ~/.claude/agents ~/.claude/memory ~/.claude/skills` exits 0 WITH empty output (CR-touched paths only; exit 0 required — an unmanaged-path abort is a FAIL, so AGENTS.md and the CLAUDE.md symlink must be brought under chezmoi management); `chezmoi apply --dry-run --verbose` (non-interactive config, scoped to the five CR-touched paths) exits 0 and mentions neither `memory/agent-baseline.md` nor `memory/orchestration-universal.md` (path forms; the whole-home unscoped dry-run both TTY-aborts on unrelated drift and false-hits unrelated project files).

## Implementation Notes
- 2026-07-20 (RED-surfaced, scope reconciliation): `chezmoi diff` is non-empty today from drift UNRELATED to this CR (e.g. `.bashrc`), so the S5 chezmoi-clean AC is scoped to the CR-touched paths. RED also exposed that the chezmoi SOURCE stores `CLAUDE.md` as a plain file while the live tree has the symlink — a live `apply` would destroy the symlink invariant. §S5 therefore includes `chezmoi add ~/.claude/CLAUDE.md` (capturing the symlink) alongside `AGENTS.md`. Files not currently under chezmoi management (`chezmoi managed` miss) are deleted with plain `rm` — nothing exists in the source to resurrect them.

- 2026-07-20 (VERIFY reconciliation): §S4 gains the five dangling-pointer files above; the S5 dry-run AC strengthened (scoped, exit-0, path-form matching) after VERIFY proved the original test vacuous. DISCLOSURE: chezmoi source commit `b89f936` swept pre-existing live-vs-source drift on the re-added agent files (stale source entries for skill lists; electronics agents newly managed) — unavoidable with `chezmoi add` of live files; contents verified to match the live tree. `~/.claude/agents/bun-fix-agent.md` remains out of source sync (pre-existing, 2-line delta) — DEFERRED, not this CR.

## Estimated size
S–M. One RED→GREEN cycle (gate tests + restructure), heavy on mechanical repoints.

## Risk
- A live Claude session elsewhere caches the old 621-line core → execute with no other Model B/orchestrator sessions active.
- Sub-agents dispatched between §S3 and Wave 2 read the procedure from the new path — agent defs must point at it in the same change (§S4), not Wave 2.

## Non-goals
- The `model-b` SKILL.md body, trigger keywords, role parameterization (Wave 2).
- Any memory-file content rewrites/merges (Wave 2).
- Agent generation (Wave 3) — §S4 edits the 17 existing files in place.
