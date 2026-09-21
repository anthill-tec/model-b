# CR-MDB-031 — Retire the Claude-era substrate: roster, emitters, symlink writer, and the skills' Claude Code mechanics

**Status:** PENDING (filed 2026-09-21 from `audits/2026-09-21-codebase-review-{modelb_axi,assets,docs}.md`)
**Type:** refactor
**Priority:** P1 — in release 1.0.0, wave 2, **after CR-MDB-025 and CR-MDB-030** (025 §S5 freezes
the roster/hooks deliberately so its own diff stays small; this CR is where that freeze ends)
**Depends on:** CR-MDB-025 (the agent-definition asset class must exist before the Claude Code
path is removed) · CR-MDB-030 (the Pi emitter must work before the others are deleted) ·
CR-MDB-026 (its bootstrap/shutdown edits touch the same skill files; sequence to avoid a double
rewrite)
**Labels:** harness, installer, hooks, skills, contracts, refactor, retirement
**Phase:** Wave 5 (repo queue) · release 1.0.0 wave 2 (Crucible board)
**Design reference:** DN §D13 (Pi), §D14 (Claude Code dropped), §D16 (archimedes dispatch:
blocking, per-call `cwd`, `tools` allowlist) · user directive 2026-08-27 ("Model B carries no
chezmoi dependency") · user ruling 2026-09-21 (OMP not a target) · `AGENTS.md` ("never a
`~/.claude` path")

## Context

After CR-025 the target set is Pi alone, but the code and the published skills still carry a
Claude-Code-shaped substrate that no CR retires. Measured (audit references in brackets):

**Code** — `harness.py:22-27` roster of four, three non-targets; `deploy.py:32-34`
`HARNESS_SKILL_DIRS = {"claude-code": ".claude/skills"}` — the installer's **only** per-harness
writer targets the tree AGENTS.md forbids; `hooks.py` `_emit_claude_code` / `_emit_opencode` /
`_emit_hermes_advisory`, `_CLAUDE_EVENT_KEYS`, `_REFUSAL_REASONS`, `AllTargetsRefusedError`
(~40% of the module, unreachable on Pi-only); `scaffold.py:264-268` `CLAUDE.md → AGENTS.md`
symlink emission, `_HARNESS_NATIVE_NOTES` for hermes/opencode, `KNOWN_STACKS` with `vscode` and
`java` (§D4 says vscode is not a stack; `java` is only a memory-template prefix); `cli.py:96`
help text naming `claude-code,hermes`. [modelb_axi §B, §D]

**Published skills** — `EnterWorktree`/`ExitWorktree` (×5), `TaskList`/`TaskUpdate`/`TaskStop`,
`run_in_background` for *dispatch* (×3 beyond the watcher launch 026 owns), `PreToolUse` /
`dangerouslyDisableSandbox` wording in `sub-agent-procedure.md:10`, "derive from CLAUDE.md" (×3),
`~/.claude/projects/-home-antonyj-…-nai/memory/*` examples in `bootstrap:89,92`,
`~/.claude/skills/...` citations in skill bodies (×12) and template bodies (×8 → 32 generated),
`~/.claude/memory/*` in `quarkus.toml:17`, the `/tmp/claude-1000/<project>-crucible` wrapper
idiom (×14), the `.claude/worktrees/<cr>` convention shared by 6 consumers incl.
`block-write-outside-worktree:25` and `worktree-flow.py:87`. [assets #7, #19–22, #32, #44–47, #58]

**The `chezmoi` bundle** — 92 lines, 35 `chezmoi` refs, all about `~/.claude`; listed as an owned
bundle in `AGENTS.md` and counted by `tests/test_installer_assets.py`. CR-021 retires chezmoi
from the *tests* only. [assets #48]

**Contracts** — `contracts/mail-axi.md` is a personal mail-assistant requirements doc
("Owner: TBD — a NEW tool", sources `~/.claude/skills/mail-tracking-core`), superseded by the
external `voa` CLI and shipped in the wheel; `contracts/lean-ctx.md` describes
`~/.claude/rules/lean-ctx.md` "imported by the global CLAUDE.md", Claude tool-name preference
order, and chezmoi discipline; `pyproject.toml:26` force-includes `contracts/` which nothing
reads at runtime. [assets #36–38]

Each of these re-teaches Claude Code to a Pi orchestrator, and several are load-bearing wire
contracts (the worktree path is checked by a hook and created by a script).

## Scope

### §S0 — Gap-analysis questions
- **`.claude/worktrees` → `<new>`**: the replacement name and whether `git worktree` placement
  moves at all (a hidden dir under the repo vs `../<repo>-worktrees/`). It is a 6-consumer wire
  contract; one wave, one rename, a `contracts/worktree-layout.md` recording it.
- **The `chezmoi` bundle**: retire (recommended — Model B has no chezmoi dependency and the
  bundle only teaches `~/.claude` edits) or keep as a user-facing skill outside the owned set.
- **`/tmp/claude-1000/<project>-crucible` wrapper**: retire the idiom (the installed clients read
  `.env` + `crucible.toml` per project — measure whether the wrapper adds anything) or name a
  harness-neutral location.
- **Roster shape**: `HARNESS_ROSTER = (("pi","pi"),)` only, or `pi` + an explicit "unverified"
  tier for hermes/opencode. Recommended: `pi` only; a harness is added when a CR measures it.
- **Sub-agent identity/boundary text**: with 030's answer on the `-p` trust gate in hand,
  `sub-agent-procedure.md` states exactly which boundary is harness-enforced on Pi (tools
  allowlist always; extension when loaded).

### §S1 — Code retirement
Remove `claude-code`, `hermes`, `opencode` from `HARNESS_ROSTER`; delete `HARNESS_SKILL_DIRS`
and `_link_harness_skills` (Pi reads `~/.agents/skills` natively — §D15.1); delete the three
non-Pi emitters, `_CLAUDE_EVENT_KEYS`, `_REFUSAL_REASONS`, `AllTargetsRefusedError` and the
refusal path in `compile_wiring`; delete `CLAUDE.md` emission and `_HARNESS_NATIVE_NOTES`;
split `KNOWN_STACKS` (generator stacks) from memory-template prefixes and drop `vscode` from the
former; fix `cli.py` help/docstrings (`resolve_target_root`'s "live `~/.claude`" text).
`hooks-src/schema.md` drops "compiled per harness (claude-code, opencode, hermes, pi)".

### §S2 — Skill mechanics for Pi + archimedes
Rewrite the orchestration mechanics once, in `skills-src/model-b/references/{orchestration-common,
orchestration-track,orchestration-mainline,sub-agent-procedure}.md`, `bootstrap`, `shutdown`:
dispatch is `subagent` (blocking, `tasks[]` for parallel, per-call `cwd` = the worktree —
never `run_in_background`); worktrees are created by `worktree-flow.py` and passed as `cwd`
(no `EnterWorktree`); todo state is the Pi `todo` tool (no `TaskList`/`TaskUpdate`); project
context is `AGENTS.md` (no `CLAUDE.md`); the boundary section names the Pi mechanisms (§S0).
Remove the NAI project-memory examples. Repoint every `~/.claude/skills/<name>/…` citation in
skill bodies, template bodies and `crucible_reference` to `~/.agents/skills/<name>/…` (or a
relative skill-dir path) — **this closes CR-025 §S0's first parked question: 031 owns it, and
runs after 025/017/020's regeneration so the fleet is regenerated once more, last.**
`quarkus.toml:17`'s `~/.claude/memory/*` refs — **DONE 2026-09-21 ahead of this CR** (user ruling:
the five Java-family refs became `skills-src/memory-templates/java-*.md`, `quarkus.toml` cites the
scaffolded `docs/memory/` paths, PRD §D5 amended). Two ontology citations remain for this CR:
`modelb_axi/scaffold.py:201` renders `crucible:docs/research/DN-model-b-language.md` into every
scaffolded AGENTS.md and `skills-src/model-b/SKILL.md:12` cites the same — both repoint to the
frozen import `docs/research/DN-model-b-language.md` (imported 2026-09-21).

### §S3 — Worktree convention
Per §S0: rename across `block-write-outside-worktree`, `worktree-flow.py`, `bootstrap`,
`shutdown`, `orchestration-track`, `sub-agent-procedure`; file `contracts/worktree-layout.md`.

### §S4 — Bundles and contracts
Retire `skills-src/chezmoi/` (per §S0) with its installer-manifest and test-name-list entries;
`git-workflow/SKILL.md:151` chezmoi line goes. Archive `contracts/mail-axi.md` (move to
`archive/`); rewrite `contracts/lean-ctx.md` against Pi + the `pi-lean-ctx` extension; drop
`contracts` from `pyproject.toml` force-include unless a consumer is named.

### §S5 — Tests
Delete `ClaudeCodeEmitterTest`, the claude-code half of `RefusalTest`, `HarnessTargetingTest`'s
four-id pin, `CLAUDE.md`-symlink and hermes/opencode-note scaffold tests, the
`HARNESS_SKILL_DIRS == {claude-code}` pin; flip the 23 `--harnesses claude-code` e2e sites to
`pi` (CR-025 adds the first Pi e2e; this CR makes it the only one). Listed by test id in the RED
plan as §D14 amendments.

## Acceptance criteria

- [ ] `HARNESS_ROSTER` contains only `pi`; `detect_harnesses()` finds it via `shutil.which("pi")`.
- [ ] `hooks.py` has exactly one emitter; `compile_wiring` has no refusal path; `grep -c
      "claude\|hermes\|opencode" modelb_axi/*.py` is 0 (docstring history excepted by an
      explicit allowlist, or 0 outright).
- [ ] A sandboxed install writes nothing under `<root>/.claude/`; `install.toml` records no
      symlink stage.
- [ ] Scaffold output contains no `CLAUDE.md`; `KNOWN_STACKS` has no `vscode`.
- [ ] Zero live `~/.claude` paths anywhere under `skills-src/`, `generator/`, `hooks-src/`,
      `scripts/`, `contracts/`, `modelb_axi/` — repo-wide grep gate (`archive/` and
      `skills-src/CRUCIBLE-HANDOVER.md` provenance line exempt).
- [ ] Zero `EnterWorktree`, `ExitWorktree`, `TaskList`, `TaskUpdate`, `TaskStop`, `PreToolUse`,
      `dangerouslyDisableSandbox`, `run_in_background` (outside the 026-owned watcher fallback
      sentence) in `skills-src/` — grep gate.
- [ ] Zero `/tmp/claude-1000` in the repo outside `archive/`.
- [ ] The worktree convention is one string, declared in `contracts/worktree-layout.md`, and
      `block-write-outside-worktree` + `worktree-flow.py` + the four skills agree — a test
      parses all six.
- [ ] `skills-src/chezmoi/` is gone (or, per §S0, moved out of the owned set) and every count
      that named it is updated (`AGENTS.md`, `tests/test_installer_assets.py`).
- [ ] `contracts/mail-axi.md` is under `archive/`; `contracts/lean-ctx.md` names no Claude Code
      surface.
- [ ] No e2e test passes `--harnesses claude-code`.
- [ ] Suite baseline re-measured and recorded in `AGENTS.md`.

## Estimated size

Large by file count, small by logic: deletions in four modules, one skill-mechanics rewrite
across six reference files, one cross-consumer rename, one bundle retirement, ~30 test
amendments. Two cycles minimum (code, then skills+contracts).

## Risk

- The worktree rename is the one change that can break a running orchestrator mid-flight — land
  it in a single commit with all six consumers, and note it in the queue at close.
- Removing `claude-code` from the roster invalidates any `install.toml` that lists it;
  `resolve_harnesses` must degrade with a clear message, not a stack trace.
- The `~/.claude/memory` language refs (PRD §D5) have no Pi home until ruled; this CR surfaces
  the ruling rather than inventing one.

## Non-goals

- No OMP code exists to remove; this CR is Claude Code / hermes / opencode residue only.
- No change to the hook *scripts'* protocol (CR-030) or to agent-definition emission (CR-025).
- No touch to `archive/`.
