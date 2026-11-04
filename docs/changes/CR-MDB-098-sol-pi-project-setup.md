# CR-MDB-098 — SoL-Pi is set up for every project Model B renders into

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-11-04 by the user's rulings, DN §D28). Gap
analysis, the spec and its pre-review happen in order when this CR starts.
**Type:** feature (installer requirement row, `init`, `agents`)
**Priority:** P2 — release 1.1.0, wave 3 (user 2026-11-04; board-authoritative: read `queue`).
**Depends on:** CR-MDB-095 (the trust write, without which Pi ignores a project's `.pi/sol-pi.json`) and
SoL-Pi's installed entry point with its per-project mode (DN §D28) — SoL-Pi's work, not on Model B's board.
**Labels:** installer, scaffold, pi, sol-pi
**Design reference:** DN-multi-harness-deploy-model §D28 (this CR's rulings), §D27 (trust, requirement
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

## Scope (seed)

1. **A `sol-pi` requirement row:** the probe of SoL-Pi's installed entry point, its remediation (SoL-Pi's
   install command); the installer never installs it.
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
     existing projects get it through the migration verbs (CR-MDB-055).

## To measure at gap analysis

- SoL-Pi's shipped entry point: its install command and location, its version, the project mode's flags,
  exit codes and output; whether it still writes a backup file or touches anything user-wide.
- Pi's version then, and SoL-Pi's tested list.
- How the call is tested hermetically (the entry point absent on the clean runner: a skip naming it, or a
  stub).
- CR-MDB-055 and CR-MDB-082 (migration verbs) and CR-MDB-094 (gitignore): what each inherits.
- Whether pi-subagents' child sessions load the project's `AGENTS.md` (if not, the tool guidelines are what
  reaches them), and whether other rows (pi-lens, lean-ctx, Sandesh) take an `about` paragraph too.
- The re-score.
