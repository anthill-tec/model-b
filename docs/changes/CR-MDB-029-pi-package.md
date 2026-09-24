# CR-MDB-029 — The Model B Pi package: the Sandesh watcher supervisor, published as `@anthill-tec/modelb-pi`

**Status:** PENDING (filed 2026-09-21; rewritten at its gap-analysis 2026-09-24, user rulings —
earlier text is git history and is not to be consulted for contracts)
**Type:** feature
**Priority:** P1 — in release 1.0.0, wave 2 (the wake watcher has no supervisor on Pi without it —
DN §D15.3)
**Depends on:** — (CR-MDB-030 and CR-MDB-025, on which earlier versions depended, have shipped).
CR-MDB-026's instruction edits cite this extension; the edge runs 026 → 029.
**Labels:** pi, packaging, extensions, sandesh, distribution, feature
**Phase:** Wave 5 (repo queue) · release 1.0.0 wave 2 (Crucible board)
**Design reference:** DN §D15.2 (Pi packages: `package.json` `pi` manifest, `npm:` install, core
packages as peer dependencies) · DN §D15.3 (user ruling: the supervised watcher is a Model-B-built
Pi extension) · DN §D18 (skills name capabilities, not harness tools) · Pi `docs/packages.md`,
`docs/extensions.md` (`pi.sendUserMessage()`) · `@gotgenes/pi-subagents/package.json` (a measured,
working Pi package manifest) · Sandesh 0.3.5 `sandesh notify --help` and `sandesh/notify.py`
(the exit contract) · CR-MDB-036 (`modelb_axi/requirements.py`, the `pi install` offer) ·
CR-MDB-030 §S8 (loading a `.ts` extension in a test through the `jiti` package)

**Target set:** Pi only (DN §D13/§D14).

## Context — measured 2026-09-24

- **The watcher's exit contract (Sandesh 0.3.5).** `sandesh notify --to <addr> --project <p>`
  prints `[notify] watching <addr> in <project> (pid …)` once it holds the address, then polls. It
  exits:

  | Code | Meaning | Response |
  |---|---|---|
  | `0` | unread `to` mail is waiting | wake the session; do not relaunch until the mail is fetched, since a relaunch with the mail unread returns `0` again at once |
  | `1` | usage or configuration error | stop; surface the error |
  | `2` | `--timeout` expired with no mail (or the DB stayed locked until the deadline) | relaunch silently |
  | `3` | the project was tombstoned | stop; surface; never relaunch |
  | `4` | evicted: another notifier took the address over | stop; surface; never relaunch |
  | `5` | a notifier was already live for the address (dedup) | stop; surface; never relaunch |
  | `128+n` | killed by signal `n` | stop; surface |

  CR-MDB-026's three-exit reading predates codes `1`, `3`, `4` and `5`.
- **Pi today:** the watcher runs as a background process whose exit wakes the session
  (`@mjakl/pi-processes`); nothing restarts it on timeout or tells the exits apart. A Pi extension
  can wake the session with `pi.sendUserMessage()`.
- **Skills** are deployed by the installer to `~/.agents/skills/` for every harness, scoped by
  stack (CR-MDB-036 §S7); the package carries none (user ruling).
- **Publication:** the source repository is private, so a `git:` install works only for people
  with access. The package is published to npm as `@anthill-tec/modelb-pi` (user ruling; the
  name is free). Publishing under that scope needs the npm organisation `anthill-tec`, and the
  user's ruling moves Model B and its sibling projects to the `anthill-tec` organisation — that
  move is a stack-level change outside this CR.

## Scope

### §S1 — The package
`pi-package/` holds `package.json`:
- `"name": "@anthill-tec/modelb-pi"`;
- `"version"`: the npm-semver form of `modelb_axi.__version__`, the single version source
  (CR-MDB-038 §S1) — `X.Y.Z` unchanged, `X.Y.Z.devN` → `X.Y.Z-dev.N`, `X.Y.ZaN`/`bN`/`rcN` →
  `X.Y.Z-alpha.N`/`-beta.N`/`-rc.N` (amended at C1: a PEP 440 version such as `0.1.0.dev0` is not
  valid npm semver);
- `"keywords": ["pi-package"]`, `"license": "MIT"`;
- `"pi": {"extensions": ["extensions/sandesh-watcher.ts"]}`;
- `peerDependencies` on `@earendil-works/pi-coding-agent`, and no `dependencies`.

It holds `extensions/sandesh-watcher.ts` and `README.md`, and no `skills/`. `README.md` is the
marked regions of `docs/install-guide.md` (CR-MDB-037 §S1) rendered by `generator/build.py`, so
`build.py --check` fails when it drifts from the guide; it carries no install text of its own.

### §S2 — The watcher supervisor extension
`extensions/sandesh-watcher.ts` registers a tool, `sandesh_watcher`, with actions `start`
(address, project), `status` and `stop`, and a `/watcher status|stop` command. `start` spawns
`sandesh notify --to <address> --project <project>` as a child with `PYTHONUNBUFFERED=1` in its
environment — Sandesh prints its banner with an unflushed `print()`, so a piped child would hold it
until exit (amended at C5, VERIFY finding 1) — and reports it ready only when the
`watching <address>` banner appears. **The watcher runs at all times** (user ruling, amended at C5):
on exit it follows the table above, and only `stop` or a terminal exit ends it.

- `0`: wakes the session with one message naming the address, the unread message ids Sandesh
  printed, and the fetch to run, with the address shell-quoted
  (`sandesh fetch --project <p> --to '<address>'`); then relaunches at once. A relaunch that exits
  `0` again with **the same** message ids does not wake the session again and retries every 30
  seconds until the mail is fetched and the banner reappears; **new** ids wake the session again;
- `2`: relaunches silently; three `2` exits within one minute surface instead of looping;
- `1`, `3`, `4`, `5`, `128+n`: stop, and surface the code and its meaning, never relaunching.

At most one watcher runs per address in a session; `start` while one runs reports it and spawns
nothing. `stop` terminates the child. Skills keep naming the capability ("start your notifier"),
never the tool (DN §D18).

### §S3 — Declared, offered and recorded by the installer
- `modelb_axi/requirements.py` gains a row: id `watcher`, tier 1, provider `@anthill-tec/modelb-pi`,
  policy `recommended`, scope `always`, the orchestration skills as dependents, tools
  `["sandesh_watcher"]`, remediation `pi install npm:@anthill-tec/modelb-pi`. The harness probe
  (CR-MDB-036 §S2) reports it like the other tier-1 capabilities.
- With `pi` among the harnesses and the package absent, the installer offers
  `pi install npm:@anthill-tec/modelb-pi`; confirmation or `--yes` runs it (user ruling: Model B's
  own package, like Sandesh), its output goes to the terminal, and the capability is re-probed
  before `installed` is recorded. The installer never edits `settings.json` itself.

### §S4 — The release publishes the package
`skills-src/git-workflow/SKILL.md` §Releases gains a project-neutral step for a Pi package: after
the version is set, publish to npm with credentials the user supplies at publish time (a scoped
package with `--access public`, amended at C5), then install the published version into an isolated
Pi agent directory (`PI_CODING_AGENT_DIR`) and confirm the extension loads. The post-release
maintenance gains the live check: after the published package is installed into the maintainer's
real Pi configuration, start the watcher and confirm a Sandesh message wakes the session.

## Acceptance criteria

### §S1
- [ ] `pi-package/package.json` carries the §S1 fields exactly; its `version` is the npm-semver form
      of `modelb_axi.__version__` and matches the semver 2.0.0 grammar; `pi.extensions` lists every file under `pi-package/extensions/`;
      there is no `dependencies` key and no `skills/` directory.
- [ ] `pi-package/README.md` equals the install guide's marked regions as `generator/build.py`
      renders them; `build.py --check` fails on a one-byte drift in either.
- [ ] No `~/.claude` or `~/.omp` path appears anywhere under `pi-package/`.

### §S2
- [ ] Loaded through the `jiti` package with a fake `sandesh` on PATH, the extension registers the
      `sandesh_watcher` tool and the `/watcher` command.
- [ ] One test per exit code, each with a fake `sandesh notify` that prints the banner then exits:
      `0` → exactly one wake message naming the ids and the shell-quoted fetch, and a relaunch;
      `0` again with the same ids → no second wake, relaunches keep going; `0` with new ids → a
      second wake; `2` → a relaunch, no message; three `2`s within a minute → surfaced, no fourth
      launch; `2`s spread over more than a minute → keep relaunching; `1`, `3`, `4`, `5` and a signal
      → surfaced with the code's meaning, no relaunch.
- [ ] The test fake buffers its stdout the way a Python `print()` into a pipe does (unless
      `PYTHONUNBUFFERED` is set), so a `start` that omits the variable hangs and the test fails.
- [ ] `start` reports ready only after the banner; a `start` while one runs spawns nothing; `stop`
      terminates the child.

### §S3
- [ ] `REQUIREMENTS` carries the `watcher` row with the §S3 fields; the harness probe reports
      `watcher=` on the `harness:` line.
- [ ] With the package absent: `--yes` runs `pi install npm:@anthill-tec/modelb-pi` exactly once
      (shim), a `detected` package runs nothing (a package listed in `settings.json` but missing from
      disk probes `absent` and is offered like any absent one — amended at C3), the verdict is re-probed, and `settings.json`
      is never written by Model B — all against a sandboxed `PI_CODING_AGENT_DIR`.

### §S4
- [ ] `skills-src/git-workflow/SKILL.md` §Releases names the Pi package step: npm publish with
      user-supplied credentials and `--access public`, then an isolated install confirming the
      extension loads; and the post-release live check (watcher started in the real configuration,
      a Sandesh message wakes the session).

### Close-out
- [ ] **Measured, not assumed, without touching the real configuration:** Pi run headless with
      `PI_CODING_AGENT_DIR` pointed at a temp directory, the local package installed there, loads the
      extension and registers `sandesh_watcher` and `/watcher` — recorded with the transcript
      reference. The live wake is a post-release step (§S4), never a CR step (user ruling, amended
      at C5: installing into the real configuration mid-CR would change the live environment).

## Risk

- Sandesh's exit codes are its contract, measured at 0.3.5; a later Sandesh changing them surfaces
  as a failing exit test when its behaviour is re-measured.
- The npm scope requires the `anthill-tec` npm organisation, which the user creates before the
  first publish.

## Non-goals

- No skills, agent definitions, tool scripts or hooks in the package.
- No change to the bootstrap/shutdown skill text (CR-MDB-026 owns it, citing this extension).
- The move of the repositories to the `anthill-tec` organisation is a stack-level change (Roundhouse
  root), not this CR.
