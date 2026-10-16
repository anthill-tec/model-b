# CR-MDB-076 — Chrome-UI-Relay waits for the user to accept Chrome's connection prompt

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-16 into release 1.0.0, wave 2).
Gap analysis, the spec and its pre-review happen in order when this CR starts.
**Type:** fix (a skill bundle) — patch CR to CR-MDB-061
**Priority:** P1 — release 1.0.0, wave 2; after CR-MDB-075.
**Depends on:** CR-MDB-061 (board-authoritative: read `queue`)
**Labels:** skills, browser, chrome-devtools-axi
**Design reference:** DN-multi-harness-deploy-model §D23; Crucible #1467.

## Context

- **What Crucible measured.** Crucible's first live run of `chrome-ui-relay` (2026-10-16, on its
  own `crucible` session, Model B develop `564f913`) hit `BRIDGE_NOT_READY` ("the attached CDP
  target appears to have gone away") on the first three calls while the bridge first attached. The
  fourth call succeeded, with nothing changed on Crucible's side.
- **The cause, per the user (2026-10-16).** Chrome asks the user to accept each new remote-debugging
  connection in its GUI. The user accepted late, and until then the tool answered
  `BRIDGE_NOT_READY` with "the attached CDP target appears to have gone away", not the start-up
  timeout message. A new connection is made on a session's first attach and after every bridge
  restart.
- **What the skill does today.** CR-MDB-061 §S6 skips the browser steps on the first
  `BRIDGE_NOT_READY`. It names "Chrome's connection prompt not accepted" as a cause, but only for the
  start-up timeout, so on "target gone away" it skips without asking the user to accept. The whole
  bootstrap's tabs would have been skipped, although the call worked once the prompt was accepted.

## Scope (seed)

1. **Ask the user to accept, then retry.** On a `BRIDGE_NOT_READY` that a pending connection prompt
   can cause ("target gone away", the start-up timeout), the skill tells the user to accept Chrome's
   connection prompt, then re-runs the same call a bounded number of times, a few seconds apart.
   Only after the last attempt fails does it skip and report. The bound and the spacing come from
   measuring the tool at gap analysis.
2. **Which causes wait for the prompt.** Causes a prompt cannot explain (remote debugging off, a port
   collision, a failed `npx` fetch) skip at once, as today. Decide the split at gap analysis, going
   by the envelope's message.
3. **Tell the caller up front.** Before the first call of a session, the skill says that Chrome will
   ask the user to accept the connection; a services skill relays it at bootstrap.
4. **Safety on retry.** A retried `newpage` still follows CR-MDB-061's rule that a timed-out
   `newpage` made its tab: confirm it among the new ids, never open it twice. Retrying `pages`,
   `selectpage` and `eval` is harmless; `closepage` keeps the id-and-URL match.
5. **The skill's gates** gain the retry rules, each proved both ways.

## To measure at gap analysis

- In the installed `chrome-devtools-axi`'s source (read-only): what produces "the attached CDP target
  appears to have gone away" while the prompt is pending; whether the tool retries internally; and
  how long Chrome keeps a prompt open.
- A live reproduction on Model B's own session with the user present, as CR-MDB-061's live check
  was run.
- The re-score.
