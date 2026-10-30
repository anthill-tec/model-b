# CR-MDB-097 — Chrome-UI-Relay: a timed-out `newpage` leaves no tab, and heavy pages get a navigation timeout

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-30 from Crucible's request #1513, by the
user's ruling). Gap analysis, the spec and its pre-review (when a trigger applies) happen in order when this
CR starts.
**Type:** fix + feature (a shipped skill)
**Priority:** P2 — release 1.1.0, wave 3 (user 2026-10-30; board-authoritative: read `queue`).
**Depends on:** nothing on the board. Its second half waits for chrome-devtools-axi to pass a navigation
timeout through `newpage` (a third-party package): kunchenguid/chrome-devtools-axi#193, filed 2026-10-30.
**Labels:** skills, chrome-ui-relay, browser
**Design reference:** CR-MDB-061 (the relay skill: `newpage` only, delta-checked, protected tabs);
CR-MDB-076 (the bridge wait, never a retry); DN-multi-harness-deploy-model §D23; Crucible #1513;
kunchenguid/chrome-devtools-axi#193.

## Context

Crucible reported (#1513, 2026-10-30) that `chrome-devtools-axi newpage <url>` cannot open a heavy page: the
load gives up at a fixed 10 s (`Navigation timeout of 10000 ms exceeded`, `code: TIMEOUT`), and nothing lets a
caller wait longer. Its measurement: an 871 KB Lavish storyboard served in 0.03 s, which Chrome took more than
10 s to load; three `newpage` calls failed, one of them `--no-snapshot`; a 294 KB page opened.

Checked against the packages `npx -y chrome-devtools-axi` resolved on 2026-10-30 (chrome-devtools-axi 0.1.46,
chrome-devtools-mcp 1.12.0):

- chrome-devtools-mcp's `new_page` accepts a `timeout` in milliseconds (0 or less means its default) and
  passes it to the page's navigation and to its wait for the load's events;
- chrome-devtools-axi's `newpage` calls `new_page` with the URL and, under `--background`, `background` —
  never a `timeout`; no flag or environment variable sets one;
- on a navigation error, `new_page` closes the tab it opened, unless a dialog holds the load open or the close
  itself fails (it then lists the pages so the caller learns the tab's id), and re-throws the error.

The skill's § Open step 4 says the opposite: "A `newpage` that timed out still made its tab. Confirm it among
the new ids; never retry, since a retry duplicates it." Against the current server, a timed-out URL is simply
not open, and its absence from the new ids stops the open (step 3).

Until both halves land, Crucible's storyboard is opened by the user by hand, which makes it a user tab that the
relay never closes.

## Scope (seed)

1. **A timed-out `newpage` (now).** § Open step 4 states what the current server does: the tab is closed and
   the URL is not open; a tab that survived (a dialog, a failed close) is found among the new ids and is the
   skill's own. Whether the skill retries a timed-out URL once is decided at gap analysis against
   CR-MDB-076's never-retry rule, which is about the bridge wait, not a navigation timeout.
2. **A navigation timeout (when chrome-devtools-axi ships it).** The skill passes the timeout upstream offers
   (a `newpage` flag or an environment variable) on every `newpage`, with a value the skill states, so a heavy
   page opens. Whether a caller can name its own value for one URL — a project's services skill opening a
   heavy artifact at bootstrap — is decided at gap analysis.
3. **The shell timeout around each call** (§ The bridge wait: at least 150 s) stays above the bridge wait plus
   the navigation timeout.
4. **The version the skill assumes.** The skill runs `npx -y chrome-devtools-axi` unpinned; the spec decides
   whether the skill names the versions whose behaviour it states, so a later change is noticed.

## To measure at gap analysis

- Whether chrome-devtools-axi has shipped the timeout (#193: a `--timeout <ms>` flag on `newpage` and `open`,
  optionally an environment-variable default), its form and its default; the chrome-devtools-mcp
  version `npx` resolves then, and whether `new_page` still closes a timed-out tab.
- The tests that pin the relay skill's text (CR-MDB-061's and CR-MDB-076's gates) and the step-4 wording.
- CR-MDB-074 (the generated services skill, wave 3), which calls this skill: what it needs from the timeout.
- The re-score.
