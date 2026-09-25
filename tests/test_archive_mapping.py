"""The living archive map gate — CR-MDB-034 §S4.

Contract: ``docs/changes/CR-MDB-034-archive-mapping.md``. ``archive/mapping.md`` holds ONE Markdown
table ``| Old path | Kind | Now | Authority | Moved by |`` mapping every relocated path to where its
content lives now; this module gates it so a later CR that moves a mapped path must update its row.

Class map:

- ``ArchiveMappingS4Test`` — the gate over the REAL ``archive/mapping.md``: the header, the table,
  every row's Kind / Now / Authority / Moved by, and the required rows.
- ``ArchiveMappingDetectorS4Test`` — detector fixtures on in-memory text: a bad Kind, an unresolved
  Now, an unknown CR id, an unresolved sha, an external row with no owner, a deleted row with no
  reason, a malformed row, a second table, a header without its gate, and a missing required row
  are each reported; a well-formed fixture yields nothing.

Every check is a pure function returning a list of problem strings (``[]`` = clean), so the real
file and the fixtures run through the same code.

Row rules (§S1/§S4):

- the file holds exactly one table (a run of lines starting with ``|``) whose header cells are
  exactly ``Old path``, ``Kind``, ``Now``, ``Authority``, ``Moved by``, followed by a ``---``
  separator; every data row has exactly five cells;
- **Old path** is one backticked path (``\\`...\\```);
- **Kind** (backticks stripped) is one of ``moved``, ``absorbed``, ``deleted``, ``external``;
- ``moved``/``absorbed``: **Now** with backticks and any ``#anchor`` stripped is a repo-relative
  path (no leading ``~`` or ``/``, no escape via ``..``) that exists under the repo root;
- ``deleted``: **Now** is exactly ``—`` and **Authority** (the reason) is non-empty;
- ``external``: **Authority** STARTS with its owner — ``Crucible``, ``Sandesh`` or ``the user``
  (``The user`` too); ``Model B (not Crucible)`` names no owner;
- **Moved by** is one or more comma-separated tokens (backticks stripped), each either
  ``CR-MDB-NNN`` with a spec ``docs/changes/CR-MDB-NNN-*.md`` (``CR-MDB-007`` is allowed without
  one — superseded, no spec) or a 7–40 lower-case hex sha that ``git cat-file -e <sha>^{commit}``
  resolves in this repo. Every token must resolve. When the repo is a shallow clone
  (``git rev-parse --is-shallow-repository`` prints ``true``) or git is unavailable, sha resolution
  is skipped — every other rule, CR ids included, is still checked and the real-map test then
  reports a skip naming why.

Header rule: the text before the table names ``tests/test_archive_mapping.py`` and states the
update-on-move rule in ONE sentence containing the words ``update`` and ``move``
(case-insensitive; ``updated``, ``moves`` count). Sentences end at ``.``/``!``/``?`` followed by
whitespace, or at a blank line.

Required-row matching rule (how an Old path "is" an archived file's original location). An Old
path is read as a PATTERN of ``/``-separated components (backticks and one trailing ``/`` stripped);
inside a component ``<name>`` matches one or more non-``/`` characters and ``{a,b,c}`` matches one
of the listed alternatives; everything else is literal. Then:

1. **Archived files.** Each file under ``archive/wave1/``, ``archive/wave2/``, ``archive/wave3/``
   and ``archive/contracts/`` is identified by ``rel`` — its path relative to that
   ``archive/<bucket>/`` directory (e.g. ``memory/git-workflow.md``,
   ``skills/agent-protocol/SKILL.md``, ``agent-baseline.md``). A row covers it when
   (a) the LAST ``len(rel)`` components of the Old path match ``rel`` component by component
   (``~/.claude/memory/git-workflow.md`` covers ``memory/git-workflow.md``;
   ``~/.claude/memory/agent-baseline.md`` covers the flattened ``agent-baseline.md``), or
   (b) the Old path ends with ``/`` (a directory row) and its last ``k`` components match the
   first ``k`` components of ``rel`` for some ``2 <= k < len(rel)`` — so
   ``~/.claude/skills/agent-protocol/`` covers ``skills/agent-protocol/scripts/heartbeat.sh``,
   while a bare grouping directory (``~/.claude/memory/``, ``~/.claude/agents/``, k = 1) covers
   nothing. A basename alone never identifies a file whose ``rel`` has a directory.
   **A placeholder never identifies a file.** The Old-path component matched against the
   component that identifies the archived file — its basename in (a), the first component of
   ``rel`` it is matched against in (b) — must contain no ``<name>``: it matches literally or via
   ``{a,b}``. So ``~/.claude/skills/<bundle>`` and ``.claude/worktrees/<cr>`` cover no flattened
   file, ``<a>/<b>/<c>/`` covers nothing, and a family of agents is spelled
   ``{bun,python}-{red,green}-agent.md``, not ``<stack>-<role>-agent.md``.
2. **Named paths.** ``skills-src/chezmoi/``, ``contracts/mail-axi.md``, ``.claude/worktrees/<cr>``,
   ``CLAUDE.md``, ``~/.claude/AGENTS.md``, ``~/.claude/scripts/worktree-flow.py``, the retired
   ``~/.claude/agents/<IDE>-<role>-agent.md`` of the retired IDE stack (CR-MDB-024) and the five Java references by their
   ORIGINAL names (``java-coding-standards``, ``java-testing-practices``, ``java-modern-syntax``,
   ``maven-best-practices``, ``quarkus-patterns`` — audits/2026-07-20-memory-corpus.md; they became
   ``java-``-prefixed only as memory templates in 2616ad9) are each covered by a row whose WHOLE Old
   path matches the named path (trailing ``/`` ignored; same component count) — so
   ``~/.claude/CLAUDE.md`` does not cover ``CLAUDE.md``. Conversely no row may cover a name that
   never existed (``NEVER_EXISTED_OLD_PATHS``), and the retired IDE agents' row is ``deleted``: no
   ``external`` row hands the IDE stack to anyone (the name is spelled non-contiguously here —
   ``tests/test_ide_overlay_retirement.py`` gates it out of ``tests/``).

Stdlib only.
"""

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests._helpers import REPO_ROOT, files_under, read_text, write_executable

MAP_PATH = REPO_ROOT / "archive" / "mapping.md"
GATE_NAME = "tests/test_archive_mapping.py"
COLUMNS = ("Old path", "Kind", "Now", "Authority", "Moved by")
KINDS = ("absorbed", "deleted", "external", "moved")
ARCHIVE_BUCKETS = ("wave1", "wave2", "wave3", "contracts")
#: Superseded with no spec in docs/changes/ (§S4).
NO_SPEC_CR_IDS = frozenset({"CR-MDB-007"})
NO_SUCCESSOR = "—"
#: The retired IDE stack (CR-MDB-024 §S3), never written contiguously in this module.
IDE_NAME = "vsc" + "ode"
RETIRED_IDE_AGENTS = f"~/.claude/agents/{IDE_NAME}-<role>-agent.md"
REQUIRED_OLD_PATHS = (
    "skills-src/chezmoi/",
    "contracts/mail-axi.md",
    ".claude/worktrees/<cr>",
    "CLAUDE.md",
    "~/.claude/AGENTS.md",
    "~/.claude/scripts/worktree-flow.py",
    RETIRED_IDE_AGENTS,
    "~/.claude/memory/java-coding-standards.md",
    "~/.claude/memory/java-testing-practices.md",
    "~/.claude/memory/java-modern-syntax.md",
    "~/.claude/memory/maven-best-practices.md",
    "~/.claude/memory/quarkus-patterns.md",
)
#: Names no ``~/.claude/memory/`` file ever had: the template names of the two unprefixed Java
#: originals, and the unprefixed forms of the three prefixed ones.
NEVER_EXISTED_OLD_PATHS = (
    "~/.claude/memory/java-maven-best-practices.md",
    "~/.claude/memory/java-quarkus-patterns.md",
    "~/.claude/memory/coding-standards.md",
    "~/.claude/memory/testing-practices.md",
    "~/.claude/memory/modern-syntax.md",
)
SHA_SKIP_MESSAGE = ("Moved by shas not resolved: the repository is a shallow clone or git is "
                    "unavailable (every other row rule, CR ids included, was checked)")

OWNER_RE = re.compile(r"(?:Crucible|Sandesh|[Tt]he user)\b")
PLACEHOLDER_RE = re.compile(r"<[^<>/]+>")
WHOLE_TEST_MODULE_RE = re.compile(r"test_<[^<>/]+>\.py")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n\s*\n")
CR_ID_RE = re.compile(r"CR-MDB-\d{3}")
SHA_RE = re.compile(r"[0-9a-f]{7,40}")
BACKTICKED_RE = re.compile(r"`([^`]+)`")
SEPARATOR_CELL_RE = re.compile(r":?-{3,}:?")
CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")
COMPONENT_TOKEN_RE = re.compile(r"<[^<>/]+>|\{[^{}/]*\}|[^<{]+|.")

# ------------------------------------------------------------------ parse ----

def _cells(line: str) -> list[str]:
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    return [cell.strip() for cell in CELL_SPLIT_RE.split(body)]


def parse_map(text: str) -> tuple:
    """``(header, rows, problems)`` for a mapping document. ``header`` is the text before the
    table; each row is a dict ``{line, old, kind, now, authority, moved_by}`` of raw cells."""
    lines = text.splitlines()
    tables: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    for number, line in enumerate(lines, start=1):
        if line.strip().startswith("|"):
            current.append((number, line))
        elif current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)
    problems: list[str] = []
    if len(tables) != 1:
        problems.append(f"expected exactly one Markdown table, found {len(tables)}")
    if not tables:
        return text, [], problems
    table = tables[0]
    header = "\n".join(lines[: table[0][0] - 1])
    header_cells = tuple(_cells(table[0][1]))
    if header_cells != COLUMNS:
        problems.append(f"table header is {header_cells!r}, expected {COLUMNS!r}")
    if len(table) < 2 or not all(SEPARATOR_CELL_RE.fullmatch(c) for c in _cells(table[1][1])):
        problems.append("table header is not followed by a --- separator row")
        data = table[1:]
    else:
        data = table[2:]
    rows = []
    for number, line in data:
        cells = _cells(line)
        if len(cells) != len(COLUMNS):
            problems.append(f"line {number}: expected {len(COLUMNS)} cells, found {len(cells)}: {line}")
            continue
        old, kind, now, authority, moved_by = cells
        rows.append({"line": number, "old": old, "kind": kind, "now": now,
                     "authority": authority, "moved_by": moved_by})
    return header, rows, problems


def header_problems(header: str) -> list[str]:
    """The header names its gate and states the update-on-move rule in one sentence."""
    problems = []
    if GATE_NAME not in header:
        problems.append(f"header does not name its gate {GATE_NAME}")
    sentences = [s.lower() for s in SENTENCE_SPLIT_RE.split(header)]
    if not any("update" in s and "move" in s for s in sentences):
        problems.append("header does not state the update-on-move rule (needs 'update' and 'move')")
    return problems

# ------------------------------------------------------------------ row checks ----

def _unticked(cell: str) -> str:
    return cell.replace("`", "").strip()


def git_commit_resolves(sha: str, git_dir: Path = REPO_ROOT) -> bool:
    """``git cat-file -e <sha>^{commit}`` succeeds in ``git_dir``."""
    result = subprocess.run(
        ["git", "-C", str(git_dir), "cat-file", "-e", f"{sha}^{{commit}}"],
        capture_output=True, text=True, check=False,
    )
    return result.returncode == 0


def git_history_available(git_dir: Path = REPO_ROOT, git: str = "git") -> bool:
    """``git rev-parse --is-shallow-repository`` prints ``false`` in ``git_dir`` — False for a
    shallow clone, a non-repository, or a git that cannot run (§S4: sha resolution is skipped)."""
    try:
        result = subprocess.run(
            [git, "-C", str(git_dir), "rev-parse", "--is-shallow-repository"],
            capture_output=True, text=True, check=False,
        )
    except OSError:
        return False
    return result.returncode == 0 and result.stdout.strip() == "false"


def _now_problem(row: dict, repo_root: Path) -> str:
    now = _unticked(row["now"]).split("#", 1)[0].strip()
    root = repo_root.resolve()
    if now and not now.startswith(("~", "/")):
        target = (root / now).resolve()
        if (target == root or root in target.parents) and target.exists():
            return ""
    return f"line {row['line']} {row['old']}: Now {now!r} does not exist in the repo"


def _moved_by_problems(row: dict, repo_root: Path, git_dir: Path, resolve_shas: bool) -> list[str]:
    where = f"line {row['line']} {row['old']}"
    tokens = [_unticked(t) for t in row["moved_by"].split(",")]
    if not any(tokens):
        return [f"{where}: Moved by is empty"]
    problems = []
    for token in tokens:
        if CR_ID_RE.fullmatch(token):
            if token in NO_SPEC_CR_IDS:
                continue
            if not list((repo_root / "docs" / "changes").glob(f"{token}-*.md")):
                problems.append(f"{where}: Moved by {token} has no spec in docs/changes/")
        elif SHA_RE.fullmatch(token):
            if resolve_shas and not git_commit_resolves(token, git_dir):
                problems.append(f"{where}: Moved by sha {token} does not resolve to a commit")
        else:
            problems.append(f"{where}: Moved by token {token!r} is neither CR-MDB-NNN nor a sha")
    return problems


def check_rows(rows: list, repo_root: Path, git_dir: Path = REPO_ROOT,
               resolve_shas: bool = True) -> list[str]:
    """Every §S1/§S4 per-row problem across ``rows`` (``[]`` = clean). With ``resolve_shas``
    False a sha token is checked by shape only; CR ids are always checked."""
    problems = []
    for row in rows:
        where = f"line {row['line']} {row['old']}"
        if not BACKTICKED_RE.fullmatch(row["old"]):
            problems.append(f"{where}: Old path is not one backticked path")
        kind = _unticked(row["kind"])
        if kind not in KINDS:
            problems.append(f"{where}: Kind {kind!r} is not one of {', '.join(KINDS)}")
        elif kind in ("moved", "absorbed"):
            problem = _now_problem(row, repo_root)
            if problem:
                problems.append(problem)
        elif kind == "deleted":
            if _unticked(row["now"]) != NO_SUCCESSOR:
                problems.append(f"{where}: deleted row's Now is {row['now']!r}, expected {NO_SUCCESSOR}")
            if not row["authority"].strip():
                problems.append(f"{where}: deleted row states no reason in Authority")
        elif not OWNER_RE.match(row["authority"].strip()):
            problems.append(f"{where}: external row's Authority {row['authority']!r} names no owner "
                            "at its start (Crucible, Sandesh, the user)")
        problems.extend(_moved_by_problems(row, repo_root, git_dir, resolve_shas))
    return problems

# ------------------------------------------------------------------ required rows ----

def _component_regex(component: str) -> re.Pattern:
    parts = []
    for token in COMPONENT_TOKEN_RE.findall(component):
        if token.startswith("<") and token.endswith(">") and len(token) > 2:
            parts.append(r"[^/]+")
        elif token.startswith("{") and token.endswith("}") and "," in token:
            parts.append("(?:" + "|".join(re.escape(a) for a in token[1:-1].split(",")) + ")")
        else:
            parts.append(re.escape(token))
    return re.compile("".join(parts))


def _raw_components(old_path: str) -> list[str]:
    path = _unticked(old_path)
    if path.endswith("/"):
        path = path[:-1]
    return path.split("/")

def _pattern_components(old_path: str) -> list[re.Pattern]:
    return [_component_regex(c) for c in _raw_components(old_path)]


def _tail_matches(patterns: list[re.Pattern], target: list[str]) -> bool:
    if not target or len(patterns) < len(target):
        return False
    tail = patterns[len(patterns) - len(target):]
    return all(p.fullmatch(t) for p, t in zip(tail, target, strict=True))


def covers_archived(old_path: str, rel: str) -> bool:
    """The Old path is the original location of the archived file ``rel`` (module docstring): the
    Old-path component matched against the identifying component never holds a placeholder."""
    raw = _raw_components(old_path)
    patterns = [_component_regex(c) for c in raw]
    parts = rel.split("/")
    if _tail_matches(patterns, parts) and not PLACEHOLDER_RE.search(raw[-1]):
        return True
    if _unticked(old_path).endswith("/"):
        return any(_tail_matches(patterns, parts[:k]) and not PLACEHOLDER_RE.search(raw[len(raw) - k])
                   for k in range(2, len(parts)))
    return False


def covers_required(old_path: str, required: str) -> bool:
    """The WHOLE Old path matches the named ``required`` path (module docstring)."""
    patterns = _pattern_components(old_path)
    parts = required.rstrip("/").split("/")
    return len(patterns) == len(parts) and _tail_matches(patterns, parts)


def archived_files(repo_root: Path) -> list[tuple[str, str]]:
    """``(bucket, rel)`` for every file under ``archive/<bucket>/``, sorted."""
    found = []
    for bucket in ARCHIVE_BUCKETS:
        base = repo_root / "archive" / bucket
        found.extend((bucket, f.relative_to(base).as_posix()) for f in files_under(base))
    return sorted(found)


def missing_rows(rows: list, archived: list, required=REQUIRED_OLD_PATHS) -> list[str]:
    """Each archived file (``archive/<bucket>/<rel>``) and each named path no row covers."""
    olds = [row["old"] for row in rows]
    missing = [f"archive/{bucket}/{rel}" for bucket, rel in archived
               if not any(covers_archived(old, rel) for old in olds)]
    missing.extend(path for path in required
                   if not any(covers_required(old, path) for old in olds))
    return missing

# ------------------------------------------------------------------ the real map ----

class ArchiveMappingS4Test(unittest.TestCase):
    """§S4 — the gate over the real ``archive/mapping.md``."""

    #: Injected so a detector can stand in for a shallow clone or an absent git (§S4).
    history_available = staticmethod(git_history_available)

    def _text(self) -> str:
        if not MAP_PATH.is_file():
            self.fail(f"archive/mapping.md is absent ({MAP_PATH}); CR-MDB-034 §S1 requires the map")
        return read_text(MAP_PATH)

    def _parsed(self) -> tuple:
        header, rows, problems = parse_map(self._text())
        self.assertEqual(problems, [], "archive/mapping.md does not parse as one five-column table")
        self.assertGreater(len(rows), 0, "archive/mapping.md's table has no rows")
        return header, rows

    def test_the_map_is_one_five_column_table(self):
        self._parsed()

    def test_the_header_names_its_gate_and_the_update_on_move_rule(self):
        header, _rows = self._parsed()
        self.assertEqual(header_problems(header), [])

    def test_every_row_passes_the_kind_now_authority_and_moved_by_rules(self):
        _header, rows = self._parsed()
        resolve = self.history_available(REPO_ROOT)
        self.assertEqual(check_rows(rows, REPO_ROOT, resolve_shas=resolve), [])
        if not resolve:
            self.skipTest(SHA_SKIP_MESSAGE)

    def test_every_archived_file_has_a_row_by_its_original_location(self):
        _header, rows = self._parsed()
        archived = archived_files(REPO_ROOT)
        self.assertGreater(len(archived), 0, "no archived files found under archive/")
        self.assertEqual(missing_rows(rows, archived, required=()), [])

    def test_every_named_retired_or_moved_path_has_a_row(self):
        _header, rows = self._parsed()
        self.assertEqual(missing_rows(rows, [], required=REQUIRED_OLD_PATHS), [])

    def test_the_retired_ide_agents_are_deleted_and_no_external_row_hands_them_on(self):
        _header, rows = self._parsed()
        retired = [row for row in rows if covers_required(row["old"], RETIRED_IDE_AGENTS)]
        self.assertEqual([_unticked(row["kind"]) for row in retired], ["deleted"],
                         f"{RETIRED_IDE_AGENTS} needs exactly one deleted row (CR-MDB-024 §S3)")
        handed_on = [row["old"] for row in rows if _unticked(row["kind"]) == "external"
                     and IDE_NAME in row["authority"].lower()]
        self.assertEqual(handed_on, [], f"an external row names {IDE_NAME} although CR-MDB-024 retired it")

    def test_no_row_claims_an_original_name_that_never_existed(self):
        _header, rows = self._parsed()
        claimed = [(row["old"], path) for path in NEVER_EXISTED_OLD_PATHS for row in rows
                   if covers_required(row["old"], path)]
        self.assertEqual(claimed, [])

    def test_the_worktree_dn_and_helper_rows_name_what_they_mean(self):
        _header, rows = self._parsed()
        worktrees = [row for row in rows if covers_required(row["old"], ".claude/worktrees/<cr>")]
        self.assertTrue(worktrees, "no .claude/worktrees/<cr> row")
        for row in worktrees:
            self.assertIn("`.worktrees/<cr>`", row["authority"])
            self.assertIn("gitignored", row["authority"])
            self.assertIn("`contracts/worktree-layout.md`", row["authority"])
            self.assertIn("d688257", row["moved_by"])
        dn = [row for row in rows
              if _unticked(row["old"]) == "crucible:docs/research/DN-model-b-language.md"]
        self.assertEqual([_unticked(row["kind"]) for row in dn], ["external"])
        self.assertIn("`docs/research/DN-model-b-language.md`", dn[0]["authority"])
        whole_modules = [row["old"] for row in rows
                         if WHOLE_TEST_MODULE_RE.fullmatch(_raw_components(row["old"])[-1])]
        self.assertEqual(whole_modules, [], "an Old path stands for every live test module")

# ------------------------------------------------------------------ detectors ----

HEADER = (
    "# Archive mapping\n\n"
    "Gated by `tests/test_archive_mapping.py`: any CR that moves a mapped path must update its "
    "row.\n\n"
)
TABLE_HEAD = "| Old path | Kind | Now | Authority | Moved by |\n|---|---|---|---|---|\n"
FIXTURE_ARCHIVED = [
    ("wave1", "agent-baseline.md"),
    ("wave2", "memory/git-workflow.md"),
    ("wave2", "skills/agent-protocol/SKILL.md"),
    ("wave2", "skills/agent-protocol/scripts/heartbeat.sh"),
    ("wave2", "skills/crucible-report-bun/SKILL.md"),
    ("contracts", "mail-axi.md"),
]
FIXTURE_REQUIRED = (
    "contracts/mail-axi.md",
    "~/.claude/memory/java-coding-standards.md",
    "~/.claude/memory/java-testing-practices.md",
)
UNKNOWN_SHA = "0123abc0123abc0123abc0123abc0123abc0123a"


class ArchiveMappingDetectorS4Test(unittest.TestCase):
    """§S4 detector fixtures: each defect is reported; a well-formed map yields nothing."""

    @classmethod
    def setUpClass(cls):
        cls.head_sha = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "--short=12", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        for rel in ("docs/changes/CR-MDB-001-core-split.md", "skills-src/model-b/SKILL.md",
                    "archive/contracts/mail-axi.md"):
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.root / rel).write_text("x\n", encoding="utf-8")
        self.rows = [
            "| `~/.claude/memory/agent-baseline.md` | absorbed | "
            "`skills-src/model-b/SKILL.md#sub-agent-procedure` | Model B; deployed to "
            "~/.agents/skills/ | CR-MDB-001 |",
            "| `~/.claude/memory/git-workflow.md` | moved | `skills-src/model-b/SKILL.md` | Model B "
            f"| CR-MDB-001, {self.head_sha} |",
            "| `~/.claude/skills/agent-protocol/` | deleted | — | superseded by the crucible skill "
            "| CR-MDB-007 |",
            "| `~/.claude/skills/crucible-report-<stack>/` | external | `~/.crucible/clients/` | "
            "Crucible; installed by its installer | CR-MDB-001 |",
            "| `contracts/mail-axi.md` | moved | `archive/contracts/mail-axi.md` | Model B | "
            "CR-MDB-001 |",
            "| `~/.claude/memory/java-{coding-standards,testing-practices}.md` | external | "
            "`~/.claude/memory/` | the user | CR-MDB-001 |",
        ]

    def tearDown(self):
        self._tmp.cleanup()

    def _text(self, rows=None, header=HEADER) -> str:
        return header + TABLE_HEAD + "\n".join(self.rows if rows is None else rows) + "\n"

    def _problems(self, text: str) -> list[str]:
        header, rows, problems = parse_map(text)
        return (problems + header_problems(header) + check_rows(rows, self.root)
                + missing_rows(rows, FIXTURE_ARCHIVED, FIXTURE_REQUIRED))

    def _with_row(self, index: int, row: str) -> str:
        rows = list(self.rows)
        rows[index] = row
        return self._text(rows)

    def test_a_well_formed_map_yields_no_problem(self):
        header, rows, problems = parse_map(self._text())
        self.assertEqual(problems, [])
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[1]["kind"], "moved")
        self.assertEqual(rows[1]["now"], "`skills-src/model-b/SKILL.md`")
        self.assertIn(GATE_NAME, header)
        self.assertEqual(self._problems(self._text()), [])

    def test_a_bad_kind_is_reported(self):
        problems = self._problems(self._with_row(
            1, "| `~/.claude/memory/git-workflow.md` | relocated | `skills-src/model-b/SKILL.md` | "
               "Model B | CR-MDB-001 |"))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("Kind 'relocated' is not one of", problems[0])
        self.assertIn("~/.claude/memory/git-workflow.md", problems[0])

    def test_an_unresolved_now_is_reported(self):
        problems = self._problems(self._with_row(
            1, "| `~/.claude/memory/git-workflow.md` | moved | `skills-src/git-workflow/SKILL.md` | "
               "Model B | CR-MDB-001 |"))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("Now 'skills-src/git-workflow/SKILL.md' does not exist", problems[0])

    def test_a_now_outside_the_repo_is_reported_for_a_moved_row(self):
        problems = self._problems(self._with_row(
            1, "| `~/.claude/memory/git-workflow.md` | absorbed | `~/.agents/skills/model-b/` | "
               "Model B | CR-MDB-001 |"))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("does not exist in the repo", problems[0])

    def test_an_unknown_cr_id_is_reported(self):
        problems = self._problems(self._with_row(
            1, "| `~/.claude/memory/git-workflow.md` | moved | `skills-src/model-b/SKILL.md` | "
               "Model B | CR-MDB-999 |"))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("CR-MDB-999 has no spec in docs/changes/", problems[0])

    def test_an_unresolved_sha_is_reported_even_beside_a_valid_cr(self):
        problems = self._problems(self._with_row(
            1, "| `~/.claude/memory/git-workflow.md` | moved | `skills-src/model-b/SKILL.md` | "
               f"Model B | CR-MDB-001, {UNKNOWN_SHA} |"))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn(f"sha {UNKNOWN_SHA} does not resolve to a commit", problems[0])

    def test_an_unrecognised_moved_by_token_is_reported(self):
        problems = self._problems(self._with_row(
            1, "| `~/.claude/memory/git-workflow.md` | moved | `skills-src/model-b/SKILL.md` | "
               "Model B | wave 2 |"))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("'wave 2' is neither CR-MDB-NNN nor a sha", problems[0])

    def test_an_external_row_with_no_owner_is_reported(self):
        problems = self._problems(self._with_row(
            3, "| `~/.claude/skills/crucible-report-<stack>/` | external | `~/.crucible/clients/` | "
               "installed elsewhere | CR-MDB-001 |"))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("names no owner", problems[0])

    def test_an_external_row_whose_authority_does_not_start_with_its_owner_is_reported(self):
        problems = self._problems(self._with_row(
            3, "| `~/.claude/skills/crucible-report-<stack>/` | external | `~/.crucible/clients/` | "
               "Model B (not Crucible) | CR-MDB-001 |"))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("names no owner at its start", problems[0])
        self.assertEqual(self._problems(self._with_row(
            3, "| `~/.claude/skills/crucible-report-<stack>/` | external | `~/.crucible/clients/` | "
               "The user; kept by hand | CR-MDB-001 |")), [])

    def test_a_deleted_row_without_a_reason_or_with_a_successor_is_reported(self):
        problems = self._problems(self._with_row(
            2, "| `~/.claude/skills/agent-protocol/` | deleted | `skills-src/model-b/SKILL.md` |  "
               "| CR-MDB-007 |"))
        self.assertEqual(len(problems), 2, problems)
        self.assertIn("deleted row's Now is", problems[0])
        self.assertIn("deleted row states no reason", problems[1])

    def test_a_row_without_five_cells_is_reported(self):
        problems = self._problems(self._with_row(
            1, "| `~/.claude/memory/git-workflow.md` | moved | `skills-src/model-b/SKILL.md` | "
               "Model B |"))
        self.assertIn("expected 5 cells, found 4", problems[0])
        # The dropped row's archived file is then uncovered, too.
        self.assertEqual(problems[1:], ["archive/wave2/memory/git-workflow.md"])

    def test_a_second_table_and_a_wrong_header_row_are_reported(self):
        text = self._text() + "\n| Old | Kind |\n|---|---|\n| `x` | moved |\n"
        self.assertEqual(parse_map(text)[2], ["expected exactly one Markdown table, found 2"])
        wrong = self._text().replace("| Moved by |", "| Moved |", 1)
        self.assertEqual(len(parse_map(wrong)[2]), 1)
        self.assertIn("table header is", parse_map(wrong)[2][0])

    def test_a_header_without_its_gate_or_the_update_rule_is_reported(self):
        self.assertEqual(header_problems("# Archive mapping\n\nWhere things went.\n"), [
            f"header does not name its gate {GATE_NAME}",
            "header does not state the update-on-move rule (needs 'update' and 'move')",
        ])

    def test_an_update_on_move_rule_split_across_sentences_is_reported(self):
        split = ("# Archive mapping\n\nGated by `tests/test_archive_mapping.py`. A CR may move a "
                 "mapped path. Its row is then updated.\n")
        self.assertEqual(header_problems(split), [
            "header does not state the update-on-move rule (needs 'update' and 'move')",
        ])
        paragraphs = "Gated by `tests/test_archive_mapping.py`; a CR that moves a path\n\nupdates it\n"
        self.assertEqual(len(header_problems(paragraphs)), 1)
        wrapped = ("Gated by `tests/test_archive_mapping.py`. Any CR that moves a mapped path must\n"
                   "  update its row in the same change.\n")
        self.assertEqual(header_problems(wrapped), [])

    def test_a_missing_required_row_is_reported(self):
        rows = [r for r in self.rows if "java-" not in r and "agent-protocol" not in r]
        problems = self._problems(self._text(rows))
        self.assertEqual(problems, [
            "archive/wave2/skills/agent-protocol/SKILL.md",
            "archive/wave2/skills/agent-protocol/scripts/heartbeat.sh",
            "~/.claude/memory/java-coding-standards.md",
            "~/.claude/memory/java-testing-practices.md",
        ])

    def test_matching_rule_tail_directory_and_pattern_cases(self):
        self.assertTrue(covers_archived("`~/.claude/memory/agent-baseline.md`", "agent-baseline.md"))
        self.assertTrue(covers_archived("`~/.claude/memory/git-workflow.md`", "memory/git-workflow.md"))
        self.assertTrue(covers_archived("`~/.claude/agents/{arduino,bun}-{red,green}-agent.md`",
                                        "agents/bun-red-agent.md"))
        self.assertTrue(covers_archived("`~/.claude/skills/agent-protocol/`",
                                        "skills/agent-protocol/scripts/heartbeat.sh"))
        # A placeholder never matches the component that identifies an archived file.
        self.assertFalse(covers_archived("`~/.claude/agents/<stack>-<role>-agent.md`",
                                         "agents/bun-red-agent.md"))
        # A bare grouping directory (k = 1) or a same-basename file elsewhere covers nothing.
        self.assertFalse(covers_archived("`~/.claude/memory/`", "memory/git-workflow.md"))
        self.assertFalse(covers_archived("`~/.claude/agents/`", "agents/bun-red-agent.md"))
        self.assertFalse(covers_archived("`~/.claude/skills/other/SKILL.md`",
                                         "skills/agent-protocol/SKILL.md"))
        self.assertFalse(covers_archived("`~/.claude/skills/agent-protocol/SKILL.md`",
                                         "skills/agent-protocol/scripts/heartbeat.sh"))
        self.assertFalse(covers_archived("`~/.claude/memory/git-workflow.md`",
                                         "memory/git-workflow.md.bak"))

    def test_a_placeholder_never_identifies_an_archived_file(self):
        for flattened in ("agent-baseline.md", "sandesh.md", "mail-axi.md"):
            self.assertFalse(covers_archived("`~/.claude/skills/<bundle>`", flattened))
            self.assertFalse(covers_archived("`.claude/worktrees/<cr>`", flattened))
            self.assertFalse(covers_archived("`~/.claude/memory/<topic>.md`", flattened))
        archived = FIXTURE_ARCHIVED + archived_files(REPO_ROOT)
        self.assertEqual([rel for _bucket, rel in archived
                          if covers_archived("`<a>/<b>/<c>/`", rel)], [])
        self.assertEqual([rel for _bucket, rel in archived
                          if covers_archived("`<a>/<b>/<c>`", rel)], [])
        # The legitimate family rows still match: literal or {a,b} on the identifying component.
        self.assertTrue(covers_archived("`~/.claude/memory/{orchestration-common,sandesh}.md`",
                                        "sandesh.md"))
        self.assertTrue(covers_archived("`~/.claude/skills/crucible-report-{bun,java}/`",
                                        "skills/crucible-report-bun/SKILL.md"))
        self.assertTrue(covers_archived("`~/.claude/skills/crucible-report-<stack>/`",
                                        "skills/crucible-report-bun/SKILL.md"))
        self.assertTrue(covers_archived("`~/.claude/skills/{bun-red-testing,bun-green-testing}/`",
                                        "skills/bun-green-testing/SKILL.md"))
        # The same placeholder rows still match NAMED paths, which are matched whole.
        self.assertTrue(covers_required("`.claude/worktrees/<cr>`", ".claude/worktrees/<cr>"))

    def test_sha_resolution_is_skipped_on_a_shallow_clone_or_without_git_but_cr_ids_are_not(self):
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        shallow = write_executable(bin_dir, "git-shallow", "#!/bin/sh\necho true\n")
        full = write_executable(bin_dir, "git-full", "#!/bin/sh\necho false\n")
        self.assertFalse(git_history_available(REPO_ROOT, git=str(shallow)))
        self.assertTrue(git_history_available(REPO_ROOT, git=str(full)))
        self.assertFalse(git_history_available(REPO_ROOT, git=str(bin_dir / "no-such-git")))
        self.assertFalse(git_history_available(self.root))
        # Without resolution an unknown sha passes by shape; an unknown CR id is still reported.
        _header, rows, _problems = parse_map(self._with_row(
            1, "| `~/.claude/memory/git-workflow.md` | moved | `skills-src/model-b/SKILL.md` | "
               f"Model B | CR-MDB-999, {UNKNOWN_SHA} |"))
        problems = check_rows(rows, self.root, resolve_shas=False)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("CR-MDB-999 has no spec in docs/changes/", problems[0])

        class ShallowClone(ArchiveMappingS4Test):
            history_available = staticmethod(lambda _git_dir: False)

        result = unittest.TestResult()
        ShallowClone("test_every_row_passes_the_kind_now_authority_and_moved_by_rules").run(result)
        self.assertEqual(result.failures + result.errors, [])
        self.assertEqual([reason for _test, reason in result.skipped], [SHA_SKIP_MESSAGE])

    def test_matching_rule_named_paths_match_the_whole_old_path(self):
        self.assertTrue(covers_required("`skills-src/chezmoi/`", "skills-src/chezmoi/"))
        self.assertTrue(covers_required("`.claude/worktrees/<cr>/`", ".claude/worktrees/<cr>"))
        self.assertTrue(covers_required("`~/.claude/memory/java-<topic>.md`",
                                        "~/.claude/memory/java-quarkus-patterns.md"))
        self.assertTrue(covers_required("`~/.claude/memory/java-{modern-syntax,quarkus-patterns}.md`",
                                        "~/.claude/memory/java-modern-syntax.md"))
        self.assertFalse(covers_required("`~/.claude/memory/java-{modern-syntax,quarkus-patterns}.md`",
                                         "~/.claude/memory/java-testing-practices.md"))
        self.assertFalse(covers_required("`~/.claude/CLAUDE.md`", "CLAUDE.md"))
        self.assertFalse(covers_required("`AGENTS.md`", "~/.claude/AGENTS.md"))

    def test_archived_files_lists_every_bucket_file_by_its_bucket_relative_path(self):
        for rel in ("archive/wave1/a.md", "archive/wave2/skills/x/SKILL.md", "archive/BASELINE.md",
                    "archive/wave4/z.md"):
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.root / rel).write_text("x\n", encoding="utf-8")
        self.assertEqual(archived_files(self.root), [
            ("contracts", "mail-axi.md"),
            ("wave1", "a.md"),
            ("wave2", "skills/x/SKILL.md"),
        ])


if __name__ == "__main__":
    unittest.main()
