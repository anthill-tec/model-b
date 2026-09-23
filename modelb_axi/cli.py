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
from modelb_axi.axi import envelope
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
    """XDG default per DN-scaffold-packaging §3: ``${XDG_DATA_HOME:-~/.local/share}/modelb``."""
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
        help="stack csv: arduino,bun,python,quarkus,rust,java",
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


def _say(line: str) -> None:
    """One human progress line — always stderr; stdout is reserved for
    the installer's single AXI envelope (CR-MDB-033 §S6)."""
    print(line, file=sys.stderr)


def _warn(message: str, warnings: list[str], level: str = "warning") -> None:
    """Print a warning/error on stderr and record it, unprefixed, for the
    envelope's ``warnings`` field (CR-MDB-033 §S6)."""
    print(f"modelb-axi: {level}: {message}", file=sys.stderr)
    warnings.append(message)


def _emit_install_envelope(
    outcome: str, ok: bool, warnings: list[str], fields: dict,
) -> None:
    """Write the installer's one AXI envelope (verb ``install``) to
    stdout (CR-MDB-033 §S6)."""
    print(envelope("install", ok, warnings=warnings, outcome=outcome, **fields))


def _confirm(prompt: str, interactive: bool) -> bool:
    """Thin prompt seam. Only ever reads stdin when `interactive` is
    True — never under --yes or without a TTY. The prompt is written to
    stderr: stdout carries nothing but the envelope (CR-MDB-033 §S6)."""
    if not interactive:
        return True
    print(f"{prompt} [Y/n] ", end="", file=sys.stderr, flush=True)
    answer = input().strip().lower()
    return answer in ("", "y", "yes")


def _select_harnesses_stage(requested: list[str], interactive: bool) -> list[str] | None:
    """Stage 2 (§S5): probe the roster, resolve the selection, print the
    ``harnesses selected:`` line (stderr). Returns None when the user
    declines the detected set; an unknown id raises
    :class:`UnknownHarnessError` for the caller to report."""
    _say("  [stage 2/3] harness targeting: roster probe + selection")
    detected = detect_harnesses()
    selected = select_harnesses(requested, detected)
    if not requested and not _confirm(
        f"Install for detected harnesses ({', '.join(selected) or 'none'})?",
        interactive,
    ):
        _say("modelb-axi: installer flow aborted by user")
        return None
    _say(f"harnesses selected: {', '.join(selected)}")
    return selected


def _deploy_stage(
    home: Path,
    target_root: Path,
    selected: list[str],
    deps_verdicts: dict[str, str],
    reinstall: bool,
    force_managed: bool,
    *,
    warnings: list[str] | None = None,
    report: dict | None = None,
) -> int:
    """Stage 3 (§S6): manifest-driven deploy, then the config write LAST
    — any deploy failure exits non-zero with NO install.toml written.

    ``reinstall`` no longer gates the manifest read (CR-MDB-033 §S3): the
    prior manifest is consulted whenever one exists under ``home``, so a
    deploy made without the flag cannot re-clobber a hand-modified
    managed file. The flag remains the CLI's state gate in :func:`main`.

    ``warnings`` collects every warning/error printed; ``report``, on
    success, receives the envelope's install fields (``target_root``,
    ``install_toml``, ``managed_files``, ``skipped``, ``unmanaged`` —
    CR-MDB-033 §S6).
    """
    if warnings is None:
        warnings = []
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
        _warn(str(exc), warnings, level="error")
        return 1
    for rel in skipped:
        _warn(
            f"skipping hand-modified managed file {rel} (hash mismatch; "
            f"re-run with --force-managed to overwrite)",
            warnings,
        )
    for rel in unmanaged:
        # CR-MDB-033 §S3: a file absent from the manifest is not Model
        # B's (DN-multi-harness-deploy-model §D3) — distinct vocabulary
        # from the managed skip above, and deliberately names NO flag:
        # --force-managed adopts nothing.
        _warn(
            f"unmanaged: {target_root / rel} — not Model B's; left "
            f"untouched (no flag overwrites it)",
            warnings,
        )
    install_toml = write_install_toml(
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
    _say(f"  wrote {install_toml} ({len(manifest)} managed files)")
    if report is not None:
        report.update(
            target_root=str(target_root),
            install_toml=str(install_toml),
            managed_files=len(manifest),
            skipped=list(skipped),
            unmanaged=list(unmanaged),
        )
    return 0


def _run_installer_flow(
    home: Path,
    harnesses: list[str],
    interactive: bool,
    target_root: Path | None,
    reinstall: bool,
    force_managed: bool,
) -> int:
    """INSTALLER flow entry (§S3 shell): banner + ordered stages.

    Every exit path writes exactly one AXI envelope (verb ``install``)
    to stdout, with the path's ``outcome`` (CR-MDB-033 §S6); every human
    line goes to stderr."""
    warnings: list[str] = []
    fields: dict = {}
    _say("modelb-axi: entering installer flow")
    _say(f"  MODELB_HOME: {home}")
    if harnesses:
        _say(f"  harnesses requested: {', '.join(harnesses)}")
    if not _confirm("Proceed with installation?", interactive):
        _say("modelb-axi: installer flow aborted by user")
        _emit_install_envelope("aborted", False, warnings, fields)
        return 1
    # Stage 1 — dependency pre-flight (§S4). Runs (and reports its
    # `deps:` line) BEFORE any later stage announcement.
    _say("  [stage 1/3] pre-flight: dependency checks (uv / Sandesh / Crucible)")
    preflight_exit, deps_verdicts = run_preflight(
        lambda prompt: _confirm(prompt, interactive), warnings,
    )
    if preflight_exit != 0:
        _emit_install_envelope("preflight_failed", False, warnings, fields)
        return preflight_exit
    fields["deps"] = deps_verdicts
    # Stage 2 — harness targeting (§S5).
    try:
        selected = _select_harnesses_stage(harnesses, interactive)
    except UnknownHarnessError as exc:
        _warn(str(exc), warnings, level="error")
        _emit_install_envelope("harness_rejected", False, warnings, fields)
        return 1
    if selected is None:
        _emit_install_envelope("aborted", False, warnings, fields)
        return 1
    fields["harnesses"] = selected
    # Stage 3 — deploy + config write (§S6): only executes against an
    # EXPLICIT target root — see resolve_target_root for why the
    # real-home default is deferred in v1.
    if target_root is None:
        _say(
            "  [stage 3/3] deploy: skipped — no --target-root/"
            "MODELB_TARGET_ROOT given (real-home deploy deferred in v1)"
        )
        _say("modelb-axi: installer flow complete")
        _emit_install_envelope("deploy_skipped", True, warnings, fields)
        return 0
    _say("  [stage 3/3] deploy: manifest-driven asset deploy + install.toml write")
    report: dict = {}
    deploy_exit = _deploy_stage(
        home, target_root, selected, deps_verdicts, reinstall, force_managed,
        warnings=warnings, report=report,
    )
    if deploy_exit != 0:
        _emit_install_envelope("deploy_failed", False, warnings, fields)
        return deploy_exit
    fields.update(report)
    _say("modelb-axi: installer flow complete")
    _emit_install_envelope("installed", True, warnings, fields)
    return 0


def _run_scaffold_mode(home: Path) -> int:
    """SCAFFOLD-mode entry (CR-MDB-013 §S2): banner proposing `init`,
    non-interactive, never re-enters the installer flow. The banner is
    human prose on stderr; stdout carries the ``already_installed``
    envelope (CR-MDB-033 §S6)."""
    _say("modelb-axi: scaffold mode")
    _say(f"  {INSTALL_TOML_NAME} found under {home}")
    _say(
        "  scaffold flow (CR-MDB-013): run `modelb-axi init` to scaffold "
        "a Model B project (see `init --help`)"
    )
    _emit_install_envelope("already_installed", True, [], {})
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
