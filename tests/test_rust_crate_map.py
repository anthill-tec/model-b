"""``scripts/rust-crate-map.py``'s render (CR-MDB-078 §S1.5 — AC4).

- ``FailedRenderTest`` — AC4: with a ``dot`` stand-in that exits 1, the crate map exits non-zero
  with an ``error:`` line and no ``Traceback``, and its JSON, markdown and Graphviz files exist.

The tool runs as a subprocess of the test interpreter under ``tests/_helpers.py``'s
``run_tool``: the test process's environment with only ``PATH`` and git's configuration
variables changed, a ``PATH`` of ``git`` and ``tar`` links plus the test's ``dot`` stand-in (never
the host's ``dot``), a temp working directory and ``--project-dir`` / ``--out`` pinned to temp
directories (§S4, AC15). The stand-in logs every call, so the test asserts it ran.

Stdlib only.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests._helpers import run_tool, tool_bin_dir, write_files

CRATE_MAP = "rust-crate-map.py"

#: A one-member workspace in the form today's manifest reading already handles, so the only
#: fault is the render's.
ONE_MEMBER_WORKSPACE = {
    "Cargo.toml": '[workspace]\nmembers = ["crates/alpha"]\n',
    "crates/alpha/Cargo.toml": '[package]\nname = "alpha"\nversion = "0.1.0"\n',
    "crates/alpha/src/lib.rs": "pub fn alpha() -> u32 {\n    1\n}\n",
}


def _failing_dot(log: Path) -> str:
    """A ``dot`` stand-in that appends its argv to ``log`` and exits 1."""
    return f'#!/bin/sh\nprintf \'%s\\n\' "$*" >> \'{log}\'\nexit 1\n'


class FailedRenderTest(unittest.TestCase):
    """AC4 (§S1.5) — a failed render is reported, its other artifacts kept."""

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="mdb-rust-render-"))
        self.addCleanup(shutil.rmtree, self.work, True)
        self.dot_log = self.work / "dot.log"
        self.bin_dir = tool_bin_dir(self.work / "bin", {"dot": _failing_dot(self.dot_log)})
        self.project = write_files(self.work / "proj", ONE_MEMBER_WORKSPACE)
        self.out = self.work / "out"
        self.cwd = self.work / "cwd"
        self.cwd.mkdir()
        self.result = run_tool(CRATE_MAP, "--project-dir", self.project, "--out", self.out,
                               "--name", "fixture", bin_dir=self.bin_dir, cwd=self.cwd)

    def test_a_failing_dot_is_reported_with_an_error_line_and_the_other_files_kept(self):
        calls = self.dot_log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(calls), 1, "AC15: the dot stand-in ran exactly once")
        self.assertIn("-Tsvg", calls[0])
        report = json.loads((self.out / "crate_map_baseline.json").read_text(encoding="utf-8"))
        self.assertEqual([row["pkg"] for row in report["crates"]], ["alpha"])
        self.assertIn("| alpha |", (self.out / "crate_map_baseline.md").read_text(encoding="utf-8"))
        graph = (self.out / "fixture_crate_map.dot").read_text(encoding="utf-8")
        self.assertTrue(graph.startswith("digraph crate_map {"), graph[:80])
        self.assertIn('"alpha"', graph)
        output = self.result.stdout + self.result.stderr
        self.assertNotIn("Traceback", output, f"AC4: no traceback:\n{self.result.stderr}")
        self.assertNotEqual(self.result.returncode, 0, "AC4: a failed render exits non-zero")
        errors = [line for line in output.splitlines() if line.startswith("error:")]
        self.assertEqual(len(errors), 1, f"AC4: one 'error:' line, got:\n{output}")


if __name__ == "__main__":
    unittest.main()
