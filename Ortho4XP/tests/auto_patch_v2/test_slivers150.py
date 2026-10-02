"""Twins for issue #150's remaining §7 criterion -- THE PLATEAU CUT'S REST
PARTS NEVER MINT AN AIRSIDE FACE OUTSIDE THE PLATEAU RINGS -- and for the
OWNER RULING that decides whose the rest parts are (RULINGS 2026-10-02x
(2)): "if scraps refer to building connected pieces like walls, then
better to stay with the pad, if it's flat planes representing something on
the ground, then join the apron".

``planar/pad_cut.plateau_cut`` splits an apron region into its plateau
piece and the REST.  The piece is quantised to the region's own ring
stations, and where it runs a CHORD between two stations the ring bulges
past, ``region - piece`` pinches off a SCRAP: measured at KCLT ~40
``pav14`` parts of 0-6 m2 within 1-23 m of the restored building84
plateau, at SPJC ~21 ``pav49`` parts of 1-5 m2 (lane sweep1005attr on
#150, RULINGS 2026-10-02q).

``_dissolve_rest_slivers`` is the rule.  A rest part under the
IDENTITY-SPACING AREA (``(identity.min_distinct_spacing_m x
terrace.sliver_area_factor)**2`` = 16 m2, the law's own number, read by
``overlay.merge_slivers`` for the same artefact class) is GROUND: it is
unioned into the part of its own HOST REGION it borders longest -- another
REST part, NEVER the plateau piece -- and the plateau never grows past its
quantised footprint.  Only a scrap standing inside the BUILDING UNIT'S
FOOTPRINT RING is structure and goes to the pad.

THE MEASURED DEFECT (RULINGS 2026-10-02w): every scrap joined the PLATEAU
piece instead (SPJC 90 / 504 m2, KCLT 211 / 977, HECA 74 / 317) and the
"another rest part first" tier NEVER FIRED, so the flat plateau grew to
the apron's own outer ring and 110 / 267 / 105 stage-1 columns with their
per-vertex ``apron_trend`` rows went with it.  The cause is what
:func:`test_the_pinched_scrap_meets_the_apron_body_at_a_point_only`
asserts.
"""
from __future__ import annotations

import pytest
import shapely
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


def test_the_pinched_scrap_meets_the_apron_body_at_a_point_only(law):
    """WHY THE "another rest part first" TIER NEVER FIRED over 375 scraps
    at three airports (RULINGS 2026-10-02w).  The quantised piece touches
    the ring AT the two stations its chord spans, so it disconnects the
    rest there: the scrap meets each apron body at a POINT, whose
    ``length`` is zero, and a union across a point is TWO polygons -- the
    scrap still standing as a face of its own under another name.  The
    plateau piece, bordering the scrap along the whole chord, won every
    time."""
    region = _apron(1.0)
    scrap, west, east = sorted(region.difference(PIECE).geoms,
                               key=lambda g: (g.area, g.bounds[0]))
    assert round(scrap.area, 6) == 10.0

    for body in (west, east):
        shared = scrap.boundary.intersection(body.boundary)
        assert shared.geom_type == "Point" and shared.length == 0.0
        assert len(shapely.get_parts(
            shapely.make_valid(body.union(scrap)))) == 2

    chord = scrap.boundary.intersection(PIECE.boundary)
    assert chord.geom_type == "LineString" and round(chord.length, 6) == 20.0


def test_a_ground_scrap_stays_the_apron_s_and_the_plateau_never_grows(law):
    """The #150 case under the ruling: the scallop is GROUND -- apron
    surface between the quantised plateau chord and the apron ring -- so
    it never joins the plateau.  Pinched off at a point it cannot be
    unioned into either apron body, so it STANDS, as an apron face of the
    host with the host's own role and ref, and is counted.  The plateau
    piece is exactly its quantised footprint and every host ring station
    is still in the apron's own face set."""
    region = _apron(1.0)
    parts = sorted(region.difference(PIECE).geoms, key=lambda g: g.area)
    assert len(parts) == 3, "a body each side of the piece, plus the scallop"
    assert round(parts[0].area, 6) == 10.0, "the fixture's scallop is sub-spacing"

    rests, pieces, stats = _dissolve_rest_slivers(
        list(parts), [PIECE], _identity_sliver_m2(law))

    assert (stats["dissolved"], stats["padded"], stats["kept"],
            stats["dropped"]) == (0, 0, 1, 0)
    assert (stats["m2"], stats["kept_m2"]) == (10.0, 10.0)
    # THE PLATEAU NEVER GROWS PAST ITS QUANTISED FOOTPRINT (the ruling)
    assert len(pieces) == 1 and pieces[0].geom_type == "Polygon"
    assert round(pieces[0].area, 6) == round(PIECE.area, 6)
    # the scrap's AREA is the apron's, not the plateau's
    assert sorted(round(g.area, 6) for g in rests) == [10.0, 400.0, 400.0]
    assert round(sum(g.area for g in rests), 6) == round(region.area - PIECE.area, 6)
    # SAME STATIONS, the §7 bar: 0 added / 0 removed OUTSIDE the plateau
    # rings.  Every apron vertex is one the uncut region ring carried or
    # one the plateau ring owns, and the bulge the plateau's chord spans
    # STAYS the apron's
    ring = _coords(region)
    plateau = _coords(pieces[0])
    for g in rests:
        assert not (_coords(g) - ring - plateau), (
            "an apron station outside the plateau ring the region never had")
    assert not (ring - set().union(*(_coords(g) for g in rests))), (
        "a host ring station left the apron's face set")
    assert (0.0, 11.0) in _coords(
        [g for g in rests if round(g.area, 6) == 10.0][0])
    assert unary_union([*rests, *pieces]).symmetric_difference(region).area < 1e-9


def test_a_scrap_above_the_threshold_stays_a_face(law):
    """A rest part at or over the identity-spacing area is a cell: the
    dissolve does not touch it, and the plateau does not grow."""
    region = _apron(5.0)
    parts = sorted(region.difference(PIECE).geoms, key=lambda g: g.area)
    assert round(parts[0].area, 6) == 50.0 > _identity_sliver_m2(law)

    rests, pieces, stats = _dissolve_rest_slivers(
        list(parts), [PIECE], _identity_sliver_m2(law))

    assert (stats["dissolved"], stats["kept"], stats["dropped"],
            stats["m2"]) == (0, 0, 0, 0.0)
    assert len(rests) == 3
    assert round(pieces[0].area, 6) == round(PIECE.area, 6)


def test_the_host_s_own_rest_part_is_the_host_never_the_plateau_piece(law):
    """A ground scrap bordering a rest part along a RUN goes to that rest
    part even though the plateau piece borders it longer -- and with no
    rest part to take it, it stays an apron face rather than joining the
    plateau (owner RULINGS 2026-10-02x (2))."""
    scrap = _rect(0.0, 10.0, 5.0, 12.0)          # 10 m2
    body = _rect(-50.0, 10.0, 0.0, 12.0)         # shares 2 m at x = 0
    piece = _rect(0.0, 0.0, 20.0, 10.0)          # shares 5 m along y = 10

    rests, pieces, stats = _dissolve_rest_slivers(
        [body, scrap], [piece], _identity_sliver_m2(law))

    assert (stats["dissolved"], stats["padded"], stats["kept"]) == (1, 0, 0)
    assert len(rests) == 1 and round(rests[0].area, 6) == 110.0
    assert round(pieces[0].area, 6) == round(piece.area, 6), "the plateau grew"

    # the same scrap with NO rest part at all: still never the plateau's
    rests, pieces, stats = _dissolve_rest_slivers(
        [scrap], [piece], _identity_sliver_m2(law))

    assert (stats["dissolved"], stats["padded"], stats["kept"]) == (0, 0, 1)
    assert len(rests) == 1 and round(rests[0].area, 6) == 10.0
    assert round(pieces[0].area, 6) == round(piece.area, 6), "the plateau grew"


def test_a_scrap_inside_the_building_footprint_ring_stays_with_the_pad(law):
    """THE RULING'S ONE EXCEPTION: a scrap standing inside the BUILDING
    UNIT'S FOOTPRINT RING is part of the building's connected structure,
    so the PAD is its host -- the plateau piece ranks ahead of the host's
    own rest part, and the piece takes it."""
    scrap = _rect(0.0, 10.0, 5.0, 12.0)          # 10 m2
    body = _rect(-50.0, 10.0, 0.0, 12.0)         # shares 2 m at x = 0
    piece = _rect(0.0, 0.0, 20.0, 10.0)          # shares 5 m along y = 10
    # the pad outline's own exterior ring, holes filled: it covers the
    # scrap and nothing of the apron body
    pad_fill = _rect(-1.0, 9.0, 21.0, 13.0)
    assert pad_fill.covers(scrap) and not pad_fill.covers(body)

    rests, pieces, stats = _dissolve_rest_slivers(
        [body, scrap], [piece], _identity_sliver_m2(law), pad_fill=pad_fill)

    assert (stats["dissolved"], stats["padded"], stats["kept"]) == (0, 1, 0)
    assert len(rests) == 1 and round(rests[0].area, 6) == round(body.area, 6)
    assert round(pieces[0].area, 6) == round(piece.area + scrap.area, 6)

    # OUTSIDE that ring the very same scrap is GROUND and the pad gets
    # nothing (the ruling's two halves read from one geometry)
    rests, pieces, stats = _dissolve_rest_slivers(
        [body, scrap], [piece], _identity_sliver_m2(law),
        pad_fill=_rect(100.0, 100.0, 120.0, 120.0))

    assert (stats["dissolved"], stats["padded"], stats["kept"]) == (1, 0, 0)
    assert round(pieces[0].area, 6) == round(piece.area, 6)


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
    dissolve into and nothing to stand against, so it is dropped, exactly
    as a part under the cut's own area floor is: the DEM owns it."""
    scrap = _rect(100.0, 100.0, 101.0, 101.0)
    body = _rect(-50.0, 0.0, 0.0, 10.0)

    rests, pieces, stats = _dissolve_rest_slivers(
        [body, scrap], [PIECE], _identity_sliver_m2(law))

    assert (stats["dissolved"], stats["kept"], stats["dropped"],
            stats["m2"]) == (0, 0, 1, 1.0)
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

    assert (stats["dissolved"], stats["kept"], stats["dropped"]) == (2, 0, 0)
    assert len(rests) == 1 and round(rests[0].area, 6) == 515.0
