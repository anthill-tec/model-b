"""``scripts/worktree-flow.py``: ``sync`` merges develop in, ``finish`` catches up the same way,
``status`` after a merge, and no rebase anywhere (CR-MDB-081 §S1–§S3 — AC1, AC2, AC3, AC4).

- ``SyncMergesDevelopInTest`` — AC1 / §S1: ``sync --cr <cr>`` brings a behind branch level by
  ``git merge --no-edit develop`` in its worktree: a merge commit on a branch with commits of its
  own (every prior sha kept), a fast-forward on a branch with none, a conflicting merge aborted
  with the branch, worktree and index as they were, and a ``--dry-run`` that prints the merge and
  changes nothing.
- ``FinishCatchUpTest`` — AC2 / §S2: ``finish`` on a behind branch catches up by that merge
  before its ``--no-ff`` merge into develop, so every branch commit keeps its sha; its
  ``--dry-run`` plan names the catch-up merge; a conflicting catch-up leaves develop, the branch
  and the worktree as they were, with the merge lock released.
- ``NoRebaseGitArgumentTest`` — AC3: no string literal passed as a git argument in
  ``scripts/worktree-flow.py`` is ``rebase``.
- ``StatusAfterAMergeTest`` — AC4 / §S3: the phase and ``commits_ahead`` come from the branch's
  own commits, merge commits excluded; ``ahead`` stays git's count; a behind branch's ``state``
  is ``SYNC NEEDED (develop moved <n>)`` and no ``state`` contains ``REBASE``.

§S8 / AC10, the paths the tool already had:

- ``ProjectResolutionTest`` — ``--project-dir``, ``$WORKTREE_FLOW_PROJECT_DIR``, the current
  directory's repository (its main worktree, even from inside a CR worktree), and not a
  repository.
- ``StartRefusalTest`` / ``StartTest`` — each ``start`` refusal; the local-develop-behind-upstream
  note; the ``.env`` copy; the track label from ``--track`` and ``$WF_TRACK``; ``--dry-run``.
- ``StatusTest`` — the merge lock, detached and dirty worktrees, a dirty integration tree, the
  track label and the phase tokens.
- ``SyncRefusalAndLevelTest`` — a level branch, clean and dirty; a behind branch with a dirty
  worktree; a missing and a detached worktree.
- ``FinishRefusalTest`` / ``FinishTest`` — each ``finish`` refusal, the lock held by another
  finish, ``--no-auto-sync`` naming ``sync --cr <cr>``; a removal that needs ``--force``, a
  partial removal, a failed branch delete, ``--push`` succeeding and failing, ``--dry-run``.
  Every git failure is real git's: a submodule store refuses a plain removal, a locked worktree
  refuses a single ``--force``, a branch checked out elsewhere refuses ``branch -d`` -- none
  depends on file permissions, so a root user sees the same.

§S4–§S6, the rules, ``abort`` and the scheduler-note board (AC5, AC6, AC7):

- ``WorktreeFlowDescribesNoRebaseTest`` — AC5: no help text, message or docstring of
  ``scripts/worktree-flow.py`` describes the tool as rebasing (a sentence saying it never
  rebases -- ``never``/``not``/``no``/``nor``/``without`` shortly before ``rebas`` -- is spared).
- ``SyncRuleSurfacesTest`` — AC5 / §S4: in ``orchestration-common.md``'s § Worktree isolation
  (basics), ``orchestration-track.md``, the ``shutdown`` skill's Step 2A and
  ``rust-orchestration.md``, a sentence names ``worktree-flow.py sync --cr <cr>`` together with
  ``finish``; no sentence forbids ``sync``, merges develop into a worktree branch by hand, or
  describes ``worktree-flow`` as rebasing.
- ``AbortBoardStepTest`` — AC6 / §S5: ``abort``'s output, refusal and help claim no board write;
  a dry run, a removal and a no-worktree run end with the orchestrator's ``cr-void`` step, a
  ``--superseded`` run with its ``cr-supersede`` step; ``--delete-branch`` with no worktree
  deletes the branch.
- ``AbortPathTest`` — §S8 / AC10: ``abort``'s refusals (no ``--cr``, a dirty worktree without
  ``--force``), ``--force``, ``--delete-branch`` with a worktree and the branch kept without it,
  no worktree and its dry run, ``--release-lock`` real and dry, ``--dry-run`` with a worktree,
  and ``--delete-branch`` with no worktree refused when more than one branch is the CR's.
- ``NoSchedulerNoteBoardTest`` — AC7 / §S6: the script names neither ``WF_REQUEST_DIR`` nor
  ``reschedule-request``; ``status`` names no note from ``$WF_REQUEST_DIR`` or the project's
  ``.env``; ``orchestration-track.md`` names no ``reschedule-request``.

Every run is a subprocess of the test interpreter under ``tests/_helpers.py``'s ``run_tool``
(§S9): real git repositories in temp directories, the tools' own variables cleared, a private
``TMPDIR`` set in the test process, and on ``PATH`` a logging ``git`` stand-in that records each
call's argv and working directory and then runs the host's git -- so a test asserts the merge a
run made, and that no ``rebase`` ran.

Stdlib only.
"""

import ast
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from tests._helpers import (
    REPO_ROOT,
    TOOL_SCRIPTS_DIR,
    decode_envelope,
    git_commit_all,
    git_repo,
    md_section,
    read_text,
    repo_git,
    run_tool,
    tool_bin_dir,
    use_private_tmpdir,
    write_files,
)
from tests.test_bootstrap_shutdown_registry import sentences

WORKTREE_FLOW = "worktree-flow.py"

#: The CR every fixture works on, its worktree directory name and its feature branch.
CR = "CR-TST-001"
BRANCH = f"feature/{CR}"
DEVELOP = "develop"

#: The merge lock ``finish`` takes in the shared git directory.
LOCK_NAME = "worktree-flow-merge.lock"

#: The file both develop and the branch change in a conflict fixture.
SHARED = "shared.txt"


def _logging_git(real_git: str, log: Path) -> str:
    """A ``git`` stand-in appending ``{argv, cwd}`` to ``log`` as one JSON line, then replacing
    itself with the host's ``real_git`` -- the run behaves as with real git, and the test reads
    every git call the tool made."""
    return (
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        f"with open({str(log)!r}, 'a', encoding='utf-8') as fh:\n"
        "    fh.write(json.dumps({'argv': sys.argv[1:], 'cwd': os.getcwd()}) + '\\n')\n"
        f"os.execv({real_git!r}, [{real_git!r}, *sys.argv[1:]])\n"
    )


class _WorktreeFlowCase(unittest.TestCase):
    """A temp work area holding a git repository on ``develop`` (``.worktrees/`` ignored), a
    working directory outside it, a private ``TMPDIR`` and a ``PATH`` whose ``git`` logs every
    call -- all removed afterwards."""

    def setUp(self):
        self.work = Path(os.path.realpath(tempfile.mkdtemp(prefix="mdb-worktree-flow-")))
        self.addCleanup(shutil.rmtree, self.work, True)
        use_private_tmpdir(self, self.work)
        self.git_log = self.work / "git-calls.jsonl"
        host_git = shutil.which("git")
        if host_git is None:
            raise RuntimeError("fixture: git is not on the host PATH")
        real_git = str(Path(host_git).resolve())
        self.bin_dir = tool_bin_dir(self.work / "bin",
                                    {"git": _logging_git(real_git, self.git_log)})
        self.cwd = self.work / "cwd"
        self.cwd.mkdir()
        self.repo = git_repo(self.work / "proj", {
            ".gitignore": ".worktrees/\n",
            "README.md": "fixture\n",
            SHARED: "base\n",
        }, branch=DEVELOP, message="chore: initial")
        self.wt = self.repo / ".worktrees" / CR

    # ------------------------------------------------------------------ fixture steps ----

    def _add_worktree(self):
        """The CR's worktree at ``.worktrees/<cr>`` on a new ``feature/<cr>`` off develop."""
        repo_git(self.repo, "worktree", "add", "-q", "-b", BRANCH, self.wt, DEVELOP)

    def _branch_commit(self, rel: str, text: str, message: str) -> str:
        write_files(self.wt, {rel: text})
        return git_commit_all(self.wt, message)

    def _develop_commit(self, rel: str, text: str, message: str) -> str:
        write_files(self.repo, {rel: text})
        return git_commit_all(self.repo, message)

    # ------------------------------------------------------------------ tool runs ----

    def _wf(self, *args, cwd=None, env=None):
        """Run the tool on the fixture repository (``--project-dir``), in ``cwd`` (default: the
        working directory outside it), with ``env`` the tools' own variables for this run."""
        return self._run(*args, "--project-dir", self.repo, cwd=cwd, env=env)

    def _run(self, *args, cwd=None, env=None):
        """Run the tool with exactly ``args`` -- no ``--project-dir`` added -- in ``cwd``."""
        return run_tool(WORKTREE_FLOW, *args, bin_dir=self.bin_dir,
                        cwd=self.cwd if cwd is None else cwd, env=env)

    def _git_calls(self) -> list:
        """Every git call the tool made: ``[{"argv": [...], "cwd": "..."}, ...]``, a leading
        ``-C <dir>`` folded into ``cwd`` so a call made in a tree reads the same either way."""
        if not self.git_log.is_file():
            return []
        calls = []
        for line in self.git_log.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            call = json.loads(line)
            argv, cwd = call["argv"], call["cwd"]
            while argv[:1] == ["-C"] and len(argv) > 1:
                cwd, argv = os.path.join(cwd, argv[1]), argv[2:]
            calls.append({"argv": argv, "cwd": cwd})
        return calls

    def _printed_rebase_commands(self, text: str) -> list:
        """The lines of ``text`` printing a git command that rebases."""
        return [line for line in text.splitlines() if "git " in line and " rebase" in line]

    def _calls_in(self, tree: Path) -> list:
        """The argv of every git call the tool made with ``tree`` as its working directory."""
        real = os.path.realpath(tree)
        return [c["argv"] for c in self._git_calls() if os.path.realpath(c["cwd"]) == real]

    def _rebase_calls(self) -> list:
        return [c for c in self._git_calls() if "rebase" in c["argv"]]

    # ------------------------------------------------------------------ git reads ----

    def _head(self, ref: str) -> str:
        return repo_git(self.repo, "rev-parse", ref)

    def _parents(self, ref: str) -> list:
        return repo_git(self.repo, "rev-list", "--parents", "-n", "1", ref).split()[1:]

    def _is_ancestor(self, commit: str, ref: str) -> bool:
        try:
            repo_git(self.repo, "merge-base", "--is-ancestor", commit, ref)
        except AssertionError:
            return False
        return True

    def _behind(self) -> int:
        return int(repo_git(self.repo, "rev-list", "--count", f"{BRANCH}..{DEVELOP}"))

    def _merge_in_progress(self, tree: Path) -> bool:
        git_dir = repo_git(tree, "rev-parse", "--path-format=absolute", "--git-dir")
        return (Path(git_dir) / "MERGE_HEAD").exists()

    def _rebase_in_progress(self, tree: Path) -> bool:
        git_dir = Path(repo_git(tree, "rev-parse", "--path-format=absolute", "--git-dir"))
        return (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists()

    def _lock(self) -> Path:
        return self.repo / ".git" / LOCK_NAME

    def _output(self, result) -> str:
        return f"rc={result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"


class SyncMergesDevelopInTest(_WorktreeFlowCase):
    """AC1 / §S1: ``sync --cr <cr>`` merges develop into the CR's worktree branch and never
    rebases."""

    def test_sync_on_a_behind_branch_with_own_commits_makes_a_merge_commit_keeping_every_sha(self):
        self._add_worktree()
        first = self._branch_commit("a.txt", "a\n", "test(core): RED — first")
        second = self._branch_commit("b.txt", "b\n", "feat(core): GREEN — second")
        moved = self._develop_commit("d.txt", "d\n", "feat(other): develop moved")

        result = self._wf("sync", "--cr", CR)

        self.assertEqual(result.returncode, 0, self._output(result))
        head = self._head(BRANCH)
        self.assertEqual(self._parents(head), [second, moved],
                         "the branch's newest commit must be a merge commit of its old head and "
                         "develop's head")
        self.assertTrue(self._is_ancestor(moved, BRANCH), "the branch must contain develop's head")
        for sha in (first, second):
            self.assertTrue(self._is_ancestor(sha, BRANCH),
                            f"{sha} must keep its sha on the branch (no rewrite)")
        self.assertEqual(self._behind(), 0)
        self.assertIn(["merge", "--no-edit", DEVELOP], self._calls_in(self.wt))
        self.assertEqual(self._rebase_calls(), [])

    def test_sync_on_a_branch_with_no_own_commits_fast_forwards_it_by_merge(self):
        self._add_worktree()
        moved = self._develop_commit("d.txt", "d\n", "feat(other): develop moved")

        result = self._wf("sync", "--cr", CR)

        self.assertEqual(result.returncode, 0, self._output(result))
        self.assertEqual(self._head(BRANCH), moved,
                         "the branch must be fast-forwarded to develop, no merge commit made")
        self.assertIn(["merge", "--no-edit", DEVELOP], self._calls_in(self.wt))
        self.assertEqual(self._rebase_calls(), [])

    def test_sync_with_a_conflicting_merge_aborts_it_names_the_path_and_leaves_the_branch(self):
        self._add_worktree()
        own = self._branch_commit(SHARED, "branch side\n", "feat(core): GREEN — branch edit")
        self._develop_commit(SHARED, "develop side\n", "feat(other): develop edit")

        result = self._wf("sync", "--cr", CR)

        self.assertNotEqual(result.returncode, 0, self._output(result))
        self.assertIn(SHARED, result.stderr, "the conflicting path must be named on stderr")
        self.assertEqual(self._head(BRANCH), own, "the branch head must be unchanged")
        self.assertEqual(repo_git(self.wt, "status", "--porcelain"), "")
        self.assertFalse(self._merge_in_progress(self.wt), "no merge may be left in progress")
        self.assertFalse(self._rebase_in_progress(self.wt), "no rebase may be left in progress")
        calls = self._calls_in(self.wt)
        self.assertIn(["merge", "--no-edit", DEVELOP], calls)
        self.assertIn(["merge", "--abort"], calls)
        self.assertLess(calls.index(["merge", "--no-edit", DEVELOP]), calls.index(["merge", "--abort"]))
        self.assertEqual(self._rebase_calls(), [])

    def test_sync_dry_run_prints_the_merge_and_changes_nothing(self):
        self._add_worktree()
        own = self._branch_commit("a.txt", "a\n", "feat(core): GREEN — own")
        moved = self._develop_commit("d.txt", "d\n", "feat(other): develop moved")

        result = self._wf("sync", "--cr", CR, "--dry-run")

        self.assertEqual(result.returncode, 0, self._output(result))
        self.assertIn(f"git -C {self.wt} merge --no-edit {DEVELOP}", result.stdout,
                      "the dry run must print the merge it would run")
        self.assertEqual(self._printed_rebase_commands(result.stdout + result.stderr), [])
        self.assertEqual(self._head(BRANCH), own)
        self.assertEqual(self._head(DEVELOP), moved)
        mutating = [argv for argv in (c["argv"] for c in self._git_calls())
                    if argv and argv[0] in ("merge", "rebase", "commit", "reset", "checkout")]
        self.assertEqual(mutating, [], "a dry run runs no mutating git command")


class FinishCatchUpTest(_WorktreeFlowCase):
    """AC2 / §S2: ``finish`` brings a behind branch level by the same merge, inside the lock,
    before its ``--no-ff`` merge into develop; it never rebases."""

    def setUp(self):
        super().setUp()
        self._add_worktree()

    def test_finish_on_a_behind_branch_merges_it_into_develop_keeping_every_branch_sha(self):
        first = self._branch_commit("a.txt", "a\n", "test(core): RED — first")
        second = self._branch_commit("b.txt", "b\n", "feat(core): GREEN — second")
        moved = self._develop_commit("d.txt", "d\n", "feat(other): develop moved")

        result = self._wf("finish", "--cr", CR)

        self.assertEqual(result.returncode, 0, self._output(result))
        for sha in (first, second, moved):
            self.assertTrue(self._is_ancestor(sha, DEVELOP),
                            f"{sha} must be on develop with its sha unchanged")
        self.assertIn(["merge", "--no-edit", DEVELOP], self._calls_in(self.wt),
                      "the catch-up is a merge of develop in the CR's worktree")
        self.assertEqual(self._rebase_calls(), [])

    def test_finish_dry_run_on_a_behind_branch_prints_the_catch_up_merge_and_changes_nothing(self):
        own = self._branch_commit("a.txt", "a\n", "feat(core): GREEN — own")
        moved = self._develop_commit("d.txt", "d\n", "feat(other): develop moved")

        result = self._wf("finish", "--cr", CR, "--dry-run")

        self.assertEqual(result.returncode, 0, self._output(result))
        printed = result.stdout + result.stderr
        self.assertIn(f"git -C {self.wt} merge --no-edit {DEVELOP}", printed,
                      "the catch-up merge must be part of the printed plan")
        self.assertEqual(self._printed_rebase_commands(printed), [], "the plan names no rebase")
        self.assertEqual(self._head(BRANCH), own)
        self.assertEqual(self._head(DEVELOP), moved)
        self.assertTrue(self.wt.is_dir(), "the worktree must still exist")
        self.assertFalse(self._lock().exists())
        mutating = [argv for argv in (c["argv"] for c in self._git_calls())
                    if argv and argv[0] in ("merge", "rebase", "commit", "branch", "push")
                    or argv[:2] == ["worktree", "remove"]]
        self.assertEqual(mutating, [], "a dry run runs no mutating git command")

    def test_finish_with_a_conflicting_catch_up_merges_nothing_and_releases_the_lock(self):
        own = self._branch_commit(SHARED, "branch side\n", "feat(core): GREEN — branch edit")
        moved = self._develop_commit(SHARED, "develop side\n", "feat(other): develop edit")

        result = self._wf("finish", "--cr", CR)

        self.assertNotEqual(result.returncode, 0, self._output(result))
        self.assertEqual(self._head(DEVELOP), moved, "develop's head must be unchanged")
        self.assertEqual(self._head(BRANCH), own, "the branch head must be unchanged")
        self.assertEqual(repo_git(self.wt, "status", "--porcelain"), "")
        self.assertFalse(self._merge_in_progress(self.wt), "no merge may be left in progress")
        self.assertFalse(self._rebase_in_progress(self.wt), "no rebase may be left in progress")
        self.assertFalse(self._lock().exists(), "the merge lock must be released")
        calls = self._calls_in(self.wt)
        self.assertIn(["merge", "--no-edit", DEVELOP], calls)
        self.assertIn(["merge", "--abort"], calls)
        self.assertEqual([argv for argv in self._calls_in(self.repo) if argv[:1] == ["merge"]], [],
                         "nothing is merged into develop")
        self.assertEqual(self._rebase_calls(), [])


#: The helpers in ``worktree-flow.py`` whose first argument is a git argv list.
GIT_CALLERS = frozenset({"_git", "_git_out"})


def _git_argument_literals(source: str) -> list:
    """Every string literal passed as a git argument in ``source``: the string constants of the
    argv list given to ``_git`` / ``_git_out``, and of any list literal whose first element is
    the string ``git``."""
    found = []
    for node in ast.walk(ast.parse(source)):
        argv = None
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in GIT_CALLERS and node.args
                and isinstance(node.args[0], ast.List)):
            argv = node.args[0].elts
        elif (isinstance(node, ast.List) and node.elts and isinstance(node.elts[0], ast.Constant)
              and node.elts[0].value == "git"):
            argv = node.elts[1:]
        for elt in argv or ():
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                found.append(elt.value)
    return found


class NoRebaseGitArgumentTest(unittest.TestCase):
    """AC3: ``worktree-flow.py`` passes no ``rebase`` to git."""

    def test_no_git_argument_literal_in_worktree_flow_is_rebase(self):
        # The scan bites on each git-caller form, and spares a string that is no git argument.
        bite = ("_git(['rebase', develop], wt)\n"
                "_git_out(['merge', '--no-edit', develop], wt)\n"
                "subprocess.run(['git', 'rebase', '--abort'])\n"
                "print('rebase')\n")
        self.assertEqual(_git_argument_literals(bite),
                         ["rebase", "merge", "--no-edit", "rebase", "--abort"])
        literals = _git_argument_literals(
            (TOOL_SCRIPTS_DIR / WORKTREE_FLOW).read_text(encoding="utf-8"))
        self.assertIn("merge", literals, "the scan must see the script's git arguments")
        self.assertEqual([lit for lit in literals if lit == "rebase"], [])


class StatusAfterAMergeTest(_WorktreeFlowCase):
    """AC4 / §S3: ``status`` reads a CR branch's own commits, merge commits excluded."""

    def setUp(self):
        super().setUp()
        self._add_worktree()

    def _row(self, result) -> dict:
        axi = decode_envelope(result.stdout)["axi"]
        rows = [r for r in axi["worktrees"] if r.get("cr") == CR]
        self.assertEqual(len(rows), 1, axi["worktrees"])
        return rows[0]

    def test_status_after_a_sync_merge_reports_the_newest_own_commit_and_own_count(self):
        self._branch_commit("a.txt", "a\n", "test(core): RED — failing contract")
        self._branch_commit("b.txt", "b\n", "feat(core): GREEN — implementation")
        self._develop_commit("d.txt", "d\n", "chore(other): develop moved")
        repo_git(self.wt, "merge", "-q", "--no-edit", DEVELOP)

        result = self._wf("status")

        self.assertEqual(result.returncode, 0, self._output(result))
        row = self._row(result)
        self.assertEqual(row["phase"], "GREEN", "the phase of the newest own commit")
        self.assertEqual(row["commits_ahead"], 2, "own commits only, the merge commit excluded")
        self.assertEqual(row["ahead"], 3, "git's count of commits not on develop, merge included")
        self.assertEqual(row["behind"], 0)

    def test_status_shows_a_behind_branch_as_sync_needed_and_no_state_names_rebase(self):
        self._branch_commit("a.txt", "a\n", "feat(core): GREEN — own")
        self._develop_commit("d1.txt", "1\n", "chore(other): develop moved once")
        self._develop_commit("d2.txt", "2\n", "chore(other): develop moved twice")

        result = self._wf("status")

        self.assertEqual(result.returncode, 0, self._output(result))
        self.assertEqual(self._row(result)["state"], "SYNC NEEDED (develop moved 2)")
        rows = decode_envelope(result.stdout)["axi"]["worktrees"]
        self.assertEqual([r["state"] for r in rows if "REBASE" in str(r["state"])], [])


# ---------------------------------------------------------------------------------------------
# §S8 / AC10: every other path of ``start``, ``status``, ``sync`` and ``finish``, and project
# resolution -- behaviour the tool already had, pinned as it runs.
# ---------------------------------------------------------------------------------------------

#: The lock line a finish running for another CR leaves in the merge lock.
OTHER_LOCK = "cr=CR-TST-999 pid=4242 ts=1700000000"

#: What ``abort --release-lock`` says when no merge lock is held.
NO_LOCK_HELD = re.compile(r"\bno (?:merge )?lock (?:was |is )?held\b", re.IGNORECASE)

#: The track label a fixture stamps on a CR.
TRACK = "Track 1 - Fixture"


class _WorktreeFlowPathCase(_WorktreeFlowCase):
    """Reads shared by the §S8 path tests: the envelope, refs, config and the lock."""

    def _axi(self, result) -> dict:
        return decode_envelope(result.stdout)["axi"]

    def _row(self, result, cr: str = CR) -> dict:
        rows = [r for r in self._axi(result)["worktrees"] if r.get("cr") == cr]
        self.assertEqual(len(rows), 1, self._output(result))
        return rows[0]

    def _integration_row(self, result) -> dict:
        rows = [r for r in self._axi(result)["worktrees"] if r["role"] == "integration"]
        self.assertEqual(len(rows), 1, self._output(result))
        return rows[0]

    def _branch_exists(self, branch: str) -> bool:
        try:
            repo_git(self.repo, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}")
        except AssertionError:
            return False
        return True

    def _config(self, key: str):
        """The fixture repository's value for ``key``, or ``None`` when it is unset."""
        try:
            return repo_git(self.repo, "config", "--get", key)
        except AssertionError:
            return None

    def _short(self, ref: str) -> str:
        return repo_git(self.repo, "rev-parse", "--short", ref)

    def _git_verbs_run(self) -> list:
        """The first argument of every git call the tool made."""
        return [c["argv"][0] for c in self._git_calls() if c["argv"]]

    def _bare_remote(self, name: str) -> Path:
        remote = self.work / name
        repo_git(self.work, "init", "-q", "--bare", remote)
        return remote


class ProjectResolutionTest(_WorktreeFlowPathCase):
    """§S8: the project is ``--project-dir``, else ``$WORKTREE_FLOW_PROJECT_DIR``, else the
    repository holding the current directory -- its main worktree, even from inside a CR
    worktree; outside any repository the run is refused naming the directory."""

    def setUp(self):
        super().setUp()
        self.other = git_repo(self.work / "other", {"o.txt": "other\n"}, branch=DEVELOP,
                              message="chore: other")

    def _assert_status_of_repo(self, result):
        self.assertEqual(result.returncode, 0, self._output(result))
        self.assertEqual(self._axi(result)["project"], "proj", self._output(result))
        self.assertIn(f"integration tree (owns {DEVELOP}): {self.repo}\n", result.stderr)

    def test_project_dir_flag_selects_the_repository_from_a_directory_outside_it(self):
        self._assert_status_of_repo(self._run("status", "--project-dir", self.repo))

    def test_project_dir_flag_wins_over_the_environment_variable(self):
        result = self._run("status", "--project-dir", self.repo,
                           env={"WORKTREE_FLOW_PROJECT_DIR": str(self.other)})
        self._assert_status_of_repo(result)
        self.assertNotIn(str(self.other), result.stderr)

    def test_environment_variable_selects_the_repository_from_a_directory_outside_it(self):
        self._assert_status_of_repo(
            self._run("status", env={"WORKTREE_FLOW_PROJECT_DIR": str(self.repo)}))

    def test_environment_variable_wins_over_the_current_directorys_repository(self):
        result = self._run("status", cwd=self.other,
                           env={"WORKTREE_FLOW_PROJECT_DIR": str(self.repo)})
        self._assert_status_of_repo(result)
        self.assertNotIn(str(self.other), result.stderr)

    def test_current_directory_inside_a_cr_worktree_resolves_the_main_worktree(self):
        self._add_worktree()
        inner = self.wt / "pkg"
        inner.mkdir()
        result = self._run("status", cwd=inner)
        self._assert_status_of_repo(result)
        self.assertEqual(self._row(result)["branch"], BRANCH)

    def test_outside_any_repository_the_run_is_refused_naming_the_directory(self):
        result = self._run("status")

        self.assertEqual(result.returncode, 1, self._output(result))
        self.assertEqual(result.stderr,
                         f"[worktree-flow] ERROR: {self.cwd} is not a git repository\n")
        self.assertEqual(result.stdout, "", "a refused run prints no envelope")

    def test_project_dir_that_is_no_repository_is_refused_naming_it(self):
        plain = self.work / "plain"
        plain.mkdir()
        result = self._run("status", "--project-dir", plain)

        self.assertEqual(result.returncode, 1, self._output(result))
        self.assertEqual(result.stderr,
                         f"[worktree-flow] ERROR: {plain} is not a git repository\n")
        self.assertEqual(result.stdout, "")


class StartRefusalTest(_WorktreeFlowPathCase):
    """§S8: each ``start`` refusal exits 1 naming its cause and creates neither the branch nor
    the worktree."""

    def _assert_refused(self, result, message: str):
        self.assertEqual(result.returncode, 1, self._output(result))
        self.assertIn(f"[worktree-flow] ERROR: {message}", result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertNotIn(["worktree", "add"], [c["argv"][:2] for c in self._git_calls()],
                         "a refused start adds no worktree")

    def test_start_refuses_a_branch_outside_the_feature_prefix(self):
        result = self._wf("start", "--cr", CR, "--branch", "topic/CR-TST-001")

        self._assert_refused(result, "--branch must start with 'feature/'")
        self.assertIn("Got: topic/CR-TST-001", result.stderr)
        self.assertFalse(self._branch_exists("topic/CR-TST-001"))
        self.assertFalse(self.wt.exists())

    def test_start_refuses_a_branch_that_already_exists(self):
        repo_git(self.repo, "branch", BRANCH)

        result = self._wf("start", "--cr", CR)

        self._assert_refused(result, f"branch already exists: {BRANCH}")
        self.assertFalse(self.wt.exists())

    def test_start_refuses_a_worktree_path_that_already_exists(self):
        write_files(self.wt, {"keep.txt": "in the way\n"})

        result = self._wf("start", "--cr", CR)

        self._assert_refused(result, f"worktree path already exists: {self.wt}")
        self.assertFalse(self._branch_exists(BRANCH))
        self.assertEqual(sorted(p.name for p in self.wt.iterdir()), ["keep.txt"])

    def test_start_refuses_a_base_that_does_not_resolve(self):
        result = self._wf("start", "--cr", CR, "--base", "no-such-base")

        self._assert_refused(result, "base ref does not resolve: no-such-base")
        self.assertFalse(self._branch_exists(BRANCH))
        self.assertFalse(self.wt.exists())


class StartTest(_WorktreeFlowPathCase):
    """§S8: ``start`` branches off LOCAL develop into ``.worktrees/<cr>``, notes a local develop
    behind its upstream, copies ``.env``, stamps the track label from ``--track`` or
    ``$WF_TRACK``, and ``--dry-run`` prints the plan and changes nothing."""

    def _assert_started(self, result, branch: str = BRANCH):
        self.assertEqual(result.returncode, 0, self._output(result))
        develop = self._head(DEVELOP)
        self.assertIn(f"start: ok worktree={self.wt} branch={branch} "
                      f"base={DEVELOP}@{self._short(DEVELOP)}\n", result.stdout)
        self.assertEqual(self._head(branch), develop, "the branch starts at local develop")
        self.assertEqual(repo_git(self.wt, "rev-parse", "--abbrev-ref", "HEAD"), branch)

    def test_start_creates_the_worktree_on_a_slugged_feature_branch_off_develop(self):
        result = self._wf("start", "--cr", CR, "--slug", "widget")

        self._assert_started(result, branch=f"{BRANCH}-widget")
        self.assertIsNone(self._config(f"wf.track.{CR}"), "no label, no track key")
        self.assertNotIn("track:", result.stdout)
        self.assertNotIn("NOTE:", result.stdout)

    def test_start_notes_a_local_develop_behind_its_upstream_and_branches_off_local(self):
        remote = self._bare_remote("origin.git")
        repo_git(self.repo, "remote", "add", "origin", remote)
        local = self._head(DEVELOP)
        self._develop_commit("pushed.txt", "p\n", "chore: only upstream keeps this")
        repo_git(self.repo, "push", "-q", "-u", "origin", DEVELOP)
        repo_git(self.repo, "reset", "-q", "--hard", local)

        result = self._wf("start", "--cr", CR)

        self._assert_started(result)
        self.assertIn(f"[worktree-flow] NOTE: local {DEVELOP} is 1 commit(s) behind "
                      f"origin/{DEVELOP}. Branching off LOCAL {DEVELOP} ({self._short(local)})",
                      result.stdout)
        self.assertEqual(self._head(BRANCH), local, "the branch is off LOCAL develop, not upstream")

    def test_start_prints_no_note_when_local_develop_is_level_with_its_upstream(self):
        remote = self._bare_remote("origin.git")
        repo_git(self.repo, "remote", "add", "origin", remote)
        repo_git(self.repo, "push", "-q", "-u", "origin", DEVELOP)

        result = self._wf("start", "--cr", CR)

        self._assert_started(result)
        self.assertNotIn("NOTE:", result.stdout)

    def test_start_copies_the_main_trees_env_file_into_the_new_worktree(self):
        write_files(self.repo, {".env": "CRUCIBLE_PROJECT_KEY=fixture-key\n"})

        result = self._wf("start", "--cr", CR)

        self._assert_started(result)
        self.assertTrue((self.wt / ".env").is_file(), "the main tree's .env must be copied")
        self.assertEqual((self.wt / ".env").read_text(encoding="utf-8"),
                         "CRUCIBLE_PROJECT_KEY=fixture-key\n")
        self.assertIn(f"  env: copied .env → {self.wt / '.env'}", result.stdout)

    def test_start_without_an_env_file_copies_nothing(self):
        result = self._wf("start", "--cr", CR)

        self._assert_started(result)
        self.assertFalse((self.wt / ".env").exists())
        self.assertNotIn("env: copied", result.stdout)

    def test_start_stamps_the_track_label_given_by_the_track_flag(self):
        result = self._wf("start", "--cr", CR, "--track", TRACK)

        self._assert_started(result)
        self.assertEqual(self._config(f"wf.track.{CR}"), TRACK)
        self.assertIn(f"  track: {TRACK}  (--track → shown in `status`)", result.stdout)

    def test_start_stamps_the_track_label_from_the_wf_track_variable(self):
        result = self._wf("start", "--cr", CR, env={"WF_TRACK": TRACK})

        self._assert_started(result)
        self.assertEqual(self._config(f"wf.track.{CR}"), TRACK)
        self.assertIn(f"  track: {TRACK}  ($WF_TRACK → shown in `status`)", result.stdout)

    def test_start_track_flag_wins_over_the_wf_track_variable(self):
        result = self._wf("start", "--cr", CR, "--track", TRACK,
                          env={"WF_TRACK": "Track 9 - Session"})

        self._assert_started(result)
        self.assertEqual(self._config(f"wf.track.{CR}"), TRACK)

    def test_start_dry_run_prints_the_worktree_add_and_label_and_changes_nothing(self):
        result = self._wf("start", "--cr", CR, "--dry-run", "--track", TRACK)

        self.assertEqual(result.returncode, 0, self._output(result))
        self.assertEqual(result.stdout.splitlines(), [
            f"[dry-run] git -C {self.repo} worktree add -b {BRANCH} {self.wt} {DEVELOP}",
            f"[dry-run] would create worktree {self.wt} on {BRANCH} from {DEVELOP} "
            f"({self._short(DEVELOP)})",
            f"[dry-run] would tag track label: {TRACK}",
        ])
        self.assertFalse(self.wt.exists())
        self.assertFalse(self._branch_exists(BRANCH))
        self.assertIsNone(self._config(f"wf.track.{CR}"))
        self.assertNotIn(["worktree", "add"], [c["argv"][:2] for c in self._git_calls()])


class StatusTest(_WorktreeFlowPathCase):
    """§S8: ``status`` reports the merge lock, detached and dirty worktrees, a dirty integration
    tree, the track label and each phase token."""

    def test_status_reports_a_held_merge_lock_on_stderr_and_as_a_warning(self):
        self._lock().write_text(OTHER_LOCK + "\n", encoding="utf-8")

        result = self._wf("status")

        self.assertEqual(result.returncode, 0, self._output(result))
        self.assertIn(f"⚠ MERGE LOCK HELD: {OTHER_LOCK}", result.stderr)
        self.assertEqual(self._axi(result)["warnings"],
                         [f"merge lock held: {OTHER_LOCK} (a finish is in progress — do not merge)"])
        self.assertEqual(self._lock().read_text(encoding="utf-8"), OTHER_LOCK + "\n",
                         "status only reads the lock")

    def test_status_with_no_lock_warns_of_none(self):
        result = self._wf("status")

        self.assertEqual(result.returncode, 0, self._output(result))
        self.assertEqual(self._axi(result)["warnings"], [])
        self.assertNotIn("MERGE LOCK", result.stderr)

    def test_status_shows_a_detached_worktree_with_no_branch_counts_or_phase(self):
        repo_git(self.repo, "worktree", "add", "-q", "--detach", self.wt, DEVELOP)

        result = self._wf("status")

        self.assertEqual(result.returncode, 0, self._output(result))
        row = self._row(result)
        self.assertEqual(row["branch"], "(detached)")
        self.assertEqual(row["head"], self._head(DEVELOP)[:9])
        self.assertEqual((row["ahead"], row["behind"]), (None, None))
        self.assertEqual((row["phase"], row["commits_ahead"]), (None, None))
        self.assertEqual(row["path"], str(self.wt))

    def test_status_never_calls_a_detached_worktree_finish_ready(self):
        # `finish` refuses a detached worktree, so its state must name it as detached instead.
        repo_git(self.repo, "worktree", "add", "-q", "--detach", self.wt, DEVELOP)

        result = self._wf("status")

        self.assertEqual(result.returncode, 0, self._output(result))
        state = self._row(result)["state"]
        self.assertNotIn("finish-ready", state)
        self.assertIn("detached", state.lower())
        board = [line for line in result.stderr.splitlines() if "(detached)" in line]
        self.assertEqual(len(board), 1, result.stderr)
        self.assertNotIn("finish-ready", board[0])
        self.assertIn("detached", board[0].split("(detached)", 1)[1].lower(),
                      "the board's state column names the worktree as detached")

    def test_status_shows_a_dirty_level_worktree_as_dirty(self):
        self._add_worktree()
        write_files(self.wt, {"wip.txt": "uncommitted\n"})

        result = self._wf("status")

        self.assertEqual(result.returncode, 0, self._output(result))
        self.assertEqual(self._row(result)["state"], "DIRTY (commit first)")
        self.assertEqual(self._integration_row(result)["state"], "clean")

    def test_status_shows_a_clean_level_worktree_as_finish_ready(self):
        self._add_worktree()
        self._branch_commit("a.txt", "a\n", "feat(core): GREEN — own")

        result = self._wf("status")

        self.assertEqual(result.returncode, 0, self._output(result))
        row = self._row(result)
        self.assertEqual(row["state"], "clean — finish-ready")
        self.assertEqual((row["ahead"], row["behind"]), (1, 0))

    def test_status_shows_a_dirty_behind_worktree_as_sync_needed_and_dirty(self):
        self._add_worktree()
        write_files(self.wt, {"wip.txt": "uncommitted\n"})
        self._develop_commit("d.txt", "d\n", "chore(other): develop moved")

        result = self._wf("status")

        self.assertEqual(result.returncode, 0, self._output(result))
        self.assertEqual(self._row(result)["state"], "SYNC NEEDED (develop moved 1) + DIRTY")

    def test_status_shows_a_dirty_integration_tree(self):
        write_files(self.repo, {"wip.txt": "uncommitted on develop\n"})

        result = self._wf("status")

        self.assertEqual(result.returncode, 0, self._output(result))
        row = self._integration_row(result)
        self.assertEqual(row["state"], "DIRTY (has WIP)")
        self.assertEqual(row["branch"], DEVELOP)
        self.assertEqual((row["cr"], row["ahead"], row["behind"]), (None, None, None))

    def test_status_shows_the_track_label_of_a_labelled_worktree_only(self):
        self._add_worktree()
        other_cr = "CR-TST-002"
        repo_git(self.repo, "worktree", "add", "-q", "-b", f"feature/{other_cr}",
                 self.repo / ".worktrees" / other_cr, DEVELOP)
        repo_git(self.repo, "config", f"wf.track.{CR}", TRACK)

        result = self._wf("status")

        self.assertEqual(result.returncode, 0, self._output(result))
        self.assertEqual(self._row(result)["track"], TRACK)
        self.assertNotEqual(self._row(result, other_cr)["track"], TRACK)
        self.assertEqual(result.stderr.count(f"track: {TRACK}"), 1)

    def test_status_reads_each_phase_token_from_the_newest_commit_subject(self):
        cases = {
            "CR-TST-P01": ("chore(core): CLOSE-OUT — wrap up", "CLOSE-OUT"),
            "CR-TST-P02": ("fix(core): RED-fix — repair the test", "RED-fix"),
            "CR-TST-P03": ("feat(core): GREEN — implement it", "GREEN"),
            "CR-TST-P04": ("docs(core): VERIFY — report", "VERIFY"),
            "CR-TST-P05": ("test(core): RED — failing contract", "RED"),
            "CR-TST-P06": ("feat(red): add a widget", "GREEN"),
            "CR-TST-P07": ("fix(core): handle an edge", "GREEN"),
            "CR-TST-P08": ("test(green): cover an edge", "RED"),
            "CR-TST-P09": ("docs(core): explain", "docs/chore"),
            "CR-TST-P10": ("chore(core): tidy", "docs/chore"),
            "CR-TST-P11": ("refactor(core): move", "?"),
        }
        for cr, (subject, _phase) in cases.items():
            tree = self.repo / ".worktrees" / cr
            repo_git(self.repo, "worktree", "add", "-q", "-b", f"feature/{cr}", tree, DEVELOP)
            git_commit_all(tree, "chore(core): an older commit")
            git_commit_all(tree, subject)
        fresh = "CR-TST-P12"
        repo_git(self.repo, "worktree", "add", "-q", "-b", f"feature/{fresh}",
                 self.repo / ".worktrees" / fresh, DEVELOP)

        result = self._wf("status")

        self.assertEqual(result.returncode, 0, self._output(result))
        for cr, (subject, phase) in cases.items():
            with self.subTest(subject=subject):
                row = self._row(result, cr)
                self.assertEqual(row["phase"], phase)
                self.assertEqual(row["commits_ahead"], 2)
                self.assertEqual(row["last_subject"], subject)
        row = self._row(result, fresh)
        self.assertEqual((row["phase"], row["commits_ahead"]), ("started — RED pending", 0))


class SyncRefusalAndLevelTest(_WorktreeFlowPathCase):
    """§S1's cases that held before the merge form: a level branch reports so and runs nothing,
    clean or not; a behind branch with a dirty worktree is refused before anything runs; a
    missing or a detached worktree is refused naming the cause."""

    def _assert_ran_no_merge(self):
        self.assertNotIn("merge", self._git_verbs_run(), "no merge may run")

    def _assert_level_reported(self, result):
        self.assertEqual(result.returncode, 0, self._output(result))
        self.assertEqual(result.stdout,
                         f"sync: ok branch={BRANCH} already up to date with {DEVELOP} "
                         f"(ahead=1, behind=0) — nothing to merge\n")
        self._assert_ran_no_merge()

    def test_sync_on_a_level_clean_branch_reports_it_and_runs_nothing(self):
        self._add_worktree()
        own = self._branch_commit("a.txt", "a\n", "feat(core): GREEN — own")

        result = self._wf("sync", "--cr", CR)

        self._assert_level_reported(result)
        self.assertEqual(self._head(BRANCH), own)

    def test_sync_on_a_level_dirty_branch_reports_it_and_runs_nothing(self):
        self._add_worktree()
        own = self._branch_commit("a.txt", "a\n", "feat(core): GREEN — own")
        write_files(self.wt, {"README.md": "edited, not committed\n"})

        result = self._wf("sync", "--cr", CR)

        self._assert_level_reported(result)
        self.assertEqual(self._head(BRANCH), own)
        self.assertEqual((self.wt / "README.md").read_text(encoding="utf-8"),
                         "edited, not committed\n")

    def test_sync_on_a_behind_branch_with_a_dirty_worktree_is_refused_before_anything_runs(self):
        self._add_worktree()
        own = self._branch_commit("a.txt", "a\n", "feat(core): GREEN — own")
        self._develop_commit("d.txt", "d\n", "chore(other): develop moved")
        write_files(self.wt, {"README.md": "edited, not committed\n"})

        result = self._wf("sync", "--cr", CR)

        self.assertEqual(result.returncode, 1, self._output(result))
        self.assertEqual(result.stderr,
                         f"[worktree-flow] ERROR: {self.wt} has uncommitted changes. "
                         f"Commit or stash before syncing.\n")
        self._assert_ran_no_merge()
        self.assertEqual(self._head(BRANCH), own)
        self.assertEqual((self.wt / "README.md").read_text(encoding="utf-8"),
                         "edited, not committed\n")

    def test_sync_with_no_worktree_is_refused_naming_it(self):
        result = self._wf("sync", "--cr", CR)

        self.assertEqual(result.returncode, 1, self._output(result))
        self.assertIn(f"[worktree-flow] ERROR: no worktree at {self.wt}. "
                      f"Run `start --cr {CR}` first", result.stderr)
        self._assert_ran_no_merge()
        self.assertFalse(self._branch_exists(BRANCH))

    def test_sync_on_a_detached_worktree_is_refused_naming_it(self):
        repo_git(self.repo, "worktree", "add", "-q", "--detach", self.wt, DEVELOP)
        self._develop_commit("d.txt", "d\n", "chore(other): develop moved")
        before = repo_git(self.wt, "rev-parse", "HEAD")

        result = self._wf("sync", "--cr", CR)

        self.assertEqual(result.returncode, 1, self._output(result))
        self.assertIn(f"[worktree-flow] ERROR: worktree {self.wt} is in detached HEAD",
                      result.stderr)
        self._assert_ran_no_merge()
        self.assertEqual(repo_git(self.wt, "rev-parse", "HEAD"), before)


class _FinishCase(_WorktreeFlowPathCase):
    """A CR worktree with one own commit, level with develop."""

    def setUp(self):
        super().setUp()
        self._add_worktree()
        self.own = self._branch_commit("a.txt", "a\n", "feat(core): GREEN — own")
        self.develop_before = self._head(DEVELOP)

    def _merge_steps(self) -> list:
        return [c["argv"] for c in self._git_calls() if c["argv"][:2] == ["merge", "--no-ff"]]

    def _assert_merged_into_develop(self):
        head = self._head(DEVELOP)
        self.assertEqual(self._parents(head), [self.develop_before, self.own],
                         "develop's head must be the --no-ff merge of the branch")
        self.assertEqual(repo_git(self.repo, "log", "-1", "--format=%s", DEVELOP),
                         f"Merge branch '{BRANCH}' into {DEVELOP}")

    def _assert_changed_nothing(self, result, message: str):
        self.assertEqual(result.returncode, 1, self._output(result))
        self.assertIn(f"[worktree-flow] ERROR: {message}", result.stderr)
        self.assertEqual(self._head(DEVELOP), self.develop_before, "develop must be unchanged")
        self.assertEqual(self._head(BRANCH), self.own, "the branch must be unchanged")
        self.assertTrue(self.wt.is_dir(), "the worktree must remain")
        self.assertEqual(self._merge_steps(), [], "nothing is merged into develop")


class FinishRefusalTest(_FinishCase):
    """§S8: each ``finish`` refusal exits 1 naming its cause, merges nothing, removes nothing
    and leaves no lock; a lock held by another finish is left as it was."""

    def test_finish_from_inside_the_worktree_is_refused(self):
        result = self._wf("finish", "--cr", CR, cwd=self.wt)

        self._assert_changed_nothing(result, f"you are INSIDE the worktree being removed ({self.wt})")
        self.assertFalse(self._lock().exists())

    def test_finish_from_a_directory_below_the_worktree_is_refused(self):
        inner = self.wt / "pkg"
        inner.mkdir()

        result = self._wf("finish", "--cr", CR, cwd=inner)

        self._assert_changed_nothing(result, f"you are INSIDE the worktree being removed ({self.wt})")

    def test_finish_with_a_dirty_worktree_is_refused(self):
        write_files(self.wt, {"README.md": "edited, not committed\n"})

        result = self._wf("finish", "--cr", CR)

        self._assert_changed_nothing(result, f"worktree {self.wt} has uncommitted changes")
        self.assertEqual((self.wt / "README.md").read_text(encoding="utf-8"),
                         "edited, not committed\n")
        self.assertFalse(self._lock().exists())

    def test_finish_with_a_dirty_integration_tree_is_refused(self):
        write_files(self.repo, {"wip.txt": "uncommitted on develop\n"})

        result = self._wf("finish", "--cr", CR)

        self._assert_changed_nothing(result, f"integration tree {self.repo} is DIRTY")
        self.assertFalse(self._lock().exists())

    def test_finish_with_the_integration_tree_off_develop_is_refused(self):
        repo_git(self.repo, "checkout", "-q", "-b", "elsewhere")

        result = self._wf("finish", "--cr", CR)

        self._assert_changed_nothing(
            result, f"integration tree is on 'elsewhere', not '{DEVELOP}'")
        self.assertEqual(self._head("elsewhere"), self.develop_before)
        self.assertFalse(self._lock().exists())

    def test_finish_with_nothing_ahead_of_develop_is_refused(self):
        repo_git(self.wt, "reset", "-q", "--hard", DEVELOP)
        self.own = self._head(DEVELOP)

        result = self._wf("finish", "--cr", CR)

        self._assert_changed_nothing(
            result, f"{BRANCH} has no commits beyond {DEVELOP} — nothing to finish.")
        self.assertTrue(self._branch_exists(BRANCH))
        self.assertFalse(self._lock().exists())

    def test_finish_with_the_lock_held_by_another_finish_is_refused_and_leaves_it(self):
        self._lock().write_text(OTHER_LOCK + "\n", encoding="utf-8")

        result = self._wf("finish", "--cr", CR)

        self._assert_changed_nothing(result, f"merge lock held by another finish [{OTHER_LOCK}]")
        self.assertEqual(self._lock().read_text(encoding="utf-8"), OTHER_LOCK + "\n",
                         "another finish's lock must be left as it was")

    def test_finish_no_auto_sync_on_a_behind_branch_is_refused_naming_sync(self):
        self.develop_before = self._develop_commit("d.txt", "d\n", "chore(other): develop moved")

        result = self._wf("finish", "--cr", CR, "--no-auto-sync")

        self._assert_changed_nothing(result, f"{BRANCH} is 1 behind {DEVELOP}")
        self.assertIn(f"Run `sync --cr {CR}` first.", result.stderr)
        self.assertNotIn("merge", self._git_verbs_run(), "no catch-up merge may run")
        self.assertFalse(self._lock().exists(), "the lock is released")


class FinishTest(_FinishCase):
    """§S8: ``finish``'s dance -- a worktree removal that needs ``--force``, a partial removal,
    a failed branch delete, ``--push`` succeeding and failing, ``--dry-run``."""

    def test_finish_retries_a_refused_worktree_removal_with_force(self):
        # git refuses a plain removal of a worktree holding a submodule store.
        git_dir = repo_git(self.wt, "rev-parse", "--path-format=absolute", "--git-dir")
        (Path(git_dir) / "modules").mkdir()

        result = self._wf("finish", "--cr", CR)

        self.assertEqual(result.returncode, 0, self._output(result))
        self._assert_merged_into_develop()
        removals = [c["argv"] for c in self._git_calls() if c["argv"][:2] == ["worktree", "remove"]]
        self.assertEqual(removals, [["worktree", "remove", str(self.wt)],
                                    ["worktree", "remove", "--force", str(self.wt)]])
        self.assertFalse(self.wt.exists())
        self.assertFalse(self._branch_exists(BRANCH))
        self.assertFalse(self._lock().exists())
        axi = self._axi(result)
        self.assertEqual((axi["ok"], axi["warnings"]), (True, []))

    def test_finish_with_a_worktree_it_cannot_remove_reports_a_partial_finish(self):
        # A locked worktree refuses removal with and without a single --force.
        repo_git(self.repo, "worktree", "lock", self.wt)

        result = self._wf("finish", "--cr", CR)

        self.assertEqual(result.returncode, 1, self._output(result))
        self._assert_merged_into_develop()
        self.assertTrue(self.wt.is_dir(), "the worktree folder remains")
        self.assertTrue(self._branch_exists(BRANCH), "a branch still checked out is kept")
        self.assertFalse(self._lock().exists(), "the merge lock is released")
        self.assertIn(f"PARTIAL FINISH — merge into {DEVELOP} SUCCEEDED", result.stderr)
        self.assertIn(f"FOLDER NOT FULLY REMOVED: {self.wt}", result.stderr)
        axi = self._axi(result)
        self.assertEqual((axi["ok"], axi["partial"]), (False, True))
        self.assertEqual(axi["merged_head"], self._short(DEVELOP))
        self.assertEqual(axi["warnings"], [
            f"PARTIAL FINISH — merge into {DEVELOP} succeeded but worktree removal did not complete",
            f"folder not fully removed: {self.wt}",
        ])
        self.assertEqual(axi["help"], [
            f"sudo rm -rf {self.wt}",
            f"git -C {self.repo} worktree prune && git -C {self.repo} branch -d {BRANCH}",
        ])

    def test_finish_with_a_failed_branch_delete_keeps_the_branch_and_warns(self):
        # The branch is also checked out elsewhere, so `branch -d` refuses it.
        repo_git(self.repo, "worktree", "add", "-q", "--force", self.work / "second", BRANCH)
        repo_git(self.repo, "config", f"wf.track.{CR}", TRACK)

        result = self._wf("finish", "--cr", CR)

        self.assertEqual(result.returncode, 0, self._output(result))
        self._assert_merged_into_develop()
        self.assertFalse(self.wt.exists(), "the CR's worktree is removed")
        self.assertTrue(self._branch_exists(BRANCH), "the branch is kept")
        self.assertIn(f"`branch -d {BRANCH}` failed (branch kept)", result.stderr)
        axi = self._axi(result)
        self.assertEqual(axi["ok"], True)
        self.assertEqual(axi["warnings"],
                         [f"branch -d {BRANCH} failed (branch kept) — delete manually"])
        self.assertEqual(axi["help"], [f"git -C {self.repo} branch -d {BRANCH}"])
        self.assertIsNone(self._config(f"wf.track.{CR}"), "the track label is unset")

    def test_finish_with_a_failed_branch_delete_never_says_the_branch_was_deleted(self):
        # The branch is also checked out elsewhere, so `branch -d` refuses it.
        repo_git(self.repo, "worktree", "add", "-q", "--force", self.work / "second", BRANCH)

        result = self._wf("finish", "--cr", CR)

        self.assertEqual(result.returncode, 0, self._output(result))
        self.assertTrue(self._branch_exists(BRANCH), "the branch is kept")
        claims = [line for line in (result.stdout + result.stderr).splitlines()
                  if "branch deleted" in line.lower()]
        self.assertEqual(claims, [], "no line may say the kept branch was deleted")
        self.assertIn(f"[worktree-flow] WARN: merge + worktree removal succeeded but "
                      f"`branch -d {BRANCH}` failed (branch kept). Delete manually: "
                      f"git -C {self.repo} branch -d {BRANCH}\n", result.stderr)
        self.assertEqual(self._axi(result)["warnings"],
                         [f"branch -d {BRANCH} failed (branch kept) — delete manually"])

    def test_finish_push_merges_removes_deletes_and_pushes_develop(self):
        remote = self._bare_remote("origin.git")
        repo_git(self.repo, "remote", "add", "origin", remote)
        repo_git(self.repo, "push", "-q", "origin", DEVELOP)
        repo_git(self.repo, "config", f"wf.track.{CR}", TRACK)

        result = self._wf("finish", "--cr", CR, "--push")

        self.assertEqual(result.returncode, 0, self._output(result))
        self._assert_merged_into_develop()
        self.assertFalse(self.wt.exists())
        self.assertFalse(self._branch_exists(BRANCH))
        self.assertFalse(self._lock().exists())
        self.assertIsNone(self._config(f"wf.track.{CR}"), "the track label is unset")
        self.assertEqual(repo_git(remote, "rev-parse", DEVELOP), self._head(DEVELOP),
                         "the remote's develop must be the merged head")
        self.assertIn(f"finish: pushed {DEVELOP} → origin", result.stderr)
        axi = self._axi(result)
        self.assertEqual((axi["ok"], axi["pushed"], axi["warnings"]), (True, True, []))
        self.assertEqual(axi["merged_head"], self._short(DEVELOP))

    def test_finish_push_failure_keeps_the_merge_and_reports_it(self):
        repo_git(self.repo, "remote", "add", "origin", self.work / "no-such-remote.git")

        result = self._wf("finish", "--cr", CR, "--push")

        self.assertEqual(result.returncode, 1, self._output(result))
        self._assert_merged_into_develop()
        self.assertFalse(self.wt.exists())
        self.assertFalse(self._branch_exists(BRANCH))
        self.assertFalse(self._lock().exists())
        self.assertIn(f"`push origin {DEVELOP}` failed", result.stderr)
        axi = self._axi(result)
        self.assertEqual((axi["ok"], axi["pushed"]), (False, False))
        self.assertEqual(axi["warnings"],
                         [f"merge succeeded but `push origin {DEVELOP}` failed — push manually"])
        self.assertEqual(axi["help"], [f"git -C {self.repo} push origin {DEVELOP}"])

    def test_finish_dry_run_prints_the_plan_and_changes_nothing(self):
        result = self._wf("finish", "--cr", CR, "--dry-run", "--push")

        self.assertEqual(result.returncode, 0, self._output(result))
        axi = self._axi(result)
        self.assertEqual((axi["ok"], axi["dry_run"], axi["cr"], axi["branch"]),
                         (True, True, CR, BRANCH))
        plan = axi["help"]
        self.assertEqual(len(plan), 5, plan)
        self.assertTrue(plan[0].startswith(f"git -C {self.repo} merge --no-ff {BRANCH} -m "),
                        plan)
        self.assertIn(f"Merge branch '{BRANCH}' into {DEVELOP}", plan[0])
        self.assertEqual(plan[1:], [
            f"git -C {self.repo} worktree remove {self.wt}",
            f"git -C {self.repo} worktree prune",
            f"git -C {self.repo} branch -d {BRANCH}",
            f"git -C {self.repo} push origin {DEVELOP}",
        ])
        self.assertIn("[dry-run] finish plan:", result.stderr)
        for step in plan:
            self.assertIn(f"  {step}\n", result.stderr)
        self.assertEqual(self._head(DEVELOP), self.develop_before)
        self.assertEqual(self._head(BRANCH), self.own)
        self.assertTrue(self.wt.is_dir())
        self.assertFalse(self._lock().exists())
        mutating = [argv for argv in (c["argv"] for c in self._git_calls())
                    if argv[:1] in (["merge"], ["branch"], ["push"])
                    or argv[:2] in (["worktree", "remove"], ["worktree", "prune"])]
        self.assertEqual(mutating, [], "a dry run runs no mutating git command")


# ---------------------------------------------------------------------------------------------
# §S4 / AC5: the tool and its rules describe a merge, never a rebase.
# ---------------------------------------------------------------------------------------------

#: ``rebas`` (rebase, rebases, rebasing, rebased) in any case.
_REBASING = re.compile(r"rebas", re.IGNORECASE)

#: A rebase the sentence says does NOT happen: a negation shortly before ``rebas``.
_NEGATED_REBASE = re.compile(r"\b(?:never|not|no|nor|without)\b[\w\s,-]{0,30}?rebas\w*",
                             re.IGNORECASE)


def _rebasing_descriptions(pieces) -> list:
    """The pieces of text that describe something as rebasing: a ``rebas`` left once every
    negated one (``never rebases``, ``merge-not-rebase``, ``not a long rebase``) is removed."""
    return [p for p in pieces if _REBASING.search(_NEGATED_REBASE.sub("", p))]


def _script_text_pieces(source: str) -> list:
    """Every string constant of ``source`` -- docstrings, help texts, messages, f-string parts
    -- split into sentences and lines."""
    pieces = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            pieces += [p for p in re.split(r"(?<=[.;!?])\s+|\n", node.value) if p.strip()]
    return pieces


class WorktreeFlowDescribesNoRebaseTest(_WorktreeFlowCase):
    """AC5 / §S4: no help text, message or docstring of ``worktree-flow.py`` describes the tool
    as rebasing."""

    maxDiff = None

    def test_no_string_in_worktree_flow_describes_the_tool_as_rebasing(self):
        # The detector bites on a rebasing description and spares a negated one.
        self.assertEqual(_rebasing_descriptions([
            "Rebase a CR's feature branch onto develop",
            "Fail (instead of auto-rebasing) if develop moved",
            "sync merges develop in and never rebases",
            "finish (merge-not-rebase)",
            "merge develop in (not a long re-conflicting rebase)",
        ]), ["Rebase a CR's feature branch onto develop",
             "Fail (instead of auto-rebasing) if develop moved"])
        source = (TOOL_SCRIPTS_DIR / WORKTREE_FLOW).read_text(encoding="utf-8")
        pieces = _script_text_pieces(source)
        self.assertIn("Print the exact git commands that would run; mutate nothing.",
                      " ".join(pieces), "the scan must see the script's help texts")
        self.assertEqual(_rebasing_descriptions(pieces), [])

    def test_no_help_of_worktree_flow_or_its_verbs_describes_rebasing(self):
        helps = {}
        for verb in ((), ("start",), ("status",), ("sync",), ("finish",), ("abort",)):
            result = self._run(*verb, "-h")
            self.assertEqual(result.returncode, 0, self._output(result))
            helps[" ".join(verb) or "worktree-flow"] = result.stdout
        offenders = {name: _rebasing_descriptions(
                         re.split(r"(?<=[.;!?])\s+|\n", re.sub(r"[ \t]*\n[ \t]+", " ", text)))
                     for name, text in helps.items()}
        self.assertEqual({name: hits for name, hits in offenders.items() if hits}, {})


#: The four rule surfaces of §S4, as ``{name: (path, heading or None)}``.
RULE_SURFACES = {
    "orchestration-common.md § Worktree isolation (basics)": (
        "skills-src/model-b/references/orchestration-common.md", "## Worktree isolation (basics)"),
    "orchestration-track.md": ("skills-src/model-b/references/orchestration-track.md", None),
    "shutdown Step 2A": ("skills-src/shutdown/SKILL.md", "## Step 2A"),
    "rust-orchestration.md": ("skills-src/memory-templates/rust-orchestration.md", None),
}

#: The rules' form of the step: the CR's worktree branch brought level by the tool.
_SYNC_FOR_CR = re.compile(r"worktree-flow\.py sync --cr <cr>")

#: A sentence telling the orchestrator not to use ``sync``.
_FORBIDS_SYNC = re.compile(r"\b(?:(?:never|not|don't|do not)\s+(?:use|run|call)|avoid)\s+"
                           r"(?:worktree-flow(?:\.py)?\s+)?sync\b")

#: A develop merge made by hand, and the worktree it is made in.
_HAND_MERGE = re.compile(r"\bmerg(?:e|es|ing) develop\b|\bgit -c \.worktrees/<cr> merge\b")
_WORKTREE_CONTEXT = re.compile(r"\.worktrees/|\bworktree\b(?!-flow)|\byour branch\b")

#: What spares a hand merge: the tool's own step, the no-worktree case §S4 keeps, a negation.
_HAND_MERGE_SPARED = re.compile(r"worktree-flow\.py sync\b|\b(?:no|without a|without its) "
                                r"worktree\b|\b(?:never|do not|don't)\s+(?:\S+\s+){0,2}merg")


def _rule_surface_sentences(name: str) -> list:
    """The normalised sentences of the rule surface ``name`` (its section, when it has one)."""
    rel, heading = RULE_SURFACES[name]
    text = read_text(REPO_ROOT / rel)
    if heading is not None:
        text = md_section(text, heading)
    return sentences(text)


def _forbids_sync(sentence_list) -> list:
    return [s for s in sentence_list if _FORBIDS_SYNC.search(s)]


def _hand_worktree_merges(sentence_list) -> list:
    """The sentences merging develop into a worktree branch by hand, not through the tool."""
    return [s for s in sentence_list if _HAND_MERGE.search(s) and _WORKTREE_CONTEXT.search(s)
            and not _HAND_MERGE_SPARED.search(s)]


#: A rule bringing a stale branch level with develop: a resync, a develop merge, "level with".
_CATCH_UP_RULE = re.compile(r"\bresync\b|\bmerg(?:e|es|ing) develop (?:in|into)\b|\blevel with\b")

#: What lets a catch-up rule stand: it names the tool's step for a worktree branch, it is the
#: main-tree case with no worktree (§S4 keeps it), or it is the ``sync`` verb's own entry.
_CATCH_UP_SPARED = re.compile(r"worktree-flow\.py sync --cr <cr>|\b(?:no|without a|without its) "
                              r"worktree\b|^sync --cr <")


def _catch_ups_without_sync(sentence_list) -> list:
    """The catch-up rules naming no ``worktree-flow.py sync --cr <cr>`` for a worktree branch."""
    return [s for s in sentence_list
            if _CATCH_UP_RULE.search(s) and not _CATCH_UP_SPARED.search(s)]


class SyncRuleSurfacesTest(unittest.TestCase):
    """AC5 / §S4: each rule surface names ``worktree-flow.py sync --cr <cr>`` as the step before
    ``finish`` -- the two in one sentence -- and none forbids ``sync``, merges develop into a
    worktree branch by hand, or describes ``worktree-flow`` as rebasing."""

    def _each_surface(self):
        for name in RULE_SURFACES:
            found = _rule_surface_sentences(name)
            self.assertTrue(found, f"{name}: the surface (or its section) is missing")
            yield name, found

    def test_each_rule_surface_names_sync_for_the_crs_worktree_together_with_finish(self):
        for name, found in self._each_surface():
            with self.subTest(surface=name):
                named = [s for s in found
                         if _SYNC_FOR_CR.search(s) and re.search(r"\bfinish\b", s)]
                self.assertTrue(named, f"{name}: no sentence names `worktree-flow.py sync --cr "
                                       f"<cr>` as the step before `finish`")

    def test_no_rule_surface_forbids_sync(self):
        self.assertEqual(_forbids_sync([
            "worktree-flow sync and finish rebase, and never use sync.",
            "do not run worktree-flow.py sync on a main-tree branch.",
            "bring it level with worktree-flow.py sync --cr <cr> before finish.",
        ]), ["worktree-flow sync and finish rebase, and never use sync.",
             "do not run worktree-flow.py sync on a main-tree branch."])
        for name, found in self._each_surface():
            with self.subTest(surface=name):
                self.assertEqual(_forbids_sync(found), [])

    def test_no_rule_surface_merges_develop_into_a_worktree_branch_by_hand(self):
        self.assertEqual(_hand_worktree_merges([
            "resync = merge develop into your branch, in the worktree (git -c .worktrees/<cr>).",
            "bring the worktree up to develop (git -c .worktrees/<cr> merge develop --no-edit).",
            "resync with worktree-flow.py sync --cr <cr>, which merges develop into your branch.",
            "a cr on a feature branch in the main tree, with no worktree, merges develop in by "
            "hand: sync needs .worktrees/<cr>.",
            "merge develop into the feature branch until behind=0.",
        ]), ["resync = merge develop into your branch, in the worktree (git -c .worktrees/<cr>).",
             "bring the worktree up to develop (git -c .worktrees/<cr> merge develop --no-edit)."])
        for name, found in self._each_surface():
            with self.subTest(surface=name):
                self.assertEqual(_hand_worktree_merges(found), [])

    def test_every_catch_up_rule_names_sync_for_a_worktree_branch(self):
        # The detector bites on a resync rule that names no tool step, and spares the tool's
        # step, the main-tree case and the sync verb's own entry.
        self.assertEqual(_catch_ups_without_sync([
            "resync a stale branch by merging develop into it (not a long re-conflicting rebase).",
            "bring the branch level with develop before finish.",
            "resync a stale branch by merging develop into it: for a cr's worktree branch, "
            "worktree-flow.py sync --cr <cr>.",
            "a cr on a feature branch in the main tree, with no worktree, merges develop in by "
            "hand until behind=0.",
            "sync --cr <id> (merges develop into the cr's branch, never a rebase;",
            "any develop-level need → relay to mainline;",
        ]), ["resync a stale branch by merging develop into it (not a long re-conflicting rebase).",
             "bring the branch level with develop before finish."])
        for name, found in self._each_surface():
            with self.subTest(surface=name):
                self.assertEqual(_catch_ups_without_sync(found), [])

    def test_no_rule_surface_describes_worktree_flow_as_rebasing(self):
        for name, found in self._each_surface():
            with self.subTest(surface=name):
                self.assertEqual(_rebasing_descriptions(found), [])


# ---------------------------------------------------------------------------------------------
# §S5 / AC6: ``abort`` promises nothing it does not do, and ends with the board step the
# orchestrator takes next.
# ---------------------------------------------------------------------------------------------

#: The cause every ``abort`` fixture gives.
REASON = "dropped by the fixture"

#: A promise of a board write: abort records, marks or files something on Crucible's queue.
_BOARD_WRITE_CLAIM = re.compile(r"\brecord|crucible'?s queue|\bmark(?:s|ed)?\b", re.IGNORECASE)

#: The orchestrator's own board step, which may say what IT records.
_BOARD_STEP = re.compile(r"\bcr-(?:void|supersede)\b")


def _board_write_claims(chunks) -> list:
    """The chunks claiming that ``abort`` writes to the board -- every chunk naming a board-write
    word and no ``cr-void`` / ``cr-supersede`` step."""
    return [c for c in chunks if _BOARD_WRITE_CLAIM.search(c) and not _BOARD_STEP.search(c)]


def _help_entries(text: str) -> list:
    """argparse help split into entries: an option line with its wrapped continuation lines
    joined, every other paragraph likewise."""
    entries, current = [], []
    for line in text.splitlines():
        if not line.strip() or re.match(r"\s{0,4}-", line):
            if current:
                entries.append(re.sub(r"\s+", " ", " ".join(current)))
            current = []
        if line.strip():
            current.append(line.strip())
    if current:
        entries.append(re.sub(r"\s+", " ", " ".join(current)))
    return entries


def _last_line(text: str) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


class AbortBoardStepTest(_WorktreeFlowPathCase):
    """AC6 / §S5: ``abort`` claims no board write; each ``--cr`` run that reaches its end closes
    with ``cr-void --cr <cr> --reason "<reason>"``, or with ``--superseded``
    ``cr-supersede --cr <cr> --by <successor>`` and the reason as the cause."""

    VOID = f'cr-void --cr {CR} --reason "{REASON}"'
    SUPERSEDE = f"cr-supersede --cr {CR} --by <successor>"

    def _abort(self, *extra):
        return self._wf("abort", "--cr", CR, "--reason", REASON, *extra)

    def _assert_ends_with_void(self, result):
        self.assertEqual(result.returncode, 0, self._output(result))
        self.assertIn(self.VOID, _last_line(result.stdout), self._output(result))
        self.assertNotIn("cr-supersede", result.stdout + result.stderr)
        self.assertEqual(_board_write_claims((result.stdout + result.stderr).splitlines()), [])

    def test_abort_help_promises_no_board_write(self):
        # The detector bites on a board-write promise and spares the orchestrator's step.
        self.assertEqual(_board_write_claims([
            f"[dry-run] record {CR} → ABORTED on the CR in Crucible's queue  ({REASON})",
            "--superseded  Mark SUPERSEDED (replaced by another CR)",
            f"abort: removed worktree {CR}",
            f'next: python-crucible.py cr-void --cr {CR} --reason "{REASON}" records the drop',
        ]), [f"[dry-run] record {CR} → ABORTED on the CR in Crucible's queue  ({REASON})",
             "--superseded  Mark SUPERSEDED (replaced by another CR)"])
        self.assertEqual(_help_entries("usage: x\n\noptions:\n  --reason REASON  why\n"
                                       "                   it was dropped\n  -h, --help  help\n"),
                         ["usage: x", "options:", "--reason REASON why it was dropped",
                          "-h, --help help"])

        result = self._run("abort", "-h")

        self.assertEqual(result.returncode, 0, self._output(result))
        entries = _help_entries(result.stdout)
        self.assertTrue([e for e in entries if e.startswith("--reason")], result.stdout)
        self.assertTrue([e for e in entries if e.startswith("--superseded")], result.stdout)
        self.assertEqual(_board_write_claims(entries), [])

    def test_abort_dry_run_ends_with_the_cr_void_step_and_changes_nothing(self):
        self._add_worktree()
        own = self._branch_commit("a.txt", "a\n", "feat(core): GREEN — own")

        result = self._abort("--dry-run")

        self._assert_ends_with_void(result)
        self.assertTrue(self.wt.is_dir(), "a dry run removes nothing")
        self.assertEqual(self._head(BRANCH), own)

    def test_abort_removal_ends_with_the_cr_void_step(self):
        self._add_worktree()
        own = self._branch_commit("a.txt", "a\n", "feat(core): GREEN — own")

        result = self._abort()

        self._assert_ends_with_void(result)
        self.assertFalse(self.wt.exists(), "the worktree is removed")
        self.assertEqual(self._head(BRANCH), own, "the branch is kept without --delete-branch")

    def test_abort_with_no_worktree_ends_with_the_cr_void_step(self):
        result = self._abort()

        self._assert_ends_with_void(result)
        self.assertFalse(self.wt.exists())

    def test_abort_superseded_ends_with_the_cr_supersede_step_giving_the_reason_as_the_cause(self):
        self._add_worktree()
        self._branch_commit("a.txt", "a\n", "feat(core): GREEN — own")

        result = self._abort("--superseded")

        self.assertEqual(result.returncode, 0, self._output(result))
        self.assertIn(self.SUPERSEDE, _last_line(result.stdout), self._output(result))
        self.assertIn(REASON, result.stdout, "the reason is given as the cause")
        self.assertNotIn("cr-void", result.stdout + result.stderr)
        self.assertEqual(_board_write_claims((result.stdout + result.stderr).splitlines()), [])
        self.assertFalse(self.wt.exists())

    def test_abort_without_reason_is_refused_without_promising_a_board_write(self):
        self._add_worktree()

        result = self._wf("abort", "--cr", CR)

        self.assertEqual(result.returncode, 1, self._output(result))
        self.assertTrue(result.stderr.startswith("[worktree-flow] ERROR: "), self._output(result))
        self.assertIn("--reason", result.stderr)
        self.assertEqual(_board_write_claims(result.stderr.splitlines()), [])
        self.assertEqual(result.stdout, "")
        self.assertTrue(self.wt.is_dir(), "a refused abort removes nothing")

    def test_abort_delete_branch_with_no_worktree_deletes_the_existing_branch(self):
        self._add_worktree()
        self._branch_commit("a.txt", "a\n", "feat(core): GREEN — unmerged own")
        repo_git(self.repo, "worktree", "remove", self.wt)
        self.assertTrue(self._branch_exists(BRANCH), "fixture: the branch outlives its worktree")
        develop_before = self._head(DEVELOP)

        result = self._abort("--delete-branch")

        self._assert_ends_with_void(result)
        self.assertFalse(self._branch_exists(BRANCH), "the existing branch is deleted")
        self.assertEqual(self._head(DEVELOP), develop_before, "develop is untouched")


#: A second branch of the fixture CR, and a branch of another CR sharing its id as a prefix.
SLUG_BRANCH = f"{BRANCH}-slug"
OTHER_CR_BRANCH = f"{BRANCH}0"


class AbortPathTest(_WorktreeFlowPathCase):
    """§S8 / AC10: ``abort``'s paths -- each refusal, ``--force`` on a dirty worktree,
    ``--delete-branch`` with a worktree and the branch kept without it, no worktree and its dry
    run, ``--release-lock`` real and dry, ``--dry-run`` with a worktree, and ``--delete-branch``
    with no worktree refused when more than one branch is the CR's."""

    VOID = f'abort: next, the orchestrator\'s board step: cr-void --cr {CR} --reason "{REASON}"'

    def _abort(self, *extra):
        return self._wf("abort", "--cr", CR, "--reason", REASON, *extra)

    def _started(self) -> str:
        """The CR's worktree with one own commit and a track label; returns the commit."""
        self._add_worktree()
        repo_git(self.repo, "config", f"wf.track.{CR}", TRACK)
        return self._branch_commit("a.txt", "a\n", "feat(core): GREEN — own")

    def _dirty(self):
        write_files(self.wt, {"a.txt": "edited, uncommitted\n", "new.txt": "untracked\n"})

    def _removals_and_deletes(self) -> list:
        """The git calls a run made that remove a worktree or delete a branch."""
        return [c["argv"] for c in self._git_calls()
                if c["argv"][:2] == ["worktree", "remove"] or c["argv"][:2] == ["branch", "-D"]]

    def _listed_worktrees(self) -> list:
        out = repo_git(self.repo, "worktree", "list", "--porcelain")
        return [os.path.realpath(line[len("worktree "):]) for line in out.splitlines()
                if line.startswith("worktree ")]

    def _assert_refused(self, result, stderr: str):
        self.assertEqual(result.returncode, 1, self._output(result))
        self.assertEqual(result.stderr, stderr, self._output(result))
        self.assertEqual(result.stdout, "", "a refusal prints no board step")
        self.assertEqual(self._removals_and_deletes(), [], "a refusal removes nothing")

    # ------------------------------------------------------------------ refusals ----

    def test_abort_without_cr_or_release_lock_is_refused_naming_both(self):
        own = self._started()

        result = self._wf("abort", "--reason", REASON, "--delete-branch")

        self._assert_refused(result, "[worktree-flow] ERROR: abort needs --cr (or --release-lock).\n")
        self.assertTrue(self.wt.is_dir())
        self.assertEqual(self._head(BRANCH), own)
        self.assertEqual(self._config(f"wf.track.{CR}"), TRACK)

    def test_abort_of_a_dirty_worktree_without_force_is_refused_and_keeps_the_changes(self):
        own = self._started()
        self._dirty()

        result = self._abort("--delete-branch")

        self._assert_refused(result, (
            f"[worktree-flow] ERROR: {self.wt} has uncommitted changes. RECOVER first — commit the "
            f"work worth keeping onto the branch (it is KEPT as the recovery point unless "
            f"--delete-branch) or stash it, then re-run. --force discards.\n"))
        self.assertEqual((self.wt / "a.txt").read_text(encoding="utf-8"), "edited, uncommitted\n")
        self.assertEqual((self.wt / "new.txt").read_text(encoding="utf-8"), "untracked\n")
        self.assertEqual(self._head(BRANCH), own, "the branch is kept")
        self.assertEqual(self._config(f"wf.track.{CR}"), TRACK, "the track label is kept")

    def test_abort_dry_run_of_a_dirty_worktree_without_force_is_refused_too(self):
        self._started()
        self._dirty()

        result = self._abort("--dry-run")

        self.assertEqual(result.returncode, 1, self._output(result))
        self.assertTrue(result.stderr.startswith(
            f"[worktree-flow] ERROR: {self.wt} has uncommitted changes."), self._output(result))
        self.assertEqual(result.stdout, "")
        self.assertTrue(self.wt.is_dir())

    # ------------------------------------------------------------------ --force ----

    def test_abort_force_removes_a_dirty_worktree_and_keeps_the_branch(self):
        own = self._started()
        self._dirty()

        result = self._abort("--force")

        self.assertEqual(result.returncode, 0, self._output(result))
        self.assertEqual(self._removals_and_deletes(),
                         [["worktree", "remove", str(self.wt), "--force"]])
        self.assertFalse(self.wt.exists(), "the dirty worktree is removed")
        self.assertNotIn(os.path.realpath(self.wt), self._listed_worktrees())
        self.assertEqual(self._head(BRANCH), own, "the branch is kept without --delete-branch")
        self.assertEqual(result.stdout.splitlines(), [
            f"abort: removed worktree {self.wt}",
            "  → exit the worktree: modelb_worktree_exit",
            f"abort: branch {BRANCH} kept (delete with: git -C {self.repo} branch -D {BRANCH})",
            self.VOID,
        ])
        self.assertIsNone(self._config(f"wf.track.{CR}"), "the track label is unset")

    # ------------------------------------------------------------------ --delete-branch ----

    def test_abort_delete_branch_with_a_worktree_removes_it_and_deletes_the_branch(self):
        self._started()
        develop_before = self._head(DEVELOP)

        result = self._abort("--delete-branch")

        self.assertEqual(result.returncode, 0, self._output(result))
        self.assertEqual(self._removals_and_deletes(),
                         [["worktree", "remove", str(self.wt)], ["branch", "-D", BRANCH]])
        self.assertFalse(self.wt.exists())
        self.assertFalse(self._branch_exists(BRANCH), "the unmerged branch is deleted")
        self.assertEqual(self._head(DEVELOP), develop_before, "develop is untouched")
        self.assertEqual(result.stdout.splitlines(), [
            f"abort: removed worktree {self.wt}",
            "  → exit the worktree: modelb_worktree_exit",
            f"abort: deleted branch {BRANCH}",
            self.VOID,
        ])
        self.assertNotIn("kept", result.stdout)
        self.assertIsNone(self._config(f"wf.track.{CR}"))

    def test_abort_without_delete_branch_keeps_the_branch_and_names_its_delete_command(self):
        own = self._started()

        result = self._abort()

        self.assertEqual(result.returncode, 0, self._output(result))
        self.assertEqual(self._removals_and_deletes(), [["worktree", "remove", str(self.wt)]])
        self.assertFalse(self.wt.exists())
        self.assertEqual(self._head(BRANCH), own, "the branch is kept at its own commit")
        self.assertIn(
            f"abort: branch {BRANCH} kept (delete with: git -C {self.repo} branch -D {BRANCH})",
            result.stdout.splitlines())
        self.assertNotIn("deleted branch", result.stdout)

    # ------------------------------------------------------------------ no worktree ----

    def test_abort_with_no_worktree_reports_it_and_touches_no_branch(self):
        repo_git(self.repo, "branch", BRANCH, DEVELOP)
        repo_git(self.repo, "config", f"wf.track.{CR}", TRACK)

        result = self._abort()

        self.assertEqual(result.returncode, 0, self._output(result))
        self.assertEqual(result.stdout.splitlines(), [
            f"abort: no live worktree for {CR} (never started or already removed)",
            self.VOID,
        ])
        self.assertEqual(result.stderr, "")
        self.assertEqual(self._removals_and_deletes(), [])
        self.assertTrue(self._branch_exists(BRANCH), "no --delete-branch, no branch deleted")
        self.assertFalse(self.wt.exists())
        self.assertIsNone(self._config(f"wf.track.{CR}"), "the track label is unset")

    def test_abort_dry_run_with_no_worktree_prints_the_plan_and_changes_nothing(self):
        repo_git(self.repo, "branch", BRANCH, DEVELOP)
        repo_git(self.repo, "config", f"wf.track.{CR}", TRACK)

        result = self._abort("--dry-run", "--delete-branch")

        self.assertEqual(result.returncode, 0, self._output(result))
        self.assertEqual(result.stdout.splitlines(), [
            f"[dry-run] no worktree for {CR}",
            f"[dry-run] git -C {self.repo} branch -D {BRANCH}",
            self.VOID,
        ])
        self.assertEqual(self._removals_and_deletes(), [])
        self.assertTrue(self._branch_exists(BRANCH), "a dry run deletes nothing")
        self.assertEqual(self._config(f"wf.track.{CR}"), TRACK, "a dry run unsets nothing")

    # ------------------------------------------------------------------ --release-lock ----

    def test_abort_release_lock_removes_the_lock_and_prints_no_board_step(self):
        own = self._started()
        self._lock().write_text(OTHER_LOCK + "\n", encoding="utf-8")

        result = self._wf("abort", "--release-lock", "--cr", CR, "--reason", REASON)

        self.assertEqual(result.returncode, 0, self._output(result))
        self.assertEqual(result.stdout, f"abort: released merge lock [{OTHER_LOCK}]\n")
        self.assertEqual(result.stderr, "")
        self.assertFalse(self._lock().exists(), "the lock file is removed")
        self.assertEqual(self._removals_and_deletes(), [], "--release-lock aborts no CR")
        self.assertTrue(self.wt.is_dir())
        self.assertEqual(self._head(BRANCH), own)
        self.assertEqual(self._config(f"wf.track.{CR}"), TRACK)

    def test_abort_release_lock_needs_no_cr_or_reason(self):
        self._lock().write_text(OTHER_LOCK + "\n", encoding="utf-8")

        result = self._wf("abort", "--release-lock")

        self.assertEqual(result.returncode, 0, self._output(result))
        self.assertEqual(result.stdout, f"abort: released merge lock [{OTHER_LOCK}]\n")
        self.assertFalse(self._lock().exists())

    def test_abort_release_lock_dry_run_names_the_holder_and_leaves_the_lock(self):
        self._lock().write_text(OTHER_LOCK + "\n", encoding="utf-8")

        result = self._wf("abort", "--release-lock", "--dry-run")

        self.assertEqual(result.returncode, 0, self._output(result))
        self.assertEqual(result.stdout, f"[dry-run] would release merge lock [{OTHER_LOCK}]\n")
        self.assertEqual(result.stderr, "")
        self.assertEqual(self._lock().read_text(encoding="utf-8"), OTHER_LOCK + "\n",
                         "a dry run leaves the lock as it was")

    def test_abort_release_lock_with_no_lock_held_says_so_and_never_prints_none(self):
        for flags in ((), ("--dry-run",)):
            with self.subTest(flags=flags):
                self.assertFalse(self._lock().exists(), "fixture: no merge lock is held")

                result = self._wf("abort", "--release-lock", *flags)

                output = result.stdout + result.stderr
                self.assertEqual(result.returncode, 0, self._output(result))
                self.assertRegex(output, NO_LOCK_HELD, self._output(result))
                self.assertNotIn("None", output, self._output(result))
                self.assertNotIn("released merge lock", output, self._output(result))
                self.assertFalse(self._lock().exists(), "no lock file is created")

    # ------------------------------------------------------------------ --dry-run ----

    def test_abort_dry_run_with_a_worktree_prints_the_commands_and_removes_nothing(self):
        own = self._started()

        result = self._abort("--dry-run", "--delete-branch")

        self.assertEqual(result.returncode, 0, self._output(result))
        self.assertEqual(result.stdout.splitlines(), [
            f"[dry-run] git -C {self.repo} worktree remove {self.wt}",
            f"[dry-run] git -C {self.repo} branch -D {BRANCH}",
            self.VOID,
        ])
        self.assertEqual(self._removals_and_deletes(), [])
        self.assertNotIn(["worktree", "prune"], [c["argv"] for c in self._git_calls()])
        self.assertTrue(self.wt.is_dir(), "a dry run removes no worktree")
        self.assertIn(os.path.realpath(self.wt), self._listed_worktrees())
        self.assertEqual(self._head(BRANCH), own, "a dry run deletes no branch")
        self.assertEqual(self._config(f"wf.track.{CR}"), TRACK, "a dry run unsets nothing")

    def test_abort_dry_run_with_force_prints_the_forced_removal(self):
        self._started()
        self._dirty()

        result = self._abort("--dry-run", "--force")

        self.assertEqual(result.returncode, 0, self._output(result))
        self.assertEqual(result.stdout.splitlines(), [
            f"[dry-run] git -C {self.repo} worktree remove {self.wt} --force",
            self.VOID,
        ])
        self.assertEqual((self.wt / "new.txt").read_text(encoding="utf-8"), "untracked\n")

    # ------------------------------------------------------------------ several branches ----

    def test_abort_delete_branch_with_no_worktree_and_two_cr_branches_is_refused_naming_them(self):
        repo_git(self.repo, "branch", BRANCH, DEVELOP)
        repo_git(self.repo, "branch", SLUG_BRANCH, DEVELOP)

        result = self._abort("--delete-branch")

        self._assert_refused(result, (
            f"[worktree-flow] ERROR: more than one branch for {CR} ({BRANCH}, {SLUG_BRANCH}) — "
            f"delete the one you mean with git branch -D.\n"))
        self.assertTrue(self._branch_exists(BRANCH))
        self.assertTrue(self._branch_exists(SLUG_BRANCH))

    def test_abort_dry_run_delete_branch_with_two_cr_branches_is_refused_too(self):
        repo_git(self.repo, "branch", BRANCH, DEVELOP)
        repo_git(self.repo, "branch", SLUG_BRANCH, DEVELOP)

        result = self._abort("--delete-branch", "--dry-run")

        self._assert_refused(result, (
            f"[worktree-flow] ERROR: more than one branch for {CR} ({BRANCH}, {SLUG_BRANCH}) — "
            f"delete the one you mean with git branch -D.\n"))

    def test_abort_delete_branch_with_no_worktree_counts_only_the_crs_own_branches(self):
        repo_git(self.repo, "branch", SLUG_BRANCH, DEVELOP)
        repo_git(self.repo, "branch", OTHER_CR_BRANCH, DEVELOP)

        result = self._abort("--delete-branch")

        self.assertEqual(result.returncode, 0, self._output(result))
        self.assertEqual(self._removals_and_deletes(), [["branch", "-D", SLUG_BRANCH]])
        self.assertFalse(self._branch_exists(SLUG_BRANCH), "the CR's slugged branch is deleted")
        self.assertTrue(self._branch_exists(OTHER_CR_BRANCH), "another CR's branch is kept")
        self.assertEqual(result.stdout.splitlines(), [
            f"abort: no live worktree for {CR} (never started or already removed)",
            f"abort: deleted branch {SLUG_BRANCH}",
            self.VOID,
        ])


# ---------------------------------------------------------------------------------------------
# §S6 / AC7: the scheduler-note board is gone.
# ---------------------------------------------------------------------------------------------

#: The notes a request directory holds in the fixture.
REQUEST_NOTE = "reschedule-request-x.md"
DIRECTIVE_NOTE = "directive-y.md"


class NoSchedulerNoteBoardTest(_WorktreeFlowPathCase):
    """AC7 / §S6: no ``$WF_REQUEST_DIR``, no ``reschedule-request``; ``status`` lists no note and
    is otherwise unchanged."""

    def setUp(self):
        super().setUp()
        self._add_worktree()
        self._branch_commit("a.txt", "a\n", "feat(core): GREEN — own")
        self.request_dir = write_files(self.work / "requests", {
            REQUEST_NOTE: "---\ndescription: please reschedule CR-TST-001\n---\n",
            DIRECTIVE_NOTE: "---\ndescription: start CR-TST-002\n---\n",
        })

    def _assert_names_no_note(self, result):
        self.assertEqual(result.returncode, 0, self._output(result))
        for text in (result.stdout, result.stderr):
            for needle in (REQUEST_NOTE, DIRECTIVE_NOTE, "reschedule", "scheduler inbox"):
                self.assertNotIn(needle, text, self._output(result))

    def test_worktree_flow_names_neither_the_request_dir_nor_a_reschedule_request(self):
        source = (TOOL_SCRIPTS_DIR / WORKTREE_FLOW).read_text(encoding="utf-8")
        self.assertEqual([n for n in ("WF_REQUEST_DIR", "reschedule-request") if n in source], [])

    def test_status_names_no_note_from_wf_request_dir_and_is_otherwise_unchanged(self):
        plain = self._wf("status")
        with_dir = self._wf("status", env={"WF_REQUEST_DIR": str(self.request_dir)})

        self._assert_names_no_note(with_dir)
        self.assertEqual((with_dir.stdout, with_dir.stderr), (plain.stdout, plain.stderr),
                         "$WF_REQUEST_DIR changes neither the envelope nor the human board")

    def test_status_reads_no_note_directory_from_the_projects_env_file(self):
        write_files(self.repo, {".env": f"WF_REQUEST_DIR={self.request_dir}\n"})

        self._assert_names_no_note(self._wf("status"))

    def test_orchestration_track_names_no_reschedule_request(self):
        track = read_text(REPO_ROOT / RULE_SURFACES["orchestration-track.md"][0])
        self.assertIn("## Raise every approval/request to Mainline", track,
                      "the scan must read the track rules")
        self.assertEqual([line for line in track.splitlines() if "reschedule-request" in line], [])


if __name__ == "__main__":
    unittest.main()
