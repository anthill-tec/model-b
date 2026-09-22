"""Command-line entrypoint for ``modelb-axi`` (CR-MDB-014 §S3/§S5/§S6).

State detection + adaptive TUI shell: resolve ``$MODELB_HOME``
(``--modelb-home`` flag > ``MODELB_HOME`` env > XDG data default), then
branch on the presence of ``install.toml`` there — absent enters the
INSTALLER flow (pre-flight → harness targeting → deploy + config
write), present enters SCAFFOLD mode (banner proposing ``init``) unless
``--reinstall`` forces the installer flow back on. The ``init``
subcommand (CR-MDB-013 §S2, ``modelb_axi.scaffold``) is the scaffold
flow itself and works in both states.

Stdlib only.
"""

import argparse
import os
import sys
from pathlib import Path

from modelb_axi import __version__
from modelb_axi.config import load_manifest_hashes, write_install_toml
from modelb_axi.deploy import (
    HOOKS_SCRIPTS_STORE_RELDIR,
    STORE_RELDIR,
    TOOL_SCRIPTS_STORE_RELDIR,
    DeployError,
    default_asset_root,
    deploy_assets,
)
from modelb_axi.harness import (
    UnknownHarnessError,
    detect_harnesses,
    parse_harnesses,
    select_harnesses,
)
from modelb_axi.preflight import run_preflight
from modelb_axi.scaffold import run_init

INSTALL_TOML_NAME = "install.toml"


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


def resolve_target_root(flag_value: str | None) -> Path | None:
    """Resolve the deploy target root: ``--target-root`` flag >
    ``MODELB_TARGET_ROOT`` env > ``None``.

    ``None`` means "not explicitly supplied": the DOCUMENTED default is
    the real user home (``Path.home()`` — the live ``~/.claude`` /
    ``~/.agents`` trees), but v1 only executes the deploy stage against
    an EXPLICIT target root. The C2 pre-flight contract pins that a run
    without ``--target-root`` writes neither deployed files nor
    ``install.toml`` (and the repo-local rule / AC7 guard forbids the
    test suite from ever touching the real trees), so the real-home
    default is deliberately never exercised by tests — deploying to it
    is deferred until the flow gains its own confirmation step."""
    if flag_value:
        return Path(flag_value).expanduser()
    env_value = os.environ.get("MODELB_TARGET_ROOT", "").strip()
    if env_value:
        return Path(env_value).expanduser()
    return None  # documented default: Path.home() — see docstring


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
        help="comma/space-separated harness targets (e.g. claude-code,hermes)",
    )
    parser.add_argument(
        "--modelb-home", metavar="DIR",
        help="override $MODELB_HOME (default: ${XDG_DATA_HOME:-~/.local/share}/modelb)",
    )
    parser.add_argument(
        "--target-root", metavar="DIR",
        help=(
            "root for deployed assets (.agents/skills store + per-harness "
            "skills dirs); default: the real user home"
        ),
    )
    parser.add_argument(
        "--reinstall", action="store_true",
        help="re-enter the installer flow even when install.toml exists",
    )
    parser.add_argument(
        "--force-managed", action="store_true",
        help="overwrite hand-modified managed files and refresh their manifest entries",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    _add_init_parser(subparsers)
    return parser


def _add_init_parser(subparsers) -> None:
    """The `init` subcommand — the scaffold flow (CR-MDB-013 §S2)."""
    init = subparsers.add_parser(
        "init",
        help="scaffold a Model B project under --target",
        description=(
            "Scaffold a Model B project: registry (.env), docs model, "
            "AGENTS.md + harness anchors for the installed set, in-repo "
            "memory, git+git-flow, and (opt-in) registrations."
        ),
    )
    init.add_argument("--name", metavar="NAME", help="project display name (registry)")
    init.add_argument("--token", metavar="TOKEN", help="project token (registry)")
    init.add_argument("--acronym", metavar="ACRO", help="project acronym (registry)")
    init.add_argument(
        "--mode", metavar="MODE", help="orchestration mode: solo | multi:<N>",
    )
    init.add_argument(
        "--repo-shape", metavar="SHAPE",
        help="repo shape: standalone | monorepo:<sub1,sub2,…>",
    )
    init.add_argument(
        "--stacks", metavar="CSV",
        help="stack csv: arduino,bun,python,quarkus,rust,vscode,java",
    )
    init.add_argument(
        "--harnesses", metavar="CSV", default=argparse.SUPPRESS,
        help=(
            "DEV-ONLY override of the installed harness set; the normal "
            "path reads install.toml under $MODELB_HOME"
        ),
    )
    init.add_argument("--owner", metavar="OWNER", help="REPO_OWNER registry value")
    init.add_argument("--target", metavar="DIR", help="project directory to scaffold into")
    init.add_argument(
        "--dry-run", action="store_true",
        help="validate + compute the plan; write NOTHING under --target",
    )
    init.add_argument(
        "--no-commit", action="store_true",
        help="skip the initial commit (leave the scaffold uncommitted)",
    )
    init.add_argument(
        "--register", action="store_true",
        help="perform Crucible/Sandesh registrations (default: emit manual-step notes)",
    )
    # Global flags accepted after the subcommand too; SUPPRESS keeps a
    # pre-subcommand value from being clobbered by a subparser default.
    init.add_argument(
        "--yes", action="store_true", default=argparse.SUPPRESS,
        help="non-interactive mode: accept all defaults, never read stdin",
    )
    init.add_argument(
        "--modelb-home", metavar="DIR", default=argparse.SUPPRESS,
        help="override $MODELB_HOME (default: ${XDG_DATA_HOME:-~/.local/share}/modelb)",
    )


def _confirm(prompt: str, interactive: bool) -> bool:
    """Thin prompt seam. Only ever reads stdin when `interactive` is
    True — never under --yes or without a TTY."""
    if not interactive:
        return True
    answer = input(f"{prompt} [Y/n] ").strip().lower()
    return answer in ("", "y", "yes")


def _select_harnesses_stage(requested: list[str], interactive: bool) -> list[str] | None:
    """Stage 2 (§S5): probe the roster, resolve the selection, print the
    machine-greppable ``harnesses selected:`` line. Returns None on a
    rejected selection (unknown id or user abort)."""
    print("  [stage 2/3] harness targeting: roster probe + selection")
    detected = detect_harnesses()
    try:
        selected = select_harnesses(requested, detected)
    except UnknownHarnessError as exc:
        print(f"modelb-axi: error: {exc}", file=sys.stderr)
        return None
    if not requested and not _confirm(
        f"Install for detected harnesses ({', '.join(selected) or 'none'})?",
        interactive,
    ):
        print("modelb-axi: installer flow aborted by user")
        return None
    print(f"harnesses selected: {', '.join(selected)}")
    return selected


def _deploy_stage(
    home: Path,
    target_root: Path,
    selected: list[str],
    deps_verdicts: dict[str, str],
    reinstall: bool,
    force_managed: bool,
) -> int:
    """Stage 3 (§S6): manifest-driven deploy, then the config write LAST
    — any deploy failure exits non-zero with NO install.toml written.

    ``reinstall`` no longer gates the manifest read (CR-MDB-033 §S3): the
    prior manifest is consulted whenever one exists under ``home``, so a
    deploy made without the flag cannot re-clobber a hand-modified
    managed file. The flag remains the CLI's state gate in :func:`main`.
    """
    asset_root = default_asset_root()
    # Manifest protection follows manifest PRESENCE, not a flag
    # (load_manifest_hashes returns {} when install.toml is absent).
    prior_hashes = load_manifest_hashes(home)
    unmanaged: list[str] = []
    try:
        manifest, skipped = deploy_assets(
            asset_root, target_root, selected,
            prior_hashes=prior_hashes, force_managed=force_managed,
            unmanaged=unmanaged,
        )
    except DeployError as exc:
        print(f"modelb-axi: error: {exc}", file=sys.stderr)
        return 1
    for rel in skipped:
        print(
            f"modelb-axi: warning: skipping hand-modified managed file "
            f"{rel} (hash mismatch; re-run with --force-managed to overwrite)",
            file=sys.stderr,
        )
    for rel in unmanaged:
        # CR-MDB-033 §S3: a file absent from the manifest is not Model
        # B's (DN §D3) — distinct vocabulary from the managed skip above,
        # and deliberately names NO flag: --force-managed adopts nothing.
        print(
            f"modelb-axi: warning: unmanaged: {target_root / rel} — not "
            f"Model B's; left untouched (no flag overwrites it)",
            file=sys.stderr,
        )
    write_install_toml(
        home,
        install={
            "version": __version__,
            "harnesses": selected,
            "asset_root": str(asset_root),
            # CR-MDB-033 §S1: the deployed root and its per-asset-class
            # dirs, recorded once here so the scaffold reads them instead
            # of re-deriving a second path rule from Path.home().
            "target_root": str(target_root),
            "skills_dir": str(target_root / STORE_RELDIR),
            "hooks_scripts_dir": str(target_root / HOOKS_SCRIPTS_STORE_RELDIR),
            # CR-MDB-022 §S4: where the adopted workflow tooling landed,
            # so a skill can name the script path without re-deriving it.
            "tool_scripts_dir": str(target_root / TOOL_SCRIPTS_STORE_RELDIR),
        },
        deps=deps_verdicts,
        files=manifest,
    )
    print(f"  wrote {home / INSTALL_TOML_NAME} ({len(manifest)} managed files)")
    return 0


def _run_installer_flow(
    home: Path,
    harnesses: list[str],
    interactive: bool,
    target_root: Path | None,
    reinstall: bool,
    force_managed: bool,
) -> int:
    """INSTALLER flow entry (§S3 shell): banner + ordered stages."""
    print("modelb-axi: entering installer flow")
    print(f"  MODELB_HOME: {home}")
    if harnesses:
        print(f"  harnesses requested: {', '.join(harnesses)}")
    if not _confirm("Proceed with installation?", interactive):
        print("modelb-axi: installer flow aborted by user")
        return 1
    # Stage 1 — dependency pre-flight (§S4). Runs (and reports its
    # `deps:` line) BEFORE any later stage announcement.
    print("  [stage 1/3] pre-flight: dependency checks (uv / Sandesh / Crucible)")
    preflight_exit, deps_verdicts = run_preflight(
        lambda prompt: _confirm(prompt, interactive)
    )
    if preflight_exit != 0:
        return preflight_exit
    # Stage 2 — harness targeting (§S5).
    selected = _select_harnesses_stage(harnesses, interactive)
    if selected is None:
        return 1
    # Stage 3 — deploy + config write (§S6): only executes against an
    # EXPLICIT target root — see resolve_target_root for why the
    # real-home default is deferred in v1.
    if target_root is not None:
        print("  [stage 3/3] deploy: manifest-driven asset deploy + install.toml write")
        deploy_exit = _deploy_stage(
            home, target_root, selected, deps_verdicts, reinstall, force_managed,
        )
        if deploy_exit != 0:
            return deploy_exit
    else:
        print(
            "  [stage 3/3] deploy: skipped — no --target-root/"
            "MODELB_TARGET_ROOT given (real-home deploy deferred in v1)"
        )
    print("modelb-axi: installer flow complete")
    return 0


def _run_scaffold_mode(home: Path) -> int:
    """SCAFFOLD-mode entry (CR-MDB-013 §S2): banner proposing `init`,
    non-interactive, never re-enters the installer flow."""
    print("modelb-axi: scaffold mode")
    print(f"  {INSTALL_TOML_NAME} found under {home}")
    print(
        "  scaffold flow (CR-MDB-013): run `modelb-axi init` to scaffold "
        "a Model B project (see `init --help`)"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    home = resolve_modelb_home(args.modelb_home)
    if getattr(args, "command", None) == "init":
        # The scaffold flow works in BOTH states (§S2).
        return run_init(args, home)
    harnesses = parse_harnesses(args.harnesses)
    target_root = resolve_target_root(args.target_root)
    interactive = not args.yes and sys.stdin.isatty()
    if (home / INSTALL_TOML_NAME).is_file() and not args.reinstall:
        return _run_scaffold_mode(home)
    return _run_installer_flow(
        home, harnesses, interactive, target_root,
        args.reinstall, args.force_managed,
    )


if __name__ == "__main__":
    sys.exit(main())
