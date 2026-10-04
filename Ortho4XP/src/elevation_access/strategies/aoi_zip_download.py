"""The ``aoi_zip_download`` access strategy (:class:`AoiZipDownloadStrategy`).

An AOI download portal: POST the polygon, GET one zip of tiles.

Everything used by this strategy alone lives in this file; what it
shares with other strategies is imported from ``elevation_access``.
"""

import datetime
import json
import math
import os
import threading

import O4_UI_Utils as UI

from elevation_access.base import ProviderUnavailable, TransientFetchError
from elevation_access.definitions import (
    _coverage_bbox_intersects,
    _parse_float,
)
from elevation_access.discovery import (
    _DISCOVERY_ERROR_KEYS,
    discovery_json_payload,
    discovery_status_is_transient,
    raise_transient_discovery_failure,
)
from elevation_access.failures import cap_exceeded_unavailable
from elevation_access.gdal_support import gdal, has_gdal
from elevation_access.las_tiles import (
    LAS_FOOTPRINT_KEY,
    LAS_PROGRESS_INTERVAL_S,
    _las_airport_label,
    _las_progress_line,
    _las_size_text,
    las_core_geometry,
)
from elevation_access.registry import register_access_strategy
from elevation_access.vertical_units import _raster_vertical_unit
from elevation_access.warp import (
    _geotiff_has_valid_data,
    _source_contribution_entry,
    inset_valid_fraction,
    warp_vsicurl_sources_to_geotiff,
)

__all__ = [
    "AOI_ZIP_BROWSER_USER_AGENT",
    "AOI_ZIP_CLASSIC_ARCHIVE_LIMIT_BYTES",
    "AOI_ZIP_DEFAULT_MAX_BYTES_PER_AIRPORT",
    "AOI_ZIP_GEOJSON_DECIMALS",
    "AOI_ZIP_LOGIN_URL_MARKERS",
    "AOI_ZIP_USER_AGENT_PROFILES",
    "AoiZipDownloadStrategy",
    "aoi_request_geometry",
]


# =====================================================================
# Strategy: aoi_zip_download (an AOI download portal -- WA DNR, Alaska)
# =====================================================================
#: The default per-airport byte cap (spec us-holder-providers §3.6): the
#: portal's own byte answer for the request polygon is judged against it
#: BEFORE the download starts.
AOI_ZIP_DEFAULT_MAX_BYTES_PER_AIRPORT = 300000000


#: The largest archive a classic (non-Zip64) zip can describe.  Beyond it
#: the portal streams a Zip64 (PAWG Wrangell: 9.2 GB) -- refused as
#: ``unavailable`` whatever the cap says (spec §3.6 / §5).
AOI_ZIP_CLASSIC_ARCHIVE_LIMIT_BYTES = 0xFFFFFFFF


#: The portal's browser client prunes every AOI coordinate to this many
#: decimals before it queries or downloads (``toFixed(4)`` in the
#: portal's ``lidar.js``); the strategy sends the same text.
AOI_ZIP_GEOJSON_DECIMALS = 4


#: ``user_agent_profile=browser`` (owner RULINGS 2026-09-30bn: the WA DNR
#: gate is honoured EXACTLY as a browser meets it).  ``engine`` sends the
#: HTTP library's own agent.
AOI_ZIP_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15"
    " (KHTML, like Gecko) Version/17.0 Safari/605.1.15")


AOI_ZIP_USER_AGENT_PROFILES = ("browser", "engine")


#: A gate page that lands on a URL carrying one of these is a LOGIN, and
#: a login is never worked around (RULINGS 2026-09-30bn): ``unavailable``.
AOI_ZIP_LOGIN_URL_MARKERS = ("login", "signin", "sign-in", "sso", "oauth")


#: ``gate URL -> (cookies, expires_epoch_or_None)``: the gate is asked
#: ONCE per process and its cookies replayed until their own Max-Age runs
#: out (``None`` = a session cookie, kept for the process).
_aoi_gate_cookie_cache = {}


_aoi_gate_cookie_lock = threading.Lock()


def _aoi_round_coordinates(value, decimals=AOI_ZIP_GEOJSON_DECIMALS):
    if isinstance(value, (list, tuple)):
        return [_aoi_round_coordinates(item, decimals) for item in value]
    return round(float(value), decimals)


def aoi_request_geometry(definition, bounding_box_wgs84):
    """``(geometry, geojson_text, is_core)``: what the portal is asked for.

    The SURGICAL core (:func:`las_core_geometry` -- the aerodrome boundary
    the ladder hands every rung, buffered by ``footprint_buffer_m``) when
    the definition carries one; otherwise the whole request box.  The
    GeoJSON text is the browser's: coordinates pruned to
    :data:`AOI_ZIP_GEOJSON_DECIMALS`, a box rounded OUTWARD so the pruning
    never shrinks it."""
    from shapely.geometry import box as _box
    from shapely.geometry import mapping

    core = las_core_geometry(definition)
    if core is not None:
        geometry = core
        if geometry.geom_type == "MultiPolygon":
            geometry = geometry.convex_hull
        mapped = mapping(geometry)
        payload = {"type": mapped["type"],
                   "coordinates": _aoi_round_coordinates(
                       mapped["coordinates"])}
    else:
        scale = 10 ** AOI_ZIP_GEOJSON_DECIMALS
        (west, south, east, north) = bounding_box_wgs84
        (west, south) = (math.floor(west * scale) / scale,
                         math.floor(south * scale) / scale)
        (east, north) = (math.ceil(east * scale) / scale,
                         math.ceil(north * scale) / scale)
        geometry = _box(west, south, east, north)
        payload = {"type": "Polygon", "coordinates": [[
            [west, south], [east, south], [east, north], [west, north],
            [west, south]]]}
    text = json.dumps(payload, separators=(",", ":"))
    return (geometry, text, core is not None)


def _aoi_dataset_ids(definition):
    ids = []
    for token in str(definition.get("dataset_ids", "")).replace(
            ";", ",").split(","):
        token = token.strip()
        if token:
            ids.append(str(int(float(token))))
    if not ids:
        raise ProviderUnavailable(
            "%s: aoi_zip_download needs dataset_ids in %s.elv"
            % (definition.get("code"), definition.get("code")))
    return ids


def _aoi_user_agent_headers(definition):
    profile = str(definition.get("user_agent_profile", "engine")).strip()
    if profile not in AOI_ZIP_USER_AGENT_PROFILES:
        raise ProviderUnavailable(
            "%s: .elv user_agent_profile=%s is not one of %s"
            % (definition.get("code"), profile,
               "|".join(AOI_ZIP_USER_AGENT_PROFILES)))
    if profile == "browser":
        return {"User-Agent": AOI_ZIP_BROWSER_USER_AGENT}
    return {}


def _aoi_gate_url(definition):
    gate = str(definition.get("gate_cookie_from", "") or "").strip()
    if not gate:
        return None
    from urllib.parse import urljoin

    return urljoin(str(definition.get("query_url")), gate)


def _aoi_gate_unavailable(definition, why):
    """THE GATE CLASS (RULINGS 2026-09-30bn): a gate that does not open the
    way a browser opens it -- a refusal, a login, no cookie -- is
    ``unavailable`` with the reason ``gate``; never retried this run,
    never worked around, never a no-coverage."""
    return ProviderUnavailable(
        "%s: gate - %s; recorded unavailable, not no-coverage (the portal's"
        " gate is honoured as a browser meets it and never worked around,"
        " owner RULINGS 2026-09-30bn)" % (definition.get("code"), why))


def _aoi_forget_gate(definition):
    gate_url = _aoi_gate_url(definition)
    if gate_url:
        with _aoi_gate_cookie_lock:
            _aoi_gate_cookie_cache.pop(gate_url, None)


def _aoi_open_gate(definition, session, headers):
    """Replay the gate's cookies on ``session`` -- asking the gate page
    ONCE per process and again only after the cookies' own Max-Age.
    Returns the gate record for the provenance (``None`` without a gate)."""
    import time as _time

    gate_url = _aoi_gate_url(definition)
    if gate_url is None:
        return None
    with _aoi_gate_cookie_lock:
        cached = _aoi_gate_cookie_cache.get(gate_url)
        now = _time.time()
        reused = cached is not None and (
            cached[1] is None or cached[1] > now)
        if not reused:
            try:
                response = session.get(gate_url, headers=headers,
                                       timeout=60, allow_redirects=True)
            except Exception as error:
                raise TransientFetchError(
                    "%s: gate page %s failed: %s"
                    % (definition.get("code"), gate_url, error)) from error
            status = int(getattr(response, "status_code", 0) or 0)
            if discovery_status_is_transient(status):
                raise TransientFetchError(
                    "%s: gate page %s answered HTTP %d"
                    % (definition.get("code"), gate_url, status))
            final_url = str(getattr(response, "url", gate_url) or gate_url)
            if status in (401, 407) or any(
                    marker in final_url.lower()
                    for marker in AOI_ZIP_LOGIN_URL_MARKERS):
                raise _aoi_gate_unavailable(
                    definition, "the gate page asks for a login (%s, HTTP "
                    "%d)" % (final_url, status))
            if status != 200:
                raise _aoi_gate_unavailable(
                    definition, "the gate page %s answered HTTP %d"
                    % (gate_url, status))
            jar = getattr(response, "cookies", None)
            cookies = []
            expiries = []
            for cookie in (jar or ()):
                cookies.append((cookie.name, cookie.value, cookie.domain,
                                cookie.path))
                if getattr(cookie, "expires", None):
                    expiries.append(float(cookie.expires))
            if not cookies:
                raise _aoi_gate_unavailable(
                    definition, "the gate page %s set no cookie" % gate_url)
            cached = (cookies, min(expiries) if expiries else None)
            _aoi_gate_cookie_cache[gate_url] = cached
    (cookies, expires) = cached
    for (name, value, domain, path) in cookies:
        session.cookies.set(name, value, domain=domain, path=path)
    return {
        "gate_cookie_from": definition.get("gate_cookie_from"),
        "gate_url": gate_url,
        "cookie_names": sorted({name for (name, _v, _d, _p) in cookies}),
        "cookie_expires_utc": (
            datetime.datetime.fromtimestamp(
                expires, datetime.timezone.utc).isoformat()
            if expires else None),
        "cookie_reused": bool(reused),
    }


def _aoi_portal_session(definition):
    import requests

    session = requests.Session()
    headers = _aoi_user_agent_headers(definition)
    session.headers.update(headers)
    return (session, headers)


@register_access_strategy("aoi_zip_download")
class AoiZipDownloadStrategy:
    """An AOI download portal: POST the polygon, GET one zip of tiles.

    The Washington DNR lidar portal and the Alaska DGGS elevation portal
    run the same software (spec us-holder-providers §3.6): ``POST
    query_url`` with the form field ``geojson=<Polygon>`` answers a JSON
    list ``[{dataset_id, project_name, dataset_name, files, bytes}]`` for
    the files the polygon touches, and ``GET download_url?geojson=&ids=``
    streams ``custom_download.zip`` of those files (no ranges, no
    Content-Length).  Discovery is the POST filtered to the definition's
    ``dataset_ids``; its ``bytes`` answer IS the cap check (before any
    byte moves).  The zip lands beside the destination, its members
    (``member_glob``) are read through ``/vsizip/``, mosaicked by a VRT
    and handed to the shared warp with the ``.elv``'s ``vertical_unit``;
    the zip is deleted (no refresh scope of its own -- RULED §3).

    THE GATE (owner RULINGS 2026-09-30bn).  ``gate_cookie_from`` names a
    page (WA: ``/``) whose cookies (WA: ``dlgate``) a browser receives
    before it may query; the strategy GETs it once per process with the
    ``user_agent_profile`` agent and replays the cookies until their own
    Max-Age.  A 401/403, a login page or a gate that sets no cookie is
    ``unavailable: ... gate`` -- never a retry loop, never a workaround.
    """

    supports_wide_area = False

    def _query(self, definition, bounding_box_wgs84, session, headers):
        """``(sources, gate_record, geojson_text, geometry, is_core)``;
        ``sources`` is ``None`` for a durable no-coverage."""
        code = definition.get("code")
        dataset_ids = _aoi_dataset_ids(definition)
        (geometry, text, is_core) = aoi_request_geometry(
            definition, bounding_box_wgs84)
        gate = _aoi_open_gate(definition, session, headers)
        description = "%s AOI query" % code
        try:
            response = session.post(
                str(definition.get("query_url")), data={"geojson": text},
                headers=headers, timeout=60)
        except Exception as error:
            raise_transient_discovery_failure(description + " request",
                                              error)
        status = int(getattr(response, "status_code", 200) or 200)
        if status in (401, 403, 407):
            _aoi_forget_gate(definition)
            raise _aoi_gate_unavailable(
                definition, "the query answered HTTP %d%s" % (
                    status, "" if gate else
                    " (no gate_cookie_from declared)"))
        payload = discovery_json_payload(response, description)
        if payload is None:
            return (None, gate, text, geometry, is_core)
        if isinstance(payload, dict):
            for key in _DISCOVERY_ERROR_KEYS:
                if payload.get(key):
                    raise_transient_discovery_failure(
                        description, "the listing reports %s: %s"
                        % (key, str(payload.get(key))[:200]))
        if not isinstance(payload, list):
            raise_transient_discovery_failure(
                description, "a listing that is not a list of datasets")
        sources = []
        for entry in payload:
            if not isinstance(entry, dict):
                raise_transient_discovery_failure(
                    description, "a listing entry that is not an object")
            try:
                dataset_id = str(int(entry.get("dataset_id")))
            except (TypeError, ValueError):
                raise_transient_discovery_failure(
                    description, "a listing entry with no dataset_id")
            if dataset_id not in dataset_ids:
                continue
            files = int(entry.get("files") or 0)
            if files <= 0:
                continue
            sources.append({
                "source_id": dataset_id,
                "title": "%s - %s" % (entry.get("project_name"),
                                      entry.get("dataset_name")),
                "files": files,
                "bytes": int(entry.get("bytes") or 0),
                "publication_date": definition.get("publication_date") or "",
            })
        return (sources or None, gate, text, geometry, is_core)

    def discover(self, definition, bounding_box_wgs84):
        if not _coverage_bbox_intersects(definition, bounding_box_wgs84):
            return None
        (session, headers) = _aoi_portal_session(definition)
        try:
            return self._query(definition, bounding_box_wgs84, session,
                               headers)[0]
        finally:
            session.close()

    def _check_caps(self, definition, sources, destination_path):
        """Refuse an over-cap download BEFORE any byte moves."""
        listed_bytes = sum(source["bytes"] for source in sources)
        listed_files = sum(source["files"] for source in sources)
        max_bytes = int(float(definition.get(
            "max_bytes_per_airport", AOI_ZIP_DEFAULT_MAX_BYTES_PER_AIRPORT)))
        max_files = int(float(definition.get("max_tiles_per_airport", 0)
                              or 0))
        needs = "%d files / %s" % (listed_files, _las_size_text(listed_bytes))
        if listed_bytes > AOI_ZIP_CLASSIC_ARCHIVE_LIMIT_BYTES:
            raise cap_exceeded_unavailable(
                definition, needs + " (a Zip64 archive)",
                _las_size_text(AOI_ZIP_CLASSIC_ARCHIVE_LIMIT_BYTES),
                "the classic-zip limit", destination_path)
        if max_bytes and listed_bytes > max_bytes:
            raise cap_exceeded_unavailable(
                definition, needs, _las_size_text(max_bytes),
                "max_bytes_per_airport", destination_path)
        if max_files and listed_files > max_files:
            raise cap_exceeded_unavailable(
                definition, needs, "%d files" % max_files,
                "max_tiles_per_airport", destination_path)
        return (listed_files, listed_bytes)

    def _download(self, definition, session, headers, url, part_path,
                  listed_bytes, label):
        """Stream the zip to ``part_path`` with the #136 heartbeat;
        returns the bytes moved.  30t classes: an exception or a 5xx/429
        is transient, a 401/403 the gate, any other refusal unavailable."""
        import time as _time

        code = definition.get("code")
        try:
            response = session.get(url, headers=headers, stream=True,
                                   timeout=(30, 120))
        except Exception as error:
            raise TransientFetchError(
                "%s: AOI download failed: %s" % (code, error)) from error
        try:
            status = int(response.status_code)
            if status in (401, 403, 407):
                _aoi_forget_gate(definition)
                raise _aoi_gate_unavailable(
                    definition, "the download answered HTTP %d" % status)
            if discovery_status_is_transient(status):
                raise TransientFetchError(
                    "%s: AOI download answered HTTP %d" % (code, status))
            if status != 200:
                raise ProviderUnavailable(
                    "%s: AOI download answered HTTP %d (listed %s)"
                    % (code, status, _las_size_text(listed_bytes)))
            os.makedirs(os.path.dirname(part_path) or ".", exist_ok=True)
            have = 0
            started = _time.monotonic()
            last_line = started
            with open(part_path, "wb") as handle:
                for block in response.iter_content(1 << 20):
                    if UI.red_flag:
                        raise TransientFetchError(
                            "%s AOI download stopped with the build" % code)
                    if block:
                        handle.write(block)
                        have += len(block)
                    now = _time.monotonic()
                    if now - last_line >= LAS_PROGRESS_INTERVAL_S:
                        last_line = now
                        UI.vprint(1, _las_progress_line(
                            label, have, listed_bytes, have, now - started))
            UI.vprint(1, _las_progress_line(
                label, have, have, have, _time.monotonic() - started,
                done=True))
            return have
        except (TransientFetchError, ProviderUnavailable):
            raise
        except Exception as error:
            raise TransientFetchError(
                "%s: AOI download died: %s" % (code, error)) from error
        finally:
            response.close()

    def fetch(
        self,
        definition,
        bounding_box_wgs84,
        target_resolution_m,
        destination_path,
    ):
        import fnmatch
        import zipfile
        from urllib.parse import quote

        code = definition.get("code")
        if not has_gdal:
            return None
        if not _coverage_bbox_intersects(definition, bounding_box_wgs84):
            return None
        (session, headers) = _aoi_portal_session(definition)
        zip_path = destination_path + ".aoi.zip"
        vrt_path = destination_path + ".aoi.vrt"
        scratch_paths = (zip_path, vrt_path)
        try:
            (sources, gate, text, geometry, is_core) = self._query(
                definition, bounding_box_wgs84, session, headers)
            if not sources:
                return None
            (listed_files, listed_bytes) = self._check_caps(
                definition, sources, destination_path)
            ids = [source["source_id"] for source in sources]
            download_base = str(definition.get("download_url"))
            url = "%s?geojson=%s&ids=%s" % (
                download_base, quote(text, safe=""), quote(",".join(ids)))
            airport = _las_airport_label(destination_path)
            UI.vprint(
                1,
                "    [inset] %s %s: downloading %d file(s), %s listed, from"
                " %s" % (airport, code, listed_files,
                         _las_size_text(listed_bytes), download_base),
            )
            fetched_bytes = self._download(
                definition, session, headers, url, zip_path, listed_bytes,
                "%s %s %s" % (airport, code, "datasets " + ",".join(ids)))
            if not zipfile.is_zipfile(zip_path):
                raise TransientFetchError(
                    "%s: the AOI download (%s) is not a complete zip "
                    "archive" % (code, _las_size_text(fetched_bytes)))
            pattern = str(definition.get("member_glob", "*.tif")).lower()
            with zipfile.ZipFile(zip_path) as archive:
                names = [name for name in archive.namelist()
                         if not name.endswith("/")]
            members = sorted(name for name in names
                             if fnmatch.fnmatch(name.lower(), pattern))
            if not members:
                raise ProviderUnavailable(
                    "%s: the AOI archive (%d members) holds none matching "
                    "member_glob=%s" % (code, len(names), pattern))
            member_paths = ["/vsizip/%s/%s" % (zip_path, name)
                            for name in members]
            source_nodata = _parse_float(definition.get("source_nodata"))
            vrt_options = {}
            if source_nodata is not None:
                vrt_options = {"srcNodata": source_nodata,
                               "VRTNodata": source_nodata}
            try:
                vrt = gdal.BuildVRT(vrt_path, member_paths, **vrt_options)
            except Exception:
                vrt = None
            if vrt is None:
                raise ProviderUnavailable(
                    "%s: GDAL could not mosaic the %d archive members"
                    % (code, len(members)))
            vrt = None
            source_srs = definition.get("source_srs")
            if source_srs and str(source_srs).strip().isdigit():
                source_srs = "EPSG:%s" % str(source_srs).strip()
            if not warp_vsicurl_sources_to_geotiff(
                [vrt_path],
                bounding_box_wgs84,
                target_resolution_m,
                destination_path,
                source_srs=source_srs or None,
                source_nodata=source_nodata,
                value_floor_m=float(definition.get("value_floor_m", -600.0)),
                vertical_unit=_raster_vertical_unit(definition),
                provider_code=code,
            ):
                return None
        finally:
            session.close()
            for path in scratch_paths:
                if os.path.isfile(path):
                    try:
                        os.remove(path)
                    except OSError:                      # pragma: no cover
                        pass
        if not _geotiff_has_valid_data(destination_path):
            try:
                os.remove(destination_path)
            except OSError:
                pass
            return None
        provenance = {
            "provider": code,
            "access_strategy": definition.get("access_strategy"),
            "source_urls": ["%s?ids=%s" % (download_base, ",".join(ids))],
            "source_ids": ids,
            "sources_used": [_source_contribution_entry(source)
                             for source in sources],
            "datasets": [
                {"dataset_id": source["source_id"], "title": source["title"],
                 "files": source["files"], "bytes": source["bytes"]}
                for source in sources],
            "archive_members": [os.path.basename(name) for name in members],
            "bytes_listed": listed_bytes,
            "bytes_fetched": fetched_bytes,
            "max_bytes_per_airport": int(float(definition.get(
                "max_bytes_per_airport",
                AOI_ZIP_DEFAULT_MAX_BYTES_PER_AIRPORT))),
            "request_geometry": "core" if is_core else "box",
            "request_geojson": json.loads(text),
            "user_agent_profile": str(
                definition.get("user_agent_profile", "engine")).strip(),
            "gate": gate,
            "publication_date": definition.get("publication_date"),
            "valid_fraction": round(
                inset_valid_fraction(destination_path), 6),
            "license": definition.get("license"),
            "license_note": definition.get("license_note"),
            "attribution": definition.get("attribution"),
            "vertical_datum": definition.get("vertical_datum"),
            "datum_note": (
                "Elevations are in the source vertical datum; lidar is "
                "treated as truth and is NOT shifted toward the base DEM."
            ),
            "fetch_date": datetime.date.today().isoformat(),
            "bounding_box_wgs84": list(bounding_box_wgs84),
            "native_resolution_m": definition.get("native_resolution_m"),
            "resolution_m": target_resolution_m,
        }
        if is_core:
            # THE SURGICAL CORE (spec las-tile §4): the portal was asked
            # for the buffered aerodrome boundary only, so the raster is
            # NoData beyond it; the ladder assembles the surround.
            provenance["core"] = {
                "provider": code,
                "bounding_box_wgs84": [round(v, 9) for v in geometry.bounds],
                "boundary_polygon_wgs84": definition.get(LAS_FOOTPRINT_KEY),
                "footprint_buffer_m": _parse_float(
                    definition.get("footprint_buffer_m"), default=0.0),
                "tile_names": [os.path.basename(name) for name in members],
                "feather_m": _parse_float(
                    definition.get("core_feather_m"), default=None),
            }
        return provenance
