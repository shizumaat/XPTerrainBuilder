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
import O4_World_State_Text as WORLD_TEXT  # noqa: E402
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
    # #2025: the departure on an adopted Ortho4XP tile, not yet answered
    "choices": [{"tile": [53, -61], "role": "departure", "icao": "CYYR",
                 "origin": "adopted", "built_by": "Ortho4XP",
                 "patched": "yes", "upgrade_estimate_s": 1500.0,
                 "choice": ""}],
}
#: ``FlightStatus.choices`` rows (#2025) for the words both apps say.
_CHOICE = FLIGHT_STATUS["choices"][0]
CHOICE_ROWS = [
    _CHOICE,
    dict(_CHOICE, patched="unknown", upgrade_estimate_s=None),
    dict(_CHOICE, role="destination", icao="", tile=[47, -53],
         origin="other", built_by="", patched="unknown"),
    dict(_CHOICE, built_by="MeshTool", origin="other", patched="no"),
    dict(_CHOICE, choice="keep"),
    dict(_CHOICE, choice="upgrade", upgrade_estimate_s=20.0),
]
WORLD_STATUS = {"state": "building", "reason": "", "building":
                [["+53-060", "drape", "building", 80]],
                # build-ahead's tiles in free flight (RULINGS 2026-11-11j)
                "jobs": [[[53, -60], "ahead", "drape", "building"],
                         [[53, -59], "ahead", "drape", "swapped"],
                         [[54, -60], "ahead", "drape", "queued"]],
                "loaded": ["+53-061", "+53-062"]}
#: ``WorldStatus.here`` as ``fly_here.describe`` gives it (#2020).
_HERE = {"tile": "+53-061", "lat": 53.3192, "lon": -60.4258,
         "on_ground": True, "kind": "placeholder", "job": "", "elapsed_s": 0,
         "estimate_s": 0, "core": False, "airport": "CYYR", "squares": 0,
         "sharp": 0, "reload_offer": ""}
HERE_CASES = [
    None, {},
    _HERE,
    dict(_HERE, job="queued"),
    dict(_HERE, job="building", elapsed_s=42, estimate_s=150, core=True),
    dict(_HERE, job="building", elapsed_s=605, estimate_s=0),
    dict(_HERE, job="staged", core=True),
    dict(_HERE, kind="drape", job="swapped", core=True, squares=9, sharp=4),
    dict(_HERE, kind="drape", job="swapped", core=True, squares=9, sharp=9),
    dict(_HERE, kind="drape", airport=""),
    dict(_HERE, kind="full", squares=4, sharp=4),
    dict(_HERE, job="failed"),
    dict(_HERE, kind="", job=""),
]
DEP = ("cyyr", 53.3192, -60.4258)
ARR = ("CYYT", 47.6186, -52.7519)


#: A departure-only flight's status (#2023): no route, a departure and
#: its window ring, no destination.
DEP_ONLY_STATUS = dict(
    FLIGHT_STATUS, flight="20261112T1600Z-CYYR-NONE", route_km=0.0,
    eta_s=0.0, jobs=[[[53, -61], "departure", "full", "building", 412.0, None],
                     [[53, -60], "enroute", "drape", "queued", 160.0, None]])


def _text_cases():
    plan = TEXT.quick_plan(DEP, ARR)
    alone = TEXT.quick_plan(DEP)
    later = TEXT.quick_plan(("CYYR", 53.3192, -60.4258), ARR)
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
        "quick_plan": [[list(DEP), list(ARR), plan], [list(DEP), None, alone]],
        "cruise_kt": [[None, TEXT.cruise_kt(None)], [plan, TEXT.cruise_kt(plan)],
                      [with_alt, TEXT.cruise_kt(with_alt)]],
        "card": [[plan, 250, TEXT.card_lines(plan, 250)],
                 [plan, 120, TEXT.card_lines(plan, 120)],
                 [with_alt, 280, TEXT.card_lines(with_alt, 280)],
                 [alone, 250, TEXT.card_lines(alone, 250)]],
        "departure_only": [[p, TEXT._departure_only(p)]
                           for p in (plan, alone, with_alt)],
        "added_destination": [
            [st, p, TEXT.added_destination(st, p)] for st, p in (
                (DEP_ONLY_STATUS, later), (DEP_ONLY_STATUS, alone),
                (FLIGHT_STATUS, later), (None, later),
                (dict(DEP_ONLY_STATUS, state="closed"), later),
                (DEP_ONLY_STATUS, TEXT.quick_plan(ARR, DEP)))],
        "world_line": [[None, TEXT.world_line(None)],
                       [WORLD_STATUS, TEXT.world_line(WORLD_STATUS)],
                       [{"state": "paused", "reason": "X-Plane is not answering"},
                        TEXT.world_line({"state": "paused",
                                         "reason": "X-Plane is not answering"})]],
        "status_line": [[None, TEXT.follow_status_line(None)],
                        [FLIGHT_STATUS, TEXT.follow_status_line(FLIGHT_STATUS)],
                        [dict(FLIGHT_STATUS, reason="Building is 3 min behind"),
                         "Building is 3 min behind"],
                        [DEP_ONLY_STATUS, TEXT.follow_status_line(DEP_ONLY_STATUS)],
                        [dict(DEP_ONLY_STATUS, state="flying"),
                         TEXT.follow_status_line(dict(DEP_ONLY_STATUS,
                                                      state="flying"))]],
        "legend_key": [[k, s, TEXT.legend_key(k, s)]
                       for k in ("full", "drape", "placeholder")
                       for s in ("queued", "fetching", "building", "staged",
                                 "swapped", "late", "shed", "failed")],
        "unknown_airport": [[" zzzz ", TEXT.unknown_airport(" zzzz ")]],
        "map_click_field": [[c, f, t, TEXT.map_click_field(c, f, t)]
                            for c in (False, True)
                            for f, t in (("", ""), (" ", ""), ("CYYR", ""),
                                         ("CYYR", "CYYT"), ("", "CYYT"))],
        "quick_map_hint": [[TEXT.QUICK_MAP_HINT]],
        "refusal": [[e, TEXT.refusal(e)] for e in (
            "", "unknown command: 'flight_create'", "No plan to build")],
        "divert_airports": AIRPORTS,
        "divert_matches": [[q, n, DTEXT.divert_matches(q, AIRPORTS, n)]
                           for q, n in (("cyy", 12), ("CYQX", 12), ("gand", 12),
                                        ("  ", 12), ("C", 2), ("zzz", 12))],
        "divert_row_label": [[row, DTEXT.divert_row_label(row)]
                             for row in AIRPORTS[2:4]],
        "reload_line": [[{"flight": "f", "reload": r, "diverted_to": d,
                          "state": s},
                         DTEXT.reload_line({"reload": r, "diverted_to": d,
                                            "state": s})]
                        for r, d, s in (("", "", "flying"),
                                        ("offered", "", "flying"),
                                        ("offered", "CYQX", "flying"),
                                        ("offered", "", "preparing"),
                                        ("sent", "CYQX", "flying"))],
        "here_lines": [[h, TEXT.here_lines(h)] for h in HERE_CASES],
        "choices": [[row, TEXT.choice_question(row), TEXT.choice_keep_label(row),
                     TEXT.choice_upgrade_label(row)] for row in CHOICE_ROWS],
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
            "aircraft_symbol": {
                "points": [list(p) for p in LAYERS.AIRCRAFT_SYMBOL],
                "placed": [[x, y, t, [list(p) for p in
                                      LAYERS.aircraft_symbol(x, y, t)]]
                           for x, y, t in ((100.0, 50.0, 0.0),
                                           (100.0, 50.0, 90.0),
                                           (10.0, 20.0, 225.0))]},
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
    # #2023: From with an empty To is a departure-only plan.
    alone = TEXT.quick_plan(DEP)
    assert TEXT._departure_only(alone) and not TEXT._departure_only(plan)
    assert alone["destination"] == "" and len(alone["waypoints"]) == 1
    assert TEXT.card_lines(alone, 250) == [
        "CYYR → no destination", "No alternate in the plan",
        TEXT.DEPARTURE_ONLY_CARD]
    assert TEXT.follow_status_line(DEP_ONLY_STATUS) == \
        TEXT.DEPARTURE_ONLY_PREPARING
    assert "Quick" in TEXT.DEPARTURE_ONLY_PREPARING
    added = TEXT.added_destination(DEP_ONLY_STATUS, plan)
    assert added == {"ident": "CYYT", "lat": 47.6186, "lon": -52.7519}
    assert TEXT.added_destination(FLIGHT_STATUS, plan) is None
    # The plan-tier word "light" never reaches the user (§14); the Fly
    # key names drapes as drapes and keeps the World pack's words (owner
    # 2026-11-12T19:11Z/19:12Z: one key, one palette).
    for _key, words in TEXT.LEGEND:
        assert not re.search(r"\blight\b", words)
    assert {w for _k, w in TEXT.LEGEND} >= {
        WORLD_TEXT.LEGEND_DRAPE, WORLD_TEXT.LEGEND_FULL,
        WORLD_TEXT.LEGEND_MESH, WORLD_TEXT.LEGEND_PLACEHOLDER}
    assert [TEXT.legend_key(k, "building") for k in ("drape", "full")] == [
        "draping", "meshing"]
    preparing = TEXT.follow_status_line(FLIGHT_STATUS)
    assert preparing.startswith("Preparing: departure building")
    assert "tiles ready" in preparing


def test_the_words_are_the_macs():
    swift = SWIFT_TEXT.read_text(encoding="utf-8")
    for name in ("PLAN_SOURCE_LABEL", "PLAN_CHOOSE", "PLAN_SIMBRIEF",
                 "PLAN_NONE", "SIMBRIEF_BUTTON", "QUICK_FROM", "QUICK_TO",
                 "QUICK_BUTTON", "NO_DESTINATION", "DEPARTURE_ONLY_CARD",
                 "DEPARTURE_ONLY_PREPARING", "DEPARTURE_ONLY_FLYING",
                 "PREPARE", "BUILD_ALTERNATE", "CRUISE_LABEL",
                 "CORRIDOR_LABEL", "SIM_PRIORITY_LABEL", "LIVE_PREVIEW",
                 "LIVE_PREVIEW_HELP", "SHARP_PHOTO", "SHARP_PHOTO_HELP", "DIVERT", "END_FLIGHT",
                 "NO_FLIGHT_MANAGER", "NO_STATUS", "CENTER_ON_AIRCRAFT",
                 "NO_AIRCRAFT_POSITION", "CHOICE_KEEP", "CHOICE_UPGRADE"):
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
    assert 'buildingKeys: Set<String> = [%s]' % ", ".join(
        '"%s"' % k for k in sorted(TEXT.BUILDING_KEYS)) in swift
    for value, words in TEXT.DRAPE_PX_CHOICES:
        assert '(%d, "%s")' % (value, words) in swift, value
    divert = SWIFT_DIVERT_TEXT.read_text(encoding="utf-8")
    for name in ("DIVERT_TITLE", "DIVERT_SEARCH", "DIVERT_ALTERNATE",
                 "DIVERT_BUTTON", "RELOAD_NOW", "WAIVE_OFFLINE"):
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
    assert after == [(47, -53, "built"), (52, -59, "draped"),
                     (53, -61, "meshing"), (53, -60, "own")]


def test_free_flight_maps_the_drapes_ahead():
    """No flight, no plan: the map draws build-ahead's tiles
    (``WorldStatus.jobs``) by the same legend; a plan's corridor wins over
    them; a flight's jobs win on their own tiles and build-ahead's other
    tiles are drawn beside them (track mode runs beside a flight, #2019)."""
    ahead = WORLD_STATUS["jobs"]
    jobs = LAYERS.map_jobs((), False, ahead)
    assert LAYERS.corridor_cells(None, 20, jobs) == [
        (53, -60, "draping"), (53, -59, "draped"), (54, -60, "own")]
    both = LAYERS.map_jobs(FLIGHT_STATUS["jobs"], False, ahead)
    assert both[:len(FLIGHT_STATUS["jobs"])] == tuple(FLIGHT_STATUS["jobs"])
    assert [tuple(r[0]) for r in both[len(FLIGHT_STATUS["jobs"]):]] == [
        tuple(r[0]) for r in ahead
        if tuple(r[0]) not in {tuple(f[0]) for f in FLIGHT_STATUS["jobs"]}]
    assert (53, -59, "draped") in LAYERS.corridor_cells(None, 20, both)
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


def test_the_here_block_says_where_and_how_far():
    """#2020: no plan, the aircraft's tile -- where, the quick photo, the
    full-detail squares; the plan-tier words never reach the user."""
    assert TEXT.here_lines(None) == [] and TEXT.here_lines({}) == []
    building = TEXT.here_lines(HERE_CASES[4])
    assert building == ["Preparing imagery at CYYR",
                        "Quick photo: building · 0:42 of about 3 min",
                        "Full detail nearby: fetching"]
    assert TEXT.here_lines(HERE_CASES[7])[-1] == \
        "Full detail nearby: 4 of 9 squares sharp"
    assert TEXT.here_lines(HERE_CASES[8])[0] == "Imagery ready at CYYR"
    assert TEXT.here_lines(HERE_CASES[9]) == ["Imagery ready at tile +53-061",
                                              "Quick photo: in place"]
    for case in HERE_CASES:
        for line in TEXT.here_lines(case):
            assert not re.search(r"placeholder|drape|light", line), line


def test_the_aircraft_is_a_small_airplane_along_its_track():
    """Owner 2026-11-12T15:33Z: a G1000-style airplane, nose along the
    track, about 21 x 22 px whatever the zoom."""
    xs = [x for x, _y in LAYERS.AIRCRAFT_SYMBOL]
    ys = [y for _x, y in LAYERS.AIRCRAFT_SYMBOL]
    assert 18 <= max(xs) - min(xs) <= 24 and 18 <= max(ys) - min(ys) <= 24
    assert LAYERS.AIRCRAFT_SYMBOL == tuple((-x, y) for x, y in
                                           [LAYERS.AIRCRAFT_SYMBOL[0]]
                                           + list(LAYERS.AIRCRAFT_SYMBOL[:0:-1]))
    north = LAYERS.aircraft_symbol(100, 50, 0)
    east = LAYERS.aircraft_symbol(100, 50, 90)
    assert north[0] == (100.0, 39.0) and east[0] == (111.0, 50.0)
