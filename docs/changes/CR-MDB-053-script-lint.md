# CR-MDB-053 — Model B's lint rule set and gate step; its findings fixed

**Status:** PENDING — spec drafted 2026-10-19 from the gap analysis; spec pre-review next.
**Type:** refactor (tool scripts, package, hooks) + tooling (lint config, the pre-merge gate)
**Priority:** P2 — release 1.0.0, wave 2; straight after CR-MDB-081, before the release's test-hygiene CR
(CR-MDB-052).
**Depends on:** CR-MDB-081. The board is authoritative: read `queue`.
**Labels:** scripts, lint, hygiene
**Design reference:** AGENTS.md § Development Commands and § Testing & QA (the pre-merge gate);
`audits/2026-09-21-codebase-review-assets.md`.

## Context

Model B configures no linter: `AGENTS.md` says "no linter/formatter/type-checker configured … Do not
invent lint commands". Lint findings were measured by hand with whatever ruff profile was at hand, and
ruff's built-in defaults change with each release (ruff 0.16 enables about 800 rules by default). This
CR pins a rule set for Model B's own Python code and adds a lint step to Model B's own pre-merge gate.
It is Model B's project-level lint, Python only; a lint step in every project's gate, per stack, is a
separate design question.

Measured 2026-10-19 on develop (82d32aa) with ruff 0.16.8 under the rule set of §S1, over every shipped
Python file: 14 findings —
- `BLE001` (a blind `except Exception`) ×6: `scripts/rust-code-health.py`, `scripts/rust-crate-map.py`,
  `scripts/rust-dead-scan.py`, `scripts/schedule_db.py`, `scripts/skill-release-gate.py`,
  `scripts/worktree-flow.py`;
- `SIM105` (`try`-`except`-`pass`) ×3: `hooks-src/scripts/ambient-board-status` (2),
  `scripts/worktree-flow.py`;
- `F401` (`json` imported, unused) and `RUF059` (`ahead` unpacked, unused) and `SIM102` (nested `if`) in
  `scripts/worktree-flow.py`;
- `F841` (`ep_txt` assigned, unused) in `scripts/skill-release-gate.py`;
- `PIE810` (repeated `startswith`) in `scripts/rust-dead-scan.py`.

The editor's Pyright (which blocks edits to these files) reports 6 errors, all in the rust tools, all
optional-typing: `rust-crate-map.py`'s `scan_dir` defaults `base: Path = None` and `modules: list = None`,
and `__doc__.splitlines()` in `rust-crate-map.py`, `rust-dead-scan.py` and `rust-code-health.py`;
`rust-dead-scan.py` stores the inventory (`list | None`) into a report dict typed from its first value.
The rest of the package, the tools and the workflow scripts are Pyright-clean.

Also: `scripts/worktree-flow.py`'s `_pid_alive` has no caller; two comment guards no mutation can kill
(`rust-crate-map.py`'s `count_signals` and `rust-dead-scan.py`'s `mode_inventory` skip `//` lines,
though the attribute patterns only match a line starting `#[`); `scripts/skill-release-gate.py` carries
pycodestyle E302/E305 blank-line slips before its top-level definitions.

## Steps

### §S1 — The rule set, pinned

`pyproject.toml` declares Model B's ruff configuration: `[tool.ruff]` with `target-version = "py314"`,
the extensionless hook scripts included (`hooks-src/scripts/*`), and the generated or non-shipped trees
excluded (`scripts/toon.py`, `.github/scripts`, `tests`, `archive`, `generator/agents`);
`[tool.ruff.lint]` with `select = ["F", "I", "BLE001", "PIE810", "RUF059", "SIM102", "SIM105"]`.
`PLW1510` is not selected: its hits are deliberate `subprocess.run` calls whose return code the caller
reads. Ruff is a development tool, never a runtime dependency.

### §S2 — The findings fixed

Every finding the rule set reports is fixed in the code, none suppressed: a blind `except Exception`
catches the exceptions its call can raise; `try`-`except`-`pass` becomes `contextlib.suppress`; unused
names go; nested conditions merge; repeated `startswith` takes a tuple. Behaviour is unchanged.

### §S3 — The Pyright findings fixed

The 6 optional-typing errors are corrected: parameters that default to `None` are annotated as allowing
it; `__doc__` is read with a fallback; the report dict is typed for the values it holds. No type checker
joins the gate.

### §S4 — Dead code and spacing

`_pid_alive` is removed; the two unkillable comment guards are removed; `scripts/skill-release-gate.py`'s
blank lines meet pycodestyle E30.

### §S5 — The gate step

`AGENTS.md`:
- § Testing & QA's pre-merge gate gains a step 7, after the existing six (whose wording
  `tests.test_coverage_gate` pins): `ruff check` from the repository root exits 0, and a finding is fixed
  before the merge;
- § Development Commands names `ruff check` and says the rule set lives in `pyproject.toml`; the "no
  linter … configured" sentence states that ruff is configured, as a development tool, and that no
  formatter or type checker is.

## Acceptance Criteria

1. **AC1 — the rule set.** `pyproject.toml`'s `[tool.ruff]` is exactly `target-version = "py314"`,
   `extend-include = ["hooks-src/scripts/*"]` and
   `extend-exclude = ["scripts/toon.py", ".github/scripts", "tests", "archive", "generator/agents"]`, and
   `[tool.ruff.lint]` is exactly `select = ["F", "I", "BLE001", "PIE810", "RUF059", "SIM102", "SIM105"]`;
   `[project] dependencies` stays empty.
2. **AC2 — lint clean.** `ruff check` (0.16 or later) run from the repository root exits 0, and no
   covered file carries a `noqa` comment.
3. **AC3 — the Pyright findings.** In `scripts/rust-crate-map.py`, `scripts/rust-dead-scan.py` and
   `scripts/rust-code-health.py`, no parameter whose default is `None` has an annotation that excludes
   `None`, and no `__doc__` attribute access lacks a fallback for a missing docstring; the editor's
   Pyright reports no error in the three files.
4. **AC4 — dead code.** `scripts/worktree-flow.py` defines no `_pid_alive`; `count_signals` and
   `mode_inventory` carry no `//` guard; `pycodestyle --select E30 scripts/skill-release-gate.py` reports
   nothing.
5. **AC5 — the gate step.** `AGENTS.md`'s pre-merge gate has a step 7 running `ruff check` that must exit
   0 before the merge; steps 1–6 keep their wording; § Development Commands names `ruff check`; no
   sentence says no linter is configured.
6. **AC6 — behaviour unchanged.** The full suite through the client is green, with the coverage check not
   below the `Coverage baseline:` line.

## Non-goals

- A lint step in every project's gate, per stack (a separate design question, with Crucible's view on a
  client's `check` verb).
- Lint of `tests/`, and rules beyond §S1's set (`PLW1510`, ruff's wider defaults).
- A type checker in the gate.
