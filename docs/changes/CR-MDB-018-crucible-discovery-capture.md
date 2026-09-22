# CR-MDB-018 — Crucible discovery capture: the installer probes the wrong binary and never records the clients dir the hook reads

**Status:** PENDING
**Type:** bugfix
**Priority:** P1 (blocks release 1.0.0 — a shipped hook reads a config key the installer never writes, so the feature is dead on every install)
**Depends on:** CR-MDB-014 (pre-flight + install.toml), CR-MDB-015 (the hook that consumes the key)
**Labels:** installer, preflight, crucible, discovery, patch
**Phase:** Wave 5
**Design reference:** the manifest contract as PUBLISHED (measured at `~/.crucible/crucible-clients.json`; Sandesh #1358/#1360) (the discovery manifest — CR-CRU-009 §S2) · the installed `crucible-axi install --target-dir` surface (default `~/.crucible`, measured 2026-09-18; subcommands `install|serve|uninstall`) · the published manifest location (measured: `~/.crucible/crucible-clients.json`) · the installed CLI name and upgrade path (`crucible-axi`, on PATH at `~/.local/bin/crucible-axi`) · PRD §D10 (installer = dependency orchestrator) · Sandesh #1357, #1358

## Context

Two defects on the same seam — Model B's installer is supposed to CAPTURE where Crucible's
clients live, and the session-start hook is supposed to CONSUME that. Neither half works.

**Defect 1 — the pre-flight probes a binary name that does not exist.**
`modelb_axi/preflight.py:77` runs `shutil.which("crucible")`. Crucible's installed CLI is
**`crucible-axi`** (the installer's own published behaviour — "it installs the `crucible-axi` primary
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
discovery manifest, explicitly built as "the Model-B pre-flight contract":
`MANIFEST_FILENAME = "crucible-clients.json"`, written by the `manifest` install stage into
`--target-dir` (default `~/.crucible`).

**RE-MEASURED 2026-09-18 against the INSTALLED PRODUCTION install — the upstream defect this
CR was written around is FIXED, and the manifest is WIDER than the schema recorded below.**
`~/.crucible/crucible-clients.json` now exists (mtime 2026-09-18) declaring
`"version": "0.2.2"`, and `~/.crucible/clients/` is populated with all five clients. So the
premise that "nothing materialises that directory yet" (`STAGE_ORDER = (server, manifest,
unit)`, Sandesh #1360) no longer holds, and **"unresolved" is no longer the expected outcome on
this machine — a successful resolution is.** Both must still be handled, but the ACs below can
no longer treat unresolved as the only reachable path.

The measured schema has **SIX** keys, not the `{version, clients, status}` three this CR was
written against — the extra three are CR-CRU-143's conditional manifest keys (Sandesh #1373):

| key | measured value | use to Model B |
|---|---|---|
| `clients` | per-stack ABSOLUTE paths (`bun`/`python`/`rust`/`mvn`/`arduino`) | what §S2 resolves `clients_dir` from |
| `version` | `"0.2.2"` | the install's own version, for the mismatch check §S3 already wants |
| `status` | `~/.crucible/clients/STATUS-CONTRACT.md` | the re-pin target CR-MDB-019 hunts for — it is DISCOVERABLE, not a guessed path |
| `config` | `~/.crucible/crucible.toml` | the operator-editable client config |
| `server_config` | `~/.local/share/crucible/crucible.toml` | the server's own limits file |
| `shipped_config` | `~/.crucible/clients/crucible.toml` | package data; the `[client] url` fallback |

The three config keys matter beyond completeness: they answer, declaratively, the board-URL
resolution question that misrouted this orchestrator's own session on 2026-09-18 (a client
invoked from a personal checkout bound to a development board because that checkout's own
`crucible.toml` won the `project → install → shipped` chain). A consumer that reads
`shipped_config`/`config` from the manifest never has to guess which config a client obeyed.

Crucible's standing ruling is unchanged and still binding: anchor on the manifest's values, do
NOT repoint at site-packages (their internal resolution detail, moves with the interpreter),
and the manifest's key names, file name and value meanings stay put — so consumption code
written to the three original keys keeps working, and reading the three new ones is additive.

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

### §S5 — The lifecycle rules the discovery seam depends on (added 2026-09-21, user directive)

Two client-lifecycle facts were measured in flight during CR-MDB-028 and CR-MDB-017, each
costing a 409 before it was understood. They are **already written into
`skills-src/crucible/SKILL.md`** ahead of this CR; this section exists so the requirement is
TRACKED by an AC rather than surviving only as prose one edit away from deletion:

- **Ingest before `cycle-done`, with `--cycle <id>`.** A run ingested after its cycle closed is
  refused (`bound cycle <id> is done — ingest refused, run NOT stored`) and nothing backfills
  it; a run from an agent bound to no cycle stores project-scoped with a `no-cycle` warning and
  is permanently untraceable to its cycle.
- **A stale cycle binding survives re-registration.** `register` on an id already bound to a
  finished cycle does not rebind it — every workflow verb then 409s. `unregister` then
  `register`. A long-running ORCHESTRATOR should register unbound.

This belongs with §S1–§S4 because it is the same surface: what the installed client's identity
and run verbs actually require of a caller. The discovery work makes the client FINDABLE; these
two rules make the found client USABLE without losing a run's attribution.

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
- [ ] A manifest carrying the measured SIX keys (`clients`, `version`, `status`, `config`,
      `server_config`, `shipped_config`) yields a resolved clients directory; the resolution
      covers all five stacks Crucible enumerates (`bun, python, rust, mvn, arduino`). Unknown
      or additional keys are tolerated, never required — the manifest is Crucible's to grow.
- [ ] **The REAL install resolves.** Asserted against the actual
      `~/.crucible/crucible-clients.json` (present since 2026-09-18, `version: "0.2.2"`, five
      client paths on disk), not only against a fixture: `clients_dir` resolves to
      `~/.crucible/clients` and `[install].clients_dir` is written. This is the criterion the
      original spec could not state, because when it was authored no install materialised that
      directory and unresolved was the only reachable outcome.
- [ ] `status` is taken FROM the manifest rather than guessed, giving CR-MDB-019 a discovered
      path to the status contract instead of a hardcoded one.
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

### §S5
- [ ] `skills-src/crucible/SKILL.md` states BOTH lifecycle rules in substance: that a run is
      ingested with `--cycle <id>` BEFORE `cycle-done` (a run ingested after the cycle closed
      is refused and nothing backfills it; an unbound agent's run stores project-scoped and
      untraceable), and that a stale cycle binding survives re-registration so clearing it
      takes `unregister` then `register`, with the ORCHESTRATOR/`report` unbound registration
      named as the way to avoid it entirely.
- [ ] A gate asserts both rules are present — added to `tests/test_skill_bundle_guards.py`'s
      bundle families or as its own method — so the prose cannot be silently dropped by a
      later bundle rewrite. The text landed ahead of this CR (2026-09-21); this AC is what
      keeps it.

## Estimated size

3 modules touched (`preflight.py`, `config.py`, the pre-flight caller in `cli.py`), 1
integration test module extended or added, 1 published bundle already carrying §S5's text
plus its gate. No change to `hooks-src/` in this CR.

## Risk

- **Upstream reality has CAUGHT UP with the upstream contract — this risk is CLOSED, and the
  gap-analysis re-check it asked for is the thing that closed it.** The original entry said
  Crucible confirmed (#1360) that `<target-dir>/clients/` was the contract but that no install
  stage materialised it, so `clients_dir` would stay unresolved on every install and the
  ambient board would keep emitting its "no status feed resolved" degrade until they shipped
  the fix. Measured 2026-09-18: **they shipped it.** `~/.crucible/crucible-clients.json` exists
  at `version: "0.2.2"` and all five clients are on disk, so resolution SUCCEEDS here. The
  degrade path stays implemented and tested — a machine without the install still needs it —
  but it is no longer the expected outcome, and no AC may assert it as the only one. The
  deliberate refusal to build a compensating fallback was vindicated: waiting cost nothing and
  a substitute path would now be dead code contradicting a real manifest.
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
