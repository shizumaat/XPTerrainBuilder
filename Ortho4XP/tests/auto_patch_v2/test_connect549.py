"""Twins for design spec §64 (lane ``connect549``; owner RULINGS 2026-09-11i
"a welded canopy-and-building group takes ONE pad across its footprint
union", restated 2026-10-10n (1) at KCLT): THE PIECES OF ONE CLUSTER ARE
ONE PLANE.

``geom/cluster_outline`` rule 2 emits a cluster whose outline falls apart
in plan as pieces ``<cid>/<k>``; ``constraints/cluster_pad.plane_groups``
priced each piece as its own plane, which is how KCLT's hourly deck took
223.21 m while the two garages its walkways join took 218.1 / 219.0 m and
the unit's one §16g zero floated ten bodies 3–5 m.  Now:

1. two LANDSIDE pieces of one cluster (fronting nothing) are ONE
   ``cluster:`` entry holding both faces;
2. two pads of two DIFFERENT clusters stay two plain entries — the piece
   stem is the witness, never proximity;
3. a piece that FRONTS AIRSIDE re-unites too (owner RULINGS 2026-10-12l (1),
   #608: the apron grades to the one level the complex is seated at) and the
   HELD blocks of one entry share one datum column (``platform.datum_groups``).
"""
from __future__ import annotations

import dataclasses as _dc

import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints.cluster_pad import _piece_stem, plane_groups
from auto_patch_v2.law import Law
from auto_patch_v2.planar.build import build
from tests.auto_patch_v2.test_v2clusterpad import (PAD_A, PAD_B, _Cluster,
                                                   _airport, _cells, _rect)

#: two landside pads on bare ground, 30 m apart, far from the apron
LAND_A = (-120.0, 420.0, -20.0, 500.0)
LAND_B = (10.0, 420.0, 110.0, 500.0)


@pytest.fixture(scope="module")
def law():
    from tests.auto_patch_v2._plate import plate_law
    return plate_law(Law.for_airport("ZZZZ"))


def _land_cells():
    return list(_cells()) + [
        Cell(6, "building", "landA", _rect(*LAND_A), (), None, None,
             "groundside", "pad", {}),
        Cell(7, "building", "landB", _rect(*LAND_B), (), None, None,
             "groundside", "pad", {}),
    ]


def _groups(law, clusters):
    airport = _airport(law)
    airport = _dc.replace(airport, clusters=tuple(clusters))
    pm, _st = build(airport, Classification(tuple(_land_cells()), (), {}, ()), law)
    land = {f.id for f in pm.faces.values() if f.ref in ("landA", "landB")}
    return [q for q in plane_groups(pm, law, airport)
            if set(q[3]) & land]


def test_piece_stem_reads_only_the_rule_2_spelling():
    assert _piece_stem("unit:31#1117/2") == "unit:31#1117"
    assert _piece_stem("unit:31#1117") is None
    assert _piece_stem("unit:31#1117/b2") is None
    assert _piece_stem("/3") is None


def test_two_landside_pieces_of_one_cluster_are_ONE_plane(law):
    airport = _airport(law)
    groups = _groups(law, (_Cluster(airport, (LAND_A,), cid="unit:9#7/0"),
                           _Cluster(airport, (LAND_B,), cid="unit:9#7/1")))
    assert len(groups) == 1, groups
    assert groups[0][1].startswith("cluster:")
    assert len(groups[0][3]) == 2


def test_two_clusters_are_two_planes_whatever_their_distance(law):
    airport = _airport(law)
    groups = _groups(law, (_Cluster(airport, (LAND_A,), cid="unit:9#7"),
                           _Cluster(airport, (LAND_B,), cid="unit:9#8")))
    assert len(groups) == 2, groups
    assert all(len(q[3]) == 1 for q in groups)


def test_a_piece_fronting_airside_re_unites_with_its_cluster(law):
    """Owner RULINGS 2026-10-12l (1) (#608): PAD_A stands in the apron and a
    landside piece of the same cluster is still ONE plane with it — the
    apron grades to the one level the complex is seated at; a frontage no
    longer pins a piece apart (the pre-12l reading left KCLT's concourse
    0.69 m under its terminal, the roofs of one building at two zeros)."""
    airport = _airport(law)
    airport = _dc.replace(airport, clusters=(
        _Cluster(airport, (PAD_A,), cid="unit:9#7/0"),
        _Cluster(airport, (LAND_B,), cid="unit:9#7/1")))
    pm, _st = build(airport, Classification(tuple(_land_cells()), (), {}, ()), law)
    want = {f.id for f in pm.faces.values() if f.ref in ("padA", "landB")}
    groups = [q for q in plane_groups(pm, law, airport) if set(q[3]) & want]
    assert len(groups) == 1, groups
    assert groups[0][1] == "cluster:unit:9#7/0"
    assert {pm.faces[q].ref for q in groups[0][3]} == {"padA", "landB"}


def test_held_blocks_of_one_plane_entry_share_one_datum_column(law):
    """``platform.datum_groups`` names the held refs of one entry and
    ``datum_group_rows`` ties their datum columns, hard, under the hold
    head (stripped in pass 1a, carried in pass 1b); two entries tie
    nothing; a ref with no datum column is skipped."""
    from auto_patch_v2.constraints.platform import (HOLD_RULING, datum_group_rows,
                                                    datum_groups)
    airport = _airport(law)
    airport = _dc.replace(airport, clusters=(
        _Cluster(airport, (PAD_A,), cid="unit:9#7/0"),
        _Cluster(airport, (LAND_B,), cid="unit:9#7/1"),
        _Cluster(airport, (LAND_A,), cid="unit:5#2")))
    pm, _st = build(airport, Classification(tuple(_land_cells()), (), {}, ()), law)
    groups = datum_groups(pm, law, airport, ["padA", "landB", "landA"])
    assert groups == {"landB": ["padA"]}
    assert datum_groups(pm, law, None, ["padA", "landB"]) == {}
    rows = datum_group_rows(groups, {"landB": 7, "padA": 3})
    assert len(rows) == 2
    assert all(r.source.ruling.split(" (")[0] == HOLD_RULING for r in rows)
    assert {tuple(sorted(dict(r.terms).items())) for r in rows} == {
        ((3, 1.0), (7, -1.0)), ((3, -1.0), (7, 1.0))}
    assert datum_group_rows(groups, {"landB": 7}) == []


# ── 10n (3): THE OBJECT CUT AT A PAD LEVEL (#547) ─────────────────────────

def _pad(ref, x0, x1, z):
    import types
    ring = ((0.0, x0), (0.0, x1), (1.0, x1), (1.0, x0))
    return types.SimpleNamespace(ref=ref, ring=ring, z=(z,) * 4)


def _part(pid, lat, lon):
    import types
    return types.SimpleNamespace(pid=pid, lat=lat, lon=lon, feet=((lat, lon, 0.0),),
                                 box=(lat, lon, lat, lon), line=False)


def _terminal(contacts=()):
    """Three members: A on pad ``t75`` (222.44), B on ``t81`` (221.75), C
    on no pad north of both; A's parts welded, B's parts welded."""
    import dataclasses
    import types

    @dataclasses.dataclass(frozen=True)
    class _Plan:
        units: tuple
        contacts: tuple
        abutments: tuple = ()

    def member(res, *parts):
        return types.SimpleNamespace(resource=res, parts=parts)
    a = member("a.obj", _part(0, 0.5, 0.1), _part(1, 0.5, 0.3))
    b = member("b.obj", _part(2, 0.5, 0.7), _part(3, 0.5, 0.9))
    c = member("c.obj", _part(4, 1.5, 0.45))
    plan = _Plan(units=(types.SimpleNamespace(members=(a, b, c)),),
                 contacts=((0, 1), (2, 3)) + tuple(contacts))
    from auto_patch_v2.airport.footprint_unit import PlanUnit
    un = PlanUnit(id="fu:6", bodies=((0, 0, 0), (0, 1, 0), (0, 2, 0)),
                  pids=frozenset(range(5)), members=("a.obj", "b.obj", "c.obj"),
                  boxes=(), area_m2=0.0)
    return plan, un


def test_a_unit_on_two_pads_a_step_apart_is_one_unit_per_level():
    """#547: the concourse pad stands 0.69 m under the terminal's; the
    unit is cut per level (the LOWER level is ``/p0``) so each body takes
    the pad it stands on; the body on no pad joins the level its WELDED
    parts stand on, and with no weld the level nearest its feet."""
    from auto_patch_v2.airport import pad_block_seat as pbs
    pads = [_pad("t75", 0.0, 0.5, 222.44), _pad("t81", 0.5, 1.0, 221.75)]
    plan, un = _terminal(((4, 2), (4, 3)))
    counts: dict = {}
    out = pbs.split_units([un], plan, pads, counts, level_tol_m=0.3)
    assert {u.id: u.bodies for u in out} == {
        "fu:6/p0": ((0, 1, 0), (0, 2, 0)), "fu:6/p1": ((0, 0, 0),)}
    assert counts["pad_level_units_split"] == 1
    assert counts["pad_level_bodies_welded"] == 1
    plan, un = _terminal()
    counts = {}
    out = pbs.split_units([un], plan, pads, counts, level_tol_m=0.3)
    assert {u.id: u.bodies for u in out}["fu:6/p1"] == ((0, 0, 0), (0, 2, 0))
    assert counts["pad_level_bodies_nearest"] == 1


def test_pads_within_the_tolerance_are_one_level_and_zero_disarms():
    """``building75`` (222.44) and ``building84`` (222.70) are 0.26 m
    apart: under ``split_tol_m`` 0.3 they are ONE level and the unit is
    not cut; ``level_tol_m`` 0 disarms the cut whatever the step."""
    from auto_patch_v2.airport import pad_block_seat as pbs
    plan, un = _terminal()
    near = [_pad("t75", 0.0, 0.5, 222.44), _pad("t84", 0.5, 1.0, 222.70)]
    assert [u.id for u in pbs.split_units([un], plan, near, {}, level_tol_m=0.3)] == ["fu:6"]
    far = [_pad("t75", 0.0, 0.5, 222.44), _pad("t81", 0.5, 1.0, 221.75)]
    assert [u.id for u in pbs.split_units([un], plan, far, {}, level_tol_m=0.0)] == ["fu:6"]
    assert pbs.level_groups({"a": 10.0, "b": 10.2, "c": 10.5, "d": 11.0}, 0.3) == \
        {"a": 0, "b": 0, "c": 1, "d": 2}


def test_block_pads_are_not_level_pads_and_a_level_id_keeps_the_block_tail():
    """A platform's BLOCKS are the block cut's (flat-pad spec §3 C16),
    never the level cut's: ``level_pad_rings`` leaves them out, so a unit
    on blocks alone is not cut by level.  The level cut runs FIRST, so a
    block id written after it (``<id>/p<k>/b<k>``) still carries the
    ``/b<k>`` tail ``seat_unit`` parses."""
    from auto_patch_v2.airport import pad_block_seat as pbs
    pads = [_pad("t81", 0.5, 1.0, 221.75),
            _pad("t/b0", 0.0, 0.2, 222.44), _pad("t/b1", 0.2, 0.5, 225.00)]
    assert [r[0] for r in pbs.level_pad_rings(pads)] == ["t81"]
    assert pbs._block_id("fu:6/p1/b1") == ("fu:6/p1", 1)
    assert pbs._block_id("fu:6/p1") is None

