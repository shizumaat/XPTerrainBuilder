"""Hand-set object seats (protocol 1.25, #1703): ``object_seat_set``
stores a user edit beside the patch, ``object_seat`` reports it, and the
object stage's plan carries it as a row seat on every rebuild."""
from __future__ import annotations

import json
import os
from types import SimpleNamespace as NS

import O4_File_Names as FNAMES
import pytest
from auto_patch_v2.airport import user_seats as US
from auto_patch_v2.model import placement as P
from o4_engine import elevation_commands as EC
from o4_engine import object_seat as OS
from o4_engine import object_seat_edit as OSE

TILE = "+45-123"


def _row(path, lat, lon, kind="OBJECT"):
    return NS(def_path=path, lat=lat, lon=lon, heading_deg=90.0, elevation=None, kind=kind)


DUMP = NS(placements=[_row("objects/a.obj", 45.1, -122.9),
                      _row("objects/bridge.obj", 45.2, -122.8),
                      _row("objects/c.obj", 45.3, -122.7, "OBJECT_AGL")])


def _plan():
    prov = P.Provenance("", "", "")
    body = P.Body.from_dict({"body_id": "b0", "class": "deck",
                             "new_resource": "objects/bridge_o4b0.obj",
                             "anchor": {"lon": -122.8, "lat": 45.2}})
    return P.PlacementPlan(
        icao="ZZZZ", pack_name="p", pack_root="/p", dsf_path="/p/x.dsf",
        dsf_backup_path="/p/x.dsf.anchor_bak", provenance=prov,
        conversions=(P.Conversion.from_dict({"index": 2, "resource": "objects/c.obj",
                                             "lon": -122.7, "lat": 45.3,
                                             "kind_before": "OBJECT_AGL"}),),
        splits=(P.Split(P.PlacementRef.from_dict({"index": 1,
                                                  "resource": "objects/bridge.obj",
                                                  "lon": -122.8, "lat": 45.2}), (body,)),),
        kept=(P.Kept(0, "objects/a.obj", "stock"),))


def test_apply_seats_split_and_converted_rows_whole():
    seats = {1: US.UserSeat(1, "objects/bridge.obj", 45.2, -122.8, 61.5),
             2: US.UserSeat(2, "objects/c.obj", 45.3, -122.7, 70.0)}
    files = (NS(resource="objects/bridge_o4b0.obj"), NS(resource="objects/other.obj"))
    plan, kept_files, seated, refused = US.apply(_plan(), files, seats, DUMP)
    assert seated == (1, 2) and refused == ()
    assert not plan.splits and not plan.conversions and len(plan.kept) == 1
    assert {(m.index, m.elevation, m.why, m.heading_deg) for m in plan.msl_seats} == {
        (1, 61.5, US.WHY, 90.0), (2, 70.0, US.WHY, 90.0)}
    assert [f.resource for f in kept_files] == ["objects/other.obj"]  # its cut body goes


def test_a_seat_whose_row_changed_is_refused():
    seats = {0: US.UserSeat(0, "objects/zz.obj", 45.1, -122.9, 1.0),
             1: US.UserSeat(1, "objects/bridge.obj", 45.25, -122.8, 1.0),
             9: US.UserSeat(9, "objects/a.obj", 45.1, -122.9, 1.0)}
    plan, _f, seated, refused = US.apply(_plan(), (), seats, DUMP)
    assert seated == () and len(refused) == 3 and plan == _plan()


def test_set_read_clear_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Patch_dir", str(tmp_path))
    r = OSE.object_seat_set(TILE, "zzzz", 1, "objects/bridge.obj", 45.2, -122.8,
                            bottom_m=60.0, y_min=-1.5)
    assert (r["zero_m"], r["previous_zero_m"]) == (61.5, None)
    path = US.seats_path(OSE._patch_dir(TILE), "ZZZZ")
    with open(path, encoding="utf-8") as fh:
        assert json.load(fh)["seats"][0]["zero_m"] == 61.5
    assert US.digest(os.path.dirname(path), "ZZZZ")
    r = OSE.object_seat_set(TILE, "ZZZZ", 1, "objects/bridge.obj", 45.2, -122.8, zero_m=63.0)
    assert (r["zero_m"], r["previous_zero_m"]) == (63.0, 61.5)
    r = OSE.object_seat_set(TILE, "ZZZZ", 1, "objects/bridge.obj", 45.2, -122.8)
    assert r["zero_m"] is None and not os.path.exists(path)
    with pytest.raises(ValueError):
        OSE.object_seat_set(TILE, "ZZZZ", 1, "m", 45.2, -122.8, bottom_m=float("nan"))


def test_object_seat_reports_the_hand_set_seat(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Patch_dir", str(tmp_path))
    monkeypatch.setattr(EC, "cursor_elevation",
                        lambda lat, lon, build_dir=None: {"elevation_m": 40.0, "pending": False})
    OSE.object_seat_set(TILE, "ZZZZ", 11, "objects/a.obj", 45.2, -122.9, zero_m=55.0)
    rec = OS.object_seat(TILE, "ZZZZ", 11, 45.2, -122.9, y_min=-1.0, y_max=3.0)
    assert rec["user_zero_m"] == 55.0 and (rec["bottom_m"], rec["top_m"]) == (54.0, 58.0)
    assert rec["why"].startswith("Set by hand at 55.0 m MSL; rebuild the tile")
    # once a build placed it, the plan's row seat says so plainly
    plan_path = OS._plan_path(TILE, "ZZZZ")
    with open(plan_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"msl_seats": [{"index": 11, "elevation": 55.0, "why": US.WHY}]}, fh)
    assert OS.object_seat(TILE, "ZZZZ", 11, 45.2, -122.9)["why"] == "Set by hand at 55.0 m MSL"
    # an edited patch in use: the object stage does not run, and it says so
    open(os.path.join(os.path.dirname(plan_path), "ZZZZ_edited.patch.osm"), "w",
         encoding="utf-8", newline="\n").close()
    assert "auto patch" in OS.object_seat(TILE, "ZZZZ", 11, 45.2, -122.9)["why"]


def test_the_object_stage_applies_the_seats_beside_the_patch(tmp_path):
    from auto_patch import object_stage as OST
    US.set_seat(str(tmp_path), "ZZZZ", US.UserSeat(1, "objects/bridge.obj", 45.2, -122.8, 61.5),
                index=1)
    plan, files = OST._user_seats(_plan(), (), DUMP, str(tmp_path), "ZZZZ")
    assert [(m.index, m.why) for m in plan.msl_seats] == [(1, US.WHY)] and not plan.splits
    # a companion pack's plan is not the airport's own pack
    plan, _f = OST._user_seats(_plan(), (), DUMP, str(tmp_path), "ZZZZ~1")
    assert plan.splits and not plan.msl_seats
