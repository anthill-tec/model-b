"""``scripts/rust-code-health.py``'s behaviour, snapshot, arguments and text (CR-MDB-078 §S3 —
AC9–AC14, AC16).

- ``SnapshotTest``, ``SnapshotRefusalTest``, ``SnapshotPostPairingTest``,
  ``SnapshotPostFallbackTest`` — AC9 (§S3.1 ``snapshot``): the directory name, the manifest,
  the refusal of an existing snapshot, the seeded configs, the refreshed living copies,
  ``health/index.json``, the dirty-tree warning, the auto-commit staging only the snapshot's
  paths, a ``post``'s pairing and ratification verdicts, and a ``post`` with no pair.
- ``QueryTest`` — AC9 (§S3.1 ``query trend|crate|delta|ledger``).
- ``LedgerAssignTest``, ``LedgerAbsentTest`` — AC9 (§S3.1 ``ledger assign``).
- ``LedgerSyncTest`` — AC9 (§S3.1 ``ledger sync``): the four board states and the no-argument
  sync with no legacy ChangeSet DB.
- ``SnapshotWithoutDotTest``, ``SnapshotPostLedgerCommitTest`` — AC9, AC15 (§S3.1 the
  auto-commit staging the snapshot's paths): with no ``dot`` the snapshot commits the paths it
  wrote and leaves the tree clean; a ``post`` commits the living ledger it rewrote.
- ``QueryWithoutHealthDirectoryTest`` — AC9 (§S3.1 ``query ledger`` with no ledger): with no
  ``<out>/health/``, ``query ledger`` reports no ledger and ``query trend`` exits 0, neither
  with a ``Traceback``.
- ``ToolCommitWithoutGlobalIdentityTest`` — AC16: a tool's own commit succeeds in a
  ``git_repo`` repository with no global git identity.
- ``SnapshotHotPathRulesTest`` — AC10 (§S3.2): a snapshot taken with ``hot_path_rules.toml`` in
  ``--out`` copies it into the snapshot directory, its dead-scan report carries that file's
  violation and sanity failure, and ``snapshot.json``'s ``totals`` count both.
- ``FailedSnapshotTest`` — AC11 (§S3.3): a sub-tool failure exits non-zero with the sub-tool's
  stderr and leaves no snapshot directory, so a rerun on the same commit and day succeeds.
- ``SnapshotOrderTest`` — AC12 (§S3.4): ``snapshot.json`` records ``created`` (UTC, to the
  second); with two ``pre`` snapshots of one slice taken the same day, the later one's short sha
  sorting first by name, a ``post`` pairs with the later one and ``health/index.json`` lists
  them in creation order.
- ``LegacySnapshotOrderTest`` — AC12 (§S3.4, the fallback for a manifest without ``created``):
  such a manifest ranks as made at the start of its directory's date, so in
  ``health/index.json`` and in a ``post``'s pairing it comes before every snapshot of the same
  date that records ``created``; across dates the date decides.
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
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import UTC, date, datetime
from pathlib import Path

from tests._helpers import (
    TOOL_SCRIPTS_DIR,
    cargo_member_manifest,
    git_commit_all,
    git_merge_no_ff,
    git_repo,
    repo_git,
    run_tool,
    tool_bin_dir,
    tool_env,
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

#: The forbidden call's site in ``ALPHA_LIB``: its path from the workspace root and its line.
VIOLATION_PATH = "crates/alpha/src/lib.rs"
VIOLATION_LINE = 2


def _site(path: str, line: int) -> str:
    """A report's ``<path>:<line>`` site, built at run time so this module carries no literal
    path-and-line citation (``tests.test_cite_by_symbol``'s guard)."""
    return f"{path}:{line}"

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
    def build(cls, prefix: str, files: dict, *, dot: bool = False):
        """``dot=True`` puts a ``dot`` stand-in on the ``PATH`` (§S4.2): it logs its argv to
        ``<work>/dot.log`` and writes the svg it is asked for, never the host's ``dot``."""
        work = Path(tempfile.mkdtemp(prefix=prefix)).resolve()
        repo = git_repo(work / "ws", files)
        stand_ins = {"dot": _dot_stand_in(work / DOT_LOG)} if dot else None
        bin_dir = tool_bin_dir(work / "bin", stand_ins)
        cwd = work / "cwd"
        cwd.mkdir()
        return work, repo, bin_dir, cwd

    def assertNoStandInOnPath(self, bin_dir):
        for program in ABSENT_PROGRAMS:
            self.assertIsNone(shutil.which(program, path=str(bin_dir)),
                              f"AC15: no {program} on the tool run's PATH")

    def assertDotStandInRan(self, work, bin_dir, times: int):
        """AC15: the ``dot`` stand-in -- and no other program of :data:`ABSENT_PROGRAMS` --
        is on the ``PATH``, and it rendered exactly ``times`` svgs."""
        self.assertEqual(shutil.which("dot", path=str(bin_dir)), str(bin_dir / "dot"))
        for program in ("cargo", "cargo-machete"):
            self.assertIsNone(shutil.which(program, path=str(bin_dir)))
        log = work / DOT_LOG
        calls = log.read_text(encoding="utf-8").splitlines() if log.is_file() else []
        self.assertEqual(len(calls), times, f"AC15: the dot stand-in ran {times} time(s)")
        for call in calls:
            self.assertRegex(call, r"^-Tsvg \S+_crate_map\.dot -o \S+_crate_map\.svg$")


def _snapshot(repo, bin_dir, cwd, phase, *extra):
    return run_tool(HEALTH, "snapshot", "--phase", phase, *extra, "--project-dir", repo,
                    "--out", repo / ASSETS, "--name", "fixture", bin_dir=bin_dir, cwd=cwd)


#: The ``dot`` stand-in's call log, in the fixture's work directory.
DOT_LOG = "dot.log"


def _dot_stand_in(log: Path) -> str:
    """A ``dot`` stand-in (§S4.2): logs its argv to ``log`` and writes a placeholder svg at
    the path after ``-o`` -- the shape ``rust-crate-map.py`` calls (``dot -Tsvg <dot> -o
    <svg>``)."""
    return (
        f"#!{sys.executable}\n"
        "import sys\n"
        f"with open({str(log)!r}, 'a', encoding='utf-8') as fh:\n"
        "    fh.write(' '.join(sys.argv[1:]) + '\\n')\n"
        "with open(sys.argv[sys.argv.index('-o') + 1], 'w', encoding='utf-8') as fh:\n"
        "    fh.write('<svg/>\\n')\n"
    )


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
            [("no-json-in-hot-path", VIOLATION_PATH, VIOLATION_LINE,
              "serde_json::to_string(&1).unwrap()")],
            "AC10: exactly the one production-line violation; the comment line is dropped")
        self.assertEqual(
            [(s["rule"], s["pattern"]) for s in hot_path["sanity_failures"]],
            [("boundary-sanity", "NEVER_PRESENT_TOKEN")])
        markdown = (self.snap / "dead_scan_report.md").read_text(encoding="utf-8")
        self.assertIn(
            f"rule `no-json-in-hot-path`: `{_site(VIOLATION_PATH, VIOLATION_LINE)}`", markdown)

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


def _legacy_snapshot(phase: str, day: str, sha: str, slice_=None) -> tuple:
    """A snapshot directory as a tool from before §S3.4 wrote it -- its manifest records no
    ``created`` -- as ``(directory name, {relative path: text})`` under ``ASSETS``. It carries
    an empty crate map, so a ``post`` paired with it can still write its delta."""
    name = f"{day}_{sha}_{phase}" + (f"_{slice_}" if slice_ else "")
    manifest = {"schema": 1, "project": "fixture", "date": day, "head": sha,
                "branch": "main", "dirty": False, "phase": phase, "slice": slice_,
                "totals": {}, "files": ["crate_map_baseline.json"]}
    return name, {
        f"{ASSETS}/health/{name}/snapshot.json": json.dumps(manifest, indent=1),
        f"{ASSETS}/health/{name}/crate_map_baseline.json": json.dumps({"crates": []}),
    }


class LegacySnapshotOrderTest(_HealthRepo):
    """AC12 (§S3.4) -- a manifest without ``created`` falls back to its directory name: it
    ranks as made at the START of its directory's date. On the same date it comes before every
    manifest that records ``created``; across dates the date decides.

    The fixture repository holds three legacy snapshots (no ``created``): a ``baseline`` of
    2000-01-01, a ``pre`` of ``CR-9`` dated today (the UTC date the new snapshots' ``created``
    carries) and an ``adhoc`` of 2999-12-31. Then a ``pre`` and a ``post`` of ``CR-9`` are
    taken, each recording ``created``."""

    SLICE = "CR-9"

    @classmethod
    def setUpClass(cls):
        cls.today = datetime.now(UTC).date().isoformat()
        cls.earlier, earlier_files = _legacy_snapshot("baseline", "2000-01-01", "1111111")
        cls.legacy_pre, legacy_pre_files = _legacy_snapshot("pre", cls.today, "0000000",
                                                            cls.SLICE)
        cls.later, later_files = _legacy_snapshot("adhoc", "2999-12-31", "2222222")
        files = {**DEAD_WORKSPACE, **earlier_files, **legacy_pre_files, **later_files}
        cls.work, cls.repo, cls.bin_dir, cls.cwd = cls.build("mdb-health-legacy-", files,
                                                              dot=True)
        cls.health = cls.repo / ASSETS / "health"
        cls.pre_result, cls.pre = _take(cls.repo, cls.bin_dir, cls.cwd, "pre",
                                        "--slice", cls.SLICE)
        cls.post_result, cls.post = _take(cls.repo, cls.bin_dir, cls.cwd, "post",
                                          "--slice", cls.SLICE)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.work, True)

    def setUp(self):
        for result in (self.pre_result, self.post_result):
            self.assertNotIn("Traceback", result.stdout + result.stderr)
        self.assertDotStandInRan(self.work, self.bin_dir, 2)
        for name in (self.earlier, self.legacy_pre, self.later):
            self.assertNotIn("created", _manifest(self.health / name),
                             f"fixture: {name} is a legacy manifest")
        for name in (self.pre, self.post):
            self.assertEqual(_manifest(self.health / name)["created"][:10], self.today,
                             f"fixture: {name} was created on the legacy pre's date")

    def _index_dirs(self) -> list:
        index = json.loads((self.health / "index.json").read_text(encoding="utf-8"))
        return [entry["dir"] for entry in index]

    def test_on_the_same_date_the_index_ranks_a_legacy_manifest_before_created_ones(self):
        same_day = [d for d in self._index_dirs()
                    if d in (self.legacy_pre, self.pre, self.post)]
        self.assertEqual(same_day, [self.legacy_pre, self.pre, self.post],
                         "AC12: a manifest without `created` ranks as made at the start of its "
                         "directory's date -- before that date's snapshots recording `created`")

    def test_the_index_lists_every_snapshot_by_date_then_creation(self):
        self.assertEqual(self._index_dirs(),
                         [self.earlier, self.legacy_pre, self.pre, self.post, self.later],
                         "AC12: across dates the date decides; on one date a legacy manifest "
                         "comes first")

    def test_across_dates_the_date_decides_the_index_order(self):
        dirs = self._index_dirs()
        self.assertEqual(len(dirs), 5, dirs)
        self.assertEqual(dirs[0], self.earlier,
                         "AC12: a legacy manifest of an earlier date comes before today's")
        self.assertEqual(dirs[-1], self.later,
                         "AC12: a legacy manifest of a later date comes after today's")

    def test_a_post_pairs_with_the_created_pre_not_a_same_day_legacy_pre(self):
        delta = (self.health / self.post / "health_delta.md").read_text(encoding="utf-8")
        self.assertEqual(delta.splitlines()[0],
                         f"# Health delta — `{self.pre}` → `{self.post}`",
                         "AC12: the pairing orders by the same rule -- the legacy pre of the "
                         "same date is the EARLIER one")
        self.assertIn(f"[health] delta vs {self.pre} -> health_delta.md",
                      self.post_result.stdout)


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


# ------------------------------------------------------------------ AC9 / AC16 ----
#
# "Each §S3.1 behaviour has a test that runs `scripts/rust-code-health.py` as a subprocess
# against a temp git repository and asserts the files, ledger rows, commits or output it names"
# (AC9); a tool's own commit in a ``git_repo`` repository succeeds with no global git identity
# (AC16). A snapshot fixture carries the ``dot`` stand-in, so the svg its auto-commit names
# exists and no host ``dot`` runs.

#: A one-member workspace whose library carries one bare ``#[allow(dead_code)]`` (a live
#: inventory finding, ``fn unused``) and no pub-scan candidate.
DEAD_LIB = "#[allow(dead_code)]\nfn unused() {}\npub fn api() {}\n"

#: The bare ``#[allow(dead_code)]``'s site in ``DEAD_LIB``, as the inventory reports it: the
#: path within its crate, and its line.
DEAD_ALLOW_PATH = "src/lib.rs"
DEAD_ALLOW_LINE = 1

DEAD_WORKSPACE = {**WORKSPACE, "crates/alpha/src/lib.rs": DEAD_LIB}

#: ``DEAD_LIB`` grown by two private production lines (prod LOC 3 -> 5, no new finding).
GROWN_LIB = DEAD_LIB + "fn helper_one() {}\nfn helper_two() {}\n"

#: The three config files a snapshot seeds besides ``hot_path_rules.toml`` (AC10's).
CONFIG_FILES = {
    "crate_map.toml": "# fixture crate-map config\n",
    "dead_code_register.toml": "# fixture retention register\n",
    "boundary_rules.toml": "# fixture boundary rules\n",
}

#: The living copies a ``--name fixture`` snapshot refreshes in ``--out``.
LIVING_COPIES = ("crate_map_baseline.json", "crate_map_baseline.md", "dead_scan_report.json",
                 "dead_scan_report.md", "fixture_crate_map.dot", "fixture_crate_map.svg")

#: The fixture identity ``git_repo`` writes into the repository's own config.
FIXTURE_AUTHOR = "Fixture <fixture@example.invalid>"

LEDGER = "audit-cull-ledger.jsonl"


def _ledger_text(rows) -> str:
    """``rows`` as JSONL in the tool's own save form, so a tool rewrite of unchanged rows keeps
    the file's bytes."""
    return "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)


def _fields(row: dict, *keys) -> tuple:
    """``row``'s values at ``keys`` (``None`` for an absent key), so a missing field fails an
    assertion rather than raising."""
    return tuple(row.get(key) for key in keys)


def _read_ledger(path) -> dict:
    """The ledger at ``path`` as ``{id: row}``, in file order."""
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()]
    return {row["id"]: row for row in rows}


def _commit_files(repo, rev: str = "HEAD") -> list:
    """The paths the commit ``rev`` changed, sorted."""
    return sorted(p for p in repo_git(repo, "show", "--name-only", "--format=", rev)
                  .splitlines() if p)


def _subject(repo, rev: str = "HEAD") -> str:
    return repo_git(repo, "log", "-1", "--format=%s", rev)


def _author(repo, rev: str = "HEAD") -> str:
    return repo_git(repo, "log", "-1", "--format=%an <%ae>", rev)


def _commit_count(repo) -> int:
    return int(repo_git(repo, "rev-list", "--count", "HEAD"))


def _manifest(snap: Path) -> dict:
    return json.loads((snap / "snapshot.json").read_text(encoding="utf-8"))


def _wait_past(created: str):
    """Poll the clock until the UTC second is past ``created`` (so two snapshots never share
    one ``created``), bounded by a deadline."""
    deadline = time.monotonic() + 5
    while _utc_now_second() <= created:
        if time.monotonic() > deadline:
            raise AssertionError("fixture: the UTC clock did not advance")
        time.sleep(0.05)


def _health_dirs(health: Path) -> list:
    return sorted(p.name for p in health.iterdir() if p.is_dir()) if health.is_dir() else []


def _take(repo, bin_dir, cwd, phase, *extra):
    """Take one snapshot and return ``(result, new snapshot directory name)``; the clock is
    then moved past its ``created``, so the next snapshot sorts after it."""
    health = repo / ASSETS / "health"
    before = set(_health_dirs(health))
    result = _snapshot(repo, bin_dir, cwd, phase, *extra)
    added = sorted(set(_health_dirs(health)) - before)
    if result.returncode != 0 or len(added) != 1:
        raise AssertionError(f"fixture: one new {phase} snapshot, got {added}:\n"
                             f"{result.stdout}{result.stderr}")
    _wait_past(_manifest(health / added[0])["created"])
    return result, added[0]


class SnapshotTest(_HealthRepo):
    """§S3.1 snapshot (AC9, AC16): the directory name, the manifest, the seeded configs, the
    living copies, ``health/index.json``, the dirty-tree warning and the scoped auto-commit.

    A clean ``adhoc`` snapshot, then -- with ``README.md`` edited and staged and ``notes.txt``
    untracked -- a dirty ``baseline`` snapshot."""

    @classmethod
    def setUpClass(cls):
        files = {**DEAD_WORKSPACE, "README.md": "fixture\n",
                 **{f"{ASSETS}/{name}": text for name, text in CONFIG_FILES.items()},
                 f"{ASSETS}/dead_scan_report.json": "stale living copy\n",
                 f"{ASSETS}/crate_map_baseline.md": "stale living copy\n",
                 f"{ASSETS}/{LEDGER}": _ledger_text(
                     [{"id": "DS-keep", "status": "PROPOSED", "verdict": "KEEP",
                       "crate": "alpha", "slice": None}])}
        cls.work, cls.repo, cls.bin_dir, cls.cwd = cls.build("mdb-health-snap-", files, dot=True)
        cls.out = cls.repo / ASSETS
        cls.health = cls.out / "health"
        cls.today = date.today().isoformat()
        cls.clean_head = _short_head(cls.repo)
        cls.clean, cls.clean_name = _take(cls.repo, cls.bin_dir, cls.cwd, "adhoc")
        write_files(cls.repo, {"README.md": "edited\n", "notes.txt": "untracked\n"})
        repo_git(cls.repo, "add", "README.md")
        cls.dirty_parent = repo_git(cls.repo, "rev-parse", "HEAD")
        cls.dirty_head = _short_head(cls.repo)
        cls.dirty, cls.dirty_name = _take(cls.repo, cls.bin_dir, cls.cwd, "baseline")
        cls.snap = cls.health / cls.dirty_name

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.work, True)

    def setUp(self):
        for result in (self.clean, self.dirty):
            output = result.stdout + result.stderr
            self.assertNotIn("Traceback", output)
            self.assertEqual(result.returncode, 0, output)
        self.assertDotStandInRan(self.work, self.bin_dir, 2)

    def test_the_snapshot_directory_is_named_by_date_short_sha_and_phase(self):
        self.assertEqual(self.clean_name, f"{self.today}_{self.clean_head}_adhoc")
        self.assertEqual(self.dirty_name, f"{self.today}_{self.dirty_head}_baseline")
        self.assertEqual(_health_dirs(self.health), sorted([self.clean_name, self.dirty_name]))
        self.assertEqual(_manifest(self.snap)["head"], self.dirty_head)
        self.assertEqual(self.dirty.stdout.splitlines()[-1],
                         f"[health] snapshot {self.dirty_name} @ {self.dirty_head} "
                         f"(main, DIRTY) — {len(_manifest(self.snap)['files'])} files")

    def test_the_manifest_records_the_project_commit_phase_slice_totals_and_files(self):
        manifest = _manifest(self.snap)
        self.assertEqual(
            {k: manifest[k] for k in ("schema", "project", "date", "head", "branch", "dirty",
                                      "phase", "slice")},
            {"schema": 1, "project": "fixture", "date": self.today, "head": self.dirty_head,
             "branch": "main", "dirty": True, "phase": "baseline", "slice": None})
        self.assertRegex(manifest["created"], CREATED_RE)
        self.assertEqual(manifest["keys"],
                         "crate(pkg) -> module(file path) -> site(line); "
                         "finding IDs DS-* stable across snapshots")
        totals = manifest["totals"]
        self.assertEqual(
            {k: totals[k] for k in ("prod_loc", "allow_bare", "expect_marks", "deprecated",
                                    "pub_candidates", "unused_deps", "hot_path_violations")},
            {"prod_loc": 3, "allow_bare": 1, "expect_marks": 0, "deprecated": 0,
             "pub_candidates": 0, "unused_deps": 0, "hot_path_violations": 0})
        self.assertEqual(manifest["files"],
                         sorted(p.name for p in self.snap.iterdir() if p.name != "snapshot.json"))
        self.assertEqual(_manifest(self.health / self.clean_name)["phase"], "adhoc")

    def test_the_config_files_and_the_ledger_are_seeded_byte_identical(self):
        files = _manifest(self.snap)["files"]
        for name, text in CONFIG_FILES.items():
            self.assertEqual((self.snap / name).read_text(encoding="utf-8") if
                             (self.snap / name).is_file() else None, text,
                             f"§S3.1: {name} is seeded into the snapshot")
            self.assertIn(name, files)
        self.assertEqual((self.snap / LEDGER).read_bytes(), (self.out / LEDGER).read_bytes(),
                         "the frozen ledger copy")
        self.assertNotIn("hot_path_rules.toml", files, "no rules file in --out, none seeded")

    def test_the_living_copies_in_out_are_refreshed_from_the_latest_snapshot(self):
        for name in LIVING_COPIES:
            self.assertTrue((self.out / name).is_file(), f"{name} is refreshed into --out")
            self.assertEqual((self.out / name).read_bytes(), (self.snap / name).read_bytes(),
                             f"§S3.1: --out/{name} is the latest snapshot's copy")
        self.assertNotEqual((self.out / "dead_scan_report.json").read_text(encoding="utf-8"),
                            "stale living copy\n")

    def test_the_health_index_is_rebuilt_with_every_snapshot(self):
        self.assertTrue((self.health / "index.json").is_file(),
                        "§S3.1: the snapshot rebuilds health/index.json")
        index = json.loads((self.health / "index.json").read_text(encoding="utf-8"))
        self.assertEqual([entry["dir"] for entry in index], [self.clean_name, self.dirty_name])
        for entry in index:
            manifest = _manifest(self.health / entry["dir"])
            self.assertEqual(entry, {"dir": entry["dir"],
                                     **{k: manifest[k] for k in ("created", "date", "head",
                                                                 "branch", "dirty", "phase",
                                                                 "slice")},
                                     "totals": manifest["totals"]})

    def test_a_dirty_tree_is_warned_about_and_recorded_a_clean_one_is_not(self):
        warning = ("[health] ⚠ WORKING TREE DIRTY — a snapshot should pin a real "
                   "commit; recorded as dirty=true, treat with suspicion.")
        self.assertEqual(self.dirty.stderr.splitlines(), [warning])
        self.assertTrue(_manifest(self.snap)["dirty"])
        self.assertEqual(self.clean.stderr, "", "a clean tree is not warned about")
        self.assertFalse(_manifest(self.health / self.clean_name)["dirty"])
        self.assertNotIn("DIRTY", self.clean.stdout)

    def test_the_auto_commit_stages_only_the_snapshots_paths(self):
        self.assertEqual(_subject(self.repo),
                         f"docs(health): BASELINE snapshot {self.dirty_name}")
        self.assertEqual(repo_git(self.repo, "rev-parse", "HEAD^"), self.dirty_parent,
                         "exactly one commit for the snapshot")
        self.assertIn(f"[health] committed: docs(health): BASELINE snapshot {self.dirty_name}",
                      self.dirty.stdout.splitlines())
        committed = _commit_files(self.repo)
        snap_rel = f"{ASSETS}/health/{self.dirty_name}"
        allowed = {f"{ASSETS}/health/index.json", *(f"{ASSETS}/{n}" for n in LIVING_COPIES)}
        self.assertEqual([p for p in committed if p.startswith(snap_rel + "/")],
                         sorted(f"{snap_rel}/{p.name}" for p in self.snap.iterdir()),
                         "the whole snapshot directory is committed")
        self.assertEqual([p for p in committed if not p.startswith(snap_rel + "/")
                          and p not in allowed], [],
                         "§S3.1: nothing outside the snapshot's paths is committed")
        self.assertIn(f"{ASSETS}/health/index.json", committed)
        self.assertEqual(repo_git(self.repo, "diff", "--cached", "--name-only"), "README.md",
                         "the unrelated staged edit stays staged, uncommitted")
        self.assertEqual(repo_git(self.repo, "status", "--porcelain"),
                         "M  README.md\n?? notes.txt",
                         "the snapshot leaves only the unrelated changes behind")
        self.assertEqual(_subject(self.repo, "HEAD^"),
                         f"docs(health): ADHOC snapshot {self.clean_name}")


class SnapshotRefusalTest(_HealthRepo):
    """§S3.1 snapshot (AC9): an existing snapshot directory is refused, untouched."""

    def setUp(self):
        self.work, self.repo, self.bin_dir, self.cwd = self.build("mdb-health-refuse-",
                                                                  DEAD_WORKSPACE, dot=True)
        self.addCleanup(shutil.rmtree, self.work, True)
        self.health = self.repo / ASSETS / "health"
        self.existing = (self.health
                         / f"{date.today().isoformat()}_{_short_head(self.repo)}_pre_CR-7")
        write_files(self.existing, {"snapshot.json": '{"sentinel": true}\n'})

    def test_an_existing_snapshot_is_refused_and_left_untouched(self):
        count = _commit_count(self.repo)
        result = _snapshot(self.repo, self.bin_dir, self.cwd, "pre", "--slice", "CR-7")
        self.assertNotIn("Traceback", result.stdout + result.stderr)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stderr.splitlines()[-1],
                         f"[health] REFUSED: {self.existing} exists — snapshots are "
                         f"immutable.")
        self.assertEqual(sorted(p.name for p in self.existing.iterdir()), ["snapshot.json"])
        self.assertEqual((self.existing / "snapshot.json").read_text(encoding="utf-8"),
                         '{"sentinel": true}\n')
        self.assertEqual(_health_dirs(self.health), [self.existing.name])
        self.assertFalse((self.health / "index.json").exists())
        self.assertFalse((self.repo / ASSETS / "dead_scan_report.json").exists())
        self.assertEqual(_commit_count(self.repo), count, "a refused snapshot commits nothing")
        self.assertDotStandInRan(self.work, self.bin_dir, 0)


class SnapshotPostPairingTest(_HealthRepo):
    """§S3.1 snapshot (AC9): a ``post`` pairs with its slice's latest ``pre`` -- not a later
    ``baseline``, not another slice's ``pre`` -- and ``health_delta.md`` carries each
    COMPLETED row's ratification verdict.

    ``pre CR-7``, then a ledger naming ``CR-7``'s findings, ``pre CR-8``, ``baseline``, then
    ``post CR-7``."""

    @classmethod
    def setUpClass(cls):
        cls.work, cls.repo, cls.bin_dir, cls.cwd = cls.build("mdb-health-post-",
                                                              DEAD_WORKSPACE, dot=True)
        cls.out = cls.repo / ASSETS
        cls.health = cls.out / "health"
        _, cls.pre = _take(cls.repo, cls.bin_dir, cls.cwd, "pre", "--slice", "CR-7")
        report = json.loads((cls.health / cls.pre / "dead_scan_report.json")
                            .read_text(encoding="utf-8"))
        live = [f["id"] for f in report["inventory"] if f["item"] == "fn unused"]
        if len(live) != 1:
            raise AssertionError(f"fixture: one live `fn unused` finding, got {live}")
        cls.live = live[0]
        cls.rows = [
            {"id": cls.live, "status": "COMPLETED", "verdict": "CULL", "crate": "alpha",
             "slice": "CR-7", "source": "scan", "item": "fn unused"},
            {"id": "DS-0000000000", "status": "COMPLETED", "verdict": "CULL",
             "crate": "alpha", "slice": "CR-7", "source": "scan", "item": "fn gone"},
            {"id": "F-1", "status": "COMPLETED", "verdict": "KEEP", "crate": "alpha",
             "slice": "CR-7", "source": "seed", "item": "manual check"},
            {"id": "F-2", "status": "COMPLETED", "verdict": "CULL", "crate": "gamma",
             "slice": "CR-7", "source": "seed", "item": "crate gamma"},
            {"id": "DS-1111111111", "status": "IN_PROGRESS", "verdict": "CULL",
             "crate": "alpha", "slice": "CR-7", "item": "fn later"},
            {"id": "DS-2222222222", "status": "COMPLETED", "verdict": "CULL",
             "crate": "alpha", "slice": "CR-8", "item": "fn other"},
        ]
        write_files(cls.out, {LEDGER: _ledger_text(cls.rows)})
        git_commit_all(cls.repo, "ledger")
        _, cls.other_pre = _take(cls.repo, cls.bin_dir, cls.cwd, "pre", "--slice", "CR-8")
        _, cls.baseline = _take(cls.repo, cls.bin_dir, cls.cwd, "baseline")
        cls.result, cls.post = _take(cls.repo, cls.bin_dir, cls.cwd, "post", "--slice", "CR-7")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.work, True)

    def setUp(self):
        output = self.result.stdout + self.result.stderr
        self.assertNotIn("Traceback", output)
        self.assertEqual(self.result.returncode, 0, output)
        self.assertDotStandInRan(self.work, self.bin_dir, 4)
        self.assertTrue(self.pre.endswith("_pre_CR-7"), self.pre)
        self.assertTrue(self.post.endswith("_post_CR-7"), self.post)

    def test_a_post_pairs_with_its_slices_latest_pre_not_a_later_baseline(self):
        delta = (self.health / self.post / "health_delta.md").read_text(encoding="utf-8")
        self.assertEqual(delta.splitlines()[0],
                         f"# Health delta — `{self.pre}` → `{self.post}`")
        self.assertIn(f"[health] delta vs {self.pre} -> health_delta.md (1 NOT-RATIFIED)",
                      self.result.stdout.splitlines())
        self.assertIn("| prod_loc | 3 | 3 | 0 |", delta.splitlines())

    def test_the_delta_carries_each_completed_rows_ratification_verdict(self):
        delta = (self.health / self.post / "health_delta.md").read_text(encoding="utf-8")
        self.assertTrue(delta.endswith(
            "\n## Ratification (ledger vs fresh scan)\n\n"
            f"- 🛑 `{self.live}` **NOT-RATIFIED** fn unused\n"
            "- ✅ `DS-0000000000` **RATIFIED** fn gone\n"
            "- ❓ `F-1` **MANUAL** manual check\n"
            "- ✅ `F-2` **RATIFIED** crate gamma\n"
            "\n**1 NOT-RATIFIED finding(s) — the slice claimed completion but they "
            "survive. Do not sign off.**\n"), delta)

    def test_the_ledger_records_each_verdict_on_the_completed_rows_of_the_slice(self):
        rows = _read_ledger(self.out / LEDGER)
        today = date.today().isoformat()
        for fid_, verdict in ((self.live, "NOT-RATIFIED"), ("DS-0000000000", "RATIFIED"),
                              ("F-1", "MANUAL"), ("F-2", "RATIFIED")):
            row = rows[fid_]
            self.assertEqual((row.get("ratified"), row.get("ratified_in"),
                              row.get("status_date")), (verdict, self.post, today), fid_)
            self.assertEqual(row.get("resolved_in"),
                             None if verdict == "NOT-RATIFIED" else self.post, fid_)
        original = {row["id"]: row for row in self.rows}
        for untouched in ("DS-1111111111", "DS-2222222222"):
            self.assertEqual(rows[untouched], original[untouched],
                             "only the slice's COMPLETED rows are ratified")
        self.assertEqual((self.health / self.post / LEDGER).read_bytes(),
                         (self.out / LEDGER).read_bytes(), "the frozen copy is ratified")


class SnapshotPostFallbackTest(_HealthRepo):
    """§S3.1 snapshot (AC9): a ``post`` whose slice has no ``pre`` pairs with the latest
    ``baseline``; with neither, it says so and writes no delta."""

    def setUp(self):
        self.work, self.repo, self.bin_dir, self.cwd = self.build("mdb-health-fallback-",
                                                                  DEAD_WORKSPACE, dot=True)
        self.addCleanup(shutil.rmtree, self.work, True)
        self.health = self.repo / ASSETS / "health"

    def test_a_post_with_no_pre_of_its_slice_pairs_with_the_latest_baseline(self):
        _, first = _take(self.repo, self.bin_dir, self.cwd, "baseline")
        _, latest = _take(self.repo, self.bin_dir, self.cwd, "baseline")
        _take(self.repo, self.bin_dir, self.cwd, "pre", "--slice", "CR-8")
        result, post = _take(self.repo, self.bin_dir, self.cwd, "post", "--slice", "CR-9")
        self.assertNotIn("Traceback", result.stdout + result.stderr)
        self.assertDotStandInRan(self.work, self.bin_dir, 4)
        self.assertNotEqual(first, latest)
        delta = (self.health / post / "health_delta.md").read_text(encoding="utf-8")
        self.assertEqual(delta.splitlines()[0],
                         f"# Health delta — `{latest}` → `{post}`",
                         "§S3.1: the latest baseline, not the first nor CR-8's pre")
        self.assertIn(f"[health] delta vs {latest} -> health_delta.md",
                      result.stdout.splitlines())
        self.assertNotIn("## Ratification", delta, "no ledger, no ratification")

    def test_a_post_with_no_pair_says_so_and_writes_no_delta(self):
        _take(self.repo, self.bin_dir, self.cwd, "adhoc")
        _take(self.repo, self.bin_dir, self.cwd, "pre", "--slice", "CR-8")
        result, post = _take(self.repo, self.bin_dir, self.cwd, "post", "--slice", "CR-9")
        self.assertNotIn("Traceback", result.stdout + result.stderr)
        self.assertDotStandInRan(self.work, self.bin_dir, 3)
        self.assertIn("[health] no paired pre/baseline snapshot found — no delta",
                      result.stdout.splitlines())
        self.assertNotIn("delta vs", result.stdout)
        self.assertFalse((self.health / post / "health_delta.md").exists())
        self.assertNotIn("health_delta.md", _manifest(self.health / post)["files"])


QUERY_LEDGER = (
    {"id": "DS-q1", "status": "APPROVED", "verdict": "CULL", "crate": "alpha",
     "path": "src/lib.rs", "line": 1, "item": "fn unused", "finding": "bare allow"},
    {"id": "DS-q2", "status": "PROPOSED", "verdict": "KEEP", "crate": "alpha",
     "path": "src/lib.rs", "item": "fn api", "finding": "public api"},
    {"id": "F-q3", "status": "APPROVED", "verdict": "CULL", "crate": None,
     "finding": "workspace dep"},
)

QUERY_LEDGER_LINES = {
    "DS-q1": (f"- DS-q1 [CULL/APPROVED] alpha "
              f"{_site(QUERY_LEDGER[0]['path'], QUERY_LEDGER[0]['line'])} fn unused — bare allow"),
    "DS-q2": "- DS-q2 [KEEP/PROPOSED] alpha src/lib.rs fn api — public api",
    "F-q3": "- F-q3 [CULL/APPROVED] (workspace)   — workspace dep",
}


class QueryTest(_HealthRepo):
    """§S3.1 ``query trend``, ``query crate``, ``query delta`` and ``query ledger`` (AC9),
    over a ``baseline`` snapshot and an ``adhoc`` one after the library grew two lines."""

    @classmethod
    def setUpClass(cls):
        files = {**DEAD_WORKSPACE, f"{ASSETS}/{LEDGER}": _ledger_text(QUERY_LEDGER)}
        cls.work, cls.repo, cls.bin_dir, cls.cwd = cls.build("mdb-health-query-", files,
                                                              dot=True)
        cls.out = cls.repo / ASSETS
        _, cls.first = _take(cls.repo, cls.bin_dir, cls.cwd, "baseline")
        write_files(cls.repo, {"crates/alpha/src/lib.rs": GROWN_LIB})
        git_commit_all(cls.repo, "grow alpha")
        _, cls.second = _take(cls.repo, cls.bin_dir, cls.cwd, "adhoc")
        report = json.loads((cls.out / "health" / cls.second / "dead_scan_report.json")
                            .read_text(encoding="utf-8"))
        cls.live = [f["id"] for f in report["inventory"]]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.work, True)

    def setUp(self):
        self.assertDotStandInRan(self.work, self.bin_dir, 2)
        self.assertEqual(len(self.live), 1, self.live)

    def query(self, *args, out=None):
        out = out or self.out
        result = run_tool(HEALTH, "query", *args, "--project-dir", out.parent.parent.parent,
                          "--out", out, bin_dir=self.bin_dir, cwd=self.cwd)
        self.assertNotIn("Traceback", result.stdout + result.stderr)
        return result

    def assertQueryOutput(self, args, expected):
        result = self.query(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, expected)

    def test_query_trend_tabulates_every_snapshot_in_order(self):
        self.assertQueryOutput(("trend",), (
            "| snapshot | phase | prod | test | tests# | allows | expects | pub-cand | deps |\n"
            "|---|---|---:|---:|---:|---:|---:|---:|---:|\n"
            f"| {self.first} | baseline | 3 | 0 | 0 | 1 | 0 | 0 | 0 |\n"
            f"| {self.second} | adhoc | 5 | 0 | 0 | 1 | 0 | 0 | 0 |\n"))

    def test_query_crate_follows_one_crate_and_lists_its_open_findings(self):
        self.assertQueryOutput(("crate", "alpha"), (
            "# alpha across snapshots\n"
            f"- {self.first} (baseline): prod 3, test 0, tests# 0, dead 1, fan-in 0\n"
            f"- {self.second} (adhoc): prod 5, test 0, tests# 0, dead 1, fan-in 0\n"
            f"\nOpen findings @ {self.second}: 1 suppressions, 0 pub candidates\n"
            f"- {self.live[0]} [allow] {_site(DEAD_ALLOW_PATH, DEAD_ALLOW_LINE)} "
            "fn unused (unclassified)\n"))

    def test_query_crate_of_an_unknown_crate_lists_nothing(self):
        self.assertQueryOutput(("crate", "ghost"), (
            "# ghost across snapshots\n"
            f"\nOpen findings @ {self.second}: 0 suppressions, 0 pub candidates\n"))

    def test_query_delta_compares_two_snapshots(self):
        metrics = [("prod_loc", 3, 5), ("test_loc", 0, 0), ("tests", 0, 0), ("ignored", 0, 0),
                   ("allow_bare", 1, 1), ("expect_marks", 0, 0), ("deprecated", 0, 0),
                   ("pub_candidates", 0, 0), ("unused_deps", 0, 0), ("unused_features", 0, 0)]
        rows = "".join(f"| {k} | {a} | {b} | {'+' if b > a else ''}{b - a} |\n"
                       for k, a, b in metrics)
        self.assertQueryOutput(("delta", self.first, self.second), (
            f"# Health delta — `{self.first}` → `{self.second}`\n\n"
            "| metric | pre | post | Δ |\n|---|---:|---:|---:|\n" + rows +
            "\n## Per-crate LOC movers\n\n"
            "| crate | pre | post | Δ |\n|---|---:|---:|---:|\n"
            "| alpha | 3 | 5 | +2 |\n"))

    def test_query_ledger_without_a_filter_lists_every_row(self):
        self.assertQueryOutput(("ledger",), (
            "ledger rows: 3 | status {'APPROVED': 2, 'PROPOSED': 1} | "
            "verdict {'CULL': 2, 'KEEP': 1}\n"
            + "".join(QUERY_LEDGER_LINES[i] + "\n" for i in ("DS-q1", "DS-q2", "F-q3"))))

    def test_query_ledger_filters_by_status_verdict_or_crate(self):
        for value, ids, status, verdict in (
                ("APPROVED", ("DS-q1", "F-q3"), "{'APPROVED': 2}", "{'CULL': 2}"),
                ("KEEP", ("DS-q2",), "{'PROPOSED': 1}", "{'KEEP': 1}"),
                ("alpha", ("DS-q1", "DS-q2"), "{'APPROVED': 1, 'PROPOSED': 1}",
                 "{'CULL': 1, 'KEEP': 1}")):
            with self.subTest(filter=value):
                self.assertQueryOutput(("ledger", value), (
                    f"ledger rows: {len(ids)} | status {status} | verdict {verdict}\n"
                    + "".join(QUERY_LEDGER_LINES[i] + "\n" for i in ids)))

    def test_query_ledger_with_no_ledger_exits_non_zero_naming_the_path(self):
        repo = git_repo(self.work / f"bare-{self._testMethodName}", DEAD_WORKSPACE)
        out = repo / ASSETS
        (out / "health").mkdir(parents=True)
        result = self.query("ledger", out=out)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, f"[health] no ledger at {out / LEDGER}\n")
        self.assertEqual(result.stdout, "")
        self.assertFalse((out / LEDGER).exists())


#: ``ledger assign``'s fixture rows: reassignable (``PROPOSED``, ``APPROVED`` with an open
#: ``CR-OLD`` lineage), not reassignable (``IN_PROGRESS``, ``COMPLETED``), and one not named.
ASSIGN_LEDGER = (
    {"id": "DS-a", "status": "PROPOSED", "verdict": "CULL", "crate": "alpha", "slice": None},
    {"id": "DS-b", "status": "APPROVED", "verdict": "CULL", "crate": "alpha",
     "slice": "CR-OLD",
     "slice_history": [{"cr": "CR-OLD", "assigned": "2026-01-01", "outcome": None}]},
    {"id": "DS-c", "status": "IN_PROGRESS", "verdict": "CULL", "crate": "alpha",
     "slice": "CR-X",
     "slice_history": [{"cr": "CR-X", "assigned": "2026-01-02", "outcome": None}]},
    {"id": "DS-d", "status": "COMPLETED", "verdict": "CULL", "crate": "alpha",
     "slice": "CR-Y", "commit": "abc1234"},
    {"id": "DS-e", "status": "APPROVED", "verdict": "CULL", "crate": "alpha", "slice": None},
)


class _LedgerRepo(_HealthRepo):
    """A fixture repository holding ``LEDGER_FILES`` beside the workspace, an unrelated staged
    edit and an untracked file; no ``cargo``, ``cargo-machete`` or ``dot`` on the ``PATH``."""

    LEDGER_FILES: dict = {}

    def setUp(self):
        files = {**WORKSPACE, "README.md": "fixture\n",
                 **{f"{ASSETS}/{name}": _ledger_text(rows)
                    for name, rows in self.LEDGER_FILES.items()}}
        self.work, self.repo, self.bin_dir, self.cwd = self.build("mdb-health-ledger-", files)
        self.addCleanup(shutil.rmtree, self.work, True)
        self.out = self.repo / ASSETS
        self.today = date.today().isoformat()
        self.prepare_history()
        write_files(self.repo, {"README.md": "edited\n", "notes.txt": "untracked\n"})
        repo_git(self.repo, "add", "README.md")
        self.base = repo_git(self.repo, "rev-parse", "HEAD")
        self.assertNoStandInOnPath(self.bin_dir)

    def prepare_history(self):
        """Commits a subclass adds before the tree is dirtied; none by default."""

    def ledger(self, *args):
        result = run_tool(HEALTH, "ledger", *args, "--project-dir", self.repo, "--out", self.out,
                          bin_dir=self.bin_dir, cwd=self.cwd)
        output = result.stdout + result.stderr
        self.assertNotIn("Traceback", output)
        self.assertEqual(result.returncode, 0, output)
        return result

    def assertCommittedOnly(self, ledger_name, subject):
        """Exactly one new commit, ``subject``, changing ``ledger_name`` alone, authored by the
        fixture identity (AC16); the unrelated staged edit and untracked file stay behind."""
        self.assertEqual(repo_git(self.repo, "rev-parse", "HEAD^"), self.base)
        self.assertEqual(_subject(self.repo), subject)
        self.assertEqual(_commit_files(self.repo), [f"{ASSETS}/{ledger_name}"])
        self.assertEqual(_author(self.repo), FIXTURE_AUTHOR)
        self.assertEqual(repo_git(self.repo, "status", "--porcelain"),
                         "M  README.md\n?? notes.txt")

    def assertNoCommit(self):
        self.assertEqual(repo_git(self.repo, "rev-parse", "HEAD"), self.base)


class LedgerAssignTest(_LedgerRepo):
    """§S3.1 ``ledger assign`` (AC9, AC16)."""

    LEDGER_FILES = {LEDGER: ASSIGN_LEDGER}

    def assign(self, ids, *extra, slice_id="CR-NEW"):
        return self.ledger("assign", "--slice", slice_id, "--ids", ids, *extra)

    def test_only_proposed_and_approved_rows_are_assigned(self):
        result = self.assign("DS-a,DS-b,DS-c,DS-d")
        rows = _read_ledger(self.out / LEDGER)
        self.assertEqual(rows["DS-a"]["slice"], "CR-NEW")
        self.assertEqual(rows["DS-a"]["slice_history"],
                         [{"cr": "CR-NEW", "assigned": self.today, "outcome": None}])
        self.assertEqual(rows["DS-b"]["slice"], "CR-NEW")
        original = {row["id"]: row for row in ASSIGN_LEDGER}
        for fid_ in ("DS-c", "DS-d", "DS-e"):
            self.assertEqual(rows[fid_], original[fid_], f"{fid_} is not assigned")
        self.assertEqual(result.stdout.splitlines()[:3], [
            "[health] warn: DS-c is IN_PROGRESS — not reassignable",
            "[health] warn: DS-d is COMPLETED — not reassignable",
            "[health] ledger assign: 2/4 findings -> slice CR-NEW"])

    def test_a_reassignment_closes_the_old_lineage_entry(self):
        self.assign("DS-b")
        self.assign("DS-b")
        row = _read_ledger(self.out / LEDGER)["DS-b"]
        self.assertEqual(row["slice"], "CR-NEW")
        self.assertEqual(row["slice_history"], [
            {"cr": "CR-OLD", "assigned": "2026-01-01", "outcome": "REASSIGNED",
             "closed": self.today},
            {"cr": "CR-NEW", "assigned": self.today, "outcome": None}],
            "one closed CR-OLD entry, one open CR-NEW entry -- a repeat opens no second")

    def test_unknown_ids_are_reported_sorted(self):
        result = self.assign("DS-zzz,DS-a,DS-yyy")
        self.assertIn("[health] ledger assign: 1/3 findings -> slice CR-NEW "
                      "(UNKNOWN ids: DS-yyy, DS-zzz)", result.stdout.splitlines())
        self.assertEqual(_read_ledger(self.out / LEDGER)["DS-a"]["slice"], "CR-NEW")

    def test_an_assignment_commits_the_ledger_alone(self):
        result = self.assign("DS-a,DS-b")
        self.assertEqual(result.stdout.splitlines(), [
            "[health] ledger assign: 2/2 findings -> slice CR-NEW",
            "[health] ledger committed: chore(ledger): assign 2 finding(s) -> CR-NEW"])
        self.assertCommittedOnly(LEDGER, "chore(ledger): assign 2 finding(s) -> CR-NEW")
        committed = json.loads(repo_git(self.repo, "show", f"HEAD:{ASSETS}/{LEDGER}")
                               .splitlines()[0])
        self.assertEqual(committed["slice"], "CR-NEW")

    def test_no_commit_writes_the_ledger_without_committing(self):
        result = self.assign("DS-a", "--no-commit")
        self.assertNoCommit()
        self.assertNotIn("committed", result.stdout)
        self.assertEqual(_read_ledger(self.out / LEDGER)["DS-a"]["slice"], "CR-NEW")
        self.assertEqual(repo_git(self.repo, "status", "--porcelain", "--", f"{ASSETS}/{LEDGER}"),
                         f"M {ASSETS}/{LEDGER}")

    def test_an_assignment_of_no_finding_commits_nothing(self):
        before = (self.out / LEDGER).read_bytes()
        result = self.assign("DS-zzz")
        self.assertEqual(result.stdout,
                         "[health] ledger assign: 0/1 findings -> slice CR-NEW "
                         "(UNKNOWN ids: DS-zzz)\n")
        self.assertNoCommit()
        self.assertEqual((self.out / LEDGER).read_bytes(), before)

    def test_a_non_cull_domain_assigns_in_its_own_ledger_file(self):
        temporal = "temporal-audit-ledger.jsonl"
        write_files(self.out, {temporal: _ledger_text(ASSIGN_LEDGER[:1])})
        cull = (self.out / LEDGER).read_bytes()
        result = self.ledger("assign", "--domain", "temporal", "--slice", "CR-T",
                             "--ids", "DS-a")
        self.assertEqual(_read_ledger(self.out / temporal)["DS-a"]["slice"], "CR-T")
        self.assertEqual((self.out / LEDGER).read_bytes(), cull, "the cull ledger is untouched")
        self.assertIn("[health] ledger assign: 1/1 findings -> slice CR-T",
                      result.stdout.splitlines())
        self.assertEqual(_subject(self.repo), "chore(ledger): assign 1 finding(s) -> CR-T")
        self.assertEqual(_commit_files(self.repo), [f"{ASSETS}/{temporal}"])


class LedgerAbsentTest(_LedgerRepo):
    """§S3.1 ``ledger assign`` with no ledger (AC9): nothing to do, nothing written."""

    def test_assign_with_no_ledger_reports_it_and_writes_nothing(self):
        result = self.ledger("assign", "--slice", "CR-NEW", "--ids", "DS-a")
        self.assertEqual(result.stdout,
                         f"[health] no ledger at {self.out / LEDGER} — nothing to do\n")
        self.assertFalse((self.out / LEDGER).exists())
        self.assertNoCommit()


#: ``ledger sync``'s fixture rows: four assigned to ``CR-S`` (``PROPOSED`` with an open
#: lineage, a legacy ``APPROVED`` with none, ``IN_PROGRESS``, an already ``COMPLETED`` one),
#: one assigned to ``CR-T``.
SYNC_LEDGER = (
    {"id": "DS-p", "status": "PROPOSED", "verdict": "CULL", "slice": "CR-S",
     "slice_history": [{"cr": "CR-S", "assigned": "2026-01-01", "outcome": None}]},
    {"id": "DS-a", "status": "APPROVED", "verdict": "CULL", "slice": "CR-S",
     "verdict_date": "2026-01-03"},
    {"id": "DS-i", "status": "IN_PROGRESS", "verdict": "CULL", "slice": "CR-S",
     "slice_history": [{"cr": "CR-S", "assigned": "2026-01-02", "outcome": None}]},
    {"id": "DS-c", "status": "COMPLETED", "verdict": "CULL", "slice": "CR-S",
     "commit": "abc1234",
     "slice_history": [{"cr": "CR-S", "assigned": "2026-01-01", "outcome": "COMPLETED",
                        "closed": "2026-01-05"}]},
    {"id": "DS-o", "status": "APPROVED", "verdict": "CULL", "slice": "CR-T"},
)


class LedgerSyncTest(_LedgerRepo):
    """§S3.1 ``ledger sync`` (AC9, AC16): each of the four board states mirrored onto
    ``CR-S``'s rows, and the no-argument sync with no legacy ChangeSet DB.

    The history: ``feature/CR-S`` merged ``--no-ff``, then ``feature/CR-T`` merged, then an
    ordinary commit -- so ``CR-S``'s merge is neither ``HEAD`` nor the latest merge."""

    LEDGER_FILES = {LEDGER: SYNC_LEDGER}

    def prepare_history(self):
        self.merges = {}
        for cr in ("CR-S", "CR-T"):
            repo_git(self.repo, "checkout", "-q", "-b", f"feature/{cr}")
            repo_git(self.repo, "commit", "-q", "--allow-empty", "-m", f"work for {cr}")
            repo_git(self.repo, "checkout", "-q", "main")
            merge = git_merge_no_ff(self.repo, f"feature/{cr}", f"Merge feature/{cr} ({cr})")
            self.merges[cr] = repo_git(self.repo, "rev-parse", "--short", merge)
        repo_git(self.repo, "commit", "-q", "--allow-empty", "-m", "after the merges")

    def setUp(self):
        super().setUp()
        self.original = {row["id"]: row for row in SYNC_LEDGER}

    def sync(self, state, *extra):
        return self.ledger("sync", "--slice", "CR-S", "--db-state", state, *extra)

    def assertUntouched(self, rows, *ids):
        for fid_ in ids:
            self.assertEqual(rows[fid_], self.original[fid_], f"{fid_} is untouched")

    def test_in_progress_moves_the_proposed_and_approved_rows(self):
        result = self.sync("IN_PROGRESS")
        rows = _read_ledger(self.out / LEDGER)
        for fid_ in ("DS-p", "DS-a"):
            self.assertEqual(_fields(rows[fid_], "status", "status_date"),
                             ("IN_PROGRESS", self.today), fid_)
        self.assertEqual(rows["DS-p"].get("slice_history"),
                         self.original["DS-p"]["slice_history"], "no second open entry")
        self.assertEqual(rows["DS-a"].get("slice_history"),
                         [{"cr": "CR-S", "assigned": self.today, "outcome": None}])
        self.assertUntouched(rows, "DS-i", "DS-c", "DS-o")
        self.assertEqual(result.stdout.splitlines()[0],
                         "[health] ledger sync: CR-S -> IN_PROGRESS: 2 row(s) updated")
        self.assertCommittedOnly(LEDGER, "chore(ledger): CR-S -> IN_PROGRESS mirror (2 row(s))")

    def test_completed_records_the_merge_commit_found_from_the_log(self):
        result = self.sync("COMPLETED")
        rows = _read_ledger(self.out / LEDGER)
        for fid_ in ("DS-p", "DS-a", "DS-i"):
            self.assertEqual(_fields(rows[fid_], "status", "status_date", "commit"),
                             ("COMPLETED", self.today, self.merges["CR-S"]), fid_)
        self.assertEqual(rows["DS-p"].get("slice_history"), [
            {"cr": "CR-S", "assigned": "2026-01-01", "outcome": "COMPLETED",
             "closed": self.today}])
        self.assertEqual(rows["DS-a"].get("slice_history"), [
            {"cr": "CR-S", "assigned": "2026-01-03", "outcome": "COMPLETED",
             "closed": self.today}], "a legacy row's lineage is backfilled")
        self.assertUntouched(rows, "DS-c", "DS-o")
        self.assertEqual(result.stdout.splitlines()[0],
                         "[health] ledger sync: CR-S -> COMPLETED: 3 row(s) updated")
        self.assertCommittedOnly(LEDGER, "chore(ledger): CR-S -> COMPLETED mirror (3 row(s))")

    def test_completed_with_a_commit_records_that_commit(self):
        self.sync("COMPLETED", "--commit", "deadbee")
        rows = _read_ledger(self.out / LEDGER)
        self.assertEqual([rows[f].get("commit") for f in ("DS-p", "DS-a", "DS-i", "DS-c")],
                         ["deadbee", "deadbee", "deadbee", "abc1234"])

    def assertReturnedToThePool(self, state):
        result = self.sync(state)
        rows = _read_ledger(self.out / LEDGER)
        for fid_ in ("DS-p", "DS-a", "DS-i"):
            self.assertEqual(_fields(rows[fid_], "status", "slice", "status_date"),
                             ("APPROVED", None, self.today), fid_)
            last = (rows[fid_].get("slice_history") or [{}])[-1]
            self.assertEqual(_fields(last, "outcome", "closed"), (state, self.today), fid_)
        self.assertEqual(len(rows["DS-p"].get("slice_history", [])), 1,
                         "the open entry is closed")
        self.assertUntouched(rows, "DS-c", "DS-o")
        self.assertEqual(result.stdout.splitlines()[0],
                         f"[health] ledger sync: CR-S -> {state}: 3 row(s) updated")
        self.assertCommittedOnly(LEDGER, f"chore(ledger): CR-S -> {state} mirror (3 row(s))")

    def test_aborted_returns_the_unfinished_findings_to_the_approved_pool(self):
        self.assertReturnedToThePool("ABORTED")

    def test_superseded_returns_the_unfinished_findings_to_the_approved_pool(self):
        self.assertReturnedToThePool("SUPERSEDED")

    def test_a_sync_matching_no_row_commits_nothing(self):
        before = (self.out / LEDGER).read_bytes()
        result = self.ledger("sync", "--slice", "CR-NONE", "--db-state", "IN_PROGRESS")
        self.assertEqual(result.stdout,
                         "[health] ledger sync: CR-NONE -> IN_PROGRESS: 0 row(s) updated\n")
        self.assertNoCommit()
        self.assertEqual((self.out / LEDGER).read_bytes(), before)

    def test_the_full_sync_with_no_changeset_db_reports_it_skipped(self):
        before = (self.out / LEDGER).read_bytes()
        result = self.ledger("sync")
        self.assertEqual(result.stdout,
                         "[health] no ChangeSet DB / schedule_db — full sync skipped\n")
        self.assertEqual((self.out / LEDGER).read_bytes(), before)
        self.assertNoCommit()
        self.assertFalse((self.repo / ".wf-schedule.db").exists())


class ToolCommitWithoutGlobalIdentityTest(_HealthRepo):
    """AC16: in a ``git_repo`` repository, a tool's own commit -- the ledger's and a
    snapshot's -- succeeds on a host with no global git identity, as the fixture identity."""

    def setUp(self):
        files = {**DEAD_WORKSPACE,
                 f"{ASSETS}/{LEDGER}": _ledger_text(ASSIGN_LEDGER[:1])}
        self.work, self.repo, self.bin_dir, self.cwd = self.build("mdb-health-identity-", files,
                                                                  dot=True)
        self.addCleanup(shutil.rmtree, self.work, True)
        probe = subprocess.run(["git", "config", "--global", "--get", "user.email"],
                               capture_output=True, text=True, env=tool_env(self.bin_dir),
                               cwd=str(self.cwd), stdin=subprocess.DEVNULL)
        self.assertEqual((probe.returncode, probe.stdout), (1, ""),
                         "the tool run sees no global git identity")
        self.count = _commit_count(self.repo)

    def test_the_ledgers_commit_succeeds_as_the_fixture_identity(self):
        result = run_tool(HEALTH, "ledger", "assign", "--slice", "CR-NEW", "--ids", "DS-a",
                          "--project-dir", self.repo, "--out", self.repo / ASSETS,
                          bin_dir=self.bin_dir, cwd=self.cwd)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "", "no auto-commit warning")
        self.assertEqual(_commit_count(self.repo), self.count + 1)
        self.assertEqual(_subject(self.repo), "chore(ledger): assign 1 finding(s) -> CR-NEW")
        self.assertEqual(_author(self.repo), FIXTURE_AUTHOR)
        self.assertEqual(repo_git(self.repo, "log", "-1", "--format=%cn <%ce>"),
                         FIXTURE_AUTHOR)

    def test_the_snapshots_commit_succeeds_as_the_fixture_identity(self):
        result, name = _take(self.repo, self.bin_dir, self.cwd, "baseline")
        self.assertDotStandInRan(self.work, self.bin_dir, 1)
        self.assertEqual(result.stderr, "", "no auto-commit warning")
        self.assertEqual(_commit_count(self.repo), self.count + 1)
        self.assertEqual(_subject(self.repo), f"docs(health): BASELINE snapshot {name}")
        self.assertEqual(_author(self.repo), FIXTURE_AUTHOR)
        self.assertEqual(repo_git(self.repo, "status", "--porcelain"), "")


# ------------------------------------------------------------------ AC9 / AC15: the paths ----
#
# "The auto-commit staging only the snapshot's paths" (§S3.1), passing "the same way on a host
# with none of ... `dot`" (AC15), and the tool's own directive at the auto-commit -- "snapshot runs
# must not leave the tree dirty" -- make every path a snapshot writes one of the snapshot's
# paths: the svg it never rendered is not one; the living ledger a ``post`` rewrote is one.
# ``query`` with no ledger (§S3.1) holds in a project that has no ``<out>/health/`` either.


class SnapshotWithoutDotTest(_HealthRepo):
    """§S3.1 snapshot (AC9, AC15): with no ``dot`` on the ``PATH`` the crate map is not
    rendered, and a snapshot in a clean repository still commits its paths -- the directory,
    ``health/index.json`` and the living copies it wrote -- leaving the tree clean."""

    @classmethod
    def setUpClass(cls):
        cls.work, cls.repo, cls.bin_dir, cls.cwd = cls.build("mdb-health-nodot-",
                                                              DEAD_WORKSPACE)
        cls.out = cls.repo / ASSETS
        cls.health = cls.out / "health"
        cls.base = repo_git(cls.repo, "rev-parse", "HEAD")
        cls.result = _snapshot(cls.repo, cls.bin_dir, cls.cwd, "baseline")
        cls.added = _health_dirs(cls.health)
        cls.name = cls.added[0] if len(cls.added) == 1 else ""

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.work, True)

    def setUp(self):
        output = self.result.stdout + self.result.stderr
        self.assertNotIn("Traceback", output)
        self.assertEqual(self.result.returncode, 0, output)
        self.assertNoStandInOnPath(self.bin_dir)
        self.assertEqual(len(self.added), 1, f"one snapshot directory:\n{output}")
        self.assertIn("[crate-map] graphviz `dot` not on PATH — skipped render "
                      "(--no-render to silence)", self.result.stdout.splitlines(),
                      "the crate map took its no-dot path")
        self.assertFalse((self.out / "fixture_crate_map.svg").exists(), "no svg rendered")

    def test_the_snapshot_commits_once_and_leaves_the_tree_clean(self):
        subject = f"docs(health): BASELINE snapshot {self.name}"
        self.assertEqual(_commit_count(self.repo), 2,
                         "§S3.1: the snapshot makes exactly one commit; stderr:\n"
                         f"{self.result.stderr}")
        self.assertEqual(repo_git(self.repo, "rev-parse", "HEAD^"), self.base)
        self.assertEqual(_subject(self.repo), subject)
        self.assertIn(f"[health] committed: {subject}", self.result.stdout.splitlines())
        self.assertEqual(self.result.stderr, "", "no auto-commit warning")
        self.assertEqual(repo_git(self.repo, "status", "--porcelain"), "",
                         "snapshot runs must not leave the tree dirty")

    def test_the_commit_holds_exactly_the_paths_the_snapshot_wrote(self):
        snap = self.health / self.name
        expected = sorted([f"{ASSETS}/health/{self.name}/{p.name}" for p in snap.iterdir()]
                          + [f"{ASSETS}/health/index.json"]
                          + [f"{ASSETS}/{n}" for n in LIVING_COPIES
                             if n != "fixture_crate_map.svg"])
        self.assertEqual(_commit_files(self.repo), expected,
                         "§S3.1: the snapshot directory, the index and the living copies it "
                         "wrote -- not the svg it never rendered")


class QueryWithoutHealthDirectoryTest(_HealthRepo):
    """§S3.1 ``query ledger`` with no ledger, and ``query trend`` (AC9), in a project with no
    snapshot and no ledger: ``<out>`` absent, and ``<out>`` present with no ``health/``."""

    LAYOUTS = {
        "no-out": DEAD_WORKSPACE,
        "out-without-health": {**DEAD_WORKSPACE,
                               f"{ASSETS}/crate_map.toml": "# fixture crate-map config\n"},
    }

    def setUp(self):
        self.work, _, self.bin_dir, self.cwd = self.build("mdb-health-nohealth-", {})
        self.addCleanup(shutil.rmtree, self.work, True)
        self.assertNoStandInOnPath(self.bin_dir)

    def projects(self):
        """Yield ``(layout, repo, out)`` for each layout, ``<out>/health/`` absent in each."""
        for layout, files in self.LAYOUTS.items():
            repo = git_repo(self.work / layout, files)
            out = repo / ASSETS
            if (out / "health").exists():
                raise AssertionError(f"fixture: {layout} has no health directory")
            yield layout, repo, out

    def query(self, repo, out, *args):
        return run_tool(HEALTH, "query", *args, "--project-dir", repo, "--out", out,
                        bin_dir=self.bin_dir, cwd=self.cwd)

    def test_query_ledger_reports_no_ledger_without_a_traceback(self):
        for layout, repo, out in self.projects():
            with self.subTest(layout=layout):
                result = self.query(repo, out, "ledger")
                self.assertNotIn("Traceback", result.stdout + result.stderr)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(result.stderr, f"[health] no ledger at {out / LEDGER}\n")
                self.assertEqual(result.stdout, "")
                self.assertFalse((out / LEDGER).exists())

    def test_query_trend_exits_zero_without_a_traceback(self):
        for layout, repo, out in self.projects():
            with self.subTest(layout=layout):
                result = self.query(repo, out, "trend")
                self.assertNotIn("Traceback", result.stdout + result.stderr)
                self.assertEqual(result.returncode, 0, result.stderr)


class SnapshotPostLedgerCommitTest(_HealthRepo):
    """§S3.1 snapshot (AC9): a ``post`` snapshot that rewrites the living ledger -- its
    ratification verdicts -- commits that ledger with the snapshot, leaving the tree clean.

    ``pre CR-7``, then a committed ledger with two COMPLETED ``CR-7`` rows (one still live,
    one gone), then ``post CR-7``."""

    @classmethod
    def setUpClass(cls):
        cls.work, cls.repo, cls.bin_dir, cls.cwd = cls.build("mdb-health-postledger-",
                                                              DEAD_WORKSPACE, dot=True)
        cls.out = cls.repo / ASSETS
        cls.health = cls.out / "health"
        _, cls.pre = _take(cls.repo, cls.bin_dir, cls.cwd, "pre", "--slice", "CR-7")
        report = json.loads((cls.health / cls.pre / "dead_scan_report.json")
                            .read_text(encoding="utf-8"))
        live = [f["id"] for f in report["inventory"] if f["item"] == "fn unused"]
        if len(live) != 1:
            raise AssertionError(f"fixture: one live `fn unused` finding, got {live}")
        cls.live = live[0]
        cls.ledger_before = _ledger_text([
            {"id": cls.live, "status": "COMPLETED", "verdict": "CULL", "crate": "alpha",
             "slice": "CR-7", "source": "scan", "item": "fn unused"},
            {"id": "DS-0000000000", "status": "COMPLETED", "verdict": "CULL",
             "crate": "alpha", "slice": "CR-7", "source": "scan", "item": "fn gone"},
        ])
        write_files(cls.out, {LEDGER: cls.ledger_before})
        cls.base = git_commit_all(cls.repo, "ledger")
        status = repo_git(cls.repo, "status", "--porcelain")
        if status:
            raise AssertionError(f"fixture: a clean tree before the post, got {status!r}")
        cls.result, cls.post = _take(cls.repo, cls.bin_dir, cls.cwd, "post", "--slice", "CR-7")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.work, True)

    def setUp(self):
        output = self.result.stdout + self.result.stderr
        self.assertNotIn("Traceback", output)
        self.assertEqual(self.result.returncode, 0, output)
        self.assertDotStandInRan(self.work, self.bin_dir, 2)
        rows = _read_ledger(self.out / LEDGER)
        self.assertEqual([rows[f].get("ratified") for f in (self.live, "DS-0000000000")],
                         ["NOT-RATIFIED", "RATIFIED"], "the post rewrote the living ledger")
        self.assertNotEqual((self.out / LEDGER).read_text(encoding="utf-8"), self.ledger_before)

    def test_the_post_snapshots_commit_includes_the_rewritten_ledger(self):
        self.assertEqual(repo_git(self.repo, "rev-parse", "HEAD^"), self.base,
                         "exactly one commit for the post snapshot")
        self.assertEqual(_subject(self.repo), f"docs(health): POST snapshot {self.post}")
        committed = _commit_files(self.repo)
        self.assertIn(f"{ASSETS}/{LEDGER}", committed,
                      "§S3.1: the living ledger the post rewrote is one of its paths")
        self.assertEqual(repo_git(self.repo, "show", f"HEAD:{ASSETS}/{LEDGER}") + "\n",
                         (self.out / LEDGER).read_text(encoding="utf-8"),
                         "the committed ledger carries the ratification verdicts")
        snap_rel = f"{ASSETS}/health/{self.post}"
        allowed = {f"{ASSETS}/health/index.json", f"{ASSETS}/{LEDGER}",
                   *(f"{ASSETS}/{n}" for n in LIVING_COPIES)}
        self.assertEqual([p for p in committed if not p.startswith(snap_rel + "/")
                          and p not in allowed], [],
                         "nothing outside the snapshot's paths is committed")

    def test_the_post_snapshot_leaves_the_tree_clean(self):
        self.assertEqual(repo_git(self.repo, "status", "--porcelain"), "",
                         "snapshot runs must not leave the tree dirty")


if __name__ == "__main__":
    unittest.main()
