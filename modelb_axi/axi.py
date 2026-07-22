"""Model B's own TOON AXI envelope emitter (CR-MDB-013 §S2).

Non-client-adopter shape per ``contracts/crucible-envelope.md``: every
scaffold verb emits exactly one ``{axi: {verb, ok, …result fields…,
warnings[]}}`` envelope on stdout with a FLATTENED context (flat fields
instead of the client ``context`` object — this tool performs no run
ingestion, so the classification object does not apply). The human
channel is stderr.

This module deliberately NEVER imports Crucible's ``clients/toon.py``;
it is Model B's own emitter, wire-compatible with the pinned
4-construct TOON subset (DN-crucible-toon-subset.md) so any subset
decoder can parse the envelope. The constructs emitted here:

    1. Scalar line   ``key: val``
    2. Nested object ``key:`` + 2-space-indented child lines
    3. List array    ``key[N]:`` + one indented scalar line per item

The uniform-object-table construct is not needed by the envelope and is
not emitted. Stdlib only.
"""

import json
import re

# Scalar strings containing any of `\n : , { } [ ]` are JSON-quoted so
# a subset decoder tokenizes them back losslessly.
_SCALAR_SPECIALS = re.compile(r"[\n:,{}\[\]]")

_INDENT = "  "


def _is_scalar(value: object) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _scalar_text(value: object) -> str:
    if isinstance(value, str):
        return json.dumps(value) if _SCALAR_SPECIALS.search(value) else value
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    return str(value)


def _encode_into(obj: dict, indent: int, lines: list[str]) -> None:
    pad = _INDENT * indent
    for key, value in obj.items():
        if _is_scalar(value):
            lines.append(f"{pad}{key}: {_scalar_text(value)}")
        elif isinstance(value, list):
            bad = [item for item in value if not _is_scalar(item)]
            if bad:
                raise TypeError(
                    f"TOON list '{key}' may hold scalars only in the "
                    f"envelope subset; got {type(bad[0]).__name__}"
                )
            lines.append(f"{pad}{key}[{len(value)}]:")
            for item in value:
                lines.append(f"{pad}{_INDENT}{_scalar_text(item)}")
        elif isinstance(value, dict):
            lines.append(f"{pad}{key}:")
            _encode_into(value, indent + 1, lines)
        else:
            raise TypeError(
                f"unsupported TOON value for '{key}': {type(value).__name__}"
            )


def encode(obj: dict) -> str:
    """Serialize ``obj`` to TOON text (scalar / nested-object / scalar
    list constructs of the pinned subset)."""
    if not isinstance(obj, dict):
        raise TypeError(
            f"encode expects a dict at the top level, got {type(obj).__name__}"
        )
    lines: list[str] = []
    _encode_into(obj, 0, lines)
    return "\n".join(lines)


def envelope(verb: str, ok: bool, warnings: list[str] | None = None, **fields) -> str:
    """Build the ``{axi: {verb, ok, …fields…, warnings[]}}`` envelope.

    ``fields`` are the flattened, verb-specific result/context fields;
    ``warnings`` is always emitted (empty list when clean) per the
    contract's "always present" rule.
    """
    axi: dict = {"verb": verb, "ok": ok}
    axi.update(fields)
    axi["warnings"] = list(warnings) if warnings else []
    return encode({"axi": axi})
