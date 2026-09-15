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
from shapely.geometry import Polygon

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, OsmWay, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.structures import airside_cut_roles, build_structures
from auto_patch_v2.planar.zones import shore_region, zone_regions


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
    against aprons ``pav32`` / ``pav30``.  The scoping is the caller's —
    asserted here at the site that reads it."""
    import inspect
    from auto_patch_v2.planar import structures as _s
    src = inspect.getsource(_s.build_structures)
    assert "if c is None and g.kind != WALL_KIND:" in src


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
