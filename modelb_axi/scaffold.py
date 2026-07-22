"""Scaffold flow of the one ``modelb-axi`` binary (CR-MDB-013 §S2).

``modelb-axi init`` is the scaffold: it makes every rule this project
forged (registry, docs model, memory instantiation, git+git-flow,
registrations) correct-by-construction for a NEW project under
``--target``. Cycle C1 ships the entry + flag surface, the installed-
harness seam, validation, and the ``--dry-run`` plan; the real emission
(§S3/§S4 writes + the initial commit) is cycle C2 and fills
:func:`_emit_plan`.

Harness seam (DN-scaffold-packaging.md §3 / Q1): the installed harness
set is read from ``install.toml [install].harnesses`` under
``$MODELB_HOME`` — never re-asked per project. ``--harnesses`` is the
DEV-ONLY source when no ``install.toml`` exists; with neither, ``init``
refuses to guess and fails naming ``install.toml``.

Channels: stdout carries exactly one TOON AXI envelope
(``modelb_axi.axi``); ALL human progress goes to stderr.

Repo-local rule: ``--dry-run`` (and any failure) writes NOTHING under
``--target``. Stdlib only.
"""

import argparse
import sys
from pathlib import Path

from modelb_axi.axi import envelope
from modelb_axi.config import load_install_toml
from modelb_axi.harness import (
    HARNESS_ROSTER_IDS,
    UnknownHarnessError,
    parse_harnesses,
)

# §S2 stack roster for --stacks validation.
KNOWN_STACKS: tuple[str, ...] = (
    "arduino", "bun", "python", "quarkus", "rust", "vscode", "java",
)

# Registry/plan inputs every init needs (flag dest -> flag name).
_REQUIRED_FLAGS: tuple[tuple[str, str], ...] = (
    ("name", "--name"),
    ("token", "--token"),
    ("acronym", "--acronym"),
    ("mode", "--mode"),
    ("repo_shape", "--repo-shape"),
    ("stacks", "--stacks"),
    ("owner", "--owner"),
    ("target", "--target"),
)


class ScaffoldError(ValueError):
    """A validation failure that aborts ``init`` before any write."""


def resolve_harnesses(home: Path, dev_override: str | None) -> tuple[list[str], str]:
    """Resolve the installed harness set per the §S2 seam.

    Returns ``(harness_ids, source)`` where source names where the set
    came from. Raises :class:`ScaffoldError` when neither
    ``install.toml`` nor the ``--harnesses`` dev override supplies it.
    """
    installed = load_install_toml(home).get("install", {}).get("harnesses")
    if installed:
        return [str(h) for h in installed], "install.toml"
    requested = parse_harnesses(dev_override)
    if requested:
        unknown = [h for h in requested if h not in HARNESS_ROSTER_IDS]
        if unknown:
            raise UnknownHarnessError(unknown)
        return requested, "--harnesses (dev override)"
    raise ScaffoldError(
        f"no install.toml under {home} and no --harnesses given; init "
        "never guesses the installed harness set — run the installer "
        "(which writes install.toml) or pass the --harnesses dev override"
    )


def _parse_stacks(raw: str) -> list[str]:
    stacks = [s.strip() for s in raw.split(",") if s.strip()]
    unknown = [s for s in stacks if s not in KNOWN_STACKS]
    if unknown:
        raise ScaffoldError(
            f"unknown stack id(s): {', '.join(unknown)}; "
            f"valid stacks: {', '.join(KNOWN_STACKS)}"
        )
    if not stacks:
        raise ScaffoldError("--stacks must name at least one stack")
    return stacks


def _validate_mode(mode: str) -> None:
    if mode == "solo":
        return
    if mode.startswith("multi:") and mode.removeprefix("multi:").isdigit():
        return
    raise ScaffoldError(f"--mode must be solo or multi:<N>; got {mode!r}")


def _sub_projects(repo_shape: str) -> list[str]:
    """Sub-project dirs for the shape (empty for standalone)."""
    if repo_shape == "standalone":
        return []
    if repo_shape.startswith("monorepo:"):
        subs = [s.strip() for s in repo_shape.removeprefix("monorepo:").split(",") if s.strip()]
        if subs:
            return subs
    raise ScaffoldError(
        f"--repo-shape must be standalone or monorepo:<sub1,sub2,…>; got {repo_shape!r}"
    )


def plan_files(sub_projects: list[str]) -> list[str]:
    """Relative paths ``init`` will create under ``--target`` (§S3
    committed set + ``.env.local``); the C2 emission walks this plan."""
    base = [
        ".env",
        ".env.local",
        ".gitignore",
        "AGENTS.md",
        "docs/changes/README.md",
        "docs/research/.gitkeep",
        "docs/memory/INDEX.md",
        "hooks/README.md",
    ]
    for sub in sub_projects:
        base += [f"{sub}/.env", f"{sub}/AGENTS.md"]
    return base


def _emit_plan(target: Path, plan: list[str]) -> None:
    """C2 seam: perform the real §S3/§S4 emission under ``target``.

    Not implemented in C1 — only ``--dry-run`` is shipped; C2 fills
    this with the actual writes + git init + the initial commit.
    """
    raise NotImplementedError(
        "modelb-axi init emission lands in CR-MDB-013 C2; "
        "re-run with --dry-run to validate and preview the plan"
    )


def run_init(args: argparse.Namespace, home: Path) -> int:
    """Entry for the ``init`` subcommand. Returns the process exit code."""
    dry_run = bool(getattr(args, "dry_run", False))
    print("modelb-axi: init — scaffold flow", file=sys.stderr)
    try:
        harnesses, harness_source = resolve_harnesses(
            home, getattr(args, "harnesses", None),
        )
        missing = [
            flag for dest, flag in _REQUIRED_FLAGS
            if not getattr(args, dest, None)
        ]
        if missing:
            raise ScaffoldError(
                f"missing required value(s): {', '.join(missing)} "
                "(every setup query has a flag; supply them for a "
                "non-interactive run)"
            )
        _validate_mode(args.mode)
        stacks = _parse_stacks(args.stacks)
        sub_projects = _sub_projects(args.repo_shape)
    except (ScaffoldError, UnknownHarnessError) as exc:
        print(f"modelb-axi: error: {exc}", file=sys.stderr)
        print(envelope("init", False, warnings=[str(exc)], dry_run=dry_run))
        return 2

    target = Path(args.target).expanduser()
    plan = plan_files(sub_projects)
    print(f"  harnesses ({harness_source}): {', '.join(harnesses)}", file=sys.stderr)
    print(f"  plan: {len(plan)} files under {target}", file=sys.stderr)

    if not dry_run:
        # C1 ships validation + plan only; the emission is cycle C2.
        try:
            _emit_plan(target, plan)
        except NotImplementedError as exc:
            print(f"modelb-axi: error: {exc}", file=sys.stderr)
            print(envelope("init", False, warnings=[str(exc)], dry_run=False))
            return 3

    print(
        envelope(
            "init", True,
            dry_run=dry_run,
            name=args.name,
            token=args.token,
            acronym=args.acronym,
            mode=args.mode,
            repo_shape=args.repo_shape,
            owner=args.owner,
            target=str(target),
            stacks=stacks,
            harnesses=harnesses,
            harness_source=harness_source,
            no_commit=bool(getattr(args, "no_commit", False)),
            register=bool(getattr(args, "register", False)),
            planned=plan,
        )
    )
    return 0
