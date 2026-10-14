"""Model B renders its own release workflow and scripts (CR-MDB-068 §S7).

Contract: ``docs/changes/CR-MDB-068-release-and-ci-workflow-templates.md`` §S7 and its acceptance
criterion: Model B's three files equal ``render(["python"], ["pypi", "npm:pi-package"],
workflows-src)``; no test reads Model B's ``.env``.

Class map:

- ``ModelBReleaseFilesTest`` — ``.github/workflows/release.yml``,
  ``.github/scripts/stamp_version.py`` and ``.github/scripts/changelog_section.py`` are, byte for
  byte, ``workflows.render(MODEL_B_STACKS, MODEL_B_TARGETS, REPO_ROOT / "workflows-src")``'s texts,
  and nothing else is rendered under ``.github/``. Model B's stacks and targets are written here,
  not read from its gitignored ``.env``.
- ``EnvReadDetectorProofTest`` / ``NoTestReadsModelBEnvTest`` — :func:`env_read_lines` proved on
  synthetic text both ways, then applied to every ``tests/**/*.py``: no test reads the
  repository's own ``.env`` or ``.env.local``.

Stdlib only.
"""

import re
import unittest
from pathlib import Path

from tests.test_workflow_render import RENDERED_FILES, SOURCE, render_files

REPO_ROOT = Path(__file__).resolve().parent.parent
#: §S7 — the render Model B commits as its own: its stack and its release targets (the value its
#: local, gitignored ``.env`` records as ``RELEASE_TARGETS``; never read by a test).
MODEL_B_STACKS = ["python"]
MODEL_B_TARGETS = ["pypi", "npm:pi-package"]

#: A path expression naming the repository's own ``.env`` (or ``.env.local``): a ``*ROOT`` constant
#: or a ``.parent`` divided by the file name, or a ``*ROOT`` constant joined with it by
#: ``os.path.join``.
_ENV_READ = re.compile(
    r"""(?:\b[A-Z_]*ROOT\b|\.parent)\s*/\s*["']\.env(?:\.local)?["']"""
    r"""|\b[A-Z_]*ROOT\b\s*,\s*["']\.env(?:\.local)?["']""")


def env_read_lines(text: str) -> list[str]:
    """The stripped lines of ``text`` that name the repository's own ``.env``."""
    return [line.strip() for line in text.splitlines() if _ENV_READ.search(line)]


class ModelBReleaseFilesTest(unittest.TestCase):
    """§S7 — Model B's three files are the render's, byte for byte."""

    def test_each_file_is_the_render_byte_for_byte(self):
        rendered = render_files(MODEL_B_STACKS, MODEL_B_TARGETS, SOURCE)
        self.assertEqual(sorted(rendered), sorted(RENDERED_FILES), "precondition: three files")
        for rel, text in rendered.items():
            with self.subTest(file=rel):
                path = REPO_ROOT / rel
                self.assertTrue(path.is_file(), f"§S7: Model B commits {rel}")
                self.assertEqual(path.read_bytes(), text.encode("utf-8"),
                                 f"§S7: {rel} is render({MODEL_B_STACKS!r}, {MODEL_B_TARGETS!r})'s "
                                 "text, byte for byte")

    def test_no_other_workflow_or_script_is_committed_under_github(self):
        # Regression pin: holds today; fails the moment a second, hand-written workflow or script
        # appears beside the rendered ones.
        found = sorted(p.relative_to(REPO_ROOT).as_posix()
                       for p in (REPO_ROOT / ".github").rglob("*")
                       if p.is_file() and "__pycache__" not in p.parts)
        self.assertEqual(found, sorted(RENDERED_FILES))


#: Synthetic lines: each names the repository's own .env (built by concatenation, so this module's
#: own text never matches the detector).
_READS = (
    "stacks = parse_env_file(REPO_ROOT / " + '".env")',
    "text = (ROOT / " + "'.env.local').read_text()",
    "path = Path(__file__).resolve().parent.parent / " + '".env"',
    "path = os.path.join(REPO_ROOT, " + '".env")',
)
#: Synthetic lines that name a sandbox project's .env, or another file: none is a read of Model B's.
_CLEAN = (
    "text = (self.target / " + '".env").read_text()',
    "path = target / " + '".env"',
    "env = REPO_ROOT / " + '".envrc"',
    "registry = REPO_ROOT / " + '"modelb_axi" / "project_schema.toml"',
)


class EnvReadDetectorProofTest(unittest.TestCase):
    """:func:`env_read_lines` bites on every spelling of the repository's ``.env`` and on no
    sandbox project's."""

    def test_every_spelling_of_the_repository_env_is_found(self):
        for line in _READS:
            with self.subTest(line=line):
                self.assertEqual(env_read_lines(line), [line])

    def test_a_sandbox_projects_env_or_another_file_is_not(self):
        for line in _CLEAN:
            with self.subTest(line=line):
                self.assertEqual(env_read_lines(line), [])


class NoTestReadsModelBEnvTest(unittest.TestCase):
    """§S7 — no test reads Model B's gitignored ``.env``: a fresh clone has none."""

    def test_no_test_module_names_the_repository_env(self):
        found = {}
        for path in sorted((REPO_ROOT / "tests").rglob("*.py")):
            lines = env_read_lines(path.read_text(encoding="utf-8"))
            if lines:
                found[path.relative_to(REPO_ROOT).as_posix()] = lines
        self.assertEqual(found, {}, "§S7: no test reads Model B's .env")


if __name__ == "__main__":
    unittest.main()
