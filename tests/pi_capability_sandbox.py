"""Sandboxed Pi agent-dir and home fixtures for the harness capability
contract (CR-MDB-036 §S2/§S1).

Every test that drives the installer flow now also drives the harness
capability probe, which reads ``$PI_CODING_AGENT_DIR/settings.json``
(else ``~/.pi/agent/settings.json``). No test may ever read the real
``~/.pi``: this module builds throw-away agent dirs in the exact shape Pi
uses (``settings.json`` ``packages[]`` + ``npm/node_modules/<name>/
package.json``) and throw-away homes carrying (or lacking) Crucible's
released-client manifest ``~/.crucible/crucible-clients.json``.

Stdlib only; not a test module (no ``test_`` prefix), so discovery never
collects it.
"""

import atexit
import json
import shutil
import tempfile
from pathlib import Path

#: Tier-1 harness capability id -> the npm package that provides it
#: (CR-MDB-036 §S1 table).
TIER1_PACKAGES = {
    "dispatch": "@gotgenes/pi-subagents",
    "lean-ctx": "pi-lean-ctx",
    "permissions": "@gotgenes/pi-permission-system",
}

#: The environment variable the probe honours before ``~/.pi/agent``.
AGENT_DIR_ENV = "PI_CODING_AGENT_DIR"


def npm_spec(package: str, version: str | None = None) -> str:
    """``npm:<name>[@<version>]`` — the string form of a packages[] entry."""
    return f"npm:{package}" + (f"@{version}" if version else "")


def install_on_disk(agent_dir: Path, package: str) -> Path:
    """Materialise ``<agent-dir>/npm/node_modules/<name>/package.json``."""
    pkg_dir = Path(agent_dir) / "npm" / "node_modules" / package
    pkg_dir.mkdir(parents=True, exist_ok=True)
    manifest = pkg_dir / "package.json"
    manifest.write_text(
        json.dumps({"name": package, "version": "0.0.0-sandbox"}) + "\n",
        encoding="utf-8",
    )
    return manifest


def write_settings(agent_dir: Path, payload) -> Path:
    """Write ``<agent-dir>/settings.json``: a str is written verbatim
    (malformed-JSON cases), anything else is JSON-encoded."""
    agent_dir = Path(agent_dir)
    agent_dir.mkdir(parents=True, exist_ok=True)
    path = agent_dir / "settings.json"
    text = payload if isinstance(payload, str) else json.dumps(payload, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")
    return path


def make_agent_dir(
    agent_dir: Path, *, packages: list, on_disk=(), extra_settings: dict | None = None,
) -> Path:
    """A Pi agent dir whose settings list ``packages`` (raw packages[]
    entries: strings or objects) and whose node_modules holds ``on_disk``
    package names. Returns the agent dir."""
    agent_dir = Path(agent_dir)
    settings = dict(extra_settings or {})
    settings["packages"] = list(packages)
    write_settings(agent_dir, settings)
    for package in on_disk:
        install_on_disk(agent_dir, package)
    return agent_dir


def make_provisioned_agent_dir(agent_dir: Path, *, omit=()) -> Path:
    """Every tier-1 extension listed (``npm:<name>``) AND on disk, except
    the capability ids in ``omit`` (which are neither listed nor on disk)."""
    packages = [pkg for cap, pkg in TIER1_PACKAGES.items() if cap not in omit]
    return make_agent_dir(
        agent_dir, packages=[npm_spec(p) for p in packages], on_disk=packages,
    )


_SHARED: dict[str, str] = {}


def shared_provisioned_agent_dir() -> str:
    """One process-wide, fully provisioned sandbox agent dir (all tier-1
    capabilities ``detected``) — the default every installer-flow helper
    injects so no run ever falls back to the real ``~/.pi``. Removed at
    interpreter exit."""
    if "dir" not in _SHARED:
        root = tempfile.mkdtemp(prefix="modelb-pi-agent-sandbox-")
        atexit.register(shutil.rmtree, root, True)
        _SHARED["dir"] = str(make_provisioned_agent_dir(Path(root) / "agent"))
    return _SHARED["dir"]


def with_agent_dir(env_overrides: dict | None) -> dict:
    """Return ``env_overrides`` plus the shared provisioned agent dir,
    unless the caller already pinned ``PI_CODING_AGENT_DIR``."""
    merged = dict(env_overrides or {})
    merged.setdefault(AGENT_DIR_ENV, shared_provisioned_agent_dir())
    return merged


#: Crucible's released-client manifest, at the install ROOT (orchestrator
#: §S1 amendment, 2026-09-24): ``<home>/.crucible/crucible-clients.json``.
CRUCIBLE_MANIFEST_RELPATH = Path(".crucible") / "crucible-clients.json"

#: Stack -> manifest ``clients`` key (quarkus and java share ``mvn``).
STACK_CLIENT_KEYS = {
    "arduino": "arduino", "bun": "bun", "python": "python",
    "quarkus": "mvn", "java": "mvn", "rust": "rust",
}


def make_home(
    home: Path, *, crucible_manifest: bool, clients=(), dangling=(),
    manifest_text: str | None = None,
) -> Path:
    """A sandbox ``$HOME``. With ``crucible_manifest`` it carries
    ``.crucible/crucible-clients.json`` shaped like Crucible's real
    manifest: ``{"version", "config", "clients": {<key>: <abs path>}}``.
    ``clients`` are manifest keys (``python``, ``mvn``, ...) whose
    ``<key>-crucible.py`` is created under ``.crucible/clients/``;
    ``dangling`` keys are listed but point at a file that does not exist.
    ``manifest_text`` writes the manifest verbatim (malformed cases)."""
    home = Path(home)
    home.mkdir(parents=True, exist_ok=True)
    root = home / ".crucible"
    clients_dir = root / "clients"
    entries = {}
    for key in clients:
        clients_dir.mkdir(parents=True, exist_ok=True)
        script = clients_dir / f"{key}-crucible.py"
        script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        script.chmod(0o755)
        entries[key] = str(script)
    for key in dangling:
        entries[key] = str(clients_dir / f"{key}-crucible.py")
    if crucible_manifest or manifest_text is not None:
        root.mkdir(parents=True, exist_ok=True)
        text = manifest_text if manifest_text is not None else json.dumps({
            "version": "0.0.0-sandbox",
            "config": str(root / "crucible.toml"),
            "clients": entries,
        }, indent=2) + "\n"
        (home / CRUCIBLE_MANIFEST_RELPATH).write_text(text, encoding="utf-8")
    return home


def shared_home_without_crucible() -> str:
    """One process-wide, EMPTY sandbox ``$HOME`` (no
    ``.crucible/crucible-clients.json``, no ``.pi``) — for
    installer runs that pin ``crucible=absent`` without depending on
    whether the machine running the suite has Crucible's clients
    installed. Removed at interpreter exit."""
    if "home" not in _SHARED:
        root = tempfile.mkdtemp(prefix="modelb-home-sandbox-")
        atexit.register(shutil.rmtree, root, True)
        _SHARED["home"] = str(make_home(Path(root) / "home", crucible_manifest=False))
    return _SHARED["home"]


def parse_group_line(stderr: str, prefix: str) -> dict | None:
    """Parse the first stderr line starting with ``prefix`` (e.g.
    ``"harness:"``) into ``{key: verdict}``; None when absent."""
    for line in stderr.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            pairs = stripped[len(prefix):].split()
            return dict(pair.split("=", 1) for pair in pairs if "=" in pair)
    return None
