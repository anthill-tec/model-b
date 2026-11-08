# CR-MDB-101 — A `sol-pi-status` skill reports SoL-Pi's state for the user

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-11-08 by the user's ruling, relayed as
SoL-Pi #1556). Gap analysis, the spec and its pre-review happen in order when this CR starts.
**Type:** feature (a skill)
**Priority:** P2 — release 1.1.0, wave 3, after CR-MDB-098 (user 2026-11-08; board-authoritative: read
`queue`).
**Depends on:** CR-MDB-098 (the `sol-pi` requirement row and the per-project setup it reports on); off the
board, SoL-Pi 0.1.0 with CR-SLP-008 (`install`'s `verify`).
**Labels:** skills, sol-pi
**Design reference:** DN-multi-harness-deploy-model §D28 (Model B reaches SoL-Pi through its installed
entry point, never installs it); CR-MDB-098 § SoL-Pi's contract (#1534, corrected by #1554).

## Context

The user ruled (SoL-Pi #1556, 2026-11-08) that a user-facing "SoL-Pi status" belongs in Model B as a skill;
SoL-Pi registers no status command. What it can read, from SoL-Pi 0.1.0's installed surface:

- `sol-pi-axi` with no arguments: the home view — `version`, `extension` (`state` absent or registered,
  `source`, a warning when it is not the tool's version), `project` and `agentConfig` (`path`, `state`
  absent, valid or invalid, `features`, `reducer`);
- `sol-pi-axi install`: registers or re-verifies; its `verify` key (CR-SLP-008) reports whether a running
  Pi loads SoL-Pi cleanly (`ok`, `exit`, `errors[{extensionPath, event, error}]`), starting Pi offline in
  RPC mode (about 0.25 s);
- `sol-pi-axi setup <dir>`: the per-project file;
- `sol-pi-axi verify` (CR-SLP-008, SoL-Pi #1558): the same load check, read-only — it registers nothing
  and writes no SoL-Pi file (Pi itself may create `auth.json` and `models-store.json` in the agent
  directory on its first start). Envelope `verb: verify`, the same `verify` key; exit 1 when SoL-Pi is not
  registered, is filtered off, its package is missing, Pi cannot start it, or it raises an extension
  error; another extension's handler error is a warning.

## Scope (seed)

1. **A `sol-pi-status` skill in `skills-src/`,** deployed like the others: it runs the home view, reads the
   envelope whole, and reports to the user in plain words — the tool's version, whether the extension is
   registered and at which version, the project's and the user-wide configuration's state, the features on
   and the reducer — with SoL-Pi's own remediation for each fault.
2. **Read-only.** A status never installs or registers (§D28): the skill checks the load with
   `sol-pi-axi verify`, never `install`, and reports each `errors[]` entry; `sol-pi-axi install` is named as
   the user's step only when SoL-Pi is not registered. The skill states that Pi may create `auth.json` and
   `models-store.json` on its first start.
3. **The project file:** an absent or invalid project configuration names `sol-pi-axi setup <dir>` (or
   `modelb-axi agents`, once CR-MDB-098 calls it) as the fix.

## To measure at gap analysis

- SoL-Pi 0.1.0's released home view and `verify` envelope against this seed.
- The skill-bundle gates a new skill meets (frontmatter, the harness-neutral guard, the deploy roster,
  `archive/mapping.md`), and the stacks it renders for (every project on Pi).
- The re-score (3 points filed).
