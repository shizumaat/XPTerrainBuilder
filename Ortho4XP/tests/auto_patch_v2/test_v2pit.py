"""Twins for RULINGS 2026-09-10h (lane ``v2pit``) — the LEMD T4S pit.

(1) THE DEGENERATE HOLE.  A face's interior ring that is nowhere as wide as
``terrace.separation_m`` (0.5 m), or under the identity's smallest face
area, is dissolved into its face at the planar stage
(``planar.overlay.dissolve_degenerate_holes``) and mints NO vertices.  The
site: LEMD way −10892, a 35 m × 0.5 m, 3-vertex hole in apron ``pav16``
whose vertices bound no face law, carry a bending row divided by a
barycentric area of 864–5,527 m² (the sliver's Delaunay triangles span the
whole apron), and so reached the least-squares solve effectively free — the
solve put them at 582.7–583.1 against a DEM of 599.0, and the mesh coned
16.3 m down to them over 265 × 240 m (the owner's "large apron dip").  A
hole holding a real face is kept however thin.

(2) THE RIM IS A CONTACT.  A basin rim vertex an apron shares takes THAT
FACE's surface — it is one vertex, it carries one value, and
``constraints.structures.basins`` pins it at nothing (``shared_with_ground``
skips it; the DEM-by-station pin is for a BARE rim only).  ``rim_law_m`` in
the sidecar is ``Basin.rim_estimate_m``, the MEDIAN DEM around the admitted
REGION — the admission diagnostic (``basins._rim_estimate``), never the
value of a rim vertex.
"""
from __future__ import annotations

import dataclasses as _dc
import math

import pytest
from shapely.geometry import Polygon

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints.structures import basins as basin_rows
from auto_patch_v2.emit.graded import RIM_KIND, graded_surface
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import ConstraintSet, Pin
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.model.structures import Basin
from auto_patch_v2.planar.build import build
from auto_patch_v2.planar.overlay import dissolve_degenerate_holes
from auto_patch_v2.solve import Options, solve_design


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


class _Flat:
    provenance = {"synthetic": "flat 700"}

    def z(self, x: float, y: float) -> float:
        return 700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


RUNWAY = Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
              "airside", "runway", {})
Y0, Y1 = 120.0, 220.0          # the apron, clear of the code-3 strip


def _airport(law, cells, basins=()):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {},
                      (), (), (), (), (), (), (), pack, _Flat(), law.ruleset_key)
    cl = Classification(tuple(cells), (), {}, ())
    pm, stats = build(airport, cl, law)
    if basins:
        pm = _dc.replace(pm, basins=tuple(basins))
    return airport, pm, stats


def _apron_with_hole(width_m: float):
    """One apron cell carrying a ``width_m`` × 20 m interior ring."""
    hole = _rect(-10.0, 160.0, -10.0 + width_m, 180.0)
    return [RUNWAY,
            Cell(1, "apron", "apronA", _rect(-200, Y0, 200, Y1), (hole,),
                 None, None, "airside", "apron", {})]


def _face(pm, ref):
    return next(f for f in pm.faces.values() if f.ref == ref)


def _in_hole(pm, width_m: float) -> list[int]:
    box = Polygon(_rect(-11.0, 159.0, -9.0 + width_m, 181.0))
    return [v for v, vx in pm.vertices.items()
            if box.contains(Polygon(_rect(*vx.xy, vx.xy[0] + 1e-9, vx.xy[1] + 1e-9))
                            .representative_point())]


# ── (1) the degenerate hole ──────────────────────────────────────────────

def test_a_sliver_hole_is_dissolved_into_its_face_and_mints_no_vertices(law):
    """0.4 m wide — under ``terrace.separation_m`` — so the apron keeps NO
    hole there and no vertex is born inside it (LEMD way −10892)."""
    _ap, pm, st = _airport(law, _apron_with_hole(0.4))
    f = _face(pm, "apronA")
    assert f.holes == (), f.holes
    assert st.holes_dissolved >= 1
    assert _in_hole(pm, 0.4) == []


def test_a_hole_wider_than_the_separation_is_kept(law):
    """3 m wide — a real gap in the pavement: the ring stands, with its
    vertices, and nothing is dissolved."""
    _ap, pm, st = _airport(law, _apron_with_hole(3.0))
    f = _face(pm, "apronA")
    assert len(f.holes) == 1
    assert st.holes_dissolved == 0
    assert len(pm.ring_vertices(f.holes[0])) >= 4


def test_the_dissolve_keeps_a_thin_hole_that_holds_a_face():
    """A hole a kept face lies inside is never dissolved, however thin —
    filling it would overlap two faces."""
    outer = Polygon(_rect(-100, 0, 100, 100), [_rect(-10, 40, -9.6, 60)])
    inner = Polygon(_rect(-10, 40, -9.6, 60))
    reg = object()
    faces = [(outer, reg), (inner, reg)]
    kept, gone = dissolve_degenerate_holes(faces, 0.5, 0.25)
    assert gone == 0
    assert len(kept[0][0].interiors) == 1


def test_the_dissolve_removes_a_hole_under_the_minimum_face_area():
    """Area under ``identity.min_distinct_spacing_m²`` is degenerate even
    where the ring is not thin."""
    outer = Polygon(_rect(-100, 0, 100, 100), [_rect(-10, 40, -9.6, 40.4)])
    kept, gone = dissolve_degenerate_holes([(outer, object())], 0.0, 0.25)
    assert gone == 1 and len(kept[0][0].interiors) == 0


# ── (2) the rim is a contact ─────────────────────────────────────────────

def _basin_cells(floor_z: float):
    """An apron the rim cuts: apron ring with the rim as its hole, the void
    (``retaining_wall``) between rim and floor, and the floor plate."""
    rim = _rect(-40.0, 140.0, 40.0, 200.0)
    floor = _rect(-30.0, 150.0, 30.0, 190.0)
    return [RUNWAY,
            Cell(1, "apron", "apronA", _rect(-200, Y0, 200, Y1), (rim,),
                 None, None, "airside", "apron", {}),
            Cell(2, "retaining_wall", "basin_wall:0", rim, (floor,),
                 None, None, "airside", "structure", {}),
            Cell(3, "tunnel_trench", "basin_floor:0", floor, (),
                 None, None, "airside", "structure", {})], rim, floor


def _basin(floor_z: float, rim, floor):
    return Basin("basin:0", ("obj:fixture",), floor_z, "basin_floor:0", "basin_wall:0",
                 tuple(floor), wall_path=tuple(rim), rim_estimate_m=690.0,
                 solid_min_z=floor_z, area_m2=4800.0)


def test_a_rim_vertex_an_apron_shares_is_never_pinned_and_carries_the_apron(law):
    """08t / 08p, reconciling 10h: the rim vertices the apron shares get NO
    structure Pin (the ground's value carries), and in the emitted surface
    the ``structure_rim`` way's value at a shared node IS the apron's."""
    cells, rim, floor = _basin_cells(688.0)
    airport, pm, _st = _airport(law, cells, basins=[_basin(688.0, rim, floor)])
    rows = basin_rows(pm, law, airport)
    pins = {r.v: r for r in rows if isinstance(r, Pin)}

    wall = _face(pm, "basin_wall:0")
    floor_f = _face(pm, "basin_floor:0")
    floor_vs = set(pm.ring_vertices(floor_f.ring))
    rim_vs = [v for v in pm.ring_vertices(wall.ring) if v not in floor_vs]
    apron_vs = set(v for h in _face(pm, "apronA").holes for v in pm.ring_vertices(h))
    shared = [v for v in rim_vs if v in apron_vs]
    assert shared, "the knife's rim IS the apron's hole ring — the vertices are one set"
    assert not any(v in pins for v in shared), \
        "a shared rim vertex is pinned by nothing: the apron's surface carries it"
    assert all(pins[v].z == pytest.approx(688.0) for v in floor_vs), "the floor is pinned"

    sol, _rep = solve_design(pm, ConstraintSet.from_rows(rows), law, Options())
    surface = graded_surface(pm, law, sol, (60.5, -135.5))
    rim_bl = [b for b in surface.breaklines if b.kind == RIM_KIND]
    assert rim_bl, "the void's exterior is emitted as a structure_rim"
    z_of = {v.id: v.z for v in surface.vertices}
    apron_face = next(f for f in surface.faces if f.ref == "apronA")
    hole_z = {v: z_of[v] for h in apron_face.holes for v in h}
    for b in rim_bl:
        for v in b.vertices:
            if v in hole_z:
                assert z_of[v] == pytest.approx(hole_z[v], abs=1e-9)


def test_rim_law_m_is_the_region_diagnostic_not_the_rim_value(law):
    """``rim_law_m`` (the sidecar) is ``Basin.rim_estimate_m`` — the median
    DEM around the ADMITTED REGION, the admission-depth diagnostic.  It is
    not a rim vertex's law, and the emitted rim is not read against it
    (LEMD: 596.022 against a rim on ground at 599)."""
    from auto_patch_v2.pipeline.publication import publication
    cells, rim, floor = _basin_cells(688.0)
    b = _basin(688.0, rim, floor)
    airport, pm, _st = _airport(law, cells, basins=[b])
    doc = publication(pm, law, airport)
    facilities = doc.get("basin_facilities") or []
    assert facilities and facilities[0]["rim_law_m"] == pytest.approx(690.0, abs=1e-3)
    # the ground the rim actually stands on here is the flat DEM, 10 m above it
    assert math.isclose(airport.dem.z(0.0, 170.0), 700.0)
