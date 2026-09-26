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

- ``AbsorbedDestinationTest`` — every ``common``, ``stack:*`` and ``project:model-b`` row whose
  destination is not under ``skills-src/gap-analysis/`` (adopted, with its rows, in C3): the named
  file exists (``project:model-b`` → the repo ``AGENTS.md``) and carries a Markdown heading, any
  level, whose text equals the row's `` § <section>`` exactly (after stripping); the new
  ``skills-src/memory-templates/arduino-orchestration.md`` exists.
- ``AbsorbedNewSectionBodyTest`` — each ``common``/``stack`` row whose Note says "New section" (or
  "New file and section") has a non-empty body under that heading, up to the next heading of the
  same or a higher level: at least one non-blank line that is not a heading.
- ``ModelBCommonTextNeutralTest`` — no line of ``skills-src/model-b/SKILL.md`` or
  ``skills-src/model-b/references/*.md`` names ``NAI``, ``Roundhouse`` or ``ORCHESTRATOR-`` unless
  the same line is a dated provenance citation (a ``CR-<ACR>-<n>`` id and a ``20YY-MM-DD`` date),
  and none names a harness tool retired by CR-MDB-031 (the vocabulary of
  ``tests.test_client_path_anchoring``, the ``sandesh_*`` MCP tools included).
- ``AbsorbRulesOnSyntheticTreeTest`` — the same pure functions over a temp tree.

Every check is a pure function returning a list of problem strings (``[]`` = clean), so the real
file and the fixtures run through the same code. Out of scope here (later cycles): the
gap-analysis bundle and its rows (C3), the mapping rows.

Stdlib only.
"""

import re
import shutil
import tempfile
import unittest
from collections.abc import Sequence
from pathlib import Path

from tests._helpers import REPO_ROOT, md_section, read_text
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
        _, triage = self.load()
        self.assertEqual(triage_findings(triage), [])

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

#: C3 adopts ``skills-src/gap-analysis/`` (§S4); its rows are checked there, not here.
C3_BUNDLE_PREFIX = "skills-src/gap-analysis/"
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
    ``project:model-b`` row — except the gap-analysis bundle's rows (C3). A destination that does
    not parse is returned with file ``""`` so the caller reports it rather than dropping it."""
    out = []
    for row in triage:
        cls, dest = row["Class"], row["Destination"]
        if cls == "common" or cls.startswith("stack:"):
            m = _SKILL_DEST.match(dest)
            if m and m.group(1).startswith(C3_BUNDLE_PREFIX):
                continue
            out.append((row, m.group(1), m.group(2).strip()) if m else (row, "", dest))
        elif cls == "project:model-b":
            m = _AGENTS_DEST.match(dest)
            out.append((row, "AGENTS.md", m.group(1).strip()) if m else (row, "", dest))
    return out


def is_new_section_row(row: dict) -> bool:
    """A ``common``/``stack`` row whose Note announces a section C2 creates."""
    return ((row["Class"] == "common" or row["Class"].startswith("stack:"))
            and _NEW_SECTION_NOTE.search(row["Note"]) is not None)


def destination_findings(targets: list[tuple[dict, str, str]], root: Path) -> list[str]:
    """Each target whose file is missing or lacks a heading equal to its section."""
    problems = []
    for row, rel, section_name in targets:
        where = f"({row['Source']})"
        if not rel:
            problems.append(f"destination does not parse: {section_name} {where}")
            continue
        path = root / rel
        if not path.is_file():
            problems.append(f"{rel}: file does not exist {where}")
            continue
        if section_body(read_text(path), section_name) is None:
            problems.append(f"{rel}: no heading '{section_name}' {where}")
    return problems


def new_section_body_findings(targets: list[tuple[dict, str, str]], root: Path) -> list[str]:
    """Each new-section target that is missing or carries no rule text under its heading."""
    problems = []
    for row, rel, section_name in targets:
        if not is_new_section_row(row):
            continue
        where = f"({row['Source']})"
        path = root / rel if rel else None
        body = section_body(read_text(path), section_name) if path and path.is_file() else None
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


class AbsorbedDestinationTest(_RealFileMixin):
    #: 63 common + 9 stack:rust + 2 stack:arduino + 4 project:model-b, less the 5 gap-analysis rows.
    EXPECTED_TARGETS = 73

    def test_absorbed_rows_selected_are_every_common_stack_and_model_b_row_but_gap_analysis(self):
        _, triage = self.load()
        targets = absorbed_destinations(triage)
        self.assertEqual(len(targets), self.EXPECTED_TARGETS)
        self.assertEqual([rel for _, rel, _ in targets if not rel], [])
        self.assertEqual([rel for _, rel, _ in targets if rel.startswith(C3_BUNDLE_PREFIX)], [])

    def test_every_absorbed_row_destination_file_carries_its_section_heading(self):
        _, triage = self.load()
        self.assertEqual(destination_findings(absorbed_destinations(triage), REPO_ROOT), [])

    def test_arduino_orchestration_template_exists_with_both_sections(self):
        path = REPO_ROOT / ARDUINO_TEMPLATE
        self.assertTrue(path.is_file(), f"CR-MDB-042 \u00a7S2: {ARDUINO_TEMPLATE} does not exist")
        text = read_text(path)
        for heading in ("Test tiers and agents", "Hardware drivers"):
            self.assertIsNotNone(section_body(text, heading), f"{ARDUINO_TEMPLATE}: no '{heading}'")

    def test_model_b_project_rows_land_in_the_repo_agents_md(self):
        _, triage = self.load()
        targets = [t for t in absorbed_destinations(triage) if t[0]["Class"] == "project:model-b"]
        self.assertEqual(len(targets), 4)
        self.assertEqual({rel for _, rel, _ in targets}, {"AGENTS.md"})
        self.assertEqual(destination_findings(targets, REPO_ROOT), [])


class AbsorbedNewSectionBodyTest(_RealFileMixin):
    #: The triage Summary's "New sections C2 would create" list: 3+4+1+2+1+2+2+1.
    EXPECTED_NEW_SECTION_ROWS = 16

    def test_new_section_rows_are_the_sixteen_the_triage_summary_lists(self):
        _, triage = self.load()
        rows = [r for r, _, _ in absorbed_destinations(triage) if is_new_section_row(r)]
        self.assertEqual(len(rows), self.EXPECTED_NEW_SECTION_ROWS)

    def test_every_new_section_carries_rule_text_under_its_heading(self):
        _, triage = self.load()
        self.assertEqual(new_section_body_findings(absorbed_destinations(triage), REPO_ROOT), [])


class ModelBCommonTextNeutralTest(unittest.TestCase):
    def test_model_b_common_files_are_the_skill_and_its_five_references(self):
        files = model_b_common_files(REPO_ROOT)
        self.assertTrue(all(p.is_file() for p in files), files)
        self.assertEqual(len(files), 6, files)

    def test_model_b_common_text_names_no_project_or_orchestrator_note(self):
        problems = []
        for path in model_b_common_files(REPO_ROOT):
            problems += project_name_findings(path.relative_to(REPO_ROOT).as_posix(), read_text(path))
        self.assertEqual(problems, [])

    def test_model_b_common_text_names_no_retired_harness_tool(self):
        problems = []
        for path in model_b_common_files(REPO_ROOT):
            problems += retired_tool_findings(path.relative_to(REPO_ROOT).as_posix(), read_text(path))
        self.assertEqual(problems, [])


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
        self._write("skills-src/model-b/SKILL.md", "# M\n\n## Roles\n\nx\n")
        targets = [_target("skills-src/model-b/SKILL.md", "Roles"),
                   _target("skills-src/model-b/SKILL.md", "Operating rules"),
                   _target(ARDUINO_TEMPLATE, "Hardware drivers", cls="stack:arduino")]
        src = "(`~/.claude/AGENTS.md` \u00a7 Non-negotiables (1))"
        self.assertEqual(destination_findings(targets, self.root), [
            f"skills-src/model-b/SKILL.md: no heading 'Operating rules' {src}",
            f"{ARDUINO_TEMPLATE}: file does not exist {src}",
        ])

    def test_selection_skips_gap_analysis_and_maps_model_b_to_agents_md(self):
        rows = [_row(dest="`skills-src/gap-analysis/SKILL.md` \u00a7 Rules"),
                _row(cls="stack:rust", dest="`skills-src/memory-templates/rust-orchestration.md` \u00a7 T"),
                _row(cls="project:model-b", dest="`AGENTS.md` \u00a7 Testing & QA"),
                _row(cls="project:nai", dest="NAI AGENTS.md"),
                _row(cls="duplicate", dest="`skills-src/model-b/SKILL.md` \u00a7 Roles"),
                _row(cls="stale", dest="\u2014", note="retired"),
                _row(dest="skills-src/model-b/SKILL.md")]
        self.assertEqual([(rel, s) for _, rel, s in absorbed_destinations(rows)], [
            ("skills-src/memory-templates/rust-orchestration.md", "T"),
            ("AGENTS.md", "Testing & QA"),
            ("", "skills-src/model-b/SKILL.md"),
        ])
        found = destination_findings(absorbed_destinations(rows)[2:], self.root)
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
            "x.md:1: names ['NAI'] outside a dated provenance citation",
            "x.md:2: names ['ORCHESTRATOR-'] outside a dated provenance citation",
            "x.md:3: names ['Roundhouse'] outside a dated provenance citation",
            "x.md:5: names ['NAI'] outside a dated provenance citation",
        ])

    def test_retired_harness_tools_flagged_per_line_sandesh_mcp_included(self):
        text = ("Track the plan with TaskList.\n"
                "Send via mcp__sandesh__sandesh_send.\n"
                "Run the `sandesh` CLI; use the subagent tool.\n"
                "Use `Bash` for it.\n")
        self.assertEqual(retired_tool_findings("x.md", text), [
            "x.md:1: names retired harness tool(s) ['TaskList']",
            "x.md:2: names retired harness tool(s) ['sandesh_send']",
            "x.md:4: names retired harness tool(s) ['Bash']",
        ])


if __name__ == "__main__":
    unittest.main()
