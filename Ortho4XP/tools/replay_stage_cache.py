"""THE CAPTURE'S FRONT HALF THROUGH THE V2 STAGE CACHE (issue #844, B3-12;
stage-cache spec §7 ``tools/v2_solve_replay.py`` bullets, §10 step 5).

``tools/v2_solve_replay.py --capture`` runs classify → planar → flat site →
road profile → shape stage; :func:`front_half` is that sequence, each stage
handed to ``pipeline/front_cache.FrontCache.run`` exactly as
``pipeline/build.py`` hands it — the same stage functions, the same input
digests, the same record payloads — so the ONE writer of a stage record is
``FrontCache`` (never a second spelling of the store).  Three modes:

* ``off`` — the cache is bypassed (``FrontCache(enabled=False)``): every
  stage runs, nothing is read or written.  The capture's default.
* ``write`` — ``--capture … --stage-cache``: records are served when their
  key and witnesses hold, else computed AND written.  The spec's "MAY"
  (§7) is taken behind this explicit flag: the capture is the one replay
  path that writes.
* ``read`` — ``--replay-cache ICAO``: served when present, a miss is
  computed and NEVER written (``FrontCache(write=False)``, the
  ``topology_cache`` rule: replays and tools write nothing).

THE KEYS ARE THE BUILD'S where the capture computes what the build computes
(classify, planar, flat_site, road_profile), so a build's record serves a
capture of the same airport and inputs and the other way round.  The
capture's SHAPE STAGE runs on the map BEFORE the target channels
(``pipeline/build`` runs the channels first, then the shape stage), so its
record carries one more input, ``targets`` = :data:`CAPTURE_SHAPES` — a
different key, never a build's shape record under a capture's name.

THE REGISTRIES (§7): the planar record carries ``capture_state.collect()``
of the map's registries; a record that does not carry every declared field
is a ``capture_state.missing()`` REFUSAL, by field name, before anything is
built on it.  ``--why-miss``: per record of a stage that did not hit, the
first recipe field that differs from the key asked for
(``stage_cache.why_miss`` over ``stage_cache.peek``).

Twin: ``tests/test_v2_replay_stage_cache.py`` (synthetic, no corpus).
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

__all__ = ["MODES", "CAPTURE_SHAPES", "front_half", "why_miss_lines"]

MODES = ("off", "write", "read")

#: the shape record's extra input: the capture's shape stage sees the map
#: WITHOUT the target channels (module doc)
CAPTURE_SHAPES = "none"

FRONT_STAGES = ("classify", "planar", "flat_site", "road_profile", "shapes")


def why_miss_lines(icao: str, fc: _t.Any) -> list[str]:
    """``--why-miss``: one line per stage that did not hit, then one per
    record of that stage on disk with the first recipe field it differs
    in (``same key`` for the record of the very key, refused as its stage
    line says)."""
    lines: list[str] = []
    stages = fc.report.get("stages", {})
    for st in FRONT_STAGES:
        rep = stages.get(st)
        if not rep or rep.get("state") == "hit":
            continue
        lines.append(f"[{icao}] why-miss {st}: {rep.get('state')} "
                     f"(key {rep.get('key', '-')})")
        recs = fc.why_miss(st)
        if not recs:
            lines.append(f"[{icao}]   no record of {st} on disk")
        for name, field in recs:
            lines.append(f"[{icao}]   {name}: "
                         + ("same key" if field is None else f"recipe:{field}"))
    return lines


def _refuse_registries(icao: str, record: _t.Any, key: str | None) -> None:
    """The §7 refusal: a planar record without its registries record."""
    from auto_patch_v2.pipeline import capture_state as _cstate
    gone = _cstate.missing(record)
    if gone:
        raise SystemExit(_cstate.refusal(
            icao, "planar", f"the stage cache's planar record (key {key or '-'})",
            gone, "Delete that record (o4_stage_<ICAO>_planar_<key>.cache in the "
                  "pack's mod-cache folder) and re-capture with --stage-cache."))


def front_half(icao: str, airport: _t.Any, law: _t.Any, inputs: _t.Any, *,
               ocache: _t.Any, pack_objects: _t.Any, pack_report: _t.Any,
               rules: _t.Any, mode: str = "off", why_miss: bool = False,
               out: _t.Callable[[str], None] = print) -> dict[str, _t.Any]:
    """Classify → planar → flat site → road profile → shape stage on the
    partitioned ``airport``, through the stage cache in ``mode`` (module
    doc).  Returns ``{"airport", "cl", "pm", "stage", "planar_record",
    "cache"}`` — ``airport`` with its own DEM (never the recorder) and
    the flat site, ``pm`` the planar map with the preferred road z,
    ``cache`` the ``FrontCache`` report."""
    if mode not in MODES:
        raise ValueError(f"stage-cache mode {mode!r}: one of {MODES}")
    from auto_patch_v2.airport.flat_site_read import verdict_for_build
    from auto_patch_v2.airport.road_profile import preferred_road_z
    from auto_patch_v2.classify import classify as _classify
    from auto_patch_v2.pipeline import capture_state as _cstate
    from auto_patch_v2.pipeline import front_cache as _front
    from auto_patch_v2.pipeline.build import _classified_land
    from auto_patch_v2.pipeline.shapes import shape_stage
    real_dem = airport.dem
    fc = _front.FrontCache(icao, airport, law, enabled=mode != "off",
                           mod_cache_root=getattr(inputs, "mod_cache_root", None),
                           pack=(pack_objects, pack_report), write=mode == "write")
    airport = fc.airport(airport)
    fc.window(True)
    fc_in = fc.common_inputs(rules, ocache)
    cl, side = fc.run(
        "classify", {**fc_in, "airport": fc.airport_digest(airport)},
        lambda lw: (_classify(airport, lw, rules, cache=ocache),
                    _front.classify_side_state()), as_served=True)
    _front.install_classify_side_state(side)
    cl_d = fc.output_digest("classify")
    pm, _pstats, record = fc.run(
        "planar", {**fc_in, "airport": fc.airport_digest(airport), "classification": cl_d},
        lambda lw: _cstate.planar_stage(airport, cl, lw, cache=ocache, objects=pack_objects,
                                        object_report=pack_report))
    _refuse_registries(icao, record, fc.report["stages"].get("planar", {}).get("key"))
    fv, _how = fc.run(
        "flat_site", {**fc_in, "airport": fc.airport_digest(airport),
                      "planar": fc.output_digest("planar"), "classification": cl_d},
        lambda lw: verdict_for_build(airport, lw, objects=pack_objects,
                                           land=_classified_land(cl)))
    airport = _dc.replace(airport, flat_site=fv)
    ap_d = fc.airport_digest(airport, flat_site=fc.output_digest("flat_site"))
    params = repr((inputs.road_grade_limit, inputs.lane_width_m))
    road_pref, _rrep, _prof = fc.run(
        "road_profile", {**fc_in, "airport": ap_d, "planar": fc.output_digest("planar"),
                         "params": params},
        lambda lw: preferred_road_z(airport, pm, lw, inputs.road_grade_limit,
                                          inputs.lane_width_m))
    pm = _dc.replace(pm, preferred_z=road_pref)
    _cstate.install(pm.registries, record)          # #840, as the build does

    def _shape(lw):
        lines: list[str] = []
        return shape_stage(pm, lw, airport, cl, out=lines.append), lines
    stage, shape_lines = fc.run(
        "shapes", {**fc_in, "airport": ap_d, "planar": fc.output_digest("planar"),
                   "road_profile": fc.output_digest("road_profile"),
                   "classification": cl_d, "params": params, "targets": CAPTURE_SHAPES},
        _shape)
    fc.close()
    for ln in shape_lines:
        out(ln)
    rep = fc.finish()
    if fc.active:
        airport = _dc.replace(airport, dem=real_dem)
        out(f"[{icao}] stage cache ({mode}): " + ", ".join(
            f"{st} {rep['stages'].get(st, {}).get('state', '-')}" for st in FRONT_STAGES))
    else:
        out(f"[{icao}] stage cache: {rep.get('state')}")
    if why_miss:
        for ln in why_miss_lines(icao, fc):
            out(ln)
    return {"airport": airport, "cl": cl, "pm": pm, "stage": stage,
            "planar_record": record, "cache": rep}
