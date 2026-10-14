"""Print one release's section of a Keep a Changelog file.

Usage: ``python3 .github/scripts/changelog_section.py <changelog> <tag>``

Prints the body of the section whose heading's bracketed label equals ``<tag>`` exactly: the lines
after that heading, up to the next ``## `` heading, the first ``[label]: url`` compare link, or the
end of the file, trimmed. Exits 1, naming the tag on stderr, when no section has that label or the
body holds nothing but whitespace and ``###`` headings — a ``###`` heading being a line that starts
with ``###`` followed by whitespace or the end of the line, so a bare ``###`` is one and a
``#### …`` line is content. Exits 1, naming the changelog's path and the tag on stderr, when the
changelog cannot be read.

The release workflow's ``create-release`` job writes this body to a file and passes it to
``gh release create --notes-file``. Rendered into the project by ``modelb-axi``; not part of the
``modelb_axi`` package. Stdlib only, and no syntax newer than Python 3.12, the hosted runner's
default.
"""

import re
import sys
from pathlib import Path

_HEADING = re.compile(r"## \[([^\]]+)\]")
_COMPARE_LINK = re.compile(r"\[[^\]]+\]: ")
_GROUP_HEADING = re.compile(r"###(\s|$)")


def section_body(text: str, tag: str) -> str | None:
    """The trimmed body of ``tag``'s section, or ``None`` when no section has that label."""
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        match = _HEADING.match(line)
        if match and match.group(1) == tag:
            start = index + 1
            break
    if start is None:
        return None
    body = []
    for line in lines[start:]:
        if line.startswith("## ") or _COMPARE_LINK.match(line):
            break
        body.append(line)
    return "\n".join(body).strip()


def _is_empty(body: str) -> bool:
    return all(not line.strip() or _GROUP_HEADING.match(line) for line in body.splitlines())


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        sys.exit("usage: changelog_section.py <changelog> <tag>")
    changelog, tag = Path(argv[1]), argv[2]
    try:
        text = changelog.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        sys.exit(f"{changelog}: cannot read the changelog for tag {tag}: {error}")
    body = section_body(text, tag)
    if body is None:
        sys.exit(f"{changelog}: no section for tag {tag}")
    if _is_empty(body):
        sys.exit(f"{changelog}: the section for tag {tag} is empty")
    sys.stdout.write(body + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
