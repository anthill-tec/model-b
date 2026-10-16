# CR-MDB-077 — The generated permission policy allows the Sandesh tools

**Status:** PENDING — spec (gap analysis 2026-10-16).
**Type:** fix (`modelb_axi`: the requirements table, the per-project policy, the `agents` verb)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** none (board-authoritative: read `queue`)
**Labels:** permissions, sandesh, scaffold
**Design reference:** DN-multi-harness-deploy-model §D24 (and its 2026-10-16 rulings); CR-MDB-037
§S3 (the per-project policy); CR-MDB-025 §S6 (marker ownership).

## Context

- **The policy.** `modelb_axi.permission_policy.render_policy` renders a Pi project's
  `.pi/extensions/pi-permission-system/config.json`:
  - `"*": "ask"` is the fallback;
  - `allow` goes, by exact tool name, to the set `workflow_tools` builds. That set is the file tools,
    the UI and child-side tools, and the `tools` of the requirement rows named in
    `_TOOL_REQUIREMENTS`: `dispatch` and `lean-ctx`.
- **The Sandesh tools ask.** The `sandesh-pi` row (`@anthill-tec/sandesh-pi`, tier 1, required) has
  an empty `tools` tuple, so no Sandesh tool is allowed. The first use of each one in a session
  raises a permission prompt. An unattended prompt blocks the session until someone answers it.
- **The extension's tools,** as sandesh-pi 0.4.3 registers them:
  - `sandesh_setup`, `sandesh_register`, `sandesh_unregister`;
  - `sandesh_send`, `sandesh_reply`;
  - `sandesh_addressbook`, `sandesh_fetch`, `sandesh_inbox`, `sandesh_thread`, `sandesh_search`,
    `sandesh_status`;
  - `sandesh_notify_start`, `sandesh_notify_stop`, `sandesh_notify_status`;
  - `sandesh_archive`, `sandesh_unarchive`.
- **Only `init` writes the policy.** `scaffold.run_init`, through `_emit_plan`, calls
  `permission_policy.place_project_policy` for a Pi project. `modelb-axi agents` re-renders a
  project's agent definitions and never the policy. `init` must not be re-run on an existing
  project, so an existing project has no way to get a changed policy.
- **This repository's own policy** is committed at `.pi/extensions/pi-permission-system/config.json`.
  It is marker-owned, intact, and identical to today's render.
- **Who the change reaches.** A sub-agent's frontmatter `tools:` line limits it to its own tools, so
  allowing the Sandesh tools at project level reaches no sub-agent.

## Scope

### §S1 — The `sandesh-pi` row names the extension's tools

`modelb_axi/requirements.py`'s `sandesh-pi` row lists, in `tools`, the sixteen names above.

### §S2 — The policy allows them, except archive and unarchive

- `_TOOL_REQUIREMENTS` names `sandesh-pi` beside `dispatch` and `lean-ctx`.
- `permission_policy.py` declares an ask-set: `sandesh_archive` and `sandesh_unarchive`.
  `workflow_tools` leaves the ask-set's names out, whichever row supplies them.
- The Sandesh tools are allowed whether lean-ctx is present or not.

### §S3 — `modelb-axi agents` re-renders the policy

When the resolved harnesses include `pi`, `modelb-axi agents` places the project's permission
policy after its agent definitions:

- it uses the same ownership rules as `init`, through `place_project_policy`: a hand-modified policy
  is skipped unless `--force-managed`, and an unmarked one is never written;
- it uses the same lean-ctx verdict it uses for the agents, the one the installation recorded;
- the policy's project-relative path appears in the envelope's `written`, `unchanged`, `skipped` or
  `unmanaged` list, beside the agent files;
- a skipped or unmanaged policy gets the same warning a skipped or unmanaged agent file gets;
- `--stacks` changes nothing in the policy;
- the policy is placed only when `pi` is among the resolved harnesses, as `init` does. The roster is
  Pi alone (CR-MDB-031 §S1), so no `agents` run reaches the no-Pi case, and no test drives it;
- the policy is placed inside the same I/O-error handling as the agent definitions: an `OSError`
  exits 3 with an `ok: false` envelope naming the error and listing the files already written;
- a run refused in validation (exit 2) writes no policy.

The verb's help, its description and its stderr progress line name the permission policy.

### §S4 — The documentation

- **The install guide's `project-trust` region:**
  - the policy bullet says the Sandesh extension's tools are allowed, except archiving and
    unarchiving a project, which ask;
  - a paragraph says that `modelb-axi agents`, run from the project's root, re-renders the policy of
    an existing project, for example after upgrading Model B, and that a policy you have edited is
    left alone unless `--force-managed`.

  The guide names no `sandesh_*` tool (DN §D18).
- **The generated package README** (`pi-package/README.md`) is re-rendered from the guide's regions
  with `generator/build.py build`.
- **The git-workflow skill's post-release maintenance step** adds, after the reinstall: run
  `modelb-axi agents` in each existing project to re-render its policy. It names no `sandesh_*`
  tool.

### §S5 — This repository's own policy

This repository's `.pi/extensions/pi-permission-system/config.json` is re-rendered with the new
policy, for lean-ctx present, through `place_project_policy`.

## Acceptance criteria

- [ ] **§S1.** The `sandesh-pi` row's `tools` equals the set of the sixteen names in § Context. Every
      other row's `tools` is unchanged.
- [ ] **§S2, the rendered policy.** A project `init` renders for Pi:
      - allows exactly the file tools, the fixed workflow tools, `skill`, and the `tools` of the
        `dispatch`, `lean-ctx` and `sandesh-pi` rows minus the ask-set. Those names are read from
        `REQUIREMENTS` at render time;
      - has neither `sandesh_archive` nor `sandesh_unarchive` in its `permission` map, so both
        resolve to `"*": "ask"`;
      - with lean-ctx absent, still allows the fourteen Sandesh tools, alongside `bash`.
- [ ] **§S2, data-derived.** In-process, replacing the `sandesh-pi` row's `tools` with sentinel names
      changes the rendered allow-set to match, and the replaced names disappear. A `sandesh_archive`
      among the `sandesh-pi` sentinels, and one among the `dispatch` sentinels, are both left out.
- [ ] **§S3, the wired path.** `python3 -m modelb_axi agents`, run in a seeded sandbox project (a
      `.env` recording `PROJECT_STACKS`, and a sandbox `install.toml` recording the `pi` harness and
      a lean-ctx verdict):
      - writes the policy when it is absent, and reports it in `written`;
      - reports an identical policy in `unchanged`;
      - rewrites a policy from an older render that still carries its intact marker, and reports it
        in `written`;
      - skips a hand-modified policy and reports it in `skipped` with the ownership warning, and
        rewrites it under `--force-managed`;
      - never writes an unmarked policy, and reports it in `unmanaged` with the warning;
      - with the recorded lean-ctx verdict switched from `detected` to `absent`, rewrites the policy
        to the lean-ctx-absent render, which allows `bash` and names no `ctx_*` tool;
      - under `--stacks`, leaves an intact, current policy byte-identical and reports it in
        `unchanged`.

      A written policy equals `render_policy(lean_ctx=<the recorded verdict>)` computed under the
      subprocess's `HOME` and `PATH`. A skipped or unmanaged policy is byte-identical to its seed.
- [ ] **§S3, failure paths.**
      - A policy path that cannot be written (for example, `.pi/extensions` is a file) exits 3 with
        `ok: false` and a warning naming the error.
      - A run without a `.env` exits 2 and creates no policy.
- [ ] **§S3, text.** The `agents` subparser's help and description, and its stderr progress line,
      name the permission policy.
- [ ] **§S4, the guide.** Gates pin, in the install guide's `project-trust` region:
      - the list item naming `.pi/extensions/pi-permission-system/config.json` says the Sandesh
        extension's tools are allowed, and one of its sentences names archiving and unarchiving a
        project as asking;
      - a paragraph names `modelb-axi agents` in code, with `re-render`, `policy` and
        `--force-managed` in the same paragraph.

      A gate finds no `sandesh_*` tool name in the guide; it is proved both ways on synthetic text,
      and the guide's conforming fixture is extended to match. `generator/build.py --check` is clean.
- [ ] **§S4, git-workflow.** A gate pins, in the post-release maintenance step, `modelb-axi agents`
      run in each existing project to re-render its policy, after the reinstall. The step names no
      `sandesh_*` tool. The skill's frontmatter is unchanged, and the skills load in Pi with no
      diagnostics.
- [ ] **§S5.** This repository's committed policy equals `render_policy(lean_ctx=True)` on the branch,
      with its marker intact. VERIFY checks this; no test pins it, because the render depends on
      where `pi` is installed.
- [ ] **Migrations (RED).** The pins on the allow-set and on the `agents` verb's output move with
      them, each marked `# MIGRATED at CR-MDB-077 (§S…)`:
      - `tests/test_project_permission_policy.py`'s `expected_allow_tools` (§S2);
      - `PermissionPolicyReadsRequirementsDataTest`'s expected set (§S2);
      - `tests/test_project_tools_setup.py`'s `test_the_verb_follows_the_recorded_verdict_both_ways`:
        `written` gains the policy path (§S3).
- [ ] **Live check, before the merge.** The CR's feature branch is checked out in the main tree, the
      orchestrator's working directory, with this repository's policy re-rendered on it. The user
      runs `/reload` in the orchestrator's Pi session. The session's first call to `sandesh_status`
      then runs with no permission prompt, and pi-permission-system's review log records no
      `permission_request` for it.
- [ ] **Runs.**
      - The suite is green through the client, with a real `HOME` and an empty one; the empty
        `HOME` stays empty.
      - New tests use a literal `§`, never `\u00a7`.
      - The `AGENTS.md` counts and baselines match.

## Non-goals

- **The user's global policy** (`~/.pi/agent/extensions/pi-permission-system/config.json`). Model B
  never writes it. In an untrusted project only it applies, and it allows no Sandesh tool.
- **Command-scoped shell rules and the policy's wider rework.** These belong to CR-MDB-049, in
  release 1.1.0.
- **Descriptive mentions of `modelb-axi agents` that concern agent definitions only.** These are
  left alone:
  - `orchestration-common.md`'s "Older projects" bullet;
  - the model-b skill's registry list;
  - the rendered `AGENTS.md` stack lines;
  - the guide's `adding-stacks-later` region.
- **Sub-agent definitions.** Their `tools:` and `permission:` frontmatter are unchanged.
- **The `worktree` row's tools** (`modelb_worktree_enter`, `modelb_worktree_exit`) stay outside
  the allow-set: the ruling covers the Sandesh extension only. CR-MDB-049 reviews the extension tools
  the workflow needs.
- **A parity check against the installed sandesh-pi.** It would read the real home, which the suite's
  hermetic rule allows only for Crucible's clients and pi-subagents. A sandesh-pi upgrade that adds
  a tool is caught at the next gap analysis that touches the row.

## Cycle plan

1. **The policy allows the Sandesh tools (§S1, §S2).** Red-green.
2. **`modelb-axi agents` re-renders the policy (§S3–§S5).** Red-green.
3. **Verify.**
