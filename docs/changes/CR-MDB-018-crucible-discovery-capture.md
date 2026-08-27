# CR-MDB-018 — Crucible discovery capture: the installer probes the wrong binary and never records the clients dir the hook reads

**Status:** PENDING
**Type:** bugfix
**Priority:** P1 (blocks release 0.1.0 — a shipped hook reads a config key the installer never writes, so the feature is dead on every install)
**Depends on:** CR-MDB-014 (pre-flight + install.toml), CR-MDB-015 (the hook that consumes the key)
**Labels:** installer, preflight, crucible, discovery, patch
**Phase:** Wave 5
**Design reference:** `crucible:crucible_axi/manifest.py` (the discovery manifest — CR-CRU-009 §S2) · `crucible:crucible_axi/cli.py` (`--target-dir`, default `~/.crucible`) · `crucible:docs/RUNBOOK.md` (the published manifest location) · `crucible:install.sh` (the installed CLI name and upgrade path) · PRD §D10 (installer = dependency orchestrator) · Sandesh #1357, #1358

## Context

Two defects on the same seam — Model B's installer is supposed to CAPTURE where Crucible's
clients live, and the session-start hook is supposed to CONSUME that. Neither half works.

**Defect 1 — the pre-flight probes a binary name that does not exist.**
`modelb_axi/preflight.py:77` runs `shutil.which("crucible")`. Crucible's installed CLI is
**`crucible-axi`** (`crucible:install.sh:13-14` — "it installs the `crucible-axi` primary
orchestrator from PyPI"; `:29`, `:53` invoke `crucible-axi uninstall`). A machine with a
correct, current Crucible install is therefore reported `crucible=absent`, and
`_CRUCIBLE_ABSENT_WARNING` (`preflight.py:39-42`) tells the user to install something they
already have. The verdict is persisted into `install.toml` `[deps]`, so the wrong answer
is durable.

**Defect 2 — the hook's discovery key is written nowhere.**
`hooks-src/scripts/ambient-board-status:66` reads
`config["install"]["clients_dir"]` out of `$MODELB_HOME/install.toml` and returns `None`
when it is missing, which the hook renders as the degrade note "no status feed resolved".
`modelb_axi/config.py:8` documents `[install]` as carrying exactly
`version / harnesses / asset_root`, and a repo-wide search for `clients_dir` returns
**only the hook's two read sites** — the key is never produced. Consequence: unless a user
manually exports `MODELB_STATUS_CMD`, the ambient board-status feature CR-MDB-015 shipped
can never resolve a feed on any install.

**The source that closes both.** Crucible's CR-CRU-009 shipped a machine-readable
discovery manifest, explicitly built as "the Model-B pre-flight contract"
(`crucible:crucible_axi/manifest.py:1-8`): `MANIFEST_FILENAME = "crucible-clients.json"`,
schema `{version, clients, status}` with `clients[stack]` for
`("bun", "python", "rust", "mvn", "arduino")`, written by the `manifest` install stage into
`--target-dir` (default `~/.crucible`, also published at `crucible:docs/RUNBOOK.md:242`).
It is released — Crucible carries tags `0.1.0`, `0.1.1`, `0.1.2`.

**The location question is ANSWERED — and it comes with an upstream defect we must survive
(Sandesh #1360).** Crucible confirms the contract is `<target-dir>/clients/<stack>-crucible.py`,
default `~/.crucible/clients/`, and that we should anchor on the manifest's `clients`
values. They also confirm the defect this repo spotted: **nothing materialises that
directory yet** — `STAGE_ORDER = (server, manifest, unit)` copies no fleet, while the files
physically ride in the wheel at `crucible_axi/clients/` for their own CLI's use. Their
ruling, verbatim in substance: the manifest is right about the contract and wrong about
reality until the stage lands; do NOT repoint at site-packages, because that path is their
internal resolution detail, moves with the interpreter/venv, and is not a surface they will
keep stable. They will file the materialisation fix as a CR at their next SCRUM, and it
will not reshape the manifest — key names, file name and value meanings all stay put, so
our consumption code will not need reworking.

Model B's resolution is therefore the manifest and nothing else: read
`crucible-clients.json`, take `clients[stack]`, and record the directory. When the manifest
is absent, unparsable, or names a directory that does not exist yet, the answer is
**unresolved** — recorded as a WARN naming the upstream gap, never a substitute path.
Building a compensating fallback would make Model B the maintainer of another project's
client fleet, which is out of scope by standing directive: Crucible owns the clients, their
installation and their location; Model B consumes the published contract and updates its
skills when that contract changes. Never resolve to `~/.claude/scripts` either — that mirror
was retired by CR-MDB-016 and running it orphans runs.

Their `crucible-axi install [--target-dir <dir>]` (default `~/.crucible`) provisions and
exits; the server is version-pinned to the installer (`CRUCIBLE_SERVER_VERSION` override,
else `crucible_axi.__version__`) and run with `crucible-axi serve`.

## Scope

### §S1 — Probe the binary Crucible actually installs
`modelb_axi/preflight.py`: detect `crucible-axi`. The absent-warning text names Crucible's
own installer entry point rather than a generic instruction, and keeps the standing rule
that modelb-axi never deploys Crucible assets. The `deps:` line keyword stays `crucible=`
(it names the dependency, not the binary) so no consumer of that machine-greppable line
breaks.

### §S2 — Capture the discovery manifest at pre-flight
When `crucible-axi` is detected, read `<target-dir>/crucible-clients.json` (default
`~/.crucible`) and resolve the clients directory from its `clients` values. When the
manifest is absent, unparsable, or resolves to a directory that does not exist — the state
every current install is in, per #1360 — record the clients dir as UNRESOLVED with a WARN
that names the upstream gap and points at `crucible-axi install`. Never a hard failure,
never a fabricated or substitute path, never a package-internal or site-packages location,
never a resolution to `~/.claude/scripts`, and never an attempt to install, upgrade, copy,
or run anything of Crucible's.

### §S3 — Persist it where the hook already looks
`modelb_axi/config.py`: `[install]` gains `clients_dir` (the resolved directory, omitted
when unresolved) and the manifest's own `version`, so a later mismatch is detectable. The
atomic temp-plus-`os.replace` write discipline is unchanged, and `install.toml` remains the
last thing written.

### §S4 — Prove the seam end to end
An integration test that drives the real installer entry point against a sandboxed
`--target-root` with a fixture manifest whose `clients` directory actually EXISTS on the
resolution path, then runs the actual `hooks-src/scripts/ambient-board-status` script
against the produced `install.toml` and asserts the hook resolves a feed instead of emitting
the "no status feed resolved" degrade. A second case, with no manifest present, asserts the
hook degrades cleanly and still exits 0 — the state every install is in until Crucible ships
materialisation.
This test is what makes the two halves one wired feature rather than two files that mention
the same key.

## Acceptance criteria

### §S1
- [ ] `modelb_axi/preflight.py` probes `crucible-axi`; the string `which("crucible")` (exact
      binary name `crucible`) no longer appears.
- [ ] With `crucible-axi` on PATH the stdout line reads `crucible=detected`; with it absent,
      `crucible=absent` plus the warning on stderr.
- [ ] The absent warning names Crucible's own installer entry point and still states that
      modelb-axi never deploys Crucible assets.

### §S2 / §S3
- [ ] A manifest whose schema is `{version, clients, status}` yields a resolved clients
      directory; the resolution covers all five stacks Crucible enumerates
      (`bun, python, rust, mvn, arduino`).
- [ ] The manifest is read from `<target-dir>/crucible-clients.json` with `~/.crucible` as
      the default target dir.
- [ ] When the manifest is absent, unparsable, or names a non-existent directory, the
      resolution result is `unresolved` and no substitute path is produced — asserted for
      all three cases independently.
- [ ] No package-internal or site-packages path appears anywhere in `modelb_axi/`, and no
      code path copies, writes, or executes a Crucible client.
- [ ] No resolution path can ever yield a `~/.claude/scripts` location — asserted.
- [ ] `install.toml` `[install]` carries `clients_dir` and the captured manifest `version`
      when resolution succeeded, and OMITS `clients_dir` entirely when it did not — no empty
      string, no placeholder path.
- [ ] Each of the three unresolved cases — absent manifest, unparsable manifest, manifest
      naming a non-existent directory — produces a recorded WARN and exit 0 from pre-flight,
      and none writes a `clients_dir`.
- [ ] `install.toml` is still written atomically and last; a failed pre-flight leaves no
      `install.toml`.

### §S4
- [ ] An integration test drives the installer entry point (not `write_install_toml`
      directly) and then executes `hooks-src/scripts/ambient-board-status` as a subprocess
      against the resulting `install.toml`, asserting stdout does NOT contain
      `no status feed resolved` and that the hook exits 0.
- [ ] A grep for non-test callers of the capture function returns at least one — the
      pre-flight path itself.

## Estimated size

3 modules touched (`preflight.py`, `config.py`, the pre-flight caller in `cli.py`), 1
integration test module extended or added. No change to `hooks-src/` in this CR.

## Risk

- **Upstream reality lags the upstream contract, and that stays visible.** Crucible
  confirmed (#1360) that `<target-dir>/clients/` is the contract but that no install stage
  materialises it yet, and that the fix is theirs. Consequence to accept deliberately: on
  every current install `clients_dir` stays unresolved and the ambient board keeps emitting
  its "no status feed resolved" degrade until Crucible ships materialisation. That is the
  honest state of a dependency Model B does not own; papering over it with a substitute path
  would hide an upstream gap and make Model B its maintainer. Re-check at gap-analysis
  whether their fix has shipped.
- Re-running Crucible's installer is an UPGRADE path on their side; Model B must never
  invoke it. Detection and manifest reading only.
- The `[install]` table gains keys. `config.py` has no schema versioning, so a stale
  `install.toml` from a prior release simply lacks them — the hook already treats a missing
  key as unresolved, so old configs degrade exactly as they do today.

## Non-goals

- No change to the hook script itself (CR-MDB-019).
- No installing, upgrading, starting, or stopping of Crucible.
- No vendoring or copying of Crucible's clients — the manifest is read, never mirrored.
- No substitute for Crucible's un-materialised install stage: no packaged-copy fallback, no
  package-internal path, no Model B-provided client. Their fleet, their installer, their
  location; Model B reads the manifest and reports unresolved when it cannot.
- No client-path changes in the skills or the generator (CR-MDB-020).
