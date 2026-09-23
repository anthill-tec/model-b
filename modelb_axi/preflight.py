"""Dependency and capability pre-flight — installer-flow stage 1
(CR-MDB-014 §S4; CR-MDB-036 §S1–§S3).

Probes, in order, against the CURRENT environment (``shutil.which`` and
``$HOME``/``$PI_CODING_AGENT_DIR`` — the tests' isolation seams):

1. **Harness capabilities** (tier 1, :mod:`modelb_axi.capabilities`) —
   reported as ``harness: dispatch=<v> lean-ctx=<v> permissions=<v>``.
2. ``uv`` — the bootstrap dependency everything else rides on. Absent is
   the pre-flight FAILURE mode: non-zero exit with bootstrap
   instructions.
3. ``sandesh`` and ``crucible`` — reported with ``uv`` as
   ``deps: uv=<v> sandesh=<v> crucible=<v>``. Crucible is judged by its
   released-client manifest ``~/.crucible/crucible-clients.json``, never
   a binary and never its server; absent means WARN pointing at
   Crucible's own installer — never hand-deploy their assets.
4. One ``stack <name>: <probe>=<v> … client=<v>`` line per selected
   stack — its §S8 toolchain (:mod:`modelb_axi.toolchains`) and its
   Crucible client; unselected stacks cost no probe.

Every group line is printed on STDERR (the human channel; stdout is the
installer's one AXI envelope, CR-MDB-033 §S6) BEFORE any policy decision
or remediation. Then policy (§S3): a missing REQUIRED capability fails the
pre-flight naming the asset families it leaves inert, unless the caller
allows missing capabilities; ``unknown`` and a missing RECOMMENDED one
WARN and continue. Model B never installs a third-party extension and
never edits Pi's ``settings.json`` — it names ``pi install npm:<pkg>``.
Sandesh (Model B's own ecosystem) keeps its install-on-confirm.

Every warning printed is also appended, unprefixed, to the caller's
``warnings`` list so the envelope can carry it. This module writes
nothing to disk. Stdlib only.
"""

import shutil
import subprocess
import sys
from collections.abc import Callable, Iterable
from pathlib import Path

from modelb_axi.capabilities import (
    ABSENT,
    DETECTED,
    UNKNOWN,
    load_crucible_clients,
    probe_crucible_client,
    probe_harness,
    resolve_agent_dir,
)
from modelb_axi.requirements import REQUIREMENTS, STACK_CLIENT_KEYS, requirement
from modelb_axi.toolchains import (
    INSTALLED,
    probe_toolchains,
    remediate_toolchains,
    resolve,
    run_on_terminal,
)

SANDESH_PACKAGE = "sandesh-relay"

#: The requirement ``probe`` kind of a tier-2 tool judged by
#: ``shutil.which`` and recorded only in ``[capabilities]`` — ``[deps]``
#: stays exactly uv/sandesh/crucible. Which tools carry it is DATA
#: (:data:`modelb_axi.requirements.REQUIREMENTS`), read at call time.
_PATH_PROBE = "path"

_UV_BOOTSTRAP_MESSAGE = (
    "pre-flight failed — `uv` not found on PATH.\n"
    "  uv is the bootstrap dependency; install uv first, e.g.:\n"
    "    curl -LsSf https://astral.sh/uv/install.sh | sh\n"
    "  then re-run modelb-axi."
)

_CRUCIBLE_ABSENT_WARNING = (
    "Crucible's released clients not found (no ~/.crucible/crucible-clients.json) "
    "— install them with Crucible's own installer; modelb-axi never deploys "
    "Crucible assets."
)

_CRUCIBLE_UNKNOWN_WARNING = (
    "crucible=unknown — ~/.crucible/crucible-clients.json does not parse; "
    "the crucible-report-* skill bundles may not find their clients. "
    "Reinstall with Crucible's own installer."
)


def _warn(message: str, warnings: list[str], level: str = "warning") -> None:
    """Print one warning on the human channel (stderr) and record it,
    unprefixed, for the installer envelope (CR-MDB-033 §S6)."""
    print(f"modelb-axi: {level}: {message}", file=sys.stderr)
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


def _client_gap(stack: str, clients: dict) -> str:
    """Why a stack's Crucible client is not ``detected`` under a detected
    manifest — the manifest has NO entry for its key, or the entry names
    a file that does not exist — and the remediation."""
    key = STACK_CLIENT_KEYS[stack]
    target = clients.get(key)
    if isinstance(target, str) and target:
        why = (f"Crucible's manifest entry for key {key} names {target}, "
               f"which does not exist")
    else:
        why = f"Crucible's manifest has no entry for key {key}"
    return f"{why}; {requirement('crucible-client')['remediation']}"


def _families(row: dict) -> str:
    return ", ".join(row["asset_families"])


def _offer_pi_installs(
    harness: dict[str, str], offer: Callable[[str], bool] | None, warnings: list[str],
    agent_dir: Path,
) -> None:
    """§S3: for each ABSENT tier-1 extension, offer Pi's own
    ``pi install npm:<package>`` — run only on an explicit interactive yes
    (``offer`` is ``None`` under ``--yes``). Model B never edits Pi's
    ``settings.json``; Pi does. A decline is recorded as a warning.

    After an install exits 0 that ONE capability is re-probed: its verdict
    in ``harness`` (updated in place) becomes ``installed`` iff Pi now
    loads it, else keeps the re-probed verdict with a warning naming where
    it was expected."""
    missing = [cap for cap, verdict in harness.items() if verdict == ABSENT]
    if offer is None or not missing:
        return
    pi_path = shutil.which("pi")
    if pi_path is None:
        return
    for cap in missing:
        package = requirement(cap)["provider"]
        spec = f"npm:{package}"
        command = f"pi install {spec}"
        if not offer(f"{cap}=absent — run Pi's own `{command}`?"):
            _warn(f"declined `{command}` — {cap} stays absent", warnings)
            continue
        try:
            returncode = run_on_terminal([pi_path, "install", spec])
        except OSError as exc:
            _warn(f"`{command}` could not run ({exc})", warnings)
            continue
        if returncode != 0:
            _warn(f"`{command}` failed (exit={returncode})", warnings)
            continue
        verdict = probe_harness({cap: package}, agent_dir)[cap]
        if verdict == DETECTED:
            harness[cap] = INSTALLED
            continue
        harness[cap] = verdict
        _warn(
            f"`{command}` exited 0 but {cap} is still {verdict} — expected "
            f"{agent_dir / 'settings.json'} packages[] to list {spec} and "
            f"{agent_dir / 'npm' / 'node_modules' / package / 'package.json'} to exist",
            warnings,
        )


def _harness_policy(
    harness: dict[str, str], settings_path: str, allow_missing: bool,
    warnings: list[str],
) -> list[str]:
    """§S3 per tier-1 capability. Returns the ids of REQUIRED capabilities
    that are absent (the pre-flight failure set; empty under the override)."""
    failed: list[str] = []
    for cap, verdict in harness.items():
        row = requirement(cap)
        if verdict in (DETECTED, INSTALLED):
            continue
        fix = f"install it with Pi's own command: `{row['remediation']}`"
        if verdict == UNKNOWN:
            _warn(
                f"{cap}=unknown — {settings_path} could not be judged; if "
                f"missing, {_families(row)} will be inert. {fix}",
                warnings,
            )
        elif row["policy"] == "required" and not allow_missing:
            _warn(
                f"{cap}=absent — required: {_families(row)} would be inert; {fix}",
                warnings, level="error",
            )
            failed.append(cap)
        elif row["policy"] == "required":
            _warn(
                f"{cap}=absent — {_families(row)} will be inert "
                f"(continuing: --allow-missing-capabilities); {fix}",
                warnings,
            )
        else:
            _warn(f"{cap}=absent — {_families(row)} is ignored; {fix}", warnings)
    return failed


def run_preflight(
    confirm: Callable[[str], bool],
    warnings: list[str] | None = None,
    *,
    stacks: Iterable[str] = (),
    allow_missing_capabilities: bool = False,
    offer: Callable[[str], bool] | None = None,
) -> tuple[int, dict[str, str], dict[str, str]]:
    """Run the dependency and capability pre-flight (installer stage 1).

    ``confirm`` is the CLI's prompt seam, pre-bound to the run's
    interactivity (always-True under ``--yes``) — used only for Model B's
    own Sandesh install, never for a third-party extension. ``offer`` is the
    explicit-yes seam (``None`` under ``--yes``) for Pi's own ``pi install``
    and the §S8 provider installers. ``warnings``,
    when given, collects every warning and error printed. ``stacks`` are
    the selected stacks, one ``stack <name>:`` line each.

    Returns ``(exit_code, deps, capabilities)``: ``deps`` is exactly
    uv/sandesh/crucible for ``[deps]``; ``capabilities`` maps every probed
    requirement id to its verdict for ``[capabilities]`` (§S4). Non-zero
    when ``uv`` is absent, or a required capability is absent without
    ``allow_missing_capabilities``.
    """
    if warnings is None:
        warnings = []
    stacks = list(stacks)
    tier1 = {row["id"]: row["provider"] for row in REQUIREMENTS if row["tier"] == 1}
    agent_dir = resolve_agent_dir()
    harness = probe_harness(tier1, agent_dir)
    print(
        "harness: " + " ".join(f"{cap}={v}" for cap, v in harness.items()),
        file=sys.stderr,
    )

    uv_path = shutil.which("uv")
    if uv_path is None:
        print(f"modelb-axi: {_UV_BOOTSTRAP_MESSAGE}", file=sys.stderr)
        warnings.append(_UV_BOOTSTRAP_MESSAGE)
        return 1, {}, dict(harness)

    sandesh_verdict = DETECTED if shutil.which("sandesh") is not None else ABSENT
    resolved: dict[str, str | None] = {"uv": uv_path}
    crucible_verdict, clients = load_crucible_clients()
    stack_clients = {
        stack: probe_crucible_client(stack, crucible_verdict, clients) for stack in stacks
    }
    path_rows = [row for row in REQUIREMENTS if row.get("probe") == _PATH_PROBE]
    path_tools = {
        row["id"]: DETECTED if resolve(row["id"], resolved) is not None else ABSENT
        for row in path_rows
    }
    toolchains = probe_toolchains(stacks, resolved)

    # Truthful DETECTION report first (AC4: "records ... detection
    # truthfully") — every group line before any policy or remediation.
    print(
        f"deps: uv=detected sandesh={sandesh_verdict} crucible={crucible_verdict}",
        file=sys.stderr,
    )
    for stack, client in stack_clients.items():
        probes = "".join(f"{name}={v} " for name, v in toolchains[stack].items())
        print(f"stack {stack}: {probes}client={client}", file=sys.stderr)

    _offer_pi_installs(harness, offer, warnings, agent_dir)
    failed = _harness_policy(
        harness, str(agent_dir / "settings.json"), allow_missing_capabilities, warnings,
    )
    if crucible_verdict == ABSENT:
        _warn(_CRUCIBLE_ABSENT_WARNING, warnings)
    elif crucible_verdict == UNKNOWN:
        _warn(_CRUCIBLE_UNKNOWN_WARNING, warnings)
    for row in path_rows:
        if path_tools[row["id"]] == ABSENT:
            _warn(
                f"{row['id']} not found on PATH — {_families(row)} will not run; "
                f"{row['remediation']}",
                warnings,
            )

    capabilities = {**harness, "uv": DETECTED, "sandesh": sandesh_verdict,
                    "crucible": crucible_verdict, **path_tools}
    if failed:
        message = (
            f"pre-flight failed — required capabilities missing: {', '.join(failed)}; "
            f"install them, or re-run with --allow-missing-capabilities"
        )
        print(f"modelb-axi: {message}", file=sys.stderr)
        warnings.append(message)
        return 1, {}, capabilities

    if sandesh_verdict == ABSENT and confirm(
        f"Sandesh not found — install via `uv tool install {SANDESH_PACKAGE}`?"
    ):
        sandesh_verdict = _install_sandesh(uv_path, warnings)
        if sandesh_verdict == "installed":
            # Updated deps line reflecting the proactive install.
            print(
                f"deps: uv=detected sandesh=installed crucible={crucible_verdict}",
                file=sys.stderr,
            )
    capabilities["sandesh"] = sandesh_verdict

    remediate_toolchains(
        toolchains, resolved, lambda message: _warn(message, warnings), offer,
    )
    for stack, client in stack_clients.items():
        if client != DETECTED and crucible_verdict == DETECTED:
            _warn(f"stack {stack}: client={client} — {_client_gap(stack, clients)}", warnings)
        for name, verdict in toolchains[stack].items():
            capabilities[f"{stack}.{name}"] = verdict
        capabilities[f"{stack}.client"] = client

    return 0, {
        "uv": DETECTED,
        "sandesh": sandesh_verdict,
        "crucible": crucible_verdict,
    }, capabilities
