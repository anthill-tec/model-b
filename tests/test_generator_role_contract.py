"""RED-phase gates for CR-MDB-017 §S6 (cycle C3) — the generator's registration
line (§S6a) and its per-stack tier guidance (§S6b).

Written BEFORE the GREEN-phase work lands (the four role templates lose
``--phase`` and gain ``--role``/``--cycle``; each stack TOML gains a
``tier_guidance`` key; the templates gain the shared tier preamble; all 16
definitions are regenerated), so these assertions are expected to FAIL against
the current tree. Measured at authoring time on
``feature/CR-MDB-017-client-role-contract-sync`` @ ``b1b013d``: 20 ``--phase``
occurrences under ``generator/`` (4 templates + 16 generated agents), zero
``--role`` and zero ``--cycle`` in any template or generated agent, and zero
``tier_guidance`` keys across the stack TOMLs.

Scope boundary (CR §S6, final AC): this module neither creates nor asserts the
absence of ``generator/stacks/rust.toml``. Rust belongs to CR-MDB-024, which
DEPENDS on this CR — an assertion that the file does not exist would break its
own dependent on landing. Every stack and role list here is therefore DERIVED
by globbing ``generator/stacks/*.toml``, ``generator/templates/*.md.tmpl`` and
``generator/agents/*.md``; nothing is hardcoded to the present four, so a fifth
stack widens these gates instead of breaking them.

All scanning walks the tree in Python (``pathlib``) — no shelling out to grep.
The single exception is the ``build.py --check`` drift gate, justified in its
own method docstring. Failure messages carry ``file:line`` so the GREEN agent
gets a work list rather than a boolean.
"""

import re
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path

from tests._helpers import read_text as _text

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR_DIR = REPO_ROOT / "generator"
TEMPLATES_DIR = GENERATOR_DIR / "templates"
STACKS_DIR = GENERATOR_DIR / "stacks"
AGENTS_DIR = GENERATOR_DIR / "agents"

DN_PLAN_REVIEW = "docs/research/DN-rationalization-plan-review.md"

# The fleet-uniform tier vocabulary (CR-CRU-111 §S1 / CR §S6b). Lowercase,
# exact: these are client verbs, not prose.
TIER_VOCABULARY = ("unit", "module", "integration", "e2e", "bdd", "regression")

# Stack-specific run verbs that must NOT stand in for the vocabulary inside the
# SHARED preamble (CR §S6b: "the preamble therefore states one vocabulary
# rather than per-stack run verbs").
STACK_RUN_VERBS = ("bun test", "pytest", "mvn test", "arduino-cli")

# ``--phase`` is retired fleet-wide; ``--phaseless`` etc. would still be a hit,
# so the boundary only excludes word/hyphen continuation on the right.
PHASE_RE = re.compile(r"--phase(?![\w-])")
ROLE_RE = re.compile(r"--role(?![\w-])")
# Word-boundaried so ``--cycles`` (and ``--cycle-kind``) cannot satisfy a
# ``--cycle`` requirement.
CYCLE_RE = re.compile(r"--cycle(?![\w-])")

CYCLE_WORD_RE = re.compile(r"(?i)(?:--cycle(?![\w-])|\bcycle\b)")
REQUIRED_WORD_RE = re.compile(r"(?i)\b(required|mandatory|must)\b")
REFUSAL_WORD_RE = re.compile(r"(?i)(\b409\b|refus|reject|unbound)")
DECLINED_RE = re.compile(
    r"(?i)(declined|closed|withdrawn|not to be built|never built|must not be built|"
    r"will not be built|won't be built)"
)
UNREACHABLE_RE = re.compile(
    r"(?i)(cannot|can't|can not|unreachable|unavailable|not honou?r|"
    r"no\s+\w+\s+tier|never\s+report|out of reach|not\s+available)"
)


def _rel(path):
    """Repo-relative POSIX path for a failure message."""
    return path.relative_to(REPO_ROOT).as_posix()


def _lines(path):
    """1-based (lineno, line) pairs."""
    return list(enumerate(_text(path).splitlines(), start=1))


def _generator_text_files():
    """Every decodable file under generator/, caches excluded, sorted."""
    found = []
    for path in sorted(GENERATOR_DIR.rglob("*")):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts:
            continue
        try:
            path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, ValueError):
            continue
        found.append(path)
    return found


def _stack_names():
    """Stack ids derived from generator/stacks/*.toml — never hardcoded."""
    return sorted(p.stem for p in STACKS_DIR.glob("*.toml"))


def _role_names():
    """Role ids derived from generator/templates/*.md.tmpl — never hardcoded."""
    return sorted(p.name[: -len(".md.tmpl")] for p in TEMPLATES_DIR.glob("*.md.tmpl"))


def _template_path(role):
    return TEMPLATES_DIR / f"{role}.md.tmpl"


AGENT_NAME_RE = re.compile(r"^(?P<stack>.+)-(?P<role>[^-]+)-agent\.md$")


def _generated_agents():
    """(stack, role, path) for every generated definition, glob-derived."""
    agents = []
    for path in sorted(AGENTS_DIR.glob("*.md")):
        match = AGENT_NAME_RE.match(path.name)
        if not match:
            continue
        agents.append((match.group("stack"), match.group("role"), path))
    return agents


def _stack_params(stack):
    with (STACKS_DIR / f"{stack}.toml").open("rb") as handle:
        return tomllib.load(handle)


def _key_lineno(stack, key):
    """1-based line of a top-level TOML key, or the file's line 1 if absent."""
    pattern = re.compile(r"^\s*" + re.escape(key) + r"\s*=")
    for lineno, line in _lines(STACKS_DIR / f"{stack}.toml"):
        if pattern.match(line):
            return lineno
    return 1


def _hits(path, regex):
    """[(lineno, line)] for every line of path matching regex."""
    return [(lineno, line) for lineno, line in _lines(path) if regex.search(line)]


def _fmt(entries):
    """Render a ``file:line`` work list, one entry per line."""
    return "\n".join(f"  {rel}:{lineno}: {text.strip()}" for rel, lineno, text in entries)


HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def _tier_section(path):
    """Extract the tier-guidance section of a rendered agent.

    Returns ``(heading_lineno, section_text)`` for the first markdown heading
    whose text mentions "tier", running to the next heading of the same or a
    higher level (the structure the generator already uses for "## Stack
    mechanics"). Returns ``(0, None)`` when no such section exists — which is
    the state today, and is reported as the failure rather than crashing.

    Deliberately does NOT pin the heading's exact wording: the CR specifies the
    section's CONTENT and its shared/per-stack split, not its title.
    """
    lines = _text(path).splitlines()
    start = None
    level = 0
    for index, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if not match:
            continue
        if start is None:
            if "tier" in match.group(2).lower():
                start = index
                level = len(match.group(1))
            continue
        if len(match.group(1)) <= level:
            return start + 1, "\n".join(lines[start:index])
    if start is None:
        return 0, None
    return start + 1, "\n".join(lines[start:])


class GeneratorRoleContractS6aTest(unittest.TestCase):
    """§S6a — the registration line the 16 generated agents instruct.

    ``--phase`` is hard-coded in all four role templates and propagated into
    all 16 definitions, so every generated agent currently instructs a
    registration that cannot parse; and with ``--cycle`` absent, even a
    corrected ``--role`` would be refused 409 for the four TDD roles.
    """

    def test_s6a_no_phase_flag_anywhere_under_generator(self):
        """Zero `--phase` under generator/ — templates, stacks AND agents."""
        found = []
        for path in _generator_text_files():
            for lineno, line in _hits(path, PHASE_RE):
                found.append((_rel(path), lineno, line))
        self.assertEqual(
            found,
            [],
            "`--phase` is retired fleet-wide (CR-MDB-017 §S6a) but still occurs "
            f"{len(found)} time(s) under generator/:\n{_fmt(found)}",
        )

    def test_s6a_each_role_template_emits_case_exact_role_flag(self):
        """Each role template emits `--role <ROLE>` in its own case-exact role."""
        roles = _role_names()
        self.assertTrue(roles, "no role templates found under generator/templates/")
        problems = []
        for role in roles:
            path = _template_path(role)
            expected = role.upper()
            wanted = re.compile(r"--role\s+" + expected + r"(?![\w-])")
            if not wanted.search(_text(path)):
                anchor = _hits(path, re.compile(r"\$\{register_command\}"))
                lineno = anchor[0][0] if anchor else 1
                problems.append(
                    (_rel(path), lineno, f"expected `--role {expected}` — not present")
                )
            for lineno, line in _hits(path, ROLE_RE):
                emitted = re.search(r"--role\s+(\S+)", line)
                if emitted and emitted.group(1) != expected:
                    problems.append(
                        (_rel(path), lineno,
                         f"emits `--role {emitted.group(1)}`, expected `{expected}`")
                    )
        self.assertEqual(
            problems,
            [],
            "every role template must emit the case-exact role enumeration "
            f"(CR-MDB-017 §S6a):\n{_fmt(problems)}",
        )

    def test_s6a_each_role_template_emits_cycle_flag(self):
        """Each role template emits `--cycle` (word-boundaried: `--cycles` fails)."""
        problems = []
        for role in _role_names():
            path = _template_path(role)
            if not CYCLE_RE.search(_text(path)):
                anchor = _hits(path, re.compile(r"\$\{register_command\}"))
                lineno = anchor[0][0] if anchor else 1
                problems.append(
                    (_rel(path), lineno,
                     "expected `--cycle <cycleId>` on the register command — not present")
                )
        self.assertEqual(
            problems,
            [],
            "the four TDD role templates must bind the registration to a cycle "
            f"(CR-MDB-017 §S6a):\n{_fmt(problems)}",
        )

    def test_s6a_templates_state_the_cycle_binding_rule_above_the_command(self):
        """The binding rule is stated ABOVE the command the agent will run.

        A rule stated below the fenced command is read after the agent has
        already run it; the server 409s an unbound TDD registration, so the
        prose must precede the command. Requires, strictly above the
        `${register_command}` line: one line binding "cycle" to a
        required/mandatory/must marker, plus a statement of the refusal
        (409 / refused / rejected / unbound).
        """
        problems = []
        for role in _role_names():
            path = _template_path(role)
            numbered = _lines(path)
            anchors = [n for n, line in numbered if "${register_command}" in line]
            if not anchors:
                problems.append((_rel(path), 1, "no ${register_command} line in template"))
                continue
            command_lineno = anchors[0]
            above = [line for n, line in numbered if n < command_lineno]
            binding = any(
                CYCLE_WORD_RE.search(line) and REQUIRED_WORD_RE.search(line)
                for line in above
            )
            refusal = any(REFUSAL_WORD_RE.search(line) for line in above)
            if not binding:
                problems.append(
                    (_rel(path), command_lineno,
                     "no line above the register command states that --cycle is REQUIRED")
                )
            if not refusal:
                problems.append(
                    (_rel(path), command_lineno,
                     "no line above the register command states the 409 refusal of an "
                     "unbound TDD registration")
                )
        self.assertEqual(
            problems,
            [],
            "the cycle-binding rule must be stated above the command the agent runs "
            f"(CR-MDB-017 §S6a):\n{_fmt(problems)}",
        )

    def test_s6a_all_generated_agents_carry_role_and_cycle(self):
        """Every generated definition carries `--role <ROLE>` and `--cycle`."""
        agents = _generated_agents()
        self.assertTrue(agents, "no generated definitions found under generator/agents/")
        problems = []
        for _stack, role, path in agents:
            text = _text(path)
            expected = role.upper()
            if not re.search(r"--role\s+" + expected + r"(?![\w-])", text):
                problems.append((_rel(path), 1, f"missing `--role {expected}`"))
            if not CYCLE_RE.search(text):
                problems.append((_rel(path), 1, "missing `--cycle <cycleId>`"))
        self.assertEqual(
            problems,
            [],
            f"all {len(agents)} generated definitions must carry --role and --cycle "
            f"(CR-MDB-017 §S6a):\n{_fmt(problems)}",
        )

    def test_s6a_generated_agents_are_not_hand_edited(self):
        """`python3 generator/build.py --check` exits 0 — no hand-edit, no drift.

        This is the ONE assertion in the module that shells out. It is
        justified because the CR names this exact command as the drift gate
        ("prove `--check` clean; no generated file is hand-edited"): the
        property under test IS the exit status of that command, so
        re-implementing the render-and-diff in the test would assert a
        second, divergent gate instead of the one the CR specifies.

        Unlike its siblings this gate is GREEN today (the tree is clean at
        b1b013d). It is here as the anti-regression half of §S6a: it trips the
        moment GREEN edits a file under generator/agents/ by hand instead of
        regenerating it from a template or stack edit.
        """
        completed = subprocess.run(
            [sys.executable, "generator/build.py", "--check"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            completed.returncode,
            0,
            "generator/build.py --check reported drift — a generated definition was "
            "hand-edited instead of regenerated (CR-MDB-017 §S6a):\n"
            f"  stdout: {completed.stdout.strip()}\n  stderr: {completed.stderr.strip()}",
        )


class GeneratorRoleContractS6bTest(unittest.TestCase):
    """§S6b — tier guidance is a shared preamble plus a PER-STACK half.

    A single generic tier paragraph is factually wrong for three of the four
    stacks, because the toolchains do not share a tier mechanism. The
    VOCABULARY is fleet-uniform; the HONOURABILITY is not — hence the split.
    """

    def test_s6b_each_stack_toml_declares_its_own_tier_guidance(self):
        """Each generator/stacks/*.toml carries a non-empty `tier_guidance` key."""
        stacks = _stack_names()
        self.assertTrue(stacks, "no stack TOMLs found under generator/stacks/")
        problems = []
        for stack in stacks:
            params = _stack_params(stack)
            value = params.get("tier_guidance")
            if not isinstance(value, str) or not value.strip():
                problems.append(
                    (f"generator/stacks/{stack}.toml", _key_lineno(stack, "tier_guidance"),
                     "missing or empty top-level `tier_guidance` string key")
                )
        self.assertEqual(
            problems,
            [],
            "every stack must carry its own tier guidance as stack DATA, not a generic "
            f"block in the template (CR-MDB-017 §S6b):\n{_fmt(problems)}",
        )

    def test_s6b_each_stacks_tier_guidance_renders_into_all_of_its_agents(self):
        """Each stack's `tier_guidance` text reaches every one of its agents."""
        problems = []
        for stack, _role, path in _generated_agents():
            guidance = _stack_params(stack).get("tier_guidance")
            if not isinstance(guidance, str) or not guidance.strip():
                problems.append(
                    (f"generator/stacks/{stack}.toml", _key_lineno(stack, "tier_guidance"),
                     f"no tier_guidance to render into {path.name}")
                )
                continue
            heading_lineno, section = _tier_section(path)
            if section is None:
                problems.append((_rel(path), 1, "no tier-guidance section in this definition"))
                continue
            if guidance.strip() not in section:
                problems.append(
                    (_rel(path), heading_lineno,
                     f"tier section does not contain {stack}'s own tier_guidance text")
                )
        self.assertEqual(
            problems,
            [],
            "the per-stack half must render verbatim from each stack's tier_guidance key "
            f"(CR-MDB-017 §S6b):\n{_fmt(problems)}",
        )

    def test_s6b_shared_preamble_is_identical_across_stacks(self):
        """The shared preamble renders byte-identically across all stacks.

        Preamble := the rendered tier section with that stack's own
        `tier_guidance` text removed. Compared per role across stacks (only
        newline padding at the region edges is normalised). The section
        HEADING is part of the preamble, so it must not interpolate a
        stack-specific value such as ${display_name}.
        """
        by_role = {}
        problems = []
        for stack, role, path in _generated_agents():
            heading_lineno, section = _tier_section(path)
            if section is None:
                problems.append((_rel(path), 1, "no tier-guidance section in this definition"))
                continue
            guidance = _stack_params(stack).get("tier_guidance")
            if isinstance(guidance, str) and guidance.strip() in section:
                section = section.replace(guidance.strip(), "", 1)
            by_role.setdefault(role, []).append((stack, path, heading_lineno, section.strip()))
        for role, entries in sorted(by_role.items()):
            reference_stack, reference_path, reference_lineno, reference = entries[0]
            for stack, path, lineno, preamble in entries[1:]:
                if preamble != reference:
                    problems.append(
                        (_rel(path), lineno,
                         f"{stack} {role} preamble differs from {reference_stack}'s "
                         f"({_rel(reference_path)}:{reference_lineno})")
                    )
        self.assertEqual(
            problems,
            [],
            "the shared tier preamble renders ONCE from the template and must be identical "
            f"across stacks (CR-MDB-017 §S6b):\n{_fmt(problems)}",
        )

    def test_s6b_preamble_names_the_fleet_uniform_tier_vocabulary(self):
        """The shared preamble names unit/module/integration/e2e/bdd/regression."""
        problems = []
        for stack, _role, path in _generated_agents():
            heading_lineno, section = _tier_section(path)
            if section is None:
                problems.append((_rel(path), 1, "no tier-guidance section in this definition"))
                continue
            guidance = _stack_params(stack).get("tier_guidance")
            if isinstance(guidance, str) and guidance.strip() in section:
                section = section.replace(guidance.strip(), "", 1)
            missing = [
                verb for verb in TIER_VOCABULARY
                if not re.search(r"(?<![\w-])" + re.escape(verb) + r"(?![\w-])", section)
            ]
            if missing:
                problems.append(
                    (_rel(path), heading_lineno,
                     "preamble omits tier verb(s): " + ", ".join(missing))
                )
        self.assertEqual(
            problems,
            [],
            "the preamble states ONE fleet-uniform vocabulary (CR-CRU-111 §S1, "
            f"CR-MDB-017 §S6b):\n{_fmt(problems)}",
        )

    def test_s6b_preamble_does_not_name_a_stack_run_verb_in_place_of_the_vocabulary(self):
        """No stack-specific run verb stands in for the vocabulary in the preamble."""
        problems = []
        for stack, _role, path in _generated_agents():
            heading_lineno, section = _tier_section(path)
            if section is None:
                problems.append((_rel(path), 1, "no tier-guidance section in this definition"))
                continue
            guidance = _stack_params(stack).get("tier_guidance")
            if isinstance(guidance, str) and guidance.strip() in section:
                section = section.replace(guidance.strip(), "", 1)
            for offset, line in enumerate(section.splitlines()):
                for verb in STACK_RUN_VERBS:
                    if verb in line:
                        problems.append(
                            (_rel(path), heading_lineno + offset,
                             f"shared preamble names the stack run verb `{verb}`")
                        )
        self.assertEqual(
            problems,
            [],
            "the SHARED half names tiers, never a stack's run verb — run verbs belong to the "
            f"per-stack half (CR-MDB-017 §S6b):\n{_fmt(problems)}",
        )

    def test_s6b_every_stack_names_the_tiers_it_cannot_honour(self):
        """Every stack's tier_guidance says which tiers it CANNOT honour.

        CR-CRU-111 §S2: a stack silent about an unreachable tier fails. The
        statement must bind a negation to a tier verb on the same line, so a
        generic "cannot" elsewhere in the text does not satisfy it.
        """
        problems = []
        for stack in _stack_names():
            lineno = _key_lineno(stack, "tier_guidance")
            guidance = _stack_params(stack).get("tier_guidance")
            if not isinstance(guidance, str) or not guidance.strip():
                problems.append(
                    (f"generator/stacks/{stack}.toml", lineno,
                     "no tier_guidance, so nothing declares an unreachable tier")
                )
                continue
            declared = any(
                UNREACHABLE_RE.search(line)
                and any(
                    re.search(r"(?<![\w-])" + re.escape(verb) + r"(?![\w-])", line)
                    for verb in TIER_VOCABULARY
                )
                for line in guidance.splitlines()
            )
            if not declared:
                problems.append(
                    (f"generator/stacks/{stack}.toml", lineno,
                     "tier_guidance never names a tier this stack cannot honour")
                )
        self.assertEqual(
            problems,
            [],
            "an unhonourable tier must be declared, not left silent (CR-CRU-111 §S2, "
            f"CR-MDB-017 §S6b):\n{_fmt(problems)}",
        )

    def test_s6b_arduino_names_hil_as_unreachable_from_the_native_host(self):
        """arduino's tier_guidance names HIL as unreachable from the native host."""
        stacks = _stack_names()
        if "arduino" not in stacks:
            self.skipTest("no arduino stack in generator/stacks/")
        lineno = _key_lineno("arduino", "tier_guidance")
        guidance = _stack_params("arduino").get("tier_guidance") or ""
        hil_lines = [line for line in guidance.splitlines() if re.search(r"(?i)\bHIL\b", line)]
        self.assertTrue(
            hil_lines,
            "arduino tier_guidance never mentions HIL — the integration/e2e end it cannot "
            "reach from the native host (CR-MDB-017 §S6b): "
            f"generator/stacks/arduino.toml:{lineno}",
        )
        qualified = [
            line for line in hil_lines
            if UNREACHABLE_RE.search(line) and re.search(r"(?i)\b(native|host)\b", line)
        ]
        self.assertTrue(
            qualified,
            "arduino mentions HIL but does not state it is UNREACHABLE FROM THE NATIVE HOST "
            f"(CR-MDB-017 §S6b): generator/stacks/arduino.toml:{lineno}\n"
            + "\n".join(f"  {line.strip()}" for line in hil_lines),
        )

    def test_s6b_no_stacks_tier_text_is_a_copy_of_anothers(self):
        """Pairwise: no two stacks share the same rendered tier text."""
        stacks = _stack_names()
        texts = {}
        for stack in stacks:
            guidance = _stack_params(stack).get("tier_guidance")
            texts[stack] = guidance.strip() if isinstance(guidance, str) else ""
        problems = []
        for index, left in enumerate(stacks):
            for right in stacks[index + 1:]:
                if texts[left] == texts[right]:
                    detail = "both empty — neither stack has authored one" if not texts[left] \
                        else "identical text — one is a copy of the other"
                    problems.append(
                        (f"generator/stacks/{right}.toml", _key_lineno(right, "tier_guidance"),
                         f"tier_guidance equals {left}'s ({detail})")
                    )
        self.assertEqual(
            problems,
            [],
            "per-stack means per-stack: a generic block copied across stacks is the defect "
            f"§S6b exists to remove (CR-MDB-017 §S6b):\n{_fmt(problems)}",
        )


class GeneratorRoleContractDNTest(unittest.TestCase):
    """Consistency follow-up carried from cycle C2 — NOT a §S6 criterion.

    C2's report flagged that ``docs/research/DN-rationalization-plan-review.md``
    still records a ``vscode-crucible.py`` client as an open ask in its
    "Scripts / AXI wave" section, while PRD §D7 records that request as
    DECLINED (user ruling, Sandesh #1370: a Crucible client targets a LANGUAGE
    STACK, and VS Code is an EDITOR). Two design documents disagreeing about a
    live ask is the same defect class §S4 sweeps for in the bundles, so it is
    gated here rather than left to a future reader to discover.

    The gate is section-scoped and satisfied either by marking the ask declined
    or by removing it — it does not dictate the wording of the fix.
    """

    def test_dn_plan_review_records_the_vscode_client_ask_as_declined(self):
        """The DN's Scripts/AXI-wave vscode-crucible.py ask reads as declined."""
        path = REPO_ROOT / DN_PLAN_REVIEW
        lines = _text(path).splitlines()
        start = None
        level = 0
        end = len(lines)
        for index, line in enumerate(lines):
            match = HEADING_RE.match(line)
            if not match:
                continue
            if start is None:
                if "scripts" in match.group(2).lower() and "axi" in match.group(2).lower():
                    start = index
                    level = len(match.group(1))
                continue
            if len(match.group(1)) <= level:
                end = index
                break
        self.assertIsNotNone(
            start, f"no 'Scripts / AXI wave' section found in {DN_PLAN_REVIEW}"
        )
        if start is None:  # pragma: no cover - assertIsNotNone already failed
            return
        problems = []
        for offset, line in enumerate(lines[start:end]):
            if "vscode-crucible.py" in line and not DECLINED_RE.search(line):
                problems.append((DN_PLAN_REVIEW, start + offset + 1, line))
        self.assertEqual(
            problems,
            [],
            "the DN still records the vscode-crucible.py client as an open ask, "
            "contradicting PRD §D7 which records it DECLINED (Sandesh #1370):\n"
            f"{_fmt(problems)}",
        )


if __name__ == "__main__":
    unittest.main()
