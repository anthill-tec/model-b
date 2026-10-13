"""Skill and agent frontmatter parses, and stays within Pi's limits (CR-MDB-065 §S3).

The file set is every ``skills-src/*/SKILL.md``, ``generator/agents/*.md`` and
``.pi/agents/*.md``. Two halves:

- **§S3.1, the stdlib rule, always run** (``frontmatter_violations``). It reads ``name`` and
  ``description`` only: one top-level line each, holding a one-line plain scalar YAML can read
  only as one string, a ``description`` of at most 1024 UTF-16 code units (the unit Pi counts),
  and a skill ``name`` that follows Pi's name rules and equals its directory. The rule is proved
  on sample text in both directions (``FrontmatterRuleCatchesTest`` /
  ``FrontmatterRulePassesTest``) and then run over the tree (``FrontmatterTreeTest``).
- **§S3.2, Pi's own loader, when it is installed** (``PiSkillLoaderOracleTest``). ``node`` runs
  Pi's exported API (``dist/index.js``) in a child process whose ``HOME`` and
  ``PI_CODING_AGENT_DIR`` are temp dirs that must stay empty: ``loadSkillsFromDir`` over
  ``skills-src/`` reports no diagnostics and one skill per bundle, ``parseFrontmatter`` reads
  every rendered agent to string ``name`` and ``description``, and an unparseable temp
  ``SKILL.md`` is caught on every run. ``_require_pi_api`` SKIPS naming the gap when ``node``,
  ``pi``, Pi's package root or ``dist/index.js`` is absent; ``_run_pi_oracle`` FAILS naming the
  export when ``dist/index.js`` lacks ``loadSkillsFromDir`` or ``parseFrontmatter``. Each case is
  proved by patching (``PiApiEnvironmentDetectionTest``), as ``test_pi_hook_runtime`` does.

The package-root finder is ``_find_pi_package_root`` from ``tests/_helpers.py``, the one copy
``test_pi_hook_runtime`` imports too (``OnePiPackageRootFinderTest``).

Stdlib only. Control and non-BMP characters are built with ``chr()``.
"""

import ast
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests import _helpers
from tests._helpers import _find_pi_package_root

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = REPO_ROOT / "tests"
SKILLS_SRC = REPO_ROOT / "skills-src"
GENERATOR_AGENTS = REPO_ROOT / "generator" / "agents"
PI_AGENTS = REPO_ROOT / ".pi" / "agents"

# ------------------------------------------------------------------ §S3.1 the stdlib rule ----

#: Pi's ``MAX_DESCRIPTION_LENGTH``, counted as JavaScript ``length`` (UTF-16 code units).
MAX_DESCRIPTION_UTF16 = 1024
#: Pi's ``MAX_NAME_LENGTH``.
MAX_NAME_LENGTH = 64
#: A plain scalar must not start with one of these (YAML's indicator characters).
YAML_INDICATORS = frozenset("-?:,[]{}#&*!|>'\"%@`")
#: The indicators that open a quoted or a block scalar: refused with a "reword it" message.
QUOTED_OR_BLOCK = frozenset("'\"|>")
NAME_CHARS_RE = re.compile(r"[a-z0-9-]+")
TOP_LEVEL_KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*:(?: |$)")
#: YAML core-schema null, boolean, integer and float forms, each with an optional sign;
#: matched against the WHOLE value, case-insensitively.
CORE_SCHEMA_SCALAR_RE = re.compile(
    r"[-+]?(?:null|~|true|false"
    r"|[0-9]+|0x[0-9a-f]+|0o[0-7]+"
    r"|(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)(?:e[-+]?[0-9]+)?"
    r"|\.inf|\.nan)",
    re.IGNORECASE,
)


def utf16_length(text: str) -> int:
    """The length Pi measures: UTF-16 code units, so a non-BMP character counts twice."""
    return len(text.encode("utf-16-le")) // 2


def _is_control(char: str) -> bool:
    return ord(char) < 0x20 or ord(char) == 0x7F


def _value_violations(key: str, raw: str, following: str) -> tuple[list, str]:
    """``(problems, value)`` for one ``key:`` line whose text after the colon is ``raw`` and
    whose next frontmatter line is ``following``."""
    problems = []
    if raw and not raw.startswith(" "):
        problems.append(f"{key}: `{key}:` must be followed by a space")
    value = raw.strip(" ")
    if not value:
        problems.append(f"{key} is empty")
    if "\t" in value:
        problems.append(f"{key} contains a tab")
    others = sorted({f"U+{ord(c):04X}" for c in value if _is_control(c) and c != "\t"})
    if others:
        problems.append(f"{key} contains the control character(s) {', '.join(others)}")
    if value and value[0] in QUOTED_OR_BLOCK:
        problems.append(f"{key} is a quoted or block scalar ({value[0]!r}) — reword it as a "
                        "one-line plain scalar")
    elif value and value[0] in YAML_INDICATORS:
        problems.append(f"{key} starts with the YAML indicator {value[0]!r} — reword it")
    if ": " in value:
        problems.append(f"{key} contains `: ` (YAML reads a mapping) — reword it")
    if " #" in value:
        problems.append(f"{key} contains ` #` (YAML reads a comment) — reword it")
    if value.endswith(":"):
        problems.append(f"{key} ends with `:` — reword it")
    if value and CORE_SCHEMA_SCALAR_RE.fullmatch(value):
        problems.append(f"{key} {value!r} reads as a YAML null, boolean or number — reword it")
    if not (following == "---" or following.startswith("#") or TOP_LEVEL_KEY_RE.match(following)):
        problems.append(f"{key} is followed by {following!r}, not a top-level key, a comment or "
                        "the closing `---`: an indented continuation line folds into the value")
    return problems, value


def _name_violations(name: str, skill_dir: str) -> list:
    """Pi's name rules, plus: a skill's ``name`` equals its directory."""
    problems = []
    if len(name) > MAX_NAME_LENGTH:
        problems.append(f"name is {len(name)} characters (Pi's limit is {MAX_NAME_LENGTH})")
    if not NAME_CHARS_RE.fullmatch(name):
        problems.append(f"name {name!r} does not match ^[a-z0-9-]+$")
    if name.startswith("-") or name.endswith("-"):
        problems.append(f"name {name!r} starts or ends with `-`")
    if "--" in name:
        problems.append(f"name {name!r} contains `--`")
    if name != skill_dir:
        problems.append(f"name {name!r} does not equal its directory {skill_dir!r}")
    return problems


def frontmatter_violations(text: str, skill_dir: str | None = None) -> list:
    """Every §S3.1 problem in ``text``'s frontmatter; empty when it is clean. ``skill_dir`` is
    the bundle directory's name for a ``SKILL.md`` (its ``name`` rules apply), ``None`` for an
    agent file."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if lines[0] != "---":
        return ["frontmatter: the file does not open with a `---` line"]
    try:
        close = lines.index("---", 1)
    except ValueError:
        return ["frontmatter: no closing `---` line"]
    block = lines[1:close]
    problems, values = [], {}
    for key in ("name", "description"):
        hits = [i for i, line in enumerate(block) if line.startswith(f"{key}:")]
        if len(hits) != 1:
            problems.append(f"frontmatter: {len(hits)} top-level `{key}:` lines (want exactly 1)")
            continue
        index = hits[0]
        following = block[index + 1] if index + 1 < len(block) else "---"
        found, values[key] = _value_violations(key, block[index][len(key) + 1:], following)
        problems += found
    description = values.get("description", "")
    if utf16_length(description) > MAX_DESCRIPTION_UTF16:
        problems.append(f"description is {utf16_length(description)} UTF-16 code units "
                        f"(Pi's limit is {MAX_DESCRIPTION_UTF16})")
    if skill_dir is not None and "name" in values:
        problems += _name_violations(values["name"], skill_dir)
    return problems


def _doc(name: str = "sample-skill", description: str = "A clean description.",
         extra: str = "") -> str:
    """A sample ``SKILL.md``: ``extra`` lands between the ``description:`` line and ``---``."""
    return f"---\nname: {name}\ndescription: {description}\n{extra}---\n\nBody.\n"


class FrontmatterRuleCatchesTest(unittest.TestCase):
    """§S3.1 — every case the spec lists is caught on sample text."""

    def _assert_caught(self, text, fragment, skill_dir="sample-skill"):
        problems = frontmatter_violations(text, skill_dir)
        self.assertTrue(any(fragment in p for p in problems),
                        f"§S3.1: expected a problem naming {fragment!r} for {text!r}, got {problems}")
        return problems

    def test_each_yaml_indicator_at_the_start_of_a_value_is_caught(self):
        for indicator in sorted(YAML_INDICATORS - QUOTED_OR_BLOCK):
            with self.subTest(indicator=indicator):
                self._assert_caught(_doc(description=f"{indicator}starts the value"),
                                    f"YAML indicator {indicator!r}")

    def test_a_quoted_value_is_refused_with_a_reword_message(self):
        for quote in ("'", '"'):
            with self.subTest(quote=quote):
                problems = self._assert_caught(
                    _doc(description=f"{quote}A quoted description{quote}"), "quoted or block scalar")
                self.assertTrue(any("reword" in p for p in problems if "quoted" in p), problems)

    def test_a_block_scalar_is_refused_with_a_reword_message(self):
        for style in ("|", ">", "|-", ">+"):
            with self.subTest(style=style):
                text = _doc(description=style, extra="  The folded description text.\n")
                problems = self._assert_caught(text, "quoted or block scalar")
                self.assertTrue(any("reword" in p for p in problems if "block" in p), problems)

    def test_colon_space_inside_a_value_is_caught(self):
        self._assert_caught(_doc(description="Authoring conventions. Triggers: CR, PRD"),
                            "contains `: `")

    def test_space_hash_inside_a_value_is_caught(self):
        self._assert_caught(_doc(description="A description #with a comment"), "contains ` #`")

    def test_a_tab_is_caught_including_tab_hash_and_colon_tab(self):
        for value in ("a" + chr(9) + "b", "a" + chr(9) + "# b", "a:" + chr(9) + "b"):
            with self.subTest(value=value):
                self._assert_caught(_doc(description=value), "contains a tab")

    def test_another_control_character_is_caught(self):
        for code in (0x00, 0x01, 0x0B, 0x1B, 0x1F, 0x7F):
            with self.subTest(code=hex(code)):
                self._assert_caught(_doc(description=f"before{chr(code)}after"), f"U+{code:04X}")

    def test_a_trailing_colon_is_caught(self):
        self._assert_caught(_doc(description="Use this skill for:"), "ends with `:`")

    def test_each_null_boolean_and_number_form_is_caught_with_sign_and_case_variants(self):
        forms = (
            "null", "Null", "NULL", "~", "+null", "+~",
            "true", "True", "TRUE", "false", "False", "FALSE", "+true", "+False",
            "0", "42", "+42", "-42",
            "0x1f", "0X1F", "+0x1F", "-0x1f",
            "0o17", "0O17", "+0o17", "-0o17",
            "1.5", "1.", ".5", "+1.5", "-.5",
            "1e5", "1E5", "1.5e-3", "-1.5E+3", "+.5e2",
            ".inf", ".Inf", ".INF", "+.inf", "-.inf",
            ".nan", ".NaN", ".NAN",
        )
        for value in forms:
            with self.subTest(value=value):
                self._assert_caught(_doc(description=value), "reads as a YAML null, boolean or number")

    def test_a_name_that_reads_as_a_number_is_caught_too(self):
        self._assert_caught(_doc(name="123"), "reads as a YAML null, boolean or number",
                            skill_dir="123")

    def test_an_indented_continuation_line_is_caught(self):
        self._assert_caught(_doc(description="A description that", extra="  continues here.\n"),
                            "continuation line")
        self._assert_caught("---\nname: sample-skill\n  more name\ndescription: Clean.\n---\n",
                            "continuation line")

    def test_an_empty_value_is_caught(self):
        self._assert_caught(_doc(description=""), "description is empty")

    def test_a_description_of_1025_code_units_is_caught(self):
        problems = self._assert_caught(_doc(description="x" * 1025), "1025 UTF-16 code units")
        self.assertEqual(len([p for p in problems if "UTF-16" in p]), 1, problems)

    def test_a_non_bmp_description_python_counts_as_1024_is_caught_at_1025_code_units(self):
        value = "x" * 1023 + chr(0x1F600)
        self.assertEqual(len(value), 1024, "precondition: Python's len is within the limit")
        self._assert_caught(_doc(description=value), "1025 UTF-16 code units")

    def test_a_name_longer_than_64_characters_is_caught(self):
        name = "a" * 65
        self._assert_caught(_doc(name=name), "65 characters", skill_dir=name)

    def test_a_name_outside_lowercase_digits_and_hyphen_is_caught(self):
        for name in ("Sample-Skill", "sample_skill", "sample.skill"):
            with self.subTest(name=name):
                self._assert_caught(_doc(name=name), "does not match ^[a-z0-9-]+$", skill_dir=name)

    def test_a_name_with_a_leading_or_trailing_hyphen_is_caught(self):
        for name in ("-sample-skill", "sample-skill-"):
            with self.subTest(name=name):
                self._assert_caught(_doc(name=name), "starts or ends with `-`", skill_dir=name)

    def test_a_name_with_a_double_hyphen_is_caught(self):
        self._assert_caught(_doc(name="sample--skill"), "contains `--`", skill_dir="sample--skill")

    def test_a_name_unequal_to_its_directory_is_caught(self):
        self._assert_caught(_doc(name="other-skill"), "does not equal its directory 'sample-skill'")

    def test_frontmatter_that_is_not_well_formed_is_caught(self):
        cases = (
            ("name: sample-skill\ndescription: Clean.\n", "does not open with a `---` line"),
            ("---\nname: sample-skill\ndescription: Clean.\n", "no closing `---` line"),
            ("---\nname: sample-skill\nname: sample-skill\ndescription: Clean.\n---\n",
             "2 top-level `name:` lines"),
            ("---\nname: sample-skill\n---\n", "0 top-level `description:` lines"),
        )
        for text, fragment in cases:
            with self.subTest(fragment=fragment):
                self._assert_caught(text, fragment)


#: Clean samples: each is a one-line plain scalar YAML reads as exactly this string, including
#: indicators, ``:`` and ``#`` where YAML does not treat them as such. ``PiSkillLoaderOracleTest``
#: re-reads every one through Pi's ``parseFrontmatter`` when Pi is installed.
CLEAN_DESCRIPTIONS = (
    "A clean description.",
    "Ratios like 3:4, C# names and a-b-c stay plain - ? , [ ] { } & * ! | > ' \" % @ ` all mid-value.",
    "nullable, trueish, 0x, 1.2.3, v1.0 and an infinite .inf mention are strings.",
    "x" * MAX_DESCRIPTION_UTF16,
    "x" * (MAX_DESCRIPTION_UTF16 - 2) + chr(0x1F600),
)


class FrontmatterRulePassesTest(unittest.TestCase):
    """§S3.1 — a clean value, and a description of exactly 1024 code units, pass."""

    def test_clean_values_pass(self):
        for description in CLEAN_DESCRIPTIONS:
            with self.subTest(description=description[:40]):
                self.assertEqual(frontmatter_violations(_doc(description=description), "sample-skill"), [])

    def test_a_description_of_exactly_1024_code_units_passes(self):
        for value in ("x" * 1024, "x" * 1022 + chr(0x1F600)):
            with self.subTest(python_len=len(value)):
                self.assertEqual(utf16_length(value), 1024)
                self.assertEqual(frontmatter_violations(_doc(description=value), "sample-skill"), [])

    def test_a_64_character_name_equal_to_its_directory_passes(self):
        name = "a" * 32 + "-" + "b" * 31
        self.assertEqual(len(name), 64)
        self.assertEqual(frontmatter_violations(_doc(name=name), name), [])

    def test_a_comment_line_or_a_further_key_may_follow_a_value(self):
        text = ("---\n# generated by a renderer\nname: sample-agent\n# a comment\n"
                "description: Clean.\ntools: read, write\npermission:\n  read: allow\n---\n")
        self.assertEqual(frontmatter_violations(text), [])

    def test_agent_files_are_not_held_to_the_skill_name_rules(self):
        self.assertEqual(frontmatter_violations(_doc(name="Some_Agent"), None), [])


def _skill_files() -> list:
    return sorted(SKILLS_SRC.glob("*/SKILL.md"))


def _agent_files() -> list:
    return sorted(GENERATOR_AGENTS.glob("*.md")) + sorted(PI_AGENTS.glob("*.md"))


class FrontmatterTreeTest(unittest.TestCase):
    """§S3.1 — the rule passes on every file of §S3's set."""

    maxDiff = None

    def _scan(self, files, skill):
        self.assertNotEqual(files, [], "§S3: the file set must not be empty")
        found = {}
        for path in files:
            problems = frontmatter_violations(path.read_text(encoding="utf-8"),
                                              path.parent.name if skill else None)
            if problems:
                found[path.relative_to(REPO_ROOT).as_posix()] = problems
        return found

    def test_every_skill_source_frontmatter_passes_the_rule(self):
        found = self._scan(_skill_files(), skill=True)
        self.assertEqual(found, {}, "§S3.1: skill frontmatter Pi would refuse or warn on:\n"
                         + "\n".join(f"  {f}: {p}" for f, ps in found.items() for p in ps))

    def test_every_rendered_generator_agent_frontmatter_passes_the_rule(self):
        found = self._scan(sorted(GENERATOR_AGENTS.glob("*.md")), skill=False)
        self.assertEqual(found, {}, f"§S3.1: rendered agent frontmatter problems: {found}")

    def test_every_project_pi_agent_frontmatter_passes_the_rule(self):
        found = self._scan(sorted(PI_AGENTS.glob("*.md")), skill=False)
        self.assertEqual(found, {}, f"§S3.1: .pi/agents frontmatter problems: {found}")


# ------------------------------------------------------------------ §S3.2 Pi's own loader ----

_ORACLE_BUDGET_S = 30.0

#: Run by ``node --input-type=module``; reads its request as JSON on stdin and writes one JSON
#: object to stdout. It checks the two exports first and does nothing else when one is missing.
ORACLE_MJS = """
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const request = JSON.parse(readFileSync(0, "utf8"));
const api = await import(pathToFileURL(request.index).href);
const missing = ["loadSkillsFromDir", "parseFrontmatter"].filter((n) => typeof api[n] !== "function");
const out = { missing_exports: missing };
if (missing.length === 0) {
  if (request.skills_dir) {
    const { skills, diagnostics } = api.loadSkillsFromDir({ dir: request.skills_dir, source: "path" });
    out.skills = skills.map((s) => ({ name: s.name, filePath: s.filePath }));
    out.diagnostics = diagnostics.map((d) => ({ type: d.type, message: d.message, path: d.path }));
  }
  const parse = (content) => {
    try {
      const { frontmatter } = api.parseFrontmatter(content);
      return {
        threw: null,
        name: frontmatter.name ?? null,
        description: frontmatter.description ?? null,
        nameType: typeof frontmatter.name,
        descriptionType: typeof frontmatter.description,
      };
    } catch (error) {
      return { threw: String(error && error.message ? error.message : error) };
    }
  };
  out.agents = (request.agents ?? []).map((path) => ({ path, ...parse(readFileSync(path, "utf8")) }));
  out.documents = (request.documents ?? []).map((content) => parse(content));
}
process.stdout.write(JSON.stringify(out));
"""


def _require_pi_api() -> dict:
    """Resolve ``node``, ``pi``, Pi's package root and its ``dist/index.js``, or raise
    ``unittest.SkipTest`` naming exactly what is missing (CR-MDB-065 §S3.2)."""
    node_bin = shutil.which("node")
    if node_bin is None:
        raise unittest.SkipTest("Pi skill-loader check: node is not installed (no `node` on PATH)")
    pi_bin = shutil.which("pi")
    if pi_bin is None:
        raise unittest.SkipTest("Pi skill-loader check: pi is not installed (no `pi` on PATH)")
    pi_resolved = Path(pi_bin).resolve()
    pi_pkg_root = _find_pi_package_root(pi_resolved)
    if pi_pkg_root is None:
        raise unittest.SkipTest("Pi skill-loader check: no Pi package root (no "
                                "dist/core/extensions/loader.js) above the resolved `pi` binary "
                                f"({pi_resolved})")
    index_js = pi_pkg_root / "dist" / "index.js"
    if not index_js.is_file():
        raise unittest.SkipTest(f"Pi skill-loader check: Pi package root {pi_pkg_root} has no "
                                "dist/index.js")
    return {"node_bin": node_bin, "pi_pkg_root": pi_pkg_root, "index_js": index_js}


def _run_pi_oracle(testcase: unittest.TestCase, api: dict, request: dict) -> dict:
    """Run ``ORACLE_MJS`` on ``api["index_js"]`` with temp ``HOME`` and ``PI_CODING_AGENT_DIR``
    (also its cwd), assert both stay empty, and return the parsed result. Fails the test naming
    the export when one is missing — a contract break, not an absent tool."""
    with (tempfile.TemporaryDirectory(prefix="modelb-pi-oracle-home-") as home,
          tempfile.TemporaryDirectory(prefix="modelb-pi-oracle-agent-") as agent_dir):
        env = dict(os.environ, HOME=home, PI_CODING_AGENT_DIR=agent_dir)
        try:
            result = subprocess.run(
                [api["node_bin"], "--input-type=module", "-e", ORACLE_MJS],
                input=json.dumps(dict(request, index=str(api["index_js"]))),
                capture_output=True, text=True, timeout=_ORACLE_BUDGET_S, env=env, cwd=home,
            )
        except subprocess.TimeoutExpired as exc:
            testcase.fail(f"§S3.2: the Pi loader child did not exit within {_ORACLE_BUDGET_S}s: {exc}")
        testcase.assertEqual(sorted(os.listdir(home)), [],
                             "§S3.2: the Pi loader child wrote under its temp HOME")
        testcase.assertEqual(sorted(os.listdir(agent_dir)), [],
                             "§S3.2: the Pi loader child wrote under its temp PI_CODING_AGENT_DIR")
    if result.returncode != 0:
        testcase.fail(f"§S3.2: the Pi loader child exited {result.returncode}: "
                      f"stderr={result.stderr!r}")
    try:
        out = json.loads(result.stdout)
    except json.JSONDecodeError:
        testcase.fail(f"§S3.2: the Pi loader child printed no JSON: stdout={result.stdout!r} "
                      f"stderr={result.stderr!r}")
    if out["missing_exports"]:
        testcase.fail(f"§S3.2: {api['index_js']} does not export "
                      f"{', '.join(out['missing_exports'])} — Pi's skill-loader contract is broken")
    return out


class PiApiEnvironmentDetectionTest(unittest.TestCase):
    """§S3.2 — the check SKIPS naming the gap for each absent piece, and FAILS naming the export
    when one is missing; each case proved by patching, on every machine."""

    FAKE_PI = "/usr/bin/pi"

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="modelb-pi-api-detect-"))

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_missing_node_skips_naming_node(self):
        with (mock.patch("shutil.which", return_value=None),
              mock.patch(f"{__name__}._find_pi_package_root") as finder,
              self.assertRaises(unittest.SkipTest) as ctx):
            _require_pi_api()
        self.assertIn("node is not installed", str(ctx.exception))
        finder.assert_not_called()

    def test_missing_pi_skips_naming_pi(self):
        def fake_which(name):
            return "/usr/bin/node" if name == "node" else None

        with (mock.patch("shutil.which", side_effect=fake_which),
              mock.patch(f"{__name__}._find_pi_package_root") as finder,
              self.assertRaises(unittest.SkipTest) as ctx):
            _require_pi_api()
        self.assertIn("pi is not installed", str(ctx.exception))
        finder.assert_not_called()

    def test_missing_pi_package_root_skips_naming_the_package_root(self):
        with (mock.patch("shutil.which", side_effect=lambda name: f"/usr/bin/{name}"),
              mock.patch(f"{__name__}._find_pi_package_root", return_value=None) as finder,
              self.assertRaises(unittest.SkipTest) as ctx):
            _require_pi_api()
        self.assertIn("no Pi package root", str(ctx.exception))
        finder.assert_called_once_with(Path(self.FAKE_PI).resolve())

    def test_missing_dist_index_js_skips_naming_dist_index_js(self):
        with (mock.patch("shutil.which", side_effect=lambda name: f"/usr/bin/{name}"),
              mock.patch(f"{__name__}._find_pi_package_root", return_value=self._tmp) as finder,
              self.assertRaises(unittest.SkipTest) as ctx):
            _require_pi_api()
        self.assertIn("dist/index.js", str(ctx.exception))
        self.assertIn(str(self._tmp), str(ctx.exception))
        finder.assert_called_once_with(Path(self.FAKE_PI).resolve())

    def _fake_root_exporting(self, source: str) -> Path:
        root = self._tmp / "fake-pi-coding-agent"
        (root / "dist").mkdir(parents=True)
        (root / "package.json").write_text('{"type": "module"}\n', encoding="utf-8")
        (root / "dist" / "index.js").write_text(source, encoding="utf-8")
        return root

    def _api_for(self, root: Path) -> dict:
        node_bin = shutil.which("node")
        if node_bin is None:
            self.skipTest("Pi skill-loader check: node is not installed (no `node` on PATH) — "
                          "the missing-export proof needs a real node")

        def fake_which(name):
            return node_bin if name == "node" else self.FAKE_PI

        with (mock.patch("shutil.which", side_effect=fake_which),
              mock.patch(f"{__name__}._find_pi_package_root", return_value=root) as finder):
            api = _require_pi_api()
        finder.assert_called_once_with(Path(self.FAKE_PI).resolve())
        self.assertEqual(api["index_js"], root / "dist" / "index.js")
        return api

    def test_missing_load_skills_from_dir_export_fails_naming_it(self):
        root = self._fake_root_exporting(
            "export const parseFrontmatter = () => ({ frontmatter: {}, body: '' });\n")
        api = self._api_for(root)
        with self.assertRaises(AssertionError) as ctx:
            _run_pi_oracle(self, api, {"skills_dir": str(self._tmp)})
        message = str(ctx.exception)
        self.assertIn("does not export loadSkillsFromDir", message)
        self.assertNotIn("parseFrontmatter", message)

    def test_missing_parse_frontmatter_export_fails_naming_it(self):
        root = self._fake_root_exporting(
            "export const loadSkillsFromDir = () => ({ skills: [], diagnostics: [] });\n")
        api = self._api_for(root)
        with self.assertRaises(AssertionError) as ctx:
            _run_pi_oracle(self, api, {"skills_dir": str(self._tmp)})
        message = str(ctx.exception)
        self.assertIn("does not export parseFrontmatter", message)
        self.assertNotIn("loadSkillsFromDir", message)


class PiSkillLoaderOracleTest(unittest.TestCase):
    """§S3.2 — Pi's own exported loader agrees the tree is clean, and still catches a defect."""

    maxDiff = None

    @classmethod
    def setUpClass(cls):
        cls.api = _require_pi_api()

    def test_pi_loads_skills_src_with_no_diagnostics(self):
        out = _run_pi_oracle(self, self.api, {"skills_dir": str(SKILLS_SRC)})
        self.assertEqual(out["diagnostics"], [],
                         "§S3.2: Pi's loadSkillsFromDir reports diagnostics over skills-src/")

    def test_pi_loads_exactly_one_skill_per_bundle_named_as_its_directory(self):
        out = _run_pi_oracle(self, self.api, {"skills_dir": str(SKILLS_SRC)})
        expected = sorted(str(p) for p in _skill_files())
        self.assertEqual(sorted(s["filePath"] for s in out["skills"]), expected,
                         "§S3.2: Pi must load exactly one skill per skills-src/*/SKILL.md")
        self.assertEqual(len(out["skills"]), len(expected))
        for skill in out["skills"]:
            with self.subTest(skill=skill["filePath"]):
                self.assertEqual(skill["name"], Path(skill["filePath"]).parent.name)

    def test_pi_parses_every_rendered_agent_to_string_name_and_description(self):
        agents = [str(p) for p in _agent_files()]
        self.assertNotEqual(agents, [])
        out = _run_pi_oracle(self, self.api, {"agents": agents})
        self.assertEqual([a["path"] for a in out["agents"]], agents)
        for agent in out["agents"]:
            with self.subTest(agent=agent["path"]):
                self.assertIsNone(agent["threw"], f"§S3.2: parseFrontmatter threw on {agent['path']}")
                self.assertEqual((agent["nameType"], agent["descriptionType"]), ("string", "string"))
                self.assertEqual(agent["name"], Path(agent["path"]).stem)

    def test_pi_catches_an_unparseable_skill_on_every_run(self):
        with tempfile.TemporaryDirectory(prefix="modelb-pi-broken-skill-") as tmp:
            skill_md = Path(tmp) / "broken-skill" / "SKILL.md"
            skill_md.parent.mkdir()
            skill_md.write_text(
                "---\nname: broken-skill\n"
                "description: Authoring conventions. Triggers: CR, PRD\n---\n\nBody.\n",
                encoding="utf-8")
            out = _run_pi_oracle(self, self.api, {"skills_dir": tmp})
        self.assertEqual(out["skills"], [], "§S3.2: an unparseable SKILL.md must load no skill")
        self.assertEqual(len(out["diagnostics"]), 1, out["diagnostics"])
        self.assertEqual(out["diagnostics"][0]["path"], str(skill_md))

    def test_pi_reads_each_clean_sample_as_exactly_its_text(self):
        out = _run_pi_oracle(self, self.api,
                             {"documents": [_doc(description=d) for d in CLEAN_DESCRIPTIONS]})
        for description, parsed in zip(CLEAN_DESCRIPTIONS, out["documents"], strict=True):
            with self.subTest(description=description[:40]):
                self.assertIsNone(parsed["threw"])
                self.assertEqual((parsed["name"], parsed["description"]),
                                 ("sample-skill", description))


# ------------------------------------------------------------------ one finder ----

class OnePiPackageRootFinderTest(unittest.TestCase):
    """§S3.2 / §S4 — ``_find_pi_package_root`` is defined once, in ``tests/_helpers.py``, and both
    modules use that one."""

    def test_the_finder_is_defined_only_in_the_helpers_module(self):
        owners = []
        for path in sorted(TESTS_DIR.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            if any(isinstance(node, ast.FunctionDef) and node.name == "_find_pi_package_root"
                   for node in ast.walk(tree)):
                owners.append(path.name)
        self.assertEqual(owners, ["_helpers.py"])

    def test_both_modules_bind_the_helpers_finder(self):
        from tests import test_pi_hook_runtime

        self.assertIs(test_pi_hook_runtime._find_pi_package_root, _helpers._find_pi_package_root)
        self.assertIs(_find_pi_package_root, _helpers._find_pi_package_root)

    def test_the_finder_returns_the_ancestor_holding_the_extension_loader(self):
        with tempfile.TemporaryDirectory(prefix="modelb-pi-finder-") as tmp:
            root = Path(tmp) / "pi-coding-agent"
            (root / "dist" / "core" / "extensions").mkdir(parents=True)
            (root / "dist" / "core" / "extensions" / "loader.js").write_text("", encoding="utf-8")
            binary = root / "dist" / "bundle" / "cli.js"
            self.assertEqual(_find_pi_package_root(binary), root)
            self.assertIsNone(_find_pi_package_root(Path(tmp) / "elsewhere" / "bin" / "pi"))


if __name__ == "__main__":
    unittest.main()
