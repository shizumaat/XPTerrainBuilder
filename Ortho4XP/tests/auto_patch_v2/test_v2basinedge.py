"""§24 THE BASIN'S EDGE AND FLOOR (owner RULINGS 2026-09-11t; spec
``docs/specs/auto-patch-v2/design-surface-spec.md`` §24) — lane
``v2basinedge``.

THE SITE, on the app's 1.0.315 LEMD products (T4S, ``basin:0``, the pit
with the control tower):

  (a) every one of its 56 rim vertices stood 1.749 / 2.064 / 4.120 m
      (min / median / max) OUTSIDE the object's own outer wall face —
      ``planar/basins._rim`` widened the region by whole grid steps
      (k = 4 → +2.0 m) until it cleared the floor (the plate ⊕
      ``floor_overlap_m``) by the stand-off, because the T4S shell
      measures 0.00 m thick.  That shelf is the owner's "gap between the
      outer edge and the apron".
  (b) the vertical step was already 0: all 71 rim vertices share their
      id with a pavement or pad face (23 apron, 51 building).
  (c) ``floor_z`` 588.952 == ``solid_min_z`` 588.952 — the trench floor
      was stated AT the object's floor plate, which is "seeing the
      terrain at the bottom of the basin".

The two laws, and the twins here:

  §24 (1) THE CUT HUGS THE WALL — the rim IS the shells' footprint below
      the ground (the outer wall face at its top), inset only by
      ``cutout.rim_inset_fraction`` × the measured shell thickness, never
      widened; the stand-off comes out of the FLOOR.
  §24 (2) THE FLOOR SITS UNDER THE OBJECT'S FLOOR — the floor row is
      ``rim − (body_depth + [basin] floor_clearance_m)``, and the plate
      seat reads its ground as the trench floor PLUS the clearance so the
      object does not chase its own trench down.

The fixtures are the M4b box pit (whose plate reaches its own walls: the
zero-thickness shell, LEMD's case exactly) and the ``test_v2pit2`` /
``test_v2basinfix`` synthetic T4S pit.  Law values are read from the
tables, never retyped.
"""
from __future__ import annotations

import dataclasses as _dc
import sys
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import Point, Polygon

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.structures import basins as basin_rows
from auto_patch_v2.law import Law
from auto_patch_v2.model.constraints import Linear, Pin
from auto_patch_v2.pipeline.build import _plate_seats
from auto_patch_v2.pipeline.publication import basin_facilities
from auto_patch_v2.planar.basins import build_basins, read_objects
from auto_patch_v2.planar.build import build as build_planar
from auto_patch_v2.planar.structure_geometry import rim_standoff
from auto_patch_v2.planar.structures import build_structures
from auto_patch_v2.solve import solve_design

sys.path.insert(0, str(Path(__file__).parent))
from test_m4b import _airport, _box_obj, _rect  # noqa: E402
from test_v2pit2 import FLOOR as _F_RING  # noqa: E402
from test_v2pit2 import RIM as _RIM  # noqa: E402
from test_v2pit2 import _cells as _pit_cells  # noqa: E402
from test_v2pit2 import _face  # noqa: E402


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


# ── §24 (1): the cut hugs the wall ────────────────────────────────────────

@pytest.fixture(scope="module")
def wide_apron_pit(tmp_path_factory, law):
    """A box pit 60 × 40 whose OSM pavement runs 2 m WIDER than the wall
    on every side — the shape the old rim was accused of taking.  The cut
    must land on the WALL, not on the pavement's own outline and not
    somewhere between them."""
    d = tmp_path_factory.mktemp("edge") / "objects"
    d.mkdir()
    objs = {"dir": d, "pit": _box_obj(d / "pit.obj", 30.0, 20.0, 6.0)}
    airport = _airport(objs, law, [("pit", (0.0, 0.0), 0.0, 0.0)])
    cells = [
        Cell(0, "runway", "09/27", _rect(-600, 500, 600, 545), (), 3, "D", "airside",
             "runway", {}),
        # the apron: the pit's footprint ⊕ 2 m, and well beyond it
        Cell(1, "apron", "apron1", _rect(-120, -80, 120, 80), (), None, None, "airside",
             "apron", {}),
    ]
    cl = Classification(tuple(cells), (), {}, ())
    objects, rep = read_objects(airport, law)
    cl2, tunnels, _st = build_structures(airport, cl, law, objects)
    cl3, basins, bs = build_basins(airport, cl2, law, tunnels, objects, report=rep)
    return airport, cl3, basins, bs


def _plate_footprint(hx=30.0, hz=20.0):
    return Polygon(_rect(-hx, -hz, hx, hz))


def test_the_rim_lies_on_the_objects_outer_wall_face(wide_apron_pit, law):
    """§24 (1), the (a) bar: every rim vertex stands within
    ``emit.identity.weld_spacing_m`` (1.0 m — the identity spacing plus
    the snap's half diagonal) of the object's outer wall face.  Measured
    at LEMD on 1.0.315 the same reading was 1.749 / 2.064 / 4.120 m, and
    EVERY vertex was outside."""
    _airport_, cl3, basins, bs = wide_apron_pit
    assert len(basins) == 1 and not bs.refused, bs.refused
    b = basins[0]
    wall = next(c for c in cl3.cells if c.ref == b.wall_ref)
    face = _plate_footprint().exterior
    weld = law.tables.emit.identity.weld_spacing_m
    d = [face.distance(Point(q)) for q in wall.ring]
    assert d and max(d) <= weld + 1e-6, (min(d), sorted(d)[len(d) // 2], max(d))


def test_the_rim_is_never_widened_outside_the_shells_footprint(wide_apron_pit):
    """The mechanism, not the symptom: the emitted rim encloses no more
    area than the shell's own footprint ⊕ the ONE widening §47 (3) names
    — the ``rim_yield`` of a shell too thin to hold two rings, reported
    per basin.  The old ``_rim`` k-loop widened by 2.0 m at LEMD —
    28,971 m² of rim over a 27,557 m² region — and nothing does that now.

    This pit's authored shell is ZERO thick, so its whole band is the
    yield: ``ring_floor_m`` 0.7071 m, snapped to the identity lattice by
    ``basin_geometry._snap_ring`` (0.5 m out on each side here)."""
    _a, cl3, basins, _bs = wide_apron_pit
    wall = next(c for c in cl3.cells if c.ref == basins[0].wall_ref)
    rim, plate = Polygon(wall.ring), _plate_footprint()
    from auto_patch_v2.law import Law
    F = Law.for_airport("ZZZZ").tables.structures.cutout.ring_floor_m
    allowed = plate.buffer(F + 1e-6, join_style="mitre", mitre_limit=2.0)
    assert allowed.contains(rim)
    assert rim.area <= allowed.area + 1e-6
    # ...and the yield is NAMED, never silent
    assert any("rim_yield" in n for n in _bs.rim_yields), _bs.rim_yields


def test_the_standoff_comes_out_of_the_floor(wide_apron_pit, law):
    """The stand-off the mesh needs to make a wall band is taken from the
    FLOOR, at the region's one derivation site — never by pushing the cut
    away from the object it is cutting for (08-30l: trim the region, do
    not veto per consumer).  The floor still clears the rim."""
    _a, cl3, basins, _bs = wide_apron_pit
    wall = next(c for c in cl3.cells if c.ref == basins[0].wall_ref)
    floor = next(c for c in cl3.cells if c.ref == basins[0].floor_ref)
    rim, fp = Polygon(wall.ring), Polygon(floor.ring)
    grid = law.tables.emit.identity.min_distinct_spacing_m
    _inset, standoff = rim_standoff(0.0, law.tables.structures.cutout)
    assert rim.contains(fp) and fp.distance(rim.exterior) >= standoff - 1e-6
    # ... and the floor never leaves the plate of a zero-thickness shell
    assert _plate_footprint().buffer(1e-6).contains(fp)


def test_the_rim_notes_name_the_hugging_law(wide_apron_pit):
    """A refusal or a reading is never anonymous: the basin's notes say
    the rim is the outer face and how much floor the stand-off cost."""
    _a, _cl3, basins, _bs = wide_apron_pit
    notes = " ".join(basins[0].notes)
    assert "THE CUT HUGS THE WALL" in notes and "trimmed" in notes


# ── §24 (2): the floor sits under the object's floor ──────────────────────

def _t4s(law, dem, depth=7.05, rim_est=700.0, solid_min_y=None):
    """The T4S pit as ``test_v2basinfix`` builds it, with the body depth
    optionally NOT evidenced (``solid_min_y = 0``: the 10bd fallback)."""
    from auto_patch_v2.model.airport import (Airport, Runway, RunwayEnd,
                                             SceneryPack)
    from auto_patch_v2.model.frame import Frame
    from auto_patch_v2.model.structures import Basin
    cells = _pit_cells("basin_wall:0", "basin_floor:0")
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 706.0, "fixture"))
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0,
                      (Runway("09/27", 45.0, 1, ends, 3, "D"),),
                      (), (), {}, (), (), (), (), (), (), (), pack, dem, law.ruleset_key)
    pm, _st = build_planar(airport, Classification(tuple(cells), (), {}, ()), law)
    floor_z = rim_est - depth
    b = Basin("basin:0", ("obj:fixture",), floor_z, "basin_floor:0", "basin_wall:0",
              tuple(_F_RING), wall_path=tuple(_RIM), rim_estimate_m=rim_est,
              solid_min_z=floor_z,
              solid_min_y_m=-depth if solid_min_y is None else solid_min_y,
              area_m2=4800.0, plate_y_m=-depth, witness_id="dsf:obj0")
    return airport, _dc.replace(pm, basins=(b,))


class _FlatDem:
    provenance = {"synthetic": "flat 700"}

    def z(self, x: float, y: float) -> float:
        return 700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _floor_to_rim(pm, law, airport):
    rows = basin_rows(pm, law, airport)
    floor_vs = set(pm.ring_vertices(_face(pm, "basin_floor:0").ring))
    rel = [r for r in rows if isinstance(r, Linear) and r.follows
           and set(r.follows) <= floor_vs]
    return {v: next(u for u, c in r.terms if c < 0) for r in rel for v in r.follows}


def test_the_floor_stands_the_clearance_under_the_plate(law):
    """§24 (2), the (c) bar: floor − plate = −``floor_clearance_m``.  On
    1.0.315 it was 0.000 — the trench floor was stated AT the plate."""
    clear = law.tables.structures.basin.floor_clearance_m
    airport, pm = _t4s(law, _FlatDem())
    cs, _counts, _w = generate(pm, law, airport)
    sol = solve_design(pm, cs, law)[0]
    z = np.asarray(sol.z, float)
    rim_of = _floor_to_rim(pm, law, airport)
    assert rim_of
    plate_of = {v: float(z[u]) - 7.05 for v, u in rim_of.items()}   # the plate's level
    worst = max(abs((float(z[v]) - plate_of[v]) + clear) for v in rim_of)
    assert worst <= law.tables.emit.materiality.elevation_m, worst


def test_a_basin_with_no_plate_reading_keeps_the_10bd_depth_less_the_clearance(law):
    """10bd's fallback survives §24 (2): a record evidencing no body depth
    (``solid_min_y_m`` 0 — a fixture, or a patch published before that
    instrument) reads its depth the long way, ``R_est − floor_z``, and
    the clearance goes under THAT."""
    clear = law.tables.structures.basin.floor_clearance_m
    airport, pm = _t4s(law, _FlatDem(), solid_min_y=0.0)
    b = pm.basins[0]
    assert b.solid_min_y_m == 0.0
    assert b.floor_below_rim_m(clear) == pytest.approx(
        (b.rim_estimate_m - b.floor_z) + clear)
    rows = basin_rows(pm, law, airport)
    rel = [r for r in rows if isinstance(r, Linear) and r.follows]
    assert rel and all(r.lo == r.hi == pytest.approx(-(7.05 + clear)) for r in rel)


def test_the_published_depth_is_the_row_the_solve_was_given(law):
    """ONE derivation (``Basin.floor_below_rim_m``): what
    ``pipeline/publication`` publishes as ``floor_below_rim_m`` — the
    number ``verify.basin_floor_at_declaration`` judges the emitted floor
    against — is the number the row was stated with.  Two copies of this
    arithmetic is how a published depth and a stated row drift apart."""
    clear = law.tables.structures.basin.floor_clearance_m
    airport, pm = _t4s(law, _FlatDem())
    rec = basin_facilities(pm, law)[0]
    assert rec["floor_clearance_m"] == pytest.approx(clear)
    assert rec["body_depth_m"] == pytest.approx(7.05)
    assert rec["floor_below_rim_m"] == pytest.approx(7.05 + clear)
    rows = [r for r in basin_rows(pm, law, airport) if isinstance(r, Linear) and r.follows]
    assert rows and all(r.lo == pytest.approx(-rec["floor_below_rim_m"]) for r in rows)


def test_a_basin_with_no_rim_of_its_own_pins_under_its_plate(law):
    """The absolute-pin fallback takes the clearance too: a basin whose
    wall ref owns no vertex keeps a pin, and that pin stands under the
    plate, never on it."""
    clear = law.tables.structures.basin.floor_clearance_m
    airport, pm = _t4s(law, _FlatDem())
    b = pm.basins[0]
    pm2 = _dc.replace(pm, basins=(_dc.replace(b, wall_ref="basin_wall:none", wall_path=()),))
    pins = [r for r in basin_rows(pm2, law, airport) if isinstance(r, Pin)]
    assert pins and all(p.z == pytest.approx(b.floor_z - clear) for p in pins)


# ── the seat does not chase the floor down ────────────────────────────────

def test_the_plate_seat_carries_the_clearance(law):
    """The other half of §24 (2): a basin member's seat stations lie ON
    the trench floor, which the floor row now puts ``floor_clearance_m``
    under the plate — so the seat's target is that ground PLUS the
    clearance (``Member.plate_clearance_m``).  Without it the plate would
    follow its own trench down and the terrain would be coplanar with it
    again."""
    clear = law.tables.structures.basin.floor_clearance_m
    _airport_, pm = _t4s(law, _FlatDem())
    seats = _plate_seats(pm, law)
    assert seats and all(len(v) == 3 for v in seats.values())
    assert seats["dsf:obj0"][2] == pytest.approx(clear)
