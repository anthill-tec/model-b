"""Shared test helpers (CR-MDB-032).

``installed_crucible_file`` resolves an installed Crucible client file through Crucible's
manifest ``~/.crucible/crucible-clients.json`` — the one sanctioned out-of-repo dependency
(standing rule 2026-09-18). No test reaches a personal Crucible checkout (CR-MDB-032 §S1): a
test that needs an installed client resolves it here and SKIPS, naming the manifest, when the
manifest, its entry or the file is missing.

Stdlib only.
"""

import json
from pathlib import Path

#: How every skip reason spells the manifest, so a reader can find it on any machine.
CRUCIBLE_MANIFEST_SPELLING = "~/.crucible/crucible-clients.json"


def installed_crucible_file(stack: str, sibling: str | None = None) -> tuple:
    """``(path, "")`` for the installed client ``clients[stack]`` listed in Crucible's manifest,
    or — when ``sibling`` is given — for the file of that name beside it (the installed clients
    directory also ships ``toon.py``). ``(None, reason)`` when anything is missing; ``reason``
    names ``~/.crucible/crucible-clients.json`` and what was missing, ready for ``skipTest``.

    Manifest paths are used as written: Crucible's installer records absolute paths.
    """
    manifest = Path.home() / ".crucible" / "crucible-clients.json"
    if not manifest.is_file():
        return None, f"{CRUCIBLE_MANIFEST_SPELLING} is absent ({manifest}); no installed Crucible client to use"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"{CRUCIBLE_MANIFEST_SPELLING} is unreadable ({type(exc).__name__}: {exc})"
    clients = data.get("clients") if isinstance(data, dict) else None
    entry = clients.get(stack) if isinstance(clients, dict) else None
    if not isinstance(entry, str) or not entry:
        return None, f"{CRUCIBLE_MANIFEST_SPELLING} lists no clients[{stack!r}] entry"
    client = Path(entry)
    target = client.parent / sibling if sibling else client
    if not target.is_file():
        what = f"{sibling} beside clients[{stack!r}]" if sibling else f"clients[{stack!r}]"
        return None, f"{CRUCIBLE_MANIFEST_SPELLING} names {what}, but {target} is not a file"
    return target, ""
