"""The installer finds and records an interpreter that meets the Python floor
(CR-MDB-064 §S2; DN-multi-harness-deploy-model §D22).

- **The probe.** The ``python3`` requirement is ``required``, with the probe kind
  ``interpreter`` and the remediation ``uv python install 3.14``. Candidates, in order: the
  ``python3`` on ``PATH``, then the interpreter ``uv python find --system '>=3.14'`` reports.
  A candidate is accepted when it runs, reports a version ≥ 3.14 and is not a virtual
  environment (``sys.prefix == sys.base_prefix``). The path recorded is the candidate's
  absolute path as found, its link not resolved; a path holding whitespace, or longer than
  the kernel's shebang limit, is rejected.
- **The verdict.** ``[capabilities].python3`` is ``detected`` when a candidate is accepted,
  ``outdated`` when a ``python3`` below the floor exists and none is accepted, ``absent`` when
  there is neither. One stderr line reports it: ``python3: <path> (<version>)``, or
  ``python3=outdated|absent — <reason>; install it with: uv python install 3.14``.
- **The refusal.** With no accepted candidate the pre-flight fails before any write —
  ``--allow-missing-capabilities`` does not override it, and a run with no ``--target-root``
  still probes and still refuses.
- **The record.** ``run_preflight`` returns the accepted interpreter after its existing
  results — ``(exit_code, deps, capabilities, python)`` — and ``install.toml`` records it as
  ``[install] python``; a re-run records it again. ``init`` reads only the verdict, and its
  capability contract renders ``python3`` with no ``unknown``.

Every run is sandboxed on the shared installer fixture (``tests._helpers``
``write_interpreter_fixture``): ``PATH`` is a fake-bin dir holding a ``python3`` stand-in and a
``uv`` stand-in answering ``uv python find --system '>=3.14'``; ``HOME``, ``PI_CODING_AGENT_DIR``,
``MODELB_HOME`` and ``XDG_DATA_HOME`` are throw-away dirs. Nothing reads or writes the real home.

Stdlib only.
"""

import contextlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from tests._helpers import (
    PYTHON_REMEDIATION,
    UV_PYTHON_FIND_ARGS,
    decode_axi,
    python3_stub,
    run_module,
    write_executable,
    write_interpreter_fixture,
)
from tests.pi_capability_sandbox import (
    AGENT_DIR_ENV,
    fake_sandesh,
    make_home,
    make_provisioned_agent_dir,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

#: §S2's verdict vocabulary for ``[capabilities].python3``.
FOUR_VERDICTS = ("detected", "installed", "absent", "outdated")

#: A stderr line's optional ``modelb-axi: <level>: `` prefix, which the human channel adds to
#: a warning or an error.
_LEVEL_PREFIX = r"(?:modelb-axi: (?:\w+: )?)?"


def _accepted_line(path: str, version: str) -> re.Pattern:
    """§S2's stderr line for an accepted candidate: ``python3: <path> (<version>)``. The version
    may be written ``X.Y`` or ``X.Y.Z``."""
    major_minor = ".".join(version.split(".")[:2])
    return re.compile(
        rf"^{_LEVEL_PREFIX}python3: {re.escape(path)} \({re.escape(major_minor)}(?:\.\d+)?\)$")


def _refusal_line(verdict: str) -> re.Pattern:
    """§S2's stderr line when no candidate is accepted."""
    return re.compile(
        rf"^{_LEVEL_PREFIX}python3={verdict} — \S.*; install it with: "
        rf"{re.escape(PYTHON_REMEDIATION)}$")


def _matching_lines(stderr: str, pattern: re.Pattern) -> list[str]:
    return [line for line in stderr.splitlines() if pattern.match(line.strip())]


class _InterpreterSandboxCase(unittest.TestCase):
    """Per-test sandbox: a fake-bin ``PATH`` (a current ``sandesh``; ``python3`` and ``uv`` are
    each test's own fixture), a second dir standing for the interpreters uv manages, a home
    without Crucible's manifest and a provisioned Pi agent dir, so the interpreter is the only
    requirement a run can miss."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="modelb-cr064-interp-")).resolve()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.bin_dir = self.root / "bin"
        self.uv_pythons = self.root / "uv-pythons" / "cpython-3.14.0-linux" / "bin"
        self.modelb_home = self.root / "modelb-home"
        self.target_root = self.root / "target"
        self.xdg = self.root / "xdg"
        self.uv_log = self.root / "uv-python-find.log"
        for d in (self.bin_dir, self.uv_pythons, self.modelb_home, self.target_root, self.xdg):
            d.mkdir(parents=True)
        self.home = make_home(self.root / "home", crucible_manifest=False)
        self.agent_dir = make_provisioned_agent_dir(self.root / "agent")
        write_executable(self.bin_dir, "sandesh", fake_sandesh())

    # -- fixtures ---------------------------------------------------------

    def uv_python(self, version: str = "3.14.0", *, directory: Path | None = None,
                  name: str = "python3.14") -> Path:
        """A system interpreter uv reports, outside ``PATH``."""
        directory = directory or self.uv_pythons
        directory.mkdir(parents=True, exist_ok=True)
        return write_executable(directory, name, python3_stub(version))

    def sandbox_env(self, path: Path | None = None) -> dict:
        return {
            "HOME": str(self.home),
            "PATH": str(path or self.bin_dir),
            AGENT_DIR_ENV: str(self.agent_dir),
            "MODELB_HOME": str(self.modelb_home),
            "XDG_DATA_HOME": str(self.xdg),
        }

    # -- runners ----------------------------------------------------------

    def run_installer(self, *extra, deploy: bool = True, path: Path | None = None,
                      stacks: str = "rust") -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env.pop("MODELB_TARGET_ROOT", None)
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + existing if existing else "")
        env.update(self.sandbox_env(path))
        for name in ("HOME", AGENT_DIR_ENV, "MODELB_HOME", "XDG_DATA_HOME"):
            self.assertTrue(env[name].startswith(str(self.root)),
                            f"sandbox guard: {name}={env[name]!r} outside {self.root}")
        args = ["--yes", "--harnesses", "pi", "--modelb-home", str(self.modelb_home),
                "--stacks", stacks]
        if deploy:
            args += ["--target-root", str(self.target_root)]
        return subprocess.run(
            [sys.executable, "-m", "modelb_axi", *args, *extra],
            capture_output=True, text=True, timeout=90, stdin=subprocess.DEVNULL, env=env,
        )

    # -- readers ----------------------------------------------------------

    def install_toml(self) -> dict:
        path = self.modelb_home / "install.toml"
        if not path.is_file():
            self.fail(f"install.toml not written under {self.modelb_home}")
        with open(path, "rb") as fh:
            return tomllib.load(fh)

    def uv_find_calls(self) -> list[list[str]]:
        if not self.uv_log.exists():
            return []
        return [line.split() for line in self.uv_log.read_text(encoding="utf-8").splitlines()
                if line.strip()]

    # -- assertions -------------------------------------------------------

    def assert_recorded(self, result, interpreter: Path | None, version: str) -> None:
        """The run installs, records ``interpreter`` as found and ``python3 = detected``, and
        prints the accepted line naming it — exactly once."""
        axi = decode_axi(result.stdout)
        self.assertEqual((result.returncode, axi.get("outcome")), (0, "installed"),
                         f"stdout={result.stdout!r} stderr={result.stderr!r}")
        data = self.install_toml()
        self.assertEqual(data.get("install", {}).get("python"), str(interpreter),
                         f"§S2: [install] python is the accepted candidate's absolute path as "
                         f"found; install={data.get('install')!r}")
        self.assertEqual(data.get("capabilities", {}).get("python3"), "detected",
                         f"§S2: an accepted candidate is `detected`; "
                         f"capabilities={data.get('capabilities')!r}")
        lines = _matching_lines(result.stderr, _accepted_line(str(interpreter), version))
        self.assertEqual(len(lines), 1,
                         f"§S2: one `python3: {interpreter} ({version})` line on stderr; "
                         f"stderr={result.stderr!r}")

    def assert_refused(self, result, verdict: str, reason: str | None = None) -> None:
        """The pre-flight fails before any write, with §S2's refusal line for ``verdict`` —
        its reason naming ``reason``, when given (DN §D22: the reason names the rejection)."""
        axi = decode_axi(result.stdout)
        self.assertNotEqual(result.returncode, 0,
                            f"§S2: no accepted interpreter refuses; stderr={result.stderr!r}")
        self.assertEqual(axi.get("outcome"), "preflight_failed",
                         f"§S2: the refusal is the pre-flight's; axi={axi!r} "
                         f"stderr={result.stderr!r}")
        self.assertFalse((self.modelb_home / "install.toml").exists(),
                         "§S2: the refusal comes before any write — no install.toml")
        self.assertEqual(sorted(p.name for p in self.target_root.iterdir()), [],
                         "§S2: the refusal comes before any write — nothing deployed")
        lines = _matching_lines(result.stderr, _refusal_line(verdict))
        self.assertEqual(len(lines), 1,
                         f"§S2: one `python3={verdict} — <reason>; install it with: "
                         f"{PYTHON_REMEDIATION}` line; stderr={result.stderr!r}")
        if reason is not None:
            self.assertIn(reason, lines[0],
                          f"DN §D22: the refusal's reason names the rejection; line={lines[0]!r}")


# ---------------------------------------------------------------------------
# §S2 — the candidates, and what is accepted
# ---------------------------------------------------------------------------

class InterpreterAcceptanceTest(_InterpreterSandboxCase):
    """§S2 AC: ``python3`` ≥ 3.14 is detected and its path recorded; below the floor, uv's
    system 3.14 is detected and its path recorded; a 3.15-only machine is accepted."""

    def test_path_python3_at_the_floor_is_detected_and_its_path_recorded(self):
        python3 = write_interpreter_fixture(self.bin_dir, uv_found=None, uv_log=self.uv_log)
        result = self.run_installer()
        self.assert_recorded(result, python3, "3.14.0")

    def test_python3_below_the_floor_falls_back_to_uvs_system_interpreter(self):
        uv_python = self.uv_python("3.14.0")
        write_interpreter_fixture(self.bin_dir, version="3.12.3", uv_found=uv_python,
                                  uv_log=self.uv_log)
        result = self.run_installer()
        self.assert_recorded(result, uv_python, "3.14.0")
        calls = self.uv_find_calls()
        self.assertTrue(calls, "§S2: the second candidate comes from `uv python find`")
        for call in calls:
            with self.subTest(call=call):
                self.assertEqual(call[:2], list(UV_PYTHON_FIND_ARGS[:2]), calls)
                self.assertIn("--system", call,
                              "§S2: `--system` — a virtual environment is never reported")
                self.assertIn(">=3.14", call, "§S2: the floor is a range, not 3.14.x only")

    def test_a_machine_with_only_python_315_is_accepted(self):
        python3 = write_interpreter_fixture(self.bin_dir, version="3.15.0", uv_found=None)
        result = self.run_installer()
        self.assert_recorded(result, python3, "3.15.0")

    def test_the_path_recorded_is_the_one_found_not_its_link_resolved(self):
        real = self.root / "opt" / "python" / "bin"
        real.mkdir(parents=True)
        target = write_executable(real, "python3.14", python3_stub("3.14.0"))
        write_interpreter_fixture(self.bin_dir, python3=False, uv_found=None)
        link = self.bin_dir / "python3"
        link.symlink_to(target)
        result = self.run_installer()
        self.assert_recorded(result, link, "3.14.0")
        self.assertNotEqual(self.install_toml()["install"].get("python"), str(target),
                            "§S2: the link is not resolved")

    def test_a_rerun_probes_and_records_the_interpreter_again(self):
        first = write_interpreter_fixture(self.bin_dir, uv_found=None)
        self.assert_recorded(self.run_installer(), first, "3.14.0")
        uv_python = self.uv_python("3.14.0")
        write_interpreter_fixture(self.bin_dir, version="3.12.3", uv_found=uv_python)
        result = self.run_installer("--reinstall")
        self.assert_recorded(result, uv_python, "3.14.0")


class InterpreterRejectionTest(_InterpreterSandboxCase):
    """§S2 AC: a virtual-environment candidate is rejected; a candidate whose path holds
    whitespace is rejected; so is one longer than the kernel's shebang limit."""

    def test_a_virtual_environment_on_path_is_passed_over_for_uvs_system_interpreter(self):
        uv_python = self.uv_python("3.14.0")
        write_interpreter_fixture(self.bin_dir, venv=True, uv_found=uv_python)
        result = self.run_installer()
        self.assert_recorded(result, uv_python, "3.14.0")

    def test_a_path_python3_holding_whitespace_is_passed_over_for_uvs(self):
        spaced = self.root / "bin with space"
        spaced.mkdir()
        write_executable(spaced, "sandesh", fake_sandesh())
        uv_python = self.uv_python("3.14.0")
        write_interpreter_fixture(spaced, uv_found=uv_python)
        result = self.run_installer(path=spaced)
        self.assert_recorded(result, uv_python, "3.14.0")

    def test_a_uv_interpreter_holding_whitespace_is_rejected_and_the_install_refused(self):
        spaced = self.uv_python("3.14.0", directory=self.root / "uv pythons" / "bin")
        write_interpreter_fixture(self.bin_dir, version="3.12.3", uv_found=spaced)
        result = self.run_installer()
        self.assert_refused(result, "outdated")

    def test_a_path_python3_longer_than_the_shebang_limit_is_passed_over(self):
        deep = self.root
        for index in range(6):
            deep = deep / (f"d{index}-" + "x" * 50)
        self.assertGreater(len(str(deep / "python3")), 300, "fixture: an over-long path")
        deep.mkdir(parents=True)
        write_executable(deep, "sandesh", fake_sandesh())
        uv_python = self.uv_python("3.14.0")
        write_interpreter_fixture(deep, uv_found=uv_python)
        result = self.run_installer(path=deep)
        self.assert_recorded(result, uv_python, "3.14.0")

    def _path_dir_for_python3_of(self, length: int) -> Path:
        """A fresh ``PATH`` dir (holding a ``sandesh``) in which ``python3``'s absolute path is
        exactly ``length`` bytes."""
        base = self.root / "shebang"
        remaining = length - len(str(base).encode()) - len("/python3")
        self.assertGreaterEqual(remaining, 2, f"fixture: {base} leaves no room for {length}")
        count = -(-remaining // 101)
        names = remaining - count
        sizes = [names // count + (1 if i < names % count else 0) for i in range(count)]
        directory = base.joinpath(*(f"{i % 10}" * size for i, size in enumerate(sizes)))
        directory.mkdir(parents=True)
        write_executable(directory, "sandesh", fake_sandesh())
        self.assertEqual(len(str(directory / "python3").encode()), length, "fixture: the path")
        return directory

    def test_a_path_python3_whose_shebang_line_is_exactly_the_limit_is_accepted(self):
        directory = self._path_dir_for_python3_of(253)
        python3 = write_interpreter_fixture(directory, uv_found=None)
        self.assertEqual(len(f"#!{python3}\n".encode()), 256,
                         "fixture: `#!<path>\\n` fills the 256-byte shebang buffer exactly")
        result = self.run_installer(path=directory)
        self.assert_recorded(result, python3, "3.14.0")

    def test_a_path_python3_whose_shebang_line_is_one_byte_over_the_limit_is_passed_over(self):
        directory = self._path_dir_for_python3_of(254)
        uv_python = self.uv_python("3.14.0")
        python3 = write_interpreter_fixture(directory, uv_found=uv_python)
        self.assertEqual(len(f"#!{python3}\n".encode()), 257,
                         "fixture: `#!<path>\\n` is one byte over the 256-byte shebang buffer")
        result = self.run_installer(path=directory)
        self.assert_recorded(result, uv_python, "3.14.0")


# ---------------------------------------------------------------------------
# §S2 — the verdict and the refusal
# ---------------------------------------------------------------------------

class InterpreterRefusalTest(_InterpreterSandboxCase):
    """§S2 AC: below the floor with none found is ``outdated`` and refused; no ``python3`` with
    none found is ``absent`` and refused; the refusal holds with
    ``--allow-missing-capabilities`` and with no ``--target-root``."""

    def test_python3_below_the_floor_and_none_found_is_outdated_and_refused(self):
        write_interpreter_fixture(self.bin_dir, version="3.12.3", uv_found=None)
        self.assert_refused(self.run_installer(), "outdated")

    def test_no_python3_and_none_found_is_absent_and_refused(self):
        write_interpreter_fixture(self.bin_dir, python3=False, uv_found=None)
        self.assert_refused(self.run_installer(), "absent")

    def test_a_python3_that_cannot_report_its_version_and_none_found_is_absent_and_refused(self):
        """DN §D22: ``outdated`` only for a ``python3`` that runs and reports a version below
        the floor — one that fails, or answers with something that is not a version, is
        ``absent``."""
        bodies = {
            "exits non-zero": "#!/bin/sh\nexit 1\n",
            "prints junk": "#!/bin/sh\necho 'not a version'\nexit 0\n",
        }
        for case, body in bodies.items():
            with self.subTest(case=case):
                write_interpreter_fixture(self.bin_dir, python3=False, uv_found=None)
                write_executable(self.bin_dir, "python3", body)
                self.assert_refused(self.run_installer(), "absent",
                                    reason="did not report its version")

    def test_a_virtual_environment_python3_and_none_found_is_absent_and_refused(self):
        """DN §D22: a ``python3`` at the floor rejected as a virtual environment counts as
        none — ``absent``, the reason naming the virtual environment."""
        write_interpreter_fixture(self.bin_dir, venv=True, uv_found=None)
        self.assert_refused(self.run_installer(), "absent", reason="virtual environment")

    def test_allow_missing_capabilities_does_not_override_the_refusal(self):
        write_interpreter_fixture(self.bin_dir, version="3.12.3", uv_found=None)
        result = self.run_installer("--allow-missing-capabilities")
        self.assert_refused(result, "outdated")

    def test_a_run_with_no_target_root_still_refuses(self):
        write_interpreter_fixture(self.bin_dir, python3=False, uv_found=None)
        result = self.run_installer(deploy=False)
        self.assert_refused(result, "absent")
        self.assertNotEqual(decode_axi(result.stdout).get("outcome"), "deploy_skipped")

    def test_a_run_with_no_target_root_still_probes_and_reports(self):
        python3 = write_interpreter_fixture(self.bin_dir, uv_found=None)
        result = self.run_installer(deploy=False)
        axi = decode_axi(result.stdout)
        self.assertEqual((result.returncode, axi.get("outcome")), (0, "deploy_skipped"),
                         result.stderr)
        self.assertEqual(len(_matching_lines(result.stderr,
                                             _accepted_line(str(python3), "3.14.0"))), 1,
                         f"§S2: the probe runs without a deploy; stderr={result.stderr!r}")
        self.assertFalse((self.modelb_home / "install.toml").exists())


# ---------------------------------------------------------------------------
# §S2 — run_preflight returns the accepted interpreter
# ---------------------------------------------------------------------------

class PreflightReturnsInterpreterTest(_InterpreterSandboxCase):
    """§S2 "The record": ``run_preflight`` returns the accepted interpreter alongside its
    existing results, as a fourth element: ``(exit_code, deps, capabilities, python)``."""

    def _preflight(self) -> tuple[tuple, str]:
        from modelb_axi import preflight
        stderr = io.StringIO()
        with (mock.patch.dict(os.environ, self.sandbox_env(), clear=True),
              contextlib.redirect_stderr(stderr)):
            result = preflight.run_preflight(lambda _prompt: False, [], stacks=())
        return result, stderr.getvalue()

    def test_an_accepted_interpreter_is_returned_after_the_capabilities(self):
        python3 = write_interpreter_fixture(self.bin_dir, uv_found=None)
        result, err = self._preflight()
        self.assertEqual(len(result), 4,
                         f"§S2: (exit_code, deps, capabilities, python); got {result!r}")
        code, deps, capabilities, python = result
        self.assertEqual(code, 0, err)
        self.assertEqual(sorted(deps), ["crucible", "sandesh", "uv"],
                         "[deps] stays exactly uv/sandesh/crucible")
        self.assertEqual(capabilities.get("python3"), "detected", capabilities)
        self.assertEqual(python, str(python3))

    def test_a_refusal_returns_no_interpreter(self):
        write_interpreter_fixture(self.bin_dir, version="3.12.3", uv_found=None)
        result, err = self._preflight()
        self.assertEqual(len(result), 4,
                         f"§S2: (exit_code, deps, capabilities, python); got {result!r}")
        self.assertEqual((result[0], result[3]), (1, None), err)
        self.assertEqual(len(_matching_lines(err, _refusal_line("outdated"))), 1, err)


# ---------------------------------------------------------------------------
# §S2 — install.toml's record, and init reading only the verdict
# ---------------------------------------------------------------------------

class InstallTomlInterpreterRecordTest(unittest.TestCase):
    """§S2 AC: ``[install] python = "<absolute path>"`` round-trips through
    ``serialize_install_toml`` / ``load_install_toml``."""

    def test_install_python_round_trips_through_the_serializer_and_the_loader(self):
        from modelb_axi.config import load_install_toml, serialize_install_toml
        root = Path(tempfile.mkdtemp(prefix="modelb-cr064-toml-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        install = {"version": "1.0.0", "harnesses": ["pi"], "stacks": ["python"],
                   "python": "/home/someone/.local/share/uv/python/cpython-3.14.0/bin/python3.14"}
        (root / "install.toml").write_text(
            serialize_install_toml(install, {"uv": "detected"}, [], {"python3": "detected"}),
            encoding="utf-8")
        loaded = load_install_toml(root)
        self.assertEqual(loaded["install"]["python"], install["python"])
        self.assertEqual(loaded["install"], install)
        self.assertIn(loaded["capabilities"]["python3"], FOUR_VERDICTS)


class InitReadsTheInterpreterVerdictTest(_InterpreterSandboxCase):
    """§S2 AC: ``init``'s capability contract renders ``python3`` with no ``unknown`` — from a
    real installer run on the fixture, and from each recorded non-present verdict."""

    _CONTRACT_LINE = re.compile(r"^- `python3` \(([^)]*)\): (present|absent|unknown)\b")

    def _init(self, label: str) -> tuple[dict, list[tuple]]:
        target = self.root / f"proj-{label}"
        result = run_module(
            "--yes", "init", "--name", "Interp", "--token", "interp", "--acronym", "INT",
            "--mode", "solo", "--repo-shape", "standalone", "--stacks", "python",
            "--owner", "tester", "--target", str(target), "--no-commit",
            "--modelb-home", str(self.modelb_home),
            env_overrides={"HOME": str(self.home), "MODELB_HOME": str(self.modelb_home),
                           "XDG_DATA_HOME": str(self.xdg), AGENT_DIR_ENV: str(self.agent_dir)},
            timeout=180,
        )
        axi = decode_axi(result.stdout)
        self.assertEqual((result.returncode, axi.get("ok")), (0, True), result.stderr)
        lines = [m.groups() for m in (self._CONTRACT_LINE.match(line) for line in
                 (target / "AGENTS.md").read_text(encoding="utf-8").splitlines()) if m]
        return axi.get("tools", {}), lines

    def test_a_fresh_install_renders_python3_present(self):
        write_interpreter_fixture(self.bin_dir, uv_found=None)
        result = self.run_installer(stacks="python")
        self.assertEqual(decode_axi(result.stdout).get("outcome"), "installed", result.stderr)
        self.assertIn(self.install_toml()["capabilities"].get("python3"), FOUR_VERDICTS)
        tools, lines = self._init("fresh")
        self.assertEqual(tools.get("python3"), "present", tools)
        self.assertEqual(len(lines), 1, f"one `python3` contract line; got {lines!r}")
        self.assertEqual(lines[0][1], "present", lines)

    def test_an_outdated_or_absent_verdict_renders_absent_never_unknown(self):
        write_interpreter_fixture(self.bin_dir, uv_found=None)
        result = self.run_installer(stacks="python")
        self.assertEqual(decode_axi(result.stdout).get("outcome"), "installed", result.stderr)
        path = self.modelb_home / "install.toml"
        recorded = path.read_text(encoding="utf-8")
        self.assertRegex(recorded, r'(?m)^"?python3"? = "detected"$')
        for verdict in ("outdated", "absent"):
            with self.subTest(verdict=verdict):
                path.write_text(re.sub(r'(?m)^("?python3"?) = "detected"$',
                                       rf'\1 = "{verdict}"', recorded), encoding="utf-8")
                tools, lines = self._init(verdict)
                self.assertEqual(tools.get("python3"), "absent", tools)
                self.assertEqual([state for _label, state in lines], ["absent"], lines)


if __name__ == "__main__":
    unittest.main()
