"""Post-merge integration twins (lane v2integ, 2026-09-05; report
``docs/specs/auto-patch-v2/m5g-report.md``).

* the verify reader's stretch join covers HOLE-RING vertices — LEMD face
  145 / taxi660: a taxi centreline entering a cross_connector's gap
  interior ring put a stretch endpoint on a vertex no outer ring holds,
  and ``within_shape`` raised ``KeyError`` (the seven-airport re-census of
  2026-09-04, main ``7ddf3f5b``).
"""
from __future__ import annotations

import math

import pytest

from auto_patch_v2.emit.surface import GradedSurface, SurfaceBreakline, SurfaceFace, SurfaceVertex
from auto_patch_v2.law import Law
from auto_patch_v2.verify.frame import Patch
from auto_patch_v2.verify.within import within_shape

LAT0, LON0 = 40.47, -3.57
R = 6378137.0


def _ll(x: float, y: float) -> tuple[float, float]:
    return (round(LAT0 + math.degrees(y / R), 11),
            round(LON0 + math.degrees(x / (R * math.cos(math.radians(LAT0)))), 11))


@pytest.fixture(scope="module")
def law() -> Law:
    return Law.for_airport("LEMD")


def _holed_connector(z_hole: float) -> tuple[GradedSurface, dict]:
    """A 200 m x 40 m cross_connector (letter F, 1.5 %) with a 10 m gap
    interior ring; a published stretch (letter B, 3 %) runs along the
    connector from the west ring edge to the HOLE's west vertex —
    LEMD's taxi660 entering face 145's gap."""
    pts = {
        0: (0.0, 0.0), 1: (200.0, 0.0), 2: (200.0, 40.0), 3: (0.0, 40.0),
        # the hole (a gap interior ring), ids 10..13
        10: (95.0, 15.0), 11: (105.0, 15.0), 12: (105.0, 25.0), 13: (95.0, 25.0),
        # the stretch's ring endpoint on the west edge
        20: (0.0, 20.0),
    }
    z = {0: 600.0, 1: 600.0, 2: 600.0, 3: 600.0, 20: 600.0,
         10: z_hole, 11: z_hole, 12: z_hole, 13: z_hole}
    verts = tuple(SurfaceVertex(i, _ll(*pts[i]), z[i]) for i in sorted(pts))
    face = SurfaceFace(145, "cross_connector", "pav84", (0, 1, 2, 3, 20),
                       ((10, 11, 12, 13),), "airside", 4, "F")
    bl = SurfaceBreakline(0, "taxi_centerline", "taxi660", (20, 10))
    surf = GradedSurface("LEMD", "icao", (LAT0, LON0), "local", 7, verts, (face,), (bl,), {})
    stretch_ll = [list(_ll(*pts[20])), list(_ll(*pts[10]))]
    pub = {"stretches": [[stretch_ll, 0.03, "B", "taxi660"]], "axes": [], "crown_drops": []}
    return surf, pub


def test_a_stretch_ending_on_a_hole_ring_vertex_prices_without_a_key_error(law):
    """The reader joins stretch vertices through the FRAME's whole vertex
    map (``Patch.xy``), exactly as the generator prices through
    ``pm.vertices`` — a hole-ring vertex on a stretch is a vertex, not a
    ``KeyError`` (LEMD 8521, 2026-09-04)."""
    surf, pub = _holed_connector(z_hole=600.0)
    within, xsec = within_shape(Patch.of(surf, law, pub, {}))
    assert within == [] and xsec == []


def test_the_outer_ring_pairs_are_still_priced_at_the_face_cap_with_the_hole_present(law):
    """A 2 % step across the ring (over F's 1.5 %) still reads as a row
    when the stretch reaches the hole: the join change adds vertices to
    the stretch map, never removes pairs from the ring's population."""
    surf, pub = _holed_connector(z_hole=600.0)
    # lift the north-east ring vertex 2 % over the 200 m length
    verts = tuple(SurfaceVertex(v.id, v.ll, 604.0 if v.id == 2 else v.z) for v in surf.vertices)
    surf2 = GradedSurface(surf.icao, surf.ruleset, surf.origin, surf.crs, surf.identity_dp,
                          verts, surf.faces, surf.breaklines, surf.provenance)
    within, _x = within_shape(Patch.of(surf2, law, pub, {}))
    assert within and all(abs(r["cap_pct"] - 1.5) < 1e-9 for r in within), within[:2]


# ── the last resort reads rows, never their reach envelope (HECA 2026-09-05) ──

from auto_patch_v2.constraints import generate
from auto_patch_v2.model.constraints import REACH_GENERATOR, Band, Diff, Linear, Source
from auto_patch_v2.solve import relax
from auto_patch_v2.solve.tiers import row_tier
from auto_patch_v2.law.tables import tiers as _tiers


@pytest.fixture(scope="module")
def hangar():
    from tests.auto_patch_v2.test_relax import _hangar_row
    law = Law.for_airport("ZZZZ")
    airport, pm = _hangar_row(law)
    cs, _counts, _w = generate(pm, law, airport)
    return law, airport, pm, cs


def test_an_apron_law_row_on_a_junction_face_relaxes_at_the_apron_tier(hangar):
    """04t-2's apron cap on a taxi face's edge along the apron is an APRON
    row: ``relaxable`` admits it although the face is taxi-family; the
    same pair under the taxi law is refused (HECA junction pav132)."""
    law, airport, pm, cs = hangar
    stub = next(f for f in pm.faces.values() if f.role == "stub")
    vs = [v for v in pm.vertices if stub.id in pm.vertices[v].incident_faces][:2]
    a, b = vs
    d = math.hypot(pm.vertices[a].xy[0] - pm.vertices[b].xy[0],
                   pm.vertices[a].xy[1] - pm.vertices[b].xy[1])
    apron_row = Diff(a, b, 0.01, d, Source("apron", "apron edge portion (04t-2)", (f"face:{stub.id}",)))
    taxi_row = Diff(a, b, 0.015, d, Source("taxi", "taxi within_shape", (f"face:{stub.id}",)))
    tt = _tiers(law)
    tier_of = {r: k for k, t in enumerate(tt) for r in t}
    assert row_tier(pm, apron_row, tier_of, len(tt) - 1) == tier_of["stub"]
    assert [x.kind for x in relax.relaxable(pm, law, [apron_row])] == ["diff"]
    assert relax.relaxable(pm, law, [apron_row])[0].tier == tier_of["apron"]
    assert relax.relaxable(pm, law, [taxi_row]) == []


def test_envelope_free_sets_aside_exactly_the_reach_bands(hangar):
    law, airport, pm, cs = hangar
    reach = [r for r in cs.rows() if isinstance(r, Band) and r.source.generator == REACH_GENERATOR]
    assert reach, "the fixture carries reach bands from its two pins"
    free = relax.envelope_free(cs)
    assert not [r for r in free.rows() if isinstance(r, Band) and r.source.generator == REACH_GENERATOR]
    assert len(list(free.rows())) == len(list(cs.rows())) - len(reach)
    # the other bands (zones, none here) and every Diff/Linear/Flat/Pin stay
    kinds = lambda c: sorted(type(r).__name__ for r in c.rows() if not (
        isinstance(r, Band) and r.source.generator == REACH_GENERATOR))
    assert kinds(free) == kinds(cs)


def test_the_hangar_row_still_relaxes_on_the_envelope_free_set(hangar):
    """The existing last-resort behaviour is unchanged where it applied:
    the hangar row relaxes, and the relaxed hard set carries no reach band."""
    from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS
    from auto_patch_v2.solve import Options
    law, airport, pm, cs = hangar
    sol, rep, cs2 = relax.solve_relaxed(pm, cs, law, DEFAULT_WEIGHTS, Options())
    assert rep.applied and sol is not None, rep.line()
    assert not [r for r in cs2.rows() if isinstance(r, Band) and r.source.generator == REACH_GENERATOR]


# ── a rigid pad inside the strip is banded through its rim (KCLT 2026-09-05) ──

def test_a_pad_inside_a_taxi_strip_carries_zone_bands_on_its_rim():
    """A shed 8 m east of stub E, inside taxiway D's zone 2 and touching
    no airside pavement: its rim vertices are strip vertices and carry
    the zone band (the FLAT row then lifts the pad to it) — before, every
    airside value face's vertices were exempt, pads included, and the
    pad floated to its DEM (KCLT building26, 24 tear rows)."""
    from tests.auto_patch_v2.test_relax import _Dem, _rect
    from auto_patch_v2.classify.roles import Cell, Classification, CutLine
    from auto_patch_v2.constraints.zones import zone_bands
    from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
    from auto_patch_v2.model.frame import Frame
    from auto_patch_v2.planar.build import build
    law = Law.for_airport("ZZZZ")
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 718.0, "fixture"))
    runways = [Runway("09/27", 45.0, 1, ends, 3, "D")]
    cells = [
        Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D", "airside", "runway", {}),
        Cell(1, "stub", "stubE", _rect(138.5, 22.5, 161.5, 120), (), None, "D", "airside", "taxi", {}),
        Cell(2, "building", "shed", _rect(170, 60, 182, 80), (), None, None, "airside", "pad", {}),
    ]
    cuts = [CutLine("taxi_centerline", "stubE", ((150.0, 0.0), (150.0, 120.0)))]
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, tuple(runways), (), (), {},
                      (), (), (), (), (), (), (), pack, _Dem(), law.ruleset_key)
    pm, _stats = build(airport, Classification(tuple(cells), tuple(cuts), {}, ()), law)
    pad = next(f for f in pm.faces.values() if f.role == "building")
    rim = {v for v in pm.vertices if pad.id in pm.vertices[v].incident_faces}
    strip_rim = {v for v in rim if any(pm.faces[f].role == "graded_strip"
                                       for f in pm.vertices[v].incident_faces)}
    assert strip_rim, "the shed's rim is welded into the strip"
    rows = zone_bands(pm, law, airport)
    banded = {v for r in rows if isinstance(r, Linear) for v, _c in r.terms} & strip_rim
    assert banded, "no zone band on the pad's strip-rim vertices"


def test_a_pad_in_the_strip_is_one_level_the_nearest_rim_carries_the_band():
    """The shed's rim spans zone 1 and zone 2; a flat plane cannot meet
    both bands, so exactly ONE rim vertex (the nearest to the lip) carries
    a ceiling and every other rim vertex a floor only — and the hard set
    with the pad stays feasible."""
    from tests.auto_patch_v2.test_relax import _Dem, _rect
    from auto_patch_v2.classify.roles import Cell, Classification, CutLine
    from auto_patch_v2.constraints.zones import zone_bands
    from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
    from auto_patch_v2.model.frame import Frame
    from auto_patch_v2.planar.build import build
    from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS
    from auto_patch_v2.solve import Options, Status
    from auto_patch_v2.solve.highs import solve as solve_hard
    law = Law.for_airport("ZZZZ")
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 718.0, "fixture"))
    runways = [Runway("09/27", 45.0, 1, ends, 3, "D")]
    cells = [
        Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D", "airside", "runway", {}),
        Cell(1, "stub", "stubE", _rect(138.5, 22.5, 161.5, 120), (), None, "D", "airside", "taxi", {}),
        Cell(2, "building", "shed", _rect(164, 60, 178, 80), (), None, None, "airside", "pad", {}),
    ]
    cuts = [CutLine("taxi_centerline", "stubE", ((150.0, 0.0), (150.0, 120.0)))]
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, tuple(runways), (), (), {},
                      (), (), (), (), (), (), (), pack, _Dem(), law.ruleset_key)
    pm, _stats = build(airport, Classification(tuple(cells), tuple(cuts), {}, ()), law)
    pad = next(f for f in pm.faces.values() if f.role == "building")
    rim = {v for v in pm.vertices if pad.id in pm.vertices[v].incident_faces}
    rows = [r for r in zone_bands(pm, law, airport) if isinstance(r, Linear)
            and r.terms[0][0] in rim]
    assert rows
    with_ceiling = {r.terms[0][0] for r in rows if r.hi is not None}
    assert len(with_ceiling) == 1, with_ceiling
    assert {r.terms[0][0] for r in rows} - with_ceiling, "the far rim carries floors"
    cs, _c, _w = generate(pm, law, airport)
    sol = solve_hard(pm, cs, DEFAULT_WEIGHTS, Options(diagnose_iis=False))
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
