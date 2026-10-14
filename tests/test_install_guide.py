"""Gates for the install guide as the single source of install text:
``docs/install-guide.md``, the repo ``README.md`` pointing at it, the
git-workflow skill's release steps, and the Pi package README's source.

Every term the guide must cover is DERIVED from the code, never hand-copied,
so a rename in the code fails the gate instead of letting it pass silently:

- install outcomes: every string literal passed to ``_emit_install_envelope``
  in ``modelb_axi/cli.py`` (found by AST);
- flags: checked present in ``modelb_axi.cli._build_parser()``;
- stacks: ``modelb_axi.scaffold.KNOWN_STACKS``;
- prerequisites / warnings: ``modelb_axi.requirements.REQUIREMENTS``;
- toolchain installers: ``modelb_axi.requirements.STACK_TOOLCHAINS``;
- pre-flight line prefixes: parsed from a real sandboxed installer run's
  stderr (``<prefix>: k=v ...`` lines);
- verdicts: ``capabilities.DETECTED/ABSENT/UNKNOWN`` + ``toolchains.INSTALLED``;
- the permission-policy directory: ``permission_policy.POLICY_RELPATH``.

Design (proposed at RED, approved by the orchestrator):

(A) The guide carries one exact ``## `` heading per install topic
    (:data:`SECTIONS`); each topic's terms are checked inside its own section
    (heading to the next ``## ``). A term counts only inside an inline code
    span or a fenced block, as a whole token.
(C) Marked regions: ``<!-- install-guide:begin <name> -->`` ...
    ``<!-- install-guide:end <name> -->`` on their own lines, kebab-case
    names, unique, non-empty, never nested; every install topic sits wholly
    inside a region; the ``## Marked regions`` section (which documents the
    convention, showing both markers in code spans) sits outside every region.
(D) No internal vocabulary anywhere in the guide: no ``§``, no CR ids, no
    ``D<n>``/``PRD``/``DN-`` references, and none of :data:`BLOCKED_WORDS`
    (case-sensitive, whole word).
(E) README: <= 20 non-blank lines, a ``# `` title then a description
    paragraph, a markdown link to ``docs/install-guide.md``, and no line or
    inline code span beginning with an installer command.
(F) git-workflow ``## Releases`` (MIGRATED at CR-MDB-058 C3 RED, §S6) carries
    the release steps of :data:`RELEASE_STEP_PHRASES`, each stated in ONE unit
    of the section: the release notes link to the install guide, its marked
    regions feed generated surfaces such as a package README, and a
    documentation review; the release-notes step (move ``[Unreleased]`` under
    ``## [X.Y.Z] - YYYY-MM-DD`` or write it from ``history`` and ``landings``,
    an ``### Upgrading`` note first, update the compare links, commit); a
    fenced release-job snippet passing the tag's section as ``--notes-file``
    (literal match, failing on a missing or empty section); and the packaging
    entries of the six stacks. It no longer says to copy the marked regions
    into the release notes (was: "copying the guide's marked regions verbatim
    into the release notes; a documentation review"). CR-MDB-029 ``### §S1`` names the guide's marked regions as the
    Pi package README's source. CR-MDB-038 §S5: ``## Releases`` also names
    the four Python release steps in order (single-source version + ``uv
    build``; the rehearsal, each release-branch push uploading the stamped dev
    version to TestPyPI through Trusted Publishing; the PyPI upload after
    ``git flow release finish`` through Trusted Publishing, with no token
    anywhere; the post-release maintenance) and names no one project.
    MIGRATED at CR-MDB-067 C3 RED (§S5; was: "TestPyPI rehearsal into an
    isolated tool directory; PyPI upload after ``git flow release finish``
    with a token the user supplies"). CR-MDB-067 §S5 adds: the branch is
    published (``git flow release publish``, ``git flow hotfix publish``),
    every push of it is the rehearsal and ``finish`` deletes the remote branch
    (:data:`PUBLISH_STEP_PHRASES`); the release-notes step is written before
    the branch is first published (was: before ``git flow release finish``);
    a ``### Rehearsal and CI`` subsection after ``### Pi package releases``
    carries the rehearsal rule, the forms table and the CI rule
    (:data:`REHEARSAL_AND_CI_PHRASES`) and names none of the Python or Pi
    steps' anchors; and no phrase of :data:`RETIRED_RELEASE_PHRASES` appears
    anywhere in ``## Releases``.
    MIGRATED at CR-MDB-070 C2 RED (§S6): the CI rule is the release
    workflow's test job, run in every run (each release or hotfix push, each
    ``master`` push, each published release), which every publish job, the
    rehearsal included, needs because a dependency gates only within one run
    (was: "a CI workflow runs the suite on every push to develop, release and
    hotfix branches and on pull requests"); in ``### Rehearsal and CI`` every
    clause naming ``develop`` or pull requests is negated, and one unit says
    there is no CI on them (:func:`excluded_ref_faults`). The release-job
    snippet checks out with full history, takes the tag from ``git tag
    --points-at HEAD`` filtered to ``X.Y.Z`` (none: exit 0, nothing to
    release), sits in a job that needs the test job and runs on the ``master``
    push, and ``github.ref_name`` is named nowhere in ``## Releases``
    (:data:`SNIPPET_ELEMENTS`). The release flow is one ``git push origin
    master develop --tags``: the ``master`` push runs the tests and creates the
    release, the release event publishes, and a ``master`` run reporting no
    version tag at ``HEAD`` is recovered by dispatching the workflow on
    ``master`` (:data:`RELEASE_FLOW_PHRASES`).
    MIGRATED at CR-MDB-070 C4 RED (VERIFY F1/F2/F3/F6): the snippet refuses
    more than one version tag at ``HEAD``, naming them (a
    :data:`SNIPPET_ELEMENTS` entry; its ``run:`` lines are EXECUTED by
    ``tests.test_release_rehearsal.SkillReleaseSnippetExecutionTest``); its
    ``actions/checkout`` line, or the comment beside it, says to pin it to a
    full commit SHA (:func:`checkout_pin_faults`); ``## Releases`` no longer
    says "the tag's release job" (:data:`RETIRED_RELEASE_PHRASES`), and the
    Python and Pi publish steps say the release event's publish job publishes
    after the tests and the ref guard (:func:`publish_job_faults`); the push
    paragraph says a red ``master`` or release run publishes nothing, to
    re-run the failed jobs, and that a real failure is fixed on a hotfix
    branch (:data:`RED_RUN_RECOVERY_PHRASES`).

Orchestrator rulings (2026-09-24, on the RED design):

- Warnings: AT-LEAST-ONE — for each requirement row, one line of the
  warnings section names the row's id (in a code span) AND at least one of
  its asset families. Whether the prose states consequences well is the
  release documentation review's judgement, not a gate's.
- Install offers: ``pi install``, ``--yes``, and ANY ONE toolchain-installer
  term (a ``STACK_TOOLCHAINS`` probe with an installer, by name or command)
  — no per-toolchain enumeration.
- Blocklist approved as listed; derived required terms were checked for
  collisions with it (none collide, so no code-span exemption exists).

Stdlib only.
"""

import argparse
import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from functools import lru_cache
from pathlib import Path

from modelb_axi.requirements import (
    ELEVATED,
    PER_PROJECT,
    PYTHON_VENV_ROUTE,
    STACK_TOOLCHAINS,
    install_display,
)
from modelb_axi.requirements import requirement as _requirement
from tests._helpers import requirements_rows as _requirements
from tests._helpers import write_interpreter_fixture
from tests.test_board_holds_the_queue import _CLAUSE_SPLIT, NEGATION, norm_units
from tests.test_bootstrap_shutdown_registry import normalise

REPO_ROOT = Path(__file__).resolve().parent.parent
GUIDE = REPO_ROOT / "docs" / "install-guide.md"
README = REPO_ROOT / "README.md"
GIT_WORKFLOW_SKILL = REPO_ROOT / "skills-src" / "git-workflow" / "SKILL.md"
CR_029 = REPO_ROOT / "docs" / "changes" / "CR-MDB-029-pi-package.md"
CLI_SOURCE = REPO_ROOT / "modelb_axi" / "cli.py"
GUIDE_LINK_TARGET = "docs/install-guide.md"

# (A) — one exact heading per install topic, in guide order.
PREREQUISITES = "Prerequisites"
STACKS = "Choosing stacks"
PREFLIGHT = "Reading the pre-flight"
WARNINGS = "Warnings: what stops working"
OFFERS = "Install offers"
MISSING = "Missing capabilities"
OUTCOMES = "Install outcomes"
REAL_HOME = "Installing into your home directory"
WIDENING = "Adding stacks later"
TRUST = "Project trust"
MARKED = "Marked regions"
INSTALL_TOPICS = (
    PREREQUISITES, STACKS, PREFLIGHT, WARNINGS, OFFERS, MISSING, OUTCOMES,
    REAL_HOME, WIDENING, TRUST,
)
SECTIONS = INSTALL_TOPICS + (MARKED,)

# (C)
MARKER_PREFIX = "<!-- install-guide:"
_NAME = r"[a-z0-9]+(?:-[a-z0-9]+)*"
BEGIN_RE = re.compile(rf"^<!-- install-guide:begin ({_NAME}) -->$")
END_RE = re.compile(rf"^<!-- install-guide:end ({_NAME}) -->$")

# (D)
BLOCKED_WORDS = (
    "RED", "GREEN", "VERIFY", "FIX", "Mainline", "vidushi", "MDB",
    "orchestrator", "wave", "cycle", "gap-analysis", "tier-1", "tier-2",
    "tier-3", "tier 1", "tier 2", "tier 3", "REQUIREMENTS", "asset_families",
    "user ruling", "dog-food",
)
BLOCKED_PATTERNS = (
    ("section sign", re.compile("§")),
    ("CR id", re.compile(r"\bCR-[A-Z]{2,5}-\d{3}\b")),
    ("decision id", re.compile(r"(?<![\w-])D\d{1,2}(?![\w-])")),
    ("PRD reference", re.compile(r"(?<![\w-])PRD(?![\w-])")),
    ("design-note reference", re.compile(r"(?<![\w-])DN-")),
)

# (E)
README_MAX_NONBLANK_LINES = 20
INSTALLER_COMMAND_PREFIXES = ("modelb-axi", "uv tool install", "pip install", "pi install")

# (F)
#: The ``## Releases`` steps, each ``(group, label, regexes)``: ONE normalised unit of the
#: section (a paragraph, a list item with its continuation lines, a table row or a fenced-code
#: line, as :func:`tests.test_board_holds_the_queue.norm_units` splits them) matches every regex
#: of a step. Backticks and ``*`` are dropped and the text lower-cased before matching.
#: MIGRATED at CR-MDB-058 C3 RED (§S6): the copy step is retired — release notes link
#: to the install guide, and the marked regions feed generated surfaces such as a package README;
#: the documentation review stays; the release-notes step, the release-job snippet and the
#: packaging entries of the six stacks join it (was the flat phrases "install guide",
#: "marked region", "verbatim", "release notes", "documentation review").
DOCUMENTATION_STEPS = "documentation steps"
RELEASE_NOTES_STEP = "release-notes step"
RELEASE_JOB_SNIPPET = "release-job snippet"
PACKAGING_ENTRIES = "packaging entries"
RETIRED_COPY_STEP = "retired copy step"
#: A failure word, for the snippet's missing and empty sections.
_FAILS = r"\b(?:fail\w*|exit\w*|error\w*|refus\w*|abort\w*|stop\w*)\b"
#: §S6 — the stacks whose packaging entry is the release body only.
RELEASE_BODY_ONLY_STACKS = ("arduino", "quarkus", "java", "rust")
RELEASE_STEP_PHRASES = (
    (DOCUMENTATION_STEPS, "release notes link to the install guide",
     (r"\brelease notes\b", r"\blink(?:s|ed|ing)?\b", r"\binstall guide\b")),
    (DOCUMENTATION_STEPS, "the marked regions feed generated surfaces such as a package README",
     (r"\bmarked regions?\b", r"\b(?:feed\w*|generat\w*)\b", r"\breadme\b")),
    (DOCUMENTATION_STEPS, "a documentation review", (r"\bdocumentation review\b",)),
    (RELEASE_NOTES_STEP, "move [Unreleased] under ## [X.Y.Z] - YYYY-MM-DD",
     (r"\bmov(?:e|es|ed|ing)\b", r"\[unreleased\]", r"## \[x\.y\.z\] - yyyy-mm-dd")),
    (RELEASE_NOTES_STEP, "or write it from the release's CRs (history and landings)",
     (r"(?<![\w-])history(?![\w-])", r"(?<![\w-])landings(?![\w-])")),
    (RELEASE_NOTES_STEP, "an ### Upgrading note first when an operator must act",
     (r"### upgrading\b", r"\bfirst\b", r"\boperators?\b")),
    (RELEASE_NOTES_STEP, "update the compare links",
     (r"\bupdat(?:e|es|ed|ing)\b", r"\bcompare links?\b")),
    (RELEASE_NOTES_STEP, "commit",
     (r"\bcommit(?:s|ted|ting)?\b",
      r"changelog|\bsection\b|\bcompare links?\b|\[unreleased\]|\brelease notes\b")),
    (RELEASE_JOB_SNIPPET, "the tag's section is matched literally",
     (r"\bliteral(?:ly)?\b|\bexact(?:ly)?\b", r"\bmatch\w*\b", r"\b(?:section|tag|heading|label)\b")),
    (RELEASE_JOB_SNIPPET, "it fails on a missing section",
     (_FAILS, r"\bmissing\b|\babsent\b", r"\b(?:section|tag)\b")),
    (RELEASE_JOB_SNIPPET, "it fails on an empty section",
     (_FAILS, r"\bempty\b", r"\bsection\b")),
    (PACKAGING_ENTRIES, "python: [project.urls] Changelog and Release Notes",
     (r"(?<![\w-])python(?![\w-])", r"\[project\.urls\]", r"\bchangelog\b",
      r"\brelease notes\b")),
    (PACKAGING_ENTRIES, "bun: CHANGELOG.md in package.json files, copied into the package "
     "directory at publish time when the package is not at the repository root",
     (r"(?<![\w-])bun(?![\w-])", r"package\.json", r"\bfiles\b", r"changelog\.md",
      r"\bcop(?:y|ies|ied|ying)\b", r"\bpublish\w*\b", r"\broot\b")),
    *((PACKAGING_ENTRIES, f"{stack}: the release body only",
       (rf"(?<![\w-]){stack}(?![\w-])", r"\brelease body\b", r"\bonly\b"))
      for stack in RELEASE_BODY_ONLY_STACKS),
)
#: §S6 — the retired copy step: "Install text from its single source … copy those
#: marked regions verbatim into the release notes" (normalised, whole section). A copy the
#: text forbids ("never copy", "not copy") is not the step.
RETIRED_COPY_STEP_RE = re.compile(
    r"\binstall text from its single source\b"
    r"|(?<!never )(?<!not )\bcop(?:y|ies)\b[^.;]{0,120}\binto (?:the |its )?release notes\b")
#: §S6 — the snippet's fenced block: a create-release step passing the section as a file.
SNIPPET_TERMS = ("gh release create", "--notes-file", "changelog.md")
#: CR-MDB-070 §S6 — what the snippet's block (the first fenced block of ``## Releases`` holding
#: every :data:`SNIPPET_TERMS`) must also carry, each ``(fault, regexes)``: every regex matches the
#: block, lower-cased, line-anchored (``re.M``). The job may be the block's own YAML keys (``needs:
#: test``, ``github.ref == 'refs/heads/master'``) or a comment naming them. Checked only when a
#: block holds every :data:`SNIPPET_TERMS`; otherwise the one "no fenced create-release step" fault
#: stands alone.
SNIPPET_ELEMENTS = (
    ("does not check out with full history (fetch-depth: 0)", (r"fetch-depth:\s*0\b",)),
    ("does not take the tag from git tag --points-at HEAD filtered to X.Y.Z",
     (r"\bgit tag --points-at head\b", r"\[0-9\]\+\\\.\[0-9\]\+\\\.\[0-9\]\+")),
    ("does not exit 0 with nothing to release when no version tag is at HEAD",
     (r"\bexit 0\b", r"\bnothing to release\b")),
    ("does not sit in a job that needs the test job",
     (r"^\s*needs:\s*\[?\s*test\b|\bneeds the test job\b",)),
    ("does not run on the master push",
     (r"refs/heads/master\b|\bmaster push\b|\bpush(?:es)? to master\b",)),
    # MIGRATED at CR-MDB-070 C4 RED (VERIFY F1): the snippet counts the tags at HEAD and refuses
    # more than one, naming them (was: two tags made ``tag`` multi-line and the step failed with
    # a misleading "no CHANGELOG.md section for 1.0.0\n1.0.1").
    ("does not refuse more than one version tag at HEAD",
     (r"\bmore than one version tag\b",)),
)
#: CR-MDB-070 C4 RED (VERIFY F2) — the snippet's ``uses: actions/checkout@…`` line, or a comment
#: line directly above or below it, says to pin the action to a full commit SHA: both regexes match
#: that line and its adjacent comment lines, lower-cased.
CHECKOUT_USES_RE = re.compile(r"^\s*(?:-\s+)?uses:\s*actions/checkout@")
CHECKOUT_PIN_TERMS = (r"\bpin", r"\bsha\b")
CHECKOUT_PIN_FAULT = "the snippet's checkout does not say to pin it to a full commit SHA"
#: CR-MDB-070 C4 RED (VERIFY F6) — recovery from a red or flaky run, in the push paragraph (the
#: unit holding ``git push origin master develop --tags``): when the ``master`` run or the release
#: run fails its tests, nothing publishes; re-run the failed jobs, and a real failure is fixed on a
#: hotfix branch. Matched as :data:`RELEASE_STEP_PHRASES` (one normalised unit).
RED_RUN_RECOVERY = "red run recovery"
RED_RUN_RECOVERY_PHRASES = (
    (RED_RUN_RECOVERY, "the push paragraph says a red master or release run publishes nothing: "
     "re-run the failed jobs, fix a real failure on a hotfix branch",
     (r"\bgit push origin master develop --tags\b", r"\bnothing publishes\b",
      r"\bre-run the failed jobs\b", r"(?<![\w-])hotfix(?![\w-])")),
)
#: CR-MDB-070 C4 RED (VERIFY F3) — the Python and Pi publish steps: the unit holding the step's
#: anchor (``no token anywhere``, ``npm publish``) says the release event's publish job publishes,
#: after the tests and the ref guard, and keeps the step's existing terms. Each
#: ``(label, anchor, terms)``; substrings of the normalised unit.
PUBLISH_JOB_TERMS = ("release event", "ref guard", "after the tests")
PUBLISH_JOB_STEPS = (
    ("pypi upload", "no token anywhere",
     ("trusted publishing", "git flow release finish", *PUBLISH_JOB_TERMS)),
    ("npm publish", "npm publish", ("trusted publishing", *PUBLISH_JOB_TERMS)),
)
#: CR-MDB-070 §S6 — the tag never comes from the pushed ref: neither ``github.ref_name`` nor
#: ``GITHUB_REF_NAME`` anywhere in ``## Releases`` (lower-cased).
REF_NAME_RE = re.compile(r"github[._]ref_name")
#: CR-MDB-070 §S6 — the release flow, each step matched in ONE normalised unit of ``## Releases``
#: (as :data:`RELEASE_STEP_PHRASES`).
RELEASE_FLOW = "release flow"
RELEASE_FLOW_PHRASES = (
    (RELEASE_FLOW, "one git push origin master develop --tags",
     (r"\b(?:one|a single)\b[^.;]{0,20}\bgit push origin master develop --tags\b",)),
    (RELEASE_FLOW, "the master push runs the tests and creates the release",
     (r"\bmaster push\b|\bpush(?:es)? (?:to|of) master\b", r"\btests?\b",
      r"\bcreates? the release\b")),
    (RELEASE_FLOW, "the release event publishes",
     (r"\brelease event\b", r"\bpublish(?:es)?\b")),
    (RELEASE_FLOW, "if the master run reports no version tag at HEAD, dispatch the workflow on "
     "master",
     (r"\bmaster run\b", r"\bno version tag\b", r"(?<![\w-])head(?![\w-])", r"\bdispatch\w*\b",
      r"\bon master\b")),
)
CR_029_S1_TERMS = ("install-guide.md", "marked region", "README")
#: CR-MDB-038 §S5 — the four Python release steps, in ritual order. Each
#: step is (label, anchor alternatives, further required terms); a term is an
#: alternatives tuple, matched case-insensitively on whitespace-normalised
#: ``## Releases`` text. The first anchor found of each step must appear in
#: step order (build, rehearse, upload, maintain).
#: MIGRATED at CR-MDB-067 C3 RED (§S5): the rehearsal is each release-branch push uploading
#: the stamped dev version to TestPyPI through Trusted Publishing, and the upload is the tag's
#: release job after ``git flow release finish``, with no token anywhere (was: rehearse terms
#: "isolated tool directory"; upload anchors "token the user supplies", "user-supplied token").
#: Build and post-release maintenance are unchanged.
PYTHON_RELEASE_STEPS = (
    ("build", ("uv build",), (("version in its single source",),)),
    ("testpypi rehearsal", ("testpypi",),
     (("each release-branch push",), ("stamped dev version",), ("trusted publishing",))),
    ("pypi upload", ("no token anywhere",),
     (("git flow release finish",),)),
    ("post-release maintenance", ("--reinstall",),
     (("from pypi",), ("global permission config",), ("per-project",),
      ("trusted project",), ("without a permission prompt",))),
)
#: The skill is used across projects: its release steps name no one project.
PROJECT_SPECIFIC_NAMES = ("modelb", "model b", "model-b")
#: CR-MDB-029 §S4 — the Pi package release step, same shape as
#: PYTHON_RELEASE_STEPS: after the version is set, npm publish with credentials
#: the user supplies at publish time; then install the published version into
#: an isolated Pi agent directory (``PI_CODING_AGENT_DIR``) and confirm the
#: extension loads. The publish anchor must precede the isolated-install one.
#: Amended at C5 (VERIFY finding 3): a scoped package publishes with
#: ``--access public``, and the post-release maintenance gains the live check
#: (the watcher started in the real Pi configuration; a Sandesh message wakes
#: the session), anchored on "live check" after the isolated install.
#: MIGRATED at CR-MDB-047 C4 FIX (VERIFY F5, spec §S3 amended at 5dd8a36):
#: the package carries only the worktree extension, so the live check confirms
#: Pi loads the worktree extension, and the section names no watcher (was:
#: "watcher", "sandesh message", "wakes the session").
#: MIGRATED at CR-MDB-067 C3 RED (§S5): the tag's release job publishes through Trusted
#: Publishing; a new package's first publish uses a one-time token kept as a repository
#: secret, then 2FA is required and the token deleted (was: "credentials the user supplies" /
#: "user-supplied credentials" and "at publish time").
PI_PACKAGE_RELEASE_STEPS = (
    ("npm publish", ("npm publish",),
     (("pi package",), ("version is set",), ("trusted publishing",),
      ("repository secret",), ("2fa",), ("--access public",))),
    ("isolated pi install", ("pi_coding_agent_dir",),
     (("pi install",), ("published version",), ("extension loads",))),
    ("live check", ("live check",),
     (("real pi configuration",), ("loads the worktree extension",))),
)
#: The retired Model B watcher, named nowhere in the Pi package's steps.
PI_PACKAGE_RETIRED_TERM = "watcher"
#: The Pi step names no project, and not the npm scope of any one project.
PI_PROJECT_SPECIFIC_NAMES = PROJECT_SPECIFIC_NAMES + ("anthill-tec",)

# CR-MDB-067 §S5 — the release flow publishes the branch, writes the notes before the first
# publish, and carries a ``### Rehearsal and CI`` subsection; the manual-rehearsal and
# user-supplied-credential phrasing is retired. Steps are matched like
# :data:`RELEASE_STEP_PHRASES`: ONE normalised unit matches every regex of a step.
PUBLISH_STEP = "publish step"
NOTES_BEFORE_PUBLISH = "notes before the first publish"
REHEARSAL_AND_CI = "rehearsal and ci"
RETIRED_PHRASES = "retired phrases"
#: §S5 "Publishing the branch" — matched in any unit of ``## Releases``.
PUBLISH_STEP_PHRASES = (
    (PUBLISH_STEP, "the release branch is published with git flow release publish",
     (r"git flow release publish\b",)),
    (PUBLISH_STEP, "a hotfix branch is published with git flow hotfix publish",
     (r"git flow hotfix publish\b",)),
    (PUBLISH_STEP, "every push of the branch is the rehearsal",
     (r"\b(?:every|each)\b", r"\bpush(?:es)?\b", r"\b(?:is|are) the rehearsal\b")),
    (PUBLISH_STEP, "finish deletes the remote branch",
     (r"(?<![\w-])finish(?:es)?(?![\w-])", r"\bdelet(?:e|es|ed|ing)\b", r"\bremote\b",
      r"\bbranch\b")),
)
#: §S5 — the release-notes step is written before the branch is first published (it was
#: "before ``git flow release finish``"); matched in a unit of the ``### Release notes``
#: subsection (its heading title starts with :data:`RELEASE_NOTES_SUBSECTION`).
RELEASE_NOTES_SUBSECTION = "Release notes"
NOTES_BEFORE_PUBLISH_PHRASE = (
    NOTES_BEFORE_PUBLISH, "the release notes are written before the branch is first published",
    (r"\bbefore\b[^.;]{0,40}\bfirst publish(?:ed|es)?\b",))
#: §S5 — the subsection's exact heading title, and the heading it must follow.
REHEARSAL_AND_CI_HEADING = "Rehearsal and CI"
PI_PACKAGE_HEADING = "Pi package releases"
#: §S5's forms table — the stacks whose rehearsal is the notes check only.
NOTES_CHECK_ONLY_STACKS = ("arduino", "quarkus", "java", "rust")
#: §S5 — the rehearsal rule, the forms table and the CI rule, each step matched in one unit of
#: the ``### Rehearsal and CI`` subsection.
REHEARSAL_AND_CI_PHRASES = (
    (REHEARSAL_AND_CI, "rehearsal rule: each push to release/X.Y.Z or hotfix/X.Y.Z",
     (r"\b(?:each|every)\b", r"\bpush(?:es)?\b", r"(?<![\w-])release/x\.y\.z\b",
      r"(?<![\w-])hotfix/x\.y\.z\b")),
    (REHEARSAL_AND_CI, "rehearsal rule: builds X.Y.Z with a dev marker and the CI run number in "
     "the stack's form",
     (r"\bbuild\w*\b", r"\bdev marker\b", r"(?<![\w-])ci(?![\w-])", r"\brun number\b",
      r"\bforms?\b")),
    (REHEARSAL_AND_CI, "rehearsal rule: refuses a committed version other than X.Y.Z",
     (r"\brefus\w*\b", r"\bcommitted version\b", r"\bother than\b")),
    (REHEARSAL_AND_CI, "rehearsal rule: fails on a missing or empty notes section",
     (r"\bfail\w*\b", r"\bmissing\b", r"\bempty\b", r"\bnotes\b")),
    (REHEARSAL_AND_CI, "forms table: python, X.Y.Z.devN, the upload to the test index",
     (r"(?<![\w-])python(?![\w-])", r"(?<![\w.])x\.y\.z\.devn\b", r"\bupload\b",
      r"\btest index\b")),
    (REHEARSAL_AND_CI, "forms table: bun, X.Y.Z-dev.N, the package manager's dry-run publish "
     "with a dist-tag",
     (r"(?<![\w-])bun(?![\w-])", r"(?<![\w.])x\.y\.z-dev\.n\b", r"\bdry-run\b",
      r"\bpublish\b", r"\bdist-tag\b")),
    *((REHEARSAL_AND_CI, f"forms table: {stack}, the notes check only",
       (rf"(?<![\w-]){stack}(?![\w-])", r"\bnotes check only\b"))
      for stack in NOTES_CHECK_ONLY_STACKS),
    # MIGRATED at CR-MDB-070 C2 RED (§S6): the CI rule is the release workflow's test job, run in
    # every run, which every publish job needs (was the one step "CI rule: a CI workflow runs the
    # suite on every push to develop, release and hotfix branches and on pull requests"). That
    # develop and pull requests run no CI is the negation-aware excluded_ref_faults, not a step.
    (REHEARSAL_AND_CI, "CI rule: the release workflow's test job runs the suite in every run",
     (r"\brelease workflow\b", r"\btest job\b", r"\bsuite\b", r"\bevery run\b")),
    (REHEARSAL_AND_CI, "CI rule: each push to a release or hotfix branch",
     (r"\b(?:each|every)\b", r"\bpush(?:es)?\b", r"\brelease (?:or|and) hotfix\b")),
    (REHEARSAL_AND_CI, "CI rule: each push to master",
     (r"\b(?:each|every) push(?:es)? to master\b|\b(?:each|every) master push(?:es)?\b",)),
    (REHEARSAL_AND_CI, "CI rule: each published release",
     (r"\b(?:each|every) published release\b",)),
    (REHEARSAL_AND_CI, "CI rule: on the stack's floor interpreter", (r"\bfloor interpreter\b",)),
    (REHEARSAL_AND_CI, "CI rule: in a clean home", (r"\bclean home\b",)),
    (REHEARSAL_AND_CI, "CI rule: with full history", (r"\bfull history\b",)),
    (REHEARSAL_AND_CI, "CI rule: it runs outside any agent session",
     (r"\boutside (?:of )?(?:any |an |every )?agent sessions?\b",)),
    (REHEARSAL_AND_CI, "CI rule: the one place the suite runs without the stack's Crucible "
     "client",
     (r"\bsuite\b", r"\bwithout\b", r"\bcrucible client\b")),
    (REHEARSAL_AND_CI, "CI rule: every publish job, the rehearsal included, needs the test job",
     (r"\b(?:every|each|all) publish(?:es|ing)? jobs?\b", r"\brehearsal\b", r"\bneeds?\b",
      r"\btest(?:s| job)\b")),
    (REHEARSAL_AND_CI, "CI rule: because a dependency gates only within one run",
     (r"\bdependenc(?:y|ies)\b", r"\bgat(?:e|es|ed|ing)\b",
      r"\bwithin (?:one|a single|the same) run\b")),
)
#: CR-MDB-070 §S6 — the refs the CI rule excludes. In ``### Rehearsal and CI`` every clause
#: (``tests.test_board_holds_the_queue._CLAUSE_SPLIT``: sentence ends, ``,:;()``, the em dash,
#: `` and ``/`` but ``/`` then ``) naming one carries a negation
#: (``tests.test_board_holds_the_queue.NEGATION``), and one unit naming CI, the suite or the test
#: job negates both: "no CI on `develop` or pull requests".
CI_EXCLUDED_REFS = (
    ("develop", re.compile(r"(?<![\w-])develop(?![\w-])")),
    ("pull requests", re.compile(r"\bpull requests?\b")),
)
NO_CI_ON_DEVELOP_OR_PRS = "CI rule: no CI on develop or pull requests"
_CI_WORD = re.compile(r"(?<![\w-])ci(?![\w-])|\bsuite\b|\btest job\b")
#: §S5 — the subsection names neither the Python steps' anchors nor the Pi step's, so each
#: checker's first-occurrence order is unchanged.
SUBSECTION_FORBIDDEN_ANCHORS = (
    *(("python step", a) for _, anchors, _ in PYTHON_RELEASE_STEPS for a in anchors),
    *(("pi package step", a) for _, anchors, _ in PI_PACKAGE_RELEASE_STEPS for a in anchors),
)
#: §S6's C3 gate content — none of these anywhere in ``## Releases`` (normalised: backticks
#: and ``*`` dropped, whitespace collapsed, lower-cased).
# MIGRATED at CR-MDB-070 C4 RED (VERIFY F3): "the tag's release job" is retired — the release
# event's publish job publishes (was: the seven phrases before it).
RETIRED_RELEASE_PHRASES = (
    "isolated tool directory", "uv_tool_dir", "test.pypi.org/simple", "token the user supplies",
    "user-supplied token", "credentials the user supplies", "user-supplied credentials",
    "the tag's release job",
)

# (G) — where the installer comes from (VERIFY cycle 100 findings 2/6), and
# the source-copy note that stays true after publishing (CR-MDB-038 \u00a7S4).
# MIGRATED at CR-MDB-063 C3 RED (§S7): each install and update command names `--python 3.14`
# (was: `uv tool install modelb-axi`, `uv tool install .`); the two update commands join them.
INSTALLER_INSTALL = "uv tool install --python 3.14 modelb-axi"
INSTALLER_UPGRADE = "uv tool upgrade --python 3.14 modelb-axi"
SOURCE_COPY_INSTALL = "uv tool install --python 3.14 ."
SOURCE_COPY_UPDATE = "uv tool install --reinstall --python 3.14 ."
#: CR-MDB-038 \u00a7S4 — wording that makes the source-copy note expire at the
#: first upload (case-insensitive, whole word, whitespace-normalised).
EXPIRING_NOTE_WORDING = (
    ("until", re.compile(r"(?<![\w-])until(?![\w-])", re.I)),
    ("interim", re.compile(r"(?<![\w-])interim(?![\w-])", re.I)),
    ("first release", re.compile(r"(?<![\w-])first release(?![\w-])", re.I)),
)
#: CR-MDB-038 \u00a7S3 — the retired global-policy report's vocabulary: its two
#: envelope fields and the two states only it reported.
RETIRED_GLOBAL_REPORT_TERMS = (
    "global_permission_policy", "global_permission_missing_tools", "no-fallback", "missing-tools",
)
REPOSITORY_PATTERNS = (
    ("git clone", re.compile(r"(?<![\w-])git clone(?![\w-])")),
    ("repository URL", re.compile(
        r"git\+\S+|git@\S+|git://\S+|(?<![\w-])git:\S+"
        r"|https?://(?:www\.)?(?:github|gitlab|bitbucket|codeberg)\.(?:com|org)/[\w.-]+/[\w.-]+")),
)
PI_PACKAGE_CLAIM = re.compile(r"(?<![\w-])Pi package(?![\w-])")


# ---------------------------------------------------------------------------
# Markdown helpers
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_INLINE_CODE_RE = re.compile(r"(`+)(.+?)\1")


def _fence_mask(lines: list[str]) -> list[bool]:
    """True for every line that is inside (or delimits) a fenced block."""
    mask, inside, fence = [], False, None
    for line in lines:
        match = _FENCE_RE.match(line)
        if match and (not inside or match.group(1) == fence):
            mask.append(True)
            inside, fence = (not inside), (match.group(1) if not inside else None)
            continue
        mask.append(inside)
    return mask


def code_texts(text: str) -> list[str]:
    """Every inline code span (outside fences) and every fenced-block line."""
    lines = text.splitlines()
    out = []
    for line, fenced in zip(lines, _fence_mask(lines), strict=True):
        if fenced:
            if not _FENCE_RE.match(line):
                out.append(line)
            continue
        out.extend(m.group(2).strip() for m in _INLINE_CODE_RE.finditer(line))
    return out


def _token_re(term: str) -> re.Pattern:
    return re.compile(r"(?<![\w-])" + re.escape(term) + r"(?![\w-])")


def has_code_token(text: str, term: str) -> bool:
    """``term`` appears as a whole token inside a code span or fenced block."""
    pattern = _token_re(term)
    return any(pattern.search(code) for code in code_texts(text))


def sections(text: str, level: str = "## ") -> dict[str, str]:
    """Heading text -> section text (heading line through the line before
    the next heading of the same level). Headings inside fences ignored."""
    lines = text.splitlines()
    mask = _fence_mask(lines)
    starts = [i for i, (ln, f) in enumerate(zip(lines, mask, strict=True))
              if not f and ln.startswith(level) and not ln.startswith(level.strip() + "#")]
    out: dict[str, str] = {}
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        out.setdefault(lines[start][len(level):].strip(), "\n".join(lines[start:end]))
    return out


def heading_counts(text: str) -> dict[str, int]:
    lines = text.splitlines()
    counts: dict[str, int] = {}
    for line, fenced in zip(lines, _fence_mask(lines), strict=True):
        if not fenced and line.startswith("## "):
            key = line[3:].strip()
            counts[key] = counts.get(key, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Derived vocabulary (the gate follows the code)
# ---------------------------------------------------------------------------


def _parser_flags() -> set[str]:
    from modelb_axi.cli import _build_parser
    parser = _build_parser()
    flags = set()
    for action in parser._actions:  # stdlib argparse: the declared actions
        if isinstance(action, argparse._SubParsersAction):
            continue
        flags.update(action.option_strings)
    return flags


def parser_flag(flag: str) -> str:
    """``flag`` if the installer's parser declares it, else AssertionError."""
    flags = _parser_flags()
    if flag not in flags:
        raise AssertionError(
            f"the installer parser no longer declares {flag}; the guide gate "
            f"must follow the code (declared: {sorted(flags)})"
        )
    return flag


def install_outcomes() -> list[str]:
    """Every outcome literal ``cli.py`` passes to ``_emit_install_envelope``."""
    tree = ast.parse(CLI_SOURCE.read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "_emit_install_envelope" and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
                and node.args[0].value not in found):
            found.append(node.args[0].value)
    return found


def known_stacks() -> list[str]:
    from modelb_axi.scaffold import KNOWN_STACKS
    return list(KNOWN_STACKS)


def verdicts() -> list[str]:
    from modelb_axi.capabilities import ABSENT, DETECTED, UNKNOWN
    from modelb_axi.toolchains import INSTALLED
    return [DETECTED, ABSENT, UNKNOWN, INSTALLED]


def toolchain_installer_terms() -> list[str]:
    """Probe names and installer commands of every toolchain probe that has
    an installer the pre-flight can offer."""
    from modelb_axi.requirements import STACK_TOOLCHAINS, install_display
    terms = []
    for probes in STACK_TOOLCHAINS.values():
        for probe in probes:
            if probe.get("install"):
                for term in (probe["name"], install_display(probe["install"])):
                    if term not in terms:
                        terms.append(term)
    return terms


def policy_dir_name() -> str:
    from modelb_axi.permission_policy import POLICY_RELPATH
    return POLICY_RELPATH.parts[1]


_GROUP_LINE_RE = re.compile(r"^([a-z][a-z0-9-]*(?: [a-z0-9-]+)?): (?:\S+=\S+\s*)+$")


@lru_cache(maxsize=1)
def preflight_prefixes() -> tuple[str, ...]:
    """The pre-flight's group-line prefixes, read from a REAL installer run
    in a sandbox (fake ``uv``/``sandesh``, sandboxed HOME and Pi agent dir,
    ``--stacks python``, no ``--target-root`` so nothing deploys). A stack
    line is normalised to ``stack <name>``."""
    root = Path(tempfile.mkdtemp(prefix="modelb-install-guide-"))
    try:
        bin_dir, home, agent = root / "bin", root / "home", root / "agent"
        for d in (bin_dir, home, agent):
            d.mkdir()
        # MIGRATED at CR-MDB-047 C1 RED (§S1 version floor): a current sandesh.
        # MIGRATED at CR-MDB-064 C2 RED (§S7): `python3` and `uv` are the shared installer
        # fixture's — an interpreter at the 3.14 floor, which the pre-flight requires
        # (CR-MDB-064 §S2), and a `uv` answering `uv python find --system '>=3.14'`.
        write_interpreter_fixture(bin_dir, uv_body="#!/bin/sh\nexit 0\n")
        exe = bin_dir / "sandesh"
        exe.write_text("#!/bin/sh\necho 'sandesh 0.4.0'\nexit 0\n", encoding="utf-8")
        exe.chmod(0o755)
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT) + (
            os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        env.update(PATH=str(bin_dir), HOME=str(home), PI_CODING_AGENT_DIR=str(agent))
        env.pop("MODELB_TARGET_ROOT", None)
        result = subprocess.run(
            [sys.executable, "-m", "modelb_axi", "--yes", "--harnesses", "pi",
             "--modelb-home", str(root / "modelb-home"), "--stacks", "python",
             "--allow-missing-capabilities"],
            capture_output=True, text=True, timeout=60,
            stdin=subprocess.DEVNULL, env=env,
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)
    stacks = set(known_stacks())
    prefixes: list[str] = []
    for line in result.stderr.splitlines():
        match = _GROUP_LINE_RE.match(line)
        if not match:
            continue
        prefix = match.group(1)
        if prefix.startswith("stack ") and prefix[len("stack "):] in stacks:
            prefix = "stack <name>"
        if prefix not in prefixes:
            prefixes.append(prefix)
    if not prefixes:
        raise AssertionError(
            "no pre-flight group line could be derived from a sandboxed "
            f"installer run; exit={result.returncode} stderr={result.stderr!r}"
        )
    return tuple(prefixes)


def _prefix_present(section: str, prefix: str) -> bool:
    if prefix == "stack <name>":
        pattern = re.compile(r"(?<![\w-])stack <[^<>\s]+>:")
        return any(pattern.search(code) for code in code_texts(section))
    return has_code_token(section, prefix + ":")


# ---------------------------------------------------------------------------
# Checkers — each returns the list of violations (empty = conforming)
# ---------------------------------------------------------------------------

def check_headings(text: str) -> list[str]:
    counts = heading_counts(text)
    return [f"heading '## {h}' appears {counts.get(h, 0)} times (want 1)"
            for h in SECTIONS if counts.get(h, 0) != 1]


def _section(text: str, heading: str) -> str:
    return sections(text).get(heading, "")


def _missing_tokens(section: str, terms, where: str) -> list[str]:
    return [f"{where}: missing `{t}`" for t in terms if not has_code_token(section, t)]


def check_prerequisites(text: str) -> list[str]:
    sec = _section(text, PREREQUISITES)
    codes = code_texts(sec)
    out = []
    rows = _requirements()
    for row in rows:
        if row["scope"] != "always":
            continue
        named = (has_code_token(sec, row["id"])
                 or any(row["provider"] in c or row["remediation"] in c for c in codes))
        if not named:
            out.append(f"{PREREQUISITES}: requirement {row['id']!r} not named "
                       "(id, provider or remediation, in code)")
    pi = re.search(r"(?<![\w-])Pi(?![\w-])", sec)
    for row in rows:
        if row["tier"] != 1:
            continue
        at = sec.find(row["provider"])
        if pi is None or at == -1 or at < pi.start():
            out.append(f"{PREREQUISITES}: Pi must be introduced before {row['provider']}")
    uv = next(r for r in rows if r["id"] == "uv")
    remediations = {r["remediation"] for r in rows}
    uv_at = sec.find(uv["remediation"])
    installer_at = -1
    for match in re.finditer(r"uv tool install[^\n`]*", sec):
        if match.group(0).strip() not in remediations:
            installer_at = match.start()
            break
    if uv_at == -1 or installer_at == -1 or uv_at > installer_at:
        out.append(f"{PREREQUISITES}: uv ({uv['remediation']!r}) must precede "
                   "the `uv tool install` that installs the installer")
    return out


def check_stacks(text: str) -> list[str]:
    sec = _section(text, STACKS)
    out = _missing_tokens(sec, [parser_flag("--stacks"), *known_stacks()], STACKS)
    if not any("crucible-report-" in c for c in code_texts(sec)):
        out.append(f"{STACKS}: must name the `crucible-report-` bundles a stack installs")
    if "does not install" not in sec.lower():
        out.append(f"{STACKS}: must say what a stack 'does not install'")
    return out


def check_preflight(text: str) -> list[str]:
    sec = _section(text, PREFLIGHT)
    out = [f"{PREFLIGHT}: missing pre-flight line `{p}:`"
           for p in preflight_prefixes() if not _prefix_present(sec, p)]
    return out + _missing_tokens(sec, verdicts(), PREFLIGHT)


def check_warnings(text: str) -> list[str]:
    sec = _section(text, WARNINGS)
    out = []
    lines = sec.splitlines()
    for row in _requirements():
        families = [f.lower() for f in row["asset_families"]]
        if not any(has_code_token(line, row["id"]) and any(f in line.lower() for f in families)
                   for line in lines):
            out.append(f"{WARNINGS}: no line names `{row['id']}` with one of "
                       f"{list(row['asset_families'])}")
    return out


def check_offers(text: str) -> list[str]:
    sec = _section(text, OFFERS)
    out = _missing_tokens(sec, ["pi install", parser_flag("--yes")], OFFERS)
    codes = code_texts(sec)
    if not any(has_code_token(sec, t) or any(t in c for c in codes)
               for t in toolchain_installer_terms()):
        out.append(f"{OFFERS}: must show that toolchain installers are offered")
    return out


def check_missing_capabilities(text: str) -> list[str]:
    sec = _section(text, MISSING)
    required = [r["id"] for r in _requirements() if r["tier"] == 1 and r["policy"] == "required"]
    return _missing_tokens(sec, [parser_flag("--allow-missing-capabilities"), *required], MISSING)


def check_outcomes(text: str) -> list[str]:
    return _missing_tokens(_section(text, OUTCOMES), install_outcomes(), OUTCOMES)


def check_real_home(text: str) -> list[str]:
    sec = _section(text, REAL_HOME)
    flag = parser_flag("--target-root")
    pattern = re.compile(r"(?<![\w-])" + re.escape(flag) + r" ~(?![\w/.-])")
    if any(pattern.search(c) for c in code_texts(sec)):
        return []
    return [f"{REAL_HOME}: missing `{flag} ~`"]


def check_widening(text: str) -> list[str]:
    return _missing_tokens(_section(text, WIDENING),
                           [parser_flag("--stacks"), parser_flag("--reinstall")], WIDENING)


def check_trust(text: str) -> list[str]:
    return _missing_tokens(_section(text, TRUST),
                           ["/trust", ".pi/extensions", policy_dir_name()], TRUST)


TOPIC_CHECKERS = {
    PREREQUISITES: check_prerequisites,
    STACKS: check_stacks,
    PREFLIGHT: check_preflight,
    WARNINGS: check_warnings,
    OFFERS: check_offers,
    MISSING: check_missing_capabilities,
    OUTCOMES: check_outcomes,
    REAL_HOME: check_real_home,
    WIDENING: check_widening,
    TRUST: check_trust,
}


def parse_marked_regions(text: str) -> tuple[list[tuple[str, int, int]], list[str]]:
    """The guide's marked regions, in order: ``(name, begin_line, end_line)``
    with 0-based indices of the two marker lines, plus the marker faults
    (malformed, nested, unmatched, never-ended). Markers inside fenced blocks
    are ignored. The one parser of the convention: :func:`check_marked_regions`
    and the Pi package README gate (``tests/test_pi_package.py``) both use it
    (CR-MDB-029 \u00a7S1, orchestrator ruling D2, 2026-09-24)."""
    lines = text.splitlines()
    mask = _fence_mask(lines)
    out: list[str] = []
    regions: list[tuple[str, int, int]] = []
    open_region: tuple[str, int] | None = None
    for i, (line, fenced) in enumerate(zip(lines, mask, strict=True)):
        stripped = line.strip()
        if fenced or not stripped.startswith(MARKER_PREFIX):
            continue
        begin, end = BEGIN_RE.match(stripped), END_RE.match(stripped)
        if begin:
            if open_region is not None:
                out.append(f"line {i + 1}: region {begin.group(1)!r} nested in {open_region[0]!r}")
            else:
                open_region = (begin.group(1), i)
        elif end:
            if open_region is None or open_region[0] != end.group(1):
                out.append(f"line {i + 1}: end {end.group(1)!r} has no matching begin")
            else:
                regions.append((open_region[0], open_region[1], i))
                open_region = None
        else:
            out.append(f"line {i + 1}: malformed marker {stripped!r}")
    if open_region is not None:
        out.append(f"region {open_region[0]!r} is never ended")
    return regions, out


def check_marked_regions(text: str) -> list[str]:
    lines = text.splitlines()
    mask = _fence_mask(lines)
    regions, out = parse_marked_regions(text)
    if not regions:
        out.append("no marked region")
    names = [r[0] for r in regions]
    out.extend(f"region name {n!r} is not unique" for n in sorted(set(names)) if names.count(n) > 1)
    for name, start, stop in regions:
        if not any(ln.strip() for ln in lines[start + 1:stop]):
            out.append(f"region {name!r} is empty")

    def inside(first: int, last: int) -> bool:
        return any(start < first and last < stop for _n, start, stop in regions)

    heads = [i for i, (ln, f) in enumerate(zip(lines, mask, strict=True)) if not f and ln.startswith("## ")]
    for n, head in enumerate(heads):
        title = lines[head][3:].strip()
        nxt = heads[n + 1] if n + 1 < len(heads) else len(lines)
        body = [j for j in range(head, nxt)
                if lines[j].strip() and not lines[j].strip().startswith(MARKER_PREFIX)]
        last = body[-1] if body else head
        if title in INSTALL_TOPICS and not inside(head, last):
            out.append(f"section '{title}' is not wholly inside a marked region")
        if title == MARKED and any(start < head < stop for _n, start, stop in regions):
            out.append(f"section '{MARKED}' must sit outside every marked region")
    marked = _section(text, MARKED)
    for kind in ("begin", "end"):
        if not any(f"{MARKER_PREFIX}{kind}" in c for c in code_texts(marked)):
            out.append(f"section '{MARKED}' must show the {kind} marker in code")
    return out


#: The PyPI project page shows the whole guide as the package readme
#: (orchestrator ruling R3, 2026-09-24, cycle 106: prose, not a table).
PYPI_PAGE = "PyPI project page"


def _prose_blocks(section: str) -> list[str]:
    """Paragraphs and list items of ``section`` (fenced code excluded)."""
    lines = section.splitlines()
    mask = _fence_mask(lines)
    text = "\n".join("" if fenced else ln for ln, fenced in zip(lines, mask, strict=True))
    return [b for b in re.split(r"\n\s*\n|\n(?=\s*[-*] )", text) if b.strip()]


def check_pypi_surface(text: str) -> list[str]:
    """The ``Marked regions`` section (outside every region) names the PyPI
    project page and says, in the same paragraph or list item, that it
    shows the whole guide as the package readme."""
    blocks = [b for b in _prose_blocks(_section(text, MARKED)) if PYPI_PAGE in " ".join(b.split())]
    if not blocks:
        return [f"section '{MARKED}' must name the {PYPI_PAGE}"]
    if not any("whole guide" in " ".join(b.split()).lower() and "readme" in b.lower()
               for b in blocks):
        return [f"section '{MARKED}' must say the {PYPI_PAGE} shows the whole guide "
                "as the package readme"]
    return []


#: CR-MDB-058 §S7 — what the ``Marked regions`` section says the regions are for, each
#: ``(label, regexes)`` matched in ONE normalised unit of the section: release notes link to the
#: guide, and the regions feed the generated package README.
MARKED_REGIONS_USE = (
    ("release notes link to the guide",
     (r"\brelease notes\b", r"\blink(?:s|ed|ing)?\b", r"\bguide\b|\bthis file\b")),
    ("the regions feed the generated package README",
     (r"\bregions?\b", r"\b(?:feed\w*|generat\w*)\b", r"\bpackage\b", r"\breadme\b")),
)


def check_marked_regions_use(text: str) -> list[str]:
    """CR-MDB-058 §S7: the ``Marked regions`` section no longer says the regions are copied
    into the release notes (a unit naming a copy and the release notes, with no negation), and
    says release notes link to the guide and the regions feed the generated package README."""
    found = norm_units(_section(text, MARKED))
    out = [f"section '{MARKED}' must say {label}" for label, regexes in MARKED_REGIONS_USE
           if not any(all(re.search(rx, u) for rx in regexes) for u in found)]
    if any(re.search(r"\bcop(?:y|ies|ied|ying)\b", u) and re.search(r"\brelease notes\b", u)
           and not NEGATION.search(u) for u in found):
        out.append(f"section '{MARKED}' must not say the regions are copied into the release "
                   "notes")
    return out


def check_vocabulary(text: str) -> list[str]:
    out = [f"{label}: {m.group(0)!r}" for label, pattern in BLOCKED_PATTERNS
           for m in pattern.finditer(text)]
    for word in BLOCKED_WORDS:
        if _token_re(word).search(text):
            out.append(f"internal vocabulary: {word!r}")
    return out


def check_readme(text: str) -> list[str]:
    out = []
    nonblank = [ln for ln in text.splitlines() if ln.strip()]
    if len(nonblank) > README_MAX_NONBLANK_LINES:
        out.append(f"{len(nonblank)} non-blank lines (max {README_MAX_NONBLANK_LINES})")
    if not nonblank or not nonblank[0].startswith("# "):
        out.append("first line must be a '# ' title")
    elif len(nonblank) < 2 or nonblank[1].lstrip().startswith(("#", "```", "~~~", "<!--", "-", "*", "|")):
        out.append("the title must be followed by a description paragraph")
    if not re.search(r"\]\((?:\./)?" + re.escape(GUIDE_LINK_TARGET) + r"(?:#[^)]*)?\)", text):
        out.append(f"no markdown link to {GUIDE_LINK_TARGET}")
    candidates = [ln.strip() for ln in text.splitlines()] + code_texts(text)
    for cand in candidates:
        cand = cand.lstrip("$> ").strip()
        if cand.startswith(INSTALLER_COMMAND_PREFIXES):
            out.append(f"installer command line: {cand!r}")
    return out


def check_release_steps(text: str) -> list[str]:
    """CR-MDB-058 §S6: ``## Releases`` states every step of :data:`RELEASE_STEP_PHRASES`
    in one unit, carries a fenced release-job snippet passing the tag's ``CHANGELOG.md``
    section as ``--notes-file`` (and no ``--generate-notes`` in a fence), and no longer says to
    copy the marked regions into the release notes. One message per fault, each prefixed
    ``## Releases: <group>: ``.

    MIGRATED at CR-MDB-067 C3 RED (§S5): it also checks the publish step
    (:data:`PUBLISH_STEP_PHRASES`), the release-notes step written before the branch is first
    published (in the ``### Release notes`` subsection), the ``### Rehearsal and CI``
    subsection after ``### Pi package releases`` (:data:`REHEARSAL_AND_CI_PHRASES`, naming none
    of :data:`SUBSECTION_FORBIDDEN_ANCHORS`), and no :data:`RETIRED_RELEASE_PHRASES`."""
    sec = next((body for head, body in sections(text).items()
                if head.startswith("Releases")), "")
    if not sec:
        return ["no '## Releases' section"]
    found = norm_units(sec)
    out = [f"## Releases: {group}: {label}" for group, label, regexes in RELEASE_STEP_PHRASES
           if not any(all(re.search(rx, u) for rx in regexes) for u in found)]
    blocks = _fenced_blocks(sec)
    snippet = release_job_snippet(text)
    if snippet is None:
        out.append(f"## Releases: {RELEASE_JOB_SNIPPET}: no fenced create-release step passing "
                   "the CHANGELOG.md section as --notes-file")
    else:
        # MIGRATED at CR-MDB-070 C2 RED (§S6): the snippet also carries SNIPPET_ELEMENTS.
        out += [f"## Releases: {RELEASE_JOB_SNIPPET}: the snippet {fault}"
                for fault, regexes in SNIPPET_ELEMENTS
                if not all(re.search(rx, snippet.lower(), re.M) for rx in regexes)]
        # CR-MDB-070 C4 RED (VERIFY F2): the checkout says to pin it to a full commit SHA.
        out += checkout_pin_faults(snippet)
    if REF_NAME_RE.search(sec.lower()):
        out.append(f"## Releases: {RELEASE_JOB_SNIPPET}: names github.ref_name")
    if any("--generate-notes" in block for block in blocks):
        out.append(f"## Releases: {RELEASE_JOB_SNIPPET}: a fenced step still uses "
                   "--generate-notes")
    if RETIRED_COPY_STEP_RE.search(normalise(sec)):
        out.append(f"## Releases: {RETIRED_COPY_STEP}: still says to copy the marked regions "
                   "into the release notes")
    out += _publish_and_rehearsal_faults(sec, found)
    out += _missing_steps(RELEASE_FLOW_PHRASES, found)
    # CR-MDB-070 C4 RED (VERIFY F6): recovery from a red or flaky run.
    out += _missing_steps(RED_RUN_RECOVERY_PHRASES, found)
    return out


def release_job_snippet(text: str) -> str | None:
    """The release-job snippet: the first fenced block of ``## Releases`` holding every
    :data:`SNIPPET_TERMS` (lower-cased); ``None`` when there is none (CR-MDB-070 C4 RED)."""
    sec = next((body for head, body in sections(text).items()
                if head.startswith("Releases")), "")
    return next((block for block in _fenced_blocks(sec)
                 if all(term in block.lower() for term in SNIPPET_TERMS)), None)


def checkout_pin_faults(snippet: str) -> list[str]:
    """CR-MDB-070 C4 RED (VERIFY F2): ``[]`` when a ``uses: actions/checkout@…`` line of
    ``snippet``, with the comment lines directly above and below it, matches every
    :data:`CHECKOUT_PIN_TERMS` regex; otherwise the one :data:`CHECKOUT_PIN_FAULT`."""
    lines = snippet.splitlines()
    for i, line in enumerate(lines):
        if not CHECKOUT_USES_RE.match(line):
            continue
        beside = [line]
        for step in (-1, 1):
            j = i + step
            while 0 <= j < len(lines) and lines[j].strip().startswith("#"):
                beside.append(lines[j])
                j += step
        if all(re.search(rx, " ".join(beside).lower()) for rx in CHECKOUT_PIN_TERMS):
            return []
    return [f"## Releases: {RELEASE_JOB_SNIPPET}: {CHECKOUT_PIN_FAULT}"]


def publish_job_faults(text: str) -> list[str]:
    """CR-MDB-070 C4 RED (VERIFY F3): for each step of :data:`PUBLISH_JOB_STEPS`, one fault per
    term no unit of ``## Releases`` holding the step's anchor carries — ``## Releases: <label>:
    the step holding <anchor> does not say <term>`` — or ``## Releases: <label>: no unit holds
    <anchor>`` when none holds it."""
    sec = next((body for head, body in sections(text).items()
                if head.startswith("Releases")), "")
    if not sec:
        return ["no '## Releases' section"]
    units = norm_units(sec)
    out = []
    for label, anchor, terms in PUBLISH_JOB_STEPS:
        holding = [unit for unit in units if anchor in unit]
        if not holding:
            out.append(f"## Releases: {label}: no unit holds {anchor!r}")
            continue
        out += [f"## Releases: {label}: the step holding {anchor!r} does not say {term!r}"
                for term in terms if not any(term in unit for unit in holding)]
    return out


_SUBHEADING_RE = re.compile(r"^(#{2,3}) (.*?)\s*$")


def _subsection(section: str, matches) -> tuple[int, str] | None:
    """The first ``### `` subsection of ``section`` whose heading title satisfies ``matches``:
    ``(the heading's line index, its body up to the next ``## ``/``### `` heading)``. A line
    inside a fence is never a heading. ``None`` when there is none."""
    lines = section.splitlines()
    start = None
    for i, (line, fenced) in enumerate(zip(lines, _fence_mask(lines), strict=True)):
        heading = None if fenced else _SUBHEADING_RE.match(line)
        if start is None:
            if heading and heading.group(1) == "###" and matches(heading.group(2)):
                start = i
        elif heading:
            return start, "\n".join(lines[start + 1:i])
    return None if start is None else (start, "\n".join(lines[start + 1:]))


def _missing_steps(phrases, units: list[str]) -> list[str]:
    """``## Releases: <group>: <label>`` for each step of ``phrases`` no unit carries whole."""
    return [f"## Releases: {group}: {label}" for group, label, regexes in phrases
            if not any(all(re.search(rx, u) for rx in regexes) for u in units)]


def _publish_and_rehearsal_faults(sec: str, found: list[str]) -> list[str]:
    """CR-MDB-067 §S5's faults of one ``## Releases`` body ``sec`` (``found`` = its units)."""
    out = _missing_steps(PUBLISH_STEP_PHRASES, found)
    notes = _subsection(sec, lambda title: title.startswith(RELEASE_NOTES_SUBSECTION))
    out += _missing_steps((NOTES_BEFORE_PUBLISH_PHRASE,), norm_units(notes[1]) if notes else [])
    rehearsal = _subsection(sec, lambda title: title == REHEARSAL_AND_CI_HEADING)
    if rehearsal is None:
        out.append(f"## Releases: {REHEARSAL_AND_CI}: no '### {REHEARSAL_AND_CI_HEADING}' "
                   "subsection")
    else:
        start, body = rehearsal
        pi = _subsection(sec, lambda title: title.startswith(PI_PACKAGE_HEADING))
        if pi is None or pi[0] > start:
            out.append(f"## Releases: {REHEARSAL_AND_CI}: '### {REHEARSAL_AND_CI_HEADING}' is not "
                       f"after '### {PI_PACKAGE_HEADING}'")
        out += _missing_steps(REHEARSAL_AND_CI_PHRASES, norm_units(body))
        out += excluded_ref_faults(norm_units(body))
        flat = " ".join(body.lower().split())
        out += [f"## Releases: {REHEARSAL_AND_CI}: names the {kind} anchor {anchor!r}"
                for kind, anchor in SUBSECTION_FORBIDDEN_ANCHORS if anchor in flat]
    plain = normalise(sec)
    out += [f"## Releases: {RETIRED_PHRASES}: names {phrase!r}"
            for phrase in RETIRED_RELEASE_PHRASES if phrase in plain]
    return out


def excluded_ref_faults(units: list[str]) -> list[str]:
    """CR-MDB-070 §S6, negation-aware: the faults of the ``### Rehearsal and CI`` units
    ``units`` (normalised) against :data:`CI_EXCLUDED_REFS`. ``no CI on develop or pull
    requests`` when no unit naming CI, the suite or the test job negates both refs, each in a
    negated clause; ``names CI on <ref>`` once per ref some clause names WITHOUT a negation."""
    positive: list[str] = []
    stated = False
    for unit in units:
        negated = set()
        for clause in _CLAUSE_SPLIT.split(unit):
            for name, rx in CI_EXCLUDED_REFS:
                if not rx.search(clause):
                    continue
                if NEGATION.search(clause):
                    negated.add(name)
                elif name not in positive:
                    positive.append(name)
        if _CI_WORD.search(unit) and len(negated) == len(CI_EXCLUDED_REFS):
            stated = True
    out = [] if stated else [f"## Releases: {REHEARSAL_AND_CI}: {NO_CI_ON_DEVELOP_OR_PRS}"]
    return out + [f"## Releases: {REHEARSAL_AND_CI}: names CI on {name}"
                  for name, _ in CI_EXCLUDED_REFS if name in positive]


def release_step_faults(text: str, group: str) -> list[str]:
    """The faults of :func:`check_release_steps` in one ``group``."""
    return [f for f in check_release_steps(text) if f.startswith(f"## Releases: {group}: ")
            or f == "no '## Releases' section"]


def _fenced_blocks(text: str) -> list[str]:
    """The body of every fenced block of ``text``, delimiters excluded."""
    lines = text.splitlines()
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for line, fenced in zip(lines, _fence_mask(lines), strict=True):
        if fenced and _FENCE_RE.match(line):
            if current is None:
                current = []
            else:
                blocks.append(current)
                current = None
        elif fenced and current is not None:
            current.append(line)
    return ["\n".join(b) for b in blocks]


def check_python_release_steps(text: str) -> list[str]:
    """CR-MDB-038 \u00a7S5: ``## Releases`` names the four Python release
    steps, in order, without naming any one project."""
    sec = next((body for head, body in sections(text).items()
                if head.startswith("Releases")), "")
    if not sec:
        return ["no '## Releases' section"]
    flat = " ".join(sec.lower().split())
    out: list[str] = []
    anchors: list[tuple[int, str]] = []
    for label, anchor, terms in PYTHON_RELEASE_STEPS:
        found = [flat.find(a) for a in anchor if a in flat]
        if found:
            anchors.append((min(found), label))
        else:
            out.append(f"## Releases: {label}: missing {anchor[0]!r}")
        for alts in terms:
            if not any(a in flat for a in alts):
                out.append(f"## Releases: {label}: missing {alts[0]!r}")
    if [lbl for _, lbl in sorted(anchors)] != [lbl for _, lbl in anchors]:
        out.append("## Releases: python release steps out of order")
    out += [f"## Releases: names project {n!r}" for n in PROJECT_SPECIFIC_NAMES if n in flat]
    return out


def check_pi_package_release_steps(text: str) -> list[str]:
    """CR-MDB-029 \u00a7S4: ``## Releases`` names the project-neutral Pi package
    step — npm publish (``--access public``) through Trusted Publishing, a new package's
    one-time token kept as a repository secret and 2FA required (MIGRATED at CR-MDB-067 C3 RED,
    §S5; was: with user-supplied credentials at publish time), then an isolated ``PI_CODING_AGENT_DIR`` install confirming the extension
    loads, then the post-release live check in the real Pi configuration."""
    sec = next((body for head, body in sections(text).items()
                if head.startswith("Releases")), "")
    if not sec:
        return ["no '## Releases' section"]
    flat = " ".join(sec.lower().split())
    out: list[str] = []
    anchors: list[tuple[int, str]] = []
    for label, anchor, terms in PI_PACKAGE_RELEASE_STEPS:
        found = [flat.find(a) for a in anchor if a in flat]
        if found:
            anchors.append((min(found), label))
        else:
            out.append(f"## Releases: {label}: missing {anchor[0]!r}")
        for alts in terms:
            if not any(a in flat for a in alts):
                out.append(f"## Releases: {label}: missing {alts[0]!r}")
    if PI_PACKAGE_RETIRED_TERM in flat:
        out.append(f"## Releases: live check: names a {PI_PACKAGE_RETIRED_TERM}")
    if [lbl for _, lbl in sorted(anchors)] != [lbl for _, lbl in anchors]:
        out.append("## Releases: pi package steps out of order")
    out += [f"## Releases: names project {n!r}" for n in PI_PROJECT_SPECIFIC_NAMES if n in flat]
    return out


def check_cr029_s1(text: str) -> list[str]:
    sec = next((body for head, body in sections(text, "### ").items()
                if head.startswith("§S1")), "")
    if not sec:
        return ["no '### §S1' section"]
    lowered = sec.lower()
    return [f"§S1: missing {t!r}" for t in CR_029_S1_TERMS
            if (t.lower() if t != "README" else t) not in (lowered if t != "README" else sec)]


# ---------------------------------------------------------------------------
# A conforming synthetic guide, built from the derived vocabulary — the proof
# that a correct guide CAN pass every checker.
# ---------------------------------------------------------------------------

def check_installer_source(text: str) -> list[str]:
    """The installer comes from PyPI (``uv tool install modelb-axi``), with
    the always-true source-copy note (``uv tool install .``, "from a source
    copy") carrying no "until", "interim" or "first release" wording
    (CR-MDB-038 \u00a7S4); it is not claimed to ship as the Pi package; the
    guide names no ``git clone`` and no repository URL; and ``git`` is a
    prerequisite that comes before the installer step."""
    sec = _section(text, PREREQUISITES)
    out = []
    if not has_code_token(sec, INSTALLER_INSTALL):
        out.append(f"{PREREQUISITES}: the installer step must name `{INSTALLER_INSTALL}`")
    # MIGRATED at CR-MDB-063 C3 RED (§S7): the two update commands are named too.
    if not has_code_token(sec, INSTALLER_UPGRADE):
        out.append(f"{PREREQUISITES}: the installer step must name `{INSTALLER_UPGRADE}`")
    if not has_code_token(sec, SOURCE_COPY_UPDATE):
        out.append(f"{PREREQUISITES}: the source-copy note must name `{SOURCE_COPY_UPDATE}`")
    if not re.search(r"(?<![\w-])PyPI(?![\w-])", sec):
        out.append(f"{PREREQUISITES}: must say the installer comes from PyPI")
    notes = [" ".join(b.split()) for b in _prose_blocks(sec)
             if has_code_token(b, SOURCE_COPY_INSTALL)]
    if not any("source copy" in note.lower() for note in notes):
        out.append(f"{PREREQUISITES}: must carry the source-copy note "
                   f"(`{SOURCE_COPY_INSTALL}` from a source copy)")
    out.extend(f"{PREREQUISITES}: the source-copy note must not say {word!r}"
               for word, pattern in EXPIRING_NOTE_WORDING
               if any(pattern.search(note) for note in notes))
    out.extend(f"{PREREQUISITES}: must not claim the installer ships as the Pi package: "
               f"{m.group(0)!r}" for m in PI_PACKAGE_CLAIM.finditer(sec))
    out.extend(f"{label}: {m.group(0)!r}"
               for label, pattern in REPOSITORY_PATTERNS for m in pattern.finditer(text))
    git_at = sec.find("`git`")
    installer_at = [at for at in (sec.find(INSTALLER_INSTALL), sec.find(SOURCE_COPY_INSTALL))
                    if at != -1]
    if git_at == -1:
        out.append(f"{PREREQUISITES}: `git` must be named")
    elif installer_at and min(installer_at) < git_at:
        out.append(f"{PREREQUISITES}: `git` must come before the installer step")
    return out


def check_permission_source(text: str) -> list[str]:
    """CR-MDB-038 \u00a7S3: the guide no longer describes the installer's
    global-policy report (none of :data:`RETIRED_GLOBAL_REPORT_TERMS`,
    anywhere), and the ``Project trust`` section states \u2014 in one paragraph
    or list item \u2014 that workflow permissions come from each project's
    policy, loaded under ``/trust``."""
    out = [f"guide: must not describe the global-policy report: `{term}`"
           for term in RETIRED_GLOBAL_REPORT_TERMS if _token_re(term).search(text)]

    def states_it(block: str) -> bool:
        low = " ".join(block.split()).lower()
        return ("workflow permissions" in low and "each project" in low and "policy" in low
                and has_code_token(block, "/trust"))

    if not any(states_it(b) for b in _prose_blocks(_section(text, TRUST))):
        out.append(f"{TRUST}: must state that workflow permissions come from each "
                   "project's policy, loaded under `/trust`")
    return out


def check_cr029_acceptance(text: str) -> list[str]:
    """CR-MDB-029's acceptance criteria take the package README from the
    guide's marked regions, and no longer own the guide's install step."""
    sec = next((body for head, body in sections(text).items()
                if head.startswith("Acceptance criteria")), "")
    if not sec:
        return ["no '## Acceptance criteria' section"]
    out = []
    if not re.search(r"README.*marked region|marked region.*README", sec, re.S):
        out.append("ACs: the Pi package README must come from the guide's marked regions")
    for term in ("check_prerequisites", "install step"):
        if term in sec:
            out.append(f"ACs: must not name {term!r}")
    return out


#: The flags the ``stale`` re-run must name so it acts on the same install
#: (VERIFY cycle 102 finding 3), derived from the parser.
def _stale_rerun_flags() -> list[str]:
    return [parser_flag(f) for f in ("--reinstall", "--target-root", "--stacks",
                                     "--harnesses", "--modelb-home")]


def check_stale_rerun(text: str) -> list[str]:
    """The ``stale`` bullet of the install-outcomes section names every
    flag of the re-run that refreshes the same install."""
    sec = _section(text, OUTCOMES)
    bullet = re.search(r"^- `stale`.*?(?=^- |^\s*$|\Z)", sec, re.M | re.S)
    if bullet is None:
        return [f"{OUTCOMES}: no `stale` bullet"]
    return _missing_tokens(bullet.group(0), _stale_rerun_flags(), f"{OUTCOMES} `stale`")


#: Harness ids the installer no longer accepts (Pi is the only harness).
RETIRED_HARNESS_IDS = ("claude-code", "hermes", "opencode")
_HARNESS_RECOVERY_RE = re.compile(r"^modelb-axi --reinstall\b.*(?<![\w-])--harnesses pi(?![\w-])")


def check_harness_rejected(text: str) -> list[str]:
    """The ``harness_rejected`` outcome row lists no retired harness id as
    valid, names a stale ``install.toml`` id as a cause, and names the
    recovery re-run (``modelb-axi --reinstall \u2026 --harnesses pi``) in one
    code span."""
    where = f"{OUTCOMES} `harness_rejected`"
    row = re.search(r"^\| `harness_rejected` \|.*$", _section(text, OUTCOMES), re.M)
    if row is None:
        return [f"{OUTCOMES}: no `harness_rejected` row"]
    line = row.group(0)
    problems = [f"{where}: names retired `{h}`" for h in RETIRED_HARNESS_IDS
                if re.search(rf"(?<![\w-]){re.escape(h)}(?![\w-])", line, re.IGNORECASE)]
    problems += _missing_tokens(line, ("install.toml", "pi"), where)
    if not any(_HARNESS_RECOVERY_RE.search(code) for code in code_texts(line)):
        problems.append(f"{where}: missing the `modelb-axi --reinstall \u2026 --harnesses pi` "
                        "recovery")
    return problems


#: The conforming guide's installer step (PyPI + the always-true source-copy
#: note, CR-MDB-038 \u00a7S4).
#: MIGRATED at CR-MDB-063 C3 RED (§S7): each form names its update command too.
_CONFORMING_INSTALLER_LINE = (
    f"- The installer, from PyPI: `{INSTALLER_INSTALL}`, updated with `{INSTALLER_UPGRADE}`; "
    f"or, from a source copy: `{SOURCE_COPY_INSTALL}`, updated with `{SOURCE_COPY_UPDATE}`"
)
#: The CR-MDB-037 installer step whose note expires at the first upload.
_EXPIRING_INSTALLER_LINE = (
    f"- The installer, from PyPI: `{INSTALLER_INSTALL}`, updated with `{INSTALLER_UPGRADE}`; "
    f"until then, from a source copy obtained from the maintainer: `{SOURCE_COPY_INSTALL}`, "
    f"updated with `{SOURCE_COPY_UPDATE}`"
)
#: The conforming guide's statement of where workflow permissions come from
#: (CR-MDB-038 \u00a7S3).
_CONFORMING_PERMISSION_SOURCE = (
    "Workflow permissions come from each project's policy, loaded once you run "
    "`/trust` in the project."
)


#: CR-MDB-058 §S7 — the conforming guide's statement of what the marked regions are for.
CONFORMING_MARKED_REGIONS_USE = (
    "Release notes link to this guide. The regions feed the generated package README.")


def conforming_guide() -> str:
    rows = _requirements()
    uv = next(r for r in rows if r["id"] == "uv")
    tier1 = [r for r in rows if r["tier"] == 1]
    always_rest = [r for r in rows if r["scope"] == "always" and r["tier"] != 1 and r["id"] != "uv"]
    prereq = ["Install Pi first; its packages come next."]
    prereq += [f"- `{r['remediation']}`" for r in tier1]
    prereq += [f"- `{uv['remediation']}`", "- `git`, from your package manager.",
               _CONFORMING_INSTALLER_LINE]
    prereq += [f"- `{r['id']}`: `{r['remediation']}`" for r in always_rest]
    stack_lines = ["Choose with `--stacks " + ",".join(known_stacks()) + "`.",
                   " ".join(f"`{s}`" for s in known_stacks()),
                   "A stack installs the `crucible-report-<stack>` bundle; it does not install a toolchain."]
    preflight = ["```"]
    for p in preflight_prefixes():
        preflight.append(("stack <name>:" if p == "stack <name>" else f"{p}:") + " x=y")
    preflight.append("```")
    preflight.append(" ".join(f"`{v}`" for v in verdicts()))
    warnings = [f"- `{r['id']}`: the {r['asset_families'][0]} will not work" for r in rows]
    offers = ["`pi install` and `" + toolchain_installer_terms()[0] + "` are offered; `--yes` never confirms them."]
    required = [r["id"] for r in tier1 if r["policy"] == "required"]
    missing = ["`--allow-missing-capabilities` continues without " + ", ".join(f"`{i}`" for i in required)]
    outcomes = [f"- `{o}`" for o in install_outcomes()]
    bodies = {
        PREREQUISITES: prereq, STACKS: stack_lines, PREFLIGHT: preflight,
        WARNINGS: warnings, OFFERS: offers, MISSING: missing, OUTCOMES: outcomes,
        REAL_HOME: ["Pass `--target-root ~` explicitly."],
        WIDENING: ["Re-run with `--reinstall --stacks python,rust`."],
        TRUST: [f"`.pi/extensions` and `{policy_dir_name()}` load once you run `/trust`.",
                "", _CONFORMING_PERMISSION_SOURCE],
    }
    out = ["# Installing", "", "<!-- install-guide:begin install -->", ""]
    for heading in INSTALL_TOPICS:
        out += [f"## {heading}", "", *bodies[heading], ""]
    out += ["<!-- install-guide:end install -->", "", f"## {MARKED}", "",
            "Regions open with `<!-- install-guide:begin <name> -->` and close with "
            "`<!-- install-guide:end <name> -->`.", "",
            # MIGRATED at CR-MDB-058 C3 RED (§S7): the section says what the regions are for.
            CONFORMING_MARKED_REGIONS_USE, "",
            f"The {PYPI_PAGE} shows the whole guide, as the package readme.", ""]
    return "\n".join(out)


#: CR-MDB-058 §S6 — a ``## Releases`` body carrying every step of
#: :data:`RELEASE_STEP_PHRASES`, one unit each, the fenced release-job snippet, and no copy
#: step. It names no project and none of the Python or Pi steps' anchors, so it can sit beside
#: them without moving their first-occurrence order.
#: MIGRATED at CR-MDB-067 C3 RED (§S5): it carries the publish step, and the release-notes
#: step is written before the branch is first published (was: "On the release branch, before
#: `git flow release finish`:").
CONFORMING_RELEASES_BODY = (
    "**Two documentation steps belong to every release** (on the release branch, before "
    "finishing):\n"
    "\n"
    "1. **Release notes link to the install guide**; they never repeat its text.\n"
    "2. **A documentation review** over the doc set, before the tag.\n"
    "\n"
    "The guide's marked regions still feed generated surfaces, such as a package README.\n"
    "\n"
    "With the version bump in place, publish the branch (`git flow release publish X.Y.Z`, or\n"
    "`git flow hotfix publish X.Y.Z` for a hotfix). Every push of the branch is the rehearsal;\n"
    "`finish` deletes the remote branch.\n"
    "\n"
    "Then push `master`, `develop` and the tags in one `git push origin master develop --tags`:\n"
    "the `master` push runs the tests and creates the release, and the release event publishes.\n"
    "If the `master` run reports no version tag at `HEAD`, dispatch the workflow on `master`.\n"
    "When the `master` run or the release run fails its tests, nothing publishes: re-run the failed\n"
    "jobs, and fix a real failure on a hotfix branch.\n"
    "\n"
    "### Release notes (`CHANGELOG.md`)\n"
    "\n"
    "On the release branch, before the branch is first published:\n"
    "\n"
    "1. Write the release's section: move `[Unreleased]` under `## [X.Y.Z] - YYYY-MM-DD`.\n"
    "2. Or write it from the release's CRs, read with the Crucible client's `history` and "
    "`landings`.\n"
    "3. Add an `### Upgrading` note first whenever an operator must act.\n"
    "4. Update the compare links at the foot of the file.\n"
    "5. Commit the `CHANGELOG.md` section.\n"
    "\n"
    "The release job publishes the tag's section as the release body:\n"
    "\n"
    "```yaml\n"
    "create-release:\n"
    "  needs: test\n"
    "  if: github.ref == 'refs/heads/master'\n"
    "  steps:\n"
    "    - uses: actions/checkout@v4 # pin to a full commit SHA\n"
    "      with:\n"
    "        fetch-depth: 0\n"
    "    - name: Create the release\n"
    "      run: |\n"
    "        tag=$(git tag --points-at HEAD | grep -E '^[0-9]+\\.[0-9]+\\.[0-9]+$' || true)\n"
    "        [ -n \"$tag\" ] || { echo \"no version tag at HEAD, nothing to release\"; exit 0; }\n"
    "        [ \"$(printf '%s\\n' \"$tag\" | wc -l)\" -eq 1 ] || { echo \"more than one version tag "
    "at HEAD: $tag\" >&2; exit 1; }\n"
    "        # the tag's section, matched literally: 1.0.1 never matches 1.0.10\n"
    "        # fails when the section is missing\n"
    "        # fails when the section is empty\n"
    "        extract-section CHANGELOG.md \"$tag\" > notes.md\n"
    "        gh release create \"$tag\" --notes-file notes.md --verify-tag\n"
    "```\n"
    "\n"
    "| Stack | Packaging entry |\n"
    "|---|---|\n"
    "| `python` | `[project.urls]` `Changelog` and `Release Notes` |\n"
    "| `bun` | `CHANGELOG.md` in `package.json` `files`, copied into the package directory when "
    "it is published, if the package is not at the repository root |\n"
    "| `arduino` | the release body only |\n"
    "| `quarkus` | the release body only |\n"
    "| `java` | the release body only |\n"
    "| `rust` | the release body only |\n"
)
#: CR-MDB-067 §S5 — the ``### Pi package releases`` heading the new subsection follows; its body
#: is a placeholder naming none of the Pi step's anchors.
CONFORMING_PI_PACKAGE_HEADING = "### Pi package releases\n\nThe Pi package's own steps.\n"
#: CR-MDB-067 §S5 — a ``### Rehearsal and CI`` subsection carrying every step of
#: :data:`REHEARSAL_AND_CI_PHRASES`, one unit each. It names none of the Python or Pi steps'
#: anchors, and no unit of it carries a step of :data:`RELEASE_STEP_PHRASES` or
#: :data:`PUBLISH_STEP_PHRASES`.
CONFORMING_REHEARSAL_AND_CI = (
    "### Rehearsal and CI\n"
    "\n"
    "Each push to `release/X.Y.Z` or `hotfix/X.Y.Z` builds `X.Y.Z` with a dev marker and the CI run\n"
    "number in the stack's own form, refuses a committed version other than `X.Y.Z`, and fails when\n"
    "the release's notes are missing or empty.\n"
    "\n"
    "| Stack | Dev version | Rehearsal |\n"
    "|---|---|---|\n"
    "| `python` | `X.Y.Z.devN` | the upload to the test index |\n"
    "| `bun` | `X.Y.Z-dev.N` | the package manager's dry-run publish with a dist-tag |\n"
    "| `arduino`, `quarkus`, `java`, `rust` | — | the notes check only |\n"
    "\n"
    "The release workflow's test job runs the suite in every run: each push to a release or hotfix\n"
    "branch, each push to `master`, each published release. It runs on the stack's floor\n"
    "interpreter, in a clean home, with full history. It runs outside any agent session, the one\n"
    "place the suite runs without the stack's Crucible client. Every publish job (the rehearsal\n"
    "included) needs the test job, because a dependency gates only within one run. No CI on\n"
    "`develop` or pull requests.\n"
)
# MIGRATED at CR-MDB-067 C3 RED (§S5): the Pi heading and the Rehearsal and CI subsection
# follow the body (was: the body alone).
CONFORMING_RELEASES = ("## Releases (NON-NEGOTIABLE)\n\n" + CONFORMING_RELEASES_BODY + "\n"
                       + CONFORMING_PI_PACKAGE_HEADING + "\n" + CONFORMING_REHEARSAL_AND_CI
                       + "\n## Next\n")


CONFORMING_README = (
    "# Model B\n\n"
    "Skills, agent definitions and hooks for an agent-harness workflow.\n\n"
    "To install, follow the [install guide](docs/install-guide.md).\n"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


# ---------------------------------------------------------------------------
# Gates over the real files
# ---------------------------------------------------------------------------

class InstallGuideTopicsTest(unittest.TestCase):
    """The guide covers every install topic, each by a gate over its heading
    and the derived terms it must name."""

    def setUp(self):
        self.assertTrue(GUIDE.is_file(), f"{GUIDE.relative_to(REPO_ROOT)} must exist")
        self.text = _read(GUIDE)

    def test_guide_carries_each_topic_heading_exactly_once(self):
        self.assertEqual(check_headings(self.text), [])

    def test_prerequisites_name_every_always_requirement_in_dependency_order(self):
        self.assertEqual(check_prerequisites(self.text), [])

    def test_stack_selector_names_flag_every_stack_and_what_a_stack_installs(self):
        self.assertEqual(check_stacks(self.text), [])

    def test_preflight_section_names_every_line_prefix_and_verdict(self):
        self.assertEqual(check_preflight(self.text), [])

    def test_warnings_section_states_what_stops_working_for_every_requirement(self):
        self.assertEqual(check_warnings(self.text), [])

    def test_install_offers_name_pi_install_toolchain_installers_and_yes(self):
        self.assertEqual(check_offers(self.text), [])

    def test_missing_capabilities_section_names_the_override_flag(self):
        self.assertEqual(check_missing_capabilities(self.text), [])

    def test_outcomes_section_names_every_install_outcome_the_cli_emits(self):
        self.assertEqual(check_outcomes(self.text), [])

    def test_real_home_deploy_takes_explicit_target_root_tilde(self):
        self.assertEqual(check_real_home(self.text), [])

    def test_widening_stacks_later_names_reinstall_and_stacks(self):
        self.assertEqual(check_widening(self.text), [])

    def test_project_trust_section_names_what_it_gates_and_slash_trust(self):
        self.assertEqual(check_trust(self.text), [])


def check_required_rows_stop_an_install(text: str) -> list[str]:
    """CR-MDB-047 §S1 (VERIFY F9, user ruling): every ``required`` row stops
    an install — the Warnings section's "stop an install" sentence names
    each; Missing capabilities names the ``sandesh`` CLI and ``outdated``;
    the prerequisites never list ``sandesh`` among the recommended tools."""
    out = []
    required = [r["id"] for r in _requirements() if r["policy"] == "required"]
    flat = " ".join(_section(text, WARNINGS).split())
    sentence = next((s for s in re.split(r"(?<=\.)\s", flat) if "stop an install" in s), "")
    out += [f"{WARNINGS}: the stop-an-install sentence omits `{i}`"
            for i in required if not has_code_token(sentence, i)]
    missing = _section(text, MISSING)
    out += [f"{MISSING}: missing `{t}`" for t in ("sandesh", "outdated")
            if not has_code_token(missing, t)]
    prereq = _section(text, PREREQUISITES)
    recommended = re.search(r"\*\*Recommended tools\.\*\*.*?(?=\n\d+\. |\Z)", prereq, re.S)
    if recommended and has_code_token(recommended.group(0), "sandesh"):
        out.append(f"{PREREQUISITES}: `sandesh` is listed among the recommended tools")
    return out


class InstallGuideSandeshCliRequiredTest(unittest.TestCase):
    """CR-MDB-047 §S1 (VERIFY F9): the guide treats the ``sandesh`` CLI as
    required, as the pre-flight does."""

    def test_every_required_row_stops_an_install_in_the_guide(self):
        self.assertEqual(check_required_rows_stop_an_install(_read(GUIDE)), [])

    def test_the_python3_interpreter_is_a_required_row_the_guide_says_stops_an_install(self):
        """CR-MDB-064 §S2/§S5: ``python3`` becomes ``required``, so the Warnings
        section's stop-an-install sentence names it with the other required rows."""
        required = [r["id"] for r in _requirements() if r["policy"] == "required"]
        self.assertIn("python3", required, "CR-MDB-064 §S2: the interpreter is required")
        self.assertNotIn(f"{WARNINGS}: the stop-an-install sentence omits `python3`",
                         check_required_rows_stop_an_install(_read(GUIDE)))

    def test_checker_bites(self):
        ids = [r["id"] for r in _requirements() if r["policy"] == "required"]
        good = (f"## {PREREQUISITES}\n\n6. **Recommended tools.** x:\n   - `gh`\n\n"
                f"## {WARNINGS}\n\nOnly " + ", ".join(f"`{i}`" for i in ids)
                + f" stop an install.\n\n## {MISSING}\n\n`sandesh` below 0.4.0 is `outdated`.\n")
        self.assertEqual(check_required_rows_stop_an_install(good), [])
        self.assertIn(f"{PREREQUISITES}: `sandesh` is listed among the recommended tools",
                      check_required_rows_stop_an_install(
                          good.replace("- `gh`", "- `gh`\n   - `sandesh`")))
        self.assertIn(f"{MISSING}: missing `outdated`",
                      check_required_rows_stop_an_install(good.replace("`outdated`", "old")))
        omitted = good.replace("Only " + ", ".join(f"`{i}`" for i in ids),
                               "Only " + ", ".join(f"`{i}`" for i in ids if i != "sandesh"))
        self.assertIn(f"{WARNINGS}: the stop-an-install sentence omits `sandesh`",
                      check_required_rows_stop_an_install(omitted))


class InstallGuideInstallerSourceTest(unittest.TestCase):
    """VERIFY (cycle 100) findings 2 and 6: the installer is installed from
    PyPI (or from a source copy \u2014 a note that stays true after publishing,
    CR-MDB-038 \u00a7S4), never from a clone
    or a repository URL, and not as the Pi package; ``git`` is a
    prerequisite ahead of the installer step. CR-MDB-029's acceptance
    criteria no longer own the guide's install step."""

    def test_guide_installs_the_installer_from_pypi_after_git_with_no_repository(self):
        self.assertTrue(GUIDE.is_file(), f"{GUIDE.relative_to(REPO_ROOT)} must exist")
        self.assertEqual(check_installer_source(_read(GUIDE)), [])

    def test_cr029_acceptance_takes_only_the_readme_from_the_guide(self):
        self.assertEqual(check_cr029_acceptance(_read(CR_029)), [])


class InstallGuideStaleRerunTest(unittest.TestCase):
    """VERIFY (cycle 102) finding 3: the ``stale`` re-run guidance names
    ``--harnesses`` and ``--modelb-home`` as well as the target root and
    stacks, so following it acts on the same install."""

    def test_stale_rerun_names_every_flag_of_the_same_install(self):
        self.assertTrue(GUIDE.is_file(), f"{GUIDE.relative_to(REPO_ROOT)} must exist")
        self.assertEqual(check_stale_rerun(_read(GUIDE)), [])

    def test_stale_rerun_checker_both_ways(self):
        good = (f"## {OUTCOMES}\n\n- `stale` \u2014 newer: re-run with `--reinstall` (and your\n"
                "  `--target-root`, `--stacks`, `--harnesses` and `--modelb-home`).\n"
                "- `retired` \u2014 gone.\n")
        self.assertEqual(check_stale_rerun(good), [])
        self.assertEqual(check_stale_rerun(good.replace("`--harnesses` and ", "")),
                         [f"{OUTCOMES} `stale`: missing `--harnesses`"])
        self.assertEqual(
            check_stale_rerun(good.replace("`--modelb-home`", "home") + "`--modelb-home`\n"),
            [f"{OUTCOMES} `stale`: missing `--modelb-home`"])
        self.assertEqual(check_stale_rerun(good.replace("- `stale`", "- stale")),
                         [f"{OUTCOMES}: no `stale` bullet"])


class InstallGuideHarnessRejectedTest(unittest.TestCase):
    """CR-MDB-031 C5 F4: ``harness_rejected`` is described for the Pi-only
    installer \u2014 a stale ``install.toml`` id is a cause and the recovery is
    named; no retired harness is listed as valid. ``pi-package/README.md``
    carries the same row (it is the guide's marked regions, byte for byte)."""

    def test_harness_rejected_row_is_pi_only_and_names_the_recovery(self):
        self.assertTrue(GUIDE.is_file(), f"{GUIDE.relative_to(REPO_ROOT)} must exist")
        self.assertEqual(check_harness_rejected(_read(GUIDE)), [])

    def test_harness_rejected_checker_both_ways(self):
        good = (f"## {OUTCOMES}\n\n| Outcome | Meaning | Exit code |\n|---|---|---|\n"
                "| `harness_rejected` | `--harnesses` named something other than `pi`, or "
                "`install.toml` records a harness this version no longer supports. Re-run "
                "`modelb-axi --reinstall --target-root <dir> --stacks <stacks> --harnesses pi`. "
                "| 1 |\n")
        where = f"{OUTCOMES} `harness_rejected`"
        self.assertEqual(check_harness_rejected(good), [])
        self.assertEqual(
            check_harness_rejected(good.replace("other than `pi`",
                                                "other than `claude-code`, `Hermes` or `pi`")),
            [f"{where}: names retired `claude-code`", f"{where}: names retired `hermes`"])
        self.assertEqual(check_harness_rejected(good.replace("`install.toml`", "the record")),
                         [f"{where}: missing `install.toml`"])
        self.assertEqual(
            check_harness_rejected(good.replace(" --harnesses pi`", "`")),
            [f"{where}: missing the `modelb-axi --reinstall \u2026 --harnesses pi` recovery"])
        self.assertEqual(check_harness_rejected(good.replace("| `harness_rejected` |", "| x |")),
                         [f"{OUTCOMES}: no `harness_rejected` row"])


class InstallGuideMarkedRegionsTest(unittest.TestCase):

    def test_install_topics_sit_in_well_formed_regions_and_convention_is_documented(self):
        self.assertTrue(GUIDE.is_file(), f"{GUIDE.relative_to(REPO_ROOT)} must exist")
        self.assertEqual(check_marked_regions(_read(GUIDE)), [])

    def test_marked_regions_section_says_release_notes_link_and_regions_feed_the_readme(self):
        """CR-MDB-058 §S7: the section no longer says the regions are copied into the
        release notes; release notes link to the guide, and the regions feed the generated
        package README. ``pi-package/README.md`` staying unchanged is the mirror gate's
        (``tests.test_pi_package``); the PyPI sentence is ``check_pypi_surface``'s."""
        self.assertTrue(GUIDE.is_file(), f"{GUIDE.relative_to(REPO_ROOT)} must exist")
        self.assertEqual(check_marked_regions_use(_read(GUIDE)), [])


class InstallGuidePermissionSourceTest(unittest.TestCase):
    """CR-MDB-038 \u00a7S3 (user ruling 2026-09-24): the installer's global-policy
    report is removed, so the guide no longer describes it, and says that
    workflow permissions come from each project's policy under ``/trust``."""

    def test_guide_drops_global_report_and_states_permissions_come_from_each_project(self):
        self.assertTrue(GUIDE.is_file(), f"{GUIDE.relative_to(REPO_ROOT)} must exist")
        self.assertEqual(check_permission_source(_read(GUIDE)), [])


class InstallGuidePypiSurfaceTest(unittest.TestCase):
    """The PyPI project page is a surface derived from the guide (the whole
    guide, as the package readme); the guide says so outside every region
    (orchestrator ruling R3, 2026-09-24, cycle 106)."""

    def test_marked_regions_section_names_the_pypi_project_page_as_the_whole_guide(self):
        self.assertTrue(GUIDE.is_file(), f"{GUIDE.relative_to(REPO_ROOT)} must exist")
        self.assertEqual(check_pypi_surface(_read(GUIDE)), [])


class InstallGuideVocabularyTest(unittest.TestCase):

    def test_guide_carries_no_section_refs_cr_ids_or_internal_vocabulary(self):
        self.assertTrue(GUIDE.is_file(), f"{GUIDE.relative_to(REPO_ROOT)} must exist")
        text = _read(GUIDE)
        self.assertTrue(text.strip(), "the guide must not be empty")
        self.assertEqual(check_vocabulary(text), [])


class RepoReadmeTest(unittest.TestCase):

    def test_readme_describes_project_and_points_at_guide_without_installer_commands(self):
        self.assertTrue(README.is_file(), "README.md must exist at the repo root")
        self.assertEqual(check_readme(_read(README)), [])


class ReleaseDocsTest(unittest.TestCase):

    # MIGRATED at CR-MDB-058 C3 RED (§S6; was
    # test_git_workflow_releases_names_guide_copy_and_documentation_review): the copy step is
    # retired; check_release_steps carries the new steps, one test per group of them.
    def test_git_workflow_releases_links_release_notes_to_the_guide_and_keeps_the_review(self):
        self.assertEqual(release_step_faults(_read(GIT_WORKFLOW_SKILL), DOCUMENTATION_STEPS), [])

    def test_git_workflow_releases_no_longer_copies_the_marked_regions_into_release_notes(self):
        self.assertEqual(release_step_faults(_read(GIT_WORKFLOW_SKILL), RETIRED_COPY_STEP), [])

    def test_git_workflow_releases_names_the_release_notes_step_and_its_four_parts(self):
        self.assertEqual(release_step_faults(_read(GIT_WORKFLOW_SKILL), RELEASE_NOTES_STEP), [])

    def test_git_workflow_releases_names_the_release_job_snippet_passing_notes_file(self):
        self.assertEqual(release_step_faults(_read(GIT_WORKFLOW_SKILL), RELEASE_JOB_SNIPPET), [])

    def test_git_workflow_releases_names_the_packaging_entries_of_the_six_stacks(self):
        self.assertEqual(release_step_faults(_read(GIT_WORKFLOW_SKILL), PACKAGING_ENTRIES), [])

    def test_git_workflow_releases_passes_the_whole_release_step_gate(self):
        self.assertEqual(check_release_steps(_read(GIT_WORKFLOW_SKILL)), [])

    def test_git_workflow_releases_names_the_four_python_release_steps_in_order(self):
        self.assertEqual(check_python_release_steps(_read(GIT_WORKFLOW_SKILL)), [])

    def test_git_workflow_releases_names_the_pi_package_publish_and_isolated_install(self):
        self.assertEqual(check_pi_package_release_steps(_read(GIT_WORKFLOW_SKILL)), [])

    # CR-MDB-067 §S5 — the release flow's publish step, the notes before the first publish, the
    # Rehearsal and CI subsection and the retired phrases, one test per group.
    def test_git_workflow_releases_publishes_the_branch_and_every_push_is_the_rehearsal(self):
        self.assertEqual(release_step_faults(_read(GIT_WORKFLOW_SKILL), PUBLISH_STEP), [])

    def test_git_workflow_releases_writes_the_notes_before_the_branch_is_first_published(self):
        self.assertEqual(release_step_faults(_read(GIT_WORKFLOW_SKILL), NOTES_BEFORE_PUBLISH), [])

    def test_git_workflow_releases_carries_the_rehearsal_and_ci_subsection_after_pi_releases(self):
        self.assertEqual(release_step_faults(_read(GIT_WORKFLOW_SKILL), REHEARSAL_AND_CI), [])

    def test_git_workflow_releases_names_none_of_the_retired_rehearsal_and_credential_phrases(self):
        self.assertEqual(release_step_faults(_read(GIT_WORKFLOW_SKILL), RETIRED_PHRASES), [])

    # CR-MDB-070 §S6 — the one-push release flow and its recovery by dispatch on master.
    def test_git_workflow_releases_pushes_once_releases_from_master_and_recovers_by_dispatch(self):
        self.assertEqual(release_step_faults(_read(GIT_WORKFLOW_SKILL), RELEASE_FLOW), [])

    # CR-MDB-070 C4 RED (VERIFY F1/F2/F3/F6) — the texts of the release job, the publish steps and the
    # recovery from a red run, one test per finding.
    def test_git_workflow_releases_snippet_refuses_more_than_one_version_tag_at_head(self):
        fault = (f"## Releases: {RELEASE_JOB_SNIPPET}: the snippet does not refuse more than one "
                 "version tag at HEAD")
        self.assertNotIn(fault, check_release_steps(_read(GIT_WORKFLOW_SKILL)))

    def test_git_workflow_releases_snippet_checkout_says_to_pin_it_to_a_full_commit_sha(self):
        snippet = release_job_snippet(_read(GIT_WORKFLOW_SKILL))
        self.assertIsNotNone(snippet, "## Releases carries the release-job snippet")
        self.assertEqual(checkout_pin_faults(snippet or ""), [])

    def test_git_workflow_releases_never_says_the_tags_release_job(self):
        self.assertNotIn(f"## Releases: {RETIRED_PHRASES}: names \"the tag's release job\"",
                         check_release_steps(_read(GIT_WORKFLOW_SKILL)))

    def test_git_workflow_releases_publish_steps_publish_on_the_release_event_after_tests_and_guard(
            self):
        self.assertEqual(publish_job_faults(_read(GIT_WORKFLOW_SKILL)), [])

    def test_git_workflow_releases_push_paragraph_says_a_red_run_publishes_nothing_and_recovers(self):
        self.assertEqual(release_step_faults(_read(GIT_WORKFLOW_SKILL), RED_RUN_RECOVERY), [])

    def test_pi_package_cr_s1_names_guide_marked_regions_as_readme_source(self):
        self.assertEqual(check_cr029_s1(_read(CR_029)), [])


# ---------------------------------------------------------------------------
# Checker proofs — a conforming guide passes; each violation is caught
# ---------------------------------------------------------------------------

class InstallGuideCheckerProofTest(unittest.TestCase):
    """Proves the gates both ways without the real files: the conforming
    synthetic guide (built from the derived vocabulary) passes every checker,
    and each targeted violation is reported."""

    def setUp(self):
        self.guide = conforming_guide()

    def test_conforming_guide_passes_every_checker(self):
        self.assertEqual(check_headings(self.guide), [])
        for heading, checker in TOPIC_CHECKERS.items():
            with self.subTest(topic=heading):
                self.assertEqual(checker(self.guide), [])
        self.assertEqual(check_marked_regions(self.guide), [])
        self.assertEqual(check_vocabulary(self.guide), [])
        self.assertEqual(check_installer_source(self.guide), [])
        self.assertEqual(check_pypi_surface(self.guide), [])
        self.assertEqual(check_permission_source(self.guide), [])
        self.assertEqual(check_marked_regions_use(self.guide), [])

    def test_permission_source_faults_are_reported(self):
        stated = _CONFORMING_PERMISSION_SOURCE
        cases = {
            **{f"describes `{term}`": (
                self.guide + f"\nThe summary carries `{term}`.\n",
                [f"guide: must not describe the global-policy report: `{term}`"])
               for term in RETIRED_GLOBAL_REPORT_TERMS},
            "not stated": (
                self.guide.replace(stated, "Pi reads the policy."),
                [f"{TRUST}: must state that workflow permissions come from each project's "
                 "policy, loaded under `/trust`"]),
            "global, not each project's": (
                self.guide.replace("each project's policy", "your global policy"),
                [f"{TRUST}: must state that workflow permissions come from each project's "
                 "policy, loaded under `/trust`"]),
            "no `/trust` in the statement": (
                self.guide.replace("loaded once you run `/trust` in the project", "loaded later"),
                [f"{TRUST}: must state that workflow permissions come from each project's "
                 "policy, loaded under `/trust`"]),
            "stated outside Project trust": (
                self.guide.replace(stated, "").replace(
                    f"## {WIDENING}\n", f"## {WIDENING}\n\n{stated}\n"),
                [f"{TRUST}: must state that workflow permissions come from each project's "
                 "policy, loaded under `/trust`"]),
        }
        for label, (text, expected) in cases.items():
            with self.subTest(case=label):
                self.assertEqual(check_permission_source(text), expected)
        wrapped = self.guide.replace(stated, "Workflow permissions come from\neach project's "
                                            "policy, loaded under\n`/trust`.")
        self.assertEqual(check_permission_source(wrapped), [],
                         "a statement wrapped across lines still counts")
        self.assertEqual(
            check_permission_source(self.guide + "\nOnly your global policy applies then.\n"), [],
            "naming Pi's global policy is not describing the installer's report")

    def test_expiring_source_copy_note_is_reported(self):
        """CR-MDB-038 \u00a7S4: the CR-MDB-037 note ("until then ... from the
        maintainer") is rejected; each expiring word is caught alone."""
        old = self.guide.replace(_CONFORMING_INSTALLER_LINE, _EXPIRING_INSTALLER_LINE)
        self.assertEqual(check_installer_source(old),
                         [f"{PREREQUISITES}: the source-copy note must not say 'until'"])
        for injected, word in (("; until PyPI, or", "until"),
                               ("; in the interim, or", "interim"),
                               ("; before the first\nrelease, or", "first release"),
                               ("; Until publishing, or", "until")):
            with self.subTest(word=injected):
                text = self.guide.replace("; or", injected, 1)
                self.assertEqual(check_installer_source(text),
                                 [f"{PREREQUISITES}: the source-copy note must not say {word!r}"])
        self.assertEqual(
            check_installer_source(self.guide.replace("; or,", "; or, continuously")), [],
            "words merely containing the letters (continuously) are not flagged")

    def test_pypi_surface_faults_are_reported(self):
        line = f"The {PYPI_PAGE} shows the whole guide, as the package readme."
        cases = {
            "not named": (self.guide.replace(line, "The release notes are copied."),
                          f"section '{MARKED}' must name the {PYPI_PAGE}"),
            "not the whole guide": (
                self.guide.replace(line, f"The {PYPI_PAGE} shows the marked regions, as the "
                                         "package readme."),
                f"section '{MARKED}' must say the {PYPI_PAGE} shows the whole guide as the "
                "package readme"),
            "only inside a region": (
                self.guide.replace(line, "").replace(
                    "<!-- install-guide:end install -->", f"{line}\n\n<!-- install-guide:end install -->"),
                f"section '{MARKED}' must name the {PYPI_PAGE}"),
            "split across paragraphs": (
                self.guide.replace(line, f"The {PYPI_PAGE} exists.\n\nThe whole guide is the readme."),
                f"section '{MARKED}' must say the {PYPI_PAGE} shows the whole guide as the "
                "package readme"),
        }
        for label, (text, expected) in cases.items():
            with self.subTest(case=label):
                self.assertEqual(check_pypi_surface(text), [expected])
        wrapped = self.guide.replace(line, "The PyPI project\npage shows the whole guide,\n"
                                           "as the package README.")
        self.assertEqual(check_pypi_surface(wrapped), [])

    def test_installer_source_faults_are_reported(self):
        git_line = "- `git`, from your package manager.\n"
        cases = {
            "no PyPI install": (
                self.guide.replace(f"`{INSTALLER_INSTALL}`", "the installer"),
                f"{PREREQUISITES}: the installer step must name `{INSTALLER_INSTALL}`"),
            "no PyPI": (self.guide.replace("from PyPI", "from the index"),
                        f"{PREREQUISITES}: must say the installer comes from PyPI"),
            "no source-copy note": (
                self.guide.replace(f"`{SOURCE_COPY_INSTALL}`", "a copy"),
                f"{PREREQUISITES}: must carry the source-copy note (`{SOURCE_COPY_INSTALL}` "
                "from a source copy)"),
            "note without 'source copy'": (
                self.guide.replace("from a source copy:", "otherwise:"),
                f"{PREREQUISITES}: must carry the source-copy note (`{SOURCE_COPY_INSTALL}` "
                "from a source copy)"),
            "Pi package claim": (
                self.guide.replace("from PyPI:", "from PyPI, as the Model B Pi package:"),
                f"{PREREQUISITES}: must not claim the installer ships as the Pi package: "
                "'Pi package'"),
            "git clone": (self.guide + "\nRun `git clone x`.\n", "git clone: 'git clone'"),
            "repository URL": (
                self.guide + "\nSee https://github.com/owner/model-b.\n",
                "repository URL: 'https://github.com/owner/model-b.'"),
            "git+ source": (self.guide + "\n`uv tool install git+https://x.invalid/y`\n",
                            "repository URL: 'git+https://x.invalid/y`'"),
            "git missing": (self.guide.replace(git_line, ""),
                            f"{PREREQUISITES}: `git` must be named"),
            "git after installer": (
                self.guide.replace(git_line, "").replace(
                    _CONFORMING_INSTALLER_LINE, _CONFORMING_INSTALLER_LINE + "\n" + git_line.rstrip()),
                f"{PREREQUISITES}: `git` must come before the installer step"),
        }
        for label, (text, expected) in cases.items():
            with self.subTest(case=label):
                self.assertIn(expected, check_installer_source(text))
        self.assertEqual(
            check_installer_source(self.guide + "\nThe GitHub CLI, from https://cli.github.com.\n"),
            [], "a host without an owner/repo path is not a repository URL")

    def test_cr029_acceptance_checker_both_ways(self):
        good = ("## Acceptance criteria\n\n- [ ] The package README is the guide's marked "
                "regions, copied verbatim.\n\n## Risk\n")
        self.assertEqual(check_cr029_acceptance(good), [])
        self.assertEqual(
            check_cr029_acceptance(good.replace("guide's marked regions", "guide")),
            ["ACs: the Pi package README must come from the guide's marked regions"])
        self.assertEqual(
            check_cr029_acceptance(good.replace(
                "## Risk", "- [ ] check_prerequisites is migrated.\n\n## Risk")),
            ["ACs: must not name 'check_prerequisites'"])
        self.assertEqual(
            check_cr029_acceptance(good.replace(
                "## Risk", "- [ ] The guide's install step names it.\n\n## Risk")),
            ["ACs: must not name 'install step'"])

    def test_derived_vocabulary_matches_the_code(self):
        self.assertIn("preflight_failed", install_outcomes())
        self.assertIn("stacks_rejected", install_outcomes())
        self.assertIn("already_installed", install_outcomes())
        self.assertEqual(verdicts(), ["detected", "absent", "unknown", "installed"])
        self.assertEqual(preflight_prefixes(), ("harness", "deps", "stack <name>"))
        self.assertEqual(policy_dir_name(), "pi-permission-system")
        with self.assertRaises(AssertionError) as ctx:
            parser_flag("--no-such-flag")
        self.assertIn("--no-such-flag", str(ctx.exception))

    def test_derived_required_terms_do_not_collide_with_blocklist(self):
        rows = _requirements()
        terms = [*install_outcomes(), *known_stacks(), *verdicts(),
                 *sorted(_parser_flags()), *toolchain_installer_terms(),
                 *(r["id"] for r in rows), *(r["provider"] for r in rows),
                 *(f for r in rows for f in r["asset_families"])]
        self.assertEqual([t for t in terms if check_vocabulary(t)], [])

    def test_missing_outcome_is_reported(self):
        broken = self.guide.replace("- `preflight_failed`\n", "")
        self.assertEqual(check_outcomes(broken), [f"{OUTCOMES}: missing `preflight_failed`"])

    def test_term_only_in_prose_does_not_count(self):
        broken = self.guide.replace("`/trust`", "/trust")
        self.assertEqual(check_trust(broken), [f"{TRUST}: missing `/trust`"])

    def test_target_root_with_other_path_does_not_count(self):
        broken = self.guide.replace("`--target-root ~`", "`--target-root ~/sandbox`")
        self.assertEqual(check_real_home(broken), [f"{REAL_HOME}: missing `--target-root ~`"])

    def test_term_in_wrong_section_does_not_count(self):
        broken = self.guide.replace("Re-run with `--reinstall --stacks python,rust`.",
                                    "Re-run later.")
        self.assertEqual(check_widening(broken), [f"{WIDENING}: missing `--stacks`",
                                                  f"{WIDENING}: missing `--reinstall`"])

    def test_duplicate_or_missing_heading_is_reported(self):
        broken = self.guide.replace(f"## {TRUST}\n", "## Trusting\n")
        self.assertEqual(check_headings(broken), [f"heading '## {TRUST}' appears 0 times (want 1)"])

    def test_prerequisites_out_of_dependency_order_is_reported(self):
        rows = _requirements()
        uv = next(r for r in rows if r["id"] == "uv")["remediation"]
        broken = self.guide.replace(f"- `{uv}`\n", "").replace(
            _CONFORMING_INSTALLER_LINE, f"{_CONFORMING_INSTALLER_LINE}\n- `{uv}`")
        self.assertEqual(len([v for v in check_prerequisites(broken) if "must precede" in v]), 1)
        no_pi = self.guide.replace("Install Pi first; its packages come next.", "Start here.")
        self.assertEqual(len([v for v in check_prerequisites(no_pi) if "Pi must" in v]),
                         len([r for r in rows if r["tier"] == 1]))

    def test_warning_line_without_asset_family_is_reported(self):
        row = next(r for r in _requirements() if r["id"] == "sandesh")
        broken = self.guide.replace(
            f"- `sandesh`: the {row['asset_families'][0]} will not work", "- `sandesh`: warns")
        self.assertEqual([v for v in check_warnings(broken) if "`sandesh`" in v],
                         [f"{WARNINGS}: no line names `sandesh` with one of "
                          f"{list(row['asset_families'])}"])

    def test_missing_preflight_prefix_or_verdict_is_reported(self):
        broken = self.guide.replace("stack <name>: x=y", "stacks x=y").replace("`installed`", "")
        self.assertEqual(check_preflight(broken),
                         [f"{PREFLIGHT}: missing pre-flight line `stack <name>:`",
                          f"{PREFLIGHT}: missing `installed`"])

    def test_offers_without_toolchain_installer_is_reported(self):
        term = toolchain_installer_terms()[0]
        broken = self.guide.replace(f"`{term}`", "a toolchain")
        self.assertEqual(check_offers(broken),
                         [f"{OFFERS}: must show that toolchain installers are offered"])

    def test_marker_faults_are_reported(self):
        begin = "<!-- install-guide:begin install -->"
        end = "<!-- install-guide:end install -->"
        cases = {
            "no region": (self.guide.replace(begin + "\n", "").replace(end + "\n", ""),
                          "no marked region"),
            "nested": (self.guide.replace(begin, begin + "\n<!-- install-guide:begin inner -->", 1),
                       "line 4: region 'inner' nested in 'install'"),
            "never ended": (self.guide.replace(end + "\n", ""), "region 'install' is never ended"),
            "malformed": (self.guide.replace(begin, "<!-- install-guide:begin Install -->"),
                          "line 3: malformed marker '<!-- install-guide:begin Install -->'"),
            "topic outside": (self.guide.replace(f"## {TRUST}", f"{end}\n\n## {TRUST}", 1).replace(
                f"{end}\n\n## {MARKED}", f"## {MARKED}"),
                f"section '{TRUST}' is not wholly inside a marked region"),
            "convention inside": (self.guide.replace(f"{end}\n\n## {MARKED}", f"## {MARKED}")
                                  + f"\n{end}\n",
                                  f"section '{MARKED}' must sit outside every marked region"),
            "convention undocumented": (self.guide.replace(
                "`<!-- install-guide:end <name> -->`", "an end marker"),
                f"section '{MARKED}' must show the end marker in code"),
        }
        for label, (text, expected) in cases.items():
            with self.subTest(case=label):
                self.assertIn(expected, check_marked_regions(text))

    def test_internal_vocabulary_is_reported(self):
        for injected, expected in (
                ("See §S1.", "section sign: '§'"),
                ("Per CR-MDB-037.", "CR id: 'CR-MDB-037'"),
                ("Decision D11.", "decision id: 'D11'"),
                ("The PRD says.", "PRD reference: 'PRD'"),
                ("DN-scaffold notes.", "design-note reference: 'DN-'"),
                ("The RED agent.", "internal vocabulary: 'RED'"),
                ("Next wave.", "internal vocabulary: 'wave'"),
                ("tier-1 tools.", "internal vocabulary: 'tier-1'"),
                ("A user ruling.", "internal vocabulary: 'user ruling'"),
                ("The orchestrator.", "internal vocabulary: 'orchestrator'")):
            with self.subTest(injected=injected):
                self.assertEqual(check_vocabulary(self.guide + "\n" + injected + "\n"), [expected])
        self.assertEqual(check_vocabulary("lifecycle, microwave, recycled, Redis"), [])

    def test_readme_checker_both_ways(self):
        self.assertEqual(check_readme(CONFORMING_README), [])
        bad = {
            "no link": (CONFORMING_README.replace("(docs/install-guide.md)", "(docs/other.md)"),
                        "no markdown link to docs/install-guide.md"),
            "command line": (CONFORMING_README + "\n```\nmodelb-axi --yes --target-root ~\n```\n",
                             "installer command line: 'modelb-axi --yes --target-root ~'"),
            "command span": (CONFORMING_README + "\nRun `uv tool install .` first.\n",
                             "installer command line: 'uv tool install .'"),
            "prompt line": (CONFORMING_README + "\n    $ pi install npm:x\n",
                            "installer command line: 'pi install npm:x'"),
            "too long": (CONFORMING_README + "\n".join(f"line {i}" for i in range(20)),
                         "23 non-blank lines (max 20)"),
            "no title": (CONFORMING_README.replace("# Model B", "Model B"),
                         "first line must be a '# ' title"),
            "no description": (CONFORMING_README.replace(
                "Skills, agent definitions and hooks for an agent-harness workflow.", "## About"),
                "the title must be followed by a description paragraph"),
        }
        for label, (text, expected) in bad.items():
            with self.subTest(case=label):
                self.assertIn(expected, check_readme(text))

    # MIGRATED at CR-MDB-058 C3 RED (§S6): the release-step half moved to
    # test_release_step_gate_passes_the_conforming_section_and_bites_once_per_step on
    # CONFORMING_RELEASES (was the copy-step sample "Copy the install guide's marked regions
    # verbatim into the release notes, then hold a documentation review").
    def test_release_and_cr029_checkers_both_ways(self):
        self.assertEqual(check_release_steps("## Other\n\nverbatim release notes\n"),
                         ["no '## Releases' section"])
        cr = ("### §S1 — Layout\nThe README is the install-guide.md marked regions.\n"
              "### §S2 — Other\n")
        self.assertEqual(check_cr029_s1(cr), [])
        self.assertEqual(check_cr029_s1(cr.replace("marked regions", "text")),
                         ["§S1: missing 'marked region'"])

    # MIGRATED at CR-MDB-067 C3 RED (§S5): the rehearse step is each release-branch push uploading
    # the stamped dev version to TestPyPI through Trusted Publishing, and the upload step names no
    # token anywhere (was: "Rehearse: upload to TestPyPI and install into an isolated tool
    # directory"; "upload to PyPI with a token the user supplies at upload time").
    def test_python_release_steps_checker_both_ways(self):
        good = ("## Releases (NON-NEGOTIABLE)\n\n"
                "### Publishing a Python package\n\n"
                "1. On the release branch, set the version in its\n   single source, then "
                "build with `uv build`.\n"
                "2. Rehearse: each release-branch push uploads the stamped dev version to\n"
                "   TestPyPI through Trusted Publishing.\n"
                "3. Publish: after `git flow release finish`, the tag's release job uploads to\n"
                "   PyPI through Trusted Publishing, with no token anywhere.\n"
                "4. Post-release: install from PyPI, replace the previous installation\n"
                "   (`--reinstall --target-root ~`), remove workflow entries from any global\n"
                "   permission config in favour of per-project policies, and confirm a\n"
                "   dispatched agent in a trusted project runs without a permission prompt.\n"
                "\n## Next\n\nuv build, TestPyPI, --reinstall\n")
        self.assertEqual(check_python_release_steps(good), [])
        self.assertEqual(check_python_release_steps(
            good.replace("each release-branch push", "each release-branch\n   push")
            .replace("no token anywhere", "no token\n   anywhere")), [],
            "a step wrapped across lines counts")
        bad = {
            "no build": (good.replace("`uv build`", "make"),
                         "## Releases: build: missing 'uv build'"),
            "no single-source version": (good.replace("version in its", "version in"),
                                         "## Releases: build: missing "
                                         "'version in its single source'"),
            "no rehearsal": (good.replace("TestPyPI", "a staging index"),
                             "## Releases: testpypi rehearsal: missing 'testpypi'"),
            "a manual rehearsal": (good.replace("each release-branch push uploads",
                                                "a manual run uploads"),
                                   "## Releases: testpypi rehearsal: missing "
                                   "'each release-branch push'"),
            "no stamped dev version": (good.replace("the stamped dev version",
                                                    "the release candidate"),
                                       "## Releases: testpypi rehearsal: missing "
                                       "'stamped dev version'"),
            "no trusted publishing": (good.replace("Trusted Publishing", "a stored token"),
                                      "## Releases: testpypi rehearsal: missing "
                                      "'trusted publishing'"),
            "a token kept": (good.replace(", with no token anywhere",
                                          " with a token the user supplies"),
                             "## Releases: pypi upload: missing 'no token anywhere'"),
            "no finish": (good.replace("after `git flow release finish`,", "after the tag,"),
                          "## Releases: pypi upload: missing 'git flow release finish'"),
            "no reinstall": (good.replace("--reinstall ", ""),
                             "## Releases: post-release maintenance: missing '--reinstall'"),
            "global kept": (good.replace("global\n   permission config", "settings"),
                            "## Releases: post-release maintenance: missing "
                            "'global permission config'"),
            "no prompt-free check": (good.replace("without a permission prompt", ""),
                                     "## Releases: post-release maintenance: missing "
                                     "'without a permission prompt'"),
            "project named": (good.replace("(`--reinstall", "(`modelb-axi --reinstall"),
                              "## Releases: names project 'modelb'"),
        }
        for label, (text, expected) in bad.items():
            with self.subTest(case=label):
                self.assertIn(expected, check_python_release_steps(text))
        reordered = ("## Releases\n\n"
                     "1. Post-release: install from PyPI with `--reinstall`, remove the global "
                     "permission config entries for per-project policies, confirm a trusted "
                     "project runs without a permission prompt.\n"
                     "2. Set the version in its single source; `uv build`.\n"
                     "3. Each release-branch push uploads the stamped dev version to TestPyPI "
                     "through Trusted Publishing.\n"
                     "4. After git flow release finish, the release job uploads with no token "
                     "anywhere.\n")
        self.assertEqual(check_python_release_steps(reordered),
                         ["## Releases: python release steps out of order"])
        swapped = good.replace(
            "2. Rehearse: each release-branch push uploads the stamped dev version to\n"
            "   TestPyPI through Trusted Publishing.\n", "").replace(
            "4. Post-release:", "4. Rehearse: each release-branch push uploads the stamped dev "
            "version to TestPyPI through Trusted Publishing.\n5. Post-release:")
        self.assertEqual(check_python_release_steps(swapped),
                         ["## Releases: python release steps out of order"],
                         "the publish anchor 'no token anywhere' must follow 'testpypi'")
        self.assertEqual(check_python_release_steps("## Other\n\nuv build TestPyPI\n"),
                         ["no '## Releases' section"])

    # MIGRATED at CR-MDB-067 C3 RED (§S5): the publish step runs through Trusted Publishing, a
    # new package's one-time token kept as a repository secret, then 2FA required (was: "with
    # credentials the user supplies at publish time; never store them").
    def test_pi_package_release_steps_checker_both_ways(self):
        pi_step = ("### Publishing a Pi package\n\n"
                   "1. Once the version is set, the tag's release job runs `npm publish --access\n"
                   "   public` through Trusted Publishing; the first publish of a new package\n"
                   "   uses a one-time token kept as a repository secret, then the trusted\n"
                   "   publisher is added, 2FA is required and the token deleted.\n"
                   "2. Point `PI_CODING_AGENT_DIR` at a scratch path, `pi install` the\n"
                   "   published version there, and confirm the extension loads.\n"
                   "3. Live check, post-release: installed into the real Pi configuration,\n"
                   "   confirm Pi loads the worktree extension there.\n")
        good = ("## Releases (NON-NEGOTIABLE)\n\n" + pi_step + "\n## Next\n\n"
                "npm publish PI_CODING_AGENT_DIR anthill-tec\n")
        self.assertEqual(check_pi_package_release_steps(good), [])
        self.assertEqual(check_pi_package_release_steps(
            good.replace("Trusted Publishing", "Trusted\n   Publishing")
            .replace("repository secret", "repository\n   secret")), [],
            "a term wrapped across lines counts")
        bad = {
            "no publish": (good.replace("`npm publish --access\n   public`", "`npm pack`"),
                           "## Releases: npm publish: missing 'npm publish'"),
            "scoped package not public": (good.replace(" --access\n   public", ""),
                                          "## Releases: npm publish: missing '--access public'"),
            "no live check": (good.replace("Live check, post-release", "Post-release"),
                              "## Releases: live check: missing 'live check'"),
            "live check not in the real configuration": (
                good.replace("the real Pi configuration", "a scratch directory"),
                "## Releases: live check: missing 'real pi configuration'"),
            "watcher named": (good.replace("confirm Pi loads", "start the watcher and confirm Pi loads"),
                              "## Releases: live check: names a watcher"),
            "worktree extension unconfirmed": (
                good.replace("Pi loads the worktree extension there", "the session wakes"),
                "## Releases: live check: missing 'loads the worktree extension'"),
            "not a pi package": (good.replace("a Pi package", "an npm module"),
                                 "## Releases: npm publish: missing 'pi package'"),
            "version not set first": (good.replace("Once the version is set, the tag's", "The tag's"),
                                      "## Releases: npm publish: missing 'version is set'"),
            "no trusted publishing": (good.replace("through Trusted Publishing",
                                                   "with the stored npm token"),
                                      "## Releases: npm publish: missing 'trusted publishing'"),
            "token not a repository secret": (good.replace("kept as a repository secret",
                                                           "kept in a local file"),
                                              "## Releases: npm publish: missing "
                                              "'repository secret'"),
            "no 2fa": (good.replace("2FA is required and ", ""),
                       "## Releases: npm publish: missing '2fa'"),
            "not isolated": (good.replace("Point `PI_CODING_AGENT_DIR` at a scratch path,",
                                          "Then"),
                             "## Releases: isolated pi install: missing 'pi_coding_agent_dir'"),
            "no pi install": (good.replace("`pi install` the", "fetch the"),
                              "## Releases: isolated pi install: missing 'pi install'"),
            "local copy installed": (good.replace("published version", "working tree"),
                                     "## Releases: isolated pi install: missing "
                                     "'published version'"),
            "load unconfirmed": (good.replace(", and confirm the extension loads", ""),
                                 "## Releases: isolated pi install: missing 'extension loads'"),
            "project named": (good.replace("`pi install` the", "`pi install npm:@x/modelb-pi`, the"),
                              "## Releases: names project 'modelb'"),
            "scope named": (good.replace("`pi install` the",
                                         "`pi install npm:@anthill-tec/x`, the"),
                            "## Releases: names project 'anthill-tec'"),
        }
        for label, (text, expected) in bad.items():
            with self.subTest(case=label):
                self.assertIn(expected, check_pi_package_release_steps(text))
        reordered = ("## Releases\n\nFor a Pi package: point PI_CODING_AGENT_DIR at a scratch "
                     "path, pi install the published version, confirm the extension loads. "
                     "Once the version is set, npm publish --access public through Trusted "
                     "Publishing, a first-publish token kept as a repository secret, then 2FA "
                     "required. Live check: in the real Pi "
                     "configuration, Pi loads the worktree extension.\n")
        self.assertEqual(check_pi_package_release_steps(reordered),
                         ["## Releases: pi package steps out of order"])
        live_first = ("## Releases\n\nLive check: in the real Pi configuration, Pi loads the "
                      "worktree extension. For a Pi package, once "
                      "the version is set, npm publish --access public through Trusted "
                      "Publishing (a first-publish token kept as a repository secret, then 2FA "
                      "required); then point PI_CODING_AGENT_DIR at a "
                      "scratch path, pi install the published version, confirm the extension "
                      "loads.\n")
        self.assertEqual(check_pi_package_release_steps(live_first),
                         ["## Releases: pi package steps out of order"])
        self.assertEqual(check_pi_package_release_steps("## Other\n\nnpm publish\n"),
                         ["no '## Releases' section"])

    def test_release_step_gate_passes_the_conforming_section_and_bites_once_per_step(self):
        """CR-MDB-058 §S6: each step of :data:`RELEASE_STEP_PHRASES` taken out of the
        conforming section is reported alone, by its own group and label."""
        good = CONFORMING_RELEASES
        self.assertEqual(check_release_steps(good), [])
        docs, notes, snippet, packaging = (DOCUMENTATION_STEPS, RELEASE_NOTES_STEP,
                                           RELEASE_JOB_SNIPPET, PACKAGING_ENTRIES)
        cases = {
            (docs, "release notes link to the install guide"):
                ("link to the install guide", "are written by hand"),
            (docs, "the marked regions feed generated surfaces such as a package README"):
                ("still feed generated surfaces, such as a package README", "are kept"),
            (docs, "a documentation review"): ("**A documentation review**", "**A check**"),
            (notes, "move [Unreleased] under ## [X.Y.Z] - YYYY-MM-DD"):
                ("move `[Unreleased]` under", "fill in"),
            (notes, "or write it from the release's CRs (history and landings)"):
                (" and `landings`", ""),
            (notes, "an ### Upgrading note first when an operator must act"):
                ("first whenever", "whenever"),
            (notes, "update the compare links"):
                ("4. Update the compare links at the foot of the file.\n", ""),
            (notes, "commit"): ("5. Commit the `CHANGELOG.md` section.\n", ""),
            (snippet, "the tag's section is matched literally"):
                ("matched literally: 1.0.1 never matches 1.0.10", "taken as it is"),
            (snippet, "it fails on a missing section"):
                ("    # fails when the section is missing\n", ""),
            (snippet, "it fails on an empty section"):
                ("    # fails when the section is empty\n", ""),
            (PACKAGING_ENTRIES, "python: [project.urls] Changelog and Release Notes"):
                ("`[project.urls]` `Changelog`", "`Changelog`"),
            (packaging, "bun: CHANGELOG.md in package.json files, copied into the package "
                        "directory at publish time when the package is not at the repository "
                        "root"):
                (", if the package is not at the repository root", ""),
            **{(packaging, f"{stack}: the release body only"):
               (f"| `{stack}` | the release body only |", f"| `{stack}` | a package README |")
               for stack in RELEASE_BODY_ONLY_STACKS},
        }
        self.assertEqual(len(cases), len(RELEASE_STEP_PHRASES), "one case per step")
        for (group, label), (old, new) in cases.items():
            with self.subTest(step=label):
                self.assertIn(old, good)
                self.assertEqual(check_release_steps(good.replace(old, new)),
                                 [f"## Releases: {group}: {label}"])
        self.assertEqual(
            check_release_steps(good.replace("`package.json` `files`", "the tarball")),
            [f"## Releases: {packaging}: bun: CHANGELOG.md in package.json files, copied into "
             "the package directory at publish time when the package is not at the repository "
             "root"])
        wrapped = good.replace("Update the compare links", "Update the compare\n   links")
        self.assertEqual(check_release_steps(wrapped), [], "a step wrapped across lines counts")
        split = good.replace("4. Update the compare links at the foot of the file.\n",
                             "4. Update the file's foot.\n\nThe compare links are listed there.\n\n")
        self.assertEqual(check_release_steps(split),
                         [f"## Releases: {notes}: update the compare links"],
                         "a step's words split across two units do not count")
        outside = good.replace("5. Commit the `CHANGELOG.md` section.\n", "").replace(
            "\n## Next\n", "\n## Next\n\nCommit the section.\n")
        self.assertEqual(check_release_steps(outside), [f"## Releases: {notes}: commit"],
                         "a step counts only inside ## Releases")
        self.assertEqual(release_step_faults(good.replace(" and `landings`", ""), notes),
                         [f"## Releases: {notes}: or write it from the release's CRs "
                          "(history and landings)"])
        self.assertEqual(release_step_faults(good.replace(" and `landings`", ""), packaging), [])

    def test_release_step_gate_flags_the_retired_copy_step_but_not_a_forbidden_copy(self):
        """CR-MDB-058 §S6: the copy step ("Install text from its single source … copy
        those marked regions verbatim into the release notes") is reported; a sentence that
        forbids the copy is not."""
        fault = (f"## Releases: {RETIRED_COPY_STEP}: still says to copy the marked regions "
                 "into the release notes")
        old_step = ("3. **Install text from its single source.** If the project keeps an install "
                    "guide with marked\n   regions, copy those marked regions verbatim into the "
                    "release notes (and into any other\n   surface that takes them, such as a "
                    "package README).\n")
        anchor = "2. **A documentation review** over the doc set, before the tag.\n"
        self.assertEqual(check_release_steps(CONFORMING_RELEASES.replace(anchor, anchor + old_step)),
                         [fault])
        copy_only = CONFORMING_RELEASES.replace(
            anchor, anchor + "3. Copy the marked regions into the release notes.\n")
        self.assertEqual(check_release_steps(copy_only), [fault])
        heading_only = CONFORMING_RELEASES.replace(
            anchor, anchor + "3. **Install text from its single source.**\n")
        self.assertEqual(check_release_steps(heading_only), [fault])
        for forbidden in ("3. Never copy the marked regions into the release notes.\n",
                          "3. Do not copy the marked regions into the release notes.\n",
                          "3. They link to the guide instead of copying its marked regions.\n"):
            with self.subTest(forbidden=forbidden):
                self.assertEqual(
                    check_release_steps(CONFORMING_RELEASES.replace(anchor, anchor + forbidden)), [])

    def test_release_job_snippet_must_be_a_fenced_step_passing_notes_file(self):
        """CR-MDB-058 §S6: the snippet is fenced, runs ``gh release create`` with the
        ``CHANGELOG.md`` section as ``--notes-file``, and no fenced step uses
        ``--generate-notes``."""
        missing = (f"## Releases: {RELEASE_JOB_SNIPPET}: no fenced create-release step passing "
                   "the CHANGELOG.md section as --notes-file")
        generated = f"## Releases: {RELEASE_JOB_SNIPPET}: a fenced step still uses --generate-notes"
        good = CONFORMING_RELEASES
        self.assertEqual(check_release_steps(
            good.replace("--notes-file notes.md", "--notes notes.md")), [missing])
        self.assertEqual(check_release_steps(
            good.replace("--notes-file notes.md", "--generate-notes")), [missing, generated])
        self.assertEqual(check_release_steps(
            good.replace("extract-section CHANGELOG.md", "extract-section NOTES.txt")), [missing])
        self.assertEqual(check_release_steps(good.replace(
            "\n## Next\n", "\n```bash\ngh release create \"$TAG\" --generate-notes\n```\n\n## Next\n")),
            [generated])
        self.assertEqual(check_release_steps(
            good + "\n```bash\ngh release create \"$TAG\" --generate-notes\n```\n"), [],
            "a fenced step outside ## Releases is not the snippet")
        unfenced = good.replace("```yaml\n", "").replace("--verify-tag\n```\n", "--verify-tag\n")
        self.assertIn(missing, check_release_steps(unfenced),
                      "the snippet counts only as a fenced block")
        self.assertEqual(check_release_steps(good.replace("```yaml", "~~~yaml").replace(
            "--verify-tag\n```", "--verify-tag\n~~~")), [], "a tilde fence counts too")

    def test_marked_regions_use_checker_both_ways(self):
        """CR-MDB-058 §S7: the ``Marked regions`` statement, proved on the conforming guide."""
        link = f"section '{MARKED}' must say release notes link to the guide"
        feed = f"section '{MARKED}' must say the regions feed the generated package README"
        copied = f"section '{MARKED}' must not say the regions are copied into the release notes"
        good = self.guide
        self.assertEqual(check_marked_regions_use(good), [])
        old = ("Each section above sits between two marker lines, so its text can be copied, "
               "unchanged, into\nthe release notes and the Pi package's README:")
        self.assertEqual(check_marked_regions_use(good.replace(CONFORMING_MARKED_REGIONS_USE, old)),
                         [link, feed, copied])
        self.assertEqual(check_marked_regions_use(
            good.replace("Release notes link to this guide. ", "")), [link])
        self.assertEqual(check_marked_regions_use(
            good.replace(" The regions feed the generated package README.", "")), [feed])
        self.assertEqual(check_marked_regions_use(
            good + "\nThe regions are copied into the release notes as well.\n"), [copied])
        self.assertEqual(check_marked_regions_use(
            good + "\nThe regions are never copied into the release notes.\n"), [],
            "a sentence that forbids the copy is not the copy")
        self.assertEqual(check_marked_regions_use(good.replace(
            CONFORMING_MARKED_REGIONS_USE,
            "Release notes\nlink to this guide. The regions feed the generated\npackage README.")),
            [], "a statement wrapped across lines counts")
        inside = good.replace(CONFORMING_MARKED_REGIONS_USE, "").replace(
            "<!-- install-guide:end install -->",
            CONFORMING_MARKED_REGIONS_USE + "\n\n<!-- install-guide:end install -->")
        self.assertEqual(check_marked_regions_use(inside), [link, feed],
                         "the statement counts only in the Marked regions section")

    def test_pi_package_step_keeps_python_and_documentation_steps_intact(self):
        """Adding the Pi step to a section already carrying the two
        documentation steps and the four Python steps leaves both their
        checkers clean, and the Pi checker does not accept Python-only text."""
        # MIGRATED at CR-MDB-058 C3 RED (§S6): the documentation steps are the conforming
        # section's (was "Copy the install guide's marked regions verbatim into the release
        # notes, then hold a documentation review.").
        # MIGRATED at CR-MDB-067 C3 RED (§S5): the Python and Pi samples are the CI-path steps
        # (was: "TestPyPI into an isolated tool directory", "upload with a token the user
        # supplies", "with credentials the user supplies at publish time"); the Pi step sits under
        # its own heading and the Rehearsal and CI subsection follows it; the python-only faults
        # drop the two retired terms and gain 'repository secret' and '2fa' ('trusted
        # publishing' is named by the Python rehearse step, so it is not missing).
        docs = CONFORMING_RELEASES_BODY + "\n"
        python = ("1. Set the version in its single source, then `uv build`.\n"
                  "2. Each release-branch push uploads the stamped dev version to TestPyPI "
                  "through Trusted Publishing.\n"
                  "3. After git flow release finish, the release job uploads to PyPI with no "
                  "token anywhere.\n"
                  "4. Install from PyPI with `--reinstall`; drop global permission config "
                  "entries for per-project policies; a trusted project runs without a "
                  "permission prompt.\n\n")
        pi = ("For a Pi package, once the version is set, npm publish --access public through "
              "Trusted Publishing, a new package's first-publish token kept as a repository "
              "secret, then 2FA required; then with PI_CODING_AGENT_DIR on "
              "a scratch path, pi install the published version and confirm the extension "
              "loads. Live check, post-release: in the real Pi configuration confirm Pi "
              "loads the worktree extension.\n")
        pi_section = "### Pi package releases\n\n" + pi + "\n"
        combined = "## Releases\n\n" + docs + python + pi_section + CONFORMING_REHEARSAL_AND_CI
        self.assertEqual(check_release_steps(combined), [])
        self.assertEqual(check_python_release_steps(combined), [])
        self.assertEqual(check_pi_package_release_steps(combined), [])
        # The subsection names none of the steps' anchors: put first, it moves no checker's
        # first-occurrence order; only its placement is reported.
        subsection_first = ("## Releases\n\n" + CONFORMING_REHEARSAL_AND_CI + "\n" + docs + python
                            + pi_section)
        self.assertEqual(check_python_release_steps(subsection_first), [])
        self.assertEqual(check_pi_package_release_steps(subsection_first), [])
        # MIGRATED at CR-MDB-070 C2 RED (§S6): put first, the subsection runs on into the body's
        # release-flow paragraph, whose `git push origin master develop --tags` names develop without
        # a negation (was: the placement fault alone).
        self.assertEqual(check_release_steps(subsection_first),
                         [f"## Releases: {REHEARSAL_AND_CI}: '### Rehearsal and CI' is not after "
                          "'### Pi package releases'",
                          f"## Releases: {REHEARSAL_AND_CI}: names CI on develop"])
        python_only = "## Releases\n\n" + docs + python
        self.assertEqual(check_pi_package_release_steps(python_only), [
            "## Releases: npm publish: missing 'npm publish'",
            "## Releases: npm publish: missing 'pi package'",
            "## Releases: npm publish: missing 'version is set'",
            "## Releases: npm publish: missing 'repository secret'",
            "## Releases: npm publish: missing '2fa'",
            "## Releases: npm publish: missing '--access public'",
            "## Releases: isolated pi install: missing 'pi_coding_agent_dir'",
            "## Releases: isolated pi install: missing 'pi install'",
            "## Releases: isolated pi install: missing 'published version'",
            "## Releases: isolated pi install: missing 'extension loads'",
            "## Releases: live check: missing 'live check'",
            "## Releases: live check: missing 'real pi configuration'",
            "## Releases: live check: missing 'loads the worktree extension'",
        ])

    # CR-MDB-067 §S5 — the new groups of check_release_steps, each proved both ways.

    def test_publish_step_gate_passes_the_conforming_section_and_bites_once_per_step(self):
        good = CONFORMING_RELEASES
        self.assertEqual(check_release_steps(good), [])
        cases = {
            "the release branch is published with git flow release publish":
                ("`git flow release publish X.Y.Z`, or\n", ""),
            "a hotfix branch is published with git flow hotfix publish":
                (", or\n`git flow hotfix publish X.Y.Z` for a hotfix", ""),
            "every push of the branch is the rehearsal":
                ("Every push of the branch is the rehearsal;\n", ""),
            "finish deletes the remote branch": ("\n`finish` deletes the remote branch.", ""),
        }
        self.assertEqual(len(cases), len(PUBLISH_STEP_PHRASES), "one case per step")
        for label, (old, new) in cases.items():
            with self.subTest(step=label):
                self.assertIn(old, good)
                self.assertEqual(check_release_steps(good.replace(old, new)),
                                 [f"## Releases: {PUBLISH_STEP}: {label}"])
        rehearsal = f"## Releases: {PUBLISH_STEP}: every push of the branch is the rehearsal"
        self.assertEqual(check_release_steps(good.replace(
            "Every push of the branch is the rehearsal", "Every push of the branch is not the rehearsal")),
            [rehearsal], "a push that is not the rehearsal is not the step")
        self.assertEqual(check_release_steps(good.replace(
            "Every push of the branch is the rehearsal;", "Every push of the branch counts.\n\nIt is the rehearsal;")),
            [rehearsal], "a step's words split across two units do not count")
        paragraph = ("With the version bump in place, publish the branch (`git flow release publish "
                     "X.Y.Z`, or\n`git flow hotfix publish X.Y.Z` for a hotfix). Every push of the "
                     "branch is the rehearsal;\n`finish` deletes the remote branch.\n")
        self.assertIn(paragraph, good)
        outside = good.replace(paragraph, "").replace("\n## Next\n", "\n## Next\n\n" + paragraph)
        self.assertEqual(release_step_faults(outside, PUBLISH_STEP),
                         [f"## Releases: {PUBLISH_STEP}: {label}" for _, label, _ in PUBLISH_STEP_PHRASES],
                         "the publish step counts only inside ## Releases")

    def test_notes_before_first_publish_gate_both_ways(self):
        fault = (f"## Releases: {NOTES_BEFORE_PUBLISH}: the release notes are written before the "
                 "branch is first published")
        good = CONFORMING_RELEASES
        preamble = "On the release branch, before the branch is first published:\n"
        self.assertIn(preamble, good)
        self.assertEqual(release_step_faults(good, NOTES_BEFORE_PUBLISH), [])
        self.assertEqual(check_release_steps(good.replace(
            preamble, "On the release branch, before `git flow release finish`:\n")), [fault],
            "the old 'before finish' step is reported")
        self.assertEqual(check_release_steps(good.replace(
            preamble, "On the release branch, before its first publish:\n")), [],
            "'before its first publish' reads the same")
        self.assertEqual(check_release_steps(good.replace(
            preamble, "On the release branch, before the release\nbranch is first published:\n")), [],
            "a step wrapped across lines counts")
        moved = good.replace(preamble, "On the release branch:\n").replace(
            "### Release notes (`CHANGELOG.md`)\n",
            "The release notes are written before the branch is first published.\n\n"
            "### Release notes (`CHANGELOG.md`)\n")
        self.assertEqual(check_release_steps(moved), [fault],
                         "the step counts only in the ### Release notes subsection")
        self.assertEqual(check_release_steps(good.replace("### Release notes (`CHANGELOG.md`)\n", "")),
                         [fault], "without the subsection the step is missing")

    def test_rehearsal_and_ci_gate_passes_the_conforming_subsection_and_bites_once_per_step(self):
        good = CONFORMING_RELEASES
        self.assertEqual(release_step_faults(good, REHEARSAL_AND_CI), [])
        labels = [label for _, label, _ in REHEARSAL_AND_CI_PHRASES]
        edits = [
            (" or `hotfix/X.Y.Z`", ""),
            ("with a dev marker and the CI run", "with the CI run"),
            ("refuses a committed version other than `X.Y.Z`, and ", ""),
            (", and fails when\nthe release's notes are missing or empty.", "."),
            ("the upload to the test index", "a build"),
            (" with a dist-tag", ""),
            ("`arduino`, ", ""),
            ("`quarkus`, ", ""),
            ("`java`, ", ""),
            (", `rust`", ""),
            # MIGRATED at CR-MDB-070 C2 RED (§S6): the CI rule's steps are the test job's (was
            # (" and on\npull requests", "") for the develop/release/hotfix/pull-request step).
            ("runs the suite in every run:", "runs the suite:"),
            (" to a release or hotfix\nbranch", " to a branch"),
            (", each push to `master`", ""),
            (", each published release", ""),
            ("on the stack's floor\ninterpreter, ", ""),
            ("in a clean home, ", ""),
            (", with full history", ""),
            ("It runs outside any agent session, the one", "It is the one"),
            (" without the stack's Crucible client", ""),
            ("Every publish job (the rehearsal\nincluded) needs the test job, because", "Because"),
            (", because a dependency gates only within one run", ""),
        ]
        self.assertEqual(len(edits), len(labels), "one case per step")
        self.assertEqual(labels[6:10], [f"forms table: {s}, the notes check only"
                                        for s in ("arduino", "quarkus", "java", "rust")])
        for label, (old, new) in zip(labels, edits, strict=True):
            with self.subTest(step=label):
                self.assertEqual(good.count(old), 1, old)
                self.assertEqual(check_release_steps(good.replace(old, new)),
                                 [f"## Releases: {REHEARSAL_AND_CI}: {label}"])
        # MIGRATED at CR-MDB-070 C2 RED (§S6): the moved rule is the test-job rule, and moving it
        # also loses the no-CI-on-develop-or-pull-requests statement (was the develop/PR CI rule).
        ci_rule = ("The release workflow's test job runs the suite in every run: each push to a "
                   "release or hotfix\nbranch, each push to `master`, each published release. It "
                   "runs on the stack's floor\ninterpreter, in a clean home, with full history. It "
                   "runs outside any agent session, the one\nplace the suite runs without the "
                   "stack's Crucible client. Every publish job (the rehearsal\nincluded) needs the "
                   "test job, because a dependency gates only within one run. No CI on\n`develop` "
                   "or pull requests.\n")
        self.assertIn(ci_rule, good)
        moved = good.replace(ci_rule, "").replace("### Release notes", ci_rule + "\n### Release notes")
        self.assertEqual(check_release_steps(moved),
                         [f"## Releases: {REHEARSAL_AND_CI}: {label}" for label in labels[10:]]
                         + [f"## Releases: {REHEARSAL_AND_CI}: {NO_CI_ON_DEVELOP_OR_PRS}"],
                         "a step counts only inside the ### Rehearsal and CI subsection")

    # CR-MDB-070 §S6 — the CI rule's develop and pull-request terms, inverted and negation-aware.

    def test_ci_on_develop_or_pull_requests_is_a_fault_and_no_ci_on_them_passes(self):
        good = CONFORMING_RELEASES
        no_ci = "No CI on\n`develop` or pull requests.\n"
        self.assertEqual(good.count(no_ci), 1)
        stated = f"## Releases: {REHEARSAL_AND_CI}: {NO_CI_ON_DEVELOP_OR_PRS}"
        on_develop = f"## Releases: {REHEARSAL_AND_CI}: names CI on develop"
        on_prs = f"## Releases: {REHEARSAL_AND_CI}: names CI on pull requests"
        self.assertEqual(excluded_ref_faults(norm_units(no_ci)), [])
        self.assertEqual(check_release_steps(good), [])
        self.assertEqual(check_release_steps(good.replace(no_ci, "")), [stated],
                         "the statement is required, not merely a positive mention forbidden")
        todays = ("A CI workflow runs the suite on every push to `develop`, release and hotfix "
                  "branches and on\npull requests, on the stack's floor interpreter.\n")
        self.assertEqual(check_release_steps(good.replace(no_ci, todays)),
                         [stated, on_develop, on_prs], "today's CI rule is the fault, both terms")
        self.assertEqual(check_release_steps(good.replace(
            no_ci, "CI runs on every push to `develop`.\n")), [stated, on_develop])
        self.assertEqual(check_release_steps(good.replace(
            no_ci, "The suite also runs on pull requests.\n")), [stated, on_prs])
        self.assertEqual(check_release_steps(good.replace(
            no_ci, no_ci + "\nThe suite also runs on every push to `develop`.\n")), [on_develop],
            "a negated statement does not excuse a positive mention beside it")
        self.assertEqual(check_release_steps(good.replace(
            no_ci, "No CI on `develop`, but CI on pull requests.\n")), [stated, on_prs],
            "a negation reaches only its own clause")
        for negated in ("CI never runs on `develop` or pull requests.\n",
                        "Not on `develop`, not on pull requests: no CI there.\n",
                        "The test job does not run on\n`develop` or on pull requests.\n"):
            with self.subTest(negated=negated):
                self.assertEqual(check_release_steps(good.replace(no_ci, negated)), [])
        self.assertEqual(check_release_steps(good.replace(
            no_ci, "Not on `develop` or pull requests.\n")), [],
            "the unit names CI elsewhere in its paragraph")
        alone = good.replace(no_ci, "").replace(
            "\n## Next\n", "\n\nNever on `develop` or pull requests.\n\n## Next\n")
        self.assertEqual(check_release_steps(alone), [stated],
                         "a negated unit naming no CI, suite or test job is not the statement")
        outside = good.replace(no_ci, "").replace(
            "### Release notes", "No CI on `develop` or pull requests.\n\n### Release notes")
        self.assertEqual(check_release_steps(outside), [stated],
                         "the statement counts only inside ### Rehearsal and CI")
        self.assertEqual(check_release_steps(good.replace(
            "### Release notes", "Pushes to `develop` merge features.\n\n### Release notes")), [],
            "a positive develop mention outside the subsection is not a CI rule")

    def test_excluded_ref_faults_reads_each_clause_on_its_own(self):
        self.assertEqual(excluded_ref_faults([]), [
            f"## Releases: {REHEARSAL_AND_CI}: {NO_CI_ON_DEVELOP_OR_PRS}"])
        self.assertEqual(excluded_ref_faults(
            ["no ci on develop or pull requests.", "ci runs on develop."]),
            [f"## Releases: {REHEARSAL_AND_CI}: names CI on develop"])
        self.assertEqual(excluded_ref_faults(
            ["the suite runs on pull requests and never on develop."]),
            [f"## Releases: {REHEARSAL_AND_CI}: {NO_CI_ON_DEVELOP_OR_PRS}",
             f"## Releases: {REHEARSAL_AND_CI}: names CI on pull requests"])
        self.assertEqual(excluded_ref_faults(
            ["ci runs on develop-branch builds; no ci on develop or pull requests."]), [],
            "develop-branch is not the develop ref")

    # CR-MDB-070 §S6 — the snippet: full history, the --points-at tag, after the tests, on master.

    def test_release_job_snippet_takes_the_points_at_tag_after_the_tests_on_the_master_push(self):
        good = CONFORMING_RELEASES
        self.assertEqual(release_step_faults(good, RELEASE_JOB_SNIPPET), [])
        faults = [f"## Releases: {RELEASE_JOB_SNIPPET}: the snippet {fault}"
                  for fault, _ in SNIPPET_ELEMENTS]
        edits = [
            ("      with:\n        fetch-depth: 0\n", ""),
            ("git tag --points-at HEAD | ", "git describe --tags | "),
            ("exit 0; }", "exit 1; }"),
            ("  needs: test\n", ""),
            ("  if: github.ref == 'refs/heads/master'\n", ""),
            # MIGRATED at CR-MDB-070 C4 RED (VERIFY F1): the sixth element, the count of tags.
            ("more than one version tag", "two version tags"),
        ]
        self.assertEqual(len(edits), len(SNIPPET_ELEMENTS), "one case per element")
        for fault, (old, new) in zip(faults, edits, strict=True):
            with self.subTest(fault=fault):
                self.assertEqual(good.count(old), 1, old)
                self.assertEqual(check_release_steps(good.replace(old, new)), [fault])
        filter_lost = good.replace(" | grep -E '^[0-9]+\\.[0-9]+\\.[0-9]+$'", "")
        self.assertNotEqual(filter_lost, good)
        self.assertEqual(check_release_steps(filter_lost), [faults[1]],
                         "the tag at HEAD is filtered to X.Y.Z")
        self.assertEqual(check_release_steps(good.replace("nothing to release", "done")),
                         [faults[2]], "no tag means nothing to release")
        self.assertEqual(check_release_steps(good.replace("  needs: test\n", "  needs: build\n")),
                         [faults[3]], "the job the snippet sits in needs the test job")
        self.assertEqual(check_release_steps(good.replace("'refs/heads/master'", "'refs/heads/main'")),
                         [faults[4]])
        named = (good.replace("  needs: test\n", "")
                 .replace("  if: github.ref == 'refs/heads/master'\n", "")
                 .replace("    - name: Create the release\n",
                          "    # in a job that needs the test job and runs on the master push\n"
                          "    - name: Create the release\n"))
        self.assertEqual(check_release_steps(named), [], "a comment naming the job counts")
        self.assertEqual(check_release_steps(good.replace(
            "\n## Next\n", "\n```yaml\nneeds: test\nfetch-depth: 0\n```\n\n## Next\n")), [],
            "another fenced block is not the snippet")
        loose = good.replace("  needs: test\n", "").replace(
            "\n## Next\n", "\n```yaml\nneeds: test\n```\n\n## Next\n")
        self.assertEqual(check_release_steps(loose), [faults[3]],
                         "an element counts only inside the snippet's own block")
        self.assertEqual(check_release_steps(good.replace("--notes-file notes.md", "--notes x")),
                         [f"## Releases: {RELEASE_JOB_SNIPPET}: no fenced create-release step "
                          "passing the CHANGELOG.md section as --notes-file"],
                         "without a snippet block its elements are not reported")

    def test_the_release_section_names_github_ref_name_nowhere(self):
        fault = f"## Releases: {RELEASE_JOB_SNIPPET}: names github.ref_name"
        good = CONFORMING_RELEASES
        self.assertEqual(check_release_steps(good.replace(
            "        tag=$(git tag --points-at HEAD",
            "        tag=${{ github.ref_name }}\n        x=$(git tag --points-at HEAD")), [fault])
        self.assertEqual(check_release_steps(good.replace(
            "\n## Next\n", "\nThe tag is never `GITHUB_REF_NAME`.\n\n## Next\n")), [fault],
            "named in prose, in any case, it is still named")
        self.assertEqual(check_release_steps(good + "\n`github.ref_name`\n"), [],
                         "outside ## Releases it is not gated")
        self.assertEqual(check_release_steps(good.replace("github.ref ==", "github.ref_name ==")),
                         [fault], "in the job's condition it is named too")

    # CR-MDB-070 §S6 — the release flow: one push, the master push releases, the event publishes.

    def test_release_flow_gate_passes_the_conforming_section_and_bites_once_per_step(self):
        good = CONFORMING_RELEASES
        self.assertEqual(release_step_faults(good, RELEASE_FLOW), [])
        labels = [label for _, label, _ in RELEASE_FLOW_PHRASES]
        edits = [
            (" in one `git push", " with `git push"),
            ("push runs the tests and creates the release", "push runs the tests"),
            (", and the release event publishes", ""),
            ("dispatch the workflow on `master`", "start again"),
        ]
        self.assertEqual(len(edits), len(labels), "one case per step")
        for label, (old, new) in zip(labels, edits, strict=True):
            with self.subTest(step=label):
                self.assertEqual(good.count(old), 1, old)
                self.assertEqual(check_release_steps(good.replace(old, new)),
                                 [f"## Releases: {RELEASE_FLOW}: {label}"])
        self.assertEqual(check_release_steps(good.replace(
            "the `master` push runs the tests", "the tag push runs the tests")),
            [f"## Releases: {RELEASE_FLOW}: {labels[1]}"], "the master push creates the release")
        self.assertEqual(check_release_steps(good.replace(
            "reports no version tag at `HEAD`", "fails")),
            [f"## Releases: {RELEASE_FLOW}: {labels[3]}"], "the recovery names its condition")
        flow = ("Then push `master`, `develop` and the tags in one `git push origin master develop "
                "--tags`:\nthe `master` push runs the tests and creates the release, and the release "
                "event publishes.\nIf the `master` run reports no version tag at `HEAD`, dispatch "
                "the workflow on `master`.\n")
        self.assertIn(flow, good)
        outside = good.replace(flow, "").replace("\n## Next\n", "\n## Next\n\n" + flow)
        self.assertEqual(release_step_faults(outside, RELEASE_FLOW),
                         [f"## Releases: {RELEASE_FLOW}: {label}" for label in labels],
                         "the flow counts only inside ## Releases")
        fenced_only = good.replace(flow, "```bash\ngit push origin master develop --tags\n```\n")
        self.assertEqual(release_step_faults(fenced_only, RELEASE_FLOW),
                         [f"## Releases: {RELEASE_FLOW}: {label}" for label in labels],
                         "the bare command (today's Java step) is not the one-push flow")

    def test_rehearsal_and_ci_subsection_must_exist_and_follow_the_pi_package_releases(self):
        good = CONFORMING_RELEASES
        missing = f"## Releases: {REHEARSAL_AND_CI}: no '### Rehearsal and CI' subsection"
        misplaced = (f"## Releases: {REHEARSAL_AND_CI}: '### Rehearsal and CI' is not after "
                     "'### Pi package releases'")
        self.assertEqual(check_release_steps(good.replace("### Rehearsal and CI\n", "")), [missing])
        self.assertEqual(check_release_steps(
            good.replace("### Rehearsal and CI\n", "### Rehearsal\n")), [missing],
            "the heading title is exactly 'Rehearsal and CI'")
        self.assertEqual(check_release_steps(good.replace("### Rehearsal and CI\n", "#### Rehearsal and CI\n")),
                         [missing], "the subsection is a ### heading")
        self.assertEqual(check_release_steps(good.replace(CONFORMING_PI_PACKAGE_HEADING, "")), [misplaced])
        before = ("## Releases (NON-NEGOTIABLE)\n\n" + CONFORMING_RELEASES_BODY + "\n"
                  + CONFORMING_REHEARSAL_AND_CI + "\n" + CONFORMING_PI_PACKAGE_HEADING + "\n## Next\n")
        self.assertEqual(check_release_steps(before), [misplaced])
        fenced = good.replace("### Rehearsal and CI\n", "```text\n### Rehearsal and CI\n```\n")
        self.assertIn(missing, check_release_steps(fenced), "a heading inside a fence is no heading")

    def test_rehearsal_and_ci_subsection_names_none_of_the_python_or_pi_anchors(self):
        self.assertEqual([a for _, a in SUBSECTION_FORBIDDEN_ANCHORS],
                         ["uv build", "testpypi", "no token anywhere", "--reinstall",
                          "npm publish", "pi_coding_agent_dir", "live check"])
        good = CONFORMING_RELEASES
        for kind, anchor in SUBSECTION_FORBIDDEN_ANCHORS:
            with self.subTest(anchor=anchor):
                named = good.replace("\n## Next\n", f"\nSee also `{anchor}`.\n\n## Next\n")
                self.assertEqual(check_release_steps(named),
                                 [f"## Releases: {REHEARSAL_AND_CI}: names the {kind} anchor {anchor!r}"])
        self.assertEqual(check_release_steps(good.replace("the upload to the test index",
                                                          "the upload to TestPyPI")),
                         [f"## Releases: {REHEARSAL_AND_CI}: forms table: python, X.Y.Z.devN, the "
                          "upload to the test index",
                          f"## Releases: {REHEARSAL_AND_CI}: names the python step anchor 'testpypi'"])
        self.assertEqual(check_release_steps(good.replace(
            "dry-run publish with a dist-tag", "dry-run publish with a dist-tag (`npm publish --dry-run`)")),
            [f"## Releases: {REHEARSAL_AND_CI}: names the pi package step anchor 'npm publish'"])
        self.assertEqual(check_release_steps(good + "\nSee also `TestPyPI` and `npm publish`.\n"), [],
                         "an anchor outside ## Releases is not the subsection's")

    def test_retired_release_phrases_gate_both_ways(self):
        # MIGRATED at CR-MDB-070 C4 RED (VERIFY F3): "the tag's release job" joins the tuple.
        self.assertEqual(RETIRED_RELEASE_PHRASES, (
            "isolated tool directory", "uv_tool_dir", "test.pypi.org/simple",
            "token the user supplies", "user-supplied token", "credentials the user supplies",
            "user-supplied credentials", "the tag's release job"))
        good = CONFORMING_RELEASES
        self.assertEqual(release_step_faults(good, RETIRED_PHRASES), [])
        for phrase in RETIRED_RELEASE_PHRASES:
            with self.subTest(phrase=phrase):
                named = good.replace("\n## Next\n", f"\nNever write {phrase}.\n\n## Next\n")
                self.assertEqual(check_release_steps(named),
                                 [f"## Releases: {RETIRED_PHRASES}: names {phrase!r}"])
        old_steps = ("2. **Rehearse on TestPyPI** — install it into an\n"
                     "   Isolated tool directory (`UV_TOOL_DIR` pointed at a scratch path) from\n"
                     "   `--index-url https://test.pypi.org/simple/`.\n"
                     "3. **Upload to PyPI** — upload with a token the user supplies.\n"
                     "4. **Publish** — `npm publish`, using credentials the user supplies.\n")
        self.assertEqual(release_step_faults(good.replace("\n## Next\n", "\n" + old_steps + "\n## Next\n"),
                                             RETIRED_PHRASES),
                         [f"## Releases: {RETIRED_PHRASES}: names {p!r}" for p in (
                             "isolated tool directory", "uv_tool_dir", "test.pypi.org/simple",
                             "token the user supplies", "credentials the user supplies")],
                         "the old Python and Pi steps' phrasing, wrapped and in any case")
        self.assertEqual(check_release_steps(good + "\nInstall into an isolated tool directory with a "
                                                    "token the user supplies.\n"), [],
                         "a phrase outside ## Releases is not gated")

    # CR-MDB-070 C4 RED (VERIFY F1/F2/F3/F6) — their gates proved both ways on sample text.

    SNIPPET_COUNT_LINE = ("        [ \"$(printf '%s\\n' \"$tag\" | wc -l)\" -eq 1 ] || { echo \"more than "
                          "one version tag at HEAD: $tag\" >&2; exit 1; }\n")

    def test_snippet_more_than_one_version_tag_gate_both_ways(self):
        fault = (f"## Releases: {RELEASE_JOB_SNIPPET}: the snippet does not refuse more than one "
                 "version tag at HEAD")
        good = CONFORMING_RELEASES
        self.assertEqual(good.count(self.SNIPPET_COUNT_LINE), 1)
        self.assertEqual(check_release_steps(good), [])
        dropped = good.replace(self.SNIPPET_COUNT_LINE, "")
        self.assertEqual(check_release_steps(dropped), [fault])
        in_prose = dropped.replace("\n## Next\n",
                                   "\nThe job refuses more than one version tag.\n\n## Next\n")
        self.assertEqual(check_release_steps(in_prose), [fault],
                         "the refusal counts only inside the snippet's own block")

    def test_snippet_checkout_pin_gate_both_ways(self):
        fault = f"## Releases: {RELEASE_JOB_SNIPPET}: {CHECKOUT_PIN_FAULT}"
        good = CONFORMING_RELEASES
        line = "    - uses: actions/checkout@v4 # pin to a full commit SHA\n"
        self.assertEqual(good.count(line), 1)
        self.assertEqual(checkout_pin_faults(release_job_snippet(good) or ""), [])
        bare = "    - uses: actions/checkout@v4\n"
        passing = {
            "the comment line above": bare.replace("    - uses", "    # pin to a full commit SHA\n    - uses"),
            "two comment lines above": ("    # pin this action to a full\n    # commit SHA\n" + bare),
            "the comment line below": bare + "      # pinned to a full commit sha\n",
        }
        for label, new in passing.items():
            with self.subTest(passes=label):
                self.assertEqual(check_release_steps(good.replace(line, new)), [])
        failing = {
            "no comment": bare,
            "pin without sha": "    - uses: actions/checkout@v4 # pin it\n",
            "sha without pin": "    - uses: actions/checkout@v4 # a full commit SHA\n",
            "a comment not beside it": ("    # pin to a full commit SHA\n    - name: Check out\n"
                                        "      uses: actions/checkout@v4\n"),
        }
        for label, new in failing.items():
            with self.subTest(fails=label):
                self.assertEqual(check_release_steps(good.replace(line, new)), [fault])
        other = good.replace(line, bare).replace(
            "    - name: Create the release\n",
            "    - uses: astral-sh/setup-uv@v6 # pin to a full commit SHA\n"
            "    - name: Create the release\n")
        self.assertEqual(check_release_steps(other), [fault],
                         "the pin comment of another action is not the checkout's")
        self.assertEqual(checkout_pin_faults("steps:\n  - run: true\n"), [fault],
                         "a snippet with no checkout line is a fault")
        prose = good.replace(line, bare).replace(
            "\n## Next\n", "\nPin the checkout to a full commit SHA.\n\n## Next\n")
        self.assertEqual(check_release_steps(prose), [fault],
                         "prose outside the snippet's block is not the comment beside it")

    PUBLISH_JOB_SAMPLE = (
        "## Releases (NON-NEGOTIABLE)\n\n"
        "### Python package releases\n\n"
        "3. **Publish to PyPI** — after `git flow release finish`, the release event's publish job\n"
        "   builds and uploads to PyPI through Trusted Publishing after the tests and the ref guard,\n"
        "   with no token anywhere.\n\n"
        "### Pi package releases\n\n"
        "1. **Publish** — on the release event, the publish job runs `npm publish --access public`\n"
        "   through Trusted Publishing, after the tests, behind the ref guard.\n\n"
        "## Next\n\nrelease event, ref guard, after the tests, trusted publishing\n")

    def test_publish_job_gate_both_ways(self):
        good = self.PUBLISH_JOB_SAMPLE
        self.assertEqual(publish_job_faults(good), [])
        self.assertEqual(publish_job_faults(good.replace("through Trusted Publishing after",
                                                         "through Trusted\n   Publishing after")),
                         [], "a term wrapped across lines counts")

        def missing(label, anchor, term):
            return f"## Releases: {label}: the step holding {anchor!r} does not say {term!r}"

        py, pi = ("pypi upload", "no token anywhere"), ("npm publish", "npm publish")
        cases = {
            missing(*py, "release event"): ("the release event's publish job\n", "the publish job\n"),
            missing(*py, "ref guard"): (" and the ref guard,\n", ",\n"),
            missing(*py, "after the tests"): ("Publishing after the tests and the ref guard",
                                             "Publishing behind the ref guard"),
            missing(*py, "trusted publishing"): ("PyPI through Trusted Publishing",
                                                "PyPI with a stored token"),
            missing(*py, "git flow release finish"): ("after `git flow release finish`, ", ""),
            missing(*pi, "release event"): ("on the release event, the publish job",
                                           "the publish job"),
            missing(*pi, "ref guard"): (", behind the ref guard.\n", ".\n"),
            missing(*pi, "after the tests"): (", after the tests, behind", ", behind"),
            missing(*pi, "trusted publishing"): ("   through Trusted Publishing, after",
                                                "   with the stored token, after"),
        }
        for fault, (old, new) in cases.items():
            with self.subTest(fault=fault):
                self.assertEqual(good.count(old), 1, old)
                self.assertEqual(publish_job_faults(good.replace(old, new)), [fault])
        split = good.replace(" after the tests and the ref guard,\n   with no token anywhere.\n",
                             ",\n   with no token anywhere.\n\nIt runs after the tests and the ref guard.\n")
        self.assertNotEqual(split, good)
        self.assertEqual(publish_job_faults(split), [missing(*py, "ref guard"),
                                                     missing(*py, "after the tests")],
                         "a term in another unit than the step's does not count")
        self.assertEqual(publish_job_faults(good.replace(",\n   with no token anywhere.", ".")),
                         ["## Releases: pypi upload: no unit holds 'no token anywhere'"])
        self.assertEqual(publish_job_faults("## Other\n\nnpm publish\n"),
                         ["no '## Releases' section"])

    def test_red_run_recovery_gate_both_ways(self):
        good = CONFORMING_RELEASES
        fault = [f"## Releases: {RED_RUN_RECOVERY}: {label}"
                 for _, label, _ in RED_RUN_RECOVERY_PHRASES]
        self.assertEqual(len(fault), 1)
        self.assertEqual(release_step_faults(good, RED_RUN_RECOVERY), [])
        cases = {
            "nothing publishes unsaid": ("nothing publishes: ", "the run stops: "),
            "no re-run of the failed jobs": ("re-run the failed\njobs, and ", "push again, and "),
            "a whole re-run is not the failed jobs": ("re-run the failed\njobs, and ",
                                                      "re-run the workflow, and "),
            "no hotfix": ("on a hotfix branch.", "on a new branch."),
            "not the push paragraph": ("on `master`.\nWhen the `master` run",
                                       "on `master`.\n\nWhen the `master` run"),
        }
        for label, (old, new) in cases.items():
            with self.subTest(case=label):
                self.assertEqual(good.count(old), 1, old)
                self.assertEqual(check_release_steps(good.replace(old, new)), fault)
        sentence = ("When the `master` run or the release run fails its tests, nothing publishes: "
                    "re-run the failed\njobs, and fix a real failure on a hotfix branch.\n")
        self.assertIn(sentence, good)
        outside = good.replace(sentence, "").replace("\n## Next\n", "\n## Next\n\n" + sentence)
        self.assertEqual(release_step_faults(outside, RED_RUN_RECOVERY), fault,
                         "the recovery counts only inside ## Releases")


# ---------------------------------------------------------------------------
# CR-MDB-064 §S5 — the guide's Python 3.14 interpreter
# ---------------------------------------------------------------------------

#: §S5/§S2 — the remediation the guide names for the interpreter. MIGRATED at CR-MDB-063 C3 RED:
#: read from the ``python3`` requirement row, never a copy (was the literal).
PYTHON_REMEDIATION = _requirement("python3")["remediation"]
PYTHON_FLOOR = (3, 14)
#: "a Python 3.14 interpreter" ("Python ≥ 3.14" and "Python 3.14 or later" read the same).
_PYTHON_FLOOR_WORDING = re.compile(r"(?<![\w-])Python (?:≥ ?|>= ?)?3\.14(?!\d|\.\d)")
_PATH_WORD = re.compile(r"(?<![\w-])PATH(?![\w-])")
#: §S2's stderr line when a candidate is accepted: ``python3: <path> (<version>)``.
PYTHON_ACCEPTED_LINE = re.compile(r"^python3: (/\S+) \((\d+)\.(\d+)[^()\s]*\)$")
#: §S2's stderr line when none is: ``python3=outdated|absent — <reason>; install it with: …``.
PYTHON_REFUSAL_LINE = re.compile(
    r"^python3=(?:outdated|absent) — \S.*; install it with: " + re.escape(PYTHON_REMEDIATION) + "$")
#: The parenthesised list of tools whose installer needs elevated privileges.
_ELEVATED_LIST = re.compile(r"(?<![\w-])needs? elevated privileges\s*\(([^)]*)\)")
_LIST_ITEM_START = re.compile(r"^\s*(?:\d+\.|[-*])\s")


def _list_items(section: str) -> list[str]:
    """Each markdown list item of ``section`` (a nested item is its own item), with its
    indented continuation lines; a blank line does not end an item, an unindented
    non-item line does."""
    items: list[str] = []
    current: list[str] | None = None
    for line in section.splitlines():
        if _LIST_ITEM_START.match(line):
            if current is not None:
                items.append("\n".join(current))
            current = [line]
        elif current is not None and (not line.strip() or line[:1] in (" ", "\t")):
            current.append(line)
        elif current is not None:
            items.append("\n".join(current))
            current = None
    if current is not None:
        items.append("\n".join(current))
    return items


def _fenced_lines(text: str) -> list[str]:
    """Every line inside a fenced block (the fence lines themselves excluded), stripped."""
    lines = text.splitlines()
    return [line.strip() for line, fenced in zip(lines, _fence_mask(lines), strict=True)
            if fenced and not _FENCE_RE.match(line)]


def check_python_interpreter(text: str) -> list[str]:
    """CR-MDB-064 §S5: the ``python3`` requirement reads as a Python 3.14 interpreter —
    ``python3`` on ``PATH``, else one uv provides — with ``uv python install 3.14`` as the
    remediation; ``python3`` is not among the tools needing elevated privileges; the sample
    pre-flight lines match §S2's stderr line."""
    out = []
    items = [i for i in _list_items(_section(text, PREREQUISITES)) if has_code_token(i, "python3")]
    if not items:
        out.append(f"{PREREQUISITES}: no item names `python3`")
    for item in items:
        head = " ".join(item.split())[:60]
        if not _PYTHON_FLOOR_WORDING.search(item):
            out.append(f"{PREREQUISITES}: the `python3` item does not read as a Python 3.14 "
                       f"interpreter: {head!r}")
        if not _PATH_WORD.search(item):
            out.append(f"{PREREQUISITES}: the `python3` item does not say `python3` on `PATH`: "
                       f"{head!r}")
        if not has_code_token(item, PYTHON_REMEDIATION):
            out.append(f"{PREREQUISITES}: the `python3` item does not name `{PYTHON_REMEDIATION}`: "
                       f"{head!r}")
    lists = [m.group(1) for m in _ELEVATED_LIST.finditer(" ".join(_section(text, OFFERS).split()))]
    if not lists:
        out.append(f"{OFFERS}: no list of the tools that need elevated privileges")
    if any(has_code_token(names, "python3") for names in lists):
        out.append(f"{OFFERS}: `python3` is listed among the tools that need elevated privileges")
    accepted = [m for m in (PYTHON_ACCEPTED_LINE.match(line)
                            for line in _fenced_lines(_section(text, PREFLIGHT))) if m]
    if not any((int(m.group(2)), int(m.group(3))) >= PYTHON_FLOOR for m in accepted):
        out.append(f"{PREFLIGHT}: the sample pre-flight shows no `python3: <path> (<version>)` "
                   "line at 3.14 or later")
    for line in _fenced_lines(text):
        if line.startswith("python3:") and not PYTHON_ACCEPTED_LINE.match(line):
            out.append(f"sample line {line!r} does not match `python3: <path> (<version>)`")
        # MIGRATED at CR-MDB-063 C3 RED (§S7): a refusal sample behind the installer's
        # error prefix is judged too (was: only lines beginning `python3=`).
        refusal = line.removeprefix(ERROR_PREFIX)
        if refusal.startswith("python3=") and not PYTHON_REFUSAL_LINE.match(refusal):
            out.append(f"sample line {line!r} does not match `python3=outdated|absent — <reason>; "
                       f"install it with: {PYTHON_REMEDIATION}`")
    return out


_CONFORMING_PYTHON_GUIDE = (
    f"## {PREREQUISITES}\n\n"
    "6. **`python3`** — required: a Python 3.14 interpreter, the `python3` on your `PATH`, else\n"
    f"   one uv provides. Install one with `{PYTHON_REMEDIATION}`.\n"
    "7. **Recommended tools.** The install goes ahead without them:\n"
    "   - `bash` and `jq` — from your operating system's package manager;\n\n"
    f"## {PREFLIGHT}\n\n"
    "```text\n"
    "deps: uv=detected sandesh=detected crucible=detected\n"
    "python3: /usr/bin/python3 (3.14.0)\n"
    "```\n\n"
    "Refused, it reads:\n\n"
    "```text\n"
    f"python3=outdated — /usr/bin/python3 is 3.12.3; install it with: {PYTHON_REMEDIATION}\n"
    "```\n\n"
    f"## {OFFERS}\n\n"
    "Tools that need elevated privileges (`mvn`, `java`, `node`, `g++`) are only named.\n"
)


class InstallGuidePythonInterpreterTest(unittest.TestCase):
    """CR-MDB-064 §S5: the guide states the 3.14 interpreter, its remediation, and §S2's
    pre-flight line."""

    maxDiff = None

    def test_guide_states_the_python_3_14_interpreter_its_remediation_and_sample_line(self):
        self.assertTrue(GUIDE.is_file(), f"{GUIDE.relative_to(REPO_ROOT)} must exist")
        self.assertEqual(check_python_interpreter(_read(GUIDE)), [])

    def test_checker_passes_a_conforming_guide(self):
        self.assertEqual(check_python_interpreter(_CONFORMING_PYTHON_GUIDE), [])
        above = _CONFORMING_PYTHON_GUIDE.replace("(3.14.0)", "(3.15.1)")
        self.assertEqual(check_python_interpreter(above), [], "a 3.15 sample is above the floor")
        final = _CONFORMING_PYTHON_GUIDE.replace("a Python 3.14 interpreter,", "an interpreter of Python 3.14.")
        self.assertEqual(check_python_interpreter(final), [], "a sentence may end on the floor")

    def test_checker_bites_on_python3_from_the_package_manager(self):
        old = _CONFORMING_PYTHON_GUIDE.replace(
            "6. **`python3`** — required: a Python 3.14 interpreter, the `python3` on your `PATH`, "
            f"else\n   one uv provides. Install one with `{PYTHON_REMEDIATION}`.\n", "").replace(
            "   - `bash` and `jq`", "   - `python3`, `bash` and `jq`")
        head = repr("- `python3`, `bash` and `jq` — from your operating system's package manager;"[:60])
        self.assertEqual(check_python_interpreter(old), [
            f"{PREREQUISITES}: the `python3` item does not read as a Python 3.14 interpreter: {head}",
            f"{PREREQUISITES}: the `python3` item does not say `python3` on `PATH`: {head}",
            f"{PREREQUISITES}: the `python3` item does not name `{PYTHON_REMEDIATION}`: {head}",
        ])

    def test_checker_bites_on_a_missing_python3_item(self):
        gone = _CONFORMING_PYTHON_GUIDE.replace("6. **`python3`**", "6. **the interpreter**").replace(
            "the `python3` on your", "the one on your")
        self.assertEqual(check_python_interpreter(gone), [f"{PREREQUISITES}: no item names `python3`"])

    def test_checker_bites_on_an_older_floor_or_another_remediation(self):
        older = _CONFORMING_PYTHON_GUIDE.replace("a Python 3.14 interpreter", "a Python 3.11 interpreter")
        self.assertEqual(len(check_python_interpreter(older)), 1)
        self.assertIn("does not read as a Python 3.14 interpreter", check_python_interpreter(older)[0])
        other = _CONFORMING_PYTHON_GUIDE.replace(f"`{PYTHON_REMEDIATION}`", "`apt install python3`", 1)
        self.assertEqual(len(check_python_interpreter(other)), 1)
        self.assertIn(f"does not name `{PYTHON_REMEDIATION}`", check_python_interpreter(other)[0])

    def test_checker_bites_on_python3_needing_elevated_privileges(self):
        listed = _CONFORMING_PYTHON_GUIDE.replace("`g++`)", "`g++`, `python3`)")
        self.assertEqual(check_python_interpreter(listed), [
            f"{OFFERS}: `python3` is listed among the tools that need elevated privileges"])
        dropped = _CONFORMING_PYTHON_GUIDE.replace(
            "Tools that need elevated privileges (`mvn`, `java`, `node`, `g++`) are only named.", "")
        self.assertEqual(check_python_interpreter(dropped), [
            f"{OFFERS}: no list of the tools that need elevated privileges"])

    def test_checker_bites_on_sample_lines_that_miss_the_stderr_line(self):
        no_line = _CONFORMING_PYTHON_GUIDE.replace("python3: /usr/bin/python3 (3.14.0)\n", "")
        self.assertEqual(check_python_interpreter(no_line), [
            f"{PREFLIGHT}: the sample pre-flight shows no `python3: <path> (<version>)` line at "
            "3.14 or later"])
        below = _CONFORMING_PYTHON_GUIDE.replace("(3.14.0)", "(3.13.2)")
        self.assertEqual(check_python_interpreter(below), [
            f"{PREFLIGHT}: the sample pre-flight shows no `python3: <path> (<version>)` line at "
            "3.14 or later"])
        bare = _CONFORMING_PYTHON_GUIDE.replace("python3: /usr/bin/python3 (3.14.0)",
                                                "python3: detected")
        self.assertIn("sample line 'python3: detected' does not match "
                      "`python3: <path> (<version>)`", check_python_interpreter(bare))
        refusal = _CONFORMING_PYTHON_GUIDE.replace(f"install it with: {PYTHON_REMEDIATION}",
                                                   "install it with: apt install python3")
        self.assertEqual(len(check_python_interpreter(refusal)), 1)
        self.assertTrue(check_python_interpreter(refusal)[0].startswith(
            "sample line 'python3=outdated — /usr/bin/python3 is 3.12.3; install it with: "
            "apt install python3' does not match"))

    # -- CR-MDB-063 §S7: a refusal sample behind the installer's error prefix is judged too ----

    def test_checker_judges_a_refusal_sample_behind_the_error_prefix(self):
        refusal = f"python3=outdated — /usr/bin/python3 is 3.12.3; install it with: {PYTHON_REMEDIATION}"
        prefixed = _CONFORMING_PYTHON_GUIDE.replace(refusal, ERROR_PREFIX + refusal)
        self.assertNotEqual(prefixed, _CONFORMING_PYTHON_GUIDE, "precondition: the prefix applied")
        self.assertEqual(check_python_interpreter(prefixed), [],
                         "a conforming refusal sample behind the prefix passes")
        wrong = prefixed.replace(f"install it with: {PYTHON_REMEDIATION}",
                                 "install it with: apt install python3")
        found = check_python_interpreter(wrong)
        self.assertEqual(len(found), 1, found)
        self.assertTrue(found[0].startswith(
            f"sample line '{ERROR_PREFIX}python3=outdated — /usr/bin/python3 is 3.12.3; "
            "install it with: apt install python3' does not match"), found[0])
        other = prefixed.replace("python3=outdated — ", "python3=missing — ")
        self.assertEqual(len(check_python_interpreter(other)), 1,
                         "a verdict other than outdated|absent behind the prefix is reported")

    def test_the_guides_own_refusal_sample_is_judged_and_conforms(self):
        text = _read(GUIDE)
        samples = [line for line in _fenced_lines(text)
                   if line.startswith(ERROR_PREFIX + "python3=")]
        self.assertEqual(len(samples), 1, f"the guide's refusal sample: {samples!r}")
        self.assertEqual(check_python_interpreter(text), [])
        broken = text.replace(samples[0], samples[0].replace(
            f"install it with: {PYTHON_REMEDIATION}", "install it with: apt install python3"))
        self.assertNotEqual(broken, text, "precondition: the sample was changed")
        found = check_python_interpreter(broken)
        self.assertEqual(len(found), 1, found)
        self.assertTrue(found[0].startswith("sample line "), found[0])
        self.assertIn("install it with: apt install python3", found[0])
        self.assertIn("does not match `python3=outdated|absent", found[0])


# ---------------------------------------------------------------------------
# CR-MDB-063 §S7 — the install commands, the test interpreters, the offers
# ---------------------------------------------------------------------------
#
# Contract: ``docs/changes/CR-MDB-063-python-test-interpreter-probe.md`` §S7 (DN §D21 amended
# 2026-10-14). Every expected string is DERIVED from ``modelb_axi.requirements``: the ``python3``
# PATH probe's install argv (``uv python install --default 3.14``), the ``.venv`` route
# (``PYTHON_VENV_ROUTE``), the per-project modules and the elevated tools (each probe's
# ``no_install``), and the interpreter's remediation (the ``python3`` requirement row).

PI_PACKAGE_README = REPO_ROOT / "pi-package" / "README.md"
AGENTS_MD = REPO_ROOT / "AGENTS.md"
#: The interpreter every install or update of the installer names.
PYTHON_FLAG = ("--python", "3.14")
#: The installer's error prefix ahead of a refusal on stderr.
ERROR_PREFIX = "modelb-axi: error: "
#: A ``uv tool install|upgrade`` command, up to a shell separator or a comment.
_UV_TOOL_COMMAND = re.compile(r"(?<![\w-])uv tool (install|upgrade)\b([^;&|#]*)")
_PIP_EDITABLE = re.compile(r"(?<![\w-])pip install -e \.(?![\w/])")
_RAW_PIP_INSTALL = re.compile(r"(?:^|-m )pip install\b")


def python3_path_install() -> str:
    """The ``python3`` PATH probe's installer command, as the pre-flight shows it."""
    probes = {p["name"]: p for p in STACK_TOOLCHAINS["python"]}
    return install_display(probes["python3"]["install"])


def _no_install_names(reason: str) -> list[str]:
    names: list[str] = []
    for probes in STACK_TOOLCHAINS.values():
        for probe in probes:
            if probe["no_install"] == reason and probe["name"] not in names:
                names.append(probe["name"])
    return names


def elevated_tools() -> list[str]:
    """The probes named, never run, because their installer needs elevated privileges."""
    return _no_install_names(ELEVATED)


def per_project_modules() -> list[str]:
    """The probes never offered, because their route runs in each python project."""
    return _no_install_names(PER_PROJECT)


def _flat(text: str) -> str:
    """Backticks and ``*`` dropped, curly apostrophes straightened, whitespace collapsed,
    lower-cased."""
    text = text.replace("`", "").replace("*", "").replace("\N{RIGHT SINGLE QUOTATION MARK}", "'")
    return " ".join(text.split()).lower()


def install_command_findings(text: str) -> list[str]:
    """Each ``uv tool install`` or ``uv tool upgrade`` of ``modelb-axi`` or ``.`` shown in
    ``text`` (a code span or a fenced line) without ``--python 3.14``."""
    out = []
    for code in code_texts(text):
        for m in _UV_TOOL_COMMAND.finditer(code):
            words = m.group(2).split()
            if not words or words[-1] not in ("modelb-axi", "."):
                continue
            if PYTHON_FLAG not in list(zip(words, words[1:], strict=False)):
                out.append(f"`uv tool {m.group(1)} {' '.join(words)}` lacks `--python 3.14`")
    return out


def check_agents_md_install(text: str) -> list[str]:
    """Model B's ``AGENTS.md``: no install of ``.`` without ``--python 3.14``, and no
    ``pip install -e .`` (PEP 668 refuses it)."""
    return install_command_findings(text) + [
        f"names `{m.group(0)}`, which PEP 668 refuses" for m in _PIP_EDITABLE.finditer(text)]


def check_python3_prerequisite(text: str) -> list[str]:
    """The prerequisites' ``python3`` item names both uv installs and says every stack's
    Crucible client runs on the ``python3`` on ``PATH``."""
    default = python3_path_install()
    items = [i for i in _list_items(_section(text, PREREQUISITES)) if has_code_token(i, "python3")]
    out = []
    if not any(has_code_token(i, PYTHON_REMEDIATION) and has_code_token(i, default) for i in items):
        out.append(f"{PREREQUISITES}: the `python3` item does not name both `{PYTHON_REMEDIATION}` "
                   f"and `{default}`")
    if not any(re.search(r"\bevery stack'?s (?:crucible )?clients?\b", _flat(i))
               and re.search(r"\bpython3 on (?:your )?path\b", _flat(i)) for i in items):
        out.append(f"{PREREQUISITES}: the `python3` item does not say every stack's Crucible "
                   "client runs on the `python3` on `PATH`")
    return out


def _stack_tool_entry(section: str, stack: str) -> str | None:
    """The tools the pre-flight section's list gives ``stack`` (``\\`<stack>\\` — …``, up to
    ``;`` or the sentence's end), or ``None``."""
    flat = " ".join(section.split())
    m = re.search(rf"`{re.escape(stack)}`(?: and `[\w+-]+`)?\s*[—:-]\s*(.*?)(?:;|\.(?=\s|$))", flat)
    return m.group(1) if m else None


def check_preflight_python3(text: str) -> list[str]:
    """The pre-flight section tells ``stack <name>: python3=`` (the ``PATH`` presence check
    for that stack's client) from the ``python3:`` line, says the two can disagree, lists
    ``python3`` for every stack, and says ``xmlrunner``/``coverage`` are checked in the
    ``PATH`` ``python3`` while a python project's tests run under its ``.venv``."""
    sec = _section(text, PREFLIGHT)
    prose = _prose_blocks(sec)
    out = []
    if not any(has_code_token(b, "stack <name>: python3=") and has_code_token(b, "python3:")
               and all(w in _flat(b) for w in ("presence", "client", "path")) for b in prose):
        out.append(f"{PREFLIGHT}: does not say `stack <name>: python3=` is a `PATH` presence "
                   "check for that stack's client, distinct from the `python3:` line")
    if "disagree" not in _flat(sec):
        out.append(f"{PREFLIGHT}: does not say the two `python3` lines can disagree")
    for stack in known_stacks():
        entry = _stack_tool_entry(sec, stack)
        if entry is None or not has_code_token(entry, "python3"):
            out.append(f"{PREFLIGHT}: the tool list does not name `python3` for `{stack}`")
    modules = per_project_modules()
    if not any(all(has_code_token(b, m) for m in modules) and ".venv" in _flat(b)
               and "python project" in _flat(b) and "path" in _flat(b) for b in prose):
        out.append(f"{PREFLIGHT}: does not say `xmlrunner` and `coverage` are checked in the "
                   "`PATH` `python3` and a python project's tests run under its `.venv`")
    return out


def check_toolchain_warning(text: str) -> list[str]:
    """The warnings table's ``toolchain`` row: an absent ``xmlrunner``/``coverage`` means the
    ``PATH`` ``python3`` cannot run python tests; a python project runs them under its
    ``.venv``."""
    row = re.search(r"^\| `toolchain` \|.*$", _section(text, WARNINGS), re.M)
    if row is None:
        return [f"{WARNINGS}: no `toolchain` row"]
    line, flat = row.group(0), _flat(row.group(0))
    if (all(has_code_token(line, m) for m in per_project_modules())
            and all(w in flat for w in ("cannot run python tests", "path", "python3", ".venv",
                                        "python project"))):
        return []
    return [f"{WARNINGS}: the `toolchain` row does not say an absent `xmlrunner`/`coverage` means "
            "the `PATH` `python3` cannot run python tests, and a python project runs them under "
            "its `.venv`"]


def check_offers_route(text: str) -> list[str]:
    """Choosing stacks and Install offers each name ``uv python install --default 3.14`` as an
    offer, show no ``pip install`` and say ``xmlrunner``/``coverage`` are never offered (their
    route runs in each python project); the elevated-privileges list stays the elevated tools."""
    default = python3_path_install()
    modules = per_project_modules()
    out = []
    for heading in (STACKS, OFFERS):
        sec = _section(text, heading)
        if not has_code_token(sec, default):
            out.append(f"{heading}: does not name `{default}` as an offer")
        out.extend(f"{heading}: still shows `{c}`" for c in code_texts(sec)
                   if _RAW_PIP_INSTALL.search(c))
        if not any(all(has_code_token(b, m) for m in modules)
                   and re.search(r"\bnever\b.{0,20}\boffered\b", _flat(b))
                   and re.search(r"\beach (?:python )?project\b", _flat(b))
                   for b in _prose_blocks(sec)):
            out.append(f"{heading}: does not say `xmlrunner` and `coverage` are never offered, "
                       "their route running in each python project")
    lists = [re.findall(r"`([^`]+)`", m.group(1))
             for m in _ELEVATED_LIST.finditer(" ".join(_section(text, OFFERS).split()))]
    if not lists:
        out.append(f"{OFFERS}: no list of the tools that need elevated privileges")
    out.extend(f"{OFFERS}: the elevated-privileges list is {names}, not {elevated_tools()}"
               for names in lists if names != elevated_tools())
    return out


def check_already_installed_interpreter(text: str) -> list[str]:
    """The ``already_installed`` report names the dead-interpreter case: ``outdated`` with an
    ``interpreter`` object (``path``, ``reason``)."""
    if any(all(has_code_token(b, t) for t in ("outdated", "interpreter", "path", "reason"))
           for b in _prose_blocks(_section(text, OUTCOMES))):
        return []
    return [f"{OUTCOMES}: the `already_installed` report does not name `outdated` with an "
            "`interpreter` object (`path`, `reason`)"]


#: §S7's guide points, each a checker over the whole guide.
INTERPRETER_POINT_CHECKERS = {
    "prerequisite": check_python3_prerequisite,
    "pre-flight": check_preflight_python3,
    "warnings table": check_toolchain_warning,
    "choosing stacks and offers": check_offers_route,
    "already_installed": check_already_installed_interpreter,
}


def conforming_interpreter_points() -> str:
    """A sample guide stating every §S7 point, built from the requirements data."""
    default = python3_path_install()
    route = ", then ".join(f"`{c}`" for c in PYTHON_VENV_ROUTE)
    elevated = ", ".join(f"`{t}`" for t in elevated_tools())
    tools = "; ".join(f"`{s}` — " + ", ".join(f"`{p['name']}`" for p in STACK_TOOLCHAINS[s])
                      for s in known_stacks())
    never = ("`xmlrunner` and `coverage` are never offered: their route runs in each python "
             f"project, {route}.")
    return (
        f"## {PREREQUISITES}\n\n"
        "7. **`python3`** — required: a Python 3.14 interpreter. Install one with "
        f"`{PYTHON_REMEDIATION}`;\n   `{default}` also puts `python3` on your `PATH`. Every "
        "stack's Crucible client runs on the\n   `python3` on your `PATH`.\n\n"
        f"## {STACKS}\n\n"
        f"A missing tool is offered its installer, such as `{default}`.\n\n{never}\n\n"
        f"## {PREFLIGHT}\n\n"
        f"- `stack <name>:` — the tools checked are: {tools}. `xmlrunner` and `coverage` are "
        "checked in the `python3` on your `PATH`; a python project's tests run under its own "
        "`.venv`.\n\n"
        "`stack <name>: python3=` is a `PATH` presence check for that stack's client, distinct "
        "from the `python3:` line, the interpreter the deployed scripts run on. On a uv-only "
        "machine the two lines can disagree.\n\n"
        f"## {WARNINGS}\n\n"
        "| Requirement | If it is missing |\n|---|---|\n"
        "| `toolchain` | an absent `xmlrunner` or `coverage` means the `PATH` `python3` cannot "
        "run python tests; a python project runs them under its `.venv`. |\n\n"
        f"## {OFFERS}\n\n"
        f"- **Toolchain installers.** For example `{default}`.\n\n{never}\n\n"
        f"Tools that need elevated privileges ({elevated}) are only named.\n\n"
        f"## {OUTCOMES}\n\n"
        "When the recorded interpreter is gone, `freshness` is `outdated` and the report carries "
        "`interpreter`, with its `path` and the `reason`.\n"
    )


class InstallCommandsNamePython314Test(unittest.TestCase):
    """§S7 — every install or update of the installer (``modelb-axi`` or ``.``) in the guide,
    the Pi package README and Model B's ``AGENTS.md`` names ``--python 3.14``; ``AGENTS.md``
    names no ``pip install -e .``."""

    maxDiff = None

    GOOD = ("```sh\nuv tool install --python 3.14 modelb-axi\nmodelb-axi --version\n```\n\n"
            "Update with `uv tool upgrade --python 3.14 modelb-axi`. From a source copy run "
            "`uv tool install --python 3.14 .`; update with\n"
            "`uv tool install --reinstall --python 3.14 .`. Sandesh: `uv tool install sandesh-relay`, "
            "`uv tool upgrade sandesh-relay`, `uv tool install --reinstall sandesh-relay`.\n")

    def test_the_derived_vocabulary_matches_the_requirements(self):
        self.assertEqual(python3_path_install(), "uv python install --default 3.14")
        self.assertEqual(elevated_tools(), ["mvn", "java", "node", "g++"])
        self.assertEqual(per_project_modules(), ["xmlrunner", "coverage"])
        self.assertEqual(PYTHON_REMEDIATION, "uv python install 3.14")

    def test_checker_passes_every_command_naming_python_3_14_and_other_tools(self):
        self.assertEqual(install_command_findings(self.GOOD), [])
        self.assertEqual(check_agents_md_install(self.GOOD), [])

    def test_checker_reports_each_install_or_upgrade_without_python_3_14(self):
        cases = {
            "uv tool install --python 3.14 modelb-axi": "uv tool install modelb-axi",
            "uv tool upgrade --python 3.14 modelb-axi": "uv tool upgrade modelb-axi",
            "uv tool install --python 3.14 .`;": "uv tool install .",
            "uv tool install --reinstall --python 3.14 .`.": "uv tool install --reinstall .",
        }
        for good, shown in cases.items():
            with self.subTest(command=shown):
                text = self.GOOD.replace(good, good.replace("--python 3.14 ", ""))
                self.assertNotEqual(text, self.GOOD, "precondition: the command was changed")
                self.assertEqual(install_command_findings(text),
                                 [f"`{shown}` lacks `--python 3.14`"])
        older = self.GOOD.replace("upgrade --python 3.14", "upgrade --python 3.13")
        self.assertEqual(install_command_findings(older),
                         ["`uv tool upgrade --python 3.13 modelb-axi` lacks `--python 3.14`"])

    def test_agents_md_checker_reports_a_bare_dot_install_and_pip_editable(self):
        text = ("```bash\nuv tool install .                       # or: pip install -e .\n```\n"
                "- Tests import `modelb_axi` — install the package (`pip install -e .`).\n")
        self.assertEqual(check_agents_md_install(text), [
            "`uv tool install .` lacks `--python 3.14`",
            "names `pip install -e .`, which PEP 668 refuses",
            "names `pip install -e .`, which PEP 668 refuses",
        ])
        fixed = text.replace("install .  ", "install --python 3.14 .").replace(
            "  # or: pip install -e .", "").replace(" (`pip install -e .`)", "")
        self.assertEqual(check_agents_md_install(fixed), [])

    def test_the_guide_names_python_3_14_on_every_installer_command(self):
        self.assertEqual(install_command_findings(_read(GUIDE)), [])

    def test_the_pi_package_readme_names_python_3_14_on_every_installer_command(self):
        self.assertTrue(PI_PACKAGE_README.is_file(), "pi-package/README.md must exist")
        self.assertEqual(install_command_findings(_read(PI_PACKAGE_README)), [])

    def test_model_b_agents_md_installs_with_python_3_14_and_never_pip_editable(self):
        self.assertEqual(check_agents_md_install(_read(AGENTS_MD)), [])


class InstallGuideTestInterpreterPointsTest(unittest.TestCase):
    """§S7 — the guide states each test-interpreter point; each checker proved both ways on
    sample text, then run over the real guide."""

    maxDiff = None

    def setUp(self):
        self.sample = conforming_interpreter_points()

    def test_the_sample_passes_every_point(self):
        for label, checker in INTERPRETER_POINT_CHECKERS.items():
            with self.subTest(point=label):
                self.assertEqual(checker(self.sample), [])

    def _changed(self, old: str, new: str, count: int = -1) -> str:
        text = self.sample.replace(old, new, count)
        self.assertNotEqual(text, self.sample, f"precondition: {old!r} is in the sample")
        return text

    def test_prerequisite_point_bites(self):
        default = python3_path_install()
        no_default = self._changed(f"`{default}` also puts `python3` on your `PATH`. ", "")
        self.assertEqual(check_python3_prerequisite(no_default), [
            f"{PREREQUISITES}: the `python3` item does not name both `{PYTHON_REMEDIATION}` and "
            f"`{default}`"])
        no_client = self._changed("Every stack's Crucible client runs on the\n   `python3` on your "
                                  "`PATH`.", "")
        self.assertEqual(check_python3_prerequisite(no_client), [
            f"{PREREQUISITES}: the `python3` item does not say every stack's Crucible client runs "
            "on the `python3` on `PATH`"])

    def test_preflight_point_bites(self):
        cases = {
            "no presence check": (("is a `PATH` presence check", "is a `PATH` check"),
                                  f"{PREFLIGHT}: does not say `stack <name>: python3=` is a `PATH` "
                                  "presence check for that stack's client, distinct from the "
                                  "`python3:` line"),
            "not told from the python3: line": (("distinct from the `python3:` line", "apart"),
                                                f"{PREFLIGHT}: does not say `stack <name>: "
                                                "python3=` is a `PATH` presence check for that "
                                                "stack's client, distinct from the `python3:` line"),
            "no disagreement": (("can disagree", "can differ"),
                                f"{PREFLIGHT}: does not say the two `python3` lines can disagree"),
            "rust lists no python3": (("`rust` — `python3`, ", "`rust` — "),
                                      f"{PREFLIGHT}: the tool list does not name `python3` for "
                                      "`rust`"),
            "no .venv": (("; a python project's tests run under its own `.venv`", ""),
                         f"{PREFLIGHT}: does not say `xmlrunner` and `coverage` are checked in the "
                         "`PATH` `python3` and a python project's tests run under its `.venv`"),
        }
        for label, ((old, new), expected) in cases.items():
            with self.subTest(case=label):
                self.assertEqual(check_preflight_python3(self._changed(old, new)), [expected])

    def test_warnings_point_bites(self):
        expected = [f"{WARNINGS}: the `toolchain` row does not say an absent `xmlrunner`/`coverage` "
                    "means the `PATH` `python3` cannot run python tests, and a python project "
                    "runs them under its `.venv`"]
        self.assertEqual(check_toolchain_warning(self._changed(
            "; a python project runs them under its `.venv`", "")), expected)
        self.assertEqual(check_toolchain_warning(self._changed(
            "cannot run python tests", "is incomplete")), expected)
        self.assertEqual(check_toolchain_warning(self._changed("| `toolchain` |", "| `chain` |")),
                         [f"{WARNINGS}: no `toolchain` row"])

    def test_offers_point_bites(self):
        default = python3_path_install()
        never = (f"{STACKS}: does not say `xmlrunner` and `coverage` are never offered, their route "
                 "running in each python project")
        cases = {
            "stacks names no default": (
                self._changed(f"such as `{default}`", "such as rustup"),
                [f"{STACKS}: does not name `{default}` as an offer"]),
            "offers names no default": (
                self._changed(f"For example `{default}`", "For example rustup"),
                [f"{OFFERS}: does not name `{default}` as an offer"]),
            "pip parenthetical kept": (
                self._changed("For example", "For example (`python3 -m pip install "
                                             "unittest-xml-reporting coverage` covers both)"),
                [f"{OFFERS}: still shows `python3 -m pip install unittest-xml-reporting "
                 "coverage`"]),
            "modules offered": (self._changed("are never offered", "are offered", 1), [never]),
            "route not per project": (
                self._changed("runs in each python project", "runs once", 1), [never]),
            "elevated list widened": (
                self._changed("`g++`)", "`g++`, `python3`)"),
                [f"{OFFERS}: the elevated-privileges list is {elevated_tools() + ['python3']}, "
                 f"not {elevated_tools()}"]),
            "elevated list gone": (
                self._changed("Tools that need elevated privileges", "Some tools"),
                [f"{OFFERS}: no list of the tools that need elevated privileges"]),
        }
        for label, (text, expected) in cases.items():
            with self.subTest(case=label):
                self.assertEqual(check_offers_route(text), expected)
        self.assertEqual(check_offers_route(self.sample + "\nRun `uv pip install x` in the venv.\n"),
                         [], "the route's own `uv pip install` is no pip parenthetical")

    def test_already_installed_point_bites(self):
        expected = [f"{OUTCOMES}: the `already_installed` report does not name `outdated` with an "
                    "`interpreter` object (`path`, `reason`)"]
        for old, new in (("`interpreter`", "an interpreter field"), ("`reason`", "why"),
                         ("`path`", "path"), ("is `outdated`", "is stale")):
            with self.subTest(case=old):
                self.assertEqual(check_already_installed_interpreter(self._changed(old, new)),
                                 expected)

    # -- the real guide ---------------------------------------------------------------------

    def test_the_guide_states_the_python3_prerequisite(self):
        self.assertEqual(check_python3_prerequisite(_read(GUIDE)), [])

    def test_the_guide_explains_the_stack_python3_line_and_the_venv(self):
        self.assertEqual(check_preflight_python3(_read(GUIDE)), [])

    def test_the_guides_toolchain_warning_names_the_path_python3_and_the_venv(self):
        self.assertEqual(check_toolchain_warning(_read(GUIDE)), [])

    def test_the_guides_stacks_and_offers_name_the_default_install_and_never_offer_the_modules(self):
        self.assertEqual(check_offers_route(_read(GUIDE)), [])

    def test_the_guides_already_installed_report_names_the_dead_interpreter(self):
        self.assertEqual(check_already_installed_interpreter(_read(GUIDE)), [])


if __name__ == "__main__":
    unittest.main()
