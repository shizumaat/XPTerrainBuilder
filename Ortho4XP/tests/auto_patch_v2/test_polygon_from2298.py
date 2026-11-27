"""#2298 (LEMO): ``classify/evidence.polygon_from`` returns a VALID polygon
even where ``buffer(0)`` hands an invalid one back — a footprint-cache
ring folded flat onto itself (two corners 1e-11 m apart) came back from
``buffer(0)`` as a shell with a hole outside it, and the fallback pads'
``unary_union`` aborted the airport (``non-noded intersection`` of a
zero-length line)."""
from __future__ import annotations

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from auto_patch_v2.classify.evidence import polygon_from

#: the LEMO footprint ring, verbatim (moved, it rounds valid)
FOLDED = ((-24077.685, 26321.455), (-24083.3, 26321.419),
          (-24088.957000000002, 26321.329), (-24094.994, 26321.241),
          (-24100.229, 26321.203))


def test_the_buffer0_repair_alone_leaves_the_folded_ring_invalid():
    assert not Polygon(FOLDED).buffer(0).is_valid


def test_a_folded_ring_reads_valid_and_unions():
    p = polygon_from(FOLDED)
    assert p is None or (p.is_valid and p.geom_type == "Polygon")
    near = box(-24095.0, 26321.0, -24080.0, 26322.0)
    assert unary_union([g for g in (p, near) if g is not None]).is_valid


def test_a_ring_buffer0_repairs_reads_as_before():
    bow = ((0.0, 0.0), (10.0, 10.0), (10.0, 0.0), (0.0, 10.0))
    assert polygon_from(bow).equals(
        max(Polygon(bow).buffer(0).geoms, key=lambda g: g.area)
        if Polygon(bow).buffer(0).geom_type != "Polygon" else Polygon(bow).buffer(0))
    sq = ((0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0))
    assert polygon_from(sq).equals(Polygon(sq))
