# CR-MDB-061 — A browser relay for Pi sessions

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-10 into release 1.0.0, wave 2).
Gap analysis, the design record, the spec and its pre-review happen in order when this CR starts.
**Type:** feature (Pi package tool, Chrome extension, bootstrap/shutdown skills)
**Priority:** P1 — release 1.0.0, wave 2 (user ruling 2026-10-10: Model B owns it; 1.0.0).
**Depends on:** none (board-authoritative: read `queue`, not this line)
**Labels:** pi-package, browser, chrome-extension, skills, bootstrap, shutdown
**Design reference:** Crucible #1437 (Mainline - Crucible, 2026-10-10; Crucible's measured use and
its semi-auto workaround); CR-MDB-029 (the Model B Pi package `@anthill-tec/modelb-pi`);
DN-multi-harness-deploy-model §D18 (skills name capabilities).

## Context

Orchestrators drive a browser — Crucible's Mainline opens its dev board and Lavish review sessions at
bootstrap, then reads, clicks and screenshots them. Today each project improvises: an earlier omp
relay navigated the user's visible tab twice by adopting the active tab (2026-09-08); Crucible now
attaches `chrome-devtools-axi` to the user's Chrome (remote debugging, Chrome 144+), opens tabs only
with `newpage`, closes them with `closepage <id>` after a `pages` snapshot, and the user groups the
tabs by hand. The user rules the relay a Model B capability.

## User rulings (2026-10-10)

1. **Model B owns it** (confirming Crucible's "user direction" claim).
2. **Release 1.0.0,** wave 2.
3. **Shape: a tool in the Model B Pi package plus a small Chrome extension;** the bootstrap and
   shutdown skills call the tool.

## Scope (seed — the five requirements, #1437)

1. **Open only its own tabs** in the user's running Chrome — open always *creates* a tab, never
   navigates an existing one; checked by delta (+N tabs, zero user URLs lost).
2. **Never touch the user's tabs** — no adoption of the active tab, no navigation, no close.
3. **Its tabs live in a named tab group, "Pi".** CDP has no tab-group API, so a Chrome-extension half
   (`chrome.tabGroups`) does the grouping; the group title is configuration, not hard-coded.
4. **Close exactly its own tabs at shutdown,** by URL, with the same delta check.
5. **Survive a session restart:** re-attach to, or re-open, the project's tabs without duplicates.
6. **The skills call it:** bootstrap opens the project's declared tabs, shutdown closes them; the tab
   list is a per-project declaration (where — `.env`, `AGENTS.md` or a project file — is a
   gap-analysis decision).

## To measure at gap analysis

- **The transport:** whether the tool drives Chrome through `chrome-devtools-axi` (already installed;
  `newpage`/`closepage`/`pages`) or CDP directly, and how the extension and the tool talk (native
  messaging, the extension's own CDP target, or a local channel).
- **Shipping a Chrome extension:** a new artifact family for Model B — how it is packaged and
  installed (unpacked load vs store), which installer verdict/preflight reports it, and its
  permissions.
- **Session identity:** how a session's tabs are told apart from another session's and from the
  user's across a restart.
- **Score:** seeded at 13 — the cap; split at gap analysis if it measures larger (e.g. the
  extension and the skills hooks as separate CRs).
