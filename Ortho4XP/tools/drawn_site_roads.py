"""LIBRARY of ``tools/drawn_site.py`` (spec ``docs/specs/2123.md`` A6 / B5,
bars A-2 / A-3 / B-3 / B-4): THE ROADS X-PLANE DRAWS at a site.

``drawn_site --roads`` reads every DSF on the site's tile that carries a
road NETWORK, in X-Plane's load order (``scenery_packs.ini``, highest
first; the X-Plane global scenery last), with the airport pack read from
the ``--pack`` folder given (the copy a lane wrote), and drops a pack's
segments where a HIGHER pack's ``sim/exclude_net`` box covers them (what
X-Plane does).  Each segment within a site's radius is sampled every
:data:`STEP_M` metres:

* its LEVEL (the junction stacking level, X-Plane's "0 on the ground, 1,
  2 ... for overpasses"; a sample takes the higher of its segment's two
  junctions -- how X-Plane raises a bridge's span is NOT read here);
* the DRAWN MESH under it (a level-0 road drapes on it);
* the highest HARD object surface over it (a generated or pack deck) and
  the CLEARANCE between them.

A-2 / A-3 read the clearance of the level-0 samples under a deck; B-3 the
level-0 samples at a generated bridge's ends; B-4 a road-pack segment
near a generated chain.  Nothing is written.
"""
from __future__ import annotations

import glob
import math
import os
import re

import numpy as np

__all__ = ["STEP_M", "network_dsfs", "read_segments", "road_samples", "print_roads"]

#: a road is sampled every this many metres along it
STEP_M = 2.0
_K_LAT = 111320.0
_EXCL = re.compile(r"^PROPERTY\s+sim/exclude_net\s+([-\d.]+)/([-\d.]+)/([-\d.]+)/([-\d.]+)")


def network_dsfs(custom_scenery: str, tile: str, packs=()) -> list[tuple[str, str]]:
    """``(pack name, DSF)`` of every enabled pack with a DSF on ``tile``,
    load order, the global scenery last; a pack named in ``packs`` (a
    folder: the lane's written copy) is read from there."""
    import O4_Scenery_Packs as SP
    over = {os.path.basename(p.rstrip("/")): p for p in packs}
    out = []
    for name in SP.load_order(custom_scenery):
        root = over.get(name, os.path.join(custom_scenery, name))
        got = sorted(glob.glob(os.path.join(root, "Earth nav data", "*", f"{tile}.dsf")))
        if got:
            out.append((name, got[0]))
    xp = os.path.dirname(custom_scenery.rstrip("/"))
    for g in sorted(glob.glob(os.path.join(xp, "Global Scenery", "*", "Earth nav data", "*",
                                           f"{tile}.dsf"))):
        out.append((os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(g)))), g))
    return out


def read_segments(text_path: str, box) -> tuple[list, list]:
    """``(segments, exclusion boxes)`` of a DSFTool dump: each segment
    ``(net, subtype, [(lon, lat, level), ...])`` with any point inside
    ``box`` ``(w, s, e, n)``; the boxes ``(w, s, e, n)`` of its
    ``sim/exclude_net`` rows."""
    w, s, e, n = box
    nets, segs, excl = [], [], []
    cur = None
    with open(text_path, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            if ln.startswith("NETWORK_DEF "):
                nets.append(ln.split(None, 1)[1].strip())
            elif ln.startswith("PROPERTY sim/exclude_net"):
                m = _EXCL.match(ln)
                if m:
                    excl.append(tuple(float(v) for v in m.groups()))
            elif ln.startswith("BEGIN_SEGMENT"):
                t = ln.split()
                cur = (int(t[1]), int(t[2]), [(float(t[4]), float(t[5]), float(t[6]))])
            elif ln.startswith("SHAPE_POINT") and cur is not None:
                t = ln.split()
                cur[2].append((float(t[1]), float(t[2]), None))
            elif ln.startswith("END_SEGMENT") and cur is not None:
                t = ln.split()
                cur[2].append((float(t[2]), float(t[3]), float(t[4])))
                if any(w <= p[0] <= e and s <= p[1] <= n for p in cur[2]):
                    net = nets[cur[0]] if cur[0] < len(nets) else "?"
                    segs.append((net, cur[1], cur[2]))
                cur = None
    return segs, excl


def _inside(lon: float, lat: float, boxes) -> bool:
    return any(b[0] <= lon <= b[2] and b[1] <= lat <= b[3] for b in boxes)


def road_samples(site, dsfs, tool: str, work: str, mesh, over=None) -> list[dict]:
    """Every drawn road sample within ``site``'s radius (module doc);
    ``over(lats, lons)`` the highest hard object surface there (``nan``
    for none)."""
    from auto_patch_v2.airport.dsf_write import dump
    kx = _K_LAT * math.cos(math.radians(site.lat))
    r = max(site.radius_m, 1.0)
    box = (site.lon - r / kx, site.lat - r / _K_LAT, site.lon + r / kx, site.lat + r / _K_LAT)
    higher: list = []
    out: list[dict] = []
    for name, dsf in dsfs:
        txt = os.path.join(work, f"roads_{abs(hash(dsf))}.txt")
        if not os.path.isfile(txt):
            try:
                dump(dsf, txt, tool)
            except Exception:                        # an unreadable DSF draws nothing
                continue
        segs, excl = read_segments(txt, box)
        for net, sub, pts in segs:
            lv = max(pts[0][2] or 0.0, pts[-1][2] or 0.0)
            for (lo0, la0, _a), (lo1, la1, _b) in zip(pts[:-1], pts[1:]):
                d = math.hypot((lo1 - lo0) * kx, (la1 - la0) * _K_LAT)
                for k in range(max(1, int(d / STEP_M)) + 1):
                    f = k / max(1, int(d / STEP_M))
                    lo, la = lo0 + f * (lo1 - lo0), la0 + f * (la1 - la0)
                    if math.hypot((lo - site.lon) * kx, (la - site.lat) * _K_LAT) > r:
                        continue
                    if _inside(lo, la, higher):
                        continue
                    out.append({"pack": name, "net": os.path.basename(net), "subtype": sub,
                                "level": int(lv), "lat": round(la, 7), "lon": round(lo, 7)})
        higher += excl
    if out:
        lats = np.array([q["lat"] for q in out])
        lons = np.array([q["lon"] for q in out])
        mz = mesh.z(lats, lons)
        oz = over(lats, lons) if over is not None else np.full(len(out), np.nan)
        for q, a, b in zip(out, mz, oz, strict=True):
            q["mesh_z"] = None if math.isnan(a) else round(float(a), 3)
            q["over_z"] = None if math.isnan(b) else round(float(b), 3)
            q["clear_m"] = (None if math.isnan(a) or math.isnan(b)
                            else round(float(b - a), 3))
    return out


def print_roads(site_rec: dict) -> None:
    """One summary line per site and road class, and the least clearance."""
    roads = site_rec.get("roads") or []
    print(f"ROADS {site_rec['name']}: {len(roads)} drawn sample(s)")
    by: dict = {}
    for q in roads:
        by.setdefault((q["pack"], q["net"], q["subtype"], q["level"]), []).append(q)
    for (pack, net, sub, lv), qs in sorted(by.items()):
        cl = [q["clear_m"] for q in qs if q.get("clear_m") is not None]
        print(f"  {pack} {net} type {sub} level {lv}: {len(qs)} sample(s)"
              + (f", under a hard surface: {len(cl)}, least clearance {min(cl):.2f} m"
                 if cl else ", none under a hard surface"))
