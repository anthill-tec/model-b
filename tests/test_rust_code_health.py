"""``scripts/rust-code-health.py``'s snapshot, arguments and text (CR-MDB-078 §S3.2–§S3.6 —
AC10–AC14).

- ``SnapshotHotPathRulesTest`` — AC10 (§S3.2): a snapshot taken with ``hot_path_rules.toml`` in
  ``--out`` copies it into the snapshot directory, its dead-scan report carries that file's
  violation and sanity failure, and ``snapshot.json``'s ``totals`` count both.
- ``FailedSnapshotTest`` — AC11 (§S3.3): a sub-tool failure exits non-zero with the sub-tool's
  stderr and leaves no snapshot directory, so a rerun on the same commit and day succeeds.
- ``SnapshotOrderTest`` — AC12 (§S3.4): ``snapshot.json`` records ``created`` (UTC, to the
  second); with two ``pre`` snapshots of one slice taken the same day, the later one's short sha
  sorting first by name, a ``post`` pairs with the later one and ``health/index.json`` lists
  them in creation order.
- ``MissingArgumentsTest`` — AC13 (§S3.5): each missing or invalid argument is an argparse usage
  error (exit 2, no ``Traceback``) that leaves the ledger byte-identical and makes no commit.
- ``HeaderAndDocstringTest`` — AC14 (§S3.6): the ``# Consuming skills:`` header and the module
  docstring are current.

Every tool run is a subprocess of the test interpreter under ``tests/_helpers.py``'s
``run_tool``: the test process's environment with only ``PATH`` and git's configuration
variables changed, a ``PATH`` of ``git`` and ``tar`` links alone (no ``cargo``,
``cargo-machete`` or ``dot`` -- the snapshot's sub-tools take their absent paths), a temp working
directory, and ``--project-dir`` / ``--out`` pinned inside a fixture repository built by
``git_repo`` in a temp directory (§S4, AC15, AC16).

Stdlib only.
"""

import ast
import json
import re
import shutil
import tempfile
import time
import unittest
from datetime import UTC, date, datetime
from pathlib import Path

from tests._helpers import (
    TOOL_SCRIPTS_DIR,
    cargo_member_manifest,
    git_commit_all,
    git_repo,
    repo_git,
    run_tool,
    tool_bin_dir,
    write_files,
)

HEALTH = "rust-code-health.py"

#: The assets directory, relative to the fixture repository, every run pins as ``--out``.
ASSETS = "docs/research/assets"

#: The programs a health run must never find on its ``PATH`` (AC15): the sub-tools take their
#: absent paths, so no stand-in runs and no host program is spawned.
ABSENT_PROGRAMS = ("cargo", "cargo-machete", "dot")

#: ``snapshot.json``'s ``created`` form (§S3.4).
CREATED_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

#: A one-member workspace whose library has one forbidden call on a production line (line 2)
#: and the same call in a comment (dropped).
ALPHA_LIB = (
    "pub fn encode() -> String {\n"
    "    serde_json::to_string(&1).unwrap()\n"
    "}\n"
    "// serde_json::to_string in a comment is not a production line\n"
)

WORKSPACE = {
    "Cargo.toml": '[workspace]\nmembers = ["crates/alpha"]\n',
    "crates/alpha/Cargo.toml": cargo_member_manifest("alpha"),
    "crates/alpha/src/lib.rs": ALPHA_LIB,
}

#: One ``[[forbid]]`` rule the library breaks once, one ``[[require_present]]`` rule whose
#: pattern appears nowhere.
HOT_PATH_RULES = (
    "[[forbid]]\n"
    'id = "no-json-in-hot-path"\n'
    'paths = ["crates/alpha/src"]\n'
    'patterns = ["serde_json::to_string"]\n'
    "\n"
    "[[require_present]]\n"
    'id = "boundary-sanity"\n'
    'paths = ["crates/alpha/src"]\n'
    'pattern = "NEVER_PRESENT_TOKEN"\n'
)


def _utc_now_second() -> str:
    """The current UTC time in ``snapshot.json``'s ``created`` form."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _short_head(repo) -> str:
    return repo_git(repo, "rev-parse", "--short", "HEAD")


class _HealthRepo(unittest.TestCase):
    """A fixture repository holding ``files`` (a workspace), committed; a
    ``PATH`` of ``git`` and ``tar`` alone; a temp working directory."""

    @classmethod
    def build(cls, prefix: str, files: dict):
        work = Path(tempfile.mkdtemp(prefix=prefix)).resolve()
        repo = git_repo(work / "ws", files)
        bin_dir = tool_bin_dir(work / "bin")
        cwd = work / "cwd"
        cwd.mkdir()
        return work, repo, bin_dir, cwd

    def assertNoStandInOnPath(self, bin_dir):
        for program in ABSENT_PROGRAMS:
            self.assertIsNone(shutil.which(program, path=str(bin_dir)),
                              f"AC15: no {program} on the tool run's PATH")


def _snapshot(repo, bin_dir, cwd, phase, *extra):
    return run_tool(HEALTH, "snapshot", "--phase", phase, *extra, "--project-dir", repo,
                    "--out", repo / ASSETS, "--name", "fixture", bin_dir=bin_dir, cwd=cwd)


# ------------------------------------------------------------------ AC10 ----


class SnapshotHotPathRulesTest(_HealthRepo):
    """AC10 (§S3.2) — the snapshot seeds ``hot_path_rules.toml`` and applies it."""

    @classmethod
    def setUpClass(cls):
        files = {**WORKSPACE, f"{ASSETS}/hot_path_rules.toml": HOT_PATH_RULES}
        cls.work, cls.repo, cls.bin_dir, cls.cwd = cls.build("mdb-health-hotpath-", files)
        cls.head = _short_head(cls.repo)
        cls.result = _snapshot(cls.repo, cls.bin_dir, cls.cwd, "baseline")
        cls.snap = (cls.repo / ASSETS / "health"
                    / f"{date.today().isoformat()}_{cls.head}_baseline")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.work, True)

    def setUp(self):
        output = self.result.stdout + self.result.stderr
        self.assertNotIn("Traceback", output)
        self.assertEqual(self.result.returncode, 0, output)
        self.assertNoStandInOnPath(self.bin_dir)
        self.assertTrue((self.snap / "snapshot.json").is_file(), output)

    def test_the_snapshot_directory_holds_a_byte_identical_copy_of_the_hot_path_rules(self):
        seeded = self.snap / "hot_path_rules.toml"
        self.assertTrue(seeded.is_file(),
                        f"AC10: hot_path_rules.toml is seeded into {self.snap.name}; it holds "
                        f"{sorted(p.name for p in self.snap.iterdir())}")
        self.assertEqual(seeded.read_bytes(),
                         (self.repo / ASSETS / "hot_path_rules.toml").read_bytes())
        manifest = json.loads((self.snap / "snapshot.json").read_text(encoding="utf-8"))
        self.assertIn("hot_path_rules.toml", manifest["files"])

    def test_the_snapshot_dead_scan_report_carries_the_rules_violation_and_sanity_failure(self):
        report = json.loads((self.snap / "dead_scan_report.json").read_text(encoding="utf-8"))
        hot_path = report["hot_path"]
        self.assertTrue(hot_path["exists"],
                        f"AC10: the snapshot's dead-scan applies the rules file, not "
                        f"{hot_path['rules_file']} absent")
        self.assertEqual(
            [(v["rule"], v["path"], v["line"], v["content"]) for v in hot_path["violations"]],
            [("no-json-in-hot-path", "crates/alpha/src/lib.rs", 2,
              "serde_json::to_string(&1).unwrap()")],
            "AC10: exactly the one production-line violation; the comment line is dropped")
        self.assertEqual(
            [(s["rule"], s["pattern"]) for s in hot_path["sanity_failures"]],
            [("boundary-sanity", "NEVER_PRESENT_TOKEN")])
        markdown = (self.snap / "dead_scan_report.md").read_text(encoding="utf-8")
        self.assertIn("rule `no-json-in-hot-path`: `crates/alpha/src/lib.rs:2`", markdown)

    def test_the_snapshot_totals_count_hot_path_violations_and_sanity_failures(self):
        totals = json.loads((self.snap / "snapshot.json").read_text(encoding="utf-8"))["totals"]
        self.assertIn("hot_path_violations", totals, f"AC10: totals keys {sorted(totals)}")
        self.assertIn("hot_path_sanity_failures", totals, f"AC10: totals keys {sorted(totals)}")
        self.assertEqual(totals["hot_path_violations"], 1)
        self.assertEqual(totals["hot_path_sanity_failures"], 1)


# ------------------------------------------------------------------ AC11 ----


class FailedSnapshotTest(_HealthRepo):
    """AC11 (§S3.3) — a failed snapshot leaves nothing behind, so its rerun is not refused.

    The committed workspace names a member with no ``Cargo.toml``: both sub-tools refuse it.
    The fix writes the manifest without committing, so the rerun is on the same commit."""

    def setUp(self):
        files = dict(WORKSPACE)
        del files["crates/alpha/Cargo.toml"]
        self.work, self.repo, self.bin_dir, self.cwd = self.build("mdb-health-failed-", files)
        self.addCleanup(shutil.rmtree, self.work, True)
        self.head = _short_head(self.repo)
        self.health = self.repo / ASSETS / "health"

    def snapshot_dir(self) -> Path:
        return self.health / f"{date.today().isoformat()}_{self.head}_baseline"

    def test_a_sub_tool_failure_exits_non_zero_with_its_stderr_and_removes_the_snapshot(self):
        result = _snapshot(self.repo, self.bin_dir, self.cwd, "baseline")
        self.assertNoStandInOnPath(self.bin_dir)
        self.assertNotEqual(result.returncode, 0, "AC11: a failed snapshot exits non-zero")
        self.assertRegex(result.stderr,
                         re.compile(r"^error: workspace member \S*crates/alpha has no Cargo\.toml$",
                                    re.M),
                         "AC11: the sub-tool's stderr is passed through")
        self.assertNotIn("Traceback", result.stdout + result.stderr)
        self.assertFalse(self.snapshot_dir().exists(),
                         f"AC11: the snapshot directory {self.snapshot_dir().name} is removed")
        snapshots = [p.name for p in self.health.iterdir()] if self.health.exists() else []
        self.assertEqual([n for n in snapshots if n != "index.json"], [],
                         "AC11: no snapshot directory remains")
        self.assertEqual(repo_git(self.repo, "rev-parse", "--short", "HEAD"), self.head,
                         "a failed snapshot commits nothing")

    def test_a_rerun_after_the_cause_is_fixed_succeeds_on_the_same_commit_and_day(self):
        first = _snapshot(self.repo, self.bin_dir, self.cwd, "baseline")
        self.assertNotEqual(first.returncode, 0, first.stdout + first.stderr)
        write_files(self.repo, {"crates/alpha/Cargo.toml": cargo_member_manifest("alpha")})
        rerun = _snapshot(self.repo, self.bin_dir, self.cwd, "baseline")
        output = rerun.stdout + rerun.stderr
        self.assertNotIn("REFUSED", output, "AC11: the rerun is not refused")
        self.assertNotIn("Traceback", output)
        self.assertEqual(rerun.returncode, 0, output)
        manifest = json.loads((self.snapshot_dir() / "snapshot.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["head"], self.head, "the rerun is on the same commit")
        self.assertEqual(manifest["date"], date.today().isoformat())
        crate_map = json.loads((self.snapshot_dir() / "crate_map_baseline.json")
                               .read_text(encoding="utf-8"))
        self.assertEqual([row["pkg"] for row in crate_map["crates"]], ["alpha"])


# ------------------------------------------------------------------ AC12 ----


class SnapshotOrderTest(_HealthRepo):
    """AC12 (§S3.4) — snapshots order by ``created``, not by directory name.

    Two ``pre`` snapshots of ``CR-1`` the same day: the first at a commit whose short sha sorts
    high, the second at a commit whose short sha sorts below the first's -- so by name the
    later one comes first. Then a ``post`` of ``CR-1``."""

    SLICE = "CR-1"
    ATTEMPTS = 64

    @classmethod
    def setUpClass(cls):
        cls.work, cls.repo, cls.bin_dir, cls.cwd = cls.build("mdb-health-order-", WORKSPACE)
        cls.health = cls.repo / ASSETS / "health"
        cls._commit_until(lambda sha: sha[0] >= "8")
        cls.first_before = _utc_now_second()
        cls.first = cls._take("pre")
        cls.first_after = _utc_now_second()
        first_sha = cls.first[1].split("_")[1]
        if not cls.first[1].endswith(f"_pre_{cls.SLICE}"):
            raise AssertionError(f"fixture: unexpected snapshot name {cls.first[1]}")
        cls._commit_until(lambda sha: sha < first_sha)
        cls._next_second(cls._created(cls.first[1]))
        cls.second = cls._take("pre")
        cls._next_second(cls._created(cls.second[1]))
        cls.post = cls._take("post")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.work, True)

    @classmethod
    def _commit_until(cls, accept):
        """Make empty commits until the short HEAD sha satisfies ``accept``."""
        for attempt in range(cls.ATTEMPTS):
            if accept(_short_head(cls.repo)):
                return
            git_commit_all(cls.repo, f"bump {attempt}")
        raise AssertionError(f"fixture: no acceptable short sha in {cls.ATTEMPTS} commits")

    @classmethod
    def _next_second(cls, created):
        """Poll the clock until the UTC second is past ``created`` (so two snapshots never
        share one ``created``), bounded by a deadline."""
        deadline = time.monotonic() + 5
        while _utc_now_second() <= created:
            if time.monotonic() > deadline:
                raise AssertionError("fixture: the UTC clock did not advance")
            time.sleep(0.05)

    @classmethod
    def _created(cls, name) -> str:
        """The snapshot ``name``'s manifest ``created``; ``""`` when it records none."""
        path = cls.health / name / "snapshot.json"
        if not path.is_file():
            return ""
        return str(json.loads(path.read_text(encoding="utf-8")).get("created") or "")

    @classmethod
    def _take(cls, phase):
        before = cls._snapshot_dirs()
        result = _snapshot(cls.repo, cls.bin_dir, cls.cwd, phase, "--slice", cls.SLICE)
        added = sorted(cls._snapshot_dirs() - before)
        if len(added) != 1:
            raise AssertionError(f"fixture: one new {phase} snapshot directory, got {added}:\n"
                                 f"{result.stdout}{result.stderr}")
        return result, added[0]

    @classmethod
    def _snapshot_dirs(cls) -> set:
        if not cls.health.is_dir():
            return set()
        return {p.name for p in cls.health.iterdir() if p.is_dir()}

    def setUp(self):
        for result, name in (self.first, self.second, self.post):
            output = result.stdout + result.stderr
            self.assertNotIn("Traceback", output)
            self.assertEqual(result.returncode, 0, output)
            self.assertTrue((self.health / name / "snapshot.json").is_file(), output)
        self.assertNoStandInOnPath(self.bin_dir)
        self.assertLess(self.second[1], self.first[1],
                        "fixture: the later pre snapshot sorts first by name")

    def test_each_manifest_records_its_utc_creation_time_to_the_second(self):
        created = self._created(self.first[1])
        self.assertRegex(created, CREATED_RE, "AC12: snapshot.json carries `created`")
        self.assertLessEqual(self.first_before, created, "AC12: `created` is UTC, at the run")
        self.assertLessEqual(created, self.first_after, "AC12: `created` is UTC, at the run")
        self.assertLess(created, self._created(self.second[1]))
        self.assertLess(self._created(self.second[1]), self._created(self.post[1]))

    def test_a_post_snapshot_pairs_with_the_latest_created_pre_of_its_slice(self):
        later = self.second[1]
        delta = (self.health / self.post[1] / "health_delta.md").read_text(encoding="utf-8")
        self.assertEqual(delta.splitlines()[0],
                         f"# Health delta — `{later}` → `{self.post[1]}`",
                         "AC12: the post pairs with the later-created pre, not the "
                         "later-named one")
        self.assertIn(f"[health] delta vs {later} -> health_delta.md", self.post[0].stdout)

    def test_the_health_index_lists_the_snapshots_in_creation_order(self):
        index = json.loads((self.health / "index.json").read_text(encoding="utf-8"))
        self.assertEqual([entry["dir"] for entry in index],
                         [self.first[1], self.second[1], self.post[1]],
                         "AC12: index.json orders by `created`")


# ------------------------------------------------------------------ AC13 ----

#: Two ledger rows, both reassignable, one already assigned to ``CR-OLD`` with an open lineage
#: entry. Written in compact JSON, a form the tool's own save never produces, so any rewrite
#: changes the file's bytes.
LEDGER_ROWS = (
    {"id": "DS-aaaa", "status": "APPROVED", "verdict": "CULL", "crate": "alpha",
     "slice": "CR-OLD",
     "slice_history": [{"cr": "CR-OLD", "assigned": "2026-01-01", "outcome": None}]},
    {"id": "DS-bbbb", "status": "PROPOSED", "verdict": "CULL", "crate": "alpha", "slice": None},
)
LEDGER_TEXT = "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in LEDGER_ROWS)


class MissingArgumentsTest(_HealthRepo):
    """AC13 (§S3.5) — a missing or invalid argument is an argparse usage error: exit 2, no
    ``Traceback``, the ledger byte-identical, no new commit."""

    def setUp(self):
        files = {**WORKSPACE, f"{ASSETS}/audit-cull-ledger.jsonl": LEDGER_TEXT}
        self.work, self.repo, self.bin_dir, self.cwd = self.build("mdb-health-args-", files)
        self.addCleanup(shutil.rmtree, self.work, True)
        (self.repo / ASSETS / "health").mkdir()
        self.ledger = self.repo / ASSETS / "audit-cull-ledger.jsonl"

    def assertUsageError(self, *args):
        before_bytes = self.ledger.read_bytes()
        before_head = repo_git(self.repo, "rev-parse", "HEAD")
        before_count = repo_git(self.repo, "rev-list", "--count", "HEAD")
        result = run_tool(HEALTH, *args, "--project-dir", self.repo, "--out", self.repo / ASSETS,
                          bin_dir=self.bin_dir, cwd=self.cwd)
        output = result.stdout + result.stderr
        self.assertNotIn("Traceback", output, f"AC13: no traceback for {args}")
        self.assertEqual(result.returncode, 2, f"AC13: {args} is a usage error:\n{output}")
        self.assertTrue(result.stderr.startswith("usage: "),
                        f"AC13: argparse prints its usage for {args}:\n{result.stderr}")
        self.assertRegex(result.stderr, re.compile(r"^rust-code-health\.py.*: error: ", re.M))
        self.assertEqual(self.ledger.read_bytes(), before_bytes,
                         f"AC13: the ledger is byte-identical after {args}")
        self.assertEqual(repo_git(self.repo, "rev-parse", "HEAD"), before_head,
                         f"AC13: {args} makes no commit")
        self.assertEqual(repo_git(self.repo, "rev-list", "--count", "HEAD"), before_count)

    def test_query_crate_without_a_crate_is_a_usage_error(self):
        self.assertUsageError("query", "crate")

    def test_query_delta_without_snapshot_names_is_a_usage_error(self):
        self.assertUsageError("query", "delta")

    def test_query_delta_with_one_snapshot_name_is_a_usage_error(self):
        self.assertUsageError("query", "delta", "2026-01-01_abc1234_pre")

    def test_ledger_assign_without_slice_is_a_usage_error(self):
        self.assertUsageError("ledger", "assign", "--ids", "DS-aaaa,DS-bbbb")

    def test_ledger_assign_without_ids_is_a_usage_error(self):
        self.assertUsageError("ledger", "assign", "--slice", "CR-NEW")

    def test_ledger_sync_with_slice_but_no_db_state_is_a_usage_error(self):
        self.assertUsageError("ledger", "sync", "--slice", "CR-OLD")

    def test_ledger_sync_with_db_state_but_no_slice_is_a_usage_error(self):
        self.assertUsageError("ledger", "sync", "--db-state", "COMPLETED")

    def test_ledger_sync_with_an_unknown_db_state_is_a_usage_error(self):
        self.assertUsageError("ledger", "sync", "--slice", "CR-OLD", "--db-state", "MERGED")


# ------------------------------------------------------------------ AC14 ----

HEALTH_SOURCE = TOOL_SCRIPTS_DIR / HEALTH

#: The docstring lines ``tests/test_worktree_flow_dbless.py`` reads (§S3.6).
DOCSTRING_HEAD_LINES = 40


def _header_lines(source: str) -> list:
    """The ``#`` comment lines at the top of ``source``, before the module docstring."""
    lines = []
    for line in source.splitlines():
        if not line.startswith("#"):
            break
        lines.append(line)
    return lines


def _consuming_skills_entry(header: list) -> str:
    """The ``# Consuming skills:`` entry with its indented continuation lines, joined."""
    entry, inside = [], False
    for line in header:
        body = line.lstrip("#")
        if body.strip().startswith("Consuming skills:"):
            inside = True
            entry.append(body.strip())
        elif inside and body.startswith("   ") and body.strip():
            entry.append(body.strip())
        elif inside:
            break
    return " ".join(entry)


def _paragraphs(text: str) -> list:
    return [p for p in re.split(r"\n\s*\n", text) if p.strip()]


class HeaderAndDocstringTest(unittest.TestCase):
    """AC14 (§S3.6) — the ``# Consuming skills:`` header and the module docstring are current."""

    @classmethod
    def setUpClass(cls):
        cls.source = HEALTH_SOURCE.read_text(encoding="utf-8")
        cls.docstring = ast.get_docstring(ast.parse(cls.source)) or ""
        cls.header = _header_lines(cls.source)

    def test_the_consuming_skills_header_names_the_code_health_skill_as_published(self):
        entry = _consuming_skills_entry(self.header)
        self.assertTrue(entry.startswith("Consuming skills:"),
                        f"the header keeps its `Consuming skills:` key:\n{self.header}")
        self.assertIn("code-health", entry)
        self.assertNotRegex(entry, re.compile(r"not\s+publish|unpublished|not\s+yet\s+published",
                                              re.I),
                            f"AC14: the header may not say code-health is unpublished:\n{entry}")
        self.assertTrue(any(line.lstrip("# ").startswith("Owner:") for line in self.header),
                        "the header keeps its `Owner:` key")

    def test_the_docstring_does_not_name_schedule_db_set_state(self):
        self.assertNotIn("schedule_db.set_state", self.docstring,
                         "AC14: board transitions no longer mirror through schedule_db.set_state")

    def test_the_docstring_does_not_name_the_changeset_db(self):
        self.assertNotIn("ChangeSet-DB", self.docstring,
                         "AC14: the ledger's slice is not a ChangeSet-DB CR id")

    def test_the_docstring_does_not_name_the_python_crucible_client(self):
        self.assertNotIn("python-crucible.py", self.docstring,
                         "AC14: a rust project's client is rust-crucible.py")

    def test_a_board_transition_reaches_the_ledger_only_through_ledger_sync(self):
        transition = [p for p in _paragraphs(self.docstring)
                      if re.search(r"board\S*\s+transition", p, re.I)]
        self.assertTrue(transition,
                        "AC14: the docstring says how a board transition reaches the ledger")
        for paragraph in transition:
            self.assertRegex(paragraph, re.compile(r"\bledger\s+sync\b"),
                             f"AC14: `ledger sync` is the way:\n{paragraph}")
            self.assertNotIn("schedule_db", paragraph,
                             f"AC14: no schedule_db mirror:\n{paragraph}")

    def test_the_cr_is_filed_with_rust_crucible_cr_plan_within_the_first_forty_lines(self):
        head = "\n".join(self.source.splitlines()[:DOCSTRING_HEAD_LINES])
        self.assertRegex(self.docstring, re.compile(r"rust-crucible\.py\s+cr-plan\b"),
                         "AC14: `rust-crucible.py cr-plan` is the filing step")
        self.assertRegex(head, re.compile(r"rust-crucible\.py\s+cr-plan\b"),
                         f"§S3.6: the filing step stays within the first "
                         f"{DOCSTRING_HEAD_LINES} lines")
        self.assertRegex(head, re.compile(r"\bledger\s+assign\b"))

    def test_the_ledger_slice_key_is_the_cr_id_on_the_crucible_board(self):
        keys = [line for line in self.docstring.splitlines() if re.search(r"\bslice\s*->", line)]
        self.assertEqual(len(keys), 1, f"one `slice ->` key in the join table:\n{keys}")
        self.assertRegex(keys[0], re.compile(r"slice\s*->\s*.*Crucible"),
                         f"§S3.6: the slice is the CR id on the Crucible board:\n{keys[0]}")


if __name__ == "__main__":
    unittest.main()
