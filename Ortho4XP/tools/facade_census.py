#!/usr/bin/env python
"""THE FACADE READ of a DSF text dump (issue #334): per ``.fac`` def the
count, the class the FILE declares (line / roofed / lot /
parking_structure), the plan area, the DSF depths, and the objects each
PLACED wall attaches with their outward reach.  A report over
``auto_patch_v2.airport.facade`` (the engine's reader; the census itself
lives here, RULINGS 2026-10-04c (4)) — it prices no law and counts no
defects.

    venv/bin/python tools/facade_census.py DUMP.text [--pack-root DIR]
        [--site LAT,LON [--radius-deg D]] [--polygons] [--json OUT]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import typing

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))

from auto_patch_v2.airport import facade  # noqa: E402


def census(polygons: typing.Iterable[typing.Any], pack_root: str | None,
           index: typing.Mapping[str, str] | None,
           keep: typing.Callable[[float, float], bool] | None = None
           ) -> dict[str, dict[str, typing.Any]]:
    """THE READ of a dump's facade polygons (``dsf.DsfPolygon`` rows with
    their ``nodes``), per def: count, class, plan area of the closed
    classes, the DSF depths, and per wall actually PLACED the attachments
    with their reach and the edge metres carrying them; ``undecided`` =
    edges of a no-wall-index polygon whose fitting walls disagree.  A
    report — it prices no law."""
    rows: dict[str, dict[str, typing.Any]] = {}
    for poly in polygons:
        if not poly.def_path.lower().endswith(".fac") or not poly.nodes:
            continue
        ring = poly.nodes[0]
        lat0 = sum(p[1] for p in ring) / len(ring)
        lon0 = sum(p[0] for p in ring) / len(ring)
        if keep is not None and not keep(lat0, lon0):
            continue
        r = rows.setdefault(poly.def_path, {
            "n": 0, "class": "unresolved", "file": None, "area_m2": 0.0,
            "depths": {}, "attachments": {}, "undecided": [], "polygons": []})
        r["n"] += 1
        r["depths"][poly.depth] = r["depths"].get(poly.depth, 0) + 1
        fac = facade.read_facade(poly.def_path, pack_root, index)
        if fac is None:
            continue
        r["class"], r["file"] = facade.facade_class(fac), fac.path
        kx = 111320.0 * math.cos(math.radians(lat0))
        xy = [((p[0] - lon0) * kx, (p[1] - lat0) * 110574.0, p[2], p[3])
              for p in ring]
        area = abs(sum(xy[i][0] * xy[(i + 1) % len(xy)][1]
                       - xy[(i + 1) % len(xy)][0] * xy[i][1]
                       for i in range(len(xy)))) / 2.0
        if r["class"] != facade.LINE:
            r["area_m2"] += area
        prow = {"lat": lat0, "lon": lon0, "depth": poly.depth,
                "height": poly.param, "area_m2": area, "edges": []}
        for e in facade.placed_edges(fac, float(poly.param), xy):
            if e.wall.wall is None and not e.wall.from_dsf and r["class"] != facade.LINE:
                r["undecided"].append((lat0, lon0, e.i, e.length_m))
            for a in e.attachments:
                key = (e.name, a.kind, a.obj)
                acc = r["attachments"].setdefault(
                    key, {"reach": a.reach, "variants": a.variants,
                          "edges": 0, "edge_m": 0.0})
                acc["edges"] += 1
                acc["edge_m"] += e.length_m
            prow["edges"].append((e.i, e.length_m, e.wall.wall, e.name, e.curved,
                                  max((a.reach[1] for a in e.attachments
                                       if a.reach is not None), default=0.0)))
        r["polygons"].append(prow)
    return rows


def main(argv: list[str] | None = None) -> int:
    # The console is UTF-8 before the parser can print (#171, #125); a
    # library with a CLI pins in its entry.  Twin: test_console_encoding.
    import O4_Console_Encoding
    O4_Console_Encoding.configure_console_streams()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("dump")
    ap.add_argument("--pack-root", default=None)
    ap.add_argument("--site", default=None, help="LAT,LON window centre")
    ap.add_argument("--radius-deg", type=float, default=0.05)
    ap.add_argument("--polygons", action="store_true",
                    help="also print every polygon carrying a reach >= 1 m")
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)
    from auto_patch_v2.airport import dsf, obj8
    from auto_patch_v2.planar.__main__ import default_inputs
    inp = default_inputs()
    index = obj8.read_library_index(
        obj8.library_index_path(inp.mod_cache_root, inp.xplane_root))
    if index is None:
        print("library index ABSENT — attachments resolve pack-relative only")
    keep = None
    if a.site:
        la, lo = (float(v) for v in a.site.split(","))
        keep = lambda lat, lon: (abs(lat - la) <= a.radius_deg  # noqa: E731
                                 and abs(lon - lo) <= a.radius_deg)
    dump = dsf.read_dump(a.dump, lambda p: p.lower().endswith(".fac"))
    rows = census(dump.polygons, a.pack_root, index, keep)
    total = 0
    for d, r in sorted(rows.items(), key=lambda kv: -kv[1]["n"]):
        total += r["n"]
        print(f"{r['n']:4d} {d:78s} {r['class']:18s} area {r['area_m2']:9.0f} m2 "
              f"depth {dict(sorted(r['depths'].items()))} role "
              f"{dsf.building_role_for_def(d)} -> "
              f"{os.path.basename(r['file']) if r['file'] else None}")
        for (wall, kind, obj), v in sorted(r["attachments"].items()):
            reach = "unresolved" if v["reach"] is None else \
                f"{v['reach'][0]:+.1f}..{v['reach'][1]:+.1f} m"
            print(f"       {wall:30s} {kind:6s} {os.path.basename(obj):34s} reach "
                  f"{reach:18s} variants {v['variants']:2d} edges {v['edges']:3d} "
                  f"{v['edge_m']:7.1f} m")
        for lat, lon, i, length in r["undecided"]:
            print(f"       UNDECIDED wall (no DSF index, fitting walls differ): "
                  f"edge {i} {length:.1f} m of the polygon at {lat:.6f}, {lon:.6f}")
        if a.polygons:
            for p in r["polygons"]:
                hot = [e for e in p["edges"] if e[5] >= 1.0]
                if hot:
                    print(f"       POLYGON {p['lat']:.6f}, {p['lon']:.6f} depth "
                          f"{p['depth']} h {p['height']} area {p['area_m2']:.0f} m2: "
                          + "; ".join(f"edge {e[0]} {e[1]:.1f} m wall {e[2]} {e[3]}"
                                      f"{' curved' if e[4] else ''} reach {e[5]:.1f}"
                                      for e in hot))
    print(f"total facade polygons {total} in {len(rows)} defs")
    if a.json:
        with open(a.json, "w", newline="\n") as fh:
            json.dump({d: {**r, "attachments": [
                {"wall": k[0], "kind": k[1], "obj": k[2], **v}
                for k, v in sorted(r["attachments"].items())]}
                for d, r in rows.items()}, fh, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
