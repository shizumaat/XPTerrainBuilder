"""Twins for :mod:`o4_engine.failure_report` (issue #565, RULINGS
2026-10-12b): the report is redacted in every rendering, the issue URL
stays under the lengths GitHub was measured to accept, the file is UTF-8 /
LF, and the engine command answers in JSON.  No network."""
from __future__ import annotations

import json
import os
import sys
from unittest import mock
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

from o4_engine import failure_report as FR  # noqa: E402
from o4_engine import jsonl  # noqa: E402
from o4_engine.redaction import Redactor  # noqa: E402

PACK = "c_USA - 100_airport - KAAA (Some Studio)"
HOMES = {
    "mac": "/Users/zelda",
    "windows": r"C:\Users\zelda",
    "linux": "/home/zelda",
}


def _log(home: str, sep: str = "/") -> list:
    """An engine stderr log: two tiles interleaved, the first built twice."""
    def path(*parts: str) -> str:
        return home + "".join(sep + p for p in parts)
    apt = path("X-Plane 12", "Custom Scenery", PACK, "Earth nav data",
               "apt.dat")
    return [
        "=== engine run 2026-10-12T01:43:38Z === app 1.0.387 | engine "
        "1.50.1834 | 2 tiles: +45-123 +47-123",
        "[+45-123] FIRST ATTEMPT marker",
        "[+47-123] OTHER TILE marker " + path("Secret Other", "o.txt"),
        "[+45-123]    Auto-patch: FAILED KAAA (build): old failure",
        "=== queued into this run 2026-10-12T01:47:34Z === 1 tile: +45-123",
        "[+45-123] ",
        "[+45-123] Step 1 : Building vector data for tile +45-123 : ",
        "[+45-123] --------",
        "[+45-123]     * Recycling OSM data from " + path(
            "XPData", "OSM_data", "+40-130", "+45-123", "a.osm.bz2"),
        "[+45-123]   [pav-builder] KAAA: apt.dat " + apt,
        "[+47-123] OTHER TILE again",
        "[+45-123]    KAAA   Alpha Field      3 runways, lat= 45.58, "
        "lon= -122.60",
        "[+45-123]    Auto-patch: KBBB [69/100] Solving the surface",
        "[+45-123]   [provenance] KBBB patch: engine=v2 version=1.50.1834 "
        "code=312205fa412410f7 dem=production[N45W123]",
        "[+45-123]   [provenance] KBBB patch: engine=v2 version=1.50.1834 "
        "code=312205fa412410f7 dem=production[N45W123]",
        "[+45-123]   settings read from " + path("Documents", "Tax 2026",
                                                 "o4.cfg")
        + " via proxy http://bob:hunter2@proxy.corp.example:8080",
        "[+45-123]   mail zelda@mail.example on failure",
        "[+45-123]    Auto-patch: FAILED KAAA (build): [v2] KAAA: "
        "TopologyException: Ring edge missing at -185.72 80.68",
        "[+45-123]    Auto-patch: FAILED KCCC (build): [v2] KCCC: "
        "TopologyException: Ring edge missing at -185.72 80.68",
        "[+45-123] ERROR: auto-patch FAILED for 2 airport(s)",
        "[worker 0] Engine process exiting (standard input closed).",
    ]


def _build(log, **kwargs):
    kwargs.setdefault("redactor", Redactor())
    kwargs.setdefault("generated", "2026-10-12T02:00:00Z")
    return FR.build_report(tile="+45-123", log_lines=log, **kwargs)


def test_log_excerpt_is_the_tiles_last_run_only():
    excerpt = FR.log_excerpt(_log("/Users/zelda"), "+45-123")
    text = "\n".join(excerpt.lines)
    assert "FIRST ATTEMPT" not in text and "old failure" not in text
    assert "OTHER TILE" not in text and "worker 0" not in text
    assert excerpt.lines[0].startswith("Step 1")       # blank + rule dropped
    assert len(excerpt.provenance) == 1                 # each once
    assert "app 1.0.387" in excerpt.header
    assert "queued into this run" in excerpt.header
    assert excerpt.total == len(excerpt.lines)


def test_failures_are_read_from_the_log_when_none_are_given():
    excerpt = FR.log_excerpt(_log("/Users/zelda"), "+45-123")
    failures = FR.failures_from_log(excerpt)
    assert len(failures) == 1                 # one cause, two airports
    assert failures[0]["airports"] == ["KAAA", "KCCC"]
    assert failures[0]["code"] == "unclassified"
    assert "TopologyException" in failures[0]["detail"]


@pytest.mark.parametrize("style", sorted(HOMES))
def test_no_rendering_carries_a_planted_secret(style):
    sep = "\\" if style == "windows" else "/"
    report = _build(_log(HOMES[style], sep), failures=[{
        "code": "airport_geometry", "what": "Tile +45-123 was built, but "
        "KAAA has no patch.", "why": "Its outline could not be closed.",
        "remedy": "Report it and attach the log (%s)." % (
            HOMES[style] + sep + "Library" + sep + "engine-stderr.log"),
        "airports": ["KAAA"],
        "detail": "read %s" % (HOMES[style] + sep + "Tax 2026" + sep + "x.py"),
    }], app_name="mac", os_text="TestOS 1 (arm64)", protocol="1.10",
        frozen=True)
    body = parse_qs(urlsplit(report.issue_url).query)["body"][0]
    assert body == report.issue_body
    for rendering in (report.text, report.title, report.issue_body, body,
                      report.file_name):
        low = rendering.lower()
        for secret in ("zelda", "tax 2026", "hunter2", "bob:", "corp.example",
                       "mail.example", "secret other"):
            assert secret not in low, (secret, rendering)
    # What the diagnosis needs is there, in the file and in the issue.
    assert PACK in report.text and "lat= 45.58, lon= -122.60" in report.text
    assert "<data>" in report.text and "<xplane>" in report.text
    for rendering in (report.text, report.issue_body):
        assert "[airport_geometry]" in rendering
        assert "Engine: 1.50.1834 (packaged), protocol 1.10" in rendering
        assert "App: mac 1.0.387" in rendering          # from the run header
        assert "Airports without a patch: KAAA" in rendering
    assert "Kept on purpose" in report.text and "public" in report.text
    assert "[provenance] KBBB" in report.text
    assert "[69/100]" in report.text and "[69/100]" not in report.issue_body


def test_title_names_code_airports_tile_and_engine():
    report = _build(_log("/Users/zelda"), failures=[
        {"code": "dsf_dump_stale", "airports": ["KAAA", "KBBB", "KCCC",
                                                 "KDDD", "KEEE"]}])
    assert report.title == ("[dsf_dump_stale] KAAA, KBBB, KCCC, KDDD +1 more "
                            "tile +45-123 (engine 1.50.1834)")
    query = parse_qs(urlsplit(report.issue_url).query)
    assert query["title"] == [report.title] and query["labels"] == ["bug"]
    assert report.issue_url.startswith(FR.ISSUES_NEW_URL + "?title=")
    assert report.file_name == \
        "XPTerrainBuilder-report-+45-123-20261012T020000Z.txt"


def test_issue_url_stays_under_the_measured_caps_whatever_the_log():
    noisy = ["[+45-123] ERROR %d: " % i + "ä/ö +%&#? " * 60
             for i in range(3000)]
    failures = [{"code": "c%d" % i, "what": "w" * 500, "detail": "d% " * 4000,
                 "airports": ["A%03d" % j for j in range(80)]}
                for i in range(6)]
    report = _build(noisy, failures=failures)
    assert len(report.issue_url) <= FR.MAX_ISSUE_URL
    assert FR.login_redirect_length(report.issue_url) <= FR.MAX_LOGIN_REDIRECT
    assert "attach the report file" in report.issue_body
    assert report.file_name in report.issue_body
    # The file is bounded too: the tail, not the log.
    assert report.text.count("\nERROR ") == FR.LOG_FILE_LINES
    # An ordinary report keeps an excerpt and still fits.
    plain = _build(_log("/Users/zelda"))
    assert "**Log excerpt**" in plain.issue_body
    assert "ERROR: auto-patch FAILED" in plain.issue_body
    assert len(plain.issue_url) <= FR.MAX_ISSUE_URL


def test_the_caps_are_the_measured_ones_and_the_redirect_model_is_githubs():
    # github.com, 2026-10-12, signed out: 7,021 accepted, 7,041 -> HTTP 500;
    # sign-in redirect kept at 7,642, dropped at 7,892.
    assert FR.MAX_ISSUE_URL < 7021 and FR.MAX_LOGIN_REDIRECT < 7642
    url = FR.issue_url("[x] KAAA tile +45-123 (engine 1.50)",
                       "**What failed**\n```\nFailure 1: a,b/c!\n```")
    assert url == (
        "https://github.com/shizumaat/XPTerrainBuilder/issues/new?title="
        "%5Bx%5D+KAAA+tile+%2B45-123+(engine+1.50)&labels=bug&body="
        "**What+failed**%0A%60%60%60%0AFailure+1:+a,b/c!%0A%60%60%60")
    # What github.com answered for that URL (Location header, verbatim).
    location = (
        "https://github.com/login?return_to=https%3A%2F%2Fgithub.com%2F"
        "shizumaat%2FXPTerrainBuilder%2Fissues%2Fnew%3Ftitle%3D%255Bx%255D"
        "%2BKAAA%2Btile%2B%252B45-123%2B%28engine%2B1.50%29%26labels%3Dbug"
        "%26body%3D%2A%2AWhat%2Bfailed%2A%2A%250A%2560%2560%2560%250A"
        "Failure%2B1%3A%2Ba%2Cb%2Fc%21%250A%2560%2560%2560")
    assert FR.login_redirect_length(url) == len(location)


def test_report_file_is_utf8_lf(tmp_path):
    report = _build(_log("/Users/zelda") + ["[+45-123] Suárez — 47,029 m²"])
    written = FR.write_report_file(report, str(tmp_path))
    assert os.path.basename(written) == report.file_name
    data = (tmp_path / report.file_name).read_bytes()
    assert b"\r" not in data
    assert data.decode("utf-8") == report.text
    assert "Suárez — 47,029 m²" in report.text
    named = FR.write_report_file(report, str(tmp_path / "mine.txt"))
    assert named.endswith("mine.txt")


def test_engine_command_answers_in_json_and_saves(tmp_path, monkeypatch):
    home = str(tmp_path / "home" / "zelda")
    monkeypatch.setenv("HOME", home)
    monkeypatch.setenv("USERPROFILE", home)
    log = tmp_path / "engine-stderr.log"
    log.write_text("\n".join(_log(home, os.sep)) + "\n", encoding="utf-8",
                   newline="\n")
    handler = jsonl._build_handlers(mock.MagicMock())["failure_report"]
    result = handler(lat=45, lon=-123, app_name="qt", log_path=str(log),
                     failures=[{"code": "airport_geometry",
                                "airports": ["KAAA"]}],
                     save_path=str(tmp_path))
    assert json.loads(json.dumps(result)) == result
    assert set(result) == {"title", "report", "issue_url", "issue_body",
                           "file_name", "saved_path", "url_length"}
    assert result["title"].startswith("[airport_geometry] KAAA tile +45-123")
    assert "zelda" not in (result["report"] + result["issue_url"]).lower()
    assert "App: qt 1.0.387" in result["report"]
    with open(result["saved_path"], encoding="utf-8", newline="") as handle:
        assert handle.read() == result["report"]
    assert result["url_length"] == len(result["issue_url"])
    with pytest.raises(ValueError):
        handler()


def test_a_missing_log_still_reports_the_failure(tmp_path):
    result = FR.failure_report(tile="+10+020", log_path=str(tmp_path / "no"),
                               failures=[{"code": "disk_full",
                                          "what": "The disk is full."}])
    assert "[disk_full] The disk is full." in result["report"]
    assert "holds no lines for this tile" in result["report"]
    assert result["title"].startswith("[disk_full] tile +10+020")
