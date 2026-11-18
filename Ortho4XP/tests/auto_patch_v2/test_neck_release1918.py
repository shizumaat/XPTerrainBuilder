"""#1918 R4 (LGAV 37.927345, 23.934221; spec ``docs/specs/1918-R4.md``):
a pad road's abeam station on a STANDING road kerb is released in the pad
roads' stage where its own law lets it (``pipeline/neck_release``), and
only pad-road rings are minted with stations (R4-1).  MEASURED: building24's
tip stood at 71.11 over a -2100 kerb station held at 70.16-70.18 on the base
edge's line, 1.1-1.5 m away — a row between two constants, never priced.

The map: a standing road S (y -8..0) shares its north kerb A-B with a pad
road P (y 0..3) into which a pad's tip T pokes down to y 1.2 over the
station St at (15, 0)."""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.law import Law
from auto_patch_v2.model.constraints import ConstraintSet, Diff, Pin, Source
from auto_patch_v2.pipeline.neck_release import late_neck_release
from auto_patch_v2.solve.design_roles import hard_rulings

A, B, C, D, ST, T, T1, T2, A2, B2, N = range(11)
XY = {A: (0.0, 0.0), B: (30.0, 0.0), C: (30.0, -8.0), D: (0.0, -8.0), ST: (15.0, 0.0),
      T: (15.0, 1.2), T1: (14.0, 3.0), T2: (16.0, 3.0), A2: (0.0, 3.0), B2: (30.0, 3.0),
      N: (20.0, -3.0)}
S, P, PAD = 0, 1, 2
NOTHING = {"released_edges": 0, "released": [], "walls": []}


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


class _Pm:
    """A planar map whose faces' rings are vertex-id cycles."""

    def __init__(self, xy, faces, pad_roads=frozenset()):
        self.faces = {f.id: f for f in faces}
        self.pad_roads = frozenset(pad_roads)
        inc: dict = {v: [] for v in xy}
        for f in faces:
            for v in f.ring:
                inc[v].append(f.id)
        self.vertices = {v: types.SimpleNamespace(xy=p, incident_faces=tuple(inc[v]))
                         for v, p in xy.items()}

    @staticmethod
    def ring_vertices(cyc):
        return tuple(cyc)


def _face(i, role, ref, ring):
    return types.SimpleNamespace(id=i, role=role, ref=ref, ring=tuple(ring), holes=())


def _maps(standing_role="service_road", st=None, notch=False, pads=True):
    """``(base map, full map)``: the base has no pad road and no station."""
    xy = dict(XY)
    if st is not None:
        xy[ST] = st
    if not notch:
        xy.pop(N)
    s_ring = [A, D, C, *([N] if notch else []), B, ST]
    faces = [_face(S, standing_role, "small_roads:-1", s_ring),
             _face(P, "service_road", "small_roads:-2", [A, ST, B, B2, T2, T, T1, A2]),
             _face(PAD, "building", "building24", [T, T2, B2, A2, T1])]
    pm = _Pm(xy, faces, {"small_roads:-2"} if pads else ())
    base = _Pm({v: p for v, p in xy.items() if v != ST},
               [_face(S, standing_role, "small_roads:-1", [v for v in s_ring if v != ST]),
                faces[2]])
    return base, pm


def _fixed(tip=71.0):
    return {A: 70.0, B: 70.0, C: 69.5, D: 69.5, ST: 70.0, T: tip, T1: tip, T2: tip,
            A2: tip, B2: tip, N: 69.8}


def _src(law):
    return Source("twin", sorted(hard_rulings(law))[0] + " (twin)", ())


def _run(law, base, pm, fixed, rows=()):
    joined = frozenset(v for v in fixed if v != ST)
    return late_neck_release(base, pm, fixed, ConstraintSet.from_rows(list(rows)), law,
                             {ST: (A, B)}, joined)


def test_a_neck_is_released_and_its_edge_ends_stay(law):
    base, pm = _maps()
    fixed = _fixed()
    rep, necks = _run(law, base, pm, fixed)
    assert ST not in fixed and fixed[A] == 70.0 and fixed[B] == 70.0
    assert rep["released_edges"] == 1 and len(rep["released"]) == 1 and not rep["walls"]
    assert [(n.s, n.v) for n in necks] == [(ST, T)] and necks[0].step == pytest.approx(1.0)


def test_a_step_under_the_bar_stays(law):
    base, pm = _maps()
    fixed = _fixed(tip=70.15)
    assert _run(law, base, pm, fixed) == (NOTHING, [])
    assert ST in fixed


def test_an_unreachable_station_stays_with_a_wall_record(law):
    base, pm = _maps()
    fixed = _fixed()
    rep, _necks = _run(law, base, pm, fixed, [Diff(ST, A, 0.01, 10.0, _src(law)),
                                               Diff(ST, T, 0.1, 1.0, _src(law))])
    assert ST in fixed and rep["released_edges"] == 0
    assert [w["reason"] for w in rep["walls"]] == ["unreachable"]
    assert rep["walls"][0]["step"] == pytest.approx(1.0)


def test_a_reachable_station_is_released(law):
    base, pm = _maps()
    fixed = _fixed()
    rep, _necks = _run(law, base, pm, fixed, [Diff(ST, A, 0.1, 15.0, _src(law)),
                                               Diff(ST, T, 0.2, 1.2, _src(law))])
    assert ST not in fixed and rep["released_edges"] == 1


def test_a_standing_vertex_abeam_the_station_stays(law):
    base, pm = _maps(notch=True)
    fixed = _fixed()
    rep, _necks = _run(law, base, pm, fixed)
    assert ST in fixed and [w["reason"] for w in rep["walls"]] == ["own_section"]


def test_a_station_within_the_identity_spacing_stays(law):
    base, pm = _maps(st=(0.4, 0.0))
    fixed = _fixed()
    assert _run(law, base, pm, fixed) == (NOTHING, [])
    assert ST in fixed


def test_a_pinned_station_stays(law):
    base, pm = _maps()
    fixed = _fixed()
    rep, _necks = _run(law, base, pm, fixed, [Pin(ST, 70.0, Source("twin", "twin pin (x)", ()))])
    assert ST in fixed and rep == NOTHING


@pytest.mark.parametrize("role", ["apron", "parking_lot", "building"])
def test_an_apron_lot_or_pad_edge_is_never_a_candidate(law, role):
    base, pm = _maps(standing_role=role)
    fixed = _fixed()
    assert _run(law, base, pm, fixed) == (NOTHING, [])
    assert ST in fixed


def test_a_map_without_pad_roads_releases_nothing(law):
    base, pm = _maps(pads=False)
    fixed = _fixed()
    assert _run(law, base, pm, fixed) == (NOTHING, [])
    assert ST in fixed


def _station_minted(law, pad_road):
    """Whether the arrangement mints the abeam station (15, 300) on a notched
    road ring (the R3 twin's geometry, 300 m north of the #609 twins' pad
    and runway) of a cell with / without pad-road evidence.  The cell's ref
    is no mapped-road ribbon's, so it is noded in pass A at full precision
    (a pass-C ribbon part carries the identity grid's precision model, on
    which the R3 face test's ``buffer(1e-6)`` is empty — lane l1918d)."""
    from auto_patch_v2.classify.roles import Cell, Classification
    from auto_patch_v2.planar import build
    from tests.auto_patch_v2.test_pad_touch import _airport, _Dem
    from tests.auto_patch_v2.test_roads609 import _ribbon_cells
    ring = tuple((x, y + 300.0) for x, y in (
        (0.0, 0.0), (30.0, 0.0), (30.0, 7.0), (16.0, 7.0), (15.0, 1.3), (14.0, 7.0), (0.0, 7.0)))
    ev = {"osm_ribbon": 1.0, **({"pad_road": 1.0} if pad_road else {})}
    cells = [*_ribbon_cells()[:2], Cell(1, "service_road", "road7", ring, (), None,
                                        None, "groundside", "service_road", ev)]
    pm, _st = build(_airport(law, _Dem()), Classification(tuple(cells), (), {}, ()), law)
    return any(abs(v.xy[0] - 15.0) < 1e-6 and abs(v.xy[1] - 300.0) < 1e-6
               for v in pm.vertices.values())


def test_only_a_pad_road_ring_is_minted_with_stations(law):
    assert _station_minted(law, pad_road=True)
    assert not _station_minted(law, pad_road=False)
