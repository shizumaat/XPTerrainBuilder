"""THE PAD EDGE READ — every steep pad edge of a graded surface, read as
BARE or PAVEMENT-ADJACENT (owner RULINGS 2026-10-09d (1)).

    venv/bin/python tools/pad_edge_read.py GRADED.json --capture CAP.pkl \
        [--off 1.0] [--within 10] [--standoff 3] [--json OUT.json] [--top N]

The ruling: a pad edge with NO pavement against it meets raw DEM with
whatever bank the mesh gives (accepted, listed only); a pad edge WITH
pavement against it welds, the pavement graded inside its own cap; where
that cannot hold, the pad's SEAT is the defect.  This reader finds every
pad-rim vertex where the surface outside the pad stands more than ``--off``
metres off the rim within ``--within`` metres of it, and classes it by WHAT
that surface is:

* ``P``  PAVEMENT OFF — a pavement cell that touches the vertex, or lies
  within ``--standoff`` of it, itself stands more than ``--off`` off the rim
  inside ``--within`` (a welded cell climbing/falling away, or an unwelded
  cell across a sliver): the seat-defect candidates.  Per cell: ``step`` =
  its level at its boundary point nearest the vertex, minus the rim (0 for a
  touching cell — one vertex, one level); ``off`` = its worst level off the
  rim inside ``--within``; ``grade`` = the steepest rise from the rim vertex
  to a vertex of a touching cell.
* ``M``  PAVEMENT BESIDE A BARE BANK — pavement touches or is within the
  stand-off and stays within ``--off`` of the rim; the height is ungraded
  ground beside it.
* ``S``  GRADED STRIP — only a graded strip (airside graded ground, not
  pavement) is against the vertex.
* ``B``  BARE — nothing but ungraded ground within the stand-off.

A RUN is a chain of same-class flagged vertices along one pad's rim.  The
ground is the build's own DEM (``airport.dem`` of a ``v2_solve_replay
--capture`` pickle — the emitted patch carries no DEM), sampled on eight
bearings at 2 / 5 / ``--within`` metres wherever no patch cell covers the
sample.  It PRICES NO LAW AND COUNTS NO DEFECTS — defect counts come from
``tools/harness/census.py`` and nowhere else.

Promoted from lane pads66's scratch ``bank.py`` on its second use (lane
pads67; RULINGS ``7e90032``).  Twin: ``tests/test_pad_edge_read.py``.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import pickle
import sys
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Sequence

#: roles that are a pad, graded ground, or a structure — never "pavement
#: against the pad" in the ruling's sense
PAD_ROLE = "building"
STRIP_ROLES = frozenset({"graded_strip"})
STRUCTURE_ROLES = frozenset({"retaining_wall"})
BEARINGS = 8
INNER_RADII = (2.0, 5.0)

Dem = Callable[[float, float], float]   # (lat, lon) -> metres


def _metres(lat0: float, lon0: float, lat: float, lon: float) -> tuple[float, float]:
    """Local tangent metres of (lat, lon) about (lat0, lon0)."""
    return ((lon - lon0) * 111320.0 * math.cos(math.radians(lat0)),
            (lat - lat0) * 110574.0)


def _rings(face: dict) -> list[list[int]]:
    return [face["ring"]] + [h for h in (face.get("holes") or [])]


def _pad_ref(face: dict) -> str:
    return str(face["ref"]).split("#collar")[0]


def _kind(role: str) -> str:
    if role == PAD_ROLE:
        return "pad"
    if role in STRIP_ROLES:
        return "strip"
    if role in STRUCTURE_ROLES:
        return "structure"
    return "pavement"


def read_edges(graded: dict, dem: Optional[Dem], *, off_m: float = 1.0,
               within_m: float = 10.0, standoff_m: float = 3.0) -> list[dict]:
    """The runs of ``graded`` (a ``graded_surface/1`` dict), worst first."""
    from shapely.geometry import Point, Polygon
    from shapely.strtree import STRtree

    lat0, lon0 = graded["frame"]["origin"]
    V = {v[0]: v for v in graded["vertices"]}
    xy = {i: _metres(lat0, lon0, v[1], v[2]) for i, v in V.items()}
    faces = graded["faces"]
    polys = []
    for f in faces:
        ext = [xy[i] for i in f["ring"]]
        holes = [[xy[i] for i in h] for h in (f.get("holes") or []) if len(h) >= 3]
        p = Polygon(ext, holes) if len(ext) >= 3 else Polygon()
        polys.append(p if p.is_valid else p.buffer(0))
    tree = STRtree(polys)
    at: dict[int, list[int]] = collections.defaultdict(list)       # vertex -> faces
    edge_faces: dict[frozenset, list[int]] = collections.defaultdict(list)
    for k, f in enumerate(faces):
        for r in _rings(f):
            for a, b in zip(r, r[1:] + r[:1]):
                at[a].append(k)
                if a != b:
                    edge_faces[frozenset((a, b))].append(k)
    # rim edges: one side a pad face, the other side not a pad face
    rim: dict[str, dict[int, set[int]]] = collections.defaultdict(lambda: collections.defaultdict(set))
    for e, ks in edge_faces.items():
        pads = {_pad_ref(faces[k]) for k in ks if faces[k]["role"] == PAD_ROLE}
        if len(pads) == 1 and (len(ks) == 1 or any(faces[k]["role"] != PAD_ROLE for k in ks)):
            a, b = tuple(e)
            ref = next(iter(pads))
            rim[ref][a].add(b)
            rim[ref][b].add(a)

    def covered(x: float, y: float) -> bool:
        pt = Point(x, y)
        return any(polys[int(k)].covers(pt) for k in tree.query(pt))

    def ground(v: int) -> Optional[tuple[float, float]]:
        """(signed off, distance) of the worst uncovered DEM sample about v."""
        if dem is None:
            return None
        x, y = xy[v]
        best = None
        for r in (*INNER_RADII, within_m):
            for j in range(BEARINGS):
                t = 2 * math.pi * j / BEARINGS
                px, py = x + r * math.cos(t), y + r * math.sin(t)
                if covered(px, py):
                    continue
                lat = lat0 + py / 110574.0
                lon = lon0 + px / (111320.0 * math.cos(math.radians(lat0)))
                d = dem(lat, lon) - V[v][3]
                if best is None or abs(d) > abs(best[0]):
                    best = (d, r)
        return best

    def nearest_z(f: dict, x: float, y: float) -> float:
        """The level of cell ``f`` at its boundary point nearest (x, y),
        interpolated along that ring segment."""
        best = (math.inf, 0.0)
        for r in _rings(f):
            for a, b in zip(r, r[1:] + r[:1]):
                (ax, ay), (bx, by) = xy[a], xy[b]
                l2 = (bx - ax) ** 2 + (by - ay) ** 2
                t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / l2))
                d = math.hypot(ax + t * (bx - ax) - x, ay + t * (by - ay) - y)
                if d < best[0]:
                    best = (d, V[a][3] + t * (V[b][3] - V[a][3]))
        return best[1]

    def cells(v: int) -> list[dict]:
        """Every non-pad cell touching v or within ``within_m`` of it: its
        distance and its worst level off the rim inside ``within_m``."""
        x, y = xy[v]
        pt = Point(x, y)
        out = []
        touching = set(at[v])
        for k in set(int(i) for i in tree.query(pt.buffer(within_m))) | touching:
            f = faces[k]
            if f["role"] == PAD_ROLE:
                continue
            d = 0.0 if k in touching else polys[k].distance(pt)
            if d > within_m:
                continue
            step = 0.0 if k in touching else nearest_z(f, x, y) - V[v][3]
            worst, grade = step, 0.0
            for r in _rings(f):
                for i in r:
                    if i == v:
                        continue
                    di = math.hypot(xy[i][0] - x, xy[i][1] - y)
                    if di <= max(within_m, d + 1e-6):
                        dz = V[i][3] - V[v][3]
                        if abs(dz) > abs(worst):
                            worst = dz
                        if k in touching and di > 0.5:
                            grade = max(grade, abs(dz) / di)
            out.append({"role": f["role"], "ref": str(f["ref"]), "kind": _kind(f["role"]),
                        "dist_m": round(d, 2), "step_m": round(step, 2), "off_m": round(worst, 2),
                        "touching": k in touching, "grade_pct": round(100 * grade, 1)})
        return out

    flagged: dict[str, dict[int, dict]] = collections.defaultdict(dict)
    for ref, adj in rim.items():
        for v in adj:
            cs = cells(v)
            near = [c for c in cs if c["dist_m"] <= standoff_m]
            pav = [c for c in near if c["kind"] == "pavement"]
            pav_off = max((abs(c["off_m"]) for c in pav), default=0.0)
            far_off = max((abs(c["off_m"]) for c in cs), default=0.0)
            g = ground(v)
            dem_off = abs(g[0]) if g else 0.0
            if max(dem_off, far_off) <= off_m:
                continue
            if pav and pav_off > off_m:
                cls = "P"
            elif pav:
                cls = "M"
            elif any(c["kind"] == "strip" for c in near):
                cls = "S"
            else:
                cls = "B"
            flagged[ref][v] = {"cls": cls, "cells": cs, "ground": g, "pav_off": pav_off,
                               "height": max(dem_off, far_off)}
    runs = []
    for ref, fl in flagged.items():
        seen: set[int] = set()
        for v0 in fl:
            if v0 in seen:
                continue
            comp, stack = [], [v0]
            seen.add(v0)
            while stack:
                v = stack.pop()
                comp.append(v)
                for u in rim[ref][v]:
                    if u in fl and u not in seen and fl[u]["cls"] == fl[v0]["cls"]:
                        seen.add(u)
                        stack.append(u)
            cset = set(comp)
            length = sum(math.hypot(xy[a][0] - xy[b][0], xy[a][1] - xy[b][1])
                         for a in comp for b in rim[ref][a] if b in cset and a < b)
            w = max(comp, key=lambda v: fl[v]["height"])
            pav = {}
            for v in comp:
                for c in fl[v]["cells"]:
                    if c["kind"] != "pad":
                        key = f'{c["role"]}:{c["ref"]}'
                        p = pav.setdefault(key, {"cell": key, "kind": c["kind"], "dist_m": c["dist_m"],
                                                 "step_m": c["step_m"], "off_m": c["off_m"], "touching": c["touching"],
                                                 "grade_pct": c["grade_pct"]})
                        p["dist_m"] = min(p["dist_m"], c["dist_m"])
                        p["touching"] = p["touching"] or c["touching"]
                        p["grade_pct"] = max(p["grade_pct"], c["grade_pct"])
                        if abs(c["step_m"]) > abs(p["step_m"]):
                            p["step_m"] = c["step_m"]
                        if abs(c["off_m"]) > abs(p["off_m"]):
                            p["off_m"] = c["off_m"]
            zs = [V[v][3] for v in comp]
            g = fl[w]["ground"]
            runs.append({"cls": fl[v0]["cls"], "pad": ref, "vertices": len(comp),
                         "length_m": round(length, 1), "site": [V[w][1], V[w][2]],
                         "rim_z": [min(zs), max(zs)], "height_m": round(fl[w]["height"], 2),
                         "ground_off_m": None if g is None else round(g[0], 2),
                         "pavement_off_m": round(max(fl[v]["pav_off"] for v in comp), 2),
                         "cells": sorted(pav.values(), key=lambda p: (p["dist_m"], -abs(p["off_m"])))})
    runs.sort(key=lambda r: (-r["height_m"], r["pad"]))
    return runs


def capture_dem(path: Path) -> Dem:
    """The build's DEM off a ``v2_solve_replay --capture`` pickle, as (lat, lon) -> z."""
    here = Path(__file__).resolve().parents[1]
    for p in (str(here / "src"), str(here / "tools")):
        if p not in sys.path:
            sys.path.insert(0, p)
    with open(path, "rb") as fh:
        rec = pickle.load(fh)
    sampler = rec["airport"].dem
    from pyproj import Transformer
    fwd = Transformer.from_crs("EPSG:4326", sampler.frame.crs, always_xy=True)

    def dem(lat: float, lon: float) -> float:
        x, y = fwd.transform(lon, lat)
        return float(sampler.z(x, y))
    return dem


NAMES = {"P": "PAVEMENT OFF (seat candidates)", "M": "PAVEMENT BESIDE A BARE BANK",
         "S": "GRADED STRIP", "B": "BARE (accepted by 2026-10-09d (1))"}


def render(runs: Sequence[dict], top: int = 0) -> Iterable[str]:
    for cls in "PMSB":
        rs = [r for r in runs if r["cls"] == cls]
        yield (f"== {cls}  {NAMES[cls]}: {len(rs)} run(s), {sum(r['vertices'] for r in rs)} vertices, "
               f"{sum(r['length_m'] for r in rs):.0f} m, worst {max((r['height_m'] for r in rs), default=0):.2f} m")
        for r in (rs[:top] if top else rs):
            yield (f"   {r['pad']:26s} {r['site'][0]:.11f}, {r['site'][1]:.11f}  height {r['height_m']:6.2f}  "
                   f"ground {r['ground_off_m']}  pavement {r['pavement_off_m']:5.2f}  n {r['vertices']:3d}  "
                   f"{r['length_m']:6.1f} m  rim {r['rim_z'][0]:.2f}..{r['rim_z'][1]:.2f}")
            for c in r["cells"][:4] if cls != "B" else r["cells"][:1]:
                yield (f"        {c['cell'][:44]:44s} {'TOUCH' if c['touching'] else 'near '} {c['dist_m']:5.2f} m  "
                       f"step {c['step_m']:+6.2f}  off {c['off_m']:+6.2f}  grade {c['grade_pct']:5.1f} %")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("graded", type=Path)
    ap.add_argument("--capture", type=Path, help="a v2_solve_replay --capture pickle: the build's DEM")
    ap.add_argument("--off", type=float, default=1.0)
    ap.add_argument("--within", type=float, default=10.0)
    ap.add_argument("--standoff", type=float, default=3.0)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--top", type=int, default=0)
    a = ap.parse_args(argv)
    if not a.graded.is_file():
        print(f"REFUSED: no graded surface at {a.graded}", file=sys.stderr)
        return 2
    graded: dict[str, Any] = json.loads(a.graded.read_text())
    dem = capture_dem(a.capture) if a.capture else None
    if dem is None:
        print("NO DEM (--capture absent): only patch cells are read; a BARE edge cannot be seen")
    runs = read_edges(graded, dem, off_m=a.off, within_m=a.within, standoff_m=a.standoff)
    print(f"{graded.get('icao')}: pad edges standing > {a.off} m off within {a.within} m "
          f"(stand-off {a.standoff} m): {len(runs)} run(s)")
    for line in render(runs, a.top):
        print(line)
    if a.json:
        a.json.write_text(json.dumps({"icao": graded.get("icao"), "off_m": a.off, "within_m": a.within,
                                      "standoff_m": a.standoff, "dem": bool(dem), "runs": runs}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
