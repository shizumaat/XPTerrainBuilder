"""Cross-tile airports a tile skipped for a neighbour that joined later.

THE DEFECT (#1643): a tile chooses its auto-patch airports at the start of
its vector step, against the tiles the run held THEN.  A neighbour queued
after that moment is "a tile this build is not building", so an airport
the tile owns that crosses into the neighbour is boundary-skipped — and
nothing ever builds it, although the neighbour is now in the run.

The fix is one re-judgement, shared by both run modes: when a tile joins a
run, every tile of the run whose selection was already made against a set
lacking it is judged again with :func:`airports_skipped_into` — the SAME
record the boundary preflight builds (:func:`boundary_record`), against the
set that selection actually used.  A tile that did skip an airport into the
new cell re-runs from its vector step (``parallel.py``) or is queued again
(the in-process run); its next selection counts the neighbour as built.
"""

__all__ = ["boundary_record", "airports_skipped_into"]


def boundary_record(lat, lon, batch):
    """``(record, siblings)`` for one home cell judged against *batch*.

    ``record`` is :func:`auto_patch.selection.boundary_skipper`'s
    ``(icao, cls, cold_cells, crossing_m)`` per candidate; ``siblings`` the
    cells of *batch* whose frame is not warm.  ``None`` when the tile has no
    CIFP directory (it patches nothing).  Offline: the tile's config, the
    CIFP directory and the apt.dat the selector chooses — never a query.
    """
    import O4_Config_Utils as CFG
    import O4_Settings_Model as SETTINGS
    import O4_Vector_Map as VMAP
    from auto_patch import selection as SELECTION

    tile = CFG.Tile(lat, lon, "")
    tile.read_from_config()
    cifp = SETTINGS.resolve_cifp_dir(CFG.cifp_data_path,
                                     CFG.custom_scenery_dir)
    if not cifp:
        return None
    record = []
    (is_cold, siblings) = VMAP.boundary_cold_predicate((lat, lon), batch)
    SELECTION.select_patch_airports(
        tile, cifp, SELECTION.resolved_auto_patch_mode(tile),
        manual_icaos=VMAP.manual_patch_icaos(tile),
        boundary=SELECTION.boundary_skipper(
            lat, lon, is_cold=is_cold,
            reach_m=SELECTION.ask_reach_m(),
            record=record))
    return (record, siblings)


def _adjacent(home, cell):
    """Is *cell* one of the eight cells around *home*?  An airport claim
    crosses into adjacent cells only (``parallel._boundary_batch_locked``)."""
    (dlat, dlon) = (int(cell[0]) - int(home[0]), int(cell[1]) - int(home[1]))
    return (dlat, dlon) != (0, 0) and abs(dlat) <= 1 and abs(dlon) <= 1


def airports_skipped_into(home, batch, cells):
    """The ICAOs *home*'s selection against *batch* boundary-skipped because
    they cross into one of *cells* (sorted; empty when none).

    Only cold cells adjacent to *home* and absent from *batch* can have
    caused a skip, so with none of those this reads nothing (the CIFP and
    apt.dat read costs seconds on a real tile).  Warmth is read NOW: a
    cell the run did not hold is warmed since only by another tile's
    "build adjacent" answer, so a frame warm now was nearly always warm
    then — and a tile that saw it warm built the airport, which a re-run
    would only repeat.  Never raises: a failure re-judges nothing.
    """
    home = (int(home[0]), int(home[1]))
    batch = frozenset((int(c[0]), int(c[1])) for c in (batch or ()))
    new = {(int(c[0]), int(c[1])) for c in (cells or ())}
    try:
        import O4_UI_Utils as UI
        import O4_Vector_Map as VMAP

        new = {c for c in new if _adjacent(home, c) and c not in batch
               and not VMAP.tile_frame_is_warm(*c)}
        if not new:
            return []
        # A judgement, not a build: the selector's narration stays in the
        # build's own log (the preflight's rule).
        with UI.quiet_thread():
            judged = boundary_record(home[0], home[1], batch)
    except Exception:
        return []
    if judged is None:
        return []
    return sorted({icao for (icao, cls, cold, _m) in judged[0]
                   if cls == "S" and new & {tuple(c) for c in cold}})
