# CR-MDB-031 — Retire the Claude-era substrate: roster, emitters, symlink writer, and the skills' Claude Code mechanics

**Status:** PENDING (filed 2026-09-21 from `audits/2026-09-21-codebase-review-{modelb_axi,assets,docs}.md`;
gap-analysed and rewritten 2026-09-24 — verdict SPEC_UPDATE_NEEDED, §S0 ruled by the user)
**Type:** refactor
**Priority:** P1 — in release 1.0.0, wave 2, after CR-MDB-025, CR-MDB-030 and CR-MDB-032
**Depends on:** CR-MDB-020 (its §S4 tool ratchet is this CR's acceptance gate for DN §D18) ·
CR-MDB-025 (Pi agent definitions render per project, DN §D17) · CR-MDB-030 (the Pi emitter works) ·
CR-MDB-026 (bootstrap/shutdown watcher edits) · CR-MDB-032 (the hermetic suite this CR amends)
**Labels:** harness, installer, hooks, skills, contracts, refactor, retirement
**Phase:** Wave 5 (repo queue) · release 1.0.0 wave 2 (Crucible board)
**Design reference:** DN §D13 (Pi), §D14 (Claude Code dropped), §D17 (agents per project), §D18
(skills name capabilities and CLIs, never a harness's tools — user ruling 2026-09-23, options A + D) ·
user directive 2026-08-27 ("Model B carries no chezmoi dependency") · user ruling 2026-09-21 (OMP not
a target) · `AGENTS.md` ("never a `~/.claude` path")

## Context

The target set is Pi alone, but the code and the published skills still carry a Claude-Code-shaped
substrate. Measured on `develop` `c8a8816` (2026-09-24; suite 1053 tests / 0 failures / 0 skips with
the real `HOME`, 1053 / 0 / 8 skips with an empty `HOME`):

**Code.** `harness.py:22-27` roster of four, three of them non-targets. `deploy.py:37`
`HARNESS_SKILL_DIRS = {"claude-code": ".claude/skills"}` and `_link_harness_skills` (`:186`) — the
installer's only per-harness writer targets the tree `AGENTS.md` forbids; the links are never recorded
in `install.toml`. `hooks.py` (665 lines) carries `_emit_claude_code`, `_emit_opencode`,
`_emit_hermes_advisory`, `_CLAUDE_EVENT_KEYS`, `_CLAUDE_TOOL_NAMES`, `_claude_matcher`,
`_HONORS_FAIL_CLOSED`, `_REFUSAL_REASONS`, `_partition` and `AllTargetsRefusedError`, all unreachable
on Pi-only. `scaffold.py` emits a `CLAUDE.md` symlink (`:741-743`), `_HARNESS_NATIVE_NOTES` for
hermes/opencode (`:268`), the claude-code anchor line (`:338-341`), a `.opencode/` `.gitignore` line
(`:209`), refusal accounting in `hooks/README.md` (`:539-577`) and the undefined
`crucible:docs/research/DN-model-b-language.md` ontology prefix (`:240`). `cli.py:78,112` name
`~/.claude` and `claude-code,hermes`. Case-insensitive `claude|hermes|opencode` hits: `hooks.py` 44,
`scaffold.py` 13, `harness.py` 7, `deploy.py` 3, `cli.py` 2.

**A live defect found at gap analysis (not in the audit).** `KNOWN_STACKS` doubles as the
memory-template prefix filter (`scaffold.py:639`): a `java-*.md` template is emitted only when the
literal stack `java` is selected. `--stacks quarkus` therefore scaffolds none of the six `java-*`
templates, while every quarkus agent definition tells the agent to read
`docs/memory/java-testing-practices.md` and `docs/memory/java-coding-standards.md`
(`generator/stacks/quarkus.toml:17`). `vscode` is already gone (CR-MDB-024); `java` is a real
install stack (report bundle, `mvn` requirement, `block-direct-mvn-test` hook) and stays one.

**Hook scripts.** `block-direct-cargo-test` carries a `dangerouslyDisableSandbox` bypass-closer
(`:12,28,38,138`) — a Claude Code Bash-tool input field that Pi's `bash` tool does not have; the
branch can never fire on Pi. `block-write-outside-worktree:26` pins `/.claude/worktrees/`.

**Published skills and templates.** `EnterWorktree`/`ExitWorktree`/`TaskList`/`TaskUpdate`
(bootstrap, orchestration-common, orchestration-track, java-/rust-orchestration), `run_in_background`
for dispatch (orchestration-track:39; crucible/SKILL.md:182 plus a bare "Monitor"),
`AskUserQuestion` (orchestration-mainline), `PreToolUse`/`Write`/`Edit`/`NotebookEdit`/
`dangerouslyDisableSandbox` (sub-agent-procedure:10), `PreToolUse-hook-blocked` (rust.toml:17,
rust-orchestration.md:10), 27 `sandesh_*` MCP verbs (bootstrap 11, sandesh.md 8, shutdown 4,
orchestration-track 1 + others), "derive from CLAUDE.md" wording (bootstrap, shutdown,
java-orchestration, the four role templates → every generated definition), 22 `~/.claude` paths in
`skills-src/` (incl. the NAI project-memory examples at bootstrap:89,92) and 52 in `generator/`
(`crucible_reference` in four stack TOMLs; the sub-agent-procedure and crucible-skill citations in
the four templates, ×20 rendered). The CR-MDB-020 §S4 ratchet (`TOOL_BASELINE`,
`tests/test_client_path_anchoring.py:469`) holds 43 occurrences in 11 files.
`java-testing-practices.md:376`'s `` `find` `` is Panache's method, not Pi's tool.
`arduino.toml:8` says no arduino crucible reference exists; `crucible/references/arduino.md` does.

**A stall, not just a stale path (CR-MDB-036 C5 VERIFY).** Every rendered definition — including this
repository's `.pi/agents/` — sends agents to `~/.claude/skills/…`, which is outside the permission
policy, so each such read stalls a background agent on an unanswered prompt.

**The `/tmp/claude-1000/<project>-crucible` wrapper** (×14: the crucible skill + 5 references,
chezmoi, `contracts/lean-ctx.md`, `contracts/crucible-envelope.md`, `AGENTS.md:128`). Measured: every
ingest from CR-MDB-026 to CR-MDB-032 ran `~/.crucible/clients/<stack>-crucible.py` directly; cycle
attach is server-side from the registration; the wrapper only exported `WORKFLOW_WAVE`/`WORKFLOW_ROLE`
display context, and `plan-file` takes `--wave`.

**The worktree convention** `.claude/worktrees/<cr>` is a six-consumer wire contract:
`block-write-outside-worktree`, `worktree-flow.py:36,106`, `bootstrap:58`, `shutdown:52`,
`orchestration-track:20`, `sub-agent-procedure:6`. `worktree-flow.py:460,688` print
`EnterWorktree(...)`/`ExitWorktree` hints. No test pins the path.

**The `chezmoi` bundle** — 92 lines, all about editing `~/.claude`; owned bundle in `AGENTS.md:46`,
named by `git-workflow/SKILL.md:205`, `contracts/lean-ctx.md:33`, and tests in 11 modules
(`test_git_chezmoi_skills.py` half of it).

**Contracts.** `contracts/mail-axi.md` is a personal mail-assistant requirements doc superseded by
the external `voa` CLI; `contracts/lean-ctx.md` describes Claude Code surfaces; `pyproject.toml:41`
force-includes `contracts/`, which no runtime code reads (only docstrings cite it).

**Tests.** `claude-code` appears in 13 test modules (~120 lines: `test_scaffold` 32,
`test_installer_correctness` 25, `test_installer` 21, `test_hooks_compiler` 20, …); `hermes`/`opencode`
in 4 (~65 lines). `test_hooks_compiler.py` has `ClaudeCodeEmitterTest`, `OpenCodeEmitterTest`,
`HermesDegradationTest` and `RefusalTest`.

**The real install.** `~/.local/share/modelb/install.toml` records `harnesses = ["claude-code"]`.
After this CR `init`/`agents` reject it (CR-MDB-033 §S5 validation) until the release step reinstalls
targeting `pi`; the refusal must say how to recover.

## §S0 — Rulings (user, 2026-09-24)

1. **Worktrees move to `.worktrees/<cr>` inside the repo.** Same placement, new segment. A worktree
   inside the project inherits Pi's project trust (closest-ancestor resolution, mirrored by
   `modelb_axi/project_trust.py`) and the project's permission scope, so the hook extension and the
   permission policy load there; a sibling directory would do neither. Recorded in
   `contracts/worktree-layout.md`; the scaffolded `.gitignore` lists `.worktrees/`.
2. **The `chezmoi` bundle is retired from Model B.** Deployed copies are reported by the existing
   CR-MDB-037 `retired: no longer shipped` path; no installer work.
3. **The `/tmp/claude-1000` wrapper idiom is retired.** Skills name the installed client directly.
4. **The §D18 rule is stated once in `skills-src/README.md`** (not a bundle — never deployed).
5. **Roster: `pi` only** (user ruling 2026-09-21; a harness returns only when a CR measures it).
6. **Sub-agent boundary text** names what holds on Pi: the agent definition's `tools` allowlist
   always; the write-boundary hook when the project is trusted (a `.worktrees/<cr>` worktree inherits
   the project's trust). The `-p`-mode trust question (DN §D16 caveat 4) is not re-opened here.

## Scope

### §S1 — Code retirement
- `harness.py`: `HARNESS_ROSTER = (("pi", "pi"),)`.
- `deploy.py`: delete `HARNESS_SKILL_DIRS`, `_link_harness_skills` and its call (Pi reads
  `~/.agents/skills` natively, §D15.1). This voids the queued "harness-link collision should warn and
  skip" follow-up.
- `hooks.py`: exactly one emitter (`_emit_pi`); delete the three non-Pi emitters and every
  Claude/hermes/opencode table and helper listed in Context; `compile_wiring` has no refusal path and
  no `AllTargetsRefusedError`. The neutral schema keeps `fail_direction` (Pi honours it).
  `hooks-src/schema.md` drops "compiled per harness (claude-code, opencode, hermes, pi)".
- `scaffold.py`: no `CLAUDE.md`, no `_HARNESS_NATIVE_NOTES`, no claude-code anchor line, no
  `.opencode/` ignore line; `.gitignore` gains `.worktrees/` (§S3); `hooks/README.md` drops refusal
  accounting; the queue README's ontology line cites the deployed `model-b` skill
  (`~/.agents/skills/model-b/SKILL.md`, which carries the ontology summary and names its source) with
  no `crucible:` prefix \u2014 a scaffolded project has no `docs/research/DN-model-b-language.md`, so a
  repo-relative citation would dangle (amended at C1 RED, 2026-09-24).
- **Template selection by stack family:** a `<prefix>-*.md` memory template is emitted when any
  stack of its family is selected — `java-*` for `java` or `quarkus`, `rust-*` for `rust` — through a
  named prefix→stacks map, not `KNOWN_STACKS`.
- A stale harness id from `install.toml` is refused naming the id and the recovery
  (`modelb-axi --reinstall … --harnesses pi`), from `init`, `agents` and the installer flow.
- `cli.py` help and `resolve_target_root`'s docstring name no Claude surface.
- `block-direct-cargo-test`: delete the `dangerouslyDisableSandbox` branch, `DS_REASON` and the
  docstring text (dead on Pi — subtractive).

### §S2 — Skill and template text, harness-neutral (DN §D18, option A)
Rewrite the mechanics in `skills-src/model-b/references/{orchestration-common,orchestration-track,
orchestration-mainline,sub-agent-procedure,sandesh}.md`, `bootstrap`, `shutdown`, `crucible` (skill +
5 references), `git-workflow`, the memory templates, `generator/templates/*.tmpl` and
`generator/stacks/*.toml`, in capability words:
- dispatch: "dispatch the sub-agent with the worktree as its working directory", and where
  background dispatch is described, "if your harness can run it in the background, do so and wait for
  its completion notice" — no tool or parameter name (`subagent`, `tasks[]`, `run_in_background`,
  `Monitor`);
- worktrees: created by `worktree-flow.py start` and passed as the working directory (no
  `EnterWorktree`/`ExitWorktree`); `worktree-flow.py`'s printed hints say `cd <path>`;
- task state: "your task list" (no `TaskList`/`TaskUpdate`/`TaskStop`/`todo`); user questions: "ask
  the user" (no `AskUserQuestion`);
- write boundary: "the write-boundary hook blocks writes outside your worktree" (no `PreToolUse`,
  `Write`/`Edit`/`NotebookEdit`, `dangerouslyDisableSandbox`), with §S0.6's statement of what holds;
- project context: `AGENTS.md` (no `CLAUDE.md`);
- Sandesh: the `sandesh` CLI with its flags (`sandesh send --to … --project …`, `sandesh fetch`,
  `sandesh reply --to-msg …`, …) replaces every `sandesh_*` MCP verb;
- Crucible: `~/.crucible/clients/<stack>-crucible.py <verb> --agent …` directly; no wrapper;
- every `~/.claude/skills/<name>/…` citation (skill bodies, templates, `crucible_reference`) becomes
  `~/.agents/skills/<name>/…`; `arduino.toml` points at `crucible/references/arduino.md`;
- the NAI project-memory examples (bootstrap:89,92) are removed;
- `java-testing-practices.md:376` writes Panache's method as `find()`;
- `skills-src/model-b/SKILL.md:12` cites the ontology as Model B's `docs/research/DN-model-b-language.md`
  (the frozen import) without `crucible:`.
Then regenerate `generator/agents/` (`python3 generator/build.py`) and re-render this repository's
`.pi/agents/` through `modelb-axi agents` (sandboxed `--modelb-home`) — never hand-edited.
`skills-src/README.md` states the §D18 rule once, citing DN §D18 and the ratchet test.

### §S3 — Worktree convention
`.claude/worktrees/<cr>` → `.worktrees/<cr>` in all six consumers in one commit;
`contracts/worktree-layout.md` declares the string, the placement rationale (§S0.1) and its six
consumers.

### §S4 — Bundles and contracts
Delete `skills-src/chezmoi/`, `git-workflow/SKILL.md:205`'s chezmoi line and every chezmoi mention in
`contracts/lean-ctx.md`; update `AGENTS.md` (bundle list and count: 13 bundles, 7 Model-B-owned,
6 imported) and every test that names the bundle. Move `contracts/mail-axi.md` to `archive/`
(an addition to `archive/`, not an edit of it). Rewrite `contracts/lean-ctx.md` against Pi and the
`pi-lean-ctx` extension. Drop `contracts` from `pyproject.toml` force-include (no runtime consumer).

### §S5 — Tests
Delete the non-Pi emitter classes (`ClaudeCodeEmitterTest`, `OpenCodeEmitterTest`,
`HermesDegradationTest`, `RefusalTest`) and every scaffold/installer/deploy test whose subject is a
retired harness, the `CLAUDE.md` symlink, the native notes or the symlink writer; flip every other
`--harnesses claude-code` / `harnesses=["claude-code"]` site to `pi`; delete the
`dangerouslyDisableSandbox` tests for `block-direct-cargo-test`; delete the chezmoi half of
`test_git_chezmoi_skills.py` and re-pin any line-number citation into files this CR edits (e.g.
`test_installer_assets.ChezmoiInvocationGateTest`). Every deleted or flipped test is listed by id in
its commit body. `TOOL_BASELINE` becomes `{}`.

## Acceptance criteria

- [ ] `HARNESS_ROSTER == (("pi", "pi"),)`; `detect_harnesses()` finds it via `shutil.which("pi")`.
- [ ] `hooks.py` defines exactly one `_emit_*` function (`_emit_pi`); `compile_wiring`'s report
      entries carry no `refusals` key; `AllTargetsRefusedError` is not defined anywhere under
      `modelb_axi/`.
- [ ] Case-insensitive `claude|hermes|opencode` matches zero lines under `modelb_axi/*.py`
      (a test asserts it).
- [ ] A sandboxed Pi install creates no symlink anywhere under `<target-root>` and nothing under
      `<target-root>/.claude/`; `deploy.py` defines no `HARNESS_SKILL_DIRS`.
- [ ] Scaffold output contains no `CLAUDE.md`, no `.opencode/` line, and a `.worktrees/` line in
      `.gitignore`; the rendered queue README's ontology line cites `~/.agents/skills/model-b/SKILL.md`
      with no `crucible:` prefix.
- [ ] `init --stacks quarkus` (sandboxed) scaffolds all six `java-*.md` templates;
      `--stacks java` does too; `--stacks rust` scaffolds `rust-orchestration.md`;
      `--stacks python` scaffolds neither family.
- [ ] With an `install.toml` recording `harnesses = ["claude-code"]`, each of `init`, `agents` and the
      installer flow (without `--harnesses`) exits non-zero, writes nothing, and its message names
      `claude-code` and the `--reinstall … --harnesses pi` recovery.
- [ ] `block-direct-cargo-test` contains no `dangerouslyDisableSandbox`; its remaining tests pass.
- [ ] Zero live `~/.claude` paths in `skills-src/`, `generator/` (templates, stacks, agents),
      `hooks-src/`, `scripts/`, `contracts/`, `modelb_axi/`, `.pi/agents/`, `AGENTS.md` and
      `docs/install-guide.md` — a grep gate; exempt only the `CRUCIBLE-HANDOVER.md` provenance line and
      prose that names `~/.claude` as the tree Model B never writes (each exemption listed by
      file:line in the gate).
- [ ] Zero `EnterWorktree`, `ExitWorktree`, `TaskList`, `TaskUpdate`, `TaskStop`, `AskUserQuestion`,
      `PreToolUse`, `NotebookEdit`, `dangerouslyDisableSandbox`, `run_in_background` and
      `sandesh_(send|reply|fetch|inbox|register|unregister|addressbook|setup)` in `skills-src/`,
      `generator/`, `hooks-src/` and `scripts/` — a grep gate. The 026-owned watcher fallback
      sentence is rewritten in capability words too (no exemption).
- [ ] Zero `CLAUDE.md` in `skills-src/`, `generator/` (templates, stacks, agents), `hooks-src/`,
      `scripts/`, `modelb_axi/` and `.pi/agents/` — a grep gate; project context is named
      `AGENTS.md` (Sheetal, the one real project named, carries `AGENTS.md` at both levels and no
      `sheetal-firmware/CLAUDE.md`; added at C2 RED, 2026-09-24).
- [ ] CR-MDB-020 §S4's ratchet passes with `TOOL_BASELINE == {}` and no exemption added.
- [ ] Every Sandesh step in `skills-src/` names the `sandesh` CLI (`sandesh <verb> …`); the gate
      asserts at least one `sandesh send`, `sandesh fetch` and `sandesh reply` form survives in
      `skills-src/`.
- [ ] `skills-src/README.md` exists, states the §D18 rule and names the ratchet test; it is not
      deployed (no `SKILL.md`, absent from a sandboxed install's manifest).
- [ ] Zero `/tmp/claude-1000` and zero "wrapper" instructions for Crucible in the shipped surfaces
      of the `~/.claude` gate above.
- [ ] `.worktrees/` is the only worktree segment: `contracts/worktree-layout.md` declares it and a test
      parses all six consumers (`block-write-outside-worktree`, `worktree-flow.py`, `bootstrap`,
      `shutdown`, `orchestration-track`, `sub-agent-procedure`) and finds exactly that string;
      `.claude/worktrees` appears nowhere in the shipped surfaces; the hook's existing behaviour tests
      pass against `.worktrees/`.
- [ ] `generator/build.py --check` is clean and `.pi/agents/` equals a fresh sandboxed
      `modelb-axi agents` render.
- [ ] `skills-src/chezmoi/` is gone; `chezmoi` appears nowhere in `skills-src/`, `generator/`,
      `contracts/` or `modelb_axi/`; `AGENTS.md` lists 13 bundles (7 owned, 6 imported).
- [ ] `contracts/mail-axi.md` exists only under `archive/`; `contracts/lean-ctx.md` names no Claude
      Code surface (it passes the `~/.claude`, `CLAUDE.md` and tool gates); `pyproject.toml`
      force-includes no `contracts`, and a built wheel carries no `_assets/contracts/`.
- [ ] No test passes `--harnesses claude-code`/`hermes`/`opencode` or lists them in `harnesses=`;
      every deleted or flipped test is listed by id in a commit body.
- [ ] Suite baseline re-measured (real and empty `HOME`) and recorded in `AGENTS.md`; 0 failures,
      0 errors in both.

## Cycle plan

- **C1 (red-green) — code (§S1, its §S5 tests).**
- **C2 (red-green) — skill and template text (§S2), regeneration, `skills-src/README.md`.**
- **C3 (red-green) — worktree convention (§S3), bundles and contracts (§S4).**
- **C4 (verify).**

## Risk

- The worktree rename breaks any orchestrator mid-flight in a `.claude/worktrees/` tree — land it in
  one commit with all six consumers; note it in the queue at close. None is in flight today.
- Retiring `claude-code` invalidates the real July `install.toml` until the release-step reinstall;
  the refusal message (AC) names the recovery.
- Text rewrites move line numbers that tests pin (inverse blast radius) — each cycle re-pins in its
  own GREEN, and C2's RED lists the pins into files it will edit.

## Non-goals

- No OMP code exists to remove.
- No change to the hook scripts' stdin/exit protocol (CR-030) or to agent-definition emission logic
  (CR-025) beyond the text they render.
- No edit of `archive/`, closed CR specs, `audits/` or `docs/research/` history (the gates scope to
  shipped surfaces).
- This repository's own `CLAUDE.md → AGENTS.md` symlink stays (the user's harness compatibility).
