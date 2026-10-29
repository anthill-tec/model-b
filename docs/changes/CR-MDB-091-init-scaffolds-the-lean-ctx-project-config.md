# CR-MDB-091 — `init` scaffolds the project's lean-ctx config

**Status:** PENDING — spec drafted 2026-10-29 from the gap analysis and the user's rulings (PRD D5, 2026-10-29); the spec pre-review folded in; awaiting approval.
**Type:** feature (`modelb_axi`: a new project file under marker ownership; `init`, `modelb-axi agents`;
the scaffolded `AGENTS.md`; the contract and the install guide)
**Priority:** P2.
**Depends on:** CR-MDB-088 (it decided the knowledge-store levers); board-authoritative: read `queue`.
**Labels:** lean-ctx, scaffold, init
**Points:** 3.
**Design reference:** PRD D5, amendment of 2026-10-29 ("the project config's knowledge levers (set by
CR-MDB-091, no trust needed): a fact cap of 500 and automatic consolidation off");
DN-multi-harness-deploy-model §D17 (per-project rendering), §D24 and §D27 (`modelb-axi agents`
re-renders a project's generated files for existing projects, under the same ownership rules);
CR-MDB-025 §S6 and CR-MDB-068 §S2 (marker ownership, `agents.first_line_ownership`); research note
`lean-ctx-for-model-b` §S4.5, §S5; `contracts/lean-ctx.md` § "Project-scoped levers"; gap analysis
2026-10-29 (`/tmp/mdb091/gap-analysis.md`); spec pre-review 2026-10-29 (`CR-MDB-091-SPEC-REVIEW`).

## Context

- **lean-ctx reads a per-project file.** lean-ctx 3.11.4 reads `<project_root>/.lean-ctx.toml`
  (`Config::local_path`, `rust/src/core/config/loader.rs`) and merges it over the global
  `~/.config/lean-ctx/config.toml`, the project winning (`Config::merge_local`,
  `rust/src/core/config/merge.rs`). The project root is resolved per process: `LEAN_CTX_PROJECT_ROOT`,
  else the latest session for the working directory, else the git top level, else the working
  directory (`Config::find_project_root_inner`). So a monorepo's sub-projects use the root's file, and a
  process in `.worktrees/<cr>` uses the worktree's committed copy.
- **Trust.** An untrusted workspace has its security-sensitive keys stripped (shell allowlists, path
  widening, proxy upstreams, tool surface; `strip_sensitive_overrides`, `loader.rs`). `memory.*` and
  `autonomy.*` are not among them: they apply without `lean-ctx trust`.
- **The two ruled levers take effect from the project file:**
  - `[memory.knowledge] max_facts` (default 200, `KnowledgePolicy`, `rust/src/core/memory_policy.rs`)
    is merged when it differs from the default. An explicit 500 survives the disk-budget scaling
    (`Config::memory_policy_effective`), and the env var `LEAN_CTX_KNOWLEDGE_MAX_FACTS` still beats it.
  - `[autonomy] auto_consolidate = false` is merged (`override_if_false!`).
  - Both are read through `Config::load()` in the process serving the project: the knowledge policy
    (`load_policy_or_error`, `rust/src/tools/knowledge_shared.rs`) and the autonomy config
    (`AutonomyConfig::load`, `rust/src/core/config/sections.rs`).
- **What `auto_consolidate = false` stops.** It stops the scheduled pass every 25 tool calls, which runs
  the fact lifecycle (`should_auto_consolidate`, `rust/src/core/autonomy.rs`). The session imports at
  checkpoint, MCP shutdown and compaction still run, with no lifecycle (`auto_consolidate_knowledge`,
  `rust/src/tools/startup.rs`). The contract already says so.
- **Comments are valid, with one hazard.** The file is TOML, so a first-line `#` marker parses. But five
  keys are merged when the raw text merely contains their name (`override_if_key_present!`,
  `merge.rs`): `response_shaping`, `compression_level`, `compression_aggressiveness`, `terse_agent`,
  `behavior_nudges`. A comment naming one resets that setting to its default for the project.
- **Any project file resets one more setting.** `Config::merge_local` assigns `autonomy.silent_preload`
  from the project file unconditionally, so a file that omits it (as this one does) sets it to its default
  `true` over a user's global `false`. The file writes two keys only, but its effect reaches a third.
- **lean-ctx never writes the file.** `lean-ctx trust` pins the file's content hash
  (`rust/src/core/workspace_trust.rs`), so any later edit, a re-render included, un-trusts it.
- **Model B scaffolds none today,** so every project runs at the 200-fact cap with automatic
  consolidation on, Model B's own repository included.
- **What the seed proposed and the analysis cut** (PRD D5, ruled 2026-10-29):
  - per-stack index excludes: `.gitignore` (honoured with or without `.git`) and lean-ctx's built-in
    skips already cover them; `[index] exclude` reaches neither `ctx_search` nor a daemon-built index
    (gap analysis DRIFT-4);
  - `preserve_compact_formats = ["toon"]`: the default, merged additively, and CR-MDB-090 runs AXI
    commands raw (DRIFT-5);
  - a `lean-ctx index build` Setup task: the index builds itself on the first read (DRIFT-6).

## Scope

### §S1 — The rendered config

A new module, `modelb_axi/lean_ctx_config.py`, shaped like `modelb_axi/permission_policy.py`:

- `CONFIG_RELPATH = ".lean-ctx.toml"`.
- `MARKER_PREFIX = "# generated by modelb-axi (Model B lean-ctx project config); sha256 "`.
- `render_config() -> str`: the marker line (prefix plus the sha256 of the body), then this body,
  exactly:

  ```toml
  [memory.knowledge]
  max_facts = 500

  [autonomy]
  auto_consolidate = false
  ```

  No other key, and no other comment (PRD D5, ruled 2026-10-29). The body ends with exactly one `\n`,
  which the marker's hash covers. The render
  takes no argument: it does not depend on the stacks, the harnesses, the lean-ctx verdict or `HOME`.
- `ownership_state(text) -> str`: `agents.first_line_ownership(text, MARKER_PREFIX)`, looked up on
  `agents` at call time.
- `place_project_config(project_root, *, force_managed=False, report=None) -> dict`: writes
  `render_config()` at `project_root / CONFIG_RELPATH` through `agents.place_owned` with
  `classify=ownership_state`; returns (and fills, when given) `report` with `written` / `unchanged` /
  `skipped` / `unmanaged`.

The module docstring cites PRD D5 and this section, and names a DN by its file
(`DN-multi-harness-deploy-model §D17`), never a bare `DN §`, which `tests.test_installer_correctness` bites.
The module uses no `.write_text(`: it writes only through `agents.place_owned`. It imports no
process-running module: Model B
never runs `lean-ctx trust`, `config set`, `index build` or `doctor --fix` (research note §S5.3).

### §S2 — `init` writes it

- `scaffold.plan_files` lists `.lean-ctx.toml` once, at the root. A monorepo sub-project gets none.
- `_emit_plan` places it with `lean_ctx_config.place_project_config`, after the permission-policy
  block, outside the `"pi" in harnesses` gate. Its `skipped` and `unmanaged` paths join `ownership`, so
  they get `_ownership_warnings`' wording; its `written` paths join `emitted`.
- It is written whatever the recorded lean-ctx verdict: present, absent, unknown or unrecorded (PRD D5,
  ruled 2026-10-29). Without lean-ctx the file is inert.
- The scaffold commit carries it, and the scaffolded `.gitignore` does not ignore it.

### §S3 — `modelb-axi agents` re-renders it

- `scaffold.run_agents` places it after the permission policy and outside its `"pi" in harnesses` gate,
  whatever the recorded lean-ctx verdict, inside the same `OSError` handler, under
  the same ownership rules: written when missing; rewritten when its marker is intact; skipped when
  hand-modified unless `--force-managed`; never written without a marker, even with `--force-managed`.
  It is reported in the envelope's `written`, `unchanged`, `skipped` or `unmanaged` list beside the agent
  files, and a skipped or unmanaged config gets the warning an agent file gets.
- `--stacks` leaves an intact current config byte-identical (the render takes no stack).
- A validation refusal (exit 2) writes no config.
- The `agents` subparser's help and description, and the verb's stderr progress line, name the "lean-ctx
  project config" and still name the "permission policy".

### §S4 — The note in the scaffolded `AGENTS.md` (PRD D5, ruled 2026-10-29)

`scaffold._render_lean_ctx_section` gains one bullet, so it reaches the root `AGENTS.md` and each
sub-project's, whatever the verdict. The bullet says, in one unit:

- the repository root's `.lean-ctx.toml` sets the knowledge store's fact cap and turns automatic
  consolidation off, needs no `lean-ctx trust`, and is Model B's: `modelb-axi agents` re-renders it;
- a security-sensitive key added to it by hand applies only after `lean-ctx trust`, which is lean-ctx's
  own decision and not Pi's `/trust`;
- a hand-edited file is left alone by `modelb-axi agents` unless `--force-managed`, which replaces it
  and drops the added keys.

The bullet does not contain the substring `lean-ctx knowledge` (it says "the knowledge store", never
"the lean-ctx knowledge store"): `pointer_findings` flags any unit naming it without "never", and that
check stays green unmigrated.

The `## Setup` section is unchanged: no `lean-ctx index build` task, and no trust task.

### §S5 — The contract

`contracts/lean-ctx.md` § "Project-scoped levers" keeps every sentence its pins read, and gains:

- where the levers are set: `modelb-axi init` writes them to the project root's `.lean-ctx.toml` under
  a first-line `#` ownership marker, and `modelb-axi agents` re-renders it for an existing project; the
  file raises lean-ctx's default 200-fact cap to 500;
- the substring hazard: lean-ctx merges `response_shaping`, `compression_level`,
  `compression_aggressiveness`, `terse_agent` and `behavior_nudges` when the file's text contains their
  name, so no comment in the file names one (`Config::merge_local`, `rust/src/core/config/merge.rs`);
- a re-render changes the content hash `lean-ctx trust` pins, so a trusted file is untrusted again.
  An intact file carries no sensitive key, so nothing it sets is lost (`is_trusted_for`,
  `rust/src/core/workspace_trust.rs`);
- any project file sets `autonomy.silent_preload` (default `true`) over the global value, even one that
  does not name it (`Config::merge_local`, `rust/src/core/config/merge.rs`).

The pinned pitfall "The cap" ("The 200-fact cap is shared with automatic captures") stays as it is: 200 is
lean-ctx's default, and the first new bullet links it to the project file's 500.

The rest of the contract is CR-MDB-092's.

### §S6 — The install guide and the generated README

The guide's `project-trust` region (`docs/install-guide.md`) gains one paragraph, after "Updating an
existing project's policy", whose sentence about the policy stays as it is:

- `init` also writes `.lean-ctx.toml`, lean-ctx's project config: the knowledge store's fact cap and
  automatic consolidation off;
- it needs no `lean-ctx trust`, which is lean-ctx's decision and not Pi's `/trust`;
- `modelb-axi agents` re-renders it; an edited one is left alone unless `--force-managed`.

`pi-package/README.md` is re-rendered from the guide's regions with `generator/build.py build`.

### §S7 — Model B's own config (PRD D5, ruled 2026-10-29)

Model B's repository root gets `.lean-ctx.toml`, placed through `place_project_config`, and committed.
The sdist does not ship it (`[tool.hatch.build.targets.sdist] only-include`).

### §S8 — Records

- `AGENTS.md`'s two module counts move with the new test module (113 → 114 on today's tree; RED
  re-counts).
- The rulings are recorded under PRD D5's 2026-10-29 amendment (`f1d7258`).

## Acceptance criteria

New tests live in `tests/test_lean_ctx_project_config.py` unless an AC names another module. Every
`init` runs in process in the sandbox of `tests.test_init_tool_verdicts` (through
`tests.test_project_setup_section._Case`). Every `agents` run drives `python3 -m modelb_axi agents` in the
seeded sandbox of `tests.test_agents_verb_permission_policy._AgentsVerbPolicyCase`. `HOME`,
`MODELB_HOME`, `XDG_DATA_HOME` and `PI_CODING_AGENT_DIR` are at per-test temp dirs. No test reads the
real `~/.config/lean-ctx`, `~/.pi` or `~/.crucible`, and none runs `lean-ctx`.

- [ ] **§S1, the render.**
      - `tomllib.loads(render_config())` equals
        `{"memory": {"knowledge": {"max_facts": 500}}, "autonomy": {"auto_consolidate": False}}`.
      - Its first line is `MARKER_PREFIX` plus `agents.sha256_text` of everything after the first
        newline, and no other line starts with `#`.
      - The text ends with exactly one `\n` (it ends `= false\n`, not `\n\n`).
      - `ownership_state(render_config())` is `intact`; with one body character changed it is
        `hand_modified`; with the marker line removed it is `unmanaged`.
      - Two calls return the same text, and a call under a changed `HOME` and `PATH`
        (`mock.patch.dict`) returns the same text.
- [ ] **§S1, the substring hazard.** `override_hazards(text)` returns the names, among `response_shaping`,
      `compression_level`, `compression_aggressiveness`, `terse_agent` and `behavior_nudges`, that
      `text` contains anywhere. `override_hazards` is a helper of `tests/test_lean_ctx_project_config.py`;
      the production module defines none. It is case-sensitive, as lean-ctx's `local_toml.contains` is,
      and returns the names in the order listed. `override_hazards(render_config())` is `[]` (the marker
      line included). The detector is proved
      both ways on synthetic text:
      - it bites each name in a comment line (`# compression_level stays global`) and as a table
        header (`[response_shaping]`);
      - it spares `compression_enabled`, `[conversation]`, `compression` alone,
        `# lean-ctx project config` and `Compression_Level` (case differs).
- [ ] **§S1, no lean-ctx command.** An `ast` walk of `modelb_axi/lean_ctx_config.py` finds no import of
      `subprocess`, `os` or `shutil`. The check is proved both ways: it bites a synthetic module that
      imports `subprocess`, and one that does `from os import system`; it spares one that does only
      `from pathlib import Path` and `from modelb_axi import agents`.
- [ ] **§S2, `init`.** For each of `tests.test_project_setup_section.SHAPES` (solo and multi, standalone
      and monorepo):
      - exactly one `.lean-ctx.toml` exists under the target, at the root, equal to `render_config()`;
      - `scaffold.plan_files(subs)` lists it once and no `<sub>/.lean-ctx.toml`, with and without
        sub-projects;
      - the envelope's `planned` and `emitted` each list it once, and `emitted` equals the files on disk;
      - with `no_commit=False`, `git ls-files` lists it and `git check-ignore -q .lean-ctx.toml` exits 1.
- [ ] **§S2, `--dry-run`.** A multi monorepo `--dry-run` plans it once at the root and writes nothing
      (the target does not exist).
- [ ] **§S2, every verdict** (PRD D5, ruled 2026-10-29). With lean-ctx recorded `detected`, `absent`,
      `unknown`, and unrecorded, `init` writes the same `.lean-ctx.toml`, equal to `render_config()`.
- [ ] **§S2, an existing file.** A target seeded with an unmarked `.lean-ctx.toml` keeps it byte-identical
      after `init`. The envelope lists it in `unmanaged` and not in `emitted`, and one warning names it
      with `_ownership_warnings`' unmanaged wording.
- [ ] **§S3, the wired path.** In the seeded sandbox, one test per bullet:
      - no config yet: the verb writes `render_config()`, lists `.lean-ctx.toml` in `written` only, and
        its index in `written` is after the policy's;
      - an identical config: `unchanged` only, byte-identical;
      - an older render under an intact marker (a body with `max_facts = 200`, its marker recomputed with
        `agents.sha256_text`): rewritten to `render_config()`, `written` only;
      - a hand-modified config: byte-identical, `skipped` only, and its warning is the one a skipped
        agent file gets, with the config's path; then with `--force-managed` it is rewritten, `written`
        only;
      - an unmarked config: byte-identical with and without `--force-managed`, `unmanaged` only, with
        the warning an unmanaged agent file gets;
      - `--stacks python,rust`: an intact current config is byte-identical and `unchanged`;
      - with lean-ctx recorded `absent` in the sandbox's `install.toml`, the verb writes the same
        `render_config()` and lists `.lean-ctx.toml` in `written`.
- [ ] **§S3, failure paths.**
      - With `.lean-ctx.toml` a directory, the verb exits 3 with `ok: false`. One warning names the
        error on that path, and `written` lists the agent files and the policy.
      - With no `.env`, the verb exits 2 and no `.lean-ctx.toml` exists.
- [ ] **§S3, text.** The `agents` subparser's help and description, and its one stderr progress line
      starting `modelb-axi: agents`, each contain "lean-ctx project config" and "permission policy"
      (whitespace-normalised, case-insensitive). The checker is proved both ways: it bites text that
      names only one of the two phrases.
- [ ] **§S4, the note** (PRD D5, ruled 2026-10-29). `project_config_note_findings(section)`
      is empty for the lean-ctx section of a scaffolded root `AGENTS.md` and of `a/AGENTS.md` (monorepo
      `a`), and for `scaffold._render_lean_ctx_section("kb-render")`. It needs one bullet unit that
      carries all four of these:
      - `.lean-ctx.toml` and `modelb-axi agents`;
      - a sentence of the unit says `lean-ctx trust` is not needed for the file: a negation (`no`,
        `not`, `never`) within 40 characters before `lean-ctx trust`, in the same sentence (for example
        "needs no `lean-ctx trust`");
      - a separate clause names Pi's `/trust` as a different decision;
      - `--force-managed`.

      Each pin is proved by a cut that removes it alone. Splitting the four across two bullets bites, and
      so does a unit whose only negation sits in the `/trust` clause ("run `lean-ctx trust`, not Pi's
      `/trust`"). The new bullet does not contain `lean-ctx knowledge`.
      These stay green unmigrated: `pointer_findings`, `_lean_ctx_sections` (one section),
      `setup_task_findings`, and the last-task-is-`REPO_OWNER` check in
      `tests/test_project_setup_section.py`. No unit of the `## Setup` section names
      `lean-ctx index build` or `lean-ctx trust`.
- [ ] **§S5, the contract.** `contracts/lean-ctx.md`'s knowledge section passes:
      - `tests/test_execution_knowledge_rules.py`'s `CONTRACT_LEVERS`, `CONTRACT_NOT_STOPPED`,
        `CONTRACT_LEVERS_ROOT` and `CONTRACT_LARGER_CATEGORY` checks, unmigrated;
      - new pins, one unit each: `.lean-ctx.toml` with `modelb-axi init`, a `#` marker and
        `modelb-axi agents`; the five substring-merged names with `Config::merge_local` and
        `rust/src/core/config/merge.rs`; a re-render, the content hash and `lean-ctx trust`;
        `autonomy.silent_preload` with `true` and `Config::merge_local`.

      Each pin is proved both ways on synthetic text, one cut per pin.
- [ ] **§S6, the guide.** The `project-trust` region carries one paragraph naming `.lean-ctx.toml`,
      `modelb-axi agents` and `--force-managed`, in which a sentence says `lean-ctx trust` is not needed
      for the file (a negation, `no`, `not` or `never`, within 40 characters before `lean-ctx trust`, in
      the same sentence) and a separate clause names Pi's `/trust` as a different decision. The gate is
      proved both ways, one cut per item, plus a cut whose only negation sits in the `/trust` clause. These stay green: every existing
      `tests/test_install_guide.py` gate on the region, including the policy re-render paragraph
      (`CONFORMING_POLICY_RERENDER`); `generator/build.py --check`; `RegenerationCleanTest`
      (`tests/test_harness_neutral_skills.py`); and `PiPackageReadmeTest` (`tests/test_pi_package.py`).
- [ ] **§S7, Model B's own config** (PRD D5, ruled 2026-10-29). `git ls-files -- .lean-ctx.toml` at the
      repository root prints `.lean-ctx.toml`. Its text equals `render_config()`, and
      `ownership_state` is `intact`.
- [ ] **Migrations (RED).** These pins move with the change, each marked `# MIGRATED at CR-MDB-091 (§S…)`:
      - `tests/test_project_registry_schema.py` `_reference_other_files`: places the config into the
        reference scratch dir with `lean_ctx_config.place_project_config`, so
        `InitAgainstToday.test_the_emitted_file_set_is_todays` and
        `test_every_other_emitted_file_is_byte_identical_to_today` cover it (§S2, cycle 1);
      - `tests/test_agents_verb_permission_policy.py`
        `AgentsVerbPlacesThePolicyTest.test_an_absent_policy_is_written_after_the_agents_and_reported_in_written`:
        the expected `written` set is the agent files, the policy and the config (§S3, cycle 2);
      - `AGENTS.md`'s two module counts (`AgentsMdTestingSectionS6Test`, `tests/test_suite_hygiene.py`),
        in cycle 1's GREEN (§S8).

      RED greps `tests/` for `.lean-ctx.toml`, `plan_files` and the `agents` envelope's `written` before
      it commits, and lists every further pin it moved, by id.
- [ ] **Live check, before the merge.** In a Pi session in Model B's tree on the branch (after §S7), or
      in a sandbox project scaffolded on the branch, the orchestrator runs `ctx_knowledge` with
      `action=policy`. It reports `memory.knowledge.max_facts=500`. The observation goes into the merge
      sign-off; no test pins lean-ctx's output. `action=policy` shows only the knowledge policy, so the
      orchestrator may also read the merged `autonomy.auto_consolidate` from lean-ctx in that project;
      otherwise the second lever rests on the source reading in Context.
- [ ] **Runs.**
      - The suite is green through the client, with a real `HOME` and with an empty one; the empty `HOME`
        stays empty.
      - `ruff check` exits 0; `generator/build.py --check` is clean.
      - New tests use a literal `§`.
      - `AGENTS.md`'s counts and baselines match the measured suite.

## Non-goals

- **Per-stack index excludes** (`[index] exclude`, `extra_ignore_patterns`) (PRD D5, ruled 2026-10-29).
  `.gitignore`, which lean-ctx honours in every walker with or without `.git`, and
  lean-ctx's built-in skips already do this work. `[index] exclude` reaches only the index builders, and
  not one owned by the daemon. Stack build directories in the scaffolded `.gitignore` belong
  with `migrate` (CR-MDB-055), which can reach existing projects.
- **`preserve_compact_formats`** (PRD D5, ruled 2026-10-29). It is the default and is merged
  additively. CR-MDB-090 routes AXI output raw.
- **`lean-ctx index build` in the Setup section** (PRD D5, ruled 2026-10-29). The index builds itself on the
  first read (`ensure_all_background`, `rust/src/core/index_orchestrator.rs`).
- **Any security-sensitive key:** `shell_allowlist_extra` for the Crucible clients, `write_allow_paths`
  for report dirs, and the rest of `strip_sensitive_overrides`. Each needs `lean-ctx trust`, which is the
  user's decision. Closing the contract's two findings is CR-MDB-092's.
- **A per-project `excluded_commands` for the clients.** CR-MDB-090 deferred it here. It is a prefix
  match that `cd … &&` defeats, it still truncates above 4000 tokens, and `raw=true` already covers the
  case.
- **`autonomy.cognition_loop_enabled = false`** and every other unruled lever (`memory.lifecycle.*`,
  `autonomy.consolidate_every_calls`) (PRD D5, ruled 2026-10-29). Each needs its own ruling.
- **`recall_facts_limit` and `[memory.compaction]`.** Both are global-only.
- **A sub-project `.lean-ctx.toml`.** Its processes resolve the repository's git top level.
- **`.lean-ctx/` in the scaffolded `.gitignore`** (some lean-ctx features write project data there).
  Raised for CR-MDB-055's `migrate`, which can reach existing projects.
- **The `git-workflow` skill's post-release step.** It runs `modelb-axi agents` "to re-render its policy".
  The same run re-renders the config, so the skill is unchanged.
- **Running `lean-ctx` from Model B:** `trust`, `config set`, `index build`, `doctor --fix`. Model B only
  tells the user.
- **The migration verb's artifact list (CR-MDB-082), handed off.** CR-MDB-082's spec lists the agent
  definitions and the permission policy, not this config. When CR-MDB-082 is next revised it adds the
  config, placed through the same `place_project_config`, as §D27 rules for the policy; this CR edits
  neither CR-MDB-082's spec nor its code.
- **The `LEAN_CTX_KNOWLEDGE_MAX_FACTS` environment variable,** which beats the file. It is the user's.

## Cycle plan

No commit sits red: each cycle commits after its GREEN, with its migrations, once `ruff check` exits 0.
The full suite is not run between cycles. Each cycle runs only the modules it names, through the client.
Every cycle that edits `modelb_axi/` runs the package-wide gates `tests.test_installer_correctness`,
`tests.test_claude_era_retirement` and `tests.test_installer_stack_selection`.

1. **The render and `init`** (§S1, §S2, §S8's module count). Red-green. Runs
   `tests.test_lean_ctx_project_config`, `tests.test_project_registry_schema`,
   `tests.test_project_setup_section`, `tests.test_scaffold`, `tests.test_suite_hygiene`,
   `tests.test_suite_hermeticity`, the package-wide gates `tests.test_installer_correctness`,
   `tests.test_claude_era_retirement` and `tests.test_installer_stack_selection`, and the modules that
   read `init`'s emitted files: `tests.test_crucible_project_config`, `tests.test_scaffold_changelog`,
   `tests.test_init_release_workflow`, `tests.test_init_sandesh_address_and_envrc` and
   `tests.test_stack_skills`.
2. **`modelb-axi agents`** (§S3). Red-green. Runs `tests.test_lean_ctx_project_config`,
   `tests.test_agents_verb_permission_policy`, `tests.test_pi_agent_definitions`,
   `tests.test_stack_skills`, `tests.test_release_workflow_verb`, `tests.test_claude_era_retirement`,
   `tests.test_installer_correctness`, `tests.test_installer_stack_selection` and
   `tests.test_project_tools_setup`.
3. **The note, the contract, the guide and Model B's own config** (§S4, §S5, §S6, §S7). Red-green. Runs
   `tests.test_lean_ctx_project_config`, `tests.test_project_tools_setup`,
   `tests.test_project_setup_section`, `tests.test_project_registry_schema`,
   `tests.test_execution_knowledge_rules`, `tests.test_install_guide`, `tests.test_pi_package`,
   `tests.test_harness_neutral_skills`, `tests.test_installer_correctness`,
   `tests.test_claude_era_retirement` and `tests.test_installer_stack_selection`.
4. **Verify.** The full suite without coverage, as VERIFY's branch check (DN §D26), then the
   orchestrator's pre-merge gate and the live check.
