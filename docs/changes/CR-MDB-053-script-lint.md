# CR-MDB-053 — Model B's lint rule set and gate step; its findings fixed

**Status:** COMPLETED (filed 2026-10-19, gap analysis and pre-review 2026-10-19).
**Type:** refactor (tool scripts, package, hooks) + tooling (lint config, the pre-merge gate)
**Priority:** P2 — release 1.0.0, wave 2; straight after CR-MDB-081, before the release's test-hygiene CR
(CR-MDB-052).
**Depends on:** CR-MDB-081. The board is authoritative: read `queue`.
**Labels:** scripts, lint, hygiene
**Design reference:** AGENTS.md § Development Commands and § Testing & QA (the pre-merge gate); the
findings CR-MDB-081's VERIFY and the CR-MDB-078 cycles recorded in this CR's seed (82d32aa).

## Context

Model B configures no linter: `AGENTS.md` says "no linter/formatter/type-checker configured … Do not
invent lint commands". Lint findings were measured by hand with whatever ruff profile was at hand, and
ruff's built-in defaults change with each release (ruff 0.16 enables about 800 rules by default). This
CR pins a rule set for Model B's own Python code and adds a lint step to Model B's own pre-merge gate.
It is Model B's project-level lint, Python only. A lint step in every project's gate is Crucible's
(a `lint` verb in every client, run by `pre-merge-gate`, in Crucible 0.4.0); when it ships, this repo's
pinned rule set becomes its declared Python linter.

Measured 2026-10-19 on develop (82d32aa) with ruff 0.16.8 under the rule set of §S1, over every shipped
Python file: 14 findings, plus 2 already suppressed in `hooks-src/scripts/ambient-board-status`
(`# noqa: BLE001 — the hook must never fail`) —
- `BLE001` (a blind `except Exception`) ×6. Three are never-fail boundaries by design: the board
  true-up in `scripts/rust-code-health.py`'s `snapshot`, the ledger hook in `scripts/schedule_db.py`,
  the `.env` copy in `scripts/worktree-flow.py`'s `start`. Three can name their exceptions: `git_head`
  in `scripts/rust-crate-map.py` and in `scripts/rust-dead-scan.py`, and the `json.loads` check in
  `scripts/skill-release-gate.py`'s phase 4;
- `SIM105` (`try`-`except`-`pass`) ×3: `hooks-src/scripts/ambient-board-status` (2),
  `scripts/worktree-flow.py`;
- `F401` (`json` imported, unused), `RUF059` (`ahead` unpacked, unused) and `SIM102` (nested `if`) in
  `scripts/worktree-flow.py`;
- `F841` (`ep_txt` assigned, unused) in `scripts/skill-release-gate.py`;
- `PIE810` (repeated `startswith`) in `scripts/rust-dead-scan.py`.

The editor's Pyright (which blocks edits to these files) reports 6 errors, all in the rust tools, all
optional-typing: `rust-crate-map.py`'s `scan_dir` defaults `base: Path = None` and `modules: list = None`;
`__doc__.splitlines()` in `rust-crate-map.py`, `rust-dead-scan.py` and `rust-code-health.py`;
`rust-dead-scan.py`'s `report` dict, inferred from its first value, receiving the inventory. This host has
no Pyright command line; the rest of the package, the tools and the workflow scripts are Pyright-clean.

Also: `scripts/worktree-flow.py`'s `_pid_alive` has no caller; two comment guards no mutation can kill
(`rust-crate-map.py`'s `count_signals` and `rust-dead-scan.py`'s `mode_inventory` skip `//` lines, though
the attribute patterns only match a line starting `#[`); `scripts/skill-release-gate.py` carries one
pycodestyle E302 blank-line slip.

## Steps

### §S1 — The rule set, pinned

`pyproject.toml` declares Model B's ruff configuration: `[tool.ruff]` with `required-version = ">=0.16"`,
`target-version = "py314"`, the extensionless hook scripts included (`hooks-src/scripts/*`), and the
generated or non-shipped trees excluded (`scripts/toon.py`, `.github/scripts`, `tests`, `archive`,
`generator/agents`); `[tool.ruff.lint]` with
`select = ["F", "I", "BLE001", "PIE810", "RUF059", "SIM102", "SIM105"]`. `PLW1510` is not selected: its
hits are deliberate `subprocess.run` calls whose return code the caller reads. Ruff is a development
tool, never a runtime dependency.

### §S2 — The findings fixed

Every finding the rule set reports is fixed, behaviour unchanged:
- **A never-fail boundary keeps its blind catch,** carrying `# noqa: BLE001` and the reason: the board
  true-up in `rust-code-health.py`'s `snapshot`, the ledger hook in `schedule_db.py`, the `.env` copy in
  `worktree-flow.py`'s `start` (and the hook's two, which already do).
- **Every other blind catch names its exceptions:** `git_head` in `rust-crate-map.py` and
  `rust-dead-scan.py` catches `(subprocess.CalledProcessError, OSError)`; phase 4's `json.loads` check in
  `skill-release-gate.py` catches `ValueError`.
- `try`-`except`-`pass` becomes `contextlib.suppress`; unused names go; nested conditions merge;
  repeated `startswith` takes a tuple.

### §S3 — The Pyright findings fixed

The 6 optional-typing errors are corrected in the code: a parameter that defaults to `None` is annotated
as allowing it; `__doc__` is read with a fallback for a missing docstring; `rust-dead-scan.py`'s `report`
dict is annotated `dict[str, object]`. No type checker joins the gate; the editor's Pyright is the
user's own confirmation.

### §S4 — Dead code and spacing

`_pid_alive` is removed; the two unkillable comment guards are removed; `scripts/skill-release-gate.py`'s
blank lines meet pycodestyle E30.

### §S5 — The gate step and the docs

`AGENTS.md`:
- § Testing & QA's pre-merge gate gains a lint step **first, before the gate run**: `ruff check` from the
  repository root exits 0, a finding being fixed on the branch before the gate runs. The six existing
  steps keep their wording, renumbered after it.
- § Development Commands names `ruff check`, says the rule set lives in `pyproject.toml`, and says how to
  get ruff (`uv tool install ruff`); the "no linter … configured" sentence states that ruff is configured,
  as a development tool, and that no formatter or type checker is.
- § Important Files names `pyproject.toml`'s `[tool.ruff]` and `[tool.ruff.lint]` beside its coverage
  tables.

### §S6 — Who checks what

The structure is pinned by RED's tests, with the standard library: the configuration (AC1), the
suppressions (AC2's `noqa` clause), the code shapes (AC3, AC4's code clauses) and the `AGENTS.md` text
(AC5). `ruff check`'s exit code and `pycodestyle` (AC2, AC4's spacing clause) are run by GREEN, FIX and
VERIFY in their cycles and by the gate's lint step; AC6 by the pre-merge gate.

## Acceptance Criteria

1. **AC1 — the rule set.** `pyproject.toml`'s `[tool.ruff]` keys other than `lint` are exactly
   `required-version = ">=0.16"`, `target-version = "py314"`, `extend-include = ["hooks-src/scripts/*"]`
   and `extend-exclude = ["scripts/toon.py", ".github/scripts", "tests", "archive", "generator/agents"]`;
   `[tool.ruff.lint]` is exactly
   `select = ["F", "I", "BLE001", "PIE810", "RUF059", "SIM102", "SIM105"]`; `[project] dependencies`
   stays empty.
2. **AC2 — lint clean.** `ruff check` (0.16 or later) run from the repository root exits 0. In the files
   it covers, a `noqa` comment naming a selected code is `# noqa: BLE001` with a stated reason, and
   appears only at the five never-fail boundaries named in §S2 (the hook's two included); the two
   `git_head` functions and phase 4's JSON check catch the named exceptions.
3. **AC3 — the Pyright findings.** In `scripts/rust-crate-map.py`, `scripts/rust-dead-scan.py` and
   `scripts/rust-code-health.py`: no parameter whose default is `None` has an annotation that excludes
   `None`; no attribute of `__doc__` is read without a fallback for a missing docstring;
   `rust-dead-scan.py`'s `report` is annotated `dict[str, object]`.
4. **AC4 — dead code and spacing.** `scripts/worktree-flow.py` defines no `_pid_alive`; `count_signals`
   and `mode_inventory` carry no `//` guard; `pycodestyle --select E30 scripts/skill-release-gate.py`
   reports nothing.
5. **AC5 — the gate step and the docs.** `AGENTS.md`'s pre-merge gate has, before the
   `pre-merge-gate` run, a step running `ruff check` that must exit 0; the six existing steps keep their
   wording; § Development Commands names `ruff check` and `uv tool install ruff`; § Important Files names
   `[tool.ruff]`; no sentence says no linter is configured; the unit naming `.github/workflows/release.yml`
   stays.
6. **AC6 — behaviour unchanged.** The full suite through the client is green, with the coverage check not
   below the `Coverage baseline:` line.

## Non-goals

- A lint step in every project's gate, per stack (Crucible's `lint` verb, 0.4.0).
- Lint of `tests/`; rules beyond §S1's set (`PLW1510`, ruff's wider defaults).
- A type checker in the gate.
- pycodestyle E30 slips outside `scripts/skill-release-gate.py` (in `generator/build.py`,
  `modelb_axi/agents.py`, `modelb_axi/scaffold.py`, `modelb_axi/cli.py`, `scripts/schedule_db.py`).
