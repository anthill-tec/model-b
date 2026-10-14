"""Stamp a dev version for the release rehearsal, or check a tag against the version sources.

Usage, from the repository root:

- ``python3 .github/scripts/stamp_version.py stamp <ref> <run-number> [<target>...]``
- ``python3 .github/scripts/stamp_version.py check <tag> <target>...``

``stamp`` accepts a ref ``release/X.Y.Z`` or ``hotfix/X.Y.Z`` (each of ``X``, ``Y``, ``Z``
matching ``0|[1-9][0-9]*``) and a run number ``N`` matching ``[1-9][0-9]*``. With no target it
prints ``X.Y.Z``. With targets, every target's version source must be ``X.Y.Z``; then it writes
``X.Y.Z.devN`` (PEP 440) into each ``pypi`` source and ``X.Y.Z-dev.N`` into each ``npm`` one --
changing only those values, every other byte unchanged -- and prints ``X.Y.Z``.

``check`` exits 1, naming each version source that is not ``<tag>``, and writes nothing.

A target is ``pypi:<dir>`` or ``npm:<dir>``. Its version source:

- ``pypi:<dir>`` -- ``<dir>/pyproject.toml``'s ``[project] version``; or, with ``version`` in
  ``[project] dynamic`` under hatchling, the file named by ``[tool.hatch.version] path`` (relative
  to ``<dir>``), its ``__version__ = "..."`` line, a trailing ``# comment`` kept.
- ``npm:<dir>`` -- ``<dir>/package.json``'s top-level ``"version"``, at a two-space indent.

A source's line endings, LF or CRLF, are kept byte for byte.

Every refusal exits 1 with one line on stderr naming the ref, the run number or the file, prints
nothing on stdout and writes nothing: a missing or unreadable file, another dynamic-version
backend, a hatch version with no ``path``, no version at all, a ``__version__`` absent or
single-quoted, a ``package.json`` with no two-space top-level ``"version"``, and a version other
than the ref's.

Rendered into the project by ``modelb-axi`` (its release workflow runs it); not part of the
``modelb_axi`` package. Stdlib only, and no syntax newer than Python 3.12, the hosted runner's
default.
"""

import re
import sys
import tomllib
from pathlib import Path

_NUMBER = r"(?:0|[1-9][0-9]*)"
_REF = re.compile(rf"(?:release|hotfix)/({_NUMBER}\.{_NUMBER}\.{_NUMBER})")
_RUN = re.compile(r"[1-9][0-9]*")
# The value may be followed by a comment; a line may end in CRLF (``$`` alone stops before LF).
_INIT_VERSION = re.compile(r'^(__version__ = ")([^"\r\n]*)(")[ \t]*(?:#[^\r\n]*)?\r?$', re.M)
# package.json is two-space indented: the anchored indent matches its top-level "version" key
# only, never a nested one on its own line.
_PACKAGE_VERSION = re.compile(r'^(  "version":\s*")([^"]*)(")', re.M)
_PROJECT_TABLE = re.compile(r"^\[project\][ \t]*(?:#[^\r\n]*)?\r?$", re.M)
_NEXT_TABLE = re.compile(r"^\[", re.M)
_PROJECT_VERSION = re.compile(r'^(version\s*=\s*")([^"]*)(")', re.M)
_HATCH = "hatchling.build"
_USAGE = ("usage: stamp_version.py stamp <ref> <run-number> [<target>...] | "
          "check <tag> <target>...")


def _read(path: Path) -> str:
    """The file's text, decoded without newline translation so a rewrite keeps every byte;
    exits 1 naming ``path`` when it is missing or unreadable."""
    try:
        return path.read_bytes().decode("utf-8")
    except FileNotFoundError:
        sys.exit(f"{path.as_posix()}: missing")
    except (OSError, UnicodeDecodeError) as error:
        sys.exit(f"{path.as_posix()}: cannot be read: {type(error).__name__}")


class _Source:
    """One version source: its file, its text and the span of its version value."""

    def __init__(self, path: Path, text: str, match: re.Match, offset: int = 0):
        self.path = path
        self.text = text
        self.start = offset + match.start(2)
        self.end = offset + match.end(2)
        self.version = match.group(2)

    def stamped(self, version: str) -> bytes:
        return (self.text[:self.start] + version + self.text[self.end:]).encode("utf-8")


def _pypi_source(directory: Path) -> _Source:
    pyproject = directory / "pyproject.toml"
    name = pyproject.as_posix()
    text = _read(pyproject)
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        sys.exit(f"{name}: cannot be parsed: {error}")
    project = data.get("project", {})
    if "version" in project.get("dynamic", []):
        backend = data.get("build-system", {}).get("build-backend")
        if backend != _HATCH:
            sys.exit(f"{name}: a dynamic version under {backend or 'no build backend'} "
                     f"is not supported; only {_HATCH}'s [tool.hatch.version] path is")
        relative = data.get("tool", {}).get("hatch", {}).get("version", {}).get("path")
        if not isinstance(relative, str) or not relative:
            sys.exit(f"{name}: [tool.hatch.version] names no path")
        version_file = directory / relative
        version_text = _read(version_file)
        match = _INIT_VERSION.search(version_text)
        if match is None:
            sys.exit(f'{version_file.as_posix()}: no __version__ = "..." line')
        return _Source(version_file, version_text, match)
    if "version" not in project:
        sys.exit(f"{name}: [project] has no version, static or dynamic")
    table = _PROJECT_TABLE.search(text)
    if table is None:
        sys.exit(f"{name}: no [project] table header")
    following = _NEXT_TABLE.search(text, table.end())
    end = following.start() if following else len(text)
    match = _PROJECT_VERSION.search(text[table.end():end])
    if match is None:
        sys.exit(f'{name}: no [project] version = "..." line')
    return _Source(pyproject, text, match, table.end())


def _npm_source(directory: Path) -> _Source:
    package = directory / "package.json"
    text = _read(package)
    match = _PACKAGE_VERSION.search(text)
    if match is None:
        sys.exit(f'{package.as_posix()}: no top-level "version" at a two-space indent')
    return _Source(package, text, match)


def _sources(targets: list[str]) -> list[tuple[str, _Source]]:
    """``(target name, source)`` for each target, every file read before any is written."""
    found = []
    for target in targets:
        name, _sep, directory = target.partition(":")
        if name == "pypi":
            found.append((name, _pypi_source(Path(directory or "."))))
        elif name == "npm":
            found.append((name, _npm_source(Path(directory or "."))))
        else:
            sys.exit(f"target {target!r} is not pypi:<dir> or npm:<dir>")
    return found


def _stamp(argv: list[str]) -> int:
    if len(argv) < 2:
        sys.exit(_USAGE)
    ref, run, targets = argv[0], argv[1], argv[2:]
    ref_match = _REF.fullmatch(ref)
    if ref_match is None:
        sys.exit(f"ref {ref!r} is not release/X.Y.Z or hotfix/X.Y.Z")
    if _RUN.fullmatch(run) is None:
        sys.exit(f"run number {run!r} is not a positive integer without leading zeros")
    release = ref_match.group(1)
    sources = _sources(targets)
    for _name, source in sources:
        if source.version != release:
            sys.exit(f"{source.path.as_posix()}: version {source.version} is not the ref's "
                     f"{release}")
    for name, source in sources:
        dev = f"{release}.dev{run}" if name == "pypi" else f"{release}-dev.{run}"
        source.path.write_bytes(source.stamped(dev))
    sys.stdout.write(release + "\n")
    return 0


def _check(argv: list[str]) -> int:
    if len(argv) < 2:
        sys.exit(_USAGE)
    tag, targets = argv[0], argv[1:]
    off = [source for _name, source in _sources(targets) if source.version != tag]
    for source in off:
        sys.stderr.write(f"{source.path.as_posix()}: version {source.version} is not the tag "
                         f"{tag}\n")
    return 1 if off else 0


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in ("stamp", "check"):
        sys.exit(_USAGE)
    return (_stamp if argv[1] == "stamp" else _check)(argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
