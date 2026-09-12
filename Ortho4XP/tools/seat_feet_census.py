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
    venv/bin/python tools/seat_feet_census.py --placement-plan PLAN.json \\
        {--mesh MESH | --graded ICAO.graded.json} [--pack ROOT] [--top 30]

THE PLACEMENT PLAN (owner RULINGS 2026-09-11e (3), spec §7/§9): with
``--placement-plan`` there is no seat and no delta — the object stage is
X-Plane's own drape, so the rows are the plan's OWN placements (every
split body at ITS anchor, reading the file the split writer wrote; every
converted placement at its authored anchor) and the residual is what the
terrain does between the anchor and each foot:

    |dz| = surface(foot) - (surface(anchor) + y_foot)

— the same instrument, the same histogram, one source further back.  The
elevation comes from the built mesh (``--mesh``) or, for a dry run with
no tile built, from the emitted DESIGN SURFACE (``--graded``), which is
the terrain the drape will read.

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

    The cache names a dump ``<dsf basename>.<sha256(dsf bytes)[:8]>.text``
    under the airport mod cache (``auto_patch.dsf_reader``); this looks
    only for one that already EXISTS — DSFTool is never run here, so a
    census can never regenerate a shared-repo artefact as a side effect.

    The DSF it names is the PRISTINE one (RULINGS 2026-09-11m,
    ``dsf_write.pristine_dsf_path``): a census of a written pack reads
    the frame the plan was made in, not the bodies the write minted.
    """
    from auto_patch.dsf_reader import airport_mod_cache_dir, _default_pack_text_cache_path
    from auto_patch_v2.airport.dsf_write import pristine_dsf_path
    cache = airport_mod_cache_dir(pack_root)
    if not cache:
        return None
    for d in sorted(glob.glob(os.path.join(pack_root, "Earth nav data", "*", "*.dsf"))
                    + glob.glob(os.path.join(pack_root, "Earth nav data", "*.dsf"))):
        cand = _default_pack_text_cache_path(cache, pristine_dsf_path(d))
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
    return measure_rows(pack_root, defs, plc, sampler, deltas, member_delta,
                        stations, thickness)


def placement_plan_rows(plan: dict) -> tuple[list[str], list[tuple[int, float, float, float]]]:
    """``(defs, placements)`` from a ``o4_v2_placement_<ICAO>.json`` —
    the plan's OWN rows in the DSF's own shape, so the census below is
    one code path for a dump and for a plan (11e (3)).

    Every SPLIT body is a row at its own anchor on its own new resource;
    every CONVERSION is a row at its authored anchor.  A KEPT placement
    that is not also a conversion carries no coordinate in the plan (it
    is the authored row, untouched) and is counted, not measured."""
    defs: list[str] = []
    idx: dict[str, int] = {}
    plc: list[tuple[int, float, float, float]] = []

    def _def(res: str) -> int:
        if res not in idx:
            idx[res] = len(defs)
            defs.append(res)
        return idx[res]

    for s in plan.get("splits", ()):
        for b in s.get("bodies", ()):
            a = b["anchor"]
            plc.append((_def(b["new_resource"]), float(a["lon"]), float(a["lat"]),
                        float(a.get("heading", 0.0))))
    for c in plan.get("conversions", ()):
        plc.append((_def(c["resource"]), float(c["lon"]), float(c["lat"]),
                    float(c.get("heading", 0.0))))
    return defs, plc


def measure_rows(pack_root: str, defs: list[str],
                 plc: list[tuple[int, float, float, float]], sampler,
                 deltas: dict, member_delta: dict,
                 stations: dict | None = None, thickness: float = 0.5) -> list[dict]:
    """The measurement itself, over placements from EITHER source."""
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



class _GradedSampler:
    """A ``--graded`` design surface in the sampler's own shape."""

    def __init__(self, path: str):
        tools = os.path.dirname(os.path.abspath(__file__))
        if tools not in sys.path:
            sys.path.insert(0, tools)
        from obj8_split_report import surface_from_graded
        self._f, self.pads, self.rims = surface_from_graded(path)

    def elevation_at_or_none(self, lat: float, lon: float):
        return self._f(lat, lon)


def _census_placement_plan(ap, args) -> int:
    """§7 read from the PLACEMENT plan (11e (3)) — no seat, no delta."""
    with open(args.placement_plan) as fh:
        plan = json.load(fh)
    pack = args.pack or plan.get("pack_root", "")
    if not pack or not os.path.isdir(pack):
        ap.error("no pack root: pass --pack (or a plan carrying pack_root)")
    defs, plc = placement_plan_rows(plan)
    if not plc:
        ap.error(f"{args.placement_plan} carries no placement row")
    if args.graded:
        sampler = _GradedSampler(args.graded)
    else:
        sampler = MeshElevationSampler(args.mesh,
                                       (min(q[2] for q in plc), min(q[1] for q in plc),
                                        max(q[2] for q in plc), max(q[1] for q in plc)))
    rows = measure_rows(pack, defs, plc, sampler, {}, {}, None, args.thickness)
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(rows, fh)
    c = plan.get("counts", {})
    label = args.label or f"{plan.get('icao', '?')} placement plan"
    census(rows, {}, set(), label, args.top)
    n_split_rows = sum(len(s.get("bodies", ())) for s in plan.get("splits", ()))
    print(f"   PLAN: {c.get('splits', 0)} split placement(s) -> {n_split_rows} body "
          f"row(s), {c.get('conversions', 0)} conversion(s), {c.get('kept', 0)} kept "
          f"(a kept placement that is already on-ground carries no coordinate in the "
          f"plan and is counted, not measured)")
    meas = [r for r in rows if r["kind"] == "measured"]
    if meas:
        over = [r for r in meas if abs(r["dmax"]) > 0.3]
        big = [r for r in meas if abs(r["dmax"]) > 3.0]
        print(f"   rows with a foot > 0.3 m: {len(over)}; > 3 m: {len(big)}")
    _print_elevated(plan, sampler)
    return 0


#: §13's threshold when the plan carries no law digest of its own: the
#: shipped ``[rebake] elevated_base_m``.  The plan is DATA — a census
#: never re-derives the law it is judging.
def _elevated_base_m(plan: dict) -> float:
    v = plan.get("provenance", {}).get("counts", {}).get("elevated_base_m")
    if v is not None:
        return float(v)
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "src"))
    from auto_patch_v2.law import Law
    return float(Law.load().tables.structures.rebake.elevated_base_m)


def _print_elevated(plan: dict, sampler=None) -> None:
    """§13 (3): THE TWO CLASSES THE OWNER'S 11r READ TURNS ON.

    ``elevated bodies as own files`` counts split bodies whose file's
    intended zero (``authored_offset[1]``, the ``y`` the writer shifts
    the body by so its own lowest vertex lands on the terrain) stands
    above ``elevated_base_m``: a roof, a road deck or a tower part set on
    the ground.  The bar is ZERO.  ``footless placements kept whole`` is
    the lawful answer for a placement with no ground body at all.

    The feet histogram above already EXCLUDES elevated vertices — a
    component whose own base stands more than a metre above the file's
    (``read_feet``) is not a foot — so this line, not the histogram, is
    what catches the class: the 218 LEMD bodies of 11s censused PERFECT
    because the writer had put each one's lowest vertex on the ground."""
    base = _elevated_base_m(plan)
    own = [(b.get("authored_offset", (0, 0, 0))[1], b.get("new_resource", "?"))
           for s in plan.get("splits", ())
           for b in s.get("bodies", ())
           if len(b.get("authored_offset", ())) > 1
           and float(b["authored_offset"][1]) > base]
    carried = sum(int(b.get("elevated_members", 0))
                  for s in plan.get("splits", ()) for b in s.get("bodies", ()))
    from auto_patch_v2.airport.placement_carrier import FOOTLESS_KEPT
    footless = sum(1 for k in plan.get("kept", ())
                   if str(k.get("reason", "")) in FOOTLESS_KEPT)
    print(f"   §13 elevated bodies as own files: {len(own)} "
          f"(bar 0, [rebake] elevated_base_m {base:g} m)"
          + ("" if not own else "   *** VIOLATED ***"))
    for y, res in sorted(own, reverse=True)[:5]:
        print(f"      +{y:.2f} m  {res}")
    print(f"   §13/§16 footless placements with no carrier "
          f"(their own ground): {footless}; "
          f"elevated bodies carried at their authored offset: {carried}")
    # §14 (4): the four bars, from the engine's own implementation — the
    # same call ``obj8_split_report`` makes over the same plan shape.
    from auto_patch_v2.airport import placement_carrier as PC
    from auto_patch_v2.law import Law
    tol = float(Law.load().tables.structures.placement.split_tol_m)
    c = PC.census_v14(plan.get("splits", ()), plan.get("kept", ()),
                      elevated_base_m=base, split_tol_m=tol)
    for line in PC.census_v14_lines(c, elevated_base_m=base, split_tol_m=tol):
        print(line)
    # §15 (3): the stands-over float — the class neither the foot census
    # nor §14's bars can see (a carried body has no feet at all)
    _pl = Law.load().tables.structures.placement
    for line in PC.census_v15_lines(PC.census_v15(
            plan.get("splits", ()), plan.get("kept", ()),
            fill_min=_pl.carrier_fill_min)):
        print(line)
    # §16 (2): the float on the body's OWN GEOMETRY — the same call
    # ``obj8_split_report`` makes over the same plan shape, needing only
    # a surface to read the ground with.  (§16 (1)'s population census
    # reads the REBAKE plan's ``skipped`` and is printed there, where
    # that plan is open.)
    if sampler is not None:
        for line in PC.census_v16_lines(PC.census_v16(
                plan.get("splits", ()),
                lambda la, lo: sampler.elevation_at_or_none(la, lo))):
            print(line)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("result", nargs="?", default="",
                    help="a seat result (o4_v2_rebake_result_<ICAO>.json) or a "
                         "v2_rebake_replay.py *.seat.json")
    ap.add_argument("--placement-plan", default="",
                    help="an o4_v2_placement_<ICAO>.json: census the PLACEMENT "
                         "plan's own rows, no seat and no delta (11e (3))")
    ap.add_argument("--mesh", default="", help="the built Data+XX+YYY.mesh")
    ap.add_argument("--graded", default="", help="an emitted <ICAO>.graded.json — the "
                                                 "DESIGN SURFACE, for a dry run with no "
                                                 "tile built")
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

    if not args.result and not args.placement_plan:
        ap.error("pass a seat result, or --placement-plan")
    if not args.mesh and not args.graded:
        ap.error("pass --mesh (the built mesh) or --graded (the design surface)")

    if args.placement_plan:
        return _census_placement_plan(ap, args)

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
