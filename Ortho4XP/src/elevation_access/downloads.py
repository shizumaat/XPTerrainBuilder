"""Whole-file downloads into the cache, for sources GDAL cannot range-read.

Zipped rasters and point-cloud tiles are downloaded whole, atomically,
with Stop honoured; a write the armed shared-repo guard would refuse is
asked about first.
"""

import os

import O4_UI_Utils as UI

from elevation_access.base import ProviderUnavailable, TransientFetchError
from elevation_access.discovery import discovery_status_is_transient
from elevation_access.gdal_support import gdal
from elevation_access.las_tiles import (
    LAS_PROGRESS_INTERVAL_S,
    _las_progress_line,
)

__all__ = [
    "_write_refused_by_armed_guard",
    "archive_raster_members",
    "download_whole",
    "download_zip_whole",
]


def archive_raster_members(root, extensions, depth=0):
    """Every member of the archive (or directory) at the GDAL path
    ``root`` whose name ends in one of ``extensions`` (the suffix
    argument: raster suffixes for the raster readers, ``.las`` for a
    zipped point cloud), as full GDAL paths; folders are walked two levels
    down (the Baden-Wuerttemberg and some Texas zips nest their tiles).
    The one member walk of the module's archive readers
    (``arcgis_feature_tiles``, ``tnm_cog``, ``las_tile_index``
    ``archive_member=las``)."""
    for member in gdal.ReadDir(root) or []:
        entry_path = root + "/" + member
        if member.lower().endswith(tuple(extensions)):
            yield entry_path
        elif depth < 2 and "." not in member:
            yield from archive_raster_members(entry_path, extensions,
                                              depth + 1)


def download_whole(definition, source, scratch_path, progress_label,
                   validate=None):
    """One remote file, WHOLE, into ``scratch_path``; re-GET whole once
    when the transfer dies or ``validate`` rejects the bytes.  ``True``,
    or ``False`` for a 404 (the listed object is not on the server).  A
    5xx/429, a JSON/HTML body inside a 200 and a transfer that died
    twice are TRANSIENT; any other status is ``unavailable``.

    THE module's one whole-file download, with one streaming / progress
    / byte-count / retry body for every caller: the CWCB lidar tiles
    (the server ignores ``Range``) and the zipped ERDAS IMAGINE products
    TNM lists for USGS 1/9 arc-second come through
    :func:`download_zip_whole`, which is this function plus a zip
    validator (#157); the STRIPPED OPR tiles come through
    :func:`_prefetch_whole_stripped_sources` (#158).  A second
    streaming downloader beside this one would be the defect, not the
    shortcut.

    ``validate(scratch_path)`` returns ``None`` when the bytes on disk
    are what was asked for, else a short problem string, which costs
    the caller its one retry exactly as a died transfer does.
    """
    import requests
    import time as _time

    code = definition.get("code")
    url = source["download_url"]
    last_problem = None
    for _attempt in range(2):
        if os.path.isfile(scratch_path):
            os.remove(scratch_path)
        try:
            response = requests.get(url, stream=True, timeout=(30, 120))
        except Exception as error:
            last_problem = error
            continue
        try:
            status = int(response.status_code)
            if status == 404:
                return False
            if discovery_status_is_transient(status):
                raise TransientFetchError(
                    "%s: tile %s answered HTTP %d"
                    % (code, source["source_id"], status))
            if status != 200:
                raise ProviderUnavailable(
                    "%s: tile %s answered HTTP %d"
                    % (code, source["source_id"], status))
            content_type = str((getattr(response, "headers", None)
                                or {}).get("Content-Type", "")).lower()
            if "json" in content_type or "html" in content_type:
                # An API error envelope inside a 200, never a tile.
                raise TransientFetchError(
                    "%s: tile %s answered a %s body, not a zip"
                    % (code, source["source_id"], content_type))
            try:
                total = int((getattr(response, "headers", None)
                             or {}).get("Content-Length") or 0)
            except (TypeError, ValueError):
                total = 0
            os.makedirs(os.path.dirname(scratch_path), exist_ok=True)
            started = _time.monotonic()
            last_line = started
            have = 0
            with open(scratch_path, "wb") as handle:
                for block in response.iter_content(1 << 20):
                    if UI.red_flag:
                        raise TransientFetchError(
                            "%s tile download stopped with the build"
                            % code)
                    if block:
                        handle.write(block)
                        have += len(block)
                    now = _time.monotonic()
                    if now - last_line >= LAS_PROGRESS_INTERVAL_S:
                        last_line = now
                        UI.vprint(1, _las_progress_line(
                            progress_label, have, total, have,
                            now - started))
            UI.vprint(1, _las_progress_line(
                progress_label, have, total or have, have,
                _time.monotonic() - started, done=True))
        except (TransientFetchError, ProviderUnavailable):
            raise
        except Exception as error:
            last_problem = error
            continue
        finally:
            response.close()
        if total and have != total:
            last_problem = "%d of %d bytes" % (have, total)
            continue
        problem = validate(scratch_path) if validate is not None else None
        if problem is not None:
            last_problem = problem
            continue
        return True
    raise TransientFetchError(
        "%s: tile %s download died twice: %s"
        % (code, source["source_id"], last_problem))


def download_zip_whole(definition, source, scratch_path, member,
                       progress_label):
    """One zip archive, WHOLE, into ``scratch_path``; re-GET whole once
    when the transfer dies, the bytes are not a zip, or the zip does not
    hold ``member`` (``member=None``: any well-formed zip).  Otherwise
    exactly :func:`download_whole` -- the zip validator is the whole
    difference (#157/#158: ONE whole-file downloader, not two).
    """
    import zipfile

    def _holds_the_wanted_member(path):
        try:
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
        except zipfile.BadZipFile as error:
            return str(error)
        if member is not None and member not in names:
            return "no member %s in %s" % (member, names[:4])
        return None

    return download_whole(definition, source, scratch_path, progress_label,
                          validate=_holds_the_wanted_member)


def _write_refused_by_armed_guard(path):
    """Would an ARMED shared-repo write guard in this process refuse a
    write to ``path``?  The engine cannot import the harness, so it asks
    whichever loaded module exposes ``active_guard_refuses`` (the harness
    ``shared_repo_guard``); with none loaded the answer is ``False``."""
    import sys
    import types

    for module in list(sys.modules.values()):
        if not isinstance(module, types.ModuleType):
            continue                 # a mock parked in sys.modules
        namespace = getattr(module, "__dict__", {})
        ask = namespace.get("active_guard_refuses")
        if not callable(ask) or not isinstance(
                namespace.get("_ACTIVE_GUARDS"), list):
            continue
        try:
            if ask(path) is True:
                return True
        except Exception:
            return True
    return False
