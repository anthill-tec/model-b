"""The bootstrap and shutdown skills read what ``init`` scaffolds (CR-MDB-041 §S1–§S4;
PRD D5 and D3.1, both amended 2026-09-26).

Contract: ``docs/changes/CR-MDB-041-bootstrap-reads-scaffolded-files.md``. The two skills
(``skills-src/bootstrap/SKILL.md``, ``skills-src/shutdown/SKILL.md``) load the orchestrator's
rules from the ``model-b`` references, then the project's ``AGENTS.md`` and ``.env``, then
``docs/memory/INDEX.md``; take the project's identity from the registry keys the CR-MDB-043
schema declares; fall back to ``AGENTS.md`` and one question; resolve the role without a
working-directory heuristic; and reload / drain work on the Crucible board, never a todo list.

Class map — one class per acceptance criterion:

- ``ReadingOrderTest`` — the rules-loading step names ``orchestration-common.md``, the role
  file, ``sandesh.md``, then ``AGENTS.md`` and ``.env``, then ``docs/memory/INDEX.md``; no
  ``ORCHESTRATOR-`` note and no ``MEMORY.md`` anywhere.
- ``ScaffoldedFilesOnlyTest`` — every project file the skills name is one a sandboxed
  ``init --harnesses pi`` produces (NO installer run).
- ``IdentityFromRegistryTest`` — ``SANDESH_PROJECT`` / ``ORCHESTRATOR_LABEL`` /
  ``track<N>-<PROJECT_TOKEN>`` / ``PROJECT_STACKS``; every ``sandesh`` example passes
  ``--project`` built from ``SANDESH_PROJECT``; no ``python-crucible.py`` for every project;
  no literal ``vidushi`` id; every key named is declared in the schema (its loader).
- ``RegistryFallbackTest`` — no registry / missing key → ``AGENTS.md`` → ask once; a missing
  index is skipped; nothing is fatal.
- ``RoleResolutionTest`` — no ``show-toplevel`` / ``/.worktrees/`` role inference; the order
  is (argument →) carried context → Sandesh address (``Track <N> - …``) → ask.
- ``BoardNotTodoListTest`` — no todo/task list (frontmatter included); bootstrap reloads from
  the board (``plans``, ``next``); shutdown finishes the active cycle and a Track's escalation
  names the active cycle (what ``plans`` returns; never "open cycles" or a last run).
- ``NameGateCoversBootstrapShutdownTest`` — ``EXEMPT_BUNDLES`` no longer lists the two, and
  the CR-MDB-042 name/retired-tool gate passes over both.
- ``SchemaReadersTest`` — the ``readers`` of ``SANDESH_PROJECT``, ``PROJECT_STACKS``,
  ``ORCHESTRATOR_LABEL`` and ``PROJECT_TOKEN`` name the two skills, nothing "pending".
- ``ClientResolutionTest`` — the client is resolved through Crucible's manifest
  (quarkus/java → ``mvn-crucible.py``); over EVERY supported stack, no surface builds a client
  path that does not exist for it (expected names from ``STACK_CLIENT_KEYS``, hermetic).
- ``TrackWorktreeTest`` — a resumed Track re-enters its worktree before any write; shutdown's
  Track path runs ``git -C .worktrees/<cr>``, never finishes without Mainline's sign-off, and
  passes ``--cr`` to ``finish`` before ``modelb_worktree_exit``.
- ``CommonRulesAgreeTest`` — ``orchestration-track.md`` and ``rust-orchestration.md`` agree on
  the Track id and the stack client.
- ``UnregisteredProjectTest`` — an empty ``CRUCIBLE_PROJECT_KEY`` is "not registered", never idle.
- ``WatcherWordingTest`` — the addressbook read as its toon fields, never the human table; the
  watcher stopped by address (``/sandesh-watcher stop <your address>``); no ``/watcher`` and no
  ``pkill`` (MIGRATED at CR-MDB-047 C2 RED, §S3).

Phrase checks normalise the text (backticks and ``*`` dropped, whitespace collapsed,
lower-cased) and test meaning through required and forbidden phrases, never whole sentences.
A forbidden phrase inside a NEGATED sentence ("never from a todo list") is not a finding.

Hermetic: reads only repo files; the one ``init`` run is sandboxed under a temp dir (every
home dir pointed there). Stdlib only.
"""

import re
import shutil
import tempfile
import unittest
from pathlib import Path

from modelb_axi import scaffold
from modelb_axi.requirements import STACK_CLIENT_KEYS
from tests._helpers import REPO_ROOT, read_text, split_frontmatter
from tests.test_orchestrator_rule_triage import (
    EXEMPT_BUNDLES,
    model_b_owned_skill_files,
    project_name_findings,
    retired_tool_findings,
)
from tests.test_project_registry_schema import (
    NOT_REGISTRY_KEYS,
    _init,
    _registry_names_named,
)

SKILLS = {
    "bootstrap": "skills-src/bootstrap/SKILL.md",
    "shutdown": "skills-src/shutdown/SKILL.md",
}
MODEL_B_REFERENCE_FILES = frozenset(
    p.name for p in (REPO_ROOT / "skills-src" / "model-b" / "references").glob("*.md"))
#: The project files §S2 has the skills read, all three scaffolded by ``init``.
PROJECT_FILES = ("AGENTS.md", ".env", "docs/memory/INDEX.md")
#: The registry keys §S2 has the skills read by schema name.
IDENTITY_KEYS = ("SANDESH_PROJECT", "ORCHESTRATOR_LABEL", "PROJECT_TOKEN", "PROJECT_STACKS")
#: The stacks the sandboxed ``init`` is run with: rust ships an orchestration template, so a
#: ``<stack>`` placeholder in a named path resolves to a file ``init`` really writes.
INIT_STACKS = ("python", "rust")
#: Crucible's installed client manifest \u2014 the file the skills resolve a stack's client through.
MANIFEST = "~/.crucible/crucible-clients.json"
#: The other surfaces \u00a7S4 aligns with the two skills (F4).
TRACK_REF = "skills-src/model-b/references/orchestration-track.md"
RUST_TEMPLATE = "skills-src/memory-templates/rust-orchestration.md"
#: Every surface whose client naming \u00a7S2/\u00a7S4 governs.
CLIENT_SURFACES = {**SKILLS, "orchestration-track": TRACK_REF, "rust-orchestration": RUST_TEMPLATE}

_NEGATION = re.compile(r"\b(?:never|not|no|nor|without|instead of|rather than|don't|do not)\b")
_SENTENCE_SPLIT = re.compile(r"(?<=[.;!?])\s+|\n\s*\n|\n\s*(?:[-*]|\d+\.)\s+")


# ------------------------------------------------------------------ helpers ----

def _skill_text(name: str) -> str:
    return read_text(REPO_ROOT / SKILLS[name])


def normalise(text: str) -> str:
    """Backticks, ``*`` and ``_``-free emphasis dropped, curly quotes straightened, whitespace
    collapsed, lower-cased — so a phrase matches however the line is wrapped or marked up."""
    text = text.replace("`", "").replace("*", "").replace("\u2019", "'").replace("\u2018", "'")
    return re.sub(r"\s+", " ", text).strip().lower()


def sentences(text: str) -> list[str]:
    """``text`` split into sentences / list items / paragraphs, each normalised, a leading list
    marker dropped."""
    out = []
    for chunk in _SENTENCE_SPLIT.split(text):
        chunk = re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", chunk)
        if chunk.strip():
            out.append(normalise(chunk))
    return out


def affirmed_findings(text: str, pattern: str) -> list[str]:
    """Each sentence of ``text`` matching ``pattern`` (regex, on normalised text) that is NOT
    negated — "never from a todo list" states the rule; "drain the todo list" breaks it."""
    rx = re.compile(pattern)
    return [s for s in sentences(text) if rx.search(s) and not _NEGATION.search(s)]


def blocks(text: str) -> list[str]:
    """Blank-line separated blocks, each normalised."""
    return [normalise(b) for b in re.split(r"\n\s*\n", text) if b.strip()]


def _headings(text: str) -> list[tuple[int, int]]:
    out, fenced = [], False
    for i, line in enumerate(text.splitlines()):
        if re.match(r"^\s*(```|~~~)", line):
            fenced = not fenced
            continue
        m = None if fenced else re.match(r"^(#{1,6})\s", line)
        if m:
            out.append((i, len(m.group(1))))
    return out


#: What the rules-loading step names, in §S2 order (regexes on the raw text).
READING_MARKERS = (
    ("orchestration-common.md", r"orchestration-common\.md"),
    ("the role file", r"orchestration-(?:mainline|track)\.md"),
    ("sandesh.md", r"(?<![\w-])sandesh\.md"),
    ("AGENTS.md", r"(?<![\w-])AGENTS\.md"),
    (".env", r"(?<![\w.])\.env(?![\w.])"),
    ("docs/memory/INDEX.md", r"docs/memory/INDEX\.md"),
)


def reading_step(text: str) -> str:
    """The step that loads the rules: of the heading sections (each up to the next heading of
    any level) that name ``orchestration-common.md``, the one naming the most
    ``READING_MARKERS`` (the first on a tie) — an intro that only mentions the common file is
    not the step; ``""`` if no section names it."""
    lines = text.splitlines()
    heads = _headings(text)
    best, best_score = "", 0
    for n, (idx, _level) in enumerate(heads):
        end = heads[n + 1][0] if n + 1 < len(heads) else len(lines)
        body = "\n".join(lines[idx:end])
        if "orchestration-common.md" not in body:
            continue
        score = sum(1 for _, rx in READING_MARKERS if re.search(rx, body))
        if score > best_score:
            best, best_score = body, score
    return best


def first_index(haystack: str, pattern: str) -> int:
    m = re.search(pattern, haystack)
    return m.start() if m else -1


def must_match(pattern: str, text: str, pos: int = 0) -> re.Match:
    """The first match of ``pattern`` in ``text`` from ``pos``; an ``AssertionError`` naming the
    pattern when there is none (a missing phrase is a test failure, not a crash)."""
    m = re.compile(pattern).search(text, pos)
    if m is None:
        raise AssertionError(f"no match for {pattern!r}")
    return m


#: A project file named in a skill: a relative path (never under ``~``, ``/`` or ``$``)
#: ending in ``.md``, or the ``.env`` / ``.env.local`` registry files.
_PROJECT_FILE_RE = re.compile(
    r"(?<![\w/~.$<>-])((?:[\w.<>-]+/)*[\w<>-][\w.<>-]*\.md|\.env(?:\.local)?)(?![\w/.-])")


def named_project_files(text: str) -> set[str]:
    """Every project file ``text`` names (see ``_PROJECT_FILE_RE``), minus the ``model-b``
    reference files and ``SKILL.md`` — those are the installed skill's, not the project's."""
    names = set(_PROJECT_FILE_RE.findall(text))
    return {n for n in names
            if n.rsplit("/", 1)[-1] not in MODEL_B_REFERENCE_FILES and n != "SKILL.md"}


def resolve_placeholders(name: str) -> list[str]:
    """``name`` with a ``<stack>`` placeholder resolved against ``INIT_STACKS`` (each stack);
    any other placeholder is left in place (and so matches no scaffolded file)."""
    if "<stack>" not in name:
        return [name]
    return [name.replace("<stack>", s) for s in INIT_STACKS]


def unscaffolded_names(named: set[str], produced: set[str]) -> list[str]:
    """Each named project file that no scaffolded file is (by path, or by basename): a
    ``<stack>`` name counts when ``init`` produced it for at least one of its stacks."""
    basenames = {p.rsplit("/", 1)[-1] for p in produced}
    return sorted(n for n in named
                  if not any(c in produced or c in basenames for c in resolve_placeholders(n)))


def sandesh_invocations(text: str) -> list[str]:
    """Every ``sandesh <verb> …`` invocation written as code — an inline span (it may wrap a
    line) or a fenced line — that carries at least one flag. A bare mention (``sandesh
    notify`` as a word) carries none and is not an invocation."""
    spans = list(re.findall(r"`([^`]+)`", text))
    fenced, inside = [], False
    for line in text.splitlines():
        if re.match(r"^\s*(```|~~~)", line):
            inside = not inside
            continue
        if inside:
            fenced.append(line)
    calls = []
    for code in spans + fenced:
        code = re.sub(r"\s+", " ", code).strip()
        m = re.search(r"(?<![\w'\"-])sandesh [a-z][a-z-]*\b.*", code)
        if m and "--" in m.group(0):
            calls.append(m.group(0))
    return calls


def project_flag_values(call: str) -> list[str]:
    return [m.group(1) for m in re.finditer(r"--project(?:=|\s+)[\"']?([^\s\"']+)", call)]


def defined_from_sandesh_project(text: str, placeholder: str) -> bool:
    """``placeholder`` (e.g. ``<Project>``) is defined from ``SANDESH_PROJECT``: some line
    names both."""
    return any(placeholder in line and "SANDESH_PROJECT" in line for line in text.splitlines())


def project_value_findings(text: str) -> list[str]:
    """Each ``sandesh`` invocation whose ``--project`` is missing or not built from
    ``SANDESH_PROJECT`` (``<SANDESH_PROJECT>``, ``$SANDESH_PROJECT``, ``${SANDESH_PROJECT}``,
    or a placeholder the skill defines from it)."""
    out = []
    for call in sandesh_invocations(text):
        values = project_flag_values(call)
        if not values:
            out.append(f"no --project: {call}")
            continue
        for value in values:
            if not built_from_sandesh_project(text, value):
                out.append(f"--project {value} is not built from SANDESH_PROJECT: {call}")
    return out


_DIRECT_SANDESH_PROJECT = frozenset({"<SANDESH_PROJECT>", "$SANDESH_PROJECT", "${SANDESH_PROJECT}"})


def built_from_sandesh_project(text: str, value: str) -> bool:
    return value in _DIRECT_SANDESH_PROJECT or defined_from_sandesh_project(text, value)


def address_findings(text: str, role: str) -> list[str]:
    """``role`` is ``Mainline`` or ``Track``: ``["none"]`` when the text builds no such
    address; otherwise each address whose project part is not built from ``SANDESH_PROJECT``."""
    lead = r"Mainline" if role == "Mainline" else r"Track <N>"
    raw = text.replace("`", "")
    parts = re.findall(lead + r" - (<[^>\s]+>|\$\{?[A-Za-z_]+\}?)", raw)
    if not parts:
        return ["none"]
    return sorted({f"{role} - {p}" for p in parts if not built_from_sandesh_project(text, p)})


def key_names_named(rel: str, text: str) -> set[str]:
    """The registry keys ``text`` names: the CR-MDB-043 §S3 detector's hits, plus every
    env-style name written as code or as a ``<KEY>`` placeholder anywhere."""
    names = {name for _, name in _registry_names_named(rel, text)}
    env_style = r"[A-Z][A-Z0-9]*_[A-Z0-9_]*[A-Z0-9]"
    names |= set(re.findall(r"`(" + env_style + r")`", text))
    names |= set(re.findall(r"<(" + env_style + r")>", text))
    return names


# ------------------------------------------------------------------ AC tests ----

class ReadingOrderTest(unittest.TestCase):
    """AC2 (first half) / §S2 reading order."""

    def test_rules_step_reads_model_b_references_then_agents_md_and_env_then_memory_index(self):
        for name in SKILLS:
            with self.subTest(skill=name):
                step = reading_step(_skill_text(name))
                self.assertNotEqual(step, "", f"{name}: no step names orchestration-common.md")
                pos = {}
                for label, rx in READING_MARKERS:
                    pos[label] = first_index(step, rx)
                    self.assertNotEqual(pos[label], -1,
                                        f"{name}: the rules step does not name {label}")
                refs = [pos["orchestration-common.md"], pos["the role file"], pos["sandesh.md"]]
                self.assertEqual(refs, sorted(refs),
                                 f"{name}: model-b references out of order: {pos}")
                project = (pos["AGENTS.md"], pos[".env"])
                self.assertGreater(min(project), refs[-1],
                                   f"{name}: AGENTS.md/.env named before the model-b references: {pos}")
                self.assertGreater(pos["docs/memory/INDEX.md"], max(project),
                                   f"{name}: docs/memory/INDEX.md before AGENTS.md/.env: {pos}")

    def test_neither_skill_names_an_orchestrator_note_or_memory_md(self):
        for name in SKILLS:
            with self.subTest(skill=name):
                text = _skill_text(name)
                hits = [line.strip() for line in text.splitlines()
                        if "ORCHESTRATOR-" in line or re.search(r"(?i)(?<![\w/-])memory\.md", line)]
                self.assertEqual(hits, [], f"{name} names a per-project orchestrator note or "
                                           f"MEMORY.md")

    def test_reading_step_detector_on_synthetic_text(self):
        good = ("# T\n\n## Step 0.5 — Read\n\n1. `orchestration-common.md`\n2. "
                "`orchestration-track.md`\n3. `sandesh.md`\n4. the project's `AGENTS.md` and "
                "`.env`\n5. `docs/memory/INDEX.md`\n\n## Step 1\n\nsandesh.md again\n")
        step = reading_step(good)
        self.assertIn("docs/memory/INDEX.md", step)
        self.assertNotIn("## Step 1", step)
        self.assertEqual(reading_step("# T\n\n## A\n\nnothing\n"), "")


class ScaffoldedFilesOnlyTest(unittest.TestCase):
    """AC2 (second half): every project file the two skills name is one a sandboxed
    ``init --harnesses pi`` produces. Sandboxed through ``test_project_registry_schema._init``
    (``--target``, ``HOME``, ``MODELB_HOME``, ``XDG_DATA_HOME``, ``PI_CODING_AGENT_DIR`` under a
    temp dir; ``install.toml`` pre-written, so no installer runs)."""

    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="r41-init-"))
        cls.target = cls.root / "proj"
        cls.result = _init(cls.root, cls.target, "--harnesses", "pi",
                           "--stacks", ",".join(INIT_STACKS))
        cls.produced = {p.relative_to(cls.target).as_posix()
                        for p in cls.target.rglob("*")
                        if p.is_file() and ".git" not in p.relative_to(cls.target).parts}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_sandboxed_init_produces_agents_md_env_and_memory_index(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr[-800:])
        for rel in PROJECT_FILES:
            self.assertIn(rel, self.produced)
        self.assertIn("docs/memory/rust-orchestration.md", self.produced)
        home_left = sorted(p.name for p in (self.root / "home").iterdir())
        self.assertEqual(home_left, [], "init wrote into the sandbox HOME")

    def test_each_skill_names_all_three_scaffolded_project_files(self):
        for name in SKILLS:
            with self.subTest(skill=name):
                named = named_project_files(_skill_text(name))
                self.assertEqual(sorted(set(PROJECT_FILES) - named), [],
                                 f"{name} does not name every file it reads")

    def test_every_project_file_either_skill_names_is_scaffolded_by_init(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr[-800:])
        for name in SKILLS:
            with self.subTest(skill=name):
                self.assertEqual(
                    unscaffolded_names(named_project_files(_skill_text(name)), self.produced), [],
                    f"{name} names a project file init does not scaffold")

    def test_project_file_detector_on_synthetic_text(self):
        text = ("Read `~/.agents/skills/model-b/references/sandesh.md`, then `AGENTS.md`, "
                "`.env`, `docs/memory/INDEX.md` and `docs/memory/<stack>-orchestration.md`; "
                "never `MEMORY.md`. See SKILL.md and $HOME/x.md and orchestration-track.md.")
        named = named_project_files(text)
        self.assertEqual(named, {"AGENTS.md", ".env", "docs/memory/INDEX.md",
                                 "docs/memory/<stack>-orchestration.md", "MEMORY.md"})
        produced = {"AGENTS.md", ".env", "docs/memory/INDEX.md", "docs/memory/rust-orchestration.md"}
        self.assertEqual(unscaffolded_names(named, produced), ["MEMORY.md"])


class IdentityFromRegistryTest(unittest.TestCase):
    """AC1 + AC3 / §S1–§S2 identity: keys by schema name, never a project's value."""

    def test_both_skills_name_the_identity_keys(self):
        for name in SKILLS:
            with self.subTest(skill=name):
                named = key_names_named(SKILLS[name], _skill_text(name))
                self.assertEqual(sorted(set(IDENTITY_KEYS) - named), [],
                                 f"{name} does not read these registry keys by name")

    def test_every_registry_key_either_skill_names_is_declared_in_the_schema(self):
        declared = {e["name"] for e in scaffold.load_schema(scaffold.PROJECT_SCHEMA_PATH)}
        for name in SKILLS:
            with self.subTest(skill=name):
                named = key_names_named(SKILLS[name], _skill_text(name))
                self.assertIn("SANDESH_PROJECT", named, f"{name} names no SANDESH_PROJECT")
                self.assertEqual(sorted(named - declared - set(NOT_REGISTRY_KEYS)), [],
                                 f"{name} names a registry key the schema does not declare")

    def test_every_sandesh_invocation_passes_project_built_from_sandesh_project(self):
        for name in SKILLS:
            with self.subTest(skill=name):
                text = _skill_text(name)
                self.assertGreaterEqual(len(sandesh_invocations(text)), 1,
                                        f"{name}: sandesh examples not found")
                self.assertEqual(project_value_findings(text), [])

    def test_sandesh_addresses_are_built_from_sandesh_project(self):
        for name in SKILLS:
            with self.subTest(skill=name):
                text = _skill_text(name)
                self.assertEqual(address_findings(text, "Mainline"), [])
                self.assertEqual(address_findings(text, "Track"), [])

    def test_address_detector_on_synthetic_text(self):
        good = "`<Project>` is `SANDESH_PROJECT`. `Mainline - <Project>`, `Track <N> - <SANDESH_PROJECT>`."
        self.assertEqual(address_findings(good, "Mainline"), [])
        self.assertEqual(address_findings(good, "Track"), [])
        bad = "Casing: `Mainline - <Project>` and `Track <N> - <Project>`."
        self.assertEqual(address_findings(bad, "Mainline"), ["Mainline - <Project>"])
        self.assertEqual(address_findings("no address", "Track"), ["none"])

    def test_own_run_id_is_orchestrator_label_and_a_tracks_is_track_n_project_token(self):
        for name in SKILLS:
            with self.subTest(skill=name):
                text = _skill_text(name)
                self.assertIn("ORCHESTRATOR_LABEL", text)
                self.assertIn("track<n>-<project_token>", normalise(text))

    def test_crucible_client_is_the_stack_client_from_project_stacks(self):
        # Migrated at CR-MDB-041 C3 (F1/F7): the client is resolved through Crucible's manifest,
        # never built as ``~/.crucible/clients/<stack>-crucible.py`` (absent for quarkus/java),
        # and no ``python-crucible.py`` example is kept beside it.
        for name in SKILLS:
            with self.subTest(skill=name):
                text = _skill_text(name)
                self.assertTrue("PROJECT_STACKS" in text, f"{name} names no PROJECT_STACKS")
                self.assertTrue(MANIFEST in text, f"{name} does not name {MANIFEST}")
                python_lines = [line.strip() for line in text.splitlines()
                                if "python-crucible.py" in line]
                self.assertEqual(python_lines, [],
                                 f"{name} names python-crucible.py (an example for every project)")

    def test_no_literal_vidushi_orchestrator_ids(self):
        for name in SKILLS:
            with self.subTest(skill=name):
                hits = [line.strip() for line in _skill_text(name).splitlines()
                        if re.search(r"(?i)\bvidushi\b", line)]
                self.assertEqual(hits, [], f"{name} names a literal vidushi id")

    def test_project_value_detector_on_synthetic_text(self):
        good = ("`<Project>` is `SANDESH_PROJECT` from `.env`.\n"
                "`sandesh addressbook --project <Project>` and\n"
                "`sandesh inbox --project <SANDESH_PROJECT> --to x`; a bare `sandesh notify`.\n")
        self.assertEqual(project_value_findings(good), [])
        bad = ("Casing matters.\n`sandesh fetch --project <Project> --to x`\n"
               "`sandesh send --from a --to b`\n")
        self.assertEqual(project_value_findings(bad), [
            "--project <Project> is not built from SANDESH_PROJECT: sandesh fetch --project <Project> --to x",
            "no --project: sandesh send --from a --to b",
        ])
        self.assertEqual(sandesh_invocations('`pkill -f "sandesh notify --to \'a\'"`'), [])


class RegistryFallbackTest(unittest.TestCase):
    """AC4 / §S2 Fallback: stated, non-fatal."""

    MISSING_REGISTRY = r"(?:no|without an?|missing|absent)\b[^.]{0,40}(?:registry|\.env|key)"
    ASK_ONCE = r"\bask(?:ed|s)?\b[^.]{0,60}\bonce\b"
    INDEX_SKIPPED = r"docs/memory/index\.md"
    NON_FATAL = (r"nothing (?:here )?is (?:an error|fatal)|never fatal|non-fatal|not (?:an error|fatal)"
                 r"|no error")

    def test_missing_registry_falls_back_to_agents_md_then_asks_once(self):
        for name in SKILLS:
            with self.subTest(skill=name):
                hits = [b for b in blocks(_skill_text(name))
                        if re.search(self.MISSING_REGISTRY, b) and "agents.md" in b
                        and re.search(self.ASK_ONCE, b)]
                self.assertTrue(hits, f"{name} states no registry → AGENTS.md → ask-once fallback")
                block = hits[0]
                self.assertLess(block.index("agents.md"), must_match(self.ASK_ONCE, block).start(),
                                f"{name}: AGENTS.md is not consulted before asking")

    def test_missing_memory_index_is_noted_and_skipped(self):
        for name in SKILLS:
            with self.subTest(skill=name):
                hits = [s for s in blocks(_skill_text(name))
                        if re.search(self.INDEX_SKIPPED, s)
                        and re.search(r"\b(?:missing|absent|no)\b[^.]{0,60}index|index\.md[^.]{0,40}"
                                      r"\b(?:missing|absent|does not exist)", s)
                        and re.search(r"\bskip", s)]
                self.assertTrue(hits, f"{name} does not skip a missing docs/memory/INDEX.md")

    def test_the_fallback_is_stated_non_fatal(self):
        for name in SKILLS:
            with self.subTest(skill=name):
                self.assertRegex(normalise(_skill_text(name)), self.NON_FATAL)


class RoleResolutionTest(unittest.TestCase):
    """AC5 / §S3: no working-directory role inference; argument → carried context → Sandesh
    address → ask."""

    CARRIED = r"carried\b[^.]{0,20}context"
    ADDRESS = r"sandesh address|track <n> - "

    def _span(self, text: str) -> str:
        """Normalised text from the first carried-context source to the next ``ask``."""
        norm = normalise(split_frontmatter(text)[1])
        c = must_match(self.CARRIED, norm)
        ask = must_match(r"\bask\b", norm, c.end())
        return norm[c.start():ask.end()]

    def test_no_worktree_or_toplevel_role_inference(self):
        for name in SKILLS:
            with self.subTest(skill=name):
                text = _skill_text(name)
                self.assertEqual(affirmed_findings(text, r"show-toplevel|/\.worktrees/"), [])
                self.assertEqual(affirmed_findings(text, r"working-tree heuristic|"
                                                         r"working-directory heuristic"), [])
                fm, _ = split_frontmatter(text)
                self.assertNotRegex(normalise(fm), r"sandesh address ?/ ?worktree|/ worktree\)")

    def test_role_falls_back_carried_context_then_sandesh_address_then_ask(self):
        for name in SKILLS:
            with self.subTest(skill=name):
                span = self._span(_skill_text(name))
                self.assertRegex(span, self.ADDRESS,
                                 f"{name}: the Sandesh address is not a role source before asking")
                self.assertNotRegex(span, r"worktree|toplevel|working[- ]?(?:tree|directory)")

    def test_bootstrap_reads_the_argument_before_the_carried_context(self):
        norm = normalise(split_frontmatter(_skill_text("bootstrap"))[1])
        c = must_match(self.CARRIED, norm)
        self.assertRegex(norm[:c.start()], r"argument")

    def test_bootstrap_reads_track_n_from_a_track_address(self):
        norm = normalise(split_frontmatter(_skill_text("bootstrap"))[1])
        self.assertRegex(norm, r"track <n> - [^.]{0,60}(?:⟹|=>|→|->|means|is)\s*track n\b")


class BoardNotTodoListTest(unittest.TestCase):
    """AC6 / §S3: the Crucible board is the task list."""

    TODO = r"\btodos?\b|to-do|task[ -]list|task panel|tasks left"

    def test_neither_skill_recovers_repaints_drains_or_escalates_a_todo_list(self):
        for name in SKILLS:
            with self.subTest(skill=name):
                self.assertEqual(affirmed_findings(_skill_text(name), self.TODO), [])

    def test_frontmatter_descriptions_name_no_todo_or_task_list(self):
        for name in SKILLS:
            with self.subTest(skill=name):
                fm, _ = split_frontmatter(_skill_text(name))
                self.assertNotEqual(fm, "")
                self.assertEqual(affirmed_findings(fm, self.TODO), [])

    def test_bootstrap_reloads_the_in_flight_cycle_from_the_board_plans_then_next(self):
        text = _skill_text("bootstrap")
        hits = [b for b in blocks(text)
                if re.search(r"\bplans\b", b) and re.search(r"\bnext\b", b)
                and "in-flight" in b.replace("in flight", "in-flight") and "board" in b]
        self.assertTrue(hits, "bootstrap does not reload the in-flight cycle from the board "
                              "(plans, next)")
        self.assertLess(must_match(r"\bplans\b", hits[0]).start(),
                        must_match(r"\bnext\b", hits[0]).start(), "plans before next")

    def test_shutdown_finishes_the_active_cycle(self):
        # Migrated at CR-MDB-041 C3 (F5): ``plans`` returns each plan's ACTIVE cycle, not a list
        # of open cycles \u2014 shutdown finishes the active cycle.
        norm = normalise(_skill_text("shutdown"))
        self.assertRegex(norm, r"finish\w*[^.]{0,60}active cycle")

    def test_shutdowns_track_escalation_names_the_active_cycle(self):
        hits = [b for b in blocks(_skill_text("shutdown"))
                if "escalat" in b and "mainline" in b and "active cycle" in b]
        self.assertTrue(hits, "shutdown's Track escalation does not name the active cycle")

    def test_neither_skill_claims_what_plans_does_not_return(self):
        # F5: ``plans`` gives activeCycleId/activeCycleLabel per plan and ``next`` what is
        # ready \u2014 no open-cycle list, no phase, no last ingested run.
        for name in SKILLS:
            with self.subTest(skill=name):
                norm = normalise(_skill_text(name))
                for rx in (r"open cycles?", r"last ingested run", r"<n> open"):
                    self.assertNotRegex(norm, rx)

    def test_bootstrap_reads_the_active_cycle_id_and_label_from_plans(self):
        hits = [b for b in blocks(_skill_text("bootstrap"))
                if re.search(r"\bplans\b", b) and "active cycle" in b
                and re.search(r"\bid\b[^.]{0,20}\blabel\b", b)]
        self.assertTrue(hits, "bootstrap does not read the active cycle (id and label) from plans")

    def test_negated_mentions_are_not_findings(self):
        text = ("Reload from the board, never from a todo list. Drain the todo list.\n\n"
                "- repaint the task list\n")
        self.assertEqual(affirmed_findings(text, self.TODO),
                         ["drain the todo list.", "repaint the task list"])


class NameGateCoversBootstrapShutdownTest(unittest.TestCase):
    """AC7 / §S4: the CR-MDB-042 name/retired-tool gate covers the two skills and passes."""

    def test_exempt_bundles_no_longer_list_bootstrap_or_shutdown(self):
        self.assertEqual(sorted({"bootstrap", "shutdown"} & set(EXEMPT_BUNDLES)), [])
        owned = {p.relative_to(REPO_ROOT).as_posix() for p in model_b_owned_skill_files(REPO_ROOT)}
        for rel in SKILLS.values():
            self.assertIn(rel, owned)

    def test_the_name_gate_passes_over_bootstrap_and_shutdown(self):
        problems = []
        for rel in SKILLS.values():
            problems += project_name_findings(rel, read_text(REPO_ROOT / rel))
        self.assertEqual(problems, [])

    def test_the_retired_tool_gate_passes_over_bootstrap_and_shutdown(self):
        problems = []
        for rel in SKILLS.values():
            problems += retired_tool_findings(rel, read_text(REPO_ROOT / rel))
        self.assertEqual(problems, [])


class SchemaReadersTest(unittest.TestCase):
    """AC7 (second half) / §S4: ``SANDESH_PROJECT``'s readers name the two skills, not pending."""

    def _readers(self) -> list[str]:
        entries = {e["name"]: e for e in scaffold.load_schema(scaffold.PROJECT_SCHEMA_PATH)}
        return list(entries["SANDESH_PROJECT"]["readers"])

    def test_sandesh_project_readers_name_bootstrap_and_shutdown_skills(self):
        readers = self._readers()
        self.assertTrue(any("bootstrap" in r and "shutdown" in r for r in readers), readers)
        self.assertTrue(any(r.startswith("modelb-axi init") for r in readers), readers)

    def test_no_sandesh_project_reader_is_marked_pending(self):
        readers = self._readers()
        self.assertEqual([r for r in readers if re.search(r"(?i)pending|CR-MDB-041", r)], [])

    def test_identity_key_readers_name_bootstrap_and_shutdown_skills(self):
        # F8 / \u00a7S4: the skills read PROJECT_STACKS, ORCHESTRATOR_LABEL and PROJECT_TOKEN too.
        entries = {e["name"]: e for e in scaffold.load_schema(scaffold.PROJECT_SCHEMA_PATH)}
        for key in ("PROJECT_STACKS", "ORCHESTRATOR_LABEL", "PROJECT_TOKEN"):
            with self.subTest(key=key):
                readers = list(entries[key]["readers"])
                self.assertTrue(any("bootstrap" in r and "shutdown" in r for r in readers), readers)


# ------------------------------------------------------------ C3 FIX (F1\u2013F10) ----

def _surface_text(key: str) -> str:
    return read_text(REPO_ROOT / CLIENT_SURFACES[key])

#: A Crucible client file named in text: ``<name>-crucible.py`` where ``<name>`` is a stack
#: token, a manifest key, or a ``<placeholder>`` (``<stack>``); bounded on the left by anything
#: but a word character, ``<``, ``>`` or ``-``.
_CLIENT_NAME_RE = re.compile(r"(?<![\w<>-])((?:<[\w-]+>|[\w])(?:<[\w-]+>|[\w-])*?)-crucible\.py\b")

def expected_client(stack: str) -> str:
    """The client file Crucible's manifest names for ``stack`` \u2014 from
    ``requirements.STACK_CLIENT_KEYS`` (the repo's record of the manifest keys), never from
    ``~/.crucible``, so the check stays hermetic."""
    return f"{STACK_CLIENT_KEYS[stack]}-crucible.py"

def missing_client_paths(text: str, stacks=scaffold.KNOWN_STACKS) -> list[str]:
    """Each client file ``text`` names that does not exist for some supported stack: a
    ``<stack>`` form checked against every stack's manifest client; any other placeholder is
    unresolvable; a concrete name must be some stack's manifest client."""
    released = {expected_client(s) for s in stacks}
    out = []
    for name in sorted(set(_CLIENT_NAME_RE.findall(text))):
        fname = f"{name}-crucible.py"
        if "<stack>" in name:
            for s in stacks:
                built = fname.replace("<stack>", s)
                if built != expected_client(s):
                    out.append(f"{fname} for {s}: builds {built}; the manifest maps {s} to "
                               f"{expected_client(s)}")
        elif "<" in name:
            out.append(f"{fname}: an unresolvable placeholder")
        elif fname not in released:
            out.append(f"{fname}: no supported stack's client")
    return sorted(out)

def _h2_section(text: str, heading: str) -> str:
    """The text under the ``## `` heading containing ``heading``, up to the next ``## ``;
    ``""`` when there is none."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("## ") and heading in line),
                 None)
    if start is None:
        return ""
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


class ClientResolutionTest(unittest.TestCase):
    """F1 / \u00a7S2 AC: the client is resolved through the manifest (quarkus/java \u2192
    ``mvn-crucible.py``); no surface builds a client path missing for a supported stack."""

    def test_every_supported_stack_has_a_manifest_client_key(self):
        self.assertEqual(sorted(set(scaffold.KNOWN_STACKS) - set(STACK_CLIENT_KEYS)), [])

    def test_no_surface_builds_a_client_path_missing_for_a_supported_stack(self):
        for key in CLIENT_SURFACES:
            with self.subTest(surface=key):
                self.assertEqual(missing_client_paths(_surface_text(key)), [])

    def test_both_skills_resolve_the_client_through_the_manifest(self):
        for name in SKILLS:
            with self.subTest(skill=name):
                hits = [b for b in blocks(_skill_text(name))
                        if MANIFEST in b and "project_stacks" in b and "quarkus" in b
                        and "java" in b and "mvn-crucible.py" in b]
                self.assertTrue(hits, f"{name} does not resolve the client through {MANIFEST} "
                                      f"(quarkus/java \u2192 mvn-crucible.py) for a PROJECT_STACKS stack")

    def test_missing_client_path_detector_on_synthetic_text(self):
        self.assertEqual(missing_client_paths("`~/.crucible/clients/<stack>-crucible.py`"), [
            "<stack>-crucible.py for java: builds java-crucible.py; the manifest maps java to "
            "mvn-crucible.py",
            "<stack>-crucible.py for quarkus: builds quarkus-crucible.py; the manifest maps "
            "quarkus to mvn-crucible.py",
        ])
        self.assertEqual(missing_client_paths("`rust-crucible.py next`, `mvn-crucible.py`, "
                                              "`~/.crucible/clients/python-crucible.py`"), [])
        self.assertEqual(missing_client_paths("`quarkus-crucible.py` or `<x>-crucible.py`"), [
            "<x>-crucible.py: an unresolvable placeholder",
            "quarkus-crucible.py: no supported stack's client",
        ])


class TrackWorktreeTest(unittest.TestCase):
    """F2/F3 / \u00a7S3: a resumed Track re-enters its worktree; shutdown's Track path works from the
    main tree, never finishes without Mainline's sign-off, ``finish --cr`` then exit."""

    def _step_2a(self) -> str:
        section = _h2_section(_skill_text("shutdown"), "Step 2A")
        self.assertNotEqual(section, "", "shutdown lost its Step 2A section")
        return section

    def test_a_resumed_track_reenters_its_worktree_before_any_write(self):
        hits = [b for b in blocks(_skill_text("bootstrap"))
                if "modelb_worktree_enter" in b and ".worktrees/<cr>" in b
                and re.search(r"\bresum", b) and "before any write" in b]
        self.assertTrue(hits, "bootstrap does not re-enter a resumed Track's worktree "
                              "(modelb_worktree_enter with .worktrees/<cr>) before any write")

    def test_shutdowns_develop_merge_runs_in_the_worktree_with_git_c(self):
        norm = normalise(_skill_text("shutdown"))
        merges = len(re.findall(r"merge develop", norm))
        in_worktree = len(re.findall(r"git -c \.worktrees/<cr> merge develop --no-edit", norm))
        self.assertGreaterEqual(in_worktree, 1)
        self.assertEqual(merges, in_worktree, "a develop merge that is not git -C .worktrees/<cr>")

    def test_the_tracks_status_check_runs_in_the_worktree_with_git_c(self):
        norm = normalise(self._step_2a())
        checks = len(re.findall(r"status --porcelain", norm))
        in_worktree = len(re.findall(r"git -c \.worktrees/<cr> status --porcelain", norm))
        self.assertGreaterEqual(in_worktree, 1)
        self.assertEqual(checks, in_worktree, "a Track status check that is not git -C")

    def test_the_track_never_finishes_without_mainlines_sign_off(self):
        section = blocks(self._step_2a())
        self.assertTrue([b for b in section if "sign-off" in b and "mainline" in b
                         and re.search(r"\bnever\b[^.]{0,60}\bfinish", b)],
                        "Step 2A does not forbid finishing without Mainline's sign-off")
        self.assertTrue([b for b in section if re.search(r"leaves? the cr open", b)],
                        "a graceful mid-CR shutdown does not leave the CR open")

    def test_an_approved_finish_passes_cr_then_exits_the_worktree(self):
        norm = normalise(_skill_text("shutdown"))
        finishes = len(re.findall(r"worktree-flow\.py finish", norm))
        with_cr = len(re.findall(r"worktree-flow\.py finish --cr <cr>", norm))
        self.assertGreaterEqual(with_cr, 1)
        self.assertEqual(finishes, with_cr, "a finish without --cr")
        step = normalise(self._step_2a())
        self.assertLess(must_match(r"worktree-flow\.py finish --cr <cr>", step).start(),
                        must_match(r"modelb_worktree_exit", step).start(),
                        "modelb_worktree_exit follows finish")

    def test_shutdowns_description_names_the_sign_off(self):
        fm, _ = split_frontmatter(_skill_text("shutdown"))
        self.assertIn("sign-off", normalise(fm))


class CommonRulesAgreeTest(unittest.TestCase):
    """F4 / \u00a7S4: ``orchestration-track.md`` and ``rust-orchestration.md`` agree with the two
    skills on the Track id and the stack client."""

    def test_track_ref_gives_the_track_id_as_track_n_project_token(self):
        text = _surface_text("orchestration-track")
        self.assertIn("track<n>-<project_token>", normalise(text))
        self.assertNotRegex(text, r"-t(?:N|<N>)\b", "the retired <orchestrator>-tN id")

    def test_track_ref_names_the_projects_stack_client_not_python_crucible(self):
        text = _surface_text("orchestration-track")
        self.assertFalse("python-crucible.py" in text, "names python-crucible.py")
        self.assertTrue(MANIFEST in text, f"orchestration-track.md does not name {MANIFEST}")
        self.assertRegex(normalise(text), r"stack client")

    def test_track_refs_shutdown_rules_agree_with_the_shutdown_skill(self):
        norm = normalise(_h2_section(_surface_text("orchestration-track"), "shutdown directive"))
        self.assertNotEqual(norm, "")
        self.assertNotRegex(norm, r"open cycles?")
        self.assertIn("sign-off", norm)

    def test_rust_template_names_the_rust_client_for_next(self):
        text = _surface_text("rust-orchestration")
        self.assertFalse("python-crucible.py" in text, "names python-crucible.py")
        self.assertTrue("rust-crucible.py next" in text, "rust-orchestration.md: no rust-crucible.py next")


class UnregisteredProjectTest(unittest.TestCase):
    """F6 / \u00a7S2: an empty ``CRUCIBLE_PROJECT_KEY`` means not registered \u2014 do the queue README's
    setup task; an empty board is never read as idle."""

    def test_an_empty_project_key_is_not_registered_never_idle(self):
        for name in SKILLS:
            with self.subTest(skill=name):
                hits = [b for b in blocks(_skill_text(name))
                        if "crucible_project_key" in b and re.search(r"\bempty\b", b)
                        and re.search(r"not (?:yet )?registered", b) and "setup task" in b
                        and re.search(r"\bnever\b[^.]{0,60}\bidle\b", b)]
                self.assertTrue(hits, f"{name}: an empty CRUCIBLE_PROJECT_KEY is not stated as "
                                      f"'not registered \u2192 setup task, never idle'")


class MemoryIndexWordingTest(unittest.TestCase):
    """F9 / \u00a7S4: the orchestration template is read "for a stack that has one"."""

    def test_orchestration_template_is_for_a_stack_that_has_one(self):
        for name in SKILLS:
            with self.subTest(skill=name):
                norm = normalise(_skill_text(name))
                self.assertRegex(norm, r"orchestration template[^.]{0,80}for a stack that has one")
                self.assertNotRegex(norm, r"orchestration template[^.]{0,80}among them")


class WatcherWordingTest(unittest.TestCase):
    """F10 / \u00a7S4, MIGRATED at CR-MDB-047 C2 RED (\u00a7S3: Sandesh's wake watcher replaces the
    Model B watcher; liveness is read from the toon addressbook; shutdown stops by address, then
    unregisters; no ``pkill``). Was: the addressbook table columns, the Model B ``/watcher``
    command, ``/watcher stop <your address>``, and the targeted-kill pattern.

    - ``test_addressbook_is_described_as_its_table_columns`` \u2192
      ``test_addressbook_is_read_as_its_toon_fields_never_the_table``;
    - ``test_both_skills_name_the_watcher_command`` \u2192
      ``test_neither_skill_names_the_model_b_watcher_command``;
    - ``test_the_watcher_is_stopped_by_address_never_bare`` keeps its name, now over
      ``/sandesh-watcher stop``;
    - ``test_the_targeted_kill_pattern_can_match_the_notifier`` \u2192 RETIRED, replaced by
      ``test_neither_skill_kills_with_pkill``.
    """

    TOON_FIELDS = "--format toon --fields address,status,listening"

    def test_addressbook_is_read_as_its_toon_fields_never_the_table(self):
        for name in SKILLS:
            with self.subTest(skill=name):
                raw = re.sub(r"\s+", " ", _skill_text(name).replace("`", ""))
                self.assertIn(f"sandesh addressbook --project <Project> {self.TOON_FIELDS}", raw,
                              f"{name} reads no liveness from the toon addressbook")
                self.assertNotIn("\u25cf live", raw, f"{name} reads liveness from the human table")

    def test_neither_skill_names_the_model_b_watcher_command(self):
        for name in SKILLS:
            with self.subTest(skill=name):
                hits = [line.strip() for line in _skill_text(name).splitlines() if re.search(r"/watcher\b", line)]
                self.assertEqual(hits, [], f"{name} names Model B's retired /watcher command")

    def test_the_watcher_is_stopped_by_address_never_bare(self):
        self.assertTrue("/sandesh-watcher stop <your address>" in _skill_text("shutdown"),
                        "shutdown does not stop the watcher by address")
        for name in SKILLS:
            with self.subTest(skill=name):
                bare = [line.strip() for line in _skill_text(name).splitlines()
                        if re.search(r"/sandesh-watcher stop(?! <)", line)
                        and not _NEGATION.search(line.lower())]
                self.assertEqual(bare, [], f"{name}: a bare /sandesh-watcher stop names no address")

    def test_neither_skill_kills_with_pkill(self):
        for name in SKILLS:
            with self.subTest(skill=name):
                hits = [line.strip() for line in _skill_text(name).splitlines() if "pkill" in line]
                self.assertEqual(hits, [], f"{name}: the watcher is stopped by address, never killed")


if __name__ == "__main__":
    unittest.main()
