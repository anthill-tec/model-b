"""The published artifacts: package metadata, one version, archive contents,
and the sdist -> wheel -> isolated install path PyPI users take.

Scope: §S1 (publishable metadata, one version) and §S2 (the built artifacts
install and work) of the PyPI-publishing change. Every assertion reads the
REAL artifacts: the test builds an sdist from the repository with
``uv build --sdist`` into a temp dir, then a wheel FROM THAT SDIST (the path
PyPI users take), and reads ``METADATA`` and archive listings from them.
Nothing is built into the repository and nothing is uploaded anywhere.

Orchestrator rulings (2026-09-24, cycle 106) these tests pin:

- R1 (classifiers, families only): exactly one ``License ::`` classifier and
  it is ``License :: OSI Approved :: MIT License``;
  ``Environment :: Console`` present. The full list is not pinned.
  MIGRATED at CR-MDB-064 C1 RED ("§S1", the published floor is 3.14; was:
  ``… :: 3.11`` present and none below 3.11): ``Programming Language ::
  Python :: 3``, ``… :: 3 :: Only`` and ``… :: 3.14`` present, and no
  ``Programming Language :: Python :: <version>`` below 3.14. The
  ``Requires-Python`` pin moves from ``>=3.11`` to ``>=3.14`` with it, and
  ``PyprojectPythonFloorTest`` reads the same two facts from
  ``pyproject.toml`` without a build.
- R2 (one version): the hatch mechanism is not pinned. ``[project]`` has no
  ``version`` key and lists ``version`` in ``dynamic``; the wheel's
  ``Version`` equals ``__version__`` in ``modelb_axi/__init__.py``; and a
  behavioural probe rewrites ``__version__`` to ``9.9.9`` in a temp copy of
  the build inputs and expects a ``9.9.9`` wheel.
- R3 (the guide names the PyPI project page) lives in
  ``tests/test_install_guide.py`` — prose in ``## Marked regions``.
- R4 (§S2): an acceptance pin that passes before the metadata change (the
  sdist already carries every asset root); proven the other way by a
  mutation done by hand at RED time (not a committed test) — an sdist
  built without ``hooks-src`` failed it. §S1 assertions are deliberately
  NOT folded into it.
- R5 (the PyPI links): MIGRATED at CR-MDB-058 C2 RED (§S3; was: no
  ``Project-URL`` and no ``Home-page`` while the repository is private). The
  wheel built from the sdist carries exactly two ``Project-URL`` lines, the
  PEP 753 well-known labels ``Changelog`` (the ``CHANGELOG.md`` on ``master``,
  which holds the released copy) and ``Release Notes`` (the GitHub releases
  page), and still no ``Home-page``. ``PyprojectUrlsTest`` reads the same
  table from ``pyproject.toml`` without a build.

CR-MDB-069 §S1: ``IsolatedWheelBuildGateTest`` reads the source of
``tests/test_tooling_detachment.py`` and ``tests/test_project_registry_schema.py``
and fails if either names a non-isolated build (``NON_ISOLATED_BUILD_MARKERS``),
if either does not import ``build_wheel`` from here by name, or if either
built-wheel check does not call ``build_wheel`` or calls ``skipTest``;
``IsolatedWheelBuildCheckerProofTest`` proves its checker on sample source
both ways.

Sandbox: every ``modelb-axi`` run passes ``--modelb-home`` and
``--target-root`` into a temp dir, with ``MODELB_HOME``, ``XDG_DATA_HOME``,
``HOME`` and ``PI_CODING_AGENT_DIR`` pointed at temp paths; the install uses
an isolated ``UV_TOOL_DIR``/``UV_TOOL_BIN_DIR``.

Stdlib only.
"""

import ast
import email.parser
import email.policy
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import tomllib
import unittest
import zipfile
from pathlib import Path

from tests._helpers import decode_axi, write_interpreter_fixture
from tests.pi_capability_sandbox import (
    AGENT_DIR_ENV,
    make_home,
    make_provisioned_agent_dir,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
LICENSE = REPO_ROOT / "LICENSE"
GUIDE = REPO_ROOT / "docs" / "install-guide.md"
MODULE_INIT = REPO_ROOT / "modelb_axi" / "__init__.py"

#: §S1 — the three directories no artifact may carry.
EXCLUDED_ROOTS = ("tests", "archive", "audits")

#: §S1 — the words an internal description would carry.
INTERNAL_MARKERS = ("DN-", "CR-", "§")

MIT_CLASSIFIER = "License :: OSI Approved :: MIT License"
#: CR-MDB-064 §S1 — the published floor, and the version classifiers it declares.
PYTHON_FLOOR = (3, 14)
REQUIRES_PYTHON = ">=3.14"
PYTHON_3_CLASSIFIER = "Programming Language :: Python :: 3"
PYTHON_3_ONLY_CLASSIFIER = "Programming Language :: Python :: 3 :: Only"
PYTHON_314_CLASSIFIER = "Programming Language :: Python :: 3.14"
CONSOLE_CLASSIFIER = "Environment :: Console"
#: CR-MDB-058 §S3 — ``[project.urls]``, and the two ``Project-URL`` lines the wheel carries.
PROJECT_URLS = {
    "Changelog": "https://github.com/anthill-tec/model-b/blob/master/CHANGELOG.md",
    "Release Notes": "https://github.com/anthill-tec/model-b/releases",
}
PROJECT_URL_LINES = [f"{label}, {url}" for label, url in PROJECT_URLS.items()]
_PYTHON_VERSION_CLASSIFIER = re.compile(
    r"Programming Language :: Python :: (\d+)(?:\.(\d+))?"
)

#: The MIT license (SPDX ``MIT``), with §S1's copyright line.
MIT_LICENSE_BODY = (
    "Copyright (c) 2026 Antony John\n\n"
    "Permission is hereby granted, free of charge, to any person obtaining a copy "
    "of this software and associated documentation files (the \"Software\"), to deal "
    "in the Software without restriction, including without limitation the rights "
    "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell "
    "copies of the Software, and to permit persons to whom the Software is "
    "furnished to do so, subject to the following conditions:\n\n"
    "The above copyright notice and this permission notice shall be included in all "
    "copies or substantial portions of the Software.\n\n"
    "THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR "
    "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, "
    "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE "
    "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER "
    "LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, "
    "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE "
    "SOFTWARE.\n"
)

#: Directory names never copied into the version-probe build tree.
_COPY_IGNORE = shutil.ignore_patterns(
    ".git", ".venv", "__pycache__", "*.pyc", ".pytest_cache", ".ruff_cache",
    "test-reports", ".benchmarks", ".lean-ctx", ".lavish", ".coverage",
    "dist", "build", "node_modules",
)

_INIT_FLAGS = (
    "--name", "X", "--token", "xproj", "--acronym", "XP",
    "--mode", "solo", "--repo-shape", "standalone",
    "--stacks", "python", "--owner", "tester",
)
TDD_ROLES = ("red", "green", "verify", "fix")
POLICY_REL = Path(".pi") / "extensions" / "pi-permission-system" / "config.json"

_FAKE_UV = (
    "#!/bin/sh\n"
    'if [ "$1" = "tool" ] && [ "$2" = "install" ]; then exit 0; fi\n'
    'echo "uv 0.0.0-fake"\n'
    "exit 0\n"
)
# MIGRATED at CR-MDB-047 C1 RED (§S1 version floor): a fake standing for a
# present Sandesh answers `--version` like the real CLI, at the 0.4.0 floor.
_FAKE_SANDESH = "#!/bin/sh\necho 'sandesh 0.4.0'\nexit 0\n"


# ---------------------------------------------------------------------------
# Pure checkers (proven both ways in PackageMetadataCheckerProofTest)
# ---------------------------------------------------------------------------

def normalise_ws(text: str) -> str:
    return " ".join(text.split())


def license_faults(text: str) -> list[str]:
    """``LICENSE`` is the MIT text with §S1's copyright line; an optional
    ``MIT License`` title line may lead it."""
    body = text.strip()
    if body.startswith("MIT License"):
        body = body[len("MIT License"):]
    if normalise_ws(body) != normalise_ws(MIT_LICENSE_BODY):
        return ["LICENSE is not the MIT license text with "
                "'Copyright (c) 2026 Antony John'"]
    return []


def summary_faults(summary: str | None) -> list[str]:
    if not summary or not summary.strip():
        return ["Summary is missing"]
    return [f"Summary carries internal vocabulary {m!r}: {summary!r}"
            for m in INTERNAL_MARKERS if m in summary]


def classifier_faults(classifiers: list[str]) -> list[str]:
    """Ruling R1 — the three classifier families; the Python family at the
    3.14 floor (CR-MDB-064 §S1)."""
    out = []
    licences = [c for c in classifiers if c.startswith("License ::")]
    if licences != [MIT_CLASSIFIER]:
        out.append(f"License classifiers must be exactly [{MIT_CLASSIFIER!r}]; got {licences!r}")
    for required in (PYTHON_3_CLASSIFIER, PYTHON_3_ONLY_CLASSIFIER, PYTHON_314_CLASSIFIER):
        if required not in classifiers:
            out.append(f"missing {required!r}")
    for c in classifiers:
        m = _PYTHON_VERSION_CLASSIFIER.fullmatch(c)
        if not m:
            continue
        major, minor = int(m.group(1)), m.group(2)
        if major < 3 or (minor is not None and (major, int(minor)) < PYTHON_FLOOR):
            out.append(f"Python classifier below 3.14: {c!r}")
    if CONSOLE_CLASSIFIER not in classifiers:
        out.append(f"missing {CONSOLE_CLASSIFIER!r}")
    return out


def package_version() -> str:
    match = re.search(r'__version__\s*=\s*"([^"]+)"', MODULE_INIT.read_text(encoding="utf-8"))
    if not match:
        raise AssertionError(f"could not find __version__ in {MODULE_INIT}")
    return match.group(1)


def parse_metadata(text: str):
    return email.parser.Parser(policy=email.policy.compat32).parsestr(text)


# ---------------------------------------------------------------------------
# Building (into temp dirs only)
# ---------------------------------------------------------------------------

def _uv() -> str:
    uv = shutil.which("uv")
    if uv is None:
        raise AssertionError("`uv` not found on PATH -- cannot build the artifacts "
                             "(guarded, not skipped)")
    return uv


def _run_uv_build(args: list[str], out_dir: Path) -> Path:
    result = subprocess.run(
        [_uv(), "build", *args, "--out-dir", str(out_dir)],
        capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"`uv build {' '.join(args)}` must succeed; exit={result.returncode}\n"
            f"stderr={result.stderr[-3000:]}"
        )
    return out_dir


def build_sdist(source: Path, out_dir: Path) -> Path:
    _run_uv_build([str(source), "--sdist"], out_dir)
    found = sorted(out_dir.glob("*.tar.gz"))
    if len(found) != 1:
        raise AssertionError(f"expected exactly one sdist in {out_dir}; got {found}")
    return found[0]


def build_wheel(source: Path, out_dir: Path) -> Path:
    """``source`` is an sdist archive or a source tree."""
    _run_uv_build([str(source), "--wheel"], out_dir)
    found = sorted(out_dir.glob("*.whl"))
    if len(found) != 1:
        raise AssertionError(f"expected exactly one wheel in {out_dir}; got {found}")
    return found[0]


_BUILD_ROOT: Path | None = None
_ARTIFACTS: tuple[Path, Path] | None = None


def artifacts() -> tuple[Path, Path]:
    """``(sdist, wheel-built-from-that-sdist)``, built once per module run."""
    global _BUILD_ROOT, _ARTIFACTS
    if _ARTIFACTS is None:
        _BUILD_ROOT = Path(tempfile.mkdtemp(prefix="modelb-publish-build-"))
        sdist = build_sdist(REPO_ROOT, _BUILD_ROOT / "sdist")
        wheel = build_wheel(sdist, _BUILD_ROOT / "wheel")
        _ARTIFACTS = (sdist, wheel)
    return _ARTIFACTS


def tearDownModule():
    global _ARTIFACTS
    if _BUILD_ROOT is not None:
        shutil.rmtree(_BUILD_ROOT, ignore_errors=True)
    # CR-MDB-058 C2 (orchestrator-approved): drop the cache too, so a later module's artifacts() rebuilds instead of reading the deleted build.
    _ARTIFACTS = None


def sdist_members(sdist: Path) -> dict[str, tarfile.TarInfo]:
    """sdist members keyed by path relative to the ``<name>-<version>/`` root."""
    with tarfile.open(sdist) as tar:
        out = {}
        for info in tar.getmembers():
            _root, _sep, rel = info.name.partition("/")
            if rel and info.isfile():
                out[rel] = info
        return out


def sdist_read(sdist: Path, rel: str) -> bytes:
    with tarfile.open(sdist) as tar:
        for info in tar.getmembers():
            if info.name.partition("/")[2] == rel:
                handle = tar.extractfile(info)
                if handle is None:
                    raise AssertionError(f"{rel} in {sdist.name} is not a regular file")
                return handle.read()
    raise AssertionError(f"{rel} not in {sdist.name}")


def wheel_names(wheel: Path) -> list[str]:
    with zipfile.ZipFile(wheel) as zf:
        return [n for n in zf.namelist() if not n.endswith("/")]


def wheel_dist_info(wheel: Path) -> str:
    dirs = {n.split("/", 1)[0] for n in wheel_names(wheel) if n.split("/", 1)[0].endswith(".dist-info")}
    if len(dirs) != 1:
        raise AssertionError(f"expected one .dist-info dir in {wheel.name}; got {sorted(dirs)}")
    return dirs.pop()


def wheel_read(wheel: Path, name: str) -> bytes:
    with zipfile.ZipFile(wheel) as zf:
        return zf.read(name)


def wheel_metadata(wheel: Path):
    text = wheel_read(wheel, f"{wheel_dist_info(wheel)}/METADATA").decode("utf-8")
    return parse_metadata(text)


def _pyproject() -> dict:
    with open(PYPROJECT, "rb") as fh:
        return tomllib.load(fh)


# ---------------------------------------------------------------------------
# §S1 — LICENSE
# ---------------------------------------------------------------------------

class LicenseFileTest(unittest.TestCase):
    """§S1 AC1 — the repository root carries the MIT license."""

    def test_license_file_is_mit_with_antony_john_2026_copyright(self):
        self.assertTrue(LICENSE.is_file(), f"§S1: {LICENSE.name} must exist at the repository root")
        self.assertEqual(license_faults(LICENSE.read_text(encoding="utf-8")), [])


# ---------------------------------------------------------------------------
# §S1 — wheel METADATA
# ---------------------------------------------------------------------------

class WheelMetadataTest(unittest.TestCase):
    """§S1 AC2 — read from ``METADATA`` of a wheel built (from the sdist) in
    the test."""

    @classmethod
    def setUpClass(cls):
        cls.sdist, cls.wheel = artifacts()
        cls.meta = wheel_metadata(cls.wheel)

    def test_summary_is_plain_language_without_design_note_cr_or_section_ids(self):
        self.assertEqual(summary_faults(self.meta.get("Summary")), [])

    def test_license_expression_is_mit_and_the_license_file_ships_in_the_wheel(self):
        self.assertEqual(self.meta.get_all("License-Expression"), ["MIT"],
                         "§S1: METADATA must carry exactly `License-Expression: MIT`")
        self.assertEqual(self.meta.get_all("License-File"), ["LICENSE"],
                         "§S1: METADATA must name exactly one License-File, LICENSE")
        shipped = f"{wheel_dist_info(self.wheel)}/licenses/LICENSE"
        self.assertIn(shipped, wheel_names(self.wheel),
                      "§S1: the wheel must carry the license file under .dist-info/licenses/")
        self.assertTrue(LICENSE.is_file(), "§S1: LICENSE must exist at the repository root")
        self.assertEqual(wheel_read(self.wheel, shipped), LICENSE.read_bytes(),
                         "§S1: the wheel's license file must be the repository LICENSE")

    def test_classifiers_name_mit_python_3_only_3_14_none_below_and_console(self):
        # MIGRATED at CR-MDB-064 C1 RED (§S1): the 3.14 floor's classifiers.
        self.assertEqual(classifier_faults(self.meta.get_all("Classifier") or []), [])

    def test_requires_python_is_3_14_and_only_the_changelog_and_release_notes_urls_are_published(self):
        # MIGRATED at CR-MDB-064 C1 RED (§S1; was `>=3.11`). MIGRATED at
        # CR-MDB-058 C2 RED (§S3): renamed from
        # test_requires_python_is_3_14_and_no_project_url_is_published; its URL
        # half moves from "no Project-URL while private" to §S3's two lines.
        self.assertEqual(self.meta.get_all("Requires-Python"), [REQUIRES_PYTHON],
                         "§S1: the built wheel must publish `Requires-Python: >=3.14`")
        project_urls = self.meta.get_all("Project-URL") or []
        self.assertCountEqual(project_urls, PROJECT_URL_LINES,
                              f"CR-MDB-058 §S3: the wheel carries exactly {PROJECT_URL_LINES}; "
                              f"got {project_urls!r}")
        self.assertEqual(self.meta.get_all("Home-page"), None,
                         "CR-MDB-058 §S3: Home-page stays absent")

    def test_description_body_is_the_install_guide_as_markdown(self):
        self.assertEqual(
            (self.meta.get("Description-Content-Type") or "").split(";")[0].strip(),
            "text/markdown",
            "§S1: the readme is markdown (docs/install-guide.md)",
        )
        body = str(self.meta.get_payload() or "")
        guide = GUIDE.read_text(encoding="utf-8")
        self.assertTrue(body.strip(), "§S1: METADATA must carry a description body")
        self.assertEqual(body.rstrip("\n"), guide.rstrip("\n"),
                         "§S1: the description body must be docs/install-guide.md, unchanged")


class PyprojectPythonFloorTest(unittest.TestCase):
    """CR-MDB-064 §S1 — ``pyproject.toml`` declares the 3.14 floor: read
    straight from the file, so the fault shows without a build."""

    def test_requires_python_declares_the_3_14_floor(self):
        self.assertEqual(_pyproject().get("project", {}).get("requires-python"), REQUIRES_PYTHON,
                         "§S1: pyproject.toml must declare requires-python = '>=3.14'")

    def test_version_classifiers_are_3_3_only_and_3_14_and_none_below(self):
        classifiers = _pyproject().get("project", {}).get("classifiers", [])
        self.assertEqual(classifier_faults(classifiers), [])
        python = [c for c in classifiers if c.startswith("Programming Language :: Python ::")]
        self.assertEqual(
            python, [PYTHON_3_CLASSIFIER, PYTHON_3_ONLY_CLASSIFIER, PYTHON_314_CLASSIFIER],
            "§S1: the version classifiers are `… :: 3`, `… :: 3 :: Only` and `… :: 3.14`",
        )


class PyprojectUrlsTest(unittest.TestCase):
    """CR-MDB-058 §S3 — ``pyproject.toml`` declares the two PEP 753 well-known links, read
    without a build."""

    def test_project_urls_are_exactly_changelog_on_master_and_release_notes(self):
        urls = _pyproject().get("project", {}).get("urls")
        self.assertEqual(urls, PROJECT_URLS,
                         f"§S3: [project.urls] must be exactly {PROJECT_URLS}; got {urls!r}")


# ---------------------------------------------------------------------------
# §S1 — one version
# ---------------------------------------------------------------------------

class SingleVersionSourceTest(unittest.TestCase):
    """§S1 AC3 + ruling R2 — ``__version__`` is the only version source."""

    def test_pyproject_carries_no_literal_version_and_declares_it_dynamic(self):
        project = _pyproject().get("project", {})
        self.assertNotIn("version", project,
                         f"§S1: pyproject.toml must carry no literal version; "
                         f"got version={project.get('version')!r}")
        self.assertIn("version", project.get("dynamic", []),
                      "§S1: [project].dynamic must list `version` (read by the build)")

    def test_built_wheel_version_equals_package_dunder_version(self):
        # Pin — equal at RED only because both literals agree today; the
        # probe below is what proves the build READS __version__.
        _sdist, wheel = artifacts()
        expected = package_version()
        self.assertEqual(wheel_metadata(wheel).get("Version"), expected)
        self.assertTrue(wheel.name.startswith(f"modelb_axi-{expected}-"),
                        f"wheel filename must carry {expected}; got {wheel.name}")

    def test_changing_dunder_version_alone_changes_the_built_version(self):
        root = Path(tempfile.mkdtemp(prefix="modelb-publish-version-probe-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        tree = root / "src"
        shutil.copytree(REPO_ROOT, tree, ignore=_COPY_IGNORE, symlinks=True)
        init = tree / "modelb_axi" / "__init__.py"
        text = init.read_text(encoding="utf-8")
        probed, count = re.subn(r'__version__\s*=\s*"[^"]+"', '__version__ = "9.9.9"', text)
        self.assertEqual(count, 1, "precondition: exactly one __version__ assignment")
        init.write_text(probed, encoding="utf-8")
        wheel = build_wheel(tree, root / "out")
        self.assertEqual(
            wheel_metadata(wheel).get("Version"), "9.9.9",
            "§S1: with __version__ = \"9.9.9\" and nothing else changed, the build "
            f"must produce 9.9.9; got {wheel.name}",
        )
        self.assertTrue(wheel.name.startswith("modelb_axi-9.9.9-"), wheel.name)


# ---------------------------------------------------------------------------
# §S1 — archive contents
# ---------------------------------------------------------------------------

class ArtifactContentsTest(unittest.TestCase):
    """§S1 AC4 — what the sdist and the wheel carry."""

    @classmethod
    def setUpClass(cls):
        cls.sdist, cls.wheel = artifacts()

    def test_sdist_carries_license_and_install_guide(self):
        members = sdist_members(self.sdist)
        missing = [rel for rel in ("LICENSE", "docs/install-guide.md") if rel not in members]
        self.assertEqual(missing, [], f"§S1: the sdist must contain {missing}")
        self.assertEqual(sdist_read(self.sdist, "docs/install-guide.md"), GUIDE.read_bytes())
        self.assertEqual(sdist_read(self.sdist, "LICENSE"), LICENSE.read_bytes())

    def test_no_artifact_carries_tests_archive_or_audits(self):
        # Pin — true at RED; guards the sdist include list GREEN widens.
        offenders = [f"sdist:{rel}" for rel in sdist_members(self.sdist)
                     if rel.split("/", 1)[0] in EXCLUDED_ROOTS]
        for name in wheel_names(self.wheel):
            parts = name.split("/")
            if parts[0] in EXCLUDED_ROOTS or (
                    parts[:2] == ["modelb_axi", "_assets"] and len(parts) > 2
                    and parts[2] in EXCLUDED_ROOTS):
                offenders.append(f"wheel:{name}")
        self.assertEqual(offenders, [], "§S1: no artifact may carry tests/, archive/ or audits/")

    def test_wheel_carries_every_tracked_file_of_every_force_include_root(self):
        # Pin — true at RED; guards the sdist -> wheel path losing an asset.
        force_include = (_pyproject().get("tool", {}).get("hatch", {}).get("build", {})
                         .get("targets", {}).get("wheel", {}).get("force-include", {}))
        self.assertEqual(
            sorted(force_include),
            ["generator", "hooks-src", "scripts", "skills-src"],
            "precondition: the four force-include asset roots (CR-MDB-031 \u00a7S4 dropped contracts)",
        )
        names = set(wheel_names(self.wheel))
        for src, dest in force_include.items():
            tracked = subprocess.run(
                ["git", "ls-files", "--", src], cwd=REPO_ROOT,
                capture_output=True, text=True, check=True,
            ).stdout.split()
            with self.subTest(root=src):
                self.assertTrue(tracked, f"precondition: {src} has tracked files")
                missing = [f for f in tracked if f"{dest}{f[len(src):]}" not in names]
                self.assertEqual(missing, [], f"§S1: the wheel must carry every file of {src}")


# ---------------------------------------------------------------------------
# §S2 — sdist -> wheel -> isolated install -> installer + init
# ---------------------------------------------------------------------------


def strip_line_comments(text: str) -> str:
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("//"))


def exercise_sdist(test: unittest.TestCase, sdist: Path) -> None:
    """§S2: build a wheel FROM ``sdist``, install it into an isolated tool
    dir, run the installed installer and ``init`` into sandboxes. Raises
    the test's failure on the first broken step."""
    root = Path(tempfile.mkdtemp(prefix="modelb-publish-s2-")).resolve()
    test.addCleanup(shutil.rmtree, root, ignore_errors=True)
    wheel = build_wheel(sdist, root / "wheel")

    tool_dir, tool_bin = root / "uv-tool", root / "uv-bin"
    install_env = dict(os.environ)
    install_env["UV_TOOL_DIR"] = str(tool_dir)
    install_env["UV_TOOL_BIN_DIR"] = str(tool_bin)
    install = subprocess.run(
        [_uv(), "tool", "install", str(wheel), "--force"],
        capture_output=True, text=True, timeout=300, env=install_env,
        stdin=subprocess.DEVNULL,
    )
    test.assertEqual(install.returncode, 0,
                     f"§S2: the wheel must install into the isolated tool dir; "
                     f"stderr={install.stderr[-2000:]}")
    binary = tool_bin / "modelb-axi"
    test.assertTrue(binary.exists(), f"§S2: {binary} must exist after the install")

    home = make_home(root / "home", crucible_manifest=False)
    agent_dir = make_provisioned_agent_dir(root / "agent")
    modelb_home, target_root, fake_bin = root / "modelb-home", root / "target", root / "fakebin"
    for d in (modelb_home, target_root, fake_bin, root / "xdg"):
        d.mkdir(parents=True)
    # MIGRATED at CR-MDB-064 C2 RED (§S7): the shared installer fixture — a `python3` at
    # the 3.14 floor (the interpreter is required, CR-MDB-064 §S2) and a `uv` answering
    # `uv python find --system '>=3.14'`, otherwise this module's fake.
    write_interpreter_fixture(fake_bin, uv_body=_FAKE_UV)
    (fake_bin / "sandesh").write_text(_FAKE_SANDESH, encoding="utf-8")
    (fake_bin / "sandesh").chmod(0o755)

    env = dict(os.environ)
    env.pop("PYTHONPATH", None)  # the repo copy must never shadow the install
    env.update({
        "HOME": str(home), AGENT_DIR_ENV: str(agent_dir),
        "MODELB_HOME": str(modelb_home), "XDG_DATA_HOME": str(root / "xdg"),
        "PATH": str(fake_bin),
    })
    installed = subprocess.run(
        [str(binary), "--yes", "--harnesses", "pi", "--stacks", "python",
         "--modelb-home", str(modelb_home), "--target-root", str(target_root)],
        capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL, env=env,
    )
    axi = decode_axi(installed.stdout)
    test.assertEqual(axi.get("outcome"), "installed",
                     f"§S2: the installed binary's installer run must reach `installed`; "
                     f"exit={installed.returncode} stdout={installed.stdout!r} "
                     f"stderr={installed.stderr[-2000:]!r}")
    test.assertEqual(installed.returncode, 0)
    with open(modelb_home / "install.toml", "rb") as fh:
        asset_root = Path(str(tomllib.load(fh).get("install", {}).get("asset_root", "")))
    test.assertEqual(asset_root.parts[-2:], ("modelb_axi", "_assets"),
                     f"§S2: assets must come from the installed package; got {asset_root}")
    test.assertTrue(str(asset_root).startswith(str(tool_dir.resolve())),
                    f"§S2: asset root must live under the isolated UV_TOOL_DIR; got {asset_root}")

    project = root / "work" / "proj"
    project.mkdir(parents=True)
    init_env = dict(env, PATH=os.pathsep.join([str(fake_bin), "/usr/bin", "/bin"]))
    init = subprocess.run(
        [str(binary), "--yes", "init", *_INIT_FLAGS, "--target", str(project),
         "--modelb-home", str(modelb_home), "--no-commit"],
        capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL, env=init_env,
    )
    test.assertEqual(init.returncode, 0,
                     f"§S2: the installed binary's init must succeed; stdout={init.stdout!r} "
                     f"stderr={init.stderr[-2000:]!r}")
    agents = project / ".pi" / "agents"
    rendered = sorted(p.name for p in agents.glob("*.md")) if agents.is_dir() else []
    test.assertEqual(rendered, sorted(f"python-{r}-agent.md" for r in TDD_ROLES),
                     "§S2: init must render exactly the four Pi agents for the python stack")
    for role in TDD_ROLES:
        text = (agents / f"python-{role}-agent.md").read_text(encoding="utf-8")
        test.assertIn(f"\nname: python-{role}-agent\n", text,
                      f"§S2: python-{role}-agent.md must carry its name in the frontmatter")
    policy = project / POLICY_REL
    test.assertTrue(policy.is_file(), f"§S2: init must render the project policy {POLICY_REL}")
    data = json.loads(strip_line_comments(policy.read_text(encoding="utf-8")))
    test.assertEqual(data.get("permission", {}).get("*"), "ask",
                     "§S2: the rendered policy must fall back to `ask`")


class BuiltArtifactsInstallAndWorkTest(unittest.TestCase):
    """§S2 AC1 — ruling R4: an acceptance pin (passes at RED)."""

    def test_wheel_built_from_sdist_installs_isolated_and_runs_installer_and_init(self):
        sdist, _wheel = artifacts()
        exercise_sdist(self, sdist)


# ---------------------------------------------------------------------------
# Checker proofs — the pure checkers pass a conforming input and catch faults
# ---------------------------------------------------------------------------

# MIGRATED at CR-MDB-064 C1 RED (§S7): the sample classifier sets follow the
# 3.14 floor (was: 3.11 and 3.12 in the conforming set).
_GOOD_CLASSIFIERS = [
    MIT_CLASSIFIER, PYTHON_3_CLASSIFIER, PYTHON_3_ONLY_CLASSIFIER, PYTHON_314_CLASSIFIER,
    CONSOLE_CLASSIFIER,
]


class PackageMetadataCheckerProofTest(unittest.TestCase):

    def test_license_checker_both_ways(self):
        good = "MIT License\n\n" + MIT_LICENSE_BODY
        self.assertEqual(license_faults(good), [])
        self.assertEqual(license_faults(MIT_LICENSE_BODY), [])
        for bad in (good.replace("2026 Antony John", "2025 Antony John"),
                    good.replace("NONINFRINGEMENT", "INFRINGEMENT"), ""):
            with self.subTest(bad=bad[:40]):
                self.assertEqual(len(license_faults(bad)), 1)

    def test_summary_checker_both_ways(self):
        self.assertEqual(summary_faults("Installer and project scaffolder for Model B."), [])
        self.assertEqual(
            summary_faults("Model B universal installer + scaffold entrypoint (adaptive "
                           "TUI), per DN-scaffold-packaging."),
            ["Summary carries internal vocabulary 'DN-': 'Model B universal installer + "
             "scaffold entrypoint (adaptive TUI), per DN-scaffold-packaging.'"],
        )
        self.assertEqual(len(summary_faults("See CR-MDB-038 §S1")), 2)
        self.assertEqual(summary_faults(None), ["Summary is missing"])

    def test_classifier_checker_both_ways(self):
        self.assertEqual(classifier_faults(_GOOD_CLASSIFIERS), [])
        # A version above the floor is not refused (a 3.15 classifier may join later).
        self.assertEqual(
            classifier_faults(_GOOD_CLASSIFIERS + ["Programming Language :: Python :: 3.15"]), [])
        cases = {
            "no licence": ([c for c in _GOOD_CLASSIFIERS if c != MIT_CLASSIFIER],
                           f"License classifiers must be exactly [{MIT_CLASSIFIER!r}]; got []"),
            "second licence": (_GOOD_CLASSIFIERS + ["License :: OSI Approved :: Apache Software License"],
                               f"License classifiers must be exactly [{MIT_CLASSIFIER!r}]; got "
                               f"[{MIT_CLASSIFIER!r}, 'License :: OSI Approved :: Apache Software License']"),
            "no 3.14": ([c for c in _GOOD_CLASSIFIERS if c != PYTHON_314_CLASSIFIER],
                        f"missing {PYTHON_314_CLASSIFIER!r}"),
            "no 3": ([c for c in _GOOD_CLASSIFIERS if c != PYTHON_3_CLASSIFIER],
                     f"missing {PYTHON_3_CLASSIFIER!r}"),
            "no 3 only": ([c for c in _GOOD_CLASSIFIERS if c != PYTHON_3_ONLY_CLASSIFIER],
                          f"missing {PYTHON_3_ONLY_CLASSIFIER!r}"),
            "3.13": (_GOOD_CLASSIFIERS + ["Programming Language :: Python :: 3.13"],
                     "Python classifier below 3.14: 'Programming Language :: Python :: 3.13'"),
            "3.11": (_GOOD_CLASSIFIERS + ["Programming Language :: Python :: 3.11"],
                     "Python classifier below 3.14: 'Programming Language :: Python :: 3.11'"),
            "python 2": (_GOOD_CLASSIFIERS + ["Programming Language :: Python :: 2"],
                         "Python classifier below 3.14: 'Programming Language :: Python :: 2'"),
            "no console": ([c for c in _GOOD_CLASSIFIERS if c != CONSOLE_CLASSIFIER],
                           f"missing {CONSOLE_CLASSIFIER!r}"),
        }
        for label, (classifiers, expected) in cases.items():
            with self.subTest(case=label):
                self.assertEqual(classifier_faults(classifiers), [expected])


# ---------------------------------------------------------------------------
# CR-MDB-069 §S1: every built-wheel check builds through build_wheel, isolated
# ---------------------------------------------------------------------------

#: The two built-wheel checks outside this module that once built without isolation, each
#: ``(module, check)``.
ISOLATED_WHEEL_CHECKS = (
    ("tests/test_tooling_detachment.py", "test_s7_built_wheel_carries_all_eight_tool_assets"),
    ("tests/test_project_registry_schema.py",
     "test_built_wheel_ships_the_schema_with_the_registry_keys"),
)
#: What names a build outside an isolated environment, or a skip on the `build` frontend.
NON_ISOLATED_BUILD_MARKERS = ("--no-isolation", 'find_spec("build")', '"-m", "build"')


def _callee(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def isolated_wheel_build_faults(source: str, check: str) -> list[str]:
    """CR-MDB-069 §S1 — the module ``source`` names no non-isolated build marker, imports
    ``build_wheel`` by name from ``tests.test_package_publishing`` and defines none of its own,
    and its test method ``check`` calls ``build_wheel`` and never ``skipTest`` (empty =
    conforming)."""
    out = [f"the module names {marker}" for marker in NON_ISOLATED_BUILD_MARKERS
           if marker in source]
    tree = ast.parse(source)
    if not any(isinstance(node, ast.ImportFrom) and node.module == "tests.test_package_publishing"
               and any(alias.name == "build_wheel" for alias in node.names)
               for node in tree.body):
        out.append("the module does not import build_wheel from tests.test_package_publishing")
    if any(isinstance(node, ast.FunctionDef) and node.name == "build_wheel"
           for node in ast.walk(tree)):
        out.append("the module defines its own build_wheel")
    defs = [node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == check]
    if len(defs) != 1:
        return out + [f"{check} is defined {len(defs)} times, not once"]
    callees = [_callee(node) for node in ast.walk(defs[0]) if isinstance(node, ast.Call)]
    if "build_wheel" not in callees:
        out.append(f"{check} does not call build_wheel")
    if "skipTest" in callees:
        out.append(f"{check} calls skipTest")
    return out


_SAMPLE_CHECK = "test_the_wheel_ships_the_asset"

#: A module whose built-wheel check conforms to §S1; another check in it may skip.
_CONFORMING_CHECK_SOURCE = f'''\
import tempfile
import unittest
import zipfile
from pathlib import Path

from tests.test_package_publishing import build_wheel

REPO_ROOT = Path(__file__).resolve().parent.parent


class WheelTest(unittest.TestCase):

    def {_SAMPLE_CHECK}(self):
        with tempfile.TemporaryDirectory() as outdir:
            wheel = build_wheel(REPO_ROOT, Path(outdir))
            with zipfile.ZipFile(wheel) as archive:
                self.assertIn("asset", archive.namelist())

    def test_another_check(self):
        self.skipTest("another check may skip")
'''

_INSIDE_THE_CHECK = "        with tempfile.TemporaryDirectory() as outdir:\n"

#: ``(label, old, new, fault)``: replacing ``old`` by ``new`` in the conforming source makes
#: :func:`isolated_wheel_build_faults` report exactly ``[fault]``.
_CHECK_MUTATIONS = (
    ("--no-isolation", _INSIDE_THE_CHECK,
     '        argv = ["--no-isolation"]\n' + _INSIDE_THE_CHECK,
     "the module names --no-isolation"),
    ("a find_spec skip", _INSIDE_THE_CHECK,
     '        spec = importlib.util.find_spec("build")\n' + _INSIDE_THE_CHECK,
     'the module names find_spec("build")'),
    ("the build frontend", _INSIDE_THE_CHECK,
     '        argv = [sys.executable, "-m", "build", "--wheel"]\n' + _INSIDE_THE_CHECK,
     'the module names "-m", "build"'),
    ("no build_wheel call", "wheel = build_wheel(REPO_ROOT, Path(outdir))",
     "wheel = sorted(Path(outdir).glob('*.whl'))[0]",
     f"{_SAMPLE_CHECK} does not call build_wheel"),
    ("a skipTest in the check", _INSIDE_THE_CHECK,
     '        self.skipTest("no uv")\n' + _INSIDE_THE_CHECK,
     f"{_SAMPLE_CHECK} calls skipTest"),
    ("no import of build_wheel", "from tests.test_package_publishing import build_wheel\n", "",
     "the module does not import build_wheel from tests.test_package_publishing"),
    ("a star import", "import build_wheel\n", "import *\n",
     "the module does not import build_wheel from tests.test_package_publishing"),
    ("a duplicated helper body", "\nclass WheelTest",
     "\ndef build_wheel(source, out_dir):\n    return out_dir\n\n\nclass WheelTest",
     "the module defines its own build_wheel"),
)


class IsolatedWheelBuildCheckerProofTest(unittest.TestCase):
    """CR-MDB-069 §S1 — the structural gate's checker, proved on sample source both ways."""

    def test_conforming_source_passes(self):
        self.assertEqual(isolated_wheel_build_faults(_CONFORMING_CHECK_SOURCE, _SAMPLE_CHECK), [])

    def test_each_fault_bites_exactly_once(self):
        for label, old, new, fault in _CHECK_MUTATIONS:
            with self.subTest(mutation=label):
                self.assertEqual(_CONFORMING_CHECK_SOURCE.count(old), 1, f"{old!r} must occur once")
                source = _CONFORMING_CHECK_SOURCE.replace(old, new)
                self.assertEqual(isolated_wheel_build_faults(source, _SAMPLE_CHECK), [fault])

    def test_a_skip_in_another_check_does_not_count(self):
        source = _CONFORMING_CHECK_SOURCE.replace(
            '        self.skipTest("another check may skip")\n',
            '        self.skipTest("another check may skip")\n        self.skipTest("twice")\n')
        self.assertEqual(isolated_wheel_build_faults(source, _SAMPLE_CHECK), [])

    def test_a_missing_check_is_a_fault_not_a_pass(self):
        self.assertEqual(
            isolated_wheel_build_faults(_CONFORMING_CHECK_SOURCE, "test_no_such_check"),
            ["test_no_such_check is defined 0 times, not once"])

    def test_the_old_non_isolated_check_bites_on_every_rule(self):
        source = _CONFORMING_CHECK_SOURCE.replace(
            "from tests.test_package_publishing import build_wheel\n",
            "import importlib.util\nimport subprocess\nimport sys\n",
        ).replace(
            "            wheel = build_wheel(REPO_ROOT, Path(outdir))\n",
            '            if importlib.util.find_spec("build") is None:\n'
            '                self.skipTest("the `build` frontend is unavailable")\n'
            '            subprocess.run([sys.executable, "-m", "build", "--wheel", "--no-isolation",\n'
            '                            "--outdir", outdir, str(REPO_ROOT)])\n'
            "            wheel = sorted(Path(outdir).glob('*.whl'))[0]\n",
        )
        self.assertEqual(isolated_wheel_build_faults(source, _SAMPLE_CHECK), [
            "the module names --no-isolation",
            'the module names find_spec("build")',
            'the module names "-m", "build"',
            "the module does not import build_wheel from tests.test_package_publishing",
            f"{_SAMPLE_CHECK} does not call build_wheel",
            f"{_SAMPLE_CHECK} calls skipTest",
        ])


class IsolatedWheelBuildGateTest(unittest.TestCase):
    """CR-MDB-069 §S1 — the two built-wheel checks build through the shared isolated
    ``build_wheel`` (``uv build``), never with the `build` frontend, and never skip."""

    maxDiff = None

    def test_the_two_built_wheel_checks_build_through_the_shared_isolated_helper(self):
        for rel, check in ISOLATED_WHEEL_CHECKS:
            with self.subTest(module=rel):
                source = (REPO_ROOT / rel).read_text(encoding="utf-8")
                self.assertEqual(isolated_wheel_build_faults(source, check), [],
                                 f"CR-MDB-069 §S1: {rel}'s {check}")


if __name__ == "__main__":
    unittest.main()
