# CR-MDB-018 — Crucible discovery: the ambient hook reads Crucible's client manifest, and the client lifecycle rules are gated

**Status:** PENDING (filed 2026-08; rewritten at its gap-analysis 2026-09-24 — earlier text is git
history and is not to be consulted for contracts)
**Type:** bugfix
**Priority:** P1 — in release 1.0.0, wave 2. The ambient board-status hook CR-MDB-015 shipped cannot
resolve a feed on any machine unless the user exports an override.
**Depends on:** CR-MDB-015 (the hook), CR-MDB-036 (the manifest as Model B's single source for
Crucible's clients)
**Labels:** hooks, crucible, discovery, skills, bugfix
**Design reference:** Crucible's released-client manifest `~/.crucible/crucible-clients.json`
(CR-CRU-009 §S2, CR-CRU-143; Sandesh #1358/#1360/#1373) · CR-MDB-036 §S1 (pre-flight judges Crucible
by that manifest, never a binary or its server) · `modelb_axi/requirements.py` `STACK_CLIENT_KEYS` ·
user ruling 2026-09-24 (the hook reads the manifest directly; no copy in `install.toml`)

## Context — measured on `develop` at `b8e17b6`

- **The hook cannot find the clients.** `hooks-src/scripts/ambient-board-status` resolves its feed
  from `[install].clients_dir` in `$MODELB_HOME/install.toml`. Nothing writes that key, and the hook
  reads only the `MODELB_HOME` environment variable — the default location is resolved by the CLI,
  never exported — so even a written key would not be found in a normal session. Unless
  `MODELB_STATUS_CMD` is set, the hook always prints "no status feed resolved".
- **The authoritative source already exists.** Crucible's installer writes
  `~/.crucible/crucible-clients.json`. Measured: `version: "0.2.2"`, six keys (`clients`, `version`,
  `status`, `config`, `server_config`, `shipped_config`), and `clients` maps `arduino`, `bun`, `mvn`,
  `python` and `rust` to absolute paths that exist. Pre-flight reads this file since CR-MDB-036
  (`capabilities.load_crucible_clients`), and `STACK_CLIENT_KEYS` maps each stack to its key
  (quarkus/java → `mvn`).
- **A copy would go stale.** Recording the clients directory in `install.toml` duplicates Crucible's
  own record; it would be wrong after any Crucible reinstall until `modelb-axi` re-ran. The user ruled
  (2026-09-24) that the hook reads the manifest itself.
- **The feed is fast enough.** `python-crucible.py status` returns in 0.08 s against the production
  board; the hook's bound is 2 s.
- **The original §S1 is done.** CR-MDB-036 replaced the `which("crucible")` probe with the manifest
  verdict; probing the `crucible-axi` binary would reverse that decision, so it is not in scope.
- **Two lifecycle rules have no gate.** `skills-src/crucible/SKILL.md` (lines ~110–118) states them —
  ingest with `--cycle <id>` before `cycle-done`, and a stale cycle binding survives re-registration —
  but no test protects the text from a later rewrite.

## Scope

### §S1 — The hook resolves its feed from Crucible's manifest
`ambient-board-status` reads `crucible-clients.json` under the user's home `.crucible` directory,
finds the project's stack from the nearest marker walking up from the working directory, and runs
`clients[<key>]` with `status`. It no longer reads `install.toml` or `MODELB_HOME`.
`MODELB_STATUS_CMD` still wins when set. The hook stays self-contained and stdlib-only (it is
deployed as a standalone script and cannot import `modelb_axi`), so it carries its own
marker → manifest-key table.

### §S2 — Every unresolved case degrades, and nothing substitutes
The manifest absent, unparsable, without a `clients` object, without the stack's key, or naming a
file that does not exist; or no stack marker found: each prints a degrade note and exits 0. A
manifest-related note names the manifest path and Crucible's own installer. No other location is
ever tried — not `~/.claude/scripts`, not a site-packages or package-internal path, not a Crucible
source checkout. Unknown extra manifest keys are ignored.

### §S3 — The hook and pre-flight agree on the keys
For every stack the hook recognises, its manifest key equals `STACK_CLIENT_KEYS` for that stack.
A test enforces the parity, so the two readers of the manifest cannot drift apart.

### §S4 — The seam, end to end
A test runs the real hook script as a subprocess with a sandboxed `HOME` holding a fixture manifest
whose client is an executable fixture printing a valid `status` envelope, from a working directory
with a stack marker, with `MODELB_STATUS_CMD` and `MODELB_HOME` unset: the hook prints board
content, not the degrade note, and exits 0. Companion cases cover each §S2 condition.

### §S5 — The client lifecycle rules are gated
A gate (in `tests/test_skill_bundle_guards.py` or its own module) asserts that
`skills-src/crucible/SKILL.md` states both rules in substance: a run is ingested with `--cycle <id>`
before `cycle-done` (after it, the run is refused and nothing backfills it; an unbound agent's run
stores project-scoped and untraceable); and a stale cycle binding survives re-registration, cleared
by `unregister` then `register`, with an unbound ORCHESTRATOR registration avoiding it.

## Acceptance criteria

### §S1
- [ ] With a sandboxed `HOME` whose `.crucible/crucible-clients.json` names an existing client for
      the working directory's stack, the hook invokes that client's `status` and renders its result.
- [ ] The hook source no longer reads `install.toml`, `clients_dir` or `MODELB_HOME`.
- [ ] `MODELB_STATUS_CMD`, when set, still takes precedence (existing tests keep passing).

### §S2
- [ ] Each of the six unresolved conditions (manifest absent; unparsable; no `clients` object; no key
      for the stack; key names a missing file; no stack marker) is asserted independently: exit 0,
      a degrade note, and no client invoked.
- [ ] A manifest carrying extra keys beyond the six measured ones still resolves.
- [ ] No path to `~/.claude/scripts`, a site-packages directory or a Crucible checkout appears in the
      hook, asserted.

### §S3
- [ ] A parity test fails if the hook's marker → key table disagrees with `STACK_CLIENT_KEYS` for any
      stack it recognises, with a detector fixture proving it bites.

### §S4
- [ ] The end-to-end test drives the actual `hooks-src/scripts/ambient-board-status` as a subprocess
      with `MODELB_STATUS_CMD` and `MODELB_HOME` unset, and asserts stdout does not contain
      `no status feed resolved` and the exit is 0.

### §S5
- [ ] The gate asserts both lifecycle rules as stated above, and a detector fixture with either rule
      removed makes it fail.

### Close-out (orchestrator, before merge)
- [ ] Run the merged hook from the model-b tree against the real manifest (production board only):
      it renders the board rather than degrading. Recorded in the merge note.

## Risk

- The hook's marker table and pre-flight's `STACK_CLIENT_KEYS` are two copies of one fact; §S3's
  parity test is what keeps them together.
- The manifest belongs to Crucible. Its key names and file name are stable by Crucible's ruling;
  reading additional keys later is additive.

## Non-goals

- No change to `install.toml`, `config.py` or pre-flight: no `clients_dir` key is added.
- No installing, upgrading, starting or stopping Crucible, and no copying of its clients.
- The status-contract re-pin (`lastRunCr` → `lastClosedCr`, the 2.0.0 document) and the arduino
  marker stay with CR-MDB-019.
- No client-path changes in the skills or the generator (CR-MDB-020).
