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

Repo-local rule: ``--dry-run`` writes NOTHING under ``--target``, and a
failure init can detect in validation (CR-MDB-033 §S1) is raised before
the first write. A failure DURING emission may leave a partial tree:
emission is not staged through a temp dir, so the ``init`` failure
envelope carries ``emitted`` -- the same field the success envelope uses
-- listing exactly the files written before the failure (CR-MDB-033 §S4).
Each file is itself written atomically (§S2). Stdlib only.
"""

import argparse
import datetime
import subprocess
import sys
from pathlib import Path

from modelb_axi import agents, requirements
from modelb_axi._fsutil import atomic_write
from modelb_axi.axi import envelope
from modelb_axi.config import INSTALL_TOML_NAME, _toml_string, load_install_toml
from modelb_axi.deploy import default_asset_root
from modelb_axi.harness import (
    HARNESS_ROSTER_IDS,
    UnknownHarnessError,
    parse_harnesses,
)
from modelb_axi.hooks import compile_wiring

# §S2 stack roster for --stacks validation.
KNOWN_STACKS: tuple[str, ...] = (
    "arduino", "bun", "python", "quarkus", "rust", "java",
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


# CR-MDB-025 §S6 — the committed `.env` key recording the project's stacks.
PROJECT_STACKS_KEY = "PROJECT_STACKS"


def resolve_harnesses(home: Path, dev_override: str | None) -> tuple[list[str], str]:
    """Resolve the installed harness set per the §S2 seam.

    Returns ``(harness_ids, source)`` where source names where the set
    came from. Raises :class:`ScaffoldError` when neither
    ``install.toml`` nor the ``--harnesses`` dev override supplies it,
    and :class:`UnknownHarnessError` for an id outside the roster from
    EITHER source (CR-MDB-033 §S5) — a stale ``install.toml`` id is
    rejected exactly like the dev override, in validation, before any
    write.
    """
    installed = load_install_toml(home).get("install", {}).get("harnesses")
    if installed:
        installed_ids = [str(h) for h in installed]
        _reject_unknown_harnesses(installed_ids)
        return installed_ids, "install.toml"
    requested = parse_harnesses(dev_override)
    if requested:
        _reject_unknown_harnesses(requested)
        return requested, "--harnesses (dev override)"
    raise ScaffoldError(
        f"no install.toml under {home} and no --harnesses given; init "
        "never guesses the installed harness set — run the installer "
        "(which writes install.toml) or pass the --harnesses dev override"
    )


def _reject_unknown_harnesses(harness_ids: list[str]) -> None:
    """Raise :class:`UnknownHarnessError` naming any id outside the roster."""
    unknown = [h for h in harness_ids if h not in HARNESS_ROSTER_IDS]
    if unknown:
        raise UnknownHarnessError(unknown)


def parse_stacks(raw: str) -> list[str]:
    """A ``--stacks`` CSV against :data:`KNOWN_STACKS` — shared by
    ``init``, ``agents`` and the installer (CR-MDB-036 §S7). An
    unsupported name raises :class:`ScaffoldError` listing the supported
    stacks."""
    # Duplicates collapse to the first occurrence, order kept (cycle-91
    # finding 10): a stack is recorded, probed and deployed once.
    stacks = list(dict.fromkeys(s.strip() for s in raw.split(",") if s.strip()))
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


def _render_env(
    name: str, token: str, acronym: str, mode: str, owner: str,
    stacks: list[str] | None = None,
) -> str:
    """The COMMITTED ``.env`` registry: all five keys (§S3.1), plus
    ``PROJECT_STACKS`` when ``stacks`` is given (CR-MDB-025 §S6 — the set
    ``modelb-axi agents`` re-renders from)."""
    text = (
        "# Project naming registry (CR-MDB-013 scaffold; committed).\n"
        f"PROJECT_NAME={name}\n"
        f"PROJECT_TOKEN={token}\n"
        f"PROJECT_ACRONYM={acronym}\n"
        f"ORCHESTRATOR_LABEL={_orchestrator_label(mode, token)}\n"
        f"REPO_OWNER={owner}\n"
    )
    if stacks:
        text += f"{PROJECT_STACKS_KEY}={','.join(stacks)}\n"
    return text


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
        # `.pi/` is NOT ignored: `.pi/extensions/` (compiled hook shims) and
        # `.pi/agents/` are tracked so every worktree carries them
        # (CR-MDB-030 §S6).
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
    notes — registrations are manual in scaffold v1), dated Notes
    footer."""
    today = datetime.date.today().isoformat()
    sandesh_task = (
        f"- [ ] Sandesh setup + register (`{name}`, `Mainline - {name}`) — "
        "manual step (registrations are manual in scaffold v1)\n"
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
        "(registrations are manual in scaffold v1)\n"
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


def _render_capability_contract(stacks: list[str]) -> str:
    """The §S6 capability contract, rendered from
    :mod:`modelb_axi.requirements` at call time (never hand-copied): one
    line per tier-1 capability and per selected stack's toolchain probe,
    each pairing the name with its remediation. Unselected stacks are not
    mentioned."""
    lines = [
        f"- `{row['id']}` ({row['policy']}): `{row['remediation']}`"
        for row in requirements.REQUIREMENTS if row["tier"] == 1
    ]
    seen: set[str] = set()
    for stack in stacks:
        for probe in requirements.STACK_TOOLCHAINS.get(stack, ()):
            if probe["name"] in seen:
                continue
            seen.add(probe["name"])
            lines.append(
                f"- `{probe['name']}` ({stack} toolchain): {probe['remediation']}"
            )
    return (
        "## Harness capability contract (from the installation's requirements)\n"
        "Each line names what this project's assets need and how to provide "
        "it when missing.\n"
        + "\n".join(lines) + "\n"
    )


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
        "- Registrations are manual in scaffold v1 — complete the "
        "manual setup tasks in the queue README.\n"
        "\n"
        f"## Skill freeze (derived from --stacks: {', '.join(stacks)})\n"
        f"{stack_lines}\n"
        "\n"
        f"## Harness anchors (installed set: {', '.join(harnesses)})\n"
        + "\n".join(anchor_lines) + "\n"
        "\n"
        + _render_capability_contract(stacks)
        + "\n"
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


# CR-MDB-015 §S5 hook-selection table (stack/mode-derived). Pinned rows
# (CR text + the C3 RED tests): the cargo guard iff a rust stack; the mvn
# guard iff a java/quarkus stack; the worktree + CR-completion guards iff
# multi mode; ambient-board-status always. Unpinned row — this slice's
# documented choice: `post-regression-disk-reminder` is a stack-neutral AND
# mode-neutral workflow-hygiene hook (the post-regression disk reminder
# applies to solo and multi projects alike), so it is emitted ALWAYS.
#
# matcher vocabulary: every matcher names the NEUTRAL tool class of
# hooks-src/schema.md (`bash`, `write|edit`), never a harness's own tool
# name (CR-MDB-030 §S4).
#
# fail_direction choice: every scaffold-emitted security-class (block-*)
# guard is `closed` (CR-MDB-030 §S6) — Pi, the primary harness, honours it.
# The fail-open-only harnesses (claude-code, hermes) refuse closed hooks,
# so they wire no block-* guard; hooks/README.md reports each refusal.


def _hook_instances(stacks: list[str], mode: str) -> list[dict]:
    """Neutral-schema (v1) hook instances for this project's stack/mode
    selection, per the table above."""
    instances: list[dict] = [
        {
            "event": "session-start",
            "command": "ambient-board-status",
            "tier": "core",
            "timeout": 10,
        },
        {
            "event": "post-tool-use",
            "matcher": "bash",
            "command": "post-regression-disk-reminder",
            "tier": "core",
        },
    ]
    if "rust" in stacks:
        instances.append({
            "event": "pre-tool-use",
            "matcher": "bash",
            "command": "block-direct-cargo-test",
            "tier": "core",
            "fail_direction": "closed",
        })
    if {"java", "quarkus"} & set(stacks):
        instances.append({
            "event": "pre-tool-use",
            "matcher": "bash",
            "command": "block-direct-mvn-test",
            "tier": "core",
            "fail_direction": "closed",
        })
    if mode != "solo":
        instances.append({
            "event": "pre-tool-use",
            "matcher": "write|edit",
            "command": "block-write-outside-worktree",
            "tier": "core",
            "fail_direction": "closed",
        })
        instances.append({
            "event": "pre-tool-use",
            "matcher": "bash",
            "command": "block-cr-completed-without-spec-update",
            "tier": "core",
            "fail_direction": "closed",
        })
    return instances


#: Instance-TOML field order (schema.md v1 field listing).
_INSTANCE_FIELD_ORDER = (
    "event", "matcher", "command", "tier", "timeout", "fail_direction",
)


def _render_instance_toml(instance: dict) -> str:
    """One neutral-schema instance as TOML. String values go through
    ``config._toml_string`` — the package's one TOML string writer
    (CR-MDB-033 §S5) — so any quote, backslash or control character
    is escaped; ints are written bare."""
    lines = [
        "# Generated by `modelb-axi init` (CR-MDB-015 §S5) — neutral hook",
        "# schema v1 (see the installation's hooks-src/schema.md).",
    ]
    for field in _INSTANCE_FIELD_ORDER:
        value = instance.get(field)
        if value is None:
            continue
        if isinstance(value, int):
            lines.append(f"{field} = {value}")
        else:
            lines.append(f"{field} = {_toml_string(str(value))}")
    return "\n".join(lines) + "\n"


def _hook_scripts_root(home: Path) -> Path:
    """Scripts root the compiled wiring points its commands at (§S5).

    Called ONCE, from :func:`run_init`'s validation phase — before the
    first write under ``--target`` and on ``--dry-run`` too (CR-MDB-033
    §S1) — so a failure init can know in advance never leaves a partial
    tree and is never previewed as a clean plan.

    Documented choice: commands target the DEPLOYED user-scope store
    (`<target-root>/.agents/hooks/scripts/…`, CR-MDB-015 §S6/PRD D10.7)
    — the one location the installer manifests the protocol scripts to —
    never a per-project copy (none exists) and never the repo checkout.
    The directory is read DIRECTLY from ``install.toml
    [install].hooks_scripts_dir``, the one place the installer records
    where it deployed the scripts (CR-MDB-033 §S1) — the scaffold never
    re-derives it. When that key is absent there is no fallback to
    ``Path.home()`` and no partial-key heuristic: :class:`ScaffoldError`
    is raised naming the missing key and ``modelb-axi --reinstall``, the
    run that records it. When no ``install.toml`` exists at ``home`` at
    all (the ``--harnesses`` dev-override path) a DISTINCT
    :class:`ScaffoldError` says so and names the installer as the
    remedy — no hook scripts have been deployed anywhere. The two cases
    are told apart by whether the file exists, never by which keys are
    present. Read-only — nothing is ever written there by the scaffold."""
    install_toml = home / INSTALL_TOML_NAME
    if not install_toml.is_file():
        raise ScaffoldError(
            f"no install.toml exists at {home}, so no hook scripts have "
            "been deployed anywhere for init to wire; run the installer "
            f"(`modelb-axi --modelb-home {home}`) first, then re-run init"
        )
    configured = load_install_toml(home).get("install", {}).get(
        "hooks_scripts_dir"
    )
    if not configured:
        raise ScaffoldError(
            f"{home / 'install.toml'} does not record "
            "[install].hooks_scripts_dir, so init cannot tell where the "
            "hook scripts were deployed; run `modelb-axi --reinstall` to "
            "record it, then re-run init"
        )
    return Path(str(configured)).expanduser()


def _render_hooks_readme(
    report: dict, instances: list[dict], harnesses: list[str],
) -> str:
    """`hooks/README.md` = the human-readable §S4 compiler report (§S5):
    per-harness accounting — emitted files, wired hooks, refusals with
    reasons, declared degradations — nothing silent."""
    lines = [
        "# hooks — compiler report",
        "",
        "Generated by `modelb-axi init` (CR-MDB-015 §S5): neutral-schema",
        "instances under `hooks/instances/*.toml`, compiled per installed",
        "harness by the §S4 compiler. Regenerate by re-running the compiler —",
        "never hand-edit the compiled wiring.",
        "",
        "## Neutral-schema instances (stack/mode-derived)",
        "",
    ]
    for instance in instances:
        lines.append(
            f"- `{instance['command']}` (event: {instance['event']})"
        )
    lines += ["", "## Per-harness accounting", ""]
    for harness in harnesses:
        entry = report.get(harness)
        lines.append(f"### {harness}")
        lines.append("")
        if entry is None:
            lines.append(
                "- not in the compiler's harness roster — no wiring emitted."
            )
            lines.append("")
            continue
        refused = {r["command"] for r in entry["refusals"]}
        wired = [i["command"] for i in instances if i["command"] not in refused]
        if wired:
            lines.append(f"- wired hooks: {', '.join(wired)}")
        if entry["emitted_files"]:
            lines.append(
                f"- emitted files: {', '.join(entry['emitted_files'])}"
            )
        for refusal in entry["refusals"]:
            lines.append(
                f"- REFUSED `{refusal['command']}`: {refusal['reason']}"
            )
        if entry["degraded"]:
            lines.append("- DEGRADED (declared):")
        for note in entry["notes"]:
            lines.append(f"  - {note}" if entry["degraded"] else f"- {note}")
        lines.append("")
    return "\n".join(lines)


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


def _agent_sources(home: Path) -> tuple[Path, Path]:
    """Asset-root resolution for the agent templates + stack TOMLs
    (CR-MDB-025 §S6), the same chain as :func:`_memory_templates_dir`:
    ``install.toml [install].asset_root`` → :func:`default_asset_root`.
    Returns ``(templates_dir, stacks_dir)``."""
    candidates: list[Path] = []
    configured = load_install_toml(home).get("install", {}).get("asset_root")
    if configured:
        candidates.append(Path(str(configured)))
    candidates.append(default_asset_root())
    for root in candidates:
        templates = root / "generator" / "templates"
        stacks = root / "generator" / "stacks"
        if templates.is_dir() and stacks.is_dir():
            return templates, stacks
    raise ScaffoldError(
        "no generator/templates + generator/stacks found under any asset "
        "root; tried: " + ", ".join(str(c) for c in candidates)
    )


def _renders_agents(harnesses: list[str]) -> bool:
    """True when any harness has a project agent directory + emitter."""
    return any(h in agents.PROJECT_AGENT_DIRS for h in harnesses)


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
    hook_scripts_root: Path | None,
    emitted: list[str] | None = None,
    agent_sources: tuple[Path, Path] | None = None,
) -> list[str]:
    """Perform the real §S3/§S4 emission under ``target``; returns the
    emitted file paths (relative to ``target``).

    ``hook_scripts_root`` is resolved by :func:`run_init` during
    validation (CR-MDB-033 §S1) — ``None`` only when no roster harness
    needs compiled wiring; emission never resolves it itself.

    ``emitted`` is an optional caller-owned out-list, appended to only
    AFTER each write succeeds, so the caller still holds exactly the
    files written when emission raises (CR-MDB-033 §S4). It is passed
    through to :func:`compile_wiring` as its ``emitted`` out-list, so
    compiled wiring files are recorded per write (not after the compiler
    returns) and each appears exactly once.

    ``agent_sources`` is the ``(templates_dir, stacks_dir)`` pair resolved
    by :func:`run_init` during validation (CR-MDB-025 §S6); ``None``
    renders no agent definitions."""
    if emitted is None:
        emitted = []

    def write(rel: str, text: str) -> None:
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(path, text.encode("utf-8"))
        emitted.append(rel)

    templates = _select_memory_templates(_memory_templates_dir(home), stacks)
    target.mkdir(parents=True, exist_ok=True)
    label = _orchestrator_label(mode, token)

    # §S3.1 registry + §S3.5 .gitignore.
    write(".env", _render_env(name, token, acronym, mode, owner, stacks))
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

    # §S3.7 hooks seam — filled by CR-MDB-015 §S5: stack/mode-derived
    # neutral-schema instances + compiled wiring for the installed harness
    # set + the compiler report as hooks/README.md.
    instances = _hook_instances(stacks, mode)
    for instance in instances:
        write(
            f"hooks/instances/{instance['command']}.toml",
            _render_instance_toml(instance),
        )
    roster_harnesses = [h for h in harnesses if h in HARNESS_ROSTER_IDS]
    report: dict = {}
    if roster_harnesses and hook_scripts_root is not None:
        report = compile_wiring(
            instances, roster_harnesses, target, hook_scripts_root,
            emitted=emitted,
        )
    write("hooks/README.md", _render_hooks_readme(report, instances, harnesses))

    # CR-MDB-025 §S6: the project's agent definitions, per installed
    # harness with an emitter; a stack with no stack TOML renders none.
    if agent_sources is not None:
        agent_report: dict = {}
        try:
            agents.render_project(
                target, stacks, harnesses, *agent_sources, report=agent_report,
            )
        finally:
            emitted.extend(agent_report.get("written", []))

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
        # Honest no-op (VERIFY F1): --register parses (surface stable)
        # but live registration ships in a later version — fail fast
        # BEFORE any emission rather than silently doing nothing.
        if getattr(args, "register", False):
            raise ScaffoldError(
                "--register: live registration is not implemented in "
                "scaffold v1 — run without --register and perform the "
                "manual registration steps the scaffold emits"
            )
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
        stacks = parse_stacks(args.stacks)
        sub_projects = _sub_projects(args.repo_shape)
    except (ScaffoldError, UnknownHarnessError) as exc:
        print(f"modelb-axi: error: {exc}", file=sys.stderr)
        print(envelope("init", False, warnings=[str(exc)], dry_run=dry_run))
        return 2

    target = Path(args.target).expanduser()
    plan = plan_files(sub_projects)
    print(f"  harnesses ({harness_source}): {', '.join(harnesses)}", file=sys.stderr)
    print(f"  plan: {len(plan)} files under {target}", file=sys.stderr)

    # CR-MDB-033 §S1: the hook-scripts dir is resolved here, in
    # validation, BEFORE the first write — a failure init can know in
    # advance never leaves a partial tree. --dry-run runs the same check
    # and carries the error text as a warning, so an unemittable plan is
    # never previewed as clean.
    plan_warnings: list[str] = []
    hook_scripts_root: Path | None = None
    if any(h in HARNESS_ROSTER_IDS for h in harnesses):
        try:
            hook_scripts_root = _hook_scripts_root(home)
        except ScaffoldError as exc:
            if not dry_run:
                print(f"modelb-axi: error: {exc}", file=sys.stderr)
                print(envelope("init", False, warnings=[str(exc)], dry_run=False))
                return 2
            print(f"modelb-axi: warning: {exc}", file=sys.stderr)
            plan_warnings.append(str(exc))

    # CR-MDB-025 §S6: the agent templates + stack TOMLs are resolved in
    # validation too, under the same dry-run/abort rule as above.
    agent_sources: tuple[Path, Path] | None = None
    if _renders_agents(harnesses):
        try:
            agent_sources = _agent_sources(home)
        except ScaffoldError as exc:
            if not dry_run:
                print(f"modelb-axi: error: {exc}", file=sys.stderr)
                print(envelope("init", False, warnings=[str(exc)], dry_run=False))
                return 2
            print(f"modelb-axi: warning: {exc}", file=sys.stderr)
            plan_warnings.append(str(exc))

    emitted: list[str] = []
    if not dry_run:
        try:
            _emit_plan(
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
                hook_scripts_root=hook_scripts_root,
                emitted=emitted,
                agent_sources=agent_sources,
            )
        except (ScaffoldError, OSError) as exc:
            # CR-MDB-033 §S4: a mid-emission failure may leave a partial
            # tree; `emitted` lists exactly the files written before it.
            print(f"modelb-axi: error: {exc}", file=sys.stderr)
            print(envelope(
                "init", False, warnings=[str(exc)], dry_run=False,
                emitted=emitted,
            ))
            return 3
        print(
            "  note: registrations are manual in scaffold v1 — steps "
            "recorded in docs/changes/README.md setup tasks",
            file=sys.stderr,
        )

    print(
        envelope(
            "init", True,
            warnings=plan_warnings,
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


def _read_env_value(env_path: Path, key: str) -> str | None:
    """The value of ``key`` in a ``KEY=VALUE`` registry file, or None."""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, _, value = stripped.partition("=")
        if name.strip() == key:
            return value.strip()
    return None


def _set_env_value(env_path: Path, key: str, value: str) -> bool:
    """Set ``key=value`` in a registry file, replacing an existing ``key``
    line in place or appending one; atomic. Returns False (and writes
    nothing) when the file already carries exactly that line."""
    lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True)
    new_line = f"{key}={value}\n"
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        if stripped.partition("=")[0].strip() == key:
            if line == new_line:
                return False
            lines[idx] = new_line
            break
    else:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.append(new_line)
    atomic_write(env_path, "".join(lines).encode("utf-8"))
    return True


def run_agents(args: argparse.Namespace, home: Path, project_root: Path | None = None) -> int:
    """Entry for the ``agents`` subcommand (CR-MDB-025 §S6): re-render the
    agent definitions of the project in the current directory from its
    ``PROJECT_STACKS``; ``--stacks`` changes the set and rewrites
    ``PROJECT_STACKS``. Emits one AXI envelope (verb ``agents``) on stdout
    listing written, unchanged, skipped and unmanaged files. Returns the
    process exit code."""
    print("modelb-axi: agents — re-render project agent definitions", file=sys.stderr)
    root = project_root if project_root is not None else Path.cwd()
    env_path = root / ".env"
    requested = getattr(args, "stacks", None)
    force_managed = bool(getattr(args, "force_managed", False))
    try:
        if not env_path.is_file():
            raise ScaffoldError(
                f"no .env in {root}; run `modelb-axi agents` from the root "
                "of a project scaffolded by `modelb-axi init`"
            )
        if requested:
            stacks = parse_stacks(requested)
        else:
            recorded = _read_env_value(env_path, PROJECT_STACKS_KEY)
            if not recorded:
                raise ScaffoldError(
                    f"{env_path} records no {PROJECT_STACKS_KEY}; pass "
                    "--stacks <csv> to render and record the project's stacks"
                )
            stacks = parse_stacks(recorded)
        harnesses, harness_source = resolve_harnesses(home, None)
        templates_dir, stacks_dir = _agent_sources(home)
    except (ScaffoldError, UnknownHarnessError) as exc:
        print(f"modelb-axi: error: {exc}", file=sys.stderr)
        print(envelope("agents", False, warnings=[str(exc)], project=str(root)))
        return 2

    print(f"  harnesses ({harness_source}): {', '.join(harnesses)}", file=sys.stderr)
    print(f"  stacks: {', '.join(stacks)}", file=sys.stderr)
    report: dict = {}
    try:
        agents.render_project(
            root, stacks, harnesses, templates_dir, stacks_dir,
            force_managed=force_managed, report=report,
        )
        if requested:
            _set_env_value(env_path, PROJECT_STACKS_KEY, ",".join(stacks))
    except OSError as exc:
        print(f"modelb-axi: error: {exc}", file=sys.stderr)
        print(envelope(
            "agents", False, warnings=[str(exc)], project=str(root), **report,
        ))
        return 3

    warnings: list[str] = []
    if not _renders_agents(harnesses):
        warnings.append(
            "no installed harness has an agent emitter; nothing rendered "
            f"(harnesses: {', '.join(harnesses)})"
        )
    for rel in report["skipped"]:
        warnings.append(
            f"skipping hand-modified managed file {rel} (marker hash "
            "mismatch; re-run with --force-managed to overwrite)"
        )
    for rel in report["unmanaged"]:
        warnings.append(
            f"unmanaged: {rel} — no Model B marker; left untouched (no "
            "flag overwrites it)"
        )
    for stack in report["no_definitions"]:
        warnings.append(f"stack {stack!r} has no agent definitions; none rendered")
    for message in warnings:
        print(f"modelb-axi: warning: {message}", file=sys.stderr)
    print(envelope(
        "agents", True,
        warnings=warnings,
        project=str(root),
        stacks=stacks,
        harnesses=harnesses,
        harness_source=harness_source,
        force_managed=force_managed,
        **report,
    ))
    return 0
