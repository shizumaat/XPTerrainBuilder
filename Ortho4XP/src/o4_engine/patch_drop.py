"""Install patch files dropped on the app (#1979): the map window, the
app icon, or the launch arguments.

Both apps hand the dropped paths to the same two functions — the Mac app
through the engine commands ``patch_drop_plan`` and ``patch_drop_install``
(capability ``patch_drop``), the Qt window in process:

* :func:`patch_drop_plan` reads what was dropped and says, for each patch,
  its airport, its tile and where it goes, and whether it replaces a file
  already there.  Nothing is written.
* :func:`patch_drop_install` makes the same plan and installs it.

WHAT IS RECOGNISED.  A ``*.patch.osm`` file, a folder searched for them
(recursively), or a ``.zip`` holding them.  Each patch carries its
companion files from the same folder (the patch family of
``O4_Unpatched_Airports.PATCH_FAMILY`` for an auto patch, the ``.axes.json``
sidecar for any patch).  Anything else is listed as skipped with the
reason; a drop with no patch at all is refused with one sentence.

WHERE IT GOES.  The airport is the patch header's ``o4_icao``, else the
file name's (``O4_File_Names.patch_file_icao``); the tile is the header's
``o4_dsf_tiles`` when it names one tile the patch lies in, else the tile
under the centre of the patch's nodes.  The folder is the tile's
``O4_File_Names.patch_dir`` — the one the build reads and writes — made
when missing.  A file named for another airport than its header says is
installed as ``<ICAO>_<name>`` so the build applies it to that airport.

NOTHING IS OVERWRITTEN.  A file already at the destination is set aside
first as ``….disabled`` (``O4_Custom_Patches.set_aside``, the rename "Use
auto patch" makes); an identical one is skipped.  The tile's next build
applies the patch.
"""
from __future__ import annotations

import filecmp
import math
import os
import shutil
import tempfile
import zipfile

import O4_Custom_Patches as CUSTOM
import O4_File_Names as FNAMES
import O4_Unpatched_Airports as UNPATCHED

from . import patch_file as PF

__all__ = ["patch_drop_plan", "patch_drop_install"]

#: An archive larger than this once unpacked is refused (patches are
#: megabytes; this bounds a zip bomb).
_ZIP_LIMIT_BYTES = 2 << 30


def _hidden(name: str) -> bool:
    return name.startswith(".") or name == "__MACOSX"


def _patches_under(folder: str) -> list[str]:
    """Every ``*.patch.osm`` below *folder*, sorted; hidden folders and
    files (``.DS_Store``, ``__MACOSX``) are not searched."""
    found = []
    for root, dirs, files in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if not _hidden(d))
        found += [os.path.join(root, f) for f in sorted(files)
                  if f.endswith(FNAMES.PATCH_SUFFIX) and not _hidden(f)]
    return found


def _unpack(archive: str, into: str) -> None:
    """Extract *archive* into *into*, refusing names that leave it."""
    with zipfile.ZipFile(archive) as zf:
        members = zf.infolist()
        if sum(m.file_size for m in members) > _ZIP_LIMIT_BYTES:
            raise ValueError("%s is too large to be a patch archive"
                             % os.path.basename(archive))
        root = os.path.realpath(into)
        for m in members:
            target = os.path.realpath(os.path.join(into, m.filename))
            if os.path.commonpath([root, target]) != root:
                raise ValueError("%s holds a file outside its own folder "
                                 "(%s); it is not installed"
                                 % (os.path.basename(archive), m.filename))
        zf.extractall(into)


def _tile_of(lat: float, lon: float) -> tuple[int, int]:
    return math.floor(lat), math.floor(lon)


def _header_tile(doc: PF.PatchFile, bbox) -> tuple[int, int] | None:
    """The header's one DSF tile (``o4_dsf_tiles='39,-107'``), when the
    patch's nodes touch it (or it has none)."""
    tiles = [t for t in doc.header.get("o4_dsf_tiles", "").split(";") if t]
    if len(tiles) != 1:
        return None
    try:
        lat, lon = (int(v) for v in tiles[0].split(","))
    except ValueError:
        return None
    if bbox is not None and not (bbox[0] < lat + 1 and bbox[2] >= lat
                                 and bbox[1] < lon + 1 and bbox[3] >= lon):
        return None
    return lat, lon


def _where(doc: PF.PatchFile) -> tuple[tuple[int, int] | None, str]:
    """``((lat, lon), found_by)`` of the tile the patch belongs to."""
    bbox = doc.bbox()
    tile = _header_tile(doc, bbox)
    if tile is not None:
        return tile, "header"
    if bbox is None:
        return None, ""
    return _tile_of((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2), "geometry"


def _icao(doc: PF.PatchFile, name: str) -> str:
    header = (doc.header.get("o4_icao") or "").strip().upper()
    return header or (FNAMES.patch_file_icao(name) or "")


def _companions(source: str, icao: str) -> list[str]:
    """The files that travel with *source*, from its own folder."""
    folder, name = os.path.split(source)
    out = [source + ".axes.json"]
    if name == FNAMES.auto_patch_name(icao):
        out += UNPATCHED.airport_patch_family(folder, icao)
    seen, keep = {source}, []
    for path in out:
        if path not in seen and os.path.isfile(path):
            seen.add(path)
            keep.append(path)
    return keep


def _target_name(name: str, icao: str) -> str:
    """The installed name: the dropped one, or ``<ICAO>_<name>`` when the
    name would be read as another airport's patch."""
    return name if FNAMES.patch_file_icao(name) == icao else "%s_%s" % (icao, name)


def _same(a: str, b: str) -> bool:
    try:
        return os.path.samefile(a, b) or filecmp.cmp(a, b, shallow=False)
    except OSError:
        return False


def _row(source: str, shown: str) -> dict:
    """One patch's plan row; ``{"skip": reason}`` when it cannot go."""
    name = os.path.basename(source)
    try:
        doc = PF.read_patch(source)
    except ValueError as error:
        return {"source": shown, "skip": str(error)}
    icao = _icao(doc, name)
    if not icao:
        return {"source": shown, "skip": "%s names no airport" % name}
    tile, found_by = _where(doc)
    if tile is None:
        return {"source": shown, "skip": "%s has no header tile and no "
                "nodes to place it by" % name}
    directory = FNAMES.patch_dir(*tile)
    target = os.path.join(directory, _target_name(name, icao))
    files = [(source, target)] + [
        (c, os.path.join(directory, os.path.basename(c).replace(
            name, os.path.basename(target), 1))) for c in _companions(source, icao)]
    if all(os.path.isfile(t) and _same(s, t) for s, t in files):
        return {"source": shown, "skip": "%s is already installed in tile %s"
                % (name, FNAMES.short_latlon(*tile))}
    return {"source": shown, "name": name, "icao": icao,
            "tile": FNAMES.short_latlon(*tile), "found_by": found_by,
            "destination": target,
            "replaces": os.path.isfile(target),
            "companions": [os.path.basename(t) for _s, t in files[1:]],
            "_files": files}


def _gather(paths, scratch: str) -> tuple[list[tuple[str, str]], list[dict]]:
    """``([(patch path, shown as)], skipped)`` of the dropped *paths*."""
    found, skipped = [], []
    for n, path in enumerate(str(p) for p in (paths or ())):
        name = os.path.basename(path.rstrip("/\\")) or path
        if os.path.isdir(path):
            inside = _patches_under(path)
            found += [(p, p) for p in inside]
            if not inside:
                skipped.append({"source": path, "skip": "the folder %s holds "
                                "no .patch.osm file" % name})
        elif path.lower().endswith(".zip") and zipfile.is_zipfile(path):
            into = os.path.join(scratch, str(n))
            try:
                _unpack(path, into)
            except (ValueError, OSError, zipfile.BadZipFile) as error:
                skipped.append({"source": path, "skip": str(error)})
                continue
            inside = _patches_under(into)
            found += [(p, os.path.join(path, os.path.relpath(p, into)))
                      for p in inside]
            if not inside:
                skipped.append({"source": path, "skip": "the archive %s holds "
                                "no .patch.osm file" % name})
        elif path.endswith(FNAMES.PATCH_SUFFIX) and os.path.isfile(path):
            found.append((path, path))
        else:
            skipped.append({"source": path, "skip": "%s is not a patch "
                            "(a .patch.osm file, a folder or a .zip of them)"
                            % name})
    return found, skipped


def _plan(paths, scratch: str) -> dict:
    found, skipped = _gather(paths, scratch)
    items, taken = [], set()
    for source, shown in found:
        row = _row(source, shown)
        if "skip" not in row and row["destination"] in taken:
            row = {"source": shown, "skip": "another dropped file already "
                   "goes to %s" % os.path.basename(row["destination"])}
        if "skip" in row:
            skipped.append(row)
            continue
        taken.add(row["destination"])
        items.append(row)
    if not items:
        reasons = "; ".join(r["skip"] for r in skipped) or "nothing was dropped"
        raise ValueError("Nothing to install: " + reasons + ".")
    return {"items": items, "skipped": skipped,
            "tiles": sorted({r["tile"] for r in items})}


def _line(row: dict) -> str:
    """One plan row as both apps show it."""
    if "skip" in row:
        return "Skipped: " + row["skip"]
    line = "%s → %s, tile %s" % (row["name"], row["icao"], row["tile"])
    if os.path.basename(row["destination"]) != row["name"]:
        line += ", as " + os.path.basename(row["destination"])
    if row["replaces"]:
        line += " (replaces the installed one, kept as .disabled)"
    return line


def _public(plan: dict) -> dict:
    """The plan as the commands reply it, with ``summary``: one line per
    patch, then one per skipped file — the confirmation both apps show."""
    return dict(plan, items=[{k: v for k, v in r.items() if k != "_files"}
                             for r in plan["items"]],
                summary=[_line(r) for r in plan["items"] + plan["skipped"]])


def _copy(source: str, target: str) -> str:
    """Copy *source* to *target*; returns where an existing *target* was
    set aside (``""`` when there was none)."""
    backup = CUSTOM.set_aside(target) if os.path.lexists(target) else ""
    shutil.copyfile(source, target + ".tmp")
    os.replace(target + ".tmp", target)
    return backup


def patch_drop_plan(paths) -> dict:
    """ENGINE COMMAND ``patch_drop_plan``: what dropping *paths* would
    install.  Writes nothing.

    :returns: ``{"items": [{"source", "name", "icao", "tile", "found_by",
        "destination", "replaces", "companions"}], "skipped": [{"source",
        "skip"}], "tiles", "summary"}``
    :raises ValueError: when nothing dropped is an installable patch (the
        sentence lists why).
    """
    with tempfile.TemporaryDirectory(prefix="o4_patch_drop_") as scratch:
        return _public(_plan(paths, scratch))


def patch_drop_install(paths) -> dict:
    """ENGINE COMMAND ``patch_drop_install``: install what
    :func:`patch_drop_plan` lists for *paths*.

    :returns: the plan, each item with ``"backups"`` (the paths replaced
        files were set aside as).
    """
    with tempfile.TemporaryDirectory(prefix="o4_patch_drop_") as scratch:
        plan = _plan(paths, scratch)
        for row in plan["items"]:
            os.makedirs(os.path.dirname(row["destination"]), exist_ok=True)
            backups = [_copy(s, t) for s, t in row["_files"]]
            row["backups"] = [b for b in backups if b]
        return _public(plan)
