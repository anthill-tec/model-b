"""``modelb-axi init`` writes the project's Sandesh identity and its direnv
entry point (CR-MDB-047 §S2; DN-multi-harness §D20 with its Sandesh 0.4.0
amendment, PRD D10, PRD D3.1).

- The schema key ``SANDESH_ADDRESS``: in ``.env``, scope ``root+sub``,
  ``source = "derive"``, derived as ``Mainline - <SANDESH_PROJECT>`` (a
  monorepo sub-project from its own ``SANDESH_PROJECT``), validated as
  non-empty; its readers are bootstrap, shutdown and Sandesh's Pi extension.
  The AC's literal form is the line ``SANDESH_ADDRESS="Mainline - <P>"`` in
  every ``.env`` ``init`` writes.
- ``.envrc``: ``init`` writes exactly ``dotenv\\n`` beside every ``.env`` it
  writes — root and each sub-project — committed, not gitignored, listed by
  ``--dry-run``. A pre-existing ``.envrc`` with other content is left alone
  and reported under ``init``'s ownership rules.
- The Sandesh setup task — in the root ``AGENTS.md``'s ``## Setup`` section since
  CR-MDB-048 §S2 (the queue README's until then) — names installing direnv and its hook,
  ``direnv allow`` in each directory with an ``.envrc``, and the Track launch
  line ``env SANDESH_ADDRESS="Track <N> - <Project>" pi``.
- The scaffolded ``AGENTS.md`` identity section names ``SANDESH_ADDRESS``
  beside ``SANDESH_PROJECT``.
- Quoting (amended at 5dd8a36 for VERIFY F1): every whitespace-containing
  value ``init`` writes to a ``.env`` is double-quoted, whatever its source,
  so a scaffolded ``.env`` (standalone and monorepo, with a project name
  containing a space) parses under :func:`_direnv_dotenv` — a pure-Python
  reading of direnv's dotenv grammar (never the real ``direnv`` binary) —
  with every key; the scaffold's own registry reader returns the value
  unquoted.

Isolation (NON-NEGOTIABLE): the sandbox of ``tests.test_init_tool_verdicts``
— every ``install.toml``, Pi agent dir and home a fixture under a per-test
temp dir; ``run_init`` runs in process with ``HOME`` and
``PI_CODING_AGENT_DIR`` pinned there. No test reads the real
``~/.local/share/modelb``, ``~/.pi`` or ``sandesh``.

Stdlib only.
"""

import re
import subprocess
import unittest
from pathlib import Path

from modelb_axi import scaffold
from tests import test_init_tool_verdicts as _verdicts
from tests._helpers import md_section, parse_env_file

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "modelb_axi" / "project_schema.toml"

#: ``SANDESH_PROJECT`` as ``init`` derives it from the sandbox's project name.
DERIVED = _verdicts.DERIVED_CHANNEL
ENVRC = b"dotenv\n"
SUBS = ("a", "b")
MONOREPO = "monorepo:" + ",".join(SUBS)

#: The Track launch line of the setup task; ``<Project>`` may be written as
#: the placeholder or as the project's ``SANDESH_PROJECT``.
TRACK_LAUNCH_RE = re.compile(
    r'env SANDESH_ADDRESS="Track <N> - (?:<Project>|' + re.escape(DERIVED) + r')" pi')


def _address_lines(env_text: str) -> list[str]:
    return [ln for ln in env_text.splitlines() if ln.startswith("SANDESH_ADDRESS=")]


#: One line of direnv's dotenv grammar (direnv ``pkg/dotenv``, measured
#: against direnv 2.37): an optional ``export``, a key, ``=`` (or ``: ``), and
#: an optional value that is single-quoted, double-quoted (a backslash escapes a
#: quote) or unquoted with NO whitespace, then an optional comment. A blank
#: line or a comment line is skipped; any other line is invalid, and direnv
#: then exports nothing from the file.
_DOTENV_LINE_RE = re.compile(
    r"""\A\s*(?:export\s+)?([\w.]+)(?:\s*=\s*|:\s+?)"""
    r"""('(?:\\'|[^'])*'|"(?:\\"|[^"])*"|[^\s#]+)?\s*(?:\#.*)?\Z"""
)
_DOTENV_VAR_RE = re.compile(r"(\\)?\$(\{?([A-Za-z0-9_]+)\}?)")


def _direnv_dotenv(text: str) -> dict:
    """``text`` read the way direnv's ``dotenv`` reads it: ``{KEY: value}``,
    or ``ValueError`` naming the first invalid line. Double-quoted values
    unescape ``\\n`` and ``\\<char>`` and expand ``$VAR``/``${VAR}``;
    single-quoted ones are literal; unquoted ones expand."""
    values: dict = {}

    def expand(value: str) -> str:
        def one(match: re.Match) -> str:
            if match.group(1):
                return match.group(0)[1:]
            return values.get(match.group(3) or "", "")
        return _DOTENV_VAR_RE.sub(one, value)

    for line in text.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        match = _DOTENV_LINE_RE.match(line)
        if match is None:
            raise ValueError(f"invalid line: {line}")
        key, raw = match.group(1), match.group(2) or ""
        if len(raw) >= 2 and raw[0] == raw[-1] == "'":
            values[key] = raw[1:-1]
            continue
        if len(raw) >= 2 and raw[0] == raw[-1] == '"':
            raw = raw[1:-1].replace("\\n", "\n").replace("\\r", "\r")
            raw = re.sub(r"\\([^$])", r"\1", raw)
        values[key] = expand(raw)
    return values


def _git(target: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(target), *args], capture_output=True, text=True,
                          timeout=30)


class _Case(_verdicts._InitSandboxCase):
    """The CR-MDB-045 init sandbox with every tool recorded present."""

    def setUp(self):
        super().setUp()
        self.write_install(_verdicts._complete_verdicts("detected"))
        self.target = self.root / "proj"

    def init_ok(self, **fields) -> tuple[dict, str]:
        rc, axi, err = self.run_init(self.target, **fields)
        self.assertEqual((rc, axi.get("ok")), (0, True), f"init must succeed; stderr={err!r}")
        return axi, err

    def read(self, rel: str) -> str:
        path = self.target / rel
        self.assertTrue(path.is_file(), f"{rel} was not emitted")
        return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# The schema key
# ---------------------------------------------------------------------------

class SandeshAddressSchemaEntryTest(unittest.TestCase):
    """§S2: ``SANDESH_ADDRESS`` is declared once, with the §S2 rules."""

    def entry(self) -> dict:
        entries = [e for e in scaffold.load_schema(SCHEMA_PATH) if e["name"] == "SANDESH_ADDRESS"]
        self.assertEqual(len(entries), 1, "§S2: exactly one SANDESH_ADDRESS key")
        return entries[0]

    def test_sandesh_address_is_a_derived_root_plus_sub_env_key_validated_non_empty(self):
        entry = self.entry()
        self.assertEqual(
            (entry["file"], entry["scope"], entry["source"], entry["validate"]),
            (".env", "root+sub", "derive", "non_empty"),
            entry,
        )
        self.assertIn("SANDESH_PROJECT", entry["inputs"],
                      "§S2: derived from the project's own SANDESH_PROJECT")

    def test_sandesh_address_readers_are_bootstrap_shutdown_and_sandeshs_pi_extension(self):
        readers = self.entry()["readers"]
        for word, pattern in (("bootstrap", r"(?i)\bbootstrap"), ("shutdown", r"(?i)\bshutdown"),
                              ("Sandesh's Pi extension",
                               r"(?i)sandesh(?:'s)?[ -]pi\b.*extension|sandesh-pi")):
            with self.subTest(reader=word):
                self.assertTrue(any(re.search(pattern, r) for r in readers),
                                f"§S2: a reader names {word}; readers={readers!r}")

    def test_the_derive_rule_gives_the_mainline_address_of_the_sandesh_project(self):
        schema = scaffold.load_schema(SCHEMA_PATH)
        inputs = {"name": "My Project", "token": "myproj", "acronym": "MYP",
                  "owner": "tester", "stacks": "python", "mode": "solo",
                  "sandesh_project": None, "knowledge_category": None}
        registry = scaffold.resolve_registry(schema, inputs)
        self.assertIn("SANDESH_ADDRESS", registry, "\u00a7S2: init derives SANDESH_ADDRESS")
        self.assertEqual(registry["SANDESH_ADDRESS"], "Mainline - MyProject")
        inputs["sandesh_project"] = "Foo_Bar"
        self.assertEqual(scaffold.resolve_registry(schema, inputs)["SANDESH_ADDRESS"],
                         "Mainline - Foo_Bar",
                         "the address follows SANDESH_PROJECT's override")


# ---------------------------------------------------------------------------
# SANDESH_ADDRESS in every .env
# ---------------------------------------------------------------------------

class InitWritesSandeshAddressTest(_Case):
    """AC: ``SANDESH_ADDRESS="Mainline - <SANDESH_PROJECT>"`` in every ``.env``
    ``init`` writes, each from its own ``SANDESH_PROJECT``."""

    def test_the_root_env_carries_the_mainline_address_once(self):
        axi, _err = self.init_ok()
        self.assertEqual(_address_lines(self.read(".env")),
                         [f'SANDESH_ADDRESS="Mainline - {DERIVED}"'])
        self.assertEqual((axi.get("registry") or {}).get("SANDESH_ADDRESS"),
                         f"Mainline - {DERIVED}", "the envelope's registry reports the value")

    def test_the_address_follows_the_sandesh_project_override(self):
        self.init_ok(sandesh_project="Foo_Bar")
        self.assertEqual(_address_lines(self.read(".env")),
                         ['SANDESH_ADDRESS="Mainline - Foo_Bar"'])

    def test_every_sub_project_env_carries_the_address_of_its_own_sandesh_project(self):
        self.init_ok(repo_shape=MONOREPO)
        for rel in (".env", *(f"{sub}/.env" for sub in SUBS)):
            with self.subTest(env=rel):
                project = parse_env_file(self.target / rel).get("SANDESH_PROJECT")
                self.assertTrue(project, f"{rel} carries SANDESH_PROJECT")
                self.assertEqual(_address_lines(self.read(rel)),
                                 [f'SANDESH_ADDRESS="Mainline - {project}"'])

    def test_a_multi_project_env_carries_the_mainline_address_too(self):
        self.init_ok(mode="multi:2")
        self.assertEqual(parse_env_file(self.target / ".env").get("SANDESH_ADDRESS"),
                         f"Mainline - {DERIVED}")

    def test_the_address_never_lands_in_the_gitignored_overlay(self):
        self.init_ok()
        self.assertNotIn("SANDESH_ADDRESS", parse_env_file(self.target / ".env.local"))


# ---------------------------------------------------------------------------
# .envrc beside every .env
# ---------------------------------------------------------------------------

class InitWritesEnvrcTest(_Case):
    """AC: ``.envrc`` containing exactly ``dotenv\\n`` beside each ``.env``,
    committed and not gitignored, listed by ``--dry-run``."""

    def test_a_standalone_project_gets_a_root_envrc_of_exactly_dotenv(self):
        axi, _err = self.init_ok()
        self.assertTrue((self.target / ".envrc").is_file(), ".envrc was not written")
        self.assertEqual((self.target / ".envrc").read_bytes(), ENVRC)
        self.assertIn(".envrc", axi.get("emitted", []))

    def test_every_sub_project_gets_its_own_envrc(self):
        axi, _err = self.init_ok(repo_shape=MONOREPO)
        for rel in (".envrc", *(f"{sub}/.envrc" for sub in SUBS)):
            with self.subTest(envrc=rel):
                path = self.target / rel
                self.assertTrue(path.is_file(), f"{rel} was not written")
                self.assertEqual(path.read_bytes(), ENVRC)
                self.assertIn(rel, axi.get("emitted", []))
        envrcs = sorted(str(p.relative_to(self.target)) for p in self.target.rglob(".envrc"))
        self.assertEqual(envrcs, sorted([".envrc", *(f"{s}/.envrc" for s in SUBS)]),
                         "one .envrc per .env, and no other")

    def test_the_envrcs_are_committed_and_not_gitignored(self):
        self.init_ok(repo_shape=MONOREPO, no_commit=False)
        tracked = _git(self.target, "ls-files").stdout.splitlines()
        for rel in (".envrc", *(f"{sub}/.envrc" for sub in SUBS)):
            with self.subTest(envrc=rel):
                self.assertIn(rel, tracked, "the scaffold commit carries it")
                ignored = _git(self.target, "check-ignore", "-q", rel)
                self.assertEqual(ignored.returncode, 1, f"{rel} must not be gitignored")

    def test_dry_run_lists_every_envrc_and_writes_nothing(self):
        axi, _err = self.init_ok(repo_shape=MONOREPO, dry_run=True)
        planned = axi.get("planned", [])
        for rel in (".envrc", *(f"{sub}/.envrc" for sub in SUBS)):
            with self.subTest(envrc=rel):
                self.assertIn(rel, planned)
        self.assertFalse(self.target.exists(), "--dry-run writes nothing")


class PreExistingEnvrcTest(_Case):
    """AC: a pre-existing ``.envrc`` with other content is left alone and
    reported, under the ownership rules ``init`` already applies."""

    OTHER = b"export FOO=bar\nuse nix\n"

    def test_an_envrc_with_other_content_is_left_alone_and_reported(self):
        self.target.mkdir()
        (self.target / ".envrc").write_bytes(self.OTHER)
        axi, _err = self.init_ok()
        self.assertEqual((self.target / ".envrc").read_bytes(), self.OTHER,
                         "the user's .envrc is left alone")
        self.assertNotIn(".envrc", axi.get("emitted", []))
        owned = list(axi.get("skipped", [])) + list(axi.get("unmanaged", []))
        self.assertIn(".envrc", owned, f"reported under the ownership rules; axi={axi!r}")
        self.assertTrue([w for w in axi.get("warnings", []) if ".envrc" in w],
                        f"a warning names the .envrc; {axi.get('warnings')!r}")
        self.assertEqual(_address_lines(self.read(".env")),
                         [f'SANDESH_ADDRESS="Mainline - {DERIVED}"'],
                         "the rest of the scaffold is still written")

    def test_a_sub_project_envrc_with_other_content_is_left_alone_and_reported(self):
        (self.target / "a").mkdir(parents=True)
        (self.target / "a" / ".envrc").write_bytes(self.OTHER)
        axi, _err = self.init_ok(repo_shape=MONOREPO)
        self.assertEqual((self.target / "a" / ".envrc").read_bytes(), self.OTHER)
        for rel in ("b/.envrc", ".envrc"):
            self.assertTrue((self.target / rel).is_file(),
                            f"{rel} is still written beside its .env")
        self.assertEqual((self.target / "b" / ".envrc").read_bytes(), ENVRC,
                         "the other sub-project still gets its .envrc")
        self.assertEqual((self.target / ".envrc").read_bytes(), ENVRC)
        owned = list(axi.get("skipped", [])) + list(axi.get("unmanaged", []))
        self.assertIn("a/.envrc", owned, f"axi={axi!r}")

    def test_an_envrc_already_reading_dotenv_draws_no_report(self):
        self.target.mkdir()
        (self.target / ".envrc").write_bytes(ENVRC)
        axi, _err = self.init_ok()
        self.assertEqual((self.target / ".envrc").read_bytes(), ENVRC)
        owned = list(axi.get("skipped", [])) + list(axi.get("unmanaged", []))
        self.assertNotIn(".envrc", owned)
        self.assertEqual([w for w in axi.get("warnings", []) if ".envrc" in w], [])


# ---------------------------------------------------------------------------
# The Sandesh setup task, in the root AGENTS.md's Setup section
# ---------------------------------------------------------------------------

class AgentsMdSandeshSetupTaskTest(_Case):
    """AC: the setup task names direnv, its hook, ``direnv allow`` and the
    Track launch line.

    MIGRATED at CR-MDB-048 C2 RED (§S2; was ``QueueReadmeSandeshSetupTaskTest``):
    the task moved from the queue README's Setup tasks into the root
    ``AGENTS.md``'s ``## Setup`` section; ``init`` writes no queue README."""

    def setup_tasks(self) -> str:
        self.init_ok(mode="multi:2")
        self.assertFalse((self.target / "docs/changes/README.md").exists(),
                         "CR-MDB-048 §S2: init writes no queue README")
        section = md_section(self.read("AGENTS.md"), "## Setup")
        self.assertTrue(section, "the root AGENTS.md carries a ## Setup section")
        return section

    def test_the_task_names_installing_direnv_and_its_shell_hook(self):
        section = self.setup_tasks()
        self.assertRegex(section, r"(?i)install\w*\b[^\n]*\bdirenv")
        self.assertIn("direnv hook", section, "the shell hook is named")

    def test_the_task_names_direnv_allow_in_each_envrc_directory(self):
        section = self.setup_tasks()
        self.assertIn("direnv allow", section)
        self.assertRegex(section, r"direnv allow`?[^\n]*\.envrc",
                         "`direnv allow` is named for the directories with an .envrc")

    def test_the_task_names_the_track_launch_line(self):
        section = self.setup_tasks()
        self.assertRegex(section, TRACK_LAUNCH_RE)

    def test_the_task_keeps_the_mainline_registration(self):
        section = self.setup_tasks()
        self.assertIn(f"`Mainline - {DERIVED}`", section)


# ---------------------------------------------------------------------------
# Quoting: a scaffolded .env reads under direnv's dotenv grammar
# ---------------------------------------------------------------------------

class DirenvDotenvGrammarTest(unittest.TestCase):
    """The grammar :func:`_direnv_dotenv` reads is direnv's: it bites on the
    line direnv 2.37 rejects (an unquoted value with a space) and reads the
    quoted forms."""

    def test_an_unquoted_value_with_whitespace_is_an_invalid_line(self):
        with self.assertRaises(ValueError) as ctx:
            _direnv_dotenv("A=x\nPROJECT_NAME=Mono Proj\n")
        self.assertIn("PROJECT_NAME=Mono Proj", str(ctx.exception))

    def test_quoted_values_comments_and_expansion_read_as_direnv_reads_them(self):
        text = ('# comment\n\nB="Mono Proj"\nC=x\nD="a $C \\" b"\n'
                "E='lit $C'\nexport F=bare # trailing\nG=\n")
        self.assertEqual(_direnv_dotenv(text), {
            "B": "Mono Proj", "C": "x", "D": 'a x " b', "E": "lit $C", "F": "bare", "G": "",
        })


class ScaffoldedEnvReadsUnderDirenvTest(_Case):
    """AC "Quoting": every whitespace-containing value in a scaffolded
    ``.env`` is double-quoted, whatever its source, so the file parses under
    direnv's dotenv grammar with every key — standalone and monorepo, the
    sandbox's project name (``Verdict Project``) containing a space."""

    def expected_keys(self, *, sub: bool) -> list:
        return [e["name"] for e in scaffold.load_schema(SCHEMA_PATH)
                if e["file"] == ".env" and (not sub or e["scope"] == "root+sub")]

    def assert_reads_under_direnv(self, rel: str, *, sub: bool) -> dict:
        text = self.read(rel)
        try:
            parsed = _direnv_dotenv(text)
        except ValueError as exc:
            self.fail(f"direnv rejects {rel}: {exc}; {rel}={text!r}")
        self.assertEqual(sorted(parsed), sorted(self.expected_keys(sub=sub)),
                         f"every key of {rel} is read; {rel}={text!r}")
        self.assertEqual(parsed, parse_env_file(self.target / rel),
                         f"direnv reads each value as written; {rel}={text!r}")
        return parsed

    def test_a_standalone_env_reads_under_direnv_with_every_key(self):
        self.init_ok()
        parsed = self.assert_reads_under_direnv(".env", sub=False)
        self.assertEqual(parsed["PROJECT_NAME"], _verdicts.NAME)
        self.assertEqual(parsed["SANDESH_ADDRESS"], f"Mainline - {DERIVED}")

    def test_every_monorepo_env_reads_under_direnv_with_every_key(self):
        self.init_ok(repo_shape=MONOREPO)
        self.assert_reads_under_direnv(".env", sub=False)
        for sub in SUBS:
            with self.subTest(sub=sub):
                parsed = self.assert_reads_under_direnv(f"{sub}/.env", sub=True)
                self.assertIn(_verdicts.NAME, parsed["PROJECT_NAME"])

    def test_every_whitespace_value_is_double_quoted(self):
        self.init_ok(repo_shape=MONOREPO)
        for rel in (".env", *(f"{sub}/.env" for sub in SUBS)):
            for line in self.read(rel).splitlines():
                if not line or line.startswith("#"):
                    continue
                _key, _, value = line.partition("=")
                if any(ch.isspace() for ch in value):
                    with self.subTest(env=rel, line=line):
                        self.assertTrue(len(value) >= 2 and value[0] == value[-1] == '"',
                                        f"{rel}: {line!r} is not double-quoted")
        self.assertIn(f'PROJECT_NAME="{_verdicts.NAME}"', self.read(".env").splitlines())

    def test_the_scaffolds_registry_reader_returns_a_quoted_value_unquoted(self):
        self.init_ok()
        schema = scaffold.load_schema(SCHEMA_PATH)
        self.assertEqual(scaffold.read_registry_value(self.target, schema, "PROJECT_NAME"),
                         _verdicts.NAME)
        self.assertEqual(scaffold.read_registry_value(self.target, schema, "SANDESH_ADDRESS"),
                         f"Mainline - {DERIVED}")


# ---------------------------------------------------------------------------
# The AGENTS.md identity section
# ---------------------------------------------------------------------------

class AgentsMdIdentityNamesSandeshAddressTest(_Case):
    """AC: the identity section names ``SANDESH_ADDRESS`` beside
    ``SANDESH_PROJECT``."""

    def test_the_identity_section_names_both_keys(self):
        self.init_ok()
        identity = md_section(self.read("AGENTS.md"), "## Identity & naming")
        self.assertIn("`SANDESH_PROJECT`", identity)
        self.assertIn("SANDESH_ADDRESS", identity,
                      f"§S2: the identity section names SANDESH_ADDRESS; got {identity!r}")
        self.assertIn(f"Mainline - {DERIVED}", identity)


if __name__ == "__main__":
    unittest.main()
