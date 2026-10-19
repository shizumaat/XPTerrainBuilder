"""THE PATCH FRESHNESS GATE'S CODE HALF (issues #346, #880): ONE digest of
the code an airport patch is built by, stamped on every patch as
``o4_code``.

WHY.  The gate (``driver._auto_patch_is_current``) keyed the engine on
``O4_Version.version`` alone.  That string moves only when
``scripts/make_engine.sh`` freezes: a checkout whose solve was edited kept
"build inputs unchanged" and reused the old patch (#346).

WHAT IS DIGESTED (#880).  The static import closure of the patch build —
where the tile build ENTERS it, ``auto_patch.driver``
(:data:`PATCH_ENTRY_MODULES`), every ``import`` followed, function-level
ones included, into every module with a source under ``src`` (the walker
is ``src/O4_Code_Closure.py``), plus the ``__init__`` of every package
above a module in it and what those ``__init__`` s import, as Python loads
them — and every data table (``.toml``: the law, the classifier's rules;
:data:`PATCH_DATA_FILES`).  The closure runs into the tile core (it
prepares the DEM the solve reads), so it is most of ``src``: 529 of 614
modules on 2026-10-19.  What it leaves out cannot shape a patch: the Qt
app, the app's command handlers (``o4_engine.*_commands``, the patch
editor, the JSONL wire), the MSFS converters, the self-checks, the
``__main__`` CLIs and ``Unused``.  An edit there no longer stales every
airport's patch.  (The tile's mesh / mask / imagery modules are IN it:
``o4_engine/__init__`` imports the app session, which imports them — a
hub cut there would narrow the key further.)  ``tests/test_patch_code_closure.py`` recomputes
the closure and fails on a module the patch build imports and
:data:`PATCH_CODE_MODULES` omits — the #346 guarantee, held by the twin
instead of by the whole tree.

THE WHOLE TREE, KEPT (#346's key, behind a switch).  :func:`freeze_digest`
is every ``.py`` and ``.toml`` under ``src``.  ``O4_PATCH_FRESHNESS_WHOLE_
TREE=1`` stamps and compares THAT digest again (:func:`freshness_code_
digest`) — the #880 trade reversed without a revert; a patch an engine
before #880 wrote then reads as current again.  It is also the engine's
code identity in the provenance line (``provenance.source_label``) and the
tile steps' fallback (``O4_Step_Reuse``).

THE MECHANISM IS THE SHARED ONE (``src/O4_Code_Closure.py``, #842): the
digest is taken from the sources in a checkout and written to a file by
the FREEZE (``Ortho4XP.spec`` / ``Ortho4XP_Qt.spec`` run
:func:`write_freeze_digest` and :func:`write_patch_freeze_digest` with
``runpy``), which the frozen engine reads back.

STDLIB ONLY, NO RELATIVE IMPORT — the specs execute this file by path.
"""
from __future__ import annotations

import os
import runpy
import sys

__all__ = ["DIGEST_FILENAME", "SOURCE_SUFFIXES", "source_files",
           "freeze_digest", "write_freeze_digest", "frozen_digest",
           "code_digest", "PATCH_ENTRY_MODULES", "PATCH_CODE_MODULES",
           "PATCH_DATA_FILES", "PATCH_DIGEST_FILENAME", "WHOLE_TREE_ENV",
           "patch_freeze_digest", "write_patch_freeze_digest",
           "frozen_patch_digest", "freshness_code_digest"]

#: The file the freeze writes beside this module (one line: the digest).
DIGEST_FILENAME = "engine_code.sha256"

#: What counts as engine source: modules, and the tables they load as data.
SOURCE_SUFFIXES = (".py", ".toml")

_SKIPPED_DIRECTORIES = ("__pycache__",)


def source_files(src_root: str) -> list[tuple[str, str]]:
    """``(posix path relative to src_root, path)`` of every engine source
    file under ``src_root``, sorted — the digest's order."""
    found = []
    for directory, subdirectories, names in os.walk(src_root):
        subdirectories[:] = [d for d in subdirectories
                             if d not in _SKIPPED_DIRECTORIES]
        for name in names:
            if name.endswith(SOURCE_SUFFIXES):
                path = os.path.join(directory, name)
                relative = os.path.relpath(path, src_root)
                found.append((relative.replace(os.sep, "/"), path))
    return sorted(found)


def _partition_code() -> dict:
    """``auto_patch_v2/airport/partition_code.py``'s namespace, which owns
    ``digest_of`` and the ONE reader/writer of a freeze-time digest file.

    By PATH when its source sits beside this tree (a checkout, and the
    spec, which executes this file by path with nothing importable); by
    IMPORT in a frozen engine, which has no sources — called lazily, so
    the package is loaded by then and the import is not circular."""
    path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "auto_patch_v2", "airport",
        "partition_code.py")
    if os.path.isfile(path):
        return runpy.run_path(path)
    from auto_patch_v2.airport import partition_code
    return vars(partition_code)


def freeze_digest(src_root: str) -> str | None:
    """The digest of :func:`source_files`, or ``None`` when ``src_root``
    holds no engine (no ``O4_Version.py``) or a file cannot be read."""
    if not os.path.isfile(os.path.join(src_root, "O4_Version.py")):
        return None
    digest_of = runpy.run_path(os.path.join(
        src_root, "auto_patch_v2", "airport", "partition_code.py"))["digest_of"]
    return digest_of(source_files(src_root))


def write_freeze_digest(src_root: str, out_dir: str) -> str:
    """THE FREEZE'S ACT: write :func:`freeze_digest` of ``src_root`` to
    ``out_dir/``:data:`DIGEST_FILENAME` and return that path.  RAISES
    ``SystemExit`` when there is no digest to write — an engine frozen
    without the file would key its patches on the version alone again."""
    digest = freeze_digest(src_root)
    if not digest:
        raise SystemExit(
            f"ERROR: could not digest the engine source under {src_root!r} — "
            "refusing to freeze an engine whose patch freshness gate would "
            "key on the version string alone.")
    return _partition_code()["write_freeze_digest"](
        src_root, out_dir, filename=DIGEST_FILENAME, digest=digest)


def frozen_digest(directory: str | None = None) -> str | None:
    """The digest the freeze wrote beside this module, or ``None`` (a
    checkout; an engine frozen by a spec that predates the file)."""
    if directory is None:
        directory = os.path.dirname(os.path.abspath(__file__))
    return _partition_code()["frozen_digest"](directory,
                                              filename=DIGEST_FILENAME)


_CODE_DIGEST: str | None = None


def code_digest() -> str:
    """The running engine's code digest (16 hex), taken once per process.

    Frozen: the file the freeze wrote.  A checkout: the sources this
    module was imported from.  ``absent`` when neither can be had — the
    explicit "could not determine" spelling of the freshness stamps; the
    version stamp is then the only code identity, as before #346.
    """
    global _CODE_DIGEST
    if _CODE_DIGEST is None:
        digest = frozen_digest()
        if digest is None and not getattr(sys, "frozen", False):
            digest = freeze_digest(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))))
        _CODE_DIGEST = digest[:16] if digest else "absent"
    return _CODE_DIGEST


# ──────────────────────────────────────────────────────────────────────
# THE PATCH BUILD'S CLOSURE (#880) — what ``o4_code`` keys on by default
# ──────────────────────────────────────────────────────────────────────

#: The file the freeze writes beside this module (one line: the digest).
PATCH_DIGEST_FILENAME = "patch_code.sha256"

#: ``1`` stamps and compares the whole-tree digest again (#346's key).
WHOLE_TREE_ENV = "O4_PATCH_FRESHNESS_WHOLE_TREE"

#: Where the tile build ENTERS the patch build: ``O4_Vector_Map`` calls
#: ``auto_patch.driver.generate_auto_patches`` (the per-airport worker,
#: ``auto_patch.engine_v2``, is in its closure).
PATCH_ENTRY_MODULES: tuple[str, ...] = ("auto_patch.driver",)


def _closure_module() -> dict:
    """``src/O4_Code_Closure.py``'s namespace: imported in a checkout, a
    test and a frozen engine; loaded BY PATH when a ``.spec`` executes this
    file with ``runpy`` (``src`` is not on ``sys.path`` then)."""
    try:
        import O4_Code_Closure
        return vars(O4_Code_Closure)
    except ImportError:
        return runpy.run_path(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "O4_Code_Closure.py"))


def _patch_sources(src_root: str):
    """``(name, path)`` of every module and data table the patch keys on."""
    source_path = _closure_module()["source_path"]
    for name in PATCH_CODE_MODULES:
        yield name, source_path(src_root, name)
    for rel in PATCH_DATA_FILES:
        yield rel, os.path.join(src_root, *rel.split("/"))


def patch_freeze_digest(src_root: str) -> str | None:
    """The digest of :data:`PATCH_CODE_MODULES` and :data:`PATCH_DATA_FILES`
    read under ``src_root``, or ``None`` when any is missing."""
    return _closure_module()["digest_of"](_patch_sources(src_root))


def write_patch_freeze_digest(src_root: str, out_dir: str) -> str:
    """THE FREEZE'S ACT for :func:`patch_freeze_digest`: write it to
    ``out_dir/``:data:`PATCH_DIGEST_FILENAME` and return that path.  RAISES
    ``SystemExit`` when there is no digest (a listed module has no
    source)."""
    return _closure_module()["write_digest_file"](
        out_dir, PATCH_DIGEST_FILENAME, patch_freeze_digest(src_root),
        "ERROR: could not digest the patch build's code under "
        f"{src_root!r} (provenance_code names a module or table with no "
        "source file) — refusing to freeze an engine whose patch freshness "
        "gate would have no code identity.")


def frozen_patch_digest(directory: str | None = None) -> str | None:
    """The patch digest the freeze wrote beside this module, or ``None``."""
    if directory is None:
        directory = os.path.dirname(os.path.abspath(__file__))
    return _closure_module()["read_digest"](directory, PATCH_DIGEST_FILENAME)


_PATCH_DIGEST: str | None = None


def _patch_code_digest() -> str:
    """The running engine's patch digest (16 hex), taken once per process:
    the freeze's file, else the sources beside this module, else
    ``absent``."""
    global _PATCH_DIGEST
    if _PATCH_DIGEST is None:
        digest = frozen_patch_digest()
        if digest is None and not getattr(sys, "frozen", False):
            digest = patch_freeze_digest(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))))
        _PATCH_DIGEST = digest[:16] if digest else "absent"
    return _PATCH_DIGEST


def freshness_code_digest(environ=None) -> str:
    """THE ``o4_code`` STAMP: the patch build's closure digest, or — with
    ``O4_PATCH_FRESHNESS_WHOLE_TREE=1`` — the whole tree's
    (:func:`code_digest`, #346)."""
    env = os.environ if environ is None else environ
    if str(env.get(WHOLE_TREE_ENV, "")).strip() == "1":
        return code_digest()
    return _patch_code_digest()


#: The data tables the patch build loads, as paths relative to ``src``
#: (posix), sorted: every ``.toml`` under ``src`` (the twin fails on one
#: that is not listed — the whole-tree digest covered them all).
PATCH_DATA_FILES: tuple[str, ...] = (
    "auto_patch_v2/classify/rules.toml",
    "auto_patch_v2/law/emit.toml",
    "auto_patch_v2/law/families.toml",
    "auto_patch_v2/law/flat_site.toml",
    "auto_patch_v2/law/precedence.toml",
    "auto_patch_v2/law/rulesets.toml",
    "auto_patch_v2/law/structures.toml",
    "auto_patch_v2/law/zones.toml",
)

#: The static import closure of :data:`PATCH_ENTRY_MODULES` under ``src``
#: with the packages above its modules and their imports (``O4_Code_Closure.closure(...,
#: packages=True)``), sorted.  Held by ``tests/test_patch_code_closure.py``;
#: when it fails, the message names the modules to add or drop.
PATCH_CODE_MODULES: tuple[str, ...] = (
    "O4_Airport_Apt_Identity",
    "O4_Airport_Batch",
    "O4_Airport_Dico",
    "O4_Airport_Elevation_Insets",
    "O4_Airport_Fade_Masks",
    "O4_Airport_Index",
    "O4_Airport_Modes",
    "O4_Airport_Rank",
    "O4_Airport_Utils",
    "O4_Authenticated_Sessions",
    "O4_Bank_Annulus",
    "O4_Bathymetry",
    "O4_Bathymetry_Band",
    "O4_Build_Info",
    "O4_Cfg_Module_Values",
    "O4_Cfg_Vars",
    "O4_Coastal_Foam_Edge",
    "O4_Code_Closure",
    "O4_Color_Harmonization",
    "O4_Config_Utils",
    "O4_Console_Encoding",
    "O4_Coral_Atlas",
    "O4_DDS_Encode",
    "O4_DDS_File",
    "O4_DDS_Mips",
    "O4_DDS_Refine",
    "O4_DEM_Utils",
    "O4_DSFTool",
    "O4_DSF_Utils",
    "O4_Default_Terrain_Map",
    "O4_Elevation_Level",
    "O4_Engine_Stderr_Log",
    "O4_External_Writes",
    "O4_File_Lock",
    "O4_File_Names",
    "O4_Geo_Utils",
    "O4_Held_File",
    "O4_Http_Pushback",
    "O4_Imagery_Async",
    "O4_Imagery_Certs",
    "O4_Imagery_Fetch",
    "O4_Imagery_Progress",
    "O4_Imagery_Utils",
    "O4_Mask_Utils",
    "O4_Mesh_IO",
    "O4_Mesh_Utils",
    "O4_Num_Text",
    "O4_OSM_Extract_Filter",
    "O4_OSM_Extracts",
    "O4_OSM_Utils",
    "O4_Object_Stage_Code",
    "O4_Overlay_Utils",
    "O4_Parallel_Utils",
    "O4_Process_Liveness",
    "O4_Proj_Runtime",
    "O4_Scenery_Links",
    "O4_Scenery_Packs",
    "O4_Sea_Nodata_Fill",
    "O4_Settings_Model",
    "O4_Step_Code",
    "O4_Step_Reuse",
    "O4_Stopped_Build",
    "O4_Text_Files",
    "O4_Tile_Failures",
    "O4_Tile_Info",
    "O4_Tile_Staging",
    "O4_Tile_Utils",
    "O4_Triangle_Binary",
    "O4_Triangle_IO",
    "O4_Triangle_Run",
    "O4_UI_Utils",
    "O4_Unmounted_Links",
    "O4_Unpatched_Airports",
    "O4_Vector_Map",
    "O4_Vector_Utils",
    "O4_Version",
    "auto_patch",
    "auto_patch.agp_reader",
    "auto_patch.apt_dat_reader",
    "auto_patch.build_support",
    "auto_patch.config",
    "auto_patch.driver",
    "auto_patch.dsf_reader",
    "auto_patch.engine_v2",
    "auto_patch.flat_site_mode",
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
    "auto_patch.osm_aeroway",
    "auto_patch.post_mesh",
    "auto_patch.progress",
    "auto_patch.provenance",
    "auto_patch.provenance_code",
    "auto_patch.provenance_env",
    "auto_patch.selection",
    "auto_patch_v2",
    "auto_patch_v2.airport",
    "auto_patch_v2.airport.anchor_rule",
    "auto_patch_v2.airport.approach",
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
    "auto_patch_v2.airport.cifp",
    "auto_patch_v2.airport.cluster_profile",
    "auto_patch_v2.airport.contact",
    "auto_patch_v2.airport.contents",
    "auto_patch_v2.airport.deck_signature",
    "auto_patch_v2.airport.dem",
    "auto_patch_v2.airport.dem_production",
    "auto_patch_v2.airport.dem_record",
    "auto_patch_v2.airport.dem_shared",
    "auto_patch_v2.airport.dem_witness",
    "auto_patch_v2.airport.door_wells",
    "auto_patch_v2.airport.dsf",
    "auto_patch_v2.airport.dsf_commands",
    "auto_patch_v2.airport.dsf_write",
    "auto_patch_v2.airport.extension_cache",
    "auto_patch_v2.airport.facade",
    "auto_patch_v2.airport.file_hash",
    "auto_patch_v2.airport.file_witness",
    "auto_patch_v2.airport.flat_site",
    "auto_patch_v2.airport.flat_site_prep",
    "auto_patch_v2.airport.flat_site_read",
    "auto_patch_v2.airport.footprint_carry",
    "auto_patch_v2.airport.footprint_connector",
    "auto_patch_v2.airport.footprint_seats",
    "auto_patch_v2.airport.footprint_unit",
    "auto_patch_v2.airport.frame_entry",
    "auto_patch_v2.airport.grade_ledger",
    "auto_patch_v2.airport.jetways",
    "auto_patch_v2.airport.line_object",
    "auto_patch_v2.airport.load",
    "auto_patch_v2.airport.obj8",
    "auto_patch_v2.airport.obj8_clip",
    "auto_patch_v2.airport.obj8_drape",
    "auto_patch_v2.airport.obj8_grade",
    "auto_patch_v2.airport.obj8_roof",
    "auto_patch_v2.airport.obj8_split",
    "auto_patch_v2.airport.object_cut",
    "auto_patch_v2.airport.object_pavement",
    "auto_patch_v2.airport.object_plan",
    "auto_patch_v2.airport.object_stage_reuse",
    "auto_patch_v2.airport.osm",
    "auto_patch_v2.airport.pack",
    "auto_patch_v2.airport.pack_art",
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
    "auto_patch_v2.airport.ramp_feet",
    "auto_patch_v2.airport.reader_work",
    "auto_patch_v2.airport.rebake_plan",
    "auto_patch_v2.airport.rebake_screen",
    "auto_patch_v2.airport.riders",
    "auto_patch_v2.airport.road_descent",
    "auto_patch_v2.airport.road_profile",
    "auto_patch_v2.airport.road_ramp",
    "auto_patch_v2.airport.road_ways",
    "auto_patch_v2.airport.scatter",
    "auto_patch_v2.airport.sheet_chain",
    "auto_patch_v2.airport.skirt",
    "auto_patch_v2.airport.slab_drape",
    "auto_patch_v2.airport.slab_faces",
    "auto_patch_v2.airport.slab_plates",
    "auto_patch_v2.airport.stage_cache",
    "auto_patch_v2.airport.sunken_ramp",
    "auto_patch_v2.airport.sunken_roads",
    "auto_patch_v2.airport.thin_plates",
    "auto_patch_v2.airport.topology_cache",
    "auto_patch_v2.airport.tunnel_objects",
    "auto_patch_v2.airport.tunnel_walls",
    "auto_patch_v2.airport.unpatched_pack",
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
    "auto_patch_v2.classify.gap_terrace",
    "auto_patch_v2.classify.lot_roads",
    "auto_patch_v2.classify.neck",
    "auto_patch_v2.classify.open_default",
    "auto_patch_v2.classify.pad_road_exit",
    "auto_patch_v2.classify.pad_touch",
    "auto_patch_v2.classify.ramp_runout",
    "auto_patch_v2.classify.retaining_wall",
    "auto_patch_v2.classify.ribbon_mint",
    "auto_patch_v2.classify.roles",
    "auto_patch_v2.classify.rules",
    "auto_patch_v2.classify.sources",
    "auto_patch_v2.classify.taxi_letter",
    "auto_patch_v2.constraints",
    "auto_patch_v2.constraints.apron",
    "auto_patch_v2.constraints.apron_shelf",
    "auto_patch_v2.constraints.apron_trend",
    "auto_patch_v2.constraints.assembly",
    "auto_patch_v2.constraints.ceiling",
    "auto_patch_v2.constraints.channel",
    "auto_patch_v2.constraints.cluster_pad",
    "auto_patch_v2.constraints.contiguity",
    "auto_patch_v2.constraints.eat",
    "auto_patch_v2.constraints.end_lip",
    "auto_patch_v2.constraints.flat_site",
    "auto_patch_v2.constraints.foot_rows",
    "auto_patch_v2.constraints.gap_follow",
    "auto_patch_v2.constraints.geometry",
    "auto_patch_v2.constraints.groundside",
    "auto_patch_v2.constraints.hard_plane",
    "auto_patch_v2.constraints.jetway_strip",
    "auto_patch_v2.constraints.junction_mesh",
    "auto_patch_v2.constraints.no_step",
    "auto_patch_v2.constraints.pad_frontage_gs",
    "auto_patch_v2.constraints.pad_fronting",
    "auto_patch_v2.constraints.pad_ramp",
    "auto_patch_v2.constraints.pad_relief",
    "auto_patch_v2.constraints.pad_road_reach",
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
    "auto_patch_v2.constraints.slab_weld",
    "auto_patch_v2.constraints.stretches",
    "auto_patch_v2.constraints.strips",
    "auto_patch_v2.constraints.structures",
    "auto_patch_v2.constraints.surface_trend",
    "auto_patch_v2.constraints.taxi",
    "auto_patch_v2.constraints.taxi_trend",
    "auto_patch_v2.constraints.taxi_trend_cap",
    "auto_patch_v2.constraints.transverse",
    "auto_patch_v2.constraints.trend",
    "auto_patch_v2.constraints.water",
    "auto_patch_v2.constraints.weld_floor",
    "auto_patch_v2.constraints.zones",
    "auto_patch_v2.emit",
    "auto_patch_v2.emit.graded",
    "auto_patch_v2.emit.osm_adapter",
    "auto_patch_v2.emit.rebake",
    "auto_patch_v2.emit.road_join",
    "auto_patch_v2.emit.surface",
    "auto_patch_v2.emit.terrain_edge",
    "auto_patch_v2.geom",
    "auto_patch_v2.geom.base_slab",
    "auto_patch_v2.geom.cluster_outline",
    "auto_patch_v2.geom.containment",
    "auto_patch_v2.geom.core_clamp",
    "auto_patch_v2.geom.coverage",
    "auto_patch_v2.geom.feet_graph",
    "auto_patch_v2.geom.feet_mst",
    "auto_patch_v2.geom.pad_evidence",
    "auto_patch_v2.geom.parts",
    "auto_patch_v2.geom.proportions",
    "auto_patch_v2.geom.ramp_grade",
    "auto_patch_v2.geom.ramp_profile",
    "auto_patch_v2.geom.rotated_rect",
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
    "auto_patch_v2.law.witness",
    "auto_patch_v2.model",
    "auto_patch_v2.model.airport",
    "auto_patch_v2.model.constraint_codec",
    "auto_patch_v2.model.constraints",
    "auto_patch_v2.model.end_area",
    "auto_patch_v2.model.frame",
    "auto_patch_v2.model.ground_fit",
    "auto_patch_v2.model.hard_plane",
    "auto_patch_v2.model.islands",
    "auto_patch_v2.model.jetway",
    "auto_patch_v2.model.map_memo",
    "auto_patch_v2.model.pad_terrace",
    "auto_patch_v2.model.placement",
    "auto_patch_v2.model.planar",
    "auto_patch_v2.model.platform",
    "auto_patch_v2.model.pulse",
    "auto_patch_v2.model.rebake",
    "auto_patch_v2.model.registries",
    "auto_patch_v2.model.structures",
    "auto_patch_v2.model.threshold_datum",
    "auto_patch_v2.pipeline",
    "auto_patch_v2.pipeline.authored_seats",
    "auto_patch_v2.pipeline.back_cache",
    "auto_patch_v2.pipeline.build",
    "auto_patch_v2.pipeline.capture_state",
    "auto_patch_v2.pipeline.constraint_records",
    "auto_patch_v2.pipeline.emit_records",
    "auto_patch_v2.pipeline.emit_stage",
    "auto_patch_v2.pipeline.front_cache",
    "auto_patch_v2.pipeline.late_records",
    "auto_patch_v2.pipeline.late_stage",
    "auto_patch_v2.pipeline.planar_report",
    "auto_patch_v2.pipeline.prefix",
    "auto_patch_v2.pipeline.publication",
    "auto_patch_v2.pipeline.rebake_inputs",
    "auto_patch_v2.pipeline.ribbon_steps",
    "auto_patch_v2.pipeline.runway_report",
    "auto_patch_v2.pipeline.seam_report",
    "auto_patch_v2.pipeline.shapes",
    "auto_patch_v2.pipeline.solve_record",
    "auto_patch_v2.pipeline.stage_code",
    "auto_patch_v2.pipeline.stage_one_map",
    "auto_patch_v2.pipeline.terrace_witness",
    "auto_patch_v2.pipeline.verify_stage",
    "auto_patch_v2.pipeline.xplat",
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
    "auto_patch_v2.planar.cluster",
    "auto_patch_v2.planar.covered_ground",
    "auto_patch_v2.planar.door_ramps",
    "auto_patch_v2.planar.edges",
    "auto_patch_v2.planar.group",
    "auto_patch_v2.planar.index",
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
    "auto_patch_v2.planar.zones",
    "auto_patch_v2.solve",
    "auto_patch_v2.solve.api",
    "auto_patch_v2.solve.design",
    "auto_patch_v2.solve.design_assemble",
    "auto_patch_v2.solve.design_edge",
    "auto_patch_v2.solve.design_ground",
    "auto_patch_v2.solve.design_junction",
    "auto_patch_v2.solve.design_qp",
    "auto_patch_v2.solve.design_report",
    "auto_patch_v2.solve.design_roles",
    "auto_patch_v2.solve.design_stage",
    "auto_patch_v2.solve.feasibility",
    "auto_patch_v2.solve.flex",
    "auto_patch_v2.solve.ground_band",
    "auto_patch_v2.solve.linear",
    "auto_patch_v2.solve.pin_yield",
    "auto_patch_v2.solve.project",
    "auto_patch_v2.solve.project_strip",
    "auto_patch_v2.solve.rows",
    "auto_patch_v2.solve.wall_cut",
    "auto_patch_v2.verify",
    "auto_patch_v2.verify.census",
    "auto_patch_v2.verify.channel",
    "auto_patch_v2.verify.chord_work",
    "auto_patch_v2.verify.contiguity",
    "auto_patch_v2.verify.cutback",
    "auto_patch_v2.verify.eat",
    "auto_patch_v2.verify.frame",
    "auto_patch_v2.verify.frontage",
    "auto_patch_v2.verify.jetway",
    "auto_patch_v2.verify.keepout",
    "auto_patch_v2.verify.no_step",
    "auto_patch_v2.verify.pads",
    "auto_patch_v2.verify.pins",
    "auto_patch_v2.verify.roads",
    "auto_patch_v2.verify.runway",
    "auto_patch_v2.verify.runway_mean_slope",
    "auto_patch_v2.verify.runway_witness",
    "auto_patch_v2.verify.steps",
    "auto_patch_v2.verify.strips",
    "auto_patch_v2.verify.structures",
    "auto_patch_v2.verify.transverse",
    "auto_patch_v2.verify.within",
    "elevation_access",
    "elevation_access.base",
    "elevation_access.base_fallback",
    "elevation_access.base_seam",
    "elevation_access.base_tiles",
    "elevation_access.capabilities",
    "elevation_access.definitions",
    "elevation_access.discovery",
    "elevation_access.downloads",
    "elevation_access.failures",
    "elevation_access.fetch_scratch",
    "elevation_access.fetch_slots",
    "elevation_access.gdal_support",
    "elevation_access.las_tiles",
    "elevation_access.registry",
    "elevation_access.stac_assets",
    "elevation_access.strategies",
    "elevation_access.strategies.aoi_zip_download",
    "elevation_access.strategies.arcgis_export_image",
    "elevation_access.strategies.arcgis_feature_tiles",
    "elevation_access.strategies.arcgis_lerc_tiles",
    "elevation_access.strategies.authenticated_token_search",
    "elevation_access.strategies.coordinate_named_url_list",
    "elevation_access.strategies.coral_atlas_library",
    "elevation_access.strategies.cwcb_lidar_api",
    "elevation_access.strategies.degree_cog_base_tile",
    "elevation_access.strategies.degree_named_cog",
    "elevation_access.strategies.direct_cog",
    "elevation_access.strategies.geojson_tile_index",
    "elevation_access.strategies.hgt_archive_drop",
    "elevation_access.strategies.las_tile_index",
    "elevation_access.strategies.manual_download",
    "elevation_access.strategies.os_grid_bucket",
    "elevation_access.strategies.stac",
    "elevation_access.strategies.static_stac",
    "elevation_access.strategies.tile_grid_http",
    "elevation_access.strategies.tnm_cog",
    "elevation_access.strategies.usgs_seamless",
    "elevation_access.strategies.viewfinder_zip",
    "elevation_access.strategies.wcs",
    "elevation_access.strategies.wcs_kvp",
    "elevation_access.strategies.wfs_tile_index",
    "elevation_access.strategies.xyz_archive_drop",
    "elevation_access.strategies.xyz_text_tiles",
    "elevation_access.vertical_units",
    "elevation_access.warp",
    "o4_engine",
    "o4_engine.download_meter",
    "o4_engine.events",
    "o4_engine.parallel",
    "o4_engine.session",
    "o4_engine.task_meter",
    "o4_engine.tile_time_model",
)
