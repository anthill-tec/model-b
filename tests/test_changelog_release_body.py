"""Model B's ``CHANGELOG.md``, its form checker, and the GitHub Release body (CR-MDB-058 §S1, §S2).

Contract: ``docs/changes/CR-MDB-058-release-notes-and-rehearsal.md``; rulings in
``docs/research/release-automation-crucible-procedure.md`` § "What Model B adopted (2026-10-14 …)".

Class map:

- ``ChangelogFormCheckerProofTest`` — §S1: the form checker (``changelog_form_faults``, one copy in
  ``tests/_helpers.py``, reused by §S5) passes the starting form and a released file, and bites
  once per rule broken on sample text.
- ``ModelBChangelogTest`` — §S1: the real ``CHANGELOG.md`` exists, opens with ``# Changelog`` and
  passes the checker.
- ``ChangelogSectionScriptTest`` — §S2: ``.github/scripts/changelog_section.py``, loaded by path
  (``importlib.util.spec_from_file_location``, run as ``__main__`` with its argv) and run as the CLI
  the workflow uses (``python3 <script> <changelog> <tag>``), prints the tag's section body or
  exits 1 naming the tag on stderr, on every sample case the AC lists.
- ``ChangelogSectionScriptSourceTest`` — §S2: the script is stdlib only and parses under
  ``ast.parse(..., feature_version=(3, 12))``.
- ``ChangelogSectionScriptNotShippedTest`` — §S2: the script is in neither the sdist nor the wheel,
  read from REAL artifacts built by ``tests.test_package_publishing``'s fixture.
- ``CreateReleaseNotesStepTest`` — §S2: ``release.yml``'s ``create-release`` step, read as text,
  writes the tag's section to a file before the "release already exists" guard and passes that
  file as ``--notes-file``; the extracted command line is EXECUTED in a temp dir.

The script's body is compared trimmed: its output is the body, with at most one trailing newline.

Stdlib only.
"""

import ast
import contextlib
import importlib.util
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from tests import test_package_publishing as publishing
from tests._helpers import changelog_form_faults, workflow_job

REPO_ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
SCRIPT_REL = ".github/scripts/changelog_section.py"
SCRIPT = REPO_ROOT / ".github" / "scripts" / "changelog_section.py"
RELEASE_YML = REPO_ROOT / ".github" / "workflows" / "release.yml"

PREAMBLE = (
    "# Changelog\n"
    "\n"
    "All notable changes to this project are documented in this file. The format is based on\n"
    "[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to\n"
    "[Semantic Versioning](https://semver.org/spec/v2.0.0.html).\n"
    "\n"
)

#: §S1's starting form: title, sentence, an empty ``[Unreleased]``, no release, no compare link.
STARTING_FORM = PREAMBLE + "## [Unreleased]\n"

#: A file in form after three releases.
RELEASED_FORM = PREAMBLE + (
    "## [Unreleased]\n"
    "\n"
    "### Added\n"
    "\n"
    "- Work not yet released.\n"
    "\n"
    "## [1.1.0] - 2026-12-01\n"
    "\n"
    "### Upgrading\n"
    "\n"
    "Reinstall the package, then run the installer again.\n"
    "\n"
    "### Changed\n"
    "\n"
    "- A changed thing.\n"
    "\n"
    "### Fixed\n"
    "\n"
    "- A fixed thing.\n"
    "\n"
    "## [1.0.1] - 2026-11-01\n"
    "\n"
    "### Security\n"
    "\n"
    "- A security fix.\n"
    "\n"
    "## [1.0.0] - 2026-10-20\n"
    "\n"
    "### Added\n"
    "\n"
    "- The first release.\n"
    "\n"
    "### Deprecated\n"
    "\n"
    "- A deprecated thing.\n"
    "\n"
    "### Removed\n"
    "\n"
    "- A removed thing.\n"
    "\n"
    "[Unreleased]: https://example.invalid/compare/1.1.0...HEAD\n"
    "[1.1.0]: https://example.invalid/compare/1.0.1...1.1.0\n"
    "[1.0.1]: https://example.invalid/compare/1.0.0...1.0.1\n"
    "[1.0.0]: https://example.invalid/releases/tag/1.0.0\n"
)

# ------------------------------------------------------------------ §S2 samples ----

#: Newest first; ``1.0.10`` above ``1.0.1``; compare links at the foot.
SAMPLE_WITH_LINKS = PREAMBLE + (
    "## [Unreleased]\n"
    "\n"
    "### Added\n"
    "\n"
    "- Work not yet released.\n"
    "\n"
    "## [1.0.10] - 2026-12-01\n"
    "\n"
    "### Fixed\n"
    "\n"
    "- The tenth patch.\n"
    "\n"
    "## [1.0.1] - 2026-11-01\n"
    "\n"
    "### Fixed\n"
    "\n"
    "- The first patch — its dash survives.\n"
    "\n"
    "## [1.0.0] - 2026-10-20\n"
    "\n"
    "### Upgrading\n"
    "\n"
    "Reinstall the package.\n"
    "\n"
    "### Added\n"
    "\n"
    "- The first release.\n"
    "\n"
    "## [1.0.0-rc1] - 2026-10-15\n"
    "\n"
    "### Added\n"
    "\n"
    "- The release candidate.\n"
    "\n"
    "[Unreleased]: https://example.invalid/compare/1.0.10...HEAD\n"
    "[1.0.10]: https://example.invalid/compare/1.0.1...1.0.10\n"
    "[1.0.1]: https://example.invalid/compare/1.0.0...1.0.1\n"
    "[1.0.0]: https://example.invalid/compare/1.0.0-rc1...1.0.0\n"
    "[1.0.0-rc1]: https://example.invalid/releases/tag/1.0.0-rc1\n"
)

#: ``1.0.0-rc1`` ABOVE ``1.0.0`` and ``1.0.1`` above ``1.0.10``, so a prefix match finds the wrong
#: section first; the last section runs to the end of the file (no compare links, trailing blanks).
SAMPLE_PREFIXES_FIRST = PREAMBLE + (
    "## [Unreleased]\n"
    "\n"
    "## [1.0.0-rc1] - 2026-10-15\n"
    "\n"
    "### Added\n"
    "\n"
    "- The release candidate.\n"
    "\n"
    "## [1.0.1] - 2026-11-01\n"
    "\n"
    "### Fixed\n"
    "\n"
    "- The first patch.\n"
    "\n"
    "## [1.0.10] - 2026-12-01\n"
    "\n"
    "### Fixed\n"
    "\n"
    "- The tenth patch.\n"
    "\n"
    "## [1.0.0] - 2026-10-20\n"
    "\n"
    "### Added\n"
    "\n"
    "- The final release, last in the file.\n"
    "\n"
    "\n"
)

#: An empty section, a ``###``-headings-only section, a good one, and an empty last section
#: before the compare links.
SAMPLE_EMPTY = PREAMBLE + (
    "## [Unreleased]\n"
    "\n"
    "## [1.3.0] - 2026-12-20\n"
    "\n"
    "\n"
    "## [1.2.0] - 2026-12-10\n"
    "\n"
    "### Added\n"
    "\n"
    "### Fixed\n"
    "   \n"
    "\n"
    "## [1.1.0] - 2026-12-01\n"
    "\n"
    "### Changed\n"
    "\n"
    "- A real entry.\n"
    "\n"
    "## [1.0.0] - 2026-10-20\n"
    "\n"
    "[Unreleased]: https://example.invalid/compare/1.3.0...HEAD\n"
    "[1.0.0]: https://example.invalid/releases/tag/1.0.0\n"
)

#: §S2's empty rule is "nothing but whitespace and ``###`` headings": a group heading is a line
#: matching ``^###(\s|$)`` — a bare ``###`` and a ``###`` followed by spaces only are headings, so a
#: body of them is empty; a ``#### Deep`` line is a level-4 heading, not a group heading, so it is
#: content and its section is printed.
SAMPLE_BARE_HEADINGS = PREAMBLE + (
    "## [Unreleased]\n"
    "\n"
    "## [2.2.0] - 2026-12-30\n"
    "\n"
    "###\n"
    "\n"
    "## [2.1.0] - 2026-12-25\n"
    "\n"
    "###   \n"
    "\n"
    "### Fixed\n"
    "\n"
    "## [2.0.1] - 2026-12-22\n"
    "\n"
    "### Added\n"
    "\n"
    "###\n"
    "\n"
    "## [2.0.0] - 2026-12-20\n"
    "\n"
    "### Added\n"
    "\n"
    "#### Deep\n"
    "\n"
    "[Unreleased]: https://example.invalid/compare/2.2.0...HEAD\n"
    "[2.0.0]: https://example.invalid/releases/tag/2.0.0\n"
)

#: (case, sample, tag, expected body) — the script prints the body and exits 0.
FOUND_CASES = (
    ("a middle section", SAMPLE_WITH_LINKS, "1.0.0",
     "### Upgrading\n\nReinstall the package.\n\n### Added\n\n- The first release."),
    ("1.0.1 beside 1.0.10 (1.0.10 above it)", SAMPLE_WITH_LINKS, "1.0.1",
     "### Fixed\n\n- The first patch — its dash survives."),
    ("1.0.10 beside 1.0.1", SAMPLE_WITH_LINKS, "1.0.10",
     "### Fixed\n\n- The tenth patch."),
    ("the last section before the compare links; a tag 1.0.0-rc1", SAMPLE_WITH_LINKS, "1.0.0-rc1",
     "### Added\n\n- The release candidate."),
    ("1.0.0 beside 1.0.0-rc1 (rc1 above it); the last section at end of file, no links",
     SAMPLE_PREFIXES_FIRST, "1.0.0",
     "### Added\n\n- The final release, last in the file."),
    ("a tag 1.0.0-rc1 with 1.0.0 below it", SAMPLE_PREFIXES_FIRST, "1.0.0-rc1",
     "### Added\n\n- The release candidate."),
    ("1.0.1 beside 1.0.10 (1.0.10 below it)", SAMPLE_PREFIXES_FIRST, "1.0.1",
     "### Fixed\n\n- The first patch."),
    ("a good section between empty ones", SAMPLE_EMPTY, "1.1.0",
     "### Changed\n\n- A real entry."),
    ("a #### line is content, not a ### group heading", SAMPLE_BARE_HEADINGS, "2.0.0",
     "### Added\n\n#### Deep"),
)

#: (case, sample, tag) — the script exits 1 naming the tag on stderr.
REFUSED_CASES = (
    ("a missing tag", SAMPLE_WITH_LINKS, "2.0.0"),
    ("a tag that is only a prefix of real labels", SAMPLE_WITH_LINKS, "1.0"),
    ("a tag that is a prefix of a prerelease label", SAMPLE_WITH_LINKS, "1.0.0-rc"),
    ("an empty section", SAMPLE_EMPTY, "1.3.0"),
    ("a section holding only ### headings", SAMPLE_EMPTY, "1.2.0"),
    ("an empty last section before the compare links", SAMPLE_EMPTY, "1.0.0"),
    ("a section holding only a bare ### line", SAMPLE_BARE_HEADINGS, "2.2.0"),
    ("a section holding a ### line with trailing spaces only and a ### heading",
     SAMPLE_BARE_HEADINGS, "2.1.0"),
    ("a section holding a ### heading then a bare ### line", SAMPLE_BARE_HEADINGS, "2.0.1"),
)


def _require_script() -> None:
    if not SCRIPT.is_file():
        raise AssertionError(f"§S2: {SCRIPT_REL} must exist")


def run_section_script_by_path(changelog: Path, tag: str) -> tuple[int, str, str]:
    """Load the script by path and run it as ``__main__`` with ``argv = [script, changelog, tag]``.

    Returns ``(exit code, stdout, stderr)`` as the interpreter would: ``SystemExit(None)`` is 0, an
    int is itself, anything else is written to stderr and is 1."""
    _require_script()
    spec = importlib.util.spec_from_file_location("__main__", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError(f"§S2: {SCRIPT_REL} cannot be loaded by path")
    loader = spec.loader
    module = importlib.util.module_from_spec(spec)
    out_bytes, err_bytes = io.BytesIO(), io.BytesIO()
    out = io.TextIOWrapper(out_bytes, encoding="utf-8", newline="")
    err = io.TextIOWrapper(err_bytes, encoding="utf-8", newline="")
    saved_argv = sys.argv
    sys.argv = [str(SCRIPT), str(changelog), tag]
    code = 0
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                loader.exec_module(module)
            except SystemExit as exc:
                if exc.code is None:
                    code = 0
                elif isinstance(exc.code, int):
                    code = exc.code
                else:
                    print(exc.code, file=err)
                    code = 1
    finally:
        sys.argv = saved_argv
    out.flush()
    err.flush()
    return code, out_bytes.getvalue().decode("utf-8"), err_bytes.getvalue().decode("utf-8")


def run_section_script_cli(changelog: Path, tag: str) -> tuple[int, str, str]:
    """``python3 .github/scripts/changelog_section.py <changelog> <tag>`` — §S2's calling form."""
    _require_script()
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(changelog), tag],
        capture_output=True, text=True, encoding="utf-8", timeout=30, stdin=subprocess.DEVNULL,
    )
    return result.returncode, result.stdout, result.stderr


RUNNERS = (("loaded by path", run_section_script_by_path), ("the CLI", run_section_script_cli))


def _is_trimmed_body(output: str, expected: str) -> bool:
    return output in (expected, expected + "\n")


# ------------------------------------------------------------------ §S1 checker ----

class ChangelogFormCheckerProofTest(unittest.TestCase):
    """§S1 — the checker in both directions: in form passes, each rule broken once bites."""

    def assertOneFault(self, text: str, needle: str):
        faults = changelog_form_faults(text)
        self.assertEqual(len(faults), 1, f"expected exactly one fault naming {needle!r}; got {faults}")
        self.assertIn(needle, faults[0])

    def test_the_starting_form_is_in_form(self):
        self.assertEqual(changelog_form_faults(STARTING_FORM), [])

    def test_a_released_file_with_upgrading_first_and_compare_links_is_in_form(self):
        self.assertEqual(changelog_form_faults(RELEASED_FORM), [])

    def test_a_missing_keep_a_changelog_link_bites(self):
        self.assertOneFault(STARTING_FORM.replace("https://keepachangelog.com/en/1.1.0/",
                                                  "https://keepachangelog.com/en/1.0.0/"),
                            "https://keepachangelog.com/en/1.1.0/")

    def test_a_missing_semver_link_bites(self):
        self.assertOneFault(STARTING_FORM.replace("https://semver.org/spec/v2.0.0.html",
                                                  "https://semver.org/"),
                            "https://semver.org/spec/v2.0.0.html")

    def test_a_file_with_no_unreleased_section_bites(self):
        self.assertOneFault(PREAMBLE, "## [Unreleased]")

    def test_a_release_section_before_unreleased_bites(self):
        text = STARTING_FORM.replace(
            "## [Unreleased]\n",
            "## [1.0.0] - 2026-10-20\n\n### Added\n\n- The first release.\n\n## [Unreleased]\n")
        faults = changelog_form_faults(text)
        # The misplaced [Unreleased] also fails the release-heading form: two faults, no more.
        self.assertEqual(len(faults), 2, faults)
        self.assertIn("first ## heading is not '## [Unreleased]'", faults[0])
        self.assertIn("'## [Unreleased]'", faults[1])

    def test_a_release_heading_without_a_date_bites(self):
        self.assertOneFault(RELEASED_FORM.replace("## [1.0.1] - 2026-11-01", "## [1.0.1]"),
                            "'## [1.0.1]'")

    def test_a_release_heading_with_a_v_prefix_bites(self):
        self.assertOneFault(RELEASED_FORM.replace("## [1.0.1] - 2026-11-01", "## [v1.0.1] - 2026-11-01"),
                            "X.Y.Z")

    def test_a_release_heading_with_an_unpadded_date_bites(self):
        self.assertOneFault(RELEASED_FORM.replace("## [1.0.1] - 2026-11-01", "## [1.0.1] - 2026-11-1"),
                            "YYYY-MM-DD")

    def test_versions_out_of_order_bite(self):
        text = RELEASED_FORM.replace("## [1.0.1] - 2026-11-01", "## [1.2.0] - 2026-11-01")
        self.assertOneFault(text, "not descending")

    def test_a_repeated_version_bites(self):
        text = RELEASED_FORM.replace("## [1.0.1] - 2026-11-01", "## [1.0.0] - 2026-11-01")
        self.assertOneFault(text, "not descending")

    def test_a_version_compared_as_text_not_number_is_still_descending(self):
        # 1.0.10 is newer than 1.0.9: a text comparison would call this order ascending.
        text = RELEASED_FORM.replace("## [1.1.0] - 2026-12-01", "## [1.0.10] - 2026-12-01").replace(
            "## [1.0.1] - 2026-11-01", "## [1.0.9] - 2026-11-01")
        self.assertEqual(changelog_form_faults(text), [])

    def test_a_group_heading_outside_the_six_names_and_upgrading_bites(self):
        self.assertOneFault(RELEASED_FORM.replace("### Security", "### Notes"), "### Notes")

    def test_upgrading_not_first_in_its_section_bites(self):
        text = RELEASED_FORM.replace(
            "### Upgrading\n\nReinstall the package, then run the installer again.\n\n"
            "### Changed\n\n- A changed thing.\n",
            "### Changed\n\n- A changed thing.\n\n"
            "### Upgrading\n\nReinstall the package, then run the installer again.\n")
        self.assertOneFault(text, "### Upgrading")

    def test_an_empty_group_heading_between_groups_bites(self):
        self.assertOneFault(RELEASED_FORM.replace("- A changed thing.\n", ""), "### Changed")

    def test_an_empty_group_heading_before_the_compare_links_bites(self):
        self.assertOneFault(RELEASED_FORM.replace("- A removed thing.\n", ""), "### Removed")


class ModelBChangelogTest(unittest.TestCase):
    """§S1 — the real ``CHANGELOG.md``."""

    def test_the_repository_changelog_opens_with_its_title_and_is_in_form(self):
        self.assertTrue(CHANGELOG.is_file(), "§S1: CHANGELOG.md must exist at the repository root")
        text = CHANGELOG.read_text(encoding="utf-8")
        self.assertEqual(text.splitlines()[0], "# Changelog")
        self.assertEqual(changelog_form_faults(text), [])


# ------------------------------------------------------------------ §S2 the script ----

class ChangelogSectionScriptTest(unittest.TestCase):
    """§S2 — every sample case of the AC, loaded by path and through the CLI."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="changelog-section-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _write(self, text: str) -> Path:
        path = self.tmp / "CHANGELOG.md"
        path.write_text(text, encoding="utf-8")
        return path

    def test_prints_the_tags_section_body_on_every_found_case(self):
        for case, sample, tag, expected in FOUND_CASES:
            changelog = self._write(sample)
            for how, run in RUNNERS:
                with self.subTest(case=case, tag=tag, run=how):
                    code, out, err = run(changelog, tag)
                    self.assertEqual(code, 0, f"stderr={err!r}")
                    self.assertTrue(_is_trimmed_body(out, expected),
                                    f"expected the body {expected!r}; got {out!r}")

    def test_exits_1_naming_the_tag_on_stderr_on_every_refused_case(self):
        for case, sample, tag in REFUSED_CASES:
            changelog = self._write(sample)
            for how, run in RUNNERS:
                with self.subTest(case=case, tag=tag, run=how):
                    code, out, err = run(changelog, tag)
                    self.assertEqual(code, 1, f"stdout={out!r} stderr={err!r}")
                    self.assertIn(tag, err)

    def test_a_missing_changelog_exits_1_naming_the_path_and_the_tag_without_a_traceback(self):
        missing = self.tmp / "absent" / "CHANGELOG.md"
        code, out, err = run_section_script_cli(missing, "1.0.0")
        self.assertEqual(code, 1, f"stdout={out!r} stderr={err!r}")
        self.assertEqual(out, "", "nothing is printed for a missing changelog")
        self.assertNotIn("Traceback", err, "a missing changelog is reported, not raised")
        self.assertIn(str(missing), err, "stderr names the changelog path")
        self.assertIn("1.0.0", err, "stderr names the tag")

    def test_a_section_body_never_carries_the_next_heading_or_a_compare_link(self):
        changelog = self._write(SAMPLE_WITH_LINKS)
        code, out, err = run_section_script_cli(changelog, "1.0.0-rc1")
        self.assertEqual(code, 0, f"stderr={err!r}")
        self.assertNotIn("]: https://", out)
        self.assertNotIn("## ", out.replace("### ", ""))


class ChangelogSectionScriptSourceTest(unittest.TestCase):
    """§S2 — stdlib only, and no syntax newer than Python 3.12 (the hosted runner's default)."""

    def test_the_script_parses_as_python_3_12(self):
        _require_script()
        source = SCRIPT.read_text(encoding="utf-8")
        ast.parse(source, filename=SCRIPT_REL, feature_version=(3, 12))

    def test_the_script_imports_the_standard_library_only(self):
        _require_script()
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0, "§S2: the script imports nothing relative")
                imported.add((node.module or "").split(".")[0])
        self.assertEqual(sorted(imported - sys.stdlib_module_names), [])


def tearDownModule():
    # The artifacts are tests.test_package_publishing's, cached on that module: remove the build
    # and drop the cache, so that module rebuilds rather than reading a removed directory.
    publishing.tearDownModule()
    publishing._BUILD_ROOT = None


class ChangelogSectionScriptNotShippedTest(unittest.TestCase):
    """§S2 — a repo-only script: neither the sdist nor the wheel carries it."""

    def test_neither_the_sdist_nor_the_wheel_carries_the_script(self):
        _require_script()  # otherwise "not shipped" would hold of nothing
        sdist, wheel = publishing.artifacts()
        offenders = [f"sdist:{rel}" for rel in publishing.sdist_members(sdist)
                     if rel.startswith(".github/") or rel.endswith("changelog_section.py")]
        offenders += [f"wheel:{name}" for name in publishing.wheel_names(wheel)
                      if ".github" in name.split("/") or name.endswith("changelog_section.py")]
        self.assertEqual(offenders, [])


# ------------------------------------------------------------------ §S2 the workflow ----

_NOTES_LINE = re.compile(
    r'python3\s+\.github/scripts/changelog_section\.py\s+CHANGELOG\.md\s+"\$TAG"\s*>\s*(\S+)')
_CREATE_LINE = re.compile(r'gh release create "\$TAG" --notes-file (\S+) --verify-tag')


def run_blocks(job: list[str]) -> list[list[str]]:
    """Every ``run: |`` block of a job, dedented, one list of lines per block."""
    blocks = []
    i = 0
    while i < len(job):
        match = re.match(r"(\s*)(?:- )?run: \|\s*$", job[i])
        if match:
            indent = len(job[i]) - len(job[i].lstrip())
            body = []
            i += 1
            while i < len(job) and (not job[i].strip()
                                    or len(job[i]) - len(job[i].lstrip()) > indent):
                body.append(job[i])
                i += 1
            blocks.append(textwrap.dedent("\n".join(body)).splitlines())
            continue
        i += 1
    return blocks


class CreateReleaseNotesStepTest(unittest.TestCase):
    """§S2 — ``create-release`` extracts the tag's section into a file, before the guard, and
    creates the release from that file."""

    @classmethod
    def setUpClass(cls):
        # The job reader is shared with CR-MDB-058 §S4's publish-npm gate (tests/_helpers.py,
        # hoisted at C2 RED from this module's create_release_job).
        cls.job = workflow_job(RELEASE_YML.read_text(encoding="utf-8"), "create-release")
        cls.blocks = [b for b in run_blocks(cls.job) if any("gh release create" in line for line in b)]

    def _block(self) -> list[str]:
        self.assertEqual(len(self.blocks), 1,
                         "exactly one create-release run block creates the release")
        return self.blocks[0]

    def _notes_line(self) -> tuple[int, str, str]:
        block = self._block()
        hits = [(i, line.strip()) for i, line in enumerate(block) if SCRIPT_REL in line]
        self.assertEqual(len(hits), 1,
                         f"§S2: one command line runs {SCRIPT_REL}; found {[h for _, h in hits]}")
        index, line = hits[0]
        match = _NOTES_LINE.fullmatch(line)
        if match is None:
            self.fail(f'§S2: the line runs the script on CHANGELOG.md and "$TAG" into a file; '
                      f"got {line!r}")
        return index, line, match.group(1)

    def test_the_notes_line_runs_the_script_on_changelog_and_tag_into_a_file(self):
        self._notes_line()

    def test_the_notes_line_runs_before_the_release_already_exists_guard(self):
        index, _line, _target = self._notes_line()
        guards = [i for i, line in enumerate(self._block()) if 'gh release view "$TAG"' in line]
        self.assertEqual(len(guards), 1, "the 'release already exists' guard stays")
        self.assertLess(index, guards[0], "§S2: the section is extracted every time, before the guard")

    def test_the_release_is_created_from_that_file_with_verify_tag(self):
        _index, _line, target = self._notes_line()
        creates = [line.strip() for line in self._block() if "gh release create" in line]
        self.assertEqual(len(creates), 1)
        match = _CREATE_LINE.fullmatch(creates[0])
        if match is None:
            self.fail(f'§S2: gh release create "$TAG" --notes-file <file> --verify-tag; '
                      f"got {creates[0]!r}")
        self.assertEqual(match.group(1), target, "§S2: --notes-file names the file the script wrote")

    def test_the_job_no_longer_generates_notes(self):
        self.assertNotIn("--generate-notes", "\n".join(self.job))

    def _execute(self, tag: str) -> tuple[subprocess.CompletedProcess, Path]:
        _index, line, target = self._notes_line()
        _require_script()
        work = Path(tempfile.mkdtemp(prefix="create-release-"))
        self.addCleanup(shutil.rmtree, work, True)
        (work / ".github" / "scripts").mkdir(parents=True)
        shutil.copy2(SCRIPT, work / SCRIPT_REL)
        (work / "CHANGELOG.md").write_text(SAMPLE_WITH_LINKS, encoding="utf-8")
        (work / "runner-temp").mkdir()
        (work / "home").mkdir()
        env = dict(os.environ, TAG=tag, RUNNER_TEMP=str(work / "runner-temp"),
                   GITHUB_WORKSPACE=str(work), HOME=str(work / "home"))
        # The `shell: bash` form (`bash --noprofile --norc -eo pipefail`), stricter than the
        # default `bash -e` of a step without `shell:`; the trailing printf reports where the
        # line wrote.
        result = subprocess.run(
            ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c",
             f"{line}\nprintf '%s' {target}\n"],
            cwd=work, env=env, capture_output=True, text=True, encoding="utf-8", timeout=30,
            stdin=subprocess.DEVNULL,
        )
        written = Path(result.stdout) if result.stdout else Path()
        return result, written if written.is_absolute() else work / written

    def test_the_extracted_line_writes_the_tags_body_to_the_notes_file(self):
        result, written = self._execute("1.0.1")
        self.assertEqual(result.returncode, 0, f"stderr={result.stderr!r}")
        self.assertTrue(written.is_file(), f"the notes file {written} must be written")
        body = written.read_text(encoding="utf-8")
        expected = "### Fixed\n\n- The first patch — its dash survives."
        self.assertTrue(_is_trimmed_body(body, expected), f"expected {expected!r}; got {body!r}")

    def test_the_extracted_line_fails_the_step_when_the_tag_has_no_section(self):
        result, _written = self._execute("9.9.9")
        self.assertNotEqual(result.returncode, 0, "§S2: a missing section fails the step")
        self.assertIn("9.9.9", result.stderr)


if __name__ == "__main__":
    unittest.main()
