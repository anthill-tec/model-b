# Owner: Model B (roundhouse/model-b) — adopted by CR-MDB-022 §S1.
# Consuming skills: none directly — imported by scripts/worktree-flow.py, which the
#   bootstrap, shutdown and model-b skills invoke.

# DEPLOYED COPY — source of truth crucible:clients/toon.py (TRACKS Crucible).
# Do not edit here; changes land upstream and re-deploy.

"""Fleet-shared Python TOON codec — the narrow 4-construct Crucible subset.

Ported construct-for-construct from `toToon()` in ``src/toon.ts`` and pinned
against the normative wire spec in ``docs/research/DN-crucible-toon-subset.md``.
It is deliberately NOT the full upstream ``@toon-format/toon`` grammar: no
delimiter variants, no key-path expansion, no inline primitive-array short form.

Public API:
    encode(obj) -> str    Python dict/list -> TOON text
    decode(text) -> obj   TOON text -> Python dict/list

The four constructs (mirroring the TS reference):
    1. Scalar line            ``key: val``
    2. Nested object          ``key:`` + 2-space-indented child lines
    3. Uniform object array   ``name[N]{col1,col2}:`` + comma-joined rows
    4. List array             ``name[N]:`` + one indented line per item
"""

from __future__ import annotations

import json
import re
from typing import Any

# Scalar strings containing any of `\n : , { } [ ]` are JSON-quoted.
_SCALAR_SPECIALS = re.compile(r"[\n:,{}\[\]]")
# Table cells containing any of `" , \n` are JSON-quoted.
_CELL_SPECIALS = re.compile(r'["\n,]')

# Header line grammar (keys in the subset are simple, colon/bracket-free).
_TABLE_HEADER = re.compile(r"^([^:\[\]{}]+)\[(\d+)\]\{([^}]*)\}:$")
_LIST_HEADER = re.compile(r"^([^:\[\]{}]+)\[(\d+)\]:$")
# A JSON number literal, used to decide when a bare token is numeric.
_NUMBER = re.compile(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?")

_INDENT = "  "


# ---------------------------------------------------------------------------
# encode
# ---------------------------------------------------------------------------
def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _is_plain_object(value: Any) -> bool:
    return isinstance(value, dict)


def _scalar_text(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value) if _SCALAR_SPECIALS.search(value) else value
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    return str(value)


def _cell_text(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value) if _CELL_SPECIALS.search(value) else value
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    return str(value)


def _is_uniform_table(items: list) -> bool:
    """Table form needs a non-empty array of plain objects sharing an
    identical, order-identical key-set with scalar-only values."""
    first = items[0]
    if not _is_plain_object(first):
        return False
    cols = list(first.keys())
    if not cols:
        return False
    for item in items:
        if not _is_plain_object(item):
            return False
        keys = list(item.keys())
        if len(keys) != len(cols):
            return False
        for i, key in enumerate(keys):
            if key != cols[i] or not _is_scalar(item[key]):
                return False
    return True


def _to_toon(obj: dict, indent: int = 0) -> str:
    pad = _INDENT * indent
    lines: list[str] = []
    for key, value in obj.items():
        if _is_scalar(value):
            lines.append(f"{pad}{key}: {_scalar_text(value)}")
        elif isinstance(value, list):
            if len(value) > 0 and _is_uniform_table(value):
                cols = list(value[0].keys())
                lines.append(f"{pad}{key}[{len(value)}]{{{','.join(cols)}}}:")
                for row in value:
                    cells = ",".join(_cell_text(row[col]) for col in cols)
                    lines.append(f"{pad}{_INDENT}{cells}")
            else:
                lines.append(f"{pad}{key}[{len(value)}]:")
                for item in value:
                    if _is_scalar(item):
                        lines.append(f"{pad}{_INDENT}{_scalar_text(item)}")
                    elif _is_plain_object(item):
                        block = _to_toon(item, indent + 1)
                        if block:
                            lines.append(block)
                    else:
                        lines.append(f"{pad}{_INDENT}{json.dumps(item)}")
        elif _is_plain_object(value):
            lines.append(f"{pad}{key}:")
            block = _to_toon(value, indent + 1)
            if block:
                lines.append(block)
    return "\n".join(lines)


def encode(obj: dict) -> str:
    """Serialize a Python dict to TOON text (the pinned 4-construct subset)."""
    if not isinstance(obj, dict):
        raise TypeError(f"encode expects a dict at the top level, got {type(obj).__name__}")
    return _to_toon(obj, 0)


# ---------------------------------------------------------------------------
# decode
# ---------------------------------------------------------------------------
def _parse_scalar(token: str) -> Any:
    """Un-quote / type a bare scalar token (scalar-line or table-cell context)."""
    if token.startswith('"'):
        return json.loads(token)
    if token == "true":
        return True
    if token == "false":
        return False
    if token == "null":
        return None
    if _NUMBER.fullmatch(token):
        if any(c in token for c in ".eE"):
            return float(token)
        return int(token)
    return token


def _split_cells(row: str) -> list[str]:
    """Split a table row on commas that are not inside a JSON-quoted cell."""
    cells: list[str] = []
    cur: list[str] = []
    i, n = 0, len(row)
    while i < n:
        c = row[i]
        if c == '"':
            j = i + 1
            while j < n:
                if row[j] == "\\":
                    j += 2
                    continue
                if row[j] == '"':
                    j += 1
                    break
                j += 1
            cur.append(row[i:j])
            i = j
        elif c == ",":
            cells.append("".join(cur))
            cur = []
            i += 1
        else:
            cur.append(c)
            i += 1
    cells.append("".join(cur))
    return cells


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _parse_object(lines: list[str], pos: list[int], base: int) -> dict:
    obj: dict = {}
    while pos[0] < len(lines):
        line = lines[pos[0]]
        if _indent_of(line) < base:
            break
        content = line.strip()

        table = _TABLE_HEADER.match(content)
        if table:
            key, declared, cols_raw = table.group(1), int(table.group(2)), table.group(3)
            cols = cols_raw.split(",") if cols_raw else []
            pos[0] += 1
            rows: list[dict] = []
            while pos[0] < len(lines) and _indent_of(lines[pos[0]]) > base:
                cells = _split_cells(lines[pos[0]].strip())
                if len(cells) != len(cols):
                    raise ValueError(
                        f"TOON table row for '{key}' has {len(cells)} cells, "
                        f"expected {len(cols)} ({','.join(cols)})"
                    )
                rows.append({col: _parse_scalar(cell) for col, cell in zip(cols, cells)})
                pos[0] += 1
            if len(rows) != declared:
                raise ValueError(
                    f"TOON table '{key}' declared [{declared}] rows but found {len(rows)}"
                )
            obj[key] = rows
            continue

        array = _LIST_HEADER.match(content)
        if array:
            key, declared = array.group(1), int(array.group(2))
            pos[0] += 1
            items: list[Any] = []
            while pos[0] < len(lines) and _indent_of(lines[pos[0]]) > base:
                items.append(_parse_scalar(lines[pos[0]].strip()))
                pos[0] += 1
            if len(items) != declared:
                raise ValueError(
                    f"TOON list '{key}' declared [{declared}] items but found {len(items)}"
                )
            obj[key] = items
            continue

        idx = content.find(":")
        key = content[:idx]
        rest = content[idx + 1:]
        if rest == "":
            pos[0] += 1
            obj[key] = _parse_object(lines, pos, base + 2)
        else:
            value = rest[1:] if rest.startswith(" ") else rest
            obj[key] = _parse_scalar(value)
            pos[0] += 1
    return obj


def decode(text: str) -> dict:
    """Parse TOON text (the pinned 4-construct subset) into a Python dict."""
    lines = [ln for ln in text.split("\n") if ln.strip() != ""]
    if not lines:
        return {}
    return _parse_object(lines, [0], 0)
