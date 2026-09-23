# CR-MDB-036 — Harness capability contract and stack selection: the installer declares what it needs, probes only what you chose, and never installs a toolchain behind your back

**Status:** PENDING
**Type:** feature
**Priority:** P1 — **in release 1.0.0, wave 2.** On a vanilla Pi the deployed agents and skills
degrade *silently*: they are installed, they look correct, and they cannot work.
**Depends on:** CR-MDB-033 (installer correctness — this adds a pre-flight stage and an
`install.toml` section, both of which ride the paths 033 repairs) · CR-MDB-025 (defines which
capabilities the emitted agent definitions actually require)
**Labels:** installer, preflight, harness, pi, extensions, feature
**Phase:** Wave 5 (repo queue) · release 1.0.0 wave 2 (Crucible board)
**Design reference:** `modelb_axi/preflight.py` (the existing three-dependency stage and its
per-dependency policy vocabulary — FAIL / install-on-confirm / WARN) · `docs/research/DN-multi-harness-deploy-model.md`
§D13–D16 · CR-MDB-025 §S7 (the measured `tools:`/`permission:` contract) ·
`contracts/lean-ctx.md` (lean-ctx is already a declared interface, not an incidental tool)

## Context

Model B ships three asset families into a harness: skill bundles, agent definitions, and hook
wiring. **All three assume harness capabilities that a vanilla Pi does not have**, and nothing in
the installer says so. Measured 2026-09-22 on this machine, against the live fleet:

| Capability | Provided by | What breaks without it |
|---|---|---|
| Sub-agent dispatch; `tools:` frontmatter | `@gotgenes/pi-subagents` | No `subagent` tool at all. Every generated agent definition is inert — a directory of Markdown nothing reads. |
| `ctx_shell` and the `ctx_*` family | `pi-lean-ctx` | **There is no other shell.** A probe naming `bash, Bash, shell, Shell, exec, run, terminal, sh, command` resolved none of them. A dispatched agent can author files and cannot run a test. Skills that instruct `ctx_read`/`ctx_search` instruct a tool that does not exist. |
| `permission:` frontmatter | `@gotgenes/pi-permission-system` | Optional *until an agent file declares `permission:`* — then the key is silently ignored, and a VERIFY agent's `write: deny` becomes decoration. Also: with it installed, an unstated policy defaults to `ask`, which is a hard stop in a background child. |

The failure mode is what makes this worth a CR: **none of these announce themselves.** A missing
extension does not error at deploy time, because deploy only writes files. It surfaces later as an
agent that "did nothing", or a skill step that reports a tool not found — several layers away from
the cause. That is precisely what happened during CR-MDB-021: four dispatched agents could author
but not execute, and two of them spent their run diagnosing the harness instead of doing the work.

`preflight.py` already solves this shape for PATH binaries (`uv` FAILs, `sandesh` installs on
confirm, `crucible` WARNs). Extensions are not on PATH — they are declared in
`~/.pi/agent/settings.json` `packages[]` and resolved under the Pi npm root — so the probe is
different even though the policy vocabulary is the same.

## Audit 2026-09-22 — every asset we ship, and what it actually requires

Measured on this machine by sweeping `skills-src/`, `generator/agents/`, the deployed fleet,
`scripts/`, and the installed Crucible clients. **Three tiers of requirement, not one** — the
harness extensions are only the first.

### Tier 1 — harness extensions (what makes the assets executable at all)

| Capability | Provider | Policy | If absent |
|---|---|---|---|
| dispatch + `tools:` allowlist | `@gotgenes/pi-subagents` | **required** | every agent definition is inert Markdown |
| `ctx_shell` + the `ctx_*` family | `pi-lean-ctx` | **required** | no shell exists at all; agents author but cannot run a test |
| `permission:` frontmatter | `@gotgenes/pi-permission-system` | recommended | a declared `write: deny` is decoration; unstated policy = `ask` = hard stop in a background child |

### Tier 2 — OUR OWN tools (shipped or depended on by Model B)

| Requirement | Used by | Measured here | Policy |
|---|---|---|---|
| `sandesh` CLI (`uv tool install sandesh-relay`) | `bootstrap`, `shutdown` skills; orchestrator comms (17 refs) | `~/.local/bin/sandesh` ✓ | required for orchestration skills; already install-on-confirm |
| Crucible **clients** `~/.crucible/clients/<stack>-crucible.py` + `_crucible_axi.py` + `crucible-clients.json` | `crucible` skill (150 refs), every `crucible-report-*` bundle, all 24 agent definitions | arduino, bun, mvn, python, rust ✓ — **no vscode** | required per stack the project uses |
| Crucible **server** `127.0.0.1:3849` | ingest verbs (`test`, `regression`, `plan-file`, cycle verbs) | pre-release, often absent | recommended — tests still run; ingest does not |
| Bundled tool scripts → `~/.agents/scripts/` | `worktree-flow.py` (11 refs), `rust-code-health.py` (3), `skill-release-gate.py`, `rust-crate-map.py`, `rust-dead-scan.py`, `schedule_db.py`, `toon.py`, `gate-lock.sh` | deployed by the installer | required — `python3` for the `.py`, **`bash` for `gate-lock.sh`** |
| `uv` | bootstrap of the above | ✓ | already FAIL-on-absent |
| `gh`, `jq` | `git-workflow`, release gates (7 + 4 refs) | ✓ | recommended |

### Tier 3 — per-stack toolchains (the agents cannot test without them)

| Stack | Requires | Measured |
|---|---|---|
| python | `python3`, **`xmlrunner`**, `coverage` — NOT stdlib, and nothing declares them today | both importable ✓ |
| rust | `cargo`, `cargo-nextest`, `llvm-cov` | `cargo` ✓ |
| quarkus | `mvn`, JaCoCo | ✓ |
| bun | `bun`, `node` | ✓ |
| arduino | `arduino-cli`, host `g++` | ✓ |
| vscode | `vitest`, `mocha`, `node` | — |

### Three contradictions the audit exposed (findings, not gaps)

1. **`preflight.py` probes a `crucible` BINARY that does not exist.** `shutil.which("crucible")`
   returns `None` here and the stage WARNs — but the real artefacts are the clients under
   `~/.crucible/clients/` and the server on `127.0.0.1:3849`. The probe can report
   `crucible=absent` on a perfectly working install, and `detected` on one with no clients at
   all. It measures the wrong thing. (Adjacent to CR-MDB-020, which anchors the client paths.)
2. **We ship `skills-src/crucible-report-vscode/` for a client that was never shipped.** There is
   no `vscode-crucible.py` (Crucible mail #1369 confirmed it did not ship), and the deployed
   `vscode-*-agent` definitions cite no client at all — they name `vitest` only. A bundle that
   instructs ingest through a nonexistent client is a broken instruction.
3. **The deployed fleet is wider than the generator.** `generator/agents/` owns 16 definitions
   (arduino, bun, python, quarkus); the deployed fleet carries **24**, adding `rust-*` and
   `vscode-*`. `generator/stacks/` has no `rust.toml` (CR-MDB-024's job) and no vscode stack at
   all. Eight deployed agents are regenerated by nobody — and a `build.py --check` reporting
   "clean" says nothing about them.

## Scope

### §S1 — Declare the requirement, in one place
A single declarative table in `modelb_axi/` naming each required capability across **all three
tiers** of the audit above: harness extensions, Model B's own tools (Sandesh CLI, the Crucible
clients + manifest + server, the eight bundled tool scripts), and the per-stack toolchains. Each
row carries the capability, its provider, the policy (`required` / `recommended`), the asset
family or stack that depends on it, and the user-facing remediation. Data, not branching code —
the pre-flight, the docs and the scaffold all read it, so a fourth requirement is one row rather
than three edits.

**Requirements are SCOPED, not global.** A python-only project must not be blocked because
`cargo` is missing. A stack's toolchain is required only when that stack is selected (installer
`--stacks`, or the scaffolded project's declared stacks); everything in Tier 1 and the
Model-B-own tools in Tier 2 apply always.

### §S2 — Probe capability, not package presence
A package present in `node_modules` is not the same as a capability the harness will honour: it
must also be listed in `settings.json` `packages[]` to load. The probe reads the resolved
harness configuration and reports per capability, never inferring one from the other. Where a
runtime probe is cheap and unambiguous it is preferred over a static one — **what matters is
whether a dispatched agent can call `ctx_shell`, not whether a directory exists.** (Evidence that
static presence lies: `~/.pi/agent/npm/node_modules/@pi-archimedes/` exists as an EMPTY directory
while providing nothing, and is absent from `packages[]`.)

### §S3 — Policy per capability, honest exit codes
- **Dispatch (`pi-subagents`) and lean-ctx: `required`.** Absent ⇒ the installer reports which
  asset families will be inert and exits non-zero unless explicitly overridden. Deploying agent
  definitions into a harness that cannot dispatch them is writing files nobody will read.
- **Permission system: `recommended`.** Absent ⇒ WARN naming the consequence (`permission:` keys
  ignored; read-only VERIFY unenforced by policy, though still enforced by tool omission).
- Model B **never installs a third-party extension on the user's behalf** without confirmation,
  and never edits `settings.json` silently — same boundary already honoured for Crucible, whose
  own installer owns its assets.

### §S4 — Record the verdicts
The per-capability verdicts persist into `install.toml` beside the existing `[deps]`, so a later
run, a support question, or a `doctor` command can answer "what did the harness look like when
this was installed?" without re-probing a machine that has since changed.

### §S5 — The assets stop assuming silently
Skill bundles and agent definitions that require a capability say so where a reader will meet it:
the agent-definition emitter (CR-MDB-025 §S7) already names `ctx_shell` in `tools:`, and the
skills that instruct `ctx_*` usage gain a one-line prerequisite note. A skill that tells an agent
to run `ctx_search` on a harness without lean-ctx is a broken instruction, not a preference.

### §S6 — Scaffolded projects inherit the contract
`modelb-axi init` emits the same requirement into the new project's `AGENTS.md`, so a project
scaffolded on one machine and cloned onto a vanilla Pi fails loudly at pre-flight rather than
mysteriously at first dispatch.

### §S7 — A stack selector on the INSTALLER, not just on `init`

Measured 2026-09-22: `modelb-axi init` accepts `--stacks`, but the installer path does not — it
carries `--harnesses` only, and `deploy.py` is **stack-blind**, shipping all 13 bundles to
everyone. A python-only user receives the arduino, quarkus and bun `crucible-report-*` bundles,
and then — under §S1's scoping — would be told about toolchains for stacks they never asked for.
(Agent definitions are not the installer's: they are rendered per project by `init` for the
project's own stacks — DN §D17 — so this selector does not scope them.)

- The installer gains **`--stacks CSV`**, mirroring `init`'s flag and vocabulary, defaulting to
  all supported stacks so existing behaviour is unchanged when the flag is omitted.
- Interactively (no `--yes`), the user is offered the stack list and selects; `--yes` takes the
  default. Selection is a *choice*, never inferred by sniffing the machine — a developer who has
  `cargo` installed has not thereby asked for the rust stack.
- **Selection scopes what is deployed**: the stack's `crucible-report-*` bundle. Stack-neutral
  assets (`model-b`, `crucible`, `cr-authoring`, `git-workflow`, `bootstrap`, `shutdown`, the hook
  scripts, the tool scripts) always deploy.
- The selection persists in `install.toml`, so a re-run, an upgrade, or a `doctor` knows which
  stacks this installation is for without asking again — and adding a stack later is a re-run
  with a wider `--stacks`, not a reinstall.

### §S8 — Probing SDKs cheaply, and never installing them behind the user's back

Tier-3 toolchains are the expensive part of the contract, in two senses: probing them badly is
slow, and installing them is a large, opinionated act on someone's machine.

- **Only SELECTED stacks are probed.** This is the main saving §S7 buys: an unselected stack costs
  zero probes, zero warnings, and zero mention in the report.
- **Probe by resolution, not by execution.** Measured on this machine: `command -v` across five
  toolchains costs ~1 ms, while a single `mvn -version` costs ~227 ms because it spawns a JVM.
  The pre-flight resolves the binary and stops there. A version *check* runs only where a minimum
  version is genuinely required, only for a selected stack, and its cost is acknowledged in the
  report rather than hidden.
- **Model B never installs a language toolchain.** For an absent SDK the installer names the
  provider's own installer (`rustup`, `sdkman`/the distro JDK, `bun`'s installer, `arduino-cli`'s
  installer) and offers to run **that**, on explicit confirmation, exactly as it already does for
  Sandesh via `uv tool install`. Declining is a first-class outcome: the stack's assets still
  deploy, the verdict is recorded `absent`, and the user is told which agents will not be able to
  run tests until it is present.
- **An absent SDK for a selected stack is a WARN, not a FAIL.** A user may legitimately install
  the assets on a machine that is not the build machine. The Tier-1 `required` gate stands
  (without dispatch or a shell nothing works anywhere); a missing `cargo` only makes the rust
  agents inert, which the report says plainly.
- Python's `xmlrunner` and `coverage` are the exception worth naming: they are **pip
  dependencies of the Crucible client we ship instructions for**, not a developer's own toolchain,
  so their absence is reported against the python stack with the exact `uv`/`pip` command, not
  left to be discovered when a RED run fails to produce JUnit XML.

### §S9 — One install guide, authored once, reused by every publishing surface

The feature's purpose is to stop silent failure. It fails that purpose if its own diagnostics need
the spec to interpret — so the user-facing guide is a deliverable of this CR, not a follow-up.

**`docs/install-guide.md` is the single source.** It covers: prerequisites in dependency order
(what must exist before `modelb-axi` is even useful), the stack selector and what choosing a
stack does and does not install, how to read every pre-flight verdict line, what each WARN means
in consequences rather than in jargon ("the rust agents will deploy but cannot run tests until
`cargo` is present"), and how to widen the selection later without reinstalling.

**Every other surface DERIVES from it; none restates it.** The same content is wanted in at least
four places, and four hand-maintained copies is four drifts waiting:

| Surface | Owner | How it gets the content |
|---|---|---|
| `docs/install-guide.md` | this CR | **the source** |
| GitHub release notes | the release ritual (`skills-src/git-workflow/SKILL.md` §Releases) | extracted at release time, never retyped |
| The Pi package's README | CR-MDB-029 §S1 | extracted at publish time |
| Repo `README.md` install section | this CR | extracted, or a pointer — never a paraphrase |

Extraction is mechanical: the guide carries explicitly marked regions, and the publishing steps
copy a named region verbatim. A gate compares each derived copy against its source region and
fails on divergence — the same discipline the board-vs-repo title-parity rule exists for, applied
to the one document a user actually reads. A paraphrase in a release note is how a user ends up
following instructions that stopped being true two releases ago.

**The REVIEW of the documentation happens at the release, not here** (user ruling 2026-09-22).
This CR's job is to make the guide exist, make it correct at the time of writing, and make every
other surface derive from it mechanically. Judging whether the whole doc set still tells the
truth is a release-boundary activity — consistent with a release being a boundary event whose
ritual lives in `skills-src/git-workflow/SKILL.md` §Releases rather than in any queue row. The
extraction gate is what makes that review cheap: a reviewer reads one source instead of
diffing four copies.

**§S9 acceptance criteria**

- [ ] `docs/install-guide.md` exists and covers, at minimum: prerequisites in dependency order;
      what the stack selector installs and skips; every pre-flight verdict line and its meaning;
      the consequence of each WARN stated in terms of what will not work; and how to add a stack
      later.
- [ ] Its regions are explicitly marked for extraction, and the marker convention is documented
      in the file itself.
- [ ] The repo `README.md` install section is extracted from it or points at it — it contains no
      independently-worded copy.
- [ ] A gate fails when a derived copy diverges from its source region, with a fixture proving the
      gate bites on an edited copy.
- [ ] `skills-src/git-workflow/SKILL.md` §Releases names TWO release steps: extracting the guide's
      marked regions into the release notes, and a **documentation review** over the doc set
      (user ruling 2026-09-22 — the review is a release-boundary activity, not a CR gate).
      CR-MDB-029 §S1 is annotated to take the Pi package README from the same source.
- [ ] The guide is written for someone on a fresh machine who has never read a CR — no §S
      references, no CR ids, no internal vocabulary in the instructions themselves.

### §S11 — The permission policy the workflow needs is shipped and checked

Measured 2026-09-23 on this machine. With `@gotgenes/pi-permission-system` installed and no
config, background children's `ask` prompts were forwarded to the user for every access outside
the working directory and every skill read. A first config without a universal fallback made it
worse: the package documents that omitting `"*"` means `"ask"`, so every tool without its own rule
prompted (11 `ctx_shell` prompts in an hour). A `"*": "allow"` fallback stopped the prompts but
the package warns against it. The policy that works names what the workflow uses:

- `"*": "ask"` as the explicit fallback;
- `allow` by exact tool name for the lean-ctx family (every `ctx_*` tool and `lean_ctx` — tool
  keys take no wildcard, so each is listed), the built-in file tools, the sub-agent tools
  (`subagent`, `get_subagent_result`, `steer_subagent`, and the child-side `notify_parent` and
  `ask_parent`), `todo` and `ask_user_question`;
- `skill: allow`; `external_directory_read` allowing `~/.agents/*`, `~/.crucible/*`,
  `~/.pi/agent/*`, the installed harness's own code (`~/.bun/install/*` for the bun-installed Pi,
  added 2026-09-23 after CR-MDB-030's RED stalled 35 minutes on unanswered prompts reading Pi's
  loader) and `/tmp/*`; `external_directory_write` allowing `/tmp/*`; both else `ask`.

An extension tool's access direction is unproven to the permission system, so it is checked against
both the read and the write policy; reads outside the project are therefore made with the built-in
tools, which the policy proves read-only (the agent-side rule is CR-MDB-025 §S7). No write
allowance outside `/tmp` is added to silence those prompts.

The installer ships that policy as a template and, when the permission system is present, reports
whether the global config carries it: absent, missing the `"*"` fallback, or missing a
workflow tool is a WARN naming the consequence. It never overwrites a user's existing config.

### §S10 — Deployed assets report when they are stale

Measured 2026-09-23: all six orchestrator skills deployed on this machine (`model-b`, `bootstrap`,
`shutdown`, `crucible`, `git-workflow`, `cr-authoring`) differ from their repo source — the
deployed copies are older, still teaching a retired `--phase` flag — and nothing said so. A
deployed asset has three possible states against the manifest and the package it came from, and
the installation must be able to tell them apart:

- **current** — deployed hash = manifest hash = packaged source hash;
- **stale** — deployed = manifest, but the packaged source has changed since (an upgrade that was
  not redeployed); the remedy is a re-run;
- **hand-modified** — deployed ≠ manifest; the remedy is the user's call (`--force-managed`).

Running bare `modelb-axi` on an installed machine (the `already_installed` outcome, CR-MDB-033
§S6) reports `stale` and `hand_modified` as lists of relative paths in its envelope. No new verb.

## Acceptance criteria

- [ ] A single declarative structure in `modelb_axi/` lists every required capability with its
      provider package, policy, dependent asset family, and remediation string. Adding a
      requirement touches exactly that structure and its test.
- [ ] The pre-flight reports one line per capability in the existing machine-greppable style
      (`harness: dispatch=detected lean-ctx=detected permissions=absent`), emitted **before** any
      remediation, mirroring `deps:`' truthful-detection-first rule.
- [ ] A capability present in `node_modules` but absent from `settings.json` `packages[]` is
      reported **absent**, with a test fixture proving that exact case (the empty-directory
      `@pi-archimedes` case is the real-world instance).
- [ ] A missing `required` capability exits non-zero and names the asset families that would be
      inert; a missing `recommended` capability WARNs and continues.
- [ ] Zero third-party extensions are installed and zero `settings.json` edits are made without
      explicit confirmation; asserted by a test that runs the installer non-interactively against
      a sandbox and diffs the harness config.
- [ ] `install.toml` carries the per-capability verdicts; a round-trip test reads them back.
- [ ] Every skill bundle instructing a `ctx_*` tool carries a prerequisite line naming lean-ctx.
- [ ] `modelb-axi init` emits the capability contract into the scaffolded `AGENTS.md`.
- [ ] **Measured, not assumed:** the pre-flight's verdict for each capability is corroborated
      against a real dispatch on this machine (an agent that can/cannot call `ctx_shell`), and the
      transcript reference is recorded in the CR's close-out.

### §S11 — permission policy

- [ ] The shipped policy template has an explicit `"*": "ask"`, allows every workflow tool named
      in §S11 by exact name, and allows no tool by a `"*": "allow"` fallback.
- [ ] With the permission system installed, the installer's result reports the global config as
      `absent`, `no-fallback`, `missing-tools` (naming them) or `ok`, and never writes that file.

### §S10 — asset freshness

- [ ] With a deployed skill left as installed and its packaged source changed, the
      `already_installed` envelope lists it under `stale`, not under `hand_modified`.
- [ ] With a deployed skill edited by hand, the envelope lists it under `hand_modified`, not under
      `stale`.
- [ ] With nothing changed, both lists are empty.

### §S7 — stack selection

- [ ] The installer accepts `--stacks CSV` with the same vocabulary as `init`; omitting it
      selects all supported stacks, so current behaviour is unchanged.
- [ ] An unsupported name is rejected with a message listing the supported stacks (the same
      rejection CR-MDB-024 §S4 requires for `vscode`).
- [ ] With `--stacks python`, a sandbox install deploys `crucible-report-python` and **no**
      arduino/bun/quarkus/rust report bundles; the stack-neutral bundles and both script classes
      still deploy; and the installer writes no agent definitions for any stack (DN §D17).
- [ ] Interactive selection is offered when neither `--stacks` nor `--yes` is given; `--yes`
      takes the default without reading stdin.
- [ ] The selection round-trips through `install.toml`, and a re-run with a wider `--stacks` adds
      the newly selected stack's assets without disturbing the rest of the manifest.

### §S8 — SDK probing

- [ ] Unselected stacks are not probed at all — asserted by a test that counts probe invocations
      for a single-stack selection.
- [ ] Toolchain probes resolve binaries rather than executing them; no probe spawns a runtime
      merely to learn that it exists.
- [ ] An absent SDK for a selected stack WARNs, records `absent`, names the provider's own
      installer, and does not fail the install.
- [ ] No language toolchain is installed without explicit confirmation; declining is recorded and
      the install continues.
- [ ] The python stack reports `xmlrunner`/`coverage` absence with the exact install command,
      distinguishing them from a developer's own toolchain.

## Estimated size

One declarative table, one new pre-flight stage reading it, an `install.toml` section, a
prerequisite line in the affected skills, and a scaffold template change. No change to the deploy
engine's file-writing path.

## Risk

- **Probing another tool's configuration is a coupling.** `settings.json`'s shape is Pi's, not
  ours, and it can change. Keep the probe narrow (does this package load?), fail *open* on a
  shape we do not recognise with a clear "could not determine" verdict, and never parse more than
  the one key needed. A pre-flight that crashes on an unfamiliar config is worse than one that
  admits ignorance.
- **`required` is a real gate and will block someone.** That is the intent — but the override must
  exist, be documented, and be recorded in `install.toml`, so an operator who knows better is not
  forced to hand-edit anything.

## Non-goals

- No vendoring of third-party extensions, and no bundling them into the Model B Pi package
  (CR-MDB-029 ships *our* package; this CR only declares what must already be present).
- No support for harnesses other than Pi — the roster is Pi-only per DN §D14.
- No auto-repair of a harness config. Detect, report, remediate on confirm; never silently.
