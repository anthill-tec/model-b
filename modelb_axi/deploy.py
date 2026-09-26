"""Deploy engine — installer-flow stage 3 (CR-MDB-014 §S6).

Manifest-driven copy of the package's skill assets into the target root:

- Skill bundles (any ``skills-src/`` subdirectory carrying a ``SKILL.md``
  marker — e.g. ``crucible``; ``memory-templates`` is scaffold material,
  not a skill bundle) deploy ONCE into the harness-neutral shared store
  ``<target-root>/.agents/skills/<name>/`` (PRD §D2). Stack-scoped bundles
  (``crucible-report-*``, CR-MDB-036 §S7; ``code-health`` -> rust,
  CR-MDB-023 §S4) deploy only for a selected stack or no stack filter.
- No per-harness link is written: Pi reads ``~/.agents/skills`` natively
  (DN-multi-harness-deploy-model §D15.1; CR-MDB-031 §S1 retired the
  per-harness link writer).
- Every deployed FILE yields a manifest entry ``{path, sha256}`` with
  ``path`` target-root-relative.

Idempotent upgrade (AC5, DN-scaffold-packaging §5): a target file whose hash matches the
source is untouched; a file whose hash differs from BOTH the source and
its recorded manifest hash is hand-modified — skipped (surfaced to the
caller) unless ``force_managed`` overwrites it and refreshes its entry.

Stdlib only. Never touches the real ``~/.agents`` in tests — callers pass
sandboxed target roots (repo-local rule, DN-scaffold-packaging §7).

Prune (CR-MDB-040 §S1): :func:`prune_assets` removes what a redeploy no
longer deploys — an unchanged file the prior manifest records and the new
one does not — and keeps a hand-modified one; it never touches a path
outside the three stores (:func:`store_root_of`).
"""

import hashlib
import os
import shutil
import stat
from pathlib import Path

from modelb_axi._fsutil import atomic_write

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


def deploy_assets(
    asset_root: Path,
    target_root: Path,
    prior_hashes: dict[str, str] | None = None,
    force_managed: bool = False,
    unmanaged: list[str] | None = None,
    stacks: list[str] | None = None,
) -> tuple[list[dict], list[str]]:
    """Run the §S6 deploy: store copies only (no per-harness links).

    The store is harness-neutral, so the selected harness set selects no
    writes and is not a parameter (CR-MDB-031 §S1; C5 F8).

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
    ``current`` entry is in none. ``files`` are ``config.manifest_entries``
    (CR-MDB-040 §S1). Reads only; writes nothing."""
    found: dict[str, list[str]] = {"stale": [], "hand_modified": [], "retired": []}
    for entry in files:
        rel, recorded = entry["path"], entry["sha256"]
        source = packaged_source(asset_root, rel)
        if source is None or not source.is_file():
            found["retired"].append(rel)
        elif _file_hash(target_root / rel) != recorded:
            found["hand_modified"].append(rel)
        elif sha256_file(source) != recorded:
            found["stale"].append(rel)
    return {state: sorted(paths) for state, paths in found.items()}


#: CR-MDB-040 §S1: the three store roots a deploy writes into — the only
#: places a prune may remove from, and never removed themselves.
_STORE_ROOTS: tuple[Path, ...] = (
    STORE_RELDIR, HOOKS_SCRIPTS_STORE_RELDIR, TOOL_SCRIPTS_STORE_RELDIR,
)


def store_root_of(rel: str) -> Path | None:
    """The store root a manifest path lies strictly inside, after
    normalising ``..`` (CR-MDB-040 §S1); ``None`` for an absolute path or
    one outside the three stores \u2014 a corrupt entry, since the deploy
    writes only there."""
    if os.path.isabs(rel):
        return None
    normalised = Path(os.path.normpath(rel))
    for store in _STORE_ROOTS:
        if normalised.is_relative_to(store) and normalised != store:
            return store
    return None


def prune_assets(
    prior_root: Path, prior_files: list[dict], new_paths: set[str],
) -> tuple[list[str], list[str]]:
    """Prune every path the prior manifest records and the new one does
    not (CR-MDB-040 §S1), both compared after ``os.path.normpath``.
    Returns ``(removed, kept)``, normalised and target-root-relative:

    * removed \u2014 the file under ``prior_root`` exists with its recorded
      hash; it is deleted, then each directory left empty, walking up and
      stopping at (never removing) its store root;
    * kept \u2014 the file exists with a different hash (hand-modified); never
      deleted, whatever ``--force-managed`` says;
    * an absent file is skipped silently, and an entry outside the three
      stores (:func:`store_root_of`) is never touched and in neither list.

    ``prior_files`` are ``config.manifest_entries`` — well-formed and
    de-duplicated by normalised path (the first wins); they are not
    re-filtered here. An ``OSError`` raises :class:`DeployError` carrying
    it as the cause."""
    removed: list[str] = []
    kept: list[str] = []
    deployed = {os.path.normpath(p) for p in new_paths}
    try:
        for entry in prior_files:
            # Compared, removed and reported by its normalised path: an entry
            # spelled differently from a deployed path IS that path.
            rel = os.path.normpath(entry["path"])
            store = store_root_of(rel)
            if store is None or rel in deployed:
                continue
            path = prior_root / rel
            if not path.is_file():
                continue  # already gone: nothing to do, not reported
            if sha256_file(path) != entry["sha256"]:
                kept.append(rel)
                continue
            path.unlink()
            removed.append(rel)
            _remove_empty_parents(path.parent, prior_root / store)
    except OSError as exc:
        raise DeployError(f"prune step failed: {exc}") from exc
    return removed, kept


def _remove_empty_parents(directory: Path, store_root: Path) -> None:
    """Remove ``directory`` and each emptied ancestor, stopping at
    ``store_root``, which is never removed, and at a directory that is a
    symbolic link, which is left in place (CR-MDB-040 §S1)."""
    while directory != store_root and directory.is_relative_to(store_root):
        if directory.is_symlink() or not directory.is_dir() or any(directory.iterdir()):
            return
        directory.rmdir()
        directory = directory.parent
