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
import datetime
import subprocess
import sys
from pathlib import Path

from modelb_axi.axi import envelope
from modelb_axi.config import load_install_toml
from modelb_axi.deploy import default_asset_root
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


def _orchestrator_label(mode: str, token: str) -> str:
    """Mode-aware orchestrator label (§S3.1): ``vidushi-<token>`` solo,
    ``Mainline-<token>`` multi."""
    return f"vidushi-{token}" if mode == "solo" else f"Mainline-{token}"


def _render_env(name: str, token: str, acronym: str, mode: str, owner: str) -> str:
    """The COMMITTED ``.env`` registry: all five keys (§S3.1)."""
    return (
        "# Project naming registry (CR-MDB-013 scaffold; committed).\n"
        f"PROJECT_NAME={name}\n"
        f"PROJECT_TOKEN={token}\n"
        f"PROJECT_ACRONYM={acronym}\n"
        f"ORCHESTRATOR_LABEL={_orchestrator_label(mode, token)}\n"
        f"REPO_OWNER={owner}\n"
    )


def _render_env_local() -> str:
    """The GITIGNORED ``.env.local``: tool-config placeholders (§S3.1)."""
    return (
        "# Local-only tool config (gitignored). Fill after registering the\n"
        "# project in Crucible — see the queue README setup tasks.\n"
        "CRUCIBLE_PROJECT_KEY=\n"
    )


def _render_gitignore() -> str:
    """``.gitignore`` incl. ``.env.local`` + harness caches (§S3.5)."""
    return (
        "# Local-only registry overlay — never committed.\n"
        ".env.local\n"
        "\n"
        "# Harness caches / local harness state.\n"
        ".claude/\n"
        ".opencode/\n"
        ".hermes/\n"
        ".pi/\n"
        "\n"
        "# Tooling debris.\n"
        "__pycache__/\n"
        "test-reports/\n"
    )


def _render_queue_readme(
    name: str, acronym: str, label: str, mode: str,
) -> str:
    """Queue template (§S3.2): four header slots, empty structure-only
    table, setup-tasks checklist (incl. the §S3.6 manual registration
    notes while ``--register`` is off), dated Notes footer."""
    today = datetime.date.today().isoformat()
    sandesh_task = (
        f"- [ ] Sandesh setup + register (`{name}`, `Mainline - {name}`) — "
        "manual step (`--register` was off at scaffold time)\n"
        if mode != "solo" else ""
    )
    return (
        f"# {name} — CR queue\n"
        "\n"
        f"**Project:** {name} (acronym: {acronym} · orchestrator: `{label}`) · "
        "**Design contract:** _fill in (`docs/research/PRD-….md`)_ · "
        "**Evidence base:** _fill in_ · "
        "**Ontology:** `crucible:docs/research/DN-model-b-language.md` · "
        "**Target release:** 0.1.0\n"
        "\n"
        "Queue rows enumerate the whole delivery (STRUCTURE only). Live "
        "status is DERIVED on the Crucible board (plans/cycles/milestones) — "
        "never hand-maintained here.\n"
        "\n"
        "## Queue\n"
        "\n"
        "| CR | Title | Wave | Depends on |\n"
        "|---|---|---|---|\n"
        "\n"
        "## Setup tasks (pre-wave — not a wave; a wave is a grouping of CRs)\n"
        "\n"
        f"- [x] Scaffold via `modelb-axi init` — {today}\n"
        "- [ ] Register the project in Crucible and paste the key into "
        "`.env.local` (`CRUCIBLE_PROJECT_KEY=`) — manual step "
        "(`--register` was off at scaffold time)\n"
        f"{sandesh_task}"
        "- [ ] Confirm the remote owner matches `REPO_OWNER` in `.env` "
        "before the first wave-boundary gate\n"
        "\n"
        "## Notes\n"
        "\n"
        f"- {today}: repository scaffolded by `modelb-axi init`.\n"
    )


_HARNESS_NATIVE_NOTES: dict[str, str] = {
    # DN-harness-agnostic-hooks §2 supplies no concrete project-config
    # anchor for these three — each reads AGENTS.md natively, so the
    # scaffold emits NO anchor file and notes that fact here (§S3.3).
    "hermes": (
        "- hermes: reads `AGENTS.md` natively — no separate anchor file "
        "emitted."
    ),
    "pi": (
        "- pi (pi.dev): reads `AGENTS.md` natively — no separate anchor "
        "file emitted."
    ),
    "opencode": (
        "- opencode: reads `AGENTS.md` natively — no separate anchor file "
        "emitted."
    ),
}


def _render_agents_md(
    name: str, token: str, acronym: str, mode: str, owner: str,
    stacks: list[str], harnesses: list[str],
) -> str:
    """Project ``AGENTS.md`` override (§S3.3/§S3.8): identity from the
    registry, workflow rules (incl. the post-036 run-context note —
    workflow cycle env vars are never hand-set, and this file must not
    name them), stack-derived skill freeze, per-installed-harness anchor
    notes, and the generator note."""
    label = _orchestrator_label(mode, token)
    stack_lines = "\n".join(
        f"- {stack}: use the `{stack}` stack skills and generated "
        f"RED/GREEN/VERIFY/FIX agents as frozen at scaffold time."
        for stack in stacks
    )
    anchor_lines = []
    if "claude-code" in harnesses:
        anchor_lines.append(
            "- claude-code: `CLAUDE.md` symlink → `AGENTS.md` (emitted by "
            "the scaffold)."
        )
    anchor_lines += [
        _HARNESS_NATIVE_NOTES[h] for h in harnesses if h in _HARNESS_NATIVE_NOTES
    ]
    return (
        f"# {name} — project AGENTS.md\n"
        "\n"
        "Project-level conventions for every session/agent working this "
        "repo. Scaffolded by `modelb-axi init`.\n"
        "\n"
        "## Identity & naming (registry: `.env` at the project root)\n"
        f"- Project **{name}** · token `{token}` · acronym `{acronym}` · "
        f"owner `{owner}`.\n"
        f"- Orchestrator label: `{label}` (mode: {mode}; mode-aware — "
        "solo `vidushi-<token>`, multi `Mainline-<token>`).\n"
        f"- CR ids: `CR-{acronym}-NNN`. Crucible agentIds follow the stack "
        "client's agent-naming header — never improvised.\n"
        "\n"
        "## Workflow rules\n"
        "- A **wave** is a grouping of CRs marking an execution boundary; "
        "setup tasks and releases are NOT waves.\n"
        "- Queue (`docs/changes/README.md`) holds STRUCTURE only; live "
        "status is DERIVED on the Crucible board.\n"
        "- Run context (post-036): workflow cycle context is attached by "
        "the tooling at ingest time — never hand-export cycle identifiers "
        "into the environment or into this file.\n"
        "- Registrations were NOT performed at scaffold time "
        "(`--register` off) — complete the manual setup tasks in the "
        "queue README.\n"
        "\n"
        f"## Skill freeze (derived from --stacks: {', '.join(stacks)})\n"
        f"{stack_lines}\n"
        "\n"
        f"## Harness anchors (installed set: {', '.join(harnesses)})\n"
        + "\n".join(anchor_lines) + "\n"
        "\n"
        "## Generator note\n"
        "- Agents regenerate from the INSTALLATION's generator assets — "
        "never from a per-project copy.\n"
    )


def _render_sub_agents_md(name: str, sub: str, token: str, acronym: str) -> str:
    """Per-sub-project ``AGENTS.md`` override (§S3 monorepo)."""
    return (
        f"# {name} / {sub} — sub-project AGENTS.md\n"
        "\n"
        f"Sub-project override for `{sub}/` (token `{token}`, acronym "
        f"`{acronym}`). Tools resolve THIS directory's `.env` registry — "
        "never the repo root's on this sub-project's behalf. Repo-wide "
        "conventions live in the root `AGENTS.md`.\n"
    )


def _render_hooks_readme() -> str:
    """Hooks seam note (§S3.7): wiring pending the CR-MDB-015 compiler,
    with the neutral-schema placeholder inline."""
    return (
        "# hooks — seam placeholder\n"
        "\n"
        "Hook wiring is pending the CR-MDB-015 compiler (harness-agnostic "
        "hooks: neutral schema + per-harness emitters + shared script "
        "protocol).\n"
        "\n"
        "Neutral-schema placeholder (compiled per harness by CR-MDB-015):\n"
        "\n"
        "```json\n"
        "{\n"
        '  "hooks": []\n'
        "}\n"
        "```\n"
    )


def _memory_templates_dir(home: Path) -> Path:
    """Asset-root resolution for ``memory-templates/`` (§S3.4):
    ``install.toml [install].asset_root`` → packaged ``modelb_axi/_assets``
    → repo checkout fallback (both via :func:`default_asset_root`)."""
    candidates: list[Path] = []
    configured = load_install_toml(home).get("install", {}).get("asset_root")
    if configured:
        candidates.append(Path(str(configured)))
    candidates.append(default_asset_root())
    for root in candidates:
        templates = root / "skills-src" / "memory-templates"
        if templates.is_dir():
            return templates
    raise ScaffoldError(
        "no memory-templates/ found under any asset root; tried: "
        + ", ".join(str(c) for c in candidates)
    )


def _select_memory_templates(templates_dir: Path, stacks: list[str]) -> list[Path]:
    """Filter templates by ``--stacks``: a ``<stack>-*.md`` template is
    emitted only when its stack is selected; stack-neutral templates
    (e.g. ``operational-commands.md``) are always emitted."""
    selected = []
    for path in sorted(templates_dir.glob("*.md")):
        prefix = path.name.split("-", 1)[0]
        if prefix in KNOWN_STACKS and prefix not in stacks:
            continue
        selected.append(path)
    return selected


def _render_memory_index(name: str, stacks: list[str], template_names: list[str]) -> str:
    lines = "\n".join(f"- [{n}]({n})" for n in template_names)
    return (
        f"# {name} — project memory index\n"
        "\n"
        "Seeded by `modelb-axi init` from the installation's "
        f"`memory-templates/` filtered by --stacks ({', '.join(stacks)}).\n"
        "\n"
        f"{lines}\n"
    )


def _git(target: Path, *args: str) -> None:
    """Run git under ``target`` with explicit identity config so commits
    work in bare CI environments (§S4)."""
    cmd = [
        "git", "-C", str(target),
        "-c", "user.email=modelb-axi@localhost",
        "-c", "user.name=modelb-axi",
        "-c", "commit.gpgsign=false",
        *args,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise ScaffoldError(
            f"git {' '.join(args)} failed under {target}: "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )


def _emit_plan(
    target: Path,
    *,
    name: str,
    token: str,
    acronym: str,
    mode: str,
    owner: str,
    stacks: list[str],
    harnesses: list[str],
    sub_projects: list[str],
    no_commit: bool,
    home: Path,
) -> list[str]:
    """Perform the real §S3/§S4 emission under ``target``; returns the
    emitted file paths (relative to ``target``)."""
    emitted: list[str] = []

    def write(rel: str, text: str) -> None:
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        emitted.append(rel)

    templates = _select_memory_templates(_memory_templates_dir(home), stacks)
    target.mkdir(parents=True, exist_ok=True)
    label = _orchestrator_label(mode, token)

    # §S3.1 registry + §S3.5 .gitignore.
    write(".env", _render_env(name, token, acronym, mode, owner))
    write(".env.local", _render_env_local())
    write(".gitignore", _render_gitignore())

    # §S3.2 docs model.
    write("docs/changes/README.md", _render_queue_readme(name, acronym, label, mode))
    write("docs/research/.gitkeep", "")

    # §S3.3 AGENTS.md + per-installed-harness anchors.
    write(
        "AGENTS.md",
        _render_agents_md(name, token, acronym, mode, owner, stacks, harnesses),
    )
    if "claude-code" in harnesses:
        (target / "CLAUDE.md").symlink_to("AGENTS.md")
        emitted.append("CLAUDE.md")

    # §S3.4 in-repo project memory.
    for template in templates:
        write(f"docs/memory/{template.name}", template.read_text(encoding="utf-8"))
    write(
        "docs/memory/INDEX.md",
        _render_memory_index(name, stacks, [t.name for t in templates]),
    )

    # §S3.7 hooks seam.
    write("hooks/README.md", _render_hooks_readme())

    # §S3 monorepo: per-sub-project registry + override.
    for sub in sub_projects:
        write(f"{sub}/.env", _render_env(name, token, acronym, mode, owner))
        write(f"{sub}/AGENTS.md", _render_sub_agents_md(name, sub, token, acronym))

    # §S3.5 git + §S4 one-commit policy.
    _git(target, "init", "-b", "master")
    if no_commit:
        # §S4: zero commits AND nothing staged — leave HEAD on an unborn
        # develop so a later hand-commit still lands per git-flow.
        _git(target, "symbolic-ref", "HEAD", "refs/heads/develop")
    else:
        # §S4: exactly the committed set — the emitted .gitignore's
        # `.env.local` pattern keeps the overlay out of the commit.
        _git(target, "add", "-A")
        _git(target, "commit", "-m", f"chore: scaffold {name} via modelb-axi init")
        _git(target, "checkout", "-b", "develop")
    return emitted


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

    emitted: list[str] = []
    if not dry_run:
        try:
            emitted = _emit_plan(
                target,
                name=args.name,
                token=args.token,
                acronym=args.acronym,
                mode=args.mode,
                owner=args.owner,
                stacks=stacks,
                harnesses=harnesses,
                sub_projects=sub_projects,
                no_commit=bool(getattr(args, "no_commit", False)),
                home=home,
            )
        except (ScaffoldError, OSError) as exc:
            print(f"modelb-axi: error: {exc}", file=sys.stderr)
            print(envelope("init", False, warnings=[str(exc)], dry_run=False))
            return 3
        if not getattr(args, "register", False):
            print(
                "  note: registrations skipped (--register off) — manual "
                "steps recorded in docs/changes/README.md setup tasks",
                file=sys.stderr,
            )

    print(
        envelope(
            "init", True,
            dry_run=dry_run,
            emitted=emitted,
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
