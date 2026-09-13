"""§24 (4)–(6) THE RING IS THE SHELL'S OUTER FOOTPRINT; THE FLOOR FOLLOWS
A RAMP (owner RULINGS 2026-09-13g; spec
``docs/specs/auto-patch-v2/design-surface-spec.md`` §24 (4)–(6)) — lane
``v2basinfoot``.

THE SITE, on the app's 1.0.325 LEMD products (T4S, ``basin:0``, the pit
with the control tower and the modelled road ramp):

  (a) the region was the union of the witnesses' footprints CLIPPED BELOW
      THE GROUND — and that clip is taken at ONE plane, the DEM under the
      component's own centroid (593.00 for ``Ground-FSX-LEMD85``).  Every
      part of the shell standing above that plane was therefore missing
      from the region: 11 of the rim ring's 59 nodes stood 6–15 m from
      any wall, and the road ramp (589.5 → 596.8 over 95 m) was cut out
      of the region the moment it climbed through 593.00 — a 52 × 11 m
      notch the pad ``building15`` then filled at 598.4, burying 51 m of
      ramp, 2.92 m at worst.
  (b) the trench floor was ONE depth under the nearest rim vertex
      everywhere, so even the stretch of ramp inside the region had flat
      terrain under it, not a profile.

The two laws, and the twins here:

  §24 (4) THE RING IS THE SHELL'S OUTER FOOTPRINT AT THE TOP OF ITS WALLS
      — every witnessing component's WHOLE plan footprint
      (``FloorWitness.outer``), never the below-DEM clip.
  §24 (5) THE FLOOR FOLLOWS A RAMP — a floor vertex under a ramp corridor
      (the shell's own deck climbing from the floor plate to the rim)
      takes the deck's authored elevation minus ``[basin]
      floor_clearance_m``, per station; elsewhere the one depth stands.

The fixture is a box pit with a RAMP welded to one wall, climbing out of
the pit and up through the ground plane — LEMD's shape, synthetically.
Law values are read from the tables, never retyped.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from shapely.geometry import Point, Polygon

from auto_patch_v2.airport import obj8
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints.structures import basins as basin_rows
from auto_patch_v2.law import Law
from auto_patch_v2.model.constraints import Linear, Pin
from auto_patch_v2.model.structures import Basin, deck_z_on_faces
from auto_patch_v2.pipeline.publication import basin_facilities
from auto_patch_v2.planar.basins import build_basins, read_objects
from auto_patch_v2.planar.build import build as build_planar
from auto_patch_v2.planar.structures import build_structures

sys.path.insert(0, str(Path(__file__).parent))
from test_m4b import _airport, _rect  # noqa: E402

#: The fixture's ground: ``_PlaneDem`` in ``test_m4b`` is flat at this.
GROUND = 700.0
DEPTH = 6.0
RAMP_LEN = 70.0            # 6.9 m of rise over it: grade 0.10, LEMD's own
RAMP_TOP = 0.9              # authored y at the ramp's outer end: ABOVE the ground
THICK = 0.35                # the slab's own thickness (>= min_solid_thickness_m)


def _pit_with_ramp(path, hx=30.0, hz=20.0, depth=DEPTH, ramp_len=RAMP_LEN,
                   ramp_top=RAMP_TOP, thickness=THICK):
    """A box pit ``2hx × 2hz`` deep ``depth`` with a RAMP welded to its
    +x wall: a solid slab whose top face climbs from the pit floor out to
    ``ramp_top`` (above the ground plane, y = 0) over ``ramp_len``.

    ONE welded component, so the pit's floor witness carries the ramp —
    which is the whole point: under the below-DEM clip the ramp's upper
    half is not in the region at all."""
    # the box (the same 8 corners ``test_m4b._box_obj`` writes)
    corners = [(-hx, -hz), (hx, -hz), (hx, hz), (-hx, hz)]
    vt = []
    for x, z in corners:
        vt.append((x, 0.0, z))              # 0, 2, 4, 6: the wall top
        vt.append((x, -depth, z))           # 1, 3, 5, 7: the floor
    tris = []
    for i in range(4):
        a, b = 2 * i, 2 * ((i + 1) % 4)
        tris += [(a, a + 1, b), (a + 1, b + 1, b)]
    tris += [(1, 3, 5), (1, 5, 7)]          # the floor plate
    # the ramp: top face 3 (hx, -depth, -hz) → 5 (hx, -depth, hz) out to
    # (hx + ramp_len, ramp_top, ±hz), with a bottom face ``thickness`` under it
    n = len(vt)
    vt.append((hx + ramp_len, ramp_top, -hz))               # n
    vt.append((hx + ramp_len, ramp_top, hz))                # n + 1
    vt.append((hx, -depth - thickness, -hz))                # n + 2
    vt.append((hx, -depth - thickness, hz))                 # n + 3
    vt.append((hx + ramp_len, ramp_top - thickness, -hz))   # n + 4
    vt.append((hx + ramp_len, ramp_top - thickness, hz))    # n + 5
    tris += [(3, n, n + 1), (3, n + 1, 5)]                  # the deck (up-facing)
    tris += [(n + 2, n + 5, n + 4), (n + 2, n + 3, n + 5)]  # the soffit
    tris += [(3, n + 4, n), (3, n + 2, n + 4)]              # the -z side
    tris += [(5, n + 1, n + 5), (5, n + 5, n + 3)]          # the +z side
    tris += [(n, n + 4, n + 5), (n, n + 5, n + 1)]          # the far end
    lines = ["A", "800", "OBJ", "", "TEXTURE none",
             f"POINT_COUNTS {len(vt)} 0 0 {3 * len(tris)}"]
    lines += [f"VT {x:.3f} {y:.3f} {z:.3f} 0 1 0 0 0" for x, y, z in vt]
    idx = [i for t in tris for i in t]
    lines += ["IDX " + " ".join(str(i) for i in idx[k:k + 10])
              for k in range(0, len(idx), 10)]
    lines.append(f"TRIS 0 {len(idx)}")
    path.write_text("\n".join(lines) + "\n")
    return path


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def ramp_pit(tmp_path_factory, law):
    d = tmp_path_factory.mktemp("basinfoot") / "objects"
    d.mkdir()
    objs = {"dir": d, "pit": _pit_with_ramp(d / "pit.obj")}
    airport = _airport(objs, law, [("pit", (0.0, 0.0), 0.0, 0.0)])
    objects, rep = read_objects(airport, law)
    cells = [
        Cell(0, "runway", "09/27", _rect(-600, 500, 600, 545), (), 3, "D", "airside",
             "runway", {}),
        Cell(1, "apron", "apron1", _rect(-250, -120, 250, 120), (), None, None, "airside",
             "apron", {}),
        # the pad that fills the notch when the ramp is outside the region
        Cell(2, "building", "padRamp", _rect(20, -25, 120, 25), (), None, None, "airside",
             "pad", {}),
    ]
    cl = Classification(tuple(cells), (), {}, ())
    cl2, tunnels, _st = build_structures(airport, cl, law, objects)
    cl3, basins, bs = build_basins(airport, cl2, law, tunnels, objects, report=rep)
    return airport, cl3, basins, bs, objects, rep, cl


# ── §24 (4): the ring is the shell's OUTER footprint ──────────────────────

def test_the_witness_carries_its_whole_plan_footprint(ramp_pit):
    """``FloorWitness.outer`` is the component's WHOLE plan footprint and
    ``below`` the clip that used to be the region: the ramp's upper half
    is in one and not the other."""
    _a, _cl, _b, _bs, objects, _rep, _raw = ramp_pit
    w = [w for o in objects for w in o.witnesses]
    assert len(w) == 1
    assert w[0].outer is not None and w[0].comp_index >= 0
    assert w[0].outer.area > w[0].below.area + 50.0
    # the clip stops where the deck climbs through the ground plane; the
    # outer footprint runs the ramp's whole length
    assert w[0].outer.bounds[2] == pytest.approx(30.0 + RAMP_LEN, abs=0.5)
    assert w[0].below.bounds[2] < 30.0 + RAMP_LEN - 1.0


def test_the_ramp_corridor_stays_inside_the_cut(ramp_pit):
    """§24 (4): the region — and so the rim ring — reaches the ramp's far
    end, and the pad over the ramp is CUT there (the ``building15`` notch
    at LEMD: with the region short, the pad filled it)."""
    _a, cl3, basins, _bs, _o, _rep, _raw = ramp_pit
    assert len(basins) == 1
    b = basins[0]
    rim = Polygon(b.wall_path)
    far = Point(30.0 + RAMP_LEN - 2.0, 0.0)
    assert rim.covers(far), "the ramp's far end is outside the cut"
    assert Polygon(b.region).covers(far)
    pad = [c for c in cl3.cells if c.role == "building" and c.ref.startswith("padRamp")]
    assert all(not Polygon(c.ring, c.holes).covers(far) for c in pad), \
        "a pad still fills the ramp corridor"


def test_a_below_dem_only_component_does_not_shrink_the_region(ramp_pit, law,
                                                               tmp_path_factory):
    """The identity case: a pit with NO geometry above the ground plane
    reads the same region either way — §24 (4) never widens a cut, it
    stops the clip from eating the shell."""
    d = tmp_path_factory.mktemp("flatpit") / "objects"
    d.mkdir()
    sys.path.insert(0, str(Path(__file__).parent))
    from test_m4b import _box_obj                       # noqa: PLC0415
    objs = {"dir": d, "pit": _box_obj(d / "pit.obj", 30.0, 20.0, DEPTH)}
    airport = _airport(objs, law, [("pit", (0.0, 0.0), 0.0, 0.0)])
    objects, rep = read_objects(airport, law)
    w = [w for o in objects for w in o.witnesses]
    assert w and w[0].outer is not None
    assert w[0].outer.area == pytest.approx(w[0].below.area, abs=1.0)


# ── §24 (5): the floor follows the ramp ───────────────────────────────────

def test_the_basin_carries_its_ramp_corridor(ramp_pit):
    b = ramp_pit[2][0]
    assert b.ramp_rings and b.ramp_faces, "the ramp corridor was not read"
    assert any("ramp corridors" in n for n in b.notes)
    # the deck climbs: floor level at the pit wall, above it at the far end
    near = b.deck_z_at(32.0, 0.0)
    far = b.deck_z_at(30.0 + RAMP_LEN - 2.0, 0.0)
    assert near is not None and far is not None
    assert far > near + 3.0
    assert b.deck_z_at(-1000.0, 0.0) is None


def test_the_floor_under_a_ramp_follows_the_deck(ramp_pit, law):
    """The floor rows: a vertex under the corridor is PINNED at the deck
    minus ``floor_clearance_m``; one over the plate keeps the relative
    row against its rim vertex."""
    airport, _cl3, basins, _bs, _o, _rep, raw = ramp_pit
    pm, _stats = build_planar(airport, raw, law)
    rows = basin_rows(pm, law, airport)
    clearance = float(law.tables.structures.basin.floor_clearance_m)
    b = pm.basins[0]
    pins = [r for r in rows if isinstance(r, Pin)]
    under = []
    for r in pins:
        x, y = pm.vertices[r.v].xy
        deck = b.deck_z_at(x, y)
        if deck is None:
            continue
        under.append(r)
        assert r.z == pytest.approx(deck - clearance, abs=1e-6)
    assert under, "no floor vertex took the ramp's profile"
    # and the deck stands ABOVE the design surface everywhere on the ramp
    for r in under:
        x, y = pm.vertices[r.v].xy
        assert b.deck_z_at(x, y) - r.z >= clearance - 1e-6
    # the plate's own floor still follows the rim
    assert any(isinstance(r, Linear) for r in rows)


def test_the_published_facility_carries_the_ramp(ramp_pit, law):
    """``verify`` re-derives the expectation from the published deck
    (``deck_z_on_faces`` — the ONE reading), so the sidecar must carry
    the corridor in the frame's own metres."""
    airport, _cl3, _b, _bs, _o, _rep, raw = ramp_pit
    pm, _stats = build_planar(airport, raw, law)
    rec = basin_facilities(pm, law)[0]
    assert rec["ramp_corridors"] >= 1
    assert rec["ramp_faces_ll"] and rec["ramp_rings_ll"]
    faces = [[tuple(q) for q in t] for t in rec["ramp_faces_ll"]]
    rings = [[tuple(q) for q in r] for r in rec["ramp_rings_ll"]]
    x, y = 30.0 + RAMP_LEN - 4.0, 0.0
    lat, lon = airport.frame.transformers()[1](x, y)
    # the published corridor is LON / LAT (the patch's own system, never
    # the planar frame's metres), and answers the same height there
    assert deck_z_on_faces(faces, rings, lon, lat, ring_tol=1.0 / 111320.0) \
        == pytest.approx(pm.basins[0].deck_z_at(x, y), abs=1e-3)


def test_a_basin_with_no_ramp_keeps_the_one_depth():
    """The identity: no corridor, no deck reading, and every floor vertex
    stays on the basin's own depth."""
    b = Basin("basin:0", (), 0.0, "basin_floor:0", "basin_wall:0", ())
    assert b.ramp_rings == () and b.ramp_faces == ()
    assert b.deck_z_at(0.0, 0.0) is None
