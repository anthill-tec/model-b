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
- **Only `init` writes the policy.** `scaffold.run_init` calls
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
- The module's docstring names the three rows and the ask-set.

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
- without `pi` among the harnesses, no policy is written.

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
      changes the rendered allow-set to match, and the replaced names disappear. A sentinel set that
      includes `sandesh_archive` renders without it.
- [ ] **§S3, the wired path.** `python3 -m modelb_axi agents`, run in a sandbox project whose
      installation records the `pi` harness:
      - writes the policy when it is absent, and reports it in `written`;
      - reports an identical policy in `unchanged`;
      - rewrites a policy from an older render that still carries its intact marker, and reports it
        in `written`;
      - skips a hand-modified policy and reports it in `skipped` with the ownership warning, and
        rewrites it under `--force-managed`;
      - never writes an unmarked policy, and reports it in `unmanaged` with the warning.

      Each case's written file equals `render_policy` for the recorded lean-ctx verdict.
- [ ] **§S3, no Pi.** With no `pi` among the resolved harnesses, `agents` writes no policy and lists
      none.
- [ ] **§S3, text.** The `agents` subparser's help and description, and its stderr progress line,
      name the permission policy.
- [ ] **§S4.** Gates pin, in the install guide's `project-trust` region:
      - the Sandesh-tools sentence, with archive and unarchive asking;
      - `modelb-axi agents` named as the way to re-render an existing project's policy, with the
        edited-file rule.

      The guide names no `sandesh_*` tool. `generator/build.py --check` is clean.
- [ ] **§S5.** This repository's committed policy equals `render_policy(lean_ctx=True)` on the branch,
      with its marker intact. VERIFY checks this; no test pins it, because the render depends on
      where `pi` is installed.
- [ ] **Migrations (RED).** The pins that restate the allow-set move with it, each marked
      `# MIGRATED at CR-MDB-077 (§S2)`:
      - `tests/test_project_permission_policy.py`'s `expected_allow_tools`;
      - `PermissionPolicyReadsRequirementsDataTest`'s expected set.
- [ ] **Live check, before the merge.** With this repository's re-rendered policy on the branch, the
      user runs `/reload` in the orchestrator's Pi session. Then the session's first call to
      `sandesh_status` runs with no permission prompt, and pi-permission-system's review log shows
      no `permission_request` for it.
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

## Cycle plan

1. **The policy allows the Sandesh tools (§S1, §S2).** Red-green.
2. **`modelb-axi agents` re-renders the policy (§S3–§S5).** Red-green.
3. **Verify.**
