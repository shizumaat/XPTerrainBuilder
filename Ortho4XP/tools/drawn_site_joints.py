"""LIBRARY of ``tools/drawn_site.py`` (#2144): ``drawn_site --joints`` reads
the JOINT STEPS of a pack's span decks AS DRAWN.

Every ``.obj`` row of each ``--pack``'s WRITTEN tile DSF that the engine's
own reader calls a deck piece (``auto_patch_v2.airport.deck_chain.piece_of``:
long along its z, both end cross-sections spanning its width) is placed the
way X-Plane places it (``drawn_site.row_base``: the drawn mesh under the
anchor, plus the AGL offset, or the row's MSL elevation); every joint
(``deck_chain.joints``: an edge meeting one edge of another piece) is read
as the drawn soffit step between the two edges.  ``--site NAME=LAT,LON,R``
reads the joints within R of the site (repeat), else every joint of the
tile.  Prints p50 / p90 / p99 / max and the worst joints; ``--json`` the
whole list.  Read-only (temp dumps).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(os.path.dirname(HERE), "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

__all__ = ["joint_steps", "steps_of", "main"]


def joint_steps(pack_root: str, tile: str, mesh, tool: str, work: str) -> list[dict]:
    """Each drawn joint of the pack's deck pieces on ``tile``."""
    import drawn_site as DS
    from auto_patch_v2.airport import deck_chain as DC
    rows = [(i, p) for i, p, _r, _t in DS.pack_rows(pack_root, {tile}, work, tool)
            if p.def_path.lower().endswith(".obj")]
    if not rows:
        return []
    la0, lo0 = float(rows[0][1].lat), float(rows[0][1].lon)
    ml, mo = 111132.0, 111320.0 * math.cos(math.radians(la0))
    placed, base = [], []
    for i, p in rows:
        pc = DC.piece_of(os.path.join(pack_root, *p.def_path.split("/")))
        if pc is None:
            continue
        placed.append(DC.Placed(i, p.def_path, float(p.lat), float(p.lon), float(p.heading_deg),
                                ((float(p.lon) - lo0) * mo, (float(p.lat) - la0) * ml), pc))
        base.append(p)
    if not placed:
        return []
    return steps_of(placed, base, mesh.z([p.lat for p in placed], [p.lon for p in placed]))


def steps_of(placed: list, base: list, ground) -> list[dict]:
    """Each joint of the ``deck_chain.Placed`` pieces as drawn: ``base`` the
    pieces' DSF rows, ``ground`` the drawn mesh under each anchor."""
    import drawn_site as DS
    from auto_patch_v2.airport import deck_chain as DC
    out = []
    for i, j, si, sj in DC.joints(placed, DC.ChainLaw()):
        zi, zj = DS.row_base(base[i], ground[i]), DS.row_base(base[j], ground[j])
        if math.isnan(zi) or math.isnan(zj):
            continue
        out.append({"rows": [placed[i].index, placed[j].index],
                    "lat": (placed[i].lat + placed[j].lat) / 2.0,
                    "lon": (placed[i].lon + placed[j].lon) / 2.0,
                    "step": round(float((zi + si) - (zj + sj)), 3),
                    "kinds": [base[i].kind, base[j].kind]})
    return out


def main(argv=None) -> int:
    import drawn_site as DS
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--joints", action="store_true")
    ap.add_argument("--pack", action="append", required=True, help="a pack folder (as written)")
    ap.add_argument("--tile", required=True, help="e.g. +25+055")
    ap.add_argument("--site", action="append", default=[], help="NAME=LAT,LON,R")
    ap.add_argument("--custom-scenery", default=os.path.expanduser("~/X-Plane 12/Custom Scenery"))
    ap.add_argument("--tile-dir", action="append", default=[])
    ap.add_argument("--tile-dsf", default=None)
    ap.add_argument("--box", default=None, help="W,S,E,N: read the mesh (and so the joints) "
                    "over this box only, not the whole tile")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)
    la, lo = int(a.tile[:3]), int(a.tile[3:])
    tool = DS.dsftool()
    sites = [DS.parse_site(s, 100.0) for s in a.site]
    box = (lo + 1e-6, la + 1e-6, lo + 1 - 1e-6, la + 1 - 1e-6)
    if a.box:
        box = tuple(float(q) for q in a.box.split(","))
    mesh = DS.DrawnMesh(box, a.custom_scenery, tool, a.tile_dsf, None, a.tile_dir)
    for t, src in sorted(mesh.sources.items()):
        print(f"mesh {t}: {src}")
    rep = {"packs": {}}
    with tempfile.TemporaryDirectory(prefix="o4_joints_") as work:
        for pack in a.pack:
            js = joint_steps(pack, a.tile, mesh, tool, work)
            rep["packs"][pack] = js
            groups = [("tile", js)] + [
                (s.name, [j for j in js if math.hypot((j["lat"] - s.lat) * 111132.0,
                          (j["lon"] - s.lon) * 111320.0 * math.cos(math.radians(s.lat)))
                          <= s.radius_m]) for s in sites]
            for name, sel in groups:
                st = np.abs([j["step"] for j in sel]) if sel else np.zeros(0)
                if not st.size:
                    print(f"JOINTS {os.path.basename(pack)} {name}: none")
                    continue
                print(f"JOINTS {os.path.basename(pack)} {name}: {st.size} joint(s), step "
                      f"p50 {np.percentile(st, 50):.3f} p90 {np.percentile(st, 90):.3f} "
                      f"p99 {np.percentile(st, 99):.3f} max {st.max():.3f} m, "
                      f"{int((st > 0.05).sum())} over 0.05 m")
            for j in sorted(js, key=lambda j: -abs(j["step"]))[:a.top]:
                print(f"  rows {j['rows']} @{j['lat']:.5f},{j['lon']:.5f} step "
                      f"{j['step']:+.3f} m ({'/'.join(j['kinds'])})")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
