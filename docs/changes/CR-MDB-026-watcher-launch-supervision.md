# CR-MDB-026 — The wake watcher must stay alive: supervised process + `restart: on-failure`, and the three-exit taxonomy the bundles conflate

**Status:** PENDING
**Type:** bugfix
**Priority:** P1 (blocks release 1.0.0 — TWO independent guarantees of a dead watcher, both
measured this session. (a) Launching it as a backgrounded shell job means any harness with a job
deadline shorter than the watcher's timeout kills it — observed at 300s against a 14400s timeout,
a 48x mismatch. (b) Even supervised, the watcher exits code 2 at its own 14400s timeout, so the
default no-restart policy leaves it dead after ~4 hours of any long session. A dead Mainline
watcher silently stops waking on Track mail while a blocked track HOLDS forever, which is the
exact failure the prime directive exists to prevent — and because a timeout exit and the
mail-arrival exit are both just "the process is gone", the bundles' current two-case reading of
an exit is itself part of the defect)
**Depends on:** CR-MDB-029 (on Pi the supervised process with `restart: on-failure` is a
Model-B-built Pi extension — DN §D15.3, user ruling; without it this CR's §S1 has no mechanism
on the only target and the watcher regresses to the very defect it exists to fix, DN §D13 (3)).
Until 029 ships, the `run_in_background` fallback §S4 names is the Pi path, and the bundles must
say so explicitly.
**Labels:** skills, hooks, orchestration, sandesh, bugfix
**Design reference:** measured failure this session (2026-09-16, Mainline - ModelB) · `skills-src/bootstrap/SKILL.md` §Step-1 · `skills-src/shutdown/SKILL.md` §common-final-step · `skills-src/model-b/references/sandesh.md` §Bootstrap + §PRIME-DIRECTIVE · project memory `sandesh-mcp-only-boundary` (the CLI verbs an agent session may run)

## Amendments 2026-09-21 (from `audits/2026-09-21-codebase-review-docs.md`)

- Dependency on **CR-MDB-029** added (header). §S1 names the Pi mechanism: the `sandesh-watcher`
  extension (029 §S2) implements this CR's three-exit taxonomy and readiness-on-banner; 029's
  AC asserts mail / timeout / lock-conflict handling with a faked `sandesh notify`. The three
  instruction-level edits (§S2/§S3) reference that extension's command, with the backgrounded
  fallback labelled as such.
- The other `run_in_background` uses in the skills (dispatching RED/GREEN/VERIFY/FIX,
  `orchestration-track.md:39`; `crucible:114`) are NOT the watcher and are NOT this CR's — they
  are rewritten for archimedes' blocking dispatch by CR-MDB-031 §S2.

## Context

`bootstrap` tells every orchestrator to launch its wake watcher as a **backgrounded shell job**:

> Launch the wake watcher **in the background** (`run_in_background`):
> `sandesh notify --to "<your address>" --project <Project>`. NEVER run it inline — it blocks.

The reasoning is sound — the watcher blocks, so it cannot run inline. The **mechanism** is wrong
on any harness that imposes a deadline on backgrounded jobs.

**Measured, this session, twice.** The watcher was launched exactly as the skill instructs and
was killed at 300 seconds by the harness job deadline, mid-poll, with no mail involved:

```
[notify] watching Mainline - ModelB in ModelB  (pid 668564, interval 10s, timeout 14400s)
[notify] 15:48:51 no 'to' mail — next check in 10s
…30 healthy polls…
[notify] 15:53:41 no 'to' mail — next check in 10s
[Command timed out after 300 seconds]
```

The watcher's own timeout is **14400s**; the harness killed it at **300s** — a 48× mismatch. It
was polling healthily at the moment it died. Relaunching it the same way just restarts the same
5-minute clock, so the steady state is a watcher that is dead far more often than alive.

**Why this is a correctness bug and not an inconvenience.** The whole point of the watcher is
out-of-band wake: an MCP server cannot re-invoke a sleeping agent, so `sandesh notify` exiting on
mail arrival IS the wake mechanism (`sandesh.md` §Two-channels). A watcher killed by a deadline
exits **exactly like a watcher that received mail** — same process gone, and on some harnesses
the same exit code. So:

- Mainline stops waking on Track requests; a track that raised a blocker HOLDS forever (`sandesh.md`:
  a track holds with "zero LLM turns, never self-poll" — it is structurally incapable of nudging).
- The deadline-kill is **indistinguishable from the mail-arrival exit** without reading the log,
  so the documented `fetch`-then-relaunch response fires on a false signal.
- A relaunched watcher only fires on mail arriving **after** it starts (`sandesh.md` PRIME
  DIRECTIVE), so every deadline-kill opens a gap in which arriving mail produces no wake at all.
  The prime directive's own `fetch`-FIRST ordering exists for this gap — but it only helps if the
  session happens to be awake to notice the exit.

**The correct mechanism already exists and is not used.** A long-running, supervised process with
no job deadline, addressed by a stable name, with readiness gated on the watcher's own log line.
Verified working this session:

```
Started sandesh-watcher-modelb: ready pid=672627 uptime=155ms restarts=0
Ready log matched: watching Mainline - ModelB
```

Readiness matched on the watcher's real banner, so "launched" and "actually listening" became one
observable fact instead of two hopes — which also closes the `listening:false` trap the bundles
currently handle with a manual re-probe step.

**Supervision alone is NOT sufficient — measured later the same session.** The supervised watcher
then exited **code 2** after ~4 hours with `timed out (1441 polls)` in its own log (1441 × 10s
≈ 14410s, i.e. the CLI's documented 14400s timeout). So the watcher has a finite natural
lifetime and dies at it, supervised or not. A supervised process with the default `restart: no`
policy is therefore still guaranteed to be dead after ~4 hours of a long session.

**There are THREE distinct exits and the bundles conflate them.** This taxonomy is the CR's
central content, because the response differs per case and two of the three look identical:

| exit | meaning | correct response |
|---|---|---|
| `0` | mail arrived — this IS the wake mechanism | `fetch` FIRST, then relaunch (the session's job) |
| `2` | the 14400s timeout expired; no mail involved | relaunch; no fetch needed (nothing was delivered) |
| non-zero, immediately after launch | a duplicate hit the lock | **do nothing** — the prior watcher is alive |

**`restart: on-failure` is the correct policy and discriminates by construction:** mail arrival
exits `0`, which a failure-only policy does NOT restart — so the session is still woken and still
performs the mandatory `fetch`-then-relaunch — while timeout expiry and transient faults exit
non-zero and self-heal under bounded backoff. Verified working this session; a duplicate-lock
exit also self-limits because the backoff applies while the live watcher keeps the lock.


**Scope is two bundles plus one reference, and the instruction appears more than once.** It is in
`bootstrap` (Step 1), in `shutdown` (the kill step names the same launch mechanism it is undoing),
and in `model-b/references/sandesh.md` (§Bootstrap step 3 — the generic mechanics every project
inherits). All three must move together or a reader following one will contradict another.

## Scope

### §S1 — Correct the launch instruction in `sandesh.md` (the generic authority)
§Bootstrap step 3 names a **supervised long-running process** as the launch mechanism, keyed by a
stable per-address name, with readiness gated on the `watching <address> in <Project>` banner,
**and an explicit `restart: on-failure` policy** — supervision without it still leaves the
watcher dead at its own 14400s timeout.
`run_in_background` is retained as an explicitly-labelled **fallback for harnesses with no process
supervisor**, together with the consequence of using it (the watcher dies at the harness job
deadline and must be treated as unreliable).

The PRIME DIRECTIVE section carries the **three-exit taxonomy** (exit `0` = mail arrived, the wake
itself, answer with `fetch` FIRST then relaunch; exit `2` = the 14400s timeout expired, relaunch
with no fetch owed; immediate non-zero = a duplicate hit the lock, do NOTHING because the prior
watcher is alive). It states that the log tail is what distinguishes them, that `fetch` precedes
relaunch whenever mail could have arrived, and that a failure-only restart policy is safe
precisely because the mail-arrival case exits `0` and is therefore never auto-restarted behind the
session's back.

### §S2 — Correct `bootstrap` Step 1
Same substitution, phrased for the bootstrap flow, keeping the existing "never run it inline" and
"exactly ONE per address" rules intact. The existing manual `listening:true` re-probe is retained
(it verifies the addressbook, which readiness-matching does not), but is no longer the only signal
that the launch worked.

### §S3 — Correct `shutdown`'s final step
The kill step names how to stop a **supervised** watcher by name, keeping the existing targeted-kill
guidance as the fallback path and the absolute prohibition on machine-wide `pkill` untouched. The
"kill it LAST, do not relaunch" semantics are unchanged — this CR changes the mechanism, never the
lifecycle.

### §S4 — No new coupling
No change to `sandesh` CLI usage beyond the launch/stop mechanism, no new dependency, and no
filesystem access to the Sandesh store (project memory `sandesh-mcp-only-boundary` stands).

## Acceptance criteria

### §S1
- [ ] `skills-src/model-b/references/sandesh.md` §Bootstrap names a supervised named process as the
      primary launch mechanism, with readiness gated on the watcher's own banner line.
- [ ] `run_in_background` appears only as an explicitly-labelled fallback, and the text states the
      deadline-kill consequence of using it.
- [ ] The launch instruction specifies `restart: on-failure` (or the harness equivalent), and the
      text states WHY a failure-only policy is correct: mail arrival exits `0` and must NOT be
      auto-restarted, because the session owes a `fetch` on that path.
- [ ] The PRIME DIRECTIVE section enumerates all THREE exits with a distinct response each —
      `0` mail-arrived (fetch first, then relaunch), `2` timeout-expired (relaunch, no fetch owed),
      immediate non-zero (duplicate hit the lock, do nothing, prior watcher alive) — and names the
      log tail as what distinguishes them.
- [ ] No instruction anywhere treats a non-zero watcher exit as proof that mail arrived, or a
      zero exit as proof that it did not.

### §S2
- [ ] `skills-src/bootstrap/SKILL.md` Step 1 matches §S1's mechanism; the "exactly ONE per address"
      and "never inline" rules survive verbatim in substance.
- [ ] The `listening:true` addressbook re-probe is still required after launch.

### §S3
- [ ] `skills-src/shutdown/SKILL.md`'s final step stops the watcher by its supervised name, retains
      the targeted-kill fallback, and still forbids machine-wide kills.
- [ ] The kill-last / no-relaunch lifecycle is unchanged — asserted by diffing the lifecycle
      sentences, which must not move.

### §S4
- [ ] Zero occurrences of a watcher-launch instruction that names ONLY `run_in_background` across
      `skills-src/` — asserted by grep over all three files.
- [ ] No test or skill instructs any direct read/write of the Sandesh data directory.

## Estimated size

Three files, instruction-level edits; no `modelb_axi/` logic change. One test extension asserting
the grep gate in §S4/AC1 (the gate is the only thing that stops the old instruction reappearing in
a future bundle).

## Risk

- **The three files must move in one commit.** A reader following a half-updated set gets
  contradictory instructions, which is worse than the current uniformly-wrong state.
- **Do not weaken the prime directive while rewording it.** The `fetch`-before-relaunch ordering
  and the exactly-one-watcher rule are load-bearing; this CR makes the launch durable, it does not
  relax the discipline.
- **Supervisor availability is harness-dependent.** The fallback must stay genuinely usable, and
  must not be written as an afterthought — a harness without a supervisor still needs a correct,
  if degraded, procedure.
- `bootstrap`/`shutdown` are deployed bundles; their gates assert structure and anchors, so the
  edits must keep section headings the existing tests pin.

## Non-goals

- No change to the `sandesh` CLI itself (not Model B's code) and no request to Crucible or Sandesh.
- No change to the wake protocol, the addressing scheme, or the request/directive/reply verbs.
- No change to the watcher's own poll interval or timeout — those are the CLI's defaults and are
  correct; the defect is purely in how Model B's bundles tell a session to launch it.
- No retrofit of other long-running processes; this CR is scoped to the Sandesh watcher, which is
  the one whose death is silent.
