# CR-MDB-098 — SoL-Pi is set up for every project Model B renders into

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-11-04 by the user's rulings, DN §D28). Gap
analysis, the spec and its pre-review happen in order when this CR starts. Crucible #1536 (the combined
lean-ctx and SoL-Pi practice, DN §D30) folded in as item 8 by the user's ruling, 2026-11-08, with
Crucible #1540 (its AGENTS.md side) under the same ruling.
**Type:** feature (installer requirement row, `init`, `agents`)
**Priority:** P2 — release 1.1.0, wave 3 (user 2026-11-04; board-authoritative: read `queue`).
**Depends on:** CR-MDB-095 (the trust write, without which Pi ignores a project's `.pi/sol-pi.json`) and
SoL-Pi's installed entry point with its per-project mode (DN §D28) — SoL-Pi's work, not on Model B's board.
**Labels:** installer, scaffold, pi, sol-pi, lean-ctx, skills
**Design reference:** DN-multi-harness-deploy-model §D28 and §D30 (this CR's rulings), §D27 (trust, requirement
rows), §D24 (tools from requirement rows); CR-MDB-095; CR-MDB-094 (generated files and the dogfooding
exception).

## Context

SoL-Pi manages a project's local configuration, `<project>/.pi/sol-pi.json`, through its setup script. Pi
reads that file only when the project is trusted (`ctx.isProjectTrusted()`); otherwise SoL-Pi falls back to
the user-wide `<agent-dir>/sol-pi.json`. The user ruled (2026-11-04) that SoL-Pi is a prerequisite of every
Model B project on Pi, reached the way Model B reaches Crucible: through an installed entry point, never a
checkout.

Measured 2026-11-04 against the fork's checkout (anthill-tec/SoL-Pi `fc1cd09`, package `sol-pi` 0.1.1):

- `setup-sol-pi.fish --install <dir>` installs for a project, but runs from the checkout (`$(pwd)`); each
  run does `npm ci`, the typecheck and test suite, an end-to-end test and `npm audit`, and a user-wide
  `pi install` when SoL-Pi is not registered;
- its strict compatibility check accepts Pi 0.84.2, 1.0.4 and 1.3.0, so it stops on the installed Pi 1.5.0;
- a re-run leaves `<dir>/.pi/sol-pi.json.bak`;
- a cancelled prompt exits 0, as a success does;
- with `PI_NONINTERACTIVE` or no terminal it takes its defaults (all four mechanisms on; the first provider
  and model Pi reports), and exits 1 when Pi has none;
- SoL-Pi registers `edit` and `write` (Pi's own, with a `then_run` shell command), `obs_recall` and
  `update_plan`.

## SoL-Pi's contract (SoL-Pi #1534, 2026-11-04, corrected by #1554, 2026-11-08; CR-SLP-002 to 006, SoL-Pi 0.1.0, target 2026-11-09)

SoL-Pi's answer to Model B's request (#1516); the gap analysis checks the released 0.1.0 against it. #1554
(the user's redesign of SoL-Pi's distribution, on Crucible's and Sandesh's pattern) replaced the install,
the probe and the command names; the flags, envelope, exit codes and opt-in prompts are unchanged.

- **Install (the user, once):** `uv tool install sol-pi-axi==<version>`, then `sol-pi-axi install`, which
  registers the Pi extension user-wide as `npm:@anthill-tec/sol-pi@<same version>` (through `pi install`)
  and writes the user-wide `sol-pi.json` (under `$PI_CODING_AGENT_DIR`, else `~/.pi/agent`) only when none
  exists. The extension alone: `pi install npm:@anthill-tec/sol-pi@<version>`. The tool needs Python 3.14+
  (uv fetches it), not Bun. `sol-pi-axi uninstall` removes the registration; `setup-sol-pi.fish` is retired.
- **Probe:** `sol-pi-axi` on `PATH` (uv's tool bin directory); `sol-pi-axi --version` (`-v`, `-V`) prints the
  bare version and exits 0. `sol-pi-axi` with no arguments prints its home view, whose `extension.state` is
  `absent` or `registered` (with its `source`), warning when the registered version differs from the
  tool's: Model B reads that, never Pi's settings.
- **`sol-pi-axi setup <project dir>`** writes at most `<dir>/.pi/sol-pi.json`, leaves no `.bak`, runs
  no dependency install, tests, audit or `pi install`. An existing valid project file stays `unchanged`
  unless value flags change it; with none, values come from the user-wide `sol-pi.json`, else its defaults
  (all four features on; the reducer on Pi's default provider and model). Value flags: `--features
  all|none|<list>`, `--reducer <provider>/<model>`, `--cache-ratio <n>`.
- **Prompts are opt-in:** never by default (`--non-interactive` accepted, a no-op); `--interactive` prompts
  only when stdin and stderr are terminals and `PI_NONINTERACTIVE` is unset or empty, else warns and runs
  non-interactively. Model B passes `--interactive` on an interactive run (terminal passed through) and
  `--non-interactive` under `--yes`.
- **Exit codes:** 0 written or unchanged; 1 failed (invalid configuration, no provider or model, bad
  directory, write error); 2 usage; 130 / 143 / 129 cancelled.
- **Stdout:** one TOON document, root `axi` — verb (`setup`), ok, `outcome` (written, unchanged, failed, usage,
  cancelled), path, version, config, context, warnings, help, error; `--format json` prints the same object
  as one JSON line.
- **Pi 1.5.0** is in its tested set (CR-SLP-002); `edit` and `write` carry `then_run` guidance
  (CR-SLP-003).

## Scope (seed)

1. **A `sol-pi` requirement row:** the probe of `sol-pi-axi` and, from its home view, whether the Pi
   extension is registered; its remediation (`uv tool install sol-pi-axi==<version>`, then `sol-pi-axi
   install`); the installer never installs either.
2. **`init` and `agents` call SoL-Pi's per-project setup** for the target, after the trust step: the
   terminal passed through on an interactive run, non-interactive under `--yes`. The outcome is reported in
   the envelope (`sol_pi`); a failure or an absent entry point warns and keeps `ok` and the exit code.
3. **The permission policy:** `obs_recall` and `update_plan` from the row; `edit` and `write` keep their
   entries, with what `then_run` adds stated.
4. **Model B's own repository** keeps committing its `.pi/sol-pi.json`.
5. **Texts:** the install guide and its README mirror, the scaffolded capability contract.
6. **What the project's agents are told about SoL-Pi (user 2026-11-04).** Two layers, each with one owner:
   - **How to use each tool** stays in SoL-Pi's own tool registrations (`promptSnippet`,
     `promptGuidelines`), which Pi puts into the system prompt of every session that has the tool; Model B
     never copies it. (`obs_recall` and `update_plan` carry it today; `edit` and `write`'s `then_run` is in
     the request to SoL-Pi.)
   - **What SoL-Pi is and why it is in the project** — one short paragraph: what it does, that it is a
     prerequisite, `.pi/sol-pi.json` read only in a trusted project, `edit` and `write` being SoL-Pi's with
     `then_run`, and how to change its settings — comes from the `sol-pi` requirement row (a new `about`
     field), rendered by `init` into a short "Workflow tools" section of the scaffolded `AGENTS.md`, never
     into the capability contract's state lines. Model B's own `AGENTS.md` gets it by hand in this CR;
     existing projects get it through the migration verbs (CR-MDB-055). The expected text is dogfooded in
     Model B's own `AGENTS.md` § Workflow tools (2026-11-04).

7. **The hooks see a `then_run` command (user 2026-11-04).** SoL-Pi's Action Fusion runs an `edit` or
   `write`'s `then_run.command` by calling Pi's built-in `bash` tool from inside the tool, so no `bash` tool
   call reaches the hooks. Model B's Pi hook shim maps `edit` and `write` to their file class, path only,
   so the runner block never sees the command: `then_run` can run a test runner directly, past the
   "tests only through the Crucible client" rule. The shim (`modelb_axi/hooks.py`'s Pi compilation) also
   evaluates an `edit` or `write` call's `then_run.command` as a shell-class (`bash`) payload, so every
   shell-class hook applies to it as to `ctx_shell`; a block blocks the whole call.

8. **The combined context-optimisation practice (Crucible #1536; user 2026-11-08, DN §D30).** Every rule
   set Model B ships states how lean-ctx and SoL-Pi are used together, for a project whose harness loads
   both: the orchestration references (common, Mainline, Track), the sub-agent brief template
   (`sub-agent-procedure.md`), the bootstrap skill, the generated agent definitions (which carry the
   lean-ctx read rules today and gain SoL-Pi's half) and the scaffolded `AGENTS.md`'s "Workflow tools"
   section. Within §D30's bounds:
   - the practice, never the usage (item 6 stands: no tool's modes or parameters are copied);
   - the rules live in the skills, loaded at bootstrap Step 0.5; no rule fact in the knowledge store;
   - an envelope may be narrowed with `--fields` and is still read whole (CR-MDB-072);
   - every brief says the agent runs only the tests it touches (§D26);
   - the separate-turns rule for `update_plan` and a background dispatch holds only until SoL-Pi
     CR-SLP-006 is released;
   - **the scaffolded `AGENTS.md` states it** (Crucible #1540): `update_plan` is mandatory, kept current at
     every milestone (dispatch, agent report, user ruling, commit); and, while SoL-Pi is older than the
     release carrying CR-SLP-006, no step is completed while a background sub-agent runs or is queued.
     How `update_plan` is called (the whole plan each time, step ids kept, one step in progress) stays
     in SoL-Pi's registration.

## To measure at gap analysis

- SoL-Pi 0.1.0 as released against § SoL-Pi's contract.
- Pi's version then, and SoL-Pi's tested list.
- How the call is tested hermetically (the entry point absent on the clean runner: a skip naming it, or a
  stub).
- CR-MDB-055 and CR-MDB-082 (migration verbs) and CR-MDB-094 (gitignore): what each inherits.
- The cases the `then_run` check (§7) must cover: the `edit` and `write` inputs as SoL-Pi's shipped version
  shapes them, a call with no `then_run`, and the worktree write boundary (a shell command is not
  path-checked; state what that leaves).
- Whether pi-subagents' child sessions load the project's `AGENTS.md` (if not, the tool guidelines are what
  reaches them), and whether other rows (pi-lens, lean-ctx, Sandesh) take an `about` paragraph too.
- For item 8: every surface that already states a lean-ctx rule (the generated agent definitions, the
  orchestration references, the scaffolded `AGENTS.md`, Model B's own `AGENTS.md` § Runtime/Tooling
  Preferences) and every guard test that pins its wording; whether SoL-Pi 0.1.0 carries CR-SLP-006 (if
  it does, and the row's probe requires 0.1.0, #1540's rule 2 never ships and only rule 1 is rendered); how a
  project whose harness loads only one of the two extensions is told (the rule set is conditional on
  both).
- The re-score (8 points before item 8; 13 after the fold, user 2026-11-08).
