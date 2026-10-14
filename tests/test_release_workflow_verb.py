"""``modelb-axi release-workflow`` re-renders a project's release workflow (CR-MDB-068 §S6).

Contract: ``docs/changes/CR-MDB-068-release-and-ci-workflow-templates.md`` §S6 and its acceptance
criterion: the verb in a sandbox project — first render, re-render unchanged, a hand-modified file
skipped then forced, an unmanaged file left, ``--release-targets`` recorded and ``""`` recorded
empty, the absent key refused, each exit code (2 and 3), the envelope fields; ``agents --stacks``
warns; ``workflows.render`` has exactly two callers.

Class map:

- ``ReleaseWorkflowParserTest`` — the verb's own subparser: ``--release-targets``,
  ``--force-managed`` and ``--modelb-home``, and no ``--stacks``.
- ``ReleaseWorkflowRenderTest`` — first render (all three ``written``, each byte for byte
  ``workflows.render(<PROJECT_STACKS>, <RELEASE_TARGETS>, scaffold._workflow_sources(home))``),
  re-render (all ``unchanged``, nothing written), the stacks read from ``PROJECT_STACKS``, the
  envelope's fields (verb ``release-workflow``: ``written``, ``unchanged``, ``skipped``,
  ``unmanaged``, ``stacks``, ``targets``, ``warnings``).
- ``ReleaseWorkflowOwnershipTest`` — a hand-modified file skipped with one warning naming it and
  ``--force-managed``, then overwritten by ``--force-managed``; a file without the marker left
  byte for byte, reported ``unmanaged`` with one warning, even with ``--force-managed``.
- ``ReleaseWorkflowTargetsTest`` — ``--release-targets <csv>`` replaces the set and records its
  canonical form in ``.env``; ``--release-targets ""`` records it empty; without the flag the
  recorded value is rendered.
- ``ReleaseWorkflowRefusalsTest`` — exit 2 with an ``ok: false`` envelope and nothing written: no
  ``.env``; ``RELEASE_TARGETS`` absent and no flag (naming ``--release-targets``); an invalid flag
  value; an invalid recorded value. Exit 3 on an I/O error.
- ``AgentsStacksWarnsOfTheReleaseWorkflowTest`` — ``modelb-axi agents --stacks`` warns, once,
  naming ``.github/workflows/release.yml`` and ``modelb-axi release-workflow``, when a managed
  ``release.yml`` exists, and leaves it byte for byte; no warning without ``--stacks``, without a
  ``release.yml`` or with an unmanaged one.
- ``RenderCallersProofTest`` / ``RenderCallersTest`` — :func:`render_callers` proved on synthetic
  sources both ways, then applied to ``modelb_axi/``: ``workflows.render`` is called from exactly
  two functions, ``scaffold.run_init`` and the function ``cli.main`` dispatches the verb to.

The I/O-error seam: a regular FILE at ``<project>/.github/workflows`` — creating
``release.yml`` beneath it fails with an ``OSError`` (no mock; any implementation writing the file
meets it).

Isolation: the project is created by an in-process ``run_init`` in the sandbox of
``tests.test_project_setup_section``; the verb runs as ``python -m modelb_axi --modelb-home <home>
release-workflow`` from the project directory, with ``MODELB_HOME``, ``XDG_DATA_HOME``, ``HOME``
and ``PI_CODING_AGENT_DIR`` pinned under the sandbox.

Stdlib only.
"""

import argparse
import ast
import contextlib
import io
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from modelb_axi import cli, scaffold
from tests import test_project_setup_section as _setup
from tests._helpers import decode_axi
from tests.pi_capability_sandbox import AGENT_DIR_ENV
from tests.test_workflow_render import (
    RELEASE_YML,
    RENDERED_FILES,
    SECTION,
    STAMP,
    render_files,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
VERB = "release-workflow"
#: §S6 — every field the verb's envelope carries.
ENVELOPE_FIELDS = ("written", "unchanged", "skipped", "unmanaged", "stacks", "targets", "warnings")
#: The verb a warning points to for re-rendering the workflow.
VERB_COMMAND = "modelb-axi release-workflow"


def cli_subparser(name: str) -> argparse.ArgumentParser:
    """The ``modelb-axi`` subparser of the subcommand ``name`` (a ``KeyError`` when absent)."""
    parser = cli._build_parser()
    sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    return sub.choices[name]


# ------------------------------------------------------------------ the render-callers gate ----

def _bound_names(tree: ast.AST) -> tuple[set[str], set[str]]:
    """``(names bound to the workflows module, names bound to its render)`` in ``tree``."""
    modules, functions = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                bound = alias.asname or alias.name
                if alias.name == "workflows" and module in ("modelb_axi", ""):
                    modules.add(bound)
                elif alias.name == "render" and module.split(".")[-1] == "workflows":
                    functions.add(bound)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "modelb_axi.workflows" and alias.asname:
                    modules.add(alias.asname)
    return modules, functions


def _calls_render(call: ast.Call, modules: set[str], functions: set[str]) -> bool:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id in functions
    if isinstance(func, ast.Attribute) and func.attr == "render":
        owner = func.value
        return ((isinstance(owner, ast.Name) and owner.id in modules)
                or (isinstance(owner, ast.Attribute) and owner.attr == "workflows"))
    return False


def render_callers(sources: dict[str, str]) -> list[tuple[str, str]]:
    """``(module, top-level function)`` of every function calling ``workflows.render`` in
    ``sources`` (module name -> source text), sorted, each once — however ``render`` or its module
    was imported; a call outside any function is attributed to ``<module>``."""
    found = set()
    for module, source in sources.items():
        tree = ast.parse(source)
        modules, functions = _bound_names(tree)
        for top in tree.body:
            named = isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            owner = top.name if named else "<module>"
            for node in ast.walk(top):
                if isinstance(node, ast.Call) and _calls_render(node, modules, functions):
                    found.add((module, owner))
    return sorted(found)


def called_names(source: str, function: str) -> set[str]:
    """Every name ``function`` (top level of ``source``) calls, plain or as an attribute."""
    tree = ast.parse(source)
    target = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function),
                  None)
    if target is None:
        raise AssertionError(f"no top-level function {function!r}")
    names = set()
    for node in ast.walk(target):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
    return names


#: Synthetic sources the gate is proved on.
_GOOD = {
    "scaffold": ("from modelb_axi import workflows\n"
                 "def run_init(args):\n"
                 "    return workflows.render(args, [], None)\n"
                 "def run_release_workflow(args):\n"
                 "    '''Not a call: workflows.render(args) in a docstring.'''\n"
                 "    # nor this: workflows.render(args)\n"
                 "    return workflows.render(args, [], None)\n"),
    "agents": ("def render(stack):\n"
               "    return stack\n"
               "def render_project(stack):\n"
               "    return render(stack)\n"),
}
_ALIASED = {"migrate": ("from modelb_axi.workflows import render as draw\n"
                        "def migrate(project):\n"
                        "    return draw(project, [], None)\n")}
_RELATIVE = {"later": ("from . import workflows as wf\n"
                       "class Later:\n"
                       "    def go(self):\n"
                       "        return wf.render([], [], None)\n")}


class RenderCallersProofTest(unittest.TestCase):
    """The gate's reader, proved both ways on synthetic sources."""

    def test_two_direct_callers_are_found_and_a_docstring_or_another_render_is_not(self):
        self.assertEqual(render_callers(_GOOD),
                         [("scaffold", "run_init"), ("scaffold", "run_release_workflow")])

    def test_a_third_caller_through_an_aliased_import_is_found(self):
        self.assertEqual(render_callers({**_GOOD, **_ALIASED}),
                         [("migrate", "migrate"), ("scaffold", "run_init"),
                          ("scaffold", "run_release_workflow")])

    def test_a_relative_module_alias_inside_a_class_is_found(self):
        self.assertEqual(render_callers(_RELATIVE), [("later", "Later")])

    def test_the_dispatch_reader_reads_the_functions_main_calls(self):
        source = ("def main(argv):\n"
                  "    if argv:\n"
                  "        return scaffold.run_release_workflow(argv, None)\n"
                  "    return run_agents(argv)\n")
        self.assertEqual(called_names(source, "main"), {"run_release_workflow", "run_agents"})


class RenderCallersTest(unittest.TestCase):
    """§S6 — ``workflows.render`` is called by ``run_init`` and the verb only."""

    def test_render_has_exactly_two_callers_run_init_and_the_verb(self):
        sources = {path.stem: path.read_text(encoding="utf-8")
                   for path in sorted((REPO_ROOT / "modelb_axi").glob("*.py"))}
        callers = render_callers(sources)
        self.assertEqual(len(callers), 2, f"§S6: exactly two callers; got {callers!r}")
        self.assertIn(("scaffold", "run_init"), callers, "§S5/§S6: run_init renders the files")
        (_module, verb_function), = [c for c in callers if c != ("scaffold", "run_init")]
        self.assertIn(verb_function, called_names(sources["cli"], "main"),
                      f"§S6: the second caller, {verb_function}, is what cli.main dispatches to")


# ------------------------------------------------------------------ the sandbox ----

class _VerbCase(_setup._Case):
    """A project created by ``init`` (python, solo, no release target) in the CR-MDB-045 sandbox,
    and the verb run from its directory."""

    def setUp(self):
        super().setUp()
        self.xdg = self.root / "xdg"
        self.xdg.mkdir()
        self.init_ok()

    def verb(self, *args: str, cwd: Path | None = None) -> tuple[int, dict, str]:
        """``python -m modelb_axi --modelb-home <home> release-workflow <args>`` from ``cwd``
        (default: the project); ``(exit code, decoded axi, stderr)``."""
        env = dict(os.environ)
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + existing if existing else "")
        env.update({"HOME": str(self.home), "MODELB_HOME": str(self.modelb_home),
                    "XDG_DATA_HOME": str(self.xdg), AGENT_DIR_ENV: str(self.agent_dir)})
        for name in ("HOME", "MODELB_HOME", "XDG_DATA_HOME", AGENT_DIR_ENV):
            self.assertTrue(env[name].startswith(str(self.root)), f"sandbox guard: {name}")
        result = subprocess.run(
            [sys.executable, "-m", "modelb_axi", "--modelb-home", str(self.modelb_home), VERB,
             *args],
            cwd=str(cwd or self.target), env=env, capture_output=True, text=True, timeout=120,
            stdin=subprocess.DEVNULL)
        return result.returncode, decode_axi(result.stdout), result.stderr

    def verb_ok(self, *args: str) -> dict:
        rc, axi, err = self.verb(*args)
        self.assertEqual((rc, axi.get("verb"), axi.get("ok")), (0, VERB, True),
                         f"§S6: the verb succeeds; stderr={err!r}")
        return axi

    def expected(self, stacks: list[str], targets: list[str]) -> dict:
        return render_files(stacks, targets, scaffold._workflow_sources(self.modelb_home))

    def drop_github(self) -> None:
        shutil.rmtree(self.target / ".github", ignore_errors=True)

    def snapshot(self, root: Path | None = None) -> dict:
        root = root or self.target
        return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*"))
                if p.is_file() and ".git" not in p.relative_to(root).parts}

    def env_text(self) -> str:
        return (self.target / ".env").read_text(encoding="utf-8")

    def set_env_key(self, key: str, value: str | None) -> None:
        """Set ``key=value`` in the project's ``.env`` (``None`` removes the line)."""
        lines = [ln for ln in self.env_text().splitlines(keepends=True)
                 if not ln.startswith(key + "=")]
        if value is not None:
            lines.append(f"{key}={value}\n")
        (self.target / ".env").write_text("".join(lines), encoding="utf-8")

    def key_lines(self, key: str) -> list[str]:
        return [ln for ln in self.env_text().splitlines(keepends=True) if ln.startswith(key + "=")]

    def assert_files(self, stacks: list[str], targets: list[str]) -> None:
        for rel, text in self.expected(stacks, targets).items():
            with self.subTest(file=rel):
                path = self.target / rel
                self.assertTrue(path.is_file(), f"§S6: {rel} is written")
                self.assertEqual(path.read_text(encoding="utf-8"), text,
                                 f"§S6: {rel} is render({stacks!r}, {targets!r})'s text")

    def assert_refused(self, rc: int, axi: dict, err: str, *named: str) -> None:
        self.assertEqual((rc, axi.get("verb"), axi.get("ok")), (2, VERB, False),
                         f"§S6: a refusal exits 2 with an ok:false envelope; stderr={err!r}")
        warnings = axi.get("warnings") or []
        for needle in named:
            self.assertTrue([w for w in warnings if needle in w],
                            f"§S6: the refusal names {needle!r}; warnings={warnings!r}")


# ------------------------------------------------------------------ the parser ----

class ReleaseWorkflowParserTest(unittest.TestCase):
    """§S6 — the verb's own parser, beside ``agents``; no ``--stacks``."""

    def _options(self) -> set:
        return {s for a in cli_subparser(VERB)._actions for s in a.option_strings}

    def test_the_verb_takes_release_targets_force_managed_and_modelb_home(self):
        options = self._options()
        for flag in ("--release-targets", "--force-managed", "--modelb-home"):
            self.assertIn(flag, options, f"§S6: release-workflow accepts {flag}")

    def test_the_verb_has_no_stacks_option(self):
        self.assertNotIn("--stacks", self._options(),
                         "§S6: no --stacks — the stacks are `agents --stacks`'s")


class ReleaseWorkflowNoStacksRunTest(_VerbCase):
    """§S6 — ``--stacks`` is refused by the parser and changes nothing."""

    def test_a_stacks_flag_is_an_unrecognised_argument(self):
        before = self.snapshot()
        rc, _axi, err = self.verb("--stacks", "python,bun")
        self.assertEqual(rc, 2, f"argparse refuses it; stderr={err!r}")
        self.assertIn("unrecognized arguments: --stacks", err,
                      "§S6: the verb parses and refuses --stacks (it is not an unknown verb)")
        self.assertEqual(self.snapshot(), before, "nothing is written")


# ------------------------------------------------------------------ rendering ----

class ReleaseWorkflowRenderTest(_VerbCase):
    """§S6 — first render, re-render, the stacks, the envelope."""

    def test_a_first_render_writes_the_three_files_and_reports_every_field(self):
        self.drop_github()
        axi = self.verb_ok()
        self.assertEqual(sorted(f for f in ENVELOPE_FIELDS if f in axi), sorted(ENVELOPE_FIELDS),
                         f"§S6: the envelope carries every field; got {axi!r}")
        self.assertEqual(sorted(axi["written"]), sorted(RENDERED_FILES))
        self.assertEqual((axi["unchanged"], axi["skipped"], axi["unmanaged"]), ([], [], []))
        self.assertEqual((axi["stacks"], axi["targets"], axi["warnings"]), (["python"], [], []))
        self.assert_files(["python"], [])

    def test_a_re_render_reports_every_file_unchanged_and_writes_nothing(self):
        self.drop_github()
        self.verb_ok()
        before = self.snapshot()
        axi = self.verb_ok()
        self.assertEqual(axi.get("written"), [], "§S6: nothing to rewrite")
        self.assertEqual(sorted(axi.get("unchanged") or []), sorted(RENDERED_FILES))
        self.assertEqual(self.snapshot(), before, "§S6: a re-render changes no byte")

    def test_the_files_init_rendered_are_unchanged(self):
        axi = self.verb_ok()
        self.assertEqual((axi.get("written"), sorted(axi.get("unchanged") or [])),
                         ([], sorted(RENDERED_FILES)),
                         "§S5/§S6: init and the verb render the same files")

    def test_the_stacks_are_the_recorded_project_stacks(self):
        self.set_env_key("PROJECT_STACKS", "python,bun")
        self.drop_github()
        axi = self.verb_ok()
        self.assertEqual(axi.get("stacks"), ["python", "bun"], "§S6: PROJECT_STACKS is read")
        self.assert_files(["python", "bun"], [])
        self.assertEqual(self.key_lines("PROJECT_STACKS"), ["PROJECT_STACKS=python,bun\n"],
                         "§S6: the verb never rewrites PROJECT_STACKS")


class ReleaseWorkflowOwnershipTest(_VerbCase):
    """§S6 — the ownership rules of ``place_owned``."""

    def setUp(self):
        super().setUp()
        self.drop_github()
        self.verb_ok()

    def _warnings_naming(self, axi: dict, rel: str) -> list[str]:
        return [w for w in axi.get("warnings") or [] if rel in w]

    def test_a_hand_modified_file_is_skipped_then_forced(self):
        path = self.target / RELEASE_YML
        edited = path.read_text(encoding="utf-8") + "# a hand edit\n"
        path.write_text(edited, encoding="utf-8")
        axi = self.verb_ok()
        self.assertEqual(axi.get("skipped"), [RELEASE_YML], f"§S6: skipped; {axi!r}")
        self.assertEqual(sorted(axi.get("unchanged") or []), sorted([STAMP, SECTION]))
        self.assertEqual(axi.get("written"), [])
        self.assertEqual(path.read_text(encoding="utf-8"), edited, "§S6: the edit is kept")
        hits = self._warnings_naming(axi, RELEASE_YML)
        self.assertEqual(len(hits), 1, f"§S6: one warning per skipped file; {axi!r}")
        self.assertIn("--force-managed", hits[0], "the warning names the override")
        self.assertEqual(len(axi.get("warnings") or []), 1, "no other warning")
        forced = self.verb_ok("--force-managed")
        self.assertEqual(forced.get("written"), [RELEASE_YML], f"§S6: forced; {forced!r}")
        self.assertEqual((forced.get("skipped"), forced.get("warnings")), ([], []))
        self.assert_files(["python"], [])

    def test_an_unmanaged_file_is_left_alone_even_when_forced(self):
        path = self.target / STAMP
        path.write_text("print('the project owns this')\n", encoding="utf-8")
        for args in ((), ("--force-managed",)):
            with self.subTest(args=args):
                axi = self.verb_ok(*args)
                self.assertEqual(axi.get("unmanaged"), [STAMP], f"§S6: unmanaged; {axi!r}")
                self.assertNotIn(STAMP, axi.get("written") or [])
                self.assertEqual(path.read_text(encoding="utf-8"),
                                 "print('the project owns this')\n", "§S6: left byte for byte")
                self.assertEqual(len(self._warnings_naming(axi, STAMP)), 1,
                                 f"§S6: one warning per unmanaged file; {axi!r}")
                self.assertEqual(len(axi.get("warnings") or []), 1, "no other warning")


class ReleaseWorkflowTargetsTest(_VerbCase):
    """§S6 — ``--release-targets`` replaces and records the set; the recorded value is read."""

    def test_the_flag_records_the_canonical_targets_and_renders_them(self):
        others = [ln for ln in self.env_text().splitlines() if not ln.startswith("RELEASE_TARGETS=")]
        axi = self.verb_ok("--release-targets", "npm:./pkg/,pypi")
        self.assertEqual(self.key_lines("RELEASE_TARGETS"), ["RELEASE_TARGETS=pypi,npm:pkg\n"],
                         "§S6: the canonical value is recorded once")
        self.assertEqual([ln for ln in self.env_text().splitlines()
                          if not ln.startswith("RELEASE_TARGETS=")], others,
                         "§S6: no other .env line changes")
        self.assertEqual(axi.get("targets"), ["pypi", "npm:pkg"])
        self.assert_files(["python"], ["pypi", "npm:pkg"])

    def test_an_empty_flag_records_the_key_empty_and_renders_no_target(self):
        self.set_env_key("RELEASE_TARGETS", "pypi")
        axi = self.verb_ok("--release-targets", "")
        self.assertEqual(self.key_lines("RELEASE_TARGETS"), ["RELEASE_TARGETS=\n"],
                         "§S6: --release-targets \"\" records empty")
        self.assertEqual(axi.get("targets"), [])
        self.assert_files(["python"], [])

    def test_without_the_flag_the_recorded_value_is_rendered(self):
        self.set_env_key("RELEASE_TARGETS", "github-assets,pypi")
        axi = self.verb_ok()
        self.assertEqual(axi.get("targets"), ["pypi", "github-assets"])
        self.assert_files(["python"], ["pypi", "github-assets"])
        self.assertEqual(self.key_lines("RELEASE_TARGETS"),
                         ["RELEASE_TARGETS=github-assets,pypi\n"],
                         "§S6: without the flag the recorded line is not rewritten")

    def test_the_flag_records_the_key_when_it_was_absent(self):
        self.set_env_key("RELEASE_TARGETS", None)
        axi = self.verb_ok("--release-targets", "npm")
        self.assertEqual(self.key_lines("RELEASE_TARGETS"), ["RELEASE_TARGETS=npm\n"])
        self.assertEqual(axi.get("targets"), ["npm"])
        self.assert_files(["python"], ["npm"])


class ReleaseWorkflowRefusalsTest(_VerbCase):
    """§S6 — exit 2 on a refusal, writing nothing; exit 3 on an I/O error."""

    def test_no_env_is_refused(self):
        empty = self.root / "not-a-project"
        empty.mkdir()
        rc, axi, err = self.verb(cwd=empty)
        self.assert_refused(rc, axi, err, ".env")
        self.assertEqual(list(empty.iterdir()), [], "§S6: nothing is written")

    def test_an_absent_key_without_the_flag_is_refused_naming_the_flag(self):
        self.set_env_key("RELEASE_TARGETS", None)
        self.drop_github()
        before = self.snapshot()
        self.assert_refused(*self.verb(), "--release-targets")
        self.assertEqual(self.snapshot(), before, "§S6: nothing is written")

    def test_an_invalid_flag_value_is_refused(self):
        before = self.snapshot()
        self.assert_refused(*self.verb("--release-targets", "crates"), "crates")
        self.assertEqual(self.snapshot(), before, "§S6: nothing is written, .env included")

    def test_an_invalid_recorded_value_is_refused(self):
        self.set_env_key("RELEASE_TARGETS", "pypi,maven-central")
        self.drop_github()
        before = self.snapshot()
        self.assert_refused(*self.verb(), "maven-central")
        self.assertEqual(self.snapshot(), before, "§S6: nothing is written")

    def test_an_io_error_exits_3(self):
        # The seam: a regular file where the workflows directory belongs.
        self.drop_github()
        (self.target / ".github").mkdir()
        (self.target / ".github" / "workflows").write_text("not a directory\n", encoding="utf-8")
        rc, axi, err = self.verb()
        self.assertEqual((rc, axi.get("verb"), axi.get("ok")), (3, VERB, False),
                         f"§S6: an I/O error exits 3 with an ok:false envelope; stderr={err!r}")
        self.assertTrue(axi.get("warnings"), f"§S6: the envelope names the error; {axi!r}")


# ------------------------------------------------------------------ agents --stacks ----

class AgentsStacksWarnsOfTheReleaseWorkflowTest(_VerbCase):
    """§S6 — ``agents --stacks`` warns that a managed ``release.yml`` is not re-rendered."""

    def setUp(self):
        super().setUp()
        self.release = self.target / RELEASE_YML
        self.release.parent.mkdir(parents=True, exist_ok=True)
        self.release.write_text(self.expected(["python"], [])[RELEASE_YML], encoding="utf-8")

    def agents(self, stacks: str | None) -> dict:
        args = argparse.Namespace(stacks=stacks, force_managed=False)
        out, err = io.StringIO(), io.StringIO()
        with (
            mock.patch.dict(os.environ, {"HOME": str(self.home), AGENT_DIR_ENV: str(self.agent_dir)}),
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err),
        ):
            rc = scaffold.run_agents(args, self.modelb_home, project_root=self.target)
        axi = decode_axi(out.getvalue())
        self.assertEqual((rc, axi.get("ok")), (0, True), f"agents succeeds; stderr={err.getvalue()!r}")
        return axi

    def release_warnings(self, axi: dict) -> list[str]:
        return [w for w in axi.get("warnings") or [] if "release.yml" in w]

    def test_agents_stacks_warns_once_when_a_managed_release_yml_exists(self):
        before = self.release.read_bytes()
        hits = self.release_warnings(self.agents("python,rust"))
        self.assertEqual(len(hits), 1, f"§S6: one warning; got {hits!r}")
        self.assertIn(RELEASE_YML, hits[0], "the warning names the workflow")
        self.assertIn(VERB_COMMAND, hits[0], "the warning names the verb that re-renders it")
        self.assertEqual(self.release.read_bytes(), before, "§S6: agents does not re-render it")

    def test_agents_without_stacks_does_not_warn(self):
        self.assertEqual(self.release_warnings(self.agents(None)), [])

    def test_agents_stacks_without_a_release_yml_does_not_warn(self):
        self.drop_github()
        self.assertEqual(self.release_warnings(self.agents("python,rust")), [])

    def test_agents_stacks_with_an_unmanaged_release_yml_does_not_warn(self):
        self.release.write_text("name: the project's own\n", encoding="utf-8")
        self.assertEqual(self.release_warnings(self.agents("python,rust")), [])


if __name__ == "__main__":
    unittest.main()
