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
``--no-groups`` drops the plan's authored-frame ABUTMENTS (10ay, spec
§17) — the pre-10ay seat over the SAME build, so one build serves both
arms of the group A/B.  ``--flat Z0`` stamps a flat-site datum (RULINGS 2026-09-08d) over the
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
    if args.line_objects:
        # RULINGS 2026-09-10bb, spec §16: stamp the LINE-OBJECT verdict onto
        # a plan that predates it, read off the AUTHORED files the plan
        # names — the same what-if as --flat.  The plan's own four feet
        # stand in for the widened DRAPE STATIONS a 10bb build writes, so
        # the drape here is coarser than the engine's; the CLASS and the
        # bodies it breaks are exact.
        from auto_patch_v2.airport import line_object as _LO
        from auto_patch_v2.airport import obj8 as _O8
        cache = _O8.ResourceCache(law.tables.structures.witness.min_thickness_m
                                  if hasattr(law.tables.structures, "witness") else 0.05)
        rb0 = law.tables.structures.rebake
        n_res = n_part = 0
        units = []
        for u in plan.units:
            ms = []
            for m in u.members:
                lo = (m.plate_y is None and m.deck_ring is None and m.deck_kind == ""
                      and _LO.is_line_object(cache, m.authored_path, rb0))
                n_res += int(lo)
                if lo:
                    n_part += len(m.parts)
                    m = dataclasses.replace(m, parts=tuple(
                        dataclasses.replace(p, line=True) for p in m.parts))
                ms.append(m)
            units.append(dataclasses.replace(u, members=tuple(ms)))
        plan = dataclasses.replace(plan, units=tuple(units))
        print(f"  --line-objects: {n_res} resource(s), {n_part} part(s) stamped "
              "LINE (10bb; the plan's own feet stand in for the drape stations)")
    if getattr(args, "elevated_decks", False):
        # owner RULINGS 2026-09-11a, spec §17.5: stamp the ELEVATED-DECK
        # verdict onto a plan that predates it, read off the AUTHORED
        # files the plan names — the same what-if as --line-objects.  The
        # reading is geometry only, so it is the build's exactly.
        from auto_patch_v2.airport import deck_signature as _DS
        from auto_patch_v2.airport import obj8 as _O8
        cache_d = _O8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
        n_deck = 0
        units = []
        for u in plan.units:
            ms = []
            for m in u.members:
                d_ = _DS.elevated_deck(cache_d, m.authored_path, law).deck
                n_deck += int(d_)
                ms.append(dataclasses.replace(m, elevated_deck=d_))
            units.append(dataclasses.replace(u, members=tuple(ms)))
        plan = dataclasses.replace(plan, units=tuple(units))
        print(f"  --elevated-decks: {n_deck} resource(s) stamped ELEVATED DECK (11a)")
    if args.no_groups:
        # owner RULINGS 2026-09-10ay (spec §17): the OFF arm of the
        # abutment group, offline — one build serves both arms, since the
        # group is a post-mesh rule over a field the plan already carries.
        n_ab = len(plan.abutments)
        plan = dataclasses.replace(plan, abutments=())
        print(f"  --no-groups: {n_ab} authored-frame abutment(s) dropped "
              "(the pre-10ay seat)")
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
    # THE LINE OBJECTS (owner RULINGS 2026-09-10bb, spec §16): the fences,
    # kerbs, jet-blast lines and light strings that bound nothing and
    # draped on their own stations, and the ORPHAN bodies rule 4 seated
    # by sampling because everything they touched was one.
    lo_rows = [(m.resource, len({c for c, *_x in m.line_stations}), len(m.line_stations),
                min(d for *_x, d in m.line_stations), max(d for *_x, d in m.line_stations))
               for u in res.units for m in u.members if m.line_stations]
    print(f"line objects: {len(lo_rows)} resource(s) draped, "
          f"{sum(r[2] for r in lo_rows)} station(s); "
          f"{res.line_bodies} line bod(y/ies), {res.line_edges_dropped} contact edge(s) bound "
          f"nothing, {res.orphan_bodies_seated} orphan bod(y/ies) sampled")
    print(f"abutment groups (10ay): {res.abutment_groups} group(s), "
          f"{res.grouped_bodies} junior bod(y/ies) on a senior's ground, "
          f"{res.group_pairs_refused} pair(s) refused")
    for r, nc, ns, lo, hi in sorted(lo_rows, key=lambda x: -x[2])[:25]:
        print(f"  {os.path.basename(r)[-56:]:56} comps {nc:4d} stations {ns:5d} "
              f"delta {lo:+.3f} … {hi:+.3f}")
    out = args.out or os.path.splitext(args.plan)[0] + ".seat.json"
    with open(out, "w") as fh:
        json.dump(res.to_dict(), fh, indent=1, default=str)
    print("->", out)
    return 0



def cmd_order(args) -> int:
    """THE PARTITION-ORDER TWIN (owner RULINGS 2026-09-11j; spec §11a (3)).

    ``rebake_plan.plan()`` used to PARTITION A FILTERED object set; it now
    FILTERS A PARTITION read once at load.  The two orders are not
    identical by construction (``airport/pack_partition`` module doc), so
    this runs both over ONE airport's real pack and reports
    ``parts`` / ``contacts`` / ``abutments`` — equal, or the difference
    named.  It builds NOTHING: load + classify-free object read only, and
    the DSF text dump is read from the mod cache, never regenerated.

    The screen here is the LOAD-DERIVABLE half (the below-grade
    components, the deck families, the structure-seat exemptions).  The
    basin exclusions and the tunnel-wall plates are PLANAR products and
    have no value outside a build; a run with those is the closing
    build's own ``rebake plan`` line.
    """
    import time
    from auto_patch_v2.airport.load import load
    from auto_patch_v2.airport.obj8 import ResourceCache
    from auto_patch_v2.airport.pack_partition import (extend_partition,
                                                      partition_pack)
    from auto_patch_v2.airport.rebake_plan import screen_of
    from auto_patch_v2.law import Law
    from auto_patch_v2.planar.basins import read_objects
    from auto_patch_v2.planar.__main__ import ENGINE_DIR, default_inputs
    os.chdir(ENGINE_DIR)
    icao = args.icao.upper()
    law = Law.for_airport(icao)
    inputs = default_inputs(None, None, None, 60.0, args.dem_frame, True)
    t = time.perf_counter()
    airport = load(icao, inputs, law)
    cache = ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    objects, _rep = read_objects(airport, law, cache)
    t_load = time.perf_counter() - t
    screen, objs = screen_of(objects, cache, law)
    # THE CACHE MUST BE WARM FOR BOTH ARMS (round 3).  Round 2 ran the
    # load arm first and the old arm second on ONE ``ResourceCache``, so
    # the old arm never paid the OBJ8 parse and its 47.0 s / 150.4 s were
    # a WARM reading of a COLD one.  In a real build the parse is paid
    # once whichever order runs — classify's skirt reader warms it for
    # the old order, the load partition warms it for the new — so the
    # only honest partition-vs-partition bar is a warm cache on both.
    t = time.perf_counter()
    for o in objs:
        if o.resolved is not None:
            cache.geometry(o.resolved)
            cache.components(o.resolved)
            cache.genuine(o.resolved)
    t_warm = time.perf_counter() - t
    print(f"[{icao}] pack parse (warm-up, paid once in any order) {t_warm:.2f} s")
    def _load_arm():
        t0 = time.perf_counter()
        ld = partition_pack(airport, objs, cache, law)
        t1 = time.perf_counter()
        mg = extend_partition(ld, airport, cache, law, screen.plate_paths)
        return ld, mg, t1 - t0, time.perf_counter() - t1

    def _old_arm():
        t0 = time.perf_counter()
        o = partition_pack(airport, objs, cache, law, screen)
        return o, time.perf_counter() - t0

    # ORDER MATTERS FOR THE CLOCK, NOT FOR THE COUNTS (round 3): the two
    # arms do the same work on the same warm cache, and the arm that runs
    # FIRST is ~50 % slower at LEMD.  ``--old-first`` runs the control arm
    # first so the 1 % timing bar is read both ways.
    if getattr(args, "old_first", False):
        old, t_old = _old_arm()
        loaded, merged, t_new, t_ext = _load_arm()
    else:
        loaded, merged, t_new, t_ext = _load_arm()
        old, t_old = _old_arm()
    new = merged.filtered(screen, law)
    print(f"[{icao}] load+object read {t_load:.2f} s; partition phase 1 (load, "
          f"screened) {t_new:.2f} s + phase 2 (incremental plates) {t_ext:.2f} s "
          f"= {t_new + t_ext:.2f} s; partition (old order) {t_old:.2f} s; "
          f"{len(objs)} placements")
    print(f"[{icao}] LOAD partition: parts {loaded.counts['parts']}  "
          f"contacts {loaded.counts['contacts']}  abutments {loaded.counts['abutments']}  "
          f"members {loaded.counts['members']}  deferred multi-anchor placements "
          f"{len(loaded.deferred)}; phase 2 re-added "
          f"{merged.counts.get('plate_readded', 0)} resources against "
          f"{merged.counts.get('plate_neighbours', 0)} neighbour parts")
    print(f"[{icao}] partition work: load  pairs_tested "
          f"{loaded.counts['pairs_tested']} unproved {loaded.counts['pairs_unproved']} "
          f"pools {loaded.counts['pools']} structures {loaded.counts['structures']} "
          f"line_members {loaded.counts['line_objects']}")
    print(f"[{icao}] partition work: old   pairs_tested "
          f"{old.counts['pairs_tested']} unproved {old.counts['pairs_unproved']} "
          f"pools {old.counts['pools']} structures {old.counts['structures']} "
          f"line_members {old.counts['line_objects']}")
    rows = ("members", "parts", "contacts", "abutments", "line_objects",
            "no_parts", "below_grade", "terrain_adapted", "multi_anchor")
    bad = 0
    for k in rows:
        a, b = int(old.counts.get(k, 0)), int(new.counts.get(k, 0))
        flag = "EQUAL" if a == b else f"DIFFER {b - a:+d}"
        if a != b and k in ("parts", "contacts", "abutments"):
            bad += 1
        print(f"    {k:<16} old {a:>8}   new {b:>8}   {flag}")
    # THE PID IS PARTITION-LOCAL and renumbers between the two orders, so
    # every set below is keyed by a part's IDENTITY: its member's
    # resource, its component index in that file and where it stands.
    def _key(m, p):
        return (m.resource, p.comp, round(p.lat, 6), round(p.lon, 6))

    def _ident(part):
        return {p.pid: _key(m, p) for u in part.units for m in u.members
                for p in m.parts}

    oi, ni = _ident(old), _ident(new)

    def _pairs(part, ident):
        out = set()
        for a, b in part.contacts:
            ka, kb = ident.get(a), ident.get(b)
            if ka is not None and kb is not None:
                out.add((ka, kb) if ka <= kb else (kb, ka))
        return out

    def _abuts(part, ident):
        out = set()
        for a, b in part.abutments:
            ka, kb = ident.get(a), ident.get(b)
            if ka is not None and kb is not None:
                out.add((ka, kb) if ka <= kb else (kb, ka))
        return out

    oc, nc = _pairs(old, oi), _pairs(new, ni)
    oa, na = _abuts(old, oi), _abuts(new, ni)
    print(f"    contact pairs  only-old {len(oc - nc)}  only-new {len(nc - oc)}"
          f"  shared {len(oc & nc)}")
    print(f"    abutment pairs only-old {len(oa - na)}  only-new {len(na - oa)}"
          f"  shared {len(oa & na)}")
    op = set(oi.values())
    npp = set(ni.values())
    print(f"    parts          only-old {len(op - npp)}  only-new {len(npp - op)}")
    for k in sorted({k[0] for k in (op - npp)})[:8]:
        print(f"      only-old part in {k}")
    for k in sorted({k[0] for k in (npp - op)})[:8]:
        print(f"      only-new part in {k}")
    return 0 if bad == 0 else 1


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
    s.add_argument("--line-objects", action="store_true",
                   help="stamp the LINE-OBJECT verdict (RULINGS 2026-09-10bb, spec §16) onto a plan "
                        "that predates it, read off the authored files — the 10bb what-if on an "
                        "earlier build's plan and mesh (the plan's own feet stand in for the "
                        "widened drape stations)")
    s.add_argument("--elevated-decks", action="store_true",
                   help="stamp the ELEVATED-DECK verdict (owner RULINGS 2026-09-11a, spec §17.5) "
                        "onto a plan that predates it, read off the authored files — the 11a "
                        "what-if (which bodies may be a cross-placement JUNIOR) on an earlier "
                        "build's plan and mesh")
    s.add_argument("--no-groups", action="store_true",
                   help="drop the plan's AUTHORED-FRAME ABUTMENTS (owner RULINGS 2026-09-10ay, "
                        "spec §17): the pre-10ay seat over the SAME build, so one build serves "
                        "both arms of the abutment-group A/B")
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
    o = sub.add_parser("order", help="THE PARTITION-ORDER TWIN (11j / spec §11a (3)): "
                                     "filter-a-partition vs partition-a-filtered-set")
    o.add_argument("icao")
    o.add_argument("--dem-frame", default="production", choices=("production", "authored"))
    o.add_argument("--old-first", action="store_true",
                   help="run the CONTROL arm first (the arm that runs first is "
                        "the slower one: read the timing bar both ways)")
    o.set_defaults(fn=cmd_order)
    d = sub.add_parser("disk", help="a pack's current bake state (read-only)")
    d.add_argument("pack_root")
    d.add_argument("--filter", default="")
    d.set_defaults(fn=cmd_disk)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
