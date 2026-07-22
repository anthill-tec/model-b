"""Deploy engine — installer-flow stage 3 (CR-MDB-014 §S6).

Manifest-driven copy of the package's skill assets into the target root:

- Skill bundles (any ``skills-src/`` subdirectory carrying a ``SKILL.md``
  marker — e.g. ``crucible``; ``memory-templates`` is scaffold material,
  not a skill bundle) deploy ONCE into the harness-neutral Vercel store
  ``<target-root>/.agents/skills/<name>/`` (PRD §D2).
- Each selected harness then gets a SYMLINK into its own skills dir per
  the mapping table below (Claude Code mapping complete in v1; the other
  roster harnesses have no skills-dir mapping yet — DN §5).
- Every deployed FILE yields a manifest entry ``{path, sha256}`` with
  ``path`` target-root-relative.

Idempotent upgrade (AC5, DN §5): a target file whose hash matches the
source is untouched; a file whose hash differs from BOTH the source and
its recorded manifest hash is hand-modified — skipped (surfaced to the
caller) unless ``force_managed`` overwrites it and refreshes its entry.

Stdlib only. Never touches the real ``~/.claude``/``~/.agents`` in
tests — callers pass sandboxed target roots (repo-local rule, DN §7).
"""

import hashlib
import os
import shutil
from pathlib import Path

# Per-harness skills-dir mapping (target-root-relative). Only harnesses
# listed here receive symlinks; the rest of the roster is deploy-inert
# in v1 (anchor-file mappings arrive with later cycles).
HARNESS_SKILL_DIRS: dict[str, str] = {
    "claude-code": ".claude/skills",
}

SKILL_BUNDLE_MARKER = "SKILL.md"
STORE_RELDIR = Path(".agents") / "skills"

#: CR-MDB-015 §S6: the shared protocol scripts deploy ONCE user-scope into
#: the same harness-neutral ``.agents/`` store the skill bundles use
#: (``hooks`` mirrors the ``skills-src`` -> ``skills`` rename).
HOOKS_SCRIPTS_STORE_RELDIR = Path(".agents") / "hooks" / "scripts"


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


def _skill_bundles(asset_root: Path) -> list[Path]:
    skills_src = asset_root / "skills-src"
    if not skills_src.is_dir():
        raise DeployError(f"asset root has no skills-src/ directory: {asset_root}")
    return sorted(
        child for child in skills_src.iterdir()
        if child.is_dir() and (child / SKILL_BUNDLE_MARKER).is_file()
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


def _deploy_file(
    src: Path,
    dest: Path,
    rel: str,
    prior_hashes: dict[str, str],
    force_managed: bool,
    skipped: list[str],
) -> dict:
    """Deploy one file into the store; return its manifest entry."""
    src_hash = sha256_file(src)
    if dest.is_file():
        dest_hash = sha256_file(dest)
        if dest_hash == src_hash:
            return {"path": rel, "sha256": src_hash}  # unchanged — untouched
        recorded = prior_hashes.get(rel)
        if recorded is not None and dest_hash != recorded and not force_managed:
            # Hand-modified managed file: never silently clobbered (AC5).
            skipped.append(rel)
            return {"path": rel, "sha256": recorded}
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    return {"path": rel, "sha256": src_hash}


def _link_harness_skills(
    target_root: Path, harnesses: list[str], bundle_names: list[str]
) -> None:
    """Create per-harness symlinks into the Vercel store (one link per
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
) -> tuple[list[dict], list[str]]:
    """Run the §S6 deploy: store copies + harness symlinks.

    Returns ``(manifest_entries, skipped_paths)`` — ``skipped_paths`` are
    hand-modified managed files left untouched (AC5). Raises
    :class:`DeployError` on any filesystem failure so the caller exits
    non-zero WITHOUT writing install.toml (atomicity)."""
    prior = prior_hashes or {}
    manifest: list[dict] = []
    skipped: list[str] = []
    try:
        bundles = _skill_bundles(asset_root)
        skills_src = asset_root / "skills-src"
        for bundle in bundles:
            for src in sorted(bundle.rglob("*")):
                if not src.is_file():
                    continue
                rel_path = STORE_RELDIR / src.relative_to(skills_src)
                rel = str(rel_path)
                dest = target_root / rel_path
                manifest.append(
                    _deploy_file(src, dest, rel, prior, force_managed, skipped)
                )
        # CR-MDB-015 §S6: the seven protocol scripts, once, user-scope.
        for src in _hook_scripts(asset_root):
            rel_path = HOOKS_SCRIPTS_STORE_RELDIR / src.name
            rel = str(rel_path)
            dest = target_root / rel_path
            manifest.append(
                _deploy_file(src, dest, rel, prior, force_managed, skipped)
            )
            if rel not in skipped:
                # Executable bit preserved (protocol scripts are run
                # directly by harness wiring); hand-modified skips are
                # left byte-AND-mode untouched.
                shutil.copymode(src, dest)
        _link_harness_skills(target_root, harnesses, [b.name for b in bundles])
    except OSError as exc:
        raise DeployError(f"deploy step failed: {exc}") from exc
    return manifest, skipped
