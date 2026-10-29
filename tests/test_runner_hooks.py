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
- **The shell grammar's positions (CR-MDB-066 §S1):** the reserved words ``!``, ``{``, ``if``,
  ``then``, ``else``, ``elif``, ``while``, ``until`` and ``do``, ``command [-p]`` and
  ``time -p`` are stepped over like a wrapper; an unquoted backquote opens a command position up
  to its closing backquote; an arithmetic ``$((…))`` or ``((…))`` is skipped whole, so no ``<<``
  in it opens a heredoc. ``command -v``/``-V`` and the text after a closing backquote stay
  allowed; the guard's ``GRAMMAR_FORMS`` and ``GRAMMAR_NON_RUNNERS`` join the parity corpus.
- **Source identity (CR-MDB-066 AC10):** the four hooks' copies of the shared parser and walk
  (``SHARED_DEFINITIONS``, and every other name all four define but the per-stack four) are one
  source, compared by ``ast.unparse``.
- **The bun forms (CR-MDB-066 §S2):** the package managers' test script (``npm test``/``tst``/
  ``t``, ``pnpm test``, ``yarn test``, ``run``/``run-script`` before ``test[:<name>]``), the
  ``bun run --filter`` workspace filter and Vitest (bare, by path, after ``bunx``/``bun x``/
  ``npx``) are blocked by the bun hook alone, in a project holding any one bun marker, and
  allowed outside one; the guard's ``PACKAGE_MANAGER_FORMS``, ``FILTER_FORMS``,
  ``VITEST_FORMS`` and ``BUN_NON_RUNNERS`` join the parity corpus.
- **The marker walk (CR-MDB-066 §S4, AC5):** each hook, loaded in process
  (``tests._helpers.load_hook_module``), lists each directory its ``_in_project`` looks in at
  most once with ``os.scandir`` and never calls ``pathlib.Path.glob`` (a recorder, proved both
  ways on a synthetic walk); a marker counts only when ``os.path.isfile`` accepts it. Through
  the real scripts: an execute-only directory still counts a literal marker it holds and is not
  descended; a read-only one hides the marker it holds; a marker-named symlink loop or
  directory is no marker. The verdicts are today's.

The block REASON (§S4) is pinned in ``tests/test_client_path_anchoring.py``, beside the reason
checks it extends. Each class is a per-hook binding of a mixin, so one more runner hook is one
more binding.

Stdlib only.
"""

import ast
import importlib.machinery
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING
from unittest import mock

from tests import _helpers
from tests._helpers import HOOK_SCRIPTS_DIR, build_tree, load_hook_module, run_hook
from tests.test_raw_runner_guard import (
    ARGUMENT_MENTIONS,
    ATTACHED_M_FORMS,
    BUN_NON_RUNNERS,
    BUN_SCRIPT_FORMS,
    CLIENT_FORMS,
    FILTER_FORMS,
    GRAMMAR_FORMS,
    GRAMMAR_NON_RUNNERS,
    HEREDOC_BODIES,
    NARROWED_BUN_SCRIPTS,
    NON_RUNNER_MENTIONS,
    NON_TEST_SCRIPTS,
    OPTION_RUN_BUDGET,
    OPTION_RUNS,
    PACKAGE_MANAGER_FORMS,
    POSITION_FORMS,
    QUOTED_LINES,
    RUNNER_FORMS,
    TEST_FILE_FORMS,
    UV_RUN_FORMS,
    VITEST_FORMS,
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
    # CR-MDB-066 §S1 — the shell grammar's positions: the reserved words, ``command [-p]``,
    # ``time -p``, an unquoted backquote, and a line after an arithmetic expansion whose ``<<``
    # opens no heredoc (the group's own braces doubled for ``str.format``: ``{ <run>; }``)
    "{{ {run}; }}",
    "if {run}; then :; fi",
    "if true; then {run}; fi",
    "if false; then :; else {run}; fi",
    "while {run}; do :; done",
    "for f in a; do {run}; done",
    "! {run}",
    "command {run}",
    "command -p {run}",
    "time -p {run}",
    "echo `{run}`",
    "out=`{run}`",
    "echo $((1<<2))\n{run}",
    "((n<<2))\n{run}",
    "while ((n<<1)); do\n{run}\ndone",
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
    # CR-MDB-066 §S1 — a lookup runs nothing; the text after a closing backquote or an
    # arithmetic expansion continues the enclosing command; a backquote inside double quotes or
    # a heredoc body opens nothing
    "command -v {run}",
    "command -V {run}",
    "echo `date` {run}",
    "echo $((1<<2)) {run}",
    'git commit -m "fix `{run}`"',
    "cat <<EOF\n`{run}`\nEOF",
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
#: MIGRATED at CR-MDB-066 (§S8.2): gains PACKAGE_MANAGER_FORMS, FILTER_FORMS and VITEST_FORMS,
#: the bun forms of §S2.
_SINGLE_LINE_CORPORA = (RUNNER_FORMS, ATTACHED_M_FORMS, UV_RUN_FORMS, TEST_FILE_FORMS,
                        BUN_SCRIPT_FORMS, PACKAGE_MANAGER_FORMS, FILTER_FORMS, VITEST_FORMS)
#: The guard's corpora of forms already placed at a later position or under a wrapper.
#: MIGRATED at CR-MDB-066 (§S8.2): gains GRAMMAR_FORMS, the shell grammar's positions.
_PLACED_CORPORA = (WRAPPED_FORMS, POSITION_FORMS, GRAMMAR_FORMS)

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
    # MIGRATED at CR-MDB-066 (§S8.2): gains BUN_NON_RUNNERS, §S2's never-runners.
    ) + BUN_NON_RUNNERS,
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


#: CR-MDB-066 §S2 — every new bun form: the package managers' test script, the workspace
#: filter and Vitest.
NEW_BUN_FORMS = tuple(command for corpus in (PACKAGE_MANAGER_FORMS, FILTER_FORMS, VITEST_FORMS)
                      for command, _stack in corpus)


class BunHookPackageManagerFilterAndVitestFormsTest(_RunnerHookCase):
    """CR-MDB-066 §S2 (AC3, the hooks' half) — the bun hook blocks each new form in a project
    holding any ONE of the four bun markers, as written and re-placed by ``FORM_PLACEMENTS``;
    it allows each outside a bun project; it allows every ``BUN_NON_RUNNERS`` entry; and the
    python, cargo and mvn hooks allow every new form, even in a project of their own stack."""

    HOOK = "bun"

    def test_blocks_each_new_form_in_a_project_holding_each_bun_marker_alone(self):
        self.assertEqual(len(NEW_BUN_FORMS), len(set(NEW_BUN_FORMS)))
        self.assertGreaterEqual(len(NEW_BUN_FORMS), 30, "precondition: the §S2 forms")
        for marker in self.spec["markers"]:
            with self.subTest(marker=marker):
                project = build_tree(self.tmp / f"only-{marker}", [marker], git="dir")
                self.assertVerdicts("block", NEW_BUN_FORMS, project, f"(only {marker})")

    def test_blocks_each_new_form_re_placed_in_a_project_holding_each_bun_marker_alone(self):
        commands = [p.format(form=f) for f in NEW_BUN_FORMS for p in FORM_PLACEMENTS]
        for marker in self.spec["markers"]:
            with self.subTest(marker=marker):
                project = build_tree(self.tmp / f"placed-{marker}", [marker], git="dir")
                self.assertVerdicts("block", commands, project, f"(re-placed, only {marker})")

    def test_allows_each_new_form_in_a_project_with_only_pyproject_toml(self):
        # Passes on arrival (no bun marker, so the hook allows today); it fails against a
        # §S2 that blocks outside a bun project.
        project = build_tree(self.tmp / "python-only", ["pyproject.toml"], git="dir")
        commands = list(NEW_BUN_FORMS) + [p.format(form=f) for f in NEW_BUN_FORMS
                                          for p in FORM_PLACEMENTS]
        self.assertVerdicts("allow", commands, project, "(no bun marker: only pyproject.toml)")

    def test_allows_every_bun_non_runner_in_a_bun_project(self):
        # Passes on arrival: a regression pin against a §S2 that over-reaches.
        self.assertVerdicts("allow", BUN_NON_RUNNERS, self.project(), "(§S2: never a runner)")

    def test_the_python_cargo_and_mvn_hooks_allow_every_new_form(self):
        # Passes on arrival: only the bun hook blocks the §S2 forms. Each hook runs in a
        # project holding its own marker AND package.json, so an allow is never just "no marker".
        for stack in ("python", "cargo", "mvn"):
            spec = RUNNER_HOOKS[stack]
            with self.subTest(hook=spec["script"]):
                project = build_tree(self.tmp / f"{stack}-and-bun",
                                     [spec["markers"][0], "package.json"], git="dir")
                wrong = {c: v for c, v in _verdicts(spec["script"], NEW_BUN_FORMS, project).items()
                         if v != "allow"}
                self.assertEqual(wrong, {}, f"{spec['script']}: a §S2 bun form is not allowed")

    def test_the_hook_docstring_states_the_new_forms_and_cites_section_s2(self):
        # CR-MDB-066 §S7.2 (AC9): the bun hook's form list.
        source = (HOOK_SCRIPTS_DIR / self.spec["script"]).read_text(encoding="utf-8")
        doc = ast.get_docstring(ast.parse(source)) or ""
        missing = [word for word in ("pnpm", "yarn", "tst", "run-script", "--filter", "vitest",
                                     "CR-MDB-066 §S2") if word not in doc]
        self.assertEqual(missing, [], "CR-MDB-066 §S7.2: the bun hook's docstring does not name")


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


# ----------------------------------------------------------------- §S4 walk ----------

class _WalkRecorder:
    """CR-MDB-066 AC5 — while active, records every directory ``os.scandir`` lists (its path
    after ``os.path.realpath``, so a listing reached through a symlink counts against its target)
    and every ``pathlib.Path.glob`` call. Each call passes through to the real function and the
    recorder raises nothing of its own: ``_in_project`` reads an ``OSError`` or ``ValueError`` as
    "not a project", so a recorder that raised would hide the walk it watches."""

    def __init__(self):
        self.listed = []
        self.globbed = []
        self._patches = ()

    def __enter__(self):
        real_scandir, real_glob = os.scandir, Path.glob

        def scandir(path="."):
            if not isinstance(path, int):  # an open directory fd names no path
                self.listed.append(os.path.realpath(path))
            return real_scandir(path)

        def glob(path, pattern, *args, **kwargs):
            self.globbed.append(f"{path}.glob({pattern!r})")
            return real_glob(path, pattern, *args, **kwargs)

        self._patches = (mock.patch.object(os, "scandir", scandir),
                         mock.patch.object(Path, "glob", glob))
        for patch in self._patches:
            patch.start()
        return self

    def __exit__(self, *exc):
        for patch in reversed(self._patches):
            patch.stop()
        return False


def _walk_findings(recorder, once, never):
    """Each way the walk ``recorder`` watched breaks CR-MDB-066 §S4.1 (AC5), one finding per
    point: a path of ``once`` listed other than exactly once, a path of ``never`` listed at all,
    any other path listed, and each ``Path.glob`` call. Paths are ``os.path.realpath`` strings;
    ``[]`` when the walk listed exactly ``once``, each one time, and globbed nothing."""
    counts = Counter(recorder.listed)
    findings = [f"{path}: listed {counts[path]} times, want once"
                for path in once if counts[path] != 1]
    findings += [f"{path}: listed {counts[path]} times, want never"
                 for path in never if counts[path]]
    findings += [f"{path}: listed {counts[path]} times, outside the walk"
                 for path in sorted(counts) if path not in once and path not in never]
    findings += [f"Path.glob called: {call}" for call in recorder.globbed]
    return findings


#: CR-MDB-066 AC5's tree: a ``.git`` directory, no marker, the directories below and a directory
#: symlink ``link -> a`` (made by the test).
WALK_TREE_DIRS = ("a/b/c/d/", "e/f/", "node_modules/x/", ".hidden/y/")
#: The directories a run from the root or from ``e/f`` lists, each exactly once (``a/b/c`` sits 3
#: levels below the git root, so its listing serves its markers; its children are never listed).
WALK_LISTED_ONCE = (".", "a", "a/b", "a/b/c", "e", "e/f")
#: The directories no run lists: 4 levels down, skipped, or below a skipped one. ``link`` is
#: never listed either: listed, it would be recorded as ``a`` (its ``realpath``), twice.
WALK_NEVER_LISTED = ("a/b/c/d", "node_modules", "node_modules/x", ".hidden", ".hidden/y")


class MarkerWalkRecorderTest(unittest.TestCase):
    """CR-MDB-066 AC5 — the walk recorder and ``_walk_findings`` proved both ways on a synthetic
    walk before they judge a hook: a clean walk yields nothing; a second listing of one directory
    (directly or through a directory symlink) and a ``Path.glob`` call are each reported."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="modelb-walk-recorder-", dir="/tmp"))
        self.root = build_tree(self.tmp / "tree", ("a/", "b/", "a/notes.txt"))
        (self.root / "link").symlink_to(self.root / "a", target_is_directory=True)
        self.once = [os.path.realpath(self.root / rel) for rel in (".", "a", "b")]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _walk(self, extra=()):
        """List the root, ``a`` and ``b`` once each, then each path of ``extra``."""
        for rel in (".", "a", "b", *extra):
            with os.scandir(self.root / rel) as entries:
                list(entries)

    def test_a_walk_listing_each_directory_once_and_globbing_nothing_yields_no_finding(self):
        with _WalkRecorder() as recorder:
            self._walk()
        self.assertEqual(len(recorder.listed), 3, "precondition: the recorder saw each listing")
        self.assertEqual(_walk_findings(recorder, self.once, []), [])

    def test_a_second_listing_of_one_directory_is_reported(self):
        with _WalkRecorder() as recorder:
            self._walk(extra=("b",))
        self.assertEqual(_walk_findings(recorder, self.once, []),
                         [f"{self.once[2]}: listed 2 times, want once"])

    def test_a_listing_through_a_directory_symlink_counts_against_its_target(self):
        with _WalkRecorder() as recorder:
            self._walk(extra=("link",))
        self.assertEqual(_walk_findings(recorder, self.once, []),
                         [f"{self.once[1]}: listed 2 times, want once"])

    def test_a_listing_of_a_never_listed_directory_is_reported(self):
        never = [os.path.realpath(self.root / "b")]
        with _WalkRecorder() as recorder:
            self._walk()
        findings = _walk_findings(recorder, self.once[:2], never)
        self.assertEqual(findings, [f"{never[0]}: listed 1 times, want never"])

    def test_a_glob_call_is_reported_and_still_answers(self):
        with _WalkRecorder() as recorder:
            matches = sorted(p.name for p in (self.root / "a").glob("*.txt"))
        self.assertEqual(matches, ["notes.txt"], "the recorder passes the call through")
        globs = [f for f in _walk_findings(recorder, [], []) if f.startswith("Path.glob")]
        self.assertEqual(globs, [f"Path.glob called: {self.root / 'a'}.glob('*.txt')"])

    def test_the_recorder_restores_scandir_and_glob_on_exit(self):
        real_scandir, real_glob = os.scandir, Path.glob
        with _WalkRecorder():
            self.assertIsNot(os.scandir, real_scandir, "precondition: scandir is wrapped")
        self.assertIs(os.scandir, real_scandir)
        self.assertIs(Path.glob, real_glob)


class HookModuleLoaderTest(unittest.TestCase):
    """CR-MDB-066 AC5 — ``tests._helpers.load_hook_module`` loads a hook in process with
    bytecode writing off for the load and restored after it. Passes on arrival (RED writes the
    loader); proved both ways in a temp directory: a plain ``SourceFileLoader`` load there writes
    a ``__pycache__``, the helper's writes none."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="modelb-hook-loader-", dir="/tmp"))
        self.saved = sys.dont_write_bytecode

    def tearDown(self):
        sys.dont_write_bytecode = self.saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _copy(self, name, directory):
        directory.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(HOOK_SCRIPTS_DIR / name, directory / name)
        return directory

    def test_a_plain_source_file_load_writes_bytecode_beside_the_hook(self):
        # The bite: what the helper must prevent happens to a load that leaves the flag on.
        directory = self._copy("block-direct-cargo-test", self.tmp / "plain")
        sys.dont_write_bytecode = False
        loader = importlib.machinery.SourceFileLoader("plain_hook",
                                                      str(directory / "block-direct-cargo-test"))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        self.assertIsNotNone(spec, "precondition: a module spec for the copy")
        assert spec is not None  # narrows the type for the checker
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        self.assertTrue((directory / "__pycache__").is_dir())

    def test_the_helper_writes_no_bytecode_and_restores_the_flag(self):
        for spec in RUNNER_HOOKS.values():
            directory = self._copy(spec["script"], self.tmp / "helper")
            for flag in (False, True):
                with self.subTest(hook=spec["script"], dont_write_bytecode=flag):
                    sys.dont_write_bytecode = flag
                    with mock.patch.object(_helpers, "HOOK_SCRIPTS_DIR", directory):
                        module = load_hook_module(spec["script"])
                    restored = sys.dont_write_bytecode
                    sys.dont_write_bytecode = self.saved
                    self.assertIs(restored, flag)
                    self.assertNotEqual(module.__name__, "__main__")
                    self.assertTrue(callable(module._in_project))
                    self.assertFalse((directory / "__pycache__").exists(),
                                     "the helper wrote bytecode beside the hook")

    def test_each_load_is_a_fresh_module_and_none_lands_in_hooks_src(self):
        for spec in RUNNER_HOOKS.values():
            with self.subTest(hook=spec["script"]):
                first = load_hook_module(spec["script"])
                self.assertIsNot(load_hook_module(spec["script"]), first)
                self.assertNotIn(first.__name__, sys.modules)
        self.assertFalse((HOOK_SCRIPTS_DIR / "__pycache__").exists(),
                         "a __pycache__ landed under hooks-src/scripts/")


class _MarkerWalk(_MixinBase):
    """CR-MDB-066 §S4 (AC5): one listing per directory, a by-name fallback for a directory that
    can be searched but not listed, a marker only when ``os.path.isfile`` accepts it."""

    def chmod(self, path, mode):
        """chmod ``path`` to ``mode`` (restored to 0o755 in tearDown)."""
        self.locked.append(path)
        path.chmod(mode)

    def literal_markers(self):
        """This stack's marker names, ``requirements*.txt`` (a pattern) aside."""
        return tuple(m for m in self.spec["markers"] if not m.startswith("requirements"))

    def test_the_walk_lists_each_directory_once_and_never_globs(self):
        # Fails today: the walk lists no directory 3 levels down (``a/b/c``'s markers are read
        # by name); python's ``_has_marker`` also globs ``requirements*.txt`` in every directory.
        root = build_tree(self.tmp / "walk", WALK_TREE_DIRS, git="dir")
        (root / "link").symlink_to(root / "a", target_is_directory=True)
        once = [os.path.realpath(root / rel) for rel in WALK_LISTED_ONCE]
        never = [os.path.realpath(root / rel) for rel in WALK_NEVER_LISTED]
        for cwd in (root, root / "e" / "f"):
            with self.subTest(cwd=str(cwd.relative_to(root))):
                module = load_hook_module(self.spec["script"])  # fresh: no state carried over
                with _WalkRecorder() as recorder:
                    in_project = module._in_project(str(cwd))
                self.assertIs(in_project, False, "precondition: the tree holds no marker")
                findings = _walk_findings(recorder, once, never)
                self.assertEqual(findings, [], f"CR-MDB-066 §S4.1: {self.spec['script']} "
                                 "lists a directory other than once, or globs:\n  "
                                 + "\n  ".join(findings))

    def test_an_execute_only_directory_still_counts_a_literal_marker_it_holds(self):
        # Passes on arrival (today reads markers by name); fails against a §S4 that drops a
        # directory it cannot list instead of checking it by name (§S4.2).
        for marker in self.literal_markers():
            with self.subTest(marker=marker):
                root = build_tree(self.tmp / f"xo-{marker}", [f"xo/{marker}", "README.md"],
                                  git="dir")
                self.chmod(root / "xo", 0o111)
                self.assertVerdict("block", self.run_cmd, root,
                                   f"(xo/{marker} in an execute-only directory below the root)")
                self.assertVerdict("block", self.run_cmd, root / "xo",
                                   f"({marker} in the execute-only cwd)")

    def test_an_execute_only_directory_is_not_descended(self):
        # Passes on arrival; fails against a §S4 that walks on below a directory it cannot list.
        root = build_tree(self.tmp / "xo-below", [f"xo/inner/{self.marker}", "README.md"],
                          git="dir")
        self.chmod(root / "xo", 0o111)
        self.assertVerdict("allow", self.run_cmd, root,
                           "(the only marker is below an execute-only directory)")

    def test_a_read_only_directory_below_the_root_hides_the_marker_it_holds(self):
        # Passes on arrival; fails against a §S4 that asks ``DirEntry.is_file()`` (answered
        # from ``d_type``, so it accepts the marker the precondition below shows) or none.
        for marker in self.spec["markers"]:
            with self.subTest(marker=marker):
                root = build_tree(self.tmp / f"ro-{marker}", [f"ro/{marker}", "README.md"],
                                  git="dir")
                self.chmod(root / "ro", 0o444)
                with os.scandir(root / "ro") as entries:
                    listed = {e.name: e.is_file() for e in entries}
                self.assertEqual(listed, {marker: True},
                                 "precondition: the read-only directory lists the marker and "
                                 "DirEntry.is_file() accepts it")
                self.assertFalse(os.path.isfile(root / "ro" / marker),
                                 "precondition: os.path.isfile cannot stat inside it")
                self.assertVerdict("allow", self.run_cmd, root,
                                   f"(ro/{marker} in a read-only directory below the root)")

    def test_a_marker_named_symlink_loop_is_no_marker_and_does_not_stop_the_walk(self):
        # Passes on arrival; fails against a §S4 that asks ``DirEntry.is_file()`` (it raises on
        # the loop, and the raise reads as "not a project") or that counts a name alone.
        root = build_tree(self.tmp / "loop", [f"a/{self.marker}"], git="dir")
        (root / self.marker).symlink_to(self.marker)
        self.assertVerdict("block", self.run_cmd, root,
                           f"(a {self.marker} symlink loop at the root, a/{self.marker} below)")
        alone = build_tree(self.tmp / "loop-alone", ["README.md"], git="dir")
        (alone / self.marker).symlink_to(self.marker)
        self.assertVerdict("allow", self.run_cmd, alone,
                           f"(the only {self.marker} is a symlink loop)")

    def test_a_directory_named_like_a_marker_is_no_marker(self):
        # Passes on arrival; fails against a §S4 that counts a listed name without
        # ``os.path.isfile``.
        for marker in self.spec["markers"]:
            with self.subTest(marker=marker):
                root = build_tree(self.tmp / f"dir-{marker}", [f"{marker}/", f"a/{marker}/"],
                                  git="dir")
                self.assertVerdict("allow", self.run_cmd, root,
                                   f"(only directories named {marker})")

    def test_the_hook_docstring_states_where_it_applies_citing_section_s4(self):
        # CR-MDB-066 §S7.2 (AC9): the "Where it applies" paragraph states §S4's walk.
        source = (HOOK_SCRIPTS_DIR / self.spec["script"]).read_text(encoding="utf-8")
        doc = ast.get_docstring(ast.parse(source)) or ""
        paragraphs = [p for p in doc.split("\n\n") if p.startswith("Where it applies")]
        self.assertEqual(len(paragraphs), 1, "precondition: one 'Where it applies' paragraph")
        self.assertIn("CR-MDB-066 §S4", paragraphs[0],
                      f"CR-MDB-066 §S7.2: {self.spec['script']}'s 'Where it applies'")


class PythonHookMarkerWalkTest(_MarkerWalk, _RunnerHookCase):
    HOOK = "python"

    def test_an_execute_only_directory_hides_a_requirements_file_it_holds(self):
        # Passes on arrival (a glob cannot list it); fails against a §S4 whose by-name
        # fallback guesses ``requirements*.txt`` names (§S4.2).
        root = build_tree(self.tmp / "xo-req", ["xo/requirements.txt", "README.md"], git="dir")
        self.chmod(root / "xo", 0o111)
        self.assertVerdict("allow", self.run_cmd, root, "(xo/requirements.txt, xo execute-only)")
        self.assertVerdict("allow", self.run_cmd, root / "xo",
                           "(requirements.txt in the execute-only cwd)")

    def test_a_requirements_file_counts_at_every_depth_the_walk_looks(self):
        # Passes on arrival; fails against a §S4 that matches ``requirements*.txt`` in some
        # listings only (the parents', or the walk's below the root).
        cases = (("requirements_test.txt", "e/f", "block", "at the root, cwd e/f"),
                 ("e/requirements-dev.txt", "e/f", "block", "in the cwd's parent"),
                 ("a/b/c/requirements.txt", ".", "block", "3 levels below the root"),
                 ("a/b/c/d/requirements.txt", ".", "allow", "4 levels below the root"))
        for index, (rel, cwd_rel, expected, why) in enumerate(cases):
            with self.subTest(marker=rel):
                root = build_tree(self.tmp / f"req-{index}", [rel, "e/f/"], git="dir")
                self.assertVerdict(expected, self.run_cmd, root / cwd_rel, f"({rel}, {why})")


class BunHookMarkerWalkTest(_MarkerWalk, _RunnerHookCase):
    HOOK = "bun"


class CargoHookMarkerWalkTest(_MarkerWalk, _RunnerHookCase):
    HOOK = "cargo"


class MvnHookMarkerWalkTest(_MarkerWalk, _RunnerHookCase):
    HOOK = "mvn"


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

    def test_allows_a_hostile_payload_without_a_traceback(self):
        """Nesting past the recursion limit, open or closed, and a number past the digit limit:
        ``json.load`` raises on each, and the hook allows."""
        project = self.project()
        depth = 100_000
        for name, raw in (("open array", "[" * depth), ("closed array", "[" * depth + "]" * depth),
                          ("nested object", '{"a":' * depth + "1" + "}" * depth),
                          ("long number", "1" * 5000)):
            with self.subTest(payload=name):
                self.assertEqual(self.verdict(raw, proc_cwd=project), "allow")

    def test_allows_an_untokenisable_command(self):
        project = self.project()
        for command in (f"{self.run_cmd} 'unterminated", f'{self.run_cmd} "unterminated'):
            with self.subTest(command=command):
                self.assertVerdict("allow", command, project)

    def test_allows_a_client_invocation(self):
        project = self.project()
        self.assertVerdict("allow", self.CLIENT_RUN, project)

    def test_judges_a_long_run_of_interpreter_options_within_the_budget(self):
        project = self.project()
        for command, stack in OPTION_RUNS:
            with self.subTest(command=command[:40]):
                start = time.perf_counter()
                got = self.verdict(self.bash(command, project))
                elapsed = time.perf_counter() - start
                self.assertEqual(got, "block" if stack == self.HOOK else "allow", command)
                self.assertLess(elapsed, OPTION_RUN_BUDGET,
                                f"{self.spec['script']} took {elapsed:.2f}s on {command!r}")

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


# ----------------------------------------------------------------- source identity ----

#: CR-MDB-066 AC10 — the shared parser and walk every runner hook carries its own copy of: each
#: must exist in all four hooks with the same source.
SHARED_DEFINITIONS = ("_SEPARATOR", "_HEREDOC", "_ENV_OPTION", "_TIMEOUT_OPTION", "_WRAPPER",
                      "_skip_heredoc_bodies", "_segments", "_commands", "_shell_words",
                      "_marker_below", "_in_project")
#: CR-MDB-066 AC10 — the per-stack names all four hooks define, each with its own source.
PER_STACK_DEFINITIONS = frozenset({"MARKERS", "REASON", "_has_marker", "main"})


def _top_level_definitions(source):
    """``{name: source}`` for each top-level definition in ``source`` (CR-MDB-066 AC10): a
    ``def`` by its whole ``ast.unparse``, an assignment to a name by its value's."""
    definitions = {}
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definitions[node.name] = ast.unparse(node)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    definitions[target.id] = ast.unparse(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) \
                and node.value is not None:
            definitions[node.target.id] = ast.unparse(node.value)
    return definitions


def _source_identity_failures(sources):
    """Each way the hooks in ``sources`` (``{script: source}``) break CR-MDB-066 AC10, naming the
    definition: a ``SHARED_DEFINITIONS`` name missing from a hook, and a shared name — one of
    ``SHARED_DEFINITIONS`` or any other all the hooks define, ``PER_STACK_DEFINITIONS`` aside —
    whose copies differ. ``[]`` when the copies are identical."""
    defined = {script: _top_level_definitions(source) for script, source in sources.items()}
    failures = [f"{script}: {name} is not defined" for name in SHARED_DEFINITIONS
                for script, names in defined.items() if name not in names]
    common = set.intersection(*(set(names) for names in defined.values()))
    for name in sorted((common | set(SHARED_DEFINITIONS)) - PER_STACK_DEFINITIONS):
        copies = {}
        for script, names in defined.items():
            if name in names:
                copies.setdefault(names[name], []).append(script)
        if len(copies) > 1:
            groups = " | ".join(", ".join(scripts) for scripts in copies.values())
            failures.append(f"{name}: {len(copies)} different copies ({groups})")
    return failures


#: A synthetic runner hook for the AC10 detector's proof: every shared definition, the per-stack
#: four (filled per copy), a shared extra helper, ``_shared_extra``.
_SYNTHETIC_HOOK = '''
import re

MARKERS = ({marker!r},)
REASON = {reason!r}
_SEPARATOR = re.compile(";")
_HEREDOC = re.compile("<<")
_ENV_OPTION = "-i"
_TIMEOUT_OPTION = "-k"
_WRAPPER = re.compile("env")


def _skip_heredoc_bodies(text, index, pending):
    return index


def _segments(text):
    return [(0, len(text))]


def _commands(text):
    return [text]


def _shell_words(segment):
    return segment.split()


def _has_marker(directory):
    return {marker!r} in directory


def _marker_below(root, depth):
    return False


def _in_project(cwd):
    return bool(cwd)


def _shared_extra(value):
    return value


def main():
    return {code}
'''


class RunnerHookSourceIdentityTest(unittest.TestCase):
    """CR-MDB-066 AC10 — the four runner hooks' copies of the shared parser and walk stay one
    source: every ``SHARED_DEFINITIONS`` name exists in each with the same ``ast.unparse``, and
    so does every other name all four define, ``PER_STACK_DEFINITIONS`` aside.

    Passes on arrival (CR-MDB-066's cycle plan, item 1): all eleven names are identical today.
    It guards cycles 1–3's edits to the hooks' copies; its detector is proved both ways on
    synthetic sources first."""

    def _synthetic(self):
        """Four synthetic hooks, identical but for the per-stack four."""
        return {f"block-direct-{stack}-test": _SYNTHETIC_HOOK.format(
                    marker=spec["markers"][0], reason=f"blocked: {spec['run']}", code=index)
                for index, (stack, spec) in enumerate(RUNNER_HOOKS.items())}

    def test_identical_copies_differing_only_in_the_per_stack_four_pass(self):
        sources = self._synthetic()
        self.assertEqual(len(set(sources.values())), 4, "precondition: the per-stack four differ")
        self.assertEqual(_source_identity_failures(sources), [])

    def test_a_changed_named_copy_is_reported_by_name(self):
        sources = self._synthetic()
        sources["block-direct-mvn-test"] = sources["block-direct-mvn-test"].replace(
            "return [(0, len(text))]", "return []")
        failures = _source_identity_failures(sources)
        self.assertEqual(len(failures), 1, failures)
        self.assertTrue(failures[0].startswith("_segments: 2 different copies"), failures)
        self.assertIn("block-direct-mvn-test", failures[0])

    def test_a_missing_named_definition_is_reported_by_name(self):
        sources = self._synthetic()
        sources["block-direct-bun-test"] = sources["block-direct-bun-test"].replace(
            '_HEREDOC = re.compile("<<")\n', "")
        self.assertEqual(_source_identity_failures(sources),
                         ["block-direct-bun-test: _HEREDOC is not defined"])

    def test_a_shared_extra_helper_changed_in_one_copy_is_reported_by_name(self):
        sources = self._synthetic()
        sources["block-direct-cargo-test"] = sources["block-direct-cargo-test"].replace(
            "    return value\n", "    return not value\n")
        failures = _source_identity_failures(sources)
        self.assertEqual(len(failures), 1, failures)
        self.assertTrue(failures[0].startswith("_shared_extra: 2 different copies"), failures)

    def test_a_helper_not_all_four_define_is_not_compared(self):
        sources = self._synthetic()
        sources["block-direct-python-test"] += "\n\ndef _own_helper():\n    return 1\n"
        sources["block-direct-bun-test"] += "\n\ndef _own_helper():\n    return 2\n"
        self.assertEqual(_source_identity_failures(sources), [])

    def test_the_four_runner_hooks_share_one_source_for_the_parser_and_the_walk(self):
        sources = {spec["script"]: (HOOK_SCRIPTS_DIR / spec["script"]).read_text(encoding="utf-8")
                   for spec in RUNNER_HOOKS.values()}
        failures = _source_identity_failures(sources)
        self.assertEqual(failures, [], "CR-MDB-066 AC10: the runner hooks' shared copies "
                         "diverge:\n  " + "\n  ".join(failures))


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
    # CR-MDB-066 §S8.2 — passes on arrival: it pins today's block. §S1.4's substitution
    # leaves its enclosing segment unchanged, so the words after the closing backquote stay
    # Maven's arguments and ``test`` is still its goal.
    ("mvn -Drevision=`git describe` test", "mvn"),
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
    ``CLIENT_FORMS`` and ``NON_RUNNER_MENTIONS``, its CR-MDB-062 and CR-MDB-066 corpora,
    ``MODULE_FORMS`` and ``PARITY_FORMS`` — the arduino (``make``) entries left out."""
    # MIGRATED at CR-MDB-066 (§S8.2): GRAMMAR_FORMS joins the labelled corpora and
    # GRAMMAR_NON_RUNNERS the plain ones.
    # MIGRATED at CR-MDB-066 (§S8.2, §S2): PACKAGE_MANAGER_FORMS, FILTER_FORMS and VITEST_FORMS
    # join the labelled corpora and BUN_NON_RUNNERS the plain ones.
    labelled = (RUNNER_FORMS + WRAPPED_FORMS + POSITION_FORMS + ATTACHED_M_FORMS + UV_RUN_FORMS
                + TEST_FILE_FORMS + BUN_SCRIPT_FORMS + GRAMMAR_FORMS + PACKAGE_MANAGER_FORMS
                + FILTER_FORMS + VITEST_FORMS + MODULE_FORMS + PARITY_FORMS)
    plain = (CLIENT_FORMS + NON_RUNNER_MENTIONS + NARROWED_BUN_SCRIPTS + HEREDOC_BODIES
             + QUOTED_LINES + NON_TEST_SCRIPTS + ARGUMENT_MENTIONS + GRAMMAR_NON_RUNNERS
             + BUN_NON_RUNNERS)
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
        # MIGRATED at CR-MDB-066 (§S8.2): the grammar corpora are in the corpus too.
        for command in ("python3 -m unittest", "bun test", "cargo test", "mvn test", "(mvn test)",
                        CLIENT_FORMS[0], NON_RUNNER_MENTIONS[0], NARROWED_BUN_SCRIPTS[0],
                        HEREDOC_BODIES[0], NON_TEST_SCRIPTS[0], ARGUMENT_MENTIONS[0],
                        GRAMMAR_FORMS[0][0], GRAMMAR_NON_RUNNERS[0],
                        # MIGRATED at CR-MDB-066 (§S8.2): the §S2 bun corpora too.
                        PACKAGE_MANAGER_FORMS[0][0], FILTER_FORMS[0][0], VITEST_FORMS[0][0],
                        BUN_NON_RUNNERS[0]):
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
