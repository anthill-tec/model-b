"""Client-path anchoring gates — CR-MDB-020 §S1–§S4.

Contract: ``docs/changes/CR-MDB-020-client-path-anchoring.md``. Every Crucible client reference
names the installed, published client ``~/.crucible/clients/<stack>-crucible.py`` (listed in
Crucible's manifest ``~/.crucible/crucible-clients.json``), never a personal checkout of the
Crucible project, an unrooted ``clients/`` path, or the retired ``~/.claude/scripts/`` mirror.

Class map:

- ``ClientPathAnchoringS1Test`` — §S1 text anchors over the named files (report bundles, the
  ``crucible`` skill and its references, the memory templates, ``AGENTS.md``, the two
  ``block-direct-*`` hooks, ``java-orchestration.md``). Meaning-bearing anchors, not sentences.
- ``ClientPathAnchoringS2Test`` — §S2 the anchoring gate over the exact tree list, with its
  exemption list asserted exactly, plus detector fixtures.
- ``ClientContractS3Test`` — §S3 every ``<stack>-crucible.py <verb> [--flags]`` invocation under
  the four trees checked against ``~/.crucible/clients/<stack>-crucible.py <verb> --help``. Only
  ``--help`` is ever run; the module skips (naming the missing path) with no released client.
- ``ToolContractS4Test`` — §S4 the harness-tool ratchet over ``skills-src/`` against the committed
  baseline ``TOOL_BASELINE`` (a dict in THIS module — the baseline lives beside the gate that
  reads it), plus the strict Pi tool-list check over ``generator/stacks/*.toml``.

§S3 parsing rules. An invocation is a ``<name>-crucible.py`` token followed by whitespace and a
verb, and it is read only inside a CODE context: a fenced block (backslash continuations are
joined into one logical line reported at its first line), an inline code span (the span ends the
command), or a double-quoted TOML string value (the closing quote ends it). Prose outside code is
never read, so "the rust-crucible.py wrapper" is not a verb. The command also ends at a shell
operator (``|``, ``||``, ``&&``, ``;``, ``>``) or a ``#`` comment token. A verb or token written as
a placeholder (``<…>``, ``{…}``, ``$…``) is not checked; only ``--long`` flags are checked, each
against the ``usage:`` block of the verb's ``--help``.

§S4 vocabulary rule. Claude Code tool names that are not ordinary words (``TaskUpdate``,
``EnterWorktree``, ``run_in_background``, the ``sandesh_*`` MCP verbs, …) count as whole-word,
case-sensitive matches. Claude Code tool names that ARE ordinary English words (``Bash``, ``Read``,
``Write``, ``Edit``, ``Monitor``, …) count only when written as a whole inline code span
(`` `Write` ``). Pi's ``PI_TOOL_NAMES`` keys follow the same split: a key that is a plain word
(``read``, ``write``, ``edit``, ``grep``, ``find``, ``ls``) counts only as a whole code span, a key
that is not (``ctx_read``, …) counts whole-word. Without that split the scan would count every
"read the spec" in the skills and the baseline would measure English, not tool names.
"""

import ast
import functools
import json
import re
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from modelb_axi.agents import PI_TOOL_NAMES, ROLE_DENIED_TOOLS

REPO_ROOT = Path(__file__).resolve().parents[1]

SKILLS_SRC = REPO_ROOT / "skills-src"
HOOK_SCRIPTS = REPO_ROOT / "hooks-src" / "scripts"

#: The released clients, by file name — ``crucible-clients.json`` 0.2.2 lists exactly these.
RELEASED_CLIENT_NAMES = ("arduino", "bun", "mvn", "python", "rust")
#: Where they are installed. Read ONLY by §S3, and only ever with ``--help``.
RELEASED_CLIENTS_DIR = Path.home() / ".crucible" / "clients"
#: The anchored spelling every Model B surface uses.
ANCHOR = "~/.crucible/clients/"
MANIFEST_NAME = "crucible-clients.json"

REPORT_BUNDLE_CLIENTS = {
    "crucible-report-arduino": "arduino-crucible.py",
    "crucible-report-bun": "bun-crucible.py",
    "crucible-report-java": "mvn-crucible.py",
    "crucible-report-python": "python-crucible.py",
    "crucible-report-rust": "rust-crucible.py",
}
REFERENCE_CLIENTS = {
    "arduino.md": "arduino-crucible.py",
    "bun.md": "bun-crucible.py",
    "java.md": "mvn-crucible.py",
    "python.md": "python-crucible.py",
    "rust.md": "rust-crucible.py",
}

# ----------------------------------------------------------------- §S2 scope ----

#: §S2 — the gated trees, exactly as the spec lists them.
GATED_TREES = (
    "skills-src",
    "generator",
    "hooks-src",
    "contracts",
    "modelb_axi",
    "scripts",
    "docs/research",
    "docs/install-guide.md",
    "README.md",
    "AGENTS.md",
)
#: §S2 — exempt path prefixes (dated records and the tests CR-MDB-032 §S1 repoints).
EXEMPT_PREFIXES = ("archive/", "audits/", "docs/changes/", "tests/")
#: §S2 — the one exempt LINE: the handover's provenance line (file, line prefix).
PROVENANCE_EXEMPTION = ("skills-src/CRUCIBLE-HANDOVER.md", "- **Origin repo:** ")
#: §S2 — the one exempt FILE: the verbatim secured record of Crucible's guard suite (a historical
#: artifact, not instructions) — orchestrator ruling on CR-MDB-020 C1 RED; the spec is amended.
EXEMPT_FILES = ("docs/research/crucible-clients-skills-guard.test.ts",)

CLIENT_FILE_RE = r"(?:[a-z]+|<stack>|\{stack\}|\*)-crucible\.py"
RE_CHECKOUT = re.compile(r"data_projects/crucible")
RE_CLIENTS_PATH = re.compile(r"clients/" + CLIENT_FILE_RE)
RE_MIRROR = re.compile(r"\.claude/scripts/[\w<>{}*.-]*-crucible\.py")

# ------------------------------------------------------------------ utils -------

_SKIP_DIRS = {"__pycache__"}


def _iter_text_files(root, rel_root):
    """Yield (rel, text) for every UTF-8 file under ``root/rel_root`` (dir or file)."""
    target = root / rel_root
    if target.is_file():
        paths = [target]
    elif target.is_dir():
        paths = sorted(p for p in target.rglob("*") if p.is_file())
    else:
        return
    for path in paths:
        rel = path.relative_to(root).as_posix()
        parts = Path(rel).parts
        if any(p in _SKIP_DIRS or (p.startswith(".") and p != ".") for p in parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        yield rel, text


def _read(rel):
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def _paragraphs(text):
    """Blank-line separated paragraphs, whitespace-normalised to one line each."""
    return [" ".join(chunk.split()) for chunk in re.split(r"\n\s*\n", text) if chunk.strip()]


def _sentences(text):
    out = []
    for para in _paragraphs(text):
        out.extend(s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z`*(])", para) if s)
    return out


# ------------------------------------------------------------ §S2 detector ------


def _anchoring_hits(root, trees=GATED_TREES):
    """Return [(rel, lineno, kind, line)] — every unanchored client path in ``trees``.

    kinds: ``checkout`` (a personal Crucible checkout), ``unrooted`` (``clients/<stack>-crucible.py``
    not immediately under ``/.crucible/``), ``mirror`` (``~/.claude/scripts/*-crucible.py``).
    """
    hits = []
    for tree in trees:
        for rel, text in _iter_text_files(root, tree):
            if rel.startswith(EXEMPT_PREFIXES) or rel in EXEMPT_FILES:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                if rel == PROVENANCE_EXEMPTION[0] and line.startswith(PROVENANCE_EXEMPTION[1]):
                    continue
                if RE_CHECKOUT.search(line):
                    hits.append((rel, lineno, "checkout", line))
                for m in RE_CLIENTS_PATH.finditer(line):
                    if not line[: m.start()].endswith("/.crucible/"):
                        hits.append((rel, lineno, "unrooted", line))
                        break
                if RE_MIRROR.search(line):
                    hits.append((rel, lineno, "mirror", line))
    return hits


def _fmt_hits(hits):
    return "\n".join(f"  {rel}:{n} [{kind}] {line.strip()[:150]}" for rel, n, kind, line in hits)


# ------------------------------------------------- §S1 copy/vendor detector -----

#: §S1 — a site-packages / package-internal client path, a Model B copy of a client, or an
#: instruction to copy, patch or edit one. The required statement "not shipped, vendored or
#: maintained by Model B" must NOT match (proved by a fixture below).
COPY_PATTERNS = (
    ("site-packages client path", re.compile(r"site-packages\S*crucible|crucible\S*site-packages", re.I)),
    ("package-internal client path", re.compile(r"_assets/\S*-crucible\.py")),
    ("project-vendored client copy", re.compile(r"project-vendored", re.I)),
    ("vendored clients/ copy", re.compile(r"vendored\s+`?clients/", re.I)),
    ("vendor a copy", re.compile(r"\bvendor(?:ed)?\s+a\s+copy\b", re.I)),
    ("copy is valid", re.compile(r"\bcopy\s+is\s+valid\b", re.I)),
    ("Model B copy of a client", re.compile(r"\bModel B(?:'s)?\s+(?:own\s+)?cop(?:y|ies)\b", re.I)),
    (
        "copy/patch/edit instruction",
        re.compile(
            r"^(?!.*\b(?:never|not|no|nor|don't|do not)\b).*"
            r"\b(?:copy|patch|edit|modify)\s+(?:the\s+|a\s+|your\s+)?(?:installed\s+)?"
            r"(?:Crucible\s+client|[a-z]+-crucible\.py)",
            re.I,
        ),
    ),
)


def _copy_hits_in_text(rel, text):
    hits = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for label, rx in COPY_PATTERNS:
            if rx.search(line):
                hits.append((rel, lineno, label, line))
    return hits


# ------------------------------------------------------------ §S3 parser --------

RE_INVOCATION = re.compile(r"(?<![\w-])([a-z]+|<stack>|\{stack\})-crucible\.py\s+(\S+)")
RE_VERB = re.compile(r"^[a-z][a-z0-9-]*$")
RE_FLAG = re.compile(r"^--[A-Za-z][\w-]*")
_STOP_TOKENS = {"|", "||", "&&", ";", ">", ">>", "2>&1", "→", "&"}
_STRIP = "[](),`'\";:"


def _logical_lines(text):
    """Yield (spans, logical_line, kind) with fenced backslash continuations joined.

    ``spans`` maps offsets in the logical line back to physical line numbers as
    [(offset, lineno), ...]; kind is ``fence`` for fenced-block lines, else ``text``.
    """
    lines = text.splitlines()
    in_fence = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
            i += 1
            continue
        if in_fence:
            spans = [(0, i + 1)]
            buf = line
            while buf.rstrip().endswith("\\") and i + 1 < len(lines):
                i += 1
                buf = buf.rstrip()[:-1] + " "
                spans.append((len(buf), i + 1))
                buf += lines[i].strip()
            yield spans, buf, "fence"
        else:
            yield [(0, i + 1)], line, "text"
        i += 1


def _lineno_at(spans, offset):
    return [n for off, n in spans if off <= offset][-1]


def _code_segment(line, start, kind, toml):
    """Return the command text starting at ``start`` if it sits in a code context, else None."""
    if kind == "fence":
        return line[start:]
    before = line[:start]
    if before.count("`") % 2 == 1:
        end = line.find("`", start)
        return line[start:] if end == -1 else line[start:end]
    if toml and re.match(r"^\s*[\w.-]+\s*=\s*\"", line):
        quotes = len(re.findall(r'(?<!\\)"', before))
        if quotes % 2 == 1:
            m = re.search(r'(?<!\\)"', line[start:])
            return line[start:] if m is None else line[start : start + m.start()]
    return None


def _parse_invocations(rel, text):
    """Return [{file, line, client, verb, flags}] for every checkable client invocation."""
    out = []
    toml = rel.endswith(".toml")
    for spans, line, kind in _logical_lines(text):
        for m in RE_INVOCATION.finditer(line):
            segment = _code_segment(line, m.start(), kind, toml)
            if segment is None:
                continue
            tokens = segment.split()[1:]  # drop the client token
            if not tokens:
                continue
            verb = tokens[0].strip(_STRIP)
            client = m.group(1)
            if client.startswith(("<", "{")) or verb.startswith(("<", "{", "$", "-")):
                continue
            if not RE_VERB.match(verb):
                continue
            flags = []
            for tok in tokens[1:]:
                if tok in _STOP_TOKENS or tok.startswith("#"):
                    break
                bare = tok.strip(_STRIP).split("=", 1)[0]
                if bare.startswith(("<", "{", "$")):
                    continue
                fm = RE_FLAG.match(bare)
                if fm and fm.group(0) == bare:
                    flags.append(bare)
            out.append({"file": rel, "line": _lineno_at(spans, m.start()), "client": client,
                        "verb": verb, "flags": flags})
    return out


def _collect_invocations(root, trees):
    found = []
    for tree in trees:
        for rel, text in _iter_text_files(root, tree):
            found.extend(_parse_invocations(rel, text))
    return found


@functools.cache
def _client_help(client_path, verb):
    """(ok, flags) for ``python3 <client_path> <verb> --help`` — help only, cached."""
    proc = subprocess.run(
        [sys.executable, client_path, verb, "--help"],
        capture_output=True, text=True, timeout=60, cwd=tempfile.gettempdir(),
    )
    if proc.returncode != 0:
        return False, frozenset()
    usage = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            if usage:
                break
            continue
        if usage or line.startswith("usage:"):
            usage.append(line)
    return True, frozenset(re.findall(r"--[A-Za-z][\w-]*", "\n".join(usage)))


def _contract_failures(invocations, clients_dir):
    """Check each invocation against the released client; raise SkipTest if one is absent."""
    needed = sorted({inv["client"] for inv in invocations if inv["client"] in RELEASED_CLIENT_NAMES})
    missing = [clients_dir / f"{c}-crucible.py" for c in needed if not (clients_dir / f"{c}-crucible.py").is_file()]
    if missing:
        raise unittest.SkipTest(
            "released Crucible client absent: " + ", ".join(str(p) for p in missing)
        )
    failures = []
    for inv in invocations:
        where = f"{inv['file']}:{inv['line']}"
        if inv["client"] not in RELEASED_CLIENT_NAMES:
            failures.append(f"{where}: {inv['client']}-crucible.py is not a released client")
            continue
        ok, flags = _client_help(str(clients_dir / f"{inv['client']}-crucible.py"), inv["verb"])
        if not ok:
            failures.append(
                f"{where}: {inv['client']}-crucible.py has no verb '{inv['verb']}'"
            )
            continue
        for flag in inv["flags"]:
            if flag not in flags:
                failures.append(
                    f"{where}: {inv['client']}-crucible.py {inv['verb']} has no flag '{flag}'"
                )
    return failures


# ------------------------------------------------------------ §S4 vocabulary ----

#: Claude Code tool names that are not ordinary words — counted whole-word.
CLAUDE_TOOLS_WHOLE_WORD = (
    "TaskList", "TaskUpdate", "TaskStop", "TaskCreate", "TaskGet", "TaskOutput",
    "EnterWorktree", "ExitWorktree", "run_in_background",
    "NotebookEdit", "AskUserQuestion", "TodoWrite", "WebFetch", "WebSearch",
    "BashOutput", "KillShell", "SendMessage", "ScheduleWakeup", "EnterPlanMode", "ExitPlanMode",
    "sandesh_send", "sandesh_reply", "sandesh_fetch", "sandesh_inbox",
    "sandesh_register", "sandesh_unregister", "sandesh_addressbook", "sandesh_setup",
)
#: Claude Code tool names that are ordinary words — counted only as a whole code span.
CLAUDE_TOOLS_CODE_SPAN = (
    "Bash", "Read", "Write", "Edit", "Glob", "Grep", "Agent", "Task", "Skill", "Monitor",
)


def _is_ordinary_word(name):
    return name.isalpha()


def _tool_vocabulary():
    """(whole_word_names, code_span_names) — Claude Code's plus Pi's ``PI_TOOL_NAMES`` keys."""
    pi = sorted(PI_TOOL_NAMES)
    whole = tuple(CLAUDE_TOOLS_WHOLE_WORD) + tuple(n for n in pi if not _is_ordinary_word(n))
    span = tuple(CLAUDE_TOOLS_CODE_SPAN) + tuple(n for n in pi if _is_ordinary_word(n))
    return whole, span


def _count_tools(text):
    whole, span = _tool_vocabulary()
    counts = {}
    for name in whole:
        n = len(re.findall(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", text))
        if n:
            counts[name] = counts.get(name, 0) + n
    for name in span:
        n = len(re.findall(rf"`{re.escape(name)}`", text))
        if n:
            counts[name] = counts.get(name, 0) + n
    return counts


def _tool_occurrences(root, tree="skills-src"):
    observed = {}
    for rel, text in _iter_text_files(root, tree):
        counts = _count_tools(text)
        if counts:
            observed[rel] = dict(sorted(counts.items()))
    return observed


def _ratchet_violations(observed, baseline):
    """Failure messages for every (file, tool) whose count rose or is new; lowering is fine."""
    out = []
    for rel, counts in sorted(observed.items()):
        base = baseline.get(rel)
        for tool, n in sorted(counts.items()):
            if base is None:
                out.append(f"{rel}: new file names harness tool '{tool}' ({n}x; not in baseline)")
            elif tool not in base:
                out.append(f"{rel}: new harness tool '{tool}' ({n}x; not in baseline)")
            elif n > base[tool]:
                out.append(f"{rel}: harness tool '{tool}' rose {base[tool]} -> {n}")
    return out


#: §S4 — today's occurrences, measured on this branch at RED (11 files, 42 occurrences). May
#: only shrink; CR-MDB-031 drains it to zero without adding exemptions. File -> {tool: count}.
TOOL_BASELINE = {
    "skills-src/bootstrap/SKILL.md": {
        "TaskList": 1, "TaskUpdate": 1, "sandesh_addressbook": 6, "sandesh_inbox": 1,
        "sandesh_register": 2, "sandesh_send": 1, "sandesh_setup": 2,
    },
    "skills-src/crucible/SKILL.md": {"run_in_background": 1},
    "skills-src/memory-templates/java-orchestration.md": {"ExitWorktree": 1},
    "skills-src/memory-templates/java-testing-practices.md": {"find": 1},
    "skills-src/memory-templates/rust-orchestration.md": {"ExitWorktree": 1},
    "skills-src/model-b/references/orchestration-common.md": {"EnterWorktree": 1, "ExitWorktree": 1},
    "skills-src/model-b/references/orchestration-mainline.md": {"AskUserQuestion": 1},
    "skills-src/model-b/references/orchestration-track.md": {
        "EnterWorktree": 2, "ExitWorktree": 1, "run_in_background": 1, "sandesh_reply": 1,
    },
    "skills-src/model-b/references/sandesh.md": {
        "sandesh_addressbook": 4, "sandesh_register": 1, "sandesh_reply": 2, "sandesh_setup": 1,
    },
    "skills-src/model-b/references/sub-agent-procedure.md": {"Edit": 1, "NotebookEdit": 1, "Write": 1},
    "skills-src/shutdown/SKILL.md": {
        "sandesh_addressbook": 1, "sandesh_reply": 1, "sandesh_send": 2, "sandesh_unregister": 1,
    },
}


def _pi_tool_violations(stack_tomls):
    """Every [roles.*].tools entry (and every role deny) that is not a PI_TOOL_NAMES key."""
    out = []
    for name, text in sorted(stack_tomls.items()):
        params = tomllib.loads(text)
        for role, table in sorted(params.get("roles", {}).items()):
            for tool in list(table.get("tools", [])) + list(ROLE_DENIED_TOOLS.get(role, ())):
                if tool not in PI_TOOL_NAMES:
                    out.append(f"{name} [roles.{role}]: '{tool}' is not a PI_TOOL_NAMES key")
    return out


# ================================================================= §S1 ==========


def _run_hook(name, payload):
    return subprocess.run(
        [sys.executable, str(HOOK_SCRIPTS / name)], input=json.dumps(payload),
        capture_output=True, text=True, timeout=10,
    )


class ClientPathAnchoringS1Test(unittest.TestCase):
    """§S1 — every client reference names the installed client."""

    maxDiff = None

    def test_s1_each_report_bundle_names_its_installed_client(self):
        missing, unanchored = [], []
        for bundle, client in REPORT_BUNDLE_CLIENTS.items():
            text = _read(f"skills-src/{bundle}/SKILL.md")
            if ANCHOR + client not in text:
                missing.append(f"{bundle}: {ANCHOR}{client}")
            unanchored.extend(_anchoring_hits(REPO_ROOT, (f"skills-src/{bundle}",)))
        self.assertEqual(missing, [], f"§S1: report bundles not naming the installed client: {missing}")
        self.assertEqual(unanchored, [], "§S1: unanchored client paths in report bundles:\n" + _fmt_hits(unanchored))

    def test_s1_each_crucible_reference_names_its_installed_client(self):
        missing, unanchored = [], []
        for ref, client in REFERENCE_CLIENTS.items():
            rel = f"skills-src/crucible/references/{ref}"
            if ANCHOR + client not in _read(rel):
                missing.append(f"{rel}: {ANCHOR}{client}")
            unanchored.extend(_anchoring_hits(REPO_ROOT, (rel,)))
        self.assertEqual(missing, [], f"§S1: references not naming the installed client: {missing}")
        self.assertEqual(unanchored, [], "§S1: unanchored client paths in references:\n" + _fmt_hits(unanchored))

    def test_s1_each_report_bundle_states_installer_provenance_exactly_once(self):
        rx_installer = re.compile(r"\bCrucible(?:'s|’s)?\s+(?:own\s+)?installer\b|\binstalled\s+by\s+Crucible\b", re.I)
        rx_not_model_b = re.compile(
            r"\b(?:not|never)\b[^.]{0,80}\b(?:shipped|maintained)\b[^.]{0,80}\bModel B\b"
        )
        failures = []
        for bundle in REPORT_BUNDLE_CLIENTS:
            paras = [p for p in _paragraphs(_read(f"skills-src/{bundle}/SKILL.md")) if MANIFEST_NAME in p]
            if len(paras) != 1:
                failures.append(f"{bundle}: {len(paras)} paragraphs name {MANIFEST_NAME} (want exactly 1)")
                continue
            para = paras[0]
            if not rx_installer.search(para):
                failures.append(f"{bundle}: statement does not say Crucible's installer installs it")
            if not rx_not_model_b.search(para):
                failures.append(f"{bundle}: statement does not say it is not shipped/maintained by Model B")
        self.assertEqual(failures, [], "§S1 provenance statement:\n  " + "\n  ".join(failures))

    def test_s1_provenance_statement_detector_accepts_the_spec_wording(self):
        # Proof a correct bundle can pass: the spec's own wording satisfies the anchors.
        para = (
            "The client is `~/.crucible/clients/rust-crucible.py`, the default location of "
            "Crucible's installed clients, listed in `~/.crucible/crucible-clients.json` and "
            "installed by Crucible's own installer; it is not shipped, vendored or maintained "
            "by Model B."
        )
        self.assertRegex(para, r"\bCrucible(?:'s)?\s+(?:own\s+)?installer\b")
        self.assertRegex(para, r"\b(?:not|never)\b[^.]{0,80}\b(?:shipped|maintained)\b[^.]{0,80}\bModel B\b")
        self.assertEqual(_copy_hits_in_text("fixture.md", para), [])

    def test_s1_crucible_skill_states_the_checkout_rule_and_reason_in_one_sentence(self):
        needed = (
            re.compile(r"\bcheckout\b", re.I),
            re.compile(r"crucible\.toml"),
            re.compile(r"\blocation\b", re.I),
            re.compile(r"\bboard\b", re.I),
            re.compile(r"\bproject key\b", re.I),
            re.compile(r"\b(?:never|not|do not|don't)\b", re.I),
        )
        sentences = _sentences(_read("skills-src/crucible/SKILL.md"))
        matching = [s for s in sentences if all(rx.search(s) for rx in needed)]
        self.assertEqual(
            len(matching), 1,
            "§S1: skills-src/crucible/SKILL.md must state the checkout rule and its reason in ONE "
            "sentence (checkout never used; own crucible.toml; config resolved from the client's "
            f"location; posts to the checkout's board with the right project key); found {matching}",
        )

    def test_s1_crucible_skill_names_the_installed_clients_and_manifest(self):
        text = _read("skills-src/crucible/SKILL.md")
        self.assertTrue("~/.crucible/clients/<stack>-crucible.py" in text,
                        "§S1: crucible/SKILL.md must name ~/.crucible/clients/<stack>-crucible.py")
        self.assertTrue(MANIFEST_NAME in text, f"§S1: crucible/SKILL.md must name {MANIFEST_NAME}")
        self.assertFalse("data_projects/crucible" in text, "§S1: crucible/SKILL.md still names the checkout")

    def test_s1_memory_templates_name_the_installed_client(self):
        expected = {
            "skills-src/memory-templates/java-testing-practices.md": "mvn-crucible.py",
            "skills-src/memory-templates/java-orchestration.md": "mvn-crucible.py",
            "skills-src/memory-templates/rust-orchestration.md": "rust-crucible.py",
        }
        missing = [f"{rel}: {ANCHOR}{c}" for rel, c in expected.items() if ANCHOR + c not in _read(rel)]
        self.assertEqual(missing, [], f"§S1: memory templates not naming the installed client: {missing}")
        hits = _anchoring_hits(REPO_ROOT, tuple(expected))
        self.assertEqual(hits, [], "§S1: unanchored client paths:\n" + _fmt_hits(hits))

    def test_s1_no_site_packages_package_internal_copy_or_edit_instruction(self):
        hits = []
        for tree in GATED_TREES:
            for rel, text in _iter_text_files(REPO_ROOT, tree):
                hits.extend(_copy_hits_in_text(rel, text))
        self.assertEqual(hits, [], "§S1: copy/vendor/site-packages client wording:\n" + _fmt_hits(hits))

    def test_s1_copy_detector_bites_on_vendoring_and_site_packages(self):
        fixture = "\n".join((
            "A project-vendored `clients/` copy is valid ONLY while a CR changes it.",
            "never vendor a copy unless a CR is changing the client",
            "Run it from site-packages/crucible/clients/rust-crucible.py",
            "Model B ships modelb_axi/_assets/clients/rust-crucible.py",
            "Copy the rust-crucible.py into your project and patch it.",
        ))
        labels = sorted({label for _, _, label, _ in _copy_hits_in_text("f.md", fixture)})
        self.assertEqual(
            labels,
            sorted({"project-vendored client copy", "vendored clients/ copy", "copy is valid",
                    "vendor a copy", "site-packages client path", "package-internal client path",
                    "copy/patch/edit instruction"}),
        )
        lines = sorted({n for _, n, _, _ in _copy_hits_in_text("f.md", fixture)})
        self.assertEqual(lines, [1, 2, 3, 4, 5])

    def test_s1_agents_md_drops_checkout_prefix_and_runs_the_installed_client(self):
        text = _read("AGENTS.md")
        self.assertFalse("data_projects/crucible" in text, "§S1: AGENTS.md still names the checkout")
        self.assertIsNone(
            re.search(r"`crucible:`\s*=", text),
            "§S1: AGENTS.md still defines the `crucible:` checkout path prefix",
        )
        self.assertIn(
            "python3 ~/.crucible/clients/python-crucible.py regression", text,
            "§S1: AGENTS.md's canonical run must use ~/.crucible/clients/python-crucible.py",
        )

    def _assert_reason_names_manifest_client(self, label, reason, client):
        self.assertTrue(MANIFEST_NAME in reason, f"§S1: {label} must name Crucible's manifest {MANIFEST_NAME}")
        self.assertTrue(ANCHOR + client in reason, f"§S1: {label} must name {ANCHOR}{client}")
        self.assertFalse("install config" in reason, f"§S1: {label} still says 'install config'")
        self.assertIsNone(re.search(r"crucible repo\s+`?clients/", reason),
                          f"§S1: {label} still names the crucible repo clients/ dir")

    def test_s1_cargo_hook_block_reasons_name_the_manifest_listed_client(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "Cargo.toml").write_text("[package]\nname='x'\n")
            plain = _run_hook("block-direct-cargo-test", {
                "tool_name": "bash", "tool_input": {"command": "cargo test"}, "cwd": tmp})
            ds = _run_hook("block-direct-cargo-test", {
                "tool_name": "bash",
                "tool_input": {"command": "cargo build", "dangerouslyDisableSandbox": True},
                "cwd": tmp})
        self.assertEqual(plain.returncode, 2, plain.stderr)
        self.assertEqual(ds.returncode, 2, ds.stderr)
        self._assert_reason_names_manifest_client(
            "cargo REASON", json.loads(plain.stdout)["reason"], "rust-crucible.py")
        self._assert_reason_names_manifest_client(
            "cargo DS_REASON", json.loads(ds.stdout)["reason"], "rust-crucible.py")

    def test_s1_mvn_hook_block_reason_names_the_manifest_listed_client(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "pom.xml").write_text("<project/>\n")
            res = _run_hook("block-direct-mvn-test", {
                "tool_name": "bash", "tool_input": {"command": "mvn test"}, "cwd": tmp})
        self.assertEqual(res.returncode, 2, res.stderr)
        self._assert_reason_names_manifest_client(
            "mvn REASON", json.loads(res.stdout)["reason"], "mvn-crucible.py")

    def test_s1_block_hook_docstrings_name_the_manifest_listed_client(self):
        failures = []
        for name in ("block-direct-cargo-test", "block-direct-mvn-test"):
            doc = ast.get_docstring(ast.parse((HOOK_SCRIPTS / name).read_text(encoding="utf-8"))) or ""
            if MANIFEST_NAME not in doc:
                failures.append(f"{name}: docstring does not name {MANIFEST_NAME}")
            if "install config" in doc:
                failures.append(f"{name}: docstring still says 'install config'")
            if re.search(r"crucible repo\s+`?clients/", doc):
                failures.append(f"{name}: docstring still names the crucible repo clients/ dir")
        self.assertEqual(failures, [], "§S1 hook docstrings:\n  " + "\n  ".join(failures))

    def test_s1_java_orchestration_names_no_reviewer_skill(self):
        rel = "skills-src/memory-templates/java-orchestration.md"
        hits = [f"{rel}:{n}: {sorted(set(re.findall(r'reviewer-[a-z]+', line)))}"
                for n, line in enumerate(_read(rel).splitlines(), 1) if re.search(r"\breviewer-[a-z]", line)]
        self.assertEqual(hits, [], f"§S1: java-orchestration.md names unshipped reviewer-* skills: {hits}")


# ================================================================= §S2 ==========


def _fixture_tree(files):
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp, root


class ClientPathAnchoringS2Test(unittest.TestCase):
    """§S2 — the anchoring gate, its exemptions, and its detectors."""

    maxDiff = None

    def test_s2_gated_trees_carry_no_unanchored_client_path(self):
        hits = _anchoring_hits(REPO_ROOT)
        self.assertEqual(
            hits, [],
            f"§S2: {len(hits)} unanchored Crucible client path(s) — name "
            f"{ANCHOR}<stack>-crucible.py instead:\n" + _fmt_hits(hits),
        )

    def test_s2_gated_tree_list_is_exact(self):
        self.assertEqual(GATED_TREES, (
            "skills-src", "generator", "hooks-src", "contracts", "modelb_axi", "scripts",
            "docs/research", "docs/install-guide.md", "README.md", "AGENTS.md",
        ))
        absent = [t for t in GATED_TREES if not (REPO_ROOT / t).exists()]
        self.assertEqual(absent, [], f"§S2: gated trees missing from the repo: {absent}")

    def test_s2_exemption_list_is_exact(self):
        self.assertEqual(EXEMPT_PREFIXES, ("archive/", "audits/", "docs/changes/", "tests/"))
        self.assertEqual(PROVENANCE_EXEMPTION, ("skills-src/CRUCIBLE-HANDOVER.md", "- **Origin repo:** "))
        self.assertEqual(EXEMPT_FILES, ("docs/research/crucible-clients-skills-guard.test.ts",))
        missing = [f for f in EXEMPT_FILES if not (REPO_ROOT / f).is_file()]
        self.assertEqual(missing, [], f"§S2: exempt file no longer exists \u2014 drop it: {missing}")
        overlap = [t for t in GATED_TREES if (t + "/").startswith(EXEMPT_PREFIXES)]
        self.assertEqual(overlap, [], f"§S2: a gated tree sits under an exemption: {overlap}")

    def test_s2_provenance_exemption_covers_exactly_the_one_origin_line(self):
        lines = _read(PROVENANCE_EXEMPTION[0]).splitlines()
        covered = [line for line in lines if line.startswith(PROVENANCE_EXEMPTION[1])]
        self.assertEqual(len(covered), 1, f"§S2: provenance exemption must cover one line, covers {covered}")
        self.assertIn("data_projects/crucible", covered[0])

    def test_s2_provenance_exemption_does_not_cover_other_handover_lines(self):
        tmp, root = _fixture_tree({
            "skills-src/CRUCIBLE-HANDOVER.md":
                "- **Origin repo:** `~/Documents/data_projects/crucible` (the Crucible repo)\n"
                "Run `~/Documents/data_projects/crucible/clients/rust-crucible.py test`.\n",
        })
        with tmp:
            hits = _anchoring_hits(root)
        self.assertEqual(
            [(rel, n, kind) for rel, n, kind, _ in hits],
            [("skills-src/CRUCIBLE-HANDOVER.md", 2, "checkout"),
             ("skills-src/CRUCIBLE-HANDOVER.md", 2, "unrooted")],
        )

    def test_s2_exempt_file_covers_only_the_guard_record(self):
        text = 'scriptSubcommandPin(content, "clients/rust-crucible.py", [\n'
        tmp, root = _fixture_tree({
            "docs/research/crucible-clients-skills-guard.test.ts": text,
            "docs/research/other-guard.test.ts": text,
        })
        with tmp:
            hits = _anchoring_hits(root, ("docs/research",))
        self.assertEqual([(rel, n, kind) for rel, n, kind, _ in hits],
                         [("docs/research/other-guard.test.ts", 1, "unrooted")])

    def test_s2_exempt_prefixes_are_not_scanned(self):
        tmp, root = _fixture_tree({
            "docs/changes/CR-X.md": "was `~/Documents/data_projects/crucible/clients/rust-crucible.py`\n",
            "docs/research/DN-x.md": "run `clients/rust-crucible.py test`\n",
        })
        with tmp:
            hits = _anchoring_hits(root, ("docs",))
        self.assertEqual([(rel, n, kind) for rel, n, kind, _ in hits],
                         [("docs/research/DN-x.md", 1, "unrooted")])

    def _gate_on(self, line):
        tmp, root = _fixture_tree({"skills-src/x/SKILL.md": "intro\n" + line + "\n"})
        with tmp:
            return [(rel, n, kind) for rel, n, kind, _ in _anchoring_hits(root)]

    def test_s2_gate_fails_on_a_checkout_path(self):
        self.assertIn(("skills-src/x/SKILL.md", 2, "checkout"),
                      self._gate_on("python3 ~/Documents/data_projects/crucible/clients/rust-crucible.py test"))

    def test_s2_gate_fails_on_an_unrooted_clients_path(self):
        self.assertEqual(self._gate_on("python3 clients/rust-crucible.py test --crate c"),
                         [("skills-src/x/SKILL.md", 2, "unrooted")])

    def test_s2_gate_fails_on_the_retired_claude_scripts_mirror(self):
        self.assertEqual(self._gate_on("python3 ~/.claude/scripts/rust-crucible.py test"),
                         [("skills-src/x/SKILL.md", 2, "mirror")])

    def test_s2_gate_passes_on_the_installed_client_path(self):
        self.assertEqual(self._gate_on("python3 ~/.crucible/clients/rust-crucible.py test --crate c"), [])
        self.assertEqual(self._gate_on("the default `~/.crucible/clients/<stack>-crucible.py`"), [])


# ================================================================= §S3 ==========

S3_TREES = ("skills-src", "generator/templates", "generator/stacks", "contracts")


class ClientContractS3Test(unittest.TestCase):
    """§S3 — documented client invocations against the released client's ``--help``."""

    maxDiff = None

    def test_s3_documented_invocations_match_the_released_client(self):
        invocations = _collect_invocations(REPO_ROOT, S3_TREES)
        self.assertGreater(len(invocations), 0, "§S3: found no client invocations — the parser is vacuous")
        clients = {inv["client"] for inv in invocations}
        self.assertEqual(
            clients & set(RELEASED_CLIENT_NAMES), set(RELEASED_CLIENT_NAMES),
            f"§S3: expected invocations of all five released clients, found {sorted(clients)}",
        )
        failures = _contract_failures(invocations, RELEASED_CLIENTS_DIR)
        self.assertEqual(
            failures, [],
            f"§S3: {len(failures)} invocation(s) disagree with the released client:\n  "
            + "\n  ".join(failures),
        )

    def test_s3_parser_joins_fenced_backslash_continuations(self):
        text = (
            "Run:\n\n```bash\n"
            "python3 ~/.crucible/clients/python-crucible.py regression --coverage \\\n"
            "  --agent vidushi-mdb --project-dir \"$PWD\"   # the gate\n"
            "```\n"
        )
        self.assertEqual(_parse_invocations("f.md", text), [{
            "file": "f.md", "line": 4, "client": "python", "verb": "regression",
            "flags": ["--coverage", "--agent", "--project-dir"],
        }])

    def test_s3_parser_skips_placeholders_and_prose(self):
        text = "\n".join((
            "Prose: the rust-crucible.py wrapper runs cargo.",
            "Span: `python-crucible.py test --tests <dotted.path> [--agent {id}]` then more.",
            "Generic: `<stack>-crucible.py <verb> --help`.",
            "Placeholder verb: `rust-crucible.py <verb> --crate c`.",
        ))
        self.assertEqual(_parse_invocations("f.md", text), [{
            "file": "f.md", "line": 2, "client": "python", "verb": "test",
            "flags": ["--tests", "--agent"],
        }])

    def test_s3_parser_reads_toml_string_values(self):
        text = 'register_command = "python3 ~/.crucible/clients/mvn-crucible.py register --agent YOUR_AGENT_ID"\n'
        self.assertEqual(_parse_invocations("generator/stacks/q.toml", text), [{
            "file": "generator/stacks/q.toml", "line": 1, "client": "mvn",
            "verb": "register", "flags": ["--agent"],
        }])

    def _released_or_skip(self):
        path = RELEASED_CLIENTS_DIR / "python-crucible.py"
        if not path.is_file():
            self.skipTest(f"released Crucible client absent: {path}")

    def test_s3_unknown_flag_fails_naming_file_line_verb_and_flag(self):
        self._released_or_skip()
        inv = _parse_invocations(
            "skills-src/x/SKILL.md",
            "a\nb\n`python3 ~/.crucible/clients/python-crucible.py test --tests t --no-such-flag`\n",
        )
        self.assertEqual(
            _contract_failures(inv, RELEASED_CLIENTS_DIR),
            ["skills-src/x/SKILL.md:3: python-crucible.py test has no flag '--no-such-flag'"],
        )

    def test_s3_unknown_verb_fails_naming_file_line_and_verb(self):
        self._released_or_skip()
        inv = _parse_invocations("contracts/x.md", "`python-crucible.py frobnicate --agent X`\n")
        self.assertEqual(
            _contract_failures(inv, RELEASED_CLIENTS_DIR),
            ["contracts/x.md:1: python-crucible.py has no verb 'frobnicate'"],
        )

    def test_s3_known_verb_and_flags_pass(self):
        self._released_or_skip()
        inv = _parse_invocations("f.md", "`python-crucible.py test --tests t --agent X`\n")
        self.assertEqual(_contract_failures(inv, RELEASED_CLIENTS_DIR), [])

    def test_s3_absent_released_client_skips_naming_the_missing_path(self):
        inv = [{"file": "f.md", "line": 1, "client": "rust", "verb": "test", "flags": []}]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(unittest.SkipTest) as ctx:
                _contract_failures(inv, Path(tmp))
            self.assertIn(str(Path(tmp) / "rust-crucible.py"), str(ctx.exception))


# ================================================================= §S4 ==========


class ToolContractS4Test(unittest.TestCase):
    """§S4 — the harness-tool ratchet and the Pi tool-list check."""

    def test_s4_vocabulary_declares_the_spec_names_and_every_pi_tool(self):
        whole, span = _tool_vocabulary()
        vocab = set(whole) | set(span)
        spec_names = {
            "TaskList", "TaskUpdate", "TaskStop", "TaskCreate", "TaskOutput", "EnterWorktree",
            "ExitWorktree", "run_in_background", "sandesh_send", "sandesh_reply", "sandesh_fetch",
            "sandesh_inbox", "sandesh_register", "sandesh_unregister", "sandesh_addressbook",
            "sandesh_setup",
        }
        self.assertEqual(spec_names - vocab, set())
        self.assertEqual(set(PI_TOOL_NAMES) - vocab, set())
        self.assertEqual(
            sorted(n for n in span if n in PI_TOOL_NAMES),
            sorted(n for n in PI_TOOL_NAMES if n.isalpha()),
        )

    def test_s4_ordinary_word_names_count_only_as_code_spans(self):
        text = "Read the spec, write a test, then `read` it; grep it. Use `Write` and ctx_read and TaskUpdate."
        self.assertEqual(_count_tools(text), {"read": 1, "Write": 1, "ctx_read": 1, "TaskUpdate": 1})

    def test_s4_baseline_is_committed_and_non_empty(self):
        self.assertTrue(TOOL_BASELINE, "§S4: the tool baseline must be committed")
        self.assertIn("TaskUpdate", TOOL_BASELINE.get("skills-src/bootstrap/SKILL.md", {}))

    def test_s4_skills_tree_does_not_exceed_the_tool_baseline(self):
        violations = _ratchet_violations(_tool_occurrences(REPO_ROOT), TOOL_BASELINE)
        self.assertEqual(violations, [], "§S4 ratchet:\n  " + "\n  ".join(violations))

    def test_s4_adding_task_update_to_a_bundle_fails_naming_file_and_tool(self):
        baseline = {"skills-src/b/SKILL.md": {"EnterWorktree": 1}}
        tmp, root = _fixture_tree({"skills-src/b/SKILL.md": "Use EnterWorktree, then TaskUpdate.\n"})
        with tmp:
            violations = _ratchet_violations(_tool_occurrences(root), baseline)
        self.assertEqual(violations, ["skills-src/b/SKILL.md: new harness tool 'TaskUpdate' (1x; not in baseline)"])

    def test_s4_a_rising_count_fails(self):
        baseline = {"skills-src/b/SKILL.md": {"TaskUpdate": 1}}
        tmp, root = _fixture_tree({"skills-src/b/SKILL.md": "TaskUpdate then TaskUpdate.\n"})
        with tmp:
            violations = _ratchet_violations(_tool_occurrences(root), baseline)
        self.assertEqual(violations, ["skills-src/b/SKILL.md: harness tool 'TaskUpdate' rose 1 -> 2"])

    def test_s4_a_new_file_fails(self):
        tmp, root = _fixture_tree({"skills-src/new/SKILL.md": "call sandesh_fetch\n"})
        with tmp:
            violations = _ratchet_violations(_tool_occurrences(root), {})
        self.assertEqual(violations, ["skills-src/new/SKILL.md: new file names harness tool 'sandesh_fetch' (1x; not in baseline)"])

    def test_s4_lowering_a_count_passes(self):
        baseline = {"skills-src/b/SKILL.md": {"TaskUpdate": 3, "EnterWorktree": 1}}
        tmp, root = _fixture_tree({"skills-src/b/SKILL.md": "TaskUpdate once.\n", "skills-src/c/x.md": "clean\n"})
        with tmp:
            self.assertEqual(_ratchet_violations(_tool_occurrences(root), baseline), [])

    def test_s4_every_stack_template_pi_tool_is_a_pi_tool_name(self):
        tomls = {p.name: p.read_text(encoding="utf-8")
                 for p in sorted((REPO_ROOT / "generator" / "stacks").glob("*.toml"))}
        self.assertEqual(len(tomls), 5, f"§S4: expected five stack TOMLs, found {sorted(tomls)}")
        roles = sum(len(tomllib.loads(t).get("roles", {})) for t in tomls.values())
        self.assertEqual(roles, 20, "§S4: expected 4 roles x 5 stacks carrying a tools list")
        self.assertEqual(_pi_tool_violations(tomls), [])

    def test_s4_unknown_pi_tool_in_a_template_fails(self):
        fixture = {"z.toml": '[roles.red]\ntools = ["read", "Bash", "ctx_read"]\n'}
        self.assertEqual(_pi_tool_violations(fixture), ["z.toml [roles.red]: 'Bash' is not a PI_TOOL_NAMES key"])


if __name__ == "__main__":
    unittest.main()
