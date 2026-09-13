"""Offline replay of the auto-patch-v2 OBJECT STAGE — the post-mesh half
without a tile build, and a pack's current bake state without a build at
all.

    venv/bin/python tools/v2_rebake_replay.py plan PLAN.json MESH --graded G.json [--runs N]
    venv/bin/python tools/v2_rebake_replay.py order ICAO [--dem-frame ...]
    venv/bin/python tools/v2_rebake_replay.py disk PACK_ROOT [--filter TOKEN]

THE SEAT IS RETIRED (owner RULINGS 2026-09-12s, spec §8): the ``seat``,
``bodies`` and ``pairs`` subcommands replayed v1's vertex rewrite and its
``o4_v2_rebake_result_*`` sidecars — a refuted mechanism — and are
DELETED with it, as are ``emit/rebake.seat``, ``emit/clusters.py`` and
``airport/rigid.py`` that they drove.  ``plan``, ``order`` and ``disk``
are the live instruments.

``plan`` (RULINGS 2026-09-12g) replays and TIMES the PLACEMENT stage —
``placement_write.build_plan`` over ``engine_v2._placement_surface``, the
surface the app itself builds — on a build's own written frame, and is
the instrument the object stage's wall time is read on.  ``--sampler
mesh`` (the default) is what the app calls; ``--sampler graded`` is the
interpolator the lanes timed the stage on, 60x off it.  ``--src`` points
the replay at another checkout's ``src``, so ONE tool measures both arms
of a sampler change; ``--oracle-write`` / ``--oracle-check`` are the
bit-identity instrument for any change to the sampler's candidate
prefilter.  Promoted from the ``v2plantime`` scout's ``measure.py`` on
its second use (lane ``v2meshgrid``).  Writes no pack and builds no tile.

``order`` is the PARTITION-ORDER twin (11j / spec §11a (3)).

``disk`` walks a scenery pack for ``<obj>.anchor_bak`` backups and prints,
per resource matching ``--filter``, the live-minus-authored vertex ``y``
delta on disk and v1's provenance record (decision kind, anchor ground,
seat datum, delta) — how a pack authored under the retired seat still
reads, which the placement path's §10 RESTORE puts back.  Read-only.

Twins: ``tests/auto_patch_v2/test_v2objsplit.py`` (the placement plan).
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))
sys.path.insert(0, os.path.join(HERE, "harness"))


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


def cmd_plan(args: argparse.Namespace) -> int:
    """THE PLACEMENT STAGE, REPLAYED AND TIMED (RULINGS 2026-09-12g).

    ``placement_write.build_plan`` on a tile build's own written frame,
    over the sampler the APP calls — which is the whole point: the
    object-stage time the lanes quoted (5.65 -> 9.9 s) was measured on
    the GRADED interpolator, 60x off the mesh sampler the shipped path
    uses, and the 1.0.320 mesh step was 706 s with 669 of them here.

    Prints the wall time per run, the ``_surface`` call count (point and
    batched) and its unique-point count, the plan's counts and file
    total.  Nothing is written to the pack, the DSF text dump is READ
    from the mod cache, and no tile is built.

    ``--oracle-write`` saves every query's (lat, lon) -> (elevation,
    terrain type, is_water | None-outside) answer; ``--oracle-check``
    replays those points through the sampler and asserts every answer
    BIT-identical — the identity instrument for any change to
    ``mesh_sampler``'s candidate prefilter.  ``--src`` replays against
    another checkout's ``src`` so one tool measures both arms.
    """
    import collections
    import math
    import pickle
    import time

    surface_source = args.src or os.path.join(os.path.dirname(HERE), "src")
    if surface_source not in sys.path:
        sys.path.insert(0, surface_source)

    # the PLAN record lives in ``model.rebake``; ``emit.rebake`` kept
    # only the deck datum when the seat was deleted (12s), so this
    # import had been dead since — the ``plan`` subcommand raised
    # AttributeError on every run (found by lane v2objmotion while
    # timing the plan stage).
    from auto_patch_v2.model import rebake as _rb
    from auto_patch_v2.airport import placement_write as _pw
    from auto_patch_v2.airport import placement_plan as _pp
    from auto_patch_v2.airport import dsf as _dsf2
    from auto_patch_v2.law import Law
    from auto_patch import dsf_reader as _DSFR
    from auto_patch import engine_v2 as _ev2
    from auto_patch_v2.airport.dsf_write import pristine_dsf_path
    import O4_File_Names as FNAMES

    with open(args.plan) as fh:
        plan_ = _rb.RebakePlan.from_json(fh.read())
    law = Law.for_airport(plan_.icao)
    # §16e (2) BACK-FILL, NAMED AND COUNTED.  ``deck_end_stations`` is
    # derived by the PATCH half (``rebake_plan.ring_ends`` /
    # ``end_line_stations``) and a plan written before §16e carries none,
    # so replaying one would measure a law the plan predates.  The SAME
    # two functions are called here on the plan's own ``deck_ring`` —
    # never a second derivation — and the count is printed.
    try:
        from auto_patch_v2.airport.rebake_plan import (end_line_stations,
                                                       ring_ends)
    except ImportError:
        ring_ends = None
    if ring_ends is not None:
        import dataclasses as _dc1
        _n = 0
        _step = law.tables.structures.bridge.abutment_sample_step_m
        _units = []
        for _u in plan_.units:
            _ms = []
            for _m in _u.members:
                if (_m.deck_kind in ("flag", "signature")
                        and _m.deck_datum_z is None and _m.deck_ring
                        and not _m.deck_end_stations):
                    _e = ring_ends(_m.deck_ring)
                    _st = end_line_stations(_e, _step)
                    if _st:
                        _n += 1
                        _m = _dc1.replace(_m, deck_ends=_m.deck_ends or _e,
                                          deck_end_stations=_st)
                _ms.append(_m)
            _units.append(_dc1.replace(_u, members=tuple(_ms)))
        plan_ = _dc1.replace(plan_, units=tuple(_units))
        if _n:
            print("  §16e (2) back-fill: %d deck member(s) given their end "
                  "lines (this plan predates the field)" % _n)
    lat, lon = args.tile
    dsf_path = _dsf2.dsf_path_in_pack(plan_.pack_root, lat, lon)
    pack_name = os.path.basename(os.path.normpath(plan_.pack_root))
    cache = _dsf2.mod_cache_dir(FNAMES.airport_mod_cache_root(), pack_name)
    dump_path = args.dsf_dump or _DSFR.ensure_dsf_text_path(
        pristine_dsf_path(dsf_path), cache)
    if not dump_path:
        print("no DSF text dump (and none in the mod cache) — pass --dsf-dump")
        return 2
    dump = _dsf2.read_dump(dump_path)
    import json as _json
    with open(args.graded, encoding="utf-8") as _gf:
        _gdoc = _json.loads(_gf.read())
    pads, rims = _pp.pads_rims_from_graded_doc(_gdoc)
    # §17 (RULINGS 2026-09-12am (2)): the face ROLES ride the sampler, as
    # they do on the shipped path — otherwise this instrument times a
    # plan the app does not build.
    from auto_patch_v2.airport import placement_boxes as _pb
    from auto_patch_v2.law import tables as _T
    _roles = _pb.graded_roles_from_doc(_gdoc,
                                       rank=lambda r: _T.authority_rank(law, r))
    _rolled = frozenset(_T.rolled_on_roles(law))
    print("%s: units %d, bounds %s, pads %d, rims %d, src %s"
          % (plan_.icao, len(plan_.units), plan_.bounds(), len(pads),
             len(rims), surface_source))

    oracle: dict = {}
    capture = [bool(args.oracle_write)]

    def _mesh_sampler():
        from auto_patch.mesh_sampler import (MeshElevationSampler,
                                             OutsideMeshError)
        started = time.perf_counter()
        sampler = MeshElevationSampler(args.mesh, plan_.bounds())
        construct = time.perf_counter() - started
        print("  MeshElevationSampler: %d retained triangles, construct %.2fs"
              % (len(sampler._triangles), construct))
        if hasattr(sampler, "_grid_cells"):
            print("  grid index: %d x %d cells, %d bucket entries "
                  "(%.2f per triangle)"
                  % (sampler._grid_cells, sampler._grid_cells,
                     len(sampler._grid_triangles),
                     len(sampler._grid_triangles)
                     / max(1, len(sampler._triangles))))

        def sample(la, lo, _s=sampler):
            try:
                s = _s.sample_at(la, lo)
            except OutsideMeshError:
                if capture[0]:
                    oracle[(la, lo)] = None
                return None
            if capture[0]:
                oracle[(la, lo)] = (float(s.elevation_metres),
                                    int(s.terrain_type), bool(s.is_water))
            z = float(s.elevation_metres)
            return (z, bool(s.is_water)) if math.isfinite(z) else None

        if hasattr(sampler, "sample_many") and not args.no_batch:
            def sample_many(las, los, _s=sampler):
                out = []
                for s in _s.sample_many(las, los):
                    if s is None:
                        out.append(None)
                        continue
                    z = float(s.elevation_metres)
                    out.append((z, bool(s.is_water))
                               if math.isfinite(z) else None)
                return out
            sample.many = sample_many
        return sample, construct, sampler

    def _graded_sampler():
        import numpy as np
        from scipy.interpolate import LinearNDInterpolator
        with open(args.graded, encoding="utf-8") as fh:
            data = json.load(fh)
        verts = data["vertices"]
        started = time.perf_counter()
        interp = LinearNDInterpolator(
            np.asarray([[v[1], v[2]] for v in verts], dtype=float),
            np.asarray([v[3] for v in verts], dtype=float))
        construct = time.perf_counter() - started
        print("  graded interpolator: %d vertices, construct %.2fs"
              % (len(verts), construct))

        def sample(la, lo):
            z = float(np.asarray(interp(la, lo)).reshape(-1)[0])
            return None if not np.isfinite(z) else (z, False)

        def sample_many(las, los):
            zs = np.asarray(interp(np.asarray(las, dtype=float),
                                   np.asarray(los, dtype=float))).reshape(-1)
            return [None if not np.isfinite(z) else (float(z), False)
                    for z in zs]
        sample.many = sample_many
        return sample, construct, None

    keywords = dict(
        icao=plan_.icao, pack_name=pack_name, pack_root=plan_.pack_root,
        dsf_path=dsf_path,
        split_tol_m=law.tables.structures.placement.split_tol_m,
        elevated_base_m=law.tables.structures.rebake.elevated_base_m,
        line_segment_m=law.tables.structures.placement.line_segment_m,
        line_stations_max=law.tables.structures.rebake.line_object_stations_max,
        line_ratio=law.tables.structures.rebake.line_object_ratio,
        line_max_h=law.tables.structures.rebake.line_object_max_h,
        foot_band_m=law.tables.structures.basin.contact_band_m,
        # every §16c key through ``getattr``: the dropper below removes
        # what THIS src's ``build_plan`` does not take, but reading a key
        # the LAW no longer has raises before it runs (``carrier_fill_min``
        # was deleted by §16c (7) and this line killed the whole
        # subcommand — found by lane v2objmotion)
        carrier_fill_min=getattr(law.tables.structures.placement,
                                 "carrier_fill_min", None),
        coarsen_reach_m=getattr(law.tables.structures.placement,
                                "coarsen_reach_m", 0.0),
        contact_eps_m=getattr(law.tables.structures.placement,
                              "contact_eps_m", 0.0),
        rigid_reach_m=getattr(law.tables.structures.placement,
                              "rigid_reach_m", 0.0),
        # (A), owner RULINGS 2026-09-12ap — through the same dropper, so
        # this entry still times a src that predates the key
        bind_ground_m=getattr(getattr(law.tables.emit, "cockpit", None),
                              "visual_m", None),
        # §16f (7) (owner RULINGS 2026-09-13bj item 1), through the same
        # dropper so a src predating the key still replays
        cluster_min_m2=getattr(law.tables.structures.placement,
                               "cluster_pad_min_m2", None),
        touch_m=getattr(law.tables.structures.placement,
                        "footprint_touch_m", None),
        connector_span_m=getattr(law.tables.structures.placement,
                                 "connector_span_m", None),
        # §16e (6): the deck end line's LANDWARD WALK, through the same
        # dropper — a src predating the rule takes neither key
        abutment_step_m=getattr(law.tables.structures.bridge,
                                "abutment_sample_step_m", None),
        abutment_walk_max_m=getattr(law.tables.structures.bridge,
                                    "abutment_walk_max_m", None),
        pads=pads, rims=rims, engine_version="", law_digest="",
        write_cuts=False)
    import inspect
    accepted = set(inspect.signature(_pw.build_plan).parameters)
    for key in [k for k in keywords
                if k not in accepted or keywords[k] is None]:
        print("  SIG DIFF: this src's build_plan takes no %r — dropped" % key)
        keywords.pop(key)

    times = []
    last_plan = last_files = None
    counters = None
    for run in range(args.runs):
        sample, construct, _sampler = (
            _graded_sampler() if args.sampler == "graded" else _mesh_sampler())
        counters = collections.Counter()
        make = getattr(_ev2, "_placement_surface", None)
        if make is None:
            # A --src predating 12g (2): the BARE closure the app shipped,
            # no .many and no memo — the arm this is measured against.
            def surface(la, lo, _s=sample):
                s = _s(la, lo)
                return None if s is None else float(s[0])
        else:
            surface = make(sample)
        watched = _watch_surface(surface, counters)
        watched.roles = _roles           # §17, as the shipped path attaches
        watched.rolled_on = _rolled
        # §16e: the WATER bit, as the shipped path attaches it
        _w = getattr(surface, "water", None)
        if _w is not None:
            watched.water = _w
        started = time.perf_counter()
        out_plan, files, _ = _pw.build_plan(plan_, dump, watched, **keywords)
        elapsed = time.perf_counter() - started
        times.append(elapsed)
        last_plan, last_files = out_plan, files
        print("  run %d: build_plan %8.2fs   surface calls %d "
              "(point %d, batched %d) unique %d   construct %.2fs"
              % (run + 1, elapsed, counters["calls"], counters["point"],
                 counters["batched"], counters["unique"], construct))
        capture[0] = False          # the oracle is run 1's reading
    print("%s sampler: wall %s  mean %.2fs  min %.2fs"
          % (args.sampler, ["%.2f" % t for t in times],
             sum(times) / len(times), min(times)))
    print("  plan counts: %s   files %d"
          % (dict(last_plan.counts()), len(last_files)))

    if args.plan_out:
        with open(args.plan_out, "w") as fh:
            fh.write(last_plan.to_json())
        print("  plan ->", args.plan_out)
    if args.oracle_write:
        with open(args.oracle_write, "wb") as fh:
            pickle.dump(oracle, fh, protocol=4)
        outside = sum(1 for v in oracle.values() if v is None)
        print("  oracle: %d unique points (%d outside) -> %s"
              % (len(oracle), outside, args.oracle_write))
    if args.oracle_check:
        return _oracle_check(args, plan_)
    return 0


def _watch_surface(surface, counters):
    """Count what ``build_plan`` asks, without changing an answer."""
    seen = set()

    def watched(la, lo):
        counters["calls"] += 1
        counters["point"] += 1
        seen.add((la, lo))
        counters["unique"] = len(seen)
        return surface(la, lo)

    inner = getattr(surface, "many", None)
    if inner is not None:
        def watched_many(las, los):
            las = list(las)
            los = list(los)
            counters["calls"] += len(las)
            counters["batched"] += len(las)
            counters["batches"] += 1
            seen.update(zip(las, los))
            counters["unique"] = len(seen)
            return inner(las, los)
        watched.many = watched_many
    return watched


def _oracle_check(args, plan_) -> int:
    """Every oracle point through THIS src's sampler, bit for bit."""
    import pickle
    from auto_patch.mesh_sampler import MeshElevationSampler, OutsideMeshError
    with open(args.oracle_check, "rb") as fh:
        oracle = pickle.load(fh)
    sampler = MeshElevationSampler(args.mesh, plan_.bounds())
    points = list(oracle.items())
    bad_point = bad_batch = outside = 0
    worst = None
    for (la, lo), expected in points:
        try:
            s = sampler.sample_at(la, lo)
            got = (float(s.elevation_metres), int(s.terrain_type),
                   bool(s.is_water))
        except OutsideMeshError:
            got = None
            outside += 1
        if got != expected:
            bad_point += 1
            if worst is None:
                worst = (la, lo, expected, got)
    if hasattr(sampler, "sample_many"):
        step = 20000
        for start in range(0, len(points), step):
            chunk = points[start:start + step]
            batch = sampler.sample_many([p[0][0] for p in chunk],
                                        [p[0][1] for p in chunk])
            for (key, expected), s in zip(chunk, batch):
                got = None if s is None else (
                    float(s.elevation_metres), int(s.terrain_type),
                    bool(s.is_water))
                if got != expected:
                    bad_batch += 1
                    if worst is None:
                        worst = (key[0], key[1], expected, got)
    print("ORACLE: %d points (%d outside) — sample_at differences %d, "
          "sample_many differences %d" % (len(points), outside, bad_point,
                                          bad_batch))
    if worst is not None:
        print("  first difference at (%.11f, %.11f): expected %s got %s"
              % worst)
    return 0 if not (bad_point or bad_batch) else 1


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


def main(argv: list[str] | None = None) -> int:
    """The entry, under the SHARED-REPO WRITE GUARD — the SAME
    implementation ``obj8_split_report.py`` and ``harness/build_airport.py``
    arm (``tools/harness/shared_repo_guard.py``), never a second one.

    A replay is a MEASUREMENT and must cost the shared corpus zero
    writes, and this entry armed NOTHING: ``plan`` calls
    ``dsf_reader.ensure_dsf_text_path``, which GENERATES a DSF text dump
    into the mod cache when the cache has none — and a lane worktree
    MOUNTS ``Airport_mod_cache`` at the shared repo (the same class
    RULINGS 2026-09-12j caught in ``obj8_split_report``)."""
    from shared_repo_guard import (SharedRepoWriteGuard,  # noqa: E402
                                   report_unauthorised_writes,
                                   require_no_unauthorised_writes,
                                   shared_repo_snapshot, snapshot_diff)
    before = shared_repo_snapshot()
    guard = SharedRepoWriteGuard(set(), os.getcwd())
    try:
        with guard:
            rc = _main(argv)
    finally:
        changes = snapshot_diff(before, shared_repo_snapshot())
        offenders = report_unauthorised_writes(changes, set(), None)
    if guard.blocked:
        print(f"\n  shared-repo writes REFUSED at the call site: "
              f"{len(guard.blocked)}")
        for b in list(guard.blocked)[:10]:
            print(f"    {b}")
    require_no_unauthorised_writes(offenders, entry="v2_rebake_replay")
    return rc


def _main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("order", help="THE PARTITION-ORDER TWIN (11j / spec §11a (3)): "
                                     "filter-a-partition vs partition-a-filtered-set")
    o.add_argument("icao")
    o.add_argument("--dem-frame", default="production", choices=("production", "authored"))
    o.add_argument("--old-first", action="store_true",
                   help="run the CONTROL arm first (the arm that runs first is "
                        "the slower one: read the timing bar both ways)")
    o.set_defaults(fn=cmd_order)
    pl = sub.add_parser("plan", help="THE PLACEMENT STAGE, replayed and TIMED "
                                     "over the sampler the app calls (12g)")
    pl.add_argument("plan", help="the tile build's o4_v2_rebake_<ICAO>.json")
    pl.add_argument("mesh", help="the built Data+XX+YYY.mesh")
    pl.add_argument("--graded", required=True,
                    help="the emitted design surface <ICAO>.graded.json "
                         "(the pads and rims §6's class rule reads)")
    pl.add_argument("--tile", nargs=2, type=int, default=(40, -4),
                    metavar=("LAT", "LON"),
                    help="the tile whose DSF the plan's pack is read from")
    pl.add_argument("--runs", type=int, default=3,
                    help="single-run wall times swing +-25%%: never one run "
                         "per side (the standing timing law)")
    pl.add_argument("--sampler", default="mesh", choices=("mesh", "graded"),
                    help="mesh = what the APP calls (12g); graded = the "
                         "interpolator the lanes timed the stage on, 60x off")
    pl.add_argument("--no-batch", action="store_true",
                    help="withhold the sampler's .many, so surface_many takes "
                         "its per-point fallback — the pre-12g shipped path")
    pl.add_argument("--src", default="",
                    help="replay against ANOTHER checkout's src (a worktree "
                         "at the base sha), so one tool measures both arms")
    pl.add_argument("--dsf-dump", default="",
                    help="the DSF text dump (default: read from the mod "
                         "cache — never generated, the churn ruling)")
    pl.add_argument("--plan-out", default="",
                    help="write the replayed o4_v2_placement_<ICAO>.json here "
                         "(lane-local) to diff against the shipped one")
    pl.add_argument("--oracle-write", default="",
                    help="save every query point's (elevation, terrain type, "
                         "is_water | None) — the identity oracle")
    pl.add_argument("--oracle-check", default="",
                    help="replay an oracle's points through THIS src and "
                         "assert every answer BIT-identical (rc 1 on any "
                         "difference)")
    pl.set_defaults(fn=cmd_plan)
    d = sub.add_parser("disk", help="a pack's current bake state (read-only)")
    d.add_argument("pack_root")
    d.add_argument("--filter", default="")
    d.set_defaults(fn=cmd_disk)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
