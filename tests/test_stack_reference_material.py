"""rust's and arduino's reference material leaves its templates (CR-MDB-085 §S2–§S6).

Contract: ``docs/changes/CR-MDB-085-stack-skills-rendered-per-project.md``. §S1's mechanism (its
tests are ``tests.test_stack_skills``) renders a stack skill declared in
``generator/stack-skills.toml`` from ``generator/skills/<name>/``. This module holds the content
the CR moves with it:

- ``RustStackDeclaredTest`` — §S1.2/§S2/AC1: ``rust-stack`` is declared for ``rust`` and nothing
  else is; its source is a ``SKILL.md`` and ``references/e2e-docker-nextest.md``, the reference
  pointed to from ``SKILL.md``; a render for ``rust`` writes both, and for any other stack nothing.
- ``RustDefinitionsLoadRustStackTest`` — §S2/AC4: every rust role lists ``rust-stack``, so every
  rendered rust definition's skills line names it; ``rust.toml``'s "Companion memory" bullet names
  it; no other stack's definition names a stack skill.
- ``RustTomlNamesNoTemplateTest`` — §S3.6/AC5: ``rust.toml`` names no ``memory-templates/`` path
  and no ``-orchestration.md`` name, its provenance comment included.
- ``RustOrchestrationMovesTest`` — §S3.1, §S3.3, §S3.4/AC5: each §S3.1 row's anchor phrase is in
  its ``rust-stack`` destination and not in the template; the three deleted sections are gone; what
  stays, stays — the gate-sizing paragraph under a heading of its own.
- ``RustTomlRoleBulletsTest`` — §S3.2/AC5: each "RED/GREEN/VERIFY additions" bullet, by its anchor
  phrase, is in the named roles' gotchas of ``rust.toml`` and not in the template; the GREEN,
  VERIFY and FIX clippy commands pass ``--tests``; the dev-dependency promotion is reconciled with
  the forbidden-dependency escalation; ``--project-dir`` arrives without its stated premise.
- ``ArduinoMovesTest`` — §S3.5/AC5: "Hardware drivers" joins ``arduino.toml``'s GREEN and FIX
  gotchas; "Test tiers and agents" stays; the preamble no longer names gating hardware drivers.
- ``RustStackRestatesNothingTest`` — §S2/AC5: the references move verbatim (their bullets' leads
  are there), and nothing ``rust.toml`` states — the §S3.2 bullets, the deleted sections, any line
  of it — is restated in ``rust-stack``.
- ``TemplatePointerDetectorTest`` / ``TemplatePointerTest`` — §S4/AC6: :func:`pointer_findings`
  proved both ways, then run over the two templates.
- ``StackSkillRewordingDetectorTest`` / ``StackSkillRewordingsTest`` — §S5/AC7: the raw-runner guard
  and :func:`rewording_findings` over ``generator/skills/``.
- ``GatesReadGeneratorSkillsTest`` — §S6.1/AC8: each gate §S6.1 names collects the ``rust-stack``
  source files (the skill-frontmatter and Pi skill-loader halves live in
  ``tests.test_skill_frontmatter``).
- ``AgentsMdNamesStackSkillSourcesTest`` — §S6.4/AC9: ``AGENTS.md`` § Key Directories names
  ``generator/skills/`` and ``generator/stack-skills.toml``.
- ``GeneratorRowDetectorTest`` / ``GeneratorRowCurrentTest`` — §S6.4/AC9: :func:`generator_row_findings`
  proved both ways, then run over ``AGENTS.md``'s ``generator/`` row: it names every
  ``generator/stacks/*.toml`` and states the number of files in ``generator/agents/``, both
  derived from the tree.

Anchor phrases are the spec's (§S3 tables), checked as written. Hermetic: reads repository files
and renders in memory; nothing is installed or written outside a temp dir. Stdlib only.
"""

import re
import tomllib
import unittest
from pathlib import Path

from modelb_axi import agents, stack_skills
from tests import test_axi_envelope_read_whole as axi_gate
from tests import test_board_holds_the_queue as board_gate
from tests import test_cite_by_symbol as cite_gate
from tests import test_deployed_script_invocation as deployed_gate
from tests import test_gap_analysis_reach_and_pre_review as ordering_gate
from tests import test_project_registry_schema as registry_gate
from tests import test_raw_runner_guard as runner_gate
from tests import test_skill_frontmatter as frontmatter_gate
from tests import test_tooling_detachment as tooling_gate
from tests import test_worktree_flow_surfaces as worktree_gate
from tests._helpers import REPO_ROOT, md_section, read_text, split_frontmatter

GENERATOR_DIR = REPO_ROOT / "generator"
STACKS_DIR = GENERATOR_DIR / "stacks"
TEMPLATES_DIR = GENERATOR_DIR / "templates"
AGENTS_DIR = GENERATOR_DIR / "agents"
PI_AGENTS_DIR = REPO_ROOT / ".pi" / "agents"
SKILLS_DIR = GENERATOR_DIR / "skills"

RUST_TOML = STACKS_DIR / "rust.toml"
ARDUINO_TOML = STACKS_DIR / "arduino.toml"
RUST_TEMPLATE_REL = "skills-src/memory-templates/rust-orchestration.md"
ARDUINO_TEMPLATE_REL = "skills-src/memory-templates/arduino-orchestration.md"
RUST_TEMPLATE = REPO_ROOT / RUST_TEMPLATE_REL
ARDUINO_TEMPLATE = REPO_ROOT / ARDUINO_TEMPLATE_REL

#: §S1.2/§S2 — the one declaration this CR makes.
RUST_STACK = "rust-stack"
EXPECTED_DECLARATION = {RUST_STACK: ["rust"]}
RUST_STACK_DIR = SKILLS_DIR / RUST_STACK
SKILL_REL = "SKILL.md"
E2E_REFERENCE_REL = "references/e2e-docker-nextest.md"
RUST_STACK_SKILL = RUST_STACK_DIR / SKILL_REL
E2E_REFERENCE = RUST_STACK_DIR / E2E_REFERENCE_REL
#: §S1.3 — where ``init`` renders it.
RENDERED_RUST_STACK = {
    f".agents/skills/{RUST_STACK}/{SKILL_REL}",
    f".agents/skills/{RUST_STACK}/{E2E_REFERENCE_REL}",
}

STACKS = ("arduino", "bun", "python", "quarkus", "rust")
ROLES = ("red", "green", "verify", "fix")

#: §S3.1 — rust-orchestration.md to rust-stack: (moved section, anchor phrase, destination).
S3_1_ROWS = (
    (
        "E2E / docker / nextest-concurrency gotchas",
        "Container UID owns bind-mount writes",
        E2E_REFERENCE,
    ),
    (
        "the Pre-merge gate bullet on a new docker-dependent test",
        "added to BOTH nextest default-filters",
        E2E_REFERENCE,
    ),
    (
        "Flaky-test investigation principle",
        "Logical sequence + data integrity preserved",
        RUST_STACK_SKILL,
    ),
)

#: §S3.2 — rust-orchestration.md § "RED/GREEN/VERIFY additions" to rust.toml, by role:
#: (bullet, anchor phrase, the roles whose gotchas carry it).
S3_2_ROWS = (
    (
        "clippy runs with --tests",
        "clippy --crate <c> --tests",
        ("green", "verify", "fix"),
    ),
    (
        "read the summary, never the exit code",
        "never the exit code",
        ("green", "verify", "fix"),
    ),
    ("#[ignore] is temporary", "never a resting state", ("red", "green")),
    ("GREEN may promote a dependency", "from dev-only to production", ("green",)),
    (
        "a shared cross-crate enum variant",
        "verified per dependent crate",
        ("green", "verify"),
    ),
    (
        "--project-dir in a worktree",
        "--project-dir <absolute worktree>",
        ("red", "green", "verify", "fix"),
    ),
    (
        "a feature-gated test file's [[test]] entry",
        "required-features",
        ("red", "green"),
    ),
    (
        "a new crate's first RED pre-wires its dependencies",
        "pre-wires every dependency",
        ("red",),
    ),
)
#: §S3.2 — the ``--project-dir`` bullet arrives without its stated premise.
PROJECT_DIR_PREMISE = (
    "cwd resets between shell calls",
    "the default resolves the main tree",
)
#: §S3.2 — the clippy command form the GREEN, VERIFY and FIX gotchas show.
CLIPPY_COMMAND = re.compile(r"clippy --crate <c>(?P<rest>[^`\n]*)")

#: §S3.3 — deleted from rust-orchestration.md (already stated in rust.toml): (heading or lead,
#: a phrase of its content).
S3_3_DELETED = (
    ("RED that won't compile", "Rust RED frequently fails to **compile**"),
    ("Crucible ingest routing", "**Crucible ingest routing**"),
    ("Test naming", "Test function names describe the invariant under test"),
)

#: §S3.4 — what stays in rust-orchestration.md: (what, a phrase it is found by).
S3_4_STAYS = (
    ("the preamble", "# Rust Orchestration"),
    ("Tooling", "## Tooling"),
    ("Use the CLI", "**Use the CLI, NEVER inline python.**"),
    ("the worktree-flow.py subcommands", "subcommands (exactly 5"),
    ("Test scope", "## Test scope"),
    (
        "the other Pre-merge gate bullets",
        "Clippy `-D warnings` clean BEFORE any full merge regression",
    ),
    ("the other Pre-merge gate bullets", "Report skipped/ignored tests explicitly"),
    ("Disk hygiene", "## Disk hygiene"),
    ("CARGO_BUILD_JOBS cap", "## CARGO_BUILD_JOBS cap"),
    ("the gate-sizing paragraph", '"N consecutive runs"'),
)
FLAKY_HEADING = "Flaky-test investigation principle"

#: §S3.5 — the "Hardware drivers" anchors, and the section that stays.
HARDWARE_DRIVER_ANCHORS = (
    "Verify the exact part",
    "Hardware identity is the first bring-up gate",
)

#: §S2 — the references move verbatim: each bullet's lead (bold markers dropped).
E2E_LEADS = (
    "Container UID owns bind-mount writes.",
    "`docker compose down -v` does NOT touch host bind-mounts",
    "`docker compose up --wait` only waits on services WITH a healthcheck.",
    "nextest runs each test in its OWN process",
    "`#[serial]` only serializes WITHIN a binary.",
    "Half-stack vs full-stack `up` profiles cause silent cross-binary breakage.",
    "Cross-binary failures ≠ production defects (usually).",
    "One invariant per e2e test.",
    "Zero-cost-when-off assertions are no signal.",
    "A new docker-dependent test is added to BOTH nextest default-filters",
)
#: A rust.toml line at least this long, restated verbatim in rust-stack, is a restatement.
RESTATED_LINE_MIN = 40

#: §S5.2 — the project components the moved examples named.
PROJECT_EXAMPLES = (
    "ensure_compose_up",
    "http_client",
    "e2e_kafka",
    "e2e_telemetry",
    "total_acked",
)
_CTX_TOOL = re.compile(r"\bctx_[a-z_]+")
_LEAN_CTX = re.compile(r"lean-ctx", re.IGNORECASE)

#: §S4 — the sections §S3 moves, by template: patterns a sentence names one by.
MOVED_SECTION_NAMES = {
    RUST_TEMPLATE_REL: (
        r"e2e\s*/\s*docker\s*/\s*nextest",
        r"flaky-test investigation",
        r"red/green/verify additions",
        r"red that won't compile",
        r"crucible ingest routing",
        r"\btest naming\b",
    ),
    ARDUINO_TEMPLATE_REL: (r"\bhardware drivers?\b",),
}
#: §S4 — a new home: the stack's agent definitions, or its stack skill.
NEW_HOME = re.compile(r"rust-stack|stack skill|agent definition", re.IGNORECASE)

_HEADING = re.compile(r"^#{1,6}\s")
_FENCE = re.compile(r"^\s*(```|~~~)")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


# ------------------------------------------------------------------ helpers ----


def _load_toml(path: Path) -> dict:
    return tomllib.loads(read_text(path))


def _rust_stack_files() -> list[Path]:
    """Every file of the rust-stack source, sorted."""
    if not RUST_STACK_DIR.is_dir():
        return []
    return sorted(p for p in RUST_STACK_DIR.rglob("*") if p.is_file())


def _skills_line(text: str) -> str | None:
    return next(
        (ln for ln in text.splitlines() if agents.SKILLS_LINE_PREFIX in ln), None
    )


def _rendered(stack: str, role: str) -> str:
    """One definition rendered in memory from today's stack file and templates."""
    return agents.render(
        stack, role, agents.load_stack_params(STACKS_DIR, stack), TEMPLATES_DIR
    )


def _preamble(text: str) -> str:
    """The text before the first ``## `` heading."""
    return text.split("\n## ", 1)[0]


def _section_of(text: str, phrase: str) -> str | None:
    """The text of the nearest heading above the first line holding ``phrase``."""
    heading = None
    for line in text.splitlines():
        if _HEADING.match(line):
            heading = line.lstrip("#").strip()
        if phrase in line:
            return heading
    return None


def _sentences(text: str) -> list[str]:
    """The sentences of ``text``'s paragraphs and list items; headings and fenced lines are not
    sentences. A list item starts a block of its own."""
    blocks, current, fenced = [], [], False
    for line in text.splitlines():
        if _FENCE.match(line):
            fenced = not fenced
            continue
        stripped = line.strip()
        starts_item = re.match(r"^\s*(?:[-*+]|\d+\.)\s", line) is not None
        if fenced or not stripped or _HEADING.match(line) or starts_item:
            if current:
                blocks.append(" ".join(current))
            current = []
            if fenced or not stripped or _HEADING.match(line):
                continue
        current.append(stripped)
    if current:
        blocks.append(" ".join(current))
    return [s for block in blocks for s in _SENTENCE_END.split(block) if s.strip()]


def pointer_findings(text: str, names: tuple[str, ...]) -> list[str]:
    """§S4: each sentence of ``text`` that names a moved section (one of ``names``) without naming
    its new home (the agent definitions or the stack skill); and a ``generator/`` path anywhere."""
    found = [
        f"names a moved section without its new home: {s[:120]!r}"
        for s in _sentences(text)
        if any(re.search(n, s, re.IGNORECASE) for n in names) and not NEW_HOME.search(s)
    ]
    if "generator/" in text:
        found.append("names a generator/ path")
    return found


def rewording_findings(text: str) -> list[str]:
    """§S5.2/§S5.3: each project component a moved example names, each ``ctx_`` tool, lean-ctx."""
    found = [
        f"names the project component {name!r}"
        for name in PROJECT_EXAMPLES
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", text)
    ]
    found += [
        f"names the tool {tool!r}" for tool in sorted(set(_CTX_TOOL.findall(text)))
    ]
    if _LEAN_CTX.search(text):
        found.append("names lean-ctx")
    return found


# ------------------------------------------------------------------ §S1.2 / §S2 ----


class RustStackDeclaredTest(unittest.TestCase):
    """§S1.2/§S2/AC1 — ``rust-stack`` is declared for ``rust``, and its source is a ``SKILL.md``
    that points to ``references/e2e-docker-nextest.md``."""

    def test_the_declaration_names_rust_stack_for_rust_and_nothing_else(self):
        self.assertEqual(
            stack_skills.load_declaration(GENERATOR_DIR),
            EXPECTED_DECLARATION,
            "§S1.2: this CR declares rust-stack for rust; no arduino-stack (§S3.5)",
        )

    def test_the_rust_stack_source_is_its_skill_md_and_the_e2e_reference(self):
        rels = [p.relative_to(RUST_STACK_DIR).as_posix() for p in _rust_stack_files()]
        self.assertEqual(rels, sorted([SKILL_REL, E2E_REFERENCE_REL]))
        frontmatter, body = split_frontmatter(read_text(RUST_STACK_SKILL))
        fields = dict(
            ln.split(": ", 1) for ln in frontmatter.splitlines() if ": " in ln
        )
        self.assertEqual(fields.get("name"), RUST_STACK)
        self.assertTrue(
            fields.get("description", "").strip(), "SKILL.md carries a description"
        )
        self.assertIn(
            E2E_REFERENCE_REL,
            body,
            "a reference is read only when SKILL.md points to it",
        )

    def test_a_render_for_rust_writes_rust_stack_and_for_any_other_stack_nothing(self):
        self.assertEqual(
            set(stack_skills.render_skills(GENERATOR_DIR, ["rust"])),
            RENDERED_RUST_STACK,
        )
        for stack in ("arduino", "bun", "python", "quarkus"):
            with self.subTest(stack=stack):
                self.assertEqual(stack_skills.render_skills(GENERATOR_DIR, [stack]), {})


class RustDefinitionsLoadRustStackTest(unittest.TestCase):
    """§S2/AC4 — every rust definition loads ``rust-stack``; no other stack's names one."""

    def test_every_rust_role_lists_rust_stack_in_its_skills(self):
        roles = _load_toml(RUST_TOML)["roles"]
        missing = [
            role for role in ROLES if RUST_STACK not in roles[role].get("skills", [])
        ]
        self.assertEqual(
            missing, [], "§S2: every role of the rust stack lists rust-stack"
        )

    def test_every_rendered_rust_definition_skills_line_names_rust_stack(self):
        failures = []
        for role in ROLES:
            for label, text in (
                ("render", _rendered("rust", role)),
                ("generator/agents", read_text(AGENTS_DIR / f"rust-{role}-agent.md")),
            ):
                line = _skills_line(text)
                if line is None or RUST_STACK not in line:
                    failures.append(f"rust-{role} ({label}): {line!r}")
        self.assertEqual(
            failures,
            [],
            "AC4: each rust skills line names rust-stack, e.g. "
            "'Load these skills first: crucible, rust-stack.'",
        )

    def test_no_other_stacks_definition_names_a_stack_skill(self):
        declared = set(stack_skills.load_declaration(GENERATOR_DIR))
        self.assertEqual(
            declared, set(EXPECTED_DECLARATION), "precondition: the declared skills"
        )
        texts = {
            f"render {s}-{r}": _rendered(s, r)
            for s in STACKS
            if s != "rust"
            for r in ROLES
        }
        texts.update(
            {
                p.relative_to(REPO_ROOT).as_posix(): read_text(p)
                for p in sorted(AGENTS_DIR.glob("*-agent.md"))
                + sorted(PI_AGENTS_DIR.glob("*.md"))
                if not p.name.startswith("rust-")
            }
        )
        found = sorted(
            f"{where}: {name}"
            for where, text in texts.items()
            for name in declared
            if name in text
        )
        self.assertEqual(
            found, [], "AC4: no other stack's definition names a stack skill"
        )

    def test_the_companion_memory_bullet_names_rust_stack_instead_of_the_template(self):
        mechanics = _load_toml(RUST_TOML)["mechanics"]
        bullets = [
            ln for ln in mechanics.splitlines() if ln.startswith("- **Companion memory")
        ]
        self.assertEqual(
            len(bullets), 1, "rust.toml's mechanics carry one Companion memory bullet"
        )
        self.assertIn(RUST_STACK, bullets[0])
        self.assertNotIn("memory-templates/", bullets[0])


class RustTomlNamesNoTemplateTest(unittest.TestCase):
    """§S3.6/AC5 — ``rust.toml`` names no template path, its provenance comment included."""

    def test_rust_toml_names_no_memory_templates_path_and_no_orchestration_name(self):
        text = read_text(RUST_TOML)
        found = sorted(
            set(re.findall(r"memory-templates/|[\w-]+-orchestration\.md", text))
        )
        self.assertEqual(found, [], "§S3.6: rust.toml names a template")


# ------------------------------------------------------------------ §S3 ----


class RustOrchestrationMovesTest(unittest.TestCase):
    """§S3.1/§S3.3/§S3.4/AC5 — what leaves rust-orchestration.md, and what stays."""

    def setUp(self):
        self.template = read_text(RUST_TEMPLATE)

    def test_each_s3_1_row_is_in_rust_stack_and_not_in_the_template(self):
        problems = []
        for section, anchor, destination in S3_1_ROWS:
            if not destination.is_file() or anchor not in read_text(destination):
                problems.append(
                    f"{section}: {anchor!r} is not in "
                    f"{destination.relative_to(REPO_ROOT).as_posix()}"
                )
            if anchor in self.template:
                problems.append(
                    f"{section}: {anchor!r} is still in {RUST_TEMPLATE_REL}"
                )
        self.assertEqual(problems, [], "§S3.1")

    def test_the_gate_sizing_paragraph_stays_under_a_heading_of_its_own(self):
        heading = _section_of(self.template, '"N consecutive runs"')
        self.assertIsNotNone(
            heading, "§S3.1: the gate-sizing paragraph stays in the template"
        )
        self.assertNotEqual(heading, f"{FLAKY_HEADING} (timing/parallel-load failures)")
        self.assertFalse((heading or "").startswith(FLAKY_HEADING), heading)

    def test_the_three_deleted_sections_are_gone_from_the_template(self):
        headings = [
            ln.lstrip("#").strip()
            for ln in self.template.splitlines()
            if _HEADING.match(ln)
        ]
        found = [
            name
            for name, phrase in S3_3_DELETED
            if name in headings or phrase in self.template
        ]
        self.assertEqual(found, [], "§S3.3: deleted (rust.toml already states them)")

    def test_what_stays_stays(self):
        missing = [
            f"{what}: {phrase!r}"
            for what, phrase in S3_4_STAYS
            if phrase not in self.template
        ]
        self.assertEqual(missing, [], "§S3.4: stays in rust-orchestration.md")


class RustTomlRoleBulletsTest(unittest.TestCase):
    """§S3.2/AC5 — the "RED/GREEN/VERIFY additions" bullets join the named roles' gotchas."""

    def setUp(self):
        self.gotchas = _load_toml(RUST_TOML)["gotchas"]
        self.template = read_text(RUST_TEMPLATE)

    def test_each_bullet_is_in_its_roles_gotchas_and_not_in_the_template(self):
        problems = []
        for bullet, anchor, roles in S3_2_ROWS:
            problems += [
                f"{bullet}: {anchor!r} not in [gotchas].{role}"
                for role in roles
                if anchor not in self.gotchas[role]
            ]
            if anchor in self.template:
                problems.append(f"{bullet}: {anchor!r} still in {RUST_TEMPLATE_REL}")
        self.assertEqual(problems, [], "§S3.2")

    def test_the_red_green_verify_additions_heading_leaves_the_template(self):
        self.assertNotIn("## RED/GREEN/VERIFY additions", self.template)

    def test_the_green_verify_and_fix_clippy_commands_pass_tests(self):
        problems = []
        for role in ("green", "verify", "fix"):
            commands = [m.group(0) for m in CLIPPY_COMMAND.finditer(self.gotchas[role])]
            if not commands:
                problems.append(f"{role}: shows no clippy command")
            problems += [
                f"{role}: {m.group(0)!r}"
                for m in CLIPPY_COMMAND.finditer(self.gotchas[role])
                if not m.group("rest").startswith(" --tests")
            ]
        self.assertEqual(
            problems,
            [],
            "§S3.2: every GREEN, VERIFY and FIX clippy command passes --tests",
        )

    def test_the_dependency_promotion_is_reconciled_with_the_forbidden_dependency_escalation(
        self,
    ):
        green = self.gotchas["green"]
        self.assertIn("from dev-only to production", green)
        self.assertRegex(
            green,
            r"(?s)forbidden dependency.{0,200}ESCALATION|ESCALATION.{0,200}"
            r"forbidden dependency",
            "§S3.2: a new or forbidden dependency still escalates",
        )

    def test_the_project_dir_bullet_arrives_without_its_stated_premise(self):
        text = read_text(RUST_TOML)
        self.assertIn("--project-dir <absolute worktree>", text)
        self.assertEqual(
            [p for p in PROJECT_DIR_PREMISE if p in text],
            [],
            "§S3.2: the --project-dir bullet arrives without its premise",
        )


class ArduinoMovesTest(unittest.TestCase):
    """§S3.5/AC5 — "Hardware drivers" joins arduino.toml's GREEN and FIX gotchas."""

    def setUp(self):
        self.template = read_text(ARDUINO_TEMPLATE)
        self.gotchas = _load_toml(ARDUINO_TOML)["gotchas"]

    def test_the_hardware_driver_rules_are_in_the_green_and_fix_gotchas(self):
        missing = [
            f"{role}: {a!r}"
            for role in ("green", "fix")
            for a in HARDWARE_DRIVER_ANCHORS
            if a not in self.gotchas[role]
        ]
        self.assertEqual(missing, [], "§S3.5")

    def test_the_hardware_driver_rules_left_the_template_and_test_tiers_stays(self):
        self.assertEqual([a for a in HARDWARE_DRIVER_ANCHORS if a in self.template], [])
        self.assertNotIn("## Hardware drivers", self.template)
        self.assertIn("## Test tiers and agents", self.template)
        self.assertIn("raise it to Model B", self.template)

    def test_the_preamble_no_longer_names_gating_hardware_drivers(self):
        self.assertNotRegex(_preamble(self.template), r"(?i)hardware\s+drivers?")


class RustStackRestatesNothingTest(unittest.TestCase):
    """§S2/AC5 — the references move verbatim, and rust-stack restates nothing rust.toml states."""

    def setUp(self):
        self.files = _rust_stack_files()
        self.assertTrue(
            self.files, f"{RUST_STACK_DIR.relative_to(REPO_ROOT)} has no files"
        )
        self.text = "\n".join(read_text(p) for p in self.files)

    def test_the_e2e_reference_carries_every_moved_bullet_lead(self):
        reference = read_text(E2E_REFERENCE).replace("**", "")
        self.assertEqual([lead for lead in E2E_LEADS if lead not in reference], [])

    def test_no_s3_2_bullet_and_no_deleted_section_is_restated(self):
        found = [anchor for _b, anchor, _r in S3_2_ROWS if anchor in self.text]
        found += [phrase for _n, phrase in S3_3_DELETED if phrase in self.text]
        self.assertEqual(found, [], "AC5: no moved text is restated in rust-stack")

    def test_no_line_of_rust_toml_is_restated_in_rust_stack(self):
        lines = {
            ln.strip().lstrip("-").strip() for ln in read_text(RUST_TOML).splitlines()
        }
        restated = sorted(
            ln for ln in lines if len(ln) >= RESTATED_LINE_MIN and ln in self.text
        )
        self.assertEqual(
            restated, [], "§S2: SKILL.md restates nothing rust.toml states"
        )


# ------------------------------------------------------------------ §S4 ----


class TemplatePointerDetectorTest(unittest.TestCase):
    """§S4 — :func:`pointer_findings` proved both ways on synthetic text."""

    RUST = MOVED_SECTION_NAMES[RUST_TEMPLATE_REL]
    ARDUINO = MOVED_SECTION_NAMES[ARDUINO_TEMPLATE_REL]

    def test_a_sentence_naming_a_moved_section_without_a_home_is_found(self):
        for text, names in (
            (
                "# T\n\nRe-read the E2E / docker / nextest-concurrency gotchas first.\n",
                self.RUST,
            ),
            ("- See RED/GREEN/VERIFY additions. Then merge.\n", self.RUST),
            ("This file owns the toolset and gating hardware drivers.\n", self.ARDUINO),
        ):
            with self.subTest(text=text):
                self.assertEqual(
                    len(pointer_findings(text, names)), 1, pointer_findings(text, names)
                )

    def test_a_sentence_naming_its_new_home_a_heading_and_a_fence_are_not(self):
        for text, names in (
            (
                "The E2E / docker / nextest-concurrency gotchas live in the `rust-stack` skill.\n",
                self.RUST,
            ),
            ("## Test naming\n\nOther text.\n", self.RUST),
            ("```\nRED that won't compile\n```\n", self.RUST),
            (
                "Hardware driver rules live in the arduino agent definitions.\n",
                self.ARDUINO,
            ),
            ("Keep the toolset current.\n", self.ARDUINO),
        ):
            with self.subTest(text=text):
                self.assertEqual(pointer_findings(text, names), [])

    def test_a_generator_path_is_found(self):
        self.assertEqual(
            pointer_findings("Edit `generator/stacks/rust.toml`.\n", ()),
            ["names a generator/ path"],
        )


class TemplatePointerTest(unittest.TestCase):
    """§S4/AC6 — no sentence left in either template names a moved section without its new home,
    and neither names a ``generator/`` path."""

    def test_each_template_points_at_where_its_material_went(self):
        found = {
            rel: f
            for rel, names in MOVED_SECTION_NAMES.items()
            if (f := pointer_findings(read_text(REPO_ROOT / rel), names))
        }
        self.assertEqual(found, {}, "§S4")


# ------------------------------------------------------------------ §S5 ----


class StackSkillRewordingDetectorTest(unittest.TestCase):
    """§S5 — :func:`rewording_findings` proved both ways on synthetic text."""

    def test_each_project_component_ctx_tool_and_lean_ctx_is_found(self):
        text = (
            "Poll in `ensure_compose_up`; `http_client.head(url)`; binaries `e2e_kafka`, "
            "`e2e_telemetry`; `total_acked >= N`. Read with `ctx_read`, via lean-ctx.\n"
        )
        self.assertEqual(
            rewording_findings(text),
            [
                "names the project component 'ensure_compose_up'",
                "names the project component 'http_client'",
                "names the project component 'e2e_kafka'",
                "names the project component 'e2e_telemetry'",
                "names the project component 'total_acked'",
                "names the tool 'ctx_read'",
                "names lean-ctx",
            ],
        )

    def test_neutral_examples_are_not(self):
        text = (
            "Poll in the harness's compose-up helper; an HTTP HEAD proves the listener is "
            "bound; two binaries `e2e_alpha` and `e2e_beta`; an ack counter. Read the file.\n"
        )
        self.assertEqual(rewording_findings(text), [])


class StackSkillRewordingsTest(unittest.TestCase):
    """§S5/AC7 — ``generator/skills/`` teaches no runner invocation, names no project component,
    no ``ctx_`` tool and no lean-ctx."""

    def setUp(self):
        self.files = (
            sorted(p for p in SKILLS_DIR.rglob("*") if p.is_file())
            if SKILLS_DIR.is_dir()
            else []
        )
        self.assertIn(
            RUST_STACK_SKILL, self.files, "generator/skills/ holds rust-stack"
        )

    def test_the_raw_runner_guard_over_generator_skills_finds_nothing(self):
        found = [
            f"{p.relative_to(REPO_ROOT).as_posix()} line {n}: `{shown}`"
            for p in self.files
            for n, shown in runner_gate.runner_findings(read_text(p))
        ]
        self.assertEqual(found, [], "§S5.1: a stack skill teaches no runner invocation")

    def test_generator_skills_name_no_project_component_ctx_tool_or_lean_ctx(self):
        found = {
            p.relative_to(REPO_ROOT).as_posix(): f
            for p in self.files
            if (f := rewording_findings(read_text(p)))
        }
        self.assertEqual(found, {}, "§S5.2/§S5.3")


# ------------------------------------------------------------------ §S6.1 ----


def _gate_collections() -> dict[str, set[Path]]:
    """What each gate §S6.1 names reads, as absolute paths."""

    def resolved(paths):
        return {Path(p).resolve() for p in paths}

    return {
        "raw-runner guard": resolved(runner_gate.guarded_files()),
        "AXI envelope guard": resolved(axi_gate.guarded_files()),
        "skill-frontmatter checks": resolved(frontmatter_gate._stack_skill_files()),
        "test_tooling_detachment": resolved(
            p
            for root in tooling_gate.S6_SCAN_ROOTS
            for p in tooling_gate._scan_files(root)
        ),
        "test_deployed_script_invocation": resolved(deployed_gate._gated_files()),
        "test_project_registry_schema": resolved(
            REPO_ROOT / rel for rel, _ in registry_gate._shipped_files()
        ),
        "test_worktree_flow_surfaces": resolved(worktree_gate._iter_surface_files()),
        "test_board_holds_the_queue": resolved(
            REPO_ROOT / rel for rel in board_gate.shipped_surfaces()
        ),
        "test_cite_by_symbol": resolved(cite_gate.guarded_files(REPO_ROOT)),
        "test_gap_analysis_reach_and_pre_review": resolved(
            REPO_ROOT / rel for rel, _ in ordering_gate._ordering_surfaces()
        ),
    }


class GatesReadGeneratorSkillsTest(unittest.TestCase):
    """§S6.1/AC8 — each gate §S6.1 names reads ``generator/skills/``: it collects rust-stack's
    ``SKILL.md`` (and its reference, where the gate reads more than skill frontmatter)."""

    def test_each_named_gate_collects_the_rust_stack_sources(self):
        missing = []
        for gate, files in _gate_collections().items():
            wanted = [RUST_STACK_SKILL] + (
                [] if gate == "skill-frontmatter checks" else [E2E_REFERENCE]
            )
            missing += [
                f"{gate}: {p.relative_to(REPO_ROOT).as_posix()}"
                for p in wanted
                if p.resolve() not in files
            ]
        self.assertEqual(missing, [], "§S6.1: a gate does not read generator/skills/")


# ------------------------------------------------------------------ §S6.4 ----


class AgentsMdNamesStackSkillSourcesTest(unittest.TestCase):
    """§S6.4/AC9 — ``AGENTS.md`` § Key Directories names the stack skills' sources."""

    def test_key_directories_name_generator_skills_and_the_declaration(self):
        section = md_section(read_text(REPO_ROOT / "AGENTS.md"), "## Key Directories")
        self.assertTrue(section, "AGENTS.md has a Key Directories section")
        self.assertEqual(
            [
                n
                for n in ("generator/skills/", "generator/stack-skills.toml")
                if n not in section
            ],
            [],
        )



#: §S6.4 — a stated count of generated definitions: ``<n> files`` or ``<n> [generated] definitions``.
_DEFINITION_COUNT = re.compile(r"(?<![\w.-])(\d+) (?:generated )?(?:files|definitions)\b")


def generator_row(agents_md: str) -> str:
    """The ``generator/`` row of ``agents_md``'s ``## Key Directories`` table ("" when none)."""
    for line in md_section(agents_md, "## Key Directories").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if line.lstrip().startswith("|") and cells[0].strip("`") == "generator/":
            return line
    return ""


def generator_row_findings(agents_md: str, stacks: list[str], definitions: int) -> list[str]:
    """What the ``generator/`` row of ``agents_md`` gets wrong against the tree (§S6.4): a stack
    of ``stacks`` (the ``generator/stacks/*.toml`` stems) it does not name, and a stated count of
    generated definitions other than exactly one, equal to ``definitions``."""
    row = generator_row(agents_md)
    if not row:
        return ["AGENTS.md: the Key Directories table has no generator/ row"]
    out = [
        f"the generator/ row does not name the stack file {stack}.toml"
        for stack in stacks
        if not re.search(rf"(?<![\w-]){re.escape(stack)}(?![\w-])", row)
    ]
    counts = _DEFINITION_COUNT.findall(row)
    if counts != [str(definitions)]:
        out.append(
            f"the generator/ row states {counts} as the generated definitions' count; "
            f"generator/agents/ holds {definitions}"
        )
    return out


class GeneratorRowDetectorTest(unittest.TestCase):
    """§S6.4 — :func:`generator_row_findings` proved both ways on synthetic tables."""

    STACKS = ["arduino", "bun", "rust"]

    @staticmethod
    def _agents_md(row: str) -> str:
        return (
            "# T\n\n## Key Directories\n\n| Path | Purpose |\n|---|---|\n"
            f"| `skills-src/` | bundles |\n{row}\n\n## Next\n\n"
            "| `generator/` | stacks/{arduino}.toml (9 files) |\n"
        )

    def test_a_current_row_has_no_finding(self):
        row = "| `generator/` | `stacks/{arduino,bun,rust}.toml` → `agents/` (12 files) |"
        self.assertEqual(generator_row_findings(self._agents_md(row), self.STACKS, 12), [])

    def test_a_row_missing_a_stack_or_stating_a_stale_count_is_found(self):
        row = "| `generator/` | `stacks/{arduino,bun}.toml` → `agents/` (8 files); rust-stack |"
        self.assertEqual(
            generator_row_findings(self._agents_md(row), self.STACKS, 12),
            [
                "the generator/ row does not name the stack file rust.toml",
                "the generator/ row states ['8'] as the generated definitions' count; "
                "generator/agents/ holds 12",
            ],
        )

    def test_a_row_stating_no_count_or_a_second_count_is_found(self):
        for label, row, counts in (
            ("no count", "| `generator/` | `stacks/{arduino,bun,rust}.toml` |", []),
            (
                "a stale count beside the right one",
                "| `generator/` | `stacks/{arduino,bun,rust}.toml` (12 files, was 8 files) |",
                ["12", "8"],
            ),
        ):
            with self.subTest(case=label):
                self.assertEqual(
                    generator_row_findings(self._agents_md(row), self.STACKS, 12),
                    [
                        f"the generator/ row states {counts} as the generated definitions' "
                        "count; generator/agents/ holds 12"
                    ],
                )

    def test_a_table_with_no_generator_row_is_found(self):
        self.assertEqual(
            generator_row_findings(self._agents_md("| `tools/` | repo-only |"), self.STACKS, 12),
            ["AGENTS.md: the Key Directories table has no generator/ row"],
            "a generator/ row outside ## Key Directories does not count",
        )


class GeneratorRowCurrentTest(unittest.TestCase):
    """§S6.4/AC9 — ``AGENTS.md``'s ``generator/`` row names every ``generator/stacks/*.toml``
    and the number of files in ``generator/agents/``, both read from the tree."""

    def test_the_generator_row_names_every_stack_file_and_the_definitions_count(self):
        stacks = sorted(path.stem for path in STACKS_DIR.glob("*.toml"))
        definitions = sum(1 for path in AGENTS_DIR.iterdir() if path.is_file())
        self.assertTrue(stacks, "precondition: generator/stacks/ holds stack files")
        self.assertGreater(definitions, 0, "precondition: generator/agents/ holds definitions")
        self.assertEqual(
            generator_row_findings(read_text(REPO_ROOT / "AGENTS.md"), stacks, definitions),
            [],
            "§S6.4/AC9: the generator/ row states the tree's stack files and definitions",
        )


if __name__ == "__main__":
    unittest.main()
