"""Which airport insets of a tile would a build RE-FETCH -- the pre-flight.

Issue #583.  A tile build runs the engine's inset pass over EVERY
selected aerodrome of the tile, and that pass re-fetches an inset it
judges stale (a wider box, a moved pack set, a resolution-ladder rung
that now lists new coverage).  The harness judged that for the ONE
airport a build names and for nobody on a ``--tile`` run, so a tile
build re-fetched two neighbours' insets into the shared corpus
mid-build.  This module asks the same per-airport question for the whole
tile, and lets ``--refresh-data dem`` complete exactly what it names.

Every verdict is the ENGINE's own predicate, imported and never copied:
``O4_Airport_Elevation_Insets.airport_inset_frame_problem`` and a ladder
verdict the caller passes in -- :func:`ladder_owed_problem` (DISK ONLY,
what a pre-flight reads) or ``build_airport``'s re-check, which ASKS the
providers' indexes and so belongs to an authorised refresh.  The airports are the engine's own selection
(``resolved_inset_mode`` / ``inset_keys``), as ``ensure_insets_for_tile``
takes it.
"""
from __future__ import annotations

__all__ = [
    "REFRESHABLE_KINDS",
    "airport_problem",
    "airports_layer_is_cached",
    "inset_selection_admits",
    "ladder_owed_problem",
    "required_boxes",
    "stale_negative_airports",
    "tile_pending_refetches",
]

#: The per-airport verdicts under which the build's inset pass FETCHES.
#: ``empty`` is a declared state (the raster is read, found empty, and
#: the airport grades on the base DEM): nothing is fetched for it.
REFRESHABLE_KINDS = ("missing", "packs", "stale", "ladder")


def airports_layer_is_cached(lat, lon) -> bool:
    """Is the tile's airports layer ON DISK?  Asked of the file itself:
    reading an absent layer is an overpass QUERY, and a pre-flight never
    reaches the network (#583)."""
    import os

    import O4_File_Names as FNAMES

    return os.path.isfile(FNAMES.osm_cached(lat, lon, "airports"))


def required_boxes(lat, lon, *, selected_only: bool) -> dict:
    """``{airport key: box}`` the tile's inset pass requires today, from
    the CACHED airports layer (the caller refuses a build without it).

    ``selected_only`` restricts it to the aerodromes the tile's inset
    mode selects -- the set ``ensure_insets_for_tile`` fetches for."""
    import O4_Airport_Elevation_Insets as INSETS
    import O4_Config_Utils as CFG
    import O4_OSM_Utils as OSM
    import O4_Vector_Map as VMAP

    tile = CFG.Tile(lat, lon, "")
    tile.read_from_config()
    layer = OSM.OSM_layer()
    OSM.OSM_queries_to_OSM_layer(VMAP.AIRPORTS_QUERIES, layer, lat, lon,
                                 ["all"], cached_suffix="airports")
    dico = VMAP.build_airports_dico(tile, layer)
    if not selected_only:
        return INSETS._airport_bounding_boxes(tile, dico)
    if not INSETS.insets_enabled_for_tile(tile):
        return {}
    selected = INSETS.inset_keys(dico, INSETS.resolved_inset_mode(tile))
    return INSETS._airport_bounding_boxes(tile, dico, only=selected)


def inset_selection_admits(lat, lon, icao) -> bool:
    """Does the tile's inset mode admit ``icao``?  The engine's own
    predicate, asked the way ``dem_production`` asks it (§A.6, issue
    #1352): an airport outside the selection solves on the base raster,
    so no inset of it is required and none is refused."""
    import O4_Config_Utils as CFG
    from O4_Airport_Modes import mode_admits, resolved_inset_mode

    tile = CFG.Tile(lat, lon, "")
    tile.read_from_config()
    return mode_admits(str(icao).upper(), resolved_inset_mode(tile))


def airport_problem(lat, lon, icao, required, ladder_problem):
    """``(kind, text)`` when the build would not reuse ``icao``'s inset
    over the ``required`` box, else ``None``.  ``ladder_problem(INSETS,
    lat, lon, icao, required)`` is the caller's ladder re-check."""
    import O4_Airport_Elevation_Insets as INSETS

    problem = INSETS.airport_inset_frame_problem(lat, lon, icao, required)
    if problem is not None:
        return problem
    return ladder_problem(INSETS, lat, lon, icao, required)


def ladder_owed_problem(INSETS, lat, lon, icao, required):
    """THE LADDER RE-CHECK, FROM DISK ALONE: ``("ladder", text)`` when the
    sidecar of ``icao``'s cached inset cannot answer the build-time
    re-check (``INSETS.ladder_recheck_owed`` -- a re-asked rung recorded
    no listing, so whatever it lists is new and the build re-runs the
    ladder), else ``None``.

    A PRE-FLIGHT NEVER REACHES THE NETWORK: with no network it would
    refuse for the wrong reason, and a query is an act of
    ``--refresh-data dem``.  A product published since the fetch is found
    there, and by the build's own declared fetch, which the guard
    refuses at the call."""
    paths = INSETS.cached_inset_paths_for_icao(lat, lon, icao)
    if not paths:
        return None
    code = INSETS._inset_provider_code_from_path(paths[0])
    owed = INSETS.ladder_recheck_owed(lat, lon, icao, code, required)
    if not owed:
        return None
    return ("ladder",
            f"LADDER RE-CHECK OWED for airport elevation inset {paths[0]} "
            f"— its record holds no listing for the resolution-ladder "
            f"rung(s) {', '.join(repr(str(label)) for label in owed)} the "
            f"build re-asks, so whatever they list today is NEW and the "
            f"build would RE-FETCH the ladder (--refresh-data dem; "
            f"--warm-insets {icao})")


def tile_pending_refetches(state, lat, lon, *, ladder_problem,
                           prepare=None) -> list:
    """``[(airport key, kind, text)]`` -- every selected aerodrome of the
    tile whose inset a TILE build would fetch or re-fetch.

    ``prepare`` runs first (the caller's X-Plane path set-up: the
    pack-set arm of the predicate lists installed packs).  Empty when the
    tile has no inset cache or no airports layer -- both are already
    refused, by name, for the whole tile."""
    if not state["airport_insets"] or not state["airports_layer"]:
        return []
    if not airports_layer_is_cached(lat, lon):
        return []           # refused for the layer, by name, elsewhere
    try:
        if prepare is not None:
            prepare()
        boxes = required_boxes(lat, lon, selected_only=True)
    except Exception as exc:
        print(f"  [harness] tile-wide inset check skipped ({exc!r})")
        return []
    pending = []
    for key in sorted(boxes, key=str):
        try:
            problem = airport_problem(lat, lon, key, boxes[key],
                                      ladder_problem)
        except Exception as exc:
            print(f"  [harness] inset check of {key} skipped ({exc!r})")
            continue
        if problem is not None and problem[0] in REFRESHABLE_KINDS:
            pending.append((key, problem[0], problem[1]))
    return pending


def stale_negative_airports(lat, lon) -> list:
    """The airports whose index carries a ``no-coverage`` the build would
    RE-PROBE (no capability record, or another engine version) -- the
    engine's two predicates, names only, sorted."""
    import O4_Airport_Elevation_Insets as INSETS

    names = {row[0] for row in
             INSETS.unverified_capability_negatives(lat, lon)}
    names.update(row[0] for row in
                 INSETS.version_stale_capability_free_negatives(lat, lon))
    return sorted(names, key=str)
