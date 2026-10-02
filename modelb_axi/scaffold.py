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
import re
import shlex
import subprocess
import sys
import tomllib
import unicodedata
from pathlib import Path

from modelb_axi import agents, permission_policy, project_trust, requirements
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
    e.g. ``--knowledge-category`` while lean-ctx is not present (CR-MDB-045
    \u00a7S4)."""
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
        "AGENTS.md",
        "docs/changes/.gitkeep",
        "docs/research/.gitkeep",
        "docs/memory/INDEX.md",
        "hooks/README.md",
    ]
    for sub in sub_projects:
        base += [f"{sub}/.env", f"{sub}/.envrc", f"{sub}/AGENTS.md"]
    return base


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


def _render_setup_section(mode: str, sandesh_project: str, tools: dict | None = None) -> str:
    """The root ``AGENTS.md``'s ``## Setup`` section (CR-MDB-048 §S2): the
    setup tasks the retired queue README carried, as they stood — the dated
    scaffold line, the manual Crucible registration (registrations are
    manual in scaffold v1), in multi mode the Sandesh and direnv task naming
    the project's Sandesh id and Mainline address from ``SANDESH_PROJECT``
    (CR-MDB-043 §S2, CR-MDB-047), and the ``REPO_OWNER`` check. Where
    ``tools`` records Sandesh or Crucible absent, its setup task names the
    tool's remediation first (CR-MDB-045 §S5)."""
    today = datetime.date.today().isoformat()
    tools = tools or {}
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
    return (
        "## Setup\n"
        "Pre-wave tasks — not a wave; a wave is a grouping of CRs.\n"
        "\n"
        f"- [x] Scaffold via `modelb-axi init` — {today}\n"
        f"- [ ] {_remediation_first(tools, 'crucible', 'Crucible')}"
        "Register the project in Crucible and paste the key into "
        "`.env` (`CRUCIBLE_PROJECT_KEY=`) — manual step "
        "(registrations are manual in scaffold v1)\n"
        f"{sandesh_task}"
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
    mentioned."""
    states = states or {}
    lines: list[str] = []

    def line(name: str, label: str, state: str, remediation: str) -> None:
        tail = "" if state == TOOL_PRESENT else f" — {remediation}"
        lines.append(f"- `{name}` ({label}): {state}{tail}")

    def worst(found: list[str]) -> str:
        return max(found, key=_TOOL_RANK.__getitem__)

    probes: dict[str, tuple[str, dict, list[str]]] = {}
    for stack in stacks:
        for probe in requirements.STACK_TOOLCHAINS.get(stack, ()):
            first = probes.setdefault(probe["name"], (stack, probe, []))
            first[2].append(states.get(f"{stack}.{probe['name']}", TOOL_UNKNOWN))
    for row in requirements.REQUIREMENTS:
        if row["scope"] == "always":
            remediation = (f"`{row['remediation']}`" if row["tier"] == 1
                           else row["remediation"])
            label, found = row["policy"], [states.get(row["id"], TOOL_UNKNOWN)]
            merged = probes.pop(row["id"], None)
            if merged is not None:
                label = f"{label}; {merged[0]} toolchain"
                found += merged[2]
            line(row["id"], label, worst(found), remediation)
        elif row["id"] == "crucible-client":
            for stack in (s for s in stacks if s in row["scope"]):
                line(row["id"], f"{stack} client, {row['policy']}",
                     states.get(f"{stack}.client", TOOL_UNKNOWN), row["remediation"])
        elif row["id"] == "toolchain":
            for name, (stack, probe, found) in probes.items():
                line(name, f"{stack} toolchain", worst(found), probe["remediation"])
    if "pi" in harnesses:
        # CR-MDB-037 §S4: Pi loads .pi/extensions only in a trusted project.
        lines.append(
            "- project trust (Pi): this project's hooks and permission "
            "policy under `.pi/extensions/` load only once the project is "
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
    orchestrator working it (CR-MDB-045 §S4): cached reads and the
    compressed shell, where execution knowledge is kept, and what
    bootstrap loads."""
    return (
        "## lean-ctx (for the orchestrator working this project)\n"
        "- Prefer lean-ctx's cached reads and compressed shell over the "
        "harness's built-in read and shell tools.\n"
        "- Keep this project's execution knowledge in lean-ctx's knowledge "
        f"store under the category `{category}` (`KNOWLEDGE_CATEGORY` in `.env`), "
        "through the session's knowledge capability. Never through the "
        "`lean-ctx knowledge` CLI: its project does not follow the working "
        "directory.\n"
        "- At bootstrap, load that category, and only that category: restore its "
        "archived facts, then list it.\n"
    )


def _render_agents_md(
    name: str, token: str, acronym: str, mode: str, owner: str,
    stacks: list[str], harnesses: list[str], sandesh_project: str | None = None,
    states: dict | None = None, knowledge_category: str | None = None,
    tools: dict | None = None,
) -> str:
    """Project ``AGENTS.md`` override (§S3.3/§S3.8): identity from the
    registry, the design-reference lines (the retired queue README's
    header slots, CR-MDB-048 §S2), workflow rules (incl. the post-036
    run-context note — workflow cycle env vars are never hand-set, and this
    file must not name them), the ``## Setup`` section from ``tools``
    (:func:`_render_setup_section`), stack-derived skill freeze,
    per-installed-harness anchor notes, the capability contract from the
    recorded ``states``, the lean-ctx section when ``knowledge_category``
    is set (CR-MDB-045 §S4/§S5), and the generator note."""
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
        f"- {stack}: use the `{stack}` stack skills and generated "
        f"RED/GREEN/VERIFY/FIX agents, rendered at scaffold time; re-render "
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
        + _render_setup_section(mode, sandesh_project or "", tools)
        + "\n"
        f"## Skill freeze (derived from --stacks: {', '.join(stacks)})\n"
        f"{stack_lines}\n"
        "\n"
        f"## Harness anchors (installed set: {', '.join(harnesses)})\n"
        + "\n".join(anchor_lines) + "\n"
        "\n"
        + _render_capability_contract(stacks, tuple(harnesses), states)
        + "\n"
        + (_render_lean_ctx_section(knowledge_category) + "\n" if knowledge_category else "")
        + "## Generator note\n"
        "- Agents regenerate from the INSTALLATION's generator assets — "
        "never from a per-project copy.\n"
    )


def _render_sub_agents_md(
    name: str, sub: str, token: str, acronym: str, knowledge_category: str | None = None,
) -> str:
    """Per-sub-project ``AGENTS.md`` override (§S3 monorepo); with
    ``knowledge_category`` — the category in the sub-project's own
    ``.env`` — it carries its own lean-ctx section (CR-MDB-045 §S4)."""
    lean_ctx = "\n" + _render_lean_ctx_section(knowledge_category) if knowledge_category else ""
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


#: Memory-template family prefix -> the stacks whose selection emits it
#: (CR-MDB-031 §S1): the quarkus agent definitions read the ``java-*``
#: templates, so a ``java-*`` template is emitted for ``java`` OR
#: ``quarkus``. A prefix absent here is stack-neutral.
MEMORY_TEMPLATE_FAMILIES: dict[str, frozenset[str]] = {
    "arduino": frozenset({"arduino"}),
    "java": frozenset({"java", "quarkus"}),
    "rust": frozenset({"rust"}),
}


def _select_memory_templates(templates_dir: Path, stacks: list[str]) -> list[Path]:
    """Filter templates by ``--stacks``: a ``<prefix>-*.md`` template of a
    family in :data:`MEMORY_TEMPLATE_FAMILIES` is emitted only when a stack
    of that family is selected; stack-neutral templates (e.g.
    ``operational-commands.md``) are always emitted."""
    selected = []
    for path in sorted(templates_dir.glob("*.md")):
        family = MEMORY_TEMPLATE_FAMILIES.get(path.name.split("-", 1)[0])
        if family is not None and not family & set(stacks):
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
    agent_texts: dict[str, str] | None = None,
    force_managed: bool = False,
    ownership: dict | None = None,
    schema: list[dict],
    registry: dict,
    tools: dict | None = None,
    tool_states: dict | None = None,
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
    lean-ctx form only when lean-ctx is present (CR-MDB-045 §S5/§S8)."""
    if emitted is None:
        emitted = []
    tools = tools or {}
    knowledge_category = registry.get("KNOWLEDGE_CATEGORY") or None

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

    templates = _select_memory_templates(_memory_templates_dir(home), stacks)
    target.mkdir(parents=True, exist_ok=True)

    # §S3.1 registry + §S3.5 .gitignore.
    write(".env", _render_env(schema, registry))
    write_envrc(".envrc")
    write(".env.local", _render_env_local(schema, registry))
    write(".gitignore", _render_gitignore())

    # §S3.2 docs model; CR-MDB-048 §S2: no queue README — the Crucible
    # board holds the queue, docs/changes/ the specs.
    write("docs/changes/.gitkeep", "")
    write("docs/research/.gitkeep", "")

    # §S3.3 AGENTS.md (Pi reads it natively — no anchor file).
    write(
        "AGENTS.md",
        _render_agents_md(name, token, acronym, mode, owner, stacks, harnesses,
                          registry.get("SANDESH_PROJECT"), tool_states,
                          knowledge_category, tools),
    )

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
                lean_ctx=tools.get("lean-ctx") == TOOL_PRESENT, rendered=agent_texts,
            )
        finally:
            emitted.extend(agent_report.get("written", []))

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
    if agent_sources is not None:
        try:
            agent_texts = _prerender_agents(stacks, harnesses, agent_sources, tools)
        except ScaffoldError as exc:
            print(f"modelb-axi: error: {exc}", file=sys.stderr)
            print(envelope("init", False, warnings=[str(exc)], dry_run=dry_run))
            return 2

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
    for rel in ownership["skipped"]:
        warning = (f"skipping hand-modified managed file {rel} (marker hash "
                   "mismatch; re-run with --force-managed to overwrite)")
        print(f"modelb-axi: warning: {warning}", file=sys.stderr)
        plan_warnings.append(warning)
    for rel in ownership["unmanaged"]:
        warning = (f"unmanaged: {rel} — no Model B marker; left untouched (no "
                   "flag overwrites it)")
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
