"""The map's "Live flight preview" (#2001; flight manager / World spec
§14): each visible texture square drawn from the imagery INSTALLED for
X-Plane, at the resolution the map shows it, marked where X-Plane shows
something else (owner 2026-11-12T19:28Z: the map "show[s] exactly what's
showing in X-Plane when in the Fly view").  The engine reads the
textures (both apps draw what it returns); this module is the rule and
the read, pure of settings (``o4_engine.live_preview_commands`` finds
the folders, ``o4_engine.live_preview_witness`` what X-Plane holds).

* A SQUARE is one Ortho4XP texture, ``<til_y>_<til_x>_<provider><zl>
  .dds``: 16 x 16 web-mercator slippy tiles at ``zl``, so its bounds are
  slippy-tile bounds and the map draws it without reprojection
  (:func:`parse_texture`).
* :func:`existing_dirs` -- a tile's candidate texture folders, in the
  order given, that exist (each once, by real path); the first folder
  holding a name wins.
* :func:`squares` -- EVERY square of a viewport (no count cap, #2012),
  nearest the viewport's centre first (the order an app fetches in); none
  while the map is so far out that a square would be under
  :data:`MIN_SQUARE_PX` on screen.  A square under that size is left out
  only where a coarser installed square of its tile lies under it (that
  one shows its ground, :func:`_covered`), or with its tile's coarsest
  squares: a tile goes as a whole as the map zooms out, never opening a
  hole.  Each
  carries the mip to fetch (:func:`mip_px`: the square's on-screen size
  in device pixels rounded up to a power of two, up to the installed
  file's full width -- 4096 px for a full-resolution square), its
  ``stamp`` (modification time and size: a changed stamp is fetched
  again), ``tier_px`` / ``sharp`` (the installed width; full resolution,
  #2020) and ``stale`` (X-Plane still holds what was there before the
  file changed: "reload to see").  ``tiles`` lists the 1° tiles in view
  that are not drawn as ours: ``own`` (X-Plane draws its own scenery
  there -- no tile of ours, or a World-pack placeholder; the map's base
  imagery shows, marked) and ``reload`` (our tile is installed, X-Plane
  loaded what was there before).
* :func:`draw_order` -- the order an app DRAWS the squares in: the
  coarsest texture zoom level first, each finer level on top (where
  X-Plane has both, its mesh shows the finer, #2012: drawn nearest-first a
  coarse square covered the finer ones by where the view's centre lay).
* :func:`fetch_plan` -- the order an app fetches mips in: a coarse
  :data:`COARSE_MIP_PX` image for every square that has none, nearest
  first, then each square at its own size (coarse first, then finer).
* :func:`mip_image` -- ONE mip level of a square's DDS
  (``O4_DDS_File.read_level``: the header and that level only), decoded
  (``O4_DDS_Decode``) and encoded (JPEG for an opaque square, PNG when it
  has transparency).  A 4096 px level costs ~0.5 s, so the engine reads
  any level above :data:`INLINE_MIP_PX` on a worker
  (``o4_engine.live_preview_mips``).
* :class:`ByteLRU` -- a least-recently-used map bounded in bytes: the
  engine's encoded mips and each app's decoded images
  (:data:`APP_CACHE_MB`; a 4096 px RGBA image is 64 MB, a view at the
  closest zoom needs a few).

No airport or tile is named.
"""
from __future__ import annotations

import base64
import io
import math
import os
import re
from collections import OrderedDict

import O4_DDS_File as DDS
import O4_DDS_Tiers as TIERS
import O4_World_Pack as WP
from O4_DDS_Decode import decode_blocks

__all__ = ["APP_CACHE_MB", "COARSE_MIP_PX", "INLINE_MIP_PX", "MAX_MIP_PX",
           "MIN_MIP_PX", "MIN_SQUARE_PX", "TILE_STATES", "ByteLRU",
           "draw_order", "existing_dirs", "fetch_plan", "mip_image", "mip_px",
           "parse_texture", "squares", "tile_squares"]

#: Below this many screen pixels a square is not drawn (the map is too
#: far out for imagery to read; the tile outlines say enough).
MIN_SQUARE_PX = 12.0
#: The finest mip: a full-resolution texture's own width.
MAX_MIP_PX = TIERS.FULL_WIDTH
MIN_MIP_PX = 32
#: The first image an app fetches for a square that shows nothing yet.
COARSE_MIP_PX = 64
#: Levels up to this size are read where they are asked for (~10 ms);
#: finer ones on the engine's worker.
INLINE_MIP_PX = 512
#: Decoded images an app keeps, in MB (least recently listed dropped
#: first).
APP_CACHE_MB = 512
#: ``tiles[].state``: X-Plane draws its own scenery here; X-Plane loaded
#: what was here before our tile.
TILE_STATES = ("own", "reload")
#: The coarsest texture zoom level a scan looks for: below a degree of
#: this many pixels, no square could reach :data:`MIN_SQUARE_PX`.
_COARSEST_ZL = 15

# <til_y_top>_<til_x_left>_<provider><zl>.dds; a suffix (an overlay) is
# not a square.
_NAME = re.compile(r"^(\d+)_(\d+)_([A-Za-z0-9]+?)(1\d|20)\.dds$",
                   re.IGNORECASE)
#: (path, stamp) -> installed width; bounded by :data:`_HEADERS_MAX`.
_HEADERS: dict = {}
_HEADERS_MAX = 200_000


def _lat(y: float, n: int) -> float:
    return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))


def parse_texture(name: str) -> "dict | None":
    """``{row, col, zl, provider, north, south, west, east}`` of an
    Ortho4XP texture name, or ``None``."""
    m = _NAME.match(name)
    if not m:
        return None
    row, col, zl = int(m.group(1)), int(m.group(2)), int(m.group(4))
    n = 2 ** zl
    return {"row": row, "col": col, "zl": zl, "provider": m.group(3),
            "north": _lat(row, n), "south": _lat(row + 16, n),
            "west": col / n * 360.0 - 180.0,
            "east": (col + 16) / n * 360.0 - 180.0}


def _tiles_in(south: float, west: float, north: float,
              east: float) -> "list[tuple[int, int]]":
    """The 1° tiles a viewport overlaps (an edge on a tile's border does
    not), its centre's first."""
    lat0 = math.floor(max(south, -85.0))
    lon0 = math.floor(max(west, -180.0))
    lat1 = max(lat0, math.ceil(min(north, 85.0)) - 1)
    lon1 = max(lon0, math.ceil(min(east, 180.0)) - 1)
    clat, clon = (south + north) / 2, (west + east) / 2
    tiles = [(la, lo) for la in range(lat0, lat1 + 1)
             for lo in range(lon0, lon1 + 1)]
    return sorted(tiles, key=lambda t: (t[0] + 0.5 - clat) ** 2
                  + (t[1] + 0.5 - clon) ** 2)


def existing_dirs(candidates) -> "list[str]":
    """``candidates`` that are folders, in order, each once by real
    path."""
    out, seen = [], set()
    for folder in candidates:
        if not folder:
            continue
        real = os.path.realpath(folder)
        if real not in seen and os.path.isdir(folder):
            seen.add(real)
            out.append(folder)
    return out


def mip_px(screen_px: float, tier_px: int = MAX_MIP_PX) -> int:
    """The mip to fetch for a square ``screen_px`` device pixels wide on
    screen: rounded up to a power of two, at least :data:`MIN_MIP_PX`,
    at most the installed width ``tier_px`` (what the file holds)."""
    top = max(MIN_MIP_PX, min(MAX_MIP_PX, int(tier_px or MAX_MIP_PX)))
    want = max(MIN_MIP_PX, float(screen_px))
    return min(top, 2 ** math.ceil(math.log2(want)))


def tile_squares(folders) -> "list[dict]":
    """Every square installed in a tile's ``folders`` (the first folder
    holding a name wins): :func:`parse_texture`'s fields with ``name``,
    ``path``, ``stamp`` and ``mtime`` (seconds)."""
    found = {}
    for folder in folders:
        try:
            entries = list(os.scandir(folder))
        except OSError:
            continue
        for entry in entries:
            if entry.name in found or DDS.is_partial_name(entry.name):
                continue
            square = parse_texture(entry.name)
            if square is None:
                continue
            try:
                st = entry.stat()
            except OSError:
                continue
            square.update(name=entry.name, path=entry.path,
                          stamp="%d-%d" % (st.st_mtime_ns, st.st_size),
                          mtime=st.st_mtime)
            found[entry.name] = square
    return list(found.values())


def _installed_width(path: str, stamp: str) -> int:
    """The DDS's width from its header, read once per (path, stamp)."""
    key = (path, stamp)
    width = _HEADERS.get(key)
    if width is None:
        header = TIERS.texture_header(path)
        width = header[0] if header else 0
        if len(_HEADERS) >= _HEADERS_MAX:
            _HEADERS.clear()
        _HEADERS[key] = width
    return width


def _overlaps(sq: dict, south, west, north, east) -> bool:
    return not (sq["east"] < west or sq["west"] > east
                or sq["north"] < south or sq["south"] > north)


def _covered(tile: "list[dict]") -> "set[str]":
    """The names of a tile's squares that lie on a coarser installed
    square of the same tile (texture squares sit on a 16-tile grid, so a
    square at ``zl`` lies on exactly one square at each coarser level)."""
    have = {(sq["zl"], sq["row"], sq["col"]) for sq in tile}
    levels = sorted({sq["zl"] for sq in tile})
    out = set()
    for sq in tile:
        for zl in levels:
            if zl >= sq["zl"]:
                break
            shift = sq["zl"] - zl
            if (zl, (sq["row"] >> shift) // 16 * 16,
                    (sq["col"] >> shift) // 16 * 16) in have:
                out.add(sq["name"])
                break
    return out


def _no_witness(_lat: int, _lon: int):
    return "ours", None


def squares(south: float, west: float, north: float, east: float,
            px_per_deg: float, folders_of, tile_state=None,
            scale: float = 1.0, late=frozenset()) -> dict:
    """The squares and marked tiles of a viewport (the module docstring).

    ``px_per_deg``: screen points per degree of longitude; ``scale``:
    device pixels per point (a Retina screen 2).  ``folders_of(lat,
    lon)``: a tile's texture folders (:func:`existing_dirs`).
    ``tile_state(lat, lon)`` -> ``(state, loaded_at)``: ``"ours"`` or a
    :data:`TILE_STATES` word, and when X-Plane loaded the tile (epoch
    seconds, ``None`` when it has not); a square whose file is newer than
    that load is ``stale``, as is one whose key is in ``late`` (the
    follow job's late landings, when the load is not known).  Replies
    ``{"squares": [{key, path, stamp, px, zl, tier_px, sharp, stale,
    north, south, west, east}], "tiles": [{lat, lon, state}], "reason":
    "" | "zoom"}`` (``zoom``: too far out for squares to be drawn)."""
    tile_state = tile_state or _no_witness
    if px_per_deg * 16 * 360.0 / 2 ** _COARSEST_ZL < MIN_SQUARE_PX:
        return {"squares": [], "tiles": [], "reason": "zoom"}
    out, marks, too_small = [], [], False
    for lat, lon in _tiles_in(south, west, north, east):
        state, loaded_at = tile_state(lat, lon)
        if state in TILE_STATES:
            marks.append({"lat": lat, "lon": lon, "state": state})
        if state == "own":
            continue                    # X-Plane does not draw ours here
        tile = tile_squares(folders_of(lat, lon))
        covered = _covered(tile)
        # the tile's coarsest squares on screen: while they show, so does
        # every finer square with no coarser one under it
        coarse = max((sq["east"] - sq["west"] for sq in tile), default=0)
        coarse_shown = coarse * px_per_deg >= MIN_SQUARE_PX
        for sq in tile:
            if not _overlaps(sq, south, west, north, east):
                continue
            screen = (sq["east"] - sq["west"]) * px_per_deg
            if screen < MIN_SQUARE_PX and (sq["name"] in covered
                                           or not coarse_shown):
                too_small = True
                continue
            key = "%s/%s" % (WP.tile_name(lat, lon), sq["name"])
            stale = state == "reload" or key in late or (
                loaded_at is not None and sq["mtime"] > loaded_at)
            out.append({"key": key,
                        "path": sq["path"], "stamp": sq["stamp"],
                        "px": screen * scale, "zl": sq["zl"],
                        "stale": bool(stale),
                        "north": sq["north"], "south": sq["south"],
                        "west": sq["west"], "east": sq["east"]})
    clat, clon = (south + north) / 2, (west + east) / 2
    out.sort(key=lambda s: ((s["north"] + s["south"]) / 2 - clat) ** 2
             + ((s["west"] + s["east"]) / 2 - clon) ** 2)
    for sq in out:
        sq["tier_px"] = _installed_width(sq["path"], sq["stamp"])
        sq["sharp"] = sq["tier_px"] >= TIERS.FULL_WIDTH
        sq["px"] = mip_px(sq["px"], sq["tier_px"])
    return {"squares": out, "tiles": marks,
            "reason": "zoom" if too_small and not out else ""}


def draw_order(rows) -> list:
    """``rows`` (:func:`squares`' list) in the order they are drawn: by
    texture zoom level, coarsest first, so a finer square is painted over
    the coarser one it lies on; within a level the given order."""
    return sorted(rows, key=lambda sq: sq.get("zl", 0))


def fetch_plan(rows, held) -> "list[tuple[dict, int]]":
    """``[(square, px)]`` in the order an app fetches: a
    :data:`COARSE_MIP_PX` image for each square of ``rows`` (nearest
    first) that ``held(key)`` -> ``(stamp, px) | None`` shows nothing for,
    then every square whose held image is not its stamp at its ``px``.
    A square with an older image keeps it on screen until the new one
    lands, so it skips the coarse step."""
    coarse, fine = [], []
    for square in rows:
        have = held(square["key"])
        current = have is not None and have[0] == square["stamp"]
        if current and have[1] >= square["px"]:
            continue
        if have is None and square["px"] > COARSE_MIP_PX:
            coarse.append((square, COARSE_MIP_PX))
        fine.append((square, square["px"]))
    return coarse + fine


class ByteLRU:
    """A least-recently-used map bounded in bytes: :meth:`put` drops the
    least recently used entries while the total is over ``budget``
    (the newest entry always stays)."""

    def __init__(self, budget: int) -> None:
        self.budget = int(budget)
        self.bytes = 0
        self._items: "OrderedDict" = OrderedDict()

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, key) -> bool:
        return key in self._items

    def keys(self) -> list:
        return list(self._items)

    def get(self, key, default=None):
        """The value (now most recently used), or ``default``."""
        if key not in self._items:
            return default
        self._items.move_to_end(key)
        return self._items[key][0]

    def peek(self, key, default=None):
        """The value, its recency unchanged."""
        item = self._items.get(key)
        return default if item is None else item[0]

    def touch(self, keys) -> None:
        """``keys`` (those held) become the most recently used, in order."""
        for key in keys:
            if key in self._items:
                self._items.move_to_end(key)

    def put(self, key, value, size: int) -> None:
        self.pop(key)
        self._items[key] = (value, int(size))
        self.bytes += int(size)
        while self.bytes > self.budget and len(self._items) > 1:
            _key, (_value, dropped) = self._items.popitem(last=False)
            self.bytes -= dropped

    def pop(self, key) -> None:
        item = self._items.pop(key, None)
        if item is not None:
            self.bytes -= item[1]

    def clear(self) -> None:
        self._items.clear()
        self.bytes = 0


def mip_image(path: str, px: int = 256) -> dict:
    """One mip of a square's texture, ready to draw: ``{width, height,
    format: "jpeg" | "png", data: base64}``.  ``ValueError`` for a file
    that is not a whole DXT1/DXT5 texture."""
    if not str(path).lower().endswith(".dds"):
        raise ValueError("not a texture: %s" % path)
    from PIL import Image

    px = max(MIN_MIP_PX, min(MAX_MIP_PX, int(px)))
    width, height, fmt, blocks = DDS.read_level(path, px)
    rgba = decode_blocks(blocks, width, height, fmt)
    buffer = io.BytesIO()
    if int(rgba[..., 3].min()) == 255:
        Image.fromarray(rgba[..., :3].copy(), "RGB").save(
            buffer, "JPEG", quality=82)
        kind = "jpeg"
    else:
        Image.fromarray(rgba, "RGBA").save(buffer, "PNG")
        kind = "png"
    return {"width": width, "height": height, "format": kind,
            "data": base64.b64encode(buffer.getvalue()).decode("ascii")}
