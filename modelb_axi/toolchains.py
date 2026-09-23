"""Per-stack toolchain probes and provider-installer offers — the tier-3
``toolchain`` requirement (CR-MDB-036 §S8).

- **Only selected stacks are probed**, each tool at most once per run
  (quarkus and java share ``mvn``/``java``; python's ``python3`` shares the
  tier-2 PATH probe) through a caller-owned resolution cache.
- **Resolution, never execution**: a binary is judged by
  ``shutil.which``. The one exception is python's ``xmlrunner`` and
  ``coverage``, imported by the PATH ``python3`` (``python3 -c "import …"``)
  — the installer's own interpreter is not the one the Crucible client uses.
- An absent toolchain WARNs, naming the provider's installer, and the
  install continues. The installer is **offered** only through ``offer``
  (the CLI's explicit-yes seam, ``None`` under ``--yes``); one that needs
  elevated privileges has no ``install`` argv and is never offered.
  Declining is recorded as a warning.

Verdicts: ``detected`` / ``absent`` / ``unknown``, and ``installed`` after a
provider installer the user confirmed exits 0. Stdlib only.
"""

import shutil
import subprocess
import sys
from collections.abc import Callable, Iterable

from modelb_axi.capabilities import ABSENT, DETECTED, UNKNOWN
from modelb_axi.requirements import STACK_TOOLCHAINS, install_display

INSTALLED = "installed"

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


def _run_installer(argv: list[str], command: str, warn: Callable[[str], None]) -> str:
    """Run one confirmed provider installer on the user's terminal
    (:func:`run_on_terminal`)."""
    try:
        returncode = run_on_terminal(argv)
    except OSError as exc:
        warn(f"`{command}` could not run ({exc}); recording absent")
        return ABSENT
    if returncode != 0:
        warn(f"`{command}` failed (exit={returncode}); recording absent")
        return ABSENT
    return INSTALLED


def remediate_toolchains(
    verdicts: dict[str, dict[str, str]],
    resolved: dict[str, str | None],
    warn: Callable[[str], None],
    offer: Callable[[str], bool] | None,
) -> None:
    """WARN for every tool not ``detected``, naming its provider's
    installer; offer a non-elevated installer whose runner resolves, at
    most once per installer. ``verdicts`` is updated in place
    (``installed`` after a confirmed installer exits 0)."""
    outcomes: dict[tuple[str, ...], str] = {}
    for stack, row in verdicts.items():
        for probe in STACK_TOOLCHAINS[stack]:
            name = probe["name"]
            if row[name] == DETECTED:
                continue
            command = probe["remediation"]
            install = probe["install"]
            if install in outcomes:
                row[name] = outcomes[install]
                continue
            # The remediation is prose with any command set apart in
            # backticks by the data (``requirements._probe``).
            warn(
                f"stack {stack}: {name}={row[name]} — {stack} tests cannot run on "
                f"this machine; {command}"
            )
            if install is None or offer is None:
                continue
            runner = resolve(install[0], resolved)
            if runner is None:
                continue
            display = install_display(install)
            if offer(f"Run `{display}` to install {name} for stack {stack}?"):
                row[name] = _run_installer([runner, *install[1:]], display, warn)
            else:
                warn(f"declined `{display}` — {name} stays {row[name]} for stack {stack}")
            outcomes[install] = row[name]
