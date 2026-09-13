"""THE DRAPE RESIDUAL AT EVERY PLACEMENT'S FEET (RULINGS 2026-09-09ac (3);
the PLACEMENT reading 2026-09-11e (3), spec §7/§9).

THE SEAT-RESULT MODE IS DELETED (owner RULINGS 2026-09-12s, spec §8):
this tool used to read an ``o4_v2_rebake_result_<ICAO>.json`` and price
v1's vertex rewrite at each foot.  The seat is a refuted mechanism and
its result files no longer exist, so the only mode is the live one — the
PLACEMENT plan.  The name is kept: the INDEX row, ``obj8_split_report``
and the twins all address it by it.

For every placement of a ``o4_v2_placement_<ICAO>.json`` — every split
body at ITS anchor, reading the file the split writer wrote; every
converted placement at its authored anchor — the residual is what the
terrain does between the anchor and each of the object's GROUND
components' lowest vertices:

    |dz| = surface(foot) - (surface(anchor) + y_foot)

The elevation comes from the built mesh (``--mesh``) or, for a dry run
with no tile built, from the emitted DESIGN SURFACE (``--graded``),
which is the terrain the drape will read.  Feet are read from the
AUTHORED pack (``.anchor_bak`` when one exists — restore-before-read).
Nothing is written to the pack.

    venv/bin/python tools/seat_feet_census.py --placement-plan PLAN.json \\
        {--mesh MESH | --graded ICAO.graded.json} [--pack ROOT] [--top 30]

Output: the |Δ| histogram (< 0.3 / 0.3-1 / 1-3 / > 3 m), the same by
CLASS, the worst N placements with lat/lon, and §13's elevated-body /
footless-carrier bars.  Promoted from the `v2lemdseats` lane's
``measure6.py`` on its third use.
"""
from __future__ import annotations

import argparse
import collections
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


def census(rows: list[dict], skipped: dict[str, str],
           label: str, top: int) -> None:
    """The histogram, the by-class table and the worst ``top``."""
    def klass(path: str) -> str:
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


def plan_bounds(plc: list[tuple[int, float, float, float]]
                ) -> tuple[float, float, float, float]:
    """THE MESH SAMPLER'S BOX, IN THE SAMPLER'S OWN ORDER (spec §16e (4)).

    ``plc`` rows are ``(def, LON, LAT, heading)`` —
    :func:`placement_plan_rows`' order — and
    :class:`auto_patch.mesh_sampler.MeshElevationSampler` takes
    ``(min_lon, min_lat, max_lon, max_lat)``.  This call was spelled
    inline as ``(min lat, min lon, max lat, max lon)``, which at OTHH
    asked for a box at lon 25.2, lat 51.6: the sampler retained NO
    triangle and ``--placement-plan --mesh`` measured nothing at all.
    The one place the two orders meet, so a twin can hold it."""
    return (min(q[1] for q in plc), min(q[2] for q in plc),
            max(q[1] for q in plc), max(q[2] for q in plc))


def measure_rows(pack_root: str, defs: list[str],
                 plc: list[tuple[int, float, float, float]], sampler,
                 thickness: float = 0.5) -> list[dict]:
    """The measurement itself, over the plan's placement rows."""
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
        ds = []
        for (ci, x, y, z, _area) in r["feet"]:
            east = x * c - z * s
            north = -(x * s + z * c)
            z_foot = sampler.elevation_at_or_none(lat + north / MLAT, lon + east / mlon)
            if z_foot is None:
                continue
            ds.append(z_foot - (z_anchor + y))
        if not ds:
            continue
        rows.append(dict(path=r["path"], kind="measured", lat=lat, lon=lon,
                         dmax=max(ds, key=abs), dmean=float(np.mean(ds)), n=len(ds),
                         span=r["span"], seated=False, line=False))
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
        sampler = MeshElevationSampler(args.mesh, plan_bounds(plc))
    rows = measure_rows(pack, defs, plc, sampler, args.thickness)
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(rows, fh)
    c = plan.get("counts", {})
    label = args.label or f"{plan.get('icao', '?')} placement plan"
    census(rows, {}, label, args.top)
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
    # §16e: A DATUM BODY IS NOT THIS CLASS.  Its ``y_zero`` is +5 … +10 m
    # BY CONSTRUCTION — a tunnel wall's crest plate, a bridge's deck top,
    # an authored height the law puts AT the ground — so counting it here
    # would report the law as the defect §13 bars at zero.  It is printed
    # as its own class instead.
    own = [(b.get("authored_offset", (0, 0, 0))[1], b.get("new_resource", "?"))
           for s in plan.get("splits", ())
           for b in s.get("bodies", ())
           if len(b.get("authored_offset", ())) > 1
           and float(b["authored_offset"][1]) > base
           and not b.get("datum")]
    datums = [(b.get("y_zero", 0.0), b.get("new_resource", "?"))
              for s in plan.get("splits", ())
              for b in s.get("bodies", ()) if b.get("datum")]
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
    if datums:
        print(f"   §16e bodies on a DATUM (a crest plate / a deck top — an "
              f"authored height AT the ground, counted apart from §13's bar): "
              f"{len(datums)}")
        for y, res in sorted(datums, reverse=True)[:5]:
            print(f"      y_zero {y:+.2f} m  {res}")
    print(f"   §13/§16 footless placements with no carrier "
          f"(their own ground): {footless}; "
          f"elevated bodies carried at their authored offset: {carried}")
    # §14 (4): the four bars, from the engine's own implementation — the
    # same call ``obj8_split_report`` makes over the same plan shape.
    from auto_patch_v2.airport import basin_ring as _BR
    from auto_patch_v2.airport import placement_carrier as PC
    from auto_patch_v2.law import Law
    tol = float(Law.load().tables.structures.placement.split_tol_m)
    # §14a: the bar reads the RINGS with their own heights, and the
    # SPLIT counts — which the written plan carries under ``provenance``
    # (``counts`` there is the WRITE half's tally).  Without a design
    # surface to read the rings from, the §14 reading stands.
    c = PC.census_v14(plan.get("splits", ()), plan.get("kept", ()),
                      elevated_base_m=base, split_tol_m=tol,
                      rims=getattr(sampler, "rims", ()) or (),
                      arc_cap=0, counts=_BR.plan_counts(plan))
    # §17 THE COCKPIT BLOCK FIRST (owner RULINGS 2026-09-12x/12y; §31 (6)).
    # The same call ``obj8_split_report`` makes over the same plan shape,
    # from the same census dicts — the §15 / §16b readings are taken here
    # and printed in their own place below, unchanged.
    _pl = Law.load().tables.structures.placement
    _v15 = PC.census_v15(plan.get("splits", ()), plan.get("kept", ()),
                         ground_tol_m=_pl.split_tol_m)
    _v16b = (None if sampler is None else PC.census_v16b(
        plan.get("splits", ()),
        lambda la, lo: sampler.elevation_at_or_none(la, lo), split_tol_m=tol))
    for line in PC.cockpit_block_lines(PC.cockpit_block(
            splits=plan.get("splits", ()), v15=_v15, v16b=_v16b)):
        print(line)
    for line in PC.census_v14_lines(c, elevated_base_m=base, split_tol_m=tol):
        print(line)
    # §16e (3): THE BRIDGE FAMILY (RULINGS 2026-09-13v) — the derived
    # relation the plan publishes per body (``bridge_of``), its bars and
    # its agreement with the pack's own ``Bridge_NN`` spelling.  The same
    # call ``obj8_split_report`` makes over the same plan shape.
    for line in PC.census_bridges_lines(PC.census_bridges(
            plan.get("splits", ()),
            None if sampler is None
            else (lambda la, lo: sampler.elevation_at_or_none(la, lo)))):
        print(line)
    # §15 (3): the stands-over float — the class neither the foot census
    # nor §14's bars can see (a carried body has no feet at all)
    for line in PC.census_v15_lines(_v15):
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
        # §16b (4): the same two bars, read on the WRITTEN GEOMETRY the
        # plan publishes per body — one implementation, both tools.
        for line in PC.census_v16b_lines(_v16b):
            print(line)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--placement-plan", required=True,
                    help="an o4_v2_placement_<ICAO>.json: census the PLACEMENT "
                         "plan's own rows (11e (3))")
    ap.add_argument("--mesh", default="", help="the built Data+XX+YYY.mesh")
    ap.add_argument("--graded", default="", help="an emitted <ICAO>.graded.json — the "
                                                 "DESIGN SURFACE, for a dry run with no "
                                                 "tile built")
    ap.add_argument("--pack", default="", help="the pack root (default: the plan's)")
    ap.add_argument("--label", default="", help="the census's name in the output")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--thickness", type=float, default=0.5,
                    help="a ground component's minimum y-extent in metres")
    ap.add_argument("--json", default="", help="write the per-placement rows here")
    args = ap.parse_args(argv)

    if not args.mesh and not args.graded:
        ap.error("pass --mesh (the built mesh) or --graded (the design surface)")

    return _census_placement_plan(ap, args)


if __name__ == "__main__":
    raise SystemExit(main())
