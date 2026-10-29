"""Scaffold flow of the one ``modelb-axi`` binary (CR-MDB-013 §S2).

``modelb-axi init`` is the scaffold: it makes every rule this project
forged (registry, docs model, stack skills, git+git-flow,
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
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tomllib
import unicodedata
from pathlib import Path

from modelb_axi import (
    agents,
    permission_policy,
    project_trust,
    requirements,
    stack_skills,
    workflows,
)
from modelb_axi._fsutil import atomic_write
from modelb_axi.axi import envelope
from modelb_axi.capabilities import resolve_agent_dir
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

# Plan inputs every init needs that are NOT registry keys (flag dest ->
# flag name); the registry's own required values come from the schema's
# ask+required keys (CR-MDB-043 §S2), inserted at the matching positions.
_PLAN_REQUIRED_FLAGS: tuple[tuple[str, str], ...] = (
    ("mode", "--mode"),
    ("repo_shape", "--repo-shape"),
    ("target", "--target"),
)

#: The packaged project-settings schema (CR-MDB-043 §S1), read by
#: :func:`run_init` and :func:`run_agents` at call time.
PROJECT_SCHEMA_PATH = Path(__file__).resolve().parent / "project_schema.toml"

#: Every declared requirement id — what a schema ``when`` may name, and
#: the keys of ``init``'s ``tools`` field (CR-MDB-045 §S2/§S3).
_REQUIREMENT_IDS: tuple[str, ...] = tuple(r["id"] for r in requirements.REQUIREMENTS)

#: ``init``'s tool states (CR-MDB-045 §S2), best to worst.
TOOL_PRESENT, TOOL_UNKNOWN, TOOL_ABSENT = "present", "unknown", "absent"
_PRESENT_VERDICTS = frozenset({"detected", "installed"})
#: Verdicts read as absent: ``outdated`` is a ``sandesh`` below its version
#: floor, reported like ``absent`` (CR-MDB-047 §S1).
_ABSENT_VERDICTS = frozenset({"absent", "outdated"})
_TOOL_RANK = {TOOL_PRESENT: 0, TOOL_UNKNOWN: 1, TOOL_ABSENT: 2}

#: A requirement id -> the key an older ``install.toml`` recorded its
#: verdict under: ``worktree`` was the ``watcher`` row before CR-MDB-047
#: §S1.
_LEGACY_KEYS: dict[str, str] = {"worktree": "watcher"}


def _tool_state(verdict) -> str:
    """One recorded verdict as a tool state: ``detected``/``installed`` are
    present, ``absent``/``outdated`` are absent, anything else (none) is
    unknown."""
    if verdict in _PRESENT_VERDICTS:
        return TOOL_PRESENT
    return TOOL_ABSENT if verdict in _ABSENT_VERDICTS else TOOL_UNKNOWN


def _recorded(capabilities: dict, deps: dict, key: str):
    """The verdict recorded for ``key``: ``[capabilities]``, else ``[deps]``,
    else its pre-rename key in ``[capabilities]`` (:data:`_LEGACY_KEYS`)."""
    verdict = capabilities.get(key, deps.get(key))
    if verdict is None and key in _LEGACY_KEYS:
        verdict = capabilities.get(_LEGACY_KEYS[key])
    return verdict


def read_tool_verdicts(install: dict, stacks: list[str]) -> tuple[dict, list[str]]:
    """The installation's recorded verdicts as ``init``'s ``tools`` map
    (CR-MDB-045 \u00a7S2) \u2014 read from a parsed ``install.toml``, never probed.

    An always-scoped row takes its ``[capabilities]`` verdict, else its
    ``[deps]`` one (uv, sandesh, crucible). A stack-scoped row takes the
    worst state over the project's stacks and each stack's probes:
    ``<stack>.client`` for ``crucible-client``, ``<stack>.<probe>`` for
    ``toolchain``. Returns ``(tools, unrecorded)``: ``unrecorded`` names
    each row with a verdict missing from ``install.toml``."""
    capabilities = install.get("capabilities")
    capabilities = capabilities if isinstance(capabilities, dict) else {}
    deps = install.get("deps")
    deps = deps if isinstance(deps, dict) else {}
    tools: dict = {}
    unrecorded: list[str] = []
    for row in requirements.REQUIREMENTS:
        rid = row["id"]
        if row["scope"] == "always":
            keys = [rid]
        else:
            project = [s for s in stacks if s in row["scope"]]
            if rid == "toolchain":
                keys = [f"{s}.{p['name']}" for s in project
                        for p in requirements.STACK_TOOLCHAINS.get(s, ())]
            else:
                keys = [f"{s}.client" for s in project]
        verdicts = [_recorded(capabilities, deps, k) for k in keys]
        if not keys or any(v is None for v in verdicts):
            unrecorded.append(rid)
        states = [_tool_state(v) for v in verdicts] or [TOOL_UNKNOWN]
        tools[rid] = max(states, key=_TOOL_RANK.__getitem__)
    return tools, unrecorded


def _tool_key_states(install: dict, stacks: list[str]) -> dict:
    """The state of every recorded key behind the project's tools map
    (CR-MDB-045 §S5): each always-scoped row by id, and for each of the
    project's stacks ``<stack>.client`` and ``<stack>.<probe>`` — the
    per-stack detail the capability contract lists. Read the way
    :func:`read_tool_verdicts` reads them; never probed."""
    capabilities = install.get("capabilities")
    capabilities = capabilities if isinstance(capabilities, dict) else {}
    deps = install.get("deps")
    deps = deps if isinstance(deps, dict) else {}
    keys = [r["id"] for r in requirements.REQUIREMENTS if r["scope"] == "always"]
    for stack in stacks:
        keys.append(f"{stack}.client")
        keys += [f"{stack}.{p['name']}" for p in requirements.STACK_TOOLCHAINS.get(stack, ())]
    return {key: _tool_state(_recorded(capabilities, deps, key)) for key in keys}


def _active_schema(schema: list[dict], tools: dict) -> list[dict]:
    """The schema keys this project renders: a ``when`` key only when its
    tool is present (CR-MDB-045 \u00a7S3)."""
    return [e for e in schema if "when" not in e or tools.get(e["when"]) == TOOL_PRESENT]

def _overrides_not_applied(schema: list[dict], tools: dict, inputs: dict) -> list[str]:
    """A note for each flag given for a ``when`` key its tool leaves out \u2014
    e.g. a fixture key's flag while its tool is not present (CR-MDB-045
    \u00a7S4). No packaged key carries ``when`` since CR-MDB-088 §S1.4, so
    ``--knowledge-category`` is always applied and never noted."""
    notes = []
    for entry in schema:
        if "when" not in entry or tools.get(entry["when"]) == TOOL_PRESENT:
            continue
        flag = entry.get("override") or entry.get("flag")
        if flag and inputs.get(_flag_dest(flag)) is not None:
            state = tools.get(entry["when"], TOOL_UNKNOWN)
            notes.append(f"{flag} given, but {entry['when']} is {state} \u2014 "
                         f"{entry['name']} is not applied")
    return notes


class ScaffoldError(ValueError):
    """A validation failure that aborts ``init`` before any write."""


# CR-MDB-025 §S6 — the committed `.env` key recording the project's stacks.
PROJECT_STACKS_KEY = "PROJECT_STACKS"

#: CR-MDB-047 §S2: the ``.envrc`` ``init`` writes beside every ``.env`` —
#: direnv's ``dotenv`` loads that ``.env`` into the environment.
ENVRC_TEXT = "dotenv\n"

#: CR-MDB-057 §S2: the one ``crucible.toml`` ``init`` writes, at the root
#: beside the root ``.env``. It declares the gate steps the project never runs
#: and no ``[client]`` table: a client reads ``[client]`` from the first
#: ``crucible.toml`` it finds, so this file keeps the project on the shipped
#: default board (the production board).
CRUCIBLE_TOML_NAME = "crucible.toml"
CRUCIBLE_TOML_TEXT = (
    "# Crucible client configuration for this project (read from the project root).\n"
    "#\n"
    "# [gate] skip: the no-mistakes steps `gate-run` never runs here. no-mistakes'\n"
    "# `ci` step is PR-based, and a git-flow project that merges directly has no PR\n"
    "# for it to watch, so the gate would otherwise block until `ci_timeout`. An\n"
    "# explicit `gate-run --skip` replaces this list; `--skip \"\"` skips nothing.\n"
    "#\n"
    "# No [client] table: a client takes [client] from the first crucible.toml it\n"
    "# finds, so this file keeps the project on the shipped default board.\n"
    "[gate]\n"
    "skip = [\"ci\"]\n"
)

#: CR-MDB-058 §S5: the one ``CHANGELOG.md`` ``init`` writes, at the root only,
#: in §S1's starting form — a ``# Changelog`` title, the Keep a Changelog and
#: Semantic Versioning links, and an empty ``## [Unreleased]``. A root
#: ``CHANGELOG.md`` already present is the project's own: never overwritten.
CHANGELOG_NAME = "CHANGELOG.md"
CHANGELOG_TEXT = (
    "# Changelog\n"
    "\n"
    "All notable changes to this project are documented in this file. The format is based on\n"
    "[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to\n"
    "[Semantic Versioning](https://semver.org/spec/v2.0.0.html).\n"
    "\n"
    "## [Unreleased]\n"
)


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
        reject_recorded_harnesses(home)
        return [str(h) for h in installed], "install.toml"
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


def harness_recovery_command(home: Path) -> str:
    """The re-run that replaces a stale recorded harness set
    (CR-MDB-031 §S1): ``modelb-axi --reinstall`` against ``home`` with the
    recorded target root and stacks (``<dir>`` when none is recorded),
    ``--harnesses`` set to the roster, and ``--allow-missing-capabilities``
    when the install recorded it (the re-run would otherwise fail the
    pre-flight the recorded install passed). Values are shell-quoted."""
    install = load_install_toml(home).get("install", {})
    target_root = install.get("target_root")
    stacks = install.get("stacks")
    parts = ["modelb-axi", "--reinstall", "--modelb-home", shlex.quote(str(home)),
             "--target-root",
             shlex.quote(target_root) if isinstance(target_root, str) and target_root
             else "<dir>"]
    if isinstance(stacks, list) and stacks and all(isinstance(s, str) for s in stacks):
        parts += ["--stacks", shlex.quote(",".join(stacks))]
    parts += ["--harnesses", ",".join(HARNESS_ROSTER_IDS)]
    allow_missing = install.get("allow_missing_capabilities")
    if isinstance(allow_missing, bool) and allow_missing:
        parts.append("--allow-missing-capabilities")
    return " ".join(parts)


def reject_recorded_harnesses(home: Path) -> None:
    """Refuse an ``install.toml`` whose ``[install].harnesses`` records an
    id outside the roster (CR-MDB-033 §S5; CR-MDB-031 §S1 — e.g. a retired
    harness recorded by an older install). The raised
    :class:`UnknownHarnessError` names the id(s) and the recovery re-run;
    nothing is written. A no-op when no harness set is recorded."""
    installed = load_install_toml(home).get("install", {}).get("harnesses")
    if not installed:
        return
    unknown = [str(h) for h in installed if str(h) not in HARNESS_ROSTER_IDS]
    if unknown:
        raise UnknownHarnessError(
            unknown,
            recovery=(f"{home / INSTALL_TOML_NAME} records it; recover with "
                      f"`{harness_recovery_command(home)}`"),
        )


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
        ".envrc",
        ".env.local",
        ".gitignore",
        CRUCIBLE_TOML_NAME,
        CHANGELOG_NAME,
        "AGENTS.md",
        "docs/changes/.gitkeep",
        "docs/research/.gitkeep",
        "hooks/README.md",
        # CR-MDB-068 §S5: the release workflow and its two scripts, at the root only.
        *RELEASE_FILES,
    ]
    for sub in sub_projects:
        base += [f"{sub}/.env", f"{sub}/.envrc", f"{sub}/AGENTS.md"]
    return base


#: The release workflow and its two scripts, as :func:`workflows.render` keys them
#: (CR-MDB-068 §S5).
RELEASE_FILES: tuple[str, ...] = (
    workflows.RELEASE_YML, workflows.STAMP_SCRIPT, workflows.SECTION_SCRIPT,
)
#: The registry key naming where a release publishes (CR-MDB-068 §S1).
RELEASE_TARGETS_KEY = "RELEASE_TARGETS"


def _orchestrator_label(mode: str, token: str) -> str:
    """Mode-aware orchestrator label (§S3.1): ``vidushi-<token>`` solo,
    ``Mainline-<token>`` multi."""
    return f"vidushi-{token}" if mode == "solo" else f"Mainline-{token}"


# --- CR-MDB-043 §S1/§S2: the project-settings schema -----------------------

def _remove_whitespace(value: str) -> str:
    """Derive rule: ``value`` with every whitespace character removed."""
    return "".join(value.split())


_NON_KEBAB_RUN_RE = re.compile(r"[^a-z0-9]+")

def _knowledge_category(token: str) -> str:
    """Derive rule: the lean-ctx knowledge category of a project,
    ``<PROJECT_TOKEN>-workflow`` normalised to kebab-case (CR-MDB-045 §S4):
    lower-cased, every run of other characters (``_``, spaces, ``.``) one
    ``-``, none leading or trailing — so any accepted token derives a valid
    category and never makes ``init`` fail."""
    word = _NON_KEBAB_RUN_RE.sub("-", token.lower()).strip("-")
    return f"{word}-workflow" if word else "workflow"


def _sandesh_address(sandesh_project: str) -> str:
    """Derive rule: the project's Mainline Sandesh address,
    ``Mainline - <SANDESH_PROJECT>`` (CR-MDB-047 §S2)."""
    return f"Mainline - {sandesh_project}"


#: Named derive rules a schema entry's ``rule`` refers to; each takes the
#: entry's ``inputs`` values positionally (CR-MDB-043 §S2).
DERIVE_RULES: dict = {
    "orchestrator_label": _orchestrator_label,
    "remove_whitespace": _remove_whitespace,
    "knowledge_category": _knowledge_category,
    "sandesh_address": _sandesh_address,
}


def _check_non_empty(value: str) -> str:
    """Validate rule: a non-empty value."""
    if not value.strip():
        raise ValueError("must be non-empty")
    return value


def _check_no_whitespace(value: str) -> str:
    """Validate rule: a non-empty value containing no whitespace."""
    if not value or any(ch.isspace() for ch in value):
        raise ValueError("must be non-empty with no whitespace")
    return value


def _check_stack_csv(value: str) -> str:
    """Validate rule: a ``--stacks`` CSV of known stacks, normalised the
    way :func:`parse_stacks` records it."""
    return ",".join(parse_stacks(value))


_SANDESH_ID_RE = re.compile(r"[A-Za-z0-9_.-]+")


def _check_sandesh_id(value: str) -> str:
    """Validate rule: a Sandesh project id — letters, digits, ``_``, ``-``
    and ``.`` only (CR-MDB-043 §S2 "Values")."""
    if not _SANDESH_ID_RE.fullmatch(value):
        raise ValueError("must use only letters, digits, `_`, `-` and `.`")
    return value


_KEBAB_ID_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def _check_kebab_id(value: str) -> str:
    """Validate rule: a kebab-case id — lower-case letters and digits in
    ``-``-separated words (CR-MDB-045 §S4)."""
    if not _KEBAB_ID_RE.fullmatch(value):
        raise ValueError("must be a kebab-case id (lower-case letters and digits "
                         "in `-`-separated words)")
    return value


#: The release targets ``RELEASE_TARGETS`` may name, in canonical order
#: (CR-MDB-068 §S1): ``workflows`` owns the one definition.
RELEASE_TARGETS = workflows.RELEASE_TARGETS


def _check_release_targets_csv(value: str) -> str:
    """Validate rule: a ``RELEASE_TARGETS`` CSV of ``name`` or
    ``name:dir`` targets (CR-MDB-068 §S1), returned canonical: the order of
    :data:`RELEASE_TARGETS`, each ``dir`` normalised and a ``.`` dir
    omitted, no whitespace; empty for no target. Refuses a duplicate name, and
    every refusal of :func:`workflows.parse_target`, which parses each item."""
    found: dict[str, str] = {}
    for item in (part.strip() for part in value.split(",")) if value.strip() else ():
        name, directory = workflows.parse_target(item)
        if name in found:
            raise ValueError(f"names the release target {name} twice (a duplicate)")
        found[name] = directory
    return ",".join(name if found[name] == "." else f"{name}:{found[name]}"
                    for name in RELEASE_TARGETS if name in found)


def _has_control_character(value: str) -> bool:
    """Whether ``value`` carries a control character (Unicode ``Cc``,
    newline and tab included)."""
    return any(unicodedata.category(ch) == "Cc" for ch in value)


#: Named validate rules a schema entry's ``validate`` refers to; each takes
#: the value and returns its canonical form, raising ``ValueError`` (or
#: :class:`ScaffoldError`) when it is invalid (CR-MDB-043 §S2).
VALIDATE_RULES: dict = {
    "non_empty": _check_non_empty,
    "no_whitespace": _check_no_whitespace,
    "stack_csv": _check_stack_csv,
    "sandesh_id": _check_sandesh_id,
    "kebab_id": _check_kebab_id,
    "release_targets_csv": _check_release_targets_csv,
}

_SCHEMA_FILES = (".env", ".env.local")
_SCHEMA_SCOPES = ("root", "root+sub")
_SCHEMA_SOURCES = ("ask", "derive", "capture")

#: ``init`` inputs a derive rule may name besides the schema's own keys —
#: the argparse dests of ``init``'s plan flags (CR-MDB-043 §S2).
DERIVE_INIT_INPUTS = frozenset({"mode", "repo_shape"})


def _is_text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _check_entry_fields(entry: dict, where: str) -> None:
    """Refuse an entry lacking a field its source requires, or carrying one
    of the wrong type (CR-MDB-043 §S2 "Loading and validating")."""
    if not _is_text(entry.get("description")):
        raise ScaffoldError(f"{where}: description must be a non-empty string")
    readers = entry.get("readers")
    if not isinstance(readers, list) or not readers or not all(map(_is_text, readers)):
        raise ScaffoldError(f"{where}: readers must be a non-empty list of strings")
    if not isinstance(entry.get("required"), bool):
        raise ScaffoldError(f"{where}: required must be a boolean (true or false)")
    if entry["file"] == ".env.local" and entry["scope"] == "root+sub":
        raise ScaffoldError(
            f"{where}: file = \".env.local\" with scope = \"root+sub\" is refused "
            "— no sub-project .env.local is emitted")
    source = entry["source"]
    if source == "ask" and not str(entry.get("flag", "")).startswith("--"):
        raise ScaffoldError(f"{where}: an ask key names its --flag")
    if source == "derive":
        if entry.get("rule") not in DERIVE_RULES:
            raise ScaffoldError(
                f"{where}: unknown derive rule {entry.get('rule')!r}; "
                f"known: {', '.join(DERIVE_RULES)}")
        inputs = entry.get("inputs")
        if not isinstance(inputs, list) or not inputs or not all(map(_is_text, inputs)):
            raise ScaffoldError(f"{where}: a derive key names its inputs")
        if "override" in entry and not (
                isinstance(entry["override"], str) and entry["override"].startswith("--")):
            raise ScaffoldError(
                f"{where}: override must be a --flag; got {entry['override']!r}")
    if source == "capture" and not _is_text(entry.get("step")):
        raise ScaffoldError(f"{where}: a capture key names its step")


def _check_when(entry: dict, where: str) -> None:
    """Refuse a ``when`` that is not the id of a declared requirement row
    (CR-MDB-045 \u00a7S3)."""
    if "when" not in entry:
        return
    when = entry["when"]
    if not isinstance(when, str):
        raise ScaffoldError(f"{where}: when must be a requirement id string; got {when!r}")
    if when not in _REQUIREMENT_IDS:
        raise ScaffoldError(
            f"{where}: when {when!r} is not a declared requirement id; "
            f"known: {', '.join(_REQUIREMENT_IDS)}")


def load_schema(path: Path) -> list[dict]:
    """Load the project-settings schema at ``path`` (CR-MDB-043 §S1): its
    one top-level array of tables, one entry per key, in declaration
    order. Raises :class:`ScaffoldError` naming the key and the field for
    an unreadable schema, an illegal or missing field, a duplicate key, an
    unknown derive/validate rule name, or a derive input that is neither a
    declared key nor an ``init`` input — before ``init`` writes anything."""
    try:
        data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ScaffoldError(f"project schema {path}: {exc}") from exc
    tables = [v for v in data.values() if isinstance(v, list)]
    if len(tables) != 1 or not all(isinstance(e, dict) for e in tables[0]):
        raise ScaffoldError(
            f"project schema {path} must hold exactly one array of tables")
    entries = tables[0]
    seen: set[str] = set()
    for entry in entries:
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise ScaffoldError(f"project schema {path}: an entry has no name")
        if name in seen:
            raise ScaffoldError(f"project schema {path}: {name} is declared twice")
        seen.add(name)
        where = f"project schema {path}: {name}"
        if entry.get("file") not in _SCHEMA_FILES:
            raise ScaffoldError(f"{where}: file must be one of {_SCHEMA_FILES}")
        if entry.get("scope") not in _SCHEMA_SCOPES:
            raise ScaffoldError(f"{where}: scope must be one of {_SCHEMA_SCOPES}")
        source = entry.get("source")
        if source not in _SCHEMA_SOURCES:
            raise ScaffoldError(f"{where}: source must be one of {_SCHEMA_SOURCES}")
        if entry.get("validate") not in VALIDATE_RULES:
            raise ScaffoldError(
                f"{where}: unknown validate rule {entry.get('validate')!r}; "
                f"known: {', '.join(VALIDATE_RULES)}")
        _check_entry_fields(entry, where)
        _check_when(entry, where)
    for entry in entries:
        for item in entry.get("inputs", []) if entry["source"] == "derive" else []:
            if item not in seen and item not in DERIVE_INIT_INPUTS:
                raise ScaffoldError(
                    f"project schema {path}: {entry['name']}: derive input {item!r} "
                    "(inputs) is neither a declared key nor an init input "
                    f"({', '.join(sorted(DERIVE_INIT_INPUTS))})")
    return entries


def _flag_dest(flag: str) -> str:
    """The argparse dest of ``flag`` (``--team-lead`` -> ``team_lead``)."""
    return flag.lstrip("-").replace("-", "_")


def _required_flags(schema: list[dict]) -> list[tuple[str, str]]:
    """``(dest, flag)`` of every value ``init`` requires: the schema's
    ask+required keys, then the non-registry plan inputs."""
    asked = [
        (_flag_dest(e["flag"]), e["flag"]) for e in schema
        if e["source"] == "ask" and e.get("required")
    ]
    return asked + list(_PLAN_REQUIRED_FLAGS)


def resolve_registry(schema: list[dict], inputs: dict) -> dict:
    """Every schema key's value for one ``init`` (CR-MDB-043 §S2), in
    schema order: an ask key from its flag's dest in ``inputs``, a derive
    key from its rule over its inputs (its ``override`` flag winning when
    given), a capture key empty (captured later). Each asked or derived
    value passes its validate rule; a failure raises :class:`ScaffoldError`
    naming the key and its flag."""
    registry: dict = {}
    derived: set = set()
    for entry in schema:
        if entry["source"] == "ask":
            registry[entry["name"]] = inputs.get(_flag_dest(entry["flag"])) or ""
        elif entry["source"] == "capture":
            registry[entry["name"]] = ""
    for entry in schema:
        if entry["source"] != "derive":
            continue
        override = entry.get("override")
        value = inputs.get(_flag_dest(override)) if override else None
        if value is None:
            args = []
            for item in entry["inputs"]:
                if item in registry:
                    args.append(registry[item])
                elif item in inputs:
                    args.append(inputs[item])
                else:
                    raise ScaffoldError(
                        f"{entry['name']}: derive input {item!r} is not resolved")
            value = DERIVE_RULES[entry["rule"]](*args)
            derived.add(entry["name"])
        registry[entry["name"]] = value
    for entry in schema:
        name = entry["name"]
        if entry["source"] == "capture" or (not registry[name] and not entry.get("required")):
            continue
        flag = entry.get("flag") or entry.get("override")
        label = f"{name} ({flag})" if flag else name
        # CR-MDB-043 §S2 "Values": no rendered value carries a control
        # character (a newline would forge a second KEY=value line).
        if _has_control_character(registry[name]):
            raise ScaffoldError(
                f"{label}: value {registry[name]!r} contains a control character")
        hint = (f"; it is derived from {', '.join(entry['inputs'])} — set it "
                f"with {entry['override']}"
                if name in derived and entry.get("override") else "")
        try:
            registry[name] = VALIDATE_RULES[entry["validate"]](registry[name])
        except ScaffoldError as exc:
            raise ScaffoldError(f"{label}: {exc}{hint}") from exc
        except ValueError as exc:
            raise ScaffoldError(f"{label}: value {registry[name]!r} {exc}{hint}") from exc
    return registry


def _render_registry(schema: list[dict], registry: dict, file: str, *, sub: bool) -> str:
    """``KEY=value`` lines of every schema key living in ``file`` — only
    the ``root+sub`` keys for a sub-project (CR-MDB-043 §S2). Every value
    containing whitespace is double-quoted, whatever its source (asked,
    derived or captured), so direnv's dotenv parser accepts the line
    (CR-MDB-047 §S2); :func:`_read_env_value` reads it back unquoted."""
    def value(entry: dict) -> str:
        text = registry.get(entry["name"], "")
        if any(ch.isspace() for ch in text):
            return f'"{text}"'
        return text

    return "".join(
        f"{e['name']}={value(e)}\n" for e in schema
        if e["file"] == file and (not sub or e["scope"] == "root+sub")
    )


def read_registry_value(project_root: Path, schema: list[dict], key: str) -> str | None:
    """The value of schema ``key`` recorded in ``project_root``, read from
    the file the schema places it in; None when absent (CR-MDB-043 §S2)."""
    entry = next((e for e in schema if e["name"] == key), None)
    if entry is None:
        raise ScaffoldError(f"{key} is not declared in the project schema")
    path = project_root / entry["file"]
    return _read_env_value(path, key) if path.is_file() else None


def _setup_required(schema: list[dict], registry: dict) -> list[dict]:
    """One row per required capture key still empty after ``init`` — the
    values the user must fill in before the key's readers run (CR-MDB-043
    §S2: CRUCIBLE_PROJECT_KEY is empty until the project is registered
    in Crucible, and is filled in ``.env``)."""
    return [
        {
            "key": e["name"],
            "file": e["file"],
            "note": (f"empty until {e['step']}; fill it in {e['file']} before "
                     f"its readers run: {', '.join(e['readers'])}"),
        }
        for e in schema
        if e["source"] == "capture" and e.get("required") and not registry.get(e["name"])
    ]


def _render_env(schema: list[dict], registry: dict, *, sub: bool = False) -> str:
    """The COMMITTED ``.env`` registry (§S3.1): the schema's ``.env`` keys
    in schema order, root or sub-project scope (CR-MDB-043 §S2)."""
    return (
        "# Project naming registry (CR-MDB-013 scaffold; committed).\n"
        + _render_registry(schema, registry, ".env", sub=sub)
    )


def _render_env_local(schema: list[dict], registry: dict) -> str:
    """The GITIGNORED ``.env.local`` overlay (§S3.1): the schema's
    ``.env.local`` keys (none today; CR-MDB-043 §S2)."""
    return (
        "# Gitignored overlay for values that stay on this machine;\n"
        "# not part of the project registry (that is .env).\n"
        + _render_registry(schema, registry, ".env.local", sub=False)
    )


def _render_gitignore() -> str:
    """``.gitignore`` incl. ``.env.local`` and the in-repo worktree
    segment ``.worktrees/`` (§S3.5; CR-MDB-031 §S0.1/§S3)."""
    return (
        "# Machine-local overlay (values that stay on this machine) — never committed.\n"
        ".env.local\n"
        "\n"
        "# CR worktrees live inside the repo (inheriting Pi's project trust).\n"
        ".worktrees/\n"
        # `.pi/` is NOT ignored: `.pi/extensions/` (compiled hook shims) and
        # `.pi/agents/` are tracked so every worktree carries them
        # (CR-MDB-030 §S6).
        "\n"
        "# Tooling debris.\n"
        "__pycache__/\n"
        "test-reports/\n"
    )


def _remediation_first(tools: dict, rid: str, label: str) -> str:
    """The lead of a setup task for tool ``rid``: its remediation when
    ``tools`` records it absent, else nothing (CR-MDB-045 §S5)."""
    if tools.get(rid) != TOOL_ABSENT:
        return ""
    return f"{label} is absent — first: {requirements.requirement(rid)['remediation']}. Then: "


def _render_setup_section(mode: str, sandesh_project: str, tools: dict | None = None,
                          label: str = "", stacks: tuple[str, ...] | list[str] = (),
                          release_setup: tuple[str, ...] | list[str] = ()) -> str:
    """The root ``AGENTS.md``'s ``## Setup`` section (CR-MDB-048 §S2): the
    setup tasks the retired queue README carried, as they stood — the dated
    scaffold line, the manual Crucible registration (registrations are
    manual in scaffold v1), in multi mode the Sandesh and direnv task naming
    the project's Sandesh id and Mainline address from ``SANDESH_PROJECT``
    (CR-MDB-043 §S2, CR-MDB-047), and the ``REPO_OWNER`` check. Where
    ``tools`` records Sandesh or Crucible absent, its setup task names the
    tool's remediation first (CR-MDB-045 §S5).

    CR-MDB-057 §S3: directly after the Crucible registration task (and
    before the Sandesh task in multi mode), the ``project-meta`` task —
    register the orchestrator ``label`` (:func:`_orchestrator_label`) as
    ``ORCHESTRATOR``, then mirror the root ``.env``'s keys but
    ``CRUCIBLE_PROJECT_KEY`` with ``project-meta --set``, re-run whenever
    ``.env`` changes; Crucible's remediation first when it is absent.

    CR-MDB-063 §S4: when ``stacks`` include ``python``, one unchecked task
    to create the python test interpreter, after the ``project-meta`` task
    and the Sandesh task (multi mode), before the ``REPO_OWNER`` check. Its
    commands are :data:`modelb_axi.requirements.PYTHON_VENV_ROUTE`, read at
    call time (never a copied string); no python stack, no task.

    CR-MDB-068 §S5: each of ``release_setup`` (:func:`release_setup_tasks`) as one
    unchecked task, after the python task, before the ``REPO_OWNER`` check."""
    today = datetime.date.today().isoformat()
    tools = tools or {}
    project_meta_task = (
        f"- [ ] {_remediation_first(tools, 'crucible', 'Crucible')}"
        "Once the key is filled, register the orchestrator "
        f"(`register --agent {label} --role ORCHESTRATOR`), then mirror the root "
        "`.env`'s keys, except `CRUCIBLE_PROJECT_KEY`, with "
        f"`project-meta --set KEY=VALUE … --agent {label}`; re-run it whenever "
        "`.env` changes\n"
    )
    sandesh_task = (
        f"- [ ] {_remediation_first(tools, 'sandesh', 'Sandesh')}"
        f"Sandesh setup + register (`{sandesh_project}`, "
        f"`Mainline - {sandesh_project}`) — "
        "manual step (registrations are manual in scaffold v1). Install direnv "
        "and its shell hook (`direnv hook fish | source`, or "
        '`eval "$(direnv hook bash)"`), then run `direnv allow` in each '
        "directory with an `.envrc` (it exports `SANDESH_ADDRESS` from `.env`); "
        f'launch a Track with `env SANDESH_ADDRESS="Track <N> - {sandesh_project}" pi`\n'
        if mode != "solo" else ""
    )
    release_tasks = "".join(f"- [ ] {task}\n" for task in release_setup)
    python_task = ""
    if "python" in stacks:
        commands = ", then ".join(f"`{command}`" for command in requirements.PYTHON_VENV_ROUTE)
        python_task = (
            "- [ ] Create the python test interpreter: from the project root, run "
            f"{commands} — the python client runs the tests under `.venv/bin/python` when "
            "it exists; `coverage` is needed for `regression --coverage`\n"
        )
    return (
        "## Setup\n"
        "Pre-wave tasks — not a wave; a wave is a grouping of CRs.\n"
        "\n"
        f"- [x] Scaffold via `modelb-axi init` — {today}\n"
        f"- [ ] {_remediation_first(tools, 'crucible', 'Crucible')}"
        "Register the project in Crucible and paste the key into "
        "`.env` (`CRUCIBLE_PROJECT_KEY=`) — manual step "
        "(registrations are manual in scaffold v1)\n"
        f"{project_meta_task}"
        f"{sandesh_task}"
        f"{python_task}"
        f"{release_tasks}"
        "- [ ] Confirm the remote owner matches `REPO_OWNER` in `.env` "
        "before the first wave-boundary gate\n"
    )


#: Pi reads ``AGENTS.md`` natively, so the scaffold emits no anchor file
#: and notes that fact (§S3.3).
_PI_ANCHOR_NOTE = (
    "- pi (pi.dev): reads `AGENTS.md` natively — no separate anchor file "
    "emitted."
)


def _render_capability_contract(
    stacks: list[str], harnesses: tuple[str, ...] = (), states: dict | None = None,
) -> str:
    """The capability contract (CR-MDB-036 §S6; CR-MDB-045 §S5), rendered
    from :mod:`modelb_axi.requirements` at call time (never hand-copied)
    and from ``states`` — each recorded key's state, as
    :func:`_tool_key_states` reads it (a key it lacks is unknown). One line
    per tool, in requirement order: each always-scoped row, then for the
    project's own stacks the Crucible client and each toolchain probe. A
    line names the tool and its state, and the remediation where it is not
    present. A toolchain probe of the same name as an always-scoped row
    (``python3``) is merged into that row's line, which takes the worse of
    their states: each tool appears once. Unselected stacks are not
    mentioned.

    CR-MDB-063 §S3: the merged ``python3`` line is labelled
    ``<policy>; <stacks> toolchain`` with every selected stack carrying the
    probe, in selection order. It names the probe's remediation (``uv python
    install --default``) when a stack's ``<stack>.python3`` state is
    non-present and ranks at least as bad as the row's own (ties included),
    else the row's."""
    states = states or {}
    lines: list[str] = []

    def line(name: str, label: str, state: str, remediation: str) -> None:
        tail = "" if state == TOOL_PRESENT else f" — {remediation}"
        lines.append(f"- `{name}` ({label}): {state}{tail}")

    def worst(found: list[str]) -> str:
        return max(found, key=_TOOL_RANK.__getitem__)

    # name -> (the selected stacks carrying it, its first probe, their states)
    probes: dict[str, tuple[list[str], dict, list[str]]] = {}
    for stack in stacks:
        for probe in requirements.STACK_TOOLCHAINS.get(stack, ()):
            first = probes.setdefault(probe["name"], ([], probe, []))
            first[0].append(stack)
            first[2].append(states.get(f"{stack}.{probe['name']}", TOOL_UNKNOWN))
    for row in requirements.REQUIREMENTS:
        if row["scope"] == "always":
            remediation = (f"`{row['remediation']}`" if row["tier"] == 1
                           else row["remediation"])
            own = states.get(row["id"], TOOL_UNKNOWN)
            label, found = row["policy"], [own]
            merged = probes.pop(row["id"], None)
            if merged is not None:
                label = f"{label}; {', '.join(merged[0])} toolchain"
                found += merged[2]
                if any(s != TOOL_PRESENT and _TOOL_RANK[s] >= _TOOL_RANK[own]
                       for s in merged[2]):
                    remediation = merged[1]["remediation"]
            line(row["id"], label, worst(found), remediation)
        elif row["id"] == "crucible-client":
            for stack in (s for s in stacks if s in row["scope"]):
                line(row["id"], f"{stack} client, {row['policy']}",
                     states.get(f"{stack}.client", TOOL_UNKNOWN), row["remediation"])
        elif row["id"] == "toolchain":
            for name, (carriers, probe, found) in probes.items():
                line(name, f"{carriers[0]} toolchain", worst(found), probe["remediation"])
    if "pi" in harnesses:
        # CR-MDB-037 §S4: Pi loads .pi/extensions only in a trusted project.
        # CR-MDB-085 §S1.5: nor its stack skills under `.agents/skills/`.
        lines.append(
            "- project trust (Pi): this project's hooks and permission "
            "policy under `.pi/extensions/`, and its stack skills under "
            "`.agents/skills/`, load only once the project is "
            "trusted: run `/trust` in Pi from the project root"
        )
    return (
        "## Harness capability contract (from the installation's recorded verdicts)\n"
        "Each line names a tool this project's assets need, its state as the "
        "installation recorded it, and how to provide it when it is not present; "
        "a tool with no recorded verdict is unknown until the installer is re-run.\n"
        + "\n".join(lines) + "\n"
    )


def _render_lean_ctx_section(category: str) -> str:
    """The lean-ctx section of a project's ``AGENTS.md``, for the
    orchestrator working it (CR-MDB-045 §S4, CR-MDB-088 §S2): cached reads
    and the compressed shell, where execution knowledge is kept, and the
    store's verbs — the scoped restore, the listing and the rewrite of the
    kept restored facts first."""
    return (
        "## lean-ctx (for the orchestrator working this project)\n"
        "- Prefer lean-ctx's cached reads and compressed shell over the "
        "harness's built-in read and shell tools.\n"
        "- Keep this project's execution knowledge in lean-ctx's knowledge "
        f"store under the category `{category}` (`KNOWLEDGE_CATEGORY` in `.env`), "
        "through the session's `ctx_knowledge` tool. Never use the "
        "`lean-ctx knowledge` CLI: its project does not follow the working "
        "directory.\n"
        "- **Restore.** At bootstrap, Mainline or Solo restores the category's "
        "archived facts with `ctx_knowledge` `action=restore`, `store=facts` "
        f"and `query={category}`, and repeats it "
        "until it restores nothing (each restore returns at most 50 items). The "
        "query is a substring match on each archived fact's category, key and "
        "value, through an archive shared between projects, so a scoped restore "
        "can still bring in another project's facts under the same or a "
        "containing name; such a fact is removed at reconciliation and reported. "
        "Never restore unscoped: that restores every store, and other projects' "
        "archived facts. A Track never restores.\n"
        f"- **List.** List the category with `action=recall` and `category={category}`. "
        "The answer says `showing <n>/<total>`. When `<n>` is less than `<total>`, "
        "the listing is incomplete: `action=export` writes the whole store to a "
        "file it names, and the rest is read from there. The file sits under "
        "lean-ctx's data directory, outside the project permission policy's "
        "allowed reads, so reading it prompts the user. A Track only lists.\n"
        "- **Rewrite first.** The restored facts are those the listing (or the "
        "export) shows below 30% confidence. Decide each fact's outcome first; "
        "then, before any other write, rewrite each restored fact that is kept "
        "with `action=remember` under its key; only then make the "
        "reconciliation's removals and other rewrites. A fact a rewrite archives "
        "again is restored by its key, with `action=restore`, `store=facts` "
        f'and `query="{category} <key>"`, and rewritten at once. Every `remember` '
        "and `remove` archives each fact still below the store's 0.3 archive "
        "threshold (a restore runs no lifecycle), and `action=feedback` does not "
        "lift a fact over that threshold.\n"
    )


def _stack_skill_clause(names: list[str]) -> str:
    """CR-MDB-085 §S1.5: the stack line's stack-skill clause — the declared
    skills of the stack, or nothing for a stack that declares none."""
    if not names:
        return ""
    noun = "stack skill" if len(names) == 1 else "stack skills"
    return f"{', '.join(f'`{n}`' for n in names)} {noun} and "


def _render_agents_md(
    name: str, token: str, acronym: str, mode: str, owner: str,
    stacks: list[str], harnesses: list[str], knowledge_category: str,
    sandesh_project: str | None = None, states: dict | None = None,
    tools: dict | None = None, release_setup: list[str] | None = None,
    stack_skill_names: dict[str, list[str]] | None = None,
) -> str:
    """Project ``AGENTS.md`` override (§S3.3/§S3.8): identity from the
    registry, the design-reference lines (the retired queue README's
    header slots, CR-MDB-048 §S2), workflow rules (incl. the post-036
    run-context note — workflow cycle env vars are never hand-set, and this
    file must not name them), the ``## Setup`` section from ``tools``
    (:func:`_render_setup_section`), stack-derived skill freeze,
    per-installed-harness anchor notes, the capability contract from the
    recorded ``states``, the lean-ctx section for ``knowledge_category`` —
    rendered for every project, whatever the lean-ctx verdict (CR-MDB-088
    §S1.3; CR-MDB-045 §S5) — and the generator note.

    CR-MDB-085 §S1.5: a stack's line names its stack skill only where
    ``stack_skill_names`` (stack -> the declared skills naming it) declares
    one; a stack without one names no stack skill."""
    label = _orchestrator_label(mode, token)
    sandesh_line = (
        f"- Sandesh project: `{sandesh_project}` (`SANDESH_PROJECT`; addresses "
        f"`Mainline - {sandesh_project}` / `Track <N> - {sandesh_project}`).\n"
        f"- Sandesh address: `SANDESH_ADDRESS` in `.env` is `Mainline - {sandesh_project}`, "
        "loaded by direnv through `.envrc`; a Track launches with "
        f'`env SANDESH_ADDRESS="Track <N> - {sandesh_project}" pi`.\n'
        if sandesh_project else ""
    )
    stack_lines = "\n".join(
        f"- {stack}: use the {_stack_skill_clause((stack_skill_names or {}).get(stack, []))}"
        f"generated RED/GREEN/VERIFY/FIX agents, rendered at scaffold time; re-render "
        f"them with `modelb-axi agents`."
        for stack in stacks
    )
    anchor_lines = [_PI_ANCHOR_NOTE] if "pi" in harnesses else []
    return (
        f"# {name} — project AGENTS.md\n"
        "\n"
        "Project-level conventions for every session/agent working this "
        "repo. Scaffolded by `modelb-axi init`.\n"
        "\n"
        "## Design references\n"
        "- Design contract: _fill in (`docs/research/PRD-….md`)_\n"
        "- Evidence base: _fill in_\n"
        "- Ontology: `~/.agents/skills/model-b/SKILL.md`\n"
        "\n"
        "## Identity & naming (registry: `.env` at the project root)\n"
        f"- Project **{name}** · token `{token}` · acronym `{acronym}` · "
        f"owner `{owner}`.\n"
        f"- Orchestrator label: `{label}` (mode: {mode}; mode-aware — "
        "solo `vidushi-<token>`, multi `Mainline-<token>`).\n"
        f"- CR ids: `CR-{acronym}-NNN`. Crucible agentIds follow the stack "
        "client's agent-naming header — never improvised; see the "
        "`crucible` skill's Identity section.\n"
        f"{sandesh_line}"
        "\n"
        "## Workflow rules\n"
        "- A **wave** is a grouping of CRs marking an execution boundary; "
        "setup tasks and releases are NOT waves.\n"
        "- The Crucible board holds the queue and the execution state "
        "(plans, cycles, milestones); `docs/changes/` holds the specs.\n"
        "- Run context (post-036): workflow cycle context is attached by "
        "the tooling at ingest time — never hand-export cycle identifiers "
        "into the environment or into this file.\n"
        "- Registrations are manual in scaffold v1 — complete them from "
        "the Setup section below.\n"
        "\n"
        + _render_setup_section(mode, sandesh_project or "", tools, label, stacks,
                                release_setup or ())
        + "\n"
        f"## Skill freeze (derived from --stacks: {', '.join(stacks)})\n"
        f"{stack_lines}\n"
        "\n"
        f"## Harness anchors (installed set: {', '.join(harnesses)})\n"
        + "\n".join(anchor_lines) + "\n"
        "\n"
        + _render_capability_contract(stacks, tuple(harnesses), states)
        + "\n"
        + _render_lean_ctx_section(knowledge_category) + "\n"
        + "## Generator note\n"
        "- Agents regenerate from the INSTALLATION's generator assets — "
        "never from a per-project copy.\n"
    )


def _render_sub_agents_md(
    name: str, sub: str, token: str, acronym: str, knowledge_category: str,
) -> str:
    """Per-sub-project ``AGENTS.md`` override (§S3 monorepo); it always
    carries its own lean-ctx section for ``knowledge_category`` — the
    category in the sub-project's own ``.env`` (CR-MDB-088 §S1.3)."""
    lean_ctx = "\n" + _render_lean_ctx_section(knowledge_category)
    return (
        f"# {name} / {sub} — sub-project AGENTS.md\n"
        "\n"
        f"Sub-project override for `{sub}/` (token `{token}`, acronym "
        f"`{acronym}`). Tools resolve THIS directory's `.env` registry — "
        "never the repo root's on this sub-project's behalf. Repo-wide "
        "conventions live in the root `AGENTS.md`.\n"
        + lean_ctx
    )


# CR-MDB-015 §S5 hook-selection table (stack/mode-derived). Pinned rows
# (CR text + the C3 RED tests): the cargo guard iff a rust stack; the mvn
# guard iff a java/quarkus stack; the python runner guard
# (`block-direct-python-test`) iff a python stack and the bun runner guard
# (`block-direct-bun-test`) iff a bun stack, each `pre-tool-use` / `bash` /
# `core` / `closed` (CR-MDB-062 §S7); the worktree + CR-completion guards iff
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
# guard is `closed` (CR-MDB-030 §S6) — Pi, the only roster harness,
# honours it.


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
    # CR-MDB-062 §S7: each test-runner guard exactly for its stack.
    for stack, command in (
        ("python", "block-direct-python-test"),
        ("bun", "block-direct-bun-test"),
    ):
        if stack in stacks:
            instances.append({
                "event": "pre-tool-use",
                "matcher": "bash",
                "command": command,
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


def _check_hook_scripts(scripts_root: Path, instances: list[dict]) -> None:
    """Every hook init would emit has its script as an executable file in
    the resolved store (CR-MDB-062 §S7).

    Called from :func:`run_init`'s validation phase, once
    :func:`_hook_scripts_root` resolves and before the first write — a
    wiring whose command names a missing or non-executable script would
    fail closed on every tool call. Raises ONE :class:`ScaffoldError`
    naming each unusable script and ``modelb-axi --reinstall``, the run
    that redeploys the store. Read-only."""
    unusable = []
    for instance in instances:
        command = instance["command"]
        script = scripts_root / command
        if not (script.is_file() and os.access(script, os.X_OK)):
            unusable.append(command)
    if unusable:
        raise ScaffoldError(
            f"the hook-script store {scripts_root} lacks an executable "
            f"script for {', '.join(unusable)}, which init would wire; run "
            "`modelb-axi --reinstall` to redeploy the hook scripts, then "
            "re-run init"
        )


def _render_hooks_readme(
    report: dict, instances: list[dict], harnesses: list[str],
) -> str:
    """`hooks/README.md` = the human-readable §S4 compiler report (§S5):
    per-harness accounting — emitted files, wired hooks and notes —
    nothing silent. ``report`` carries an entry for every harness in
    ``harnesses``: :func:`run_init` validates the set against the roster
    and resolves the scripts root before emission (CR-MDB-031 C5 F8)."""
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
        entry = report[harness]
        lines.append(f"### {harness}")
        lines.append("")
        wired = [i["command"] for i in instances]
        if wired:
            lines.append(f"- wired hooks: {', '.join(wired)}")
        if entry["emitted_files"]:
            lines.append(
                f"- emitted files: {', '.join(entry['emitted_files'])}"
            )
        for note in entry["notes"]:
            lines.append(f"- {note}")
        lines.append("")
    return "\n".join(lines)


def _agent_sources(home: Path) -> tuple[Path, Path]:
    """Asset-root resolution for the agent templates + stack TOMLs
    (CR-MDB-025 §S6): ``install.toml [install].asset_root`` →
    :func:`default_asset_root`.
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


def _workflow_sources(home: Path) -> Path:
    """Asset-root resolution for the release-workflow templates and scripts
    (CR-MDB-068 §S2), the chain of :func:`_agent_sources`:
    ``install.toml [install].asset_root`` → :func:`default_asset_root`.
    Returns the ``workflows-src`` directory of the first root holding one."""
    candidates: list[Path] = []
    configured = load_install_toml(home).get("install", {}).get("asset_root")
    if configured:
        candidates.append(Path(str(configured)))
    candidates.append(default_asset_root())
    for root in candidates:
        source = root / "workflows-src"
        if source.is_dir():
            return source
    raise ScaffoldError(
        "no workflows-src/ found under any asset root; tried: "
        + ", ".join(str(c) for c in candidates)
    )


#: CR-MDB-068 §S5: the release setup task of each stack, keyed by stack; stacks sharing a
#: task (quarkus and java: the Maven wrapper) carry it once.
_RELEASE_STACK_TASKS: dict[str, str] = {
    "python": ("Add a `tests/` package holding the project's unittest modules — the "
               "release workflow's `test-python` job discovers its tests there"),
    "bun": ("Commit `bun.lock` — the release workflow's `test-bun` job installs from "
            "the frozen lockfile"),
    "rust": ("Commit `Cargo.lock` — the release workflow's `test-rust` job builds "
             "locked"),
    "quarkus": ("Commit the executable Maven wrapper `mvnw` — the release workflow's "
                "Maven test job runs it"),
    "java": ("Commit the executable Maven wrapper `mvnw` — the release workflow's "
             "Maven test job runs it"),
    "arduino": ("Add an executable `.github/scripts/ci-test` — the release workflow's "
                "`test-arduino` job runs it and fails naming it when it is missing"),
}
#: CR-MDB-068 §S5: the one task every rendered workflow needs (its `create-release` job).
_RELEASE_PAT_TASK = (
    "Add the `RELEASE_PAT` repository secret, a token with `contents: write` — the "
    "release workflow's `create-release` job creates the release with it, so the release "
    "fires the publish run"
)
#: CR-MDB-068 §S5: the release setup task of each target, keyed by target name.
_RELEASE_TARGET_TASKS: dict[str, str] = {
    "pypi": ("Create the `pypi` and `testpypi` environments in the repository settings, "
             "and add `release.yml` as a trusted publisher on PyPI (environment `pypi`) and "
             "on TestPyPI (environment `testpypi`)"),
    "npm": ("Create the `npm` environment in the repository settings and add the "
            "`NPM_TOKEN` repository secret for the first publish; then add `release.yml` as "
            "the package's trusted publisher on npm (environment `npm`) and delete the token"),
    # CR-MDB-071 §S4: the header's crates and maven-central items, as tasks.
    "crates": ("Create the `crates` environment in the repository settings, admitting the "
               "version tags, and add the `CARGO_REGISTRY_TOKEN` repository secret for the "
               "first publish; then add the crates.io trusted publisher (this repository, "
               "`release.yml`, environment `crates`) and delete the token"),
    "maven-central": ("Create the `maven-central` environment in the repository settings, "
                      "admitting the version tags; verify the namespace on the Central Portal; "
                      "add the repository secrets `MAVEN_CENTRAL_USERNAME` and "
                      "`MAVEN_CENTRAL_PASSWORD` (a Portal user token), `MAVEN_GPG_PRIVATE_KEY` "
                      "and `MAVEN_GPG_PASSPHRASE`; make the POM carry "
                      "`central-publishing-maven-plugin` with `<extensions>true</extensions>`, "
                      "the sources and javadoc jars, and `maven-gpg-plugin` 3.2.0 or newer; "
                      "commit one `mvnw` at the repository root"),
    "github-assets": ("Add an executable `.github/scripts/build-assets` that fills "
                      "`dist-assets/` — the release workflow's rehearsal and its "
                      "`publish-github-assets` job run it"),
}


def release_setup_tasks(stacks: list[str], targets: list[str]) -> list[str]:
    """The release workflow's setup tasks (CR-MDB-068 §S5), each without its ``- [ ] ``
    prefix: one per stack (a task two stacks share, once), the ``RELEASE_PAT`` secret, then one
    per canonical target (``name`` or ``name:dir``)."""
    tasks: list[str] = []
    for stack in stacks:
        task = _RELEASE_STACK_TASKS.get(stack)
        if task is not None and task not in tasks:
            tasks.append(task)
    tasks.append(_RELEASE_PAT_TASK)
    for target in targets:
        tasks.append(_RELEASE_TARGET_TASKS[target.partition(":")[0]])
    return tasks


def _release_targets(value: str) -> list[str]:
    """The canonical ``RELEASE_TARGETS`` value as a list (empty for no target)."""
    return value.split(",") if value else []


def _place_release_files(root: Path, texts: dict[str, str], force_managed: bool,
                         report: dict) -> dict:
    """Write the pre-rendered release files under ``root`` by the ownership rules
    (``agents.place_owned`` classifying by :func:`workflows.ownership_state`, CR-MDB-068
    §S5/§S6); fills and returns ``report`` (``written`` / ``unchanged`` / ``skipped``
    / ``unmanaged``)."""
    for key in ("written", "unchanged", "skipped", "unmanaged"):
        report.setdefault(key, [])
    for rel, text in texts.items():
        agents.place_owned(root / rel, rel, text, force_managed, report,
                           classify=workflows.ownership_state)
    return report


def _managed_release_workflow(root: Path) -> bool:
    """Whether ``root`` holds a ``release.yml`` under the release-workflow marker, intact or
    hand-modified (CR-MDB-068 §S6)."""
    path = root / workflows.RELEASE_YML
    if not path.is_file():
        return False
    text = path.read_bytes().decode("utf-8", errors="replace")
    return workflows.ownership_state(text) != agents.NOT_OWNED


def _ownership_warnings(skipped: list[str], unmanaged: list[str]) -> list[str]:
    """One warning per file the ownership rules left alone (CR-MDB-025 §S6): a hand-modified
    one names ``--force-managed``; an unmanaged one says no flag overwrites it."""
    return ([f"skipping hand-modified managed file {rel} (marker hash mismatch; re-run with "
             "--force-managed to overwrite)" for rel in skipped]
            + [f"unmanaged: {rel} — no Model B marker; left untouched (no flag "
               "overwrites it)" for rel in unmanaged])


def _renders_agents(harnesses: list[str]) -> bool:
    """True when any harness has a project agent directory + emitter."""
    return any(h in agents.PROJECT_AGENT_DIRS for h in harnesses)


def _prerender_agents(
    stacks: list[str], harnesses: list[str], agent_sources: tuple[Path, Path], tools: dict,
) -> dict[str, str]:
    """Every agent definition of the project, rendered in memory in the form
    the lean-ctx verdict selects (CR-MDB-045 §S8). A render failure — a
    missing or unreadable built-in passages file, a definition still naming
    lean-ctx — is a :class:`ScaffoldError`, raised before any write."""
    try:
        return agents.render_definitions(
            stacks, harnesses, *agent_sources,
            lean_ctx=tools.get("lean-ctx") == TOOL_PRESENT)
    except agents.AgentRenderError as exc:
        raise ScaffoldError(f"agent definitions cannot be rendered: {exc}") from exc


def _prerender_stack_skills(
    stacks: list[str], agent_sources: tuple[Path, Path],
) -> tuple[dict[str, str], dict[str, list[str]]]:
    """The project's stack skills (CR-MDB-085 §S1), from the ``generator/``
    directory of the asset root the agent sources resolved from: every file
    rendered in memory (keyed by project-relative path), and each stack's
    rendered skill names for the ``AGENTS.md`` stack line. A declaration or
    source that cannot be rendered is a :class:`ScaffoldError`, raised before
    any write."""
    generator_dir = agent_sources[0].parent
    try:
        texts = stack_skills.render_skills(generator_dir, stacks)
        declared = stack_skills.skills_for(
            stack_skills.load_declaration(generator_dir), stacks)
    except stack_skills.StackSkillError as exc:
        raise ScaffoldError(f"stack skills cannot be rendered: {exc}") from exc
    rendered = {rel.split("/")[2] for rel in texts}
    names = {stack: [n for n in found if n in rendered] for stack, found in declared.items()}
    return texts, names


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
    agent_texts: dict[str, str] | None = None,
    force_managed: bool = False,
    ownership: dict | None = None,
    schema: list[dict],
    registry: dict,
    tools: dict | None = None,
    tool_states: dict | None = None,
    release_texts: dict[str, str] | None = None,
    release_setup: list[str] | None = None,
    skill_texts: dict[str, str] | None = None,
    skill_names: dict[str, list[str]] | None = None,
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
    renders no agent definitions. ``agent_texts`` is every definition
    :func:`run_init` rendered in memory during validation (CR-MDB-045
    §S8); emission writes only that text.

    ``ownership``, when given, receives the permission policy's
    ``skipped`` (hand-edited) and ``unmanaged`` paths (CR-MDB-037 §S3).

    ``schema``/``registry`` are the project-settings schema and the values
    :func:`run_init` resolved from it in validation (CR-MDB-043 §S2).

    ``tools``/``tool_states`` are the installation's recorded verdicts
    (:func:`read_tool_verdicts`, :func:`_tool_key_states`): they shape the
    capability contract and the setup tasks, and the agents take the
    lean-ctx form only when lean-ctx is present (CR-MDB-045 §S5/§S8).

    ``release_texts`` is the release workflow and its two scripts
    :func:`run_init` rendered in validation, written at the root under the
    ownership rules; ``release_setup`` their setup tasks, carried by the
    root ``AGENTS.md``'s Setup section (CR-MDB-068 §S5).

    ``skill_texts`` is the stack skills :func:`run_init` rendered in
    validation, written at the root under the ownership rules; ``skill_names``
    each stack's skills, named by the ``AGENTS.md`` stack line (CR-MDB-085
    §S1.3/§S1.5)."""
    if emitted is None:
        emitted = []
    tools = tools or {}
    knowledge_category = registry["KNOWLEDGE_CATEGORY"]

    def write(rel: str, text: str) -> None:
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(path, text.encode("utf-8"))
        emitted.append(rel)

    def write_envrc(rel: str) -> None:
        """CR-MDB-047 \u00a7S2: ``.envrc`` (exactly :data:`ENVRC_TEXT`) beside a
        ``.env``, so direnv loads it. One already reading so is left as it
        is; one with other content is the user's \u2014 left alone and reported
        as unmanaged, under the ownership rules."""
        path = target / rel
        if path.is_file() or path.is_symlink():
            if path.is_file() and path.read_text(encoding="utf-8") == ENVRC_TEXT:
                return
            if ownership is not None:
                ownership.setdefault("unmanaged", []).append(rel)
            return
        write(rel, ENVRC_TEXT)

    def write_changelog() -> None:
        """CR-MDB-058 §S5: the root ``CHANGELOG.md`` skeleton
        (:data:`CHANGELOG_TEXT`). One already byte-identical to it is left as
        it is, reported nowhere, as an identical ``.envrc`` is; any other
        existing one is the project's own — left byte for byte and reported
        as unmanaged, as ``.envrc`` is."""
        path = target / CHANGELOG_NAME
        if path.exists() or path.is_symlink():
            if path.is_file() and path.read_bytes() == CHANGELOG_TEXT.encode("utf-8"):
                return
            if ownership is not None:
                ownership.setdefault("unmanaged", []).append(CHANGELOG_NAME)
            return
        write(CHANGELOG_NAME, CHANGELOG_TEXT)

    target.mkdir(parents=True, exist_ok=True)

    # §S3.1 registry + §S3.5 .gitignore.
    write(".env", _render_env(schema, registry))
    write_envrc(".envrc")
    write(".env.local", _render_env_local(schema, registry))
    write(".gitignore", _render_gitignore())
    # CR-MDB-057 §S2: one crucible.toml, at the root only — a monorepo
    # sub-project gets none (the client resolves to the repository root).
    write(CRUCIBLE_TOML_NAME, CRUCIBLE_TOML_TEXT)
    # CR-MDB-058 §S5: one CHANGELOG.md, at the root only — a sub-project
    # gets none.
    write_changelog()

    # §S3.2 docs model; CR-MDB-048 §S2: no queue README — the Crucible
    # board holds the queue, docs/changes/ the specs.
    write("docs/changes/.gitkeep", "")
    write("docs/research/.gitkeep", "")

    # §S3.3 AGENTS.md (Pi reads it natively — no anchor file).
    write(
        "AGENTS.md",
        _render_agents_md(name, token, acronym, mode, owner, stacks, harnesses,
                          knowledge_category, registry.get("SANDESH_PROJECT"),
                          tool_states, tools, release_setup,
                          stack_skill_names=skill_names),
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
                lean_ctx=tools.get("lean-ctx") == TOOL_PRESENT, rendered=agent_texts,
            )
        finally:
            emitted.extend(agent_report.get("written", []))

    # CR-MDB-085 §S1.3: the stack skills, at the root only, under the
    # agent definitions' ownership rules.
    if skill_texts:
        skill_report: dict = {}
        try:
            stack_skills.place_skills(target, skill_texts, force_managed, skill_report)
        finally:
            emitted.extend(skill_report.get("written", []))
            if ownership is not None:
                for key in ("skipped", "unmanaged"):
                    ownership.setdefault(key, []).extend(skill_report.get(key, []))

    # CR-MDB-037 §S3: the workflow permission policy, for a Pi project,
    # under the CR-MDB-025 §S6 ownership rules.
    if "pi" in harnesses:
        policy_report: dict = {}
        try:
            permission_policy.place_project_policy(
                target, force_managed=force_managed, report=policy_report,
                lean_ctx=tools.get("lean-ctx") == TOOL_PRESENT,
            )
        finally:
            emitted.extend(policy_report.get("written", []))
            if ownership is not None:
                for key in ("skipped", "unmanaged"):
                    ownership.setdefault(key, []).extend(policy_report.get(key, []))

    # CR-MDB-068 §S5: the release workflow and its two scripts, at the root
    # only, under the same ownership rules.
    if release_texts is not None:
        release_report: dict = {}
        try:
            _place_release_files(target, release_texts, force_managed, release_report)
        finally:
            emitted.extend(release_report.get("written", []))
            if ownership is not None:
                for key in ("skipped", "unmanaged"):
                    ownership.setdefault(key, []).extend(release_report.get(key, []))

    # §S3 monorepo: per-sub-project registry + override.
    for sub in sub_projects:
        write(f"{sub}/.env", _render_env(schema, registry, sub=True))
        write_envrc(f"{sub}/.envrc")
        write(f"{sub}/AGENTS.md",
              _render_sub_agents_md(name, sub, token, acronym, knowledge_category))

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
        schema = load_schema(PROJECT_SCHEMA_PATH)
        missing = [
            flag for dest, flag in _required_flags(schema)
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
        # CR-MDB-045 §S2: the installation's recorded verdicts, read from
        # install.toml before any project value is rendered — never probed.
        install = load_install_toml(home)
        tools, unrecorded = read_tool_verdicts(install, stacks)
        tool_states = _tool_key_states(install, stacks)
        not_applied = _overrides_not_applied(schema, tools, vars(args))
        schema = _active_schema(schema, tools)
        # CR-MDB-043 §S2: derive + validate every registry value BEFORE
        # any write (and before --dry-run reports them).
        registry = resolve_registry(schema, vars(args))
    except (ScaffoldError, UnknownHarnessError) as exc:
        print(f"modelb-axi: error: {exc}", file=sys.stderr)
        print(envelope("init", False, warnings=[str(exc)], dry_run=dry_run))
        return 2

    target = Path(args.target).expanduser()
    plan = plan_files(sub_projects)
    print(f"  harnesses ({harness_source}): {', '.join(harnesses)}", file=sys.stderr)
    print(f"  plan: {len(plan)} files under {target}", file=sys.stderr)
    if unrecorded:
        print(
            f"  note: {INSTALL_TOML_NAME} records no verdict for {', '.join(unrecorded)} "
            "— treated as unknown and not set up; re-run the installer (modelb-axi) "
            "to record them",
            file=sys.stderr,
        )
    for note in not_applied:
        print(f"  note: {note}", file=sys.stderr)

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
            # CR-MDB-062 §S7: once the store resolves, every emitted hook's
            # script must be an executable file there — same refuse-or-warn
            # rule; an unresolved store keeps today's error alone.
            _check_hook_scripts(hook_scripts_root, _hook_instances(stacks, args.mode))
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

    # CR-MDB-045 §S8: every agent is rendered in memory now, in the form
    # the lean-ctx verdict selects — a render failure is refused before the
    # first write, --dry-run included; emission writes only this text.
    agent_texts: dict[str, str] | None = None
    skill_texts: dict[str, str] | None = None
    skill_names: dict[str, list[str]] | None = None
    if agent_sources is not None:
        try:
            agent_texts = _prerender_agents(stacks, harnesses, agent_sources, tools)
            # CR-MDB-085 §S1.3: the stack skills too, before the first write.
            skill_texts, skill_names = _prerender_stack_skills(stacks, agent_sources)
        except ScaffoldError as exc:
            print(f"modelb-axi: error: {exc}", file=sys.stderr)
            print(envelope("init", False, warnings=[str(exc)], dry_run=dry_run))
            return 2

    # CR-MDB-068 §S5: the release workflow and its two scripts are rendered
    # in memory now — a render failure is refused before the first write,
    # --dry-run included; emission writes only this text.
    release_targets = _release_targets(registry.get(RELEASE_TARGETS_KEY, ""))
    try:
        release_texts = workflows.render(stacks, release_targets, _workflow_sources(home))
    except (ScaffoldError, OSError, ValueError) as exc:
        message = f"the release workflow cannot be rendered: {exc}"
        print(f"modelb-axi: error: {message}", file=sys.stderr)
        print(envelope("init", False, warnings=[message], dry_run=dry_run))
        return 2
    release_setup = release_setup_tasks(stacks, release_targets)

    emitted: list[str] = []
    ownership: dict = {"skipped": [], "unmanaged": []}
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
                agent_texts=agent_texts,
                force_managed=bool(getattr(args, "force_managed", False)),
                ownership=ownership,
                schema=schema,
                registry=registry,
                tools=tools,
                tool_states=tool_states,
                release_texts=release_texts,
                release_setup=release_setup,
                skill_texts=skill_texts,
                skill_names=skill_names,
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
            "recorded in AGENTS.md's Setup section",
            file=sys.stderr,
        )

    # CR-MDB-037 §S3: a policy left alone under the ownership rules is
    # reported, in the wording `agents` uses for its own files.
    for warning in _ownership_warnings(ownership["skipped"], ownership["unmanaged"]):
        print(f"modelb-axi: warning: {warning}", file=sys.stderr)
        plan_warnings.append(warning)

    # CR-MDB-037 §S4: report Pi's saved trust decision whenever this run
    # wrote under .pi/extensions/ (read-only; never edits trust.json).
    trust_fields: dict = {}
    extensions_prefix = f"{Path('.pi') / 'extensions'}/"
    if any(rel.startswith(extensions_prefix) for rel in emitted):
        trust = project_trust.resolve_trust(target, resolve_agent_dir())
        trust_fields["trust"] = trust
        if trust in (project_trust.UNTRUSTED, project_trust.ASK):
            warning = project_trust.UNTRUSTED_WARNING.format(state=trust)
            print(f"modelb-axi: warning: {warning}", file=sys.stderr)
            plan_warnings.append(warning)

    # CR-MDB-043 §S2: a captured key init leaves empty (the Crucible
    # project key) is reported, dry run or not — it is a setup step, not
    # a warning.
    setup_required = _setup_required(schema, registry)
    for row in setup_required:
        print(f"  setup required: {row['key']} in {row['file']} is {row['note']}",
              file=sys.stderr)

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
            registry=registry,
            tools=tools,
            setup_required=setup_required,
            release_setup=release_setup,
            skipped=ownership["skipped"],
            unmanaged=ownership["unmanaged"],
            **trust_fields,
        )
    )
    return 0


def _read_env_value(env_path: Path, key: str) -> str | None:
    """The value of ``key`` in a ``KEY=VALUE`` registry file, or None. A
    double-quoted value (how :func:`_render_registry` writes one containing
    whitespace, CR-MDB-047 §S2) is returned without its quotes."""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, _, value = stripped.partition("=")
        if name.strip() == key:
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] == '"':
                value = value[1:-1]
            return value
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
    listing written, unchanged, skipped and unmanaged files. For a Pi
    project the permission policy is placed after the agents, under the same
    ownership rules and recorded lean-ctx verdict (CR-MDB-077 §S3). Returns
    the process exit code."""
    print("modelb-axi: agents — re-render project agent definitions and the "
          "permission policy", file=sys.stderr)
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
            # CR-MDB-043 §S2: read through the schema reader.
            recorded = read_registry_value(
                root, load_schema(PROJECT_SCHEMA_PATH), PROJECT_STACKS_KEY)
            if not recorded:
                raise ScaffoldError(
                    f"{env_path} records no {PROJECT_STACKS_KEY}; pass "
                    "--stacks <csv> to render and record the project's stacks"
                )
            stacks = parse_stacks(recorded)
        harnesses, harness_source = resolve_harnesses(home, None)
        templates_dir, stacks_dir = _agent_sources(home)
        # CR-MDB-045 §S8: the agents match the installation's recorded
        # lean-ctx verdict, read on every run (never probed).
        tools, _unrecorded = read_tool_verdicts(load_install_toml(home), stacks)
        # CR-MDB-045 §S8: rendered in memory before the first write.
        agent_texts = _prerender_agents(stacks, harnesses, (templates_dir, stacks_dir), tools)
        # CR-MDB-085 §S1.4: the stack skills, rendered with the agents and
        # before the first write — only where the agent definitions render.
        skill_texts = (_prerender_stack_skills(stacks, (templates_dir, stacks_dir))[0]
                       if _renders_agents(harnesses) else {})
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
            lean_ctx=tools.get("lean-ctx") == TOOL_PRESENT, rendered=agent_texts,
        )
        # CR-MDB-085 §S1.4: the stack skills, by the same rules; a re-render
        # writes and never deletes.
        stack_skills.place_skills(root, skill_texts, force_managed, report)
        # CR-MDB-077 §S3: the permission policy, for a Pi project, as
        # `init` places it; reported beside the agent files.
        if "pi" in harnesses:
            permission_policy.place_project_policy(
                root, force_managed=force_managed, report=report,
                lean_ctx=tools.get("lean-ctx") == TOOL_PRESENT,
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
    warnings += _ownership_warnings(report["skipped"], report["unmanaged"])
    for stack in report["no_definitions"]:
        warnings.append(f"stack {stack!r} has no agent definitions; none rendered")
    # CR-MDB-068 §S6: a new stack set does not re-render a managed release
    # workflow — say so, and name the verb that does.
    if requested and _managed_release_workflow(root):
        warnings.append(
            f"{workflows.RELEASE_YML} is not re-rendered for the new stacks; run "
            "`modelb-axi release-workflow` to re-render it"
        )
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


def _release_registry(root: Path, requested: str | None,
                      targets_hint: str) -> tuple[list[str], str]:
    """``(stacks, canonical RELEASE_TARGETS value)`` of the project at ``root``, read from its
    ``.env`` through the schema reader and validated as ``init`` validates them — shared by the
    ``release-workflow`` and ``release-check`` verbs (CR-MDB-068 §S6, CR-MDB-071 §S5).
    ``requested`` (a ``--release-targets`` value) replaces the recorded targets; ``targets_hint``
    ends the refusal of an absent ``RELEASE_TARGETS``. Raises :class:`ScaffoldError`."""
    env_path = root / ".env"
    schema = load_schema(PROJECT_SCHEMA_PATH)
    recorded_stacks = read_registry_value(root, schema, PROJECT_STACKS_KEY)
    if not recorded_stacks:
        raise ScaffoldError(
            f"{env_path} records no {PROJECT_STACKS_KEY}; set the project's stacks "
            "with `modelb-axi agents --stacks <csv>`"
        )
    stacks = parse_stacks(recorded_stacks)
    value = requested
    if value is None:
        value = read_registry_value(root, schema, RELEASE_TARGETS_KEY)
        if value is None:
            raise ScaffoldError(f"{env_path} records no {RELEASE_TARGETS_KEY}; {targets_hint}")
    try:
        value = _check_release_targets_csv(value)
    except ValueError as exc:
        raise ScaffoldError(
            f"{RELEASE_TARGETS_KEY} (--release-targets): value {value!r} {exc}") from exc
    return stacks, value


def run_release_workflow(args: argparse.Namespace, home: Path,
                         project_root: Path | None = None) -> int:
    """Entry for the ``release-workflow`` subcommand (CR-MDB-068 §S6): re-render
    the release workflow and its two scripts of the project in the current
    directory from its ``PROJECT_STACKS`` and ``RELEASE_TARGETS``;
    ``--release-targets`` replaces the set and records it in ``.env``. The
    files are rendered in memory, then written under the ownership rules.
    Emits one AXI envelope (verb ``release-workflow``); exit 2 on a refusal,
    3 on an I/O error."""
    print("modelb-axi: release-workflow — re-render the project's release workflow",
          file=sys.stderr)
    root = project_root if project_root is not None else Path.cwd()
    env_path = root / ".env"
    requested = getattr(args, "release_targets", None)
    force_managed = bool(getattr(args, "force_managed", False))
    try:
        if not env_path.is_file():
            raise ScaffoldError(
                f"no .env in {root}; run `modelb-axi release-workflow` from the root "
                "of a project scaffolded by `modelb-axi init`"
            )
        stacks, value = _release_registry(
            root, requested,
            "pass --release-targets <csv> (or \"\" for no target) to render and "
            "record where a release publishes")
        targets = _release_targets(value)
        try:
            texts = workflows.render(stacks, targets, _workflow_sources(home))
        except (OSError, ValueError) as exc:
            raise ScaffoldError(f"the release workflow cannot be rendered: {exc}") from exc
    except ScaffoldError as exc:
        print(f"modelb-axi: error: {exc}", file=sys.stderr)
        print(envelope("release-workflow", False, warnings=[str(exc)], project=str(root)))
        return 2

    print(f"  stacks: {', '.join(stacks)}", file=sys.stderr)
    print(f"  targets: {', '.join(targets) or '(none)'}", file=sys.stderr)
    report: dict = {}
    try:
        _place_release_files(root, texts, force_managed, report)
        if requested is not None:
            _set_env_value(env_path, RELEASE_TARGETS_KEY, value)
    except OSError as exc:
        print(f"modelb-axi: error: {exc}", file=sys.stderr)
        print(envelope(
            "release-workflow", False, warnings=[str(exc)], project=str(root), **report,
        ))
        return 3

    warnings = _ownership_warnings(report["skipped"], report["unmanaged"])
    for message in warnings:
        print(f"modelb-axi: warning: {message}", file=sys.stderr)
    print(envelope(
        "release-workflow", True,
        warnings=warnings,
        project=str(root),
        stacks=stacks,
        targets=targets,
        force_managed=force_managed,
        **report,
    ))
    return 0


# ------------------------------------------------------------ release-check (CR-MDB-071 §S5) ----

#: The three areas and three states of a ``release-check`` item.
_AREA_LOCAL, _AREA_GITHUB, _AREA_REGISTRY = "local", "github", "registry"
_READY, _MISSING, _UNKNOWN = "ready", "missing", "unknown"
#: What a stale or absent rendered file's detail tells the user to run.
_RERENDER = "run `modelb-axi release-workflow`"
#: Each stack's release prerequisite and each target's: ``(project-relative path, kind)``, the
#: kind ``dir``, ``file`` or ``exec`` (an executable file). Two owners of one path check it once.
_STACK_PREREQUISITES: dict[str, tuple[str, str]] = {
    "python": ("tests/", "dir"), "bun": ("bun.lock", "file"), "rust": ("Cargo.lock", "file"),
    "quarkus": ("mvnw", "exec"), "java": ("mvnw", "exec"),
    "arduino": (".github/scripts/ci-test", "exec"),
}
_TARGET_PREREQUISITES: dict[str, tuple[str, str]] = {
    "maven-central": ("mvnw", "exec"),
    "github-assets": (".github/scripts/build-assets", "exec"),
}
#: The stacks whose test job builds a target; a target not listed needs no particular stack.
_TARGET_BUILDERS: dict[str, tuple[str, ...]] = {
    "crates": ("rust",), "maven-central": ("java", "quarkus"),
}
#: Each target's GitHub environments, as its rendered jobs name them.
_TARGET_ENVIRONMENTS: dict[str, tuple[str, ...]] = {
    "pypi": ("pypi", "testpypi"), "npm": ("npm",), "crates": ("crates",),
    "maven-central": ("maven-central",),
}
#: The rehearsal's environment and the branch patterns it must admit (compared, never evaluated).
_REHEARSAL_ENVIRONMENT = "testpypi"
_REHEARSAL_BRANCHES = ("release/**", "hotfix/**")
#: The secret every rendered workflow's ``create-release`` job needs.
_RELEASE_PAT = "RELEASE_PAT"
#: First-publish tokens: absent, they are unknown (a trusted publisher replaces them).
_FIRST_PUBLISH_TOKENS = frozenset({"NPM_TOKEN", "CARGO_REGISTRY_TOKEN"})
_SECRET_REF = re.compile(r"secrets\.([A-Z][A-Z0-9_]*)")
_SECRETS_SCOPE = "organisation and environment secrets are not read"
#: The three GitHub origin forms, each with or without ``.git``: the one origin-URL parser.
_GITHUB_ORIGIN = re.compile(
    r"(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)"
    r"([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?")
_UNRELEASED = re.compile(r"^##[ \t]*\[Unreleased\]", re.M)
_SUBPROCESS_TIMEOUT = 60


def _check_item(area: str, item: str, state: str, detail: str) -> dict:
    return {"area": area, "item": item, "state": state, "detail": detail}


def _no_env_refusal(root: Path, verb: str) -> str:
    """The refusal of a directory holding no ``.env``, naming where to run ``verb`` from: the
    nearest enclosing directory holding one, when there is one."""
    holder = next((p for p in root.parents if (p / ".env").is_file()), None)
    where = (f"run it from {holder}" if holder is not None
             else "run it from the project's root, the directory holding .env")
    return f"no .env in {root}; `modelb-axi {verb}` reads the project's .env: {where}"


def _github_repository(url: str) -> tuple[str, str] | None:
    """``(owner, repository)`` of a GitHub origin URL in one of the three forms
    (``https://github.com/o/r``, ``git@github.com:o/r``, ``ssh://git@github.com/o/r``, each with
    or without ``.git``); None for any other URL (CR-MDB-071 §S5)."""
    match = _GITHUB_ORIGIN.fullmatch(url.strip())
    return (match.group(1), match.group(2)) if match else None


def _origin_repository(root: Path) -> tuple[tuple[str, str] | None, str]:
    """``(repository or None, why not)`` from ``git remote get-url origin`` in ``root``."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"], cwd=str(root), capture_output=True,
            text=True, timeout=_SUBPROCESS_TIMEOUT, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"`git remote get-url origin` failed ({exc}); GitHub not read"
    if result.returncode != 0:
        return None, "no origin remote; GitHub not read"
    repository = _github_repository(result.stdout)
    if repository is None:
        return None, "the origin remote is not on github.com; GitHub not read"
    return repository, ""


def _json_documents(text: str) -> list:
    """Every JSON document in ``text`` (``gh api --paginate`` prints one per page). Raises
    ``ValueError`` when there is none or one does not parse."""
    decoder, documents, index = json.JSONDecoder(), [], 0
    while True:
        while index < len(text) and text[index].isspace():
            index += 1
        if index == len(text):
            break
        document, index = decoder.raw_decode(text, index)
        documents.append(document)
    if not documents:
        raise ValueError("no JSON document")
    return documents


def _listed(documents: list, key: str) -> list[dict]:
    """The ``key`` list of every page, joined. Raises ``ValueError`` on another shape."""
    entries: list[dict] = []
    for document in documents:
        page = document.get(key) if isinstance(document, dict) else None
        if not isinstance(page, list) or not all(isinstance(e, dict) for e in page):
            raise ValueError(f"no {key!r} list")
        entries.extend(page)
    return entries


def _gh_list(gh: str | None, path: str, key: str, root: Path) -> tuple[list[dict] | None, str]:
    """``(entries, "")`` of ``gh api --method GET --paginate <path>``'s ``key`` list, or
    ``(None, error)``: no ``gh``, a failed run (its stderr) or unparseable output."""
    if gh is None:
        return None, "gh is not on PATH: install GitHub CLI and run `gh auth login`"
    try:
        result = subprocess.run(
            [gh, "api", "--method", "GET", "--paginate", path], cwd=str(root),
            capture_output=True, text=True, timeout=_SUBPROCESS_TIMEOUT,
            stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"gh api {path}: {exc}"
    if result.returncode != 0:
        error = " ".join(result.stderr.split()) or f"exit {result.returncode}"
        return None, f"gh api {path} failed: {error}"
    try:
        return _listed(_json_documents(result.stdout), key), ""
    except ValueError as exc:
        return None, f"gh api {path}: unparseable output ({exc})"


def _environment_item(gh: str | None, base: str, name: str, environment: dict | None,
                      root: Path) -> dict:
    """One environment's item: present, and admitting the version tags (a publish environment)
    or the release and hotfix branches (the rehearsal's). Patterns are compared, not evaluated."""
    item = f"environment {name}"
    if environment is None:
        return _check_item(_AREA_GITHUB, item, _MISSING,
                           f"create the {name} environment in the repository settings")
    rehearsal = name == _REHEARSAL_ENVIRONMENT
    admits = ("the release and hotfix branches" if rehearsal else "the version tags")
    policy = environment.get("deployment_branch_policy")
    if policy is None:
        return _check_item(_AREA_GITHUB, item, _READY,
                           "no deployment-branch policy: every branch and tag is admitted")
    if not isinstance(policy, dict):
        return _check_item(_AREA_GITHUB, item, _UNKNOWN,
                           f"unparseable deployment_branch_policy: {policy!r}")
    if policy.get("protected_branches"):
        return _check_item(_AREA_GITHUB, item, _MISSING,
                           f"admits protected branches only, not {admits}")
    path = f"{base}/environments/{name}/deployment-branch-policies"
    policies, error = _gh_list(gh, path, "branch_policies", root)
    if policies is None:
        return _check_item(_AREA_GITHUB, item, _UNKNOWN, error)
    patterns = [(str(p.get("type") or "branch"), str(p.get("name", ""))) for p in policies]
    if rehearsal:
        branches = {pattern for kind, pattern in patterns if kind == "branch"}
        absent = [b for b in _REHEARSAL_BRANCHES if b not in branches]
        if absent:
            return _check_item(_AREA_GITHUB, item, _MISSING,
                               f"add the branch policies {', '.join(absent)} so it admits "
                               f"{admits} (patterns compared, not evaluated)")
        return _check_item(_AREA_GITHUB, item, _READY,
                           f"branch policies {', '.join(_REHEARSAL_BRANCHES)} admit {admits}")
    tags = [pattern for kind, pattern in patterns if kind == "tag"]
    if not tags:
        return _check_item(_AREA_GITHUB, item, _MISSING,
                           f"no tag policy: add one admitting {admits}")
    return _check_item(_AREA_GITHUB, item, _READY,
                       f"tag policies (not evaluated): {', '.join(tags)}")


def _github_check_items(root: Path, names: list[str], secrets: list[str],
                        repository: tuple[str, str] | None, why: str) -> list[dict]:
    """Each target's environment and each repository secret the rendered jobs name."""
    environments = [env for name in names for env in _TARGET_ENVIRONMENTS.get(name, ())]
    if repository is None:
        return ([_check_item(_AREA_GITHUB, f"environment {env}", _UNKNOWN, why)
                 for env in environments]
                + [_check_item(_AREA_GITHUB, f"secret {secret}", _UNKNOWN,
                               f"{why}; {_SECRETS_SCOPE}") for secret in secrets])
    base = f"repos/{repository[0]}/{repository[1]}"
    gh = shutil.which("gh")
    items: list[dict] = []
    if environments:
        listed, error = _gh_list(gh, f"{base}/environments", "environments", root)
        by_name = ({str(e.get("name")): e for e in listed} if listed is not None else None)
        for env in environments:
            items.append(_check_item(_AREA_GITHUB, f"environment {env}", _UNKNOWN, error)
                         if by_name is None
                         else _environment_item(gh, base, env, by_name.get(env), root))
    listed, error = _gh_list(gh, f"{base}/actions/secrets", "secrets", root)
    present = {str(s.get("name")) for s in listed} if listed is not None else None
    for secret in secrets:
        item = f"secret {secret}"
        if present is None:
            items.append(_check_item(_AREA_GITHUB, item, _UNKNOWN, f"{error}; {_SECRETS_SCOPE}"))
        elif secret in present:
            items.append(_check_item(_AREA_GITHUB, item, _READY,
                                     f"a repository secret; {_SECRETS_SCOPE}"))
        elif secret in _FIRST_PUBLISH_TOKENS:
            items.append(_check_item(
                _AREA_GITHUB, item, _UNKNOWN,
                "not a repository secret: needed only for the first publish, not once the "
                f"trusted publisher exists; {_SECRETS_SCOPE}"))
        else:
            items.append(_check_item(_AREA_GITHUB, item, _MISSING,
                                     f"add the repository secret {secret}; {_SECRETS_SCOPE}"))
    return items


def _registry_check_items(names: list[str], repository: tuple[str, str] | None) -> list[dict]:
    """Each target's registry publisher: never read, so ``unknown``, naming the fields to check."""
    where = (f"owner {repository[0]}, repository {repository[1]}" if repository is not None
             else "this repository's owner and name")

    def publisher(registry: str, environment: str) -> str:
        return (f"not read; check on {registry}: {where}, workflow release.yml, "
                f"environment {environment}")
    publishers: dict[str, list[tuple[str, str]]] = {
        "pypi": [("PyPI trusted publisher", publisher("PyPI", "pypi")),
                 ("TestPyPI trusted publisher", publisher("TestPyPI", "testpypi"))],
        "npm": [("npm trusted publisher", publisher("npmjs.com (the package's settings)",
                                                    "npm"))],
        "crates": [("crates.io trusted publisher",
                    publisher("crates.io (the crate's settings)", "crates"))],
        "maven-central": [("Central Portal namespace", (
            "not read; check on the Central Portal: the namespace (the POM's groupId) is "
            "verified, the user token behind MAVEN_CENTRAL_USERNAME and MAVEN_CENTRAL_PASSWORD "
            "is live, and the public key of MAVEN_GPG_PRIVATE_KEY is on a public keyserver"))],
    }
    return [_check_item(_AREA_REGISTRY, item, _UNKNOWN, detail)
            for name in names for item, detail in publishers.get(name, [])]


def _rendered_file_item(root: Path, rel: str, text: str) -> dict:
    """A rendered file against the render for the current ``.env``."""
    path = root / rel
    if not path.is_file():
        return _check_item(_AREA_LOCAL, rel, _MISSING, f"absent; {_RERENDER}")
    current = path.read_bytes().decode("utf-8", errors="replace")
    if current == text:
        return _check_item(_AREA_LOCAL, rel, _READY, "equals the render for the current .env")
    state = workflows.ownership_state(current)
    if state == agents.OWNED_HAND_MODIFIED:
        return _check_item(_AREA_LOCAL, rel, _READY,
                           "note: hand-modified (its marker digest does not match), so not "
                           "compared with the render; `modelb-axi release-workflow` skips it "
                           "unless --force-managed")
    if state == agents.NOT_OWNED:
        return _check_item(_AREA_LOCAL, rel, _MISSING,
                           f"carries no Model B marker; move it aside and {_RERENDER}")
    return _check_item(_AREA_LOCAL, rel, _MISSING,
                       f"differs from the render for the current .env; {_RERENDER}")


def _version_item(root: Path, target: str) -> dict:
    """A versioned target's version, read by the project's own rendered ``stamp_version.py``."""
    item = f"version {target}"
    if not (root / workflows.STAMP_SCRIPT).is_file():
        return _check_item(_AREA_LOCAL, item, _UNKNOWN,
                           f"{workflows.STAMP_SCRIPT} is absent; {_RERENDER}")
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        result = subprocess.run(
            [sys.executable or "python3", workflows.STAMP_SCRIPT, "read", target],
            cwd=str(root), env=environment, capture_output=True, text=True,
            timeout=_SUBPROCESS_TIMEOUT, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _check_item(_AREA_LOCAL, item, _UNKNOWN, f"{workflows.STAMP_SCRIPT}: {exc}")
    if result.returncode != 0:
        return _check_item(_AREA_LOCAL, item, _MISSING,
                           result.stderr.strip() or f"exit {result.returncode}")
    version = result.stdout.strip().rpartition("\t")[2]
    return _check_item(_AREA_LOCAL, item, _READY,
                       f"{version} (read by {workflows.STAMP_SCRIPT})")


def _prerequisite_items(root: Path, stacks: list[str], names: list[str]) -> list[dict]:
    """Each stack's and target's prerequisite, each path once."""
    owners: dict[str, tuple[str, list[str]]] = {}
    for owner, (rel, kind) in ([(f"the {s} stack", _STACK_PREREQUISITES[s])
                                for s in stacks if s in _STACK_PREREQUISITES]
                               + [(f"the {n} target", _TARGET_PREREQUISITES[n])
                                  for n in names if n in _TARGET_PREREQUISITES]):
        owners.setdefault(rel, (kind, []))[1].append(owner)
    items = []
    for rel, (kind, needers) in owners.items():
        path, needed = root / rel, f"needed by {' and '.join(needers)}"
        if kind == "dir":
            present = path.is_dir()
        else:
            present = path.is_file()
        if not present:
            items.append(_check_item(_AREA_LOCAL, f"prerequisite {rel}", _MISSING,
                                     f"absent; {needed}"))
        elif kind == "exec" and not os.access(path, os.X_OK):
            items.append(_check_item(_AREA_LOCAL, f"prerequisite {rel}", _MISSING,
                                     f"not executable (chmod +x); {needed}"))
        else:
            items.append(_check_item(_AREA_LOCAL, f"prerequisite {rel}", _READY, needed))
    return items


def _local_check_items(root: Path, stacks: list[str], parsed: list[tuple[str, str]],
                       texts: dict[str, str]) -> list[dict]:
    """The rendered files, the versions, the prerequisites, the test jobs and the changelog."""
    names = [name for name, _directory in parsed]
    items = [_rendered_file_item(root, rel, text) for rel, text in texts.items()]
    items += [_version_item(root, f"{name}:{directory}") for name, directory in parsed
              if name in workflows._VERSIONED]
    items += _prerequisite_items(root, stacks, names)
    for name in names:
        builders = _TARGET_BUILDERS.get(name)
        if builders is None:
            continue
        building = [stack for stack in stacks if stack in builders]
        items.append(
            _check_item(_AREA_LOCAL, f"test job for {name}", _READY,
                        f"built by the {building[0]} stack's test job") if building
            else _check_item(_AREA_LOCAL, f"test job for {name}", _MISSING,
                             f"no test job builds {name}: add the {' or '.join(builders)} "
                             "stack (`modelb-axi agents --stacks <csv>`, then "
                             "`modelb-axi release-workflow`)"))
    changelog = root / CHANGELOG_NAME
    if not changelog.is_file():
        items.append(_check_item(_AREA_LOCAL, CHANGELOG_NAME, _MISSING,
                                 "absent; add it with a `## [Unreleased]` section"))
    elif _UNRELEASED.search(changelog.read_bytes().decode("utf-8", errors="replace")):
        items.append(_check_item(_AREA_LOCAL, CHANGELOG_NAME, _READY,
                                 "has an [Unreleased] section"))
    else:
        items.append(_check_item(_AREA_LOCAL, CHANGELOG_NAME, _READY,
                                 "note: no [Unreleased] section to release from"))
    return items


def run_release_check(args: argparse.Namespace, home: Path,
                      project_root: Path | None = None) -> int:
    """Entry for the ``release-check`` subcommand (CR-MDB-071 §S5): report the release readiness
    of the project in the current directory — its local items, its GitHub environments and
    secrets (``gh api --method GET``) and its registry checklist — as one AXI envelope (verb
    ``release-check``) with ``items`` and the counts ``ready``, ``missing`` and ``unknown``.
    Read-only: it writes nothing. Exit 0 when nothing is missing, 1 when anything is, 2 on a
    refusal."""
    print("modelb-axi: release-check — report the project's release readiness",
          file=sys.stderr)
    root = project_root if project_root is not None else Path.cwd()
    try:
        if not (root / ".env").is_file():
            raise ScaffoldError(_no_env_refusal(root, "release-check"))
        stacks, value = _release_registry(
            root, None,
            "record the targets with `modelb-axi release-workflow --release-targets <csv>` "
            "(\"\" for no target)")
        targets = _release_targets(value)
        try:
            texts = workflows.render(stacks, targets, _workflow_sources(home))
        except (OSError, ValueError) as exc:
            raise ScaffoldError(f"the release workflow cannot be rendered: {exc}") from exc
    except ScaffoldError as exc:
        print(f"modelb-axi: error: {exc}", file=sys.stderr)
        print(envelope("release-check", False, warnings=[str(exc)], project=str(root)))
        return 2

    parsed = [workflows.parse_target(target) for target in targets]
    names = [name for name, _directory in parsed]
    # GITHUB_TOKEN is the run's own token, never a repository secret.
    secrets = sorted((set(_SECRET_REF.findall(texts[workflows.RELEASE_YML])) - {"GITHUB_TOKEN"})
                     | {_RELEASE_PAT})
    repository, why = _origin_repository(root)
    items = (_local_check_items(root, stacks, parsed, texts)
             + _github_check_items(root, names, secrets, repository, why)
             + _registry_check_items(names, repository))
    counts = {state: sum(1 for i in items if i["state"] == state)
              for state in (_READY, _MISSING, _UNKNOWN)}
    for i in items:
        print(f"  {i['state']:<7} {i['area']}: {i['item']} — {i['detail']}", file=sys.stderr)
    print(f"  {counts[_READY]} ready, {counts[_MISSING]} missing, {counts[_UNKNOWN]} unknown",
          file=sys.stderr)
    print(envelope(
        "release-check", True,
        warnings=[],
        project=str(root),
        stacks=stacks,
        targets=targets,
        items=items,
        **counts,
    ))
    return 1 if counts[_MISSING] else 0
