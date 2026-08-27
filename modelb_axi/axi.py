"""Model B's own TOON AXI envelope emitter (CR-MDB-013 §S2).

Non-client-adopter shape per ``contracts/crucible-envelope.md``: every
scaffold verb emits exactly one ``{axi: {verb, ok, …result fields…,
warnings[]}}`` envelope on stdout with a FLATTENED context (flat fields
instead of the client ``context`` object — this tool performs no run
ingestion, so the classification object does not apply). The human
channel is stderr.

This module deliberately NEVER imports Crucible's ``clients/toon.py``. The
codec is Model B's own, ``modelb_axi.toon`` — the one hand-maintained
implementation in this repo (CR-MDB-022 §S2), which encodes a documented
valid subset of the OFFICIAL TOON spec (toonformat.dev /
github.com/toon-format). That spec is the wire contract: the note this
module used to cite as its authority, ``DN-crucible-toon-subset.md``, is
RETIRED (Crucible CR-CRU-046, 2026-08-01) and survives only as a pointer
at the official spec, so there is no private subset to be pinned against.
``contracts/crucible-envelope.md`` records what Model B emits.

Stdlib only.
"""

from modelb_axi.toon import encode


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
