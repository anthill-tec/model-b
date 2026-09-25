"""Worktree isolation on Pi: the Model B Pi package's worktree extension,
``pi-package/extensions/worktree.ts`` (CR-MDB-039 §S1), and the ``watcher``
capability that now also provides it (§S3). DN-multi-harness §D19.

The extension is loaded by ``tests/fixtures/pi_worktree_harness.mjs`` with the
``jiti`` mechanism Pi's own loader uses (the CR-MDB-030 §S8 pattern,
``tests/test_pi_hook_runtime.py``; the loader environment and its skips are
``_require_loader_env``'s). The harness hands the factory a recording fake
``pi`` and a fake pi-subagents service published under the service key, then
runs a JSON step script:

- the fake service mirrors the installed ``@gotgenes/pi-subagents``
  (``src/service/service.ts``, ``subagent-manager.ts``): it counts every
  ``registerWorkspaceProvider`` call, refuses a second provider while one is
  active, returns an unregister function, and answers ``getRecord(agentId)``
  with the record a ``prepare`` step registered BEFORE calling the provider
  (the real manager registers the child's record before ``prepare`` runs);
- a ``prepare`` step is one dispatch: it fires the extension's ``tool_call``
  handlers with the pi-subagents ``subagent`` call, registers the record, then
  calls the active provider's ``prepare({agentId, agentType, baseCwd})``.

Lazy registration ("looked up lazily, at first use, so load order does not
matter"): every scenario fires ``session_start`` after the factory; a dispatch
fires ``tool_call`` before the provider is needed; tool calls run where the
test says. A provider registered at load, at ``session_start``, on the
dispatch's ``tool_call`` or on a tool call all satisfy these tests; the
load-order test publishes the service only AFTER the factory ran.

Fixture repositories are real throwaway git repos under the temp dir, with
worktrees at ``.worktrees/<cr>`` added by ``git worktree add``. The hook
integration drives the REAL ``hooks-src/scripts/block-write-outside-worktree``
through a hook extension compiled by ``modelb_axi.hooks.compile_wiring``,
loaded into the SAME harness process, so the ``WF_WORKTREE_ROOT`` the tool
set is the one the hook's child process inherits. The script allows every
write under ``/tmp`` and ``$TMPDIR`` (scratch), so "outside" targets lie
under neither -- they are fixed system paths, never the checkout (which may
itself live under ``/tmp``). The script only decides, it never writes.

A child session loads pi-subagents too: its own service instance republishes,
then deletes, the global service entry (pi-subagents ``src/index.ts``,
``handlers/lifecycle.ts``). The harness's ``replaceService`` and
``deleteService`` steps reproduce that.

Stdlib only.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests._helpers import rel_to_repo
from tests.test_pi_hook_runtime import _require_loader_env
from tests.test_worktree_layout_and_bundles import _git_c3 as _git

REPO_ROOT = Path(__file__).resolve().parent.parent
PI_PACKAGE = REPO_ROOT / "pi-package"
PACKAGE_JSON = PI_PACKAGE / "package.json"
EXTENSION = PI_PACKAGE / "extensions" / "worktree.ts"
HARNESS_MJS = REPO_ROOT / "tests" / "fixtures" / "pi_worktree_harness.mjs"
REAL_SCRIPTS_ROOT = REPO_ROOT / "hooks-src" / "scripts"
AGENTS_DIR = REPO_ROOT / "generator" / "agents"

ENTER = "modelb_worktree_enter"
EXIT = "modelb_worktree_exit"

#: The pi-subagents service key (CR-MDB-039 Context 1); the fake service is
#: published under it, and the contract test pins it to the installed source.
SERVICE_KEY = "@gotgenes/pi-subagents:service"

#: Where the installed pi-subagents declares its service key.
PI_SUBAGENTS_SERVICE_TS_REL = Path("npm/node_modules/@gotgenes/pi-subagents/src/service/service.ts")

_HARNESS_BUDGET_S = 60.0

#: Write targets outside every fixture worktree AND outside /tmp and
#: $TMPDIR (the script's scratch allowance), wherever the checkout lives.
#: Never written -- only judged. ``WorktreeOutsideTargetsTest`` pins that
#: neither lies under the scratch allowance.
OUTSIDE_ETC = "/etc/modelb-cr039-outside-fixture.txt"
OUTSIDE_VAR = "/var/lib/modelb-cr039-outside-fixture/another-tree/src/x.py"


def _under_scratch(path: str) -> bool:
    """``path`` lies under ``/tmp`` or ``$TMPDIR`` (both resolved), the hook
    script's scratch allowance."""
    real = os.path.realpath(path)
    roots = ["/tmp", os.path.realpath("/tmp")]
    tmpdir = os.environ.get("TMPDIR", "")
    if tmpdir:
        roots.append(os.path.realpath(tmpdir))
    roots.append(os.path.realpath(tempfile.gettempdir()))
    return any(f"{real}/".startswith(f"{root.rstrip('/')}/") for root in roots)

_SYMBOL_FOR = re.compile(r"""Symbol\.for\(\s*(["'`])(.*?)\1\s*\)""")
_TOOLS_LINE = re.compile(r"^tools:\s*(.*)$", re.M)


def _symbol_for_keys(source: str) -> list[str]:
    """Every string key passed to ``Symbol.for(...)`` in ``source``, in order."""
    return [m.group(2) for m in _SYMBOL_FOR.finditer(source)]


def _frontmatter_tools(markdown: str) -> list[str]:
    """The comma-separated ``tools:`` entries of an agent definition's
    ``---`` frontmatter; ``[]`` when it has no frontmatter or no such line."""
    if not markdown.startswith("---"):
        return []
    end = markdown.find("\n---", 3)
    if end < 0:
        return []
    match = _TOOLS_LINE.search(markdown[3:end])
    if not match:
        return []
    return [t.strip() for t in match.group(1).split(",") if t.strip()]


def _installed_service_ts() -> Path:
    """The installed pi-subagents ``service.ts`` under Pi's agent dir
    (``$PI_CODING_AGENT_DIR``, else ``~/.pi/agent``)."""
    agent_dir = os.environ.get("PI_CODING_AGENT_DIR") or str(Path.home() / ".pi" / "agent")
    return Path(agent_dir) / PI_SUBAGENTS_SERVICE_TS_REL


# ============================================================ detectors ====

class WorktreeDetectorsTest(unittest.TestCase):
    """The two parsers this module's gates stand on bite and spare."""

    def test_symbol_for_keys_reads_every_quote_style_in_order(self):
        src = ('const A = Symbol.for("@x/y:service");\n'
               "const B = Symbol.for( 'k2' );\n"
               "const C = Symbol.for(`k3`); const D = Symbol('not-for');\n")
        self.assertEqual(_symbol_for_keys(src), ["@x/y:service", "k2", "k3"])

    def test_symbol_for_keys_is_empty_without_symbol_for(self):
        self.assertEqual(_symbol_for_keys("const K = '@gotgenes/pi-subagents:service';"), [])

    def test_frontmatter_tools_reads_the_tools_line_only_inside_frontmatter(self):
        md = ("---\nname: x\ntools: read, write, modelb_worktree_enter\n---\n"
              "tools: modelb_worktree_exit\n")
        self.assertEqual(_frontmatter_tools(md), ["read", "write", ENTER])

    def test_frontmatter_tools_is_empty_without_frontmatter(self):
        self.assertEqual(_frontmatter_tools("tools: modelb_worktree_enter\n"), [])


class WorktreeOutsideTargetsTest(unittest.TestCase):
    """The integration's "outside" targets lie outside the hook script's
    scratch allowance wherever the checkout is (CR-MDB-039 VERIFY F8)."""

    def test_under_scratch_bites_on_tmp_and_spares_etc(self):
        self.assertTrue(_under_scratch("/tmp/x/y.txt"))
        self.assertTrue(_under_scratch(os.path.join(tempfile.gettempdir(), "y.txt")))
        self.assertFalse(_under_scratch("/etc/y.txt"))

    def test_no_outside_target_lies_under_tmp_or_tmpdir(self):
        for target in (OUTSIDE_ETC, OUTSIDE_VAR):
            with self.subTest(target=target):
                self.assertTrue(os.path.isabs(target), target)
                self.assertFalse(_under_scratch(target),
                                 f"{target} is under the scratch allowance: the hook would allow it")

    def test_no_outside_target_depends_on_the_checkout_location(self):
        for target in (OUTSIDE_ETC, OUTSIDE_VAR):
            with self.subTest(target=target):
                self.assertFalse(f"{target}/".startswith(f"{REPO_ROOT}/"),
                                 f"{target} is inside the checkout, which may itself be under /tmp")


# ============================================================ fixtures =====

class WorktreeExtensionTestCase(unittest.TestCase):
    """A throwaway git repo with registered worktrees, and the drive fixture."""

    @classmethod
    def setUpClass(cls):
        env = _require_loader_env()
        cls.node_bin = env["node_bin"]
        cls.jiti_mjs = env["jiti_mjs"]
        cls.pi_pkg_root = env["pi_pkg_root"]

    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="modelb-pi-worktree-")).resolve()
        self.addCleanup(self._cleanup)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        (self.repo / "src").mkdir()
        self._ok(_git(self.repo, "init", "-q"))
        (self.repo / "README.md").write_text("fixture\n", encoding="utf-8")
        self._ok(_git(self.repo, "add", "README.md"))
        self._ok(_git(self.repo, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "init"))
        self.wt_foo = self._add_worktree(".worktrees/CR-FOO-001", "feature/CR-FOO-001")
        self.wt_bar = self._add_worktree(".worktrees/CR-BAR-002", "feature/CR-BAR-002")
        # A directory under .worktrees/ that is NOT a registered worktree.
        self.unregistered = self.repo / ".worktrees" / "CR-NOTWT-003"
        self.unregistered.mkdir(parents=True)
        # A registered worktree NOT under a /.worktrees/<cr> segment.
        self.elsewhere = self._add_worktree(str(self.base / "elsewhere"), "elsewhere")

    def _cleanup(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def _ok(self, proc: subprocess.CompletedProcess):
        self.assertEqual(proc.returncode, 0, f"fixture git failed: {proc.args}: {proc.stderr}")

    def _add_worktree(self, where: str, branch: str) -> Path:
        self._ok(_git(self.repo, "worktree", "add", "-q", "-b", branch, where))
        path = (self.repo / where).resolve()
        self.assertTrue(path.is_dir(), f"fixture worktree missing: {path}")
        return path

    # -- the harness ----------------------------------------------------

    def drive(self, steps: list[dict], service_at_load: bool = True,
              session_cwd: Path | None = None, session_start: bool = True) -> dict:
        self.assertTrue(
            EXTENSION.is_file(),
            f"§S1: {rel_to_repo(EXTENSION)} must exist (the worktree extension)",
        )
        env = dict(os.environ)
        env.pop("WF_WORKTREE_ROOT", None)
        env.pop("ALLOW_WRITE_OUTSIDE_WORKTREE", None)
        env.update({"HOME": str(self.base / "home"), "PI_CODING_AGENT_DIR": str(self.base / "pi-agent")})
        preamble = [{"op": "event", "name": "session_start"}] if session_start else []
        scenario = {
            "serviceKey": SERVICE_KEY,
            "serviceAtLoad": service_at_load,
            "sessionCwd": str(session_cwd or self.repo),
            "steps": preamble + steps,
        }
        try:
            result = subprocess.run(
                [self.node_bin, str(HARNESS_MJS), str(EXTENSION), str(self.jiti_mjs), str(self.pi_pkg_root)],
                input=json.dumps(scenario), capture_output=True, text=True,
                timeout=_HARNESS_BUDGET_S, env=env, cwd=str(self.base),
            )
        except subprocess.TimeoutExpired as exc:
            self.fail(f"worktree harness did not exit within {_HARNESS_BUDGET_S}s: {exc}")
        self.assertEqual(result.returncode, 0, f"harness crashed: {result.stderr[-2000:]}")
        try:
            out = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.fail(f"harness emitted no JSON: stdout={result.stdout[-2000:]!r} "
                      f"stderr={result.stderr[-2000:]!r}")
        self.assertIsNone(out["harnessError"], out["harnessError"])
        self.assertIsNone(out["importError"],
                          f"jiti could not load {EXTENSION}: {str(out['importError'])[:1500]}")
        self.assertTrue(out["defaultIsFunction"], "the extension must default-export a factory")
        out["steps"] = out["steps"][len(preamble):]
        for step in out["steps"]:
            self.assertFalse(step.get("missing"), f"a step addressed an unregistered tool/handler: {step}")
            self.assertFalse(step.get("timedOut"), f"a step timed out: {step}")
        return out

    # -- step builders --------------------------------------------------

    @staticmethod
    def enter(path) -> dict:
        return {"op": "tool", "name": ENTER, "params": {"path": str(path)}}

    @staticmethod
    def exit_() -> dict:
        return {"op": "tool", "name": EXIT, "params": {}}

    def prepare(self, description: str, agent_id: str = "agent-1", label: str | None = None,
                base_cwd: Path | None = None) -> dict:
        step = {"op": "prepare", "agentId": agent_id, "description": description,
                "baseCwd": str(base_cwd or self.repo)}
        if label:
            step["label"] = label
        return step

    # -- report helpers -------------------------------------------------

    def assert_prepared_to(self, step: dict, expected: Path, why: str):
        self.assertFalse(step.get("noProvider"), f"{why}: no workspace provider was registered: {step}")
        self.assertIsNone(step.get("threw"), f"{why}: prepare threw: {step}")
        self.assertEqual(step.get("cwd"), str(expected), f"{why}: {step}")
        self.assertEqual(step.get("disposeReturn"), "<undefined>",
                         f"{why}: dispose must return nothing: {step}")

    def assert_prepared_undefined(self, step: dict, why: str):
        self.assertFalse(step.get("noProvider"), f"{why}: no workspace provider was registered: {step}")
        self.assertIsNone(step.get("threw"), f"{why}: prepare threw: {step}")
        self.assertIs(step.get("returnedUndefined"), True,
                      f"{why}: prepare must resolve undefined (the child keeps the parent's cwd): {step}")


# ============================================================ §S1 tools ====

class WorktreeExtensionManifestTest(unittest.TestCase):
    """§S1: the package lists the extension."""

    def test_package_json_pi_extensions_lists_the_worktree_extension(self):
        manifest = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
        listed = (manifest.get("pi") or {}).get("extensions") or []
        self.assertIn("extensions/worktree.ts", listed,
                      f"§S1: pi.extensions must list extensions/worktree.ts; got {listed}")
        self.assertEqual(listed.count("extensions/worktree.ts"), 1, listed)


class WorktreeToolRegistrationTest(WorktreeExtensionTestCase):
    """§S1 AC1: the two tools and their parameters."""

    def test_factory_registers_exactly_the_enter_and_exit_tools(self):
        out = self.drive([])
        self.assertEqual(sorted(out["tools"]), [ENTER, EXIT])

    def test_enter_takes_one_string_path_and_exit_takes_nothing(self):
        out = self.drive([])
        enter = json.loads(out["toolParameters"].get(ENTER) or "null") or {}
        exit_ = json.loads(out["toolParameters"].get(EXIT) or "null") or {}
        self.assertEqual(sorted((enter.get("properties") or {}).keys()), ["path"], enter)
        self.assertEqual((enter["properties"]["path"] or {}).get("type"), "string", enter)
        self.assertIn("path", enter.get("required") or [], f"path is required: {enter}")
        self.assertEqual(exit_.get("type"), "object", exit_)
        self.assertEqual(exit_.get("properties") or {}, {}, f"exit takes no parameters: {exit_}")


class WorktreeEnterExitTest(WorktreeExtensionTestCase):
    """§S1 AC3-AC5: enter sets WF_WORKTREE_ROOT, exit deletes it, refusals
    change nothing, a second enter replaces, exit is idempotent."""

    def test_enter_a_registered_worktree_sets_the_variable_and_names_the_root(self):
        out = self.drive([self.enter(self.wt_foo)])
        step = out["steps"][0]
        self.assertIsNone(step["threw"], step)
        self.assertEqual(step["env"], str(self.wt_foo))
        self.assertIn(str(self.wt_foo), step["text"] or "", "the result names the active root")
        self.assertNotRegex(step["text"] or "", r"(?i)not\b.{0,40}relocat",
                            "with the service present, dispatches ARE relocated")

    def test_enter_resolves_a_relative_path_against_the_session_cwd(self):
        # The harness runs in the temp base dir, not the repo: only ctx.cwd
        # makes the relative path land on the worktree.
        out = self.drive([self.enter(".worktrees/CR-FOO-001")])
        step = out["steps"][0]
        self.assertIsNone(step["threw"], step)
        self.assertEqual(step["env"], str(self.wt_foo))

    def test_exit_deletes_the_variable_and_names_no_root(self):
        out = self.drive([self.enter(self.wt_foo), self.exit_()])
        step = out["steps"][1]
        self.assertIsNone(step["threw"], step)
        self.assertIsNone(step["env"], "exit must delete WF_WORKTREE_ROOT")
        self.assertRegex(step["text"] or "", r"(?i)\bnone\b", "the exit result names no active root")

    def test_exit_is_idempotent(self):
        out = self.drive([self.exit_(), self.enter(self.wt_foo), self.exit_(), self.exit_()])
        for i in (0, 2, 3):
            with self.subTest(step=i):
                step = out["steps"][i]
                self.assertIsNone(step["threw"], f"a repeated exit is a no-op, not an error: {step}")
                self.assertIsNone(step["env"], step)
                self.assertRegex(step["text"] or "", r"(?i)\bnone\b", step)

    def test_second_enter_replaces_the_first(self):
        out = self.drive([self.enter(self.wt_foo), self.enter(self.wt_bar),
                          self.prepare("general housekeeping, no change request named")])
        second, dispatch = out["steps"][1], out["steps"][2]
        self.assertIsNone(second["threw"], second)
        self.assertEqual(second["env"], str(self.wt_bar))
        self.assertIn(str(self.wt_bar), second["text"] or "")
        self.assert_prepared_to(dispatch, self.wt_bar, "the entered root is the replaced one")

    def _refusals(self) -> list[tuple[str, str]]:
        return [
            ("a path that does not exist", str(self.repo / ".worktrees" / "CR-GONE-404")),
            ("a registered worktree not under /.worktrees/<cr>", str(self.elsewhere)),
            ("a directory under .worktrees/ that is not a registered worktree", str(self.unregistered)),
        ]

    def test_enter_refuses_bad_paths_and_changes_nothing_when_none_was_entered(self):
        for why, path in self._refusals():
            with self.subTest(refused=why):
                out = self.drive([self.enter(path), self.prepare("no change request here")])
                step, dispatch = out["steps"]
                self.assertIsNotNone(step["threw"], f"{why}: enter must fail as a tool error: {step}")
                self.assertIsNone(step["env"], f"{why}: WF_WORKTREE_ROOT must stay unset")
                self.assert_prepared_undefined(dispatch, f"{why}: no root may have been entered")

    def test_enter_refusal_keeps_the_previously_entered_root(self):
        for why, path in self._refusals():
            with self.subTest(refused=why):
                out = self.drive([self.enter(self.wt_foo), self.enter(path),
                                  self.prepare("no change request here")])
                first, refused, dispatch = out["steps"]
                self.assertIsNone(first["threw"], first)
                self.assertIsNotNone(refused["threw"], f"{why}: enter must fail: {refused}")
                self.assertEqual(refused["env"], str(self.wt_foo),
                                 f"{why}: a refusal leaves WF_WORKTREE_ROOT unchanged")
                self.assertEqual(refused["registrations"], first["registrations"],
                                 f"{why}: a refusal registers no provider")
                self.assert_prepared_to(dispatch, self.wt_foo, f"{why}: the entered root is unchanged")

    def test_enter_through_a_symlinked_path_records_and_exports_the_real_path(self):
        link_repo = self.base / "repo-link"
        link_repo.symlink_to(self.repo, target_is_directory=True)
        link_wt = self.base / "foo-link"
        link_wt.symlink_to(self.wt_foo, target_is_directory=True)
        for why, path in (("a symlinked repository", link_repo / ".worktrees" / "CR-FOO-001"),
                          ("a symlink to the worktree itself", link_wt)):
            with self.subTest(entered_through=why):
                out = self.drive([self.enter(path), self.prepare("no change request here")])
                step, dispatch = out["steps"]
                self.assertIsNone(step["threw"], f"{why}: {step}")
                self.assertEqual(step["env"], str(self.wt_foo), f"{why}: the real path is exported")
                self.assertIn(str(self.wt_foo), step["text"] or "", f"{why}: the real path is named")
                self.assert_prepared_to(dispatch, self.wt_foo, f"{why}: the real path is recorded")

    def test_enter_says_the_boundary_governs_file_tool_writes(self):
        out = self.drive([self.enter(self.wt_foo)])
        step = out["steps"][0]
        self.assertIsNone(step["threw"], step)
        self.assertRegex(step["text"] or "", r"(?i)\bfile-tool writes\b",
                         "the hook governs file-tool writes, not a shell command's writes")
        self.assertNotRegex(step["text"] or "", r"(?<!File-tool )(?<!file-tool )\bWrites outside it are blocked",
                            "no unqualified claim that every write outside is blocked")

    def test_enter_without_the_service_sets_the_variable_and_says_no_relocation(self):
        out = self.drive([self.enter(self.wt_foo)], service_at_load=False)
        step = out["steps"][0]
        self.assertIsNone(step["threw"], step)
        self.assertEqual(step["env"], str(self.wt_foo))
        self.assertIn(str(self.wt_foo), step["text"] or "")
        self.assertRegex(step["text"] or "", r"(?i)not\b.{0,40}relocat",
                         "the result must say dispatched agents will not be relocated")
        self.assertEqual(out["providerRegistrations"], 0)


# ============================================================ §S1 routing ==

class WorktreeRoutingTest(WorktreeExtensionTestCase):
    """§S1 AC2: one workspace provider; prepare follows the routing steps."""

    def test_exactly_one_provider_is_registered_across_events_tools_and_dispatches(self):
        out = self.drive([
            self.prepare("CR-FOO-001-C1-RED: write tests", "a1"),
            self.enter(self.wt_foo), self.exit_(), self.enter(self.wt_bar),
            {"op": "event", "name": "session_start"},
            self.prepare("CR-BAR-002-C1-GREEN: implement", "a2"),
        ])
        self.assertEqual(out["providerRegistrations"], 1)
        self.assertEqual(out["providerUnregistrations"], 0)
        self.assertEqual(out["steps"][0]["registrations"], 1,
                         "the provider is in place by the first dispatch, with no tool call")

    def test_service_published_after_load_is_still_found(self):
        out = self.drive([{"op": "installService"}, {"op": "event", "name": "session_start"},
                          self.prepare("CR-FOO-001-C1-RED: write tests")],
                         service_at_load=False, session_start=False)
        self.assertEqual(out["providerRegistrations"], 1)
        self.assert_prepared_to(out["steps"][2], self.wt_foo, "load order does not matter")

    def test_a_dispatch_naming_a_cr_with_a_worktree_goes_to_that_worktree(self):
        out = self.drive([self.prepare("CR-FOO-001-C1-RED: write the failing tests")])
        self.assert_prepared_to(out["steps"][0], self.wt_foo, "CR-FOO-001 has .worktrees/CR-FOO-001")

    def test_the_repository_is_the_one_containing_base_cwd(self):
        out = self.drive([self.prepare("CR-BAR-002 verify", base_cwd=self.repo / "src")])
        self.assert_prepared_to(out["steps"][0], self.wt_bar, "baseCwd is a subdirectory of the repo")

    def test_two_dispatches_naming_two_crs_go_to_their_own_worktrees(self):
        out = self.drive([
            self.prepare("CR-FOO-001-C1-RED: tests", "a1"),
            self.prepare("CR-BAR-002-C2-GREEN: code", "a2"),
            self.prepare("CR-FOO-001-C1-VERIFY: check", "a3"),
        ])
        self.assert_prepared_to(out["steps"][0], self.wt_foo, "first dispatch, CR-FOO-001")
        self.assert_prepared_to(out["steps"][1], self.wt_bar, "second dispatch, CR-BAR-002")
        self.assert_prepared_to(out["steps"][2], self.wt_foo, "no state carried between dispatches")

    def test_the_first_cr_id_in_the_description_wins(self):
        out = self.drive([self.prepare("CR-BAR-002 follow-up to CR-FOO-001")])
        self.assert_prepared_to(out["steps"][0], self.wt_bar, "first match of CR-[A-Z][A-Z0-9]*-[0-9]+")

    def test_only_a_cr_id_opening_the_description_routes(self):
        out = self.drive([
            self.prepare("Review CR-BAR-002 interplay for CR-FOO-001", "a1"),
            self.prepare("CR-FOO-001 C1 RED", "a2"),
            self.enter(self.wt_foo),
            self.prepare("Review CR-BAR-002 interplay for CR-FOO-001", "a3"),
        ])
        s = out["steps"]
        self.assert_prepared_undefined(s[0], "a CR id not opening the description does not route")
        self.assert_prepared_to(s[1], self.wt_foo, "the agent-id convention `CR-FOO-001 C1 RED` routes")
        self.assert_prepared_to(s[3], self.wt_foo,
                                "entered: a CR named mid-description neither routes nor is refused")

    def test_records_are_read_from_the_service_that_accepted_the_provider(self):
        # Each child session loads pi-subagents: its own service republishes the
        # global entry (holding none of the parent's records), then deletes it.
        out = self.drive([
            self.prepare("CR-FOO-001-C1-RED: first dispatch", "a1"),
            {"op": "replaceService"},
            self.prepare("CR-BAR-002-C1-RED: after a child republished the service", "a2"),
            self.enter(self.wt_bar),
            {"op": "deleteService"},
            self.prepare("CR-BAR-002-C2-GREEN: after a child deleted the service", "a3"),
            self.exit_(),
            self.prepare("CR-FOO-001-C2-GREEN: still no global service", "a4"),
        ])
        s = out["steps"]
        self.assert_prepared_to(s[0], self.wt_foo, "before any child")
        self.assert_prepared_to(s[2], self.wt_bar, "global entry replaced by another instance")
        self.assert_prepared_to(s[5], self.wt_bar, "global entry deleted, root entered")
        self.assert_prepared_to(s[7], self.wt_foo, "global entry deleted, nothing entered")
        self.assertEqual(out["providerRegistrations"], 1)
        self.assertEqual(out["otherRegistrations"], 0,
                         "the provider is never re-registered on a child's service")

    def test_entered_a_dispatch_whose_cr_has_another_worktree_is_refused_naming_both(self):
        out = self.drive([
            self.enter(self.wt_foo),
            self.prepare("CR-BAR-002-C1-RED: a different CR's worktree", "a1"),
            self.prepare("CR-FOO-001-C1-RED: the entered CR", "a2"),
        ])
        other, same = out["steps"][1], out["steps"][2]
        self.assertFalse(other.get("noProvider"), other)
        self.assertIsNotNone(other.get("threw"),
                             f"entered CR-FOO-001: a CR-BAR-002 child would be confined to the wrong "
                             f"worktree: {other}")
        self.assertIn(str(self.wt_foo), other["threw"], "the error names the entered worktree")
        self.assertIn(str(self.wt_bar), other["threw"], "the error names the CR's worktree")
        self.assertIsNone(other.get("cwd"), other)
        self.assert_prepared_to(same, self.wt_foo, "the entered CR is routed normally")

    def test_no_cr_or_no_worktree_without_an_entered_root_keeps_the_parent_cwd(self):
        out = self.drive([
            self.prepare("tidy the README", "a1"),
            self.prepare("CR-BAZ-009-C1-RED: no worktree exists for this CR", "a2"),
            self.prepare("CR-NOTWT-003: directory exists but is not a registered worktree", "a3"),
        ])
        self.assert_prepared_undefined(out["steps"][0], "no CR named")
        self.assert_prepared_undefined(out["steps"][1], "a CR with no worktree")
        self.assert_prepared_undefined(out["steps"][2], "an unregistered .worktrees/<cr> directory")

    def test_no_cr_or_no_worktree_with_an_entered_root_goes_to_the_entered_root(self):
        out = self.drive([
            self.enter(self.wt_foo),
            self.prepare("tidy the README", "a1"),
            self.prepare("CR-BAZ-009-C1-RED: no worktree exists for this CR", "a2"),
            self.prepare("CR-FOO-001-C1-RED: the entered CR's own worktree", "a3"),
            self.exit_(),
            self.prepare("tidy the README again", "a4"),
        ])
        self.assert_prepared_to(out["steps"][1], self.wt_foo, "no CR -> entered root")
        self.assert_prepared_to(out["steps"][2], self.wt_foo, "CR without worktree -> entered root")
        self.assert_prepared_to(out["steps"][3], self.wt_foo, "the entered CR -> its own worktree")
        self.assert_prepared_undefined(out["steps"][5], "after exit there is no entered root")

    def test_prepare_throws_when_the_entered_root_has_been_deleted(self):
        out = self.drive([
            self.enter(self.wt_foo),
            {"op": "rmrf", "path": str(self.wt_foo)},
            self.prepare("tidy the README"),
        ])
        step = out["steps"][2]
        self.assertFalse(step.get("noProvider"), step)
        self.assertIsNotNone(step.get("threw"),
                             f"no child may silently land in the main tree: {step}")
        self.assertIn(str(self.wt_foo), step["threw"], "the error names the missing root")
        self.assertIsNone(step.get("cwd"), step)


# ============================================================ integration ==

class WorktreeHookIntegrationTest(WorktreeExtensionTestCase):
    """§S1 integration AC: the REAL block-write-outside-worktree script,
    through the compiled Pi hook, in the process the tool changed."""

    def setUp(self):
        super().setUp()
        from modelb_axi.hooks import compile_wiring

        target = self.base / "hook-target"
        target.mkdir()
        report = compile_wiring(
            schema_instances=[{
                "event": "pre-tool-use", "matcher": "write|edit",
                "command": "block-write-outside-worktree", "tier": "core",
                "timeout": 10, "fail_direction": "closed",
            }],
            harnesses=["pi"], target=target, scripts_root=REAL_SCRIPTS_ROOT,
        )
        self.assertNotIn("refusals", report["pi"])
        ts_files = sorted((target / ".pi" / "extensions").glob("*.ts"))
        self.assertEqual(len(ts_files), 1, ts_files)
        self.guard = str(ts_files[0])

    def write(self, path: str, cwd: str | None = None, cwd_from: str | None = None) -> dict:
        step = {"op": "hook", "extPath": self.guard,
                "event": {"type": "tool_call", "toolCallId": "w-" + path, "toolName": "write",
                          "input": {"path": path, "content": "x"}},
                "ctx": {"cwd": cwd} if cwd else {}}
        if cwd_from:
            step["cwdFrom"] = cwd_from
        return step

    def assert_blocked(self, step: dict, why: str):
        self.assertIsNone(step.get("threw"), f"{why}: hook threw: {step}")
        result = step.get("result")
        self.assertIsInstance(result, dict, f"{why}: expected a block result: {step}")
        assert isinstance(result, dict)
        self.assertIs(result.get("block"), True, f"{why}: must block: {step}")
        self.assertIn("worktree", (result.get("reason") or "").lower(), step)

    def assert_allowed(self, step: dict, why: str):
        self.assertIsNone(step.get("threw"), f"{why}: hook threw: {step}")
        self.assertIsNot((step.get("result") or {}).get("block"), True, f"{why}: must allow: {step}")

    def test_the_variable_set_by_enter_blocks_the_orchestrators_writes_outside(self):
        main = str(self.repo)
        out = self.drive([
            self.write(OUTSIDE_ETC, cwd=main),
            self.enter(self.wt_foo),
            self.write(OUTSIDE_ETC, cwd=main),
            self.write(OUTSIDE_VAR, cwd=main),
            self.write(str(self.wt_foo / "src" / "new.py"), cwd=main),
            self.exit_(),
            self.write(OUTSIDE_ETC, cwd=main),
        ])
        s = out["steps"]
        self.assert_allowed(s[0], "before enter the main-tree session has no worktree context")
        self.assertEqual(s[1]["env"], str(self.wt_foo))
        self.assert_blocked(s[2], "entered: a write to /etc")
        self.assert_blocked(s[3], "entered: a write to /var")
        self.assert_allowed(s[4], "entered: a write inside the entered worktree")
        self.assert_allowed(s[6], "after exit the boundary is lifted")

    def test_the_cwd_prepare_returned_blocks_a_childs_write_outside(self):
        out = self.drive([
            self.prepare("CR-FOO-001-C1-GREEN: implement", label="child"),
            self.write(OUTSIDE_ETC, cwd_from="child"),
            self.write(OUTSIDE_VAR, cwd_from="child"),
            self.write("src/impl.py", cwd_from="child"),
        ])
        s = out["steps"]
        self.assert_prepared_to(s[0], self.wt_foo, "the child is routed to its CR's worktree")
        self.assertIsNone(s[1]["env"], "no enter: the boundary comes from the child's cwd alone")
        self.assertEqual(s[1]["ctxCwd"], str(self.wt_foo))
        self.assert_blocked(s[1], "a child rooted in the worktree writing to /etc")
        self.assert_blocked(s[2], "a child rooted in the worktree writing to /var")
        self.assert_allowed(s[3], "a relative write resolves inside the child's worktree")

    def test_entered_a_dispatch_routed_to_another_crs_worktree_is_refused(self):
        # Why (F1): the hook prefers the process-wide WF_WORKTREE_ROOT over the
        # child's cwd, so a child rooted in CR-BAR-002's worktree while CR-FOO-001
        # is entered is judged against FOO's root -- prepare refuses it instead.
        # (The fixture is under /tmp, the script's scratch allowance, so the why
        # is shown by the root the block names, not by a write into BAR.)
        out = self.drive([
            self.enter(self.wt_foo),
            self.write(OUTSIDE_ETC, cwd=str(self.wt_bar)),
            self.prepare("CR-BAR-002-C1-GREEN: implement", label="child"),
        ])
        s = out["steps"]
        self.assert_blocked(s[1], "entered FOO: a BAR-rooted writer")
        reason = s[1]["result"].get("reason") or ""
        self.assertIn(f"worktree root: {self.wt_foo}", reason,
                      "the hook judges a BAR-rooted writer against the entered FOO root")
        self.assertFalse(s[2].get("noProvider"), s[2])
        self.assertIsNotNone(s[2].get("threw"), f"a BAR dispatch while FOO is entered must fail: {s[2]}")
        self.assertIn(str(self.wt_foo), s[2]["threw"], "the error names the entered worktree")
        self.assertIn(str(self.wt_bar), s[2]["threw"], "the error names the CR's worktree")
        self.assertIsNone(s[2].get("cwd"), s[2])


# ============================================================ contract =====

class WorktreeServiceKeyContractTest(unittest.TestCase):
    """§S1 AC: the extension's service key equals the installed pi-subagents'."""

    def test_extension_service_key_equals_the_installed_pi_subagents_key(self):
        service_ts = _installed_service_ts()
        if not service_ts.is_file():
            self.skipTest(f"pi-subagents is not installed: {service_ts} is absent")
        installed = _symbol_for_keys(service_ts.read_text(encoding="utf-8"))
        self.assertEqual(installed, [SERVICE_KEY],
                         f"{service_ts} declares one Symbol.for key, the one the fake service uses")
        self.assertTrue(EXTENSION.is_file(), f"§S1: {rel_to_repo(EXTENSION)} must exist")
        keys = _symbol_for_keys(EXTENSION.read_text(encoding="utf-8"))
        self.assertEqual(keys, installed,
                         f"the extension must look the service up under exactly {installed}; got {keys}")


# ============================================================ §S3 ==========

class WatcherCapabilityWorktreeTest(unittest.TestCase):
    """§S3: the watcher capability names worktree isolation and its tools."""

    def _row(self) -> dict:
        from modelb_axi.requirements import REQUIREMENTS
        rows = [r for r in REQUIREMENTS if r.get("id") == "watcher"]
        self.assertEqual(len(rows), 1, "exactly one watcher row")
        return rows[0]

    def test_watcher_asset_families_name_worktree_isolation(self):
        families = list(self._row()["asset_families"])
        hits = [f for f in families if re.search(r"(?i)worktree isolation", f)]
        self.assertEqual(len(hits), 1, f"one asset family names worktree isolation: {families}")

    def test_watcher_tools_include_both_worktree_tools(self):
        tools = list(self._row()["tools"])
        for name in (ENTER, EXIT):
            self.assertIn(name, tools, f"§S3: the watcher tools must list {name}")
        self.assertEqual(len(tools), len(set(tools)), tools)


# ============================================================ agents =======

class GeneratedAgentsOmitWorktreeToolsTest(unittest.TestCase):
    """§S1: only the orchestrator uses the tools; no generated agent lists them."""

    def test_no_generated_agent_lists_either_worktree_tool(self):
        agents = sorted(AGENTS_DIR.glob("*.md"))
        self.assertGreaterEqual(len(agents), 16, "the generated agent definitions are scanned")
        offenders = []
        for md in agents:
            tools = _frontmatter_tools(md.read_text(encoding="utf-8"))
            self.assertTrue(tools, f"{md.name} has a tools: line to scan")
            offenders += [f"{md.name}: {t}" for t in tools if t in (ENTER, EXIT)]
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
