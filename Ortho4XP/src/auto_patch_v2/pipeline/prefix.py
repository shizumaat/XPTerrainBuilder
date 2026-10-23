"""THE BUILD'S PREFIX, ONE NAMED FUNCTION (stage-cache spec §4b.3, §10 step
8): planar → flat site → the preferred road profile → the target channels
→ the shape stage → the constraint generators → the jetway strips → the
hold binding, for one classification.

The main pass runs it on the build's classification through the build's
cache (``pipeline/front_cache.py``; the constraint and jetway-strip records
of ``pipeline/constraint_records.py``); the ribbon-free pass
(``stage_one_map.stage_one_problem``) and the late stage's derives
(``late_stage``) run it on another classification through the SAME records,
each keyed by its own classification and map (spec §4b.3, a
:class:`Deriver` holding the cache); ``tools/v2_solve_replay.py`` runs it
with no cache.  The main pass says its lines; a re-run is silent."""
from __future__ import annotations

import dataclasses as _dc
import time
import types as _types
import typing as _t

from ..airport import flat_site as _flat
from ..airport.flat_site_read import verdict_for_build as _flat_verdict
from ..airport.road_descent import descent_line
from ..airport.road_profile import preferred_road_z
from ..airport.road_ramp import with_road_ramp
from ..classify import load_rules
from ..constraints.apron_trend import ApronTrendReport, with_apron_trend
from ..constraints.eat import withdraw_trend_over_reach
from ..constraints.runway_chord import ChordReport, with_runway_chord
from ..constraints.runway_yield import yielded_lines
from ..constraints.taxi_trend import TaxiTrendReport, with_taxi_trend
from ..emit.road_join import with_road_coverage_join
from ..model import pulse as _pulse
from ..planar.build import build as build_planar
from . import capture_state as _cstate
from .constraint_records import constraints_stage, strips_stage
from .planar_report import say_planar
from .shapes import shape_stage

__all__ = ["PackRead", "PrefixRecord", "Deriver", "run_prefix", "classified_land"]


class PackRead(_t.NamedTuple):
    """The pack the build read once (``pipeline/build.pack_stage``): its
    placed objects, their report and the run's ``ResourceCache``."""

    objects: _t.Any
    report: _t.Any
    resources: _t.Any


@_dc.dataclass
class PrefixRecord:
    """What one prefix run produced.  ``airport`` carries the flat-site
    verdict; ``planar_pm`` is the planar stage's map before the target
    channels, ``pm`` the shape stage's; ``reports`` the channel reports
    (``runway_chord``, ``taxi_trend``, ``apron_trend``, ``eat_reach``,
    ``road_ramp``); ``planar_record`` the planar stage's registries record
    (``None`` on a re-run, which installs none); ``wall`` the step clocks."""

    airport: _t.Any
    planar_pm: _t.Any
    pstats: _t.Any
    planar_record: _t.Any
    flat_how: str
    road_rep: dict
    road_profiles: _t.Any
    reports: dict
    yield_records: list
    stage: _t.Any
    pm: _t.Any
    cs: _t.Any
    counts: dict
    gwalls: dict
    seam_yielded: list
    strips: _t.Any
    hold: _t.Any
    wall: dict
    #: the run's record identities the solve and the late stage are keyed on
    #: (``pm`` the shape stage's output digest, ``airport``, ``assembly`` the
    #: assembly's KEY, ``strips`` the strips' output digest, ``chain`` the
    #: DEM chain after them); empty with no cache, ``None`` where a step was
    #: not cached
    keys: dict = _dc.field(default_factory=dict)

    def derived(self) -> tuple:
        """``(pm, cs, strips, hold)`` — what ``stage_one_problem`` and
        ``late_stage.run_last_stages`` take from a ``derive``."""
        return self.pm, self.cs, self.strips, self.hold


def classified_land(classification):
    """§37 (11) (4) THE AIRPORT'S OWN SURFACES ARE LAND BY DECLARATION
    (owner RULINGS 2026-09-15f item 2; Fable 2026-09-15i) — the union of
    every classified cell, for the flat-site datum region's water cut.

    It is the SAME declaration ``planar/zones.shore_region`` makes for
    the zone trim and ``constraints/water.water_pins`` has always made
    ("an apron over water is a deck, not water"); read from the
    classification so there is one source and not three."""
    from shapely.geometry import Polygon as _P
    from shapely.ops import unary_union as _u
    cells = list(getattr(classification, "cells", ()) or ())
    if not cells:
        return None
    land = _u([_P(c.ring, c.holes) for c in cells])
    return None if land.is_empty else land


def _run(cache, law, stage: str, inputs: _t.Callable[[], dict], fn):
    """``fn(law)`` through ``cache``'s ``stage`` record (keyed on
    ``inputs()``), or plainly when there is no cache."""
    return fn(law) if cache is None else cache.run(stage, inputs(), fn)


def _channels(icao: str, pm, law, law_c, airport, road_profiles, road_rep, road_s: float,
              lrep, out: _t.Callable[[str], None]) -> tuple[_t.Any, list]:
    """THE TARGET CHANNELS in their order, and their lines: ``(pm, the §50.4
    yielded-runway records)``; the reports go into ``lrep``."""
    # THE RUNWAY PROFILE (RULINGS 2026-09-08d (1) / 09-10q/10r/10t (3), spec
    # §21; ``constraints/runway_chord.py``): every runway-family vertex of a
    # two-pin runway takes the TARGET PROFILE at weight ``[design] chord`` —
    # the ground's long-wave trend through the threshold pins, or the
    # straight chord where the DEM frame is degraded.  The DEM fit stays for
    # every other role.
    chord_rep: ChordReport = {}
    pm = with_runway_chord(pm, law_c, airport, chord_rep)
    lrep.runway_chord = dict(chord_rep)
    out(f"[{icao}] runway profile (08d-1/10t-3): target {chord_rep.get('target_kind', '-')} "
         f"(window {chord_rep.get('window_m', 0.0):.0f} m, {chord_rep.get('runways_trend', 0)} trend / "
         f"{chord_rep.get('runways_chord', 0)} chord"
         + (f", FALLBACK {chord_rep['fallback']}" if chord_rep.get("fallback") else "")
         + f"); {chord_rep.get('runways', 0)} runways with two pins "
         f"({chord_rep.get('runways_without', 0)} without, DEM fit kept)  vertices "
         f"{chord_rep.get('vertices', 0)}  target above DEM up to {chord_rep.get('max_above_dem_m', 0.0):.2f} m, "
         f"below up to {chord_rep.get('max_below_dem_m', 0.0):.2f} m"
         + ("; off the straight chord " + ", ".join(
             f"{r['runway']} {r['trend_max_off_chord_m']:+.2f}" for r in chord_rep.get("by_runway", [])[:6])
            if chord_rep.get("by_runway") else ""))
    # §50.4 THE ONE LOUD LINE (owner RULINGS 2026-09-18d (3)): one line per
    # OVER-GRADE runway, naming the grade its own pins demand, the two pins
    # and the cap they exceeded.  A LINE, never a gate — no verify family
    # is added and ``defect_gate`` is untouched.  Recorded in three places
    # from ONE record: ``report.json["runway_cap_yield"]`` (here, through
    # ``lrep``), the GradedSurface provenance key of the same name, and the
    # sidecar law key ``runway_caps`` (EVERY runway, yielded or not).
    _caps = dict(getattr(pm, "runway_caps", {}) or {})
    _yield_records = [rc.as_dict(law.ruleset_key)
                      for _r, rc in sorted(_caps.items()) if rc.yielded]
    for _line in yielded_lines(icao, _caps, law.ruleset.authority):
        out(_line)
    # THE TAXI CHAIN'S TARGET PROFILE (owner RULINGS 2026-09-10v (1); spec
    # §8.6): every taxi centreline chain takes the ground's LONG-WAVE TREND
    # along itself — the same §21 fit at the same window — shifted linearly
    # through the chain's runway contacts, at the WEAK ``[design]
    # taxi_trend``.  Fitted AFTER the runway profile, because a chain's
    # runway contact is pinned to the runway's own target.
    tt_rep: TaxiTrendReport = {}
    pm = with_taxi_trend(pm, law_c, airport, tt_rep)
    lrep.taxi_trend = dict(tt_rep)
    out(f"[{icao}] taxi profile (10v-1): {tt_rep.get('chains', 0)} chains "
         f"({tt_rep.get('chains_without', 0)} without a fit) "
         f"window {tt_rep.get('window_m', 0.0):.0f} m  vertices "
         f"{tt_rep.get('vertices', 0)}  shifted through "
         f"{tt_rep.get('pins', 0)} runway contacts  target above DEM up to "
         f"{tt_rep.get('max_above_dem_m', 0.0):.2f} m, below up to "
         f"{tt_rep.get('max_below_dem_m', 0.0):.2f} m"
         + (f"; FALLBACK {tt_rep['fallback']}" if tt_rep.get("fallback") else ""))
    # THE APRON BODY'S TARGET SURFACE (owner RULINGS 2026-09-10ar; spec
    # §8.7): an apron body LARGER THAN THE FIT WINDOW takes the ground's
    # 2-D long-wave trend at every vertex — a moving quadratic SURFACE fit
    # of the production DEM — instead of its three affine ``body_datum``
    # rows, which a plane-sized body keeps.  Fitted AFTER the taxi trend,
    # because a vertex the taxi chain already holds takes no second
    # authority.
    at_rep: ApronTrendReport = {}
    pm = with_apron_trend(pm, law_c, airport, at_rep)
    lrep.apron_trend = dict(at_rep)
    out(f"[{icao}] apron surface (10ar): {at_rep.get('bodies', 0)} bodies on the "
         f"ground's 2-D TREND ({at_rep.get('vertices', 0)} vertices, "
         f"{at_rep.get('samples', 0)} DEM cells, fit "
         f"{at_rep.get('fit_wall_s', 0.0):.2f} s), "
         f"{at_rep.get('bodies_plane', 0)} bodies keep their affine PLANE; "
         f"window {at_rep.get('window_m', 0.0):.0f} m, widest body "
         f"{at_rep.get('max_diameter_m', 0.0):.0f} m; target above DEM up to "
         f"{at_rep.get('max_above_dem_m', 0.0):.2f} m, below up to "
         f"{at_rep.get('max_below_dem_m', 0.0):.2f} m"
         + (f"; FALLBACK {at_rep['fallback']}" if at_rep.get("fallback") else ""))
    # THE EAT RAMP'S REACH — THE TREND YIELDS (owner RULINGS 2026-09-13aa;
    # spec §36 (5)).  An end-around taxiway pinned a tail height below the
    # departure surface must ramp back to the ground at the TAXI cap, and
    # the ramp's free neighbours were buying ~1 % of grade with their
    # ground-trend residual instead (measured 2.37-3.87 % at KCLT).  Over
    # the DERIVED reach — drop / cap along the loop's own centreline — both
    # trend channels are WITHDRAWN, not outweighed.  Runs AFTER both are
    # published, so neither claim is re-opened by the other's absence.
    er_rep: dict = {}
    pm = withdraw_trend_over_reach(pm, law_c, airport, er_rep)
    lrep.eat_reach = dict(er_rep)
    if er_rep.get("pins"):
        out(f"[{icao}] EAT ramp reach (13aa/§36-5): {er_rep.get('pins', 0)} pinned feet on "
             f"{len(er_rep.get('feet', []))} loop(s), reach "
             + ", ".join(f"{r['reach_m']:.0f} m (drop {r['drop_m']:.2f} at cap {r['cap']:.3f})"
                         for r in er_rep.get("feet", [])[:4])
             + f"; trend rows withdrawn {er_rep.get('withdrawn', 0)} "
             f"(taxi {er_rep.get('withdrawn_taxi', 0)}, apron {er_rep.get('withdrawn_apron', 0)})"
             + (f"; LOOP TOO SHORT at {len(er_rep['short'])} foot(feet) — forced grade "
                + ", ".join(f"{(s.get('forced_grade') or 0) * 100:.2f} %"
                            for s in er_rep["short"][:4]) + " (taxi family)"
                if er_rep.get("short") else ""))
    # §37 (6) A GROUNDSIDE ROAD IS A RAMP FROM ITS AIRSIDE CONTACT TO THE
    # DEM (owner RULINGS 2026-09-13j item 5, ruled 13aj; spec §37 (6)).
    # LAST of the target channels, because a mouth's level is READ from the
    # airside's own published target (§21 chord / §8.6 taxi trend / §8.7
    # apron trend) where it carries one; the ramp target then SUPERSEDES
    # the core's soft road fit for every vertex it governs — the ONE
    # superseding site.  The rows are ``constraints/road_ramp.py``'s.
    ramp_rep: dict = {}
    pm = with_road_ramp(pm, law_c, airport, ramp_rep, road_profiles,
                        service=load_rules().service)
    # §37 (9) THE COVERAGE-EDGE JOIN (owner RULINGS 2026-09-13be): the core
    # levels the road OUTSIDE the coverage and not inside it, so where a
    # way leaves, the patch takes the ribbon's own altitude there.
    join_rep: dict = {}
    pm = with_road_coverage_join(pm, law_c, road_profiles, join_rep)
    ramp_rep.update({f"join_{k}": v for k, v in join_rep.items()})
    lrep.road_ramp = dict(ramp_rep)
    rs = road_rep["profiles"]
    out(f"[{icao}] road profile {road_s:.2f} s  ways {rs['ways']} "
         f"(osm {rs['ways_by_kind'].get('osm', 0)}, route {rs['ways_by_kind'].get('route', 0)}, "
         f"axis {rs['ways_by_kind'].get('axis', 0)})"
         f"  stations {rs['stations']}  clamped {rs['clamped_stations']} "
         f"(max lift {rs['max_lift_m']:.2f} m, cut {rs['max_cut_m']:.2f} m)  cap {rs['cap']:.3f}"
         f"  vertices {road_rep['vertices']}  preferred {road_rep['preferred']}"
         f"  DEM fallback {road_rep['dem_fallback']}"
         f"  off-DEM {road_rep['preferred_off_dem']} (max {road_rep['max_preferred_shift_m']:.2f} m)")
    out(f"[{icao}] road ramps (§37 (6)): {ramp_rep.get('vertices', 0)} groundside-road "
         f"vertices from {ramp_rep.get('mouths', 0)} airside contacts at cap "
         f"{ramp_rep.get('cap') or 0.0:.3f} -> {ramp_rep.get('targets', 0)} targets "
         f"({ramp_rep.get('on_dem', 0)} on the DEM, {ramp_rep.get('on_ramp', 0)} on the ramp "
         f"up to {ramp_rep.get('max_above_dem_m', 0.0):.2f} m above it over "
         f"{ramp_rep.get('max_reach_m', 0.0):.0f} m of route, "
         f"{ramp_rep.get('no_contact', 0)} with no contact); core fit withdrawn on "
         f"{ramp_rep.get('preferred_withdrawn', 0)}; clamp over the DEM up to "
         f"{ramp_rep.get('max_clamp_over_dem_m', 0.0):.2f} m; coverage-edge joins "
         f"(§37 (9)) {ramp_rep.get('join_exits', 0)} exit(s) on "
         f"{ramp_rep.get('join_routes', 0)} route(s) -> {ramp_rep.get('join_vertices', 0)} "
         f"pinned vertices; road-edge drops (10-20d) {ramp_rep.get('road_drop_runs', 0)} "
         f"run(s) over {ramp_rep.get('road_drop_vertices', 0)} kerb vertices, "
         f"{ramp_rep.get('road_edge_walls', 0)} declared, "
         f"{ramp_rep.get('road_edge_no_lower', 0)} with no low side")
    out(f"[{icao}] road {descent_line(ramp_rep)}")
    return pm, _yield_records


_REPORTS = ("runway_chord", "taxi_trend", "apron_trend", "eat_reach", "road_ramp")


def run_prefix(airport, cl, law, inputs, pack: PackRead, cache=None, *,
               common: _t.Mapping[str, _t.Any] | None = None, cl_digest: str | None = None,
               icao: str | None = None, lrep=None,
               out: _t.Callable[[str], None] | None = None, heartbeat: str | None = None,
               targets: _t.Callable[[_t.Any], _t.Any] | None = None,
               rows: _t.Callable[[_t.Any], _t.Any] | None = None) -> PrefixRecord:
    """THE PREFIX on ``cl`` (module docstring).

    ``cache`` is the build's ``FrontCache`` (its planar, flat_site,
    road_profile and shapes records, keyed on ``common`` and the
    classification digest ``cl_digest``; the planar stage's registries record
    is installed before the shapes and the window closed after them; then
    the constraint and jetway-strip records), or ``None`` (every step runs
    plainly).  ``lrep`` (the load report)
    receives the flat-site record and the channel reports; ``out`` says the
    main pass's lines (``None``: silent); ``heartbeat`` names every step's
    pulse (a re-run's own work).  ``targets(pm) -> pm`` replaces the target
    channels and ``rows(cs) -> cs`` filters the constraint set (the replay
    tool's arms; ``None`` in a build)."""
    icao = icao or airport.icao
    say = out or (lambda m: None)
    lrep = lrep if lrep is not None else _types.SimpleNamespace()
    common = dict(common or {})

    def tick(what: str) -> None:
        _pulse.tick(heartbeat or what)
    wall: dict[str, float] = {}
    t = time.perf_counter()
    if cache is not None:
        pm, pstats, planar_record = cache.run(
            "planar", {**common, "airport": cache.airport_digest(airport),
                       "classification": cl_digest},
            lambda lw: _cstate.planar_stage(airport, cl, lw, cache=pack.resources,
                                            objects=pack.objects, object_report=pack.report))
    else:
        (pm, pstats), planar_record = build_planar(
            airport, cl, law, cache=pack.resources, objects=pack.objects,
            object_report=pack.report), None
    wall["planar"] = time.perf_counter() - t
    planar_pm = pm
    if out is not None:
        say_planar(icao, pm, pstats, airport, lrep, wall["planar"], out)
    # THE FLAT-SITE VERDICT (RULINGS 2026-09-05k-2; issue #932): DEM prep
    # DECIDED it once on the raw raster and the record rides on the DEM
    # (``airport/flat_site_read.py``) — read here, never re-measured; S4
    # (the pack's seats the planar stage read) is a report; a plateau the
    # record requires and the composed DEM lacks is an error.  The datum is
    # a preference the generator below prices, the runway keeps its pins
    t = time.perf_counter()
    tick("flat site")
    # §37 (11) (4) (owner RULINGS 2026-09-15f item 2): the airport's OWN
    # classified surfaces are LAND by declaration, so the datum region's
    # water cut cannot call a reclaimed apron sea (``_cut_water``'s own
    # docstring carries the VMMC measurement).
    fv, flat_how = _run(
        cache, law, "flat_site",
        lambda: {**common, "airport": cache.airport_digest(airport),
                 "planar": cache.output_digest("planar"), "classification": cl_digest},
        lambda lw: _flat_verdict(airport, lw, objects=pack.objects,
                                 land=classified_land(cl)))
    airport = _dc.replace(airport, flat_site=fv)
    wall["flat_site"] = time.perf_counter() - t
    lrep.flat_site = _flat.record(fv)
    say(_flat.log_line(icao, fv) + f" [{flat_how}]  ({wall['flat_site']:.2f} s)")
    # THE CORE SMOOTHS FIRST (RULINGS 2026-09-04t-4): every road-family
    # vertex's fit target is the core's clamped, laterally-levelled road
    # profile on this DEM (``airport/road_profile.py``); the cap rows
    # below stay and v2 moves a vertex off it only where one binds.
    t = time.perf_counter()
    tick("the preferred road profile")
    ap_digest = (cache.airport_digest(airport, flat_site=cache.output_digest("flat_site"))
                 if cache is not None else None)
    params = repr((inputs.road_grade_limit, inputs.lane_width_m))
    road_pref, road_rep, road_profiles = _run(
        cache, law, "road_profile",
        lambda: {**common, "airport": ap_digest, "planar": cache.output_digest("planar"),
                 "params": params},
        lambda lw: preferred_road_z(airport, pm, lw, inputs.road_grade_limit,
                                    inputs.lane_width_m))
    pm = _dc.replace(pm, preferred_z=road_pref)
    # the target channels below read the law the shape record is keyed on
    law_c = cache.stage_law() if cache is not None else law
    wall["road_profile"] = time.perf_counter() - t
    if targets is not None:
        pm, yield_records = targets(pm), []
    else:
        pm, yield_records = _channels(icao, pm, law, law_c, airport, road_profiles, road_rep,
                                      wall["road_profile"], lrep, say)
    # THE SHAPE STAGE (owner RULINGS 2026-09-08k; ``pipeline/shapes.py``):
    # the route bands, the withdraw set, the joint filter, the yield transform
    t = time.perf_counter()
    tick("the shapes")
    if planar_record is not None:
        _cstate.install(pm.registries, planar_record)   # #840: the planar stage's record

    def _shapes(lw):
        lines: list[str] = []
        return shape_stage(pm, lw, airport, cl, out=lines.append), lines
    # keyed on what the target channels above were handed (their code is
    # the ``channels`` digest of the shape record's key)
    stage, shape_lines = _run(
        cache, law, "shapes",
        lambda: {**common, "airport": ap_digest, "planar": cache.output_digest("planar"),
                 "road_profile": cache.output_digest("road_profile"),
                 "classification": cl_digest, "params": params}, _shapes)
    if cache is not None:
        cache.close()
    for ln in shape_lines:
        say(ln)
    pm = stage.pm
    wall["shapes"] = time.perf_counter() - t
    t = time.perf_counter()
    tick("generating the law constraints")
    seam_yielded: list = []
    # the generators' and the assembly's records (spec §4b.1), keyed on the
    # shape stage's output (the map and its registries) and the airport
    back_in = {"pm": cache.output_digest("shapes"), "airport": ap_digest} \
        if cache is not None else {}
    con = constraints_stage(cache, pm, law, airport, stage, back_in, seam_yielded)
    cs, counts, gwalls = con.cs, con.counts, con.walls
    wall["constraints"] = time.perf_counter() - t
    if out is not None:
        _say_constraints(icao, stage, cs, counts, gwalls, wall["constraints"], out)
    if rows is not None:
        cs = rows(cs)
    # THE JETWAY STRIP'S REGION (owner RULINGS 2026-09-18t Q3; jetway-strip
    # spec §1): derived HERE, where the airport, the map and the constraint
    # set meet, and handed to the solve as data — ``solve`` may not import
    # ``constraints`` (M0 §1).  The projection itself runs between §20b's
    # two stages (``solve/project_strip.py``).
    t = time.perf_counter()
    tick("the jetway strips")
    # a ``rows`` filter (the replay's arm) is not in the assembly's key
    sgot = strips_stage(cache, pm, law, airport,
                        con._replace(cs=cs, key=con.key if rows is None else None), back_in)
    strips = sgot.value
    wall["jetway_strip"] = time.perf_counter() - t
    say(f"[{icao}] jetway strip region (18t Q3) {wall['jetway_strip']:.2f} s: "
        + ", ".join(f"{k} {v}" for k, v in strips.counts.items()))
    # flat-pad spec v2 §1 / §2 (RULINGS 2026-09-30as): the hold's pass 1a /
    # interval / pass 1b, bound here because ``solve`` may not import
    # ``constraints``
    from ..constraints.no_step import hold_pass
    return PrefixRecord(
        airport=airport, planar_pm=planar_pm, pstats=pstats, planar_record=planar_record,
        flat_how=flat_how, road_rep=road_rep, road_profiles=road_profiles,
        reports={k: getattr(lrep, k, None) for k in _REPORTS},
        yield_records=yield_records, stage=stage, pm=pm, cs=cs, counts=counts,
        gwalls=gwalls, seam_yielded=seam_yielded, strips=strips,
        hold=hold_pass(pm, law, airport), wall=wall,
        keys={} if cache is None else {
            **back_in, "assembly": con.key if rows is None else None,
            "strips": sgot.digest, "chain": con.chain})


def _say_constraints(icao: str, stage, cs, counts: dict, gwalls: dict, wall_s: float,
                     out: _t.Callable[[str], None]) -> None:
    """The constraint stage's lines: the joint drops, the counts by kind and
    the rows (and seconds) per generator."""
    if stage.dropped:
        out(f"[{icao}] joints (08k): {sum(stage.dropped.values())} rows dropped across shape "
            f"boundaries — " + ", ".join(f"{g} {n}" for g, n in sorted(stage.dropped.items()))
            + f"; reach bands withdrawn {stage.bands_withdrawn}; flats straddling "
            f"{stage.flats_straddling}")
    out(f"[{icao}] constraints {wall_s:.2f} s  {cs.counts()}")
    for name, n in counts.items():
        # a ``<generator>.<stat>`` key is a statistic, not a timed generator
        out(f"    {name:28s} {n:8d}  {gwalls[name]:.3f} s" if name in gwalls
            else f"    {name:28s} {n:8d}")


class Deriver:
    """A ``derive(cl) -> (pm, cs, strips, hold)`` over :func:`run_prefix`
    (silent) for ``stage_one_problem`` and the late stage; ``last`` is the
    last run's :class:`PrefixRecord`.  With the build's ``cache`` (and its
    ``common`` inputs) every run goes through the records, keyed by its
    own classification, and is reported as ``<stage>@prefix<n>`` (spec
    §4b.3); with none it runs plainly."""

    def __init__(self, airport, law, inputs, pack: PackRead, cache=None,
                 common: _t.Mapping[str, _t.Any] | None = None, **kw: _t.Any) -> None:
        self.airport, self.law, self.inputs, self.pack, self.kw = airport, law, inputs, pack, kw
        self.cache, self.common = cache, common
        self.runs = 0
        self.last: PrefixRecord | None = None

    def __call__(self, cl) -> tuple:
        self.runs += 1
        cl_digest = None
        if self.cache is not None:
            self.cache.reopen(f"prefix{self.runs}")
            cl_digest = self.cache.digest(cl)
        try:
            self.last = run_prefix(self.airport, cl, self.law, self.inputs, self.pack,
                                   self.cache, common=self.common, cl_digest=cl_digest,
                                   **self.kw)
        finally:
            if self.cache is not None:
                self.cache.tag = ""
        return self.last.derived()
