# Contract — gate-lock serialize-heavy-gates mutex

**Owner:** SHARED — Model B holds the WAITER half (`scripts/gate-lock.sh`, deployed to
`~/.agents/scripts/gate-lock.sh`); the CRUCIBLE project holds the GATE-RUNNER half
(`~/.crucible/clients/rust-crucible.py`, the installed client listed in
`~/.crucible/crucible-clients.json`).
**Status:** LIVE on both sides. Neither half is a copy of the other: they are two
programs that must derive the SAME path and agree on who mutates the file. This
document records the protocol so either side can check the other's behaviour without
reading it.

## Why it exists

Two heavy gates (full regression / pre-merge) running concurrently on one box
compile-and-resource starve each other until the environment KILLS them. The rule is
`model-b/references/orchestration-common.md`'s **serialize heavy gates across parallel
tracks**; this file is that rule's wire contract.

## Lock path derivation

A single lock file, shared across ALL worktrees of a repo, so the mutex spans every
track:

| Step | Value |
|---|---|
| Directory | the parent of git's COMMON dir — `git -C <dir> rev-parse --path-format=absolute --git-common-dir`, then `dirname`. This is the MAIN repo root, never inside `.git`. |
| Older-git fallback | resolve the possibly-relative `--git-common-dir` to absolute first, then `dirname`. |
| Filename | `nai-gate.lock` |
| No-git fallback | `/tmp/nai-gate.lock` — Model B only. |

- Model B: `scripts/gate-lock.sh::lock_path()`.
- Crucible: `~/.crucible/clients/rust-crucible.py::_gate_lock_path()`, whose docstring names
  `gate-lock.sh`'s `lock_path()` as the thing it matches. It has NO `/tmp` fallback —
  it returns `None` and the run proceeds UNLOCKED (degraded, deliberately non-blocking),
  so the `/tmp` branch is Model B's alone and is still part of this contract because a
  non-git checkout must not silently share a lock with an unrelated tree.

Derivation equality is a GATE, not a promise: `tests/test_tooling_detachment.py`
drives `gate-lock.sh` as a subprocess and evaluates Crucible's `_gate_lock_path` out of
process against one fixture git layout, and asserts the two strings are byte-identical
from both the main tree and a linked worktree.

## Lock file body

`key=value` lines, written by whichever side creates the file:
`owner=` · `cr=` · `pid=` · `epoch=` · `started=` (Crucible adds `runner=`). `pid` is the
REAL run pid, so liveness of the recorded holder is checkable by either side.

## Verbs (Model B's half)

| Verb | Meaning |
|---|---|
| `wait-free` | the live PRE-FLIGHT: poll until the lock is free (absent, or holder pid dead) AND resources have headroom, then return and let the gate-runner create the lock. Does NOT write the lock. |
| `status` | current holder, lock age, run-pid liveness, resource readings. Read-only. |
| `check` | resource-headroom check only (RAM / CPU-load-per-core / free disk). Read-only. |
| `acquire` | SELF-SERVICE fallback for a gate NOT run through Crucible: writes the lock itself. Not the live path when Crucible runs the gate. |
| `wait-acquire` | `acquire` retried every `--freq` s up to `--max` s. Run it in the BACKGROUND — a 600 s loop exceeds a 10-minute foreground cap. |
| `release` | remove YOUR OWN lock post-gate; REFUSES a lock owned by another track. |
| `force-release` | MAINLINE-only arbiter verb: remove a genuinely forgotten lock, with `--reason`. |

## Exit codes

| Code | Meaning |
|---|---|
| 0 | acquired / free — proceed and run the gate |
| 1 | HOLD: the lock is held by another track |
| 2 | HOLD: the lock is free but resources are loaded (box busy) |
| 5 | timed out waiting — ESCALATE to Mainline, never force-release yourself |

Local, non-protocol codes: `3` = usage error (a verb called without `--cr`/`--track`),
`4` = `release` refused because the lock belongs to another owner.

## Ownership division

- **Model B WAITS and observes.** `wait-free` only OBSERVES the lock and never creates
  it; it polls, reports the holder, and escalates on timeout. Model B is not the
  arbiter of the file's lifecycle.
- **Crucible OWNS the lock FILE.** `~/.crucible/clients/rust-crucible.py::_acquire_gate_lock`
  CREATES it atomically (`O_CREAT | O_EXCL`) stamped with its own pid at the start of a
  gated run, and REFUSES to start when a live holder is already present rather than
  running a second concurrent regression.
- **Crucible DELETES it** on finish, on `atexit`, and from a signal handler for the
  catchable kills (SIGTERM / SIGINT / SIGHUP), re-raising the signal so the exit status
  still reflects the kill.
- **Crucible RECLAIMS a STALE lock** on the next run — holder pid dead, pid recycled to
  a process that is not the gate runner, or lock age beyond `STALE_LOCK_MAX_AGE_S`
  (7200 s / 2 h, its portable backstop for an uncatchable SIGKILL or an oomd kill whose
  pid was later recycled). An oomd-killed run therefore never permanently wedges the
  gate.
- **Mainline is the RARE arbiter**, not a participant: it verifies the holder's real run
  pid and interrogates the holder before any `force-release`. Never conclude a run is
  dead from a proxy signal.
- Crucible names Model B's half in its own operator help — the `gate-locked` hint tells
  the caller to "wait for the in-flight gate to finish (`gate-lock.sh wait-free`), then
  re-run" — so the two halves reference each other by name in both directions.

## The filename cannot change on one side alone

`nai-gate.lock` is a CROSS-PROJECT WIRE CONTRACT, not a stray project name to tidy up.
It must not be renamed, and the `nai-` prefix must not be "cleaned up", in this repo.

A one-sided rename is not cosmetic and does not fail loudly: each tool would wait on a
path the other never writes, so BOTH conclude the gate is free, and two heavy
regressions run concurrently — the exact compile/resource starvation the
serialize-heavy-gates rule exists to prevent. The failure surfaces as an environment
kill during a gate, hours later, attributed to the wrong cause.

A rename therefore requires agreement from both projects and a coordinated change on
both sides: it is filed as a CReq to Crucible (CR-MDB-022 §S5), never an edit here.
Two gates hold this: `tests/test_tooling_detachment.py` pins the `nai-gate.lock` and
`/tmp/nai-gate.lock` literals in `scripts/gate-lock.sh`, and the derivation-equality
gate above fails the moment the two sides disagree.
