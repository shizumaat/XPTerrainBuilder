"""K1 (kord-trench-frame-spec) and owner RULINGS 2026-11-19k (2): what a
building pad is NOT.

K1 -- a building rises above its own grade: a cluster whose tallest
ABOVE-GRADE component extent is under the walled height mints no pad, even
where a footprint-cache ring vouches the ground (KORD's I-190 road bed,
one slab y -5..0, vouched by 52 m2 of a neighbour's ring).

19k (2) -- a taxi route never crosses a building: a 1202 route passing
over the closed outline refuses the pad; one ending at its edge keeps it.
"""
from __future__ import annotations

import types

from shapely.geometry import box

from auto_patch_v2.geom import cluster_outlines
from auto_patch_v2.geom.cluster_outline import CACHE_VOUCHED_SOURCE
from auto_patch_v2.geom.pad_evidence import PadEvidence
from auto_patch_v2.geom.route_over_pad import OVER, TOUCH, RouteWitness
from auto_patch_v2.law.tables import load_default, pad_admission

ADMISSION = pad_admission(load_default())


def _ident(lon: float, lat: float) -> tuple[float, float]:
    return (lon, lat)


def _cluster(cid: str, x0, y0, x1, y1, above: float, total: float = 2.72):
    ring = [(y0, x0), (y0, x1), (y1, x1), (y1, x0)]
    area = (x1 - x0) * (y1 - y0)
    rows = (("slab.obj", total, above, area),)
    ev = PadEvidence(tall_base_fill=0.86, tallest_extent_m=above,
                     evidence_coverage=0.0, hull_area_m2=area,
                     name_vouched=False, evidence_name_vouched=False,
                     length_m=x1 - x0, width_m=y1 - y0, components=1,
                     rows=rows)
    return types.SimpleNamespace(id=cid, rings=[ring], walled=1, area_m2=area,
                                 floors=(-5.0,), members=("slab.obj",),
                                 evidence=ev, bridges=())


def _outlines(clusters, routes=None, vouch=CACHE_VOUCHED_SOURCE):
    refused: list[dict] = []
    got, counts = cluster_outlines(clusters, _ident, 0.0, walled_only=True,
                                   admission=ADMISSION,
                                   osm_evidence=lambda _u: vouch,
                                   refused=refused, routes=routes)
    return got, counts, refused


def test_k1_admission_carries_the_walled_height():
    law = load_default()
    assert ADMISSION.above_grade_min_m == float(
        law.tables.structures.placement.chain_min_height_m) == 2.5


def test_k1_a_slab_under_its_own_grade_mints_nothing_even_vouched():
    """The road bed: one component y -5.00..0.00 (above grade 0), the cache
    vouching its corner.  The vouch says a building is NEAR, never that the
    slab is one."""
    got, counts, refused = _outlines([_cluster("bed", 0, 0, 470, 96, 0.0)])
    assert got == [] and counts["below_grade"] == 1
    assert refused[0]["id"] == "bed" and refused[0]["gate"] == "above_grade_min_m"


def test_k1_a_building_standing_above_grade_still_mints_on_the_vouch():
    """A 4 m shed (under rule 10's 6 m, so the vouch carries it) is above
    the walled height: K1 leaves it alone."""
    got, counts, _r = _outlines([_cluster("shed", 0, 0, 40, 20, 4.0)])
    assert len(got) == 1 and counts["below_grade"] == 0
    assert counts["cache_vouched"] == 1


def test_k1_half_sunk_structure_under_the_walled_height_loses_its_pad():
    """0.82 m above grade (a half-sunk parking deck) is under 2.5 m."""
    got, counts, _r = _outlines([_cluster("park", 0, 0, 20, 17, 0.82)])
    assert got == [] and counts["below_grade"] == 1


def _airport(*edges):
    nodes = {}
    out = []
    for a, b in edges:
        for p in (a, b):
            nodes.setdefault(p, types.SimpleNamespace(xy=p))
        out.append(types.SimpleNamespace(a=a, b=b))
    ids = {p: k for k, p in enumerate(nodes)}
    return types.SimpleNamespace(
        taxi_nodes={ids[p]: n for p, n in nodes.items()},
        taxi_edges=[types.SimpleNamespace(a=ids[e.a], b=ids[e.b]) for e in out])


def test_route_over_a_pad_reads_over():
    rw = RouteWitness(_airport(((-10.0, 5.0), (50.0, 5.0))))
    kind, inside = rw.read(box(0, 0, 40, 10))
    assert kind == OVER and inside == 40.0


def test_route_through_a_node_inside_reads_over():
    rw = RouteWitness(_airport(((-10.0, 5.0), (20.0, 5.0)),
                               ((20.0, 5.0), (20.0, 30.0))))
    assert rw.read(box(0, 0, 40, 10))[0] == OVER


def test_route_ending_at_or_in_a_hangar_reads_touch():
    door = RouteWitness(_airport(((20.0, -30.0), (20.0, 0.0))))
    assert door.read(box(0, 0, 40, 10)) == (TOUCH, 0.0)
    inside = RouteWitness(_airport(((20.0, -30.0), (20.0, 4.0))))
    assert inside.read(box(0, 0, 40, 10)) == (TOUCH, 4.0)
    along = RouteWitness(_airport(((-10.0, 0.0), (50.0, 0.0))))
    assert along.read(box(0, 0, 40, 10))[0] == TOUCH
    clear = RouteWitness(_airport(((-10.0, -5.0), (50.0, -5.0))))
    assert clear.read(box(0, 0, 40, 10)) == ("", 0.0)


def test_a_route_over_a_cluster_refuses_its_pad_a_door_keeps_it():
    tall = _cluster("hangar", 0, 0, 40, 10, 12.0)
    over = RouteWitness(_airport(((-10.0, 5.0), (50.0, 5.0))))
    got, counts, refused = _outlines([tall], routes=over)
    assert got == [] and counts["taxi_route_over"] == 1
    assert refused[0]["gate"] == "taxi_route"
    door = RouteWitness(_airport(((20.0, -30.0), (20.0, 0.0))))
    got, counts, _r = _outlines([tall], routes=door)
    assert len(got) == 1 and counts["taxi_route_touch"] == 1
