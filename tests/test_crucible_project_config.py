"""A Crucible client's connection and gate steps are project configuration (CR-MDB-057 §S1–§S3;
DN-multi-harness-deploy-model §D21).

Crucible 0.3.0's clients take the board from ``[client] url`` in the first ``crucible.toml`` that
exists and parses — the project's, the install's, the shipped one — and read the gate steps a
project never runs from ``[gate] skip``. Contract: ``docs/changes/CR-MDB-057-crucible-0-3-0-doc-sync.md``.

Class map:

- ``ClientSteeringVariableGateTest`` — §S1/AC: no skill, contract, ``AGENTS.md``, generator
  asset, hook, package module or test names one of the four environment variables that used to
  point a client at a board. The gate builds those names from fragments, so its own pattern
  literals never match it; the detector is proven both ways on synthetic text.
- ``ScaffoldCrucibleTomlTest`` — §S2/AC: ``init`` (standalone and monorepo, solo and multi) writes
  exactly one ``crucible.toml``, at the root, declaring ``[gate]`` ``skip = ["ci"]`` with the
  rationale comment and no ``[client]``; no sub-project gets one; ``plan_files`` and the
  envelope's ``planned`` list it, ``emitted`` names it, ``--dry-run`` writes nothing, and the
  scaffold commit carries it.
- ``ModelBCrucibleTomlTest`` — §S2/AC: Model B's own repository tracks a ``crucible.toml`` with the
  same ``[gate]`` declaration.
- ``CrucibleSkillProjectMetaTest`` — §S3: the ``crucible`` skill documents ``project-meta``: a read
  without ``--agent``; a write with ``--set``/``--unset`` and ``--agent``, as a registered
  ``ORCHESTRATOR``, an unregistered id refused 409.
- ``CrucibleSkillConnectionTest`` — §S1/AC: the ``crucible`` skill states ``[client] url``, read from
  the first ``crucible.toml`` that exists and parses — the project's, the install's, the shipped one
  (``http://localhost:3849``) — and from that file only, so a project file without ``[client]`` sends
  the client to the shipped default; its intro names no host or port, and every host or port it
  names is the shipped default's. The checkout sentence stays the single one
  ``test_s1_crucible_skill_states_the_checkout_rule_and_reason_in_one_sentence``
  (``tests/test_client_path_anchoring.py``) finds; that gate is cited, not repeated.

Isolation: every ``init`` runs in process in the sandbox of ``tests.test_init_tool_verdicts`` (via
``tests.test_project_setup_section``'s case). No test reads ``~/.crucible`` or runs a client.

Stdlib only.
"""

import re
import subprocess
import tomllib
import unittest
from pathlib import Path

from modelb_axi import scaffold
from tests import test_project_setup_section as _setup
from tests.test_board_holds_the_queue import norm_units
from tests.test_bootstrap_shutdown_registry import normalise

REPO_ROOT = Path(__file__).resolve().parent.parent
CRUCIBLE_TOML = "crucible.toml"
CRUCIBLE_SKILL = REPO_ROOT / "skills-src" / "crucible" / "SKILL.md"

# ------------------------------------------------------------------ §S1 grep gate ----

#: The four variables that pointed a pre-0.3.0 client at a board, built from fragments so this
#: module never spells one (the gate scans ``tests/``, this file included).
_STEM = "CRUCIBLE" + "_"
STEERING_VARIABLES = tuple(_STEM + suffix for suffix in ("URL", "BASE", "PORT", "HOST"))
STEERING_VARIABLE_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:" + "|".join(STEERING_VARIABLES) + r")(?![A-Za-z0-9_])")
#: §S1/AC: the surfaces the gate reads (directories walked recursively, files read whole).
STEERING_SURFACES = ("skills-src", "contracts", "AGENTS.md", "generator", "hooks-src",
                     "modelb_axi", "tests")


def steering_hits(text: str) -> list[tuple[int, str]]:
    """``(line number, line)`` for every line of ``text`` naming a steering variable."""
    return [(n, line) for n, line in enumerate(text.splitlines(), 1)
            if STEERING_VARIABLE_RE.search(line)]


def _surface_files(rel: str):
    """The readable text files of the surface ``rel`` (a file or a directory), bytecode caches
    skipped."""
    root = REPO_ROOT / rel
    paths = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())
    for path in paths:
        if "__pycache__" in path.parts:
            continue
        try:
            yield path, path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue


class ClientSteeringVariableGateTest(unittest.TestCase):
    """§S1/AC — no surface steers a Crucible client through an environment variable."""

    def test_no_surface_names_a_client_steering_variable(self):
        offenders = []
        for rel in STEERING_SURFACES:
            self.assertTrue((REPO_ROOT / rel).exists(), f"the surface {rel} exists")
            for path, text in _surface_files(rel):
                offenders += [f"{path.relative_to(REPO_ROOT).as_posix()}:{n}: {line.strip()[:160]}"
                              for n, line in steering_hits(text)]
        self.assertEqual(
            offenders, [],
            "a client reads its board from `[client] url` in crucible.toml (CR-MDB-057 §S1); no "
            "surface may point it through an environment variable:\n" + "\n".join(offenders))

    def test_the_detector_bites_on_each_variable_and_spares_the_project_key(self):
        url, base, port, host = STEERING_VARIABLES
        for line in (f"export {url}=http://127.0.0.1:9", f"set -x {base} http://h",
                     f"env.update({port}='9')", f"curl ${host}:3849/api",
                     f"os.environ['{url}']"):
            with self.subTest(line=line):
                self.assertEqual(steering_hits(f"a\n{line}\n"), [(2, line)])
        for line in ("CRUCIBLE_PROJECT_KEY=abc", f"{url}S=x", f"MY_{base}=1",
                     "[client] url = \"http://127.0.0.1:9\""):
            with self.subTest(line=line):
                self.assertEqual(steering_hits(line), [])

    def test_this_module_spells_no_steering_variable(self):
        own = Path(__file__).read_text(encoding="utf-8")
        self.assertEqual(steering_hits(own), [],
                         "the gate's own pattern literals are built from fragments")


# ------------------------------------------------------------------ §S2 scaffold ----

def gate_comment_findings(text: str) -> list[str]:
    """What the comment lines of a scaffolded ``crucible.toml`` lack of §S2's rationale:
    no-mistakes' ``ci`` step is PR-based, and a git-flow project that merges directly has no PR
    for it to watch."""
    comment = normalise(" ".join(ln.strip().lstrip("#") for ln in text.splitlines()
                                 if ln.strip().startswith("#")))
    checks = (
        ("the ci step", r"\bci\b"),
        ("PR-based", r"\bpr-based\b|\bpull[- ]request[- ]based\b"),
        ("a project that merges directly", r"\bmerg\w*\s+directly\b"),
        ("no PR to watch", r"\bno (?:pr|pull request)\b"),
    )
    return [f"the comment does not say {what}: {comment!r}"
            for what, rx in checks if not re.search(rx, comment)]


class ScaffoldCrucibleTomlTest(_setup._Case):
    """§S2/AC — ``init`` writes exactly one ``crucible.toml``, at the root, with ``[gate]``
    ``skip = ["ci"]``, the rationale comment and no ``[client]``; ``plan_files`` lists it and
    ``emitted`` matches the files on disk."""

    def test_plan_files_lists_crucible_toml_once_at_the_root(self):
        for subs in ([], [str(s) for s in _setup.SUBS]):
            with self.subTest(subs=subs):
                plan = scaffold.plan_files(subs)
                self.assertEqual(plan.count(CRUCIBLE_TOML), 1, plan)
                self.assertEqual([p for p in plan if p.endswith("/" + CRUCIBLE_TOML)], [],
                                 "no sub-project gets one")

    def test_every_shape_writes_one_root_crucible_toml_declaring_the_gate_skip(self):
        for mode, shape in _setup.SHAPES:
            with self.subTest(mode=mode, shape=shape):
                self.target = self.root / f"proj-{mode.replace(':', '')}-{shape.split(':')[0]}"
                axi, _err = self.init_ok(mode=mode, repo_shape=shape)
                found = sorted(p.relative_to(self.target).as_posix()
                               for p in self.target.rglob(CRUCIBLE_TOML))
                self.assertEqual(found, [CRUCIBLE_TOML], "exactly one, at the root")
                text = self.text(CRUCIBLE_TOML)
                data = tomllib.loads(text)
                self.assertEqual(data.get("gate", {}).get("skip"), ["ci"], text)
                self.assertNotIn("client", data,
                                 "no [client]: the project's board is the shipped default")
                self.assertEqual(gate_comment_findings(text), [], text)
                planned, emitted = axi.get("planned", []), axi.get("emitted", [])
                self.assertEqual((planned.count(CRUCIBLE_TOML), emitted.count(CRUCIBLE_TOML)),
                                 (1, 1), f"planned={planned!r} emitted={emitted!r}")
                self.assertEqual(set(emitted), self.on_disk(), "emitted is on disk")

    def test_dry_run_plans_crucible_toml_and_writes_nothing(self):
        axi, _err = self.init_ok(mode=_setup.MULTI, repo_shape=_setup.MONOREPO, dry_run=True)
        planned = axi.get("planned", [])
        self.assertEqual(planned.count(CRUCIBLE_TOML), 1, planned)
        self.assertEqual([p for p in planned if p.endswith("/" + CRUCIBLE_TOML)], [], planned)
        self.assertFalse(self.target.exists(), "--dry-run writes nothing")

    def test_the_scaffold_commit_carries_crucible_toml(self):
        self.init_ok(no_commit=False)
        tracked = subprocess.run(["git", "-C", str(self.target), "ls-files"], capture_output=True,
                                 text=True, timeout=30, check=True).stdout.splitlines()
        self.assertIn(CRUCIBLE_TOML, tracked)

    def test_the_comment_detector_both_ways(self):
        good = ("# no-mistakes' `ci` step is PR-based: a git-flow project that merges directly\n"
                "# has no PR for it to watch.\n[gate]\nskip = [\"ci\"]\n")
        self.assertEqual(gate_comment_findings(good), [])
        for cut in ("PR-based", "merges directly", "has no PR"):
            with self.subTest(cut=cut):
                self.assertTrue(gate_comment_findings(good.replace(cut, "x")))
        self.assertTrue(gate_comment_findings("[gate]\nskip = [\"ci\"]  # PR-based\n"),
                        "a rationale outside a comment line is not the comment")


class ModelBCrucibleTomlTest(unittest.TestCase):
    """§S2/AC — Model B's repository tracks ``crucible.toml`` with ``[gate]`` ``skip = ["ci"]``."""

    def test_the_repository_tracks_crucible_toml_declaring_the_gate_skip(self):
        tracked = subprocess.run(["git", "-C", str(REPO_ROOT), "ls-files", "--", CRUCIBLE_TOML],
                                 capture_output=True, text=True, timeout=30, check=True)
        self.assertEqual(tracked.stdout.splitlines(), [CRUCIBLE_TOML], "crucible.toml is tracked")
        data = tomllib.loads((REPO_ROOT / CRUCIBLE_TOML).read_text(encoding="utf-8"))
        self.assertEqual(data.get("gate", {}).get("skip"), ["ci"], data)


# ------------------------------------------------------------------ §S3 skill ----

#: §S3: what the ``crucible`` skill states of ``project-meta`` (normalised text).
PROJECT_META_STATEMENTS = (
    ("a read needs no --agent",
     r"\bread\w*\b[^.]{0,120}\b(?:no|without|needs no|takes no)\b[^.]{0,20}--agent"
     r"|\b(?:no|without)\b[^.]{0,20}--agent[^.]{0,120}\bread"),
    ("a write with --set", r"--set\b"),
    ("a write with --unset", r"--unset\b"),
    ("a write needs --agent", r"\bwrites?\b[^.]{0,160}--agent|--agent[^.]{0,160}\bwrites?\b"),
    ("as a registered ORCHESTRATOR", r"\bregistered\b[^.]{0,40}\borchestrator\b"),
    ("an unregistered id is refused 409", r"\bunregistered\b[^.]{0,80}\b409\b"
                                          r"|\b409\b[^.]{0,80}\bunregistered\b"),
)


def project_meta_findings(text: str) -> list[str]:
    """What ``text``'s units naming ``project-meta`` lack of §S3's statements."""
    meta = " ".join(u for u in norm_units(text) if "project-meta" in u)
    if not meta:
        return ["project-meta is not documented"]
    return [f"project-meta: {what} is not stated"
            for what, rx in PROJECT_META_STATEMENTS if not re.search(rx, meta)]


class CrucibleSkillProjectMetaTest(unittest.TestCase):
    """§S3 — the ``crucible`` skill documents ``project-meta``'s read and write."""

    def test_the_crucible_skill_documents_project_meta(self):
        text = CRUCIBLE_SKILL.read_text(encoding="utf-8")
        self.assertEqual(project_meta_findings(text), [])

    def test_the_project_meta_detector_both_ways(self):
        good = ("- `project-meta` reads the project's metadata map; a read takes no `--agent`. "
                "A write — `project-meta --set KEY=VALUE` / `--unset KEY` — needs `--agent`, "
                "posting as a registered ORCHESTRATOR; an unregistered id is refused 409.\n")
        self.assertEqual(project_meta_findings(good), [])
        self.assertEqual(project_meta_findings("- `status` reads the board.\n"),
                         ["project-meta is not documented"])
        for cut in ("a read takes no `--agent`. ", " / `--unset KEY`", "a registered ",
                    "; an unregistered id is refused 409"):
            with self.subTest(cut=cut):
                self.assertEqual(len(project_meta_findings(good.replace(cut, ""))), 1,
                                 good.replace(cut, ""))


# ------------------------------------------------------------------ §S1 skill ----

#: §S1: what the ``crucible`` skill states of the connection. Each entry is ``(what, regexes)``;
#: one normalised unit (a paragraph, a bullet with its continuation lines, a table row) must match
#: every regex of an entry.
CONNECTION_STATEMENTS = (
    ("[client] url from the first crucible.toml that exists and parses",
     (r"\[client\] url", r"\bfirst\b.{0,80}crucible\.toml",
      r"\bexists?\b.{0,40}\bpars(?:es|ed|ing)\b")),
    ("the order: the project's, the install's, the shipped one",
     (r"crucible\.toml",
      r"\bproject'?s?\b.{0,240}?\binstall(?:'s|ation'?s?)?(?![\w-]).{0,240}?\bshipped\b")),
    ("the shipped one is http://localhost:3849",
     (r"\bshipped\b.{0,160}http://localhost:3849|http://localhost:3849.{0,160}\bshipped\b",)),
    ("[client] is taken from that file only",
     (r"\[client\]",
      r"\bthat (?:one )?file only\b|\bonly (?:from |in )?that (?:one )?file\b"
      r"|\bthat file alone\b")),
    ("a project file without [client] sends the client to the shipped default",
     (r"\bwithout (?:a |any )?\[client\].{0,200}\bshipped\b",)),
)

#: A fixed board address: a host with a port, or the production board's port on its own.
HOST_PORT_RE = re.compile(r"\blocalhost:\d+|\b127\.0\.0\.1:\d+|:3849\b")


def connection_findings(text: str) -> list[str]:
    """What ``text`` (the ``crucible`` skill) lacks of §S1's connection statements."""
    found = norm_units(text)
    return [f"the skill does not state {what}" for what, rxs in CONNECTION_STATEMENTS
            if not any(all(re.search(rx, u) for rx in rxs) for u in found)]


def _intro(text: str) -> str:
    """The text after the frontmatter and before the first ``## `` heading."""
    body = text.split("\n---\n", 1)[1] if text.startswith("---\n") else text
    return body.split("\n## ", 1)[0]


def fixed_address_findings(text: str) -> list[str]:
    """Every place ``text`` names a host or port as the board: anywhere in its intro, and any unit
    naming one that is not about the shipped default."""
    out = [f"the intro names {m.group(0)!r}" for m in HOST_PORT_RE.finditer(_intro(text))]
    out += [f"names a fixed board address outside the shipped default: {u[:160]!r}"
            for u in norm_units(text) if HOST_PORT_RE.search(u) and not re.search(r"\bshipped\b", u)]
    return out


class CrucibleSkillConnectionTest(unittest.TestCase):
    """§S1/AC — the ``crucible`` skill states where a client finds its board, and names no fixed
    host or port as "the" board."""

    GOOD = ("---\nname: crucible\n---\n\n# Crucible\n\nCrucible is the test-outcome board.\n\n"
            "## Connection\n\n"
            "- A client reads its board from `[client] url` in the first `crucible.toml` that exists "
            "and parses, in this order: the project's, the install's (beside `clients/`), the shipped "
            "one (`http://localhost:3849`, the production board).\n"
            "- `[client]` is taken from that file only, so a project file without `[client]` sends "
            "the client to the shipped default.\n")

    def test_the_crucible_skill_states_the_client_url_resolution(self):
        self.assertEqual(connection_findings(CRUCIBLE_SKILL.read_text(encoding="utf-8")), [])

    def test_the_crucible_skill_names_no_fixed_board_address(self):
        self.assertEqual(fixed_address_findings(CRUCIBLE_SKILL.read_text(encoding="utf-8")), [])

    def test_the_connection_detector_both_ways(self):
        self.assertEqual(connection_findings(self.GOOD), [])
        for cut, missing in (
                ("`[client] url` in the first `crucible.toml` that exists and parses",
                 "[client] url from the first crucible.toml"),
                ("the install's (beside `clients/`), ", "the order"),
                (" (`http://localhost:3849`, the production board)", "http://localhost:3849"),
                ("from that file only, so ", "that file only"),
                ("without `[client]` sends the client to the shipped default", "without [client]")):
            with self.subTest(cut=cut):
                found = connection_findings(self.GOOD.replace(cut, "x"))
                self.assertTrue(any(missing in f for f in found), found)
        self.assertEqual(len(connection_findings(self.GOOD.replace(
            "the project's, the install's (beside `clients/`), the shipped one",
            "the shipped one, the install's (beside `clients/`), the project's"))), 1,
            "the order is part of the statement")

    def test_the_fixed_address_detector_both_ways(self):
        self.assertEqual(fixed_address_findings(self.GOOD), [])
        intro = self.GOOD.replace("Crucible is the test-outcome board.",
                                  "Crucible (`localhost:3849`) is the test-outcome board.")
        self.assertEqual(len(fixed_address_findings(intro)), 2,
                         "an intro naming the port bites twice: intro and unit")
        for line in ("- The board is `http://127.0.0.1:3849`.\n",
                     "- Check the board at port :3849 first.\n",
                     "- `curl -s http://localhost:4000/api/v2/runs`\n"):
            with self.subTest(line=line):
                self.assertEqual(len(fixed_address_findings(self.GOOD + line)), 1)


if __name__ == "__main__":
    unittest.main()
