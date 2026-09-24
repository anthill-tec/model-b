"""Shared test helpers (CR-MDB-032).

``installed_crucible_file`` resolves an installed Crucible client file through Crucible's
manifest ``~/.crucible/crucible-clients.json`` — the one sanctioned out-of-repo dependency
(standing rule 2026-09-18). No test reaches a personal Crucible checkout (CR-MDB-032 §S1): a
test that needs an installed client resolves it here and SKIPS, naming the manifest, when the
manifest, its entry or the file is missing.

Every other helper here is one that several test modules used to define privately with an
identical body (CR-MDB-032 §S3); a module imports it under its old local name. Where two
look-alikes behave differently they stay two helpers — ``read_text`` (strict UTF-8) and
``read_text_lenient`` (undecodable bytes replaced) are not one function.

Stdlib only.
"""

import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

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


# ------------------------------------------------------------------ file reads ----

def read_text(path: Path) -> str:
    """``path`` as strict UTF-8 text (a decode error raises)."""
    return path.read_text(encoding="utf-8")


def read_text_lenient(path: Path) -> str:
    """``path`` as UTF-8 text with undecodable bytes replaced (never raises on encoding)."""
    return path.read_text(encoding="utf-8", errors="replace")


def files_under(dir_path: Path):
    """Yield all regular files under dir_path (recursive). Empty if dir absent."""
    if not dir_path.is_dir():
        return
    for root, _dirs, files in os.walk(dir_path):
        for name in files:
            yield Path(root) / name


def files_containing(dir_path: Path, needle: str):
    """Return sorted relative paths of files under dir_path whose content contains needle."""
    hits = []
    for f in files_under(dir_path):
        try:
            content = read_text_lenient(f)
        except (UnicodeDecodeError, OSError):
            continue
        if needle in content:
            hits.append(str(f.relative_to(dir_path)))
    return sorted(hits)


#: The wave-2 archive the retired-content moves landed in.
ARCHIVE_WAVE2 = REPO_ROOT / "archive" / "wave2"


def archive_has_content_move(name: str, anchor: str) -> bool:
    """True if some file under archive/wave2/ has `name` as a path component
    (or matching filename) and its content contains `anchor` -- tolerant of
    exact archival layout (flat file vs mirrored subdirectory) while still
    proving it is a REAL content-preserving copy, not a stub."""
    for f in files_under(ARCHIVE_WAVE2):
        if name not in f.parts and f.name != name:
            continue
        try:
            content = read_text_lenient(f)
        except (UnicodeDecodeError, OSError):
            continue
        if anchor in content:
            return True
    return False


# ------------------------------------------------------------------ AXI envelopes ----

def decode_axi(stdout: str) -> dict:
    """The ``axi`` mapping of a TOON envelope printed on stdout, decoded with the package's OWN
    codec; ``{}`` when stdout is not an envelope (the caller's assertions then report it)."""
    from modelb_axi.toon import decode
    try:
        return decode(stdout).get("axi", {})
    except Exception:  # noqa: BLE001 -- a non-envelope stdout fails the caller's asserts
        return {}


def decode_envelope(stdout: str) -> dict:
    """Decode a ``modelb_axi`` TOON envelope printed on stdout, whole, using the package's OWN
    codec (a decode error raises)."""
    from modelb_axi.toon import decode
    return decode(stdout)


# ------------------------------------------------------------------ markdown ----

def split_frontmatter(content: str):
    """Split a markdown file into (frontmatter, body) on the '---'
    delimiters. Returns ("", content) if there is no well-formed '---'
    frontmatter block."""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", content
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            frontmatter = "\n".join(lines[1:idx])
            body = "\n".join(lines[idx + 1:])
            return frontmatter, body
    return "", content


def md_section(content: str, heading_prefix: str) -> str:
    """The Markdown section whose heading line starts with
    ``heading_prefix``, up to (not including) the next ``## `` heading;
    ``""`` when no such heading exists."""
    out: list[str] = []
    inside = False
    for line in content.splitlines():
        if not inside and line.startswith(heading_prefix):
            inside = True
            out.append(line)
            continue
        if inside and line.startswith("## "):
            break
        if inside:
            out.append(line)
    return "\n".join(out)


def parse_env_file(path: Path) -> dict:
    """Minimal ``KEY=VALUE`` parser for an emitted ``.env``/``.env.local``
    (values may be bare or double-quoted; blank lines and ``#``-comments are
    skipped; ``{}`` when the file is absent) -- test-side only, no production
    coupling."""
    values: dict = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, raw_value = stripped.partition("=")
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1]
        values[key.strip()] = value
    return values


# ------------------------------------------------------------------ fixtures ----

def write_executable(bin_dir, name: str, body: str) -> Path:
    """Write an executable script fixture at ``bin_dir/name`` (mode 0755) and return its path --
    the seam for fake ``uv``/``sandesh``/``pi`` binaries on an isolated tmp ``PATH``."""
    path = Path(bin_dir) / name
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path

