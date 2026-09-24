"""The Sandesh install reports and re-probes (CR-MDB-037 §S5 + the
Migration AC for the Sandesh install path).

``uv tool install sandesh-relay``, run on confirmation, sends its output to
the user's terminal (CR-MDB-036's ``run_on_terminal``) rather than
discarding it, and a confirmed install is re-probed before ``installed`` is
recorded; otherwise ``absent`` with a warning.

Orchestrator rulings (2026-09-24, CR-MDB-037 C2 RED):

5. The terminal test mirrors CR-MDB-036's
   ``ChildInstallerOutputOnTerminalTest``: a real subprocess whose stdin
   AND stderr are one pseudo-terminal, stdout a pipe carrying the envelope;
   an interactive run (``--stacks bun`` with bun/node shimmed, so the only
   prompts are "Proceed" and the Sandesh confirm) with ``sandesh`` absent
   and a ``uv`` shim reporting whether its stdout is the terminal.
6. Re-probe, ``--yes`` runs: ``uv`` exits 0 AND places ``sandesh`` on PATH
   → ``installed`` in the envelope ``deps``, ``install.toml`` ``[deps]`` and
   ``[capabilities]``, with no Sandesh warning; ``uv`` exits 0 WITHOUT
   placing it → ``absent`` in all three plus a warning containing
   ``uv tool install sandesh-relay`` and ``absent``.

Isolation (NON-NEGOTIABLE): every run pins ``HOME`` (sandbox, no Crucible
manifest), ``PATH`` (a fake-bin dir of shims — never a real ``uv``),
``MODELB_HOME`` and ``PI_CODING_AGENT_DIR`` (a provisioned sandbox agent
dir). Nothing is ever really installed.

Stdlib only.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from tests.pi_capability_sandbox import (
    AGENT_DIR_ENV,
    make_home,
    make_provisioned_agent_dir,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SANDESH_INSTALL = "uv tool install sandesh-relay"
_FAKE_TOOL = "#!/bin/sh\necho fake\nexit 0\n"


def _write_exe(bin_dir: Path, name: str, body: str) -> Path:
    path = Path(bin_dir) / name
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


def _decode(stdout: str) -> dict:
    from modelb_axi.toon import decode
    try:
        return decode(stdout).get("axi", {})
    except Exception:  # noqa: BLE001 — a non-envelope stdout fails the caller's asserts
        return {}


def _chmod_path() -> str:
    """The real ``chmod``, resolved on the TEST's PATH so the ``uv`` shim can
    call it under the sandbox's one-directory PATH."""
    found = shutil.which("chmod")
    if found is None:
        raise unittest.SkipTest("chmod not available to build the uv shim")
    return found


def _uv_shim(marker: Path, bin_dir: Path, *, places_sandesh: bool) -> str:
    """A fake ``uv``: ``tool install`` records its argv in ``marker``,
    reports whether its stdout is the terminal, writes one stderr line and
    — when ``places_sandesh`` — puts an executable ``sandesh`` on the
    sandbox PATH, then exits 0. Anything else exits 0 quietly."""
    place = (
        f"    printf '#!/bin/sh\\necho sandesh-fake\\nexit 0\\n' > \"{bin_dir}/sandesh\"\n"
        f"    \"{_chmod_path()}\" 755 \"{bin_dir}/sandesh\"\n"
    ) if places_sandesh else ""
    return (
        "#!/bin/sh\n"
        'if [ "$1" = "tool" ] && [ "$2" = "install" ]; then\n'
        f"    printf 'uv %s\\n' \"$*\" >> \"{marker}\"\n"
        '    if [ -t 1 ]; then echo "CHILD-STDOUT-ON-TERMINAL uv"; '
        'else echo "CHILD-STDOUT-CAPTURED uv"; fi\n'
        '    echo "CHILD-STDERR uv" >&2\n'
        f"{place}"
        "    exit 0\n"
        "fi\n"
        'echo "uv 0.0.0-fake"\n'
        "exit 0\n"
    )


class _SandeshSandboxCase(unittest.TestCase):
    """Sandbox with NO ``sandesh`` on PATH; ``bun``/``node`` shimmed so the
    selected stack raises no toolchain offer."""

    places_sandesh = True

    def setUp(self):
        self._root = Path(tempfile.mkdtemp(prefix="modelb-cr037-sandesh-"))
        self.modelb_home = self._root / "modelb-home"
        self.target_root = self._root / "target"
        self.bin_dir = self._root / "bin"
        self.home = self._root / "home"
        self.agent_dir = self._root / "agent"
        self.marker = self._root / "uv-runs"
        for d in (self.modelb_home, self.target_root, self.bin_dir):
            d.mkdir(parents=True)
        make_home(self.home, crucible_manifest=False)
        make_provisioned_agent_dir(self.agent_dir)
        for name in ("bun", "node"):
            _write_exe(self.bin_dir, name, _FAKE_TOOL)
        _write_exe(self.bin_dir, "uv",
                   _uv_shim(self.marker, self.bin_dir, places_sandesh=self.places_sandesh))
        self.assertIsNone(
            shutil.which("sandesh", path=str(self.bin_dir)),
            "fixture: sandesh must start absent",
        )

    def tearDown(self):
        shutil.rmtree(self._root, ignore_errors=True)

    def _env(self) -> dict:
        env = dict(os.environ)
        env.pop("MODELB_TARGET_ROOT", None)
        existing_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + existing_pp if existing_pp else "")
        env.update({
            "HOME": str(self.home),
            "PATH": str(self.bin_dir),
            "MODELB_HOME": str(self.modelb_home),
            AGENT_DIR_ENV: str(self.agent_dir),
        })
        return env

    def _args(self) -> list[str]:
        return ["--harnesses", "pi", "--modelb-home", str(self.modelb_home),
                "--target-root", str(self.target_root), "--stacks", "bun"]

    def uv_runs(self) -> list[str]:
        if not self.marker.exists():
            return []
        return [ln for ln in self.marker.read_text(encoding="utf-8").splitlines() if ln.strip()]

    def install_toml(self) -> dict:
        path = self.modelb_home / "install.toml"
        if not path.is_file():
            self.fail(f"install.toml not written under {self.modelb_home}")
        with open(path, "rb") as fh:
            return tomllib.load(fh)

    def run_yes(self):
        result = subprocess.run(
            [sys.executable, "-m", "modelb_axi", "--yes", *self._args()],
            capture_output=True, text=True, timeout=60,
            stdin=subprocess.DEVNULL, env=self._env(),
        )
        self.assertEqual(
            self.uv_runs(), [f"uv {SANDESH_INSTALL[3:]}"],
            f"precondition: exactly one `{SANDESH_INSTALL}`; stderr={result.stderr!r}",
        )
        return result, _decode(result.stdout)


class SandeshInstallOutputOnTerminalTest(_SandeshSandboxCase):
    """§S5 AC1: a confirmed Sandesh install's output reaches the terminal
    and not the stdout envelope."""

    def _run_on_terminal(self, answers: str = "y\ny\n" + "n\n" * 4):
        import pty
        import threading
        master, slave = pty.openpty()
        proc = subprocess.Popen(
            [sys.executable, "-m", "modelb_axi", *self._args()],
            stdin=slave, stdout=subprocess.PIPE, stderr=slave,
            env=self._env(), close_fds=True,
        )
        os.close(slave)
        os.write(master, answers.encode())
        chunks: list[bytes] = []

        def pump():
            while True:
                try:
                    data = os.read(master, 4096)
                except OSError:
                    return
                if not data:
                    return
                chunks.append(data)

        reader = threading.Thread(target=pump, daemon=True)
        reader.start()
        try:
            stdout, _ = proc.communicate(timeout=60)
        finally:
            reader.join(timeout=10)
            os.close(master)
        return proc.returncode, stdout.decode(), b"".join(chunks).decode(errors="replace")

    def test_confirmed_sandesh_install_writes_to_the_users_terminal_not_a_capture(self):
        code, stdout, terminal = self._run_on_terminal()
        self.assertIn("Sandesh not found", terminal,
                      f"precondition: the Sandesh confirm was offered; terminal={terminal!r}")
        self.assertEqual(self.uv_runs(), [f"uv {SANDESH_INSTALL[3:]}"],
                         f"precondition: the install was confirmed; terminal={terminal!r}")
        self.assertIn(
            "CHILD-STDOUT-ON-TERMINAL uv", terminal,
            f"§S5: uv's stdout must reach the user's terminal, not a capture; "
            f"terminal={terminal!r}",
        )
        self.assertIn("CHILD-STDERR uv", terminal,
                      f"§S5: uv's errors must be visible; terminal={terminal!r}")
        self.assertNotIn("CHILD-", stdout, "stdout carries only the envelope")
        axi = _decode(stdout)
        self.assertEqual(axi.get("outcome"), "installed", f"stdout={stdout!r} terminal={terminal!r}")
        self.assertEqual(code, 0, f"stdout={stdout!r} terminal={terminal!r}")


class SandeshInstallReprobeFindsSandeshTest(_SandeshSandboxCase):
    """§S5 AC2 (positive): exit 0 with ``sandesh`` then on PATH records
    ``installed`` everywhere, with no Sandesh warning."""

    places_sandesh = True

    def test_install_exiting_zero_with_sandesh_on_path_records_installed(self):
        result, axi = self.run_yes()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(axi.get("outcome"), "installed", f"axi={axi!r}")
        data = self.install_toml()
        self.assertEqual(axi.get("deps", {}).get("sandesh"), "installed", f"axi={axi!r}")
        self.assertEqual(data["deps"].get("sandesh"), "installed", f"[deps]={data['deps']!r}")
        self.assertEqual(data.get("capabilities", {}).get("sandesh"), "installed",
                         f"[capabilities]={data.get('capabilities')!r}")
        sandesh_warnings = [w for w in axi.get("warnings", []) if "sandesh" in w.lower()]
        self.assertEqual(sandesh_warnings, [], "no Sandesh warning when re-probe finds it")


class SandeshInstallReprobeMissesSandeshTest(_SandeshSandboxCase):
    """§S5 AC2 (negative): exit 0 WITHOUT ``sandesh`` on PATH records
    ``absent`` everywhere, with one warning naming the install."""

    places_sandesh = False

    def test_install_exiting_zero_without_sandesh_records_absent_with_warning(self):
        result, axi = self.run_yes()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(axi.get("outcome"), "installed", f"axi={axi!r}")
        data = self.install_toml()
        self.assertEqual(axi.get("deps", {}).get("sandesh"), "absent",
                         f"§S5: not re-found → absent; axi={axi!r}")
        self.assertEqual(data["deps"].get("sandesh"), "absent", f"[deps]={data['deps']!r}")
        self.assertEqual(data.get("capabilities", {}).get("sandesh"), "absent",
                         f"[capabilities]={data.get('capabilities')!r}")
        hits = [w for w in axi.get("warnings", [])
                if SANDESH_INSTALL in w and "absent" in w]
        self.assertEqual(len(hits), 1,
                         f"exactly one warning naming the install; warnings={axi.get('warnings')!r}")
        self.assertNotIn("sandesh=installed", result.stderr,
                         "no `installed` deps line for a Sandesh the re-probe did not find")


class SandeshDeclineRecordsWarningTest(_SandeshSandboxCase):
    """VERIFY finding 4: declining the Sandesh install at the prompt records
    a warning naming ``uv tool install sandesh-relay``, as a declined
    ``pi install`` or toolchain offer does — and runs nothing. In-process
    ``run_preflight`` with the confirm seam answering no, ``HOME``/``PATH``/
    ``PI_CODING_AGENT_DIR`` pinned to the sandbox."""

    def test_declined_sandesh_install_is_recorded_as_a_warning(self):
        import contextlib
        import io
        from unittest import mock

        from modelb_axi.preflight import run_preflight
        prompts: list[str] = []

        def decline(prompt: str) -> bool:
            prompts.append(prompt)
            return False

        warnings: list[str] = []
        env = {"HOME": str(self.home), "PATH": str(self.bin_dir),
               AGENT_DIR_ENV: str(self.agent_dir)}
        with mock.patch.dict(os.environ, env), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            code, deps, _caps = run_preflight(decline, warnings, stacks=())
        self.assertEqual(code, 0, err.getvalue())
        self.assertTrue(any("Sandesh not found" in p for p in prompts),
                        f"precondition: the Sandesh install was offered; prompts={prompts!r}")
        self.assertEqual(self.uv_runs(), [], "a declined install runs nothing")
        self.assertEqual(deps.get("sandesh"), "absent", f"deps={deps!r}")
        hits = [w for w in warnings if "declined" in w and SANDESH_INSTALL in w]
        self.assertEqual(len(hits), 1,
                         f"one warning naming the declined install; warnings={warnings!r}")


if __name__ == "__main__":
    unittest.main()
