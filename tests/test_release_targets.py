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
- ``ReleaseTargetsThroughTheRegistryTest`` — the rule wired through ``scaffold.resolve_registry``
  over the packaged schema: the canonical value recorded, a refusal naming the key and its flag.
- ``InitWithoutReleaseTargetsTest`` — a sandboxed ``modelb-axi --yes init`` with no
  ``--release-targets`` records ``RELEASE_TARGETS=`` (empty) in the root ``.env``, after
  ``PROJECT_STACKS``, and never in a monorepo sub-project's ``.env``.

Stdlib only.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from modelb_axi import scaffold
from tests.test_project_registry_schema import (
    SCHEMA_PATH,
    _entries_by_name,
    _init,
    _key_lines,
)

KEY = "RELEASE_TARGETS"
RULE = "release_targets_csv"
#: §S1 — the supported target names, in canonical order.
SUPPORTED = ("pypi", "npm", "github-assets")

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
)

#: (value, what the refusal names) — §S1's refusals.
REFUSED = (
    ("crates", "crates"),
    ("pypi,maven-central", "maven-central"),
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

    def test_the_readers_are_init_and_the_release_workflow_verb(self):
        readers = _entries_by_name().get(KEY, {}).get("readers", [])
        self.assertEqual(len(readers), 2, f"§S1: two readers; got {readers!r}")
        self.assertTrue(readers[0].startswith("modelb-axi init"), readers)
        self.assertTrue(readers[1].startswith("modelb-axi release-workflow"), readers)


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

    def test_an_unknown_name_lists_the_supported_ones(self):
        for value in ("crates", "pypi,maven-central"):
            with self.subTest(value=value):
                message = self._refusal(value)
                for name in SUPPORTED:
                    self.assertIn(name, message, f"§S1: the refusal lists {name}")

    def test_a_duplicate_name_says_duplicate(self):
        for value in ("pypi,pypi", "npm:a,npm:b"):
            with self.subTest(value=value):
                self.assertIn("duplicate", self._refusal(value).lower())


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

    def test_a_refused_value_names_the_key_and_its_flag(self):
        with self.assertRaises(scaffold.ScaffoldError) as caught:
            self._resolve(release_targets="crates")
        self.assertIn(f"{KEY} (--release-targets)", str(caught.exception))


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
