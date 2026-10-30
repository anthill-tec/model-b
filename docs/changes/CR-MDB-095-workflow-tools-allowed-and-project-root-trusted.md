# CR-MDB-095 — Every workflow tool is allowed by default, and Model B trusts the project root

**Status:** PENDING — spec drafted 2026-10-30 from the gap analysis and the user's rulings
(DN-multi-harness-deploy-model §D27, amended 2026-10-30, with the rulings of CR-MDB-095's gap analysis).
Pre-review: ran — it touches another project's surface (Pi's `trust.json`), and the gap analysis needed
the user's rulings; its findings F1–F11 folded in 2026-10-30.
**Type:** feature (permission policy, requirements, project trust)
**Priority:** P1 — release 1.0.0, wave 2 (board-authoritative: read `queue`).
**Depends on:** nothing on the board.
**Labels:** pi, permissions, trust, requirements
**Points:** 8 (seeded 5; re-scored at gap analysis: a trust writer taking Pi's lock, `init`/`agents` wiring
and envelope fields, a requirement row, the policy, the install guide and its mirror, CR-MDB-037 §S4's
read-only rule reversed with its tests).
**Design reference:** DN-multi-harness-deploy-model §D27 and its amendment of 2026-10-30, with the rulings
of CR-MDB-095's gap analysis; §D25's 2026-10-30 amendment (the workflow's own tools); CR-MDB-037 §S3/§S4;
CR-MDB-077; CR-MDB-089.

## Context

The user ruled (§D27, 2026-10-30) that every tool providing the workflow's functionality is allowed by
default in the generated per-project policy, and that Model B trusts the project root it renders into, on
Pi. At this CR's gap analysis the user ruled that only pi-lens's read-only tools are allowed, that Model B
writes trust only where Pi would not already trust the root, and that the write fails safe.

Measured 2026-10-30:

- **The policy** (`modelb_axi/permission_policy.py`): `workflow_tools` allows the tools of the requirement
  rows in `_TOOL_REQUIREMENTS` (`dispatch`, `lean-ctx`, `sandesh-pi`, `processes`, `web-search`), less
  `ASK_TOOLS` (`sandesh_archive`, `sandesh_unarchive`). The `worktree` row (`modelb_axi/requirements.py`,
  tools `modelb_worktree_enter`, `modelb_worktree_exit`) is not among them, so its tools ask.
- **pi-lens 4.4.7** (`npm:pi-lens` in Pi's `settings.json` packages; `node_modules/pi-lens`) registers 13
  Pi tools: `ast_grep_search`, `ast_grep_replace`, `ast_grep_outline`, `lsp_navigation`,
  `lens_diagnostics`, `lens_diagnostic_mark`, `symbol_search`, `module_report`, `project_report`,
  `read_symbol`, `read_enclosing`, `effective_config`, `pi_lens_activate_tools`. Five are situational
  (inactive until `pi_lens_activate_tools`): `ast_grep_search`, `ast_grep_replace`, `ast_grep_outline`,
  `lsp_navigation`, `lens_diagnostic_mark`. Three can write to the project: `ast_grep_replace`,
  `lsp_navigation` (rename), `lens_diagnostic_mark` (an inline ignore comment). No requirement row names
  pi-lens. The `pi-package` probe (settings `packages[]` lists `npm:<provider>`, and
  `<agent-dir>/npm/node_modules/<provider>/package.json` exists) finds it by provider `pi-lens`.
- **The worktree write boundary** (`hooks-src/scripts/block-write-outside-worktree`) gates the neutral
  `write` and `edit` classes; the compiled Pi wiring maps `write`, `edit`, `ctx_edit` and `ctx_patch` to
  them, and no pi-lens tool.
- **Pi 1.4.0's trust store** (`@earendil-works/pi-coding-agent/dist/core/trust-manager.js`):
  `<agent-dir>/trust.json`, keyed by the canonical absolute path (`canonicalizePath(resolvePath(cwd))`),
  values `true`, `false` or `null`; the nearest entry walking from the directory up wins. Reads and writes
  hold proper-lockfile's lock: `lockfile.lockSync(<agent-dir>, {realpath: false, lockfilePath:
  "<agent-dir>/trust.json.lock"})` — a lock directory — with 10 attempts 20 ms apart. Pi writes the
  object with its keys sorted, `JSON.stringify(sorted, null, 2)` and a trailing newline. A malformed file
  or a value outside `true`/`false`/`null` is an error to Pi.
- **Model B today** (`modelb_axi/project_trust.py`, CR-MDB-037 §S4) only reads that decision:
  `resolve_trust` returns `trusted | untrusted | ask | unknown`, and `init` reports it as `trust` in its
  envelope when it wrote under `.pi/extensions/`, warning (`UNTRUSTED_WARNING`) for `untrusted` and `ask`.
  `agents` reports nothing. The user's own `trust.json` holds `"/home/antonyj": false`, so every new
  project starts untrusted.
- **The text that says Model B never changes `trust.json`, or that the user must run `/trust`:**
  `docs/install-guide.md` § Project trust (its `install-guide:begin project-trust` region) and its mirror
  in `pi-package/README.md`; the scaffolded `AGENTS.md` capability contract's "project trust (Pi)" line
  (`modelb_axi/scaffold.py`); `project_trust.py`'s module docstring; `scaffold.py`'s comment at the trust
  report.
- **Pinned by:** `tests/test_project_permission_policy.py` (the allow-set, the ask-set, the rows),
  `tests/test_harness_capability_contract.py` (the requirement rows),
  `tests/test_modelb_pi_worktree_capability.py` (the `worktree` row), `tests/test_project_trust.py` (the
  resolver; "§S4: Model B never edits trust.json"), `tests/test_install_guide.py` (the guide's regions and
  the mirror), `tests/test_project_setup_section.py` and `tests/test_project_tools_setup.py` (the
  scaffolded `AGENTS.md`).

**Baseline:** CR-MDB-096's pre-merge gate, 2026-10-30 (develop since moved only by docs: CR-MDB-096's
status flip and this spec, their doc gates passing): 4808 tests, 4807 passed, 0 failed, 1 skip; 114
modules.

## Scope

### §S1 — The policy allows every workflow tool, and only pi-lens's read-only ones

1. **The `worktree` row joins `_TOOL_REQUIREMENTS`:** `modelb_worktree_enter` and `modelb_worktree_exit` are
   allowed.
2. **A `code-intelligence` requirement row** in `modelb_axi/requirements.py`: tier 1, provider `pi-lens`,
   policy `recommended`, scope `always`, probe `pi-package`, asset families `("orchestrator sessions' code
   navigation",)`, remediation `pi install npm:pi-lens`, `tools` the 13 tools the package registers (the
   Context's list). Third-party: the installer names its remediation and never installs it (as the
   `processes` and `web-search` rows, CR-MDB-089).
3. **`code-intelligence` joins `_TOOL_REQUIREMENTS`,** and **`ASK_TOOLS` gains the three write-capable
   tools** (`ast_grep_replace`, `lsp_navigation`, `lens_diagnostic_mark`), so they stay at `"*": "ask"`
   whichever row supplies them. The other ten are allowed.
4. Every project gets the change through `init` and `modelb-axi agents`, which render the policy through
   `render_policy` (§D24, §D27).

### §S2 — `init` and `agents` trust the project root on Pi

1. **A writer in `modelb_axi/project_trust.py`:** `trust_root(target, agent_dir, *, force_managed=False,
   dry_run=False) -> dict` returns `{"trust_write": <outcome>, "trust": <state>}` and, where it wrote
   nothing for a reason, `"reason": <text>`. It never raises. Outcomes, decided in this order:
   - `planned` — `dry_run`; nothing is read under a lock, nothing is written, no lock is taken;
   - `refused` — the lock stays held after the retries; `reason` says so and, when the lock directory is
     older than 10 s, that it looks left behind and that starting Pi in the project clears it (Pi reclaims
     a lock older than 10 s);
   - then, **under the lock**, from that one read:
     - `refused` — `trust.json` cannot be read or parsed, is not a JSON object, or holds a value other
       than `true`, `false` or `null` (`reason` names which);
     - `unchanged` — Pi's resolution for the root (the closest entry in that read, else
       `defaultProjectTrust`) is already `trusted`;
     - `left` — the root's own key holds `false` and `force_managed` is false;
     - `written` — the root's key is set to `true`;
   - `refused` — any `OSError` on the way (the agent dir, the lock, the temporary file, `os.replace`),
     `reason` naming it; a failed lock release is not an error (the outcome stands).

   Nothing is written in any outcome but `written`. `trust` is `resolve_trust`'s state after the step.
2. **The key** is `str(Path(target).resolve())`, Pi's canonical form for a path whose links resolve.
3. **The lock** is Pi's own: `os.mkdir(<agent-dir>/trust.json.lock)`, with 10 attempts 20 ms apart while
   it exists; released by `os.rmdir` in a `finally`. A lock directory Model B did not create is never
   removed. `<agent-dir>` is created when absent (as Pi's `mkdirSync(..., {recursive: true})`).
4. **The write**, under the lock, from the read that decided the outcome (absent file → `{}`): set the
   key, and write the object with its keys sorted, `json.dumps(..., indent=2, ensure_ascii=False)` and a
   trailing newline (Pi's form, non-ASCII written as is), through a temporary file and `os.replace` — the
   project's atomic-write convention. When `trust.json` is a symbolic link, the write goes to its resolved
   target (the temporary file beside it), so the link stays a link, as Pi's write through the link leaves
   it; an existing file keeps its mode. Every other entry, `null` values included, is kept as it was.
5. **`init`** calls `trust_root(target, resolve_agent_dir(), force_managed=…, dry_run=…)` when Pi is
   among the run's harnesses, in place of the bare `resolve_trust` call: its envelope carries `trust` (as
   today, a state string) and `trust_write`. It no longer depends on the run having written under
   `.pi/extensions/`. It runs after the files are emitted, so the target exists.
6. **`modelb-axi agents`** does the same when Pi is among the installation's harnesses: its envelope gains
   `trust` and `trust_write`. An outcome of the trust step never changes either verb's exit code or `ok`.
   (Pi is the roster's only harness, so in practice both always run the step.)
7. **Warnings** (stderr and the envelope's `warnings[]`, as today):
   - `left`: the root has a saved `false` that Model B left; run `/trust` in Pi from the project root, or
     re-run with `--force-managed`;
   - `refused`: `trust.json` was not written, with the reason; run `/trust` in Pi from the project root;
   - `UNTRUSTED_WARNING` keeps its text and is emitted when the final `trust` is `untrusted` or `ask` and
     neither warning above was — exactly one warning names `/trust` per run.
8. **Never touched:** any other key; the user's `settings.json`; the installer (`modelb-axi --yes`) trusts
   nothing.

### §S3 — The text says so

1. **`docs/install-guide.md` § Project trust** (its marked region) and its mirror in
   `pi-package/README.md`: `init` and `modelb-axi agents` record the project root as trusted in
   `~/.pi/agent/trust.json` unless Pi already trusts it; a saved `false` for that exact root is left, and
   reported, unless `--force-managed`; a locked or unreadable `trust.json` is left, with a warning; the
   summary reports `trust` and `trust_write`; `/trust` remains the remedy for the cases left alone. The
   sentence "Model B never changes `trust.json`" goes.
2. **The scaffolded `AGENTS.md` capability contract's "project trust (Pi)" line:** `init` and
   `modelb-axi agents` record the project root as trusted unless a saved `false` stands; otherwise run
   `/trust` in Pi from the project root.
3. **`project_trust.py`'s module docstring** and **`scaffold.py`'s comment** at the trust step describe
   the writer; "read-only" and "never edits trust.json" go.
4. **The hooks note** `hooks.compile_wiring` writes into every scaffolded `hooks/README.md` ("pi loads
   .pi/extensions/*.ts only after the project-TRUST prompt …; regeneration re-triggers the trust
   re-confirm step"): Pi loads them only in a trusted project, and `init` and `modelb-axi agents` record
   the project root as trusted unless a saved `false` stands. The re-confirm clause goes (Pi 1.4.0 keys
   trust by path, with no content hash).
5. **The pi-lens tools** are named only through the requirement row; no skill or template text changes.

### §S4 — The gates this change moves (named migrations)

1. `tests/test_project_permission_policy.py`: the allow-set gains the two worktree tools and the ten
   read-only pi-lens tools; the ask-set gains the three write-capable ones; the declared rows include
   `code-intelligence`.
2. `tests/test_harness_capability_contract.py`: the `code-intelligence` row's fields.
3. `tests/test_project_trust.py`:
   - MIGRATED "§S4: Model B never edits trust.json" to the writer's outcomes;
   - the resolver keeps unit tests calling `resolve_trust` directly;
   - MIGRATED the `init`-driven cases whose outcome the writer changes:
     `test_closest_ancestor_false_entry_is_untrusted_and_warns` and
     `test_string_prefix_that_is_not_an_ancestor_does_not_decide` (now `written`, `trusted`, no warning),
     `test_no_entry_and_no_setting_is_ask_and_warns` (now `written`, `trusted`),
     `ProjectTrustFieldPresenceTest`'s dry run (now `trust` and `trust_write: planned`); the no-Pi half
     stays retired (CR-MDB-031 §S1).
4. `tests/test_stack_skills.py` `StackSkillsTrustSurfacesTest`: the root's own `false` → `left`, exactly
   one `/trust` warning.
5. `tests/test_ide_overlay_retirement.py`: its `_run_init` sandboxes `PI_CODING_AGENT_DIR` (it reads the
   real agent dir today).
6. `tests/test_project_tools_setup.py`: the `code-intelligence` row in the unrecorded-rows list and its
   capability-contract line (as CR-MDB-089 did for its rows).
7. `tests/test_install_guide.py`, `tests/test_project_setup_section.py`, `tests/test_hooks_compiler.py`:
   the §S3 texts.

No test module is added. No skip is added. No floor is lowered. Every test sandboxes
`PI_CODING_AGENT_DIR`; none reads or writes the real `~/.pi/agent/trust.json`.

## Acceptance criteria

- [ ] **AC1 — the policy (§S1).** `workflow_tools()` contains `modelb_worktree_enter`,
      `modelb_worktree_exit` and the ten read-only pi-lens tools, and none of `ast_grep_replace`,
      `lsp_navigation`, `lens_diagnostic_mark`, `sandesh_archive`, `sandesh_unarchive`; the rendered
      policy maps each of the three write-capable tools to nothing (they resolve to `"*": "ask"`);
      `bash` is still absent with lean-ctx present.
- [ ] **AC2 — the row (§S1.2).** `requirement("code-intelligence")` has exactly the §S1.2 fields, its
      `tools` the 13 names; the installer's pre-flight probes it as `pi-package`; when it is absent the
      installer warns with its remediation, offers `pi install npm:pi-lens` interactively and runs it only
      on an explicit yes, and never runs it under `--yes` (as `processes`). `init` against an
      `install.toml` that records no verdict for it reports so, and the scaffolded capability contract
      carries a `code-intelligence` line with its state and remediation.
- [ ] **AC3 — the writer's outcomes (§S2.1–§S2.4)**, each in a sandboxed agent dir:
      - no `trust.json` → `written`; the file then holds exactly `{"<root>": true}` in Pi's form;
      - an ancestor's `false` (`{"<parent>": false}`) → `written`; the parent's entry stays;
      - an ancestor's `true`, or no entry with `settings.json` `defaultProjectTrust` `always` →
        `unchanged`, the file byte-identical;
      - the root's own `false` → `left` (byte-identical); with `force_managed` → `written`;
      - malformed JSON, a JSON array, a value `"yes"` → `refused`, byte-identical, `reason` naming the
        fault;
      - `<agent-dir>/trust.json.lock` present for the whole retry window → `refused`, byte-identical, the
        lock directory still present afterwards; with the lock directory's mtime older than 10 s, the
        `reason` says it looks left behind and that starting Pi clears it;
      - an agent dir that does not exist → created, `written`;
      - an agent dir that cannot be written (mode `0o500`) → `refused`, `reason` naming the error, no
        exception, no lock left behind;
      - `dry_run` → `planned`, no file and no lock created;
      - a `null` entry and unrelated entries survive a `written` step unchanged;
      - a target reached through a symlink is keyed by its resolved path;
      - a root whose path holds a non-ASCII character is written as is (no `\u` escape);
      - a `trust.json` that is a symbolic link stays a link after `written`, and its target holds the entry;
      - the written file is Pi's form: keys sorted, two-space indent, a trailing newline;
      - after `written`, `resolve_trust` returns `trusted` for the root.
- [ ] **AC4 — `init` and `agents` (§S2.5–§S2.7).** With Pi among the harnesses, each envelope carries
      `trust` and `trust_write`; `init --dry-run` reports `planned` and writes nothing; each warning of
      §S2.7 is emitted exactly when its outcome occurs, and exactly one warning names `/trust` in a run
      that emits any; a `refused` outcome leaves `ok` true and the exit code 0.
- [ ] **AC5 — the texts (§S3).** The guide's region and its mirror state §S3.1 and no longer say
      "Model B never changes `trust.json`"; the mirror gate passes; the scaffolded capability-contract
      line states §S3.2; the hooks note states §S3.4 with no re-confirm clause; the docstring and comment
      no longer say read-only.
- [ ] **AC6 — standing gates.** `ruff check` exits 0; no test module and no skip is added; every module
      the cycle plan names passes through the client; no test touches the real `~/.pi/agent`; VERIFY runs
      the full suite through the client with a real `HOME` and an empty one, and the empty `HOME` stays
      empty.

## Non-goals

- **The three write-capable pi-lens tools** stay on ask; routing them into the worktree hook's `edit`
  class is not done (§D27, 2026-10-30).
- **Agent definitions' tool grants** (`modelb_axi/agents.py` `PI_TOOL_NAMES`, the role templates) are
  unchanged: the policy allows the tools in the orchestrator's session; no role is granted a pi-lens or
  worktree tool.
- **The user's global policy and `settings.json`** are not written (CR-MDB-038 §S3, §D27).
- **A stale-lock reclaim:** a lock Model B did not take is never removed.
- **A test reading back through Pi's own `ProjectTrustStore`** (Node): it would need `node` and Pi's
  package, absent on the clean runner, and so a new skip. The spec pre-review verified in a `/tmp` sandbox
  that Pi 1.4.0 reads a Model B write, honours Model B's lock directory and keys a symlinked root as
  `Path.resolve()` does; the tests pin Pi's form, key and lock in Python.
- **`bash`** stays on ask.

## After merge

None of these steps is an acceptance criterion.
1. The user reinstalls the tool (`uv tool install --reinstall --python 3.14 .`): the package changed.
2. Each project re-renders its policy and gets its root trusted with `modelb-axi agents`.

## Cycle plan

RED commits its failing tests on their own (test-only), and GREEN makes them pass in the same cycle, once
`ruff check` exits 0 (PRD D5, 2026-10-29). Nobody runs the full suite between cycles; VERIFY runs it once.
Each cycle runs, through the client, the modules it names plus the docs gates of `AGENTS.md`
(`tests.test_client_path_anchoring`, `tests.test_project_registry_schema`, `tests.test_suite_hygiene`,
`tests.test_archive_mapping`, `tests.test_cite_by_symbol`, `tests.test_harness_neutral_skills`,
`tests.test_axi_envelope_read_whole`, `tests.test_orchestration_rules_from_crucible`,
`tests.test_raw_runner_guard`, `tests.test_tooling_detachment`, `tests.test_claude_era_retirement`,
`tests.test_prd_criteria`). A module found reading an edited file and not named is run too, and named in
the cycle's report.

1. **The policy and the row** (§S1, §S4.1–§S4.2). Red-green.
   - **RED:** AC1, AC2. **GREEN:** `requirements.py`, `permission_policy.py`.
   - **Modules:** the docs gates, plus `tests.test_project_permission_policy`,
     `tests.test_harness_capability_contract`, `tests.test_modelb_pi_worktree_capability`,
     `tests.test_init_tool_verdicts`, `tests.test_installer_sandesh_requirements`,
     `tests.test_agents_verb_permission_policy`, `tests.test_project_tools_setup`.
2. **The trust writer** (§S2, §S4.3). Red-green.
   - **RED:** AC3, AC4. **GREEN:** `project_trust.py`, `scaffold.py` (`init`, `agents`).
   - **RED** also makes §S4.3–§S4.5's migrations.
   - **Modules:** the docs gates, plus `tests.test_project_trust`, `tests.test_scaffold`,
     `tests.test_agents_verb_permission_policy`, `tests.test_init_tool_verdicts`,
     `tests.test_stack_skills`, `tests.test_ide_overlay_retirement`.
3. **The texts** (§S3, §S4.4). Red-green.
   - **RED:** AC5. **GREEN:** the guide's region, its mirror, the scaffolded line, the hooks note
     (`modelb_axi/hooks.py`), the docstring and the comment.
   - **Modules:** the docs gates, plus `tests.test_install_guide`, `tests.test_project_setup_section`,
     `tests.test_project_tools_setup`, `tests.test_pi_package`, `tests.test_hooks_compiler`.
4. **Verify.** VERIFY runs the full suite once, without coverage, through the client, with a real `HOME`
   and an empty one, and reads every AC. The orchestrator then runs the pre-merge gate and records the
   `AGENTS.md` baselines at close-out.
