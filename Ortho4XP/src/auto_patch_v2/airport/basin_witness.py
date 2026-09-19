"""THE PACK'S PLACED OBJECTS, AND WHO IS A BASIN MEMBER — read ONCE, and
read FIRST (owner RULINGS 2026-09-10ax (2)).

``planar/basins.py`` owns the basin REGION (rules 2-5: the union of the
witnesses' below-ground footprints, the rim, the floor, the cut).  What
lives here is the half of the reading that has to happen EARLIER than
that: rule 1 — which PLACEMENTS carry a basin floor witness (a genuine
solid whose rim reaches grade and whose floor plate stands
``admission_depth_m`` under the local ground AND ``authored_depth_min_m``
under the placement's own render datum, RULINGS 2026-09-09ak).

Why earlier: the skirt reader (``airport/skirt.py``, 10ag) and the
re-seat plan's below-grade skip (``airport/rebake_plan.py``, 09w (1))
both ask "is this placement's below-zero geometry a FOUNDATION?", and a
basin's members answer yes by geometry alone — a pit IS uniform
below-zero extent across its footprint.  Measured at LEMD (2026-09-10,
lane ``v2basinfix``): the T4S basin's own members
``Ground-FSX-LEMD36``/``LEMD85`` read skirts of 7.01/7.03 m, covered
94 % of the T4S terminal pad ``building16``, and dropped it under 10ag;
with the pad gone the OSM road bore ``-5970`` was no longer refused
("the mouth stands against building pad building16") and its ramp — a
``kind == "structure"`` cell — landed on the pit's rim, so
``planar/basins`` rule 5 refused the basin itself ("27557 m2 overlaps a
tunnel structure").  ``basin_facilities`` 1 -> 0, the pit went uncut and
``Ground-FSX-LEMD37`` was seated +4.7 m onto the uncut surface: the
owner's "lip 2 m above the apron" on app 1.0.310.

THE RULE (10ax (2)): a basin facility admitted under 09ak is never
demoted by the skirt reader or by the below-grade skip.  A skirt is a
foundation under a building that stands ABOVE ground; a basin's members
ARE the pit.  So the admission runs FIRST and its members are exempt at
both sites — ``skirt.skirted_placements`` (the one derivation site of
"skirted", which ``classify/evidence._drop_skirted`` and
``emit/clusters`` both read) and ``rebake_plan``'s per-component
below-grade skip.

The read itself is memoised on the shared ``obj8.ResourceCache`` (the
one v2skirt made the whole build share), so asking the question at
classify time costs the planar pass nothing.
"""
from __future__ import annotations

import typing as _t

import math

import numpy as np
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from . import deck_signature, frame_entry as _fe, obj8
from .obj8 import is_stock_library_resource, placement_affine

if _t.TYPE_CHECKING:                                   # pragma: no cover
    from ..law import Law

__all__ = ["read_objects", "basin_member_ids", "ramp_decks"]


def read_objects(airport, law: "Law", cache: obj8.ResourceCache | None = None
                 ) -> tuple[list[obj8.PlacedObject], obj8.ObjReport]:
    """Every placed OBJ8 of the pack read once (``airport/obj8.py``),
    memoised on ``cache`` — ``planar/basins.read_objects`` is this
    function, and the classify-time basin admission below shares the
    same reading."""
    bl = law.tables.structures.basin
    cache = cache or obj8.ResourceCache(bl.min_solid_thickness_m, _fe.quantum(law))
    hit = cache.placed.get("objects")
    if hit is not None:
        return hit                                     # type: ignore[return-value]
    rows = []
    for o in airport.dsf_objects:
        if not o.path.lower().endswith(".obj"):
            continue
        rows.append((o.id, o.path, o.xy, o.heading_deg,
                     o.y_offset_m if o.kind == "OBJECT_AGL" else None, o.kind))
    # the loader already resolved: hand the resolved path through the
    # index mapping so obj8 never walks the pack a second time
    index = {o.path: o.resolved_path for o in airport.dsf_objects if o.resolved_path}
    objs, rep = obj8.read_placed_objects(rows, None, index, airport.dem.z,
                                         bl.admission_depth_m, bl.min_solid_thickness_m,
                                         bl.contact_band_m, cache,
                                         shell_reaches_grade=bl.shell_reaches_grade,
                                         floor_plate_normal_y_min=bl.floor_plate_normal_y_min,
                                         rim_reaches_grade=bl.rim_reaches_grade,
                                         rim_protrusion_max_fraction=bl.rim_protrusion_max_fraction,
                                         authored_depth_min_m=bl.authored_depth_min_m)
    # THE DECK SIGNATURE BY GEOMETRY (04k): un-flagged plates spanning a
    # mapped bridge way are decks; ``ATTR_hard_deck`` stays primary
    objs, drep = deck_signature.classify(objs, cache, law,
                                         deck_signature.bridge_lines(airport.osm_ways))
    rep.deck_families = drep.families
    rep.deck_signature_families = drep.accepted
    rep.deck_candidate_families = drep.candidates
    rep.deck_records = tuple(drep.records)
    cache.placed["objects"] = (objs, rep)
    return objs, rep


def basin_member_ids(airport, law: "Law",
                     cache: obj8.ResourceCache | None = None) -> frozenset[str]:
    """The placement ids carrying a basin FLOOR WITNESS — rule 1 of
    ``planar/basins``' admission, asked before anything else reads the
    pack's below-zero geometry (10ax (2)).  Rule 1 is the per-placement
    half of the admission and the half that founds a region: the later
    region rules (a runway, a basement, a structure overlap) can only
    REFUSE a region these members made, never make one, so exempting a
    witness here can never exempt a placement no basin would have
    claimed.

    Empty when the airport carries no DEM to judge a ground against (a
    fixture without terrain admits no basin, by rule 1's own terms)."""
    if getattr(airport, "dem", None) is None:
        return frozenset()
    objs, _rep = read_objects(airport, law, cache)
    return frozenset(o.id for o in objs if o.witnesses)


def ramp_decks(o: "obj8.PlacedObject", cache: "obj8.ResourceCache",
               comp_indices: _t.Sequence[int],
               floor_z: float, rim_z: float, band_m: float, normal_y_min: float,
               rise_m: float, max_grade: float) -> list[dict]:
    """THE RAMP CORRIDORS of one basin member (spec §24 (5), owner
    RULINGS 2026-09-13g): one record per candidate deck —
    ``{"ring", "faces", "rise_m", "run_m", "grade", "area_m2",
    "admitted", "reason"}``, the shell's own near-horizontal DECK faces
    climbing from the pit's floor to its rim, in the frame.  EVERY
    candidate comes back, admitted or not, so the basin's notes print
    what was refused and why.

    The candidate faces are the shell components' (``comp_indices``, the
    components that witnessed the floor — the pit's own shell, never a
    slab STANDING in it) up-facing solids (``|n_y| >= normal_y_min``,
    ``[basin] floor_plate_normal_y_min``: the same face test the floor
    plate is read with) whose rendered mid-height stands more than
    ``rise_m`` above the floor and no higher than ``rim_z + band_m``.
    They are joined in plan, and a connected part is a RAMP only when it
    spans the pit: its top comes within ``band_m`` of the rim and its
    foot within ``band_m`` of the floor.

    That climb test is what separates the modelled road ramp from
    everything else raised inside a pit.  MEASURED at LEMD's T4S basin
    (floor 588.95, R_est 596.02, band 1.0): two parts — the road ramp
    (1,271 m2, 589.53 … 596.78 over a 95 m run: a ramp) and a 2,045 m2
    slab of ``Ground-FSX-LEMD36`` topping out at 594.02, two metres short
    of the rim (not a ramp, and its terrain keeps the one depth)."""
    if o.resolved is None or is_stock_library_resource(o.path):
        return []
    g = cache.geometry(o.resolved)
    if g is None:
        return []
    v = g.vertices
    base = o.anchor_z + o.agl_m
    a, b, d, e, xoff, yoff = placement_affine(o.xy, o.heading_deg)
    comps = cache.components(o.resolved)
    faces: list[tuple] = []
    for ci in comp_indices:
        if ci < 0 or ci >= len(comps):
            continue
        t = comps[ci].tris
        if not t.shape[0]:
            continue
        p0, p1, p2 = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
        n = np.cross(p1 - p0, p2 - p0)
        ln = np.linalg.norm(n, axis=1)
        ny = np.zeros(t.shape[0])
        ok = ln > 1e-12
        ny[ok] = np.abs(n[ok, 1] / ln[ok])
        zmid = base + (p0[:, 1] + p1[:, 1] + p2[:, 1]) / 3.0
        keep = (ny >= normal_y_min) & (zmid > floor_z + rise_m) & (zmid <= rim_z + band_m)
        for k in np.nonzero(keep)[0].tolist():
            tri = []
            for i in t[k].tolist():
                px, py, pz = float(v[i][0]), float(v[i][1]), float(v[i][2])
                tri.append((a * px + b * pz + xoff, d * px + e * pz + yoff, base + py))
            area = 0.5 * abs((tri[1][0] - tri[0][0]) * (tri[2][1] - tri[0][1])
                             - (tri[2][0] - tri[0][0]) * (tri[1][1] - tri[0][1]))
            nyk = float(ny[k])
            faces.append((tuple(tri), min(q[2] for q in tri), max(q[2] for q in tri),
                          math.sqrt(max(0.0, 1.0 - nyk * nyk)) / max(nyk, 1e-6), area))
    if not faces:
        return []
    polys = []
    for tri, _lo, _hi, _sl, _ar in faces:
        try:
            p = Polygon([(q[0], q[1]) for q in tri])
        except (ValueError, TypeError):
            continue
        if p.is_valid and p.area > 1e-9:
            polys.append(p)
    if not polys:
        return []
    u = unary_union(polys)
    out: list[dict] = []
    for part in ([u] if u.geom_type == "Polygon" else list(u.geoms)):
        if part.geom_type != "Polygon" or part.area <= 1e-6:
            continue
        mine = [f for f in faces
                if part.intersects(Point(sum(q[0] for q in f[0]) / 3.0,
                                         sum(q[1] for q in f[0]) / 3.0))]
        if not mine:
            continue
        # THE CLIMB TEST is taken on the faces' own VERTICES, never their
        # mid-heights: a deck tessellated coarsely (a fixture's two
        # triangles over a 40 m ramp) has no face whose MIDDLE reaches
        # either end of the climb, and would read as no ramp at all.
        hi = max(mine, key=lambda f: f[2])
        lo = min(mine, key=lambda f: f[1])
        spans = hi[2] >= rim_z - band_m and lo[1] <= floor_z + band_m
        a = min(hi[0], key=lambda q: -q[2])
        b = min(lo[0], key=lambda q: q[2])
        rise = hi[2] - lo[1]
        run = math.hypot(a[0] - b[0], a[1] - b[1])
        # THE GRADE IS THE SURFACE'S OWN, area-weighted over the part's
        # faces (``sqrt(1 - n_y^2) / n_y``, the slope each triangle
        # actually has) — never rise over the part's plan span, which
        # reads a DRAINAGE BOWL's ring of banks as a 3 % ramp because its
        # lowest and highest faces lie a bowl-diameter apart (measured at
        # OTHH Drainage_01: 3.61 m over 133.5 m = 0.03, banks of 0.78).
        wa = sum(f[4] for f in mine)
        grade = (sum(f[3] * f[4] for f in mine) / wa) if wa > 1e-9 else math.inf
        # A RAMP IS DRIVABLE, A BANK IS NOT.  Spanning the pit is not
        # enough: a drainage BOWL's sloping sides climb from its floor to
        # its rim too, and under ``floor_plate_normal_y_min`` (0.7, up to
        # 45 deg) they read as near-horizontal.
        out.append({"ring": Polygon(part.exterior.coords), "faces": [f[0] for f in mine],
                    "rise_m": rise, "run_m": run, "grade": grade,
                    "area_m2": float(part.area),
                    "admitted": bool(spans and grade <= max_grade),
                    "reason": ("" if spans and grade <= max_grade
                               else "does not span the pit" if not spans
                               else f"grade {grade:.2f} over max_grade {max_grade:g}")})
    return out
