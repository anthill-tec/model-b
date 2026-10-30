"""Per-stack toolchain probes and provider-installer offers — the tier-3
``toolchain`` requirement (CR-MDB-036 §S8).

- **Only selected stacks are probed**, each tool at most once per run
  (quarkus and java share ``mvn``/``java``; every stack's ``python3`` probe
  — its Crucible client runs on the PATH ``python3``, CR-MDB-063 §S1 — is
  resolved once, through the same cache as the §D22 interpreter probe)
  through a caller-owned resolution cache.
- **Resolution, never execution**: a binary is judged by
  ``shutil.which``. The one exception is python's ``xmlrunner`` and
  ``coverage``, imported by the PATH ``python3`` (``python3 -c "import …"``)
  — the installer's own interpreter is not the one the Crucible client uses.
- An absent toolchain WARNs, naming the provider's installer, and the
  install continues. The installer is **offered** only through ``offer``
  (the CLI's explicit-yes seam, ``None`` under ``--yes``), at most once per
  run per installer — ``python3``'s ``uv python install --default`` once
  for every stack it covers, its prompt naming them all, each re-probed
  after it ran. Each tool gets its own warning, save one covered and
  installed: a later covered stack whose re-probe finds the tool gets none
  (CR-MDB-066 §S6). A probe with no
  ``install`` argv is never offered. A warning's effect clause follows the
  probe's kind: a ``module`` probe (``xmlrunner``, ``coverage``) is judged
  in the PATH ``python3``, so its warning says the PATH ``python3`` cannot
  run the stack's tests. The ``no_install`` reason (CR-MDB-063 §S2)
  decides the elevated note: ``elevated`` carries :data:`_ELEVATED_NOTE`;
  ``per-project`` carries none, and records that the route runs in each
  project. Declining is recorded as one warning naming every covered stack.

Verdicts: ``detected`` / ``absent`` / ``unknown``, and ``installed`` when a
provider installer the user confirmed exits 0 AND a re-probe of that one
tool then finds it (else ``absent``, warning where it was expected).
Stdlib only.
"""

import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterable
from pathlib import Path

from modelb_axi.capabilities import ABSENT, DETECTED, UNKNOWN
from modelb_axi.requirements import ELEVATED, STACK_TOOLCHAINS, install_display

INSTALLED = "installed"

#: Appended to the warning for a tool whose installer needs elevated
#: privileges (``no_install`` is ``elevated``): the installer names it, never
#: runs it.
_ELEVATED_NOTE = " (needs elevated privileges — named, never run by modelb-axi)"

#: Upper bound on one ``python3 -c "import …"`` check.
_IMPORT_CHECK_TIMEOUT_S = 30


def resolve(tool: str, resolved: dict[str, str | None]) -> str | None:
    """``shutil.which(tool)``, at most once per ``resolved`` cache."""
    if tool not in resolved:
        resolved[tool] = shutil.which(tool)
    return resolved[tool]


def _import_verdict(python3: str | None, module: str) -> str:
    """Whether the PATH ``python3`` imports ``module``: ``absent`` when
    there is no ``python3`` or the import fails; ``unknown`` when the
    check itself cannot run."""
    if python3 is None:
        return ABSENT
    try:
        result = subprocess.run(
            [python3, "-c", f"import {module}"],
            capture_output=True, text=True, check=False,
            timeout=_IMPORT_CHECK_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired):
        return UNKNOWN
    return DETECTED if result.returncode == 0 else ABSENT


def probe_toolchains(
    stacks: Iterable[str], resolved: dict[str, str | None],
) -> dict[str, dict[str, str]]:
    """``{stack: {probe: verdict}}`` for the selected ``stacks``, in §S8
    table order. Nothing is executed but the ``python3`` import checks."""
    modules: dict[str, str] = {}
    verdicts: dict[str, dict[str, str]] = {}
    for stack in stacks:
        row: dict[str, str] = {}
        for probe in STACK_TOOLCHAINS[stack]:
            name = probe["name"]
            if probe["kind"] == "module":
                if name not in modules:
                    modules[name] = _import_verdict(resolve("python3", resolved), name)
                row[name] = modules[name]
            else:
                row[name] = DETECTED if resolve(name, resolved) is not None else ABSENT
        verdicts[stack] = row
    return verdicts


def human_channel_fd() -> int:
    """The file descriptor of the human channel: ``sys.stderr``'s, or the
    process's fd 2 when ``sys.stderr`` has been replaced by an object
    with no descriptor."""
    try:
        return sys.stderr.fileno()
    except (AttributeError, OSError, ValueError):  # io.UnsupportedOperation is an OSError
        return 2


def run_on_terminal(argv: list[str], env: dict[str, str] | None = None) -> int:
    """Run a confirmed third-party installer (a provider installer or
    Pi's ``pi install``) UNCAPTURED: stdin and stderr are inherited, and
    its stdout goes to the human channel (stderr) — so its prompts and
    errors reach the user while it runs, and stdout keeps carrying only
    the envelope. Returns the exit code; ``OSError`` when it cannot run."""
    sys.stderr.flush()
    return subprocess.run(argv, stdout=human_channel_fd(), env=env, check=False).returncode


def _installer_env(
    probe: dict, command: str, warn: Callable[[str], None],
) -> tuple[bool, dict[str, str] | None]:
    """``(ok, env)``: the environment a probe's installer runs with \u2014 the
    current one plus its ``env_dirs`` (``~`` expanded), each directory
    created if missing; ``None`` (inherit) when it declares none. When a
    directory cannot be created (unwritable, or a non-directory in its
    path) it WARNs naming that path and returns ``ok`` False: the installer
    is not run and the tool is recorded ``absent`` \u2014 never raised."""
    env_dirs = probe.get("env_dirs") or {}
    if not env_dirs:
        return True, None
    env = dict(os.environ)
    for var, raw in env_dirs.items():
        path = Path(raw).expanduser()
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            warn(
                f"cannot create {var}={path} for `{command}` "
                f"({exc}); not run \u2014 {probe['name']} recorded absent"
            )
            return False, None
        env[var] = str(path)
    return True, env


def _run_installer(
    argv: list[str], command: str, warn: Callable[[str], None],
    env: dict[str, str] | None = None,
) -> bool:
    """Run one confirmed provider installer on the user's terminal
    (:func:`run_on_terminal`); True when it exits 0."""
    try:
        returncode = run_on_terminal(argv, env)
    except OSError as exc:
        warn(f"`{command}` could not run ({exc}); recording absent")
        return False
    if returncode != 0:
        warn(f"`{command}` failed (exit={returncode}); recording absent")
        return False
    return True


def _reprobe(
    probe: dict, resolved: dict[str, str | None], command: str,
    warn: Callable[[str], None],
) -> str:
    """Probe ONE tool again after its confirmed installer exited 0 \u2014 the
    only probe beyond one per tool: ``installed`` iff it is now found, else
    ``absent`` with a warning naming where it was expected."""
    name = probe["name"]
    if probe["kind"] == "module":
        found = _import_verdict(resolve("python3", resolved), name) == DETECTED
    else:
        resolved.pop(name, None)
        found = resolve(name, resolved) is not None
    if found:
        return INSTALLED
    warn(
        f"`{command}` exited 0 but {name} is still not found \u2014 expected "
        f"{probe.get('expected') or 'on PATH'}; recording absent"
    )
    return ABSENT


def remediate_toolchains(
    verdicts: dict[str, dict[str, str]],
    resolved: dict[str, str | None],
    warn: Callable[[str], None],
    offer: Callable[[str], bool] | None,
) -> None:
    """WARN for every tool not ``detected`` — each tool its OWN warning,
    naming its provider's installer, even when another tool shares that
    installer — save one covered and installed (CR-MDB-066 §S6): offer a
    non-elevated installer whose runner resolves, at most once per
    installer, its prompt naming every stack it covers (those, in
    selection order, whose tool it installs is not ``detected``).
    ``verdicts`` is updated in place: after a confirmed installer exits 0,
    every stack it covers is re-probed (``installed`` iff now found), and
    a later covered stack whose re-probe finds the tool gets no warning of
    its own; one whose re-probe does not keeps it beside the re-probe's. A
    decline is recorded once, naming every covered stack."""
    covered = _covered_stacks(verdicts)
    offered: dict[tuple[str, ...], bool] = {}  # installer -> ran and exited 0
    for stack, row in verdicts.items():
        for probe in STACK_TOOLCHAINS[stack]:
            name = probe["name"]
            if row[name] == DETECTED:
                continue
            install = probe["install"]
            # The remediation is prose with any command set apart in
            # backticks by the data (``requirements._probe``); the
            # elevated-privilege note and the effect are installer wording,
            # never data. A module is judged in the PATH python3, which is
            # what cannot run the tests (CR-MDB-063 §S2).
            effect = (f"the PATH python3 cannot run {stack} tests" if probe["kind"] == "module"
                      else f"{stack} tests cannot run on this machine")
            own = (
                f"stack {stack}: {name}={row[name]} — {effect}; {probe['remediation']}"
                + (_ELEVATED_NOTE if probe.get("no_install") == ELEVATED else "")
            )
            if install is not None and offer is not None and offered.get(install):
                # Shared installer, already run this run and exited 0: re-probe
                # this covered stack; its own warning stands only when the
                # re-probe does not find the tool (CR-MDB-066 §S6).
                display = install_display(install)
                reprobe_warnings: list[str] = []
                row[name] = _reprobe(probe, resolved, display, reprobe_warnings.append)
                if row[name] != INSTALLED:
                    warn(own)
                for line in reprobe_warnings:
                    warn(line)
                continue
            warn(own)
            if install is None or offer is None or install in offered:
                # No installer, ``--yes``, or a shared installer already
                # offered (declined or failed): no second offer.
                continue
            display = install_display(install)
            runner = resolve(install[0], resolved)
            if runner is None:
                continue
            with_env = "".join(
                f" with {var}={raw}" for var, raw in (probe.get("env_dirs") or {}).items()
            )
            stacks = covered.get(install, [stack])
            for_stacks = f"{'stack' if len(stacks) == 1 else 'stacks'} {', '.join(stacks)}"
            if offer(f"Run `{display}`{with_env} to install {name} for {for_stacks}?"):
                # env dirs are created only once the user has said yes.
                env_ok, env = _installer_env(probe, display, warn)
                ran = env_ok and _run_installer([runner, *install[1:]], display, warn, env)
                row[name] = _reprobe(probe, resolved, display, warn) if ran else ABSENT
            else:
                ran = False
                warn(f"declined `{display}` — {name} stays {row[name]} for {for_stacks}")
            offered[install] = ran


def _covered_stacks(
    verdicts: dict[str, dict[str, str]],
) -> dict[tuple[str, ...], list[str]]:
    """``{installer argv: [stack, …]}``: the stacks each installer covers —
    those, in ``verdicts`` (selection) order, whose tool it installs is not
    ``detected`` (CR-MDB-066 §S6)."""
    covered: dict[tuple[str, ...], list[str]] = {}
    for stack, row in verdicts.items():
        for probe in STACK_TOOLCHAINS[stack]:
            install = probe["install"]
            if install is None or row[probe["name"]] == DETECTED:
                continue
            stacks = covered.setdefault(install, [])
            if stack not in stacks:
                stacks.append(stack)
    return covered
