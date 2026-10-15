"""The ``RELEASE_TARGETS`` registry key and its ``release_targets_csv`` validate rule
(CR-MDB-068 §S1).

Contract: ``docs/changes/CR-MDB-068-release-and-ci-workflow-templates.md`` §S1; rulings in
``docs/research/release-automation-crucible-procedure.md`` § "Release workflow templates (user
rulings, 2026-10-14, at CR-MDB-068's gap analysis)".

Class map:

- ``ReleaseTargetsSchemaEntryTest`` — the schema entry: right after ``PROJECT_STACKS``, its fields
  exactly as §S1 lists them, and the packaged schema still loads with it.
- ``ReleaseTargetsCsvAcceptedFormsTest`` — ``scaffold.VALIDATE_RULES["release_targets_csv"]``
  returns the canonical form of every accepted value: the order ``pypi``, ``npm``,
  ``github-assets``; a ``dir`` normalised as a ``PurePosixPath`` (``./pkg/`` -> ``pkg``, ``.``
  omitted); no whitespace; empty for no target.
- ``ReleaseTargetsCsvRefusalsTest`` — each refusal: an unknown name (listing the supported ones), a
  duplicate name, an empty or blank ``dir``, an absolute ``dir`` or one holding ``..``, a ``dir`` on
  ``github-assets``.
- ``ReleaseTargetsCsvUnsafeDirTest`` — CR-MDB-068 C5 RED (VERIFY F1): a ``dir`` holding any
  character outside ``[A-Za-z0-9._/-]`` (a space, ``;``, ``$``, ``(``, a quote, a backtick, a tab, a
  non-ASCII letter) is refused, naming the target and the ``dir`` as its ``repr``; the safe characters
  are still accepted. The renderer refuses the same dirs (``tests.test_workflow_render``).
- ``ReleaseTargetsThroughTheRegistryTest`` — the rule wired through ``scaffold.resolve_registry``
  over the packaged schema: the canonical value recorded, a refusal naming the key and its flag.
- ``InitWithoutReleaseTargetsTest`` — a sandboxed ``modelb-axi --yes init`` with no
  ``--release-targets`` records ``RELEASE_TARGETS=`` (empty) in the root ``.env``, after
  ``PROJECT_STACKS``, and never in a monorepo sub-project's ``.env``.
- ``ReleaseTargetsSurfacesTest`` — CR-MDB-071 §S1: the ``--release-targets`` help of ``init`` and
  ``release-workflow`` and the schema entry's description name all five targets.

CR-MDB-071 §S1 adds ``crates`` and ``maven-central`` (each taking an optional ``dir``) between ``npm``
and ``github-assets``; the unknown names the refusals use are ``cargo`` and ``maven``.

Stdlib only.
"""

import argparse
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from modelb_axi import cli, scaffold
from tests.test_project_registry_schema import (
    SCHEMA_PATH,
    _entries_by_name,
    _init,
    _key_lines,
)

KEY = "RELEASE_TARGETS"
RULE = "release_targets_csv"
#: §S1 — the supported target names, in canonical order.
# MIGRATED at CR-MDB-071 (§S1): crates and maven-central join, between npm and github-assets
# (was: ("pypi", "npm", "github-assets")).
SUPPORTED = ("pypi", "npm", "crates", "maven-central", "github-assets")
#: CR-MDB-071 §S1 — names no target answers to (an unknown name must still be refused).
UNKNOWN_NAMES = ("cargo", "maven")

#: (value given, canonical form returned) — §S1's accepted forms.
ACCEPTED = (
    ("", ""),
    ("pypi", "pypi"),
    ("npm", "npm"),
    ("github-assets", "github-assets"),
    ("pypi:.", "pypi"),
    ("npm:.", "npm"),
    ("npm:./", "npm"),
    ("npm:pkg", "npm:pkg"),
    ("npm:./pkg/", "npm:pkg"),
    ("npm:pkg//sub/", "npm:pkg/sub"),
    ("pypi:py/./src", "pypi:py/src"),
    ("github-assets,npm:pkg,pypi", "pypi,npm:pkg,github-assets"),
    ("npm:pi-package,pypi", "pypi,npm:pi-package"),
    ("github-assets,pypi", "pypi,github-assets"),
    (" pypi , npm:pkg ", "pypi,npm:pkg"),
    # CR-MDB-071 §S1: crates and maven-central, each with an optional dir, in canonical order.
    ("crates", "crates"),
    ("maven-central", "maven-central"),
    ("crates:.", "crates"),
    ("maven-central:./", "maven-central"),
    ("crates:./crates/core/", "crates:crates/core"),
    ("maven-central:lib//api/", "maven-central:lib/api"),
    ("github-assets,maven-central:b,crates:a", "crates:a,maven-central:b,github-assets"),
    ("maven-central,crates,npm:pkg,github-assets,pypi",
     "pypi,npm:pkg,crates,maven-central,github-assets"),
    (" maven-central:java , crates:rs ", "crates:rs,maven-central:java"),
)

#: (value, what the refusal names) — §S1's refusals.
# MIGRATED at CR-MDB-071 (§S1): the unknown names are cargo and maven (was: crates and
# maven-central, now targets); crates and maven-central refused under every existing rule.
REFUSED = (
    ("cargo", "cargo"),
    ("pypi,maven", "maven"),
    ("Crates", "Crates"),
    ("crates,crates:core", "crates"),
    ("maven-central:a,maven-central:b", "maven-central"),
    ("crates:", "crates"),
    ("maven-central: ", "maven-central"),
    ("crates:/abs/rs", "/abs/rs"),
    ("maven-central:../java", "../java"),
    ("crates:rs/../other", "rs/../other"),
    ("PyPI", "PyPI"),
    ("pypi,pypi", "pypi"),
    ("pypi,pypi:sub", "pypi"),
    ("npm:a,npm:b", "npm"),
    ("npm:", "npm"),
    ("pypi: ", "pypi"),
    ("npm:/abs/pkg", "/abs/pkg"),
    ("pypi:/", "/"),
    ("npm:../pkg", "../pkg"),
    ("npm:pkg/../other", "pkg/../other"),
    ("github-assets:dist", "github-assets"),
)


#: CR-MDB-068 C5 RED (VERIFY F1) — ``(value, its dir)``: each ``dir`` holds one character outside
#: ``[A-Za-z0-9._/-]``, which the rendered workflow would write unquoted into a shell line.
UNSAFE_DIRS = (
    ("npm:a b", "a b"),
    ("pypi:a;b", "a;b"),
    ("npm:a$b", "a$b"),
    ("npm:a(b", "a(b"),
    ("pypi:a'b", "a'b"),
    ('npm:a"b', 'a"b'),
    ("npm:a`b", "a`b"),
    ("npm:a\tb", "a\tb"),
    ("pypi:pkg/sub dir", "pkg/sub dir"),
    # CR-MDB-071 §S1: the new targets' dirs are written into shell lines too.
    ("crates:a b", "a b"),
    ("crates:rs;x", "rs;x"),
    ("maven-central:a$b", "a$b"),
    ("maven-central:java`x", "java`x"),
    ("npm:pkgé", "pkgé"),
)
#: CR-MDB-068 C5 RED (VERIFY F1) — dirs using only ``[A-Za-z0-9._/-]``, with their canonical form.
SAFE_DIRS = (
    ("npm:pkg-1/sub_dir.v2", "npm:pkg-1/sub_dir.v2"),
    ("pypi:A.b/C_d-9", "pypi:A.b/C_d-9"),
    ("crates:crates/core-1.x", "crates:crates/core-1.x"),
    ("maven-central:java/lib_2", "maven-central:java/lib_2"),
)

def _rule():
    """The §S1 rule, looked up as ``load_schema`` looks it up: ``scaffold.VALIDATE_RULES``."""
    return scaffold.VALIDATE_RULES[RULE]


class ReleaseTargetsSchemaEntryTest(unittest.TestCase):
    """§S1 — the schema entry, its position after ``PROJECT_STACKS``, and its fields."""

    def test_the_entry_follows_project_stacks(self):
        names = [entry["name"] for entry in scaffold.load_schema(SCHEMA_PATH)]
        self.assertIn(KEY, names, f"§S1: the schema declares {KEY}; got {names}")
        self.assertEqual(names.index(KEY), names.index("PROJECT_STACKS") + 1,
                         f"§S1: {KEY} comes right after PROJECT_STACKS; got {names}")
        self.assertEqual(names.count(KEY), 1)

    def test_the_entry_carries_exactly_the_fields_s1_lists(self):
        entry = _entries_by_name().get(KEY, {})
        fields = {key: entry.get(key) for key in
                  ("required", "file", "scope", "source", "flag", "validate")}
        self.assertEqual(fields, {"required": False, "file": ".env", "scope": "root",
                                  "source": "ask", "flag": "--release-targets",
                                  "validate": RULE}, f"§S1: got {entry!r}")
        self.assertEqual(sorted(set(entry) - {"name", "description", "readers", *fields}), [],
                         "§S1: an ask key carries no rule, inputs, step, override or when")
        self.assertTrue(str(entry.get("description", "")).strip(), "§S1: a description")

    # MIGRATED at CR-MDB-071 (§S5): the readers gain `modelb-axi release-check` (was two).
    def test_the_readers_are_init_the_release_workflow_verb_and_release_check(self):
        readers = _entries_by_name().get(KEY, {}).get("readers", [])
        self.assertEqual(len(readers), 3, f"CR-MDB-071 §S1/§S5: three readers; got {readers!r}")
        self.assertTrue(readers[0].startswith("modelb-axi init"), readers)
        self.assertTrue(readers[1].startswith("modelb-axi release-workflow"), readers)
        self.assertTrue(readers[2].startswith("modelb-axi release-check"), readers)


class ReleaseTargetsCsvAcceptedFormsTest(unittest.TestCase):
    """§S1 — every accepted form returns its canonical form."""

    def test_each_accepted_form_returns_its_canonical_form(self):
        rule = _rule()
        for value, canonical in ACCEPTED:
            with self.subTest(value=value):
                self.assertEqual(rule(value), canonical)

    def test_a_canonical_value_is_its_own_canonical_form(self):
        rule = _rule()
        for _value, canonical in ACCEPTED:
            with self.subTest(canonical=canonical):
                self.assertEqual(rule(canonical), canonical, "§S1: the rule is idempotent")

    def test_no_canonical_form_carries_whitespace_or_a_dot_dir(self):
        rule = _rule()
        for value, _canonical in ACCEPTED:
            with self.subTest(value=value):
                out = rule(value)
                self.assertFalse(any(ch.isspace() for ch in out), out)
                self.assertNotIn(":.", out, "§S1: a `.` dir is omitted")
                self.assertFalse(out.endswith("/") or "/," in out, "§S1: no trailing slash")


class ReleaseTargetsCsvRefusalsTest(unittest.TestCase):
    """§S1 — each refusal raises (``ValueError``, ``ScaffoldError`` being one) naming the bad part."""

    def _refusal(self, value: str) -> str:
        with self.assertRaises(ValueError) as caught:
            _rule()(value)
        return str(caught.exception)

    def test_each_refused_value_raises_naming_the_offending_part(self):
        for value, named in REFUSED:
            with self.subTest(value=value):
                self.assertIn(named, self._refusal(value))

    # MIGRATED at CR-MDB-071 (§S1): the unknown names are cargo and maven (was: crates and
    # pypi,maven-central), and the refusal lists all five targets.
    def test_an_unknown_name_lists_the_supported_ones(self):
        for value in (*UNKNOWN_NAMES, "pypi,maven"):
            with self.subTest(value=value):
                message = self._refusal(value)
                for name in SUPPORTED:
                    self.assertIn(name, message, f"§S1: the refusal lists {name}")

    def test_a_duplicate_name_says_duplicate(self):
        for value in ("pypi,pypi", "npm:a,npm:b", "crates,crates:core",
                      "maven-central:a,maven-central:b"):
            with self.subTest(value=value):
                self.assertIn("duplicate", self._refusal(value).lower())

    def test_crates_and_maven_central_dir_refusals_name_the_target(self):
        # CR-MDB-071 §S1: each existing dir rule applies to the new targets, the target named.
        for value, named in (("crates:", "crates"), ("maven-central: ", "maven-central"),
                             ("crates:/abs/rs", "/abs/rs"), ("maven-central:../java", "../java")):
            with self.subTest(value=value):
                message = self._refusal(value)
                self.assertIn(named, message)
                self.assertIn(value.partition(":")[0], message)
                self.assertNotIn("unknown", message, "§S1: a known target, refused for its dir")


class ReleaseTargetsCsvUnsafeDirTest(unittest.TestCase):
    """CR-MDB-068 C5 RED (VERIFY F1) — a ``dir`` is refused when it holds any character outside
    ``[A-Za-z0-9._/-]``; the refusal names the target and the ``dir`` (as its ``repr``)."""

    def test_a_dir_holding_a_character_outside_the_safe_set_is_refused_naming_it(self):
        for value, directory in UNSAFE_DIRS:
            name = value.partition(":")[0]
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as caught:
                    _rule()(value)
                message = str(caught.exception)
                self.assertIn(repr(directory), message, "F1: the refusal names the bad dir")
                self.assertIn(name, message, "F1: the refusal names the target")

    def test_an_unsafe_dir_beside_a_valid_target_is_still_refused(self):
        with self.assertRaises(ValueError) as caught:
            _rule()("pypi,npm:a b")
        self.assertIn(repr("a b"), str(caught.exception))

    def test_a_dir_of_safe_characters_is_accepted_in_canonical_form(self):
        for value, canonical in SAFE_DIRS:
            with self.subTest(value=value):
                self.assertEqual(_rule()(value), canonical)

    def test_an_unsafe_dir_through_the_registry_names_the_key_and_its_flag(self):
        with self.assertRaises(scaffold.ScaffoldError) as caught:
            scaffold.resolve_registry(scaffold.load_schema(SCHEMA_PATH),
                                      {**ReleaseTargetsThroughTheRegistryTest.INPUTS,
                                       "release_targets": "npm:a;b"})
        message = str(caught.exception)
        self.assertIn(f"{KEY} (--release-targets)", message)
        self.assertIn(repr("a;b"), message)

class ReleaseTargetsThroughTheRegistryTest(unittest.TestCase):
    """§S1 — the packaged schema's entry validates through ``resolve_registry``."""

    INPUTS = {"name": "My Project", "token": "myproj", "acronym": "MYP", "owner": "tester",
              "stacks": "python", "mode": "solo", "repo_shape": "standalone"}

    def _resolve(self, **extra) -> dict:
        return scaffold.resolve_registry(scaffold.load_schema(SCHEMA_PATH),
                                         {**self.INPUTS, **extra})

    def test_the_flag_value_is_recorded_in_canonical_form(self):
        self.assertEqual(self._resolve(release_targets="npm:./pkg/,pypi").get(KEY), "pypi,npm:pkg")

    def test_no_flag_records_the_key_empty(self):
        registry = self._resolve()
        self.assertIn(KEY, registry, f"§S1: {KEY} is resolved; got {sorted(registry)}")
        self.assertEqual(registry[KEY], "")

    # MIGRATED at CR-MDB-071 (§S1): the refused value is the unknown name cargo (was: crates).
    def test_a_refused_value_names_the_key_and_its_flag(self):
        with self.assertRaises(scaffold.ScaffoldError) as caught:
            self._resolve(release_targets="cargo")
        self.assertIn(f"{KEY} (--release-targets)", str(caught.exception))
        self.assertIn("cargo", str(caught.exception))

    def test_crates_and_maven_central_are_recorded_in_canonical_form(self):
        # CR-MDB-071 §S1: the new targets pass the registry, ordered between npm and github-assets.
        self.assertEqual(self._resolve(
            release_targets="github-assets,maven-central:./java/,crates,pypi").get(KEY),
            "pypi,crates,maven-central:java,github-assets")


#: CR-MDB-071 §S1 — the surfaces naming the supported targets: each names all five.
TARGET_SURFACE_COMMANDS = ("init", "release-workflow")


class ReleaseTargetsSurfacesTest(unittest.TestCase):
    """CR-MDB-071 §S1 — the ``--release-targets`` help of ``init`` and ``release-workflow`` and the
    schema entry's description name every supported target."""

    def _help(self, command: str) -> str:
        parser = cli._build_parser()
        sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
        action = next(a for a in sub.choices[command]._actions
                      if "--release-targets" in a.option_strings)
        return " ".join((action.help or "").split())

    def test_each_release_targets_help_names_all_five_targets(self):
        for command in TARGET_SURFACE_COMMANDS:
            help_text = self._help(command)
            for name in SUPPORTED:
                with self.subTest(command=command, target=name):
                    self.assertRegex(help_text, rf"(?<![\w-]){re.escape(name)}(?![\w-])",
                                     f"§S1: `{command} --release-targets` names {name}")

    def test_the_schema_description_names_all_five_targets_as_code(self):
        description = str(_entries_by_name().get(KEY, {}).get("description", ""))
        for name in SUPPORTED:
            with self.subTest(target=name):
                self.assertIn(f"`{name}`", description, f"§S1: the description names {name}")

    def test_the_surfaces_name_no_unknown_target(self):
        texts = [self._help(command) for command in TARGET_SURFACE_COMMANDS]
        texts.append(str(_entries_by_name().get(KEY, {}).get("description", "")))
        for text in texts:
            for name in UNKNOWN_NAMES:
                with self.subTest(text=text[:60], name=name):
                    self.assertNotRegex(text, rf"(?<![\w-]){name}(?![\w-])")


class InitWithoutReleaseTargetsTest(unittest.TestCase):
    """§S1 AC — ``init`` without ``--release-targets`` records an empty value."""

    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="r68-targets-"))
        cls.target = cls.root / "proj"
        cls.result = _init(cls.root, cls.target, shape="monorepo:a")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def _env(self, rel: str) -> str:
        path = self.target / rel
        self.assertTrue(path.is_file(), f"init exit={self.result.returncode} "
                                        f"stderr={self.result.stderr[-800:]!r}")
        return path.read_text(encoding="utf-8")

    def test_the_root_env_records_release_targets_empty_after_project_stacks(self):
        text = self._env(".env")
        self.assertEqual(_key_lines(text, KEY), [f"{KEY}=\n"], text)
        lines = text.splitlines()
        stacks = next(i for i, line in enumerate(lines) if line.startswith("PROJECT_STACKS="))
        self.assertEqual(lines[stacks + 1], f"{KEY}=", "§S1: rendered after PROJECT_STACKS")

    def test_a_sub_project_env_carries_no_release_targets(self):
        text = self._env("a/.env")
        self.assertIn("PROJECT_TOKEN=", text, "precondition: the sub-project registry")
        self.assertEqual(_key_lines(text, KEY), [], "§S1: scope root — never a sub-project's")
        self.assertEqual(_key_lines(self._env(".env"), KEY), [f"{KEY}=\n"])


if __name__ == "__main__":
    unittest.main()
