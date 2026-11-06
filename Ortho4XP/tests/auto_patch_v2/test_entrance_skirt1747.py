"""Twin for #1747's ENTRANCE SKIRT (owner RULINGS 2026-11-06c (3) and its
17:37Z clarification; ``planar/entrance_skirt``, ``constraints/
entrance_skirt``): an entrance face's ramp ends at the face's FRONT, and the
ground under and within ``[tunnel.object] entrance_skirt_m`` of its top is
held at that top, falling to the DEM beyond at ``emit.design.bank_slope``.
On a slope the face's edges come out flush; on flat ground nothing but the
plan changes (the top IS the ground, no bank).  Synthetic bore and DEM; law
values read from the tables."""
from __future__ import annotations

import dataclasses as _dc

import pytest
from auto_patch_v2.airport.portal_objects import Portal
from auto_patch_v2.classify.roles import Classification
from auto_patch_v2.constraints.entrance_skirt import skirt_pins
from auto_patch_v2.law import Law
from auto_patch_v2.planar.entrance_skirt import face_front_mouth
from auto_patch_v2.planar.structures import build_structures
from shapely.geometry import LineString, Point, Polygon, box
from test_mouth_at_pavement971 import _airport as _bore_airport
from test_mouth_at_pavement971 import _base_cells, _FlatDem


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


class _SlopeDem:
    """700 m on the bore's axis, falling 0.25 m per metre north."""
    provenance = {"synthetic": "north slope"}

    def z(self, x: float, y: float) -> float:
        return 700.0 - 0.25 * y

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


_PLANS = {1: box(-66.0, -14.0, -60.0, 14.0), 2: box(60.0, -14.0, 66.0, 14.0)}


def _portals(top: float):
    """Each mouth's entrance face: a 6 m-deep top across the bore standing
    OUT of the mapped end (x = +-60), its back on the end."""
    return [Portal(f"dsf:obj{i}", "objects/entrance.obj", (x, 0.0), -101, 6.0, 0.0,
                   (x, 0.0), floor_z=top - 5.5, opening_m=12.0, bottom_y=-5.0,
                   face_plan=_PLANS[i], face_top_z=top)
            for i, x in ((1, -60.0), (2, 60.0))]


def _build(law, dem, top):
    airport = _dc.replace(_bore_airport(law), dem=dem)
    return build_structures(airport, Classification(tuple(_base_cells()), (), {}, ()),
                            law, portals=_portals(top))


def test_the_mouth_stands_at_the_faces_front():
    """The mapped end at the face's back: the axis is cut back to its front;
    a mapped end short of the face runs on to it."""
    axis = LineString([(60.0, 0.0), (300.0, 0.0)])
    ln, moved = face_front_mouth(axis, (-1.0, 0.0), _PLANS[2], 6.0)
    assert moved == pytest.approx(-6.0) and ln.coords[0] == pytest.approx((66.0, 0.0))
    ln, moved = face_front_mouth(axis, (-1.0, 0.0), box(50.0, -14.0, 56.0, 14.0), 6.0)
    assert moved == pytest.approx(4.0) and ln.coords[0] == pytest.approx((56.0, 0.0))


def test_a_mouth_on_a_slope_gets_a_skirt_at_its_top(law):
    ob = law.tables.structures.tunnel.object
    cl, tunnels, st = _build(law, _SlopeDem(), 703.5)
    assert len(tunnels) == 2, st.refused
    cores = {c.ref: Polygon(c.ring, c.holes) for c in cl.cells
             if c.ref.startswith("entrance_skirt:")}
    for tn in tunnels:
        top, core_ref, _bank_ref = tn.entrance_skirt
        assert top == pytest.approx(703.5)
        core = cores[core_ref]
        plan = _PLANS[2] if tn.axis[0][0] > 0 else _PLANS[1]
        # the face's top beside the ramp's own wall stand-off, and its band
        assert core.intersection(plan).area >= 0.4 * plan.area
        assert core.contains(Point(plan.centroid.x, 13.0))
        assert core.contains(Point(plan.centroid.x, 14.0 + float(ob.entrance_skirt_m) - 0.5))
        assert abs(tn.axis[0][0]) == pytest.approx(66.0, abs=0.5)       # the front
    banks = [Polygon(c.ring) for c in cl.cells if c.ref.startswith("entrance_bank:")]
    # the bank falls to the DEM: up to 3.5 + 0.25 * 17 m of relief at 1:bank_slope
    assert banks and max(p.bounds[3] for p in banks) > 14.0 + float(ob.entrance_skirt_m) + 1.0
    # neither piece is a rim (the object stage would read the entrance as a basin's)
    assert not any(c.role == "retaining_wall" and c.ref.startswith("entrance_")
                   for c in cl.cells)


def test_a_mouth_on_flat_ground_has_no_bank(law):
    ob = law.tables.structures.tunnel.object
    cl, tunnels, st = _build(law, _FlatDem(), 700.0)
    assert len(tunnels) == 2, st.refused
    pieces = [Polygon(c.ring) for c in cl.cells if c.ref.startswith("entrance_")]
    # the skirt's level piece only: no bank, nothing past the band
    assert pieces and not any(c.ref.startswith("entrance_bank:") for c in cl.cells)
    assert max(p.bounds[3] for p in pieces) <= 14.0 + float(ob.entrance_skirt_m) + 0.1
    assert all(tn.entrance_skirt[0] == pytest.approx(700.0) for tn in tunnels)


class _V:
    def __init__(self, xy):
        self.xy = xy


class _F:
    def __init__(self, role, ring=()):
        self.role, self.ring = role, tuple(ring)


def test_the_skirt_pins_its_level_piece_at_the_top_and_its_bank_at_the_dem(law):
    """A level-piece vertex takes the face's top, a bank vertex its own
    DEM, a vertex the apron shares neither (airside is king), nor a bank
    vertex other governed ground carries."""
    from auto_patch_v2.model.structures import SKIRT_ROLE
    from auto_patch_v2.planar.entrance_skirt import skirt_refs
    core_ref, bank_ref = skirt_refs("tunnel:t@0")
    tn = type("T", (), {"entrance_skirt": (703.5, core_ref, bank_ref)})()
    pm = type("P", (), {"ring_vertices": staticmethod(lambda ring: list(ring))})()
    pm.vertices = {0: _V((10.0, 5.0)), 1: _V((15.0, 5.0)), 2: _V((5.0, 10.0)),
                   3: _V((20.0, 8.0)), 4: _V((20.0, 0.0))}
    core, bank, apron = _F(SKIRT_ROLE, (0, 2)), _F(SKIRT_ROLE, (0, 1, 3, 4)), _F("apron", (2,))
    pm.faces = {0: core, 1: bank, 2: apron}
    vf = {0: [0, 1], 1: [1], 2: [0, 2], 3: [1], 4: [1]}
    airport = type("A", (), {"dem": _SlopeDem()})()
    got: dict = {}
    n = skirt_pins(pm, airport, law, tn, {core_ref: [core], bank_ref: [bank]}, vf,
                   ("retaining_wall", SKIRT_ROLE), lambda v: v == 4,
                   lambda v, z, src, senior=False: got.__setitem__(v, z), ())
    assert n == 3
    assert got[0] == pytest.approx(703.5)                      # the level piece
    assert got[1] == pytest.approx(700.0 - 0.25 * 5.0)         # the bank: its DEM
    assert got[3] == pytest.approx(700.0 - 0.25 * 8.0)
    assert 2 not in got and 4 not in got


def test_a_plate_running_on_along_the_bore_is_a_lid_never_a_face_top():
    """ENGM ``Ham2``: a 1,665 m2 top 70 m out of its end is a lid the road
    passes under -- no skirt, the mouth stays mapped; a headwall's 6 m top
    is the face's."""
    from auto_patch_v2.airport.trench_objects import _face_top
    assert _face_top(box(60.0, -14.0, 66.0, 14.0), (60.0, 0.0), (-1.0, 0.0), 10.0) is not None
    assert _face_top(box(60.0, -14.0, 130.0, 14.0), (60.0, 0.0), (-1.0, 0.0), 10.0) is None
    assert _face_top(box(60.0, -14.0, 66.0, 14.0), (60.0, 0.0), None, 10.0) is None
