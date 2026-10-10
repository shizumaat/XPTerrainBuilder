"""pads60 SCRATCH PROBE: why a building scrap is / is not re-roled (logs every non-largest rigid face under 300 m2)."""
import sys, json, runpy
OUT = sys.argv[1]; del sys.argv[1]; sys.path.insert(0, "src")
from auto_patch_v2.planar import pad_sliver as PS
orig = PS.rerole_plateau_scraps
def hook(faces, law, counts=None):
    from shapely.strtree import STRtree
    from auto_patch_v2.model.planar import pad_base_ref, plateau_block_of
    from auto_patch_v2.law.tables import role_side
    rigid = {r for r, s in law.tables.precedence.roles.items() if s.rigid}
    tree = STRtree([g for g, _ in faces]); rows = []
    for k, (g, r) in enumerate(faces):
        if r.role not in rigid or g.area > 300 or plateau_block_of(r.ref) is not None: continue
        nb = []; cov = 0.0
        for j in tree.query(g, predicate="intersects"):
            j = int(j)
            if j == k: continue
            run = float(g.boundary.intersection(faces[j][0].boundary).length)
            if run > 0: nb.append((faces[j][1].role, faces[j][1].ref, round(run, 2), role_side(law, faces[j][1].role))); cov += run
        c = g.representative_point()
        rows.append({"ref": r.ref, "role": r.role, "m2": round(g.area, 2), "per": round(g.length, 2), "meanw": round(2 * g.area / g.length, 2), "cov": round(cov, 2), "nb": nb, "xy": [round(c.x, 1), round(c.y, 1)]})
    with open(OUT, "a") as fh: fh.write(json.dumps({"rigid": sorted(rigid), "n_faces": len(faces), "rows": rows}) + "\n")
    return orig(faces, law, counts)
PS.rerole_plateau_scraps = hook
runpy.run_path("tools/v2_solve_replay.py", run_name="__main__")
