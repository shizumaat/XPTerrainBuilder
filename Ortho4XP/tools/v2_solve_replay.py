#!/usr/bin/env python3
"""THE v2 SOLVE REPLAY — capture one airport's v2 pipeline product at the
territory stage ONCE, then re-run the constraint generators and the solve
under the CURRENT tree as often as a change needs, without paying for the
load / classify / planar stages again (the synthetic-first solve-arm
pattern of ``docs/specs/auto-patch-v2/heca-sag-ablation/ablate_heca_pin.py``,
promoted on its second use by lane ``v2chord``).

    venv/bin/python tools/v2_solve_replay.py --capture ICAO --out DIR/ICAO.pkl
    venv/bin/python tools/v2_solve_replay.py --replay DIR/ICAO.pkl [--from constraints|shapes|planar]
        [--drop-generator G ...] [--json OUT.json] [--z-out Z.npy] [--why-hard [N]]
    venv/bin/python tools/v2_solve_replay.py --why-from SOLVED.pkl --why-hard [N]

``--drop-generator`` also takes the pseudo-generator ``eat_ramp_reach``:
the EAT's §36 (5) trend WITHDRAWAL is a channel edit made before the
solve, not a row, so it is dropped by name here rather than by row
filter (``eat_anchor_rect`` drops the pins and their reach together).

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
    the same predicate.

    THE PREDICATE IS "THE DERIVATION RAN", NOT "IT FOUND SOMETHING"
    (lane ``v2roadcap2``, 2026-09-13).  It read ``bool(groups.groups)``
    and so refused every capture of an airport that HAS no groups —
    KCLT's pack partitions 7,163 bodies into 0 groups, and a complete,
    current capture of it could not be replayed at all.  An empty group
    set is a measurement, not a missing stage; a capture predating 12u
    is still caught by ``partition is None``, which is what actually
    distinguishes the two."""
    ap = cap.get("airport")
    return (getattr(ap, "partition", None) is not None
            and getattr(ap, "groups", None) is not None)


def _placement_override(law, over: dict[str, object]):
    """Return ``law`` with ``[placement]`` keys replaced (the CAPTURE arm).

    §16g (10)'s pad keys (``pad_from_cluster``, ``pad_airside_clip``) are
    read in ``classify/evidence._pads`` and ``planar/overlay`` — both
    UPSTREAM of the capture — so ``--design-weight`` (a ``[design]``
    override applied at REPLAY) cannot arm them and a replay of a
    pads-OFF capture silently measures the pads-OFF law however the toml
    reads.  This is the capture-time twin of that override: one matched
    pair is two captures of the same tree, not two edits of the shipped
    law (lane ``v2padqp``, §16g (10) (11)).
    """
    import dataclasses as _d
    fields = {f.name: f.type for f in _d.fields(law.tables.structures.placement)}
    kw: dict[str, object] = {}
    for k, v in over.items():
        if k not in fields:
            raise SystemExit(f"--placement: no such [placement] key {k!r}")
        cur = getattr(law.tables.structures.placement, k)
        if isinstance(cur, bool):
            kw[k] = str(v).strip().lower() in ("1", "true", "yes", "on")
        elif isinstance(cur, (int, float)):
            kw[k] = type(cur)(v)
        else:
            kw[k] = v
    pl = _dc.replace(law.tables.structures.placement, **kw)
    st = _dc.replace(law.tables.structures, placement=pl)
    return _dc.replace(law, tables=_dc.replace(law.tables, structures=st)), kw


def _capture_guarded(icao: str, out: Path, mod_cache_root: str | None = None,
                     placement: dict[str, object] | None = None) -> None:
    """:func:`capture` with the shared-repo guard and the lane-local cache
    redirects armed around it (``harness/build_airport.
    arm_shared_repo_protection``, the ONE arming composition).  The
    REDIRECT must happen before the engine is imported, which is why it
    is here and not inside the capture (lane ``v2padqp``)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    _harness_dir = str(ROOT / "tools" / "harness")
    if _harness_dir not in sys.path:
        sys.path.insert(0, _harness_dir)
    from build_airport import (arm_shared_repo_protection as _arm,
                               report_guard_churn as _churn)
    _guard, _redirects = _arm(ROOT, out.parent, f"cap_{icao}")
    _guard.__enter__()
    try:
        capture(icao, out, mod_cache_root, placement)
    finally:
        _guard.__exit__(None, None, None)
        _churn(_guard)
        print("[guard]", "shared repo UNCHANGED" if not _guard.blocked
              else f"BLOCKED {_guard.blocked}", flush=True)


def capture(icao: str, out: Path, mod_cache_root: str | None = None,
            placement: dict[str, object] | None = None) -> None:
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
    to ``build_planar`` — the pack is read once, as the build reads it.

    THE SHARED-REPO GUARD AND THE LANE-LOCAL CACHE REDIRECTS are armed by
    the CLI around this call (:func:`_capture_guarded`) through
    ``harness/build_airport.arm_shared_repo_protection`` — the ONE arming
    composition (CLAUDE.md; the ``classify_report.py`` precedent, ten
    corpus files written by an unguarded in-process engine call) — and
    every capture prints ``[guard] shared repo UNCHANGED``.  It is armed
    OUTSIDE this function because the redirect must precede the engine
    imports below (lane ``v2padqp``)."""
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
    if placement:
        law, _kw = _placement_override(law, placement)
        print(f"[{icao}] CAPTURE ARM [placement] {_kw}")
    inputs = default_inputs()
    if mod_cache_root:
        # AN EXPLICIT OVERRIDE ONLY (lane ``v2roadcap2``, RULINGS
        # 2026-09-13ab).  ``default_inputs`` now resolves the root through
        # ``O4_File_Names.airport_mod_cache_root``, so the harness's
        # copy-on-write overlay already arrives in ``inputs`` via
        # ``O4_AIRPORT_MOD_CACHE_DIR``; this flag names a root the
        # environment does not.
        inputs = _dc.replace(inputs, mod_cache_root=mod_cache_root)
    # THE PRISTINE-DUMP HALF, THE BUILD ENTRY'S OWN IMPLEMENTATION
    # (``auto_patch.engine_v2.fresh_pack_dump``, public since lane
    # ``v2zerocrater``).  v2's read frame is the ``.dsf.anchor_bak`` and
    # v2 never runs DSFTool itself, so without this a capture of an
    # airport whose pack the object stage has written refuses at
    # ``airport/load.py:289`` — KCLT has never had such a dump (13y).  The
    # dump lands in whatever root was just resolved, which is lane-local
    # whenever an overlay is armed.
    try:
        from auto_patch.engine_v2 import fresh_pack_dump as _fresh_dump
        _harness = str(ROOT / "tools" / "harness")
        if _harness not in sys.path:
            sys.path.insert(0, _harness)
        from build_airport import resolve_tile_for as _resolve_tile
        _tile = _resolve_tile(icao, ROOT)
        if _tile is not None:
            _dump = _fresh_dump(inputs.xplane_root, icao, *_tile)
            if _dump:
                inputs = _dc.replace(inputs, dsf_dump_path=_dump)
                print(f"  pack DSF dump (pristine read frame): {_dump}")
    except Exception as exc:                # the load stage refuses loudly
        print(f"  pack dump refresh skipped for {icao}: {exc}")
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
    # THE CLUSTERS, beside the partition and the groups (``pipeline/
    # build.py:370-380``, the same call on the same input).  Without them
    # ``Airport.clusters`` is empty in every replay of the capture, so
    # §30 (4)'s CLUSTER PAD and its apron reach — and §16g (10)'s derived
    # pads — are INERT and a pads-ON arm silently measures the pads-OFF
    # law (lane ``v2padvert`` 2026-09-14: "pads-ON was NOT measurable off
    # this capture").  Same trap as 12u's missing groups, same answer.
    from auto_patch_v2.planar.cluster import clusters as _derive_clusters
    _cl_t = time.perf_counter()
    airport = _dc.replace(airport, clusters=_derive_clusters(airport, law))
    print(f"[{icao}] clusters {len(airport.clusters)} "
          f"({time.perf_counter() - _cl_t:.0f} s)")
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
                     "inputs": inputs, "placement": dict(placement or {})}, fh)
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


def _worst_vertex_at(pm, airport, z, at: tuple, radius_m: float):
    """The vertex within ``radius_m`` of ``at`` whose |z - DEM| is largest
    — the vertex an owner coordinate MEANS (lane ``v2roadcap2``).  One
    resolution, shared by ``--why-at``; the frame is the airport's own
    transformer, never a proximity join on lat/lon degrees."""
    to_xy, _ = airport.frame.transformers()
    x0, y0 = to_xy(at[1], at[0])
    best = None
    for v, vert in pm.vertices.items():
        x, y = vert.xy
        if (x - x0) ** 2 + (y - y0) ** 2 > radius_m * radius_m:
            continue
        d = vert.dem_z
        if d is None:
            continue
        off = abs(float(z[v]) - float(d))
        if best is None or off > best[0]:
            best = (off, v)
    return None if best is None else best[1]


def why_hard(icao, pm, law, cs, z, limit: int = 40, out=print,
             stage: int | None = None) -> dict:
    """EVERY VIOLATED HARD ROW OF A SOLVED SURFACE (spec §32 (4) instrument;
    promoted from scout ``v2unsettled2``'s ``hardrows.py`` on its second use).

    ``HARD SET NOT SETTLED`` names ONE row — its ruling, truncated.  That is
    not enough to attribute: 12u spent a scout re-deriving the population by
    hand, and 13ac needed the row's VERTICES and their lat/lon to see that
    main's worst row was a pair the zone projection had clamped
    independently.  This prints the whole violated set: generator, ruling,
    demanded vs allowed metres, and per vertex the id, coefficient, solved z,
    DEM, lat/lon and the roles touching it.

    It re-assembles the design problem from ``(pm, cs, law)`` — the same
    ``solve.design.assemble`` the solve runs — and applies design.py's own
    row scaling (``2 / Σ|c|``, so every violation reads in METRES of surface,
    the units ``hard_tol_m`` is stated in).  Read-only: no solve, no write.

    ``stage=1`` reads §20b STAGE 1's OWN ASSEMBLY instead of the full
    problem (``solve.design.stage_split``'s drop + fixed): the AIRSIDE hard
    set, in the same rows and the same metre scaling stage 1 enforced them
    under.  The full read cannot answer this — the airside rows are a
    subset of 325k whose scaling and population the stage's own drop
    changes — and "the airside solve does not settle" (RULINGS 13y (B) /
    13ab / 14as) is a claim about exactly that set (lane ``v2settle``).
    """
    from auto_patch_v2.law.tables import design as design_law
    from auto_patch_v2.solve.design import assemble, stage_split
    from auto_patch_v2.solve.design_report import DesignReport, hard_exceeds
    if stage == 1:
        drop, fixed = stage_split(pm, cs, law)
        base = assemble(pm, cs, law, DesignReport(), drop=drop, fixed=fixed)
    elif stage is not None:
        raise SystemExit(f"--why-hard-stage {stage}: only stage 1 is readable "
                         "off a shipped surface (stage 2 IS the full problem "
                         "with airside substituted, which the full read gives)")
    else:
        base = assemble(pm, cs, law, DesignReport())
    tol = float(design_law(law).hard_tol_m)
    rows = []
    for k in sorted(base.hard):
        terms, bound, row = base.one[k]
        s = sum(abs(c) for _v, c in terms)
        sc = 2.0 / s if s > 0 else 1.0
        val = sum(c * float(z[v]) for v, c in terms)
        v = (val - float(bound)) * sc
        # ONE settle derivation with the report (``design_report.hard_exceeds``):
        # the runway projection lands its own rows AT the bar, and a strict
        # ``>`` on a 2e-14 m solver residual reported 6 HELD runway rows as
        # violations (lane ``v2settle``).
        if hard_exceeds(v, tol):
            rows.append((v, k, terms, float(bound), val, row))
    rows.sort(key=lambda r: -r[0])
    by_gen: dict[str, int] = {}
    for v, _k, _t, _b, _val, row in rows:
        by_gen[row.source.generator] = by_gen.get(row.source.generator, 0) + 1
    tag = "why-hard" if stage is None else f"why-hard stage {stage}"
    out(f"[{icao}] {tag}: {len(rows)} / {len(base.hard)} hard rows violated over "
        f"hard_tol_m {tol} m"
        + (f"; worst {rows[0][0]:.6f} m" if rows else " — HARD SET SETTLED"))
    if by_gen:
        out("    by generator: " + ", ".join(f"{k} {n}" for k, n in
                                             sorted(by_gen.items(), key=lambda kv: -kv[1])))
    recs = []
    for v, k, terms, bound, val, row in rows[:limit]:
        out(f"--- row {k}  violation {v:.4f} m  gen={row.source.generator}")
        out(f"    ruling: {row.source.ruling[:160]}")
        out(f"    demanded {val:.4f} vs allowed {bound:.4f} (raw {val - bound:+.4f})")
        vs = []
        for vid, c in terms:
            key = pm.vertices[vid].key
            roles = sorted({pm.faces[f].role for f in pm.vertices[vid].incident_faces})
            out(f"      v{vid} c={c:+.6f} z={float(z[vid]):.4f} dem={pm.vertices[vid].dem_z} "
                f"ll={key[0]},{key[1]} roles={roles}")
            vs.append({"v": vid, "c": c, "z": round(float(z[vid]), 4),
                       "dem": pm.vertices[vid].dem_z, "lat": key[0], "lon": key[1],
                       "roles": roles})
        recs.append({"row": k, "violation_m": round(v, 6),
                     "generator": row.source.generator, "ruling": row.source.ruling,
                     "demanded": round(val, 6), "allowed": round(bound, 6),
                     "vertices": vs})
    return {"icao": icao, "stage": stage,
            "hard_rows": len(base.hard), "violated": len(rows),
            "hard_tol_m": tol, "settled": not rows,
            "worst_m": round(rows[0][0], 6) if rows else 0.0,
            "by_generator": by_gen, "rows": recs}


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


def emit_patch(icao, pm, law, airport, cs, sol, emit_dir: Path) -> dict:
    """THE BUILD'S EMIT HALF on a replay arm (``pipeline/build.py:780-795``):
    the graded surface, THE BANK (``emit/bank.with_bank``), the terrain-edge
    ways and the patch — so a same-frame divergence
    (``tools/patch_proximity_diff.py``, ``tools/osm_site.py``) can be read
    off a replay instead of a 6-minute build.  No rebake plan, no tile
    pieces.

    THE BANK WAS MISSING HERE until 2026-09-13 (lane ``v2zonebank``): the
    replay wrote the patch straight out of ``graded_surface``, so every
    ``bank_foot`` question asked of a replay arm read ZERO feet and looked
    like the defect under attribution."""
    from auto_patch_v2.emit.bank import BankReport, with_bank
    from auto_patch_v2.emit.graded import graded_surface
    from auto_patch_v2.emit.osm_adapter import write_patch
    from auto_patch_v2.emit.terrain_edge import with_terrain_edges
    from auto_patch_v2.pipeline.publication import face_tags, publication
    t = time.perf_counter()
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs,
                          {"law_ruleset": law.ruleset_key, "pack": airport.pack.name})
    brep = BankReport()
    surf_out = with_bank(surf, pm, law, airport, brep)
    surf_out = with_terrain_edges(surf_out, pm, law)
    print("    " + brep.line(icao))
    pub = publication(pm, law, airport, sol.z, cs)
    header = {"o4_apt_dat": airport.pack.apt_dat_path, "o4_pack": airport.pack.name,
              "o4_replay": "v2_solve_replay"}
    paths = write_patch(surf_out, law, emit_dir, pub, header, face_tags(pm, law, airport))
    print(f"    emitted {paths.patch} ({paths.ways} ways, {paths.nodes} nodes) in "
          f"{time.perf_counter() - t:.1f} s")
    return {"patch": str(paths.patch), "bank": _dc.asdict(brep),
            "surface": surf_out}


def bank_walk(icao, pm, law, airport, surf_out, out=print) -> dict:
    """§37 (3) THE ZONE-2 WALK (owner RULINGS 2026-09-13bu): per
    ``adjacent_ground:*:zone2`` face ring, ``|z_ring − DEM(foot)|`` at every
    station — the drop the law measures load-bearing against — with the
    stations at or over ``bank_materiality_m``, whether the station's foot
    point stands OUTSIDE the design coverage at all (only those can carry a
    bank), whether it falls in the terrain-edge no-bank region or the water
    cut, and how many emitted ``bank_foot`` vertices lie within reach of the
    ring.  Prices no law and counts no defects: every number is read off the
    map, the DEM and the emitted surface."""
    import numpy as np
    from shapely.geometry import Point, Polygon
    from auto_patch_v2.emit.bank import (BANK_KIND, _dem_many, _outward_normals,
                                         bank_materiality_m, coverage_polygon)
    from auto_patch_v2.emit.terrain_edge import no_bank_region
    d_law = law.tables.emit.design
    mat = bank_materiality_m(d_law)
    min_w = float(d_law.bank_min_width_m)
    reach = float(d_law.bank_max_width_m)
    slope = float(d_law.bank_slope)
    dem = getattr(airport, "dem", None)
    cov = coverage_polygon(pm)
    if dem is None or cov is None:
        return {}
    edge_geom = no_bank_region(pm, law, cov)
    water_geom = None
    wf = getattr(dem, "water_geometry", None)
    if callable(wf):
        try:
            bx0, by0, bx1, by1 = cov.bounds
            water_geom = wf((bx0 - reach, by0 - reach, bx1 + reach, by1 + reach))
        except Exception:
            water_geom = None
        if water_geom is not None and water_geom.is_empty:
            water_geom = None
    z_of = {v.id: v.z for v in surf_out.vertices}
    feet = [(v.id, v.ll) for v in surf_out.vertices]
    foot_ids: set[int] = set()
    for b in surf_out.breaklines:
        if b.kind == BANK_KIND:
            foot_ids.update(b.vertices)
    _to_xy = airport.frame.transformers()[0]
    fpts = []
    for vid, ll in feet:
        if vid in foot_ids:
            fpts.append(_to_xy(ll[1], ll[0]))   # to_xy(lon, lat)
    tree = None
    if fpts:
        from scipy.spatial import cKDTree
        tree = cKDTree(np.asarray(fpts, float))
    rows = []
    for fid, f in sorted(pm.faces.items()):
        ref = f.ref or ""
        if ":zone2" not in ref:
            continue
        ring = [pm.vertices[v].xy for v in pm.ring_vertices(f.ring)]
        vids = list(pm.ring_vertices(f.ring))
        if len(ring) < 3:
            continue
        nrm = np.asarray(_outward_normals(ring), float)
        pts = np.asarray(ring, float)
        fx = pts[:, 0] + nrm[:, 0] * min_w
        fy = pts[:, 1] + nrm[:, 1] * min_w
        zdem = _dem_many(dem, fx, fy)
        zr = np.asarray([z_of.get(v, float("nan")) for v in vids], float)
        drop = np.abs(zr - zdem)
        outside = np.asarray([not cov.contains(Point(x, y))
                              for x, y in zip(fx.tolist(), fy.tolist())])
        in_edge = np.asarray([edge_geom is not None
                              and edge_geom.contains(Point(x, y))
                              for x, y in zip(fx.tolist(), fy.tolist())])
        in_water = np.asarray([water_geom is not None
                               and water_geom.contains(Point(x, y))
                               for x, y in zip(fx.tolist(), fy.tolist())])
        # THE FOOT'S OWN REACH, per station: the 1:3 daylight distance this
        # station's drop buys plus the minimum width — never the airport-wide
        # ``bank_max_width_m``, which calls a foot 200 m away "near".
        near_foot = np.zeros(len(pts), bool)
        if tree is not None:
            dd, _ = tree.query(np.column_stack([fx, fy]))
            want = np.minimum(np.nan_to_num(drop) / slope, reach) + 2.0 * min_w
            near_foot = dd <= want
        material = np.isfinite(drop) & (drop > mat)
        bad = np.flatnonzero(material & outside & ~near_foot)
        _to_ll = airport.frame.transformers()[1]
        probe = [(float(fx[i]), float(fy[i]), *_to_ll(float(pts[i, 0]),
                                                      float(pts[i, 1])),
                  float(drop[i])) for i in bad.tolist()]
        rows.append({"_probe": probe,
            "face": fid, "ref": ref, "stations": int(len(pts)),
            "material": int(material.sum()),
            "material_outside": int((material & outside).sum()),
            "material_outside_no_foot": int((material & outside & ~near_foot).sum()),
            "in_edge_region": int((material & outside & in_edge).sum()),
            "in_water": int((material & outside & in_water).sum()),
            "max_drop_m": round(float(np.nanmax(drop)) if len(drop) else 0.0, 2),
        })
    tot = {k: sum(r[k] for r in rows) for k in
           ("stations", "material", "material_outside",
            "material_outside_no_foot", "in_edge_region", "in_water")}
    out(f"[{icao}] §37 (3) zone-2 walk: {len(rows)} zone2 ring(s), "
        f"{tot['stations']} stations, materiality {mat:.2f} m; "
        f"{tot['material']} station(s) >= materiality, of which "
        f"{tot['material_outside']} have their foot point OUTSIDE the design "
        f"coverage; {tot['material_outside_no_foot']} of those carry NO "
        f"bank_foot within their own 1:3 reach "
        f"({tot['in_edge_region']} in the terrain-edge no-bank region, "
        f"{tot['in_water']} in water)")
    worst = sorted(rows, key=lambda r: -r["material_outside_no_foot"])[:12]
    for r in worst:
        if not r["material_outside_no_foot"]:
            break
        out(f"    {r['ref']}#{r['face']}: {r['material_outside_no_foot']}/"
            f"{r['stations']} unbanked material station(s), max drop "
            f"{r['max_drop_m']:.2f} m, edge {r['in_edge_region']}, "
            f"water {r['in_water']}")
    res = {"materiality_m": mat, "totals": tot, "rings": rows,
           "unbanked": [[r["ref"], r["face"], *pr] for r in rows
                        for pr in r.get("_probe", [])]}
    for r in rows:
        r.pop("_probe", None)
    return res


def bank_from(pkl: Path, emit_dir: Path | None, walk: bool,
              json_out: Path | None) -> int:
    """THE EMIT HALF ALONE, off a ``--solved-out`` pickle: the bank stage
    replayed without re-paying the 80 s solve (lane ``v2zonebank``, §37 (3))."""
    from auto_patch_v2.law import Law
    from auto_patch_v2.solve.api import Solution, Status
    with pkl.open("rb") as fh:
        sv = pickle.load(fh)
    icao, pm, airport, cs, z = (sv["icao"], sv["pm"], sv["airport"],
                                sv["cs"], sv["z"])
    law = Law.for_airport(icao)
    sol = Solution(tuple(float(v) for v in z), Status.OPTIMAL, None)
    res: dict = {}
    surf_out = None
    if emit_dir is not None:
        r = emit_patch(icao, pm, law, airport, cs, sol, emit_dir)
        surf_out = r.pop("surface")
        res.update(r)
    if walk:
        from auto_patch_v2.emit.bank import BankReport, with_bank
        from auto_patch_v2.emit.graded import graded_surface
        surf = graded_surface(pm, law, sol, airport.frame.origin,
                              airport.frame.crs, {})
        brep = BankReport()
        surf_out = with_bank(surf, pm, law, airport, brep)
        print("    " + brep.line(icao))
        res["bank"] = _dc.asdict(brep)
        res["zone2_walk"] = bank_walk(icao, pm, law, airport, surf_out)
    if json_out is not None:
        json_out.write_text(json.dumps(res, indent=1, default=str))
    return 0


def stability_probe(pkl: Path, site: tuple[float, float], drop_m: float,
                    arms: list[dict], json_out: Path | None,
                    tol_m: float = 0.02) -> int:
    """§20a/§20c THE STABILITY PROBE, off a ``--solved-out`` pickle.

    Is the design surface's optimum LOCALLY STABLE?  A perturbation
    confined to one apron vertex must not move the far field.  One extra
    ``Band`` ceiling ``drop_m`` under where the ARM's own base solve put
    that vertex, re-solved, and the moved set binned by distance from it.

    Promoted (tool discipline, RULINGS ``7e90032``) from lane
    ``v2settle`` r2's ``scratchpad/v2settle/probe3.py`` / ``probe4.py``,
    which measured RULINGS 2026-09-14bw's headline at HECA — 959 vertices
    moved by one 0.30 m row, 953 of them beyond 500 m, zero within 100 m —
    on its SECOND use, by lane ``v2qp`` measuring §20c's own bar.  Each
    ``arms`` entry is a ``[design]`` override dict, so the pair
    ``{"solver": "fixed_point"}`` / ``{"solver": "qp"}`` is one run.
    """
    import dataclasses as _dcl

    import numpy as np
    from auto_patch_v2.law import Law
    from auto_patch_v2.model.constraints import Band, Source
    from auto_patch_v2.solve.design import solve_design

    with pkl.open("rb") as fh:
        sv = pickle.load(fh)
    icao, pm, airport, cs = sv["icao"], sv["pm"], sv["airport"], sv["cs"]
    law0 = Law.for_airport(icao)
    to_xy, _from = airport.frame.transformers()
    sx, sy = to_xy(site[1], site[0])
    n = len(pm.vertices)
    xy = np.array([pm.vertices[i].xy for i in range(n)], float)
    vid = int(np.argmin(np.hypot(xy[:, 0] - sx, xy[:, 1] - sy)))
    dist = np.hypot(xy[:, 0] - xy[vid, 0], xy[:, 1] - xy[vid, 1])
    print(f"[{icao}] probe v{vid} at {pm.vertices[vid].key}, "
          f"{float(np.hypot(xy[vid,0]-sx, xy[vid,1]-sy)):.1f} m from the site; "
          f"ceiling {drop_m:g} m under its own base surface", flush=True)
    out: dict = {"icao": icao, "vertex": vid, "site": list(site),
                 "drop_m": drop_m, "arms": []}
    for over in arms:
        d0 = law0.tables.emit.design
        law = _dc.replace(law0, tables=_dc.replace(
            law0.tables, emit=_dc.replace(law0.tables.emit,
                                          design=_dc.replace(d0, **over))))
        t = time.perf_counter()
        sol0, rep0 = solve_design(pm, cs, law)
        w0 = time.perf_counter() - t
        z0 = np.asarray(sol0.z, float)
        src = Source("stability_probe", "§20a/§20c stability probe", ())
        cs2 = _dcl.replace(cs, bands=tuple(cs.bands)
                           + (Band(vid, None, float(z0[vid]) - drop_m, src),))
        t = time.perf_counter()
        sol1, rep1 = solve_design(pm, cs2, law)
        w1 = time.perf_counter() - t
        dz = np.abs(np.asarray(sol1.z, float) - z0)
        moved = dz > tol_m
        bins = {}
        for lo, hi in ((0, 40), (40, 100), (100, 250), (250, 500), (500, 10 ** 9)):
            bins[f"{lo}-{hi:g}"] = int((moved & (dist >= lo) & (dist < hi)).sum())
        far = moved & (dist >= 250.0)
        rec = {"arm": over, "moved": int(moved.sum()), "of": n,
               "max_m": round(float(dz.max()), 4), "bins": bins,
               "beyond_100m": int((moved & (dist >= 100)).sum()),
               "beyond_250m": int(far.sum()),
               "beyond_500m": int((moved & (dist >= 500)).sum()),
               "worst_beyond_250m": round(float(dz[far].max()) if far.any() else 0.0, 4),
               "base_wall_s": round(w0, 1), "pert_wall_s": round(w1, 1),
               "base_hard": [rep0.hard_active, rep0.hard_rows,
                             round(rep0.hard_max_violation_m, 4), rep0.hard_settled],
               "pert_hard": [rep1.hard_active, rep1.hard_rows,
                             round(rep1.hard_max_violation_m, 4), rep1.hard_settled],
               "base_exit": rep0.set_exit_line() or rep0.qp_line(),
               "pert_exit": rep1.set_exit_line() or rep1.qp_line()}
        out["arms"].append(rec)
        print(f"  {over}: moved>{tol_m:g} {rec['moved']}/{n} max {rec['max_m']} m; "
              f"beyond 100 m {rec['beyond_100m']}, 250 m {rec['beyond_250m']} "
              f"(worst {rec['worst_beyond_250m']} m), 500 m {rec['beyond_500m']}; "
              f"bins {bins}; base {rec['base_wall_s']} s / pert "
              f"{rec['pert_wall_s']} s; hard {rec['base_hard']} -> {rec['pert_hard']}",
              flush=True)
        print(f"     base [{rec['base_exit']}]\n     pert [{rec['pert_exit']}]",
              flush=True)
    if json_out is not None:
        json_out.write_text(json.dumps(out, indent=1, default=str))
    return 0


def replay(pkl: Path, resume: str, drop: list[str], json_out: Path | None,
           z_out: Path | None, method: str = "normal",
           design_weights: dict[str, float] | None = None, verbose: bool = False,
           sites: list[tuple[float, float]] | None = None, emit_dir: Path | None = None,
           why_hump: tuple[str, float, float] | None = None, verify: bool = False,
           solved_out: Path | None = None, chord_fill: tuple[str, ...] = (),
           site_radius_m: float = 12.0, why_hard_limit: int | None = None,
           why_hard_stage: int | None = None) -> int:
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
    # A CAPTURE PREDATING A TARGET CHANNEL REPLAYS WITH THAT CHANNEL
    # EMPTY, and says which (lane ``v2roadcontact``, §37 (10)).  A
    # ``PlanarMap`` field added since the pickle was written is simply
    # ABSENT on the unpickled instance, so the first ``dataclasses.replace``
    # raises ``AttributeError`` and a REGISTERED FRAME another lane shares
    # becomes unreplayable for a channel its own stage never produced.
    # The publisher derives the channel in the replay anyway; the backfill
    # is the dataclass's OWN default, and every field it fills is named.
    missing = [f for f in _dc.fields(type(pm)) if not hasattr(pm, f.name)]
    for f in missing:
        d = (f.default_factory() if f.default_factory is not _dc.MISSING
             else f.default)
        object.__setattr__(pm, f.name, None if d is _dc.MISSING else d)
    if missing:
        print(f"[{icao}] capture predates {len(missing)} PlanarMap channel(s), "
              f"backfilled at their defaults: {', '.join(f.name for f in missing)}")
    law = Law.for_airport(icao)
    # A CAPTURE PREDATING THE CLUSTERS derives them HERE, off its own
    # partition, and says so — the same "the publisher derives the
    # channel in the replay anyway" rule as the PlanarMap backfill above.
    # A replay whose ``Airport.clusters`` is empty solves the pads-OFF
    # problem however the law values are set (§30 (4) / §16g (10)).
    if not (getattr(airport, "clusters", None) or ()):
        from auto_patch_v2.planar.cluster import clusters as _derive_clusters
        _ct = time.perf_counter()
        airport = _dc.replace(airport, clusters=_derive_clusters(airport, law))
        print(f"[{icao}] capture predates Airport.clusters — derived "
              f"{len(airport.clusters)} off its own partition "
              f"({time.perf_counter() - _ct:.0f} s)")
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
                        ("apron_trend", "with_apron_trend"),
                        ("eat", "withdraw_trend_over_reach")):
            # THE EAT RAMP REACH IS A CHANNEL EDIT, NOT A ROW (spec
            # §36 (5)): it WITHDRAWS trend targets before the solve, so
            # ``--drop-generator`` cannot reach it the way it reaches a
            # generator's rows.  ``eat_anchor_rect`` drops the whole law
            # (the pins AND their reach — a reach without its pin is not
            # a state the build can be in); ``eat_ramp_reach`` drops the
            # withdrawal ALONE, which is the §36 (5) before-arm.
            if mod == "eat" and ({"eat_anchor_rect", "eat_ramp_reach"} & set(drop)):
                continue
            try:
                pub = getattr(__import__(f"auto_patch_v2.constraints.{mod}",
                                         fromlist=[fn]), fn)
            except (ImportError, AttributeError):
                continue
            m = pub(m, law, airport)
        # §37 (6) LAST, and out of the loop because its DERIVATION is an
        # M1 producer's (it reads the DEM along the road's own route):
        # the ramp reads the airside's own published target at the mouth
        # and supersedes the core's road fit for the vertices it governs.
        try:
            from auto_patch_v2.airport.road_ramp import with_road_ramp
        except ImportError:
            return m
        m = with_road_ramp(m, law, airport)
        # §37 (9) the coverage-edge join, after the frame it reads
        try:
            from auto_patch_v2.airport.road_profile import core_profiles
            from auto_patch_v2.emit.road_join import with_road_coverage_join
        except ImportError:
            return m
        prof, per_face = core_profiles(airport, m, law)
        return with_road_coverage_join(m, law, prof)

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
            from auto_patch_v2.verify.census import (DEFECT_KEYS, defect_gate,
                                                      under_floor_text)
            t = time.perf_counter()
            surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs,
                                  {"law_ruleset": law.ruleset_key, "pack": airport.pack.name})
            vrows = run_census(surf, law, publication(pm, law, airport, sol.z, cs),
                               road_law_caps(pm, law, airport))
            summary = {k: len(v) for k, v in vrows.items() if v}
            # ONE READING OF THE GATE (RULINGS 2026-09-14bx): the same
            # ``defect_gate`` the build and the app driver use — a row under
            # the materiality floor is a census violation, never an abort
            _defects, _under = defect_gate(law, vrows)
            result["verify"] = {"by_family": summary, "defects": _defects,
                                "defects_under_floor": _under}
            print(f"    verify {time.perf_counter() - t:.1f} s: {sum(summary.values())} rows  "
                  + ", ".join(f"{k} {n}" for k, n in sorted(summary.items())))
            print(f"    verify DEFECT families ({', '.join(DEFECT_KEYS)}): "
                  + (", ".join(f"{k} {n}" for k, n in result["verify"]["defects"].items())
                     or "ALL ZERO"))
            if _under:
                print(f"      {under_floor_text(_under)} — a census violation, "
                      "not an abort (RULINGS 2026-09-14bx)")
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
        if why_hard_limit is not None:
            result["why_hard"] = why_hard(icao, pm, law, cs, z, why_hard_limit,
                                          stage=why_hard_stage)
        if why_hump is not None:
            result["why_hump"] = _why_hump(icao, pm, law, airport, cs, z, *why_hump)
        if z_out is not None:
            np.save(z_out, z)
        if emit_dir is not None:
            result.update(emit_patch(icao, pm, law, airport, cs, sol, emit_dir))
    if json_out is not None:
        json_out.write_text(json.dumps(result, indent=1, default=str))
    return 0


def _design_value(v: str):
    """One ``--design-weight TERM=V`` value.  Every ``[design]`` term was a
    NUMBER until §20c added ``solver = "fixed_point" | "qp"`` (RULINGS
    2026-09-14bw), so a value that does not parse as a float is passed to
    ``dataclasses.replace`` as the string it is — which is how an arm says
    ``--design-weight solver=qp``."""
    try:
        return float(v)
    except ValueError:
        return v.strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--capture", metavar="ICAO")
    ap.add_argument("--mod-cache-root", metavar="DIR",
                    help="Airport_mod_cache root for the capture (the harness's "
                         "lane-local copy-on-write overlay); default: the engine "
                         "tree's mount")
    ap.add_argument("--placement", action="append", default=[], metavar="KEY=V",
                    help="CAPTURE ARM: override one [placement] law key for this "
                         "capture (repeat).  The §16g (10) pad keys are read in "
                         "classify/planar — upstream of the capture — so a replay "
                         "override cannot arm them; e.g. "
                         "--placement pad_from_cluster=true "
                         "--placement pad_airside_clip=true")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--replay", type=Path, metavar="PKL")
    ap.add_argument("--from", dest="resume", choices=("constraints", "shapes", "planar"),
                    default="constraints")
    ap.add_argument("--drop-generator", action="append", default=[])
    ap.add_argument("--json", type=Path)
    ap.add_argument("--z-out", type=Path)
    ap.add_argument("--design-weight", action="append", default=[], metavar="TERM=V",
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
    ap.add_argument("--why-at", metavar="LAT,LON",
                    help="why on the WORST vertex (max |z - DEM|) within --site-radius "
                         "of this coordinate — the owner's own frame for naming a site, "
                         "so a report does not have to translate a coordinate into a "
                         "vertex id by hand (lane v2roadcap2)")


    ap.add_argument("--why-hard", nargs="?", type=int, const=40, default=None, metavar="N",
                    help="list EVERY violated hard row of the solved surface (spec §32 (4)): "
                         "generator, ruling, demanded vs allowed metres, and per vertex the "
                         "id, coefficient, z, DEM, lat/lon and roles; N caps the printed rows "
                         "(default 40, the counts and the JSON cover them all).  Works on a "
                         "--replay arm and on a --why-from PKL")
    ap.add_argument("--why-hard-stage", type=int, default=None, metavar="N",
                    help="read §20b STAGE N's own hard set instead of the full "
                         "problem's (N=1: the AIRSIDE problem alone, the set "
                         "RULINGS 13y (B)/13ab/14as call unsettled)")
    ap.add_argument("--why-relax", nargs="+", default=[], metavar="FAMILY",
                    help="relax-one-family arms (solve.why family labels) over the hump's ridge vertices")
    ap.add_argument("--why-hump", nargs=3, metavar=("RUNWAY", "S0", "S1"),
                    help="why on the highest ridge vertex above the chord in stations S0..S1")
    ap.add_argument("--bank-from", type=Path, metavar="PKL",
                    help="replay the EMIT HALF (bank + terrain edges + patch) off a "
                         "--solved-out pickle, without re-paying the solve")
    ap.add_argument("--bank-walk", action="store_true",
                    help="§37 (3): the per-station adjacent-ground zone-2 walk "
                         "(|z_ring - DEM(foot)| and the feet emitted)")
    ap.add_argument("--probe-site", metavar="LAT,LON",
                    help="§20a/§20c THE STABILITY PROBE off a --solved-out "
                         "pickle (--why-from): one extra ceiling row --probe-drop "
                         "under the base surface at the vertex nearest this point, "
                         "re-solved, the moved set binned by distance")
    ap.add_argument("--probe-drop", type=float, default=0.30, metavar="M",
                    help="the probe's ceiling, metres under the base surface (default 0.30)")
    ap.add_argument("--probe-arm", action="append", default=[], metavar="TERM=V",
                    help="one probe ARM as a [design] override; repeat for a "
                         "matched pair (e.g. --probe-arm solver=fixed_point "
                         "--probe-arm solver=qp).  Default: the shipped law alone")
    a = ap.parse_args()
    if a.probe_site:
        if not a.why_from:
            ap.error("--probe-site needs --why-from PKL (a --solved-out pickle)")
        lat, lon = (float(v) for v in a.probe_site.split(","))
        arms = ([{k.strip(): _design_value(v)}
                 for k, v in (it.split("=") for it in a.probe_arm)]
                if a.probe_arm else [{}])
        return stability_probe(a.why_from, (lat, lon), a.probe_drop, arms, a.json)
    if a.bank_from:
        return bank_from(a.bank_from, a.emit, a.bank_walk, a.json)
    if a.capture:
        if a.out is None:
            ap.error("--capture needs --out")
        pl = dict(it.split("=", 1) for it in a.placement)
        _capture_guarded(a.capture.upper(), a.out, a.mod_cache_root, pl)
        return 0
    if a.why_from:
        from auto_patch_v2.law import Law
        with a.why_from.open("rb") as fh:
            sv = pickle.load(fh)
        law = Law.for_airport(sv["icao"])
        if a.why_hard is not None:
            res = why_hard(sv["icao"], sv["pm"], law, sv["cs"], sv["z"], a.why_hard,
                           stage=a.why_hard_stage)
            if a.json:
                a.json.write_text(json.dumps(res, indent=1, default=str))
            return 0
        wh = (a.why_hump[0], float(a.why_hump[1]), float(a.why_hump[2])) if a.why_hump else ("", 0.0, 0.0)
        vertex = a.why_vertex
        if a.why_at:
            vertex = _worst_vertex_at(sv["pm"], sv["airport"], sv["z"],
                                      tuple(float(x) for x in a.why_at.split(",")),
                                      a.site_radius)
            if vertex is None:
                print(f"[{sv['icao']}] --why-at {a.why_at}: no vertex within "
                      f"{a.site_radius:g} m")
                return 1
        res = _why_hump(sv["icao"], sv["pm"], law, sv["airport"], sv["cs"], sv["z"], *wh,
                        relax=a.why_relax, vertex=vertex)
        if a.json:
            a.json.write_text(json.dumps(res, indent=1, default=str))
        return 0
    if a.replay:
        sites = [tuple(float(x) for x in it.split(",")) for it in a.site]
        wh = (a.why_hump[0], float(a.why_hump[1]), float(a.why_hump[2])) if a.why_hump else None
        return replay(a.replay, a.resume, a.drop_generator, a.json, a.z_out,
                      method=a.method,
                      design_weights={k.strip(): _design_value(v)
                                      for k, v in (it.split("=") for it in a.design_weight)},
                      verbose=a.design_verbose, sites=sites, site_radius_m=a.site_radius,
                      emit_dir=a.emit, why_hump=wh, verify=a.verify, solved_out=a.solved_out,
                      chord_fill=tuple(a.chord_fill), why_hard_limit=a.why_hard,
                      why_hard_stage=a.why_hard_stage)
    ap.error("one of --capture / --replay")
    return 2


if __name__ == "__main__":
    sys.exit(main())
