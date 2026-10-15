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

## Invocation and the session

Every call is `npx -y chrome-devtools-axi <verb>` with:

- `CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1`;
- `CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN>`, the value from the project's `.env`.

Each project has its own bridge, and its `stop` ends only its own.

A call, in full:

```bash
CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1 CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN> npx -y chrome-devtools-axi pages
```

It never launches a browser and never uses `open`. Navigation is `newpage` only.

Read `PROJECT_TOKEN` from the project's `.env` before the first call.

When `PROJECT_TOKEN` is absent, not of the form `[A-Za-z0-9._-]{1,64}`, or `default`:

- the browser steps are skipped;
- the skill reports "no valid session name: set `PROJECT_TOKEN` in `.env`";
- it never falls back to the default session.

## Inputs

The caller gives three lists:

- the URLs to open;
- the URL patterns the project's tabs match;
- the protected patterns: tabs never selected, evaluated or closed, such as a production install's
  port.

**Protected wins everywhere.** A protected tab is never counted as already open, never chosen and
never closed. A URL to open that matches a protected pattern is a caller error: it is reported and
skipped.

## Open

1. **`pages`.** Keep its id set as "before".
   - A URL to open that already shows in a tab is not opened again.
   - That tab is the user's or a previous bridge's. It is never selected, evaluated or closed.

   ```bash
   CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1 CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN> npx -y chrome-devtools-axi pages
   ```

2. **`newpage <dev-url>`** for each remaining URL. Never navigate an existing or selected tab.

   ```bash
   CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1 CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN> npx -y chrome-devtools-axi newpage <dev-url>
   ```

3. **`pages` again.** The new tabs are the "after" ids minus the "before" ids.
   - Every URL opened shows among the new ids.
   - Every "before" id is still there.
   - Otherwise, stop and report.
   - The new ids are the skill's own tabs for this bridge. It keeps that record for the session.
4. **A `newpage` that timed out still made its tab.** Confirm it among the new ids; never retry,
   since a retry duplicates it.
5. **Rendered text** is confirmed with `selectpage <id>` and `eval document.body.innerText.length`
   on the skill's own tabs only, never the load event.

   ```bash
   CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1 CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN> npx -y chrome-devtools-axi selectpage <id>
   CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1 CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN> npx -y chrome-devtools-axi eval document.body.innerText.length
   ```

## Close

1. **`pages`, fresh.** The tabs to close are those in the skill's record that still show, and are
   not protected.
2. **`closepage`** each of them.

   ```bash
   CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1 CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN> npx -y chrome-devtools-axi closepage <id>
   ```

3. **`pages` again,** to verify. A last-tab no-op shows here as a tab still open.
4. **`stop`.** It disconnects the project's bridge and never closes Chrome.

   ```bash
   CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1 CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN> npx -y chrome-devtools-axi stop
   ```

- **When control fails,** retry once. Otherwise report the tabs left open, naming their URLs.
- **When there is no record,** because the bridge restarted or bootstrap never opened a tab,
  nothing is closed. Tabs on the project's URLs are reported for the user to close.
- **When bootstrap skipped its browser steps,** shutdown skips its own and starts no bridge.

## When the bridge cannot attach

The browser is detected at run time. An envelope whose `error` code is `BRIDGE_NOT_READY` means:

- the skill's browser steps are skipped;
- the skill reports the envelope's message and suggestions in full;
- a skipped browser never fails bootstrap or shutdown.

The causes the tool reports, each with its fix:

- **Chrome stable not running, or remote debugging off:** enable it at
  `chrome://inspect/#remote-debugging`.
- **Chromium or another channel running instead of Chrome stable:** start Chrome stable instead.
- **Chrome's connection prompt not accepted within the start-up timeout:** ask the user to accept
  the prompt, then run the step again.
- **A port collision** ("code 48"): set `CHROME_DEVTOOLS_AXI_PORT` for this session only.

## Reading the output

Every `chrome-devtools-axi` envelope is read whole. It is never piped through grep, head or tail,
narrowed with `jq`, or redirected away.
