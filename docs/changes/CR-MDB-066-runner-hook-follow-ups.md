# CR-MDB-066 — Runner-hook follow-ups from CR-MDB-062's verify

**Status:** PENDING — **SEED, not the finished spec.** Gap analysis, the design record, the spec and
its pre-review happen in order when this CR starts.
**Type:** fix (hook scripts, guard)
**Priority:** P3 — release 1.0.0, wave 2; last in the wave, after its P1 CRs.
**Depends on:** CR-MDB-062 (merged `282eaa7`; board-authoritative: read `queue`)
**Labels:** hooks, guard, enforcement
**Design reference:** DN-multi-harness-deploy-model §D21 (third amendment); CR-MDB-062 §S1–§S6.

## Context

CR-MDB-062's VERIFY (C5) found no defect in its scope. It recorded these points outside the spec's set.

## Scope (seed)

1. **Runner forms that the guard and all four hooks miss (they agree on each).** Decide for the guard
   and the hooks together, since they stay in parity:
   - other ways to run npm's test script: `npm t`, `npm run-script test`, `pnpm test`, `yarn test`;
   - shell grammar positions: `{ pytest; }`, `if pytest;`, `do pytest`, `! pytest`, `command pytest`,
     `time -p pytest`;
   - a command wrapped in backquotes;
   - a line after an arithmetic `$((1<<2))`, which is read as a heredoc.

   CR-MDB-056's verify listed further forms. They are now non-goals in CR-MDB-062: `make test`,
   `mvn install`, `vitest` and `jest`, `python3 -m tests.test_x`, `bash -c`, `sudo`, `xargs`, `nohup`
   and `exec`.
2. **The other `block-*` hooks:**
   - `block-cr-completed-without-spec-update` still cites `ORCHESTRATOR-RULES.md §5`, a stale reference;
   - it, `block-write-outside-worktree` and `post-regression-disk-reminder` still catch only
     `JSONDecodeError`/`OSError` on the payload. CR-MDB-062 C5 F2 widened the runner hooks' catch to
     `RecursionError` and the digit limit, because a crash in a `closed` hook blocks the call.
3. **The marker walk's cost** (measured at C5): a runner command in a tree of 15,650 directories costs
   0.2–0.6 s, and python pays most for its per-directory `requirements*.txt` glob. One `scandir` per
   directory would serve it.
4. **The bun reason's wording:** a tier verb runs the declared `test:<tier>` script, and the client
   refuses when none is declared.
5. **A shared installer's offer names one stack** (from CR-MDB-063's verify, F2). The
   `uv python install --default 3.14` offer covers every selected stack's `python3`, but its prompt
   names only the first ("…to install python3 for stack rust?"). After a successful install, the later
   stacks' warnings still read `python3=absent` while `install.toml` records `installed`. Shared
   installers behaved this way before CR-MDB-063; word the prompt and the later warnings for every
   stack the installer covers.
