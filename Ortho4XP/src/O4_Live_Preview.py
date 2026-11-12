"""The map's "Live flight preview" (#2001; flight manager / World spec
§14): each visible texture square drawn from the imagery INSTALLED for
X-Plane, so the pilot watches the map fill in around and ahead of the
aircraft.  The engine reads the textures (both apps draw what it
returns); this module is the rule and the read, pure of settings
(``o4_engine.live_preview_commands`` finds the folders).

* A SQUARE is one Ortho4XP texture, ``<til_y>_<til_x>_<provider><zl>
  .dds``: 16 x 16 web-mercator slippy tiles at ``zl``, so its bounds are
  slippy-tile bounds and the map draws it without reprojection
  (:func:`parse_texture`).
* :func:`existing_dirs` -- a tile's candidate texture folders, in the
  order given, that exist (each once, by real path); the first folder
  holding a name wins.
* :func:`squares` -- the squares to draw for a viewport, CAPPED by zoom
  (none while a square would be under :data:`MIN_SQUARE_PX` on screen;
  at most :data:`MAX_TILES` tiles and :data:`MAX_SQUARES` squares, the
  nearest the viewport's centre first) with the mip size each should be
  fetched at (:func:`_mip_px`: the on-screen size rounded up to a power of
  two, :data:`MIN_MIP_PX`..:data:`MAX_MIP_PX`).  Each carries a
  ``stamp`` (modification time and size): a square whose stamp changes
  (the follow job landed a finer tier, build-ahead swapped a tile in) is
  fetched again; its ``tier_px`` is the installed file's width (512 px a
  quick drape, 4096 full resolution: what X-Plane draws there, #2020)
  and ``sharp`` says it is full resolution: the apps outline those.
* :func:`mip_image` -- ONE mip level of a square's DDS
  (``O4_DDS_File.read_level``: the header and that level only, never the
  whole file), decoded (``O4_DDS_Decode``) and encoded small (JPEG for an
  opaque square, PNG when it has transparency).

Memory: a reply holds the encoded image (a 256 px JPEG is ~20 KB); the
apps keep at most :data:`APP_CACHE_IMAGES` decoded images (256 px RGBA is
256 KB, so <= 48 MB at the largest mip).  No airport or tile is named.
"""
from __future__ import annotations

import base64
import io
import math
import os
import re

import O4_DDS_File as DDS
import O4_DDS_Tiers as TIERS
import O4_World_Pack as WP
from O4_DDS_Decode import decode_blocks

__all__ = ["APP_CACHE_IMAGES", "MAX_MIP_PX", "MAX_SQUARES", "MAX_TILES",
           "MIN_MIP_PX", "MIN_SQUARE_PX", "existing_dirs", "mip_image",
           "parse_texture", "squares", "tile_squares"]

#: Below this many screen pixels a square is not drawn (the map is too
#: far out for imagery to read; the tile outlines say enough).
MIN_SQUARE_PX = 12.0
#: The finest mip fetched: the 256 px level (issue #2001).
MAX_MIP_PX = 256
MIN_MIP_PX = 32
#: Squares listed for one viewport, nearest its centre first.
MAX_SQUARES = 160
#: Tiles read for one viewport.
MAX_TILES = 12
#: Decoded images an app keeps (least recently drawn dropped first).
APP_CACHE_IMAGES = 192

# <til_y_top>_<til_x_left>_<provider><zl>.dds; a suffix (an overlay) is
# not a square.
_NAME = re.compile(r"^(\d+)_(\d+)_([A-Za-z0-9]+?)(1\d|20)\.dds$",
                   re.IGNORECASE)


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
    """The 1° tiles a viewport touches, its centre's first."""
    lat0, lat1 = math.floor(max(south, -85.0)), math.floor(min(north, 84.999))
    lon0, lon1 = math.floor(max(west, -180.0)), math.floor(min(east, 179.999))
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


def _mip_px(screen_px: float) -> int:
    """The mip size to fetch for a square ``screen_px`` wide on screen."""
    want = max(MIN_MIP_PX, min(MAX_MIP_PX, screen_px))
    return min(MAX_MIP_PX, 2 ** math.ceil(math.log2(want)))


def tile_squares(folders) -> "list[dict]":
    """Every square installed in a tile's ``folders`` (the first folder
    holding a name wins): :func:`parse_texture`'s fields with ``name``,
    ``path`` and ``stamp``."""
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
                          stamp="%d-%d" % (st.st_mtime_ns, st.st_size))
            found[entry.name] = square
    return list(found.values())


def _overlaps(sq: dict, south, west, north, east) -> bool:
    return not (sq["east"] < west or sq["west"] > east
                or sq["north"] < south or sq["south"] > north)


def squares(south: float, west: float, north: float, east: float,
            px_per_deg: float, folders_of) -> dict:
    """The squares to draw for a viewport (see the module docstring).

    ``px_per_deg``: screen pixels per degree of longitude.  ``folders_of
    (lat, lon)``: a tile's texture folders (:func:`existing_dirs`).
    Replies ``{"squares": [{key, path, stamp, px, zl, tier_px, sharp, north,
    south, west, east}], "capped": bool, "reason": "" | "zoom"}`` (``zoom``: squares
    are installed here but too small to draw at this zoom)."""
    tiles = _tiles_in(south, west, north, east)
    out, too_small = [], False
    capped = len(tiles) > MAX_TILES
    for lat, lon in tiles[:MAX_TILES] if px_per_deg > 0 else ():
        for sq in tile_squares(folders_of(lat, lon)):
            if not _overlaps(sq, south, west, north, east):
                continue
            screen = (sq["east"] - sq["west"]) * px_per_deg
            if screen < MIN_SQUARE_PX:
                too_small = True
                continue
            out.append({"key": "%s/%s" % (WP.tile_name(lat, lon), sq["name"]),
                        "path": sq["path"], "stamp": sq["stamp"],
                        "px": _mip_px(screen), "zl": sq["zl"],
                        "north": sq["north"], "south": sq["south"],
                        "west": sq["west"], "east": sq["east"]})
    clat, clon = (south + north) / 2, (west + east) / 2
    out.sort(key=lambda s: ((s["north"] + s["south"]) / 2 - clat) ** 2
             + ((s["west"] + s["east"]) / 2 - clon) ** 2)
    if len(out) > MAX_SQUARES:
        out, capped = out[:MAX_SQUARES], True
    for sq in out:
        header = TIERS.texture_header(sq["path"])
        sq["tier_px"] = header[0] if header else 0
        sq["sharp"] = sq["tier_px"] >= TIERS.FULL_WIDTH
    return {"squares": out, "capped": capped,
            "reason": "zoom" if too_small and not out else ""}


def mip_image(path: str, px: int = MAX_MIP_PX) -> dict:
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
