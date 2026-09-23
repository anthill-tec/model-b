"""Dependency pre-flight — installer-flow stage 1 (CR-MDB-014 §S4, AC4).

Checks the three ecosystem dependencies in order against the CURRENT
``PATH`` (``shutil.which`` — the tests' isolation seam):

1. ``uv`` — the bootstrap dependency everything else rides on. Absent is
   the pre-flight FAILURE mode: non-zero exit with bootstrap
   instructions, before any other stage output.
2. ``sandesh`` — absent triggers a proactive install THROUGH the
   provider's own method (``uv tool install sandesh-relay``, via the
   PATH-resolved ``uv``) on confirm; ``--yes`` supplies the implicit
   confirm (DN-scaffold-packaging §4 "on confirm").
3. ``crucible`` — Crucible ships its own installer (DN-scaffold-packaging §4 / decision D):
   absent means WARN pointing at Crucible's own installer and record
   ``absent`` — never hand-deploy their assets.

Emits the machine-greppable ``deps: uv=... sandesh=... crucible=...``
line on STDERR — the human channel; stdout is reserved for the
installer's one AXI envelope (CR-MDB-033 §S6) — and returns the final
verdicts for ``[deps]`` persistence into ``install.toml`` (§S6). Every
warning printed is also appended, unprefixed, to the caller's
``warnings`` list so the envelope can carry it. This module itself
writes nothing to disk.

Stdlib only.
"""

import shutil
import subprocess
import sys
from collections.abc import Callable

SANDESH_PACKAGE = "sandesh-relay"

_UV_BOOTSTRAP_MESSAGE = (
    "pre-flight failed — `uv` not found on PATH.\n"
    "  uv is the bootstrap dependency; install uv first, e.g.:\n"
    "    curl -LsSf https://astral.sh/uv/install.sh | sh\n"
    "  then re-run modelb-axi."
)

_CRUCIBLE_ABSENT_WARNING = (
    "Crucible not found on PATH — install it with Crucible's own "
    "installer; modelb-axi never deploys Crucible assets."
)


def _warn(message: str, warnings: list[str]) -> None:
    """Print one warning on the human channel (stderr) and record it,
    unprefixed, for the installer envelope (CR-MDB-033 §S6)."""
    print(f"modelb-axi: warning: {message}", file=sys.stderr)
    warnings.append(message)


def _install_sandesh(uv_path: str, warnings: list[str]) -> str:
    """Install Sandesh via the provider's own method (`uv tool install
    sandesh-relay`) through the PATH-resolved ``uv``. Returns the deps
    verdict: ``installed`` on success, ``absent`` on failure."""
    result = subprocess.run(
        [uv_path, "tool", "install", SANDESH_PACKAGE],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        _warn(
            f"`uv tool install {SANDESH_PACKAGE}` failed "
            f"(exit={result.returncode}); recording sandesh=absent",
            warnings,
        )
        return "absent"
    return "installed"


def run_preflight(
    confirm: Callable[[str], bool], warnings: list[str] | None = None,
) -> tuple[int, dict[str, str]]:
    """Run the §S4 dependency pre-flight (installer-flow stage 1).

    ``confirm`` is the CLI's prompt seam, pre-bound to the run's
    interactivity (always-True under ``--yes``). ``warnings``, when
    given, collects the text of every warning and error printed
    (CR-MDB-033 §S6). Returns ``(exit_code, verdicts)``: exit 0 on
    success (with the final per-dep verdicts for ``[deps]``
    persistence), non-zero when ``uv`` is absent.
    """
    if warnings is None:
        warnings = []
    uv_path = shutil.which("uv")
    if uv_path is None:
        print(f"modelb-axi: {_UV_BOOTSTRAP_MESSAGE}", file=sys.stderr)
        warnings.append(_UV_BOOTSTRAP_MESSAGE)
        return 1, {}

    sandesh_verdict = "detected" if shutil.which("sandesh") is not None else "absent"
    if shutil.which("crucible") is not None:
        crucible_verdict = "detected"
    else:
        _warn(_CRUCIBLE_ABSENT_WARNING, warnings)
        crucible_verdict = "absent"

    # Truthful DETECTION report first (AC4: "records ... detection
    # truthfully") — before any remediation mutates the picture.
    print(
        f"deps: uv=detected sandesh={sandesh_verdict} crucible={crucible_verdict}",
        file=sys.stderr,
    )

    if sandesh_verdict == "absent" and confirm(
        f"Sandesh not found — install via `uv tool install {SANDESH_PACKAGE}`?"
    ):
        sandesh_verdict = _install_sandesh(uv_path, warnings)
        if sandesh_verdict == "installed":
            # Updated deps line reflecting the proactive install.
            print(
                f"deps: uv=detected sandesh=installed crucible={crucible_verdict}",
                file=sys.stderr,
            )

    return 0, {
        "uv": "detected",
        "sandesh": sandesh_verdict,
        "crucible": crucible_verdict,
    }
