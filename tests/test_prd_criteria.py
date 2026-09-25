"""PRD success criteria, invariants and design sections, measured against the shipped tree.

``docs/research/PRD-model-b-rationalization.md`` is the design contract, and a contract that
disagrees with the queue is worse than a missing one. This module makes three of its §4
criteria executable and pins the PRD text that CR-MDB-035 reconciles (§S1-§S4):

- **Criterion 3 (reference library).** Every ``~/.agents/skills/<path>`` citation in
  ``skills-src/**/*.md`` and ``generator/templates/*`` resolves to a file under
  ``skills-src/`` — the installer deploys ``skills-src/`` to ``~/.agents/skills/``, so an
  unresolved citation is a dangling instruction in every deployed skill or agent.
- **Criterion 1 (always-loaded context).** The ``AGENTS.md`` that ``init`` scaffolds for all
  five stacks in ``multi:3`` mode is at most 100 lines. Driven through the real ``init`` entry
  in a sandbox (``HOME``, ``MODELB_HOME``, ``XDG_DATA_HOME``, ``PI_CODING_AGENT_DIR`` and
  ``--target``/``--modelb-home`` all temporary).
- **The PRD text.** §3 and §4 name no ``CLAUDE.md``, ``chezmoi``, ``Claude Code``, ``Hermes``,
  ``OpenCode`` or ``~/.claude``/``$HOME/.claude`` path outside a dated amendment note (matched
  case-insensitively, ``claude-code`` included); every §4 criterion carries a **Check:**; every
  ``tests/…py`` path §4 names and every repo script a **Check:** invokes (``generator/build.py``)
  exists; the §S1/§S2 content; every §S3 site carries its dated
  ``AMENDED 2026-09-25 (CR-MDB-035…`` line; and outside §1, the header and the amendment notes
  the PRD requires no ``CLAUDE.md``, chezmoi bundle, ``~/.claude`` path or non-Pi harness.

**What counts as a dated amendment note** (the two forms the PRD already uses, CR-MDB-035 §S1
and §S3), exactly:

1. an *italic span* ``*Amended YYYY-MM-DD (…)…*`` — one ``*`` (not ``**``), the word
   ``Amended``, an ISO date, a parenthesised attribution, then any text without ``*`` up to the
   closing ``*``; only the span is a note, the rest of its line is not;
2. an *AMENDED line* — any physical line containing ``AMENDED YYYY-MM-DD (`` (upper case, ISO
   date, opening parenthesis of the attribution); the whole line is a note.

**Two exemptions**, both stated here so the scans are reproducible:

- *Negation.* A term directly preceded by ``no`` (``emits no `CLAUDE.md` ``, ``no
  `~/.claude/scripts` mirror-sync``) states the term's absence, not a requirement, and is not
  reported. §S2 prescribes the invariant "it emits no ``CLAUDE.md``" in §3, so without this the
  §3 scan could never pass.
- *Kept originals* (whole-PRD scan only). §S3 keeps each original sentence and adds a dated
  AMENDED line; a line whose next non-blank line is an AMENDED line is therefore superseded and
  not reported. §3 and §4 get no such exemption — their terms may appear only inside a note.

Every scan has a detector fixture below proving it bites on a defective input and spares a
compliant one. Stdlib only.
"""

import os
import re
import shutil
import site
import tempfile
import unittest
from pathlib import Path

from tests._helpers import md_section, read_text
from tests._helpers import run_module as _run_module
from tests._helpers import write_install_toml as _write_install_toml

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_SRC = REPO_ROOT / "skills-src"
TEMPLATES_DIR = REPO_ROOT / "generator" / "templates"
PRD = REPO_ROOT / "docs" / "research" / "PRD-model-b-rationalization.md"

# ------------------------------------------------------------------ criterion 3 citations ----

#: ``~/.agents/skills/`` followed by a path; a bare ``~/.agents/skills/`` (the store root) names
#: no file and is not a citation.
SKILL_CITATION = re.compile(r"~/\.agents/skills/([A-Za-z0-9_./-]*[A-Za-z0-9_/-])")


def _cited_skill_paths(text: str) -> list:
    """Every path cited as ``~/.agents/skills/<path>`` in ``text``, in order (a trailing ``.``
    is sentence punctuation, not part of the path)."""
    return [m.group(1) for m in SKILL_CITATION.finditer(text)]


def _citation_sources(skills_root: Path, templates_dir: Path) -> list:
    """The files criterion 3 scans: ``<skills_root>/**/*.md`` and ``<templates_dir>/*``."""
    sources = sorted(p for p in skills_root.rglob("*.md") if p.is_file())
    if templates_dir.is_dir():
        sources += sorted(p for p in templates_dir.iterdir() if p.is_file())
    return sources


def _unresolved_skill_citations(sources, skills_root: Path) -> list:
    """``[(source, cited path), …]`` for every citation that does not resolve under
    ``skills_root`` — a file citation must be a file, a ``…/`` citation a directory."""
    unresolved = []
    for source in sources:
        for cited in _cited_skill_paths(read_text(source)):
            target = skills_root / cited
            ok = target.is_dir() if cited.endswith("/") else target.is_file()
            if not ok:
                unresolved.append((str(source), cited))
    return unresolved


class SkillCitationDetectorTest(unittest.TestCase):
    """The criterion-3 detector bites on an unresolved citation and spares a resolved one."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="mdb-prd-citations-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.skills = self.root / "skills-src"
        (self.skills / "alpha" / "references").mkdir(parents=True)
        (self.skills / "alpha" / "SKILL.md").write_text("# alpha\n", encoding="utf-8")
        (self.skills / "alpha" / "references" / "ref.md").write_text("ref\n", encoding="utf-8")
        self.templates = self.root / "templates"
        self.templates.mkdir()

    def test_citation_extraction_drops_sentence_punctuation_and_the_bare_store_root(self):
        text = ("See `~/.agents/skills/alpha/SKILL.md`. Then ~/.agents/skills/alpha/references/ref.md."
                " The store is `~/.agents/skills/`.")
        self.assertEqual(_cited_skill_paths(text),
                         ["alpha/SKILL.md", "alpha/references/ref.md"])

    def test_an_unresolved_citation_in_a_skill_doc_is_reported_and_a_resolved_one_is_not(self):
        doc = self.skills / "alpha" / "references" / "notes.md"
        doc.write_text("Load `~/.agents/skills/alpha/references/ref.md` and "
                       "`~/.agents/skills/alpha/references/missing.md`.\n", encoding="utf-8")
        found = _unresolved_skill_citations(_citation_sources(self.skills, self.templates),
                                            self.skills)
        self.assertEqual(found, [(str(doc), "alpha/references/missing.md")])

    def test_an_unresolved_citation_in_a_template_is_reported(self):
        template = self.templates / "red.md.tmpl"
        template.write_text("- `~/.agents/skills/beta/SKILL.md` (the beta skill)\n",
                            encoding="utf-8")
        found = _unresolved_skill_citations(_citation_sources(self.skills, self.templates),
                                            self.skills)
        self.assertEqual(found, [(str(template), "beta/SKILL.md")])

    def test_a_citation_naming_a_directory_as_a_file_is_reported(self):
        doc = self.skills / "alpha" / "SKILL.md"
        doc.write_text("Read ~/.agents/skills/alpha/references for more.\n", encoding="utf-8")
        found = _unresolved_skill_citations(_citation_sources(self.skills, self.templates),
                                            self.skills)
        self.assertEqual(found, [(str(doc), "alpha/references")])


class ReferenceLibraryCitationsResolveTest(unittest.TestCase):
    """PRD §4 criterion 3 — every ``~/.agents/skills/<path>`` citation in the shipped skill docs
    and agent templates resolves to a file under ``skills-src/``."""

    def test_every_skill_citation_in_skills_src_and_generator_templates_resolves(self):
        sources = _citation_sources(SKILLS_SRC, TEMPLATES_DIR)
        cited = {c for s in sources for c in _cited_skill_paths(read_text(s))}
        # Non-vacuity: the scan must see the citations the agents and skills are known to carry.
        self.assertTrue({"model-b/references/sub-agent-procedure.md",
                         "crucible/SKILL.md"} <= cited,
                        f"criterion 3: the scan found too few citations to mean anything: {cited}")
        unresolved = _unresolved_skill_citations(sources, SKILLS_SRC)
        self.assertEqual(unresolved, [],
                         "criterion 3: these ~/.agents/skills citations name no file under "
                         "skills-src/ (the installer deploys skills-src/ to ~/.agents/skills/)")


# ------------------------------------------------------------------ criterion 1 AGENTS.md ----

ALL_STACKS = ("arduino", "bun", "python", "quarkus", "rust")
AGENTS_MD_LINE_LIMIT = 100


class ScaffoldedAgentsMdLineBudgetTest(unittest.TestCase):
    """PRD §4 criterion 1 — the project ``AGENTS.md`` that ``init`` scaffolds for the five
    generated stacks in ``multi:3`` mode is at most 100 lines. Real ``init`` entry, fully
    sandboxed.

    This is not the largest possible input: the file grows by one skill-freeze line per
    ``--stacks`` token (``java``, which renders no agents of its own, adds a sixth), and neither
    the mode nor the track count changes its length. Measured 2026-09-25: 47 lines here, 48 with
    all six known stack tokens, the same in ``solo``, ``multi:99`` and a monorepo. The budget
    therefore leaves roughly half its lines as margin, far more than the one line per stack
    token that separates this input from the largest one."""

    @classmethod
    def setUpClass(cls):
        user_base = os.environ.get("PYTHONUSERBASE") or site.getuserbase()
        cls._sandbox = Path(tempfile.mkdtemp(prefix="mdb-prd-agents-md-"))
        for sub in ("home", "modelb-home", "xdg", "target"):
            (cls._sandbox / sub).mkdir()
        modelb_home = cls._sandbox / "modelb-home"
        _write_install_toml(str(modelb_home), harnesses=("pi",))
        cls.target = cls._sandbox / "target"
        cls.result = _run_module(
            "--yes", "init",
            "--name", "Budget", "--token", "budget", "--acronym", "BDG",
            "--mode", "multi:3", "--repo-shape", "standalone",
            "--stacks", ",".join(ALL_STACKS), "--owner", "tester",
            "--target", str(cls.target), "--modelb-home", str(modelb_home), "--no-commit",
            env_overrides={
                "HOME": str(cls._sandbox / "home"),
                "MODELB_HOME": str(modelb_home),
                "XDG_DATA_HOME": str(cls._sandbox / "xdg"),
                "PYTHONUSERBASE": user_base,
            },
            timeout=120,
        )
        agents = cls.target / "AGENTS.md"
        cls.text = agents.read_text(encoding="utf-8") if agents.is_file() else ""

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._sandbox, ignore_errors=True)

    def test_init_for_all_five_stacks_in_multi_mode_succeeds_and_writes_agents_md(self):
        self.assertEqual(self.result.returncode, 0,
                         f"precondition: init must succeed; stderr={self.result.stderr[-2000:]!r}")
        self.assertTrue(self.text.strip(), "init must write a non-empty AGENTS.md")
        missing = [s for s in ALL_STACKS if s not in self.text]
        self.assertEqual(missing, [],
                         "the measured AGENTS.md must be the all-stacks one (each stack named)")

    def test_scaffolded_agents_md_is_at_most_100_lines(self):
        lines = len(self.text.splitlines())
        self.assertGreater(lines, 0, "no AGENTS.md was scaffolded — nothing was measured")
        self.assertLessEqual(lines, AGENTS_MD_LINE_LIMIT,
                             f"criterion 1: the scaffolded AGENTS.md is {lines} lines "
                             f"(all five stacks, multi:3); the budget is {AGENTS_MD_LINE_LIMIT}")


# ------------------------------------------------------------------ PRD scans ----

#: Form 1 — the italic span ``*Amended YYYY-MM-DD (…)…*`` (single ``*``, never ``**``).
AMENDED_ITALIC = re.compile(r"(?<!\*)\*Amended \d{4}-\d{2}-\d{2} \([^)]*\)[^*]*\*(?!\*)")
#: Form 2 — a physical line containing ``AMENDED YYYY-MM-DD (``.
AMENDED_LINE = re.compile(r"AMENDED \d{4}-\d{2}-\d{2} \(")
#: A term directly preceded by ``no`` (optionally opening a code span) states an absence.
NEGATED = re.compile(r"\bno\s+`?$")

#: A home-relative ``.claude`` path in any spelling: ``~/.claude``, ``$HOME/.claude``,
#: ``${HOME}/.claude``.
HOME_CLAUDE_PATH = re.compile(r"(?:~|\$HOME|\$\{HOME\})/\.claude\b")
#: The retired names, matched case-insensitively; the harness names also with ``-`` or
#: whitespace between words (``Claude Code``, ``claude-code``, ``CLAUDE CODE``; ``OpenCode``,
#: ``open-code``).
CLAUDE_MD = re.compile(r"CLAUDE\.md", re.I)
CLAUDE_CODE = re.compile(r"\bclaude[\s-]+code\b", re.I)
HERMES = re.compile(r"\bhermes\b", re.I)
OPENCODE = re.compile(r"\bopen-?code\b", re.I)

#: §3/§4 (CR-MDB-035 §S4): these names may appear only inside a dated amendment note.
SECTION_BANNED_TERMS = {
    "CLAUDE.md": CLAUDE_MD,
    "chezmoi": re.compile(r"\bchezmoi\b", re.I),
    "Claude Code": CLAUDE_CODE,
    "Hermes": HERMES,
    "OpenCode": OPENCODE,
    "~/.claude path": HOME_CLAUDE_PATH,
}

#: Whole PRD (acceptance criteria): what a sentence must not REQUIRE — a ``CLAUDE.md``, a
#: chezmoi bundle (the skill, or ``chezmoi diff``/``apply`` as a Model B step), a ``~/.claude``
#: path or a ``.claude/`` harness directory, or a harness other than Pi.
REQUIREMENT_TERMS = {
    "CLAUDE.md": CLAUDE_MD,
    "chezmoi bundle": re.compile(r"`chezmoi`|\bchezmoi\s+(?:skill|bundle|diff|apply)\b"),
    "~/.claude path": HOME_CLAUDE_PATH,
    ".claude/ harness dir": re.compile(r"(?<![~/\w])\.claude/"),
    "Claude Code": CLAUDE_CODE,
    "Hermes": HERMES,
    "OpenCode": OPENCODE,
}


def _blank_amendment_notes(line: str) -> str:
    """``line`` with every amendment note replaced by spaces: the whole line when it is an
    AMENDED line, otherwise each italic ``*Amended …*`` span (offsets are preserved)."""
    if AMENDED_LINE.search(line):
        return " " * len(line)
    return AMENDED_ITALIC.sub(lambda m: " " * len(m.group(0)), line)


def _term_hits(line: str, terms: dict) -> list:
    """The labels of ``terms`` occurring in ``line`` outside amendment notes and not negated."""
    visible = _blank_amendment_notes(line)
    hits = []
    for label, pattern in terms.items():
        for m in pattern.finditer(visible):
            if not NEGATED.search(visible[:m.start()]):
                hits.append(label)
    return hits


def _banned_terms_outside_notes(text: str) -> list:
    """``[(line number within text, term), …]`` for §3/§4: every banned name outside a note.
    Italic notes may wrap, so the scan runs over the joined text and reports line numbers."""
    visible = AMENDED_ITALIC.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)
    found = []
    for number, line in enumerate(visible.splitlines(), start=1):
        found += [(number, term) for term in _term_hits(line, SECTION_BANNED_TERMS)]
    return found


def _prd_regions(text: str) -> tuple:
    """``(header line numbers, §1 line numbers)`` (1-based): the header is every line before
    the first ``## `` heading; §1 runs from ``## 1.`` to the next ``## `` heading."""
    lines = text.splitlines()
    first = next((i for i, line in enumerate(lines) if line.startswith("## ")), len(lines))
    header = set(range(1, first + 1))
    problem = set()
    inside = False
    for number, line in enumerate(lines, start=1):
        if line.startswith("## "):
            inside = line.startswith("## 1.")
        if inside:
            problem.add(number)
    return header, problem


def _unamended_requirements(text: str) -> list:
    """``[(line number, term), …]`` for every REQUIREMENT_TERMS hit outside the header, §1 and
    amendment notes, on a line that is not a kept original (next non-blank line AMENDED)."""
    header, problem = _prd_regions(text)
    visible = AMENDED_ITALIC.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)
    lines = visible.splitlines()
    found = []
    for index, line in enumerate(lines):
        number = index + 1
        if number in header or number in problem:
            continue
        following = next((later for later in lines[index + 1:] if later.strip()), "")
        if AMENDED_LINE.search(following):
            continue
        found += [(number, term) for term in _term_hits(line, REQUIREMENT_TERMS)]
    return found


#: A §4 criterion starts at a column-0 ``N. `` line and runs to the next one.
CRITERION_START = re.compile(r"^(\d+)\.\s")
#: The **Check:** marker — ``Check:`` closing a bold span (``**Check:**`` or
#: ``**Unmet until CR-MDB-040 merges. Check:**``).
CHECK_MARKER = re.compile(r"\bCheck:\*\*")
TESTS_PATH = re.compile(r"\btests/[\w/.-]*?\.py\b")


def _criteria(section: str) -> list:
    """``[(number, text), …]`` for the numbered criteria of a §4 section body."""
    criteria = []
    for line in section.splitlines():
        start = CRITERION_START.match(line)
        if start:
            criteria.append([int(start.group(1)), line])
        elif criteria and not line.startswith("#"):
            criteria[-1][1] += "\n" + line
    return [(number, body.strip()) for number, body in criteria]


def _criteria_without_check(criteria: list) -> list:
    """The numbers of the criteria that carry no **Check:**."""
    return [number for number, body in criteria if not CHECK_MARKER.search(body)]


def _missing_tests_paths(section: str, root: Path) -> list:
    """Every ``tests/…py`` path named in ``section`` that is not a file under ``root``."""
    return sorted({p for p in TESTS_PATH.findall(section) if not (root / p).is_file()})


#: A repo-relative script path (``generator/build.py``, ``scripts/x.sh``): at least one directory
#: component, a ``.py``/``.sh``/``.fish`` suffix, and not the tail of a longer or home path.
REPO_SCRIPT_PATH = re.compile(r"(?<![\w./~$-])((?:[\w-]+/)+[\w.-]+\.(?:py|sh|fish))\b")


def _check_scripts(criteria: list) -> list:
    """Every repo script path a criterion's **Check:** names (the text after the marker)."""
    found = []
    for _number, body in criteria:
        marker = CHECK_MARKER.search(body)
        if marker:
            found += REPO_SCRIPT_PATH.findall(body[marker.end():])
    return found


def _missing_check_scripts(criteria: list, root: Path) -> list:
    """Every repo script a **Check:** invokes that is not a file under ``root``."""
    return sorted({p for p in _check_scripts(criteria) if not (root / p).is_file()})


LIST_ITEM = re.compile(r"^(\s*)(?:[-*]|\d+\.)\s")


def _site_block(section: str, anchor: str) -> str:
    """The text from ``anchor`` to the end of its list item or paragraph block: the anchor's
    line plus following lines up to the next heading or the next list item indented no deeper
    than the anchor's line. ``""`` when ``anchor`` is absent from ``section``."""
    lines = section.splitlines()
    for index, line in enumerate(lines):
        if anchor not in line:
            continue
        indent = len(line) - len(line.lstrip())
        block = [line[line.index(anchor):]]
        for later in lines[index + 1:]:
            item = LIST_ITEM.match(later)
            if later.startswith("#") or (item and len(item.group(1)) <= indent):
                break
            block.append(later)
        return "\n".join(block)
    return ""


#: The CR-MDB-035 amendment line every §S3 site must carry.
CR035_AMENDED = re.compile(r"AMENDED 2026-09-25 \(CR-MDB-035\b[^\n]*")

#: CR-MDB-035 §S3: (site, section heading, anchor in the kept original, a token the AMENDED line
#: must carry — the current design or the CR/DN that moved it, per the §S3 table).
S3_SITES = (
    ("D1 CLAUDE.md-symlink invariant", "### D1 ",
     "**Invariant: `CLAUDE.md` is ALWAYS a symlink to `AGENTS.md`.**", "CR-MDB-031"),
    ("D2 harness-dir symlinks and the chezmoi bundle", "### D2 ",
     "symlinked into harness dirs like `~/.claude/skills/`", "CR-MDB-031"),
    ("D4 chezmoi skill", "### D4 ", "`chezmoi` (new): the add/apply cycle", "CR-MDB-031"),
    ("D9 workshop directory list and chezmoi sentence", "### D9 ",
     "The `model-b` repo is the permanent authoring workspace", "plans/"),
    ("D10.4 CLAUDE.md symlink", "### D10 ",
     "**`CLAUDE.md` as a plain symlink to `AGENTS.md`**", "CR-MDB-031"),
    ("D10 check-in policy", "### D10 ", "**Check-in policy (REQUIRED", "CR-MDB-031"),
    ("D10.7 .claude/settings.json", "### D10 ",
     "Claude Code: the project's `.claude/settings.json`", ".pi/extensions/"),
    ("D10 installer-vs-scaffold split", "### D10 ", "**Installer vs scaffold split", "Pi"),
    ("D10(e) harness roster", "### D10 ", "(e) **Initial harness roster**", "§D14"),
    ("D2 Tier-3 memory/ library", "### D2 ", "the `memory/` reference library",
     "skills-src/memory-templates/"),
    ("D2 global language refs", "### D2 ", "global language refs per D5", "no global memory tier"),
    ("D3 status-report skill", "### D3 ",
     "`bootstrap` / `shutdown` / `code-health` / `status-report` reference `model-b`",
     "no `status-report` bundle"),
    ("D6 generated set (20 files)", "### D6 ", "(20 files)", "rendered per project"),
    ("D6 bespoke list", "### D6 ", "Bespoke (not generated)", "no bespoke agents"),
    ("D7 bundle path crucible:clients/", "### D7 ", "bundle path `crucible:clients/`",
     "~/.crucible/clients/"),
    ("D8 mail-axi contract", "### D8 ", "`mail-axi` (Fastmail/Gmail/Calendar)",
     "archive/contracts/mail-axi.md"),
    ("D10.5 run-context wrapper plumbing", "### D10 ", "the run-context wrapper plumbing",
     "installed Crucible client"),
)


def _sites_without_amendment(text: str, sites=S3_SITES) -> list:
    """``[(site, why), …]`` for every §S3 site whose original is gone, or whose block carries no
    CR-MDB-035 AMENDED line naming its token."""
    problems = []
    for site_name, heading, anchor, token in sites:
        block = _site_block(md_section(text, heading, stop_prefix="#"), anchor)
        if not block:
            problems.append((site_name, "original sentence not found (§S3 keeps it)"))
            continue
        amended = CR035_AMENDED.search(block)
        if not amended:
            problems.append((site_name, "no 'AMENDED 2026-09-25 (CR-MDB-035' line"))
        elif token not in amended.group(0):
            problems.append((site_name, f"the AMENDED line does not name {token!r}"))
    return problems


class PrdScanDetectorTest(unittest.TestCase):
    """The PRD scans bite on defective text and spare compliant text."""

    def test_italic_amendment_span_is_exempt_but_the_rest_of_its_line_is_not(self):
        text = ("1. Context. *Amended 2026-09-25 (CR-MDB-035): was `~/.claude/AGENTS.md` and "
                "`CLAUDE.md`, Claude Code.* **Check:** x\n"
                "2. Needs a `CLAUDE.md` symlink and the chezmoi skill.\n")
        self.assertEqual(_banned_terms_outside_notes(text), [(2, "CLAUDE.md"), (2, "chezmoi")])

    def test_bold_or_undated_amended_text_is_not_a_note(self):
        text = ("- **Amended 2026-09-25 (CR-MDB-035): Hermes.**\n"
                "- *Amended (CR-MDB-035): OpenCode.*\n"
                "- AMENDED 2026-09-25: Claude Code\n")
        self.assertEqual(_banned_terms_outside_notes(text),
                         [(1, "Hermes"), (2, "OpenCode"), (3, "Claude Code")])

    def test_an_amended_line_is_a_note_as_a_whole(self):
        text = "  **AMENDED 2026-09-25 (CR-MDB-035, §D14):** Claude Code, Hermes, OpenCode gone.\n"
        self.assertEqual(_banned_terms_outside_notes(text), [])

    def test_a_wrapped_italic_note_is_exempt_on_every_line(self):
        text = "6. Manifest. *Amended 2026-09-25 (CR-MDB-035): replaces\n   `chezmoi diff`.*\n"
        self.assertEqual(_banned_terms_outside_notes(text), [])

    def test_a_negated_term_is_not_reported_but_a_required_one_is(self):
        text = ("- `AGENTS.md` is the only file; it emits no `CLAUDE.md` (CR-MDB-031).\n"
                "- `CLAUDE.md` symlink invariant — never de-symlinked.\n")
        self.assertEqual(_banned_terms_outside_notes(text), [(2, "CLAUDE.md")])

    def test_criteria_split_and_the_check_marker_forms(self):
        section = ("## 4. Success criteria\n"
                   "1. One. **Check:** `tests/test_a.py`.\n"
                   "2. Two,\n   wrapped. **Unmet until CR-MDB-040 merges. Check:** gate.\n"
                   "3. Three, Check: in prose only.\n")
        criteria = _criteria(section)
        self.assertEqual([n for n, _ in criteria], [1, 2, 3])
        self.assertIn("wrapped", criteria[1][1])
        self.assertEqual(_criteria_without_check(criteria), [3])

    def test_a_named_tests_path_that_does_not_exist_is_reported(self):
        section = ("1. **Check:** `tests/test_suite_hygiene.py`, `tests/test_no_such_module.py` "
                   "(`NoSuchTest`).\n")
        self.assertEqual(_missing_tests_paths(section, REPO_ROOT),
                         ["tests/test_no_such_module.py"])

    def test_whole_prd_scan_spares_header_problem_notes_and_kept_originals(self):
        text = ("# PRD\n**Co-author:** Claude Code\n\n"
                "## 1. Problem\n`CLAUDE.md` bloat under ~/.claude.\n\n"
                "## 2. Design contract\n### D1 — Core\n"
                "- **Invariant: `CLAUDE.md` is ALWAYS a symlink.**\n"
                "  **AMENDED 2026-09-25 (CR-MDB-035, §D14):** no `CLAUDE.md` (CR-MDB-031).\n"
                "- Hook wiring (Claude Code: the project's `.claude/settings.json`).\n"
                "- Roster: pi, Hermes.\n\n"
                "- Installer: no `~/.claude/scripts` mirror-sync; the `chezmoi` skill ships.\n")
        self.assertEqual(_unamended_requirements(text),
                         [(11, ".claude/ harness dir"), (11, "Claude Code"), (12, "Hermes"),
                          (14, "chezmoi bundle")])

    def test_an_original_followed_by_an_unrelated_line_is_not_a_kept_original(self):
        text = ("## 2. Design\n- `CLAUDE.md` symlink.\n- Other bullet.\n"
                "  **AMENDED 2026-09-25 (CR-MDB-035):** something else.\n")
        self.assertEqual(_unamended_requirements(text), [(2, "CLAUDE.md")])

    def test_site_block_ends_at_the_next_sibling_item_and_the_site_check_bites(self):
        text = ("### D10 — Scaffold\n"
                "  4. **`CLAUDE.md` as a plain symlink to `AGENTS.md`** — compat.\n"
                "  5. git init.\n"
                "     **AMENDED 2026-09-25 (CR-MDB-035, CR-MDB-031):** misplaced under item 5.\n")
        site = (("D10.4", "### D10 ", "**`CLAUDE.md` as a plain symlink to `AGENTS.md`**",
                 "CR-MDB-031"),)
        self.assertEqual(_sites_without_amendment(text, site),
                         [("D10.4", "no 'AMENDED 2026-09-25 (CR-MDB-035' line")])
        fixed = text.replace("  5. git init.\n",
                             "     **AMENDED 2026-09-25 (CR-MDB-035, CR-MDB-031):** no "
                             "`CLAUDE.md`.\n  5. git init.\n")
        self.assertEqual(_sites_without_amendment(fixed, site), [])

    def test_site_check_reports_a_deleted_original_and_a_wrong_token(self):
        text = ("### D9 — Workshop\nThe `model-b` repo is the permanent authoring workspace.\n"
                "**AMENDED 2026-09-25 (CR-MDB-035):** the D4 reference is retired.\n"
                "### D4 — Skills\n- `git-workflow` (rewrite).\n")
        sites = (("D9", "### D9 ", "The `model-b` repo is the permanent authoring workspace",
                  "plans/"),
                 ("D4", "### D4 ", "`chezmoi` (new): the add/apply cycle", "CR-MDB-031"))
        self.assertEqual(_sites_without_amendment(text, sites),
                         [("D9", "the AMENDED line does not name 'plans/'"),
                          ("D4", "original sentence not found (§S3 keeps it)")])

    def test_agent_count_bites_on_literal_counts_and_spares_ids_and_versions(self):
        self.assertEqual(
            AGENT_COUNT.findall("`build.py --check` idempotent; 16 agents generated, 13 bespoke "
                                "intact; 20 generated."),
            ["16 agents generated", "13 bespoke", "20 generated"])
        self.assertEqual(
            AGENT_COUNT.findall("CR-MDB-025 moved definitions to per-project rendering; "
                                "release 0.2.2 agents; CR-MDB-024 made rust the fifth "
                                "generated stack."),
            [])

    def test_section_scan_matches_retired_names_case_insensitively_and_home_claude_paths(self):
        text = ("- Wire claude-code, CLAUDE CODE and opencode; a claude.md; HERMES.\n"
                "- Write `$HOME/.claude/settings.json` and `~/.claude/hooks`.\n"
                "- It emits no `claude.md` and no opencode anchor.\n")
        self.assertEqual(_banned_terms_outside_notes(text),
                         [(1, "CLAUDE.md"), (1, "Claude Code"), (1, "Claude Code"), (1, "Hermes"),
                          (1, "OpenCode"), (2, "~/.claude path"), (2, "~/.claude path")])

    def test_whole_prd_scan_matches_case_insensitively_and_home_claude_paths(self):
        text = ("## 2. Design\n- Roster: pi, hermes, claude-code, opencode.\n"
                "- Hooks go to `$HOME/.claude/hooks` and `${HOME}/.claude/skills`.\n")
        self.assertEqual(_unamended_requirements(text),
                         [(2, "Claude Code"), (2, "Hermes"), (2, "OpenCode"),
                          (3, "~/.claude path"), (3, "~/.claude path")])

    def test_a_missing_script_a_check_invokes_is_reported_and_prose_before_check_is_not(self):
        section = ("## 4. Success criteria\n"
                   "1. One. **Check:** `generator/build.py --check`, "
                   "`tests/test_suite_hygiene.py`.\n"
                   "2. Two. **Check:** `python3 generator/no_such_build.py --check`, "
                   "`scripts/gone.sh`.\n"
                   "3. Three cites `generator/also_missing.py` in prose. **Check:** "
                   "`tests/test_suite_hygiene.py`.\n")
        # The tests/…py matcher alone accepted this section: it names no missing tests path.
        self.assertEqual(_missing_tests_paths(section, REPO_ROOT), [])
        self.assertEqual(_missing_check_scripts(_criteria(section), REPO_ROOT),
                         ["generator/no_such_build.py", "scripts/gone.sh"])


# ------------------------------------------------------------------ the PRD itself ----

#: CR-MDB-035 §S1: the bold title each rewritten criterion opens with (2 keeps its text).
CRITERION_OPENINGS = {
    1: "**Always-loaded context.**",
    2: "Zero references",
    3: "**Reference library.**",
    4: "**Generated agents.**",
    5: "**Crucible clients.**",
    6: "**Deployed state matches the manifest.**",
}
#: A literal agent count: ``16 agents``, ``13 bespoke``, ``20 generated``, ``16 agent
#: definitions``. Digits that end an id or version (``CR-MDB-025 moved definitions``) are not a count.
AGENT_COUNT = re.compile(
    r"(?<![\w.-])\d+\s+(?:\w+\s+)?(?:agents?|definitions?|bespoke|generated)\b")


class PrdSectionsThreeAndFourTest(unittest.TestCase):
    """CR-MDB-035 §S4 — §3 and §4 name no retired harness surface outside a dated amendment
    note; every §4 criterion carries a **Check:**; every ``tests/…py`` path in §4 exists."""

    @classmethod
    def setUpClass(cls):
        cls.text = read_text(PRD)
        cls.s3 = md_section(cls.text, "## 3.")
        cls.s4 = md_section(cls.text, "## 4.")

    def test_sections_three_and_four_are_present(self):
        self.assertTrue(self.s3.startswith("## 3. Invariants"), "PRD must keep §3 Invariants")
        self.assertTrue(self.s4.startswith("## 4. Success criteria"),
                        "PRD must keep §4 Success criteria")

    def test_section_three_names_no_retired_surface_outside_an_amendment_note(self):
        self.assertEqual(_banned_terms_outside_notes(self.s3), [],
                         "§S4: PRD §3 (line numbers within §3) names these outside a dated "
                         "amendment note")

    def test_section_four_names_no_retired_surface_outside_an_amendment_note(self):
        self.assertEqual(_banned_terms_outside_notes(self.s4), [],
                         "§S4: PRD §4 (line numbers within §4) names these outside a dated "
                         "amendment note")

    def test_every_section_four_criterion_carries_a_check(self):
        criteria = _criteria(self.s4)
        self.assertTrue(criteria, "§4 has no numbered criteria")
        self.assertEqual(_criteria_without_check(criteria), [],
                         "§S1/§S4: these §4 criteria carry no **Check:** naming how to measure "
                         "them")

    def test_every_tests_path_named_in_section_four_exists(self):
        self.assertTrue(TESTS_PATH.search(self.s4), "§4 names no tests/…py path at all")
        self.assertEqual(_missing_tests_paths(self.s4, REPO_ROOT), [],
                         "§S4: §4 names these tests/…py paths, which do not exist")

    def test_every_repo_script_a_section_four_check_invokes_exists(self):
        criteria = _criteria(self.s4)
        self.assertIn("generator/build.py", _check_scripts(criteria),
                      "non-vacuity: criterion 4's Check invokes generator/build.py")
        self.assertEqual(_missing_check_scripts(criteria, REPO_ROOT), [],
                         "§S4: a §4 **Check:** invokes these repo scripts, which do not exist")


class PrdSuccessCriteriaContentTest(unittest.TestCase):
    """CR-MDB-035 §S1 and its acceptance criteria — the mechanically testable content of §4."""

    @classmethod
    def setUpClass(cls):
        cls.criteria = dict(_criteria(md_section(read_text(PRD), "## 4.")))

    def test_section_four_is_exactly_the_six_s1_criteria_in_order(self):
        self.assertEqual(sorted(self.criteria), [1, 2, 3, 4, 5, 6],
                         "§S1: §4 is exactly six numbered criteria")
        wrong = {n: body[:80] for n, body in self.criteria.items()
                 if not body.startswith(f"{n}. {CRITERION_OPENINGS.get(n, '')}")}
        self.assertEqual(wrong, {}, "§S1: each criterion opens as §S1 writes it "
                                    f"(expected openings {CRITERION_OPENINGS})")

    def test_no_criterion_states_a_literal_agent_count(self):
        counts = {n: AGENT_COUNT.findall(body) for n, body in self.criteria.items()
                  if AGENT_COUNT.search(body)}
        self.assertEqual(counts, {}, "AC: no §4 criterion states a literal agent count")

    def test_criterion_four_is_the_render_and_ownership_property(self):
        body = self.criteria.get(4, "")
        missing = [s for s in ("generator/build.py --check", "generator/stacks/*.toml",
                               "generator/templates/*.md.tmpl", "--force-managed",
                               "CR-MDB-024", "CR-MDB-025")
                   if s not in body]
        self.assertEqual(missing, [], "§S1: criterion 4 states the generation/render property")

    def test_criterion_four_skips_hand_modified_definitions_and_never_writes_unmarked_ones(self):
        body = " ".join(self.criteria.get(4, "").split())
        missing = [s for s in ("a hand-modified definition is skipped unless `--force-managed`",
                               "an unmarked one is never written")
                   if s not in body]
        self.assertEqual(missing, [], "§S1 (amended f395454): criterion 4 states the ownership "
                                      "rule as §S1 writes it")
        self.assertNotIn("never overwrite an unmarked", body,
                         "§S1: an unmarked definition is never written, not merely never "
                         "overwritten")

    def test_criterion_five_splits_the_halves_and_declines_the_vscode_client(self):
        body = self.criteria.get(5, "")
        missing = [s for s in ("Model B's half", "Crucible's half", "vscode-crucible.py",
                               "declined", "#1370", "ClientContractS3Test")
                   if s not in body]
        self.assertEqual(missing, [], "§S1: criterion 5 separates the halves and states "
                                      "vscode-crucible.py as declined (D7, Sandesh #1370)")

    def test_criterion_five_names_the_scanned_surfaces_and_claims_no_manifest_resolution(self):
        body = " ".join(self.criteria.get(5, "").split())
        self.assertIn("every Crucible client invocation in shipped skills, templates, stack "
                      "parameters and contracts matches the released client's surface at "
                      "`~/.crucible/clients/`", body,
                      "§S1 (amended f395454): criterion 5 names the surfaces its Check scans")
        claims = [s for s in ("crucible-clients.json", "resolved through") if s in body]
        self.assertEqual(claims, [], "§S1: ClientContractS3Test reads ~/.crucible/clients/ "
                                     "directly; criterion 5 must not claim manifest resolution")

    def test_criterion_six_is_the_manifest_property_unmet_until_cr_mdb_040(self):
        body = self.criteria.get(6, "")
        self.assertRegex(body, r"(?i)unmet until CR-MDB-040 merges",
                         "§S1: criterion 6 states it is unmet until CR-MDB-040 merges")
        missing = [s for s in ("manifest", "CR-MDB-021") if s not in body]
        self.assertEqual(missing, [], "§S1: criterion 6 is the manifest property and names "
                                      "CR-MDB-021 as why `chezmoi diff` left the PRD")


class PrdInvariantsTest(unittest.TestCase):
    """CR-MDB-035 §S2 — §3 invariant 1 and the unittest wording."""

    @classmethod
    def setUpClass(cls):
        cls.s3 = md_section(read_text(PRD), "## 3.")

    def test_invariant_one_states_agents_md_is_the_only_file_and_no_claude_md(self):
        block = _site_block(self.s3, "- ")
        self.assertIn("`AGENTS.md` is the only project-context file Model B writes; it emits no "
                      "`CLAUDE.md` (CR-MDB-031)", block,
                      f"§S2: §3 invariant 1 is the AGENTS.md-only invariant; it is {block!r}")
        notes = AMENDED_ITALIC.findall(block) + [line for line in block.splitlines()
                                                 if AMENDED_LINE.search(line)]
        self.assertTrue(any("D1" in note for note in notes),
                        "§S2: invariant 1 carries a dated note recording that it replaces the "
                        f"D1 symlink invariant; notes found: {notes}")

    def test_ac_gates_are_described_as_unittest_checks_not_pytest(self):
        visible = "\n".join(_blank_amendment_notes(line) for line in self.s3.splitlines())
        self.assertIn("executable `unittest` checks", visible,
                      "§S2: 'AC gates are executable `unittest` checks'")
        self.assertNotIn("pytest", visible, "§S2: the suite has never used pytest")


class PrdDesignSectionAmendmentsTest(unittest.TestCase):
    """CR-MDB-035 §S3 and the acceptance criteria — every contradicting design site keeps its
    original and carries a dated CR-MDB-035 AMENDED line; outside §1, the header and the notes,
    no sentence requires a ``CLAUDE.md``, a chezmoi bundle, a ``~/.claude`` path or a non-Pi
    harness."""

    @classmethod
    def setUpClass(cls):
        cls.text = read_text(PRD)

    def test_every_s3_site_keeps_its_original_and_carries_a_dated_amended_line(self):
        self.assertEqual(_sites_without_amendment(self.text), [],
                         "§S3: each site keeps its original sentence and gains an "
                         "'AMENDED 2026-09-25 (CR-MDB-035, …)' line stating the current design")

    def test_no_prd_sentence_outside_problem_header_and_notes_requires_a_retired_surface(self):
        self.assertEqual(_unamended_requirements(self.text), [],
                         "AC: (PRD line, term) — a sentence outside §1, the header and dated "
                         "amendment notes that still requires a retired surface")


if __name__ == "__main__":
    unittest.main()
