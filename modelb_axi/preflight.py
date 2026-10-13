"""Dependency and capability pre-flight — installer-flow stage 1
(CR-MDB-014 §S4; CR-MDB-036 §S1–§S3).

Probes, in order, against the CURRENT environment (``shutil.which`` and
``$HOME``/``$PI_CODING_AGENT_DIR`` — the tests' isolation seams):

1. **Harness capabilities** (tier 1, :mod:`modelb_axi.capabilities`) —
   reported as ``harness: dispatch=<v> lean-ctx=<v> permissions=<v>
   worktree=<v> sandesh-pi=<v>``.
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
Sandesh (Model B's own ecosystem) keeps its install-on-confirm, and so
does Model B's own Pi package, ``pi install npm:@anthill-tec/modelb-pi``
(the ``worktree`` capability, CR-MDB-029 §S3), when ``pi`` is targeted.

The ``sandesh`` probe runs ``sandesh --version`` (CR-MDB-047 §S1): a CLI
below :data:`SANDESH_VERSION_FLOOR` is ``outdated`` — reported like
``absent``, naming ``uv tool upgrade sandesh-relay``, and never
re-installed. The ``sandesh`` CLI is REQUIRED: still absent after its
install offer, declined, or ``outdated``, it fails the pre-flight unless
the caller allows missing capabilities.

Every warning printed is also appended, unprefixed, to the caller's
``warnings`` list so the envelope can carry it. This module writes
nothing to disk. Stdlib only.
"""

import os
import re
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

#: Model B's own Pi package (the ``worktree`` capability, CR-MDB-029 §S3):
#: the one tier-1 provider ``--yes`` installs — never a third-party one.
MODELB_PI_PACKAGE = requirement("worktree")["provider"]

#: The oldest ``sandesh`` CLI Model B accepts (CR-MDB-047 §S1): Sandesh's
#: Pi extension 0.4.0 refuses an older one.
SANDESH_VERSION_FLOOR: tuple[int, int, int] = (0, 4, 0)

#: The verdict of a ``sandesh`` below the floor, or one whose version
#: cannot be read (CR-MDB-047 §S1).
OUTDATED = "outdated"

_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")
_VERSION_TIMEOUT_SECONDS = 10

#: The requirement ``probe`` kind of a tier-2 tool judged by
#: ``shutil.which`` and recorded only in ``[capabilities]`` — ``[deps]``
#: stays exactly uv/sandesh/crucible. Which tools carry it is DATA
#: (:data:`modelb_axi.requirements.REQUIREMENTS`), read at call time.
_PATH_PROBE = "path"

#: The published Python floor (CR-MDB-064 §S2): the interpreter the
#: deployed scripts run on reports a version at or above it.
PYTHON_FLOOR: tuple[int, int] = (3, 14)
_PYTHON_FLOOR_TEXT = ".".join(str(part) for part in PYTHON_FLOOR)

#: The second candidate's query (§S2): ``--system`` so uv never reports a
#: virtual environment, and a range so 3.15 qualifies.
_UV_PYTHON_FIND = ("python", "find", "--system", f">={_PYTHON_FLOOR_TEXT}")

#: Linux's shebang buffer (``BINPRM_BUF_SIZE``): a ``#!<path>`` line that
#: does not fit in it is truncated, so such a path cannot be recorded.
_SHEBANG_LIMIT = 256

#: What a candidate is asked, by running it (§S2): its version and whether
#: it is a virtual environment (``sys.prefix != sys.base_prefix``).
_INTERPRETER_QUERY = (
    "import sys; "
    "print('%d.%d.%d' % tuple(sys.version_info[:3]), int(sys.prefix == sys.base_prefix))"
)

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
    sandesh-relay`) through the PATH-resolved ``uv``, its output on the
    user's terminal (CR-MDB-036's :func:`run_on_terminal`), then RE-PROBE
    (CR-MDB-037 §S5). Returns the deps verdict: ``installed`` only when
    ``sandesh`` is then found on PATH, else ``absent`` with a warning."""
    command = f"uv tool install {SANDESH_PACKAGE}"
    try:
        returncode = run_on_terminal([uv_path, "tool", "install", SANDESH_PACKAGE])
    except OSError as exc:
        _warn(f"`{command}` could not run ({exc}); recording sandesh=absent", warnings)
        return ABSENT
    if returncode != 0:
        _warn(
            f"`{command}` failed (exit={returncode}); recording sandesh=absent",
            warnings,
        )
        return ABSENT
    if shutil.which("sandesh") is None:
        _warn(
            f"`{command}` exited 0 but `sandesh` is still not on PATH; "
            f"recording sandesh=absent",
            warnings,
        )
        return ABSENT
    return INSTALLED


def _probe_sandesh() -> tuple[str, str | None]:
    """The ``sandesh`` deps verdict and the version read (CR-MDB-047 §S1).

    ``absent`` when not on PATH; otherwise ``sandesh --version`` is run and
    its ``X.Y.Z`` compared numerically with :data:`SANDESH_VERSION_FLOOR`:
    ``detected`` at or above it, ``outdated`` below it or when no version
    can be read (the floor cannot be confirmed)."""
    path = shutil.which("sandesh")
    if path is None:
        return ABSENT, None
    try:
        result = subprocess.run(
            [path, "--version"], capture_output=True, text=True,
            timeout=_VERSION_TIMEOUT_SECONDS, stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired):
        return OUTDATED, None
    match = _VERSION_RE.search(result.stdout or "")
    if result.returncode != 0 or match is None:
        return OUTDATED, None
    version = tuple(int(part) for part in match.groups())
    verdict = DETECTED if version >= SANDESH_VERSION_FLOOR else OUTDATED
    return verdict, match.group(0)


def _read_interpreter(path: str) -> tuple[tuple[int, int, int], bool] | None:
    """Run the candidate ``path`` and read its version and whether it is NOT a
    virtual environment (CR-MDB-064 §S2); ``None`` when it cannot run or
    reports nothing readable."""
    try:
        result = subprocess.run(
            [path, "-I", "-c", _INTERPRETER_QUERY], capture_output=True, text=True,
            timeout=_VERSION_TIMEOUT_SECONDS, stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+) ([01])", (result.stdout or "").strip())
    if result.returncode != 0 or match is None:
        return None
    major, minor, micro, system = match.groups()
    return (int(major), int(minor), int(micro)), system == "1"


def _judge_interpreter(path: str) -> tuple[str | None, str | None, bool]:
    """Judge one candidate (CR-MDB-064 §S2): ``(version, rejection, below)``.

    Accepted (``rejection`` ``None``) when it is an existing executable that
    reports a version at or above :data:`PYTHON_FLOOR`, is not a virtual
    environment, and its path holds no whitespace and fits a shebang line.
    ``below`` is whether it ran and reported a version under the floor."""
    if not (os.path.isfile(path) and os.access(path, os.X_OK)):
        return None, "is not an executable file", False
    read = _read_interpreter(path)
    if read is None:
        return None, "did not report its version", False
    version_info, system = read
    version = ".".join(str(part) for part in version_info)
    if version_info[:2] < PYTHON_FLOOR:
        return version, f"is {version}, below the {_PYTHON_FLOOR_TEXT} floor", True
    if not system:
        return version, "is a virtual environment", False
    if any(char.isspace() for char in path):
        return version, "has whitespace in its path, which a shebang line cannot carry", False
    if len(f"#!{path}\n".encode()) > _SHEBANG_LIMIT:
        return version, (f"has a path longer than the kernel's {_SHEBANG_LIMIT}-byte "
                         "shebang limit"), False
    return version, None, False


def interpreter_rejection(path: str) -> str | None:
    """Why a recorded interpreter no longer serves the deployed scripts
    (CR-MDB-064 §S3) — it is missing, cannot run, reports a version below
    :data:`PYTHON_FLOOR`, or is otherwise unacceptable — or ``None`` when it
    still meets every rule a candidate meets (:func:`_judge_interpreter`)."""
    return _judge_interpreter(path)[1]


def _uv_python_find(uv_path: str) -> str | None:
    """The interpreter ``uv python find --system '>=3.14'`` reports, as its
    absolute path, or ``None`` when uv reports none (CR-MDB-064 §S2)."""
    try:
        result = subprocess.run(
            [uv_path, *_UV_PYTHON_FIND], capture_output=True, text=True,
            timeout=_VERSION_TIMEOUT_SECONDS, stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    lines = (result.stdout or "").strip().splitlines()
    if result.returncode != 0 or not lines or not lines[0].strip():
        return None
    return os.path.abspath(lines[0].strip())


def _probe_interpreter(
    uv_path: str, resolved: dict[str, str | None],
) -> tuple[str, str | None, str | None, str | None]:
    """Find the interpreter the deployed scripts run on (CR-MDB-064 §S2):
    ``(verdict, path, version, reason)``.

    Candidates, in order: ``python3`` on ``PATH`` (its absolute path as found,
    the link not resolved), then the one ``uv python find`` reports. The first
    accepted is ``detected``. Otherwise ``path`` is ``None`` and ``reason``
    names every rejection; the verdict is ``outdated`` when the ``PATH``
    ``python3`` reports a version below the floor, else ``absent`` — a
    ``python3`` at or above the floor that is rejected (a virtual environment,
    an unrecordable path) counts as none."""
    rejections: list[str] = []
    outdated = False
    found = resolve("python3", resolved)
    if found is None:
        rejections.append("no python3 on PATH")
    else:
        candidate = os.path.abspath(found)
        version, reason, below = _judge_interpreter(candidate)
        if reason is None:
            return DETECTED, candidate, version, None
        # DN-multi-harness-deploy-model §D22 ruling: `outdated` only when
        # this python3 ran and reported a version below the floor. One that
        # cannot report its version, or one at or above the floor rejected as
        # a virtual environment or for an unrecordable path, leaves the
        # verdict `absent`; the reason names the rejection.
        outdated = below
        rejections.append(f"python3 on PATH ({candidate}) {reason}")
    query = " ".join(_UV_PYTHON_FIND[:-1]) + f" '{_UV_PYTHON_FIND[-1]}'"
    candidate = _uv_python_find(uv_path)
    if candidate is None:
        rejections.append(f"`uv {query}` found none")
    else:
        version, reason, _below = _judge_interpreter(candidate)
        if reason is None:
            return DETECTED, candidate, version, None
        rejections.append(f"`uv {query}` found {candidate}, which {reason}")
    return (OUTDATED if outdated else ABSENT), None, None, ", and ".join(rejections)


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
    agent_dir: Path, *, confirm: Callable[[str], bool], pi_targeted: bool,
) -> None:
    """§S3: for each ABSENT tier-1 extension, offer Pi's own
    ``pi install npm:<package>``. A THIRD-PARTY extension runs only on an
    explicit interactive yes (``offer`` is ``None`` under ``--yes``). Model
    B's OWN package (:data:`MODELB_PI_PACKAGE`, CR-MDB-029 §S3) goes through
    ``confirm`` like Sandesh — so ``--yes`` runs it — and only when
    ``pi_targeted`` (``pi`` is among the run's harnesses). Model B never
    edits Pi's ``settings.json``; Pi does. A decline is recorded as a
    warning.

    After an install exits 0 that ONE capability is re-probed: its verdict
    in ``harness`` (updated in place) becomes ``installed`` iff Pi now
    loads it, else keeps the re-probed verdict with a warning naming where
    it was expected."""
    missing = [cap for cap, verdict in harness.items() if verdict == ABSENT]
    if not missing:
        return
    pi_path = shutil.which("pi")
    if pi_path is None:
        return
    for cap in missing:
        package = requirement(cap)["provider"]
        spec = f"npm:{package}"
        command = f"pi install {spec}"
        if package == MODELB_PI_PACKAGE:
            if not pi_targeted:
                continue
            ask = confirm
            prompt = f"{cap}=absent — install Model B's own Pi package via `{command}`?"
        elif offer is None:
            continue
        else:
            ask = offer
            prompt = f"{cap}=absent — run Pi's own `{command}`?"
        if not ask(prompt):
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
    harnesses: Iterable[str] = (),
) -> tuple[int, dict[str, str], dict[str, str], str | None]:
    """Run the dependency and capability pre-flight (installer stage 1).

    ``confirm`` is the CLI's prompt seam, pre-bound to the run's
    interactivity (always-True under ``--yes``) — used only for Model B's
    own Sandesh install and its own Pi package, never for a third-party
    extension. ``offer`` is the
    explicit-yes seam (``None`` under ``--yes``) for Pi's own ``pi install``
    and the §S8 provider installers. ``warnings``,
    when given, collects every warning and error printed. ``stacks`` are
    the selected stacks, one ``stack <name>:`` line each. ``harnesses`` are
    the harnesses the run targets: Model B's own Pi package is offered only
    when ``pi`` is among them (CR-MDB-029 §S3).

    Returns ``(exit_code, deps, capabilities, python)``: ``deps`` is exactly
    uv/sandesh/crucible for ``[deps]``; ``capabilities`` maps every probed
    requirement id to its verdict for ``[capabilities]`` (§S4); ``python``
    is the accepted interpreter's absolute path for ``[install] python``
    (CR-MDB-064 §S2), ``None`` when none was accepted. Non-zero when ``uv``
    is absent, when no interpreter meets the Python floor (whatever
    ``allow_missing_capabilities`` says), or a required capability (a tier-1
    one, or the ``sandesh`` CLI absent or ``outdated``) is missing without
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
        return 1, {}, dict(harness), None

    resolved: dict[str, str | None] = {"uv": uv_path}
    # CR-MDB-064 §S2: the interpreter, right after the `uv` check.
    python_verdict, python, python_version, python_reason = _probe_interpreter(
        uv_path, resolved)
    sandesh_verdict, sandesh_version = _probe_sandesh()
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
    if python is not None:
        print(f"python3: {python} ({python_version})", file=sys.stderr)
    for stack, client in stack_clients.items():
        probes = "".join(f"{name}={v} " for name, v in toolchains[stack].items())
        print(f"stack {stack}: {probes}client={client}", file=sys.stderr)

    if python is None:
        # CR-MDB-064 §S2: no accepted interpreter refuses before any write or
        # offer, whatever the flags — --allow-missing-capabilities does not
        # override it: every deployed script runs on the recorded one.
        remediation = requirement("python3")["remediation"]
        _warn(f"python3={python_verdict} — {python_reason}; install it with: "
              f"{remediation}", warnings, level="error")
        message = (
            f"pre-flight failed — no Python {_PYTHON_FLOOR_TEXT} interpreter, which every "
            f"deployed script runs on; --allow-missing-capabilities does not override it"
        )
        print(f"modelb-axi: {message}", file=sys.stderr)
        warnings.append(message)
        return 1, {}, {**harness, "uv": DETECTED, "sandesh": sandesh_verdict,
                       "crucible": crucible_verdict, **path_tools,
                       "python3": python_verdict}, None

    _offer_pi_installs(
        harness, offer, warnings, agent_dir,
        confirm=confirm, pi_targeted="pi" in set(harnesses),
    )
    failed = _harness_policy(
        harness, str(agent_dir / "settings.json"), allow_missing_capabilities, warnings,
    )
    if crucible_verdict == ABSENT:
        _warn(_CRUCIBLE_ABSENT_WARNING, warnings)
    elif crucible_verdict == UNKNOWN:
        _warn(_CRUCIBLE_UNKNOWN_WARNING, warnings)
    for row in path_rows:
        if path_tools[row["id"]] == ABSENT:
            effect = f": {row['absent_effect']}" if row.get("absent_effect") else ""
            _warn(
                f"{row['id']} not found on PATH — {_families(row)} will not run{effect}; "
                f"{row['remediation']}",
                warnings,
            )

    capabilities = {**harness, "uv": DETECTED, "sandesh": sandesh_verdict,
                    "crucible": crucible_verdict, **path_tools,
                    "python3": python_verdict}
    if failed:
        message = (
            f"pre-flight failed — required capabilities missing: {', '.join(failed)}; "
            f"install them, or re-run with --allow-missing-capabilities"
        )
        print(f"modelb-axi: {message}", file=sys.stderr)
        warnings.append(message)
        return 1, {}, capabilities, python

    if sandesh_verdict == ABSENT:
        command = f"uv tool install {SANDESH_PACKAGE}"
        if confirm(f"Sandesh not found — install via `{command}`?"):
            sandesh_verdict = _install_sandesh(uv_path, warnings)
            if sandesh_verdict == INSTALLED:
                # Updated deps line reflecting the proactive install.
                print(
                    f"deps: uv=detected sandesh=installed crucible={crucible_verdict}",
                    file=sys.stderr,
                )
        else:
            _warn(f"declined `{command}` — sandesh stays absent", warnings)
    elif sandesh_verdict == OUTDATED:
        floor = ".".join(str(part) for part in SANDESH_VERSION_FLOOR)
        families = _families(requirement("sandesh"))
        if sandesh_version is None:
            # CR-MDB-047 §S1: an unreadable version is never known to be
            # below the floor — the floor just cannot be confirmed.
            message = (
                f"sandesh=outdated — its version could not be read, so the {floor} "
                f"floor cannot be confirmed; {families} need it; upgrade it with "
                f"`uv tool upgrade {SANDESH_PACKAGE}`, or reinstall it with "
                f"`uv tool install --reinstall {SANDESH_PACKAGE}`"
            )
        else:
            message = (
                f"sandesh=outdated — found {sandesh_version}, below the {floor} floor; "
                f"{families} need it; upgrade with `uv tool upgrade {SANDESH_PACKAGE}`"
            )
        _warn(message, warnings)
    capabilities["sandesh"] = sandesh_verdict
    if sandesh_verdict in (ABSENT, OUTDATED) and not allow_missing_capabilities:
        # CR-MDB-047 §S1: the `sandesh` CLI is required — sandesh-pi refuses
        # a missing or outdated one — so, still absent after the offer,
        # declined or outdated, it fails the pre-flight like a required
        # tier-1 capability, before anything is written.
        message = (
            "pre-flight failed — required capabilities missing: sandesh; "
            "install them, or re-run with --allow-missing-capabilities"
        )
        print(f"modelb-axi: {message}", file=sys.stderr)
        warnings.append(message)
        return 1, {}, capabilities, python

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
    }, capabilities, python
