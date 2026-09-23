"""RED-phase tests for CR-MDB-030 cycle C2 (\u00a7S7 -- retire the cycle-
todo-naming guard).

Model B no longer keeps a local todo list (the Crucible board is the task
list) and DN \u00a7D18 bars a shared asset from naming a harness's todo tool, so
the practice the retired hook policed is gone. \u00a7S7 DELETES it, not
retargets it: the script, its schema.md entry, its scaffold instance, and
its tests. The installer's hook-script set becomes six. Closed specs
(CR-MDB-015) and audits/ are history and are not edited (\u00a7S7's own text)
-- this sweep does not touch them, and does not require them to be clean.

This module is the ONE place under tests/, hooks-src/ or modelb_axi/
allowed to spell the retired hook's name literally -- every other test
module that referenced it (tests/test_hooks.py, tests/test_hooks_compiler.py,
tests/test_scaffold.py, tests/test_installer_assets.py,
tests/test_installer_correctness.py) was migrated or had its literal
reference removed this same cycle, so THIS module's own definition of the
forbidden token is excluded from its own sweep by PATH (`Path(__file__)`),
mirroring the established self-exclusion idiom already used by
tests/test_client_verb_sweep.py::test_s4b_gate_hardcodes_no_release_version_as_unreleased
and tests/test_tooling_adoption.py's `THIS_MODULE_SOURCE` guard -- never by
obscuring the string itself.

Stdlib only: unittest + pathlib.
"""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_SRC_DIR = REPO_ROOT / "hooks-src"
MODELB_AXI_DIR = REPO_ROOT / "modelb_axi"
TESTS_DIR = REPO_ROOT / "tests"

# The three roots the AC names, swept for literal references below.
_SWEPT_ROOTS = (HOOKS_SRC_DIR, MODELB_AXI_DIR, TESTS_DIR)

# The retired hook's identifier -- spelled ONLY here (self-excluded below).
_RETIRED_HOOK_NAME = "block-bad-cycle-task-name"

RETIRED_SCRIPT_PATH = HOOKS_SRC_DIR / "scripts" / _RETIRED_HOOK_NAME

THIS_FILE = Path(__file__).resolve()

# Directories under the three roots never worth descending into for a
# text sweep (compiled bytecode cache; never real source).
_SKIP_DIR_NAMES = {"__pycache__"}


def _iter_swept_files():
    for root in _SWEPT_ROOTS:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if _SKIP_DIR_NAMES & set(path.parts):
                continue
            yield path


class HookRetirementS7Test(unittest.TestCase):
    """CR-MDB-030 \u00a7S7 AC: the retired hook exists nowhere under
    hooks-src/, modelb_axi/ or tests/, and a sandbox install deploys six
    hook scripts (that half of the AC is
    tests/test_installer_assets.py::HookScriptsDeployEndToEndTest's exact-
    bound assertion, migrated this same cycle -- not duplicated here)."""

    def test_the_retired_script_file_no_longer_exists(self):
        self.assertFalse(
            RETIRED_SCRIPT_PATH.exists(),
            f"\u00a7S7: {RETIRED_SCRIPT_PATH} must be DELETED, not retargeted "
            "(the script, its schema.md entry, its scaffold instance and "
            "its tests all go together)",
        )

    def test_zero_literal_references_under_hooks_src_modelb_axi_and_tests(self):
        offenders = []
        for path in _iter_swept_files():
            if path.resolve() == THIS_FILE:
                continue  # this module's own definition of the token
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue  # binary / unreadable -- cannot carry the literal
            if _RETIRED_HOOK_NAME in text:
                offenders.append(str(path.relative_to(REPO_ROOT)))
        # POSITIVE/EXACT -- zero references anywhere under the three named
        # roots (this module's own self-referential definition excluded).
        self.assertEqual(
            offenders, [],
            f"\u00a7S7: {_RETIRED_HOOK_NAME!r} must exist nowhere under "
            f"hooks-src/, modelb_axi/ or tests/ (this file excluded); "
            f"found in: {offenders}",
        )

    def test_the_sweep_itself_would_catch_a_real_reference(self):
        """Proves the sweep test's own mechanics are sound: a throwaway
        file carrying the retired token, placed under one of the swept
        roots, IS reported -- so a clean sweep above is not a vacuous
        pass from a broken walk/read/self-exclusion path."""
        probe_dir = TESTS_DIR / "fixtures"
        self.assertTrue(
            probe_dir.is_dir(), f"expected an existing fixtures dir at {probe_dir}"
        )
        probe_path = probe_dir / "_s7_sweep_self_check_probe.tmp"
        probe_path.write_text(
            f"# throwaway probe -- mentions {_RETIRED_HOOK_NAME} on purpose\n",
            encoding="utf-8",
        )
        try:
            offenders = []
            for path in _iter_swept_files():
                if path.resolve() == THIS_FILE:
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    continue
                if _RETIRED_HOOK_NAME in text:
                    offenders.append(str(path.relative_to(REPO_ROOT)))
            probe_rel = str(probe_path.relative_to(REPO_ROOT))
            self.assertIn(
                probe_rel, offenders,
                f"the sweep must catch a real planted reference at "
                f"{probe_rel!r}; got offenders={offenders}",
            )
        finally:
            probe_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
