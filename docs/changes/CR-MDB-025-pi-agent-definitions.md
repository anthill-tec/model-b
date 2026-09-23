# CR-MDB-025 — Pi agent definitions: neutral schema, per-harness emitter, rendered per project

**Status:** PENDING (re-specced 2026-09-21 for Pi; rewritten 2026-09-23 at gap-analysis for DN §D17.
Earlier versions are git history — `git log --follow docs/changes/CR-MDB-025-*` — and are not to be
consulted for contracts)
**Type:** feature
**Priority:** P1 — in release 1.0.0, wave 2 (user ruling 2026-09-21)
**Depends on:** — (CR-MDB-017, -024, -027, -030 and -033, on which earlier versions depended, have shipped)
**Labels:** generator, scaffold, harness, agent-definitions, pi, feature
**Phase:** Wave 5 (repo queue) · release 1.0.0 wave 2 (Crucible board)
**Design reference:** PRD D10.8 and DN §D17 (agents are rendered per project, per harness, by
`init`) · DN §D18 (shared text names capabilities and CLIs) · DN §D1 (neutral source + per-harness
emitters) · DN §D3 (own only what you generate) · PRD §D6 (role templates × stack params) ·
Roundhouse PRD §D4 (`generator/stacks/*.toml` `model` is the Tier-1 seam) ·
`@gotgenes/pi-subagents` `docs/configuration.md` (the reader's contract, installed locally) ·
`@gotgenes/pi-permission-system` `docs/configuration.md` · `modelb_axi/hooks.py::compile_wiring`
(the neutral-schema + emitter precedent)

**Target set:** Pi only (DN §D13/§D14). Nothing in this CR emits to, reads from or verifies against
`~/.omp/` or `~/.claude/`.

## Context — measured

**The reader.** Sub-agents are dispatched by `@gotgenes/pi-subagents` (v21.7.x). It discovers a
definition at `<project>/.pi/agents/<name>.md` first and `~/.pi/agent/agents/<name>.md` second; a
project definition overrides a global one of the same name. It reads these frontmatter fields:
`description`, `display_name`, `tools`, `model` (omitted ⇒ the parent's), `thinking` (`off` …
`max`; an unrecognised value is dropped), `max_turns`, `prompt_mode`, `inherit_context`,
`run_in_background`, `enabled`, `locked`. It does not read `color`, `effort`, `maxTurns` or
`skills`. `permission:` is read only by `@gotgenes/pi-permission-system`.

**Measured in the field, 2026-09-22/23** (dispatches during CR-MDB-021, -030, -024):

- `tools` is the complete allowlist, not a filter. Omitting it grants the built-ins and **no
  extension tools**; naming an extension tool is the only way to admit it.
- Capitalised Claude Code names (`Read, Grep, Glob, Bash`) match no registered tool: the agent
  that carried them had **zero** tools.
- **`ctx_shell` is the only shell a dispatched child has** in this install — no native `bash`
  resolves. An agent without `ctx_shell` can author files but cannot run a test.
- With the permission system installed, a granted tool with no policy defaults to `ask`, and `ask`
  in a background child is a hard stop. `permission:` frontmatter resolves it.
- The permission system proves the built-in `read`/`grep`/`find`/`ls` read-only but checks an
  extension tool against the write policy as well, so a `ctx_read` outside the project prompts
  the user.
- Project extensions and project agents reach dispatched children, which run in-process.

**What is wrong in the generator today.** `generator/stacks/*.toml` `[frontmatter]` is free text in
Claude Code's shape: `model: sonnet|inherit`, `effort`, `color`, `maxTurns`, `skills:` and
capitalised tools. On Pi half of it is inert and the tools line admits nothing. The generated
definitions are rendered by a script (`generator/build.py`) that an installed package cannot run,
and they are deployed nowhere — the definitions agents actually use are hand-placed.

## Scope

### §S1 — Neutral definition and per-harness emitter, in the package
Rendering moves into `modelb_axi/agents.py`. It renders each stack × role into a **neutral
definition** — a plain dict: `name`, `description`, `body`, `tools` (intent names), `thinking`,
`skills` (list) — and serialises it with a per-harness emitter; `_emit_pi(defn) -> str` is the only
one written today (DN §D17: the generator exists to tailor definitions to each harness). A future
emitter is one function. `generator/build.py` becomes a thin wrapper over the same module, so
`build`, `--check` and `--list` keep their behaviour and there is one code path. `generator/agents/`
remains the committed reference output that `--check` gates.

`generator/stacks/*.toml`'s free-text `[frontmatter]` blocks are replaced by structured per-role
tables — `[roles.<role>]` with `tools`, `thinking`, `skills`, and an optional `model` — so the
emitter never parses text it wrote.

### §S2 — Tools: translated, per role, lean-ctx explicit
The stack TOML carries intent names; one module-level dict in `agents.py` translates them to Pi
names. An unknown intent name is dropped with a recorded reason, never passed through or renamed.

- Tool names are lowercase Pi names. `ctx_shell` is mandatory in every definition.
- **RED, GREEN, FIX:** `read, write, edit, grep, find, ls` plus `ctx_shell, ctx_read, ctx_grep,
  ctx_glob, ctx_find, ctx_ls, ctx_patch, ctx_edit, ctx_search, ctx_tree`.
- **VERIFY:** `read, grep, find, ls` plus `ctx_shell, ctx_read, ctx_grep, ctx_glob, ctx_find,
  ctx_ls, ctx_search, ctx_tree` — no `write`, `edit`, `ctx_patch` or `ctx_edit`.
- `tools:` is emitted as one comma-separated string.

### §S3 — Frontmatter: only what the reader reads
The Pi emitter writes exactly `name` (equal to the filename stem), `description`, `tools`,
`thinking` and `permission`, plus `model` only when the stack TOML sets one.

- `model` is omitted — the child inherits the parent's model — until the Tier-1 route ids exist
  (Roundhouse PRD §D4; changed only by a `CR-RND` that updates `contracts/switchyard-routes.md` and
  the stack TOMLs together). No literal `sonnet`, `inherit`, `opus` or `haiku` survives under
  `generator/`.
- `effort` becomes `thinking` (`high`, `medium`, …).
- `color` and `maxTurns` are dropped: the reader ignores the first, and the project's
  `.pi/subagents.json` `defaultMaxTurns` governs the second.
- `skills:` is not emitted. The body carries one line, "Load these skills first: …", built from the
  role's `skills` list; skill names are harness-neutral (DN §D18).

### §S4 — Permission policy beside the tools
Every definition carries a `permission:` block giving `allow` to exactly the tools its `tools:` line
admits. VERIFY definitions also state `write: deny` and `edit: deny`, so the read-only property is
enforced by both the allowlist and the policy.

### §S5 — The role templates carry the rules the live definitions carry
`generator/templates/*.md.tmpl` gain what was applied by hand to the live definitions on
2026-09-22/23, so the next render does not erase it:

- **All four roles — reading outside the repository.** Built-in `read`/`grep`/`find`/`ls` for any
  path outside the project; `ctx_*` inside it.
- **RED — prove every test both ways.** Each test fails for the right reason on current code, and
  a spec-permitted implementation can pass it; a regression pin is proved against the regression
  it guards; both proofs are reported.
- **RED — test migration.** When a contract changes, search for tests that assert the old value
  and for tests that depend on removed behaviour without naming it; a migrated assertion takes its
  new value from the spec, never from the changed code; migrated tests are listed by id.
- **All roles — tool names.** No body instructs a tool its own frontmatter does not grant; no body
  names `Bash`. (Client paths are CR-MDB-020's; `~/.claude/skills/` citations are CR-MDB-031's.)
- **All roles — register first.** Registration with Crucible is First Action 1 in every definition,
  ahead of the AC cross-check, as `skills-src/model-b/references/sub-agent-procedure.md` already
  requires ("register immediately on startup, before reading/running anything"). A cross-check that
  finds the spec unsatisfiable ends in escalate-then-unregister. Today `red.md.tmpl` and
  `green.md.tmpl` put the cross-check first; `fix` and `verify` already comply.

### §S6 — `init` renders the project's agents
`init` renders definitions for the project's stacks into each installed harness's project agent
directory that has an emitter — for Pi, `<target>/.pi/agents/<stack>-<role>-agent.md` — and records
the stacks as `PROJECT_STACKS` in the project's `.env` (the committed registry; only `.env.local` is
ignored). The installer deploys no agent definitions.

**Re-render.** `modelb-axi agents` re-renders the definitions of the project in the current
directory from its `PROJECT_STACKS`; `--stacks` changes the set and rewrites `PROJECT_STACKS`.
It emits one AXI envelope on stdout, listing written, unchanged, skipped and unmanaged files.

**Ownership.** Each rendered file carries a marker comment inside its frontmatter naming the
generator and the sha256 of the rest of the file. A render:
- writes a file that does not exist;
- rewrites a file whose marker is intact (hash matches its content);
- skips a file whose marker is present but whose content was edited, reporting it
  `hand_modified`, unless `--force-managed`;
- never writes a same-named file with no marker, reporting it `unmanaged`;
- never writes or deletes a file of any other name in the directory.

### §S7 — Model B dog-foods it
This repository's `.pi/agents/` — hand-made on 2026-09-23 — is replaced by `modelb-axi agents`
output for `PROJECT_STACKS=python`.

### §S8 — The released client in the generator inputs (moved from CR-MDB-020 §S2)
`generator/stacks/*.toml` `test_command`, `register_command` and `unregister_command` name the
released Crucible client, `~/.crucible/clients/<stack>-crucible.py`, instead of the retired mirror
`~/.claude/scripts/<stack>-crucible.py`, which does not exist on a Pi install. Without this, `init`
ships definitions whose First Action 1 cannot run. `crucible_reference` is unchanged. Moved here by
user ruling 2026-09-23; CR-MDB-020 keeps the skill, reference and memory-template anchoring and
the anchoring and contract gates.

## Acceptance criteria

### §S1
- [ ] `modelb_axi/agents.py` holds the neutral render and `_emit_pi`; `generator/build.py` imports
      it and contains no rendering logic of its own.
- [ ] `python3 generator/build.py --check` is clean across all 20 targets, and fails on a one-byte
      drift.
- [ ] `generator/stacks/*.toml` carry `[roles.<role>]` tables; no `[frontmatter]` block remains.

### §S2
- [ ] The translation map is a module-level dict; an unknown intent name is dropped with a
      recorded reason — asserted by a test feeding one.
- [ ] Every emitted definition's `tools:` is one comma-separated string of lowercase Pi names,
      contains `ctx_shell`, and contains no capitalised name — a gate over the generated fleet,
      with a detector fixture proving it bites on `Read`.
- [ ] Every RED/GREEN/FIX definition carries exactly §S2's write-capable set; every VERIFY
      definition carries exactly the read-only set and none of `write`, `edit`, `ctx_patch`,
      `ctx_edit`.

### §S3
- [ ] Every emitted frontmatter key set is ⊆ {`name`, `description`, `tools`, `thinking`,
      `permission`, `model`}, and `model` appears only where the stack TOML sets it.
- [ ] Zero `sonnet`, `inherit`, `opus`, `haiku`, `effort`, `color`, `maxTurns` or `skills:` under
      `generator/` (templates, stacks, rendered output).
- [ ] Every definition whose role lists skills carries one "Load these skills first:" body line
      naming them.

### §S4
- [ ] Every definition's `permission:` grants `allow` to exactly the tools its `tools:` admits — a
      gate cross-checking the two keys across the fleet.
- [ ] Every VERIFY definition states `write: deny` and `edit: deny`.

### §S5
- [ ] Every rendered definition carries the out-of-repository read rule; every rendered RED
      definition carries the prove-both-ways rule and the test-migration rule — gates over the
      fleet.
- [ ] No rendered body names `Bash`, and no body instructs a tool absent from its own `tools:` line.
- [ ] Every rendered definition's First Actions list has registration with Crucible as item 1, ahead
      of the AC cross-check — a gate over the fleet (all 20), with a detector fixture proving it bites
      on the pre-amendment order.

### §S6
- [ ] `init --stacks python` with installed harnesses `[pi]` writes exactly
      `.pi/agents/python-{red,green,verify,fix}-agent.md` and records `PROJECT_STACKS=python` in
      `.env`; each rendered file is byte-identical to what `build.py` renders for the same stack ×
      role.
- [ ] An installed-wheel `init` (not a repo checkout) renders them — the wheel carries the templates,
      stacks and `modelb_axi/agents.py` (the CR-MDB-014/022 missing-asset class).
- [ ] `modelb-axi agents` in an initialised project re-renders after a template change and changes
      no other file; `--stacks python,rust` adds the four rust definitions and rewrites
      `PROJECT_STACKS`.
- [ ] Ownership, one subtest per rule: a missing file is written; an intact marked file is
      rewritten; an edited marked file is skipped as `hand_modified` and rewritten with
      `--force-managed`; a same-named file without a marker is never written and is reported
      `unmanaged`; a file of another name is untouched.
- [ ] The installer writes nothing under any agents directory, and `install.toml` carries no agent key.
- [ ] `modelb-axi agents` emits one AXI envelope on stdout listing each file's outcome.

### §S7
- [ ] `model-b/.pi/agents/` equals `modelb-axi agents` output for `PROJECT_STACKS=python`.
- [ ] **Measured, not assumed:** a rendered definition of each role, dispatched from this
      repository, runs a real command through `ctx_shell` and returns its output without a
      permission prompt — recorded with the transcript reference at close-out.

### §S8
- [ ] All five `generator/stacks/*.toml` resolve their three command strings to
      `~/.crucible/clients/<stack>-crucible.py`; `crucible_reference` is unchanged.
- [ ] Zero occurrences of `~/.claude/scripts/` paired with `-crucible.py` under `generator/`
      (templates, stacks, rendered output) — a gate, with a detector fixture proving it bites.
- [ ] All 20 files under `generator/agents/` carry the released-client form, and
      `python3 generator/build.py --check` is clean.

### Migration
- [ ] Existing tests that assert the old frontmatter, `render()` output, the `[frontmatter]` block
      or `~/.claude/agents` — and those that depend on them without naming them — are migrated to
      this contract and listed by id in the RED report. Starting set, measured at gap-analysis:
      `test_agent_generator`, `test_installer_assets`, `test_realhome_supersede`,
      `test_tooling_adoption`, `test_git_chezmoi_skills`.

## Estimated size

`modelb_axi/agents.py` (~200 lines, most moved from `build.py`), five stack TOMLs restructured,
four templates amended, `scaffold.py` (render call + `PROJECT_STACKS`), `cli.py` (the `agents`
verb), the fleet regenerated, tests. Medium.

## Risk

- Pi reader drift: the contract is measured against the installed `@gotgenes/pi-subagents`; §S7's
  measured dispatch is the check.
- A project initialised before this CR has no `PROJECT_STACKS`; `modelb-axi agents` without
  `--stacks` then fails naming the flag.

## Non-goals

- No installer asset class for agents (DN §D17). Nothing under `~/.pi/agent/agents/` (Pi's global
  scope, legacy) is written or deleted.
- No Tier-1 route ids (a `CR-RND`); no `user`-field workload identity (gated on CR-SY-003 §S1).
- No client-path anchoring beyond §S8's three generator commands: skills, references, memory
  templates and the anchoring gate over `skills-src/` stay CR-MDB-020's; no `~/.claude/skills/`
  citation repoint (CR-MDB-031).
- No emitter for any harness but Pi.
