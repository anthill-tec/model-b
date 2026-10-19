"""``scripts/rust-dead-scan.py``: its modes, its report, its stated modes and its ``lift-lint``
mode (CR-MDB-078 §S2.1–§S2.3, §S2.5, §S2.6, §S2.7 — AC5, AC6, AC7, AC8).

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
- AC5 — each §S2.1 mode's cases, asserted on ``dead_scan_report.json``: ``InventoryModeTest``,
  ``PubScanModeTest``, ``DepsModeTest`` (with a ``cargo-machete`` stand-in replaying the real
  tool's output shape, §S4.2, and with it absent), ``ReconcileModeTest``,
  ``BoundariesModeTest``, ``HotPathModeTest`` (the JSON side) and ``LiftLintCollectionTest``
  (stripping, collection and ``check_ok``); ``ModeSelectionTest`` (§S2.2) and
  ``StableFindingIdsTest`` (§S2.3).

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


# ============================================================ AC5 — the modes (§S2.1–§S2.3) ====

#: ``fid``'s documented shape: ``DS-`` and ten lowercase hex digits (the module docstring).
FINDING_ID_RE = re.compile(r"^DS-[0-9a-f]{10}$")

#: The default modes ``main()`` runs, in its order (§S2.2).
DEFAULT_MODES = ["inventory", "pub-scan", "deps", "reconcile", "boundaries", "hot-path"]

#: The report key each mode writes.
MODE_KEYS = {"inventory": "inventory", "pub-scan": "pub_scan", "deps": "deps",
             "reconcile": "reconcile", "boundaries": "boundaries", "hot-path": "hot_path",
             "lift-lint": "lift_lint"}


def _section_keys(report: dict) -> set:
    """The report's mode sections: every top-level key but ``meta``."""
    return set(report) - {"meta"}


class _ModeCase(_DeadScanCase):
    """A dead-scan run over a synthetic workspace with no stand-in on ``PATH`` unless a test
    names one: ``cargo``, ``cargo-machete`` and ``dot`` absent, ``git`` and ``tar`` linked
    (§S4.2)."""

    def _bin(self, stand_ins=None) -> Path:
        bin_dir = self.work / "bin"
        if not bin_dir.exists():
            tool_bin_dir(bin_dir, stand_ins)
        return bin_dir

    def _scan(self, *args, stand_ins=None, out=None) -> dict:
        """Run the dead scan with ``args`` (modes and flags), assert a clean exit, and return
        the JSON report it wrote."""
        out = self.out if out is None else out
        out.mkdir(parents=True, exist_ok=True)
        result = run_tool(DEAD_SCAN, *args, "--project-dir", self.project, "--out", out,
                          bin_dir=self._bin(stand_ins), cwd=self.cwd)
        self.assertEqual(result.returncode, 0,
                         f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
        self._assert_no_traceback(result)
        return json.loads((out / "dead_scan_report.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ inventory ----

#: A library with one site of every kind the inventory records, line by line.
INVENTORY_LIB = (
    "// #[allow(dead_code)] in a comment is prose, not a site\n"         # 1
    '#[allow(dead_code, reason = "admin endpoint for diagnostics")]\n'  # 2
    "pub fn admin_probe() {}\n"                                         # 3
    '#[expect(dead_code, reason = "held for the v2 parity check")]\n'   # 4
    "struct Holder {\n"                                                 # 5
    "    #[allow(dead_code)]\n"                                         # 6
    "    spare: u32,\n"                                                 # 7
    "}\n"                                                               # 8
    "enum Mode {\n"                                                     # 9
    "    #[allow(dead_code)]\n"                                         # 10
    "    Legacy,\n"                                                     # 11
    "}\n"                                                               # 12
    '#[deprecated(note = "use admin_probe")]\n'                         # 13
    "pub fn old_probe() {}\n"                                           # 14
    "#[cfg(test)]\n"                                                    # 15
    "mod tests {\n"                                                     # 16
    "    #[allow(dead_code)]\n"                                         # 17
    "    fn fixture_helper() {}\n"                                      # 18
    "}\n"                                                               # 19
)

#: An integration-test file: its site is in the ``tests-dir`` context.
INVENTORY_TESTS_FILE = "#[allow(dead_code)]\nfn shared_setup() {}\n"

#: Every site of :data:`INVENTORY_LIB` and :data:`INVENTORY_TESTS_FILE`, in scan order:
#: ``(attr, crate, path, line, item, context, reason, class)``.
INVENTORY_EXPECTED = [
    ("allow", "alpha", "src/lib.rs", 2, "fn admin_probe", "src-prod",
     "admin endpoint for diagnostics", "observability"),
    ("expect", "alpha", "src/lib.rs", 4, "struct Holder", "src-prod",
     "held for the v2 parity check", "parity-held"),
    ("allow", "alpha", "src/lib.rs", 6, "field spare", "src-prod", "", "unclassified"),
    ("allow", "alpha", "src/lib.rs", 10, "variant Legacy", "src-prod", "", "unclassified"),
    ("deprecated", "alpha", "src/lib.rs", 13, "fn old_probe", "src-prod",
     "use admin_probe", "deprecated"),
    ("allow", "alpha", "src/lib.rs", 17, "fn fixture_helper", "src-testgated", "",
     "unclassified"),
    ("allow", "alpha", "tests/it.rs", 1, "fn shared_setup", "tests-dir", "", "unclassified"),
]


class InventoryModeTest(_ModeCase):
    """§S2.1 ``inventory``: the ``allow``/``expect(dead_code)`` and ``deprecated`` sites, their
    reason clause and class bucket, their context, comment lines skipped, the decorated item
    named as fn/struct/…, field or variant."""

    def setUp(self):
        super().setUp()
        write_files(self.project, {
            "Cargo.toml": WORKSPACE_ROOT_MANIFEST,
            "crates/alpha/Cargo.toml": cargo_member_manifest("alpha"),
            "crates/alpha/src/lib.rs": INVENTORY_LIB,
            "crates/alpha/tests/it.rs": INVENTORY_TESTS_FILE,
        })

    @staticmethod
    def _projection(inventory):
        return [(f["attr"], f["crate"], f["path"], f["line"], f["item"], f["context"],
                 f["reason"], f["class"]) for f in inventory]

    def test_every_site_is_listed_with_its_item_context_reason_and_class(self):
        inventory = self._scan("inventory")["inventory"]
        self.assertEqual(self._projection(inventory), INVENTORY_EXPECTED)

    def test_an_attribute_inside_a_comment_is_not_a_site(self):
        inventory = self._scan("inventory")["inventory"]
        self.assertNotIn(1, [f["line"] for f in inventory if f["path"] == "src/lib.rs"],
                         "line 1 is a comment: its attribute text is prose")
        self.assertEqual(len(inventory), len(INVENTORY_EXPECTED))

    def test_each_site_carries_a_distinct_finding_id(self):
        inventory = self._scan("inventory")["inventory"]
        ids = [f["id"] for f in inventory]
        for fid_ in ids:
            self.assertRegex(fid_, FINDING_ID_RE)
        self.assertEqual(len(set(ids)), len(INVENTORY_EXPECTED), f"distinct ids: {ids}")

    def test_a_member_with_no_sites_yields_an_empty_inventory(self):
        write_files(self.project, {"crates/alpha/src/lib.rs": "pub fn used() {}\n",
                                   "crates/alpha/tests/it.rs": "fn check() {}\n"})
        report = self._scan("inventory")
        self.assertEqual(report["inventory"], [])
        self.assertEqual(report["meta"]["members"], 1)


# ------------------------------------------------------------------ pub-scan ----

#: ``alpha``'s library: a dead-pub item, a test-coat item, an internal-only item, an item a
#: sibling crate uses, a common and a short name, a name ``beta`` also defines, and an item only
#: a doc comment names.
PUB_SCAN_ALPHA_LIB = (
    "pub fn orphan_widget() {}\n"                                       # 1  dead-pub
    "pub fn tested_gadget() {}\n"                                       # 2  test-coat
    "pub fn local_helper() {}\n"                                        # 3  internal-only
    "pub fn shared_service() {}\n"                                      # 4  cleared (beta)
    "pub fn new() {}\n"                                                 # 5  common: skipped
    "pub fn abc() {}\n"                                                 # 6  short: skipped
    "pub struct Collide;\n"                                             # 7  collision
    "/// Callers reach documented_thing through the docs only.\n"       # 8  doc ref
    "pub fn documented_thing() {}\n"                                    # 9  dead-pub, doc 1
    "fn caller() { local_helper(); }\n"                                 # 10
    "#[cfg(test)]\n"                                                    # 11
    "mod tests {\n"                                                     # 12
    "    fn check() { super::tested_gadget(); }\n"                      # 13 test ref
    "}\n"                                                               # 14
)

PUB_SCAN_ALPHA_TESTS = "fn exercises() { alpha::tested_gadget(); }\n"

PUB_SCAN_BETA_LIB = (
    "pub struct Collide;\n"
    "fn beta_entry() { alpha::shared_service(); }\n"
)

#: The candidates, in the report's order (tier, then crate and path, then name):
#: ``(tier, name, crate, path, line, kind, prod_own, prod_cross, test, doc)``.
PUB_SCAN_EXPECTED = [
    ("dead-pub", "documented_thing", "alpha", "src/lib.rs", 9, "fn", 0, 0, 0, 1),
    ("dead-pub", "orphan_widget", "alpha", "src/lib.rs", 1, "fn", 0, 0, 0, 0),
    ("test-coat", "tested_gadget", "alpha", "src/lib.rs", 2, "fn", 0, 0, 2, 0),
    ("internal-only", "local_helper", "alpha", "src/lib.rs", 3, "fn", 1, 0, 0, 0),
]


class PubScanModeTest(_ModeCase):
    """§S2.1 ``pub-scan``: the ``dead-pub``, ``test-coat`` and ``internal-only`` tiers; a
    cross-crate reference clearing a candidate; name collisions listed, never flagged; common and
    short names skipped and counted; doc-comment references counted apart."""

    def setUp(self):
        super().setUp()
        write_files(self.project, {
            "Cargo.toml": '[workspace]\nmembers = ["crates/alpha", "crates/beta"]\n',
            "crates/alpha/Cargo.toml": cargo_member_manifest("alpha"),
            "crates/alpha/src/lib.rs": PUB_SCAN_ALPHA_LIB,
            "crates/alpha/tests/it.rs": PUB_SCAN_ALPHA_TESTS,
            "crates/beta/Cargo.toml": cargo_member_manifest("beta"),
            "crates/beta/src/lib.rs": PUB_SCAN_BETA_LIB,
        })

    def test_the_candidates_are_tiered_with_their_reference_counts(self):
        pub_scan = self._scan("pub-scan")["pub_scan"]
        got = [(c["tier"], c["name"], c["crate"], c["path"], c["line"], c["kind"],
                c["prod_own"], c["prod_cross"], c["test"], c["doc"])
               for c in pub_scan["candidates"]]
        self.assertEqual(got, PUB_SCAN_EXPECTED)
        for candidate in pub_scan["candidates"]:
            self.assertRegex(candidate["id"], FINDING_ID_RE)

    def test_a_cross_crate_reference_clears_the_candidate(self):
        names = [c["name"] for c in self._scan("pub-scan")["pub_scan"]["candidates"]]
        self.assertNotIn("shared_service", names, "beta uses shared_service in production")

    def test_a_name_two_crates_define_is_listed_as_a_collision_never_flagged(self):
        pub_scan = self._scan("pub-scan")["pub_scan"]
        self.assertEqual(pub_scan["collisions"], ["Collide"])
        self.assertNotIn("Collide", [c["name"] for c in pub_scan["candidates"]])

    def test_common_and_short_names_are_skipped_and_counted(self):
        pub_scan = self._scan("pub-scan")["pub_scan"]
        self.assertEqual(pub_scan["skipped_common"], 2, "`new` (common) and `abc` (short)")
        names = {c["name"] for c in pub_scan["candidates"]}
        self.assertFalse(names & {"new", "abc"}, f"skipped names are never flagged: {names}")


# ------------------------------------------------------------------ deps ----

#: ``crates/alpha``'s manifest: package ``alpha-core``, a ``default`` feature, a feature used in
#: code, an unreferenced one and one ``beta`` forwards.
DEPS_ALPHA_MANIFEST = (
    '[package]\nname = "alpha-core"\nversion = "0.1.0"\nedition = "2021"\n\n'
    '[features]\ndefault = ["fast"]\nfast = []\nunused-flag = []\nforwarded = []\n'
)

DEPS_ALPHA_LIB = '#[cfg(feature = "fast")]\npub fn speedy() {}\n'

DEPS_BETA_MANIFEST = (
    '[package]\nname = "beta"\nversion = "0.1.0"\nedition = "2021"\n\n'
    '[dependencies]\nalpha-core = { path = "../alpha", features = ["forwarded"] }\n'
)

#: ``cargo-machete`` 0.9.2's report for this workspace (§S4.2): a ``<package> -- <path>/Cargo.toml:``
#: line, then tab-indented dependency names; ``@ROOT@`` is the directory it was given.
MACHETE_OUTPUT = (
    "Analyzing dependencies of crates in this directory...\n"
    "cargo-machete found the following unused dependencies in @ROOT@:\n"
    "alpha-core -- @ROOT@/crates/alpha/Cargo.toml:\n"
    "\tserde\n"
    "\titertools\n"
    "beta -- @ROOT@/crates/beta/Cargo.toml:\n"
    "\tregex\n"
    "\n"
    "If you believe cargo-machete has detected an unused dependency incorrectly,\n"
    "you can add the dependency to the list of dependencies to ignore in the\n"
    "`[package.metadata.cargo-machete]` section of the appropriate Cargo.toml. For example:\n"
    "\n"
    "[package.metadata.cargo-machete]\n"
    'ignored = ["prost"]\n'
    "\n"
    "Done!\n"
)


def _cargo_machete_stand_in(log: Path) -> str:
    """A ``cargo-machete`` stand-in: appends its argv to ``log``, prints :data:`MACHETE_OUTPUT`
    for the directory it was given and exits 1, as the real tool does on finding unused deps."""
    return (
        f"#!{sys.executable}\n"
        "import json, sys\n"
        f"with open({str(log)!r}, 'a', encoding='utf-8') as fh:\n"
        "    fh.write(json.dumps({'argv': sys.argv[1:]}) + '\\n')\n"
        f"sys.stdout.write({MACHETE_OUTPUT!r}.replace('@ROOT@', sys.argv[1]))\n"
        "sys.exit(1)\n"
    )


class DepsModeTest(_ModeCase):
    """§S2.1 ``deps``: ``cargo-machete`` present, its output parsed into unused deps, and absent,
    reported as not installed; a feature unreferenced, referenced in code, or forwarded by another
    member; ``default`` ignored."""

    def setUp(self):
        super().setUp()
        self.machete_log = self.work / "machete.log"
        write_files(self.project, {
            "Cargo.toml": '[workspace]\nmembers = ["crates/alpha", "crates/beta"]\n',
            "crates/alpha/Cargo.toml": DEPS_ALPHA_MANIFEST,
            "crates/alpha/src/lib.rs": DEPS_ALPHA_LIB,
            "crates/beta/Cargo.toml": DEPS_BETA_MANIFEST,
            "crates/beta/src/lib.rs": "pub fn beta_entry() {}\n",
        })

    def _machete_calls(self) -> list:
        if not self.machete_log.exists():
            return []
        return [json.loads(line)
                for line in self.machete_log.read_text(encoding="utf-8").splitlines()]

    def test_cargo_machetes_output_is_parsed_into_unused_deps(self):
        report = self._scan("deps", stand_ins={
            "cargo-machete": _cargo_machete_stand_in(self.machete_log)})
        self.assertEqual(self._machete_calls(), [{"argv": [str(self.project.resolve())]}],
                         "the cargo-machete stand-in ran once, on the project root")
        self.assertEqual(report["deps"]["machete"], {
            "available": True,
            "unused": [{"crate": "alpha_core", "dep": "serde"},
                       {"crate": "alpha_core", "dep": "itertools"},
                       {"crate": "beta", "dep": "regex"}],
        })

    def test_cargo_machete_absent_is_reported_as_not_installed(self):
        report = self._scan("deps")
        self.assertFalse((self.work / "bin" / "cargo-machete").exists())
        self.assertEqual(self._machete_calls(), [], "no cargo-machete stand-in is on PATH")
        self.assertEqual(report["deps"]["machete"], {"available": False, "unused": []})
        self.assertIn("cargo-machete NOT installed", self._markdown())

    def test_only_the_unreferenced_unforwarded_feature_is_a_finding(self):
        features = self._scan("deps")["deps"]["features"]
        self.assertEqual([(f["crate"], f["feature"]) for f in features],
                         [("alpha_core", "unused-flag")],
                         "`fast` is used in code, `forwarded` is forwarded by beta, "
                         "`default` is ignored")
        self.assertRegex(features[0]["id"], FINDING_ID_RE)
        self.assertIn("never referenced", features[0]["note"])


# ------------------------------------------------------------------ reconcile ----

RECONCILE_LIB = (
    "#[expect(dead_code)]\nfn kept_for_plugin() {}\n"
    "#[expect(dead_code)]\nfn forgotten_mark() {}\n"
    "#[allow(dead_code)]\nfn bare_one() {}\n"
    "#[allow(dead_code)]\nfn bare_two() {}\n"
    "#[allow(dead_code)]\nfn bare_three() {}\n"
)

RECONCILE_REGISTER = (
    '[[keep_future]]\ncrate = "alpha"\nitem = "fn kept_for_plugin"\nreason = "plugin API"\n\n'
    '[[keep_future]]\ncrate = "alpha"\nitem = "fn removed_long_ago"\nreason = "gone"\n'
)


class ReconcileModeTest(_ModeCase):
    """§S2.1 ``reconcile``: register present and absent; unregistered ``expect`` marks;
    orphaned register entries; the count of bare ``allow``s."""

    def setUp(self):
        super().setUp()
        write_files(self.project, {
            "Cargo.toml": WORKSPACE_ROOT_MANIFEST,
            "crates/alpha/Cargo.toml": cargo_member_manifest("alpha"),
            "crates/alpha/src/lib.rs": RECONCILE_LIB,
        })

    def test_with_a_register_the_unregistered_marks_and_orphaned_entries_are_findings(self):
        write_files(self.out, {"dead_code_register.toml": RECONCILE_REGISTER})
        reconcile = self._scan("reconcile")["reconcile"]
        self.assertEqual(reconcile["register"]["path"],
                         str(self.out.resolve() / "dead_code_register.toml"))
        self.assertTrue(reconcile["register"]["exists"])
        self.assertEqual(len(reconcile["register"]["entries"]), 2)
        self.assertEqual(reconcile["expect_marks"], 2)
        self.assertEqual(reconcile["bare_allows_pending"], 3)
        self.assertEqual([(m["crate"], m["item"], m["line"])
                          for m in reconcile["unregistered_marks"]],
                         [("alpha", "fn forgotten_mark", 3)])
        self.assertEqual(reconcile["orphaned_register_entries"],
                         [{"crate": "alpha", "item": "fn removed_long_ago", "reason": "gone"}])

    def test_without_a_register_every_expect_mark_is_unregistered(self):
        reconcile = self._scan("reconcile")["reconcile"]
        self.assertFalse(reconcile["register"]["exists"])
        self.assertEqual(reconcile["register"]["entries"], [])
        self.assertEqual([m["item"] for m in reconcile["unregistered_marks"]],
                         ["fn kept_for_plugin", "fn forgotten_mark"])
        self.assertEqual(reconcile["orphaned_register_entries"], [])
        self.assertEqual(reconcile["bare_allows_pending"], 3)
        self.assertIn("register: MISSING", self._markdown())


# ------------------------------------------------------------------ boundaries ----

BOUNDARY_MEMBERS = {
    "Cargo.toml": (
        "[workspace]\n"
        'members = ["crates/core", "crates/adapter-http", "crates/adapter-grpc", "crates/app"]\n'
    ),
    "crates/core/Cargo.toml": (
        '[package]\nname = "core"\nversion.workspace = true\nedition = "2021"\n\n'
        '[dependencies]\nserde = "1"\ntokio = "1"\n\n'
        '[dev-dependencies]\ncriterion = "0.5"\n'
    ),
    "crates/adapter-http/Cargo.toml": (
        '[package]\nname = "adapter-http"\nversion.workspace = true\nedition = "2021"\n\n'
        '[dependencies]\ncore.workspace = true\nserde = "1"\nhyper = "1"\nanyhow = "1"\n'
        'internal_util = "0.1"\n'
    ),
    "crates/adapter-grpc/Cargo.toml": (
        '[package]\nname = "adapter-grpc"\nversion = { workspace = true }\nedition = "2021"\n\n'
        '[dependencies]\ncore.workspace = true\nserde = "1"\ntonic = "0.12"\n'
        'internal_util = "0.1"\n'
    ),
    "crates/app/Cargo.toml": (
        '[package]\nname = "app"\nversion = "0.1.0"\nedition = "2021"\n\n'
        '[dependencies]\nserde = "1"\ninternal_util = "0.1"\ntokio.workspace = true\n'
    ),
    "crates/core/src/lib.rs": "pub fn core_entry() {}\n",
    "crates/adapter-http/src/lib.rs": "pub fn http_entry() {}\n",
    "crates/adapter-grpc/src/lib.rs": "pub fn grpc_entry() {}\n",
    "crates/app/src/lib.rs": "pub fn app_entry() {}\n",
}

#: ``forbid_deps`` on ``core`` (a dev dependency it names is not a production dep);
#: ``allow_deps_only`` on every member under ``crates/adapter-``; version lockstep; hoisting at
#: three crates with ``internal_`` exempt.
BOUNDARY_RULES = (
    "[version_lockstep]\nrequire_workspace_version = true\n\n"
    '[hoisting]\nmin_crates = 3\nexempt_prefixes = ["internal_"]\n\n'
    '[[rules]]\ncrate = "core"\nforbid_deps = ["tokio", "criterion"]\n'
    'reason = "core stays runtime-free"\n\n'
    '[[rules]]\nmember_prefix = "crates/adapter-"\n'
    'allow_deps_only = ["core", "serde", "hyper", "tonic", "internal_util"]\n'
    'reason = "adapters are thin"\n'
)


class BoundariesModeTest(_ModeCase):
    """§S2.1 ``boundaries``: no rules file; ``forbid_deps``; ``allow_deps_only``;
    ``member_prefix``; version lockstep; hoisting with ``min_crates`` and ``exempt_prefixes``."""

    def setUp(self):
        super().setUp()
        write_files(self.project, BOUNDARY_MEMBERS)

    def test_without_a_rules_file_nothing_is_checked(self):
        boundaries = self._scan("boundaries")["boundaries"]
        self.assertEqual(boundaries, {
            "rules_file": str(self.out.resolve() / "boundary_rules.toml"), "exists": False,
            "violations": [], "hoist_candidates": [], "lockstep_failures": []})

    def test_forbid_deps_and_a_member_prefix_allow_list_report_their_violations(self):
        write_files(self.out, {"boundary_rules.toml": BOUNDARY_RULES})
        boundaries = self._scan("boundaries")["boundaries"]
        self.assertTrue(boundaries["exists"])
        self.assertEqual(
            [(v["crate"], v["dep"], v["reason"]) for v in boundaries["violations"]],
            [("core", "tokio", "core stays runtime-free"),
             ("adapter_http", "anyhow", "not in allow-list (adapters are thin)")],
            "core's dev-dependency criterion is not a production dep; adapter-grpc keeps to the "
            "allow-list; app has no rule")
        for violation in boundaries["violations"]:
            self.assertRegex(violation["id"], FINDING_ID_RE)

    def test_version_lockstep_flags_a_member_with_its_own_version(self):
        write_files(self.out, {"boundary_rules.toml": BOUNDARY_RULES})
        boundaries = self._scan("boundaries")["boundaries"]
        self.assertEqual([(f["crate"], f["detail"]) for f in boundaries["lockstep_failures"]],
                         [("app", "version is not workspace-inherited")])

    def test_hoisting_names_a_dep_declared_by_min_crates_members_minus_exempt_prefixes(self):
        write_files(self.out, {"boundary_rules.toml": BOUNDARY_RULES})
        boundaries = self._scan("boundaries")["boundaries"]
        self.assertEqual(
            [(h["dep"], h["declarers"]) for h in boundaries["hoist_candidates"]],
            [("serde", ["adapter_grpc", "adapter_http", "app", "core"])],
            "internal_util (three declarers) is exempt; tokio is declared with its own version "
            "by core alone")

    def test_hoisting_defaults_to_three_crates_and_no_exemption(self):
        write_files(self.out, {"boundary_rules.toml": '[[rules]]\ncrate = "app"\n'})
        boundaries = self._scan("boundaries")["boundaries"]
        self.assertEqual([h["dep"] for h in boundaries["hoist_candidates"]],
                         ["internal_util", "serde"])
        self.assertEqual(boundaries["lockstep_failures"], [], "lockstep is opt-in")
        self.assertEqual(boundaries["violations"], [])

    def test_hoisting_below_min_crates_names_nothing(self):
        write_files(self.out, {"boundary_rules.toml": "[hoisting]\nmin_crates = 5\n"})
        boundaries = self._scan("boundaries")["boundaries"]
        self.assertEqual(boundaries["hoist_candidates"], [], "serde has four declarers, not five")


# ------------------------------------------------------------------ hot-path ----

#: The guarded file, line by line: production hits on lines 1 and 6 only.
HOT_PATH_FRAME = (
    "use serde_json::Value;\n"                                          # 1 violation
    "// serde_json:: is forbidden on this path\n"                       # 2 comment
    "fn dump(x: u8) { serde_json::to_vec(&x); } // JSON-BOUNDARY\n"     # 3 marker on line
    "// JSON-BOUNDARY: the admin dump below\n"                          # 4 marker
    "fn admin(x: u8) { serde_json::to_string(&x); }\n"                 # 5 marker line before
    "fn decode(b: &[u8]) { serde_json::from_slice::<Value>(b); }\n"    # 6 violation
    "#[cfg(test)]\n"                                                    # 7
    "mod tests {\n"                                                     # 8
    "    fn t() { serde_json::json!({}); }\n"                           # 9 test-gated
    "}\n"                                                               # 10
)

HOT_PATH_SCAN_RULES = (
    "[[forbid]]\n"
    'id = "no-json-hot"\n'
    'paths = ["crates/alpha/src"]\n'
    'allow_paths = ["crates/alpha/src/admin.rs"]\n'
    'patterns = ["serde_json::"]\n'
    'source = "D3"\n'
    "\n"
    "[[require_present]]\n"
    'id = "decoder-present"\n'
    'paths = ["crates/alpha/src"]\n'
    'pattern = "fn decode\\\\("\n'
    "\n"
    "[[require_present]]\n"
    'id = "binary-codec-present"\n'
    'paths = ["crates/alpha/src/frame.rs"]\n'
    'pattern = "fn decode_binary"\n'
    'source = "D3"\n'
)


class HotPathModeTest(_ModeCase):
    """§S2.1 ``hot-path`` (the JSON report): no rules file; a ``forbid`` rule's patterns on
    production lines; ``allow_paths``; the boundary marker on the line or the line before;
    comment and ``#[cfg(test)]`` lines dropped; ``require_present`` reporting a sanity failure."""

    def setUp(self):
        super().setUp()
        write_files(self.project, {
            "Cargo.toml": WORKSPACE_ROOT_MANIFEST,
            "crates/alpha/Cargo.toml": cargo_member_manifest("alpha"),
            "crates/alpha/src/lib.rs": "mod admin;\nmod frame;\n",
            "crates/alpha/src/frame.rs": HOT_PATH_FRAME,
            "crates/alpha/src/admin.rs": "fn dump(x: u8) { serde_json::to_string(&x); }\n",
        })

    def test_without_a_rules_file_nothing_is_checked(self):
        hot_path = self._scan("hot-path")["hot_path"]
        self.assertEqual(hot_path, {
            "rules_file": str(self.out.resolve() / "hot_path_rules.toml"), "exists": False,
            "violations": [], "sanity_failures": []})

    def test_a_forbid_rule_reports_only_its_production_hits(self):
        write_files(self.out, {"hot_path_rules.toml": HOT_PATH_SCAN_RULES})
        hot_path = self._scan("hot-path")["hot_path"]
        self.assertTrue(hot_path["exists"])
        self.assertEqual(
            [(v["rule"], v["path"], v["line"], v["content"], v["source"])
             for v in hot_path["violations"]],
            [("no-json-hot", "crates/alpha/src/frame.rs", 1, "use serde_json::Value;", "D3"),
             ("no-json-hot", "crates/alpha/src/frame.rs", 6,
              "fn decode(b: &[u8]) { serde_json::from_slice::<Value>(b); }", "D3")],
            "admin.rs is allow-listed; lines 2 and 4 are comments, 3 carries the marker, 5 "
            "follows it, 9 is test-gated")
        for violation in hot_path["violations"]:
            self.assertRegex(violation["id"], FINDING_ID_RE)

    def test_an_unmet_require_present_rule_is_a_sanity_failure(self):
        write_files(self.out, {"hot_path_rules.toml": HOT_PATH_SCAN_RULES})
        hot_path = self._scan("hot-path")["hot_path"]
        self.assertEqual(
            [(s["rule"], s["pattern"], s["source"]) for s in hot_path["sanity_failures"]],
            [("binary-codec-present", "fn decode_binary", "D3")],
            "decoder-present is met by frame.rs line 6")


# ------------------------------------------------------------------ lift-lint ----

#: A library whose ``dead_code`` suppressions take every form ``lift-lint`` strips: plain, indented
#: with a reason, and with a trailing comment; a commented-out one and another lint's ``allow``
#: stay.
LIFT_STRIP_LIB = (
    "pub fn used() {}\n"
    "#[allow(dead_code)]\n"
    "fn a() {}\n"
    '    #[expect(dead_code, reason = "held for parity")]\n'
    "fn b() {}\n"
    "#[allow(dead_code)] // trailing note\n"
    "fn c() {}\n"
    "// #[allow(dead_code)] commented out\n"
    "#[allow(unused_variables)]\n"
    "fn d() {}\n"
)

#: :data:`LIFT_STRIP_LIB` as the scratch copy holds it: the three suppressions gone.
LIFT_STRIPPED_LIB = (
    "pub fn used() {}\n"
    "fn a() {}\n"
    "fn b() {}\n"
    "fn c() {}\n"
    "// #[allow(dead_code)] commented out\n"
    "#[allow(unused_variables)]\n"
    "fn d() {}\n"
)

#: ``cargo check --message-format=json``'s stdout: a non-JSON line, an artifact line, a
#: message with no code, a ``dead_code`` warning with a primary and a secondary span, an
#: ``unused_imports`` warning, a second ``dead_code`` warning, and ``build-finished``.
LIFT_CARGO_STDOUT = "\n".join([
    "   Compiling alpha v0.1.0",
    json.dumps({"reason": "compiler-artifact", "package_id": "alpha 0.1.0"}),
    json.dumps({"reason": "compiler-message",
                "message": {"code": None, "level": "warning", "message": "unused doc comment",
                            "spans": [{"file_name": "crates/alpha/src/lib.rs",
                                       "line_start": 1, "is_primary": True}]}}),
    json.dumps({"reason": "compiler-message",
                "message": {"code": {"code": "dead_code"}, "level": "warning",
                            "message": "function `a` is never used",
                            "spans": [{"file_name": "crates/alpha/src/lib.rs",
                                       "line_start": 2, "is_primary": True},
                                      {"file_name": "crates/alpha/src/lib.rs",
                                       "line_start": 7, "is_primary": False}]}}),
    json.dumps({"reason": "compiler-message",
                "message": {"code": {"code": "unused_imports"}, "level": "warning",
                            "message": "unused import: `std::fmt`",
                            "spans": [{"file_name": "crates/alpha/src/lib.rs",
                                       "line_start": 1, "is_primary": True}]}}),
    json.dumps({"reason": "compiler-message",
                "message": {"code": {"code": "dead_code"}, "level": "warning",
                            "message": "function `helper` is never used",
                            "spans": [{"file_name": "crates/alpha/tests/it.rs",
                                       "line_start": 1, "is_primary": True}]}}),
    json.dumps({"reason": "build-finished", "success": False}),
]) + "\n"

#: The warnings ``lift-lint`` collects from :data:`LIFT_CARGO_STDOUT`, in order.
LIFT_FIRED = [
    {"path": "crates/alpha/src/lib.rs", "line": 2, "text": "function `a` is never used"},
    {"path": "crates/alpha/tests/it.rs", "line": 1, "text": "function `helper` is never used"},
]


def _recording_cargo_stand_in(log: Path, stdout: str, exit_code: int) -> str:
    """A ``cargo`` stand-in that appends ``{argv, cwd, tree}`` to ``log`` -- ``tree`` maps every
    ``.rs`` file under its working directory to its text -- then prints ``stdout`` and exits
    ``exit_code``."""
    return (
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "tree = {p.as_posix(): p.read_text() for p in sorted(Path('.').rglob('*.rs'))}\n"
        f"with open({str(log)!r}, 'a', encoding='utf-8') as fh:\n"
        "    fh.write(json.dumps({'argv': sys.argv[1:], 'cwd': os.getcwd(), 'tree': tree})"
        " + '\\n')\n"
        f"sys.stdout.write({stdout!r})\n"
        f"sys.exit({exit_code})\n"
    )


class LiftLintCollectionTest(_ModeCase):
    """§S2.1 ``lift-lint``: suppressions stripped and counted; the ``dead_code`` warnings
    collected from the compiler's JSON messages; ``check_ok`` from the compiler's exit; the
    scratch copy removed."""

    WORKSPACE = {
        "Cargo.toml": WORKSPACE_ROOT_MANIFEST,
        "crates/alpha/Cargo.toml": cargo_member_manifest("alpha"),
        "crates/alpha/src/lib.rs": LIFT_STRIP_LIB,
        "crates/alpha/tests/it.rs": "#[allow(dead_code)]\nfn helper() {}\n",
    }

    def setUp(self):
        super().setUp()
        self.cargo_log = self.work / "cargo.log"
        scratch_before = _scratch_dirs()
        self.addCleanup(lambda: [shutil.rmtree(d, ignore_errors=True)
                                 for d in _scratch_dirs() - scratch_before])
        git_repo(self.project, self.WORKSPACE)

    def _lift_lint(self, exit_code: int) -> tuple:
        report = self._scan("lift-lint", stand_ins={
            "cargo": _recording_cargo_stand_in(self.cargo_log, LIFT_CARGO_STDOUT, exit_code)})
        calls = [json.loads(line)
                 for line in self.cargo_log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(calls), 1, f"the cargo stand-in ran once: {calls}")
        self.assertFalse(Path(calls[0]["cwd"]).exists(),
                         f"the scratch copy {calls[0]['cwd']} is removed")
        return report["lift_lint"], calls[0]

    def test_the_suppressions_are_stripped_from_the_scratch_copy_and_counted(self):
        lift_lint, call = self._lift_lint(0)
        self.assertEqual(call["argv"],
                         ["check", "--workspace", "--all-features", "--message-format=json"])
        self.assertEqual(call["tree"], {
            "crates/alpha/src/lib.rs": LIFT_STRIPPED_LIB,
            "crates/alpha/tests/it.rs": "fn helper() {}\n",
        })
        self.assertEqual(lift_lint["stripped_attr_lines"], 4)
        self.assertEqual((self.project / "crates/alpha/src/lib.rs").read_text(encoding="utf-8"),
                         LIFT_STRIP_LIB, "the project's own tree is never stripped")

    def test_only_primary_spans_of_dead_code_messages_are_collected(self):
        lift_lint, _ = self._lift_lint(0)
        self.assertEqual(lift_lint["fired"], LIFT_FIRED)
        self.assertTrue(lift_lint["check_ok"])

    def test_a_failing_compiler_exit_sets_check_ok_false_and_keeps_the_warnings(self):
        lift_lint, _ = self._lift_lint(101)
        self.assertIs(lift_lint["check_ok"], False)
        self.assertEqual(lift_lint["fired"], LIFT_FIRED)
        self.assertIn("check FAILED", self._markdown())


# ------------------------------------------------------------------ mode selection ----

class ModeSelectionTest(_ModeCase):
    """§S2.2: the default set, an explicit subset, and ``--lift-lint`` adding its mode."""

    def setUp(self):
        super().setUp()
        self.cargo_log = self.work / "cargo.log"
        scratch_before = _scratch_dirs()
        self.addCleanup(lambda: [shutil.rmtree(d, ignore_errors=True)
                                 for d in _scratch_dirs() - scratch_before])
        git_repo(self.project, {
            "Cargo.toml": WORKSPACE_ROOT_MANIFEST,
            "crates/alpha/Cargo.toml": cargo_member_manifest("alpha"),
            "crates/alpha/src/lib.rs": LIFT_LINT_LIB,
        })
        self.stand_ins = {"cargo": _cargo_stand_in(self.cargo_log)}

    def _cargo_runs(self) -> int:
        if not self.cargo_log.exists():
            return 0
        return len(self.cargo_log.read_text(encoding="utf-8").splitlines())

    def test_no_mode_argument_runs_the_default_set_and_not_lift_lint(self):
        report = self._scan(stand_ins=self.stand_ins)
        self.assertEqual(report["meta"]["modes"], DEFAULT_MODES)
        self.assertEqual(_section_keys(report), {MODE_KEYS[m] for m in DEFAULT_MODES})
        self.assertEqual(self._cargo_runs(), 0, "lift-lint is opt-in: cargo never ran")

    def test_an_explicit_subset_runs_only_those_modes(self):
        report = self._scan("inventory", "hot-path", stand_ins=self.stand_ins)
        self.assertEqual(report["meta"]["modes"], ["inventory", "hot-path"])
        self.assertEqual(_section_keys(report), {"inventory", "hot_path"})
        self.assertEqual(self._cargo_runs(), 0)

    def test_reconcile_alone_reports_no_inventory_section(self):
        report = self._scan("reconcile", stand_ins=self.stand_ins)
        self.assertEqual(_section_keys(report), {"reconcile"})
        self.assertEqual(report["reconcile"]["bare_allows_pending"], 1,
                         "reconcile still reads the inventory it does not report")

    def test_the_lift_lint_flag_adds_lift_lint_to_an_explicit_subset(self):
        report = self._scan("inventory", "--lift-lint", stand_ins=self.stand_ins)
        self.assertEqual(report["meta"]["modes"], ["inventory", "lift-lint"])
        self.assertEqual(_section_keys(report), {"inventory", "lift_lint"})
        self.assertEqual(self._cargo_runs(), 1)

    def test_the_lift_lint_flag_adds_lift_lint_to_the_default_set(self):
        report = self._scan("--lift-lint", stand_ins=self.stand_ins)
        self.assertEqual(report["meta"]["modes"], DEFAULT_MODES + ["lift-lint"])
        self.assertEqual(_section_keys(report),
                         {MODE_KEYS[m] for m in DEFAULT_MODES + ["lift-lint"]})
        self.assertEqual(self._cargo_runs(), 1)

    def test_the_lift_lint_flag_with_the_lift_lint_mode_runs_it_once(self):
        report = self._scan("lift-lint", "--lift-lint", stand_ins=self.stand_ins)
        self.assertEqual(report["meta"]["modes"], ["lift-lint"])
        self.assertEqual(self._cargo_runs(), 1)


# ------------------------------------------------------------------ stable ids ----

STABLE_ID_LIB = (
    "#[allow(dead_code)]\nfn first_unused() {}\n"
    "#[allow(dead_code)]\nfn second_unused() {}\n"
    "pub fn lonely_export() {}\n"
)


class StableFindingIdsTest(_ModeCase):
    """§S2.3: the same tree yields the same ids, and moving an item to another path changes
    its id."""

    def setUp(self):
        super().setUp()
        write_files(self.project, {
            "Cargo.toml": WORKSPACE_ROOT_MANIFEST,
            "crates/alpha/Cargo.toml": cargo_member_manifest("alpha"),
            "crates/alpha/src/lib.rs": STABLE_ID_LIB,
        })

    @staticmethod
    def _ids(report) -> dict:
        ids = {("inventory", f["item"]): f["id"] for f in report["inventory"]}
        ids.update({("pub", c["name"]): c["id"] for c in report["pub_scan"]["candidates"]})
        return ids

    def test_the_same_tree_yields_the_same_ids(self):
        first = self._ids(self._scan("inventory", "pub-scan", out=self.work / "out-1"))
        second = self._ids(self._scan("inventory", "pub-scan", out=self.work / "out-2"))
        self.assertEqual(sorted(first), [("inventory", "fn first_unused"),
                                         ("inventory", "fn second_unused"),
                                         ("pub", "lonely_export")])
        self.assertEqual(first, second)
        self.assertEqual(len(set(first.values())), 3, f"three distinct ids: {first}")

    def test_moving_an_item_to_another_path_changes_its_id_and_only_its(self):
        before = self._ids(self._scan("inventory", "pub-scan", out=self.work / "out-1"))
        write_files(self.project, {
            "crates/alpha/src/lib.rs": ("mod legacy;\n#[allow(dead_code)]\nfn first_unused() {}\n"
                                        "pub fn lonely_export() {}\n"),
            "crates/alpha/src/legacy.rs": "#[allow(dead_code)]\nfn second_unused() {}\n",
        })
        after = self._ids(self._scan("inventory", "pub-scan", out=self.work / "out-2"))
        self.assertEqual(sorted(after), sorted(before))
        self.assertNotEqual(after[("inventory", "fn second_unused")],
                            before[("inventory", "fn second_unused")],
                            "second_unused moved from src/lib.rs to src/legacy.rs")
        self.assertEqual(after[("inventory", "fn first_unused")],
                         before[("inventory", "fn first_unused")],
                         "first_unused stayed in src/lib.rs, a line lower")
        self.assertEqual(after[("pub", "lonely_export")], before[("pub", "lonely_export")])


if __name__ == "__main__":
    unittest.main()
