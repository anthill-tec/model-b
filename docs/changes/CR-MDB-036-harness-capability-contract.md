# CR-MDB-036 — Harness capability contract: the installer declares, probes and verifies the Pi extensions Model B's assets depend on

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
