# CR-MDB-076 — Chrome-UI-Relay waits for the user to accept Chrome's connection prompt

**Status:** PENDING — spec (gap analysis 2026-10-16).
**Type:** fix (a skill bundle) — patch CR to CR-MDB-061
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** CR-MDB-061 (board-authoritative: read `queue`)
**Labels:** skills, browser, chrome-devtools-axi
**Design reference:** DN-multi-harness-deploy-model §D23 (its 2026-10-16 ruling on waiting for
Chrome's connection prompt); Crucible #1467, #1469.

## Context

- **What Crucible saw.** Crucible's first live run of `chrome-ui-relay` (2026-10-16, Model B develop
  `564f913`) got `BRIDGE_NOT_READY` ("the attached CDP target appears to have gone away") on its first
  three calls. The fourth succeeded.
- **The cause.** Chrome asks the user, in its GUI, to accept each new remote-debugging connection, and
  the user accepted late.
- **What `chrome-devtools-axi` does** (0.1.42, `dist/src/client.js` `ensureBridge`, read 2026-10-16):
  - When no healthy bridge exists, it spawns one and polls its health every 500 ms until
    `CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS` runs out (30 s by default).
  - A bridge whose server came up but never attached to Chrome, as while the prompt is pending, ends
    in `BRIDGE_NOT_READY` "Bridge is running but the attached CDP target appears to have gone away".
  - A bridge that never came up ends in "Bridge failed to start within <n>s".
  - The next call finds the unhealthy bridge, kills it and spawns a new one: a new connection, and so
    a new prompt.
- **What the shipped skill does** (CR-MDB-061 §S6). It skips the browser steps on the first
  `BRIDGE_NOT_READY`. It names "Chrome's connection prompt not accepted within the start-up
  timeout" as a cause, with the fix "ask the user to accept the prompt, then run the step again". It
  doesn't warn the user beforehand, and with the 30 s default a slow click loses the whole step.

## Scope

### §S1 — The warning before the first call

Before a session's first `chrome-devtools-axi` call, the skill tells the user that Chrome will ask
them to accept the connection, and that the browser steps wait up to two minutes for it. A services
skill relays this at bootstrap. The same warning applies after a bridge restart, which raises a new
prompt.

### §S2 — One connection, a two-minute wait, no retry

- **Every call** carries `CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=120000`, beside
  `CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1` and `CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN>`. A healthy
  bridge answers at once; only a bridge waiting to attach uses the time.
- **The skill never retries a call that ended in `BRIDGE_NOT_READY`.** A retry kills the waiting bridge
  and raises a new prompt.
- **A call that still fails** skips the browser steps, as CR-MDB-061 §S6 says.
- **The cost is stated:** with no browser to attach to, the first call can take up to two minutes
  before the skip.

### §S3 — The causes

The skill's list of causes reads:

- **Chrome's connection prompt not accepted within the two-minute wait.** The message is "the
  attached CDP target appears to have gone away". The fix: the user accepts the prompt, then asks for
  the browser steps again. The skill never re-runs them on its own.
- **Chrome stable not running, or remote debugging off.** Unchanged.
- **Chromium or another channel running instead of Chrome stable.** Unchanged.
- **A port collision** ("code 48"). Unchanged.
- **`npx` failing to fetch `chrome-devtools-mcp`.** Unchanged; it now covers "Bridge failed to start
  within <n>s" too.

Every call that shows the session also shows the bridge wait: the invocation section and each fenced
command.

### §S4 — The pins

- **`test_project_registry_schema`'s `NOT_REGISTRY_KEYS`** gains
  `CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS`, which the registry-key detector flags in the skill's code
  spans. This is a RED-cycle migration, marked `# MIGRATED at CR-MDB-076 (§S4)`.
- **`test_chrome_ui_relay_skill`'s rules** move with the new text:
  - the invocation rule now requires the bridge wait;
  - the prompt cause changes from "run the step again" to "the user asks for the browser steps again";
  - the conforming sample is updated.

## Acceptance criteria

- [ ] **§S1.** A gate pins the warning before the first call: Chrome will ask, two minutes, a services
      skill relays it, and again after a bridge restart.
- [ ] **§S2.** Gates pin:
      - `CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=120000` in the invocation rule and on every fenced call;
      - "never retries" after `BRIDGE_NOT_READY`, with its reason;
      - the skip;
      - the stated cost.

      A negative gate fails on any fenced call that names `CHROME_DEVTOOLS_AXI_SESSION` without the
      bridge wait.
- [ ] **§S3.** Gates pin the prompt cause (its message, the two-minute wait, the user asks again, never
      re-run by the skill), and the `npx` cause covering "failed to start".
- [ ] **§S4.** `NOT_REGISTRY_KEYS` holds exactly the new name. The registry-key gate and its
      stale-name rule pass. The migrated rules are marked.
- [ ] **Every detector kind** is proved both ways.
- [ ] **Runs.**
      - The suite is green through the client, with a real `HOME` and an empty one.
      - No test runs `chrome-devtools-axi`, `npx` or a browser.
      - The frontmatter stays within Pi's limits, and the loader reports no diagnostics.
      - `generator/build.py --check` is clean.
      - The `AGENTS.md` baselines match.
- [ ] **Live check, before merge.** With the user present, under Model B's own session, after `stop`
      so the first call raises a fresh prompt:
      - the user accepts after a deliberate delay of over 30 s and under two minutes;
      - the first `pages` call succeeds;
      - its envelope goes in the sign-off.

## Non-goals

- **Pinning or installing `chrome-devtools-mcp`.**
- **Changing the session or tab-ownership rules.**
- **Detecting the prompt itself.** The tool exposes no such state.

## Cycle plan

1. **The wait and the warning (§S1–§S4).** Red-green.
2. **Verify, with the live check.**
