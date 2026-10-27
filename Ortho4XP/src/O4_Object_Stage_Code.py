"""THE OBJECT STAGE REUSE'S CODE HALF (issue #879): the modules the object
stage after the mesh runs through, and ONE digest of their source bytes —
taken from the sources in a checkout, and from the file the FREEZE wrote
in a frozen engine.

A TOP-LEVEL ``O4_*`` MODULE, not an ``auto_patch_v2`` one: the stage it
keys is the v1-named ``auto_patch.object_stage``, so this file names v1
modules, and ``auto_patch_v2`` may not (``tests/auto_patch_v2/
test_model.py``) — the same home as the tile steps' ``O4_Step_Code``.

The partition's and the v2 stages' mechanism (``auto_patch_v2/airport/
partition_code.py``, ``auto_patch_v2/pipeline/stage_code.py``) for one
more cached unit: :data:`ENTRY_MODULES` is where ``O4_Mesh_Utils`` enters
the stage (``object_stage.rebake_after_mesh``), :data:`CODE_MODULES` the
static import closure of it, every ``import`` in every function included,
followed into :data:`CLOSURE_PREFIXES`.  ``tests/auto_patch_v2/test_object_stage_code_
closure.py`` recomputes the closure and fails on a module the stage imports
and the list omits (a STALE HIT after an edit there), and on the reverse.
The top-level ``O4_*`` modules the stage reaches are not keyed — the same
rule ``stage_code`` follows (#842, there for the spec author to rule).

STDLIB ONLY, NO RELATIVE IMPORT: the specs execute this file with
``runpy`` (they never import engine packages); the shared mechanism
(``O4_Code_Closure.py`` beside this file) is then loaded by path.
"""
from __future__ import annotations

import os

__all__ = ["ENTRY_MODULES", "CODE_MODULES", "CLOSURE_PREFIXES",
           "DIGEST_FILENAME", "write_freeze_digest", "runtime_digest"]

#: The file the freeze writes beside this module (one line: the digest).
DIGEST_FILENAME = "object_stage_code.sha256"

#: The closure follows imports into these top-level packages only.
CLOSURE_PREFIXES: tuple[str, ...] = ("auto_patch", "auto_patch_v2")

#: Where ``O4_Mesh_Utils._auto_patch_post_mesh_rebake`` enters the stage.
ENTRY_MODULES: tuple[str, ...] = ("auto_patch.object_stage",)

try:
    import O4_Code_Closure as _closure_module
    _CLOSURE = vars(_closure_module)
except ImportError:
    import runpy as _runpy
    _CLOSURE = _runpy.run_path(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "O4_Code_Closure.py"))


def write_freeze_digest(src_root: str, out_dir: str) -> str:
    """THE FREEZE'S ACT: write the digest of :data:`CODE_MODULES` read under
    ``src_root`` to ``out_dir/``:data:`DIGEST_FILENAME` and return that
    path (the specs bundle it beside this module).  RAISES ``SystemExit``
    when a listed module has no source."""
    return _CLOSURE["write_digest_file"](
        out_dir, DIGEST_FILENAME,
        _CLOSURE["modules_digest"](src_root, CODE_MODULES),
        "ERROR: could not digest the object stage's code modules under "
        f"{src_root!r} (O4_Object_Stage_Code.CODE_MODULES names a module with "
        "no source file) — refusing to freeze an engine whose object stage "
        "reuse would have no code identity.")


_RUNTIME: list = []


def runtime_digest() -> "str | None":
    """The digest for THIS engine, once per process: of the sources in a
    checkout (``src``, this module's folder), else the file the freeze
    wrote beside this module (``_internal`` in a frozen engine).  ``None`` with neither — the stage
    then neither
    reads nor writes a record."""
    if not _RUNTIME:
        here = os.path.dirname(os.path.abspath(__file__))
        got = _CLOSURE["modules_digest"](here, CODE_MODULES)
        _RUNTIME.append(got or _CLOSURE["read_digest"](here, DIGEST_FILENAME))
    return _RUNTIME[0]


#: The stage's static import closure under :data:`CLOSURE_PREFIXES`,
#: sorted — the code half of its key.  Held by
#: ``tests/auto_patch_v2/test_object_stage_code_closure.py``; when it fails, the message
#: names the modules to add or drop.  A package is listed as its
#: ``__init__``.
CODE_MODULES: tuple[str, ...] = (
    "auto_patch",
    "auto_patch.agp_reader",
    "auto_patch.build_support",
    "auto_patch.config",
    "auto_patch.config_gates",
    "auto_patch.dsf_reader",
    "auto_patch.forest_stage",
    "auto_patch.geom_safe",
    "auto_patch.mesh_sampler",
    "auto_patch.obj8_partition",
    "auto_patch.obj8_reader",
    "auto_patch.object_anchor",
    "auto_patch.object_clusters",
    "auto_patch.object_footprints",
    "auto_patch.object_frame",
    "auto_patch.object_rebake",
    "auto_patch.object_stage",
    "auto_patch.object_terrain_features",
    "auto_patch.object_terrain_kinds",
    "auto_patch.post_mesh",
    "auto_patch.progress",
    "auto_patch.provenance",
    "auto_patch.provenance_code",
    "auto_patch.provenance_env",
    "auto_patch.selection",
    "auto_patch_v2",
    "auto_patch_v2.airport",
    "auto_patch_v2.airport.airside_deck_seat",
    "auto_patch_v2.airport.airside_group_seat",
    "auto_patch_v2.airport.anchor_rule",
    "auto_patch_v2.airport.apt_dat",
    "auto_patch_v2.airport.authored_landing",
    "auto_patch_v2.airport.authored_seat",
    "auto_patch_v2.airport.backup_state",
    "auto_patch_v2.airport.basin_ring",
    "auto_patch_v2.airport.basin_witness",
    "auto_patch_v2.airport.borrow",
    "auto_patch_v2.airport.bridge_approach",
    "auto_patch_v2.airport.bridge_family",
    "auto_patch_v2.airport.bulk_geos",
    "auto_patch_v2.airport.cifp",
    "auto_patch_v2.airport.cluster_profile",
    "auto_patch_v2.airport.contact",
    "auto_patch_v2.airport.contents",
    "auto_patch_v2.airport.cut_deck_seat",
    "auto_patch_v2.airport.deck_signature",
    "auto_patch_v2.airport.dem_witness",
    "auto_patch_v2.airport.dsf",
    "auto_patch_v2.airport.dsf_commands",
    "auto_patch_v2.airport.dsf_write",
    "auto_patch_v2.airport.extension_cache",
    "auto_patch_v2.airport.file_hash",
    "auto_patch_v2.airport.file_witness",
    "auto_patch_v2.airport.footprint_carry",
    "auto_patch_v2.airport.footprint_connector",
    "auto_patch_v2.airport.footprint_seats",
    "auto_patch_v2.airport.footprint_unit",
    "auto_patch_v2.airport.frame_entry",
    "auto_patch_v2.airport.frame_riders",
    "auto_patch_v2.airport.line_object",
    "auto_patch_v2.airport.msl_feet",
    "auto_patch_v2.airport.obj8",
    "auto_patch_v2.airport.obj8_clip",
    "auto_patch_v2.airport.obj8_drape",
    "auto_patch_v2.airport.obj8_grade",
    "auto_patch_v2.airport.obj8_roof",
    "auto_patch_v2.airport.obj8_split",
    "auto_patch_v2.airport.object_plan",
    "auto_patch_v2.airport.object_stage_reuse",
    "auto_patch_v2.airport.one_building",
    "auto_patch_v2.airport.open_frame_seat",
    "auto_patch_v2.airport.pack",
    "auto_patch_v2.airport.pack_art",
    "auto_patch_v2.airport.pack_forests",
    "auto_patch_v2.airport.pack_forests_map",
    "auto_patch_v2.airport.pack_journal",
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
    "auto_patch_v2.airport.placement_write",
    "auto_patch_v2.airport.pool",
    "auto_patch_v2.airport.rebake_plan",
    "auto_patch_v2.airport.rebake_screen",
    "auto_patch_v2.airport.riders",
    "auto_patch_v2.airport.ring_contact_batch",
    "auto_patch_v2.airport.scatter",
    "auto_patch_v2.airport.sheet_chain",
    "auto_patch_v2.airport.skirt",
    "auto_patch_v2.airport.slab_drape",
    "auto_patch_v2.airport.slab_faces",
    "auto_patch_v2.airport.slab_plates",
    "auto_patch_v2.airport.split_guard",
    "auto_patch_v2.airport.stage_cache",
    "auto_patch_v2.airport.terrain_feature",
    "auto_patch_v2.airport.topology_cache",
    "auto_patch_v2.airport.unpatched_pack",
    "auto_patch_v2.geom",
    "auto_patch_v2.geom.base_slab",
    "auto_patch_v2.geom.cluster_outline",
    "auto_patch_v2.geom.foot_planes",
    "auto_patch_v2.geom.grid_pickle",
    "auto_patch_v2.geom.pad_evidence",
    "auto_patch_v2.geom.parts",
    "auto_patch_v2.geom.rotated_rect",
    "auto_patch_v2.geom.union_find",
    "auto_patch_v2.law",
    "auto_patch_v2.law.airports_schema",
    "auto_patch_v2.law.base_profile_schema",
    "auto_patch_v2.law.basin_schema",
    "auto_patch_v2.law.cockpit_schema",
    "auto_patch_v2.law.cutout_schema",
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
    "auto_patch_v2.pipeline",
    "auto_patch_v2.pipeline.xplat",
)
