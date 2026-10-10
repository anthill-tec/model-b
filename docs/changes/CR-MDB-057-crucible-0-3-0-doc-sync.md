# CR-MDB-057 — Crucible 0.3.0 doc-sync

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-10 into release 1.0.0, wave 2).
Gap analysis, the design record, the spec and its pre-review happen in order when this CR starts.
**Type:** refactor (skills, agent definitions, project docs, tests)
**Priority:** P1 — release 1.0.0, wave 2 (user ruling 2026-10-10: a separate CR, not folded into CR-MDB-056).
**Depends on:** none (board-authoritative: read `queue`, not this line)
**Labels:** skills, crucible, doc-sync, release
**Design reference:** Crucible #1432 (Mainline - Crucible, 2026-10-10: Crucible 0.3.0 release note,
release notes at `anthill-tec/crucible` tag `0.3.0` and its `CHANGELOG.md`); `skills-src/CRUCIBLE-HANDOVER.md`
§ Maintenance contract (every client-surface change obligates a Model B doc-sync; the pre-release ask).

## Context

Crucible 0.3.0 is released and installed (`crucible-axi` 0.3.0; clients re-laid 2026-10-10; the
production board migrated from schema v13 to v20). Under the handover's maintenance contract every
client-surface change since the last doc-sync is synced into Model B's skill text before Model B
1.0.0 is released; #1432 is that list and doubles as the pre-release ask. CR-MDB-056 cites 0.3.0's
`test --cycle` for its own rule; everything else from #1432 lands here.

## Scope (seed — the #1432 items, each checked against the installed 0.3.0 `--help`)

1. **The connection is configuration, not environment.** The server no longer reads
   `$CRUCIBLE_PORT`/`$CRUCIBLE_HOST`; the clients no longer read `$CRUCIBLE_URL` (arduino:
   `$CRUCIBLE_BASE`) — the board comes from the project's `crucible.toml` `[client]`. *Measured:*
   `tests/test_project_registry_schema.py`
   (`test_filled_env_key_resolves_through_the_installed_client`) points the installed client at a
   fake server through `CRUCIBLE_URL`, so on 0.3.0 it is no longer hermetic. Any skill, scaffold or
   `.envrc` text setting these variables moves the value into the file.
2. **`[gate]` in `crucible.toml`** declares the steps a project never runs (`pr,ci` for git-flow), so
   `gate-run` no longer needs `--skip` on every call. *Measured:* `AGENTS.md` (Workflow Rules,
   wave-boundary gate) and the workflow text name `--skip ci`.
3. **`--release <X.Y.Z>`** on test runs files release verification under the release.
4. **Gate runs** have their own board identity (`<caller>·gate·<run>`), interim snapshots carry the
   release, and the decision stays the caller's.
5. **Read verbs:** `queue --fields release,seq,points,dependsOn` (a `warning` column; `--full`), a new
   `history` verb in all five clients (`--fields`, `--release`), and `status` showing work in flight.
6. **Output handling:** a closed pipe no longer leaves a run open, but skills send client output to a
   file rather than through `| head`.
7. **Plans grow only by fix cycles;** a skipped cycle is a failure; `cycle-add --before <verify id>`
   keeps verify last.
8. **Run hygiene:** each run keeps its reports to itself; a run nothing will file is closed at once.
9. **Interim workaround for two Crucible-side defects** (until Crucible fixes them): after a
   `gate-respond` timeout ("no-mistakes recorded no decision" while a step still runs), check
   `axi status` and reattach with `gate-run --intent …`; `gate-respond` has no `--release`.

## To measure at gap analysis

- **Every consumer** of the changed surfaces: the `crucible`, `crucible-register` and
  `crucible-report-*` skills (Model B owns them — #1337, confirmed #1430), the sub-agent procedure,
  the agent templates and stack TOMLs, `AGENTS.md`, `init`'s scaffold (does it write `crucible.toml`
  or `.envrc` connection lines?), the hook scripts, and the tests that drive the installed client.
- **Step 0 baseline on 0.3.0:** the full suite with real and with empty `HOME`, against the 2077-test
  baseline measured on 0.2.x.
- **Boundary with CR-MDB-056:** 056 owns the test-run rule and its `--cycle` wording; 057 owns the
  rest. Shared files (the `crucible` skill, the templates) are sequenced, not edited twice in conflict.
