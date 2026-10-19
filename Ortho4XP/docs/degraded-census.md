# Degraded outcomes: the census (issue #853, B3-21)

Spec: `docs/specs/code-quality-beta3-spec.md` §2. A DEGRADED outcome is a
tile that was built, but with an output that is not what was asked. Before
#853 these were console prints only. This file is the census of every
`WARNING` string in the tile-build step modules, one row per function.
`tests/test_tile_failures.py` reads the table below as its own: a new
`WARNING` print in one of these modules, or one more in a listed function,
fails the twin until it has a row here.

Classes:

- `degraded`: the output changes and the tile's `BuildDone.warnings` names
  it. The `code` column is an `O4_Tile_Failures` code whose severity is
  `degraded`, and a step module publishes it
  (`O4_Unpatched_Airports.record_degraded`).
- `failure`: the print comes before a coded tile failure (severity
  `blocking`). The `code` column names it.
- `uncoded`: the output changes, but nothing names it to the user yet.
  These are the follow-up list. Each one needs a code, a row publisher and
  copy the master rules.
- `diagnostic`: the output does not change. Examples: an audit in warn
  mode that also has a strict mode, a cache entry that is refetched, a
  check that was skipped.
- `config`: a settings or provider-file entry was unreadable, so the
  default was used. This is about the setup, not about a tile's output.

`count` is the number of string constants containing `WARNING` in the
function (docstrings excluded).

| module | function | count | class | code | effect |
|---|---|---|---|---|---|
| O4_Vector_Map.py | derive_auto_patch_selection | 1 | diagnostic | | each consumer recomputes the selection |
| O4_Vector_Map.py | audit_interp_alt_seed_sealing | 1 | uncoded | | warn mode of an audit whose strict mode raises `UnsealedInterpAltSeed` |
| O4_Mesh_Utils.py | hairline_preflight | 1 | diagnostic | | the pre-flight check is skipped |
| O4_Mesh_Utils.py | build_curv_tol_weight_map | 2 | uncoded | | airport zoom upgrade or inset mesh density not applied |
| O4_Mesh_Utils.py | patch_valued_vertex_indices | 2 | uncoded | | free-interior interpolation disabled for the tile |
| O4_Mesh_Utils.py | patch_segment_split_values | 1 | uncoded | | ring-segment vertices keep the free-interior treatment |
| O4_Mesh_Utils.py | _levelled_road_lines | 1 | uncoded | | bank blend overrides nothing pre-valued |
| O4_Mesh_Utils.py | pavement_shore_vertices | 1 | uncoded | | pavement ring vertices on the water line keep the water datum (the #945 ridge) |
| O4_Mesh_Utils.py | audit_bank_annulus | 1 | uncoded | | warn mode of an audit whose strict mode raises `BankAnnulusCollapse` |
| O4_Mesh_Utils.py | interp_alt_ribbon_vertex_indices | 1 | uncoded | | road ribbon nodes stay in the free set |
| O4_Mesh_Utils.py | bank_annulus_blend_values | 2 | uncoded | | bank annulus keeps the graph-harmonic treatment |
| O4_Mesh_Utils.py | patch_coverage_polygon | 1 | uncoded | | free-interior interpolation disabled for the tile |
| O4_Mesh_Utils.py | audit_interp_alt_extent | 1 | uncoded | | warn mode of an audit whose strict mode raises `InterpAltLeak` |
| O4_Mesh_Utils.py | post_process_nodes_altitudes | 4 | uncoded | | degenerate triangles left, a blend or interpolation pass skipped |
| O4_Mesh_Utils.py | build_mesh | 1 | uncoded | | the mesh is retried with a lower minimum angle |
| O4_Mask_Utils.py | build_masks | 1 | degraded | mask_extent_missing | the regular masks are built instead of the custom extent |
| O4_Mask_Utils.py | delete_old_masks_in_tile | 1 | uncoded | | an old mask the build could not delete stays on disk |
| O4_Mask_Utils.py | load_shallow_water_polygons | 2 | degraded | mask_shallow_water_skipped | a shallow-water category (reefs, tidal flats) is not shaded |
| O4_Tile_Utils.py | download_textures | 1 | degraded | imagery_incomplete | textures that failed to download are white squares |
| O4_Imagery_Utils.py | incomplete_texture_warning | 1 | degraded | imagery_incomplete | the same, said once at the step's end (`O4_Tile_Utils.warn_if_imagery_incomplete` publishes it) |
| O4_Imagery_Utils.py | artifact_state | 1 | diagnostic | | an unreadable artifact is kept, never deleted |
| O4_Imagery_Utils.py | initialize_providers_dict | 1 | config | | an unreadable provider file is skipped |
| O4_Imagery_Utils.py | convert_texture | 1 | failure | texture_convert_failed | #903: an unconverted texture fails the tile, which is not activated |
| O4_DSF_Utils.py | zone_list_to_ortho_dico | 1 | uncoded | | airport zoom upgrade not applied (the airport file is missing) |
| O4_DSF_Utils.py | _tile_elevation_post_grid | 1 | uncoded | | the synthesized DSF raster has no elevation source |
| O4_DSF_Utils.py | build_dsf | 1 | uncoded | | default_xplane mode substituted a projected terrain |
| O4_DEM_Utils.py | drop_missing_pinned_files | 1 | uncoded | | a pinned elevation file is missing, so the default sources are used |
| O4_DEM_Utils.py | read_elevation_from_file | 4 | uncoded | | assumed no-data or EPSG, unsupported raster read as zero altitude |
| O4_DEM_Utils.py | fill_nodata_values_with_nearest_neighbor | 1 | uncoded | | holes too large to fill are set to zero |
| O4_Airport_Elevation_Insets.py | _parse_resolution_ladder | 2 | config | | a malformed ladder rung is skipped |
| O4_Airport_Elevation_Insets.py | initialize_elevation_providers_dict | 3 | config | | an unreadable or refused provider definition is skipped |
| O4_Airport_Elevation_Insets.py | select_provider_definitions | 1 | config | | an unknown provider code is ignored |
| O4_Airport_Elevation_Insets.py | fetch_inset | 1 | config | | a provider names no access strategy |
| O4_Airport_Elevation_Insets.py | _building_footprint_polygons_from_layer | 1 | uncoded | | buildings are not masked out of a surface-model inset |
| O4_Airport_Elevation_Insets.py | openstreetmap_building_footprints | 1 | uncoded | | the same (the building query failed) |
| O4_Airport_Elevation_Insets.py | mask_building_footprints_in_surface_model | 1 | uncoded | | the same (the masking failed) |
| O4_Airport_Elevation_Insets.py | warn_if_delivered_inset_clips_airport | 1 | uncoded | | ground beyond a short inset is graded on the base source |
| O4_Airport_Elevation_Insets.py | _clear_poisoned_insets | 1 | diagnostic | | an unreadable cached inset is removed and refetched |
| O4_Airport_Elevation_Insets.py | _archive_void_inset_record | 1 | diagnostic | | a void record could not be archived |
| O4_Airport_Elevation_Insets.py | ensure_airport_insets._fetch_airport_insets | 2 | degraded | inset_fetch_failed | an airport inset was not fetched, so the airport uses the base source |
| O4_Airport_Elevation_Insets.py | _load_inset_raster | 1 | uncoded | | an unreadable inset is skipped |
| O4_Airport_Elevation_Insets.py | parse_airport_elevation_level | 1 | config | | an unrecognised level reads as auto |
| O4_Airport_Elevation_Insets.py | ensure_insets_for_tile | 2 | degraded | inset_fetch_failed | the same, published by the home tile's pass |
| O4_Airport_Elevation_Insets.py | _warn_if_provider_offsets_systematic | 1 | diagnostic | | a provider's datum looks offset |
| O4_Airport_Elevation_Insets.py | bake_airport_insets_into_alt_dem | 1 | uncoded | | an inset could not be baked |
| O4_Airport_Elevation_Insets.py | _bake_one_inset | 1 | diagnostic | | an inset differs from the base by a median offset |
| O4_Airport_Elevation_Insets.py | overlay_flat_site_insets | 1 | uncoded | | flat-site mode and the DEM query path disagree |
| O4_Airport_Elevation_Insets.py | warn_if_inset_does_not_cover_airport | 1 | uncoded | | the airport ground outside the inset is graded on the base source |
| O4_Airport_Elevation_Insets.py | seam_harmonized_ballot_insets | 1 | uncoded | | the seam harmonization stops at its component limit |
