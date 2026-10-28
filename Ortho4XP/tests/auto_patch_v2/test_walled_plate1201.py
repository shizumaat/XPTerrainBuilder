"""#1201 (owner RULINGS 2026-10-27t / 2026-10-27u): a runway-end WALLED PLATE
is recognised by geometry and position, the safety area ends at its inner
edge, its top is the seat's datum, and the ground under it never rises
through it.  Synthetic: one runway along +y, its north end at (0, 0); a plate
290-310 m past the end, a 20 m wall at its outer edge, the DEM stepping 15 m."""
from __future__ import annotations

import types

import numpy as np
import pytest
from auto_patch_v2.airport import plate_ground as PG
from auto_patch_v2.airport import walled_plate as W
from auto_patch_v2.airport.anchor_rule import datum_of
from auto_patch_v2.airport.obj8 import ObjGeometry, PlacedObject
from auto_patch_v2.constraints.walled_plate import RULING, under_plate_rows
from auto_patch_v2.law import Law
from auto_patch_v2.model.constraints import Band
from auto_patch_v2.model.end_area import end_area_lengths
from auto_patch_v2.model.walled_plate import WalledPlate
from shapely.geometry import Polygon


@pytest.fixture(scope="module")
def law():
    return Law.load()


def _runway():
    def end(n, xy):
        return types.SimpleNamespace(name=n, xy=xy, approach="visual")
    return types.SimpleNamespace(id="16/34",
                                 ends=(end("16", (0.0, 0.0)), end("34", (0.0, -3000.0))),
                                 code_number=4, code_letter="E", instrument=False, width_m=45.0)


class _Dem:
    """Upper ground falling 3 % past the end, ``step`` m lower past s = 318."""

    def __init__(self, step=15.0):
        self.step = step

    def z(self, x, y):
        return 100.0 - 0.03 * max(y, 0.0) - (self.step if y > 314.0 else 0.0)

    def z_many(self, xs, ys):
        return np.array([self.z(x, y) for x, y in zip(xs, ys, strict=True)])


def _plate_geometry(wall=True, half=100.0, s0=290.0, s1=310.0, h=20.0) -> ObjGeometry:
    """An OBJ8 placed at the origin (0, 0) heading 0: authored x east,
    z south, so the frame's north s is -z."""
    v = [(-half, 0.0, -s0), (half, 0.0, -s0), (half, 0.0, -s1), (-half, 0.0, -s1)]
    tris = [(0, 1, 2), (0, 2, 3)]
    if wall:
        v += [(-half, -h, -s1), (half, -h, -s1)]
        tris += [(3, 2, 5), (3, 5, 4)]
    vv = np.array(v, dtype=float)
    t = np.array(tris, dtype=np.int64)
    return ObjGeometry("p.obj", vv, t, np.zeros(len(t), dtype=np.int64),
                       np.zeros((0, 3), dtype=np.int64))


def _placed(xy=(0.0, 0.0), extent=None) -> PlacedObject:
    box = Polygon(extent or [(-100, 280), (100, 280), (100, 320), (-100, 320)])
    return PlacedObject("dsf:1", "objects/p.obj", "/pack/objects/p.obj", xy, 0.0, 0.0, "OBJECT",
                        100.0, None, box, None, None, None, None, origin_built=True,
                        deck_kind="candidate")


def _airport(dem=None, plates=()):
    return types.SimpleNamespace(runways=(_runway(),), dem=dem or _Dem(), walled_plates=plates)


class _Cache:
    def __init__(self, g):
        self.g = g

    def geometry(self, path):
        return self.g


def test_recognised_by_all_four_witnesses(law):
    out = W.mark(_airport(), [_placed()], _Cache(_plate_geometry()), law)
    p = out[0].walled_plate
    assert p is not None and p.end_name == "16" and p.end == 0
    assert p.inner_s == pytest.approx(290.0, abs=1.0)
    assert p.height_m == pytest.approx(20.0, abs=0.5)
    assert p.plate_y == pytest.approx(0.0)
    # out of the readings another law owns (27u replaces the 20s guard)
    assert out[0].origin_built is False and out[0].deck_kind == ""
    assert all(s[1] == pytest.approx(288.0, abs=1.0) for s in p.stations)


@pytest.mark.parametrize("why, kw", [
    ("no outer wall", dict(geometry=_plate_geometry(wall=False))),
    ("no lower ground at the foot", dict(dem=_Dem(step=0.0))),
    ("a step deeper than the wall: its foot would float", dict(dem=_Dem(step=30.0))),
    ("too narrow for the safety area", dict(geometry=_plate_geometry(half=30.0))),
])
def test_refused(law, why, kw):
    g = kw.get("geometry", _plate_geometry())
    out = W.mark(_airport(kw.get("dem")), [_placed()], _Cache(g), law)
    assert out[0].walled_plate is None, why
    assert out[0].origin_built is True


def test_off_the_axis_is_not_read(law):
    far = [(900, 280), (1100, 280), (1100, 320), (900, 320)]
    out = W.mark(_airport(), [_placed(xy=(1000.0, 0.0), extent=far)], _Cache(_plate_geometry()),
                 law)
    assert out[0].walled_plate is None


def _record(**kw) -> WalledPlate:
    base = dict(ids=("dsf:1",), runway="16/34", end=0, plate_y=-9.9, inner_s=290.0,
                stations=((0.0, 288.0),), inner=((-100.0, 290.0), (100.0, 290.0)),
                outer=((-100.0, 310.0), (100.0, 310.0)),
                footprint=((-100.0, 290.0), (100.0, 290.0), (100.0, 310.0), (-100.0, 310.0),
                           (-100.0, 290.0)),
                height_m=20.0, step_m=15.0, end_name="16")
    base.update(kw)
    return WalledPlate(**base)


def test_the_safety_area_ends_at_the_inner_edge(law):
    ap = types.SimpleNamespace(runways=(_runway(),), dem=None, walled_plates=(_record(),))
    lens = end_area_lengths(ap, law)["16/34"]
    assert lens[0] == pytest.approx(290.0)
    assert lens[1] > 290.0                  # the uncapped end keeps its length


def test_the_plate_is_the_seat_datum_at_any_height():
    m = types.SimpleNamespace(plate_y=-9.9, plate_kind="walled", plate_stations=((47.0, -122.0),),
                              deck_top_y=None, deck_kind="")
    d = datum_of(m)
    assert d is not None and d.y == pytest.approx(-9.9) and d.stations == ((47.0, -122.0),)
    # without the kind, a negative plate is a floor plate and reads no datum
    m.plate_kind = ""
    assert datum_of(m) is None


def _planar(points):
    """``points``: id -> (xy, roles); one face per role."""
    roles = sorted({r for _xy, rs in points.values() for r in rs})
    fid = {r: i for i, r in enumerate(roles)}
    faces = {i: types.SimpleNamespace(id=i, role=r, ref="") for r, i in fid.items()}
    verts = {k: types.SimpleNamespace(id=k, xy=xy, incident_faces=tuple(fid[r] for r in rs))
             for k, (xy, rs) in points.items()}
    pm = types.SimpleNamespace(vertices=verts, faces=faces)
    pm.plate_under = PG.under_plate_vertices(pm, (_record(),))
    return pm


def test_the_ground_under_the_plate_stays_below_it(law):
    pm = _planar({1: ((0.0, 300.0), ["graded_strip"]), 2: ((5.0, 300.0), ["service_road"]),
                  3: ((5.0, 330.0), ["service_road"]), 4: ((0.0, 290.5), ["service_road"])})
    rows = under_plate_rows(pm, law, _airport(plates=(_record(),)))
    # the road under the plate only: never the safety area's own vertex, never
    # a vertex on the inner edge or past the outer one
    caps = [r for r in rows if isinstance(r, Band)]
    assert [r.v for r in caps] == [2]
    # and its soft design target at the same level (the lidar there is the step)
    tg = [r for r in rows if not isinstance(r, Band)]
    assert [(r.terms, r.lo) for r in tg] == [(((2, 1.0),), caps[0].hi)]
    r = caps[0]
    assert isinstance(r, Band) and r.lo is None and r.source.ruling == RULING
    # the ground read step_inside_m (5 m) inside the inner edge, off the smear
    assert r.hi == pytest.approx(_Dem().z(0.0, 285.0) - 0.05)


def test_the_wall_at_the_plate_is_declared_lawful_to_the_census():
    """27t: a terrace joint at the plate carries the emitter's flag, and the
    census's runway-strip wall ban (2026-08-01) exempts exactly it."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    import check_grade
    at = {"points": [[290.0, -50.0], [290.0, 50.0]]}         # (lat, lon) = (y, x) here
    away = {"points": [[100.0, -50.0], [100.0, 50.0]]}
    wing = {"points": [[200.0, 90.0], [280.0, 90.0]], "shapes": ["objects/p.obj#comp1"]}
    rows = W.declare_joints([at, away, wing], (_record(),), lambda lon, lat: (lon, lat),
                            ("objects/p.obj",))
    assert rows[0].get(W.JOINT_KEY) is True and W.JOINT_KEY not in rows[1]
    assert rows[2].get(W.JOINT_KEY) is True          # the plate object's own wall
    assert check_grade._terrace_joint_strip_exempt(rows) == [True, False, True]


# ── l1201c (KSEA sim read 2026-10-27): the four follow-ups ──────────────

def test_a_landed_keep_is_written_as_authored():
    """Fix A: a placement the stage KEPT because its authored seat lands
    (14g (3), ``authored_seat_lands``) keeps its OBJECT_MSL row — converting
    it to on-ground put KSEA 16C's plate 8.7 m over the safety area."""
    from auto_patch_v2.airport import placement_write as PW
    row = types.SimpleNamespace(def_path="objects/p.obj", lat=47.0, lon=-122.0,
                                heading_deg=0.0, kind="OBJECT_MSL", elevation=118.87)
    dump = types.SimpleNamespace(placements=[row])
    plan = types.SimpleNamespace(units=(), contacts=(), flat=None, authored_seats=())

    def conv(kept):
        ss = types.SimpleNamespace(unit_seats=(), kept=kept)
        c, msl, _r, counts = PW.dump_rows(dump, plan, ss, (), lambda la, lo: 130.7, "",
                                          tol_m=0.02)
        return {x.index for x in c} | {m.index for m in msl}, counts
    landed = (types.SimpleNamespace(index=0, reason="authored_seat_lands"),)
    touched, counts = conv(landed)
    assert touched == set() and counts["authored_rows_kept"] == 1
    # the control: a keep for another reason (one body) still converts
    other = (types.SimpleNamespace(index=0, reason="one_body"),)
    assert conv(other)[0] == {0}


class _PlateStepDem(_Dem):
    """The upper ground falling 0.5 %, then 15 m down across 285-300 m (the
    plate's own step: the plate's inner edge at 290); ``early``: a genuine
    drop at 150 m too."""

    def __init__(self, early=False):
        super().__init__()
        self.early = early

    def z(self, x, y):
        z = 100.0 - 0.005 * max(y, 0.0) - 15.0 * min(1.0, max(0.0, (y - 285.0) / 15.0))
        return z - (20.0 if self.early and y > 150.0 else 0.0)


def test_the_plates_own_step_never_ends_the_safety_area(law):
    """Fix B (1): a drop whose crest stands at the plate's inner edge is the
    plate's own step — the end keeps the plate's inner edge; without the
    plate the same DEM ends the area at the crest.  A genuine drop before
    the plate still wins, and a side line just outside the plate's width
    reads the plate's corner (KSEA 16L: the end stopped at 275 m)."""
    plate = _record(inner=((-74.0, 290.0), (74.0, 290.0)))
    bare = types.SimpleNamespace(runways=(_runway(),), dem=_PlateStepDem(), walled_plates=())
    capped = types.SimpleNamespace(runways=(_runway(),), dem=_PlateStepDem(),
                                   walled_plates=(plate,))
    assert end_area_lengths(bare, law)["16/34"][0] < 290.0 - 1.0
    assert end_area_lengths(capped, law)["16/34"][0] == pytest.approx(290.0)
    early = types.SimpleNamespace(runways=(_runway(),), dem=_PlateStepDem(early=True),
                                  walled_plates=(plate,))
    assert end_area_lengths(early, law)["16/34"][0] < 160.0


def test_the_band_ends_at_the_plate_never_at_its_step(law):
    """Fix B (2) (3): the plateau of ``test_v2edge`` with a walled plate on
    its lip — the zone band is cut by the plate's footprint (no stand-off)
    and the plate's own step is not a crest, so the band reaches the plate.
    Without the plate the crest trims it a probe short (the control)."""
    from auto_patch_v2.classify.roles import Cell
    from auto_patch_v2.planar.zones import zone_regions
    from test_v2edge import PAV, _Dem as _Plateau
    cells = (Cell(0, "runway", "09/27", PAV, (), 4, None, "airside", "runway", {}),)
    foot = ((50.0, -200.0), (70.0, -200.0), (70.0, 200.0), (50.0, 200.0), (50.0, -200.0))
    plate = _record(footprint=foot, inner=((50.0, -200.0), (50.0, 200.0)))

    def reach(plates):
        regs = zone_regions(cells, law, (), _Plateau(drop=20.0), (), None, plates=plates)
        mid = [r.polygon.intersection(Polygon([(0, -100), (100, -100), (100, 100), (0, 100)]))
               for r in regs]
        return max(g.bounds[2] for g in mid if not g.is_empty)
    d = law.tables.emit.design
    assert reach(()) <= 50.0 - d.edge_probe_m + d.edge_grid_m      # the crest's trim
    assert reach((plate,)) == pytest.approx(50.0, abs=0.05)          # flush at the plate


def test_the_cap_under_the_plate_reads_the_nearest_station(law):
    """The under-plate ceiling is the DEM at the seat station NEAREST the
    vertex: the lowest station over the width sank KSEA's service roads
    4.3 m under their own ground."""
    class _Tilted(_Dem):
        def z(self, x, y):
            return 100.0 + 0.05 * x
    rec = _record(stations=((-80.0, 288.0), (80.0, 288.0)))
    pm = _planar({1: ((-60.0, 300.0), ["service_road"]), 2: ((60.0, 300.0), ["service_road"])})
    pm.plate_under = PG.under_plate_vertices(pm, (rec,))
    rows = {r.v: r.hi for r in under_plate_rows(pm, law, _airport(dem=_Tilted(), plates=(rec,)))
            if isinstance(r, Band)}
    assert rows[1] == pytest.approx(96.0 - 0.05) and rows[2] == pytest.approx(104.0 - 0.05)


def test_only_public_roads_are_cut_from_a_safety_area(law):
    """28p (1): the runway band's zone 2 yields its cut to every mapped road
    but an airport service road, which sits at grade on the safety area."""
    from auto_patch_v2.model.airport import OsmWay
    from auto_patch_v2.planar.road_yield import road_carriageways, rsa_carriageways
    ways = (OsmWay(1, "airport_small_roads", ((0.0, 0.0), (0.0, 50.0)), False,
                   {"highway": "service"}),
            OsmWay(2, "big_roads", ((10.0, 0.0), (10.0, 50.0)), False,
                   {"highway": "secondary"}))
    assert len(road_carriageways(ways, law)) == 2
    assert [ln.coords[0][0] for ln, _h in rsa_carriageways(ways, law)] == [10.0]


def test_a_service_road_through_the_safety_area_sits_at_grade():
    """28p (1), solved: #951's twin — a road along y = -30 through the
    runway band's zone 2 over ground 8 m BELOW the band (a 92 m cut through a
    ~99 m band).  The tertiary road of #951 is cut out and follows its
    ground; a SERVICE road is not cut, carries no yield record, and stands
    at the safety area's grade."""
    import dataclasses as _dc
    from test_band_road_cut951 import _band_vertices
    from test_roadmint100 import _way, _with
    from test_roadterrace100 import _solve
    from test_wall_step715 import ROAD, _road, _StepDem
    law = Law.for_airport("SYNT")
    a = _dc.replace(_with(_way(-3, ROAD, highway="service")), dem=_StepDem())
    pm, sol, _rep = _solve(a, law)
    road = _road(pm)
    assert road and not pm.road_yield
    assert road & _band_vertices(pm), "the service road is welded to the band"
    assert min(sol.z[v] for v in road) >= 98.0


def test_a_road_on_the_plate_ramps_to_no_dem():
    """A road vertex on the plate or on its inner edge is the plate's ground
    (its ceiling governs it), never a §37 (6) ramp to the DEM: that ramp at
    KSEA 16R's inner edge pulled the safety area 1.3 m under the plate."""
    on = PG.vertices_on_plates(
        {1: types.SimpleNamespace(xy=(0.0, 300.0)), 2: types.SimpleNamespace(xy=(0.0, 288.5)),
         3: types.SimpleNamespace(xy=(0.0, 250.0))}, (_record(),), 2.0)
    assert on == {1, 2}
    assert PG.vertices_on_plates({1: types.SimpleNamespace(xy=(0.0, 300.0))}, (), 2.0) == set()


def test_the_plate_is_the_step_between_the_safety_area_and_the_ground_it_hides(law):
    """A pair row from a vertex UNDER the plate to one outside it is
    withdrawn (a road drawn across the plate is two surfaces); a row
    between two vertices under it, or two outside, stays."""
    from auto_patch_v2.constraints.walled_plate import release_across
    from auto_patch_v2.model.constraints import Diff, Source
    pm = _planar({1: ((0.0, 300.0), ["service_road"]), 2: ((5.0, 305.0), ["service_road"]),
                  3: ((0.0, 280.0), ["service_road"]), 4: ((0.0, 270.0), ["service_road"])})
    src = Source("road_cross_section", "x", ())
    rows = [Diff(1, 3, 0.1, 20.0, src), Diff(1, 2, 0.1, 7.0, src), Diff(3, 4, 0.1, 10.0, src)]
    counts = {}
    kept = release_across(rows, pm, _airport(plates=(_record(),)), counts)
    assert [(r.a, r.b) for r in kept] == [(1, 2), (3, 4)] and counts["walled_plate_released"] == 1
    assert release_across(rows, pm, _airport()) == rows


def test_the_bending_does_not_reach_under_the_plate():
    """``solve/wall_cut``: every triangle edge from a vertex under the plate
    to one that is not is cut from the bending (the plate is the step)."""
    from auto_patch_v2.solve.wall_cut import wall_cut_edges
    pm = _planar({1: ((0.0, 300.0), ["service_road"]), 2: ((5.0, 305.0), ["service_road"]),
                  3: ((0.0, 280.0), ["graded_strip"])})
    pm.road_terrace = {}
    assert pm.plate_under == {1, 2}
    assert wall_cut_edges(pm, [(1, 2, 3)]) == {(1, 3), (2, 3)}


def test_the_walled_plates_datum_leads_its_connected_group():
    """#1201 (owner sim read 2026-10-28, KSEA 16L): a walled plate's bodies
    ride its datum (RULINGS 2026-10-27u) — the connected group's median zero
    (22o) sank 16L's plate 2.7 m under the safety area.  The control: the
    same record on a member that is not a walled plate takes the group zero."""
    from auto_patch_v2.airport import anchor_rule as AR
    from auto_patch_v2.airport import open_frame_seat as OFS
    from auto_patch_v2.airport.placement_record import Body, Split

    def body(i, zero, datum, pids):
        a = AR.Anchor(AR.OTHER, 47.0, -122.0, 0.5 if datum else 100.0 - zero,
                      "§16e walled plate" if datum else "§16g unit", 100.0 if not datum
                      else zero + 0.5, offset=(0.0, 0.0, 0.0), datum=datum)
        return Body(i, AR.OTHER, (i,), a, f"objects/p__b{i}.obj", pids=pids)
    rec = Split(0, "dsf:obj1", "objects/p.obj", "/x/objects/p.obj", 47.0, -122.0, 0.0,
                (body(0, 122.77, True, (1,)), body(1, 119.39, False, (2,))))
    pw = {1: ("fu:32:1", 120.09), 2: ("fu:32:1", 120.09)}
    zeros = {OFS.group_key("fu:32:1", "unit:1"): (120.09, 0.0)}
    walled = types.SimpleNamespace(resource="objects/p.obj", zero_y=0.0, plate_kind="walled")
    other = types.SimpleNamespace(resource="objects/p.obj", zero_y=0.0, plate_kind="")
    counts: dict = {}
    out = OFS.group_zero(rec, walled, pw, zeros, counts, "unit:1")
    z = [round(b.anchor.surface_z - b.anchor.y_zero, 2) for b in out.bodies]
    assert z == [122.77, 122.77] and counts["walled_plate_led_groups"] == 1
    ctl = OFS.group_zero(rec, other, pw, zeros, {}, "unit:1")
    assert [round(b.anchor.surface_z - b.anchor.y_zero, 2) for b in ctl.bodies] == [120.09, 120.09]
