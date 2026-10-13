# CR-MDB-062 — Blocking hooks for python and bun test runners

**Status:** PENDING — **SEED, not the finished spec.** Gap analysis, the design record, the spec and
its pre-review happen in order when this CR starts.
**Type:** feature (hook scripts, scaffold, installer)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** CR-MDB-056 (board-authoritative: read `queue`)
**Labels:** hooks, scaffold, installer, enforcement
**Design reference:** DN-multi-harness-deploy-model §D21 and its 2026-10-13 amendments; `hooks-src/schema.md` v1;
the CR-MDB-056 spec pre-review (findings F4–F8, F12).

## Context

Only cargo and mvn have blocking hooks (`block-direct-cargo-test`, `block-direct-mvn-test`); `init`
emits none for python or bun. CR-MDB-056 states the rule and guards the text; this CR stops a raw run
at tool-call time.

## Scope (seed)

1. **`block-direct-python-test` and `block-direct-bun-test`** in `hooks-src/scripts/`, built like the
   cargo and mvn hooks (python3, stdlib, the neutral `bash` payload, exit 0 / exit 2 + block JSON,
   fail-open on an unparseable payload), with `ALLOW_RAW_PYTHON=1` / `ALLOW_RAW_BUN=1` escape hatches.
2. **One runner table** shared in content with CR-MDB-056's guard (a parity test keeps them equal), and
   a command-position detector that steps past `VAR=value`, `env`, `timeout`, `nice`, `time`. Python:
   an interpreter bare, versioned or a path (`.venv/bin/python`), options before `-m`, `-m
   unittest|pytest|xmlrunner|coverage run`, `pytest`/`py.test`, `uv run pytest`, `coverage run -m …`.
   Bun: `bun test`, `bun run test…`, `npm test`/`npm run test…`, `bunx`/`bun x`/`npx playwright test`,
   `playwright test`. A runner inside an argument (`git commit -m "… pytest …"`) is never blocked.
3. **Where a hook applies:** the project markers miss common layouts (bun's package in
   `integrations/pi/`; a monorepo sub-project) — measure, and decide between no marker check and the git
   root plus its sub-projects.
4. **Block reasons** name the client manifest `~/.crucible/crucible-clients.json` and the client
   `~/.crucible/clients/<stack>-crucible.py`, its `test` invocation, the escape hatch, and the known
   client gaps; no stale references.
5. **`init`** emits each hook for its stack (`pre-tool-use`, `bash`, `closed`) and **refuses or skips
   with a warning any emitted hook whose script is absent from the deployed store**, checked before the
   first write — a `closed` hook with a missing script blocks every shell call.
6. **The installer** deploys both scripts.
7. **The gates that move:** `NOT_REGISTRY_KEYS` (`ALLOW_RAW_PYTHON`, `ALLOW_RAW_BUN`),
   `test_installer_assets` `HOOK_SCRIPT_NAMES`, `test_hooks` `IMPORTED_SCRIPT_NAMES`/`ALL_SIX_SCRIPT_NAMES`,
   `test_client_path_anchoring`'s reason/docstring checks, `test_pi_hook_runtime`'s cross-tool guard
   test, `test_scaffold` `HookSelectionTableTest` and the table above `_hook_instances`,
   `hooks-src/schema.md`'s security-class roster, `AGENTS.md`'s executable-script count.

## To measure at gap analysis

- The block-reason convention the anchoring tests enforce; Model B's own wiring after merge (the user
  redeploys, then the wiring is recompiled — DN §D21 amendment).
