# CR-MDB-037 — Install guide, deployed-asset freshness, and the shipped permission policy

**Status:** PENDING (split from CR-MDB-036 at its gap-analysis, 2026-09-24, user ruling)
**Type:** feature
**Priority:** P1 — in release 1.0.0, wave 2
**Depends on:** CR-MDB-036 (the guide documents its pre-flight verdicts and stack selector; §S3's
check reads the capability verdicts it records)
**Labels:** installer, docs, pi, permissions, feature
**Phase:** Wave 5 (repo queue) · release 1.0.0 wave 2 (Crucible board)
**Design reference:** PRD D11 · CR-MDB-036 (capability contract, stack selector) · CR-MDB-033 §S6
(the install envelope and its outcomes) · DN-multi-harness-deploy-model §D17 (per-project
rendering, the pattern §S3 prefers) · `@gotgenes/pi-permission-system` `docs/configuration.md`
· `skills-src/git-workflow/SKILL.md` §Releases

**Target set:** Pi only (DN §D13/§D14).

## Context

CR-MDB-036 makes the installer declare and probe what the harness must have. Three things it leaves
open are what a user meets next: instructions that explain its verdicts, a way to tell that
deployed assets have fallen behind the package, and a permission policy under which the workflow's
background agents can run without stopping on prompts.

Measured on this machine, 2026-09-23:

- `model-b` has no `README.md`, and no document explains an install to someone who has never read
  a CR.
- All six orchestrator skills deployed here (`model-b`, `bootstrap`, `shutdown`, `crucible`,
  `git-workflow`, `cr-authoring`) differ from their repo source; the deployed copies are older and
  still teach a retired `--phase` flag. Nothing reported it.
- With `@gotgenes/pi-permission-system` installed and no config, background children's `ask`
  prompts reached the user for every access outside the working directory and every skill read. A
  config without a universal fallback made it worse, since the package treats an omitted `"*"` as
  `"ask"` (11 `ctx_shell` prompts in an hour). A `"*": "allow"` fallback stopped the prompts but
  the package warns against it.

## Scope

### §S1 — One install guide, the single source

`docs/install-guide.md` covers, for someone on a fresh machine: prerequisites in dependency order;
what the stack selector installs and skips; every pre-flight verdict line and what it means; the
consequence of each WARN stated as what will not work ("the rust report bundle deploys, but rust
agents cannot run tests until `cargo` is present"); how to widen the stack selection later without
reinstalling; and that deploying into the real home directory takes an explicit
`--target-root ~`.

Other surfaces take their install text from it, never a paraphrase:

| Surface | How it gets the content |
|---|---|
| Repo `README.md` | a short project description and a pointer to the guide; no install instructions of its own |
| GitHub release notes | the guide's marked regions, copied verbatim at release time |
| The Pi package README | the same marked regions, copied at publish time (CR-MDB-029 §S1) |

The guide carries explicitly marked regions, with the marker convention documented in the file.

**The review of the documentation happens at the release, not in this CR** (user ruling
2026-09-22): a release is a boundary event whose ritual lives in `skills-src/git-workflow/SKILL.md`
§Releases.

### §S2 — Deployed assets report when they are stale

A deployed asset is in one of three states against the manifest and the package it came from:

- **current** — deployed hash = manifest hash = packaged source hash;
- **stale** — deployed = manifest, but the packaged source has changed since; the remedy is a
  re-run;
- **hand-modified** — deployed ≠ manifest; the remedy is the user's (`--force-managed`).

Running bare `modelb-axi` on an installed machine (the `already_installed` outcome, CR-MDB-033 §S6)
reports `stale` and `hand_modified` as lists of target-root-relative paths in its envelope. No new
verb.

### §S3 — The permission policy the workflow needs

The policy that works names what the workflow uses:

- `"*": "ask"` as the explicit fallback;
- `allow` by exact tool name for the lean-ctx family (every `ctx_*` tool and `lean_ctx` — tool
  keys take no wildcard), the built-in file tools, the sub-agent tools (`subagent`,
  `get_subagent_result`, `steer_subagent`, and the child-side `notify_parent`, `ask_parent`),
  `todo` and `ask_user_question`;
- `skill: allow`; `external_directory_read` allowing `~/.agents/*`, `~/.crucible/*`,
  `~/.pi/agent/*`, the installed harness's own code (`~/.bun/install/*` for a bun-installed Pi) and
  `/tmp/*`; `external_directory_write` allowing `/tmp/*`; both else `ask`.

An extension tool's access direction is unproven to the permission system, so it is checked
against both the read and the write policy; reads outside the project are made with the built-in
tools (the agent-side rule is CR-MDB-025 §S5). No write allowance outside `/tmp` is added to
silence those prompts.

**Where it lives is decided by measurement, preferring per project** (user ruling 2026-09-24). The
first cycle measures whether the permission system merges a project
`.pi/extensions/pi-permission-system/config.json` with the global one:

- **If it merges**, `init` renders the workflow policy into the project, exactly as it renders
  agents and hooks (DN §D17), under the same ownership rules as CR-MDB-025 §S6; the installer only
  checks the global config.
- **If it does not**, the installer ships the policy as a template and checks the global config.

Either way the installer reports whether the global config is `absent`, lacks the `"*"` fallback
(`no-fallback`), lacks workflow tools (`missing-tools`, naming them), or is `ok` — and never writes
the user's global config.

## Acceptance criteria

### §S1
- [ ] `docs/install-guide.md` covers every item §S1 lists, including the explicit
      `--target-root ~` for a real-home deploy.
- [ ] Its regions are marked for extraction, and the marker convention is documented in the file.
- [ ] `README.md` exists, describes the project in a few lines and points at the guide; it carries
      no install instructions of its own — a gate asserts the pointer and the absence of
      installer commands.
- [ ] `skills-src/git-workflow/SKILL.md` §Releases names two release steps: copying the guide's
      marked regions verbatim into the release notes, and a documentation review over the doc set.
- [ ] CR-MDB-029 §S1 names the guide's marked regions as the source of the Pi package README.
- [ ] The guide's instructions carry no §S references, CR ids or internal vocabulary.

### §S2
- [ ] With a deployed skill left as installed and its packaged source changed, the
      `already_installed` envelope lists it under `stale`, not `hand_modified`.
- [ ] With a deployed skill edited by hand, the envelope lists it under `hand_modified`, not
      `stale`.
- [ ] With nothing changed, both lists are empty.

### §S3
- [ ] **Measured, not assumed:** whether a project policy file merges with the global one is
      recorded, with the evidence, before any policy code is written; the placement follows it.
- [ ] The policy (template or rendered file) has an explicit `"*": "ask"`, allows every workflow
      tool §S3 names by exact name, and has no `"*": "allow"`.
- [ ] With the permission system installed, the installer's envelope reports the global config as
      `absent`, `no-fallback`, `missing-tools` (naming them) or `ok`, and the installer never writes
      that file — asserted against a sandboxed `PI_CODING_AGENT_DIR`.
- [ ] If the policy is rendered per project: `init` writes it, `modelb-axi agents`-style ownership
      applies (an unmarked or hand-edited file is never overwritten), and a dispatched agent from a
      scaffolded project runs `ctx_shell` and reads `~/.agents/skills/` without a prompt.

## Risk

- The permission system's config schema is the package's, not ours. The check reads only the keys
  §S3 names and reports a config it cannot parse as `unknown`, never crashing.

## Non-goals

- No edits to a user's global permission config, ever.
- No gate over GitHub release notes or the Pi package README (they are outside this repository);
  their faithfulness is the release ritual's job.
