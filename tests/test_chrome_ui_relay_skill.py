"""The Chrome-UI-Relay skill — its bundle and its text (CR-MDB-061 §S1–§S7).

Contract: ``docs/changes/CR-MDB-061-browser-relay-for-pi-sessions.md`` (design reference
DN-multi-harness-deploy-model §D23 and §D18). The deliverable is one Markdown skill,
``skills-src/chrome-ui-relay/SKILL.md``; these tests pin its text.

Class map:

- ``ChromeUiRelayBundleTest`` — §S1: the bundle exists, its frontmatter is clean (the
  ``frontmatter_violations`` rule of ``tests/test_skill_frontmatter.py``) with
  ``name: chrome-ui-relay``, its heading is "Chrome-UI-Relay", it carries no stack scope and bundle
  discovery selects it for every stack selection; it writes grep, head and tail as plain words,
  never code spans; its example URL is the ``<dev-url>`` placeholder and it names no host and port.
- ``ChromeUiRelayPhraseRulesTest`` — §S1 (the not-the-omp-relay statement) and §S2–§S7: one
  phrase gate per acceptance rule, one test method per rule, each generated from ``PHRASE_RULES``.
- ``ChromeUiRelayPhraseDetectorProofTest`` — every detector kind proved both ways on
  ``CONFORMING_SAMPLE``, a spec-worded sample skill: the sample passes every gate, and each rule's
  cut of the sample bites that rule.
- ``OpenStepGateTest`` — negative gate 1: no ``chrome-devtools-axi open`` shown as a step.
- ``PipedOutputGateTest`` — negative gate 2: no ``chrome-devtools-axi`` output shown piped
  through grep, head, tail or ``jq``, or redirected away.

**A phrase rule** is a set of patterns that must all match inside ONE unit of the skill's body
(``units``): a paragraph, a list item together with its nested items, a heading, a table row or a
whole fenced block; a paragraph ending in ``:`` is a lead-in and takes the list that follows it.
Each unit is normalised (``normalise``) — backticks and ``*`` dropped, curly quotes straightened,
whitespace collapsed, lower-cased — so a phrase matches however the line is wrapped or marked up.

**The negative gates** read the skill as the raw-runner guard does (``_blocks``, ``_code_spans``,
``_QUOTE`` imported from ``tests/test_raw_runner_guard.py``): a fenced line is judged alone, a code
span against the masked prose before it. A form is exempt when a prohibition governs it — the
guard's ``PROHIBITION`` in the clause the guard's ``_CLAUSE_END`` ends, both imported, never copied.

Existing gates over every bundle cover the rest of §S1 and are not repeated here: Pi's loader
(``PiSkillLoaderOracleTest``), the frontmatter tree (``FrontmatterTreeTest``), the tool-name
ratchet, the project-name gate and the raw-runner guard.

Hermetic: reads repository files only; nothing runs ``chrome-devtools-axi`` or ``npx``, and
nothing touches a browser. Stdlib only.
"""

import re
import unittest

from modelb_axi import deploy
from tests._helpers import REPO_ROOT, read_text, split_frontmatter
from tests.test_installer_stack_selection import ALL_STACKS
from tests.test_raw_runner_guard import _CLAUSE_END, PROHIBITION, _blocks, _code_spans, _QUOTE
from tests.test_skill_frontmatter import frontmatter_violations

BUNDLE = "chrome-ui-relay"
SKILL_MD = REPO_ROOT / "skills-src" / BUNDLE / "SKILL.md"
HEADING = "Chrome-UI-Relay"
#: §S1: the placeholder an example URL is written as.
DEV_URL_PLACEHOLDER = "<dev-url>"

# ------------------------------------------------------------------ units ----

_FENCE_LINE = re.compile(r"^\s*(`{3,}|~{3,})")
_HEADING_LINE = re.compile(r"^\s*#{1,6}\s")
_LIST_ITEM = re.compile(r"^(\s*)(?:[-*+]|\d+[.)])\s+")
_CURLY = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"'})


def normalise(text: str) -> str:
    """Backticks and ``*`` dropped, curly quotes straightened, whitespace collapsed, lower-cased."""
    text = text.replace("`", "").replace("*", "").translate(_CURLY)
    return re.sub(r"\s+", " ", text).strip().lower()


def units(text: str) -> list[str]:
    """The normalised units of ``text``'s body (its frontmatter left out): a paragraph, a
    top-level list item with its nested items and wrapped lines, a heading, a table row, a whole
    fenced block. A paragraph whose last line ends in ``:`` is a lead-in: the list after it joins
    its unit, up to the next paragraph, heading, table row or fence."""
    _frontmatter, body = split_frontmatter(text)
    out: list[str] = []
    current: list[str] = []
    fence = None
    lead_in = False
    after_blank = False

    def flush():
        if current:
            out.append(normalise("\n".join(current)))
            current.clear()

    for line in body.splitlines():
        opener = _FENCE_LINE.match(line)
        if fence is not None:
            current.append(line)
            if opener and opener.group(1)[0] == fence[0] and len(opener.group(1)) >= len(fence):
                flush()
                fence = None
            continue
        if opener:
            flush()
            fence, lead_in = opener.group(1), False
            current.append(line)
            continue
        if not line.strip():
            after_blank = True
            continue
        if _HEADING_LINE.match(line) or line.lstrip().startswith("|"):
            flush()
            out.append(normalise(line))
            lead_in = after_blank = False
            continue
        item = _LIST_ITEM.match(line)
        if item:
            if len(item.group(1)) < 2 and not lead_in:
                flush()
        elif after_blank and not line[:1].isspace():
            flush()
            lead_in = False
        if not current and not item:
            lead_in = False
        current.append(line)
        if not item and not line[:1].isspace() and line.rstrip().endswith(":"):
            lead_in = True
        after_blank = False
    flush()
    return out


def rule_findings(text: str, patterns: tuple[str, ...]) -> list[str]:
    """``[]`` when one unit of ``text`` matches every pattern; otherwise one finding naming the
    patterns the closest unit lacks."""
    compiled = [re.compile(p) for p in patterns]
    best: list[str] = list(patterns)
    for unit in units(text):
        missing = [rx.pattern for rx in compiled if not rx.search(unit)]
        if not missing:
            return []
        if len(missing) < len(best):
            best = missing
    return [f"no unit states the rule; the closest lacks {best}"]


# ------------------------------------------------------------------ shown forms ----

#: Negative gate 1: ``open`` shown as a ``chrome-devtools-axi`` step.
OPEN_STEP = re.compile(r"chrome-devtools-axi\s+open\b")
#: Negative gate 2: ``chrome-devtools-axi`` output piped through grep, head, tail or ``jq``, or
#: redirected away (``>``, ``>>``, ``N>``, ``&>``; ``2>&1`` keeps it).
PIPED_OUTPUT = re.compile(
    r"chrome-devtools-axi\b.*?(?:\|\s*(?:grep|head|tail|jq)\b|(?:^|\s)(?:\d?>{1,2}|&>)\s*(?!&\d)\S)")
#: §S1: grep, head and tail are plain words, never a code span.
PLAIN_WORD_SPAN = re.compile(r"(?:grep|head|tail)\b")
#: §S1: a host with a port — ``localhost``, a dotted quad or a dotted name, then ``:`` and digits.
HOST_PORT = re.compile(
    r"(?<![\w.-])(?:localhost|\d{1,3}(?:\.\d{1,3}){3}|[a-z0-9-]+(?:\.[a-z0-9-]+)+|\[[0-9a-f:]+\])"
    r":\d{2,5}\b", re.IGNORECASE)


def _prohibited(masked_prefix: str) -> bool:
    """True when the guard's ``PROHIBITION`` appears in the clause ``masked_prefix`` ends in
    (clauses end where the guard's ``_CLAUSE_END`` matches)."""
    return bool(PROHIBITION.search(_CLAUSE_END.split(masked_prefix)[-1]))


def shown(text: str):
    """Yield ``(line_number, content, governing_prefix)`` for each code span and each fenced line
    of ``text``, read as the raw-runner guard reads a file. ``governing_prefix`` is the masked
    prose before a span, or ``None`` for a fenced line (judged alone, on its own text)."""
    lines = [_QUOTE.sub("", line) for line in text.splitlines()]
    for first, block in _blocks(lines):
        if block is None:
            yield first + 1, lines[first].strip(), None
            continue
        joined = "\n".join(block)
        spans = list(_code_spans(joined))
        masked = list(joined)
        for start, end, _content in spans:
            masked[start:end] = "x" * (end - start)
        masked = "".join(masked)
        for start, _end, content in spans:
            yield first + joined.count("\n", 0, start) + 1, content, masked[:start]


def shown_form_findings(text: str, form: re.Pattern) -> list[tuple[int, str]]:
    """Every ``form`` a code span or a fenced line of ``text`` shows, ungoverned by a
    prohibition, as ``(line_number, shown)``."""
    findings = []
    for number, content, prefix in shown(text):
        match = form.search(content)
        if not match:
            continue
        before = content[:match.start()] if prefix is None else prefix
        if not _prohibited(before):
            findings.append((number, content))
    return findings


def plain_word_span_findings(text: str) -> list[tuple[int, str]]:
    """Every code span (not a fenced line) of ``text`` that writes grep, head or tail."""
    return [(n, c) for n, c, prefix in shown(text) if prefix is not None and PLAIN_WORD_SPAN.match(c)]


def host_port_findings(text: str) -> list[tuple[int, str]]:
    """Every line of ``text`` naming a host with a port."""
    return [(n, line.strip()) for n, line in enumerate(text.splitlines(), 1) if HOST_PORT.search(line)]


def frontmatter_value(text: str, key: str):
    """The value of ``key`` in ``text``'s frontmatter, stripped, or ``None``."""
    frontmatter, _body = split_frontmatter(text)
    match = re.search(rf"^{re.escape(key)}:[ \t]*(.*)$", frontmatter, re.MULTILINE)
    return None if match is None else match.group(1).strip()


def first_heading(text: str):
    """The text of the body's first level-1 heading, or ``None``."""
    _frontmatter, body = split_frontmatter(text)
    match = re.search(r"^#\s+(.+?)\s*$", body, re.MULTILINE)
    return None if match is None else match.group(1)


# ------------------------------------------------------------------ the rules ----

_NEVER_RETRIED = r"\b(?:never|not|no)\b[^.;]{0,10}\bretr(?:y|ied|ies)\b"

#: One phrase gate per acceptance rule: ``(test_name, section, patterns, cut)``. ``patterns`` must
#: all match inside one unit; ``cut`` is the ``(old, new)`` replacements of
#: ``CONFORMING_SAMPLE`` that remove the rule, so the proof can show the gate bites.
PHRASE_RULES = (
    # §S1
    ("s1_states_it_is_not_the_omp_era_cdp_relay_which_never_runs_under_pi", "§S1",
     (r"\bnot\b[^.;]{0,20}\bomp-era cdp relay\b",
      r"\b(?:never|not)(?: be)? run\w*\b[^.;]{0,15}\bunder pi\b"),
     (("must never run under Pi", "is retired"),)),
    # §S2
    ("s2_every_call_is_npx_with_auto_connect_and_the_project_token_session", "§S2",
     (re.escape("npx -y chrome-devtools-axi"),
      re.escape("chrome_devtools_axi_auto_connect=1"),
      r"chrome_devtools_axi_session=(?:<project_token>|\"?\$\{?project_token\}?\"?)"),
     (("`CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1`", "`CHROME_DEVTOOLS_AXI_TRACE=1`"),)),
    ("s2_each_project_has_its_own_bridge_and_its_stop_ends_only_its_own", "§S2",
     (r"\b(?:each|every) project\b", r"\bown bridge\b",
      r"\bstop\b[^.;]{0,30}\bonly\b[^.;]{0,15}\bown\b"),
     (("ends only its own", "ends every bridge"),)),
    ("s2_never_launches_a_browser", "§S2",
     (r"\bnever (?:launch|start)\w* (?:a |the )?(?:browser|chrome)\b",),
     (("never launches a browser and ", ""),)),
    ("s2_never_uses_open", "§S2",
     (r"\bnever (?:use|run|call|send)s? (?:the )?(?:npx -y )?(?:chrome-devtools-axi )?open\b",),
     (("never uses `open`", "uses every verb"),
      ("never run `npx -y chrome-devtools-axi open <dev-url>`",
       "run `npx -y chrome-devtools-axi newpage <dev-url>`"))),
    ("s2_an_absent_malformed_or_default_token_skips_the_browser_steps", "§S2",
     (r"\bproject_token\b", r"\babsent\b", re.escape("[a-za-z0-9._-]{1,64}"),
      r"\bdefault\b", r"\bbrowser steps are skipped\b"),
     (("not of the form `[A-Za-z0-9._-]{1,64}`, ", ""),)),
    ("s2_reports_no_valid_session_name_set_project_token_in_env", "§S2",
     (re.escape("no valid session name: set project_token in .env"),),
     (("no valid session name: set `PROJECT_TOKEN` in `.env`", "the token is wrong"),)),
    ("s2_never_falls_back_to_the_default_session", "§S2",
     (r"\b(?:never|not|no)\b[^.;]{0,20}\bfalls?\s*back\b[^.;]{0,20}\bdefault session\b",),
     (("it never falls back to the default session", "it uses the default session"),)),
    # §S3
    ("s3_the_caller_gives_three_lists_urls_project_patterns_and_protected_patterns", "§S3",
     (r"\bthree\b", r"\burls to open\b", r"\burl patterns\b", r"\bprotected patterns\b",
      r"\bnever selected, evaluated or closed\b"),
     (("the URL patterns the project's tabs match", "the project's tabs"),)),
    ("s3_protected_wins_a_protected_tab_never_counted_chosen_or_closed", "§S3",
     (r"\bprotected wins\b", r"\bnever counted as already open\b", r"\bnever chosen\b",
      r"\bnever closed\b"),
     (("**Protected wins everywhere.** ", ""),)),
    ("s3_a_protected_url_to_open_is_a_caller_error_reported_and_skipped", "§S3",
     (r"\burl to open\b", r"\bprotected pattern\b", r"\bcaller error\b", r"\breported\b",
      r"\bskipped\b"),
     (("is a caller error: it is reported and skipped", "is opened"),)),
    # §S4
    ("s4_open_keeps_the_pages_id_set_as_before", "§S4",
     (r"\bpages\b", r'\bid set as "?before"?'),
     (('Keep its id set as "before".', "Read it."),)),
    ("s4_an_already_open_url_is_not_reopened_and_its_tab_never_touched", "§S4",
     (r"\balready (?:shows|open)\b", r"\b(?:not|never) (?:opened again|reopened)\b",
      r"\bnever selected, evaluated or closed\b"),
     (("is not opened again", "is opened"),)),
    ("s4_opens_with_newpage_only_never_navigating_an_existing_or_selected_tab", "§S4",
     (r"\bnewpage\b", r"\bnever navigates?\b[^.;]{0,20}\b(?:existing|selected)\b"),
     ((" Never navigate an existing or selected tab.", ""),)),
    ("s4_the_new_tabs_are_the_after_ids_minus_the_before_ids", "§S4",
     (r"\bpages again\b", r'"?after"? ids minus the "?before"? ids\b'),
     (('The new tabs are the "after" ids minus the "before" ids.', "The new tabs are the last ones."),)),
    ("s4_every_url_opened_shows_and_every_before_id_stays_or_it_stops_and_reports", "§S4",
     (r"\bevery url opened\b", r'\bevery "?before"? id is still there\b', r"\bstop and report\b"),
     (('   - Every "before" id is still there.\n', ""),)),
    ("s4_the_new_ids_are_the_skills_own_tabs_kept_as_its_record_for_the_session", "§S4",
     (r"\bown tabs\b", r"\brecord\b", r"\bsession\b"),
     ((" It keeps that record for the session.", ""),)),
    ("s4_a_timed_out_newpage_is_confirmed_among_the_new_ids_never_retried", "§S4",
     (r"\btimed out\b", r"\bstill made its tab\b", _NEVER_RETRIED, r"\bduplicat"),
     (("; never retry, since a retry duplicates it", "; retry it"),)),
    ("s4_rendered_text_is_confirmed_on_the_skills_own_tabs_never_the_load_event", "§S4",
     (r"\bselectpage\b", re.escape("eval document.body.innertext.length"), r"\bown tabs only\b",
      r"\b(?:never|not) (?:on |by |from )?the load event\b"),
     ((", never the load event", ""),)),
    # §S5
    ("s5_close_takes_a_fresh_pages_and_closes_recorded_tabs_still_shown_not_protected", "§S5",
     (r"\bpages\b[^.]{0,5}\bfresh\b|\bfresh pages\b", r"\brecord\b", r"\bstill show",
      r"\bnot protected\b"),
     ((", and are not protected", ""),)),
    ("s5_pages_again_verifies_and_a_last_tab_no_op_shows_as_still_open", "§S5",
     (r"\bpages again\b", r"\bverify\b", r"\blast.tab\b", r"\bstill open\b"),
     ((" A last-tab no-op shows here as a tab still open.", ""),)),
    ("s5_stop_disconnects_the_bridge_and_never_closes_chrome", "§S5",
     (r"\bstop\b", r"\bdisconnects\b", r"\b(?:never|not) closes? (?:the user's )?chrome\b"),
     ((" and never closes Chrome", ""),)),
    ("s5_failed_control_retries_once_then_reports_the_tabs_left_open_by_url", "§S5",
     (r"\bretry once\b", r"\btabs left open\b", r"\burls\b"),
     (("retry once", "retry"),)),
    ("s5_no_record_closes_nothing_and_reports_project_tabs_for_the_user", "§S5",
     (r"\bno record\b", r"\bnothing is closed\b|\bcloses? nothing\b", r"\bfor the user to close\b"),
     (("nothing is closed", "they are closed"),)),
    ("s5_a_skipped_bootstrap_means_shutdown_skips_and_starts_no_bridge", "§S5",
     (r"\bbootstrap skipped\b", r"\bshutdown skips\b",
      r"\bstarts no bridge\b|\bnever starts a bridge\b|\bno bridge\b"),
     ((" and starts no bridge", ""),)),
    # §S6
    ("s6_a_bridge_not_ready_error_skips_the_browser_steps", "§S6",
     (r"\bbridge_not_ready\b", r"\bbrowser steps are skipped\b"),
     (("`BRIDGE_NOT_READY`", "`FAILED`"),)),
    ("s6_reports_the_envelopes_message_and_suggestions_in_full", "§S6",
     (r"\bmessage\b", r"\bsuggestions\b", r"\bin full\b"),
     ((" in full", ""),)),
    ("s6_a_skipped_browser_never_fails_bootstrap_or_shutdown", "§S6",
     (r"\b(?:never|not) fails? bootstrap or shutdown\b",),
     (("never fails bootstrap", "fails bootstrap"),)),
    ("s6_chrome_not_running_or_remote_debugging_off_enable_it_at_chrome_inspect", "§S6",
     (r"\bchrome stable\b", r"\bnot running\b", r"\bremote debugging\b",
      re.escape("chrome://inspect/#remote-debugging")),
     ((" enable it at `chrome://inspect/#remote-debugging`", " enable it"),)),
    ("s6_chromium_or_another_channel_running_instead_of_chrome_stable", "§S6",
     (r"\bchromium\b", r"\b(?:another|other|wrong) channel\b"),
     (("Chromium or another channel", "Something else"),)),
    ("s6_the_connection_prompt_not_accepted_within_the_start_up_timeout", "§S6",
     (r"\bconnection prompt\b", r"\bnot accepted\b", r"\btimeout\b"),
     (("not accepted", "seen"),)),
    ("s6_a_port_collision_code_48_sets_the_port_for_this_session_only", "§S6",
     (r"\bport collision\b", r"\bcode 48\b", r"\bchrome_devtools_axi_port\b",
      r"\bthis session only\b"),
     ((" for this session only", ""),)),
    # §S7
    ("s7_every_envelope_is_read_whole_never_piped_narrowed_or_redirected", "§S7",
     (r"\bread whole\b", r"\bnever piped\b", r"\bgrep\b", r"\bhead\b", r"\btail\b", r"\bjq\b",
      r"\bredirected away\b"),
     ((", narrowed with `jq`,", ","),)),
)

#: A spec-worded skill every gate passes — the "conforming" half of each both-ways proof.
CONFORMING_SAMPLE = """---
name: chrome-ui-relay
description: Open, read and close a frontend project's own tabs on the user's running Chrome through chrome-devtools-axi, one bridge per project.
---

# Chrome-UI-Relay

This skill is not the omp-era CDP relay; that relay must never run under Pi.

## Invocation and the session

Every call is `npx -y chrome-devtools-axi <verb>` with:

- `CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1`;
- `CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN>`, the value from the project's `.env`.

Each project has its own bridge, and its `stop` ends only its own.

It never launches a browser and never uses `open`.

Navigation is `newpage` only: never run `npx -y chrome-devtools-axi open <dev-url>`.

When `PROJECT_TOKEN` is absent, not of the form `[A-Za-z0-9._-]{1,64}`, or `default`:

- the browser steps are skipped;
- the skill reports "no valid session name: set `PROJECT_TOKEN` in `.env`";
- it never falls back to the default session.

## Inputs

The caller gives three lists:

- the URLs to open;
- the URL patterns the project's tabs match;
- the protected patterns: tabs never selected, evaluated or closed.

**Protected wins everywhere.** A protected tab is never counted as already open, never chosen and never closed. A URL to open that matches a protected pattern is a caller error: it is reported and skipped.

## Open

1. **`pages`.** Keep its id set as "before".
   - A URL to open that already shows in a tab is not opened again.
   - That tab is the user's or a previous bridge's. It is never selected, evaluated or closed.
2. **`newpage <dev-url>`** for each remaining URL. Never navigate an existing or selected tab.
3. **`pages` again.** The new tabs are the "after" ids minus the "before" ids.
   - Every URL opened shows among the new ids.
   - Every "before" id is still there.
   - Otherwise, stop and report.
   - The new ids are the skill's own tabs for this bridge. It keeps that record for the session.
4. **A `newpage` that timed out still made its tab.** Confirm it among the new ids; never retry, since a retry duplicates it.
5. **Rendered text** is confirmed with `selectpage <id>` and `eval document.body.innerText.length` on the skill's own tabs only, never the load event.

## Close

1. **`pages`, fresh.** The tabs to close are those in the skill's record that still show, and are not protected.
2. **`closepage`** each of them.
3. **`pages` again,** to verify. A last-tab no-op shows here as a tab still open.
4. **`stop`.** It disconnects the project's bridge and never closes Chrome.

- **When control fails,** retry once. Otherwise report the tabs left open, naming their URLs.
- **When there is no record,** nothing is closed. Tabs on the project's URLs are reported for the user to close.
- **When bootstrap skipped its browser steps,** shutdown skips its own and starts no bridge.

## When the bridge cannot attach

An envelope whose `error` code is `BRIDGE_NOT_READY` means:

- the skill's browser steps are skipped;
- the skill reports the envelope's message and suggestions in full;
- a skipped browser never fails bootstrap or shutdown.

The causes the tool reports, each with its fix:

- **Chrome stable not running, or remote debugging off:** enable it at `chrome://inspect/#remote-debugging`.
- **Chromium or another channel running instead of Chrome stable.**
- **Chrome's connection prompt not accepted within the start-up timeout.**
- **A port collision** ("code 48"): set `CHROME_DEVTOOLS_AXI_PORT` for this session only.

## Reading the output

Every `chrome-devtools-axi` envelope is read whole. It is never piped through grep, head or tail, narrowed with `jq`, or redirected away.
"""


def _cut(text: str, replacements) -> str:
    for old, new in replacements:
        if text.count(old) != 1:
            raise AssertionError(f"cut {old!r} must occur exactly once in the sample")
        text = text.replace(old, new)
    return text


# ------------------------------------------------------------------ tests ----

class _RealSkillCase(unittest.TestCase):
    """Reads the real skill; a missing bundle is a test failure naming it, never an error."""

    def real_text(self) -> str:
        if not SKILL_MD.is_file():
            self.fail(f"§S1: {SKILL_MD.relative_to(REPO_ROOT)} does not exist")
        return read_text(SKILL_MD)


class ChromeUiRelayBundleTest(_RealSkillCase):
    """§S1 — the bundle, its frontmatter, its heading, its deployment and its text rules."""

    def test_skill_md_frontmatter_is_clean_and_names_chrome_ui_relay(self):
        text = self.real_text()
        self.assertEqual(frontmatter_violations(text, BUNDLE), [])
        self.assertEqual(frontmatter_value(text, "name"), BUNDLE)
        self.assertTrue(frontmatter_value(text, "description"), "§S1: the skill has a description")

    def test_heading_is_chrome_ui_relay(self):
        self.assertEqual(first_heading(self.real_text()), HEADING)

    def test_no_stack_scope_and_discovered_for_every_stack_selection(self):
        self.real_text()
        self.assertNotIn(BUNDLE, deploy.STACK_SCOPED_BUNDLES, "§S1: scoped to no stack")
        missing = [stacks for stacks in [None] + [[s] for s in ALL_STACKS]
                   if BUNDLE not in {p.name for p in deploy._skill_bundles(REPO_ROOT, stacks)}]
        self.assertEqual(missing, [], "§S1: selections whose bundle discovery lacks the skill")

    def test_writes_grep_head_and_tail_as_plain_words_never_code_spans(self):
        self.assertEqual(plain_word_span_findings(self.real_text()), [])

    def test_example_urls_are_the_dev_url_placeholder_never_a_host_and_port(self):
        text = self.real_text()
        self.assertIn(DEV_URL_PLACEHOLDER, text, "§S1: an example URL is written <dev-url>")
        self.assertEqual(host_port_findings(text), [])


def _phrase_test(patterns):
    def test(self):
        self.assertEqual(rule_findings(self.real_text(), patterns), [])
    return test


class ChromeUiRelayPhraseRulesTest(_RealSkillCase):
    """§S1 (the relay statement) and §S2–§S7 — one phrase gate per rule, on the skill's text."""


for _name, _section, _patterns, _cut_pairs in PHRASE_RULES:
    _test = _phrase_test(_patterns)
    _test.__name__ = f"test_{_name}"
    _test.__doc__ = f"{_section}: {_name.split('_', 1)[1].replace('_', ' ')}."
    setattr(ChromeUiRelayPhraseRulesTest, _test.__name__, _test)


class ChromeUiRelayPhraseDetectorProofTest(unittest.TestCase):
    """Every detector kind both ways: the conforming sample passes; each cut bites its rule."""

    def test_rule_names_are_unique(self):
        names = [rule[0] for rule in PHRASE_RULES]
        self.assertEqual(len(names), len(set(names)))

    def test_conforming_sample_passes_every_phrase_rule(self):
        failing = {name: rule_findings(CONFORMING_SAMPLE, patterns)
                   for name, _s, patterns, _c in PHRASE_RULES}
        self.assertEqual({k: v for k, v in failing.items() if v}, {})

    def test_each_cut_of_the_sample_bites_its_rule(self):
        not_biting = [name for name, _s, patterns, cut in PHRASE_RULES
                      if rule_findings(_cut(CONFORMING_SAMPLE, cut), patterns) == []]
        self.assertEqual(not_biting, [])

    def test_conforming_sample_passes_the_bundle_text_gates(self):
        self.assertEqual(frontmatter_violations(CONFORMING_SAMPLE, BUNDLE), [])
        self.assertEqual(frontmatter_value(CONFORMING_SAMPLE, "name"), BUNDLE)
        self.assertEqual(first_heading(CONFORMING_SAMPLE), HEADING)
        self.assertEqual(plain_word_span_findings(CONFORMING_SAMPLE), [])
        self.assertEqual(host_port_findings(CONFORMING_SAMPLE), [])
        self.assertIn(DEV_URL_PLACEHOLDER, CONFORMING_SAMPLE)

    def test_heading_and_name_detectors_bite(self):
        self.assertEqual(first_heading("---\nname: x\n---\n\n# Chrome UI Relay\n"), "Chrome UI Relay")
        self.assertIsNone(first_heading("---\nname: x\n---\n\n## Chrome-UI-Relay\n"))
        self.assertEqual(frontmatter_value("---\nname: chrome-relay\n---\n", "name"), "chrome-relay")
        self.assertIsNone(frontmatter_value("# no frontmatter\n", "name"))

    def test_plain_word_span_detector_bites_on_spans_and_spares_plain_words_and_fences(self):
        self.assertEqual(plain_word_span_findings("Never pipe through `grep`.\n"), [(1, "grep")])
        self.assertEqual(len(plain_word_span_findings("Use `head -5` or `tail`.\n")), 2)
        self.assertEqual(plain_word_span_findings("Never piped through grep, head or tail.\n"), [])
        self.assertEqual(plain_word_span_findings("Narrowed with `jq`; a `header` field.\n"), [])

    def test_host_port_detector_bites_on_hosts_with_ports_and_spares_placeholders(self):
        for bad in ("Open `http://localhost:5173`.", "The relay held 127.0.0.1:9224.",
                    "Open `https://app.example.com:8443/`."):
            with self.subTest(bad=bad):
                self.assertEqual(len(host_port_findings(bad)), 1)
        for good in ("Open `<dev-url>`.", "Enable it at `chrome://inspect/#remote-debugging`.",
                     "Only `default` uses 9224; others hash into 9225–10224.",
                     'A port collision ("code 48").', "Set `CHROME_DEVTOOLS_AXI_PORT`."):
            with self.subTest(good=good):
                self.assertEqual(host_port_findings(good), [])

    def test_units_merge_a_lead_in_with_its_list_and_split_paragraphs_and_items(self):
        text = ("Lead-in with:\n\n- one;\n- two.\n\nNext paragraph.\n\n"
                "1. Step one.\n   - nested.\n2. Step two.\n\n## Head\n\n```\nx\ny\n```\n")
        self.assertEqual(units(text), ["lead-in with: - one; - two.", "next paragraph.",
                                       "1. step one. - nested.", "2. step two.", "## head",
                                       "x y"])


class OpenStepGateTest(_RealSkillCase):
    """Negative gate 1 (§S2, AC): no ``chrome-devtools-axi open`` shown as a step — a code span
    or a fenced line, outside a prohibition clause."""

    def test_the_skill_shows_no_open_step(self):
        self.assertEqual(shown_form_findings(self.real_text(), OPEN_STEP), [])

    def test_detector_spares_the_conforming_sample_and_its_governed_open(self):
        self.assertEqual(shown_form_findings(CONFORMING_SAMPLE, OPEN_STEP), [])
        self.assertIn("never run `npx -y chrome-devtools-axi open <dev-url>`", CONFORMING_SAMPLE)

    def test_detector_bites_on_a_fenced_open_line(self):
        text = "Navigate:\n\n```bash\nnpx -y chrome-devtools-axi open <dev-url>\n```\n"
        self.assertEqual(shown_form_findings(text, OPEN_STEP),
                         [(4, "npx -y chrome-devtools-axi open <dev-url>")])

    def test_detector_bites_on_an_ungoverned_span_a_prohibition_governs_only_its_clause(self):
        text = "Do not stop: run `npx -y chrome-devtools-axi  open <dev-url>`.\n"
        self.assertEqual(len(shown_form_findings(text, OPEN_STEP)), 1)
        self.assertEqual(len(shown_form_findings(
            "Then run `chrome-devtools-axi open <dev-url>`.\n", OPEN_STEP)), 1)

    def test_detector_spares_other_verbs_and_prose_mentions(self):
        for good in ("Run `npx -y chrome-devtools-axi newpage <dev-url>`.\n",
                     "The tool's chrome-devtools-axi open verb navigates the selected tab.\n",
                     "It never uses `chrome-devtools-axi open`.\n",
                     "```\n# never run npx -y chrome-devtools-axi open <dev-url>\n```\n"):
            with self.subTest(good=good):
                self.assertEqual(shown_form_findings(good, OPEN_STEP), [])


class PipedOutputGateTest(_RealSkillCase):
    """Negative gate 2 (§S7, AC): no ``chrome-devtools-axi`` output shown piped through grep,
    head, tail or ``jq``, or redirected away."""

    def test_the_skill_shows_no_piped_or_redirected_output(self):
        self.assertEqual(shown_form_findings(self.real_text(), PIPED_OUTPUT), [])

    def test_detector_spares_the_conforming_sample(self):
        self.assertEqual(shown_form_findings(CONFORMING_SAMPLE, PIPED_OUTPUT), [])

    def test_detector_bites_on_pipes_and_redirects(self):
        for bad in ("```\nnpx -y chrome-devtools-axi pages | grep about\n```\n",
                    "Run `npx -y chrome-devtools-axi pages | head -20`.\n",
                    "Run `npx -y chrome-devtools-axi pages | tail -5`.\n",
                    "Run `npx -y chrome-devtools-axi pages | jq .`.\n",
                    "Run `npx -y chrome-devtools-axi snapshot > /tmp/snap.txt`.\n",
                    "Run `npx -y chrome-devtools-axi pages >>log`.\n",
                    "Run `npx -y chrome-devtools-axi pages 2>/dev/null`.\n",
                    "Run `npx -y chrome-devtools-axi pages &> /dev/null`.\n"):
            with self.subTest(bad=bad):
                self.assertEqual(len(shown_form_findings(bad, PIPED_OUTPUT)), 1)

    def test_detector_spares_kept_output_and_governed_examples(self):
        for good in ("Run `npx -y chrome-devtools-axi pages 2>&1`.\n",
                     "Run `npx -y chrome-devtools-axi newpage <dev-url>`.\n",
                     "It is never piped: never `npx -y chrome-devtools-axi pages | grep x`.\n",
                     "Read `grep x file | wc -l` elsewhere.\n"):
            with self.subTest(good=good):
                self.assertEqual(shown_form_findings(good, PIPED_OUTPUT), [])


if __name__ == "__main__":
    unittest.main()
