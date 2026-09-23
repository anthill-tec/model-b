"""RED-phase tests for CR-MDB-014 cycle C4 (§S7 -- skill-source imports +
generator retarget).

Written before any of §S7's production code lands:
  - `skills-src/` on this branch contains only `crucible/` (CR-MDB-011) and
    `memory-templates/`; the six imports (`model-b`, `cr-authoring`,
    `git-workflow`, `chezmoi`, `bootstrap`, `shutdown`) do not exist yet, so
    the bundle-fidelity and deploy-discovery tests below fail cleanly.
  - `generator/build.py`'s `AGENTS_DIR` constant still resolves to the real
    `Path.home() / ".claude" / "agents"` (pre-S7), so the CLI-retarget and
    generated-assets tests below fail against the live output location.

RED-PINNED RETARGET CONTRACT (AC6, documented per the dispatch instructions
-- GREEN must implement exactly this, the minimal change that preserves
`--check`/`--list`/`build`'s existing logic):

    generator/build.py's `AGENTS_DIR` module constant moves from
        Path.home() / ".claude" / "agents"
    to the repo-local package asset path
        <repo_root>/generator/agents/

`generator/` is already a declared asset root (§S2 context: "Package data
wires in the asset roots (skills-src/, generator/, contracts/, scripts)"),
so colocating the regenerated agent `.md` files as `generator/agents/`
siblings of `templates/`/`stacks/` needs no new asset-root wiring -- just
retargeting the one constant. `--list`/`--check`/`build` keep their exact
current control flow; they just resolve a different `AGENTS_DIR`.

Nothing in this module ever invokes `generator/build.py`'s `build`
sub-command against today's (pre-retarget) code, because that command
would write into the REAL `~/.claude/agents/` -- forbidden for this agent
and for the whole test suite (repo-local authoring rule / AC7). Instead:
  - the CLI-retarget test only drives the read-only `--list`/`--check`
    sub-commands (never `build`);
  - the generated-assets test never shells out to `build.py` at all -- it
    imports the module (pure, no I/O) and compares its own `render()`
    output against files already expected to live at the pinned
    `generator/agents/` location (GREEN is expected to have run `build`
    once, post-retarget, to produce and commit those files as repo
    assets -- exactly the pattern `tests/test_agent_generator.py` already
    uses for the live `~/.claude/agents/` tree pre-S7).

Stdlib only: unittest + subprocess + sys + shutil + tempfile +
tomllib + importlib.util + pathlib + hashlib + re (CR-MDB-021 §S4 --
git-backed byte-identity gate + prose-instruction matcher).
"""

import ast
import hashlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_SRC_DIR = REPO_ROOT / "skills-src"
GENERATOR_DIR = REPO_ROOT / "generator"
BUILD_PY = GENERATOR_DIR / "build.py"
# The RED-pinned retarget contract's output dir (see module docstring).
GENERATOR_AGENTS_DIR = GENERATOR_DIR / "agents"

# CR-MDB-021 §S1 -- the three roots the chezmoi-invocation gate scans.
# hooks-src/scripts/ holds extensionless-but-python3 neutral hook scripts
# (see hooks-src/schema.md), so it is walked separately from the .py globs
# used for tests/ and modelb_axi/.
CHEZMOI_INVOCATION_SCAN_ROOTS = (
    REPO_ROOT / "tests",
    REPO_ROOT / "modelb_axi",
    REPO_ROOT / "hooks-src" / "scripts",
)

CLAUDE_SKILLS_DIR = Path.home() / ".claude" / "skills"

# CR-MDB-016 Sec1/AC4 -- the 7 handover bundles (crucible-register +
# crucible-report-{arduino,bun,java,python,rust,vscode}), imported from
# crucible:clients/skills/ -- extending this file's durable
# coverage-superset fidelity gate + bundle-discovery guard to cover them.
CRUCIBLE_HANDOVER_BUNDLE_NAMES = (
    "crucible-register",
    "crucible-report-arduino",
    "crucible-report-bun",
    "crucible-report-java",
    "crucible-report-python",
    "crucible-report-rust",
    "crucible-report-vscode",
)
ORIGIN_CRUCIBLE_SKILLS_DIR = (
    Path.home() / "Documents" / "data_projects" / "crucible" / "clients" / "skills"
)

# §S7's six Model B-owned skill imports (crucible is the pre-existing 011
# authorship -- guarded, not re-imported).
IMPORTED_BUNDLE_NAMES = (
    "model-b",
    "cr-authoring",
    "git-workflow",
    "chezmoi",
    "bootstrap",
    "shutdown",
)
CRUCIBLE_BUNDLE_NAME = "crucible"
ALL_SEVEN_BUNDLE_NAMES = frozenset(IMPORTED_BUNDLE_NAMES) | {CRUCIBLE_BUNDLE_NAME}

# CR-MDB-024 \u00a7S2 -- rust joined the generator as a fifth stack (16 -> 20).
STACKS = ("arduino", "bun", "python", "quarkus", "rust")
ROLES = ("red", "green", "verify", "fix")

# §S6 (CR-MDB-015) -- the shared protocol script library that must ship as
# packaged data and get deployed user-scope, once, by the installer.
# MIGRATED (CR-MDB-030 §S7, this cycle): the cycle-todo-naming guard
# retired -- six scripts now, not seven; its own nonexistence is
# tests/test_hook_retirement.py's job, not this deploy-shape pin's.
HOOKS_SRC_DIR = REPO_ROOT / "hooks-src"
HOOKS_SRC_SCRIPTS_DIR = HOOKS_SRC_DIR / "scripts"
HOOK_SCRIPT_NAMES = (
    "ambient-board-status",
    "block-cr-completed-without-spec-update",
    "block-direct-cargo-test",
    "block-direct-mvn-test",
    "block-write-outside-worktree",
    "post-regression-disk-reminder",
)


def _relative_file_set(root: Path) -> set:
    return {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}


def _load_build_module():
    """Import generator/build.py as a standalone module (pure -- no I/O,
    never invokes cmd_build/cmd_check/cmd_list). generator/ has no
    __init__.py so this goes through importlib.util rather than a normal
    package import."""
    spec = importlib.util.spec_from_file_location("_cr_mdb_014_c4_build", BUILD_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_fake_executable(bin_dir: str, name: str, script_body: str) -> Path:
    path = Path(bin_dir) / name
    path.write_text(script_body, encoding="utf-8")
    path.chmod(0o755)
    return path


_FAKE_UV_SCRIPT = (
    "#!/bin/sh\n"
    'if [ "$1" = "tool" ] && [ "$2" = "install" ]; then\n'
    "    exit 0\n"
    "fi\n"
    'echo "uv 0.0.0-fake"\n'
    "exit 0\n"
)
_FAKE_SANDESH_SCRIPT = (
    "#!/bin/sh\n"
    'echo "sandesh-relay 0.0.0-fake"\n'
    "exit 0\n"
)


def _run_module(*args, env_overrides=None, timeout=20):
    env = dict(os.environ)
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + existing_pp if existing_pp else "")
    if env_overrides:
        env.update(env_overrides)
    cmd = [sys.executable, "-m", "modelb_axi", *args]
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout,
        stdin=subprocess.DEVNULL, env=env,
    )


class ImportedSkillBundleFidelityTest(unittest.TestCase):
    """AC6 pin #1 (amended, CR-MDB-013 F1 orchestrator disposition) -- the
    six imported bundles exist under skills-src/ with a SKILL.md, and each
    bundle's relative-path file set is a SUPERSET of the deployed
    ~/.claude/skills/<name>/ set (a deletion would break deployed
    consumers; evolution/additions are fine).

    Byte-for-byte fidelity was an IMPORT-TIME property, verified at
    CR-MDB-014 C4 (2026-07-22). Under the repo-local authoring rule the
    repo copy deliberately evolves AHEAD of the deployed tree between
    installer deploys (e.g. CR-MDB-013 §S5 evolved
    skills-src/model-b/SKILL.md), so per-file sha256 equality no longer
    holds by design and is no longer asserted here."""

    def test_each_imported_bundle_exists_and_covers_deployed_file_set(self):
        failures = []
        for name in IMPORTED_BUNDLE_NAMES:
            deployed_dir = CLAUDE_SKILLS_DIR / name
            imported_dir = SKILLS_SRC_DIR / name
            # The pin is explicit: a missing deployed dir must FAIL with a
            # clear message, never be silently skipped.
            if not deployed_dir.is_dir():
                failures.append(
                    f"{name}: deployed dir {deployed_dir} does not exist -- "
                    f"cannot verify the import covers it"
                )
                continue
            if not (imported_dir / "SKILL.md").is_file():
                failures.append(
                    f"{name}: skills-src/{name}/SKILL.md does not exist "
                    f"(import not yet authored)"
                )
                continue
            deployed_files = _relative_file_set(deployed_dir)
            imported_files = _relative_file_set(imported_dir)
            missing = sorted(deployed_files - imported_files)
            if missing:
                failures.append(
                    f"{name}: repo bundle must cover every deployed file "
                    f"(superset of {deployed_dir}); missing from "
                    f"skills-src/{name}/: {missing}"
                )
        # POSITIVE/EXACT -- every one of the six bundles exists and covers
        # the deployed file set completely; zero deletions.
        self.assertEqual(failures, [], "\n".join(failures))


class CrucibleHandoverBundleFidelityTest(unittest.TestCase):
    """CR-MDB-016 AC4 -- extends the CR-MDB-014 import-fidelity gate
    (ImportedSkillBundleFidelityTest above) to the 7 handover bundles:
    each must exist under skills-src/ with a SKILL.md, its file set must
    be a superset of its origin counterpart under crucible:clients/skills/
    (WHEN that origin still exists -- it freezes/retires post-handover,
    same durability guard CR-MDB-016's own AC1 test uses), and the deploy
    engine's bundle-discovery function must find it (so the wheel/_assets
    coverage this AC gates actually reaches it, additively -- the
    pre-existing seven-bundle exact-match test below is untouched)."""

    def test_each_handover_bundle_exists_and_covers_origin_file_set(self):
        if not ORIGIN_CRUCIBLE_SKILLS_DIR.is_dir():
            self.skipTest(
                f"{ORIGIN_CRUCIBLE_SKILLS_DIR} absent -- origin has "
                f"frozen/retired post-handover; coverage-superset fidelity "
                f"is no longer checkable against it"
            )
        failures = []
        for name in CRUCIBLE_HANDOVER_BUNDLE_NAMES:
            origin_dir = ORIGIN_CRUCIBLE_SKILLS_DIR / name
            imported_dir = SKILLS_SRC_DIR / name
            if not (imported_dir / "SKILL.md").is_file():
                failures.append(
                    f"{name}: skills-src/{name}/SKILL.md does not exist "
                    f"(handover import not yet authored)"
                )
                continue
            origin_files = _relative_file_set(origin_dir)
            imported_files = _relative_file_set(imported_dir)
            missing = sorted(origin_files - imported_files)
            if missing:
                failures.append(
                    f"{name}: repo bundle must cover every origin file "
                    f"(superset of {origin_dir}); missing from "
                    f"skills-src/{name}/: {missing}"
                )
        # POSITIVE/EXACT -- every one of the 7 handover bundles exists and
        # covers the origin file set completely.
        self.assertEqual(failures, [], "\n".join(failures))

    def test_deploy_module_discovers_all_seven_handover_bundle_names(self):
        sys.path.insert(0, str(REPO_ROOT))
        try:
            from modelb_axi import deploy as deploy_module
        finally:
            sys.path.remove(str(REPO_ROOT))
        bundles = deploy_module._skill_bundles(REPO_ROOT)
        bundle_names = {b.name for b in bundles}
        missing = sorted(set(CRUCIBLE_HANDOVER_BUNDLE_NAMES) - bundle_names)
        # POSITIVE -- the deploy engine's own discovery must find every
        # handover bundle (additive to the pre-existing 7 -- 14 total once
        # Sec1 lands), so wheel/_assets packaging carries them.
        self.assertEqual(
            missing, [],
            f"deploy._skill_bundles(REPO_ROOT) must discover every handover "
            f"bundle {sorted(CRUCIBLE_HANDOVER_BUNDLE_NAMES)}; missing: {missing}",
        )


class SkillBundleDiscoveryGuardTest(unittest.TestCase):
    """AC6 pin #2 -- the deploy engine's own bundle-discovery function
    (modelb_axi.deploy._skill_bundles, pure/read-only) finds exactly the
    seven skill bundles (six imports + crucible) once §S7 lands; the
    crucible bundle's content stays exactly as CR-MDB-011 committed it
    (no-active-cycle client present, zero WORKFLOW_CYCLE_ID references --
    the import step must never touch it)."""

    def test_deploy_module_discovers_seven_bundles_with_crucible_content_unchanged(self):
        sys.path.insert(0, str(REPO_ROOT))
        try:
            from modelb_axi import deploy as deploy_module
        finally:
            sys.path.remove(str(REPO_ROOT))
        bundles = deploy_module._skill_bundles(REPO_ROOT)
        bundle_names = {b.name for b in bundles}
        # POSITIVE/EXACT -- CR-MDB-016 supersedes the seven-only bound: the
        # seven pre-existing bundles UNION the seven imported handover
        # bundles (14 total), no more (e.g. memory-templates/, which has no
        # SKILL.md, must never be picked up) and no fewer.
        expected_bundle_names = (
            set(ALL_SEVEN_BUNDLE_NAMES) | set(CRUCIBLE_HANDOVER_BUNDLE_NAMES)
        )
        self.assertEqual(
            bundle_names, expected_bundle_names,
            f"deploy._skill_bundles(REPO_ROOT) must discover exactly the "
            f"fourteen skill bundles {sorted(expected_bundle_names)}; "
            f"found {sorted(bundle_names)}",
        )
        crucible_skill_md = SKILLS_SRC_DIR / CRUCIBLE_BUNDLE_NAME / "SKILL.md"
        self.assertTrue(
            crucible_skill_md.is_file(),
            f"{crucible_skill_md} must still exist (011 authorship)",
        )
        crucible_content = crucible_skill_md.read_text(encoding="utf-8")
        # POSITIVE -- the no-active-cycle client behaviour text survives.
        self.assertIn(
            "no-active-cycle", crucible_content,
            "skills-src/crucible/SKILL.md must still describe the "
            "no-active-cycle client behaviour (011 authorship untouched "
            "by the §S7 import step)",
        )
        # NEGATIVE -- zero WORKFLOW_CYCLE_ID references (CR-CRU-036 removed
        # this from the client contract; the import must not reintroduce it).
        self.assertNotIn(
            "WORKFLOW_CYCLE_ID", crucible_content,
            "skills-src/crucible/SKILL.md must contain zero "
            "WORKFLOW_CYCLE_ID references",
        )


class GeneratorAgentsAssetTest(unittest.TestCase):
    """AC6 pin #4/#5 -- the retargeted output dir (generator/agents/, the
    RED-pinned contract) contains the 20 generated agent .md files
    (CR-MDB-024 \u00a7S2: 16 legacy + 4 rust),
    content-identical to build.py's own render() (pure, no I/O -- this
    test never shells out to build.py's `build` sub-command)."""

    def test_generator_agents_dir_contains_twenty_files_matching_render(self):
        module = _load_build_module()
        failures = []
        if not GENERATOR_AGENTS_DIR.is_dir():
            self.fail(
                f"{GENERATOR_AGENTS_DIR} does not exist -- generator/build.py "
                f"has not been retargeted off Path.home()/'.claude'/'agents' "
                f"(RED-pinned AC6 contract, see module docstring)"
            )
        found_names = {p.name for p in GENERATOR_AGENTS_DIR.glob("*.md")}
        expected_names = {f"{stack}-{role}-agent.md" for stack in STACKS for role in ROLES}
        # POSITIVE/EXACT -- exactly the 20 generated stack files, none missing,
        # none extra.
        self.assertEqual(
            found_names, expected_names,
            f"{GENERATOR_AGENTS_DIR} must contain exactly the 20 "
            f"regenerated stack agent files; found {sorted(found_names)}",
        )
        for stack in STACKS:
            params = module.load_stack_params(stack)
            for role in ROLES:
                name = f"{stack}-{role}-agent.md"
                expected_content = module.render(stack, role, params)
                actual_content = (GENERATOR_AGENTS_DIR / name).read_text(encoding="utf-8")
                if actual_content != expected_content:
                    failures.append(
                        f"{name}: content does not match build.py's own "
                        f"render(); the repo-local asset must be the exact "
                        f"regeneration output"
                    )
        # POSITIVE/EXACT -- every file's content is build.py's own
        # deterministic render() output, byte for byte.
        self.assertEqual(failures, [], "\n".join(failures))


class BuildPyCliRetargetTest(unittest.TestCase):
    """AC6 pin #4 -- generator/build.py's CLI-observable retarget: `--list`
    reports repo-local paths (never the real user home), `--check` stays a
    green drift gate against the repo-local dir, and generator/ carries
    zero chezmoi-source references. Only read-only sub-commands
    (`--list`/`--check`) are ever invoked here -- never `build`."""

    def test_build_py_list_is_repo_local_check_clean_and_zero_chezmoi_refs(self):
        self.assertTrue(BUILD_PY.is_file(), f"{BUILD_PY} must exist")

        list_result = subprocess.run(
            [sys.executable, str(BUILD_PY), "--list"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(
            list_result.returncode, 0,
            f"generator/build.py --list must exit 0, got rc="
            f"{list_result.returncode}\nstderr:\n{list_result.stderr[:2000]}",
        )
        listed_paths = [
            Path(line.strip()) for line in list_result.stdout.splitlines() if line.strip()
        ]
        home_rooted = [p for p in listed_paths if str(p).startswith(str(Path.home() / ".claude"))]
        # NEGATIVE -- the RED-pinned retarget contract requires zero listed
        # paths under the real user home (pre-retarget these were all under
        # ~/.claude/agents).
        self.assertEqual(
            home_rooted, [],
            f"generator/build.py --list must report repo-local paths only "
            f"post-S7 retarget (pinned contract: {GENERATOR_AGENTS_DIR}); "
            f"found home-rooted paths: {home_rooted}",
        )
        # CR-MDB-022 §S2 SANCTIONED AMENDMENT -- superseded pin: build.py
        # gained a SECOND target class, the generated codec at its own
        # CODEC_TARGET (scripts/toon.py), drift-gated by this same
        # --check/--list surface because "inventing a second gate binary would
        # create a parallel convention". "Every listed path's parent is
        # generator/agents/" is therefore a superseded contract. The amended
        # form pins the EXACT set of listed target paths -- the 20 agent
        # definitions (CR-MDB-024 \u00a7S2: 16 legacy + 4 rust) plus that one
        # codec, named from build.py's own constant
        # rather than a duplicated string -- which is strictly stronger than
        # the parent-directory check it replaces: a 21st stray target, a
        # missing target, a relocated target and a renamed output dir all
        # still fail. The home-rooted (§S7 retarget) and chezmoi-reference
        # halves of this test are unchanged.
        module = _load_build_module()
        expected_paths = {
            GENERATOR_AGENTS_DIR / f"{stack}-{role}-agent.md"
            for stack in STACKS for role in ROLES
        } | {module.CODEC_TARGET}
        # POSITIVE/EXACT -- the listed target set is exactly the pinned
        # repo-local agent assets plus the generated codec.
        self.assertEqual(
            set(listed_paths), expected_paths,
            f"generator/build.py --list must report exactly the 20 agent "
            f"definitions under {GENERATOR_AGENTS_DIR} plus the generated "
            f"codec {module.CODEC_TARGET}; got "
            f"{sorted(str(p) for p in listed_paths)}, expected "
            f"{sorted(str(p) for p in expected_paths)}",
        )
        # bound -- each target is listed exactly once (no duplicated line
        # hidden by the set comparison above).
        self.assertEqual(
            len(listed_paths), len(expected_paths),
            f"generator/build.py --list must report each target exactly once, "
            f"got {len(listed_paths)} lines for {len(expected_paths)} targets",
        )

        check_result = subprocess.run(
            [sys.executable, str(BUILD_PY), "--check"],
            capture_output=True, text=True, timeout=60,
        )
        # POSITIVE -- the drift gate stays green against the repo-local dir
        # (the same invariant test_agent_generator.py pinned pre-retarget).
        self.assertEqual(
            check_result.returncode, 0,
            f"generator/build.py --check must exit 0 against the retargeted "
            f"repo-local asset dir, got rc={check_result.returncode}\n"
            f"stdout:\n{check_result.stdout[:2000]}\n"
            f"stderr:\n{check_result.stderr[:2000]}",
        )

        grep_result = subprocess.run(
            ["grep", "-rn", "chezmoi", str(GENERATOR_DIR)],
            capture_output=True, text=True, timeout=15,
        )
        chezmoi_hits = [ln for ln in grep_result.stdout.splitlines() if ln.strip()]
        # NEGATIVE/EXACT bound -- zero chezmoi-source references anywhere
        # under generator/ (AC6's named grep gate).
        self.assertEqual(
            chezmoi_hits, [],
            f"generator/ must contain zero chezmoi-source references; "
            f"found: {chezmoi_hits}",
        )


def _is_chezmoi_which_call(node):
    """True for a call node shaped exactly `shutil.which("chezmoi")`
    (first positional arg a string constant equal to "chezmoi")."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "which"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "shutil"
        and len(node.args) >= 1
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "chezmoi"
    )


_SUBPROCESS_INVOCATION_FUNCS = frozenset({"run", "call", "check_call", "check_output", "Popen"})


def _is_subprocess_call(node):
    """True for `subprocess.<run|call|check_call|check_output|Popen>(...)`
    -- restricted to the `subprocess.` attribute form actually used in this
    tree (never a bare `run(...)`, which would risk false positives on an
    unrelated same-named helper)."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in _SUBPROCESS_INVOCATION_FUNCS
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
    )


def _first_argv_element(call_node):
    """The first element of a subprocess call's argv list/tuple literal, or
    None if the first positional arg is not a list/tuple literal or is
    empty (e.g. `shell=True` string-form calls, which this repo does not
    use for chezmoi and which this gate therefore does not need to match)."""
    if not call_node.args:
        return None
    first = call_node.args[0]
    if isinstance(first, (ast.List, ast.Tuple)) and first.elts:
        return first.elts[0]
    return None


class _ChezmoiInvocationVisitor(ast.NodeVisitor):
    """Walks one module's AST in source order, tracking which local names
    are bound to `shutil.which("chezmoi")` so a later subprocess argv head
    referencing that name is recognised as the SAME invocation CR-MDB-021
    §S1 targets -- not just a bare `"chezmoi"` literal."""

    def __init__(self):
        self.hits = []  # list of (lineno, enclosing_funcname, kind)
        self._which_names = set()
        self._func_stack = []

    def _enclosing(self):
        return self._func_stack[-1] if self._func_stack else "<module>"

    def _visit_function(self, node):
        self._func_stack.append(node.name)
        self.generic_visit(node)
        self._func_stack.pop()

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function

    def visit_Assign(self, node):
        if _is_chezmoi_which_call(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self._which_names.add(target.id)
        self.generic_visit(node)

    def visit_Call(self, node):
        if _is_chezmoi_which_call(node):
            self.hits.append((node.lineno, self._enclosing(), 'shutil.which("chezmoi")'))
        elif _is_subprocess_call(node):
            head = _first_argv_element(node)
            if isinstance(head, ast.Constant) and head.value == "chezmoi":
                self.hits.append(
                    (node.lineno, self._enclosing(), 'subprocess argv[0] == "chezmoi" literal')
                )
            elif isinstance(head, ast.Name) and head.id in self._which_names:
                self.hits.append((
                    node.lineno, self._enclosing(),
                    f'subprocess argv[0] == {head.id!r} (bound to shutil.which("chezmoi"))',
                ))
        self.generic_visit(node)


def find_chezmoi_invocations(source, filename="<string>"):
    """CR-MDB-021 §S1 -- static (never-executes-anything) detector for a
    chezmoi-binary INVOCATION in Python source text. Returns a list of
    `(lineno, enclosing_funcname, kind)` tuples, empty if none found.

    Matches ONLY:
      (a) `shutil.which("chezmoi")`, and
      (b) a `subprocess.<run|call|check_call|check_output|Popen>(...)` call
          whose argv list/tuple's FIRST element is either the literal
          string "chezmoi" or a name bound (by a plain `x = shutil.which(
          "chezmoi")` assignment earlier in the same source) to that call.

    Deliberately does NOT match a bare substring/mention of "chezmoi" --
    `self.assertEqual(x, "chezmoi")`, `self.assertIn("chezmoi", ...)`, and
    `"chezmoi"` as a tuple/list element (e.g. a bundle-name registry) all
    produce zero hits. Pure `ast.parse` + tree walk -- runs no subprocess,
    reads no file, touches nothing under `$HOME`.
    """
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        raise ValueError(f"{filename}: could not parse as Python source: {exc}") from exc
    visitor = _ChezmoiInvocationVisitor()
    visitor.visit(tree)
    return visitor.hits


def _iter_chezmoi_scan_sources(root):
    """Yield (path, source_text) for every file under `root` this gate
    inspects: `*.py` files everywhere, plus extensionless `#!.../python3`
    scripts under `hooks-src/scripts/` (the neutral hook-script convention
    -- see hooks-src/schema.md -- ships no file extension)."""
    if not root.is_dir():
        return
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix == ".py":
            yield path, path.read_text(encoding="utf-8")
        elif root.name == "scripts" and path.suffix == "":
            text = path.read_text(encoding="utf-8")
            first_line = text.splitlines()[0] if text else ""
            if first_line.startswith("#!") and "python" in first_line:
                yield path, text


class ChezmoiInvocationGateTest(unittest.TestCase):
    """CR-MDB-021 §S1 -- the guard that makes the chezmoi-retirement policy
    self-enforcing: no module under tests/, modelb_axi/, or
    hooks-src/scripts/ may INVOKE the chezmoi binary. Static AST inspection
    only (see find_chezmoi_invocations); this class itself never runs
    chezmoi and never reads anything under $HOME."""

    def test_detector_bites_fires_on_real_invocation_only(self):
        synthetic_source = (
            "import shutil\n"
            "import subprocess\n"
            "\n"
            "\n"
            "def test_real_invocation():\n"
            '    chezmoi = shutil.which("chezmoi")\n'
            '    subprocess.run([chezmoi, "diff", "/tmp"], capture_output=True)\n'
            "\n"
            "\n"
            "def test_assert_equal_bare_literal():\n"
            '    self.assertEqual(observed_bundle_manager, "chezmoi", "must be chezmoi")\n'
            "\n"
            "\n"
            "def test_assert_in_bare_literal():\n"
            '    self.assertIn("chezmoi", content.lower(), "must mention chezmoi")\n'
            "\n"
            "\n"
            "def test_bundle_name_tuple_element():\n"
            "    NAMES = (\n"
            '        "model-b",\n'
            '        "chezmoi",\n'
            '        "bootstrap",\n'
            "    )\n"
        )
        hits = find_chezmoi_invocations(synthetic_source, filename="<detector-bites>")
        hit_funcs = sorted({funcname for (_lineno, funcname, _kind) in hits})
        # POSITIVE/EXACT -- the matcher fires on the real-invocation function
        # only; the assertEqual/assertIn/tuple-element forms produce zero hits.
        self.assertEqual(
            hit_funcs, ["test_real_invocation"],
            f"detector-bites fixture: matcher must fire on test_real_invocation "
            f"only (never on the bare-literal assertEqual/assertIn/tuple-element "
            f"forms), got hits in: {hit_funcs}",
        )
        # bound -- exactly the two matched sites inside that one function
        # (the shutil.which binding, then the subprocess argv head bound to
        # it), never more and never fewer.
        self.assertEqual(
            len(hits), 2,
            f"detector-bites fixture: expected exactly 2 matched sites inside "
            f"test_real_invocation (shutil.which + subprocess argv head), "
            f"got {len(hits)}: {hits}",
        )

    def test_retained_live_lines_present_and_do_not_trip_matcher(self):
        git_chezmoi_skills = REPO_ROOT / "tests" / "test_git_chezmoi_skills.py"
        source = git_chezmoi_skills.read_text(encoding="utf-8")
        lines = source.splitlines()
        # POSITIVE -- the two retained content-assertion lines this CR
        # deliberately keeps are still exactly where the spec pins them.
        self.assertIn(
            '"chezmoi"', lines[168],
            f"{git_chezmoi_skills}:169 must still read the literal \"chezmoi\" "
            f"(shipped SKILL.md frontmatter name assertion), got: {lines[168]!r}",
        )
        self.assertIn("assertEqual", lines[167], f"{git_chezmoi_skills}:168 must be an assertEqual(")
        self.assertIn(
            '"chezmoi"', lines[343],
            f"{git_chezmoi_skills}:344 must still read the literal \"chezmoi\" "
            f"(AGENTS.md content assertion), got: {lines[343]!r}",
        )
        self.assertIn("assertIn", lines[342], f"{git_chezmoi_skills}:343 must be an assertIn(")

        hits = find_chezmoi_invocations(source, filename=str(git_chezmoi_skills))
        offending_at_retained_lines = [h for h in hits if h[0] in (168, 169, 343, 344)]
        # NEGATIVE -- neither retained line trips the matcher.
        self.assertEqual(
            offending_at_retained_lines, [],
            f"matcher must not trip on the retained content-assertion lines "
            f"168-169/343-344 of {git_chezmoi_skills}; got "
            f"{offending_at_retained_lines}",
        )

        this_file = REPO_ROOT / "tests" / "test_installer_assets.py"
        this_source = this_file.read_text(encoding="utf-8")
        this_lines = this_source.splitlines()
        bundle_tuple_line = next(
            i for i, ln in enumerate(this_lines) if '"chezmoi",' in ln
        )
        # POSITIVE sanity -- the Model-B-owned bundle-name tuple element this
        # CR exempts is still present in this very file.
        self.assertIn('"chezmoi"', this_lines[bundle_tuple_line])
        hits_here = find_chezmoi_invocations(this_source, filename=str(this_file))
        bundle_tuple_hits = [h for h in hits_here if h[0] == bundle_tuple_line + 1]
        # NEGATIVE -- the matcher must not trip on this file's own
        # IMPORTED_BUNDLE_NAMES tuple element.
        self.assertEqual(
            bundle_tuple_hits, [],
            f"matcher must not trip on this file's own bundle-name tuple "
            f"element at line {bundle_tuple_line + 1}; got {bundle_tuple_hits}",
        )

    def test_zero_chezmoi_invocations_under_tests_modelb_axi_hooks_scripts(self):
        violations = {}
        for root in CHEZMOI_INVOCATION_SCAN_ROOTS:
            for path, source in _iter_chezmoi_scan_sources(root):
                try:
                    hits = find_chezmoi_invocations(source, filename=str(path))
                except ValueError as exc:
                    self.fail(str(exc))
                if not hits:
                    continue
                by_func = {}
                for lineno, funcname, kind in hits:
                    by_func.setdefault(funcname, []).append((lineno, kind))
                rel = path.relative_to(REPO_ROOT)
                for funcname, sites in sorted(by_func.items()):
                    violations[f"{rel}::{funcname}"] = sites
        scanned_roots = [str(r.relative_to(REPO_ROOT)) for r in CHEZMOI_INVOCATION_SCAN_ROOTS]
        # NEGATIVE/EXACT -- zero chezmoi-binary invocation sites (static
        # source inspection of shutil.which("chezmoi") + subprocess argv
        # heads) anywhere under tests/, modelb_axi/, hooks-src/scripts/.
        # THIS IS THE RED: today 8 methods across 7 modules still invoke
        # chezmoi (see CR-MDB-021 Context table) -- this must fail until
        # §S2/§S3 remove them.
        self.assertEqual(
            violations, {},
            f"found {len(violations)} chezmoi-invocation site(s) under "
            f"{scanned_roots}: {violations}",
        )


# ---------------------------------------------------------------------------
# CR-MDB-021 §S4 -- prose surfaces must not INSTRUCT a chezmoi step as
# part of Model B CR work. Naming/describing the retired mechanism (a
# closed CR's history, a bundle-name list entry, a quoted citation of
# another line, or the user's own dotfile discipline) is NOT the same as
# instructing it -- see find_chezmoi_prose_instructions' docstring.
# ---------------------------------------------------------------------------

CONTRACTS_DIR = REPO_ROOT / "contracts"
CHANGES_DIR = REPO_ROOT / "docs" / "changes"
MEMORY_TEMPLATES_DIR = SKILLS_SRC_DIR / "memory-templates"

# The exact OPEN CR numbers in scope for the §S4 prose-instruction gate,
# per dispatch (007 has no separate spec file; 027 is an open CR but was
# not named in scope and is deliberately excluded here -- CLOSED CRs
# 001-016 are covered separately, by ClosedCrSpecsUntouchedTest below, never
# by this gate).
OPEN_CR_NUMBERS_IN_S4_SCOPE = (17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 28, 29, 30, 31, 32, 33, 34, 35)


def _chezmoi_prose_instruction_scope_files():
    """The exact §S4 surface set: AGENTS.md, contracts/lean-ctx.md,
    every skills-src/memory-templates/*.md, docs/changes/README.md, and the
    named OPEN CR specs only."""
    files = [REPO_ROOT / "AGENTS.md", CONTRACTS_DIR / "lean-ctx.md", CHANGES_DIR / "README.md"]
    files.extend(sorted(MEMORY_TEMPLATES_DIR.glob("*.md")))
    for number in OPEN_CR_NUMBERS_IN_S4_SCOPE:
        files.extend(sorted(CHANGES_DIR.glob(f"CR-MDB-0{number}-*.md")))
    return [f for f in files if f.is_file()]


_CHEZMOI_PROSE_PARAGRAPH_START_RE = re.compile(r'^(#{1,6}\s|-\s|\*\s|\d+\.\s|\|)')

# The three curated prescriptive frames CR-MDB-021 §S4 measured -- each
# one is an ACTUAL sentence shape that prescribes a dotfile-manager
# mechanism for MODEL B's own mutation, not a description of one.
# Deliberately does NOT include a bare "chezmoi diff"/"chezmoi apply"
# mention: AGENTS.md:135's "chezmoi diff cleanliness" names what a
# now-removed test asserted (a prose-staleness fix bundled into the Suite
# AC's close-out step, not a live instruction site), and AGENTS.md:138
# names retired gates for the historical baseline-count record -- both are
# describing, not instructing (the same test_ac7 substring-sweep trap
# CR-MDB-017 had to repair).
_CHEZMOI_PROSE_TRIGGERS = {
    "follows chezmoi discipline": re.compile(r'\bfollows?\s+chezmoi\s+discipline\b', re.IGNORECASE),
    "goes through chezmoi": re.compile(r'\bgoes\s+through\s+chezmoi\b', re.IGNORECASE),
    "(chezmoi-managed rationale)": re.compile(r'\(chezmoi-managed\b', re.IGNORECASE),
}

# Describing is not instructing: a paragraph matching one of these is
# exempt even if it also matches a trigger above.
_CHEZMOI_PROSE_EXEMPTIONS = (
    # a quoted CITATION of another line's trigger phrase (e.g. this CR's
    # own §S4 Amendments section quoting contracts/lean-ctx.md:33
    # verbatim in parens-and-quotes) -- reporting that a line elsewhere
    # says this is not issuing the instruction here.
    re.compile(
        r'["\u201c][^"\u201d\n]{0,400}?'
        r'(?:goes\s+through\s+chezmoi|chezmoi\s+discipline|chezmoi-managed)'
        r'[^"\u201d\n]{0,20}?["\u201d]',
        re.IGNORECASE,
    ),
    # "chezmoi" as one element of a backtick-quoted, comma-separated
    # bundle/skill-name list (AGENTS.md's skills-src/ row and its
    # load-on-demand-references bullet; CR-023's parallel bundle count).
    re.compile(r'`chezmoi`\s*,|,\s*`chezmoi`\b'),
    re.compile(r'\bskills-src/chezmoi\b', re.IGNORECASE),
    re.compile(r'\bchezmoi\s+(?:skill\s+)?bundle\b', re.IGNORECASE),
    # the USER's own dotfile discipline -- explicitly out of scope.
    re.compile(r"user'?s?\s+own\s+dotfile", re.IGNORECASE),
    # a dated Notes-log entry or a completed setup checkbox in
    # docs/changes/README.md's queue footer -- historical record.
    re.compile(r'^-\s*\d{4}-\d{2}-\d{2}\s*\u2014'),
    re.compile(r'^-\s*\[[xX]\]'),
)


def _iter_prose_paragraphs(text):
    """Group physical lines into logical markdown paragraphs: a heading,
    top-level bullet, numbered item, or table row starts a new paragraph;
    an indented/unmarked line merges into the paragraph above it (this
    repo wraps bullet continuations at 2-space indent). A blank line
    always closes the current paragraph. Returns a list of
    `(start_lineno, joined_text)`, 1-indexed."""
    paragraphs = []
    current_lines = []
    current_start = None
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line.strip() == "":
            if current_lines:
                paragraphs.append((current_start, " ".join(current_lines)))
                current_lines = []
                current_start = None
            continue
        if current_lines and _CHEZMOI_PROSE_PARAGRAPH_START_RE.match(line):
            paragraphs.append((current_start, " ".join(current_lines)))
            current_lines = []
        if not current_lines:
            current_start = lineno
        current_lines.append(line.strip())
    if current_lines:
        paragraphs.append((current_start, " ".join(current_lines)))
    return paragraphs


def find_chezmoi_prose_instructions(text, filename="<string>"):
    """CR-MDB-021 §S4 -- REGRESSION PIN, not a general natural-language
    instruction detector. This function fires on exactly the three curated
    phrasings in _CHEZMOI_PROSE_TRIGGERS -- "follows chezmoi discipline",
    "goes through chezmoi", "(chezmoi-managed" -- because those were the
    precise three sites measured live in Model B prose on 2026-09-21
    (AGENTS.md:49, AGENTS.md:109, contracts/lean-ctx.md:33). It does NOT
    detect a differently-phrased future instruction (e.g. "run chezmoi
    apply after each ~/.claude edit", "sync this via chezmoi", "chezmoi
    manages the memory directory") -- those phrasings simply do not match
    any of the three fixed regexes and pass through silently. Catching a
    reworded or novel instruction is a gap-analysis / CR-review
    responsibility, not this test's: broadening the regexes to guess at
    unseen phrasings would recreate the over-firing trap this gate was
    built to avoid (see the docstring below and the exemption list, which
    exist because a naive substring match on "chezmoi" fires on citations,
    bundle-name list entries, and the user's own dotfile discipline).

    Contrast with ChezmoiInvocationGateTest (§S1, find_chezmoi_invocations
    above): THAT gate is self-enforcing because it hooks real Python AST
    shapes (shutil.which("chezmoi") / a subprocess argv head bound to it)
    and so generalises to any future code using that API, regardless of
    surrounding phrasing. This prose gate has no equivalent structural
    anchor -- natural-language phrasing has no AST -- so it cannot borrow
    that self-enforcing framing and must not be described as if it did.

    Paragraph-scoped (see _iter_prose_paragraphs). A paragraph is reported
    once, on its first matching trigger, if it contains one of the three
    curated prescriptive frames in _CHEZMOI_PROSE_TRIGGERS AND matches none
    of _CHEZMOI_PROSE_EXEMPTIONS. `filename` is carried through only for
    caller error messages; this function reads no file itself.

    Returns a list of `(start_lineno, trigger_name, paragraph_text)`
    tuples, empty if none. Pure string/regex inspection -- never invokes
    chezmoi, never runs a subprocess, reads nothing under $HOME.
    """
    hits = []
    for start_lineno, paragraph in _iter_prose_paragraphs(text):
        if "chezmoi" not in paragraph.lower():
            continue
        if any(exempt.search(paragraph) for exempt in _CHEZMOI_PROSE_EXEMPTIONS):
            continue
        for trigger_name, pattern in _CHEZMOI_PROSE_TRIGGERS.items():
            if pattern.search(paragraph):
                hits.append((start_lineno, trigger_name, paragraph))
                break
    return hits


class ChezmoiProseInstructionGateTest(unittest.TestCase):
    """CR-MDB-021 §S4 -- REGRESSION PIN on the three exact prescriptive
    phrasings measured live in Model B prose on 2026-09-21: "follows
    chezmoi discipline" (AGENTS.md:49), "goes through chezmoi"
    (contracts/lean-ctx.md:33), and "(chezmoi-managed" (AGENTS.md:109).
    This is NOT a general natural-language chezmoi-instruction detector --
    it asserts that those three sites, and only those three phrasings
    wherever they recur, no longer instruct a chezmoi step across AGENTS.md,
    contracts/lean-ctx.md, skills-src/memory-templates/*.md,
    docs/changes/README.md, and the named OPEN CR specs. A differently
    phrased future instruction (e.g. "run chezmoi apply after each
    ~/.claude edit", "sync this via chezmoi") will NOT be caught by this
    gate; recognising that is a gap-analysis / CR-review responsibility at
    review time, not a property this test can or should guarantee.

    Unlike ChezmoiInvocationGateTest (§S1) -- which hooks a real Python
    AST shape (shutil.which("chezmoi") / a subprocess argv head bound to
    it) and therefore stays self-enforcing against any future code using
    that API -- this gate has no structural anchor to generalise from:
    prose has no AST. Do not describe this class as self-enforcing or as
    a general prohibition; it is a pin on the three measured sites only.
    Static text inspection only (see find_chezmoi_prose_instructions);
    this class never runs chezmoi and never reads anything under $HOME."""

    def test_detector_bites_fires_on_genuine_instruction_only(self):
        synthetic_prose = (
            "## Scenario (a) -- genuine instruction (MUST fire)\n"
            "\n"
            "- Every `~/.claude` mutation follows chezmoi discipline: no-auto temp\n"
            "  config, manual source commits, deletions via `chezmoi destroy`/`forget`\n"
            "  (a plain `rm` resurrects on apply). Never `chezmoi apply`, never push\n"
            "  the source repo.\n"
            "\n"
            "## Scenario (b) -- historical/descriptive citation-quote (MUST NOT fire)\n"
            "\n"
            "- **Amendment:** `contracts/lean-ctx.md:33` (\"every `~/.claude` mutation\n"
            "  in this workflow goes through chezmoi\") is in scope as a historical\n"
            "  citation of an existing line, not a live instruction issued here.\n"
            "\n"
            "## Scenario (c) -- skills-src/chezmoi bundle-name list element (MUST NOT fire)\n"
            "\n"
            "| `skills-src/` | 13 skill bundles. Model-B-owned: `model-b`, `crucible`, "
            "`cr-authoring`, `git-workflow`, `chezmoi`, `bootstrap`, `shutdown`. |\n"
            "\n"
            "## Scenario (d) -- the USER's own dotfile discipline (MUST NOT fire)\n"
            "\n"
            "`skills-src/chezmoi/` documents the USER's own dotfile discipline and is\n"
            "not a Model B dependency on chezmoi.\n"
        )
        hits = find_chezmoi_prose_instructions(synthetic_prose, filename="<detector-bites>")
        # POSITIVE/EXACT -- fires on scenario (a) only, at its start line,
        # via the "follows chezmoi discipline" trigger.
        self.assertEqual(
            [h[0] for h in hits], [3],
            f"detector-bites fixture: matcher must fire on scenario (a) "
            f"(line 3) only; got hits at lines {[h[0] for h in hits]}",
        )
        self.assertEqual(
            hits[0][1], "follows chezmoi discipline",
            f"scenario (a) must trip the 'follows chezmoi discipline' "
            f"trigger; got {hits[0][1]!r}",
        )
        # NEGATIVE -- scenario (b)'s quoted citation of the SAME "goes
        # through chezmoi" phrase this gate's own real-world target
        # (contracts/lean-ctx.md:33) uses does NOT trip the matcher: the
        # gate must distinguish reporting a line from re-issuing it.
        self.assertNotIn(
            10, [h[0] for h in hits],
            "scenario (b) (line 10) is a quoted historical citation, not "
            "a live instruction -- must not trip the matcher",
        )
        # NEGATIVE -- scenario (c)'s bundle-name list element.
        self.assertNotIn(
            16, [h[0] for h in hits],
            "scenario (c) (line 16) is a bundle-name list element, not an "
            "instruction -- must not trip the matcher",
        )
        # NEGATIVE -- scenario (d)'s USER's-own-dotfiles sentence.
        self.assertNotIn(
            20, [h[0] for h in hits],
            "scenario (d) (line 20) describes the USER's own dotfile "
            "discipline, not a Model B CR instruction -- must not trip "
            "the matcher",
        )

    def test_zero_chezmoi_instruction_sites_across_live_model_b_prose(self):
        violations = {}
        for path in _chezmoi_prose_instruction_scope_files():
            source = path.read_text(encoding="utf-8")
            hits = find_chezmoi_prose_instructions(source, filename=str(path))
            if hits:
                rel = path.relative_to(REPO_ROOT)
                violations[str(rel)] = [(lineno, trigger) for lineno, trigger, _para in hits]
        # NEGATIVE/EXACT -- zero chezmoi-instruction sites across AGENTS.md,
        # contracts/lean-ctx.md, skills-src/memory-templates/*.md,
        # docs/changes/README.md, and the named OPEN CR specs. THIS IS THE
        # RED: AGENTS.md:49 and :109, plus contracts/lean-ctx.md:33, still
        # prescribe a dotfile-manager mechanism for Model B work today --
        # this must fail until they are reworded.
        self.assertEqual(
            violations, {},
            f"found chezmoi-instruction site(s) in live Model B prose: {violations}",
        )


# ---------------------------------------------------------------------------
# CR-MDB-021 §S4 AC -- closed CR specs (001-016) are historical record
# and must remain byte-identical to their committed state on the
# merge-base with develop.
# ---------------------------------------------------------------------------

CLOSED_CR_SPEC_NAME_RE = re.compile(r'^CR-MDB-0(0[1-9]|1[0-6])-.*\.md$')


def _closed_cr_spec_files():
    """Every docs/changes/CR-MDB-0{01..16}-*.md file that exists (007 has
    no separate spec file -- see docs/changes/README.md's queue row, which
    points CR-MDB-007 at README.md#footer-notes instead)."""
    return sorted(
        p for p in CHANGES_DIR.glob("CR-MDB-0*.md")
        if CLOSED_CR_SPEC_NAME_RE.match(p.name)
    )


class _DevelopRefUnresolvable(RuntimeError):
    """Raised by _git_merge_base_with_develop when neither `develop` nor
    `origin/develop` can be resolved against HEAD in this clone."""


def _git_merge_base_with_develop(repo_root):
    """Resolve the merge-base between HEAD and develop's history.

    Tries `git merge-base HEAD develop` first (a local branch, present when
    this clone has ever checked out or tracked one), then falls back to
    `git merge-base HEAD origin/develop` (the remote-tracking ref, present
    in a plain single-branch `git clone` that never checked out `develop`
    locally). If NEITHER ref resolves, raises _DevelopRefUnresolvable naming
    both attempted refs and their git errors.

    A fresh single-branch clone carrying no `develop` history at all is an
    ENVIRONMENT precondition gap, not a closed-CR-integrity violation --
    reporting it as the latter is exactly the defect class CR-MDB-021
    itself exists to remove (a gate failing for a reason that is not a
    Model B property; see the CR's own Context). The caller
    (ClosedCrSpecsUntouchedTest) must `self.skipTest` on
    _DevelopRefUnresolvable, never `self.fail` -- the substantive
    byte-identity assertion is unchanged and still runs whenever either
    ref IS resolvable.

    This is how "the committed manifest" (§S4 AC) is derived here:
    this RED agent has no shell/execution tool of its own to run
    `sha256sum` and hand-type digest literals from its output (a
    documented dispatch constraint -- fabricating hex digest strings
    without computing them would be worse than not gating at all), and
    this file may touch no other file, so no committed snapshot fixture
    can be added alongside it either. The comparison target is instead
    resolved by the SAME `git` the test-runner already has, AT TEST RUN
    TIME -- never guessed by this agent -- which is a stronger and more
    literal reading of the AC's own wording ("byte-identical to its
    committed state on the merge-base with develop") than a hand-typed
    sha256 manifest would have been anyway.
    """
    attempt_errors = []
    for ref in ("develop", "origin/develop"):
        result = subprocess.run(
            ["git", "merge-base", "HEAD", ref],
            cwd=str(repo_root), capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        attempt_errors.append(f"{ref}: {result.stderr.strip()}")
    raise _DevelopRefUnresolvable(
        "neither 'develop' nor 'origin/develop' could be resolved against "
        "HEAD (tried in that order): " + "; ".join(attempt_errors)
    )


def _git_committed_blob_sha256(commit, relpath, repo_root):
    """sha256 of `relpath` as it existed at `commit` (`git show
    <commit>:<relpath>`), computed from the raw blob bytes -- never reads
    the live working-tree file."""
    result = subprocess.run(
        ["git", "show", f"{commit}:{relpath}"],
        cwd=str(repo_root), capture_output=True, timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git show {commit}:{relpath} failed (exit {result.returncode}): "
            f"{result.stderr.decode('utf-8', errors='replace').strip()}"
        )
    return hashlib.sha256(result.stdout).hexdigest()


class ClosedCrSpecsUntouchedTest(unittest.TestCase):
    """CR-MDB-021 §S4 AC -- 'CLOSED CR specs under docs/changes/ are
    unmodified -- git diff touches no CR-MDB-0{01..16}-*.md'. PRD §D9:
    waves 1-2 'legitimately deployed [through chezmoi] pre-installer and
    their history stands'; rewriting them would falsify the record."""

    def test_closed_cr_specs_byte_identical_to_merge_base_with_develop(self):
        closed_specs = _closed_cr_spec_files()
        # sanity -- the 001-016 range yields the 15 files that exist today
        # (007 has no separate spec file); catches an accidental empty scan.
        self.assertEqual(
            len(closed_specs), 15,
            f"expected exactly 15 closed CR spec files (001-016, minus 007 "
            f"which has no separate file) under {CHANGES_DIR}; found "
            f"{len(closed_specs)}: {[p.name for p in closed_specs]}",
        )
        try:
            merge_base = _git_merge_base_with_develop(REPO_ROOT)
        except _DevelopRefUnresolvable as exc:
            # ENVIRONMENT precondition gap, not a closed-CR-integrity
            # violation -- a fresh single-branch clone carries no `develop`
            # history at all, so this check simply cannot run here.
            # Reporting that as an integrity FAILURE is exactly the defect
            # class CR-MDB-021 exists to remove (a gate failing for a
            # reason that is not a Model B property) -- skip, don't fail.
            self.skipTest(
                f"cannot resolve 'develop' or 'origin/develop' in this "
                f"clone -- the closed-CR byte-identity check needs a clone "
                f"that carries develop's history: {exc}"
            )
        except RuntimeError as exc:
            self.fail(f"could not resolve merge-base with develop: {exc}")

        mismatched = []
        for path in closed_specs:
            relpath = str(path.relative_to(REPO_ROOT))
            try:
                committed_sha256 = _git_committed_blob_sha256(merge_base, relpath, REPO_ROOT)
            except RuntimeError as exc:
                self.fail(str(exc))
            live_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
            if live_sha256 != committed_sha256:
                mismatched.append(relpath)
        # NEGATIVE/EXACT -- zero closed CR specs differ from their
        # committed state on the merge-base with develop.
        self.assertEqual(
            mismatched, [],
            f"{len(mismatched)} closed CR spec file(s) differ from their "
            f"committed state on the merge-base with develop -- closed CRs "
            f"are historical record and must not be edited: {mismatched}",
        )


class DeployEngineSevenBundlesEndToEndTest(unittest.TestCase):
    """AC6 pin #3 -- a full sandboxed installer run (fakes on PATH, tmp
    MODELB_HOME + tmp target-root -- never the real ~/.claude/~/.agents)
    deploys ALL SEVEN skill bundles into the sandbox Vercel store with a
    manifest entry each."""

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-s7-home-")
        self._tmp_bin = tempfile.mkdtemp(prefix="modelb-axi-s7-fakebin-")
        self._tmp_target_root = tempfile.mkdtemp(prefix="modelb-axi-s7-target-")
        _write_fake_executable(self._tmp_bin, "uv", _FAKE_UV_SCRIPT)
        _write_fake_executable(self._tmp_bin, "sandesh", _FAKE_SANDESH_SCRIPT)

    def tearDown(self):
        for root in (self._tmp_home, self._tmp_bin, self._tmp_target_root):
            for p in Path(root).rglob("*"):
                try:
                    p.chmod(0o700)
                except OSError:
                    continue
        shutil.rmtree(self._tmp_home, ignore_errors=True)
        shutil.rmtree(self._tmp_bin, ignore_errors=True)
        shutil.rmtree(self._tmp_target_root, ignore_errors=True)

    def test_end_to_end_install_deploys_seven_skill_bundles_with_manifest_and_symlinks(self):
        result = _run_module(
            "--yes", "--harnesses", "claude-code",
            "--modelb-home", self._tmp_home,
            "--target-root", self._tmp_target_root,
            env_overrides={"PATH": self._tmp_bin},
        )
        self.assertEqual(
            result.returncode, 0,
            f"end-to-end sandboxed install must exit 0; got "
            f"exit={result.returncode} stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        with open(Path(self._tmp_home) / "install.toml", "rb") as fh:
            data = tomllib.load(fh)
        files_section = data.get("files")
        self.assertIsInstance(
            files_section, list,
            f"[[files]] must parse as a list of entries; got {type(files_section)}",
        )
        skill_md_names = set()
        for entry in files_section:
            if not isinstance(entry, dict):
                continue
            path = str(entry.get("path", ""))
            parts = Path(path).parts
            if len(parts) >= 2 and parts[-1] == "SKILL.md":
                skill_md_names.add(parts[-2])
        # POSITIVE/EXACT -- CR-MDB-016 supersedes the seven-only bound: a
        # manifest entry for every one of the seven pre-existing skill
        # bundles' SKILL.md UNION the seven imported handover bundles'
        # SKILL.md (14 distinct names, exactly).
        expected_skill_md_names = (
            set(ALL_SEVEN_BUNDLE_NAMES) | set(CRUCIBLE_HANDOVER_BUNDLE_NAMES)
        )
        self.assertEqual(
            skill_md_names, expected_skill_md_names,
            f"install.toml [[files]] must record a SKILL.md entry for "
            f"exactly the fourteen bundles {sorted(expected_skill_md_names)}; "
            f"found {sorted(skill_md_names)}",
        )
        store_root = Path(self._tmp_target_root) / ".agents" / "skills"
        harness_root = Path(self._tmp_target_root) / ".claude" / "skills"
        missing_store = [
            name for name in ALL_SEVEN_BUNDLE_NAMES
            if not (store_root / name / "SKILL.md").is_file()
        ]
        # POSITIVE/EXACT -- every bundle physically deployed once into the
        # harness-neutral store.
        self.assertEqual(
            missing_store, [],
            f"Vercel store must contain SKILL.md for every bundle under "
            f"{store_root}; missing: {missing_store}",
        )
        missing_symlink = [
            name for name in ALL_SEVEN_BUNDLE_NAMES
            if not (harness_root / name).is_symlink()
        ]
        # POSITIVE/EXACT -- every bundle symlinked into the claude-code
        # harness skills dir (never a second physical copy).
        self.assertEqual(
            missing_symlink, [],
            f"claude-code harness skills dir must symlink every bundle "
            f"under {harness_root}; missing symlinks: {missing_symlink}",
        )


class InstalledPackageAssetRootEndToEndTest(unittest.TestCase):
    """CR-MDB-014 F1 (VERIFY blocking #1 coverage gap) -- AC1's own
    install mechanism, end to end: `uv tool install <repo> --force` into
    a fully sandboxed UV_TOOL_DIR/UV_TOOL_BIN_DIR (the AC1-probe helper
    pattern), then a full sandboxed installer run of the INSTALLED
    `modelb-axi` binary -- never the PYTHONPATH dev-mode module. Proves
    the wheel's force-included package data (modelb_axi/_assets/) is what
    a genuinely-installed deploy resolves and deploys from; the dev-mode
    tests mask this because they resolve the repo root."""

    def setUp(self):
        self._tmp_dirs = []
        self._uv_tool_dir = self._mkdtemp("modelb-axi-e2e-uvtool-")
        self._uv_tool_bin_dir = self._mkdtemp("modelb-axi-e2e-uvbin-")
        self._tmp_home = self._mkdtemp("modelb-axi-e2e-home-")
        self._tmp_bin = self._mkdtemp("modelb-axi-e2e-fakebin-")
        self._tmp_target_root = self._mkdtemp("modelb-axi-e2e-target-")
        _write_fake_executable(self._tmp_bin, "uv", _FAKE_UV_SCRIPT)
        _write_fake_executable(self._tmp_bin, "sandesh", _FAKE_SANDESH_SCRIPT)

    def _mkdtemp(self, prefix: str) -> str:
        path = tempfile.mkdtemp(prefix=prefix)
        self._tmp_dirs.append(path)
        return path

    def tearDown(self):
        for root in self._tmp_dirs:
            shutil.rmtree(root, ignore_errors=True)

    def test_installed_package_deploys_from_packaged_assets(self):
        uv = shutil.which("uv")
        if uv is None:
            self.fail(
                "installed-package e2e: `uv` binary not found on PATH -- "
                "cannot verify installability (guarded, not skipped)"
            )
        install_env = dict(os.environ)
        install_env["UV_TOOL_DIR"] = self._uv_tool_dir
        install_env["UV_TOOL_BIN_DIR"] = self._uv_tool_bin_dir
        install = subprocess.run(
            [uv, "tool", "install", str(REPO_ROOT), "--force"],
            capture_output=True, text=True, timeout=240, env=install_env,
        )
        # POSITIVE -- the sandboxed real install must succeed.
        self.assertEqual(
            install.returncode, 0,
            f"`uv tool install {REPO_ROOT} --force` must exit 0 into the "
            f"sandboxed UV_TOOL_DIR/UV_TOOL_BIN_DIR; got "
            f"exit={install.returncode}\nstdout={install.stdout[-2000:]}"
            f"\nstderr={install.stderr[-2000:]}",
        )
        installed_bin = Path(self._uv_tool_bin_dir) / "modelb-axi"
        self.assertTrue(
            installed_bin.exists(),
            f"installed console script {installed_bin} must exist after "
            f"`uv tool install`",
        )

        run_env = dict(os.environ)
        # The dev-mode repo copy of modelb_axi must never shadow the
        # installed package -- that shadowing is exactly the masking this
        # test exists to kill.
        run_env.pop("PYTHONPATH", None)
        # Fakes-only PATH (the same composition the sandboxed dev-mode
        # e2e above uses): pre-flight must FIND the fake uv/sandesh and
        # nothing real; the installed script needs no PATH entry for its
        # own interpreter -- its shebang pins the tool venv's python by
        # absolute path (the AC1 probe runs it with no PATH restriction
        # at all, so this is strictly tighter).
        run_env["PATH"] = self._tmp_bin
        result = subprocess.run(
            [str(installed_bin), "--yes", "--harnesses", "claude-code",
             "--modelb-home", self._tmp_home,
             "--target-root", self._tmp_target_root],
            capture_output=True, text=True, timeout=60,
            stdin=subprocess.DEVNULL, env=run_env,
        )
        # POSITIVE -- the INSTALLED binary's full sandboxed install run
        # must succeed (pre-F1 this failed: no skills-src/ in
        # site-packages -> DeployError).
        self.assertEqual(
            result.returncode, 0,
            f"installed `modelb-axi` end-to-end sandboxed install must "
            f"exit 0; got exit={result.returncode} stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )

        install_toml = Path(self._tmp_home) / "install.toml"
        self.assertTrue(
            install_toml.is_file(),
            f"{install_toml} must be written by the installed binary's run",
        )
        with open(install_toml, "rb") as fh:
            data = tomllib.load(fh)
        asset_root = Path(str(data.get("install", {}).get("asset_root", "")))
        # POSITIVE/EXACT -- the recorded asset root is the force-included
        # package-data dir INSIDE the installed package, never the repo.
        self.assertEqual(
            asset_root.parts[-2:], ("modelb_axi", "_assets"),
            f"[install].asset_root must point inside the installed package "
            f"(.../modelb_axi/_assets); got {asset_root}",
        )
        self.assertTrue(
            str(asset_root).startswith(str(Path(self._uv_tool_dir).resolve())),
            f"[install].asset_root must live under the sandboxed "
            f"UV_TOOL_DIR ({Path(self._uv_tool_dir).resolve()}); got "
            f"{asset_root}",
        )
        self.assertNotEqual(
            asset_root, REPO_ROOT,
            "[install].asset_root must NOT be the repo root when running "
            "the installed package",
        )

        store_root = Path(self._tmp_target_root) / ".agents" / "skills"
        missing_store = [
            name for name in sorted(ALL_SEVEN_BUNDLE_NAMES)
            if not (store_root / name / "SKILL.md").is_file()
        ]
        # POSITIVE/EXACT -- every bundle (crucible included) physically
        # deployed into the sandbox Vercel store FROM THE PACKAGED ASSETS.
        self.assertEqual(
            missing_store, [],
            f"Vercel store must contain SKILL.md for every bundle under "
            f"{store_root} when deployed from the installed package; "
            f"missing: {missing_store}",
        )


class HooksSrcPackagingAssetTest(unittest.TestCase):
    """§S6 AC7 (CR-MDB-015) -- `hooks-src/` (schema.md + the seven protocol
    scripts) ships as packaged data: pyproject.toml force-includes it into
    the wheel under `modelb_axi/_assets/hooks-src`, mirroring the existing
    skills-src/generator/contracts/scripts rows, and the sdist only-include
    list carries it too (so a source distribution build never silently
    drops it). Direct pyproject.toml parse -- no wheel build needed."""

    def test_pyproject_force_include_and_sdist_only_include_name_hooks_src(self):
        pyproject_path = REPO_ROOT / "pyproject.toml"
        with open(pyproject_path, "rb") as fh:
            data = tomllib.load(fh)
        force_include = (
            data.get("tool", {}).get("hatch", {}).get("build", {})
            .get("targets", {}).get("wheel", {}).get("force-include", {})
        )
        # POSITIVE/EXACT -- the wheel force-include maps hooks-src into the
        # SAME package-data location the other three asset roots use.
        self.assertEqual(
            force_include.get("hooks-src"), "modelb_axi/_assets/hooks-src",
            "S6/AC7: pyproject.toml [tool.hatch.build.targets.wheel."
            "force-include] must map \"hooks-src\" = "
            f"\"modelb_axi/_assets/hooks-src\"; got force_include={force_include!r}",
        )
        sdist_only_include = (
            data.get("tool", {}).get("hatch", {}).get("build", {})
            .get("targets", {}).get("sdist", {}).get("only-include", [])
        )
        # NEGATIVE / bound -- a source distribution build must not silently
        # drop hooks-src/ either.
        self.assertIn(
            "hooks-src", sdist_only_include,
            "S6/AC7: pyproject.toml [tool.hatch.build.targets.sdist]."
            f"only-include must list \"hooks-src\"; got {sdist_only_include!r}",
        )


class HookScriptsDeployEndToEndTest(unittest.TestCase):
    """§S6 AC7 (CR-MDB-015) -- the deploy engine's sandboxed install run
    manifests the six `hooks-src/scripts/` protocol scripts user-scope,
    once, under the target-root's neutral store -- mirroring the existing
    skill-bundle store pattern (`<target-root>/.agents/skills/<name>/`,
    see DeployEngineSevenBundlesEndToEndTest above). No script-deploy path
    exists yet in modelb_axi/deploy.py (only SKILL.md-marked bundles under
    skills-src/ are deployed today -- hooks-src/scripts/ files carry no
    SKILL.md marker), so this test pins the MINIMAL contract per the
    dispatch instruction: the six scripts land under
    `<target-root>/.agents/hooks/scripts/<name>` (the deploy engine's own
    `.agents/` store root; `hooks` mirrors the `skills-src` -> `skills`
    rename the existing skill store already uses) with one install.toml
    [[files]] manifest entry each. MIGRATED (CR-MDB-030 §S7, this cycle):
    was seven scripts before the cycle-todo-naming guard's retirement; the
    deployed-set assertion below is now an EXACT bound (six, no more, no
    fewer), catching the retired script if it is still physically present
    under hooks-src/scripts/ when it should have been deleted."""

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-hookdeploy-home-")
        self._tmp_bin = tempfile.mkdtemp(prefix="modelb-axi-hookdeploy-fakebin-")
        self._tmp_target_root = tempfile.mkdtemp(prefix="modelb-axi-hookdeploy-target-")
        _write_fake_executable(self._tmp_bin, "uv", _FAKE_UV_SCRIPT)
        _write_fake_executable(self._tmp_bin, "sandesh", _FAKE_SANDESH_SCRIPT)

    def tearDown(self):
        shutil.rmtree(self._tmp_home, ignore_errors=True)
        shutil.rmtree(self._tmp_bin, ignore_errors=True)
        shutil.rmtree(self._tmp_target_root, ignore_errors=True)

    def test_end_to_end_install_deploys_six_hook_scripts_with_manifest_entries(self):
        result = _run_module(
            "--yes", "--harnesses", "claude-code",
            "--modelb-home", self._tmp_home,
            "--target-root", self._tmp_target_root,
            env_overrides={"PATH": self._tmp_bin},
        )
        self.assertEqual(
            result.returncode, 0,
            f"end-to-end sandboxed install must exit 0; got "
            f"exit={result.returncode} stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        deployed_dir = Path(self._tmp_target_root) / ".agents" / "hooks" / "scripts"
        missing_scripts = [
            name for name in HOOK_SCRIPT_NAMES
            if not (deployed_dir / name).is_file()
        ]
        # POSITIVE/EXACT -- every one of the six protocol scripts lands
        # under the store, none missing.
        self.assertEqual(
            missing_scripts, [],
            f"deployed hook-scripts store {deployed_dir} must contain all "
            f"six protocol scripts; missing={missing_scripts}",
        )
        # NEGATIVE/EXACT bound (\u00a7S7) -- exactly six scripts land, nothing
        # extra -- catches the retired cycle-todo-naming guard still being
        # deployed if hooks-src/scripts/ was not actually cleaned up.
        deployed_names = sorted(
            p.name for p in deployed_dir.iterdir() if p.is_file()
        ) if deployed_dir.is_dir() else []
        self.assertEqual(
            deployed_names, sorted(HOOK_SCRIPT_NAMES),
            f"deployed hook-scripts store {deployed_dir} must contain "
            f"EXACTLY the six surviving protocol scripts, no more (a "
            f"retired script left on disk would leak through here); got "
            f"{deployed_names!r}",
        )
        # Round-trip fidelity across the deploy boundary -- a deployed
        # script's bytes must match its hooks-src/scripts/ source exactly
        # (catches a mangled/partial/truncated copy).
        source_text = (HOOKS_SRC_SCRIPTS_DIR / "ambient-board-status").read_text(
            encoding="utf-8",
        )
        deployed_text = (deployed_dir / "ambient-board-status").read_text(
            encoding="utf-8",
        )
        self.assertEqual(
            deployed_text, source_text,
            "S6/AC7: the deployed ambient-board-status script must be "
            "byte-for-byte identical to hooks-src/scripts/ambient-board-status",
        )
        with open(Path(self._tmp_home) / "install.toml", "rb") as fh:
            data = tomllib.load(fh)
        files_section = data.get("files", [])
        manifest_paths = {
            str(entry.get("path", "")) for entry in files_section
            if isinstance(entry, dict)
        }
        expected_manifest_paths = {
            str(Path(".agents") / "hooks" / "scripts" / name)
            for name in HOOK_SCRIPT_NAMES
        }
        missing_manifest = sorted(expected_manifest_paths - manifest_paths)
        # POSITIVE/EXACT -- one install.toml [[files]] manifest entry per
        # deployed hook script.
        self.assertEqual(
            missing_manifest, [],
            f"install.toml [[files]] must record a manifest entry for "
            f"every deployed hook script; missing={missing_manifest} "
            f"(found paths sample={sorted(manifest_paths)[:20]})",
        )


if __name__ == "__main__":
    unittest.main()
