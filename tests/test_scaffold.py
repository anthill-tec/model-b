"""RED-phase tests for CR-MDB-013 cycle C1 (scaffold flow entry + flags +
dry-run, §S2): the `modelb-axi init` subcommand and its flags, the
scaffold-mode bare-invocation banner, the `--dry-run` empty-target +
TOON-envelope contract, the install.toml-vs-`--harnesses` seam, and a
stdlib-only import guard over the `modelb_axi` package.

Written before any of §S2's production code lands (`init` is not yet a
recognised subcommand on `cli.py`), so every behavioural test below is
expected to FAIL against the current tree -- either a clean argparse usage
error (`init` unrecognised) or, once flags partially exist, a missing
flag/behavior. `StdlibOnlyImportScanTest` is a structural forward-guard
(scans whatever `modelb_axi/*.py` modules currently exist); it may
legitimately PASS today since the package is already stdlib-only and no new
module exists yet to violate it -- see the RED-run report for why this one
is not a spec-behavior assertion.

All invocations are subprocess probes (`python -m modelb_axi ...`) against
tmp sandboxes (`$MODELB_HOME`, `--target`) -- per the CR's binding rule and
DN-scaffold-packaging.md §7, nothing here ever deploys into the real
`~/.claude` or `~/.agents`. (CR-MDB-032 §S2 dropped the module-level
real-home mtime guard: every run pins its own sandbox.)

Stdlib only: ast + unittest + subprocess + sys + os + shutil + tempfile +
pathlib.
"""

import argparse
import ast
import contextlib
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from modelb_axi import requirements as _requirements
from tests._helpers import md_section as _md_section
from tests._helpers import parse_env_file as _parse_env_file
from tests._helpers import run_module as _run_module
from tests._helpers import write_install_toml as _write_install_toml
from tests.pi_capability_sandbox import AGENT_DIR_ENV, shared_provisioned_agent_dir

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_DIR = REPO_ROOT / "modelb_axi"

# CR-MDB-032 §S2: the real-home mtime guard over ~/.claude/skills and
# ~/.agents is dropped -- every deploy/init run here pins its own sandbox.


def _load_toon_codec():
    """Model B's own TOON codec (`modelb_axi.toon`) for TEST-side parsing of
    the envelope. No Crucible checkout is loaded (CR-MDB-032 §S1)."""
    from modelb_axi import toon
    return toon


class InitHelpFlagsTest(unittest.TestCase):
    """§S2 AC -- `modelb-axi init --help` exits 0 and lists every flag the
    scaffold subcommand accepts."""

    def test_init_help_exits_zero_and_lists_all_flags(self):
        result = _run_module("init", "--help")
        self.assertEqual(
            result.returncode, 0,
            "S2: `modelb-axi init --help` must exit 0; got "
            f"exit={result.returncode} stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        required_flags = [
            "--name", "--token", "--acronym", "--mode", "--repo-shape",
            "--stacks", "--harnesses", "--owner", "--target", "--dry-run",
            "--no-commit", "--register",
        ]
        missing = [flag for flag in required_flags if flag not in result.stdout]
        self.assertEqual(
            missing, [],
            "S2: `init --help` must list every scaffold flag; missing "
            f"{missing} from stdout={result.stdout!r}",
        )


class ScaffoldModeEntryTest(unittest.TestCase):
    """§S2 AC -- with a valid install.toml present under $MODELB_HOME, a
    bare non-interactive invocation (no subcommand) banners scaffold mode
    and proposes `init`, exiting 0."""

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-scaffold-home-")

    def tearDown(self):
        shutil.rmtree(self._tmp_home, ignore_errors=True)

    def test_bare_invocation_with_install_toml_banners_scaffold_and_proposes_init(self):
        _write_install_toml(self._tmp_home)
        result = _run_module("--yes", "--modelb-home", self._tmp_home)
        self.assertEqual(
            result.returncode, 0,
            "S2: bare non-interactive invocation with install.toml present "
            f"must exit 0; got exit={result.returncode} "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        # CR-MDB-033 \u00a7S6: stdout carries nothing but the AXI envelope
        # now (verb `install`); these are PROSE checks over the human
        # scaffold-mode banner, which moved to stderr.
        self.assertIn(
            "scaffold", result.stderr.lower(),
            "S2: with install.toml present, stderr must banner scaffold "
            f"mode; got stderr={result.stderr!r}",
        )
        self.assertIn(
            "init", result.stderr.lower(),
            "S2: the scaffold-mode banner must propose running `init`; got "
            f"stderr={result.stderr!r}",
        )
        # NEGATIVE -- must not re-enter the installer flow.
        self.assertNotIn(
            "installer flow", result.stderr.lower(),
            f"S2: must not re-enter the installer flow; got stderr={result.stderr!r}",
        )


class InitDryRunTest(unittest.TestCase):
    """§S2 AC -- `init --dry-run` with a full flag set writes NOTHING
    under --target and emits a TOON envelope on stdout naming
    `axi.verb == "init"` with a true `dry_run` field."""

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-init-home-")
        self._tmp_target = tempfile.mkdtemp(prefix="modelb-axi-init-target-")

    def tearDown(self):
        shutil.rmtree(self._tmp_home, ignore_errors=True)
        shutil.rmtree(self._tmp_target, ignore_errors=True)

    def _full_flags(self):
        return [
            "init",
            "--name", "X", "--token", "x", "--acronym", "XX",
            "--mode", "solo", "--repo-shape", "standalone",
            "--stacks", "python", "--owner", "tester",
            "--target", self._tmp_target, "--dry-run",
        ]

    def test_dry_run_with_install_toml_writes_nothing_and_emits_toon_envelope(self):
        _write_install_toml(self._tmp_home)
        result = _run_module(
            "--yes", *self._full_flags(), "--modelb-home", self._tmp_home,
        )
        self.assertEqual(
            result.returncode, 0,
            "S2: `init --dry-run` with a full flag set must exit 0; got "
            f"exit={result.returncode} stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        # NEGATIVE / bound -- --target must remain a genuinely empty dir.
        listing = sorted(os.listdir(self._tmp_target))
        self.assertEqual(
            listing, [],
            f"S2: `--dry-run` must write NOTHING under --target; found {listing!r}",
        )
        toon = _load_toon_codec()
        try:
            envelope = toon.decode(result.stdout)
        except Exception as exc:
            self.fail(
                "S2: init --dry-run stdout must parse as a TOON envelope; "
                f"decode failed with {exc!r} on stdout={result.stdout!r}"
            )
        axi = envelope.get("axi", {})
        self.assertEqual(
            axi.get("verb"), "init",
            f"S2: envelope axi.verb must be 'init'; got envelope={envelope!r}",
        )
        self.assertIs(
            axi.get("dry_run"), True,
            f"S2: envelope axi.dry_run must be true; got envelope={envelope!r}",
        )

    def test_dry_run_envelope_reports_ok_true_with_no_warnings(self):
        _write_install_toml(self._tmp_home)
        result = _run_module(
            "--yes", *self._full_flags(), "--modelb-home", self._tmp_home,
        )
        toon = _load_toon_codec()
        try:
            envelope = toon.decode(result.stdout)
        except Exception as exc:
            self.fail(
                "S2: init --dry-run stdout must parse as a TOON envelope; "
                f"decode failed with {exc!r} on stdout={result.stdout!r}"
            )
        axi = envelope.get("axi", {})
        # POSITIVE -- a clean dry-run reports ok:true.
        self.assertIs(
            axi.get("ok"), True,
            f"S2: envelope axi.ok must be true for a clean dry-run; got envelope={envelope!r}",
        )
        # NEGATIVE / bound -- a clean run carries no warnings.
        self.assertEqual(
            axi.get("warnings", None), [],
            f"S2: envelope axi.warnings must be an empty list; got envelope={envelope!r}",
        )


class HarnessSeamTest(unittest.TestCase):
    """§S2 AC -- `--harnesses` is the DEV-ONLY override of the installed
    set when install.toml is absent; without install.toml AND without
    --harnesses, `init` refuses to guess and fails non-zero naming
    install.toml."""

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-devharness-home-")
        self._tmp_target = tempfile.mkdtemp(prefix="modelb-axi-devharness-target-")

    def tearDown(self):
        shutil.rmtree(self._tmp_home, ignore_errors=True)
        shutil.rmtree(self._tmp_target, ignore_errors=True)

    def _full_flags(self, *, harnesses=None):
        flags = [
            "init",
            "--name", "X", "--token", "x", "--acronym", "XX",
            "--mode", "solo", "--repo-shape", "standalone",
            "--stacks", "python", "--owner", "tester",
            "--target", self._tmp_target, "--dry-run",
        ]
        if harnesses is not None:
            flags += ["--harnesses", harnesses]
        return flags

    def test_dev_override_harnesses_without_install_toml_dry_run_succeeds(self):
        # No install.toml written under self._tmp_home -- installer-state.
        result = _run_module(
            "--yes", *self._full_flags(harnesses="pi"),
            "--modelb-home", self._tmp_home,
        )
        self.assertEqual(
            result.returncode, 0,
            "S2: `init --dry-run --harnesses pi` without "
            "install.toml (dev override) must still succeed; got "
            f"exit={result.returncode} stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        listing = sorted(os.listdir(self._tmp_target))
        self.assertEqual(
            listing, [],
            f"S2: dev-override dry-run must still write NOTHING under --target; found {listing!r}",
        )

    def test_missing_install_toml_and_missing_harnesses_fails_naming_install_toml(self):
        # Neither install.toml nor --harnesses -- the seam must refuse to
        # guess the installed harness set.
        result = _run_module(
            "--yes", *self._full_flags(harnesses=None),
            "--modelb-home", self._tmp_home,
        )
        self.assertNotEqual(
            result.returncode, 0,
            "S2: `init` without install.toml and without --harnesses must "
            f"fail non-zero (never guess harnesses); got exit="
            f"{result.returncode} stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        combined = (result.stdout + result.stderr).lower()
        self.assertIn(
            "install.toml", combined,
            "S2: the failure message must name install.toml as the missing "
            f"seam; got stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        listing = sorted(os.listdir(self._tmp_target))
        self.assertEqual(
            listing, [],
            f"S2: a failed init must write NOTHING under --target; found {listing!r}",
        )


def _stale_install_toml(home: Path, *, allow_missing: bool) -> None:
    """An ``install.toml`` recording a retired harness id, a target root and stacks, and
    (when ``allow_missing``) ``allow_missing_capabilities = true``."""
    home.mkdir(parents=True, exist_ok=True)
    lines = ["[install]", 'version = "0.1.0"', 'harnesses = ["claude-code"]',
             'target_root = "/nonexistent/mdb recovery target"', 'stacks = ["bun", "python"]']
    if allow_missing:
        lines.append("allow_missing_capabilities = true")
    (home / "install.toml").write_text("\n".join(lines + ["", "[files]", ""]), encoding="utf-8")


class HarnessRecoveryCommandTest(unittest.TestCase):
    """CR-MDB-031 C5 F6 -- the recovery re-run printed for a stale recorded harness id keeps
    ``--allow-missing-capabilities`` when ``install.toml`` recorded it true (the re-run would
    otherwise fail the pre-flight the original install passed with the override)."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="modelb-axi-recovery-")

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _argv(self, *, allow_missing: bool) -> list:
        from modelb_axi import scaffold

        home = Path(self._tmp) / ("allow" if allow_missing else "strict")
        _stale_install_toml(home, allow_missing=allow_missing)
        argv = shlex.split(scaffold.harness_recovery_command(home))
        self.assertEqual(argv[:2], ["modelb-axi", "--reinstall"], f"argv={argv!r}")
        for flag, value in (("--modelb-home", str(home)),
                            ("--target-root", "/nonexistent/mdb recovery target"),
                            ("--stacks", "bun,python"), ("--harnesses", "pi")):
            self.assertEqual(argv[argv.index(flag) + 1], value, f"{flag}: argv={argv!r}")
        return argv

    def test_recorded_allow_missing_capabilities_is_carried_into_the_recovery(self):
        self.assertIn("--allow-missing-capabilities", self._argv(allow_missing=True))

    def test_recovery_omits_the_override_when_install_toml_did_not_record_it(self):
        self.assertNotIn("--allow-missing-capabilities", self._argv(allow_missing=False))

    def test_the_refusal_message_carries_the_same_recovery(self):
        from modelb_axi import scaffold
        from modelb_axi.harness import UnknownHarnessError

        home = Path(self._tmp) / "refusal"
        _stale_install_toml(home, allow_missing=True)
        with self.assertRaises(UnknownHarnessError) as raised:
            scaffold.reject_recorded_harnesses(home)
        self.assertIn(f"`{scaffold.harness_recovery_command(home)}`", str(raised.exception))
        self.assertIn("--allow-missing-capabilities", str(raised.exception))


def _uncovered_stack_templates(names, stack_names, families) -> list:
    """Sorted memory-template names ``<prefix>-*.md`` whose prefix is a stack name but which no
    selection of that stack would emit: the prefix is not a ``families`` key, or its family does
    not list the prefix's own stack."""
    uncovered = []
    for name in names:
        prefix = name.split("-", 1)[0] if "-" in name else None
        if prefix in stack_names and prefix not in families.get(prefix, frozenset()):
            uncovered.append(name)
    return sorted(uncovered)


class MemoryTemplateFamilyCoverageTest(unittest.TestCase):
    """CR-MDB-031 C5 F7 -- every stack-prefixed memory template (``<prefix>-*.md`` where the
    prefix is a ``KNOWN_STACKS`` entry or a generator stack) is covered by
    ``MEMORY_TEMPLATE_FAMILIES``; otherwise it would ship to every project as if stack-neutral."""

    def test_every_stack_prefixed_memory_template_has_a_family(self):
        from modelb_axi import scaffold

        templates = REPO_ROOT / "skills-src" / "memory-templates"
        names = sorted(p.name for p in templates.glob("*.md"))
        self.assertTrue(names, "precondition: memory templates exist")
        stack_names = set(scaffold.KNOWN_STACKS) | {
            p.stem for p in (REPO_ROOT / "generator" / "stacks").glob("*.toml")}
        self.assertEqual(
            _uncovered_stack_templates(names, stack_names, scaffold.MEMORY_TEMPLATE_FAMILIES), [],
            "stack-prefixed memory templates with no MEMORY_TEMPLATE_FAMILIES entry",
        )

    def test_detector_bites_on_an_unmapped_or_self_excluding_prefix(self):
        families = {"java": frozenset({"quarkus"}), "rust": frozenset({"rust"})}
        names = ["java-a.md", "rust-b.md", "python-c.md", "quarkus-d.md",
                 "operational-commands.md", "notes.md"]
        self.assertEqual(
            _uncovered_stack_templates(names, {"java", "rust", "python", "quarkus"}, families),
            ["java-a.md", "python-c.md", "quarkus-d.md"],
        )


class StdlibOnlyImportScanTest(unittest.TestCase):
    """§S2 AC -- the scaffold flow lives in the stdlib-only `modelb_axi`
    package; scan every module's imports statically (AST, not execution)
    so a new module can never sneak in a third-party runtime dependency."""

    def test_all_modelb_axi_modules_import_only_stdlib_or_local(self):
        stdlib_names = set(sys.stdlib_module_names)
        offenders = {}
        for path in sorted(MODULE_DIR.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            bad = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top = alias.name.split(".")[0]
                        if top != "modelb_axi" and top not in stdlib_names:
                            bad.add(top)
                elif isinstance(node, ast.ImportFrom):
                    if node.level and node.level > 0:
                        continue  # relative import -- local, always fine
                    top = (node.module or "").split(".")[0]
                    if top and top != "modelb_axi" and top not in stdlib_names:
                        bad.add(top)
            if bad:
                offenders[path.name] = sorted(bad)
        self.assertEqual(
            offenders, {},
            "S2: every modelb_axi/*.py module must import only stdlib or "
            f"local (modelb_axi.*) modules; found third-party imports: {offenders!r}",
        )


class InitEmissionSoloRunTest(unittest.TestCase):
    """§S3 AC -- a solo, standalone, single-stack `init` run (installed
    harness set = pi per the test's install.toml fixture -- flipped from
    claude-code by CR-MDB-031 §S1) emits the full committed set: registry
    `.env`/`.env.local`, the docs model, `AGENTS.md`, in-repo memory, the git+commit
    state, and the hooks seam note. One subprocess run shared read-only
    across the test methods below (mirrors the class-level shared-fixture
    style already used for HarnessTargetingTest in test_installer.py)."""

    @classmethod
    def setUpClass(cls):
        cls._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-emit-home-")
        cls._tmp_target = tempfile.mkdtemp(prefix="modelb-axi-emit-target-")
        _write_install_toml(cls._tmp_home, harnesses=("pi",))
        cls._result = _run_module(
            "--yes", "init",
            "--name", "X", "--token", "xproj", "--acronym", "XP",
            "--mode", "solo", "--repo-shape", "standalone",
            "--stacks", "python", "--owner", "tester",
            "--target", cls._tmp_target,
            "--modelb-home", cls._tmp_home,
        )
        cls._target = Path(cls._tmp_target)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmp_home, ignore_errors=True)
        shutil.rmtree(cls._tmp_target, ignore_errors=True)

    def test_env_and_env_local_registry_and_gitignore_contract(self):
        env_path = self._target / ".env"
        self.assertTrue(
            env_path.is_file(),
            "S3.1: `.env` must be emitted at the project root; init "
            f"exit={self._result.returncode} stderr={self._result.stderr!r}",
        )
        env = _parse_env_file(env_path)
        # POSITIVE -- all five registry keys, mode-aware orchestrator label.
        self.assertEqual(env.get("PROJECT_NAME"), "X", f"S3.1: got env={env!r}")
        self.assertEqual(env.get("PROJECT_TOKEN"), "xproj", f"S3.1: got env={env!r}")
        self.assertEqual(env.get("PROJECT_ACRONYM"), "XP", f"S3.1: got env={env!r}")
        self.assertEqual(env.get("REPO_OWNER"), "tester", f"S3.1: got env={env!r}")
        self.assertEqual(
            env.get("ORCHESTRATOR_LABEL"), "vidushi-xproj",
            f"S3.1: ORCHESTRATOR_LABEL must be vidushi-<token> in solo mode; got env={env!r}",
        )
        env_local_path = self._target / ".env.local"
        self.assertTrue(
            env_local_path.is_file(),
            "S3.1: `.env.local` must be emitted; target listing="
            f"{list(self._target.iterdir()) if self._target.exists() else 'MISSING'}",
        )
        gitignore_text = (self._target / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(
            ".env.local", gitignore_text,
            f"S3.1/S4: `.gitignore` must ignore `.env.local`; got {gitignore_text!r}",
        )
        env_local = _parse_env_file(env_local_path)
        # POSITIVE -- seeded as an empty placeholder, not absent/None.
        self.assertEqual(
            env_local.get("CRUCIBLE_PROJECT_KEY"), "",
            f"S3.1: `.env.local` must seed CRUCIBLE_PROJECT_KEY as an empty placeholder; got {env_local!r}",
        )

    def test_docs_model_queue_readme_and_research_dir(self):
        readme_path = self._target / "docs" / "changes" / "README.md"
        self.assertTrue(
            readme_path.is_file(),
            f"S3.2: `docs/changes/README.md` must be emitted; init stderr={self._result.stderr!r}",
        )
        readme = readme_path.read_text(encoding="utf-8")
        for slot in ("Design contract", "Evidence base", "Ontology", "Target release"):
            self.assertIn(
                slot, readme,
                f"S3.2: queue README must carry the four header slots incl. {slot!r}; got readme={readme!r}",
            )
        self.assertIn(
            "| CR | Title | Wave | Depends on |", readme,
            f"S3.2: queue README must carry the structure-only table header; got readme={readme!r}",
        )
        self.assertTrue(
            (self._target / "docs" / "research").is_dir(),
            "S3.2: `docs/research/` must exist",
        )

    def test_agents_md_identity_freeze_and_claude_md_symlink(self):
        agents_path = self._target / "AGENTS.md"
        self.assertTrue(
            agents_path.is_file(),
            f"S3.3: `AGENTS.md` must be emitted; init stderr={self._result.stderr!r}",
        )
        content = agents_path.read_text(encoding="utf-8")
        self.assertIn("xproj", content, f"S3.3: AGENTS.md must carry the token; got content={content!r}")
        self.assertIn("XP", content, f"S3.3: AGENTS.md must carry the acronym; got content={content!r}")
        # Migrated (CR-MDB-036 \u00a7S6): the capability contract now names the
        # python toolchain (`python3`), so a whole-file "python" check would
        # pass with the skill freeze gone -- scope it to the freeze section.
        freeze = _md_section(content, "## Skill freeze")
        self.assertIn(
            "python", freeze.lower(),
            f"S3.3: AGENTS.md's skill-freeze section must carry the python stack; got section={freeze!r} content={content!r}",
        )
        self.assertIn(
            "grouping of CRs", content,
            f"S3.3: AGENTS.md must carry the wave definition phrase; got content={content!r}",
        )
        # NEGATIVE -- post-036 run-context note: zero WORKFLOW_CYCLE_ID occurrences.
        self.assertNotIn(
            "WORKFLOW_CYCLE_ID", content,
            f"S3.3: AGENTS.md must carry zero WORKFLOW_CYCLE_ID occurrences; got content={content!r}",
        )
        # CR-MDB-031 §S1: the CLAUDE.md symlink half is retired with the
        # claude-code anchor.

    def test_memory_docs_index_and_stack_filtered_templates(self):
        memory_dir = self._target / "docs" / "memory"
        index_path = memory_dir / "INDEX.md"
        self.assertTrue(
            index_path.is_file(),
            f"S3.4: `docs/memory/INDEX.md` must be emitted; init stderr={self._result.stderr!r}",
        )
        # NEGATIVE / bound -- zero non-python stack templates leak into a
        # `--stacks python` run (java/rust templates exist in the source tree).
        for offender in ("java-orchestration.md", "rust-orchestration.md"):
            self.assertFalse(
                (memory_dir / offender).exists(),
                f"S3.4: `--stacks python` must emit zero non-python stack templates; found {offender}",
            )
        # POSITIVE -- the stack-neutral template IS emitted regardless of --stacks.
        self.assertTrue(
            (memory_dir / "operational-commands.md").is_file(),
            "S3.4: the stack-neutral memory template must be emitted for any --stacks value",
        )

    def test_git_repo_on_develop_with_single_commit_and_clean_porcelain(self):
        git_dir = self._target / ".git"
        self.assertTrue(
            git_dir.is_dir(),
            f"S3.5: `init` must create a git repo under --target; init stderr={self._result.stderr!r}",
        )
        branch = subprocess.run(
            ["git", "-C", str(self._target), "branch", "--show-current"],
            capture_output=True, text=True,
        )
        self.assertEqual(
            branch.stdout.strip(), "develop",
            f"S3.5: repo must be checked out on develop; got stdout={branch.stdout!r} stderr={branch.stderr!r}",
        )
        master = subprocess.run(
            ["git", "-C", str(self._target), "rev-parse", "--verify", "master"],
            capture_output=True, text=True,
        )
        self.assertEqual(
            master.returncode, 0,
            f"S3.5: a `master` ref must exist; stdout={master.stdout!r} stderr={master.stderr!r}",
        )
        commit_count = subprocess.run(
            ["git", "-C", str(self._target), "rev-list", "--all", "--count"],
            capture_output=True, text=True,
        )
        self.assertEqual(
            commit_count.stdout.strip(), "1",
            f"S4: exactly one initial commit is expected; got count={commit_count.stdout!r}",
        )
        porcelain = subprocess.run(
            ["git", "-C", str(self._target), "status", "--porcelain"],
            capture_output=True, text=True,
        )
        # POSITIVE -- a genuinely gitignored file never shows up in plain
        # `git status --porcelain` output at all; a non-empty porcelain
        # here would mean either something is left uncommitted OR
        # `.env.local` is NOT actually ignored (both are failures).
        self.assertEqual(
            porcelain.stdout.strip(), "",
            f"S4: `git status --porcelain` must be EMPTY (committed set "
            f"clean, `.env.local` genuinely gitignored); got porcelain={porcelain.stdout!r}",
        )
        env_local_path = self._target / ".env.local"
        self.assertTrue(
            env_local_path.is_file(),
            "S3.1/S4: `.env.local` must exist on disk even though it is "
            f"gitignored; target listing={list(self._target.iterdir()) if self._target.exists() else 'MISSING'}",
        )
        check_ignore = subprocess.run(
            ["git", "-C", str(self._target), "check-ignore", ".env.local"],
            capture_output=True, text=True,
        )
        self.assertEqual(
            check_ignore.returncode, 0,
            "S4: `.env.local` must be genuinely gitignored (`git "
            f"check-ignore` must exit 0); got exit={check_ignore.returncode} "
            f"stdout={check_ignore.stdout!r} stderr={check_ignore.stderr!r}",
        )

    def test_hooks_readme_names_cr_mdb_015(self):
        """AMENDED (sanctioned CR-MDB-015 013-gate amendment, per the CR's
        Context section): this gate originally pinned the C1 seam-
        placeholder text ("pending the CR-MDB-015 compiler" + the inert
        `{"hooks": []}` JSON block). Now that §S5 fills the seam for real,
        the placeholder is retired -- the gate retargets to the REAL
        emission: `hooks/README.md` must carry the §S4 compiler's
        per-harness report, naming the installed harness ("pi" -- flipped
        from "claude-code" by CR-MDB-031 §S1)
        and the always-on `ambient-board-status` hook, rather than the
        old placeholder. The method name is kept unchanged (it is cited by
        name in the CR's Context section as "the sanctioned gate") -- only
        the body's assertions retarget.
        """
        hooks_readme = self._target / "hooks" / "README.md"
        self.assertTrue(
            hooks_readme.is_file(),
            f"S3.7/S5: `hooks/README.md` must be emitted; init stderr={self._result.stderr!r}",
        )
        content = hooks_readme.read_text(encoding="utf-8")
        # POSITIVE -- the real compiler report names the installed harness.
        self.assertIn(
            "### pi", content,
            "S5: hooks/README.md must carry the compiler report naming the "
            f"emitted harness 'pi'; got content={content!r}",
        )
        # POSITIVE -- and the always-on ambient-board-status hook.
        self.assertIn(
            "ambient-board-status", content,
            "S5: hooks/README.md must name the ambient-board-status hook "
            f"in the compiler report; got content={content!r}",
        )
        # NEGATIVE -- the C1 seam placeholder text is retired.
        self.assertNotIn(
            "pending the CR-MDB-015 compiler", content,
            "S5: the C1 placeholder text must be replaced by the real "
            f"compiler report; got content={content!r}",
        )

    def test_non_dry_init_success_envelope_reports_ok_true_with_files_emitted_count(self):
        self.assertEqual(
            self._result.returncode, 0,
            "S3/S6: a full non-dry init run must exit 0; got "
            f"exit={self._result.returncode} stdout={self._result.stdout!r} "
            f"stderr={self._result.stderr!r}",
        )
        toon = _load_toon_codec()
        try:
            envelope = toon.decode(self._result.stdout)
        except Exception as exc:
            self.fail(
                "S6: a non-dry `init` success must still emit a parseable "
                f"TOON envelope; decode failed with {exc!r} on stdout={self._result.stdout!r}"
            )
        axi = envelope.get("axi", {})
        self.assertIs(
            axi.get("ok"), True,
            f"S6: a successful non-dry init must report axi.ok true; got envelope={envelope!r}",
        )
        count_field = next(
            (k for k in ("emitted", "files_emitted", "planned") if k in axi), None,
        )
        self.assertIsNotNone(
            count_field,
            "S6: the success envelope must carry a files-emitted count/list "
            f"field (emitted/files_emitted/planned); got envelope={envelope!r}",
        )
        value = axi[count_field]
        count = len(value) if isinstance(value, list) else value
        # NEGATIVE / bound -- at least the 8 base committed-set files, loosely pinned.
        self.assertGreaterEqual(
            count, 8,
            "S6: the files-emitted count/list must cover at least the base "
            f"committed set (>=8); got {count_field}={value!r}",
        )


class HooksSeamSoloRustEmissionTest(unittest.TestCase):
    """§S5 AC (CR-MDB-015) -- a solo, single-stack `rust` init (pi-only
    install.toml fixture -- flipped from claude-code by CR-MDB-031 §S1)
    fills the hooks seam: stack/mode-derived neutral-schema TOML instances
    land under `hooks/instances/<command>.toml` (one instance per hook --
    schema.md v1's "one instance per hook" line), and the §S4 compiler
    wires the emitted instances for the installed harness.

    Derived stack/mode selection table (documented per dispatch instruction,
    from §S5's "cargo guard only for rust stacks; worktree/CR guards only
    for multi mode; ambient-board-status always" rule plus each guard's own
    nature -- schema.md v1's security-class list and each script's own
    stdlib docstring). The CR text pins ONLY the rows this test and
    HooksSeamMultiPythonEmissionTest assert on (cargo/mvn stack-gating,
    worktree/CR mode-gating, ambient-status always-on); it is silent on
    `post-regression-disk-reminder`'s exact gating for THIS scenario, so
    neither its presence nor its absence is asserted below -- only the
    pinned rows:

        hook                                    | stack gate               | mode gate
        -----------------------------------------|--------------------------|----------
        ambient-board-status                      | none (always)            | none (always)
        block-direct-cargo-test                   | stacks ∩ {rust}          | none
        block-direct-mvn-test                     | stacks ∩ {java, quarkus} | none
        block-write-outside-worktree              | none (stack-neutral)     | multi only
        block-cr-completed-without-spec-update    | none (stack-neutral)     | multi only
        post-regression-disk-reminder             | none (stack-neutral per  | UNPINNED by
                                                   | dispatch note)           | this CR slice
    """

    @classmethod
    def setUpClass(cls):
        cls._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-hooks-rust-home-")
        cls._tmp_target = tempfile.mkdtemp(prefix="modelb-axi-hooks-rust-target-")
        _write_install_toml(cls._tmp_home, harnesses=("pi",))
        cls._result = _run_module(
            "--yes", "init",
            "--name", "X", "--token", "xproj", "--acronym", "XP",
            "--mode", "solo", "--repo-shape", "standalone",
            "--stacks", "rust", "--owner", "tester",
            "--target", cls._tmp_target,
            "--modelb-home", cls._tmp_home,
        )
        cls._target = Path(cls._tmp_target)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmp_home, ignore_errors=True)
        shutil.rmtree(cls._tmp_target, ignore_errors=True)

    def _instance_path(self, command):
        return self._target / "hooks" / "instances" / f"{command}.toml"

    def test_cargo_guard_and_ambient_status_toml_instances_emitted_with_correct_fields(self):
        cargo_path = self._instance_path("block-direct-cargo-test")
        self.assertTrue(
            cargo_path.is_file(),
            "S5: a `--stacks rust` init must emit the cargo-guard neutral "
            f"schema instance at {cargo_path}; init exit={self._result.returncode} "
            f"stderr={self._result.stderr!r}",
        )
        with open(cargo_path, "rb") as fh:
            cargo_instance = tomllib.load(fh)
        self.assertEqual(
            cargo_instance.get("command"), "block-direct-cargo-test",
            f"S5: got instance={cargo_instance!r}",
        )
        self.assertEqual(
            cargo_instance.get("event"), "pre-tool-use",
            f"S5: cargo guard is a pre-tool-use hook; got instance={cargo_instance!r}",
        )
        # POSITIVE -- security-class (block-*) hooks MUST declare
        # fail_direction (schema.md v1).
        self.assertIn(
            cargo_instance.get("fail_direction"), ("open", "closed"),
            "S5: the cargo guard is security-class and must declare "
            f"fail_direction; got instance={cargo_instance!r}",
        )

        ambient_path = self._instance_path("ambient-board-status")
        instances_dir = self._target / "hooks" / "instances"
        self.assertTrue(
            ambient_path.is_file(),
            "S5: ambient-board-status must always be emitted; hooks/instances "
            f"listing={list(instances_dir.iterdir()) if instances_dir.is_dir() else 'MISSING'}",
        )
        with open(ambient_path, "rb") as fh:
            ambient_instance = tomllib.load(fh)
        self.assertEqual(
            ambient_instance.get("command"), "ambient-board-status",
            f"S5: got instance={ambient_instance!r}",
        )
        self.assertEqual(
            ambient_instance.get("event"), "session-start",
            f"S5: ambient-board-status is a session-start hook; got instance={ambient_instance!r}",
        )

    def test_mvn_and_worktree_and_cr_completed_guard_instances_not_emitted_for_solo_rust(self):
        # NEGATIVE -- no java/quarkus stack selected, so the mvn guard must
        # not appear.
        self.assertFalse(
            self._instance_path("block-direct-mvn-test").exists(),
            "S5: `--stacks rust` (no java/quarkus) must not emit the mvn-"
            "guard instance",
        )
        # NEGATIVE -- solo mode, so neither the worktree nor the CR-
        # completion guard may appear.
        self.assertFalse(
            self._instance_path("block-write-outside-worktree").exists(),
            "S5: solo mode must not emit the worktree guard instance",
        )
        self.assertFalse(
            self._instance_path("block-cr-completed-without-spec-update").exists(),
            "S5: solo mode must not emit the CR-completion guard instance",
        )


class HooksSeamMultiPythonEmissionTest(unittest.TestCase):
    """§S5 AC (CR-MDB-015) -- a `--mode multi:2 --stacks python` init emits
    the mode-gated worktree/CR-completion guard instances (multi only) and
    withholds the stack-gated cargo/mvn guards (python selects neither rust
    nor java/quarkus). See HooksSeamSoloRustEmissionTest's docstring for the
    full derived selection table this pair of test classes is pinned from.
    """

    @classmethod
    def setUpClass(cls):
        cls._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-hooks-multi-home-")
        cls._tmp_target = tempfile.mkdtemp(prefix="modelb-axi-hooks-multi-target-")
        _write_install_toml(cls._tmp_home, harnesses=("pi",))
        cls._result = _run_module(
            "--yes", "init",
            "--name", "X", "--token", "xproj", "--acronym", "XP",
            "--mode", "multi:2", "--repo-shape", "standalone",
            "--stacks", "python", "--owner", "tester",
            "--target", cls._tmp_target,
            "--modelb-home", cls._tmp_home,
        )
        cls._target = Path(cls._tmp_target)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmp_home, ignore_errors=True)
        shutil.rmtree(cls._tmp_target, ignore_errors=True)

    def _instance_path(self, command):
        return self._target / "hooks" / "instances" / f"{command}.toml"

    def test_worktree_and_cr_completed_guard_instances_emitted_for_multi_mode(self):
        for command in (
            "block-write-outside-worktree",
            "block-cr-completed-without-spec-update",
        ):
            path = self._instance_path(command)
            self.assertTrue(
                path.is_file(),
                f"S5: `--mode multi:2` must emit the {command!r} guard "
                f"instance; init exit={self._result.returncode} "
                f"stderr={self._result.stderr!r}",
            )
            with open(path, "rb") as fh:
                instance = tomllib.load(fh)
            self.assertEqual(
                instance.get("command"), command,
                f"S5: got instance={instance!r}",
            )
            # POSITIVE -- these are security-class (block-*) hooks too.
            self.assertIn(
                instance.get("fail_direction"), ("open", "closed"),
                f"S5: {command!r} is security-class and must declare "
                f"fail_direction; got instance={instance!r}",
            )

    def test_cargo_and_mvn_guard_instances_not_emitted_for_python_stack(self):
        # NEGATIVE / bound -- `--stacks python` selects neither rust nor
        # java/quarkus, so neither stack-gated guard may appear, even
        # though this run is multi-mode.
        self.assertFalse(
            self._instance_path("block-direct-cargo-test").exists(),
            "S5: `--stacks python` must not emit the cargo guard instance",
        )
        self.assertFalse(
            self._instance_path("block-direct-mvn-test").exists(),
            "S5: `--stacks python` (no java/quarkus) must not emit the mvn "
            "guard instance",
        )


class PiWorktreeCarryAndClosedGuardsTest(unittest.TestCase):
    """\u00a7S6 AC (CR-MDB-030) -- the scaffold's `.gitignore` stops ignoring
    `.pi/` wholesale so a fresh `git worktree add` carries the project's
    `.pi/extensions/` (compiled pi hook shims) and `.pi/agents/` (subagent
    defs); every scaffold `block-*` guard instance is emitted
    `fail_direction: closed` (the pre-CR-030 value was `open`); and the old
    Claude-refusal rationale comment that justified `open` is gone from
    `scaffold.py`'s source.

    RUN CONTEXT -- one `--mode multi:2 --stacks rust,java` init fixture for
    a pi install (flipped from claude-code,pi by CR-MDB-031 §S1), shared by
    every test method below: multi mode + rust + java together select ALL FOUR block-* instances (see
    HooksSeamSoloRustEmissionTest's derived selection table), and `pi` in
    the installed harness roster makes the \u00a7S4 compiler
    (`hooks.compile_wiring` -> `_emit_pi`) emit one `.pi/extensions/
    <command>.ts` per instance.
    """

    @classmethod
    def setUpClass(cls):
        cls._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-pi-worktree-home-")
        cls._tmp_target = tempfile.mkdtemp(prefix="modelb-axi-pi-worktree-target-")
        _write_install_toml(cls._tmp_home, harnesses=("pi",))
        cls._result = _run_module(
            "--yes", "init",
            "--name", "X", "--token", "xproj", "--acronym", "XP",
            "--mode", "multi:2", "--repo-shape", "standalone",
            "--stacks", "rust,java", "--owner", "tester",
            "--target", cls._tmp_target,
            "--modelb-home", cls._tmp_home,
        )
        cls._target = Path(cls._tmp_target)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmp_home, ignore_errors=True)
        shutil.rmtree(cls._tmp_target, ignore_errors=True)

    def _instance_path(self, command):
        return self._target / "hooks" / "instances" / f"{command}.toml"

    def test_init_succeeded_precondition(self):
        # Fixture precondition, not an S6 assertion itself -- every other
        # method in this class depends on this run having actually emitted
        # a project tree.
        self.assertEqual(
            self._result.returncode, 0,
            f"S6 fixture precondition: init must succeed; "
            f"stdout={self._result.stdout!r} stderr={self._result.stderr!r}",
        )

    def test_gitignore_has_no_line_ignoring_pi_directory_wholesale(self):
        gitignore_path = self._target / ".gitignore"
        self.assertTrue(gitignore_path.is_file(), f"expected {gitignore_path}")
        lines = [
            ln.strip()
            for ln in gitignore_path.read_text(encoding="utf-8").splitlines()
        ]
        # NEGATIVE/EXACT -- any of these forms blanket-ignores the whole
        # `.pi/` tree, which would silently drop `.pi/extensions/` AND
        # `.pi/agents/` from every future `git add -A`.
        offending = [ln for ln in lines if ln in (".pi/", ".pi", "/.pi/", "/.pi")]
        self.assertEqual(
            offending, [],
            f"S6: `.gitignore` must not ignore `.pi/` wholesale (so "
            f".pi/extensions/ and .pi/agents/ can be tracked); got "
            f"lines={lines!r}",
        )

    def test_every_scaffold_block_guard_instance_is_fail_closed(self):
        for command in (
            "block-direct-cargo-test",
            "block-direct-mvn-test",
            "block-write-outside-worktree",
            "block-cr-completed-without-spec-update",
        ):
            path = self._instance_path(command)
            self.assertTrue(
                path.is_file(),
                f"S6 fixture precondition: {command!r} instance must be "
                f"emitted by this run (rust+java stacks, multi mode); init "
                f"stderr={self._result.stderr!r}",
            )
            with open(path, "rb") as fh:
                instance = tomllib.load(fh)
            # POSITIVE/EXACT -- CR-MDB-030 \u00a7S6 flips every scaffold
            # block-* guard from "open" to "closed"; the pre-CR-030 value
            # ("open") must NOT survive.
            self.assertEqual(
                instance.get("fail_direction"), "closed",
                f"S6: {command!r} must be emitted fail_direction=closed "
                f"(not the pre-CR-030 'open'); got instance={instance!r}",
            )

    def test_claude_refusal_rationale_comment_removed_from_scaffold_source(self):
        source = (REPO_ROOT / "modelb_axi" / "scaffold.py").read_text(encoding="utf-8")
        # NEGATIVE -- the pre-CR-030 rationale sentence that justified
        # emitting `fail_direction: "open"` because `closed` would make the
        # \u00a7S4 compiler refuse the guard on Claude Code (a fail-open
        # harness) must be gone now that guards ARE closed.
        self.assertNotIn(
            "REFUSE the guard on the fail-open harnesses",
            source,
            "S6: the Claude-refusal rationale comment that justified "
            "fail_direction='open' must be deleted from scaffold.py now "
            "that block-* guards are closed",
        )
        self.assertNotIn(
            'fail_direction = "open"',
            source,
            "S6: scaffold.py's block-* comment/prose must not still "
            "prescribe fail_direction='open'",
        )

    def test_fresh_worktree_checkout_carries_pi_extensions_and_pi_agents(self):
        # Simulate a user-authored Pi subagent definition living alongside
        # the scaffold-emitted `.pi/extensions/*.ts` -- proves the
        # `.gitignore` fix is not merely cosmetic: a REAL `.pi/agents/*`
        # file survives `git add -A` and is present after `git worktree
        # add`, exactly like the `.pi/extensions/*.ts` files init already
        # emitted.
        agents_dir = self._target / ".pi" / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        agent_file = agents_dir / "sample-subagent.md"
        agent_file.write_text("# sample subagent\n", encoding="utf-8")

        # NEGATIVE -- `git check-ignore` exits 0 when a path IS ignored;
        # this must exit non-zero (not ignored) for both a scaffold-
        # emitted extension and the manually-added agents file, or
        # nothing downstream (`add`/`commit`/the worktree) can carry them.
        for rel in (".pi/agents/sample-subagent.md", ".pi/extensions"):
            check_ignore = subprocess.run(
                ["git", "check-ignore", rel], cwd=self._target,
                capture_output=True, text=True,
            )
            self.assertNotEqual(
                check_ignore.returncode, 0,
                f"S6: {rel!r} must NOT be git-ignored; `git check-ignore` "
                f"reported it ignored (stdout={check_ignore.stdout!r})",
            )

        add = subprocess.run(
            ["git", "add", "-A"], cwd=self._target,
            capture_output=True, text=True,
        )
        self.assertEqual(add.returncode, 0, f"git add failed: {add.stderr!r}")
        commit = subprocess.run(
            [
                "git", "-c", "user.email=modelb-axi-test@localhost",
                "-c", "user.name=modelb-axi-test",
                "commit", "-m", "test: add sample .pi/agents fixture",
            ],
            cwd=self._target, capture_output=True, text=True,
        )
        self.assertEqual(
            commit.returncode, 0,
            f"S6: committing the new `.pi/agents/*` file must succeed "
            f"(it must be a real, add-able change, not gitignored-away); "
            f"git commit stdout={commit.stdout!r} stderr={commit.stderr!r}",
        )

        ls_files = subprocess.run(
            ["git", "ls-files", ".pi"], cwd=self._target,
            capture_output=True, text=True,
        )
        self.assertEqual(ls_files.returncode, 0, f"git ls-files failed: {ls_files.stderr!r}")
        tracked = set(ls_files.stdout.split())
        # POSITIVE/EXACT -- the agents file must be genuinely git-tracked,
        # not merely present on disk.
        self.assertIn(
            ".pi/agents/sample-subagent.md", tracked,
            f"S6: `.pi/agents/*` must be genuinely git-tracked (not "
            f"ignored); tracked .pi entries={tracked!r}",
        )
        tracked_extensions = [
            entry for entry in tracked if entry.startswith(".pi/extensions/")
        ]
        self.assertTrue(
            tracked_extensions,
            f"S6 fixture precondition: at least one .pi/extensions/*.ts "
            f"must be emitted+tracked (pi harness selected); "
            f"tracked={tracked!r}",
        )

        worktree_root = tempfile.mkdtemp(prefix="modelb-axi-pi-worktree-checkout-")
        self.addCleanup(shutil.rmtree, worktree_root, ignore_errors=True)
        checkout_path = Path(worktree_root) / "wt"
        worktree_add = subprocess.run(
            [
                "git", "worktree", "add", "-b", "s6-worktree-check",
                str(checkout_path), "develop",
            ],
            cwd=self._target, capture_output=True, text=True,
        )
        self.addCleanup(
            lambda: subprocess.run(
                ["git", "worktree", "remove", "--force", str(checkout_path)],
                cwd=self._target, capture_output=True, text=True,
            )
        )
        self.assertEqual(
            worktree_add.returncode, 0,
            f"git worktree add failed: {worktree_add.stderr!r}",
        )
        # POSITIVE -- the fresh worktree checkout (a SEPARATE working tree
        # from a fresh `git checkout` of the same commit) must physically
        # contain both directories -- this is the literal AC wording ("a
        # fresh `git worktree add` ... contains its .pi/extensions/ and
        # .pi/agents/").
        pi_listing = (
            sorted(str(p.relative_to(checkout_path)) for p in (checkout_path / ".pi").rglob("*"))
            if (checkout_path / ".pi").exists() else "MISSING .pi"
        )
        self.assertTrue(
            (checkout_path / ".pi" / "agents" / "sample-subagent.md").is_file(),
            f"S6: fresh worktree checkout must carry .pi/agents/*; "
            f"listing={pi_listing}",
        )
        extensions_dir = checkout_path / ".pi" / "extensions"
        extensions_in_worktree = list(extensions_dir.glob("*.ts")) if extensions_dir.is_dir() else []
        self.assertTrue(
            extensions_in_worktree,
            f"S6: fresh worktree checkout must carry .pi/extensions/*.ts; "
            f"listing={pi_listing}",
        )


class MonorepoEmissionTest(unittest.TestCase):
    """§S3 AC -- `--repo-shape monorepo:a,b` emits per-sub-project `.env`
    + `AGENTS.md` under each sub-project dir (`a/`, `b/`)."""

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-mono-home-")
        self._tmp_target = tempfile.mkdtemp(prefix="modelb-axi-mono-target-")
        _write_install_toml(self._tmp_home, harnesses=("pi",))

    def tearDown(self):
        shutil.rmtree(self._tmp_home, ignore_errors=True)
        shutil.rmtree(self._tmp_target, ignore_errors=True)

    def test_monorepo_repo_shape_emits_per_subproject_env_and_agents_md(self):
        result = _run_module(
            "--yes", "init",
            "--name", "X", "--token", "xproj", "--acronym", "XP",
            "--mode", "solo", "--repo-shape", "monorepo:a,b",
            "--stacks", "python", "--owner", "tester",
            "--target", self._tmp_target,
            "--modelb-home", self._tmp_home,
        )
        target = Path(self._tmp_target)
        for sub in ("a", "b"):
            sub_env = target / sub / ".env"
            sub_agents = target / sub / "AGENTS.md"
            self.assertTrue(
                sub_env.is_file(),
                f"S3: monorepo sub-project {sub!r} must get its own `.env`; "
                f"init exit={result.returncode} stderr={result.stderr!r}",
            )
            self.assertTrue(
                sub_agents.is_file(),
                f"S3: monorepo sub-project {sub!r} must get its own `AGENTS.md`",
            )
            sub_env_content = _parse_env_file(sub_env)
            self.assertEqual(
                sub_env_content.get("PROJECT_TOKEN"), "xproj",
                f"S3: sub-project .env must carry the project registry too; got {sub_env_content!r}",
            )


class NoCommitPolicyTest(unittest.TestCase):
    """§S4 AC -- `--no-commit` leaves zero commits with no partial
    commit, while the emission itself still happens."""

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-nocommit-home-")
        self._tmp_target = tempfile.mkdtemp(prefix="modelb-axi-nocommit-target-")
        _write_install_toml(self._tmp_home, harnesses=("pi",))

    def tearDown(self):
        shutil.rmtree(self._tmp_home, ignore_errors=True)
        shutil.rmtree(self._tmp_target, ignore_errors=True)

    def test_no_commit_flag_leaves_zero_commits_and_still_emits_files(self):
        result = _run_module(
            "--yes", "init",
            "--name", "X", "--token", "xproj", "--acronym", "XP",
            "--mode", "solo", "--repo-shape", "standalone",
            "--stacks", "python", "--owner", "tester",
            "--target", self._tmp_target,
            "--modelb-home", self._tmp_home,
            "--no-commit",
        )
        target = Path(self._tmp_target)
        # POSITIVE -- emission still happens under --no-commit.
        self.assertTrue(
            (target / "AGENTS.md").is_file(),
            f"S4: --no-commit must still emit files; init exit={result.returncode} "
            f"stderr={result.stderr!r}",
        )
        git_dir = target / ".git"
        if git_dir.is_dir():
            commit_count = subprocess.run(
                ["git", "-C", str(target), "rev-list", "--all", "--count"],
                capture_output=True, text=True,
            )
            self.assertEqual(
                commit_count.stdout.strip(), "0",
                f"S4: --no-commit must leave zero commits; got count={commit_count.stdout!r}",
            )
            # NEGATIVE -- no partial commit: nothing may be staged either.
            staged = subprocess.run(
                ["git", "-C", str(target), "diff", "--cached", "--name-only"],
                capture_output=True, text=True,
            )
            self.assertEqual(
                staged.stdout.strip(), "",
                f"S4: --no-commit must leave nothing staged (no partial commit); got staged={staged.stdout!r}",
            )


class RegisterHonestNoOpTest(unittest.TestCase):
    """VERIFY F1 finding (sanctioned) -- `--register` is an honest no-op
    in scaffold v1: live registration is NOT implemented, so passing the
    flag must fail fast non-zero BEFORE any emission (`--target` stays
    genuinely empty) with output naming `--register` and the fact it is
    not implemented -- never a silent zero-work success."""

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-register-home-")
        self._tmp_target = tempfile.mkdtemp(prefix="modelb-axi-register-target-")
        _write_install_toml(self._tmp_home, harnesses=("pi",))

    def tearDown(self):
        shutil.rmtree(self._tmp_home, ignore_errors=True)
        shutil.rmtree(self._tmp_target, ignore_errors=True)

    def test_register_flag_fails_fast_nonzero_with_empty_target(self):
        result = _run_module(
            "--yes", "init",
            "--name", "X", "--token", "xproj", "--acronym", "XP",
            "--mode", "solo", "--repo-shape", "standalone",
            "--stacks", "python", "--owner", "tester",
            "--target", self._tmp_target,
            "--modelb-home", self._tmp_home,
            "--register",
        )
        # POSITIVE -- the honest no-op refuses to pretend it registered.
        self.assertNotEqual(
            result.returncode, 0,
            "F1: `init --register` must exit non-zero in v1 (live "
            "registration is not implemented); got "
            f"exit={result.returncode} stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        # NEGATIVE / bound -- fail fast means NOTHING emitted under --target.
        listing = sorted(os.listdir(self._tmp_target))
        self.assertEqual(
            listing, [],
            f"F1: `init --register` must write NOTHING under --target; found {listing!r}",
        )
        combined = result.stdout + result.stderr
        self.assertIn(
            "--register", combined,
            "F1: the failure output must name the --register flag; got "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        self.assertIn(
            "not implemented", combined.lower(),
            "F1: the failure output must say registration is not "
            f"implemented; got stdout={result.stdout!r} stderr={result.stderr!r}",
        )


def _names(text: str, token: str) -> bool:
    """True when ``token`` occurs in ``text`` as a whole name -- not as part
    of a longer identifier (``lean-ctx`` inside ``pi-lean-ctx`` is not a
    mention of ``lean-ctx``; ``cargo`` inside ``cargo-nextest`` is not a
    mention of ``cargo``)."""
    return re.search(
        rf"(?<![\w-]){re.escape(token)}(?![\w-])", text,
    ) is not None


def _tier1_rows() -> list[dict]:
    return [row for row in _requirements.REQUIREMENTS if row["tier"] == 1]


def _line_pairing(content: str, name: str, remediation: str) -> list[str]:
    """Lines of ``content`` naming ``name`` AND carrying ``remediation``
    verbatim -- the \u00a7S6 "each with its remediation" pairing."""
    return [
        line for line in content.splitlines()
        if _names(line, name) and remediation in line
    ]


def _run_init_subprocess(stacks: str, harnesses=("pi",)):
    """A real `modelb-axi --yes init` (production entry) into a fresh
    sandbox; returns ``(result, AGENTS.md text or "", dirs to clean)``."""
    tmp_home = tempfile.mkdtemp(prefix="modelb-axi-contract-home-")
    tmp_target = tempfile.mkdtemp(prefix="modelb-axi-contract-target-")
    _write_install_toml(tmp_home, harnesses=harnesses)
    result = _run_module(
        "--yes", "init",
        "--name", "X", "--token", "xproj", "--acronym", "XP",
        "--mode", "solo", "--repo-shape", "standalone",
        "--stacks", stacks, "--owner", "tester",
        "--target", tmp_target,
        "--modelb-home", tmp_home,
        timeout=60,
    )
    agents_path = Path(tmp_target) / "AGENTS.md"
    text = agents_path.read_text(encoding="utf-8") if agents_path.is_file() else ""
    return result, text, (tmp_home, tmp_target)


class ScaffoldCapabilityContractTest(unittest.TestCase):
    """CR-MDB-036 \u00a7S6 AC -- `init` writes the tier-1 capabilities and the
    selected stacks' toolchains, with remediations, into the scaffolded
    `AGENTS.md`; a python-only project names no other stack's toolchain.

    Every expected value is read from ``modelb_axi.requirements``
    (``REQUIREMENTS`` tier-1 rows, ``STACK_TOOLCHAINS``) -- never a hand-
    copied string -- and driven through the real `init` entry point.
    Pairing is asserted per line: a capability/probe name and its own
    remediation on one line, so a list of names followed by an unrelated
    list of remediations does not pass."""

    @classmethod
    def setUpClass(cls):
        cls._result, cls._content, cls._dirs = _run_init_subprocess("python")

    @classmethod
    def tearDownClass(cls):
        for d in cls._dirs:
            shutil.rmtree(d, ignore_errors=True)

    def _precondition(self):
        self.assertEqual(
            self._result.returncode, 0,
            f"precondition: init must succeed; stdout={self._result.stdout!r} "
            f"stderr={self._result.stderr!r}",
        )
        self.assertTrue(self._content, "precondition: AGENTS.md must be emitted")

    def test_every_tier1_capability_is_named_with_its_remediation(self):
        self._precondition()
        rows = _tier1_rows()
        # Bound on the data itself: \u00a7S1 declares three tier-1 rows and
        # CR-MDB-029 \u00a7S3 adds the fourth, ``watcher``.
        self.assertEqual(
            sorted(r["id"] for r in rows), ["dispatch", "lean-ctx", "permissions", "watcher"],
            f"requirements data drifted from \u00a7S1's tier-1 table: {rows!r}",
        )
        for row in rows:
            with self.subTest(capability=row["id"]):
                self.assertTrue(
                    _line_pairing(self._content, row["id"], row["remediation"]),
                    f"\u00a7S6: AGENTS.md must name tier-1 capability {row['id']!r} "
                    f"with its remediation {row['remediation']!r} on one line; "
                    f"got content={self._content!r}",
                )

    def test_python_only_project_names_python_toolchain_and_no_other_stacks(self):
        self._precondition()
        python_probes = _requirements.STACK_TOOLCHAINS["python"]
        for probe in python_probes:
            with self.subTest(probe=probe["name"]):
                self.assertTrue(
                    _line_pairing(self._content, probe["name"], probe["remediation"]),
                    f"\u00a7S6: a python project's AGENTS.md must name toolchain probe "
                    f"{probe['name']!r} with its remediation "
                    f"{probe['remediation']!r} on one line; got content={self._content!r}",
                )
        # NEGATIVE -- no other stack's toolchain: neither a probe name nor
        # a remediation from any unselected stack's STACK_TOOLCHAINS row.
        python_names = {p["name"] for p in python_probes}
        python_remediations = {p["remediation"] for p in python_probes}
        for stack, probes in _requirements.STACK_TOOLCHAINS.items():
            if stack == "python":
                continue
            for probe in probes:
                if probe["name"] not in python_names:
                    self.assertFalse(
                        _names(self._content, probe["name"]),
                        f"\u00a7S6: a python-only AGENTS.md must not name {stack}'s "
                        f"toolchain probe {probe['name']!r}; got content={self._content!r}",
                    )
                if probe["remediation"] not in python_remediations:
                    self.assertNotIn(
                        probe["remediation"], self._content,
                        f"\u00a7S6: a python-only AGENTS.md must not carry {stack}'s "
                        f"remediation {probe['remediation']!r}",
                    )


class ScaffoldCapabilityContractMultiStackTest(unittest.TestCase):
    """CR-MDB-036 \u00a7S6 AC, edge -- with `--stacks python,rust` BOTH selected
    stacks' toolchains are written with remediations, and no unselected
    stack's (arduino, bun, quarkus/java) toolchain appears."""

    @classmethod
    def setUpClass(cls):
        cls._result, cls._content, cls._dirs = _run_init_subprocess("python,rust")

    @classmethod
    def tearDownClass(cls):
        for d in cls._dirs:
            shutil.rmtree(d, ignore_errors=True)

    def test_each_selected_stack_toolchain_named_and_unselected_absent(self):
        self.assertEqual(
            self._result.returncode, 0,
            f"precondition: init must succeed; stderr={self._result.stderr!r}",
        )
        selected = ("python", "rust")
        for stack in selected:
            for probe in _requirements.STACK_TOOLCHAINS[stack]:
                with self.subTest(stack=stack, probe=probe["name"]):
                    self.assertTrue(
                        _line_pairing(self._content, probe["name"], probe["remediation"]),
                        f"\u00a7S6: AGENTS.md for --stacks python,rust must name {stack}'s "
                        f"toolchain probe {probe['name']!r} with its remediation "
                        f"{probe['remediation']!r}; got content={self._content!r}",
                    )
        selected_names = {
            p["name"] for s in selected for p in _requirements.STACK_TOOLCHAINS[s]
        }
        for stack, probes in _requirements.STACK_TOOLCHAINS.items():
            if stack in selected:
                continue
            for probe in probes:
                if probe["name"] in selected_names:
                    continue
                self.assertFalse(
                    _names(self._content, probe["name"]),
                    f"\u00a7S6: unselected stack {stack!r}'s toolchain probe "
                    f"{probe['name']!r} must not be named; got content={self._content!r}",
                )
                self.assertNotIn(probe["remediation"], self._content)


class ScaffoldCapabilityContractRemediationOnlyTest(unittest.TestCase):
    """CR-MDB-036 cycle-91 finding 11 -- the scaffolded AGENTS.md states the
    remediation only: no installer-only wording (e.g. "named, never run by
    modelb-axi") in its capability contract, for every stack."""

    @classmethod
    def setUpClass(cls):
        cls._result, cls._content, cls._dirs = _run_init_subprocess(
            "arduino,bun,python,quarkus,rust,java",
        )

    @classmethod
    def tearDownClass(cls):
        for d in cls._dirs:
            shutil.rmtree(d, ignore_errors=True)

    def test_contract_carries_no_installer_only_wording(self):
        self.assertEqual(self._result.returncode, 0, self._result.stderr)
        start = self._content.find("## Harness capability contract")
        self.assertNotEqual(start, -1, f"precondition: contract present; {self._content!r}")
        end = self._content.find("\n## ", start + 1)
        section = self._content[start:end if end != -1 else None]
        for phrase in ("modelb-axi", "never run", "named,"):
            with self.subTest(phrase=phrase):
                self.assertNotIn(
                    phrase, section,
                    f"finding 11: installer-only wording in AGENTS.md; section={section!r}",
                )


class ScaffoldCapabilityContractReadsRequirementsDataTest(unittest.TestCase):
    """CR-MDB-036 \u00a7S1/\u00a7S6 -- the contract is DATA read by the scaffold
    ("adding a requirement touches only that structure"): changing a row in
    ``modelb_axi.requirements`` changes the scaffolded AGENTS.md, and the
    replaced text disappears. In-process ``scaffold.run_init`` (the only way
    to alter the data mid-run; same idiom as test_installer_correctness's
    ``_render_agents_md`` injection). The rows and the toolchain dict are
    mutated IN PLACE (``mock.patch.dict``), so the patch lands whatever
    import style the scaffold uses."""

    _SENTINEL_PROBE = {
        "name": "sentinel-probe-036",
        "kind": "binary",
        "remediation": "run sentinel-installer-036 --for-s6",
        "install": None,
    }
    _SENTINEL_TIER1_REMEDIATION = "pi install npm:sentinel-dispatch-036"

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-contract-data-home-")
        self._tmp_target = tempfile.mkdtemp(prefix="modelb-axi-contract-data-target-")
        self.addCleanup(shutil.rmtree, self._tmp_home, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self._tmp_target, ignore_errors=True)
        _write_install_toml(self._tmp_home, harnesses=("pi",))

    def test_agents_md_follows_the_requirements_data_not_a_copy(self):
        from modelb_axi import scaffold

        original_dispatch = _requirements.requirement("dispatch")["remediation"]
        original_python = [p["remediation"] for p in _requirements.STACK_TOOLCHAINS["python"]]
        args = argparse.Namespace(
            name="X", token="xproj", acronym="XP", mode="solo",
            repo_shape="standalone", stacks="python", owner="tester",
            target=self._tmp_target, dry_run=False, no_commit=True,
            register=False, harnesses=None,
        )
        with mock.patch.dict(
            _requirements.STACK_TOOLCHAINS, {"python": (dict(self._SENTINEL_PROBE),)},
        ), mock.patch.dict(
            _requirements.requirement("dispatch"),
            {"remediation": self._SENTINEL_TIER1_REMEDIATION},
        ), mock.patch.dict(
            # CR-MDB-037 migration: init reads Pi's agent dir (§S4 trust).
            os.environ, {AGENT_DIR_ENV: shared_provisioned_agent_dir()},
        ), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            exit_code = scaffold.run_init(args, Path(self._tmp_home))
        self.assertEqual(exit_code, 0, f"precondition: init must succeed; stderr={err.getvalue()!r}")
        content = (Path(self._tmp_target) / "AGENTS.md").read_text(encoding="utf-8")
        # POSITIVE -- the patched data is what is written, paired per line.
        self.assertTrue(
            _line_pairing(content, "dispatch", self._SENTINEL_TIER1_REMEDIATION),
            f"\u00a7S6: AGENTS.md must render the dispatch row's remediation from "
            f"the requirements data; got content={content!r}",
        )
        self.assertTrue(
            _line_pairing(content, self._SENTINEL_PROBE["name"], self._SENTINEL_PROBE["remediation"]),
            f"\u00a7S6: AGENTS.md must render the python toolchain from "
            f"STACK_TOOLCHAINS; got content={content!r}",
        )
        # NEGATIVE -- the replaced values are gone (no hand-copied strings).
        self.assertNotIn(original_dispatch, content)
        for remediation in original_python:
            self.assertNotIn(remediation, content)


class RegistryKeyDocPropagationTest(unittest.TestCase):
    """§S5 AC -- the repo-local `skills-src/model-b/SKILL.md` documents
    the full `.env` registry key set incl. REPO_OWNER and the scaffold
    as its instantiation path. This is a direct repo-file read (no
    subprocess) -- it is EXPECTED to fail until GREEN edits that
    repo-local file."""

    SKILL_MD_PATH = REPO_ROOT / "skills-src" / "model-b" / "SKILL.md"

    def test_skill_md_names_repo_owner_and_scaffold_instantiation_path(self):
        content = self.SKILL_MD_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "REPO_OWNER", content,
            "S5: SKILL.md must name REPO_OWNER among the registry keys; "
            f"got content head={content[:2000]!r}",
        )
        self.assertIn(
            "scaffold", content.lower(),
            "S5: SKILL.md must document the scaffold flow as the "
            f"registry's instantiation path; got content head={content[:2000]!r}",
        )


if __name__ == "__main__":
    unittest.main()
