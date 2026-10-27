"""A tile built WITHOUT an airport's patch: what is set aside, who is told.

Owner RULINGS 2026-10-12a (issue #564).  An airport whose patch could not
be built no longer aborts its tile.  The tile is meshed with the patches
this build wrote, that airport takes the engine's ordinary (non-auto-patch)
airport handling, and the build ends as a success WITH WARNINGS.

What H1 protected stays law (docs/POSTMORTEM-20260831.md Task C: a silent
per-airport death once meshed the STALE patch on disk and shipped the
previous day's geometry as a new build): no mesh is built on a patch this
build did not write.  Every reader of the patch directory — the patch
ingest, the road pins, the mesh step's bank rings, the post-mesh object
stage — selects files BY NAME, and the mesh step may run in another
process than the vector step.  So the failed airport's files are RENAMED
at the one place failures are named (``auto_patch.driver``), and no reader
needs to know: there is nothing left under a name it looks for.

This module owns four things and nothing else: the per-airport file
family and its set-aside, the continue-or-abort decision (with the strict
mode the harness and the release checks run in), the engine-log warning,
and the list of unpatched airports the session reports from — plus the
sidecar's other closing facts of a built tile (stand-in elevation,
unreachable packs, and the DEGRADED outputs of #853: :func:`record_degraded`).
"""
from __future__ import annotations

import json
import os

__all__ = [
    "STALE_SUFFIX", "STRICT_ENV", "UNPATCHED_SIDECAR", "PATCH_FAMILY",
    "airport_patch_family",
    "set_aside_unbuilt", "strict", "may_continue", "record", "read",
    "PACK_RESTORE_KEY", "note_pack",
    "record_substitutions", "read_substitutions",
    "UNMOUNTED_KEY", "record_unmounted_packs", "read_unmounted_packs",
    "DEGRADED_KEY", "record_degraded", "read_degraded",
    "warn",
]

#: What a failed airport's files are renamed to.  No reader's pattern
#: matches it: ``*.patch.osm``, ``*.patch.osm.axes.json``, the plan glob
#: ``o4_v2_rebake_*.json`` and the graded surface's exact path all end
#: before it.
STALE_SUFFIX = ".stale"

#: ``1`` = an airport failure still FAILS the tile (ruling point 4: "a
#: missing patch is a defect to the project").  Set by the harness build
#: environment, the tile tools and the frozen-tile release check; the app
#: sets nothing.  An environment variable because the app's steps run in
#: worker processes, which inherit it.
STRICT_ENV = "O4_AUTO_PATCH_STRICT"

#: Beside the tile (``tile.build_dir``): the airports its mesh was built
#: without.  Rewritten by every vector step — an empty list when none — so
#: it always describes the mesh on disk.  A FILE because the app emits the
#: tile's final ``BuildDone`` from a different process than step 1.
UNPATCHED_SIDECAR = "o4_unpatched_airports.json"

#: Key of an unpatched record: why the airport's PACK could not be put
#: back to its original (absent when it was, or was never rewritten).
PACK_RESTORE_KEY = "pack_restore"

#: The whole-tile failure record's airport name (``stage == "config"``:
#: auto-patch is on and no CIFP directory resolves).  Not one airport's
#: failure, so it still ends the tile (ruling point 5).
WHOLE_TILE = "*"


#: The per-airport files placed beside the patch that a later stage reads
#: by name: the patch, its sidecar, the graded surface, and the object
#: stage's plan, screen and refusal marker.  SPELLED HERE, not imported
#: from their writers (``auto_patch.engine_v2``, ``auto_patch_v2.model.
#: rebake``, ``auto_patch_v2.airport.rebake_screen`` / ``object_plan``): a
#: failure of the v2 package to import is itself an airport failure, and
#: naming it must not need that package.  ``tests/test_unpatched_airports
#: .py`` holds each name against its writer's constant.
PATCH_FAMILY = (
    "{icao}_auto.patch.osm",
    "{icao}_auto.patch.osm.axes.json",
    "{icao}.graded.json",
    "o4_v2_rebake_{icao}.json",
    "o4_v2_rebake_{icao}.screen.json",
    "o4_v2_rebake_{icao}.screen.refused",
)


#: The plans of the airport's objects-only COMPANION packs, numbered
#: (``auto_patch_v2.airport.companion.COMPANION_PLAN``; RULINGS 2026-10-28p (5)).
COMPANION_PLANS = "o4_v2_rebake_{icao}~*.json"


def airport_patch_family(patch_dir: str, icao: str) -> list:
    """The :data:`PATCH_FAMILY` paths of one airport in *patch_dir*, then
    its :data:`COMPANION_PLANS` on disk."""
    import glob
    return [os.path.join(patch_dir, name.format(icao=icao))
            for name in PATCH_FAMILY] + sorted(glob.glob(os.path.join(
                glob.escape(patch_dir), COMPANION_PLANS.format(icao=glob.escape(icao)))))


def set_aside_unbuilt(patch_dir: str, icao: str) -> tuple:
    """Rename a failed airport's files out of every reader's sight.

    ``(moved, left)``.  What is on disk for an airport this build did not
    finish is the PREVIOUS build's set, or a half-placed set from a
    ``write`` failure.  Renamed, not deleted: the last good patch stays
    for diagnosis, an older ``.stale`` copy is overwritten, and the next
    build finds no patch and rebuilds the airport by itself.  ``left``
    names what could not be moved — the tile must then NOT be built."""
    moved, left = [], []
    for path in airport_patch_family(patch_dir, icao):
        if not os.path.lexists(path):
            continue
        try:
            os.replace(path, path + STALE_SUFFIX)
            moved.append(path)
        except OSError:
            left.append(path)
    return moved, left


def strict() -> bool:
    """Whether an airport failure fails the tile (:data:`STRICT_ENV`)."""
    return os.environ.get(STRICT_ENV, "") not in ("", "0")


def may_continue(failure) -> bool:
    """Whether the tile is built past this ``AutoPatchBuildFailure``.

    No when strict mode is on, when a record is the whole tile's rather
    than one airport's, or when a failed airport's stale file could not be
    set aside (``failure.stale_left``)."""
    if strict() or getattr(failure, "stale_left", None):
        return False
    return all(rec.get("icao") not in (None, "", WHOLE_TILE)
               for rec in failure.failures)


def _sidecar_path(build_dir: str) -> str:
    return os.path.join(build_dir, UNPATCHED_SIDECAR)


def record(tile, failures) -> list:
    """Publish the airports this tile is built without.

    ``tile.auto_patch_unpatched`` for a caller in this process, and the
    sidecar for one that is not.  Called by every vector step, with an
    empty list when every patch was built.  Never fatal: a sidecar that
    cannot be written costs the report, not the tile."""
    # ``code`` / ``params`` (O4_Tile_Failures, #562) ride along when the
    # worker could name the cause: the final step's process words the
    # warning from this record alone.
    unpatched = [{"icao": str(rec.get("icao") or "?"),
                  "stage": str(rec.get("stage") or "?"),
                  "error": str(rec.get("error") or ""),
                  **{k: rec[k] for k in ("code", "params") if rec.get(k)}}
                 for rec in failures or ()]
    tile.auto_patch_unpatched = unpatched
    _write_sidecar(tile, unpatched)
    return unpatched


def _write_sidecar(tile, unpatched: list) -> None:
    build_dir = getattr(tile, "build_dir", None)
    if not build_dir:
        return
    try:
        os.makedirs(build_dir, exist_ok=True)
        _write_key(build_dir, "unpatched", unpatched)
    except OSError:
        pass


def _read_all(build_dir: str) -> dict:
    try:
        with open(_sidecar_path(build_dir), encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _write_key(build_dir: str, key: str, value) -> None:
    """Rewrite ONE key of the sidecar, keeping the others (the same file
    carries the tile's other closing facts)."""
    data = _read_all(build_dir)
    data[key] = value
    with open(_sidecar_path(build_dir), "w", encoding="utf-8",
              newline="\n") as handle:
        json.dump(data, handle)


#: Sidecar key of the base-elevation cells read from a FALLBACK source
#: (owner RULINGS 2026-10-12e, ``elevation_access.base_fallback``).
SUBSTITUTIONS_KEY = "elevation_substituted"


def _publish_rows(tile, attr: str, key: str, rows) -> list:
    """Publish ``rows`` (dicts) as ``tile.<attr>`` for this process and
    under ``key`` in the sidecar for another.  Never fatal."""
    rows = [dict(row) for row in rows or () if isinstance(row, dict)]
    setattr(tile, attr, rows)
    build_dir = getattr(tile, "build_dir", None)
    if build_dir:
        try:
            os.makedirs(build_dir, exist_ok=True)
            _write_key(build_dir, key, rows)
        except OSError:
            pass
    return rows


def _read_rows(tile, attr: str, key: str) -> list:
    own = getattr(tile, attr, None)
    if own is not None:
        return list(own)
    try:
        return list(_read_all(tile.build_dir).get(key) or [])
    except (AttributeError, TypeError):
        return []


def record_substitutions(tile, rows) -> list:
    """Publish the base cells this tile's DEM read from a fallback source
    — the same two ways as :func:`record`, for the same reason (the tile's
    final ``BuildDone`` comes from another process).  Called by every
    production DEM load, with an empty list when none.  Never fatal."""
    return _publish_rows(tile, "elevation_substitutions", SUBSTITUTIONS_KEY,
                         rows)


def read_substitutions(tile) -> list:
    """The substituted cells of the tile on disk (see :func:`read`)."""
    return _read_rows(tile, "elevation_substitutions", SUBSTITUTIONS_KEY)


#: Sidecar key of the airports graded WITHOUT their pack because the pack
#: is a link to a drive that is not mounted (#668, ``O4_Unmounted_Links``).
UNMOUNTED_KEY = "unmounted_packs"


def record_unmounted_packs(tile, rows) -> list:
    """Publish the airports of this tile whose pack is an unreachable
    link (rows of ``O4_Unmounted_Links.unmounted_packs``) — called by every
    vector step, before it rewrites the patches.  Never fatal."""
    return _publish_rows(tile, "unmounted_packs", UNMOUNTED_KEY, rows)


def read_unmounted_packs(tile) -> list:
    """The rows :func:`record_unmounted_packs` published for the tile on
    disk (see :func:`read`)."""
    return _read_rows(tile, "unmounted_packs", UNMOUNTED_KEY)


#: Sidecar key of the DEGRADED outputs (#853): ``{source: [row, ...]}``,
#: one list per step part that can degrade, each restated whole by that
#: part on every run (an empty list clears it).
DEGRADED_KEY = "degraded"


def record_degraded(tile, source: str, rows) -> list:
    """Publish what the build part ``source`` (``"imagery"``, ``"masks"``,
    ``"airport-insets"``) produced NOT as asked — rows of
    ``{"code", "detail", ...words}`` with a DEGRADED ``O4_Tile_Failures``
    code — replacing that part's earlier rows; the final ``BuildDone``
    names them as warnings (:func:`read_degraded`).  Never fatal."""
    rows = [dict(row) for row in rows or () if isinstance(row, dict)]
    own = getattr(tile, "degraded_outputs", None)
    if own is None:
        own = {}
        build_dir = getattr(tile, "build_dir", None)
        if build_dir:
            on_disk = _read_all(build_dir).get(DEGRADED_KEY)
            own = dict(on_disk) if isinstance(on_disk, dict) else {}
    own[str(source)] = rows
    try:
        tile.degraded_outputs = own
    except AttributeError:                     # a slotted stand-in tile
        pass
    build_dir = getattr(tile, "build_dir", None)
    if build_dir:
        try:
            os.makedirs(build_dir, exist_ok=True)
            _write_key(build_dir, DEGRADED_KEY, own)
        except OSError:
            pass
    return rows


def read_degraded(tile) -> list:
    """Every degraded row of the tile on disk, in source order (see
    :func:`read`)."""
    own = getattr(tile, "degraded_outputs", None)
    if own is None:
        try:
            own = _read_all(tile.build_dir).get(DEGRADED_KEY)
        except (AttributeError, TypeError):
            own = None
    if not isinstance(own, dict):
        return []
    return [dict(row) for source in sorted(own)
            for row in own[source] or () if isinstance(row, dict)]


def note_pack(tile, icao: str, text: str, pack: str = "",
              reason: str = "") -> None:
    """Add to ``icao``'s record what could NOT be done about its pack.

    Owner RULINGS 2026-10-12d: an airport left without a patch gets its
    original pack back, and a restore that cannot be proven is NAMED,
    never skipped silently — the pack may still be seated for the graded
    ground this tile no longer has.  The object stage (which runs after
    the mesh, usually in another process) calls this; the sentence lands
    under :data:`PACK_RESTORE_KEY` in the sidecar the final step reads."""
    unpatched = read(tile)
    for rec in unpatched:
        if rec.get("icao") == icao:
            earlier = rec.get(PACK_RESTORE_KEY)
            rec[PACK_RESTORE_KEY] = (earlier + " " + text) if earlier else text
            # the pieces a front-end message is worded from (#562)
            if pack:
                rec[PACK_RESTORE_KEY + "_pack"] = pack
            if reason:
                rec[PACK_RESTORE_KEY + "_reason"] = reason
    tile.auto_patch_unpatched = unpatched
    _write_sidecar(tile, unpatched)


def read(tile) -> list:
    """The airports the tile on disk was built without — this process's
    own record when it ran the vector step, else the sidecar's."""
    own = getattr(tile, "auto_patch_unpatched", None)
    if own is not None:
        return list(own)
    try:
        with open(_sidecar_path(tile.build_dir), encoding="utf-8") as handle:
            return list(json.load(handle).get("unpatched") or [])
    except (OSError, ValueError, AttributeError, TypeError):
        return []


def warn(tile, unpatched) -> None:
    """The engine log's account: one warning naming every airport the tile
    is built without, and one line per airport with its cause."""
    if not unpatched:
        return
    import O4_UI_Utils as UI

    UI.loud_warning(
        "   WARNING: this tile is built WITHOUT the airport patch of {} "
        "airport(s): {}. Each keeps the ungraded terrain; the rest of the "
        "tile is unaffected.".format(
            len(unpatched), ", ".join(rec["icao"] for rec in unpatched)))
    for rec in unpatched:
        UI.loud_warning("   {}: no patch ({}): {}".format(
            rec["icao"], rec["stage"], rec["error"]))
