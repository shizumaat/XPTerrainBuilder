#!/usr/bin/env python3
"""THE v2 SOLVE REPLAY — capture one airport's v2 pipeline product at the
territory stage ONCE, then re-run the constraint generators and the solve
under the CURRENT tree as often as a change needs, without paying for the
load / classify / planar stages again (the synthetic-first solve-arm
pattern of ``docs/specs/auto-patch-v2/heca-sag-ablation/ablate_heca_pin.py``,
promoted on its second use by lane ``v2chord``).

    venv/bin/python tools/v2_solve_replay.py --capture ICAO --out DIR/ICAO.pkl
    venv/bin/python tools/v2_solve_replay.py --replay DIR/ICAO.pkl [--from constraints|shapes|planar]
        [--drop-generator G ...] [--json OUT.json] [--z-out Z.npy]

``--capture`` runs load → PACK PARTITION + GROUPS (owner RULINGS
2026-09-11j; folded in 2026-09-12u after a replay off a capture without
them silently solved a different problem — no foot rows, no pad relief)
→ classify → planar (which labels the SHAPES, owner RULINGS 2026-09-08k)
→ flat site → road profile → shape stage exactly as ``pipeline/build.py``
does and pickles the airport, the classification, the planar map and the
stage.  A capture predating that is REFUSED BY NAME at replay
(:func:`capture_has_groups`).  ``--replay`` resumes from
the named stage (``constraints``: generators + joint filter + solve, the
default; ``shapes``: the shape stage too; ``planar``: the planar build
too — for a change in the map or the shapes) and
prints, per runway with two CIFP thresholds, the crown-ridge BOW (min of
z − the threshold line), the ridge minimum and its station, and z − DEM
over the ridge (mean / min / max); the law-tier line, the yielded-rows
figure per family and per shape (``constraints.yielding.yielded_rows``),
the shapes (count, the largest, the shape of each ``--site``), the joint
steps and the solve wall (ONE pass, 08k (4)).  No patch is written: this is the solve arm, the emitted
patch is the closing build's (``harness/build_airport.py``).

Run it from ``Ortho4XP/``; read-only on the shared corpus (the capture
reads through the production loader like a build; nothing is written
outside ``--out`` / ``--json``)."""
from __future__ import annotations

import argparse
import dataclasses as _dc
import json
import math
import pickle
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def capture_has_groups(cap: dict) -> bool:
    """IS THIS CAPTURE THE BUILD'S WHOLE PRE-SOLVE HALF? (owner RULINGS
    2026-09-12u, spec \u00a730 (3a)).  A capture written before the pack
    partition was folded in carries an ``Airport`` with no ``partition``
    and no derived ``groups``, and a replay off it silently solves a
    DIFFERENT problem.  One derivation, so the refusal and its twin read
    the same predicate."""
    ap = cap.get("airport")
    groups = getattr(ap, "groups", None)
    return (getattr(ap, "partition", None) is not None
            and groups is not None and bool(getattr(groups, "groups", ())))


def capture(icao: str, out: Path, mod_cache_root: str | None = None) -> None:
    """THE CAPTURE IS ``pipeline/build.py``'s OWN PRE-SOLVE HALF, WHOLE
    (owner RULINGS 2026-09-12u, spec §30 (3a)).  Until 12u it ran
    load → classify → planar and SKIPPED the pack partition and the group
    derivation ``build.py:288-318`` runs BEFORE classify — so the captured
    ``Airport`` carried no ``partition`` and no ``groups``, and every
    replay off it silently solved a DIFFERENT problem: no ``foot_rows``,
    no ``pad_relief`` targets, no basin bodies.  Scout ``v2unsettled``
    paid for that trap once (its ``capture2.py``, folded in here): the
    replay of the shipped LEMD solve could not reproduce the shipped hard
    set until the partition and the groups were captured with it.  ONE
    ``ResourceCache`` for the whole capture, and the same objects handed
    to ``build_planar`` — the pack is read once, as the build reads it."""
    from auto_patch_v2.airport import flat_site as _flat
    from auto_patch_v2.airport.load import load_with_report
    from auto_patch_v2.airport.obj8 import ResourceCache as _RCache
    from auto_patch_v2.airport.pack_partition import partition_pack as _partition_pack
    from auto_patch_v2.airport.road_profile import preferred_road_z
    from auto_patch_v2.classify import classify, load_rules
    from auto_patch_v2.law import Law
    from auto_patch_v2.law.tables import group_span_max_m as _span_max
    from auto_patch_v2.pipeline.__main__ import default_inputs
    from auto_patch_v2.pipeline.shapes import shape_stage
    from auto_patch_v2.planar.basins import read_objects as _read_objects
    from auto_patch_v2.planar.build import build as build_planar
    from auto_patch_v2.planar.group import derive as _derive_groups
    law = Law.for_airport(icao)
    inputs = default_inputs()
    if mod_cache_root:
        # THE LANE-LOCAL DERIVED CACHE (RULINGS 2026-09-13, lane
        # ``v2zerocrater``): ``default_inputs`` reads no environment (the
        # M0 §1 law ``test_model`` enforces), so the harness's
        # copy-on-write ``Airport_mod_cache`` overlay is named HERE.  Needed
        # to replay a pack the object stage has rewritten: v2's read frame
        # is the ``.dsf.anchor_bak``, whose dump only the driver's
        # ``engine_v2.fresh_pack_dump`` makes, and it must land lane-local.
        inputs = _dc.replace(inputs, mod_cache_root=mod_cache_root)
    t = time.perf_counter()
    airport, _lrep = load_with_report(icao, inputs, law)
    # THE PACK PARTITION AND THE GROUPS (build.py:288-318, verbatim in
    # kind — the pad law's bodies, feet and abutments, and the feasibility
    # verdict priced against the DEM's own fall, RULINGS 09-11j / 09-11q).
    ocache = _RCache(law.tables.structures.basin.min_solid_thickness_m)
    pack_objects, pack_report = _read_objects(airport, law, ocache)
    _part = _partition_pack(airport, pack_objects, ocache, law)
    _to_xy, _ = airport.frame.transformers()

    def _dem_at(lat: float, lon: float) -> float | None:
        x, y = _to_xy(lon, lat)
        try:
            z = airport.dem.z(x, y)
        except Exception:
            return None
        if z is None:
            return None
        z = float(z)
        return None if z != z else z        # NaN outside the raster

    _bank = float(law.tables.emit.design.bank_slope)
    _groups = _derive_groups(_part, _span_max(law), _bank,
                             dem_at=_dem_at, bank_slope=_bank)
    airport = _dc.replace(airport, partition=_part, groups=_groups)
    print(f"[{icao}] pack partition {time.perf_counter() - t:.0f} s  "
          f"bodies {_groups.counts['bodies']}  groups {_groups.counts['groups']}  "
          f"relief {_groups.counts['relief_bodies']}  "
          f"infeasible {_groups.counts['infeasible']}")
    cl = classify(airport, law, load_rules(), cache=ocache)
    objects_out: list = []
    pm, _pstats = build_planar(airport, cl, law, objects_out=objects_out, cache=ocache,
                               objects=pack_objects, object_report=pack_report)
    fv = _flat.detect(airport, law, objects=objects_out[0] if objects_out else ())
    airport = _dc.replace(airport, flat_site=fv)
    road_pref, _rep, _p = preferred_road_z(airport, pm, law, inputs.road_grade_limit,
                                           inputs.lane_width_m)
    pm = _dc.replace(pm, preferred_z=road_pref)
    stage = shape_stage(pm, law, airport, cl)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as fh:
        pickle.dump({"icao": icao, "airport": airport, "cl": cl, "pm": pm, "stage": stage,
                     "inputs": inputs}, fh)
    print(f"[{icao}] captured -> {out} in {time.perf_counter() - t:.0f} s "
          f"(vertices {len(pm.vertices)}, faces {len(pm.faces)})")


def network_crosscheck(pm, law, airport) -> dict:
    """THE PREDICATE AGAINST ``routes.reach`` (spec §10 deviation): the
    taxi-family faces carrying a centreline edge whose endpoints the
    threshold pins reach along the route graph, against
    ``planar.shapes.network_faces`` (the breakline graph from the runway
    roots); prints and returns the two counts and the symmetric difference."""
    from auto_patch_v2.constraints.no_step import reach_band_values
    from auto_patch_v2.planar.shapes import STATION_KIND, network_faces
    net, _N = network_faces(pm, law)
    rw = set(law.tables.precedence.runway_family.members)
    taxi = set(law.tables.precedence.taxi_family.members)
    planar_net = {f for f in net if pm.faces[f].role in taxi}
    reach = reach_band_values(pm, law, airport)
    by_reach: set[int] = set()
    for b in pm.breaklines.values():
        if b.kind != STATION_KIND:
            continue
        for eid in b.edges:
            e = pm.edges[eid]
            if e.a in reach and e.b in reach:
                by_reach.update(f for f in (e.left_face, e.right_face)
                                if f is not None and pm.faces[f].role in taxi)
    only_planar = sorted(planar_net - by_reach)
    only_reach = sorted(by_reach - planar_net)
    print(f"[{pm.icao}] network cross-check: planar predicate {len(planar_net)} taxi-family faces, "
          f"routes.reach {len(by_reach)} (reach vertices {len(reach)}); only planar {len(only_planar)} "
          f"{[(f, pm.faces[f].role, pm.faces[f].ref) for f in only_planar[:8]]}; only reach {len(only_reach)} "
          f"{[(f, pm.faces[f].role, pm.faces[f].ref) for f in only_reach[:8]]}; runway faces {len(net) - len(planar_net)}")
    return {"planar": len(planar_net), "reach": len(by_reach), "only_planar": only_planar, "only_reach": only_reach}


def runway_read(pm, law, airport, z) -> list[dict]:
    """Per runway with two thresholds: bow, ridge min, z − DEM over the ridge."""
    from auto_patch_v2.constraints.precedence import view
    from auto_patch_v2.constraints.runway_profile import ridge_chains
    chains = ridge_chains(view(pm, law))
    out = []
    for rw in airport.runways:
        e0, e1 = rw.ends
        if e0.threshold_elev_m is None or e1.threshold_elev_m is None:
            continue
        chs = chains.get(rw.id) or []
        vs = [v for ch in chs for v in ch]
        if not vs:
            continue
        L = math.dist(e0.xy, e1.xy)
        ux, uy = (e1.xy[0] - e0.xy[0]) / L, (e1.xy[1] - e0.xy[1]) / L
        rows = []
        for v in vs:
            x, y = pm.vertices[v].xy
            s = (x - e0.xy[0]) * ux + (y - e0.xy[1]) * uy
            line = e0.threshold_elev_m + (e1.threshold_elev_m - e0.threshold_elev_m) * s / L
            rows.append((s, float(z[v]), line, pm.vertices[v].dem_z, v))
        bow = min(rows, key=lambda r: r[1] - r[2])
        zmin = min(rows, key=lambda r: r[1])
        off = [r[1] - r[3] for r in rows if r[3] is not None]
        out.append({"runway": rw.id, "bow_m": round(bow[1] - bow[2], 2), "bow_station_m": round(bow[0]),
                    "ridge_min_z": round(zmin[1], 2), "ridge_min_station_m": round(zmin[0]),
                    "z_dem_mean": round(sum(off) / len(off), 2) if off else None,
                    "z_dem_min": round(min(off), 2) if off else None,
                    "z_dem_max": round(max(off), 2) if off else None, "stations": len(rows)})
    return out


def _site_read(pm, airport, z, sites, near_m: float = 12.0) -> list[dict]:
    """Per lat/lon site: the map vertices within ``near_m`` — z, DEM, z − DEM
    and the roles touching them (the owner's site figures, RULINGS 2026-09-08g-2)."""
    to_xy, _ = airport.frame.transformers()
    pm_step_horizon = 1.0        # a STEP is a |dz| across an edge shorter than twice the readers' contact horizon
    out = []
    for lat, lon in sites:
        x, y = to_xy(lon, lat)
        hits = []
        for vid, v in pm.vertices.items():
            d = math.hypot(v.xy[0] - x, v.xy[1] - y)
            if d <= near_m and v.dem_z is not None:
                roles = sorted({pm.faces[f].role for f in v.incident_faces})
                hits.append({"v": vid, "dist_m": round(d, 1), "z": round(float(z[vid]), 2),
                             "dem": round(v.dem_z, 2), "z_dem": round(float(z[vid]) - v.dem_z, 2),
                             "roles": roles, "shape": pm.shape_of_vertex.get(vid, -1),
                             "faces": sorted(v.incident_faces)})
        hits.sort(key=lambda h: h["dist_m"])
        near_ids = {h["v"] for h in hits}
        step = 0.0
        for e in pm.edges.values():
            if e.a in near_ids and e.b in near_ids:
                d = math.dist(pm.vertices[e.a].xy, pm.vertices[e.b].xy)
                dz = abs(float(z[e.a]) - float(z[e.b]))
                if d < 2.0 * pm_step_horizon and dz > step:
                    step = dz
        off = [h["z_dem"] for h in hits]
        out.append({"lat": lat, "lon": lon, "vertices": len(hits),
                    "z_dem_mean": round(sum(off) / len(off), 2) if off else None,
                    "z_dem_min": round(min(off), 2) if off else None,
                    "z_dem_max": round(max(off), 2) if off else None,
                    "roles": sorted({r for h in hits for r in h["roles"]}),
                    "shapes": sorted({h["shape"] for h in hits}),
                    "max_step_m": round(step, 2),
                    "nearest": hits[:3]})
    return out


def _why_hump(icao, pm, law, airport, cs, z, runway: str, s0: float, s1: float,
              out=print, relax: list[str] | None = None, vertex: int | None = None) -> dict:
    """``why`` for the highest crown-ridge vertex of ``runway`` in stations
    ``[s0, s1]`` (z − threshold chord): the binding rows by family on the
    vertex (solve.why.bindings — a duals solve of the SAME LP) and the chain
    trace to its hard terminal.  No relax arms (each is a full re-solve)."""
    import numpy as np
    from auto_patch_v2.constraints.precedence import view
    from auto_patch_v2.constraints.runway_profile import ridge_chains
    from auto_patch_v2.model.constraints import Diff, Linear
    from auto_patch_v2.solve.why import Prepared, bindings, chain_trace, solve_with_pressure, _vname, _row_desc
    hump: list[int] = []
    best = None
    if vertex is not None:
        best = (float("nan"), vertex, float("nan"))
        hump = [vertex]
    else:
        rw = next(r for r in airport.runways if r.id == runway)
        e0, e1 = rw.ends
        L = math.dist(e0.xy, e1.xy)
        ux, uy = (e1.xy[0] - e0.xy[0]) / L, (e1.xy[1] - e0.xy[1]) / L
        chains = ridge_chains(view(pm, law))
        for ch in chains.get(rw.id) or []:
            for v in ch:
                x, y = pm.vertices[v].xy
                s = (x - e0.xy[0]) * ux + (y - e0.xy[1]) * uy
                if not (s0 <= s <= s1):
                    continue
                hump.append(v)
                line = e0.threshold_elev_m + (e1.threshold_elev_m - e0.threshold_elev_m) * s / L
                if best is None or z[v] - line > best[0]:
                    best = (z[v] - line, v, s)
    if best is None:
        out(f"[{icao}] why-hump: no ridge vertex of {runway} in s {s0}..{s1}")
        return {}
    above, v, s = best
    out(f"[{icao}] why-hump {runway}: ridge vertex v{v} at s={s:.0f}  z {z[v]:.2f}  chord+{above:.2f}  "
        f"DEM {pm.vertices[v].dem_z:.2f} (z-DEM {z[v] - pm.vertices[v].dem_z:+.2f}); pressure solve ...")
    t = time.perf_counter()
    sol2, drep, press = solve_with_pressure(pm, cs, law)
    zz = np.asarray(sol2.z, float)
    out(f"    pressure solve {time.perf_counter() - t:.0f} s status {sol2.status.value}; "
        f"|z_pressure - z| max {float(np.max(np.abs(zz - np.asarray(z)))):.3f} m")
    prep = Prepared(icao, airport, law, pm, cs, {}, drep, zz, {}, press)
    bl = bindings(prep, [v])[v]
    fam: dict[str, dict] = {}
    for b in bl:
        rec = fam.setdefault(b.family, {"rows": 0, "sum_abs_dual": 0.0, "example": _row_desc(prep, b)})
        rec["rows"] += 1
        rec["sum_abs_dual"] += abs(b.dual or 0.0)
    out(f"    binding rows on v{v} by family (rows, sum|dual|, example):")
    for k, r in sorted(fam.items(), key=lambda kv: -kv[1]["sum_abs_dual"]):
        out(f"      {k:20s} {r['rows']:4d}  {r['sum_abs_dual']:10.2f}  {r['example']}")
    if not fam:
        out("      (none: no row binds the vertex — the objective holds it)")
    tr = chain_trace(prep, [v])
    trace = None
    if tr is not None:
        fams: dict[str, float] = {}
        for st in tr.steps:
            fams[st.family] = fams.get(st.family, 0.0) + st.dz
        out(f"    chain trace: terminal {_vname(prep, tr.terminal)} z {zz[tr.terminal]:.2f} "
            f"[{tr.terminal_kind}: {tr.terminal_note}]; {len(tr.steps)} hops; sum dz {tr.sum_dz:+.2f} m")
        out("    by family along the chain (sum dz): " + ", ".join(
            f"{k} {d:+.2f}" for k, d in sorted(fams.items(), key=lambda kv: -abs(kv[1]))))
        for i, st in enumerate(tr.steps[:12]):
            r = st.row
            extra = (f"cap {r.cap:.2%} x {r.d:.1f} m" if isinstance(r, Diff) else
                     f"{type(r).__name__} {r.source.ruling[:40]}")
            out(f"      {i + 1:3d}. {_vname(prep, st.v)} z {zz[st.v]:.2f} -> {_vname(prep, st.u)} "
                f"z {zz[st.u]:.2f} dz {st.dz:+.2f} {st.family} {extra}")
        trace = {"terminal": tr.terminal, "terminal_kind": tr.terminal_kind, "terminal_note": tr.terminal_note,
                 "hops": len(tr.steps), "sum_dz": round(tr.sum_dz, 2),
                 "by_family": {k: round(d, 2) for k, d in fams.items()}}
    else:
        out("    chain trace: no terminal reached — the objective holds it")
    arms = {}
    if relax:
        from auto_patch_v2.solve.why import relax_family
        out(f"    relax-one-family arms over {len(hump)} ridge vertices (full re-solve each; dz = z_arm - z):")
        for fam_name in relax:
            t = time.perf_counter()
            rr = relax_family(prep, fam_name, hump)
            arms[fam_name] = {"rows_dropped": rr.rows_dropped, "status": rr.status, "dz_median": round(rr.dz_median, 3),
                         "dz_min": round(rr.dz_min, 3), "dz_max": round(rr.dz_max, 3)}
            out(f"      {fam_name:22s} -{rr.rows_dropped:6d} rows  {rr.status:8s}  dz median {rr.dz_median:+.3f}  "
                f"min {rr.dz_min:+.3f}  max {rr.dz_max:+.3f}  ({time.perf_counter() - t:.0f} s)")
    return {"vertex": v, "relax_arms": arms, "hump_vertices": len(hump),
            "station_m": None if s != s else round(s), "z": round(float(z[v]), 2),
            "above_chord_m": None if above != above else round(float(above), 2),
            "z_dem": round(float(z[v] - pm.vertices[v].dem_z), 2),
            "families": {k: {"rows": r["rows"], "sum_abs_dual": round(r["sum_abs_dual"], 2), "example": r["example"]}
                         for k, r in fam.items()}, "trace": trace}


def replay(pkl: Path, resume: str, drop: list[str], json_out: Path | None,
           z_out: Path | None, method: str = "normal",
           design_weights: dict[str, float] | None = None, verbose: bool = False,
           sites: list[tuple[float, float]] | None = None, emit_dir: Path | None = None,
           why_hump: tuple[str, float, float] | None = None, verify: bool = False,
           solved_out: Path | None = None, chord_fill: tuple[str, ...] = (),
           site_radius_m: float = 12.0) -> int:
    import numpy as np
    from auto_patch_v2.airport.road_profile import preferred_road_z
    from auto_patch_v2.law import Law
    from auto_patch_v2.model.constraints import ConstraintSet
    from auto_patch_v2.pipeline.build import displacement_by_role
    from auto_patch_v2.pipeline.shapes import joint_steps, shape_constraints, shape_stage
    from auto_patch_v2.planar.build import build as build_planar
    from auto_patch_v2.solve import Options
    from auto_patch_v2.solve import solve_design
    with pkl.open("rb") as fh:
        cap = pickle.load(fh)
    icao, airport, cl, pm, stage, inputs = (cap["icao"], cap["airport"], cap["cl"], cap["pm"],
                                            cap["stage"], cap["inputs"])
    if not capture_has_groups(cap):
        raise SystemExit(
            f"[{icao}] REFUSED: this capture carries no pack PARTITION / GROUPS, so the "
            "replay would solve a DIFFERENT problem from the build (no foot rows, no pad "
            "relief targets, no basin bodies) — the trap owner RULINGS 2026-09-12u names, "
            "spec \u00a730 (3a).  Re-capture with the current tool: "
            f"venv/bin/python tools/v2_solve_replay.py --capture {icao} --out {pkl}")
    law = Law.for_airport(icao)
    t0 = time.perf_counter()
    if resume == "planar":
        pm, _ps = build_planar(airport, cl, law)
        road_pref, _r, _p = preferred_road_z(airport, pm, law, inputs.road_grade_limit,
                                             inputs.lane_width_m)
        pm = _dc.replace(pm, preferred_z=road_pref)
    from auto_patch_v2.constraints.runway_chord import with_runway_chord

    def _targets(m):
        """THE BUILD'S OWN TARGET CHANNELS, in ``pipeline/build.py``'s order:
        the runway profile, then the taxi chains' trend (RULINGS 2026-09-10v),
        then the apron bodies' 2-D trend (RULINGS 2026-09-10ar).  The replay
        claims to reproduce the build's LP, so it must publish all three —
        without them a replay arm silently solves a DIFFERENT problem (this
        is how a lane read two arms of the apron trend as byte-identical).
        A tree that predates a channel simply does not have it: the import
        is asked for, never assumed, so an OLD capture and an OLD tree still
        replay."""
        m = with_runway_chord(m, law, airport, fill_roles=chord_fill)
        for mod, fn in (("taxi_trend", "with_taxi_trend"),
                        ("apron_trend", "with_apron_trend")):
            try:
                pub = getattr(__import__(f"auto_patch_v2.constraints.{mod}",
                                         fromlist=[fn]), fn)
            except (ImportError, AttributeError):
                continue
            m = pub(m, law, airport)
        return m

    if chord_fill:
        print(f"[{icao}] chord-fill target arm (08g-2): roles {chord_fill} within the strip take the "
              f"crown-plane chord target")
    if resume == "shapes":
        from auto_patch_v2.planar.shapes import build_shapes
        pm, sst = build_shapes(pm, law, airport, cl)      # the shapes over the captured map
        print(f"[{icao}] network (08p): {sst.network_faces} of {sst.faces} pavement faces "
              f"({', '.join(f'{k} {n}' for k, n in sorted(sst.network_by_role.items()))}), "
              f"{sst.network_vertices} vertices, {sst.connected_stations} connected stations, "
              f"{sst.unconnected_station_edges} unconnected centreline edges; bodies {sst.body_faces} faces "
              f"({sst.faces_unlabelled} welded whole)")
        print(f"[{icao}] shapes rebuilt: {sst.body_faces} body faces -> {sst.components} components, {sst.bodies} bodies, "
              f"{sst.shapes} shapes (strip welds {sst.welded_strip_pairs}, route welds {sst.welded_route_pairs}); "
              f"joints {sst.contours} contours ({sst.contour_length_m:,.0f} m) + {sst.gap_joints} gap; {sst.wall_s:.2f} s")
        print(f"[{icao}] by shape (id, faces, m2, vertices, roles): {sst.by_shape[:12]}")
    network_crosscheck(pm, law, airport)
    if resume in ("planar", "shapes"):
        pm = _targets(pm)                                 # change 1 (build.py order)
        stage = shape_stage(pm, law, airport, cl)
    else:
        stage = _dc.replace(stage, pm=_targets(stage.pm))
    pm = stage.pm
    if design_weights:
        d0 = law.tables.emit.design
        law = _dc.replace(law, tables=_dc.replace(
            law.tables, emit=_dc.replace(law.tables.emit,
                                         design=_dc.replace(d0, **design_weights))))
        print(f"[{icao}] design weight ARM: {design_weights} -> {law.tables.emit.design}")
    size: dict = {}
    cs, counts, _w = shape_constraints(pm, law, airport, stage)
    if drop:
        cs = ConstraintSet.from_rows([r for r in cs.rows() if r.source.generator not in drop])
    t = time.perf_counter()
    sol, rep = solve_design(pm, cs, law, Options(verbose=verbose), size_out=size, method=method)
    wall = round(time.perf_counter() - t, 1)
    print(f"[{icao}] solve (ONE pass, 08k): {wall:.1f} s status {sol.status.value}")
    print(f"[{icao}] resume {resume}; rows {cs.counts()}; dropped generators {drop or '-'}; "
          f"solve {wall:.1f} s status {sol.status.value}; {rep.line()}")
    print(f"[{icao}] LP size: {size}")
    n_shapes = len({v for v in pm.shape_of_vertex.values() if v >= 0})
    by_shape: dict[int, int] = {}
    for v in pm.shape_of_vertex.values():
        by_shape[v] = by_shape.get(v, 0) + 1
    print(f"[{icao}] shapes (08k): {n_shapes} over {len(pm.shape_of_vertex)} vertices; joints "
          f"{len(pm.shape_joints)} ({sum(1 for j in pm.shape_joints if j.gap)} gap); largest by vertices "
          f"{sorted(by_shape.items(), key=lambda kv: -kv[1])[:6]}")
    result = {"icao": icao, "resume": resume, "drop": drop, "status": sol.status.value,
              "solve_wall_s": wall, "passes": 1,
              "shapes": n_shapes, "shape_vertices": len(pm.shape_of_vertex),
              "shapes_by_vertices": sorted(by_shape.items(), key=lambda kv: -kv[1])[:12],
              "stage_wall_s": round(time.perf_counter() - t0 - wall, 1),
              "design": rep.as_dict(), "counts": {k: v for k, v in counts.items()
                                               if not k.startswith("joint_dropped")},
              "joint_dropped": {k[14:]: v for k, v in counts.items() if k.startswith("joint_dropped.")}}
    if sol.status.value in ("optimal", "feasible"):
        z = np.asarray(sol.z, float)
        result["runways"] = runway_read(pm, law, airport, z)
        for r in result["runways"]:
            print(f"    {r['runway']}: bow {r['bow_m']:+.2f} at s={r['bow_station_m']}  ridge min "
                  f"{r['ridge_min_z']:.2f} at s={r['ridge_min_station_m']}  z-DEM mean "
                  f"{r['z_dem_mean']:+.2f} min {r['z_dem_min']:+.2f} max {r['z_dem_max']:+.2f}")
        moved = displacement_by_role(pm, law, sol)
        result["off_dem_by_role"] = moved
        print("    off-DEM by role (max |z-DEM| m, over 0.5 m / vertices): " + ", ".join(
            f"{k} {v['max_m']:.2f} ({v['over']}/{v['vertices']})" for k, v in moved.items()))
        js = joint_steps(pm, law, stage, z)
        worst = sorted(js["contours"], key=lambda c: -c["step_m"])[:10]
        result["joints"] = {"count": len(js["contours"]), "gap": sum(1 for c in js["contours"] if c["gap"]),
                            "max_step_m": max((c["step_m"] for c in js["contours"]), default=0.0),
                            "worst": worst, "roads": js["roads"][:10]}
        print(f"    joints (08k): {result['joints']['count']} ({result['joints']['gap']} gap), max step "
              f"{result['joints']['max_step_m']:.2f} m; worst "
              f"{[(c['id'], c['step_m'], c['shapes'], 'gap' if c['gap'] else 'contour') for c in worst]}")
        if js["roads"]:
            print(f"    road steps: {[(r['face'], r['ref'], r['step_m']) for r in js['roads'][:8]]}")
        result["road_ramps"] = js.get("ramps", [])
        if js.get("ramps"):
            print(f"    road ramps (08r-2): {len(js['ramps'])}; steepest "
                  f"{[(r['face'], r['ref'], r['dz_m'], r['length_m'], round(100 * r['grade'], 2)) for r in js['ramps'][:8]]}; "
                  f"too short {[(r['face'], r['ref']) for r in js['ramps'] if r['too_short']]}")
        if sites:
            result["sites"] = _site_read(pm, airport, z, sites, site_radius_m)
            for srec in result["sites"]:
                print(f"    site {srec['lat']:.6f},{srec['lon']:.6f}: {srec['vertices']} vertices within {site_radius_m:g} m, "
                      f"z-DEM mean {srec['z_dem_mean']} min {srec['z_dem_min']} max {srec['z_dem_max']} "
                      f"roles {srec['roles']} shapes {srec['shapes']} max step over a short edge {srec['max_step_m']} m")
        if verify:
            # THE VERIFY CENSUS on the solved surface (the build's own reader,
            # ``pipeline/build.py``): the rows per family and the DEFECT
            # families the app's driver gates on
            from auto_patch_v2.constraints.roads import road_law_caps
            from auto_patch_v2.emit.graded import graded_surface
            from auto_patch_v2.pipeline.publication import publication
            from auto_patch_v2.verify import census as run_census
            from auto_patch_v2.verify.census import DEFECT_KEYS
            t = time.perf_counter()
            surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs,
                                  {"law_ruleset": law.ruleset_key, "pack": airport.pack.name})
            vrows = run_census(surf, law, publication(pm, law, airport, sol.z, cs),
                               road_law_caps(pm, law, airport))
            summary = {k: len(v) for k, v in vrows.items() if v}
            result["verify"] = {"by_family": summary,
                                "defects": {k: len(vrows[k]) for k in DEFECT_KEYS if vrows.get(k)}}
            print(f"    verify {time.perf_counter() - t:.1f} s: {sum(summary.values())} rows  "
                  + ", ".join(f"{k} {n}" for k, n in sorted(summary.items())))
            print(f"    verify DEFECT families ({', '.join(DEFECT_KEYS)}): "
                  + (", ".join(f"{k} {n}" for k, n in result["verify"]["defects"].items())
                     or "ALL ZERO"))
            for k in DEFECT_KEYS:
                for r in (vrows.get(k) or [])[:6]:
                    print(f"      {k}: {r}")
            result["verify"]["defect_rows"] = {k: (vrows.get(k) or [])[:20] for k in DEFECT_KEYS}
        if solved_out is not None:
            # the solved set (pm, stage, rows, z) for a later ``--why-from``
            # (the duals solve is a second full LP; kept out of the timed arm)
            with solved_out.open("wb") as fh:
                pickle.dump({"icao": icao, "airport": airport, "law_icao": icao, "pm": pm, "cs": cs,
                             "z": z}, fh)
        if why_hump is not None:
            result["why_hump"] = _why_hump(icao, pm, law, airport, cs, z, *why_hump)
        if z_out is not None:
            np.save(z_out, z)
        if emit_dir is not None:
            # THE PATCH (the build's emit half, ``pipeline/build.py``): so the
            # same-frame divergence (``tools/patch_proximity_diff.py``) can be
            # read on a replay arm — no rebake plan, no tile pieces
            from auto_patch_v2.emit.graded import graded_surface
            from auto_patch_v2.emit.osm_adapter import write_patch
            from auto_patch_v2.pipeline.publication import face_tags, publication
            t = time.perf_counter()
            surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs,
                                  {"law_ruleset": law.ruleset_key, "pack": airport.pack.name})
            pub = publication(pm, law, airport, sol.z, cs)
            header = {"o4_apt_dat": airport.pack.apt_dat_path, "o4_pack": airport.pack.name,
                      "o4_replay": "v2_solve_replay"}
            paths = write_patch(surf, law, emit_dir, pub, header, face_tags(pm, law, airport))
            result["patch"] = str(paths.patch)
            print(f"    emitted {paths.patch} ({paths.ways} ways, {paths.nodes} nodes) in "
                  f"{time.perf_counter() - t:.1f} s")
    if json_out is not None:
        json_out.write_text(json.dumps(result, indent=1, default=str))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--capture", metavar="ICAO")
    ap.add_argument("--mod-cache-root", metavar="DIR",
                    help="Airport_mod_cache root for the capture (the harness's "
                         "lane-local copy-on-write overlay); default: the engine "
                         "tree's mount")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--replay", type=Path, metavar="PKL")
    ap.add_argument("--from", dest="resume", choices=("constraints", "shapes", "planar"),
                    default="constraints")
    ap.add_argument("--drop-generator", action="append", default=[])
    ap.add_argument("--json", type=Path)
    ap.add_argument("--z-out", type=Path)
    ap.add_argument("--design-weight", action="append", default=[], metavar="TERM=W",
                    help="MEASUREMENT ARM: override an emit.toml [design] weight for this "
                         "replay only (never a build); TERM in law/design_schema.DESIGN_TERMS")
    ap.add_argument("--design-verbose", action="store_true",
                    help="print the design solve's objective per active-set round")
    ap.add_argument("--method", default="normal", choices=("normal", "cg", "lsqr"),
                    help="the design solve's linear solver (solve/design.METHODS)")
    ap.add_argument("--site", action="append", default=[], metavar="LAT,LON",
                    help="report z - DEM on the vertices within --site-radius of the point")
    ap.add_argument("--site-radius", type=float, default=12.0, metavar="M",
                    help="the --site horizon in metres (default 12; the owner's step horizon is 60)")
    ap.add_argument("--emit", type=Path, metavar="DIR", help="write the patch of the solved surface")
    ap.add_argument("--verify", action="store_true",
                    help="run the v2 verify census on the solved surface and print the rows "
                         "per family and the DEFECT families (the app's gate)")
    ap.add_argument("--chord-fill", nargs="+", default=[], metavar="ROLE",
                    help="experiment arm (08g-2): these roles' vertices within the strip take the "
                         "crown-plane chord as their fit target (constraints.runway_chord fill_roles)")
    ap.add_argument("--solved-out", type=Path, metavar="PKL",
                    help="pickle the solved set for --why-from")
    ap.add_argument("--why-from", type=Path, metavar="PKL",
                    help="run --why-hump on a --solved-out pickle (no re-solve of the arm)")
    ap.add_argument("--why-vertex", type=int, help="why on this vertex id instead of --why-hump")
    ap.add_argument("--why-relax", nargs="+", default=[], metavar="FAMILY",
                    help="relax-one-family arms (solve.why family labels) over the hump's ridge vertices")
    ap.add_argument("--why-hump", nargs=3, metavar=("RUNWAY", "S0", "S1"),
                    help="why on the highest ridge vertex above the chord in stations S0..S1")
    a = ap.parse_args()
    if a.capture:
        if a.out is None:
            ap.error("--capture needs --out")
        capture(a.capture.upper(), a.out, a.mod_cache_root)
        return 0
    if a.why_from:
        from auto_patch_v2.law import Law
        with a.why_from.open("rb") as fh:
            sv = pickle.load(fh)
        law = Law.for_airport(sv["icao"])
        wh = (a.why_hump[0], float(a.why_hump[1]), float(a.why_hump[2])) if a.why_hump else ("", 0.0, 0.0)
        res = _why_hump(sv["icao"], sv["pm"], law, sv["airport"], sv["cs"], sv["z"], *wh,
                        relax=a.why_relax, vertex=a.why_vertex)
        if a.json:
            a.json.write_text(json.dumps(res, indent=1, default=str))
        return 0
    if a.replay:
        sites = [tuple(float(x) for x in it.split(",")) for it in a.site]
        wh = (a.why_hump[0], float(a.why_hump[1]), float(a.why_hump[2])) if a.why_hump else None
        return replay(a.replay, a.resume, a.drop_generator, a.json, a.z_out,
                      method=a.method,
                      design_weights={k.strip(): float(v)
                                      for k, v in (it.split("=") for it in a.design_weight)},
                      verbose=a.design_verbose, sites=sites, site_radius_m=a.site_radius,
                      emit_dir=a.emit, why_hump=wh, verify=a.verify, solved_out=a.solved_out,
                      chord_fill=tuple(a.chord_fill))
    ap.error("one of --capture / --replay")
    return 2


if __name__ == "__main__":
    sys.exit(main())
