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
3. a piece that FRONTS AIRSIDE is pinned by its frontage (§20 / §63 Rule S)
   and the re-union does not take it: the entries stay apart.
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


def test_a_piece_fronting_airside_is_pinned_and_the_rest_stay_apart(law):
    """PAD_A stands in the apron (its frontage fit is its seat); a landside
    piece of the same cluster does not pull it, nor ride it."""
    airport = _airport(law)
    airport = _dc.replace(airport, clusters=(
        _Cluster(airport, (PAD_A,), cid="unit:9#7/0"),
        _Cluster(airport, (LAND_B,), cid="unit:9#7/1")))
    pm, _st = build(airport, Classification(tuple(_land_cells()), (), {}, ()), law)
    want = {f.id for f in pm.faces.values() if f.ref in ("padA", "landB")}
    groups = [q for q in plane_groups(pm, law, airport) if set(q[3]) & want]
    assert len(groups) == 2, groups
    assert all(len(q[3]) == 1 for q in groups)
