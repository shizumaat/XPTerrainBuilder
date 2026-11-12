"""The Fly pane's words and map layers (spec flight-manager-and-world-
20261110 §4.3, §5.3, §14; #2001; lane U2), and ``aircraft_watch``.

``src/O4_Fly_Text.py`` / ``O4_Fly_Layers.py`` (the Qt window's) and the
Mac app's ``Sources/SceneryKit/FlyText.swift`` / ``FlyLayers.swift`` read
ONE shared fixture, ``tests/fixtures/fly_pane_cases.json``: this file
writes it from the Python rules (``REGENERATE_FLY_PANE=1``) and checks it
is current; ``Tests/SceneryKitTests/FlyPaneTests.swift`` checks the Swift
rules give the same answers and decodes the events in it.  Hermetic: no
Qt, no network, no X-Plane.
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import sys
import threading
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Fly_Divert_Text as DTEXT  # noqa: E402
import O4_Fly_Layers as LAYERS  # noqa: E402
import O4_Fly_Text as TEXT  # noqa: E402
from o4_engine import aircraft_watch as WATCH  # noqa: E402
from o4_engine import events as EV  # noqa: E402
from o4_engine.jsonl import serialize_event  # noqa: E402

CASES = Path(__file__).resolve().parent / "fixtures" / "fly_pane_cases.json"
SWIFT_TEXT = (Path(__file__).resolve().parents[2] / "Sources" / "SceneryKit"
              / "FlyText.swift")
SWIFT_DIVERT_TEXT = SWIFT_TEXT.with_name("FlyDivertText.swift")
#: The airport search's rows ``[ident, name, lat, lon]`` (lane F2).
AIRPORTS = [["CYQX", "Gander International", 48.94, -54.57],
            ["CYYT", "St. John's International", 47.62, -52.75],
            ["CYYR", "Goose Bay", 53.32, -60.43],
            ["CYY", "", 50.0, -60.0],
            ["KGND", "Gandy Field", 40.0, -100.0],
            ["CYQXA", "Gander Seaplane", 48.95, -54.6]]

# A FlightStatus as spec §5.3 freezes it (lane F1b emits it; until then
# this is the shape both panes are built on).
FLIGHT_STATUS = {
    "event": "FlightStatus", "flight": "20261110T1612Z-CYYR-CYYT",
    "state": "preparing", "phase": "parked", "ready": False,
    "countdown_s": 712.0, "reason": "",
    "items": [["world", "done", 0.0, ""], ["budget", "done", 0.0, ""],
              ["network", "done", 0.0, ""], ["prefetch", "working", None, ""],
              ["departure", "working", 412.0, ""],
              ["first_window", "waiting", 600.0, ""],
              ["route", "waiting", 712.0, ""],
              ["destination", "done", 0.0, "Ready 18 min before it loads"],
              ["loaded", "done", 0.0, ""]],
    "jobs": [[[53, -61], "departure", "full", "building", 412.0, None],
             [[53, -60], "enroute", "drape", "queued", 80.0, 1200.0],
             [[52, -59], "enroute", "drape", "swapped", 0.0, 900.0],
             [[47, -53], "destination", "full", "staged", 0.0, 1080.0]],
    "route_km": 833.6, "done_km": 0.0, "eta_s": 6480.0, "late": [],
    "shed": [], "reload": "", "diverted_to": "", "waivable": [],
}
WORLD_STATUS = {"state": "building", "reason": "", "building":
                [["+53-060", "drape", "building", 80]],
                # build-ahead's tiles in free flight (RULINGS 2026-11-11j)
                "jobs": [[[53, -60], "ahead", "drape", "building"],
                         [[53, -59], "ahead", "drape", "swapped"],
                         [[54, -60], "ahead", "drape", "queued"]],
                "loaded": ["+53-061", "+53-062"]}
DEP = ("cyyr", 53.3192, -60.4258)
ARR = ("CYYT", 47.6186, -52.7519)


def _text_cases():
    plan = TEXT.quick_plan(DEP, ARR)
    with_alt = dict(plan, alternate={"ident": "CYQX", "lat": 48.94,
                                     "lon": -54.57, "alt_ft": None,
                                     "t_s": None}, ete_s=5400.0,
                    cruise_ms=280 * 1852 / 3600)
    return {
        "countdown": [[s, TEXT.countdown_text(s)]
                      for s in (None, 0, -5, 30, 61, 712, 3600)],
        "items": [[row, TEXT.item_text(row)] for row in FLIGHT_STATUS["items"]
                  + [["world", "blocked", None, "Restart X-Plane once"],
                     ["alternate", "failed", None, "The build failed twice"],
                     ["mystery", "waiting", 30.0, ""]]],
        "plan_rows": [[row, TEXT.plan_row_label(row)] for row in (
            {"name": "CYLWCYYC", "origin": "CYLW", "destination": "CYYC"},
            {"name": "VFR hop", "origin": "", "destination": ""},
            {"name": "X", "origin": "KSEA", "destination": ""})],
        "quick_plan": [[list(DEP), list(ARR), plan]],
        "cruise_kt": [[None, TEXT.cruise_kt(None)], [plan, TEXT.cruise_kt(plan)],
                      [with_alt, TEXT.cruise_kt(with_alt)]],
        "card": [[plan, 250, TEXT.card_lines(plan, 250)],
                 [plan, 120, TEXT.card_lines(plan, 120)],
                 [with_alt, 280, TEXT.card_lines(with_alt, 280)]],
        "world_line": [[None, TEXT.world_line(None)],
                       [WORLD_STATUS, TEXT.world_line(WORLD_STATUS)],
                       [{"state": "paused", "reason": "X-Plane is not answering"},
                        TEXT.world_line({"state": "paused",
                                         "reason": "X-Plane is not answering"})]],
        "status_line": [[None, TEXT.follow_status_line(None)],
                        [FLIGHT_STATUS, TEXT.follow_status_line(FLIGHT_STATUS)],
                        [dict(FLIGHT_STATUS, reason="Building is 3 min behind"),
                         "Building is 3 min behind"]],
        "legend_key": [[k, s, TEXT.legend_key(k, s)]
                       for k in ("full", "drape", "placeholder")
                       for s in ("queued", "fetching", "building", "staged",
                                 "swapped", "late", "shed", "failed")],
        "unknown_airport": [[" zzzz ", TEXT.unknown_airport(" zzzz ")]],
        "refusal": [[e, TEXT.refusal(e)] for e in (
            "", "unknown command: 'flight_create'", "No plan to build")],
        "divert_airports": AIRPORTS,
        "divert_matches": [[q, n, DTEXT.divert_matches(q, AIRPORTS, n)]
                           for q, n in (("cyy", 12), ("CYQX", 12), ("gand", 12),
                                        ("  ", 12), ("C", 2), ("zzz", 12))],
        "divert_row_label": [[row, DTEXT.divert_row_label(row)]
                             for row in AIRPORTS[2:4]],
        "reload_line": [[{"flight": "f", "reload": r, "diverted_to": d},
                         DTEXT.reload_line({"reload": r, "diverted_to": d})]
                        for r, d in (("", ""), ("scheduled", "CYQX"),
                                     ("offered", ""), ("sent", "CYQX"))],
        "waiver_line": [[{"flight": "f", "waivable": w},
                         DTEXT.waiver_line({"waivable": w})]
                        for w in ([], ["+53-062", "+53-063"])],
    }


def _track_case():
    steps = [(53.0, -60.0), (53.0001, -60.0), (53.01, -60.0), (53.02, -60.01),
             (55.0, -60.0), (55.01, -60.0), (10.0, 179.99), (10.0, -179.99),
             (10.0, -179.9)]
    track = LAYERS.AircraftTrack()
    changed = [track.add(lat, lon, 90.0) for lat, lon in steps]
    return {"steps": [list(s) for s in steps], "changed": changed,
            "parts": [[list(p) for p in part] for part in track.parts()]}


def _doc():
    plan = TEXT.quick_plan(DEP, ARR)
    position = EV.AircraftPosition(lat=53.3, lon=-60.4, alt_m=640.5,
                                   track_deg=91.5, speed_ms=72.0,
                                   on_ground=False, paused=True)
    wire = {k: v for k, v in serialize_event(position).items()
            if k not in ("seq", "ts")}
    from o4_engine.flight_notices import notice
    flight_notice = {k: v for k, v in serialize_event(EV.FlightNotice(
        flight=FLIGHT_STATUS["flight"], **notice(
            "diversion_ready", destination="CYQX"))).items()
        if k not in ("seq", "ts")}
    return {"_comment": "Written by tests/test_fly_pane.py "
                        "(REGENERATE_FLY_PANE=1); read by "
                        "Tests/SceneryKitTests/FlyPaneTests.swift.",
            "events": {"AircraftPosition": wire, "FlightStatus": FLIGHT_STATUS,
                       "WorldStatus": WORLD_STATUS,
                       "FlightNotice": flight_notice},
            "text": _text_cases(),
            "track": _track_case(),
            "corridor": [[plan, 20, [], LAYERS.corridor_cells(plan, 20)],
                         [plan, 20, FLIGHT_STATUS["jobs"],
                          LAYERS.corridor_cells(plan, 20, FLIGHT_STATUS["jobs"])],
                         [None, 20, [], LAYERS.corridor_cells(None, 20)],
                         # free flight: build-ahead's drapes on the map
                         [None, 20, WORLD_STATUS["jobs"],
                          LAYERS.corridor_cells(None, 20, WORLD_STATUS["jobs"])]]}


def test_the_shared_fixture_is_current():
    doc = json.loads(json.dumps(_doc()))
    if os.environ.get("REGENERATE_FLY_PANE"):
        with open(CASES, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(doc, fh, indent=1, ensure_ascii=False)
            fh.write("\n")
    with open(CASES, encoding="utf-8") as fh:
        assert json.load(fh) == doc


def test_the_words():
    assert TEXT.countdown_text(None) == "Ready in —"
    assert TEXT.countdown_text(712) == "Ready in about 12 min"
    assert TEXT.item_text(["departure", "working", 412.0, ""]) == \
        "… Departure airport · about 7 min"
    assert TEXT.item_text(["world", "blocked", None, "Restart X-Plane once"]) \
        == "! World pack in X-Plane · Restart X-Plane once"
    plan = TEXT.quick_plan(DEP, ARR)
    assert plan["origin"] == "CYYR" and plan["destination"] == "CYYT"
    assert 820 < plan["route_km"] < 845
    assert TEXT.card_lines(plan, 250)[1] == "No alternate in the plan"
    # The plan-tier words never reach the user (§14).
    for _key, words in TEXT.LEGEND:
        assert not re.search(r"placeholder|drape|light", words)


def test_the_words_are_the_macs():
    swift = SWIFT_TEXT.read_text(encoding="utf-8")
    for name in ("PLAN_SOURCE_LABEL", "PLAN_CHOOSE", "PLAN_SIMBRIEF",
                 "PLAN_NONE", "SIMBRIEF_BUTTON", "QUICK_FROM", "QUICK_TO",
                 "QUICK_BUTTON", "PREPARE", "BUILD_ALTERNATE", "CRUISE_LABEL",
                 "CORRIDOR_LABEL", "SIM_PRIORITY_LABEL", "LIVE_PREVIEW",
                 "LIVE_PREVIEW_HELP", "DIVERT", "END_FLIGHT",
                 "NO_FLIGHT_MANAGER", "NO_STATUS", "CENTER_ON_AIRCRAFT",
                 "NO_AIRCRAFT_POSITION"):
        camel = re.sub(r"_(\w)", lambda m: m.group(1).upper(), name.lower())
        said = re.search(r'static let %s = "([^"]+)"' % camel, swift)
        assert said and said.group(1) == getattr(TEXT, name), name
    for key, label in TEXT.READINESS_LABELS.items():
        assert '"%s": "%s"' % (key, label) in swift, key
    for key, words in TEXT.LEGEND:
        assert '("%s", "%s")' % (key, words.replace('"', '\\"')) in swift, key
    for value, words in TEXT.SIM_PRIORITIES:
        assert '("%s", "%s")' % (value, words) in swift, value
    assert 'static let drapePxLabel = "%s"' % TEXT.DRAPE_PX_LABEL in swift
    assert 'static let drapePxKey = "%s"' % TEXT.DRAPE_PX_KEY in swift
    assert "static let aircraftFreshS = %.1f" % TEXT.AIRCRAFT_FRESH_S in swift
    for value, words in TEXT.DRAPE_PX_CHOICES:
        assert '(%d, "%s")' % (value, words) in swift, value
    divert = SWIFT_DIVERT_TEXT.read_text(encoding="utf-8")
    for name in ("DIVERT_TITLE", "DIVERT_SEARCH", "DIVERT_ALTERNATE",
                 "DIVERT_BUTTON", "RELOAD_NOW", "NOT_NOW", "WAIVE_OFFLINE"):
        camel = re.sub(r"_(\w)", lambda m: m.group(1).upper(), name.lower())
        said = re.search(r'static let %s = "([^"]+)"' % camel, divert)
        assert said and said.group(1) == getattr(DTEXT, name), name
    assert "static let searchLimit = %d" % DTEXT.SEARCH_LIMIT in divert


def test_the_track_breaks_at_jumps_and_the_antimeridian():
    case = _track_case()
    assert case["changed"] == [True, False, True, True, True, True, True,
                               True, True]
    assert [len(p) for p in case["parts"]] == [3, 2, 2]
    track = LAYERS.AircraftTrack()
    for i in range(LAYERS.TRACK_MAX_POINTS + 50):
        track.add(10.0 + i * 0.001, 20.0)
    assert sum(len(p) for p in track.parts()) == LAYERS.TRACK_MAX_POINTS


def test_the_corridor_follows_the_jobs_once_reported():
    plan = TEXT.quick_plan(DEP, ARR)
    before = LAYERS.corridor_cells(plan, 20)
    assert before and {k for *_t, k in before} == {"own"}
    assert (53, -61, "own") in before and (47, -53, "own") in before
    after = LAYERS.corridor_cells(plan, 20, FLIGHT_STATUS["jobs"])
    assert after == [(47, -53, "built"), (52, -59, "quick"),
                     (53, -61, "building"), (53, -60, "own")]


def test_free_flight_maps_the_drapes_ahead():
    """No flight, no plan: the map draws build-ahead's tiles
    (``WorldStatus.jobs``) by the same legend; a flight's jobs, or a plan's
    corridor, win over them."""
    ahead = WORLD_STATUS["jobs"]
    jobs = LAYERS.map_jobs((), False, ahead)
    assert LAYERS.corridor_cells(None, 20, jobs) == [
        (53, -60, "building"), (53, -59, "quick"), (54, -60, "own")]
    assert LAYERS.map_jobs(FLIGHT_STATUS["jobs"], False, ahead) == \
        FLIGHT_STATUS["jobs"]
    assert LAYERS.map_jobs((), True, ahead) == ()
    assert set(EV.WorldStatus.__dataclass_fields__) >= {"jobs", "building"}


# ─── aircraft_watch ────────────────────────────────────────────────────────

class _Reader:
    """X-Plane standing in: a position per read, then nothing."""

    def __init__(self, recs):
        self.recs = list(recs)
        self.resolved = True
        self.done = threading.Event()

    def read(self):
        if not self.recs:
            self.done.set()
            return None
        rec = self.recs.pop(0)
        self.resolved = rec.pop("_resolved", False)
        return rec


def test_the_event_fields_are_the_specs():
    fields = [f.name for f in dataclasses.fields(EV.AircraftPosition)
              if f.name not in ("seq", "ts")]
    assert fields == ["lat", "lon", "alt_m", "track_deg", "speed_ms",
                      "on_ground", "paused"]
    assert "aircraft_position" in EV.CAPABILITIES


def test_the_watch_publishes_positions_until_stopped():
    sent = []
    clock = iter(range(100))
    reader = _Reader([
        {"lat": 53.0, "lon": -60.0, "elev_m": 100.0, "agl_m": 0.5,
         "hdg": 270.0, "paused": 0, "_resolved": True},
        {"lat": 53.0, "lon": -59.99, "elev_m": 150.0, "agl_m": 50.0,
         "hdg": 270.0, "paused": 1},
    ])
    reply = WATCH.aircraft_watch(sent.append, on=True, reader=reader,
                                 period_s=0.001, clock=lambda: next(clock))
    assert reply == {"watching": True}
    assert reader.done.wait(5)
    assert WATCH.aircraft_watch(sent.append, on=False) == {"watching": False}
    first, second = sent[:2]
    assert (first.on_ground, first.track_deg, first.speed_ms) == (True, 270.0, 0.0)
    assert not second.on_ground and second.paused and second.alt_m == 150.0
    assert 85.0 < second.track_deg < 95.0 and second.speed_ms > 600


def test_the_watch_is_in_the_command_table():
    from o4_engine import jsonl

    src = Path(jsonl.__file__).read_text(encoding="utf-8")
    assert "**aircraft_watch_handlers(session._emit)" in src
    assert set(WATCH.aircraft_watch_handlers(lambda e: None)) == {"aircraft_watch"}


def test_a_record_with_no_position_never_ends_the_watch():
    """X-Plane answers with lat/lon null while a flight loads (1.0.494:
    the watch thread died on float(None) and never came back)."""
    import threading

    from o4_engine import aircraft_watch as WATCH

    class Reader:
        resolved = False

        def __init__(self):
            self.recs = [{"lat": None, "lon": None},
                         {"lat": 49.9, "lon": -97.2, "elev_m": 230.0}]
            self.done = threading.Event()

        def read(self):
            if not self.recs:
                self.done.set()
                return None
            return self.recs.pop(0)

    got, stop, reader = [], threading.Event(), Reader()
    thread = threading.Thread(target=WATCH._run, args=(
        got.append, reader, stop, 0.01, lambda: 0.0), daemon=True)
    thread.start()
    assert reader.done.wait(5)
    stop.set()
    thread.join(5)
    assert [round(p.lat, 1) for p in got] == [49.9]


def test_the_reader_treats_a_null_position_as_no_read(monkeypatch):
    import O4_XPlane_WebAPI as API
    monkeypatch.setattr(API, "resolve_refs", lambda *a, **k: ({"lat": 1}, []))
    monkeypatch.setattr(API, "read_position",
                        lambda *a, **k: {"lat": None, "lon": None})
    reader = API.PositionReader(base="http://127.0.0.1:1")
    assert reader.read() is None and "no position yet" in reader.error
