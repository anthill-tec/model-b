"""The runner hooks, run for real on payloads — CR-MDB-062 §S2, §S3, §S5 and §S6.

Contract: ``docs/changes/CR-MDB-062-blocking-hooks-for-python-and-bun.md``. Every test runs the
REAL script under ``hooks-src/scripts/`` (``tests._helpers.run_hook``) on the neutral payload
(``tool_name`` ``bash``, ``tool_input.command``, ``cwd``) inside a temp project tree under
``/tmp`` (``tests._helpers.build_tree``). A verdict is exit 0 (allow) or exit 2 with
``{"decision": "block", …}`` on stdout; any traceback on stderr fails the test, because a
``closed`` hook that raises blocks every shell call.

What the module pins, for all four runner hooks — ``block-direct-python-test`` and
``block-direct-bun-test`` (§S2), ``block-direct-cargo-test`` and ``block-direct-mvn-test`` (§S5):

- **The scripts (§S2):** each exists, is executable, and imports only the stdlib and no sibling
  (an AST check, its detector proved on synthetic source first).
- **Each stack's runner forms (§S1, §S2):** the python hook blocks exactly §S1's python forms
  and the bun hook exactly §S2's bun list, at every position and under every wrapper; neither
  blocks a non-test script, a narrowed bun script, a client invocation, a non-runner mention or
  a runner word inside an argument or a heredoc body.

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
  ``cwd`` allows. The python and bun markers count like the others, and the Sandesh layout
  (``pyproject.toml`` at the root, ``integrations/pi/package.json``, run from the root) is a
  project of both.
- **Fail-open behaviour kept:** the escape hatch (``ALLOW_RAW_<RUNNER>``; another runner's hatch
  opens nothing), a non-``bash`` tool, an unreadable payload and an untokenisable command allow.
- **Shell words (orchestrator ruling on §S6):** the shell removes quotes and redirections before
  the runner sees its arguments, so ``mvn "test"``, ``cargo "test"``, ``"pytest"`` and
  ``mvn test>build.log`` run tests; a here-string (``<<<``) is not a heredoc, so the next line
  is a command position.
- **Parity with the guard (§S6):** one corpus — the guard's ``RUNNER_FORMS``,
  ``WRAPPED_FORMS``, ``CLIENT_FORMS`` and ``NON_RUNNER_MENTIONS``, its CR-MDB-062 corpora, this
  module's position and mention forms and ``PARITY_FORMS`` (the shell readings, the quoted and
  redirected words, ``(mvn test)``) — run through the guard's ``stack_of`` and through all four
  real scripts in a project carrying every stack's markers. A command the guard assigns to a
  stack is blocked by that stack's hook only; a command it passes is allowed by all four; each
  of §S5's hook-only extras (``HOOK_ONLY_EXTRAS``) is blocked by its own hook only. The arduino
  forms are left out.

The block REASON (§S4) is pinned in ``tests/test_client_path_anchoring.py``, beside the reason
checks it extends. Each class is a per-hook binding of a mixin, so one more runner hook is one
more binding.

Stdlib only.
"""

import ast
import json
import os
import shutil
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

from tests._helpers import HOOK_SCRIPTS_DIR, build_tree, run_hook
from tests.test_raw_runner_guard import (
    ARGUMENT_MENTIONS,
    ATTACHED_M_FORMS,
    BUN_SCRIPT_FORMS,
    CLIENT_FORMS,
    HEREDOC_BODIES,
    NARROWED_BUN_SCRIPTS,
    NON_RUNNER_MENTIONS,
    NON_TEST_SCRIPTS,
    POSITION_FORMS,
    QUOTED_LINES,
    RUNNER_FORMS,
    TEST_FILE_FORMS,
    UV_RUN_FORMS,
    WRAPPED_FORMS,
    stack_of,
)

#: The four runner hooks, keyed by the stack the guard's ``stack_of`` names: the script, its
#: stack's markers (§S3's table, primary first; ``requirements*.txt`` as concrete names) and the
#: plain runner command each blocks.
RUNNER_HOOKS = {
    "python": {"script": "block-direct-python-test",
               "markers": ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
                           "requirements-dev.txt"),
               "run": "python3 -m unittest"},
    "bun": {"script": "block-direct-bun-test",
            "markers": ("package.json", "bun.lock", "bun.lockb", "bunfig.toml"), "run": "bun test"},
    "cargo": {"script": "block-direct-cargo-test", "markers": ("Cargo.toml",),
              "run": "cargo test"},
    "mvn": {"script": "block-direct-mvn-test",
            "markers": ("pom.xml", "build.gradle", "build.gradle.kts"), "run": "mvn test"},
}

#: Each runner hook's escape hatch (§S2, §S5), plus the guard corpus's ``ALLOW_RAW_PYTEST``:
#: a hook opens only to its own.
ESCAPE_HATCHES = ("ALLOW_RAW_PYTHON", "ALLOW_RAW_BUN", "ALLOW_RAW_CARGO", "ALLOW_RAW_MVN",
                  "ALLOW_RAW_PYTEST")

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
    # the shell readings the guard chose (§S6): ``$(`` is a position, a ``#`` inside a word
    # starts no comment, a redirection is no part of the runner's words, and a here-string
    # (``<<<``) is not a heredoc, so the next line is a command position
    "echo $({run})",
    "out=$({run})",
    "echo a#b && {run}",
    "{run} 2>&1 | tee test.log",
    "{run}>out.txt",
    "{run} &> out.txt",
    "cat <<< EOF\n{run}",
    "cat <<<EOF\n{run}",
    'cat <<< "$x"\n{run}',
    "cat <<< hi && {run}",
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
    # a redirection's target, a comment, a continued line and a here-string's word are no
    # command position (§S6's shell readings)
    "echo done 2>&1 {run}",
    "echo x >| {run}",
    "echo x &> {run}",
    "echo hi # && {run}",
    "echo hi #; {run}",
    "echo hi \\\n{run}",
    "cat <<<'{run}'",
)

#: Orchestrator ruling on §S6: the shell removes quotes and redirections before the runner
#: sees its words, so each of these runs its stack's tests (a block by that stack's hook).
QUOTED_WORD_FORMS = {
    "python": ('"pytest"', "'pytest' -x", '"pytest" -q tests/', 'python3 -m "unittest"',
               "python3 -m 'pytest' -x", '"python3" -m unittest', "pytest>out.txt",
               "python3 -m unittest>log.txt"),
    "bun": ('"bun" test', "bun 'test'", 'npm "test"', "bun run 'test:unit'",
            "npx playwright 'test'", "bun test>out.txt", "npm test>out.txt"),
    "cargo": ('cargo "test"', "cargo 'nextest' run", '"cargo" test', "cargo test>out.txt",
              "cargo llvm-cov>cov.txt"),
    "mvn": ('mvn "test"', "mvn 'surefire:test'", "mvn test>build.log", '"mvn" verify',
            "./mvnw 'verify'", "mvn -q 'test-compile'"),
}


def _bash_payload(command, cwd):
    """The neutral payload of a ``bash`` call running ``command`` in ``cwd``."""
    return {"tool_name": "bash", "tool_input": {"command": command}, "cwd": str(cwd)}


def _verdict_of(script, payload):
    """``"allow"``, ``"block"`` or ``"error: …"`` from the REAL hook ``script`` on ``payload``:
    an error is a traceback, an exit other than 0 or 2, or an exit 2 without a block decision
    (a missing script included), so it never equals a verdict a test expects."""
    res = run_hook(script, payload)
    if "Traceback" in res.stderr:
        return f"error: {script} raised: {res.stderr.strip()[-400:]}"
    if res.returncode == 0:
        return "allow"
    try:
        decision = json.loads(res.stdout).get("decision")
    except (ValueError, AttributeError):
        decision = None
    if res.returncode == 2 and decision == "block":
        return "block"
    return f"error: {script} exit {res.returncode}, stdout {res.stdout[:200]!r}, stderr {res.stderr[:300]!r}"


def _verdicts(script, commands, cwd):
    """``{command: verdict}`` for each of ``commands`` run through the REAL hook ``script`` in
    ``cwd``, one process per command (a hook reads one payload), eight at a time."""
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {c: pool.submit(_verdict_of, script, _bash_payload(c, cwd)) for c in commands}
    return {command: future.result() for command, future in futures.items()}


class _RunnerHookCase(unittest.TestCase):
    """One runner hook (``HOOK``, a ``RUNNER_HOOKS`` key) run on payloads in temp trees."""

    HOOK = ""

    def setUp(self):
        self.spec = RUNNER_HOOKS[self.HOOK]
        self.marker = self.spec["markers"][0]
        self.run_cmd = self.spec["run"]
        script = HOOK_SCRIPTS_DIR / self.spec["script"]
        self.assertTrue(script.is_file(), f"§S2: the runner hook script {script} does not exist")
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
        return _bash_payload(command, cwd)

    def assertVerdicts(self, expected, commands, cwd, why=""):
        """Every one of ``commands`` gets ``expected`` from the real hook in ``cwd``."""
        wrong = {c: v for c, v in _verdicts(self.spec["script"], commands, cwd).items()
                 if v != expected}
        self.assertEqual(wrong, {}, f"{self.spec['script']}: want {expected} for each command "
                                    f"in {cwd} {why}")

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

    def test_blocks_the_runner_whose_words_are_quoted_or_carry_a_redirection(self):
        # The shell removes the quotes and the redirection before the runner sees its words.
        self.assertVerdicts("block", QUOTED_WORD_FORMS[self.HOOK], self.project(),
                            "(quoted or redirected words)")


class PythonHookCommandPositionTest(_CommandPositions, _RunnerHookCase):
    HOOK = "python"


class BunHookCommandPositionTest(_CommandPositions, _RunnerHookCase):
    HOOK = "bun"


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


# ----------------------------------------------------------------- §S1/§S2 forms ----

#: The guard's corpora of single-line runner forms, each entry labelled with its stack (§S1).
_SINGLE_LINE_CORPORA = (RUNNER_FORMS, ATTACHED_M_FORMS, UV_RUN_FORMS, TEST_FILE_FORMS,
                        BUN_SCRIPT_FORMS)
#: The guard's corpora of forms already placed at a later position or under a wrapper.
_PLACED_CORPORA = (WRAPPED_FORMS, POSITION_FORMS)

#: §S1's python runner forms beyond the guard's corpora, one per shape.
PYTHON_HOOK_FORMS = (
    "python3 -m pytest",
    "python -m xmlrunner discover",
    "python3 -m coverage run -m pytest",
    "python3 -mcoverage run -m unittest",
    "py.test -k smoke",
    "/opt/venv/bin/pytest -q",
    "uv run pytest -x",
    "uv run --with pytest python3 -m pytest",
    "uv run python3 -munittest",
    "coverage run --source=src -m pytest",
    "python3 test_cli.py",
    "python3 -u pkg/parser_test.py --verbose",
)
#: §S2's bun list beyond the guard's corpora.
BUN_HOOK_FORMS = (
    "bun test src/a.test.ts",
    "bun run test:e2e",
    "npm test -- --watch",
    "npm run test:unit",
    "bunx playwright test",
    "bun x playwright test",
    "npx playwright test --project=chromium",
    "playwright test --ui",
)
#: Each single-line form re-placed (§S2): on a later line, after a separator in a subshell, and
#: under every wrapper at once.
FORM_PLACEMENTS = (
    "echo hi\n{form}",
    "(cd sub && {form})",
    "env -i HOME=/tmp/h timeout -k 5 60 nice -n 5 time {form}",
)
#: §S2 — never blocked by either new hook: a non-test script, a narrowed bun script, a runner
#: word inside an argument, a client invocation, a non-runner mention, a heredoc body, a line in
#: quotes.
NEVER_RUNNERS = (NON_TEST_SCRIPTS + NARROWED_BUN_SCRIPTS + ARGUMENT_MENTIONS + CLIENT_FORMS
                 + NON_RUNNER_MENTIONS + HEREDOC_BODIES + QUOTED_LINES)
#: §S2 — what each new hook never blocks beyond ``NEVER_RUNNERS`` (the brief's named cases).
NEVER_BLOCKED = {
    "python": (
        "python3 generator/build.py --check",
        'python3 -c "import unittest; print(1)"',
        "python3 - <<EOF\nprint('pytest')\nEOF",
        "python3 - <<'EOF'\nimport unittest\nEOF",
        "uv run --with x python script.py",
        'git commit -m "fix; pytest"',
        "echo python3 -m unittest",
        "pip install pytest",
        "cat pytest.ini",
        "python3 ~/.crucible/clients/python-crucible.py regression --coverage --agent a",
    ),
    "bun": (
        "bun run tests/x.ts",
        "npm run build",
        "npx playwright install",
        "npx playwright install --with-deps",
        "bun install",
        "bun run dev",
        "npm ci",
        "bun run build && echo test",
        "echo bun test",
        "git commit -m 'bun test passes; npm test too'",
        "cat > notes.md <<EOF\nnpm test\nnpx playwright test\nEOF",
        "python3 ~/.crucible/clients/bun-crucible.py check --agent a",
    ),
}


def _forms_of(stack, corpora):
    """The commands of ``corpora`` (``(command, stack)`` tuples) labelled ``stack``."""
    return tuple(command for corpus in corpora for command, label in corpus if label == stack)


class _StackRunnerForms(_MixinBase):
    """§S1/§S2 — the hook blocks exactly its stack's runner forms (``EXTRA_FORMS`` plus the
    guard corpora's entries of its stack) and never a non-runner."""

    EXTRA_FORMS = ()

    def _single_line_forms(self):
        return _forms_of(self.HOOK, _SINGLE_LINE_CORPORA) + self.EXTRA_FORMS

    def test_blocks_each_runner_form_of_its_stack(self):
        forms = self._single_line_forms() + _forms_of(self.HOOK, _PLACED_CORPORA)
        self.assertGreaterEqual(len(forms), 20, "precondition: the stack's forms are collected")
        self.assertVerdicts("block", forms, self.project(), "(a runner form of its stack)")

    def test_blocks_each_runner_form_on_a_later_line_in_a_subshell_and_under_every_wrapper(self):
        commands = [p.format(form=f) for f in self._single_line_forms() for p in FORM_PLACEMENTS]
        self.assertVerdicts("block", commands, self.project(), "(a re-placed runner form)")

    def test_allows_every_command_that_is_never_a_runner(self):
        self.assertVerdicts("allow", NEVER_RUNNERS + NEVER_BLOCKED[self.HOOK], self.project(),
                            "(never a runner)")

    def test_allows_every_other_stacks_runner_forms(self):
        others = tuple(c for corpus in _SINGLE_LINE_CORPORA for c, label in corpus
                       if label not in (self.HOOK, "make"))
        self.assertVerdicts("allow", others, self.project(), "(another stack's runner)")


class PythonHookRunnerFormsTest(_StackRunnerForms, _RunnerHookCase):
    HOOK = "python"
    EXTRA_FORMS = PYTHON_HOOK_FORMS


class BunHookRunnerFormsTest(_StackRunnerForms, _RunnerHookCase):
    HOOK = "bun"
    EXTRA_FORMS = BUN_HOOK_FORMS


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


class _NotASandeshStack(_MixinBase):
    """A hook whose stack Sandesh does not carry (cargo, mvn): its layout is no project."""

    def test_allows_the_sandesh_layout_without_this_stacks_marker(self):
        root = build_tree(self.tmp / "repo", ["pyproject.toml", "integrations/pi/package.json"],
                          git="dir")
        self.assertVerdict("allow", self.run_cmd, root, "(no marker of this stack)")


class _SandeshStack(_MixinBase):
    """A hook whose stack Sandesh carries (python, bun). Sandesh's layout: ``pyproject.toml`` at
    the root, its bun package in ``integrations/pi/``; a Pi shell call runs from the session
    root, so both hooks block their own stack's runner there."""

    #: The one Sandesh marker of the OTHER stack.
    OTHER_SANDESH_MARKER = ""

    def test_blocks_its_runner_in_the_sandesh_layout_from_the_root_and_a_sub_directory(self):
        for git in ("dir", "file"):
            with self.subTest(git=git):
                root = build_tree(self.tmp / f"sandesh-{git}",
                                  ["pyproject.toml", "integrations/pi/package.json",
                                   "integrations/pi/src/index.ts", "src/sandesh/cli.py"], git=git)
                self.assertVerdict("block", self.run_cmd, root, "(Sandesh layout, from the root)")
                self.assertVerdict("block", self.run_cmd, root / "src" / "sandesh",
                                   "(Sandesh layout, from src/sandesh)")

    def test_allows_its_runner_when_only_the_other_sandesh_stacks_marker_is_present(self):
        root = build_tree(self.tmp / "sandesh-other", [self.OTHER_SANDESH_MARKER, "src/x.txt"],
                          git="dir")
        self.assertVerdict("allow", self.run_cmd, root,
                           f"(only {self.OTHER_SANDESH_MARKER}, the other stack's marker)")


class _MarkerVariants(_MixinBase):
    """Every marker of §S3's table counts like the primary one; a near miss never does."""

    VARIANTS = ()
    NEAR_MISSES = ()

    def test_each_marker_of_its_stack_counts_like_the_primary_one(self):
        for marker in self.VARIANTS:
            with self.subTest(marker=marker):
                root = build_tree(self.tmp / f"variant-{marker}", ["app/" + marker], git="dir")
                self.assertVerdict("block", self.run_cmd, root, f"(app/{marker} below the root)")
                (root / "app" / "src").mkdir()
                self.assertVerdict("block", self.run_cmd, root / "app" / "src",
                                   f"(app/{marker} in a parent)")
                cwd = build_tree(self.tmp / f"plain-{marker}", [marker])
                self.assertVerdict("block", self.run_cmd, cwd, f"({marker} in the cwd)")

    def test_a_file_that_only_resembles_a_marker_does_not_count(self):
        for name in self.NEAR_MISSES:
            with self.subTest(file=name):
                root = build_tree(self.tmp / f"near-{name}", [name, "app/" + name], git="dir")
                self.assertVerdict("allow", self.run_cmd, root, f"(only {name})")


class PythonHookMarkerRuleTest(_MarkerRule, _SandeshStack, _MarkerVariants, _RunnerHookCase):
    HOOK = "python"
    OTHER_SANDESH_MARKER = "integrations/pi/package.json"
    VARIANTS = ("setup.py", "setup.cfg", "requirements.txt", "requirements-dev.txt",
                "requirements_test.txt")
    NEAR_MISSES = ("requirements.in", "dev-requirements.txt", "requirements.txt.bak",
                   "pyproject.toml.orig")


class BunHookMarkerRuleTest(_MarkerRule, _SandeshStack, _MarkerVariants, _RunnerHookCase):
    HOOK = "bun"
    OTHER_SANDESH_MARKER = "pyproject.toml"
    VARIANTS = ("bun.lock", "bun.lockb", "bunfig.toml")
    NEAR_MISSES = ("package-lock.json", "bun.lock.bak", "tsconfig.json")


class CargoHookMarkerRuleTest(_MarkerRule, _NotASandeshStack, _RunnerHookCase):
    HOOK = "cargo"


class MvnHookMarkerRuleTest(_MarkerRule, _NotASandeshStack, _RunnerHookCase):
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

    def test_another_runners_escape_hatch_does_not_open_this_hook(self):
        others = [f"{hatch}=1 {self.run_cmd}" for hatch in ESCAPE_HATCHES if hatch != self.HATCH]
        self.assertEqual(len(others), len(ESCAPE_HATCHES) - 1, "precondition: HATCH is listed")
        self.assertVerdicts("block", others, self.project(), "(another runner's hatch)")


class PythonHookFailOpenTest(_FailOpen, _RunnerHookCase):
    HOOK = "python"
    HATCH = "ALLOW_RAW_PYTHON"
    CLIENT_RUN = "python3 ~/.crucible/clients/python-crucible.py test --tests tests.test_x --agent a"


class BunHookFailOpenTest(_FailOpen, _RunnerHookCase):
    HOOK = "bun"
    HATCH = "ALLOW_RAW_BUN"
    CLIENT_RUN = "python3 ~/.crucible/clients/bun-crucible.py test --tests src/a.test.ts --agent a"


class CargoHookFailOpenTest(_FailOpen, _RunnerHookCase):
    HOOK = "cargo"
    HATCH = "ALLOW_RAW_CARGO"
    CLIENT_RUN = "python3 ~/.crucible/clients/rust-crucible.py test --crate fixture --agent a"


class MvnHookFailOpenTest(_FailOpen, _RunnerHookCase):
    HOOK = "mvn"
    HATCH = "ALLOW_RAW_MVN"
    CLIENT_RUN = "python3 ~/.crucible/clients/mvn-crucible.py unit --test FooTest --agent a"


# ----------------------------------------------------------------- §S2 imports --------

#: Standard-library modules that load other modules by name or path: a hook importing one could
#: reach a sibling without an ``import`` statement naming it.
_MODULE_LOADERS = frozenset({"importlib", "runpy", "imp", "zipimport"})


def _import_violations(source, siblings):
    """Each way ``source`` imports beyond the stdlib or reaches a module in ``siblings`` (import
    names): a non-stdlib module, a sibling, a relative import, a module loader, or a call to
    ``__import__``/``exec``/``eval``. ``[]`` when it keeps CR-MDB-015's self-containment."""
    violations = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in ("__import__", "exec", "eval"):
            violations.append(f"line {node.lineno}: calls {node.func.id}()")
            continue
        if isinstance(node, ast.ImportFrom) and node.level:
            violations.append(f"line {node.lineno}: a relative import")
            continue
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [node.module or ""]
        else:
            continue
        for module in modules:
            top = module.split(".")[0]
            if top in siblings:
                violations.append(f"line {node.lineno}: imports the sibling {module}")
            elif top in _MODULE_LOADERS:
                violations.append(f"line {node.lineno}: imports the module loader {module}")
            elif top not in sys.stdlib_module_names:
                violations.append(f"line {node.lineno}: imports {module}, not the stdlib")
    return violations


class RunnerHookScriptsSelfContainedTest(unittest.TestCase):
    """§S2 / CR-MDB-015 — each of the four runner hooks exists, is executable, and imports only
    the stdlib and no sibling (the detector is proved on synthetic source first)."""

    SIBLINGS = frozenset({"block_direct_python_test", "block_direct_bun_test",
                          "block_direct_cargo_test", "block_direct_mvn_test"})

    def test_the_import_detector_bites_on_each_breach_and_passes_the_stdlib(self):
        clean = "import json\nimport os.path\nfrom pathlib import Path\nimport re, sys\n"
        self.assertEqual(_import_violations(clean, self.SIBLINGS), [])
        breaches = {
            "a third-party module": "import yaml\n",
            "a first-party package": "from modelb_axi import hooks\n",
            "a relative import": "from . import shared\n",
            "a sibling hook": "import block_direct_cargo_test\n",
            "a sibling through from": "from block_direct_mvn_test import _segments\n",
            "a module loader": "import importlib.util\n",
            "runpy": "from runpy import run_path\n",
            "__import__": "x = __import__('block_direct_cargo_test')\n",
            "exec": "exec(open('block-direct-cargo-test').read())\n",
        }
        for label, source in breaches.items():
            with self.subTest(breach=label):
                self.assertEqual(len(_import_violations(source, self.SIBLINGS)), 1, label)

    def test_each_runner_hook_exists_is_executable_and_imports_only_the_stdlib(self):
        siblings = self.SIBLINGS | {p.name.replace("-", "_") for p in HOOK_SCRIPTS_DIR.iterdir()}
        failures = []
        for spec in RUNNER_HOOKS.values():
            path = HOOK_SCRIPTS_DIR / spec["script"]
            if not path.is_file():
                failures.append(f"{spec['script']}: missing at {path}")
                continue
            if not os.access(path, os.X_OK):
                failures.append(f"{spec['script']}: not executable")
            failures += [f"{spec['script']}: {v}" for v in
                         _import_violations(path.read_text(encoding="utf-8"), siblings)]
        self.assertEqual(failures, [], "§S2 runner hook scripts:\n  " + "\n  ".join(failures))


# ----------------------------------------------------------------- §S6 parity ---------

#: §S6 — commands beyond the guard's own corpora, each with the stack the guard must name
#: (``None``: no runner). ``git commit -m "fix; pytest"``, the subshell Maven runs, and the
#: shell readings the guard chose: ``2>&1``, ``>|`` and ``&>`` redirect and separate nothing; a
#: ``#`` starting a word begins a comment; a backslash-newline continues the line; ``<<<`` is a
#: here-string, not a heredoc; ``$(`` is a command position.
PARITY_FORMS = (
    ('git commit -m "fix; pytest"', None),
    ("(mvn test)", "mvn"),
    ("(timeout 60 mvn test)", "mvn"),
    ("out=$(mvn test)", "mvn"),
    ("cargo test 2>&1 | tee test.log", "cargo"),
    ("mvn verify &> build.log", "mvn"),
    ("pytest >| out.txt", "python"),
    ("echo done 2>&1 pytest", None),
    ("echo done 2>&1 bun test", None),
    ("echo x >| pytest", None),
    ("echo x >| cargo test", None),
    ("echo x &> mvn test", None),
    ("echo x &> bun test", None),
    ("echo hi # && pytest", None),
    ("echo hi #; mvn test", None),
    ("echo a#b && cargo test", "cargo"),
    ("echo a#b; bun test", "bun"),
    ("echo hi \\\npytest", None),
    ("echo hi \\\ncargo test", None),
    ("echo hi \\\nbun test", None),
    ("echo hi \\\nmvn verify", None),
    ("cat <<< EOF\npytest", "python"),
    ("cat <<<EOF\ncargo test", "cargo"),
    ('cat <<< "$x"\nbun test', "bun"),
    ("cat <<< hi\nmvn test", "mvn"),
    ("cat <<<'bun test'", None),
    ("cat <<< hi && mvn test", "mvn"),
    ("echo $(pytest -q)", "python"),
    ("echo $(cargo test)", "cargo"),
    ("echo $(bun test)", "bun"),
) + tuple((command, stack) for stack, forms in QUOTED_WORD_FORMS.items() for command in forms)

#: This module's position and mention forms, for each hook's plain runner, with their stacks.
MODULE_FORMS = tuple(
    (form.format(run=spec["run"]), stack)
    for stack, spec in RUNNER_HOOKS.items() for form in BLOCKED_POSITIONS
) + tuple((form.format(run=spec["run"]), None)
          for spec in RUNNER_HOOKS.values() for form in ALLOWED_MENTIONS)

#: §S5's hook-only extras: the guard passes each, and only its own hook blocks it.
HOOK_ONLY_EXTRAS = {
    "cargo": ("cargo check", "cargo clippy -- -D warnings", "cargo +nightly test",
              "cargo +stable nextest run", "echo hi\ncargo check"),
    "mvn": ("mvnd test", "mvnd verify", "/usr/bin/mvn test", "tools/maven/bin/mvn verify",
            "sub/dir/mvnw integration-test"),
}


def _parity_corpus():
    """§S6's corpus, each command once: the guard's ``RUNNER_FORMS``, ``WRAPPED_FORMS``,
    ``CLIENT_FORMS`` and ``NON_RUNNER_MENTIONS``, its CR-MDB-062 corpora, ``MODULE_FORMS`` and
    ``PARITY_FORMS`` — the arduino (``make``) entries left out."""
    labelled = (RUNNER_FORMS + WRAPPED_FORMS + POSITION_FORMS + ATTACHED_M_FORMS + UV_RUN_FORMS
                + TEST_FILE_FORMS + BUN_SCRIPT_FORMS + MODULE_FORMS + PARITY_FORMS)
    plain = (CLIENT_FORMS + NON_RUNNER_MENTIONS + NARROWED_BUN_SCRIPTS + HEREDOC_BODIES
             + QUOTED_LINES + NON_TEST_SCRIPTS + ARGUMENT_MENTIONS)
    commands = [command for command, stack in labelled if stack != "make"] + list(plain)
    return tuple(dict.fromkeys(commands))


class RunnerHookGuardParityTest(unittest.TestCase):
    """§S6 — the corpus through the guard's ``stack_of`` and through all four REAL hook scripts,
    each payload's ``cwd`` a temp git project carrying every stack's marker."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="modelb-runner-parity-", dir="/tmp"))
        project = build_tree(cls.tmp / "all-stacks",
                             [spec["markers"][0] for spec in RUNNER_HOOKS.values()], git="dir")
        cls.corpus = _parity_corpus()
        cls.extras = tuple(c for commands in HOOK_ONLY_EXTRAS.values() for c in commands)
        cls.verdicts = {stack: _verdicts(spec["script"], cls.corpus + cls.extras, project)
                        for stack, spec in RUNNER_HOOKS.items()}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_the_corpus_holds_every_named_corpus_and_no_arduino_form(self):
        for command in ("python3 -m unittest", "bun test", "cargo test", "mvn test", "(mvn test)",
                        CLIENT_FORMS[0], NON_RUNNER_MENTIONS[0], NARROWED_BUN_SCRIPTS[0],
                        HEREDOC_BODIES[0], NON_TEST_SCRIPTS[0], ARGUMENT_MENTIONS[0]):
            self.assertIn(command, self.corpus)
        self.assertEqual([c for c in self.corpus if "make junit" in c], [])
        self.assertEqual(len(self.corpus), len(set(self.corpus)))

    def test_the_guard_names_the_stack_of_each_form_this_module_labels(self):
        wrong = [f"{command!r}: guard says {stack_of(command)!r}, want {stack!r}"
                 for command, stack in MODULE_FORMS + PARITY_FORMS if stack_of(command) != stack]
        wrong += [f"{command!r}: a hook-only extra, but the guard says {stack_of(command)!r}"
                  for command in self.extras if stack_of(command) is not None]
        self.assertEqual(wrong, [], "§S6: the guard's verdicts:\n  " + "\n  ".join(wrong))

    def test_each_command_the_guard_assigns_to_a_stack_is_blocked_by_that_stacks_hook_only(self):
        wrong = []
        for command in self.corpus:
            stack = stack_of(command)
            if stack is None:
                continue
            for hook, verdicts in self.verdicts.items():
                want = "block" if hook == stack else "allow"
                if verdicts[command] != want:
                    wrong.append(f"{command!r} (guard: {stack}): {hook} hook {verdicts[command]}")
        self.assertEqual(wrong, [], "§S6 parity:\n  " + "\n  ".join(wrong))

    def test_each_command_the_guard_passes_is_allowed_by_all_four_hooks(self):
        wrong = [f"{command!r} (guard: None): {hook} hook {verdicts[command]}"
                 for command in self.corpus if stack_of(command) is None
                 for hook, verdicts in self.verdicts.items() if verdicts[command] != "allow"]
        self.assertEqual(wrong, [], "§S6 parity:\n  " + "\n  ".join(wrong))

    def test_each_hook_only_extra_is_blocked_by_its_own_hook_only(self):
        wrong = [f"{command!r} (a {owner} extra): {hook} hook {verdicts[command]}"
                 for owner, commands in HOOK_ONLY_EXTRAS.items() for command in commands
                 for hook, verdicts in self.verdicts.items()
                 if verdicts[command] != ("block" if hook == owner else "allow")]
        self.assertEqual(wrong, [], "§S5/§S6 extras:\n  " + "\n  ".join(wrong))


if __name__ == "__main__":
    unittest.main()
