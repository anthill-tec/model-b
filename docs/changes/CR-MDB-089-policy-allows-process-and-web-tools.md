# CR-MDB-089 — The generated permission policy allows the process tool and the read-only web tools

**Status:** COMPLETED (filed, gap analysis and pre-review 2026-10-29).
**Type:** fix (`modelb_axi`: the requirements table, the per-project policy; the install guide)
**Priority:** P1 — release 1.0.0, wave 2, ahead of CR-MDB-088.
**Depends on:** none (board-authoritative: read `queue`)
**Labels:** permissions, scaffold, pi
**Design reference:** DN-multi-harness-deploy-model §D27 (user rulings 2026-10-29) and §D24 (the
derivation from requirement rows; `modelb-axi agents` re-renders the policy); CR-MDB-077 (its
implementation); CR-MDB-037 §S3 (the per-project policy); CR-MDB-025 §S6 (marker ownership).

## Context

- **The policy.** `modelb_axi.permission_policy.render_policy` renders a Pi project's
  `.pi/extensions/pi-permission-system/config.json`:
  - `"*": "ask"` is the fallback;
  - `allow` goes, by exact tool name, to the set `workflow_tools` builds: the file tools, the UI and
    child-side tools, and the `tools` of the requirement rows named in `_TOOL_REQUIREMENTS`
    (`dispatch`, `lean-ctx`, `sandesh-pi`), minus the ask-set.
- **Three tools the workflow uses ask.** The names were read from the installed packages' source,
  not their READMEs (`@ollama/pi-web-search`'s README names other tools than its code registers):
  - `process` supervises long runs: full test suites, the pre-merge gate, the clean runner, builds.
    `@mjakl/pi-processes` 2.5.0 registers it, and nothing else. Its `start` action runs any command
    it is given.
  - `web_fetch` and `web_search` read the web during research and gap analysis.
    `@ollama/pi-web-search` 0.0.5 registers them, and nothing else. Both call a local Ollama, which
    must be running and signed in. `web_fetch` fetches any URL.

  No requirement row names these packages, so the policy allows none of the three. The first use of
  each in a session raises a permission prompt. On 2026-10-29 a research sub-agent raised a run of
  them, and the user ruled (§D27).
- **New tier-1 rows are handled generically.** The pre-flight's probe, the harness line, the
  `[capabilities]` record, the interactive offers, the policy-driven WARN, and `init`'s tool verdicts
  and capability contract all loop over the rows. Only `MODELB_PI_PACKAGE` (the `worktree` row) is
  named in code.
- **Both policy writers already exist.** `init` places the policy for a new Pi project, and `modelb-axi
  agents` re-renders it for an existing one under the ownership rules (CR-MDB-077 §S3). A later
  migration verb (CR-MDB-082) is to render it through the same `place_project_policy`.
- **This repository's own policy** is committed at `.pi/extensions/pi-permission-system/config.json`.
  It is marker-owned, intact, and identical to today's render (checked at pre-review).
- **Who the change reaches.** A sub-agent whose frontmatter has a `tools:` line is limited to those
  tools, so the generated RED, GREEN, VERIFY and FIX agents gain no tool. A dispatch type without a
  `tools:` line (for example `general-purpose`) runs under the project's policy.

## Scope

### §S1 — Two requirement rows

`modelb_axi/requirements.py` gains two tier-1 rows, after `sandesh-pi`. Both have `tier` 1, `scope`
`"always"` and `probe` `"pi-package"`:

| id | provider | policy | tools | asset_families | remediation |
|---|---|---|---|---|---|
| `processes` | `@mjakl/pi-processes` | recommended | `("process",)` | `("orchestration skills' supervised long runs",)` | `pi install npm:@mjakl/pi-processes` |
| `web-search` | `@ollama/pi-web-search` | recommended | `("web_fetch", "web_search")` | `("research in gap analysis and spec review",)` | `pi install npm:@ollama/pi-web-search` |

Neither row has an `absent_effect`. The Ollama precondition is stated in the install guide only
(§S4).

**What follows from the generic handling.** No code changes for any of these:
- **The pre-flight.** Each row is probed through Pi's settings, and the harness line reports its
  verdict.
- **A missing package.** Each run without one WARNs `<id>=absent — <asset_families> is ignored`,
  naming its `pi install` remediation, and the run continues.
- **Interactive and `--yes` runs.** An interactive install with `pi` on `PATH` offers each missing
  package with a `[y/N]` prompt, and a decline is recorded as a warning. `--yes` installs neither,
  since both are third-party.
- **`install.toml`.** `[capabilities]` gains both keys.
- **`init`.** Its envelope's `tools` field gains both keys. The scaffolded `AGENTS.md`'s harness
  capability contract gains a line for each: `` `<id>` (recommended): <state> ``, plus the remediation
  when the package is not detected.
- **`init` on an older installation.** When `install.toml` predates the rows, `init`'s existing
  "records no verdict" note names them, and the two contract lines read `unknown`, until the
  installer is re-run.
- **Unchanged:** `init`'s `## Setup` section, `project_schema.toml` and the `agents` verb.

The two module docstrings that list the rows or the harness line are updated: `preflight`'s and
`permission_policy`'s.

### §S2 — The policy allows their tools

`_TOOL_REQUIREMENTS` names `processes` and `web-search`. The rendered policy allows `process`,
`web_fetch` and `web_search`, read from the rows at render time. It allows them whatever the packages'
own verdicts are and whether lean-ctx is present or not, as it allows the `dispatch` and `sandesh-pi`
tools. Allowing a tool the harness lacks is harmless. Nothing else changes: `bash` stays outside the
allow-set while lean-ctx is present, and the ask-set is unchanged.

### §S3 — Scaffold and migration

No new code path. `init` and `modelb-axi agents` both render through `place_project_policy`. A new
project gets the three tools at scaffold, and an existing project at its next `modelb-axi agents` run.
The ownership rules are unchanged: a hand-modified policy is skipped unless `--force-managed`.

### §S4 — The install guide and the generated README

The install guide (`docs/install-guide.md`) names the two packages wherever it lists the tier-1 Pi
packages:

- the quick-start `pi install` block;
- the prerequisites region: its count of Pi packages (five, becoming seven) and its list, each new
  package after "Pi" and marked recommended and third-party, the `web-search` one with its
  precondition: a local Ollama, running and signed in;
- the pre-flight region: its example `harness:` line and its count of Pi packages;
- the warnings table: a row per new id, carrying its `asset_families` string verbatim;
- the `missing-capabilities` region's sentence naming the recommended rows, which names all four
  (`permissions`, `worktree`, `processes`, `web-search`);
- the `project-trust` region's policy bullet: the policy also allows the process tool and the web
  tools. It names neither `web_fetch` nor `web_search`, and never `process` in code (DN §D18, as
  extended to the guide by CR-MDB-077).

The generated package README (`pi-package/README.md`) is re-rendered from the guide's regions with
`generator/build.py build`.

### §S5 — This repository's own policy

This repository's `.pi/extensions/pi-permission-system/config.json` is re-rendered with the new
policy, for lean-ctx present, through `place_project_policy`.

## Acceptance criteria

- [ ] **§S1, the rows.** `REQUIREMENTS` has `processes` and `web-search` rows with exactly the §S1
      table's fields and literal values, and neither has an `absent_effect`. Every other row is
      unchanged.
- [ ] **§S1, the pre-flight** (through `tests/pi_capability_sandbox.py`, with `HOME` and
      `PI_CODING_AGENT_DIR` at temp dirs):
      - with neither package provisioned, the harness line's verdict map has `processes=absent` and
        `web-search=absent`, each WARN names its `pi install npm:…` remediation and its
        `asset_families`, and the run continues;
      - under `--yes`, neither package is installed;
      - with both listed in the sandbox `settings.json` `packages[]` and present under
        `npm/node_modules/`, both report `detected`.
- [ ] **§S1, `init`.** A sandboxed `init` against an installation recording both verdicts renders a
      capability-contract line for each new id with its state, plus the remediation when the package
      is not `detected`. Its `tools` field has both keys. Against an `install.toml` without them, its
      "records no verdict" note names both ids.
- [ ] **§S2, the rendered policy.** A project `init` renders for Pi a policy that allows `process`,
      `web_fetch` and `web_search`, both with lean-ctx present and with it absent. `bash` is allowed
      only with lean-ctx absent, as today.
- [ ] **§S2, data-derived.** In-process, replacing either row's `tools` with sentinel names changes
      the rendered allow-set to match, and the replaced names disappear.
- [ ] **§S3, the wired path** (cycle 1, where the render first changes). `python3 -m modelb_axi
      agents`, run in a seeded sandbox project:
      - given a policy rendered without the three tools, its marker re-computed
        (`agents.sha256_text`) so it is intact, it rewrites the policy to the new render and reports
        it in `written`;
      - it skips a hand-modified policy and reports it in `skipped`.
- [ ] **§S4, the guide.** The guide's real-text gates pass with the new rows:
      - the prerequisites gate (every always-scoped row named, each tier-1 provider after "Pi");
      - the warnings gate (a line per row id carrying one of its `asset_families`).

      New gates pin:
      - both `pi install npm:…` lines in the quick-start block;
      - the Ollama precondition beside `web-search`;
      - the four recommended rows in `missing-capabilities`;
      - the `project-trust` bullet's process and web tools.

      A gate finds neither `web_fetch` nor `web_search` in the guide, and no `` `process` ``. It is
      proved both ways on synthetic text, as CR-MDB-077's `sandesh_*` gate is, and the guide's
      conforming fixture is extended to match. `generator/build.py --check` is clean.
- [ ] **§S5.** This repository's committed policy equals `render_policy(lean_ctx=True)` on the
      branch, with its marker intact. VERIFY checks this; no test pins it, because the render depends
      on where `pi` is installed.
- [ ] **Migrations (RED).** These pins move with the change, each marked
      `# MIGRATED at CR-MDB-089 (§S…)`:
      - `tests/pi_capability_sandbox.py`: `TIER1_PACKAGES` gains both providers, and
        `THIRD_PARTY_TIER1` gains both ids (§S1);
      - `tests/test_harness_capability_contract.py`: `RequirementsDeclarationTest._TABLE`, the
        harness dicts of the malformed-JSON, unrecognised-settings-shape, env-var-agent-dir,
        home-pi-agent and no-third-party-install checks, and
        `PreflightReportLinesTest.test_harness_line_is_exact_…` (§S1);
      - `tests/test_installer_sandesh_requirements.py`: `_OTHER_ROWS_TOOLS` (§S1);
      - `tests/test_modelb_pi_worktree_capability.py`: the tier-1 id→probe map (§S1);
      - `tests/test_scaffold.py`: `ScaffoldCapabilityContractTest`'s sorted tier-1 ids (§S1);
      - `tests/test_init_tool_verdicts.py`: `TIER1_IDS` and `EXPECTED_TOOL_IDS` (§S1);
      - `tests/test_project_tools_setup.py`: the unrecorded-tools list (§S1);
      - `tests/test_project_permission_policy.py`: `expected_allow_tools`, and
        `PermissionPolicyReadsRequirementsDataTest`'s expected set (§S2).
- [ ] **Live check, before the merge.** The branch is checked out in the main tree, with this
      repository's policy re-rendered on it. The user runs `/reload` in the orchestrator's Pi session.
      The session's next `process` call then runs with no permission prompt.
- [ ] **Runs.**
      - The suite is green through the client, with a real `HOME` and an empty one; the empty `HOME`
        stays empty.
      - New tests use a literal `§`.
      - The `AGENTS.md` counts and baselines match.

## Non-goals

- **The user's global policy.** Model B never writes it (§D27).
- **`bash`, and command-scoped shell rules.** `bash` stays on ask. `process` starts arbitrary
  commands, as a shell tool does, and `ctx_shell` is already allowed by name. CR-MDB-049's strict,
  command-scoped rework decides whether `process` is then treated as a shell tool.
- **An Ollama warning from the pre-flight.** `absent_effect` is read only for `path` rows. The
  precondition goes in the guide (§S4).
- **Sub-agent definitions.** Their `tools:` and `permission:` frontmatter are unchanged. Whether the
  generated agents should have `process` or more lean-ctx tools is CR-MDB-092's question.
- **Installing the packages.** Both are third-party: the installer offers them interactively and never
  installs them under `--yes`.
- **Other user-installed tools,** for example pi-lens's and pi-studio's. Only §D27's three tools are
  allowed; any other needs its own ruling.
- **A parity check against the installed packages.** It would read the real home, which the suite's
  hermetic rule allows only for Crucible's clients and pi-subagents. A package upgrade that renames a
  tool is caught at the next gap analysis that touches its row.
- **CR-MDB-082's migrate verb.** When it is built, it renders the policy through
  `place_project_policy`; this CR adds nothing to it.

## Cycle plan

1. **The rows, the policy, the `agents` re-render and the guide regions that list the rows** (§S1,
   §S2, §S3; §S4's quick-start, prerequisites, pre-flight, warnings and `missing-capabilities`
   regions, and the README re-render). Red-green. The guide moves in this cycle because its gates read
   the rows.
2. **The `project-trust` bullet and this repository's policy** (§S4's remaining bullet, §S5).
   Red-green.
3. **Verify.**
