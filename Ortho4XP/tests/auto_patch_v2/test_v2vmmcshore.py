"""§34 (12) / §37 (11) TWINS — A TUNNEL SERVES THE FIELD OR IS NOT BUILT;
THE SHORE TRIMS THE ZONES (owner RULINGS 2026-09-15f; Fable 2026-09-15i;
spec ``design-surface-spec.md`` §34 (12), §37 (11)) — lane `v2vmmcshore`.

The defects these twins hold down, both read at VMMC 1.0.340:

* eleven ``tunnel_ramp`` faces and nineteen rims ran 600 m along the
  Taipa seafront from an OSM ``highway=service tunnel=yes`` bore — a car
  park ramp under a building that has nothing to do with the aerodrome —
  and knifed code-E junction ``pav5`` into six faces at 3.58–4.50 m
  against the 6.10 m field, because only the runway family was exempt
  from a corridor cut (08-07 ruling 4);
* thirteen zone faces crossed the coastline by 3–195 m and their rings
  stood at exactly 0.00 up to 42 m seaward of it — the second,
  translucent water plane in the owner's screenshot.

One synthetic airport per case; law values are read from the tables.
"""
from __future__ import annotations

import pytest
import dataclasses as _dc

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, OsmWay, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.structures import airside_cut_roles, build_structures
from auto_patch_v2.planar.zones import shore_region, zone_regions

_dc_replace = _dc.replace


class _PlaneDem:
    provenance = {"synthetic": "flat 700 m"}

    def z(self, x: float, y: float) -> float:
        return 700.0

    def bounds(self):
        return (-20000.0, -20000.0, 20000.0, 20000.0)


class _SeaDem(_PlaneDem):
    """A DEM that also answers the SEA question (``sea_geometry``, the
    coastline partition's own product): everything south of
    ``y = y_shore`` is sea, in the frame's own metres."""

    def __init__(self, y_shore: float = -30.0) -> None:
        self.y_shore = float(y_shore)

    def sea_geometry(self, bounds=None):
        return Polygon(((-5000.0, -5000.0), (5000.0, -5000.0),
                        (5000.0, self.y_shore), (-5000.0, self.y_shore)))


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


TAGS_T = {"highway": "service", "tunnel": "yes", "lanes": "2"}
TAGS_R = {"highway": "service", "lanes": "2"}


def _cells(extra=()):
    """A runway, an apron the bore may pass under, a code-E JUNCTION 30 m
    from the apron's edge (VMMC's ``pav5``), and a groundside lot."""
    return [
        Cell(0, "runway", "09/27", _rect(-600, 500, 600, 545), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "apron", "apron1", _rect(-80, -60, 80, 60), (), None, None,
             "airside", "apron", {}),
        Cell(2, "junction", "pav5", _rect(120, -60, 320, 60), (), None, "E",
             "airside", "junction", {}),
        Cell(3, "parking_lot", "lot1", _rect(-600, -300, -200, -100), (),
             None, None, "groundside", "lot", {}),
    ] + list(extra)


def _run(law, bore_pts, approaches=(), cells=None):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 522.5), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 522.5), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    ways = [OsmWay(-101, "big_roads", tuple(bore_pts), False, TAGS_T)]
    ways += [OsmWay(-200 - i, "big_roads", tuple(a), False, TAGS_R)
             for i, a in enumerate(approaches)]
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                      (), (), (), tuple(ways), (), (), pack, _PlaneDem(),
                      law.ruleset_key)
    cl = Classification(tuple(_cells() if cells is None else cells), (), {}, ())
    return build_structures(airport, cl, law)


# ── §34 (12) (1) IS WITHDRAWN: admission is by the mouth ────────────────

def test_admission_is_by_the_mouth_and_nothing_else(law):
    """§34 (12) (1) WITHDRAWN (Fable 2026-09-15; RULINGS 2026-09-15w).

    Round 1 read (1) as "a tunnel is built only where its bore passes
    under a cover class" and measured the price at LEMD by dry pair:
    **54 tunnels → 16**, the 38 lost being owner 2026-09-12ab's "Build
    them" population.  A mapped bore whose mouth stands on the field is
    BUILT whether or not it passes under an airport surface — here the
    bore runs entirely through the GROUNDSIDE lot and is built, because
    its mouth is on the field.  What stops VMMC's seafront line is
    (2)-(4), and this twin is what forbids the reversal coming back."""
    _cl2, tunnels, st = _run(law, ((-600.0, -200.0), (-200.0, -200.0)),
                             (((-200.0, -200.0), (-100.0, -100.0)),))
    assert st.bores == 1 and st.bores_no_mouth == 0
    assert st.tunnels >= 1 and tunnels
    assert not hasattr(st, "bores_no_service")


# ── §34 (12) (3): a corridor never cuts airside pavement ─────────────────

def test_the_airside_cut_set_is_the_whole_airside_role_set(law):
    """§34 (12) (3): the exemption list is EMPTY — every airside role that
    carries a surface of its own is protected, not the runway family
    alone.  Read from ``precedence.toml``, never typed out."""
    roles = set(airside_cut_roles(law))
    for r in ("runway", "runway_crossing", "junction", "apron", "stub",
              "primary_parallel", "secondary_parallel", "cross_connector"):
        assert r in roles, r
    # a pad keeps its own machinery (``tunnel.ramp_crosses_pad`` STOPS the
    # ramp at the pad edge instead of refusing the corridor)
    assert "building" not in roles
    # and nothing groundside is in it
    assert "parking_lot" not in roles and "graded_strip" not in roles


def test_a_ramp_walking_at_a_junction_STOPS_SHORT_of_it(law):
    """§34 (12) (3) AS AMENDED — THE VMMC DEFECT.  The bore runs under the
    apron and its ramp then walks east toward code-E junction ``pav5``.
    The corridor is NOT refused: the ramp STOPS SHORT of the pavement
    (the ruling's own words), so ``pav5`` keeps its own surface and no
    ramp face stands on it."""
    cl2, tunnels, st = _run(law, ((-80.0, 0.0), (80.0, 0.0)),
                            (((80.0, 0.0), (400.0, 0.0)),))
    assert tunnels, st.refused
    pav5 = next(p for p in (Polygon(_rect(120, -60, 320, 60)),))
    ramps = [Polygon(c.ring, c.holes) for c in cl2.cells
             if c.role == "tunnel_ramp"]
    assert ramps, "the corridor is built, not refused"
    for r in ramps:
        assert r.intersection(pav5).area < 1e-6
    # and pav5 is still ONE face, uncut
    assert sum(1 for c in cl2.cells if c.ref.startswith("pav5")) == 1


def test_a_pack_stated_corridor_is_never_bound_by_clause_3(law):
    """§34 (12) (3) is SCOPED TO OSM-DERIVED CORRIDORS (RULINGS
    2026-09-15w).  A pack-stated corridor (§33 (6) signatures — an
    object corridor, a wall corridor, a plate) is authored geometry and
    its crossing of airside IS an underpass by authorship.  Measured at
    OTHH: bound by (3) it refused three terminal tunnels
    (``tunnel middle - east`` / ``- west``, ``tunnel south west 2``)
    against aprons ``pav32`` / ``pav30``.

    Asserted at the ONE site that reads the scoping: a corridor record
    (or a wall corridor) keeps the building pads alone; an OSM bore adds
    the airside faces."""
    from auto_patch_v2.planar.structure_service import osm_stops

    class _G:
        kind, members, mouth = "bore", (), (0.0, 0.0)

    cells = _cells()
    polys = [Polygon(c.ring, c.holes) for c in cells]
    pads = [(polys[1], "building1")]
    roles = set(airside_cut_roles(law))
    packed, _t = osm_stops(object(), _G(), cells, polys, pads, None, roles,
                           (), (), 0.5, "wall")
    assert packed == pads          # a pack-stated corridor: pads alone
    osm, _t2 = osm_stops(None, _G(), cells, polys, pads, None, roles,
                         (), (), 0.5, "wall")
    assert len(osm) > len(pads)
    assert any(ref == "pav5" for _p, ref in osm)


# ── §34 (12) (4): a bridge severs the climb only where it crosses ───────

def test_a_bridge_running_ALONGSIDE_the_corridor_does_not_sever_the_climb(law):
    """§34 (12) (4).  A mapped ``bridge=yes`` way that runs ALONGSIDE the
    approach the ramp walks does not sever the climb; one that CROSSES it
    does.

    The shipped test is the ALONGSIDE limb: a bridge whose run inside the
    corridor exceeds ``_DECK_ALONGSIDE_MAX`` times its own carriageway
    width is not an over-crossing.  It is armed only for a group that has
    BORES (an OSM corridor), never for a pack-stated one.

    THE OTHER LIMB — "it must cross the BORE, within the corridor's own
    width" — is MEASURED AND REFUTED (lane v2vmmcshore r3): right at VMMC,
    where the two decks holding ``tunnel:-2488@0``'s floor flat stand
    137.2 m and 46.7 m from a 36.6 m bore; wrong at LEMD, where it dropped
    ALL SEVEN decks including ``bridge_deck:-6288`` (§33 (4) / RULINGS
    2026-09-14bp item 10).  Its absence is what this twin's second half
    pins, so the reversal cannot arrive unnoticed."""
    from auto_patch_v2.planar.structure_deck import (_DECK_ALONGSIDE_MAX,
                                                     deck_intervals)
    from shapely.geometry import LineString
    from shapely.strtree import STRtree

    axis = LineString([(0.0, 0.0), (0.0, 400.0)])
    bore = LineString([(0.0, -40.0), (0.0, 0.0)])
    wd = 7.0

    class _W:
        def __init__(self, pts):
            self.points, self.id, self.tags = pts, -9, {"bridge": "yes",
                                                        "width": str(wd)}

    across = _W([(-60.0, 200.0), (60.0, 200.0)])          # a real crossing
    # VMMC's shape: a seafront way that FOLLOWS the winding approach,
    # clipping the corridor again and again — each clip is steep enough
    # to pass the 30-degree gate, and together they run far more than the
    # way's own width through the corridor
    beside = _W([(-30.0, 20.0), (30.0, 60.0), (-30.0, 100.0), (30.0, 140.0),
                 (-30.0, 180.0), (30.0, 220.0), (-30.0, 260.0)])
    for way, want in ((across, 1), (beside, 0)):
        ln = LineString(way.points)
        got = deck_intervals(axis, wd / 2 + 2.0, [way], [ln],
                             STRtree([ln]), law, [bore])
        assert len(got) == want, (way.points, got)
    # the alongside bar is the way's OWN width, read from the law's tag
    assert _DECK_ALONGSIDE_MAX * wd == 42.0
    # ...and with NO bores (a pack-stated corridor) the limb is disarmed
    ln = LineString(beside.points)
    assert len(deck_intervals(axis, wd / 2 + 2.0, [beside], [ln],
                              STRtree([ln]), law, ())) == 1
    # THE REFUTED LIMB IS ABSENT: a bridge crossing the APPROACH far from
    # the bore still severs (LEMD's seven decks are exactly this shape)
    ln = LineString(across.points)
    assert across.points[0][1] - bore.coords[0][1] > 200.0
    assert len(deck_intervals(axis, wd / 2 + 2.0, [across], [ln],
                              STRtree([ln]), law, [bore])) == 1


def test_a_deck_severs_only_where_a_CUTTING_is_witnessed(law):
    """§34 (12) (4) AS RULED FROM THE TABLE (owner RULINGS 2026-09-15ap).

    A mapped bridge severs the climb only where the ground beneath its
    span is WITNESSED below grade — (i) the corridor's way under the span
    carries ``tunnel=yes`` / ``layer <= -1``, or (ii) the DEM under the
    span is ``[bridge] deck_cut_witness_m`` below the mean of the
    abutments.  Both numbers are the law's; nothing here is typed.

    The four cases are the measured ones (lane v2vmmcshore r5):
    LEMD `-11828` (+1.34 m of DEM cut, no tag) severs by (ii); LEMD
    `-15293` (−1.46 m, so (ii) says no) severs by (i) where its bore runs
    UNDER the span; VMMC `-2088` (0.00 m on the flat field, no tag) does
    not sever; and a deck whose feed predates the 2026-09-15 tag schema
    carries no tag at all and is judged by (ii) alone — the same path,
    which is why the ruling needs no special case for it."""
    from auto_patch_v2.planar.structure_deck import _witnessed
    from auto_patch_v2.planar.structure_service import deck_witness_for

    br = law.tables.structures.bridge
    floor = br.deck_cut_witness_m

    class _Way:
        def __init__(self, wid, pts, tags):
            self.id, self.points, self.tags = wid, tuple(pts), dict(tags)

    class _Dem:
        """Flat at 100 m but for a trench along ``x = 0``."""

        def __init__(self, depth):
            self.depth = depth

        def z(self, x, y):
            return 100.0 - (self.depth if abs(x) <= 5.0 else 0.0)

    class _Airport:
        def __init__(self, dem):
            self.dem = dem

    bore_tagged = _Way(-1568, [(0.0, -50.0), (0.0, 50.0)],
                       {"tunnel": "yes", "layer": "-1", "highway": "motorway"})
    bore_plain = _Way(-2488, [(0.0, -50.0), (0.0, 50.0)], {"highway": "service"})
    deck = _Way(-11828, [(-60.0, 0.0), (60.0, 0.0)],
                {"bridge": "yes", "highway": "tertiary"})
    span = LineString(deck.points).buffer(4.0, cap_style="flat")

    def _run(airport, unders, dpoly=span):
        w = deck_witness_for(airport, law, unders)
        return _witnessed([(deck, 10.0, 20.0, dpoly)], w)

    # (ii) alone: a real cutting, no tag on the way beneath — LEMD -11828
    cut = _Dem(1.34)
    assert 1.34 >= floor
    assert _run(_Airport(cut), [bore_plain]), "a witnessed cutting severs"

    # (i) alone: the ground is HIGHER under the span (LEMD -15293 reads
    # -1.46) but the way beneath carries layer -1
    hump = _Dem(-1.46)
    assert _run(_Airport(hump), [bore_tagged]), "the tag alone severs"
    assert not _run(_Airport(hump), [bore_plain]), "neither witness: no sever"

    # VMMC -2088: flat field, no tag — does not sever
    assert not _run(_Airport(_Dem(0.0)), [bore_plain])

    # A STALE FEED carries no tag, and is judged by (ii) alone — the same
    # path.  Under the same flat ground it does not sever; over a cutting
    # it does, whatever the feed could not say.
    stale = _Way(-9, [(0.0, -50.0), (0.0, 50.0)], {"highway": "service"})
    assert not _run(_Airport(_Dem(0.0)), [stale])
    assert _run(_Airport(_Dem(floor + 0.01)), [stale])

    # (i) IS THE CORRIDOR, NOT THE SPAN — §34 (12) (4) AMENDED (2) (owner
    # RULINGS 2026-09-16f, lane `v2vmmcbore`).  THE HISTORY, so the
    # reversal cannot come back unnoticed: r6 read (i) as "the corridor's
    # way beneath the deck's SPAN", which dropped the two decks the owner
    # then checked in the sim and confirmed span REAL CUTS — shape 981 =
    # `bridge_deck:-5305` at 40.4788711,-3.5787587 and shape 988 =
    # `bridge_deck:-15293` at 40.4659974,-3.5811339, whose bore chains
    # carry `layer -1 tunnel=yes` but end short of the crossing station
    # (s 103.3 / 146.2 m of the approach walk).  The narrow reading
    # existed ONLY to keep VMMC's seafront decks out; §34 (12) (5) now
    # keeps the seafront BORES out, so the deck reading need not.  A
    # tagged bore the span does not reach NOW severs.
    far = LineString([(200.0, -30.0), (200.0, 30.0)]).buffer(4.0,
                                                             cap_style="flat")
    assert _run(_Airport(_Dem(0.0)), [bore_tagged], far), \
        "witness (i) reads the corridor's whole bore chain (16f)"
    # and the untagged corridor over flat ground still severs nothing,
    # wherever the span stands — (ii) is unchanged and still decides alone
    assert not _run(_Airport(_Dem(0.0)), [bore_plain], far)


# ── §34 (12) (2): no structure face, rim or ramp over the water ─────────

def test_no_ramp_or_rim_stands_on_the_water(law):
    """§34 (12) (2) — "a corridor reaching the water ends at the shore".
    The bore runs under the apron and its ramp walks SOUTH, out over the
    sea.  Every emitted structure face is clipped at the coastline.

    ONE WITNESS, and it is the zone trim's: ``zones.shore_region`` (the
    tile's SEA minus the airport's own classified surfaces).  MEASURED at
    VMMC: ramp + rim standing on the sea 1,544 m² (base) -> 906
    (unclipped, once (1) was withdrawn) -> 1.7 m²."""
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 522.5), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 522.5), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    ways = [OsmWay(-101, "big_roads", ((0.0, 0.0), (0.0, -600.0)), False, TAGS_T)]
    # (the apron is x -80..80, y -60..60, so the mouth at (0, 0) is on it)
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    cells = tuple(_cells())
    dry = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                  (), (), (), tuple(ways), (), (), pack, _PlaneDem(), law.ruleset_key)
    # the ramp is built OUTWARD from the mouth at (0, 0), so it runs
    # NORTH, past the apron's own edge at y = 60; the sea lies beyond it
    # (the AIRPORT'S OWN SURFACES ARE LAND, so a sea that overlapped the
    # apron would correctly clip nothing — that is the reclaimed-land
    # reading `shore_region` exists for)
    class _NorthSea(_PlaneDem):
        def sea_geometry(self, bounds=None):
            return Polygon(((-5000.0, 70.0), (5000.0, 70.0),
                            (5000.0, 5000.0), (-5000.0, 5000.0)))

    wet = _dc_replace(dry, dem=_NorthSea())
    out = {}
    for tag, ap in (("dry", dry), ("wet", wet)):
        cl2, _t, _st = build_structures(ap, Classification(cells, (), {}, ()), law)
        out[tag] = unary_union([Polygon(c.ring, c.holes) for c in cl2.cells
                                if c.role in ("tunnel_ramp", "retaining_wall")] or [Polygon()])
    sea = Polygon(((-5000.0, 70.0), (5000.0, 70.0),
                   (5000.0, 5000.0), (-5000.0, 5000.0)))
    assert out["dry"].intersection(sea).area > 10.0, "the fixture must reach the water"
    assert out["wet"].intersection(sea).area < 1.0
    assert not out["wet"].is_empty, "the dry half of the corridor survives"


# ── §37 (11) (1)/(2): the shore trims the zones; the quay ────────────────

def _zone_cells():
    """A code-E junction whose south edge stands 10 m from the shore — the
    land runs out well inside lip + half-width (code E: 3 m lip + 19 m
    band), which is VMMC's own geometry."""
    return (Cell(0, "junction", "pav5", _rect(-200, -20, 200, 120), (),
                 None, "E", "airside", "junction", {}),)


def test_the_airports_own_surfaces_are_land_by_declaration(law):
    """§37 (11) (1) / §34 (12) (2): the water region is the witness MINUS
    every classified cell.  At VMMC 110,826 m² — 24.5 % — of the
    runway/taxi union lies inside the coastline partition's sea (the
    field is on reclaimed land), so a raw clip would cut the band away
    from the pavement it serves."""
    cells = (Cell(0, "junction", "pav5", _rect(-200, -200, 200, 120), (),
                  None, "E", "airside", "junction", {}),)
    water = shore_region(cells, _SeaDem())
    assert water is not None
    # the pavement's own footprint is NOT water, however wet the witness
    assert not water.intersects(Polygon(_rect(-199, -199, 199, 119)).buffer(-1.0))


def test_no_zone_ring_is_emitted_seaward_of_the_coastline(law):
    """§37 (11) (1): the zone region is CLIPPED by the water at its single
    derivation site — no ring, lip or band stands on the sea."""
    water = _SeaDem()
    dry = zone_regions(_zone_cells(), law, (), None, ())
    wet = zone_regions(_zone_cells(), law, (), water, ())
    assert dry and wet
    sea = water.sea_geometry()
    assert any(r.polygon.intersects(sea) for r in dry), "the fixture must be wet"
    for r in wet:
        assert r.polygon.intersection(sea).area < 1e-6, r.ref


def test_a_zone_that_reaches_the_coastline_is_a_quay(law):
    """§37 (11) (2): where the land between the pavement edge and the
    coastline is narrower than lip + half-width the zone REACHES the
    water, and that land is a QUAY — one plane at the pavement edge's
    level, ending at the coastline in a sea wall."""
    wet = zone_regions(_zone_cells(), law, (), _SeaDem(), ())
    quays = [r for r in wet if r.quay]
    assert quays, [r.ref for r in wet]
    # ...and a region nowhere near the water is NOT a quay
    inland = zone_regions(_zone_cells(), law, (), _SeaDem(-5000.0), ())
    assert not any(r.quay for r in inland)


def test_the_shore_trim_is_reported(law):
    """The trim states its own numbers (the build's ``terrain edge`` line),
    so the region a lane cut is visible without a rebuild."""
    from auto_patch_v2.planar.terrain_edge import EdgeReport
    rep = EdgeReport()
    zone_regions(_zone_cells(), law, (), _SeaDem(), (), rep)
    assert rep.shore_regions > 0
    assert rep.shore_cut_m2 > 0.0
    assert "SHORE" in rep.line()


# ── §37 (11) (5): the sea-wall family and its exclusion ──────────────────

def _grade_law():
    import importlib.util
    import pathlib
    import sys
    root = pathlib.Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "check_grade_twin", root / "tools" / "check_grade.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_grade_twin"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_the_sea_wall_family_is_registered_and_never_adjudicates():
    """§37 (11) (5): ``sea_wall`` is a law family of its own, and its rows
    are stamped so acceptance never counts a lawful wall."""
    cg = _grade_law()
    keys = [k for k, *_ in cg.LAW_FAMILIES]
    assert "sea_wall" in keys
    assert cg.SEA_WALL_OUT_OF_SCOPE in cg.OUT_OF_SCOPE_CLASSES
    assert cg.SEA_WALL_TEAR_OUT_OF_SCOPE in cg.OUT_OF_SCOPE_CLASSES


def test_a_tear_whose_two_vertices_stand_on_the_shore_is_the_wall():
    """§37 (11) (5): "the tear IS the wall" — a ``strip_seam_tear`` /
    ``adjacent_ground_step`` row on the declared shore is stamped out of
    the acceptance count, and one INLAND is untouched."""
    cg = _grade_law()

    class _Row:
        def __init__(self, lat, lon):
            self.lat, self.lon = lat, lon
            self.out_of_scope = None

    shore = [[0.0, 0.0, 0.0, 0.01]]          # a shore segment along lon
    nodes = {}

    def ll_to_m(lat, lon):
        return (lon * 100000.0, lat * 100000.0)

    on = _Row(0.0, 0.005)
    off = _Row(0.01, 0.005)                  # ~1 km inland
    n = cg.stamp_sea_wall_tears([on, off], shore, nodes, ll_to_m)
    assert n == 1
    assert on.out_of_scope == cg.SEA_WALL_TEAR_OUT_OF_SCOPE
    assert off.out_of_scope is None


def test_a_patch_with_no_shore_key_reads_exactly_as_before():
    """A patch built before §39 (1) declares no ``shore_edges``: the
    family reports nothing and stamps nothing — never a guess."""
    cg = _grade_law()

    class _Row:
        lat, lon, out_of_scope = 0.0, 0.0, None

    assert cg._check_sea_wall(None, {}, [], lambda a, b: (0.0, 0.0)) == []
    assert cg.stamp_sea_wall_tears([_Row()], None, {}, lambda a, b: (0.0, 0.0)) == 0
