"""One imagery source list for every front end (#1345, owner ruling
2026-10-25T22:11Z).

The Build box, the map's preview picker and the Qt window all read
:func:`imagery_sources`: one row per source, combined sources first, then
the single providers grouped by region.  Each row says whether the live
map can preview the source and, when it cannot, why.  A previewable
source carries a ``preview`` template made by the engine's OWN request
builders (``IMG.wmts_request`` / ``IMG.wms_request``) with the tile
fields left as placeholders, so a front end never builds a provider URL
of its own:

    {zoom} {x} {y} {-y} {quadkey} {switch:a,b}   XYZ tile fields
    {tilematrix}   the WMTS matrix id for the zoom (``tilematrix[z]``)
    {bbox}         the tile's EPSG:3857 box "minx,miny,maxx,maxy"
    {bbox_yx}      the same box "miny,minx,maxy,maxx" (WMS 1.3 order)

:func:`check_status` is the launch-time liveness check: one sample
request per source at a point it covers, at most :data:`STATUS_WORKERS`
at a time, each bounded by :data:`STATUS_TIMEOUT_S`; every answer streams
back as an ``ImagerySourceStatus`` event.  A source never checked, or
checked without a clear answer, is ``unknown`` and stays enabled.

Core module: no GUI-toolkit imports, no network at import.
"""

from __future__ import annotations

import math
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional

import O4_Geo_Utils as GEO
import O4_Imagery_Utils as IMG

__all__ = [
    "STATUS_TIMEOUT_S", "STATUS_WORKERS", "check_status", "covers_tile", "expand_preview",
    "imagery_sources", "is_previewable", "preview_max_zl", "preview_tile_url",
    "probe",
    "sample_request", "tile_source",
]

#: Internal layers no picker offers (the sea overlay's low-resolution layer).
HIDDEN = frozenset({"SEA"})
#: Sources the map may preview but a build may not download: the
#: OpenStreetMap tile usage policy forbids bulk downloading.
MAP_ONLY = frozenset({"OSM"})

STATUS_TIMEOUT_S = 5.0
STATUS_WORKERS = 4
#: The zoom level of a liveness sample (capped by the source's max_zl).
SAMPLE_ZL = 15
#: Where a source with no extent and no ``sample_point`` is sampled.
_DEFAULT_SAMPLE = (40.7128, -74.0060)

_WM_ORIGIN = 20037508.342789244
_PLACEHOLDER_X = 918273645
_PLACEHOLDER_Y = 546372819
_PLACEHOLDER_BOX = (101.5, 404.5, 303.5, 202.5)     # minx, maxy, maxx, miny
_XYZ_FIELDS = ("{zoom}", "{x}", "{y}", "{-y}", "{quadkey}", "{switch:")


# ---------------------------------------------------------------------------
# The list
# ---------------------------------------------------------------------------
def _max_zl(provider) -> Optional[int]:
    try:
        return int(provider["max_zl"])
    except (KeyError, TypeError, ValueError):
        return None


def _wm_resolution(z: int) -> float:
    return 2 * _WM_ORIGIN / (256 * 2 ** z)


def _tilematrix_by_zoom(provider) -> List[Optional[int]]:
    """For each web-mercator zoom 0..20, the index of the provider's tile
    matrix with the same grid (origin, tile size, resolution), or None."""
    if str(provider.get("epsg_code")) != "3857" or provider.get("tile_size") != 256:
        return []
    resolutions = provider.get("resolutions")
    corners = provider.get("top_left_corner")
    if resolutions is None or corners is None:
        return []
    found: List[Optional[int]] = []
    for z in range(21):
        target = _wm_resolution(z)
        match = None
        for index, resolution in enumerate(resolutions):
            if index >= len(corners):
                break
            x0, y0 = (float(v) for v in corners[index][:2])
            if (abs(float(resolution) / target - 1) < 1e-3
                    and abs(x0 + _WM_ORIGIN) < 1 and abs(y0 - _WM_ORIGIN) < 1):
                match = index
                break
        found.append(match)
    return found


def _custom_request(provider) -> bool:
    return IMG.has_URL and provider.get("code") in IMG.URL.custom_url_list


def _referer(headers) -> str:
    if isinstance(headers, dict):
        return str(headers.get("Referer") or "")
    return ""


def preview_spec(provider) -> tuple[Optional[Dict[str, Any]], str]:
    """``(preview, reason)``: the map-preview template of one provider, or
    None and the user's sentence saying why the map cannot show it."""
    if _custom_request(provider):
        return None, "This source builds its addresses in custom code the map can't follow."
    if "{api_key}" in str(provider.get("url_template", "")):
        return None, "This source needs an API key, which the map preview doesn't send."
    kind = provider.get("request_type")
    if kind == "local_tms":
        return None, "This source reads tiles from this computer, not from a map service."
    if str(provider.get("epsg_code", "3857")) != "3857" and provider.get("grid_type") != "webmercator":
        return None, ("This source uses map projection EPSG:%s, which the map "
                      "can't preview." % provider.get("epsg_code"))
    max_zl = _max_zl(provider)
    tilematrix = None
    if kind == "wms":
        url, headers = IMG.wms_request(_PLACEHOLDER_BOX, 256, 256, provider)
        minx, maxy, maxx, miny = (str(v) for v in _PLACEHOLDER_BOX)
        url = (url.replace(",".join((minx, miny, maxx, maxy)), "{bbox}")
                  .replace(",".join((miny, minx, maxy, maxx)), "{bbox_yx}"))
    elif kind == "wmts":
        tilematrix = _tilematrix_by_zoom(provider)
        some = next((t for t in tilematrix if t is not None), None)
        if some is None:
            return None, "This source's tile grid doesn't line up with the map's."
        url, headers = IMG.wmts_request(some, _PLACEHOLDER_X, _PLACEHOLDER_Y, provider)
        ident = provider["tilematrixset"]["tilematrices"][some]["identifier"]
        url = (url.replace("TILEMATRIX=" + ident + "&", "TILEMATRIX={tilematrix}&")
                  .replace(str(_PLACEHOLDER_X), "{x}").replace(str(_PLACEHOLDER_Y), "{y}"))
        tilematrix = [
            None if t is None else provider["tilematrixset"]["tilematrices"][t]["identifier"]
            for t in tilematrix]
        zooms = [z for z, t in enumerate(tilematrix) if t is not None]
        max_zl = min(max_zl, zooms[-1]) if max_zl is not None else zooms[-1]
    elif kind == "tms":
        if provider.get("grid_type") != "webmercator":
            grid = _tilematrix_by_zoom(provider)
            if not grid or any(t != z for z, t in enumerate(grid) if t is not None) \
                    or all(t is None for t in grid):
                return None, "This source's tile grid doesn't line up with the map's."
        url = str(provider.get("url_template") or "")
        headers = provider.get("fake_headers")
        if any(f in url for f in ("{xcenter}", "{ycenter}", "{size}", "{|y|}")):
            return None, "This source's addresses use a form the map can't preview."
        if not any(f in url for f in _XYZ_FIELDS):
            return None, "This source has no tile address the map can follow."
    else:
        return None, "This source's request type can't be previewed."
    preview = {"template": url, "referer": _referer(headers), "max_zl": max_zl}
    if tilematrix is not None:
        preview["tilematrix"] = tilematrix
    return preview, ""


def _extent_bbox(extent_code) -> Optional[List[float]]:
    """``[min_lon, min_lat, max_lon, max_lat]`` of an extent, or None
    (global, negated or unknown)."""
    if not extent_code or extent_code in ("global", "default") or extent_code.startswith("!"):
        return None
    bounds = IMG.extents_dict.get(extent_code, {}).get("mask_bounds")
    if isinstance(bounds, list) and len(bounds) == 4:
        return [float(v) for v in bounds]
    return None


def _coverage(provider, extent_code=None) -> Optional[List[float]]:
    """``[min_lon, min_lat, max_lon, max_lat]`` a source covers: its
    ``coverage_bounds``, else its extent's box; None = everywhere."""
    raw = provider.get("coverage_bounds")
    if raw:
        try:
            box = [float(v) for v in str(raw).split(",")]
            if len(box) == 4:
                return box
        except ValueError:
            pass
    return _extent_bbox(extent_code or provider.get("extent"))


def covers_tile(coverage: Optional[List[float]], lat: int, lon: int) -> bool:
    """Does a coverage box reach into the 1 degree tile at (lat, lon)?"""
    if coverage is None:
        return True
    min_lon, min_lat, max_lon, max_lat = coverage
    return lon < max_lon and lon + 1 > min_lon and lat < max_lat and lat + 1 > min_lat


def _member(layer_code, extent_code) -> Dict[str, Any]:
    provider = IMG.providers_dict[layer_code]
    preview, _reason = preview_spec(provider)
    return {"code": layer_code, "extent": extent_code,
            "bbox": _extent_bbox(extent_code), "preview": preview}


def _region_label(directory: str) -> str:
    return directory.replace("_", " ")


def _single_row(code) -> Dict[str, Any]:
    provider = IMG.providers_dict[code]
    preview, reason = preview_spec(provider)
    return {
        "code": code,
        "region": _region_label(str(provider.get("directory", ""))),
        "name": str(provider.get("name") or code),
        "combined": False,
        "members": [],
        "max_zl": _max_zl(provider),
        "coverage": _coverage(provider),
        "buildable": code not in MAP_ONLY,
        "previewable": preview is not None,
        "reason": reason,
        "preview": preview,
        "attribution": str(provider.get("attribution") or ""),
    }


def _combined_row(code) -> Dict[str, Any]:
    members = [_member(layer["layer_code"], layer["extent_code"])
               for layer in IMG.combined_providers_dict[code]]
    previewable = any(m["preview"] is not None for m in members)
    zls = [_max_zl(IMG.providers_dict[m["code"]]) for m in members]
    boxes = [_coverage(IMG.providers_dict[m["code"]], m["extent"]) for m in members]
    return {
        "code": code,
        "region": "",
        "name": code,
        "combined": True,
        "members": members,
        "max_zl": None if any(z is None for z in zls) else max(zls),
        "coverage": None if any(b is None for b in boxes) else [
            min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)],
        "buildable": True,
        "previewable": previewable,
        "reason": "" if previewable else "None of this source's layers can be previewed.",
        "preview": None,
        "attribution": "",
    }


def _offered(code) -> bool:
    provider = IMG.providers_dict[code]
    return bool(provider.get("in_GUI", True)) and code not in HIDDEN


def imagery_sources(tile=None) -> List[Dict[str, Any]]:
    """Every imagery source a front end offers, in menu order: combined
    sources first, then single providers by region (``Global`` first)
    and code.  With ``tile`` (``[lat, lon]``), only the sources whose
    ``coverage`` reaches into that tile."""
    combined = [_combined_row(code)
                for code in sorted(IMG.combined_providers_dict, key=str.lower)]
    singles = [_single_row(code) for code in IMG.providers_dict if _offered(code)]
    singles.sort(key=lambda row: (row["region"] != "Global", row["region"].lower(),
                                  row["code"].lower()))
    rows = combined + singles
    if tile is not None:
        lat, lon = (int(v) for v in tile)
        rows = [row for row in rows if covers_tile(row["coverage"], lat, lon)]
    return rows


# ---------------------------------------------------------------------------
# Preview URLs
# ---------------------------------------------------------------------------
def _quadkey(x: int, y: int, z: int) -> str:
    return GEO.gtile_to_quadkey(x, y, z)


def expand_preview(preview: Dict[str, Any], z: int, x: int, y: int) -> Optional[str]:
    """The URL of web-mercator tile ``z/x/y`` from a preview template, or
    None where the source has no tile at that zoom.  The front ends'
    expanders (``ImageryModel.swift``) follow THIS function; the parity
    test pins them to the same fixtures."""
    tilematrix = preview.get("tilematrix")
    url = str(preview["template"])
    if "{tilematrix}" in url:
        if tilematrix is None or z >= len(tilematrix) or tilematrix[z] is None:
            return None
        url = url.replace("{tilematrix}", str(tilematrix[z]))
    size = 2 * _WM_ORIGIN / 2 ** z
    minx, maxy = -_WM_ORIGIN + x * size, _WM_ORIGIN - y * size
    maxx, miny = minx + size, maxy - size
    box = ["%.2f" % v for v in (minx, miny, maxx, maxy)]
    url = (url.replace("{bbox}", ",".join(box))
              .replace("{bbox_yx}", ",".join((box[1], box[0], box[3], box[2])))
              .replace("{zoom}", str(z)).replace("{x}", str(x)).replace("{y}", str(y))
              .replace("{-y}", str(2 ** z - 1 - y)))
    if "{quadkey}" in url:
        url = url.replace("{quadkey}", _quadkey(x, y, z))
    if "{switch:" in url:
        head, rest = url.split("{switch:", 1)
        options, tail = rest.split("}", 1)
        choices = [c.strip() for c in options.split(",") if c.strip()]
        url = head + (choices[abs(x + y) % len(choices)] if choices else "") + tail
    return url


_ROW_CACHE: Dict[str, Any] = {"key": None, "rows": {}}


def _row(code) -> Optional[Dict[str, Any]]:
    """One source's row (combined or single, offered or not), cached
    until the registries change: the map asks once per tile."""
    key = (id(IMG.providers_dict), len(IMG.providers_dict),
           id(IMG.combined_providers_dict), len(IMG.combined_providers_dict))
    if _ROW_CACHE["key"] != key:
        _ROW_CACHE.update(key=key, rows={})
    rows = _ROW_CACHE["rows"]
    if code not in rows:
        if code in IMG.combined_providers_dict:
            rows[code] = _combined_row(code)
        elif code in IMG.providers_dict:
            rows[code] = _single_row(code)
        else:
            rows[code] = None
    return rows[code]


def is_previewable(code: str) -> bool:
    row = _row(code)
    return bool(row and row["previewable"])


def preview_max_zl(code: str) -> Optional[int]:
    """The deepest zoom the map may ask of a source (None: no ceiling);
    a combined source's is its deepest previewable layer's."""
    row = _row(code)
    if row is None:
        return None
    previews = ([row["preview"]] if not row["combined"]
                else [m["preview"] for m in row["members"]])
    zls = [p.get("max_zl") for p in previews if p is not None]
    if not zls or any(z is None for z in zls):
        return None
    return max(zls)


def tile_source(code: str, z: int, x: int, y: int) -> Optional[Dict[str, Any]]:
    """The layer that paints map tile ``z/x/y`` of a source: the single
    source itself or, for a combined one, the first layer (top first)
    whose extent holds the tile's centre and that the map can preview —
    ``{"code", "url", "referer"}``, or None.  ``ImageryModel.swift``
    resolves combined sources the same way."""
    row = _row(code)
    if row is None or not row["previewable"]:
        return None
    if not row["combined"]:
        layers = [(code, row["preview"])]
    else:
        lat, lon = GEO.gtile_to_wgs84(x + 0.5, y + 0.5, z)
        layers = [(m["code"], m["preview"]) for m in row["members"]
                  if m["preview"] is not None
                  and (m["bbox"] is None or (m["bbox"][0] <= lon <= m["bbox"][2]
                                             and m["bbox"][1] <= lat <= m["bbox"][3]))]
    for layer, preview in layers:
        if preview.get("max_zl") is not None and z > preview["max_zl"]:
            return None
        url = expand_preview(preview, z, x, y)
        if url is None:
            return None
        return {"code": layer, "url": url, "referer": preview["referer"]}
    return None


def preview_tile_url(code: str, z: int, x: int, y: int) -> Dict[str, Any]:
    """The ``preview_tile_url`` command: the URL and Referer of one map
    tile of a single source, or ``url`` None and the reason."""
    row = _row(code)
    if row is None:
        raise ValueError("preview_tile_url: %r is not a known imagery source." % (code,))
    if row["combined"]:
        raise ValueError("preview_tile_url: %r is combined; ask for one of its layers." % (code,))
    preview = row["preview"]
    if preview is None:
        return {"url": None, "referer": "", "reason": row["reason"]}
    return {"url": expand_preview(preview, int(z), int(x), int(y)),
            "referer": preview["referer"], "reason": ""}


# ---------------------------------------------------------------------------
# Liveness
# ---------------------------------------------------------------------------
def _sample_point(provider, extent_code=None) -> tuple[float, float]:
    """``(lat, lon)`` the source covers: its ``sample_point``, else the
    centre of its extent, else :data:`_DEFAULT_SAMPLE`."""
    raw = provider.get("sample_point")
    if raw:
        try:
            lat, lon = (float(v) for v in str(raw).split(","))
            return lat, lon
        except ValueError:
            pass
    bbox = _extent_bbox(extent_code or provider.get("extent"))
    if bbox:
        return (bbox[1] + bbox[3]) / 2, (bbox[0] + bbox[2]) / 2
    return _DEFAULT_SAMPLE


def sample_request(provider, lat: float, lon: float):
    """``(url, headers)`` of one ~256-pixel sample of ``provider`` around
    ``(lat, lon)``, through the build's own request builders, or None."""
    kind = provider.get("request_type")
    epsg = str(provider.get("epsg_code", "3857"))
    x, y = GEO.transformer("4326", epsg).transform(lon, lat)
    if kind == "wms":
        half = 128 * (2e-5 if epsg == "4326" else 2.0)
        return IMG.wms_request((x - half, y + half, x + half, y - half), 256, 256, provider)
    if kind not in ("tms", "wmts"):
        return None
    resolutions = provider["resolutions"]
    target = 2e-5 if epsg == "4326" else _wm_resolution(min(SAMPLE_ZL, _max_zl(provider) or SAMPLE_ZL))
    tm = min(range(len(resolutions)),
             key=lambda i: abs(math.log(float(resolutions[i]) / target)))
    x0, y0 = (float(v) for v in provider["top_left_corner"][tm][:2])
    cell = float(resolutions[tm]) * provider["tile_size"]
    return IMG.wmts_request(tm, int((x - x0) // cell), int((y0 - y) // cell), provider)


def _http_get(url, headers, timeout):
    """The HTTP layer of a liveness probe (tests replace it)."""
    import requests
    return requests.get(url, headers=headers or None, timeout=timeout)


def probe(url: str, headers, timeout: float = STATUS_TIMEOUT_S) -> tuple[str, str]:
    """``(status, reason)`` of one sample request: ``online``, ``offline``
    (no answer, a refusal or a page instead of imagery) or ``unknown``."""
    import requests
    try:
        answer = _http_get(url, headers, timeout)
    except requests.Timeout:
        return "offline", "No answer within %g seconds." % timeout
    except requests.RequestException as error:
        return "offline", "Could not connect (%s)." % type(error).__name__
    code = getattr(answer, "status_code", 0)
    if code >= 400:
        return "offline", "The service answered HTTP %d." % code
    kind = str(answer.headers.get("Content-Type", "")).lower()
    if code == 200 and kind.startswith("image/"):
        return "online", ""
    if code == 200 and ("html" in kind or "xml" in kind or "json" in kind):
        return "offline", "The service answered with a page, not imagery."
    return "unknown", ""


def _check_one(code, extent_code=None) -> tuple[str, str]:
    provider = IMG.providers_dict[code]
    if provider.get("session_name"):
        import O4_Authenticated_Sessions as SESSIONS
        try:
            SESSIONS.ensure_api_key(provider)
        except Exception:
            return "unknown", ""          # no key yet: a build will ask for one
    try:
        request = sample_request(provider, *_sample_point(provider, extent_code))
    except Exception:
        return "unknown", ""
    if request is None:
        return "unknown", ""
    url, headers = request
    return probe(url, headers)


def check_status(emit: Callable[[str, str, str], None],
                 codes: Optional[List[str]] = None) -> Dict[str, Any]:
    """The ``imagery_source_status`` command: start the liveness check of
    ``codes`` (default: every listed source) on a worker thread and reply
    at once; ``emit(code, status, reason)`` is called once per source.
    A combined source is offline only when every one of its layers is."""
    rows = imagery_sources()
    wanted = set(codes) if codes else {row["code"] for row in rows}
    combined = {row["code"]: row for row in rows if row["combined"] and row["code"] in wanted}
    singles: Dict[str, Optional[str]] = {
        row["code"]: None for row in rows if not row["combined"] and row["code"] in wanted}
    for row in combined.values():
        for member in row["members"]:
            singles.setdefault(member["code"], member["extent"])

    def run():
        results: Dict[str, tuple[str, str]] = {}

        def one(code):
            try:
                results[code] = _check_one(code, singles[code])
            except Exception:
                results[code] = ("unknown", "")
            if code in wanted and code not in combined:
                emit(code, *results[code])

        with ThreadPoolExecutor(max_workers=STATUS_WORKERS) as pool:
            list(pool.map(one, sorted(singles)))
        for code, row in sorted(combined.items()):
            states = [results.get(m["code"], ("unknown", ""))[0] for m in row["members"]]
            if states and all(s == "offline" for s in states):
                emit(code, "offline", "None of this source's layers answered.")
            elif any(s == "online" for s in states):
                emit(code, "online", "")
            else:
                emit(code, "unknown", "")

    threading.Thread(target=run, daemon=True, name="o4-imagery-status").start()
    return {"started": True, "count": len(wanted)}
