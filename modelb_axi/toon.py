"""Model B's one hand-maintained TOON codec (CR-MDB-022 §S2/§S3).

``scripts/toon.py`` is GENERATED from this module by ``generator/build.py``
and is the self-contained copy that ships beside the deployed tooling (a
deployed ``worktree-flow.py`` runs under a bare ``python3`` that cannot reach
``modelb_axi``, so it cannot be a re-export). This file is the only place the
codec is edited.

Model B does NOT implement the TOON spec — the official ecosystem
(toonformat.dev / github.com/toon-format) does, and that spec, not any
private note, is the wire contract. This module ENCODES a documented, valid
SUBSET of it and DECODES what Model B's own tools emit. Conformance is
PROVEN rather than asserted: ``tests/test_toon_codec.py`` round-trips the
encoder's output through Crucible's spec-conformant port OUT OF PROCESS
(subprocess only, never an import). ``contracts/crucible-envelope.md``
records the subset and this quoting rule.

The subset emitted here:

    1. Scalar line          ``key: <scalar>``
    2. Nested object        ``key:`` + 2-space-indented child lines
    3. Empty array          ``key[0]:``
    4. Scalar array         ``key[N]: <item>,<item>`` — the canonical INLINE
       form a spec-conformant encoder emits. A ``[N]`` header followed by
       BARE indented items is NOT valid TOON: a conformant decoder counts an
       item line only when it starts with ``- ``, so bare items are read as
       zero items against a declared count.
    5. Uniform object table ``key[N]{col,…}:`` + one comma-joined row per item

QUOTING RULE — the wire rule and the type-preservation fix in one. A string
is written BARE only when it is non-empty, has no leading or trailing space,
is not ``true``/``false``/``null``, is not numeric-looking, holds none of
``:`` ``"`` ``\\`` ``[`` ``]`` ``{`` ``}``, no control character, not the
``,`` delimiter, and does not start with ``-`` or ``#``. Otherwise it is
JSON-quoted. So ``"4"``, ``"42"``, ``"true"``, ``"null"``, ``""`` and
``"  indented  "`` are all quoted and survive the round trip as the strings
they were, and the decoder never re-types a quoted scalar. A plain em dash
is not special and stays bare.

Stdlib only and self-contained by construction.
"""

import json
import re
from typing import Any

#: The only delimiter Model B emits (the spec default).
_DELIMITER = ","
_INDENT = "  "

_BOOL_NULL = frozenset({"true", "false", "null"})

#: EMIT test — deliberately WIDER than :data:`_NUMBER`: anything a decoder
#: could plausibly read as a number is quoted, so ``"+7"`` survives too.
_NUMERIC_LIKE = re.compile(r"[+-]?\d+(?:\.\d+)?(?:e[+-]?\d+)?", re.IGNORECASE)
#: DECODE test — exactly the JSON number literal a BARE token is promoted to.
_NUMBER = re.compile(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:e[+-]?\d+)?", re.IGNORECASE)
_CONTROL = re.compile(r"[\x00-\x1f]")

#: Characters that force a string to be quoted: structural or ambiguous.
_UNSAFE_BARE = ':"\\[]{}'

#: Array headers. Keys in this subset are plain identifiers, so the key group
#: excludes every structural character and the two patterns cannot collide.
_TABLE_HEADER = re.compile(r"([^:\[\]{}]+)\[(\d+)\]\{([^}]*)\}:")
_ARRAY_HEADER = re.compile(r"([^:\[\]{}]+)\[(\d+)\]:(.*)")

#: The canonical EMPTY array form a spec-conformant encoder emits. Model B
#: emits ``key[0]:`` instead (§S3/AC3 — the form its tooling has always
#: written), but decoding this one costs two lines and stops the codec
#: silently reading a conformant peer's empty array as the string "[]".
_EMPTY_ARRAY = "[]"


# ---------------------------------------------------------------------------
# encode
# ---------------------------------------------------------------------------
def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _is_safe_bare(value: str) -> bool:
    """The spec's unquoted-string rule."""
    if not value:
        return False
    if value[0] == " " or value[-1] == " ":
        return False
    if value in _BOOL_NULL or _NUMERIC_LIKE.fullmatch(value):
        return False
    if _CONTROL.search(value):  # tab, newline, carriage return and friends
        return False
    if any(char in value for char in _UNSAFE_BARE):
        return False
    if _DELIMITER in value:
        return False
    return not value.startswith(("-", "#"))


def _scalar_text(value: Any) -> str:
    if isinstance(value, bool):  # before int — bool subclasses int
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, str):
        # `ensure_ascii=False` matches the reference encoder, which escapes
        # only `\ " \n \r \t` and C0 controls; an em dash stays an em dash.
        return value if _is_safe_bare(value) else json.dumps(value, ensure_ascii=False)
    return str(value)


def _is_uniform_table(items: list) -> bool:
    """True when ``items`` is the uniform-object-table construct: plain
    objects sharing one order-identical, non-empty, scalar-only key set."""
    first = items[0]
    if not isinstance(first, dict):
        return False
    cols = list(first)
    if not cols:
        return False
    for item in items:
        if not isinstance(item, dict) or list(item) != cols:
            return False
        for col in cols:
            if not _is_scalar(item[col]):
                return False
    return True


def _encode_array(pad: str, key: str, items: list, lines: list) -> None:
    if not items:
        lines.append(f"{pad}{key}[0]:")
        return
    if _is_uniform_table(items):
        cols = list(items[0])
        lines.append(f"{pad}{key}[{len(items)}]{{{_DELIMITER.join(cols)}}}:")
        for row in items:
            cells = _DELIMITER.join(_scalar_text(row[col]) for col in cols)
            lines.append(f"{pad}{_INDENT}{cells}")
        return
    for item in items:
        if not _is_scalar(item):
            raise TypeError(
                f"TOON array '{key}' is outside the subset Model B emits: it "
                f"must hold scalars only, or plain objects sharing one "
                f"order-identical scalar key set; got "
                f"{type(item).__name__}"
            )
    lines.append(
        f"{pad}{key}[{len(items)}]: "
        f"{_DELIMITER.join(_scalar_text(item) for item in items)}"
    )


def _encode_into(obj: dict, indent: int, lines: list) -> None:
    pad = _INDENT * indent
    for key, value in obj.items():
        if _is_scalar(value):
            lines.append(f"{pad}{key}: {_scalar_text(value)}")
        elif isinstance(value, list):
            _encode_array(pad, key, value, lines)
        elif isinstance(value, dict):
            lines.append(f"{pad}{key}:")
            _encode_into(value, indent + 1, lines)
        else:
            raise TypeError(
                f"unsupported TOON value for '{key}': {type(value).__name__}"
            )


def encode(obj: dict) -> str:
    """Serialize ``obj`` to TOON text in the subset documented above."""
    if not isinstance(obj, dict):
        raise TypeError(
            f"encode expects a dict at the top level, got {type(obj).__name__}"
        )
    lines: list[str] = []
    _encode_into(obj, 0, lines)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# decode
# ---------------------------------------------------------------------------
def _parse_scalar(token: str) -> Any:
    """Type one wire token.

    The boundary trim is STRUCTURAL and matches the reference port exactly
    (``k: value  `` reads as ``"value"`` there too). Whitespace that MEANS
    something is inside the quotes the encoder put there, so it is never
    touched: a quoted token is JSON-decoded and NEVER promoted, which is what
    keeps ``"4"``, ``"42"``, ``"true"``, ``"null"``, ``""`` and
    ``"  indented  "`` the strings they were.
    """
    token = token.strip()
    if len(token) > 1 and token.startswith('"') and token.endswith('"'):
        return json.loads(token)
    if token == "true":
        return True
    if token == "false":
        return False
    if token == "null":
        return None
    if _NUMBER.fullmatch(token):
        return float(token) if any(char in token for char in ".eE") else int(token)
    return token


def _split_delimited(raw: str) -> list:
    """Split ``raw`` on delimiters that are not inside a JSON-quoted token."""
    tokens: list[str] = []
    start = index = 0
    length = len(raw)
    while index < length:
        char = raw[index]
        if char == '"':
            index += 1
            while index < length:
                if raw[index] == "\\":
                    index += 2
                    continue
                if raw[index] == '"':
                    index += 1
                    break
                index += 1
        elif char == _DELIMITER:
            tokens.append(raw[start:index])
            index += 1
            start = index
        else:
            index += 1
    tokens.append(raw[start:])
    return tokens


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _parse_table(lines: list, pos: list, base: int, header: re.Match) -> list:
    key, declared, cols_raw = header.group(1), int(header.group(2)), header.group(3)
    cols = cols_raw.split(_DELIMITER) if cols_raw else []
    pos[0] += 1
    rows: list[dict] = []
    row_indent = base + len(_INDENT)
    while pos[0] < len(lines) and _indent_of(lines[pos[0]]) >= row_indent:
        line = lines[pos[0]]
        cells = _split_delimited(line[_indent_of(line):])
        if len(cells) != len(cols):
            raise ValueError(
                f"TOON table row for '{key}' carries {len(cells)} cells, "
                f"expected {len(cols)} ({cols_raw})"
            )
        rows.append({col: _parse_scalar(cell) for col, cell in zip(cols, cells)})
        pos[0] += 1
    if len(rows) != declared:
        raise ValueError(
            f"TOON table '{key}' declares [{declared}] rows but carries {len(rows)}"
        )
    return rows


def _parse_array(lines: list, pos: list, base: int, header: re.Match) -> list:
    key, declared, tail = header.group(1), int(header.group(2)), header.group(3)
    pos[0] += 1
    inline = tail[1:] if tail.startswith(" ") else tail
    if inline.strip():
        items = [_parse_scalar(token) for token in _split_delimited(inline)]
    else:
        items = []
        item_indent = base + len(_INDENT)
        while pos[0] < len(lines) and _indent_of(lines[pos[0]]) >= item_indent:
            line = lines[pos[0]]
            content = line[_indent_of(line):]
            # `- item` is the spec's list form. A BARE item is the legacy form
            # the pre-CR-MDB-022 tooling emitted; it is still ACCEPTED here so
            # an older deployed copy's output stays readable, and it is never
            # WRITTEN any more (see `_encode_array`).
            items.append(_parse_scalar(content[2:] if content.startswith("- ") else content))
            pos[0] += 1
    if len(items) != declared:
        raise ValueError(
            f"TOON array '{key}' declares [{declared}] items but carries {len(items)}"
        )
    return items


def _parse_object(lines: list, pos: list, base: int) -> dict:
    obj: dict = {}
    while pos[0] < len(lines):
        line = lines[pos[0]]
        if _indent_of(line) < base:
            break
        content = line[_indent_of(line):]

        table = _TABLE_HEADER.fullmatch(content.rstrip())
        if table:
            obj[table.group(1)] = _parse_table(lines, pos, base, table)
            continue

        array = _ARRAY_HEADER.fullmatch(content)
        if array:
            obj[array.group(1)] = _parse_array(lines, pos, base, array)
            continue

        key, colon, rest = content.partition(":")
        if not colon:
            raise ValueError(
                f"TOON line {pos[0] + 1} is neither a key line nor an array "
                f"header: {line!r}"
            )
        trimmed = rest.strip()
        if trimmed == _EMPTY_ARRAY:
            obj[key] = []
            pos[0] += 1
        elif trimmed == "":
            # A `key:` header with an empty tail is a NESTED OBJECT, exactly
            # as the reference port reads it. An intentional empty STRING is
            # emitted QUOTED (`key: ""`), so the two are no longer confusable
            # in anything Model B writes.
            pos[0] += 1
            obj[key] = _parse_object(lines, pos, base + len(_INDENT))
        else:
            obj[key] = _parse_scalar(rest)
            pos[0] += 1
    return obj


def decode(text: str) -> dict:
    """Parse TOON text into a Python dict."""
    lines = [line for line in text.split("\n") if line.strip()]
    if not lines:
        return {}
    return _parse_object(lines, [0], 0)
