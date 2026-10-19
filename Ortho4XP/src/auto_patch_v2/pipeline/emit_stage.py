"""THE EMIT STAGE (stage-cache spec §4b.6, §10 step 8): the post-solve glue
— the join yield, the runway / taxi / apron report blocks, the flat-site
datum rows, the displacement by role, the ground envelope, the seam and
the road agreement — and the emit itself: the graded surface, the
publication, the terrain edges, the shore weld, ``write_patch``, the tile
pieces and the rebake screen.  ``pipeline/build.build`` calls these in
order; they write the report keys and the stage clocks the build kept."""
from __future__ import annotations

import dataclasses as _dc
import os
import time
import typing as _t
from pathlib import Path

from ..airport import rebake_screen as _rscreen
from ..airport.rebake_plan import plan as rebake_plan
from ..classify import load_rules
from ..constraints.apron_trend import apron_trend_block
from ..constraints.flat_site import GEN as FLAT_GEN
from ..constraints.taxi_trend import taxi_trend_block
from ..emit.graded import graded_surface
from ..emit.osm_adapter import (
    WeldReport,
    merge_sub_spacing,
    shore_edges_of,
    weld_to_shore,
    write_patch,
    write_tile_pieces,
)
from ..emit.terrain_edge import with_terrain_edges
from ..law import Law
from ..model import pulse as _pulse
from ..model.planar import PlanarMap
from ..solve import Solution
from ..solve.ground_band import ground_envelope, outside_envelope
from .publication import face_tags, publication
from .rebake_inputs import _rebake_inputs
from .seam_report import seam_yield_block

__all__ = ["MOVED_M", "borrowed_apt_dat_stamp", "displacement_by_role", "with_join_yield",
           "post_solve", "emit"]


def borrowed_apt_dat_stamp(path: str | None) -> dict[str, str]:
    """The freshness stamp for §44's BORROWED Global Airports apt.dat.

    ``{}`` when nothing was borrowed (the empty path), else
    ``{"o4_apt_dat_borrowed_mtime": "<mtime>.6f"}`` — the same rendering
    ``auto_patch/engine_v2._stamp_header`` gives ``o4_apt_dat_mtime``, so
    the two mtimes compare the same way in the gate.  An ``OSError``
    (the borrowed file vanished between the load stage and the emit)
    OMITS the key, exactly as ``_stamp_header`` does for ``o4_apt_dat``
    — and the gate reads a non-empty ``o4_apt_dat_borrowed`` with no
    mtime as "not current" (fail-safe), so the patch rebuilds once.

    The PATH itself rides RAW (``o4_apt_dat_borrowed``, written beside
    this key since §44 (4)), XML-escaped by the emitter's ``_q``; only
    ``o4_apt_dat`` is percent-encoded, and by the v1 host's
    ``header_extra``.  ``layout.read_patch_source`` reads each back in
    the encoding it is written in.
    """
    if not path:
        return {}
    try:
        return {"o4_apt_dat_borrowed_mtime": f"{os.path.getmtime(path):.6f}"}
    except OSError:
        return {}


#: The report's "moved" threshold (metres off the DEM sample) — a report
#: figure (M3b §4 / M5), not a law value.
MOVED_M = 0.5


def displacement_by_role(pm: PlanarMap, law: Law, sol: Solution
                         ) -> dict[str, dict[str, _t.Any]]:
    """Per role (a vertex counts for the SENIOR role touching it): how
    many vertices sit more than :data:`MOVED_M` off their DEM sample, and
    the largest such displacement — the M5 "what yielded where" figure."""
    from ..law.tables import senior_role, tiers
    tier_of = {r: k for k, t in enumerate(tiers(law)) for r in t}  # report order only
    acc: dict[str, dict[str, _t.Any]] = {}
    for vid, v in pm.vertices.items():
        if v.dem_z is None or not v.incident_faces:
            continue
        roles = [pm.faces[f].role for f in v.incident_faces]
        role = senior_role(law, roles)
        rec = acc.setdefault(role, {"tier": tier_of.get(role), "vertices": 0,
                                    "over": 0, "max_m": 0.0})
        d = abs(sol.z[vid] - v.dem_z)
        rec["vertices"] += 1
        if d > MOVED_M:
            rec["over"] += 1
        rec["max_m"] = max(rec["max_m"], d)
    for rec in acc.values():
        rec["max_m"] = round(rec["max_m"], 3)
    return dict(sorted(acc.items(), key=lambda kv: (kv[1]["tier"] is None, kv[1]["tier"])))


def with_join_yield(icao: str, pm, law: Law, airport, sol, pin_yield,
                    out: _t.Callable[[str], None]):
    """``pm`` with the solve's released §37 (9) join pins taken (owner
    RULINGS 2026-09-27a (10)), each one said."""
    # OWNER RULINGS 2026-09-27a (10): THE RIBBON YIELDS where the solve
    # released a §37 (9) join pin — the join takes the patch's level and
    # the sidecar tells the core clamp to follow (``road_join_yield``)
    # joinyield128: a join on AIRSIDE was never pinned — the ribbon takes
    # the airside's solved level there (``road_ramp.airside_joins``)
    from ..constraints.road_ramp import airside_joins
    from ..emit.road_join import with_pin_yield
    pm = with_pin_yield(pm, pin_yield,
                        float(law.tables.emit.materiality.elevation_m),
                        withheld=airside_joins(pm, law),
                        z=sol.z or None)
    _to_ll = airport.frame.transformers()[1] if pm.road_join_yield else None
    for _v, (_rib, _zp) in sorted(pm.road_join_yield.items()):
        _lat, _lon = _to_ll(*pm.vertices[_v].xy)
        out(f"[{icao}] JOIN YIELD (27a (10)): v{_v} at {_lat:.8f},{_lon:.8f} "
             f"ribbon {_rib:.3f} -> patch {_zp:.3f} (excess {_zp - _rib:+.3f} m; "
             f"the core ribbon takes the patch level beyond its budget)")
    return pm


def post_solve(icao: str, pm, law: Law, airport, sol, cs, design_rep, tt_rep, fv, lrep,
               seam_yielded: list, out: _t.Callable[[str], None]) -> dict[str, _t.Any]:
    """THE READS OF THE SOLVED SURFACE before emit: the runway / taxi /
    apron blocks into ``design_rep``, the flat-site datum rows into
    ``lrep``, and ``{"moved", "envelope", "off_ground", "seam",
    "road_agree"}`` for the report — each said."""
    # THE REPORT NAMES THE RESIDUAL PER RUNWAY (spec §21.2 (4)): the built
    # ridge against the target profile it was given, its mean |z - DEM| and
    # the law row holding it where it did not reach.
    if sol.z:
        from .runway_report import runway_profile_block
        design_rep.runway_profile = runway_profile_block(pm, law, airport, cs, sol.z)
        # ... beside what the publisher covered (§61: the feet it named, the
        # ones past the reach or on a face no chain owns, the chains no fit)
        design_rep.taxi_trend = {
            **taxi_trend_block(pm, law, sol.z),
            **{k: tt_rep[k] for k in ("xsec_vertices", "xsec_pin_const",
                                      "xsec_far", "xsec_no_chain",
                                      "chains_without") if k in tt_rep}}
        design_rep.apron_trend = apron_trend_block(pm, law, sol.z)
        for r in design_rep.runway_profile["runways"]:
            out(f"    runway {r['runway']} ({r['kind']}, window {r['window_m']:.0f} m): "
                 f"target RMS {r['target_rms_m']:.3f} m, max {r['target_max_m']:.3f} m; "
                 f"|z-DEM| mean "
                 + ("-" if r["dem_mean_abs_m"] is None else f"{r['dem_mean_abs_m']:.3f} m")
                 + f"; bow vs straight chord {r['chord_bow_m']:+.2f} m; binding "
                 + (f"{r['binding']} (slack {r['binding_slack_m']:.3f} m)"
                    if r["binding"] else "nothing"))
    if fv.substitutes and sol.z:
        tol = law.tables.emit.materiality.elevation_m
        dz = [abs(sol.z[r.terms[0][0]] - r.hi) for r in cs.linears
              if r.source.generator == FLAT_GEN]
        held = sum(1 for d in dz if d <= tol)
        lrep.flat_site["rows"] = len(dz)
        lrep.flat_site["rows_at_datum"] = held
        lrep.flat_site["max_off_datum_m"] = round(max(dz), 3) if dz else 0.0
        out(f"[flat-site] {icao}: {held}/{len(dz)} datum rows at Z0 {fv.z0_m:.2f} "
             f"(max off {lrep.flat_site['max_off_datum_m']:.3f} m; the law rows outrank "
             f"the preference where they differ)")
    moved = displacement_by_role(pm, law, sol) if sol.z else {}
    if moved:
        out(f"[{icao}] off-DEM > {MOVED_M} m by role: " + ", ".join(
            f"{r} {v['over']}/{v['vertices']} (max {v['max_m']:.2f})"
            for r, v in moved.items() if v["over"]))
    # issue #623 THE GROUND ENVELOPE: a solved vertex outside every level
    # the airport's ground holds is named here and FAILS the airport in the
    # driver (``auto_patch/engine_v2.py``) — the solve cannot see it, a
    # wrong datum is met exactly and the status is optimal.
    _envelope = ground_envelope(pm, law)
    off_ground = outside_envelope(pm, sol.z, _envelope) if sol.z else []
    if off_ground:
        w = off_ground[0]
        out(f"[{icao}] OFF THE GROUND: {len(off_ground)} solved vertex(es) "
             f"outside the ground envelope [{_envelope[0]:.2f}, "
             f"{_envelope[1]:.2f}] m — worst {w['z_m']:.2f} m over a DEM of "
             f"{w['dem_m']} m at ({w['lat']}, {w['lon']}); the app build "
             f"fails this airport (issue #623)")
    if sol.status.value in ("optimal", "feasible") and pm.seam_vertices:
        tol = law.tables.emit.materiality.elevation_m
        res_seam = sorted(((abs(sol.z[v] - pm.vertices[v].dem_z), v)
                           for v in pm.seam_vertices if pm.vertices[v].dem_z is not None),
                          reverse=True)
        off = [(d, v) for d, v in res_seam if d > tol]
        report_seam = {"seam_vertices": len(pm.seam_vertices), "honoured": len(res_seam) - len(off),
                       "residual": [{"vertex": v, "off_dem_m": round(d, 3)} for d, v in off]}
        # §38 (2) A FAMILY UNMET BETWEEN TWO PINS IS NAMED (owner RULINGS
        # 2026-09-13ah: "never a moved pin, never a silent residual").  The
        # rows the seam pin made the zone band yield, read at the SOLVED
        # surface: the pin, the family, and demanded vs allowed metres.
        report_seam["yielded"] = seam_yield_block(pm, law, seam_yielded, sol.z)
        out(f"[{icao}] seam: {report_seam['honoured']}/{len(res_seam)} vertices on the DEM; "
             f"{len(off)} residual" + (f", max {off[0][0]:.3f} m at vertex {off[0][1]}" if off else ""))
        yb = report_seam["yielded"]
        out(f"[{icao}] seam yield (38.2): {yb['rows']} row(s) yielded to a seam pin"
             + (f", {yb['unmet']} still unmet at the solved surface"
                f" (worst {yb['worst_m']:.3f} m: " + "; ".join(yb["named"]) + ")"
                if yb["unmet"] else " — every one met at the solved surface"))
    else:
        report_seam = None
    road_agree = None
    if sol.status.value in ("optimal", "feasible") and pm.preferred_z:
        from ..verify.roads import road_profile_agreement
        road_agree = road_profile_agreement(pm, law, sol.z)
        out(f"[{icao}] roads vs core profile: {road_agree['vertices']} vertices, "
             f"mean |z-profile| {road_agree['mean_m']:.3f} m, max {road_agree['max_m']:.3f} m, "
             f"{road_agree['off']} off beyond materiality in {road_agree['faces_off']} "
             f"of {len(road_agree['faces'])} faces")
    if sol.residual is not None:
        r = sol.residual
        out(f"    residual: pin {r.max_pin_m:.4f} diff {r.max_diff_m:.4f} "
             f"flat {r.max_flat_m:.4f} band {r.max_band_m:.4f} "
             f"offset {r.max_offset_m:.4f} m  objective {r.objective:.2f}")
    return {"moved": moved, "envelope": _envelope, "off_ground": off_ground,
            "seam": report_seam, "road_agree": road_agree}


def emit(icao: str, *, pm, law: Law, airport, sol, cs, cl, strips, design_rep,
         yield_records, late_report, lrep, header_extra, out_dir, objects_out,
         report: dict, wall: dict, out: _t.Callable[[str], None]) -> tuple:
    """THE EMIT (spec §4b.6): the patch, its sidecar and tile pieces written
    into ``out_dir``, the rebake screen (or the inline plan) beside them;
    ``report`` takes ``warnings``, ``shore_weld``, ``rebake_plan``,
    ``rebake_screen`` and ``emit``, ``wall`` the stage clocks.  Returns
    ``(paths, pieces, surf, pub)`` — ``surf`` and ``pub`` are what verify
    reads."""
    pieces = None
    t = time.perf_counter()
    _pulse.tick("emitting the patch")
    from .publication import jetway_strips_ll
    _strip_records = jetway_strips_ll(pm, airport, strips,
                                      design_rep.jetway_strip)
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs,
                          {"law_ruleset": law.ruleset_key,
                           "pack": airport.pack.name,
                           # §50.4: the yielded runways ride the
                           # surface's own provenance (an open object)
                           "runway_cap_yield": yield_records,
                           # jetway-strip spec §4 (C17): the object
                           # stage seats the riders off this
                           "jetway_strips": _strip_records})
    pub = publication(pm, law, airport, sol.z, cs, strips=strips,
                      strip_rep=design_rep.jetway_strip)
    # THE DESIGN SURFACE's own publication (RULINGS 2026-09-08t/v): the
    # residual per family (``design``, replacing ``law_tiers``) and the
    # rows the surface missed (``design_target``), which the census
    # counts law-true in their families and reports under one heading
    pub["design"] = design_rep.as_dict()
    # spec §56 (3) (owner 07c (6) "warn and explain"): the fixed line of
    # every block whose released frontage weld is over the bar — the
    # engine says each ONCE through its warning path (``auto_patch/
    # driver``: ``UI.loud_warning``); this package prints nothing
    from ..constraints.pad_warning import warnings_of
    report["warnings"] = warnings_of(pub.get("platforms"))
    from .publication import gap_pieces, late_stage, pad_touch
    _gap_records = gap_pieces(late_report and late_report["cut"], cl.cells)
    if late_report is not None or _gap_records:
        pub["gap_pieces"] = _gap_records
    if late_report is not None:
        pub["late_stage"] = late_stage(late_report["stage"])
    _touch = pad_touch(cl.cells, law, pm)
    if _touch:
        pub["pad_touch"] = _touch
    pub["design_target"] = design_rep.targets
    js = report["joint_steps"]
    if js and js["contours"]:
        worst = max(js["contours"], key=lambda c: c["step_m"])
        out(f"[{icao}] joint steps (08k): {len(js['contours'])} joints, max step "
             f"{worst['step_m']:.2f} m (joint {worst['id']}, {worst['length_m']:.0f} m, "
             f"shapes {worst['shapes']}, {'gap' if worst['gap'] else 'contour'}, "
             f"{'/'.join(worst['roles'])}); by roles " + ", ".join(
                 f"{k} {v['edges']} edges max {v['max_step_m']:.2f}" for k, v in sorted(js["by_roles"].items()))
             + (f"; roads: " + ", ".join(f"#{r['face']} {r['ref']} {r['step_m']:.2f} m"
                                         for r in js["roads"][:8]) if js["roads"] else ""))
    if js and js.get("ramps"):
        short = [r for r in js["ramps"] if r["too_short"]]
        out(f"[{icao}] road ramps (08r-2): {len(js['ramps'])} roads crossing between shapes, steepest "
             + ", ".join(f"#{r['face']} {r['ref']} {r['dz_m']:.2f} m over {r['length_m']:.0f} m = "
                         f"{100 * r['grade']:.2f} % (shapes {r['shapes']})" for r in js["ramps"][:6])
             + (f"; TOO SHORT (at the cap): " + ", ".join(f"#{r['face']} {r['ref']}" for r in short)
                if short else "; none at the cap"))
    header = {"o4_apt_dat": airport.pack.apt_dat_path,
              "o4_pack": airport.pack.name,
              # §44 (4): the Global Airports apt.dat this patch
              # borrowed its pavement from ("" = nothing borrowed)
              "o4_apt_dat_borrowed": airport.pack.borrowed_apt_dat_path}
    header.update(borrowed_apt_dat_stamp(
        airport.pack.borrowed_apt_dat_path))
    header.update(header_extra or {})
    # THE TERRAIN EDGE (owner RULINGS 2026-09-10b/10c, spec §19.3 C12):
    # the edge segments published as open ways over the vertices they
    # already run through — the owner's KML read of where ground ends
    surf_out = with_terrain_edges(surf, pm, law)
    # §39 (1) THE HAIRLINE LAW / THE SHORE WELD (owner RULINGS
    # 2026-09-13bk): the LAST thing done to the surface before it is
    # written, at the one site every ring passes through.  No emitted
    # vertex may stand beside a foreign constrained edge; where the
    # bank followed the water line it now SHARES the water's own
    # vertices.  The edges are published so the ``hairline_pair``
    # census prices exactly the population the weld ran against.
    wrep = WeldReport()
    shore = shore_edges_of(airport.dem, surf_out)
    surf_out = weld_to_shore(surf_out, law, shore, wrep)
    # §39 (iii) (owner RULINGS 2026-09-13cg): and the identity join
    # MERGES a sub-spacing segment rather than writing one — after the
    # weld, whose projection can itself bring two vertices together.
    surf_out = merge_sub_spacing(surf_out, law, wrep)
    out(wrep.line(icao))
    report["shore_weld"] = _dc.asdict(wrep)
    pub["shore_edges"] = [[a[0], a[1], b[0], b[1]] for a, b in shore]
    # OWNER RULINGS 2026-10-02ag (2) (#100): the vertices the strip tie is
    # withdrawn under (road cap governs) — the census reads the same set
    from ..law.tables import airside_stage_roles as _asr
    rc_vs = pm.road_cap_vertices(_asr(law))
    if rc_vs:
        _to_ll_rc = airport.frame.transformers()[1]
        pub["road_cap_governs"] = [list(_to_ll_rc(*pm.vertices[v].xy))
                                   for v in sorted(rc_vs)]
    # OWNER RULINGS 2026-10-15j: a non-runway pavement's own lip inside a
    # runway end area — the end laws yield there; both readers skip it
    from .publication import end_profile_yields as _epy
    _lip = _epy(pm, law, airport)
    if _lip:
        pub["end_profile_yields"] = _lip
    # OWNER RULINGS 2026-10-03b (#100): the terrace's second witness — a
    # pack fence / wall line along a bordered ribbon run (REPORT ONLY)
    from .terrace_witness import terrace_witness
    _wit = terrace_witness(pm, airport, sol.z, load_rules(), lrep.dsf_dump_path,
                           law=law)
    if _wit:
        pub["road_terrace_witness"] = _wit
    out(f"[{icao}] road terrace witness (10-03b, report only): {len(_wit)} "
         "fence/wall line(s) along a bordered road run"
         + "".join(f"; {w['object']} {w['length_m']} m road {w['road_m']['mean']} m"
                   + (f" dem {w['dem_m']['min']}..{w['dem_m']['max']} m"
                      if 'dem_m' in w else "") for w in _wit[:6]))
    wedges = getattr(pm, "natural_shore_wedges", ()) or ()
    if wedges:
        _to_ll = airport.frame.transformers()[1]
        pub["natural_shore"] = [[list(_to_ll(x, y)) for x, y in ring]
                                for ring in wedges]
    paths = write_patch(surf_out, law, out_dir, pub, header,
                        face_tags(pm, law, airport))
    if pm.seam_vertices:
        pieces = write_tile_pieces(surf_out, law, out_dir, pub, header,
                                   face_tags(pm, law, airport))
    wall["emit"] = time.perf_counter() - t
    out(f"[{icao}] emit {wall['emit']:.2f} s  ways {paths.ways}  nodes {paths.nodes}"
         f"  patch {paths.bytes_patch} B  sidecar {paths.bytes_sidecar} B")
    rplan, rscreen = _rebake(icao, pm, law, surf, airport, objects_out, paths, pieces,
                             out_dir, wall, out)
    for (tl, tn), pp in (pieces or {}).items():
        out(f"    tile {tl:+03d}{tn:+04d}: ways {pp.ways}  nodes {pp.nodes}  "
             f"-> {pp.patch}")
    report["rebake_plan"] = None if rplan is None else {
        "path": str(Path(out_dir) / f"{icao}.rebake.json"),
        "counts": dict(rplan.counts), "skipped": len(rplan.skipped)}
    report["rebake_screen"] = None if rscreen is None else {
        "path": str(Path(out_dir) / f"{icao}.rebake.screen.json"),
        "partition_fp": rscreen.partition_fp,
        "patch_bodies": list(rscreen.patch_bodies)}
    report["emit"] = {"patch": str(paths.patch), "sidecar": str(paths.sidecar),
                      "ways": paths.ways, "nodes": paths.nodes,
                      "bytes_patch": paths.bytes_patch,
                      "bytes_sidecar": paths.bytes_sidecar,
                      # a scalar sidecar key (``seam_half_width_m``) is reported as its
    # own value; every other key is a collection and reports its size
    "published": {k: (len(v) if hasattr(v, "__len__") else v)
                  for k, v in pub.items()},
                      "tiles": {f"{tl:+03d}{tn:+04d}": {"patch": str(pp.patch),
                                                         "ways": pp.ways,
                                                         "nodes": pp.nodes}
                                for (tl, tn), pp in (pieces or {}).items()}}
    return paths, pieces, surf, pub


def _rebake(icao: str, pm, law: Law, surf, airport, objects_out, paths, pieces, out_dir,
            wall: dict, out: _t.Callable[[str], None]) -> tuple:
    """The rebake SCREEN beside the patch, or the inline plan when no
    partition cache was kept: ``(plan or None, screen or None)``."""
    # THE RE-BAKE PLAN LEAVES THE PATCH BUILD (owner RULINGS 2026-10-04x
    # (1), issue #362; RULINGS 04f-1 for the plan itself).  The plan is
    # object-stage work the patch never reads, so what is written HERE
    # is the SCREEN SIDECAR — the planar and solved facts ``plan()``
    # needs beyond the cached partition (``airport/rebake_screen``) —
    # and the tile build's object step builds the plan from the two.
    # A run that kept NO partition cache has nothing to defer onto and
    # plans inline, exactly as before.
    t = time.perf_counter()
    _pulse.tick("the object re-bake screen")
    rplan = rscreen = None
    if objects_out:
        _plan_args = _rebake_inputs(pm, law, surf, airport)
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        rscreen = _rscreen.take(
            airport, objects_out[0], law,
            patches=[paths.patch] + [pp.patch for pp in (pieces or {}).values()],
            **_plan_args)
        if rscreen is not None:
            screen_path = Path(out_dir) / f"{icao}.rebake.screen.json"
            screen_path.write_text(rscreen.to_json(), encoding="utf-8", newline="\n")
            wall["rebake_screen"] = time.perf_counter() - t
            out(f"[{icao}] rebake screen {wall['rebake_screen']:.2f} s  "
                 f"excluded {len(rscreen.excluded)}  plates {len(rscreen.plates)}  "
                 f"below-grade regions {len(rscreen.below_grade)}  "
                 f"deck rings {len(rscreen.deck_datum)}  — the plan is built by "
                 f"the object step from partition {rscreen.partition_fp[:12]}"
                 f"  -> {screen_path}")
        else:
            # no extension cache without a partition cache: nothing is kept
            rplan = rebake_plan(airport, objects_out[0], objects_out[1], law,
                                partition=airport.partition,
                                keep_extension=False, **_plan_args)
            rebake_path = Path(out_dir) / f"{icao}.rebake.json"
            rebake_path.write_text(rplan.to_json(),
                                   encoding="utf-8", newline="\n")
            wall["rebake_plan"] = time.perf_counter() - t
            from ..airport.partition_cache import companion_notes as _cnotes
            for _ln in _cnotes():               # [extension] cache OFF
                out("  " + _ln)
            out(_rscreen.plan_line(icao, rplan, wall["rebake_plan"])
                 + f"  (inline: no partition cache was kept)  -> {rebake_path}")
    return rplan, rscreen
