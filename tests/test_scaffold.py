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
`~/.claude` or `~/.agents`. Reuses the AC7-style module-level mtime sandbox
guard from `tests/test_installer.py`.

Stdlib only: ast + unittest + subprocess + sys + os + shutil + tempfile +
importlib.util + pathlib.
"""

import ast
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_DIR = REPO_ROOT / "modelb_axi"

CLAUDE_DIR = Path.home() / ".claude"
AGENTS_HOME_DIR = Path.home() / ".agents"
# Sandbox guard (mirrors tests/test_installer.py's AC7 slice): these two
# real, live trees must never be touched by anything in this test module.
_GUARD_DIRS = [CLAUDE_DIR / "skills", AGENTS_HOME_DIR]

# READ-ONLY test-side import of Crucible's TOON codec -- production
# `modelb_axi` code must never depend on it; the envelope is Model B's own
# emitter per contracts/crucible-envelope.md's non-client-adopter shape.
TOON_CODEC_PATH = (
    Path.home() / "Documents" / "data_projects" / "crucible" / "clients" / "toon.py"
)


def _snapshot_mtimes(roots):
    """Best-effort recursive mtime snapshot of `roots` for the sandbox
    guard."""
    snap = {}
    for root in roots:
        if not root.exists():
            continue
        snap[root] = root.stat().st_mtime
        for child in root.rglob("*"):
            try:
                snap[child] = child.stat().st_mtime
            except OSError:
                continue
    return snap


_guard_snapshot_before = {}


def setUpModule():
    global _guard_snapshot_before
    _guard_snapshot_before = _snapshot_mtimes(_GUARD_DIRS)


def tearDownModule():
    after = _snapshot_mtimes(_GUARD_DIRS)
    if after != _guard_snapshot_before:
        all_paths = set(_guard_snapshot_before) | set(after)
        changed = sorted(
            str(p) for p in all_paths
            if _guard_snapshot_before.get(p) != after.get(p)
        )
        raise AssertionError(
            "sandbox guard violated: the real ~/.claude/skills and/or "
            "~/.agents tree changed mtime while running "
            f"tests/test_scaffold.py; changed paths (up to 20): {changed[:20]}"
        )


def _run_module(*args, env_overrides=None, timeout=15, stdin=subprocess.DEVNULL):
    """Invoke `python -m modelb_axi <args>` with the repo root on
    PYTHONPATH (mirrors tests/test_installer.py's `_run_module`), so a
    not-yet-existing subcommand surfaces as a clean subprocess-level
    argparse failure instead of an in-process error."""
    env = dict(os.environ)
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + existing_pp if existing_pp else "")
    if env_overrides:
        env.update(env_overrides)
    cmd = [sys.executable, "-m", "modelb_axi", *args]
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, stdin=stdin, env=env,
    )


def _write_install_toml(home: str, harnesses=("claude-code",)) -> Path:
    """Valid install.toml fixture -- the seam §S2 reads the installed
    harness set from (DN-scaffold-packaging.md §3). Records
    ``hooks_scripts_dir`` as every install after CR-MDB-033 §S1 does,
    pointed at the sandbox (never the real home)."""
    harnesses_toml = ", ".join(f'"{h}"' for h in harnesses)
    hooks_scripts_dir = Path(home) / ".agents" / "hooks" / "scripts"
    install_toml = Path(home) / "install.toml"
    install_toml.write_text(
        "[install]\n"
        'version = "0.1.0"\n'
        f"harnesses = [{harnesses_toml}]\n"
        'asset_root = "/tmp/does-not-matter-for-this-test"\n'
        f'hooks_scripts_dir = "{hooks_scripts_dir}"\n'
        "\n"
        "[deps]\n"
        'uv = "present"\n'
        "\n"
        "[files]\n",
        encoding="utf-8",
    )
    return install_toml


def _load_toon_codec():
    """READ-ONLY import of Crucible's TOON codec for TEST-side parsing
    only."""
    spec = importlib.util.spec_from_file_location(
        "crucible_toon_readonly_for_tests", TOON_CODEC_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _parse_env_file(path: Path) -> dict:
    """Minimal ``KEY=VALUE`` parser for the emitted ``.env``/``.env.local``
    files (values may be bare or double-quoted; blank lines and
    ``#``-comments are skipped) -- test-side only, no production coupling."""
    values: dict = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, raw_value = stripped.partition("=")
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1]
        values[key.strip()] = value
    return values


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
            "--yes", *self._full_flags(harnesses="claude-code"),
            "--modelb-home", self._tmp_home,
        )
        self.assertEqual(
            result.returncode, 0,
            "S2: `init --dry-run --harnesses claude-code` without "
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
    harness set = claude-code per the test's install.toml fixture) emits
    the full committed set: registry `.env`/`.env.local`, the docs model,
    `AGENTS.md` + the claude-code anchor, in-repo memory, the git+commit
    state, and the hooks seam note. One subprocess run shared read-only
    across the test methods below (mirrors the class-level shared-fixture
    style already used for HarnessTargetingTest in test_installer.py)."""

    @classmethod
    def setUpClass(cls):
        cls._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-emit-home-")
        cls._tmp_target = tempfile.mkdtemp(prefix="modelb-axi-emit-target-")
        _write_install_toml(cls._tmp_home, harnesses=("claude-code",))
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
        self.assertIn(
            "python", content.lower(),
            f"S3.3: AGENTS.md must carry the python skill-freeze content; got content={content!r}",
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
        claude_md = self._target / "CLAUDE.md"
        self.assertTrue(
            claude_md.is_symlink(),
            "S3.3: CLAUDE.md must be a symlink for the claude-code anchor; "
            f"target listing={list(self._target.iterdir()) if self._target.exists() else 'MISSING'}",
        )
        self.assertEqual(
            claude_md.resolve(), agents_path.resolve(),
            "S3.3: CLAUDE.md symlink must resolve to AGENTS.md; got resolved="
            f"{claude_md.resolve() if claude_md.exists() else 'MISSING'}",
        )

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
        per-harness report, naming the installed harness ("claude-code")
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
            "claude-code", content,
            "S5: hooks/README.md must carry the compiler report naming the "
            f"emitted harness 'claude-code'; got content={content!r}",
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
    """§S5 AC (CR-MDB-015) -- a solo, single-stack `rust` init (claude-code
    -only install.toml fixture) fills the hooks seam: stack/mode-derived
    neutral-schema TOML instances land under `hooks/instances/<command>.toml`
    (one instance per hook -- schema.md v1's "one instance per hook" line),
    and the §S4 compiler wires the emitted instances into
    `.claude/settings.json` for the installed claude-code harness.

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
        _write_install_toml(cls._tmp_home, harnesses=("claude-code",))
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

    def test_claude_code_settings_json_wires_cargo_guard_and_ambient_status_commands(self):
        settings_path = self._target / ".claude" / "settings.json"
        self.assertTrue(
            settings_path.is_file(),
            "S5: compiled claude-code wiring must land at "
            f".claude/settings.json under --target; init stderr={self._result.stderr!r}",
        )
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        hooks_by_event = settings.get("hooks", {})

        def _commands_for(event):
            return [
                spec.get("command", "")
                for entry in hooks_by_event.get(event, [])
                for spec in entry.get("hooks", [])
            ]

        def _all_commands():
            commands = []
            for event in hooks_by_event:
                commands.extend(_commands_for(event))
            return commands

        # POSITIVE -- the cargo guard is wired under PreToolUse.
        pre_tool_commands = _commands_for("PreToolUse")
        self.assertTrue(
            any(cmd.endswith("block-direct-cargo-test") for cmd in pre_tool_commands),
            "S5: PreToolUse must wire the cargo guard; got PreToolUse commands="
            f"{pre_tool_commands!r} (full settings={settings!r})",
        )
        # POSITIVE -- ambient-board-status is wired under SessionStart.
        session_start_commands = _commands_for("SessionStart")
        self.assertTrue(
            any(cmd.endswith("ambient-board-status") for cmd in session_start_commands),
            "S5: SessionStart must wire ambient-board-status; got SessionStart "
            f"commands={session_start_commands!r} (full settings={settings!r})",
        )
        # NEGATIVE / bound -- zero mvn/worktree/cr-completed commands
        # anywhere in the compiled wiring.
        forbidden = (
            "block-direct-mvn-test", "block-write-outside-worktree",
            "block-cr-completed-without-spec-update",
        )
        leaked = [
            cmd for cmd in _all_commands()
            if any(cmd.endswith(f) for f in forbidden)
        ]
        self.assertEqual(
            leaked, [],
            "S5: solo/rust wiring must carry zero mvn/worktree/CR-completion "
            f"commands; found {leaked!r} in settings={settings!r}",
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
        _write_install_toml(cls._tmp_home, harnesses=("claude-code",))
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

    RUN CONTEXT -- one `--mode multi:2 --stacks rust,java --harnesses
    claude-code,pi` init fixture, shared by every test method below: multi
    mode + rust + java together select ALL FOUR block-* instances (see
    HooksSeamSoloRustEmissionTest's derived selection table), and `pi` in
    the installed harness roster makes the \u00a7S4 compiler
    (`hooks.compile_wiring` -> `_emit_pi`) emit one `.pi/extensions/
    <command>.ts` per instance.
    """

    @classmethod
    def setUpClass(cls):
        cls._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-pi-worktree-home-")
        cls._tmp_target = tempfile.mkdtemp(prefix="modelb-axi-pi-worktree-target-")
        _write_install_toml(cls._tmp_home, harnesses=("claude-code", "pi"))
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


class HarnessAnchorMatrixTest(unittest.TestCase):
    """§S3.3 AC -- per-harness anchors are emitted ONLY for the harnesses
    the INSTALLATION declares. `DN-harness-agnostic-hooks.md` §2 surveys
    Codex/Gemini/Cursor/Copilot/opencode/Amp project-config paths but
    names neither `Hermes` nor `pi` (pi.dev) at all, and even for
    opencode gives only a plugin mechanism (no concrete anchor-file
    path) -- so for all three of hermes/pi/opencode the DN supplies no
    concrete anchor location and §S3.3's fallback applies: "where a
    harness reads AGENTS.md natively, emit nothing and note it" i.e. a
    documented native-AGENTS.md note naming the harness, not a separate
    anchor file."""

    def _run_with_harnesses(self, harnesses):
        tmp_home = tempfile.mkdtemp(prefix="modelb-axi-anchor-home-")
        tmp_target = tempfile.mkdtemp(prefix="modelb-axi-anchor-target-")
        self.addCleanup(shutil.rmtree, tmp_home, ignore_errors=True)
        self.addCleanup(shutil.rmtree, tmp_target, ignore_errors=True)
        _write_install_toml(tmp_home, harnesses=harnesses)
        result = _run_module(
            "--yes", "init",
            "--name", "X", "--token", "xproj", "--acronym", "XP",
            "--mode", "solo", "--repo-shape", "standalone",
            "--stacks", "python", "--owner", "tester",
            "--target", tmp_target,
            "--modelb-home", tmp_home,
        )
        return result, Path(tmp_target)

    def test_all_four_installed_harnesses_get_documented_anchors(self):
        result, target = self._run_with_harnesses(
            ("claude-code", "hermes", "pi", "opencode"),
        )
        claude_md = target / "CLAUDE.md"
        self.assertTrue(
            claude_md.is_symlink(),
            f"S3.3: CLAUDE.md symlink anchor must exist for claude-code; "
            f"init stderr={result.stderr!r}",
        )
        agents_path = target / "AGENTS.md"
        self.assertTrue(
            agents_path.is_file(),
            f"S3.3: AGENTS.md must be emitted; init stderr={result.stderr!r}",
        )
        content = agents_path.read_text(encoding="utf-8").lower()
        for marker in ("hermes", "pi.dev", "opencode"):
            self.assertIn(
                marker, content,
                "S3.3: with all four roster harnesses installed, AGENTS.md "
                f"must carry a native-anchor note naming {marker!r}; got content={content!r}",
            )

    def test_claude_only_install_emits_no_hermes_pi_opencode_anchors(self):
        result, target = self._run_with_harnesses(("claude-code",))
        claude_md = target / "CLAUDE.md"
        self.assertTrue(
            claude_md.is_symlink(),
            f"S3.3: CLAUDE.md symlink anchor must still exist for claude-code; "
            f"init stderr={result.stderr!r}",
        )
        agents_path = target / "AGENTS.md"
        content = agents_path.read_text(encoding="utf-8").lower() if agents_path.is_file() else ""
        for marker in ("hermes", "pi.dev", "opencode"):
            self.assertNotIn(
                marker, content,
                "S3.3: with only claude-code installed, NO hermes/pi/opencode "
                f"anchor note may appear; found {marker!r} in content={content!r}",
            )


class MonorepoEmissionTest(unittest.TestCase):
    """§S3 AC -- `--repo-shape monorepo:a,b` emits per-sub-project `.env`
    + `AGENTS.md` under each sub-project dir (`a/`, `b/`)."""

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-mono-home-")
        self._tmp_target = tempfile.mkdtemp(prefix="modelb-axi-mono-target-")
        _write_install_toml(self._tmp_home, harnesses=("claude-code",))

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
        _write_install_toml(self._tmp_home, harnesses=("claude-code",))

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
        _write_install_toml(self._tmp_home, harnesses=("claude-code",))

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
