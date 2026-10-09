"""zonefloor: what the zone-part WIDTH floor (planar/zones._unmeshable) changes at
the planar stage.  Classify once; per arm re-run the planar stage only (--pad-read:
dry) and dump the zone parts, the runway-ring vertex keys and a digest of the map.

    cd Ortho4XP && venv/bin/python ../docs/briefs/zonefloor/zone_probe.py CAPTURE.pkl OUT.json ARM [ARM ...]

ARM = letters: F (floor ON; absent = the floor disabled), T (the gap-apron
claim trim ON; absent = every gap-apron cell put back INTO the claim).
"FT" is the tree; "T" is the branch base; "F" is the frame twin's arm; "-" neither.
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path[:0] = ["src", ".", "tools"]


def main() -> None:
    pkl, out, arms = sys.argv[1], sys.argv[2], sys.argv[3:]
    import auto_patch_v2.classify as _cl
    import auto_patch_v2.planar.overlay as _ov
    import auto_patch_v2.planar.zones as _z
    import v2_solve_replay as _r
    memo: dict = {}
    _orig_cl = _cl.classify

    def _classify(airport, law, rules=None, cache=None):
        if "cl" not in memo:
            memo["cl"] = _orig_cl(airport, law, rules, cache=cache)
        return memo["cl"]
    _cl.classify = _classify
    floor, gap_ref, zr = _z._unmeshable, _z.is_gap_apron_ref, _ov.zone_regions
    calls: list = []

    def _zr(*a, **k):
        res = zr(*a, **k)
        calls.append(res)
        return res
    _ov.zone_regions = _zr
    res = json.load(open(out)) if Path(out).exists() else {}
    for arm in arms:
        _z._unmeshable = floor if "F" in arm else (lambda g, s: False)
        _z.is_gap_apron_ref = gap_ref if "T" in arm else (lambda ref: False)
        calls.clear()
        r = _r.replay_problem(Path(pkl), "classify", [], None, (), placement={}, sites=[],
                              pad_read_only=True)
        pm = r["pm"]
        rw, h = set(), hashlib.sha256()
        for fid in sorted(pm.faces):
            f = pm.faces[fid]
            keys = [[tuple(pm.vertices[v].key) for v in pm.ring_vertices(ring)]
                    for ring in (f.ring, *f.holes)]
            h.update(repr((f.role, f.ref, keys)).encode())
            if f.role in ("runway", "runway_crossing"):
                rw.update(k for ring in keys for k in ring)
        to_ll = memo["cl"] and r.get("airport") and r["airport"].frame.transformers()[1]
        zones = []
        for z in calls[0]:
            g = z.polygon
            c = g.representative_point()
            ll = to_ll(c.x, c.y) if to_ll else (c.x, c.y)
            zones.append({"ref": z.ref, "area": g.area, "len": g.length,
                          "thin": bool(floor(g, 0.5)), "at": [round(ll[1], 7), round(ll[0], 7)],
                          "wkb": hashlib.sha1(g.normalize().wkb).hexdigest()})
        res[arm] = {"zone_calls": len(calls), "zones": zones, "runway": sorted(rw),
                    "map": h.hexdigest(), "n_vertices": len(pm.vertices), "n_faces": len(pm.faces)}
        print("ARM", arm, "zones", len(zones), "thin", sum(z["thin"] for z in zones),
              "runway vertices", len(rw), "map", h.hexdigest()[:12], flush=True)
        json.dump(res, open(out, "w"))
    base = arms[0]
    b = res[base]
    for arm in arms[1:]:
        a = res[arm]
        sa, sb = set(map(tuple, a["runway"])), set(map(tuple, b["runway"]))
        wa, wb = {z["wkb"] for z in a["zones"]}, {z["wkb"] for z in b["zones"]}
        print(f"{base} -> {arm}: runway +{len(sa - sb)} / -{len(sb - sa)}; zone parts only-{base} "
              f"{len(wb - wa)} only-{arm} {len(wa - wb)}; map {'=' if a['map'] == b['map'] else 'DIFFERS'}")
        for z in b["zones"]:
            if z["wkb"] not in wa:
                print(f"   only-{base}: {z['ref']} {z['area']:.2f} m2 perim {z['len']:.1f} m thin={z['thin']} at {z['at']}")
        for z in a["zones"]:
            if z["wkb"] not in wb:
                print(f"   only-{arm}: {z['ref']} {z['area']:.2f} m2 perim {z['len']:.1f} m thin={z['thin']} at {z['at']}")


if __name__ == "__main__":
    main()
