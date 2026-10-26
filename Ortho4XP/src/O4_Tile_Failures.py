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
  ``UI.tile_failure("...")``.  A refused ACTIVATION of a finished scenery
  file names its code with :func:`code_for_activation` (#585).

A third class (issue #853, spec code-quality-beta3 §2): a DEGRADED
outcome — the tile was built, but not as asked (white-squared textures,
an airport inset not fetched, a mask built without what it was told to
use).  The step that degraded publishes a row beside the tile
(``O4_Unpatched_Airports.record_degraded``); :func:`from_degraded` turns
the rows into records, and they ride ``BuildDone.warnings`` like an
unpatched airport.  Every entry has a severity (:data:`SEVERITIES`) and a
domain (:data:`DOMAINS`); every folded entry carries the OCCURRENCE's
severity on the wire (``severity``, protocol 1.13, additive).
``docs/degraded-census.md`` is the census of the step modules' WARNING
prints; ``tests/test_tile_failures.py`` reads it as its table.

ADDING A FAILURE CLASS: one :data:`CATALOGUE` entry, plus either the
exception class name in :data:`EXCEPTION_CODES` or ``failure_code = "..."``
on the class (an optional ``failure_params`` dict fills ``{pack}``).
``tests/test_tile_failures.py`` fails for an exception class or an error
exit that has no entry.

Stdlib only: the airport workers and the core step modules import it.
"""

from __future__ import annotations

import errno as _errno
import os
from typing import Iterable, NamedTuple, Optional

__all__ = [
    "CATALOGUE", "EXCEPTION_CODES", "STAGE_CODES", "REMEDIES", "UNMAPPED",
    "UNMAPPED_AIRPORT", "UNMAPPED_STEP", "code_for_exception",
    "code_for_activation", "params_for_exception", "record_fields", "code_for_stage", "record", "fold", "headline",
    "render", "from_unpatched", "from_substitutions", "from_unmounted",
    "closing_lines",
    "is_proxy_refusal",
    "SEVERITIES", "DOMAINS", "SEVERITY_LABELS", "severity_of", "domain_of",
    "from_degraded",
]


class Entry(NamedTuple):
    """One failure class: the tail of "Tile X was not built: …", the cause
    and the remedy key (:data:`REMEDIES`).

    ``severity`` (:data:`SEVERITIES`) is what the class is when it is the
    tile's own outcome; ``domain`` (:data:`DOMAINS`) is the part of the
    build it belongs to — empty when the code's first word names it
    (:func:`domain_of`)."""

    what: str
    why: str
    remedy: str
    severity: str = "blocking"
    domain: str = ""


#: ``blocking``: the tile was not built (for an airport code: the airport
#: has no patch).  ``degraded``: built, but an output is not what was
#: asked.  ``info``: built as asked, with something worth knowing.
SEVERITIES = ("blocking", "degraded", "info")

#: The part of the build a code belongs to.
DOMAINS = ("airport", "pack", "elevation", "map", "mesh", "masks",
           "imagery", "scenery", "overlay", "network", "system", "app")

#: A code's first word that is not itself a domain -> its domain.
_WORD_DOMAINS = {
    "road": "map", "texture": "imagery", "output": "system",
    "proxy": "network", "disk": "system", "no": "system", "out": "system",
    "file": "system", "earlier": "app", "worker": "app", "step": "app",
    "unexpected": "app", "inset": "elevation", "mask": "masks",
}

#: How both apps label a wire ``severity`` (identical to the mac app's
#: ``O4TileFailureCopy.severityLabel``).
SEVERITY_LABELS = {"blocking": "Not built", "degraded": "Warning",
                   "info": "Note"}


# The fixed remedy set (the master rules the copy; census
# docs/briefs/failmsg562-census.md).
REMEDIES = {
    "retry": "Build the tile again. If it fails again, {report}.",
    "network": "Check the internet connection, then build the tile again.",
    "later": "Try again later.",
    "disk": "Free some disk space, then build the tile again.",
    "pack": "Update, repair or disable that scenery pack, then build the "
            "tile again.",
    "report": "{Report}.",
    # the per-pack control both apps show in "Modified airports"
    "restore_pack": "Use Revert to default for that scenery pack (under "
                    "Modified airports), or reinstall it.",
    "rebuild_later": "Build the tile again later to replace it.",
    "memory": "Close other apps to free memory, then build the tile again.",
    "permissions": "Check that the app is allowed to write to the X-Plane "
                   "folder and its own data folder, then build the tile "
                   "again.",
    "settings": "Check the X-Plane folder and the sources chosen in "
                "Settings, then build the tile again.",
    "all_steps": "Build the tile again with every step selected.",
    "reinstall": "Update or reinstall the app. If it still fails, "
                 "{report}.",
    "quit_xplane": "Quit X-Plane if it is running, then build the tile "
                   "again. If it fails again, check that the app is "
                   "allowed to write to the tile's folder.",
    # a link into a drive that is not mounted (#668); ``{connect}`` names
    # the drive.  Both apps offer the removal as a button.
    "unmounted_output": "{connect} and build the tile again, or remove the "
                        "link to build on this computer's drive.",
    "unmounted_pack": "{connect} and build the tile again.",
    "elevation_link": "{connect}, or replace the link with an empty "
                      "folder, then build the tile again.",
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
    # issue #623: the solve met its rules and still put part of the surface
    # far off the ground (a level read from the wrong place)
    "airport_surface_off_ground": Entry(
        "the ground at {airports} came out at an impossible height.",
        "Part of the shaped surface stood far above or below the terrain "
        "around the airport, so it was not used.", "report"),
    "airport_verify": Entry(
        "the ground at {airports} failed its final check.",
        "The shaped surface broke one of the app's own rules, so it was "
        "not used.", "report"),
    "airport_write": Entry(
        "the result for {airports} could not be saved.",
        "The app could not write its working files.", "retry"),
    "airport_worker_died": Entry(
        "work on {airports} stopped unexpectedly.",
        "A background process ended early.", "retry"),
    "airport_no_result": Entry(
        "{airports} produced no result.",
        "A background process ended without reporting why.", "retry"),
    "airport_data_missing": Entry(
        "X-Plane's airport data was not found.",
        "The app could not find the navigation data in the X-Plane "
        "folder it was given.", "settings"),
    # A cold production frame names its cause in its own code
    # (``dem_production.cold_frame_code``, issue #1352): a cache this
    # build never filled is not an internet problem, and an airport
    # outside the inset selection or with no provider coverage is not
    # cold at all (it is patched on the base elevation).
    "airport_elevation_missing": Entry(
        "elevation data for {airports} was not available.",
        "The detailed elevation for this airport was not in the app's "
        "cache, and this build did not download it.",
        "retry"),
    "airport_elevation_offline": Entry(
        "elevation data for {airports} was not available.",
        "The download of the detailed elevation for this airport failed.",
        "network"),
    "pack_dump_stale": Entry(
        "scenery for {airports} could not be read.",
        "The app could not make a readable copy of the file from {pack} "
        "for this tile.", "retry"),
    # X-Plane's own converter failed on the pack's file (lane dump560's
    # ``DsfToolError``; a crash on a stock file is a bug, #568): retrying
    # does not help, so this one is "report it".
    "pack_dump_failed": Entry(
        "scenery for {airports} could not be read.",
        "The file from {pack} for this tile could not be converted.",
        "report"),
    # ...and when the converter was stopped at its time limit (the
    # exception's ``timed_out``): a retry can succeed.
    "pack_dump_timed_out": Entry(
        "scenery for {airports} could not be read.",
        "Converting the file from {pack} for this tile took too long.",
        "retry"),
    # an exception inside ONE pack object's build (pack_partition)
    "pack_object_failed": Entry(
        "{airports} could not be graded.",
        "{pack} contains an object the app could not process.", "report"),
    # an unpatched airport whose pack could not be put back (RULINGS
    # 2026-10-12d; ``O4_Unpatched_Airports.PACK_RESTORE_KEY``)
    "pack_restore_unproven": Entry(
        "objects at {airports} may float or sink.",
        "An earlier build moved the objects of {pack} onto graded ground, "
        "and they could not be put back: {reason}", "restore_pack",
        severity="degraded"),
    # a NOTE, not a failure: a base cell read from a fallback source
    # (RULINGS 2026-10-12e; ``elevation_access.base_fallback``)
    "elevation_substituted": Entry(
        "with stand-in elevation for {cells}.",
        "{source} did not answer, so {fallback} was used. It includes "
        "trees and buildings, so the ground there may read a few metres "
        "high.", "rebuild_later", severity="info"),
    "pack_write_failed": Entry(
        "objects for {airports} could not be updated.",
        "The app could not safely rewrite the file of {pack}.", "pack"),
    "road_data_stale": Entry(
        "the road data for this area is out of date.",
        "It could not be refreshed, which needs an internet connection.",
        "network"),
    # ── degraded: built, but not as asked (#853, docs/degraded-census.md)
    "imagery_incomplete": Entry(
        "some of its aerial images are missing.",
        "{textures} could not be downloaded from {imagery_source}, so they "
        "show as white squares.", "network", severity="degraded"),
    "inset_fetch_failed": Entry(
        "the detailed elevation for {airports} could not be downloaded.",
        "{inset_source} did not answer, so the ground there was shaped from "
        "the standard elevation data.", "network", severity="degraded"),
    "mask_extent_missing": Entry(
        "its water masks were built without the custom extent you chose.",
        "The extent “{extent}” was not found in the app's Extents folder, "
        "so the regular masks were used.", "settings", severity="degraded"),
    "mask_shallow_water_skipped": Entry(
        "part of its shallow-water shading is missing.",
        "The map data for {category} could not be downloaded, so those "
        "areas are not shaded as shallow water.", "network",
        severity="degraded"),
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
    # issue #1354: OSM coastline would turn high ground into sea
    "map_coastline_implausible": Entry(
        "the coastline map data for this area looks wrong.",
        "OpenStreetMap marks most of this tile as sea, but its ground is "
        "far above sea level everywhere.", "report"),
    "mesh_refused": Entry(
        "the terrain mesh could not be built.",
        "The tile's shapes failed one of the app's own safety checks.",
        "report"),
    "mesh_failed": Entry(
        "the terrain mesh could not be built.",
        "The mesh program stopped before it finished.", "retry"),
    "earlier_step_missing": Entry(
        "files from an earlier step are missing.",
        "The step before this one did not finish, or its files were "
        "deleted.", "all_steps"),
    "imagery_source_unknown": Entry(
        "no usable imagery source is set for it.",
        "The imagery source named in the tile's settings is not one the "
        "app knows.", "settings"),
    # a texture neither encoder converted (#900/#901): the new scenery
    # file is not activated, since X-Plane stops on a missing texture
    "texture_convert_failed": Entry(
        "some of its textures could not be converted.",
        "{textures} could not be converted; X-Plane stops on a missing "
        "texture, so the new scenery was not put in place.", "retry"),
    "imagery_download_failed": Entry(
        "its aerial images could not be downloaded.",
        "None of the downloads from the imagery source succeeded.",
        "network"),
    "scenery_file_failed": Entry(
        "its scenery file could not be written.",
        "The app hit a problem while assembling the tile's scenery file.",
        "report"),
    # The finished file could not be moved into place (#585): the tile is
    # NOT active.  See :func:`code_for_activation`.
    "scenery_file_locked": Entry(
        "its new scenery file could not be put in place.",
        "The file it replaces is in use or protected.", "quit_xplane"),
    "scenery_file_not_activated": Entry(
        "its new scenery file could not be put in place.",
        "The finished file could not be moved into the tile's folder.",
        "retry"),
    # the tile's folder in Custom Scenery is a link whose target is
    # missing — a drive not mounted (#668, ``O4_Unmounted_Links``)
    "output_link_unmounted": Entry(
        "its folder in Custom Scenery could not be reached.",
        "“{link_name}” is a link to “{target}”, {missing}.",
        "unmounted_output"),
    # ...the tile's elevation bucket folder is such a link (#1167): the
    # link is the user's, so the remedy names it and nothing removes it
    "elevation_link_broken": Entry(
        "its elevation data folder could not be reached.",
        "“{link_name}” is a link to “{target}”, {missing}.",
        "elevation_link"),
    # ...and a pack the build only READS: the tile builds, the airport is
    # graded from X-Plane's own data (the #564 "built, but" path)
    "airport_pack_unmounted": Entry(
        "{airports} {was} graded without {pack}.",
        "The pack is a link to “{target}”, {missing}, so X-Plane's own "
        "airport data was used instead; the ground may not match the pack "
        "when the drive is back.", "unmounted_pack", severity="degraded"),
    "output_folder_unwritable": Entry(
        "its output folder could not be written.",
        "The folder is protected or the disk is full.", "permissions"),
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
    # A refusal that KNOWS a proxy answered sets failure_code to this.
    "proxy_refused": Entry(
        "something it needs could not be downloaded.",
        "Your proxy or VPN refused the connection.", "network"),
    "disk_full": Entry(
        "the disk is full.",
        "There was no room left to write the tile's files.", "disk"),
    "no_permission": Entry(
        "the app was not allowed to write a file.",
        "A folder it needs is read-only or protected.", "permissions"),
    "out_of_memory": Entry(
        "the computer ran out of memory.",
        "This tile needed more memory than was free.", "memory"),
    "file_missing": Entry(
        "a file it needs was not found.",
        "It is missing from the X-Plane install, a scenery pack or the "
        "app's working folder.", "settings"),
    "worker_died": Entry(
        "the build stopped unexpectedly.",
        "A background process ended early.", "retry"),
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
    "ElevationTransportRefused": "elevation_download_failed",
    "ElevationAbsentRefused": "elevation_download_failed",
    "ProviderQueryError": "elevation_download_failed",
    "ProviderUnavailable": "elevation_download_failed",
    "TransientFetchError": "elevation_download_failed",
    "AltFrameRefused": "elevation_cache_bad",
    "ColdDemFrame": "airport_elevation_missing",
    "ColdTile": "airport_elevation_missing",
    # map data
    "ExtractFilterError": "map_data_failed",
    "AtlasApiError": "network_unavailable",
    "ImplausibleSeaTile": "map_coastline_implausible",
    # mesh
    "BankAnnulusCollapse": "mesh_refused",
    "InterpAltLeak": "mesh_refused",
    "UnsealedInterpAltSeed": "mesh_refused",
    # a malformed or truncated .mesh / Triangle exchange file (O4_Mesh_IO, O4_Triangle_IO)
    "MeshFormatError": "mesh_failed",
    "TriangleFormatError": "mesh_failed",
    # scenery packs
    "PackDumpStale": "pack_dump_stale",
    "DsfToolError": "pack_dump_failed",
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
    # a stage-cache record that may not be served (#843): caught inside
    # the build, which then runs the stage — never a failure
    "Refused": UNMAPPED_AIRPORT,
    # caught before the worker / never raised by an app build
    "AutoPatchBuildFailure": UNMAPPED_AIRPORT,
    "ExternalWriteRefused": UNMAPPED,
    # o4_engine.command_process (#753): a queued preview read nobody wants
    # any more is skipped, never shown — never a build failure
    "Superseded": UNMAPPED,
    # O4_Unmounted_Links (#668) names its code with ``failure_code``
    "UnmountedLink": "output_link_unmounted",
    "ElevationLinkBroken": "elevation_link_broken",
    "LoginError": UNMAPPED,
    "CredentialStoreUnavailable": UNMAPPED,
    # O4_Flight_Plan (#829): a plan the "Select from flight plan" dialog
    # cannot read is shown in that dialog — never a build failure
    "FlightPlanError": UNMAPPED,
    # the standard library and the HTTP stack
    "MemoryError": "out_of_memory",
    "FileNotFoundError": "file_missing",
    "PermissionError": "no_permission",
    "ProxyError": "proxy_refused",
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
            # a converter stopped at its time limit may finish next time;
            # one that crashed or failed will not (``DsfToolError``)
            if code == "pack_dump_failed" and getattr(exc, "timed_out",
                                                      False):
                return "pack_dump_timed_out"
            return code
    return default


def code_for_activation(exc: BaseException) -> str:
    """The code of a refused ACTIVATION — the rename, replace or copy that
    puts a finished scenery file where X-Plane reads it (#585).

    A refused permission there is a file in use at least as often as a
    protected folder (Windows refuses to replace a file a running X-Plane
    holds open, and reports it as "access denied"), so it gets the remedy
    that names X-Plane.  A full disk keeps its own code; anything else —
    the finished file missing — is the generic "not put in place".
    """
    if (isinstance(exc, PermissionError)
            or getattr(exc, "winerror", None) in (5, 32)):
        return "scenery_file_locked"
    by_errno = _ERRNO_CODES.get(getattr(exc, "errno", None))
    return by_errno or "scenery_file_not_activated"


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


def severity_of(code: str) -> str:
    """The catalogue severity of ``code`` (an unknown code is blocking)."""
    entry = CATALOGUE.get(code)
    return entry.severity if entry else "blocking"


def domain_of(code: str) -> str:
    """The domain of ``code``: its entry's own, else its first word's."""
    entry = CATALOGUE.get(code)
    if entry and entry.domain:
        return entry.domain
    word = str(code).split("_", 1)[0]
    return _WORD_DOMAINS.get(word, word)


def is_proxy_refusal(exc: BaseException) -> bool:
    """Whether ``exc`` says a PROXY refused the connection — by class
    (``ProxyError`` anywhere on the MRO) or by its own ``failure_code``."""
    return (getattr(exc, "failure_code", None) == "proxy_refused"
            or any(k.__name__ == "ProxyError" for k in type(exc).__mro__))


def record(code: str, detail: str = "", airport: str = "", cell: str = "",
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
            "scope": scope, "named": str(airport or ""),
            "cell": str(cell or ""),
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


# "Report it", by WHO IS DRIVING: an app has the button (#565); a shell or
# harness build is told where the log is.  The one place that decides.
def _report_phrase(report_button: bool, log_path: str) -> str:
    if report_button:
        return "press Report this problem"
    if log_path:
        return "report it with the log: " + log_path
    return "report it with the log"


UNPATCHED = ("An airport without a patch is left on ungraded terrain; the "
             "next build of this tile tries it again.")


def _cells_phrase(cells: list) -> str:
    if len(cells) <= 1:
        return "cell " + (cells[0] if cells else "?")
    return "cells %s and %s" % (", ".join(cells[:-1]), cells[-1])


def _describe(code: str, tile: str, airports: list, params: dict,
              details: list, built: bool, log_path: str,
              report_button: bool, cells: list, note: bool) -> dict:
    entry = CATALOGUE[code]
    pack = params.get("pack")
    words = {
        "airports": _airports_phrase(airports),
        "cells": _cells_phrase(cells),
        "reason": params.get("reason") or "the cause was not recorded.",
        "source": params.get("source") or "the elevation source",
        "fallback": params.get("fallback") or "another source",
        "pack": ("the scenery pack “%s”" % pack) if pack
                else "a scenery pack on this tile",
        "step": params.get("step") or "build",
        "textures": ("%s of its aerial images" % params["count"])
                    if params.get("count") else "Some of its aerial images",
        "imagery_source": params.get("source") or "the imagery source",
        "inset_source": params.get("source")
                        or "The detailed elevation source",
        "extent": params.get("extent") or "?",
        "category": _CATEGORY_WORDS.get(params.get("category", ""),
                                        "reefs or tidal flats"),
    }
    words.update(_link_words(params))
    words["was"] = "were" if len(airports) > 1 else "was"
    why = entry.why.format(**words)
    why = why[:1].upper() + why[1:]
    lead = ("Tile %s was built " if note else "Tile %s was built, but "
            if built else "Tile %s was not built: ")
    # the unpatched sentence belongs to an airport left WITHOUT a patch: a
    # blocking airport cause on a tile that was built (UNMAPPED is a
    # degraded row whose code was not a degraded one: no airport)
    unpatched = (built and not note and entry.severity == "blocking"
                 and code != UNMAPPED)
    return {
        "code": code,
        # the OCCURRENCE's severity (protocol 1.13, additive): a tile not
        # built is blocking whatever ended it; a built tile's warning is
        # degraded, its note info
        "severity": ("info" if note else "degraded") if built
                    else "blocking",
        "what": lead % tile + entry.what.format(**words),
        "why": (why + " " + UNPATCHED) if unpatched else why,
        "cells": list(cells),
        "remedy": _remedy(entry.remedy, report_button, log_path,
                          words["connect"]),
        "airports": list(airports),
        # the link a front end may offer to remove (#668), else ""
        "link": params.get("link", "") if code == "output_link_unmounted"
                else "",
        "detail": "\n".join(details),
        "log_path": log_path,
    }


# The shallow-water fallback's categories (``O4_Mask_Utils.
# SHALLOW_WATER_CATEGORIES``) in words.
_CATEGORY_WORDS = {"reef": "coral reefs", "tidalflat": "tidal flats"}


def _link_words(params: dict) -> dict:
    """The words of a link whose target is missing (#668): its name, its
    target, and the drive it waits for when the target names one."""
    volume = params.get("volume") or ""
    return {
        "link_name": os.path.basename(params.get("link") or "") or "?",
        "target": params.get("target") or "?",
        "missing": ("and the drive “%s” is not mounted" % volume) if volume
                   else "which no longer exists",
        "connect": ("Mount the drive “%s”" % volume) if volume
                   else "Restore the folder the link points to",
    }


def _remedy(key: str, report_button: bool, log_path: str,
            connect: str = "") -> str:
    phrase = _report_phrase(report_button, log_path)
    text = REMEDIES[key].replace("{report}", phrase).replace(
        "{Report}", phrase[:1].upper() + phrase[1:]).replace(
        "{connect}", connect)
    # a path ends the sentence by itself ("…log: /x/y.log")
    return text[:-1] if text.endswith(".log.") else text


def fold(records: Iterable[dict], tile: str, built: bool = False,
         log_path: str = "", report_button: bool = False,
         note: bool = False) -> list:
    """The tile's failures, one per CAUSE: records with the same code and
    parameters fold into one message listing their airports (six airports
    refused for one stale file are one message, not six).  First-seen
    order; each entry is the wire dict of ``BuildDone.failures`` — or,
    with ``built``, of ``BuildDone.warnings``: the tile was built and the
    airports named are the ones without a patch.  ``log_path`` is the
    log a report reads; ``report_button`` says an APP is driving (it has
    "Report this problem"), else the remedy names that log."""
    groups: dict = {}
    for rec in records:
        key = (rec["code"], tuple(sorted(rec.get("params", {}).items())))
        group = groups.setdefault(key, {"airports": [], "details": [],
                                        "cells": []})
        if rec.get("cell") and rec["cell"] not in group["cells"]:
            group["cells"].append(rec["cell"])
        airport = rec.get("airport")
        if airport and airport not in group["airports"]:
            group["airports"].append(airport)
        detail = rec.get("detail")
        context = rec.get("params", {}).get("context")
        if detail and context:
            detail = "%s [%s]" % (detail, context)
        if detail:
            line = "%s: %s" % (airport, detail) if airport else detail
            if line not in group["details"]:
                group["details"].append(line)
    return [_describe(code, tile, group["airports"], dict(params),
                      group["details"], built, log_path, report_button,
                      group["cells"], note)
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


def from_unpatched(rows: Iterable[dict]) -> list:
    """Raw records from ``O4_Unpatched_Airports.read(tile)`` rows
    (``{"icao", "stage", "error"}`` plus ``code`` / ``params`` when the
    worker named the cause) — the airports a built tile has no patch for."""
    out = []
    for row in rows or ():
        params = row.get("params") or {}
        out.append(dict(
            record(code_for_stage(row.get("stage"), row.get("code")),
                   "(%s) %s" % (row.get("stage") or "?",
                                row.get("error") or ""),
                   airport=row.get("icao") or "?", **params),
            stage=str(row.get("stage") or "?")))
        # RULINGS 2026-10-12d: the airport's pack could not be put back —
        # a second message for the same airport (``secondary``: it is not
        # another unpatched airport).
        restore = row.get("pack_restore")
        if restore:
            # the bare cause when the object stage recorded one, else its
            # whole sentence; exactly one full stop either way
            reason = str(row.get("pack_restore_reason") or restore)
            reason = reason.strip().rstrip(". ") + "."
            pack = row.get("pack_restore_pack") or params.get("pack")
            out.append(dict(
                record("pack_restore_unproven", str(restore),
                       airport=row.get("icao") or "?", reason=reason,
                       **({"pack": pack} if pack else {})),
                secondary=True))
    return out


def from_unmounted(rows: Iterable[dict]) -> list:
    """Raw WARNING records from ``O4_Unpatched_Airports.read_unmounted_packs``
    rows (``{"icao", "pack", "link", "target", "volume"}``, #668): an
    airport graded without its pack because the pack is a link to a drive
    that is not mounted.  Folded per pack."""
    return [record("airport_pack_unmounted",
                   "%s -> %s" % (row.get("link"), row.get("target")),
                   airport=row.get("icao") or "?",
                   pack=row.get("pack") or "", link=row.get("link") or "",
                   target=row.get("target") or "",
                   volume=row.get("volume") or "")
            for row in rows or () if isinstance(row, dict)]


def from_substitutions(rows: Iterable[dict]) -> list:
    """Raw NOTE records from the tile's base-elevation substitutions
    (``{"cell", "code", "path"}`` plus ``source`` / ``fallback`` labels):
    one per cell, folded per (source, fallback) pair."""
    return [record("elevation_substituted",
                   "%s: source %s read from %s (%s)" % (
                       row.get("cell"), row.get("keyword") or "?",
                       row.get("code"), row.get("path")),
                   cell=str(row.get("cell") or "?"),
                   source=row.get("source") or "",
                   fallback=row.get("fallback") or row.get("code") or "")
            for row in rows or () if isinstance(row, dict)]


def from_degraded(rows: Iterable[dict]) -> list:
    """Raw WARNING records from ``O4_Unpatched_Airports.read_degraded``
    rows (``{"code", "detail"}``, an optional ``airport``, the rest its
    words' parameters, #853): an output the tile was built with that is
    not what was asked.  A row whose code is not a DEGRADED one is the
    generic "report it" — a step never turns a failure into a warning."""
    out = []
    for row in rows or ():
        if not isinstance(row, dict):
            continue
        code = str(row.get("code") or "")
        params = {k: v for k, v in row.items()
                  if k not in ("code", "detail", "airport")}
        airport = str(row.get("airport") or "")
        if severity_of(code) != "degraded" or code not in CATALOGUE:
            params, airport = {}, ""
            code = "[%s]" % code          # record() makes it UNMAPPED
        out.append(record(code, str(row.get("detail") or ""),
                          airport=airport, **params))
    return out


def closing_lines(warnings: list, notes: Iterable[dict] = ()) -> list:
    """The tile's closing account of its warnings and notes, for the
    engine log: the last thing such a tile prints (master ruling, #564)."""
    lines = []
    for (label, entries) in (("WARNING: ", warnings), ("NOTE: ", notes)):
        for entry in entries:
            lines.append(label + entry["what"])
            lines.append("   " + entry["why"])
            lines.append("   " + entry["remedy"])
    return lines
