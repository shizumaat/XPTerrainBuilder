"""The orchestration (plan §1 row ``pipeline``): load → classify →
planar → constraints → solve → emit → verify, each stage timed, progress
lines on stdout.  The ONLY package that reads the environment (it does
not yet: inputs come from ``planar.__main__.default_inputs`` and the
CLI).  The objective's weights are LAW (``emit.toml [design]``, RULINGS
2026-09-08t), not a config object here.
"""
from __future__ import annotations

import dataclasses as _dc
import json
import time
import typing as _t
from pathlib import Path

from ..airport.load import Inputs, load_with_report
from ..classify import classify, load_rules
from ..constraints.routes import RIDGE_KIND  # noqa: F401
from ..constraints.runway_profile import RUNWAY_FAMILY  # noqa: F401
from ..constraints.taxi_trend import TaxiTrendReport
from ..emit.osm_adapter import PatchPaths
from ..law import Law
from ..model import pulse as _pulse
from ..model.constraints import ConstraintSet
from ..model.planar import PlanarMap
from ..planar import arrangement_memo as _arr_memo
from ..planar.pack_reads import pool_report as _pack_read_pool
from ..solve import DesignReport, Options, Solution, solve_design  # noqa: F401
from . import emit_records as _emit_records
from . import front_cache as _front
from . import xplat as _xplat

# the stages (stage-cache spec §10 step 8): the prefix, the emit, the verify;
# the names marked "read here" are re-exported for the tools and twins
from .emit_stage import (  # noqa: F401
    MOVED_M,
    borrowed_apt_dat_stamp,
    displacement_by_role,
    post_solve,
    with_join_yield,
)
from .planar_report import shore_decision_lines  # noqa: F401  (read here)
from .prefix import Deriver, PackRead, run_prefix
from .prefix import classified_land as _classified_land  # noqa: F401  (read here)
from .rebake_inputs import _plate_seats, _rebake_inputs, plate_stations  # noqa: F401
from .late_records import prefix_identity
from .shapes import joint_steps
from .solve_record import identity, solve_stage

__all__ = ["Config", "BuildResult", "build", "borrowed_apt_dat_stamp"]


@_dc.dataclass(frozen=True)
class Config:
    """Build configuration (a schema, never an env gate)."""

    options: Options = Options()
    verify: bool = True
    feather_m: float = 60.0
    #: Extra ``<osm>`` root attributes for the emitted patch (and every
    #: tile piece): a HOSTING tile build's rebuild-freshness stamps
    #: (the v1 tile driver reads them back through ``read_patch_source``
    #: before reusing a patch).  Applied over the adapter's own header, so
    #: a host may override ``o4_apt_dat`` with its percent-encoded form.
    header_extra: _t.Mapping[str, str] | None = None
    #: THE CROSS-PLATFORM STAGE DUMP (lane ``xplatdeterminism``): write
    #: ``<ICAO>.xplat.json`` beside the report — per-stage counts and
    #: order-free geometry digests at 9/6/4/2/1 dp, plus what the running
    #: wheels actually bundle (GEOS, PROJ, BLAS).  A SCHEMA FLAG, not an
    #: env gate: the release check asks for it through
    #: ``auto_patch/engine_v2.py``, which is where its
    #: ``O4_V2_XPLAT_DIGEST`` is read.  Off by default — the digests walk
    #: every vertex of every stage.
    xplat_dump: bool = False
    #: THE MEASUREMENT ARM'S OVERRIDE of ``emit.identity.input_quantum_m``
    #: (§46 (4)).  Since §46 the quantum SHIPS, at ``Frame.entry`` — this
    #: is not a second quantiser but a way to run an arm on another grid,
    #: notably ``0.0`` = the pre-§46 UNQUANTISED arm, which is how §46 (6)'s
    #: residues are attributed against the shipped law.  Read ONLY when
    #: ``xplat_dump`` is set; ``None`` (the default, and every shipped
    #: build) means "the law's value".
    xplat_quantise_m: float | None = None
    #: THE V2 STAGE CACHE (issue #843; ``pipeline/front_cache.py``): serve
    #: the front-half stages from their content-keyed records under the
    #: build's mod-cache root.  A SCHEMA FLAG: ``auto_patch/engine_v2.py``
    #: reads ``O4_V2_STAGE_CACHE`` (``0`` = off) and sets it; off by default
    #: here, so a direct caller (a tool, a twin) writes no record.
    stage_cache: bool = False


@_dc.dataclass
class BuildResult:
    """Everything a build produced, for the report."""

    icao: str
    planar: PlanarMap
    constraints: ConstraintSet
    counts: dict[str, int]
    solution: Solution
    paths: PatchPaths | None
    verify_rows: dict[str, list[dict]] | None
    pieces: dict[tuple[int, int], PatchPaths] | None
    wall: dict[str, float]
    lp_size: dict[str, int]
    report: dict[str, _t.Any]
    #: ``<out>/<ICAO>.rebake.json`` — the post-mesh re-seat plan (04f-1),
    #: written HERE only by a build that kept no partition cache
    rebake_plan: Path | None = None
    #: ``<out>/<ICAO>.rebake.screen.json`` — what the object step builds
    #: that plan from (owner RULINGS 2026-10-04x (1); ``airport/rebake_screen``)
    rebake_screen: Path | None = None


#: the taxi-family row counters (§8.6 trend, §61 cross-section and
#: membrane, #517 through-junction profile): their rows live in the stage that owns their vertices — the
#: base's stage 1 — so behind a last stage (§55 (4)) the sidecar's top
#: block is the sum over stages, never the last stage's own 0
_BASE_STAGE_ROWS = ("taxi_trend_rows", "taxi_xsec_rows", "taxi_junction_rows",
                    "free_membrane_rows")


def _fold_base_rows(rep, base) -> None:
    """Add the base solve's :data:`_BASE_STAGE_ROWS` into the last
    stage's report ``rep`` (in place)."""
    for k in _BASE_STAGE_ROWS:
        setattr(rep, k, getattr(rep, k) + getattr(base, k))


def _say(msg: str, out: _t.Callable[[str], None]) -> None:
    out(msg)


def pack_stage(icao: str, airport, law: Law, inputs: Inputs, lrep,
               out: _t.Callable[[str], None] = print, *,
               write_cache: bool = True) -> dict:
    """THE PACK STAGE — read the pack, partition it (or revive the cached
    partition), derive the groups and the clusters — exactly as ``build``
    runs it; ``build`` and ``tools/pack_stage_profile.py`` call THIS (one
    code path, never a second spelling of the drive site).  Returns
    ``{"airport", "ocache", "objects", "report", "partition", "groups",
    "clusters", "cache", "wall"}`` — ``airport`` carries the partition,
    the groups and the clusters; ``cache`` is ``HIT`` / ``MISS`` / ``OFF``;
    ``wall`` the stage seconds by part (``read``, ``partition``,
    ``groups``, ``clusters``, ``total``).  ``write_cache=False`` reads a
    cached partition but never writes one (the dry ``planar --stage
    structures`` replay, issue #75: a replay writes nothing shared).
    ``pool`` is the stage's work pool's own account (``airport/pool.py``
    ``WorkPool.report``: workers, parallel, fell_back, reason, wall_s,
    tasks) — said on the ``[pool]`` line too, so a stage that ran on one
    core cannot read as a pooled one."""
    wall: dict[str, float] = {}
    _sub: dict[str, float] = {}
    t = time.perf_counter()
    # ONE ``ResourceCache`` for the whole build (spec §22): the skirt
    # reader runs inside classify, the structure passes and the re-seat
    # plan read the same parsed geometry, so the pack is parsed once
    #
    # IT CARRIES THE §51 (6) INPUT QUANTUM (owner RULINGS 2026-10-02v (4),
    # issue #222: "the snapped read is the law").  Read through the package's
    # ONE accessor (``frame_entry.quantum``) — the same call
    # ``planar/build.build_planar`` makes for the cache it builds when this
    # stage does not hand it one, so the pack reaches the planar map snapped
    # on the input grid whichever of the two minted the cache.  Without it
    # ``frame_entry.enter`` ran the affine and the repair and skipped the
    # snap (§51 (2) (b)), which is the SYNTHETIC-TWIN frame the class
    # documents, and the production build read unsnapped pack geometry:
    # measured on KCLT, an unsnapped ``tunnel_ramp`` face and its
    # ``structure_rim`` / ``tunnel_wall`` ring at 35.2217, -80.9417 (14
    # planar vertices) that the snapped read does not have, and 2,381
    # row-side values apart, worst 1.12 m.
    from ..airport import frame_entry as _fe
    from ..airport.obj8 import ResourceCache as _RCache
    ocache = _RCache(law.tables.structures.basin.min_solid_thickness_m,
                     _fe.quantum(law))
    # THE PACK PARTITION IS A LOAD-STAGE INPUT (owner RULINGS 2026-09-11j;
    # spec §11a (3)).  The pad law needs the pack's BODIES, FEET and
    # ABUTMENTS, and the pads are minted inside ``classify`` — so the pack
    # is read and partitioned HERE, once, and ``rebake_plan.plan()``
    # FILTERS this reading after the solve instead of re-partitioning a
    # filtered object set.  ``planar`` is handed the same objects, so the
    # pack is still read once.
    # THE PACK PARTITION IS CACHED (lane ``v2cost2``, RULINGS 2026-09-14q
    # item 1): the pack reading and the partition are a pure function of
    # the pack files, the dump, the law, the frame and the code, so they
    # are stored beside ``o4_object_footprints_<tile>.cache`` in the
    # pack's mod-cache folder under the same fingerprint discipline
    # (``airport/partition_cache.py`` carries the whole argument, and why
    # the write is that cache's class and not a ``--refresh-data`` act).
    # ``_derive_groups`` reads the DEM and is NEVER cached.
    from ..airport import partition_cache as _pcache
    from ..airport.pack_partition import partition_pack as _partition_pack

    # THE STAGE'S WORK POOL (issue #362): opened here so its lines reach
    # the build log through ``out`` and its account reaches the report;
    # lazily started, so a cache HIT spawns nothing
    from ..airport.pack_work import open_pool as _open_pool
    from ..law.tables import group_span_max_m as _span_max
    from ..planar.basins import read_objects as _read_objects
    from ..planar.group import derive as _derive_groups
    _wpool = _open_pool(law, ocache, out=lambda m: _say("  " + m, out))
    _fp = _pcache.fingerprint(airport, law, dump_path=lrep.dsf_dump_path,
                              radius_deg=inputs.radius_deg,
                              pristine=getattr(inputs, "pack_pristine", None))
    _cpath = _pcache.cache_path(airport, inputs.mod_cache_root, lrep.dsf_dump_path)
    _hit = _pcache.read(_cpath, _fp)
    # spec §B.4: the ``[partition] cache HIT|MISS|WROTE`` line is REQUIRED
    # on every build — its absence is how a cache that never hit went
    # unnoticed (TNCM + TFFG overwrote one tile-named file, issue #27)
    _cstate = "OFF" if not (_cpath and _fp) else ("HIT" if _hit is not None else "MISS")
    if _cstate == "OFF":
        _say(f"  [partition] cache OFF (no pack, dump or mod-cache root)", out)
    if _hit is not None:
        pack_objects, pack_report, _part, _cached_clusters, _derived = _hit
        # the reading goes back on the ONE ``ResourceCache`` (RULINGS
        # 2026-09-14v item 2 — ``partition_cache.put_back`` carries it)
        _nd = _pcache.put_back(ocache, _hit)
        _rd = _pcache.resolved_digest(airport)
        _say(f"  [partition] cache HIT {_cpath} ({_nd} resource reading(s) "
             f"restored; resolved {_rd[0]} sha {_rd[1][:12]})", out)
    else:
        if _cstate == "MISS":
            # issue #88: a miss whose stored resolved set differs from
            # this run's names BOTH digests (the stale-key case)
            _rd = _pcache.resolved_digest(airport)
            _was = _pcache.peek(_cpath)
            _why = ""
            if _was is not None and _was != _rd:
                _why = (f" (resolved set moved: cached {_was[0]} sha "
                        f"{_was[1][:12]} -> now {_rd[0]} sha {_rd[1][:12]})")
            _say(f"  [partition] cache MISS {_cpath} (resolved {_rd[0]} sha "
                 f"{_rd[1][:12]}){_why}", out)
        _cached_clusters = None
        try:                # the workers never outlive a stage that raised
            _t = time.perf_counter()
            _pulse.tick("reading the pack's objects")
            # issue #382: the reading asks the DEM through a witness, so
            # the cache file can say which ground it was read on
            pack_objects, pack_report = _read_objects(
                _dc.replace(airport, dem=_pcache.ground_witness(_fp, airport.dem)),
                law, ocache, pool=_wpool)
            _sub["read"] = time.perf_counter() - _t
            _t = time.perf_counter()
            _pulse.tick("partitioning the pack")
            _part = _partition_pack(airport, pack_objects, ocache, law, pool=_wpool)
            _sub["partition"] = time.perf_counter() - _t
        except BaseException:
            _wpool.close()
            raise
    # THE FEASIBILITY BAR IS THE GROUND'S, NOT THE PAD'S (owner RULINGS
    # 2026-09-11j; spec §11 (4) "the emitted surface stays lawful").  The
    # terrain under an object's feet is GROUND, and the slope a pilot
    # reads as ground rather than a wall is ``emit.design.bank_slope``
    # (1:3).  Priced at the pad's own 1 % tilt instead, every body with
    # any authored relief came out infeasible (LEMD 7,627 of 13,064
    # groups), which is a verdict that says nothing.
    # THE FEASIBILITY VERDICT PRICES THE DEM'S FALL (owner RULINGS
    # 2026-09-11q; spec §11b (3)).  Round 5's reading judged the AUTHORED
    # relief alone, which says a colonnade rising 2.63 m over 52.8 m is
    # feasible on flat ground and infeasible on the hillside it was
    # authored for — exactly backwards.  The body's level is FITTED to the
    # ground under its feet and the residual judged against the bank the
    # terrain may lawfully make (``bank_slope``, 1:3).
    # §46 (9) census row 8: the ``(lat, lon)`` handed to ``_dem_at`` are
    # the groups' own INPUT feet — the ENTRY projection, so the §11b (3)
    # verdict samples the DEM at the same point ``foot_rows`` does
    _to_xy = airport.frame.entry()

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

    # the pool stays open through the clusters (their profile compositions
    # are pooled, issue #362) and never outlives a stage that raised
    try:
        _bank = float(law.tables.emit.design.bank_slope)
        _t = time.perf_counter()
        _pulse.tick("deriving the pack's groups")
        _groups = _derive_groups(_part, _span_max(law), _bank,
                                 dem_at=_dem_at, bank_slope=_bank)
        _sub["groups"] = time.perf_counter() - _t
        # §16g / §30 (4) THE TERMINAL CLUSTERS (owner RULINGS 2026-09-13bj
        # item 1, 13bo): the FOOTPRINT UNITS whose union passes
        # ``[placement] cluster_pad_min_m2``, derived from the same partition
        # so the design surface's pad and the object stage's unit are one
        # relation.  Carried on the airport because ``constraints`` may not
        # import ``planar``.
        from ..planar.cluster import clusters as _derive_clusters

        # unit-platform spec §2 (owner RULINGS 2026-09-28a (2)): THE ONE
        # CONNECTOR VERDICT, derived on the DEM and STAMPED on the partition —
        # ``plan_clusters`` reads it here and the rebake plan carries it to the
        # object stage.  It reads the DEM, which the partition cache does not
        # fingerprint, so it is derived fresh on every build and a cached
        # cluster set derived under a different verdict is re-derived.
        from ..planar.cluster import connector_verdicts as _cverdicts
        _t = time.perf_counter()
        _pulse.tick("reading the connectors")
        _stamped = getattr(_part, "connectors", None)
        _verdicts = _cverdicts(_dc.replace(airport, partition=_dc.replace(
            _part, connectors=None)), law, pool=_wpool)
        _sub["connectors"] = time.perf_counter() - _t
        for _ln in _pcache.companion_notes():       # [topology] cache HIT|MISS
            _say("  " + _ln, out)
        if _cached_clusters is not None and _stamped != _verdicts:
            _cached_clusters = None
        _part = _dc.replace(_part, connectors=_verdicts)
        _say(f"  [connectors] {len(_verdicts)} connector(s): "
             f"{sum(1 for v in _verdicts if v.solid)} SOLID, "
             f"{sum(1 for v in _verdicts if not v.solid)} CUT", out)
        if _cached_clusters is not None:
            _clusters = _cached_clusters
        else:
            _t = time.perf_counter()
            _pulse.tick("deriving the terminal clusters")
            _clusters = _derive_clusters(_dc.replace(airport, partition=_part), law,
                                         pool=_wpool)
            _sub["clusters"] = time.perf_counter() - _t
            if write_cache and _pcache.write(_cpath, _fp,
                             (pack_objects, pack_report, _part, _clusters,
                              ocache.derived_state())):
                _rd = _pcache.resolved_digest(airport)
                _say(f"  [partition] cache WROTE {_cpath} (resolved {_rd[0]} "
                     f"sha {_rd[1][:12]})", out)
            for _ln in _pcache.companion_notes():   # [topology] cache WROTE
                _say("  " + _ln, out)
    finally:
        _wpool.close()
    airport = _dc.replace(airport, partition=_part, groups=_groups,
                          clusters=_clusters)
    # issue #516: the sunken ramps' ground, beside the clusters it trims
    from ..airport.sunken_ramp import attach_sunken_ramps
    airport = attach_sunken_ramps(airport, law, ocache)
    # §16g (8)/(9) (owner RULINGS 2026-09-14w): the cluster count, SAID.
    # HECA's round-5 build priced 0 cluster cross-links while
    # ``plan_clusters`` on the same plan returned 2, and nothing in the
    # build named the difference — an empty derivation must say why.
    from ..planar.cluster import WHY as _cwhy
    # §16g (9)/(10) (owner RULINGS 2026-09-14x): the population is now
    # EVERY footprint chain split at its ground floor, not the two
    # families §16f's gates left, so the count is the airport's buildings
    # and the say-line names what the PAD derivation will get: how many
    # carry an outline (a pre-14o plan carries none and the pads then
    # fall back to the footprint cache) and how many clear the cluster
    # PAD PLANE threshold.
    _say(f"  [clusters] {len(_clusters)} cluster(s)"
         + (f"  -- {_cwhy['gate']}" if not _clusters and _cwhy.get("gate")
            else "")
         + (f"  (partition units {_cwhy.get('units')}, touch "
            f"{_cwhy.get('touch_m')} m, floor split "
            f"{_cwhy.get('floor_split_m')} m, "
            f"{_cwhy.get('with_rings')} with an outline, "
            f"{sum(1 for _c in _clusters if _c.area_m2 >= _cwhy.get('min_m2', 0.0))} "
            f"over the cluster-pad threshold {_cwhy.get('min_m2')} m2)"), out)
    # issue #14 (``welded-deck-spec.md`` §1 (4)): the welded decks the load
    # read and the shade that leaves every cluster outline, SAID
    from ..planar.cluster import deck_shades as _deck_shades
    _ds = _deck_shades(airport)
    if _ds["members"]:
        _say(f"  [deck shades] {_ds['shades']} of {len(_ds['members'])} hard deck(s) "
             f"read DECK, shade {_ds['area_m2']:,.0f} m2  ("
             + ", ".join(f"{q['resource']} {q['ratio']}" for q in _ds["members"])
             + ")", out)
    _say("  " + _wpool.line(), out)
    wall["partition"] = time.perf_counter() - t
    _say(f"[{icao}] pack partition {wall['partition']:.2f} s  "
         f"members {_part.counts['members']}  parts {_part.counts['parts']}  "
         f"contacts {_part.counts['contacts']}  abutments {_part.counts['abutments']}  "
         f"bodies {_groups.counts['bodies']}  groups {_groups.counts['groups']} "
         f"(cross-placement {_groups.counts['cross_groups']}, long span "
         f"{_groups.counts['long_span']}, relief {_groups.counts['relief_bodies']}, "
         f"infeasible {_groups.counts['infeasible']} of which short "
         f"{_groups.counts['infeasible_short']}, released "
         f"{_groups.counts['released']})", out)
    return {"airport": airport, "ocache": ocache, "objects": pack_objects,
            "report": pack_report, "partition": _part, "groups": _groups,
            "clusters": _clusters, "cache": _cstate,
            "wall": {**_sub, "total": wall["partition"]},
            "pool": _wpool.report()}


@_arr_memo.scoped   # the arrangement's front, read once per build (#803)
def build(icao: str, inputs: Inputs, out_dir: str | Path,
          config: Config | None = None, law: Law | None = None,
          out: _t.Callable[[str], None] = print) -> BuildResult:
    """Run every stage and write the patch + report into ``out_dir``."""
    cfg = config or Config()
    wall: dict[str, float] = {}
    t = time.perf_counter()
    # THE RUN'S OWN CLOCK (lane ``v2cost2``, RULINGS 2026-09-14q item 7):
    # ``total`` was the SUM OF THE STAGES, so every second spent outside a
    # named stage was invisible — OTHH's 105 s.  ``total`` is now the wall
    # of the whole call and ``unclocked`` names what no stage claimed.
    t_build = t
    law = law or Law.for_airport(icao)
    # THE RAW PROJECTION DUMP (lane ``xplatspread``): armed BEFORE the load
    # stage, because the load stage's ``_vector_to_xy`` is the hook.  Off,
    # nothing is armed and the hook returns the frame's own function
    # unchanged — the shipped path never sees a wrapper.
    if cfg.xplat_dump:
        _xplat.arm_projection(cfg.xplat_quantise_m)
    else:
        _xplat.disarm_projection()
    airport, lrep = load_with_report(icao, inputs, law)
    wall["load"] = time.perf_counter() - t
    # THE CROSS-PLATFORM STAGE DUMP (lane ``xplatdeterminism``): armed by
    # ``O4_V2_XPLAT_DIGEST`` alone, off by default.  These are REFERENCES
    # to the stage products, which are frozen dataclasses replaced rather
    # than mutated, so holding one is a true snapshot and costs nothing
    # until the digests are taken at the report site.
    _xp: dict = {}
    if cfg.xplat_dump:
        _xp["armed"] = True
    _say(f"[{icao}] load {wall['load']:.2f} s  runways {len(airport.runways)}  "
         f"pavements {len(airport.pavements)}  buildings {len(airport.buildings)}", out)
    # §37 (11) (7) THE SHORE FEED (issue #72): how many built-shore
    # declarations the zones will see, and from how many feed files — a
    # zero with no file is "never filled", not "no quay here".
    _shore = sum(1 for w in airport.osm_ways
                 if getattr(w, "kind", "") == "shore_structures")
    _say(f"  [load] shore feed (§37 (11) (7)): {len(lrep.osm_shore_feeds)} "
         f"file(s), {_shore} shore-structure way(s)"
         + ("" if lrep.osm_shore_feeds else
            " — NOT FILLED: every coast reads natural "
            "(build_airport.py --refresh-data shore)"), out)
    # §44 (4) THE PAVEMENT BORROW (owner RULINGS 2026-09-15f): ONE line,
    # only when the pack's own pavement did not stand.
    for _line in lrep.cifp_coordinate_joins:     # #119: named, every one
        _say(f"  [load] {_line}", out)
    if lrep.pavement_borrow_line:
        _say(f"[load] {lrep.pavement_borrow_line}", out)
    # §42 (3) THE CENSUS (RULINGS 2026-09-13cv): the pack's draped OBJ8
    # ground polygons admitted as source polygons, per resource.
    if lrep.object_pavements.line():
        _say(f"  [load] {lrep.object_pavements.line()}", out)
        for ln in lrep.object_pavements.resource_lines():
            _say(ln, out)
    if lrep.dsf_gap_sheets:
        # the ``.pol`` sheets are the LAST ``dsf_gap_sheets`` of the tuple
        _defs = len({g.description
                     for g in airport.gap_sheets[-lrep.dsf_gap_sheets:]})
        _say(f"  [load] {lrep.dsf_gap_sheets} draped .pol page(s) admitted by "
             f"SURFACE as gap sheets ({lrep.dsf_gap_sheet_m2:,.0f} m², "
             f"{_defs} defs) — never a pavement source (§60)", out)
    _ps = pack_stage(icao, airport, law, inputs, lrep, out)
    airport, ocache = _ps["airport"], _ps["ocache"]
    pack_objects, pack_report = _ps["objects"], _ps["report"]
    _part, _groups = _ps["partition"], _ps["groups"]
    wall["partition"] = _ps["wall"]["total"]
    # THE STAGE CACHE (issue #843; ``pipeline/front_cache.py``): classify,
    # planar, flat_site, road_profile and the shapes are served from their
    # records when key and witnesses hold.  Off (``Config.stage_cache``
    # False, the xplat dump armed), every call below runs as it always did.
    fc = _front.FrontCache(icao, airport, law, enabled=cfg.stage_cache,
                           mod_cache_root=inputs.mod_cache_root,
                           pack=(pack_objects, pack_report),
                           # the release gate measures the programme (§7):
                           # every record reports ``bypass: xplat``
                           bypass="xplat" if cfg.xplat_dump else None)
    airport = fc.airport(airport)
    fc.window(True)
    t = time.perf_counter()
    _pulse.tick("classifying the airport")
    _rules = load_rules()
    _fc_in = fc.common_inputs(_rules, ocache)
    cl, _cl_side = fc.run(
        "classify", {**_fc_in, "airport": fc.airport_digest(airport)},
        lambda lw: (classify(airport, lw, _rules, cache=ocache),
                    _front.classify_side_state()), as_served=True)
    # what ``classify`` leaves in ``classify.evidence`` for the sidecar's
    # ``pad_refusals``, put back on a hit (and, unchanged, on a miss)
    _front.install_classify_side_state(_cl_side)
    wall["classify"] = time.perf_counter() - t
    # spec §55 (4), (9) THE GAP PIECES JOIN IN THE LAST STAGE: with a §53
    # gap piece minted, every stage below runs on the classification
    # WITHOUT the pieces (the BASE — the build an airport with no gap sheet
    # gets, row for row) and ``pipeline/late_stage`` solves the pieces
    # against its levels after the solve.  No piece: ``None``, and nothing
    # of the last stage runs.  The PAD ROADS (issue #609; owner RULINGS
    # 2026-10-13a (1), 13d) join there too: a road admitted for a pad is
    # solved against the levels of the map without it, so no pad, lot or
    # airside level moves for it.
    from .stage_one_map import gap_free
    cl_gaps, _cl_base = None, gap_free(cl)
    _cl_digest = fc.output_digest("classify")
    if _cl_base is not None:
        cl_gaps, cl = cl, _cl_base
        _cl_digest = fc.digest(cl)
    # issue #669 / #711: the object ramps' feet — for the planar stage's
    # landing run-outs (``planar/landing_runout``) and the last stage's
    # run-outs — read HERE, on the run's ResourceCache (one parse per
    # resource: the planar stage reads the same cache)
    from ..airport.ramp_feet import REPORT as _feet_rep
    from ..airport.ramp_feet import attach_ramp_feet
    airport = attach_ramp_feet(airport, law, ocache)
    wall["ramp_feet"] = _feet_rep.get("s", 0.0)
    _say(f"[{icao}] ramp feet (14c (5)): {_feet_rep}", out)
    # stage-cache spec §10 step 1 (#840): the registries the planar stage
    # fills come back as its RECORD, installed explicitly before the shapes
    # (``pipeline/prefix.run_prefix``).
    # ``objects_out`` is ``[the pack's objects, the cache]`` — the very
    # objects the pack stage read (the planar stage reads, never mutates,
    # them) and the build's own ``ResourceCache``, so it is not recorded
    objects_out: list = [pack_objects, ocache]
    pack = PackRead(pack_objects, pack_report, ocache)
    if _xp:
        _xp["classification"] = cl
        _xp["partition_airport"] = airport
    # THE PREFIX (stage-cache spec §4b.3; ``pipeline/prefix.py``): planar →
    # flat site → road profile → target channels → shapes → constraints →
    # jetway strips → the hold, through the front cache, saying its lines
    pre = run_prefix(airport, cl, law, inputs, pack, fc, common=_fc_in, cl_digest=_cl_digest,
                     icao=icao, lrep=lrep, out=out)
    wall.update(pre.wall)
    if _xp:
        _xp["planar_pm"] = pre.planar_pm
    airport, pm, pstats, stage = pre.airport, pre.pm, pre.pstats, pre.stage
    fv, road_rep, tt_rep = airport.flat_site, pre.road_rep, pre.reports["taxi_trend"]
    cs, counts, gwalls, strips = pre.cs, pre.counts, pre.gwalls, pre.strips
    _yield_records, seam_yielded = pre.yield_records, pre.seam_yielded
    t = time.perf_counter()
    _pulse.tick("solving the surface")
    # OWNER RULINGS 2026-09-27a (11): a reach contact within one lane width
    # seeds the ramp from STAGE 1's solved level — applied between the two
    # stages, bound here because ``solve`` may not import ``constraints``
    from ..constraints.road_ramp import reach_seed_rewrite

    # #100 round 8, option (c): STAGE 1 IS ASSEMBLED ON THE RIBBON-FREE MAP —
    # this build's own prefix, re-run on the classification without ribbons
    # (``pipeline/stage_one_map``); ``None`` when no ribbon was minted
    from .stage_one_map import stage_one_problem
    # the heartbeat names THIS work, not the inner planar build's last step
    # the re-runs go through the same records, keyed by their own
    # classification (stage-cache spec §4b.3)
    derive = Deriver(airport, law, inputs, pack, cache=fc, common=_fc_in,
                     heartbeat="stage 1 on the ribbon-free map: shapes and constraints")
    _s1 = stage_one_problem(cl, derive, pm.registries)
    _pulse.tick("solving the surface")
    if _s1 is not None:
        _s1.bind(pm)
        _say(f"[{icao}] stage 1 on the ribbon-free map (#100 (c)): {_s1.report}", out)
    # OWNER RULINGS 2026-10-15i (3), option (b): the taxi trend's SECOND
    # PASS — the apron levels stage 1 solved become trend contacts, bound
    # here because ``solve`` may not import ``constraints``
    from ..constraints.taxi_trend import stage_one_retarget

    def _solve() -> tuple:
        size: dict[str, int] = {}
        tt2: TaxiTrendReport = {}
        sol, rep = solve_design(
            pm, cs, law, cfg.options, size_out=size, strips=strips,
            stage2_rewrite=lambda lv: reach_seed_rewrite(pm, law, cs, lv),
            hold=pre.hold, stage1=_s1,
            trend_rewrite=lambda pm_x, lv: stage_one_retarget(pm_x, law, airport,
                                                              lv, tt2))
        return sol, rep, size, tt2, None if _s1 is None else dict(_s1.report)
    # THE SOLVE'S RECORD (stage-cache spec §4b.4; ``pipeline/solve_record``):
    # keyed on the prefix's records and the ribbon-free prefix's, never
    # served without its certificate
    _solved = solve_stage(
        fc, {**pre.keys, "stage_one": "none" if _s1 is None else prefix_identity(
            derive.last.keys), "options": fc.digest(cfg.options)},
        _solve, cs=cs, n=len(pm.vertices), law=law, options=cfg.options,
        held=pm.registries.held)
    sol, design_rep = _solved.value.sol, _solved.value.design
    size, tt2_rep = dict(_solved.value.size), _solved.value.second_pass
    wall["solve"] = time.perf_counter() - t
    if tt2_rep:
        lrep.taxi_trend["second_pass"] = {
            k: tt2_rep.get(k) for k in ("retarget_moved", "retarget_worst_m",
                                        "extra_contacts", "short_connectors",
                                        "hold_passes", "hold_residual_m",
                                        "hold_stalled")}
        _say(f"[{icao}] taxi trend second pass (15i (3)): "
             f"{tt2_rep.get('extra_contacts', 0)} apron levels as contacts, "
             f"{tt2_rep.get('retarget_moved', 0)} targets moved (worst "
             f"{tt2_rep.get('retarget_worst_m', 0.0):.2f} m)"
             + ("" if tt2_rep.get("retarget_moved") else " — first pass stands")
             + f"; {len(tt2_rep.get('short_connectors') or ())} short connector(s)", out)
        for r in (tt2_rep.get("short_connectors") or ())[:20]:
            _say(f"[{icao}] SHORT CONNECTOR at {r['ll'][0]:.7f},{r['ll'][1]:.7f}: "
                 f"run {r['run_m']:.1f} m, height {r['height_m']:.2f} m needs "
                 f"{r['grade_needed_pct']:.2f} % against {r['grade_allowed_pct']:.2f} % "
                 f"(high contact {r['high_ll'][0]:.7f},{r['high_ll'][1]:.7f}, "
                 f"low {r['low_ll'][0]:.7f},{r['low_ll'][1]:.7f})", out)
    _pin_yield = list(design_rep.pin_yield or ())
    hard_conflict = design_rep.hard_conflict     # spec §3b: a record field
    _late_report: dict | None = None
    if cl_gaps is not None:
        # spec §55 (4) THE LAST STAGE: the pieces cut by the base's levels,
        # the full map through THIS build's own prefix, the followers solved
        # against constants.  Everything below reads the full map.
        t = time.perf_counter()
        _pulse.tick("the last stage: the gap pieces")
        from .late_stage import run_last_stages
        _base_rep = design_rep
        # the last stage re-mints the held registry (its own prefix run): the
        # base solve's hold report is carried over it (``model.platform``)
        from ..model.platform import install_hold_report
        from .late_records import LateRecords
        _late_records = LateRecords(
            fc, {"airport": pre.keys.get("airport"), "rules": _fc_in.get("rules"),
                 "options": fc.digest(cfg.options)},
            identity(pre.keys.get("pm"), _solved.digest), law, cfg.options)
        pm, sol, _late = run_last_stages(
            cl_gaps, airport, law, derive,
            {"pm": pm, "z": sol.z, "pin_yield": _pin_yield,
             "hard_conflict": hard_conflict},
            rules=load_rules(), options=cfg.options,
            out=lambda m: _say(f"[{icao}] {m}", out), records=_late_records)
        install_hold_report(pm.registries.held, _base_rep.hold_report)
        hard_conflict = _late["hard_conflict"]
        cl, cs, stage = _late["cl"], _late["cs_full"], _dc.replace(
            derive.last.stage, pm=pm)
        strips, design_rep = _late["strips"], _late["design"]
        design_rep.stages["base"] = dict(_base_rep.stages)
        _fold_base_rows(design_rep, _base_rep)
        _pin_yield = [*_late["pin_yield"], *(design_rep.pin_yield or ())]
        wall["late_stage"] = time.perf_counter() - t
        _late_report = {"cut": _late["cut"], "followers": _late["followers"],
                        "stage": _late["stage"],
                        "join": _late["join"], "dropped": _late["dropped"],
                        "follow_rows": _late["follow"].get("rows", 0),
                        "lot_rows": _late["follow"].get("lot_rows", 0),
                        "declared_bounds": len(_late["follow"].get("declared", ())),
                        "wall_s": _late["wall_s"]}
    # OWNER RULINGS 2026-09-27a (10): THE RIBBON YIELDS (``emit_stage``)
    pm = with_join_yield(icao, pm, law, airport, sol, _pin_yield, out)
    # ONE solve pass (owner RULINGS 2026-09-08k (4)): joints are geometric,
    # nothing is re-solved on a built step
    # THE SEAM PASSES ARE DELETED (§38 (1); owner RULINGS 2026-09-13ah,
    # attributed 13am).  A seam vertex is a ``Pin``, held exactly by the
    # reduction, so there is no honoured set to iterate to a fixed point.
    # The M3a pass re-ran the whole solve up to six times over the set of
    # seam values the previous solve happened to hold, and at SPLP it
    # OSCILLATED (45 → 28 → 27 → 28 …, terminating on repetition, 12 s of
    # the 24 s build) while shipping 123 residuals up to 3.430 m.
    _say(f"[{icao}] solve {wall['solve']:.2f} s  status {sol.status.value}  "
         f"LP {size}  {sol.message}", out)
    _say(f"[{icao}] {design_rep.line()}", out)
    # THE READS OF THE SOLVED SURFACE (``emit_stage.post_solve``): the
    # runway / taxi / apron blocks, the datum rows, the displacement, the
    # ground envelope (issue #623), the seam and the road agreement
    _post = post_solve(icao, pm, law, airport, sol, cs, design_rep, tt_rep, fv, lrep,
                       seam_yielded, out)
    moved, _envelope, off_ground = _post["moved"], _post["envelope"], _post["off_ground"]
    report_seam, road_agree = _post["seam"], _post["road_agree"]
    report: dict[str, _t.Any] = {
        "icao": icao, "ruleset": law.ruleset_key,
        "load": _dc.asdict(lrep), "planar": _dc.asdict(pstats),
        # §50.4: the OVER-GRADE runways, one record each (§50.1 (4)'s
        # shape) — yielded runways only; EVERY runway's cap is in the
        # sidecar's ``runway_caps``
        "runway_cap_yield": _yield_records,
        "basins": [_dc.asdict(b) for b in pm.basins],
        "constraints": {"by_generator": counts, "by_kind": cs.counts(),
                        "wall_s": {k: round(v, 4) for k, v in gwalls.items()}},
        "lp": size,
        # THE DESIGN SURFACE's residual per family (RULINGS 2026-09-08t):
        # replaces ``law_tiers`` — a law is a TARGET, so a missed one is a
        # residual to report, never a demotion to name
        "design": design_rep.as_dict(),
        "off_dem_by_role": moved,
        "road_profile": road_rep,
        "road_profile_agreement": road_agree,
        "seam": report_seam,
        "shapes": dict(stage.as_dict(), by_shape=pstats.shapes.by_shape),
        "joint_steps": joint_steps(pm, law, stage, sol.z) if sol.z else None,
        "solve": {"status": sol.status.value, "wall_s": round(sol.wall_s, 3),
                  "iterations": sol.iterations, "message": sol.message,
                  "rounds": design_rep.rounds, "converged": design_rep.converged,
                  "residual": None if sol.residual is None else _dc.asdict(sol.residual),
                  # issue #623: empty at every lawful airport
                  "off_ground": {"envelope_m": None if _envelope is None else
                                 [round(_envelope[0], 3), round(_envelope[1], 3)],
                                 "vertices": off_ground[:50],
                                 "count": len(off_ground)}},
    }
    if _late_report is not None:
        report["late_stage"] = _late_report
    paths = None
    vrows = None
    pieces = None
    #: the verify work pool's account (``report["pool"]["verify"]``)
    _vpool: list[dict] = []
    if sol.status.value in ("optimal", "feasible"):
        # THE EMIT (spec §4b.6; ``pipeline/emit_stage.py``) through its
        # record (``pipeline/emit_records.py``; the header is not keyed)
        # its key names the final map, ``z``, design and constraint set by
        # the solve record and the last late solve record (§4b.6)
        _em_in = _emit_records.emit_inputs(
            fc, final=_emit_records.final_identity(
                _solved, None if _late_report is None else _late_records),
            cl=cl, yield_records=_yield_records, lrep=lrep, airport=airport,
            objects_out=objects_out, common=_fc_in, feather_m=cfg.feather_m)
        _em = _emit_records.emit(
            fc, _em_in,
            icao=icao, pm=pm, law=law, airport=airport, sol=sol, cs=cs, cl=cl, strips=strips,
            design_rep=design_rep, hard_conflict=hard_conflict,
            yield_records=_yield_records, late_report=_late_report,
            lrep=lrep, header_extra=cfg.header_extra, out_dir=out_dir,
            objects_out=objects_out, report=report, wall=wall, out=out)
        paths, pieces = _em.paths, _em.pieces
        if cfg.verify:
            # THE VERIFY STAGE (spec §4b.7; ``pipeline/verify_stage.py``):
            # its record holds only while the bodies on disk are the judged
            vrows = _emit_records.verify(fc, _em, pm_digest=_em_in.get("final"),
                                    airport_digest=_em_in.get("airport"),
                                    icao=icao, pm=pm, law=law, airport=airport,
                                    report=report, wall=wall, pool_out=_vpool, out=out)
    report["cache"] = fc.finish()
    _staged = sum(wall.values())
    wall["total"] = time.perf_counter() - t_build
    wall["unclocked"] = wall["total"] - _staged
    report["wall_s"] = {k: round(v, 3) for k, v in wall.items()}
    # the work pools' own account, per stage (clocks and head counts: never
    # in a digest — ``pipeline/xplat.py`` reads the model, not this report)
    # ``verify`` is ``None`` when the apron chords were read on one core by
    # the budget or the size rule (a small airport), or verify did not run
    report["pool"] = {"pack": _ps["pool"], "planar": _pack_read_pool(ocache),
                      "verify": _vpool[-1] if _vpool else None}
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    if _xp:
        # The dump is a READ of the stages already held — it prices no law
        # and counts no defects.  It goes in its OWN file so the report's
        # schema (which the app, the census and the twins read) is
        # untouched by a debugging instrument.
        _xplat.write(str(Path(out_dir) / f"{icao}.xplat.json"),
                     _xplat.stage_digests(
                         icao,
                         airport=_xp.get("partition_airport"),
                         classification=_xp.get("classification"),
                         pm=_xp.get("planar_pm"),
                         stage=stage, constraints=cs, lp=size,
                         solved=sol.z or None, final_pm=pm))
        _say(f"[{icao}] cross-platform stage dump -> {icao}.xplat.json", out)
        if _xp.get("classification") is not None:
            _xplat.write(str(Path(out_dir) / f"{icao}.xcells.json"),
                         _xplat.classify_lines(icao, _xp["classification"]))
        # THE EXACT PROJECTION (lane ``xplatspread``): its OWN file, so a
        # reader that only wants the stage table never parses the ~N-vertex
        # hex table, and vice versa.
        _xplat.write(str(Path(out_dir) / f"{icao}.xproj.json"),
                     _xplat.projection_payload(
                         icao, frame=airport.frame,
                         solved=sol.z or None, final_pm=pm,
                         constraints=cs))
        _say(f"[{icao}] exact projection dump -> {icao}.xproj.json "
             f"(entry quantum {_xplat.projection_quantum():g} m)", out)
        _xplat.disarm_projection()
    (Path(out_dir) / f"{icao}.report.json").write_text(
        json.dumps(report, indent=1, default=str),
        encoding="utf-8", newline="\n")
    _say(f"[{icao}] total {wall['total']:.2f} s  -> {out_dir}", out)
    return BuildResult(icao, pm, cs, counts, sol, paths, vrows, pieces, wall, size, report,
                       Path(out_dir) / f"{icao}.rebake.json" if report.get("rebake_plan")
                       else None,
                       Path(out_dir) / f"{icao}.rebake.screen.json"
                       if report.get("rebake_screen") else None)
