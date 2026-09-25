"""Sandesh CLI forms in the shipped skills carry their identity flags (CR-MDB-031 C5 VERIFY F1).

Contract: ``docs/changes/CR-MDB-031-claude-era-substrate-retirement.md`` §S2 (the MCP verbs become
the ``sandesh`` CLI) and ``contracts/sandesh-cli.md``. A CLI form copied from a skill must work as
written: the CLI does not know who is speaking or which project it is in unless told.

- ``sandesh send`` / ``sandesh reply`` carry ``--from`` (the sender) and ``--project``.
- ``sandesh unregister`` carries ``--as`` (the caller's own address) and ``--project``.
- Every flag a form uses is one ``sandesh <verb> --help`` lists (when ``sandesh`` is on ``PATH``;
  the check skips, naming the missing binary, otherwise).

A FORM is a ``sandesh <verb>`` occurrence in ``skills-src/`` that carries at least one ``--flag``:
inside an inline code span it runs to the closing backtick (a span may wrap lines); on a fenced
line it runs to the end of that line; elsewhere to the next backtick or blank line. A bare verb
name with no flag (``(`sandesh send`)``) names the verb, it is not a form. Every scan has a
detector fixture. Stdlib only.
"""

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests._helpers import REPO_ROOT

SKILLS_SRC = REPO_ROOT / "skills-src"

#: The verbs gated here, and the flags each form must carry.
REQUIRED_FLAGS = {
    "send": ("--from", "--project"),
    "reply": ("--from", "--project"),
    "unregister": ("--as", "--project"),
}
FORM_START_RE = re.compile(r"(?<![\w-])sandesh (send|reply|unregister)(?![\w-])")
FLAG_RE = re.compile(r"(?<![\w-])--[a-z][a-z-]*")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


def _fenced_line_numbers(lines: list) -> set:
    """1-based numbers of the lines strictly inside a fenced block."""
    inside, numbers = False, set()
    for number, line in enumerate(lines, 1):
        if FENCE_RE.match(line):
            inside = not inside
        elif inside:
            numbers.add(number)
    return numbers


def sandesh_forms(root: Path) -> list:
    """``[(rel, lineno, verb, form_text)]`` for every ``sandesh send|reply|unregister`` FORM (see
    the module docstring) under ``root/skills-src``; whitespace inside a form is collapsed."""
    forms = []
    for path in sorted((root / "skills-src").rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        fenced = _fenced_line_numbers(text.splitlines())
        rel = path.relative_to(root).as_posix()
        for match in FORM_START_RE.finditer(text):
            lineno = text.count("\n", 0, match.start()) + 1
            rest = text[match.start():]
            if lineno in fenced:
                end = rest.find("\n")
            else:
                ends = [i for i in (rest.find("`"), rest.find("\n\n")) if i != -1]
                end = min(ends) if ends else -1
            form = " ".join((rest if end == -1 else rest[:end]).split())
            if FLAG_RE.search(form):
                forms.append((rel, lineno, match.group(1), form))
    return forms


def missing_required_flags(forms: list) -> list:
    """``"<rel>:<lineno>: <verb> lacks <flag>: <form>"`` for every form missing a required flag."""
    problems = []
    for rel, lineno, verb, form in forms:
        flags = set(FLAG_RE.findall(form))
        for flag in REQUIRED_FLAGS[verb]:
            if flag not in flags:
                problems.append(f"{rel}:{lineno}: sandesh {verb} lacks {flag}: {form[:160]}")
    return problems


def unknown_flags(forms: list, help_flags: dict) -> list:
    """``"<rel>:<lineno>: sandesh <verb> --x not in --help"`` for every flag the CLI's help for
    that verb does not list (``help_flags``: ``{verb: set of flags}``)."""
    problems = []
    for rel, lineno, verb, form in forms:
        for flag in sorted(set(FLAG_RE.findall(form)) - help_flags[verb]):
            problems.append(f"{rel}:{lineno}: sandesh {verb} {flag} not in `sandesh {verb} --help`")
    return problems


def _write_tree(root: Path, files: dict) -> None:
    for rel, body in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")


class SandeshFormFlagsTest(unittest.TestCase):
    """Every ``sandesh send|reply`` form names ``--from`` and ``--project``; every ``sandesh
    unregister`` names ``--as`` and ``--project``."""

    def test_forms_of_every_gated_verb_exist(self):
        verbs = {verb for _rel, _n, verb, _form in sandesh_forms(REPO_ROOT)}
        self.assertEqual(sorted(set(REQUIRED_FLAGS) - verbs), [],
                         "precondition: skills-src/ carries a form of each gated verb")

    def test_every_form_carries_its_identity_and_project_flags(self):
        problems = missing_required_flags(sandesh_forms(REPO_ROOT))
        self.assertEqual(problems, [], "sandesh forms missing a required flag:\n  "
                                       + "\n  ".join(problems))

    def test_detector_bites_on_missing_flags_across_wrapped_spans_and_spares_bare_verb_names(self):
        with tempfile.TemporaryDirectory(prefix="mdb-sandesh-forms-") as tmp:
            root = Path(tmp)
            _write_tree(root, {"skills-src/b/SKILL.md": (
                "Ack (`sandesh reply --project <P>\n"                                  # 1 no --from
                "   --to-msg <id> …`), or `sandesh send --project <P> --from \"<a>\"\n"   # 2 ok
                "   --to \"M\" …`.\n"
                "Name the verb (`sandesh send`) only.\n"                                # bare: spared
                "Then `sandesh unregister --project <P> --address \"<a>\"` to finish.\n"  # 5 no --as
                "```\n"
                "sandesh send --from X --to Y\n"                                        # 7 no --project
                "```\n"
                "`sandesh unregister --project P --address A --as A`\n"                 # ok
                "`sandesh reply --to-msg 7 --from A --project P`\n"                     # ok
            )})
            forms = sandesh_forms(root)
            problems = missing_required_flags(forms)
        self.assertEqual([(n, v) for _r, n, v, _f in forms],
                         [(1, "reply"), (2, "send"), (5, "unregister"), (7, "send"),
                          (9, "unregister"), (10, "reply")])
        self.assertEqual([p.split(": ", 2)[:2] for p in problems], [
            ["skills-src/b/SKILL.md:1", "sandesh reply lacks --from"],
            ["skills-src/b/SKILL.md:5", "sandesh unregister lacks --as"],
            ["skills-src/b/SKILL.md:7", "sandesh send lacks --project"],
        ])


class SandeshFormHelpConformanceTest(unittest.TestCase):
    """Every flag a form uses is listed by ``sandesh <verb> --help`` (read-only ``--help`` calls;
    skipped when ``sandesh`` is not on ``PATH``)."""

    @classmethod
    def setUpClass(cls):
        binary = shutil.which("sandesh")
        if binary is None:
            raise unittest.SkipTest("the `sandesh` CLI is not on PATH — its --help cannot be read")
        cls.help_flags = {}
        for verb in REQUIRED_FLAGS:
            result = subprocess.run([binary, verb, "--help"], capture_output=True, text=True,
                                    timeout=30, stdin=subprocess.DEVNULL)
            if result.returncode != 0:
                raise AssertionError(f"`sandesh {verb} --help` exited {result.returncode}: "
                                     f"{result.stderr!r}")
            cls.help_flags[verb] = set(FLAG_RE.findall(result.stdout))

    def test_help_lists_the_required_flags(self):
        for verb, flags in REQUIRED_FLAGS.items():
            with self.subTest(verb=verb):
                self.assertEqual(sorted(set(flags) - self.help_flags[verb]), [],
                                 f"`sandesh {verb} --help` must list {flags}")

    def test_every_flag_a_form_uses_is_in_the_verbs_help(self):
        problems = unknown_flags(sandesh_forms(REPO_ROOT), self.help_flags)
        self.assertEqual(problems, [], "flags the CLI does not know:\n  " + "\n  ".join(problems))

    def test_detector_bites_on_an_unknown_flag(self):
        forms = [("x.md", 3, "send", "sandesh send --project P --from A --sender B")]
        self.assertEqual(unknown_flags(forms, {"send": {"--project", "--from"}}),
                         ["x.md:3: sandesh send --sender not in `sandesh send --help`"])


if __name__ == "__main__":
    unittest.main()
