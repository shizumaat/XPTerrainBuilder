"""#2197 round 2 (``constraints/rim_pins``): a groundside face touching a
partial shell takes the author's ground -- under the sheet its sheet,
just outside the plan its rim stations -- as yielding groundside pins;
never an airside vertex, never an open edge, never under the shell's
buildings.  Synthetic map and shell, no corpus."""
from __future__ import annotations

import types

import numpy as np
import pytest
from auto_patch_v2.airport import ground_rim as GR
from auto_patch_v2.constraints import rim_pins as RP
from auto_patch_v2.constraints.gap_follow import reach_m
from auto_patch_v2.geom.terrain_deck import UNDER_M
from auto_patch_v2.law import Law
from auto_patch_v2.model.constraints import Pin
from auto_patch_v2.solve.design_roles import groundside_pin_rulings

LAW = Law.for_airport("KBNA")


def _pm(coords, faces):
    """A planar map of ``(role, ref, ring)`` faces; an edge with one face
    is an OPEN edge of the patch."""
    eid, ends = {}, {}
    fs = {}
    for i, (role, ref, ring) in enumerate(faces):
        n = len(ring)
        cyc = []
        for k in range(n):
            a, b = ring[k], ring[(k + 1) % n]
            key = frozenset((a, b))
            if key not in eid:
                eid[key] = 1000 + len(eid)
                ends[eid[key]] = types.SimpleNamespace(a=a, b=b, left_face=i, right_face=None)
            else:
                ends[eid[key]].right_face = i
            cyc.append(eid[key])
        fs[i] = types.SimpleNamespace(id=i, role=role, ref=ref, holes=(), ring=tuple(cyc))
    return types.SimpleNamespace(
        vertices={i: types.SimpleNamespace(xy=xy, dem_z=100.0) for i, xy in enumerate(coords)},
        faces=fs, edges=ends,
        ring_vertices=lambda cyc: tuple(dict.fromkeys(v for e in cyc for v in (ends[e].a,
                                                                                ends[e].b))))


def _shell(x0=1000.0, y0=2000.0):
    """A 60 x 40 m shell at ``(x0, y0)``: its sheet at 110 + 0.1 e, a
    building (no sheet) over its middle 10 x 10 m."""
    step = 1.0
    e = np.arange(-30, 30) + 0.5
    z = np.tile(110.0 + 0.1 * e, (40, 1))
    z[15:25, 25:35] = np.nan
    ring = np.array([(-30, -20), (30, -20), (30, 20), (-30, 20), (-30, -20)], float)
    rim = [(ee, nn) for ee in e for nn in (-19.5, 19.5)] + \
        [(ee, nn) for ee in (-29.5, 29.5) for nn in np.arange(-20, 20) + 0.5]
    st = np.array([(a, b, 110.0 + 0.1 * a) for a, b in rim], float)
    rs = GR._RimSet((x0, y0), 0.0, 105.0, 60.0, 0.9, 1.0, 6.0, st, (ring,),
                    sheet=(-30.0, -20.0, step, z))
    return rs, types.SimpleNamespace(terrain_models=(
        ("a", "lot.obj", types.SimpleNamespace(id="a", rim=rs), 0.0),
        ("b", "lot2.obj", types.SimpleNamespace(id="a", rim=rs), 0.0)))


def _rows(pm, airport):
    return {r.v: r.z for r in RP.rim_pins(pm, LAW, airport) if isinstance(r, Pin)}


def test_a_lot_under_the_sheet_takes_the_authors_ground():
    x0, y0 = 1000.0, 2000.0
    _rs, ap = _shell(x0, y0)
    # a lot inside the plan (0..3) inside a groundside ring (4..7, open edges)
    c = [(x0 - 20, y0 - 10), (x0 - 10, y0 - 10), (x0 - 10, y0 + 10), (x0 - 20, y0 + 10),
         (x0 - 25, y0 - 15), (x0 - 5, y0 - 15), (x0 - 5, y0 + 15), (x0 - 25, y0 + 15)]
    pm = _pm(c, [("parking_lot", "lot1", (0, 1, 2, 3)),
                 ("parking_lot", "lot2", (4, 5, 6, 7, 4, 0, 3, 2, 1, 0))])
    got = _rows(pm, ap)
    for v in (0, 1, 2, 3):
        assert got[v] == pytest.approx(110.0 + 0.1 * (c[v][0] - x0 + 0.5) - UNDER_M, abs=0.11)
    assert not set(got) & {4, 5, 6, 7}            # the patch's open edge


def test_beside_the_rim_the_stations_beyond_the_reach_nothing():
    x0, y0 = 1000.0, 2000.0
    rs, _ap = _shell(x0, y0)
    r = reach_m(LAW)
    xy = np.array([(x0 + 30 + 0.5 * r, y0), (x0 + 30 + 2 * r, y0), (x0 - 10, y0 - 5)])
    t = RP._targets(rs, xy, r)
    assert t[0] == pytest.approx(110.0 + 0.1 * 29.5 - UNDER_M, abs=0.05)
    assert np.isnan(t[1])                          # beyond the stand-off reach
    assert t[2] == pytest.approx(110.0 + 0.1 * -9.5 - UNDER_M, abs=1e-9)   # its sheet


def test_never_an_airside_vertex_nor_under_a_building():
    x0, y0 = 1000.0, 2000.0
    _rs, ap = _shell(x0, y0)
    c = [(x0, y0 - 2), (x0 + 3, y0 - 2), (x0 + 3, y0 + 2), (x0, y0 + 2),
         (x0 - 15, y0 - 10), (x0 - 12, y0 - 10), (x0 - 12, y0 - 6), (x0 - 15, y0 - 6),
         (x0 - 40, y0 - 40), (x0 + 40, y0 - 40), (x0 + 40, y0 + 40), (x0 - 40, y0 + 40)]
    pm = _pm(c, [("parking_lot", "under_building", (0, 1, 2, 3)),
                 ("apron", "a", (4, 5, 6, 7)),
                 ("parking_lot", "l", (5, 6, 7, 4)),
                 ("graded_strip", "g", (8, 9, 10, 11))])
    got = _rows(pm, ap)
    assert not set(got) & {0, 1, 2, 3}             # the building covers them
    assert not set(got) & {4, 5, 6, 7}             # airside is king


def test_no_partial_shell_no_rows_and_the_pin_is_groundside_and_yields():
    pm = _pm([(0, 0), (1, 0), (1, 1)], [("parking_lot", "l", (0, 1, 2))])
    assert RP.rim_pins(pm, LAW, types.SimpleNamespace(terrain_models=())) == []
    assert RP.RULING in groundside_pin_rulings(LAW)
    from auto_patch_v2.law.tables import design as design_law
    assert RP.RULING in design_law(LAW).yielding_pin_rulings
