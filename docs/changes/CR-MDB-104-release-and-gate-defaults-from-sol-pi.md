# CR-MDB-104 — Release and gate defaults from SoL-Pi 0.1.0's release

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-11-11 by the user's ruling, from the
generator notes in SoL-Pi #1599). Gap analysis and the spec happen in order when this CR starts. Pre-review: none
(5 points; no contract, hook or other project's surface).
**Type:** defect (three defaults that failed a governed project's release)
**Priority:** P1 — release 1.0.0, wave 2 (user 2026-11-11; board-authoritative: read `queue`).
**Depends on:** none on the board.
**Labels:** release-workflow, gate, release-check, scaffold
**Design reference:** CR-MDB-068/070 (the release workflow rendered from `workflows-src/`); CR-MDB-071 §S5
(`release-check` reads GitHub through the origin remote); the scaffolded `crucible.toml` `[gate] skip`
(`modelb_axi/scaffold.py`) and `AGENTS.md`'s wave-boundary gate rule.

## Context

SoL-Pi released 0.1.0 on 2026-11-11 under Model B's generated workflow and gate. Three defaults failed it
(#1599); SoL-Pi worked round each by hand:

1. **The rendered `test-python` job installs nothing.** `workflows-src/release/test-python.yml` sets up
   Python 3.14 and uv, then runs `python -m unittest discover -s tests -t .`. A project whose suite needs
   its own package and its development dependencies installed fails; SoL-Pi hand-edited the job to
   `pip install -e ".[dev]"`.
2. **`[gate] skip = ["ci"]` leaves no-mistakes' `pr` and `push` steps on.** On a git-flow project the gate
   would open a PR release→main and push the release branch, which fires the release rehearsal. SoL-Pi runs
   the gate with `--skip push,pr,ci` by the user's ruling. Model B scaffolds `skip = ["ci"]`, and its own
   `crucible.toml` and `AGENTS.md` (§ Workflow Rules, the wave-boundary gate) say the same.
3. **`modelb-axi release-check` reports every GitHub item `unknown`** when origin uses an SSH host alias
   (`git@github.com-<alias>:owner/repo.git`): `_origin_repository` matches `_GITHUB_ORIGIN` only, and answers
   "the origin remote is not on github.com; GitHub not read".

## Scope (seed)

1. **`test-python` installs the project before the tests,** editable with its development extra where the
   project declares one. How the job learns the extra's name (or whether it has one), and whether uv or pip
   installs it, is measured at gap analysis.
2. **The scaffolded `[gate] skip` covers `push` and `pr` as well as `ci`,** with the comment saying why, and
   Model B's own `crucible.toml` and `AGENTS.md`'s gate rule say the same. Whether no-mistakes' step names
   are exactly `push`, `pr`, `ci` on the installed version is measured.
3. **`release-check` resolves an SSH host alias** to its real host before deciding the origin is not on
   github.com (for example through `ssh -G <alias>`'s `hostname`), and still reports `unknown` with the
   reason when it cannot.
4. **The guards that pin the old text move with it** (the scaffold's `crucible.toml`, the gate rule in
   `AGENTS.md`, the release workflow's rendered jobs).
5. **SoL-Pi is told when it merges,** so it re-renders its workflow and drops its hand edits.

## To measure at gap analysis

- Which tests pin `skip = ["ci"]`, the gate rule's text and `test-python.yml`'s steps.
- no-mistakes' step names on the installed version.
- How other governed projects' suites need installing (an extra named `dev`, `test`, or none).
- The re-score (5 points filed) and the behaviour units.
