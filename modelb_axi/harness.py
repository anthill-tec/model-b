"""Harness targeting — installer-flow stage 2 (CR-MDB-014 §S5).

The initial harness roster (DN §5) maps stable harness ids to the binary
names probed on ``PATH``; the probed binary differs from the harness id
in exactly one case (``claude`` → ``claude-code``):

    claude-code ← ``claude``
    hermes      ← ``hermes``
    pi          ← ``pi``
    opencode    ← ``opencode``

Detection (``shutil.which`` against the current ``PATH`` — the tests'
isolation seam) proposes a default set; an explicit ``--harnesses``
selection wins outright. Unknown ids are rejected naming the valid
roster. Stdlib only.
"""

import re
import shutil

# Roster order is canonical: selections are always reported in this order.
HARNESS_ROSTER: tuple[tuple[str, str], ...] = (
    ("claude-code", "claude"),
    ("hermes", "hermes"),
    ("pi", "pi"),
    ("opencode", "opencode"),
)

HARNESS_ROSTER_IDS: tuple[str, ...] = tuple(hid for hid, _ in HARNESS_ROSTER)


class UnknownHarnessError(ValueError):
    """Raised when ``--harnesses`` names an id outside the roster."""

    def __init__(self, unknown: list[str]):
        self.unknown = unknown
        super().__init__(
            f"unknown harness id(s): {', '.join(unknown)}; "
            f"valid roster: {', '.join(HARNESS_ROSTER_IDS)}"
        )


def parse_harnesses(raw: str | None) -> list[str]:
    """Split a comma- and/or space-separated ``--harnesses`` value."""
    if not raw:
        return []
    return [item for item in re.split(r"[,\s]+", raw) if item]


def detect_harnesses() -> list[str]:
    """Probe the roster binaries on ``PATH``; return detected harness ids
    in roster order."""
    return [hid for hid, binary in HARNESS_ROSTER if shutil.which(binary)]


def select_harnesses(requested: list[str], detected: list[str]) -> list[str]:
    """Resolve the selected harness set (§S5): an explicit request wins
    outright over the detected set; the result is deduplicated and in
    roster order. Raises :class:`UnknownHarnessError` for ids outside
    the roster."""
    if requested:
        unknown = [hid for hid in requested if hid not in HARNESS_ROSTER_IDS]
        if unknown:
            raise UnknownHarnessError(unknown)
        return [hid for hid in HARNESS_ROSTER_IDS if hid in requested]
    return list(detected)
