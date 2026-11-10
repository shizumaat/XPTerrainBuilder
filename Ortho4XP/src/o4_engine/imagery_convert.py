"""Convert the ortho tiles a Custom Scenery folder already has to
on-demand form (#1992 phase P1c; capability ``imagery_ondemand_convert``).

Each ``zOrtho4XP_<tile>`` entry -- a symlink onto a library volume, or a
local folder -- gets a lean LOCAL copy (``O4_Imagery_OnDemand_Convert``:
placeholders cut from its own full DDS, the DSF 7z-compressed, no build
intermediates) whose manifest names the full textures' home, so the
follow job lands full tiers from it while it is mounted (no network) and
re-downloads them when it is not.

* :func:`dry_run` -- per ``zOrtho4XP_<tile>`` entry (kind ``link``,
  ``link-unmounted``, ``dir`` or ``converted``; enabled in
  ``scenery_packs.ini`` or not) and in total: placeholder bytes at each
  width asked, the DSFs compressed (ratio measured on a sample),
  intermediates left out.  Reads headers and ``stat`` only.
* :func:`convert` -- convert entries in parallel (one worker per tile);
  each copy is staged, verified and stamped before anything else moves.
  With ``swap`` the Custom Scenery entry is then EXCHANGED for the copy
  in one atomic step (``O4_Path_Exchange``), so a run killed at any point
  leaves the entry pointing at a complete tile; the previous entry (the
  symlink, or the local full folder) is kept in the work folder, and
  :func:`revert` swaps it back.  The source is only ever read; the
  entry's NAME never changes, so ``scenery_packs.ini`` (order, enabled)
  is untouched.  A finished entry is a no-op on the next run.
* :func:`converted_tiles` -- ``(dir, lat, lon)`` of every converted copy
  (the registry), which the index scan includes
  (``imagery_ondemand.imagery_ondemand_scan``).
* :func:`imagery_ondemand_convert` -- the ENGINE COMMAND over the above.

No tile, airport or volume is named here; paths come from the caller.
"""
from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Dict, Optional

import O4_DSF_Compress as DSFC
import O4_File_Names as FNAMES
import O4_Imagery_OnDemand_Convert as CONVERT
import O4_Imagery_Placeholder as PLACEHOLDER
import O4_Path_Exchange as EXCHANGE

__all__ = ["WORK_DIR_NAME", "convert", "converted_tiles", "dry_run",
           "imagery_ondemand_convert", "revert"]

#: Beside the Custom Scenery folder (same volume, so the exchange is one
#: step; X-Plane does not scan it): staged copies and previous entries.
WORK_DIR_NAME = "XPTerrainBuilder_ondemand_work"
_REGISTRY = "converted.json"
_registry_lock = threading.Lock()


@dataclass
class _Entry:
    """One ``zOrtho4XP_<tile>`` entry of a Custom Scenery folder."""
    name: str
    path: str
    lat: int
    lon: int
    kind: str           # link | link-unmounted | dir | converted
    source: str         # where its files are read from (realpath)
    enabled: bool

    @property
    def tile(self) -> str:
        return FNAMES.short_latlon(self.lat, self.lon)


def _work_dir_for(custom_scenery_dir: str) -> str:
    """The default work folder of a Custom Scenery folder."""
    parent = os.path.dirname(os.path.abspath(custom_scenery_dir))
    return os.path.join(parent, WORK_DIR_NAME)


def _entries(custom_scenery_dir: str, names=None) -> "list[_Entry]":
    """The tile entries of ``custom_scenery_dir`` (only ``names`` when
    given), sorted by name."""
    import O4_Scenery_Links as LINKS
    import O4_Scenery_Packs as PACKS
    enabled = PACKS.enabled_pack_names(custom_scenery_dir)
    wanted = set(names) if names else None
    found = []
    for item in sorted(os.scandir(custom_scenery_dir), key=lambda e: e.name):
        key = LINKS._parse_tile_name(item.name)
        if key is None or (wanted is not None and item.name not in wanted):
            continue
        source = os.path.realpath(item.path)
        if item.is_symlink() and CONVERT.is_converted(source):
            kind = "converted"          # a link to a copy in a local root
        elif item.is_symlink():
            kind = "link" if os.path.isdir(source) else "link-unmounted"
        elif item.is_dir():
            kind = "converted" if CONVERT.is_converted(item.path) else "dir"
        else:
            continue
        found.append(_Entry(item.name, item.path, key[0], key[1], kind,
                           source, item.name in enabled))
    return found


def _xplane_running() -> bool:
    """Is an X-Plane process running on this machine (best effort: macOS
    and Linux process names; ``False`` where it cannot tell)?"""
    if sys.platform == "win32":
        return False
    for name in ("X-Plane", "X-Plane-x86_64", "X-Plane-arm64"):
        with contextlib.suppress(OSError):
            done = subprocess.run(["pgrep", "-x", name], capture_output=True,
                                  check=False)
            if done.returncode == 0:
                return True
    return False


# ----------------------------------------------------------------- dry run


def _size_row(entry: _Entry, widths) -> dict:
    row = {"name": entry.name, "kind": entry.kind, "enabled": entry.enabled}
    if entry.kind in ("link-unmounted", "converted"):
        return row
    for index, px in enumerate(widths):
        plan = CONVERT.plan_tile(entry.source, px)
        row[f"placeholder_bytes_{px}"] = plan.total("textures")
        if index == 0:
            row.update(textures=len(plan.textures),
                       source_texture_bytes=plan.total("source_textures"),
                       copy_bytes=plan.total("copies"),
                       dsf_bytes=plan.total("dsfs"),
                       dsf_already_7z=sum(1 for d in plan.dsfs if d[2]),
                       skipped_bytes=plan.total("skipped"),
                       whole_copies=plan.whole_copies,
                       dsf_paths=[os.path.join(plan.source, d[0])
                                  for d in plan.dsfs if not d[2]])
    return row


def _dsf_ratio(paths, sample: int) -> "tuple[float, int]":
    """(compressed / raw bytes over ``sample`` DSFs spread over ``paths``,
    DSFs measured)."""
    if not paths or sample <= 0:
        return 0.6, 0
    step = max(1, len(paths) // sample)
    chosen = paths[::step][:sample]
    raw = packed = 0
    with tempfile.TemporaryDirectory(prefix="o4_dsf_ratio_") as scratch:
        for number, path in enumerate(chosen):
            dest = os.path.join(scratch, f"{number}.dsf")
            try:
                DSFC.compress(path, dest)
            except DSFC.CompressError:
                continue
            raw += os.path.getsize(path)
            packed += os.path.getsize(dest)
            os.remove(dest)
    return (packed / raw if raw else 0.6), len(chosen)


def dry_run(custom_scenery_dir: str, names=None, *, widths=(512,),
            workers: int = 8, sample_dsf: int = 6) -> Dict[str, Any]:
    """Sizing of a conversion of every entry (or ``names``): ``{"rows",
    "totals"}``; reads headers and ``stat`` only, plus ``sample_dsf``
    DSFs compressed in a temporary folder for the ratio."""
    found = _entries(custom_scenery_dir, names)
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        rows = list(pool.map(lambda e: _size_row(e, widths), found))
    raw_dsfs = [p for r in rows for p in r.pop("dsf_paths", [])]
    ratio, measured = _dsf_ratio(raw_dsfs, sample_dsf)
    sized = [r for r in rows if "textures" in r]
    totals = {"entries": len(rows),
              "by_kind": {k: sum(1 for r in rows if r["kind"] == k)
                          for k in sorted({r["kind"] for r in rows})},
              "enabled": sum(1 for r in rows if r["enabled"]),
              "dsf_ratio": round(ratio, 4), "dsf_ratio_sample": measured,
              "seconds": round(time.monotonic() - started, 1)}
    for key in ("textures", "source_texture_bytes", "copy_bytes",
                "dsf_bytes", "dsf_already_7z", "skipped_bytes",
                "whole_copies", *(f"placeholder_bytes_{px}" for px in widths)):
        totals[key] = sum(r.get(key, 0) for r in sized)
    already = sum(r["dsf_bytes"] for r in sized if r.get("dsf_already_7z"))
    totals["dsf_compressed_bytes_est"] = int(
        (totals["dsf_bytes"] - already) * ratio + already)
    for px in widths:
        totals[f"total_bytes_{px}_est"] = (
            totals[f"placeholder_bytes_{px}"] + totals["copy_bytes"]
            + totals["dsf_compressed_bytes_est"])
    return {"rows": rows, "totals": totals}


# ----------------------------------------------------------------- convert


def _registry_path() -> str:
    return os.path.join(FNAMES.data_path(PLACEHOLDER.STORE_DIR), _REGISTRY)


def _registry() -> dict:
    try:
        with open(_registry_path(), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _record(tile: str, record: "dict | None") -> None:
    """Set (``None``: drop) ``tile``'s registry record."""
    with _registry_lock:
        data = _registry()
        if record is None:
            data.pop(tile, None)
        else:
            data[tile] = record
        path = _registry_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        temp = f"{path}.{os.getpid()}.part"
        with open(temp, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
        os.replace(temp, path)


def converted_tiles() -> "list[tuple[str, int, int]]":
    """``(dir, lat, lon)`` of every registered converted copy still on
    disk (a finished copy)."""
    out = []
    for tile, record in sorted(_registry().items()):
        folder = record.get("dir") if isinstance(record, dict) else None
        if folder and CONVERT.is_converted(folder):
            out.append((folder, int(tile[:3]), int(tile[3:])))
    return out


def _register(entry: _Entry, folder: str, record: dict,
              index: "str | None") -> int:
    """Keep the copy's placeholders in the store and write its index rows
    (``imagery_ondemand.register_tiles``); the rows written."""
    from . import imagery_ondemand as ONDEMAND
    tile = SimpleNamespace(lat=entry.lat, lon=entry.lon)
    textures = os.path.join(folder, "textures")
    for name in sorted(os.listdir(textures)):
        if name.endswith(".dds"):
            PLACEHOLDER.keep(tile, os.path.join(textures, name))
    _record(entry.tile, record)
    return ONDEMAND.register_tiles([(folder, entry.lat, entry.lon)], index)


def _aside(path: str) -> str:
    """``path``, or ``path.<n>`` when that is taken (never overwrites)."""
    candidate, number = path, 1
    while os.path.lexists(candidate):
        candidate, number = f"{path}.{number}", number + 1
    return candidate


def _swap(entry: _Entry, incoming: str, work: str) -> str:
    """Exchange the Custom Scenery entry for ``incoming`` (a staged folder
    or a symlink to the copy); the previous entry is moved aside in
    ``work``.  Returns where it now is."""
    EXCHANGE.exchange(incoming, entry.path)
    previous = _aside(os.path.join(work, f"{entry.name}.previous"))
    os.rename(incoming, previous)
    return previous


def _convert_one(entry: _Entry, *, px: int, local_root, swap: bool, work: str,
                 threads: int, register: bool, index) -> dict:
    out = {"name": entry.name, "kind": entry.kind}
    if entry.kind == "converted":
        return {**out, "status": "already converted"}
    if entry.kind == "link-unmounted":
        return {**out, "status": "skipped: source not mounted"}
    if local_root:
        final = os.path.join(local_root, entry.name)
        staged = os.path.join(local_root, ".staging", entry.name)
    else:
        final = staged = os.path.join(work, f"{entry.name}.incoming")
    if local_root and CONVERT.is_converted(final, entry.source, px):
        result = {"bytes_written": 0, "seconds": 0.0, "problems": []}
        out["status"] = "copy already done"
    else:
        moved_full = swap and not local_root and entry.kind == "dir"
        full_source = (os.path.join(work, f"{entry.name}.previous")
                       if moved_full else entry.source)
        plan = CONVERT.plan_tile(entry.source, px)
        result = CONVERT.convert_tile(plan, staged, entry.tile,
                                      full_source=full_source,
                                      threads=threads)
        if result["problems"]:
            return {**out, **result, "status": "failed: copy incomplete"}
        if staged != final:
            if os.path.lexists(final):
                return {**out, **result,
                        "status": f"failed: {final} exists, not a finished copy"}
            os.rename(staged, final)
        out["status"] = "copied"
    out.update(result)
    in_use = final
    if swap:
        if _xplane_running():
            return {**out, "status": out["status"] + "; NOT swapped: "
                    "X-Plane is running"}
        incoming = final
        if local_root:
            incoming = os.path.join(work, f"{entry.name}.incoming-link")
            with contextlib.suppress(FileNotFoundError):
                os.remove(incoming)
            os.symlink(final, incoming)
        try:
            out["previous"] = _swap(entry, incoming, work)
        except OSError as error:
            return {**out, "status": out["status"] + f"; NOT swapped: {error}"}
        in_use = entry.path if not local_root else final
        out["status"] += "; swapped"
    if register:
        out["index_rows"] = _register(entry, in_use, {
            "dir": in_use, "entry": entry.path, "source": entry.source,
            "placeholder_px": px, "previous": out.get("previous"),
            "converted_at": time.time()}, index)
    return out


def convert(custom_scenery_dir: str, names=None, *, px: int = CONVERT.DEFAULT_PX,
            local_root: "str | None" = None, swap: bool = False,
            work_dir: "str | None" = None, workers: int = 4,
            threads: int = 4, register: bool = True,
            index: "str | None" = None) -> Dict[str, Any]:
    """Convert every entry (or ``names``), ``workers`` tiles at a time.
    ``local_root``: where the copies live (default: in place of the
    entry, so ``swap`` puts a real folder under the entry's name).
    Returns ``{"rows", "bytes_written", "seconds"}``."""
    work = work_dir or _work_dir_for(custom_scenery_dir)
    if swap or not local_root:          # copies into a local root need none
        os.makedirs(work, exist_ok=True)
    if swap and not EXCHANGE.supported(work):
        raise EXCHANGE.ExchangeUnsupported(
            "no atomic exchange in %s: --swap refused (copies only)" % work)
    if local_root:
        os.makedirs(os.path.join(local_root, ".staging"), exist_ok=True)
    found = _entries(custom_scenery_dir, names)
    started = time.monotonic()

    def one(entry):
        try:
            return _convert_one(entry, px=int(px), local_root=local_root,
                                swap=swap, work=work, threads=threads,
                                register=register, index=index)
        except OSError as error:
            return {"name": entry.name, "status": f"failed: {error}"}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        rows = list(pool.map(one, found))
    return {"rows": rows,
            "bytes_written": sum(r.get("bytes_written", 0) for r in rows),
            "seconds": round(time.monotonic() - started, 1)}


def revert(custom_scenery_dir: str, name: str,
           work_dir: "str | None" = None,
           index: "str | None" = None) -> Dict[str, Any]:
    """Swap a converted entry back to what it was before (the newest
    ``<name>.previous`` in the work folder); the copy is kept aside as
    ``<name>.converted``.  Its index rows and registry record go."""
    work = work_dir or _work_dir_for(custom_scenery_dir)
    entry = os.path.join(custom_scenery_dir, name)
    kept = sorted((p for p in os.listdir(work)
                   if p == f"{name}.previous" or
                   p.startswith(f"{name}.previous.")),
                  key=lambda p: os.lstat(os.path.join(work, p)).st_mtime)
    if not kept:
        raise ValueError(f"{name}: no previous entry in {work}")
    if _xplane_running():
        raise ValueError(f"{name}: not while X-Plane is running")
    previous = os.path.join(work, kept[-1])
    EXCHANGE.exchange(previous, entry)
    aside = _aside(os.path.join(work, f"{name}.converted"))
    os.rename(previous, aside)
    import O4_Scenery_Links as LINKS
    key = LINKS._parse_tile_name(name)
    if key is not None:
        from . import imagery_ondemand as ONDEMAND
        tile = FNAMES.short_latlon(*key)
        _record(tile, None)
        ONDEMAND.forget_tile(tile, index)
    return {"name": name, "restored": entry, "converted_copy": aside}


def imagery_ondemand_convert(custom_scenery_dir: str, tiles=None,
                             dry_run_only: bool = True,
                             placeholder_px: int = CONVERT.DEFAULT_PX,
                             local_root: Optional[str] = None,
                             swap: bool = False, workers: int = 4
                             ) -> Dict[str, Any]:
    """ENGINE COMMAND ``imagery_ondemand_convert``: the dry run (default)
    or the conversion of ``tiles`` (entry names; all when omitted) of
    ``custom_scenery_dir``.  Synchronous: it answers when done."""
    if dry_run_only:
        return dry_run(custom_scenery_dir, tiles,
                       widths=(int(placeholder_px),), workers=workers)
    return convert(custom_scenery_dir, tiles, px=int(placeholder_px),
                   local_root=local_root, swap=bool(swap), workers=workers)
