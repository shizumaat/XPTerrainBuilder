"""Per-tile build logs and the build record (#1226, owner Q139).

The rules (``O4_Tile_Build_Log``): a tile's newest 3 build logs are kept
in its build folder beside ``build_record.json`` (start, end, outcome,
duration, warnings, log name, builder); every line a tile's build writes
reaches its log — in-process through the stream tag, in a parallel run
through the orchestrator — and carries the ``[+47-123] `` console prefix
a front end filters by.  The record schema is read by the Mac app's twin
(``Sources/SceneryKit/TileBuildRecord.swift``) from the fixture
``tests/fixtures/build_record_v1.json``.
"""

import io
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Tile_Build_Log as TILELOG  # noqa: E402
import O4_Tile_Info as TINFO  # noqa: E402
import pytest  # noqa: E402
from o4_engine import events as EV  # noqa: E402
from o4_engine.session import EngineSession  # noqa: E402
from test_engine_parallel import (  # noqa: E402
    Collector,
    _start_parallel,
    reset_ui_routing,
    stub_worker,
)
from test_engine_session import install_stub_pipeline  # noqa: E402

__all__ = ["reset_ui_routing", "stub_worker"]   # fixtures, used by name

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "fixtures", "build_record_v1.json")
WHO = {"tool": "XPTerrainBuilder", "app_version": "1.0.999",
       "engine_version": "1.50.9"}


def _run_in_process(session, tiles, build_dir):
    collector = Collector(session)
    assert session.build(tiles, "BI", 16, build_dir, slots=1) is True
    collector.wait_run_done(30.0)
    return collector.events


def _logs(build_dir):
    folder = TILELOG.build_logs_dir(build_dir)
    return sorted(n for n in os.listdir(folder) if n.endswith(".log"))


def test_retention_keeps_the_newest_three_builds_per_tile(tmp_path,
                                                          monkeypatch):
    clock = iter(range(1_000_000, 1_000_000 + 1000, 10))
    monkeypatch.setattr(TILELOG.time, "time", lambda: float(next(clock)))
    logs = TILELOG.TileBuildLogs(who=WHO)
    for build in range(5):
        logs.begin((47, -123), str(tmp_path))
        logs.line((47, -123), "build %d" % build)
        logs.finish((47, -123), "ok")
    # A second tile in the same (grouped) folder keeps its own three.
    logs.begin((48, -123), str(tmp_path))
    logs.finish((48, -123), "failed")

    rows = TILELOG.read_records(str(tmp_path), 47, -123)
    assert len(rows) == 3
    assert [TILELOG.read_log(str(tmp_path), r["log"]).strip()
            for r in rows] == ["build 4", "build 3", "build 2"]
    assert len([n for n in _logs(tmp_path) if "+47-123" in n]) == 3
    assert TILELOG.last_build(str(tmp_path), 48, -123)["outcome"] == "failed"


def test_record_row_schema_round_trip(tmp_path):
    logs = TILELOG.TileBuildLogs(who=WHO)
    logs.begin((47, -123), str(tmp_path))
    logs.finish((47, -123), "warnings", warnings=2, closing=["closing"])
    row = TILELOG.last_build(str(tmp_path), 47, -123)
    with open(FIXTURE, encoding="utf-8") as handle:
        fixture = json.load(handle)
    # Same keys and value types as the fixture the Swift twin decodes.
    sample = fixture["builds"][0]
    assert set(row) == set(sample)
    for key, value in sample.items():
        assert isinstance(row[key], type(value)) or (
            isinstance(value, float) and isinstance(row[key], (int, float)))
    assert row["outcome"] == "warnings" and row["warnings"] == 2
    assert row["builder"] == WHO
    assert row["end"] >= row["start"]
    assert TILELOG.read_log(str(tmp_path), row["log"]) == "closing\n"
    # The record file itself carries the schema version.
    with open(os.path.join(TILELOG.build_logs_dir(str(tmp_path)),
                           TILELOG.RECORD_NAME), encoding="utf-8") as handle:
        assert json.load(handle)["schema"] == fixture["schema"]


def test_built_by_text_from_record_and_dsf_agent():
    with open(FIXTURE, encoding="utf-8") as handle:
        row = json.load(handle)["builds"][0]
    assert TILELOG.built_by_text(row) == (
        "XPTerrainBuilder 1.0.430, engine 1.50.1880")
    assert TILELOG.built_by_text(agent="Ortho4XP") == (
        "Ortho4XP (older build, version unknown)")
    assert TILELOG.built_by_text(agent="WorldEditor 2.5") == "WorldEditor 2.5"
    assert TILELOG.built_by_text() == ""
    assert TILELOG.creation_agent(WHO) == (
        "XPTerrainBuilder 1.0.999 (engine 1.50.9)")


def test_dsf_creation_agent_reads_the_head(tmp_path):
    dsf = tmp_path / "t.dsf"
    dsf.write_bytes(b"XPLNEDSF\x01\x00\x00\x00HEAD....PROP"
                    b"sim/west\x00-123\x00sim/creation_agent\x00Ortho4XP\x00")
    assert TILELOG.dsf_creation_agent(str(dsf)) == "Ortho4XP"
    (tmp_path / "z.dsf").write_bytes(b"7z\xbc\xaf\x27\x1c")
    assert TILELOG.dsf_creation_agent(str(tmp_path / "z.dsf")) == ""
    assert TILELOG.dsf_creation_agent(str(tmp_path / "missing.dsf")) == ""


@pytest.mark.parametrize("line, tile, text", [
    ("[+47-123] Step 1 done", "+47-123", "Step 1 done"),
    ("[-01+005] x", "-01+005", "x"),
    ("[worker 2] boom", None, "[worker 2] boom"),
    ("=== Run complete ===", None, "=== Run complete ==="),
])
def test_tile_of_line(line, tile, text):
    assert TILELOG.tile_of_line(line) == (tile, text)


def test_date_ranges(monkeypatch):
    now = 1_800_000_000.0
    assert TILELOG.in_date_range(None, "all", now)
    assert not TILELOG.in_date_range(None, "7d", now)
    assert TILELOG.in_date_range(now - 47 * 3600, "48h", now)
    assert not TILELOG.in_date_range(now - 49 * 3600, "48h", now)
    assert TILELOG.in_date_range(now - 6 * 86400, "7d", now)
    assert not TILELOG.in_date_range(now - 31 * 86400, "30d", now)
    assert TILELOG.in_date_range(now, "today", now)
    assert not TILELOG.in_date_range(now - 86400, "today", now)
    assert [key for key, _ in TILELOG.DATE_RANGES][-1] == "all"


def test_stream_tag_prefixes_and_logs_while_a_tile_builds(tmp_path):
    logs = TILELOG.TileBuildLogs(who=WHO)
    out = io.StringIO()
    active = {"tile": None}
    stream = TILELOG.TileStreamTag(out, logs, lambda: active["tile"])
    stream.write("before\n")
    logs.begin((47, -123), str(tmp_path))
    active["tile"] = (47, -123)
    stream.write("Step ")
    stream.write("one\n\n")
    active["tile"] = None
    logs.finish((47, -123), "ok")
    stream.write("after\n")
    assert out.getvalue() == "before\n[+47-123] Step one\n\nafter\n"
    row = TILELOG.last_build(str(tmp_path), 47, -123)
    assert TILELOG.read_log(str(tmp_path), row["log"]) == "Step one\n"


def test_log_is_capped(tmp_path):
    logs = TILELOG.TileBuildLogs(who=WHO, max_bytes=40)
    logs.begin((1, 2), str(tmp_path))
    for _ in range(10):
        logs.line((1, 2), "0123456789")
    logs.finish((1, 2), "ok")
    text = TILELOG.read_log(
        str(tmp_path), TILELOG.last_build(str(tmp_path), 1, 2)["log"])
    assert text.count("0123456789") == 3
    assert "cap of a tile's build log" in text


def test_in_process_build_tags_lines_and_writes_records(monkeypatch,
                                                        tmp_path, capsys):
    """In-process (1 slot): the tile's prints carry its prefix on the
    console and land in its own log; the record says how it ended."""
    install_stub_pipeline(
        monkeypatch,
        results={"mesh": lambda tile: 0 if tile.lat == 11 else 1},
        hooks={"vector": lambda tile: print("vector of", tile.lat)})
    session = EngineSession()
    events = _run_in_process(session, [(10, 20), (11, 21)], str(tmp_path))
    out = capsys.readouterr().out
    assert "[+10+020] vector of 10" in out
    assert "[+11+021] vector of 11" in out
    assert "[+10+020] Tile +10+020 completed in" in out
    ok = TILELOG.last_build(str(tmp_path), 10, 20)
    failed = TILELOG.last_build(str(tmp_path), 11, 21)
    assert ok["outcome"] == "ok" and failed["outcome"] == "failed"
    text = TILELOG.read_log(str(tmp_path), ok["log"])
    assert "vector of 10" in text and "vector of 11" not in text
    assert "*** Tile +11+021 failed" in TILELOG.read_log(
        str(tmp_path), failed["log"])
    # The streams are handed back when the run ends.
    assert not isinstance(sys.stdout, TILELOG.TileStreamTag)
    # The scan reads the record.
    dsf = TINFO.FNAMES.dsf_file(str(tmp_path), 10, 20)
    os.makedirs(os.path.dirname(dsf))
    with open(dsf, "wb") as handle:
        handle.write(b"XPLNEDSF")
    info = TINFO.tile_info(10, 20, str(tmp_path), grouped=True)
    assert info.last_build["log"] == ok["log"]
    assert info.built_by.startswith("XPTerrainBuilder ")
    assert any(isinstance(e, EV.RunDone) for e in events)


def test_in_process_warning_log_event_carries_its_tile(monkeypatch,
                                                       tmp_path):
    import O4_UI_Utils as UI
    install_stub_pipeline(
        monkeypatch, hooks={"vector": lambda tile: UI.loud_warning("loud")})
    session = EngineSession()
    UI.engine_session = session
    events = _run_in_process(session, [(10, 20)], str(tmp_path))
    warnings = [e for e in events if isinstance(e, EV.Log)]
    assert warnings and warnings[0].tile == (10, 20)


def test_stepwise_child_logs_nothing(monkeypatch, tmp_path):
    """A per-step worker child's lines are the parent's to log."""
    install_stub_pipeline(monkeypatch)
    session = EngineSession()
    collector = Collector(session)
    assert session.build([(10, 20)], "BI", 16, str(tmp_path),
                         steps=("vector",)) is True
    collector.wait_run_done(30.0)
    assert not os.path.exists(TILELOG.build_logs_dir(str(tmp_path)))


def test_parallel_build_logs_each_tile(stub_worker, tmp_path):
    """Parallel: worker lines reach their tile's log; the orchestrator's
    closing line joins it after the terminal; a crashed tile is failed."""
    session = EngineSession()
    collector = Collector(session)
    build_dir = str(tmp_path) + os.sep
    assert _start_parallel(session, [(10, 20), (62, 20)], slots=2,
                           custom_build_dir=build_dir) is True
    collector.wait_run_done(30.0)
    ok_dir = os.path.join(str(tmp_path), "zOrtho4XP_+10+020")
    crash_dir = os.path.join(str(tmp_path), "zOrtho4XP_+62+020")
    ok = TILELOG.last_build(ok_dir, 10, 20)
    crashed = TILELOG.last_build(crash_dir, 62, 20)
    assert ok["outcome"] == "ok"
    assert "Tile +10+020 completed in" in TILELOG.read_log(ok_dir, ok["log"])
    assert crashed["outcome"] == "failed"
    assert "crashing on purpose" in TILELOG.read_log(crash_dir,
                                                     crashed["log"])
