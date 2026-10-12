"""Tile-ending failures in the user's words: the ONE catalogue (issue #562).

Owner requirement (2026-10-12): any error that leaves a tile unbuilt has a
user-facing message — what failed, why, and what to do.  This module owns
that text for every front end; the session (``o4_engine.session``) composes
it into ``BuildDone.failures`` and the apps only render it.

Two classes share the catalogue and the carrier (owner RULINGS 2026-10-12a,
#564): a TILE-ENDING failure ("Tile X was not built: …") and an AIRPORT
WITHOUT A PATCH on a tile that was built ("Tile X was built, but …",
``BuildDone.warnings``).

A failure is named by a stable ``code``.  A code reaches here three ways:

* an exception — :func:`code_for_exception` reads an explicit
  ``failure_code`` attribute first, then the errno, then the class NAMES
  along the MRO (:data:`EXCEPTION_CODES`).  Never the message text: a
  reworded refusal keeps its code.
* an airport's failure record — its ``stage`` (:data:`STAGE_CODES`) unless
  the record already carries a ``code``.
* a step that prints its error and returns 0 —
  ``UI.exit_message_and_bottom_line(..., code="...")`` or
  ``UI.tile_failure("...")``.

ADDING A FAILURE CLASS: one :data:`CATALOGUE` entry, plus either the
exception class name in :data:`EXCEPTION_CODES` or ``failure_code = "..."``
on the class (an optional ``failure_params`` dict fills ``{pack}``).
``tests/test_tile_failures.py`` fails for an exception class or an error
exit that has no entry.

Stdlib only: the airport workers and the core step modules import it.
"""

from __future__ import annotations

import errno as _errno
from typing import Iterable, NamedTuple, Optional

__all__ = [
    "CATALOGUE", "EXCEPTION_CODES", "STAGE_CODES", "REMEDIES", "UNMAPPED",
    "UNMAPPED_AIRPORT", "UNMAPPED_STEP", "code_for_exception",
    "params_for_exception", "record_fields", "code_for_stage", "record", "fold", "headline",
    "render",
]


class Entry(NamedTuple):
    """One failure class: the tail of "Tile X was not built: …", the cause
    and the remedy key (:data:`REMEDIES`)."""

    what: str
    why: str
    remedy: str


# The fixed remedy set (the master rules the copy; census
# docs/briefs/failmsg562-census.md).
REMEDIES = {
    "retry": "Build the tile again. If it fails again, report it and "
             "attach the log{log}.",
    "network": "Check the internet connection, then build the tile again.",
    "later": "Try again later.",
    "disk": "Free some disk space, then build the tile again.",
    "pack": "Update, repair or disable that scenery pack, then build the "
            "tile again.",
    "report": "Report it and attach the log{log}.",
    "settings": "Check the X-Plane folder and the sources chosen in "
                "Settings, then build the tile again.",
    "all_steps": "Build the tile again with every step selected.",
    "reinstall": "Update or reinstall the app. If it still fails, report "
                 "it and attach the log{log}.",
}

UNMAPPED = "unexpected_error"          # an exception nobody catalogued
UNMAPPED_AIRPORT = "airport_failed"    # ...inside one airport's build
UNMAPPED_STEP = "step_failed"          # a step returned 0 and said nothing

CATALOGUE = {
    # ── per airport ────────────────────────────────────────────────────
    "airport_geometry": Entry(
        "{airports} could not be processed.",
        "Its pavement outlines produced a shape the app could not work "
        "with.", "report"),
    "airport_failed": Entry(
        "{airports} could not be processed.",
        "The app hit a problem it does not recognise in this airport's "
        "data.", "report"),
    "airport_solve": Entry(
        "the ground at {airports} could not be shaped.",
        "The app found no surface that meets its slope limits there.",
        "report"),
    "airport_verify": Entry(
        "the ground at {airports} failed its final check.",
        "The shaped surface broke one of the app's own rules, so it was "
        "not used.", "report"),
    "airport_write": Entry(
        "the result for {airports} could not be saved.",
        "The app could not write its working files.", "retry"),
    "airport_worker_died": Entry(
        "work on {airports} stopped unexpectedly.",
        "A background process ended early, most often because the "
        "computer ran out of memory.", "retry"),
    "airport_no_result": Entry(
        "{airports} produced no result.",
        "A background process ended without reporting why.", "retry"),
    "airport_data_missing": Entry(
        "X-Plane's airport data was not found.",
        "The app could not find the navigation data in the X-Plane "
        "folder it was given.", "settings"),
    "airport_elevation_missing": Entry(
        "elevation data for {airports} was not available.",
        "The detailed elevation for this airport could not be prepared.",
        "network"),
    "pack_dump_stale": Entry(
        "scenery for {airports} could not be read.",
        "The app could not make a readable copy of the file from {pack} "
        "for this tile.", "pack"),
    "pack_dump_failed": Entry(
        "scenery for {airports} could not be read.",
        "The file from {pack} for this tile could not be converted.",
        "pack"),
    "pack_write_failed": Entry(
        "objects for {airports} could not be updated.",
        "The app could not safely rewrite the file of {pack}.", "pack"),
    "road_data_stale": Entry(
        "the road data for this area is out of date.",
        "It could not be refreshed, which needs an internet connection.",
        "network"),
    # ── whole tile ─────────────────────────────────────────────────────
    "elevation_download_failed": Entry(
        "its elevation data could not be downloaded.",
        "The elevation server did not answer, or the connection to it "
        "was blocked.", "network"),
    "elevation_cache_bad": Entry(
        "saved elevation data for this tile could not be read.",
        "A file left by an earlier build is damaged or out of date.",
        "retry"),
    "elevation_source_unset": Entry(
        "no usable elevation source is set for it.",
        "The elevation source in the tile's settings is missing or does "
        "not match the saved data.", "settings"),
    "map_data_failed": Entry(
        "the map data for this area could not be prepared.",
        "The downloaded OpenStreetMap extract could not be read or "
        "filtered.", "retry"),
    "mesh_refused": Entry(
        "the terrain mesh could not be built.",
        "The tile's shapes failed one of the app's own safety checks.",
        "report"),
    "mesh_failed": Entry(
        "the terrain mesh could not be built.",
        "The mesh program stopped, most often because the computer ran "
        "out of memory.", "retry"),
    "earlier_step_missing": Entry(
        "files from an earlier step are missing.",
        "The step before this one did not finish, or its files were "
        "deleted.", "all_steps"),
    "imagery_source_unknown": Entry(
        "no usable imagery source is set for it.",
        "The imagery source named in the tile's settings is not one the "
        "app knows.", "settings"),
    "imagery_download_failed": Entry(
        "its aerial images could not be downloaded.",
        "None of the downloads from the imagery source succeeded.",
        "network"),
    "scenery_file_failed": Entry(
        "its scenery file could not be written.",
        "The app hit a problem while assembling the tile's scenery file.",
        "report"),
    "output_folder_unwritable": Entry(
        "its output folder could not be written.",
        "The disk is full or the folder is protected.", "disk"),
    "overlay_source_missing": Entry(
        "X-Plane's default scenery for this tile was not found.",
        "The overlay is copied from X-Plane's Global Scenery, which is "
        "missing for this tile.", "settings"),
    "overlay_tool_failed": Entry(
        "its overlay could not be converted.",
        "A helper program the app ships did not run.", "reinstall"),
    "app_component_broken": Entry(
        "a part of the app is not working.",
        "Its map-projection component failed its start-up check.",
        "reinstall"),
    # ── any step ───────────────────────────────────────────────────────
    "network_unavailable": Entry(
        "something it needs could not be downloaded.",
        "The internet connection failed or the server did not answer.",
        "network"),
    "disk_full": Entry(
        "the disk is full.",
        "There was no room left to write the tile's files.", "disk"),
    "no_permission": Entry(
        "the app was not allowed to write a file.",
        "A folder it needs is read-only or protected.", "settings"),
    "out_of_memory": Entry(
        "the computer ran out of memory.",
        "This tile needed more memory than was free.", "later"),
    "file_missing": Entry(
        "a file it needs was not found.",
        "It is missing from the X-Plane install, a scenery pack or the "
        "app's working folder.", "settings"),
    "worker_died": Entry(
        "the build stopped unexpectedly.",
        "A background process ended early, most often because the "
        "computer ran out of memory.", "retry"),
    # ── the fallbacks: never a bare exception string as the headline ───
    "step_failed": Entry(
        "the {step} step failed.",
        "The app did not record a specific cause.", "report"),
    "unexpected_error": Entry(
        "the app ran into an unexpected problem.",
        "This is a fault in the app, not in your setup.", "report"),
}

# Exception class NAME -> code, matched along the MRO (most derived first),
# so a subclass inherits its parent's entry and no module is imported to
# ask.  Every exception class defined under ``src/`` is listed (the twin
# walks them); one that says nothing more specific maps to a fallback.
EXCEPTION_CODES = {
    # geometry (shapely's GEOSException covers TopologyException, #559)
    "GEOSException": "airport_geometry",
    "TopologicalError": "airport_geometry",
    "GeomSafeError": "airport_geometry",
    "PlanarError": "airport_geometry",
    # elevation
    "ElevationDownloadRefused": "elevation_download_failed",
    "ProviderUnavailable": "elevation_download_failed",
    "TransientFetchError": "elevation_download_failed",
    "AltFrameRefused": "elevation_cache_bad",
    "ColdDemFrame": "airport_elevation_missing",
    "ColdTile": "airport_elevation_missing",
    # map data
    "ExtractFilterError": "map_data_failed",
    "AtlasApiError": "network_unavailable",
    # mesh
    "BankAnnulusCollapse": "mesh_refused",
    "InterpAltLeak": "mesh_refused",
    "UnsealedInterpAltSeed": "mesh_refused",
    # scenery packs
    "PackDumpStale": "pack_dump_stale",
    "BackupUnproven": "pack_write_failed",
    "StaleScreen": "pack_write_failed",
    "ColdPartition": "pack_write_failed",
    # airport build internals with nothing a user can act on
    "LawError": UNMAPPED_AIRPORT,
    "RulesError": UNMAPPED_AIRPORT,
    "OrphanShapeError": UNMAPPED_AIRPORT,
    "OutsideMeshError": UNMAPPED_AIRPORT,
    "StrippedField": UNMAPPED_AIRPORT,
    "Unreplayable": UNMAPPED_AIRPORT,
    # caught before the worker / never raised by an app build
    "AutoPatchBuildFailure": UNMAPPED_AIRPORT,
    "ExternalWriteRefused": UNMAPPED,
    "LoginError": UNMAPPED,
    "CredentialStoreUnavailable": UNMAPPED,
    # the standard library and the HTTP stack
    "MemoryError": "out_of_memory",
    "FileNotFoundError": "file_missing",
    "PermissionError": "no_permission",
    "ConnectionError": "network_unavailable",
    "TimeoutError": "network_unavailable",
    "RequestException": "network_unavailable",
    "URLError": "network_unavailable",
    "HTTPError": "network_unavailable",
    "BrokenProcessPool": "airport_worker_died",
}

_ERRNO_CODES = {
    _errno.ENOSPC: "disk_full",
    getattr(_errno, "EDQUOT", -1): "disk_full",
    _errno.EACCES: "no_permission",
    _errno.EPERM: "no_permission",
    _errno.EROFS: "no_permission",
}

# An airport record's ``stage`` (auto_patch.driver.AutoPatchBuildFailure).
STAGE_CODES = {
    "build": UNMAPPED_AIRPORT,
    "solve": "airport_solve",
    "verify": "airport_verify",
    "write": "airport_write",
    "worker": "airport_worker_died",
    "missing": "airport_no_result",
    "manifest": "airport_no_result",
    "config": "airport_data_missing",
}

AIRPORTS_NAMED = 6      # more than this many fold into "and N more"


def code_for_exception(exc: BaseException, default: str = UNMAPPED) -> str:
    """The catalogue code of ``exc``; ``default`` when nothing names it.

    Order: an explicit ``failure_code`` attribute, the errno (disk full,
    not permitted), then the class names along the MRO.
    """
    explicit = getattr(exc, "failure_code", None)
    if explicit in CATALOGUE:
        return explicit
    by_errno = _ERRNO_CODES.get(getattr(exc, "errno", None))
    if by_errno:
        return by_errno
    for klass in type(exc).__mro__:
        code = EXCEPTION_CODES.get(klass.__name__)
        if code:
            return code
    return default


def params_for_exception(exc: BaseException) -> dict:
    """The exception's own ``failure_params`` (``{"pack": name}``), as
    strings; empty when it declares none."""
    params = getattr(exc, "failure_params", None)
    if not isinstance(params, dict):
        return {}
    return {str(k): str(v) for k, v in params.items()}


def record_fields(exc: BaseException) -> dict:
    """The ``code`` / ``params`` keys an airport worker adds to its failure
    record (picklable).  ``code`` is ``""`` when only the stage can say."""
    return {"code": code_for_exception(exc, default=""),
            "params": params_for_exception(exc)}


def code_for_stage(stage: str, code: Optional[str] = None) -> str:
    """An airport record's code: its own when catalogued, else its stage's."""
    if code in CATALOGUE:
        return code
    return STAGE_CODES.get(str(stage or ""), UNMAPPED_AIRPORT)


def record(code: str, detail: str = "", airport: str = "",
           **params) -> dict:
    """One raw failure, before folding.  An unknown ``code`` becomes the
    generic one — the headline is never whatever string arrived.
    ``airport`` (even ``"*"``, every airport of the tile) marks the record
    as AIRPORT-scoped: it costs a patch, not necessarily the tile."""
    scope = "airport" if airport else "tile"
    if code not in CATALOGUE:
        detail = ("[%s] %s" % (code, detail)).strip()
        code = UNMAPPED_AIRPORT if airport else UNMAPPED
    airport = "" if airport in ("*", "?") else str(airport or "")
    return {"code": code, "detail": str(detail or ""), "airport": airport,
            "scope": scope,
            "params": {str(k): str(v) for k, v in params.items()
                       if v not in (None, "")}}


def _airports_phrase(airports: list) -> str:
    if not airports:
        return "an airport"
    named = list(airports[:AIRPORTS_NAMED])
    rest = len(airports) - len(named)
    if rest:
        return "airports %s and %d more" % (", ".join(named), rest)
    if len(named) == 1:
        return "airport " + named[0]
    return "airports %s and %s" % (", ".join(named[:-1]), named[-1])


UNPATCHED = "An airport without a patch is left on ungraded terrain."


def _describe(code: str, tile: str, airports: list, params: dict,
              details: list, built: bool, log_path: str) -> dict:
    entry = CATALOGUE[code]
    pack = params.get("pack")
    words = {
        "airports": _airports_phrase(airports),
        "pack": ("the scenery pack “%s”" % pack) if pack
                else "a scenery pack on this tile",
        "step": params.get("step") or "build",
    }
    why = entry.why.format(**words)
    why = why[:1].upper() + why[1:]
    lead = "Tile %s was built, but " if built else "Tile %s was not built: "
    return {
        "code": code,
        "what": lead % tile + entry.what.format(**words),
        "why": (why + " " + UNPATCHED) if built else why,
        "remedy": REMEDIES[entry.remedy].replace(
            "{log}", (" (%s)" % log_path) if log_path else ""),
        "airports": list(airports),
        "detail": "\n".join(details),
        "log_path": log_path,
    }


def fold(records: Iterable[dict], tile: str, built: bool = False,
         log_path: str = "") -> list:
    """The tile's failures, one per CAUSE: records with the same code and
    parameters fold into one message listing their airports (six airports
    refused for one stale file are one message, not six).  First-seen
    order; each entry is the wire dict of ``BuildDone.failures`` — or,
    with ``built``, of ``BuildDone.warnings``: the tile was built and the
    airports named are the ones without a patch.  ``log_path`` is named
    by every "report it" remedy."""
    groups: dict = {}
    for rec in records:
        key = (rec["code"], tuple(sorted(rec.get("params", {}).items())))
        group = groups.setdefault(key, {"airports": [], "details": []})
        airport = rec.get("airport")
        if airport and airport not in group["airports"]:
            group["airports"].append(airport)
        detail = rec.get("detail")
        if detail:
            line = "%s: %s" % (airport, detail) if airport else detail
            if line not in group["details"]:
                group["details"].append(line)
    return [_describe(code, tile, group["airports"], dict(params),
                      group["details"], built, log_path)
            for (code, params), group in groups.items()]


def render(failure: dict) -> str:
    """One folded failure as the three lines every front end shows."""
    return "%s\n%s\n%s" % (failure.get("what", ""), failure.get("why", ""),
                           failure.get("remedy", ""))


def headline(failures: list) -> str:
    """``BuildDone.error`` — the plain sentence an older front end (which
    reads only that field) shows.  Never the exception text."""
    return " | ".join(" ".join((f["what"], f["why"], f["remedy"]))
                      for f in failures)
