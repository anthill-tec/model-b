## Quick start

If you already have Pi and the `modelb-axi` command (see [Prerequisites](#prerequisites), step
5), the whole install is:

```sh
pi install npm:@gotgenes/pi-subagents
pi install npm:pi-lean-ctx
pi install npm:@gotgenes/pi-permission-system
modelb-axi --yes --harnesses pi --target-root ~ --stacks python
```

Replace `python` with the stacks you work in (see [Choosing stacks](#choosing-stacks)). The
rest of this guide explains each step, every line the installer prints, and what to do when a
line is not what you expected.

## Prerequisites

Install these in the order given; no step relies on one that comes after it.

1. **Pi.** The `pi` command must be on your `PATH`. Install it by Pi's own instructions.
   Model B deploys into Pi's reach; it does not install Pi.
2. **Pi's packages.** Model B's assets rely on four Pi packages. Install them with Pi's own
   command (the installer can also offer to run these for you, see
   [Install offers](#install-offers)):
   - `dispatch` — required: `pi install npm:@gotgenes/pi-subagents`
   - `lean-ctx` — required: `pi install npm:pi-lean-ctx`
   - `permissions` — recommended: `pi install npm:@gotgenes/pi-permission-system`
   - `watcher` — recommended, Model B's own package: `pi install npm:@anthill-tec/modelb-pi`
3. **`uv`** — required. It installs the installer itself:
   `curl -LsSf https://astral.sh/uv/install.sh | sh`
4. **`git`** — required to create a project: every project `modelb-axi init` creates is a
   git repository. Install it from your operating system's package manager.
5. **The installer.** Model B's installer, the `modelb-axi` command, is installed from PyPI
   with `uv`:

   ```sh
   uv tool install modelb-axi
   modelb-axi --version
   ```

   To update later, run `uv tool upgrade modelb-axi`.

   From a source copy of Model B, run `uv tool install .` from the root of that copy instead;
   to update, run `uv tool install --reinstall .` from a newer copy.
6. **Recommended tools.** The install goes ahead without them, but some assets will not work
   (see [Warnings: what stops working](#warnings-what-stops-working)):
   - `sandesh` — `uv tool install sandesh-relay` (the installer offers to run this for you);
   - `crucible` — Crucible's released clients, installed with Crucible's own installer; the
     installer looks for their manifest at `~/.crucible/crucible-clients.json`;
   - `python3`, `bash` and `jq` — from your operating system's package manager;
   - `gh` — the GitHub CLI, from https://cli.github.com.

## Choosing stacks

A *stack* is a language toolchain you write and test code in. The installer supports six:
`arduino`, `bun`, `python`, `quarkus`, `rust` and `java`.

Choose them with `--stacks`, comma-separated, for example `--stacks python,rust`. Without
`--stacks`, an interactive run asks you (press Enter for all of them); a run with `--yes` takes
all six. An unknown name stops the run before anything is checked or written, with the
outcome `stacks_rejected` and the list of supported stacks.

For each stack you choose, the installer:

- deploys that stack's test-reporting skill, `crucible-report-<stack>` (`quarkus` and `java`
  share `crucible-report-java`); `rust` also deploys the `code-health` skill;
- checks the stack's toolchain and its Crucible client, one `stack <name>:` line each (see
  [Reading the pre-flight](#reading-the-pre-flight));
- records the choice in `install.toml`.

A stack does not install its toolchain: a missing tool is reported, and where the tool's own
installer can run without elevated privileges the installer offers to run it — nothing more.
It does not install Crucible's clients either. The hook scripts, the workflow scripts and every
other skill but `code-health` are deployed whatever stacks you choose, and a project's own
stacks are chosen separately, when you create it with `modelb-axi init --stacks`.

## Reading the pre-flight

Before it writes anything, the installer checks the machine and prints one line per group. A
typical run with `--stacks python` prints:

```text
harness: dispatch=detected lean-ctx=detected permissions=detected watcher=detected
deps: uv=detected sandesh=detected crucible=detected
stack python: python3=detected xmlrunner=absent coverage=detected client=detected
```

- `harness:` — the four Pi packages. A package counts as `detected` only when Pi would load
  it: it is listed in `packages` in `~/.pi/agent/settings.json` (not switched off with
  `"extensions": []`) and it is present under `~/.pi/agent/npm/node_modules/`. If you keep
  Pi's settings elsewhere, set `PI_CODING_AGENT_DIR` and the installer looks there instead.
- `deps:` — `uv`, `sandesh` and `crucible`. Crucible is judged by its clients' manifest,
  `~/.crucible/crucible-clients.json`, never by a running server.
- `stack <name>:` — one line per chosen stack: each toolchain tool, then `client=` for that
  stack's Crucible client, looked up in the same manifest. The tools checked are:
  `python` — `python3`, `xmlrunner`, `coverage` (the last two must import in the `python3` on
  your `PATH`); `rust` — `cargo`, `cargo-nextest`, `cargo-llvm-cov`; `bun` — `bun`, `node`;
  `arduino` — `arduino-cli`, `g++`; `quarkus` and `java` — `mvn`, `java`.

Each check ends in one of four verdicts:

- `detected` — present and usable.
- `absent` — not found. What that costs is in
  [Warnings: what stops working](#warnings-what-stops-working).
- `unknown` — the installer could not tell: Pi's settings file cannot be read or lists a
  package from a source other than npm; the Crucible manifest does not parse; or an import
  check could not run. The installer warns and carries on.
- `installed` — was absent, you accepted an offer to install it, and a second check found it.
  After a Sandesh install you see a second line, `deps: uv=detected sandesh=installed ...`;
  other `installed` verdicts are recorded in `install.toml`.

All warnings are printed after these lines, so the lines always show what was found before
anything was changed.

## Warnings: what stops working

Each warning names the missing piece, what will not work without it, and the command that
provides it. By requirement:

| Requirement | If it is missing |
|---|---|
| `dispatch` | the agent definitions and the orchestration skills are inert: nothing can start a sub-agent. Required — see [Missing capabilities](#missing-capabilities). |
| `lean-ctx` | the agent definitions and the tool scripts are inert: they call its tools. Required — see [Missing capabilities](#missing-capabilities). |
| `permissions` | the agent definitions' permission: frontmatter is ignored, so sub-agents run without their declared tool limits, and a project's permission policy has nothing to enforce it. |
| `watcher` | the orchestration skills cannot keep a session listening for Sandesh messages: nothing wakes the session when a message arrives. |
| `uv` | the modelb-axi installer cannot be installed or updated and the Sandesh install cannot run; the pre-flight stops at once. |
| `sandesh` | the bootstrap and shutdown skills cannot send or watch for messages. |
| `crucible` | the crucible skills and the crucible-report-* skill bundles have no client to report test runs through. |
| `crucible-client` | that stack's `crucible-report-<stack> skill bundle` has no client (a `stack <name>:` line shows `client=absent`). |
| `python3` | the tool scripts and hook scripts, which are Python, will not run. |
| `bash` | the tool scripts (gate-lock.sh) will not run. |
| `gh` | the git-workflow skill cannot reach GitHub (pull requests, releases). |
| `jq` | the tool scripts that call it will not run. |
| `toolchain` | that stack's tests cannot run on this machine, so its agent definitions cannot carry out test-first work there; shown as `<tool>=absent` on the `stack <name>:` line. |

Only `uv`, `dispatch` and `lean-ctx` stop an install. Every other warning is recorded and the
install continues, so you can fix it later and re-run.

## Install offers

When something is missing and there is a command that would provide it, an interactive run can
offer to run that command for you:

- **Pi's packages.** For each absent package, and only when `pi` is on your `PATH`:
  ``dispatch=absent — run Pi's own `pi install npm:@gotgenes/pi-subagents`? [y/N]``.
  Pi installs the package and updates its own settings; Model B never edits Pi's settings.
  These offers come before the required-package check, so accepting them can turn a failing
  pre-flight into a passing one.
- **Toolchain installers.** For a missing tool whose own installer needs no elevated
  privileges, and when the command that installer starts with is on your `PATH`, for example ``Run `curl -fsSL https://bun.sh/install | bash` to install bun for
  stack bun? [y/N]``. The same installer is offered once even when it provides several tools
  (`python3 -m pip install unittest-xml-reporting coverage` covers both Python modules). Tools
  that need elevated privileges (`mvn`, `java`, `node`, `g++`, `python3`) are only named,
  never run.

These offers need an explicit `y` or `yes`; pressing Enter declines, and a decline is recorded
as a warning. A command you accept runs in your terminal, so you see its output and answer its
own prompts. Afterwards the tool is checked again: `installed` if it is now found, otherwise
`absent` with a warning saying where it was expected (for example `~/.cargo/bin`, which must
be on your `PATH`).

`--yes` never confirms these offers. It makes the run non-interactive: it never reads the
keyboard, accepts the defaults (proceed; all stacks unless `--stacks` is given; the detected
harnesses unless `--harnesses` is given), and skips every offer above, leaving its warning. A
run whose input is not a terminal behaves the same way.

The installs `--yes` does accept are Model B's own. When `sandesh` is absent the installer
asks ``Sandesh not found — install via `uv tool install sandesh-relay`? [Y/n]``. When `pi` is
among the harnesses you install for and Model B's own Pi package is absent, it asks
``watcher=absent — install Model B's own Pi package via `pi install npm:@anthill-tec/modelb-pi`? [Y/n]``.
In both, Enter means yes and a decline is recorded as a warning. Under `--yes`, and in a run
whose input is not a terminal, they run without asking. The command runs in your terminal and
the package is checked again afterwards, exactly as for the offers above.

## Missing capabilities

`dispatch` and `lean-ctx` are required. If either is `absent`, the installer prints an error
naming what would be inert and the `pi install` command that provides it, then stops with the
outcome `preflight_failed`. Nothing is deployed and no `install.toml` is written. Install the
package and run the installer again.

To install anyway — for example on a machine where you will add the packages later — add
`--allow-missing-capabilities`:

```sh
modelb-axi --yes --harnesses pi --target-root ~ --stacks python --allow-missing-capabilities
```

The same messages become warnings, the install completes, the assets that depend on the
missing package stay inert until you install it, and `install.toml` records that the override
was used.

A required package reported `unknown` does not stop the install; it is a warning, because the
installer cannot prove the package is missing. `permissions` and `watcher` are recommended
rather than required: when either is absent you get a warning, never a failure.

## Install outcomes

Every run ends with one summary on standard output, whose `outcome` is one of:

| Outcome | Meaning | Exit code |
|---|---|---|
| `installed` | The assets were deployed and `install.toml` written. The summary lists the target root, the number of managed files, and any files it left alone. | 0 |
| `deploy_skipped` | The checks ran, but no `--target-root` (or `MODELB_TARGET_ROOT`) was given, so no assets and no `install.toml` were written (a `sandesh` install the checks made still happened). See [Installing into your home directory](#installing-into-your-home-directory). | 0 |
| `already_installed` | `install.toml` already exists and `--reinstall` was not given. Nothing is deployed; the summary reports the state of what is deployed (below). | 0 |
| `preflight_failed` | `uv` is missing, or a required Pi package is missing without `--allow-missing-capabilities`. Nothing was written. | 1 |
| `stacks_rejected` | `--stacks` (or your answer to the stacks question) named an unsupported stack. Nothing was written. | 1 |
| `harness_rejected` | `--harnesses` named something other than `pi`, or `install.toml` records a harness this version no longer supports (one an older install targeted). Nothing was written. The error prints the re-run that replaces it, with your values: `modelb-axi --reinstall --target-root <dir> --stacks <stacks> --harnesses pi`. | 1 |
| `aborted` | You answered no to "Proceed with installation?" or to the detected-harness question. Nothing was written. | 1 |
| `deploy_failed` | Copying the assets failed (for example a directory could not be written). No `install.toml` is written, and an existing one is left as it was. | 1 |

The summary also carries every warning printed, the `deps` verdicts and the selected harnesses.

**Files the installer leaves alone.** A file at a path the installer deploys to that it did not
put there is reported as `unmanaged` and never overwritten. A file it deployed that you have
since edited is reported as skipped and left as you edited it, unless you re-run with
`--force-managed`.

**Files the installer removes.** A `--reinstall` removes each file it deployed earlier and no
longer deploys (a skill of a stack you dropped, or one no longer shipped) when the file is
unchanged, and any directory that leaves empty. The `installed` summary lists those paths in
`removed`, and in `kept` the ones it left in place because you edited them. A kept file is
warned about, stays recorded in `install.toml`, and is reported again by every later run until
you restore or delete it; `--force-managed` never removes an edited file.

If `install.toml` records a different target root from this run's `--target-root`, nothing is
removed: the files under the old target root are left in place and are no longer managed, so
no later run updates or removes them. The run warns, naming the old root.

**The `already_installed` report.** Running `modelb-axi` on a machine that already has an
install compares what is deployed with what the installed package ships. `freshness` is
`current` when everything matches, `outdated` when one of these lists is not empty:

- `stale` — unchanged since it was deployed, but the package now ships a newer version:
  re-run with `--reinstall` (and your `--target-root`, `--stacks` and `--harnesses`, plus
  `--modelb-home` if you used one).
- `hand_modified` — edited since it was deployed: keep it, or re-run with `--reinstall` and
  `--force-managed` to replace it.
- `retired` — deployed earlier, but no longer deployed (no longer shipped, or its stack is no
  longer selected): re-run with `--reinstall` (the command the report prints), which removes
  them.
- `kept` — no longer deployed, and left in place because you edited it: restore or delete it,
  then re-run with `--reinstall` (the command the report prints).

An `install.toml` written by an older version records no target root; the report is then
`freshness: unknown` with a warning telling you to re-run with `--reinstall --target-root`.

## Installing into your home directory

The installer deploys into your home directory only when you say so. Pass the target
explicitly:

```sh
modelb-axi --yes --harnesses pi --target-root ~ --stacks python
```

With `--target-root ~` it writes:

- the skills to `~/.agents/skills/`, where Pi finds them;
- the hook scripts to `~/.agents/hooks/scripts/`;
- the workflow scripts to `~/.agents/scripts/`;
- the record of the install, `install.toml`, to `~/.local/share/modelb/` (or
  `$XDG_DATA_HOME/modelb`; override with `--modelb-home` or `MODELB_HOME`).

Without `--target-root` (and without `MODELB_TARGET_ROOT` set), every check still runs but no
asset and no `install.toml` is written, and the outcome is `deploy_skipped`. That is not
quite a dry run: the checks' install offers still act on your machine, whatever the target.
If `sandesh` is missing, a run with `--yes`, or one whose input is not a terminal, installs it
into your home directory (`uv tool install sandesh-relay`) before it ends; an interactive run
installs it unless you answer no, and runs any other offer you accept. For a run that changes
nothing, have `sandesh` installed first and answer no to every offer.

To try a full install without touching your home directory's Model B files, point both
locations at a scratch directory (the same caveat about `sandesh` applies):

```sh
modelb-axi --yes --harnesses pi --stacks python --target-root /tmp/modelb-trial --modelb-home /tmp/modelb-trial/state
```

## Adding stacks later

The installer does not remember your earlier stack choice when you run it again, so name every
stack you want, not only the new one. Once installed, re-running needs `--reinstall`:

```sh
modelb-axi --yes --harnesses pi --target-root ~ --reinstall --stacks python,rust
```

This deploys the new stack's `crucible-report-<stack>` skill (for `rust`, the `code-health`
skill too), runs the new `stack <name>:` checks, and records the new list in `install.toml`. A
`--reinstall` under `--yes` without `--stacks` selects all six stacks.

A `--reinstall` naming fewer stacks removes the dropped stacks' skills that are unchanged since
they were deployed. One you have edited is left in place and reported as `kept`.

A project keeps its own list of stacks. To change it, run from the project's root:

```sh
modelb-axi agents --stacks python,rust
```

This re-renders the project's agent definitions for the new list and records it in the
project's `.env`. Agent definitions you have edited are left alone.

## Project trust

Pi loads a project's own settings, extensions, skills, prompts and themes (`.pi/settings.json`,
`.pi/extensions`, `.pi/skills`, `.pi/prompts`, `.pi/themes`) only once the project is
*trusted*. `.pi/agents` is not covered by trust.

A project created with `modelb-axi init` depends on two things under `.pi/extensions`:

- its hooks, the `.ts` files that run Model B's checks at points in a Pi session;
- its permission policy, `.pi/extensions/pi-permission-system/config.json`, read by the
  `pi-permission-system` package: anything not listed is asked about (`"*": "ask"`); the
  workflow's tools and skills are allowed; reads of `~/.agents/*`, `~/.crucible/*`,
  `~/.pi/agent/*` and `/tmp/*` are allowed, and so are reads of `~/.bun/install/*` when the
  `pi` on your `PATH` was installed with bun (Pi's own code); writes outside the project are
  allowed only under `/tmp/*`.

Until the project is trusted, Pi does not load either of them: the hooks do not run and the
policy does not apply. If a saved decision says the project is untrusted, Pi skips them without
asking. Only your global policy,
`~/.pi/agent/extensions/pi-permission-system/config.json`, applies then.

**Trusting a project.** Open Pi in the project's root and run `/trust`. Pi saves the decision
in `~/.pi/agent/trust.json`. A saved decision applies to a directory and everything below it,
and the closest one wins: if you once declined trust for your home directory, every project
under it is untrusted until you run `/trust` in that project.

**What `init` tells you.** When `init` writes under `.pi/extensions`, it reads Pi's saved
decision for the new project and reports it as `trust` in its summary: `trusted`,
`untrusted`, `ask` (no saved decision, so Pi will ask) or `unknown` (Pi's files could not be
read). For `untrusted` and `ask` it prints a warning naming `/trust`. This is Pi's saved
decision only; starting Pi with `--approve`, or an extension, can decide differently for one
session. Model B never changes `trust.json` — trusting a project is always your decision.

**Where workflow permissions come from.** Workflow permissions come from each project's policy,
loaded once you run `/trust` in the project. The installer does not read or report your global
policy, and Model B never writes it.

**Creating a project.** For example:

```sh
modelb-axi init --name "My Project" --token myproject --acronym MYP --mode solo --repo-shape standalone --stacks python --owner your-github-name --target ~/code/myproject
```

Add `--dry-run` to see what would be written without writing anything.
