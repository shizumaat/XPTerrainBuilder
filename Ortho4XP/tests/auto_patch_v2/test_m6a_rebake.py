"""M6a twins (RULINGS 2026-09-04i 04f-1): restore before read, the
re-seat plan and the seat law — v2-pure, hermetic, no v1 import."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from auto_patch_v2.airport import obj8
from auto_patch_v2.airport import pack as P
from auto_patch_v2.airport.load import Inputs, load_with_report
from auto_patch_v2.airport.rebake_plan import plan as _plan
from auto_patch_v2.emit import rebake as R
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import (Airport, DsfObject, Runway, RunwayEnd,
                                         SceneryPack)
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.basins import read_objects

FIX = Path(__file__).resolve().parent / "fixtures" / "CYXY"


# ── synthetic OBJ8 (a box whose feet sit ``depth`` under y = top) ────────

def _box_obj(path: Path, hx: float, hz: float, depth: float, top: float = 0.0,
             attr: str = "") -> Path:
    corners = [(-hx, -hz), (hx, -hz), (hx, hz), (-hx, hz)]
    vt = []
    for x, z in corners:
        vt.append((x, top, z))
        vt.append((x, top - depth, z))
    tris = []
    for i in range(4):
        a, b = 2 * i, 2 * ((i + 1) % 4)
        tris += [(a, a + 1, b), (a + 1, b + 1, b)]
    tris += [(1, 3, 5), (1, 5, 7), (0, 2, 4), (0, 4, 6)]
    lines = ["A", "800", "OBJ", "", "TEXTURE none",
             f"POINT_COUNTS {len(vt)} 0 0 {3 * len(tris)}"]
    lines += [f"VT {x:.3f} {y:.3f} {z:.3f} 0 1 0 0 0" for x, y, z in vt]
    idx = [i for t in tris for i in t]
    for k in range(0, len(idx), 10):
        chunk = idx[k:k + 10]
        lines.append(("IDX10 " if len(chunk) == 10 else "IDX ") + " ".join(map(str, chunk)))
    if attr:
        lines.append(attr)
    lines.append(f"TRIS 0 {len(idx)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    return path


class _FlatDem:
    provenance = {"synthetic": "flat 700"}

    def z(self, x: float, y: float) -> float:
        return 700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    root = tmp_path_factory.mktemp("pack")
    (root / "Earth nav data").mkdir()
    (root / "Earth nav data" / "apt.dat").write_text("I\n1200\n\n1 700 0 0 ZZZZ Synthetic\n")
    d = root / "objects"
    # feet 2 m under the authored ground plane (above the 2.5 m
    # below-grade admission): a seat lifts them +2
    _box_obj(d / "a.obj", 10.0, 8.0, 2.0)
    _box_obj(d / "b.obj", 6.0, 6.0, 2.0)
    _box_obj(d / "deck.obj", 12.0, 8.0, 0.5, top=4.0, attr="ATTR_hard_deck")
    _box_obj(d / "twice.obj", 4.0, 4.0, 2.0)
    # a resource a previous build baked: the live file is +3 m, the
    # authored bytes are in the backup
    _box_obj(d / "baked.obj", 5.0, 5.0, 2.0)
    shutil.copy2(d / "baked.obj", d / "baked.obj.anchor_bak")
    _box_obj(d / "baked.obj", 5.0, 5.0, 2.0, top=3.0)
    # a pit: genuine solids 6 m under grade — the terrain adapts to it
    _box_obj(d / "pit.obj", 30.0, 20.0, 6.0)
    _box_obj(root.parent / "lib" / "x.obj", 3.0, 3.0, 1.0)     # a stock library file
    return root


def _airport(pack_root: Path, law, placements) -> Airport:
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 522.5), (60.5, -135.5), 0.0, 0.0, 697.0, "fixture"),
            RunwayEnd("27", (600.0, 522.5), (60.5, -135.5), 0.0, 0.0, 703.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    sp = SceneryPack("fixture", str(pack_root / "Earth nav data" / "apt.dat"), "0", (), ())
    dsf = []
    for i, (name, xy, hd, agl) in enumerate(placements):
        path = f"objects/{name}.obj"
        resolved = str(pack_root / path) if not name.startswith("lib") else None
        if name.startswith("lib"):
            path = "lib/airport/x.obj"
            resolved = str(pack_root.parent / "lib" / "x.obj")
        resolved, _ = P.authored_source(resolved)
        dsf.append(DsfObject(f"dsf:obj{i}", path, xy, hd, None, False, None, agl,
                             resolved, "OBJECT_AGL" if agl else "OBJECT"))
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (), (), (), (),
                   (), (), tuple(dsf), sp, _FlatDem(), law.ruleset_key)


# ── 1. restore before read ───────────────────────────────────────────────

def test_authored_source_prefers_the_backup(pack):
    live = str(pack / "objects" / "baked.obj")
    got, restored = P.authored_source(live)
    assert restored and got == live + ".anchor_bak"
    assert P.live_path_of(got) == live
    assert P.authored_source(got) == (got, False)          # already the backup
    plain = str(pack / "objects" / "a.obj")
    assert P.authored_source(plain) == (plain, False)
    assert P.authored_source(None) == (None, False)


def test_read_side_restore_reads_the_authored_geometry(pack, law):
    """The planar object read sees the AUTHORED box (top 0), not the
    +3 m bake on disk."""
    a = _airport(pack, law, [("baked", (0.0, 0.0), 0.0, 0.0)])
    objs, rep = read_objects(a, law)
    assert rep.resolved == 1
    g = obj8.parse_obj8(objs[0].resolved)
    assert objs[0].resolved.endswith(".anchor_bak")
    assert float(g.vertices[:, 1].max()) == 0.0
    assert float(obj8.parse_obj8(str(pack / "objects" / "baked.obj")).vertices[:, 1].max()) == 3.0


def test_loader_counts_restored_for_read(tmp_path, law):
    """Through ``airport.load``: a pack-relative placement whose live
    file has an ``.anchor_bak`` resolves to the backup and is counted."""
    root = tmp_path / "fix"
    shutil.copytree(FIX, root)
    pack_root = root / "Custom Scenery" / "CYXY Fixture"
    _box_obj(pack_root / "objects" / "shed.obj", 5.0, 5.0, 3.0)
    shutil.copy2(pack_root / "objects" / "shed.obj", pack_root / "objects" / "shed.obj.anchor_bak")
    dump = root / "Airport_mod_cache" / "CYXY Fixture" / "+60-136.dsf.fixture.text"
    text = dump.read_text()
    n_defs = text.count("OBJECT_DEF ")
    text = text.replace("OBJECT 0 ", f"OBJECT {n_defs} ", 1)
    text = text.replace("OBJECT_DEF lib/airport/buildings/utility/sheds/10x12/1.obj",
                        "OBJECT_DEF lib/airport/buildings/utility/sheds/10x12/1.obj\n"
                        "OBJECT_DEF objects/shed.obj", 1)
    dump.write_text(text)
    inp = Inputs(xplane_root=str(root), cifp_dir=str(root / "CIFP"),
                 osm_root=str(root / "OSM_data"), elevation_root=str(root / "Elevation_data"),
                 dem_frame="authored", mod_cache_root=str(root / "Airport_mod_cache"))
    a, rep = load_with_report("CYXY", inp, Law.for_airport("CYXY"))
    assert rep.objects_resolved == 1 and rep.objects_restored_for_read == 1
    o = next(o for o in a.dsf_objects if o.resolved_path)
    assert o.resolved_path.endswith("shed.obj.anchor_bak")


# ── 2. the plan ──────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def planned(pack, law):
    a = _airport(pack, law, [
        ("a", (0.0, 0.0), 0.0, 0.0),
        ("b", (0.0, 0.0), 90.0, 0.0),           # same anchor spelling: one unit
        ("deck", (300.0, 0.0), 0.0, 0.0),
        ("twice", (500.0, 0.0), 0.0, 0.0),
        ("twice", (600.0, 0.0), 0.0, 0.0),      # two anchors: I-4, skipped
        ("lib", (800.0, 0.0), 0.0, 0.0),        # stock library: skipped
        ("baked", (-400.0, 0.0), 0.0, 0.0),
        ("pit", (-900.0, 0.0), 0.0, 0.0),       # below grade: skipped
    ])
    objs, _ = read_objects(a, law)
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    for o in objs:
        if o.resolved:
            cache.geometry(o.resolved)
    return a, _plan(a, objs, cache, law)


def test_plan_units_and_skips(planned):
    a, pl = planned
    by_res = {m.resource: (u, m) for u in pl.units for m in u.members}
    ua, _ = by_res["objects/a.obj"]
    ub, _ = by_res["objects/b.obj"]
    assert ua is ub and len(ua.members) == 2                 # one anchor, one unit
    skipped = dict(pl.skipped)
    assert "I-4" in skipped["objects/twice.obj"]
    assert "stock" in skipped["lib/airport/x.obj"]
    assert "objects/twice.obj" not in by_res
    assert pl.counts["multi_anchor"] == 1 and pl.counts["stock"] == 1
    assert pl.counts["below_grade"] == 1 and "below-grade" in skipped["objects/pit.obj"]
    assert pl.counts["units"] == 3 and pl.counts["members"] == 4
    _, md = by_res["objects/deck.obj"]
    assert md.deck_ring and len(md.deck_ring) >= 4 and md.deck_top_y == 4.0
    _, mk = by_res["objects/baked.obj"]
    assert mk.authored_path.endswith(".anchor_bak") and mk.live_path.endswith("baked.obj")
    assert all(f.y == -2.0 for f in mk.feet)                # the authored feet, not the bake


def test_plan_json_round_trip(planned):
    _, pl = planned
    back = R.RebakePlan.from_json(pl.to_json())
    assert back == pl
    assert json.loads(pl.to_json())["version"] == R.PLAN_VERSION


# ── 3. the seat ──────────────────────────────────────────────────────────

def _flat(z: float, water: bool = False):
    return lambda lat, lon: (z, water)


def test_feet_seat_on_the_mesh(planned, law):
    _, pl = planned
    # anchor ground 710, the mesh 705 under the feet (authored at −2, i.e.
    # 708): the feet float 3 m over the ground and the seat LOWERS the
    # unit −3 (05p: feet 2 m UNDER a flat mesh would be a facility)
    seen = {"n": 0}

    def s(lat, lon):
        seen["n"] += 1
        return (710.0 if seen["n"] == 1 else 705.0, False)
    unit = next(u for u in pl.units if u.members[0].resource == "objects/a.obj")
    res = R.seat(R.RebakePlan(pl.icao, pl.pack_name, pl.pack_root, (unit,), (), {}), s, law)
    ua = res.units[0]
    assert ua.bakes and ua.datum == "feet" and ua.delta_m == pytest.approx(-3.0)
    assert ua.seat_datum_m == pytest.approx(707.0)
    assert set(ua.resources) == {"objects/a.obj", "objects/b.obj"}   # one delta, both
    assert all(m.delta_m == pytest.approx(-3.0) and not m.facility for m in ua.members)


# ── 3b. THE FACILITY RULE (RULINGS 2026-09-05p) ──────────────────────────

def _feet_member(name: str, y: float, n: int = 16, lat0: float = 0.0):
    feet = tuple(R.Foot(lat0 + i * 1e-5, 1e-5, y) for i in range(n))
    return R.Member(name, f"objects/{name}.obj", name, name, 0.0, feet)


def _unit(*members):
    return R.RebakePlan("OTHH", "p", "/p", (R.Unit("unit:21", (0.0, 0.0), 0.0, members),),
                        (), {})


def test_facility_member_never_founds(law):
    """OTHH unit:21: three at-grade members and one whose feet stand
    2.5 m under the mesh — the sunken one is a FACILITY member, the seat
    is founded by the at-grade band (delta ≈ 0), the family stays."""
    depth = law.tables.structures.basin.contact_band_m
    pl = _unit(_feet_member("Terminal_Base", 0.0), _feet_member("Terminal_Interior", 0.0),
               _feet_member("Terminal_Orchard", 0.0),
               _feet_member("TerminalRoads_03_004", -(depth + 1.5)))
    us = R.seat(pl, _flat(710.0), law).units[0]
    by = {m.resource: m for m in us.members}
    assert us.delta_m == pytest.approx(0.0, abs=1e-9) and not us.held
    assert us.skip_reason.startswith("below_threshold")
    road = by["objects/TerminalRoads_03_004.obj"]
    assert road.facility and not road.founding and "facility member" in road.note
    assert all(by[r].founding and not by[r].facility for r in by if "Terminal_" in r)
    assert any("facility member" in f and "TerminalRoads_03_004" in f for f in us.findings)
    assert R.SeatResult("OTHH", (us,)).counts()["facility_members"] == 1


def test_members_above_the_mesh_still_found(law):
    """HECA's authored plane over a cut apron: every member 15 m ABOVE
    the mesh — never a facility, the seat lowers the family −15."""
    pl = _unit(_feet_member("a", 15.0), _feet_member("b", 15.0), _feet_member("c", 15.0))
    us = R.seat(pl, _flat(710.0), law).units[0]
    assert us.bakes and us.delta_m == pytest.approx(-15.0)
    assert all(m.founding and not m.facility for m in us.members)


def test_all_sunken_unit_has_no_founder(law):
    depth = law.tables.structures.basin.contact_band_m
    pl = _unit(_feet_member("road", -(depth + 0.9)), _feet_member("parking", -(depth + 1.4)))
    us = R.seat(pl, _flat(710.0), law).units[0]
    assert us.delta_m is None and not us.bakes and not us.held
    assert "no founder" in us.skip_reason and "facility" in us.skip_reason
    assert all(m.facility and not m.founding for m in us.members)
    assert any("2 facility member(s)" in f for f in us.findings)
    # exactly at the band the member is still at grade (the band is inclusive)
    us2 = R.seat(_unit(_feet_member("edge", -depth)), _flat(710.0), law).units[0]
    assert not us2.members[0].facility and us2.delta_m == pytest.approx(depth)


def test_facility_member_is_excluded_from_the_decision(law):
    """The v1 decision hands a facility member to the excluded path with
    a reason the provenance records (``excluded_reason``)."""
    from auto_patch.engine_v2 import _decision_from_seats
    depth = law.tables.structures.basin.contact_band_m
    pl = _unit(_feet_member("Terminal_Base", 12.0), _feet_member("road", -(depth + 1.0)))
    res = R.seat(pl, _flat(710.0), law)
    assert res.units[0].bakes and res.units[0].delta_m == pytest.approx(-12.0)
    dec = _decision_from_seats(pl, res, measure_only=False)
    reasons = dict(dec.skipped)
    assert "facility member (05p)" in reasons["objects/road.obj"]
    assert "objects/road.obj" not in dec.delta_by_resource_and_vertex
    assert "objects/road.obj" in dec.anchor_by_resource      # registered for the reversion pass


def test_water_never_founds_a_seat(planned, law):
    _, pl = planned
    res = R.seat(pl, _flat(710.0, water=True), law)
    assert all(not u.bakes and "water" in (u.skip_reason or "") for u in res.units)


def test_below_threshold_stays(planned, law):
    _, pl = planned
    rb = law.tables.structures.rebake
    # feet at −2 seat +2; a mesh 1.5 m LOWER under the feet than at the
    # anchor is impossible with a flat sampler, so shift through the
    # anchor: sampler answers 710 at the anchor and 708.5 elsewhere
    seen = {"n": 0}

    def s(lat, lon):
        seen["n"] += 1
        return (710.0 if seen["n"] == 1 else 708.5, False)
    res = R.seat(R.RebakePlan(pl.icao, pl.pack_name, pl.pack_root, pl.units[:1], (), {}),
                 s, law)
    u = res.units[0]
    assert not u.bakes and u.skip_reason.startswith("below_threshold")
    assert abs(u.delta_m) < rb.min_delta_m


def test_deck_top_datum(planned, law):
    _, pl = planned
    unit = next(u for u in pl.units if u.members[0].resource == "objects/deck.obj")
    m = unit.members[0]
    # the solved surface put 703.0 at the deck: deck top (authored +4)
    # must land there → delta = 703 − (710 + 4) = −11
    m2 = R.Member(m.id, m.resource, m.authored_path, m.live_path, m.heading_deg, m.feet,
                  m.deck_ring, m.deck_top_y, 703.0)
    pl2 = R.RebakePlan(pl.icao, pl.pack_name, pl.pack_root,
                       (R.Unit(unit.id, unit.anchor, unit.agl_m, (m2,)),), (), {})
    u = R.seat(pl2, _flat(710.0), law).units[0]
    assert u.bakes and u.datum == "deck_top" and u.delta_m == pytest.approx(-11.0)
    # without a solved value the deck ring's mesh samples found it
    u = R.seat(pl, _flat(710.0), law).units[[x.id for x in pl.units].index(unit.id)]
    assert u.datum == "deck_top" and u.delta_m == pytest.approx(-4.0)


def test_family_takes_the_agreeing_coalition(law):
    rb = law.tables.structures.rebake
    assert R._coalition([6.0, 6.1, 9.0], rb.agreement_window_m)[0] == [6.0, 6.1]
    coal, why = R._coalition([1.0, 1.1, 5.0, 5.1], rb.agreement_window_m)
    assert coal is None and "tie" in why
    assert R._coalition([1.0, 3.0, 5.0], rb.agreement_window_m)[0] is None
    assert R._coalition([2.0], rb.agreement_window_m)[0] is None
