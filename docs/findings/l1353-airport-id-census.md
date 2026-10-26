# #1353 consumer census: every pass keyed by airport code

Lane l1353, base `dae8b1b09`, 2026-10-26. RULINGS 2026-08-30l: one table of
every reader of the airport key, ruled before any consumer is edited.

## The derivation site

`O4_Airport_Dico.build_airports_dico` is the ONE place a tile's airport
dictionary (`dico_airports`) is keyed. `O4_Airport_Utils.discover_airport_names`
and `attach_surfaces_to_airports` key an OSM aerodrome by its `icao` / `iata` /
`local_ref` tag, else its `name` (key_type `name`), else a (lon, lat)
representative-node TUPLE (key_type `repr_node`, printed `****`).
`O4_Airport_Apt_Identity.adopt_apt_dat_identities` then re-keys every OSM
aerodrome apt.dat knows to its apt.dat code. What is left without a code is
key_type `name` or `repr_node`.

**Rule (this lane):** one more step at that same site, right after
`drop_unclaimed_seeds`: every record still keyed `name` / `repr_node` is
re-keyed to `O4_Airport_Apt_Identity.synthetic_airport_id` (key_type
`synthetic`). Every consumer below then reads a string code. No consumer gets
a per-consumer exemption.

On +43-122 at base: `Fall River Airfield`, `Mahogany Mtn. Airport`,
`Black Rock Ranch airstrip` (name keys) and two `repr_node` tuples
(43.6743, -121.5931) and (43.9452, -121.0211).

## Consumers

| # | Consumer (file:line at base) | Reads | Before (name / tuple key) | After (synthetic ID) | Edit? |
|---|---|---|---|---|---|
| 1 | Tile airport list, `O4_Airport_Utils.list_airports_and_runways` :878 (log; both apps show it through `Log`) | key + key_type | prints `****` for name and tuple keys | prints the ID; name "Unnamed airstrip (lat, lon)" when OSM has none | yes: print the key for every string key; sort `synthetic` last |
| 2 | Inset boxes, `O4_Airport_Elevation_Insets._airport_bounding_boxes` :5728, `airport_boundary_polygons` :5775 | `isinstance(key, str)` | tuple skipped ("skipped N unnamed airport(s)"); name key admitted | admitted; no tuple is left, so the skip line cannot fire | no (the guard stays for an old pickled dico) |
| 3 | Inset selection, `O4_Airport_Modes.inset_keys` :128 / `mode_admits` :85 (callers: `ensure_insets_for_tile` :5902, `O4_Vector_Map` :1846, `O4_Elevation_Level` :1805/:1880, `dem_production` :953) | key string | `All`: name admitted, tuple skipped; `ICAO`: neither | `All` admits; `ICAO` never (8 characters, not 4 letters) | no |
| 4 | Inset cache files, `O4_File_Names.airport_inset_dem` / `_provenance` :702 (`<key>_<provider>.tif`), parsed by `_inset_icao_from_path` :8484 (split on `_`), `cached_inset_paths_for_icao` :7988 | key in a file name | a tuple could not name a file; a name key with spaces did | the ID is `[0-9A-Z]`, no `_`, filename-safe on every OS | no. One-time re-fetch for name-keyed strips (their old `<name>_*.tif` stay as orphans the disk-driven readers still read) |
| 5 | Inset discovery index `index.json`, `tile.inset_selection_keys` :5914/:6104 | key | name key | ID | no |
| 6 | Smoothing radius / clip warning, `O4_Airport_Utils.smooth_raster_over_airports` :1054/:1069 | `isinstance(key, str)` | a tuple got no inset lookup | gets it | no |
| 7 | Auto-patch selection, `auto_patch.selection.select_patch_airports` :76 | CIFP airport ICAO + apt.dat | an OSM-only aerodrome is not a candidate | still not a candidate: the set is CIFP x apt.dat; an aerodrome apt.dat does not know has no runway / threshold data for v2 to build from. The mode predicate it shares (`mode_admits`) admits the ID under `All` | no. FOLLOW-UP for the owner (below) |
| 8 | Patch file names, `O4_File_Names.patch_file_icao` :451, `manual_patch_icaos_in` :464 | `<ICAO>_*.patch.osm` | n/a | an ID-named manual patch would parse to the ID (no `_` in it) | no |
| 9 | Flat-site pass, `auto_patch.flat_site_mode.tile_icao_candidates` :107 | 4-letter alpha keys | skipped | skipped (flat-site needs an apt.dat block) | no |
| 10 | "ICAO" high-res cover, `O4_DSF_Utils` :200 | key_type `icao` | excluded | excluded (key_type `synthetic`) | no |
| 11 | apt.dat identity, `O4_Airport_Apt_Identity.adopt_apt_dat_identities` | runs BEFORE the re-key | name / tuple keys matched by overlap | unchanged: only what apt.dat did not claim gets an ID | no |
| 12 | Inset coverage census tool, `tools/inset_coverage_census.py` :236 | `isinstance(key, str)` | tuple skipped | counted | no |
| 13 | Wire protocol, `o4_engine/events.py` (`AutoPatchBegin.airports`, `AutoPatchProgress.airport`, `AutoPatchFailed.airport`, `BuildDone.unpatched_airports`) | CIFP codes; airport strings | never carries a dico key the patch set lacks | the ID could only travel as an existing `str` field | no protocol change |
| 14 | `Sources/SceneryKit/OrthoEngineClient.swift` | the same events | — | — | no (events.py unchanged) |
| 15 | Mac airport list (`MapModel.swift` :279 `airports`, `defaultAirports` from `GlobalAirportIndex`) | scenery packs + apt.dat index | OSM-only aerodromes are not listed | not listed (apt.dat population); the ID reaches the Mac app in the build log (row 1) | no |
| 16 | Qt airport list (`O4_Qt_GUI._load_airports_async` :1697, marks, search) | the same apt.dat index (`airport_index`) | as Mac | as Mac; the build log shows the ID | no |

## Collision rule

The ID is `X` + 7 base-36 digits of the 0.001 degree cell of the aerodrome's
centroid (boundary area centroid, else the representative node): 8 characters.
The global airport index holds codes of 3 to 7 characters (38,854 rows,
measured on this machine), so an ID cannot equal one today; the step still
checks every index code and every key already on the tile, and a taken ID gets
a numeric suffix, in a fixed order.

## Not done here (follow-up)

Row 7: "they get no auto-patch" cannot be closed by the identifier. The v2
engine builds a patch from the airport's apt.dat (runways, boundary) and the
CIFP thresholds; an aerodrome only OSM shows has neither. Patching one needs an
OSM-only patch input, which is an owner decision, not an identifier.
