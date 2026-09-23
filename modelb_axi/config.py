"""``install.toml`` read/write (CR-MDB-014 §S6).

Reads go through stdlib ``tomllib``. Writes use a small hand-rolled
serializer covering exactly the pinned config schema — string values,
lists of strings, and the ``[[files]]`` array-of-tables — because the
stdlib ships no TOML writer and the runtime is stdlib-only:

    [install]           version / harnesses / asset_root
    [deps]              persisted pre-flight verdicts
    [[files]]           one entry per deployed file: path + sha256

Atomicity (§S6 "written last"): the file is serialized to a temp file in
the same directory and ``os.replace``-d into place, and callers only
invoke :func:`write_install_toml` AFTER every deploy step has succeeded
— a failed deploy leaves no ``install.toml`` at all.
"""

import tomllib
from pathlib import Path

from modelb_axi._fsutil import atomic_write

INSTALL_TOML_NAME = "install.toml"
#: install.toml holds no secrets, so 0644 is a decision rather than
#: tempfile's 0600 default (CR-MDB-033 §S2).
_INSTALL_TOML_MODE = 0o644


def _toml_string(value: str) -> str:
    """Serialize a basic TOML string (escape backslash, quote, control)."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    escaped = escaped.replace("\n", "\\n").replace("\t", "\\t").replace("\r", "\\r")
    return f'"{escaped}"'


def _toml_value(value) -> str:
    if isinstance(value, str):
        return _toml_string(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    raise TypeError(f"unsupported TOML value type for this schema: {type(value)!r}")


def serialize_install_toml(
    install: dict, deps: dict, files: list[dict]
) -> str:
    """Serialize the pinned install.toml schema to TOML text."""
    lines: list[str] = ["[install]"]
    for key, value in install.items():
        lines.append(f"{key} = {_toml_value(value)}")
    lines.append("")
    lines.append("[deps]")
    for key, value in deps.items():
        lines.append(f"{key} = {_toml_value(value)}")
    for entry in files:
        lines.append("")
        lines.append("[[files]]")
        for key, value in entry.items():
            lines.append(f"{key} = {_toml_value(value)}")
    return "\n".join(lines) + "\n"


def write_install_toml(
    home: Path, install: dict, deps: dict, files: list[dict]
) -> Path:
    """Atomically write ``install.toml`` under ``home`` (temp + rename).

    Mode 0644: the file holds no secrets (CR-MDB-033 §S2)."""
    home.mkdir(parents=True, exist_ok=True)
    text = serialize_install_toml(install, deps, files)
    target = home / INSTALL_TOML_NAME
    atomic_write(target, text.encode("utf-8"), mode=_INSTALL_TOML_MODE)
    return target


def load_install_toml(home: Path) -> dict:
    """Parse ``install.toml`` under ``home`` (empty dict when absent)."""
    path = home / INSTALL_TOML_NAME
    if not path.is_file():
        return {}
    with open(path, "rb") as fh:
        return tomllib.load(fh)


def load_manifest_hashes(home: Path) -> dict[str, str]:
    """Prior-install manifest as ``{path: sha256}`` for the §S6/AC5
    hash-check. Tolerates a missing/legacy ``files`` shape (e.g. the C1
    hand-authored ``[files]`` table stub) by returning ``{}``."""
    data = load_install_toml(home)
    files = data.get("files")
    if not isinstance(files, list):
        return {}
    return {
        str(entry["path"]): str(entry["sha256"])
        for entry in files
        if isinstance(entry, dict) and "path" in entry and "sha256" in entry
    }
