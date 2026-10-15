"""Stamp a dev version for the release rehearsal, check a tag against the version sources, or
read them.

Usage, from the repository root:

- ``python3 .github/scripts/stamp_version.py stamp <ref> <run-number> [<target>...]``
- ``python3 .github/scripts/stamp_version.py check <tag> <target>...``
- ``python3 .github/scripts/stamp_version.py read <target>...``

``stamp`` accepts a ref ``release/X.Y.Z`` or ``hotfix/X.Y.Z`` (each of ``X``, ``Y``, ``Z``
matching ``0|[1-9][0-9]*``) and a run number ``N`` matching ``[1-9][0-9]*``. With no target it
prints ``X.Y.Z``. With targets, every target's version source must be ``X.Y.Z``; then it writes
``X.Y.Z.devN`` (PEP 440) into each ``pypi`` source and ``X.Y.Z-dev.N`` into each ``npm`` one --
changing only those values, every other byte unchanged -- and prints ``X.Y.Z``. A ``crates`` or
``maven-central`` source is never stamped (its rehearsal uploads nothing): it is left unchanged,
but still refused when its version is not ``X.Y.Z``.

``check`` exits 1, naming each version source that is not ``<tag>``, and writes nothing.

``read <target>...`` prints ``<target><TAB><version>`` per target, each target exactly as given,
in order; it compares nothing and writes nothing, and exits 1 with one stderr line per refusal.

A target is ``pypi:<dir>``, ``npm:<dir>``, ``crates:<dir>`` or ``maven-central:<dir>``. Its
version source:

- ``pypi:<dir>`` -- ``<dir>/pyproject.toml``'s ``[project] version``; or, with ``version`` in
  ``[project] dynamic`` under hatchling, the file named by ``[tool.hatch.version] path`` (relative
  to ``<dir>``), its ``__version__ = "..."`` line, a trailing ``# comment`` kept.
- ``npm:<dir>`` -- ``<dir>/package.json``'s top-level ``"version"``, at a two-space indent.
- ``crates:<dir>`` -- ``<dir>/Cargo.toml``'s ``[package] version``; or, with
  ``version.workspace = true`` (or ``version = { workspace = true }``) there, the repository root
  ``Cargo.toml``'s ``[workspace.package] version``.
- ``maven-central:<dir>`` -- ``<dir>/pom.xml``'s own ``<version>``, the child of ``<project>``,
  never the ``<parent>``'s.

A source's line endings, LF or CRLF, are kept byte for byte.

Every refusal exits 1 with one line on stderr naming the ref, the run number or the file, prints
nothing on stdout and writes nothing: a missing or unreadable file, another dynamic-version
backend, a hatch version with no ``path``, no version at all, a ``__version__`` absent or
single-quoted, a ``package.json`` with no two-space top-level ``"version"``, a ``Cargo.toml`` with
no ``[package]`` table or no version, a workspace version with no ``[workspace.package]
version``, a ``pom.xml`` with no own ``<version>`` or a property reference (``${...}``) as its
version, and a version other than the ref's.

Rendered into the project by ``modelb-axi`` (its release workflow runs it); not part of the
``modelb_axi`` package. Stdlib only, and no syntax newer than Python 3.12, the hosted runner's
default.
"""

import re
import sys
import tomllib
from pathlib import Path
from xml.etree import ElementTree

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
#: The targets with a version source, as this script takes them.
_FORMS = "pypi:<dir>, npm:<dir>, crates:<dir> or maven-central:<dir>"
#: The targets whose source ``stamp`` writes.
_STAMPED = ("pypi", "npm")
_USAGE = ("usage: stamp_version.py stamp <ref> <run-number> [<target>...] | "
          "check <tag> <target>... | read <target>...")


class _Refusal(Exception):
    """One refusal: its message is the one stderr line."""


def _read(path: Path) -> str:
    """The file's text, decoded without newline translation so a rewrite keeps every byte;
    refuses naming ``path`` when it is missing or unreadable."""
    try:
        return path.read_bytes().decode("utf-8")
    except FileNotFoundError:
        raise _Refusal(f"{path.as_posix()}: missing") from None
    except (OSError, UnicodeDecodeError) as error:
        raise _Refusal(f"{path.as_posix()}: cannot be read: {type(error).__name__}") from None


def _toml(path: Path) -> dict:
    """``path`` read and parsed as TOML; refuses naming it when it cannot be."""
    try:
        return tomllib.loads(_read(path))
    except tomllib.TOMLDecodeError as error:
        raise _Refusal(f"{path.as_posix()}: cannot be parsed: {error}") from None


class _Source:
    """One version source: its file and version, and for a stamped one its text and the span
    of its version value."""

    def __init__(self, path: Path, version: str, text: str = "", span: tuple[int, int] = (0, 0)):
        self.path = path
        self.version = version
        self.text = text
        self.start, self.end = span

    @classmethod
    def matched(cls, path: Path, text: str, match: re.Match, offset: int = 0) -> "_Source":
        return cls(path, match.group(2), text, (offset + match.start(2), offset + match.end(2)))

    def stamped(self, version: str) -> bytes:
        return (self.text[:self.start] + version + self.text[self.end:]).encode("utf-8")


def _pypi_source(directory: Path) -> _Source:
    pyproject = directory / "pyproject.toml"
    name = pyproject.as_posix()
    text = _read(pyproject)
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise _Refusal(f"{name}: cannot be parsed: {error}") from None
    project = data.get("project", {})
    if "version" in project.get("dynamic", []):
        backend = data.get("build-system", {}).get("build-backend")
        if backend != _HATCH:
            raise _Refusal(f"{name}: a dynamic version under {backend or 'no build backend'} "
                           f"is not supported; only {_HATCH}'s [tool.hatch.version] path is")
        relative = data.get("tool", {}).get("hatch", {}).get("version", {}).get("path")
        if not isinstance(relative, str) or not relative:
            raise _Refusal(f"{name}: [tool.hatch.version] names no path")
        version_file = directory / relative
        version_text = _read(version_file)
        match = _INIT_VERSION.search(version_text)
        if match is None:
            raise _Refusal(f'{version_file.as_posix()}: no __version__ = "..." line')
        return _Source.matched(version_file, version_text, match)
    if "version" not in project:
        raise _Refusal(f"{name}: [project] has no version, static or dynamic")
    table = _PROJECT_TABLE.search(text)
    if table is None:
        raise _Refusal(f"{name}: no [project] table header")
    following = _NEXT_TABLE.search(text, table.end())
    end = following.start() if following else len(text)
    match = _PROJECT_VERSION.search(text[table.end():end])
    if match is None:
        raise _Refusal(f'{name}: no [project] version = "..." line')
    return _Source.matched(pyproject, text, match, table.end())


def _npm_source(directory: Path) -> _Source:
    package = directory / "package.json"
    text = _read(package)
    match = _PACKAGE_VERSION.search(text)
    if match is None:
        raise _Refusal(f'{package.as_posix()}: no top-level "version" at a two-space indent')
    return _Source.matched(package, text, match)


def _crates_source(directory: Path) -> _Source:
    """``<dir>/Cargo.toml``'s ``[package] version``, or the repository root ``Cargo.toml``'s
    ``[workspace.package] version`` when the package takes the workspace's."""
    manifest = directory / "Cargo.toml"
    package = _toml(manifest).get("package")
    if not isinstance(package, dict):
        raise _Refusal(f"{manifest.as_posix()}: no [package] table")
    version = package.get("version")
    if isinstance(version, str):
        return _Source(manifest, version)
    if version != {"workspace": True}:
        raise _Refusal(f'{manifest.as_posix()}: no [package] version = "..." '
                       "and no version.workspace = true")
    root = Path("Cargo.toml")
    shared = _toml(root).get("workspace", {}).get("package", {}).get("version")
    if not isinstance(shared, str):
        raise _Refusal(f"{root.as_posix()}: no [workspace.package] version, which "
                       f"{manifest.as_posix()} takes")
    return _Source(root, shared)


def _maven_source(directory: Path) -> _Source:
    """``<dir>/pom.xml``'s own ``<version>``, the child of ``<project>``."""
    pom = directory / "pom.xml"
    name = pom.as_posix()
    text = _read(pom)
    if "<!DOCTYPE" in text or "<!ENTITY" in text:
        # A POM needs no DTD; refusing one keeps entity expansion out of the stdlib parser.
        raise _Refusal(f"{name}: a DOCTYPE or ENTITY declaration is not supported")
    try:
        project = ElementTree.fromstring(text.encode("utf-8"))  # noqa: S314 - no DTD, above
    except ElementTree.ParseError as error:
        raise _Refusal(f"{name}: cannot be parsed: {error}") from None
    if project.tag.rpartition("}")[2] != "project":
        raise _Refusal(f"{name}: the root element is <{project.tag}>, not <project>")
    own = [(child.text or "").strip() for child in project
           if child.tag == "version" or child.tag.endswith("}version")]
    version = own[0] if own else ""
    if not version:
        raise _Refusal(f"{name}: no own <version> under <project> (a <parent>'s is not read)")
    if "${" in version:
        raise _Refusal(f"{name}: the version {version} is a property reference, not a version")
    return _Source(pom, version)


_READERS = {"pypi": _pypi_source, "npm": _npm_source, "crates": _crates_source,
            "maven-central": _maven_source}


def _source(target: str) -> tuple[str, _Source]:
    """``(target name, source)`` of one target; refuses a target with no version source."""
    name, sep, directory = target.partition(":")
    reader = _READERS.get(name) if sep else None
    if reader is None:
        raise _Refusal(f"target {target!r} is not {_FORMS}")
    return name, reader(Path(directory or "."))


def _sources(targets: list[str]) -> list[tuple[str, _Source]]:
    """``(target name, source)`` for each target, every file read before any is written."""
    return [_source(target) for target in targets]


def _stamp(argv: list[str]) -> int:
    if len(argv) < 2:
        sys.exit(_USAGE)
    ref, run, targets = argv[0], argv[1], argv[2:]
    ref_match = _REF.fullmatch(ref)
    if ref_match is None:
        raise _Refusal(f"ref {ref!r} is not release/X.Y.Z or hotfix/X.Y.Z")
    if _RUN.fullmatch(run) is None:
        raise _Refusal(f"run number {run!r} is not a positive integer without leading zeros")
    release = ref_match.group(1)
    sources = _sources(targets)
    for _name, source in sources:
        if source.version != release:
            raise _Refusal(f"{source.path.as_posix()}: version {source.version} is not the "
                           f"ref's {release}")
    for name, source in sources:
        if name in _STAMPED:
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


def _read_targets(argv: list[str]) -> int:
    if not argv:
        sys.exit(_USAGE)
    lines, refusals = [], []
    for target in argv:
        try:
            lines.append(f"{target}\t{_source(target)[1].version}\n")
        except _Refusal as refusal:
            refusals.append(f"{refusal}\n")
    if refusals:
        sys.stderr.write("".join(refusals))
        return 1
    sys.stdout.write("".join(lines))
    return 0


_SUBCOMMANDS = {"stamp": _stamp, "check": _check, "read": _read_targets}


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in _SUBCOMMANDS:
        sys.exit(_USAGE)
    try:
        return _SUBCOMMANDS[argv[1]](argv[2:])
    except _Refusal as refusal:
        sys.exit(str(refusal))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
