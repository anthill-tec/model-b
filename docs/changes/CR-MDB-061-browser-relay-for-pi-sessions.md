# CR-MDB-061 — A global Chrome-UI skill for frontend projects

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-10 into release 1.0.0, wave 2;
re-scoped 2026-10-15). Gap analysis, the design record, the spec and its pre-review happen in order
when this CR starts.
**Type:** feature (a skill bundle)
**Priority:** P1 — release 1.0.0, wave 2. Only where Chrome or Chromium is available.
**Depends on:** none (board-authoritative: read `queue`, not this line)
**Labels:** skills, browser, chrome-devtools-axi
**Design reference:** DN-multi-harness-deploy-model §D23 (browser handling is a global skill,
frontend projects only) and §D18 (skills name capabilities); Crucible #1437, #1456–#1458. The
project-local services skill and the project type are CR-MDB-074.

## Context

Frontend projects' orchestrators drive a browser: Crucible's Mainline opens its dev board and
Lavish review sessions at bootstrap, then reads, clicks and screenshots them, and closes them at
shutdown. Crucible keeps this in a hand-written project skill. The browser handling in it is the
same for every frontend project; its services are not.

- **The route that works under Pi:** `chrome-devtools-axi` with `CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1`
  attaches to the user's already-running Chrome through its bridge on `:9224`, and never starts a
  Chrome of its own.
- **The route that must not run under Pi:** the omp-era CDP relay (`omp browser-relay`, or a wrapper
  of it). Its extension never connects, and it holds `:9224`, so the bridge then fails with
  `BRIDGE_NOT_READY` (exit 48).

## Scope (seed)

1. **The skill bundle** in `skills-src/`, deployed with the others. It takes:
   - the URLs to open;
   - the URL patterns that count as its own at close;
   - the protected patterns (tabs never selected, evaluated or closed, such as a production
     install's port).
2. **Route:** `chrome-devtools-axi` with `CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1`, through its bridge on
   `:9224`; never a cold-started Chrome. The skill states that the omp-era relay must not run under
   Pi, and why.
3. **Open:**
   - Run `pages` before, `newpage <url>` per tab, and `pages` after.
   - Only `newpage`: never navigate an existing or selected tab, which may be the user's.
   - Check by delta: +N tabs and zero user URLs lost. A flat count means stop.
   - A `newpage` that timed out still made its tab: confirm it in the after list, never retry
     (a retry duplicates it).
   - Confirm rendered text with `selectpage` plus `eval document.body.innerText.length`, never the
     load event.
4. **Close:**
   - Pick the skill's own tabs by URL from a fresh `pages` list, never by a remembered id.
   - Close the highest id first, then list again to verify, then `chrome-devtools-axi stop`.
   - If control fails, retry once. Otherwise report the tabs left open, naming their URLs.
5. **Only where Chrome or Chromium is available:**
   - The installer detects the browser and records a verdict like any other tool (PRD D10).
   - Where none is found, the skill reports the browser steps as skipped.
   - An absent browser is not a preflight failure.

## To measure at gap analysis

- The installed `chrome-devtools-axi` surface (`--help`; the bridge and its port; `pages`,
  `newpage`, `selectpage`, `eval`, `closepage`, `stop`) and the exit codes it reports.
- Session identity across a restart: re-attaching to, or re-opening, the project's tabs without
  duplicates. Do URL patterns suffice?
- Which existing skills name the browser (`bootstrap`, `shutdown`, the `chrome-devtools-axi` skill
  itself) and what they say.
- The re-score: seeded at 13 when it carried an extension. The skill alone measures smaller.
