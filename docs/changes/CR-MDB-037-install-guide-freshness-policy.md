# CR-MDB-037 — Install guide, deployed-asset freshness, the per-project permission policy, and project trust

**Status:** PENDING (split from CR-MDB-036, 2026-09-24; rewritten at its own gap-analysis the same
day, user rulings — earlier text is git history and is not to be consulted for contracts)
**Type:** feature
**Priority:** P1 — in release 1.0.0, wave 2
**Depends on:** CR-MDB-036 (merged: the guide documents its pre-flight, and §S3 derives tool names
from its `REQUIREMENTS`)
**Labels:** installer, scaffold, docs, pi, permissions, trust, feature
**Phase:** Wave 5 (repo queue) · release 1.0.0 wave 2 (Crucible board)
**Design reference:** PRD D11 · CR-MDB-036 (`modelb_axi/requirements.py`, `toolchains.run_on_terminal`)
· CR-MDB-033 §S6 (install envelope outcomes) · CR-MDB-025 §S6 (per-project rendering and ownership
markers) · CR-MDB-030 (per-project hook extensions) · DN-multi-harness-deploy-model §D17 · Pi
`docs/security.md` §Project trust · `@gotgenes/pi-permission-system` `docs/configuration.md`,
`docs/migration/0644-project-trust-gating.md`

**Target set:** Pi only (DN §D13/§D14).

## Context — measured 2026-09-23/24

- `model-b` has no `README.md`, and no document explains an install to someone who has never read
  a CR.
- All six orchestrator skills deployed here differ from their repo source and still teach a retired
  `--phase` flag; nothing reported it. This machine's `install.toml` (the July `0.1.0.dev0` install)
  predates CR-MDB-033 and has **no `target_root`**, and its manifest still lists
  `crucible-report-vscode`, whose source CR-MDB-024 deleted.
- **Pi project trust.** Pi loads `.pi/settings.json`, `.pi/extensions`, `.pi/skills`, `.pi/prompts`
  and `.pi/themes` from a project only when the project is trusted. The decision is, in order: a
  command-line `--approve`/`--no-approve`; an extension handling `project_trust`; the saved decision
  for the directory **or its closest ancestor** in `<agent-dir>/trust.json`; else the setting
  `defaultProjectTrust` (`ask` by default). `.pi/agents/` is not a protected resource. Here
  `trust.json` holds `"/home/antonyj": false`, so every project under the home directory is
  untrusted, and its `.pi/extensions` are skipped **without a prompt**. That silently disables
  CR-MDB-030's per-project hooks in every scaffolded project on this machine.
- **The permission system's scopes.** Global
  `<agent-dir>/extensions/pi-permission-system/config.json`, project
  `<cwd>/.pi/extensions/pi-permission-system/config.json`. Precedence (later wins): global config,
  project config, global agent frontmatter, project agent frontmatter; the `permission` object
  deep-shallow merges. The project scope loads **only in a trusted project**. An invalid
  non-global scope fails closed: every `allow` is clamped to `ask`. The loader strips `//` comments
  before parsing (`config-loader.ts`), and the top level is a strict object, so an unknown key
  makes the file invalid.
- With the permission system and no suitable policy, background children's `ask` prompts reached
  the user for every access outside the working directory and every skill read; an omitted `"*"`
  means `"ask"`, and a `"*": "allow"` fallback is warned against by the package.
- `preflight._install_sandesh` captures and discards `uv tool install sandesh-relay` output, and is
  the one confirmed install that is not re-probed (CR-MDB-036 C5 VERIFY finding 6).

## Scope

### §S1 — One install guide, the single source
`docs/install-guide.md` covers, for someone on a fresh machine:

- prerequisites in dependency order;
- the stack selector (`--stacks`, the interactive offer) and what a stack does and does not
  install;
- every pre-flight line (`harness:`, `deps:`, `stack <name>:`) and each verdict (`detected`,
  `absent`, `unknown`, `installed`);
- the consequence of each WARN, stated as what will not work;
- the install offers (`pi install`, toolchain installers) and that `--yes` never confirms them;
- `--allow-missing-capabilities`;
- every install outcome, including `preflight_failed` and `stacks_rejected`;
- that deploying into the real home directory takes an explicit `--target-root ~`;
- widening the stack selection later;
- **project trust:** what it gates, why a scaffolded project's hooks and permission policy do not
  load until the project is trusted, and how to trust it (`/trust`).

Other surfaces take their install text from it:

| Surface | How it gets the content |
|---|---|
| Repo `README.md` | a short project description and a pointer to the guide; no install instructions of its own |
| GitHub release notes | the guide's marked regions, copied verbatim at release time |
| The Pi package README | the same marked regions, copied at publish time (CR-MDB-029 §S1) |

The guide carries explicitly marked regions, with the marker convention documented in the file. The
review of the documentation happens at the release (user ruling 2026-09-22).

### §S2 — Deployed assets report their state
Against the manifest and the package the installer is running from, a deployed asset is:

- **current** — deployed hash = manifest hash = packaged source hash;
- **stale** — deployed = manifest, but the packaged source has changed; the remedy is a re-run;
- **hand-modified** — deployed ≠ manifest; the remedy is the user's (`--force-managed`);
- **retired** — in the manifest, but the package no longer ships a source for it (e.g.
  `crucible-report-vscode`); the remedy is the user's to remove.

Running bare `modelb-axi` on an installed machine (the `already_installed` outcome) reports `stale`,
`hand_modified` and `retired` as lists of target-root-relative paths in its envelope. When
`install.toml` records no `target_root` (an install older than CR-MDB-033), the envelope carries a
`freshness: unknown` field and a warning naming the re-run, and guesses no location. No new verb.

### §S3 — The workflow permission policy, rendered per project (user ruling 2026-09-24)
`init` renders `<target>/.pi/extensions/pi-permission-system/config.json` for every project with Pi
among its harnesses. The policy:

- `"*": "ask"` as the explicit fallback, and no `"*": "allow"`;
- `allow` by exact tool name for: the tools CR-MDB-036's `REQUIREMENTS` lists for `dispatch` and
  `lean-ctx` (derived from that data, never restated); the built-in file tools; `todo`,
  `ask_user_question`, and the child-side `notify_parent`, `ask_parent`;
- `skill: allow`; `external_directory_read` allowing `~/.agents/*`, `~/.crucible/*`,
  `~/.pi/agent/*`, the installed harness's own code (`~/.bun/install/*` for a bun-installed Pi) and
  `/tmp/*`; `external_directory_write` allowing `/tmp/*`; both else `ask`.

The file is JSON carrying CR-MDB-025 §S6's ownership marker as a leading `//` comment — the loader
strips comments; a marker key would make the file invalid and clamp the project to `ask`. The
ownership rules are CR-MDB-025 §S6's: write if missing, rewrite if the marker is intact, skip a
hand-edited file unless `--force-managed`, never write an unmarked file. The file contains only
top-level keys the package's schema declares.

The installer also reports whether the **global** config is `absent`, lacks the `"*"` fallback
(`no-fallback`), lacks workflow tools (`missing-tools`, naming them), is `ok`, or cannot be parsed
(`unknown`) — the global policy is what applies in an untrusted project — and never writes it.

An extension tool's access direction is unproven to the permission system, so it is checked against
both the read and the write policy; reads outside the project are made with the built-in tools
(CR-MDB-025 §S5). No write allowance outside `/tmp` is added to silence those prompts.

### §S4 — `init` reports project trust (user ruling 2026-09-24)
When `init` writes anything under `<target>/.pi/extensions/` (CR-MDB-030's hooks, §S3's policy), it
resolves Pi's **saved** trust decision for the target: the entry for the target or its closest
ancestor in `<agent-dir>/trust.json`, else `defaultProjectTrust` from `<agent-dir>/settings.json`
(`ask` when unset). The agent dir is `$PI_CODING_AGENT_DIR`, else `~/.pi/agent`. It reports
`trust: trusted | untrusted | ask | unknown` in its envelope. For `untrusted` or `ask` it WARNs that
the project's hooks and permission policy will not load until the project is trusted, naming
`/trust`; an unreadable or unrecognised file gives `unknown` and never a crash. The report is of the
saved decision only; a command-line override or an extension can still decide differently, and the
warning says so. Model B never edits `trust.json`.

The scaffolded `AGENTS.md` capability section (CR-MDB-036 §S6) gains one line: the project's hooks
and permission policy need project trust, with the remediation `/trust`.

### §S5 — The Sandesh install reports and re-probes
`uv tool install sandesh-relay`, run on confirmation, sends its output to the user's terminal
(CR-MDB-036's `run_on_terminal`) rather than discarding it, and a confirmed install is re-probed
before `installed` is recorded; otherwise `absent` with a warning.

## Acceptance criteria

### §S1
- [ ] `docs/install-guide.md` covers every item §S1 lists, each checked by a gate over its headings
      or named terms (`--stacks`, `--allow-missing-capabilities`, `preflight_failed`,
      `stacks_rejected`, `--target-root ~`, `/trust`).
- [ ] Its regions are marked for extraction, and the marker convention is documented in the file.
- [ ] `README.md` exists, describes the project in a few lines and points at the guide; it carries
      no installer commands — a gate asserts the pointer and the absence of `modelb-axi` command
      lines.
- [ ] `skills-src/git-workflow/SKILL.md` §Releases names two release steps: copying the guide's
      marked regions verbatim into the release notes, and a documentation review over the doc set.
- [ ] CR-MDB-029 §S1 names the guide's marked regions as the source of the Pi package README.
- [ ] The guide's instructions carry no §S references, CR ids or internal vocabulary.

### §S2
- [ ] Stale: a deployed skill left as installed with its packaged source changed is listed under
      `stale` only.
- [ ] Hand-modified: a deployed skill edited by hand is listed under `hand_modified` only.
- [ ] Retired: a manifest entry whose packaged source no longer exists is listed under `retired`
      only.
- [ ] With nothing changed, all three lists are empty.
- [ ] An `install.toml` without `target_root` yields `freshness: unknown` and a warning naming the
      re-run, and reads no deployed file.

### §S3
- [ ] `init` with Pi among the harnesses writes `.pi/extensions/pi-permission-system/config.json`;
      with no Pi, it writes none.
- [ ] The rendered file parses as JSON after `//` comments are stripped, carries the ownership
      marker as a leading `//` comment, has only top-level keys the package's schema declares, has
      `"*": "ask"`, has no `"*": "allow"`, and allows exactly the §S3 tools — the `dispatch` and
      `lean-ctx` names read from `REQUIREMENTS`, asserted by mutating that data in-process.
- [ ] Ownership, one subtest per rule (missing → written; intact → rewritten; hand-edited →
      skipped, then rewritten with `--force-managed`; unmarked → never written).
- [ ] The installer's envelope reports the global config as `absent`, `no-fallback`,
      `missing-tools` (naming them), `ok` or `unknown`, one test each, against a sandboxed
      `PI_CODING_AGENT_DIR`; the file is byte-identical afterwards.

### §S4
- [ ] `init` writing under `.pi/extensions/` reports `trust:` with one test per case: an exact
      `true` entry → `trusted`; a closest-ancestor `false` entry (the `/home/antonyj` shape) →
      `untrusted`; no entry and no setting → `ask`; `defaultProjectTrust: "always"` → `trusted`;
      malformed `trust.json` → `unknown`, no crash. All against a sandboxed `PI_CODING_AGENT_DIR`.
- [ ] `untrusted` and `ask` WARN naming what will not load and `/trust`, and state that an
      override or extension may decide otherwise; `trust.json` is byte-identical afterwards.
- [ ] `init` writing nothing under `.pi/extensions/` reports no `trust:` field.
- [ ] The scaffolded `AGENTS.md` carries the project-trust line with `/trust`.

### §S5
- [ ] A confirmed Sandesh install's output reaches the terminal and not the stdout envelope —
      asserted on a pseudo-terminal, as CR-MDB-036's installer-output test does.
- [ ] A confirmed install exiting 0 with `sandesh` then on PATH records `installed`; exiting 0
      without it records `absent` with a warning.

### Close-out
- [ ] **Measured, not assumed:** this repository carries the rendered policy (dog-food); with the
      user having trusted this repository, a dispatched agent reads `~/.agents/skills/` and runs
      `ctx_shell` without a permission prompt — the permission log since dispatch shows no prompt,
      recorded with the transcript reference. Trusting the repository is the user's action.

### Migration
- [ ] Tests asserting `init`'s emitted file set or the contents of `.pi/extensions/`, the scaffolded
      `AGENTS.md`, the `already_installed` envelope, or the Sandesh install path — and tests
      depending on them without naming them — are migrated and listed by id in the RED report.
      Starting set: `test_scaffold`, `test_pi_hook_runtime`, `test_hooks`, `test_installer`,
      `test_installer_correctness`.

## Risk

- Two more of Pi's files are read: `trust.json` and the permission system's config. Both probes read
  only the keys named here and report `unknown` on anything unrecognised.
- The trust report is of the saved decision; Pi's full decision can also come from a command-line
  override or an extension. The warning says so rather than overclaiming.

## Non-goals

- No edits to the user's global permission config or to `trust.json`, ever.
- No gate over GitHub release notes or the Pi package README (outside this repository).
