# CR-MDB-061 — Chrome-UI-Relay: a global skill for a frontend project's browser tabs

**Status:** PENDING — spec (gap analysis and pre-review 2026-10-16).
**Type:** feature (a skill bundle)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** none (board-authoritative: read `queue`)
**Labels:** skills, browser, chrome-devtools-axi
**Design reference:** DN-multi-harness-deploy-model §D23 (browser handling is a global skill,
frontend projects only; its rulings of 2026-10-15 and 2026-10-16) and §D18 (skills name
capabilities). The project-local services skill that calls it is CR-MDB-074.

## Context

**Who drives a browser.** A frontend project's orchestrator:

- opens its dev pages and design reviews at bootstrap;
- reads and screenshots them;
- closes them at shutdown.

Crucible keeps this in a hand-written project skill. Its browser half is the same for every frontend
project.

**`chrome-devtools-axi`** (0.1.42; chrome-devtools-mcp 1.11.0 behind its bridge; measured 2026-10-16):

- **How it runs.** It is not installed on `PATH`; it runs as `npx -y chrome-devtools-axi`.
- **`CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1`.** The tool attaches to the user's running Chrome stable
  (144+, remote debugging enabled at `chrome://inspect/#remote-debugging`) instead of launching one.
  - Chrome asks the user to accept each new connection: every bridge, and every bridge restart.
  - `stop` disconnects the bridge. It closes only a Chrome the tool launched itself, never the
    user's.
- **`CHROME_DEVTOOLS_AXI_SESSION=<name>`** gives a session its own bridge process, state and port.
  - The port is hashed from the name into 9225–10224, unless `CHROME_DEVTOOLS_AXI_PORT` overrides it.
  - Names must match `[A-Za-z0-9._-]{1,64}`.
  - Only the name `default` uses 9224.
- **Any verb starts a bridge if none is running.**
- **`pages`** lists every tab as `pages[N]{id,url,selected}`. Ids are counted per bridge and reset
  when a bridge restarts.
- **`newpage <url>`** prints the new page's title, URL and snapshot, but not its id.
- **`closepage` on the last open tab** does nothing and says so.
- **A bridge that cannot start or attach** is reported in the envelope's `error` with code
  `BRIDGE_NOT_READY`, its message naming the cause and the fix. The command exits 1.
  - A port collision says "exited with code 48".
  - Other causes the tool reports: Chrome not running, remote debugging off, a wrong channel ("Could
    not find DevToolsActivePort") and the 30 s start-up timeout.
- **`open <url>`** navigates the selected tab.

**The omp-era CDP relay** must not run under Pi. It holds 9224, the default session's port. A named
session never binds 9224.

**The user-level `chrome-devtools-axi` skill** (third-party, outside Model B) says to navigate with
`open <url>` and to pipe output through grep or head. For a project's tabs, this skill overrides both.

**What exists in Model B:** no skill drives a browser, and the installer probes no browser.

## Scope

### §S1 — The bundle

- **The file.** `skills-src/chrome-ui-relay/SKILL.md`, with frontmatter `name: chrome-ui-relay` and a
  description within Pi's limits. Its heading is "Chrome-UI-Relay".
- **Deployment.** It is deployed with every Model B skill and scoped to no stack. Only a frontend
  project's services skill calls it.
- **The relay.** It states that it is not the omp-era CDP relay, and that the relay must never run
  under Pi.
- **Its text, as for every Model B-owned skill (§D18):**
  - it names no Pi tool and no tool wrapper;
  - it writes grep, head and tail as plain words, not code spans;
  - its example URLs are placeholders (`<dev-url>`), never a host and port.

### §S2 — Invocation and the session

Every call is `npx -y chrome-devtools-axi <verb>` with:

- `CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1`;
- `CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN>`, the value from the project's `.env`. Each project has
  its own bridge, and its `stop` ends only its own.

It never launches a browser and never uses `open`. `<PROJECT_TOKEN>`, `<dev-url>` and `<id>` are
values to substitute, never typed literally. `pages` prints its tabs as `pages[N]{id,url,selected}`,
one row per tab.

When `PROJECT_TOKEN` is absent, not of the form `[A-Za-z0-9._-]{1,64}`, or `default`:

- the browser steps are skipped;
- the skill reports "no valid session name: set `PROJECT_TOKEN` in `.env`";
- it never falls back to the default session.

### §S3 — Inputs

The caller gives three lists:

- the URLs to open;
- the URL patterns the project's tabs match;
- the protected patterns: tabs never selected, evaluated or closed, such as a production install's
  port.

**URLs are compared by pattern.** Chrome normalises the URLs it shows (a trailing slash, a
redirect), so a tab "shows" a URL to open when its URL matches the project pattern the caller gives
for that URL, never by exact string.

**Protected wins everywhere.** A protected tab is never counted as already open, never chosen and
never closed. A URL to open that matches a protected pattern is a caller error: it is reported and
skipped.

### §S4 — Open

1. **`pages`.** Keep its id set as "before".
   - A URL to open that already shows in a tab is not opened again.
   - That tab is the user's or a previous bridge's. It is never selected, evaluated or closed.
2. **`newpage <url>`** for each remaining URL. Never navigate an existing or selected tab.
3. **`pages` again.** The new tabs are the "after" ids minus the "before" ids.
   - Every URL opened shows among the new ids.
   - Every "before" id is still there.
   - Otherwise, stop and report.
   - The new tabs are the skill's own for this bridge. It keeps that record as **(id, URL) pairs**,
     held in the caller's working context; a restarted agent session has no record.
4. **A `newpage` that timed out still made its tab.** Confirm it among the new ids; never retry,
   since a retry duplicates it.
5. **Rendered text** is confirmed with `selectpage <id>` and `eval document.body.innerText.length` on
   the skill's own tabs only, never the load event.

### §S5 — Close

1. **`pages`, fresh.** The tabs to close are those in the skill's record whose id still shows with
   its recorded URL, and are not protected.
   - If any recorded id shows with a different URL, or is gone while its URL shows on another id, the
     bridge has restarted silently (the tool never reports a respawn): close nothing, and report the
     tabs on the project's URLs for the user to close.
2. **`closepage`** each of them.
3. **`pages` again,** to verify. A last-tab no-op shows here as a tab still open.
4. **`stop`.** It disconnects the project's bridge and never closes Chrome.

- **When control fails,** retry once. Otherwise report the tabs left open, naming their URLs.
- **When there is no record,** because the bridge restarted or bootstrap never opened a tab, nothing
  is closed. Tabs on the project's URLs are reported for the user to close.
- **When bootstrap skipped its browser steps,** shutdown skips its own and starts no bridge.

### §S6 — When the bridge cannot attach

The browser is detected at run time. An envelope carrying `code: BRIDGE_NOT_READY` means:

- the skill's browser steps are skipped;
- the skill reports the envelope's `error` line and every `help` line in full; the suggestions are
  reported, never run (one of them suggests `open`);
- a skipped browser never fails bootstrap or shutdown.

The skill names the causes the tool reports, each with its fix:

- **Chrome stable not running, or remote debugging off:** enable it at
  `chrome://inspect/#remote-debugging`.
- **Chromium or another channel running instead of Chrome stable.**
- **Chrome's connection prompt not accepted within the start-up timeout.**
- **A port collision** ("code 48"): set `CHROME_DEVTOOLS_AXI_PORT` for this session only.
- **`npx` failing to fetch `chrome-devtools-mcp`** on a cold start: report the tool's own message and
  fix.

### §S7 — Reading the output

Every `chrome-devtools-axi` envelope is read whole. It is never piped through grep, head or tail,
narrowed with `jq`, or redirected away.

### §S8 — The docs and the pins

- **`AGENTS.md`'s `skills-src/` row:**
  - 15 bundles (it says 14);
  - `chrome-ui-relay` in its Model-B-owned list, which grows from 8 to 9 names.
- **The pins that list or count the bundles** move with it:
  - `test_installer_assets` (`MODELB_OWNED_BUNDLE_NAMES`);
  - `test_orchestrator_rule_triage` (its owned-bundle set);
  - `test_ide_overlay_retirement` (the bundle count);
  - `test_worktree_layout_and_bundles` (`EXPECTED_BUNDLE_COUNT`, and the owned names in the
    `AGENTS.md` row);
  - `test_code_health_skill` (the bundle count).

## Acceptance criteria

- [ ] **§S1.**
      - The bundle exists with valid frontmatter.
      - Pi's loader loads it with no diagnostics (the existing `PiSkillLoaderOracleTest` covers every
        bundle).
      - A deploy places it with every stack selection (the existing deploy tests, through
        `MODELB_OWNED_BUNDLE_NAMES`).
      - It passes the suite's gates over every Model B-owned skill: the tool-name count, the project
        name, the host and port.
      - A gate pins its not-the-omp-relay statement.
- [ ] **§S2–§S7.** One phrase gate per rule, each pinned on the skill's text:
      - **§S2:** auto-connect and the per-project session; never launches a browser; never `open`;
        the token rule and its report; no default-session fallback.
      - **§S3:** the three inputs; protected wins; a protected URL to open is reported.
      - **§S4:**
        - "before" set;
        - an already-open URL not reopened and never touched;
        - `newpage` only;
        - id-set delta;
        - the record;
        - timeout confirmed, never retried;
        - rendered text on the skill's own tabs.
      - **§S5:**
        - the record ∩ still shown, not protected;
        - verify;
        - `stop` disconnects and never closes Chrome;
        - retry once, then report;
        - no record → close nothing and report;
        - a skipped bootstrap → no shutdown bridge.
      - **§S6:** keyed on `BRIDGE_NOT_READY`; the message reported in full; never fails bootstrap or
        shutdown; the four causes and fixes.
      - **§S7:** the whole-envelope rule.

      The fix cycle adds rules for: the (id, URL) record and its home; close on an id+URL match
      only; any mismatch closes nothing and reports; URLs compared by pattern; reading ids from
      `pages`; placeholders substituted; `code: BRIDGE_NOT_READY`, the `error` and `help` lines in
      full, suggestions never run; the `npx` fetch cause. Phrases are anchored so a reversed
      wording ("not in the record", "never reports … in full") fails.

      Each detector kind is proved both ways. Two negative gates:
      - **no `open` shown as a step:** a code span or fenced line matching
        `chrome-devtools-axi\s+open\b` outside a prohibition clause, using `PROHIBITION` and
        `_CLAUSE_END` from `tests/test_raw_runner_guard.py`;
      - **no `chrome-devtools-axi` output shown piped or redirected:** any single `|` after the
        tool (not `||`), a `$(…)` capture, and any redirect, with or without a space before it;
        fenced lines continued with `\` are joined before they are judged. The same joining
        applies to the `open` gate.
- [ ] **§S8.** The `AGENTS.md` row and every pin above are migrated, each marked
      `# MIGRATED at CR-MDB-061 (§S8)`, and `generator/build.py --check` is clean.
- [ ] **Runs.**
      - The suite is green through the client, with a real `HOME` and an empty one; the empty `HOME`
        stays empty.
      - No test runs `chrome-devtools-axi` or `npx`, or touches a browser.
      - The new tests carry no `\uXXXX` escapes.
- [ ] **Live check, before merge.** With the user present (expect Chrome's connection prompt), the
      orchestrator runs the skill's open and close once on the user's Chrome, under Model B's own
      session.
      - It opens `https://example.com/?chrome-ui-relay-check=<nonce>`.
      - It passes when the user's (id, url) set is identical before and after, one id is added and
        then removed, and `stop` is ok.
      - The full before and after `pages` envelopes go in the sign-off.

## Non-goals

- **The services skill, the dev server, Lavish and `PROJECT_TYPE`.** These are CR-MDB-074.
- **An installer requirement row for Chrome.**
- **Tab groups and a Chrome extension.**
- **Pinning or installing the tools.** `chrome-devtools-mcp` is not pinned
  (`CHROME_DEVTOOLS_AXI_MCP_PATH`), and `chrome-devtools-axi` is not installed on `PATH`.
- **Editing the third-party `chrome-devtools-axi` skill.**
- **Proving that two projects' bridges attach to one Chrome at once.** The tool allows it. The live
  check runs one session.

## Cycle plan

1. **The skill and its pins (§S1–§S8).** Red-green.
2. **Verify**, with the live check run inside it before the pre-merge gate.
