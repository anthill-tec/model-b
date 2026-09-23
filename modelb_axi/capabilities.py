"""Read-only capability probes for the installer pre-flight (CR-MDB-036
§S1/§S2).

- :func:`probe_harness` judges each tier-1 Pi capability by what Pi
  actually LOADS: its npm package listed in ``<agent-dir>/settings.json``
  ``packages[]`` (not disabled by ``extensions: []``) AND resolvable at
  ``<agent-dir>/npm/node_modules/<name>/package.json``. Only the
  ``packages`` key is read; a settings file that cannot be read or has an
  unrecognised shape yields ``unknown`` — never a crash.
- :func:`probe_crucible` / :func:`probe_crucible_client` judge Crucible by
  its released-client manifest ``~/.crucible/crucible-clients.json``
  (§S1 amendment) — never a ``crucible`` binary, never the server.

Verdicts are the strings ``detected`` / ``absent`` / ``unknown``. Nothing
here writes, executes, or opens a network connection. Stdlib only.
"""

import json
import os
from pathlib import Path

from modelb_axi.requirements import CRUCIBLE_MANIFEST_RELPATH, STACK_CLIENT_KEYS

#: Pi's agent-dir override; ``~/.pi/agent`` when unset.
AGENT_DIR_ENV = "PI_CODING_AGENT_DIR"

DETECTED = "detected"
ABSENT = "absent"
UNKNOWN = "unknown"


def resolve_agent_dir() -> Path:
    """``$PI_CODING_AGENT_DIR`` when set, else ``~/.pi/agent`` (§S2) —
    the personal settings only; a project's ``.pi/`` is its own concern."""
    env_value = os.environ.get(AGENT_DIR_ENV, "").strip()
    if env_value:
        return Path(env_value).expanduser()
    return Path.home() / ".pi" / "agent"


def _load_packages(settings_path: Path) -> list | None:
    """``packages[]`` from Pi's settings; ``[]`` when the file does not
    exist (a vanilla Pi lists nothing); ``None`` when it is unreadable or
    unrecognised."""
    try:
        text = settings_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except (OSError, UnicodeDecodeError):
        return None
    try:
        settings = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(settings, dict):
        return None
    packages = settings.get("packages", [])
    return packages if isinstance(packages, list) else None


def _npm_name(spec: str) -> str | None:
    """Package name of an ``npm:<name>[@<version>]`` spec (scoped names
    keep their leading ``@``); ``None`` for any other source."""
    if not spec.startswith("npm:"):
        return None
    body = spec[len("npm:"):]
    version_at = body.find("@", 1) if body.startswith("@") else body.find("@")
    return body if version_at == -1 else body[:version_at]


def _entry_source(entry) -> tuple[str | None, bool]:
    """``(source, enabled)`` for a packages[] entry: a string is its own
    source; an object's is its ``source``, disabled by ``extensions: []``."""
    if isinstance(entry, str):
        return entry, True
    if isinstance(entry, dict):
        source = entry.get("source")
        enabled = entry.get("extensions") != []
        return (source if isinstance(source, str) else None), enabled
    return None, True


def _package_verdict(packages: list, package: str, agent_dir: Path) -> str:
    matched_enabled = False
    matched = False
    other_sources = False
    for entry in packages:
        source, enabled = _entry_source(entry)
        name = _npm_name(source) if source is not None else None
        if name is None:
            other_sources = True
        elif name == package:
            matched = True
            matched_enabled = matched_enabled or enabled
    if matched:
        if not matched_enabled:
            return ABSENT
        on_disk = agent_dir / "npm" / "node_modules" / package / "package.json"
        return DETECTED if on_disk.is_file() else ABSENT
    # A git:/URL/local entry could provide the package under another spec.
    return UNKNOWN if other_sources else ABSENT


def probe_harness(providers: dict[str, str], agent_dir: Path | None = None) -> dict[str, str]:
    """Verdict per capability id, for ``providers`` (id -> npm package)."""
    if agent_dir is None:
        agent_dir = resolve_agent_dir()
    packages = _load_packages(agent_dir / "settings.json")
    if packages is None:
        return dict.fromkeys(providers, UNKNOWN)
    return {
        cap: _package_verdict(packages, package, agent_dir)
        for cap, package in providers.items()
    }


def crucible_manifest_path(home: Path | None = None) -> Path:
    """``<home>/.crucible/crucible-clients.json`` (``home`` = ``$HOME``)."""
    return (home if home is not None else Path.home()) / CRUCIBLE_MANIFEST_RELPATH


def load_crucible_clients(home: Path | None = None) -> tuple[str, dict]:
    """``(crucible verdict, clients mapping)`` per the §S1 manifest rules:
    ``detected`` iff the manifest parses with a ``clients`` object,
    ``absent`` if missing or without one, ``unknown`` if it does not parse."""
    path = crucible_manifest_path(home)
    if not path.is_file():
        return ABSENT, {}
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return UNKNOWN, {}
    clients = manifest.get("clients") if isinstance(manifest, dict) else None
    if not isinstance(clients, dict):
        return ABSENT, {}
    return DETECTED, clients


def probe_crucible_client(stack: str, crucible_verdict: str, clients: dict) -> str:
    """A stack's ``crucible-client`` verdict: ``detected`` iff
    ``clients[<key>]`` names an existing file (quarkus/java -> ``mvn``);
    an unparseable manifest leaves it ``unknown``."""
    if crucible_verdict == UNKNOWN:
        return UNKNOWN
    target = clients.get(STACK_CLIENT_KEYS[stack])
    if isinstance(target, str) and target and Path(target).expanduser().is_file():
        return DETECTED
    return ABSENT
