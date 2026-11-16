"""The zoom level inside an airport's boundary (#2107).

Owner 2026-11-16T14:26Z: "use the highest zoom level available from the
provider just for the area inside the airport boundary."  The squares
that meet an airport's boundary (no ``cover_extent``, no approach
corridor: those keep ``cover_zl``, ``O4_Airport_Approach_Cover``) are
textured at the finest zoom level the tile can carry there:

* the CEILING is the tile's ``mesh_zl`` -- the texture grid the mesh is
  cut on (``O4_DSF_Utils.zone_list_to_ortho_dico`` gives every
  ``mesh_zl`` block ONE texture, so no texture can be finer) -- and the
  provider's ``max_zl`` when its ``.lay`` names one;
* the provider is ASKED, square by square, whether it has imagery at that
  level (:func:`_available_zl`: a few sample tiles; the server's "no
  imagery here" tile, ``O4_Imagery_Utils.is_placeholder_tile``, or a 404
  is no data); where it has none the square falls back a level, down to
  ``cover_zl`` (no change).  An answer that never comes (offline, a
  timeout) is not a "no": the square keeps the level and the
  downloader's own lower-zoom fill (``get_wmts_image``) covers a gap.
* a source that cannot be asked tile by tile (a combined source, a WMS
  grid) abstains: its squares keep ``cover_zl``.

The squares found are recorded on the tile (``airport_boundary_textures``,
their texture names) for the imagery record: on-demand imagery makes
them low-res last, with the favorites (``O4_Imagery_OnDemand_Cores``).
Nothing here knows which airport it reads.

* :func:`boundary_blocks` -- ``{mesh block: zoom}`` for the airports.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Iterable, Optional

import O4_Airport_Approach_Cover as COVER
import requests

__all__ = ["SAMPLE_OFFSETS", "PROBE_TIMEOUT_S", "PROBE_THREADS",
           "boundary_blocks"]

#: The tiles of a square asked (offsets in its 16 x 16 grid at the
#: ceiling): its centre and two diagonal quarters.
SAMPLE_OFFSETS = ((8, 8), (4, 4), (12, 12))
#: Seconds one sample request may take.
PROBE_TIMEOUT_S = 10.0
#: Squares asked at once.
PROBE_THREADS = 8

#: one process asks each (provider, zoom, x, y) once (the DSF writer and
#: the airport prefetch both read the assignment)
_ANSWERS: dict = {}


def _provider(code):
    """The ``.lay`` provider ``code`` names, or ``None`` (a combined source
    or an unknown code)."""
    import O4_Imagery_Utils as IMG
    if not IMG.providers_dict:
        try:
            IMG.initialize_providers_dict()
        except Exception:
            return None
    return IMG.providers_dict.get(code)


def _askable(provider) -> bool:
    """A source whose tiles can be asked one by one (a web-mercator TMS)."""
    return bool(provider) and provider.get("grid_type") == "webmercator" \
        and provider.get("request_type") in ("tms", "wmts")


def _ceiling_zl(tile, provider) -> Optional[int]:
    """The finest level ``tile``'s boundary squares may use: its
    ``mesh_zl``, capped by ``provider``'s ``max_zl``; ``None`` when that is
    no finer than ``cover_zl`` or the source cannot be asked."""
    if not _askable(provider):
        return None
    ceiling = int(getattr(tile, "mesh_zl", 0) or 0)
    if "max_zl" in provider:
        ceiling = min(ceiling, int(provider["max_zl"]))
    return ceiling if ceiling > int(getattr(tile, "cover_zl", 0) or 0) else None


def _probe_tile(provider, zl: int, til_x: int, til_y: int) -> Optional[bool]:
    """True when ``provider`` serves imagery for tile ``(til_x, til_y)`` at
    ``zl``, False for its "no imagery here" tile or a 404, ``None`` when
    no answer came."""
    key = (provider.get("code"), zl, til_x, til_y)
    if key in _ANSWERS:
        return _ANSWERS[key]
    import O4_Imagery_Utils as IMG
    answer = None
    try:
        request = IMG.wmts_request(zl, til_x, til_y, provider)
        if request is not None:
            url, headers = request
            r = requests.get(url, headers=headers or None,
                             timeout=PROBE_TIMEOUT_S)
            if r.status_code == 404 or IMG.is_placeholder_tile(url, r.headers):
                answer = False
            elif r.status_code == 200 and "image" in r.headers.get(
                    "Content-Type", ""):
                answer = True
    except Exception:
        answer = None
    _ANSWERS[key] = answer
    return answer


def _available_zl(provider, square, ceiling: int, floor: int,
                 probe: Callable = _probe_tile) -> int:
    """The finest level from ``ceiling`` down to above ``floor`` at which
    ``provider`` has imagery for the ``ceiling`` square whose top-left
    tile is ``square``; ``floor`` when it has none above it.  A level is
    missing when more answered samples say "no data" than "imagery"; no
    answer at all keeps it."""
    sx, sy = square
    for zl in range(ceiling, floor, -1):
        shift = ceiling - zl
        answers = [probe(provider, zl, (sx + dx) >> shift, (sy + dy) >> shift)
                   for dx, dy in SAMPLE_OFFSETS]
        no = sum(1 for a in answers if a is False)
        yes = sum(1 for a in answers if a is True)
        if no <= yes:
            return zl
    return floor


def boundary_blocks(tile, dico_airports: dict, airports: Iterable,
                    provider=None, probe: Optional[Callable] = None) -> dict:
    """``{(til_x, til_y): zoom}``: each ``tile.mesh_zl`` block of a
    ceiling square that meets one of ``airports``' boundaries, at the
    finest level the provider has there (:func:`_available_zl`); ``{}``
    when the source abstains or nothing is finer than ``cover_zl``."""
    if provider is None:
        provider = _provider(getattr(tile, "default_website", ""))
    ceiling = _ceiling_zl(tile, provider)
    if ceiling is None:
        return {}
    probe = probe or _probe_tile
    floor = int(tile.cover_zl)
    step = 2 ** (int(tile.mesh_zl) - ceiling)
    squares = set()
    for airport in airports:
        squares |= COVER.region_squares(
            dico_airports[airport].get("boundary"), tile.lat, tile.lon, ceiling)
    squares = sorted(squares)
    with ThreadPoolExecutor(max_workers=PROBE_THREADS) as pool:
        zooms = list(pool.map(
            lambda sq: _available_zl(provider, sq, ceiling, floor, probe),
            squares))
    blocks = {}
    for square, zl in zip(squares, zooms, strict=True):
        if zl <= floor:
            continue
        for til_x in range(square[0] * step, (square[0] + 16) * step, 16):
            for til_y in range(square[1] * step, (square[1] + 16) * step, 16):
                blocks[(til_x, til_y)] = zl
    return blocks
