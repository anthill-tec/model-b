---
name: code-health
description: Take a code-health snapshot of a Cargo workspace, RATIFY maintenance/cull CR completion, and produce a summarized health report for the user. Runs the Model-B health tool trio (rust-crate-map.py + rust-dead-scan.py via the rust-code-health.py orchestrator), pins the snapshot to the current git commit, and summarizes trends, deltas, ledger lifecycle, and ratification verdicts. Use when the user asks for a "code health report", "health snapshot", "how healthy is the codebase", "what's dead/unwired", "cull progress", to "ratify/validate a cull or maintenance CR", or at the defined snapshot points — audit baseline, PRE (slice dispatch) and POST (after merge) of every cull run, wave boundaries, and ad-hoc decision support. Snapshot-taking AND maintenance ratification/validation are the MAINLINE orchestrator's functions EXCLUSIVELY — never a track's.
---

# Code-Health Snapshot & Report

Produce a git-pinned code-health snapshot of the current Rust workspace and a
summarized report for the USER. Works on any Cargo workspace (all tools are
generic; project specifics live in the repo's `docs/research/assets/` configs).

## Ownership & when

- **Mainline-owned.** Tracks never take snapshots; Mainline brackets each cull
  slice (PRE at dispatch, POST after merge, on the integration tree) and runs
  ad-hoc snapshots for decision support.
- Defined points: exercise `baseline` · `pre`/`post` of EVERY cull run (paired
  by `--slice <CR-id>`) · wave boundaries · `adhoc` anytime the user needs a
  picture.
- Snapshots pin a git commit. If the tool warns the tree is DIRTY, prefer
  committing first — a snapshot at a dirty tree is recorded as suspect.

## Tools (Model-B toolset, `~/.agents/scripts/`)

```bash
# take a snapshot (immutable dir under docs/research/assets/health/)
python3 ~/.agents/scripts/rust-code-health.py snapshot --phase {baseline|pre|post|adhoc} [--slice CR-XXX]

# query the dataset
python3 ~/.agents/scripts/rust-code-health.py query trend            # totals across all snapshots
python3 ~/.agents/scripts/rust-code-health.py query crate <pkg>      # one crate's history + open findings
python3 ~/.agents/scripts/rust-code-health.py query delta <a> <b>    # any two snapshots
python3 ~/.agents/scripts/rust-code-health.py query ledger [FILTER]  # machine ledger (status/verdict/crate filter)

# heavier, on demand (lift-lint BUILDS the workspace; minutes):
python3 ~/.agents/scripts/rust-dead-scan.py inventory pub-scan deps reconcile boundaries hot-path lift-lint
```

### Ledger lifecycle (maintenance CRs) — mirrored by hand at each board event

The ledger does not mirror the board by itself: Mainline runs each sync at the
named board event. Crucible clients live at the path in Crucible's client
manifest (`~/.crucible/clients/` by default).

```bash
# filing, two steps: file the CR on the board, then stamp its findings
python3 ~/.crucible/clients/rust-crucible.py cr-plan --cr <CR-id> --title "<brief>" --release <rel> --wave <n> --agent <orchestrator-id>
python3 ~/.agents/scripts/rust-code-health.py ledger assign --slice <CR-id> --ids F-1,DS-...

# transition: when the CR's first cycle activates on the board
python3 ~/.agents/scripts/rust-code-health.py ledger sync --slice <CR-id> --db-state IN_PROGRESS

# transition: after the merge is closed with ~/.crucible/clients/rust-crucible.py cr-close --commit <merge sha>
python3 ~/.agents/scripts/rust-code-health.py ledger sync --slice <CR-id> --db-state COMPLETED --commit <merge sha>
# an aborted or superseded CR: --db-state ABORTED / --db-state SUPERSEDED, likewise
```

- The no-argument full `ledger sync` only works where a legacy ChangeSet DB
  exists; elsewhere it skips — always pass `--slice` and `--db-state`.
- The ledger is multi-domain: `--domain cull|temporal|<name>` selects the
  file (`cull` is the default; `<name>` writes `<name>-audit-ledger.jsonl`).

Dataset (all git-committed, lean-ctx-indexed, RAG-able):
`docs/research/assets/` — living `crate_map_baseline.{json,md}`, rendered map
SVG, `dead_scan_report.{json,md}`, the cull domain's machine ledger
`audit-cull-ledger.jsonl` (schema v2 — joins crate→module→site, snapshot dirs,
git commits, register, ChangeSet-DB slice; `status` lifecycle `PROPOSED →
APPROVED → IN_PROGRESS → COMPLETED`, terminal `STRUCK`), retention register
`dead_code_register.toml`, and the immutable
`health/<date>_<sha>_<phase>[_<slice>]/` archive + `health/index.json`. Ledger
`first_seen`/`resolved_in` point at the snapshot directories carrying the
finding's related assets.

## Procedure

1. `git status` — note cleanliness; commit or flag before snapshotting.
2. Run the snapshot for the requested phase (or just queries if the user only
   wants a read of existing data).
3. Read `snapshot.json` totals + (post) `health_delta.md`; `query trend` for
   the series; `query ledger OPEN` for outstanding findings.
4. Commit the new snapshot dir + refreshed living artifacts on the integration
   branch (`docs(health): <phase> snapshot @ <sha>`).
5. Produce the report (below). Numbers come from the tools — never estimated.

## Report template (adapt, keep ≤ ~20 lines)

- **Headline** — snapshot id, git sha/branch, phase; one-sentence verdict
  (improving / regressing / steady vs last snapshot).
- **Size** — prod LOC, test LOC, test:prod ratio, crate count (+ deltas).
- **Dead-code posture** — bare `allow(dead_code)` (target 0), `expect` marks
  vs register (reconcile status), dead-pub / test-coat candidate counts.
- **Deps/features** — unused-dep candidates (note verify-first caveats:
  feature-gated + macro-only deps false-positive).
- **Ledger** — counts by lifecycle status (PROPOSED/APPROVED/IN_PROGRESS/COMPLETED) and verdict; anything awaiting user decision.
- **Ratification (post runs)** — the NOT-RATIFIED list from `health_delta.md`; any NOT-RATIFIED finding means the slice claimed completion falsely — block sign-off.
- **Trend** — 2–4 lines from `query trend` (or the delta table on post runs).
- **Recommended next actions** — concrete, decision-ready.

## Ratify a maintenance CR (MAINLINE-ONLY — the cull's quality gate)

Ratification/validation of maintenance work is Mainline's function exclusively.
It runs after the CR's `cr-close` and the COMPLETED ledger sync that follows it
(`ledger sync --slice <CR-id> --db-state COMPLETED --commit <merge sha>`):

1. `python3 ~/.agents/scripts/rust-code-health.py snapshot --phase post --slice <CR-id>`
   on the integration tree — the fresh scan is compared against the CR's
   COMPLETED ledger rows.
2. Read `health_delta.md`: every finding gets ✅ RATIFIED (stable id gone from
   the scan / crate gone from the map) · 🛑 NOT-RATIFIED (still present —
   the slice claimed completion falsely) · ❓ MANUAL (seed/manual finding —
   Mainline verifies by hand, e.g. with lean-ctx, then records).
3. **Any NOT-RATIFIED ⇒ block sign-off** — the CR is not done regardless of
   its board state; dispatch the gap back to the owning track.
4. Resolve every ❓ MANUAL before declaring the slice ratified; then report
   the ratified delta to the user. The ledger rows now carry
   `ratified`/`ratified_in`/`resolved_in` as the permanent evidence.

## Caveats to always carry into the report

- pub-scan is regex-based v1: collisions + common names are SKIPPED not
  cleared; macro-generated references are invisible — verify with lean-ctx
  before any CULL verdict.
- Coverage masks deadness (self-tested dead code shows covered) — never cite
  coverage as liveness evidence.
- `testing = []` marker features are enabled externally by the test harness —
  protected, never "unused".
