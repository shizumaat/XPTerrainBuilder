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
from shapely.geometry import Point, Polygon

from auto_patch_v2.airport import ramp_feet as rf
from auto_patch_v2.airport.rebake_plan import _mpd
from auto_patch_v2.classify.ramp_runout import mint_ramp_runouts, runout_of
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.constraints.ramp_runout import RUNOUT_RULING, runout_rows
from auto_patch_v2.law import load_default
from auto_patch_v2.model.constraints import ConstraintSet

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
                  [(0, 8, 0, -20, 0.0, 5.0)]):          # a 25 % pitch
        part = _partition(tmp_path, quads)
        rf._MEMO.clear()
        assert rf.ramp_feet(types.SimpleNamespace(partition=part), law, to_xy) == ()


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
    c = cl.cells[-1]
    assert c.role == "service_road" and c.ref == "runout:0"
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
    assert rep == {"faces": 1, "rows": 2}
    rows = [r for r in cs.linears if r.source.ruling == RUNOUT_RULING]
    assert {r.terms[0][0] for r in rows} == {2, 3}
    # 80 m on at 5 % the ramp has come down the whole 4 m: the DEM
    assert all(r.lo == pytest.approx(10.0) for r in rows)



def test_a_landing_foot_keeps_its_collar(tmp_path, law):
    # 10-03e's landing under the foot: not yet run out (module NOT YET)
    from auto_patch_v2.classify.roles import Classification
    rf._MEMO.clear()
    part = _partition(tmp_path, [(0, 8, 0, -100, 0.0, 6.0)])
    ap = types.SimpleNamespace(partition=part, dem=_Dem(), frame=_frame())
    # the landing is a PLANAR pad region on the solved map, not a cell
    cl = Classification((), (), {}, ())
    xy = [(-4, -3), (12, -3), (12, 100), (-4, 100)]
    pm = types.SimpleNamespace(
        vertices={k: types.SimpleNamespace(xy=p) for k, p in enumerate(xy)},
        faces={0: types.SimpleNamespace(ref="building4/landing0", ring=(0, 1, 2, 3))},
        ring_vertices=lambda cyc: tuple(cyc))
    _cl, rep = mint_ramp_runouts(cl, ap, law, load_rules(), pm, {k: 14.0 for k in range(4)})
    assert rep["runouts"] == 0 and rep["landing"] == 1
