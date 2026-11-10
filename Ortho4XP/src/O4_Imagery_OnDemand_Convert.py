"""Convert ONE built ortho tile to on-demand form: a lean copy X-Plane
flies on placeholders, whose full textures stay where they are (#1992
phase P1c; local-imagery-cache spec §3 placeholder mode, §5 index, §8).

The copy holds what X-Plane reads and nothing else:

* every ``textures/*.dds`` as a PLACEHOLDER under its own name: the
  source DDS's own ``placeholder_px`` level and the levels below it,
  re-headed (``O4_DDS_Tiers.tier_from_file``: no decode, no re-encode, a
  512 px tier reads ~175 KB of an 11 MB file).  A source with no such
  level (no mips) or already that small is copied whole;
* ``terrain/`` as it is (the ``.ter`` files' ``LOAD_CENTER`` and texture
  names do not change: X-Plane reads the smaller file's own header,
  spec §2.3), and the non-DDS textures a ``.ter`` names (water borders);
* every DSF 7z-compressed (``O4_DSF_Compress``: proven to decode to the
  source byte for byte); one that does not compress is copied as is;
* the tile's config files and its imagery manifest, which gains
  ``on_demand``, ``placeholder_px``, ``placeholder_zl`` and
  ``full_source`` (the folder whose ``textures/`` holds the full DDS: the
  lander lands from it while it is mounted, spec §4.4).

Left out: the build intermediates (``Data<tile>.*``), ``*.bak``, build
logs, step records, DSFTool ``.text`` dumps and ``.raw`` rasters left in
``Earth nav data``, and anything not listed above (:func:`plan_tile`
lists each with its size).

* :func:`plan_tile` -- what a conversion of a source folder writes and
  skips, with sizes, from headers and ``stat`` alone (the dry run).
* :func:`convert_tile` -- write the copy into a staging folder.  It is
  RESUMABLE: every texture lands whole (partial name + rename,
  ``O4_DDS_File.land``) and one already whole at its width is kept; a
  copy of matching size and time is kept; a DSF already proven is kept.
  The stamp (:data:`STAMP`) is written LAST, after the copy verifies
  complete: every texture a ``.ter`` names is a whole DDS, every DSF
  decodes to its source.
* :func:`is_converted` -- is a folder a finished (stamped) copy of a
  source.

The source is only ever READ.  Standard library only.
"""
from __future__ import annotations

import contextlib
import json
import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import O4_DDS_File as DDS
import O4_DDS_Tiers as TIERS
import O4_DSF_Compress as DSFC
import O4_Imagery_OnDemand_Budget as BUDGET

__all__ = ["DEFAULT_PX", "STAMP", "convert_tile", "is_converted",
           "plan_tile"]

#: Placeholder width of a converted texture.  512 px is the build's
#: placeholder (spec §3.3; owner 2026-11-10T06:26Z for converted tiles too).
DEFAULT_PX = 512
#: The record a finished copy carries (written last).
STAMP = ".ondemand_convert.json"
_STAMP_VERSION = 1
_NAV = "Earth nav data"
_TERRAIN, _TEXTURES = "terrain", "textures"
_JUNK = (".DS_Store",)
_KEEP_TOP_SUFFIXES = (".cfg",)
#: Besides the DSF, what X-Plane reads in ``Earth nav data`` (apt.dat ...);
#: a build's DSFTool text dumps and raw rasters there are left out.
_NAV_KEEP = (".dat",)


@dataclass
class _TilePlan:
    """What converting ``source`` writes (relative paths, source bytes)
    and leaves out."""
    source: str
    placeholder_px: int
    textures: list = field(default_factory=list)  # (rel, src bytes, out bytes)
    copies: list = field(default_factory=list)    # (rel, bytes)
    dsfs: list = field(default_factory=list)      # (rel, bytes, already 7z)
    skipped: list = field(default_factory=list)   # (rel, bytes)
    whole_copies: int = 0       # textures copied whole (no such mip level)
    manifest: "str | None" = None                 # source imagery manifest

    def total(self, which: str) -> int:
        """Bytes of ``textures`` (placeholders written), ``source_textures``,
        ``copies``, ``dsfs`` (source) or ``skipped``."""
        if which == "textures":
            return sum(out for (_r, _s, out) in self.textures)
        if which == "source_textures":
            return sum(src for (_r, src, _o) in self.textures)
        return sum(item[1] for item in getattr(self, which))


#: A file's size, 0 when it is gone (shared with the ortho budget).
_size = BUDGET.file_size


def _tree_bytes(path: str) -> int:
    if not os.path.isdir(path) or os.path.islink(path):
        return _size(path)
    total = 0
    for root, _dirs, files in os.walk(path):
        total += sum(_size(os.path.join(root, f)) for f in files)
    return total


def _ter_textures(terrain_dir: str) -> set:
    """Base names of every ``../textures/`` file a ``.ter`` names."""
    named = set()
    with contextlib.suppress(OSError):
        for item in os.scandir(terrain_dir):
            if not item.name.endswith(".ter"):
                continue
            with open(item.path, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    for word in line.split():
                        if "textures/" in word.replace("\\", "/"):
                            named.add(os.path.basename(
                                word.replace("\\", "/")))
    return named


def _placeholder_size(path: str, px: int, src_bytes: int) -> "tuple[int, bool]":
    """(bytes the placeholder of ``path`` will be, cut from its levels?)."""
    span = TIERS.tier_span(path, px)
    if span is None:
        return src_bytes, False
    return DDS.HEADER_BYTES + sum(span[2]), True


def _plan_textures(plan: _TilePlan, folder: str, named: set) -> None:
    for item in sorted(os.scandir(folder), key=lambda e: e.name):
        rel = f"{_TEXTURES}/{item.name}"
        if not item.is_file() or item.name in _JUNK:
            continue
        size = item.stat().st_size
        if item.name.endswith(".dds") and not DDS.is_partial_name(item.name):
            out, cut = _placeholder_size(item.path, plan.placeholder_px, size)
            plan.textures.append((rel, size, out))
            plan.whole_copies += 0 if cut else 1
        elif item.name in named:
            plan.copies.append((rel, size))
        else:
            plan.skipped.append((rel, size))


def _plan_tree(plan: _TilePlan, folder: str, rel_root: str) -> None:
    for root, _dirs, files in os.walk(folder):
        for name in sorted(files):
            path = os.path.join(root, name)
            rel = os.path.relpath(path, plan.source).replace(os.sep, "/")
            size = _size(path)
            if name in _JUNK or name.endswith(".bak"):
                plan.skipped.append((rel, size))
            elif rel_root == _NAV and name.endswith(".dsf"):
                plan.dsfs.append((rel, size, DSFC.is_compressed(path)))
            elif rel_root == _NAV and not name.endswith(_NAV_KEEP):
                plan.skipped.append((rel, size))   # DSFTool .text, .raw
            else:
                plan.copies.append((rel, size))


def plan_tile(source: str, placeholder_px: int = DEFAULT_PX) -> _TilePlan:
    """What :func:`convert_tile` writes from ``source`` and leaves out,
    from headers and ``stat`` only (reads no pixel)."""
    source = os.path.realpath(source)
    plan = _TilePlan(source=source, placeholder_px=int(placeholder_px))
    named = _ter_textures(os.path.join(source, _TERRAIN))
    for item in sorted(os.scandir(source), key=lambda e: e.name):
        if item.is_dir():
            if item.name == _TEXTURES:
                _plan_textures(plan, item.path, named)
            elif item.name in (_TERRAIN, _NAV):
                _plan_tree(plan, item.path, item.name)
            else:
                plan.skipped.append((item.name, _tree_bytes(item.path)))
        elif item.name.endswith("_imagery.json"):
            plan.manifest = item.path
        elif item.name.endswith(_KEEP_TOP_SUFFIXES):
            plan.copies.append((item.name, item.stat().st_size))
        else:
            plan.skipped.append((item.name, _size(item.path)))
    return plan


# ------------------------------------------------------------- the copy


def _placeholder(plan: _TilePlan, rel: str, staged: str) -> int:
    """Land one texture's placeholder in ``staged``; bytes written (0 when
    a whole one of the right width is already there)."""
    src = os.path.join(plan.source, rel)
    dest = os.path.join(staged, rel)
    if DDS.is_whole(dest):
        have = TIERS.texture_header(dest)
        if have is not None and (have[0] == plan.placeholder_px
                                 or _size(dest) == _size(src)):
            return 0
    data = TIERS.tier_from_file(src, plan.placeholder_px)
    partial = DDS.partial_name(dest)
    if data is not None:
        with open(partial, "wb") as handle:
            handle.write(data)
    else:
        shutil.copyfile(src, partial)
    if not DDS.land(partial, dest):
        raise OSError(f"{rel}: the placeholder did not land whole")
    return _size(dest)


def _copy(plan: _TilePlan, rel: str, staged: str) -> int:
    """Copy one file as it is (kept when size and mtime match)."""
    src, dest = os.path.join(plan.source, rel), os.path.join(staged, rel)
    with contextlib.suppress(OSError):
        a, b = os.stat(src), os.stat(dest)
        if a.st_size == b.st_size and int(a.st_mtime) == int(b.st_mtime):
            return 0
    temp = f"{dest}.{os.getpid()}.part"
    shutil.copy2(src, temp)
    os.replace(temp, dest)
    return _size(dest)


def _dsf(plan: _TilePlan, rel: str, staged: str, threads: int) -> "tuple[int, bool]":
    """(bytes written, compressed?) of one DSF; a copy already proven to
    decode to the source is kept."""
    src, dest = os.path.join(plan.source, rel), os.path.join(staged, rel)
    if os.path.isfile(dest) and DSFC.decodes_to(dest, src):
        return 0, DSFC.is_compressed(dest)
    if DSFC.is_compressed(src):
        return _copy(plan, rel, staged), True
    try:
        DSFC.compress(src, dest, threads=threads)
        return _size(dest), True
    except DSFC.CompressError:
        return _copy(plan, rel, staged), False


def _zoom_of(plan: _TilePlan, manifest: dict) -> "tuple[str | None, int | None]":
    if manifest.get("provider") and manifest.get("zoomlevel"):
        return manifest["provider"], int(manifest["zoomlevel"])
    import O4_Custom_Scenery as CS
    found = CS.imagery_from_file_names(
        os.path.basename(rel) for (rel, _s, _o) in plan.textures)
    return found if found else (None, None)


def _write_manifest(plan: _TilePlan, staged: str, tile: str,
                    full_source: str) -> None:
    manifest = {}
    if plan.manifest:
        with contextlib.suppress(OSError, ValueError):
            with open(plan.manifest, encoding="utf-8") as handle:
                manifest = json.load(handle) or {}
    provider, zoom = _zoom_of(plan, manifest)
    drop = (TIERS.FULL_WIDTH // plan.placeholder_px).bit_length() - 1
    manifest.update({
        "on_demand": True, "pinned": bool(manifest.get("pinned", False)),
        "placeholder_px": plan.placeholder_px,
        "placeholder_zl": (zoom - drop) if zoom else None,
        "full_source": full_source, "converted_from": plan.source,
        "provider": provider, "zoomlevel": zoom,
    })
    path = os.path.join(staged, f"Ortho4XP_{tile}_imagery.json")
    temp = f"{path}.{os.getpid()}.part"
    with open(temp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
    os.replace(temp, path)


def convert_tile(plan: _TilePlan, staged: str, tile: str, *,
                 full_source: "str | None" = None, threads: int = 8) -> dict:
    """Write ``plan``'s copy into ``staged`` (created; resumable), verify
    it, and stamp it.  ``tile`` is ``+60-136``; ``full_source`` the folder
    the manifest names as the full textures' home (default: the source).
    Returns ``{"bytes_written", "seconds", "textures", "whole_copies",
    "dsf_compressed", "problems"}``; the stamp is written only when
    ``problems`` is empty."""
    started = time.monotonic()
    for rel in {os.path.dirname(r) for (r, *_x) in
                plan.textures + plan.copies + plan.dsfs}:
        os.makedirs(os.path.join(staged, rel), exist_ok=True)
    os.makedirs(os.path.join(staged, _TEXTURES), exist_ok=True)
    with ThreadPoolExecutor(max_workers=max(1, threads)) as pool:
        written = sum(pool.map(lambda r: _placeholder(plan, r[0], staged),
                               plan.textures))
    written += sum(_copy(plan, rel, staged) for (rel, _s) in plan.copies)
    compressed = 0
    for rel, _s, _z in plan.dsfs:
        size, packed = _dsf(plan, rel, staged, threads=2)
        written += size
        compressed += int(packed)
    _write_manifest(plan, staged, tile, full_source or plan.source)
    problems = _verify(plan, staged)
    if not problems:
        _stamp(plan, staged)
    return {"bytes_written": written,
            "seconds": round(time.monotonic() - started, 2),
            "textures": len(plan.textures), "whole_copies": plan.whole_copies,
            "dsf_compressed": compressed, "problems": problems}


def _verify(plan: _TilePlan, staged: str) -> "list[str]":
    """What is wrong with the copy in ``staged`` (empty: complete): a
    texture missing or not whole, a ``.ter``-named texture missing, a DSF
    that does not decode to its source."""
    problems = []
    for rel, _s, _o in plan.textures:
        if not DDS.is_whole(os.path.join(staged, rel)):
            problems.append(f"texture not whole: {rel}")
    for name in sorted(_ter_textures(os.path.join(staged, _TERRAIN))):
        if not os.path.isfile(os.path.join(staged, _TEXTURES, name)):
            problems.append(f"a .ter names a missing texture: {name}")
    for rel, _s, _z in plan.dsfs:
        if not DSFC.decodes_to(os.path.join(staged, rel),
                               os.path.join(plan.source, rel)):
            problems.append(f"DSF does not decode to its source: {rel}")
    return problems


def _stamp(plan: _TilePlan, staged: str) -> None:
    """Write the finished copy's record (last step of a conversion)."""
    record = {"version": _STAMP_VERSION, "source": plan.source,
              "placeholder_px": plan.placeholder_px,
              "textures": len(plan.textures), "dsfs": len(plan.dsfs),
              "converted_at": time.time()}
    path = os.path.join(staged, STAMP)
    temp = f"{path}.{os.getpid()}.part"
    with open(temp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(record, handle, indent=2, sort_keys=True)
    os.replace(temp, path)


def _read_stamp(folder: str) -> "dict | None":
    """The stamp of a finished copy in ``folder``, or ``None``."""
    try:
        with open(os.path.join(folder, STAMP), encoding="utf-8") as handle:
            record = json.load(handle)
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) else None


def is_converted(folder: str, source: "str | None" = None,
                 placeholder_px: "int | None" = None) -> bool:
    """Is ``folder`` a finished copy (of ``source``, at ``placeholder_px``,
    when given)?"""
    record = _read_stamp(folder)
    if record is None or record.get("version") != _STAMP_VERSION:
        return False
    if source is not None and record.get("source") != os.path.realpath(source):
        return False
    return placeholder_px is None or record.get("placeholder_px") == int(
        placeholder_px)
