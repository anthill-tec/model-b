"""``scripts/rust-dead-scan.py``: its markdown report's hot-path section, its stated modes and its
``lift-lint`` mode (CR-MDB-078 §S2.5, §S2.6, §S2.7 — AC6, AC7, AC8).

- ``HotPathMarkdownSectionTest`` — AC6: with a ``hot_path_rules.toml`` carrying one violated
  ``forbid`` rule and one unmet ``require_present`` rule, ``dead_scan_report.md`` has a hot-path
  section naming the violation's path and line and the sanity failure's rule id; without the
  file, the section says no rules file was found.
- ``StatedModesTest`` — AC7: the modes the module docstring names as its default are the modes a
  run with no mode argument runs (``main()``'s default ``modes`` list, read from the report's
  ``meta.modes``), and the docstring names ``lift-lint`` as opt-in; the rust memory template lists
  ``hot-path`` among the dead scan's modes.
- ``LiftLintTest`` — AC8: with a ``cargo`` stand-in reporting one ``dead_code`` warning,
  ``lift-lint`` on a project at a path containing a space exits 0 and reports that warning; with
  ``cargo`` absent, and in a repository with no commit, it exits non-zero with an ``error:`` line
  and no ``Traceback``. In all three cases no ``dead-scan-lift-*`` scratch directory remains.

Every tool run is a subprocess of the test interpreter under ``tests/_helpers.py``'s
``run_tool``: the test process's environment with only ``PATH`` and git's configuration
variables changed, a ``PATH`` holding links to ``git`` and ``tar`` alone plus the test's own
stand-ins, a temp directory as the working directory and ``--project-dir`` / ``--out`` pinned to
temp directories (§S4, AC15). The ``cargo`` stand-in logs every call, so each test asserts
whether it ran; the fixture repositories come from ``git_repo`` (§S4.3, AC16).

Stdlib only.
"""

import ast
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from tests._helpers import (
    REPO_ROOT,
    TOOL_SCRIPTS_DIR,
    cargo_member_manifest,
    git_repo,
    run_tool,
    tool_bin_dir,
    write_files,
)

DEAD_SCAN = "rust-dead-scan.py"

#: The rust memory template whose tool list names the dead scan's modes (§S2.6).
RUST_MEMORY_TEMPLATE = REPO_ROOT / "skills-src" / "memory-templates" / "rust-orchestration.md"

#: The prefix of the scratch directory ``lift-lint`` copies the tree into (§S2.7).
SCRATCH_PREFIX = "dead-scan-lift-"


#: A one-member workspace: ``crates/alpha``.
WORKSPACE_ROOT_MANIFEST = '[workspace]\nmembers = ["crates/alpha"]\n'

# ------------------------------------------------------------------ AC6 fixtures ----

#: The member library the hot-path rules scan: ``serde_json::`` on production line 2.
HOT_PATH_LIB = (
    "pub fn decode_frame(bytes: &[u8]) -> u32 {\n"
    "    let parsed: serde_json::Value = serde_json::from_slice(bytes).unwrap();\n"
    "    parsed.as_u64().unwrap_or(0) as u32\n"
    "}\n"
)

#: The path and line of the one ``forbid`` violation in :data:`HOT_PATH_LIB`.
VIOLATION_PATH = "crates/alpha/src/lib.rs"
VIOLATION_LINE = 2

#: The ``forbid`` rule ``HOT_PATH_LIB`` violates, and the ``require_present`` rule it leaves unmet.
FORBID_RULE_ID = "no-json-in-frame-decode"
SANITY_RULE_ID = "frame-decoder-present"

HOT_PATH_RULES = (
    "[[forbid]]\n"
    f'id = "{FORBID_RULE_ID}"\n'
    'paths = ["crates/alpha/src"]\n'
    'patterns = ["serde_json::"]\n'
    'source = "fixture"\n'
    "\n"
    "[[require_present]]\n"
    f'id = "{SANITY_RULE_ID}"\n'
    'paths = ["crates/alpha/src"]\n'
    'pattern = "fn decode_binary_frame"\n'
    'source = "fixture"\n'
)

#: A markdown heading line whose text names the hot path (``hot-path`` / ``hot path``).
HOT_PATH_HEADING_RE = re.compile(r"^#{2,}\s.*\bhot[- ]?path", re.IGNORECASE)


def _hot_path_section(markdown: str) -> list[str]:
    """The lines of the report's hot-path section: its heading line, up to (not including) the
    next heading of the same or a higher level. ``[]`` when the report has no such heading."""
    lines = markdown.splitlines()
    for start, line in enumerate(lines):
        if HOT_PATH_HEADING_RE.match(line):
            level = len(line) - len(line.lstrip("#"))
            section = [line]
            for following in lines[start + 1:]:
                hashes = len(following) - len(following.lstrip("#"))
                if hashes and following[hashes:hashes + 1] == " " and hashes <= level:
                    break
                section.append(following)
            return section
    return []


# ------------------------------------------------------------------ AC8 fixtures ----

#: The member library ``lift-lint`` copies: one ``allow(dead_code)`` it strips, after which the
#: function it decorates sits on line 2.
LIFT_LINT_LIB = "pub fn used() {}\n#[allow(dead_code)]\nfn unused_helper() {}\n"

#: The one ``dead_code`` warning the ``cargo`` stand-in reports, as the report carries it.
DEAD_CODE_WARNING = {
    "path": "crates/alpha/src/lib.rs",
    "line": 2,
    "text": "function `unused_helper` is never used",
}


def _cargo_stand_in(log: Path) -> str:
    """A ``cargo`` stand-in that appends ``{argv, cwd, manifest}`` to ``log`` on every call. Run
    where there is no ``Cargo.toml``, it fails as cargo does (exit 101, no messages); otherwise it
    replays ``cargo check --message-format=json``: an ``unused_variables`` warning, the one
    ``dead_code`` warning of :data:`DEAD_CODE_WARNING`, a ``build-finished`` line, exit 0."""
    messages = [
        {"reason": "compiler-message", "package_id": "alpha 0.1.0",
         "message": {"code": {"code": "unused_variables", "explanation": None},
                     "level": "warning", "message": "unused variable: `frame`",
                     "spans": [{"file_name": "crates/alpha/src/lib.rs", "line_start": 1,
                                "is_primary": True}]}},
        {"reason": "compiler-message", "package_id": "alpha 0.1.0",
         "message": {"code": {"code": "dead_code", "explanation": None},
                     "level": "warning", "message": DEAD_CODE_WARNING["text"],
                     "spans": [{"file_name": DEAD_CODE_WARNING["path"],
                                "line_start": DEAD_CODE_WARNING["line"], "is_primary": True}]}},
        {"reason": "build-finished", "success": True},
    ]
    lines = "\n".join(json.dumps(m) for m in messages)
    return (
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "manifest = os.path.isfile('Cargo.toml')\n"
        f"with open({str(log)!r}, 'a', encoding='utf-8') as fh:\n"
        "    fh.write(json.dumps({'argv': sys.argv[1:], 'cwd': os.getcwd(),"
        " 'manifest': manifest}) + '\\n')\n"
        "if not manifest:\n"
        "    sys.stderr.write('error: could not find `Cargo.toml` in the current directory\\n')\n"
        "    sys.exit(101)\n"
        f"sys.stdout.write({lines!r} + '\\n')\n"
        "sys.exit(0)\n"
    )


def _scratch_dirs() -> set:
    """Every ``dead-scan-lift-*`` entry in the temp directory a tool run inherits (its ``TMPDIR``
    is the test process's — §S4.1)."""
    return set(Path(tempfile.gettempdir()).glob(SCRATCH_PREFIX + "*"))


class _DeadScanCase(unittest.TestCase):
    """A temp work area: a project directory, an output directory and a working directory, all
    removed afterwards (§S4.4). ``bin_dir`` is built per case with the stand-ins it needs."""

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="mdb-rust-dead-scan-"))
        self.addCleanup(shutil.rmtree, self.work, True)
        self.project = self.work / "proj"
        self.out = self.work / "out"
        self.out.mkdir()
        self.cwd = self.work / "cwd"
        self.cwd.mkdir()

    def _assert_no_traceback(self, result):
        self.assertNotIn("Traceback", result.stderr, f"no traceback expected:\n{result.stderr}")
        self.assertNotIn("Traceback", result.stdout, f"no traceback expected:\n{result.stdout}")

    def _report(self) -> dict:
        return json.loads((self.out / "dead_scan_report.json").read_text(encoding="utf-8"))

    def _markdown(self) -> str:
        return (self.out / "dead_scan_report.md").read_text(encoding="utf-8")


class HotPathMarkdownSectionTest(_DeadScanCase):
    """AC6 / §S2.5: the markdown report carries a hot-path section listing each violation and
    sanity failure, and saying when no rules file was found."""

    def setUp(self):
        super().setUp()
        self.bin_dir = tool_bin_dir(self.work / "bin")
        write_files(self.project, {
            "Cargo.toml": WORKSPACE_ROOT_MANIFEST,
            "crates/alpha/Cargo.toml": cargo_member_manifest("alpha"),
            "crates/alpha/src/lib.rs": HOT_PATH_LIB,
        })

    def _scan(self):
        result = run_tool(DEAD_SCAN, "--project-dir", self.project, "--out", self.out,
                          bin_dir=self.bin_dir, cwd=self.cwd)
        self.assertEqual(result.returncode, 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
        self._assert_no_traceback(result)
        return result

    def test_the_markdown_report_has_a_hot_path_section(self):
        write_files(self.out, {"hot_path_rules.toml": HOT_PATH_RULES})
        self._scan()
        section = _hot_path_section(self._markdown())
        self.assertTrue(section, f"AC6: no hot-path heading in the markdown report:\n"
                                 f"{self._markdown()}")

    def test_the_section_names_the_violations_path_and_line(self):
        write_files(self.out, {"hot_path_rules.toml": HOT_PATH_RULES})
        self._scan()
        # The precondition the markdown assertions rest on: the JSON report carries exactly the
        # fixture's one violation and one sanity failure.
        hot_path = self._report()["hot_path"]
        self.assertTrue(hot_path["exists"])
        self.assertEqual([(v["rule"], v["path"], v["line"]) for v in hot_path["violations"]],
                         [(FORBID_RULE_ID, VIOLATION_PATH, VIOLATION_LINE)])
        self.assertEqual([s["rule"] for s in hot_path["sanity_failures"]], [SANITY_RULE_ID])
        section = _hot_path_section(self._markdown())
        line_re = re.compile(rf"(?<![0-9]){VIOLATION_LINE}(?![0-9])")
        naming = [line for line in section[1:]
                  if VIOLATION_PATH in line and line_re.search(line.replace(VIOLATION_PATH, ""))]
        self.assertEqual(len(naming), 1,
                         f"AC6: exactly one line of the hot-path section names "
                         f"{VIOLATION_PATH} and line {VIOLATION_LINE}:\n" + "\n".join(section))

    def test_the_section_names_the_sanity_failures_rule_id(self):
        write_files(self.out, {"hot_path_rules.toml": HOT_PATH_RULES})
        self._scan()
        section = _hot_path_section(self._markdown())
        self.assertTrue(any(SANITY_RULE_ID in line for line in section[1:]),
                        f"AC6: the hot-path section names the sanity failure's rule id "
                        f"{SANITY_RULE_ID}:\n" + "\n".join(section))

    def test_the_section_does_not_say_no_rules_file_when_the_file_exists(self):
        write_files(self.out, {"hot_path_rules.toml": HOT_PATH_RULES})
        self._scan()
        section = _hot_path_section(self._markdown())
        self.assertTrue(section, "AC6: no hot-path heading in the markdown report")
        self.assertNotIn("no rules file", "\n".join(section).lower())

    def test_without_the_rules_file_the_section_says_no_rules_file_was_found(self):
        self._scan()
        self.assertFalse(self._report()["hot_path"]["exists"])
        section = _hot_path_section(self._markdown())
        self.assertTrue(section, f"AC6: no hot-path heading in the markdown report:\n"
                                 f"{self._markdown()}")
        body = "\n".join(section[1:])
        self.assertIn("no rules file", body.lower(),
                      "AC6: without hot_path_rules.toml the section says no rules file was found")
        self.assertNotIn(VIOLATION_PATH, body, "no rules file: the section lists no violation")


class StatedModesTest(_DeadScanCase):
    """AC7 / §S2.6: the docstring's default modes are ``main()``'s, ``lift-lint`` is named as
    opt-in, and the rust memory template lists ``hot-path`` among the modes."""

    @staticmethod
    def _docstring() -> str:
        source = (TOOL_SCRIPTS_DIR / DEAD_SCAN).read_text(encoding="utf-8")
        return ast.get_docstring(ast.parse(source)) or ""

    def _docstring_default_modes(self) -> list[str]:
        match = re.search(r"Modes\s*\(\s*default:\s*([^;)]*)", self._docstring())
        if match is None:
            self.fail("the module docstring states its default modes as 'Modes (default: …'")
        return re.findall(r"[a-z][a-z-]*[a-z]", match.group(1))

    def _main_default_modes(self) -> list[str]:
        """``main()``'s default ``modes``: what a run with no mode argument records as
        ``meta.modes``."""
        bin_dir = tool_bin_dir(self.work / "bin")
        write_files(self.project, {
            "Cargo.toml": WORKSPACE_ROOT_MANIFEST,
            "crates/alpha/Cargo.toml": cargo_member_manifest("alpha"),
            "crates/alpha/src/lib.rs": "pub fn used() {}\n",
        })
        result = run_tool(DEAD_SCAN, "--project-dir", self.project, "--out", self.out,
                          bin_dir=bin_dir, cwd=self.cwd)
        self.assertEqual(result.returncode, 0, f"stderr:\n{result.stderr}")
        self._assert_no_traceback(result)
        return self._report()["meta"]["modes"]

    def test_the_docstrings_default_modes_are_mains_default_modes(self):
        main_modes = self._main_default_modes()
        self.assertCountEqual(self._docstring_default_modes(), main_modes,
                              "AC7: the docstring's default modes equal main()'s default list")
        self.assertRegex(self._docstring(), r"lift-lint[^\n]*opt-in",
                         "AC7: the docstring names lift-lint as opt-in")
        self.assertNotIn("lift-lint", main_modes, "lift-lint is opt-in, never a default")

    def test_the_rust_memory_template_lists_hot_path_among_the_modes(self):
        text = RUST_MEMORY_TEMPLATE.read_text(encoding="utf-8")
        entries = [line for line in text.splitlines()
                   if "rust-dead-scan.py`**" in line and "Modes:" in line]
        self.assertEqual(len(entries), 1,
                         "the template has one rust-dead-scan.py entry listing its modes")
        modes = re.findall(r"· `([a-z-]+)`|Modes: `([a-z-]+)`", entries[0])
        named = {first or second for first, second in modes}
        self.assertIn("inventory", named, "the template's modes are read from its Modes: list")
        self.assertIn("hot-path", named,
                      f"AC7: the rust memory template names hot-path among the modes: {sorted(named)}")


class LiftLintTest(_DeadScanCase):
    """AC8 / §S2.7: ``lift-lint`` copies the tree without a shell, refuses a missing ``cargo``
    and a repository with no commit with an ``error:`` line, and removes its scratch copy on
    every path. Only the first case's project path contains a space, so the other two fail for
    their own cause."""

    WORKSPACE = {
        "Cargo.toml": WORKSPACE_ROOT_MANIFEST,
        "crates/alpha/Cargo.toml": cargo_member_manifest("alpha"),
        "crates/alpha/src/lib.rs": LIFT_LINT_LIB,
    }

    def setUp(self):
        super().setUp()
        self.cargo_log = self.work / "cargo.log"
        self.scratch_before = _scratch_dirs()
        self.addCleanup(self._remove_new_scratch)

    def _remove_new_scratch(self):
        """Remove any scratch copy the run left behind, after the test has asserted on it, so a
        failing run leaves no debris in the temp directory."""
        for leftover in _scratch_dirs() - self.scratch_before:
            shutil.rmtree(leftover, ignore_errors=True)

    def _cargo_calls(self) -> list[dict]:
        if not self.cargo_log.exists():
            return []
        return [json.loads(line)
                for line in self.cargo_log.read_text(encoding="utf-8").splitlines()]

    def _lift_lint(self, bin_dir):
        return run_tool(DEAD_SCAN, "lift-lint", "--project-dir", self.project, "--out", self.out,
                        bin_dir=bin_dir, cwd=self.cwd, timeout=120)

    def _assert_no_new_scratch(self):
        self.assertEqual(_scratch_dirs() - self.scratch_before, set(),
                         f"AC8: no {SCRATCH_PREFIX}* scratch directory remains")

    def _assert_refused(self, result):
        self.assertNotEqual(result.returncode, 0, f"stdout:\n{result.stdout}")
        self._assert_no_traceback(result)
        errors = [line for line in result.stderr.splitlines() if line.startswith("error:")]
        self.assertTrue(errors, f"AC8: a stderr line starting 'error:':\n{result.stderr}")

    def test_a_project_path_with_a_space_reports_the_compilers_dead_code_warning(self):
        self.project = self.work / "my project"
        git_repo(self.project, self.WORKSPACE)
        bin_dir = tool_bin_dir(self.work / "bin", {"cargo": _cargo_stand_in(self.cargo_log)})
        result = self._lift_lint(bin_dir)
        self.assertEqual(result.returncode, 0,
                         f"AC8: exit 0\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")
        self._assert_no_traceback(result)
        calls = self._cargo_calls()
        self.assertEqual(len(calls), 1, f"the cargo stand-in ran once: {calls}")
        self.assertEqual(calls[0]["argv"][0], "check")
        self.assertTrue(calls[0]["manifest"],
                        "cargo check ran in a copy of the tree holding its Cargo.toml")
        lift_lint = self._report()["lift_lint"]
        self.assertEqual(lift_lint["fired"], [DEAD_CODE_WARNING],
                         "AC8: the one dead_code warning, and only it, is reported")
        self.assertTrue(lift_lint["check_ok"])
        self.assertEqual(lift_lint["stripped_attr_lines"], 1)
        self.assertIn(f"{DEAD_CODE_WARNING['path']}:{DEAD_CODE_WARNING['line']}", self._markdown())
        self.assertFalse(Path(calls[0]["cwd"]).exists(),
                         f"AC8: the scratch copy {calls[0]['cwd']} is removed")
        self._assert_no_new_scratch()

    def test_cargo_absent_is_refused_with_an_error_line(self):
        git_repo(self.project, self.WORKSPACE)
        bin_dir = tool_bin_dir(self.work / "bin")
        result = self._lift_lint(bin_dir)
        self._assert_refused(result)
        self.assertEqual(self._cargo_calls(), [], "no cargo stand-in is on PATH")
        self._assert_no_new_scratch()

    def test_a_repository_with_no_commit_is_refused_with_an_error_line(self):
        git_repo(self.project)
        write_files(self.project, self.WORKSPACE)
        bin_dir = tool_bin_dir(self.work / "bin", {"cargo": _cargo_stand_in(self.cargo_log)})
        result = self._lift_lint(bin_dir)
        self._assert_refused(result)
        self.assertEqual(self._cargo_calls(), [],
                         "with no commit to copy, cargo check never runs")
        self._assert_no_new_scratch()


if __name__ == "__main__":
    unittest.main()
