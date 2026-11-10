"""The flight record (spec flight-manager-and-world-20261110 §6.1, lane
F1a): made from a read plan, written atomically under ``Flights/``, read
back with unknown keys kept, listed newest first, one active flight."""

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Flight_Plan as FP  # noqa: E402
import pytest  # noqa: E402
from o4_engine import flight_record as FR  # noqa: E402

PLANS = os.path.join(os.path.dirname(__file__), "fixtures", "flight_plan")
NOW = datetime(2026, 11, 10, 16, 12, 30, tzinfo=timezone.utc)


def _plan(name):
    return FP.read_plan_file(os.path.join(PLANS, name))


def test_a_simbrief_record():
    rec = FR.from_plan(_plan("simbrief_ofp_full.xml"), "simbrief", NOW)
    assert rec.id == "20261110T1612Z-ENGM-ENBR"
    assert rec.source == {"kind": "simbrief", "name": "simbrief_ofp_full.xml",
                          "read_at": "2026-11-10T16:12:30Z"}
    assert rec.origin == {"ident": "ENGM", "lat": 60.193917, "lon": 11.100361}
    assert rec.alternate["ident"] == "ENZV" and rec.build_alternate is False
    assert rec.waypoints[1] == {"ident": "TOC", "lat": 60.3, "lon": 9.8,
                                "alt_ft": 24000.0, "t_s": 900.0}
    assert rec.profile["basis"] == "plan"
    assert rec.profile["cruise_ms"] == pytest.approx(280 * 1852 / 3600)
    assert (rec.profile["ete_s"], rec.profile["cruise_alt_ft"]) == (3300.0, 24000.0)
    assert (rec.state, rec.corridor_km, rec.tiles) == ("preparing", 20.0, [])


def test_the_speed_basis_order():
    fms = _plan("short_hop_v11.fms")            # no times, no speed
    assert FR.from_plan(fms, "fms", NOW).profile == {
        "cruise_ms": pytest.approx(250 * 1852 / 3600), "basis": "default"}
    assert FR.from_plan(fms, "fms", NOW, aircraft_ms=100.0).profile["basis"] == "aircraft"
    pilot = FR.from_plan(_plan("simbrief_ofp_full.xml"), "simbrief", NOW, cruise_kt=180)
    assert pilot.profile["basis"] == "pilot"
    assert pilot.profile["cruise_ms"] == pytest.approx(180 * 1852 / 3600)
    # timed waypoints and no speed: the mean speed over the route
    timed = fms._replace(waypoints=[w._replace(t_s=600.0 * i)
                                    for i, w in enumerate(fms.waypoints)])
    mean = FP.route_length_km(fms.points()) * 1000 / 1800.0
    assert FR.from_plan(timed, "fms", NOW).profile["cruise_ms"] == pytest.approx(mean)
    with pytest.raises(ValueError):
        FR.from_plan(fms, "garmin", NOW)


def test_an_odd_ident_still_makes_a_file_name():
    assert FR.flight_id("+45.000_+170.000", "", NOW) == "20261110T1612Z-45000170-NONE"


def test_save_load_round_trip_keeps_unknown_keys(tmp_path):
    rec = FR.from_plan(_plan("simbrief_ofp_full.xml"), "simbrief", NOW)
    rec.tiles.append(FR.TileRow(tile=[60, 5], role="destination", kind="full",
                                deadline_s=2900.0, est_s=[600.0, 1200.0]))
    folder = FR.flights_dir(str(tmp_path))
    path = FR.save(rec, folder)
    assert path == os.path.join(str(tmp_path), "Flights", rec.id + ".json")
    doc = json.load(open(path, encoding="utf-8"))
    doc["from_a_newer_engine"] = {"x": 1}
    doc["tiles"][0]["also_newer"] = 2
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh)
    back = FR.load(path)
    assert back.tiles == rec.tiles
    assert back.extra == {"from_a_newer_engine": {"x": 1}}
    FR.save(back, folder)
    assert json.load(open(path, encoding="utf-8"))["from_a_newer_engine"] == {"x": 1}
    assert not [n for n in os.listdir(folder) if n != rec.id + ".json"]


def test_list_and_the_active_flight(tmp_path):
    folder = str(tmp_path)
    fms = _plan("short_hop_v11.fms")
    old = FR.from_plan(fms, "fms", NOW)
    new = FR.from_plan(fms, "fms", NOW.replace(hour=18))
    new.state = "closed"
    FR.save(old, folder)
    FR.save(new, folder)
    (tmp_path / "junk.json").write_text("[]", encoding="utf-8", newline="\n")
    (tmp_path / "broken.json").write_text("{", encoding="utf-8", newline="\n")
    assert [r.id for r in FR.list_flights(folder)] == [new.id, old.id]
    assert FR.active_flight(folder).id == old.id
    assert FR.list_flights(str(tmp_path / "none")) == []
