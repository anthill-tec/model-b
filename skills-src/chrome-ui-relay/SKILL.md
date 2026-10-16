---
name: chrome-ui-relay
description: Open, read and close a frontend project's own tabs in the user's running Chrome through chrome-devtools-axi, one bridge per project. Use when a frontend project's services skill opens its dev pages at bootstrap, reads them, or closes them at shutdown.
---

# Chrome-UI-Relay

This skill drives a frontend project's own tabs in the user's Chrome. A frontend project's
services skill calls it: to open its dev pages at bootstrap, to read them, and to close them at
shutdown. No other caller uses it.

This skill is not the omp-era CDP relay; that relay must never run under Pi.

For a project's tabs, this skill overrides the user-level `chrome-devtools-axi` skill: it never
navigates with `open`, and it never narrows the output.

## Before the first call

Before the first call of every bootstrap, and of every shutdown that runs a call other than `stop`
(`stop` never connects, so no prompt comes), the skill warns the user, and a services skill relays
the warning:

- Chrome will ask them to accept the connection;
- they accept within about a minute, and if Chrome asks again, they accept again;
- any call may restart the bridge, which the tool never reports, and a restart raises a new prompt.

## Invocation and the session

Every call is `npx -y chrome-devtools-axi <verb>` with:

- `CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1`;
- `CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN>`, the value from the project's `.env`;
- `CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=120000`, the bridge wait of two minutes, written exactly so;
  on `stop` it does nothing but is kept, so every call reads the same.

Each project has its own bridge, and its `stop` ends only its own.

A call, in full:

```bash
CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1 CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN> CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=120000 npx -y chrome-devtools-axi pages
```

It never launches a browser and never uses `open`. Navigation is `newpage` only.

`<PROJECT_TOKEN>`, `<dev-url>` and `<id>` are values to substitute, never typed literally.

`pages` prints its tabs as `pages[N]{id,url,selected}`, one row per tab.

Read `PROJECT_TOKEN` from the project's `.env` before the first call.

When `PROJECT_TOKEN` is absent, not of the form `[A-Za-z0-9._-]{1,64}`, or `default`:

- the browser steps are skipped;
- the skill reports "no valid session name: set `PROJECT_TOKEN` in `.env`";
- it never falls back to the default session.

## The bridge wait

Each call is given a shell timeout of at least 150 s (2.5 minutes). A call killed by its shell
timeout counts as `BRIDGE_NOT_READY`.

The skill never retries a call that ended in `BRIDGE_NOT_READY`: a retry kills the waiting bridge
and raises a new prompt.

With no browser to attach to, the first call takes the full two minutes before the skip.

## Inputs

The caller gives three lists:

- the URLs to open;
- the URL patterns the project's tabs match;
- the protected patterns: tabs never selected, evaluated or closed, such as a production install's
  port.

**URLs are compared by pattern.** Chrome normalises the URLs it shows (a trailing slash, a
redirect). So a tab "shows" a URL to open when its URL matches the project pattern the caller gives
for that URL, never by exact string.

**Protected wins everywhere.** A protected tab is never counted as already open, never chosen and
never closed. A URL to open that matches a protected pattern is a caller error: it is reported and
skipped.

## Open

1. **`pages`.** Keep its id set as "before".
   - A URL to open that already shows in a tab is not opened again.
   - That tab is the user's or a previous bridge's. It is never selected, evaluated or closed.

   ```bash
   CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1 CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN> CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=120000 npx -y chrome-devtools-axi pages
   ```

2. **`newpage <dev-url>`** for each remaining URL. Never navigate an existing or selected tab.

   ```bash
   CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1 CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN> CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=120000 npx -y chrome-devtools-axi newpage <dev-url>
   ```

3. **`pages` again.** The new tabs are the "after" ids minus the "before" ids.
   - Every URL opened shows among the new ids.
   - Every "before" id is still there.
   - Otherwise, stop and report.
   - The new tabs are the skill's own for this bridge. It keeps that record as **(id, URL) pairs**,
     held in the caller's working context; a restarted agent session has no record.
4. **A `newpage` that timed out still made its tab.** Confirm it among the new ids; never retry,
   since a retry duplicates it.
5. **Rendered text** is confirmed with `selectpage <id>` and `eval document.body.innerText.length`
   on the skill's own tabs only, never the load event.

   ```bash
   CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1 CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN> CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=120000 npx -y chrome-devtools-axi selectpage <id>
   CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1 CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN> CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=120000 npx -y chrome-devtools-axi eval document.body.innerText.length
   ```

## Close

1. **`pages`, fresh.** The tabs to close are those in the skill's record whose id still shows with
   its recorded URL, and are not protected.
   - If any recorded id shows with a different URL, or is gone while its URL shows on another id, the
     bridge has restarted silently (the tool never reports a respawn): close nothing, and report the
     tabs on the project's URLs for the user to close.
2. **`closepage`** each of them.

   ```bash
   CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1 CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN> CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=120000 npx -y chrome-devtools-axi closepage <id>
   ```

3. **`pages` again,** to verify. A last-tab no-op shows here as a tab still open.
4. **`stop`.** It disconnects the project's bridge and never closes Chrome.

   ```bash
   CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1 CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN> CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=120000 npx -y chrome-devtools-axi stop
   ```

- **When control fails,** retry once; the single retry never applies to a `BRIDGE_NOT_READY`
  envelope: that envelope skips. The single retry never repeats `stop`. Otherwise report the tabs
  left open, naming their URLs.
- **When there is no record,** because the bridge restarted or bootstrap never opened a tab,
  nothing is closed. Tabs on the project's URLs are reported for the user to close.
- **When bootstrap skipped on a `BRIDGE_NOT_READY`,** shutdown skips its browser steps: it runs one
  `stop` and nothing else, and starts no bridge. When bootstrap skipped for no valid session name,
  shutdown runs no call at all: with no valid session, a `stop` would reach the shared default
  session's bridge.

## When the bridge cannot attach

The browser is detected at run time. An envelope carrying `code: BRIDGE_NOT_READY` means:

- the skill's browser steps are skipped;
- the skill runs `stop` once, which never starts a bridge, so the call's stray bridge raises no late
  prompt;
- the skill reports the envelope's `error` line and every `help` line in full; the suggestions are
  reported, never run (one of them suggests `open`);
- a skipped browser never fails bootstrap or shutdown.

The causes the tool reports, each with its fix:

- **"The attached CDP target appears to have gone away",** after the two-minute wait. The message
  is shared by three causes, which the skill reports together:
  - Chrome stable not running, or remote debugging off: enable it at
    `chrome://inspect/#remote-debugging`;
  - another channel (Chromium) running instead of Chrome stable: start Chrome stable instead;
  - the connection prompt not accepted within the wait.

  The fix: the user asks for the browser steps again, and accepts within a minute. The skill never
  re-runs them on its own.
- **A port collision** ("code 48"): set `CHROME_DEVTOOLS_AXI_PORT` for this session only.
- **`npx` failing to fetch `chrome-devtools-mcp`** on a cold start, including "Bridge failed to start
  within <n>s": report the tool's own message and fix.

## Reading the output

Every `chrome-devtools-axi` envelope is read whole. It is never piped through grep, head or tail,
narrowed with `jq`, or redirected away.
