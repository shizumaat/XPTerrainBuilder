"""Twins for §16g (9) ONE POPULATION and §16g (10) THE PAD IS THE CLUSTER
(owner RULINGS 2026-09-14x / 14z) — lane ``v2padcluster``.

Owner, verbatim: *"pads must match building clusters, no building, or
cluster can span multiple pads, if it does, it means we didn't identify
the building shape or cluster correctly.  They should match exactly."*

Four laws, four twins:

1. (9) ONE POPULATION — ``plan_clusters`` has no ``FAMILY_*`` gate and no
   area gate: every connected footprint chain is a cluster, singletons
   included.  ``cluster_pad_min_m2`` keeps only its threshold job.
2. (10) (1) A CLUSTER IS ONE BUILDING — a touching chain splits where two
   GROUND-CONTACT bodies' authored ground floors differ by more than
   ``floor_split_m``; an ELEVATED body (no ground-contact component)
   chains by touch alone, because splitting on its lowest component
   splits a tall building per storey (HECA 2,677 -> 20,203, MEASURED).
3. (10) (2) THE PAD IS DERIVED FROM THE CLUSTER — one pad per cluster,
   its outline union; the footprints no cluster covers are the fallback;
   ``pad_from_cluster = false`` is the identity.
4. (10) (3) ``pad_cluster_mismatch`` — CRITICAL, and 0 is the bar.
"""
from __future__ import annotations

from auto_patch_v2.airport.placement_family import plan_clusters
from auto_patch_v2.law import Law

from test_v2connector import (_blk, _chain, _lat, _PMember, _PPart,  # noqa: E402
                             _PPlan, _PUnit)


def _part(pid, la0, la1, *, base_y=0.0, footed=True, lo0=-3.0000, lo1=-2.9990):
    p = _PPart(pid, _blk(la0, la1, lo0, lo1))
    p.base_y = base_y
    # a GROUND-CONTACT component is one the plan gave FEET; an ELEVATED
    # one has none (``model/rebake.Part.feet``)
    p.feet = ((p.lat, p.lon, base_y),) if footed else ()
    p.rings = (((la0, lo0), (la1, lo0), (la1, lo1), (la0, lo1)),)
    return p


def _plan(members, contacts=()):
    return _PPlan([_PUnit("unit:0", members)], contacts)


TOUCH = 0.5


# ── (9) ONE POPULATION ──────────────────────────────────────────────────

def test_16g_9_the_family_gates_are_gone_and_a_lone_body_is_a_cluster():
    """§16g (9) (owner RULINGS 2026-09-14x): until 14x this applied
    ``FAMILY_MIN_MEMBERS`` (2 members), ``FAMILY_SHARE_MIN`` (half the
    unit's bodies) and ``cluster_pad_min_m2`` (5,000 m2), and returned
    TWO clusters at HECA while the object stage's §16g (7) chained the
    same bodies with no gate at all.  Two populations for "what is one
    building" is the census-wrapper defect in geometry.  There is now
    one: three bodies apart in plan are three clusters."""
    a = _PMember("objects/a.obj", [_part(1, _lat(0), _lat(10))])
    b = _PMember("objects/b.obj", [_part(2, _lat(100), _lat(110))])
    c = _PMember("objects/c.obj", [_part(3, _lat(200), _lat(210))])
    got = plan_clusters(_plan([a, b, c]), TOUCH)
    assert len(got) == 3, [q.id for q in got]
    assert all(q.bodies == 1 for q in got)
    # ... and every one of them carries its OUTLINE, which is what the
    # pad is derived from
    assert all(len(q.rings) == 1 for q in got)
    # the area threshold does NOT filter the population any more — these
    # blocks are ~10 x 84 m, far under ``cluster_pad_min_m2``
    assert all(q.area_m2 < 5000.0 for q in got)


def test_16g_9_touching_bodies_at_one_floor_are_ONE_cluster():
    """The other half of (9): the chain itself is unchanged — bodies
    whose footprints touch within ``footprint_touch_m`` and agree about
    their floor are ONE building, however many members they span."""
    a = _PMember("objects/a.obj", [_part(1, _lat(0), _lat(40))])
    b = _PMember("objects/b.obj", [_part(2, _lat(40), _lat(80))])
    got = plan_clusters(_plan([a, b]), TOUCH, floor_split_m=0.5)
    assert len(got) == 1 and got[0].bodies == 2, [q.id for q in got]
    assert got[0].footed == 2


# ── (10) (1) A CLUSTER IS ONE BUILDING ──────────────────────────────────

def test_16g_10_1_a_touching_body_at_a_different_floor_is_its_own_cluster():
    """§16g (10) (1): "A touching body at a different authored floor is a
    different building — its own cluster, its own pad, and the difference
    is a declared terrace step between the two pads."

    The same two touching bodies as above, one authored 3 m up: TWO
    clusters.  At ``floor_split_m = 0`` the split is disarmed and they
    are one again, which is the law key's own clause."""
    a = _PMember("objects/a.obj", [_part(1, _lat(0), _lat(40), base_y=0.0)])
    b = _PMember("objects/b.obj", [_part(2, _lat(40), _lat(80), base_y=3.0)])
    two = plan_clusters(_plan([a, b]), TOUCH, floor_split_m=0.5)
    assert len(two) == 2, [(q.id, q.floors) for q in two]
    assert sorted(min(q.floors) for q in two) == [0.0, 3.0]
    one = plan_clusters(_plan([a, b]), TOUCH, floor_split_m=0.0)
    assert len(one) == 1

    # ... and a floor difference INSIDE the tolerance does not split
    b2 = _PMember("objects/b.obj", [_part(2, _lat(40), _lat(80), base_y=0.4)])
    assert len(plan_clusters(_plan([a, b2]), TOUCH, floor_split_m=0.5)) == 1


def test_16g_10_1_an_ELEVATED_body_never_splits_a_tall_building():
    """§16g (10) (1) as 14z ruled it: the floor is the body's GROUND
    FLOOR — the lowest GROUND-CONTACT component's ``base_y`` — and the
    split is asked only where BOTH bodies have one.

    MEASURED at HECA: 15,875 of 24,165 plan bodies carry no footed
    component at all, and reading their lowest component as a floor took
    the airport from 2,677 clusters to 20,203 — a tall building split per
    storey, which is what 14z forbids.  Here a wall on the ground carries
    a roof authored 12 m up: ONE building."""
    wall = _PMember("objects/wall.obj",
                    [_part(1, _lat(0), _lat(40), base_y=0.0, footed=True)])
    roof = _PMember("objects/roof.obj",
                    [_part(2, _lat(0), _lat(40), base_y=12.0, footed=False)])
    got = plan_clusters(_plan([wall, roof]), TOUCH, floor_split_m=0.5)
    assert len(got) == 1, [(q.id, q.floors, q.footed) for q in got]
    assert got[0].bodies == 2 and got[0].footed == 1
    # the ELEVATED body's own floor is still recorded (it is its lowest
    # component), it is simply not a reason to split
    assert sorted(got[0].floors) == [0.0, 12.0]


def test_16g_10_1_the_ground_floor_is_the_lowest_FOOTED_component():
    """A body of several components takes the lowest component that has
    FEET, not the lowest component: a basement slab the plan judged
    elevated does not become the building's ground floor."""
    m = _PMember("objects/m.obj",
                 [_part(1, _lat(0), _lat(40), base_y=-6.0, footed=False),
                  _part(2, _lat(0), _lat(40), base_y=2.0, footed=True),
                  _part(3, _lat(0), _lat(40), base_y=9.0, footed=True)])
    got = plan_clusters(_plan([m], _chain([1, 2, 3])), TOUCH,
                        floor_split_m=0.5)
    assert len(got) == 1 and got[0].floors == (2.0,), got[0].floors


# ── (10) (2) THE PAD IS DERIVED FROM THE CLUSTER ────────────────────────

class _Frame:
    """The identity transform, so a fixture's metres ARE its degrees."""

    def transformers(self):
        return (lambda lon, lat: (float(lon), float(lat)),
                lambda x, y: (float(y), float(x)))


class _Cl:
    def __init__(self, cid, rings, area=20000.0, floors=(0.0,)):
        self.id = cid
        self.rings = tuple(rings)
        self.area_m2 = area
        self.floors = tuple(floors)
        self.boxes = ()
        self.bodies = len(self.floors)
        self.footed = len(self.floors)


def _sq(x0, y0, x1, y1):
    """A ring in the ``(lat, lon)`` spelling ``PlanCluster.rings`` uses."""
    return ((y0, x0), (y0, x1), (y1, x1), (y1, x0))


class _AP:
    frame = _Frame()

    def __init__(self, clusters, buildings=()):
        self.clusters = tuple(clusters)
        self.buildings = tuple(buildings)
        self.dsf_objects = ()


def test_16g_10_2_one_pad_per_cluster_and_touching_clusters_are_not_merged():
    """§16g (10) (2): the ``building`` pad is DERIVED from the cluster —
    one pad per cluster, its outline union.

    The load-bearing half is that two TOUCHING clusters are NOT unioned
    into one pad: the pre-14x derivation ran one ``unary_union`` over
    every admitted footprint and its connected parts were the pads, so a
    building at a different floor sharing a wall with its neighbour came
    out as one pad with one level.  Under (10) they are two buildings,
    two pads, and the step between them is §23's declared terrace."""
    from auto_patch_v2.classify.evidence import _cluster_pads
    law = Law.for_airport("ZZZZ")
    ap = _AP([_Cl("unit:0#0", [_sq(0.0, 0.0, 40.0, 40.0)], floors=(0.0,)),
              _Cl("unit:0#1", [_sq(40.0, 0.0, 80.0, 40.0)], floors=(3.0,))])
    got = _cluster_pads(ap, law)
    assert len(got) == 2, [g.bounds for g in got]
    assert sorted(round(g.area) for g in got) == [1600, 1600]
    # one cluster of two touching bodies IS one pad (its own outline
    # union), which is the other direction of the same rule
    ap2 = _AP([_Cl("unit:0#0", [_sq(0.0, 0.0, 40.0, 40.0),
                                _sq(40.0, 0.0, 80.0, 40.0)])])
    got2 = _cluster_pads(ap2, law)
    assert len(got2) == 1 and round(got2[0].area) == 3200


def test_16g_10_2_pad_from_cluster_false_is_the_identity():
    """The matched BASE ARM: ``[placement] pad_from_cluster = false``
    derives no cluster pad at all and ``_pads`` falls back to the
    pre-14x reading over the admitted footprints."""
    import dataclasses as _dc

    from auto_patch_v2.classify.evidence import CLUSTER_PADS, _cluster_pads
    law = Law.for_airport("ZZZZ")
    off = _dc.replace(
        law.tables.structures.placement, pad_from_cluster=False)
    st = _dc.replace(law.tables.structures, placement=off)
    tables = _dc.replace(law.tables, structures=st)
    law_off = _dc.replace(law, tables=tables)
    ap = _AP([_Cl("unit:0#0", [_sq(0.0, 0.0, 40.0, 40.0)])])
    assert _cluster_pads(ap, law) != []
    assert _cluster_pads(ap, law_off) == []
    assert CLUSTER_PADS.get("disarmed") is True


def test_16g_10_2_a_cluster_with_no_outline_is_skipped_and_counted():
    """A plan written before §16g (7) (1)'s ring field carries no
    outline.  A box union is not a footprint (13ci measured what pricing
    one costs), so such a cluster mints NO pad and the count says so —
    the build then falls back to the footprint cache and is not silently
    reading boxes as buildings."""
    from auto_patch_v2.classify.evidence import CLUSTER_PADS, _cluster_pads
    law = Law.for_airport("ZZZZ")
    got = _cluster_pads(_AP([_Cl("unit:0#0", [])]), law)
    assert got == [] and CLUSTER_PADS["no_rings"] == 1


# ── (10) (3) pad_cluster_mismatch ───────────────────────────────────────

def test_16g_10_3_the_mismatch_family_is_registered_and_priced():
    """§16g (10) (3): CRITICAL, and the census must be able to say 0.

    The family is SIDECAR-DECLARED (the outlines live in the rebake plan,
    which no patch carries), so the twin is over the contract: the family
    is registered in both registers, and the check turns each declared
    record into exactly one row."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    import check_grade as cg

    assert "pad_cluster_mismatch" in {k for k, _t, _b in cg.LAW_FAMILIES}
    assert cg.SIDECAR_LAW_KEYS["pad_cluster_mismatch"] == "pad_cluster_mismatch"
    assert cg._check_pad_cluster_mismatch(None) == []
    assert cg._check_pad_cluster_mismatch([]) == []
    rows = cg._check_pad_cluster_mismatch([
        {"kind": "pad_spans_clusters", "ref": "building7",
         "others": ["unit:0#0", "unit:0#3"], "lat": 30.1, "lon": 31.4},
        {"kind": "cluster_spans_pads", "ref": "unit:1#2",
         "others": ["building8", "building9"], "lat": 30.2, "lon": 31.5}])
    assert len(rows) == 2
    assert rows[0].way_a.ref.startswith("pad_spans_clusters:building7")
    assert (rows[0].lat, rows[0].lon) == (30.1, 31.4)
    assert all(r.way_a.tags["role"] == "object_pad" for r in rows)
