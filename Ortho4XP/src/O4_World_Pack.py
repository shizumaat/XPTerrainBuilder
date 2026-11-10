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
(:func:`swap_in`); X-Plane opens it when the tile's column loads, with no
reload (H1-H3, flown on the CYYR World pack flight, flight manager /
World spec 2026-11-10 §2.1).

Every DSF in the pack says what it is through ``sim/creation_agent``
(:func:`kind_of`, spec §18): a placeholder (:data:`PLACEHOLDER_AGENT`) is
NOT a tile; a drape, light or full tile is a tile of that kind (the stage
step stamps ``[world <kind>]`` onto the builder's agent, :func:`stamp`).

Publishing a build (spec §7.3): :func:`stage_tile` lays the build folder
out in the pack's shape under a staging folder -- textures hard-linked,
``.ter`` references and DSF definitions given the tile subfolder by a
BINARY rewrite (``O4_DSF_Binary``; no DSFTool) -- :func:`verify_tile`
checks it, :func:`publish` swaps it in unless X-Plane may hold the tile
(then it stays staged, rule S3/S4; :func:`swap_staged` retries).

Placeholders are written in pure Python (:func:`write_placeholder`,
:func:`write_placeholders`): the bytes DSFTool writes, verified against
DSFTool in a twin.  DSFTool is used here only by the drape writer
(``O4_World_Drape``) through :func:`dsftool_path`.

Standard library plus ``O4_DSF_Binary`` / ``O4_DSF_Header`` and
``O4_Scenery_Packs`` (all stdlib-only), so the module still runs from a kit
copy beside the engine checkout.
"""
from __future__ import annotations

import hashlib
import math
import os
import re
import shutil
import subprocess
from typing import Callable, Iterator

import O4_DSF_Binary as DSFB

__all__ = [
    "PACK_NAME", "PLACEHOLDER_AGENT", "KINDS", "PLACEHOLDER_MAX_BYTES",
    "STAGING_DIR", "tile_name", "parse_tile",
    "dsf_relpath", "placeholder_text", "write_placeholder",
    "write_placeholders", "is_placeholder", "kind_of", "stamp", "pack_dsfs",
    "real_tiles", "holds_tile", "world_tiles", "block_tiles", "rewrite_ter", "pack_def",
    "rewrite_dsf_text", "relayout_tile", "verify_tile", "stage_tile",
    "publish", "swap_staged", "swap_in", "swap_out", "ini_install",
    "ini_remove", "dsftool_path", "dsf_header",
]

PACK_NAME = "zXPTerrainBuilder World"
#: ``sim/creation_agent`` of a placeholder: how :func:`is_placeholder` knows one.
PLACEHOLDER_AGENT = "XPTerrainBuilder world placeholder"
#: The kinds of tile the pack holds (spec §3); ``placeholder`` is no tile.
KINDS = ("placeholder", "drape", "light", "full")
#: A placeholder is 328 bytes; a DSF larger than this is never one, so a
#: scan reads the head only of files this small.
PLACEHOLDER_MAX_BYTES = 4096
#: Staged tiles, under the data folder (never inside Custom Scenery).
STAGING_DIR = "World_staging"
_KIND_RE = re.compile(r"world (placeholder|drape|light|full)\b")
_STAMP_RE = re.compile(r"\s*\[world (?:drape|light|full)\]$")


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
                          encoding="utf-8", errors="replace", timeout=timeout)
    if done.returncode != 0:
        raise RuntimeError(f"DSFTool {' '.join(args[:1])} failed "
                           f"(exit {done.returncode}): {done.stdout[-400:]}"
                           f"{done.stderr[-400:]}")
    return done.stdout


def _write_atomic(dest: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    partial = dest + ".partial"
    with open(partial, "wb") as handle:
        handle.write(data)
    os.replace(partial, dest)


def write_placeholder(pack: str, lat: int, lon: int) -> str:
    """Write the placeholder DSF of a tile into ``pack`` (the bytes DSFTool
    writes for :func:`placeholder_text`, ``O4_DSF_Binary``); returns its
    path.  Written beside its name and renamed over it."""
    dest = os.path.join(pack, dsf_relpath(lat, lon))
    _write_atomic(dest, DSFB.placeholder_bytes(lat, lon, PLACEHOLDER_AGENT))
    return dest


def write_placeholders(pack: str, tiles) -> dict:
    """A placeholder for every tile of ``tiles`` that has no DSF in
    ``pack`` yet (a tile of ours is never overwritten).  Returns
    ``{"written", "kept"}``."""
    out = {"written": 0, "kept": 0}
    for lat, lon in tiles:
        if os.path.exists(os.path.join(pack, dsf_relpath(lat, lon))):
            out["kept"] += 1
            continue
        write_placeholder(pack, lat, lon)
        out["written"] += 1
    return out


def is_placeholder(path: str, size: int | None = None) -> bool:
    """Whether the DSF at ``path`` is one of our placeholders (its header
    carries :data:`PLACEHOLDER_AGENT`; a real tile never does).  ``size``
    (when the caller has it from a listing) skips the read of any file
    larger than :data:`PLACEHOLDER_MAX_BYTES`."""
    if size is not None and size > PLACEHOLDER_MAX_BYTES:
        return False
    try:
        with open(path, "rb") as handle:
            head = handle.read(PLACEHOLDER_MAX_BYTES)
    except OSError:
        return False
    return PLACEHOLDER_AGENT.encode() in head


def kind_of(path: str) -> str | None:
    """What a World-pack DSF is: ``placeholder``, ``drape``, ``light`` or
    ``full`` (its ``sim/creation_agent``; a DSF of ours with no stamp is a
    ``full`` tile); ``None`` when there is no readable DSF."""
    import O4_DSF_Header as DSFH
    if is_placeholder(path):
        return "placeholder"
    props = DSFH.dsf_properties(path)
    if props is None:
        return None
    m = _KIND_RE.search(props.get("sim/creation_agent", ""))
    return m.group(1) if m else "full"


def stamp(agent: str, kind: str) -> str:
    """``agent`` with the World kind ``[world <kind>]`` at its end (an
    earlier stamp replaced)."""
    if kind not in KINDS[1:]:
        raise ValueError(f"not a tile kind: {kind!r}")
    return f"{_STAMP_RE.sub('', agent).strip()} [world {kind}]".strip()


def pack_dsfs(pack: str) -> Iterator[tuple[tuple[int, int], str, int]]:
    """``((lat, lon), path, bytes)`` of every tile DSF in ``pack``: two
    directory levels, one ``stat`` per file (the size)."""
    nav = os.path.join(pack, "Earth nav data")
    try:
        blocks = sorted(os.listdir(nav))
    except OSError:
        return
    for block in blocks:
        try:
            entries = list(os.scandir(os.path.join(nav, block)))
        except OSError:
            continue
        for entry in entries:
            name = entry.name
            if not name.lower().endswith(".dsf"):
                continue
            try:
                key = parse_tile(name[:-4])
                size = entry.stat().st_size
            except (ValueError, OSError):
                continue
            yield key, entry.path, size


def real_tiles(pack: str) -> dict:
    """``{(lat, lon): dsf path}`` of the tiles in ``pack`` that are tiles
    (every DSF but a placeholder): what a scan of installed scenery sees.
    Reads the head of small files only."""
    return {key: path for key, path, size in pack_dsfs(pack)
            if not is_placeholder(path, size)}


def holds_tile(scenery_dir: str, lat: int, lon: int) -> bool:
    """Does the World pack in Custom Scenery folder ``scenery_dir`` hold a
    tile (not a placeholder) for ``(lat, lon)``?"""
    if not scenery_dir:
        return False
    dsf = os.path.join(scenery_dir, PACK_NAME, dsf_relpath(lat, lon))
    return os.path.isfile(dsf) and not is_placeholder(dsf)


def world_tiles(pack: str) -> dict:
    """``{(lat, lon): kind}`` of every DSF in ``pack`` (:func:`kind_of`;
    placeholders by size and head only)."""
    out = {}
    for key, path, size in pack_dsfs(pack):
        if is_placeholder(path, size):
            out[key] = "placeholder"
        else:
            out[key] = kind_of(path) or "full"
    return out


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


_DEF_PATH = re.compile(r"^((?:TERRAIN|OBJECT|POLYGON|NETWORK)_DEF\s+)(\S+)",
                       re.M)
#: The DEFN tables whose strings name files (:func:`pack_def` applies).
_DEF_TABLES = ("TERT", "OBJT", "POLY", "NETW")


def pack_def(ref: str, tile: str) -> str:
    """A definition path of a tile moved into the World pack: under the
    pack's ``terrain/`` or ``textures/`` it gains the tile subfolder;
    library paths (``lib/...``) and built-ins (``terrain_Water``) are left
    alone, and so is a path already in the tile's folder."""
    for top in ("terrain/", "textures/"):
        if ref.startswith(top) and not ref.startswith(f"{top}{tile}/"):
            return f"{top}{tile}/{ref[len(top):]}"
    return ref


def rewrite_dsf_text(text: str, tile: str) -> tuple[str, int]:
    """DSFTool text of a tile moved into the World pack, each definition
    through :func:`pack_def` -- the text oracle of the binary rewrite in
    :func:`relayout_tile` (the twin compares them)."""
    count = 0

    def one(m: re.Match) -> str:
        nonlocal count
        new = pack_def(m.group(2), tile)
        count += new != m.group(2)
        return m.group(1) + new
    return _DEF_PATH.sub(one, text), count


def _link_or_copy(src: str, dst: str) -> None:
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def relayout_tile(tile_dir: str, out_dir: str, lat: int, lon: int,
                  kind: str = "full") -> dict:
    """Lay a built tile folder out as World-pack files in ``out_dir`` (a
    staging folder with the pack's own shape).  Textures are hard-linked
    (copied across volumes); ``.ter`` references are rewritten; the DSF's
    definitions are given the tile subfolder and its agent the ``kind``
    stamp by a binary rewrite (a 7z DSF is read decompressed).  Returns
    counts.  ``out_dir`` must not exist yet."""
    import O4_DSF_Header as DSFH
    tile = tile_name(lat, lon)
    if os.path.exists(out_dir):
        raise FileExistsError(out_dir)
    src_dsf = os.path.join(tile_dir, dsf_relpath(lat, lon))
    data = DSFH.dsf_bytes(src_dsf)
    if not data:
        raise ValueError(f"{src_dsf}: not a readable DSF")
    ter_out = os.path.join(out_dir, "terrain", tile)
    tex_out = os.path.join(out_dir, "textures", tile)
    os.makedirs(ter_out)
    os.makedirs(tex_out)
    counts = {"ter": 0, "ter_refs": 0, "textures": 0, "dsf_defs": 0}
    ter_in = os.path.join(tile_dir, "terrain")
    for name in sorted(os.listdir(ter_in) if os.path.isdir(ter_in) else ()):
        if not name.endswith(".ter"):
            continue
        with open(os.path.join(ter_in, name), encoding="utf-8") as handle:
            text, n = rewrite_ter(handle.read(), tile)
        with open(os.path.join(ter_out, name), "w", encoding="utf-8",
                  newline="\n") as handle:
            handle.write(text)
        counts["ter"] += 1
        counts["ter_refs"] += n
    tex_in = os.path.join(tile_dir, "textures")
    for name in sorted(os.listdir(tex_in) if os.path.isdir(tex_in) else ()):
        if name.lower().endswith((".dds", ".png")) and not name.startswith("."):
            _link_or_copy(os.path.join(tex_in, name), os.path.join(tex_out, name))
            counts["textures"] += 1

    def defs(table: str, ref: str) -> str:
        if table not in _DEF_TABLES:
            return ref
        new = pack_def(ref, tile)
        counts["dsf_defs"] += new != ref
        return new

    def props(pairs: list) -> list:
        out = [(k, stamp(v, kind) if k == "sim/creation_agent" else v)
               for k, v in pairs]
        if not any(k == "sim/creation_agent" for k, _v in out):
            out.append(("sim/creation_agent", stamp("", kind)))
        return out
    _write_atomic(os.path.join(out_dir, dsf_relpath(lat, lon)),
                  DSFB.rewrite(data, props=props, defs=defs))
    return counts


_TER_REF = re.compile(r"^\s*\S*TEX\S*\s+(\S+)", re.M)


def verify_tile(root: str, lat: int, lon: int) -> dict:
    """Read the tile's DSF definitions (binary, ``O4_DSF_Binary``) and
    check that every ``terrain/`` definition names a ``.ter`` under
    ``root`` in the tile's folder and every texture a ``.ter`` names
    exists.  ``root`` is the pack or a staging folder of the same shape.
    Returns counts, ``overlay``, ``kind`` and ``problems``."""
    import O4_DSF_Header as DSFH
    tile = tile_name(lat, lon)
    out = {"tile": tile, "defs": 0, "pack_defs": 0, "ters_checked": 0,
           "tex_refs": 0, "overlay": None, "kind": None, "problems": []}
    path = os.path.join(root, dsf_relpath(lat, lon))
    data = DSFH.dsf_bytes(path)
    if not data:
        out["problems"].append(f"no readable DSF: {dsf_relpath(lat, lon)}")
        return out
    try:
        props = dict(DSFB.properties(data))
        terrain = DSFB.definitions(data).get("TERT", [])
    except ValueError as error:
        out["problems"].append(f"DSF does not parse: {error}")
        return out
    if not DSFB.dsf_md5_ok(data):
        out["problems"].append("DSF MD5 footer does not match")
    out["overlay"] = props.get("sim/overlay") == "1"
    out["kind"] = kind_of(path)
    ters = []
    for ref in terrain:
        out["defs"] += 1
        if ref.startswith(("terrain/", "textures/")):
            out["pack_defs"] += 1
            if not ref.startswith(f"terrain/{tile}/"):
                out["problems"].append(f"DSF def outside the tile folder: {ref}")
            ter = os.path.join(root, ref)
            if not os.path.isfile(ter):
                out["problems"].append(f"DSF def missing on disk: {ref}")
            else:
                ters.append(ter)
    for ter in ters:
        out["ters_checked"] += 1
        with open(ter, encoding="utf-8") as handle:
            body = handle.read()
        for m in _TER_REF.finditer(body):
            ref = m.group(1)
            if "/" not in ref:
                continue
            out["tex_refs"] += 1
            if not ref.startswith(f"../../textures/{tile}/"):
                out["problems"].append(f"{os.path.basename(ter)}: {ref}")
            elif not os.path.isfile(os.path.normpath(
                    os.path.join(os.path.dirname(ter), ref))):
                out["problems"].append(f"{os.path.basename(ter)}: "
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
            for k, v in zip(words[0::2], words[1::2], strict=False):
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
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    partial = dest + ".partial"
    if os.path.exists(partial):
        os.remove(partial)
    _link_or_copy(os.path.join(staged, dsf_relpath(lat, lon)), partial)
    os.replace(partial, dest)
    return {"tile": tile, "dsf": dest, "was_placeholder": was_placeholder}


def swap_out(pack: str, lat: int, lon: int) -> str:
    """Put the placeholder back over a tile's DSF (one rename).  Its
    terrain and texture folders stay: X-Plane may still map them."""
    return write_placeholder(pack, lat, lon)


def stage_tile(build_dir: str, staging_root: str, lat: int, lon: int,
               kind: str = "full") -> dict:
    """Stage a built tile for the pack (spec §7.3 steps 2-3): an earlier
    staging of it is replaced, the tile laid out by :func:`relayout_tile`
    in ``<staging_root>/<tile>/`` and checked by :func:`verify_tile`.
    Returns ``{"staged", "counts", "problems"}``."""
    staged = os.path.join(staging_root, tile_name(lat, lon))
    if os.path.exists(staged):
        shutil.rmtree(staged)
    os.makedirs(staging_root, exist_ok=True)
    counts = relayout_tile(build_dir, staged, lat, lon, kind)
    check = verify_tile(staged, lat, lon)
    return {"staged": staged, "counts": counts, "problems": check["problems"]}


def _swap_staged_tile(pack: str, staged: str, lat: int, lon: int) -> dict:
    res = swap_in(pack, staged, lat, lon)
    shutil.rmtree(staged, ignore_errors=True)
    return res


def publish(pack: str, build_dir: str, lat: int, lon: int, *,
            staging_root: str, kind: str = "full",
            loaded: Callable[[int, int], bool] = lambda lat, lon: False
            ) -> dict:
    """Stage, verify and swap a built tile into ``pack`` (spec §7.3, rules
    S1-S4).  Nothing in the pack changes unless the staged tile verifies
    (S1); a tile ``loaded(lat, lon)`` says X-Plane may hold stays staged
    (S3/S4) for :func:`swap_staged`.  Returns ``{"tile", "state"
    ("swapped" | "staged" | "failed"), "problems", "counts"}``."""
    tile = tile_name(lat, lon)
    try:
        done = stage_tile(build_dir, staging_root, lat, lon, kind)
    except (OSError, ValueError) as error:
        return {"tile": tile, "state": "failed", "problems": [str(error)],
                "counts": {}}
    out = {"tile": tile, "problems": done["problems"], "counts": done["counts"]}
    if done["problems"]:
        shutil.rmtree(done["staged"], ignore_errors=True)
        return {**out, "state": "failed"}
    if loaded(lat, lon):
        return {**out, "state": "staged"}
    _swap_staged_tile(pack, done["staged"], lat, lon)
    return {**out, "state": "swapped"}


def swap_staged(pack: str, staging_root: str,
                loaded: Callable[[int, int], bool] = lambda lat, lon: False
                ) -> list:
    """Swap in every staged tile ``loaded`` now allows; the tile names
    swapped."""
    done = []
    try:
        names = sorted(os.listdir(staging_root))
    except OSError:
        return done
    for name in names:
        try:
            lat, lon = parse_tile(name)
        except ValueError:
            continue
        staged = os.path.join(staging_root, name)
        if (os.path.isfile(os.path.join(staged, dsf_relpath(lat, lon)))
                and not loaded(lat, lon)):
            _swap_staged_tile(pack, staged, lat, lon)
            done.append(name)
    return done


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
