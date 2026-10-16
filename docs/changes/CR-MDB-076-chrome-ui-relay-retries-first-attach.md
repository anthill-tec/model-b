# CR-MDB-076 — Chrome-UI-Relay retries a bridge that is still attaching

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
- **What the skill does today.** CR-MDB-061 §S6 skips the browser steps on the first
  `BRIDGE_NOT_READY`. Under that rule the whole bootstrap's tabs would have been skipped, although
  a retry a moment later worked.

## Scope (seed)

1. **A bounded retry before the skip.** On `BRIDGE_NOT_READY`, re-run the same call a bounded number
   of times, a few seconds apart, before skipping. The bound and the spacing come from measuring
   the tool at gap analysis. Only after the last attempt fails does the skill skip and report.
2. **Which causes are retried.** Decide at gap analysis which `BRIDGE_NOT_READY` causes are worth
   retrying ("target gone away", the start-up timeout) and which are not (remote debugging off, a
   port collision), going by the envelope's message.
3. **Safety on retry.** A retried `newpage` still follows CR-MDB-061's rule that a timed-out
   `newpage` made its tab: confirm it among the new ids, never open it twice. Retrying `pages`,
   `selectpage` and `eval` is harmless; `closepage` keeps the id-and-URL match.
4. **The skill's gates** gain the retry rules, each proved both ways.

## To measure at gap analysis

- In the installed `chrome-devtools-axi`'s source (read-only), what produces "the attached CDP target
  appears to have gone away", and whether the tool retries internally.
- A live reproduction on Model B's own session with the user present, as CR-MDB-061's live check
  was run.
- The re-score.
