"""§34 (13) (3) / (4) — lane ``v2lemdstruct2`` r3 (Fable 2026-09-15;
RULINGS 2026-09-15y).

(3) A junction's transverse law is the RAW PAIR across its width; at a
runway contact the junction's far edge follows the RUNWAY's edge level.
(4) THE ROAD BETWEEN TWO MOUTHS is minted at the planar stage, and only
there — never a general road admission (r2's 24-reader consumer census
read 207 faces / 944,872 m² for that, HAZARD on five readers).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import sys
from pathlib import Path

import pytest
from shapely.geometry import Polygon

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auto_patch_v2.classify.roles import Cell           # noqa: E402
from auto_patch_v2.law import Law                       # noqa: E402
from auto_patch_v2.model.airport import OsmWay          # noqa: E402
from auto_patch_v2.planar import structure_road as _sr  # noqa: E402

from test_v2rampwalk import _airport, TAGS_R, TAGS_T    # noqa: E402


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


class _Tn:
    """A structure record as ``mouth_pair_roads`` reads one: its mouth is
    ``axis[0]`` and ``ways`` are the bores it was cut from."""

    def __init__(self, tid, mouth, ways):
        self.id = tid
        self.axis = (mouth, (mouth[0] + 1.0, mouth[1]))
        self.ways = tuple(ways)


@_dc.dataclass(frozen=True)
class _Cl:
    cells: tuple = ()


def _mint(law, ways, tunnels, cells=()):   # noqa: D401
    cl, notes = _sr.mouth_pair_roads(_airport(law, ways=ways),
                                     _Cl(tuple(cells)), law, tunnels)
    return [c for c in cl.cells if c.ref.startswith(_sr.MOUTH_ROAD_REF)], notes


# the LEMD shape, in the fixture's metres: a bore ending at (0, 0) whose
# mouth is there, a second bore whose mouth is 80 m away, and the surface
# road between them
def _pair(gap_m=80.0, road_tags=None, bore_tags=None):
    bore_a = OsmWay(-101, "big_roads", ((-200.0, 0.0), (0.0, 0.0)), False,
                    dict(bore_tags or TAGS_T))
    bore_b = OsmWay(-102, "big_roads", ((gap_m, 0.0), (gap_m + 200.0, 0.0)),
                    False, dict(bore_tags or TAGS_T))
    road = OsmWay(-103, "big_roads", ((0.0, 0.0), (gap_m, 0.0)), False,
                  dict(road_tags or TAGS_R))
    tns = [_Tn("tunnel:-101@0", (0.0, 0.0), (-101,)),
           _Tn("tunnel:-102@0", (gap_m, 0.0), (-102,))]
    return [bore_a, bore_b, road], tns


def test_the_road_between_two_mouths_mints_one_face(law):
    """The owner's site (15e item 5), in the fixture's own metres: OSM
    −5944 runs from ``tunnel:-5931@1``'s mouth (sharing its node, 0.00 m)
    to 47.3 m short of ``tunnel:-5980@0``.  One way, two DIFFERENT mouths,
    one face — the road's own carriageway width."""
    ways, tns = _pair()
    faces, notes = _mint(law, ways, tns)
    assert len(faces) == 1, notes
    f = faces[0]
    assert f.role == "service_road"
    assert f.ref == f"{_sr.MOUTH_ROAD_REF}:-103"
    assert f.side == "groundside"
    poly = Polygon(f.ring, f.holes)
    # 80 m of road at the 2-lane carriageway width (lanes x lane_width_m)
    want = 80.0 * law.tables.structures.tunnel.lane_width_m * 2
    assert poly.area == pytest.approx(want, rel=0.02), (poly.area, want)
    assert any("mouth road -103" in n for n in notes), notes


def test_a_structure_way_is_never_a_mouth_road(law):
    """The consumer census's worst HAZARD: a face minted over a
    ``tunnel=yes`` way carries no structure record, so
    ``airport/road_ramp.deck_refs`` cannot exclude it and §37 (6) grades
    it to the surface OVER THE BORE."""
    ways, tns = _pair(road_tags=TAGS_T)
    faces, _n = _mint(law, ways, tns)
    assert faces == []
    ways2, tns2 = _pair(road_tags={**TAGS_R, "bridge": "yes"})
    assert _mint(law, ways2, tns2)[0] == []


def test_one_end_at_a_mouth_is_not_a_road_between_two_mouths(law):
    """A road that leaves a portal and goes somewhere else is an ordinary
    mapped road — the population r2's census refused."""
    ways, tns = _pair()
    faces, _n = _mint(law, ways, [tns[0]])          # only the near mouth
    assert faces == []


def test_two_ends_at_ONE_mouth_are_not_two_mouths(law):
    """A loop out of a portal and back is not a road BETWEEN two."""
    ways, tns = _pair()
    same = [_Tn("tunnel:-101@0", (0.0, 0.0), (-101,)),
            _Tn("tunnel:-101@0", (80.0, 0.0), (-101,))]   # one id, two ends
    faces, _n = _mint(law, ways, same)
    assert faces == []


def test_at_least_one_end_must_be_a_true_NODE_join(law):
    """The canonical identity join (memory ``canonical-identity-join``).
    MEASURED at LEMD: demanding TWO node joins reads 0 ways (a merged dual
    carriageway reports its mouth at the PAIR'S CENTRE — −5944's far end
    is 47.3 m out); demanding NONE reads 27; demanding ONE reads 4."""
    # both bores pulled back so neither end coincides with a bore endpoint
    bore_a = OsmWay(-101, "big_roads", ((-200.0, 0.0), (-30.0, 0.0)), False, dict(TAGS_T))
    bore_b = OsmWay(-102, "big_roads", ((110.0, 0.0), (300.0, 0.0)), False, dict(TAGS_T))
    road = OsmWay(-103, "big_roads", ((0.0, 0.0), (80.0, 0.0)), False, dict(TAGS_R))
    tns = [_Tn("tunnel:-101@0", (0.0, 0.0), (-101,)),
           _Tn("tunnel:-102@0", (80.0, 0.0), (-102,))]
    assert _mint(law, [bore_a, bore_b, road], tns)[0] == []


def test_mouth_pair_m_bounds_the_class(law):
    """The law key, not a literal: beyond ``mouth_pair_m`` the way is an
    ordinary road again."""
    pair_m = law.tables.structures.tunnel.mouth_pair_m
    assert len(_mint(law, *_pair(gap_m=pair_m * 0.5))[0]) == 1
    # the road's FAR end now stands beyond the bound from the far mouth:
    # the bore is pulled back so its mouth is > mouth_pair_m from the road
    gap = pair_m * 0.5
    bore_a = OsmWay(-101, "big_roads", ((-200.0, 0.0), (0.0, 0.0)), False, dict(TAGS_T))
    bore_b = OsmWay(-102, "big_roads", ((gap, 0.0), (gap + 200.0, 0.0)), False, dict(TAGS_T))
    road = OsmWay(-103, "big_roads", ((0.0, 0.0), (gap, 0.0)), False, dict(TAGS_R))
    far_tns = [_Tn("tunnel:-101@0", (0.0, 0.0), (-101,)),
               _Tn("tunnel:-102@0", (gap + pair_m + 10.0, 0.0), (-102,))]
    assert _mint(law, [bore_a, bore_b, road], far_tns)[0] == []


def test_the_face_never_overlaps_an_existing_cell(law):
    """The 1206 corridor mint's own construction: minus every cell, so a
    mouth road never lies on pavement, a pad or a corridor."""
    ways, tns = _pair()
    covering = Cell(0, "apron", "pav1",
                    ((0.0, -50.0), (40.0, -50.0), (40.0, 50.0), (0.0, 50.0)),
                    (), None, None, "airside", "apron", {})
    faces, _n = _mint(law, ways, tns, cells=[covering])
    assert faces, "the far half is still a road"
    cov = Polygon(covering.ring)
    for f in faces:
        assert Polygon(f.ring, f.holes).intersection(cov).area < 1e-6


# ── §34 (13) (3) the raw pair ───────────────────────────────────────────

def test_the_contact_row_has_its_own_hard_head(law):
    """Only the RUNWAY-CONTACT rows are constraints.  MEASURED: hardening
    all 1,591 LEMD raw pairs leaves 10,006 of 109,240 hard rows violated,
    worst 60.48 m; the contact subset is 62 rows."""
    from auto_patch_v2.constraints.transverse import (RAW_PAIR_CONTACT_RULING,
                                                      RAW_PAIR_RULING)
    from auto_patch_v2.solve.design_roles import hard_rulings, one_way_rulings
    plain = RAW_PAIR_RULING.split(" (")[0]
    contact = RAW_PAIR_CONTACT_RULING.split(" (")[0]
    assert plain != contact
    assert contact in hard_rulings(law) and contact in one_way_rulings(law)
    assert plain not in hard_rulings(law), (
        "hardening every raw pair is infeasible — only the contact is a "
        "constraint")
    assert plain in one_way_rulings(law)
