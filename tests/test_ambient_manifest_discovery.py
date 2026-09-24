"""Ambient board-status discovery through Crucible's client manifest, and the
Crucible client-lifecycle rules gate (CR-MDB-018 §S1–§S5).

The ambient hook ``hooks-src/scripts/ambient-board-status`` must resolve its
status feed from Crucible's released-client manifest
``$HOME/.crucible/crucible-clients.json`` (the file pre-flight already judges
Crucible by, CR-MDB-036): the nearest stack marker walking up from the
working directory picks a manifest key, and ``clients[<key>] status`` is run.
It no longer reads ``install.toml``, ``clients_dir`` or ``MODELB_HOME``;
``MODELB_STATUS_CMD`` still wins when set.

Sandbox discipline
------------------
Every case runs the REAL hook as a subprocess (``sys.executable`` + the
script path) with ``HOME`` pointed at a temp directory holding the fixture
manifest, ``MODELB_STATUS_CMD`` and ``MODELB_HOME`` removed from the
environment (unless a case sets one deliberately), and ``cwd`` a temp project
directory. The real ``~/.crucible`` is never read and no Crucible checkout is
ever loaded: the fixture envelope is built with Model B's own
``modelb_axi.toon``. Each fixture client appends ``{"key", "argv"}`` to a
per-test invocation log, so "no client invoked" is assertable.

§S3 contract pinned for the hook's marker table
-----------------------------------------------
The hook carries a module-level ``_STACK_MARKERS``: an ORDERED sequence of
``(marker_filename, stack, manifest_key)`` 3-tuples of ``str`` — the marker
file that identifies a project's stack, the stack's name as spelled in
``modelb_axi.requirements.STACK_CLIENT_KEYS``, and the ``clients`` key of
the manifest the hook runs for it. At each directory walking up from the cwd
the entries are tried in order. Parity: every ``stack`` is a key of
``STACK_CLIENT_KEYS`` and every ``manifest_key`` equals
``STACK_CLIENT_KEYS[stack]``. The table is read by loading the hook with
``importlib.machinery.SourceFileLoader`` (its file name has no ``.py`` and
carries a hyphen), so it must stay importable without side effects.

MIGRATED by CR-MDB-019 §S5 (arduino sketch marker): a ``marker_filename``
may be a TEMPLATE carrying the literal placeholder ``{dir}``, which the hook
replaces with the NAME of the candidate directory being tried (so
``"{dir}.ino"`` at ``.../sheetal-firmware/`` means
``sheetal-firmware/sheetal-firmware.ino``, the arduino-cli sketch rule).
The arduino entry is exactly ``("{dir}.ino", "arduino", "arduino")``; every
other marker is a literal filename with no ``{dir}``. The entry is still a
``str`` 3-tuple, so the same parity check covers arduino ->
``STACK_CLIENT_KEYS["arduino"]``. ``_marker_filename`` below materialises
a marker for a given directory. The fixture envelope is STATUS-CONTRACT
document 2.0.0's: it carries ``lastClosedCr`` (``lastRunCr`` is gone).
"""

import ast
import importlib.machinery
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from modelb_axi import toon  # noqa: E402
from modelb_axi.requirements import STACK_CLIENT_KEYS  # noqa: E402

HOOK_PATH = REPO_ROOT / "hooks-src" / "scripts" / "ambient-board-status"
CRUCIBLE_SKILL = REPO_ROOT / "skills-src" / "crucible" / "SKILL.md"
MANIFEST_RELPATH = Path(".crucible") / "crucible-clients.json"
MANIFEST_TILDE_FORM = "~/.crucible/crucible-clients.json"
LEGACY_DEGRADE_TEXT = "no status feed resolved"

#: The fixture board: one open plan. Its values are what "board content
#: rendered" is asserted against.
FIXTURE_CR = "CR-MDB-018"
FIXTURE_CYCLE = "C1"
FIXTURE_LAST_CLOSED_CR = "CR-MDB-036"
FIXTURE_ENVELOPE = toon.encode({"axi": {
    "verb": "status",
    "ok": True,
    "plans": [{"cr": FIXTURE_CR, "wave": 2, "status": "open",
               "activeCycleId": FIXTURE_CYCLE}],
    "lastClosedCr": FIXTURE_LAST_CLOSED_CR,
    "count": 1,
    "help": ["cr-close --commit"],
    "context": {"projectKey": "fixture-project-key"},
    "warnings": [],
}})

#: The markers the hook recognises, and the manifest key each must resolve
#: to. ``{dir}.ino`` is the arduino sketch template (CR-MDB-019 §S5).
EXPECTED_MARKER_KEYS = {
    "Cargo.toml": "rust",
    "pom.xml": "mvn",
    "bun.lock": "bun",
    "bun.lockb": "bun",
    "pyproject.toml": "python",
    "{dir}.ino": "arduino",
}


def _marker_filename(marker: str, directory: Path) -> str:
    """The file name ``marker`` denotes in ``directory``: the ``{dir}``
    placeholder (if any) replaced by the directory's own name."""
    return marker.replace("{dir}", directory.name)

#: The six top-level keys measured in Crucible's real manifest (0.2.2).
MEASURED_MANIFEST_KEYS = ("clients", "version", "status", "config",
                          "server_config", "shipped_config")


# ---------------------------------------------------------------------------
# sandbox helpers
# ---------------------------------------------------------------------------

def _client_source(key: str, log_path: Path, envelope: str = FIXTURE_ENVELOPE) -> str:
    """An executable fixture client: logs its key + argv, prints a valid
    STATUS-CONTRACT 2.0.0 ``status`` envelope, exits 0."""
    return (
        f"#!{sys.executable}\n"
        "import json, sys\n"
        f"with open({str(log_path)!r}, 'a', encoding='utf-8') as fh:\n"
        f"    fh.write(json.dumps({{'key': {key!r}, 'argv': sys.argv[1:]}}) + '\\n')\n"
        f"print({envelope!r})\n"
    )


class _Sandbox:
    """A temp HOME, a temp project dir and an invocation log."""

    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix="mdb-018-ambient-"))
        self.home = self.root / "home"
        self.home.mkdir()
        self.project = self.root / "project"
        self.project.mkdir()
        self.log = self.root / "invocations.jsonl"
        self.manifest = self.home / MANIFEST_RELPATH

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write_client(self, key: str, where: Path | None = None) -> Path:
        directory = where if where is not None else self.home / ".crucible" / "clients"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{key}-crucible.py"
        path.write_text(_client_source(key, self.log), encoding="utf-8")
        path.chmod(0o755)
        return path

    def write_manifest(self, clients: dict | None = None, *, extra: dict | None = None,
                       text: str | None = None, omit_clients: bool = False) -> Path:
        """Write the manifest shaped like Crucible's real one (the six
        measured keys). ``clients`` maps key -> path; ``text`` writes
        verbatim; ``omit_clients`` drops the ``clients`` key."""
        self.manifest.parent.mkdir(parents=True, exist_ok=True)
        if text is None:
            body = {
                "clients": {k: str(v) for k, v in (clients or {}).items()},
                "version": "0.2.2",
                "status": "installed",
                "config": str(self.home / ".crucible" / "crucible.toml"),
                "server_config": str(self.home / ".crucible" / "server.toml"),
                "shipped_config": str(self.home / ".crucible" / "shipped.toml"),
            }
            if omit_clients:
                del body["clients"]
            body.update(extra or {})
            text = json.dumps(body, indent=2) + "\n"
        self.manifest.write_text(text, encoding="utf-8")
        return self.manifest

    def mark(self, marker: str = "pyproject.toml", where: Path | None = None) -> Path:
        directory = where if where is not None else self.project
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / marker
        path.write_text("", encoding="utf-8")
        return path

    def invocations(self) -> list[dict]:
        if not self.log.exists():
            return []
        return [json.loads(line) for line in
                self.log.read_text(encoding="utf-8").splitlines() if line.strip()]

    def run_hook(self, *, cwd: Path | None = None,
                 env_overrides: dict | None = None,
                 argv_prefix: list[str] | None = None) -> subprocess.CompletedProcess:
        """Run the real hook. ``argv_prefix`` (e.g. a wrapper that alters
        the child's process state, then execs the hook) goes before the
        hook path, replacing the bare ``sys.executable``."""
        env = dict(os.environ)
        env.pop("MODELB_STATUS_CMD", None)
        env.pop("MODELB_HOME", None)
        env["HOME"] = str(self.home)
        env.update(env_overrides or {})
        return subprocess.run(
            [*(argv_prefix or [sys.executable]), str(HOOK_PATH)],
            input="{}", capture_output=True, text=True, timeout=15,
            cwd=str(cwd if cwd is not None else self.project), env=env,
        )


class _SandboxCase(unittest.TestCase):
    def setUp(self):
        self.assertTrue(HOOK_PATH.is_file(), f"expected the hook at {HOOK_PATH}")
        self.sb = _Sandbox()
        self.addCleanup(self.sb.cleanup)

    # -- shared assertions ------------------------------------------------

    def assert_board_rendered(self, result, *, via_key: str):
        self.assertEqual(result.returncode, 0,
                         f"a SessionStart hook never blocks; stderr={result.stderr!r}")
        self.assertNotIn(LEGACY_DEGRADE_TEXT, result.stdout,
                         f"the feed must resolve from the manifest; got {result.stdout!r}")
        self.assertNotIn("degraded", result.stdout.lower(),
                         f"a resolved feed renders the board, not a degrade note; "
                         f"got {result.stdout!r}")
        self.assertIn(FIXTURE_CR, result.stdout, "the plan's cr must be rendered")
        self.assertIn(FIXTURE_CYCLE, result.stdout, "the activeCycleId must be rendered")
        self.assertIn(FIXTURE_LAST_CLOSED_CR, result.stdout, "lastClosedCr must be rendered")
        calls = self.sb.invocations()
        self.assertEqual(calls, [{"key": via_key, "argv": ["status"]}],
                         f"exactly one client — clients[{via_key!r}] — run with `status`")

    def assert_degraded_without_invocation(self, result, *, manifest_related: bool):
        self.assertEqual(result.returncode, 0,
                         f"an unresolved feed degrades to exit 0; stderr={result.stderr!r}")
        lowered = result.stdout.lower()
        self.assertIn("degrad", lowered, f"expected a degrade note; got {result.stdout!r}")
        self.assertNotIn(FIXTURE_CR, result.stdout,
                         f"no board content may render when unresolved; got {result.stdout!r}")
        self.assertEqual(self.sb.invocations(), [],
                         "no client — manifest-named or substitute — may be invoked")
        if manifest_related:
            names_path = (str(self.sb.manifest) in result.stdout
                          or MANIFEST_TILDE_FORM in result.stdout)
            self.assertTrue(
                names_path,
                f"a manifest-related degrade note names the manifest path "
                f"({self.sb.manifest} or {MANIFEST_TILDE_FORM}); got {result.stdout!r}")
            self.assertIn("installer", lowered,
                          f"a manifest-related degrade note names Crucible's own "
                          f"installer; got {result.stdout!r}")
            self.assertIn("crucible", lowered)

    def plant_substitutes(self, key: str = "python"):
        """Decoy clients at every location the hook must never try: the
        manifest's conventional clients dir, ``~/.claude/scripts`` and a
        ``~/.crucible/clients`` sibling. Each logs if invoked."""
        self.sb.write_client(key, self.sb.home / ".claude" / "scripts")
        self.sb.write_client(key, self.sb.home / ".crucible" / "clients")
        self.sb.write_client(key, self.sb.home / ".crucible")


# ---------------------------------------------------------------------------
# §S1 — the hook resolves its feed from Crucible's manifest
# ---------------------------------------------------------------------------

class ManifestFeedResolutionS1Test(_SandboxCase):
    """§S1: manifest + nearest stack marker -> ``clients[<key>] status``."""

    def test_s1_manifest_client_for_the_cwd_stack_is_run_with_status_and_rendered(self):
        client = self.sb.write_client("python", self.sb.root / "released")
        self.sb.write_manifest({"python": client})
        self.sb.mark("pyproject.toml")
        self.assert_board_rendered(self.sb.run_hook(), via_key="python")

    def test_s1_each_recognised_marker_runs_its_own_manifest_key(self):
        for marker, key in EXPECTED_MARKER_KEYS.items():
            with self.subTest(marker=marker, key=key):
                sb = _Sandbox()
                self.addCleanup(sb.cleanup)
                self.sb = sb
                clients = {k: sb.write_client(k, sb.root / "released" / k)
                           for k in sorted(set(EXPECTED_MARKER_KEYS.values()))}
                sb.write_manifest(clients)
                sb.mark(_marker_filename(marker, sb.project))
                self.assert_board_rendered(sb.run_hook(), via_key=key)

    def test_s1_marker_is_found_walking_up_from_a_nested_cwd(self):
        client = self.sb.write_client("python", self.sb.root / "released")
        self.sb.write_manifest({"python": client})
        self.sb.mark("pyproject.toml")
        nested = self.sb.project / "src" / "pkg" / "deep"
        nested.mkdir(parents=True)
        self.assert_board_rendered(self.sb.run_hook(cwd=nested), via_key="python")

    def test_s1_nearest_marker_wins_over_an_ancestor_marker(self):
        released = self.sb.root / "released"
        self.sb.write_manifest({
            "python": self.sb.write_client("python", released / "py"),
            "rust": self.sb.write_client("rust", released / "rs"),
        })
        self.sb.mark("Cargo.toml")                       # ancestor: rust
        inner = self.sb.project / "bindings" / "py"
        self.sb.mark("pyproject.toml", where=inner)      # nearest: python
        self.assert_board_rendered(self.sb.run_hook(cwd=inner), via_key="python")

    def test_s1_manifest_client_path_with_a_tilde_is_expanded_under_home(self):
        """A ``~``-relative client path resolves under ``$HOME``, as
        ``capabilities.probe_crucible_client`` does (``expanduser``)."""
        self.sb.write_client("python", self.sb.home / "cl")
        self.sb.write_manifest({"python": "~/cl/python-crucible.py"})
        self.sb.mark("pyproject.toml")
        self.assert_board_rendered(self.sb.run_hook(), via_key="python")

    def test_s1_install_toml_clients_dir_under_modelb_home_is_never_read(self):
        """A ``$MODELB_HOME/install.toml`` whose ``clients_dir`` names a
        working client must NOT resolve the feed when the manifest is absent."""
        legacy_dir = self.sb.root / "legacy-clients"
        self.sb.write_client("python", legacy_dir)
        modelb_home = self.sb.root / "modelb-home"
        modelb_home.mkdir()
        (modelb_home / "install.toml").write_text(
            f'[install]\nclients_dir = "{legacy_dir}"\n', encoding="utf-8")
        self.sb.mark("pyproject.toml")
        result = self.sb.run_hook(env_overrides={"MODELB_HOME": str(modelb_home)})
        self.assert_degraded_without_invocation(result, manifest_related=True)

    def test_s1_manifest_client_is_run_even_when_install_toml_names_another(self):
        manifest_client = self.sb.write_client("python", self.sb.root / "released")
        self.sb.write_manifest({"python": manifest_client})
        legacy_dir = self.sb.root / "legacy-clients"
        legacy_dir.mkdir()
        (legacy_dir / "python-crucible.py").write_text(
            _client_source("legacy-install-toml", self.sb.log), encoding="utf-8")
        (legacy_dir / "python-crucible.py").chmod(0o755)
        modelb_home = self.sb.root / "modelb-home"
        modelb_home.mkdir()
        (modelb_home / "install.toml").write_text(
            f'[install]\nclients_dir = "{legacy_dir}"\n', encoding="utf-8")
        self.sb.mark("pyproject.toml")
        result = self.sb.run_hook(env_overrides={"MODELB_HOME": str(modelb_home)})
        self.assert_board_rendered(result, via_key="python")

    def test_s1_modelb_status_cmd_still_takes_precedence_over_the_manifest(self):
        client = self.sb.write_client("python", self.sb.root / "released")
        self.sb.write_manifest({"python": client})
        self.sb.mark("pyproject.toml")
        override = self.sb.write_client("override", self.sb.root / "override-bin")
        result = self.sb.run_hook(env_overrides={"MODELB_STATUS_CMD": str(override)})
        self.assertEqual(result.returncode, 0, f"stderr={result.stderr!r}")
        self.assertIn(FIXTURE_CR, result.stdout)
        self.assertEqual(self.sb.invocations(), [{"key": "override", "argv": []}],
                         "MODELB_STATUS_CMD is the complete feed command and wins; "
                         "the manifest client must not run")

    def test_s1_fixture_envelope_is_a_valid_feed_through_the_override_seam(self):
        """Control: the fixture client's envelope renders through the
        existing ``MODELB_STATUS_CMD`` seam, so a manifest-case failure is
        about discovery, never about the fixture."""
        client = self.sb.write_client("python", self.sb.root / "released")
        result = self.sb.run_hook(
            env_overrides={"MODELB_STATUS_CMD": f"{client} status"})
        self.assertEqual(result.returncode, 0)
        self.assertIn(FIXTURE_CR, result.stdout)
        self.assertIn(FIXTURE_CYCLE, result.stdout)
        self.assertIn(FIXTURE_LAST_CLOSED_CR, result.stdout)
        self.assertEqual(self.sb.invocations(), [{"key": "python", "argv": ["status"]}])


class HookSourceS1Test(unittest.TestCase):
    """§S1 AC: the hook source no longer reads install.toml / clients_dir /
    MODELB_HOME (checked on code string literals, not the docstring)."""

    def test_s1_hook_code_names_no_install_toml_clients_dir_or_modelb_home(self):
        literals = _code_string_literals(HOOK_PATH.read_text(encoding="utf-8"))
        for token in ("install.toml", "clients_dir", "MODELB_HOME"):
            with self.subTest(token=token):
                hits = [s for s in literals if token in s]
                self.assertEqual(hits, [], f"the hook still reads {token!r}: {hits!r}")

    def test_s1_hook_does_not_import_tomllib_or_modelb_axi(self):
        imported = _imported_modules(HOOK_PATH.read_text(encoding="utf-8"))
        self.assertNotIn("tomllib", imported,
                         "install.toml is no longer read, so tomllib has no use")
        self.assertFalse([m for m in imported if m.split(".")[0] == "modelb_axi"],
                         "the hook is deployed standalone and cannot import modelb_axi")


# ---------------------------------------------------------------------------
# §S2 — every unresolved case degrades, and nothing substitutes
# ---------------------------------------------------------------------------

class UnresolvedFeedDegradesS2Test(_SandboxCase):
    """§S2: six unresolved conditions, each: exit 0, a degrade note, no client
    invoked (decoys planted at every substitute location)."""

    def test_s2_manifest_absent_degrades_naming_the_manifest_and_installer(self):
        self.plant_substitutes("python")
        self.assertFalse(self.sb.manifest.exists())
        self.sb.mark("pyproject.toml")
        self.assert_degraded_without_invocation(self.sb.run_hook(), manifest_related=True)

    def test_s2_unparsable_manifest_degrades_naming_the_manifest_and_installer(self):
        self.plant_substitutes("python")
        self.sb.write_manifest(text='{"clients": {"python": ')
        self.sb.mark("pyproject.toml")
        self.assert_degraded_without_invocation(self.sb.run_hook(), manifest_related=True)

    def test_s2_manifest_without_clients_object_degrades(self):
        self.plant_substitutes("python")
        self.sb.write_manifest(omit_clients=True)
        self.sb.mark("pyproject.toml")
        self.assert_degraded_without_invocation(self.sb.run_hook(), manifest_related=True)

    def test_s2_manifest_whose_clients_is_not_an_object_degrades(self):
        for bad in ([], "python-crucible.py", None):
            with self.subTest(clients=bad):
                self.sb.log.unlink(missing_ok=True)
                self.plant_substitutes("python")
                self.sb.write_manifest(text=json.dumps(
                    {"clients": bad, "version": "0.2.2"}))
                self.sb.mark("pyproject.toml")
                self.assert_degraded_without_invocation(
                    self.sb.run_hook(), manifest_related=True)

    def test_s2_manifest_without_the_stacks_key_degrades_and_runs_no_other_key(self):
        self.plant_substitutes("python")
        released = self.sb.root / "released"
        self.sb.write_manifest({
            "rust": self.sb.write_client("rust", released / "rs"),
            "mvn": self.sb.write_client("mvn", released / "mvn"),
        })
        self.sb.mark("pyproject.toml")
        self.assert_degraded_without_invocation(self.sb.run_hook(), manifest_related=True)

    def test_s2_manifest_key_naming_a_missing_file_degrades(self):
        self.plant_substitutes("python")
        missing = self.sb.root / "released" / "python-crucible.py"
        self.sb.write_manifest({
            "python": missing,
            "rust": self.sb.write_client("rust", self.sb.root / "released" / "rs"),
        })
        self.assertFalse(missing.exists())
        self.sb.mark("pyproject.toml")
        self.assert_degraded_without_invocation(self.sb.run_hook(), manifest_related=True)

    def test_s2_no_stack_marker_degrades_and_guesses_no_stack(self):
        self.plant_substitutes("python")
        released = self.sb.root / "released"
        self.sb.write_manifest({k: self.sb.write_client(k, released / k)
                                for k in sorted(set(STACK_CLIENT_KEYS.values()))})
        for directory in (self.sb.project, *self.sb.project.parents):
            for marker in EXPECTED_MARKER_KEYS:
                concrete = _marker_filename(marker, directory)
                self.assertFalse((directory / concrete).exists(),
                                 f"precondition: no marker above the sandbox "
                                 f"({directory / concrete})")
        self.assert_degraded_without_invocation(self.sb.run_hook(), manifest_related=False)

    def test_s2_manifest_with_extra_unknown_keys_still_resolves(self):
        client = self.sb.write_client("python", self.sb.root / "released")
        self.sb.write_manifest({"python": client}, extra={
            "future_field": {"nested": [1, 2, 3]},
            "installed_at": "2026-09-24T00:00:00Z",
            "hooks": None,
        })
        body = json.loads(self.sb.manifest.read_text(encoding="utf-8"))
        self.assertTrue(set(MEASURED_MANIFEST_KEYS) < set(body),
                        "precondition: the six measured keys plus extras")
        self.sb.mark("pyproject.toml")
        self.assert_board_rendered(self.sb.run_hook(), via_key="python")

    # -- hardening: filesystem errors and malformed shapes never raise --------
    # Permission-denied stats raise PermissionError from ``Path.is_file()`` on
    # Python 3.11/3.12 (only ENOENT/ENOTDIR/EBADF/ELOOP are swallowed there);
    # 3.13+ swallows every OSError, so run under 3.11 to see these bite.

    def _deny(self, directory: Path):
        """chmod 000 ``directory``, restored before the sandbox is removed."""
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            self.skipTest("root ignores directory permissions")
        directory.chmod(0o000)
        self.addCleanup(directory.chmod, 0o755)

    def test_s2_unreadable_crucible_dir_degrades_without_raising(self):
        client = self.sb.write_client("python", self.sb.root / "released")
        self.plant_substitutes("python")
        self.sb.write_manifest({"python": client})
        self.sb.mark("pyproject.toml")
        self._deny(self.sb.home / ".crucible")
        self.assert_degraded_without_invocation(self.sb.run_hook(), manifest_related=True)

    def test_s2_unreadable_client_parent_dir_degrades_without_raising(self):
        released = self.sb.root / "released"
        client = self.sb.write_client("python", released)
        self.plant_substitutes("python")
        self.sb.write_manifest({"python": client})
        self.sb.mark("pyproject.toml")
        self._deny(released)
        self.assert_degraded_without_invocation(self.sb.run_hook(), manifest_related=True)

    def test_s2_manifest_whose_top_level_is_not_an_object_degrades(self):
        for bad in ([{"clients": {"python": "x"}}], "python-crucible.py"):
            with self.subTest(manifest=bad):
                self.sb.log.unlink(missing_ok=True)
                self.plant_substitutes("python")
                self.sb.write_manifest(text=json.dumps(bad))
                self.sb.mark("pyproject.toml")
                self.assert_degraded_without_invocation(
                    self.sb.run_hook(), manifest_related=True)

    def test_s2_manifest_client_entry_that_is_not_a_path_string_degrades(self):
        for bad in (123, ["a"], ""):
            with self.subTest(client=bad):
                self.sb.log.unlink(missing_ok=True)
                self.plant_substitutes("python")
                self.sb.write_manifest(text=json.dumps(
                    {"clients": {"python": bad}, "version": "0.2.2"}))
                self.sb.mark("pyproject.toml")
                self.assert_degraded_without_invocation(
                    self.sb.run_hook(), manifest_related=True)

    def test_s2_deleted_working_directory_degrades_without_raising(self):
        """The child chdirs into a temp dir, removes it, then execs the hook:
        ``os.getcwd()`` fails, which must degrade, never raise."""
        client = self.sb.write_client("python", self.sb.root / "released")
        self.sb.write_manifest({"python": client})
        self.sb.mark("pyproject.toml")
        doomed = self.sb.project / "doomed"
        doomed.mkdir()
        wrapper = ("import os, sys\n"
                   "os.chdir(sys.argv[1]); os.rmdir(sys.argv[1])\n"
                   "os.execv(sys.executable, [sys.executable, sys.argv[2]])\n")
        result = self.sb.run_hook(
            argv_prefix=[sys.executable, "-c", wrapper, str(doomed)])
        self.assertFalse(doomed.exists(), "precondition: the cwd was removed")
        self.assert_degraded_without_invocation(result, manifest_related=False)


_FORBIDDEN_PATH_TOKENS = (
    ".claude",            # ~/.claude/scripts or any ~/.claude location
    "site-packages",
    "dist-packages",
    "_assets",            # modelb_axi's package-internal asset root
    "data_projects",      # a Crucible source checkout
    "crucible/clients",   # a checkout's (or install's) clients dir by convention
)
_FORBIDDEN_IMPORTS = ("site", "sysconfig", "importlib", "modelb_axi")


def _docstring_nodes(tree: ast.AST) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            body = getattr(node, "body", [])
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                ids.add(id(body[0].value))
    return ids


def _code_string_literals(source: str) -> list[str]:
    """Every string constant in ``source`` except docstrings."""
    tree = ast.parse(source)
    skip = _docstring_nodes(tree)
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in skip]


def _imported_modules(source: str) -> list[str]:
    names = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def _substitute_path_findings(source: str) -> list[str]:
    """Findings for any code literal naming a substitute location, or any
    import that could reach one."""
    findings = []
    for literal in _code_string_literals(source):
        for token in _FORBIDDEN_PATH_TOKENS:
            if token in literal:
                findings.append(f"literal {literal!r} names {token!r}")
    for module in _imported_modules(source):
        if module.split(".")[0] in _FORBIDDEN_IMPORTS:
            findings.append(f"imports {module!r}")
    return findings


class NoSubstituteLocationS2Test(unittest.TestCase):
    """§S2 AC: no path to ``~/.claude/scripts``, a site-packages directory or
    a Crucible checkout appears in the hook."""

    def test_s2_hook_names_no_substitute_client_location(self):
        findings = _substitute_path_findings(HOOK_PATH.read_text(encoding="utf-8"))
        self.assertEqual(findings, [])

    def test_s2_detector_flags_a_claude_scripts_path_built_by_joins(self):
        src = 'from pathlib import Path\nP = Path.home() / ".claude" / "scripts"\n'
        self.assertEqual(_substitute_path_findings(src),
                         ["literal '.claude' names '.claude'"])

    def test_s2_detector_flags_site_packages_and_checkout_paths(self):
        src = ('import site\nA = "lib/python3/site-packages/crucible"\n'
               'B = "~/Documents/data_projects/crucible/clients"\n')
        findings = _substitute_path_findings(src)
        self.assertIn("imports 'site'", findings)
        self.assertTrue(any("site-packages" in f for f in findings), findings)
        self.assertTrue(any("data_projects" in f for f in findings), findings)
        self.assertTrue(any("crucible/clients" in f for f in findings), findings)

    def test_s2_detector_ignores_a_docstring_mention(self):
        src = ('"""Never tries ~/.claude/scripts or site-packages."""\n'
               'def f():\n    """Nor data_projects/crucible/clients."""\n    return 1\n')
        self.assertEqual(_substitute_path_findings(src), [])


# ---------------------------------------------------------------------------
# §S3 — the hook and pre-flight agree on the keys
# ---------------------------------------------------------------------------

def _load_hook_module():
    """Load the hook as a module without writing bytecode beside it (a
    ``__pycache__`` in ``hooks-src/scripts/`` would pollute the asset tree)."""
    loader = importlib.machinery.SourceFileLoader("ambient_board_status_hook",
                                                  str(HOOK_PATH))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None, f"could not build a module spec for {HOOK_PATH}"
    module = importlib.util.module_from_spec(spec)
    saved = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved
    return module


def _marker_table_parity_findings(table, stack_client_keys: dict) -> list[str]:
    """Findings where a ``(marker, stack, manifest_key)`` table disagrees with
    ``STACK_CLIENT_KEYS`` — or is not shaped as the pinned contract."""
    findings = []
    if not isinstance(table, (tuple, list)) or not table:
        return [f"table is not a non-empty sequence: {table!r}"]
    for entry in table:
        if (not isinstance(entry, (tuple, list)) or len(entry) != 3
                or not all(isinstance(x, str) for x in entry)):
            findings.append(f"entry {entry!r} is not a (marker, stack, key) str 3-tuple")
            continue
        marker, stack, key = entry
        if stack not in stack_client_keys:
            findings.append(f"{marker}: stack {stack!r} is not in STACK_CLIENT_KEYS")
        elif stack_client_keys[stack] != key:
            findings.append(f"{marker}: stack {stack!r} -> key {key!r}, "
                            f"STACK_CLIENT_KEYS says {stack_client_keys[stack]!r}")
    return findings


class MarkerKeyParityS3Test(unittest.TestCase):
    """§S3: the hook's ``_STACK_MARKERS`` agrees with ``STACK_CLIENT_KEYS``."""

    def test_s3_hook_marker_table_agrees_with_stack_client_keys(self):
        table = getattr(_load_hook_module(), "_STACK_MARKERS", None)
        self.assertEqual(_marker_table_parity_findings(table, STACK_CLIENT_KEYS), [])

    def test_s3_hook_marker_table_covers_every_recognised_marker(self):
        table = getattr(_load_hook_module(), "_STACK_MARKERS", ())
        mapping = {e[0]: e[2] for e in table
                   if isinstance(e, (tuple, list)) and len(e) == 3}
        self.assertEqual(mapping, EXPECTED_MARKER_KEYS)

    def test_s3_detector_bites_on_a_key_mismatch(self):
        bad = (("pyproject.toml", "python", "python"),
               ("pom.xml", "quarkus", "quarkus"))
        self.assertEqual(
            _marker_table_parity_findings(bad, STACK_CLIENT_KEYS),
            ["pom.xml: stack 'quarkus' -> key 'quarkus', STACK_CLIENT_KEYS says 'mvn'"])

    def test_s3_detector_bites_on_an_unknown_stack_and_a_malformed_entry(self):
        bad = (("pyproject.toml", "snake", "python"), ("Cargo.toml", "rust-crucible.py"))
        findings = _marker_table_parity_findings(bad, STACK_CLIENT_KEYS)
        self.assertEqual(len(findings), 2, findings)
        self.assertIn("not in STACK_CLIENT_KEYS", findings[0])
        self.assertIn("is not a (marker, stack, key)", findings[1])

    def test_s3_detector_passes_a_table_in_parity(self):
        good = (("Cargo.toml", "rust", "rust"), ("pom.xml", "java", "mvn"),
                ("pom.xml", "quarkus", "mvn"), ("pyproject.toml", "python", "python"))
        self.assertEqual(_marker_table_parity_findings(good, STACK_CLIENT_KEYS), [])


# ---------------------------------------------------------------------------
# §S4 — the seam, end to end
# ---------------------------------------------------------------------------

class ManifestSeamEndToEndS4Test(_SandboxCase):
    """§S4: the real hook, sandboxed HOME with a fixture manifest, a stack
    marker, MODELB_STATUS_CMD and MODELB_HOME unset -> board content, exit 0."""

    def test_s4_real_hook_renders_the_board_from_the_manifest_client(self):
        client = self.sb.write_client("python", self.sb.root / "released")
        self.sb.write_manifest({"python": client})
        self.sb.mark("pyproject.toml")
        result = self.sb.run_hook()
        self.assertEqual(result.returncode, 0, f"stderr={result.stderr!r}")
        self.assertNotIn(LEGACY_DEGRADE_TEXT, result.stdout)
        self.assertIn(f"cr={FIXTURE_CR}", result.stdout)
        self.assertIn(f"activeCycleId={FIXTURE_CYCLE}", result.stdout)
        self.assertIn(f"last closed: {FIXTURE_LAST_CLOSED_CR}", result.stdout)
        self.assertEqual(self.sb.invocations(), [{"key": "python", "argv": ["status"]}])


# ---------------------------------------------------------------------------
# §S5 — the client lifecycle rules are gated
# ---------------------------------------------------------------------------

#: Each element of the two lifecycle rules, as a regex over the lower-cased,
#: whitespace-collapsed SKILL.md text.
_LIFECYCLE_ELEMENTS = (
    ("ingest-rule:ingest-before-cycle-done",
     r"ingest[^.]*before\s+`?cycle-done"),
    ("ingest-rule:pass-cycle-flag",
     r"ingest[^.]*before[^.]*`?cycle-done`?[^.]*--cycle <id>"),
    ("ingest-rule:after-close-refused",
     r"after\s+its\s+cycle\s+(closed|is\s+done|was\s+done)[^.]*refused"),
    ("ingest-rule:nothing-backfills",
     r"nothing\s+backfills"),
    ("ingest-rule:unbound-run-project-scoped",
     r"bound\s+to\s+no\s+cycle[^.]*project-scoped"),
    ("ingest-rule:unbound-run-untraceable",
     r"project-scoped[^.]*(can\s+never\s+be\s+traced|untraceable)"),
    ("binding-rule:stale-binding-survives-reregistration",
     r"stale\s+cycle\s+binding\s+survives\s+re-?registration"),
    ("binding-rule:unregister-then-register",
     r"`?unregister`?\s+then\s+`?register`?"),
    ("binding-rule:unbound-orchestrator-avoids-it",
     r"orchestrator\b[^.]*\b(never\s+binds|unbound)\b[^.]*\bavoid"),
)


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).lower()


def _lifecycle_rule_findings(text: str) -> list[str]:
    """The lifecycle-rule elements ``text`` fails to state."""
    norm = _normalise(text)
    return [name for name, pattern in _LIFECYCLE_ELEMENTS
            if not re.search(pattern, norm)]


def _remove_bullet(text: str, bullet_start: str) -> str:
    """Drop the markdown bullet beginning with ``bullet_start`` (through the
    line before the next bullet or blank line)."""
    lines = text.splitlines(keepends=True)
    out, skipping = [], False
    for line in lines:
        if line.startswith(bullet_start):
            skipping = True
            continue
        if skipping and (line.startswith("- ") or not line.strip()):
            skipping = False
        if not skipping:
            out.append(line)
    return "".join(out)


_INGEST_BULLET = "- **Ingest the run BEFORE `cycle-done`"
_BINDING_BULLET = "- **A stale cycle binding survives re-registration"


class CrucibleLifecycleRulesS5Test(unittest.TestCase):
    """§S5: ``skills-src/crucible/SKILL.md`` states both client lifecycle
    rules in substance. The text already exists at RED — this gate passes by
    design and exists to catch a later rewrite; the detectors prove it bites."""

    def setUp(self):
        self.text = CRUCIBLE_SKILL.read_text(encoding="utf-8")

    def test_s5_crucible_skill_states_both_lifecycle_rules(self):
        self.assertEqual(_lifecycle_rule_findings(self.text), [])

    def test_s5_detector_bites_when_the_ingest_rule_is_removed(self):
        self.assertIn(_INGEST_BULLET, self.text, "precondition: the ingest bullet exists")
        stripped = _remove_bullet(self.text, _INGEST_BULLET)
        self.assertNotEqual(stripped, self.text)
        findings = _lifecycle_rule_findings(stripped)
        self.assertTrue(findings, "removing the ingest rule must fail the gate")
        self.assertTrue(all(f.startswith("ingest-rule:") for f in findings), findings)
        self.assertIn("ingest-rule:nothing-backfills", findings)
        self.assertIn("ingest-rule:unbound-run-project-scoped", findings)

    def test_s5_detector_bites_when_the_binding_rule_is_removed(self):
        self.assertIn(_BINDING_BULLET, self.text, "precondition: the binding bullet exists")
        stripped = _remove_bullet(self.text, _BINDING_BULLET)
        findings = _lifecycle_rule_findings(stripped)
        self.assertEqual(findings, [
            "binding-rule:stale-binding-survives-reregistration",
            "binding-rule:unregister-then-register",
            "binding-rule:unbound-orchestrator-avoids-it",
        ])

    def test_s5_detector_bites_on_a_weakened_single_element(self):
        weakened = self.text.replace("nothing backfills it", "it may be re-sent later")
        self.assertNotEqual(weakened, self.text, "precondition: phrase present")
        self.assertEqual(_lifecycle_rule_findings(weakened),
                         ["ingest-rule:nothing-backfills"])


if __name__ == "__main__":
    unittest.main()
