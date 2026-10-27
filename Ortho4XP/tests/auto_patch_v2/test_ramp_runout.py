"""Issue #669 twin: THE RAMP FOOT RUNS OUT AT ROAD GRADE TO RAW DEM (owner
RULINGS 2026-10-14c (5)).

KCLT's departures ramp came down to its zero over pack pavement graded up
to it; beyond the patch the raw DEM stood 4 m lower — a cliff.  The foot is
read off the ramp object's own top surface (``airport/ramp_feet``), the
strip is minted in the last stage off the patch's edge
(``classify/ramp_runout``) and graded at the design grade from the patch's
level there to the DEM (``constraints/ramp_runout``).
"""
from __future__ import annotations

import types

import numpy as np
import pytest
from auto_patch_v2.airport import ramp_feet as rf
from auto_patch_v2.airport.rebake_plan import _mpd
from auto_patch_v2.classify.ramp_runout import mint_ramp_runouts, runout_of
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.constraints.ramp_runout import RUNOUT_RULING, runout_rows
from auto_patch_v2.law import load_default
from auto_patch_v2.model.constraints import ConstraintSet
from shapely.geometry import Point, Polygon

LAT0, LON0 = 10.0, 20.0
ML, MO = _mpd(LAT0)


def to_xy(lon, lat):
    return ((lon - LON0) * MO, (lat - LAT0) * ML)


def ll(e, n):
    return (LAT0 + n / ML, LON0 + e / MO)


def _obj(path, quads):
    """An OBJ8 of quads ``[(x0, x1, z0, z1, y0, y1)]`` (``y`` from ``y0`` at
    ``z0`` to ``y1`` at ``z1``; OBJ8 ``z`` points south)."""
    vt, idx = [], []
    for x0, x1, z0, z1, y0, y1 in quads:
        b = len(vt)
        vt += [(x0, y0, z0), (x1, y0, z0), (x1, y1, z1), (x0, y1, z1)]
        idx += [b, b + 1, b + 2, b, b + 2, b + 3]
    lines = ["I", "800", "OBJ", f"POINT_COUNTS {len(vt)} 0 0 {len(idx)}"]
    lines += [f"VT {x} {y} {z} 0 1 0 0 0" for x, y, z in vt]
    lines += [f"IDX {i}" for i in idx]
    lines += [f"TRIS 0 {len(idx)}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return str(path)


def _partition(tmp_path, quads, e0=0.0, e1=8.0, n0=0.0, n1=100.0, kind="flag"):
    path = _obj(tmp_path / "ramp.obj", quads)
    ring = (ll(e0, n0), ll(e1, n0), ll(e1, n1), ll(e0, n1), ll(e0, n0))
    m = types.SimpleNamespace(resource="ramp.obj", heading_deg=0.0, origin=(LAT0, LON0),
                              live_path=path, authored_path=path, deck_kind=kind,
                              elevated_deck=False,
                              parts=(types.SimpleNamespace(rings=(ring,), base_y=0.0),))
    unit = types.SimpleNamespace(id="unit:0", anchor=(LAT0, LON0), members=(m,))
    return types.SimpleNamespace(units=(unit,))


@pytest.fixture
def law():
    return load_default()


def test_the_foot_of_a_ramp_and_its_direction_of_travel(tmp_path, law):
    # an 8 m wide deck climbing 6 m north over 100 m: its foot is its
    # south end, travel off it runs south
    part = _partition(tmp_path, [(0, 8, 0, -100, 0.0, 6.0)])
    feet = rf.ramp_feet(types.SimpleNamespace(partition=part), law, to_xy)
    assert len(feet) == 1
    f = feet[0]
    assert f.direction[1] == pytest.approx(-1.0, abs=0.02)
    assert abs(f.lip[0] - 4.0) <= 1.0 and abs(f.lip[1]) <= 2.0
    assert 7.0 <= f.width_m <= 11.0
    assert f.climb_m >= 5.0 and abs(f.y_foot) <= 0.5


def test_a_slab_a_roof_and_a_steep_pitch_are_not_ramps(tmp_path, law):
    for quads in ([(0, 8, 0, -100, 0.0, 0.0)],          # a slab at its zero
                  [(0, 8, 0, -100, 5.0, 11.0)],         # a deck never down to zero
                  [(0, 8, 0, -20, 0.0, 6.0)]):          # a 30 % pitch: over any authored ramp
        part = _partition(tmp_path, quads)
        rf._MEMO.clear()
        assert rf.ramp_feet(types.SimpleNamespace(partition=part), law, to_xy) == ()


def test_a_steep_authored_ramp_has_a_foot(tmp_path, law):
    # issue #711: HECA's T3 viaduct's south ramp comes down at 14.2 %, over
    # the sunken-ramp step grade (12 %) — read as no ramp, its foot got no
    # run-out.  A deck ramp is read up to the pack's authored bound
    # (``[cutout.wall_corridor] max_authored_grade``).
    part = _partition(tmp_path, [(0, 8, 0, -50, 0.0, 7.0)])     # 14 %
    rf._MEMO.clear()
    feet = rf.ramp_feet(types.SimpleNamespace(partition=part), law, to_xy)
    assert len(feet) == 1
    assert feet[0].direction[1] == pytest.approx(-1.0, abs=0.02)
    assert feet[0].climb_m >= 5.0


def test_a_member_that_is_no_deck_is_not_read(tmp_path, law):
    part = _partition(tmp_path, [(0, 8, 0, -100, 0.0, 6.0)], kind="")
    rf._MEMO.clear()
    assert rf.ramp_feet(types.SimpleNamespace(partition=part), law, to_xy) == ()


class _Dem:
    def z(self, x, y):
        return 10.0


def _frame():
    def to_ll(x, y):
        return (LAT0 + y / ML, LON0 + x / MO)
    return types.SimpleNamespace(entry=lambda: to_xy,
                                 transformers=lambda: (to_xy, to_ll))


def _cell(i, role, ref, poly):
    from auto_patch_v2.classify.roles import Cell
    return Cell(i, role, ref, tuple(poly.exterior.coords)[:-1], (), None, None,
                "groundside", role, {})


def _mint(tmp_path, law, ground_end_n=-3.0, level=14.0):
    rf._MEMO.clear()
    part = _partition(tmp_path, [(0, 8, 0, -100, 0.0, 6.0)])
    ap = types.SimpleNamespace(partition=part, dem=_Dem(), frame=_frame())
    # the pavement graded up under the ramp: to 3 m beyond its foot
    pav = Polygon([(-4, ground_end_n), (12, ground_end_n), (12, 100), (-4, 100)])
    from auto_patch_v2.classify.roles import Classification
    cl = Classification((_cell(0, "groundside_pavement", "gap:0", pav),), (), {}, ())
    # the base map's solved level along the pavement's south edge
    pm = types.SimpleNamespace(vertices={
        k: types.SimpleNamespace(xy=(x, ground_end_n))
        for k, x in enumerate(np.linspace(-4, 12, 9))})
    z = {k: level for k in pm.vertices}
    return mint_ramp_runouts(cl, ap, law, load_rules(), pm, z)


def test_a_graded_foot_runs_out_to_raw_dem(tmp_path, law):
    cl, rep = _mint(tmp_path, law)
    assert rep["runouts"] == 1, rep
    c = next(c for c in cl.cells if c.ref == "runout:0")
    assert c.role == "service_road"
    assert c.evidence["pad_road"]
    q = Polygon(c.ring)
    x0, y0, dx, dy, z0, dem0 = runout_of(c)
    assert z0 == pytest.approx(14.0) and dem0 == pytest.approx(10.0)
    assert dy == pytest.approx(-1.0, abs=0.02)
    # it starts where the patch ends and runs |dz| / 5 % = 80 m on south,
    # the ramp's width wide
    g = float(law.tables.emit.road_contact.ramp_grade)
    assert q.bounds[3] == pytest.approx(-3.0, abs=0.05)
    assert q.bounds[1] == pytest.approx(-3.0 - 4.0 / g, abs=1.5)
    assert 7.0 <= q.bounds[2] - q.bounds[0] <= 11.0
    assert not q.intersects(Point(4, 0))          # nothing standing taken


def test_a_foot_at_grade_asks_nothing(tmp_path, law):
    cl, rep = _mint(tmp_path, law, level=10.2)
    assert rep["runouts"] == 0 and rep["at_grade"] == 1


def test_a_foot_no_pavement_holds_is_not_graded(tmp_path, law):
    cl, rep = _mint(tmp_path, law, ground_end_n=30.0)
    assert rep["runouts"] == 0 and rep["ungraded"] == 1


class _Planar:
    """A one-face map: the run-out strip's four corners."""

    def __init__(self, xy, dem):
        self.vertices = {k: types.SimpleNamespace(xy=p, dem_z=dem, incident_faces=(0,))
                         for k, p in enumerate(xy)}
        self.faces = {0: types.SimpleNamespace(id=0, ref="runout:0", role="service_road",
                                               ring=(0, 1, 2, 3), holes=())}
        self.ramp_runouts = {"runout:0": (4.0, -3.0, 0.0, -1.0, 14.0, 10.0)}

    def ring_vertices(self, cycle):
        return tuple(cycle)


def test_the_runout_rows_lay_the_design_grade_to_the_dem(law):
    pm = _Planar([(0, -3), (8, -3), (8, -83), (0, -83)], 10.0)
    cs, rep = runout_rows(pm, law, ConstraintSet(), levels={0: 14.0, 1: 14.0})
    assert rep == {"faces": 1, "rows": 2, "bank_faces": 0, "bank_rows": 0}
    rows = [r for r in cs.linears if r.source.ruling == RUNOUT_RULING]
    assert {r.terms[0][0] for r in rows} == {2, 3}
    # 80 m on at 5 % the ramp has come down the whole 4 m: the DEM
    assert all(r.lo == pytest.approx(10.0) for r in rows)


def test_the_strip_sides_carry_matching_stations(tmp_path, law):
    # #1093: a profile and its cross-fall are only what the ring's vertices
    # hold — both sides take a vertex at the same stations, STATION_M apart
    from auto_patch_v2.classify.ramp_runout import STATION_M
    cl, rep = _mint(tmp_path, law)
    ring = next(c for c in cl.cells if c.ref == "runout:0").ring
    sides = [sorted(round(y, 1) for x, y in ring if (x < 4.0) == west) for west in (True, False)]
    assert sides[0] == sides[1] and len(sides[0]) > 2
    assert max(b - a for a, b in zip(sides[0][:-1], sides[0][1:], strict=True)) <= STATION_M + 0.5


class _Tilted:
    """A ground falling 10 % across the strip (east up)."""

    def z(self, x, y):
        return 10.0 + 0.1 * (x - 4.0)


def test_the_runout_rows_read_the_axis_ground(law):
    # #1093: the two sides at one station take ONE target, off the axis's
    # ground — never each side's own, which the cross-fall cap contests
    pm = _Planar([(0, -3), (8, -3), (8, -43), (0, -43)], 10.0)
    pm.vertices[2].dem_z, pm.vertices[3].dem_z = 10.4, 9.6
    cs, _rep = runout_rows(pm, law, ConstraintSet(), levels={0: 14.0, 1: 14.0},
                           dem=_Tilted())
    lo = {r.terms[0][0]: r.lo for r in cs.linears if r.source.ruling == RUNOUT_RULING}
    assert lo[2] == pytest.approx(lo[3])


def test_a_road_ramp_row_on_a_ramp_foot_runout_is_withdrawn(law):
    # #1093: the run-out's own rows are its vertices' road-grade profile;
    # the §37 target off the DEM held KCLT's strip 1.9 m under it
    from auto_patch_v2.constraints import road_ramp
    from auto_patch_v2.constraints.ramp_runout import runout_exempt
    from auto_patch_v2.model.constraints import Linear, Source
    pm = _Planar([(0, -3), (8, -3), (8, -83), (0, -83)], 10.0)
    pm.registries = types.SimpleNamespace(landing_runouts={})
    on = Linear(((2, 1.0),), 9.0, 9.0, Source(road_ramp.GEN, road_ramp.RULING, ("vertex:2",)))
    off = Linear(((7, 1.0),), 9.0, 9.0, Source(road_ramp.GEN, road_ramp.RULING, ("vertex:7",)))
    rows, n = runout_exempt([on, off], pm)
    assert n == 1 and rows == [off]


def test_a_landing_foot_keeps_its_collar(tmp_path, law):
    # 10-03e's landing under the foot: not yet run out (module NOT YET)
    from auto_patch_v2.classify.roles import Classification
    rf._MEMO.clear()
    part = _partition(tmp_path, [(0, 8, 0, -100, 0.0, 6.0)])
    ap = types.SimpleNamespace(partition=part, dem=_Dem(), frame=_frame())
    cl = Classification((), (), {}, ())
    xy = [(-4, -3), (12, -3), (12, 100), (-4, 100)]
    pm = types.SimpleNamespace(
        vertices={k: types.SimpleNamespace(xy=p) for k, p in enumerate(xy)},
        faces={0: types.SimpleNamespace(ref="building4/landing0", ring=(0, 1, 2, 3))},
        ring_vertices=lambda cyc: tuple(cyc))
    _cl, rep = mint_ramp_runouts(cl, ap, law, load_rules(), pm, {k: 14.0 for k in range(4)})
    assert rep["runouts"] == 0 and rep["landing"] == 1


# --- lane lramp2 (#669 / #1093): the foot leads its run-out, and the run-out
# ends on the ground (``docs/findings/kclt-ramp-lramp2.md``)

def test_the_strip_is_banked_to_its_daylight_line(tmp_path, law):
    # R3 (20aw trial, 20ay "no visible edge"): the strip stands 4 m over a
    # flat DEM where it leaves the patch and meets it 80 m on; its sides are
    # banked at 1:3 to where that slope meets the ground — 12 m out at the
    # start, nothing where the strip is down on its DEM
    from auto_patch_v2.classify.ramp_runout import BANK_EVIDENCE
    cl, rep = _mint(tmp_path, law)
    banks = [c for c in cl.cells if c.ref == "runout:0#collar"]
    assert banks and rep["banks"] == len(banks)
    assert all(c.role == "building" and c.evidence[BANK_EVIDENCE] for c in banks)
    strip = Polygon(next(c for c in cl.cells if c.ref == "runout:0").ring)
    bank = Polygon(banks[0].ring)
    for c in banks[1:]:
        bank = bank.union(Polygon(c.ring))
    k = float(law.tables.emit.design.bank_slope)
    x0 = strip.bounds[0]
    # beside the strip's start, the bank runs out to 4 / k metres
    near = bank.intersection(Polygon([(x0 - 30, -6), (x0, -6), (x0, -4), (x0 - 30, -4)]))
    assert near.bounds[0] == pytest.approx(x0 - 4.0 / k, abs=1.5)
    # near its end the strip is on its DEM: the bank has all but closed
    far = bank.intersection(Polygon([(x0 - 30, -80), (x0, -80), (x0, -78), (x0 - 30, -78)]))
    assert far.is_empty or far.bounds[0] >= x0 - 1.5
    assert not bank.intersects(Point(4, 0))      # nothing standing taken


class _BankPlanar(_Planar):
    """The strip and its bank: a toe vertex 9 m west of the strip's start."""

    def __init__(self):
        super().__init__([(0, -3), (8, -3), (8, -83), (0, -83)], 10.0)
        self.vertices[4] = types.SimpleNamespace(xy=(-9.0, -3.0), dem_z=10.0,
                                                 incident_faces=(1,))
        self.vertices[5] = types.SimpleNamespace(xy=(-30.0, -40.0), dem_z=10.0,
                                                 incident_faces=(1,))
        self.vertices[0].incident_faces = (0, 1)
        self.vertices[3].incident_faces = (0, 1)
        self.faces[1] = types.SimpleNamespace(id=1, ref="runout:0#collar", role="building",
                                              ring=(0, 4, 5, 3), holes=())
        self.edges = {}


def test_the_bank_lies_on_its_slope_to_the_ground(law):
    # R3's rows: a bank vertex takes its own ground, clamped into the 1:3
    # cone off the nearest point of its strip (here the start, at 14 m)
    from auto_patch_v2.constraints.ramp_runout import BANK_RULING
    pm = _BankPlanar()
    cs, rep = runout_rows(pm, law, ConstraintSet(), levels={0: 14.0, 1: 14.0}, dem=_Dem())
    assert rep["bank_faces"] == 1 and rep["bank_rows"] == 2
    lo = {r.terms[0][0]: r.lo for r in cs.linears if r.source.ruling == BANK_RULING}
    k = float(law.tables.emit.design.bank_slope)
    assert lo[4] == pytest.approx(max(10.0, 14.0 - 9.0 * k))    # 9 m out: 11 m
    assert lo[5] == pytest.approx(10.0)                          # past daylight: its DEM
    # the strip's own vertices shared with its bank keep their profile rows
    on = {r.terms[0][0] for r in cs.linears if r.source.ruling == RUNOUT_RULING}
    assert 3 in on


class _RoadPlanar:
    """A mapped road leaving a ramp foot (lip (4, 0), travel south): its
    vertices 6 m behind the lip, at the lip's patch edge 3 m on, and 40 m
    and 100 m on."""

    def __init__(self):
        ys = (6.0, -3.0, -40.0, -100.0)
        self.vertices = {k: types.SimpleNamespace(xy=(4.0, y), dem_z=10.0, incident_faces=(0,))
                         for k, y in enumerate(ys)}
        self.faces = {0: types.SimpleNamespace(id=0, ref="big_roads:-1", role="service_road",
                                               ring=(0, 1, 2, 3), holes=())}
        self.ramp_runouts = {}
        self.pad_roads = frozenset()

    def ring_vertices(self, cycle):
        return tuple(cycle)


def _foot_ap(tmp_path):
    rf._MEMO.clear()
    part = _partition(tmp_path, [(0, 8, 0, -100, 0.0, 6.0)])
    return types.SimpleNamespace(partition=part, dem=_Dem(), frame=_frame())


def test_a_mapped_road_ahead_of_the_foot_carries_its_runout(tmp_path, law, monkeypatch):
    # R1 + R2 (RULINGS 2026-10-14i): KCLT's departures roadway — mapped
    # ahead of the ramp's foot — held the ground at the lip 2.5 m under the
    # deck.  The road starts AT the foot's level and comes down at the design
    # grade until it meets the DEM; its §37 rows there are withdrawn
    from auto_patch_v2.constraints import foot_road as rr
    from auto_patch_v2.constraints import road_ramp
    from auto_patch_v2.model.constraints import Linear, Source
    monkeypatch.setattr(rr, "foot_levels", lambda pm, law, ap, feet, lv: [14.0] * len(feet))
    monkeypatch.setattr(rr, "_on_landing", lambda pm, lip, reach: False)
    ap, pm = _foot_ap(tmp_path), _RoadPlanar()
    r37 = Linear(((2, 1.0),), 9.0, 9.0, Source(road_ramp.GEN, road_ramp.RULING, ("vertex:2",)))
    cs, rep = rr.foot_road_rows(pm, law, ConstraintSet.from_rows([r37]), {}, ap,
                                rf.ramp_feet(ap, law, to_xy), back_m=rf.FOOT_SPAN_M,
                                max_run_m=400.0)
    assert rep["roads"] == 1 and rep["withdrawn"] == 1
    lo = {r.terms[0][0]: r.lo for r in cs.linears if r.source.ruling == rr.FOOT_ROAD_RULING}
    g = float(law.tables.emit.road_contact.ramp_grade)
    lip_n = rf.ramp_feet(ap, law, to_xy)[0].lip[1]
    assert lo[0] == pytest.approx(14.0)                       # under the ramp: the foot
    assert lo[1] == pytest.approx(14.0 - g * (lip_n + 3.0), abs=0.06)
    assert lo[2] == pytest.approx(14.0 - g * (lip_n + 40.0), abs=0.06)
    assert 3 not in lo                                        # past the meeting: its own law
    assert r37 not in list(cs.rows())


def test_a_foot_with_no_seat_constant_leaves_the_road(tmp_path, law, monkeypatch):
    from auto_patch_v2.constraints import foot_road as rr
    monkeypatch.setattr(rr, "foot_levels", lambda pm, law, ap, feet, lv: [None] * len(feet))
    ap = _foot_ap(tmp_path)
    cs, rep = rr.foot_road_rows(_RoadPlanar(), law, ConstraintSet(), {}, ap,
                                rf.ramp_feet(ap, law, to_xy), back_m=rf.FOOT_SPAN_M,
                                max_run_m=400.0)
    assert rep["no_level"] == 1 and rep["rows"] == 0


def test_the_foot_level_is_its_units_seat_on_a_flat_held_pad(tmp_path, law, monkeypatch):
    # R1: the unit's origin sits on the pad under its anchor; the foot is
    # the deck's authored y above it
    from auto_patch_v2.constraints import foot_road as rr
    from auto_patch_v2.constraints import platform
    from auto_patch_v2.model import platform as mplat
    ap = _foot_ap(tmp_path)
    feet = rf.ramp_feet(ap, law, to_xy)
    xy = [(-20, -20), (20, -20), (20, 20), (-20, 20)]
    pm = types.SimpleNamespace(
        vertices={k: types.SimpleNamespace(xy=p) for k, p in enumerate(xy)},
        faces={0: types.SimpleNamespace(ref="building1", ring=(0, 1, 2, 3), role="building")},
        ring_vertices=lambda cyc: tuple(cyc))
    monkeypatch.setattr(platform, "flat_held_refs", lambda pm, law: frozenset({"building1"}))
    monkeypatch.setattr(mplat, "datum_vertices", lambda pm, law: {"building1": 2})
    got = rr.foot_levels(pm, law, ap, feet, {2: 30.0})
    assert got == [pytest.approx(30.0 + feet[0].y_foot)]
    assert rr.foot_levels(pm, law, ap, feet, {}) == [None]      # not a constant here


def test_a_strip_beside_its_carrying_road_is_that_roads_shoulder(law):
    # R2/R3: the strips beside the road that carries the run-out ride the
    # road's level (its lead), not their own DEM-closing profile: KCLT's
    # held 1.5-2.3 m over it where the road ran on to a raised junction
    from auto_patch_v2.geom.ramp_profile import lead_section, strip_level
    g = float(law.tables.emit.road_contact.ramp_grade)

    def ground(s):
        return 10.0
    lead = lead_section([(0.0, 14.0), (0.4, 14.0), (60.0, 13.0)])
    assert len(lead) == 2
    assert strip_level(30.0, 14.0, 10.0, ground, g, lead) == pytest.approx(13.5, abs=0.01)
    # past the lead's end, the ramp law off its last station
    assert strip_level(70.0, 14.0, 10.0, ground, g, lead) == pytest.approx(13.0 - g * 10.0)
    # no lead: the strip's own profile off its start
    assert strip_level(30.0, 14.0, 10.0, ground, g) == pytest.approx(14.0 - g * 30.0)


def test_the_runout_rows_ride_a_standing_road_beside_the_strip(law):
    pm = _Planar([(0, -3), (8, -3), (8, -83), (0, -83)], 10.0)
    # a mapped road shares the strip's east side, standing at 13.5 -> 12.0
    pm.faces[1] = types.SimpleNamespace(id=1, ref="big_roads:-1", role="service_road",
                                        ring=(1, 2), holes=())
    pm.vertices[1].incident_faces = (0, 1)
    pm.vertices[2].incident_faces = (0, 1)
    cs, _rep = runout_rows(pm, law, ConstraintSet(), levels={0: 14.0, 1: 13.5, 2: 12.0},
                           dem=_Dem())
    lo = {r.terms[0][0]: r.lo for r in cs.linears if r.source.ruling == RUNOUT_RULING}
    assert lo == {3: pytest.approx(12.0)}      # the road's level at the far station


def test_a_bank_node_on_a_standing_edge_stands_on_it(law):
    # a bank node the arrangement notched beside the apron's edge takes the
    # apron edge's level there, not its DEM (KCLT: four mid-edge steps of
    # 0.95-2.38 m against the apron ``pav14``)
    from auto_patch_v2.constraints.ramp_runout import BANK_RULING
    pm = _BankPlanar()
    pm.vertices[6] = types.SimpleNamespace(xy=(-30.0, -10.0), dem_z=10.0, incident_faces=(2,))
    pm.vertices[7] = types.SimpleNamespace(xy=(-30.0, -70.0), dem_z=10.0, incident_faces=(2,))
    pm.faces[2] = types.SimpleNamespace(id=2, ref="pav1", role="apron", ring=(6, 7), holes=())
    pm.vertices[5].xy = (-30.05, -40.0)                  # 5 cm off the apron's edge
    pm.edges = {0: types.SimpleNamespace(a=6, b=7, left_face=2, right_face=None)}
    cs, _rep = runout_rows(pm, law, ConstraintSet(),
                           levels={0: 14.0, 1: 14.0, 6: 13.0, 7: 12.0}, dem=_Dem())
    lo = {r.terms[0][0]: r.lo for r in cs.linears if r.source.ruling == BANK_RULING}
    assert lo[5] == pytest.approx(12.5, abs=0.01)
