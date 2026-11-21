# CR-MDB-108 — Crucible 0.4.0 doc-sync: the skills, stack files and hooks follow the released clients

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-11-21 by the user's rulings, on
Crucible's #1622, the 0.4.0 release notes; widened the same day by the user's rulings on Crucible's #1520
and #1522). Gap analysis and the spec happen in order when this CR starts. Pre-review:
due (13 points; it changes hooks, and the user's rulings were needed).
**Type:** doc-sync (the released Crucible client surface) and a test-suite fix (A3)
**Priority:** P1 — release 1.0.0, wave 2, right after CR-MDB-095 (board-authoritative: read `queue`).
**Depends on:** none. Crucible 0.4.0 is released and installed (2026-11-21).
**Labels:** crucible, doc-sync, skills, stacks, hooks
**Design reference:** PRD-model-b-rationalization D7 (Crucible V2 client contract); DN-multi-harness-deploy-model
§D26 (test scope); Crucible's `CHANGELOG.md` § `[0.4.0] - 2026-11-21` (Upgrading, Changed, Stack declaration
changes) and its requests #1613 (CR-CRU-252), #1615 (CR-CRU-222), #1619 (CR-CRU-259..264) and #1622.

## Context

Crucible 0.4.0 changed the client surface that Model B's skills, stack files, templates and hooks describe.
The user ruled (2026-11-13, 2026-11-20, 2026-11-21) that one doc-sync CR carries it, filed once the release
notes and changelog were in hand. A smoke run of Model B's own suite on the 0.4.0 client passed (83/0).

## Scope (seed)

1. **No board, no run (#1619 A1, CR-CRU-259, #1613 CR-CRU-252).** The crucible skill's § Connection, the
   briefs and the DN (~L832) say a client reaches the board its project's or its install's `crucible.toml`
   declares in `[client] url`, and refuses when neither declares one; never a port. Model B's own
   `crucible.toml` comment ("keeps Model B on the shipped default board") is re-worded: the shipped file
   declares no board. `tests/test_crucible_project_config.py`'s `CONNECTION_STATEMENTS` and its GOOD sample
   move with the text. The skill's "never run a client from a checkout of the Crucible project" rule
   (L110–114; Crucible #1522) loses its premise, since the shipped `crucible.toml` declares no board: it
   becomes "a project runs Crucible's installed clients", which Crucible's own repository, running its own
   checkout against its own board, does not contradict (user, 2026-11-21).
2. **The python gate's tier dispatch (#1619 A3, CR-CRU-261).** The python stack's material states that the
   gate runs a `python3 -m unittest discover -s <dir>/<tier>` script as that tier's verb, without `-t`, so a
   test module imports the project's own test package and never puts its own directory on `sys.path`.
   **Model B's own suite conforms (user, 2026-11-21):** the eight modules that edit `sys.path` today
   (`test_ambient_manifest_discovery`, `test_ambient_status_contract`, `test_hooks`, `test_installer_assets`,
   `test_suite_hermeticity`, `test_tooling_detachment`, `test_toon_codec`, `test_worktree_flow_dbless`) are
   rewritten to import what they need without it.
3. **The bun stack's declaration (CR-CRU-222, CR-CRU-265, the notes' bun section).** The
   `block-direct-bun-test` hook (docstring ~L70–72, REASON ~L138) and the bun templates name the
   `crucible.targets` entry's `"test": true` marker and its `junit`, never `crucible.testScript` or
   `crucible.reportPath`; `regression` runs the marked entry, else `bun test`; `--tests` entries are written
   relative to the package directory. `tests/test_client_path_anchoring.py`'s runner-line checks move with them.
4. **The rust stack's gate envelope.** `stage: "lint"` (was `clippy`), `lint-gate-abort`, `--skip-lint`
   (`--skip-clippy` its alias); every run streams through nextest 0.9.130 or later; `--ignore-run-fail` retired.
5. **Every stack's verbs, where the skill names them.** The `lint` verb and the gate's lint stage
   (`lint-not-declared` when a project declares none); `regression` measures coverage only with `--coverage`;
   `runs`/`run`; `pre-merge-gate --suites`; `release-notes --release`; the python `[python] runner`; the
   coverage envelope's least-covered files (CR-CRU-193's field names).
6. **xmlrunner has left the python client (Crucible #1520, CR-CRU-224, user 2026-11-21).** A unittest run
   streams its results through the client's own runner, with no `TEST-*.xml` and no `ingest junit:` line.
   The bootstrap skill's Step 0.7 checks `import coverage` only, its remediation installs `coverage` only;
   the python stack file and its templates stop naming xmlrunner, `TEST-*.xml` and JUnit; `AGENTS.md`'s
   interpreter and JUnit lines follow.
7. **The guards move with the text,** each named at gap analysis.

## Non-goals

- **Model B's own gate step 1 (`ruff check`) stays a separate step** (user, 2026-11-21): no `[lint]` table in
  Model B's `crucible.toml`.
- **Left to their own CRs:** `--cycle` on every run (CR-MDB-083, #1619 A2); the arduino `CRUCIBLE_STREAM`
  make contract (CR-MDB-084); the go stack (CR-MDB-080); `project-create` (CR-MDB-106); the per-modality test
  tools (CR-MDB-099); the tiers, the pyramid and the orchestrator rules (CR-MDB-109).

## To measure at gap analysis

- Every Model B surface naming each changed verb, key or field (`git grep`), against the installed 0.4.0
  clients' `--help` and `crucible-declaration.schema.json` (version 3).
- CR-CRU-192 (coverage config read from the project; stale data erased by the client): whether `AGENTS.md`'s
  `--cov-source` and the gate's hand-erase step can go.
- CR-CRU-189 (passing subtests counted): the suite's count under 0.4.0, for the `AGENTS.md` baselines.
- The score (13 points filed) and the behaviour units.
