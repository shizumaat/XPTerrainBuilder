"""jetspec scratch ARM: the stand-zone PLATEAU of a held block is extended to the WHOLE BAYS of
its outline (owner RULINGS 2026-10-08b: "whole piers as well, the pad should be flat and the
apron welds to it") — a hull pocket of the block's outline that holds a rider edge or a stand
(it intersects the §3 stand-zone parts) joins the zone WHOLE, not clipped to the 90 m held span;
everything else in ``planar/pad_cut.plateau_cut`` is untouched (apron faces only, taxi faces
never, the snap, the dissolve).  No law key, no engine edit: a monkeypatch on ``_stand_zone``
at module level so the work pool's workers carry it.
usage (from Ortho4XP/): venv/bin/python <this> --replay CAP.pkl --from planar --emit DIR --verify [...]
   env JETSPEC_BAYS=0 runs the unpatched base through the same entry (the frame)."""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "src")); sys.path.insert(0, str(Path.cwd() / "tools"))
from shapely.geometry import Polygon
from shapely.ops import unary_union
from auto_patch_v2.planar import pad_cut as pc

_real = pc._stand_zone
BAYS = {"n": 0, "m2": 0.0}


def pockets_of(outline):
    polys = pc._flat_polys(outline)
    filled = unary_union([Polygon(g.exterior) for g in polys])
    hull = filled.convex_hull
    diff = hull.difference(filled)
    return [g for g in getattr(diff, "geoms", [diff]) if not g.is_empty and g.area > 1.0]


def _bays(parts, close_m, span, outline, ident):
    base = _real(parts, close_m, span, outline, ident)
    held = unary_union(parts)
    bays = [p for p in pockets_of(outline) if p.intersects(held)]
    if not bays:
        return base
    BAYS["n"] += len(bays); BAYS["m2"] += sum(p.area for p in bays)
    zone = unary_union(([base] if base is not None else []) + bays)
    zone = unary_union([Polygon(g.exterior) for g in pc._flat_polys(zone)]).simplify(ident)
    near = outline.buffer(max(ident, 1e-6))
    keep = [Polygon(g.exterior) for g in pc._flat_polys(zone) if g.intersects(near)]
    return unary_union(keep) if keep else None


if os.environ.get("JETSPEC_BAYS", "1") != "0":
    pc._stand_zone = _bays

if __name__ == "__main__":
    import v2_solve_replay
    rc = v2_solve_replay.main()
    print(f"[jetspec] bays added to stand zones: {BAYS['n']} pockets, {BAYS['m2']:,.0f} m2 (main process only)")
    sys.exit(rc)
