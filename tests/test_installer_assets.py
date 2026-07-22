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

Stdlib only: unittest + subprocess + sys + shutil + tempfile + hashlib +
tomllib + importlib.util + pathlib.
"""

import hashlib
import importlib.util
import os
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

CLAUDE_SKILLS_DIR = Path.home() / ".claude" / "skills"

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

STACKS = ("arduino", "bun", "python", "quarkus")
ROLES = ("red", "green", "verify", "fix")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    """AC6 pin #1 -- the six imported bundles exist under skills-src/ as a
    faithful (byte-identical, same file set) read-only copy of the
    currently-deployed ~/.claude/skills/<name>/ tree."""

    def test_each_imported_bundle_exists_and_matches_deployed_tree_byte_for_byte(self):
        failures = []
        for name in IMPORTED_BUNDLE_NAMES:
            deployed_dir = CLAUDE_SKILLS_DIR / name
            imported_dir = SKILLS_SRC_DIR / name
            # The pin is explicit: a missing deployed dir must FAIL with a
            # clear message, never be silently skipped.
            if not deployed_dir.is_dir():
                failures.append(
                    f"{name}: deployed dir {deployed_dir} does not exist -- "
                    f"cannot verify the import is faithful"
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
            if deployed_files != imported_files:
                missing = sorted(deployed_files - imported_files)
                extra = sorted(imported_files - deployed_files)
                failures.append(
                    f"{name}: file SET mismatch against {deployed_dir} -- "
                    f"missing from import: {missing}; extra in import: {extra}"
                )
                continue
            for rel in sorted(deployed_files):
                deployed_hash = _sha256_file(deployed_dir / rel)
                imported_hash = _sha256_file(imported_dir / rel)
                if deployed_hash != imported_hash:
                    failures.append(
                        f"{name}/{rel}: sha256 mismatch -- deployed="
                        f"{deployed_hash} imported={imported_hash} "
                        f"(import must be byte-identical)"
                    )
        # POSITIVE/EXACT -- every one of the six bundles is a faithful,
        # complete, byte-identical read-only copy; zero mismatches.
        self.assertEqual(failures, [], "\n".join(failures))


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
        # POSITIVE/EXACT -- exactly the seven expected bundle names, no more
        # (e.g. memory-templates/, which has no SKILL.md, must never be
        # picked up) and no fewer.
        self.assertEqual(
            bundle_names, set(ALL_SEVEN_BUNDLE_NAMES),
            f"deploy._skill_bundles(REPO_ROOT) must discover exactly the "
            f"seven skill bundles {sorted(ALL_SEVEN_BUNDLE_NAMES)}; "
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
    RED-pinned contract) contains the 16 generated agent .md files,
    content-identical to build.py's own render() (pure, no I/O -- this
    test never shells out to build.py's `build` sub-command)."""

    def test_generator_agents_dir_contains_sixteen_files_matching_render(self):
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
        # POSITIVE/EXACT -- exactly the 16 small-stack files, none missing,
        # none extra.
        self.assertEqual(
            found_names, expected_names,
            f"{GENERATOR_AGENTS_DIR} must contain exactly the 16 "
            f"regenerated small-stack agent files; found {sorted(found_names)}",
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
        wrong_parent = [p for p in listed_paths if p.parent != GENERATOR_AGENTS_DIR]
        # POSITIVE/EXACT -- every listed path's parent is exactly the
        # pinned repo-local output dir.
        self.assertEqual(
            wrong_parent, [],
            f"generator/build.py --list must report every target under "
            f"{GENERATOR_AGENTS_DIR}; found paths with a different parent: "
            f"{wrong_parent}",
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
        # POSITIVE/EXACT -- a manifest entry for every one of the seven
        # skill bundles' SKILL.md (>=7 distinct names, exactly these seven).
        self.assertEqual(
            skill_md_names, set(ALL_SEVEN_BUNDLE_NAMES),
            f"install.toml [[files]] must record a SKILL.md entry for "
            f"exactly the seven bundles {sorted(ALL_SEVEN_BUNDLE_NAMES)}; "
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


if __name__ == "__main__":
    unittest.main()
