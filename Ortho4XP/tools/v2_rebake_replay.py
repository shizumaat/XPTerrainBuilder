#!/usr/bin/env python
"""Offline replay of the auto-patch-v2 RE-SEAT (RULINGS 2026-09-04i 04f-1)
— the post-mesh half without a tile build, and the pack's current bake
state without a build at all.

    venv/bin/python tools/v2_rebake_replay.py seat PLAN.json MESH [--filter TOKEN] [--flat Z0]
    venv/bin/python tools/v2_rebake_replay.py disk PACK_ROOT [--filter TOKEN]
    venv/bin/python tools/v2_rebake_replay.py bodies PLAN.json RESULT.json [--top N]

``seat`` reads a tile build's ``o4_v2_rebake_<ICAO>.json`` plan (or the
pipeline's ``<ICAO>.rebake.json``) and a built ``Data+XX+YYY.mesh``, seats
every unit exactly as ``auto_patch.engine_v2.rebake_after_mesh`` would
(``auto_patch_v2.emit.rebake.seat`` over v1's ``MeshElevationSampler``),
prints the counts, the largest seats and every unit matching ``--filter``
(member seats, witnesses, water, outliers), and writes
``PLAN.seat.json`` beside the plan, and the resources that would be
written BY FAMILY (the pack's second path component) with their deltas.
``--flat Z0`` stamps a flat-site datum (RULINGS 2026-09-08d) over the
plan's bounds onto a plan that carries none (a pre-08d version-4 plan is
read as version 5): the what-if of the 08d rules on an older build's plan
and mesh.  It NEVER writes a pack.

``bodies`` (RULINGS 2026-09-09b (5)) replays the WRITE half —
``engine_v2._decision``'s per-component delta map over the plan's authored
OBJ8s and a seat result — and reports, per written member, the CONNECTED
COMPONENTS the seat left with no delta (a floor or ceiling PLANE stays at
its authored y while its walls move) both BEFORE and AFTER
``airport/rigid.complete_component_deltas``.  Read-only.

``disk`` walks a scenery pack for ``<obj>.anchor_bak`` backups and prints,
per resource matching ``--filter``, the live-minus-authored vertex ``y``
delta on disk and v1's provenance record (decision kind, anchor ground,
seat datum, delta) — the "before" reading of any re-seat.  Read-only.

Twins: ``tests/auto_patch_v2/test_m6a_rebake.py`` (the seat law),
``tests/test_engine_v2_rebake.py`` (the hook the ``seat`` half mirrors).
"""
from __future__ import annotations

import argparse
import collections
import dataclasses
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))


def cmd_seat(args: argparse.Namespace) -> int:
    from auto_patch.mesh_sampler import MeshElevationSampler, OutsideMeshError
    from auto_patch_v2.emit import rebake as R
    from auto_patch_v2.law import Law
    with open(args.plan) as fh:
        d = json.load(fh)
    if d.get("version") in (4, 5):
        was = d["version"]
        d["version"] = R.PLAN_VERSION
        # 4: a pre-08d plan carries no flat-site datum (--flat supplies one);
        # 5: a pre-09s plan carries no part FEET, and every part falls back to
        # one foot at its centroid with base_y — the pre-09s reading exactly
        print(f"  plan version {was} read as {R.PLAN_VERSION}"
              + (" (no flat-site datum recorded)" if was == 4 else
                 " (no part feet recorded: the centroid fallback, RULINGS 09s (2))"))
    plan = R.RebakePlan.from_dict(d)
    if args.flat is not None and plan.flat is None:
        lo0, la0, lo1, la1 = plan.bounds()
        sq = ((la0, lo0), (la0, lo1), (la1, lo1), (la1, lo0))
        plan = dataclasses.replace(plan, flat=R.FlatDatum("flat_candidate", float(args.flat),
                                                          "replay", ((sq, ()),)))
        print(f"  --flat {args.flat}: datum stamped over the plan's bounds")
    law = Law.for_airport(plan.icao)
    print(f"{plan.icao} plan: {dict(plan.counts)} skipped {len(plan.skipped)}")
    print("  skip reasons:", collections.Counter(
        r.split(" (")[0].split(":")[0] for _, r in plan.skipped).most_common(6))
    sampler = MeshElevationSampler(args.mesh, plan.bounds())

    def sample(lat: float, lon: float):
        try:
            m = sampler.sample_at(lat, lon)
        except OutsideMeshError:
            return None
        return (float(m.elevation_metres), bool(m.is_water))

    res = R.seat(plan, sample, law)
    print("seat:", res.counts())
    # THE CLUSTERS (06g): the largest lifts, the widest spans, the residuals
    baked = sorted((k for k in res.clusters if k.bakes and k.lift_m is not None),
                   key=lambda k: -abs(k.lift_m))
    print("largest cluster seats:")
    for k in baked[:args.top]:
        print(f"  cluster {k.id} (structure {k.structure}) parts={k.n_parts} ground={k.n_ground} "
              f"measured={k.n_measured} ground_m={k.ground_m:.2f} lift={k.lift_m:+.3f} "
              f"span={k.span_m:.2f} residual_parts={k.residual_parts} pad={k.needs_pad} "
              f"resources=" + ", ".join(os.path.basename(r)[:28] for r in k.resources[:3]))
    spans = [k.span_m for k in res.clusters if k.n_measured]
    if spans:
        print(f"cluster spans: max {max(spans):.2f} m, > pad {sum(1 for x in spans if x > law.tables.structures.rebake.cluster_span_pad_m)}")
    if res.pad_requests:
        worst = max(res.pad_requests, key=lambda p: abs(p.residual_m))
        print(f"pad requests: {len(res.pad_requests)} (seated {sum(1 for p in res.pad_requests if p.seated)}), "
              f"worst residual {worst.residual_m:+.2f} m on {os.path.basename(worst.resource)} "
              f"({worst.part_count} part(s))")
    for u in [u for u in res.units if u.datum != R.DATUM_CLUSTER][:args.top]:
        print(f"  {u.unit_id} {u.datum} n={len(u.resources)} delta={u.delta_m} "
              + (f"  {u.findings[0]}" if u.findings else ""))
    if args.filter:
        for u in res.units:
            if any(args.filter in r for r in u.resources):
                print(f"{u.unit_id} n={len(u.resources)} datum={u.datum} anchor_ground={u.anchor_ground_m} "
                      f"delta={u.delta_m} held={u.held} skip={u.skip_reason} findings={u.findings}")
                for m in u.members:
                    print(f"     {os.path.basename(m.resource):48s} {m.datum:8s} delta={m.delta_m if m.delta_m is None else round(m.delta_m, 3)} "
                          f"w={m.witnesses} water={m.water} off={m.off_mesh} out={m.outliers} {m.note}")
    # THE MEMBER RESIDUALS (06g report metric): per member, the worst
    # post-seat ground-part residual — rendered ground (the cluster's
    # median, or the authored base where the cluster stays) + base_y −
    # the mesh under the part; "within 1 m of its own ground" = worst ≤ 1
    within = total = 0
    worst_all = 0.0
    for u, pu in zip(res.units, plan.units):
        if u.anchor_ground_m is None:
            continue
        base = u.anchor_ground_m + pu.agl_m
        for ms, m in zip(u.members, pu.members):
            by_comp = {c: (k, d) for c, k, d in ms.part_deltas}
            worst = None
            for p in m.parts:
                if p.base_y > law.tables.structures.rebake.elevated_base_m:
                    continue
                smp = sample(p.lat, p.lon)
                if smp is None or smp[1]:
                    continue
                k, d = by_comp.get(p.comp, (None, None))
                delta = d if d is not None else (ms.delta_m if ms.delta_m is not None else 0.0)
                r = abs(base + delta + p.base_y - smp[0])
                worst = r if worst is None else max(worst, r)
            if worst is None:
                continue
            total += 1
            within += worst <= 1.0
            worst_all = max(worst_all, worst)
    print(f"members within 1 m of their own ground: {within}/{total} (worst {worst_all:.2f} m)")
    ds = [d for u in res.units if u.bakes for m in u.members
          for d in ([m.delta_m] if m.delta_m is not None else [x for _c, _k, x in m.part_deltas if x is not None])]
    if ds:
        print(f"baked deltas: median {statistics.median(ds):+.3f} min {min(ds):+.3f} max {max(ds):+.3f} over {len(ds)} part delta(s)")
    # THE WRITES BY FAMILY (08d): one line per family, the file count and the delta range
    fam: dict[str, list[tuple[str, float, float]]] = {}
    for u in res.units:
        if not u.bakes:
            continue
        for m in u.members:
            if not m.bakes:
                continue
            vals = [m.delta_m] if m.delta_m is not None else [x for _c, _k, x in m.part_deltas if x is not None]
            parts = m.resource.split("/")
            fam.setdefault(parts[1] if len(parts) > 2 else parts[0], []).append(
                (m.resource, min(vals), max(vals)))
    files = {r for rows in fam.values() for r, _lo, _hi in rows}
    print(f"resources written: {len(files)} file(s) in {len(fam)} famil{'y' if len(fam) == 1 else 'ies'}")
    for name, rows in sorted(fam.items(), key=lambda kv: -len(kv[1])):
        lo = min(r[1] for r in rows); hi = max(r[2] for r in rows)
        n_files = len({r[0] for r in rows})
        print(f"  {name:28s} {n_files:3d} file(s)  delta {lo:+.3f} … {hi:+.3f}")
    out = args.out or os.path.splitext(args.plan)[0] + ".seat.json"
    with open(out, "w") as fh:
        json.dump(res.to_dict(), fh, indent=1, default=str)
    print("->", out)
    return 0


def cmd_disk(args: argparse.Namespace) -> int:
    from auto_patch_v2.airport import obj8
    root = args.pack_root
    prov: dict = {}
    pp = os.path.join(root, ".o4_reanchor_provenance.json")
    if os.path.isfile(pp):
        with open(pp) as fh:
            prov = json.load(fh).get("objects", {})
    n_bak = baked = 0
    rows = []
    for d, _, fs in os.walk(root):
        for f in fs:
            if not f.endswith(".anchor_bak"):
                continue
            n_bak += 1
            bak = os.path.join(d, f)
            live = bak[:-len(".anchor_bak")]
            rel = os.path.relpath(live, root)
            if not os.path.isfile(live):
                continue
            try:
                ga, gl = obj8.parse_obj8(bak), obj8.parse_obj8(live)
            except (OSError, ValueError):
                continue
            if ga.vertices.shape != gl.vertices.shape or ga.vertices.shape[0] == 0:
                continue
            dy = gl.vertices[:, 1] - ga.vertices[:, 1]
            if abs(dy).max() > 1e-6:
                baked += 1
            if args.filter and args.filter not in rel:
                continue
            e = prov.get(rel, {})
            rows.append((rel, float(dy.min()), float(dy.max()), e.get("decision_kind"),
                         e.get("anchor_ground_m"), e.get("seat_datum_m"), e.get("delta_m")))
    print(f"{root}: anchor_bak files {n_bak}, live != backup {baked}, provenance entries {len(prov)}")
    for rel, lo, hi, kind, ag, seat, delta in sorted(rows):
        print(f"  {rel:62s} dy[{lo:+8.4f},{hi:+8.4f}] {kind} anchor_ground={ag} seat={seat} delta={delta}")
    return 0


def cmd_bodies(args: argparse.Namespace) -> int:
    """The rigid-body completeness read (RULINGS 2026-09-09b (5) /
    2026-09-09z (4): the carrier is the component the plane TOUCHES)."""
    from auto_patch_v2.airport import obj8 as O
    from auto_patch_v2.airport import rigid as RG
    with open(args.plan) as fh:
        plan = json.load(fh)
    with open(args.result) as fh:
        res = json.load(fh)
    res = res.get("seat", res)
    auth = {m["resource"]: m["authored_path"]
            for u in plan["units"] for m in u["members"]}
    anch = {m["resource"]: u.get("anchor")
            for u in plan["units"] for m in u["members"]}
    rows, n_before, n_after, n_flat = [], 0, 0, 0
    for u in res["units"]:
        if u.get("held"):
            continue
        for m in u["members"]:
            r = m["resource"]
            if m.get("facility") or r not in auth:
                continue
            pd = m.get("part_deltas") or []
            dm = m.get("delta_m")
            try:
                geom = O.parse_obj8(auth[r])
            except (OSError, ValueError):
                continue
            comps = O.solid_components(geom)
            if not comps:
                continue
            if dm is not None and not pd:
                by = {i: float(dm) for i in range(len(comps))}
            else:
                by = {c: float(d) for c, _k, d in pd
                      if d is not None and 0 <= c < len(comps)}
            if not by:
                continue                       # engine_v2 skips: nothing written
            held = {c for c, _k, d in pd if d is None} - set(by)
            free = [i for i in range(len(comps)) if i not in by and i not in held]
            done = RG.complete_component_deltas(geom, comps, by, held, args.contact)
            n_before += len(free)
            n_after += sum(1 for i in free if i not in done)
            n_flat += sum(1 for i in free
                          if comps[i].max_y - comps[i].min_y < args.thickness)
            if free:
                vals = list(by.values())
                rows.append((max(abs(x) for x in vals), r, anch.get(r), len(comps),
                             len(by), len(free),
                             sum(1 for i in free
                                 if comps[i].max_y - comps[i].min_y < args.thickness),
                             min(vals), max(vals)))
    rows.sort(reverse=True)
    print(f"{res.get('icao', '?')}: {n_before} component(s) stranded by the seat "
          f"({n_flat} of them flat under {args.thickness} m) -> {n_after} after the "
          f"rigid-body completion; {len(rows)} member(s) affected")
    for sep, r, a, nc, nm, nf, nff, lo, hi in rows[:args.top]:
        ll = f"{a[0]:.5f},{a[1]:.5f}" if a else "?"
        print(f"  {sep:8.3f} m | {r[-52:]:52s} | {ll} | comps {nc:5d} moved {nm:5d} "
              f"stranded {nf:5d} (flat {nff:5d}) | delta[{lo:+.3f},{hi:+.3f}]")
    return 0


def _plate_vs_wall(args, r, v, idxs, final, parts, rows, sites, buckets, n_pairs, n_over):
    """THE PLATE-vs-WALL CENSUS (RULINGS 2026-09-10u): a PLATE (a component
    of authored y-extent under ``--plate-thickness`` with at least three
    vertices) whose APPLIED delta stands more than ``--floor`` metres ABOVE
    a WALL (y-extent at or over it) that lies within ``--near`` metres of it
    IN PLAN — the floating roof the owner sees.  Bucketed by the AUTHORED
    vertical gap (plate bottom minus wall top): ``contact`` (within
    ``--contact-eps``, ``[rebake] contact_epsilon_m`` — the class the
    cluster pass owns), ``gap`` (within ``--gap``, ``[rebake]
    plate_gap_max_m`` — the eave / parapet class the carrier rule owns) and
    ``far`` (beyond: nearest, reported not fixed).  Proximity is PLAN, not
    3-D, so a roof metres clear of its wall is still its wall's pair."""
    import numpy as np
    from scipy.spatial import cKDTree
    ext = [(float(v[i][:, 1].min()), float(v[i][:, 1].max())) for i in idxs]
    plates = [k for k, (a, b) in enumerate(ext)
              if (b - a) < args.plate_thickness and len(idxs[k]) >= 3]
    walls = [k for k, (a, b) in enumerate(ext) if (b - a) >= args.plate_thickness]
    if not plates or not walls:
        return n_pairs, n_over
    wpts = np.concatenate([v[idxs[k]][:, [0, 2]] for k in walls])
    wown = np.concatenate([np.full(len(idxs[k]), k, dtype=np.int64) for k in walls])
    wt = cKDTree(wpts)
    for pk in plates:
        dp = final.get(pk)
        if dp is None:
            continue
        near = {int(wown[j]) for lst in wt.query_ball_point(v[idxs[pk]][:, [0, 2]], args.near)
                for j in lst}
        for wk in sorted(near):
            dw = final.get(wk)
            if dw is None or dp - dw <= args.floor:
                continue
            gap = ext[pk][0] - ext[wk][1]
            buckets["contact" if gap <= args.contact_eps
                    else "gap" if gap <= args.gap else "far"] += 1
            n_pairs += 1
            rows.append((dp - dw, r, pk, wk, dp, dw))
            if dp - dw > args.bar:
                n_over += 1
                lat = lon = 0.0
                for p in parts.get(r, ()):
                    if p[1] in (pk, wk):
                        lat, lon = float(p[2]), float(p[3])
                        break
                prev = sites.get(r)
                if prev is None or dp - dw > prev[2]:
                    sites[r] = (lat, lon, dp - dw, pk, wk)
    return n_pairs, n_over


def cmd_pairs(args: argparse.Namespace) -> int:
    """THE TEAR CENSUS (RULINGS 2026-09-10i): pairs of components of ONE
    OBJ8 whose geometry comes within ``--near`` metres yet whose APPLIED
    deltas differ — the instrument the 10i bars are stated in ("12,057
    pairs within 2 m with different deltas, 85 sites over 2 m").  Reads a
    plan + a seat result, completes the write half exactly as
    ``engine_v2._decision`` does, and never writes a pack."""
    import numpy as np
    from scipy.spatial import cKDTree
    from auto_patch_v2.airport import obj8 as O
    from auto_patch_v2.airport import rigid as RG
    with open(args.plan) as fh:
        plan = json.load(fh)
    with open(args.result) as fh:
        res = json.load(fh)
    res = res.get("seat", res)
    auth = {m["resource"]: m["authored_path"] for u in plan["units"] for m in u["members"]}
    # the plan's parts carry (pid, comp, lat, lon, ...): the affine map from
    # the file's own plan frame to lat/lon, so a pair can be put on a map
    parts = {m["resource"]: m["parts"] for u in plan["units"] for m in u["members"]}
    n_pairs = n_over = 0
    sites: dict[str, tuple[float, float, float, int, int]] = {}
    rows = []
    buckets: collections.Counter = collections.Counter()
    for u in res["units"]:
        if u.get("held"):
            continue
        for m in u["members"]:
            r = m["resource"]
            if m.get("facility") or r not in auth:
                continue
            pd = m.get("part_deltas") or []
            dm = m.get("delta_m")
            try:
                geom = O.parse_obj8(auth[r])
            except (OSError, ValueError):
                continue
            comps = O.solid_components(geom)
            if not comps:
                continue
            if dm is not None and not pd:
                by = {i: float(dm) for i in range(len(comps))}
            else:
                by = {c: float(d) for c, _k, d in pd if d is not None and 0 <= c < len(comps)}
            if not by:
                continue
            held = {c for c, _k, d in pd if d is None} - set(by)
            final = RG.complete_component_deltas(geom, comps, by, held, args.contact,
                                                 getattr(args, "plate_gap", 0.0))
            v = geom.vertices
            idxs = [np.unique(c.tris.reshape(-1)) for c in comps]
            if args.klass == "plate-vs-wall":
                n_pairs, n_over = _plate_vs_wall(args, r, v, idxs, final, parts,
                                                 rows, sites, buckets, n_pairs, n_over)
                continue
            pts = np.concatenate([v[i] for i in idxs])
            owner = np.concatenate([np.full(len(i), k, dtype=np.int64) for k, i in enumerate(idxs)])
            t = cKDTree(pts)
            pr = t.sparse_distance_matrix(t, args.near, output_type="ndarray")
            if not pr.size:
                continue
            a = owner[pr["i"].astype(np.int64)]
            b = owner[pr["j"].astype(np.int64)]
            sel = a < b
            for ca, cb in np.unique(np.stack([a[sel], b[sel]], axis=1), axis=0).tolist():
                da, db = final.get(int(ca)), final.get(int(cb))
                if da is None or db is None or abs(da - db) <= args.floor:
                    continue
                n_pairs += 1
                if abs(da - db) > args.bar:
                    n_over += 1
                    lat = lon = None
                    for p in parts.get(r, ()):
                        if p[1] == int(ca):
                            lat, lon = float(p[2]), float(p[3])
                            break
                    prev = sites.get(r)
                    if prev is None or abs(da - db) > prev[2]:
                        sites[r] = (lat if lat is not None else 0.0,
                                    lon if lon is not None else 0.0,
                                    abs(da - db), int(ca), int(cb))
                    rows.append((abs(da - db), r, int(ca), int(cb), da, db))
    rows.sort(reverse=True)
    if args.klass == "plate-vs-wall":
        print(f"{res.get('icao', '?')}: PLATE-vs-WALL (RULINGS 2026-09-10u) — a plate "
              f"(y-extent < {args.plate_thickness} m) whose applied delta stands more than "
              f"{args.floor} m ABOVE a wall within {args.near} m in PLAN: {n_pairs} pair(s), "
              f"{len({(x[1], x[2]) for x in rows})} plate(s), {len(sites)} resource(s)")
        print(f"  by AUTHORED vertical gap (plate bottom - wall top): "
              f"contact (<= {args.contact_eps} m) {buckets['contact']}; "
              f"gap (<= {args.gap} m) {buckets['gap']}; far {buckets['far']}")
        for sep, r, ca, cb, da, db in rows[:args.top]:
            print(f"  {sep:8.3f} m | {r[-52:]:52s} | plate c{ca} {da:+.3f} vs wall c{cb} {db:+.3f}")
        return 0
    print(f"{res.get('icao', '?')}: pairs of ONE OBJ8 within {args.near} m with different "
          f"deltas (floor {args.floor} m): {n_pairs}; over {args.bar} m: {n_over} "
          f"pair(s) in {len(sites)} site(s) (resources)")
    for sep, r, ca, cb, da, db in rows[:args.top]:
        print(f"  {sep:8.3f} m | {r[-52:]:52s} | c{ca} {da:+.3f} vs c{cb} {db:+.3f}")
    if args.kml:
        with open(args.kml, "w") as fh:
            fh.write('<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.open'
                     'gis.net/kml/2.2"><Document>\n<name>%s tear sites (RULINGS 2026-09-10i)'
                     '</name>\n' % res.get("icao", "?"))
            for r, (lat, lon, sep, ca, cb) in sorted(sites.items(), key=lambda kv: -kv[1][2]):
                fh.write(f"<Placemark><name>{r.rsplit('/', 1)[-1]} — {sep:.3f} m</name>"
                         f"<description>c{ca} vs c{cb}, worst pair of this placement"
                         f"</description><Point><coordinates>{lon:.6f},{lat:.6f},0"
                         f"</coordinates></Point></Placemark>\n")
            fh.write("</Document></kml>\n")
        print("->", args.kml)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("seat", help="seat a plan against a built mesh (no write)")
    s.add_argument("plan")
    s.add_argument("mesh")
    s.add_argument("--filter", default="", help="print every unit whose resources contain this")
    s.add_argument("--top", type=int, default=12)
    s.add_argument("--out", default="", help="where to write the seat result (default: beside the plan — "
                   "pass a lane-local path when the plan lives in the shared data repo)")
    s.add_argument("--flat", type=float, default=None,
                   help="stamp a flat-site datum Z0 over the plan's bounds when the plan has none (08d what-if)")
    s.set_defaults(fn=cmd_seat)
    b = sub.add_parser("bodies", help="the rigid-body completeness of the write half (09b (5))")
    b.add_argument("plan")
    b.add_argument("result", help="the tile build's o4_v2_rebake_result_<ICAO>.json")
    b.add_argument("--top", type=int, default=10)
    b.add_argument("--contact", type=float, default=0.5,
                   help="the contact test's tolerance in metres (RULINGS 2026-09-09z (4): "
                        "emit.identity.min_distinct_spacing_m; 0 = the pre-09z pure-nearest rule)")
    b.add_argument("--thickness", type=float, default=0.3,
                   help="[structures.basin] min_solid_thickness_m — the seat's witness gate")
    b.set_defaults(fn=cmd_bodies)
    p = sub.add_parser("pairs", help="the TEAR census (10i): pairs of one OBJ8 within N m "
                                     "whose applied deltas differ")
    p.add_argument("plan")
    p.add_argument("result", help="the tile build's o4_v2_rebake_result_<ICAO>.json, or a "
                                  "`seat` replay's *.seat.json")
    p.add_argument("--near", type=float, default=2.0, help="two components this close are ONE site")
    p.add_argument("--bar", type=float, default=2.0, help="a pair over this is a tear SITE")
    p.add_argument("--floor", type=float, default=0.05, help="materiality: deltas differing by "
                                                             "less than this are the same delta")
    p.add_argument("--contact", type=float, default=0.5)
    p.add_argument("--top", type=int, default=15)
    p.add_argument("--kml", default="", help="write the sites to this KML")
    p.add_argument("--class", dest="klass", default="all",
                   choices=("all", "plate-vs-wall"),
                   help="plate-vs-wall (RULINGS 2026-09-10u): only FLOATING-ROOF pairs — a "
                        "flat plate whose delta stands above a wall within --near IN PLAN, "
                        "bucketed by the authored vertical gap")
    p.add_argument("--plate-thickness", type=float, default=0.5,
                   help="plate-vs-wall: a component of y-extent under this is a PLATE")
    p.add_argument("--gap", type=float, default=4.0,
                   help="plate-vs-wall: [rebake] plate_gap_max_m — the eave / parapet class")
    p.add_argument("--contact-eps", type=float, default=0.25,
                   help="plate-vs-wall: [rebake] contact_epsilon_m — the touching class")
    p.add_argument("--plate-gap", type=float, default=0.0,
                   help="the carrier rule's [rebake] plate_gap_max_m for the write half "
                        "(0 = the pre-10u pure-nearest fallback)")
    p.set_defaults(fn=cmd_pairs)
    d = sub.add_parser("disk", help="a pack's current bake state (read-only)")
    d.add_argument("pack_root")
    d.add_argument("--filter", default="")
    d.set_defaults(fn=cmd_disk)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
