"""Deploy engine — installer-flow stage 3 (CR-MDB-014 §S6).

Manifest-driven copy of the package's skill assets into the target root:

- Skill bundles (any ``skills-src/`` subdirectory carrying a ``SKILL.md``
  marker — e.g. ``crucible``; ``memory-templates`` is scaffold material,
  not a skill bundle) deploy ONCE into the harness-neutral shared store
  ``<target-root>/.agents/skills/<name>/`` (PRD §D2). Stack-scoped bundles
  (``crucible-report-*``, CR-MDB-036 §S7; ``code-health`` -> rust,
  CR-MDB-023 §S4) deploy only for a selected stack or no stack filter.
- Each selected harness then gets a SYMLINK into its own skills dir per
  the mapping table below (Claude Code mapping complete in v1; the other
  roster harnesses have no skills-dir mapping yet — DN-scaffold-packaging §5).
- Every deployed FILE yields a manifest entry ``{path, sha256}`` with
  ``path`` target-root-relative.

Idempotent upgrade (AC5, DN-scaffold-packaging §5): a target file whose hash matches the
source is untouched; a file whose hash differs from BOTH the source and
its recorded manifest hash is hand-modified — skipped (surfaced to the
caller) unless ``force_managed`` overwrites it and refreshes its entry.

Stdlib only. Never touches the real ``~/.claude``/``~/.agents`` in
tests — callers pass sandboxed target roots (repo-local rule, DN-scaffold-packaging §7).
"""

import hashlib
import os
import shutil
import stat
from pathlib import Path

from modelb_axi._fsutil import atomic_write

# Per-harness skills-dir mapping (target-root-relative). Only harnesses
# listed here receive symlinks; the rest of the roster is deploy-inert
# in v1 (anchor-file mappings arrive with later cycles).
HARNESS_SKILL_DIRS: dict[str, str] = {
    "claude-code": ".claude/skills",
}

SKILL_BUNDLE_MARKER = "SKILL.md"
#: Stack-scoped skill bundles (CR-MDB-036 §S7) share this name prefix.
REPORT_BUNDLE_PREFIX = "crucible-report-"
#: Other stack-scoped skill bundles (CR-MDB-023 §S4): bundle name -> the
#: stack whose selection deploys it, under the same rule as the
#: ``crucible-report-*`` bundles (deployed when that stack is selected or
#: no stack filter is given).
STACK_SCOPED_BUNDLES: dict[str, str] = {"code-health": "rust"}
STORE_RELDIR = Path(".agents") / "skills"

#: CR-MDB-015 §S6: the shared protocol scripts deploy ONCE user-scope into
#: the same harness-neutral ``.agents/`` store the skill bundles use
#: (``hooks`` mirrors the ``skills-src`` -> ``skills`` rename).
HOOKS_SCRIPTS_STORE_RELDIR = Path(".agents") / "hooks" / "scripts"

#: CR-MDB-022 §S4: the adopted workflow tooling (``scripts/``) deploys the
#: same way — ONCE user-scope into the harness-neutral ``.agents/`` store,
#: with NO per-harness symlink (a script is invoked by the path a skill
#: names, so a harness-specific tool path would defeat the detachment).
TOOL_SCRIPTS_STORE_RELDIR = Path(".agents") / "scripts"


class DeployError(Exception):
    """A deploy step failed; install.toml must NOT be written (§S6)."""


def default_asset_root() -> Path:
    """Asset root resolution (§S2):

    - Installed package: the wheel force-includes the asset roots under
      ``modelb_axi/_assets/`` — when that directory exists it IS the
      asset root (``skills-src/`` etc. live inside it).
    - Repo checkout (dev / PYTHONPATH runs): no ``_assets/`` dir exists
      in the tree, so fall back to the directory containing the
      ``modelb_axi`` package — the repo root (``skills-src/`` sibling,
      as the dev-mode tests pin)."""
    packaged_assets = Path(__file__).resolve().parent / "_assets"
    if packaged_assets.is_dir():
        return packaged_assets
    return Path(__file__).resolve().parent.parent


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def report_bundle(stack: str) -> str:
    """The ``crucible-report-*`` bundle a stack deploys (CR-MDB-036 §S7):
    ``crucible-report-<stack>``, except quarkus and java share ``-java``."""
    return f"{REPORT_BUNDLE_PREFIX}{'java' if stack in ('quarkus', 'java') else stack}"


def _skill_bundles(asset_root: Path, stacks: list[str] | None = None) -> list[Path]:
    """The ``skills-src/`` bundles to deploy. ``stacks`` scopes the
    ``crucible-report-*`` bundles (CR-MDB-036 §S7) and the
    :data:`STACK_SCOPED_BUNDLES` (CR-MDB-023 §S4) to the selection;
    ``None`` deploys every bundle."""
    skills_src = asset_root / "skills-src"
    if not skills_src.is_dir():
        raise DeployError(f"asset root has no skills-src/ directory: {asset_root}")
    wanted = None if stacks is None else (
        {report_bundle(s) for s in stacks}
        | {name for name, stack in STACK_SCOPED_BUNDLES.items() if stack in stacks}
    )
    return sorted(
        child for child in skills_src.iterdir()
        if child.is_dir() and (child / SKILL_BUNDLE_MARKER).is_file()
        and (wanted is None or child.name in wanted
             or not (child.name.startswith(REPORT_BUNDLE_PREFIX)
                     or child.name in STACK_SCOPED_BUNDLES))
    )


def _hook_scripts(asset_root: Path) -> list[Path]:
    """The protocol scripts under ``<asset-root>/hooks-src/scripts/``.

    Asset-root resolution is the caller's (:func:`default_asset_root` —
    packaged ``modelb_axi/_assets`` first, repo checkout fallback), the
    SAME chain the skill bundles use (CR-MDB-015 §S6)."""
    scripts_dir = asset_root / "hooks-src" / "scripts"
    if not scripts_dir.is_dir():
        raise DeployError(
            f"asset root has no hooks-src/scripts/ directory: {asset_root}"
        )
    return sorted(child for child in scripts_dir.iterdir() if child.is_file())


def _tool_scripts(asset_root: Path) -> list[Path]:
    """The adopted workflow tooling under ``<asset-root>/scripts/``.

    Same shape as :func:`_hook_scripts` — one asset-root argument, a flat
    sorted file list — over the asset root ``pyproject.toml`` already
    force-includes (CR-MDB-022 §S4)."""
    scripts_dir = asset_root / "scripts"
    if not scripts_dir.is_dir():
        raise DeployError(
            f"asset root has no scripts/ directory: {asset_root}"
        )
    return sorted(child for child in scripts_dir.iterdir() if child.is_file())


def _deploy_file(
    src: Path,
    dest: Path,
    rel: str,
    prior_hashes: dict[str, str],
    force_managed: bool,
    skipped: list[str],
    unmanaged: list[str],
) -> dict | None:
    """Deploy one file into the store; return its manifest entry, or
    ``None`` when the destination is UNMANAGED (CR-MDB-033 §S3).

    Three destination states are distinguished, and only the last is a
    write:

    * identical to the source — untouched, recorded unchanged;
    * present but ABSENT from the prior manifest — unmanaged: not Model
      B's to overwrite (DN-multi-harness-deploy-model §D3), so it is left byte-identical, reported
      through ``unmanaged``, and recorded in NO manifest entry (recording
      it would adopt it, and a later run could then clobber it);
    * present, recorded in the prior manifest, hash-mismatched — a
      hand-modified MANAGED file: skipped unless ``force_managed``.
    """
    src_hash = sha256_file(src)
    if dest.is_file():
        dest_hash = sha256_file(dest)
        if dest_hash == src_hash:
            return {"path": rel, "sha256": src_hash}  # unchanged — untouched
        recorded = prior_hashes.get(rel)
        if recorded is None:
            # Unmanaged file at a path Model B deploys to: no flag
            # overwrites it (CR-MDB-033 §S3 / DN-multi-harness-deploy-model §D3).
            unmanaged.append(rel)
            return None
        if dest_hash != recorded and not force_managed:
            # Hand-modified managed file: never silently clobbered (AC5).
            skipped.append(rel)
            return {"path": rel, "sha256": recorded}
    dest.parent.mkdir(parents=True, exist_ok=True)
    # CR-MDB-033 §S2: atomic, carrying the source mode (exec bit included).
    atomic_write(dest, src.read_bytes(), mode=stat.S_IMODE(src.stat().st_mode))
    return {"path": rel, "sha256": src_hash}


def _link_harness_skills(
    target_root: Path, harnesses: list[str], bundle_names: list[str]
) -> None:
    """Create per-harness symlinks into the shared store (one link per
    skill bundle, pointing at the store dir — never a second copy)."""
    for harness_id in harnesses:
        skills_reldir = HARNESS_SKILL_DIRS.get(harness_id)
        if skills_reldir is None:
            continue  # no skills-dir mapping for this harness in v1
        for name in bundle_names:
            store_dir = target_root / STORE_RELDIR / name
            link = target_root / skills_reldir / name
            if link.is_symlink():
                if link.resolve() == store_dir.resolve():
                    continue
                link.unlink()
            elif link.exists():
                raise DeployError(
                    f"harness skills path exists and is not a symlink: {link}"
                )
            link.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(store_dir, link)


def deploy_assets(
    asset_root: Path,
    target_root: Path,
    harnesses: list[str],
    prior_hashes: dict[str, str] | None = None,
    force_managed: bool = False,
    unmanaged: list[str] | None = None,
    stacks: list[str] | None = None,
) -> tuple[list[dict], list[str]]:
    """Run the §S6 deploy: store copies + harness symlinks.

    Returns ``(manifest_entries, skipped_paths)`` — ``skipped_paths`` are
    hand-modified managed files left untouched (AC5). Raises
    :class:`DeployError` on any filesystem failure so the caller exits
    non-zero WITHOUT writing install.toml (atomicity).

    ``unmanaged`` is a caller-supplied out-list filled with the relative
    paths left untouched because they are ABSENT from the prior manifest
    (CR-MDB-033 §S3). It is an out-parameter rather than a third return
    value because ``(manifest, skipped)`` is a pinned return shape
    (CR-MDB-022 §S4): the two skip vocabularies stay distinct without
    breaking existing callers.

    ``stacks`` (CR-MDB-036 §S7) scopes the ``crucible-report-*`` bundles
    and (CR-MDB-023 §S4) the ``code-health`` bundle to the selection
    (``None`` = every stack); every other bundle, the
    hook scripts and the tool scripts always deploy."""
    prior = prior_hashes or {}
    manifest: list[dict] = []
    skipped: list[str] = []
    unmanaged_paths = unmanaged if unmanaged is not None else []
    try:
        bundles = _skill_bundles(asset_root, stacks)
        skills_src = asset_root / "skills-src"
        for bundle in bundles:
            for src in sorted(bundle.rglob("*")):
                if not src.is_file():
                    continue
                rel_path = STORE_RELDIR / src.relative_to(skills_src)
                rel = str(rel_path)
                dest = target_root / rel_path
                entry = _deploy_file(
                    src, dest, rel, prior, force_managed, skipped,
                    unmanaged_paths,
                )
                if entry is not None:
                    manifest.append(entry)
        # CR-MDB-015 §S6: the seven protocol scripts, once, user-scope.
        for src in _hook_scripts(asset_root):
            rel_path = HOOKS_SCRIPTS_STORE_RELDIR / src.name
            rel = str(rel_path)
            dest = target_root / rel_path
            entry = _deploy_file(
                src, dest, rel, prior, force_managed, skipped, unmanaged_paths,
            )
            if entry is not None:
                manifest.append(entry)
            if entry is not None and rel not in skipped:
                # Executable bit preserved (protocol scripts are run
                # directly by harness wiring); hand-modified skips and
                # unmanaged files are left byte-AND-mode untouched.
                shutil.copymode(src, dest)
        # CR-MDB-022 §S4: the eight adopted workflow tools, once,
        # user-scope — NO per-harness symlink (see the store constant).
        for src in _tool_scripts(asset_root):
            rel_path = TOOL_SCRIPTS_STORE_RELDIR / src.name
            rel = str(rel_path)
            dest = target_root / rel_path
            entry = _deploy_file(
                src, dest, rel, prior, force_managed, skipped, unmanaged_paths,
            )
            if entry is not None:
                manifest.append(entry)
            if entry is not None and rel not in skipped:
                shutil.copymode(src, dest)
        _link_harness_skills(target_root, harnesses, [b.name for b in bundles])
    except OSError as exc:
        raise DeployError(f"deploy step failed: {exc}") from exc
    return manifest, skipped


#: CR-MDB-037 \u00a7S2: where each deployed store's packaged source lives,
#: relative to the asset root (the inverse of :func:`deploy_assets`).
_STORE_SOURCES: tuple[tuple[Path, Path], ...] = (
    (STORE_RELDIR, Path("skills-src")),
    (HOOKS_SCRIPTS_STORE_RELDIR, Path("hooks-src") / "scripts"),
    (TOOL_SCRIPTS_STORE_RELDIR, Path("scripts")),
)


def packaged_source(asset_root: Path, rel: str) -> Path | None:
    """The packaged source a manifest path was deployed from, or ``None``
    when the path lies in no store Model B deploys to."""
    rel_path = Path(rel)
    for store, source in _STORE_SOURCES:
        if rel_path.is_relative_to(store) and rel_path != store:
            return asset_root / source / rel_path.relative_to(store)
    return None


def _file_hash(path: Path) -> str | None:
    return sha256_file(path) if path.is_file() else None


def deployed_freshness(
    asset_root: Path, target_root: Path, files: list[dict],
) -> dict[str, list[str]]:
    """Judge each manifest entry against its deployed copy under
    ``target_root`` and its packaged source under ``asset_root``
    (CR-MDB-037 \u00a7S2). Returns the sorted target-root-relative paths that
    are ``stale`` (deployed = manifest \u2260 source), ``hand_modified``
    (deployed \u2260 manifest) and ``retired`` (no packaged source); a
    ``current`` entry is in none. Reads only; writes nothing."""
    found: dict[str, list[str]] = {"stale": [], "hand_modified": [], "retired": []}
    for entry in files:
        if not isinstance(entry, dict) or "path" not in entry or "sha256" not in entry:
            continue
        rel, recorded = str(entry["path"]), str(entry["sha256"])
        source = packaged_source(asset_root, rel)
        if source is None or not source.is_file():
            found["retired"].append(rel)
        elif _file_hash(target_root / rel) != recorded:
            found["hand_modified"].append(rel)
        elif sha256_file(source) != recorded:
            found["stale"].append(rel)
    return {state: sorted(paths) for state, paths in found.items()}
