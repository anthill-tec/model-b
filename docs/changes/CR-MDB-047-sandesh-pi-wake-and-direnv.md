# CR-MDB-047 — Sandesh's Pi extension is the wake path; direnv loads the project environment

**Status:** PENDING (filed 2026-09-27; re-scoped for Sandesh 0.4.0; gap analysis 2026-09-27)
**Type:** refactor (installer requirements, scaffold, schema, skills, Pi package, contract)
**Priority:** P1 — release 1.0.0, wave 2. Every session's wake depends on it.
**Depends on:** —
**Labels:** sandesh, wake, direnv, scaffold, installer, pi-package
**Design reference:** DN-multi-harness §D20 (2026-09-27, amended for Sandesh 0.4.0; it supersedes
§D15.3's ruling to build the watcher as a Model B Pi extension); DN §D18 (skills name capabilities
and CLIs); PRD D10 (the installer detects the tools, the scaffold sets each project up); PRD D3.1
(the schema-driven registry)

## Context

**Model B's watcher.** Model B wakes an orchestrator through its own watcher: the `sandesh-watcher`
extension and the `/watcher` command in `@anthill-tec/modelb-pi`, built under §D15.3 and CR-MDB-026.
The skills carry a relaunch-on-exit rule for it. The `watcher` requirement row names that package,
which also provides worktree isolation (`modelb_worktree_enter`/`_exit`, §D19).

**What Sandesh 0.4.0 provides.** `@anthill-tec/sandesh-pi` 0.4.0 needs the `sandesh` CLI 0.4.0 or
later, and refuses an older one at session start. It carries a supervised wake watcher, started by a
tool call:
- **Defaults:** the start, status and stop verbs default to `$SANDESH_ADDRESS` and
  `$SANDESH_PROJECT`.
- **Supervision:** it relaunches after every wake, injecting a turn that names the unread ids. It
  retries once when the address is already live elsewhere, and stops with a notice on exit 1, 3
  (tombstoned) or 4 (evicted).
- **The `/sandesh-watcher` command** offers status and stop.
- **Session start:** it injects a short status block (address, listening, unread). It arms the
  watcher only under `SANDESH_AUTOSTART=1`.

The 0.4.0 CLI adds a `status` home view, and `--format toon` envelopes, for example `addressbook
--fields address,status,listening`. No CLI verb starts the supervised watcher; only the extension
does.

**Loading the environment.** Every tool reads the process environment and never parses `.env`.
Nothing loads a project's `.env` into it today: the documented `set -a; . ./.env` idiom is POSIX-only
and fails on fish.

**The gates in force.**
- **Skills name no tool:** under §D18, the CR-MDB-026 gate (`FORBIDDEN_TOOL_TOKENS`) and the CR-MDB-020
  retired-tool gate, no skill names a harness tool. That includes `sandesh_watcher` and the
  `sandesh_*` names, which sandesh-pi's tools share with Sandesh's MCP server.
- **Model B reaches Sandesh through its CLI,** never its MCP server.

## Scope

### §S1 — The installer (`modelb_axi/requirements.py`, `preflight.py`)

- **`sandesh-pi` row:** tier 1, policy `required` (was `recommended`). `--yes` still never installs a
  third-party package. The `sandesh` CLI row is `required` too, since sandesh-pi refuses a missing
  or outdated CLI.
- **The `watcher` row** becomes the `worktree` row:
  - same provider (`@anthill-tec/modelb-pi`), same `--yes` install, same policy;
  - its `tools` drop `sandesh_watcher`, keeping `modelb_worktree_enter` and `_exit`;
  - `read_tool_verdicts` reads a recorded `watcher` verdict as the `worktree` verdict, so an
    `install.toml` written before this CR still reports it.
- **`sandesh` version floor.** The `sandesh` probe runs `sandesh --version`. A version below 0.4.0
  gets the verdict `outdated`:
  - it is reported like `absent`, with the remediation `uv tool upgrade sandesh-relay`. An
    unreadable version gets the same verdict, and its warning says the floor can't be confirmed and
    names upgrading or reinstalling;
  - it is recorded in `[deps]`;
  - `init` reads it as not present.
- **direnv** is declared a tier-2 `path` probe, policy `recommended`. Its remediation names
  installing direnv and its shell hook (`direnv hook fish | source`, or `eval "$(direnv hook bash)"`).
  The hook is not probed. Its absent-warning says what stops working: the project's `.env`, including
  its wake identity, is not loaded into the environment.

### §S2 — `modelb-axi init` (`modelb_axi/scaffold.py`, `project_schema.toml`)

- **`SANDESH_ADDRESS` schema key:**
  - in `.env`, scope `root+sub`, `source = "derive"`;
  - derived as `Mainline - <SANDESH_PROJECT>`, so a monorepo sub-project derives from its own
    `SANDESH_PROJECT`;
  - validated as non-empty;
- **Quoting.** Every value `init` writes to a `.env` that contains whitespace is double-quoted,
  whatever its source, so direnv's dotenv parser accepts the file.
  - readers: bootstrap, shutdown, and Sandesh's Pi extension (the environment).
- **`.envrc`:** `init` writes `dotenv` next to every `.env` it writes, root and each sub-project,
  atomically. The file is committed and is not gitignored. A dry run lists it. A run that finds an
  `.envrc` with other content leaves it alone and reports it, under the ownership rules `init`
  already applies.
- **The queue README's Sandesh setup task** names:
  - installing direnv and its hook;
  - `direnv allow` in each directory that has an `.envrc`;
  - launching a Track with `env SANDESH_ADDRESS="Track <N> - <Project>" pi`.

  CR-MDB-048 later moves this task into the scaffolded `AGENTS.md`.
- **The scaffolded `AGENTS.md`** identity section names `SANDESH_ADDRESS` beside `SANDESH_PROJECT`.

### §S3 — The skills

All of these name the wake as a capability: "Sandesh's wake watcher, started through the harness's
Sandesh extension". They may name its `/sandesh-watcher` command, but name no harness tool.

**Bootstrap Step 1:**
- **Identity.** The role's address is `Mainline - <Project>` or `Track <N> - <Project>`, and
  `<Project>` is `SANDESH_PROJECT`, from `.env` or the environment.
- **When the environment disagrees.**
  - If `$SANDESH_ADDRESS` is unset, or names another address, bootstrap says so. For a Track this
    usually means it was launched without its `env SANDESH_ADDRESS=…` override, which matters because
    direnv exports the Mainline address in every session started from the directory.
  - It gives the remediation: load direnv, or relaunch with the override.
  - It does not stop: it carries on with the role's address passed explicitly.
- **Register and start.** It registers the address with the CLI when the addressbook shows it absent
  or inactive. It then always starts Sandesh's wake watcher for that address and project, passed
  explicitly. The start is idempotent. An address the addressbook already shows listening may be held
  by a stale watcher or another session, so bootstrap starts the watcher anyway. It checks the
  in-session watcher with `/sandesh-watcher status`.
- **Confirm.** It confirms with `sandesh addressbook --project <Project> --format toon --fields
  address,status,listening`: the address `active` and listening. It reads the Tracks' or Mainline's
  liveness the same way. It never reads the human table.
- **The extension is missing.** Bootstrap says the wake is unavailable, names the remediation, and
  carries on without a wake.

**After a wake:**
- the orchestrator fetches the named ids (`sandesh fetch --project <Project> --to '<address>'`) and
  never relaunches anything;
- on a stop notice it re-checks its liveness;
- it starts the watcher again once for exit 1 or a signal;
- it reports a tombstone (3) or an eviction (4): Mainline to the user, a Track to Mainline;
- a second exit 5 in a row stops the loop quietly, with no notice, so the in-session check is
  bootstrap's confirmation, not a notice.

**A project scaffolded before this CR:** bootstrap's remediation for a missing `SANDESH_ADDRESS` or
`.envrc` is to add them by hand. It never says to re-run `modelb-axi init`, which overwrites a
project's existing files.

**Solo** follows Mainline, wake included: it registers, starts and stops its own watcher. Only the
Track machinery (dispatching to Tracks, collecting their acks) is inert for Solo.

**The `git-workflow` skill's Pi-package release step** checks that the worktree extension loads,
not a watcher.

**Removed:** the relaunch-on-exit rule, the plain background `sandesh notify` fallback, and every
mention of the Model B watcher and `/watcher`.

**Shutdown's final step** stops its own watcher by address (Sandesh's extension, or
`/sandesh-watcher stop <address>`), then unregisters it with the CLI. The stop is the step's
documented exception. No `pkill`.

**The other files that state these rules agree:**
- `sandesh.md`: the wake section, the exit table, and Mainline's own watcher;
- `orchestration-common`: the bootstrap/shutdown bracket and the notifier-kill override;
- `orchestration-mainline`: the inbox watcher;
- `orchestration-track`: shutdown.

### §S4 — `@anthill-tec/modelb-pi` (`pi-package/`)

- `extensions/sandesh-watcher.ts` and `/watcher` are removed.
- `package.json` lists only `extensions/worktree.ts`.
- The package README (generated from the install guide) and `docs/install-guide.md` describe the
  `worktree` capability, `sandesh-pi` as required, the `sandesh` version floor, and direnv.

### §S5 — The contract (`contracts/sandesh-cli.md`)

The contract records Sandesh 0.4.0 as Model B relies on it:
- the version floor;
- `status` and `--format toon`;
- the notify exit table, as sandesh-pi's supervision treats it;
- that only the extension starts the supervised watcher;
- every exit, including 2 (timeout, relaunched silently) and a signal.

**The retired tests are listed:** every test class and module this CR retires or migrates is named
in a test module's docstring.

## Acceptance criteria

- [ ] **Requirements.**
      - `REQUIREMENTS` declares `sandesh-pi` as tier-1 `required`.
      - It declares a `worktree` row (provider `@anthill-tec/modelb-pi`, tools without
        `sandesh_watcher`) and no `watcher` row.
      - It declares a tier-2 `direnv` path probe with the hook remediation.
      - A recorded `watcher` verdict is read as `worktree`'s.
- [ ] **Version floor.** In a sandbox with a fake `sandesh`:
      - `--version` 0.3.9 gives `outdated`, recorded in `[deps]` and reported with
        `uv tool upgrade sandesh-relay`;
      - 0.4.0 gives `detected`;
      - `init` reads `outdated` as not present.
- [ ] **`init` writes the identity and `.envrc`.**
      - It writes `SANDESH_ADDRESS="Mainline - <SANDESH_PROJECT>"` in every `.env` it writes, root and
        sub-project, each from its own `SANDESH_PROJECT`.
      - It writes `.envrc` containing exactly `dotenv\n` beside each one, not gitignored, listed by
        `--dry-run`.
      - A pre-existing `.envrc` with other content is left alone and reported.
- [ ] **Quoting.** Every whitespace-containing value in a scaffolded `.env` is double-quoted. A test
      parses the scaffolded `.env` (standalone and monorepo, with a name containing a space) with a
      dotenv grammar compatible with direnv's and gets every key. The `sandesh` CLI row is `required`.
      The unreadable-version warning and direnv's absent-warning state what §S1 gives them.
- [ ] **The setup task** names direnv, its hook, `direnv allow`, and the Track launch line. The
      identity section names `SANDESH_ADDRESS`.
- [ ] **Bootstrap:**
      - the role's address is passed explicitly;
      - it states the warning for an unset or mismatched `$SANDESH_ADDRESS` and carries on;
      - it registers if absent or inactive, then starts the watcher;
      - it confirms with `addressbook --format toon --fields address,status,listening`;
      - it handles a missing extension.

      No skill reads liveness from the human table (`● live`).
- [ ] **No skill contains** "relaunch" for the wake, "Model B watcher", `/watcher`, `pkill`, a
      background `sandesh notify` launch, or a harness tool name. The CR-026 and CR-020 gates hold,
      or are migrated with each migration listed.
- [ ] **Shutdown** stops the watcher by address, then unregisters, as its final step.
- [ ] **Bootstrap always starts the watcher**, with no skip on an address already listening, and checks
      it with `/sandesh-watcher status`. The exit-5 row says a second exit 5 stops quietly. The
      older-project remediation says to add the keys by hand and never says to re-run `init`. Solo
      follows Mainline for its own watcher in both skills. `git-workflow`'s Pi-package release step
      names the worktree extension, not a watcher.
- [ ] **After a wake,** the skills say: fetch only; on a stop notice, one restart for exit 1 or a
      signal; report exits 3 and 4.
- [ ] **`sandesh.md` and the orchestration files** agree with bootstrap and shutdown. Each line that
      changed is checked by a test.
- [ ] **The Pi package.** `pi-package/` has no `sandesh-watcher.ts`, and `package.json` lists only
      `worktree.ts`. The tests of the removed extension are retired, and each is listed by id in a
      test module's docstring. The worktree
      extension's tests still pass.
- [ ] **Docs and contract.** The install guide and the generated package README match §S4, and
      `build.py --check` is clean. `contracts/sandesh-cli.md` records §S5, exits 2 and a signal included. No source comment carries a
      literal `\u` escape.
- [ ] **No test reads the real `~/.pi`, `install.toml` or `sandesh` binary for the new behaviour.**
      The suite baselines are re-measured in `AGENTS.md`.

## Non-goals

- Sandesh's diagnostic for an identity in `./.env` that is not exported: Sandesh's own CR.
- `SANDESH_AUTOSTART`: Model B leaves it unset, and bootstrap starts the watcher.
- Writing the user's shell configuration, or running `direnv allow` for the user.
- Projects scaffolded before this CR: bootstrap works without their `SANDESH_ADDRESS` or `.envrc`,
  and names adding them by hand as the remediation.
- An ownership guard for `init` over a project's existing `.env` and `AGENTS.md`.
- The queue README's retirement (CR-MDB-048).
