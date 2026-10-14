"""Stamp a dev version for the release rehearsal (CR-MDB-067 §S1).

Usage: ``python3 .github/scripts/stamp_version.py <ref> <run-number>``, from the repository root.

Accepts a ref ``release/X.Y.Z`` or ``hotfix/X.Y.Z`` (each of ``X``, ``Y``, ``Z`` matching
``0|[1-9][0-9]*``) and a run number ``N`` matching ``[1-9][0-9]*``. When
``modelb_axi/__init__.py``'s ``__version__`` and ``pi-package/package.json``'s ``version`` are both
``X.Y.Z``, writes ``X.Y.Z.devN`` into the first and ``X.Y.Z-dev.N`` into the second — changing only
those two values, every other byte of both files unchanged — and prints ``X.Y.Z`` on stdout.

Otherwise exits 1 with one line on stderr, prints nothing on stdout and writes nothing: the line
names the ref, the run number, or the file with the version found and ``X.Y.Z``.

The release workflow's ``rehearse`` job runs it on every release or hotfix push. Repo-only: never
in the wheel or the sdist. Stdlib only, and no syntax newer than Python 3.12, the hosted runner's
default.
"""

import re
import sys
from pathlib import Path

INIT = "modelb_axi/__init__.py"
PACKAGE_JSON = "pi-package/package.json"

_NUMBER = r"(?:0|[1-9][0-9]*)"
_REF = re.compile(rf"(?:release|hotfix)/({_NUMBER}\.{_NUMBER}\.{_NUMBER})")
_RUN = re.compile(r"[1-9][0-9]*")
_INIT_VERSION = re.compile(r'^(__version__ = ")([^"]*)(")$', re.M)
_PACKAGE_VERSION = re.compile(r'^(\s*"version":\s*")([^"]*)(")', re.M)


def _read(path: str) -> str:
    """The file's text, decoded without newline translation so a rewrite keeps every byte."""
    return Path(path).read_bytes().decode("utf-8")


def _replace(text: str, pattern: re.Pattern, path: str, release: str, stamped: str) -> str:
    """``text`` with ``pattern``'s first version value set to ``stamped``; exits 1, naming
    ``path``, the version found and ``release``, unless that value is ``release``."""
    match = pattern.search(text)
    found = match.group(2) if match else "no version"
    if found != release:
        sys.exit(f"{path}: version {found} is not the ref's {release}")
    return text[:match.start(2)] + stamped + text[match.end(2):]


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        sys.exit("usage: stamp_version.py <ref> <run-number>")
    ref, run = argv[1], argv[2]
    ref_match = _REF.fullmatch(ref)
    if ref_match is None:
        sys.exit(f"ref {ref!r} is not release/X.Y.Z or hotfix/X.Y.Z")
    if _RUN.fullmatch(run) is None:
        sys.exit(f"run number {run!r} is not a positive integer without leading zeros")
    release = ref_match.group(1)
    init = _replace(_read(INIT), _INIT_VERSION, INIT, release, f"{release}.dev{run}")
    package = _replace(_read(PACKAGE_JSON), _PACKAGE_VERSION, PACKAGE_JSON, release,
                       f"{release}-dev.{run}")
    Path(INIT).write_bytes(init.encode("utf-8"))
    Path(PACKAGE_JSON).write_bytes(package.encode("utf-8"))
    sys.stdout.write(release + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
