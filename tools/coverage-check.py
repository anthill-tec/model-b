#!/usr/bin/env python3
# Owner: Model B (roundhouse/model-b) — CR-MDB-073 §S2. Repo-only: never deployed, unlike the
# tool scripts in scripts/. Run from the project root.
"""The pre-merge gate's coverage check (CR-MDB-073 §S2).

Reads an lcov file and the project's ``pyproject.toml``, prints a table of lines hit/found per
area (the entries of ``[tool.coverage.run] source``) and in total, names every expected source
file the lcov has no record for and names ``scripts/gate-lock.sh`` as unmeasured, then compares
the measured total with the one ``Coverage baseline: <hit>/<found>`` line of the baseline file
(``./AGENTS.md`` by default), exactly, by cross-multiplying.

Exit codes, any reason on stderr: 0 when the measured ratio is at least the baseline's; 1 when it
is lower, naming both figures; 2 when the lcov is missing or has no records, a record lies outside
every area, or the baseline file has zero or several ``Coverage baseline:`` lines. It writes
nothing.

Usage: python3 tools/coverage-check.py <lcov> [--baseline <path>]
"""

import argparse
import fnmatch
import re
import sys
import tomllib
from pathlib import Path

#: The expected-file rule's extensionless directory: every regular file in it is a source.
HOOK_SCRIPTS_DIR = "hooks-src/scripts"
#: The non-Python script coverage.py cannot measure.
UNMEASURED = "scripts/gate-lock.sh"
BASELINE_PREFIX = "Coverage baseline:"
FIGURE = re.compile(r"(?<![\d/])(\d+)/(\d+)(?![\d/])")


class CheckError(Exception):
    """A condition that makes the check impossible — exit 2."""


def _load_config(root: Path) -> tuple[list[str], list[str]]:
    """``(source, omit)`` from ``root``'s ``pyproject.toml``."""
    path = root / "pyproject.toml"
    try:
        with path.open("rb") as fh:
            config = tomllib.load(fh)
    except FileNotFoundError as exc:
        raise CheckError(f"no pyproject.toml in {root}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise CheckError(f"{path} does not parse: {exc}") from exc
    coverage = config.get("tool", {}).get("coverage", {})
    source = coverage.get("run", {}).get("source")
    if not isinstance(source, list) or not source or not all(isinstance(s, str) for s in source):
        raise CheckError(f"{path} has no [tool.coverage.run] source list")
    omit = coverage.get("report", {}).get("omit", [])
    if not isinstance(omit, list) or not all(isinstance(o, str) for o in omit):
        raise CheckError(f"{path}'s [tool.coverage.report] omit is not a list of strings")
    return [s.strip("/") for s in source], omit


def _relative(path: str, root: Path) -> str:
    """``path`` relative to ``root`` when it is absolute and under it; else as written."""
    candidate = Path(path)
    if candidate.is_absolute():
        try:
            return candidate.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            return path
    return candidate.as_posix()


def _parse_lcov(path: Path, root: Path) -> dict[str, tuple[int, int]]:
    """Every record of the lcov at ``path``: its source file → ``(hit, found)`` lines."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise CheckError(f"lcov file not found: {path}") from exc
    records: dict[str, tuple[int, int]] = {}
    current = None
    da_hit = da_found = 0
    lh: int | None = None
    lf: int | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("SF:"):
            current = _relative(line[3:], root)
            da_hit = da_found = 0
            lh = lf = None
        elif current is None:
            continue
        elif line.startswith("DA:"):
            fields = line[3:].split(",")
            da_found += 1
            if len(fields) > 1 and fields[1].isdigit() and int(fields[1]) > 0:
                da_hit += 1
        elif line.startswith("LH:") and line[3:].isdigit():
            lh = int(line[3:])
        elif line.startswith("LF:") and line[3:].isdigit():
            lf = int(line[3:])
        elif line == "end_of_record":
            hit = lh if lh is not None else da_hit
            found = lf if lf is not None else da_found
            prior = records.get(current, (0, 0))
            records[current] = (prior[0] + hit, prior[1] + found)
            current = None
    if not records:
        raise CheckError(f"the lcov has no records: {path}")
    return records


def _area_of(path: str, areas: list[str]) -> str | None:
    """The longest area ``path`` starts with, or ``None``."""
    matches = [a for a in areas if path == a or path.startswith(a + "/")]
    return max(matches, key=len) if matches else None


def _omitted(path: str, omit: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in omit)


def _expected_files(root: Path, areas: list[str], omit: list[str]) -> list[str]:
    """The ``*.py`` files under each area, plus every regular file in ``hooks-src/scripts/`` when
    an area covers it, minus ``omit`` and anything under ``__pycache__``."""
    found: set[str] = set()
    for area in areas:
        base = root / area
        if base.is_dir():
            found.update(p.relative_to(root).as_posix() for p in base.rglob("*.py") if p.is_file())
    hooks = root / HOOK_SCRIPTS_DIR
    if hooks.is_dir() and _area_of(HOOK_SCRIPTS_DIR, areas) is not None:
        found.update(p.relative_to(root).as_posix() for p in hooks.iterdir() if p.is_file())
    return sorted(rel for rel in found
                  if "__pycache__" not in rel.split("/") and not _omitted(rel, omit))


def _read_baseline(path: Path) -> tuple[int, int]:
    """The ``(hit, found)`` of the one ``Coverage baseline:`` line of ``path``."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise CheckError(f"baseline file not found: {path}") from exc
    lines = [line for line in text.splitlines() if line.startswith(BASELINE_PREFIX)]
    if len(lines) != 1:
        raise CheckError(f"{path} has {len(lines)} lines starting with `{BASELINE_PREFIX}`; "
                         "exactly one is needed")
    match = FIGURE.search(lines[0][len(BASELINE_PREFIX):])
    if match is None:
        raise CheckError(f"the {BASELINE_PREFIX} line of {path} carries no <hit>/<found>: "
                         f"{lines[0]}")
    hit, found = int(match.group(1)), int(match.group(2))
    if found == 0 or hit > found:
        raise CheckError(f"the {BASELINE_PREFIX} line of {path} carries an impossible figure "
                         f"{hit}/{found}")
    return hit, found


def _percent(hit: int, found: int) -> str:
    return f"{100 * hit / found:.1f}%" if found else "n/a"


def _figure(hit: int, found: int) -> str:
    return f"{hit}/{found} ({_percent(hit, found)})"


def _check(lcov: Path, baseline: Path, root: Path) -> int:
    areas, omit = _load_config(root)
    records = _parse_lcov(lcov, root)
    outside = sorted(path for path in records if _area_of(path, areas) is None)
    if outside:
        raise CheckError("lcov records outside every [tool.coverage.run] source area: "
                         + ", ".join(outside))
    base_hit, base_found = _read_baseline(baseline)

    per_area = {area: [0, 0] for area in areas}
    for path, (hit, found) in records.items():
        area = _area_of(path, areas)
        assert area is not None  # every record was checked against the areas above
        totals = per_area[area]
        totals[0] += hit
        totals[1] += found
    total_hit = sum(hit for hit, _found in per_area.values())
    total_found = sum(found for _hit, found in per_area.values())

    width = max(len(area) for area in [*areas, "total"])
    print(f"{'area':<{width}}  lines hit/found  percent")
    for area in areas:
        hit, found = per_area[area]
        print(f"{area:<{width}}  {f'{hit}/{found}':>15}  {_percent(hit, found):>7}")
    print(f"{'total':<{width}}  {f'{total_hit}/{total_found}':>15}  "
          f"{_percent(total_hit, total_found):>7}")
    missing = [rel for rel in _expected_files(root, areas, omit) if rel not in records]
    print("no lcov record: " + (", ".join(missing) if missing else "none"))
    print(f"unmeasured: {UNMEASURED} (not Python; outside coverage.py)")

    if total_hit * base_found >= base_hit * total_found:
        return 0
    print(f"coverage dropped: measured {_figure(total_hit, total_found)} is below the baseline "
          f"{_figure(base_hit, base_found)} ({baseline})", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="coverage-check.py",
        description="Check an lcov file's total line coverage against the Coverage baseline.")
    parser.add_argument("lcov", help="the lcov file, e.g. test-reports/vidushi-mdb/coverage.lcov")
    parser.add_argument("--baseline", default="AGENTS.md",
                        help="the file carrying the `Coverage baseline:` line (default ./AGENTS.md)")
    args = parser.parse_args(argv)
    root = Path.cwd()
    try:
        return _check(Path(args.lcov), Path(args.baseline), root)
    except CheckError as exc:
        print(f"coverage-check: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
