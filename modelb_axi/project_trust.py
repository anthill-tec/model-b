"""Pi's SAVED project-trust decision for a directory (CR-MDB-037 §S4).

Mirrors Pi's own resolution (``trust-manager.js``): the entry for the
canonical directory or its CLOSEST ancestor in ``<agent-dir>/trust.json``
(values ``true`` / ``false``; ``null`` is no decision), else
``defaultProjectTrust`` from ``<agent-dir>/settings.json`` (``ask`` when
unset). A command-line ``--approve``/``--no-approve`` or an extension can
still decide differently at run time; this reports the saved decision only.

Read-only — Model B never edits ``trust.json``. Any unreadable or
unrecognised file gives ``unknown``, never an exception. Stdlib only.
"""

import json
from pathlib import Path

TRUSTED = "trusted"
UNTRUSTED = "untrusted"
ASK = "ask"
UNKNOWN = "unknown"

_DEFAULT_TRUST = {"always": TRUSTED, "never": UNTRUSTED, "ask": ASK}

#: The one warning for ``untrusted`` / ``ask`` (§S4).
UNTRUSTED_WARNING = (
    "project trust: {state} — Pi will not load this project's hooks and "
    "permission policy (.pi/extensions/) until the project is trusted; run "
    "/trust in Pi from the project. This is Pi's saved decision only: a "
    "command-line override (--approve) or an extension may decide otherwise."
)


class _Unrecognised(ValueError):
    """A trust or settings file Model B cannot interpret."""


def _load_json_object(path: Path) -> dict | None:
    """The file's JSON object; ``None`` when it does not exist."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as exc:
        raise _Unrecognised(str(exc)) from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise _Unrecognised(str(exc)) from exc
    if not isinstance(data, dict):
        raise _Unrecognised(f"{path}: expected an object")
    return data


def _saved_entry(entries: dict, directory: Path) -> bool | None:
    """The closest ``true``/``false`` entry for ``directory`` or an
    ancestor, by path component; ``None`` when none applies."""
    for candidate in (directory, *directory.parents):
        value = entries.get(str(candidate))
        if isinstance(value, bool):
            return value
    return None


def resolve_trust(target: Path, agent_dir: Path) -> str:
    """``trusted | untrusted | ask | unknown`` for ``target``."""
    try:
        entries = _load_json_object(agent_dir / "trust.json") or {}
        if any(v is not None and not isinstance(v, bool) for v in entries.values()):
            raise _Unrecognised("trust.json values must be true, false or null")
        decision = _saved_entry(entries, Path(target).resolve())
        if decision is not None:
            return TRUSTED if decision else UNTRUSTED
        settings = _load_json_object(agent_dir / "settings.json") or {}
    except _Unrecognised:
        return UNKNOWN
    default = settings.get("defaultProjectTrust", "ask")
    return _DEFAULT_TRUST.get(default, UNKNOWN) if isinstance(default, str) else UNKNOWN
