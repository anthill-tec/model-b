"""Dependency pre-flight — installer-flow stage 1 (CR-MDB-014 §S4, AC4).

Checks the three ecosystem dependencies in order against the CURRENT
``PATH`` (``shutil.which`` — the tests' isolation seam):

1. ``uv`` — the bootstrap dependency everything else rides on. Absent is
   the pre-flight FAILURE mode: non-zero exit with bootstrap
   instructions, before any other stage output.
2. ``sandesh`` — absent triggers a proactive install THROUGH the
   provider's own method (``uv tool install sandesh-relay``, via the
   PATH-resolved ``uv``) on confirm; ``--yes`` supplies the implicit
   confirm (DN §4 "on confirm").
3. ``crucible`` — Crucible ships its own installer (DN §4 / decision D):
   absent means WARN pointing at Crucible's own installer and record
   ``absent`` — never hand-deploy their assets.

Emits the machine-greppable ``deps: uv=... sandesh=... crucible=...``
line on stdout. ``[deps]`` persistence into ``install.toml`` lands with
§S6 in C3 — this module writes nothing to disk.

Stdlib only.
"""

import shutil
import subprocess
import sys
from collections.abc import Callable

SANDESH_PACKAGE = "sandesh-relay"

_UV_BOOTSTRAP_MESSAGE = (
    "modelb-axi: pre-flight failed — `uv` not found on PATH.\n"
    "  uv is the bootstrap dependency; install uv first, e.g.:\n"
    "    curl -LsSf https://astral.sh/uv/install.sh | sh\n"
    "  then re-run modelb-axi."
)

_CRUCIBLE_ABSENT_WARNING = (
    "modelb-axi: warning: Crucible not found on PATH — install it with "
    "Crucible's own installer; modelb-axi never deploys Crucible assets."
)


def _install_sandesh(uv_path: str) -> str:
    """Install Sandesh via the provider's own method (`uv tool install
    sandesh-relay`) through the PATH-resolved ``uv``. Returns the deps
    verdict: ``installed`` on success, ``absent`` on failure."""
    result = subprocess.run(
        [uv_path, "tool", "install", SANDESH_PACKAGE],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        print(
            f"modelb-axi: warning: `uv tool install {SANDESH_PACKAGE}` "
            f"failed (exit={result.returncode}); recording sandesh=absent",
            file=sys.stderr,
        )
        return "absent"
    return "installed"


def run_preflight(confirm: Callable[[str], bool]) -> int:
    """Run the §S4 dependency pre-flight (installer-flow stage 1).

    ``confirm`` is the CLI's prompt seam, pre-bound to the run's
    interactivity (always-True under ``--yes``). Returns the process
    exit code: 0 on success, non-zero when ``uv`` is absent.
    """
    uv_path = shutil.which("uv")
    if uv_path is None:
        print(_UV_BOOTSTRAP_MESSAGE, file=sys.stderr)
        return 1

    sandesh_verdict = "detected" if shutil.which("sandesh") is not None else "absent"
    if shutil.which("crucible") is not None:
        crucible_verdict = "detected"
    else:
        print(_CRUCIBLE_ABSENT_WARNING, file=sys.stderr)
        crucible_verdict = "absent"

    # Truthful DETECTION report first (AC4: "records ... detection
    # truthfully") — before any remediation mutates the picture.
    print(f"deps: uv=detected sandesh={sandesh_verdict} crucible={crucible_verdict}")

    if sandesh_verdict == "absent" and confirm(
        f"Sandesh not found — install via `uv tool install {SANDESH_PACKAGE}`?"
    ):
        sandesh_verdict = _install_sandesh(uv_path)
        if sandesh_verdict == "installed":
            # Updated deps line reflecting the proactive install.
            print(f"deps: uv=detected sandesh=installed crucible={crucible_verdict}")

    return 0
