# CR-MDB-076 — Chrome-UI-Relay waits for the user to accept Chrome's connection prompt

**Status:** COMPLETED (filed, gap analysis and pre-review 2026-10-16). The file name's "retries" slug
predates the no-retry ruling and is kept so references stay stable.
**Type:** fix (a skill bundle) — patch CR to CR-MDB-061
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** CR-MDB-061 (board-authoritative: read `queue`)
**Labels:** skills, browser, chrome-devtools-axi
**Design reference:** DN-multi-harness-deploy-model §D23 (its 2026-10-16 rulings on waiting for
Chrome's connection prompt); Crucible #1467, #1469.

## Context

- **What Crucible saw.** Crucible's first live run of `chrome-ui-relay` (2026-10-16, Model B develop
  `564f913`) got `BRIDGE_NOT_READY` ("the attached CDP target appears to have gone away") on its first
  three calls; the fourth succeeded. Chrome asks the user, in its GUI, to accept each new
  remote-debugging connection, and the user accepted late.
- **`chrome-devtools-axi`** (0.1.42, `dist/src/client.js`, read 2026-10-16):
  - **The bridge wait.** With no healthy bridge, `ensureBridge` spawns one and polls until
    `CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS` runs out. Each poll is a deep probe (≤5 s), a shallow
    probe (≤2 s), then 500 ms, so the last round can overrun by about 7 s.
    - The variable is read per call, in milliseconds, with no maximum.
    - Empty, non-numeric or ≤0 means 30 000. Below 1 000 is raised to 1 000.
    - `120s` parses as 1 s, so the value must be exactly `120000`.
  - **A healthy bridge** answers at once, whatever the variable says.
  - **After the deadline:**
    - a bridge whose server came up but never attached reports "Bridge is running but the attached
      CDP target appears to have gone away";
    - one that never came up reports "Bridge failed to start within <n>s".
  - **Early exits.** A bridge whose process exits early (a port collision, code 48; a failed `npx`
    fetch) reports at once, "exited with code <n> before becoming ready".
  - **The next call** finds an unhealthy bridge, kills it and spawns a new one: a new connection, a new
    prompt.
  - **A failed call leaves its own bridge running** until the next call or `stop`. `stop` never spawns
    a bridge.
- **`chrome-devtools-mcp`** (`@latest`, read at 1.11.0, the server behind the bridge) gives up on a
  pending connection after 60 s and opens a new one. So a prompt left more than a minute is replaced by
  a second prompt.
- **One message, several causes.** No Chrome stable running, remote debugging off, another channel
  running, and a prompt not accepted all end the same way: the full wait, then "the attached CDP
  target appears to have gone away".
- **What the shipped skill does** (CR-MDB-061 §S6):
  - It skips the browser steps on the first `BRIDGE_NOT_READY`.
  - It names "Chrome's connection prompt not accepted within the start-up timeout" as a cause, with
    "ask the user to accept the prompt, then run the step again".
  - Its Close section retries a failed control once.
  - It doesn't warn the user beforehand, and with the 30 s default a slow click loses the whole step.

## Scope

### §S1 — The warning

The skill tells the user before the first call of every bootstrap, and of every shutdown that runs
a call other than `stop` (`stop` never connects, so no prompt comes):

- Chrome will ask them to accept the connection.
- They should accept within about a minute; if Chrome asks again, they accept again.
- Any call may restart the bridge, which the tool never reports, and a restart raises a new prompt.

A services skill relays the warning.

### §S2 — One wait of two minutes, no retry, the stray bridge stopped

- **Every call carries `CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=120000`,** beside
  `CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1` and `CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN>`. On `stop` it
  does nothing but is kept, so every call reads the same.
- **Each call is given a shell timeout of at least 150 s (2.5 minutes).** A call killed by its shell
  timeout counts as `BRIDGE_NOT_READY`.
- **The skill never retries a call that ended in `BRIDGE_NOT_READY`:** a retry kills the waiting
  bridge and raises a new prompt. Close's single retry never applies to a `BRIDGE_NOT_READY`
  envelope; that envelope skips.
- **On a `BRIDGE_NOT_READY` skip,** the skill:
  - skips the browser steps, as CR-MDB-061 §S6 says;
  - runs `stop` once (it never starts a bridge), so the call's stray bridge raises no late prompt.

  A shutdown whose bootstrap skipped on a `BRIDGE_NOT_READY` runs that one `stop` and nothing else.
  A shutdown whose bootstrap skipped for no valid session name runs no call at all: with no valid
  session, a `stop` would reach the shared default session's bridge.
- **Close's single retry never repeats `stop`.**
- **The cost is stated:** with no browser to attach to, the first call takes the full two minutes
  before the skip.

### §S3 — The causes

The skill's list of causes:

- **"The attached CDP target appears to have gone away",** after the two-minute wait. The message is
  shared by three causes, which the skill reports together:
  - Chrome stable not running, or remote debugging off: enable it at
    `chrome://inspect/#remote-debugging`;
  - another channel (Chromium) running instead of Chrome stable;
  - the connection prompt not accepted within the wait.

  The fix: the user asks for the browser steps again, and accepts within a minute. The skill never
  re-runs them on its own.
- **A port collision** ("code 48"): set `CHROME_DEVTOOLS_AXI_PORT` for this session only. Unchanged.
- **`npx` failing to fetch `chrome-devtools-mcp`,** including "Bridge failed to start within <n>s":
  report the tool's own message and fix.

Every call that shows the session also shows the bridge wait: the invocation section and each fenced
command.

### §S4 — The pins

- **`test_project_registry_schema`'s `NOT_REGISTRY_KEYS`** gains exactly one entry,
  `CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS`, with its reason. The registry-key detector flags it in the
  skill's code spans. This is a RED-cycle migration, marked `# MIGRATED at CR-MDB-076 (§S4)`.
- **`test_chrome_ui_relay_skill`'s rules,** each marked `# MIGRATED at CR-MDB-076 (§S…)`:
  - the invocation rule requires the bridge wait;
  - the prompt-cause rule's `\btimeout\b` becomes the two-minute wait and the shared message, and its
    cut and name are renamed;
  - the Close retry rule's unit carries the `BRIDGE_NOT_READY` exception;
  - the bridge-cannot-attach rules carry the single `stop`;
  - the conforming sample is updated.

## Acceptance criteria

- [ ] **§S1.** A gate pins the warning: before the first call of every bootstrap and of every shutdown
      that runs a call other than `stop`; "accept within about a minute"; "accept again"; a restart
      raises a new prompt; a services skill relays it.
- [ ] **§S2.** Gates pin:
      - the exact `CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=120000`;
      - the 150 s shell timeout, and a killed call counting as `BRIDGE_NOT_READY`;
      - "never retries", with its reason;
      - Close's retry not applying to `BRIDGE_NOT_READY`;
      - the skip and the single `stop`;
      - the single `stop` only after a `BRIDGE_NOT_READY` skip, and no call at all after a skip for no
        valid session name;
      - Close's retry never repeating `stop`;
      - the full-two-minutes cost.

      The new text names no harness tool ("shell timeout", never a tool's name).
- [ ] **The negative gate.** It fails on any fenced line running `chrome-devtools-axi` that lacks any of
      these exact tokens:
      - `CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1`
      - `CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN>`
      - `CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=120000`

      The tokens must be env assignments before the `chrome-devtools-axi` word of each command
      segment: a line is split on `&&`, `||`, `;` and `|`, and a trailing ` #…` comment is stripped.
      It is proved both ways, including a wrong value (`=60000`), a backslash-continued line, tokens
      after the verb, tokens in a trailing comment, and a chained second call without them. The
      skill's fenced calls are counted: all 7 (`pages` twice, `newpage`, `selectpage`, `eval`,
      `closepage`, `stop`) are checked.
- [ ] **§S3.** Gates pin:
      - the shared message;
      - its three causes reported together;
      - the user asks again and accepts within a minute;
      - never re-run by the skill;
      - the `npx` cause covering "failed to start".
- [ ] **§S4.** `NOT_REGISTRY_KEYS` gains exactly one entry, and the registry-key gate and its stale-name
      rule pass. The migrated rules are marked.
- [ ] **Every detector kind** is proved both ways.
- [ ] **Runs.**
      - The suite is green through the client, with a real `HOME` and an empty one.
      - No test runs `chrome-devtools-axi`, `npx` or a browser.
      - The frontmatter stays within Pi's limits, and the loader reports no diagnostics.
      - `generator/build.py --check` is clean.
      - The `AGENTS.md` baselines match.
- [ ] **Live check, before merge.** With the user present, under Model B's own session, after `stop` so
      the first call raises a fresh prompt:
      - the user accepts after a deliberate delay of over 30 s and under 60 s;
      - the first `pages` call, run with a shell timeout of at least 150 s, succeeds;
      - the start and end times show the delay;
      - its envelope goes in the sign-off, with the `pages[N]` header kept and the user's tab URLs
        redacted.

## Non-goals

- **Pinning or installing `chrome-devtools-mcp`.**
- **Changing the session or tab-ownership rules.**
- **Detecting the prompt itself.** The tool exposes no such state.

## Consequences

- **Crucible.** Its services skill runs these calls, so it needs the shell timeout and the relayed
  warning. Crucible gets a Sandesh note when this merges.

## Cycle plan

1. **The wait, the warning and the stop (§S1–§S4).** Red-green.
2. **Verify, with the live check.**
