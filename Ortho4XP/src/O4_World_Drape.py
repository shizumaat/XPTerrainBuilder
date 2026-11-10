"""A DRAPED tile for the World pack: orthophotos laid over X-Plane's own
mesh, no mesh of ours (owner idea 2026-11-10, "seems worth looking into";
the World pack is ``O4_World_Pack``).

For a tile the aircraft only passes over, the full build (OSM, DEM,
Triangle mesh, masks: ~5 min at the light tier) is replaced by an OVERLAY
DSF that drapes one polygon per ortho texture square over the default
Global Scenery mesh, the way WED drapes an airport orthophoto:

* one ``.pol`` per texture (``DRAPED_POLYGON``, ``TEXTURE_NOWRAP``,
  ``LOAD_CENTER`` so X-Plane pages its resolution by distance, layer
  group ``terrain +1`` = above the ground, below beaches, airports and
  roads);
* one UV-mapped polygon per texture square in the DSF (parameter 65535,
  coordinates ``lon lat s t``), clipped to the tile; the corner ST values
  are Ortho4XP's own (``O4_Geo_Utils.st_coord``, Web Mercator), linear
  between corners (error under 1 m for a ZL16 square at 53 N, sub-pixel
  at 512 px);
* ``sim/overlay 1`` and ``sim/creation_agent`` :data:`DRAPE_AGENT`, so
  ``world.py`` can tell a drape from a placeholder and from a real tile.

Same pack layout as a real tile: ``terrain/<tile>/<name>.pol`` (texture
``../../textures/<tile>/<name>.dds``) and the DSF at
``Earth nav data/<block>/<tile>.dsf``; :func:`O4_World_Pack.swap_in`
lands it unchanged.  The imagery itself is fetched by
``O4_World_Drape_Fetch`` (the engine's download/convert at the
placeholder tier).
"""
from __future__ import annotations

import math
import os
import re
import tempfile

import O4_Geo_Utils as GEO
import O4_World_Pack as WP

__all__ = ["DRAPE_AGENT", "LAYER_GROUP", "texture_squares", "drape_quad",
           "pol_text", "drape_dsf_text", "write_drape", "verify_drape",
           "is_drape", "dds_width", "default_dds_name"]

#: ``sim/creation_agent`` of a draped tile (:func:`is_drape`).
DRAPE_AGENT = "XPTerrainBuilder world drape"
#: Above the ground (default scenery puts its ground .pol at ``terrain +1``),
#: below beaches, airport pavement and roads (OBJ8 ``ATTR_layer_group``).
LAYER_GROUP = "terrain +1"
_M_PER_DEG = 111_320.0
#: ``sim/exclude_<class>`` of the DSF spec (all but forests are polygons;
#: a whole-tile rectangle serves both).
_EXCLUDABLE = ("obj", "fac", "for", "bch", "net", "lin", "pol", "str")


def texture_squares(lat: int, lon: int, zl: int) -> list[tuple[int, int]]:
    """Every ZL ``zl`` texture square (16 x 16 map tiles, Ortho4XP's
    ``wgs84_to_orthogrid`` grid) that overlaps tile (lat, lon), as
    ``(til_x_left, til_y_top)``, north-west first."""
    eps = 1e-9
    x0, y0 = GEO.wgs84_to_orthogrid(lat + 1 - eps, lon + eps, zl)
    x1, y1 = GEO.wgs84_to_orthogrid(lat + eps, lon + 1 - eps, zl)
    return [(x, y) for y in range(y0, y1 + 1, 16)
            for x in range(x0, x1 + 1, 16)]


def _bounds(til_x: int, til_y: int, zl: int) -> tuple[float, float, float, float]:
    """(south, west, north, east) of a texture square."""
    north, west = GEO.gtile_to_wgs84(til_x, til_y, zl)
    south, east = GEO.gtile_to_wgs84(til_x + 16, til_y + 16, zl)
    return south, west, north, east


def drape_quad(lat: int, lon: int, til_x: int, til_y: int,
               zl: int) -> list[tuple[float, float, float, float]] | None:
    """The square's polygon clipped to the tile, counter-clockwise from
    the south-west corner, each point ``(lon, lat, s, t)``; ``None`` when
    the square does not reach into the tile."""
    s0, w0, n0, e0 = _bounds(til_x, til_y, zl)
    south, west = max(s0, lat), max(w0, lon)
    north, east = min(n0, lat + 1), min(e0, lon + 1)
    if west >= east or south >= north:
        return None
    corners = ((west, south), (east, south), (east, north), (west, north))
    return [(x, y, *GEO.st_coord(y, x, til_x, til_y, zl, ""))
            for x, y in corners]


def pol_text(texture_rel: str, til_x: int, til_y: int, zl: int,
             px: int) -> str:
    """The ``.pol`` of one texture square: clamped texture (an orthophoto
    sub-section, never tiled), ``LOAD_CENTER`` at the square's centre with
    its ground size and the DDS's real width.  ``SCALE`` is ignored for a
    UV-mapped polygon; it is written as the square's size, like WED."""
    south, west, north, east = _bounds(til_x, til_y, zl)
    clat, clon = (south + north) / 2, (west + east) / 2
    h_m = (north - south) * _M_PER_DEG
    w_m = (east - west) * _M_PER_DEG * math.cos(math.radians(clat))
    return "\n".join([
        "A", "850", "DRAPED_POLYGON", f"# {DRAPE_AGENT}",
        f"LAYER_GROUP {LAYER_GROUP}",
        f"TEXTURE_NOWRAP {texture_rel}",
        f"SCALE {w_m:.1f} {h_m:.1f}",
        "NO_ALPHA",
        f"LOAD_CENTER {clat:.6f} {clon:.6f} {max(w_m, h_m):.0f} {px}", ""])


def drape_dsf_text(lat: int, lon: int, pols: list,
                   exclude: tuple[str, ...] = ()) -> str:
    """DSFTool text of the overlay: ``pols`` is ``[(POLYGON_DEF path,
    quad)]``; ``exclude`` names default-scenery classes to hide under the
    whole tile (``for`` = forests, ``obj`` = objects/autogen ...) — from
    the packs BELOW this one only (DSF spec, exclusion zones)."""
    bad = [c for c in exclude if c not in _EXCLUDABLE]
    if bad:
        raise ValueError(f"cannot exclude {bad}: one of {_EXCLUDABLE}")
    box = f"{lon}/{lat}/{lon + 1}/{lat + 1}"
    lines = ["A", "800", "DSF2TEXT", "",
             "PROPERTY sim/planet earth", "PROPERTY sim/overlay 1",
             f"PROPERTY sim/creation_agent {DRAPE_AGENT}"]
    lines += [f"PROPERTY sim/exclude_{c} {box}" for c in exclude]
    lines += [f"PROPERTY sim/west {lon}", f"PROPERTY sim/east {lon + 1}",
              f"PROPERTY sim/north {lat + 1}", f"PROPERTY sim/south {lat}", ""]
    lines += [f"POLYGON_DEF {path}" for path, _ in pols]
    lines.append("")
    for i, (_, quad) in enumerate(pols):
        lines += [f"BEGIN_POLYGON {i} 65535 4", "BEGIN_WINDING"]
        lines += [f"POLYGON_POINT {x:.9f} {y:.9f} {s:.6f} {t:.6f}"
                  for x, y, s, t in quad]
        lines += ["END_WINDING", "END_POLYGON"]
    return "\n".join(lines) + "\n"


def dds_width(path: str) -> int | None:
    """Pixel width from a DDS header, ``None`` for anything else."""
    try:
        with open(path, "rb") as handle:
            head = handle.read(20)
    except OSError:
        return None
    if len(head) < 20 or head[:4] != b"DDS ":
        return None
    return int.from_bytes(head[16:20], "little")


def default_dds_name(til_x: int, til_y: int, zl: int, provider: str) -> str:
    """``<til_y>_<til_x>_<provider><zl>.dds`` (the engine's
    ``FNAMES.dds_file_name_from_attributes`` for every provider but
    g2xpl)."""
    return f"{til_y}_{til_x}_{provider}{zl}.dds"


def write_drape(lat: int, lon: int, zl: int, provider: str, tex_in: str,
                out_dir: str, tool: str, exclude: tuple[str, ...] = (),
                dds_name=default_dds_name) -> dict:
    """Lay a draped tile out in ``out_dir`` (must not exist): the texture
    squares found as DDS in ``tex_in`` are hard-linked to
    ``textures/<tile>/``, one ``.pol`` each written to ``terrain/<tile>/``,
    and the DSF encoded by DSFTool.  Returns counts; a square that reaches
    into the tile but has no DDS is counted ``missing`` and left out (it
    shows X-Plane's default ground)."""
    tile = WP.tile_name(lat, lon)
    if os.path.exists(out_dir):
        raise FileExistsError(out_dir)
    ter_out = os.path.join(out_dir, "terrain", tile)
    tex_out = os.path.join(out_dir, "textures", tile)
    os.makedirs(ter_out)
    os.makedirs(tex_out)
    counts = {"squares": 0, "polygons": 0, "missing": 0}
    pols = []
    for til_x, til_y in texture_squares(lat, lon, zl):
        quad = drape_quad(lat, lon, til_x, til_y, zl)
        if quad is None:
            continue
        counts["squares"] += 1
        name = dds_name(til_x, til_y, zl, provider)
        src = os.path.join(tex_in, name)
        px = dds_width(src)
        if px is None:
            counts["missing"] += 1
            continue
        WP._link_or_copy(src, os.path.join(tex_out, name))
        pol = os.path.splitext(name)[0] + ".pol"
        with open(os.path.join(ter_out, pol), "w", encoding="utf-8",
                  newline="\n") as handle:
            handle.write(pol_text(f"../../textures/{tile}/{name}",
                                  til_x, til_y, zl, px))
        pols.append((f"terrain/{tile}/{pol}", quad))
    counts["polygons"] = len(pols)
    dsf = os.path.join(out_dir, WP.dsf_relpath(lat, lon))
    os.makedirs(os.path.dirname(dsf))
    with tempfile.TemporaryDirectory() as work:
        txt = os.path.join(work, tile + ".txt")
        with open(txt, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(drape_dsf_text(lat, lon, pols, exclude))
        WP._dsftool(tool, "--text2dsf", txt, dsf)
    counts["dsf_bytes"] = os.path.getsize(dsf)
    return counts


_POL_TEX = re.compile(r"^TEXTURE(?:_NOWRAP)?\s+(\S+)", re.M)
_POINT = re.compile(r"^POLYGON_POINT\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)", re.M)


def _points_problem(text: str, lat: int, lon: int) -> tuple[int, str | None]:
    """(points read, first point outside the tile or ST outside [0, 1])."""
    n = 0
    for m in _POINT.finditer(text):
        n += 1
        x, y, s, t = map(float, m.groups())
        inside = (lon - 1e-6 <= x <= lon + 1 + 1e-6
                  and lat - 1e-6 <= y <= lat + 1 + 1e-6)
        if not inside or not (-1e-4 <= s <= 1 + 1e-4 and -1e-4 <= t <= 1 + 1e-4):
            return n, f"point out of range: {m.group(0)}"
    return n, None


def _pol_problem(path: str) -> str | None:
    """Why the ``.pol`` at ``path`` would not draw, or ``None``."""
    with open(path, encoding="utf-8") as handle:
        body = handle.read()
    tex = _POL_TEX.search(body)
    dds = tex and os.path.normpath(os.path.join(os.path.dirname(path),
                                                tex.group(1)))
    if not dds or dds_width(dds) is None:
        return f"{os.path.basename(path)}: no DDS"
    if "LOAD_CENTER" not in body:
        return f"{os.path.basename(path)}: no LOAD_CENTER"
    return None


def verify_drape(root: str, lat: int, lon: int, tool: str) -> dict:
    """Read a draped tile's DSF back with DSFTool (``root`` = the pack or a
    staging folder of its shape): an overlay with :data:`DRAPE_AGENT`, one
    UV polygon per ``POLYGON_DEF``, every point inside the tile with ST in
    [0, 1], every ``.pol`` on disk under ``terrain/<tile>/`` and its DDS
    whole.  Returns counts and ``problems``."""
    tile = WP.tile_name(lat, lon)
    with tempfile.TemporaryDirectory() as work:
        txt = os.path.join(work, "v.txt")
        WP._dsftool(tool, "--dsf2text",
                    os.path.join(root, WP.dsf_relpath(lat, lon)), txt)
        with open(txt, encoding="utf-8") as handle:
            text = handle.read()
    defs = re.findall(r"^POLYGON_DEF\s+(\S+)", text, re.M)
    out = {"tile": tile, "overlay": "PROPERTY sim/overlay 1" in text,
           "agent": DRAPE_AGENT in text, "defs": len(defs),
           "polygons": len(re.findall(r"^BEGIN_POLYGON\s+\d+\s+65535\s+4",
                                      text, re.M)),
           "excludes": re.findall(r"^PROPERTY sim/exclude_(\w+)", text, re.M),
           "pols_checked": 0, "problems": []}
    out["points"], bad_point = _points_problem(text, lat, lon)
    if bad_point:
        out["problems"].append(bad_point)
    if out["polygons"] != out["defs"]:
        out["problems"].append(f"{out['defs']} defs, {out['polygons']} "
                               "UV polygons")
    for ref in defs:
        path = os.path.join(root, ref)
        if not ref.startswith(f"terrain/{tile}/") or not os.path.isfile(path):
            out["problems"].append(f"polygon def missing: {ref}")
            continue
        out["pols_checked"] += 1
        problem = _pol_problem(path)
        if problem:
            out["problems"].append(problem)
    return out


def is_drape(path: str) -> bool:
    """Whether the DSF at ``path`` is a draped tile (header agent)."""
    try:
        with open(path, "rb") as handle:
            head = handle.read(1024)
    except OSError:
        return False
    return DRAPE_AGENT.encode() in head
