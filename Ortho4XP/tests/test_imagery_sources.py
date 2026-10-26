"""The engine's one imagery source list, its preview URLs and the
launch-time liveness check (#1345, ``src/O4_Imagery_Sources.py``).

Offline: the vendored ``Providers/`` tree, and an HTTP layer stubbed by
monkeypatching ``SOURCES._http_get``.
"""
import os
import sys
import threading

import pytest
import requests

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="module")
def sources():
    old_cwd = os.getcwd()
    os.chdir(REPO_ROOT)
    for path in (os.path.join(REPO_ROOT, "src"),
                 os.path.join(REPO_ROOT, "Providers")):
        if path not in sys.path:
            sys.path.insert(0, path)
    try:
        import O4_Imagery_Sources as SOURCES
        import O4_Imagery_Utils as IMG

        if not (IMG.providers_dict and IMG.combined_providers_dict):
            IMG.initialize_extents_dict()
            IMG.initialize_color_filters_dict()
            IMG.initialize_providers_dict()
            IMG.initialize_combined_providers_dict()
        yield SOURCES
    finally:
        try:
            os.chdir(old_cwd)
        except OSError:
            os.chdir(REPO_ROOT)


def _rows(sources):
    return {row["code"]: row for row in sources.imagery_sources()}


def test_list_counts_and_order(sources):
    import O4_Imagery_Utils as IMG

    rows = sources.imagery_sources()
    codes = [row["code"] for row in rows]
    offered = {code for code, p in IMG.providers_dict.items()
               if p.get("in_GUI", True) and code not in sources.HIDDEN}
    assert len(rows) == len(IMG.combined_providers_dict) + len(offered)
    assert len(set(codes)) == len(codes)
    # Combined first, then Global, then the other regions in order.
    n_comb = len(IMG.combined_providers_dict)
    assert all(row["combined"] for row in rows[:n_comb])
    singles = rows[n_comb:]
    assert singles[0]["region"] == "Global"
    keys = [(r["region"] != "Global", r["region"].lower(), r["code"].lower())
            for r in singles]
    assert keys == sorted(keys)
    assert "SEA" not in codes and "EUR" in codes


def test_previewable_flags(sources):
    rows = _rows(sources)
    for code in ("PDOK", "FIN", "QC", "PT", "AL", "BI", "OSM"):
        assert rows[code]["previewable"], code
        assert rows[code]["reason"] == ""
    assert not rows["Govmap"]["previewable"]
    assert "EPSG:2039" in rows["Govmap"]["reason"]
    assert not rows["Here"]["previewable"]        # custom URL code
    assert rows["EUR"]["previewable"] and rows["EUR"]["members"][-1]["bbox"] is None
    assert not rows["OSM"]["buildable"] and rows["BI"]["buildable"]


def test_wmts_preview_is_the_build_request(sources):
    """The map's WMTS URL is the build's own GetTile, tile for tile."""
    import O4_Imagery_Utils as IMG

    for code in ("PDOK", "FIN"):
        provider = IMG.providers_dict[code]
        preview = _rows(sources)[code]["preview"]
        for z in (10, 15):
            ident = preview["tilematrix"][z]
            tm = next(i for i, t in enumerate(provider["tilematrixset"]["tilematrices"])
                      if t["identifier"] == ident)
            built, _ = IMG.wmts_request(tm, 1234, 2345, provider)
            assert sources.expand_preview(preview, z, 1234, 2345) == built


def test_wms_preview_is_the_build_request(sources):
    import O4_Imagery_Utils as IMG

    provider = IMG.providers_dict["PT"]
    url = sources.preview_tile_url("PT", 14, 7820, 6240)["url"]
    size = 2 * 20037508.342789244 / 2 ** 14
    minx = -20037508.342789244 + 7820 * size
    maxy = 20037508.342789244 - 6240 * size
    box = tuple(float("%.2f" % v) for v in (minx, maxy, minx + size, maxy - size))
    built, _ = IMG.wms_request(box, 256, 256, provider)
    head, _, numbers = url.partition("BBOX=")
    built_head, _, built_numbers = built.partition("BBOX=")
    assert head == built_head
    assert [float(v) for v in numbers.split(",")] == [float(v) for v in built_numbers.split(",")]


def test_tms_preview_follows_the_template(sources):
    assert sources.preview_tile_url("QC", 15, 9692, 23000)["url"].endswith(
        "/15/9692/9767.jpg")
    reply = sources.preview_tile_url("Govmap", 15, 0, 0)
    assert reply["url"] is None and "EPSG:2039" in reply["reason"]
    with pytest.raises(ValueError):
        sources.preview_tile_url("NOPE", 1, 0, 0)


def test_combined_tile_resolves_its_layer(sources):
    import O4_Geo_Utils as GEO

    x, y = GEO.wgs84_to_gtile(52.37, 4.90, 14)        # inside the NL extent
    assert sources.tile_source("EUR", 14, x, y)["code"] in ("NL", "BE_Vl")
    x, y = GEO.wgs84_to_gtile(40.71, -74.0, 14)       # outside every extent
    assert sources.tile_source("EUR", 14, x, y)["code"] == "Arc@"


class _Answer:
    def __init__(self, status, kind):
        self.status_code = status
        self.headers = {"Content-Type": kind}


def test_probe_classifies_answers(sources, monkeypatch):
    answers = {
        "a": _Answer(200, "image/jpeg"),
        "b": _Answer(403, "text/html"),
        "c": _Answer(200, "text/html; charset=utf-8"),
        "d": _Answer(204, ""),
    }

    def fake_get(url, headers, timeout):
        assert timeout == sources.STATUS_TIMEOUT_S
        if url == "t":
            raise requests.Timeout()
        if url == "e":
            raise requests.ConnectionError()
        return answers[url]

    monkeypatch.setattr(sources, "_http_get", fake_get)
    assert sources.probe("a", None) == ("online", "")
    assert sources.probe("b", None)[0] == "offline"
    assert sources.probe("c", None)[0] == "offline"
    assert sources.probe("d", None) == ("unknown", "")
    assert sources.probe("t", None) == ("offline", "No answer within 5 seconds.")
    assert sources.probe("e", None)[0] == "offline"


def test_status_check_streams_one_event_per_source(sources, monkeypatch):
    """Stubbed HTTP: every source answers except the Bing host; combined
    EUR stays online while one of its layers is."""
    calls = []

    def fake_get(url, headers, timeout):
        calls.append(url)
        if "virtualearth" in url:
            raise requests.ConnectionError()
        return _Answer(200, "image/jpeg")

    monkeypatch.setattr(sources, "_http_get", fake_get)
    events, done = [], threading.Event()
    wanted = ["BI", "PDOK", "EUR", "Govmap"]

    def emit(code, status, reason):
        events.append((code, status, reason))
        if len(events) == len(wanted):
            done.set()

    reply = sources.check_status(emit, codes=wanted)
    assert reply == {"started": True, "count": 4}
    assert done.wait(30)
    by_code = {code: (status, reason) for code, status, reason in events}
    assert by_code["BI"][0] == "offline" and by_code["BI"][1]
    assert by_code["PDOK"] == ("online", "")
    assert by_code["EUR"] == ("online", "")
    assert by_code["Govmap"] == ("online", "")      # sampled in its own grid
    assert len(events) == 4                          # members are not reported


def test_session_and_transport_carry_the_commands(sources, monkeypatch):
    import O4_UI_Utils as UI
    from o4_engine import events as EV
    from o4_engine.jsonl import command_table
    from o4_engine.session import EngineSession

    monkeypatch.setattr(sources, "_http_get",
                        lambda url, headers, timeout: _Answer(200, "image/png"))
    # Never ``session.shutdown()`` here: it raises the process-wide stop
    # flag, and later tests on this worker (the inset ladder) then fetch
    # nothing.
    session = EngineSession()
    try:
        got, done = [], threading.Event()

        def on_event(event):
            if isinstance(event, EV.ImagerySourceStatus):
                got.append(event)
                done.set()

        session.subscribe(on_event)
        table = command_table(session)
        for name in ("imagery_sources", "imagery_source_status", "preview_tile_url"):
            assert name in table
        assert table["imagery_sources"]()[0]["code"] == "EUR"
        assert table["imagery_source_status"](codes=["PDOK"])["started"]
        assert done.wait(30)
        assert got[0].code == "PDOK" and got[0].status == "online"
        assert got[0].event == "ImagerySourceStatus"
        assert tuple(int(p) for p in EV.PROTOCOL_VERSION.split(".")) >= (1, 15)
    finally:
        UI.engine_session = None


def test_shared_fixture_rows_have_the_wire_shape(sources):
    """The Mac/Qt parity fixture's rows carry exactly the keys the engine
    sends (``Tests/SceneryKitTests/Fixtures/Imagery/imagery_menu.json``)."""
    import json

    path = os.path.join(REPO_ROOT, "..", "Tests", "SceneryKitTests", "Fixtures",
                        "Imagery", "imagery_menu.json")
    with open(path, encoding="utf-8") as handle:
        rows = json.load(handle)["rows"]
    wire = _rows(sources)
    for row in rows:
        assert set(row) == set(wire[row["code"]]), row["code"]
        for member in row["members"]:
            assert set(member) == {"code", "extent", "bbox", "preview"}
