"""Command-line entrypoint for ``modelb-axi`` (CR-MDB-014 §S3).

State detection + adaptive TUI shell: resolve ``$MODELB_HOME``
(``--modelb-home`` flag > ``MODELB_HOME`` env > XDG data default), then
branch on the presence of ``install.toml`` there — absent enters the
INSTALLER flow (stage stubs in C1; pre-flight/deploy arrive in C2/C3),
present enters SCAFFOLD mode (v1 stub naming CR-MDB-013).

Stdlib only in C1; the rich-style prompt layer (DN §4) grows in C3.
"""

import argparse
import os
import sys
from pathlib import Path

from modelb_axi import __version__

INSTALL_TOML_NAME = "install.toml"

# Ordered installer-flow stages (§S3 shell). C1 ships announcements only;
# C2 fills pre-flight (§S4), C3 fills harness targeting + deploy (§S5/§S6).
_INSTALLER_STAGES = (
    ("pre-flight", "dependency checks (uv / Sandesh / Crucible) — arrives in C2"),
    ("harness targeting", "roster probe + selection — arrives in C3"),
    ("deploy", "manifest-driven asset deploy + install.toml write — arrives in C3"),
)


def _default_modelb_home() -> Path:
    """XDG default per DN §3: ``${XDG_DATA_HOME:-~/.local/share}/modelb``."""
    xdg_data_home = os.environ.get("XDG_DATA_HOME", "").strip()
    base = Path(xdg_data_home) if xdg_data_home else Path.home() / ".local" / "share"
    return base / "modelb"


def resolve_modelb_home(flag_value: str | None) -> Path:
    """Resolve MODELB_HOME with precedence flag > env > XDG default."""
    if flag_value:
        return Path(flag_value).expanduser()
    env_value = os.environ.get("MODELB_HOME", "").strip()
    if env_value:
        return Path(env_value).expanduser()
    return _default_modelb_home()


def _parse_harnesses(raw: str | None) -> list[str]:
    """Split a comma-separated ``--harnesses`` value into a clean list."""
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="modelb-axi",
        description=(
            "Model B universal installer / scaffold entrypoint. "
            "Adaptive: runs the installer flow when no install.toml exists "
            "under $MODELB_HOME, scaffold mode when one does."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"modelb-axi {__version__}",
    )
    parser.add_argument(
        "--yes", action="store_true",
        help="non-interactive mode: accept all defaults, never read stdin",
    )
    parser.add_argument(
        "--harnesses", metavar="LIST",
        help="comma-separated harness targets (e.g. claude-code,hermes)",
    )
    parser.add_argument(
        "--modelb-home", metavar="DIR",
        help="override $MODELB_HOME (default: ${XDG_DATA_HOME:-~/.local/share}/modelb)",
    )
    return parser


def _confirm(prompt: str, interactive: bool) -> bool:
    """Thin prompt seam (grows rich-style in C3). Only ever reads stdin
    when `interactive` is True — never under --yes or without a TTY."""
    if not interactive:
        return True
    answer = input(f"{prompt} [Y/n] ").strip().lower()
    return answer in ("", "y", "yes")


def _run_installer_flow(home: Path, harnesses: list[str], interactive: bool) -> int:
    """INSTALLER flow entry (§S3 shell): banner + ordered stage stubs."""
    print("modelb-axi: entering installer flow")
    print(f"  MODELB_HOME: {home} (no {INSTALL_TOML_NAME} found)")
    if harnesses:
        print(f"  harnesses requested: {', '.join(harnesses)}")
    if not _confirm("Proceed with installation?", interactive):
        print("modelb-axi: installer flow aborted by user")
        return 1
    total = len(_INSTALLER_STAGES)
    for index, (name, note) in enumerate(_INSTALLER_STAGES, start=1):
        print(f"  [stage {index}/{total}] {name}: {note}")
    print("modelb-axi: installer flow shell complete (C1 skeleton)")
    return 0


def _run_scaffold_stub(home: Path) -> int:
    """SCAFFOLD mode v1 stub (§S3): the scaffold flow is CR-MDB-013."""
    print("modelb-axi: scaffold mode")
    print(f"  {INSTALL_TOML_NAME} found under {home}")
    print("  the scaffold flow is CR-MDB-013's flow; this v1 stub only detects state")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    home = resolve_modelb_home(args.modelb_home)
    harnesses = _parse_harnesses(args.harnesses)
    interactive = not args.yes and sys.stdin.isatty()
    if (home / INSTALL_TOML_NAME).is_file():
        return _run_scaffold_stub(home)
    return _run_installer_flow(home, harnesses, interactive)


if __name__ == "__main__":
    sys.exit(main())
