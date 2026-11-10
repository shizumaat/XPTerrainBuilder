"""One Custom Scenery pack for every tile: the World pack experiment
(owner idea 2026-11-10; #1992 local-imagery loader, spec §2/§4.5).

Instead of one ``zOrtho4XP_<tile>`` folder per tile, a single pack holds an
OVERLAY-ONLY placeholder DSF for every tile not built yet (X-Plane falls
through to its default mesh there) and, per built tile, the real DSF with
its ``.ter`` and textures in per-tile subfolders::

    <pack>/Earth nav data/+50-070/+53-063.dsf
    <pack>/terrain/+53-063/<name>.ter        (textures as ../../textures/+53-063/)
    <pack>/textures/+53-063/<name>.dds|png

Building a tile later replaces its placeholder DSF in one rename
(:func:`swap_in`).  Whether X-Plane picks that up without a scenery reload
is what the kit tests (hypotheses H1-H3 of the lane brief).

Standard library plus ``O4_Scenery_Packs`` (itself stdlib-only); DSFTool is
passed in as a path and run through ``subprocess``, so the module runs from
a kit copy beside the engine checkout.
"""
from __future__ import annotations

import hashlib
import math
import os
import re
import shutil
import subprocess
import tempfile

__all__ = [
    "PACK_NAME", "PLACEHOLDER_AGENT", "tile_name", "parse_tile",
    "dsf_relpath", "placeholder_text", "write_placeholder", "is_placeholder",
    "block_tiles", "rewrite_ter", "rewrite_dsf_text", "relayout_tile",
    "verify_tile", "swap_in", "swap_out", "tile_reach", "xp_window", "ini_install",
    "ini_remove", "dsftool_path", "dsf_header",
]

PACK_NAME = "zXPTerrainBuilder World"
#: ``sim/creation_agent`` of a placeholder: how :func:`is_placeholder` knows one.
PLACEHOLDER_AGENT = "XPTerrainBuilder world placeholder"
_M_PER_DEG = 111_320.0


def tile_name(lat: int, lon: int) -> str:
    """``+53-063`` for (53, -63)."""
    return f"{lat:+03d}{lon:+04d}"


def parse_tile(name: str) -> tuple[int, int]:
    """(53, -63) for ``+53-063``; ``ValueError`` for anything else."""
    m = re.fullmatch(r"([+-]\d\d)([+-]\d\d\d)", name.strip())
    if not m:
        raise ValueError(f"not a tile name: {name!r} (want e.g. +53-063)")
    return int(m.group(1)), int(m.group(2))


def dsf_relpath(lat: int, lon: int) -> str:
    """``Earth nav data/+50-070/+53-063.dsf`` (10° block, floor)."""
    block = tile_name(10 * math.floor(lat / 10), 10 * math.floor(lon / 10))
    return os.path.join("Earth nav data", block, tile_name(lat, lon) + ".dsf")


def placeholder_text(lat: int, lon: int) -> str:
    """DSFTool text of an overlay-only DSF with no content: X-Plane draws
    nothing from it and takes the tile's base mesh from the next pack down
    (the default Global Scenery).  The same shape as an exclusion-only WED
    overlay."""
    return "\n".join([
        "A", "800", "DSF2TEXT", "",
        "PROPERTY sim/planet earth",
        "PROPERTY sim/overlay 1",
        f"PROPERTY sim/creation_agent {PLACEHOLDER_AGENT}",
        f"PROPERTY sim/west {lon}", f"PROPERTY sim/east {lon + 1}",
        f"PROPERTY sim/north {lat + 1}", f"PROPERTY sim/south {lat}", ""])


def _dsftool(tool: str, *args: str, timeout: float = 600) -> str:
    done = subprocess.run([tool, *args], capture_output=True, text=True,
                          timeout=timeout)
    if done.returncode != 0:
        raise RuntimeError(f"DSFTool {' '.join(args[:1])} failed "
                           f"(exit {done.returncode}): {done.stdout[-400:]}"
                           f"{done.stderr[-400:]}")
    return done.stdout


def write_placeholder(pack: str, lat: int, lon: int, tool: str) -> str:
    """Write and round-trip-check the placeholder DSF of a tile into
    ``pack``; returns its path.  Written beside its name and renamed."""
    dest = os.path.join(pack, dsf_relpath(lat, lon))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with tempfile.TemporaryDirectory() as work:
        src = os.path.join(work, "ph.txt")
        with open(src, "w", encoding="utf-8") as handle:
            handle.write(placeholder_text(lat, lon))
        out = os.path.join(work, "ph.dsf")
        _dsftool(tool, "--text2dsf", src, out)
        back = os.path.join(work, "back.txt")
        _dsftool(tool, "--dsf2text", out, back)
        with open(back, encoding="utf-8") as handle:
            text = handle.read()
        for want in ("PROPERTY sim/overlay 1", f"PROPERTY sim/west {lon}",
                     f"PROPERTY sim/south {lat}", PLACEHOLDER_AGENT):
            if want not in text:
                raise RuntimeError(f"placeholder {tile_name(lat, lon)}: "
                                   f"round trip lost {want!r}")
        partial = dest + ".partial"
        shutil.copyfile(out, partial)
        os.replace(partial, dest)
    return dest


def is_placeholder(path: str) -> bool:
    """Whether the DSF at ``path`` is one of our placeholders (its header
    carries :data:`PLACEHOLDER_AGENT`; a real tile never does)."""
    try:
        with open(path, "rb") as handle:
            head = handle.read(1024)
    except OSError:
        return False
    return PLACEHOLDER_AGENT.encode() in head


def block_tiles(lat: int, lon: int, radius: int,
                skip=()) -> list[tuple[int, int]]:
    """Tiles of the (2r+1)² block centred on (lat, lon), minus ``skip``."""
    return [(la, lo) for la in range(lat - radius, lat + radius + 1)
            for lo in range(lon - radius, lon + radius + 1)
            if (la, lo) not in set(skip)]


_TER_TEX = re.compile(r"(?<![\w/.])\.\./textures/")


def rewrite_ter(text: str, tile: str) -> tuple[str, int]:
    """A ``.ter`` moved from ``terrain/`` to ``terrain/<tile>/``: every
    ``../textures/X`` becomes ``../../textures/<tile>/X``.  Returns the text
    and the number of references rewritten."""
    return _TER_TEX.subn(f"../../textures/{tile}/", text)


_DEF_PATH = re.compile(r"^((?:TERRAIN|OBJECT|POLYGON|NETWORK)_DEF\s+)"
                       r"(terrain|textures)/", re.M)


def rewrite_dsf_text(text: str, tile: str) -> tuple[str, int]:
    """DSFTool text of a tile moved into the World pack: every definition
    path under the pack's ``terrain/`` or ``textures/`` gains the tile
    subfolder.  Library paths (``lib/...``) and built-ins (``terrain_Water``)
    are left alone."""
    return _DEF_PATH.subn(lambda m: f"{m.group(1)}{m.group(2)}/{tile}/", text)


def _link_or_copy(src: str, dst: str) -> None:
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def relayout_tile(tile_dir: str, out_dir: str, lat: int, lon: int,
                  tool: str) -> dict:
    """Lay a built ``zOrtho4XP_<tile>`` folder out as World-pack files in
    ``out_dir`` (a staging folder with the pack's own shape).  Textures are
    hard-linked (copied across volumes); ``.ter`` and the DSF are rewritten.
    Returns counts.  ``out_dir`` must not exist yet."""
    tile = tile_name(lat, lon)
    if os.path.exists(out_dir):
        raise FileExistsError(out_dir)
    ter_out = os.path.join(out_dir, "terrain", tile)
    tex_out = os.path.join(out_dir, "textures", tile)
    os.makedirs(ter_out)
    os.makedirs(tex_out)
    counts = {"ter": 0, "ter_refs": 0, "textures": 0, "dsf_defs": 0}
    for name in sorted(os.listdir(os.path.join(tile_dir, "terrain"))):
        if not name.endswith(".ter"):
            continue
        with open(os.path.join(tile_dir, "terrain", name),
                  encoding="utf-8") as handle:
            text, n = rewrite_ter(handle.read(), tile)
        with open(os.path.join(ter_out, name), "w", encoding="utf-8",
                  newline="\n") as handle:
            handle.write(text)
        counts["ter"] += 1
        counts["ter_refs"] += n
    tex_in = os.path.join(tile_dir, "textures")
    for name in sorted(os.listdir(tex_in)):
        if name.lower().endswith((".dds", ".png")) and not name.startswith("."):
            _link_or_copy(os.path.join(tex_in, name), os.path.join(tex_out, name))
            counts["textures"] += 1
    src_dsf = os.path.join(tile_dir, dsf_relpath(lat, lon))
    dst_dsf = os.path.join(out_dir, dsf_relpath(lat, lon))
    os.makedirs(os.path.dirname(dst_dsf))
    with tempfile.TemporaryDirectory() as work:
        txt = os.path.join(work, tile + ".txt")
        _dsftool(tool, "--dsf2text", src_dsf, txt)
        with open(txt, encoding="utf-8") as handle:
            text, counts["dsf_defs"] = rewrite_dsf_text(handle.read(), tile)
        with open(txt, "w", encoding="utf-8") as handle:
            handle.write(text)
        _dsftool(tool, "--text2dsf", txt, dst_dsf)
    return counts


_TER_REF = re.compile(r"^\s*\S*TEX\S*\s+(\S+)", re.M)


def verify_tile(root: str, lat: int, lon: int, tool: str) -> dict:
    """Read the tile's DSF back with DSFTool and check that every
    ``terrain/`` definition names a ``.ter`` under ``root`` and every
    texture a ``.ter`` names exists.  ``root`` is the pack or a staging
    folder of the same shape.  Returns counts and ``problems``."""
    tile = tile_name(lat, lon)
    out = {"tile": tile, "defs": 0, "pack_defs": 0, "ters_checked": 0,
           "tex_refs": 0, "overlay": None, "problems": []}
    with tempfile.TemporaryDirectory() as work:
        txt = os.path.join(work, "v.txt")
        _dsftool(tool, "--dsf2text", os.path.join(root, dsf_relpath(lat, lon)),
                 txt)
        with open(txt, encoding="utf-8") as handle:
            text = handle.read()
    out["overlay"] = "PROPERTY sim/overlay 1" in text
    ters = []
    for m in re.finditer(r"^TERRAIN_DEF\s+(\S+)", text, re.M):
        out["defs"] += 1
        ref = m.group(1)
        if ref.startswith(("terrain/", "textures/")):
            out["pack_defs"] += 1
            if not ref.startswith(f"terrain/{tile}/"):
                out["problems"].append(f"DSF def outside the tile folder: {ref}")
            path = os.path.join(root, ref)
            if not os.path.isfile(path):
                out["problems"].append(f"DSF def missing on disk: {ref}")
            else:
                ters.append(path)
    for path in ters:
        out["ters_checked"] += 1
        with open(path, encoding="utf-8") as handle:
            body = handle.read()
        for m in _TER_REF.finditer(body):
            ref = m.group(1)
            if "/" not in ref:
                continue
            out["tex_refs"] += 1
            if not ref.startswith(f"../../textures/{tile}/"):
                out["problems"].append(f"{os.path.basename(path)}: {ref}")
            elif not os.path.isfile(os.path.normpath(
                    os.path.join(os.path.dirname(path), ref))):
                out["problems"].append(f"{os.path.basename(path)}: "
                                       f"missing {ref}")
    return out


def dsf_header(path: str) -> dict:
    """The binary checks of a DSF, with no DSFTool: ``XPLNEDSF`` magic,
    version 1, the MD5 footer over the rest of the file, the top-level
    atoms and the HEAD properties (``sim/west`` ... ``sim/overlay``)."""
    with open(path, "rb") as handle:
        data = handle.read()
    out = {"bytes": len(data), "magic_ok": data[:8] == b"XPLNEDSF",
           "version": int.from_bytes(data[8:12], "little"),
           "md5_ok": hashlib.md5(data[:-16]).digest() == data[-16:],
           "atoms": [], "properties": {}}
    at, end = 12, len(data) - 16
    while at + 8 <= end:
        name = data[at:at + 4][::-1].decode("ascii", "replace")
        size = int.from_bytes(data[at + 4:at + 8], "little")
        if size < 8:
            break
        out["atoms"].append(name)
        if name == "HEAD" and data[at + 8:at + 12][::-1] == b"PROP":
            psize = int.from_bytes(data[at + 12:at + 16], "little")
            words = data[at + 16:at + 8 + psize].split(b"\0")
            for k, v in zip(words[0::2], words[1::2]):
                out["properties"][k.decode()] = v.decode("utf-8", "replace")
        at += size
    return out


def _place_dir(staged: str, dest: str) -> None:
    """Hard-link a staged folder in as ``dest`` with one rename; an earlier
    copy of ``dest`` is renamed aside first (never deleted while X-Plane may
    map it) and removed after."""
    parent = os.path.dirname(dest)
    os.makedirs(parent, exist_ok=True)
    incoming = os.path.join(parent, f".{os.path.basename(dest)}.incoming")
    if os.path.exists(incoming):
        shutil.rmtree(incoming)
    shutil.copytree(staged, incoming, copy_function=_link_or_copy)
    old = None
    if os.path.exists(dest):
        old = os.path.join(parent, f".{os.path.basename(dest)}.old")
        if os.path.exists(old):
            shutil.rmtree(old)
        os.rename(dest, old)
    os.rename(incoming, dest)
    if old:
        shutil.rmtree(old, ignore_errors=True)


def swap_in(pack: str, staged: str, lat: int, lon: int) -> dict:
    """Put a staged real tile into the pack: its terrain and texture
    folders first (new names X-Plane has never seen), then the DSF over the
    placeholder in ONE ``os.replace`` — the only change X-Plane can see."""
    tile = tile_name(lat, lon)
    for sub in ("terrain", "textures"):
        _place_dir(os.path.join(staged, sub, tile),
                   os.path.join(pack, sub, tile))
    dest = os.path.join(pack, dsf_relpath(lat, lon))
    was_placeholder = is_placeholder(dest)
    partial = dest + ".partial"
    if os.path.exists(partial):
        os.remove(partial)
    _link_or_copy(os.path.join(staged, dsf_relpath(lat, lon)), partial)
    os.replace(partial, dest)
    return {"tile": tile, "dsf": dest, "was_placeholder": was_placeholder}


def swap_out(pack: str, lat: int, lon: int, tool: str) -> str:
    """Put the placeholder back over a tile's DSF (one rename).  Its
    terrain and texture folders stay: X-Plane may still map them."""
    return write_placeholder(pack, lat, lon, tool)


def tile_reach(lat: float, lon: float, tlat: int, tlon: int) -> dict:
    """Where a point stands from a tile: ``tiles`` = Chebyshev distance in
    whole tiles (0 inside, 1 in a neighbour) and ``km`` = ground distance
    to the tile's nearest edge (0 inside)."""
    here = (math.floor(lat), math.floor(lon))
    tiles = max(abs(here[0] - tlat), abs(here[1] - tlon))
    dlat = max(tlat - lat, 0.0, lat - (tlat + 1))
    dlon = max(tlon - lon, 0.0, lon - (tlon + 1))
    km = math.hypot(dlat, dlon * math.cos(math.radians(lat))) * _M_PER_DEG / 1000
    return {"tiles": tiles, "km": round(km, 1)}


#: X-Plane 12's DSF window, read off the CYXY recorder flight 2
#: (2026-11-10, 60°N; every .dsf open with the aircraft position): FOUR
#: columns centred on a tile boundary B (columns B-2 .. B+1) and THREE rows
#: (the aircraft's row +-1).  The window moves one column when the aircraft
#: is more than ``WINDOW_SHIFT`` degrees of longitude from B (four shifts
#: seen, all at 0.64-0.65).  A DSF is opened when its column enters.
WINDOW_SHIFT = 0.65


def xp_window(lat: float, lon: float, tlat: int, tlon: int) -> dict:
    """Is tile (tlat, tlon) in X-Plane's DSF window for an aircraft at
    (lat, lon), estimated with B = the nearest boundary (the history is
    unknown), and how far the aircraft is from the line where it would
    enter: ``{"in_window", "km_to_load"}``.  [measured at 60°N, flight 2;
    assumed elsewhere]"""
    centre = round(lon)
    cols = tlon >= centre - 2 and tlon <= centre + 1
    rows = abs(math.floor(lat) - tlat) <= 1
    cos_lat = math.cos(math.radians(lat))
    if tlon < centre - 2:              # west of the window: enters at T+2.35
        dlon = lon - (tlon + 3 - WINDOW_SHIFT)
    elif tlon > centre + 1:            # east: enters at T-0.35
        dlon = (tlon - 1 + WINDOW_SHIFT) - lon
    else:
        dlon = 0.0
    if tlat > math.floor(lat) + 1:
        dlat = (tlat - 1) - lat
    elif tlat < math.floor(lat) - 1:
        dlat = lat - (tlat + 2)
    else:
        dlat = 0.0
    km = max(max(dlon, 0.0) * cos_lat, max(dlat, 0.0)) * _M_PER_DEG / 1000
    return {"in_window": cols and rows, "km_to_load": round(km, 1)}


def ini_install(lines: list, pack_name: str = PACK_NAME) -> bool:
    """File the World pack's row into ``scenery_packs.ini`` lines (edited in
    place) as an ortho-group pack, through the app's own filing rule
    (``O4_Scenery_Packs.insert_new_packs``).  ``False`` when a row for it
    is already there (it is then enabled, never moved)."""
    import O4_Scenery_Packs as PACKS
    for i, line in enumerate(lines):
        if line.strip().rstrip("/").endswith("Custom Scenery/" + pack_name):
            lines[i] = f"SCENERY_PACK Custom Scenery/{pack_name}/"
            return False
    PACKS.insert_new_packs(lines, [pack_name],
                           lambda name: "ortho" if name == pack_name else None)
    return True


def ini_remove(lines: list, pack_name: str = PACK_NAME) -> int:
    """Drop the World pack's rows; returns how many."""
    keep = [line for line in lines
            if not line.strip().rstrip("/").endswith("Custom Scenery/" + pack_name)]
    gone = len(lines) - len(keep)
    lines[:] = keep
    return gone


def dsftool_path(engine_dir: str) -> str:
    """The engine checkout's bundled DSFTool for this platform."""
    sub = {"darwin": ("mac", "DSFTool"), "win32": ("win", "DSFTool.exe")}
    folder, exe = sub.get(os.sys.platform, ("lin", "DSFTool"))
    path = os.path.join(engine_dir, "Utils", folder, exe)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    return path
