"""The Cargo workspace manifest, as both rust health scanners read it (CR-MDB-078 §S1.3, §S1.4,
§S2.4 — AC2, AC3).

``scripts/rust-crate-map.py`` and ``scripts/rust-dead-scan.py`` each keep their own manifest
reading (§S1.6), and both resolve the same member set from the same manifest:

- ``WorkspaceMembersTest`` — AC2: the root manifest is TOML. ``members`` holds paths and glob
  patterns, ``exclude`` removes entries, ``default-members`` does not change the set, a
  commented-out ``members`` line is not read, and a root ``[package]`` makes the root package a
  member. Both tools exit 0 and report exactly ``root``, ``alpha`` and ``beta``.
- ``CrateMapMalformedWorkspaceTest`` / ``DeadScanMalformedWorkspaceTest`` — AC3: each §S1.4 case,
  a glob matching a directory with no ``Cargo.toml`` included, is refused. The tool exits
  non-zero, writes a stderr line starting ``error:`` that names the file or key, and prints no
  ``Traceback``.

Every tool run is a subprocess of the test interpreter under ``tests/_helpers.py``'s
``run_tool``: the test process's environment with only ``PATH`` and git's configuration
variables changed, a ``PATH`` holding links to ``git`` and ``tar`` alone (no ``cargo``,
``cargo-machete`` or ``dot``), a temp directory as the working directory and ``--project-dir``
/ ``--out`` pinned to temp directories (§S4, AC15).

Stdlib only.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests._helpers import (
    cargo_member_manifest,
    git_repo,
    repo_git,
    run_tool,
    tool_bin_dir,
    write_files,
)

CRATE_MAP = "rust-crate-map.py"
DEAD_SCAN = "rust-dead-scan.py"

#: A dead-code site in a crate's library, so the dead-scan inventory names the crate it scanned.
DEAD_SITE_LIB = "#[allow(dead_code)]\nfn unused_helper() {}\n"


#: AC2's root manifest: a root package, ``default-members`` on a line before ``members``, a
#: commented-out ``members`` line, a glob ``members`` and an ``exclude``.
AC2_ROOT_MANIFEST = (
    cargo_member_manifest("root")
    + "\n[workspace]\n"
    + 'default-members = ["crates/alpha"]\n'
    + '# members = ["crates/alpha", "crates/beta", "crates/skip"]\n'
    + 'members = ["crates/*"]\n'
    + 'exclude = ["crates/skip"]\n'
)

#: AC2's tree: the root package and ``crates/alpha``, ``crates/beta`` and ``crates/skip``, each
#: with a ``Cargo.toml`` and one dead-code site.
AC2_WORKSPACE = {
    "Cargo.toml": AC2_ROOT_MANIFEST,
    "src/lib.rs": DEAD_SITE_LIB,
    "crates/alpha/Cargo.toml": cargo_member_manifest("alpha"),
    "crates/alpha/src/lib.rs": DEAD_SITE_LIB,
    "crates/beta/Cargo.toml": cargo_member_manifest("beta"),
    "crates/beta/src/lib.rs": DEAD_SITE_LIB,
    "crates/skip/Cargo.toml": cargo_member_manifest("skip"),
    "crates/skip/src/lib.rs": DEAD_SITE_LIB,
}

#: The packages AC2's workspace has, and no other.
AC2_PACKAGES = ["alpha", "beta", "root"]


def _tool_args(script: str, project: Path, out: Path) -> list:
    """The pinned arguments of a run: the crate map skips its render (no ``dot`` is on ``PATH``);
    the dead-scan runs its default modes."""
    args = ["--project-dir", project, "--out", out]
    return args + ["--no-render"] if script == CRATE_MAP else args


class _ToolRunCase(unittest.TestCase):
    """A temp work area: a ``PATH`` directory of ``git`` and ``tar`` links, a project directory,
    an output directory and a working directory, all removed afterwards (§S4.2, §S4.4)."""

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="mdb-rust-manifest-"))
        self.addCleanup(shutil.rmtree, self.work, True)
        self.bin_dir = tool_bin_dir(self.work / "bin")
        self.project = self.work / "proj"
        self.out = self.work / "out"
        self.cwd = self.work / "cwd"
        self.cwd.mkdir()

    def run_scanner(self, script: str):
        return run_tool(script, *_tool_args(script, self.project, self.out),
                        bin_dir=self.bin_dir, cwd=self.cwd)

    def assertRanClean(self, result, script: str):
        self.assertNotIn("Traceback", result.stderr + result.stdout,
                         f"{script}: a run prints no traceback:\n{result.stderr}")
        self.assertEqual(result.returncode, 0,
                         f"{script}: exit {result.returncode}, stderr:\n{result.stderr}")


class WorkspaceMembersTest(_ToolRunCase):
    """AC2 (§S1.3, §S2.4) — the member set follows Cargo, the same for both tools."""

    def setUp(self):
        super().setUp()
        git_repo(self.project, AC2_WORKSPACE)
        self.head = repo_git(self.project, "rev-parse", "--short", "HEAD")

    def test_crate_map_reports_the_root_package_and_the_glob_members_minus_the_excluded(self):
        result = self.run_scanner(CRATE_MAP)
        self.assertRanClean(result, CRATE_MAP)
        report = json.loads((self.out / "crate_map_baseline.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(row["pkg"] for row in report["crates"]), AC2_PACKAGES,
                         "AC2: exactly the root package, alpha and beta — never default-members' "
                         "set alone, never the excluded skip")
        self.assertEqual(report["meta"]["members"], 3)
        self.assertEqual(report["meta"]["head"], self.head,
                         "the run inherits git and reads the fixture repository's HEAD")
        table = (self.out / "crate_map_baseline.md").read_text(encoding="utf-8")
        for pkg in AC2_PACKAGES:
            self.assertIn(f"| {pkg} |", table)
        self.assertNotIn("| skip |", table, "AC2: the excluded member has no row")

    def test_dead_scan_scans_the_root_package_and_the_glob_members_minus_the_excluded(self):
        result = self.run_scanner(DEAD_SCAN)
        self.assertRanClean(result, DEAD_SCAN)
        report = json.loads((self.out / "dead_scan_report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["meta"]["members"], 3,
                         "AC2: three members — root, alpha and beta")
        self.assertEqual(sorted(site["crate"] for site in report["inventory"]), AC2_PACKAGES,
                         "AC2: one dead-code site from each member and none from skip")
        self.assertEqual(report["meta"]["head"], self.head)
        self.assertFalse(report["deps"]["machete"]["available"],
                         "AC15: no cargo-machete is on the run's PATH, so none ran")


# ------------------------------------------------------------------ AC3 ----

def _workspace(members: str) -> str:
    return f"[workspace]\nmembers = {members}\n"


#: A well-formed member, so a case's only fault is the one it names.
ALPHA_MEMBER = {
    "crates/alpha/Cargo.toml": cargo_member_manifest("alpha"),
    "crates/alpha/src/lib.rs": "pub fn alpha() {}\n",
}

#: §S1.4's malformed workspaces: ``{case: (tree, tokens)}``. The refusal's ``error:`` line names
#: the file or key at fault, so it carries at least one of ``tokens``.
MALFORMED_WORKSPACES = {
    "no_root_manifest": ({**ALPHA_MEMBER}, ("Cargo.toml",)),
    "root_manifest_not_toml": (
        {"Cargo.toml": _workspace('["crates/alpha"]') + "broken = \n", **ALPHA_MEMBER},
        ("Cargo.toml",),
    ),
    "no_workspace_table": (
        {"Cargo.toml": cargo_member_manifest("solo") + '\n[package.metadata.release]\nmembers = ["crates/alpha"]\n',
         **ALPHA_MEMBER},
        ("Cargo.toml", "workspace"),
    ),
    "path_member_without_manifest": (
        {"Cargo.toml": _workspace('["crates/alpha", "crates/ghost"]'), **ALPHA_MEMBER,
         "crates/ghost/src/lib.rs": "pub fn ghost() {}\n"},
        ("crates/ghost",),
    ),
    "glob_match_without_manifest": (
        {"Cargo.toml": _workspace('["crates/*"]'), **ALPHA_MEMBER,
         "crates/empty/src/lib.rs": "pub fn empty() {}\n"},
        ("crates/empty",),
    ),
    "member_manifest_without_package_name": (
        {"Cargo.toml": _workspace('["crates/alpha"]'),
         "crates/alpha/Cargo.toml": '[package]\nversion = "0.1.0"\n\n[lib]\nname = "alpha_lib"\n',
         "crates/alpha/src/lib.rs": "pub fn alpha() {}\n"},
        ("crates/alpha", "[package] name", "package.name"),
    ),
}


class _MalformedWorkspaceCases(_ToolRunCase):
    """AC3 (§S1.4, §S2.4) — each malformed workspace refused with a message, never a traceback.
    A subclass names the tool in ``SCRIPT``; this base is removed from the module namespace once
    both are defined, so the loader collects the cases once per tool and never tool-less."""

    SCRIPT = ""

    def assertRefused(self, case: str):
        tree, tokens = MALFORMED_WORKSPACES[case]
        write_files(self.project, tree)
        result = self.run_scanner(self.SCRIPT)
        self.assertNotIn("Traceback", result.stderr + result.stdout,
                         f"AC3 {case}: {self.SCRIPT} prints no traceback:\n{result.stderr}")
        self.assertNotEqual(result.returncode, 0,
                            f"AC3 {case}: {self.SCRIPT} refuses the workspace, exit non-zero")
        errors = [line for line in result.stderr.splitlines() if line.startswith("error:")]
        self.assertEqual(len(errors), 1,
                         f"AC3 {case}: one stderr line starting 'error:', got:\n{result.stderr}")
        self.assertTrue(any(token in errors[0] for token in tokens),
                        f"AC3 {case}: the error line names one of {tokens}: {errors[0]!r}")

    def test_no_root_manifest_is_refused(self):
        self.assertRefused("no_root_manifest")

    def test_a_root_manifest_that_is_not_toml_is_refused(self):
        self.assertRefused("root_manifest_not_toml")

    def test_a_root_manifest_without_a_workspace_table_is_refused(self):
        self.assertRefused("no_workspace_table")

    def test_a_path_member_without_a_manifest_is_refused(self):
        self.assertRefused("path_member_without_manifest")

    def test_a_glob_match_without_a_manifest_is_refused(self):
        self.assertRefused("glob_match_without_manifest")

    def test_a_member_manifest_without_a_package_name_is_refused(self):
        self.assertRefused("member_manifest_without_package_name")


class CrateMapMalformedWorkspaceTest(_MalformedWorkspaceCases):
    SCRIPT = CRATE_MAP


class DeadScanMalformedWorkspaceTest(_MalformedWorkspaceCases):
    SCRIPT = DEAD_SCAN


del _MalformedWorkspaceCases


if __name__ == "__main__":
    unittest.main()
