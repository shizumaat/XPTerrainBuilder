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
                 "auto_patch_v2.constraints.taxi_route_yield",
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
        "auto_patch_v2.airport.access_road",
        "auto_patch_v2.airport.adapted_riders",
        "auto_patch_v2.airport.agp_deck_ends",
        "auto_patch_v2.airport.agp_deck_join",
        "auto_patch_v2.airport.agp_floors",
        "auto_patch_v2.airport.agp_foot_pads",
        "auto_patch_v2.airport.agp_gap_plates",
        "auto_patch_v2.airport.agp_ground",
        "auto_patch_v2.airport.agp_group",
        "auto_patch_v2.airport.agp_pieces",
        "auto_patch_v2.airport.agp_plan",
        "auto_patch_v2.airport.agp_plates",
        "auto_patch_v2.airport.airside_deck_seat",
        "auto_patch_v2.airport.airside_floor",
        "auto_patch_v2.airport.airside_group_seat",
        "auto_patch_v2.airport.anchor_rule",
        "auto_patch_v2.airport.apt_dat",
        "auto_patch_v2.airport.apt_edit",
        "auto_patch_v2.airport.apt_flatten",
        "auto_patch_v2.airport.authored_landing",
        "auto_patch_v2.airport.authored_seat",
        "auto_patch_v2.airport.backup_state",
        "auto_patch_v2.airport.basin_ring",
        "auto_patch_v2.airport.basin_witness",
        "auto_patch_v2.airport.below_grade_witness",
        "auto_patch_v2.airport.borrow",
        "auto_patch_v2.airport.bridge_approach",
        "auto_patch_v2.airport.bridge_axis",
        "auto_patch_v2.airport.bridge_end_state",
        "auto_patch_v2.airport.bridge_family",
        "auto_patch_v2.airport.bridge_frame",
        "auto_patch_v2.airport.bridge_stack",
        "auto_patch_v2.airport.bridge_witness",
        "auto_patch_v2.airport.bridged_ground",
        "auto_patch_v2.airport.bulk_geos",
        "auto_patch_v2.airport.cluster_profile",
        "auto_patch_v2.airport.connector_warp",
        "auto_patch_v2.airport.contact",
        "auto_patch_v2.airport.contents",
        "auto_patch_v2.airport.cut_deck_seat",
        "auto_patch_v2.airport.cut_portal_seat",
        "auto_patch_v2.airport.deck_carry",
        "auto_patch_v2.airport.deck_end_read",
        "auto_patch_v2.airport.deck_ends",
        "auto_patch_v2.airport.deck_family_contact",
        "auto_patch_v2.airport.deck_plane_ring",
        "auto_patch_v2.airport.deck_plates",
        "auto_patch_v2.airport.deck_profile",
        "auto_patch_v2.airport.deck_riders",
        "auto_patch_v2.airport.deck_signature",
        "auto_patch_v2.airport.deck_stack",
        "auto_patch_v2.airport.deck_surface",
        "auto_patch_v2.airport.deck_touch",
        "auto_patch_v2.airport.deck_track_bend",
        "auto_patch_v2.airport.dem",
        "auto_patch_v2.airport.dem_witness",
        "auto_patch_v2.airport.drawn_anchor",
        "auto_patch_v2.airport.dsf",
        "auto_patch_v2.airport.dsf_heights",
        "auto_patch_v2.airport.entrance_seat",
        "auto_patch_v2.airport.exclusion",
        "auto_patch_v2.airport.extension_cache",
        "auto_patch_v2.airport.facade",
        "auto_patch_v2.airport.facade_seat",
        "auto_patch_v2.airport.file_hash",
        "auto_patch_v2.airport.floor_deck_ends",
        "auto_patch_v2.airport.floor_rim",
        "auto_patch_v2.airport.footprint_carry",
        "auto_patch_v2.airport.footprint_connector",
        "auto_patch_v2.airport.footprint_seats",
        "auto_patch_v2.airport.footprint_unit",
        "auto_patch_v2.airport.level_base",
        "auto_patch_v2.airport.frame_entry",
        "auto_patch_v2.airport.free_bridge_seat",
        "auto_patch_v2.airport.free_column",
        "auto_patch_v2.airport.ground_route_ways",
        "auto_patch_v2.airport.ground_shell",
        "auto_patch_v2.airport.hanging_objects",
        "auto_patch_v2.airport.hung_wall_seat",
        "auto_patch_v2.airport.interior_deck",
        "auto_patch_v2.airport.isolated_seat",
        "auto_patch_v2.airport.jetways",
        "auto_patch_v2.airport.line_object",
        "auto_patch_v2.airport.line_solidity",
        "auto_patch_v2.airport.msl_feet",
        "auto_patch_v2.airport.obj8",
        "auto_patch_v2.airport.obj8_band",
        "auto_patch_v2.airport.obj8_clip",
        "auto_patch_v2.airport.obj8_drape",
        "auto_patch_v2.airport.obj8_grade",
        "auto_patch_v2.airport.obj8_memo",
        "auto_patch_v2.airport.obj8_rest",
        "auto_patch_v2.airport.obj8_roof",
        "auto_patch_v2.airport.obj8_split",
        "auto_patch_v2.airport.obj8_warp",
        "auto_patch_v2.airport.object_cut",
        "auto_patch_v2.airport.object_floor",
        "auto_patch_v2.airport.object_pack",
        "auto_patch_v2.airport.one_building",
        "auto_patch_v2.airport.open_frame_seat",
        "auto_patch_v2.airport.pack",
        "auto_patch_v2.airport.pack_art",
        "auto_patch_v2.airport.pack_choice",
        "auto_patch_v2.airport.pack_ground",
        "auto_patch_v2.airport.pack_health",
        "auto_patch_v2.airport.pack_health.light_records",
        "auto_patch_v2.airport.pack_local",
        "auto_patch_v2.airport.pack_partition",
        "auto_patch_v2.airport.pack_patch_witness",
        "auto_patch_v2.airport.pack_terrain",
        "auto_patch_v2.airport.pack_work",
        "auto_patch_v2.airport.pad_block_seat",
        "auto_patch_v2.airport.pad_level_group",
        "auto_patch_v2.airport.partition_cache",
        "auto_patch_v2.airport.partition_code",
        "auto_patch_v2.airport.pavement_end_plate",
        "auto_patch_v2.airport.pit_frame",
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
        "auto_patch_v2.airport.pool_memory",
        "auto_patch_v2.airport.pool_slots",
        "auto_patch_v2.airport.rebake_plan",
        "auto_patch_v2.airport.relief_skin",
        "auto_patch_v2.airport.file_verdict",
        "auto_patch_v2.airport.rider_floor",
        "auto_patch_v2.airport.riders",
        "auto_patch_v2.airport.ring_contact_batch",
        "auto_patch_v2.airport.road_ways",
        "auto_patch_v2.airport.runway_strip",
        "auto_patch_v2.airport.scatter",
        "auto_patch_v2.airport.sheet_chain",
        "auto_patch_v2.airport.shell_ground",
        "auto_patch_v2.airport.skirt",
        "auto_patch_v2.airport.slab_faces",
        "auto_patch_v2.airport.slab_plates",
        "auto_patch_v2.airport.split_bar",
        "auto_patch_v2.airport.split_guard",
        "auto_patch_v2.airport.split_level",
        "auto_patch_v2.airport.split_level_wings",
        "auto_patch_v2.airport.stack_end_seat",
        "auto_patch_v2.airport.stack_walls",
        "auto_patch_v2.airport.stacked_deck",
        "auto_patch_v2.airport.sunk_frame",
        "auto_patch_v2.airport.sunken_ramp",
        "auto_patch_v2.airport.terrain_base",
        "auto_patch_v2.airport.terrain_feature",
        "auto_patch_v2.airport.terrain_model",
        "auto_patch_v2.airport.terrain_shaped",
        "auto_patch_v2.airport.terrain_shell",
        "auto_patch_v2.airport.tilt_float",
        "auto_patch_v2.airport.topology_cache",
        "auto_patch_v2.airport.touch_graph",
        "auto_patch_v2.airport.touch_seat",
        "auto_patch_v2.airport.unit_storey",
        "auto_patch_v2.airport.user_roles",
        "auto_patch_v2.airport.wall_class",
        "auto_patch_v2.airport.wall_geometry",
        "auto_patch_v2.airport.wall_sheets",
        "auto_patch_v2.airport.wall_sides",
        "auto_patch_v2.airport.wall_top",
        "auto_patch_v2.airport.walled_pit",
        "auto_patch_v2.airport.walled_plate",
        "auto_patch_v2.airport.zero_level_seat",
        "auto_patch_v2.classify",
        "auto_patch_v2.classify.airside_edge",
        "auto_patch_v2.classify.apron_gate",
        "auto_patch_v2.classify.apt_shoulder",
        "auto_patch_v2.classify.blast_pad",
        "auto_patch_v2.classify.car_lot",
        "auto_patch_v2.classify.edge_line_mint",
        "auto_patch_v2.classify.end_pad",
        "auto_patch_v2.classify.evidence",
        "auto_patch_v2.classify.facade_mint",
        "auto_patch_v2.classify.fence_division",
        "auto_patch_v2.classify.fence_yard",
        "auto_patch_v2.classify.floor_yard",
        "auto_patch_v2.classify.frontage_road",
        "auto_patch_v2.classify.gap_apron",
        "auto_patch_v2.classify.gap_band",
        "auto_patch_v2.classify.gap_mint",
        "auto_patch_v2.classify.gap_stands",
        "auto_patch_v2.classify.island_spurs",
        "auto_patch_v2.classify.lot_roads",
        "auto_patch_v2.classify.neck",
        "auto_patch_v2.classify.open_default",
        "auto_patch_v2.classify.pad_cut_corridor",
        "auto_patch_v2.classify.neck_road",
        "auto_patch_v2.classify.pad_sunk",
        "auto_patch_v2.classify.pad_touch",
        "auto_patch_v2.classify.reachability",
        "auto_patch_v2.classify.retaining_wall",
        "auto_patch_v2.classify.ribbon_mint",
        "auto_patch_v2.classify.roles",
        "auto_patch_v2.classify.rules",
        "auto_patch_v2.classify.sources",
        "auto_patch_v2.classify.storey_edge",
        "auto_patch_v2.classify.taxi_letter",
        "auto_patch_v2.classify.taxi_shoulder",
        "auto_patch_v2.classify.wall_clip",
        "auto_patch_v2.classify.wall_cutback",
        "auto_patch_v2.classify.wrap_page",
        "auto_patch_v2.geom",
        "auto_patch_v2.geom.agp_plate",
        "auto_patch_v2.geom.author_ground",
        "auto_patch_v2.geom.base_slab",
        "auto_patch_v2.geom.capped_plane",
        "auto_patch_v2.geom.centreline",
        "auto_patch_v2.geom.cluster_outline",
        "auto_patch_v2.geom.deck_ground",
        "auto_patch_v2.geom.diameter",
        "auto_patch_v2.geom.end_line",
        "auto_patch_v2.geom.fixed_overlay",
        "auto_patch_v2.geom.foot_planes",
        "auto_patch_v2.geom.lens",
        "auto_patch_v2.geom.line_walk",
        "auto_patch_v2.geom.lowest_face",
        "auto_patch_v2.geom.many_buffers",
        "auto_patch_v2.geom.pad_evidence",
        "auto_patch_v2.geom.parts",
        "auto_patch_v2.geom.plane_groups",
        "auto_patch_v2.geom.plate_bands",
        "auto_patch_v2.geom.plate_heights",
        "auto_patch_v2.geom.proportions",
        "auto_patch_v2.geom.ramp_profile",
        "auto_patch_v2.geom.rotated_rect",
        "auto_patch_v2.geom.shape_class",
        "auto_patch_v2.geom.slope_pad",
        "auto_patch_v2.geom.terrain_deck",
        "auto_patch_v2.geom.triangulate",
        "auto_patch_v2.geom.union_find",
        "auto_patch_v2.geom.valid_area",
        "auto_patch_v2.geom.vector",
        "auto_patch_v2.law",
        "auto_patch_v2.law.agp_schema",
        "auto_patch_v2.law.airports_schema",
        "auto_patch_v2.law.base_profile_schema",
        "auto_patch_v2.law.basin_schema",
        "auto_patch_v2.law.cockpit_schema",
        "auto_patch_v2.law.cutout_schema",
        "auto_patch_v2.law.deck_gen_schema",
        "auto_patch_v2.law.design_schema",
        "auto_patch_v2.law.eat_schema",
        "auto_patch_v2.law.flat_pack_schema",
        "auto_patch_v2.law.flat_site_schema",
        "auto_patch_v2.law.inset_class",
        "auto_patch_v2.law.model",
        "auto_patch_v2.law.model_types",
        "auto_patch_v2.law.rebake_schema",
        "auto_patch_v2.law.reference_code",
        "auto_patch_v2.law.role_cap_schema",
        "auto_patch_v2.law.runway_ends_schema",
        "auto_patch_v2.law.tables",
        "auto_patch_v2.law.terrace_schema",
        "auto_patch_v2.law.terrain_witness_schema",
        "auto_patch_v2.law.tunnel_object_schema",
        "auto_patch_v2.law.units",
        "auto_patch_v2.law.walled_plate_schema",
        "auto_patch_v2.model",
        "auto_patch_v2.model.agp_group",
        "auto_patch_v2.model.agp_plate",
        "auto_patch_v2.model.airport",
        "auto_patch_v2.model.clocks",
        "auto_patch_v2.model.deck_ends",
        "auto_patch_v2.model.deck_stack",
        "auto_patch_v2.model.end_area",
        "auto_patch_v2.model.floor_ground",
        "auto_patch_v2.model.frame",
        "auto_patch_v2.model.free_bridge",
        "auto_patch_v2.model.placement",
        "auto_patch_v2.model.planar",
        "auto_patch_v2.model.pulse",
        "auto_patch_v2.model.rebake",
        "auto_patch_v2.model.registries",
        "auto_patch_v2.model.road_clearance",
        "auto_patch_v2.model.structures",
        "auto_patch_v2.model.wall_reach",
        "auto_patch_v2.model.walled_plate",
    ),
    "planar": (
        "auto_patch_v2",
        "auto_patch_v2.airport",
        "auto_patch_v2.airport.access_road",
        "auto_patch_v2.airport.adapted_riders",
        "auto_patch_v2.airport.agp_deck_ends",
        "auto_patch_v2.airport.agp_deck_join",
        "auto_patch_v2.airport.agp_floors",
        "auto_patch_v2.airport.agp_foot_pads",
        "auto_patch_v2.airport.agp_gap_plates",
        "auto_patch_v2.airport.agp_ground",
        "auto_patch_v2.airport.agp_group",
        "auto_patch_v2.airport.agp_pieces",
        "auto_patch_v2.airport.agp_plan",
        "auto_patch_v2.airport.agp_plates",
        "auto_patch_v2.airport.airside_deck_seat",
        "auto_patch_v2.airport.airside_floor",
        "auto_patch_v2.airport.airside_group_seat",
        "auto_patch_v2.airport.anchor_rule",
        "auto_patch_v2.airport.apt_dat",
        "auto_patch_v2.airport.apt_edit",
        "auto_patch_v2.airport.apt_flatten",
        "auto_patch_v2.airport.authored_landing",
        "auto_patch_v2.airport.authored_seat",
        "auto_patch_v2.airport.backup_state",
        "auto_patch_v2.airport.basin_ring",
        "auto_patch_v2.airport.basin_witness",
        "auto_patch_v2.airport.below_grade_witness",
        "auto_patch_v2.airport.below_zero",
        "auto_patch_v2.airport.bore_ground",
        "auto_patch_v2.airport.borrow",
        "auto_patch_v2.airport.bridge_approach",
        "auto_patch_v2.airport.bridge_axis",
        "auto_patch_v2.airport.bridge_class",
        "auto_patch_v2.airport.bridge_end_state",
        "auto_patch_v2.airport.bridge_family",
        "auto_patch_v2.airport.bridge_frame",
        "auto_patch_v2.airport.bridge_ground",
        "auto_patch_v2.airport.bridge_stack",
        "auto_patch_v2.airport.bridge_witness",
        "auto_patch_v2.airport.bridged_ground",
        "auto_patch_v2.airport.bulk_geos",
        "auto_patch_v2.airport.cluster_profile",
        "auto_patch_v2.airport.connector_warp",
        "auto_patch_v2.airport.contact",
        "auto_patch_v2.airport.contents",
        "auto_patch_v2.airport.cut_deck_seat",
        "auto_patch_v2.airport.cut_portal",
        "auto_patch_v2.airport.cut_portal_seat",
        "auto_patch_v2.airport.deck_carry",
        "auto_patch_v2.airport.deck_end_read",
        "auto_patch_v2.airport.deck_ends",
        "auto_patch_v2.airport.deck_family_contact",
        "auto_patch_v2.airport.deck_plane_ring",
        "auto_patch_v2.airport.deck_plates",
        "auto_patch_v2.airport.deck_profile",
        "auto_patch_v2.airport.deck_riders",
        "auto_patch_v2.airport.deck_roof",
        "auto_patch_v2.airport.deck_signature",
        "auto_patch_v2.airport.deck_stack",
        "auto_patch_v2.airport.deck_surface",
        "auto_patch_v2.airport.deck_touch",
        "auto_patch_v2.airport.deck_track_bend",
        "auto_patch_v2.airport.dem",
        "auto_patch_v2.airport.dem_production",
        "auto_patch_v2.airport.dem_shared",
        "auto_patch_v2.airport.dem_witness",
        "auto_patch_v2.airport.door_wells",
        "auto_patch_v2.airport.drawn_anchor",
        "auto_patch_v2.airport.dsf",
        "auto_patch_v2.airport.dsf_heights",
        "auto_patch_v2.airport.entrance_front",
        "auto_patch_v2.airport.entrance_seat",
        "auto_patch_v2.airport.exclusion",
        "auto_patch_v2.airport.extension_cache",
        "auto_patch_v2.airport.facade",
        "auto_patch_v2.airport.facade_seat",
        "auto_patch_v2.airport.file_hash",
        "auto_patch_v2.airport.floor_deck_ends",
        "auto_patch_v2.airport.floor_rim",
        "auto_patch_v2.airport.foot_lot",
        "auto_patch_v2.airport.footed_portal",
        "auto_patch_v2.airport.footprint_carry",
        "auto_patch_v2.airport.footprint_connector",
        "auto_patch_v2.airport.footprint_seats",
        "auto_patch_v2.airport.footprint_unit",
        "auto_patch_v2.airport.level_base",
        "auto_patch_v2.airport.frame_entry",
        "auto_patch_v2.airport.free_bridge_seat",
        "auto_patch_v2.airport.free_column",
        "auto_patch_v2.airport.grade_ledger",
        "auto_patch_v2.airport.ground_route_ways",
        "auto_patch_v2.airport.ground_shell",
        "auto_patch_v2.airport.hanging_objects",
        "auto_patch_v2.airport.hung_wall_seat",
        "auto_patch_v2.airport.interior_deck",
        "auto_patch_v2.airport.isolated_seat",
        "auto_patch_v2.airport.jetways",
        "auto_patch_v2.airport.line_object",
        "auto_patch_v2.airport.line_solidity",
        "auto_patch_v2.airport.mouth_group",
        "auto_patch_v2.airport.msl_feet",
        "auto_patch_v2.airport.obj8",
        "auto_patch_v2.airport.obj8_band",
        "auto_patch_v2.airport.obj8_clip",
        "auto_patch_v2.airport.obj8_drape",
        "auto_patch_v2.airport.obj8_grade",
        "auto_patch_v2.airport.obj8_memo",
        "auto_patch_v2.airport.obj8_rest",
        "auto_patch_v2.airport.obj8_roof",
        "auto_patch_v2.airport.obj8_split",
        "auto_patch_v2.airport.obj8_warp",
        "auto_patch_v2.airport.object_cut",
        "auto_patch_v2.airport.object_floor",
        "auto_patch_v2.airport.object_ground",
        "auto_patch_v2.airport.object_pack",
        "auto_patch_v2.airport.old_dem_fill",
        "auto_patch_v2.airport.one_building",
        "auto_patch_v2.airport.open_frame_seat",
        "auto_patch_v2.airport.pack",
        "auto_patch_v2.airport.pack_art",
        "auto_patch_v2.airport.pack_choice",
        "auto_patch_v2.airport.pack_ground",
        "auto_patch_v2.airport.pack_health",
        "auto_patch_v2.airport.pack_health.light_records",
        "auto_patch_v2.airport.pack_local",
        "auto_patch_v2.airport.pack_partition",
        "auto_patch_v2.airport.pack_patch_witness",
        "auto_patch_v2.airport.pack_terrain",
        "auto_patch_v2.airport.pack_work",
        "auto_patch_v2.airport.pad_block_seat",
        "auto_patch_v2.airport.pad_level_group",
        "auto_patch_v2.airport.partition_cache",
        "auto_patch_v2.airport.partition_code",
        "auto_patch_v2.airport.pavement_end_plate",
        "auto_patch_v2.airport.pit_frame",
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
        "auto_patch_v2.airport.plate_frame",
        "auto_patch_v2.airport.plate_ground",
        "auto_patch_v2.airport.pool",
        "auto_patch_v2.airport.pool_memory",
        "auto_patch_v2.airport.pool_slots",
        "auto_patch_v2.airport.portal_floor",
        "auto_patch_v2.airport.portal_objects",
        "auto_patch_v2.airport.ramp_feet",
        "auto_patch_v2.airport.ramp_wing",
        "auto_patch_v2.airport.reader_work",
        "auto_patch_v2.airport.rebake_plan",
        "auto_patch_v2.airport.relief_skin",
        "auto_patch_v2.airport.file_verdict",
        "auto_patch_v2.airport.rider_floor",
        "auto_patch_v2.airport.riders",
        "auto_patch_v2.airport.ring_contact_batch",
        "auto_patch_v2.airport.road_bridge_ground",
        "auto_patch_v2.airport.road_descent",
        "auto_patch_v2.airport.road_profile",
        "auto_patch_v2.airport.road_stations",
        "auto_patch_v2.airport.road_ways",
        "auto_patch_v2.airport.runway_strip",
        "auto_patch_v2.airport.scatter",
        "auto_patch_v2.airport.sheet_chain",
        "auto_patch_v2.airport.shell_ground",
        "auto_patch_v2.airport.skirt",
        "auto_patch_v2.airport.slab_faces",
        "auto_patch_v2.airport.slab_plates",
        "auto_patch_v2.airport.split_bar",
        "auto_patch_v2.airport.split_guard",
        "auto_patch_v2.airport.split_level",
        "auto_patch_v2.airport.split_level_forecourt",
        "auto_patch_v2.airport.split_level_wings",
        "auto_patch_v2.airport.stack_end_seat",
        "auto_patch_v2.airport.stack_walls",
        "auto_patch_v2.airport.stacked_deck",
        "auto_patch_v2.airport.sunk_frame",
        "auto_patch_v2.airport.sunken_ramp",
        "auto_patch_v2.airport.sunken_roads",
        "auto_patch_v2.airport.terrain_base",
        "auto_patch_v2.airport.terrain_cut",
        "auto_patch_v2.airport.terrain_feature",
        "auto_patch_v2.airport.terrain_model",
        "auto_patch_v2.airport.terrain_shaped",
        "auto_patch_v2.airport.terrain_shell",
        "auto_patch_v2.airport.thin_plates",
        "auto_patch_v2.airport.tilt_float",
        "auto_patch_v2.airport.topology_cache",
        "auto_patch_v2.airport.touch_graph",
        "auto_patch_v2.airport.touch_seat",
        "auto_patch_v2.airport.trench_objects",
        "auto_patch_v2.airport.tunnel_objects",
        "auto_patch_v2.airport.tunnel_walls",
        "auto_patch_v2.airport.unit_storey",
        "auto_patch_v2.airport.user_roles",
        "auto_patch_v2.airport.visible_cut",
        "auto_patch_v2.airport.wall_class",
        "auto_patch_v2.airport.wall_corridor_probe",
        "auto_patch_v2.airport.wall_corridors",
        "auto_patch_v2.airport.wall_family",
        "auto_patch_v2.airport.wall_geometry",
        "auto_patch_v2.airport.wall_lines",
        "auto_patch_v2.airport.wall_mouth",
        "auto_patch_v2.airport.wall_sheets",
        "auto_patch_v2.airport.wall_sides",
        "auto_patch_v2.airport.wall_top",
        "auto_patch_v2.airport.walled_pit",
        "auto_patch_v2.airport.walled_plate",
        "auto_patch_v2.airport.walled_trench",
        "auto_patch_v2.airport.zero_level_seat",
        "auto_patch_v2.classify",
        "auto_patch_v2.classify.airside_edge",
        "auto_patch_v2.classify.apron_gate",
        "auto_patch_v2.classify.apt_shoulder",
        "auto_patch_v2.classify.blast_pad",
        "auto_patch_v2.classify.car_lot",
        "auto_patch_v2.classify.edge_line_mint",
        "auto_patch_v2.classify.end_pad",
        "auto_patch_v2.classify.evidence",
        "auto_patch_v2.classify.facade_mint",
        "auto_patch_v2.classify.fence_division",
        "auto_patch_v2.classify.fence_yard",
        "auto_patch_v2.classify.floor_yard",
        "auto_patch_v2.classify.frontage_road",
        "auto_patch_v2.classify.gap_apron",
        "auto_patch_v2.classify.gap_band",
        "auto_patch_v2.classify.gap_mint",
        "auto_patch_v2.classify.gap_stands",
        "auto_patch_v2.classify.island_spurs",
        "auto_patch_v2.classify.lot_roads",
        "auto_patch_v2.classify.neck",
        "auto_patch_v2.classify.open_default",
        "auto_patch_v2.classify.pad_cut_corridor",
        "auto_patch_v2.classify.neck_road",
        "auto_patch_v2.classify.pad_sunk",
        "auto_patch_v2.classify.pad_touch",
        "auto_patch_v2.classify.ramp_runout",
        "auto_patch_v2.classify.reachability",
        "auto_patch_v2.classify.retaining_wall",
        "auto_patch_v2.classify.ribbon_mint",
        "auto_patch_v2.classify.roles",
        "auto_patch_v2.classify.rules",
        "auto_patch_v2.classify.sources",
        "auto_patch_v2.classify.storey_edge",
        "auto_patch_v2.classify.taxi_letter",
        "auto_patch_v2.classify.taxi_shoulder",
        "auto_patch_v2.classify.wall_clip",
        "auto_patch_v2.classify.wall_cutback",
        "auto_patch_v2.classify.wrap_page",
        "auto_patch_v2.geom",
        "auto_patch_v2.geom.agp_plate",
        "auto_patch_v2.geom.author_ground",
        "auto_patch_v2.geom.base_slab",
        "auto_patch_v2.geom.capped_plane",
        "auto_patch_v2.geom.centreline",
        "auto_patch_v2.geom.cluster_outline",
        "auto_patch_v2.geom.collapsed_spike",
        "auto_patch_v2.geom.containment",
        "auto_patch_v2.geom.core_clamp",
        "auto_patch_v2.geom.coverage",
        "auto_patch_v2.geom.deck_ground",
        "auto_patch_v2.geom.deck_spans",
        "auto_patch_v2.geom.diameter",
        "auto_patch_v2.geom.end_line",
        "auto_patch_v2.geom.exact",
        "auto_patch_v2.geom.fixed_overlay",
        "auto_patch_v2.geom.foot_planes",
        "auto_patch_v2.geom.lens",
        "auto_patch_v2.geom.line_walk",
        "auto_patch_v2.geom.lowest_face",
        "auto_patch_v2.geom.many_buffers",
        "auto_patch_v2.geom.pad_evidence",
        "auto_patch_v2.geom.parts",
        "auto_patch_v2.geom.plane_groups",
        "auto_patch_v2.geom.plate_bands",
        "auto_patch_v2.geom.plate_cells",
        "auto_patch_v2.geom.plate_heights",
        "auto_patch_v2.geom.proportions",
        "auto_patch_v2.geom.ramp_grade",
        "auto_patch_v2.geom.ramp_profile",
        "auto_patch_v2.geom.rotated_rect",
        "auto_patch_v2.geom.route_over_pad",
        "auto_patch_v2.geom.shape_class",
        "auto_patch_v2.geom.slope_pad",
        "auto_patch_v2.geom.station_runs",
        "auto_patch_v2.geom.terrain_deck",
        "auto_patch_v2.geom.trend",
        "auto_patch_v2.geom.triangulate",
        "auto_patch_v2.geom.union_find",
        "auto_patch_v2.geom.valid_area",
        "auto_patch_v2.geom.vector",
        "auto_patch_v2.geom.wall_lines",
        "auto_patch_v2.geom.water_level",
        "auto_patch_v2.law",
        "auto_patch_v2.law.agp_schema",
        "auto_patch_v2.law.airports_schema",
        "auto_patch_v2.law.approach_corridor",
        "auto_patch_v2.law.base_profile_schema",
        "auto_patch_v2.law.basin_schema",
        "auto_patch_v2.law.cockpit_schema",
        "auto_patch_v2.law.cutout_schema",
        "auto_patch_v2.law.deck_gen_schema",
        "auto_patch_v2.law.design_schema",
        "auto_patch_v2.law.eat_schema",
        "auto_patch_v2.law.flat_pack_schema",
        "auto_patch_v2.law.flat_site_schema",
        "auto_patch_v2.law.inset_class",
        "auto_patch_v2.law.model",
        "auto_patch_v2.law.model_types",
        "auto_patch_v2.law.rebake_schema",
        "auto_patch_v2.law.reference_code",
        "auto_patch_v2.law.role_cap_schema",
        "auto_patch_v2.law.runway_ends_schema",
        "auto_patch_v2.law.tables",
        "auto_patch_v2.law.terrace_schema",
        "auto_patch_v2.law.terrain_witness_schema",
        "auto_patch_v2.law.tunnel_object_schema",
        "auto_patch_v2.law.units",
        "auto_patch_v2.law.walled_plate_schema",
        "auto_patch_v2.model",
        "auto_patch_v2.model.agp_group",
        "auto_patch_v2.model.agp_plate",
        "auto_patch_v2.model.airport",
        "auto_patch_v2.model.clocks",
        "auto_patch_v2.model.constraints",
        "auto_patch_v2.model.deck_bank",
        "auto_patch_v2.model.deck_ends",
        "auto_patch_v2.model.deck_piece",
        "auto_patch_v2.model.deck_stack",
        "auto_patch_v2.model.end_area",
        "auto_patch_v2.model.floor_ground",
        "auto_patch_v2.model.frame",
        "auto_patch_v2.model.free_bridge",
        "auto_patch_v2.model.grade_separation",
        "auto_patch_v2.model.islands",
        "auto_patch_v2.model.map_memo",
        "auto_patch_v2.model.pad_terrace",
        "auto_patch_v2.model.placement",
        "auto_patch_v2.model.planar",
        "auto_patch_v2.model.platform",
        "auto_patch_v2.model.pulse",
        "auto_patch_v2.model.rebake",
        "auto_patch_v2.model.registries",
        "auto_patch_v2.model.road_clearance",
        "auto_patch_v2.model.road_yield",
        "auto_patch_v2.model.stage_one",
        "auto_patch_v2.model.storey_shell",
        "auto_patch_v2.model.structures",
        "auto_patch_v2.model.wall_reach",
        "auto_patch_v2.model.walled_plate",
        "auto_patch_v2.model.wing_cut",
        "auto_patch_v2.planar",
        "auto_patch_v2.planar.agp_ground",
        "auto_patch_v2.planar.apron_shelf",
        "auto_patch_v2.planar.bank_cut",
        "auto_patch_v2.planar.basin_author_ground",
        "auto_patch_v2.planar.basin_datum",
        "auto_patch_v2.planar.basin_floor_width",
        "auto_patch_v2.planar.basin_geometry",
        "auto_patch_v2.planar.basin_rim",
        "auto_patch_v2.planar.basins",
        "auto_patch_v2.planar.bore_continuation",
        "auto_patch_v2.planar.bridge_span",
        "auto_patch_v2.planar.build",
        "auto_patch_v2.planar.pinned_span",
        "auto_patch_v2.planar.cell_knife",
        "auto_patch_v2.planar.channel",
        "auto_patch_v2.planar.channel_claims",
        "auto_patch_v2.planar.channel_depth",
        "auto_patch_v2.planar.channel_floor",
        "auto_patch_v2.planar.channel_geometry",
        "auto_patch_v2.planar.channel_ramp",
        "auto_patch_v2.planar.channel_stretch",
        "auto_patch_v2.planar.channel_strip",
        "auto_patch_v2.planar.channel_building",
        "auto_patch_v2.planar.channel_witness",
        "auto_patch_v2.planar.chords",
        "auto_patch_v2.planar.covered_bores",
        "auto_patch_v2.planar.covered_cut",
        "auto_patch_v2.planar.covered_ground",
        "auto_patch_v2.planar.cut_frame",
        "auto_patch_v2.planar.cut_runout",
        "auto_patch_v2.planar.deck_airside",
        "auto_patch_v2.planar.deck_bores",
        "auto_patch_v2.planar.deck_bridge",
        "auto_patch_v2.planar.deck_generated",
        "auto_patch_v2.planar.deck_pack_cover",
        "auto_patch_v2.planar.deck_route",
        "auto_patch_v2.planar.deck_runout",
        "auto_patch_v2.planar.deck_skirt",
        "auto_patch_v2.planar.deck_span_cut",
        "auto_patch_v2.planar.route_lines",
        "auto_patch_v2.planar.deck_takeover",
        "auto_patch_v2.planar.deck_walls",
        "auto_patch_v2.planar.deck_width",
        "auto_patch_v2.planar.door_ramps",
        "auto_patch_v2.planar.dual_width",
        "auto_patch_v2.planar.edges",
        "auto_patch_v2.planar.end_barriers",
        "auto_patch_v2.planar.end_witness",
        "auto_patch_v2.planar.entrance_skirt",
        "auto_patch_v2.planar.fill_bank",
        "auto_patch_v2.planar.fill_riser",
        "auto_patch_v2.planar.fill_road",
        "auto_patch_v2.planar.floor_decks",
        "auto_patch_v2.planar.foot_kerb",
        "auto_patch_v2.planar.free_bridge",
        "auto_patch_v2.planar.front_band",
        "auto_patch_v2.planar.grade_separation",
        "auto_patch_v2.planar.ground_chords",
        "auto_patch_v2.planar.group_low",
        "auto_patch_v2.planar.group_up",
        "auto_patch_v2.planar.landing",
        "auto_patch_v2.planar.landing_runout",
        "auto_patch_v2.planar.level_depth",
        "auto_patch_v2.planar.level_regions",
        "auto_patch_v2.planar.level_underside",
        "auto_patch_v2.planar.lidar_road",
        "auto_patch_v2.planar.low_extent",
        "auto_patch_v2.planar.low_fill",
        "auto_patch_v2.planar.low_level",
        "auto_patch_v2.planar.mouth_behind",
        "auto_patch_v2.planar.mouth_opening",
        "auto_patch_v2.planar.object_corridor",
        "auto_patch_v2.planar.object_floor_cells",
        "auto_patch_v2.planar.overlay",
        "auto_patch_v2.planar.overpass_deck",
        "auto_patch_v2.planar.pack_reads",
        "auto_patch_v2.geom.pad_base_slope",
        "auto_patch_v2.planar.pad_blocks",
        "auto_patch_v2.planar.pad_cut",
        "auto_patch_v2.planar.pad_fill",
        "auto_patch_v2.planar.pad_sliver",
        "auto_patch_v2.planar.pad_terrace",
        "auto_patch_v2.planar.passage_court",
        "auto_patch_v2.planar.pit_bank",
        "auto_patch_v2.planar.plate_bays",
        "auto_patch_v2.planar.platform",
        "auto_patch_v2.planar.ramp_carry",
        "auto_patch_v2.planar.reach_after_pads",
        "auto_patch_v2.planar.reach_under_covers",
        "auto_patch_v2.planar.ribbon_weld",
        "auto_patch_v2.planar.ribbons",
        "auto_patch_v2.planar.ridge_reach",
        "auto_patch_v2.planar.road_shadow",
        "auto_patch_v2.planar.road_wall_witness",
        "auto_patch_v2.planar.road_yield",
        "auto_patch_v2.planar.shape_airside",
        "auto_patch_v2.planar.shape_mouths",
        "auto_patch_v2.planar.shape_pad_corner",
        "auto_patch_v2.planar.shape_parts",
        "auto_patch_v2.planar.shapes",
        "auto_patch_v2.planar.shore",
        "auto_patch_v2.planar.short_bore",
        "auto_patch_v2.planar.split_level_pit",
        "auto_patch_v2.planar.stack_ground",
        "auto_patch_v2.planar.station_level",
        "auto_patch_v2.planar.storey_floor",
        "auto_patch_v2.planar.storey_pad",
        "auto_patch_v2.planar.strip_keepout",
        "auto_patch_v2.planar.structure_approach",
        "auto_patch_v2.planar.structure_deck",
        "auto_patch_v2.planar.structure_fence",
        "auto_patch_v2.planar.structure_geometry",
        "auto_patch_v2.planar.structure_mouth",
        "auto_patch_v2.planar.structure_overlap",
        "auto_patch_v2.planar.structure_pair",
        "auto_patch_v2.planar.structure_road",
        "auto_patch_v2.planar.structure_service",
        "auto_patch_v2.planar.structure_stats",
        "auto_patch_v2.planar.structure_underpass",
        "auto_patch_v2.planar.structures",
        "auto_patch_v2.planar.survey_cut",
        "auto_patch_v2.planar.survey_deck_cut",
        "auto_patch_v2.planar.terrain_edge",
        "auto_patch_v2.planar.underpass_mouth",
        "auto_patch_v2.planar.unframed_ramp",
        "auto_patch_v2.planar.viaduct_road",
        "auto_patch_v2.planar.wall_corridor_ramps",
        "auto_patch_v2.planar.wall_slope",
        "auto_patch_v2.planar.weld",
        "auto_patch_v2.planar.wing_cut",
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
        "auto_patch_v2.law.agp_schema",
        "auto_patch_v2.law.airports_schema",
        "auto_patch_v2.law.base_profile_schema",
        "auto_patch_v2.law.basin_schema",
        "auto_patch_v2.law.cockpit_schema",
        "auto_patch_v2.law.cutout_schema",
        "auto_patch_v2.law.deck_gen_schema",
        "auto_patch_v2.law.design_schema",
        "auto_patch_v2.law.eat_schema",
        "auto_patch_v2.law.flat_pack_schema",
        "auto_patch_v2.law.flat_site_schema",
        "auto_patch_v2.law.inset_class",
        "auto_patch_v2.law.model",
        "auto_patch_v2.law.model_types",
        "auto_patch_v2.law.rebake_schema",
        "auto_patch_v2.law.reference_code",
        "auto_patch_v2.law.role_cap_schema",
        "auto_patch_v2.law.runway_ends_schema",
        "auto_patch_v2.law.tables",
        "auto_patch_v2.law.terrace_schema",
        "auto_patch_v2.law.terrain_witness_schema",
        "auto_patch_v2.law.tunnel_object_schema",
        "auto_patch_v2.law.units",
        "auto_patch_v2.law.walled_plate_schema",
        "auto_patch_v2.model",
        "auto_patch_v2.model.airport",
        "auto_patch_v2.model.frame",
    ),
    "road_profile": (
        "auto_patch_v2",
        "auto_patch_v2.airport",
        "auto_patch_v2.airport.adapted_riders",
        "auto_patch_v2.airport.airside_deck_seat",
        "auto_patch_v2.airport.airside_floor",
        "auto_patch_v2.airport.airside_group_seat",
        "auto_patch_v2.airport.anchor_rule",
        "auto_patch_v2.airport.apt_dat",
        "auto_patch_v2.airport.apt_edit",
        "auto_patch_v2.airport.apt_flatten",
        "auto_patch_v2.airport.authored_landing",
        "auto_patch_v2.airport.authored_seat",
        "auto_patch_v2.airport.backup_state",
        "auto_patch_v2.airport.basin_ring",
        "auto_patch_v2.airport.basin_witness",
        "auto_patch_v2.airport.below_grade_witness",
        "auto_patch_v2.airport.bore_ground",
        "auto_patch_v2.airport.borrow",
        "auto_patch_v2.airport.bridge_approach",
        "auto_patch_v2.airport.bridge_axis",
        "auto_patch_v2.airport.bridge_family",
        "auto_patch_v2.airport.bridge_ground",
        "auto_patch_v2.airport.bridge_witness",
        "auto_patch_v2.airport.bridged_ground",
        "auto_patch_v2.airport.bulk_geos",
        "auto_patch_v2.airport.cluster_profile",
        "auto_patch_v2.airport.connector_warp",
        "auto_patch_v2.airport.contact",
        "auto_patch_v2.airport.contents",
        "auto_patch_v2.airport.cut_deck_seat",
        "auto_patch_v2.airport.cut_portal_seat",
        "auto_patch_v2.airport.deck_carry",
        "auto_patch_v2.airport.deck_end_read",
        "auto_patch_v2.airport.deck_family_contact",
        "auto_patch_v2.airport.deck_plane_ring",
        "auto_patch_v2.airport.deck_plates",
        "auto_patch_v2.airport.deck_profile",
        "auto_patch_v2.airport.deck_riders",
        "auto_patch_v2.airport.deck_signature",
        "auto_patch_v2.airport.deck_surface",
        "auto_patch_v2.airport.deck_touch",
        "auto_patch_v2.airport.deck_track_bend",
        "auto_patch_v2.airport.dem",
        "auto_patch_v2.airport.dem_witness",
        "auto_patch_v2.airport.drawn_anchor",
        "auto_patch_v2.airport.dsf",
        "auto_patch_v2.airport.entrance_seat",
        "auto_patch_v2.airport.exclusion",
        "auto_patch_v2.airport.extension_cache",
        "auto_patch_v2.airport.facade",
        "auto_patch_v2.airport.file_hash",
        "auto_patch_v2.airport.file_verdict",
        "auto_patch_v2.airport.floor_rim",
        "auto_patch_v2.airport.footprint_carry",
        "auto_patch_v2.airport.footprint_connector",
        "auto_patch_v2.airport.footprint_seats",
        "auto_patch_v2.airport.footprint_unit",
        "auto_patch_v2.airport.frame_entry",
        "auto_patch_v2.airport.free_bridge_seat",
        "auto_patch_v2.airport.free_column",
        "auto_patch_v2.airport.ground_shell",
        "auto_patch_v2.airport.hanging_objects",
        "auto_patch_v2.airport.hung_wall_seat",
        "auto_patch_v2.airport.interior_deck",
        "auto_patch_v2.airport.isolated_seat",
        "auto_patch_v2.airport.level_base",
        "auto_patch_v2.airport.line_object",
        "auto_patch_v2.airport.line_solidity",
        "auto_patch_v2.airport.msl_feet",
        "auto_patch_v2.airport.obj8",
        "auto_patch_v2.airport.obj8_band",
        "auto_patch_v2.airport.obj8_clip",
        "auto_patch_v2.airport.obj8_drape",
        "auto_patch_v2.airport.obj8_grade",
        "auto_patch_v2.airport.obj8_memo",
        "auto_patch_v2.airport.obj8_rest",
        "auto_patch_v2.airport.obj8_roof",
        "auto_patch_v2.airport.obj8_split",
        "auto_patch_v2.airport.obj8_warp",
        "auto_patch_v2.airport.object_cut",
        "auto_patch_v2.airport.object_floor",
        "auto_patch_v2.airport.object_ground",
        "auto_patch_v2.airport.object_pack",
        "auto_patch_v2.airport.one_building",
        "auto_patch_v2.airport.open_frame_seat",
        "auto_patch_v2.airport.pack",
        "auto_patch_v2.airport.pack_art",
        "auto_patch_v2.airport.pack_choice",
        "auto_patch_v2.airport.pack_ground",
        "auto_patch_v2.airport.pack_health",
        "auto_patch_v2.airport.pack_health.light_records",
        "auto_patch_v2.airport.pack_local",
        "auto_patch_v2.airport.pack_partition",
        "auto_patch_v2.airport.pack_patch_witness",
        "auto_patch_v2.airport.pack_terrain",
        "auto_patch_v2.airport.pack_work",
        "auto_patch_v2.airport.pad_block_seat",
        "auto_patch_v2.airport.pad_level_group",
        "auto_patch_v2.airport.partition_cache",
        "auto_patch_v2.airport.partition_code",
        "auto_patch_v2.airport.pavement_end_plate",
        "auto_patch_v2.airport.pit_frame",
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
        "auto_patch_v2.airport.plate_ground",
        "auto_patch_v2.airport.pool",
        "auto_patch_v2.airport.pool_memory",
        "auto_patch_v2.airport.pool_slots",
        "auto_patch_v2.airport.rebake_plan",
        "auto_patch_v2.airport.relief_skin",
        "auto_patch_v2.airport.rider_floor",
        "auto_patch_v2.airport.ring_contact_batch",
        "auto_patch_v2.airport.road_bridge_ground",
        "auto_patch_v2.airport.road_profile",
        "auto_patch_v2.airport.road_stations",
        "auto_patch_v2.airport.road_ways",
        "auto_patch_v2.airport.scatter",
        "auto_patch_v2.airport.sheet_chain",
        "auto_patch_v2.airport.shell_ground",
        "auto_patch_v2.airport.skirt",
        "auto_patch_v2.airport.slab_faces",
        "auto_patch_v2.airport.slab_plates",
        "auto_patch_v2.airport.split_bar",
        "auto_patch_v2.airport.split_guard",
        "auto_patch_v2.airport.stacked_deck",
        "auto_patch_v2.airport.sunk_frame",
        "auto_patch_v2.airport.sunken_ramp",
        "auto_patch_v2.airport.terrain_base",
        "auto_patch_v2.airport.terrain_cut",
        "auto_patch_v2.airport.terrain_feature",
        "auto_patch_v2.airport.terrain_model",
        "auto_patch_v2.airport.terrain_shaped",
        "auto_patch_v2.airport.terrain_shell",
        "auto_patch_v2.airport.tilt_float",
        "auto_patch_v2.airport.topology_cache",
        "auto_patch_v2.airport.touch_graph",
        "auto_patch_v2.airport.touch_seat",
        "auto_patch_v2.airport.wall_class",
        "auto_patch_v2.airport.wall_geometry",
        "auto_patch_v2.airport.wall_sheets",
        "auto_patch_v2.airport.wall_sides",
        "auto_patch_v2.airport.wall_top",
        "auto_patch_v2.airport.walled_pit",
        "auto_patch_v2.airport.walled_plate",
        "auto_patch_v2.airport.zero_level_seat",
        "auto_patch_v2.geom",
        "auto_patch_v2.geom.author_ground",
        "auto_patch_v2.geom.base_slab",
        "auto_patch_v2.geom.centreline",
        "auto_patch_v2.geom.cluster_outline",
        "auto_patch_v2.geom.core_clamp",
        "auto_patch_v2.geom.coverage",
        "auto_patch_v2.geom.diameter",
        "auto_patch_v2.geom.exact",
        "auto_patch_v2.geom.foot_planes",
        "auto_patch_v2.geom.line_walk",
        "auto_patch_v2.geom.lowest_face",
        "auto_patch_v2.geom.pad_evidence",
        "auto_patch_v2.geom.parts",
        "auto_patch_v2.geom.plane_groups",
        "auto_patch_v2.geom.plate_bands",
        "auto_patch_v2.geom.rotated_rect",
        "auto_patch_v2.geom.shape_class",
        "auto_patch_v2.geom.station_runs",
        "auto_patch_v2.geom.terrain_deck",
        "auto_patch_v2.geom.union_find",
        "auto_patch_v2.geom.vector",
        "auto_patch_v2.law",
        "auto_patch_v2.law.agp_schema",
        "auto_patch_v2.law.airports_schema",
        "auto_patch_v2.law.base_profile_schema",
        "auto_patch_v2.law.basin_schema",
        "auto_patch_v2.law.cockpit_schema",
        "auto_patch_v2.law.cutout_schema",
        "auto_patch_v2.law.deck_gen_schema",
        "auto_patch_v2.law.design_schema",
        "auto_patch_v2.law.eat_schema",
        "auto_patch_v2.law.flat_pack_schema",
        "auto_patch_v2.law.flat_site_schema",
        "auto_patch_v2.law.model",
        "auto_patch_v2.law.model_types",
        "auto_patch_v2.law.rebake_schema",
        "auto_patch_v2.law.reference_code",
        "auto_patch_v2.law.role_cap_schema",
        "auto_patch_v2.law.runway_ends_schema",
        "auto_patch_v2.law.tables",
        "auto_patch_v2.law.terrace_schema",
        "auto_patch_v2.law.terrain_witness_schema",
        "auto_patch_v2.law.tunnel_object_schema",
        "auto_patch_v2.law.units",
        "auto_patch_v2.law.walled_plate_schema",
        "auto_patch_v2.model",
        "auto_patch_v2.model.airport",
        "auto_patch_v2.model.floor_ground",
        "auto_patch_v2.model.frame",
        "auto_patch_v2.model.free_bridge",
        "auto_patch_v2.model.placement",
        "auto_patch_v2.model.planar",
        "auto_patch_v2.model.pulse",
        "auto_patch_v2.model.rebake",
        "auto_patch_v2.model.registries",
        "auto_patch_v2.model.road_clearance",
        "auto_patch_v2.model.structures",
        "auto_patch_v2.model.wall_reach",
        "auto_patch_v2.model.walled_plate",
    ),
    "channels": (
        "auto_patch_v2",
        "auto_patch_v2.airport",
        "auto_patch_v2.airport.adapted_riders",
        "auto_patch_v2.airport.airside_deck_seat",
        "auto_patch_v2.airport.airside_floor",
        "auto_patch_v2.airport.airside_group_seat",
        "auto_patch_v2.airport.anchor_rule",
        "auto_patch_v2.airport.apt_dat",
        "auto_patch_v2.airport.apt_edit",
        "auto_patch_v2.airport.apt_flatten",
        "auto_patch_v2.airport.authored_landing",
        "auto_patch_v2.airport.authored_seat",
        "auto_patch_v2.airport.backup_state",
        "auto_patch_v2.airport.band_run",
        "auto_patch_v2.airport.basin_ring",
        "auto_patch_v2.airport.basin_witness",
        "auto_patch_v2.airport.below_grade_witness",
        "auto_patch_v2.airport.bore_ground",
        "auto_patch_v2.airport.borrow",
        "auto_patch_v2.airport.bridge_approach",
        "auto_patch_v2.airport.bridge_axis",
        "auto_patch_v2.airport.bridge_family",
        "auto_patch_v2.airport.bridge_ground",
        "auto_patch_v2.airport.bridge_span",
        "auto_patch_v2.airport.bridge_witness",
        "auto_patch_v2.airport.bridged_ground",
        "auto_patch_v2.airport.bulk_geos",
        "auto_patch_v2.airport.cluster_profile",
        "auto_patch_v2.airport.connector_warp",
        "auto_patch_v2.airport.contact",
        "auto_patch_v2.airport.contents",
        "auto_patch_v2.airport.cut_deck_seat",
        "auto_patch_v2.airport.cut_portal_seat",
        "auto_patch_v2.airport.deck_carry",
        "auto_patch_v2.airport.deck_end_read",
        "auto_patch_v2.airport.deck_ends",
        "auto_patch_v2.airport.deck_family_contact",
        "auto_patch_v2.airport.deck_plane_ring",
        "auto_patch_v2.airport.deck_plates",
        "auto_patch_v2.airport.deck_profile",
        "auto_patch_v2.airport.deck_riders",
        "auto_patch_v2.airport.deck_signature",
        "auto_patch_v2.airport.deck_surface",
        "auto_patch_v2.airport.deck_touch",
        "auto_patch_v2.airport.deck_track_bend",
        "auto_patch_v2.airport.dem",
        "auto_patch_v2.airport.dem_witness",
        "auto_patch_v2.airport.drawn_anchor",
        "auto_patch_v2.airport.dsf",
        "auto_patch_v2.airport.entrance_seat",
        "auto_patch_v2.airport.exclusion",
        "auto_patch_v2.airport.extension_cache",
        "auto_patch_v2.airport.facade",
        "auto_patch_v2.airport.file_hash",
        "auto_patch_v2.airport.file_verdict",
        "auto_patch_v2.airport.floor_rim",
        "auto_patch_v2.airport.foot_lot",
        "auto_patch_v2.airport.footprint_carry",
        "auto_patch_v2.airport.footprint_connector",
        "auto_patch_v2.airport.footprint_seats",
        "auto_patch_v2.airport.footprint_unit",
        "auto_patch_v2.airport.frame_entry",
        "auto_patch_v2.airport.free_bridge_seat",
        "auto_patch_v2.airport.free_column",
        "auto_patch_v2.airport.ground_shell",
        "auto_patch_v2.airport.hanging_objects",
        "auto_patch_v2.airport.hung_wall_seat",
        "auto_patch_v2.airport.interior_deck",
        "auto_patch_v2.airport.isolated_seat",
        "auto_patch_v2.airport.level_base",
        "auto_patch_v2.airport.line_object",
        "auto_patch_v2.airport.line_solidity",
        "auto_patch_v2.airport.lot_level",
        "auto_patch_v2.airport.msl_feet",
        "auto_patch_v2.airport.obj8",
        "auto_patch_v2.airport.obj8_band",
        "auto_patch_v2.airport.obj8_clip",
        "auto_patch_v2.airport.obj8_drape",
        "auto_patch_v2.airport.obj8_grade",
        "auto_patch_v2.airport.obj8_memo",
        "auto_patch_v2.airport.obj8_rest",
        "auto_patch_v2.airport.obj8_roof",
        "auto_patch_v2.airport.obj8_split",
        "auto_patch_v2.airport.obj8_warp",
        "auto_patch_v2.airport.object_cut",
        "auto_patch_v2.airport.object_floor",
        "auto_patch_v2.airport.object_ground",
        "auto_patch_v2.airport.object_pack",
        "auto_patch_v2.airport.one_building",
        "auto_patch_v2.airport.open_frame_seat",
        "auto_patch_v2.airport.pack",
        "auto_patch_v2.airport.pack_art",
        "auto_patch_v2.airport.pack_choice",
        "auto_patch_v2.airport.pack_ground",
        "auto_patch_v2.airport.pack_health",
        "auto_patch_v2.airport.pack_health.light_records",
        "auto_patch_v2.airport.pack_local",
        "auto_patch_v2.airport.pack_partition",
        "auto_patch_v2.airport.pack_patch_witness",
        "auto_patch_v2.airport.pack_terrain",
        "auto_patch_v2.airport.pack_work",
        "auto_patch_v2.airport.pad_block_seat",
        "auto_patch_v2.airport.pad_level_group",
        "auto_patch_v2.airport.partition_cache",
        "auto_patch_v2.airport.partition_code",
        "auto_patch_v2.airport.pavement_end_plate",
        "auto_patch_v2.airport.pit_frame",
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
        "auto_patch_v2.airport.plate_ground",
        "auto_patch_v2.airport.pool",
        "auto_patch_v2.airport.pool_memory",
        "auto_patch_v2.airport.pool_slots",
        "auto_patch_v2.airport.public_road",
        "auto_patch_v2.airport.rebake_plan",
        "auto_patch_v2.airport.relief_skin",
        "auto_patch_v2.airport.rider_floor",
        "auto_patch_v2.airport.ring_contact_batch",
        "auto_patch_v2.airport.riser_wall",
        "auto_patch_v2.airport.road_bridge_ground",
        "auto_patch_v2.airport.road_descent",
        "auto_patch_v2.airport.road_joint",
        "auto_patch_v2.airport.road_profile",
        "auto_patch_v2.airport.road_ramp",
        "auto_patch_v2.airport.road_stations",
        "auto_patch_v2.airport.road_ways",
        "auto_patch_v2.airport.scatter",
        "auto_patch_v2.airport.sheet_chain",
        "auto_patch_v2.airport.shell_ground",
        "auto_patch_v2.airport.skirt",
        "auto_patch_v2.airport.slab_faces",
        "auto_patch_v2.airport.slab_plates",
        "auto_patch_v2.airport.split_bar",
        "auto_patch_v2.airport.split_guard",
        "auto_patch_v2.airport.stacked_deck",
        "auto_patch_v2.airport.sunk_frame",
        "auto_patch_v2.airport.sunken_ramp",
        "auto_patch_v2.airport.terrain_base",
        "auto_patch_v2.airport.terrain_cut",
        "auto_patch_v2.airport.terrain_feature",
        "auto_patch_v2.airport.terrain_model",
        "auto_patch_v2.airport.terrain_shaped",
        "auto_patch_v2.airport.terrain_shell",
        "auto_patch_v2.airport.tilt_float",
        "auto_patch_v2.airport.topology_cache",
        "auto_patch_v2.airport.touch_graph",
        "auto_patch_v2.airport.touch_seat",
        "auto_patch_v2.airport.wall_class",
        "auto_patch_v2.airport.wall_geometry",
        "auto_patch_v2.airport.wall_sheets",
        "auto_patch_v2.airport.wall_sides",
        "auto_patch_v2.airport.wall_top",
        "auto_patch_v2.airport.walled_pit",
        "auto_patch_v2.airport.walled_plate",
        "auto_patch_v2.airport.zero_level_seat",
        "auto_patch_v2.constraints",
        "auto_patch_v2.constraints.apron",
        "auto_patch_v2.constraints.apron_trend",
        "auto_patch_v2.constraints.cluster_pad",
        "auto_patch_v2.constraints.deck_anchor",
        "auto_patch_v2.constraints.deck_lines",
        "auto_patch_v2.constraints.eat",
        "auto_patch_v2.constraints.edge_floor",
        "auto_patch_v2.constraints.face_index",
        "auto_patch_v2.constraints.geometry",
        "auto_patch_v2.constraints.group_level",
        "auto_patch_v2.constraints.pad_relief",
        "auto_patch_v2.constraints.pad_warning",
        "auto_patch_v2.constraints.pads",
        "auto_patch_v2.constraints.platform",
        "auto_patch_v2.constraints.precedence",
        "auto_patch_v2.constraints.routes",
        "auto_patch_v2.constraints.runway_chord",
        "auto_patch_v2.constraints.runway_junctions",
        "auto_patch_v2.constraints.runway_profile",
        "auto_patch_v2.constraints.runway_yield",
        "auto_patch_v2.constraints.shoulder_crossing",
        "auto_patch_v2.constraints.stretches",
        "auto_patch_v2.constraints.surface_trend",
        "auto_patch_v2.constraints.taxi",
        "auto_patch_v2.constraints.taxi_route_yield",
        "auto_patch_v2.constraints.taxi_trend",
        "auto_patch_v2.constraints.taxi_trend_cap",
        "auto_patch_v2.constraints.threshold_seam",
        "auto_patch_v2.emit",
        "auto_patch_v2.emit.road_join",
        "auto_patch_v2.geom",
        "auto_patch_v2.geom.agp_plate",
        "auto_patch_v2.geom.author_ground",
        "auto_patch_v2.geom.base_slab",
        "auto_patch_v2.geom.centreline",
        "auto_patch_v2.geom.cluster_outline",
        "auto_patch_v2.geom.containment",
        "auto_patch_v2.geom.core_clamp",
        "auto_patch_v2.geom.coverage",
        "auto_patch_v2.geom.deck_ground",
        "auto_patch_v2.geom.diameter",
        "auto_patch_v2.geom.end_line",
        "auto_patch_v2.geom.exact",
        "auto_patch_v2.geom.foot_planes",
        "auto_patch_v2.geom.line_walk",
        "auto_patch_v2.geom.lowest_face",
        "auto_patch_v2.geom.pad_evidence",
        "auto_patch_v2.geom.parts",
        "auto_patch_v2.geom.plane_groups",
        "auto_patch_v2.geom.plate_bands",
        "auto_patch_v2.geom.plate_heights",
        "auto_patch_v2.geom.ramp_grade",
        "auto_patch_v2.geom.rotated_rect",
        "auto_patch_v2.geom.runway_contact",
        "auto_patch_v2.geom.shape_class",
        "auto_patch_v2.geom.slope_pad",
        "auto_patch_v2.geom.station_runs",
        "auto_patch_v2.geom.terrain_deck",
        "auto_patch_v2.geom.trend",
        "auto_patch_v2.geom.triangulate",
        "auto_patch_v2.geom.union_find",
        "auto_patch_v2.geom.vector",
        "auto_patch_v2.law",
        "auto_patch_v2.law.agp_schema",
        "auto_patch_v2.law.airports_schema",
        "auto_patch_v2.law.base_profile_schema",
        "auto_patch_v2.law.basin_schema",
        "auto_patch_v2.law.cockpit_schema",
        "auto_patch_v2.law.cutout_schema",
        "auto_patch_v2.law.deck_gen_schema",
        "auto_patch_v2.law.design_schema",
        "auto_patch_v2.law.eat_schema",
        "auto_patch_v2.law.flat_pack_schema",
        "auto_patch_v2.law.flat_site_schema",
        "auto_patch_v2.law.inset_class",
        "auto_patch_v2.law.model",
        "auto_patch_v2.law.model_types",
        "auto_patch_v2.law.rebake_schema",
        "auto_patch_v2.law.reference_code",
        "auto_patch_v2.law.role_cap_schema",
        "auto_patch_v2.law.runway_ends_schema",
        "auto_patch_v2.law.tables",
        "auto_patch_v2.law.terrace_schema",
        "auto_patch_v2.law.terrain_witness_schema",
        "auto_patch_v2.law.tunnel_object_schema",
        "auto_patch_v2.law.units",
        "auto_patch_v2.law.walled_plate_schema",
        "auto_patch_v2.model",
        "auto_patch_v2.model.agp_group",
        "auto_patch_v2.model.agp_plate",
        "auto_patch_v2.model.airport",
        "auto_patch_v2.model.constraints",
        "auto_patch_v2.model.deck_ends",
        "auto_patch_v2.model.deck_stack",
        "auto_patch_v2.model.floor_ground",
        "auto_patch_v2.model.frame",
        "auto_patch_v2.model.free_bridge",
        "auto_patch_v2.model.grade_separation",
        "auto_patch_v2.model.islands",
        "auto_patch_v2.model.map_memo",
        "auto_patch_v2.model.placement",
        "auto_patch_v2.model.planar",
        "auto_patch_v2.model.platform",
        "auto_patch_v2.model.pulse",
        "auto_patch_v2.model.rebake",
        "auto_patch_v2.model.registries",
        "auto_patch_v2.model.road_clearance",
        "auto_patch_v2.model.road_yield",
        "auto_patch_v2.model.stage_one",
        "auto_patch_v2.model.storey_shell",
        "auto_patch_v2.model.structures",
        "auto_patch_v2.model.wall_reach",
        "auto_patch_v2.model.walled_plate",
    ),
    "shapes": (
        "auto_patch_v2",
        "auto_patch_v2.airport",
        "auto_patch_v2.airport.access_road",
        "auto_patch_v2.airport.adapted_riders",
        "auto_patch_v2.airport.agp_deck_ends",
        "auto_patch_v2.airport.agp_deck_join",
        "auto_patch_v2.airport.agp_floors",
        "auto_patch_v2.airport.agp_foot_pads",
        "auto_patch_v2.airport.agp_gap_plates",
        "auto_patch_v2.airport.agp_ground",
        "auto_patch_v2.airport.agp_group",
        "auto_patch_v2.airport.agp_pieces",
        "auto_patch_v2.airport.agp_plan",
        "auto_patch_v2.airport.agp_plates",
        "auto_patch_v2.airport.airside_deck_seat",
        "auto_patch_v2.airport.airside_floor",
        "auto_patch_v2.airport.airside_group_seat",
        "auto_patch_v2.airport.anchor_rule",
        "auto_patch_v2.airport.apt_dat",
        "auto_patch_v2.airport.apt_edit",
        "auto_patch_v2.airport.apt_flatten",
        "auto_patch_v2.airport.authored_landing",
        "auto_patch_v2.airport.authored_seat",
        "auto_patch_v2.airport.backup_state",
        "auto_patch_v2.airport.basin_ring",
        "auto_patch_v2.airport.basin_witness",
        "auto_patch_v2.airport.below_grade_witness",
        "auto_patch_v2.airport.borrow",
        "auto_patch_v2.airport.bridge_approach",
        "auto_patch_v2.airport.bridge_axis",
        "auto_patch_v2.airport.bridge_end_state",
        "auto_patch_v2.airport.bridge_family",
        "auto_patch_v2.airport.bridge_frame",
        "auto_patch_v2.airport.bridge_stack",
        "auto_patch_v2.airport.bridge_witness",
        "auto_patch_v2.airport.bridged_ground",
        "auto_patch_v2.airport.bulk_geos",
        "auto_patch_v2.airport.cluster_profile",
        "auto_patch_v2.airport.connector_warp",
        "auto_patch_v2.airport.contact",
        "auto_patch_v2.airport.contents",
        "auto_patch_v2.airport.cut_deck_seat",
        "auto_patch_v2.airport.cut_portal_seat",
        "auto_patch_v2.airport.deck_carry",
        "auto_patch_v2.airport.deck_end_read",
        "auto_patch_v2.airport.deck_ends",
        "auto_patch_v2.airport.deck_family_contact",
        "auto_patch_v2.airport.deck_plane_ring",
        "auto_patch_v2.airport.deck_plates",
        "auto_patch_v2.airport.deck_profile",
        "auto_patch_v2.airport.deck_riders",
        "auto_patch_v2.airport.deck_signature",
        "auto_patch_v2.airport.deck_stack",
        "auto_patch_v2.airport.deck_surface",
        "auto_patch_v2.airport.deck_touch",
        "auto_patch_v2.airport.deck_track_bend",
        "auto_patch_v2.airport.dem",
        "auto_patch_v2.airport.dem_witness",
        "auto_patch_v2.airport.drawn_anchor",
        "auto_patch_v2.airport.dsf",
        "auto_patch_v2.airport.dsf_heights",
        "auto_patch_v2.airport.entrance_seat",
        "auto_patch_v2.airport.exclusion",
        "auto_patch_v2.airport.extension_cache",
        "auto_patch_v2.airport.facade",
        "auto_patch_v2.airport.facade_seat",
        "auto_patch_v2.airport.file_hash",
        "auto_patch_v2.airport.floor_deck_ends",
        "auto_patch_v2.airport.floor_rim",
        "auto_patch_v2.airport.footprint_carry",
        "auto_patch_v2.airport.footprint_connector",
        "auto_patch_v2.airport.footprint_seats",
        "auto_patch_v2.airport.footprint_unit",
        "auto_patch_v2.airport.level_base",
        "auto_patch_v2.airport.frame_entry",
        "auto_patch_v2.airport.free_bridge_seat",
        "auto_patch_v2.airport.free_column",
        "auto_patch_v2.airport.ground_route_ways",
        "auto_patch_v2.airport.ground_shell",
        "auto_patch_v2.airport.hanging_objects",
        "auto_patch_v2.airport.hung_wall_seat",
        "auto_patch_v2.airport.interior_deck",
        "auto_patch_v2.airport.isolated_seat",
        "auto_patch_v2.airport.jetways",
        "auto_patch_v2.airport.line_object",
        "auto_patch_v2.airport.line_solidity",
        "auto_patch_v2.airport.msl_feet",
        "auto_patch_v2.airport.obj8",
        "auto_patch_v2.airport.obj8_band",
        "auto_patch_v2.airport.obj8_clip",
        "auto_patch_v2.airport.obj8_drape",
        "auto_patch_v2.airport.obj8_grade",
        "auto_patch_v2.airport.obj8_memo",
        "auto_patch_v2.airport.obj8_rest",
        "auto_patch_v2.airport.obj8_roof",
        "auto_patch_v2.airport.obj8_split",
        "auto_patch_v2.airport.obj8_warp",
        "auto_patch_v2.airport.object_cut",
        "auto_patch_v2.airport.object_floor",
        "auto_patch_v2.airport.object_pack",
        "auto_patch_v2.airport.one_building",
        "auto_patch_v2.airport.open_frame_seat",
        "auto_patch_v2.airport.pack",
        "auto_patch_v2.airport.pack_art",
        "auto_patch_v2.airport.pack_choice",
        "auto_patch_v2.airport.pack_ground",
        "auto_patch_v2.airport.pack_health",
        "auto_patch_v2.airport.pack_health.light_records",
        "auto_patch_v2.airport.pack_local",
        "auto_patch_v2.airport.pack_partition",
        "auto_patch_v2.airport.pack_patch_witness",
        "auto_patch_v2.airport.pack_terrain",
        "auto_patch_v2.airport.pack_work",
        "auto_patch_v2.airport.pad_block_seat",
        "auto_patch_v2.airport.pad_level_group",
        "auto_patch_v2.airport.partition_cache",
        "auto_patch_v2.airport.partition_code",
        "auto_patch_v2.airport.pavement_end_plate",
        "auto_patch_v2.airport.pit_frame",
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
        "auto_patch_v2.airport.pool_memory",
        "auto_patch_v2.airport.pool_slots",
        "auto_patch_v2.airport.rebake_plan",
        "auto_patch_v2.airport.relief_skin",
        "auto_patch_v2.airport.file_verdict",
        "auto_patch_v2.airport.rider_floor",
        "auto_patch_v2.airport.riders",
        "auto_patch_v2.airport.ring_contact_batch",
        "auto_patch_v2.airport.road_ways",
        "auto_patch_v2.airport.runway_strip",
        "auto_patch_v2.airport.scatter",
        "auto_patch_v2.airport.sheet_chain",
        "auto_patch_v2.airport.shell_ground",
        "auto_patch_v2.airport.skirt",
        "auto_patch_v2.airport.slab_faces",
        "auto_patch_v2.airport.slab_plates",
        "auto_patch_v2.airport.split_bar",
        "auto_patch_v2.airport.split_guard",
        "auto_patch_v2.airport.split_level",
        "auto_patch_v2.airport.split_level_wings",
        "auto_patch_v2.airport.stack_end_seat",
        "auto_patch_v2.airport.stack_walls",
        "auto_patch_v2.airport.stacked_deck",
        "auto_patch_v2.airport.sunk_frame",
        "auto_patch_v2.airport.sunken_ramp",
        "auto_patch_v2.airport.terrain_base",
        "auto_patch_v2.airport.terrain_feature",
        "auto_patch_v2.airport.terrain_model",
        "auto_patch_v2.airport.terrain_shaped",
        "auto_patch_v2.airport.terrain_shell",
        "auto_patch_v2.airport.tilt_float",
        "auto_patch_v2.airport.topology_cache",
        "auto_patch_v2.airport.touch_graph",
        "auto_patch_v2.airport.touch_seat",
        "auto_patch_v2.airport.unit_storey",
        "auto_patch_v2.airport.user_roles",
        "auto_patch_v2.airport.wall_class",
        "auto_patch_v2.airport.wall_geometry",
        "auto_patch_v2.airport.wall_sheets",
        "auto_patch_v2.airport.wall_sides",
        "auto_patch_v2.airport.wall_top",
        "auto_patch_v2.airport.walled_pit",
        "auto_patch_v2.airport.walled_plate",
        "auto_patch_v2.airport.zero_level_seat",
        "auto_patch_v2.classify",
        "auto_patch_v2.classify.airside_edge",
        "auto_patch_v2.classify.apron_gate",
        "auto_patch_v2.classify.apt_shoulder",
        "auto_patch_v2.classify.blast_pad",
        "auto_patch_v2.classify.car_lot",
        "auto_patch_v2.classify.edge_line_mint",
        "auto_patch_v2.classify.end_pad",
        "auto_patch_v2.classify.evidence",
        "auto_patch_v2.classify.facade_mint",
        "auto_patch_v2.classify.fence_division",
        "auto_patch_v2.classify.fence_yard",
        "auto_patch_v2.classify.floor_yard",
        "auto_patch_v2.classify.frontage_road",
        "auto_patch_v2.classify.gap_apron",
        "auto_patch_v2.classify.gap_band",
        "auto_patch_v2.classify.gap_mint",
        "auto_patch_v2.classify.gap_stands",
        "auto_patch_v2.classify.island_spurs",
        "auto_patch_v2.classify.lot_roads",
        "auto_patch_v2.classify.neck",
        "auto_patch_v2.classify.open_default",
        "auto_patch_v2.classify.pad_cut_corridor",
        "auto_patch_v2.classify.neck_road",
        "auto_patch_v2.classify.pad_sunk",
        "auto_patch_v2.classify.pad_touch",
        "auto_patch_v2.classify.reachability",
        "auto_patch_v2.classify.retaining_wall",
        "auto_patch_v2.classify.ribbon_mint",
        "auto_patch_v2.classify.roles",
        "auto_patch_v2.classify.rules",
        "auto_patch_v2.classify.sources",
        "auto_patch_v2.classify.storey_edge",
        "auto_patch_v2.classify.taxi_letter",
        "auto_patch_v2.classify.taxi_shoulder",
        "auto_patch_v2.classify.wall_clip",
        "auto_patch_v2.classify.wall_cutback",
        "auto_patch_v2.classify.wrap_page",
        "auto_patch_v2.constraints",
        "auto_patch_v2.constraints.agp_level",
        "auto_patch_v2.constraints.agp_plate",
        "auto_patch_v2.constraints.airside_floor",
        "auto_patch_v2.constraints.airside_top",
        "auto_patch_v2.constraints.apron",
        "auto_patch_v2.constraints.apron_shelf",
        "auto_patch_v2.constraints.assembly",
        "auto_patch_v2.constraints.bridge_span_release",
        "auto_patch_v2.constraints.ceiling",
        "auto_patch_v2.constraints.channel",
        "auto_patch_v2.constraints.cluster_pad",
        "auto_patch_v2.constraints.contiguity",
        "auto_patch_v2.constraints.cut_kerb",
        "auto_patch_v2.constraints.deck_anchor",
        "auto_patch_v2.constraints.deck_lines",
        "auto_patch_v2.constraints.deck_runout",
        "auto_patch_v2.constraints.deck_stack",
        "auto_patch_v2.constraints.door_pad",
        "auto_patch_v2.constraints.eat",
        "auto_patch_v2.constraints.edge_deck",
        "auto_patch_v2.constraints.edge_floor",
        "auto_patch_v2.constraints.end_lip",
        "auto_patch_v2.constraints.entrance_skirt",
        "auto_patch_v2.constraints.face_index",
        "auto_patch_v2.constraints.fill_bank",
        "auto_patch_v2.constraints.flat_site",
        "auto_patch_v2.constraints.foot_rows",
        "auto_patch_v2.constraints.gap_follow",
        "auto_patch_v2.constraints.geometry",
        "auto_patch_v2.constraints.groundside",
        "auto_patch_v2.constraints.group_level",
        "auto_patch_v2.constraints.hard_plane",
        "auto_patch_v2.constraints.junction_mesh",
        "auto_patch_v2.constraints.no_step",
        "auto_patch_v2.constraints.object_floor",
        "auto_patch_v2.constraints.pad_frontage_gs",
        "auto_patch_v2.constraints.pad_fronting",
        "auto_patch_v2.constraints.pad_sunk_level",
        "auto_patch_v2.constraints.pad_ramp",
        "auto_patch_v2.constraints.pad_relief",
        "auto_patch_v2.constraints.pad_warning",
        "auto_patch_v2.constraints.pads",
        "auto_patch_v2.constraints.pavement_cap",
        "auto_patch_v2.constraints.platform",
        "auto_patch_v2.constraints.precedence",
        "auto_patch_v2.constraints.proximity",
        "auto_patch_v2.constraints.public_road_release",
        "auto_patch_v2.constraints.ramp_runout",
        "auto_patch_v2.constraints.riser",
        "auto_patch_v2.constraints.road_bridge_ceiling",
        "auto_patch_v2.constraints.road_ramp",
        "auto_patch_v2.constraints.roads",
        "auto_patch_v2.constraints.routes",
        "auto_patch_v2.constraints.runway_chord",
        "auto_patch_v2.constraints.runway_junctions",
        "auto_patch_v2.constraints.runway_mean_slope",
        "auto_patch_v2.constraints.runway_profile",
        "auto_patch_v2.constraints.runway_step",
        "auto_patch_v2.constraints.runway_yield",
        "auto_patch_v2.constraints.seams",
        "auto_patch_v2.constraints.shell_datum",
        "auto_patch_v2.constraints.shoulder_crossing",
        "auto_patch_v2.constraints.steep_apron",
        "auto_patch_v2.constraints.stretches",
        "auto_patch_v2.constraints.strips",
        "auto_patch_v2.constraints.structures",
        "auto_patch_v2.constraints.survey_floor",
        "auto_patch_v2.constraints.taxi",
        "auto_patch_v2.constraints.taxi_route_yield",
        "auto_patch_v2.constraints.taxi_trend",
        "auto_patch_v2.constraints.taxi_trend_cap",
        "auto_patch_v2.constraints.terrain_shaped",
        "auto_patch_v2.constraints.threshold_seam",
        "auto_patch_v2.constraints.transverse",
        "auto_patch_v2.constraints.viaduct_floor",
        "auto_patch_v2.constraints.wall_zone",
        "auto_patch_v2.constraints.walled_plate",
        "auto_patch_v2.constraints.water",
        "auto_patch_v2.constraints.weld_floor",
        "auto_patch_v2.constraints.wing_cut",
        "auto_patch_v2.constraints.yard_edge",
        "auto_patch_v2.constraints.zones",
        "auto_patch_v2.geom",
        "auto_patch_v2.geom.agp_plate",
        "auto_patch_v2.geom.author_ground",
        "auto_patch_v2.geom.base_slab",
        "auto_patch_v2.geom.capped_plane",
        "auto_patch_v2.geom.centreline",
        "auto_patch_v2.geom.channel_declared",
        "auto_patch_v2.geom.cluster_outline",
        "auto_patch_v2.geom.containment",
        "auto_patch_v2.geom.core_clamp",
        "auto_patch_v2.geom.deck_ground",
        "auto_patch_v2.geom.diameter",
        "auto_patch_v2.geom.end_line",
        "auto_patch_v2.geom.exact",
        "auto_patch_v2.geom.feet_graph",
        "auto_patch_v2.geom.feet_mst",
        "auto_patch_v2.geom.fixed_overlay",
        "auto_patch_v2.geom.foot_planes",
        "auto_patch_v2.geom.lens",
        "auto_patch_v2.geom.line_walk",
        "auto_patch_v2.geom.lowest_face",
        "auto_patch_v2.geom.many_buffers",
        "auto_patch_v2.geom.pad_evidence",
        "auto_patch_v2.geom.parts",
        "auto_patch_v2.geom.plane_groups",
        "auto_patch_v2.geom.plate_bands",
        "auto_patch_v2.geom.plate_heights",
        "auto_patch_v2.geom.proportions",
        "auto_patch_v2.geom.ramp_grade",
        "auto_patch_v2.geom.ramp_profile",
        "auto_patch_v2.geom.rotated_rect",
        "auto_patch_v2.geom.runway_contact",
        "auto_patch_v2.geom.shape_class",
        "auto_patch_v2.geom.slope_pad",
        "auto_patch_v2.geom.terrain_deck",
        "auto_patch_v2.geom.trend",
        "auto_patch_v2.geom.triangulate",
        "auto_patch_v2.geom.union_find",
        "auto_patch_v2.geom.valid_area",
        "auto_patch_v2.geom.vector",
        "auto_patch_v2.geom.wall_lines",
        "auto_patch_v2.geom.water_level",
        "auto_patch_v2.law",
        "auto_patch_v2.law.agp_schema",
        "auto_patch_v2.law.airports_schema",
        "auto_patch_v2.law.base_profile_schema",
        "auto_patch_v2.law.basin_schema",
        "auto_patch_v2.law.cockpit_schema",
        "auto_patch_v2.law.cutout_schema",
        "auto_patch_v2.law.deck_gen_schema",
        "auto_patch_v2.law.design_schema",
        "auto_patch_v2.law.eat_schema",
        "auto_patch_v2.law.flat_pack_schema",
        "auto_patch_v2.law.flat_site_schema",
        "auto_patch_v2.law.inset_class",
        "auto_patch_v2.law.model",
        "auto_patch_v2.law.model_types",
        "auto_patch_v2.law.rebake_schema",
        "auto_patch_v2.law.reference_code",
        "auto_patch_v2.law.role_cap_schema",
        "auto_patch_v2.law.runway_ends_schema",
        "auto_patch_v2.law.tables",
        "auto_patch_v2.law.terrace_schema",
        "auto_patch_v2.law.terrain_witness_schema",
        "auto_patch_v2.law.tunnel_object_schema",
        "auto_patch_v2.law.units",
        "auto_patch_v2.law.walled_plate_schema",
        "auto_patch_v2.model",
        "auto_patch_v2.model.agp_group",
        "auto_patch_v2.model.agp_plate",
        "auto_patch_v2.model.airport",
        "auto_patch_v2.model.clocks",
        "auto_patch_v2.model.constraints",
        "auto_patch_v2.model.deck_bank",
        "auto_patch_v2.model.deck_ends",
        "auto_patch_v2.model.deck_stack",
        "auto_patch_v2.model.end_area",
        "auto_patch_v2.model.floor_ground",
        "auto_patch_v2.model.frame",
        "auto_patch_v2.model.free_bridge",
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
        "auto_patch_v2.model.road_clearance",
        "auto_patch_v2.model.stage_one",
        "auto_patch_v2.model.structures",
        "auto_patch_v2.model.threshold_datum",
        "auto_patch_v2.model.wall_reach",
        "auto_patch_v2.model.walled_plate",
        "auto_patch_v2.model.wing_cut",
        "auto_patch_v2.model.yard_run",
        "auto_patch_v2.pipeline",
        "auto_patch_v2.pipeline.shapes",
        "auto_patch_v2.planar",
        "auto_patch_v2.planar.shape_airside",
        "auto_patch_v2.planar.shape_mouths",
        "auto_patch_v2.planar.shape_pad_corner",
        "auto_patch_v2.planar.shape_parts",
        "auto_patch_v2.planar.shapes",
        "auto_patch_v2.planar.strip_keepout",
    ),
}


def _mods(names: str) -> tuple[str, ...]:
    """``auto_patch_v2``-relative module names, whitespace-separated, as the
    sorted tuple :data:`CODE_MODULES` holds — with ``auto_patch_v2`` itself,
    the package above every one of them (#993)."""
    return tuple(sorted({"auto_patch_v2",
                         *(f"auto_patch_v2.{n}" for n in names.split())}))


#: Each constraint generator's module (``constraints.GENERATORS``: name ->
#: ``fn.__module__``), held by ``test_stage_code_closure.py``.
GENERATOR_MODULES: dict[str, str] = {
    "runway_profile": "runway_profile",
    "runway_crown": "runway_profile",
    "runway_transverse": "runway_profile",
    "runway_vertical_curve": "runway_profile",
    "runway_step": "runway_step",
    "runway_mean_slope": "runway_mean_slope",
    "runway_within_shape": "runway_profile",
    "runway_crossing_pin": "runway_chord",
    "deck_anchor": "deck_anchor",
    "taxi_chain": "taxi",
    "taxi_centerlines": "taxi",
    "triangle_planes": "taxi",
    "taxi_box": "taxi",
    "junction_mesh": "junction_mesh",
    "apron_within_shape": "apron",
    "hard_plane_level": "hard_plane",
    "steep_apron_plane": "steep_apron",
    "door_pad_level": "door_pad",
    "apron_edge_portions": "apron",
    "road_within_shape": "roads",
    "road_ramp": "road_ramp",
    "road_contact": "road_ramp",
    "edge_deck": "edge_deck",
    "road_coverage_join": "road_ramp",
    "wall_terrace": "road_ramp",
    "groundside_ramp": "groundside",
    "transverse": "transverse",
    "junction_raw_transverse": "transverse",
    "no_step_pairs": "no_step",
    "no_step_rate": "no_step",
    "cross_shape_pairs": "proximity",
    "airside_sliver_pairs": "proximity",
    "reach_bands": "no_step",
    "zone_bands": "zones",
    "strip_transverse": "zones",
    "road_bridge_ceiling": "road_bridge_ceiling",
    "walled_plate_under": "walled_plate",
    "terrain_shaped_deck": "terrain_shaped",
    "strip_longitudinal": "strips",
    "strip_arc": "strips",
    "resa_transverse": "strips",
    "end_corridor_longitudinal": "strips",
    "end_corridor_rate": "strips",
    "raoa": "strips",
    "pad_flats": "pads",
    "pad_frontage_level": "pads",
    "pad_sunk_level": "pad_sunk_level",
    "pad_fronting_level": "pad_fronting",
    "pad_slope_ceiling": "pads",
    "platform_collar": "platform",
    "block_strip": "platform",
    "platform_plane": "platform",
    "landing_level": "platform",
    "shell_datum": "shell_datum",
    "landing_runout": "ramp_runout",
    "platform_level": "platform",
    "frontage_hold": "platform",
    "frontage_near_miss": "pads",
    "groundside_frontage_level": "pad_frontage_gs",
    "kerb_frontage_level": "kerb_frontage",
    "eat_anchor_rect": "eat",
    "water_pins": "water",
    "fill_toe_pins": "fill_bank",
    "seam_pins": "seams",
    "flat_datum": "flat_site",
    "foot_rows": "foot_rows",
    "structures": "structures",
    "rim_level": "structures",
    "basins": "structures",
    "object_floor": "object_floor",
    "wing_cut": "wing_cut",
    "deck_stack": "deck_stack",
    "agp_plate": "agp_plate",
    "channels": "channel",
}

#: The modules every generator module's closure holds.
_GENERATOR_CORE = """
    constraints geom geom.rotated_rect law law.airports_schema law.base_profile_schema
    law.basin_schema law.cockpit_schema law.cutout_schema law.design_schema
    law.eat_schema law.flat_pack_schema law.flat_site_schema law.model law.model_types
    law.rebake_schema law.reference_code law.role_cap_schema law.runway_ends_schema
    law.tables law.terrace_schema law.terrain_witness_schema law.tunnel_object_schema
    law.units law.walled_plate_schema law.agp_schema model model.constraints model.frame
    model.planar
    model.registries model.structures
    law.deck_gen_schema
"""

#: The rest of each generator module's import closure, keyed by module.
_GENERATOR_CLOSURES: dict[str, tuple[str, ...]] = {
    "apron": _mods(_GENERATOR_CORE + """
        geom.exact
        constraints.apron constraints.geometry constraints.precedence model.airport
        constraints.cluster_pad constraints.face_index constraints.group_level
        constraints.pad_relief constraints.pad_warning constraints.pads constraints.platform
        constraints.routes constraints.stretches constraints.taxi constraints.taxi_route_yield
        geom.base_slab geom.cluster_outline geom.containment geom.pad_evidence geom.slope_pad
        geom.triangulate geom.union_find model.islands model.map_memo model.platform
    """),
    "channel": _mods(_GENERATOR_CORE + """
        geom.channel_declared
        geom.exact
        constraints.channel constraints.geometry constraints.precedence model.airport
    """),
    "object_floor": _mods(_GENERATOR_CORE + """
        constraints.object_floor geom.lowest_face model.airport
    """),
    "wing_cut": _mods(_GENERATOR_CORE + """
        constraints.wing_cut constraints.edge_floor constraints.geometry geom.exact geom.containment
        model.airport model.platform model.islands model.map_memo model.wing_cut
    """),
    "deck_stack": _mods(_GENERATOR_CORE + """
    model.deck_stack constraints.deck_runout
        geom.deck_ground geom.end_line model.deck_ends
        geom.lowest_face geom.plate_heights
        geom.exact geom.lowest_face
        constraints.contiguity constraints.deck_stack constraints.edge_deck geom.wall_lines
        model.deck_bank
        constraints.edge_floor constraints.deck_lines
        constraints.end_lip constraints.geometry
        constraints.precedence constraints.roads constraints.strips geom.containment
        model.airport model.end_area law.inset_class model.islands model.map_memo model.platform
        model.threshold_datum
    geom.plate_bands geom.union_find
    """),
    "agp_plate": _mods(_GENERATOR_CORE + """
    model.deck_stack
        geom.agp_plate model.agp_plate model.deck_ends geom.end_line
        geom.lowest_face geom.plate_heights
        geom.exact  
        constraints.agp_plate constraints.contiguity constraints.edge_deck geom.wall_lines
        model.deck_bank
        constraints.edge_floor constraints.deck_lines
        constraints.end_lip constraints.geometry
        constraints.precedence constraints.roads constraints.strips geom.containment
        model.airport model.end_area law.inset_class model.islands model.map_memo model.platform
        model.threshold_datum
    geom.plate_bands geom.union_find
    """),
    "eat": _mods(_GENERATOR_CORE + """
        geom.runway_contact
        geom.exact
        constraints.apron constraints.cluster_pad constraints.eat constraints.geometry
        constraints.pad_relief constraints.pad_warning constraints.pads
        constraints.platform constraints.precedence constraints.routes
        constraints.runway_chord constraints.runway_profile constraints.runway_yield
        constraints.runway_junctions
        constraints.threshold_seam
        constraints.shoulder_crossing constraints.stretches constraints.taxi
        constraints.taxi_route_yield constraints.taxi_trend constraints.taxi_trend_cap
        geom.trend
        geom.base_slab geom.cluster_outline geom.containment geom.core_clamp
        geom.pad_evidence geom.triangulate geom.union_find law.inset_class model.airport
        model.islands model.map_memo model.platform
        geom.slope_pad
        constraints.group_level constraints.face_index
        constraints.deck_anchor constraints.edge_floor
        constraints.deck_lines
        model.stage_one
    geom.plate_bands
"""),
    "fill_bank": _mods(_GENERATOR_CORE + """
    geom.agp_plate
    model.deck_stack
        geom.deck_ground
        constraints.fill_bank model.airport
        constraints.contiguity constraints.end_lip constraints.gap_follow
        constraints.geometry constraints.precedence constraints.roads constraints.strips
        geom.containment geom.end_line geom.exact geom.lowest_face geom.plate_heights
        model.deck_ends model.end_area law.inset_class model.islands model.map_memo model.platform
        model.threshold_datum
    model.floor_ground
"""),
    "flat_site": _mods(_GENERATOR_CORE + """
        geom.exact
        constraints.flat_site constraints.geometry constraints.precedence model.airport
    """),
    "foot_rows": _mods(_GENERATOR_CORE + """
    constraints.airside_top
        geom.exact
        constraints.apron constraints.cluster_pad constraints.foot_rows
        constraints.geometry constraints.pad_relief constraints.pad_warning
        constraints.pads constraints.platform constraints.precedence
        constraints.edge_floor constraints.structures
        constraints.airside_floor constraints.survey_floor
        constraints.entrance_skirt
    constraints.viaduct_floor geom.base_slab geom.cluster_outline
        geom.containment
        geom.feet_graph geom.feet_mst geom.pad_evidence geom.triangulate geom.union_find
        model.airport model.ground_fit model.islands model.map_memo model.platform
        geom.slope_pad
        geom.foot_planes model.wall_reach
        constraints.face_index constraints.group_level
        constraints.routes constraints.stretches constraints.taxi constraints.taxi_route_yield
    """),
    "groundside": _mods(_GENERATOR_CORE + """
        geom.exact
        constraints.geometry constraints.groundside constraints.precedence
    """),
    "hard_plane": _mods(_GENERATOR_CORE + """
        constraints.hard_plane model.airport model.hard_plane
    """),
    "steep_apron": _mods(_GENERATOR_CORE + """
        geom.exact
        constraints.apron constraints.cluster_pad constraints.geometry
        constraints.pad_relief constraints.pad_warning constraints.pads
        constraints.platform constraints.precedence constraints.steep_apron
        geom.base_slab geom.cluster_outline
        geom.containment geom.pad_evidence geom.triangulate geom.union_find
        model.airport model.islands model.map_memo model.platform
        geom.slope_pad
        constraints.group_level constraints.face_index
        constraints.routes constraints.stretches constraints.taxi constraints.taxi_route_yield
    """),
    "door_pad": _mods(_GENERATOR_CORE + """
        geom.exact
        constraints.apron constraints.door_pad constraints.geometry constraints.precedence
        geom.slope_pad model.airport
        model.stage_one
        constraints.cluster_pad constraints.face_index constraints.group_level
        constraints.pad_relief constraints.pad_warning constraints.pads constraints.platform
        constraints.routes constraints.stretches constraints.taxi constraints.taxi_route_yield
        geom.base_slab geom.cluster_outline geom.containment geom.pad_evidence geom.triangulate
        geom.union_find model.islands model.map_memo model.platform
    """),
    "junction_mesh": _mods(_GENERATOR_CORE + """
        geom.exact
        constraints.apron constraints.cluster_pad constraints.geometry
        constraints.junction_mesh constraints.pad_relief constraints.pad_warning
        constraints.pads constraints.platform constraints.precedence constraints.routes
        constraints.stretches constraints.taxi geom.base_slab geom.cluster_outline
        geom.containment geom.pad_evidence geom.triangulate geom.union_find
        model.airport model.islands model.map_memo model.platform
        geom.slope_pad
        constraints.group_level constraints.face_index
        constraints.taxi_route_yield
    """),
    "no_step": _mods(_GENERATOR_CORE + """
        geom.runway_contact
        geom.exact
        law.inset_class
        constraints.apron constraints.ceiling constraints.cluster_pad
        constraints.contiguity constraints.end_lip constraints.geometry
        constraints.groundside constraints.no_step constraints.pad_frontage_gs
        constraints.pad_relief constraints.pad_warning constraints.pads
        constraints.platform constraints.precedence constraints.roads constraints.routes
        constraints.runway_profile constraints.shoulder_crossing constraints.stretches
        constraints.threshold_seam
        constraints.strips constraints.transverse geom.trend
        constraints.weld_floor geom.base_slab geom.cluster_outline geom.containment
        geom.pad_evidence geom.triangulate geom.union_find model.airport model.end_area
        law.inset_class
        model.islands model.map_memo model.platform model.threshold_datum
        geom.slope_pad
        constraints.group_level constraints.face_index
        constraints.taxi constraints.taxi_route_yield
    """),
    "pad_frontage_gs": _mods(_GENERATOR_CORE + """
        geom.exact
        constraints.apron constraints.cluster_pad constraints.geometry
        constraints.groundside constraints.pad_frontage_gs constraints.pad_relief
        constraints.pad_warning constraints.pads constraints.platform
        constraints.precedence geom.base_slab geom.cluster_outline geom.containment
        geom.pad_evidence geom.triangulate geom.union_find model.airport model.islands
        model.map_memo model.platform
        geom.slope_pad
        constraints.group_level constraints.face_index
        constraints.routes constraints.stretches constraints.taxi constraints.taxi_route_yield
    """),
    "pad_fronting": _mods(_GENERATOR_CORE + """
        geom.exact geom.parts model.wall_reach
        constraints.apron constraints.cluster_pad constraints.geometry
        constraints.pad_fronting constraints.pad_relief constraints.pad_warning
        constraints.pads constraints.platform constraints.precedence geom.base_slab
        geom.cluster_outline geom.containment geom.pad_evidence geom.triangulate
        geom.union_find model.airport model.islands model.map_memo model.platform
        geom.slope_pad model.wall_reach
        constraints.group_level constraints.face_index
        constraints.routes constraints.stretches constraints.taxi constraints.taxi_route_yield
    """),
    "pads": _mods(_GENERATOR_CORE + """
        geom.exact
        constraints.apron constraints.cluster_pad constraints.geometry
        constraints.pad_relief constraints.pad_warning constraints.pads
        constraints.platform constraints.precedence geom.base_slab geom.cluster_outline
        geom.containment geom.pad_evidence geom.triangulate geom.union_find
        model.airport model.islands model.map_memo model.platform
        geom.slope_pad
        constraints.group_level constraints.face_index
        constraints.routes constraints.stretches constraints.taxi constraints.taxi_route_yield
    """),
    "platform": _mods(_GENERATOR_CORE + """
        geom.exact
        constraints.apron constraints.cluster_pad constraints.geometry
        constraints.pad_relief constraints.pad_warning constraints.pads
        constraints.platform constraints.precedence geom.base_slab geom.cluster_outline
        geom.containment geom.pad_evidence geom.triangulate geom.union_find
        model.airport model.islands model.map_memo model.platform
        geom.slope_pad
        constraints.group_level constraints.face_index
        constraints.routes constraints.stretches constraints.taxi constraints.taxi_route_yield
    """),
    "proximity": _mods(_GENERATOR_CORE + """
        geom.exact
        constraints.contiguity constraints.end_lip constraints.geometry
        constraints.precedence constraints.proximity constraints.roads
        constraints.strips geom.containment model.airport model.end_area law.inset_class
        model.islands
        model.map_memo model.platform model.threshold_datum
    """),
    "ramp_runout": _mods(_GENERATOR_CORE + """
        geom.deck_ground constraints.deck_runout
    constraints.deck_runout constraints.agp_level model.agp_group
        geom.exact
        constraints.wall_zone model.wall_reach constraints.airside_top constraints.edge_floor
        constraints.apron constraints.apron_shelf constraints.cut_kerb constraints.cluster_pad
        constraints.geometry constraints.pad_ramp constraints.pad_relief
        constraints.pad_warning constraints.pads constraints.platform
        constraints.precedence constraints.ramp_runout constraints.road_ramp
        geom.base_slab geom.cluster_outline geom.containment geom.pad_evidence
        geom.ramp_grade geom.ramp_profile geom.triangulate geom.union_find model.airport
        model.islands model.map_memo model.platform
        geom.slope_pad
        constraints.group_level constraints.face_index
        constraints.routes constraints.stretches constraints.taxi constraints.taxi_route_yield
    constraints.contiguity constraints.end_lip constraints.public_road_release constraints.roads
    constraints.strips model.end_area law.inset_class model.threshold_datum
    """),
    "road_ramp": _mods(_GENERATOR_CORE + """
    constraints.deck_runout geom.deck_ground constraints.agp_level model.agp_group
        geom.exact
        constraints.wall_zone model.wall_reach constraints.airside_top constraints.edge_floor
        constraints.apron constraints.apron_shelf constraints.cut_kerb constraints.cluster_pad
        constraints.geometry constraints.pad_relief constraints.pad_warning
        constraints.pads constraints.platform constraints.precedence
        constraints.road_ramp geom.base_slab geom.cluster_outline geom.containment
        geom.pad_evidence geom.ramp_grade geom.triangulate geom.union_find model.airport
        model.islands model.map_memo model.platform
        geom.slope_pad
        constraints.group_level constraints.face_index
        constraints.routes constraints.stretches constraints.taxi constraints.taxi_route_yield
    constraints.contiguity constraints.end_lip constraints.public_road_release constraints.roads
    constraints.strips model.end_area law.inset_class model.threshold_datum
    """),
    "edge_deck": _mods(_GENERATOR_CORE + """
        geom.exact
        constraints.contiguity constraints.edge_deck geom.wall_lines model.deck_bank
        constraints.edge_floor
        constraints.deck_lines
        constraints.end_lip constraints.geometry
        constraints.precedence constraints.roads constraints.strips geom.containment
        model.airport model.end_area law.inset_class model.islands model.map_memo model.platform
        model.threshold_datum
    geom.plate_bands geom.union_find
    """),
    "roads": _mods(_GENERATOR_CORE + """
        geom.exact
        constraints.contiguity constraints.end_lip constraints.geometry
        constraints.precedence constraints.roads constraints.strips geom.containment
        model.airport model.end_area law.inset_class model.islands model.map_memo model.platform
        model.threshold_datum
    """),
    "deck_anchor": _mods(_GENERATOR_CORE + """
        geom.runway_contact
        geom.exact
        law.inset_class
        constraints.apron constraints.cluster_pad constraints.geometry
        constraints.pad_relief constraints.pad_warning constraints.pads
        constraints.platform constraints.precedence constraints.routes
        constraints.runway_chord constraints.runway_profile constraints.runway_yield
        constraints.runway_junctions
        constraints.threshold_seam
        constraints.shoulder_crossing constraints.stretches geom.trend
        geom.base_slab geom.cluster_outline geom.containment geom.pad_evidence
        geom.triangulate geom.union_find model.airport model.islands model.map_memo
        model.platform
        geom.slope_pad
        constraints.group_level constraints.face_index
        constraints.deck_anchor constraints.edge_floor
        constraints.deck_lines
        model.stage_one
        constraints.taxi constraints.taxi_route_yield
    geom.plate_bands
"""),
    "runway_chord": _mods(_GENERATOR_CORE + """
        geom.runway_contact
        geom.exact
        law.inset_class
        constraints.apron constraints.cluster_pad constraints.geometry
        constraints.pad_relief constraints.pad_warning constraints.pads
        constraints.platform constraints.precedence constraints.routes
        constraints.runway_chord constraints.runway_profile constraints.runway_yield
        constraints.runway_junctions
        constraints.threshold_seam
        constraints.shoulder_crossing constraints.stretches geom.trend
        geom.base_slab geom.cluster_outline geom.containment geom.pad_evidence
        geom.triangulate geom.union_find model.airport model.islands model.map_memo
        model.platform
        geom.slope_pad
        constraints.group_level constraints.face_index
        constraints.deck_anchor constraints.edge_floor
        constraints.deck_lines
        model.stage_one
        constraints.taxi constraints.taxi_route_yield
    geom.plate_bands
"""),
    "runway_mean_slope": _mods(_GENERATOR_CORE + """
        geom.runway_contact
        geom.exact
        law.inset_class
        constraints.apron constraints.cluster_pad constraints.geometry
        constraints.pad_relief constraints.pad_warning constraints.pads
        constraints.platform constraints.precedence constraints.routes
        constraints.runway_chord constraints.runway_mean_slope
        constraints.runway_profile constraints.threshold_seam constraints.runway_yield
        constraints.runway_junctions
        constraints.shoulder_crossing constraints.stretches geom.trend
        geom.base_slab geom.cluster_outline geom.containment geom.pad_evidence
        geom.triangulate geom.union_find model.airport model.islands model.map_memo
        model.platform
        geom.slope_pad
        constraints.group_level constraints.face_index
        constraints.deck_anchor constraints.edge_floor
        constraints.deck_lines
        model.stage_one
        constraints.taxi constraints.taxi_route_yield
    geom.plate_bands
"""),
    "runway_profile": _mods(_GENERATOR_CORE + """
        geom.runway_contact
        geom.exact
        law.inset_class
        constraints.geometry constraints.precedence constraints.runway_profile
        constraints.threshold_seam
        constraints.shoulder_crossing geom.trend model.airport
    """),
    "runway_step": _mods(_GENERATOR_CORE + """
        geom.runway_contact
        geom.exact
        law.inset_class
        constraints.geometry constraints.precedence constraints.runway_profile
        constraints.threshold_seam
        constraints.runway_step constraints.shoulder_crossing geom.trend
        model.airport
    """),
    "seams": _mods(_GENERATOR_CORE + """
        constraints.seams model.airport
    """),
    "strips": _mods(_GENERATOR_CORE + """
        geom.exact
        constraints.end_lip constraints.geometry constraints.precedence
        constraints.strips model.airport model.end_area law.inset_class model.threshold_datum
    """),
    "structures": _mods(_GENERATOR_CORE + """
    constraints.airside_top
        geom.exact
        constraints.apron constraints.cluster_pad constraints.geometry
        constraints.pad_relief constraints.pad_warning constraints.pads
        constraints.platform constraints.precedence constraints.edge_floor constraints.structures
        constraints.airside_floor
        constraints.survey_floor
        constraints.entrance_skirt
    constraints.viaduct_floor
        geom.base_slab geom.cluster_outline geom.containment geom.pad_evidence
        geom.triangulate geom.union_find model.airport model.islands model.map_memo
        model.platform
        geom.slope_pad
        constraints.group_level constraints.face_index
        constraints.routes constraints.stretches constraints.taxi constraints.taxi_route_yield
    """),
    "shell_datum": _mods(_GENERATOR_CORE + """
    constraints.airside_top
        geom.exact
        constraints.apron constraints.cluster_pad constraints.geometry
        constraints.pad_relief constraints.pad_warning constraints.pads
        constraints.platform constraints.precedence constraints.edge_floor constraints.structures
        constraints.airside_floor
        constraints.survey_floor constraints.shell_datum
        constraints.entrance_skirt
    constraints.viaduct_floor
        geom.base_slab geom.cluster_outline geom.containment geom.pad_evidence
        geom.triangulate geom.union_find model.airport model.islands model.map_memo
        model.platform
        geom.slope_pad
        constraints.group_level constraints.face_index
        constraints.routes constraints.stretches constraints.taxi constraints.taxi_route_yield
    """),
    "taxi": _mods(_GENERATOR_CORE + """
        geom.exact
        constraints.apron constraints.cluster_pad constraints.geometry
        constraints.pad_relief constraints.pad_warning constraints.pads
        constraints.platform constraints.precedence constraints.routes
        constraints.stretches constraints.taxi geom.base_slab geom.cluster_outline
        geom.containment geom.pad_evidence geom.triangulate geom.union_find
        model.airport model.islands model.map_memo model.platform
        geom.slope_pad
        constraints.group_level constraints.face_index
        constraints.taxi_route_yield
    """),
    "transverse": _mods(_GENERATOR_CORE + """
        geom.exact
        constraints.contiguity constraints.end_lip constraints.geometry
        constraints.precedence constraints.roads constraints.stretches
        constraints.strips constraints.transverse geom.containment model.airport
        model.end_area law.inset_class model.islands model.map_memo model.platform
        model.threshold_datum
        constraints.apron constraints.cluster_pad constraints.face_index constraints.group_level
        constraints.pad_relief constraints.pad_warning constraints.pads constraints.platform
        constraints.routes constraints.taxi constraints.taxi_route_yield geom.base_slab
        geom.cluster_outline geom.pad_evidence geom.slope_pad geom.triangulate geom.union_find
    """),
    "terrain_shaped": _mods(_GENERATOR_CORE + """
        constraints.terrain_shaped geom.terrain_deck model.airport
    """),
    "walled_plate": _mods(_GENERATOR_CORE + """
        geom.exact
        constraints.walled_plate model.airport
    """),
    "water": _mods(_GENERATOR_CORE + """
        geom.exact
        geom.water_level geom.terrain_deck constraints.geometry constraints.precedence
        constraints.water model.airport
    """),
    "road_bridge_ceiling": _mods("""
    constraints constraints.road_bridge_ceiling law law.agp_schema
    law.airports_schema law.base_profile_schema law.basin_schema law.cockpit_schema
    law.cutout_schema law.deck_gen_schema law.design_schema law.eat_schema
    law.flat_pack_schema law.flat_site_schema law.model law.model_types law.rebake_schema
    law.reference_code law.role_cap_schema law.runway_ends_schema law.tables
    law.terrace_schema law.terrain_witness_schema law.tunnel_object_schema law.units
    law.walled_plate_schema model model.constraints model.road_clearance
"""),
    "zones": _mods(_GENERATOR_CORE + """
        geom.exact
        constraints.contiguity constraints.end_lip constraints.geometry
        constraints.precedence constraints.roads constraints.strips constraints.zones
        geom.containment model.airport model.end_area law.inset_class model.islands model.map_memo
        model.platform model.threshold_datum
    """),
}
CODE_MODULES["constraints.assembly"] = _mods("""
    geom.channel_declared
    airport.cut_portal_seat
    airport.hung_wall_seat airport.wall_top
    airport.floor_rim airport.object_floor airport.walled_pit geom.shape_class geom.plane_groups
    geom.line_walk
    constraints.agp_plate geom.agp_plate model.agp_plate
    constraints.deck_runout constraints.agp_level law.agp_schema model.agp_group
    model.deck_stack
    airport.hanging_objects airport.object_cut airport.split_level airport.split_level_wings
    airport.wall_geometry
    geom.vector
    airport.facade airport.line_solidity classify.edge_line_mint
    constraints.yard_edge model.yard_run
    classify.fence_yard classify.floor_yard geom.capped_plane
    constraints.deck_stack geom.deck_ground geom.end_line model.deck_ends
    geom.lowest_face geom.plate_heights
    airport.pit_frame
    constraints.airside_top
    geom.runway_contact
    constraints.fill_bank
    constraints.object_floor geom.lowest_face
    geom.exact
        law.runway_ends_schema law.terrain_witness_schema
    airport classify model pipeline planar airport.anchor_rule airport.apt_dat
    airport.apt_flatten
    airport.authored_landing airport.authored_seat airport.backup_state
    airport.basin_ring airport.basin_witness airport.borrow airport.bridge_family
    airport.deck_touch airport.interior_deck
    airport.bulk_geos airport.cluster_profile airport.contact airport.contents
    airport.deck_signature airport.dem geom.water_level airport.dem_witness airport.dsf
    airport.deck_family_contact
    airport.extension_cache airport.file_hash airport.footprint_carry
    airport.footprint_connector airport.footprint_seats airport.footprint_unit airport.one_building
    airport.level_base
    airport.frame_entry airport.jetways airport.line_object
    airport.airside_floor airport.msl_feet airport.obj8
    airport.terrain_feature airport.terrain_model airport.terrain_shell
    airport.bridged_ground airport.ground_shell
    airport.relief_skin airport.file_verdict
    airport.free_column airport.rider_floor
    airport.isolated_seat airport.terrain_base geom.diameter
    airport.terrain_shaped airport.pack_ground geom.terrain_deck
    airport.obj8_clip airport.obj8_drape airport.obj8_grade airport.obj8_roof
    airport.obj8_split airport.obj8_warp airport.deck_profile
    airport.deck_track_bend
    airport.obj8_rest airport.obj8_memo airport.pack_health airport.pack_health.light_records
    airport.pack airport.pack_partition airport.adapted_riders airport.pack_work
    airport.object_pack airport.pack_local
    airport.pack_art airport.pack_choice airport.pack_terrain
    airport.pad_block_seat airport.partition_cache airport.partition_code
    airport.placement_atom
    airport.drawn_anchor airport.exclusion
    airport.placement_body airport.placement_boxes
    airport.placement_carrier airport.placement_census airport.placement_cockpit
    airport.placement_contact airport.placement_cut airport.placement_deck
    airport.placement_family airport.placement_file airport.placement_geom
    airport.placement_leaves airport.placement_motion airport.placement_orphan
    airport.placement_plan
    airport.airside_deck_seat airport.airside_group_seat airport.cut_deck_seat
     airport.entrance_seat airport.split_guard
    airport.bridge_approach airport.deck_carry airport.deck_end_read airport.deck_riders
    airport.bridge_axis airport.bridge_witness airport.deck_surface geom.centreline
    airport.free_bridge_seat
    airport.open_frame_seat airport.pad_level_group
    airport.placement_read airport.placement_record
    airport.placement_seams airport.placement_seat_tilt airport.placement_targets
    airport.pool airport.pool_memory airport.pool_slots airport.rebake_plan airport.deck_plane_ring
    airport.pack_patch_witness airport.riders airport.ring_contact_batch
    airport.road_ways airport.scatter
    airport.sheet_chain airport.skirt airport.slab_faces airport.slab_plates
    airport.topology_cache airport.sunken_ramp airport.wall_class airport.sunk_frame
    airport.wall_sheets
    classify.airside_edge classify.evidence
    classify.apt_shoulder classify.blast_pad classify.storey_edge airport.unit_storey
    airport.user_roles
    classify.facade_mint classify.frontage_road geom.lens geom.many_buffers
    classify.car_lot
    classify.gap_apron classify.fence_division classify.gap_band
    classify.gap_mint classify.gap_stands
    classify.lot_roads
    classify.neck classify.neck_road classify.open_default
    classify.pad_cut_corridor classify.pad_sunk classify.pad_touch classify.retaining_wall
    airport.wall_sides classify.wall_cutback model.wall_reach
    classify.ribbon_mint classify.roles classify.rules classify.sources
    classify.end_pad classify.island_spurs classify.wrap_page
    classify.taxi_letter classify.taxi_shoulder
     classify.wall_clip constraints constraints.apron constraints.apron_shelf constraints.cut_kerb
    constraints.assembly constraints.ceiling constraints.channel constraints.cluster_pad
    constraints.contiguity constraints.eat
    constraints.edge_deck geom.wall_lines model.deck_bank constraints.end_lip constraints.flat_site
    constraints.foot_rows constraints.geometry constraints.groundside
    constraints.hard_plane constraints.steep_apron constraints.junction_mesh constraints.no_step
    constraints.pad_frontage_gs constraints.pad_fronting constraints.pad_ramp
    constraints.pad_sunk_level
    constraints.pad_relief constraints.pad_warning constraints.pads
    constraints.pavement_cap constraints.platform constraints.precedence
    constraints.public_road_release
    constraints.proximity constraints.ramp_runout constraints.shell_datum
    constraints.riser constraints.road_ramp
    constraints.roads constraints.routes constraints.runway_chord
    constraints.runway_mean_slope constraints.runway_profile constraints.runway_step
    constraints.threshold_seam
    constraints.runway_yield constraints.runway_junctions
    constraints.seams constraints.shoulder_crossing constraints.stretches
    constraints.strips constraints.edge_floor constraints.structures
        constraints.airside_floor constraints.survey_floor
    constraints.entrance_skirt
    constraints.viaduct_floor constraints.taxi
    constraints.deck_lines
    constraints.taxi_trend
    constraints.taxi_trend_cap constraints.transverse geom.trend
    constraints.water constraints.weld_floor constraints.zones geom geom.base_slab
    geom.fixed_overlay
    geom.valid_area
    geom.cluster_outline geom.containment geom.core_clamp geom.feet_graph geom.feet_mst
    geom.pad_evidence geom.parts geom.proportions geom.ramp_grade geom.ramp_profile
    geom.rotated_rect geom.triangulate geom.union_find law law.airports_schema
    law.base_profile_schema law.basin_schema law.cockpit_schema law.cutout_schema
    law.design_schema law.eat_schema law.flat_pack_schema
    law.flat_site_schema law.inset_class law.model
    law.model_types law.rebake_schema law.reference_code airport.runway_strip
    law.role_cap_schema law.tables
    law.terrace_schema law.tunnel_object_schema law.units model.airport
    model.constraints model.end_area law.inset_class model.frame model.ground_fit model.hard_plane
    model.islands model.map_memo model.placement model.planar model.platform model.pulse
    model.rebake model.registries model.structures model.threshold_datum pipeline.shapes
    planar.shape_airside planar.shape_mouths
    planar.shape_pad_corner planar.shape_parts planar.shapes
    planar.strip_keepout
    classify.reachability
    constraints.door_pad
    geom.slope_pad
    constraints.wall_zone
    geom.foot_planes constraints.face_index constraints.group_level
    model.stage_one
    airport.pavement_end_plate
    airport.walled_plate constraints.walled_plate constraints.terrain_shaped
    airport.zero_level_seat
    law.walled_plate_schema model.walled_plate
    constraints.deck_anchor
    constraints.taxi_route_yield
    airport.below_grade_witness airport.shell_ground geom.author_ground
    model.free_bridge
    constraints.wing_cut model.wing_cut
    constraints.bridge_span_release
    airport.access_road airport.agp_deck_ends airport.agp_deck_join airport.agp_floors
    airport.agp_gap_plates airport.agp_ground airport.agp_group airport.agp_pieces
    airport.agp_plan airport.agp_plates airport.apt_edit airport.bridge_end_state
    airport.bridge_frame airport.bridge_stack airport.deck_ends airport.deck_stack
    airport.agp_foot_pads airport.floor_deck_ends airport.stack_end_seat
    airport.dsf_heights airport.facade_seat airport.ground_route_ways airport.stack_walls
    airport.touch_graph airport.touch_seat constraints.gap_follow law.deck_gen_schema
    airport.connector_warp airport.stacked_deck airport.tilt_float airport.split_bar
    airport.deck_plates airport.obj8_band classify.apron_gate geom.plate_bands model.floor_ground
    constraints.road_bridge_ceiling model.road_clearance
    model.clocks
""")
CODE_MODULES["jetway_strip"] = _mods("""
    airport.cut_portal_seat
    airport.facade airport.hung_wall_seat airport.line_solidity airport.sunken_ramp
    airport.wall_class airport.sunk_frame
    airport.wall_sheets airport.wall_sides airport.wall_top model.wall_reach
    airport.floor_rim airport.object_floor airport.walled_pit geom.shape_class geom.plane_groups
    geom.line_walk
    airport.below_grade_witness airport.hanging_objects airport.object_cut
    airport.shell_ground airport.wall_geometry geom.author_ground geom.vector
    law.agp_schema
    airport.pit_frame
    geom.runway_contact
    geom.exact
        law.inset_class law.runway_ends_schema law.terrain_witness_schema
    airport constraints model airport.anchor_rule airport.apt_dat
    airport.apt_flatten
    airport.authored_landing airport.authored_seat airport.backup_state
    airport.basin_ring airport.basin_witness airport.borrow airport.bridge_family
    airport.deck_touch airport.interior_deck
    airport.bulk_geos airport.cluster_profile airport.contact airport.contents
    airport.deck_signature airport.dem_witness airport.dsf airport.extension_cache
    airport.deck_family_contact
    airport.file_hash airport.footprint_carry airport.footprint_connector
    airport.footprint_seats airport.footprint_unit airport.one_building airport.frame_entry
    airport.level_base
    airport.line_object airport.airside_floor airport.msl_feet airport.obj8
    airport.terrain_feature airport.terrain_model airport.terrain_shell
    airport.bridged_ground airport.ground_shell
    airport.relief_skin airport.file_verdict
    airport.free_column airport.rider_floor
    airport.isolated_seat airport.terrain_base geom.diameter
    airport.terrain_shaped airport.pack_ground geom.terrain_deck
    airport.obj8_clip airport.obj8_drape
    airport.obj8_grade airport.obj8_roof airport.obj8_split airport.obj8_warp airport.deck_profile
    airport.deck_track_bend
    airport.obj8_rest airport.obj8_memo airport.pack_health airport.pack_health.light_records
    airport.pack
    airport.object_pack airport.pack_local
    airport.pack_art airport.pack_choice airport.pack_terrain
    airport.pack_partition airport.adapted_riders airport.pack_work airport.pad_block_seat
    airport.partition_cache airport.partition_code airport.placement_atom
    airport.drawn_anchor airport.exclusion
    airport.placement_body airport.placement_boxes airport.placement_carrier
    airport.placement_census airport.placement_cockpit airport.placement_contact
    airport.placement_cut airport.placement_deck airport.placement_family
    airport.placement_file airport.placement_geom airport.placement_leaves
    airport.placement_motion airport.placement_orphan airport.placement_plan
    airport.airside_deck_seat airport.airside_group_seat airport.cut_deck_seat
     airport.entrance_seat airport.split_guard
    airport.bridge_approach airport.deck_carry airport.deck_end_read airport.deck_riders
    airport.bridge_axis airport.bridge_witness airport.deck_surface geom.centreline
    airport.free_bridge_seat
    geom.lowest_face airport.open_frame_seat airport.pad_level_group
    airport.placement_read airport.placement_record airport.placement_seams
    airport.placement_seat_tilt airport.placement_targets airport.pool airport.pool_memory
    airport.pool_slots
    airport.rebake_plan airport.deck_plane_ring airport.pack_patch_witness airport.riders
    airport.ring_contact_batch airport.scatter airport.sheet_chain airport.skirt
    airport.slab_faces airport.slab_plates airport.topology_cache constraints.apron
    constraints.ceiling constraints.cluster_pad constraints.contiguity
    constraints.end_lip constraints.geometry constraints.groundside
    constraints.jetway_strip constraints.no_step constraints.pad_frontage_gs
    constraints.pad_relief constraints.pad_warning constraints.pads constraints.platform
    constraints.precedence constraints.roads constraints.routes
    constraints.runway_profile constraints.shoulder_crossing constraints.stretches
    constraints.threshold_seam
    constraints.strips constraints.transverse geom.trend constraints.weld_floor
    geom geom.base_slab geom.cluster_outline geom.containment geom.pad_evidence geom.parts
    geom.rotated_rect geom.triangulate geom.union_find law law.airports_schema
    law.base_profile_schema law.basin_schema law.cockpit_schema law.cutout_schema
    law.design_schema law.eat_schema law.flat_pack_schema
    law.flat_site_schema law.model law.model_types
    law.rebake_schema law.reference_code law.role_cap_schema law.tables
    law.terrace_schema law.tunnel_object_schema law.units model.airport
    model.constraints model.end_area law.inset_class model.frame model.islands model.jetway
    model.map_memo model.placement model.planar model.platform model.pulse model.rebake
    model.registries model.structures model.threshold_datum
    geom.slope_pad
    geom.foot_planes constraints.group_level constraints.face_index
    airport.pavement_end_plate
    airport.dem airport.walled_plate law.walled_plate_schema model.walled_plate
    airport.zero_level_seat
    constraints.taxi constraints.taxi_route_yield
    model.free_bridge
    airport.apt_edit airport.touch_graph airport.touch_seat law.deck_gen_schema
    airport.connector_warp airport.stacked_deck airport.tilt_float airport.split_bar
    airport.deck_plates airport.obj8_band geom.plate_bands model.floor_ground
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
    geom.deck_spans planar.deck_span_cut planar.route_lines
    planar.channel_ramp
    airport.cut_portal airport.cut_portal_seat
    airport.hung_wall_seat airport.wall_top
    constraints.airside_top
    airport.facade_seat
    airport.access_road airport.agp_plates geom.agp_plate model.agp_plate planar.agp_ground
    planar.bank_cut planar.pit_bank planar.deck_skirt
    airport.agp_deck_ends airport.agp_deck_join
    airport.agp_floors airport.agp_ground airport.agp_group airport.agp_pieces
    constraints.deck_runout constraints.agp_level law.agp_schema model.agp_group
    airport.bridge_end_state airport.bridge_stack
    airport.dsf_heights airport.facade airport.line_solidity classify.edge_line_mint
    model.yard_run geom.slope_bound
    classify.fence_yard classify.floor_yard geom.capped_plane solve.project_yard
    airport.deck_carry airport.deck_stack airport.stack_walls model.deck_stack
    airport.agp_foot_pads airport.floor_deck_ends airport.stack_end_seat
    airport.deck_ends geom.deck_ground geom.end_line model.deck_ends planar.stack_ground
    geom.lowest_face geom.plate_heights
    airport.walled_pit geom.line_walk airport.portal_floor airport.pit_frame
    geom.runway_contact geom.collapsed_spike
    airport.old_dem_fill planar.fill_bank
    geom.plane_groups geom.shape_class planar.floor_decks
    airport.object_floor airport.floor_rim geom.author_ground geom.lowest_face
    planar.object_floor_cells airport.walled_trench
    airport.visible_cut planar.channel_depth
    pipeline.lot_follow solve.follow_stage
    geom.exact
        law.runway_ends_schema law.terrain_witness_schema
    airport classify constraints model pipeline planar solve airport.anchor_rule
    airport.apt_dat airport.authored_landing airport.authored_seat airport.backup_state
    airport.apt_flatten
    airport.basin_ring airport.basin_witness airport.below_zero airport.borrow
    airport.deck_touch airport.interior_deck
    airport.bridge_family airport.bulk_geos airport.cluster_profile airport.contact
    airport.contents airport.deck_signature airport.dem geom.water_level airport.dem_production
    airport.deck_family_contact
    airport.dem_record airport.dem_shared airport.dem_witness airport.door_wells
    airport.dsf airport.extension_cache airport.file_hash airport.file_witness
    airport.footprint_carry airport.footprint_connector airport.footprint_seats
    airport.footprint_unit airport.level_base
    airport.one_building airport.frame_entry airport.grade_ledger airport.jetways
    airport.line_object airport.airside_floor airport.msl_feet airport.obj8
    airport.terrain_feature airport.terrain_model airport.terrain_shell
    airport.bridged_ground airport.ground_shell
    airport.relief_skin airport.file_verdict
    airport.free_column airport.rider_floor
    airport.terrain_shaped airport.pack_ground geom.terrain_deck
    airport.obj8_clip airport.obj8_drape
    airport.obj8_grade airport.obj8_roof
    airport.below_grade_witness
    airport.obj8_split airport.obj8_warp airport.deck_profile
    airport.deck_track_bend
    airport.obj8_rest airport.obj8_memo airport.pack_health airport.pack_health.light_records
    airport.object_cut airport.hanging_objects
    airport.adapted_riders
    airport.pack airport.pack_partition airport.pack_work airport.pad_block_seat
    airport.object_pack airport.pack_local
    airport.pack_art airport.pack_choice airport.pack_terrain
    airport.partition_cache airport.partition_code airport.placement_atom
    airport.drawn_anchor airport.exclusion
    airport.placement_body airport.placement_boxes airport.placement_carrier
    airport.placement_census airport.placement_cockpit airport.placement_contact
    airport.placement_cut airport.placement_deck airport.placement_family
    airport.placement_file airport.placement_geom airport.placement_leaves
    airport.placement_motion airport.placement_orphan airport.placement_plan
    airport.airside_deck_seat airport.airside_group_seat airport.cut_deck_seat
     airport.entrance_seat airport.split_guard
    airport.bridge_approach airport.deck_end_read airport.deck_riders
    airport.deck_surface airport.free_bridge_seat
    airport.open_frame_seat airport.pad_level_group
    airport.placement_read airport.placement_record airport.placement_seams
    airport.placement_seat_tilt airport.placement_targets airport.plate_frame
    airport.plate_ground airport.pool airport.pool_memory airport.pool_slots
    airport.ramp_feet
    airport.reader_work airport.rebake_plan airport.deck_plane_ring airport.pack_patch_witness
    airport.riders airport.road_profile
    airport.road_stations airport.road_ways airport.scatter airport.sheet_chain airport.skirt
    airport.deck_roof
    airport.split_level airport.split_level_forecourt airport.split_level_wings
    airport.ring_contact_batch
    airport.slab_faces airport.slab_plates airport.stage_cache airport.sunken_ramp
    airport.sunken_roads airport.thin_plates airport.topology_cache
    airport.trench_objects
    airport.tunnel_objects airport.portal_objects airport.footed_portal
    airport.tunnel_walls airport.wall_class airport.sunk_frame
    airport.wall_sheets
    airport.wall_corridor_probe airport.wall_corridors airport.wall_family
    airport.wall_geometry airport.wall_mouth classify.airside_edge classify.evidence
    classify.apt_shoulder classify.blast_pad classify.storey_edge airport.unit_storey
    airport.user_roles
    classify.facade_mint classify.frontage_road geom.lens geom.many_buffers
    classify.car_lot
    classify.gap_apron classify.fence_division classify.gap_band
    classify.gap_mint classify.gap_stands
    classify.lot_roads
    classify.neck classify.neck_road classify.open_default
    classify.pad_cut_corridor classify.pad_sunk classify.pad_touch classify.ramp_runout
    classify.retaining_wall
    airport.wall_sides classify.wall_cutback model.wall_reach
    classify.ribbon_mint classify.roles classify.rules
    classify.end_pad classify.island_spurs classify.wrap_page
    classify.sources classify.taxi_letter classify.taxi_shoulder
     classify.wall_clip constraints.apron
    constraints.apron_shelf constraints.cut_kerb
    constraints.ceiling constraints.cluster_pad constraints.contiguity
    constraints.end_lip constraints.geometry constraints.groundside constraints.no_step
    constraints.pad_frontage_gs constraints.pad_relief constraints.pad_warning
    constraints.pads constraints.platform constraints.precedence constraints.road_ramp
    constraints.roads constraints.routes constraints.runway_chord
    constraints.runway_profile constraints.runway_yield constraints.runway_junctions
    constraints.shoulder_crossing
    constraints.threshold_seam
    constraints.stretches constraints.strips constraints.taxi constraints.taxi_trend
    constraints.taxi_trend_cap constraints.transverse geom.trend
    constraints.weld_floor geom geom.base_slab geom.cluster_outline geom.containment
    geom.core_clamp geom.coverage geom.grid_pickle geom.pad_evidence geom.parts geom.proportions
    geom.ramp_grade geom.ramp_profile geom.rotated_rect geom.triangulate geom.union_find
    geom.vector law law.airports_schema law.approach_corridor law.base_profile_schema
    law.basin_schema law.cockpit_schema law.cutout_schema law.design_schema
    law.eat_schema law.flat_pack_schema
    law.flat_site_schema law.inset_class law.model law.model_types
    law.rebake_schema law.reference_code airport.runway_strip law.role_cap_schema law.tables
    law.terrace_schema law.tunnel_object_schema law.units model.airport
    model.constraints model.end_area law.inset_class model.frame model.hard_plane model.islands
    model.jetway model.map_memo model.pad_terrace model.placement model.planar
    model.platform model.pulse model.rebake model.registries model.structures
    model.threshold_datum pipeline.back_cache pipeline.capture_state
    pipeline.solve_record pipeline.stage_one_map planar.apron_shelf
    planar.basin_datum planar.basin_floor_width
    planar.basin_geometry planar.basin_rim planar.basins planar.bore_continuation
    planar.build planar.channel
    planar.pinned_span
    planar.channel_claims planar.channel_floor planar.channel_geometry planar.channel_stretch
    planar.channel_strip planar.channel_building
    planar.bridge_span planar.channel_witness planar.chords planar.covered_bores
    planar.covered_cut planar.covered_ground planar.cut_runout planar.deck_bores
    geom.station_runs airport.bridge_ground airport.road_bridge_ground
    airport.bore_ground airport.object_ground
    airport.terrain_cut
    planar.cut_frame planar.deck_bridge planar.deck_walls geom.wall_lines model.deck_bank
    planar.deck_route
    planar.door_ramps planar.dual_width planar.edges planar.end_barriers planar.end_witness
    planar.landing
    planar.landing_runout planar.level_depth planar.level_regions planar.level_underside
    planar.lidar_road planar.low_level planar.object_corridor planar.overlay planar.overpass_deck
    planar.pack_reads geom.pad_base_slope planar.pad_blocks planar.pad_cut planar.pad_fill
    planar.pad_sliver planar.pad_terrace planar.passage_court planar.plate_bays planar.platform
    planar.ribbon_weld planar.ribbons
    planar.ridge_reach planar.road_yield planar.shape_airside planar.shape_mouths
    planar.shape_pad_corner
    planar.shape_parts planar.shapes planar.shore planar.station_level planar.strip_keepout
    planar.split_level_pit
    planar.structure_approach planar.structure_deck planar.structure_fence
    planar.structure_geometry
    planar.structure_overlap planar.structure_pair planar.structure_road
    planar.structure_mouth planar.underpass_mouth planar.survey_cut planar.structure_service
    planar.survey_deck_cut planar.grade_separation model.grade_separation
    planar.structure_stats
    planar.structure_underpass planar.structures planar.entrance_skirt planar.terrain_edge
    planar.mouth_behind planar.mouth_opening
    planar.unframed_ramp planar.viaduct_road
    planar.wall_corridor_ramps planar.wall_slope planar.weld planar.zones solve.api
    solve.design solve.design_assemble solve.design_edge solve.design_ground
    solve.design_junction solve.design_qp solve.design_report solve.design_roles
    solve.design_stage solve.feasibility solve.fill_order solve.flex solve.linear solve.pin_yield
    solve.project solve.project_strip solve.round_normal solve.rows solve.runway_first
    solve.wall_cut solve.warm_seed
    classify.reachability
    planar.zone_pass
    geom.fixed_overlay
    geom.valid_area
    constraints.door_pad
    geom.slope_pad
    planar.fill_road planar.fill_riser
    model.road_yield planar.road_shadow
    constraints.wall_zone
    geom.foot_planes constraints.group_level constraints.face_index planar.group_low planar.group_up
    airport.pavement_end_plate
    airport.walled_plate law.walled_plate_schema model.stage_one model.walled_plate
    airport.zero_level_seat
    planar.low_extent planar.low_fill planar.reach_after_pads planar.reach_under_covers
    constraints.deck_anchor constraints.edge_floor
    constraints.deck_lines
    constraints.taxi_route_yield
    airport.foot_lot
    planar.foot_kerb planar.ground_chords airport.road_descent
    airport.isolated_seat airport.terrain_base geom.diameter
    model.storey_shell planar.cell_knife planar.storey_pad planar.storey_floor
    airport.shell_ground planar.basin_author_ground
    airport.bridge_axis airport.bridge_class airport.bridge_frame
    airport.bridge_witness geom.centreline
    model.free_bridge planar.free_bridge airport.ground_route_ways
    planar.front_band airport.entrance_front planar.ramp_carry planar.deck_runout
    planar.wing_cut model.wing_cut airport.mouth_group airport.ramp_wing airport.wall_lines
    planar.mouth_behind
    airport.agp_gap_plates airport.agp_plan airport.apt_edit airport.touch_graph
    airport.touch_seat law.deck_gen_schema planar.deck_generated planar.short_bore
    airport.connector_warp airport.stacked_deck airport.tilt_float airport.split_bar
    planar.deck_pack_cover planar.deck_takeover
    airport.deck_plates airport.obj8_band classify.apron_gate constraints.public_road_release
    geom.plate_bands model.floor_ground planar.road_wall_witness
    model.road_clearance
    model.clocks
""")
CODE_MODULES["late_cut"] = CODE_MODULES["late_solve"] = _mods("""
    pipeline.registry_writes
    geom.deck_spans planar.deck_span_cut planar.route_lines
    pipeline.late_view
    geom.channel_declared planar.channel_ramp
    airport.cut_portal airport.cut_portal_seat
    airport.hung_wall_seat airport.wall_top
    airport.facade_seat
    airport.access_road airport.agp_plates constraints.agp_plate geom.agp_plate
    model.agp_plate planar.agp_ground
    planar.bank_cut planar.pit_bank planar.deck_skirt
    airport.agp_deck_ends airport.agp_deck_join
    airport.agp_floors airport.agp_ground airport.agp_group airport.agp_pieces
    constraints.deck_runout constraints.agp_level law.agp_schema model.agp_group
    airport.bridge_end_state airport.bridge_stack
    airport.dsf_heights airport.facade airport.line_solidity classify.edge_line_mint
    constraints.yard_edge model.yard_run geom.slope_bound
    classify.fence_yard classify.floor_yard geom.capped_plane solve.project_yard
    airport.deck_carry airport.deck_stack airport.stack_walls model.deck_stack
    airport.agp_foot_pads airport.floor_deck_ends airport.stack_end_seat
    airport.deck_ends geom.deck_ground geom.end_line model.deck_ends planar.stack_ground
    geom.lowest_face geom.plate_heights
    constraints.deck_stack
    airport.walled_pit geom.line_walk airport.portal_floor airport.pit_frame constraints.airside_top
    geom.runway_contact geom.collapsed_spike
    airport.old_dem_fill constraints.fill_bank planar.fill_bank
    geom.plane_groups geom.shape_class planar.floor_decks
    airport.object_floor airport.floor_rim constraints.object_floor
    planar.object_floor_cells airport.walled_trench
    geom.author_ground geom.lowest_face
    airport.visible_cut planar.channel_depth
    solve.follow_stage
    geom.exact
        law.runway_ends_schema law.terrain_witness_schema
    airport classify emit model pipeline planar solve airport.anchor_rule
    airport.apt_dat airport.authored_landing airport.authored_seat airport.backup_state
    airport.apt_flatten
    airport.basin_ring airport.basin_witness airport.below_zero airport.borrow
    airport.deck_touch airport.interior_deck
    airport.bridge_family airport.bulk_geos airport.cluster_profile airport.contact
    airport.contents airport.deck_signature airport.dem geom.water_level airport.dem_production
    airport.deck_family_contact
    airport.dem_record airport.dem_shared airport.dem_witness airport.door_wells
    airport.dsf airport.extension_cache airport.file_hash airport.file_witness
    airport.footprint_carry airport.footprint_connector airport.footprint_seats
    airport.footprint_unit airport.level_base
    airport.one_building airport.frame_entry airport.grade_ledger airport.jetways
    airport.line_object airport.airside_floor airport.msl_feet airport.obj8
    airport.terrain_feature airport.terrain_model airport.terrain_shell
    airport.bridged_ground airport.ground_shell
    airport.relief_skin airport.file_verdict
    airport.free_column airport.rider_floor
    airport.terrain_shaped airport.pack_ground geom.terrain_deck
    airport.obj8_clip airport.obj8_drape
    airport.obj8_grade airport.obj8_roof
    airport.below_grade_witness
    airport.obj8_split airport.obj8_warp airport.deck_profile
    airport.deck_track_bend
    airport.obj8_rest airport.obj8_memo airport.pack_health airport.pack_health.light_records
    airport.object_cut airport.hanging_objects
    airport.adapted_riders
    airport.pack airport.pack_partition airport.pack_work airport.pad_block_seat
    airport.object_pack airport.pack_local
    airport.pack_art airport.pack_choice airport.pack_terrain
    airport.partition_cache airport.partition_code airport.placement_atom
    airport.drawn_anchor airport.exclusion
    airport.placement_body airport.placement_boxes airport.placement_carrier
    airport.placement_census airport.placement_cockpit airport.placement_contact
    airport.placement_cut airport.placement_deck airport.placement_family
    airport.placement_file airport.placement_geom airport.placement_leaves
    airport.placement_motion airport.placement_orphan airport.placement_plan
    airport.airside_deck_seat airport.airside_group_seat airport.cut_deck_seat
     airport.entrance_seat airport.split_guard
    airport.bridge_approach airport.deck_end_read airport.deck_riders
    airport.deck_surface airport.free_bridge_seat
    airport.open_frame_seat airport.pad_level_group
    airport.placement_read airport.placement_record airport.placement_seams
    airport.placement_seat_tilt airport.placement_targets airport.plate_frame
    airport.plate_ground airport.pool airport.pool_memory airport.pool_slots
    airport.ramp_feet
    airport.reader_work airport.rebake_plan airport.deck_plane_ring airport.pack_patch_witness
    airport.riders airport.road_profile
    airport.road_stations airport.road_ways airport.scatter airport.sheet_chain airport.skirt
    airport.deck_roof
    airport.split_level airport.split_level_forecourt airport.split_level_wings
    airport.ring_contact_batch
    airport.slab_faces airport.slab_plates airport.stage_cache airport.sunken_ramp
    airport.sunken_roads airport.thin_plates airport.topology_cache
    airport.trench_objects
    airport.tunnel_objects airport.portal_objects airport.footed_portal
    airport.tunnel_walls airport.wall_class airport.sunk_frame
    airport.wall_sheets
    airport.wall_corridor_probe airport.wall_corridors airport.wall_family
    airport.wall_geometry airport.wall_mouth classify.airside_edge classify.evidence
    classify.apt_shoulder classify.blast_pad classify.storey_edge airport.unit_storey
    airport.user_roles
    classify.facade_mint classify.frontage_road geom.lens geom.many_buffers
    classify.car_lot
    classify.gap_apron classify.fence_division classify.gap_band
    classify.gap_mint classify.gap_stands
    classify.gap_terrace
    classify.lot_roads classify.neck classify.neck_road classify.open_default classify.pad_road_exit
    classify.pad_cut_corridor classify.pad_sunk classify.pad_touch
    classify.ramp_runout classify.retaining_wall
    airport.wall_sides classify.wall_cutback model.wall_reach classify.ribbon_mint
    classify.roles classify.rules classify.sources classify.taxi_letter classify.taxi_shoulder
    classify.end_pad classify.island_spurs classify.wrap_page
     classify.wall_clip
    constraints
    constraints.apron constraints.apron_shelf constraints.cut_kerb
    constraints.assembly constraints.ceiling
    constraints.channel constraints.cluster_pad constraints.contiguity constraints.eat
    constraints.edge_deck geom.wall_lines model.deck_bank
    constraints.end_lip constraints.flat_site constraints.foot_road constraints.foot_rows
    constraints.gap_follow constraints.geometry constraints.groundside
    constraints.hard_plane constraints.steep_apron constraints.jetway_strip
    constraints.junction_mesh
    constraints.no_step constraints.pad_frontage_gs constraints.pad_fronting
    constraints.pad_ramp constraints.pad_relief constraints.pad_road_reach
    constraints.pad_warning constraints.pads constraints.pavement_cap
    constraints.public_road_release
    constraints.platform constraints.precedence constraints.proximity
    constraints.ramp_runout constraints.shell_datum
    constraints.riser constraints.road_ramp constraints.roads constraints.routes
    constraints.runway_chord constraints.runway_mean_slope constraints.runway_profile
    constraints.threshold_seam
    constraints.runway_step
    constraints.runway_yield constraints.runway_junctions constraints.seams
    constraints.shoulder_crossing
    constraints.slab_weld constraints.stretches constraints.strips
    constraints.edge_floor constraints.structures
        constraints.airside_floor constraints.survey_floor
    constraints.entrance_skirt
    constraints.viaduct_floor constraints.taxi constraints.taxi_trend
    constraints.deck_lines
    constraints.taxi_trend_cap constraints.transverse geom.trend
    constraints.water constraints.weld_floor constraints.zones emit.graded emit.surface
    geom geom.base_slab geom.cluster_outline geom.containment geom.core_clamp
    geom.coverage geom.grid_pickle geom.feet_graph geom.feet_mst geom.pad_evidence geom.parts
    geom.proportions geom.ramp_grade geom.ramp_profile geom.rotated_rect
    geom.triangulate geom.union_find geom.vector law law.airports_schema
    law.approach_corridor law.base_profile_schema law.basin_schema law.cockpit_schema
    law.cutout_schema law.design_schema law.eat_schema law.flat_pack_schema law.flat_site_schema
    law.inset_class law.model law.model_types law.rebake_schema law.reference_code
    airport.runway_strip
    law.role_cap_schema law.tables law.terrace_schema law.tunnel_object_schema law.units
    model.airport model.constraint_codec model.constraints model.end_area law.inset_class
    model.frame
    model.ground_fit model.hard_plane model.islands model.jetway model.map_memo
    model.pad_terrace model.placement model.planar model.platform model.pulse
    model.rebake model.registries model.structures model.threshold_datum
    pipeline.back_cache pipeline.capture_state pipeline.constraint_records
    pipeline.car_lot_stage constraints.car_lot_follow
    pipeline.late_records pipeline.late_stage pipeline.shapes pipeline.solve_record
    pipeline.stage_code pipeline.stage_one_map planar.apron_shelf
    planar.basin_datum planar.basin_floor_width
    planar.basin_geometry planar.basin_rim planar.basins planar.bore_continuation
    planar.build planar.channel
    planar.pinned_span
    planar.channel_claims planar.channel_floor planar.channel_geometry planar.channel_stretch
    planar.channel_strip planar.channel_building
    planar.bridge_span planar.channel_witness planar.chords planar.covered_bores
    planar.covered_cut planar.covered_ground planar.cut_runout planar.deck_bores
    geom.station_runs airport.bridge_ground airport.road_bridge_ground
    airport.bore_ground airport.object_ground
    airport.terrain_cut
    planar.cut_frame planar.deck_bridge planar.deck_walls
    planar.deck_route
    planar.door_ramps planar.dual_width planar.edges planar.end_barriers planar.end_witness
    planar.landing
    planar.landing_runout planar.level_depth planar.level_regions planar.level_underside
    planar.lidar_road planar.low_level planar.object_corridor planar.overlay planar.overpass_deck
    planar.pack_reads geom.pad_base_slope planar.pad_blocks planar.pad_cut planar.pad_fill
    planar.pad_sliver planar.pad_terrace planar.passage_court planar.plate_bays planar.platform
    planar.ribbon_weld planar.ribbons
    planar.ridge_reach planar.road_yield planar.shape_airside planar.shape_mouths
    planar.shape_pad_corner
    planar.shape_parts planar.shapes planar.shore planar.station_level planar.strip_keepout
    planar.split_level_pit
    planar.structure_approach planar.structure_deck planar.structure_fence
    planar.structure_geometry
    planar.structure_overlap planar.structure_pair planar.structure_road
    planar.structure_mouth planar.underpass_mouth planar.survey_cut planar.structure_service
    planar.survey_deck_cut planar.grade_separation model.grade_separation
    planar.structure_stats
    planar.structure_underpass planar.structures planar.entrance_skirt planar.terrain_edge
    planar.mouth_behind planar.mouth_opening pipeline.neck_release
    planar.unframed_ramp planar.viaduct_road
    planar.wall_corridor_ramps planar.wall_slope planar.weld planar.zones solve.api
    solve.design solve.design_assemble solve.design_edge solve.design_ground
    solve.design_junction solve.design_qp solve.design_report solve.design_roles
    solve.design_stage solve.feasibility solve.fill_order solve.flex solve.linear solve.pin_yield
    solve.project solve.project_strip solve.round_normal solve.rows solve.runway_first
    solve.wall_cut solve.warm_seed
    classify.reachability
    planar.zone_pass
    geom.fixed_overlay
    geom.valid_area
    constraints.door_pad
    geom.slope_pad
    planar.fill_road planar.fill_riser
    model.road_yield planar.road_shadow
    constraints.wall_zone
    geom.foot_planes constraints.face_index constraints.group_level planar.group_low planar.group_up
    airport.pavement_end_plate
    airport.walled_plate constraints.walled_plate constraints.terrain_shaped law.walled_plate_schema
    airport.zero_level_seat
    model.stage_one model.walled_plate planar.low_extent planar.low_fill planar.reach_after_pads
    planar.reach_under_covers
    constraints.deck_anchor
    constraints.taxi_route_yield
    airport.foot_lot
    planar.foot_kerb planar.ground_chords airport.road_descent
    airport.isolated_seat airport.terrain_base geom.diameter
    model.storey_shell planar.cell_knife planar.storey_pad planar.storey_floor
    airport.shell_ground planar.basin_author_ground
    airport.bridge_axis airport.bridge_class airport.bridge_frame
    airport.bridge_witness geom.centreline
    model.free_bridge planar.free_bridge airport.ground_route_ways
    planar.front_band airport.entrance_front planar.ramp_carry planar.deck_runout
    planar.wing_cut model.wing_cut airport.mouth_group constraints.wing_cut
    airport.wall_lines airport.ramp_wing
    constraints.bridge_span_release planar.mouth_behind
    airport.agp_gap_plates airport.agp_plan airport.apt_edit airport.touch_graph
    airport.touch_seat law.deck_gen_schema planar.deck_generated planar.short_bore
    airport.connector_warp airport.stacked_deck airport.tilt_float airport.split_bar
    planar.deck_pack_cover planar.deck_takeover
    airport.deck_plates airport.obj8_band classify.apron_gate geom.plate_bands
    model.floor_ground planar.road_wall_witness
    constraints.road_bridge_ceiling model.road_clearance
    model.clocks
""")
CODE_MODULES["emit"] = _mods("""
    geom.deck_spans planar.deck_span_cut planar.route_lines
    airport.band_run
    airport.deck_roof airport.ramp_feet geom.channel_declared planar.basin_author_ground
    planar.basin_datum planar.basin_floor_width planar.basin_geometry planar.basin_rim
    planar.basins planar.channel_claims planar.channel_ramp planar.covered_cut
    planar.cut_runout planar.door_ramps planar.fill_riser planar.group_low planar.group_up
    planar.landing_runout planar.level_depth planar.level_regions planar.level_underside
    planar.low_extent planar.low_fill planar.low_level planar.pad_blocks
    planar.passage_court planar.road_yield planar.split_level_pit planar.station_level
    planar.storey_floor planar.storey_pad planar.viaduct_road
    airport.cut_portal_seat airport.cut_bridge airport.cut_portal
    airport.hung_wall_seat airport.wall_top planar.index
    model.wing_cut
    airport.mouth_group airport.ramp_wing airport.wall_lines
    geom.agp_plate model.agp_plate
    constraints.deck_runout constraints.agp_level law.agp_schema model.agp_group
    model.deck_stack
    airport.facade airport.line_solidity classify.edge_line_mint
    model.yard_run geom.slope_bound
    classify.fence_yard classify.floor_yard geom.capped_plane solve.project_yard
    airport.deck_ends geom.deck_ground geom.end_line model.deck_ends
    geom.lowest_face geom.plate_heights
    airport.walled_pit geom.line_walk airport.pit_frame constraints.airside_top geom.plane_groups
    geom.runway_contact airport.centreline_seat
    geom.station_runs airport.bridge_ground airport.road_bridge_ground
    airport.bore_ground airport.object_ground
    airport.terrain_cut airport.terrain_fill
    geom.shape_class
    airport.hanging_objects airport.object_cut airport.object_floor airport.floor_rim
    airport.wall_geometry
    geom.author_ground geom.lowest_face geom.vector
    airport.lot_level solve.follow_stage
    geom.exact
        constraints.runway_end_report law.runway_ends_schema law.terrain_witness_schema
    airport constraints emit model pipeline planar verify airport.anchor_rule
    airport.apt_dat airport.authored_landing airport.authored_seat airport.backup_state
    airport.apt_flatten
    airport.basin_ring airport.basin_witness airport.borrow airport.bridge_family
    airport.deck_touch airport.interior_deck
    airport.bulk_geos airport.cluster_profile airport.contact airport.contents
    airport.deck_signature airport.dem airport.dem_witness airport.dsf geom.water_level
    airport.deck_family_contact
    airport.extension_cache airport.file_hash airport.footprint_carry
    airport.footprint_connector airport.footprint_seats airport.footprint_unit airport.one_building
    airport.level_base
    airport.frame_entry airport.jetways airport.line_object
    airport.airside_floor airport.msl_feet airport.obj8
    airport.terrain_feature airport.terrain_model airport.terrain_shell
    airport.bridged_ground airport.ground_shell
    airport.relief_skin airport.file_verdict airport.retaining_seat airport.sunk_frame
    airport.free_column airport.rider_floor
    airport.isolated_seat airport.terrain_base geom.diameter
    airport.terrain_shaped airport.pack_ground geom.terrain_deck
    airport.obj8_clip airport.obj8_drape airport.obj8_grade airport.obj8_roof
    airport.below_grade_witness
    airport.obj8_split airport.obj8_warp airport.deck_profile
    airport.deck_track_bend
    airport.obj8_rest airport.obj8_memo airport.pack_health airport.pack_health.light_records
    airport.pack airport.pack_partition airport.adapted_riders airport.pack_work
    airport.object_pack airport.pack_local
    airport.pack_art airport.pack_choice airport.pack_terrain
    airport.pad_block_seat airport.partition_cache airport.partition_code
    airport.placement_atom
    airport.drawn_anchor airport.exclusion
    airport.placement_body airport.placement_boxes
    airport.placement_carrier airport.placement_census airport.placement_cockpit
    airport.placement_contact airport.placement_cut airport.placement_deck
    airport.placement_family airport.placement_file airport.placement_geom
    airport.placement_leaves airport.placement_motion airport.placement_orphan
    airport.placement_plan
    airport.airside_deck_seat airport.airside_group_seat airport.cut_deck_seat
     airport.entrance_seat airport.split_guard
    airport.bridge_approach airport.deck_carry airport.deck_end_read airport.deck_riders
    airport.bridge_axis airport.bridge_witness airport.deck_surface geom.centreline
    airport.free_bridge_seat
    airport.open_frame_seat airport.pad_level_group
    airport.placement_read airport.placement_record
    airport.placement_seams airport.placement_seat_tilt airport.placement_targets
    airport.pool airport.pool_memory airport.rebake_plan airport.rebake_screen airport.riders
    airport.pool_slots
    airport.deck_plane_ring airport.pack_patch_witness
    airport.plate_ground airport.public_road
    airport.road_descent airport.road_joint airport.road_profile airport.road_ramp
    model.grade_separation
    airport.road_stations
    airport.road_ways airport.scatter airport.sheet_chain airport.skirt airport.slab_faces
    airport.ring_contact_batch
    airport.slab_plates airport.topology_cache airport.sunken_ramp airport.wall_class
    airport.wall_sheets classify
    classify.airside_edge classify.evidence classify.facade_mint classify.frontage_road
    geom.lens geom.many_buffers
    classify.gap_apron classify.fence_division
    classify.apt_shoulder classify.blast_pad classify.storey_edge airport.unit_storey
    airport.user_roles
    classify.car_lot
    classify.gap_band
    classify.gap_mint classify.gap_stands classify.lot_roads classify.neck
    classify.neck_road classify.open_default
    classify.pad_cut_corridor classify.pad_sunk classify.pad_touch
    classify.retaining_wall
    airport.wall_sides classify.wall_cutback model.wall_reach classify.ribbon_mint classify.roles
    classify.end_pad classify.island_spurs classify.wrap_page
    classify.rules classify.sources classify.taxi_letter classify.taxi_shoulder
     classify.wall_clip constraints.apron
    constraints.apron_shelf constraints.cut_kerb constraints.apron_trend constraints.ceiling
    constraints.channel constraints.cluster_pad constraints.contiguity constraints.eat
    constraints.edge_floor constraints.end_lip constraints.flat_site constraints.geometry
    constraints.deck_lines
    constraints.groundside constraints.junction_mesh constraints.no_step
    constraints.pad_frontage_gs constraints.pad_relief constraints.pad_warning
    constraints.pads constraints.platform constraints.precedence constraints.road_ramp
    constraints.roads constraints.routes constraints.runway_chord
    constraints.runway_mean_slope constraints.runway_profile constraints.threshold_seam
    constraints.runway_yield constraints.runway_junctions
    constraints.seams constraints.shoulder_crossing constraints.stretches
    constraints.strips constraints.surface_trend constraints.taxi constraints.taxi_trend
    constraints.taxi_trend_cap constraints.transverse geom.trend
    constraints.weld_floor emit.graded emit.osm_adapter emit.rebake emit.ring_fold emit.road_join
    emit.surface emit.terrain_edge geom geom.base_slab geom.cluster_outline
    geom.fixed_overlay
    geom.valid_area
    geom.containment geom.core_clamp geom.coverage geom.pad_evidence geom.parts
    geom.proportions geom.ramp_grade geom.rotated_rect geom.triangulate geom.union_find
    law law.airports_schema law.base_profile_schema law.basin_schema law.cockpit_schema
    law.cutout_schema law.design_schema law.eat_schema law.flat_pack_schema law.flat_site_schema
    law.inset_class law.model law.model_types law.rebake_schema law.reference_code
    airport.runway_strip
    law.role_cap_schema law.tables law.terrace_schema law.tunnel_object_schema law.units
    model.airport model.constraints model.end_area law.inset_class model.frame model.hard_plane
    model.islands model.jetway model.map_memo model.placement model.planar
    model.platform model.pulse model.rebake model.registries model.structures
    model.threshold_datum pipeline.authored_seats pipeline.emit_stage
    pipeline.publication pipeline.rebake_inputs pipeline.ribbon_steps
    pipeline.runway_report pipeline.seam_report pipeline.terrace_witness planar.cluster
    planar.shape_airside planar.shape_mouths
    planar.shape_pad_corner planar.shape_parts planar.shapes
    planar.strip_keepout solve solve.api solve.design solve.design_assemble
    solve.design_edge solve.design_ground solve.design_junction solve.design_qp
    solve.design_report solve.design_roles solve.design_stage solve.feasibility
    solve.fill_order solve.flex solve.ground_band solve.linear solve.pin_yield solve.project
    solve.project_strip solve.round_normal solve.rows solve.runway_first solve.wall_cut
    solve.warm_seed verify.roads
    classify.reachability
    geom.slope_pad
    airport.riser_wall
    model.road_yield pipeline.band_road_wall pipeline.wing_wall_joints
    constraints.wall_zone
    geom.foot_planes constraints.group_level constraints.face_index
    airport.pavement_end_plate
    airport.walled_plate law.walled_plate_schema model.walled_plate
    airport.zero_level_seat
    constraints.deck_anchor
    model.stage_one
    constraints.taxi_route_yield
    airport.foot_lot
    airport.split_level airport.split_level_wings airport.storey_seat model.storey_shell
    pipeline.storey_publication
    pipeline.upper_pad_publication
    airport.shell_ground
    model.free_bridge
    airport.bridge_span constraints.bridge_span_release
    airport.access_road airport.agp_deck_ends airport.agp_deck_join airport.agp_floors
    airport.agp_gap_plates airport.agp_ground airport.agp_group airport.agp_pieces
    airport.agp_plan airport.agp_plates airport.apt_edit airport.bridge_end_state
    airport.bridge_frame airport.bridge_stack airport.deck_stack airport.dsf_heights
    airport.agp_foot_pads airport.floor_deck_ends airport.stack_end_seat
    airport.facade_seat airport.footed_portal airport.ground_route_ways
    airport.portal_objects airport.stack_walls airport.touch_graph airport.touch_seat
    airport.connector_warp airport.stacked_deck airport.tilt_float airport.split_bar
    airport.tunnel_walls airport.wall_corridor_probe airport.wall_corridors
    airport.wall_mouth geom.ramp_profile law.approach_corridor law.deck_gen_schema
    pipeline.generated_publication planar.bore_continuation planar.cell_knife planar.channel
    planar.channel_depth planar.channel_floor planar.channel_geometry planar.channel_stretch
    planar.channel_strip planar.channel_building planar.channel_witness
    planar.covered_ground planar.deck_bridge
    planar.deck_generated planar.deck_route planar.deck_walls geom.wall_lines model.deck_bank
    planar.end_witness
    planar.deck_pack_cover
    planar.entrance_skirt planar.lidar_road planar.mouth_behind planar.mouth_opening
    planar.object_corridor planar.structure_approach planar.structure_deck
    planar.structure_fence planar.structure_geometry planar.structure_mouth
    planar.structure_overlap planar.structure_pair planar.structure_service
    planar.structure_underpass planar.underpass_mouth planar.unframed_ramp
    planar.wall_corridor_ramps
    airport.deck_plates airport.obj8_band airport.split_level_forecourt classify.apron_gate
    constraints.public_road_release geom.plate_bands model.floor_ground
    model.road_clearance
    model.clocks
""")
CODE_MODULES["verify"] = _mods("""
    geom.channel_declared
    airport.cut_portal_seat
    airport.hung_wall_seat airport.wall_top
    constraints.airside_top
    constraints.apron_shelf constraints.cut_kerb constraints.road_ramp
    constraints.wall_zone geom.ramp_grade
    geom.agp_plate
    constraints.apron_shelf constraints.cut_kerb constraints.road_ramp
    constraints.wall_zone geom.ramp_grade
    constraints.deck_runout constraints.agp_level law.agp_schema model.agp_group
    geom.deck_ground model.deck_stack
    airport.split_level airport.split_level_wings
    airport.facade airport.line_solidity classify.edge_line_mint
    model.yard_run geom.slope_bound solve.project_yard
    classify.fence_yard classify.floor_yard geom.capped_plane
    airport.below_grade_witness airport.floor_rim airport.hanging_objects airport.object_cut
    airport.object_floor airport.wall_geometry airport.walled_pit geom.line_walk geom.plane_groups
    geom.author_ground geom.lowest_face geom.shape_class geom.vector
    airport.pit_frame
    geom.runway_contact
    geom.exact
        constraints.runway_end_report law.runway_ends_schema law.terrain_witness_schema
    airport classify constraints emit model pipeline planar solve airport.anchor_rule
    airport.apt_dat airport.authored_landing airport.authored_seat airport.backup_state
    airport.apt_flatten
    airport.basin_ring airport.basin_witness airport.borrow airport.bridge_family
    airport.deck_touch airport.interior_deck
    airport.bulk_geos airport.cluster_profile airport.contact airport.contents
    airport.deck_family_contact airport.deck_signature airport.dem airport.dem_witness airport.dsf
    airport.extension_cache airport.file_hash airport.footprint_carry
    airport.footprint_connector airport.footprint_seats airport.footprint_unit airport.one_building
    airport.level_base
    airport.frame_entry airport.jetways airport.line_object
    airport.airside_floor airport.msl_feet airport.obj8
    airport.terrain_feature airport.terrain_model airport.terrain_shell
    airport.bridged_ground airport.ground_shell
    airport.relief_skin airport.file_verdict
    airport.free_column airport.rider_floor
    airport.isolated_seat airport.terrain_base geom.diameter
    airport.terrain_shaped airport.pack_ground geom.terrain_deck
    airport.obj8_clip airport.obj8_drape airport.obj8_grade airport.obj8_roof
    airport.obj8_split airport.obj8_warp airport.deck_profile
    airport.deck_track_bend
    airport.obj8_rest airport.obj8_memo airport.pack_health airport.pack_health.light_records
    airport.pack airport.pack_partition airport.adapted_riders airport.pack_work
    airport.object_pack airport.pack_local
    airport.pack_art airport.pack_choice airport.pack_terrain
    airport.pad_block_seat airport.partition_cache airport.partition_code
    airport.placement_atom
    airport.drawn_anchor airport.exclusion
    airport.placement_body airport.placement_boxes
    airport.placement_carrier airport.placement_census airport.placement_cockpit
    airport.placement_contact airport.placement_cut airport.placement_deck
    airport.placement_family airport.placement_file airport.placement_geom
    airport.placement_leaves airport.placement_motion airport.placement_orphan
    airport.placement_plan
    airport.airside_deck_seat airport.airside_group_seat airport.cut_deck_seat
     airport.entrance_seat airport.split_guard
    airport.bridge_approach airport.deck_carry airport.deck_end_read airport.deck_riders
    airport.bridge_axis airport.bridge_witness airport.deck_surface geom.centreline
    airport.free_bridge_seat
    airport.open_frame_seat airport.pad_level_group
    airport.placement_read airport.placement_record
    airport.placement_seams airport.placement_seat_tilt airport.placement_targets
    airport.pool airport.pool_memory airport.pool_slots airport.rebake_plan airport.deck_plane_ring
    airport.pack_patch_witness airport.riders
    airport.ring_contact_batch airport.road_ways airport.scatter
    airport.sheet_chain airport.skirt airport.slab_faces airport.slab_plates
    airport.topology_cache airport.sunken_ramp airport.wall_class airport.sunk_frame
    airport.wall_sheets
    classify.airside_edge classify.evidence
    classify.apt_shoulder classify.blast_pad classify.storey_edge airport.unit_storey
    airport.user_roles
    classify.facade_mint classify.frontage_road geom.lens geom.many_buffers
    classify.car_lot
    classify.gap_apron classify.fence_division classify.gap_band
    classify.gap_mint classify.gap_stands
    classify.lot_roads
    classify.neck classify.neck_road classify.open_default
    classify.pad_cut_corridor classify.pad_sunk classify.pad_touch classify.retaining_wall
    airport.wall_sides classify.wall_cutback model.wall_reach
    classify.ribbon_mint classify.roles classify.rules classify.sources
    classify.end_pad classify.island_spurs classify.wrap_page
    classify.taxi_letter classify.taxi_shoulder
     classify.wall_clip constraints.apron constraints.ceiling
    constraints.channel
    constraints.cluster_pad constraints.contiguity constraints.eat constraints.end_lip
    constraints.geometry constraints.groundside constraints.junction_mesh
    constraints.no_step constraints.pad_frontage_gs constraints.pad_relief
    constraints.pad_warning constraints.pads constraints.platform constraints.precedence
    constraints.roads constraints.routes constraints.runway_chord
    constraints.runway_mean_slope constraints.runway_profile constraints.threshold_seam
    constraints.runway_yield constraints.runway_junctions
    constraints.seams constraints.shoulder_crossing constraints.stretches
    constraints.strips constraints.taxi constraints.taxi_trend
    constraints.taxi_trend_cap constraints.transverse geom.trend
    constraints.weld_floor emit.ring_fold emit.surface geom geom.base_slab geom.cluster_outline
    geom.fixed_overlay
    geom.valid_area
    geom.containment geom.core_clamp geom.pad_evidence geom.parts geom.proportions
    geom.rotated_rect geom.triangulate geom.union_find law law.airports_schema
    law.base_profile_schema law.basin_schema law.cockpit_schema law.cutout_schema
    law.design_schema law.eat_schema law.flat_pack_schema
    law.flat_site_schema law.inset_class law.model
    law.model_types law.rebake_schema law.reference_code airport.runway_strip
    law.role_cap_schema law.tables
    law.terrace_schema law.tunnel_object_schema law.units model.airport
    model.constraints model.end_area law.inset_class model.frame model.islands model.map_memo
    model.placement model.planar model.platform model.pulse model.rebake
    model.registries model.structures model.threshold_datum pipeline.publication
    pipeline.ribbon_steps pipeline.verify_stage planar.cluster planar.shape_airside
    planar.shape_mouths
    planar.shape_pad_corner planar.shape_parts planar.shapes planar.strip_keepout
    solve.design_roles solve.ground_band verify verify.census verify.channel
    verify.chord_work verify.contiguity verify.cutback verify.eat verify.frame
    verify.frontage verify.jetway verify.keepout verify.no_step verify.pads verify.pins
    verify.runway verify.runway_mean_slope verify.runway_witness verify.steps
    verify.strips verify.structures verify.transverse verify.within
    classify.reachability
    geom.slope_pad
    model.road_yield pipeline.band_road_wall pipeline.wing_wall_joints
    geom.foot_planes constraints.group_level constraints.face_index
    airport.pavement_end_plate
    airport.walled_plate law.walled_plate_schema model.walled_plate
    airport.zero_level_seat
    constraints.deck_anchor constraints.edge_floor
    constraints.deck_lines
    model.stage_one
    verify.deck_flush
    constraints.taxi_route_yield
    pipeline.storey_publication pipeline.upper_pad_publication
    airport.shell_ground
    model.free_bridge
    constraints.bridge_span_release
    airport.access_road airport.agp_deck_ends airport.agp_deck_join airport.agp_floors
    airport.agp_gap_plates airport.agp_ground airport.agp_group airport.agp_pieces
    airport.agp_plan airport.agp_plates airport.apt_edit airport.bridge_end_state
    airport.bridge_frame airport.bridge_stack airport.deck_ends airport.deck_stack
    airport.agp_foot_pads airport.floor_deck_ends airport.stack_end_seat
    airport.dsf_heights airport.facade_seat airport.ground_route_ways airport.stack_walls
    airport.touch_graph airport.touch_seat geom.end_line geom.plate_heights
    airport.connector_warp airport.stacked_deck airport.tilt_float airport.split_bar
    geom.ramp_profile law.deck_gen_schema model.agp_plate model.deck_ends
    airport.deck_plates airport.obj8_band classify.apron_gate constraints.public_road_release
    geom.plate_bands model.floor_ground
    model.road_clearance
    verify.nearest
    model.clocks
""")

#: #2188: the held terrace's level reads the pads' own derivations
# #2279 step 2 (lane lphli2): the landside kerb rows and the wall exempt
_GENERATOR_CLOSURES["kerb_frontage"] = _mods(_GENERATOR_CORE + """
    constraints.agp_level constraints.airside_top constraints.apron constraints.apron_shelf
    constraints.cluster_pad constraints.contiguity constraints.cut_kerb constraints.deck_lines
    constraints.deck_runout constraints.edge_floor constraints.end_lip constraints.face_index
    constraints.geometry constraints.groundside constraints.group_level constraints.kerb_frontage
    constraints.pad_relief constraints.pad_warning constraints.pads constraints.platform
    constraints.precedence constraints.public_road_release constraints.road_ramp
    constraints.roads constraints.routes constraints.stretches constraints.strips
    constraints.taxi constraints.taxi_route_yield constraints.wall_zone geom.base_slab
    geom.cluster_outline geom.containment geom.deck_ground geom.deg_metres geom.exact
    geom.pad_base_slope geom.pad_evidence geom.place_matrix geom.plate_bands geom.ramp_grade
    geom.route_over_pad geom.slope_pad geom.sunk_cluster geom.triangulate geom.union_find
    geom.wall_lines geom.walled_trench law.inset_class model.agp_group model.airport
    model.end_area model.islands model.map_memo model.platform model.threshold_datum
    model.wall_reach
""")
_GENERATOR_CLOSURES["pad_sunk_level"] = tuple(sorted(
    {*_GENERATOR_CLOSURES["pads"], "auto_patch_v2.constraints.pad_sunk_level"}))

def generator_stage(name: str) -> str:
    """The stage-code entry of the constraint generator ``name``."""
    return f"constraints.{name}"


for _name, _module in GENERATOR_MODULES.items():
    ENTRY_MODULES[generator_stage(_name)] = (f"auto_patch_v2.constraints.{_module}",)
    CODE_MODULES[generator_stage(_name)] = _GENERATOR_CLOSURES[_module]
# #798 round 3: the records' assembly enters through ``constraints.
# post_passes`` (the door pads' blend, then ``assembly.assemble``)
ENTRY_MODULES["constraints.assembly"] = ("auto_patch_v2.constraints",
                                         "auto_patch_v2.constraints.assembly",
                                         "auto_patch_v2.pipeline.shapes")
ENTRY_MODULES["jetway_strip"] = ("auto_patch_v2.airport.riders",
                                 "auto_patch_v2.constraints.jetway_strip")
ENTRY_MODULES["solve"] = ("auto_patch_v2.solve.design", "auto_patch_v2.solve.api",
                          "auto_patch_v2.constraints.face_index",
                          "auto_patch_v2.constraints.group_level",
                          "auto_patch_v2.constraints.no_step",
                          "auto_patch_v2.constraints.road_ramp",
                          "auto_patch_v2.constraints.taxi_route_yield",
                          "auto_patch_v2.constraints.taxi_trend",
                          "auto_patch_v2.pipeline.lot_follow",
                          "auto_patch_v2.pipeline.stage_one_map",
                          "auto_patch_v2.pipeline.solve_record")
ENTRY_MODULES["late_cut"] = ("auto_patch_v2.pipeline.late_stage",
                             "auto_patch_v2.classify.gap_terrace",
                             "auto_patch_v2.pipeline.late_records",
                             "auto_patch_v2.classify.gap_mint",
                             "auto_patch_v2.classify.gap_stands")
ENTRY_MODULES["late_solve"] = ("auto_patch_v2.pipeline.late_stage",
                               "auto_patch_v2.constraints.face_index",
                               "auto_patch_v2.constraints.gap_follow",
                               "auto_patch_v2.constraints.group_level",
                               "auto_patch_v2.constraints.no_step",
                               "auto_patch_v2.constraints.road_ramp",
                               "auto_patch_v2.pipeline.late_records",
                               "auto_patch_v2.solve.design",
                               "auto_patch_v2.constraints.taxi_trend")
# THE EMIT AND THE VERIFY (spec §4b.6, §4b.7; #843 step 9c): entered at
# ``pipeline/emit_stage`` (``render`` / ``install``, the post-solve glue
# with them) and ``pipeline/verify_stage`` (``judge`` / ``install``)
ENTRY_MODULES["emit"] = ("auto_patch_v2.pipeline.emit_stage",)
ENTRY_MODULES["verify"] = ("auto_patch_v2.pipeline.verify_stage",)

# MERGE test-565 (2026-11-19): constraints/__init__ -> walled_floor and
# geom.pad_base_slope -> airport.obj8_grade widened these closures.
_GROWN: dict[str, str] = {
    'classify': """
    geom.plate_cells geom.route_over_pad geom.sunk_cluster model.deck_piece
    """,
    'planar': """
    geom.sunk_cluster planar.deck_gen_cover planar.deck_gen_pairs
    """,
    'road_profile': """
    geom.plate_cells geom.sunk_cluster model.deck_piece
    """,
    'channels': """
    geom.plate_cells geom.route_over_pad geom.sunk_cluster geom.wall_lines model.deck_piece
    geom.pad_base_slope
    """,
    'shapes': """
    constraints.walled_floor geom.plate_cells geom.route_over_pad geom.sunk_cluster model.deck_piece
    geom.pad_base_slope
    """,
    'constraints.runway_mean_slope': """
    geom.route_over_pad geom.sunk_cluster geom.wall_lines geom.pad_base_slope
    """,
    'constraints.runway_crossing_pin': """
    geom.route_over_pad geom.sunk_cluster geom.wall_lines geom.pad_base_slope
    """,
    'constraints.deck_anchor': """
    geom.route_over_pad geom.sunk_cluster geom.wall_lines geom.pad_base_slope
    """,
    'constraints.taxi_chain': """
    geom.route_over_pad geom.sunk_cluster geom.pad_base_slope
    """,
    'constraints.taxi_centerlines': """
    geom.route_over_pad geom.sunk_cluster geom.pad_base_slope
    """,
    'constraints.triangle_planes': """
    geom.route_over_pad geom.sunk_cluster geom.pad_base_slope
    """,
    'constraints.taxi_box': """
    geom.route_over_pad geom.sunk_cluster geom.pad_base_slope
    """,
    'constraints.junction_mesh': """
    geom.route_over_pad geom.sunk_cluster geom.pad_base_slope
    """,
    'constraints.apron_within_shape': """
    geom.route_over_pad geom.sunk_cluster geom.pad_base_slope
    """,
    'constraints.steep_apron_plane': """
    geom.route_over_pad geom.sunk_cluster geom.pad_base_slope
    """,
    'constraints.door_pad_level': """
    geom.route_over_pad geom.sunk_cluster geom.pad_base_slope
    """,
    'constraints.apron_edge_portions': """
    geom.route_over_pad geom.sunk_cluster geom.pad_base_slope
    """,
    'constraints.road_ramp': """
    constraints.deck_lines geom.plate_bands geom.route_over_pad geom.sunk_cluster geom.wall_lines
    geom.pad_base_slope
    """,
    'constraints.road_contact': """
    constraints.deck_lines geom.plate_bands geom.route_over_pad geom.sunk_cluster geom.wall_lines
    geom.pad_base_slope
    """,
    'constraints.edge_deck': """
    constraints.walled_floor
    """,
    'constraints.road_coverage_join': """
    constraints.deck_lines geom.plate_bands geom.route_over_pad geom.sunk_cluster geom.wall_lines
    geom.pad_base_slope
    """,
    'constraints.wall_terrace': """
    constraints.deck_lines geom.plate_bands geom.route_over_pad geom.sunk_cluster geom.wall_lines
    geom.pad_base_slope
    """,
    'constraints.transverse': """
    geom.route_over_pad geom.sunk_cluster geom.pad_base_slope
    """,
    'constraints.junction_raw_transverse': """
    geom.route_over_pad geom.sunk_cluster geom.pad_base_slope
    """,
    'constraints.no_step_pairs': """
    geom.route_over_pad geom.sunk_cluster geom.pad_base_slope
    """,
    'constraints.no_step_rate': """
    geom.route_over_pad geom.sunk_cluster geom.pad_base_slope
    """,
    'constraints.reach_bands': """
    geom.route_over_pad geom.sunk_cluster geom.pad_base_slope
    """,
    'constraints.pad_flats': """
    geom.route_over_pad geom.sunk_cluster geom.pad_base_slope
    """,
    'constraints.pad_frontage_level': """
    geom.route_over_pad geom.sunk_cluster geom.pad_base_slope
    """,
    'constraints.pad_fronting_level': """
    geom.route_over_pad geom.sunk_cluster geom.pad_base_slope
    """,
    'constraints.pad_slope_ceiling': """
    geom.route_over_pad geom.sunk_cluster geom.pad_base_slope
    """,
    'constraints.platform_collar': """
    geom.route_over_pad geom.sunk_cluster geom.pad_base_slope
    """,
    'constraints.block_strip': """
    geom.route_over_pad geom.sunk_cluster geom.pad_base_slope
    """,
    'constraints.platform_plane': """
    geom.route_over_pad geom.sunk_cluster geom.pad_base_slope
    """,
    'constraints.landing_level': """
    geom.route_over_pad geom.sunk_cluster geom.pad_base_slope
    """,
    'constraints.shell_datum': """
    constraints.deck_lines geom.plate_bands geom.route_over_pad geom.sunk_cluster geom.wall_lines
    geom.pad_base_slope
    """,
    'constraints.landing_runout': """
    constraints.deck_lines geom.plate_bands geom.route_over_pad geom.sunk_cluster geom.wall_lines
    geom.pad_base_slope
    """,
    'constraints.platform_level': """
    geom.route_over_pad geom.sunk_cluster geom.pad_base_slope
    """,
    'constraints.frontage_hold': """
    geom.route_over_pad geom.sunk_cluster geom.pad_base_slope
    """,
    'constraints.frontage_near_miss': """
    geom.route_over_pad geom.sunk_cluster geom.pad_base_slope
    """,
    'constraints.groundside_frontage_level': """
    geom.route_over_pad geom.sunk_cluster geom.pad_base_slope
    """,
    'constraints.eat_anchor_rect': """
    geom.route_over_pad geom.sunk_cluster geom.wall_lines geom.pad_base_slope
    """,
    'constraints.foot_rows': """
    constraints.deck_lines geom.plate_bands geom.route_over_pad geom.sunk_cluster geom.wall_lines
    geom.pad_base_slope
    """,
    'constraints.structures': """
    constraints.deck_lines geom.plate_bands geom.route_over_pad geom.sunk_cluster geom.wall_lines
    geom.pad_base_slope
    """,
    'constraints.rim_level': """
    constraints.deck_lines geom.plate_bands geom.route_over_pad geom.sunk_cluster geom.wall_lines
    geom.pad_base_slope
    """,
    'constraints.basins': """
    constraints.deck_lines geom.plate_bands geom.route_over_pad geom.sunk_cluster geom.wall_lines
    geom.pad_base_slope
    """,
    'constraints.wing_cut': """
    constraints.deck_lines geom.plate_bands geom.union_find geom.wall_lines
    """,
    'constraints.deck_stack': """
    constraints.walled_floor
    """,
    'constraints.agp_plate': """
    constraints.walled_floor
    """,
    'constraints.assembly': """
    constraints.walled_floor geom.plate_cells geom.route_over_pad geom.sunk_cluster model.deck_piece
    geom.pad_base_slope
    """,
    'jetway_strip': """
    geom.plate_cells geom.route_over_pad geom.sunk_cluster model.deck_piece geom.pad_base_slope
    """,
    'solve': """
    geom.plate_cells geom.route_over_pad geom.sunk_cluster model.deck_piece planar.deck_gen_cover
    planar.deck_gen_pairs
    """,
    'late_cut': """
    constraints.pad_sunk_level constraints.walled_floor geom.plate_cells geom.route_over_pad
    geom.sunk_cluster model.deck_piece planar.deck_gen_cover planar.deck_gen_pairs
    """,
    'late_solve': """
    constraints.pad_sunk_level constraints.walled_floor geom.plate_cells geom.route_over_pad
    geom.sunk_cluster model.deck_piece planar.deck_gen_cover planar.deck_gen_pairs
    """,
    'emit': """
    geom.plate_cells geom.route_over_pad geom.sunk_cluster model.deck_piece pipeline.road_deck
    planar.deck_gen_cover planar.deck_gen_pairs geom.pad_base_slope
    """,
    'verify': """
    geom.plate_cells geom.route_over_pad geom.sunk_cluster geom.wall_lines model.deck_piece
    geom.pad_base_slope
    """,
    'constraints.pad_sunk_level': """
    geom.route_over_pad geom.sunk_cluster geom.pad_base_slope
    """,
}
for _stage, _names in _GROWN.items():
    CODE_MODULES[_stage] = tuple(sorted({*CODE_MODULES[_stage], *_mods(_names)}))

# lbridge2 (2026-11-19, airside-first bridges): planar/deck_airside,
# planar/deck_width and geom/coons_patch widened these closures.
_GROWN_BRIDGES: dict[str, str] = {
    'planar': "planar.deck_airside planar.deck_width",
    'solve': "planar.deck_airside planar.deck_width",
    'late_cut': "planar.deck_airside planar.deck_width",
    'late_solve': "planar.deck_airside planar.deck_width",
    'emit': "planar.deck_width",
}
for _stage, _names in _GROWN_BRIDGES.items():
    CODE_MODULES[_stage] = tuple(sorted({*CODE_MODULES[_stage], *_mods(_names)}))

# lcarve (2026-11-19, the cut is the deck's): planar/deck_carve and its
# geom / model records widened these closures.
_GROWN_CARVE = "geom.carve_profile model.deck_carve planar.deck_carve"
for _stage in ("planar", "solve", "late_cut", "late_solve"):
    CODE_MODULES[_stage] = tuple(sorted({*CODE_MODULES[_stage], *_mods(_GROWN_CARVE)}))
# lcarve2: the stage-2 airside held at the surface solved without the cut
for _stage in ("solve", "late_cut", "late_solve", "emit"):
    CODE_MODULES[_stage] = tuple(sorted({*CODE_MODULES[_stage], *_mods("solve.stage_shadow")}))

# lcross20 (2026-11-20, one decision per crossing): the deck frame moved
# into geom, the road decks' spans read by the planar cut, the pack bridge
# census reader; emit reads the road decks' published top (coons patch)
_GROWN_CROSS = "geom.deck_frame geom.road_span"
for _stage in ("planar", "solve", "late_cut", "late_solve", "emit"):
    CODE_MODULES[_stage] = tuple(sorted({*CODE_MODULES[_stage], *_mods(_GROWN_CROSS)}))
CODE_MODULES["emit"] = tuple(sorted({*CODE_MODULES["emit"], *_mods(
    "constraints.deck_carve constraints.deck_floor_follow geom.carve_profile "
    "geom.coons_patch model.deck_carve")}))
CODE_MODULES["verify"] = tuple(sorted({*CODE_MODULES["verify"], *_mods("verify.pack_bridge")}))

# lphli2 (2026-11-25, #2279 step 2): the landside kerb line published on
# its block (planar/kerb_frontage) and its rows / wall exempt
for _stage in ("planar", "solve", "late_cut", "late_solve"):
    CODE_MODULES[_stage] = tuple(sorted({*CODE_MODULES[_stage], *_mods("planar.kerb_frontage")}))
for _stage in ("shapes", "constraints.assembly", "late_cut", "late_solve", "emit", "verify"):
    CODE_MODULES[_stage] = tuple(sorted({*CODE_MODULES[_stage],
                                         *_mods("constraints.kerb_frontage")}))
# the wall the kerb meets, declared on the sidecar (pipeline/kerb_publication)
for _stage in ("emit", "verify"):
    CODE_MODULES[_stage] = tuple(sorted({*CODE_MODULES[_stage],
                                         *_mods("pipeline.kerb_publication")}))

#: The cached stages, in build order.
STAGES: tuple[str, ...] = tuple(ENTRY_MODULES)

# lmslframe (2026-11-20, RULINGS 20l): the MSL feet seat joins the sets of
# one anchor where their geometry meets (geom/point_triangle)
for _stage, _mods_of in list(CODE_MODULES.items()):
    if "auto_patch_v2.airport.msl_feet" in _mods_of:
        CODE_MODULES[_stage] = tuple(sorted({*_mods_of, *_mods("geom.point_triangle")}))

# ltunnel2 (2026-11-21, RULINGS 21d / #2221): the at-grade mouth's seat and
# level floor (planar/portal_level), read by planar/structures
for _stage in ("planar", "solve", "late_cut", "late_solve"):
    CODE_MODULES[_stage] = tuple(sorted({*CODE_MODULES[_stage], *_mods("planar.portal_level")}))

# lci573 (2026-11-21): the walled trench's plan geometry moved into geom
# (geom/walled_trench) so constraints/walled_floor reads it without
# importing planar; every stage reading the deck cut or the floor rows
for _stage, _mods_of in list(CODE_MODULES.items()):
    if {"auto_patch_v2.planar.deck_bridge", "auto_patch_v2.planar.deck_walls",
            "auto_patch_v2.constraints.walled_floor", "auto_patch_v2.constraints.deck_lines",
            "auto_patch_v2.constraints.deck_carve",
            "auto_patch_v2.constraints.deck_floor_follow"} & set(_mods_of):
        CODE_MODULES[_stage] = tuple(sorted({*_mods_of, *_mods("geom.walled_trench")}))
# the generated decks stage 1 withholds moved into model/deck_withheld (read
# by planar/deck_airside and constraints/deck_floor_follow), the member
# placement matrix into geom/place_matrix (read by airport/obj8_grade and
# geom/pad_base_slope): constraints import no planar
for _stage, _mods_of in list(CODE_MODULES.items()):
    if "auto_patch_v2.planar.deck_airside" in _mods_of \
            or "auto_patch_v2.constraints.deck_floor_follow" in _mods_of:
        CODE_MODULES[_stage] = tuple(sorted({*CODE_MODULES[_stage], *_mods("model.deck_withheld")}))
    if "auto_patch_v2.airport.obj8_grade" in _mods_of \
            or "auto_patch_v2.geom.pad_base_slope" in _mods_of:
        CODE_MODULES[_stage] = tuple(sorted({*CODE_MODULES[_stage], *_mods("geom.place_matrix")}))
# metres per degree moved into geom/deg_metres (model/frame re-exports it),
# read by geom/pad_base_slope
for _stage, _mods_of in list(CODE_MODULES.items()):
    if {"auto_patch_v2.model.frame", "auto_patch_v2.geom.pad_base_slope"} & set(_mods_of):
        CODE_MODULES[_stage] = tuple(sorted({*CODE_MODULES[_stage], *_mods("geom.deg_metres")}))
