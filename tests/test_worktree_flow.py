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
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from tests._helpers import (
    TOOL_SCRIPTS_DIR,
    decode_envelope,
    git_commit_all,
    git_repo,
    repo_git,
    run_tool,
    tool_bin_dir,
    use_private_tmpdir,
    write_files,
)

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

    def _wf(self, *args):
        return run_tool(WORKTREE_FLOW, *args, "--project-dir", self.repo,
                        bin_dir=self.bin_dir, cwd=self.cwd)

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


if __name__ == "__main__":
    unittest.main()
