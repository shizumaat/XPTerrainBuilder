#!/usr/bin/env python3
"""THE SEAT RESIDUAL AT EVERY PLACEMENT'S FEET (RULINGS 2026-09-09ac (3)).

The instrument the LEMD seat rounds are judged on: for every OBJ
placement of a pack, the vertical gap between the mesh under each of the
object's GROUND components' lowest vertices and where that vertex will
render after the re-seat —

    |dz| = mesh(foot) - (mesh(anchor) + y_foot + delta(component))

computed from the AUTHORED pack (``.anchor_bak`` when one exists —
restore-before-read, RULINGS 2026-09-04 v2rebake), a seat RESULT's
per-component deltas and ONE mesh.  Nothing is written to the pack, so
two seat arms are compared against the SAME terrain without a build
between them: run ``v2_rebake_replay.py seat PLAN MESH`` per arm and
census each result here.

    venv/bin/python tools/seat_feet_census.py RESULT.json --mesh MESH \\
        [--plan PLAN.json] [--pack ROOT] [--dsf-dump DUMP.text] \\
        [--label L] [--top 30] [--json OUT.json]

``--plan`` supplies the pack root and the skip reasons that name each
unseated placement's CLASS (the by-class table below); without it every
unseated placement reads "not in plan".  The DSF text dump is the
DSFTool ``--dsf2text`` output already in the mod cache — it is only ever
READ here (never regenerated: the churn ruling), and is found from the
pack automatically when ``--dsf-dump`` is not given.

Output: the |Δ| histogram (< 0.3 / 0.3-1 / 1-3 / > 3 m), the same by
CLASS, and the worst N placements with lat/lon.  Promoted from the
`v2lemdseats` lane's ``measure6.py`` on its third use.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

import numpy as np  # noqa: E402

from auto_patch.mesh_sampler import MeshElevationSampler  # noqa: E402
from auto_patch_v2.airport import obj8  # noqa: E402

#: metres per degree of latitude (the frame every v2 reader uses)
MLAT = 111132.0

#: how a skip reason from the plan is spelled in the by-class table
_CLASSES = (("stock", "stock library"),
            ("placed at", "multi-anchor resource"),
            ("no genuine", "no ground contacts (plan)"),
            ("below-grade", "below-grade skip"),
            ("basin facility", "terrain-adapted (structure member)"),
            ("resolves outside", "outside pack"))


def find_dsf_dump(pack_root: str) -> str | None:
    """The pack's cached DSFTool text dump, READ-ONLY.

    The cache names a dump ``<dsf basename>.<sha1(abs dsf path)[:8]>.text``
    under the airport mod cache (``auto_patch.dsf_reader``); this looks
    only for one that already EXISTS — DSFTool is never run here, so a
    census can never regenerate a shared-repo artefact as a side effect.
    """
    from auto_patch.dsf_reader import airport_mod_cache_dir, _default_pack_text_cache_path
    cache = airport_mod_cache_dir(pack_root)
    if not cache:
        return None
    for d in sorted(glob.glob(os.path.join(pack_root, "Earth nav data", "*", "*.dsf"))
                    + glob.glob(os.path.join(pack_root, "Earth nav data", "*.dsf"))):
        cand = _default_pack_text_cache_path(cache, d)
        if os.path.isfile(cand):
            return cand
    return None


def read_result(path: str) -> tuple[dict[str, dict[int, float]], dict[str, float]]:
    """``resource -> {component: delta}``, the member's own delta, and
    the LINE OBJECTS' drape stations (RULINGS 2026-09-10bb).

    Reads either a seat RESULT (``o4_v2_rebake_result_<ICAO>.json``) or a
    ``v2_rebake_replay.py seat`` ``*.seat.json`` (whose ``seat`` key
    holds the same record).  A structure-seated member carries one
    ``delta_m``; a plate unit's delta stands in for its members.
    """
    with open(path) as fh:
        res = json.load(fh)
    res = res.get("seat", res)
    deltas: dict[str, dict[int, float]] = {}
    member_delta: dict[str, float] = {}
    # THE LINE OBJECT'S DRAPE STATIONS (RULINGS 2026-09-10bb, spec §16):
    # resource -> comp -> [(lat, lon, delta)].  A foot inside a draped
    # component reads the station NEAREST it, not the component's median
    # — otherwise the census measures a seat the writer never applied.
    stations: dict[str, dict[int, list[tuple[float, float, float]]]] = {}
    for u in res["units"]:
        for m in u["members"]:
            d = deltas.setdefault(m["resource"], {})
            for row in (m.get("line_stations") or []):
                comp, la, lo, dz = row
                stations.setdefault(m["resource"], {}).setdefault(
                    int(comp), []).append((float(la), float(lo), float(dz)))
            for row in (m.get("part_deltas") or []):
                comp, _cluster, dz = row
                if dz is not None:
                    d[int(comp)] = float(dz)
            if m.get("delta_m") is not None:
                member_delta[m["resource"]] = float(m["delta_m"])
            elif u.get("delta_m") is not None and u.get("datum") == "plate":
                member_delta.setdefault(m["resource"], float(u["delta_m"]))
    return deltas, member_delta, stations


def read_placements(dump: str) -> tuple[list[str], list[tuple[int, float, float, float]]]:
    """``OBJECT_DEF`` paths and ``OBJECT`` placements from a text dump."""
    defs: list[str] = []
    plc: list[tuple[int, float, float, float]] = []
    with open(dump, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("OBJECT_DEF "):
                defs.append(line[11:].strip())
            elif line.startswith("OBJECT "):
                p = line.split()
                plc.append((int(p[1]), float(p[2]), float(p[3]), float(p[4])))
    return defs, plc


def read_feet(pack_root: str, path: str, thickness: float = 0.5,
              max_feet: int = 16) -> dict | str:
    """The object's GROUND components' feet, or why it has none.

    A foot is the lowest vertex of a genuine solid component (y-extent at
    least ``thickness`` — a decal never stands on the ground) whose own
    base is within 1 m of the file's base: those are the components that
    touch the terrain, and their residual is what the eye reads in the
    sim.  The AUTHORED file is read (``.anchor_bak`` first).
    """
    live = os.path.join(pack_root, path.replace("\\", "/"))
    src = live + ".anchor_bak" if os.path.isfile(live + ".anchor_bak") else live
    if not os.path.isfile(src):
        return "missing"
    geom = obj8.parse_obj8(src)
    if geom.solid.shape[0] == 0:
        return "no solid geometry"
    v = geom.vertices
    vi = np.unique(geom.solid.reshape(-1))
    base = float(v[vi][:, 1].min())
    if base > 1.0:
        return "elevated base (+%.1f m)" % base
    if base < -2.0:
        return "buried base (%.1f m)" % base
    feet = []
    for ci, c in enumerate(obj8.solid_components(geom)):
        if c.max_y - c.min_y < thickness or c.min_y > base + 1.0:
            continue
        pts = v[np.unique(c.tris.reshape(-1))]
        q = pts[int(np.argmin(pts[:, 1]))]
        feet.append((ci, float(q[0]), float(q[1]), float(q[2]),
                     float(np.ptp(pts[:, 0]) * np.ptp(pts[:, 2]))))
    if not feet:
        return "no thick ground component"
    feet.sort(key=lambda f: -f[4])
    return dict(path=path, feet=feet[:max_feet], base=base,
                span=float(np.hypot(np.ptp(v[vi][:, 0]), np.ptp(v[vi][:, 2]))))


def census(rows: list[dict], skipped: dict[str, str], seated: set[str],
           label: str, top: int, line_objects: set[str] = frozenset()) -> None:
    """The histogram, the by-class table and the worst ``top``."""
    def klass(path: str) -> str:
        if path in line_objects:
            return "SEATED (line object, draped)"
        if path in seated:
            return "SEATED"
        s = skipped.get(path)
        if s is None:
            return "not in plan"
        for pre, lab in _CLASSES:
            if s.startswith(pre):
                return lab
        return s[:32]

    def bucket(a: float) -> str:
        return "<0.3" if a < 0.3 else "0.3-1" if a < 1 else "1-3" if a < 3 else ">3"

    meas = [r for r in rows if r["kind"] == "measured"]
    if not meas:
        print(f"== {label}: no placement measured (of {len(rows)} OBJ placements)")
        return
    hist = collections.Counter(bucket(abs(r["dmax"])) for r in meas)
    print(f"== {label}: {len(meas)} measured placements (of {len(rows)} OBJ placements)")
    for k in ("<0.3", "0.3-1", "1-3", ">3"):
        print(f"   {k:6s} {hist[k]:5d} {100 * hist[k] / len(meas):5.1f}%")
    print("   seated:", sum(1 for r in meas if r["seated"]))
    by = collections.defaultdict(list)
    for r in meas:
        by[klass(r["path"])].append(abs(r["dmax"]))
    print("   BY CLASS (n, >3 m, max):")
    for k, a in sorted(by.items(), key=lambda kv: -sum(1 for x in kv[1] if x > 3)):
        print(f"     {k:36s} n={len(a):5d} >3m={sum(1 for x in a if x > 3):4d} "
              f"max={max(a):7.2f}")
    meas.sort(key=lambda r: -abs(r["dmax"]))
    print(f"   WORST {top}:")
    for i, r in enumerate(meas[:top], 1):
        print(f"   {i:2d} {r['lat']:10.6f} {r['lon']:11.6f} "
              f"{os.path.basename(r['path'])[-44:]:44} {r['dmax']:8.2f} "
              f"span={r['span']:5.0f} {klass(r['path'])}")


def _nearest_station(st: list, lat: float, lon: float) -> float:
    """The delta of the drape station nearest ``(lat, lon)`` in plan."""
    mlon = MLAT * math.cos(math.radians(lat))
    return min(st, key=lambda r: ((r[0] - lat) * MLAT) ** 2
               + ((r[1] - lon) * mlon) ** 2)[2]


def measure(pack_root: str, dump: str, sampler, deltas: dict, member_delta: dict,
            stations: dict | None = None, thickness: float = 0.5) -> list[dict]:
    """One row per OBJ placement: its worst foot residual, or its kind.

    ``sampler`` is anything with ``elevation_at_or_none(lat, lon)`` — the
    mesh under both the anchor and each foot (``MeshElevationSampler``
    in the CLI below; a stub in the twins).
    """
    defs, plc = read_placements(dump)
    if not plc:
        return []
    resources: dict[int, dict | str] = {}
    for i, p in enumerate(defs):
        if not p.lower().endswith(".obj"):
            resources[i] = "notobj"
        elif p.replace("\\", "/").lower().startswith("lib/"):
            resources[i] = "stock"
        else:
            resources[i] = read_feet(pack_root, p, thickness)
    rows: list[dict] = []
    for idx, lon, lat, hdg in plc:
        r = resources.get(idx)
        if isinstance(r, str):
            rows.append(dict(path=defs[idx], kind=r, lat=lat, lon=lon))
            continue
        z_anchor = sampler.elevation_at_or_none(lat, lon)
        if z_anchor is None:
            continue
        # OBJ8 is x east, y up, z SOUTH, rotated by the heading (clockwise
        # from north) about y — the frame ``airport/obj8`` documents
        h = math.radians(hdg)
        s, c = math.sin(h), math.cos(h)
        mlon = MLAT * math.cos(math.radians(lat))
        by_comp = deltas.get(r["path"], {})
        st_of = (stations or {}).get(r["path"], {})
        md = member_delta.get(r["path"])
        ds = []
        for (ci, x, y, z, _area) in r["feet"]:
            east = x * c - z * s
            north = -(x * s + z * c)
            z_foot = sampler.elevation_at_or_none(lat + north / MLAT, lon + east / mlon)
            if z_foot is None:
                continue
            la_f = lat + north / MLAT
            lo_f = lon + east / mlon
            st = st_of.get(ci)
            dz = _nearest_station(st, la_f, lo_f) if st \
                else by_comp.get(ci, md if md is not None else 0.0)
            ds.append(z_foot - (z_anchor + y + dz))
        if not ds:
            continue
        rows.append(dict(path=r["path"], kind="measured", lat=lat, lon=lon,
                         dmax=max(ds, key=abs), dmean=float(np.mean(ds)), n=len(ds),
                         span=r["span"], seated=bool(by_comp or md is not None),
                         line=bool(st_of)))
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("result", help="a seat result (o4_v2_rebake_result_<ICAO>.json) or a "
                                   "v2_rebake_replay.py *.seat.json")
    ap.add_argument("--mesh", required=True, help="the built Data+XX+YYY.mesh")
    ap.add_argument("--plan", default="", help="the rebake plan: supplies the pack root and "
                                               "the skip reason behind each class")
    ap.add_argument("--pack", default="", help="the pack root (default: the plan's)")
    ap.add_argument("--dsf-dump", default="", help="the DSFTool text dump (default: the "
                                                   "pack's cached dump, read-only)")
    ap.add_argument("--label", default="", help="the census's name in the output")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--thickness", type=float, default=0.5,
                    help="a ground component's minimum y-extent in metres")
    ap.add_argument("--json", default="", help="write the per-placement rows here")
    args = ap.parse_args(argv)

    plan = {}
    if args.plan:
        with open(args.plan) as fh:
            plan = json.load(fh)
    pack = args.pack or plan.get("pack_root", "")
    if not pack or not os.path.isdir(pack):
        ap.error("no pack root: pass --pack (or a --plan carrying pack_root)")
    dump = args.dsf_dump or find_dsf_dump(pack)
    if not dump or not os.path.isfile(dump):
        ap.error(f"no DSF text dump for {pack}: pass --dsf-dump (it is never generated here)")
    deltas, member_delta, stations = read_result(args.result)
    _defs, plc = read_placements(dump)
    if not plc:
        ap.error(f"{dump} carries no OBJECT placement")
    sampler = MeshElevationSampler(args.mesh, (min(q[1] for q in plc), min(q[2] for q in plc),
                                               max(q[1] for q in plc), max(q[2] for q in plc)))
    rows = measure(pack, dump, sampler, deltas, member_delta, stations, args.thickness)
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(rows, fh)
    census(rows, dict(plan.get("skipped") or []), set(deltas) | set(member_delta),
           args.label or os.path.basename(args.result), args.top, set(stations))
    if stations:
        n_st = sum(len(v) for c in stations.values() for v in c.values())
        print(f"   LINE OBJECTS (10bb): {len(stations)} resource(s) draped on "
              f"{n_st} station(s)")
        for r in sorted(stations)[:40]:
            c = stations[r]
            print(f"     {os.path.basename(r)[-56:]:56} comps {len(c):4d} "
                  f"stations {sum(len(v) for v in c.values()):5d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
