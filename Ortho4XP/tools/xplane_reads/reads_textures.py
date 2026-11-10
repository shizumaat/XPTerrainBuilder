"""Ortho4XP texture names, DDS mip layout and the .ter LOAD_CENTER size, for
the X-Plane read recorder (#1992).  Standard library only: the owner runs the
recorder with macOS /usr/bin/python3 3.9 and no engine on the path, so this
does not import ``src/O4_DDS_File.py`` (which owns the engine's DDS writer).
"""
from __future__ import annotations

import math
import os
import re
import struct

# Ortho4XP names: <til_y_top>_<til_x_left>_<provider><zl>[_overlay].dds|ter
O4_NAME = re.compile(r"^(\d+)_(\d+)_([A-Za-z]+?)(\d\d)(?:_[A-Za-z_]+)?\.(dds|ter)$")
DSF_NAME = re.compile(r"^([+-]\d\d)([+-]\d\d\d)\.dsf$")
EARTH_RADIUS_M = 6378137.0       # O4_Geo_Utils.earth_radius (web mercator)


def parse_name(base: str) -> dict | None:
    """Ortho4XP texture/terrain or DSF name -> its square (lat/lon bounds)."""
    m = O4_NAME.match(base)
    if m:
        y, x, zl = int(m.group(1)), int(m.group(2)), int(m.group(4))
        n = 2 ** zl

        def lat(yy: float) -> float:
            return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * yy / n))))
        return {"type": m.group(5), "row": y, "col": x, "zl": zl,
                "provider": m.group(3),
                "north": lat(y), "south": lat(y + 16),
                "west": x / n * 360.0 - 180.0,
                "east": (x + 16) / n * 360.0 - 180.0}
    m = DSF_NAME.match(base)
    if m:
        la, lo = int(m.group(1)), int(m.group(2))
        return {"type": "dsf", "north": la + 1.0, "south": float(la),
                "west": float(lo), "east": lo + 1.0}
    return None


def square_size_m(sq: dict) -> int | None:
    """The LOAD_CENTER size Ortho4XP writes for a square (O4_DSF_Utils:
    web-mercator pixel size at the square's centre latitude x 4096)."""
    if "zl" not in sq:
        return None
    n = 2 ** sq["zl"]
    yc = sq["row"] + 8
    lat = math.atan(math.sinh(math.pi * (1 - 2 * yc / n)))
    return int(2 * math.pi * EARTH_RADIUS_M * math.cos(lat)
               / 2 ** (sq["zl"] + 8) * 4096)


def ter_load_center(path: str) -> int | None:
    """The size (metres) on a .ter's ``LOAD_CENTER lat lon SIZE PX`` line."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 4 and parts[0] == "LOAD_CENTER":
                    return int(float(parts[3]))
    except OSError:
        return None
    return None


def load_center_of(dds_path: str, sq: dict | None) -> tuple[int | None, str]:
    """S for a texture: the pack's own .ter when it is readable, else the
    size Ortho4XP would write.  Returns (S, "ter" | "name" | "none")."""
    stem = os.path.splitext(os.path.basename(dds_path))[0]
    pack = os.path.dirname(os.path.dirname(dds_path))
    s = ter_load_center(os.path.join(pack, "terrain", stem + ".ter"))
    if s:
        return s, "ter"
    s = square_size_m(sq) if sq else None
    return (s, "name") if s else (None, "none")


# DXGI formats (DX10 header) -> bytes per 4x4 block (block) or per pixel.
DXGI_BLOCK = {70: 8, 71: 8, 72: 8, 73: 16, 74: 16, 75: 16, 76: 16, 77: 16,
              78: 16, 79: 8, 80: 8, 81: 8, 82: 16, 83: 16, 84: 16, 94: 16,
              95: 16, 96: 16, 97: 16, 98: 16, 99: 16}
DXGI_PIXEL = {2: 16, 10: 8, 24: 4, 28: 4, 29: 4, 87: 4, 88: 4, 91: 4}
FOURCC_BLOCK = {b"DXT1": 8, b"DXT2": 16, b"DXT3": 16, b"DXT4": 16,
                b"DXT5": 16, b"ATI1": 8, b"BC4U": 8, b"BC4S": 8,
                b"ATI2": 16, b"BC5U": 16, b"BC5S": 16}


def dds_header(blob: bytes, size: int) -> dict | None:
    """Parse a DDS header (first 148 bytes) -> geometry needed for mips."""
    if len(blob) < 128 or blob[:4] != b"DDS ":
        return None
    (_hsz, flags, height, width, _pitch, _depth,
     mips) = struct.unpack_from("<7I", blob, 4)
    pf_flags, fourcc, rgb_bits = struct.unpack_from("<I4sI", blob, 80)
    hdr = 128
    block = pixel = None
    fmt = fourcc.decode("latin-1") if pf_flags & 0x4 else f"rgb{rgb_bits}"
    if pf_flags & 0x4 and fourcc == b"DX10":
        if len(blob) < 148:
            return None
        dxgi = struct.unpack_from("<I", blob, 128)[0]
        hdr, fmt = 148, f"dxgi{dxgi}"
        block, pixel = DXGI_BLOCK.get(dxgi), DXGI_PIXEL.get(dxgi)
    elif pf_flags & 0x4:
        block = FOURCC_BLOCK.get(fourcc)
    else:
        pixel = rgb_bits // 8 or None
    if not (flags & 0x20000) or mips == 0:
        mips = 1
    return {"size": size, "width": width, "height": height, "mips": mips,
            "format": fmt, "header": hdr, "block": block, "pixel": pixel}


def mip_ranges(info: dict) -> list[tuple[int, int, int, int, int]]:
    """[(level, start, end, w, h)] byte ranges of each mip in the file."""
    out, off = [], info["header"]
    w, h = info["width"], info["height"]
    for lvl in range(info["mips"]):
        if info.get("block"):
            n = max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * info["block"]
        elif info.get("pixel"):
            n = w * h * info["pixel"]
        else:
            return []
        out.append((lvl, off, off + n, w, h))
        off += n
        w, h = max(1, w // 2), max(1, h // 2)
    return out


def coverage_finest(info: dict, spans: list[tuple[int, int]],
                    need: float = 0.5) -> int | None:
    """Finest mip whose bytes are at least `need` covered by `spans`
    (byte ranges read or resident)."""
    mips = mip_ranges(info) if info and "width" in info else []
    if not mips or not spans:
        return None
    spans = sorted(spans)
    for lvl, s, e, _w, _h in mips:
        got = sum(max(0, min(e, b) - max(s, a)) for a, b in spans)
        if got >= need * (e - s):
            return lvl
    return None


def resident_finest(info: dict, pages: list[list[int]],
                    page_size: int) -> int | None:
    """Finest mip from the page ranges resident right after a close."""
    return coverage_finest(info, [(a * page_size, b * page_size)
                                  for a, b in pages])
