"""Gates for the Model B Pi package, ``pi-package/`` (CR-MDB-029 \u00a7S1).

What is gated:

- ``pi-package/package.json``: the \u00a7S1 fields (name, version, keywords,
  license, ``pi`` manifest, peer dependency), no ``dependencies`` key;
- ``pi-package/`` carries no ``skills/`` directory and names no ``.claude``
  or ``.omp`` path in any file;
- ``pi-package/README.md`` is the install guide's marked regions as
  ``generator/build.py`` renders them, and ``build.py --check`` fails on a
  one-byte drift in either the README or a region of the guide.

Orchestrator rulings (2026-09-24, on the cycle-111 RED design):

- D1 \u2014 README rendering: the lines strictly between each begin/end
  marker pair, in guide order, each region's leading and trailing blank lines
  trimmed, regions joined by exactly one blank line, the file ending in a
  single newline. No marker lines, no title, no banner. :func:`render_readme`
  below is this test's own oracle; the README is compared to it byte for byte.
- D2 \u2014 the marked-region convention has one parser,
  ``tests.test_install_guide.parse_marked_regions``, reused here.
- D3 \u2014 the README is a target of every ``build.py`` invocation (like
  the codec copy): ``build`` writes it, ``--check`` prints
  ``pi-package/README.md`` when it drifts, ``--list`` prints its path.
- D4 \u2014 drift gates mutate the live file one byte and restore it in a
  ``finally`` (the ``tests/test_agent_generator.py`` pattern); a byte changed
  OUTSIDE every region leaves ``--check`` clean.
- D5 \u2014 ``peerDependencies`` is exactly
  ``{"@earendil-works/pi-coding-agent": "*"}``; other top-level keys
  (``description``, ``files``, ...) are not gated; the path gate is the regex
  :data:`HARNESS_HOME_PATH`.
- Q1 \u2014 this cycle pins only the agreement between ``pi.extensions`` and
  the files under ``pi-package/extensions/`` (a missing or empty directory
  counts as an empty list); the exact ``["extensions/worktree.ts"]``
  pin (CR-MDB-047 \u00a7S4: ``sandesh-watcher.ts`` removed) belongs to the
  extension's own cycle.
- Q2 \u2014 ``version`` is the npm-semver form of ``modelb_axi.__version__``
  (a PEP 440 ``0.1.0.dev0`` is not valid npm semver): ``X.Y.Z`` unchanged;
  ``X.Y.Z.devN`` \u2192 ``X.Y.Z-dev.N``; ``X.Y.ZaN``/``bN``/``rcN`` \u2192
  ``X.Y.Z-alpha.N``/``-beta.N``/``-rc.N``. :func:`npm_semver` is this test's
  oracle, table-tested below; where the product keeps the mapping is not
  pinned.

Stdlib only.
"""

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

from tests.test_install_guide import parse_marked_regions

REPO_ROOT = Path(__file__).resolve().parent.parent
PI_PACKAGE = REPO_ROOT / "pi-package"
PACKAGE_JSON = PI_PACKAGE / "package.json"
PI_README = PI_PACKAGE / "README.md"
EXTENSIONS_DIR = PI_PACKAGE / "extensions"
SKILLS_DIR = PI_PACKAGE / "skills"
GUIDE = REPO_ROOT / "docs" / "install-guide.md"
BUILD_PY = REPO_ROOT / "generator" / "build.py"
PI_README_REL = "pi-package/README.md"

PACKAGE_NAME = "@anthill-tec/modelb-pi"
PEER_DEPENDENCIES = {"@earendil-works/pi-coding-agent": "*"}

#: A ``.claude`` or ``.omp`` path segment (``~/.claude``, ``$HOME/.omp/x``,
#: ``.claude/settings.json``); ``claude-code`` does not match (ruling D5).
HARNESS_HOME_PATH = re.compile(r"(?<![\w-])\.(claude|omp)(?![\w-])")

#: CR-MDB-047 \u00a7S4 \u2014 the retired Model B watcher: its tool, its command
#: registration, and its ``/watcher`` command (never Sandesh's ``/sandesh-watcher``).
WATCHER_MARKERS = (
    re.compile(r"sandesh_watcher"),
    re.compile(r"registerCommand\(\s*['\"]watcher['\"]"),
    re.compile(r"/watcher\b"),
)

#: The semver 2.0.0 grammar (semver.org, the suggested regular expression).
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

_PEP440_RE = re.compile(r"^(\d+\.\d+\.\d+)(?:\.dev(\d+)|(a|b|rc)(\d+))?$")
_PRE_LABELS = {"a": "alpha", "b": "beta", "rc": "rc"}


def npm_semver(version: str) -> str:
    """The npm-semver form of a PEP 440 version (orchestrator ruling Q2)."""
    match = _PEP440_RE.match(version)
    if not match:
        raise ValueError(f"no npm-semver mapping for version {version!r}")
    release, dev, pre, pre_n = match.groups()
    if dev is not None:
        return f"{release}-dev.{int(dev)}"
    if pre is not None:
        return f"{release}-{_PRE_LABELS[pre]}.{int(pre_n)}"
    return release


def render_readme(guide_text: str) -> str:
    """The Pi package README for ``guide_text`` (orchestrator ruling D1)."""
    regions, faults = parse_marked_regions(guide_text)
    if faults or not regions:
        raise AssertionError(f"the guide's marked regions are malformed: {faults or 'none'}")
    lines = guide_text.splitlines()
    blocks = []
    for _name, begin, end in regions:
        body = lines[begin + 1:end]
        while body and not body[0].strip():
            body.pop(0)
        while body and not body[-1].strip():
            body.pop()
        blocks.append("\n".join(body))
    return "\n\n".join(blocks) + "\n"


def _manifest() -> dict:
    if not PACKAGE_JSON.is_file():
        raise AssertionError(f"{PACKAGE_JSON.relative_to(REPO_ROOT)} does not exist")
    data = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AssertionError(f"package.json must be a JSON object, got {type(data).__name__}")
    return data


def _package_files() -> list[Path]:
    return sorted(p for p in PI_PACKAGE.rglob("*") if p.is_file())


def _run_build(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(BUILD_PY), *args],
        capture_output=True, text=True, timeout=60,
    )


def _flip_byte(data: bytes, at: int) -> bytes:
    """``data`` with the ASCII letter at ``at`` swapped for another letter."""
    old = data[at:at + 1]
    new = b"b" if old != b"b" else b"c"
    return data[:at] + new + data[at + 1:]


def _first_letter(data: bytes) -> int:
    """Byte offset of the first ASCII letter in ``data``."""
    match = re.search(rb"[A-Za-z]", data)
    if match is None:
        raise AssertionError("no letter to drift")
    return match.start()


def _first_letter_between(data: bytes, start_line: int, end_line: int) -> int:
    """Byte offset of the first ASCII letter on a line strictly between two
    0-based line indices (the marker lines of one region)."""
    offset = 0
    for i, line in enumerate(data.splitlines(keepends=True)):
        if start_line < i < end_line:
            match = re.search(rb"[A-Za-z]", line)
            if match:
                return offset + match.start()
        offset += len(line)
    raise AssertionError("no letter inside the region")


class PiPackageManifestTest(unittest.TestCase):
    """\u00a7S1 AC1 \u2014 ``pi-package/package.json`` carries the \u00a7S1 fields."""

    def test_name_is_the_anthill_tec_scoped_package(self):
        self.assertEqual(_manifest().get("name"), PACKAGE_NAME)

    def test_version_is_the_npm_semver_form_of_the_package_dunder_version(self):
        from modelb_axi import __version__
        expected = npm_semver(__version__)
        version = _manifest().get("version")
        self.assertIsInstance(version, str, f"package.json version must be a string, got {version!r}")
        assert isinstance(version, str)
        self.assertEqual(
            version, expected,
            f"package.json version must be the npm-semver form of modelb_axi.__version__ "
            f"{__version__!r} (ruling Q2), i.e. {expected!r}; got {version!r}",
        )
        self.assertRegex(version, SEMVER_RE, "package.json version must be valid semver 2.0.0")

    def test_keywords_are_exactly_pi_package(self):
        self.assertEqual(_manifest().get("keywords"), ["pi-package"])

    def test_license_is_mit(self):
        self.assertEqual(_manifest().get("license"), "MIT")

    def test_peer_dependencies_are_exactly_the_pi_coding_agent_at_any_version(self):
        self.assertEqual(_manifest().get("peerDependencies"), PEER_DEPENDENCIES)

    def test_manifest_declares_no_dependencies_key(self):
        manifest = _manifest()
        self.assertNotIn(
            "dependencies", manifest,
            f"package.json must carry no 'dependencies' key, got {manifest.get('dependencies')!r}",
        )

    def test_pi_manifest_extensions_agree_with_the_extensions_directory(self):
        pi = _manifest().get("pi")
        self.assertIsInstance(pi, dict, f"package.json 'pi' must be an object, got {pi!r}")
        assert isinstance(pi, dict)
        self.assertEqual(sorted(pi), ["extensions"], "the 'pi' manifest carries only 'extensions'")
        listed = pi["extensions"]
        self.assertIsInstance(listed, list, f"pi.extensions must be a list, got {listed!r}")
        self.assertEqual(len(listed), len(set(listed)), f"pi.extensions lists a file twice: {listed}")
        bad = [e for e in listed if not (isinstance(e, str) and e.startswith("extensions/"))]
        self.assertEqual(bad, [], "every pi.extensions entry must be 'extensions/<file>'")
        on_disk = sorted(
            p.relative_to(PI_PACKAGE).as_posix() for p in EXTENSIONS_DIR.rglob("*") if p.is_file()
        ) if EXTENSIONS_DIR.is_dir() else []
        self.assertEqual(
            sorted(listed), on_disk,
            "pi.extensions must list exactly the files under pi-package/extensions/",
        )

    def test_pi_manifest_extensions_are_exactly_the_worktree_extension(self):
        # Ruling Q1 (cycle 111) moved this exact pin to the extension's own
        # cycle (C2, cycle 112); orchestrator ruling H adds it here without
        # migrating the agreement test above. MIGRATED at CR-MDB-039 C1 RED
        # (S1: pi-package/extensions/worktree.ts, listed in pi.extensions),
        # then at CR-MDB-047 C2 RED (\u00a7S4: sandesh-watcher.ts is removed;
        # package.json lists only worktree.ts); was
        # test_pi_manifest_extensions_are_exactly_the_sandesh_watcher_and_the_worktree_extension.
        pi = _manifest().get("pi")
        self.assertIsInstance(pi, dict, f"package.json 'pi' must be an object, got {pi!r}")
        assert isinstance(pi, dict)
        self.assertEqual(sorted(pi.get("extensions") or []), ["extensions/worktree.ts"])
        self.assertTrue((EXTENSIONS_DIR / "worktree.ts").is_file(), "pi-package/extensions/worktree.ts must exist")
        self.assertFalse(
            (EXTENSIONS_DIR / "sandesh-watcher.ts").exists(),
            "\u00a7S4: pi-package/extensions/sandesh-watcher.ts is removed",
        )

    def test_no_package_file_carries_the_model_b_watcher(self):
        # CR-MDB-047 \u00a7S4: the Model B watcher (its `sandesh_watcher` tool and its
        # `/watcher` command) is gone from the package; Sandesh's own extension
        # provides the wake (`/sandesh-watcher` is Sandesh's, not this package's).
        offending = []
        for path in _package_files():
            text = path.read_text(encoding="utf-8", errors="replace")
            rel = path.relative_to(PI_PACKAGE).as_posix()
            for pattern in WATCHER_MARKERS:
                if pattern.search(text):
                    offending.append(f"{rel}: {pattern.pattern}")
        self.assertEqual(offending, [], f"the Model B watcher remains in pi-package/: {offending}")

    def test_watcher_marker_detector_bites_and_spares_sandeshs_command(self):
        violating = (
            'pi.registerTool({ name: "sandesh_watcher" });',
            'pi.registerCommand("watcher", { handler });',
            "Run `/watcher status` to list them.",
        )
        for text in violating:
            self.assertTrue(any(p.search(text) for p in WATCHER_MARKERS), text)
        for text in ('pi.registerCommand("worktree", {});', "Use `/sandesh-watcher stop <your address>`."):
            self.assertFalse(any(p.search(text) for p in WATCHER_MARKERS), text)

    def test_package_carries_no_skills_directory(self):
        self.assertTrue(PI_PACKAGE.is_dir(), f"{PI_PACKAGE} must exist")
        self.assertFalse(SKILLS_DIR.exists(), f"{SKILLS_DIR} must not exist (the package carries no skills)")


class PiPackageHarnessPathTest(unittest.TestCase):
    """\u00a7S1 AC3 \u2014 no ``~/.claude`` or ``~/.omp`` path anywhere under
    ``pi-package/``."""

    def test_no_claude_or_omp_path_in_any_package_file(self):
        files = _package_files() if PI_PACKAGE.is_dir() else []
        names = {p.relative_to(PI_PACKAGE).as_posix() for p in files}
        # Not vacuous: the files the \u00a7S1 package must carry are scanned.
        self.assertTrue(
            {"package.json", "README.md"} <= names,
            f"pi-package/ must carry package.json and README.md to be scanned, got {sorted(names)}",
        )
        hits = []
        for path in files:
            text = path.read_text(encoding="utf-8", errors="replace")
            for n, line in enumerate(text.splitlines(), 1):
                if HARNESS_HOME_PATH.search(line):
                    hits.append(f"{path.relative_to(REPO_ROOT)}:{n}: {line.strip()}")
            if HARNESS_HOME_PATH.search(path.relative_to(PI_PACKAGE).as_posix()):
                hits.append(f"{path.relative_to(REPO_ROOT)}: the path itself")
        self.assertEqual(hits, [], "pi-package/ must name no .claude or .omp path")


class PiPackageReadmeTest(unittest.TestCase):
    """\u00a7S1 AC2 \u2014 ``pi-package/README.md`` is the guide's marked regions as
    ``build.py`` renders them; ``--check`` fails on a one-byte drift in
    either."""

    def test_readme_equals_the_guides_marked_regions_as_rendered(self):
        self.assertTrue(PI_README.is_file(), f"{PI_README_REL} must exist")
        expected = render_readme(GUIDE.read_text(encoding="utf-8"))
        self.assertEqual(
            PI_README.read_text(encoding="utf-8"), expected,
            f"{PI_README_REL} must be exactly the guide's marked regions (ruling D1)",
        )

    def test_list_names_the_readme_target_once(self):
        result = _run_build("--list")
        self.assertEqual(result.returncode, 0, result.stderr[:2000])
        listed = [Path(ln.strip()) for ln in result.stdout.splitlines() if ln.strip()]
        self.assertEqual(
            listed.count(PI_README), 1,
            f"build.py --list must print {PI_README} exactly once, got {[str(p) for p in listed]}",
        )

    def test_check_is_clean_when_readme_matches_the_guide(self):
        self.assertTrue(PI_README.is_file(), f"{PI_README_REL} must exist")
        result = _run_build("--check")
        self.assertEqual(result.returncode, 0, result.stdout[:2000] + result.stderr[:2000])
        self.assertNotIn(PI_README_REL, result.stdout)

    def _assert_check_names_readme_after(self, target: Path, at_of) -> None:
        original = target.read_bytes()
        try:
            target.write_bytes(_flip_byte(original, at_of(original)))
            self.assertEqual(
                len(target.read_bytes()), len(original), "precondition: a one-byte drift"
            )
            result = _run_build("--check")
        finally:
            target.write_bytes(original)
        self.assertEqual(target.read_bytes(), original, f"{target} must be restored")
        self.assertEqual(
            result.returncode, 1,
            f"build.py --check must exit 1 after a one-byte drift in {target.relative_to(REPO_ROOT)}, "
            f"got rc={result.returncode}\nstdout:\n{result.stdout[:2000]}",
        )
        drifted = result.stdout.split("drifted", 1)[-1].splitlines()
        self.assertIn(
            PI_README_REL, [ln.strip() for ln in drifted],
            f"--check must list {PI_README_REL} as drifted, got:\n{result.stdout[:2000]}",
        )

    def test_check_fails_naming_readme_on_a_one_byte_readme_drift(self):
        self.assertTrue(PI_README.is_file(), f"{PI_README_REL} must exist to be drifted")
        self._assert_check_names_readme_after(
            PI_README, lambda data: _first_letter(data))

    def test_check_fails_naming_readme_on_a_one_byte_guide_region_drift(self):
        regions, faults = parse_marked_regions(GUIDE.read_text(encoding="utf-8"))
        self.assertEqual(faults, [])
        _name, begin, end = regions[0]
        self._assert_check_names_readme_after(
            GUIDE, lambda data: _first_letter_between(data, begin, end))

    def test_check_stays_clean_on_a_one_byte_guide_drift_outside_every_region(self):
        # Regression pin (ruling D4): the README carries only the regions, so
        # the guide's title (line 1, outside every region) is not rendered.
        self.assertTrue(PI_README.is_file(), f"{PI_README_REL} must exist")
        original = GUIDE.read_bytes()
        regions, _faults = parse_marked_regions(original.decode("utf-8"))
        self.assertLess(0, regions[0][1], "precondition: line 1 sits outside every region")
        at = _first_letter(original.splitlines(keepends=True)[0])
        mutated = _flip_byte(original, at)
        self.assertEqual(
            render_readme(mutated.decode("utf-8")), render_readme(original.decode("utf-8")),
            "precondition: a correct renderer ignores the title",
        )
        try:
            GUIDE.write_bytes(mutated)
            result = _run_build("--check")
        finally:
            GUIDE.write_bytes(original)
        self.assertEqual(GUIDE.read_bytes(), original, f"{GUIDE} must be restored")
        self.assertEqual(
            result.returncode, 0,
            f"a byte outside every region must not drift the README, got:\n{result.stdout[:2000]}",
        )


class PiPackageOracleProofTest(unittest.TestCase):
    """The test-side oracles are right: the npm-semver mapping (ruling Q2) and
    the README rendering (ruling D1)."""

    def test_npm_semver_maps_every_pep440_form(self):
        table = (
            ("1.0.0", "1.0.0"),
            ("0.1.0.dev0", "0.1.0-dev.0"),
            ("1.2.3.dev12", "1.2.3-dev.12"),
            ("1.0.0a1", "1.0.0-alpha.1"),
            ("1.0.0b2", "1.0.0-beta.2"),
            ("1.0.0rc3", "1.0.0-rc.3"),
        )
        for pep440, semver in table:
            with self.subTest(pep440=pep440):
                self.assertEqual(npm_semver(pep440), semver)
                self.assertRegex(npm_semver(pep440), SEMVER_RE)

    def test_npm_semver_refuses_a_version_outside_the_ruling(self):
        for bad in ("1.0", "1.0.0.post1", "1.0.0-dev.0", "v1.0.0"):
            with self.subTest(version=bad), self.assertRaises(ValueError) as ctx:
                npm_semver(bad)
            self.assertIn(repr(bad), str(ctx.exception))

    def test_semver_grammar_rejects_the_raw_pep440_dev_version(self):
        self.assertIsNone(SEMVER_RE.match("0.1.0.dev0"))
        self.assertIsNotNone(SEMVER_RE.match("0.1.0-dev.0"))

    def test_render_readme_joins_trimmed_region_bodies_with_one_blank_line(self):
        guide = (
            "# Title\n\nintro\n"
            "<!-- install-guide:begin one -->\n\n## One\n\nbody one\n\n"
            "<!-- install-guide:end one -->\n\nbetween\n\n"
            "<!-- install-guide:begin two -->\n## Two\n```\n<!-- install-guide:end two -->\n```\n"
            "<!-- install-guide:end two -->\n\n## Marked regions\n\noutside\n"
        )
        self.assertEqual(
            render_readme(guide),
            "## One\n\nbody one\n\n## Two\n```\n<!-- install-guide:end two -->\n```\n",
        )

    def test_render_readme_refuses_malformed_regions(self):
        with self.assertRaises(AssertionError) as ctx:
            render_readme("<!-- install-guide:begin one -->\nx\n")
        self.assertIn("never ended", str(ctx.exception))


#: The module, its fixture and every test CR-MDB-047 retired with the Model B
#: watcher ("Removed", amended at 5dd8a36 for VERIFY F2) — read from
#: ``git show ddd69f7^:tests/test_pi_sandesh_watcher.py``, the commit that
#: deleted them: 25 test methods under three classes, on the base case
#: ``SandeshWatcherTestCase``, driven through the fixture harness.
RETIRED_WATCHER_MODULE = "tests/test_pi_sandesh_watcher.py"
RETIRED_WATCHER_FIXTURE = "tests/fixtures/pi_watcher_harness.mjs"
RETIRED_WATCHER_TESTS = (
    "SandeshWatcherRegistrationTest.test_factory_registers_the_sandesh_watcher_tool_and_the_watcher_command",
    "SandeshWatcherRegistrationTest.test_tool_schema_declares_start_status_stop_and_address_project",
    "SandeshWatcherStartTest.test_start_spawns_sandesh_notify_with_exactly_to_and_project",
    "SandeshWatcherStartTest.test_start_spawns_the_child_with_pythonunbuffered_so_the_banner_is_not_held",
    "SandeshWatcherStartTest.test_start_reports_ready_naming_the_address_only_after_the_banner",
    "SandeshWatcherStartTest.test_start_does_not_hang_when_the_child_exits_without_a_banner",
    "SandeshWatcherStartTest.test_start_while_one_runs_reports_it_and_spawns_nothing",
    "SandeshWatcherStartTest.test_stop_tool_terminates_the_child",
    "SandeshWatcherStartTest.test_watcher_stop_command_terminates_the_child",
    "SandeshWatcherStartTest.test_status_tool_names_the_running_address",
    "SandeshWatcherStartTest.test_watcher_status_command_names_the_running_address",
    "SandeshWatcherExitTest.test_exit_0_wakes_once_naming_the_ids_and_quoted_fetch_and_relaunches_at_once",
    "SandeshWatcherExitTest.test_exit_0_again_with_the_same_ids_does_not_wake_and_retries_every_30s",
    "SandeshWatcherExitTest.test_status_during_a_retry_does_not_name_the_dead_childs_pid",
    "SandeshWatcherExitTest.test_exit_0_without_ids_wakes_again_after_a_relaunch_reports_no_mail",
    "SandeshWatcherExitTest.test_exit_0_with_the_same_ids_wakes_again_after_a_relaunch_reports_no_mail",
    "SandeshWatcherExitTest.test_exit_0_with_new_ids_wakes_again",
    "SandeshWatcherExitTest.test_exit_2_relaunches_once_silently",
    "SandeshWatcherExitTest.test_three_exit_2_within_a_minute_surface_and_stop_relaunching",
    "SandeshWatcherExitTest.test_exit_2_spread_over_more_than_a_minute_keeps_relaunching_silently",
    "SandeshWatcherExitTest.test_exit_1_surfaces_usage_or_configuration_error_without_relaunch",
    "SandeshWatcherExitTest.test_exit_3_surfaces_tombstoned_project_without_relaunch",
    "SandeshWatcherExitTest.test_exit_4_surfaces_eviction_without_relaunch",
    "SandeshWatcherExitTest.test_exit_5_surfaces_already_live_dedup_without_relaunch",
    "SandeshWatcherExitTest.test_signal_exit_surfaces_the_signal_without_relaunch",
)


class RetiredWatcherTestsAreListedTest(unittest.TestCase):
    """AC "The Pi package": the tests of the removed extension are retired,
    and each is listed by id in this module's docstring."""

    def setUp(self):
        self.doc = sys.modules[__name__].__doc__ or ""

    def test_the_retired_module_and_fixture_are_gone(self):
        for rel in (RETIRED_WATCHER_MODULE, RETIRED_WATCHER_FIXTURE):
            with self.subTest(path=rel):
                self.assertFalse((REPO_ROOT / rel).exists(), f"{rel} is retired")

    def test_the_docstring_names_the_retired_module_and_its_fixture(self):
        for rel in (RETIRED_WATCHER_MODULE, RETIRED_WATCHER_FIXTURE, "SandeshWatcherTestCase"):
            with self.subTest(name=rel):
                self.assertIn(rel, self.doc, f"the module docstring lists {rel}")

    def test_the_docstring_lists_every_retired_test_by_id(self):
        self.assertEqual(len(RETIRED_WATCHER_TESTS), 25)
        missing = [t for t in RETIRED_WATCHER_TESTS
                   if f"tests.test_pi_sandesh_watcher.{t}" not in self.doc]
        self.assertEqual(missing, [], "each retired test is listed by its full id "
                                      "(tests.test_pi_sandesh_watcher.<Class>.<method>)")


if __name__ == "__main__":
    unittest.main()
