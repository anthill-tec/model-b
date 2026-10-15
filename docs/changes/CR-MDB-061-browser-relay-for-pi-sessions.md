# CR-MDB-061 — Chrome-UI-Relay: a global skill for a frontend project's browser tabs

**Status:** PENDING — spec (gap analysis 2026-10-16).
**Type:** feature (a skill bundle)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** none (board-authoritative: read `queue`)
**Labels:** skills, browser, chrome-devtools-axi
**Design reference:** DN-multi-harness-deploy-model §D23 (browser handling is a global skill,
frontend projects only; its rulings of 2026-10-15 and 2026-10-16) and §D18 (skills name
capabilities). The project-local services skill that calls it is CR-MDB-074.

## Context

- **Who drives a browser.** A frontend project's orchestrator opens its dev pages and design
  reviews at bootstrap, reads and screenshots them, and closes them at shutdown. Crucible keeps
  this in a hand-written project skill. Its browser half is the same for every frontend project.
- **`chrome-devtools-axi` (0.1.42, measured 2026-10-16):**
  - It is not installed on `PATH`; it runs as `npx -y chrome-devtools-axi`.
  - **`CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1`** attaches to the user's running Chrome (144+, with
    remote debugging enabled at `chrome://inspect/#remote-debugging`) instead of launching one.
  - **`CHROME_DEVTOOLS_AXI_SESSION=<name>`** gives a session its own bridge process, port (derived
    from the name) and on-disk state. The default session uses port 9224.
  - Without `CHROME_DEVTOOLS_AXI_MCP_PATH`, the bridge runs `npx -y chrome-devtools-mcp@latest`.
  - Its verbs include `pages`, `newpage <url>`, `selectpage <id>`, `closepage <id>`, `eval <js>`
    and `stop`; `open <url>` navigates the selected tab.
- **The omp-era CDP relay** (`omp browser-relay`, or a wrapper of it) must not run under Pi. Its
  extension never connects, and it holds 9224, so a bridge there fails with `BRIDGE_NOT_READY`
  (exit 48).
- **The user-level `chrome-devtools-axi` skill** (third-party, outside Model B) says to navigate
  with `open <url>` and to pipe output through `grep`/`head`. For a project's tabs, this skill
  overrides both: `open` navigates a tab that may be the user's, and every envelope is read whole.
- **What exists in Model B:** no skill drives a browser, and the installer probes no browser.

## Scope

### §S1 — The bundle

- `skills-src/chrome-ui-relay/SKILL.md`, with frontmatter `name: chrome-ui-relay` and a
  description within Pi's limits. Its heading is "Chrome-UI-Relay".
- It is deployed with every Model B skill, scoped to no stack. Only a frontend project's services
  skill calls it.
- It states that it is not the omp-era CDP relay, and that the relay must never run under Pi.

### §S2 — Invocation and the session

Every call is `npx -y chrome-devtools-axi <verb>` with:

- `CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1`;
- `CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN>`, the value from the project's `.env`, so each project
  has its own bridge, and its `stop` ends only its own.

It never launches a browser, and never uses `open`.

### §S3 — Inputs

The caller gives three lists:

- the URLs to open;
- the URL patterns that count as the project's own;
- the protected patterns: tabs never selected, evaluated or closed, such as a production install's
  port.

### §S4 — Open

1. `pages`. Any URL to open that is already open is not opened again, which makes a session restart
   safe.
2. `newpage <url>` for each remaining URL. Never navigate an existing or selected tab.
3. `pages` again. Check the delta: one new tab per `newpage`, and no URL present before is lost. A
   flat count means stop and report.
4. A `newpage` that timed out still made its tab. Confirm it in the after list; never retry, since a
   retry duplicates it.
5. Confirm rendered text with `selectpage <id>` and `eval document.body.innerText.length`, never the
   load event, and never on a protected tab.

### §S5 — Close

1. `pages`, fresh. Pick the project's own tabs by its patterns, never by a remembered id, and never
   a protected tab.
2. `closepage` the highest id first.
3. `pages` again, to verify.
4. `stop`, which ends the project's own bridge only.

If control fails, retry once. Otherwise report the tabs left open, naming their URLs.

### §S6 — When the bridge cannot attach

The browser is detected at run time. A bridge that cannot attach means the skill's browser steps
are skipped. The skill reports the cause and its fix:

- no Chrome 144+, or remote debugging off: enable it at `chrome://inspect/#remote-debugging`;
- `BRIDGE_NOT_READY` (exit 48) with the omp-era relay holding the port: stop the relay.

A skipped browser never fails bootstrap or shutdown.

### §S7 — Reading the output

Every `chrome-devtools-axi` envelope is read whole: never piped through `grep`, `head` or `tail`,
narrowed with `jq`, or redirected away. A large result is written to a file and that file is read.

### §S8 — The docs

- **`AGENTS.md`'s skills row** names the new bundle, and the bundle count goes from 14 to 15.
- **`skills-src/README.md`** names it where it lists the bundles, if it does.
- **`pi-package/README.md`** is regenerated (`generator/build.py build`).

## Acceptance criteria

- [ ] **§S1.**
      - **Skill:** the bundle exists with valid frontmatter.
      - **Load:** Pi's loader loads it with no diagnostics.
      - **Deploy:** a sandboxed deploy places it under `.agents/skills/` for every stack selection,
        driven through `deploy.deploy_assets`.
      - **Wording:** a gate pins its not-the-omp-relay statement.
- [ ] **§S2–§S7.** One phrase gate per section pins each rule above. Each detector kind is proved both
      ways: it passes the shipped text and bites a sample without the rule. Two negative gates:
      - no `open <url>` call shown as a step;
      - no `chrome-devtools-axi` output shown piped or redirected.
- [ ] **§S8.** The `AGENTS.md` bundle row and count gates pass. Every gate that lists the bundles is
      migrated (marked `# MIGRATED at CR-MDB-061`). `pi-package/README.md` is regenerated, and
      `generator/build.py --check` is clean.
- [ ] **Runs.**
      - The suite is green through the client, with a real `HOME` and an empty one; the empty `HOME`
        stays empty.
      - No test runs `chrome-devtools-axi` or `npx`, or touches a browser.
      - The skill's text is the deliverable.
- [ ] **Live check, before merge.** With the user present, the orchestrator runs the skill's open and
      close once against the user's Chrome. It opens one harmless URL, checks the delta, closes the
      tab, and confirms none of the user's tabs moved. The result goes in the sign-off.

## Non-goals

- **The services skill, the dev server, Lavish and `PROJECT_TYPE`.** These are CR-MDB-074.
- **An installer requirement row for Chrome.**
- **Tab groups and a Chrome extension.**
- **Pinning `chrome-devtools-mcp`** (`CHROME_DEVTOOLS_AXI_MCP_PATH`), or installing
  `chrome-devtools-axi` on `PATH`.
- **Editing the third-party `chrome-devtools-axi` skill.**

## Cycle plan

1. **The skill and its docs (§S1–§S8).** Red-green.
2. **Verify.**
