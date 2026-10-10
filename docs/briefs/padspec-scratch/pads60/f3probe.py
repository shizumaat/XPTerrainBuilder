"""pads60 SCRATCH PROBE (never committed): what platform_split does with
every pad over cluster_pad_min_m2 — cand, welded samples, and what
plan_blocks answers when asked anyway."""
import sys, json, runpy
OUT = sys.argv[1]; del sys.argv[1]; sys.path.insert(0, "src")
from auto_patch_v2.planar import platform as PL
from auto_patch_v2.planar import pad_blocks as PB
from shapely.ops import unary_union
orig = PL.draped_facade_pads
def hook(pad_regions, airport):
    loc = sys._getframe(1).f_locals
    rows = []
    for pr in pad_regions:
        P = pr.polygon
        if P is None or P.is_empty or P.geom_type != "Polygon" or P.area < loc["min_m2"]:
            continue
        cand = [loc["air_polys"][int(j)] for j in loc["tree"].query(P, predicate="dwithin", distance=loc["near"])]
        nw = PL._welded_samples(P, unary_union(cand), loc["near"]) if cand else 0
        try:
            bp = PB.plan_blocks(str(pr.ref), P, loc["base_regions"], loc["law"], loc["dem"], airport, loc["near"])
            plan = None if bp is None else {"blocks": len(bp.blocks), "verdict": bp.verdict, "base": str(bp.base), "datums": [round(b.datum, 2) for b in bp.blocks]}
        except Exception as e:
            plan = "EXC " + repr(e)
        c = P.representative_point()
        rows.append({"ref": str(pr.ref), "m2": round(P.area, 1), "cand": len(cand), "nw": nw, "plan": plan,
                     "base": str(PB.unit_base(P, airport)), "xy": [round(c.x, 1), round(c.y, 1)]})
    json.dump({"near": loc["near"], "min_m2": loc["min_m2"], "rows": rows}, open(OUT, "w"), indent=0)
    return orig(pad_regions, airport)
PL.draped_facade_pads = hook
runpy.run_path("tools/v2_solve_replay.py", run_name="__main__")
