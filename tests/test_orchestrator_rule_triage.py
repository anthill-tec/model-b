"""The orchestrator-rule triage file gate — CR-MDB-042 §S1 (inventory and triage).

Contract: ``docs/changes/CR-MDB-042-orchestrator-definitions-absorbed.md``. The rules learned while
running the orchestrator were written to per-project memory under ``~/.claude/projects/<slug>/
memory/`` and to ``~/.claude/AGENTS.md``; ``audits/2026-09-26-orchestrator-rule-triage.md``
inventories those sources and classifies every rule item. This module reads ONLY that repo file —
the suite is hermetic: no test reads ``~/.claude``, ``~/.agents`` or anything else under ``$HOME``
(re-deriving the inventory from the real sources is the orchestrator's and VERIFY's job).

File format (pinned here; GREEN writes to it):

- a section headed exactly ``## Inventory`` holding ONE Markdown table
  ``| Source | sha256 |`` — one row per source file.
  **Source** is a home-relative path in backticks starting ``~/.claude/``, e.g.
  ``\\`~/.claude/projects/-home-antonyj-Documents-data-projects-nai/memory/ORCHESTRATOR-RULES.md\\```;
  **sha256** is 64 lower-case hex characters in backticks. No source appears twice.
- a section headed exactly ``## Triage`` holding ONE Markdown table
  ``| Source | Class | Destination | Note |`` — one row per rule item.
  **Source** is ``\\`<inventory path>\\``` optionally followed by `` § <heading>`` (a heading of that
  file as written, without its ``#`` marks). The three notes are triaged per heading (every row of
  theirs carries `` § ``); ``~/.claude/AGENTS.md`` per Non-negotiables bullet, exactly
  `` § Non-negotiables (1)`` … `` § Non-negotiables (7)``; a feedback topic file is ONE item with
  no `` § `` — or split per its own headings, but never both a whole-file row and heading rows.
  No two rows share the same Source cell.
- **Class** is exactly one of ``common``, ``stack:<stack>`` (stack ∈ arduino, bun, python, quarkus,
  rust, java), ``project:<project>``, ``duplicate``, ``stale``.
- **Destination** by class:
  ``common`` — ``\\`skills-src/<bundle>/<file>.md\\` § <section>`` with ``<bundle>`` a Model B-owned
  bundle: model-b, gap-analysis, cr-authoring, git-workflow, crucible, bootstrap, shutdown;
  ``stack:<stack>`` — ``\\`skills-src/code-health/<file>.md\\` § <section>`` or
  ``\\`skills-src/memory-templates/<t>-orchestration.md\\` § <section>`` with ``<t>`` = the stack
  (``java`` for both ``quarkus`` and ``java``);
  ``project:model-b`` — ``\\`AGENTS.md\\` § <section>``;
  any other ``project:*`` — non-empty text naming that project's ``AGENTS.md`` (e.g. ``NAI AGENTS.md``);
  ``duplicate`` — a ``\\`skills-src/...md\\` § <section>`` in one of the common or stack bundles
  above (the section it repeats);
  ``stale`` — exactly ``—``.
  Crucible's imported bundles (``skills-src/crucible-register/``, ``skills-src/crucible-report-*/``)
  are never a destination.
- **Note** is non-empty on every ``stale`` row.

Class map:

- ``TriageFileStructureTest`` — the file exists; both sections exist; each holds one table with the
  exact header.
- ``TriageInventoryTest`` — inventory rows: path/sha shape, no duplicates, the required sources
  present, the out-of-scope slugs absent.
- ``TriageCoverageTest`` — triage ↔ inventory coverage, unique Source cells, per-heading notes,
  the seven ``~/.claude/AGENTS.md`` Non-negotiables rows.
- ``TriageClassRulesTest`` — class vocabulary, destination rules per class, stale notes.
- ``TriageRulesOnSyntheticTextTest`` — the same pure functions on in-memory text: a well-formed
  fixture yields nothing, and each bad row is reported.

CR-MDB-042 §S2–§S3 (absorb) — the approved triage is the work list:

- ``AbsorbedDestinationTest`` — every ``common``, ``stack:*`` and ``project:model-b`` row (the
  five whose destination is under ``skills-src/gap-analysis/`` included since C3 adopted that
  bundle, §S4): the named
  file exists (``project:model-b`` → the repo ``AGENTS.md``) and carries a Markdown heading, any
  level, whose text equals the row's `` § <section>`` exactly (after stripping); the new
  ``skills-src/memory-templates/arduino-orchestration.md`` exists.
- ``AbsorbedNewSectionBodyTest`` — each ``common``/``stack`` row whose Note says "New section" (or
  "New file and section") has a non-empty body under that heading, up to the next heading of the
  same or a higher level: at least one non-blank line that is not a heading.
- ``ModelBCommonTextNeutralTest`` — no line of ``skills-src/model-b/SKILL.md``,
  ``skills-src/model-b/references/*.md`` or ``skills-src/gap-analysis/SKILL.md`` names ``NAI``,
  ``Roundhouse`` or ``ORCHESTRATOR-`` unless
  the same line is a dated provenance citation (a ``CR-<ACR>-<n>`` id and a ``20YY-MM-DD`` date),
  and none names a harness tool retired by CR-MDB-031 (the vocabulary of
  ``tests.test_client_path_anchoring``, the ``sandesh_*`` MCP tools included).
- ``HeadingRenameMapTest`` — CR-MDB-044 §S1: the triage is frozen, so a destination heading
  renamed since resolves through ``HEADING_RENAMES`` (file, old heading) → new heading, held here
  and holding exactly one entry: ``orchestration-common.md`` § "Never author code — always
  dispatch + diff-verify" → "Never author code — dispatch with an accurate brief". A mapped
  heading is looked up under its new name only; every other destination resolves unaided.
- ``AbsorbRulesOnSyntheticTreeTest`` — the same pure functions over a temp tree.
- ``MovedRulesMapTest`` — CR-MDB-085 §S6.2: the triage stays frozen while CR-MDB-085 §S3 moves six
  of its rules out of their memory template. ``MOVED_RULES`` — beside ``HEADING_RENAMES``, which
  keeps its one entry — maps each such row, by its line in the frozen audit (191, 192, 211, 284,
  373 and 384; 191 joined the spec's five by orchestrator ruling), to its new file and its §S3
  anchor phrase(s). The gate finds the phrases there instead of checking the row's old heading, its
  new-section body and its class rule; the audit's bytes are pinned (``TRIAGE_FILE_SHA256``).
- ``MovedRulesOnSyntheticTextTest`` — the moved-rules functions on in-memory text and a temp tree.
- ``FileMoveMapTest`` — CR-MDB-060 §S5.2/AC6: the triage stays frozen while CR-MDB-060 §S1.1 moves
  each stack's memory template, headings unchanged, into its stack skill. ``FILE_MOVES`` — beside
  ``MOVED_RULES`` — maps each old template path to its ``references/orchestration.md``; every check
  that reads a destination file (the destination and new-section-body checks, the moved-rules
  departure check, the arduino template check, ``CapabilityWordingTest``, the pinned bundle set)
  resolves the file through it (``resolve_file``). The audit's Destination strings and the class
  rules are left as written; the audit's bytes stay pinned.
- ``FileMoveMapOnSyntheticTreeTest`` — ``resolve_file`` and the checks that use it, both sides of
  the move, over a temp tree.

CR-MDB-042 §S5 (mapping) — ``archive/mapping.md`` (gated by ``tests.test_archive_mapping``, whose
pattern matcher ``covers_required`` is reused: ``<name>`` is one path component, ``{a,b}`` one of
the names, ``*`` is literal):

- ``OrchestratorSourcesMappedTest`` — exactly ten rows of Kind ``absorbed`` whose Now is the triage
  file: one per note (its literal path), one for ``~/.claude/AGENTS.md`` whose Authority names the
  Non-negotiables, and one per feedback project whose Old path covers every inventoried feedback
  memory of that project and none of another's; every inventory source is covered; each row's
  Moved by cites ``CR-MDB-042``. One ``moved`` row ``~/.agents/skills/gap-analysis/`` →
  ``skills-src/gap-analysis/`` citing ``CR-MDB-042``. Every row covering one of the five Java
  originals states that the original remains in ``~/.claude/memory/`` until the user removes it.
- ``MappingRulesOnSyntheticRowsTest`` — the same pure functions over in-memory rows.

Every check is a pure function returning a list of problem strings (``[]`` = clean), so the real
file and the fixtures run through the same code.

Stdlib only.
"""

import re
import shutil
import tempfile
import tomllib
import unittest
from collections.abc import Sequence
from pathlib import Path

from tests._helpers import (
    ORCHESTRATION_TEMPLATE_MOVES,
    REPO_ROOT,
    at_line,
    md_section,
    read_text,
    sha256_bytes,
)
from tests.test_archive_mapping import (
    MAP_PATH,
    _unticked,
    check_rows,
    covers_required,
    parse_map,
)
from tests.test_client_path_anchoring import _count_tools

TRIAGE_FILE = REPO_ROOT / "audits" / "2026-09-26-orchestrator-rule-triage.md"

INVENTORY_HEADER = ["Source", "sha256"]
TRIAGE_HEADER = ["Source", "Class", "Destination", "Note"]

NAI = "-home-antonyj-Documents-data-projects-nai"
CRUCIBLE = "-home-antonyj-Documents-data-projects-crucible"
SANDESH = "-home-antonyj-Documents-data-projects-sandesh"
ROUNDHOUSE = "-home-antonyj-Documents-configurations-roundhouse"
MODEL_B = "-home-antonyj-Documents-configurations-roundhouse-model-b"
VALMIK = "-home-antonyj-Documents-device-projects-Arduino-Valmik"
PUMPCONTROL = "-home-antonyj-Documents-device-projects-Arduino-PumpControl"

#: The six projects whose ``type: feedback`` memories are sources (Roundhouse holds none).
FEEDBACK_SLUGS = (NAI, CRUCIBLE, SANDESH, MODEL_B, VALMIK, PUMPCONTROL)
#: Every project slug a source may live under.
IN_SCOPE_SLUGS = FEEDBACK_SLUGS + (ROUNDHOUSE,)
#: Not Model B projects — out of scope.
OUT_OF_SCOPE_MARKERS = ("ah-codeforge", "sys-toolbox")

GLOBAL_AGENTS = "~/.claude/AGENTS.md"
NOTES = (
    f"~/.claude/projects/{NAI}/memory/ORCHESTRATOR-RULES.md",
    f"~/.claude/projects/{NAI}/memory/ORCHESTRATOR-NAI.md",
    f"~/.claude/projects/{ROUNDHOUSE}/memory/ORCHESTRATOR-Roundhouse.md",
)
REQUIRED_SOURCES = NOTES + (GLOBAL_AGENTS,)
NON_NEGOTIABLES = tuple(f"`{GLOBAL_AGENTS}` § Non-negotiables ({n})" for n in range(1, 8))

STACKS = ("arduino", "bun", "python", "quarkus", "rust", "java")
COMMON_BUNDLES = ("model-b", "gap-analysis", "cr-authoring", "git-workflow", "crucible",
                  "bootstrap", "shutdown")
STALE_DESTINATION = "—"

_PATH_CELL = re.compile(r"^`(~/\.claude/[^`]+)`$")
_SHA_CELL = re.compile(r"^`[0-9a-f]{64}`$")
_TRIAGE_SOURCE = re.compile(r"^`([^`]+)`(?: § (.+))?$")
_SKILL_DEST = re.compile(r"^`(skills-src/[^`]+\.md)` § (\S.*)$")
_AGENTS_DEST = re.compile(r"^`AGENTS\.md` § (\S.*)$")
_PROJECT_CLASS = re.compile(r"^project:([A-Za-z0-9][A-Za-z0-9._-]*)$")
_SEPARATOR = re.compile(r"^\|(\s*:?-+:?\s*\|)+$")


# ------------------------------------------------------------------ parsing ----

def section(text: str, heading: str) -> str:
    """The body of the section headed exactly ``heading`` (``## X``), up to the next ``## ``
    heading; ``""`` when absent. ``md_section`` matches by prefix, so the heading line is
    re-checked for an exact match (``## Triage notes`` is not ``## Triage``)."""
    for line in text.splitlines():
        if line.rstrip() == heading:
            break
    else:
        return ""
    chunk = md_section(text, heading)
    lines = chunk.splitlines()
    while lines and lines[0].rstrip() != heading:  # a prefix-matching heading came first
        rest = text[text.index(chunk) + len(chunk):]
        chunk = md_section(rest, heading)
        lines = chunk.splitlines()
    return "\n".join(lines[1:])


def parse_table(body: str, header: list[str]) -> tuple[list[dict], list[str]]:
    """``(rows, problems)`` for the ONE Markdown table in ``body``. A table is a run of lines
    starting with ``|``; its first line must carry exactly ``header``, its second a ``---``
    separator, and every data row exactly ``len(header)`` cells. Rows are dicts keyed by header."""
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            current.append(stripped)
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    if len(blocks) != 1:
        return [], [f"expected exactly one table, found {len(blocks)}"]
    lines = blocks[0]
    cells = [_cells(line) for line in lines]
    if cells[0] != header:
        return [], [f"table header is {cells[0]!r}, expected {header!r}"]
    if len(lines) < 2 or not _SEPARATOR.match(lines[1]):
        return [], ["table header is not followed by a --- separator row"]
    rows, problems = [], []
    for line, row in zip(lines[2:], cells[2:], strict=True):
        if len(row) != len(header):
            problems.append(f"row has {len(row)} cells, expected {len(header)}: {line}")
            continue
        rows.append(dict(zip(header, row, strict=True)))
    return rows, problems


def _cells(line: str) -> list[str]:
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return [c.strip() for c in inner.split("|")]


def parse_triage_text(text: str) -> tuple[list[dict], list[dict], list[str]]:
    """``(inventory_rows, triage_rows, problems)`` for a whole triage file's text."""
    problems = []
    inv_body = section(text, "## Inventory")
    tri_body = section(text, "## Triage")
    if not inv_body:
        problems.append("no '## Inventory' section")
    if not tri_body:
        problems.append("no '## Triage' section")
    inventory, p1 = parse_table(inv_body, INVENTORY_HEADER) if inv_body else ([], [])
    triage, p2 = parse_table(tri_body, TRIAGE_HEADER) if tri_body else ([], [])
    problems += [f"Inventory: {p}" for p in p1] + [f"Triage: {p}" for p in p2]
    return inventory, triage, problems


def inventory_path(cell: str) -> str | None:
    """The ``~/.claude/...`` path of an inventory Source cell, or ``None`` if malformed."""
    m = _PATH_CELL.match(cell)
    return m.group(1) if m else None


def triage_source(cell: str) -> tuple[str | None, str | None]:
    """``(path, heading)`` of a triage Source cell (heading ``None`` when whole-file);
    ``(None, None)`` if malformed."""
    m = _TRIAGE_SOURCE.match(cell)
    if not m:
        return None, None
    return m.group(1), m.group(2)


# ------------------------------------------------------------------ rules ----

def inventory_findings(rows: list[dict]) -> list[str]:
    """Shape rules over inventory rows: backticked ``~/.claude/`` path, 64-hex sha, no duplicate,
    no out-of-scope slug, project sources only under in-scope slugs."""
    problems, seen = [], set()
    for row in rows:
        path = inventory_path(row["Source"])
        if path is None:
            problems.append(f"inventory Source is not a backticked ~/.claude/ path: {row['Source']}")
            continue
        if not _SHA_CELL.match(row["sha256"]):
            problems.append(f"inventory sha256 is not 64 lower-case hex in backticks: "
                            f"{row['sha256']} ({path})")
        if path in seen:
            problems.append(f"inventory lists a source twice: {path}")
        seen.add(path)
        if any(marker in path for marker in OUT_OF_SCOPE_MARKERS):
            problems.append(f"inventory lists an out-of-scope source: {path}")
        elif path.startswith("~/.claude/projects/"):
            slug = path[len("~/.claude/projects/"):].split("/", 1)[0]
            if slug not in IN_SCOPE_SLUGS:
                problems.append(f"inventory source lies under a project slug not in scope: {path}")
    return problems


def missing_required_sources(paths: Sequence[str | None]) -> list[str]:
    """Required sources absent from ``paths``: the three notes, ``~/.claude/AGENTS.md``, and at
    least one memory file (other than an ``ORCHESTRATOR-`` note) per feedback project."""
    missing = [p for p in REQUIRED_SOURCES if p not in paths]
    for slug in FEEDBACK_SLUGS:
        prefix = f"~/.claude/projects/{slug}/memory/"
        if not any(p is not None and p.startswith(prefix) and "/" not in p[len(prefix):]
                   and not p[len(prefix):].startswith("ORCHESTRATOR-") for p in paths):
            missing.append(f"{prefix}<feedback memory>")
    return missing


def coverage_findings(inventory: list[dict], triage: list[dict]) -> list[str]:
    """Triage ↔ inventory coverage: every triage path inventoried, every inventory path triaged,
    unique Source cells, notes per heading, no whole-file row beside heading rows, and exactly the
    seven Non-negotiables rows for ``~/.claude/AGENTS.md``."""
    problems = []
    inv_paths = {p for p in (inventory_path(r["Source"]) for r in inventory) if p is not None}
    by_path: dict[str, list[str | None]] = {}
    cells_seen: set[str] = set()
    agents_cells = []
    for row in triage:
        cell = row["Source"]
        path, heading = triage_source(cell)
        if path is None:
            problems.append(f"triage Source is not '`<path>`' or '`<path>` § <heading>': {cell}")
            continue
        if cell in cells_seen:
            problems.append(f"two triage rows share the Source cell: {cell}")
        cells_seen.add(cell)
        if path not in inv_paths:
            problems.append(f"triage row names a source not in the inventory: {path}")
        by_path.setdefault(path, []).append(heading)
        if path == GLOBAL_AGENTS:
            agents_cells.append(cell)
    for path in sorted(inv_paths):
        headings = by_path.get(path)
        if not headings:
            problems.append(f"inventory source has no triage row: {path}")
            continue
        if None in headings and len(headings) > 1:
            problems.append(f"source triaged both whole-file and per heading: {path}")
        if (path in NOTES or path == GLOBAL_AGENTS) and None in headings:
            problems.append(f"note triaged as a whole file instead of per heading: {path}")
    if GLOBAL_AGENTS in inv_paths and sorted(agents_cells) != sorted(NON_NEGOTIABLES):
        problems.append(f"{GLOBAL_AGENTS} rows are {sorted(agents_cells)!r}, expected exactly "
                        f"{list(NON_NEGOTIABLES)!r}")
    return problems


def _stack_destination_ok(stack: str, dest_path: str) -> bool:
    template = "java" if stack in ("quarkus", "java") else stack
    return (dest_path.startswith("skills-src/code-health/")
            or dest_path == f"skills-src/memory-templates/{template}-orchestration.md")


def _in_common_bundle(dest_path: str) -> bool:
    return any(dest_path.startswith(f"skills-src/{b}/") for b in COMMON_BUNDLES)


def _in_stack_bundle(dest_path: str) -> bool:
    return (dest_path.startswith("skills-src/code-health/")
            or re.fullmatch(r"skills-src/memory-templates/[a-z]+-orchestration\.md", dest_path)
            is not None)


def _crucible_owned(dest_path: str) -> bool:
    return dest_path.startswith(("skills-src/crucible-register/", "skills-src/crucible-report-"))


def triage_row_findings(row: dict) -> list[str]:
    """Class vocabulary and the destination / note rule of one triage row."""
    cls, dest, note, src = row["Class"], row["Destination"], row["Note"], row["Source"]
    where = f"({src})"
    skill = _SKILL_DEST.match(dest)
    dest_path = skill.group(1) if skill else None
    if dest_path and _crucible_owned(dest_path):
        return [f"destination is a Crucible-owned imported bundle: {dest} {where}"]
    if cls == "common":
        if not dest_path:
            return [f"common destination is not '`skills-src/...md` § <section>': {dest} {where}"]
        if not _in_common_bundle(dest_path):
            return [f"common destination is not in a Model B-owned bundle: {dest} {where}"]
        return []
    if cls.startswith("stack:"):
        stack = cls[len("stack:"):]
        if stack not in STACKS:
            return [f"unknown stack in class {cls!r} {where}"]
        if not dest_path:
            return [f"stack destination is not '`skills-src/...md` § <section>': {dest} {where}"]
        if not _stack_destination_ok(stack, dest_path):
            return [f"{cls} destination is not code-health or the {stack} orchestration "
                    f"template: {dest} {where}"]
        return []
    if cls.startswith("project:"):
        m = _PROJECT_CLASS.match(cls)
        if not m:
            return [f"malformed project class {cls!r} {where}"]
        if m.group(1) == "model-b":
            if not _AGENTS_DEST.match(dest):
                return [f"project:model-b destination is not '`AGENTS.md` § <section>': "
                        f"{dest} {where}"]
            return []
        if not dest:
            return [f"{cls} row has an empty destination {where}"]
        return []
    if cls == "duplicate":
        if not dest_path:
            return [f"duplicate destination is not '`skills-src/...md` § <section>': "
                    f"{dest} {where}"]
        if not (_in_common_bundle(dest_path) or _in_stack_bundle(dest_path)):
            return [f"duplicate destination is not in a Model B-owned bundle: {dest} {where}"]
        return []
    if cls == "stale":
        problems = []
        if dest != STALE_DESTINATION:
            problems.append(f"stale destination must be exactly '—', got {dest!r} {where}")
        if not note:
            problems.append(f"stale row carries no Note {where}")
        return problems
    return [f"unknown class {cls!r} {where}"]


def triage_findings(rows: list[dict]) -> list[str]:
    problems = []
    for row in rows:
        problems += triage_row_findings(row)
    return problems


# ------------------------------------------------------------------ real file ----

class _RealFileMixin(unittest.TestCase):
    """Base for the real-file classes (no tests of its own)."""

    def moved(self) -> dict:
        """CR-MDB-085 §S6.2: the frozen rows whose rule moved, by Source cell."""
        rows, problems = moved_rule_rows(read_text(TRIAGE_FILE))
        self.assertEqual(problems, [], "MOVED_RULES names an audit line that is not a triage row")
        return rows

    def load(self):
        self.assertTrue(TRIAGE_FILE.is_file(),
                        f"CR-MDB-042 §S1: {TRIAGE_FILE.relative_to(REPO_ROOT)} does not exist")
        inventory, triage, problems = parse_triage_text(read_text(TRIAGE_FILE))
        self.assertEqual(problems, [], "triage file does not parse")
        self.assertGreater(len(inventory), 0, "the Inventory table has no rows")
        self.assertGreater(len(triage), 0, "the Triage table has no rows")
        return inventory, triage


class TriageFileStructureTest(_RealFileMixin):
    def test_triage_file_exists_with_inventory_and_triage_tables(self):
        inventory, triage = self.load()
        # every source has at least one item, so the item count is never below the source count
        self.assertGreaterEqual(len(triage), len(inventory))


class TriageInventoryTest(_RealFileMixin):
    def test_every_inventory_row_is_a_backticked_claude_path_with_a_sha256(self):
        inventory, _ = self.load()
        self.assertEqual(inventory_findings(inventory), [])

    def test_inventory_lists_the_notes_global_agents_and_every_feedback_project(self):
        inventory, _ = self.load()
        paths = [inventory_path(r["Source"]) for r in inventory]
        self.assertEqual(missing_required_sources(paths), [])

    def test_inventory_lists_the_sandesh_no_cross_project_reads_memory(self):
        """CR-MDB-042 VERIFY F7: a ``type: feedback`` memory created after the triage."""
        inventory, triage = self.load()
        path = f"~/.claude/projects/{SANDESH}/memory/no-cross-project-reads.md"
        self.assertIn(path, [inventory_path(r["Source"]) for r in inventory])
        self.assertIn(path, [triage_source(r["Source"])[0] for r in triage])

    def test_inventory_lists_nothing_from_ah_codeforge_or_sys_toolbox(self):
        inventory, _ = self.load()
        leaked = [r["Source"] for r in inventory
                  if any(m in r["Source"] for m in OUT_OF_SCOPE_MARKERS)]
        self.assertEqual(leaked, [])


class TriageCoverageTest(_RealFileMixin):
    def test_triage_and_inventory_cover_each_other_one_row_per_item(self):
        inventory, triage = self.load()
        self.assertEqual(coverage_findings(inventory, triage), [])

    def test_global_agents_is_triaged_as_exactly_the_seven_non_negotiables(self):
        _, triage = self.load()
        cells = sorted(r["Source"] for r in triage
                       if triage_source(r["Source"])[0] == GLOBAL_AGENTS)
        self.assertEqual(cells, sorted(NON_NEGOTIABLES))

    def test_each_orchestrator_note_is_triaged_per_heading(self):
        _, triage = self.load()
        for note in NOTES:
            headings = [triage_source(r["Source"])[1] for r in triage
                        if triage_source(r["Source"])[0] == note]
            self.assertGreater(len(headings), 0, f"{note} has no triage row")
            self.assertNotIn(None, headings, f"{note} carries a whole-file row")


class TriageClassRulesTest(_RealFileMixin):
    def test_every_row_has_a_known_class_and_a_destination_its_class_allows(self):
        # MIGRATED (CR-MDB-085 §S6.2): a moved row is checked by its anchor phrases in its new
        # file (MovedRulesMapTest) instead of by its class rule.
        _, triage = self.load()
        self.assertEqual(triage_findings(unmoved(triage, self.moved())), [])

    def test_every_stale_row_carries_a_note_and_the_dash_destination(self):
        _, triage = self.load()
        bad = [r["Source"] for r in triage
               if r["Class"] == "stale" and (not r["Note"] or r["Destination"] != "—")]
        self.assertEqual(bad, [])

    def test_no_row_routes_into_crucibles_imported_bundles(self):
        _, triage = self.load()
        bad = [r["Source"] for r in triage
               if "skills-src/crucible-register/" in r["Destination"]
               or "skills-src/crucible-report-" in r["Destination"]]
        self.assertEqual(bad, [])


# ------------------------------------------------------------------ fixtures ----

_H = "~/.claude/projects"
_SHA = "`" + "a" * 64 + "`"


def _fixture_inventory() -> list[str]:
    paths = list(REQUIRED_SOURCES) + [f"{_H}/{s}/memory/feedback_example.md" for s in FEEDBACK_SLUGS]
    return [f"| `{p}` | {_SHA} |" for p in paths]


def _fixture_triage() -> list[str]:
    rows = [
        f"| `{NOTES[0]}` § §1 Gap analysis | common | "
        "`skills-src/gap-analysis/SKILL.md` § Dimensions | |",
        f"| `{NOTES[0]}` § §7 Rust overrides | stack:rust | "
        "`skills-src/memory-templates/rust-orchestration.md` § Gates | |",
        f"| `{NOTES[1]}` § Identity | project:nai | NAI AGENTS.md | |",
        f"| `{NOTES[2]}` § Board | stale | — | retired mechanism: Claude Code TaskList |",
    ]
    rows += [f"| {c} | duplicate | `skills-src/model-b/references/orchestration-common.md` § "
             f"Scope | |" for c in NON_NEGOTIABLES]
    rows += [
        f"| `{_H}/{NAI}/memory/feedback_example.md` | stack:quarkus | "
        "`skills-src/memory-templates/java-orchestration.md` § Build | |",
        f"| `{_H}/{CRUCIBLE}/memory/feedback_example.md` | stack:python | "
        "`skills-src/code-health/SKILL.md` § Checks | |",
        f"| `{_H}/{SANDESH}/memory/feedback_example.md` | common | "
        "`skills-src/crucible/SKILL.md` § Lifecycle | |",
        f"| `{_H}/{MODEL_B}/memory/feedback_example.md` | project:model-b | "
        "`AGENTS.md` § Workflow Rules (Model B, solo) | |",
        f"| `{_H}/{VALMIK}/memory/feedback_example.md` § Approval | common | "
        "`skills-src/model-b/references/orchestration-common.md` § Gap analysis | |",
        f"| `{_H}/{VALMIK}/memory/feedback_example.md` § Flashing | stack:arduino | "
        "`skills-src/memory-templates/arduino-orchestration.md` § Upload | |",
        f"| `{_H}/{PUMPCONTROL}/memory/feedback_example.md` | stale | — | "
        "route to Crucible |",
    ]
    return rows


def _fixture_text(inventory=None, triage=None) -> str:
    inventory = _fixture_inventory() if inventory is None else inventory
    triage = _fixture_triage() if triage is None else triage
    return "\n".join(
        ["# Orchestrator rule triage", "", "## Inventory", "",
         "| Source | sha256 |", "|---|---|", *inventory, "",
         "## Triage", "", "| Source | Class | Destination | Note |", "|---|---|---|---|",
         *triage, "", "## Merge note", "", "Nothing.", ""])


def _all_findings(text: str) -> list[str]:
    inventory, triage, problems = parse_triage_text(text)
    paths = [inventory_path(r["Source"]) for r in inventory]
    return (problems + inventory_findings(inventory) + missing_required_sources(paths)
            + coverage_findings(inventory, triage) + triage_findings(triage))


def _row(src="`~/.claude/AGENTS.md` § Non-negotiables (1)", cls="common",
         dest="`skills-src/model-b/SKILL.md` § Roles", note="") -> dict:
    return {"Source": src, "Class": cls, "Destination": dest, "Note": note}


class TriageRulesOnSyntheticTextTest(unittest.TestCase):
    def test_well_formed_fixture_yields_no_finding(self):
        text = _fixture_text()
        inventory, triage, _ = parse_triage_text(text)
        self.assertEqual(len(inventory), 10)
        self.assertEqual(len(triage), 18)
        self.assertEqual(_all_findings(text), [])

    def test_missing_sections_and_wrong_header_are_reported(self):
        self.assertEqual(parse_triage_text("# nothing\n")[2],
                         ["no '## Inventory' section", "no '## Triage' section"])
        bad = _fixture_text().replace("| Source | sha256 |", "| Path | sha256 |")
        self.assertEqual(parse_triage_text(bad)[2],
                         ["Inventory: table header is ['Path', 'sha256'], "
                          "expected ['Source', 'sha256']"])

    def test_a_prefix_heading_is_not_taken_for_the_section(self):
        text = _fixture_text().replace("## Triage\n", "## Triage notes\n")
        self.assertIn("no '## Triage' section", parse_triage_text(text)[2])

    def test_second_table_in_a_section_is_reported(self):
        text = _fixture_text().replace("## Triage\n", "| x | y |\n|---|---|\n| 1 | 2 |\n\n## Triage\n")
        self.assertIn("Inventory: expected exactly one table, found 2", parse_triage_text(text)[2])

    def test_malformed_inventory_rows_are_reported(self):
        rows = [f"| `{GLOBAL_AGENTS}` | `ABC` |", f"| `{GLOBAL_AGENTS}` | {_SHA} |",
                f"| /home/x/AGENTS.md | {_SHA} |",
                f"| `{_H}/-home-antonyj-Documents-ah-codeforge/memory/feedback_x.md` | {_SHA} |",
                f"| `{_H}/-home-antonyj-other/memory/feedback_x.md` | {_SHA} |"]
        inventory, _, _ = parse_triage_text(_fixture_text(inventory=rows, triage=[]))
        self.assertEqual(inventory_findings(inventory), [
            f"inventory sha256 is not 64 lower-case hex in backticks: `ABC` ({GLOBAL_AGENTS})",
            f"inventory lists a source twice: {GLOBAL_AGENTS}",
            "inventory Source is not a backticked ~/.claude/ path: /home/x/AGENTS.md",
            f"inventory lists an out-of-scope source: "
            f"{_H}/-home-antonyj-Documents-ah-codeforge/memory/feedback_x.md",
            f"inventory source lies under a project slug not in scope: "
            f"{_H}/-home-antonyj-other/memory/feedback_x.md",
        ])

    def test_missing_required_sources_are_named(self):
        paths = [p for p in REQUIRED_SOURCES if p != NOTES[2]]
        paths += [f"{_H}/{s}/memory/feedback_x.md" for s in FEEDBACK_SLUGS if s != SANDESH]
        self.assertEqual(missing_required_sources(paths),
                         [NOTES[2], f"~/.claude/projects/{SANDESH}/memory/<feedback memory>"])

    def test_orchestrator_notes_alone_do_not_count_as_nai_feedback(self):
        paths = list(REQUIRED_SOURCES) + [f"{_H}/{s}/memory/f.md" for s in FEEDBACK_SLUGS[1:]]
        self.assertEqual(missing_required_sources(paths),
                         [f"~/.claude/projects/{NAI}/memory/<feedback memory>"])

    def test_coverage_gaps_are_reported(self):
        triage = _fixture_triage()
        triage = [r for r in triage if "Non-negotiables (7)" not in r and PUMPCONTROL not in r]
        triage.append(triage[0])  # duplicate Source cell
        triage.append(f"| `{NOTES[1]}` | stale | — | whole-file row |")
        triage.append(f"| `{_H}/{NAI}/memory/not_inventoried.md` | stale | — | x |")
        inventory, rows, _ = parse_triage_text(_fixture_text(triage=triage))
        found = coverage_findings(inventory, rows)
        self.assertIn(f"two triage rows share the Source cell: `{NOTES[0]}` § §1 Gap analysis", found)
        self.assertIn(f"triage row names a source not in the inventory: "
                      f"{_H}/{NAI}/memory/not_inventoried.md", found)
        self.assertIn(f"inventory source has no triage row: "
                      f"{_H}/{PUMPCONTROL}/memory/feedback_example.md", found)
        self.assertIn(f"source triaged both whole-file and per heading: {NOTES[1]}", found)
        self.assertIn(f"note triaged as a whole file instead of per heading: {NOTES[1]}", found)
        self.assertTrue(any(f.startswith(f"{GLOBAL_AGENTS} rows are ") for f in found), found)
        self.assertEqual(len(found), 6, found)

    def test_unknown_class_is_rejected(self):
        self.assertEqual(triage_row_findings(_row(cls="generic")),
                         ["unknown class 'generic' (`~/.claude/AGENTS.md` § Non-negotiables (1))"])

    def test_unknown_stack_is_rejected(self):
        self.assertEqual(len(triage_row_findings(_row(cls="stack:electronics"))), 1)
        self.assertIn("unknown stack", triage_row_findings(_row(cls="stack:electronics"))[0])

    def test_stale_without_note_or_dash_is_rejected(self):
        found = triage_row_findings(_row(cls="stale", dest="skills-src/x.md", note=""))
        self.assertEqual(len(found), 2, found)
        self.assertIn("stale destination must be exactly '—'", found[0])
        self.assertIn("stale row carries no Note", found[1])
        self.assertEqual(triage_row_findings(_row(cls="stale", dest="—", note="superseded")), [])

    def test_common_into_crucible_imported_bundle_is_rejected(self):
        for dest in ("`skills-src/crucible-report-rust/SKILL.md` § Ingest",
                     "`skills-src/crucible-register/SKILL.md` § Register"):
            found = triage_row_findings(_row(dest=dest))
            self.assertEqual(len(found), 1, found)
            self.assertIn("Crucible-owned imported bundle", found[0])
        # the Model B-owned `crucible` bundle is allowed
        self.assertEqual(triage_row_findings(_row(dest="`skills-src/crucible/SKILL.md` § Verbs")), [])

    def test_common_outside_model_b_bundles_or_without_section_is_rejected(self):
        self.assertIn("not in a Model B-owned bundle", triage_row_findings(
            _row(dest="`skills-src/code-health/SKILL.md` § Checks"))[0])
        self.assertIn("is not '`skills-src/...md` § <section>'", triage_row_findings(
            _row(dest="`skills-src/model-b/SKILL.md`"))[0])
        self.assertIn("is not '`skills-src/...md` § <section>'", triage_row_findings(
            _row(dest="skills-src/model-b/SKILL.md § Roles"))[0])

    def test_stack_destination_must_match_its_stack(self):
        self.assertIn("not code-health or the rust orchestration template", triage_row_findings(
            _row(cls="stack:rust", dest="`skills-src/memory-templates/java-orchestration.md` § X"))[0])
        self.assertEqual(triage_row_findings(
            _row(cls="stack:java", dest="`skills-src/memory-templates/java-orchestration.md` § X")), [])
        self.assertEqual(len(triage_row_findings(
            _row(cls="stack:bun", dest="`skills-src/model-b/SKILL.md` § X"))), 1)

    def test_project_model_b_needs_agents_md_section_other_projects_any_text(self):
        self.assertEqual(len(triage_row_findings(
            _row(cls="project:model-b", dest="Model B AGENTS.md"))), 1)
        self.assertEqual(triage_row_findings(
            _row(cls="project:model-b", dest="`AGENTS.md` § Testing & QA")), [])
        self.assertEqual(triage_row_findings(_row(cls="project:crucible", dest="Crucible AGENTS.md")), [])
        self.assertEqual(len(triage_row_findings(_row(cls="project:crucible", dest=""))), 1)
        self.assertEqual(len(triage_row_findings(_row(cls="project:", dest="x"))), 1)

    def test_duplicate_must_point_at_a_model_b_skill_section(self):
        self.assertEqual(len(triage_row_findings(_row(cls="duplicate", dest="—"))), 1)
        self.assertEqual(len(triage_row_findings(
            _row(cls="duplicate", dest="`skills-src/crucible-report-bun/SKILL.md` § X"))), 1)
        self.assertEqual(triage_row_findings(
            _row(cls="duplicate", dest="`skills-src/git-workflow/SKILL.md` § Branches")), [])


# ------------------------------------------------------------------ absorb (§S2–§S3) ----

#: C3 adopts ``skills-src/gap-analysis/`` (§S4); its five rows are checked with the rest.
GAP_ANALYSIS_PREFIX = "skills-src/gap-analysis/"
GAP_ANALYSIS_SKILL = "skills-src/gap-analysis/SKILL.md"
#: §S2 introduces this stack template (the triage's two ``stack:arduino`` rows).
ARDUINO_TEMPLATE = "skills-src/memory-templates/arduino-orchestration.md"
MODEL_B_SKILL = "skills-src/model-b/SKILL.md"
MODEL_B_REFERENCES = "skills-src/model-b/references"

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)(?:\s+#+)?\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")
_NEW_SECTION_NOTE = re.compile(r"\bnew (?:file and )?section\b", re.IGNORECASE)
_PROJECT_NAME = re.compile(r"(?<![A-Za-z0-9])(NAI(?![A-Za-z0-9])|Roundhouse(?![A-Za-z0-9])|ORCHESTRATOR-)")
_CR_CITATION = re.compile(r"\bCR-[A-Z]+-\d+")
_DATE_CITATION = re.compile(r"\b20\d\d-\d\d-\d\d\b")


def markdown_headings(text: str) -> list[tuple[int, int, str]]:
    """``(line_index, level, text)`` for every ATX heading outside a fenced code block (a ``# x``
    comment inside a shell fence is not a heading). Heading text is stripped, closing ``#`` s
    dropped."""
    out, fenced = [], False
    for i, line in enumerate(text.splitlines()):
        if _FENCE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        m = _HEADING.match(line)
        if m:
            out.append((i, len(m.group(1)), m.group(2).strip()))
    return out


def section_body(text: str, heading: str) -> str | None:
    """The lines under the first heading whose text equals ``heading`` (stripped), up to the next
    heading of the same or a higher level; ``None`` when no heading matches."""
    headings = markdown_headings(text)
    lines = text.splitlines()
    for n, (idx, level, htext) in enumerate(headings):
        if htext == heading.strip():
            end = next((j for j, lvl, _ in headings[n + 1:] if lvl <= level), len(lines))
            return "\n".join(lines[idx + 1:end])
    return None


def has_rule_body(body: str) -> bool:
    """At least one non-blank line that is not a heading."""
    return any(line.strip() and not _HEADING.match(line) for line in body.splitlines())


def absorbed_destinations(triage: list[dict]) -> list[tuple[dict, str, str]]:
    """``(row, repo-relative file, section)`` for every ``common``, ``stack:*`` and
    ``project:model-b`` row — the gap-analysis bundle's rows included (C3, §S4). A destination
    that does not parse is returned with file ``""`` so the caller reports it rather than
    dropping it."""
    out = []
    for row in triage:
        cls, dest = row["Class"], row["Destination"]
        if cls == "common" or cls.startswith("stack:"):
            m = _SKILL_DEST.match(dest)
            out.append((row, m.group(1), m.group(2).strip()) if m else (row, "", dest))
        elif cls == "project:model-b":
            m = _AGENTS_DEST.match(dest)
            out.append((row, "AGENTS.md", m.group(1).strip()) if m else (row, "", dest))
    return out


def is_new_section_row(row: dict) -> bool:
    """A ``common``/``stack`` row whose Note announces a section C2 creates."""
    return ((row["Class"] == "common" or row["Class"].startswith("stack:"))
            and _NEW_SECTION_NOTE.search(row["Note"]) is not None)


#: CR-MDB-044 §S1: the CR-MDB-042 triage audit is frozen and names a destination heading renamed
#: since. ``(file, heading as the audit names it)`` -> the heading the file now carries. Exactly this
#: one entry; every other triage destination resolves unaided.
HEADING_RENAMES = {
    ("skills-src/model-b/references/orchestration-common.md",
     "Never author code — always dispatch + diff-verify"):
        "Never author code — dispatch with an accurate brief",
}


#: CR-MDB-085 §S6.2: the triage audit stays frozen, and CR-MDB-085 §S3 moves six of its rules out
#: of their memory template. Each such row, keyed by its line in the frozen audit, names the file its
#: rule now lives in and the §S3 anchor phrase(s) it is found by there. For a moved row the gate
#: checks the phrases in the new file INSTEAD OF the old heading, its new-section body and its class
#: rule. Row 191 joined the spec's five by orchestrator ruling: its rules move with §S3.2's bullets.
MOVED_RULES = {
    191: ("generator/stacks/rust.toml",
          ("clippy --crate <c> --tests", "never the exit code", "never a resting state")),
    192: ("generator/stacks/rust.toml", ("from dev-only to production",)),
    211: ("generator/skills/rust-stack/references/e2e-docker-nextest.md",
          ("added to BOTH nextest default-filters",)),
    284: ("generator/stacks/rust.toml", ("verified per dependent crate",)),
    373: ("generator/stacks/arduino.toml",
          ("Verify the exact part", "Hardware identity is the first bring-up gate")),
    384: ("generator/stacks/arduino.toml",
          ("Verify the exact part", "Hardware identity is the first bring-up gate")),
}
#: CR-MDB-085 §S6.2/AC9: the frozen audit's bytes — the moved-rules map never edits it.
TRIAGE_FILE_SHA256 = "01e0ff21c75bfb28bf06a902947781344f1aa875f34ff8abaa3532621c6c7ebb"

#: CR-MDB-060 §S5.2: the triage stays frozen while CR-MDB-060 §S1.1 moves each stack's memory
#: template, headings unchanged, into its stack skill. A destination the audit names by an old
#: template path resolves through this map to the file its rules live in now; the audit's
#: Destination strings and the class rules are left as written.
FILE_MOVES = {
    "skills-src/memory-templates/arduino-orchestration.md":
        "generator/skills/arduino-stack/references/orchestration.md",
    "skills-src/memory-templates/java-orchestration.md":
        "generator/skills/java-stack/references/orchestration.md",
    "skills-src/memory-templates/rust-orchestration.md":
        "generator/skills/rust-stack/references/orchestration.md",
}


def resolve_file(rel: str, root: Path, moves: dict = FILE_MOVES) -> str:
    """The repo-relative file a destination ``rel`` names under ``root``: a moved template's
    reference (``moves``) — unless only the template is on disk, i.e. the move has not landed
    under ``root`` — and every other path as written. A moved template found nowhere resolves to
    its reference, so a missing file is reported where it should be."""
    new = moves.get(rel)
    if new is None:
        return rel
    if (root / rel).is_file() and not (root / new).is_file():
        return rel
    return new


def moved_rule_rows(text: str, moved: dict = MOVED_RULES) -> tuple[dict, list[str]]:
    """``({Source cell: (audit line, row, new file, anchors)}, problems)``: the triage row at each
    line ``moved`` names. A line that is not a row of the ``## Triage`` table is a problem."""
    _, triage, _ = parse_triage_text(text)
    by_source = {row["Source"]: row for row in triage}
    lines = text.splitlines()
    out, problems = {}, []
    for number, (new_file, anchors) in sorted(moved.items()):
        line = lines[number - 1] if 0 < number <= len(lines) else ""
        cells = _cells(line) if line.strip().startswith("|") else []
        row = by_source.get(cells[0]) if cells else None
        if row is None:
            problems.append(f"audit line {number} is not a triage row")
            continue
        out[row["Source"]] = (number, row, new_file, anchors)
    return out, problems


def moved_rule_findings(moved_rows: dict, root: Path) -> list[str]:
    """Each moved row whose new file is missing, or lacks one of its anchor phrases."""
    problems = []
    for number, _row, new_file, anchors in sorted(moved_rows.values(), key=lambda v: v[0]):
        path = root / new_file
        if not path.is_file():
            problems.append(f"row {number}: {new_file} does not exist")
            continue
        text = read_text(path)
        problems += [f"row {number}: {new_file} lacks {anchor!r}" for anchor in anchors
                     if anchor not in text]
    return problems


def moved_rule_departure_findings(moved_rows: dict, root: Path,
                                  moves: dict = FILE_MOVES) -> list[str]:
    """Each moved row whose anchor phrase is still in the memory template it moved out of — the
    template read where it lives now (``resolve_file``, CR-MDB-060 §S5.2)."""
    problems = []
    for number, row, _new_file, anchors in sorted(moved_rows.values(), key=lambda v: v[0]):
        m = _SKILL_DEST.match(row["Destination"])
        rel = resolve_file(m.group(1), root, moves) if m else None
        if rel is None or not (root / rel).is_file():
            continue
        text = read_text(root / rel)
        problems += [f"row {number}: {rel} still carries {anchor!r}" for anchor in anchors
                     if anchor in text]
    return problems


def unmoved(rows_or_targets: list, moved_rows: dict) -> list:
    """Triage rows, or ``(row, file, section)`` targets, without the rows whose rule moved."""
    def source(item):
        return (item[0] if isinstance(item, tuple) else item)["Source"]
    return [item for item in rows_or_targets if source(item) not in moved_rows]


def resolve_heading(rel: str, section_name: str, renames: dict = HEADING_RENAMES) -> str:
    """The heading a destination resolves to: its rename when ``(rel, section)`` is mapped, else
    the section as written."""
    return renames.get((rel, section_name), section_name)


def _renamed_note(section_name: str, resolved: str) -> str:
    return f" (renamed from '{section_name}')" if resolved != section_name else ""


def destination_findings(targets: list[tuple[dict, str, str]], root: Path,
                         renames: dict = HEADING_RENAMES, moves: dict = FILE_MOVES) -> list[str]:
    """Each target whose file is missing or lacks a heading equal to its section — a renamed
    section (``renames``) is looked up under its new heading only, and a moved file (``moves``,
    CR-MDB-060 §S5.2) is read where it lives now."""
    problems = []
    for row, rel, section_name in targets:
        where = f"({row['Source']})"
        if not rel:
            problems.append(f"destination does not parse: {section_name} {where}")
            continue
        found = resolve_file(rel, root, moves)
        path = root / found
        if not path.is_file():
            problems.append(f"{found}: file does not exist {where}")
            continue
        resolved = resolve_heading(rel, section_name, renames)
        if section_body(read_text(path), resolved) is None:
            problems.append(f"{found}: no heading '{resolved}'{_renamed_note(section_name, resolved)} "
                            f"{where}")
    return problems


def new_section_body_findings(targets: list[tuple[dict, str, str]], root: Path,
                              renames: dict = HEADING_RENAMES,
                              moves: dict = FILE_MOVES) -> list[str]:
    """Each new-section target that is missing or carries no rule text under its heading (a
    renamed section is read under its new heading; a moved file where it lives now)."""
    problems = []
    for row, rel, section_name in targets:
        if not is_new_section_row(row):
            continue
        where = f"({row['Source']})"
        path = root / resolve_file(rel, root, moves) if rel else None
        resolved = resolve_heading(rel, section_name, renames)
        body = section_body(read_text(path), resolved) if path and path.is_file() else None
        if body is None:
            problems.append(f"{rel} \u00a7 {section_name}: new section is absent {where}")
        elif not has_rule_body(body):
            problems.append(f"{rel} \u00a7 {section_name}: new section has no body {where}")
    return problems


def is_provenance_citation(line: str) -> bool:
    return _CR_CITATION.search(line) is not None and _DATE_CITATION.search(line) is not None


def project_name_findings(rel: str, text: str) -> list[str]:
    """``NAI`` / ``Roundhouse`` / ``ORCHESTRATOR-`` on a line that is not a dated citation."""
    problems = []
    for n, line in enumerate(text.splitlines(), 1):
        names = _PROJECT_NAME.findall(line)
        if names and not is_provenance_citation(line):
            problems.append(f"{rel}:{n}: names {sorted(set(names))!r} outside a dated "
                            f"provenance citation")
    return problems


def retired_tool_findings(rel: str, text: str) -> list[str]:
    """Each line naming a harness tool retired by CR-MDB-031 (``_count_tools`` vocabulary)."""
    problems = []
    for n, line in enumerate(text.splitlines(), 1):
        tools = _count_tools(line)
        if tools:
            problems.append(f"{rel}:{n}: names retired harness tool(s) {sorted(tools)!r}")
    return problems


def model_b_common_files(root: Path) -> list[Path]:
    return [root / MODEL_B_SKILL] + sorted((root / MODEL_B_REFERENCES).glob("*.md"))


#: The bundles the widened name gate (CR-MDB-042 AC3, amended) leaves out: Crucible's imported
#: bundles (byte-faithful). ``bootstrap/`` and ``shutdown/`` left it at CR-MDB-041 \u00a7S4.
EXEMPT_BUNDLES = ("crucible-register",)
EXEMPT_BUNDLE_PREFIXES = ("crucible-report-",)


def model_b_owned_skill_files(root: Path) -> list[Path]:
    """Every ``skills-src/**/*.md`` Model B owns: all of them but the exempt bundles'."""
    out = []
    for path in sorted((root / "skills-src").rglob("*.md")):
        parts = path.relative_to(root / "skills-src").parts
        if len(parts) > 1 and (parts[0] in EXEMPT_BUNDLES
                               or parts[0].startswith(EXEMPT_BUNDLE_PREFIXES)):
            continue
        out.append(path)
    return out


class AbsorbedDestinationTest(_RealFileMixin):
    #: 63 common + 9 stack:rust + 2 stack:arduino + 4 project:model-b \u2014 the 5 gap-analysis rows
    #: included since C3 adopted the bundle (\u00a7S4; was 73 while they were excluded) \u2014 plus the
    #: Sandesh ``no-cross-project-reads`` memory inventoried at C5 FIX (``common``).
    EXPECTED_TARGETS = 79
    #: The triage's five ``common`` rows destined for ``skills-src/gap-analysis/SKILL.md``.
    EXPECTED_GAP_ANALYSIS_TARGETS = 5

    def test_absorbed_rows_selected_are_every_common_stack_and_model_b_row(self):
        _, triage = self.load()
        targets = absorbed_destinations(triage)
        self.assertEqual(len(targets), self.EXPECTED_TARGETS)
        self.assertEqual([rel for _, rel, _ in targets if not rel], [])
        self.assertEqual(len([rel for _, rel, _ in targets if rel.startswith(GAP_ANALYSIS_PREFIX)]),
                         self.EXPECTED_GAP_ANALYSIS_TARGETS)

    def test_gap_analysis_rows_land_in_the_adopted_bundle_under_their_section_headings(self):
        _, triage = self.load()
        targets = [t for t in absorbed_destinations(triage) if t[1].startswith(GAP_ANALYSIS_PREFIX)]
        self.assertEqual({rel for _, rel, _ in targets}, {GAP_ANALYSIS_SKILL})
        self.assertEqual(len(targets), self.EXPECTED_GAP_ANALYSIS_TARGETS)
        self.assertEqual(destination_findings(targets, REPO_ROOT), [])

    def test_every_absorbed_row_destination_file_carries_its_section_heading(self):
        # MIGRATED (CR-MDB-085 §S6.2): a row whose rule moved is checked by its anchor phrases in
        # its new file (MovedRulesMapTest), not by its old heading.
        _, triage = self.load()
        targets = unmoved(absorbed_destinations(triage), self.moved())
        self.assertEqual(len(targets), self.EXPECTED_TARGETS - MovedRulesMapTest.EXPECTED_ABSORBED)
        self.assertEqual(destination_findings(targets, REPO_ROOT), [])

    def test_arduino_template_keeps_test_tiers_and_its_driver_rules_join_the_arduino_gotchas(self):
        # MIGRATED (CR-MDB-085 §S3.5/§S6.3; was "the template exists with both sections"): "Test
        # tiers and agents" stays; "Hardware drivers" leaves the template and its two rules join
        # arduino.toml's GREEN and FIX gotchas.
        # MIGRATED (CR-MDB-060 §S5.2): the template is read where it lives now (``FILE_MOVES``).
        rel = resolve_file(ARDUINO_TEMPLATE, REPO_ROOT)
        path = REPO_ROOT / rel
        self.assertTrue(path.is_file(), f"CR-MDB-042 \u00a7S2: {rel} does not exist")
        text = read_text(path)
        self.assertIsNotNone(section_body(text, "Test tiers and agents"),
                             f"{rel}: no 'Test tiers and agents'")
        self.assertIsNone(section_body(text, "Hardware drivers"),
                          f"CR-MDB-085 §S3.5: {rel} still carries 'Hardware drivers'")
        gotchas = tomllib.loads(read_text(REPO_ROOT / ARDUINO_STACK))["gotchas"]
        missing = [f"{role}: {anchor!r}" for role in ("green", "fix")
                   for anchor in HARDWARE_DRIVER_ANCHORS if anchor not in gotchas[role]]
        self.assertEqual(missing, [], "CR-MDB-085 §S3.5: arduino.toml's GREEN and FIX gotchas")

    def test_model_b_project_rows_land_in_the_repo_agents_md(self):
        _, triage = self.load()
        targets = [t for t in absorbed_destinations(triage) if t[0]["Class"] == "project:model-b"]
        self.assertEqual(len(targets), 4)
        self.assertEqual({rel for _, rel, _ in targets}, {"AGENTS.md"})
        self.assertEqual(destination_findings(targets, REPO_ROOT), [])


class AbsorbedNewSectionBodyTest(_RealFileMixin):
    #: The triage Summary's "New sections C2 would create" list: 3+4+1+2+1+2+2+1. The five
    #: gap-analysis rows (C3) extend sections the adopted skill already has — none is new, so the
    #: count stays 16 with them selected.
    EXPECTED_NEW_SECTION_ROWS = 16

    def test_new_section_rows_are_the_sixteen_the_triage_summary_lists(self):
        _, triage = self.load()
        rows = [r for r, _, _ in absorbed_destinations(triage) if is_new_section_row(r)]
        self.assertEqual(len(rows), self.EXPECTED_NEW_SECTION_ROWS)

    def test_every_new_section_carries_rule_text_under_its_heading(self):
        # MIGRATED (CR-MDB-085 §S6.2): a row whose rule moved is checked by its anchor phrases in
        # its new file (MovedRulesMapTest), not by a body under its old heading.
        _, triage = self.load()
        targets = unmoved(absorbed_destinations(triage), self.moved())
        self.assertEqual(new_section_body_findings(targets, REPO_ROOT), [])


class HeadingRenameMapTest(_RealFileMixin):
    """CR-MDB-044 §S1: the frozen triage names ``orchestration-common.md`` § "Never author code —
    always dispatch + diff-verify"; the section is retitled "Never author code — dispatch with an
    accurate brief". The gate resolves the old name through ``HEADING_RENAMES`` — exactly one
    entry — and every other destination resolves unaided."""

    OLD = "Never author code — always dispatch + diff-verify"
    NEW = "Never author code — dispatch with an accurate brief"
    #: The triage's ``common`` rows destined for the renamed section (frozen audit).
    EXPECTED_RENAMED_TARGETS = 11

    def _split(self):
        _, triage = self.load()
        targets = absorbed_destinations(triage)
        renamed = [t for t in targets if (t[1], t[2]) in HEADING_RENAMES]
        others = [t for t in targets if (t[1], t[2]) not in HEADING_RENAMES]
        return renamed, others

    def test_rename_map_has_exactly_the_one_orchestration_common_entry(self):
        self.assertEqual(HEADING_RENAMES, {(MODEL_B_COMMON, self.OLD): self.NEW})

    def test_the_renamed_rows_are_the_eleven_that_name_the_old_heading(self):
        renamed, _ = self._split()
        self.assertEqual(len(renamed), self.EXPECTED_RENAMED_TARGETS)
        self.assertEqual({(rel, s) for _, rel, s in renamed}, {(MODEL_B_COMMON, self.OLD)})

    def test_renamed_rows_resolve_through_the_map_to_the_new_heading(self):
        renamed, _ = self._split()
        self.assertEqual(destination_findings(renamed, REPO_ROOT), [])

    def test_renamed_rows_do_not_resolve_unaided_the_old_heading_is_gone(self):
        renamed, _ = self._split()
        found = destination_findings(renamed, REPO_ROOT, renames={})
        self.assertEqual(len(found), self.EXPECTED_RENAMED_TARGETS, found)
        self.assertTrue(all(f"no heading '{self.OLD}'" in f for f in found), found)

    def test_every_other_destination_resolves_unaided(self):
        # MIGRATED (CR-MDB-085 §S6.2): the rows whose rule moved are checked by the moved-rules
        # map instead (was 79 - 11 = 68 rows resolving unaided).
        _, others = self._split()
        others = unmoved(others, self.moved())
        self.assertEqual(len(others), AbsorbedDestinationTest.EXPECTED_TARGETS
                         - self.EXPECTED_RENAMED_TARGETS - MovedRulesMapTest.EXPECTED_ABSORBED)
        self.assertEqual(destination_findings(others, REPO_ROOT, renames={}), [])


#: CR-MDB-085 §S3.5: arduino.toml's stack file, and the two "Hardware drivers" anchor phrases.
ARDUINO_STACK = "generator/stacks/arduino.toml"
HARDWARE_DRIVER_ANCHORS = ("Verify the exact part", "Hardware identity is the first bring-up gate")


class MovedRulesMapTest(_RealFileMixin):
    """CR-MDB-085 §S6.2/AC9 — the frozen triage's moved rules are found by their anchor phrases in
    their new files; the rename map keeps its one entry and the audit is not edited."""

    #: The frozen rows whose rule CR-MDB-085 moves (191 joined the spec's five by ruling).
    EXPECTED_ROWS = (191, 192, 211, 284, 373, 384)
    #: Of them, the rows ``absorbed_destinations`` selects (384 is a ``duplicate``).
    EXPECTED_ABSORBED = 5

    def test_the_map_names_exactly_the_six_frozen_rows_each_a_template_row(self):
        self.assertEqual(tuple(sorted(MOVED_RULES)), self.EXPECTED_ROWS)
        moved = self.moved()
        self.assertEqual(sorted(number for number, _r, _f, _a in moved.values()),
                         list(self.EXPECTED_ROWS))
        for number, row, _new_file, anchors in moved.values():
            with self.subTest(row=number):
                self.assertTrue(anchors)
                self.assertRegex(row["Destination"],
                                 r"^`skills-src/memory-templates/(rust|arduino)-orchestration\.md` § ")
        _, triage = self.load()
        absorbed = [t for t in absorbed_destinations(triage) if t[0]["Source"] in moved]
        self.assertEqual(len(absorbed), self.EXPECTED_ABSORBED)

    def test_each_moved_rule_is_found_by_its_anchor_phrases_in_its_new_file(self):
        self.assertEqual(moved_rule_findings(self.moved(), REPO_ROOT), [],
                         "CR-MDB-085 §S6.2: a moved rule is not in its new file")

    def test_each_moved_rule_has_left_the_template_it_moved_out_of(self):
        self.assertEqual(moved_rule_departure_findings(self.moved(), REPO_ROOT), [],
                         "CR-MDB-085 §S3: a moved rule's anchor phrase is still in its template")

    def test_the_frozen_audit_is_byte_for_byte_unchanged(self):
        self.assertEqual(sha256_bytes(TRIAGE_FILE.read_bytes()), TRIAGE_FILE_SHA256,
                         "CR-MDB-085 §S6.2: the triage audit is frozen — never edited")


def moved_template_targets(triage: list[dict], moves: dict = FILE_MOVES) -> list[tuple[dict, str, str]]:
    """``(row, old template, section)`` for every triage row, of any class, whose Destination
    names a template ``moves`` maps (CR-MDB-060 §S5.2)."""
    out = []
    for row in triage:
        m = _SKILL_DEST.match(row["Destination"])
        if m and m.group(1) in moves:
            out.append((row, m.group(1), m.group(2).strip()))
    return out


class FileMoveMapTest(_RealFileMixin):
    """CR-MDB-060 §S5.2/AC6 — the frozen triage's moved templates resolve through ``FILE_MOVES``
    to their stack skills' ``references/orchestration.md``; the audit is not edited."""

    RUST = "skills-src/memory-templates/rust-orchestration.md"
    #: The frozen rows destined for a moved template, per template (no row names the java one).
    EXPECTED_ROWS_BY_TEMPLATE = {RUST: 12, ARDUINO_TEMPLATE: 4}
    #: Of the sixteen, the rows ``MOVED_RULES`` maps (191, 192, 211, 284, 373 and 384).
    EXPECTED_MOVED = 6
    #: Of the ten left, the rows ``absorbed_destinations`` selects (208, 209, 260, 271 and 362).
    EXPECTED_ABSORBED_UNMOVED = 5

    def _targets(self) -> list:
        _, triage = self.load()
        return moved_template_targets(triage)

    def test_the_map_moves_each_stack_template_to_its_stack_skills_orchestration_reference(self):
        self.assertEqual(FILE_MOVES, ORCHESTRATION_TEMPLATE_MOVES,
                         "CR-MDB-060 §S1.1: the triage's file-move map is §S1.1's table")
        self.assertEqual(FILE_MOVES[self.RUST],
                         "generator/skills/rust-stack/references/orchestration.md")

    def test_the_rows_destined_for_a_moved_template_are_the_frozen_sixteen(self):
        targets = self._targets()
        counts = {}
        for _row, rel, _section in targets:
            counts[rel] = counts.get(rel, 0) + 1
        self.assertEqual(counts, self.EXPECTED_ROWS_BY_TEMPLATE)
        self.assertEqual(len(targets) - len(unmoved(targets, self.moved())), self.EXPECTED_MOVED)

    def test_every_row_destined_for_a_moved_template_resolves_to_its_reference(self):
        # AC6: the audit names the old template; the gate reads the reference it became.
        wrong = sorted({f"{rel} resolves to {resolve_file(rel, REPO_ROOT)}, expected the existing "
                        f"{FILE_MOVES[rel]}" for _row, rel, _section in self._targets()
                        if resolve_file(rel, REPO_ROOT) != FILE_MOVES[rel]
                        or not (REPO_ROOT / FILE_MOVES[rel]).is_file()})
        self.assertEqual(wrong, [], "CR-MDB-060 §S5.2/AC6: a moved template's rows do not resolve "
                                    "to its reference")

    def test_through_the_map_every_unmoved_rows_heading_is_found(self):
        targets = unmoved(self._targets(), self.moved())
        self.assertEqual(len(targets), sum(self.EXPECTED_ROWS_BY_TEMPLATE.values())
                         - self.EXPECTED_MOVED)
        self.assertEqual(destination_findings(targets, REPO_ROOT), [])

    def test_unaided_the_moved_templates_rows_no_longer_resolve_the_templates_are_gone(self):
        # Like the rename map's unaided check: the old template paths are left for good.
        targets = unmoved(self._targets(), self.moved())
        found = destination_findings(targets, REPO_ROOT, moves={})
        self.assertEqual(len(found), len(targets), found)
        self.assertTrue(all(": file does not exist (" in f for f in found), found)

    def _tree(self, side: str) -> Path:
        """A temp copy of every file the destination and departure checks read, each moved
        template placed at its old path (``before``) or at its reference (``after``), read from
        wherever it lives in the repository now."""
        root = Path(tempfile.mkdtemp(prefix=f"mdb-file-moves-{side}-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        _, triage = self.load()
        rels = {rel for _, rel, _ in absorbed_destinations(triage) if rel} | set(FILE_MOVES)
        for rel in sorted(rels):
            src = REPO_ROOT / resolve_file(rel, REPO_ROOT)
            self.assertTrue(src.is_file(), f"{rel}: found neither at its path nor through the map")
            dst = root / (FILE_MOVES.get(rel, rel) if side == "after" else rel)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
        return root

    def test_the_real_destinations_resolve_on_both_sides_of_the_move(self):
        """The map proved both ways over the real files: with every template at its old path and
        with every template at its reference, the destination, new-section-body and departure
        checks find nothing; unaided, the after side loses exactly the absorbed template rows."""
        _, triage = self.load()
        targets = unmoved(absorbed_destinations(triage), self.moved())
        for side in ("before", "after"):
            with self.subTest(side=side):
                root = self._tree(side)
                self.assertEqual(resolve_file(ARDUINO_TEMPLATE, root),
                                 ARDUINO_TEMPLATE if side == "before" else FILE_MOVES[ARDUINO_TEMPLATE])
                self.assertEqual(destination_findings(targets, root), [])
                self.assertEqual(new_section_body_findings(targets, root), [])
                self.assertEqual(moved_rule_departure_findings(self.moved(), root), [])
                unaided = destination_findings(targets, root, moves={})
                expected = 0 if side == "before" else self.EXPECTED_ABSORBED_UNMOVED
                self.assertEqual(len(unaided), expected, unaided)


class ModelBCommonTextNeutralTest(unittest.TestCase):
    """CR-MDB-042 AC3 (widened at 3b6555c): the name and tool gate covers every Model B-owned
    ``skills-src/`` Markdown file, not only the ``model-b`` bundle and ``gap-analysis``."""

    def test_model_b_owned_files_are_every_bundle_but_the_exempt_ones(self):
        files = model_b_owned_skill_files(REPO_ROOT)
        rels = {p.relative_to(REPO_ROOT).as_posix() for p in files}
        for path in model_b_common_files(REPO_ROOT) + [REPO_ROOT / GAP_ANALYSIS_SKILL]:
            self.assertIn(path.relative_to(REPO_ROOT).as_posix(), rels)
        bundles = {rel.split("/")[1] for rel in rels if rel.count("/") > 1}
        # MIGRATED PIN (CR-MDB-041 \u00a7S4): bootstrap/ and shutdown/ are no longer exempt.
        # MIGRATED at CR-MDB-061 (§S8): the chrome-ui-relay bundle is Model B-owned.
        # MIGRATED (CR-MDB-060 §S5.2): the memory-templates bundle is pinned only while a
        # template has not moved (``FILE_MOVES``); once moved, the rust notes are no skills-src/
        # file (widening the gate to generator/skills/ is §S5.1's).
        rust = resolve_file("skills-src/memory-templates/rust-orchestration.md", REPO_ROOT)
        unmoved_bundles = {rel.split("/")[1] for rel in FILE_MOVES
                           if resolve_file(rel, REPO_ROOT) == rel}
        self.assertEqual(bundles, {"bootstrap", "chrome-ui-relay", "code-health", "cr-authoring",
                                   "crucible", "gap-analysis", "git-workflow",
                                   "model-b", "shutdown"} | unmoved_bundles)
        if rust.startswith("skills-src/"):
            self.assertIn(rust, rels)
        else:
            self.assertNotIn("skills-src/memory-templates/rust-orchestration.md", rels)

    def test_model_b_owned_text_names_no_project_or_orchestrator_note(self):
        problems = []
        for path in model_b_owned_skill_files(REPO_ROOT):
            problems += project_name_findings(path.relative_to(REPO_ROOT).as_posix(), read_text(path))
        self.assertEqual(problems, [])

    def test_model_b_owned_text_names_no_retired_harness_tool(self):
        problems = []
        for path in model_b_owned_skill_files(REPO_ROOT):
            problems += retired_tool_findings(path.relative_to(REPO_ROOT).as_posix(), read_text(path))
        self.assertEqual(problems, [])


#: CR-MDB-042 \u00a7S2 rulings (user, 2026-09-26) the shipped skills must state.
MODEL_B_COMMON = f"{MODEL_B_REFERENCES}/orchestration-common.md"
MODEL_B_MAINLINE = f"{MODEL_B_REFERENCES}/orchestration-mainline.md"
MODEL_B_TRACK = f"{MODEL_B_REFERENCES}/orchestration-track.md"
CR_AUTHORING_SKILL = "skills-src/cr-authoring/SKILL.md"
PATCH_CR_FILES = (MODEL_B_MAINLINE, MODEL_B_TRACK, CR_AUTHORING_SKILL)
#: The superseded "fix the spec in the worktree" model, as the shipped text phrased it.
SUPERSEDED_RESPEC_PHRASES = (
    "sends the changes to the owning track, which edits in its worktree",
    "writes the code-level spec in its worktree",
    "a dated scope-reconciliation note",
)
_FIX_INSIDE_VERIFY = re.compile(
    r"\bfix\b[^.\n]{0,80}\b(?:inside|within|under)\b[^.\n]{0,20}\bverify\b(?:[^.\n]{0,10}\bcycle)",
    re.IGNORECASE)


def fix_inside_verify_findings(rel: str, text: str) -> list[str]:
    """Lines that run a FIX inside the VERIFY cycle \u2014 unless the same line says never."""
    return [f"{rel}:{n}: {line.strip()}" for n, line in enumerate(text.splitlines(), 1)
            if _FIX_INSIDE_VERIFY.search(line) and not re.search(r"\bnever\b", line, re.I)]


class ShippedRulingsTest(unittest.TestCase):
    """CR-MDB-042 AC (rulings): the shipped skills state the \u00a7S2 rulings and nothing contradicts
    them \u2014 the mainline and track references and ``cr-authoring`` agree on the patch-CR rule."""

    def _text(self, rel: str) -> str:
        path = REPO_ROOT / rel
        self.assertTrue(path.is_file(), rel)
        return read_text(path)

    def test_mainline_track_and_cr_authoring_each_state_the_patch_cr_rule(self):
        missing = [rel for rel in PATCH_CR_FILES if "patch CR" not in self._text(rel)]
        self.assertEqual(missing, [])

    def test_each_limits_in_worktree_spec_edits_to_status_and_own_contract_defects(self):
        missing = [rel for rel in PATCH_CR_FILES if "own contracts" not in self._text(rel)]
        self.assertEqual(missing, [])

    def test_none_says_a_track_re_specs_its_cr_in_the_worktree(self):
        found = [f"{rel}: {phrase!r}" for rel in PATCH_CR_FILES for phrase in SUPERSEDED_RESPEC_PHRASES
                 if phrase in self._text(rel).lower()]
        self.assertEqual(found, [])

    def test_mainline_never_edits_an_in_progress_spec_on_develop(self):
        self.assertIn("never edits an IN_PROGRESS CR's spec on develop", self._text(MODEL_B_MAINLINE))

    def test_common_gives_an_approved_verify_finding_its_own_fix_cycle(self):
        body = section_body(self._text(MODEL_B_COMMON), "Cycle discipline") or ""
        for phrase in ("own FIX cycle", "cycle-add --kind fix", "never inside the VERIFY cycle"):
            self.assertIn(phrase, body)

    def test_no_owned_skill_runs_a_fix_inside_the_verify_cycle(self):
        found = []
        for path in model_b_owned_skill_files(REPO_ROOT):
            found += fix_inside_verify_findings(path.relative_to(REPO_ROOT).as_posix(), read_text(path))
        self.assertEqual(found, [])


class CapabilityWordingTest(unittest.TestCase):
    """CR-MDB-042 VERIFY F5/F6: stack templates route generator changes to Model B, and the
    ``model-b`` bundle names capabilities, never a harness tool (DN-multi-harness \u00a7D18)."""

    def test_memory_templates_name_no_generator_stacks_path(self):
        # MIGRATED (CR-MDB-060 §S5.2): the stack templates are read where they live now
        # (``FILE_MOVES``); operational-commands.md, a command sheet and no stack template, is
        # dropped by CR-MDB-060 §S2.
        files = [REPO_ROOT / resolve_file(rel, REPO_ROOT) for rel in sorted(FILE_MOVES)]
        self.assertEqual([p.relative_to(REPO_ROOT).as_posix() for p in files if not p.is_file()], [])
        found = [f"{p.relative_to(REPO_ROOT).as_posix()}: {n}" for p in files
                 for n, line in enumerate(read_text(p).splitlines(), 1) if "generator/stacks/" in line]
        self.assertEqual(found, [])

    def test_model_b_bundle_names_no_subagent_tool(self):
        pattern = re.compile(r"`subagent`\s+tool|\bsubagent tool\b")
        found = [f"{p.relative_to(REPO_ROOT).as_posix()}:{n}"
                 for p in sorted((REPO_ROOT / "skills-src" / "model-b").rglob("*.md"))
                 for n, line in enumerate(read_text(p).splitlines(), 1) if pattern.search(line)]
        self.assertEqual(found, [])


class MovedRulesOnSyntheticTextTest(unittest.TestCase):
    """CR-MDB-085 §S6.2 — the moved-rules functions proved both ways on synthetic text."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="mdb-moved-rules-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.text = _fixture_text()
        self.lines = self.text.splitlines()
        # The fixture's stack:rust row, and its line number (1-based).
        self.rust_line = next(n for n, ln in enumerate(self.lines, 1) if "§ §7 Rust overrides" in ln)
        self.rust_source = _cells(self.lines[self.rust_line - 1])[0]

    def _write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_a_mapped_line_resolves_to_its_triage_row_and_a_non_row_line_is_reported(self):
        moved = {self.rust_line: ("new.toml", ("rule phrase",)), 1: ("x.toml", ("y",))}
        rows, problems = moved_rule_rows(self.text, moved)
        self.assertEqual(problems, ["audit line 1 is not a triage row"])
        self.assertEqual(list(rows), [self.rust_source])
        number, row, new_file, anchors = rows[self.rust_source]
        self.assertEqual((number, row["Class"], new_file, anchors),
                         (self.rust_line, "stack:rust", "new.toml", ("rule phrase",)))

    def test_an_inventory_line_is_not_a_triage_row(self):
        inventory_line = next(n for n, ln in enumerate(self.lines, 1) if ln.startswith("| `~/"))
        _, problems = moved_rule_rows(self.text, {inventory_line: ("new.toml", ("p",))})
        self.assertEqual(problems, [f"audit line {inventory_line} is not a triage row"])

    def test_the_anchor_is_found_in_the_new_file_or_reported(self):
        rows, _ = moved_rule_rows(self.text, {self.rust_line: ("g/new.toml", ("one", "two"))})
        n = self.rust_line
        self.assertEqual(moved_rule_findings(rows, self.root),
                         [f"row {n}: g/new.toml does not exist"])
        self._write("g/new.toml", "one only\n")
        self.assertEqual(moved_rule_findings(rows, self.root), [f"row {n}: g/new.toml lacks 'two'"])
        self._write("g/new.toml", "one and two\n")
        self.assertEqual(moved_rule_findings(rows, self.root), [])

    def test_an_anchor_still_in_the_old_template_is_reported(self):
        rows, _ = moved_rule_rows(self.text, {self.rust_line: ("g/new.toml", ("one",))})
        old = "skills-src/memory-templates/rust-orchestration.md"
        self._write(old, "## Gates\n\n- one rule.\n")
        self.assertEqual(moved_rule_departure_findings(rows, self.root),
                         [f"row {self.rust_line}: {old} still carries 'one'"])
        self._write(old, "## Gates\n\n- the rule lives in the rust agent definitions.\n")
        self.assertEqual(moved_rule_departure_findings(rows, self.root), [])

    def test_a_moved_row_leaves_the_destination_check_and_an_unmoved_one_stays(self):
        _, triage, _ = parse_triage_text(self.text)
        rows, _ = moved_rule_rows(self.text, {self.rust_line: ("g/new.toml", ("one",))})
        targets = absorbed_destinations(triage)
        kept = unmoved(targets, rows)
        self.assertEqual(len(kept), len(targets) - 1)
        self.assertNotIn(self.rust_source, [t[0]["Source"] for t in kept])
        self.assertEqual(len(unmoved(triage, rows)), len(triage) - 1)
        self.assertEqual(unmoved(targets, {}), targets)


class FileMoveMapOnSyntheticTreeTest(unittest.TestCase):
    """CR-MDB-060 §S5.2 — ``resolve_file`` and the checks that read through it, proved on both
    sides of a move over a temp tree."""

    OLD = "skills-src/memory-templates/rust-orchestration.md"
    NEW = "generator/skills/rust-stack/references/orchestration.md"
    SRC = "(`~/.claude/AGENTS.md` § Non-negotiables (1))"

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="mdb-file-moves-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def _write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_a_moved_template_resolves_to_its_reference_unless_only_the_template_is_on_disk(self):
        moves = {self.OLD: self.NEW}
        self.assertEqual(resolve_file(self.OLD, self.root, moves), self.NEW)  # neither on disk
        self._write(self.OLD, "## Gates\n")
        self.assertEqual(resolve_file(self.OLD, self.root, moves), self.OLD)  # before the move
        self._write(self.NEW, "## Gates\n")
        self.assertEqual(resolve_file(self.OLD, self.root, moves), self.NEW)  # both: the reference
        (self.root / self.OLD).unlink()
        self.assertEqual(resolve_file(self.OLD, self.root, moves), self.NEW)  # after the move
        self.assertEqual(resolve_file("skills-src/model-b/SKILL.md", self.root, moves),
                         "skills-src/model-b/SKILL.md")
        self.assertEqual(resolve_file(self.OLD, self.root, {}), self.OLD)

    def test_the_destination_check_reads_a_moved_template_at_its_reference(self):
        self._write(self.NEW, "# R\n\n## Gates\n\nRule.\n")
        targets = [_target(self.OLD, "Gates", cls="stack:rust"),
                   _target(self.OLD, "Gone", cls="stack:rust")]
        self.assertEqual(destination_findings(targets, self.root),
                         [f"{self.NEW}: no heading 'Gone' {self.SRC}"])
        self.assertEqual(destination_findings(targets, self.root, moves={}),
                         [f"{self.OLD}: file does not exist {self.SRC}"] * 2)

    def test_the_new_section_body_check_reads_a_moved_template_at_its_reference(self):
        new = "New section. Rule: x."
        self._write(self.NEW, "## Full\n\nRule.\n\n## Empty\n\n## End\n")
        targets = [_target(self.OLD, "Full", cls="stack:rust", note=new),
                   _target(self.OLD, "Empty", cls="stack:rust", note=new)]
        self.assertEqual(new_section_body_findings(targets, self.root),
                         [f"{self.OLD} § Empty: new section has no body {self.SRC}"])
        self.assertEqual(len(new_section_body_findings(targets, self.root, moves={})), 2)

    def test_an_anchor_still_in_the_moved_reference_is_reported_under_the_reference(self):
        text = _fixture_text()
        line = next(n for n, ln in enumerate(text.splitlines(), 1) if "§ §7 Rust overrides" in ln)
        rows, _ = moved_rule_rows(text, {line: ("g/new.toml", ("one",))})
        self._write(self.NEW, "## Gates\n\n- one rule.\n")
        self.assertEqual(moved_rule_departure_findings(rows, self.root, {self.OLD: self.NEW}),
                         [f"row {line}: {self.NEW} still carries 'one'"])
        self.assertEqual(moved_rule_departure_findings(rows, self.root, {}), [])
        self._write(self.NEW, "## Gates\n\n- the rule lives in the rust agent definitions.\n")
        self.assertEqual(moved_rule_departure_findings(rows, self.root, {self.OLD: self.NEW}), [])


def _target(rel: str, section_name: str, cls: str = "common", note: str = "Rule: x.") -> tuple:
    return (_row(cls=cls, dest=f"`{rel}` \u00a7 {section_name}", note=note), rel, section_name)


class AbsorbRulesOnSyntheticTreeTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="mdb-absorb-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def _write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_heading_match_is_exact_any_level_and_ignores_fenced_comments(self):
        text = ("# Title\n\n## 7. Operating rules (every role)\n\nRule.\n\n"
                "```bash\n# Hardware drivers\n```\n#### Deep \u2014 one ##\n")
        self.assertEqual([h for _, _, h in markdown_headings(text)],
                         ["Title", "7. Operating rules (every role)", "Deep \u2014 one"])
        self.assertIsNotNone(section_body(text, "7. Operating rules (every role)"))
        self.assertIsNotNone(section_body(text, " Deep \u2014 one "))
        self.assertIsNone(section_body(text, "7. Operating rules"))  # prefix is not a match
        self.assertIsNone(section_body(text, "Hardware drivers"))  # fenced comment

    def test_section_body_stops_at_same_or_higher_level_heading(self):
        text = "## A\n\n### A1\n\nsub rule\n\n## B\n\nb rule\n"
        self.assertEqual(section_body(text, "A"), "\n### A1\n\nsub rule\n")
        self.assertEqual(section_body(text, "A1"), "\nsub rule\n")
        self.assertEqual(section_body(text, "B"), "\nb rule")

    def test_missing_file_and_missing_heading_are_reported_present_ones_are_not(self):
        # MIGRATED (CR-MDB-060 §S5.2): a moved template found nowhere is reported where it lives
        # now — its reference (``FILE_MOVES``), was the template path.
        self._write("skills-src/model-b/SKILL.md", "# M\n\n## Roles\n\nx\n")
        targets = [_target("skills-src/model-b/SKILL.md", "Roles"),
                   _target("skills-src/model-b/SKILL.md", "Operating rules"),
                   _target(ARDUINO_TEMPLATE, "Hardware drivers", cls="stack:arduino")]
        src = "(`~/.claude/AGENTS.md` \u00a7 Non-negotiables (1))"
        self.assertEqual(destination_findings(targets, self.root), [
            f"skills-src/model-b/SKILL.md: no heading 'Operating rules' {src}",
            "generator/skills/arduino-stack/references/orchestration.md: file does not exist "
            f"{src}",
        ])

    def test_a_mapped_heading_is_looked_up_under_its_new_name_only(self):
        rel = "skills-src/model-b/references/c.md"
        renames = {(rel, "Old name"): "New name"}
        self._write(rel, "## New name\n\nRule.\n\n## Kept\n\nRule.\n")
        targets = [_target(rel, "Old name"), _target(rel, "Kept")]
        src = "(`~/.claude/AGENTS.md` \u00a7 Non-negotiables (1))"
        self.assertEqual(destination_findings(targets, self.root, renames=renames), [])
        # Unaided, the old name is not in the file.
        self.assertEqual(destination_findings(targets, self.root, renames={}),
                         [f"{rel}: no heading 'Old name' {src}"])

    def test_a_mapped_heading_still_carrying_its_old_name_is_reported(self):
        rel = "skills-src/model-b/references/c.md"
        renames = {(rel, "Old name"): "New name"}
        self._write(rel, "## Old name\n\nRule.\n")
        src = "(`~/.claude/AGENTS.md` \u00a7 Non-negotiables (1))"
        self.assertEqual(destination_findings([_target(rel, "Old name")], self.root, renames=renames),
                         [f"{rel}: no heading 'New name' (renamed from 'Old name') {src}"])

    def test_a_rename_applies_only_to_its_own_file(self):
        rel, other = "skills-src/model-b/references/c.md", "skills-src/model-b/references/d.md"
        renames = {(rel, "Old name"): "New name"}
        self._write(other, "## Old name\n\nRule.\n")
        self.assertEqual(resolve_heading(other, "Old name", renames), "Old name")
        self.assertEqual(resolve_heading(rel, "Old name", renames), "New name")
        self.assertEqual(destination_findings([_target(other, "Old name")], self.root, renames=renames), [])

    def test_a_renamed_new_section_is_checked_for_a_body_under_its_new_name(self):
        rel = "skills-src/model-b/references/c.md"
        renames = {(rel, "Old name"): "New name"}
        new = "New section. Rule: x."
        src = "(`~/.claude/AGENTS.md` \u00a7 Non-negotiables (1))"
        self._write(rel, "## Old name\n\nRule.\n\n## New name\n\n## End\n")
        self.assertEqual(new_section_body_findings([_target(rel, "Old name", note=new)], self.root,
                                                   renames=renames),
                         [f"{rel} \u00a7 Old name: new section has no body {src}"])

    def test_selection_includes_gap_analysis_and_maps_model_b_to_agents_md(self):
        rows = [_row(dest="`skills-src/gap-analysis/SKILL.md` \u00a7 Rules"),
                _row(cls="stack:rust", dest="`skills-src/memory-templates/rust-orchestration.md` \u00a7 T"),
                _row(cls="project:model-b", dest="`AGENTS.md` \u00a7 Testing & QA"),
                _row(cls="project:nai", dest="NAI AGENTS.md"),
                _row(cls="duplicate", dest="`skills-src/model-b/SKILL.md` \u00a7 Roles"),
                _row(cls="stale", dest="\u2014", note="retired"),
                _row(dest="skills-src/model-b/SKILL.md")]
        self.assertEqual([(rel, s) for _, rel, s in absorbed_destinations(rows)], [
            (GAP_ANALYSIS_SKILL, "Rules"),
            ("skills-src/memory-templates/rust-orchestration.md", "T"),
            ("AGENTS.md", "Testing & QA"),
            ("", "skills-src/model-b/SKILL.md"),
        ])
        found = destination_findings(absorbed_destinations(rows)[3:], self.root)
        self.assertEqual(len(found), 1, found)
        self.assertIn("destination does not parse", found[0])
        self.assertEqual(len(found), 1, found)
        self.assertIn("destination does not parse", found[0])

    def test_new_section_note_detection(self):
        self.assertTrue(is_new_section_row(_row(note="New section. Rule: x.")))
        self.assertTrue(is_new_section_row(_row(cls="stack:arduino", note="New file and section. Rule: x.")))
        self.assertFalse(is_new_section_row(_row(note="Rule: extend the existing section.")))
        self.assertFalse(is_new_section_row(_row(cls="duplicate", note="New section.")))

    def test_new_section_with_only_a_heading_or_blank_lines_is_reported(self):
        self._write("skills-src/model-b/references/a.md",
                    "## Full\n\nRule: do x.\n\n## Empty\n\n\n## Nested\n\n### Sub\n\n## End\n")
        new = "New section. Rule: x."
        rel = "skills-src/model-b/references/a.md"
        targets = [_target(rel, "Full", note=new), _target(rel, "Empty", note=new),
                   _target(rel, "Nested", note=new), _target(rel, "Missing", note=new),
                   _target(rel, "End", note="Rule: existing section, not checked for a body.")]
        src = "(`~/.claude/AGENTS.md` \u00a7 Non-negotiables (1))"
        self.assertEqual(new_section_body_findings(targets, self.root), [
            f"{rel} \u00a7 Empty: new section has no body {src}",
            f"{rel} \u00a7 Nested: new section has no body {src}",
            f"{rel} \u00a7 Missing: new section is absent {src}",
        ])

    def test_project_names_flagged_unless_on_a_dated_cr_citation_line(self):
        text = ("Never run two NAI orchestrators.\n"
                "Read the ORCHESTRATOR-RULES note first.\n"
                "The Roundhouse board.\n"
                "Learned on NAI (CR-NAI-042, 2026-07-01).\n"
                "Learned on NAI (CR-NAI-042).\n"
                "A DOMAIN or NAIVE word is fine; so is roundhouse in a path.\n")
        self.assertEqual(project_name_findings("x.md", text), [
            at_line("x.md", 1) + ": names ['NAI'] outside a dated provenance citation",
            at_line("x.md", 2) + ": names ['ORCHESTRATOR-'] outside a dated provenance citation",
            at_line("x.md", 3) + ": names ['Roundhouse'] outside a dated provenance citation",
            at_line("x.md", 5) + ": names ['NAI'] outside a dated provenance citation",
        ])

    def test_owned_skill_files_include_bootstrap_shutdown_and_skip_crucible_imports(self):
        # MIGRATED PIN (CR-MDB-041 \u00a7S4): was ..._skip_bootstrap_shutdown_and_crucible_imports.
        for rel in ("skills-src/README.md", "skills-src/model-b/SKILL.md",
                    "skills-src/memory-templates/rust-orchestration.md",
                    "skills-src/bootstrap/SKILL.md", "skills-src/shutdown/SKILL.md",
                    "skills-src/crucible-register/SKILL.md",
                    "skills-src/crucible-report-bun/SKILL.md", "skills-src/crucible/SKILL.md"):
            self._write(rel, "# x\n")
        self.assertEqual([p.relative_to(self.root).as_posix() for p in model_b_owned_skill_files(self.root)],
                         ["skills-src/README.md", "skills-src/bootstrap/SKILL.md",
                          "skills-src/crucible/SKILL.md",
                          "skills-src/memory-templates/rust-orchestration.md",
                          "skills-src/model-b/SKILL.md", "skills-src/shutdown/SKILL.md"])

    def test_fix_inside_verify_is_flagged_unless_the_line_says_never(self):
        text = ("Run the FIX agent inside the same VERIFY cycle.\n"
                "A finding is fixed in its own FIX cycle, never inside the VERIFY cycle.\n"
                "FIX agents run after VERIFY.\n")
        self.assertEqual(fix_inside_verify_findings("x.md", text),
                         [at_line("x.md", 1) + ": Run the FIX agent inside the same VERIFY cycle."])

    def test_retired_harness_tools_flagged_per_line_sandesh_mcp_included(self):
        text = ("Track the plan with TaskList.\n"
                "Send via mcp__sandesh__sandesh_send.\n"
                "Run the `sandesh` CLI; use the subagent tool.\n"
                "Use `Bash` for it.\n")
        self.assertEqual(retired_tool_findings("x.md", text), [
            at_line("x.md", 1) + ": names retired harness tool(s) ['TaskList']",
            at_line("x.md", 2) + ": names retired harness tool(s) ['sandesh_send']",
            at_line("x.md", 4) + ": names retired harness tool(s) ['Bash']",
        ])


# ------------------------------------------------------------------ mapping (\u00a7S5) ----

TRIAGE_REL = TRIAGE_FILE.relative_to(REPO_ROOT).as_posix()
MAPPING_CR = "CR-MDB-042"
#: The three notes, ``~/.claude/AGENTS.md`` and the six projects' feedback memories.
EXPECTED_SOURCE_GROUPS = len(REQUIRED_SOURCES) + len(FEEDBACK_SLUGS)
GAP_ANALYSIS_STORE = "~/.agents/skills/gap-analysis/"
GAP_ANALYSIS_NOW = "skills-src/gap-analysis/"
#: The five Java references by their ORIGINAL names (``tests.test_archive_mapping``).
JAVA_ORIGINALS = tuple(f"~/.claude/memory/{name}.md" for name in (
    "java-coding-standards", "java-testing-practices", "java-modern-syntax",
    "maven-best-practices", "quarkus-patterns"))
_ORIGINAL_REMAINS = re.compile(
    r"\boriginals? remains? in `~/\.claude/memory/` until the user removes (?:it|them)\b",
    re.IGNORECASE)


def _map_now(row: dict) -> str:
    return _unticked(row["now"]).split("#", 1)[0].strip()


def _cites_cr(row: dict) -> bool:
    return MAPPING_CR in {_unticked(t) for t in row["moved_by"].split(",")}


def _feedback_members(slug: str, inventory_paths: Sequence[str]) -> list[str]:
    prefix = f"~/.claude/projects/{slug}/memory/"
    return [p for p in inventory_paths if p.startswith(prefix) and "/" not in p[len(prefix):]
            and not p[len(prefix):].startswith("ORCHESTRATOR-")]


def source_group_mapping_findings(rows: list[dict], inventory_paths: Sequence[str]) -> list[str]:
    """\u00a7S5: one ``absorbed`` row to the triage file per inventory source group \u2014 each note and
    ``~/.claude/AGENTS.md`` by its literal path (the latter naming the Non-negotiables), each
    feedback project by one row covering all of its inventoried memories and no other project's
    \u2014 ten rows in all, every inventory source covered, each citing ``CR-MDB-042``."""
    absorbed = [r for r in rows if _unticked(r["kind"]) == "absorbed" and _map_now(r) == TRIAGE_REL]
    problems = []
    for single in REQUIRED_SOURCES:
        hits = [r for r in absorbed if _unticked(r["old"]) == single]
        if len(hits) != 1:
            problems.append(f"{single}: {len(hits)} absorbed rows map it to {TRIAGE_REL}, "
                            "expected exactly 1")
        elif single == GLOBAL_AGENTS and "Non-negotiables" not in hits[0]["authority"]:
            problems.append(f"{GLOBAL_AGENTS}: the absorbed row's Authority does not name the "
                            "Non-negotiables")
    groups = [r for r in absorbed if _unticked(r["old"]) not in REQUIRED_SOURCES]
    for slug in FEEDBACK_SLUGS:
        members = _feedback_members(slug, inventory_paths)
        if not members:
            problems.append(f"{slug}: the inventory lists no feedback memory")
            continue
        covering = [r for r in groups if all(covers_required(r["old"], p) for p in members)]
        if len(covering) != 1:
            problems.append(f"{slug}: {len(covering)} absorbed rows cover its {len(members)} "
                            "feedback memories, expected exactly 1")
        prefix = f"~/.claude/projects/{slug}/"
        for row in covering:
            foreign = [p for p in inventory_paths
                       if not p.startswith(prefix) and covers_required(row["old"], p)]
            if foreign:
                problems.append(f"{row['old']}: covers another project's source {foreign[0]}")
    if len(absorbed) != EXPECTED_SOURCE_GROUPS:
        problems.append(f"{len(absorbed)} absorbed rows map to {TRIAGE_REL}, expected "
                        f"{EXPECTED_SOURCE_GROUPS}")
    problems += [f"inventory source not covered by an absorbed row: {p}" for p in inventory_paths
                 if not any(covers_required(r["old"], p) for r in absorbed)]
    problems += [f"{r['old']}: Moved by does not cite {MAPPING_CR}" for r in absorbed
                 if not _cites_cr(r)]
    return problems


def gap_analysis_mapping_findings(rows: list[dict]) -> list[str]:
    """\u00a7S5: exactly one ``moved`` directory row ``~/.agents/skills/gap-analysis/`` whose Now is
    ``skills-src/gap-analysis/``, citing ``CR-MDB-042``."""
    hits = [r for r in rows if _unticked(r["old"]).rstrip("/") == GAP_ANALYSIS_STORE.rstrip("/")]
    if len(hits) != 1:
        return [f"{GAP_ANALYSIS_STORE}: {len(hits)} rows, expected exactly 1"]
    row, problems = hits[0], []
    if not _unticked(row["old"]).endswith("/"):
        problems.append(f"{GAP_ANALYSIS_STORE}: the Old path is not the directory row")
    if _unticked(row["kind"]) != "moved":
        problems.append(f"{GAP_ANALYSIS_STORE}: Kind is {_unticked(row['kind'])!r}, expected 'moved'")
    if _map_now(row).rstrip("/") != GAP_ANALYSIS_NOW.rstrip("/"):
        problems.append(f"{GAP_ANALYSIS_STORE}: Now is {_map_now(row)!r}, expected "
                        f"{GAP_ANALYSIS_NOW!r}")
    if not _cites_cr(row):
        problems.append(f"{GAP_ANALYSIS_STORE}: Moved by does not cite {MAPPING_CR}")
    return problems


def java_reference_mapping_findings(rows: list[dict]) -> list[str]:
    """\u00a7S5: every row covering a Java original states that the original remains in
    ``~/.claude/memory/`` until the user removes it."""
    problems = []
    for original in JAVA_ORIGINALS:
        covering = [r for r in rows if covers_required(r["old"], original)]
        if not covering:
            problems.append(f"{original}: no row")
        problems += [f"{original}: the row at line {r['line']} does not state that the original "
                     "remains in `~/.claude/memory/` until the user removes it"
                     for r in covering if not _ORIGINAL_REMAINS.search(r["authority"])]
    return problems


class OrchestratorSourcesMappedTest(_RealFileMixin):
    def _map_rows(self) -> list[dict]:
        _, rows, problems = parse_map(read_text(MAP_PATH))
        self.assertEqual(problems, [], "archive/mapping.md does not parse")
        return rows

    def test_each_inventory_source_group_has_one_absorbed_row_to_the_triage_file(self):
        inventory, _ = self.load()
        paths = [p for p in (inventory_path(r["Source"]) for r in inventory) if p is not None]
        self.assertEqual(source_group_mapping_findings(self._map_rows(), paths), [])

    def test_gap_analysis_store_bundle_has_a_moved_row_to_skills_src(self):
        self.assertEqual(gap_analysis_mapping_findings(self._map_rows()), [])

    def test_java_reference_rows_state_the_originals_remain_until_the_user_removes_them(self):
        self.assertEqual(java_reference_mapping_findings(self._map_rows()), [])


def _map_row(old: str, kind: str = "absorbed", now: str = f"`{TRIAGE_REL}`",
             authority: str = "Model B; triaged rule by rule", moved_by: str = MAPPING_CR,
             line: int = 1) -> dict:
    return {"line": line, "old": f"`{old}`", "kind": kind, "now": now, "authority": authority,
            "moved_by": moved_by}


def _fixture_map_rows() -> list[dict]:
    rows = [_map_row(n) for n in NOTES]
    rows.append(_map_row(GLOBAL_AGENTS, authority="Model B; the Non-negotiables (1)\u2013(7)"))
    rows += [_map_row(f"{_H}/{s}/memory/<topic>.md") for s in FEEDBACK_SLUGS]
    return rows


def _fixture_inventory_paths() -> list[str]:
    paths: list[str] = list(REQUIRED_SOURCES)
    paths += [f"{_H}/{s}/memory/feedback_example.md" for s in FEEDBACK_SLUGS]
    return paths + [f"{_H}/{NAI}/memory/reviewer-must-read-code.md"]


class MappingRulesOnSyntheticRowsTest(unittest.TestCase):
    def test_well_formed_source_group_rows_yield_nothing_and_pass_the_mapping_gate(self):
        rows = _fixture_map_rows()
        self.assertEqual(len(rows), EXPECTED_SOURCE_GROUPS)
        self.assertEqual(source_group_mapping_findings(rows, _fixture_inventory_paths()), [])
        self.assertEqual(check_rows(rows, REPO_ROOT, resolve_shas=False), [])

    def test_a_literal_glob_covers_nothing_so_its_project_is_reported(self):
        rows = _fixture_map_rows()
        rows[-1] = _map_row(f"{_H}/{PUMPCONTROL}/memory/feedback_*.md")
        found = source_group_mapping_findings(rows, _fixture_inventory_paths())
        self.assertEqual(found, [
            f"{PUMPCONTROL}: 0 absorbed rows cover its 1 feedback memories, expected exactly 1",
            f"inventory source not covered by an absorbed row: "
            f"{_H}/{PUMPCONTROL}/memory/feedback_example.md",
        ])

    def test_one_row_for_every_project_is_reported_as_crossing_projects(self):
        rows = _fixture_map_rows()[:4]
        rows.append(_map_row(f"{_H}/{{{','.join(FEEDBACK_SLUGS)}}}/memory/<topic>.md"))
        found = source_group_mapping_findings(rows, _fixture_inventory_paths())
        self.assertEqual(len([f for f in found if "covers another project's source" in f]), 6)
        self.assertIn(f"5 absorbed rows map to {TRIAGE_REL}, expected 10", found)

    def test_global_agents_row_without_non_negotiables_and_uncited_rows_are_reported(self):
        rows = _fixture_map_rows()
        rows[3] = _map_row(GLOBAL_AGENTS, authority="Model B; global rules")
        rows[4] = _map_row(f"{_H}/{NAI}/memory/<topic>.md", moved_by="CR-MDB-041")
        self.assertEqual(source_group_mapping_findings(rows, _fixture_inventory_paths()), [
            f"{GLOBAL_AGENTS}: the absorbed row's Authority does not name the Non-negotiables",
            f"`{_H}/{NAI}/memory/<topic>.md`: Moved by does not cite {MAPPING_CR}",
        ])

    def test_a_note_row_of_another_kind_or_destination_is_missing(self):
        rows = _fixture_map_rows()
        rows[0] = _map_row(NOTES[0], kind="moved")
        rows[1] = _map_row(NOTES[1], now="`skills-src/model-b/references/orchestration-common.md`")
        found = source_group_mapping_findings(rows, _fixture_inventory_paths())
        self.assertIn(f"{NOTES[0]}: 0 absorbed rows map it to {TRIAGE_REL}, expected exactly 1", found)
        self.assertIn(f"{NOTES[1]}: 0 absorbed rows map it to {TRIAGE_REL}, expected exactly 1", found)
        self.assertIn(f"8 absorbed rows map to {TRIAGE_REL}, expected 10", found)

    def test_gap_analysis_row_rules(self):
        good = _map_row(GAP_ANALYSIS_STORE, kind="moved", now=f"`{GAP_ANALYSIS_NOW}`")
        self.assertEqual(gap_analysis_mapping_findings([good]), [])
        self.assertEqual(gap_analysis_mapping_findings([]),
                         [f"{GAP_ANALYSIS_STORE}: 0 rows, expected exactly 1"])
        placeholder = _map_row("~/.agents/skills/<bundle>/", kind="moved", now="`skills-src/`")
        self.assertEqual(gap_analysis_mapping_findings([placeholder]),
                         [f"{GAP_ANALYSIS_STORE}: 0 rows, expected exactly 1"])
        bad = _map_row("~/.agents/skills/gap-analysis", kind="absorbed", now="`skills-src/`",
                       moved_by="CR-MDB-041")
        self.assertEqual(gap_analysis_mapping_findings([bad]), [
            f"{GAP_ANALYSIS_STORE}: the Old path is not the directory row",
            f"{GAP_ANALYSIS_STORE}: Kind is 'absorbed', expected 'moved'",
            f"{GAP_ANALYSIS_STORE}: Now is 'skills-src/', expected {GAP_ANALYSIS_NOW!r}",
            f"{GAP_ANALYSIS_STORE}: Moved by does not cite {MAPPING_CR}",
        ])

    def test_java_rows_must_state_the_originals_remain_until_the_user_removes_them(self):
        family = ("~/.claude/memory/{java-coding-standards,java-testing-practices,"
                  "java-modern-syntax,maven-best-practices,quarkus-patterns}.md")
        silent = _map_row(family, kind="moved", now="`skills-src/memory-templates/`",
                          authority="Model B; all `java-`-prefixed as templates", line=7)
        found = java_reference_mapping_findings([silent])
        self.assertEqual(len(found), 5, found)
        self.assertTrue(all("the row at line 7 does not state" in f for f in found), found)
        stated = dict(silent, authority="Model B; the originals remain in `~/.claude/memory/` "
                                        "until the user removes them")
        self.assertEqual(java_reference_mapping_findings([stated]), [])
        self.assertEqual(java_reference_mapping_findings([]),
                         [f"{p}: no row" for p in JAVA_ORIGINALS])


if __name__ == "__main__":
    unittest.main()
