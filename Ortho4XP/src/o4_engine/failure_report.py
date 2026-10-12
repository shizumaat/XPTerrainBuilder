"""The failure report a user sends us: redacted text, file and issue link.

Issue #565, owner RULINGS 2026-10-12b (completes 12a (3) "report it"): when
a tile is not built, or is built with an airport left without a patch, a
front end offers "Report this problem" (the user reads the report, then a
prefilled new-issue page opens in the browser) and "Save report file" (the
same report as a file to send by e-mail or on a forum).  There is no
server and no token: the user's own browser files the issue.

One report, three renderings, all from :func:`build_report`:

* ``text`` — the whole report: what failed, versions, provenance, and the
  tail of the engine log for that tile.  :func:`write_report_file` saves
  exactly this.
* ``issue_body`` / ``issue_url`` — the summary and a short excerpt, fitted
  under the URL length GitHub accepts (:data:`MAX_ISSUE_URL`,
  :data:`MAX_LOGIN_REDIRECT`), with a request to attach the saved file.
* ``title`` — failure code, airports, tile, engine version: the same
  failure on the same airport files under a title a search finds.

EVERYTHING passes :class:`o4_engine.redaction.Redactor` before it is
returned; nothing here writes or returns unredacted log text.

:func:`failure_report` is the engine command (``{"cmd": "failure_report",
...}``, registered in :mod:`o4_engine.jsonl`): it adds what only the engine
knows — its version, the protocol, the data root — and reads the log.
``tools/failure_report.py`` is the same thing from a shell.

A failure is plain data, never an import: ``{"code", "what", "why",
"remedy", "airports", "detail"}`` — the entries of ``BuildDone.failures``
and ``BuildDone.warnings`` (issue #562) can be passed back unchanged.
"""

from __future__ import annotations

import os
import platform
import re
import sys
import time
from dataclasses import dataclass
from typing import Callable, Iterable, List, Mapping, Optional, Sequence
from urllib.parse import quote

import O4_File_Names as FNAMES
import O4_Version

from . import events
from .redaction import KEPT, RULES, Redactor

__all__ = [
    "ISSUES_NEW_URL", "MAX_ISSUE_URL", "MAX_LOGIN_REDIRECT",
    "LOG_FILE_LINES", "FailureReport", "LogExcerpt", "tile_name",
    "log_excerpt", "failures_from_log", "build_report", "issue_url",
    "login_redirect_length", "write_report_file", "failure_report",
]

ISSUES_NEW_URL = "https://github.com/shizumaat/XPTerrainBuilder/issues/new"

# MEASURED against github.com on 2026-10-12 (signed out, curl, filler
# bodies; docs/briefs/report565-notes.md has the table):
# * a URL of 7,021 characters is accepted, 7,041 answers HTTP 500, and
#   8,281 answers HTTP 414;
# * a signed-out user is sent to the sign-in page with the whole URL
#   percent-encoded AGAIN in ``return_to``; that second URL is kept at
#   7,642 characters and silently DROPPED at 7,892 — the user signs in and
#   lands on an empty form.
# Both are enforced, with margin.
MAX_ISSUE_URL = 6800
MAX_LOGIN_REDIRECT = 7500
_LOGIN_PREFIX = "https://github.com/login?return_to="
# Characters a URL query may carry as they are (RFC 3986 "query" minus the
# ones a form decoder reads as structure).
_QUERY_SAFE = "/:,()!*"

LOG_FILE_LINES = 400       # tail of the tile's log kept in the report file
_LOG_READ_BYTES = 8 * 1024 * 1024
_ISSUE_TAIL_LINES = 30     # before fitting; the fit only ever removes
_ISSUE_ERROR_LINES = 8
_ISSUE_LINE_CHARS = 240
_ISSUE_DETAIL_CHARS = 700

_HEADER = re.compile(r"^=== ")
_RUN_VERSIONS = re.compile(r"app (\S+) \| engine (\S+)")
_RUN_STAMP = re.compile(r"=== [a-z ]+? (\d{4}-\d\d-\d\dT[\d:]+Z) ===")
_RULE_LINE = re.compile(r"^[\s\-_=*]*$")
_PROGRESS = re.compile(r"\[\d+/\d+\]|^\s*\.\.\.still ")
_SALIENT = re.compile(r"ERROR|FAILED|ABORTED|Traceback|Exception|Error:|"
                      r"refus", re.IGNORECASE)
_FAILED_AIRPORT = re.compile(r"Auto-patch: FAILED (\S+) \(([^)]*)\): (.*)")


@dataclass(frozen=True)
class LogExcerpt:
    """The part of an engine log that belongs to one tile's LAST run."""

    header: str               # the run header the lines stand under
    lines: List[str]          # the tile's lines, prefix removed
    provenance: List[str]     # its ``[provenance]`` lines, each once
    total: int                # how many lines the tile had in that run


@dataclass(frozen=True)
class FailureReport:
    """A redacted report in its three renderings."""

    title: str
    text: str
    issue_body: str
    issue_url: str
    file_name: str


def tile_name(lat: int, lon: int) -> str:
    """``+45-123``: the name the log, the files and the issues use."""
    return FNAMES.short_latlon(lat, lon)


# ---------------------------------------------------------------------------
# The log
# ---------------------------------------------------------------------------
def log_excerpt(lines: Iterable[str], tile: str) -> LogExcerpt:
    """Read one tile's last run out of an engine stderr log.

    The log interleaves tiles, each line prefixed ``[+LAT+LON]``, under
    ``=== engine run ... ===`` / ``=== queued into this run ... ===``
    headers that list the tiles they start.  The tile's last run begins at
    the last header naming it; only ITS prefixed lines are read, so another
    tile's text never enters the report.
    """
    lines = [line.rstrip("\r\n") for line in lines]
    start = 0
    for index, line in enumerate(lines):
        if _HEADER.match(line) and tile in line:
            start = index
    run = ""
    for line in lines[:start + 1]:
        if _HEADER.match(line) and _RUN_VERSIONS.search(line):
            run = line
    header = lines[start] if lines and _HEADER.match(lines[start]) else ""
    if run and run != header:
        header = run + ("\n" + header if header else "")
    prefix = "[%s]" % tile
    own = [line[len(prefix):].rstrip() for line in lines[start:]
           if line.startswith(prefix)]
    own = [line[1:] if line.startswith(" ") else line for line in own]
    own = [line for line in own if not _RULE_LINE.match(line)]
    provenance: List[str] = []
    for line in own:
        if "[provenance]" in line and line.strip() not in provenance:
            provenance.append(line.strip())
    return LogExcerpt(header=header, lines=own, provenance=provenance,
                      total=len(own))


def failures_from_log(excerpt: LogExcerpt) -> List[dict]:
    """Failures read from the log's own words, for a caller that has no
    failure record (the shell tool run on an old log).  The code is
    ``unclassified``: the catalogue (#562) names failures, not this text.
    """
    by_detail: dict = {}
    for line in excerpt.lines:
        match = _FAILED_AIRPORT.search(line)
        if match is None:
            continue
        ident, stage, detail = match.groups()
        # The detail names its own airport; without the name, six airports
        # refused for one reason are one failure.
        common = re.sub(r"\b%s\b:?\s*" % re.escape(ident), "", detail).strip()
        entry = by_detail.setdefault((stage, common), {
            "code": "unclassified", "what": "", "why": "", "remedy": "",
            "airports": [], "detail": "stage %s: %s" % (stage, detail)})
        if ident not in entry["airports"]:
            entry["airports"].append(ident)
    if by_detail:
        return list(by_detail.values())
    salient = [line.strip() for line in excerpt.lines if "ERROR" in line]
    if salient:
        return [{"code": "unclassified", "what": "", "why": "", "remedy": "",
                 "airports": [], "detail": salient[-1]}]
    return []


# ---------------------------------------------------------------------------
# The issue link
# ---------------------------------------------------------------------------
def issue_url(title: str, body: str) -> str:
    """The prefilled new-issue URL (not length-checked: see
    :func:`build_report`, which fits the body)."""
    def encode(text: str) -> str:
        return quote(text, safe=_QUERY_SAFE).replace("%20", "+")
    return "%s?title=%s&labels=bug&body=%s" % (
        ISSUES_NEW_URL, encode(title), encode(body))


def login_redirect_length(url: str) -> int:
    """Length of the sign-in URL GitHub sends a signed-out user to."""
    return len(_LOGIN_PREFIX) + len(quote(url, safe="-._~"))


def _fits(url: str) -> bool:
    return (len(url) <= MAX_ISSUE_URL
            and login_redirect_length(url) <= MAX_LOGIN_REDIRECT)


def _clip(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------
def _normalise(failures: Optional[Sequence[Mapping]]) -> List[dict]:
    out = []
    for failure in failures or ():
        airports = failure.get("airports") or []
        if isinstance(airports, str):
            airports = [airports]
        out.append({
            "code": str(failure.get("code") or "unclassified"),
            "message": " ".join(
                str(failure.get(k) or "").strip() for k in ("what", "why")
            ).strip(),
            "remedy": str(failure.get("remedy") or "").strip(),
            "airports": [str(a) for a in airports],
            "detail": str(failure.get("detail") or "").strip(),
        })
    return out


def _listed(items: Sequence[str], limit: int) -> str:
    items = list(items)
    if len(items) <= limit:
        return ", ".join(items)
    return "%s +%d more" % (", ".join(items[:limit]), len(items) - limit)


def _title(failures: List[dict], airports: List[str], tile: str,
           engine_version: str) -> str:
    codes: List[str] = []
    for failure in failures:
        if failure["code"] not in codes:
            codes.append(failure["code"])
    parts = ["[%s]" % _listed(codes or ["unclassified"], 2)]
    if airports:
        parts.append(_listed(airports, 4))
    parts.append("tile %s" % tile)
    return "%s (engine %s)" % (" ".join(parts), engine_version or "unknown")


def _privacy_lines() -> List[str]:
    return ["Redacted on the user's machine before anything was sent:"] + [
        "  - " + rule for rule in RULES] + [
        "Kept on purpose, because they are the diagnosis: %s." % KEPT,
        "The issue tracker is public. Read the report before you send it."]


def _facts(tile: str, airports: List[str], engine_version: str,
           frozen: Optional[bool], protocol: str, app_version: str,
           app_name: str, os_text: str, generated: str) -> List[str]:
    kind = {True: "packaged", False: "source"}.get(frozen, "unknown")
    app = " ".join(p for p in (app_name, app_version) if p) or "unknown"
    return [
        "Tile: %s" % tile,
        "Airports without a patch: %s" % (", ".join(airports) or "none named"),
        "Engine: %s (%s), protocol %s" % (engine_version or "unknown", kind,
                                         protocol or "unknown"),
        "App: %s" % app,
        "System: %s" % (os_text or "unknown"),
        "Generated: %s" % generated,
    ]


def _failure_lines(failures: List[dict], detail_chars: int) -> List[str]:
    out: List[str] = []
    for number, failure in enumerate(failures, 1):
        out.append("Failure %d: [%s] %s" % (
            number, failure["code"], failure["message"] or "(no message)"))
        if failure["airports"]:
            out.append("  Airports: %s" % ", ".join(failure["airports"]))
        if failure["remedy"]:
            out.append("  Suggested to the user: %s" % failure["remedy"])
        if failure["detail"]:
            out.append("  Detail: %s" % _clip(failure["detail"], detail_chars))
    return out or ["Failure: none recorded (see the log excerpt)"]


def _issue_excerpt(lines: List[str]) -> tuple:
    """The lines an issue shows, as ``(errors, tail)``: the last lines that
    name an error, each once, and the end of the log without its progress
    ticks and provenance (the report file has those)."""
    quiet = [line.strip() for line in lines
             if not _PROGRESS.search(line) and "[provenance]" not in line]
    errors: List[str] = []
    for line in quiet:
        if _SALIENT.search(line) and line not in errors:
            errors.append(line)
    errors = errors[-_ISSUE_ERROR_LINES:]
    tail = [line for line in quiet[-_ISSUE_TAIL_LINES:] if line not in errors]
    return ([_clip(line, _ISSUE_LINE_CHARS) for line in errors],
            [_clip(line, _ISSUE_LINE_CHARS) for line in tail])


def _issue_body(facts: List[str], failures: List[str], excerpt: List[str],
                shown_of: int, file_name: str) -> str:
    fence = "```"
    parts = ["**What failed**", fence, *failures, fence, "",
             "**Where**", *["- " + fact for fact in facts], ""]
    if excerpt:
        parts += ["**Log excerpt** (%d of %d lines for this tile)"
                  % (len(excerpt), shown_of), fence, *excerpt, fence, ""]
    parts += [
        "**Please attach the report file** `%s` (\"Save report file\" in "
        "the app): it holds the longer log excerpt." % file_name, "",
        "_Redacted on the user's machine: home folder, user name, paths "
        "outside the scenery and data folders, proxies, credentials, "
        "e-mail addresses. Kept: %s._" % KEPT,
    ]
    return "\n".join(parts)


def build_report(*, tile: str, failures: Optional[Sequence[Mapping]] = None,
                 airports: Optional[Sequence[str]] = None,
                 engine_version: str = "", protocol: str = "",
                 frozen: Optional[bool] = None, app_version: str = "",
                 app_name: str = "", os_text: str = "",
                 log_lines: Iterable[str] = (), generated: str = "",
                 redactor: Optional[Redactor] = None) -> FailureReport:
    """Build the redacted report for one tile.

    ``failures`` are plain dicts (module docstring); with none given they
    are read from the log.  ``airports`` are the airports without a patch;
    by default, the ones the failures name.  ``log_lines`` is the engine
    stderr log (any iterable of lines).  Versions left empty are read from
    the log's run header where it has them.
    """
    redactor = redactor or Redactor.for_this_machine()
    clean: Callable[[str], str] = redactor.text
    raw = log_excerpt(log_lines, tile)
    entries = _normalise(failures) or _normalise(failures_from_log(raw))
    named: List[str] = [str(a) for a in airports or ()]
    for entry in entries:
        named += [a for a in entry["airports"] if a not in named]

    # REDACTION, at the door: everything that came from outside is cleaned
    # here, before any of it is cut to length (a path cut in half is no
    # longer recognisably a path).  The first call only learns the user
    # names, so a name one line reveals is removed from all of them.
    redactor.lines([raw.header, *raw.lines]
                   + [entry[key] for entry in entries
                      for key in ("message", "remedy", "detail")])
    excerpt = LogExcerpt(header=clean(raw.header),
                         lines=redactor.lines(raw.lines),
                         provenance=redactor.lines(raw.provenance),
                         total=raw.total)
    entries = [{key: redactor.lines(value) if isinstance(value, list)
                else clean(value) for key, value in entry.items()}
               for entry in entries]
    named = redactor.lines(named)

    versions = _RUN_VERSIONS.search(excerpt.header)
    if versions:
        app_version = app_version or versions.group(1)
        engine_version = engine_version or versions.group(2)
    stamp = _RUN_STAMP.search(excerpt.header)
    generated = generated or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    file_name = "XPTerrainBuilder-report-%s-%s.txt" % (
        tile, re.sub(r"[^0-9TZ]", "", generated))

    def facts(airports_shown: List[str]) -> List[str]:
        return redactor.lines(_facts(
            tile, airports_shown, engine_version, frozen, protocol,
            app_version, app_name, os_text, generated))

    tail = excerpt.lines[-LOG_FILE_LINES:]
    text = clean("\n".join(
        ["XPTerrainBuilder failure report (format 1)", ""]
        + _privacy_lines() + ["", "== Summary =="] + facts(named)
        + ["", "== What failed =="] + _failure_lines(entries, 100000)
        + ["", "== Provenance (patches this run wrote) =="]
        + (excerpt.provenance or ["(none in the log)"])
        + ["", "== Engine log for tile %s: last %d of %d lines%s =="
           % (tile, len(tail), excerpt.total,
              (", run of " + stamp.group(1)) if stamp else "")]
        + ([h for h in excerpt.header.split("\n") if h])
        + (tail or ["(the log holds no lines for this tile)"]) + [""]))

    title = clean(_title(entries, named, tile, engine_version))
    issue_facts = facts([_listed(named, 12)] if named else [])
    issue_failures = _failure_lines(entries, _ISSUE_DETAIL_CHARS)
    errors, tail = _issue_excerpt(excerpt.lines)
    detail_chars = _ISSUE_DETAIL_CHARS
    while True:
        body = clean(_issue_body(issue_facts, issue_failures, errors + tail,
                                 excerpt.total, file_name))
        url = issue_url(title, body)
        if _fits(url):
            break
        if tail:
            tail.pop(0)         # oldest first: the end of the log says most
        elif errors:
            errors.pop(0)
        elif detail_chars > 80:
            detail_chars //= 2
            issue_failures = [_clip(line, detail_chars)
                              for line in issue_failures]
        elif len(issue_failures) > 1:
            issue_failures.pop()
        else:
            title = _clip(title, max(20, len(title) // 2))
    return FailureReport(title=title, text=text, issue_body=body,
                         issue_url=url, file_name=file_name)


def write_report_file(report: FailureReport, path: str) -> str:
    """Save the report text (UTF-8, LF).  ``path`` may be a folder: the
    report's own file name is used inside it.  Returns the path written."""
    if os.path.isdir(path):
        path = os.path.join(path, report.file_name)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(report.text)
    return path


# ---------------------------------------------------------------------------
# The engine command
# ---------------------------------------------------------------------------
def _read_log(path: str) -> List[str]:
    """The end of a log file, as lines; an unreadable log is an empty one
    (the report still carries the failure the caller passed)."""
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - _LOG_READ_BYTES))
            data = handle.read()
    except OSError:
        return []
    return data.decode("utf-8", errors="replace").splitlines()


def _default_log_path() -> str:
    return FNAMES.data_path(os.path.join("logs", "engine-stderr.log"))


def failure_report(lat: Optional[int] = None, lon: Optional[int] = None,
                   failures: Optional[Sequence[Mapping]] = None,
                   airports: Optional[Sequence[str]] = None,
                   app_version: str = "", app_name: str = "",
                   log_path: str = "", xplane_dir: str = "",
                   save_path: str = "", tile: str = "") -> dict:
    """ENGINE COMMAND ``failure_report``: one tile's redacted report.

    A front end calls it when the user presses "Report this problem" (show
    ``report``, then open ``issue_url``) and again with ``save_path`` for
    "Save report file".  Synchronous: it reads the end of one log file.

    Args:
        lat, lon: The tile (or ``tile`` as ``"+45-123"``).
        failures: ``BuildDone.failures`` / ``warnings`` entries, unchanged.
        airports: Airports without a patch (default: the failures' own).
        app_version, app_name: The front end ("mac", "qt") and its version.
        log_path: The engine stderr log the front end writes; empty means
            ``<data root>/logs/engine-stderr.log``.
        xplane_dir: The X-Plane folder, kept as ``<xplane>`` in paths.
        save_path: A file or folder to write the report to; empty writes
            nothing.

    Returns:
        ``{"title", "report", "issue_url", "issue_body", "file_name",
        "saved_path", "url_length"}`` — all redacted but ``saved_path``,
        which is the local path just written and goes nowhere.
    """
    if not tile:
        if lat is None or lon is None:
            raise ValueError("failure_report needs a tile: lat and lon")
        tile = tile_name(int(lat), int(lon))
    roots = {"data": [FNAMES.current_data_root()],
             "engine": [FNAMES.resource_path("")],
             "xplane": [xplane_dir]}
    for paths in roots.values():
        paths += [os.path.realpath(p) for p in paths if p]
    report = build_report(
        tile=tile, failures=failures, airports=airports,
        engine_version=O4_Version.version,
        protocol=events.PROTOCOL_VERSION,
        frozen=bool(getattr(sys, "frozen", False)),
        app_version=app_version, app_name=app_name,
        os_text=platform.platform(),
        log_lines=_read_log(log_path or _default_log_path()),
        redactor=Redactor.for_this_machine(roots))
    saved = write_report_file(report, save_path) if save_path else ""
    return {"title": report.title, "report": report.text,
            "issue_url": report.issue_url, "issue_body": report.issue_body,
            "file_name": report.file_name, "saved_path": saved,
            "url_length": len(report.issue_url)}
