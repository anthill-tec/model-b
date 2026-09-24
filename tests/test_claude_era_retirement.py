"""Claude-era substrate retirement — code (CR-MDB-031 §S1 and its §S5 tests; cycle C1).

Contract: ``docs/changes/CR-MDB-031-claude-era-substrate-retirement.md``. The target set is Pi
alone (DN §D13/§D14, §S0.5): the roster, the hook compiler, the deploy engine, the scaffold and the
CLI carry no Claude Code / Hermes / opencode substrate, and a stale harness id recorded by an older
install is refused with the recovery named.

Class map (one per C1 acceptance criterion):

- ``PiOnlyRosterTest`` — ``HARNESS_ROSTER == (("pi", "pi"),)``; ``detect_harnesses()`` probes
  exactly ``shutil.which("pi")``.
- ``SinglePiEmitterTest`` — ``hooks.py`` defines exactly one ``_emit_*`` (``_emit_pi``); a
  ``compile_wiring`` report entry carries no ``refusals`` key; a retired id is an unknown harness;
  ``AllTargetsRefusedError`` is defined nowhere under ``modelb_axi/``.
- ``RetiredHarnessNameGateTest`` — case-insensitive ``claude|hermes|opencode`` matches zero lines
  in ``modelb_axi/*.py``. This gate ALSO covers the AC "``cli.py`` help and
  ``resolve_target_root``'s docstring name no Claude surface" (``cli.py:78`` ``~/.claude``,
  ``cli.py:112`` ``claude-code,hermes``) — no second test duplicates it.
- ``RetiredScanDetectorTest`` — the two source scans above bite on synthetic fixtures.
- ``DeployHasNoHarnessLinkWriterTest`` — ``deploy.py`` defines no ``HARNESS_SKILL_DIRS`` (nor the
  ``_link_harness_skills`` writer §S1 deletes).
- ``PiOnlyInstallCreatesNoSymlinkTest`` — a REAL sandboxed Pi install creates no symlink anywhere
  under ``<target-root>`` and nothing under ``<target-root>/.claude/`` (regression pin: passes
  today for a Pi-only selection; its scan is proven by ``RetiredScanDetectorTest``).
- ``ScaffoldPiProjectTest`` — a sandboxed ``init``: no ``CLAUDE.md``, no ``.opencode/`` line, a
  ``.worktrees/`` line in ``.gitignore``; ``AGENTS.md`` cites
  ``docs/research/DN-model-b-language.md`` with no ``crucible:`` prefix (and the queue README's
  ontology line drops the prefix too, §S1 scope); ``_HARNESS_NATIVE_NOTES`` is gone.
- ``MemoryTemplateFamilyTest`` — ``--stacks quarkus`` and ``--stacks java`` scaffold all six
  ``java-*.md``; ``--stacks rust`` scaffolds ``rust-orchestration.md``; ``--stacks python`` neither.
- ``StaleHarnessIdRefusedTest`` — with ``install.toml`` recording ``harnesses = ["claude-code"]``,
  ``init``, ``agents`` and the installer flow (``--reinstall`` without ``--harnesses``) each exit
  non-zero, write nothing, and name ``claude-code`` and the ``--reinstall … --harnesses pi``
  recovery.
- ``CargoGuardSandboxBypassRetiredTest`` — ``block-direct-cargo-test`` carries no
  ``dangerouslyDisableSandbox`` and ignores the field; its real guard still blocks.

Isolation: every subprocess pins ``HOME``, ``MODELB_HOME`` (flag and env), ``XDG_DATA_HOME`` and
``PI_CODING_AGENT_DIR`` to sandboxes; installs pass ``--target-root`` to a sandbox. Nothing here
reads or writes the real ``~/.local/share/modelb``, ``~/.claude``, ``~/.pi`` or ``~/.crucible``.

Stdlib only.
"""

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from modelb_axi import deploy, harness, hooks, scaffold
from modelb_axi.harness import UnknownHarnessError
from tests import test_deployed_asset_freshness as freshness
from tests._helpers import decode_axi
from tests.pi_capability_sandbox import AGENT_DIR_ENV, shared_provisioned_agent_dir

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = REPO_ROOT / "modelb_axi"
HOOK_SCRIPTS = REPO_ROOT / "hooks-src" / "scripts"
MEMORY_TEMPLATES = REPO_ROOT / "skills-src" / "memory-templates"
CARGO_GUARD = HOOK_SCRIPTS / "block-direct-cargo-test"

#: The retired harness names (§S0.5): case-insensitive, anywhere on a line.
RETIRED_HARNESS_RE = re.compile(r"claude|hermes|opencode", re.IGNORECASE)

#: The ontology citation §S1 requires, and the undefined checkout prefix it retires.
ONTOLOGY_PATH = "docs/research/DN-model-b-language.md"
CHECKOUT_PREFIXED_ONTOLOGY = "crucible:" + ONTOLOGY_PATH

#: The stale id the real July install records, and the recovery §S1 requires every refusal to name
#: (``modelb-axi --reinstall … --harnesses pi``: ``--reinstall`` first, ``--harnesses pi`` later on
#: the same line).
STALE_ID = "claude-code"
RECOVERY_RE = re.compile(r"--reinstall\b.*--harnesses[ =]pi\b")

#: The six java memory templates the quarkus agent definitions tell the agent to read.
JAVA_TEMPLATES = frozenset(p.name for p in MEMORY_TEMPLATES.glob("java-*.md"))
RUST_TEMPLATES = frozenset(p.name for p in MEMORY_TEMPLATES.glob("rust-*.md"))


# ------------------------------------------------------------------ scans ----

def retired_harness_lines(package_dir: Path) -> list:
    """``"<file>:<n>: <line>"`` for every line of a top-level ``*.py`` in ``package_dir`` naming a
    retired harness (``RETIRED_HARNESS_RE``). Subdirectories and non-``.py`` files are out of scope
    (the AC names ``modelb_axi/*.py``)."""
    found = []
    for source in sorted(package_dir.glob("*.py")):
        numbered = enumerate(source.read_text(encoding="utf-8").splitlines(), start=1)
        found += [f"{source.name}:{n}: {text.strip()}" for n, text in numbered
                  if RETIRED_HARNESS_RE.search(text)]
    return found


def top_level_definitions(source: str) -> set:
    """Names bound at module level by ``def``/``class``/assignment in ``source``."""
    bound = set()
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            bound.update(t.id for t in targets if isinstance(t, ast.Name))
    return bound


def modules_defining(package_dir: Path, name: str) -> list:
    """Package-relative paths of every ``*.py`` under ``package_dir`` (recursive, ``__pycache__``
    skipped) that binds ``name`` at module level."""
    hits = []
    for source in sorted(package_dir.rglob("*.py")):
        if "__pycache__" in source.parts:
            continue
        if name in top_level_definitions(source.read_text(encoding="utf-8")):
            hits.append(source.relative_to(package_dir).as_posix())
    return hits


def symlinks_under(root: Path) -> list:
    """Root-relative POSIX paths of every symlink at or below ``root`` (links not followed)."""
    links = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for entry in dirnames + filenames:
            candidate = Path(dirpath, entry)
            if candidate.is_symlink():
                links.append(candidate.relative_to(root).as_posix())
    return sorted(links)


def tree_state(root: Path) -> dict:
    """``{relpath: fingerprint}`` of everything under ``root`` — ``("link", target)``,
    ``("file", sha256)`` or ``("dir",)`` — so any write, delete or new entry changes the result.
    ``{}`` when ``root`` does not exist."""
    state: dict = {}
    if not root.exists():
        return state
    for entry in sorted(root.rglob("*")):
        rel = entry.relative_to(root).as_posix()
        if entry.is_symlink():
            state[rel] = ("link", os.readlink(entry))
        elif entry.is_file():
            state[rel] = ("file", hashlib.sha256(entry.read_bytes()).hexdigest())
        else:
            state[rel] = ("dir",)
    return state


# ------------------------------------------------------------------ sandboxed runs ----

def sandbox_env(home: Path, modelb_home: Path, xdg: Path) -> dict:
    """The child env for a sandboxed ``python -m modelb_axi`` run: repo on ``PYTHONPATH``; ``HOME``,
    ``MODELB_HOME``, ``XDG_DATA_HOME`` and ``PI_CODING_AGENT_DIR`` all sandboxes; no
    ``MODELB_TARGET_ROOT`` leaking in from the parent."""
    env = {k: v for k, v in os.environ.items() if k != "MODELB_TARGET_ROOT"}
    inherited = env.get("PYTHONPATH")
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(REPO_ROOT), inherited]))
    env.update(HOME=str(home), MODELB_HOME=str(modelb_home), XDG_DATA_HOME=str(xdg))
    env[AGENT_DIR_ENV] = shared_provisioned_agent_dir()
    return env


def pi_install_toml(modelb_home: Path) -> Path:
    """A Pi-only ``install.toml`` whose hook-scripts dir is the repo's own ``hooks-src/scripts``
    (no asset root recorded: the scaffold falls back to the running package's assets)."""
    modelb_home.mkdir(parents=True, exist_ok=True)
    path = modelb_home / "install.toml"
    path.write_text(
        "\n".join((
            "[install]",
            'version = "0.1.0"',
            f"harnesses = {json.dumps(['pi'])}",
            f"hooks_scripts_dir = {json.dumps(str(HOOK_SCRIPTS))}",
            "",
            "[deps]",
            'uv = "present"',
            "",
            "[files]",
            "",
        )),
        encoding="utf-8",
    )
    return path


def init_argv(target: Path, stacks: str, modelb_home: Path) -> list:
    """``modelb-axi --yes init …`` for a solo, standalone project named Retire."""
    return ["--yes", "init", "--name", "Retire", "--token", "retire", "--acronym", "RET",
            "--mode", "solo", "--repo-shape", "standalone", "--stacks", stacks,
            "--owner", "tester", "--target", str(target), "--modelb-home", str(modelb_home)]


class _SandboxedInitCase(unittest.TestCase):
    """A per-class sandbox (home, MODELB_HOME, XDG) with a Pi-only ``install.toml``, and a runner
    for real ``init`` subprocesses into fresh targets under it."""

    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="mdb-031-retire-"))
        cls.home = cls.root / "home"
        cls.modelb_home = cls.root / "modelb-home"
        cls.xdg = cls.root / "xdg"
        for directory in (cls.home, cls.xdg):
            directory.mkdir(parents=True)
        pi_install_toml(cls.modelb_home)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    @classmethod
    def scaffold(cls, stacks: str) -> tuple:
        """Run a real ``init --stacks <stacks>`` into ``<root>/proj-<stacks>``; returns
        ``(completed process, target)``."""
        target = cls.root / f"proj-{stacks.replace(',', '-')}"
        completed = subprocess.run(
            [sys.executable, "-m", "modelb_axi", *init_argv(target, stacks, cls.modelb_home)],
            capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL,
            env=sandbox_env(cls.home, cls.modelb_home, cls.xdg), cwd=str(cls.root),
        )
        return completed, target


# ------------------------------------------------------------------ roster ----

class PiOnlyRosterTest(unittest.TestCase):
    """§S1/§S0.5 — the roster is Pi alone, and detection probes only the ``pi`` binary."""

    def test_roster_is_exactly_pi_probed_as_pi(self):
        self.assertEqual(
            harness.HARNESS_ROSTER, (("pi", "pi"),),
            "§S1: HARNESS_ROSTER must be (('pi', 'pi'),) — the claude-code/hermes/opencode rows "
            f"are retired (§S0.5); got {harness.HARNESS_ROSTER!r}",
        )
        self.assertEqual(harness.HARNESS_ROSTER_IDS, ("pi",),
                         f"§S1: the roster ids must be ('pi',); got {harness.HARNESS_ROSTER_IDS!r}")

    def test_detect_harnesses_finds_pi_through_a_single_which_pi_probe(self):
        with mock.patch.object(harness.shutil, "which",
                               side_effect=lambda name: "/sandbox/bin/pi" if name == "pi" else None
                               ) as which:
            detected = harness.detect_harnesses()
        self.assertEqual(detected, ["pi"], f"§S1: pi on PATH must be detected; got {detected!r}")
        probed = [c.args for c in which.call_args_list]
        self.assertEqual(
            probed, [("pi",)],
            "§S1: detect_harnesses() must probe exactly shutil.which('pi') — probing a retired "
            f"harness binary means the roster still carries it; probed {probed!r}",
        )

    def test_detect_harnesses_is_empty_when_pi_is_absent(self):
        with mock.patch.object(harness.shutil, "which", return_value=None) as which:
            detected = harness.detect_harnesses()
        self.assertEqual(detected, [], f"§S1: no pi on PATH detects nothing; got {detected!r}")
        which.assert_called_once_with("pi")


# ------------------------------------------------------------------ hook compiler ----

#: One neutral guard + one ambient hook, the shape every Pi scaffold compiles.
_GUARD = {"event": "pre-tool-use", "matcher": "bash", "command": "block-direct-cargo-test",
          "tier": "core", "timeout": 5, "fail_direction": "closed"}
_AMBIENT = {"event": "session-start", "matcher": "*", "command": "ambient-board-status",
            "tier": "core", "timeout": 3, "fail_direction": None}


class SinglePiEmitterTest(unittest.TestCase):
    """§S1 — ``hooks.py`` has one emitter and no refusal path."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="mdb-031-hooks-")
        self.target = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_hooks_defines_exactly_one_emitter_named_emit_pi(self):
        emitters = sorted(n for n in top_level_definitions(
            (PACKAGE_DIR / "hooks.py").read_text(encoding="utf-8")) if n.startswith("_emit_"))
        self.assertEqual(
            emitters, ["_emit_pi"],
            f"§S1: hooks.py must define exactly one _emit_* function (_emit_pi); got {emitters!r}",
        )

    def test_compile_wiring_report_entry_carries_no_refusals_key(self):
        report = hooks.compile_wiring([_GUARD, _AMBIENT], ["pi"], self.target, HOOK_SCRIPTS)
        self.assertEqual(list(report), ["pi"], f"§S1: one report entry, for pi; got {report!r}")
        entry = report["pi"]
        self.assertEqual(
            sorted(entry["emitted_files"]),
            [".pi/extensions/ambient-board-status.ts", ".pi/extensions/block-direct-cargo-test.ts"],
            f"§S1: both hooks are wired for pi; got {entry!r}",
        )
        self.assertNotIn(
            "refusals", entry,
            f"§S1: compile_wiring has no refusal path — a report entry carries no 'refusals' key; "
            f"got keys {sorted(entry)!r}",
        )

    def test_compile_wiring_rejects_a_retired_harness_id_and_writes_nothing(self):
        with self.assertRaises(UnknownHarnessError) as raised:
            hooks.compile_wiring([_AMBIENT], [STALE_ID], self.target, HOOK_SCRIPTS)
        message = str(raised.exception)
        self.assertIn(STALE_ID, message)
        self.assertIn("valid roster: pi", message,
                      f"§S1: the rejection names the Pi-only roster; got {message!r}")
        self.assertEqual(tree_state(self.target), {},
                         "§S1: a rejected harness id compiles no wiring at all")

    def test_all_targets_refused_error_is_defined_nowhere_in_the_package(self):
        self.assertEqual(
            modules_defining(PACKAGE_DIR, "AllTargetsRefusedError"), [],
            "§S1: AllTargetsRefusedError must not be defined anywhere under modelb_axi/ — with "
            "Pi alone there is no all-refused state",
        )
        self.assertFalse(hasattr(hooks, "AllTargetsRefusedError"),
                         "§S1: modelb_axi.hooks must not expose AllTargetsRefusedError")


# ------------------------------------------------------------------ retired-name gate ----

class RetiredHarnessNameGateTest(unittest.TestCase):
    """§S1 AC — case-insensitive ``claude|hermes|opencode`` matches zero lines under
    ``modelb_axi/*.py``. Covers ``cli.py``'s ``--harnesses``/``--target-root`` help and
    ``resolve_target_root``'s docstring (the "name no Claude surface" AC) — deliberately not
    duplicated elsewhere."""

    def test_package_modules_name_no_retired_harness(self):
        hits = retired_harness_lines(PACKAGE_DIR)
        self.assertEqual(
            hits, [],
            f"§S1: {len(hits)} line(s) in modelb_axi/*.py name a retired harness "
            "(claude|hermes|opencode, case-insensitive):\n  " + "\n  ".join(hits),
        )


class RetiredScanDetectorTest(unittest.TestCase):
    """The scans behind the gates bite on synthetic fixtures (and only where they should)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="mdb-031-detector-")
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_retired_name_scan_reports_each_spelling_and_ignores_out_of_scope_files(self):
        (self.root / "mod.py").write_text(
            '"""Deploys to ~/.claude."""\n'
            'ROSTER = ("HERMES", "pi")\n'
            "x = 1  # pi only\n"
            "PLUGIN = '.OpenCode/plugin'\n",
            encoding="utf-8",
        )
        (self.root / "notes.md").write_text("claude-code\n", encoding="utf-8")
        (self.root / "sub").mkdir()
        (self.root / "sub" / "deep.py").write_text("hermes = 1\n", encoding="utf-8")
        self.assertEqual(
            retired_harness_lines(self.root),
            ['mod.py:1: """Deploys to ~/.claude."""', 'mod.py:2: ROSTER = ("HERMES", "pi")',
             "mod.py:4: PLUGIN = '.OpenCode/plugin'"],
        )

    def test_definition_scan_finds_a_class_function_or_constant_but_not_a_mention(self):
        (self.root / "a.py").write_text("class AllTargetsRefusedError(Exception):\n    pass\n",
                                        encoding="utf-8")
        (self.root / "nested").mkdir()
        (self.root / "nested" / "b.py").write_text("HARNESS_SKILL_DIRS: dict = {}\n",
                                                   encoding="utf-8")
        (self.root / "c.py").write_text(
            '"""AllTargetsRefusedError is gone."""\nraise_it = "AllTargetsRefusedError"\n',
            encoding="utf-8")
        self.assertEqual(modules_defining(self.root, "AllTargetsRefusedError"), ["a.py"])
        self.assertEqual(modules_defining(self.root, "HARNESS_SKILL_DIRS"), ["nested/b.py"])
        self.assertIn("_link", top_level_definitions("def _link():\n    pass\n"))

    def test_symlink_scan_finds_a_harness_skill_link_the_retired_writer_created(self):
        store = self.root / ".agents" / "skills" / "crucible"
        store.mkdir(parents=True)
        (store / "SKILL.md").write_text("x\n", encoding="utf-8")
        link = self.root / ".claude" / "skills" / "crucible"
        link.parent.mkdir(parents=True)
        link.symlink_to(store)
        self.assertEqual(symlinks_under(self.root), [".claude/skills/crucible"])
        link.unlink()
        self.assertEqual(symlinks_under(self.root), [])


# ------------------------------------------------------------------ deploy ----

class DeployHasNoHarnessLinkWriterTest(unittest.TestCase):
    """§S1 — Pi reads ``~/.agents/skills`` natively (§D15.1): the per-harness link map and its
    writer are deleted."""

    def test_deploy_defines_no_harness_skill_dirs(self):
        self.assertEqual(modules_defining(PACKAGE_DIR, "HARNESS_SKILL_DIRS"), [],
                         "§S1: HARNESS_SKILL_DIRS must not be defined under modelb_axi/")
        self.assertFalse(hasattr(deploy, "HARNESS_SKILL_DIRS"),
                         f"§S1: deploy.HARNESS_SKILL_DIRS still exists: "
                         f"{getattr(deploy, 'HARNESS_SKILL_DIRS', None)!r}")

    def test_deploy_defines_no_harness_link_writer(self):
        self.assertFalse(hasattr(deploy, "_link_harness_skills"),
                         "§S1: deploy._link_harness_skills (the only per-harness writer, "
                         "targeting ~/.claude) must be deleted with its call")


class PiOnlyInstallCreatesNoSymlinkTest(freshness._InstalledMachineCase):
    """§S1 AC — a REAL sandboxed Pi install (``--harnesses pi --stacks bun`` into a sandbox
    ``--target-root``; ``HOME``/``PATH``/``MODELB_HOME``/``XDG_DATA_HOME``/``PI_CODING_AGENT_DIR``
    pinned by the fixture) creates no symlink anywhere under ``<target-root>`` and nothing under
    ``<target-root>/.claude/``. Regression pin: the retired writer only ever linked for
    ``claude-code``."""

    ROOT_PREFIX = "mdb-031-pi-install-"

    def test_pi_install_creates_no_symlink_and_nothing_under_dot_claude(self):
        self.assertEqual(self.load_install()["install"]["harnesses"], ["pi"],
                         "fixture: the install must be recorded for pi only")
        self.assertTrue((self.target_root / freshness.SKILL_REL).is_file(),
                        f"fixture: the Pi install must deploy {freshness.SKILL_REL}")
        self.assertEqual(symlinks_under(self.target_root), [],
                         "§S1: a Pi install must create no symlink under the target root")
        dot_claude = self.target_root / ".claude"
        self.assertFalse(dot_claude.exists() or dot_claude.is_symlink(),
                         f"§S1: a Pi install must create nothing under {dot_claude}")


# ------------------------------------------------------------------ scaffold ----

class ScaffoldPiProjectTest(_SandboxedInitCase):
    """§S1 AC — one real sandboxed ``init --stacks python`` for a Pi install, inspected."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.result, cls.target = cls.scaffold("python")

    def _require_scaffold(self):
        self.assertEqual(
            self.result.returncode, 0,
            f"fixture: the Pi init must succeed; exit={self.result.returncode} "
            f"axi={decode_axi(self.result.stdout)!r} stderr={self.result.stderr!r}",
        )

    def test_scaffold_emits_no_claude_md(self):
        self._require_scaffold()
        claude_md = self.target / "CLAUDE.md"
        self.assertFalse(claude_md.exists() or claude_md.is_symlink(),
                         "§S1: the scaffold emits no CLAUDE.md (file or symlink)")
        emitted = decode_axi(self.result.stdout).get("emitted") or []
        self.assertNotIn("CLAUDE.md", list(emitted), "§S1: no CLAUDE.md in the envelope's emitted")

    def test_gitignore_lists_worktrees_and_no_retired_harness_cache(self):
        self._require_scaffold()
        lines = [line.strip() for line in
                 (self.target / ".gitignore").read_text(encoding="utf-8").splitlines()]
        self.assertIn(".worktrees/", lines,
                      f"§S1/§S0.1: .gitignore must list .worktrees/; got {lines!r}")
        self.assertEqual(lines.count(".worktrees/"), 1, f"exactly one .worktrees/ line: {lines!r}")
        retired = [line for line in lines if line in (".opencode/", ".claude/", ".hermes/")]
        self.assertEqual(retired, [],
                         f"§S1: .gitignore must not ignore a retired harness cache; got {retired!r}")
        self.assertIn(".env.local", lines, "the overlay is still ignored")

    def test_agents_md_cites_the_repo_local_ontology_without_the_crucible_prefix(self):
        self._require_scaffold()
        agents_md = (self.target / "AGENTS.md").read_text(encoding="utf-8")
        self.assertNotIn(CHECKOUT_PREFIXED_ONTOLOGY, agents_md,
                         "§S1: AGENTS.md must not use the undefined crucible: ontology prefix")
        self.assertIn(
            ONTOLOGY_PATH, agents_md,
            f"§S1 AC: the rendered AGENTS.md must name {ONTOLOGY_PATH}; got {agents_md!r}",
        )

    def test_queue_readme_ontology_line_has_no_crucible_prefix(self):
        self._require_scaffold()
        readme = (self.target / "docs" / "changes" / "README.md").read_text(encoding="utf-8")
        ontology = [line for line in readme.splitlines() if "Ontology" in line]
        self.assertEqual(len(ontology), 1, f"one ontology slot in the queue README: {readme!r}")
        self.assertIn(ONTOLOGY_PATH, ontology[0])
        self.assertNotIn(
            "crucible:", ontology[0],
            f"§S1: the ontology line cites {ONTOLOGY_PATH} with no crucible: prefix; "
            f"got {ontology[0]!r}",
        )

    def test_scaffold_carries_no_harness_native_notes_table(self):
        self.assertFalse(hasattr(scaffold, "_HARNESS_NATIVE_NOTES"),
                         "§S1: scaffold._HARNESS_NATIVE_NOTES (hermes/opencode notes) is deleted")


class MemoryTemplateFamilyTest(_SandboxedInitCase):
    """§S1 AC — a ``<prefix>-*.md`` memory template is emitted when any stack of its family is
    selected: ``java-*`` for ``java`` or ``quarkus``, ``rust-*`` for ``rust``."""

    def _memory_files(self, stacks: str) -> set:
        result, target = self.scaffold(stacks)
        self.assertEqual(result.returncode, 0,
                         f"fixture: init --stacks {stacks} must succeed; stderr={result.stderr!r}")
        memory = target / "docs" / "memory"
        return {p.name for p in memory.glob("*.md")}

    def test_fixture_has_six_java_and_one_rust_template(self):
        self.assertEqual(len(JAVA_TEMPLATES), 6, f"the six java-* templates: {JAVA_TEMPLATES!r}")
        self.assertEqual(RUST_TEMPLATES, {"rust-orchestration.md"})

    def test_quarkus_scaffolds_all_six_java_templates(self):
        files = self._memory_files("quarkus")
        self.assertEqual(
            sorted(JAVA_TEMPLATES - files), [],
            "§S1: --stacks quarkus must scaffold every java-*.md template its agent definitions "
            f"cite; scaffolded {sorted(files)!r}",
        )
        self.assertEqual(sorted(RUST_TEMPLATES & files), [], "no rust template for quarkus")

    def test_java_scaffolds_all_six_java_templates(self):
        files = self._memory_files("java")
        self.assertEqual(sorted(JAVA_TEMPLATES - files), [],
                         f"§S1: --stacks java scaffolds every java-*.md; got {sorted(files)!r}")

    def test_rust_scaffolds_rust_orchestration_and_no_java_template(self):
        files = self._memory_files("rust")
        self.assertIn("rust-orchestration.md", files, f"§S1: got {sorted(files)!r}")
        self.assertEqual(sorted(JAVA_TEMPLATES & files), [], "no java template for rust")

    def test_python_scaffolds_neither_family_but_the_stack_neutral_template(self):
        files = self._memory_files("python")
        self.assertEqual(sorted((JAVA_TEMPLATES | RUST_TEMPLATES) & files), [],
                         f"§S1: --stacks python scaffolds neither family; got {sorted(files)!r}")
        self.assertIn("operational-commands.md", files, "stack-neutral templates are still emitted")


# ------------------------------------------------------------------ stale harness id ----

class StaleHarnessIdRefusedTest(freshness._InstalledMachineCase):
    """§S1 AC — after a real sandboxed install, ``install.toml`` is rewritten to record
    ``harnesses = ["claude-code"]`` (the real July install's shape). Each of ``init``, ``agents``
    and the installer flow (``--reinstall`` without ``--harnesses``) must exit non-zero, write
    nothing, and name ``claude-code`` and the ``--reinstall … --harnesses pi`` recovery."""

    ROOT_PREFIX = "mdb-031-stale-id-"

    def setUp(self):
        super().setUp()
        # The fixture's PATH is a fake-bin dir; `init` needs the real git (a missing git would fail
        # init for the wrong reason and mask the defect).
        real_git = shutil.which("git")
        if real_git is None:
            self.fail("fixture: git must be on the parent PATH")
        (self.bin_dir / "git").symlink_to(real_git)
        data = self.load_install()
        self.assertEqual(data["install"]["harnesses"], ["pi"], "fixture: installed for pi")
        data["install"]["harnesses"] = [STALE_ID]
        self.write_install(data)
        self.assertEqual(self.load_install()["install"]["harnesses"], [STALE_ID],
                         "fixture: install.toml now records the stale id")

    def _run(self, argv: list, cwd: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "modelb_axi", *argv],
            capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL,
            env=self._env(), cwd=str(cwd),
        )

    def _assert_refused(self, verb: str, result, before: dict, after: dict):
        output = result.stdout + result.stderr
        self.assertNotEqual(
            result.returncode, 0,
            f"§S1: {verb} with install.toml harnesses=['claude-code'] must exit non-zero; "
            f"got exit=0 axi={decode_axi(result.stdout)!r} stderr={result.stderr!r}",
        )
        self.assertIn(STALE_ID, output, f"§S1: the {verb} refusal must name {STALE_ID!r}")
        self.assertRegex(
            output, RECOVERY_RE,
            f"§S1: the {verb} refusal must name the recovery "
            f"`modelb-axi --reinstall … --harnesses pi`; got {output!r}",
        )
        changed = sorted(set(before.items()) ^ set(after.items()))
        self.assertEqual(changed, [], f"§S1: a refused {verb} must write nothing; changed={changed!r}")

    def _world(self, *extra: Path) -> dict:
        roots = {"home": self.modelb_home, "target": self.target_root}
        roots.update({f"extra{n}": p for n, p in enumerate(extra)})
        return {(label, rel): fp for label, root in roots.items()
                for rel, fp in tree_state(root).items()}

    def test_init_refuses_the_stale_id_naming_the_recovery_and_writes_nothing(self):
        project = self._root / "project"
        before = self._world(project)
        result = self._run(init_argv(project, "bun", self.modelb_home), self.cwd)
        self._assert_refused("init", result, before, self._world(project))
        self.assertFalse(project.exists(), "§S1: a refused init creates no --target")

    def test_agents_refuses_the_stale_id_naming_the_recovery_and_writes_nothing(self):
        project = self._root / "agents-project"
        project.mkdir()
        (project / ".env").write_text("PROJECT_TOKEN=retire\nPROJECT_STACKS=bun\n",
                                      encoding="utf-8")
        before = self._world(project)
        result = self._run(["agents", "--modelb-home", str(self.modelb_home)], project)
        self._assert_refused("agents", result, before, self._world(project))

    def test_installer_flow_refuses_the_stale_id_naming_the_recovery_and_writes_nothing(self):
        before = self._world()
        result = self._run(
            ["--yes", "--reinstall", "--modelb-home", str(self.modelb_home),
             "--target-root", str(self.target_root), "--stacks", "bun"],
            self.cwd,
        )
        self._assert_refused("the installer flow", result, before, self._world())
        # The named recovery works: the same re-run with --harnesses pi reinstalls for pi.
        recovered = self._run(
            ["--yes", "--reinstall", "--modelb-home", str(self.modelb_home),
             "--target-root", str(self.target_root), "--stacks", "bun", "--harnesses", "pi"],
            self.cwd,
        )
        self.assertEqual(decode_axi(recovered.stdout).get("outcome"), "installed",
                         f"the recovery re-run must install; stderr={recovered.stderr!r}")
        self.assertEqual(self.load_install()["install"]["harnesses"], ["pi"])


# ------------------------------------------------------------------ cargo guard ----

class CargoGuardSandboxBypassRetiredTest(unittest.TestCase):
    """§S1 — the ``dangerouslyDisableSandbox`` branch (a Claude Code Bash-tool field Pi's ``bash``
    tool does not have) is deleted: the text is gone, the field changes nothing, and the real
    cargo guard still blocks."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="mdb-031-cargo-")
        self.project = Path(self._tmp.name)
        (self.project / "Cargo.toml").write_text("[package]\nname = 'x'\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def _guard(self, tool_input: dict) -> subprocess.CompletedProcess:
        payload = {"tool_name": "bash", "tool_input": tool_input, "cwd": str(self.project)}
        return subprocess.run([sys.executable, str(CARGO_GUARD)], input=json.dumps(payload),
                              capture_output=True, text=True, timeout=15)

    def test_cargo_guard_source_carries_no_sandbox_bypass_closer(self):
        text = CARGO_GUARD.read_text(encoding="utf-8")
        hits = [n for n, line in enumerate(text.splitlines(), start=1)
                if "dangerouslyDisableSandbox" in line or "DS_REASON" in line]
        self.assertEqual(hits, [], "§S1: block-direct-cargo-test still names "
                                   f"dangerouslyDisableSandbox/DS_REASON on lines {hits!r}")

    def test_sandbox_field_does_not_change_the_verdict_on_a_non_test_cargo_command(self):
        plain = self._guard({"command": "cargo build"})
        flagged = self._guard({"command": "cargo build", "dangerouslyDisableSandbox": True})
        self.assertEqual(plain.returncode, 0, f"cargo build is allowed; stdout={plain.stdout!r}")
        self.assertEqual(
            flagged.returncode, plain.returncode,
            "§S1: the retired dangerouslyDisableSandbox field must not change the guard's verdict; "
            f"got exit={flagged.returncode} stdout={flagged.stdout!r}",
        )

    def test_cargo_guard_still_blocks_direct_cargo_test(self):
        blocked = self._guard({"command": "cargo test"})
        self.assertEqual(blocked.returncode, 2, blocked.stderr)
        self.assertEqual(json.loads(blocked.stdout)["decision"], "block")


if __name__ == "__main__":
    unittest.main()
