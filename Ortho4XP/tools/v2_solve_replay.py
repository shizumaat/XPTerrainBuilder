#!/usr/bin/env python3
"""THE v2 SOLVE REPLAY — capture one airport's v2 pipeline product at the
territory stage ONCE, then re-run the constraint generators and the solve
under the CURRENT tree as often as a change needs, without paying for the
load / classify / planar stages again (the synthetic-first solve-arm
pattern of ``docs/specs/auto-patch-v2/heca-sag-ablation/ablate_heca_pin.py``,
promoted on its second use by lane ``v2chord``).

    venv/bin/python tools/v2_solve_replay.py --capture ICAO --out DIR/ICAO.pkl
    venv/bin/python tools/v2_solve_replay.py --replay DIR/ICAO.pkl [--from constraints|shapes|planar|classify]
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
import re as _re
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
                     placement: dict[str, object] | None = None,
                     rule: dict[str, object] | None = None) -> None:
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
        capture(icao, out, mod_cache_root, placement, rule)
    finally:
        _guard.__exit__(None, None, None)
        _churn(_guard)
        print("[guard]", "shared repo UNCHANGED" if not _guard.blocked
              else f"BLOCKED {_guard.blocked}", flush=True)


def _rules_override(rules, over: dict[str, object]):
    """Return ``rules`` with ``classify/rules.toml`` keys replaced (the
    CAPTURE arm), as :func:`_placement_override` does for ``[placement]``.

    A CLASSIFY-stage key is read UPSTREAM of the capture — the capture
    holds the classification — so no replay-time override can arm one and
    a matched pair on a classify law has to be two CAPTURES.  Doing that
    by EDITING the shipped toml between the arms is exactly the defect
    RULINGS 2026-09-15az records (disarming a head by prefix also deleted
    ``foot_row_rulings`` and silently re-priced every foot row); this makes
    the arm ONE command-line variable instead, on one unedited tree.
    ``SECTION.KEY=VALUE``, e.g. ``--rule corridor.runway_shoulder_band=false``
    (lane ``v2shoulderband``, §40 (5))."""
    import dataclasses as _d
    for spec, v in over.items():
        if "." not in spec:
            raise SystemExit(f"--rule: expected SECTION.KEY=VALUE, got {spec!r}")
        sec, key = spec.split(".", 1)
        if not hasattr(rules, sec):
            raise SystemExit(f"--rule: no such rules section {sec!r}")
        node = getattr(rules, sec)
        if not any(f.name == key for f in _d.fields(node)):
            raise SystemExit(f"--rule: no such [{sec}] key {key!r}")
        cur = getattr(node, key)
        if isinstance(cur, bool):
            val: object = str(v).strip().lower() in ("1", "true", "yes", "on")
        elif isinstance(cur, (int, float)):
            val = type(cur)(v)
        elif isinstance(cur, (tuple, list)):
            # a list key (``surfaces.graded_codes=1,2,3,15``): comma-
            # separated, each element typed like the shipped first one
            # (lane ``nlwf``, the transparent-apron arm)
            elem = type(cur[0]) if cur else str
            val = type(cur)(elem(t.strip()) for t in str(v).split(",")
                            if t.strip())
        else:
            val = v
        rules = _dc.replace(rules, **{sec: _dc.replace(node, **{key: val})})
    return rules


def capture(icao: str, out: Path, mod_cache_root: str | None = None,
            placement: dict[str, object] | None = None,
            rule: dict[str, object] | None = None) -> None:
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
    _rules = load_rules()
    if rule:
        _rules = _rules_override(_rules, rule)
        print(f"[{icao}] CAPTURE ARM [rules] {rule}")
    cl = classify(airport, law, _rules, cache=ocache)
    objects_out: list = []
    pm, _pstats = build_planar(airport, cl, law, objects_out=objects_out, cache=ocache,
                               objects=pack_objects, object_report=pack_report)
    # §37 (11) (4) (owner RULINGS 2026-09-15f item 2): the airport's OWN
    # classified surfaces are LAND, so the datum region's water cut cannot
    # call a reclaimed apron sea.  ONE derivation
    # (``pipeline/build._classified_land``), read here too — without it a
    # replay solves a DIFFERENT problem from the build (measured at VMMC:
    # pav5 1.95 m against the build's 5.09, within_shape 327 against 2).
    from auto_patch_v2.pipeline.build import _classified_land
    fv = _flat.detect(airport, law, objects=objects_out[0] if objects_out else (),
                      land=_classified_land(cl))
    airport = _dc.replace(airport, flat_site=fv)
    road_pref, _rep, _p = preferred_road_z(airport, pm, law, inputs.road_grade_limit,
                                           inputs.lane_width_m)
    pm = _dc.replace(pm, preferred_z=road_pref)
    stage = shape_stage(pm, law, airport, cl)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as fh:
        # §16g (10) (12) (2) (RULINGS 2026-09-16b): the ARRANGEMENT's own
        # reading of what its pad stage did to the airside vertex set
        # travels WITH the capture.  It is produced in ``build_planar``
        # and lives in a module global, so a replay that did not run the
        # arrangement has none — and ``pipeline/publication`` then OMITS
        # the sidecar key rather than publishing an empty list, which
        # would make every replay arm read a perfect
        # ``pad_airside_renode``.  Carrying it here is what lets a
        # matched replay PAIR be adjudicated on that family at all.
        from auto_patch_v2.planar.overlay import PAD_AIRSIDE
        pickle.dump({"icao": icao, "airport": airport, "cl": cl, "pm": pm, "stage": stage,
                     "inputs": inputs, "placement": dict(placement or {}),
                     "pad_airside": dict(PAD_AIRSIDE)}, fh)
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


def emit_patch(icao, pm, law, airport, cs, sol, emit_dir: Path, strips=None,
               strip_rep=None) -> dict:
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
    pub = publication(pm, law, airport, sol.z, cs, strips=strips,
                      strip_rep=strip_rep)
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


def reclassify(pkl: Path, rule: dict[str, object],
               json_out: Path | None, top: int = 12) -> int:
    """THE §40 SHOULDER-BAND READING, DRY, OFF A REGISTERED CAPTURE
    (lane ``v2shoulderband`` r2; promoted on its second use per RULINGS
    ``7e90032`` — r1 hand-rolled it in a scratchpad for the HECA control
    and r2 needs it at five airports).

    A CLASSIFY law key cannot be armed at replay (the capture HOLDS the
    classification, which is why ``--rule`` is a CAPTURE arm), but the
    capture also carries the ``Airport`` the classifier ran on — so the
    CLASSIFY STAGE ALONE can be re-run over it on the CURRENT tree with
    the law key as the only variable, at seconds instead of a capture's
    minutes.  That is a DRY read and says so: it re-runs no planar build,
    no solve and no emit, so it prices no law and counts no defects
    (defect counts come from ``harness/census.py`` and nowhere else) and
    it cannot answer anything downstream of classify.  What it answers is
    exactly §40 (5)'s own table:

    * the ``runway_shoulder`` population — cells and m², each named;
    * what the band KEPT and what the remainder earned, by role;
    * the worst lateral offset of a runway-family cell vertex off its own
      runway's apt.dat axis, and how many stand beyond the strip half
      width (§40 (5) (1)'s own bar, "→ 0");
    * the classifier's own ``shoulder_band_*`` stats.

    The axis and the half width are the DERIVATION's own
    (``classify/roles.shoulder_band``), imported and never re-spelled.
    """
    from auto_patch_v2.classify import classify, load_rules
    from auto_patch_v2.classify.roles import shoulder_band
    from auto_patch_v2.law import Law
    from auto_patch_v2.law.tables import zone2_half_width_m
    from shapely.geometry import Point, Polygon

    with pkl.open("rb") as fh:
        cap = pickle.load(fh)
    icao, airport = cap["icao"], cap["airport"]
    law = Law.for_airport(icao)
    rules = load_rules()
    if rule:
        rules = _rules_override(rules, rule)
    print(f"[{icao}] RECLASSIFY ARM [rules] {rule or '(shipped)'}  <- {pkl}")
    t0 = time.perf_counter()
    cl = classify(airport, law, rules)
    print(f"[{icao}] classify {time.perf_counter() - t0:.1f} s, "
          f"{len(cl.cells)} cells")

    rw_of = {rw.id: rw for rw in airport.runways}
    def _lat_off(ring, rw) -> float:
        (ax, ay), (bx, by) = rw.ends[0].xy, rw.ends[1].xy
        L = math.hypot(bx - ax, by - ay) or 1.0
        ux, uy = (bx - ax) / L, (by - ay) / L
        return max(abs(-(x - ax) * uy + (y - ay) * ux) for x, y in ring)

    sh = [c for c in cl.cells if c.kind == "runway_shoulder"]
    body = [c for c in cl.cells
            if c.role == "runway" and c.kind != "runway_shoulder"]
    rest = [c for c in cl.cells if c.evidence.get("shoulder_beyond_band")]
    def _area(c):
        return Polygon(c.ring, c.holes).area
    sh_m2 = sum(_area(c) for c in sh)
    res: dict = {
        "icao": icao, "capture": str(pkl), "rule": {k: str(v) for k, v in rule.items()},
        "cells": len(cl.cells),
        "runway_shoulder": {"cells": len(sh), "m2": sh_m2},
        "runway_body_m2": sum(_area(c) for c in body),
        "remainder": {"faces": len(rest), "m2": sum(_area(c) for c in rest)},
        "stats": {k: v for k, v in cl.stats.items() if k.startswith("shoulder_band")},
    }
    by_role: dict[str, list[float]] = {}
    for c in rest:
        by_role.setdefault(c.role, []).append(_area(c))
    res["remainder_by_role"] = {r: {"faces": len(v), "m2": sum(v)}
                                for r, v in sorted(by_role.items(),
                                                   key=lambda kv: -sum(kv[1]))}
    worst = 0.0
    beyond = 0
    cellrows = []
    for c in sh:
        rw = rw_of.get(c.ref)
        if rw is None:
            continue
        hw = zone2_half_width_m(law, "runway", c.code_number, c.code_letter) or 0.0
        off = _lat_off(c.ring, rw)
        worst = max(worst, off)
        band = shoulder_band(
            rw, law, end_cap=rules.corridor.runway_shoulder_band_end_cap)
        out_m2 = (Polygon(c.ring, c.holes).difference(band).area
                  if band is not None else 0.0)
        keep = band.buffer(0.05) if band is not None else None
        n_out = (sum(1 for x, y in c.ring if not keep.covers(Point(x, y)))
                 if keep is not None else 0)
        beyond += n_out
        cellrows.append({"ref": c.ref, "of": c.evidence.get("shoulder_of", ""),
                         "m2": _area(c), "lateral_max_m": off,
                         "strip_half_m": hw, "vertices_beyond_band": n_out,
                         "m2_outside_band": out_m2})
    cellrows.sort(key=lambda r: -r["m2"])
    res["worst_lateral_m"] = worst
    res["vertices_beyond_band"] = beyond
    res["cells_detail"] = cellrows

    print(f"[{icao}] runway_shoulder {len(sh)} cell(s) {sh_m2:,.0f} m2 "
          f"(runway BODY {res['runway_body_m2']:,.0f} m2)")
    print(f"[{icao}] remainder {len(rest)} face(s) "
          f"{res['remainder']['m2']:,.0f} m2 by role: "
          + ", ".join(f"{r} {v['faces']}/{v['m2']:,.0f}"
                      for r, v in res["remainder_by_role"].items()))
    print(f"[{icao}] worst lateral off its own axis {worst:,.1f} m; "
          f"shoulder vertices beyond the band {beyond}")
    print(f"[{icao}] stats {res['stats']}")
    for r in cellrows[:top]:
        print(f"    {r['ref']:<12} {r['m2']:>12,.0f} m2  lateral max "
              f"{r['lateral_max_m']:>8.1f} m  (strip half {r['strip_half_m']:.0f})")
    if json_out:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(res, indent=1, default=str))
        print(f"[{icao}] -> {json_out}")
    return 0


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


#: a CANONICAL vertex key, "LAT,LON" at 11 dp — the identity every
#: stage-1 dump joins on (memory ``canonical-identity-join``)
_IS_KEY = _re.compile(r"^-?\d+\.\d{11},-?\d+\.\d{11}$")


def _stage1_faces(pm, law, drop_v, stage_roles=None
                  ) -> list[tuple[str, str, float, list[str]]]:
    """The faces :func:`solve.design.assemble` triangulates for the stage —
    ITS OWN predicate, imported (``bend_roles`` + "no dropped vertex"),
    re-read here so a dump can name the sheet.  The count is asserted
    against the report's own ``triangles`` by :func:`stage1_population`, so
    a re-spelling that drifted from the assembly would fail loudly."""
    from auto_patch_v2.solve.design_roles import bend_roles
    roles = set(bend_roles(law))
    out: list[tuple[str, str, float, list[str]]] = []
    for f in pm.faces.values():
        if f.role not in roles or (stage_roles is not None
                                   and f.role not in stage_roles):
            continue
        vs = [v for ring in (f.ring, *f.holes) for v in pm.ring_vertices(ring)]
        if drop_v and any(v in drop_v for v in vs):
            continue
        ring = pm.ring_vertices(f.ring)
        area = abs(sum(pm.vertices[ring[i]].xy[0] * pm.vertices[ring[(i + 1) % len(ring)]].xy[1]
                       - pm.vertices[ring[(i + 1) % len(ring)]].xy[0] * pm.vertices[ring[i]].xy[1]
                       for i in range(len(ring)))) * 0.5
        out.append((f.role, min(_vkey(pm, v) for v in ring), area,
                    sorted({_vkey(pm, v) for v in vs})))
    return out


def _vkey(pm, vid: int) -> str:
    """A vertex's CANONICAL identity — the 11-dp lat/lon spelling that
    carries node ids across arms (memory ``canonical-identity-join``)."""
    lat, lon = pm.vertices[vid].key
    return f"{lat:.11f},{lon:.11f}"


def stage1_population(pkl: Path, drop: list[str], out: Path,
                      design_weights: dict | None = None,
                      from_capture: bool = False, resume: str = "constraints") -> int:
    """§20b (3) STAGE 1'S POPULATION, dumped off a ``--solved-out`` pickle.

    The question RULINGS 2026-09-16v asks first: *what does a pad's
    presence change in the STAGE-1 problem?*  §20b (1) made stage 1 solve
    the airside alone; it did not make stage 1's POPULATION independent of
    what stands beside it, and v2padclip r2 measured 1,544 airside vertices
    moving between the pads-OFF and pads-ON arms with EVERY pad generator
    dropped — a problem with no pad row anywhere.

    This is the reader for that: :func:`solve.design.stage_split` +
    :func:`solve.design.assemble` — the assembly the stage actually solves,
    never a re-derivation — with every row, column, sheet face and triangle
    keyed CANONICALLY (11-dp lat/lon), so two arms' dumps diff by identity.
    It solves nothing, prices no law and counts no defects.
    """
    import gzip

    from auto_patch_v2.law import Law
    from auto_patch_v2.model.constraints import ConstraintSet
    from auto_patch_v2.solve.design import assemble, stage_split
    from auto_patch_v2.solve.design_report import DesignReport
    from auto_patch_v2.solve.design_roles import (airside_stage_roles,
                                                  airside_stage_vertices,
                                                  ruling_head)
    from auto_patch_v2.solve.rows import _face_triangles
    t0 = time.perf_counter()
    if from_capture:
        # THE CAPTURE PATH runs the replay's OWN prelude (the generators
        # under the current tree), which is what a stage-1 population
        # measured against a CODE change needs; the ``--solved-out`` path
        # reads the constraint set another arm already built.
        prob = replay_problem(pkl, resume, drop, design_weights)
        icao, pm, cs, law = prob["icao"], prob["pm"], prob["cs"], prob["law"]
    else:
        with pkl.open("rb") as fh:
            sv = pickle.load(fh)
        icao, pm, cs = sv["icao"], sv["pm"], sv["cs"]
        law = Law.for_airport(icao)
        if design_weights:
            d0 = law.tables.emit.design
            law = _dc.replace(law, tables=_dc.replace(
                law.tables, emit=_dc.replace(law.tables.emit,
                                             design=_dc.replace(d0, **design_weights))))
        if drop:
            cs = ConstraintSet.from_rows([r for r in cs.rows()
                                          if r.source.generator not in drop])
    drop_v, foreign = stage_split(pm, cs, law)
    rep = DesignReport()
    s_roles = airside_stage_roles(law)          # the §20b dispatch's own arm
    base = assemble(pm, cs, law, rep, drop=drop_v, fixed=foreign,
                    stage_roles=s_roles)
    red, rows = base.red, base.rows

    # the columns, canonically: a column is the SET of vertices the
    # reduction merged into it (a rigid ``Flat`` group is one column)
    col_v: dict[int, list[str]] = {}
    for vid in range(len(pm.vertices)):
        c = int(red.col[vid])
        if c >= 0:
            col_v.setdefault(c, []).append(_vkey(pm, vid))
    col_key = {c: f"{min(vs)}#{len(vs)}" for c, vs in col_v.items()}

    # the least-squares stack, one canonical key per row
    terms_of: dict[int, list[tuple[int, float]]] = {}
    for r_, c_, v_ in zip(rows.r, rows.c, rows.v):
        terms_of.setdefault(int(r_), []).append((int(c_), float(v_)))

    def _own(o) -> tuple[str, str]:
        if isinstance(o, tuple) and o:
            tag = o[0]
            if tag == "law":
                row = o[1]
                return (f"law:{row.source.generator}",
                        f"law:{row.source.generator}:{ruling_head(row)}")
            if tag in ("bend", "taxi_trend", "chord", "road_fit",
                       "ground_datum") and isinstance(o[1], int):
                return tag, f"{tag}:{_vkey(pm, o[1])}"
            return str(tag), str(tag)
        return "other", "other"

    row_keys: list[str] = []
    for i in range(rows.n):
        cls, head = _own(rows.owner[i])
        ts = ";".join(sorted(f"{col_key[c]}*{v:.6f}" for c, v in terms_of.get(i, ())))
        row_keys.append(f"{cls}\t{head}|{ts}|{rows.b[i]:.6f}")

    # THE PER-BODY DATUM stack is kept OUT of ``rows`` (RULINGS 2026-09-09r
    # (1)) and is part of the problem all the same — the apron bodies' own
    # DEM planes, which a pad cutting a body re-fits.
    body_keys: list[str] = []
    if base.body is not None and base.body.n:
        bt: dict[int, list[tuple[int, float]]] = {}
        for r_, c_, v_ in zip(base.body.r, base.body.c, base.body.v):
            bt.setdefault(int(r_), []).append((int(c_), float(v_)))
        for i in range(base.body.n):
            cls, head = _own(base.body.owner[i])
            ts = ";".join(sorted(f"{col_key[c]}*{v:.6f}" for c, v in bt.get(i, ())))
            body_keys.append(f"body:{cls}\t{head}|{ts}|{base.body.b[i]:.6f}")

    one_keys: list[str] = []
    for terms, hi, row in base.one:
        ts = ";".join(sorted(f"{_vkey(pm, v)}*{c:.6f}" for v, c in terms))
        one_keys.append(f"{row.source.generator}\t{ruling_head(row)}|{ts}|{hi:.6f}")

    faces = _stage1_faces(pm, law, drop_v, s_roles)
    tris: list[str] = []
    # the triangulation, off the same face list the assembly uses
    role_of = {(r, k): a for r, k, a, _vs in faces}
    for f in pm.faces.values():
        key = (f.role, min(_vkey(pm, v) for v in pm.ring_vertices(f.ring)))
        if key not in role_of:
            continue
        for a, b, c in _face_triangles(pm, f.id):
            tris.append("|".join(sorted((_vkey(pm, a), _vkey(pm, b), _vkey(pm, c)))))
    if len(tris) != rep.triangles:
        raise SystemExit(f"[{icao}] REFUSED: the dump's sheet re-read {len(tris)} "
                         f"triangles against the assembly's {rep.triangles} — the "
                         f"face predicate has drifted from ``assemble``")

    air_v = airside_stage_vertices(pm, law)
    rec = {"icao": icao, "pkl": str(pkl), "drop": list(drop),
           "design_weights": dict(design_weights or {}),
           "counts": {"columns": red.n_cols, "ls_rows": rows.n,
                      "body_datum_rows": len(body_keys),
                      "one_sided_rows": len(base.one), "eq_rows": len(base.eqs),
                      "hard_rows": rep.hard_rows, "triangles": len(tris),
                      "sheet_faces": len(faces),
                      "airside_stage_vertices": len(air_v),
                      "vertices": len(pm.vertices),
                      "foreign_vertices": len(drop_v),
                      "stage_dropped_rows": rep.stage_dropped_rows},
           "cols": sorted(col_key.values()),
           "rows": row_keys, "body": body_keys, "one": one_keys, "tris": tris,
           "faces": [[r, k, round(a, 2), vs] for r, k, a, vs in faces],
           "airside_v": sorted(_vkey(pm, v) for v in air_v)}
    with gzip.open(out, "wt") as fh:
        json.dump(rec, fh)
    print(f"[{icao}] stage-1 population -> {out} ({time.perf_counter()-t0:.1f} s): "
          + ", ".join(f"{k} {v:,}" for k, v in rec["counts"].items()))
    return 0


def stage1_diff(a: Path, b: Path, movers: Path | None, json_out: Path | None,
                top: int = 12) -> int:
    """§20b (3) (4) THE DECOMPOSITION: two :func:`stage1_population` dumps
    diffed by identity, and (with ``movers``, an
    ``airside_value_delta --json``) the airside movers attributed to the
    classes of stage-1 difference they stand on.

    It derives no law and measures no defect: every number is a set
    difference over the two arms' own assemblies."""
    import gzip
    from collections import Counter

    def _load(p: Path) -> dict:
        with gzip.open(p, "rt") as fh:
            return json.load(fh)

    A, B = _load(a), _load(b)
    out: dict = {"a": str(a), "b": str(b), "counts": {}, "classes": {}}
    print(f"STAGE-1 POPULATION, arm A {A['pkl']} vs arm B {B['pkl']} "
          f"(drop {A['drop']} / {B['drop']})")
    print(f"{'count':34s} {'A':>12s} {'B':>12s} {'B-A':>10s}")
    for k in A["counts"]:
        va, vb = A["counts"][k], B["counts"][k]
        out["counts"][k] = [va, vb]
        print(f"{k:34s} {va:12,d} {vb:12,d} {vb-va:+10,d}")

    def _diff(name: str, ka: list[str], kb: list[str]) -> dict:
        """THE THREE WAYS A ROW CAN DIFFER, kept apart because they are
        three mechanisms: a row REMOVED (its vertices or its generator are
        gone), a row ADDED, and a row RETARGETED — the same row over the
        same vertices at a different right-hand side, which is a TARGET
        the pad's presence moved (an apron body's 2-D trend fitted over a
        different body, a datum plane over a different vertex set) and
        never a row of the pad law."""
        ca, cb = Counter(ka), Counter(kb)
        gone, new = ca - cb, cb - ca
        # the STEM is the row without its right-hand side
        stem_g, stem_n = Counter(), Counter()
        for k, c in gone.items():
            stem_g[k.rsplit("|", 1)[0]] += c
        for k, c in new.items():
            stem_n[k.rsplit("|", 1)[0]] += c
        retarget = stem_g & stem_n
        rem, add = stem_g - retarget, stem_n - retarget
        by = {"retargeted": Counter(), "removed": Counter(), "added": Counter()}
        for lbl, cnt in (("retargeted", retarget), ("removed", rem), ("added", add)):
            for k, c in cnt.items():
                by[lbl][k.split("\t")[0]] += c
        print(f"\n{name}: A-only {sum(gone.values()):,}  B-only {sum(new.values()):,}"
              f"  = RETARGETED {sum(retarget.values()):,} + REMOVED "
              f"{sum(rem.values()):,} + ADDED {sum(add.values()):,}")
        for lbl in ("retargeted", "removed", "added"):
            if by[lbl]:
                print(f"  {lbl:11s}: "
                      + ", ".join(f"{k} {v:,}" for k, v in by[lbl].most_common(top)))
        return {"a_only": sum(gone.values()), "b_only": sum(new.values()),
                "retargeted": sum(retarget.values()), "removed": sum(rem.values()),
                "added": sum(add.values()),
                "by_class": {k: dict(v.most_common()) for k, v in by.items()},
                "retargeted_keys": list(retarget.elements())[:4000],
                "removed_keys": list(rem.elements())[:4000],
                "added_keys": list(add.elements())[:4000]}

    out["classes"]["ls_rows"] = _diff("LEAST-SQUARES ROWS", A["rows"], B["rows"])
    out["classes"]["body"] = _diff("PER-BODY DATUM ROWS",
                                   A.get("body", []), B.get("body", []))
    out["classes"]["one_sided"] = _diff("ONE-SIDED LAW ROWS", A["one"], B["one"])
    ca, cb = set(A["cols"]), set(B["cols"])
    out["classes"]["columns"] = {"a_only": sorted(ca - cb), "b_only": sorted(cb - ca)}
    print(f"\nCOLUMNS: A-only {len(ca-cb):,}  B-only {len(cb-ca):,}")
    for lbl, s in (("A-only", ca - cb), ("B-only", cb - ca)):
        if s:
            print(f"  {lbl}: " + ", ".join(sorted(s)[:top]))
    ta, tb = Counter(A["tris"]), Counter(B["tris"])
    out["classes"]["triangles"] = {"a_only": sum((ta - tb).values()),
                                   "b_only": sum((tb - ta).values())}
    print(f"\nTRIANGLES: A-only {sum((ta-tb).values()):,}  "
          f"B-only {sum((tb-ta).values()):,}")
    fa = {(r, k): ar for r, k, ar, *_ in A["faces"]}
    fb = {(r, k): ar for r, k, ar, *_ in B["faces"]}
    only_a = {k: v for k, v in fa.items() if k not in fb}
    only_b = {k: v for k, v in fb.items() if k not in fa}
    retri = {k: (fa[k], fb[k]) for k in set(fa) & set(fb)}
    out["classes"]["faces"] = {
        "a_only": [[r, k, v] for (r, k), v in sorted(only_a.items())],
        "b_only": [[r, k, v] for (r, k), v in sorted(only_b.items())]}
    print(f"SHEET FACES: A-only {len(only_a):,} ({sum(only_a.values()):,.0f} m2)  "
          f"B-only {len(only_b):,} ({sum(only_b.values()):,.0f} m2)")
    by_role_a, by_role_b = Counter(), Counter()
    for (r, _k), v in only_a.items():
        by_role_a[r] += 1
    for (r, _k), v in only_b.items():
        by_role_b[r] += 1
    if by_role_a:
        print("  A-only by role: " + ", ".join(f"{k} {v}" for k, v in by_role_a.most_common()))
    if by_role_b:
        print("  B-only by role: " + ", ".join(f"{k} {v}" for k, v in by_role_b.most_common()))
    # THE m2 PER CLASS: the stage-1 sheet faces carrying a vertex of a
    # changed row, by role — "how much of the airside sheet is priced on a
    # different row set because a pad stands beside it".
    def _vs_of_keys(keys: list[str]) -> set[str]:
        s: set[str] = set()
        for k in keys:
            mid = k.split("\t", 1)[-1].split("|")
            for piece in (mid[1].split(";") if len(mid) > 1 else []):
                if piece:
                    s.add(piece.split("*")[0].split("#")[0])
            s.add(mid[0].split(":")[-1])
        return {x for x in s if _IS_KEY.match(x)}

    fv_b = [(r, k, ar, set(vs)) for r, k, ar, vs in B["faces"]]
    print("\nTHE SHEET PRICED ON A DIFFERENT ROW SET (arm B faces carrying a "
          "changed row), by role:")
    per_class_m2: dict[str, dict] = {}
    for cls_name in ("removed_keys", "added_keys", "retargeted_keys"):
        vs_all: set[str] = set()
        for c in ("ls_rows", "body", "one_sided"):
            vs_all |= _vs_of_keys(out["classes"][c][cls_name])
        by_role: Counter = Counter()
        m2: Counter = Counter()
        for r, _k, ar, fvs in fv_b:
            if fvs & vs_all:
                by_role[r] += 1
                m2[r] += ar
        per_class_m2[cls_name] = {"vertices": len(vs_all),
                                  "faces": dict(by_role.most_common()),
                                  "m2": {k: round(v) for k, v in m2.most_common()}}
        print(f"  {cls_name.replace('_keys',''):11s}: {len(vs_all):,} vertices, "
              + ", ".join(f"{r} {by_role[r]} faces / {m2[r]:,.0f} m2"
                          for r, _n in m2.most_common(6)))
    out["sheet_m2"] = per_class_m2
    va, vb = set(A["airside_v"]), set(B["airside_v"])
    print(f"AIRSIDE STAGE VERTICES: A {len(va):,} B {len(vb):,}; "
          f"A-only {len(va-vb):,} B-only {len(vb-va):,}")
    out["classes"]["airside_vertices"] = {"a_only": sorted(va - vb)[:200],
                                          "b_only": sorted(vb - va)[:200],
                                          "n_a_only": len(va - vb),
                                          "n_b_only": len(vb - va)}

    if movers is not None:
        mv = json.loads(movers.read_text())
        rows_ = [m for m in mv["frames"]["solve-owned"]["moved"]
                 if "building" not in m["roles"]]
        touched: dict[str, set[str]] = {}

        def _vs_of(keys: list[str], kind: str = "row") -> set[str]:
            """The canonical vertex keys a row key names — its terms, plus
            the vertex in a per-vertex owner tag (``bend:LAT,LON``)."""
            s: set[str] = set()
            for k in keys:
                body = k.split("\t", 1)[-1]
                mid = body.split("|")
                head = mid[0]
                for piece in (mid[1].split(";") if len(mid) > 1 else []):
                    if piece:
                        s.add(piece.split("*")[0].split("#")[0])
                s.add(head.split(":")[-1])
            return {k for k in s if _IS_KEY.match(k)}

        for lbl, fld in (("row removed", "removed_keys"), ("row added", "added_keys"),
                         ("row retargeted", "retargeted_keys")):
            touched[lbl] = set().union(*(
                _vs_of(out["classes"][c][fld])
                for c in ("ls_rows", "body", "one_sided")))
        tri_v: set[str] = set()
        for k in list((ta - tb).elements()) + list((tb - ta).elements()):
            tri_v.update(k.split("|"))
        touched["triangulation changed"] = tri_v
        touched["column changed"] = {k.split("#")[0] for k in (ca ^ cb)
                                     if _IS_KEY.match(k.split("#")[0])}
        print(f"\nTHE MOVERS ({len(rows_):,} non-pad solve-owned vertices over "
              f"{mv['tol_m']} m), by the stage-1 change they stand on:")
        seen: set[str] = set()
        order = ["column changed", "triangulation changed", "row added",
                 "row removed", "row retargeted"]
        tbl = []
        for cls in order:
            vs = touched[cls]
            hit = [m for m in rows_
                   if f"{float(m['lat']):.11f},{float(m['lon']):.11f}" in vs
                   and f"{float(m['lat']):.11f},{float(m['lon']):.11f}" not in seen]
            seen.update(f"{float(m['lat']):.11f},{float(m['lon']):.11f}" for m in hit)
            worst = max((m["dz_m"] for m in hit), default=0.0)
            tbl.append((cls, len(hit), worst,
                        max(hit, key=lambda m: m["dz_m"], default=None)))
        rest = [m for m in rows_
                if f"{float(m['lat']):.11f},{float(m['lon']):.11f}" not in seen]
        tbl.append(("none of these (far field)", len(rest),
                    max((m["dz_m"] for m in rest), default=0.0),
                    max(rest, key=lambda m: m["dz_m"], default=None)))
        print(f"{'class':32s} {'movers':>8s} {'worst m':>9s}  worst site")
        for cls, n, w, m in tbl:
            site = (f"{m['lat']},{m['lon']} {','.join(m['roles'])}" if m else "-")
            print(f"{cls:32s} {n:8,d} {w:9.2f}  {site}")
        out["movers"] = [{"class": c, "n": n, "worst_m": w,
                          "worst": m} for c, n, w, m in tbl]
        # THE REACH: how far each mover stands from the NEAREST changed
        # stage-1 item.  A least-squares surface is solved globally, so a
        # mover that stands on nothing changed is the CHANGE PROPAGATING
        # through the sheet — this is the profile of that propagation, and
        # it is what separates "the pads moved this vertex" from "the pads
        # moved the problem and this vertex is downstream of it".
        changed = set().union(*touched.values())
        if changed and rest:
            import numpy as np
            cxy = np.array([[float(k.split(",")[0]), float(k.split(",")[1])]
                            for k in changed])
            lat0 = float(cxy[:, 0].mean())
            sc = np.array([111_320.0, 111_320.0 * math.cos(math.radians(lat0))])
            cm = cxy * sc
            bins = [0, 25, 100, 250, 500, 1000, 10 ** 9]
            prof: dict[str, int] = {}
            worst_far = (0.0, None)
            for m in rest:
                p = np.array([float(m["lat"]), float(m["lon"])]) * sc
                dmin = float(np.min(np.hypot(cm[:, 0] - p[0], cm[:, 1] - p[1])))
                for lo, hi in zip(bins, bins[1:]):
                    if lo <= dmin < hi:
                        prof[f"{lo}-{hi:g} m"] = prof.get(f"{lo}-{hi:g} m", 0) + 1
                        break
                if dmin > worst_far[0]:
                    worst_far = (dmin, m)
            print("  the far-field movers' distance to the nearest changed "
                  "stage-1 item: " + ", ".join(f"{k} {v:,}" for k, v in prof.items()))
            if worst_far[1] is not None:
                print(f"  the farthest: {worst_far[0]:,.0f} m at "
                      f"{worst_far[1]['lat']},{worst_far[1]['lon']} "
                      f"({worst_far[1]['dz_m']} m)")
            out["far_field_reach"] = prof
    if json_out is not None:
        json_out.write_text(json.dumps(out, indent=1, default=str))
    return 0


def pad_read(icao: str, pm, law, airport, sites: list[tuple[float, float]]) -> dict:
    """THE PAD READ of a re-run arrangement (lane ``spjcpads``, issues #3 /
    #4, RULINGS 2026-09-23a): what the planar stage made of the building
    pads, read off the MAP (not the mint) so it is what the solve sees.

    * the arrangement's own pad/airside publication (``PAD_AIRSIDE``: the
      23a apron cut's ``apron_faces_cut`` / ``apron_face_consumed`` /
      ``pad_airside_weld_pairs`` / ``pad_area_kept_m2``, or the pre-23a
      clip's counters, and the §16g (10) (12) re-node census);
    * the ``building`` faces and refs and their area, and the rolled-on
      (airside) face area — what 23a trades between the two;
    * the WELD by node identity: pad refs sharing a vertex with an airside
      face, and how many vertices they share (the §28 / §16g (10) (6)
      ``pad_airside_weld`` population the census prices);
    * ``pad_cluster_mismatch`` (§16g (10) (3)), the declared defect set;
    * per ``--site``: the face under the point, and for a pad the WHOLE
      ref — faces, area — because a pad is a ref, not a face.
    Prices no law; solves nothing."""
    from shapely.geometry import Point
    from auto_patch_v2.constraints.cluster_pad import pad_cluster_mismatch
    from auto_patch_v2.law.tables import rolled_on_roles
    from auto_patch_v2.planar.index import face_polygon
    from auto_patch_v2.planar.overlay import PAD_AIRSIDE
    rolled = rolled_on_roles(law)
    polys = {fid: face_polygon(pm, fid) for fid in pm.faces}
    bref: dict[str, list[int]] = {}
    for fid, f in pm.faces.items():
        if f.role == "building":
            bref.setdefault(str(f.ref), []).append(fid)
    b_area = sum(polys[i].area for fs in bref.values() for i in fs)
    air_area = sum(polys[fid].area for fid, f in pm.faces.items() if f.role in rolled)
    air_v = {v for fid, f in pm.faces.items() if f.role in rolled
             for v in _face_vids(f)}
    weld_refs = 0
    weld_v = 0
    for ref, fs in bref.items():
        n = len({v for i in fs for v in _face_vids(pm.faces[i])} & air_v)
        if n:
            weld_refs += 1
            weld_v += n
    mism = pad_cluster_mismatch(pm, law, airport)
    pa = {k: v for k, v in PAD_AIRSIDE.items() if not isinstance(v, (list, tuple, set))}
    out = {"pad_airside": pa, "building_faces": sum(len(v) for v in bref.values()),
           "building_refs": len(bref), "building_area_m2": round(b_area, 1),
           "airside_area_m2": round(air_area, 1), "weld_refs": weld_refs,
           "weld_vertices": weld_v, "pad_cluster_mismatch": len(mism), "sites": []}
    print(f"[{icao}] PAD READ arrangement {pa}")
    print(f"[{icao}] PAD READ building faces {out['building_faces']} in "
          f"{len(bref)} refs, {b_area:,.0f} m2; airside (rolled-on) faces "
          f"{air_area:,.0f} m2; weld: {weld_refs} pad refs share {weld_v} "
          f"vertices with airside; pad_cluster_mismatch {len(mism)}")
    to_xy = airport.frame.entry()
    for lat, lon in sites:
        P = Point(to_xy(lon, lat))
        hit = [fid for fid, g in polys.items() if g.buffer(0.01).contains(P)]
        for fid in hit:
            f = pm.faces[fid]
            row = {"site": [lat, lon], "face": fid, "role": f.role,
                   "ref": str(f.ref), "face_m2": round(polys[fid].area, 1)}
            if f.role == "building":
                fs = bref.get(str(f.ref), [])
                row["ref_faces"] = len(fs)
                row["ref_m2"] = round(sum(polys[i].area for i in fs), 1)
            out["sites"].append(row)
            print(f"[{icao}] PAD READ site {lat},{lon}: {row}")
        if not hit:
            print(f"[{icao}] PAD READ site {lat},{lon}: no face")
    return out


def _face_vids(f) -> list[int]:
    from auto_patch_v2.model.planar import face_vertex_ids
    return face_vertex_ids(f.ring, f.holes)


def replay_problem(pkl: Path, resume: str, drop: list[str],
                   design_weights: dict | None = None,
                   chord_fill: tuple[str, ...] = (),
                   placement: dict | None = None,
                   sites: list[tuple[float, float]] | None = None,
                   pad_read_only: bool = False) -> dict:
    """THE REPLAY'S OWN PROBLEM, up to and including the constraint set —
    the prelude ``--replay`` and ``--stage1-dump`` SHARE (a second copy of
    it is the census-wrapper defect, RULINGS ``7e90032``): the capture, the
    re-node reading, the channel backfills, the clusters, the target
    channels in ``pipeline/build.py``'s order, the shape stage, the
    ``[design]`` arm and ``shape_constraints`` with ``--drop-generator``
    applied.  It solves nothing."""
    import numpy as np  # noqa: F401  (the prelude's imports are the replay's)
    from auto_patch_v2.airport.road_profile import preferred_road_z
    from auto_patch_v2.law import Law
    from auto_patch_v2.model.constraints import ConstraintSet
    from auto_patch_v2.pipeline.build import displacement_by_role
    from auto_patch_v2.pipeline.shapes import joint_steps, shape_constraints, shape_stage
    from auto_patch_v2.planar.build import build as build_planar
    from auto_patch_v2.solve import Options
    from auto_patch_v2.solve import solve_design
    # REFUSED BEFORE THE (multi-GB) CAPTURE IS READ: a pad key is read at
    # classify / planar, so a replay-time ``--placement`` arm — and the
    # ``--pad-read`` of the arrangement — is honest only when the replay
    # re-runs that stage.  A later resume re-uses the captured map and the
    # override would be silently inert.
    if (placement or pad_read_only) and resume not in ("classify", "planar"):
        raise SystemExit("--placement / --pad-read at replay need --from "
                         "classify or --from planar (a later resume re-uses "
                         "the captured arrangement and cannot see the key)")
    with pkl.open("rb") as fh:
        cap = pickle.load(fh)
    icao, airport, cl, pm, stage, inputs = (cap["icao"], cap["airport"], cap["cl"], cap["pm"],
                                            cap["stage"], cap["inputs"])
    # restore the arrangement's re-node reading (see ``--capture``); a
    # capture written before 2026-09-16 carries none and every reader
    # then reports the key ABSENT rather than zero
    _pa = cap.get("pad_airside")
    if _pa:
        from auto_patch_v2.planar.overlay import PAD_AIRSIDE
        PAD_AIRSIDE.clear()
        PAD_AIRSIDE.update(_pa)
        print(f"[{cap['icao']}] pad/airside re-node from the capture: "
              f"deleted {_pa.get('renode_deleted')} minted {_pa.get('renode_minted')}")
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
    if placement:
        # THE REPLAY-TIME [placement] ARM (lane ``spjcpads``): a pad key is
        # read at classify / planar, so it is an honest one-variable arm
        # ONLY when the replay re-runs that stage — ``--from classify``
        # (the mint and the arrangement) or ``--from planar`` (the
        # arrangement alone).  Any later resume re-uses the captured map
        # and the override would be silently inert, so it refuses.
        law, _kw = _placement_override(law, placement)
        print(f"[{icao}] REPLAY ARM [placement] {_kw}")
    # A CAPTURE PREDATING §46's INPUT QUANTUM says so (spec §46 (8)): its
    # Frame carries no ``input_quantum_m``, so every ENTRY projection in
    # the replay (the pack's rings and feet — the load stage is already
    # in the pickle) is EXACT, i.e. the pre-§46 law.  It is NOT
    # backfilled: the pickle's own coordinates were produced without the
    # quantum and a half-quantised replay would be neither law.
    _fr = getattr(airport, "frame", None)
    if _fr is not None and "input_quantum_m" not in getattr(_fr, "__dict__", {}):
        from auto_patch_v2.law.tables import input_quantum_m as _iq
        print(f"[{icao}] capture predates §46's input quantum — this replay's "
              f"ENTRY projections are EXACT (the pre-§46 law), not "
              f"{_iq(law):g} m")
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
    if resume == "classify":
        # §16g (10) (2)'s pad is MINTED AT CLASSIFY TIME off ``Airport.
        # clusters`` — and BOTH are captured, so a change in the cluster
        # derivation (``plan_clusters``) or the pad mint (``geom.
        # cluster_outlines``) is INVISIBLE to ``--from planar``, which
        # re-uses the captured classification (lane ``spjcpads``, issues
        # #3 / #4: the fix moved 0 pads under ``--from planar``).  This
        # arm re-derives the clusters off the captured partition and
        # re-runs the CLASSIFY stage under the current tree, printing the
        # cluster-outline counters the sidecar publishes, then the planar
        # map as ``--from planar`` does.  Seconds against a capture.
        from auto_patch_v2.classify import classify as _classify, load_rules as _load_rules
        from auto_patch_v2.classify.evidence import CLUSTER_PADS as _CP
        from auto_patch_v2.planar.cluster import WHY as _WHY
        from auto_patch_v2.planar.cluster import clusters as _derive_clusters
        _ct = time.perf_counter()
        airport = _dc.replace(airport, clusters=_derive_clusters(airport, law))
        print(f"[{icao}] clusters re-derived under the current tree: "
              f"{len(airport.clusters)} ({time.perf_counter() - _ct:.0f} s) {dict(_WHY)}")
        _ct = time.perf_counter()
        cl = _classify(airport, law, _load_rules())
        print(f"[{icao}] classify re-run: {len(cl.cells)} cells "
              f"({time.perf_counter() - _ct:.0f} s); cluster pads {dict(_CP)}")
    if resume in ("classify", "planar"):
        pm, _ps = build_planar(airport, cl, law)
        road_pref, _r, _p = preferred_road_z(airport, pm, law, inputs.road_grade_limit,
                                             inputs.lane_width_m)
        pm = _dc.replace(pm, preferred_z=road_pref)
        _pr = pad_read(icao, pm, law, airport, sites or [])
        if pad_read_only:
            return {"icao": icao, "airport": airport, "cl": cl, "pm": pm,
                    "law": law, "t0": t0, "pad_read": _pr}
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
        # §50.4 THE ONE LOUD LINE (owner RULINGS 2026-09-18d (3)): the
        # replay prints exactly what the build prints, from the SAME
        # record (``pm.runway_caps``, which ``with_runway_chord`` has just
        # derived) — so an over-grade runway is visible in a stage replay
        # and under ``--why-hard`` without an airport build.
        try:
            from auto_patch_v2.constraints.runway_yield import yielded_lines
            for _ln in yielded_lines(icao, getattr(m, "runway_caps", {}) or {},
                                     law.ruleset.authority):
                print(_ln)
        except ImportError:
            pass                       # a tree that predates §50
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
    if resume in ("classify", "planar", "shapes"):
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
    cs, counts, _w = shape_constraints(pm, law, airport, stage)
    if drop:
        cs = ConstraintSet.from_rows([r for r in cs.rows() if r.source.generator not in drop])
    return {"icao": icao, "airport": airport, "cl": cl, "pm": pm, "stage": stage,
            "law": law, "cs": cs, "counts": counts, "inputs": inputs, "t0": t0}


def replay(pkl: Path, resume: str, drop: list[str], json_out: Path | None,
           z_out: Path | None, method: str = "normal",
           design_weights: dict[str, float] | None = None, verbose: bool = False,
           sites: list[tuple[float, float]] | None = None, emit_dir: Path | None = None,
           why_hump: tuple[str, float, float] | None = None, verify: bool = False,
           solved_out: Path | None = None, chord_fill: tuple[str, ...] = (),
           site_radius_m: float = 12.0, why_hard_limit: int | None = None,
           why_hard_stage: int | None = None,
           placement: dict | None = None) -> int:
    import numpy as np
    from auto_patch_v2.pipeline.build import displacement_by_role
    from auto_patch_v2.pipeline.shapes import joint_steps
    from auto_patch_v2.solve import Options
    from auto_patch_v2.solve import solve_design
    prob = replay_problem(pkl, resume, drop, design_weights, chord_fill,
                          placement=placement, sites=sites)
    icao, airport, pm, law, cs = (prob["icao"], prob["airport"], prob["pm"],
                                  prob["law"], prob["cs"])
    cl, stage, counts, t0 = prob["cl"], prob["stage"], prob["counts"], prob["t0"]
    size: dict = {}
    # THE JETWAY STRIP'S REGION (jetway-strip spec §1): the build's own
    # derivation (``pipeline/build.py``), so the replay solves the problem
    # the build solves
    from auto_patch_v2.airport.riders import rider_candidates
    from auto_patch_v2.constraints.jetway_strip import jetway_strips
    t = time.perf_counter()
    strips = jetway_strips(pm, law, airport, cs, rider_candidates(airport, law))
    print(f"[{icao}] jetway strip region (18t Q3) {time.perf_counter() - t:.2f} s: "
          + ", ".join(f"{k} {v}" for k, v in strips.counts.items()))
    t = time.perf_counter()
    sol, rep = solve_design(pm, cs, law, Options(verbose=verbose), size_out=size,
                            method=method, strips=strips)
    wall = round(time.perf_counter() - t, 1)
    print(f"[{icao}] {rep.jetway_strip.line()}")
    for _s in rep.jetway_strip.strips:
        print(f"    strip {_s['id']} pad {_s['pad_ref']} frontage resid "
              f"{_s.get('frontage_resid_m')} gated {_s.get('gated')} level {_s['level']} riders "
              f"{_s['riders']} vertices {_s['vertices']} max move {_s['moved_max_m']} m; "
              f"clamps {len(_s['clamps'])} worst "
              f"{max((abs(c[2]) for c in _s['clamps']), default=0.0)} m "
              f"{sorted({c[1] for c in _s['clamps']})}")
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
            vrows = run_census(surf, law, publication(pm, law, airport, sol.z, cs,
                                                      strips=strips,
                                                      strip_rep=rep.jetway_strip),
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
            # EVERY family's rows (capped), so a --json arm can be read by
            # site without a second census (lane ``nlwf``)
            result["verify"]["rows"] = {k: v[:200] for k, v in vrows.items() if v}
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
            result.update(emit_patch(icao, pm, law, airport, cs, sol, emit_dir,
                                     strips=strips, strip_rep=rep.jetway_strip))
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
    ap.add_argument("--rule", action="append", default=[], metavar="SECTION.KEY=V",
                    help="CAPTURE ARM: override one classify/rules.toml key for "
                         "this capture (repeat).  A CLASSIFY key is read upstream "
                         "of the capture, so a matched pair on one is two captures "
                         "\u2014 this makes the arm one command-line variable instead "
                         "of an edit to the shipped toml; e.g. "
                         "--rule corridor.runway_shoulder_band=false")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--reclassify", type=Path, metavar="PKL",
                    help="DRY \u00a740 SHOULDER-BAND READ off a registered capture: "
                         "re-run the CLASSIFY stage alone over the capture's own "
                         "Airport on the current tree, with --rule as the only "
                         "variable, and print the band table (shoulder m2, the "
                         "remainder by earned role, the worst lateral offset and "
                         "the vertices beyond the band).  Prices no law and counts "
                         "no defects.")
    ap.add_argument("--replay", type=Path, metavar="PKL")
    ap.add_argument("--from", dest="resume",
                    choices=("constraints", "shapes", "planar", "classify"),
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
    ap.add_argument("--pad-read", action="store_true",
                    help="DRY: with --from classify/planar, re-run the stage, print "
                         "the PAD READ (pad/airside arrangement counters, building vs "
                         "airside area, weld population, pad_cluster_mismatch, the "
                         "pad ref under each --site) and stop before the solve")
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
    ap.add_argument("--stage1-dump", type=Path, metavar="OUT.json.gz",
                    help="§20b (3) THE STAGE-1 POPULATION off a --solved-out "
                         "pickle (--why-from): stage_split + assemble, with every "
                         "row, column, sheet face and triangle keyed canonically "
                         "(11-dp lat/lon), written gzipped.  Solves nothing; "
                         "--drop-generator and --design-weight apply")
    ap.add_argument("--stage1-diff", nargs=2, type=Path, metavar=("A.json.gz", "B.json.gz"),
                    help="§20b (3) (4) THE DECOMPOSITION: diff two --stage1-dump "
                         "arms by identity — rows removed / added, columns, sheet "
                         "faces and triangles — and with --movers attribute an "
                         "airside_value_delta --json's movers to the class of "
                         "stage-1 change each stands on")
    ap.add_argument("--movers", type=Path, metavar="AVD.json",
                    help="an airside_value_delta --json dump for --stage1-diff")
    ap.add_argument("--probe-arm", action="append", default=[], metavar="TERM=V",
                    help="one probe ARM as a [design] override; repeat for a "
                         "matched pair (e.g. --probe-arm solver=fixed_point "
                         "--probe-arm solver=qp).  Default: the shipped law alone")
    a = ap.parse_args()
    if a.stage1_diff:
        return stage1_diff(a.stage1_diff[0], a.stage1_diff[1], a.movers, a.json)
    if a.stage1_dump:
        if not (a.why_from or a.replay):
            ap.error("--stage1-dump needs --why-from PKL (a --solved-out pickle) "
                     "or --replay PKL (a capture, whose generators are re-run "
                     "under the current tree)")
        dw = {k.strip(): _design_value(v)
              for k, v in (it.split("=") for it in a.design_weight)}
        return stage1_population(a.why_from or a.replay, a.drop_generator,
                                 a.stage1_dump, dw,
                                 from_capture=a.why_from is None, resume=a.resume)
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
        rl = dict(it.split("=", 1) for it in a.rule)
        _capture_guarded(a.capture.upper(), a.out, a.mod_cache_root, pl, rl)
        return 0
    if a.reclassify:
        rl = dict(it.split("=", 1) for it in a.rule)
        return reclassify(a.reclassify, rl, a.json)
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
        pl = dict(it.split("=", 1) for it in a.placement)
        if a.pad_read:
            res = replay_problem(a.replay, a.resume, a.drop_generator, None, (),
                                 placement=pl, sites=sites, pad_read_only=True)
            if a.json:
                a.json.write_text(json.dumps(res["pad_read"], indent=1, default=str))
            return 0
        return replay(a.replay, a.resume, a.drop_generator, a.json, a.z_out,
                      method=a.method,
                      design_weights={k.strip(): _design_value(v)
                                      for k, v in (it.split("=") for it in a.design_weight)},
                      verbose=a.design_verbose, sites=sites, site_radius_m=a.site_radius,
                      emit_dir=a.emit, why_hump=wh, verify=a.verify, solved_out=a.solved_out,
                      chord_fill=tuple(a.chord_fill), why_hard_limit=a.why_hard,
                      why_hard_stage=a.why_hard_stage, placement=pl)
    ap.error("one of --capture / --replay")
    return 2


if __name__ == "__main__":
    sys.exit(main())
