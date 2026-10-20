"""THE V2 STAGE CACHE'S CODE HALF (issue #842, spec
``docs/specs/v2-stage-cache-spec.md`` §4): per cacheable stage, the modules
the stage runs through and ONE digest of their source bytes — taken from
the sources in a checkout, and from the file the FREEZE wrote in a frozen
engine.

The partition's mechanism (``airport/partition_code.py``, #362), stage by
stage: each stage declares where the build ENTERS it
(:data:`ENTRY_MODULES`) and the static import closure of those modules
(:data:`CODE_MODULES`, sorted, every ``import`` in every function
included).  ``tests/auto_patch_v2/test_stage_code_closure.py`` recomputes
each closure and fails on a module the stage imports and its list omits,
and on the reverse.  A module in two closures is keyed by both — an edit
there re-runs both stages, which is the truth.

The closure is limited to ``auto_patch_v2`` (the partition's rule).  The
top-level ``O4_*`` modules a stage reaches are not keyed: the closure
through them is the whole tile core (``planar`` reaches 487 modules with
them, 200 without) — reported on #842 for the spec author to rule.

The stage cache (#843, ``pipeline/front_cache.py``) reads them through
:func:`runtime_digests`.  ``channels`` is the build's TARGET CHANNELS
(``pipeline/prefix.py`` between the road profile and the shape stage: the
runway chord, the taxi and apron trends, the EAT reach, the road ramps and
the coverage join).  They are not cached — they run on every build — but
the shape stage's record is keyed on what they are handed, so their code
is part of the shape record's key.

THE BACK HALF (spec §4b.1, §4b.2; #843 step 9): one entry per constraint
generator, ``constraints.<generator>``, entered at the generator's own
module (``fn.__module__`` — generators of one module share the digest,
never the record), ``constraints.assembly`` (the post-passes and the joint
filter: ``constraints/assembly.py`` + ``pipeline/shapes.py``),
``jetway_strip``; then ``solve``, ``late_cut`` and ``late_solve`` (spec
§4b.4, §4b.5; step 9b), ``emit`` and ``verify`` (§4b.6, §4b.7; step 9c).
Their closures are declared at the end of this file, the generators' as
the modules all of them share plus each module's own.

STDLIB ONLY, NO RELATIVE IMPORT: the specs execute this file with
``runpy`` (they never import engine packages); the shared mechanism
(``src/O4_Code_Closure.py``) is then loaded by path.
"""
from __future__ import annotations

import os

__all__ = ["STAGES", "ENTRY_MODULES", "CODE_MODULES", "CLOSURE_PREFIXES",
           "GENERATOR_MODULES", "generator_stage",
           "DIGEST_FILENAME", "freeze_digests", "write_freeze_digest",
           "frozen_digests", "runtime_digests"]

#: The file the freeze writes beside this module: one ``stage digest``
#: line per stage.
DIGEST_FILENAME = "stage_code.sha256"

#: The closure follows imports into these top-level packages only.
CLOSURE_PREFIXES: tuple[str, ...] = ("auto_patch_v2",)

#: Where the build ENTERS each cached stage (``pipeline/build.build`` for
#: classify, ``pipeline/prefix.run_prefix`` for the rest — the module that
#: DEFINES the function it calls, not a package re-exporting it):
#: ``classify(...)`` / ``load_rules()`` (re-exported by
#: ``classify/__init__``), ``planar.build.build``, ``flat_site_read.verdict_for_build``,
#: ``road_profile.preferred_road_z``, ``shapes.shape_stage``.
ENTRY_MODULES: dict[str, tuple[str, ...]] = {
    "classify": ("auto_patch_v2.classify.roles", "auto_patch_v2.classify.rules"),
    "planar": ("auto_patch_v2.planar.build",),
    "flat_site": ("auto_patch_v2.airport.flat_site_read",),
    "road_profile": ("auto_patch_v2.airport.road_profile",),
    "channels": ("auto_patch_v2.airport.road_ramp", "auto_patch_v2.constraints.apron_trend",
                 "auto_patch_v2.constraints.eat", "auto_patch_v2.constraints.runway_chord",
                 "auto_patch_v2.constraints.taxi_trend", "auto_patch_v2.emit.road_join"),
    "shapes": ("auto_patch_v2.pipeline.shapes",),
}


#: The ONE implementation of the closure, the digest and the digest file
#: (``src/O4_Code_Closure.py``).  Imported in a checkout, a test and a
#: frozen engine; loaded BY PATH when a ``.spec`` executes this file with
#: ``runpy`` (``src`` is not on ``sys.path`` then).
try:
    import O4_Code_Closure as _closure_module
    _CLOSURE = vars(_closure_module)
except ImportError:
    import runpy as _runpy
    _CLOSURE = _runpy.run_path(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir,
        "O4_Code_Closure.py"))


def freeze_digests(src_root: str) -> dict[str, "str | None"]:
    """``{stage: digest}`` of each stage's :data:`CODE_MODULES` read under
    ``src_root`` (the directory holding ``auto_patch_v2``); a stage whose
    list names a module with no source digests to ``None``."""
    return {stage: _CLOSURE["modules_digest"](src_root, CODE_MODULES[stage])
            for stage in STAGES}


def write_freeze_digest(src_root: str, out_dir: str) -> str:
    """THE FREEZE'S ACT: write :func:`freeze_digests` of ``src_root`` to
    ``out_dir/``:data:`DIGEST_FILENAME` and return that path (the specs
    bundle it beside this module).  RAISES ``SystemExit`` when any stage
    has no digest."""
    return _CLOSURE["write_digest_file"](
        out_dir, DIGEST_FILENAME, freeze_digests(src_root),
        "ERROR: could not digest the v2 stage cache's code modules under "
        f"{src_root!r} (stage_code.CODE_MODULES names a module with no "
        "source file) — refusing to freeze an engine whose stage cache "
        "would have no code identity.")


def frozen_digests(directory: str | None = None) -> dict[str, str] | None:
    """The ``{stage: digest}`` table the freeze wrote beside this module,
    or ``None`` (a checkout; an engine frozen by a spec that predates the
    file; a malformed file)."""
    d = directory if directory is not None else os.path.dirname(
        os.path.abspath(__file__))
    return _CLOSURE["read_digest_table"](d, DIGEST_FILENAME)


_RUNTIME: dict[str, "str | None"] | None = None


def runtime_digests() -> dict[str, "str | None"]:
    """``{stage: digest}`` for THIS engine, once per process: of the sources
    in a checkout (``src`` beside this package), else the table the freeze
    wrote (:func:`frozen_digests`).  A stage with neither is ``None`` — the
    stage cache then neither reads nor writes it."""
    global _RUNTIME
    if _RUNTIME is None:
        src_root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        got = freeze_digests(src_root)
        if any(v is None for v in got.values()):
            frozen = frozen_digests() or {}
            got = {s: got.get(s) or frozen.get(s) for s in STAGES}
        _RUNTIME = got
    return dict(_RUNTIME)


#: Each stage's static import closure under :data:`CLOSURE_PREFIXES`,
#: sorted — the code half of its key.  Held by
#: ``tests/auto_patch_v2/test_stage_code_closure.py``; when it fails, the
#: message names the modules to add or drop.  A package is listed as its
#: ``__init__``.
CODE_MODULES: dict[str, tuple[str, ...]] = {
    "classify": (
        "auto_patch_v2",
        "auto_patch_v2.airport",
        "auto_patch_v2.airport.anchor_rule",
        "auto_patch_v2.airport.apt_dat",
        "auto_patch_v2.airport.authored_landing",
        "auto_patch_v2.airport.authored_seat",
        "auto_patch_v2.airport.backup_state",
        "auto_patch_v2.airport.basin_ring",
        "auto_patch_v2.airport.basin_witness",
        "auto_patch_v2.airport.borrow",
        "auto_patch_v2.airport.bridge_family",
        "auto_patch_v2.airport.bulk_geos",
        "auto_patch_v2.airport.cluster_profile",
        "auto_patch_v2.airport.contact",
        "auto_patch_v2.airport.contents",
        "auto_patch_v2.airport.deck_signature",
        "auto_patch_v2.airport.dem",
        "auto_patch_v2.airport.dem_witness",
        "auto_patch_v2.airport.dsf",
        "auto_patch_v2.airport.extension_cache",
        "auto_patch_v2.airport.file_hash",
        "auto_patch_v2.airport.footprint_carry",
        "auto_patch_v2.airport.footprint_connector",
        "auto_patch_v2.airport.footprint_seats",
        "auto_patch_v2.airport.footprint_unit",
        "auto_patch_v2.airport.frame_entry",
        "auto_patch_v2.airport.jetways",
        "auto_patch_v2.airport.line_object",
        "auto_patch_v2.airport.obj8",
        "auto_patch_v2.airport.obj8_clip",
        "auto_patch_v2.airport.obj8_drape",
        "auto_patch_v2.airport.obj8_grade",
        "auto_patch_v2.airport.obj8_roof",
        "auto_patch_v2.airport.obj8_split",
        "auto_patch_v2.airport.one_building",
        "auto_patch_v2.airport.pack",
        "auto_patch_v2.airport.pack_partition",
        "auto_patch_v2.airport.pack_work",
        "auto_patch_v2.airport.pad_block_seat",
        "auto_patch_v2.airport.partition_cache",
        "auto_patch_v2.airport.partition_code",
        "auto_patch_v2.airport.placement_atom",
        "auto_patch_v2.airport.placement_body",
        "auto_patch_v2.airport.placement_boxes",
        "auto_patch_v2.airport.placement_carrier",
        "auto_patch_v2.airport.placement_census",
        "auto_patch_v2.airport.placement_cockpit",
        "auto_patch_v2.airport.placement_contact",
        "auto_patch_v2.airport.placement_cut",
        "auto_patch_v2.airport.placement_deck",
        "auto_patch_v2.airport.placement_family",
        "auto_patch_v2.airport.placement_file",
        "auto_patch_v2.airport.placement_geom",
        "auto_patch_v2.airport.placement_leaves",
        "auto_patch_v2.airport.placement_motion",
        "auto_patch_v2.airport.placement_orphan",
        "auto_patch_v2.airport.placement_plan",
        "auto_patch_v2.airport.placement_read",
        "auto_patch_v2.airport.placement_record",
        "auto_patch_v2.airport.placement_seams",
        "auto_patch_v2.airport.placement_seat_tilt",
        "auto_patch_v2.airport.placement_targets",
        "auto_patch_v2.airport.pool",
        "auto_patch_v2.airport.rebake_plan",
        "auto_patch_v2.airport.riders",
        "auto_patch_v2.airport.road_ways",
        "auto_patch_v2.airport.scatter",
        "auto_patch_v2.airport.sheet_chain",
        "auto_patch_v2.airport.skirt",
        "auto_patch_v2.airport.slab_faces",
        "auto_patch_v2.airport.slab_plates",
        "auto_patch_v2.airport.topology_cache",
        "auto_patch_v2.airport.wall_class",
        "auto_patch_v2.classify",
        "auto_patch_v2.classify.airside_edge",
        "auto_patch_v2.classify.evidence",
        "auto_patch_v2.classify.facade_mint",
        "auto_patch_v2.classify.gap_apron",
        "auto_patch_v2.classify.gap_mint",
        "auto_patch_v2.classify.lot_roads",
        "auto_patch_v2.classify.neck",
        "auto_patch_v2.classify.open_default",
        "auto_patch_v2.classify.pad_touch",
        "auto_patch_v2.classify.reachability",
        "auto_patch_v2.classify.retaining_wall",
        "auto_patch_v2.classify.ribbon_mint",
        "auto_patch_v2.classify.roles",
        "auto_patch_v2.classify.rules",
        "auto_patch_v2.classify.sources",
        "auto_patch_v2.classify.taxi_letter",
        "auto_patch_v2.geom",
        "auto_patch_v2.geom.base_slab",
        "auto_patch_v2.geom.cluster_outline",
        "auto_patch_v2.geom.pad_evidence",
        "auto_patch_v2.geom.parts",
        "auto_patch_v2.geom.proportions",
        "auto_patch_v2.geom.rotated_rect",
        "auto_patch_v2.geom.slope_pad",
        "auto_patch_v2.geom.triangulate",
        "auto_patch_v2.geom.union_find",
        "auto_patch_v2.law",
        "auto_patch_v2.law.airports_schema",
        "auto_patch_v2.law.base_profile_schema",
        "auto_patch_v2.law.basin_schema",
        "auto_patch_v2.law.cockpit_schema",
        "auto_patch_v2.law.cutout_schema",
        "auto_patch_v2.law.design_schema",
        "auto_patch_v2.law.eat_schema",
        "auto_patch_v2.law.flat_site_schema",
        "auto_patch_v2.law.model",
        "auto_patch_v2.law.model_types",
        "auto_patch_v2.law.rebake_schema",
        "auto_patch_v2.law.reference_code",
        "auto_patch_v2.law.role_cap_schema",
        "auto_patch_v2.law.tables",
        "auto_patch_v2.law.terrace_schema",
        "auto_patch_v2.law.tunnel_object_schema",
        "auto_patch_v2.law.units",
        "auto_patch_v2.model",
        "auto_patch_v2.model.airport",
        "auto_patch_v2.model.frame",
        "auto_patch_v2.model.placement",
        "auto_patch_v2.model.planar",
        "auto_patch_v2.model.pulse",
        "auto_patch_v2.model.rebake",
        "auto_patch_v2.model.registries",
        "auto_patch_v2.model.structures",
    ),
    "planar": (
        "auto_patch_v2",
        "auto_patch_v2.airport",
        "auto_patch_v2.airport.anchor_rule",
        "auto_patch_v2.airport.apt_dat",
        "auto_patch_v2.airport.authored_landing",
        "auto_patch_v2.airport.authored_seat",
        "auto_patch_v2.airport.backup_state",
        "auto_patch_v2.airport.basin_ring",
        "auto_patch_v2.airport.basin_witness",
        "auto_patch_v2.airport.below_zero",
        "auto_patch_v2.airport.borrow",
        "auto_patch_v2.airport.bridge_family",
        "auto_patch_v2.airport.bulk_geos",
        "auto_patch_v2.airport.cluster_profile",
        "auto_patch_v2.airport.contact",
        "auto_patch_v2.airport.contents",
        "auto_patch_v2.airport.deck_signature",
        "auto_patch_v2.airport.dem",
        "auto_patch_v2.airport.dem_production",
        "auto_patch_v2.airport.dem_shared",
        "auto_patch_v2.airport.dem_witness",
        "auto_patch_v2.airport.door_wells",
        "auto_patch_v2.airport.dsf",
        "auto_patch_v2.airport.extension_cache",
        "auto_patch_v2.airport.file_hash",
        "auto_patch_v2.airport.footprint_carry",
        "auto_patch_v2.airport.footprint_connector",
        "auto_patch_v2.airport.footprint_seats",
        "auto_patch_v2.airport.footprint_unit",
        "auto_patch_v2.airport.frame_entry",
        "auto_patch_v2.airport.grade_ledger",
        "auto_patch_v2.airport.jetways",
        "auto_patch_v2.airport.line_object",
        "auto_patch_v2.airport.obj8",
        "auto_patch_v2.airport.obj8_clip",
        "auto_patch_v2.airport.obj8_drape",
        "auto_patch_v2.airport.obj8_grade",
        "auto_patch_v2.airport.obj8_roof",
        "auto_patch_v2.airport.obj8_split",
        "auto_patch_v2.airport.object_cut",
        "auto_patch_v2.airport.one_building",
        "auto_patch_v2.airport.pack",
        "auto_patch_v2.airport.pack_partition",
        "auto_patch_v2.airport.pack_work",
        "auto_patch_v2.airport.pad_block_seat",
        "auto_patch_v2.airport.partition_cache",
        "auto_patch_v2.airport.partition_code",
        "auto_patch_v2.airport.placement_atom",
        "auto_patch_v2.airport.placement_body",
        "auto_patch_v2.airport.placement_boxes",
        "auto_patch_v2.airport.placement_carrier",
        "auto_patch_v2.airport.placement_census",
        "auto_patch_v2.airport.placement_cockpit",
        "auto_patch_v2.airport.placement_contact",
        "auto_patch_v2.airport.placement_cut",
        "auto_patch_v2.airport.placement_deck",
        "auto_patch_v2.airport.placement_family",
        "auto_patch_v2.airport.placement_file",
        "auto_patch_v2.airport.placement_geom",
        "auto_patch_v2.airport.placement_leaves",
        "auto_patch_v2.airport.placement_motion",
        "auto_patch_v2.airport.placement_orphan",
        "auto_patch_v2.airport.placement_plan",
        "auto_patch_v2.airport.placement_read",
        "auto_patch_v2.airport.placement_record",
        "auto_patch_v2.airport.placement_seams",
        "auto_patch_v2.airport.placement_seat_tilt",
        "auto_patch_v2.airport.placement_targets",
        "auto_patch_v2.airport.pool",
        "auto_patch_v2.airport.ramp_feet",
        "auto_patch_v2.airport.reader_work",
        "auto_patch_v2.airport.rebake_plan",
        "auto_patch_v2.airport.riders",
        "auto_patch_v2.airport.road_profile",
        "auto_patch_v2.airport.road_ways",
        "auto_patch_v2.airport.scatter",
        "auto_patch_v2.airport.sheet_chain",
        "auto_patch_v2.airport.skirt",
        "auto_patch_v2.airport.slab_faces",
        "auto_patch_v2.airport.slab_plates",
        "auto_patch_v2.airport.sunken_ramp",
        "auto_patch_v2.airport.sunken_roads",
        "auto_patch_v2.airport.thin_plates",
        "auto_patch_v2.airport.topology_cache",
        "auto_patch_v2.airport.tunnel_objects",
        "auto_patch_v2.airport.tunnel_walls",
        "auto_patch_v2.airport.wall_class",
        "auto_patch_v2.airport.wall_corridor_probe",
        "auto_patch_v2.airport.wall_corridors",
        "auto_patch_v2.airport.wall_family",
        "auto_patch_v2.airport.wall_geometry",
        "auto_patch_v2.airport.wall_mouth",
        "auto_patch_v2.classify",
        "auto_patch_v2.classify.airside_edge",
        "auto_patch_v2.classify.evidence",
        "auto_patch_v2.classify.facade_mint",
        "auto_patch_v2.classify.gap_apron",
        "auto_patch_v2.classify.gap_mint",
        "auto_patch_v2.classify.lot_roads",
        "auto_patch_v2.classify.neck",
        "auto_patch_v2.classify.open_default",
        "auto_patch_v2.classify.pad_touch",
        "auto_patch_v2.classify.ramp_runout",
        "auto_patch_v2.classify.reachability",
        "auto_patch_v2.classify.retaining_wall",
        "auto_patch_v2.classify.ribbon_mint",
        "auto_patch_v2.classify.roles",
        "auto_patch_v2.classify.rules",
        "auto_patch_v2.classify.sources",
        "auto_patch_v2.classify.taxi_letter",
        "auto_patch_v2.geom",
        "auto_patch_v2.geom.base_slab",
        "auto_patch_v2.geom.cluster_outline",
        "auto_patch_v2.geom.containment",
        "auto_patch_v2.geom.core_clamp",
        "auto_patch_v2.geom.coverage",
        "auto_patch_v2.geom.pad_evidence",
        "auto_patch_v2.geom.parts",
        "auto_patch_v2.geom.proportions",
        "auto_patch_v2.geom.ramp_grade",
        "auto_patch_v2.geom.ramp_profile",
        "auto_patch_v2.geom.rotated_rect",
        "auto_patch_v2.geom.slope_pad",
        "auto_patch_v2.geom.triangulate",
        "auto_patch_v2.geom.union_find",
        "auto_patch_v2.geom.vector",
        "auto_patch_v2.law",
        "auto_patch_v2.law.airports_schema",
        "auto_patch_v2.law.approach_corridor",
        "auto_patch_v2.law.base_profile_schema",
        "auto_patch_v2.law.basin_schema",
        "auto_patch_v2.law.cockpit_schema",
        "auto_patch_v2.law.cutout_schema",
        "auto_patch_v2.law.design_schema",
        "auto_patch_v2.law.eat_schema",
        "auto_patch_v2.law.flat_site_schema",
        "auto_patch_v2.law.inset_class",
        "auto_patch_v2.law.model",
        "auto_patch_v2.law.model_types",
        "auto_patch_v2.law.rebake_schema",
        "auto_patch_v2.law.reference_code",
        "auto_patch_v2.law.role_cap_schema",
        "auto_patch_v2.law.tables",
        "auto_patch_v2.law.terrace_schema",
        "auto_patch_v2.law.tunnel_object_schema",
        "auto_patch_v2.law.units",
        "auto_patch_v2.model",
        "auto_patch_v2.model.airport",
        "auto_patch_v2.model.end_area",
        "auto_patch_v2.model.frame",
        "auto_patch_v2.model.islands",
        "auto_patch_v2.model.map_memo",
        "auto_patch_v2.model.pad_terrace",
        "auto_patch_v2.model.placement",
        "auto_patch_v2.model.planar",
        "auto_patch_v2.model.platform",
        "auto_patch_v2.model.pulse",
        "auto_patch_v2.model.rebake",
        "auto_patch_v2.model.registries",
        "auto_patch_v2.model.structures",
        "auto_patch_v2.planar",
        "auto_patch_v2.planar.apron_shelf",
        "auto_patch_v2.planar.basin_datum",
        "auto_patch_v2.planar.basin_geometry",
        "auto_patch_v2.planar.basin_rim",
        "auto_patch_v2.planar.basins",
        "auto_patch_v2.planar.build",
        "auto_patch_v2.planar.channel",
        "auto_patch_v2.planar.channel_claims",
        "auto_patch_v2.planar.channel_floor",
        "auto_patch_v2.planar.channel_geometry",
        "auto_patch_v2.planar.channel_witness",
        "auto_patch_v2.planar.chords",
        "auto_patch_v2.planar.covered_ground",
        "auto_patch_v2.planar.door_ramps",
        "auto_patch_v2.planar.edges",
        "auto_patch_v2.planar.landing",
        "auto_patch_v2.planar.landing_runout",
        "auto_patch_v2.planar.object_corridor",
        "auto_patch_v2.planar.overlay",
        "auto_patch_v2.planar.pack_reads",
        "auto_patch_v2.planar.pad_blocks",
        "auto_patch_v2.planar.pad_cut",
        "auto_patch_v2.planar.pad_sliver",
        "auto_patch_v2.planar.pad_terrace",
        "auto_patch_v2.planar.platform",
        "auto_patch_v2.planar.ribbon_weld",
        "auto_patch_v2.planar.ribbons",
        "auto_patch_v2.planar.ridge_reach",
        "auto_patch_v2.planar.road_yield",
        "auto_patch_v2.planar.shape_airside",
        "auto_patch_v2.planar.shape_mouths",
        "auto_patch_v2.planar.shape_parts",
        "auto_patch_v2.planar.shapes",
        "auto_patch_v2.planar.shore",
        "auto_patch_v2.planar.strip_keepout",
        "auto_patch_v2.planar.structure_approach",
        "auto_patch_v2.planar.structure_deck",
        "auto_patch_v2.planar.structure_geometry",
        "auto_patch_v2.planar.structure_mouth",
        "auto_patch_v2.planar.structure_overlap",
        "auto_patch_v2.planar.structure_pair",
        "auto_patch_v2.planar.structure_road",
        "auto_patch_v2.planar.structure_service",
        "auto_patch_v2.planar.structure_stats",
        "auto_patch_v2.planar.structure_underpass",
        "auto_patch_v2.planar.structures",
        "auto_patch_v2.planar.terrain_edge",
        "auto_patch_v2.planar.unframed_ramp",
        "auto_patch_v2.planar.wall_corridor_ramps",
        "auto_patch_v2.planar.weld",
        "auto_patch_v2.planar.zone_pass",
        "auto_patch_v2.planar.zones",
    ),
    "flat_site": (
        "auto_patch_v2",
        "auto_patch_v2.airport",
        "auto_patch_v2.airport.dem",
        "auto_patch_v2.airport.dem_production",
        "auto_patch_v2.airport.flat_site",
        "auto_patch_v2.airport.flat_site_read",
        "auto_patch_v2.geom",
        "auto_patch_v2.geom.rotated_rect",
        "auto_patch_v2.law",
        "auto_patch_v2.law.airports_schema",
        "auto_patch_v2.law.base_profile_schema",
        "auto_patch_v2.law.basin_schema",
        "auto_patch_v2.law.cockpit_schema",
        "auto_patch_v2.law.cutout_schema",
        "auto_patch_v2.law.design_schema",
        "auto_patch_v2.law.eat_schema",
        "auto_patch_v2.law.flat_site_schema",
        "auto_patch_v2.law.inset_class",
        "auto_patch_v2.law.model",
        "auto_patch_v2.law.model_types",
        "auto_patch_v2.law.rebake_schema",
        "auto_patch_v2.law.reference_code",
        "auto_patch_v2.law.role_cap_schema",
        "auto_patch_v2.law.tables",
        "auto_patch_v2.law.terrace_schema",
        "auto_patch_v2.law.tunnel_object_schema",
        "auto_patch_v2.law.units",
        "auto_patch_v2.model",
        "auto_patch_v2.model.airport",
        "auto_patch_v2.model.frame",
    ),
    "road_profile": (
        "auto_patch_v2",
        "auto_patch_v2.airport",
        "auto_patch_v2.airport.road_profile",
        "auto_patch_v2.geom",
        "auto_patch_v2.geom.core_clamp",
        "auto_patch_v2.geom.coverage",
        "auto_patch_v2.geom.rotated_rect",
        "auto_patch_v2.law",
        "auto_patch_v2.law.airports_schema",
        "auto_patch_v2.law.base_profile_schema",
        "auto_patch_v2.law.basin_schema",
        "auto_patch_v2.law.cockpit_schema",
        "auto_patch_v2.law.cutout_schema",
        "auto_patch_v2.law.design_schema",
        "auto_patch_v2.law.eat_schema",
        "auto_patch_v2.law.flat_site_schema",
        "auto_patch_v2.law.model",
        "auto_patch_v2.law.model_types",
        "auto_patch_v2.law.rebake_schema",
        "auto_patch_v2.law.reference_code",
        "auto_patch_v2.law.role_cap_schema",
        "auto_patch_v2.law.tables",
        "auto_patch_v2.law.terrace_schema",
        "auto_patch_v2.law.tunnel_object_schema",
        "auto_patch_v2.law.units",
        "auto_patch_v2.model",
        "auto_patch_v2.model.airport",
        "auto_patch_v2.model.frame",
        "auto_patch_v2.model.planar",
        "auto_patch_v2.model.registries",
        "auto_patch_v2.model.structures",
    ),
    "channels": (
        "auto_patch_v2",
        "auto_patch_v2.airport",
        "auto_patch_v2.airport.dem",
        "auto_patch_v2.airport.road_descent",
        "auto_patch_v2.airport.road_profile",
        "auto_patch_v2.airport.road_ramp",
        "auto_patch_v2.airport.wall_class",
        "auto_patch_v2.constraints",
        "auto_patch_v2.constraints.apron",
        "auto_patch_v2.constraints.apron_trend",
        "auto_patch_v2.constraints.cluster_pad",
        "auto_patch_v2.constraints.eat",
        "auto_patch_v2.constraints.geometry",
        "auto_patch_v2.constraints.pad_relief",
        "auto_patch_v2.constraints.pad_warning",
        "auto_patch_v2.constraints.pads",
        "auto_patch_v2.constraints.platform",
        "auto_patch_v2.constraints.precedence",
        "auto_patch_v2.constraints.routes",
        "auto_patch_v2.constraints.runway_chord",
        "auto_patch_v2.constraints.runway_profile",
        "auto_patch_v2.constraints.runway_yield",
        "auto_patch_v2.constraints.shoulder_crossing",
        "auto_patch_v2.constraints.stretches",
        "auto_patch_v2.constraints.surface_trend",
        "auto_patch_v2.constraints.taxi",
        "auto_patch_v2.constraints.taxi_trend",
        "auto_patch_v2.constraints.taxi_trend_cap",
        "auto_patch_v2.constraints.trend",
        "auto_patch_v2.emit",
        "auto_patch_v2.emit.road_join",
        "auto_patch_v2.geom",
        "auto_patch_v2.geom.base_slab",
        "auto_patch_v2.geom.cluster_outline",
        "auto_patch_v2.geom.containment",
        "auto_patch_v2.geom.core_clamp",
        "auto_patch_v2.geom.coverage",
        "auto_patch_v2.geom.pad_evidence",
        "auto_patch_v2.geom.ramp_grade",
        "auto_patch_v2.geom.rotated_rect",
        "auto_patch_v2.geom.slope_pad",
        "auto_patch_v2.geom.triangulate",
        "auto_patch_v2.geom.union_find",
        "auto_patch_v2.law",
        "auto_patch_v2.law.airports_schema",
        "auto_patch_v2.law.base_profile_schema",
        "auto_patch_v2.law.basin_schema",
        "auto_patch_v2.law.cockpit_schema",
        "auto_patch_v2.law.cutout_schema",
        "auto_patch_v2.law.design_schema",
        "auto_patch_v2.law.eat_schema",
        "auto_patch_v2.law.flat_site_schema",
        "auto_patch_v2.law.inset_class",
        "auto_patch_v2.law.model",
        "auto_patch_v2.law.model_types",
        "auto_patch_v2.law.rebake_schema",
        "auto_patch_v2.law.reference_code",
        "auto_patch_v2.law.role_cap_schema",
        "auto_patch_v2.law.tables",
        "auto_patch_v2.law.terrace_schema",
        "auto_patch_v2.law.tunnel_object_schema",
        "auto_patch_v2.law.units",
        "auto_patch_v2.model",
        "auto_patch_v2.model.airport",
        "auto_patch_v2.model.constraints",
        "auto_patch_v2.model.frame",
        "auto_patch_v2.model.islands",
        "auto_patch_v2.model.map_memo",
        "auto_patch_v2.model.planar",
        "auto_patch_v2.model.platform",
        "auto_patch_v2.model.registries",
        "auto_patch_v2.model.structures",
    ),
    "shapes": (
        "auto_patch_v2",
        "auto_patch_v2.airport",
        "auto_patch_v2.airport.anchor_rule",
        "auto_patch_v2.airport.apt_dat",
        "auto_patch_v2.airport.authored_landing",
        "auto_patch_v2.airport.authored_seat",
        "auto_patch_v2.airport.backup_state",
        "auto_patch_v2.airport.basin_ring",
        "auto_patch_v2.airport.basin_witness",
        "auto_patch_v2.airport.borrow",
        "auto_patch_v2.airport.bridge_family",
        "auto_patch_v2.airport.bulk_geos",
        "auto_patch_v2.airport.cluster_profile",
        "auto_patch_v2.airport.contact",
        "auto_patch_v2.airport.contents",
        "auto_patch_v2.airport.deck_signature",
        "auto_patch_v2.airport.dem",
        "auto_patch_v2.airport.dem_witness",
        "auto_patch_v2.airport.dsf",
        "auto_patch_v2.airport.extension_cache",
        "auto_patch_v2.airport.file_hash",
        "auto_patch_v2.airport.footprint_carry",
        "auto_patch_v2.airport.footprint_connector",
        "auto_patch_v2.airport.footprint_seats",
        "auto_patch_v2.airport.footprint_unit",
        "auto_patch_v2.airport.frame_entry",
        "auto_patch_v2.airport.jetways",
        "auto_patch_v2.airport.line_object",
        "auto_patch_v2.airport.obj8",
        "auto_patch_v2.airport.obj8_clip",
        "auto_patch_v2.airport.obj8_drape",
        "auto_patch_v2.airport.obj8_grade",
        "auto_patch_v2.airport.obj8_roof",
        "auto_patch_v2.airport.obj8_split",
        "auto_patch_v2.airport.one_building",
        "auto_patch_v2.airport.pack",
        "auto_patch_v2.airport.pack_partition",
        "auto_patch_v2.airport.pack_work",
        "auto_patch_v2.airport.pad_block_seat",
        "auto_patch_v2.airport.partition_cache",
        "auto_patch_v2.airport.partition_code",
        "auto_patch_v2.airport.placement_atom",
        "auto_patch_v2.airport.placement_body",
        "auto_patch_v2.airport.placement_boxes",
        "auto_patch_v2.airport.placement_carrier",
        "auto_patch_v2.airport.placement_census",
        "auto_patch_v2.airport.placement_cockpit",
        "auto_patch_v2.airport.placement_contact",
        "auto_patch_v2.airport.placement_cut",
        "auto_patch_v2.airport.placement_deck",
        "auto_patch_v2.airport.placement_family",
        "auto_patch_v2.airport.placement_file",
        "auto_patch_v2.airport.placement_geom",
        "auto_patch_v2.airport.placement_leaves",
        "auto_patch_v2.airport.placement_motion",
        "auto_patch_v2.airport.placement_orphan",
        "auto_patch_v2.airport.placement_plan",
        "auto_patch_v2.airport.placement_read",
        "auto_patch_v2.airport.placement_record",
        "auto_patch_v2.airport.placement_seams",
        "auto_patch_v2.airport.placement_seat_tilt",
        "auto_patch_v2.airport.placement_targets",
        "auto_patch_v2.airport.pool",
        "auto_patch_v2.airport.rebake_plan",
        "auto_patch_v2.airport.riders",
        "auto_patch_v2.airport.road_ways",
        "auto_patch_v2.airport.scatter",
        "auto_patch_v2.airport.sheet_chain",
        "auto_patch_v2.airport.skirt",
        "auto_patch_v2.airport.slab_faces",
        "auto_patch_v2.airport.slab_plates",
        "auto_patch_v2.airport.topology_cache",
        "auto_patch_v2.airport.wall_class",
        "auto_patch_v2.classify",
        "auto_patch_v2.classify.airside_edge",
        "auto_patch_v2.classify.evidence",
        "auto_patch_v2.classify.facade_mint",
        "auto_patch_v2.classify.gap_apron",
        "auto_patch_v2.classify.gap_mint",
        "auto_patch_v2.classify.lot_roads",
        "auto_patch_v2.classify.neck",
        "auto_patch_v2.classify.open_default",
        "auto_patch_v2.classify.pad_touch",
        "auto_patch_v2.classify.reachability",
        "auto_patch_v2.classify.retaining_wall",
        "auto_patch_v2.classify.ribbon_mint",
        "auto_patch_v2.classify.roles",
        "auto_patch_v2.classify.rules",
        "auto_patch_v2.classify.sources",
        "auto_patch_v2.classify.taxi_letter",
        "auto_patch_v2.constraints",
        "auto_patch_v2.constraints.apron",
        "auto_patch_v2.constraints.apron_shelf",
        "auto_patch_v2.constraints.assembly",
        "auto_patch_v2.constraints.ceiling",
        "auto_patch_v2.constraints.channel",
        "auto_patch_v2.constraints.cluster_pad",
        "auto_patch_v2.constraints.contiguity",
        "auto_patch_v2.constraints.door_pad",
        "auto_patch_v2.constraints.eat",
        "auto_patch_v2.constraints.end_lip",
        "auto_patch_v2.constraints.flat_site",
        "auto_patch_v2.constraints.foot_rows",
        "auto_patch_v2.constraints.geometry",
        "auto_patch_v2.constraints.groundside",
        "auto_patch_v2.constraints.hard_plane",
        "auto_patch_v2.constraints.junction_mesh",
        "auto_patch_v2.constraints.no_step",
        "auto_patch_v2.constraints.pad_frontage_gs",
        "auto_patch_v2.constraints.pad_fronting",
        "auto_patch_v2.constraints.pad_ramp",
        "auto_patch_v2.constraints.pad_relief",
        "auto_patch_v2.constraints.pad_warning",
        "auto_patch_v2.constraints.pads",
        "auto_patch_v2.constraints.pavement_cap",
        "auto_patch_v2.constraints.platform",
        "auto_patch_v2.constraints.precedence",
        "auto_patch_v2.constraints.proximity",
        "auto_patch_v2.constraints.ramp_runout",
        "auto_patch_v2.constraints.road_ramp",
        "auto_patch_v2.constraints.roads",
        "auto_patch_v2.constraints.routes",
        "auto_patch_v2.constraints.runway_chord",
        "auto_patch_v2.constraints.runway_mean_slope",
        "auto_patch_v2.constraints.runway_profile",
        "auto_patch_v2.constraints.runway_yield",
        "auto_patch_v2.constraints.seams",
        "auto_patch_v2.constraints.shoulder_crossing",
        "auto_patch_v2.constraints.stretches",
        "auto_patch_v2.constraints.strips",
        "auto_patch_v2.constraints.structures",
        "auto_patch_v2.constraints.taxi",
        "auto_patch_v2.constraints.taxi_trend",
        "auto_patch_v2.constraints.taxi_trend_cap",
        "auto_patch_v2.constraints.transverse",
        "auto_patch_v2.constraints.trend",
        "auto_patch_v2.constraints.water",
        "auto_patch_v2.constraints.weld_floor",
        "auto_patch_v2.constraints.zones",
        "auto_patch_v2.geom",
        "auto_patch_v2.geom.base_slab",
        "auto_patch_v2.geom.cluster_outline",
        "auto_patch_v2.geom.containment",
        "auto_patch_v2.geom.core_clamp",
        "auto_patch_v2.geom.feet_graph",
        "auto_patch_v2.geom.feet_mst",
        "auto_patch_v2.geom.pad_evidence",
        "auto_patch_v2.geom.parts",
        "auto_patch_v2.geom.proportions",
        "auto_patch_v2.geom.ramp_grade",
        "auto_patch_v2.geom.ramp_profile",
        "auto_patch_v2.geom.rotated_rect",
        "auto_patch_v2.geom.slope_pad",
        "auto_patch_v2.geom.triangulate",
        "auto_patch_v2.geom.union_find",
        "auto_patch_v2.law",
        "auto_patch_v2.law.airports_schema",
        "auto_patch_v2.law.base_profile_schema",
        "auto_patch_v2.law.basin_schema",
        "auto_patch_v2.law.cockpit_schema",
        "auto_patch_v2.law.cutout_schema",
        "auto_patch_v2.law.design_schema",
        "auto_patch_v2.law.eat_schema",
        "auto_patch_v2.law.flat_site_schema",
        "auto_patch_v2.law.inset_class",
        "auto_patch_v2.law.model",
        "auto_patch_v2.law.model_types",
        "auto_patch_v2.law.rebake_schema",
        "auto_patch_v2.law.reference_code",
        "auto_patch_v2.law.role_cap_schema",
        "auto_patch_v2.law.tables",
        "auto_patch_v2.law.terrace_schema",
        "auto_patch_v2.law.tunnel_object_schema",
        "auto_patch_v2.law.units",
        "auto_patch_v2.model",
        "auto_patch_v2.model.airport",
        "auto_patch_v2.model.constraints",
        "auto_patch_v2.model.end_area",
        "auto_patch_v2.model.frame",
        "auto_patch_v2.model.ground_fit",
        "auto_patch_v2.model.hard_plane",
        "auto_patch_v2.model.islands",
        "auto_patch_v2.model.map_memo",
        "auto_patch_v2.model.placement",
        "auto_patch_v2.model.planar",
        "auto_patch_v2.model.platform",
        "auto_patch_v2.model.pulse",
        "auto_patch_v2.model.rebake",
        "auto_patch_v2.model.registries",
        "auto_patch_v2.model.structures",
        "auto_patch_v2.model.threshold_datum",
        "auto_patch_v2.pipeline",
        "auto_patch_v2.pipeline.shapes",
        "auto_patch_v2.planar",
        "auto_patch_v2.planar.shape_airside",
        "auto_patch_v2.planar.shape_mouths",
        "auto_patch_v2.planar.shape_parts",
        "auto_patch_v2.planar.shapes",
        "auto_patch_v2.planar.strip_keepout",
    ),
}


def _mods(names: str) -> tuple[str, ...]:
    """``auto_patch_v2``-relative module names, whitespace-separated, as the
    sorted tuple :data:`CODE_MODULES` holds — with ``auto_patch_v2`` itself,
    the package above every one of them (#993)."""
    return tuple(sorted(["auto_patch_v2",
                         *(f"auto_patch_v2.{n}" for n in names.split())]))


#: Each constraint generator's module (``constraints.GENERATORS``: name ->
#: ``fn.__module__``), held by ``test_stage_code_closure.py``.
GENERATOR_MODULES: dict[str, str] = {
    "runway_profile": "runway_profile",
    "runway_crown": "runway_profile",
    "runway_transverse": "runway_profile",
    "runway_vertical_curve": "runway_profile",
    "runway_mean_slope": "runway_mean_slope",
    "runway_within_shape": "runway_profile",
    "runway_crossing_pin": "runway_chord",
    "taxi_chain": "taxi",
    "taxi_centerlines": "taxi",
    "triangle_planes": "taxi",
    "taxi_box": "taxi",
    "junction_mesh": "junction_mesh",
    "apron_within_shape": "apron",
    "hard_plane_level": "hard_plane",
    "door_pad_level": "door_pad",
    "apron_edge_portions": "apron",
    "road_within_shape": "roads",
    "road_ramp": "road_ramp",
    "road_contact": "road_ramp",
    "road_coverage_join": "road_ramp",
    "wall_terrace": "road_ramp",
    "groundside_ramp": "groundside",
    "transverse": "transverse",
    "junction_raw_transverse": "transverse",
    "no_step_pairs": "no_step",
    "no_step_rate": "no_step",
    "cross_shape_pairs": "proximity",
    "reach_bands": "no_step",
    "zone_bands": "zones",
    "strip_transverse": "zones",
    "strip_longitudinal": "strips",
    "strip_arc": "strips",
    "resa_transverse": "strips",
    "end_corridor_longitudinal": "strips",
    "end_corridor_rate": "strips",
    "raoa": "strips",
    "pad_flats": "pads",
    "pad_frontage_level": "pads",
    "pad_fronting_level": "pad_fronting",
    "pad_slope_ceiling": "pads",
    "platform_collar": "platform",
    "block_strip": "platform",
    "platform_plane": "platform",
    "landing_level": "platform",
    "landing_runout": "ramp_runout",
    "platform_level": "platform",
    "frontage_hold": "platform",
    "frontage_near_miss": "pads",
    "groundside_frontage_level": "pad_frontage_gs",
    "eat_anchor_rect": "eat",
    "water_pins": "water",
    "seam_pins": "seams",
    "flat_datum": "flat_site",
    "foot_rows": "foot_rows",
    "structures": "structures",
    "rim_level": "structures",
    "basins": "structures",
    "channels": "channel",
}

#: The modules every generator module's closure holds.
_GENERATOR_CORE = """
    constraints geom geom.rotated_rect law law.airports_schema law.base_profile_schema
    law.basin_schema law.cockpit_schema law.cutout_schema law.design_schema
    law.eat_schema law.flat_site_schema law.model law.model_types law.rebake_schema
    law.reference_code law.role_cap_schema law.tables law.terrace_schema
    law.tunnel_object_schema law.units model model.constraints model.frame model.planar
    model.registries model.structures
"""

#: The rest of each generator module's import closure, keyed by module.
_GENERATOR_CLOSURES: dict[str, tuple[str, ...]] = {
    "apron": _mods(_GENERATOR_CORE + """
        constraints.apron constraints.geometry constraints.precedence model.airport
    """),
    "channel": _mods(_GENERATOR_CORE + """
        constraints.channel constraints.geometry constraints.precedence model.airport
    """),
    "eat": _mods(_GENERATOR_CORE + """
        constraints.apron constraints.cluster_pad constraints.eat constraints.geometry
        constraints.pad_relief constraints.pad_warning constraints.pads
        constraints.platform constraints.precedence constraints.routes
        constraints.runway_chord constraints.runway_profile constraints.runway_yield
        constraints.shoulder_crossing constraints.stretches constraints.taxi
        constraints.taxi_trend constraints.taxi_trend_cap constraints.trend
        geom.base_slab geom.cluster_outline geom.containment geom.core_clamp
        geom.slope_pad
        geom.pad_evidence geom.triangulate geom.union_find law.inset_class model.airport
        model.islands model.map_memo model.platform
    """),
    "flat_site": _mods(_GENERATOR_CORE + """
        constraints.flat_site constraints.geometry constraints.precedence model.airport
    """),
    "foot_rows": _mods(_GENERATOR_CORE + """
        constraints.apron constraints.cluster_pad constraints.foot_rows
        constraints.geometry constraints.pad_relief constraints.pad_warning
        constraints.pads constraints.platform constraints.precedence
        constraints.structures geom.base_slab geom.cluster_outline geom.containment
        geom.slope_pad
        geom.feet_graph geom.feet_mst geom.pad_evidence geom.triangulate geom.union_find
        model.airport model.ground_fit model.islands model.map_memo model.platform
    """),
    "groundside": _mods(_GENERATOR_CORE + """
        constraints.geometry constraints.groundside constraints.precedence
    """),
    "hard_plane": _mods(_GENERATOR_CORE + """
        constraints.hard_plane model.airport model.hard_plane
    """),
    "door_pad": _mods(_GENERATOR_CORE + """
        constraints.apron constraints.door_pad constraints.geometry constraints.precedence
        geom.slope_pad model.airport
    """),
    "junction_mesh": _mods(_GENERATOR_CORE + """
        constraints.apron constraints.cluster_pad constraints.geometry
        constraints.junction_mesh constraints.pad_relief constraints.pad_warning
        constraints.pads constraints.platform constraints.precedence constraints.routes
        constraints.stretches constraints.taxi geom.base_slab geom.cluster_outline
        geom.slope_pad
        geom.containment geom.pad_evidence geom.triangulate geom.union_find
        model.airport model.islands model.map_memo model.platform
    """),
    "no_step": _mods(_GENERATOR_CORE + """
        constraints.apron constraints.ceiling constraints.cluster_pad
        constraints.contiguity constraints.end_lip constraints.geometry
        constraints.groundside constraints.no_step constraints.pad_frontage_gs
        constraints.pad_relief constraints.pad_warning constraints.pads
        constraints.platform constraints.precedence constraints.roads constraints.routes
        constraints.runway_profile constraints.shoulder_crossing constraints.stretches
        constraints.strips constraints.transverse constraints.trend
        constraints.weld_floor geom.base_slab geom.cluster_outline geom.containment
        geom.slope_pad
        geom.pad_evidence geom.triangulate geom.union_find model.airport model.end_area
        model.islands model.map_memo model.platform model.threshold_datum
    """),
    "pad_frontage_gs": _mods(_GENERATOR_CORE + """
        constraints.apron constraints.cluster_pad constraints.geometry
        constraints.groundside constraints.pad_frontage_gs constraints.pad_relief
        constraints.pad_warning constraints.pads constraints.platform
        constraints.precedence geom.base_slab geom.cluster_outline geom.containment
        geom.slope_pad
        geom.pad_evidence geom.triangulate geom.union_find model.airport model.islands
        model.map_memo model.platform
    """),
    "pad_fronting": _mods(_GENERATOR_CORE + """
        constraints.apron constraints.cluster_pad constraints.geometry
        constraints.pad_fronting constraints.pad_relief constraints.pad_warning
        constraints.pads constraints.platform constraints.precedence geom.base_slab
        geom.cluster_outline geom.containment geom.pad_evidence geom.triangulate
        geom.slope_pad
        geom.union_find model.airport model.islands model.map_memo model.platform
    """),
    "pads": _mods(_GENERATOR_CORE + """
        constraints.apron constraints.cluster_pad constraints.geometry
        constraints.pad_relief constraints.pad_warning constraints.pads
        constraints.platform constraints.precedence geom.base_slab geom.cluster_outline
        geom.containment geom.pad_evidence geom.triangulate geom.union_find
        model.airport model.islands model.map_memo model.platform
        geom.slope_pad
    """),
    "platform": _mods(_GENERATOR_CORE + """
        constraints.apron constraints.cluster_pad constraints.geometry
        constraints.pad_relief constraints.pad_warning constraints.pads
        constraints.platform constraints.precedence geom.base_slab geom.cluster_outline
        geom.containment geom.pad_evidence geom.triangulate geom.union_find
        model.airport model.islands model.map_memo model.platform
        geom.slope_pad
    """),
    "proximity": _mods(_GENERATOR_CORE + """
        constraints.contiguity constraints.end_lip constraints.geometry
        constraints.precedence constraints.proximity constraints.roads
        constraints.strips geom.containment model.airport model.end_area model.islands
        model.map_memo model.platform model.threshold_datum
    """),
    "ramp_runout": _mods(_GENERATOR_CORE + """
        constraints.apron constraints.apron_shelf constraints.cluster_pad
        constraints.geometry constraints.pad_ramp constraints.pad_relief
        constraints.pad_warning constraints.pads constraints.platform
        constraints.precedence constraints.ramp_runout constraints.road_ramp
        geom.base_slab geom.cluster_outline geom.containment geom.pad_evidence
        geom.slope_pad
        geom.ramp_grade geom.ramp_profile geom.triangulate geom.union_find model.airport
        model.islands model.map_memo model.platform
    """),
    "road_ramp": _mods(_GENERATOR_CORE + """
        constraints.apron constraints.apron_shelf constraints.cluster_pad
        constraints.geometry constraints.pad_relief constraints.pad_warning
        constraints.pads constraints.platform constraints.precedence
        constraints.road_ramp geom.base_slab geom.cluster_outline geom.containment
        geom.slope_pad
        geom.pad_evidence geom.ramp_grade geom.triangulate geom.union_find model.airport
        model.islands model.map_memo model.platform
    """),
    "roads": _mods(_GENERATOR_CORE + """
        constraints.contiguity constraints.end_lip constraints.geometry
        constraints.precedence constraints.roads constraints.strips geom.containment
        model.airport model.end_area model.islands model.map_memo model.platform
        model.threshold_datum
    """),
    "runway_chord": _mods(_GENERATOR_CORE + """
        constraints.apron constraints.cluster_pad constraints.geometry
        constraints.pad_relief constraints.pad_warning constraints.pads
        constraints.platform constraints.precedence constraints.routes
        constraints.runway_chord constraints.runway_profile constraints.runway_yield
        constraints.shoulder_crossing constraints.stretches constraints.trend
        geom.base_slab geom.cluster_outline geom.containment geom.pad_evidence
        geom.slope_pad
        geom.triangulate geom.union_find model.airport model.islands model.map_memo
        model.platform
    """),
    "runway_mean_slope": _mods(_GENERATOR_CORE + """
        constraints.apron constraints.cluster_pad constraints.geometry
        constraints.pad_relief constraints.pad_warning constraints.pads
        constraints.platform constraints.precedence constraints.routes
        constraints.runway_chord constraints.runway_mean_slope
        constraints.runway_profile constraints.runway_yield
        constraints.shoulder_crossing constraints.stretches constraints.trend
        geom.base_slab geom.cluster_outline geom.containment geom.pad_evidence
        geom.slope_pad
        geom.triangulate geom.union_find model.airport model.islands model.map_memo
        model.platform
    """),
    "runway_profile": _mods(_GENERATOR_CORE + """
        constraints.geometry constraints.precedence constraints.runway_profile
        constraints.shoulder_crossing constraints.trend model.airport
    """),
    "seams": _mods(_GENERATOR_CORE + """
        constraints.seams model.airport
    """),
    "strips": _mods(_GENERATOR_CORE + """
        constraints.end_lip constraints.geometry constraints.precedence
        constraints.strips model.airport model.end_area model.threshold_datum
    """),
    "structures": _mods(_GENERATOR_CORE + """
        constraints.apron constraints.cluster_pad constraints.geometry
        constraints.pad_relief constraints.pad_warning constraints.pads
        constraints.platform constraints.precedence constraints.structures
        geom.base_slab geom.cluster_outline geom.containment geom.pad_evidence
        geom.slope_pad
        geom.triangulate geom.union_find model.airport model.islands model.map_memo
        model.platform
    """),
    "taxi": _mods(_GENERATOR_CORE + """
        constraints.apron constraints.cluster_pad constraints.geometry
        constraints.pad_relief constraints.pad_warning constraints.pads
        constraints.platform constraints.precedence constraints.routes
        constraints.stretches constraints.taxi geom.base_slab geom.cluster_outline
        geom.slope_pad
        geom.containment geom.pad_evidence geom.triangulate geom.union_find
        model.airport model.islands model.map_memo model.platform
    """),
    "transverse": _mods(_GENERATOR_CORE + """
        constraints.contiguity constraints.end_lip constraints.geometry
        constraints.precedence constraints.roads constraints.stretches
        constraints.strips constraints.transverse geom.containment model.airport
        model.end_area model.islands model.map_memo model.platform model.threshold_datum
    """),
    "water": _mods(_GENERATOR_CORE + """
        constraints.geometry constraints.precedence constraints.water model.airport
    """),
    "zones": _mods(_GENERATOR_CORE + """
        constraints.contiguity constraints.end_lip constraints.geometry
        constraints.precedence constraints.roads constraints.strips constraints.zones
        geom.containment model.airport model.end_area model.islands model.map_memo
        model.platform model.threshold_datum
    """),
}
CODE_MODULES["constraints.assembly"] = _mods("""
    airport classify model pipeline planar airport.anchor_rule airport.apt_dat
    airport.authored_landing airport.authored_seat airport.backup_state
    airport.basin_ring airport.basin_witness airport.borrow airport.bridge_family
    airport.bulk_geos airport.cluster_profile airport.contact airport.contents
    airport.deck_signature airport.dem airport.dem_witness airport.dsf
    airport.extension_cache airport.file_hash airport.footprint_carry
    airport.footprint_connector airport.footprint_seats airport.footprint_unit airport.one_building
    airport.frame_entry airport.jetways airport.line_object airport.obj8
    airport.obj8_clip airport.obj8_drape airport.obj8_grade airport.obj8_roof
    airport.obj8_split airport.pack airport.pack_partition airport.pack_work
    airport.pad_block_seat airport.partition_cache airport.partition_code
    airport.placement_atom airport.placement_body airport.placement_boxes
    airport.placement_carrier airport.placement_census airport.placement_cockpit
    airport.placement_contact airport.placement_cut airport.placement_deck
    airport.placement_family airport.placement_file airport.placement_geom
    airport.placement_leaves airport.placement_motion airport.placement_orphan
    airport.placement_plan airport.placement_read airport.placement_record
    airport.placement_seams airport.placement_seat_tilt airport.placement_targets
    airport.pool airport.rebake_plan airport.riders airport.road_ways airport.scatter
    airport.sheet_chain airport.skirt airport.slab_faces airport.slab_plates
    airport.topology_cache airport.wall_class classify.airside_edge classify.evidence
    classify.facade_mint classify.gap_apron classify.gap_mint classify.lot_roads
    classify.neck classify.open_default classify.pad_touch classify.retaining_wall
    classify.ribbon_mint classify.roles classify.rules classify.sources
    classify.taxi_letter constraints constraints.apron constraints.apron_shelf
    constraints.assembly constraints.ceiling constraints.channel constraints.cluster_pad
    constraints.contiguity constraints.eat constraints.end_lip constraints.flat_site
    constraints.foot_rows constraints.geometry constraints.groundside
    constraints.hard_plane constraints.junction_mesh constraints.no_step
    constraints.door_pad
    constraints.pad_frontage_gs constraints.pad_fronting constraints.pad_ramp
    constraints.pad_relief constraints.pad_warning constraints.pads
    constraints.pavement_cap constraints.platform constraints.precedence
    constraints.proximity constraints.ramp_runout constraints.road_ramp
    constraints.roads constraints.routes constraints.runway_chord
    constraints.runway_mean_slope constraints.runway_profile constraints.runway_yield
    constraints.seams constraints.shoulder_crossing constraints.stretches
    constraints.strips constraints.structures constraints.taxi constraints.taxi_trend
    constraints.taxi_trend_cap constraints.transverse constraints.trend
    constraints.water constraints.weld_floor constraints.zones geom geom.base_slab
    geom.cluster_outline geom.containment geom.core_clamp geom.feet_graph geom.feet_mst
    geom.slope_pad
    geom.pad_evidence geom.parts geom.proportions geom.ramp_grade geom.ramp_profile
    geom.rotated_rect geom.triangulate geom.union_find law law.airports_schema
    law.base_profile_schema law.basin_schema law.cockpit_schema law.cutout_schema
    law.design_schema law.eat_schema law.flat_site_schema law.inset_class law.model
    law.model_types law.rebake_schema law.reference_code law.role_cap_schema law.tables
    law.terrace_schema law.tunnel_object_schema law.units model.airport
    model.constraints model.end_area model.frame model.ground_fit model.hard_plane
    model.islands model.map_memo model.placement model.planar model.platform model.pulse
    model.rebake model.registries model.structures model.threshold_datum pipeline.shapes
    planar.shape_airside planar.shape_mouths planar.shape_parts planar.shapes
    planar.strip_keepout
    classify.reachability
""")
CODE_MODULES["jetway_strip"] = _mods("""
    airport constraints model airport.anchor_rule airport.apt_dat
    airport.authored_landing airport.authored_seat airport.backup_state
    airport.basin_ring airport.basin_witness airport.borrow airport.bridge_family
    airport.bulk_geos airport.cluster_profile airport.contact airport.contents
    airport.deck_signature airport.dem_witness airport.dsf airport.extension_cache
    airport.file_hash airport.footprint_carry airport.footprint_connector
    airport.footprint_seats airport.footprint_unit airport.one_building airport.frame_entry
    airport.line_object airport.obj8 airport.obj8_clip airport.obj8_drape
    airport.obj8_grade airport.obj8_roof airport.obj8_split airport.pack
    airport.pack_partition airport.pack_work airport.pad_block_seat
    airport.partition_cache airport.partition_code airport.placement_atom
    airport.placement_body airport.placement_boxes airport.placement_carrier
    airport.placement_census airport.placement_cockpit airport.placement_contact
    airport.placement_cut airport.placement_deck airport.placement_family
    airport.placement_file airport.placement_geom airport.placement_leaves
    airport.placement_motion airport.placement_orphan airport.placement_plan
    airport.placement_read airport.placement_record airport.placement_seams
    airport.placement_seat_tilt airport.placement_targets airport.pool
    airport.rebake_plan airport.riders airport.scatter airport.sheet_chain airport.skirt
    airport.slab_faces airport.slab_plates airport.topology_cache constraints.apron
    constraints.ceiling constraints.cluster_pad constraints.contiguity
    constraints.end_lip constraints.geometry constraints.groundside
    constraints.jetway_strip constraints.no_step constraints.pad_frontage_gs
    constraints.pad_relief constraints.pad_warning constraints.pads constraints.platform
    constraints.precedence constraints.roads constraints.routes
    constraints.runway_profile constraints.shoulder_crossing constraints.stretches
    constraints.strips constraints.transverse constraints.trend constraints.weld_floor
    geom geom.base_slab geom.cluster_outline geom.slope_pad geom.containment geom.pad_evidence
    geom.rotated_rect geom.triangulate geom.union_find law law.airports_schema
    law.base_profile_schema law.basin_schema law.cockpit_schema law.cutout_schema
    law.design_schema law.eat_schema law.flat_site_schema law.model law.model_types
    law.rebake_schema law.reference_code law.role_cap_schema law.tables
    law.terrace_schema law.tunnel_object_schema law.units model.airport
    model.constraints model.end_area model.frame model.islands model.jetway
    model.map_memo model.placement model.planar model.platform model.pulse model.rebake
    model.registries model.structures model.threshold_datum
""")

#: THE SOLVE AND THE LAST STAGE (spec §4b.4, §4b.5; #843 step 9b): the solve
#: is entered at ``solve.design`` / ``solve.api`` AND at the callback
#: modules the build binds into it (``solve`` may not import
#: ``constraints``): ``constraints.road_ramp`` (``reach_seed_rewrite``),
#: ``constraints.no_step`` (``hold_pass``), ``constraints.taxi_trend``
#: (``stage_one_retarget``), ``pipeline.stage_one_map`` (the ribbon-free
#: stage-one problem the solve reads) and ``pipeline.solve_record`` (its
#: codec and certificate).  The late cut and the late solve share one
#: closure: ``pipeline.late_stage`` reaches the whole of both halves.
CODE_MODULES["solve"] = _mods("""
    airport classify constraints model pipeline planar solve airport.anchor_rule
    airport.apt_dat airport.authored_landing airport.authored_seat airport.backup_state
    airport.basin_ring airport.basin_witness airport.below_zero airport.borrow
    airport.bridge_family airport.bulk_geos airport.cluster_profile airport.contact
    airport.contents airport.deck_signature airport.dem airport.dem_production
    airport.dem_record airport.dem_shared airport.dem_witness airport.door_wells
    airport.dsf airport.extension_cache airport.file_hash airport.file_witness
    airport.footprint_carry airport.footprint_connector airport.footprint_seats
    airport.footprint_unit
    airport.one_building airport.frame_entry airport.grade_ledger airport.jetways
    airport.line_object airport.obj8 airport.obj8_clip airport.obj8_drape
    airport.obj8_grade airport.obj8_roof airport.obj8_split airport.object_cut
    airport.pack airport.pack_partition airport.pack_work airport.pad_block_seat
    airport.partition_cache airport.partition_code airport.placement_atom
    airport.placement_body airport.placement_boxes airport.placement_carrier
    airport.placement_census airport.placement_cockpit airport.placement_contact
    airport.placement_cut airport.placement_deck airport.placement_family
    airport.placement_file airport.placement_geom airport.placement_leaves
    airport.placement_motion airport.placement_orphan airport.placement_plan
    airport.placement_read airport.placement_record airport.placement_seams
    airport.placement_seat_tilt airport.placement_targets airport.pool airport.ramp_feet
    airport.reader_work airport.rebake_plan airport.riders airport.road_profile
    airport.road_ways airport.scatter airport.sheet_chain airport.skirt
    airport.slab_faces airport.slab_plates airport.stage_cache airport.sunken_ramp
    airport.sunken_roads airport.thin_plates airport.topology_cache
    airport.tunnel_objects airport.tunnel_walls airport.wall_class
    airport.wall_corridor_probe airport.wall_corridors airport.wall_family
    airport.wall_geometry airport.wall_mouth classify.airside_edge classify.evidence
    classify.facade_mint classify.gap_apron classify.gap_mint classify.lot_roads
    classify.neck classify.open_default classify.pad_touch classify.ramp_runout
    classify.retaining_wall classify.ribbon_mint classify.roles classify.rules
    classify.sources classify.taxi_letter constraints.apron constraints.apron_shelf
    constraints.ceiling constraints.cluster_pad constraints.contiguity
    constraints.end_lip constraints.geometry constraints.groundside constraints.no_step
    constraints.door_pad
    constraints.pad_frontage_gs constraints.pad_relief constraints.pad_warning
    constraints.pads constraints.platform constraints.precedence constraints.road_ramp
    constraints.roads constraints.routes constraints.runway_chord
    constraints.runway_profile constraints.runway_yield constraints.shoulder_crossing
    constraints.stretches constraints.strips constraints.taxi constraints.taxi_trend
    constraints.taxi_trend_cap constraints.transverse constraints.trend
    constraints.weld_floor geom geom.base_slab geom.cluster_outline geom.slope_pad geom.containment
    geom.core_clamp geom.coverage geom.pad_evidence geom.parts geom.proportions
    geom.ramp_grade geom.ramp_profile geom.rotated_rect geom.triangulate geom.union_find
    geom.vector law law.airports_schema law.approach_corridor law.base_profile_schema
    law.basin_schema law.cockpit_schema law.cutout_schema law.design_schema
    law.eat_schema law.flat_site_schema law.inset_class law.model law.model_types
    law.rebake_schema law.reference_code law.role_cap_schema law.tables
    law.terrace_schema law.tunnel_object_schema law.units model.airport
    model.constraints model.end_area model.frame model.hard_plane model.islands
    model.jetway model.map_memo model.pad_terrace model.placement model.planar
    model.platform model.pulse model.rebake model.registries model.structures
    model.threshold_datum pipeline.back_cache pipeline.capture_state
    pipeline.solve_record pipeline.stage_one_map planar.apron_shelf planar.basin_datum
    planar.basin_geometry planar.basin_rim planar.basins planar.build planar.channel
    planar.channel_claims planar.channel_floor planar.channel_geometry
    planar.channel_witness planar.chords planar.covered_ground planar.door_ramps
    planar.edges planar.landing planar.landing_runout planar.object_corridor
    planar.overlay planar.pack_reads planar.pad_blocks planar.pad_cut planar.pad_sliver
    planar.pad_terrace planar.platform planar.ribbon_weld planar.ribbons
    planar.ridge_reach planar.road_yield planar.shape_airside planar.shape_mouths
    planar.shape_parts planar.shapes planar.shore planar.strip_keepout
    planar.structure_approach planar.structure_deck planar.structure_geometry
    planar.structure_overlap planar.structure_pair planar.structure_road
    planar.structure_mouth planar.structure_service planar.structure_stats
    planar.structure_underpass planar.structures planar.terrain_edge
    planar.unframed_ramp planar.wall_corridor_ramps planar.weld planar.zones solve.api
    solve.design solve.design_assemble solve.design_edge solve.design_ground
    solve.design_junction solve.design_qp solve.design_report solve.design_roles
    solve.design_stage solve.feasibility solve.flex solve.linear solve.pin_yield
    solve.project solve.project_strip solve.rows solve.wall_cut
    classify.reachability
    planar.zone_pass
""")
CODE_MODULES["late_cut"] = CODE_MODULES["late_solve"] = _mods("""
    airport classify emit model pipeline planar solve airport.anchor_rule
    airport.apt_dat airport.authored_landing airport.authored_seat airport.backup_state
    airport.basin_ring airport.basin_witness airport.below_zero airport.borrow
    airport.bridge_family airport.bulk_geos airport.cluster_profile airport.contact
    airport.contents airport.deck_signature airport.dem airport.dem_production
    airport.dem_record airport.dem_shared airport.dem_witness airport.door_wells
    airport.dsf airport.extension_cache airport.file_hash airport.file_witness
    airport.footprint_carry airport.footprint_connector airport.footprint_seats
    airport.footprint_unit
    airport.one_building airport.frame_entry airport.grade_ledger airport.jetways
    airport.line_object airport.obj8 airport.obj8_clip airport.obj8_drape
    airport.obj8_grade airport.obj8_roof airport.obj8_split airport.object_cut
    airport.pack airport.pack_partition airport.pack_work airport.pad_block_seat
    airport.partition_cache airport.partition_code airport.placement_atom
    airport.placement_body airport.placement_boxes airport.placement_carrier
    airport.placement_census airport.placement_cockpit airport.placement_contact
    airport.placement_cut airport.placement_deck airport.placement_family
    airport.placement_file airport.placement_geom airport.placement_leaves
    airport.placement_motion airport.placement_orphan airport.placement_plan
    airport.placement_read airport.placement_record airport.placement_seams
    airport.placement_seat_tilt airport.placement_targets airport.pool airport.ramp_feet
    airport.reader_work airport.rebake_plan airport.riders airport.road_profile
    airport.road_ways airport.scatter airport.sheet_chain airport.skirt
    airport.slab_faces airport.slab_plates airport.stage_cache airport.sunken_ramp
    airport.sunken_roads airport.thin_plates airport.topology_cache
    airport.tunnel_objects airport.tunnel_walls airport.wall_class
    airport.wall_corridor_probe airport.wall_corridors airport.wall_family
    airport.wall_geometry airport.wall_mouth classify.airside_edge classify.evidence
    classify.facade_mint classify.gap_apron classify.gap_mint classify.gap_terrace
    classify.lot_roads classify.neck classify.open_default classify.pad_road_exit
    classify.pad_touch classify.ramp_runout classify.retaining_wall classify.ribbon_mint
    classify.roles classify.rules classify.sources classify.taxi_letter constraints
    constraints.apron constraints.apron_shelf constraints.assembly constraints.ceiling
    constraints.channel constraints.cluster_pad constraints.contiguity constraints.eat
    constraints.end_lip constraints.flat_site constraints.foot_rows
    constraints.gap_follow constraints.geometry constraints.groundside
    constraints.hard_plane constraints.jetway_strip constraints.junction_mesh
    constraints.no_step constraints.pad_frontage_gs constraints.pad_fronting
    constraints.pad_ramp constraints.pad_relief constraints.pad_road_reach
    constraints.pad_warning constraints.pads constraints.pavement_cap
    constraints.platform constraints.precedence constraints.proximity
    constraints.ramp_runout constraints.road_ramp constraints.roads constraints.routes
    constraints.runway_chord constraints.runway_mean_slope constraints.runway_profile
    constraints.runway_yield constraints.seams constraints.shoulder_crossing
    constraints.slab_weld constraints.stretches constraints.strips
    constraints.structures constraints.taxi constraints.taxi_trend
    constraints.taxi_trend_cap constraints.transverse constraints.trend
    constraints.water constraints.weld_floor constraints.zones emit.graded emit.surface
    geom geom.base_slab geom.cluster_outline geom.containment geom.core_clamp
    geom.coverage geom.feet_graph geom.feet_mst geom.pad_evidence geom.parts
    geom.proportions geom.ramp_grade geom.ramp_profile geom.rotated_rect
    constraints.door_pad geom.slope_pad
    geom.triangulate geom.union_find geom.vector law law.airports_schema
    law.approach_corridor law.base_profile_schema law.basin_schema law.cockpit_schema
    law.cutout_schema law.design_schema law.eat_schema law.flat_site_schema
    law.inset_class law.model law.model_types law.rebake_schema law.reference_code
    law.role_cap_schema law.tables law.terrace_schema law.tunnel_object_schema law.units
    model.airport model.constraint_codec model.constraints model.end_area model.frame
    model.ground_fit model.hard_plane model.islands model.jetway model.map_memo
    model.pad_terrace model.placement model.planar model.platform model.pulse
    model.rebake model.registries model.structures model.threshold_datum
    pipeline.back_cache pipeline.capture_state pipeline.constraint_records
    pipeline.late_records pipeline.late_stage pipeline.shapes pipeline.solve_record
    pipeline.stage_code pipeline.stage_one_map planar.apron_shelf planar.basin_datum
    planar.basin_geometry planar.basin_rim planar.basins planar.build planar.channel
    planar.channel_claims planar.channel_floor planar.channel_geometry
    planar.channel_witness planar.chords planar.covered_ground planar.door_ramps
    planar.edges planar.landing planar.landing_runout planar.object_corridor
    planar.overlay planar.pack_reads planar.pad_blocks planar.pad_cut planar.pad_sliver
    planar.pad_terrace planar.platform planar.ribbon_weld planar.ribbons
    planar.ridge_reach planar.road_yield planar.shape_airside planar.shape_mouths
    planar.shape_parts planar.shapes planar.shore planar.strip_keepout
    planar.structure_approach planar.structure_deck planar.structure_geometry
    planar.structure_overlap planar.structure_pair planar.structure_road
    planar.structure_mouth planar.structure_service planar.structure_stats
    planar.structure_underpass planar.structures planar.terrain_edge
    planar.unframed_ramp planar.wall_corridor_ramps planar.weld planar.zones solve.api
    solve.design solve.design_assemble solve.design_edge solve.design_ground
    solve.design_junction solve.design_qp solve.design_report solve.design_roles
    solve.design_stage solve.feasibility solve.flex solve.linear solve.pin_yield
    solve.project solve.project_strip solve.rows solve.wall_cut
    classify.reachability
    planar.zone_pass
""")
CODE_MODULES["emit"] = _mods("""
    airport constraints emit model pipeline planar verify airport.anchor_rule
    airport.apt_dat airport.authored_landing airport.authored_seat airport.backup_state
    airport.basin_ring airport.basin_witness airport.borrow airport.bridge_family
    airport.bulk_geos airport.cluster_profile airport.contact airport.contents
    airport.deck_signature airport.dem airport.dem_witness airport.dsf
    airport.extension_cache airport.file_hash airport.footprint_carry
    airport.footprint_connector airport.footprint_seats airport.footprint_unit airport.one_building
    airport.frame_entry airport.jetways airport.line_object airport.obj8
    airport.obj8_clip airport.obj8_drape airport.obj8_grade airport.obj8_roof
    airport.obj8_split airport.pack airport.pack_partition airport.pack_work
    airport.pad_block_seat airport.partition_cache airport.partition_code
    airport.placement_atom airport.placement_body airport.placement_boxes
    airport.placement_carrier airport.placement_census airport.placement_cockpit
    airport.placement_contact airport.placement_cut airport.placement_deck
    airport.placement_family airport.placement_file airport.placement_geom
    airport.placement_leaves airport.placement_motion airport.placement_orphan
    airport.placement_plan airport.placement_read airport.placement_record
    airport.placement_seams airport.placement_seat_tilt airport.placement_targets
    airport.pool airport.rebake_plan airport.rebake_screen airport.riders
    airport.road_descent airport.road_profile airport.road_ramp airport.road_ways
    airport.scatter airport.sheet_chain airport.skirt airport.slab_faces
    airport.slab_plates airport.topology_cache airport.wall_class classify
    classify.airside_edge classify.evidence classify.facade_mint classify.gap_apron
    classify.gap_mint classify.lot_roads classify.neck classify.open_default
    classify.pad_touch classify.retaining_wall classify.ribbon_mint classify.roles
    classify.rules classify.sources classify.taxi_letter constraints.apron
    constraints.apron_shelf constraints.apron_trend constraints.ceiling
    constraints.channel constraints.cluster_pad constraints.contiguity constraints.eat
    constraints.end_lip constraints.flat_site constraints.geometry
    constraints.groundside constraints.junction_mesh constraints.no_step
    constraints.pad_frontage_gs constraints.pad_relief constraints.pad_warning
    constraints.pads constraints.platform constraints.precedence constraints.road_ramp
    constraints.roads constraints.routes constraints.runway_chord
    constraints.runway_mean_slope constraints.runway_profile constraints.runway_yield
    constraints.seams constraints.shoulder_crossing constraints.stretches
    constraints.strips constraints.surface_trend constraints.taxi constraints.taxi_trend
    constraints.taxi_trend_cap constraints.transverse constraints.trend
    constraints.weld_floor emit.graded emit.osm_adapter emit.rebake emit.road_join
    emit.surface emit.terrain_edge geom geom.base_slab geom.cluster_outline geom.slope_pad
    geom.containment geom.core_clamp geom.coverage geom.pad_evidence geom.parts
    geom.proportions geom.ramp_grade geom.rotated_rect geom.triangulate geom.union_find
    law law.airports_schema law.base_profile_schema law.basin_schema law.cockpit_schema
    law.cutout_schema law.design_schema law.eat_schema law.flat_site_schema
    law.inset_class law.model law.model_types law.rebake_schema law.reference_code
    law.role_cap_schema law.tables law.terrace_schema law.tunnel_object_schema law.units
    model.airport model.constraints model.end_area model.frame model.hard_plane
    model.islands model.jetway model.map_memo model.placement model.planar
    model.platform model.pulse model.rebake model.registries model.structures
    model.threshold_datum pipeline.authored_seats pipeline.emit_stage
    pipeline.publication pipeline.rebake_inputs pipeline.ribbon_steps
    pipeline.runway_report pipeline.seam_report pipeline.terrace_witness planar.cluster
    planar.shape_airside planar.shape_mouths planar.shape_parts planar.shapes
    planar.strip_keepout solve solve.api solve.design solve.design_assemble
    solve.design_edge solve.design_ground solve.design_junction solve.design_qp
    solve.design_report solve.design_roles solve.design_stage solve.feasibility
    solve.flex solve.ground_band solve.linear solve.pin_yield solve.project
    solve.project_strip solve.rows solve.wall_cut verify.roads
    classify.reachability
""")
CODE_MODULES["verify"] = _mods("""
    airport classify constraints emit model pipeline planar solve airport.anchor_rule
    airport.apt_dat airport.authored_landing airport.authored_seat airport.backup_state
    airport.basin_ring airport.basin_witness airport.borrow airport.bridge_family
    airport.bulk_geos airport.cluster_profile airport.contact airport.contents
    airport.deck_signature airport.dem airport.dem_witness airport.dsf
    airport.extension_cache airport.file_hash airport.footprint_carry
    airport.footprint_connector airport.footprint_seats airport.footprint_unit airport.one_building
    airport.frame_entry airport.jetways airport.line_object airport.obj8
    airport.obj8_clip airport.obj8_drape airport.obj8_grade airport.obj8_roof
    airport.obj8_split airport.pack airport.pack_partition airport.pack_work
    airport.pad_block_seat airport.partition_cache airport.partition_code
    airport.placement_atom airport.placement_body airport.placement_boxes
    airport.placement_carrier airport.placement_census airport.placement_cockpit
    airport.placement_contact airport.placement_cut airport.placement_deck
    airport.placement_family airport.placement_file airport.placement_geom
    airport.placement_leaves airport.placement_motion airport.placement_orphan
    airport.placement_plan airport.placement_read airport.placement_record
    airport.placement_seams airport.placement_seat_tilt airport.placement_targets
    airport.pool airport.rebake_plan airport.riders airport.road_ways airport.scatter
    airport.sheet_chain airport.skirt airport.slab_faces airport.slab_plates
    airport.topology_cache airport.wall_class classify.airside_edge classify.evidence
    classify.facade_mint classify.gap_apron classify.gap_mint classify.lot_roads
    classify.neck classify.open_default classify.pad_touch classify.retaining_wall
    classify.ribbon_mint classify.roles classify.rules classify.sources
    classify.taxi_letter constraints.apron constraints.ceiling constraints.channel
    constraints.cluster_pad constraints.contiguity constraints.eat constraints.end_lip
    constraints.geometry constraints.groundside constraints.junction_mesh
    constraints.no_step constraints.pad_frontage_gs constraints.pad_relief
    constraints.pad_warning constraints.pads constraints.platform constraints.precedence
    constraints.roads constraints.routes constraints.runway_chord
    constraints.runway_mean_slope constraints.runway_profile constraints.runway_yield
    constraints.seams constraints.shoulder_crossing constraints.stretches
    constraints.strips constraints.taxi constraints.taxi_trend
    constraints.taxi_trend_cap constraints.transverse constraints.trend
    constraints.weld_floor emit.surface geom geom.base_slab geom.cluster_outline geom.slope_pad
    geom.containment geom.core_clamp geom.pad_evidence geom.parts geom.proportions
    geom.rotated_rect geom.triangulate geom.union_find law law.airports_schema
    law.base_profile_schema law.basin_schema law.cockpit_schema law.cutout_schema
    law.design_schema law.eat_schema law.flat_site_schema law.inset_class law.model
    law.model_types law.rebake_schema law.reference_code law.role_cap_schema law.tables
    law.terrace_schema law.tunnel_object_schema law.units model.airport
    model.constraints model.end_area model.frame model.islands model.map_memo
    model.placement model.planar model.platform model.pulse model.rebake
    model.registries model.structures model.threshold_datum pipeline.publication
    pipeline.ribbon_steps pipeline.verify_stage planar.cluster planar.shape_airside
    planar.shape_mouths planar.shape_parts planar.shapes planar.strip_keepout
    solve.design_roles solve.ground_band verify verify.census verify.channel
    verify.chord_work verify.contiguity verify.cutback verify.eat verify.frame
    verify.frontage verify.jetway verify.keepout verify.no_step verify.pads verify.pins
    verify.runway verify.runway_mean_slope verify.runway_witness verify.steps
    verify.strips verify.structures verify.transverse verify.within
    classify.reachability
""")


def generator_stage(name: str) -> str:
    """The stage-code entry of the constraint generator ``name``."""
    return f"constraints.{name}"


for _name, _module in GENERATOR_MODULES.items():
    ENTRY_MODULES[generator_stage(_name)] = (f"auto_patch_v2.constraints.{_module}",)
    CODE_MODULES[generator_stage(_name)] = _GENERATOR_CLOSURES[_module]
ENTRY_MODULES["constraints.assembly"] = ("auto_patch_v2.constraints.assembly",
                                         "auto_patch_v2.pipeline.shapes")
ENTRY_MODULES["jetway_strip"] = ("auto_patch_v2.airport.riders",
                                 "auto_patch_v2.constraints.jetway_strip")
ENTRY_MODULES["solve"] = ("auto_patch_v2.solve.design", "auto_patch_v2.solve.api",
                          "auto_patch_v2.constraints.road_ramp",
                          "auto_patch_v2.constraints.no_step",
                          "auto_patch_v2.constraints.taxi_trend",
                          "auto_patch_v2.pipeline.stage_one_map",
                          "auto_patch_v2.pipeline.solve_record")
ENTRY_MODULES["late_cut"] = ("auto_patch_v2.pipeline.late_stage",
                             "auto_patch_v2.pipeline.late_records",
                             "auto_patch_v2.classify.gap_terrace",
                             "auto_patch_v2.classify.gap_mint")
ENTRY_MODULES["late_solve"] = ("auto_patch_v2.pipeline.late_stage",
                               "auto_patch_v2.pipeline.late_records",
                               "auto_patch_v2.constraints.gap_follow",
                               "auto_patch_v2.solve.design",
                               "auto_patch_v2.constraints.road_ramp",
                               "auto_patch_v2.constraints.no_step",
                               "auto_patch_v2.constraints.taxi_trend")
# THE EMIT AND THE VERIFY (spec §4b.6, §4b.7; #843 step 9c): entered at
# ``pipeline/emit_stage`` (``render`` / ``install``, the post-solve glue
# with them) and ``pipeline/verify_stage`` (``judge`` / ``install``)
ENTRY_MODULES["emit"] = ("auto_patch_v2.pipeline.emit_stage",)
ENTRY_MODULES["verify"] = ("auto_patch_v2.pipeline.verify_stage",)

#: The cached stages, in build order.
STAGES: tuple[str, ...] = tuple(ENTRY_MODULES)
