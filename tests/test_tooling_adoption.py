"""RED-phase tests for CR-MDB-022 cycle C1 (§S1 -- adopt the eight scripts
into `scripts/`; §S4 -- ship them through the installer).

Written before any of §S1/§S4's production code lands on this branch. The
current tree measures (2026-08-27):
  - `git ls-files scripts/` returns exactly one path, `scripts/.gitkeep` --
    none of the eight tools exists anywhere in this repo, so every §S1
    structural assertion below fails cleanly and every content assertion
    fails at its file-existence guard rather than on a missing attribute.
  - `modelb_axi/deploy.py` carries `STORE_RELDIR` (`.agents/skills`) and
    `HOOKS_SCRIPTS_STORE_RELDIR` (`.agents/hooks/scripts`) and no third
    asset class; there is no `.agents/scripts` constant and no enumerator
    beside `_hook_scripts()`, so the §S4 constant/enumerator tests fail on
    absence.
  - `install.toml`'s `[install]` table carries exactly `version`,
    `harnesses` and `asset_root` (`modelb_axi/cli.py`'s `_deploy_stage`),
    so the
    deployed-tooling-location key is not written and a sandboxed installer
    run deploys nothing under `<target-root>/.agents/scripts/`.

PINNED CONTRACTS (RED-authored -- none of this exists in code yet, so the
gate has to state what GREEN must produce):

1. Ownership header (§S1/AC2). No owner-header convention exists anywhere
   in the repo today, so this module pins the minimal machine-checkable
   shape rather than inventing prose: within the first
   `HEADER_SCAN_LINES` lines of each adopted script,
     - an `Owner:` key whose value names `Model B`, and
     - a consuming-skill key (`Consuming skill:` / `Consuming skills:`)
       with a non-empty value.
   Asserted PER FILE (the AC says "each carries"), never in aggregate.
   Which skills consume which tool is the CR's Context section's fact, not
   this gate's: the value is required to be present and non-empty, its
   exact roster is not pinned here.

2. Source-location executable bits (§S1/AC3). The mode bits of the eight
   files at their only live location, `~/.claude/scripts/`, were READ ONCE
   (read-only, 2026-08-27) and are pinned below as the explicit literal
   `SOURCE_EXECUTABLE_NAMES`, so this assertion never depends on that
   directory existing -- or on this machine -- at run time. Nothing in
   this module reads, writes or deletes under `~/.claude`, and no test
   here invokes `chezmoi` (§S1/AC6).

3. Store path + enumerator (§S4/AC2). `.agents/scripts` as a module-level
   `Path` constant in `modelb_axi/deploy.py`, declared in the same
   constants block as `STORE_RELDIR`/`HOOKS_SCRIPTS_STORE_RELDIR`, and an
   enumerator analogous to `_hook_scripts()` -- one asset-root argument,
   returning the flat file list under `<asset-root>/scripts`. Both are
   discovered by VALUE/BEHAVIOUR over `modelb_axi.deploy`'s module
   namespace, not by one pinned identifier spelling, so GREEN is free to
   name them (`TOOL_SCRIPTS_STORE_RELDIR`/`_tool_scripts` per §S4) without
   this gate dictating the spelling.

4. Idempotence vocabulary (§S4/AC1). `deploy_assets()` reports
   `(manifest, skipped)` and `_deploy_file()` returns a `{path, sha256}`
   entry WITHOUT copying when the destination hash already matches the
   source. "Unchanged rather than rewritten" is therefore asserted in that
   existing vocabulary: a second deploy must leave each tooling file's
   `st_mtime_ns` untouched while still carrying its manifest entry, and
   must not report it skipped-as-hand-modified.

Test boundary (PRD §D9, §S4/AC6): every deploy in this module targets a
`tempfile` sandbox created in `setUp` and removed in `tearDown`. No real
deployed path is ever asserted against -- `ToolingDeployS4Test` proves it
dynamically as well as by scanning this module's own source.

Stdlib only: unittest + os + re + shutil + subprocess + sys + tempfile +
tomllib + pathlib.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from tests.pi_capability_sandbox import with_agent_dir

from modelb_axi import deploy
from tests._helpers import write_executable as _write_fake_executable

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
GITKEEP = SCRIPTS_DIR / ".gitkeep"
DEPLOY_PY = REPO_ROOT / "modelb_axi" / "deploy.py"
THIS_MODULE_SOURCE = Path(__file__).resolve()

#: §S1 -- the eight scripts, exact names (CR-MDB-022 Context, :18-19).
TOOL_SCRIPT_NAMES = (
    "toon.py",
    "worktree-flow.py",
    "schedule_db.py",
    "skill-release-gate.py",
    "rust-code-health.py",
    "rust-crate-map.py",
    "rust-dead-scan.py",
    "gate-lock.sh",
)

#: §S1/AC3 -- pinned literal (see docstring pin 2): the six of the eight
#: whose source-location mode bits carry an executable bit (0o755); the
#: other two (`toon.py`, `schedule_db.py`) are 0o644 imported modules.
SOURCE_EXECUTABLE_NAMES = (
    "worktree-flow.py",
    "skill-release-gate.py",
    "rust-code-health.py",
    "rust-crate-map.py",
    "rust-dead-scan.py",
    "gate-lock.sh",
)

HEADER_SCAN_LINES = 40
OWNER_PATTERN = re.compile(r"^[^\n]*\bOwner\s*:[^\n]*\bModel\s*B\b", re.MULTILINE)
CONSUMING_SKILL_PATTERN = re.compile(
    r"^[^\n]*\bConsuming\s+skills?\s*:\s*(?P<value>\S[^\n]*)$", re.MULTILINE
)

#: §S1/AC4 -- the TRANSITIONAL banner's three required facts.
TRANSITIONAL_PATTERN = re.compile(r"\bTRANSITIONAL\b")
SUCCESSOR_PATTERN = re.compile(
    r"Crucible\b[^\n]{0,200}?\b(?:owns|ownership|takes over|own)\b", re.IGNORECASE | re.DOTALL
)
PLAN_STATE_STORAGE_PATTERN = re.compile(
    r"\b(?:workflow\s+)?plan\b[^\n]{0,120}?\b(?:state|storage|stor\w+)\b",
    re.IGNORECASE,
)
TRIGGER_RELEASE_PATTERN = re.compile(r"\b0\.2\.0\b")
DO_NOT_EXTEND_PATTERN = re.compile(
    r"\b(?:not\s+be\s+extended|do\s+not\s+extend|must\s+not\s+be\s+extended|never\s+extend)\b",
    re.IGNORECASE,
)

#: §S1/AC5 -- Crucible 0.2.0 is UNRELEASED (#1359) and must never be
#: presented as available. Conditional/future phrasing ("when 0.2.0
#: ships") is REQUIRED by the transitional banner, so only assertions of
#: present availability are flagged.
RELEASED_CLAIM_PATTERNS = (
    re.compile(
        r"0\.2\.0\b[^\n]{0,60}?\b(?:is|was|has\s+been|have\s+been|now)\s+"
        r"(?:already\s+)?(?:released|shipped|out|available|live|GA)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:released|shipped|available|live|GA)\b[^\n]{0,40}?"
        r"Crucible\s+0\.2\.0\b",
        re.IGNORECASE,
    ),
)
RELEASED_CLAIM_NEGATIONS = re.compile(
    r"\b(?:un|not\s+yet\s+|not\s+|never\s+)(?:released|shipped|available|live)\b",
    re.IGNORECASE,
)

#: §S4/AC2 -- the pinned store path value (discovered by value, not name).
TOOLING_STORE_RELDIR_VALUE = Path(".agents") / "scripts"

#: §S4/AC6 + §S1/AC6 -- tokens that would mean this module resolved a real
#: deployed path (or drove the dotfiles manager) instead of a temp sandbox.
#: Assembled from fragments so the scanner never matches its own source.
FORBIDDEN_REAL_HOME_TOKENS = tuple(
    left + right for left, right in (
        ("Path", ".home()"),
        ("os.path.", "expanduser"),
        (".", "expanduser("),
        ("~/.", "claude"),
        ("~/.", "agents"),
        ("chez", "moi"),
    )
)

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


def _run_installer(*args, env_overrides=None, timeout=60):
    """Drive the REAL installer entry point (`python -m modelb_axi`)."""
    env = dict(os.environ)
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + existing_pp if existing_pp else "")
    # CR-MDB-036 migration: pin PI_CODING_AGENT_DIR to a sandboxed,
    # fully provisioned Pi agent dir unless the caller pins its own --
    # the pre-flight now probes harness capabilities and no test may
    # read the real ~/.pi.
    env.update(with_agent_dir(env_overrides))
    return subprocess.run(
        [sys.executable, "-m", "modelb_axi", *args],
        capture_output=True, text=True, timeout=timeout,
        stdin=subprocess.DEVNULL, env=env,
    )


def _header_of(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    return "\n".join(text.splitlines()[:HEADER_SCAN_LINES])


def _tooling_store_constants() -> list[str]:
    """Module-level names in `modelb_axi.deploy` bound to the pinned
    `.agents/scripts` Path value (§S4/AC2 -- discovered by value)."""
    return sorted(
        name for name, value in vars(deploy).items()
        if not name.startswith("__")
        and isinstance(value, Path)
        and value == TOOLING_STORE_RELDIR_VALUE
    )


def _tooling_enumerator_candidates() -> list[tuple]:
    """Deploy-module functions that could be the `scripts/` enumerator:
    defined in `modelb_axi.deploy`, script-named, and not the existing
    hook-scripts enumerator (§S4/AC2 -- discovered by behaviour)."""
    return sorted(
        (name, value) for name, value in vars(deploy).items()
        if callable(value)
        and getattr(value, "__module__", None) == deploy.__name__
        and "script" in name
        and name != "_hook_scripts"
    )


class ToolingAdoptionS1Test(unittest.TestCase):
    """§S1 acceptance criteria -- the eight tools are ADOPTED into
    `scripts/` (the already-force-included asset root, pyproject.toml:26),
    each carrying its ownership header, source executable bits preserved,
    `schedule_db.py` carrying its TRANSITIONAL banner, and nothing in the
    asset class presenting Crucible 0.2.0 as released."""

    def _require_adopted(self, name: str) -> Path:
        path = SCRIPTS_DIR / name
        self.assertTrue(
            path.is_file(),
            f"S1/AC1: scripts/{name} must exist as a file in the repo; "
            f"{path} is not a file (scripts/ currently holds "
            f"{sorted(p.name for p in SCRIPTS_DIR.iterdir()) if SCRIPTS_DIR.is_dir() else 'no directory'})",
        )
        return path

    def test_s1_all_eight_scripts_exist_under_scripts_dir(self):
        missing = [
            name for name in TOOL_SCRIPT_NAMES
            if not (SCRIPTS_DIR / name).is_file()
        ]
        self.assertEqual(
            missing, [],
            f"S1/AC1: all eight tools must exist as files under "
            f"{SCRIPTS_DIR}; missing={missing}; present="
            f"{sorted(p.name for p in SCRIPTS_DIR.iterdir()) if SCRIPTS_DIR.is_dir() else '<no scripts/ dir>'}",
        )

    def test_s1_gitkeep_placeholder_is_gone(self):
        self.assertFalse(
            GITKEEP.exists(),
            f"S1/AC1: the placeholder {GITKEEP} must be gone once the "
            f"asset class carries real content; it still exists",
        )

    def test_s1_each_script_header_names_model_b_owner_and_consuming_skills(self):
        for name in TOOL_SCRIPT_NAMES:
            with self.subTest(script=name):
                header = _header_of(self._require_adopted(name))
                self.assertRegex(
                    header, OWNER_PATTERN,
                    f"S1/AC2: scripts/{name}'s first {HEADER_SCAN_LINES} "
                    f"lines must carry an 'Owner:' key naming Model B as "
                    f"owner; header was:\n{header}",
                )
                match = CONSUMING_SKILL_PATTERN.search(header)
                self.assertIsNotNone(
                    match,
                    f"S1/AC2: scripts/{name}'s first {HEADER_SCAN_LINES} "
                    f"lines must list its consuming skill(s) on a "
                    f"'Consuming skill(s):' key; header was:\n{header}",
                )
                self.assertNotEqual(
                    match.group("value").strip().rstrip(".-"), "",
                    f"S1/AC2: scripts/{name}'s consuming-skill key must "
                    f"name at least one skill; value was "
                    f"{match.group('value')!r}",
                )

    def test_s1_source_executable_scripts_are_executable_in_repo(self):
        self.assertEqual(
            sorted(set(SOURCE_EXECUTABLE_NAMES) - set(TOOL_SCRIPT_NAMES)), [],
            "the pinned executable literal must be a subset of the eight "
            "adopted names",
        )
        not_executable = []
        for name in SOURCE_EXECUTABLE_NAMES:
            path = self._require_adopted(name)
            if not path.stat().st_mode & 0o111:
                not_executable.append(f"{name} (mode={oct(path.stat().st_mode & 0o777)})")
        self.assertEqual(
            not_executable, [],
            f"S1/AC3: every tool executable at its source location must be "
            f"executable in the repo; these carry no executable bit: "
            f"{not_executable}",
        )

    def test_s1_schedule_db_carries_transitional_sunset_banner(self):
        path = self._require_adopted("schedule_db.py")
        header = _header_of(path)
        self.assertRegex(
            header, TRANSITIONAL_PATTERN,
            f"S1/AC4: scripts/schedule_db.py's header must be marked "
            f"TRANSITIONAL; header was:\n{header}",
        )
        self.assertRegex(
            header, SUCCESSOR_PATTERN,
            "S1/AC4: the banner must name Crucible's OWNERSHIP of the "
            f"successor as what supersedes this script; header was:\n{header}",
        )
        self.assertRegex(
            header, PLAN_STATE_STORAGE_PATTERN,
            "S1/AC4: the banner must name the superseded responsibility as "
            f"workflow plan/state storage; header was:\n{header}",
        )
        self.assertRegex(
            header, TRIGGER_RELEASE_PATTERN,
            "S1/AC4: the banner must name 0.2.0 as the release that "
            f"triggers the sunset; header was:\n{header}",
        )
        self.assertRegex(
            header, DO_NOT_EXTEND_PATTERN,
            "S1/AC4: the banner must state that the script must not be "
            f"extended; header was:\n{header}",
        )

    def test_s1_no_script_presents_crucible_020_as_released(self):
        # Guard first: a negative scan over an EMPTY asset class proves
        # nothing, so the eight must be present before it is meaningful.
        missing = [
            name for name in TOOL_SCRIPT_NAMES
            if not (SCRIPTS_DIR / name).is_file()
        ]
        self.assertEqual(
            missing, [],
            f"S1/AC5: the 0.2.0-availability scan requires a populated "
            f"asset class; missing={missing}",
        )
        offenders = []
        for path in sorted(p for p in SCRIPTS_DIR.rglob("*") if p.is_file()):
            text = path.read_text(encoding="utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if "0.2.0" not in line or RELEASED_CLAIM_NEGATIONS.search(line):
                    continue
                if any(pattern.search(line) for pattern in RELEASED_CLAIM_PATTERNS):
                    offenders.append(
                        f"{path.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}"
                    )
        self.assertEqual(
            offenders, [],
            f"S1/AC5: Crucible 0.2.0 is unreleased and must never be "
            f"presented as released/shipped/available; offending lines: "
            f"{offenders}",
        )


class ToolingDeployS4Test(unittest.TestCase):
    """§S4 acceptance criteria -- `scripts/` is a deployed asset class
    under the existing sha256 manifest discipline: a module-level
    `.agents/scripts` store constant beside the other two, an enumerator
    analogous to `_hook_scripts()`, ONE user-scope deploy with NO
    per-harness symlink, idempotence, an `[install]` string key, and a
    real-installer integration run that executes a deployed script.

    Every deploy target is a `tempfile` sandbox (PRD §D9)."""

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-tooling-home-")
        self._tmp_bin = tempfile.mkdtemp(prefix="modelb-axi-tooling-fakebin-")
        self._tmp_target_root = tempfile.mkdtemp(prefix="modelb-axi-tooling-target-")
        _write_fake_executable(self._tmp_bin, "uv", _FAKE_UV_SCRIPT)
        _write_fake_executable(self._tmp_bin, "sandesh", _FAKE_SANDESH_SCRIPT)

    def tearDown(self):
        shutil.rmtree(self._tmp_home, ignore_errors=True)
        shutil.rmtree(self._tmp_bin, ignore_errors=True)
        shutil.rmtree(self._tmp_target_root, ignore_errors=True)

    @property
    def _deployed_tooling_dir(self) -> Path:
        return Path(self._tmp_target_root) / TOOLING_STORE_RELDIR_VALUE

    def _run_real_installer(self, *extra_args):
        result = _run_installer(
            "--yes", "--harnesses", "pi",
            "--modelb-home", self._tmp_home,
            "--target-root", self._tmp_target_root,
            *extra_args,
            env_overrides={"PATH": self._tmp_bin},
        )
        self.assertEqual(
            result.returncode, 0,
            f"the sandboxed real-installer run must exit 0; got "
            f"exit={result.returncode} stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        return result

    def test_s4_store_path_constant_is_declared_beside_the_other_stores(self):
        names = _tooling_store_constants()
        self.assertNotEqual(
            names, [],
            f"S4/AC2: modelb_axi/deploy.py must bind a module-level "
            f"constant to Path('.agents')/'scripts'; no public name in "
            f"modelb_axi.deploy holds that value (Path constants present: "
            f"{ {n: str(v) for n, v in vars(deploy).items() if isinstance(v, Path) and not n.startswith('__')} })",
        )
        source_lines = DEPLOY_PY.read_text(encoding="utf-8").splitlines()
        first_body_line = next(
            (i for i, line in enumerate(source_lines)
             if line.startswith(("def ", "class "))),
            len(source_lines),
        )
        store_reldir_line = next(
            i for i, line in enumerate(source_lines)
            if line.startswith("STORE_RELDIR")
        )
        declared = [
            name for name in names
            if any(
                re.match(rf"^{re.escape(name)}\s*[:=]", line)
                for line in source_lines[store_reldir_line:first_body_line]
            )
        ]
        self.assertNotEqual(
            declared, [],
            f"S4/AC2: the tooling store constant must be declared at "
            f"module level in the same constants block as STORE_RELDIR "
            f"(line {store_reldir_line + 1}) and "
            f"HOOKS_SCRIPTS_STORE_RELDIR, before the first def/class "
            f"(line {first_body_line + 1}); candidates={names} were not "
            f"assigned in that block",
        )

    def test_s4_tooling_script_enumerator_returns_all_eight(self):
        candidates = _tooling_enumerator_candidates()
        self.assertNotEqual(
            candidates, [],
            f"S4/AC2: modelb_axi/deploy.py must expose an enumerator for "
            f"the tooling scripts analogous to _hook_scripts() (one "
            f"asset-root argument, flat file list under "
            f"<asset-root>/scripts); no such callable exists in "
            f"modelb_axi.deploy (callables present: "
            f"{sorted(n for n, v in vars(deploy).items() if callable(v) and getattr(v, '__module__', None) == deploy.__name__)})",
        )
        results = {}
        for name, func in candidates:
            try:
                results[name] = func(REPO_ROOT)
            except Exception as exc:  # enumerator must accept an asset root
                results[name] = exc
        enumerated = {
            name: value for name, value in results.items()
            if isinstance(value, list)
            and value
            and all(
                isinstance(item, Path) and item.parent == SCRIPTS_DIR
                for item in value
            )
        }
        self.assertNotEqual(
            enumerated, {},
            f"S4/AC2: the tooling enumerator called with the repo root "
            f"must return the flat file list under {SCRIPTS_DIR}; got "
            f"{ {k: (str(v) if isinstance(v, Exception) else [str(p) for p in v]) for k, v in results.items()} }",
        )
        for name, value in enumerated.items():
            with self.subTest(enumerator=name):
                self.assertEqual(
                    sorted(p.name for p in value), sorted(TOOL_SCRIPT_NAMES),
                    f"S4/AC2: {name}(<repo-root>) must enumerate exactly "
                    f"the eight tools; got {sorted(p.name for p in value)}",
                )

    def test_s4_deploy_places_eight_in_store_with_no_harness_symlink(self):
        target_root = Path(self._tmp_target_root)
        deploy.deploy_assets(REPO_ROOT, target_root)
        missing = [
            name for name in TOOL_SCRIPT_NAMES
            if not (self._deployed_tooling_dir / name).is_file()
        ]
        self.assertEqual(
            missing, [],
            f"S4/AC1: a deploy into a sandboxed target root must place all "
            f"eight tools under {self._deployed_tooling_dir}; "
            f"missing={missing}",
        )
        store_dir = self._deployed_tooling_dir.resolve()
        tooling_symlinks = [
            f"{path.relative_to(target_root)} -> {os.readlink(path)}"
            for path in sorted(target_root.rglob("*"))
            if path.is_symlink()
            and (
                Path(os.readlink(path)).resolve() == store_dir
                or store_dir in Path(os.readlink(path)).resolve().parents
            )
        ]
        self.assertEqual(
            tooling_symlinks, [],
            f"S4/AC3: the tooling deploys ONCE user-scope with NO "
            f"per-harness symlink; found symlinks pointing at the tooling "
            f"store: {tooling_symlinks}",
        )

    def test_s4_second_deploy_reports_tooling_files_unchanged(self):
        target_root = Path(self._tmp_target_root)
        first_manifest, first_skipped = deploy.deploy_assets(
            REPO_ROOT, target_root
        )
        expected_rels = {
            str(TOOLING_STORE_RELDIR_VALUE / name) for name in TOOL_SCRIPT_NAMES
        }
        first_rels = {entry["path"] for entry in first_manifest}
        self.assertEqual(
            sorted(expected_rels - first_rels), [],
            f"S4/AC1: the first deploy's manifest must carry an entry for "
            f"every tooling file; missing="
            f"{sorted(expected_rels - first_rels)}",
        )
        before = {
            name: (self._deployed_tooling_dir / name).stat().st_mtime_ns
            for name in TOOL_SCRIPT_NAMES
        }
        prior_hashes = {entry["path"]: entry["sha256"] for entry in first_manifest}
        second_manifest, second_skipped = deploy.deploy_assets(
            REPO_ROOT, target_root, prior_hashes=prior_hashes
        )
        second_rels = {entry["path"] for entry in second_manifest}
        self.assertEqual(
            sorted(expected_rels - second_rels), [],
            f"S4/AC1: the second deploy's manifest must still carry every "
            f"tooling file; missing={sorted(expected_rels - second_rels)}",
        )
        rewritten = [
            name for name in TOOL_SCRIPT_NAMES
            if (self._deployed_tooling_dir / name).stat().st_mtime_ns != before[name]
        ]
        self.assertEqual(
            rewritten, [],
            f"S4/AC1: a second deploy must report every tooling file "
            f"unchanged and leave it untouched, not rewrite it; these were "
            f"rewritten: {rewritten}",
        )
        self.assertEqual(
            sorted(rel for rel in second_skipped if rel in expected_rels), [],
            f"S4/AC1: an unmodified tooling file must be reported "
            f"unchanged, never skipped as hand-modified; skipped="
            f"{second_skipped} (first run skipped={first_skipped})",
        )

    def test_s4_install_toml_records_tooling_location_as_string(self):
        self._run_real_installer()
        with open(Path(self._tmp_home) / "install.toml", "rb") as fh:
            data = tomllib.load(fh)
        install_table = data.get("install", {})
        expected_values = {
            str(self._deployed_tooling_dir),
            str(TOOLING_STORE_RELDIR_VALUE),
        }
        # Located BY KEY NAME (CR-MDB-033 §S1): a sweep for /script|tool/
        # keys would also catch the per-class dirs §S1 records
        # (e.g. hooks_scripts_dir), which are not the tooling location.
        key = "tool_scripts_dir"
        self.assertIn(
            key, install_table,
            f"S4/AC4: install.toml's [install] table must record the "
            f"deployed tooling location under {key!r} (expected one of "
            f"{sorted(expected_values)}); [install] holds "
            f"{install_table}",
        )
        value = install_table[key]
        self.assertIsInstance(
            value, str,
            f"S4/AC4: [install].{key} must be a STRING "
            f"(config.py::_toml_value serializes only strings and "
            f"lists of strings); got {type(value)!r} value="
            f"{value!r}",
        )
        self.assertIn(
            value, expected_values,
            f"S4/AC4: [install].{key} must name the deployed "
            f"tooling location; got {value!r}, expected one of "
            f"{sorted(expected_values)}",
        )

    def test_s4_real_installer_deploys_an_executable_worktree_flow(self):
        self._run_real_installer()
        deployed = self._deployed_tooling_dir / "worktree-flow.py"
        self.assertTrue(
            deployed.is_file(),
            f"S4/AC5: the real installer run must deploy "
            f"{deployed} into the sandboxed target root; it is not a file",
        )
        result = subprocess.run(
            [sys.executable, str(deployed), "--help"],
            capture_output=True, text=True, timeout=60,
            stdin=subprocess.DEVNULL,
        )
        self.assertEqual(
            result.returncode, 0,
            f"S4/AC5 (wire-the-call-path): the deployed "
            f"worktree-flow.py --help must exit 0; got "
            f"exit={result.returncode} stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )

    def test_s4_this_module_asserts_only_sandboxed_deploy_targets(self):
        source = THIS_MODULE_SOURCE.read_text(encoding="utf-8")
        body = source.split('"""', 2)[-1]
        real_home_references = sorted(
            token for token in FORBIDDEN_REAL_HOME_TOKENS if token in body
        )
        self.assertEqual(
            real_home_references, [],
            f"S4/AC6 + S1/AC6 (PRD §D9): this module must never resolve a "
            f"real deployed path, never read or write the real user home, "
            f"and never invoke the dotfiles manager; found "
            f"{real_home_references}",
        )
        # Dynamic half: the tooling store this module drives must actually
        # materialize INSIDE the temp sandbox -- proving the boundary
        # holds against a real deploy, not just in this file's source.
        deploy.deploy_assets(REPO_ROOT, Path(self._tmp_target_root))
        deployed = sorted(
            path for path in self._deployed_tooling_dir.glob("*")
            if path.is_file()
        ) if self._deployed_tooling_dir.is_dir() else []
        self.assertEqual(
            sorted(p.name for p in deployed), sorted(TOOL_SCRIPT_NAMES),
            f"S4/AC6: the deploy this module drives must place the eight "
            f"tools under the temp sandbox {self._deployed_tooling_dir}; "
            f"got {[p.name for p in deployed]}",
        )
        tmp_root = Path(tempfile.gettempdir()).resolve()
        outside = [
            str(path) for path in deployed
            if tmp_root not in path.resolve().parents
        ]
        self.assertEqual(
            outside, [],
            f"S4/AC6: every deploy target asserted by this module must "
            f"live under {tmp_root}; these do not: {outside}",
        )


if __name__ == "__main__":
    unittest.main()
