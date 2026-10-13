"""The raw-runner guard — CR-MDB-056 §S3.

Contract: ``docs/changes/CR-MDB-056-tests-run-only-through-crucible-clients.md`` §S3 (design
reference DN-multi-harness-deploy-model §D21 and its 2026-10-13 amendments). Every test run goes
through the stack's Crucible client, so no guarded file shows a runner invocation as something to
type: a guarded file fails when it shows a runner invocation in a code span or on a fenced-block
line, unless a prohibition governs it — a whole-word, case-insensitive "never", "do not", "must
not" or "not" earlier in the same clause as the runner span. A fenced-block line is judged on
its own; prose around a fence never exempts it.

**The runner** is matched as a whole command word at a command position — the start of the span
or line, or after ``&&``, ``||``, ``;``, ``|``, a leading ``VAR=value``, or one of ``env`` (with
any options, e.g. ``env -i``, ``env -u NAME``), ``timeout <n>``, ``nice``, ``time``
(``runner_at``):

- a python interpreter (bare, versioned or a path), with any options, then ``-m unittest``,
  ``-m pytest``, ``-m xmlrunner`` or ``-m coverage run``;
- ``pytest`` or ``py.test`` (bare or a path), ``uv run pytest``, ``coverage run -m <runner>``;
- ``bun test``, ``bun run test…``, ``npm test``, ``npm run test…``, ``bunx``/``bun x``/``npx``
  ``playwright test``, ``playwright test``;
- ``cargo test``, ``cargo nextest``, ``cargo llvm-cov``;
- ``mvn``/``mvnw``/``./mvnw`` with the goal ``test``, ``verify``, ``integration-test`` or
  ``test-compile``, or a ``surefire:``/``failsafe:`` goal (exact goals);
- ``make junit``.

A client invocation (``<stack>-crucible.py …``) and a non-runner mention (``[tool.pytest]``,
``pytest.ini``, ``pytest-cov``, ``/tmp/pytest-collect.txt``, ``mvn package``) are never runner
invocations.

**Guarded** (``GUARDED_ROOTS``): ``skills-src/`` except ``skills-src/memory-templates/``,
``contracts/``, ``AGENTS.md``, ``generator/templates/``, ``generator/stacks/``,
``generator/agents/`` and ``.pi/agents/``.

How a text is read (``runner_findings``): a fence is a line opening with three or more backticks
or tildes; each line inside it is one command line, judged alone. Outside fences, a block is a
paragraph or a list item with its wrapped lines; a heading and a table row are blocks of their
own. A code span is a backtick run closed by a run of the same length, and may wrap a line. A
sentence ends at ``.``, ``!`` or ``?`` before whitespace (not after ``e.g.``, ``i.e.``, ``cf.``,
``vs.``), at a table-cell ``|`` and at the block's edge; a clause ends there too, and also at
``;`` and ``:``, so a prohibition governs a span only in its own clause ("Do not stop: run
`pytest`." is caught). Code-span contents never end a sentence or a clause and never supply a
prohibition word. A known limit: a comma does not end a clause, so "If the build is not green,
run `cargo test`." is read as governed — commas are not parsed.

The detector is a pure function proved on sample text both ways in
``RawRunnerDetectorOnSampleTextTest`` before ``GuardedTreeHasNoRawRunnerTest`` applies it to the
tree. Stdlib only.
"""

import os
import re
import unittest
from pathlib import Path

from tests._helpers import REPO_ROOT, read_text

#: §S3's guarded set, relative to the repository root: a directory guards every file under it.
GUARDED_ROOTS = (
    "skills-src",
    "contracts",
    "AGENTS.md",
    "generator/templates",
    "generator/stacks",
    "generator/agents",
    ".pi/agents",
)
#: The one carve-out from §S3's guarded set (CR-MDB-060 carries the rule into the facts).
GUARD_EXCLUDED = ("skills-src/memory-templates",)

#: Where a runner command word ends: whitespace, the fragment's end, or closing punctuation.
_END = r"(?=$|[\s)\"'`,])"
#: A command separator; the text after one is a command position.
_SEPARATOR = re.compile(r"&&|\|\||;|\|")
#: ``env``'s options: ``-u NAME``/``-C DIR`` and their long forms take an argument; any other
#: option stands alone. Assignments after ``env`` are matched as ``VAR=value`` wrappers.
_ENV_OPTION = (r"(?:-[uC]\s*\S+|--(?:unset|chdir)(?:=\S+|\s+\S+)"
               r"|-{1,2}[A-Za-z0-9][\w-]*(?:=\S+)?)")
#: A wrapper before a command: ``VAR=value``, ``env [options]``, ``timeout <n>``, ``nice``,
#: ``time``.
_WRAPPER = re.compile(
    r"(?:[A-Za-z_][A-Za-z0-9_]*=(?:\"[^\"]*\"|'[^']*'|\S*)|env(?:\s+" + _ENV_OPTION + r")*"
    r"|timeout\s+\S+|nice|time)(?:\s+|$)")
#: The runners §S3 lists, each anchored at a command position.
_RUNNERS = (
    re.compile(r"(?:\S*/)?python(?:\d+(?:\.\d+)*)?(?=\s)"
               r"(?:\s+(?:-[WX]\s*\S+|-(?!m(?:\s|$))\S+))*"
               r"\s+-m\s+(?:unittest|pytest|xmlrunner|coverage\s+run)" + _END),
    re.compile(r"(?:\S*/)?(?:pytest|py\.test)" + _END),
    re.compile(r"uv\s+run\s+(?:pytest|py\.test)" + _END),
    re.compile(r"coverage\s+run(?:\s+-(?!m(?:\s|$))\S+)*\s+-m\s+\S+"),
    re.compile(r"bun\s+test" + _END),
    re.compile(r"(?:bun|npm)\s+run\s+test\S*"),
    re.compile(r"npm\s+test" + _END),
    re.compile(r"(?:(?:bunx|bun\s+x|npx)\s+)?playwright\s+test" + _END),
    re.compile(r"cargo\s+(?:test|nextest|llvm-cov)" + _END),
    re.compile(r"make\s+junit" + _END),
)
#: Maven's launcher words and the goals that run tests (exact goals).
_MAVEN = re.compile(r"(?:mvn|mvnw|\./mvnw)" + _END)
_MAVEN_TEST_GOALS = frozenset({"test", "verify", "integration-test", "test-compile"})
_MAVEN_TEST_PLUGINS = ("surefire:", "failsafe:")

#: A whole-word, case-insensitive prohibition ("do not" and "must not" end in "not").
PROHIBITION = re.compile(r"\b(?:never|do\s+not|must\s+not|not)\b", re.IGNORECASE)
#: A sentence boundary in masked prose: terminal punctuation before whitespace, or a table cell.
_SENTENCE_END = re.compile(r"(?<!\be\.g)(?<!\bi\.e)(?<!\bcf)(?<!\bvs)[.!?](?=\s|$)|\|")
#: A clause boundary: a sentence boundary, ``;`` or ``:`` — a prohibition governs its own clause.
_CLAUSE_END = re.compile(_SENTENCE_END.pattern + r"|[;:]")
#: A fence opener or closer: three or more backticks or tildes.
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
#: A line that opens a block of its own: a heading, a list item, a table row.
_BLOCK_START = re.compile(r"^\s*(?:#{1,6}\s|[-*+]\s|\d+[.)]\s|\|)")
#: A blockquote marker: a quoted line is read as the line it quotes.
_QUOTE = re.compile(r"^\s*(?:>\s?)+")


def _is_maven_test_run(segment: str) -> bool:
    """True when ``segment`` starts with a Maven launcher and names a test goal (exact goals)."""
    if not _MAVEN.match(segment):
        return False
    goals = segment.split()[1:]
    return any(g in _MAVEN_TEST_GOALS or g.startswith(_MAVEN_TEST_PLUGINS) for g in goals)


def runner_at(fragment: str):
    """The offset in ``fragment`` where a §S3 runner command starts at a command position, or
    ``None``. ``fragment`` is a code span's content or one fenced line."""
    position = 0
    for piece in _SEPARATOR.split(fragment):
        start = position + len(piece) - len(piece.lstrip())
        segment = piece.lstrip()
        while True:
            wrapper = _WRAPPER.match(segment)
            if not wrapper or not wrapper.group(0):
                break
            start += wrapper.end()
            segment = segment[wrapper.end():]
        if any(r.match(segment) for r in _RUNNERS) or _is_maven_test_run(segment):
            return start
        separator = _SEPARATOR.match(fragment, position + len(piece))
        position += len(piece) + (len(separator.group(0)) if separator else 0)
    return None


def _governed(masked_prefix: str) -> bool:
    """True when a prohibition appears in the clause ``masked_prefix`` ends in."""
    boundaries = list(_CLAUSE_END.finditer(masked_prefix))
    clause = masked_prefix[boundaries[-1].end():] if boundaries else masked_prefix
    return bool(PROHIBITION.search(clause))


def _code_spans(text: str):
    """Yield ``(start, end, content)`` for each code span in ``text`` (``start``/``end`` cover
    the backticks): a backtick run closed by the next run of the same length."""
    i = 0
    while i < len(text):
        if text[i] != "`":
            i += 1
            continue
        length = len(text[i:]) - len(text[i:].lstrip("`"))
        run = "`" * length
        closer = re.compile(rf"(?<!`){run}(?!`)")
        close = closer.search(text, i + len(run))
        if not close:
            i += len(run)
            continue
        yield i, close.end(), text[i + len(run):close.start()].replace("\n", " ").strip()
        i = close.end()


def _blocks(lines: list[str]):
    """Yield ``(first_line_index, block_lines)`` for the prose blocks and ``(index, None)`` for
    each fenced line — fenced lines come back one by one, to be judged alone."""
    fence, block, first = None, [], 0
    for index, line in enumerate(lines):
        opener = _FENCE.match(line)
        if fence is not None:
            if opener and opener.group(1)[0] == fence[0] and len(opener.group(1)) >= len(fence) \
                    and not line.strip()[len(opener.group(1)):].strip():
                fence = None
            else:
                yield index, None
            continue
        if opener:
            if block:
                yield first, block
            fence, block = opener.group(1), []
            continue
        if not line.strip() or _BLOCK_START.match(line):
            if block:
                yield first, block
            block = []
            if not line.strip():
                continue
            if re.match(r"^\s*(?:#{1,6}\s|\|)", line):
                yield index, [line]
                continue
        if not block:
            first = index
        block.append(line)
    if block:
        yield first, block


def runner_findings(text: str) -> list[tuple[int, str]]:
    """Every ungoverned runner invocation ``text`` shows, as ``(line_number, shown)`` — the
    1-based line and the code span's content or the fenced line, stripped."""
    lines = [_QUOTE.sub("", line) for line in text.splitlines()]
    findings = []
    for first, block in _blocks(lines):
        if block is None:
            line = lines[first]
            start = runner_at(line)
            if start is not None and not _governed(line[:start]):
                findings.append((first + 1, line.strip()))
            continue
        joined = "\n".join(block)
        spans = list(_code_spans(joined))
        masked = list(joined)
        for start, end, _content in spans:
            masked[start:end] = "x" * (end - start)
        masked = "".join(masked)
        for start, _end, content in spans:
            if runner_at(content) is not None and not _governed(masked[:start]):
                findings.append((first + joined.count("\n", 0, start) + 1, content))
    return findings


def guarded_files(root: Path = REPO_ROOT) -> list[Path]:
    """Every file §S3 guards under ``root``, sorted."""
    files = []
    for entry in GUARDED_ROOTS:
        path = root / entry
        if path.is_file():
            files.append(path)
            continue
        for directory, _dirs, names in os.walk(path):
            files.extend(Path(directory) / name for name in names)
    excluded = [root / e for e in GUARD_EXCLUDED]
    return sorted(f for f in files if not any(f.is_relative_to(e) for e in excluded))


# ------------------------------------------------------------------ sample text ----

#: Each runner form §S3 lists, as it would be shown to be typed.
RUNNER_FORMS = (
    "python -m unittest",
    "python3 -m unittest discover -s tests -t .",
    "python3.14 -m unittest tests.test_hooks",
    ".venv/bin/python -m pytest -q",
    "/usr/bin/python3 -W error -m xmlrunner discover",
    "python3 -B -m coverage run -m unittest",
    "pytest",
    "pytest -x tests/",
    ".venv/bin/pytest tests/ --junitxml=test-reports/junit.xml",
    "py.test",
    "uv run pytest",
    "coverage run -m unittest",
    "coverage run --branch -m pytest",
    "bun test",
    "bun test --reporter=junit",
    "bun run test",
    "bun run test:unit",
    "npm test",
    "npm run test:e2e",
    "bunx playwright test",
    "bun x playwright test --grep login",
    "npx playwright test",
    "playwright test",
    "cargo test",
    "cargo test --workspace",
    "cargo nextest run",
    "cargo llvm-cov --lcov --output-path lcov.info",
    "mvn test",
    "mvn -q clean test-compile",
    "mvnw verify",
    "./mvnw integration-test",
    "mvn surefire:test",
    "mvn -Dit.test=FooIT failsafe:integration-test",
    "make junit",
)

#: Each command position §S3 lists that is not the start: a wrapper or a separator.
WRAPPED_FORMS = (
    "env HOME=/tmp/h pytest",
    "env python3 -m unittest",
    "HOME=/tmp/h python3 -m unittest",
    "ALLOW_RAW_PYTEST=1 pytest",
    "timeout 600 cargo test",
    "nice bun test",
    "time mvn verify",
    "cd tests/native && make junit",
    "false || npm test",
    "cd crates/core; cargo nextest run",
    "echo tests | pytest",
    "env FOO=1 timeout 60 nice time pytest",
    "env -i HOME=/tmp/h pytest",
    "env -u PYTHONPATH python3 -m unittest",
    "env --unset=FOO -i cargo test",
    "env -C tests/native HOME=/tmp/h make junit",
)

#: Client invocations: never runners.
CLIENT_FORMS = (
    "python3 ~/.crucible/clients/python-crucible.py test --tests tests.test_hooks --agent A",
    "python-crucible.py regression --coverage --agent vidushi-mdb",
    "python-crucible.py test --python python3.11 --agent A",
    "bun-crucible.py test --tests src/a.test.ts --agent A",
    "bun-crucible.py integration --agent A",
    "rust-crucible.py test --agent A",
    "java-crucible.py compile --agent A",
    "arduino-crucible.py test --agent A",
)

#: The non-runner mentions §S3 lists: never runners.
NON_RUNNER_MENTIONS = (
    "[tool.pytest]",
    "pytest.ini",
    "pytest-cov",
    "/tmp/pytest-collect.txt",  # noqa: S108 — §S3's sample mention, never opened
    "mvn package",
)


class RawRunnerDetectorOnSampleTextTest(unittest.TestCase):
    """§S3 — the detector, proved on sample text both ways before it is applied to the tree."""

    def assertCaught(self, text: str, expected: list[tuple[int, str]]):
        self.assertEqual(runner_findings(text), expected, f"for sample text:\n{text}")

    def test_each_runner_form_in_a_code_span_is_caught_as_an_instruction(self):
        for form in RUNNER_FORMS:
            with self.subTest(form=form):
                self.assertCaught(f"Run `{form}` from the project root.", [(1, form)])

    def test_each_runner_form_on_a_fenced_line_is_caught(self):
        for form in RUNNER_FORMS:
            with self.subTest(form=form):
                self.assertCaught(f"Iterate:\n\n```bash\n{form}\n```\n", [(4, form)])

    def test_each_wrapper_and_separator_is_a_command_position(self):
        for form in WRAPPED_FORMS:
            with self.subTest(form=form):
                self.assertCaught(f"Then `{form}` once.", [(1, form)])
                self.assertCaught(f"```\n{form}\n```", [(2, form)])

    def test_a_runner_word_away_from_a_command_position_is_not_a_runner(self):
        for text in ("Use `echo pytest` to print the word.", "Log `grep cargo test.log`.",
                     "```\ngit commit -m 'cargo test passes'\n```"):
            with self.subTest(text=text):
                self.assertCaught(text, [])

    def test_a_runner_word_must_be_whole(self):
        for text in ("See `pytester` and `cargo testing` and `bun tests`.",
                     "Use `pythonista -m unittest` and `mvn testx`."):
            with self.subTest(text=text):
                self.assertCaught(text, [])

    def test_each_governed_prohibition_exempts_the_span(self):
        for text in ("Never run `pytest` directly.",
                     "Do not use `bun test` here.",
                     "An agent must not call `cargo test`.",
                     "A runner is not invoked as `python3 -m unittest`.",
                     "NEVER type `mvn verify` yourself.",
                     "**Never** `npm test` — the client runs it.",
                     "do NOT run `make junit` by hand.",
                     "Never — not even once to look —\nrun `cargo nextest run` yourself.",
                     "> Run through the client. Do NOT\n> invoke `bun test` directly."):
            with self.subTest(text=text):
                self.assertCaught(text, [])

    def test_a_not_in_an_unrelated_clause_is_caught(self):
        cases = (
            ("Run `pytest` when the cache is not warm.", [(1, "pytest")]),
            ("This step is not optional. Run `cargo test` first.", [(1, "cargo test")]),
            ("Never skip a step.\nThen run `bun test --reporter=junit`.",
             [(2, "bun test --reporter=junit")]),
            ("| Never | `python3 -m unittest` |", [(1, "python3 -m unittest")]),
            ("You cannot skip it: run `npm test`.", [(1, "npm test")]),
            ("Notably, `mvn test` is fast.", [(1, "mvn test")]),
            ("> Never skip a step.\n> Run `pytest -q`.", [(2, "pytest -q")]),
        )
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertCaught(text, expected)

    def test_a_prohibition_governs_only_its_own_clause(self):
        cases = (
            ("Do not stop: run `pytest`.", [(1, "pytest")]),
            ("Never mind; run `cargo test`.", [(1, "cargo test")]),
            ("x; do not y; run `pytest`.", [(1, "pytest")]),
            ("> Never stop:\n> run `bun test` now.", [(2, "bun test")]),
        )
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertCaught(text, expected)
        for text in ("Never run `pytest`.",
                     "Do NOT invoke `bun test`/`make junit` directly.",
                     "Run it through the client: never `cargo test` yourself.",
                     "One rule; do not type `npm test`."):
            with self.subTest(text=text):
                self.assertCaught(text, [])

    def test_env_options_before_the_runner_are_part_of_the_wrapper(self):
        for text in ("Use `env -u pytest echo hi` to clear the variable.",
                     "Then `env -i HOME=/tmp/h ls` lists it.",
                     "Never `env -i HOME=/tmp/h pytest` by hand."):
            with self.subTest(text=text):
                self.assertCaught(text, [])
        self.assertCaught("```\nenv -i -u X HOME=/tmp/h bun test\n```",
                          [(2, "env -i -u X HOME=/tmp/h bun test")])

    def test_a_prohibition_in_one_block_does_not_govern_the_next(self):
        self.assertCaught("- Never hand-run a suite.\n- `pytest -x`", [(2, "pytest -x")])
        self.assertCaught("## Never\n\n`cargo test` is the loop.", [(3, "cargo test")])

    def test_a_prohibition_word_inside_a_code_span_does_not_govern(self):
        self.assertCaught("Pass `--not-cached`, then `pytest`.", [(1, "pytest")])

    def test_a_plain_words_description_is_not_caught(self):
        for text in ("The client runs the bun test runner with a JUnit reporter.",
                     "It runs cargo test under nextest and ingests the report.",
                     "Runs python -m unittest through xmlrunner, then ingests."):
            with self.subTest(text=text):
                self.assertCaught(text, [])

    def test_a_client_invocation_is_not_caught(self):
        for form in CLIENT_FORMS:
            with self.subTest(form=form):
                self.assertCaught(f"Run `{form}` now.", [])
                self.assertCaught(f"```bash\n{form}\n```", [])

    def test_each_non_runner_mention_is_not_caught(self):
        for mention in NON_RUNNER_MENTIONS:
            with self.subTest(mention=mention):
                self.assertCaught(f"See `{mention}` for the settings.", [])
                self.assertCaught(f"```\n{mention}\n```", [])

    def test_prose_above_a_fence_does_not_exempt_a_fenced_line(self):
        self.assertCaught("Never run these:\n\n```bash\npytest\ncargo test\n```\n",
                          [(4, "pytest"), (5, "cargo test")])
        self.assertCaught("Do not run the following.\n```\nbun test\n```", [(3, "bun test")])

    def test_a_fenced_line_is_judged_on_its_own(self):
        self.assertCaught("```\n# never run the next line\npytest\n```", [(3, "pytest")])
        self.assertCaught("```\npytest  # do not run this\n```", [(2, "pytest  # do not run this")])

    def test_a_fenced_line_after_the_fence_closes_is_prose_again(self):
        self.assertCaught("```\nls\n```\nNever `pytest`.\n```\nmake junit\n```",
                          [(6, "make junit")])

    def test_a_code_span_wrapped_over_a_line_is_one_span_on_its_first_line(self):
        self.assertCaught("Then run `python3 -m\nunittest discover` again.",
                          [(1, "python3 -m unittest discover")])


class GuardedSetTest(unittest.TestCase):
    """§S3 — the guard covers exactly the guarded set: every file under each guarded root, the
    memory templates excepted, and nothing outside it."""

    def setUp(self):
        self.files = guarded_files()
        self.relative = [f.relative_to(REPO_ROOT).as_posix() for f in self.files]

    def test_every_file_under_each_guarded_root_is_guarded(self):
        for entry in GUARDED_ROOTS:
            path = REPO_ROOT / entry
            expected = ([path] if path.is_file() else
                        [Path(d) / n for d, _s, names in os.walk(path) for n in names])
            expected = [p for p in expected
                        if not p.is_relative_to(REPO_ROOT / "skills-src" / "memory-templates")]
            with self.subTest(root=entry):
                self.assertTrue(expected, f"§S3's guarded {entry} is missing from the tree")
                self.assertEqual(sorted(set(expected) - set(self.files)), [])

    def test_the_guarded_set_names_each_root_of_section_s3(self):
        self.assertIn("AGENTS.md", self.relative)
        for prefix in ("skills-src/", "contracts/", "generator/templates/", "generator/stacks/",
                       "generator/agents/", ".pi/agents/"):
            with self.subTest(root=prefix):
                self.assertTrue(any(r.startswith(prefix) for r in self.relative))

    def test_the_memory_templates_are_outside_the_guard(self):
        memory = REPO_ROOT / "skills-src" / "memory-templates"
        self.assertTrue(any(memory.rglob("*")), "the carve-out must name a real directory")
        self.assertEqual([r for r in self.relative if r.startswith("skills-src/memory-templates/")],
                         [])

    def test_nothing_outside_the_guarded_set_is_guarded(self):
        roots = ("skills-src/", "contracts/", "generator/templates/", "generator/stacks/",
                 "generator/agents/", ".pi/agents/")
        stray = [r for r in self.relative if r != "AGENTS.md" and not r.startswith(roots)]
        self.assertEqual(stray, [])
        for outside in ("docs/", "tests/", "hooks-src/", "archive/", "audits/", "scripts/",
                        "generator/build.py", "modelb_axi/"):
            with self.subTest(outside=outside):
                self.assertFalse(any(r.startswith(outside) for r in self.relative))


class GuardedTreeHasNoRawRunnerTest(unittest.TestCase):
    """§S3 — no guarded file shows a runner invocation in a code span or on a fenced line
    outside a governed prohibition."""

    def test_no_guarded_file_shows_an_ungoverned_runner_invocation(self):
        found = []
        for path in guarded_files():
            for line, shown in runner_findings(read_text(path)):
                found.append(f"{path.relative_to(REPO_ROOT).as_posix()}:{line}: `{shown}`")
        self.assertEqual(found, [], "§S3: a guarded file shows a runner invocation outside a "
                         "governed prohibition — run it through the client, describe it in plain "
                         f"words, or govern it with a prohibition ({len(found)}):\n"
                         + "\n".join(found))


if __name__ == "__main__":
    unittest.main()
