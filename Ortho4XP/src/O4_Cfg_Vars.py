""""Ortho4XP configuration variables."""

import os

import O4_OSM_Utils as OSM

# THE ROAD GRADE CAP IS ONE CONSTANT, NOT TWO (linear-transport census
# #115/#116), AND SINCE 2026-09-17 THAT CONSTANT IS THE V2 LAW TABLE'S
# (lane ``v1retire`` round 1, session ruling (c) of the stage-B brief).
# ``road_grade_limit`` below is the user-facing knob whose DEFAULT is the
# engine's own ground-vehicle grade limit — ``[common.roles]``
# ``service_road.longitudinal`` in ``auto_patch_v2/law/rulesets.toml``
# (VDOT GS-9, owner 2026-08-03), which ``law/emit.toml``'s road section
# already names as "ONE constant with the core's ``road_grade_limit``
# default".  It used to be read from
# ``auto_patch.config.SERVICE_ROAD_MAX_GRADE``, i.e. out of the v1
# engine; for v2 the value lives in the law table, so the READER moves
# rather than the value being re-spelled (a second 0.08 here would be
# the silently-different-copy defect the moment one of them moved).
# The DEFAULT ruleset is the right scope: this is a registry default,
# not an airport's law, and every ruleset inherits ``common.roles``
# unless it states its own.
def _road_grade_cap_from_law() -> float:
    from auto_patch_v2.law import tables as _v2_tables
    return float(_v2_tables.role_cap(
        _v2_tables.load_default(), "service_road").longitudinal)


_ROAD_GRADE_CAP = _road_grade_cap_from_law()


# THE NEIGHBOURHOOD CLAMP'S LAW IS THE SAME TABLE (owner RULINGS
# 2026-09-18n; spec ``linear-transport-redesign-spec.md`` §2-SUPPLEMENT
# S.4 row 16).  ONE definition, both engines: the run-out, the deviation
# budget, the gradeability ceiling and the PER-CLASS caps live in
# ``auto_patch_v2/law/emit.toml`` ``[road_profile]`` and the core reads
# them HERE — never as literals beside the clamp.
def road_neighbourhood_law() -> dict:
    """``{runout_m, budget_m, cap_ceiling, class_caps}`` from the law
    table (``O4_Vector_Utils.clamp_road_network`` / v2's
    ``airport/road_profile``)."""
    from auto_patch_v2.law import tables as _v2_tables
    rp = _v2_tables.load_default().tables.emit.road_profile
    return {
        "runout_m": float(rp.runout_m),
        "budget_m": float(rp.budget_m),
        "cap_ceiling": float(rp.cap_ceiling),
        "class_caps": {str(k): float(v) for k, v in rp.class_caps.items()},
    }


global_prefix = "global_"
overpass_server_keys = sorted(OSM.overpass_servers.keys())
overpass_server_values = (
    ["random"] + overpass_server_keys if len(overpass_server_keys) > 1 else overpass_server_keys
)
overpass_server_default = (
    "random" if len(overpass_server_keys) != 1
    else overpass_server_keys[0]
)

cfg_app_vars = {
    # App
    "verbosity": {
        "module": "UI",
        "type": int,
        "default": 1,
        "values": (0, 1, 2, 3),
        "value_labels": {
            0: "Quiet - errors only",
            1: "Normal progress",
            2: "Detailed progress",
            3: "Debug - everything",
        },
        "hint": "How much build information is printed to the console. Critical errors are always reported and logged regardless of this setting.",
    },
    "cleaning_level": {
        "module": "UI",
        "type": int,
        "default": 1,
        "values": (0, 1, 2, 3),
        "value_labels": {
            0: "Keep every file (DEM iteration)",
            1: "Keep files to redo any step",
            2: "Lean - rebuilds restart from step 1",
            3: "Minimal - X-Plane files + config only",
        },
        "hint": "Which build files are deleted after a successful tile build. X-Plane itself only reads the .dsf, terrain/ and textures/ folders - everything else exists to speed up partial rebuilds, so the higher levels trade rebuild convenience for disk space. Iterated DEM refinement requires keeping every file.",
    },
    "overpass_server_choice": {
        "module": "OSM",
        "type": str,
        "default": overpass_server_default,
        "values": overpass_server_values,
        "hint": "OSM Overpass server used to grab vector data. Servers are specified in overpass_servers.txt.",
    },
    "osm_regional_extracts": {
        "type": bool,
        "default": True,
        "hint": "Serve OpenStreetMap vector data from locally stored Geofabrik regional extracts when available, falling back to the Overpass servers. The extract for a region is fetched once (typically a few hundred megabytes) and every build in that region then reads OSM data locally - no waiting on shared OSM servers, no rate limits.",
    },
    "osm_extract_foreground_download": {
        "type": bool,
        "default": True,
        "hint": "When a build needs a regional extract that is not stored yet, download it immediately and wait for it (the Geofabrik servers are fast and unthrottled, so this is almost always quicker than the Overpass fallback - a first Cairo-tile build spent 21 minutes on throttled Overpass queries while the Egypt extract finished downloading one minute in). Off: the first build in a region uses Overpass while the extract downloads in the background, as before.",
    },
    "osm_extract_refresh_days": {
        "type": float,
        "default": 180.0,
        "hint": "How old, in days, a stored regional extract may grow before background maintenance re-downloads it at application start. OpenStreetMap edits reach scenery slowly, so the default trades roughly half a year of staleness for far fewer multi-hundred-megabyte downloads.",
    },
    "base_elevation_source": {
        "module": "DEM",
        "type": str,
        "default": "auto",
        "hint": 'Which base (tile-wide) elevation source to use when no custom_dem is set. "auto" (default) ranks the enabled role=base definition files in Providers/Elevation/<CODE>.elv that cover the tile by priority, capped at 1 arc-second (for example the USGS national elevation dataset over the continental United States, Viewfinderpanoramas elsewhere). A provider code (for example "NED13") or a legacy keyword (View, SRTM, NED1, NED1/3, ALOS) pins one source explicitly.',
    },
    "skip_downloads": {
        "module": "TILE",
        "type": bool,
        "default": False,
        "hint": "Will only build the DSF and TER files but not the textures (neither download nor convert). This could be useful in cases where imagery cannot be shared.",
    },
    "skip_converts": {
        "module": "TILE",
        "type": bool,
        "default": False,
        "hint": "Imagery will be downloaded but not converted from jpg to dds. Some user prefer to postprocess imagery with third party softwares prior to the dds conversion. In that case Step 3 needs to be run a second time after the retouch work.",
    },
    "max_download_slots": {
        "module": "TILE",
        "type": int,
        "default": 0,
        "values": (0, 1, 2, 3, 4, 6, 8),
        "value_labels": {
            0: "Auto — scale to this machine",
            1: "1 (historic behaviour)",
        },
        "hint": "How many orthophotos are constructed in parallel; each uses 16 request threads by default (unless the provider file says otherwise). Auto is currently two — downloads are network-bound, so processor cores are irrelevant here. If running Ortho4XP from an external drive, errors may occur at settings higher than 4; set an explicit 1 to restore the historic behaviour.",
    },
    "max_convert_slots": {
        "module": "TILE",
        "type": int,
        "default": 0,
        "values": (0, 1, 2, 4, 6, 8, 12, 16),
        "value_labels": {
            0: "Auto — scale to this machine",
        },
        "hint": "Number of parallel workers for dds conversion. Auto: every processor core but two, at least two, at most sixteen. Conversion is CPU-bound, so Auto tracks your machine.",
    },
    "max_build_slots": {
        "type": int,
        "default": 0,
        "values": (0, 1, 2, 3, 4, 5, 6, 7, 8),
        "value_labels": {
            0: "Auto — scale to this machine",
            1: "1 (one tile at a time)",
            2: "2",
            3: "3",
            4: "4",
            5: "5",
            6: "6",
            7: "7",
            8: "8",
        },
        "hint": "How many tiles build at the same time when several are queued. 0 (the default) means Auto: one tile per processor core, reduced only when the machine has too little free memory to feed that many workers. Memory is guarded per STEP rather than per slot — a run never projects more than eighty per cent of the memory the machine can hand out onto the steps it has started, so the multi-gigabyte rasters of the fine elevation detail levels are scheduled around each other automatically. Politeness to the OpenStreetMap and imagery servers is handled separately — at most four tiles fetch from either at once however many slots you run, and a tile whose data is already downloaded never waits for that budget — so extra slots buy processor parallelism only. Explicit values are honoured above or below Auto. 1 builds tiles one after another in the application process (the historic behaviour); higher values run each tile in its own worker process. Parallel conversion workers automatically share the processor between concurrent tiles.",
    },
    "check_tms_response": {
        "module": "IMG",
        "type": bool,
        "default": True,
        "hint": "When set, internal server errors (HTTP [500] and the likes) yields new requests, if not a white texture is used in place.",
    },
    "http_timeout": {
        "module": "IMG",
        "type": float,
        "default": 10.0,
        "hint": "Delay before we decide that a http request is timed out.",
    },
    "max_connect_retries": {
        "module": "IMG",
        "type": int,
        "default": 5,
        "hint": "How much times do we try again after a failed connection for imagery request. Only used if check_tms_response is set to True.",
    },
    "max_baddata_retries": {
        "module": "IMG",
        "type": int,
        "default": 5,
        "hint": "How much times do we try again after an internal server error for an imagery request. Only used if check_tms_response is set to True.",
    },
    "ovl_exclude_pol": {
        "module": "OVL",
        "type": list,
        "default": [0],
        "hint": 'Indices of polygon types which one would like to left aside in the extraction of overlays. The list of these indices in front of their name can be obtained by running the "extract overlay" process with verbosity = 2 (skip facades that can be numerous) or 3. Index 0 corresponds to beaches in Global and HD sceneries. Strings can be used in places of indices, in that case any polygon_def that contains that string is excluded, and the string can begin with a ! to invert the matching. As an exmaple, ["!.for"] would exclude everything but forests.',
    },
    "ovl_exclude_net": {
        "module": "OVL",
        "type": list,
        "default": [],
        "hint": "Indices of road types which one would like to left aside in the extraction of overlays. The list of these indices is can be in the roads.net file within X-Plane Resources, but some sceneries use their own corresponding net definition file. Powerlines have index 22001 in XP11 roads.net default file.",
    },
    "custom_scenery_dir": {
        "type": str,
        "default": "",
        "hint": 'Your X-Plane Custom Scenery. Used only for "1-click" creation (or deletion) of symbolic links from Ortho4XP tiles to there.',
    },
    "custom_overlay_src": {
        "module": "OVL",
        "type": str,
        "default": "",
        "hint": "The directory containing the sceneries with the overlays you would like to extract. You need to select the level of directory just _ABOVE_ Earth nav data.",
    },
    "custom_overlay_src_alternate": {
        "module": "OVL",
        "type": str,
        "default": "",
        "hint": "If sceneries with overlays are not found in custom_overlay_src, set an alternate directory to search.",
    },
    "auto_patch_boundary": {
        "type": str,
        "default": "Ask",
        "values": ("Ask", "Build adjacent", "Skip patch"),
        "value_labels": {
            "Ask": "Ask me each time",
            "Build adjacent": "Build the adjacent tiles too",
            "Skip patch": "Skip those airports' patches",
        },
        # APP-level, not a tile var, deliberately (spec §C.4): under
        # RULINGS 2026-09-18a a tile var is frozen per tile and would need
        # write-through, and this is a preference about how the USER IS
        # ASKED, not a property of a tile.
        "hint": 'What to do when an airport\'s runways or taxiways cross into a 1 degree tile you are not building. Its elevation patch needs the neighbouring tile\'s terrain, so either that tile is built too or the airport gets no patch this run. "Ask me each time" (default) shows one dialog per build, with "build the adjacent tiles" preselected. When nobody can be asked - a command-line build, or an older front end - the answer is always to SKIP those airports\' patches, loudly: an unattended run never grows its own tile list.',
    },
    "cifp_data_path": {
        "type": str,
        "default": "",
        "hint": "Path to CIFP/AIRAC aeronautical data directory (contains .dat files per airport). If empty, Ortho4XP will look in your X-Plane installation under 'Custom Data/CIFP/'. Set this to use a different data source such as Navigraph.",
    },
}

cfg_tile_vars = {
    # Auto-patch
    "auto_patch": {
        "type": str,
        "default": "ICAO",
        "values": ("None", "ICAO", "All"),
        "value_labels": {
            "None": "Off",
            "ICAO": "Airports with ICAO codes",
            "All": "All airports",
        },
        "hint": 'Controls Ortho4XP auto-generation of runway slope patches from CIFP/AIRAC data. Auto-patches provide accurate threshold-anchored elevation profiles and are overridden by any manual patches. "ICAO" (default) only patches airports with a 4-letter ICAO code, "All" patches every airport found in CIFP, "None" disables auto-patching entirely.',
    },
    # ── THE SOLVE MODEL: RETIRED (owner RULINGS 2026-09-13bh) ─────────
    # ``solve_model`` ("Airport elevation solve", Iterative /
    # Constructive) was v1's solver switch: the two elevation solves that
    # shipped side by side under ``docs/specs/constructive-solve-spec.md``.
    # NOTHING IN V2 READS IT — v2 solves the whole airport surface in one
    # linear program and there is no second solve to select.  Removed
    # exactly as ``auto_patch_engine`` was in stage A (RULINGS
    # 2026-09-13az): the key lives on only in ``retired_cfg_keys`` below,
    # where the readers DELETE it from any cfg still carrying it (RULINGS
    # 2026-09-13a (2)) — a stale ``solve_model=constructive`` line is
    # never honoured and never warned about.
    # ── THE AUTO-PATCH ENGINE: RETIRED (owner RULINGS 2026-09-13au,
    # stage A).  Two engines shipped side by side from 2026-09-03d; v2
    # won.  There is no setting any more — ``auto_patch.engine_v2.
    # resolved_auto_patch_engine`` returns ``"v2"`` unconditionally and
    # ``engine_v2.build_write_verify_one_v2`` is the ONE per-airport
    # build step.  The key lives on only in ``retired_cfg_keys`` below,
    # where the readers DELETE it from any cfg still carrying it
    # (RULINGS 2026-09-13a (2)): a stale ``auto_patch_engine=v1`` line is
    # never honoured and never warned about.
    # ── FLAT-SITE declaration (docs/specs/flat-site-detector-spec.md
    # section 2 (c), owner ruling 2026-08-09) ──────────────────────────
    # INTENT NEVER WAITS ON STATISTICS.  The detector measures four
    # signals and can be wrong about a site the owner knows is flat; a
    # declared airport takes the verdict ``flat_declared`` and the
    # detector still runs and records what it WOULD have said, so
    # declaration and detection stay auditable against each other
    # forever.  The flat-site mode treats ``flat_declared`` exactly as
    # ``flat_candidate``.
    # ── DECLARED FLAT SITES: RETIRED (RULINGS 2026-09-05k-2, lane
    # v2flatsite).  The ONE declared register is the v2 law table
    # ``src/auto_patch_v2/law/flat_site.toml [declared]`` (ICAO → z0 +
    # source), which both DEM prep (v1 ``flat_site.declared_flat_airports``)
    # and the v2 law read, so the two can never declare two datums.  The
    # keys live on only in ``retired_cfg_keys`` below, loudly.
    # ── DECLARED CORRIDORS: RETIRED (Round 21, owner ruling 2026-08-12
    # "LAND-CONNECTED CONTINUITY, NO DECLARATIONS").  R17-2 asked the
    # owner to type a causeway's bounding box into a per-tile cfg; the
    # law is now MEASURED — where the airport's flat-site family stands
    # on one sea-bounded land component, the land between its members
    # grades with them, for every airport and every user, with no key to
    # set.  The key lives on only in ``retired_cfg_keys`` below, so a cfg
    # that still carries the line loads with a loud no-op warning instead
    # of an error.
    "modify_custom_airports": {
        "type": bool,
        "default": True,
        "hint": (
            "Allow the auto-patch pass to modify installed custom airport "
            "packages. After the mesh is rebuilt, 3-D objects of custom "
            "airports in Custom Scenery are reseated in place (originals "
            "kept as .anchor_bak backups) so they sit at the new ground "
            "elevation. Off leaves every installed package byte-identical; "
            "objects at reprofiled airports may then float above or sink "
            "into the terrain until the tile is rebuilt with this back on."
        ),
    },
    # Elevation
    "elevation_level": {
        "type": str,
        "default": "auto",
        "values": ("auto", "coastline", "90", "30", "10", "5", "1"),
        "value_labels": {
            "auto": "Auto — 90 m base + lidar at airports",
            "coastline": "Auto + coastline lidar band",
            "90": "90 m (3 arc-second)",
            "30": "30 m (1 arc-second)",
            "10": "10 m (1/3 arc-second)",
            "5": "5 m (1/6 arc-second)",
            "1": "1 m sources (1/9 arc-second grid)",
        },
        "hint": 'Tile-wide elevation detail level — the elevation analogue of the imagery zoom level. "auto" (default) uses a 90 m class base source (3 arc-second, small downloads) plus meter-class lidar insets at airports, where detail is actually visible on approach. "90" pins that 90 m base class explicitly. "coastline" keeps the automatic behaviour and additionally drapes a lidar band along the tile\'s coastlines (width set by elevation_coastline_band_km), graded by approach visibility: about 10 m detail within 20 km of an airport, 20 m out to 50 km, and 30 m beyond — lidar\'s vertical accuracy everywhere on the shore without paying for detail invisible from cruise altitudes. "30" and finer restore the 1 arc-second base class and additionally fetch the finest wide-area elevation source covering the tile (for example national lidar services) warped to that ground resolution over the whole tile, densifying the working elevation grid to match: 30 m = 1 arc-second, 10 m = 1/3, 5 m = 1/6, 1 m = 1/9 arc-second (about 3.4 m posting, the practical whole-tile grid ceiling; airports keep their finer insets on top). Levels never coarsen what the automatic behaviour would have chosen, and are capped to the finest source actually covering the tile, so an over-ambitious level gracefully has no effect. Higher levels mean substantially larger downloads, working files and memory: the working raster alone is roughly 0.5 GB at 10 m, 2 GB at 5 m and 4 GB at 1 m, with peak memory several times that, and more mesh triangles unless curvature_tol is raised. Useful for islands and mountainous tiles where 30 m relief is visibly too coarse. An explicit (non-auto) base_elevation_source always wins over the level\'s base-class preference.',
    },
    "elevation_coastline_band_km": {
        "type": float,
        "default": 5.0,
        "hint": 'Width in kilometres of the lidar band along coastlines fetched by the "coastline" elevation level, measured inland (and seaward) from the OpenStreetMap coastline. Only used when elevation_level is "coastline".',
    },
    # Vector
    "apt_smoothing_pix": {
        "type": int,
        "default": 8,
        "hint": "How much gaussian blur is applied to the elevation raster for the look up of altitude over airports. Unit is the elevation raster pixel size.",
    },
    "apt_smoothing_auto": {
        "type": bool,
        "default": True,
        "hint": "When set, the airport smoothing radius (apt_smoothing_pix) is scaled per airport to the resolution of the finest elevation source actually covering that airport, never exceeding apt_smoothing_pix. Airports covered by coarse global data keep the full radius (identical to today); airports covered by high resolution elevation insets are blurred less or not at all. Unset restores the fixed radius for every airport.",
    },
    "airport_elevation_insets": {
        "type": str,
        "default": "ICAO",
        "values": ("None", "ICAO", "All"),
        "value_labels": {
            "None": "Off",
            "ICAO": "Airports with ICAO codes",
            "All": "All airports",
        },
        # This key was a BOOL until 2026-09-18 (RULINGS 18c/18e).  The cfg
        # reader maps an existing line loudly, once, on read; the runtime
        # backstop for objects built some other way is
        # ``auto_patch.selection.resolved_inset_mode``.
        "legacy_values": {
            "True": "ICAO", "true": "ICAO", "1": "ICAO",
            "False": "None", "false": "None", "0": "None",
        },
        "hint": 'Which airports get automatic high resolution elevation insets: meter-class public elevation (for example the United States Geological Survey 3D Elevation Program) fetched for the airport neighbourhood and overlaid on the base elevation raster before the mesh is built. "Airports with ICAO codes" (default) insets only airports with a 4-letter ICAO code, "All airports" insets every named aerodrome on the tile, and "Off" fetches none and bakes none (the build is byte-identical to the feature being absent). Requires the GDAL python bindings and network access; when either is missing the feature disables itself.',
    },
    "airport_inset_water": {
        "type": bool,
        "default": False,
        "hint": "RETIRED (2026-07-26) and ignored: the hydro-flat basin scan of lidar insets is no longer run — water comes from OpenStreetMap / custom data only. The variable is kept so existing config files parse; its value has no effect.",
    },
    "airport_elevation_providers": {
        "type": str,
        "default": "auto",
        "hint": 'Which elevation inset providers to consider, referring to the definition files in Providers/Elevation/<CODE>.elv. "auto" (default) uses every enabled provider ranked by its priority field. An explicit comma-separated list of provider codes (for example "USGS3DEP") pins or filters providers, which is useful for testing.',
    },
    "airport_elevation_level": {
        "type": str,
        "default": "auto",
        "values": ("auto", "0.5", "1", "5", "10", "30"),
        "value_labels": {
            "auto": "Auto — best available (down to 0.5 m)",
            "0.5": "0.5 m",
            "1": "1 m",
            "5": "5 m",
            "10": "10 m",
            "30": "30 m",
        },
        "hint": 'Airport elevation detail level — the ground resolution in metres to which fetched airport elevation insets are warped and stored. "auto" (default) uses each provider\'s best available native resolution, never finer than 0.5 m. A numeric level pins the warp target instead: coarser levels store fewer bytes and warp faster (a 1 m inset stores roughly nine times the bytes of a 3 m one) at the cost of fine relief. A level FINER than what a provider publishes is raised to that provider\'s native resolution — interpolating 30 m data onto a 3 m grid adds no detail while costing ~100x the disk — so a fine level only takes effect where a source genuinely offers it. Cached insets are recycled as-is until refreshed, except one stored finer than its source publishes, which is regenerated at native posting.',
    },
    "airport_elevation_inset_margin_m": {
        "type": float,
        "default": 2000.0,
        "hint": "How far beyond each airport's smoothing mask, in metres, the elevation inset bounding box is expanded. The clearance band and custom object neighbourhoods extend well past the boundary polygon, so a generous margin is deliberate.",
    },
    "airport_elevation_inset_feather_m": {
        "type": float,
        "default": 60.0,
        "hint": "Width in metres of the blend band over which a baked elevation inset ramps from its own values to the underlying base elevation at the inset edge, avoiding a cliff at the seam.",
    },
    "working_grid_arc_seconds": {
        "type": str,
        "default": "auto",
        "hint": 'Spacing of the working elevation grid (the .alt raster the mesher reads). "auto" (default) keeps the historic 1 arc-second grid when the tile has no cached airport elevation insets (byte-identical to before), and densifies to the coarsest of 1/2 or 1/3 arc-second whose ideal-bake error at the stored acceptance probes stays within 1 metre when insets are present, so meter-class airport relief is not lost to the grid floor. An explicit value ("1", "1/2", "1/3") pins the spacing.',
    },
    "road_level": {
        "type": str,
        "default": "auto",
        "values": ("auto", "0", "1", "2", "3", "4", "5"),
        "value_labels": {
            "auto": "Auto — major roads tile-wide, all roads near airports",
            "0": "No roads",
            "1": "Major roads + railways",
            "2": "+ tertiary roads",
            "3": "+ residential streets",
            "4": "+ service roads",
            "5": "+ dirt tracks",
        },
        "hint": 'Allows to level the mesh along roads and railways. "auto" (default) levels major roads and railways across the whole tile (level 1) and additionally levels EVERY road and rail class (level 5 + rail sidings/spurs/trams) inside each airport\'s elevation-inset neighbourhood, where lidar terrain makes unlevelled minor roads most visible — same spirit as the elevation/imagery auto modes. Numeric levels keep the historical tile-wide behaviour: zero means nothing is included; "1" looks for banking ways among motorways, primary and secondary roads and railway tracks; "2" adds tertiary roads; "3" brings residential and unclassified roads; "4" takes service roads, and 5 finishes with tracks. Purge the small_roads / airport_small_roads cached data if you change your mind in between levels.',
    },
    "road_banking_limit": {
        "type": float,
        "default": 0.5,
        "hint": "How much sloped does a roads need to be to be in order to be included in the mesh levelling process. The value is in meters, measuring the height difference between a point in the center of a road node and its closest point on the side of the road.",
    },
    "road_grade_limit": {
        "type": float,
        "default": _ROAD_GRADE_CAP,
        "hint": "Longitudinal grade cap, as a fraction (0.08 = 8 %), for roads INSIDE an auto-patched airport's patch area, where the airport builder grades them. Outside the patch area roads follow the terrain exactly as the base engine levels them; within about 100 m of the patch a road is eased onto the patch using a grade limit for its road class (motorway 6 % … service road 20 %) and is never moved more than about 1 m off the terrain to do it.",
    },
    "lane_width": {
        "type": float,
        "default": 4.0,
        "hint": "Width (in meters) to be used for buffering that part of the road network that requires leveling.",
    },
    "max_levelled_segs": {
        "type": int,
        "default": 200000,
        "hint": "This limits the total number of roads segments included for mesh levelling, in order to keep triangle count under control in case of abundant OSM data.",
    },
    "water_simplification": {
        "type": float,
        "default": 0.0,
        "hint": "In case the OSM data for water areas would become too large, this parameter (in meter) can be used for node simplification.",
    },
    "min_area": {
        "type": float,
        "default": 0.001,
        "hint": "Minimum area (in km^2) a water patch needs to be in order to be included in the mesh as such. Contiguous water patches are merged before area computation.",
    },
    "max_area": {
        "type": float,
        "default": 200.0,
        "hint": "Any water patch larger than this quantity (in km^2) will be masked like the sea.",
    },
    "clean_bad_geometries": {
        "type": bool,
        "default": True,
        "hint": "When set, all OSM geometries are checked for self-intersection and merged between themselves in case of overlapping, allowing (hopefully!) to go around most OSM errors. This is computationally expensive, especially in places where OSM road/water data is detailed, and this is the reason for this switch, but if you are not in a hurry it is probably wise leaving it always activated.",
    },
    "mesh_zl": {
        "type": int,
        "default": 19,
        "values": (16, 17, 18, 19, 20),
        "value_labels": {
            16: "ZL16 (up to ~2.4 m/pixel imagery)",
            17: "ZL17 (up to ~1.2 m/pixel imagery)",
            18: "ZL18 (up to ~0.6 m/pixel imagery)",
            19: "ZL19 (up to ~0.3 m/pixel imagery)",
            20: "ZL20 (up to ~0.15 m/pixel imagery)",
        },
        "hint": "The mesh will be preprocessed to accept later any combination of imageries up to and including a zoomlevel equal to mesh_zl. Lower value could save a few tens of thousands triangles, but put a limitation on the maximum allowed imagery zoomlevel.",
    },
    # Mesh
    "curvature_tol": {
        "type": float,
        "default": 2.0,
        "hint": "This parameter is intrinsically linked the mesh final density. Mesh refinement is mostly based on curvature computations on the elevation data (the exact decision rule can be found in _ triunsuitable() _ in Utils/Triangle4XP.c). A higher curvature tolerance yields fewer triangles.",
    },
    "apt_curv_tol": {
        "type": float,
        "default": 0.5,
        "hint": "If smaller, it supersedes curvature_tol over airports neighbourhoods.",
    },
    "apt_curv_ext": {
        "type": float,
        "default": 0.5,
        "hint": "Extent (in km) around the airports where apt_curv_tol applies.",
    },
    "coast_curv_tol": {
        "type": float,
        "default": 1.0,
        "hint": "If smaller, it supersedes curvature_tol along the coastline.",
    },
    "coast_curv_ext": {
        "type": float,
        "default": 0.5,
        "hint": "Extent (in km) around the coastline where coast_curv_tol applies.",
    },
    "limit_tris": {
        "type": float,
        "default": 3.0,
        "hint": "If non zero, approx upper bound _in millions_ on the number of final triangles in the mesh. Note: When 0 we impose a hard limit of 5M, to keep X-Plane comfortable. For high resolution DEMS you _should_ use it.",
    },
    "min_angle": {
        "type": float,
        "default": 10.0,
        "hint": "The mesh algorithm will try to not have mesh triangles with (smallest for water / second smallest for regular land) angle less than the value (in deg) of min_angle.",
    },
    "sea_smoothing_mode": {
        "type": str,
        "default": "zero",
        "values": ["zero", "mean", "none"],
        "value_labels": {
            "zero": "Flatten sea to zero elevation",
            "mean": "Level each sea triangle (smooth)",
            "none": "Keep DEM elevations (high-res DEM)",
        },
        "hint": "Zero means that all nodes of sea triangles are set to zero elevation. With mean, some kind of smoothing occurs (triangles are levelled one at a time to their mean elevation), None (a value mostly appropriate for DEM resolution of 10m and less), positive altitudes of sea nodes are kept intact, only negative ones are brought back to zero, this avoids to create unrealistic vertical cliffs if the coastline vector data was lower res.",
    },
    "water_smoothing": {
        "type": int,
        "default": 10,
        "hint": "Number of smoothing passes over all inland water triangles (sequentially set to their mean elevation).",
    },
    "iterate": {
        "type": int,
        "default": 0,
        "hint": "Allows to refine a mesh using higher resolution elevation data of local scope only (requires Gdal), typically LIDAR data. Having an iterate number is handy to go backward one step when some choice of parameters needs to be revised. REQUIRES cleaning_level=0.",
    },
    # Masks
    "mask_zl": {
        "type": int,
        "default": 14,
        "values": (14, 15, 16),
        "value_labels": {
            14: "ZL14 - softest, least VRAM",
            15: "ZL15 - balanced",
            16: "ZL16 - sharpest, most VRAM",
        },
        "hint": "The zoomlevel at which the (sea) water masks are built. Masks are used for alpha channel, and this channel usually requires less resolution than the RGB ones, the reason for this (VRAM saving) parameter. If the coastline and elevation data are very detailed, it might be interesting to lift this parameter up so that the masks can reproduce this complexity.",
    },
    "masks_width": {
        "type": list,
        "default": 100,
        "hint": "Maximum extent of the masks perpendicularly to the coastline (rough definition). NOTE: The value is now in meters, it used to be in ZL14 pixel size in earlier verions, the scale is roughly one to ten between both.",
    },
    "inland_shore_feather_m": {
        "type": float,
        "default": 120.0,
        "hint": "How far, in meters, inland water eases from opaque orthophoto at its shoreline down to the constant ratio_water blend. The feather never continues toward open-water transparency - mapped inland water (lagoons, lakes near the coast) keeps orthos visible under water everywhere. 0 restores the historic hard shoreline. Only squares the masks step covers are feathered (inland water near the sea); far-inland lakes keep the constant blend either way.",
    },
    "masking_mode": {
        "type": str,
        "default": "sand",
        "values": ["sand", "rocks", "3steps"],
        "value_labels": {
            "sand": "Sand - wide, soft beach fade",
            "rocks": "Rocks - narrow, abrupt fade",
            "3steps": "Three steps - beach, shallows, deep",
        },
        "hint": 'A selection of three tentative masking algorithms (still looking for the Holy Grail...). The first two (sand and rocks) requires masks_width to be a single value; the third one (3steps) requires a list of the form [a,b,c] for masks width: "a" is the length in meters of a first transition from plain imagery at the shoreline towards ratio_water transparency, "b" is the second extent zone where transparency level is kept constant equal to ratio_water, and "c" is the last extent where the masks eventually fade to nothing. The transition with rocks is more abrupt than with sand.',
    },
    "use_masks_for_inland": {
        "type": bool,
        "default": False,
        "hint": "Will use masks for the inland water (lakes, rivers, etc) too, instead of the default constant transparency level determined by ratio_water. This is VRAM expensive and presumably not really worth the price.",
    },
    "imprint_masks_to_dds": {
        "type": bool,
        "default": False,
        "hint": "Will apply masking directly to dds textures (at the Build Imagery/DSF step) rather than using external png files. This doubles the file size of masked textures (dxt5 vs dxt1) but reduce the overall VRAM footprint (a matter of choice!)",
    },
    "distance_masks_too": {
        "type": bool,
        "default": False,
        "hint": "This will additionally build distance to coastline masks that are used in Step 3 in order to improve the bathymetric profile (otherwise too low res) and avoid steep walls close to piers or rocks. Masks_zl should not be too low to grab these details.",
    },
    "masks_use_DEM_too": {
        "type": str,
        "default": "auto",
        "values": ["auto", "True", "False"],
        "value_labels": {
            "auto": "Auto - measured depth near airports",
            "True": "On - measured depth along the whole shoreline",
            "False": "Off - vector coastline only",
        },
        "hint": "Draw the masks from elevation data in addition to the vector coastline. Auto turns itself on when a fine bathymetry provider covers the tile (see reef_visibility_depth), but only fetches measured depth within bathymetry_airport_radius_km of the anchor types checked below (ICAO airports, small airfields, seaplane bases, heliports) - that is where flying happens low; farther shoreline keeps the classic distance fade plus the mapped shallow-water fallback, which read fine from altitude. Auto also skips intertidal-only sources (exposed-flats lidar that stops at the waterline): their result is a flats layer the free OpenStreetMap fallback matches without the slow national-server downloads. On fetches the whole shoreline band with any covering provider - including coarse global and intertidal-only sources, for regions whose OSM tidal flats are unmapped - and keeps the legacy custom_dem land refinement (really shines with 5m or lower; a coarse DEM yields unpleasant pixellisation). Off is the pure vector fade.",
    },
    "bathymetry_band_km": {
        "type": float,
        "default": 5.0,
        "hint": "How far from the coastline (and from large inland water), in kilometres, measured seabed depth is fetched for the depth-graded masks and the X-Plane 12 sea level raster. The data is fetched as 0.1 degree cells, like the coastline elevation band.",
    },
    "bathymetry_airport_radius_km": {
        "type": float,
        "default": 20.0,
        "hint": "In Auto mode, measured bathymetry is only fetched for shoreline cells within this many kilometres of the anchor types checked below - low flying over water happens around them, and from cruise altitude the classic coastline fade plus the mapped shallow-water fallback look identical. Each anchor projects a disk of this radius; 20 km covers the traffic pattern and most of a visual approach. 0 fetches the whole shoreline band regardless of anchors; masks_use_DEM_too=True always does. Cost scale: every 0.1 degree shoreline cell inside a disk is a separate download - on slow national lidar servers a first fetch runs minutes per cell. Needs the offline airport index, which the map window builds automatically once the X-Plane folder is set (without it, the whole band is fetched).",
    },
    "bathymetry_near_icao_airports": {
        "type": bool,
        "default": True,
        "hint": "Fetch measured depth around airports carrying an ICAO code (about 15k worldwide). The anchor for airline and general-aviation flying: approaches and departures over water get real depth-graded shallows instead of the distance fade. Modest cost - ICAO fields are sparse along most coastlines.",
    },
    "bathymetry_near_other_airports": {
        "type": bool,
        "default": True,
        "hint": "Fetch measured depth around small airfields without an ICAO code (about 16k worldwide: grass strips, bush and ultralight fields, local identifiers). The anchor for low-and-slow VFR flying - island strips and coastal bush fields sit exactly where tidal flats and reefs are. Cost grows in strip-dense regions: each field adds a full radius disk of cell downloads.",
    },
    "bathymetry_near_seaplane_bases": {
        "type": bool,
        "default": True,
        "hint": "Fetch measured depth around seaplane bases (only ~150 worldwide, but you land ON the water there). Near-zero added cost and the highest value per anchor - leave it on unless you never fly floats.",
    },
    "bathymetry_near_heliports": {
        "type": bool,
        "default": False,
        "hint": "Fetch measured depth around heliports (about 7k worldwide - hospital pads, offshore platforms, private rooftops). Off by default: they are the densest anchor type and most have no over-water approach, so they inflate downloads the most for the least gain (measured on the Portuguese coast: enabling them grew the fetched shoreline cells by a quarter). Turn on for offshore/HEMS helicopter flying.",
    },
    "reef_visibility_depth": {
        "type": float,
        "default": 25.0,
        "hint": "Water shallower than this (in metres) keeps part of its imagery visible in the masks, fading smoothly from fully opaque at the waterline to the ratio_water transparency at this depth. Larger values keep deeper reef structure visible - Pacific atolls and lagoons read well around 30-40. Only effective where a bathymetry provider covers the tile.",
    },
    "osm_shallow_water_fallback": {
        "type": bool,
        "default": True,
        "hint": "Where no measured bathymetry applies - no fine source covers the tile, or the shoreline lies beyond bathymetry_airport_radius_km in Auto mode - mapped OpenStreetMap shallow water is treated as such in the masks: natural=reef polygons as roughly 2 m deep and wetland=tidalflat polygons as roughly 1 m, so reef flats, atoll rings and tidal lagoons (the Ria Formosa, the Waddenzee) keep their imagery visible. Measured bathymetry always wins when available; this only fills the gaps (most Pacific atolls and European tidal lagoons are mapped in OpenStreetMap but have no open depth data).",
    },
    "masks_custom_extent": {
        "type": str,
        "default": "",
        "hint": 'Yet another tentative to draw masks with maximizing the use of the good imagery part. Requires to draw (JOSM) the "good imagery" threshold first, but it could be one order of magnitude faster to do compared to hand tweaking the masks and the imageries one by one.',
    },
    "coastal_foam_edge": {
        "type": bool,
        "default": False,
        "hint": "Restyles the coastline transition in the water masks: the machine-straight land-to-water fade is replaced by an organically wavy shoreline with a semi-transparent foam band on the water side. Purely cosmetic and a matter of taste, hence off by default. The band width follows masks_width and the foam transparency follows ratio_water; within that band this overrides the masking_mode transition shape.",
    },
    # DSF/Imagery
    "texture_mode": {
        "type": str,
        "default": "full_ortho",
        "values": ("full_ortho", "airport_ortho", "default_xplane"),
        "value_labels": {
            "full_ortho": "Full Ortho",
            "airport_ortho": "Airport Ortho",
            "default_xplane": "Default X-Plane",
        },
        "hint": "What the base mesh is textured with. Full Ortho: orthophotos everywhere (classic). Airport Ortho: orthophotos on and around airports only, fading into X-Plane default terrain. Default X-Plane: no orthophotos; the custom mesh uses X-Plane default landclass terrain read from the installed Global Scenery.",
    },
    "airport_ortho_fade_width": {
        "type": float,
        "default": 1000.0,
        "hint": "Airport Ortho mode: width in meters of the band beyond the airport boundary over which orthophoto fades into default terrain.",
    },
    "default_website": {"type": str, "default": "", "hint": ""},
    "default_zl": {"type": int, "default": 16, "hint": ""},
    "zone_list": {"type": list, "default": [], "hint": ""},
    "cover_airports_with_highres": {
        "type": str,
        "default": "False",
        "values": ("False", "True", "ICAO", "Existing"),
        "value_labels": {
            "False": "Off",
            "True": "All airports",
            "ICAO": "Airports with ICAO codes",
            "Existing": "Reuse already-downloaded textures",
        },
        # Values written by other Ortho4XP forks, read as their closest
        # equivalent here (loudly) so rebuilding a foreign-built tile
        # never silently loses its airport coverage: "Progressive"
        # (progressive ZL rings) upgrades all airports at cover_zl.
        "legacy_values": {"Progressive": "True"},
        "hint": 'When set, textures above airports will be upgraded to a higher zoomlevel, the imagery being the same as the one they would otherwise receive. Can be limited to airports with an ICAO code for tiles with so many airports. Exceptional: use "Existing" to (try to) derive custom zl zones from the textures directory of an existing tile.',
        "short_name": "high_zl_airports",
    },
    "cover_extent": {
        "type": float,
        "default": 1.0,
        "hint": "The extent (in km) past the airport boundary taken into account for higher ZL. Note that for VRAM efficiency higher ZL textures are fully used on their whole extent as soon as part of them are needed.",
    },
    "cover_zl": {
        "type": int,
        "default": 18,
        "hint": "The zoomlevel with which to cover the airports zone when high_zl_airports is set. Note that if the cover_zl is lower than the zoomlevel which would otherwise be applied on a specific zone, the latter is used.",
    },
    "sea_texture_blur": {
        "type": float,
        "default": 0.0,
        "hint": 'For layers of type "mask" in combined providers imageries, determines the extent (in meters) of the blur radius applied. This allows to smoothen some sea imageries where the wave or reflection pattern was too much present.',
    },
    "color_harmonization": {
        "type": bool,
        "default": True,
        "hint": "Harmonizes texture colors across the tile, removing the patchwork caused by different acquisition dates and providers while preserving genuine geographic color gradients. The color difference is MEASURED where two textures meet (the strips on either side of a seam photograph the same ground), water is excluded using the tile's own coastline masks, and the correction is a smooth field interpolated across texture centres — so it can never draw a line at a seam. Fully automatic; no reference imagery or manual correction needed. Adds a short wait before conversions start (the field needs every download finished) and changes the output textures.",
    },
    "sea_nodata_fill": {
        "type": bool,
        "default": True,
        "hint": "Repairs imagery provider no-data defects (large saturated white or black rectangles over coastal water) by cloning nearby genuine sea pixels into the hole. Only regions that are simultaneously saturated, perfectly flat, larger than 2% of the texture and mostly on the water side of the coastline mask are touched, so real photographed water and land are never modified. Applies at the texture conversion step on coastal textures.",
    },
    "water_tech": {
        "type": str,
        "default": "XP12",
        "values": ("XP12", "XP11 + bathy"),
        "hint": "Water tech type. XP12 uses a new (partly in construction) rendering tech, XP11 + bathy uses a more traditionnal blend. Both allows for 3D water.",
    },
    "dsf_bathymetry": {
        "type": str,
        "default": "auto",
        "values": ["auto", "True", "False"],
        "value_labels": {
            "auto": "Auto - synthesize when Global Scenery is missing",
            "True": "On - always splice measured depths in",
            "False": "Off - copy the Global Scenery rasters only",
        },
        "hint": "Where the X-Plane 12 DSF gets its sea level (bathymetry) raster, which drives the simulator's depth-aware water light filtering. Auto copies the raster from the installed Global Scenery as before, and synthesizes it from measured coastal depths when that Global Scenery tile is not installed. On additionally replaces the sea part of the copied raster with measured depths where a bathymetry provider covers the tile. Only meaningful with water_tech=XP12.",
    },
    # "add_low_res_sea_ovl": {
    #    "type": bool,
    #    "default": False,
    #    "hint": "Will add an extra texture layer over the sea (with constant alpha channel given by ratio_water as for inland water), based on a low resolution imagery with global coverage. Masks with their full resolution imagery are still being used when present, the final render is a composite of both. The default imagery with code SEA can be changed as any other imagery defined in the Providers directory, it needs to have a max_zl defined and is used at its max_zl.",
    # },
    # "experimental_water": {
    #    "type": int,
    #    "default": 0,
    #    "values": (0, 1, 2, 3),
    #    "hint": 'If non zero, replaces X-Plane water by a custom normal map over low res ortho-imagery (requires XP11 but turns water rendering more XP10 alike). The value 0 corresponds to legacy X-Plane water, 1 replaces it for inland water only, 2 over sea water only, and 3 over both. Values 2 and 3 should always be used in combination with "imprint_masks_to_dds".\n\nThis experimental feature has two strong downsides: 1) the waves are static rather dynamical (would require a plugin to update the normal_map as X-Plane does) and 2) the wave height is no longer weather dependent. On the other hand, waves might have less repetitive patterns and some blinking in water reflections might be improved too; users are welcome to improve the provided water_normal_map.dds (Gimp can be used to edit the mipmaps individually).',
    # },
    "ratio_water": {
        "type": float,
        "default": 0.25,
        "hint": 'Inland water rendering is made of two layers : one bottom layer of "X-Plane water" and one overlay layer of orthophoto with constant level of transparency applied. The parameter ratio_water (values between 0 and 1) determines how much transparency is applied to the orthophoto. At zero, the orthophoto is fully opaque and X-Plane water cannot be seen ; at 1 the orthophoto is fully transparent and only the X-Plane water is seen.',
    },
    "ratio_bathy": {
        "type": float,
        "default": 1.0,
        "hint": "Bathymetry multiplier for near shore vertices. In the range [0,1].",
    },
    "normal_map_strength": {
        "type": float,
        "default": 1.0,
        "hint": 'Orthophotos by essence already contain the part of the shading burned in (here by shading we mean the amount of reflected light in the camera direction as a function of the terrain slope, not the shadows). This option allows to tweak the normal coordinates of the mesh in the DSF to avoid "overshading", but it has side effects on the way X-Plane computes scenery shadows. Used to be 0.3 by default in earlier versions, the default is now 1 which means exact normals.',
    },
    "terrain_casts_shadows": {
        "type": bool,
        "default": True,
        "hint": "If unset, the terrain itself will not cast (but still receive!) shadows. This option is only meaningful if scenery shadows are opted for in the X-Plane graphics settings.",
        "short_name": "terrain_casts_shadow",
    },
    "overlay_lod": {
        "type": float,
        "default": 25000,
        "hint": "Distance until which overlay imageries (that is orthophotos over water) are drawn. Lower distances have a positive impact on frame rate and VRAM usage, and IFR flyers will probably need a higher value than VFR ones.",
    },
    "use_decal_on_terrain": {
        "type": bool,
        "default": False,
        "hint": "Terrain files for all but water triangles will contain the maquify_1_green_key.dcl decal directive. The effect is noticeable at very low altitude and helps to overcome the orthophoto blur at such levels. Can be slightly distracting at higher altitude.",
    },
    # Other
    "custom_dem": {
        "type": str,
        "default": "",
        "hint": "Path to an elevation data file to be used instead of the default Viewfinderpanoramas.org ones (J. de Ferranti). The raster must be in geopgraphical coordinates (EPSG:4326) but the extent need not match the tile boundary (requires Gdal). Regions of the tile that are not covered by the raster are mapped to zero altitude (can be useful for high resolution data over islands in particular).",
    },
    "fill_nodata": {
        "type": bool,
        "default": True,
        "hint": "When set, the no_data values in the raster will be filled by a nearest neighbour algorithm. If unset, they are turned into zero (can be useful for rasters with no_data over the whole oceanic part or partial LIDAR data).",
    },
}

# Create dictionary from cfg_tile_vars with prefix and remove keys not in global config
cfg_global_tile_vars = {
    f"{global_prefix}{key}": value
    for key, value in cfg_tile_vars.items()
    if key not in ["default_website", "default_zl", "zone_list"]
}

cfg_vars = {**cfg_app_vars, **cfg_tile_vars, **cfg_global_tile_vars}

list_app_vars = [
    "verbosity",
    "cleaning_level",
    "overpass_server_choice",
    "osm_regional_extracts",
    "osm_extract_foreground_download",
    "osm_extract_refresh_days",
    "base_elevation_source",
    # APP-level by design (spec §C.4, RULINGS 2026-09-18a/18j): the
    # "Airports on a tile edge" answer.  It lives in ``cfg_app_vars``; it
    # must ALSO sit in this list, because this list is what the schema
    # dump publishes as the ``app`` GROUP — a front end that walks
    # ``groups`` instead of resolving rows by name never saw it (#34).
    "auto_patch_boundary",
    "skip_downloads",
    "skip_converts",
    "max_download_slots",
    "max_convert_slots",
    "max_build_slots",
    "check_tms_response",
    "http_timeout",
    "max_connect_retries",
    "max_baddata_retries",
    "ovl_exclude_pol",
    "ovl_exclude_net",
    "custom_scenery_dir",
    "custom_overlay_src",
    "custom_overlay_src_alternate",
    "cifp_data_path",
]

gui_app_vars_short = list_app_vars[:-4]

gui_app_vars_long = list_app_vars[-4:]

list_vector_vars = [
    "auto_patch",
    "modify_custom_airports",
    "elevation_level",
    "elevation_coastline_band_km",
    "apt_smoothing_pix",
    "apt_smoothing_auto",
    "airport_elevation_insets",
    "airport_elevation_providers",
    "airport_elevation_level",
    "airport_elevation_inset_margin_m",
    "airport_elevation_inset_feather_m",
    "airport_inset_water",
    "working_grid_arc_seconds",
    "road_level",
    "road_banking_limit",
    "road_grade_limit",
    "lane_width",
    "max_levelled_segs",
    "water_simplification",
    "min_area",
    "max_area",
    "clean_bad_geometries",
    "mesh_zl",
]

list_mesh_vars = [
    "curvature_tol",
    "apt_curv_tol",
    "apt_curv_ext",
    "coast_curv_tol",
    "coast_curv_ext",
    "limit_tris",
    "min_angle",
    "sea_smoothing_mode",
    "water_smoothing",
    "iterate",
]

list_mask_vars = [
    "mask_zl",
    "masks_width",
    "masking_mode",
    "inland_shore_feather_m",
    "use_masks_for_inland",
    "imprint_masks_to_dds",
    "distance_masks_too",
    "masks_use_DEM_too",
    "bathymetry_band_km",
    "bathymetry_airport_radius_km",
    "bathymetry_near_icao_airports",
    "bathymetry_near_other_airports",
    "bathymetry_near_seaplane_bases",
    "bathymetry_near_heliports",
    "reef_visibility_depth",
    "osm_shallow_water_fallback",
    "masks_custom_extent",
    "coastal_foam_edge",
]

list_dsf_vars = [
    "texture_mode",
    "airport_ortho_fade_width",
    "cover_airports_with_highres",
    "cover_extent",
    "cover_zl",
    "water_tech",
    "dsf_bathymetry",
    "ratio_bathy",
    "ratio_water",
    "overlay_lod",
    "sea_texture_blur",
    "sea_nodata_fill",
    "color_harmonization",
    # "add_low_res_sea_ovl",
    # "experimental_water",
    "normal_map_strength",
    "terrain_casts_shadows",
    "use_decal_on_terrain",
]

list_other_vars = ["custom_dem", "fill_nodata"]

list_tile_vars = (
    list_vector_vars
    + list_mesh_vars
    + list_mask_vars
    + list_dsf_vars
    + list_other_vars
    + ["default_website", "default_zl", "zone_list"]
)

list_global_tile_vars = [
    global_prefix + item
    for item in (
        list_vector_vars
        + list_mesh_vars
        + list_mask_vars
        + list_dsf_vars
        + list_other_vars
    )
]

list_global_vector_vars = [global_prefix + item for item in list_vector_vars]

list_global_mesh_vars = [global_prefix + item for item in list_mesh_vars]

list_global_dsf_vars = [global_prefix + item for item in list_dsf_vars]

list_global_mask_vars = [global_prefix + item for item in list_mask_vars]

list_cfg_vars = list_tile_vars + list_global_tile_vars + list_app_vars

# ──────────────────────────────────────────────────────────────────────
# THE TILE-CFG STAMP (owner RULINGS 2026-09-18c (2))
# ──────────────────────────────────────────────────────────────────────
#: The one line every tile config this engine writes carries, recording
#: WHICH build wrote it.  It is NOT a setting: it is never in
#: ``cfg_vars``/``list_tile_vars``, never read as a value, and readers
#: skip it explicitly rather than swallowing it as an unknown key.
#:
#: WHY IT EXISTS.  The owner ruled, verbatim: "let's just move any config
#: file created before 1.0.352, to a backup so everything going forward
#: starts with no config and global defaults, any changes then write a
#: new config file."  File mtime cannot answer "which build wrote this"
#: (a copy, a restore, a rsync all rewrite it), so the file says so
#: itself.  ABSENT stamp = written before 1.0.352 = move it aside.
cfg_stamp_key = "cfg_written_by"

# ──────────────────────────────────────────────────────────────────────
# RETIRED KEYS
# ──────────────────────────────────────────────────────────────────────
#: Keys that WERE settings and are not any more.  Every one of them is
#: DELETED from a cfg file the moment a reader meets it
#: (:func:`cleanup_retired_cfg_keys`, owner RULINGS 2026-09-13a (2)) and
#: reported once as INFO — a stale line in a user's cfg must never take a
#: build down, and must never nag either (the owner's own +22+113 tile
#: cfg still carries ``flat_site_declared_corridors=``).  The value is
#: the registry's record of the retirement: ``None`` where the key was
#: merely superseded, a sentence where a user's setting stopped being
#: honoured and the docs/tests need to say what replaced it.
#:
#: The registry lives HERE, beside the live keys, so a reader never has
#: to look in two places to answer "is this key known".
retired_cfg_keys = {
    # Superseded by airport_elevation_level (2026-07-24).
    "airport_elevation_inset_resolution_m": None,
    # RULINGS 2026-09-13au: v1 is retired; v2 is the only engine.  Silent
    # (value ``None``) — the owner's own tile cfgs carry the line, and a
    # user who never chose an engine must not be told one went away.
    "auto_patch_engine": None,
    # RULINGS 2026-09-13bh: v1's solver switch; v2 has ONE solve and
    # nothing reads this key.  Silent (value ``None``) — as with
    # ``auto_patch_engine``, a user who never chose a solve must not be
    # told one went away.
    "solve_model": None,
    # RULINGS 2026-09-05k-2: the declared register is the v2 law table.
    "flat_site_declared": (
        "flat_site_declared is RETIRED and IGNORED: an airport is declared "
        "a flat site in the engine's law table "
        "src/auto_patch_v2/law/flat_site.toml [declared] (ICAO = { z0, "
        "source }), the ONE register DEM prep and the v2 law both read "
        "(owner ruling 2026-09-05k-2) — delete the line."
    ),
    "flat_site_declared_elevation_m": (
        "flat_site_declared_elevation_m is RETIRED and IGNORED: a declared "
        "flat site's datum is its entry in src/auto_patch_v2/law/"
        "flat_site.toml [declared] (source = \"metres\" makes z0 the datum; "
        "owner ruling 2026-09-05k-2) — delete the line."
    ),
    # Round 21, owner ruling 2026-08-12: the causeway is MEASURED now.
    "flat_site_declared_corridors": (
        "flat_site_declared_corridors is RETIRED and IGNORED: the ground "
        "between an airport's flat-site footprints is now detected "
        "automatically (land-connected continuity, owner ruling "
        "2026-08-12) — delete the line."
    ),
}


#: THE REPORT REGISTER (owner RULINGS 2026-09-13a (2)): what this
#: process has already said about a cfg file.  Entries are
#: ``(abspath, var)`` for a removed key and ``(abspath, None)`` for a
#: file whose cleanup could not be written.  KCLT's tile cfg carries two
#: retired keys and is read three times per build (the tile overlay
#: layers plus a read outside any tile context), so the owner saw six
#: WARNING lines for two stale cfg lines.  Now the FIRST read deletes the
#: lines and says so once; the reads after it find nothing to say.
_retired_cfg_reported = set()


def cleanup_retired_cfg_keys(source):
    """REMOVE every retired key from the cfg file *source*.

    The owner's ruling (2026-09-13a (2)): a retired key found on READ is
    not warned about for the rest of time — it is deleted from the file,
    reported ONCE as INFO, and never seen again.  The rewrite goes
    through :func:`O4_Settings_Model._write_atomic_with_backup` — THE cfg
    writer, so the prior file is kept as ``<cfg>.bak`` and no second
    writer exists to disagree with it.  (Imported lazily:
    ``O4_Settings_Model`` imports this module at module level.)

    A file that cannot be rewritten (a read-only cfg, a read-only
    directory) is NOT an error: the caller is told once, per file, and
    the build carries on — a stale cfg line must never take a build
    down.  Comments and blank lines do not survive a rewrite; a file
    carrying NO retired key is never rewritten, so a clean cfg keeps
    every byte (and mints no ``.bak``).

    :param source: path to the cfg file just read.
    :returns: the INFO lines the caller should print (possibly empty).
        Never raises.
    """
    try:
        path = os.path.abspath(source) if source else None
        if not path or not os.path.isfile(path):
            return []
        import O4_Settings_Model as SETTINGS

        data = SETTINGS._parse_cfg(path, strip_quotes=False)
        stale = [var for var in data if var in retired_cfg_keys]
        if not stale:
            return []
        try:
            SETTINGS._write_atomic_with_backup(
                path, {k: v for k, v in data.items() if k not in stale})
        except Exception as error:
            if (path, None) in _retired_cfg_reported:
                return []
            _retired_cfg_reported.add((path, None))
            return ["retired key" + ("s" if len(stale) > 1 else "") + " "
                    + ", ".join(stale) + " in " + path + " " +
                    ("are" if len(stale) > 1 else "is") +
                    " IGNORED; the file could not be rewritten (" +
                    str(error) + ")"]
        lines = []
        for var in stale:
            if (path, var) in _retired_cfg_reported:
                continue
            _retired_cfg_reported.add((path, var))
            lines.append("removed retired key " + var + " from " + path)
        return lines
    except Exception:
        # A cleanup that raises is a cleanup that breaks builds.
        return []


def retired_cfg_key_warning(var, value=None):
    """The sentence explaining a key's retirement, or ``None``.

    ``None`` for a live key and for a silently-retired one.  The READERS
    no longer print this — since 2026-09-13a they delete the line and say
    so (:func:`cleanup_retired_cfg_keys`); the sentence remains the
    registry's own record of WHY a key went, and what replaced it.
    """
    if var not in retired_cfg_keys:
        return None
    message = retired_cfg_keys[var]
    if not message:
        return None
    text = str(value or "").strip()
    if text:
        return message + " (it carried: " + text + ")"
    return message
