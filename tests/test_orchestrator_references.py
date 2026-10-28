"""The orchestrator's stack notes move into the stack skills; ``init`` writes no ``docs/memory/``
(CR-MDB-060 §S1–§S3).

Contract: ``docs/changes/CR-MDB-060-memory-notes-in-the-knowledge-store.md``. The mechanism these
tests drive is CR-MDB-085's stack skill (``tests.test_stack_skills``); the declaration and each
skill's exact source set are checked as data in ``tests.test_stack_reference_material``
(:data:`EXPECTED_DECLARATION`, :data:`STACK_SKILL_SOURCES`, ``arduino-stack`` among them). This
module holds what that data does not:

- ``OrchestrationReferenceDetectorTest`` — the pure functions below, proved both ways on synthetic
  text before any of them is run over the tree.
- ``OrchestrationReferencesMovedTest`` — §S1.1/AC1: each stack template exists only at its stack
  skill's ``references/orchestration.md``; its first line names it ``the <stack>-stack skill's
  orchestrator reference`` and never a memory template; its headings move as they are.
- ``StackSkillsRouteTheOrchestratorTest`` — §S1.2–3/AC2: ``java-stack``'s and ``rust-stack``'s
  ``SKILL.md`` each route the orchestrator to ``references/orchestration.md``; ``arduino-stack``'s
  routes to it; no arduino definition's skills line names ``arduino-stack`` (a regression pin —
  its only reader is the orchestrator).
- ``ArduinoStackInitTest`` — §S1.2/AC2: ``init --stacks arduino`` (sandboxed, Pi harness, the
  repository's own assets) renders ``.agents/skills/arduino-stack/`` and its ``AGENTS.md`` stack
  line names it.
- ``OrchestrationReferenceRewordingsTest`` — §S1.4–5/AC3: the raw-runner guard finds nothing in
  the references; they name no ``ctx_`` tool and no lean-ctx; ``generator/skills/`` holds none of
  §S1.5's anchors; the Java reference names no ``rust-orchestration.md`` and points at the
  ``worktree-flow`` tool's own help; ``rust.toml`` names no ``project's orchestration notes`` and
  sends per-crate feature flags to the dispatch prompt or the project's ``AGENTS.md``.
- ``OperationalCommandsDroppedTest`` — §S2/AC3: ``operational-commands.md`` does not exist; the
  Quarkus, schema-registry and RediSearch commands are in ``references/quarkus-patterns.md`` by
  §S2's anchors (the RediSearch commands beside its RediSearch section), the generic sections are
  not; ``java-stack``'s routing row for the reference names the moved commands.
- ``InitWritesNoDocsMemoryTest`` — §S3.1–2/AC4: ``init`` for each stack writes no ``docs/memory/``
  and names none in its ``planned`` or ``emitted`` list; ``skills-src/memory-templates/`` does not
  exist; ``modelb_axi/`` defines none of §S3.1's symbols and names no ``memory-templates`` or
  ``docs/memory``.
- ``OlderProjectKeepsDocsMemoryTest`` — §S3.3/AC7: a project scaffolded with a ``docs/memory/``
  keeps it, byte for byte, after ``modelb-axi agents``, which renders its stack skills, the
  orchestration reference included.

Isolation: every ``init``/``agents`` run is in process under ``tests.test_stack_skills``' sandbox
(``HOME``, ``PI_CODING_AGENT_DIR``, ``MODELB_HOME`` and ``XDG_DATA_HOME`` pinned to a throw-away
directory), its ``install.toml`` pointed at the repository's own assets. Stdlib only.
"""

import ast
import re
import shutil
import unittest
from pathlib import Path

from modelb_axi import agents, scaffold, stack_skills
from tests import test_raw_runner_guard as runner_gate
from tests import test_stack_skills as skills_gate
from tests._helpers import (
    ORCHESTRATION_REFERENCES,
    ORCHESTRATION_TEMPLATE_MOVES,
    REPO_ROOT,
    md_section,
    read_text,
    split_frontmatter,
)
from tests._helpers import rendered_definition as _rendered_definition

GENERATOR_DIR = REPO_ROOT / "generator"
SKILLS_DIR = GENERATOR_DIR / "skills"
STACKS_DIR = GENERATOR_DIR / "stacks"
TEMPLATES_DIR = GENERATOR_DIR / "templates"
AGENTS_DIR = GENERATOR_DIR / "agents"
PI_AGENTS_DIR = REPO_ROOT / ".pi" / "agents"
RUST_TOML = STACKS_DIR / "rust.toml"
MEMORY_TEMPLATES_DIR = REPO_ROOT / "skills-src" / "memory-templates"
PACKAGE_DIR = REPO_ROOT / "modelb_axi"

#: §S1.1 — the reference, relative to its skill's directory.
ORCHESTRATION_REL = "references/orchestration.md"
#: §S1.2 — the skill the arduino notes become.
ARDUINO_STACK = "arduino-stack"
#: §S1.3 — the skills that gain a routing row for the orchestrator.
ROUTED_FOR_THE_ORCHESTRATOR = ("java-stack", "rust-stack")
ROLES = ("red", "green", "verify", "fix")

#: §S1.1 — the headings each template carries today, which move as they are (the title included).
TEMPLATE_HEADINGS = {
    "arduino": (
        "# Arduino Orchestration — firmware tiers + Crucible (orchestrator-side)",
        "## Test tiers and agents",
    ),
    "java": (
        "# Java/Quarkus Orchestration — Maven + Crucible + worktree-flow (orchestrator-side)",
        "## Tooling (the workflow is embodied here — don't hand-roll)",
        "## Pre-merge gate (the regression gate)",
        "## JaCoCo — read the RIGHT report",
        "## Layered enterprise architecture (Quarkus-specific — folded into the universal agents)",
        "### Planning the layers (orchestrator — architecture + cycle planning)",
        "## Disk / cache hygiene",
    ),
    "rust": (
        "# Rust Orchestration — Cargo + Crucible + worktree-flow (orchestrator-side)",
        "## Tooling (the workflow is embodied here — don't hand-roll)",
        "## Test scope",
        "## Pre-merge gate — two tiers (docker-free default + opt-in docker-e2e)",
        "## Disk hygiene (orchestrator-only)",
        "## CARGO_BUILD_JOBS cap (dev workstation — mandatory before any heavy build)",
        "## Gate sizing",
    ),
}

#: §S1.5 — one project's detail the Rust notes may no longer name, by the spec's anchors.
S1_5_ANCHORS = (
    "NaiApp",
    "DevApp",
    "kafka connector e2e",
    "Bridge",
    "kafka-e2e-serial",
    "librocksdb",
    "observed 2026-07-03",
    "24-core",
    "31 GiB",
    ".nai-schedule.db",
    "post-test-crucible-reminder",
    "project's orchestration notes",
)
#: §S1.4 — the name of the Rust notes the Java notes may no longer point at.
RUST_NOTES_NAME = "rust-orchestration.md"
#: §S1.4 — a sentence pointing at the ``worktree-flow`` tool's own help.
WORKTREE_FLOW_HELP = re.compile(
    r"worktree-flow(?:\.py)?\b[^\n]{0,120}?(?:--help|(?<![\w-])-h\b|\bhelp\b)"
    r"|\bhelp\b[^\n]{0,120}?worktree-flow",
    re.IGNORECASE,
)
#: §S1.4/AC3 — a ``ctx_`` tool, or lean-ctx itself.
CTX_OR_LEAN_CTX = re.compile(r"(?<![\w])ctx_[a-z_]+|lean[-_]ctx", re.IGNORECASE)
#: §S1.5 — the phrase ``rust.toml``'s workspace-layout bullet leaves.
ORCHESTRATION_NOTES = "project's orchestration notes"
FEATURE_FLAGS_LINE = re.compile(r"(?i)per-crate feature flags")

#: §S2 — the moved commands' anchors, checked in ``references/quarkus-patterns.md``.
QUARKUS_PATTERNS = SKILLS_DIR / "java-stack" / "references" / "quarkus-patterns.md"
QUARKUS_PATTERNS_REL = "references/quarkus-patterns.md"
MOVED_COMMAND_ANCHORS = ("/q/health", "/q/openapi", "quarkus.container-image.build", "ccompat", "FT._LIST")
#: §S2 — the RediSearch commands' anchor, and the section of the reference they sit beside.
REDISEARCH_ANCHOR = "FT._LIST"
REDISEARCH_SECTION = "RediSearch"
#: §S2 — the moved commands java-stack's routing row names: (what, how it is found).
MOVED_COMMAND_TOPICS = (
    ("health", re.compile(r"(?i)\bhealth\b")),
    ("metrics", re.compile(r"(?i)\bmetrics\b")),
    ("OpenAPI", re.compile(r"(?i)\bopenapi\b")),
    ("container-image builds", re.compile(r"(?i)container[- ]image")),
    ("the schema registry", re.compile(r"(?i)schema[- ]registry")),
    ("RediSearch", re.compile(r"(?i)redisearch")),
)
#: §S2 — the operational-commands sections that go, by their headings.
DROPPED_SECTIONS = (
    "Docker Commands (Generic)",
    "MongoDB CLI Commands (Generic)",
    "Redis CLI Commands (Generic)",
    "SSE Testing Commands (Generic)",
    "HTTPie Commands (Generic)",
    "Performance Testing (Generic)",
    "Port Troubleshooting (Generic)",
    "Summary: Command Categories",
)
OPERATIONAL_COMMANDS_NAME = "operational-commands.md"

#: §S3.1 — what ``modelb_axi/scaffold.py`` loses, by name.
RETIRED_SYMBOLS = (
    "_memory_templates_dir",
    "MEMORY_TEMPLATE_FAMILIES",
    "_select_memory_templates",
    "_render_memory_index",
)
#: §S3.1–2/AC4 — what no file under ``modelb_axi/`` names.
RETIRED_NAMES = ("memory-templates", "docs/memory")
DOCS_MEMORY = "docs/memory"

_FENCE = re.compile(r"^\s*(```|~~~)")
_HEADING = re.compile(r"^#{1,6}\s")


# ------------------------------------------------------------------ pure functions ----


def headings(text: str) -> list[str]:
    """Every Markdown heading line of ``text``, stripped, in order; a fenced line never is one."""
    found, fenced = [], False
    for line in text.splitlines():
        if _FENCE.match(line):
            fenced = not fenced
            continue
        if not fenced and _HEADING.match(line):
            found.append(line.strip())
    return found


def h2_sections(text: str) -> list[tuple[str, str]]:
    """``(heading title, body)`` for each ``## `` section of ``text`` (fences respected); the
    text before the first one is not a section."""
    sections, title, body, fenced = [], None, [], False
    for line in text.splitlines():
        if _FENCE.match(line):
            fenced = not fenced
        if not fenced and line.startswith("## "):
            if title is not None:
                sections.append((title, "\n".join(body)))
            title, body = line[3:].strip(), []
            continue
        body.append(line)
    if title is not None:
        sections.append((title, "\n".join(body)))
    return sections


def provenance_findings(stack: str, text: str) -> list[str]:
    """§S1.1/AC1: what the first line of ``text`` lacks to name it ``the <stack>-stack skill's
    orchestrator reference`` (backticks and a typographic apostrophe read as plain text), or what it
    names instead — a memory template, a ``docs/memory/`` path."""
    first = text.splitlines()[0] if text else ""
    plain = first.replace("`", "").replace("\u2019", "'")
    found = []
    if not re.search(rf"(?i)\bthe {re.escape(stack)}-stack skill's orchestrator reference\b", plain):
        found.append(f"the first line does not name it the {stack}-stack skill's orchestrator "
                     f"reference: {first!r}")
    if re.search(r"(?i)memory[\s-]+template", plain):
        found.append(f"the first line calls it a memory template: {first!r}")
    if "docs/memory" in plain:
        found.append(f"the first line names docs/memory: {first!r}")
    return found


def anchor_findings(text: str, anchors=S1_5_ANCHORS) -> list[str]:
    """§S1.5: each of ``anchors`` that ``text`` holds, as written."""
    return [anchor for anchor in anchors if anchor in text]


def ctx_findings(text: str) -> list[str]:
    """§S1.4: each ``ctx_`` tool and each lean-ctx ``text`` names."""
    return sorted(set(m.group(0) for m in CTX_OR_LEAN_CTX.finditer(text)))


def routing_lines(skill_md: str, rel: str) -> list[str]:
    """The lines of a ``SKILL.md`` body that name ``rel`` by its path."""
    return [line for line in skill_md.splitlines() if rel in line]


def skills_lines_naming(texts: dict, skill: str) -> list[str]:
    """``where`` for each ``{where: definition text}`` whose skills line names ``skill``."""
    named = []
    for where, text in texts.items():
        line = next((ln for ln in text.splitlines() if agents.SKILLS_LINE_PREFIX in ln), "")
        if re.search(rf"(?<![\w-]){re.escape(skill)}(?![\w-])", line):
            named.append(where)
    return sorted(named)


def defined_names(source: str) -> set[str]:
    """Every name ``source`` defines, at any depth: functions, classes, assigned names."""
    names = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def beside_section_findings(text: str, anchor: str, section: str) -> list[str]:
    """§S2: ``anchor`` sits in the ``## `` section whose title starts with ``section``, or in the
    section right before or after it whose title names ``section``."""
    sections = h2_sections(text)
    home = [i for i, (title, _body) in enumerate(sections) if title.startswith(section)]
    if not home:
        return [f"no section titled {section!r}"]
    i = home[0]
    near = [i] + [j for j in (i - 1, i + 1)
                  if 0 <= j < len(sections) and section.lower() in sections[j][0].lower()]
    if any(anchor in sections[j][1] for j in near):
        return []
    return [f"{anchor!r} is not in or beside the {sections[i][0]!r} section"]


def _reference(stack: str) -> Path:
    return REPO_ROOT / ORCHESTRATION_REFERENCES[stack]


def _require_references(test: unittest.TestCase) -> dict:
    """``{stack: text}`` of the three references, failing the test when one is missing."""
    missing = [rel for rel in ORCHESTRATION_REFERENCES.values() if not (REPO_ROOT / rel).is_file()]
    test.assertEqual(missing, [], "§S1.1: each stack's orchestration reference exists")
    return {stack: read_text(_reference(stack)) for stack in ORCHESTRATION_REFERENCES}


# ------------------------------------------------------------------ the detectors ----


class OrchestrationReferenceDetectorTest(unittest.TestCase):
    """Each pure function above, proved both ways on synthetic text."""

    def test_provenance_names_the_stack_skills_orchestrator_reference_or_is_found(self):
        good = "<!-- The `rust-stack` skill's orchestrator reference (moved by CR-MDB-060). -->\n# T\n"
        self.assertEqual(provenance_findings("rust", good), [])
        self.assertEqual(
            provenance_findings("rust", "<!-- The rust-stack skill\u2019s orchestrator reference -->\n"),
            [],
        )
        self.assertEqual(len(provenance_findings("java", good)), 1, "another stack's name")
        self.assertEqual(len(provenance_findings("rust", "# T\n" + good)), 1, "not the first line")
        self.assertEqual(
            provenance_findings("rust", "<!-- The rust-stack skill's orchestrator reference, a "
                                        "memory template seeded into docs/memory/. -->\n"),
            [
                "the first line calls it a memory template: \"<!-- The rust-stack skill's "
                "orchestrator reference, a memory template seeded into docs/memory/. -->\"",
                "the first line names docs/memory: \"<!-- The rust-stack skill's orchestrator "
                "reference, a memory template seeded into docs/memory/. -->\"",
            ],
        )
        self.assertEqual(len(provenance_findings("rust", "")), 1)

    def test_headings_skip_fenced_comment_lines(self):
        text = "# T\n\nIntro.\n\n## A\n\n```bash\n# a comment\n```\n\n### B\ntext\n"
        self.assertEqual(headings(text), ["# T", "## A", "### B"])

    def test_each_s1_5_anchor_is_found_and_a_neutral_statement_is_not(self):
        project = (
            "Full-boot e2e (NaiApp/DevApp) are docker-free; the kafka connector e2e and Bridge "
            "tests form the kafka-e2e-serial group (observed 2026-07-03: librocksdb sources "
            "vanished). On the 24-core / 31 GiB box; legacy .nai-schedule.db; "
            "post-test-crucible-reminder.sh; see the project's orchestration notes.\n"
        )
        self.assertEqual(anchor_findings(project), list(S1_5_ANCHORS))
        neutral = (
            "In-process full-boot e2e tests are docker-free; the docker-infra tests share one "
            "serial group. A concurrent registry prune can delete a vendored crate's sources "
            "mid-build. On a many-core workstation cap the build jobs; the project's AGENTS.md "
            "names its feature flags; the post-regression-disk-reminder hook nudges.\n"
        )
        self.assertEqual(anchor_findings(neutral), [])

    def test_ctx_tools_and_lean_ctx_are_found_and_the_word_context_is_not(self):
        self.assertEqual(
            ctx_findings("Read it with `ctx_read`, search with ctx_search, via lean-ctx.\n"),
            ["ctx_read", "ctx_search", "lean-ctx"],
        )
        self.assertEqual(ctx_findings("Read the file; the context window; exact_ctx_x.\n"), [])

    def test_worktree_flow_help_pointer_is_found_both_ways(self):
        self.assertRegex("the command set is in `worktree-flow.py --help`.", WORKTREE_FLOW_HELP)
        self.assertRegex("See the `worktree-flow` tool's own help for its verbs.", WORKTREE_FLOW_HELP)
        self.assertNotRegex("the `worktree-flow` command set is in rust-orchestration.md.",
                            WORKTREE_FLOW_HELP)

    def test_routing_lines_name_the_reference_by_its_path(self):
        body = ("| Topic | Read |\n|---|---|\n| Gates (orchestrator) | `references/orchestration.md` |\n"
                "| Other | `references/other.md` |\n")
        self.assertEqual(routing_lines(body, ORCHESTRATION_REL),
                         ["| Gates (orchestrator) | `references/orchestration.md` |"])
        self.assertEqual(routing_lines("Read the orchestration notes.\n", ORCHESTRATION_REL), [])

    def test_a_skills_line_naming_the_skill_is_found_and_a_longer_name_is_not(self):
        prefix = agents.SKILLS_LINE_PREFIX
        texts = {
            "a": f"x\n{prefix} crucible, arduino-stack.\n",
            "b": f"{prefix} crucible.\nthe arduino-stack skill is the orchestrator's.\n",
            "c": f"{prefix} crucible, arduino-stack-extra.\n",
        }
        self.assertEqual(skills_lines_naming(texts, ARDUINO_STACK), ["a"])

    def test_defined_names_reads_functions_classes_and_assignments_at_any_depth(self):
        source = (
            "X: dict = {}\nY = 1\n\ndef f():\n    Z = 2\n\nclass C:\n    def m(self):\n        pass\n"
            "\nx.attr = 3\n"
        )
        self.assertEqual(defined_names(source), {"X", "Y", "f", "Z", "C", "m"})

    def test_beside_section_accepts_the_section_or_its_redisearch_neighbour_only(self):
        inside = "# T\n\n## RediSearch Module Best Practices\n\n```\nredis-cli FT._LIST\n```\n"
        after = ("# T\n\n## RediSearch Module Best Practices\n\nx\n\n## RediSearch commands\n\n"
                 "`FT._LIST`\n")
        far = ("# T\n\n## RediSearch Module Best Practices\n\nx\n\n## Other\n\ny\n\n## Commands\n\n"
               "`FT._LIST`\n")
        self.assertEqual(beside_section_findings(inside, "FT._LIST", "RediSearch"), [])
        self.assertEqual(beside_section_findings(after, "FT._LIST", "RediSearch"), [])
        self.assertEqual(
            beside_section_findings(far, "FT._LIST", "RediSearch"),
            ["'FT._LIST' is not in or beside the 'RediSearch Module Best Practices' section"],
        )
        self.assertEqual(beside_section_findings("# T\n", "FT._LIST", "RediSearch"),
                         ["no section titled 'RediSearch'"])


# ------------------------------------------------------------------ §S1.1 ----


class OrchestrationReferencesMovedTest(unittest.TestCase):
    """§S1.1/AC1 — each stack template lives only at its stack skill's reference, opens on a line
    naming it that skill's orchestrator reference, and keeps its headings."""

    def test_each_template_exists_only_at_its_stack_skills_reference(self):
        problems = []
        for old, new in ORCHESTRATION_TEMPLATE_MOVES.items():
            if (REPO_ROOT / old).exists():
                problems.append(f"{old} still exists")
            if not (REPO_ROOT / new).is_file():
                problems.append(f"{new} does not exist")
        self.assertEqual(problems, [], "§S1.1/AC1: each template moves to its stack skill")

    def test_each_references_first_line_names_it_the_stack_skills_orchestrator_reference(self):
        found = {
            stack: f
            for stack, text in _require_references(self).items()
            if (f := provenance_findings(stack, text))
        }
        self.assertEqual(found, {}, "§S1.1/AC1: the provenance line")

    def test_each_reference_keeps_the_templates_headings(self):
        texts = _require_references(self)
        for stack, expected in TEMPLATE_HEADINGS.items():
            with self.subTest(stack=stack):
                self.assertEqual(
                    headings(texts[stack]),
                    list(expected),
                    f"§S1.1: {ORCHESTRATION_REFERENCES[stack]} moves its headings as they are",
                )


# ------------------------------------------------------------------ §S1.2–3 ----


class StackSkillsRouteTheOrchestratorTest(unittest.TestCase):
    """§S1.2–3/AC2 — each stack skill's ``SKILL.md`` routes to ``references/orchestration.md``;
    no arduino definition loads ``arduino-stack``."""

    def _skill_md(self, name: str) -> str:
        path = SKILLS_DIR / name / "SKILL.md"
        self.assertTrue(path.is_file(), f"§S1.2: {path.relative_to(REPO_ROOT).as_posix()} exists")
        frontmatter, body = split_frontmatter(read_text(path))
        self.assertRegex(frontmatter, rf"(?m)^name: {re.escape(name)}$")
        return body

    def test_arduino_stack_skill_md_routes_to_its_orchestration_reference(self):
        body = self._skill_md(ARDUINO_STACK)
        self.assertEqual(
            len(routing_lines(body, ORCHESTRATION_REL)),
            1,
            f"§S1.2/AC2: arduino-stack's SKILL.md routes to {ORCHESTRATION_REL}; body={body!r}",
        )

    def test_java_and_rust_stack_each_route_the_orchestrator_to_the_reference(self):
        for name in ROUTED_FOR_THE_ORCHESTRATOR:
            with self.subTest(skill=name):
                rows = routing_lines(self._skill_md(name), ORCHESTRATION_REL)
                self.assertEqual(len(rows), 1, f"§S1.3/AC2: one routing row in {name}; {rows!r}")
                self.assertRegex(rows[0], r"(?i)\borchestrator\b",
                                 f"§S1.3: {name}'s row routes the orchestrator; {rows[0]!r}")

    def test_no_arduino_definition_names_arduino_stack_in_its_skills_line(self):
        # Regression pin (passes today): §S1.2's "no arduino role lists it". It fails against an
        # arduino.toml role listing arduino-stack, as the detector's own proof shows.
        texts = {f"render arduino-{role}": _rendered_definition("arduino", role) for role in ROLES}
        texts.update({
            p.relative_to(REPO_ROOT).as_posix(): read_text(p)
            for p in sorted(AGENTS_DIR.glob("arduino-*.md")) + sorted(PI_AGENTS_DIR.glob("arduino-*.md"))
        })
        self.assertGreaterEqual(len(texts), 2 * len(ROLES), "precondition: renders and files read")
        self.assertEqual(skills_lines_naming(texts, ARDUINO_STACK), [], "§S1.2/AC2")


class ArduinoStackInitTest(skills_gate._RepoAssetsSandbox):
    """§S1.2/AC2 — ``init --stacks arduino`` (sandboxed, Pi harness, the repository's own assets)
    renders ``arduino-stack`` with its reference, and the ``AGENTS.md`` stack line names it."""

    def setUp(self):
        super().setUp()
        self.target = self.root / "proj-arduino"
        self.axi = self.init_ok(self.target, "arduino")

    def test_init_renders_arduino_stack_and_its_orchestration_reference(self):
        self.assertEqual(
            skills_gate.skill_files(self.target),
            [skills_gate.rel(ARDUINO_STACK, "SKILL.md"), skills_gate.rel(ARDUINO_STACK, ORCHESTRATION_REL)],
            "§S1.2/AC2: init --stacks arduino renders .agents/skills/arduino-stack/",
        )

    def test_the_agents_md_stack_line_names_arduino_stack(self):
        freeze = md_section(read_text(self.target / "AGENTS.md"), "## Skill freeze")
        lines = [ln for ln in freeze.splitlines() if ln.startswith("- arduino:")]
        self.assertEqual(len(lines), 1, f"precondition: one arduino stack line; {freeze!r}")
        self.assertIn(f"`{ARDUINO_STACK}`", lines[0], "§S1.2/AC2: the stack line names it")


# ------------------------------------------------------------------ §S1.4–5 ----


class OrchestrationReferenceRewordingsTest(unittest.TestCase):
    """§S1.4–5/AC3 — what the move rewords: no raw runner, no ``ctx_`` tool or lean-ctx, no
    project's detail, no pointer to the Rust notes from the Java ones, and ``rust.toml``'s
    workspace-layout bullet points at no notes this CR retires."""

    def test_the_raw_runner_guard_finds_nothing_in_any_orchestration_reference(self):
        found = {
            ORCHESTRATION_REFERENCES[stack]: [f"line {n}: `{shown}`" for n, shown in hits]
            for stack, text in _require_references(self).items()
            if (hits := runner_gate.runner_findings(text))
        }
        self.assertEqual(found, {}, "§S1.4/AC3: `mvn clean verify` (twice) and `cargo llvm-cov "
                                    "nextest …` reworded to the client's verb or a description")

    def test_no_orchestration_reference_names_a_ctx_tool_or_lean_ctx(self):
        found = {
            ORCHESTRATION_REFERENCES[stack]: f
            for stack, text in _require_references(self).items()
            if (f := ctx_findings(text))
        }
        self.assertEqual(found, {}, "§S1.4/AC3")

    def test_generator_skills_hold_none_of_the_s1_5_anchors(self):
        _require_references(self)
        found = {
            p.relative_to(REPO_ROOT).as_posix(): f
            for p in sorted(SKILLS_DIR.rglob("*"))
            if p.is_file() and (f := anchor_findings(read_text(p)))
        }
        self.assertEqual(found, {}, "§S1.5/AC3: no project named in the Rust notes")

    def test_the_java_reference_names_no_rust_notes_and_points_at_worktree_flows_help(self):
        text = _require_references(self)["java"]
        self.assertEqual(text.count(RUST_NOTES_NAME), 0,
                         "§S1.4/AC3: a Java project has no Rust skill")
        self.assertIsNotNone(WORKTREE_FLOW_HELP.search(text),
                             "§S1.4: the command set is the worktree-flow tool's own help")

    def test_rust_toml_names_no_orchestration_notes_and_sends_feature_flags_to_agents_md(self):
        text = read_text(RUST_TOML)
        self.assertEqual(text.count(ORCHESTRATION_NOTES), 0,
                         f"§S1.5/AC3: rust.toml names {ORCHESTRATION_NOTES!r}")
        lines = [ln for ln in text.splitlines() if FEATURE_FLAGS_LINE.search(ln)]
        self.assertEqual(len(lines), 1, f"precondition: one per-crate feature-flags line; {lines!r}")
        self.assertIn("dispatch prompt", lines[0], "§S1.5: the dispatch prompt names them")
        self.assertIn("AGENTS.md", lines[0], "§S1.5: or the project's AGENTS.md")
        self.assertNotRegex(lines[0], r"(?i)orchestration\s+notes")


# ------------------------------------------------------------------ §S2 ----


class OperationalCommandsDroppedTest(unittest.TestCase):
    """§S2/AC3 — ``operational-commands.md`` goes; its Quarkus, schema-registry and RediSearch
    commands live in ``java-stack``'s ``references/quarkus-patterns.md``, whose routing row names
    them; its generic sections go."""

    def test_operational_commands_md_exists_nowhere_in_the_shipped_sources(self):
        found = sorted(
            p.relative_to(REPO_ROOT).as_posix()
            for root in ("skills-src", "generator")
            for p in (REPO_ROOT / root).rglob(OPERATIONAL_COMMANDS_NAME)
        )
        self.assertEqual(found, [], "§S2/AC3: operational-commands.md is deleted")

    def test_quarkus_patterns_carries_the_moved_commands_and_none_of_the_generic_sections(self):
        text = read_text(QUARKUS_PATTERNS)
        self.assertEqual([a for a in MOVED_COMMAND_ANCHORS if a not in text], [],
                         "§S2/AC3: the moved commands, by their anchors")
        titles = [title for title, _body in h2_sections(text)] + [h.lstrip("#").strip()
                                                                    for h in headings(text)]
        self.assertEqual(sorted({t for t in titles if t in DROPPED_SECTIONS}), [],
                         "§S2: the generic commands and the summary table go")

    def test_the_redisearch_commands_sit_beside_the_redisearch_section(self):
        self.assertEqual(
            beside_section_findings(read_text(QUARKUS_PATTERNS), REDISEARCH_ANCHOR, REDISEARCH_SECTION),
            [],
            "§S2: the RediSearch commands move beside the reference's RediSearch section",
        )

    def test_java_stacks_routing_row_for_quarkus_patterns_names_the_moved_commands(self):
        _frontmatter, body = split_frontmatter(read_text(SKILLS_DIR / "java-stack" / "SKILL.md"))
        rows = routing_lines(body, QUARKUS_PATTERNS_REL)
        self.assertEqual(len(rows), 1, f"precondition: one routing row; {rows!r}")
        self.assertEqual(
            [what for what, pattern in MOVED_COMMAND_TOPICS if not pattern.search(rows[0])],
            [],
            f"§S2/AC3: the row names the moved commands; {rows[0]!r}",
        )


# ------------------------------------------------------------------ §S3 ----


class InitWritesNoDocsMemoryTest(skills_gate._RepoAssetsSandbox):
    """§S3.1–2/AC4 — ``init`` (sandboxed, Pi harness, the repository's own assets) writes no
    ``docs/memory/`` for any stack, and names none; the template directory and its scaffold
    machinery are gone."""

    def test_init_for_each_stack_writes_no_docs_memory_and_lists_none(self):
        for stack in scaffold.KNOWN_STACKS:
            with self.subTest(stack=stack):
                target = self.root / f"proj-{stack}"
                axi = self.init_ok(target, stack)
                self.assertFalse((target / DOCS_MEMORY).exists(),
                                 f"§S3.1/AC4: init --stacks {stack} writes no docs/memory/")
                for key in ("planned", "emitted"):
                    listed = skills_gate._listed(axi, key)
                    self.assertTrue(listed, f"precondition: the envelope's {key} list; axi={axi!r}")
                    self.assertEqual([rel for rel in listed if rel.startswith(DOCS_MEMORY)], [],
                                     f"§S3.1/AC4: {key} names no docs/memory/ file")

    def test_skills_src_has_no_memory_templates_directory(self):
        self.assertFalse(MEMORY_TEMPLATES_DIR.exists(), "§S3.1/AC4: skills-src/memory-templates/ goes")

    def test_modelb_axi_defines_none_of_the_retired_symbols(self):
        found = {
            p.name: sorted(defined_names(read_text(p)) & set(RETIRED_SYMBOLS))
            for p in sorted(PACKAGE_DIR.glob("*.py"))
        }
        self.assertEqual({k: v for k, v in found.items() if v}, {}, "§S3.1/AC4")
        self.assertEqual([s for s in RETIRED_SYMBOLS if hasattr(scaffold, s)], [], "§S3.1/AC4")

    def test_modelb_axi_names_no_memory_templates_or_docs_memory(self):
        found = {}
        for path in sorted(PACKAGE_DIR.rglob("*")):
            parts = path.relative_to(PACKAGE_DIR).parts
            if not path.is_file() or "__pycache__" in parts or parts[0] == "_assets":
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if hits := [name for name in RETIRED_NAMES if name in text]:
                found[path.relative_to(REPO_ROOT).as_posix()] = hits
        self.assertEqual(found, {}, "§S3.1–2/AC4: scaffold.py's emission and docstrings, deploy.py's "
                                    "docstring")


class OlderProjectKeepsDocsMemoryTest(skills_gate._RepoAssetsSandbox):
    """§S3.3/AC7 — a project scaffolded before this CR keeps its ``docs/memory/`` untouched;
    ``modelb-axi agents``, run at its root, renders its stack skills, the orchestration reference
    included."""

    MEMORY_FILES = {
        "INDEX.md": "# Older — project memory index\n\n- [rust-orchestration.md](rust-orchestration.md)\n",
        "rust-orchestration.md": "# Rust Orchestration — this project's own notes\n\nKept as is.\n",
        "notes.md": "A file only this project has.\n",
    }

    def setUp(self):
        super().setUp()
        self.target = self.root / "older"
        self.init_ok(self.target, "rust")
        # The older project: no rendered stack skills yet, and a docs/memory/ of its own.
        shutil.rmtree(self.target / ".agents" / "skills", ignore_errors=True)
        memory = self.target / DOCS_MEMORY
        shutil.rmtree(memory, ignore_errors=True)
        memory.mkdir(parents=True)
        for name, text in self.MEMORY_FILES.items():
            (memory / name).write_text(text, encoding="utf-8")
        self.before = self._memory_snapshot()

    def _memory_snapshot(self) -> dict:
        memory = self.target / DOCS_MEMORY
        return {p.relative_to(memory).as_posix(): p.read_bytes()
                for p in sorted(memory.rglob("*")) if p.is_file()}

    def test_agents_keeps_docs_memory_and_renders_the_stack_skills_with_the_reference(self):
        axi = self.agents_ok(self.target)
        self.assertEqual(self._memory_snapshot(), self.before,
                         "§S3.3/AC7: docs/memory/ is left untouched, byte for byte")
        reference = skills_gate.rel("rust-stack", ORCHESTRATION_REL)
        self.assertEqual(
            skills_gate.skill_files(self.target),
            sorted(stack_skills.render_skills(GENERATOR_DIR, ["rust"])),
            "§S3.3: agents renders the project's stack skills from the installation's sources",
        )
        self.assertIn(reference, skills_gate.skill_files(self.target),
                      "§S3.3/AC7: the orchestration reference is rendered")
        self.assertIn(reference, skills_gate._listed(axi, "written"),
                      f"§S3.3: the envelope names it written; axi={axi!r}")


if __name__ == "__main__":
    unittest.main()
