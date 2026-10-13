"""The runner hooks, run for real on payloads — CR-MDB-062 §S2, §S3 and §S5.

Contract: ``docs/changes/CR-MDB-062-blocking-hooks-for-python-and-bun.md``. Every test runs the
REAL script under ``hooks-src/scripts/`` (``tests._helpers.run_hook``) on the neutral payload
(``tool_name`` ``bash``, ``tool_input.command``, ``cwd``) inside a temp project tree under
``/tmp`` (``tests._helpers.build_tree``). A verdict is exit 0 (allow) or exit 2 with
``{"decision": "block", …}`` on stdout; any traceback on stderr fails the test, because a
``closed`` hook that raises blocks every shell call.

What the module pins, for ``block-direct-cargo-test`` and ``block-direct-mvn-test`` (§S5):

- **Command positions (§S2):** every line start outside quotes and heredoc bodies; after ``&&``,
  ``||``, ``;``, ``|``, ``&`` and ``(``; past ``VAR=value``, ``env`` with any options and
  assignments, ``timeout`` with any options and a duration, ``nice [-n N]`` and ``time``. A heredoc
  body (``<<WORD``, ``<<'WORD'``, ``<<-WORD``) and a quoted argument are never a position, a
  separator inside them included.
- **Extras and allowed goals (§S5):** cargo blocks ``check``, ``clippy`` and a ``+toolchain``;
  mvn blocks ``mvnd`` and a launcher invoked by path, and allows ``package``, ``install`` and
  ``compile``.
- **The marker rule (§S3):** a marker in the ``cwd``, in a parent up to and including the git root
  (the nearest ancestor holding any ``.git`` entry, a directory or a file), or in a directory at
  most 3 levels below the git root. The walk below follows no symlink, skips hidden directories,
  ``node_modules``, ``.venv``, ``venv``, ``target``, ``dist`` and ``build``, and skips a directory
  it cannot read. Without a git root only the ``cwd`` and its parents count; an empty or missing
  ``cwd`` allows.
- **Fail-open behaviour kept:** the escape hatch, a non-``bash`` tool, an unreadable payload and an
  untokenisable command allow.

The block REASON (§S4) is pinned in ``tests/test_client_path_anchoring.py``, beside the reason
checks it extends. Each class is a per-hook binding of a mixin, so one more runner hook is one
more binding.

Stdlib only.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import TYPE_CHECKING

from tests._helpers import build_tree, run_hook

#: The two hooks §S5 aligns: the script, its stack's markers (§S3's table, primary first) and
#: the plain runner command each blocks.
RUNNER_HOOKS = {
    "cargo": {"script": "block-direct-cargo-test", "markers": ("Cargo.toml",),
              "run": "cargo test"},
    "mvn": {"script": "block-direct-mvn-test",
            "markers": ("pom.xml", "build.gradle", "build.gradle.kts"), "run": "mvn test"},
}

#: §S2 — commands that put ``{run}`` at a command position (a block).
BLOCKED_POSITIONS = (
    "{run}",
    "cd sub && {run}",
    "false || {run}",
    "echo hi; {run}",
    "echo hi | {run}",
    "echo hi & {run}",
    "({run})",
    "(cd sub && {run})",
    "FOO=1 {run}",
    # a later line
    "echo hi\n{run}",
    "echo hi\n\n  {run}",
    'echo "a\nb"\n{run}',
    "cat <<EOF\nnotes\nEOF\n{run}",
    "git commit -F - <<'EOF'\nfix: tidy\nEOF\n{run}",
    # wrappers
    "env {run}",
    "env -i HOME=/tmp/h {run}",
    "env -u HOME FOO=1 {run}",
    "env --unset=FOO -i {run}",
    "env - PATH=/usr/bin {run}",
    "env -- {run}",
    "timeout 60 {run}",
    "timeout -k 5 60 {run}",
    "timeout --signal=KILL 10m {run}",
    "timeout -s KILL --preserve-status 60 {run}",
    "nice {run}",
    "nice -n 10 {run}",
    "time {run}",
    "env FOO=1 timeout 60 nice -n 5 time {run}",
    "echo hi && env FOO=1 {run}",
    "(timeout 60 {run})",
    "echo hi\nnice -n 10 {run}",
)

#: §S2 — commands where ``{run}`` sits only in a heredoc body or a quoted argument (an allow).
ALLOWED_MENTIONS = (
    "echo {run}",
    "git commit -m 'make {run} pass'",
    'git commit -m "fix; {run}"',
    'git commit -m "fix && {run} || true"',
    'git commit -m "subject\n\n{run} now passes"',
    "git commit -F - <<'EOF'\nfix: {run}\n{run}\nEOF",
    "git commit -F - <<'EOF'\nfix: make it pass; {run}\nEOF",
    "cat > f.md <<EOF\n{run}\nEOF",
    "cat > f.md <<EOF\nstep one && {run}\nEOF",
    "cat <<-EOF\n\t{run}\n\tEOF",
    "cat <<-EOF\n\tx | {run}\n\tEOF",
    'cat <<"EOF" > notes.md\n({run})\nEOF',
)


class _RunnerHookCase(unittest.TestCase):
    """One runner hook (``HOOK``, a ``RUNNER_HOOKS`` key) run on payloads in temp trees."""

    HOOK = ""

    def setUp(self):
        self.spec = RUNNER_HOOKS[self.HOOK]
        self.marker = self.spec["markers"][0]
        self.run_cmd = self.spec["run"]
        self.tmp = Path(tempfile.mkdtemp(prefix="modelb-runner-hook-", dir="/tmp"))
        self.locked = []
        # A tree's meaning depends on what sits above it: nothing above /tmp may hold a git entry
        # or one of this stack's markers, or "no git root" and "above the git root" would lie.
        for parent in self.tmp.parents:
            for entry in (".git", *self.spec["markers"]):
                self.assertFalse((parent / entry).exists(),
                                 f"precondition: {parent / entry} exists above the temp tree")

    def tearDown(self):
        for path in self.locked:
            path.chmod(0o755)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def lock(self, path):
        """chmod 000 ``path`` (restored in tearDown)."""
        self.locked.append(path)
        path.chmod(0o000)

    def verdict(self, payload, proc_cwd=None):
        """``"block"`` or ``"allow"`` from the real hook on ``payload``; a traceback, another exit
        code or a malformed block fails the test."""
        res = run_hook(self.spec["script"], payload, cwd=proc_cwd)
        self.assertNotIn("Traceback", res.stderr, f"{self.HOOK}: the hook raised:\n{res.stderr}")
        if res.returncode == 0:
            return "allow"
        self.assertEqual(res.returncode, 2, f"{self.HOOK}: exit {res.returncode}: {res.stderr}")
        self.assertEqual(json.loads(res.stdout).get("decision"), "block", res.stdout)
        return "block"

    def bash(self, command, cwd):
        return {"tool_name": "bash", "tool_input": {"command": command}, "cwd": str(cwd)}

    def assertVerdict(self, expected, command, cwd, why=""):
        got = self.verdict(self.bash(command, cwd))
        self.assertEqual(got, expected,
                         f"{self.spec['script']}: {command!r} in {cwd} {why}— want {expected}")

    def project(self, name="proj"):
        """A temp project holding the hook's primary marker in its root, no git entry."""
        return build_tree(self.tmp / name, [self.marker])


#: The base a mixin below declares to a type checker; at run time a mixin is a plain ``object``,
#: so unittest never collects it unbound to a hook.
_MixinBase = _RunnerHookCase if TYPE_CHECKING else object


# ----------------------------------------------------------------- §S2 positions ----

class _CommandPositions(_MixinBase):
    def test_blocks_the_runner_at_every_command_position_and_under_every_wrapper(self):
        project = self.project()
        for form in BLOCKED_POSITIONS:
            command = form.format(run=self.run_cmd)
            with self.subTest(command=command):
                self.assertVerdict("block", command, project)

    def test_allows_the_runner_inside_a_heredoc_body_or_a_quoted_argument(self):
        project = self.project()
        for form in ALLOWED_MENTIONS:
            command = form.format(run=self.run_cmd)
            with self.subTest(command=command):
                self.assertVerdict("allow", command, project)

    def test_a_line_after_a_heredoc_body_or_a_multi_line_quote_is_a_command_position(self):
        project = self.project()
        for command in (f"git commit -F - <<'EOF'\n{self.run_cmd}\nEOF\n{self.run_cmd}",
                        f'git commit -m "a\n{self.run_cmd}"\n{self.run_cmd}'):
            with self.subTest(command=command):
                self.assertVerdict("block", command, project)


class CargoHookCommandPositionTest(_CommandPositions, _RunnerHookCase):
    HOOK = "cargo"


class MvnHookCommandPositionTest(_CommandPositions, _RunnerHookCase):
    HOOK = "mvn"


# ----------------------------------------------------------------- §S5 extras -------

class CargoHookExtrasTest(_RunnerHookCase):
    HOOK = "cargo"

    def test_blocks_check_clippy_and_a_toolchain_selector(self):
        project = self.project()
        for command in ("cargo check", "cargo clippy -- -D warnings", "cargo +nightly test",
                        "cargo +stable clippy", "cargo nextest run", "cargo llvm-cov --lcov",
                        "cargo test -p fixture", "echo hi\ncargo +nightly check",
                        "nice -n 5 cargo clippy", "timeout 60 cargo +nightly nextest run"):
            with self.subTest(command=command):
                self.assertVerdict("block", command, project)

    def test_allows_cargo_verbs_that_run_no_tests(self):
        project = self.project()
        for command in ("cargo build", "cargo run --bin x", "cargo fmt", "cargo +nightly build",
                        "cargo doc", "env FOO=1 cargo build", "cargo build\necho test"):
            with self.subTest(command=command):
                self.assertVerdict("allow", command, project)


class MvnHookExtrasTest(_RunnerHookCase):
    HOOK = "mvn"

    def test_blocks_mvnd_a_path_launcher_and_every_test_goal(self):
        project = self.project()
        for command in ("mvnd test", "mvnw verify", "./mvnw verify", "/usr/bin/mvn test",
                        "tools/maven/bin/mvn integration-test", "mvn -q test-compile",
                        "mvn surefire:test", "mvn failsafe:integration-test",
                        "mvn clean verify -pl runtime", "timeout 600 ./mvnw verify",
                        "echo hi\nmvnd test", "env -i HOME=/tmp/h /usr/bin/mvn test"):
            with self.subTest(command=command):
                self.assertVerdict("block", command, project)

    def test_allows_package_install_and_compile(self):
        project = self.project()
        for command in ("mvn package", "mvn install", "mvn compile",
                        "mvn clean install -DskipTests", "./mvnw package", "mvnd compile",
                        "env FOO=1 mvn package", "time ./mvnw install"):
            with self.subTest(command=command):
                self.assertVerdict("allow", command, project)

    def test_a_goal_on_a_later_line_is_not_the_launchers_argument(self):
        # A line break ends the command (§S2): ``test`` on the next line is no Maven goal.
        project = self.project()
        for command in ("mvn package\necho test", "mvn install\ngit commit -m verify"):
            with self.subTest(command=command):
                self.assertVerdict("allow", command, project)


# ----------------------------------------------------------------- §S3 markers ------

class _MarkerRule(_MixinBase):
    """Each case runs the hook's plain runner from a ``cwd`` in a tree under ``self.tmp``."""

    def _tree(self, files, git, name="repo"):
        return build_tree(self.tmp / name, [f.format(m=self.marker) for f in files], git=git)

    def _check(self, expected, root, cwd_rel, why):
        cwd = root / cwd_rel
        cwd.mkdir(parents=True, exist_ok=True)
        self.assertVerdict(expected, self.run_cmd, cwd, why)

    def test_blocks_when_the_marker_is_in_the_cwd(self):
        for git in (None, "dir", "file"):
            with self.subTest(git=git):
                root = self._tree(["{m}"], git, name=f"cwd-{git}")
                self._check("block", root, ".", "(marker in the cwd)")

    def test_blocks_when_the_marker_is_in_a_parent_up_to_the_git_root(self):
        for git in ("dir", "file"):
            with self.subTest(git=git):
                root = self._tree(["{m}"], git, name=f"root-{git}")
                self._check("block", root, "a/b", "(marker at the git root)")
                root = self._tree(["svc/{m}"], git, name=f"mid-{git}")
                self._check("block", root, "svc/src/main/java", "(marker between cwd and root)")

    def test_blocks_when_the_marker_is_one_two_or_three_levels_below_the_git_root(self):
        for git in ("dir", "file"):
            for rel in ("a/{m}", "crates/core/{m}", "a/b/c/{m}"):
                with self.subTest(git=git, marker=rel):
                    root = self._tree([rel, "README.md"], git, name=f"below-{git}-{rel.count('/')}")
                    self._check("block", root, ".", f"(marker at {rel} below the git root)")

    def test_blocks_when_the_marker_is_below_the_git_root_off_the_cwds_path(self):
        for git in ("dir", "file"):
            with self.subTest(git=git):
                root = self._tree(["services/api/{m}", "docs/README.md"], git, name=f"off-{git}")
                self._check("block", root, "docs", "(cwd in a sibling of the marker's directory)")
                self._check("block", root, "docs/a/b/c/d", "(cwd 5 levels deep, marker elsewhere)")

    def test_blocks_in_the_sandesh_layout_run_from_the_root(self):
        # Sandesh: pyproject.toml at the root, its bun package in integrations/pi/; this stack's
        # marker only in a sub-directory; the shell call runs from the session root.
        for git in ("dir", "file"):
            with self.subTest(git=git):
                root = self._tree(["pyproject.toml", "integrations/pi/package.json",
                                   "integrations/native/{m}"], git, name=f"sandesh-{git}")
                self._check("block", root, ".", "(Sandesh layout, marker in a sub-directory)")

    def test_allows_the_sandesh_layout_without_this_stacks_marker(self):
        root = self._tree(["pyproject.toml", "integrations/pi/package.json"], "dir")
        self._check("allow", root, ".", "(no marker of this stack)")

    def test_allows_when_the_only_marker_is_four_or_more_levels_below_off_the_cwds_path(self):
        for git in ("dir", "file"):
            with self.subTest(git=git):
                root = self._tree(["a/b/c/d/{m}", "a/b/c/e/f/{m}"], git, name=f"deep-{git}")
                self._check("allow", root, ".", "(markers 4 and 5 levels deep)")
                self._check("allow", root, "x", "(cwd in a sibling, markers 4+ levels deep)")
                self._check("allow", root, "a/b", "(cwd on the way, marker 2 below the cwd)")

    def test_blocks_a_deep_marker_on_the_cwds_own_path(self):
        root = self._tree(["a/b/c/d/{m}"], "dir")
        self._check("block", root, "a/b/c/d", "(the deep marker is in the cwd)")
        self._check("block", root, "a/b/c/d/e/f", "(the deep marker is in a parent)")

    def test_allows_when_the_only_marker_sits_in_a_skipped_directory(self):
        for skipped in (".hidden", ".github", "node_modules", ".venv", "venv", "target", "dist",
                        "build"):
            for rel in (f"{skipped}/{{m}}", f"pkg/{skipped}/{{m}}", f"pkg/{skipped}/sub/{{m}}"):
                with self.subTest(marker=rel):
                    name = f"skip-{skipped.strip('.')}-{rel.count('/')}"
                    root = self._tree([rel], "dir", name=name)
                    self._check("allow", root, ".", f"(the only marker is at {rel})")

    def test_allows_when_the_only_marker_sits_behind_a_symlink(self):
        outside = build_tree(self.tmp / "outside", [self.marker])
        root = self._tree(["a/b/c/d/{m}", "src/"], "dir")
        (root / "vendor").symlink_to(outside, target_is_directory=True)
        (root / "shortcut").symlink_to(root / "a" / "b" / "c" / "d", target_is_directory=True)
        (root / "src" / "linked").symlink_to(outside, target_is_directory=True)
        self._check("allow", root, ".", "(markers only through directory symlinks)")

    def test_allows_when_no_marker_exists(self):
        for git in (None, "dir", "file"):
            with self.subTest(git=git):
                root = self._tree(["README.md", "src/main.c", "docs/a/b/notes.md"], git,
                                  name=f"none-{git}")
                self._check("allow", root, ".", "(no marker anywhere)")
                self._check("allow", root, "docs/a", "(no marker anywhere)")

    def test_allows_when_the_only_marker_is_above_the_git_root(self):
        # The parents count up to and INCLUDING the git root, never past it: a submodule
        # (a ``.git`` file) inside a project of this stack is its own root.
        for git in ("dir", "file"):
            with self.subTest(git=git):
                outer = build_tree(self.tmp / f"outer-{git}", [self.marker, "other/"], git="dir")
                root = self._tree(["src/lib.txt"], git, name=f"outer-{git}/sub")
                self._check("allow", root, ".", "(marker only above the git root)")
                self._check("allow", root, "src", "(marker only above the git root)")
                self.assertTrue((outer / self.marker).is_file())

    def test_without_a_git_root_only_the_cwd_and_its_parents_count(self):
        root = self._tree(["{m}"], None, name="nogit-parent")
        self._check("block", root, "x/y", "(no git root, marker in a parent)")
        root = self._tree(["sub/{m}", "pkg/a/{m}"], None, name="nogit-below")
        self._check("allow", root, ".", "(no git root, markers only below the cwd)")
        self._check("allow", root, "other", "(no git root, markers only in siblings)")

    def test_allows_on_an_empty_or_missing_cwd(self):
        # The hook process itself runs inside a project holding the marker, so a hook falling
        # back to its own working directory would block.
        project = self.project()
        payloads = {
            "empty cwd": {"tool_name": "bash", "tool_input": {"command": self.run_cmd}, "cwd": ""},
            "null cwd": {"tool_name": "bash", "tool_input": {"command": self.run_cmd},
                         "cwd": None},
            "no cwd": {"tool_name": "bash", "tool_input": {"command": self.run_cmd}},
        }
        for label, payload in payloads.items():
            with self.subTest(case=label):
                self.assertEqual(self.verdict(payload, proc_cwd=project), "allow", label)

    def test_allows_without_a_traceback_when_a_directory_in_the_walk_is_unreadable(self):
        root = self._tree(["locked/inner/", "locked/{m}", "README.md"], "dir")
        self.lock(root / "locked")
        self._check("allow", root, ".", "(the only marker is in an unreadable directory)")

    def test_an_unreadable_directory_does_not_stop_the_walk(self):
        root = self._tree(["aaa/inner/", "mmm/inner/", "zzz/{m}"], "dir")
        self.lock(root / "aaa")
        self.lock(root / "mmm" / "inner")
        self._check("block", root, ".", "(marker beside unreadable directories)")


class CargoHookMarkerRuleTest(_MarkerRule, _RunnerHookCase):
    HOOK = "cargo"


class MvnHookMarkerRuleTest(_MarkerRule, _RunnerHookCase):
    HOOK = "mvn"

    def test_each_gradle_marker_counts_like_pom_xml(self):
        for marker in ("build.gradle", "build.gradle.kts"):
            with self.subTest(marker=marker):
                root = build_tree(self.tmp / marker, ["app/" + marker], git="dir")
                self._check("block", root, ".", f"(app/{marker} below the git root)")
                self._check("block", root, "app/src", f"(app/{marker} in a parent)")


# ----------------------------------------------------------------- fail-open --------

class _FailOpen(_MixinBase):
    HATCH = ""
    CLIENT_RUN = ""

    def test_allows_under_the_escape_hatch(self):
        project = self.project()
        for command in (f"{self.HATCH}=1 {self.run_cmd}", f"{self.HATCH}=true {self.run_cmd}",
                        f"env {self.HATCH}=1 {self.run_cmd}",
                        f"echo hi\n{self.HATCH}=1 {self.run_cmd}"):
            with self.subTest(command=command):
                self.assertVerdict("allow", command, project)

    def test_allows_a_tool_other_than_bash(self):
        project = self.project()
        for tool in ("Bash", "write", "ctx_execute"):
            with self.subTest(tool=tool):
                payload = {"tool_name": tool, "tool_input": {"command": self.run_cmd},
                           "cwd": str(project)}
                self.assertEqual(self.verdict(payload), "allow")

    def test_allows_an_unreadable_payload(self):
        project = self.project()
        for raw in ("not json", "", json.dumps([self.run_cmd]), '{"tool_name": "bash"'):
            with self.subTest(payload=raw):
                self.assertEqual(self.verdict(raw, proc_cwd=project), "allow")

    def test_allows_an_untokenisable_command(self):
        project = self.project()
        for command in (f"{self.run_cmd} 'unterminated", f'{self.run_cmd} "unterminated'):
            with self.subTest(command=command):
                self.assertVerdict("allow", command, project)

    def test_allows_a_client_invocation(self):
        project = self.project()
        self.assertVerdict("allow", self.CLIENT_RUN, project)


class CargoHookFailOpenTest(_FailOpen, _RunnerHookCase):
    HOOK = "cargo"
    HATCH = "ALLOW_RAW_CARGO"
    CLIENT_RUN = "python3 ~/.crucible/clients/rust-crucible.py test --crate fixture --agent a"


class MvnHookFailOpenTest(_FailOpen, _RunnerHookCase):
    HOOK = "mvn"
    HATCH = "ALLOW_RAW_MVN"
    CLIENT_RUN = "python3 ~/.crucible/clients/mvn-crucible.py unit --test FooTest --agent a"


if __name__ == "__main__":
    unittest.main()
