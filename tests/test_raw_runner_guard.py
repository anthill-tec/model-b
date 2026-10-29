"""The raw-runner guard — CR-MDB-056 §S3, its detector reshaped by CR-MDB-062 §S1.

Contract: ``docs/changes/CR-MDB-062-blocking-hooks-for-python-and-bun.md`` §S1 (the per-stack
groups, the hooks' command positions, the three python forms) over
``docs/changes/CR-MDB-056-tests-run-only-through-crucible-clients.md`` §S3 (design reference
DN-multi-harness-deploy-model §D21 and its amendments). Every test run goes
through the stack's Crucible client, so no guarded file shows a runner invocation as something to
type: a guarded file fails when it shows a runner invocation in a code span or on a fenced-block
line, unless a prohibition governs it — a whole-word, case-insensitive "never", "do not", "must
not" or "not" earlier in the same clause as the runner span. A fenced-block line is judged on
its own; prose around a fence never exempts it.

**The runner** is matched as a whole command word at a command position — the hooks' set
(CR-MDB-062 §S1 item 2): every line start outside quotes and outside a heredoc body (``<<WORD``,
``<<'WORD'``, ``<<"WORD"``, ``<<-WORD`` up to the line ``WORD``), and after ``&&``, ``||``,
``;``, ``|``, ``&`` or ``(`` outside quotes; past a leading ``VAR=value``, ``env`` with any
options and assignments, ``timeout`` with any options and a duration, ``nice [-n N]`` and
``time`` (``runner_at``). CR-MDB-066 §S1 adds the shell grammar's positions: the reserved
words ``!``, ``{``, ``if``, ``then``, ``else``, ``elif``, ``while``, ``until`` and ``do``,
each a whole word before whitespace, are stepped over like a wrapper, in any order with the
others, and so are ``command [-p]`` (``command -v``/``-V`` run nothing and stay unmatched) and
``time [-p]``; an unquoted backquote opens a command substitution whose text, up to the
closing backquote, is one more position, its enclosing segment unchanged (a backquote in
quotes or a heredoc body opens nothing, an unclosed one reads as an unclosed quote); and an
unquoted ``$((…))`` or ``((…))`` is skipped whole up to the ``))`` that closes it, so
nothing in it is a position and no ``<<`` in it opens a heredoc. ``stack_of`` names the stack
of that runner. The forms, in per-stack
groups (§S1 item 1):

- ``PYTHON_RUNNERS``: a python interpreter (bare, versioned or a path), with any options, then
  ``-m unittest``, ``-m pytest``, ``-m xmlrunner`` or ``-m coverage run``, the ``-m`` separate or
  attached; ``pytest`` or ``py.test`` (bare or a path); ``coverage run [options] -m <module>``;
  a test file (``test_*.py``, ``*_test.py``) run directly by an interpreter. ``uv run`` with
  its options (and their values) is a command position before any of these;
- ``BUN_RUNNERS``: ``bun test``, ``bun run test``/``npm run test`` alone or as ``test:<name>``,
  ``npm test``, ``bunx``/``bun x``/``npx`` ``playwright test``, ``playwright test``;
- ``CARGO_RUNNERS``: ``cargo test``, ``cargo nextest``, ``cargo llvm-cov``;
- the Maven rule: ``mvn``/``mvnw``/``./mvnw`` with the goal ``test``, ``verify``,
  ``integration-test`` or ``test-compile``, or a ``surefire:``/``failsafe:`` goal (exact goals);
- ``MAKE_RUNNERS``: ``make junit``.

A client invocation (``<stack>-crucible.py …``) and a non-runner mention (``[tool.pytest]``,
``pytest.ini``, ``pytest-cov``, ``/tmp/pytest-collect.txt``, ``mvn package``) are never runner
invocations.

**Guarded** (``GUARDED_ROOTS``): ``skills-src/``, ``contracts/``, ``AGENTS.md``, ``generator/templates/``, ``generator/stacks/``,
``generator/agents/``, ``.pi/agents/`` and — CR-MDB-085 §S6.1 — ``generator/skills/``, the stack
skills' sources — the stacks' orchestration notes among them since CR-MDB-060 §S1.1 moved them
there from ``skills-src/memory-templates/``, the one carve-out, which went with the directory
(CR-MDB-060 §S3.1, §S5.1).

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
import shlex
import sys
import time
import unittest
from pathlib import Path

from tests._helpers import ORCHESTRATION_REFERENCES, REPO_ROOT, read_text

#: §S3's guarded set, relative to the repository root: a directory guards every file under it.
GUARDED_ROOTS = (
    "skills-src",
    "contracts",
    "AGENTS.md",
    "generator/templates",
    "generator/stacks",
    "generator/agents",
    ".pi/agents",
    # MIGRATED (CR-MDB-085 §S6.1): the stack skills' sources are guarded too.
    "generator/skills",
)
#: Carve-outs from §S3's guarded set: none. MIGRATED (CR-MDB-060 §S3.1/§S5.1; was
#: ``skills-src/memory-templates``): the directory is gone, its notes guarded in ``generator/skills``.
GUARD_EXCLUDED = ()

#: Where a runner command word ends: whitespace, the fragment's end, or closing punctuation.
_END = r"(?=$|[\s)\"'`,])"
#: A command separator outside quotes; the text after one is a command position. A ``&`` in a
#: redirection (``2>&1``, ``<&0``, ``&>file``) and the ``|`` of ``>|`` separate nothing.
_SEPARATOR = re.compile(r"&&|\|\||\|&|;|(?<![<>])\|(?!\|)|(?<![<>])&(?![&>])|\(")
#: A heredoc operator (``<<WORD``, ``<<'WORD'``, ``<<"WORD"``, ``<<\WORD``, ``<<-WORD``): its
#: body, from the next line to the line ``WORD``, is never a command position.
_HEREDOC = re.compile(r"<<(-?)[ \t]*(?:'([^'\n]*)'|\"([^\"\n]*)\"|\\?([A-Za-z0-9_][\w.-]*))")
#: ``env``'s options: ``-u NAME``/``-C DIR`` and their long forms take an argument; any other
#: option stands alone, a bare ``-`` and ``--`` included. Assignments after ``env`` are matched
#: as ``VAR=value`` wrappers.
_ENV_OPTION = (r"(?:-[uC]\s*\S+|--(?:unset|chdir)(?:=\S+|\s+\S+)"
               r"|-{1,2}[A-Za-z0-9][\w-]*(?:=\S+)?|--?(?=\s|$))")
#: ``timeout``'s options: ``-k``/``-s`` and their long forms take an argument; any other option
#: stands alone.
_TIMEOUT_OPTION = (r"(?:-[ks]\s*\S+|--(?:kill-after|signal)(?:=\S+|\s+\S+)"
                   r"|-{1,2}[A-Za-z][\w-]*(?:=\S+)?)")
#: A wrapper before a command: ``VAR=value``, ``env [options]``, ``timeout [options] <n>``,
#: ``nice [-n N]``, ``time [-p]``, ``command [-p]`` and the reserved words ``!``, ``{``,
#: ``if``, ``then``, ``else``, ``elif``, ``while``, ``until``, ``do`` (CR-MDB-066 §S1).
_WRAPPER = re.compile(
    r"(?:[A-Za-z_][A-Za-z0-9_]*=(?:\"[^\"]*\"|'[^']*'|\S*)|env(?:\s+" + _ENV_OPTION + r")*"
    r"|timeout(?:\s+" + _TIMEOUT_OPTION + r")*\s+\S+"
    r"|nice(?:\s+(?:-n\s*\S+|--adjustment(?:=\S+|\s+\S+)|-\d+))?|time(?:\s+-p)?"
    r"|command(?:\s+-p)?|[!{]|if|then|else|elif|while|until|do)(?:\s+|$)")
#: ``uv run`` with its options, the ones that take a value stepped over with it: a command
#: position before a python runner form (CR-MDB-062 §S1 item 3).
_UV_RUN = re.compile(
    r"uv\s+run(?:\s+(?:-[pw]\s*\S+"
    r"|--(?:with-requirements|with-editable|with|python|project|directory|package|group"
    r"|extra|only-group|env-file|index|default-index|index-url|extra-index-url)"
    r"(?:=\S+|\s+\S+)"
    r"|--?[A-Za-z][\w-]*(?:=\S+)?))*(?:\s+|$)")
#: A python interpreter (bare, versioned or a path) and its options; an option never opens with
#: ``-m``, so an attached ``-m<module>`` is read as the module flag. ``-W``/``-X`` take a value,
#: attached or the next word; the three option forms share no string, so a run of options is
#: read one way only and a non-matching command fails in linear time.
_INTERPRETER = (r"(?:\S*/)?python(?:\d+(?:\.\d+)*)?(?=\s)"
                r"(?:\s+(?:-[WX]\S+|-[WX]\s+\S+|-(?![mWX])\S+))*")
#: The python runner forms (CR-MDB-062 §S1): ``-m`` (separate or attached) with a runner
#: module, ``pytest``/``py.test``, ``coverage run -m``, and a test file run directly.
PYTHON_RUNNERS = (
    re.compile(_INTERPRETER + r"\s+-m\s*(?:unittest|pytest|xmlrunner|coverage\s+run)" + _END),
    re.compile(r"(?:\S*/)?(?:pytest|py\.test)" + _END),
    re.compile(r"coverage\s+run(?:\s+-(?!m(?:\s|$))\S+)*\s+-m\s+\S+"),
    re.compile(_INTERPRETER + r"\s+(?:[^\s'\"`]*/)?(?:test_[^\s/'\"`]*|[^\s/'\"`]*_test)\.py"
               + _END),
)
#: The bun runner forms; a script row is ``test`` alone or ``test:<name>`` (§S1 item 4).
BUN_RUNNERS = (
    re.compile(r"bun\s+test" + _END),
    re.compile(r"(?:bun|npm)\s+run\s+test(?::\S+)?" + _END),
    re.compile(r"npm\s+test" + _END),
    re.compile(r"(?:(?:bunx|bun\s+x|npx)\s+)?playwright\s+test" + _END),
)
#: The cargo runner forms.
CARGO_RUNNERS = (re.compile(r"cargo\s+(?:test|nextest|llvm-cov)" + _END),)
#: The make runner form.
MAKE_RUNNERS = (re.compile(r"make\s+junit" + _END),)
#: Each named group with the stack ``stack_of`` names for it; Maven's rule follows them.
_GROUPS = (("python", PYTHON_RUNNERS), ("bun", BUN_RUNNERS), ("cargo", CARGO_RUNNERS),
           ("make", MAKE_RUNNERS))
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


def _shell_words(segment: str) -> list[str]:
    """``segment``'s words as the shell passes them to the command: quotes removed, a ``#``
    comment dropped, a redirection (``>file``, ``2>&1``, ``>|``, ``&>``) and its target no part
    of them, and a ``)`` closing a subshell ending them. An unclosed quote reads plain words."""
    lex = shlex.shlex(segment, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    words, skip_target = [], False
    try:
        for word in lex:
            if word.startswith(")"):
                break
            if skip_target:
                skip_target = False
                continue
            if word and set(word) <= set("<>&|"):
                skip_target = True
                if words and words[-1].isdigit():
                    words.pop()  # the file descriptor of ``2>`` is the redirection's
                continue
            words.append(word)
    except ValueError:
        return segment.split()
    return words


def _normal(segment: str) -> str:
    """``segment`` as the words the shell passes (``_shell_words``), joined by one space."""
    return " ".join(_shell_words(segment))


def _is_maven_test_run(segment: str) -> bool:
    """True when ``segment`` starts with a Maven launcher and names a test goal (exact goals)."""
    if not _MAVEN.match(segment):
        return False
    goals = segment.split()[1:]
    return any(g in _MAVEN_TEST_GOALS or g.startswith(_MAVEN_TEST_PLUGINS) for g in goals)


def _skip_heredoc_bodies(text: str, index: int, pending: list[tuple[str, bool]]) -> int:
    """The offset just past the heredoc bodies ``pending`` opens, read in order from the line
    at ``index``; each ends at the line holding its word (leading tabs stripped for ``<<-``)."""
    for word, strip_tabs in pending:
        while index < len(text):
            newline = text.find("\n", index)
            end = len(text) if newline < 0 else newline
            line = text[index:end]
            index = end + 1
            if (line.lstrip("\t") if strip_tabs else line) == word:
                break
    return min(index, len(text))


def _segments(text: str) -> list[tuple[int, int]]:
    """Each command segment of ``text`` as ``(start, end)``: a segment starts at a command
    position — the text's start, a line start, or after a separator — and runs to the next one.
    Quotes, a ``#`` comment and a backslash escape hide what they hold; a heredoc body is
    skipped whole, so nothing in it is a position."""
    segments, start, quote, pending = [], 0, None, []
    index = 0
    while index < len(text):
        char = text[index]
        if quote:
            if char == "\\" and quote == '"':
                index += 2
                continue
            quote = None if char == quote else quote
            index += 1
            continue
        if char == "\\":
            index += 2
            continue
        if char in "'\"":
            quote = char
            index += 1
            continue
        if char == "`":
            close = index + 1
            while close < len(text) and text[close] != "`":
                close += 2 if text[close] == "\\" else 1
            if close >= len(text):
                quote = char  # an unclosed backquote reads as an unclosed quote
                break
            inner = _segments(text[index + 1:close])
            segments.extend((index + 1 + begin, index + 1 + end) for begin, end in inner)
            index = close + 1
            continue
        if char == "#" and (index == 0 or text[index - 1] in " \t\n;&|("):
            newline = text.find("\n", index)
            index = len(text) if newline < 0 else newline
            continue
        if char == "\n":
            segments.append((start, index))
            index = _skip_heredoc_bodies(text, index + 1, pending)
            start, pending = index, []
            continue
        if text.startswith("$((", index) or text.startswith("((", index):
            index, depth = text.index("((", index) + 2, 2
            while index < len(text) and depth:
                depth += {"(": 1, ")": -1}.get(text[index], 0)
                index += 1
            continue
        if text.startswith("<<<", index):
            index += 3  # a here-string, not a heredoc: it opens no body
            continue
        heredoc = _HEREDOC.match(text, index)
        if heredoc:
            word = next(g for g in heredoc.groups()[1:] if g is not None)
            pending.append((word, bool(heredoc.group(1))))
            index = heredoc.end()
            continue
        separator = _SEPARATOR.match(text, index)
        if separator:
            segments.append((start, index))
            index = start = separator.end()
            continue
        index += 1
    segments.append((start, len(text)))
    return sorted(segments)


def _runner(fragment: str):
    """``(offset, stack)`` of the first runner at a command position in ``fragment``, or
    ``None``. Wrappers before a command are stepped over; ``uv run`` and its options are a
    position before a python runner form only. A runner is read in the words the shell passes
    (``_normal``): quotes removed, a redirection no part of them."""
    for begin, end in _segments(fragment):
        piece = fragment[begin:end]
        start = begin + len(piece) - len(piece.lstrip())
        segment = piece.lstrip()
        while True:
            wrapper = _WRAPPER.match(segment)
            if not wrapper or not wrapper.group(0):
                break
            start += wrapper.end()
            segment = segment[wrapper.end():]
        uv_run = _UV_RUN.match(segment)
        if uv_run:
            after = _normal(segment[uv_run.end():])
            if any(r.match(after) for r in PYTHON_RUNNERS):
                return start + uv_run.end(), "python"
            continue
        normal = _normal(segment)
        for stack, group in _GROUPS:
            if any(r.match(normal) for r in group):
                return start, stack
        if _is_maven_test_run(normal):
            return start, "mvn"
    return None


def runner_at(fragment: str):
    """The offset in ``fragment`` where a runner command starts at a command position, or
    ``None``. ``fragment`` is a code span's content, one fenced line, or a hook's command."""
    found = _runner(fragment)
    return None if found is None else found[0]


def stack_of(command: str):
    """The stack of the runner at a command position in ``command`` — ``"python"``,
    ``"bun"``, ``"cargo"``, ``"mvn"`` or ``"make"`` (``STACKS``) — or ``None``."""
    found = _runner(command)
    return None if found is None else found[1]


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

#: The stack labels ``stack_of`` names (CR-MDB-062 §S1 item 1): the runner tool word, which is
#: also the ``<x>`` of the runner hook ``block-direct-<x>-test`` (``make`` has no hook).
STACKS = ("python", "bun", "cargo", "mvn", "make")

#: Each runner form §S3 lists, as it would be shown to be typed, with its stack.
RUNNER_FORMS = (
    ("python -m unittest", "python"),
    ("python3 -m unittest discover -s tests -t .", "python"),
    ("python3.14 -m unittest tests.test_hooks", "python"),
    (".venv/bin/python -m pytest -q", "python"),
    ("/usr/bin/python3 -W error -m xmlrunner discover", "python"),
    ("python3 -B -m coverage run -m unittest", "python"),
    ("pytest", "python"),
    ("pytest -x tests/", "python"),
    (".venv/bin/pytest tests/ --junitxml=test-reports/junit.xml", "python"),
    ("py.test", "python"),
    ("uv run pytest", "python"),
    ("coverage run -m unittest", "python"),
    ("coverage run --branch -m pytest", "python"),
    ("bun test", "bun"),
    ("bun test --reporter=junit", "bun"),
    ("bun run test", "bun"),
    ("bun run test:unit", "bun"),
    ("npm test", "bun"),
    ("npm run test:e2e", "bun"),
    ("bunx playwright test", "bun"),
    ("bun x playwright test --grep login", "bun"),
    ("npx playwright test", "bun"),
    ("playwright test", "bun"),
    ("cargo test", "cargo"),
    ("cargo test --workspace", "cargo"),
    ("cargo nextest run", "cargo"),
    ("cargo llvm-cov --lcov --output-path lcov.info", "cargo"),
    ("mvn test", "mvn"),
    ("mvn -q clean test-compile", "mvn"),
    ("mvnw verify", "mvn"),
    ("./mvnw integration-test", "mvn"),
    ("mvn surefire:test", "mvn"),
    ("mvn -Dit.test=FooIT failsafe:integration-test", "mvn"),
    ("make junit", "make"),
)

#: Each command position §S3 lists that is not the start: a wrapper or a separator, with its
#: stack.
WRAPPED_FORMS = (
    ("env HOME=/tmp/h pytest", "python"),
    ("env python3 -m unittest", "python"),
    ("HOME=/tmp/h python3 -m unittest", "python"),
    ("ALLOW_RAW_PYTEST=1 pytest", "python"),
    ("timeout 600 cargo test", "cargo"),
    ("nice bun test", "bun"),
    ("time mvn verify", "mvn"),
    ("cd tests/native && make junit", "make"),
    ("false || npm test", "bun"),
    ("cd crates/core; cargo nextest run", "cargo"),
    ("echo tests | pytest", "python"),
    ("env FOO=1 timeout 60 nice time pytest", "python"),
    ("env -i HOME=/tmp/h pytest", "python"),
    ("env -u PYTHONPATH python3 -m unittest", "python"),
    ("env --unset=FOO -i cargo test", "cargo"),
    ("env -C tests/native HOME=/tmp/h make junit", "make"),
)

#: CR-MDB-062 §S1 item 2 — the hooks' command positions the guard newly takes, with the stack
#: of the runner at the position: a later line (also after a heredoc body or a line in quotes
#: ends), ``&``, ``(``, ``env`` with any options, ``timeout`` with options, ``nice -n N``.
POSITION_FORMS = (
    ("echo hi\npytest", "python"),
    ("cd crates/core\ncargo test --workspace", "cargo"),
    ("sleep 1 & pytest", "python"),
    ("bun run dev & npx playwright test", "bun"),
    ("(pytest -x)", "python"),
    ("(cargo test) || true", "cargo"),
    ("env - HOME=/tmp/h pytest", "python"),
    ("env -- python3 -m unittest", "python"),
    ("env --ignore-environment --unset=FOO cargo test", "cargo"),
    ("timeout -k 5 60 pytest", "python"),
    ("timeout --signal=KILL 60 cargo test", "cargo"),
    ("timeout -s KILL 60 bun test", "bun"),
    ("timeout --kill-after=5s --preserve-status 10m mvn verify", "mvn"),
    ("nice -n 10 pytest", "python"),
    ("nice -n 19 cargo nextest run", "cargo"),
    ("timeout -k 5 60 nice -n 10 env -i HOME=/tmp/h python3 -m unittest", "python"),
    ("cat > f.md <<EOF\nbun test\nEOF\npytest", "python"),
    ("git commit -F - <<'EOF'\npytest -x\nEOF\ncargo test", "cargo"),
    ("cat <<-EOF\n\tpytest\nEOF\nbun test", "bun"),
    ("cat <<EOF > notes.md && pytest\nbun test\nEOF", "python"),
    ("echo 'one\nbun test'\npytest", "python"),
    ('git commit -m "fix\ncargo test"\nmvn test', "mvn"),
)

#: CR-MDB-062 §S1 item 3 — an attached ``-m`` (each of the four).
ATTACHED_M_FORMS = (
    ("python3 -munittest", "python"),
    ("python -mpytest -x", "python"),
    ("python3.14 -mxmlrunner discover -s tests", "python"),
    (".venv/bin/python -B -mcoverage run -m unittest", "python"),
)

#: CR-MDB-062 §S1 item 3 — ``uv run`` with its options (and their values) stepped over, before
#: a python runner form.
UV_RUN_FORMS = (
    ("uv run python -m pytest", "python"),
    ("uv run python3 tests/test_x.py", "python"),
    ("uv run --with pytest pytest", "python"),
    ("uv run --with=pytest-xdist pytest -n 4", "python"),
    ("uv run --with-requirements requirements-dev.txt python -m unittest", "python"),
    ("uv run --python 3.14 python3 -munittest", "python"),
    ("uv run -p 3.12 py.test", "python"),
    ("uv run --project ../core python3 -m xmlrunner discover", "python"),
    ("uv run --directory sub pytest", "python"),
    ("uv run --package core python -m coverage run -m pytest", "python"),
    ("uv run --group test pytest", "python"),
    ("uv run --extra dev coverage run -m unittest", "python"),
    ("uv run --frozen --with pytest --python=3.14 pytest", "python"),
)

#: CR-MDB-062 §S1 item 3 — a test file run directly: an interpreter, its options, then a
#: script whose basename matches ``test_*.py`` or ``*_test.py``.
TEST_FILE_FORMS = (
    ("python3 tests/test_x.py", "python"),
    ("python tests/test_hooks.py -v", "python"),
    ("python3.14 -B tests/test_raw_runner_guard.py", "python"),
    (".venv/bin/python pkg/parser_test.py", "python"),
    ("/usr/bin/python3 -W error -X dev test_cli.py", "python"),
)

#: CR-MDB-062 §S1 item 4 — the bun script rows: ``test`` alone or as ``test:<name>``.
BUN_SCRIPT_FORMS = (
    ("npm run test", "bun"),
    ("bun run test --coverage", "bun"),
    ("npm run test -- --watch", "bun"),
    ("npm run test:integration", "bun"),
)

#: CR-MDB-062 §S1 item 4 — scripts the narrowed bun rows pass.
NARROWED_BUN_SCRIPTS = (
    "bun run tests/x.ts",
    "bun run test.ts",
    "npm run testdata",
    "npm run test-utils",
    "npm run build",
    "npx playwright install",
)

#: CR-MDB-062 §S1 item 2 — a heredoc body is never a command position (``<<WORD``,
#: ``<<'WORD'``, ``<<-WORD``), separators inside it included.
HEREDOC_BODIES = (
    "git commit -F - <<'EOF'\nfix: make cargo test && pytest pass\npytest -x\nEOF",
    "cat > f.md <<EOF\nbun test\nEOF",
    "cat <<-EOF\n\tpytest\n\tcargo test\nEOF",
    "cat > notes.md <<'EOF'\nstep one; pytest -x\nEOF",
    "python3 - <<EOF\npytest = 1\nprint(pytest)\nEOF",
)

#: CR-MDB-062 §S1 item 2 — a line inside quotes spanning lines is not a command position.
QUOTED_LINES = (
    "git commit -m 'first line\npytest -x\n'",
    'echo "a\nbun test"',
    "printf 'echo hi\ncargo test\n'",
)

#: CR-MDB-062 §S1 item 3 — non-test scripts and non-runner ``python``/``uv`` commands: never
#: runners, so a value of a ``uv run`` option is never read as the runner.
NON_TEST_SCRIPTS = (
    "python3 generator/build.py --check",
    'python3 -c "import unittest"',
    "python3 -mjson.tool data.json",
    "python3 tests/testdata.py",
    "python3 scripts/latest.py",
    "python3 tests/_helpers.py",
    "cat tests/test_x.py",
    "uv run --with x python script.py",
    "uv run --with pytest python script.py",
    "uv run python generator/build.py --check",
    "uv tool install .",
    "uv tool install --reinstall --python 3.14 .",
)

#: CR-MDB-062 §S2 — a runner word inside an argument is never a runner.
ARGUMENT_MENTIONS = (
    "echo pytest",
    'git commit -m "… pytest …"',
    "git commit -m 'cargo test passes'",
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
    "uv run python3 ~/.crucible/clients/python-crucible.py check --agent A",
)

#: The non-runner mentions §S3 lists: never runners.
NON_RUNNER_MENTIONS = (
    "[tool.pytest]",
    "pytest.ini",
    "pytest-cov",
    "/tmp/pytest-collect.txt",  # noqa: S108 — §S3's sample mention, never opened
    "mvn package",
)

#: CR-MDB-066 §S1 — the command positions the shell grammar adds, with the stack of the runner
#: at the position (labelled). At least one entry per §S1 item for each of python, bun, cargo
#: and mvn, and ``{ make junit; }`` for make: (1) the reserved words ``!``, ``{``, ``if``,
#: ``then``, ``else``, ``elif``, ``while``, ``until`` and ``do``, stepped over in any order with
#: the other wrappers; (2) ``command`` with an optional ``-p``; (3) ``time -p``; (4) an unquoted
#: backquote, whose text up to the closing backquote is a position; (5) an arithmetic ``$((…))``
#: or ``((…))``, skipped whole, so no ``<<`` inside it opens a heredoc that swallows a later
#: line.
GRAMMAR_FORMS = (
    # python
    ("{ pytest; }", "python"),
    ("if pytest; then echo ok; fi", "python"),
    ("! pytest -x", "python"),
    ("for f in a; do python3 -m unittest; done", "python"),
    ("! time -p pytest", "python"),
    ("if ! command pytest; then :; fi", "python"),
    ("command pytest", "python"),
    ("command -p python3 -m unittest", "python"),
    ("time -p pytest", "python"),
    ("echo `pytest -q`", "python"),
    ("out=`python3 -m unittest`", "python"),
    ("echo $((1<<2))\npytest", "python"),
    # bun
    ("{ bun test; }", "bun"),
    ("if true; then bun test; fi", "bun"),
    ("until bun test; do :; done", "bun"),
    ("command bun test", "bun"),
    ("time -p bun test", "bun"),
    ("echo `bun test`", "bun"),
    ("((n<<2))\nbun test", "bun"),
    # cargo
    ("! cargo test", "cargo"),
    ("if false; then :; else cargo test; fi", "cargo"),
    ("while cargo test; do :; done", "cargo"),
    ("command -p cargo test", "cargo"),
    ("time -p cargo nextest run", "cargo"),
    ("time -p nice -n 5 cargo test", "cargo"),
    ("v=`cargo test --workspace`", "cargo"),
    ("while ((n<<1)); do cargo llvm-cov; done", "cargo"),
    ("while ((n<<1)); do\ncargo test\ndone", "cargo"),
    # mvn
    ("{ mvn verify; }", "mvn"),
    ("if false; then :; elif mvn test; then :; fi", "mvn"),
    ("command mvn test", "mvn"),
    ("time -p mvn verify", "mvn"),
    ("echo `mvn verify`", "mvn"),
    ("echo $((1<<2))\nmvn verify", "mvn"),
    # make
    ("{ make junit; }", "make"),
)

#: CR-MDB-066 §S1 (AC1) — what §S1's grammar never makes a runner: ``command -v``/``-V`` look a
#: command up and run nothing; the text after a closing backquote and after an arithmetic
#: expansion continues the enclosing command; ``if`` and ``ifconfig`` are whole words only when
#: they are; a backquote inside double quotes opens nothing.
GRAMMAR_NON_RUNNERS = (
    "command -v pytest",
    "command -V cargo",
    "echo `date` pytest",
    "echo $((1<<2)) pytest",
    "if [ -f pytest.ini ]; then echo y; fi",
    "ifconfig",
    'git commit -m "fix `pytest`"',
)

#: Long runs of interpreter options (CR-MDB-062 C5 F1): ``-W``/``-X`` take a value, attached or
#: the next word, and the option forms share no string, so each run is read one way only and is
#: judged well inside a hook's timeout — a run that names no runner as fast as one that does.
OPTION_RUN_LENGTH = 60
OPTION_RUNS = (
    ("python3 " + "-W " * OPTION_RUN_LENGTH + "x", None),
    ("python3 " + "-X " * OPTION_RUN_LENGTH + "x", None),
    ("python3 " + "-Wa " * OPTION_RUN_LENGTH + "x", None),
    ("uv run python3 " + "-W -Xa " * (OPTION_RUN_LENGTH // 2) + "tests/x.py", None),
    ("env timeout 5 python3 " + "-Xa -W " * (OPTION_RUN_LENGTH // 2) + "-m pytes", None),
    ("python3 " + "-Wa " * OPTION_RUN_LENGTH + "-m pytest", "python"),
    ("python3 " + "-W error " * OPTION_RUN_LENGTH + "tests/test_x.py", "python"),
)
#: How long one judgement of an ``OPTION_RUNS`` command may take, in seconds; Pi kills a hook
#: after 10, and a timed-out ``closed`` hook blocks.
OPTION_RUN_BUDGET = 1.0


class RawRunnerDetectorOnSampleTextTest(unittest.TestCase):
    """§S3 — the detector, proved on sample text both ways before it is applied to the tree."""

    def assertCaught(self, text: str, expected: list[tuple[int, str]]):
        self.assertEqual(runner_findings(text), expected, f"for sample text:\n{text}")

    def test_each_runner_form_in_a_code_span_is_caught_as_an_instruction(self):
        for form, _stack in RUNNER_FORMS:
            with self.subTest(form=form):
                self.assertCaught(f"Run `{form}` from the project root.", [(1, form)])

    def test_each_runner_form_on_a_fenced_line_is_caught(self):
        for form, _stack in RUNNER_FORMS:
            with self.subTest(form=form):
                self.assertCaught(f"Iterate:\n\n```bash\n{form}\n```\n", [(4, form)])

    def test_each_wrapper_and_separator_is_a_command_position(self):
        for form, _stack in WRAPPED_FORMS:
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


def _detector(name: str):
    """A detector-section name CR-MDB-062 §S1 adds, looked up when a test runs — so a name not
    there yet fails only the tests that need it, with an ``AttributeError``, and the module still
    imports."""
    return getattr(sys.modules[__name__], name)


def _single_line(corpus):
    """The commands of ``corpus`` (bare or ``(command, stack)``) that fit on one line — the ones
    a code span or a fenced line can show."""
    commands = [entry[0] if isinstance(entry, tuple) else entry for entry in corpus]
    return [c for c in commands if "\n" not in c]


class RunnerStackOnSampleTextTest(unittest.TestCase):
    """CR-MDB-062 §S1 — the per-stack groups, ``stack_of``, the hooks' command positions, the
    three python forms and the narrowed bun rows, each proved on sample text both ways."""

    def assertRunner(self, command: str, stack: str):
        """``command`` holds a runner at a command position, and ``stack_of`` names ``stack``."""
        self.assertIsNotNone(runner_at(command), f"no runner found at a command position in "
                             f"{command!r}")
        self.assertEqual(_detector("stack_of")(command), stack, f"for {command!r}")

    def assertNoRunner(self, command: str):
        """``command`` holds no runner at a command position, and ``stack_of`` gives ``None``."""
        self.assertIsNone(runner_at(command), f"a runner was found in {command!r}")
        self.assertIsNone(_detector("stack_of")(command), f"for {command!r}")

    # -- item 1: the per-stack groups and ``stack_of`` ------------------------------------

    def test_the_runner_forms_are_split_into_the_named_per_stack_groups(self):
        groups = {stack: _detector(name) for stack, name in (
            ("python", "PYTHON_RUNNERS"), ("bun", "BUN_RUNNERS"), ("cargo", "CARGO_RUNNERS"),
            ("make", "MAKE_RUNNERS"))}
        for stack, group in groups.items():
            with self.subTest(group=stack):
                self.assertGreater(len(group), 0)
                self.assertTrue(all(isinstance(p, re.Pattern) for p in group), group)
        for form, stack in RUNNER_FORMS:
            if form.startswith("uv run"):
                continue  # §S1 item 3: ``uv run`` is a position, not a group's own form
            matched = sorted(s for s, group in groups.items() if any(p.match(form) for p in group))
            with self.subTest(form=form):
                # Maven's forms belong to the Maven rule, so no group holds them.
                self.assertEqual(matched, [] if stack == "mvn" else [stack])

    def test_stack_of_names_the_stack_of_each_existing_runner_and_wrapped_form(self):
        for form, stack in RUNNER_FORMS + WRAPPED_FORMS:
            with self.subTest(form=form):
                self.assertRunner(form, stack)

    def test_stack_of_gives_none_for_each_client_invocation_and_non_runner_mention(self):
        for form in CLIENT_FORMS + NON_RUNNER_MENTIONS + ARGUMENT_MENTIONS:
            with self.subTest(form=form):
                self.assertNoRunner(form)

    def test_every_corpus_entry_is_labelled_with_one_of_the_stacks_and_appears_once(self):
        # MIGRATED at CR-MDB-066 (§S8.1): GRAMMAR_FORMS joins the labelled corpora and
        # GRAMMAR_NON_RUNNERS the plain ones.
        labelled = (RUNNER_FORMS + WRAPPED_FORMS + POSITION_FORMS + ATTACHED_M_FORMS
                    + UV_RUN_FORMS + TEST_FILE_FORMS + BUN_SCRIPT_FORMS + GRAMMAR_FORMS)
        self.assertEqual(sorted({stack for _form, stack in labelled}), sorted(STACKS))
        commands = ([form for form, _stack in labelled] + list(CLIENT_FORMS)
                    + list(NON_RUNNER_MENTIONS) + list(NARROWED_BUN_SCRIPTS)
                    + list(HEREDOC_BODIES) + list(QUOTED_LINES) + list(NON_TEST_SCRIPTS)
                    + list(ARGUMENT_MENTIONS) + list(GRAMMAR_NON_RUNNERS))
        self.assertEqual(sorted(c for c in set(commands) if commands.count(c) > 1), [],
                         "a corpus entry appears more than once (the corpora are §S6's parity "
                         "source)")

    # -- item 2: command positions ---------------------------------------------------------

    def test_each_command_position_of_the_hooks_is_a_position(self):
        for form, stack in POSITION_FORMS:
            with self.subTest(form=form):
                self.assertRunner(form, stack)

    def test_runner_at_gives_the_offset_of_the_runner_at_each_new_position(self):
        cases = (
            ("echo hi\npytest", 8),
            ("sleep 1 & pytest", 10),
            ("(cargo test) || true", 1),
            ("env - HOME=/tmp/h pytest", 18),
            ("timeout -k 5 60 pytest", 16),
            ("nice -n 10 bun test", 11),
            ("cat > f.md <<EOF\nbun test\nEOF\npytest", 30),
        )
        for command, offset in cases:
            with self.subTest(command=command):
                self.assertEqual(runner_at(command), offset)

    def test_a_heredoc_body_is_never_a_command_position(self):
        for body in HEREDOC_BODIES:
            with self.subTest(command=body):
                self.assertNoRunner(body)
        # The line after the closing word is a position again; the body's runner is not the one.
        for form, stack in POSITION_FORMS:
            if "<<" in form:
                with self.subTest(command=form):
                    self.assertRunner(form, stack)

    def test_a_line_inside_quotes_spanning_lines_is_not_a_command_position(self):
        for quoted in QUOTED_LINES:
            with self.subTest(command=quoted):
                self.assertNoRunner(quoted)
        # The line after the closing quote is a position again.
        for form, stack in (("echo 'one\nbun test'\npytest", "python"),
                            ('git commit -m "fix\ncargo test"\nmvn test', "mvn")):
            with self.subTest(command=form):
                self.assertRunner(form, stack)

    # -- item 3: the three python forms ----------------------------------------------------

    def test_an_attached_m_runs_each_of_the_four_python_runners(self):
        for form, stack in ATTACHED_M_FORMS:
            with self.subTest(form=form):
                self.assertRunner(form, stack)

    def test_uv_run_with_its_options_and_values_before_a_python_runner_form_is_caught(self):
        for form, stack in UV_RUN_FORMS:
            with self.subTest(form=form):
                self.assertRunner(form, stack)

    def test_a_test_file_run_directly_by_an_interpreter_is_caught(self):
        for form, stack in TEST_FILE_FORMS:
            with self.subTest(form=form):
                self.assertRunner(form, stack)

    def test_non_test_scripts_and_client_invocations_pass(self):
        for command in NON_TEST_SCRIPTS + CLIENT_FORMS + (HEREDOC_BODIES[-1],):
            with self.subTest(command=command):
                self.assertNoRunner(command)

    def test_a_long_run_of_interpreter_options_is_judged_within_the_budget(self):
        for command, stack in OPTION_RUNS:
            with self.subTest(command=command[:40]):
                start = time.perf_counter()
                got = _detector("stack_of")(command)
                elapsed = time.perf_counter() - start
                self.assertEqual(got, stack, f"for {command!r}")
                self.assertLess(elapsed, OPTION_RUN_BUDGET,
                                f"stack_of took {elapsed:.2f}s on {command!r}")

    # -- item 4: the bun script rows narrow -------------------------------------------------

    def test_the_bun_script_rows_catch_test_alone_or_as_test_name(self):
        rows = BUN_SCRIPT_FORMS + tuple(
            (f, s) for f, s in RUNNER_FORMS if f.startswith(("bun run ", "npm run ")))
        self.assertEqual(len(rows), 7)
        for form, stack in rows:
            with self.subTest(form=form):
                self.assertRunner(form, stack)

    def test_the_bun_script_rows_pass_every_other_script(self):
        for command in NARROWED_BUN_SCRIPTS:
            with self.subTest(command=command):
                self.assertNoRunner(command)

    # -- the new forms as a guarded file shows them -----------------------------------------

    def test_each_new_single_line_runner_form_is_caught_in_a_code_span_and_on_a_fenced_line(self):
        for form in _single_line(POSITION_FORMS + ATTACHED_M_FORMS + UV_RUN_FORMS
                                 + TEST_FILE_FORMS + BUN_SCRIPT_FORMS):
            with self.subTest(form=form):
                self.assertEqual(runner_findings(f"Run `{form}` from the project root."),
                                 [(1, form)])
                self.assertEqual(runner_findings(f"Iterate:\n\n```bash\n{form}\n```\n"),
                                 [(4, form)])

    def test_each_new_single_line_non_runner_is_not_caught_in_a_code_span_or_a_fenced_line(self):
        for command in _single_line(NARROWED_BUN_SCRIPTS + NON_TEST_SCRIPTS + ARGUMENT_MENTIONS):
            with self.subTest(command=command):
                self.assertEqual(runner_findings(f"Run `{command}` now."), [])
                self.assertEqual(runner_findings(f"```bash\n{command}\n```"), [])


def _in_code_span(entry: str) -> str:
    """``entry`` as a guarded file shows it in a code span (CR-MDB-066 §S8.1, AC1): delimited
    by a backtick run one longer than the longest run ``entry`` holds, padded with a space on
    each side, so a backquote inside the entry neither closes the span nor joins its
    delimiter."""
    longest = max((len(run) for run in re.findall(r"`+", entry)), default=0)
    delimiter = "`" * (longest + 1)
    return f"{delimiter} {entry} {delimiter}"


#: CR-MDB-066 §S1 — which item each ``GRAMMAR_FORMS`` entry exercises, read off its text: a
#: reserved word, ``command``, ``time -p``, a backquote, an arithmetic ``((``.
_GRAMMAR_ITEMS = {
    "reserved word": re.compile(r"(?:^|[\s;(])(?:!|\{|if|then|else|elif|while|until|do)\s"),
    "command": re.compile(r"(?:^|[\s;(])command\s"),
    "time -p": re.compile(r"(?:^|[\s;(])time\s+-p\s"),
    "backquote": re.compile(r"`"),
    "arithmetic": re.compile(r"\(\("),
}


class CommandGrammarOnSampleTextTest(unittest.TestCase):
    """CR-MDB-066 §S1 (AC1) — the shell grammar's command positions in the guard: reserved
    words, ``command [-p]``, ``time -p``, an unquoted backquote and an arithmetic expansion,
    proved on sample text both ways."""

    def test_grammar_forms_hold_an_entry_per_section_s1_item_for_each_hooked_stack(self):
        # AC1's corpus shape; a precondition of the checks below, so a corpus that lost an
        # item's entry for a stack would make them prove less than AC1 asks.
        missing = [f"{stack}: {item}" for stack in ("python", "bun", "cargo", "mvn")
                   for item, pattern in _GRAMMAR_ITEMS.items()
                   if not any(pattern.search(c) for c, s in GRAMMAR_FORMS if s == stack)]
        self.assertEqual(missing, [], "AC1: GRAMMAR_FORMS lacks an entry for")
        self.assertIn(("{ make junit; }", "make"), GRAMMAR_FORMS)
        # The fails-today detector: the stack of each form comes from ``stack_of``.
        wrong = [f"{command!r}: stack_of gives {stack_of(command)!r}, want {stack!r}"
                 for command, stack in GRAMMAR_FORMS if stack_of(command) != stack]
        self.assertEqual(wrong, [], "CR-MDB-066 §S1: the guard misses a command position:\n  "
                         + "\n  ".join(wrong))

    def test_runner_at_finds_a_runner_in_each_grammar_form(self):
        missed = [command for command, _stack in GRAMMAR_FORMS if runner_at(command) is None]
        self.assertEqual(missed, [], "CR-MDB-066 §S1: runner_at finds no runner in")

    def test_the_code_span_placement_shows_each_entry_whole(self):
        # The placement AC1 prescribes, proved before it is used: the span's content is the
        # entry itself, backquotes and all; a single-backtick span would cut it.
        for entry in _single_line(GRAMMAR_FORMS) + _single_line(GRAMMAR_NON_RUNNERS):
            with self.subTest(entry=entry):
                placed = f"Run {_in_code_span(entry)} from the project root."
                self.assertEqual([content for _s, _e, content in _code_spans(placed)], [entry])
        self.assertEqual(_in_code_span("echo `pytest`"), "`` echo `pytest` ``")
        self.assertEqual(_in_code_span("pytest"), "` pytest `")
        cut = [content for _s, _e, content in _code_spans("Run `echo `pytest`` now.")]
        self.assertNotEqual(cut, ["echo `pytest`"])

    def test_each_single_line_grammar_form_is_caught_in_a_code_span_and_on_a_fenced_line(self):
        forms = _single_line(GRAMMAR_FORMS)
        self.assertGreaterEqual(len(forms), 25, "precondition: the single-line forms")
        for form in forms:
            with self.subTest(form=form):
                self.assertEqual(
                    runner_findings(f"Run {_in_code_span(form)} from the project root."),
                    [(1, form)])
                self.assertEqual(runner_findings(f"Iterate:\n\n```bash\n{form}\n```\n"),
                                 [(4, form)])

    def test_each_grammar_non_runner_gives_no_stack_and_no_finding_in_either_placement(self):
        # A regression pin, passing today: it fails against a §S1 that over-reaches — one
        # stepping over ``command -v``/``-V``, reading the text after a closing backquote or
        # after ``$((…))`` as a position, matching ``if`` inside ``ifconfig``, or opening a
        # substitution inside double quotes.
        self.assertEqual(len(GRAMMAR_NON_RUNNERS), 7)
        for command in GRAMMAR_NON_RUNNERS:
            with self.subTest(command=command):
                self.assertIsNone(stack_of(command), f"for {command!r}")
                self.assertIsNone(runner_at(command), f"for {command!r}")
                self.assertEqual(runner_findings(f"Run {_in_code_span(command)} now."), [])
                self.assertEqual(runner_findings(f"```bash\n{command}\n```"), [])


class GuardedSetTest(unittest.TestCase):
    """§S3 — the guard covers exactly the guarded set: every file under each guarded root, and
    nothing outside it. MIGRATED (CR-MDB-060 §S3.1): no memory-templates carve-out."""

    def setUp(self):
        self.files = guarded_files()
        self.relative = [f.relative_to(REPO_ROOT).as_posix() for f in self.files]

    def test_every_file_under_each_guarded_root_is_guarded(self):
        for entry in GUARDED_ROOTS:
            path = REPO_ROOT / entry
            expected = ([path] if path.is_file() else
                        [Path(d) / n for d, _s, names in os.walk(path) for n in names])
            with self.subTest(root=entry):
                self.assertTrue(expected, f"§S3's guarded {entry} is missing from the tree")
                self.assertEqual(sorted(set(expected) - set(self.files)), [])

    def test_the_guarded_set_names_each_root_of_section_s3(self):
        self.assertIn("AGENTS.md", self.relative)
        for prefix in ("skills-src/", "contracts/", "generator/templates/", "generator/stacks/",
                       "generator/agents/", ".pi/agents/", "generator/skills/"):
            with self.subTest(root=prefix):
                self.assertTrue(any(r.startswith(prefix) for r in self.relative))

    def test_the_orchestration_references_are_inside_the_guard(self):
        # MIGRATED (CR-MDB-060 §S1.1/§S3.1; was test_the_memory_templates_are_outside_the_guard):
        # the notes the carve-out spared are stack-skill references now, and guarded.
        self.assertEqual(GUARD_EXCLUDED, ())
        self.assertEqual(
            [rel for rel in ORCHESTRATION_REFERENCES.values() if rel not in self.relative], [],
            "CR-MDB-060 §S1.1: each stack's orchestration reference is guarded",
        )

    def test_nothing_outside_the_guarded_set_is_guarded(self):
        roots = ("skills-src/", "contracts/", "generator/templates/", "generator/stacks/",
                 "generator/agents/", ".pi/agents/", "generator/skills/")
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
