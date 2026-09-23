# CR-MDB-036 — Harness capability contract and installer stack selection

**Status:** PENDING (rewritten 2026-09-24 at gap-analysis: §S9–§S11 split to CR-MDB-037 and §S5
cut, user ruling; earlier versions are git history and are not to be consulted for contracts)
**Type:** feature
**Priority:** P1 — in release 1.0.0, wave 2. On a vanilla Pi the deployed assets degrade silently:
they install, they look correct, and they cannot work.
**Depends on:** — (CR-MDB-033 and CR-MDB-025, on which earlier versions depended, have shipped)
**Labels:** installer, preflight, harness, pi, stacks, feature
**Phase:** Wave 5 (repo queue) · release 1.0.0 wave 2 (Crucible board)
**Design reference:** PRD D11 (capability contract, stack-scoped installation; amended 2026-09-24)
· PRD D10(c) (provider's own install method, on confirm) · `modelb_axi/preflight.py` (the existing
stage and its FAIL / install-on-confirm / WARN vocabulary) · CR-MDB-033 §S6 (install envelope
outcomes) · DN-multi-harness-deploy-model §D17 (agents are rendered per project, not installed) ·
Pi `docs/packages.md`, `docs/environment-variables.md` (the settings the probe reads)

**Target set:** Pi only (DN §D13/§D14).

## Context — measured

A deployed Model B asset can only run if the harness provides capabilities a vanilla Pi does not
have, and nothing in the installer checks them. Measured on this machine, 2026-09-22/24:

- **Dispatch** — `@gotgenes/pi-subagents` provides `subagent`, `get_subagent_result` and
  `steer_subagent`, and reads agent definitions. Without it every rendered definition is inert.
- **Shell** — `pi-lean-ctx` provides the `ctx_*` tools. `ctx_shell` is the only shell a dispatched
  child has: a probe of `bash, shell, exec, run, terminal, sh, command` resolved none.
- **Permissions** — `@gotgenes/pi-permission-system` reads `permission:` frontmatter. Without it
  those keys are ignored; VERIFY stays read-only because its `tools:` line omits write tools.
- Pi loads a package only if `<agent-dir>/settings.json` `packages[]` lists it; the agent dir is
  `$PI_CODING_AGENT_DIR`, else `~/.pi/agent`. npm packages resolve under `<agent-dir>/npm/node_modules/`.
  Entries are strings (`npm:<name>[@<version>]`, `git:…`, a URL, a local path) or objects whose
  `source` is such a string and whose `extensions: []` loads no extensions. Presence on disk is not
  loading: `<agent-dir>/npm/node_modules/@pi-archimedes/` exists here, empty and unlisted.
- `preflight.py` probes `shutil.which("crucible")`. There is no such binary; the released Crucible
  clients live in `~/.crucible/clients/` with a `crucible-clients.json` manifest, so the probe
  reports `absent` on a working install.
- `deploy.py` ships every skill bundle to everyone; the installer has `--harnesses` but no
  `--stacks`.

## Scope

### §S1 — The requirement, declared once
One declarative structure in `modelb_axi/` lists every requirement, as data read by the pre-flight
and the scaffold. Each row names: an id, its tier, the provider, the policy, its scope (always, or
the stacks that need it), the asset families that depend on it, the remediation, and — for a
harness capability — the tool names it provides (CR-MDB-020 §S5 checks skills against these).

| Tier | Id | Provider | Policy | Scope |
|---|---|---|---|---|
| 1 | `dispatch` | `@gotgenes/pi-subagents` | required | always |
| 1 | `lean-ctx` | `pi-lean-ctx` | required | always |
| 1 | `permissions` | `@gotgenes/pi-permission-system` | recommended | always |
| 2 | `uv` | uv | required | always |
| 2 | `sandesh` | `sandesh-relay` (via `uv tool install`) | recommended, install-on-confirm | always |
| 2 | `crucible` | Crucible's released clients: `~/.crucible/clients/crucible-clients.json` | recommended | always |
| 2 | `crucible-client` | `~/.crucible/clients/<client>-crucible.py` | recommended | per selected stack |
| 2 | `python3`, `bash` | the OS | recommended | always (tool scripts; `gate-lock.sh` needs `bash`) |
| 2 | `gh`, `jq` | their projects | recommended | always |
| 3 | toolchain | see §S8 | recommended | per selected stack |

The Crucible server is not probed: it is up or down from minute to minute, and a recorded verdict
would be stale on arrival. Ingest failures surface at run time, where the clients report them.

### §S2 — Probe capability, not package presence
A harness capability is `detected` only if its npm package is listed in `packages[]` — matched by
package name, ignoring any `@version`, as a string or as an object's `source`, and not with
`extensions: []` — **and** resolves under `<agent-dir>/npm/node_modules/<name>/package.json`.
Listed but not on disk, or on disk but not listed, is `absent`. When no npm entry matches but the
list holds `git:`, URL or local entries (which could provide the package under another spec), the
verdict is `unknown`. An unreadable or unrecognised settings file is `unknown` — the probe never
crashes on another tool's configuration and reads no key but `packages`. The installer reads the
personal settings only; project `.pi/settings.json` is a project's concern.

### §S3 — Policy per capability
- A missing **required** capability (`dispatch`, `lean-ctx`, `uv`) exits non-zero with outcome
  `preflight_failed`, naming the asset families that would be inert — unless
  `--allow-missing-capabilities` is given, which is documented in `--help` and recorded in
  `install.toml`.
- `unknown` and a missing **recommended** capability WARN, naming the consequence, and continue.
- Model B never installs a third-party extension, and never edits `settings.json`. For a missing
  extension it names Pi's own command (`pi install npm:<package>`) and offers to run it only on an
  explicit interactive confirmation; `--yes` never confirms a third-party install. Sandesh keeps its
  existing install-on-confirm behaviour (it is Model B's own ecosystem).

### §S4 — Record the verdicts
`install.toml` gains a `[capabilities]` table (id → verdict), the selected `stacks` in `[install]`,
and the override flag when used, so a later run or a support question can see what the harness
looked like at install time without re-probing.

### §S6 — Scaffolded projects inherit the contract
`modelb-axi init` writes the contract into the scaffolded `AGENTS.md`: the tier-1 capabilities and
the selected stacks' toolchains, each with its remediation, so a clone on a vanilla Pi shows what
is missing.

### §S7 — A stack selector on the installer
- The installer accepts `--stacks CSV` with `init`'s vocabulary (`arduino, bun, python, quarkus,
  rust, java`); omitting it selects all, so current behaviour is unchanged. An unsupported name is
  rejected with a message listing the supported stacks.
- Interactively (no `--yes`, no `--stacks`) the user is offered the list; `--yes` takes the default.
  Selection is a choice, never inferred from the machine.
- **Selection scopes the report bundles**: a stack deploys `crucible-report-<stack>`, except
  `quarkus` and `java`, which both deploy `crucible-report-java`. Every bundle not named
  `crucible-report-*`, the hook scripts and the tool scripts always deploy. The installer deploys no
  agent definitions (DN §D17).
- The selection persists in `install.toml`; a re-run with a wider `--stacks` adds the new stack's
  assets without disturbing the rest of the manifest.

### §S8 — Toolchains: probed cheaply, installed only on confirmation
- **Only selected stacks are probed.** An unselected stack costs no probe, warning or mention.
- **Probe by resolution** (`shutil.which`), never by execution — `command -v` across five
  toolchains costs ~1 ms here; one `mvn -version` ~227 ms. The one exception is python's
  `xmlrunner` and `coverage`, dependencies of the Crucible client: they are checked by the PATH
  `python3` (`python3 -c "import …"`), because the installer runs inside its own uv environment and
  its interpreter is not the one the client uses.

  | Stack | Probed | Client |
  |---|---|---|
  | python | `python3`; modules `xmlrunner`, `coverage` | `python-crucible.py` |
  | rust | `cargo`, `cargo-nextest`, `cargo-llvm-cov` | `rust-crucible.py` |
  | quarkus, java | `mvn`, `java` | `mvn-crucible.py` |
  | bun | `bun`, `node` | `bun-crucible.py` |
  | arduino | `arduino-cli`, `g++` | `arduino-crucible.py` |

- An absent toolchain for a selected stack **WARNs and continues** (a machine that is not the build
  machine is legitimate), records `absent`, and names the provider's own installer (`rustup`,
  `cargo install cargo-nextest`, `bun`'s installer, `arduino-cli`'s installer, a JDK/Maven source).
  For `xmlrunner`/`coverage` it names the exact install command.
- The installer **offers to run the provider's installer on explicit interactive confirmation**
  (user ruling 2026-09-24); `--yes` never confirms it, and an installer that needs elevated
  privileges (a distro JDK package) is named, never run. Declining is recorded and the install
  continues.

## Acceptance criteria

### §S1
- [ ] One declarative structure in `modelb_axi/` holds every §S1 row with all its fields; adding a
      requirement touches only that structure and its test.
- [ ] Each tier-1 row lists the tool names its provider supplies: `dispatch` → `subagent`,
      `get_subagent_result`, `steer_subagent`; `lean-ctx` → every `ctx_*` tool and `lean_ctx`.
- [ ] The `crucible` verdict comes from `~/.crucible/clients/crucible-clients.json`, never from a
      `crucible` binary on PATH; no probe contacts a Crucible server.

### §S2
- [ ] The probe reads `$PI_CODING_AGENT_DIR/settings.json` when the variable is set, else
      `~/.pi/agent/settings.json`; every probe test runs against a sandboxed agent dir.
- [ ] One test per case: listed and on disk → `detected`; on disk, unlisted (the empty
      `@pi-archimedes` shape) → `absent`; listed, not on disk → `absent`; `npm:<name>@<version>` →
      matched; object form with `source` → matched; object form with `extensions: []` → `absent`;
      no npm match with a `git:` entry present → `unknown`; malformed JSON → `unknown`, no crash.

### §S3
- [ ] A missing `dispatch` or `lean-ctx` exits non-zero with outcome `preflight_failed` and names
      the inert asset families; with `--allow-missing-capabilities` the install proceeds and
      `install.toml` records the override.
- [ ] A missing `permissions`, or an `unknown` verdict, WARNs with its consequence and continues.
- [ ] A non-interactive (`--yes`) run against a sandbox agent dir lacking every extension installs
      nothing and leaves `settings.json` byte-identical — asserted by a diff.
- [ ] The pre-flight prints, before any remediation, one line per group on stderr:
      `harness: dispatch=<v> lean-ctx=<v> permissions=<v>`, then `deps: uv=<v> sandesh=<v>
      crucible=<v>`, then one `stack <name>: <probe>=<v> … client=<v>` line per selected stack.

### §S4
- [ ] `install.toml` carries `[capabilities]`, `[install].stacks`, and the override flag when used;
      a round-trip test writes and reads them back, and a pre-036 `install.toml` still loads.

### §S6
- [ ] `init` writes the tier-1 capabilities and the selected stacks' toolchains, with remediations,
      into the scaffolded `AGENTS.md`; a python-only project names no other stack's toolchain.

### §S7
- [ ] `--stacks` accepts `init`'s vocabulary; omitting it selects all; an unsupported name is
      rejected listing the supported stacks.
- [ ] `--stacks python` deploys `crucible-report-python` and no other `crucible-report-*`;
      `--stacks quarkus` and `--stacks java` each deploy `crucible-report-java`; every other bundle,
      the hook scripts and the tool scripts deploy in all cases; no agent definition is written.
- [ ] With neither `--stacks` nor `--yes`, the selection is offered; `--yes` takes the default
      without reading stdin.
- [ ] The selection round-trips through `install.toml`, and a re-run with a wider `--stacks` adds
      the new stack's bundle leaving the other manifest entries unchanged.

### §S8
- [ ] A single-stack selection probes only that stack's table row — asserted by counting probe
      calls.
- [ ] Toolchain probes resolve binaries without executing them; the only subprocess any probe runs
      is the PATH `python3` import check for `xmlrunner`/`coverage`, and only when python is
      selected.
- [ ] An absent toolchain WARNs, records `absent`, names the provider's installer, and the install
      succeeds; `xmlrunner`/`coverage` absence names the exact install command.
- [ ] Under `--yes`, no toolchain installer runs; interactively, one runs only after an explicit
      yes, an elevated-privilege installer is never run, and declining is recorded.

### Close-out
- [ ] **Measured, not assumed:** the installer's harness verdicts, run read-only against this
      machine's real agent dir, report `dispatch`, `lean-ctx` and `permissions` as `detected`, and a
      dispatched agent calls `ctx_shell` — recorded with the transcript reference.

### Migration
- [ ] Tests asserting the old `deps:` line, the `crucible` binary probe, the `install.toml` schema,
      or the scaffolded `AGENTS.md` — and tests depending on them without naming them — are migrated
      and listed by id in the RED report. Starting set: `test_installer`,
      `test_installer_correctness`, `test_scaffold`.

## Estimated size

A requirements module (the §S1 data), a harness probe, a stack-scoped extension of `preflight.py`,
`deploy.py` bundle scoping, a `--stacks` and an override flag in `cli.py`, a `config.py` schema
extension, an `AGENTS.md` template change, tests. Medium-large.

## Non-goals

- No vendoring or bundling of third-party extensions (CR-MDB-029 ships Model B's own package).
- No harness but Pi. No auto-repair of a harness config.
- No Crucible server probe.
- The install guide, deployed-asset freshness and the permission policy are CR-MDB-037.
