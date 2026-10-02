"""Twins for issue #150's remaining §7 criterion: THE PLATEAU CUT'S REST
PARTS NEVER MINT AN AIRSIDE FACE OUTSIDE THE PLATEAU RINGS.

``planar/pad_cut.plateau_cut`` splits an apron region into its plateau
piece and the REST.  The piece is quantised to the region's own ring
stations, and where it runs a CHORD between two stations the ring bulges
past, ``region - piece`` pinches off a SCRAP: measured at KCLT ~40
``pav14`` parts of 0-6 m2 within 1-23 m of the restored building84
plateau, at SPJC ~21 ``pav49`` parts of 1-5 m2 (lane sweep1005attr on
#150, RULINGS 2026-10-02q).  Each one emitted is a face of 4-5 airside
vertices minted outside every plateau ring.

``_dissolve_rest_slivers`` is the rule: a rest part under the
IDENTITY-SPACING AREA (``(identity.min_distinct_spacing_m x
terrace.sliver_area_factor)**2`` = 16 m2, the law's own number, read by
``overlay.merge_slivers`` for the same artefact class) is unioned into the
part of its own host region it borders longest -- another REST part first,
then the host's PLATEAU PIECE -- and is never a face of its own.  A part
at or above that area is a cell and stays one.
"""
from __future__ import annotations

import pytest
from shapely.geometry import Polygon
from shapely.ops import unary_union

from auto_patch_v2.law import Law
from auto_patch_v2.planar.pad_cut import (_dissolve_rest_slivers,
                                          _identity_sliver_m2)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _rect(x0, y0, x1, y1) -> Polygon:
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _coords(g) -> set:
    return {(round(float(x), 6), round(float(y), 6))
            for ring in (g.exterior, *g.interiors) for x, y in ring.coords}


def _apron(bulge: float) -> Polygon:
    """An apron whose north edge carries a station the ring bulges to: the
    KCLT scallop class, ``bulge`` m of bulge over a 20 m chord."""
    return Polygon([(-50.0, 0.0), (50.0, 0.0), (50.0, 10.0), (10.0, 10.0),
                    (0.0, 10.0 + bulge), (-10.0, 10.0), (-50.0, 10.0)])


#: the plateau piece, quantised to the ring stations at x = -10 and x = 10:
#: its north edge CHORDS the bulge the ring stands past
PIECE = _rect(-10.0, 0.0, 10.0, 10.0)


def test_the_identity_spacing_area_is_the_law_s_own_number(law):
    ident = float(law.tables.emit.identity.min_distinct_spacing_m)
    factor = float(law.tables.emit.terrace.sliver_area_factor)
    assert _identity_sliver_m2(law) == (ident * factor) ** 2 == 16.0


def test_a_sub_spacing_scrap_is_dissolved_and_the_apron_is_unchanged(law):
    """The #150 case: one plateau piece whose rest leaves a scrap under the
    identity-spacing area.  The scrap is dissolved, the apron face set
    outside the plateau ring is unchanged face for face and station for
    station, and the plateau piece is whole."""
    region = _apron(1.0)
    parts = sorted(region.difference(PIECE).geoms, key=lambda g: g.area)
    assert len(parts) == 3, "a body each side of the piece, plus the scallop"
    assert round(parts[0].area, 6) == 10.0, "the fixture's scallop is sub-spacing"

    rests, pieces, stats = _dissolve_rest_slivers(
        list(parts), [PIECE], _identity_sliver_m2(law))

    assert (stats["dissolved"], stats["dropped"], stats["m2"]) == (1, 0, 10.0)
    # the apron's own faces: the two bodies, no third
    assert len(rests) == 2
    assert sorted(round(g.area, 6) for g in rests) == [400.0, 400.0]
    # SAME STATIONS, the §7 bar: 0 added / 0 removed OUTSIDE the plateau
    # rings.  Every apron vertex is one the uncut region ring carried or
    # one the plateau ring owns, and the only station the apron gives up
    # is the bulge the plateau took with the scrap
    ring = _coords(region)
    plateau = _coords(pieces[0])
    for g in rests:
        assert not (_coords(g) - ring - plateau), (
            "an apron station outside the plateau ring the region never had")
    gone = ring - set().union(*(_coords(g) for g in rests))
    assert gone == {(0.0, 11.0)} and gone <= plateau, gone
    # the piece is WHOLE -- one face, the scrap inside it, nothing lost
    assert len(pieces) == 1 and pieces[0].geom_type == "Polygon"
    assert pieces[0].contains(PIECE.buffer(-1e-9))
    assert round(pieces[0].area, 6) == 210.0
    assert unary_union([*rests, *pieces]).symmetric_difference(region).area < 1e-9


def test_a_scrap_above_the_threshold_stays_a_face(law):
    """A rest part at or over the identity-spacing area is a cell: the
    dissolve does not touch it, and the plateau does not grow."""
    region = _apron(5.0)
    parts = sorted(region.difference(PIECE).geoms, key=lambda g: g.area)
    assert round(parts[0].area, 6) == 50.0 > _identity_sliver_m2(law)

    rests, pieces, stats = _dissolve_rest_slivers(
        list(parts), [PIECE], _identity_sliver_m2(law))

    assert (stats["dissolved"], stats["dropped"], stats["m2"]) == (0, 0, 0.0)
    assert len(rests) == 3
    assert round(pieces[0].area, 6) == round(PIECE.area, 6)


def test_the_host_s_own_rest_part_comes_before_the_plateau_piece(law):
    """The scrap goes to the HOST REGION's own face even when the plateau
    piece borders it longer: a rest part is the same role and the same ref,
    so nothing about the host changes but the run of ring coming back."""
    scrap = _rect(0.0, 10.0, 5.0, 12.0)          # 10 m2
    body = _rect(-50.0, 10.0, 0.0, 12.0)         # shares 2 m at x = 0
    piece = _rect(0.0, 0.0, 20.0, 10.0)          # shares 5 m along y = 10

    rests, pieces, stats = _dissolve_rest_slivers(
        [body, scrap], [piece], _identity_sliver_m2(law))

    assert (stats["dissolved"], stats["dropped"]) == (1, 0)
    assert len(rests) == 1 and round(rests[0].area, 6) == 110.0
    assert round(pieces[0].area, 6) == round(piece.area, 6), "the plateau grew"


def test_the_tie_reads_only_the_two_candidates(law):
    """Two hosts bordering the scrap by the SAME run take it to a tie, and
    the tie is broken by the candidates' own geometry -- never by their
    order in the list (the #81 rule; a plateau cut hundreds of metres away
    reorders every part otherwise)."""
    scrap = _rect(-1.0, 10.0, 1.0, 11.0)         # 2 m2
    west = _rect(-21.0, 10.0, -1.0, 11.0)        # shares 1 m at x = -1
    east = _rect(1.0, 10.0, 21.0, 11.0)          # shares 1 m at x = 1
    assert round(west.area, 6) == round(east.area, 6)

    won = set()
    for order in ([west, east, scrap], [east, west, scrap],
                  [scrap, west, east], [scrap, east, west]):
        rests, _p, stats = _dissolve_rest_slivers(
            list(order), [], _identity_sliver_m2(law))
        assert stats["dissolved"] == 1
        grown = [g for g in rests if round(g.area, 6) == 22.0]
        assert len(grown) == 1
        won.add("west" if grown[0].bounds[0] < 0.0 else "east")
    assert won == {"west"}, won


def test_a_scrap_bordering_nothing_is_dropped(law):
    """A part that borders no face of its host region has no host to
    dissolve into and is dropped, exactly as a part under the cut's own
    area floor is: the DEM owns it."""
    scrap = _rect(100.0, 100.0, 101.0, 101.0)
    body = _rect(-50.0, 0.0, 0.0, 10.0)

    rests, pieces, stats = _dissolve_rest_slivers(
        [body, scrap], [PIECE], _identity_sliver_m2(law))

    assert (stats["dissolved"], stats["dropped"], stats["m2"]) == (0, 1, 1.0)
    assert len(rests) == 1 and rests[0].equals(body)
    assert round(pieces[0].area, 6) == round(PIECE.area, 6)


def test_a_chain_of_scraps_resolves_into_the_body(law):
    """Smallest first: a scrap dissolving into a scrap that is itself under
    the bar does not leave the second one standing as a face."""
    body = _rect(-50.0, 0.0, 0.0, 10.0)
    near = _rect(0.0, 0.0, 1.0, 10.0)            # 10 m2, borders the body
    far = _rect(1.0, 0.0, 1.5, 10.0)             # 5 m2, borders only `near`

    rests, _p, stats = _dissolve_rest_slivers(
        [body, near, far], [], _identity_sliver_m2(law))

    assert (stats["dissolved"], stats["dropped"]) == (2, 0)
    assert len(rests) == 1 and round(rests[0].area, 6) == 515.0
