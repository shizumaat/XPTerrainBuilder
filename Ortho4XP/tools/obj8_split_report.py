#!/usr/bin/env python3
"""THE OBJ8 SPLIT, DRY-RUN (spec ``object-placement-spec.md`` §4 / §6 / §7).

What a pack's object stage would look like after the switch to AGL
placement with split objects and placed anchors — computed from a build's
own two products and NOTHING ELSE: the re-seat plan
(``<ICAO>.rebake.json`` — the pack read once, its welded parts and the
ε-contact graph) and the emitted DESIGN SURFACE
(``<ICAO>.graded.json``), which is the terrain X-Plane will drape onto.

    venv/bin/python tools/obj8_split_report.py PLAN.json --graded SURFACE.json
        [--write-into DIR] [--json OUT.json] [--top N] [--filter SUBSTR]
        [--no-cut]

Per placement it reports the bodies, their §6 CLASSES, each body's anchor
and authored offset, the files that would be written, and the
placements KEPT WHOLE with the reason (§2 ``kept``).  With
``--write-into`` the cut files are written into a scratch directory and
each is parsed back through ``airport/obj8.parse_obj8`` — the proof that
what the writer emits is an OBJ8 the readers accept.  THE PACK IS NEVER
TOUCHED: nothing here opens a file for writing inside the scenery pack,
and the DSF is not read at all (§3 is the other lane's half).

It also prints §7's CENSUS from the plan: per body, the design surface at
its ANCHOR against the surface under every ground-contact FOOT, which is
what the placement law makes of the float —

    float(foot) = surface(foot) - (surface(anchor) + y_foot - y_zero)

— the same |Δ| histogram ``seat_feet_census.py`` prints from a mesh and a
seat RESULT, read instead from the plan and the design surface, so the
bars of §7 (LEMD feet > 0.3 m 284 -> <= 60) are comparable.  A foot or an
anchor standing outside every graded face reads NO surface and is counted
as ``off-surface``, never guessed at: the DEM governs there, and this
tool does not open the DEM.

The design surface is sampled by linear interpolation over the emitted
surface's own vertices (``scipy.spatial.Delaunay`` over the graded
vertices, ``None`` outside their hull) — the surface as a continuous
field, which is what a drape reads.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

import numpy as np                                             # noqa: E402

from auto_patch_v2.airport import anchor_rule as AR            # noqa: E402
from auto_patch_v2.airport import obj8                         # noqa: E402
from auto_patch_v2.airport import placement_plan as PP         # noqa: E402


def surface_from_graded(path: str):
    """``(sampler, pads, rims)`` from an emitted ``<ICAO>.graded.json``."""
    d = json.loads(open(path, encoding="utf-8").read())
    vs = d["vertices"]
    pts = np.asarray([[v[1], v[2]] for v in vs], dtype=float)
    zs = np.asarray([v[3] for v in vs], dtype=float)
    by_id = {v[0]: (v[1], v[2]) for v in vs}
    from scipy.interpolate import LinearNDInterpolator
    interp = LinearNDInterpolator(pts, zs)

    def sampler(lat: float, lon: float):
        z = interp(lat, lon)
        z = float(np.asarray(z).reshape(-1)[0])
        return None if not np.isfinite(z) else z

    pads = tuple(AR.PadRing(f["ref"], tuple(by_id[i] for i in f["ring"] if i in by_id))
                 for f in d["faces"] if f["role"] == "building" and len(f["ring"]) >= 3)
    rims = tuple(AR.RimRing(b["ref"], tuple(by_id[i] for i in b["vertices"] if i in by_id))
                 for b in d["breaklines"] if b["kind"] == "structure_rim"
                 and len(b["vertices"]) >= 3)
    return sampler, pads, rims


def census(ss: PP.SplitSet, sampler, band_m: float) -> dict:
    """§7: the float per ground-contact foot under the placement law.

    A foot counts when it is a ground-contact foot OF THE BODY: within
    ``band_m`` (``[basin] contact_band_m``, the same band the plan itself
    picks a PART's feet with) of the body's own lowest foot.  The plan's
    ground verdict was taken per part against its contact STRUCTURE, and
    a structure is not a body — at LEMD ``Munoza-LEMD79`` body 0 carries
    a part founded at -1.36 and one at +26.9, and counting the upper
    one's feet censused a rooftop 28 m "off its ground".  Re-judging at
    body level is 10i's own rule one level up, with 10i's own band.

    Every body counts — the bodies of a placement that would be SPLIT and
    the single body of one that stays whole alike, because the law is the
    same for both: the placement is AGL, its origin lands on the surface
    at its anchor, and the foot floats by whatever the surface does
    between the two points."""
    bins: collections.Counter = collections.Counter()
    worst: list[tuple[float, str, float, float]] = []
    per_placement: collections.Counter = collections.Counter()
    by_class: dict[str, collections.Counter] = collections.defaultdict(
        collections.Counter)
    for s in ss.all:
        for b in s.bodies:
            za = b.anchor.surface_z
            if not b.feet:
                continue
            floor = min(f[2] for f in b.feet)
            for lat, lon, y in [f for f in b.feet if f[2] - floor <= band_m]:
                if za is None:
                    bins["off-surface"] += 1
                    by_class[b.body_class]["off-surface"] += 1
                    continue
                zf = sampler(lat, lon)
                if zf is None:
                    bins["off-surface"] += 1
                    by_class[b.body_class]["off-surface"] += 1
                    continue
                d = abs(zf - (za + y - b.anchor.y_zero))
                key = ("<0.3" if d < 0.3 else "0.3-1" if d < 1.0
                       else "1-3" if d < 3.0 else ">3")
                bins[key] += 1
                by_class[b.body_class][key] += 1
                if d >= 0.3:
                    per_placement[s.resource] += 1
                worst.append((d, f"{s.resource} b{b.body_id} [{b.body_class}]", lat, lon))
    worst.sort(reverse=True)
    return {"bins": dict(bins), "worst": worst[:20], "feet": sum(bins.values()),
            "placements_over_0_3": len(per_placement),
            "by_class": {k: dict(v) for k, v in by_class.items()}}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", help="<ICAO>.rebake.json (or o4_v2_rebake_<ICAO>.json)")
    ap.add_argument("--graded", required=True, help="<ICAO>.graded.json")
    ap.add_argument("--write-into", default="", help="write the cut files here and "
                                                     "parse each back (scratch only)")
    ap.add_argument("--json", default="", help="write the whole report here")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--filter", default="", help="only placements whose resource "
                                                 "contains this")
    ap.add_argument("--no-cut", action="store_true",
                    help="body counts only — do not cut any OBJ8")
    a = ap.parse_args()

    from auto_patch_v2.law import Law
    band_m = Law.load().tables.structures.basin.contact_band_m
    plan, abut = PP.read_plan(a.plan)
    sampler, pads, rims = surface_from_graded(a.graded)
    print(f"plan {plan.icao}  pack {plan.pack_name}\n"
          f"  units {len(plan.units)}  members {sum(len(u.members) for u in plan.units)}"
          f"  parts {plan.counts.get('parts')}  contacts {len(plan.contacts)}"
          f"  abutments {len(abut)}\n"
          f"  surface: {len(pads)} object pads, {len(rims)} structure rims")
    ss = PP.build_splits(plan, sampler, pads, rims, write=not a.no_cut)
    c = ss.counts
    print(f"\nSPLIT  placements {c['placements']}  split {c['split']} into "
          f"{c['files']} files  kept whole {c['kept']}")
    print("  kept-whole reasons: " + ", ".join(
        f"{k} {v}" for k, v in sorted(collections.Counter(
            k.reason for k in ss.kept).items(), key=lambda kv: -kv[1])))
    print("  body classes: " + ", ".join(f"{k[6:]} {v}" for k, v in sorted(c.items())
                                         if k.startswith("class_")))

    rows = [s for s in ss.splits if a.filter in s.resource]
    rows.sort(key=lambda s: -len(s.bodies))
    print(f"\nthe {min(a.top, len(rows))} placements with the most bodies:")
    for s in rows[:a.top]:
        print(f"  #{s.index} {s.resource}  {len(s.bodies)} bodies -> "
              f"{len(s.files)} files")
        for b in s.bodies[:6]:
            print(f"      b{b.body_id} [{b.body_class}] {b.anchor.lat:.7f},"
                  f"{b.anchor.lon:.7f}  y0 {b.anchor.y_zero:+.2f}  "
                  f"offset {b.anchor.offset[0]:+.1f},{b.anchor.offset[1]:+.1f},"
                  f"{b.anchor.offset[2]:+.1f}  {b.anchor.reason}")
        if len(s.bodies) > 6:
            print(f"      ... {len(s.bodies) - 6} more")

    wrote = parsed = 0
    if a.write_into:
        os.makedirs(a.write_into, exist_ok=True)
        for s in ss.splits:
            for f in s.files:
                p = os.path.join(a.write_into, f.resource.replace("/", "__"))
                with open(p, "w", encoding="latin-1") as fh:
                    fh.write(f.text)
                wrote += 1
                g = obj8.parse_obj8(p)
                if g.solid.shape[0] + g.draped.shape[0] == f.tris:
                    parsed += 1
                else:
                    print(f"  MISMATCH {f.resource}: wrote {f.tris} tris, "
                          f"parse_obj8 reads {g.solid.shape[0] + g.draped.shape[0]}")
        print(f"\nwrote {wrote} files into {a.write_into}; "
              f"{parsed} parse back with the written triangle count")

    cen = census(ss, sampler, band_m)
    print(f"\nCENSUS (§7) over {cen['feet']} ground-contact feet of "
          f"{sum(len(s.bodies) for s in ss.all)} bodies:")
    print("  " + "  ".join(f"{k} {v}" for k, v in sorted(cen["bins"].items())))
    print(f"  placements with any foot > 0.3 m: {cen['placements_over_0_3']}")
    for k, v in sorted(cen["by_class"].items()):
        print(f"    {k:<13} " + "  ".join(f"{kk} {vv}" for kk, vv in sorted(v.items())))
    print("  worst feet:")
    for d, who, lat, lon in cen["worst"][:8]:
        print(f"    {d:7.2f} m  {who}  {lat:.6f},{lon:.6f}")

    if a.json:
        out = ss.to_dict()
        out["wrote"] = wrote
        out["parsed"] = parsed
        out["census"] = {"bins": cen["bins"], "feet": cen["feet"],
                         "placements_over_0_3": cen["placements_over_0_3"]}
        json.dump(out, open(a.json, "w", encoding="utf-8"))
        print(f"report -> {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
