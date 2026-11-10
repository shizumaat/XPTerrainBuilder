"""The dry run of the World migration (``world_migrate``, World spec §13
M1): what moving every ``zOrtho4XP_<tile>`` entry into the World pack
would do, write and take, with nothing written in Custom Scenery.

* per entry: its action (``world_migrate.classify``) and the new bytes:
  the on-demand copy of a linked tile (P1c ``plan_tile``: placeholders,
  ``terrain/``, no DSF) and the World pack's own DSF (the relaid DSF is
  written uncompressed; a 7z source counts at its packed size over
  :data:`SEVEN_ZIP_RATIO`).  Textures go into the pack as hard links:
  no new bytes on the same volume, their whole size on another;
* the time, from a sample of up to ``sample`` tiles migrated for real
  into a scratch World pack in a temporary folder (no ini, no index) and
  removed after: the mean seconds per action, times the entries, over
  the workers.

Reads headers and ``stat`` only, besides the sample.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

import O4_DSF_Compress as DSFC
import O4_Imagery_OnDemand_Convert as CONVERT
import O4_World_Pack as WP

from . import world_migrate as MIGRATE

__all__ = ["SEVEN_ZIP_RATIO", "dry_run"]

#: Packed / raw bytes of a 7z DSF, for sizing an unpack (P1c's ratio).
SEVEN_ZIP_RATIO = 0.6
_MOVES = ("copy", "stage", "resume")


def _tree_bytes(folder: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(folder):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


def _dsf_bytes(path: str) -> int:
    """Uncompressed bytes of the DSF at ``path`` (estimated for a 7z)."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return 0
    return int(size / SEVEN_ZIP_RATIO) if DSFC.is_compressed(path) else size


def _same_volume(a: str, b: str) -> bool:
    try:
        return os.stat(a).st_dev == os.stat(b).st_dev
    except OSError:
        return False


def _size_row(entry, action: str, scenery_dir: str, px: int) -> dict:
    row = {"name": entry.name, "kind": entry.kind, "action": action,
           "enabled": entry.enabled}
    if action not in _MOVES:
        return row
    dsf = os.path.join(entry.source, WP.dsf_relpath(entry.lat, entry.lon))
    row["dsf_bytes"] = _dsf_bytes(dsf)
    row["dsf_7z"] = DSFC.is_compressed(dsf)
    if entry.kind == "link":
        plan = CONVERT.plan_tile(entry.source, px)
        row["copy_bytes"] = plan.total("textures") + plan.total("copies")
        row["library_texture_bytes"] = plan.total("source_textures")
        row["linked_texture_bytes"] = 0     # the copy is beside the pack
    else:
        textures = _tree_bytes(os.path.join(entry.source, "textures"))
        row["copy_bytes"] = 0
        row["linked_texture_bytes"] = (
            0 if _same_volume(entry.source, scenery_dir) else textures)
    row["new_bytes"] = (row["copy_bytes"] + row["dsf_bytes"]
                        + row["linked_texture_bytes"])
    return row


def _sample(chosen, scratch: str, px: int) -> list:
    """Migrate ``chosen`` into a scratch World pack under ``scratch``
    (no ini, no index); ``[(action, seconds, status)]``."""
    pack = os.path.join(scratch, WP.PACK_NAME)
    os.makedirs(pack)
    journal, lock = MIGRATE.Journal(scratch), threading.Lock()
    out = []
    for entry, action in chosen:
        started = time.monotonic()
        try:
            row = MIGRATE.migrate_tile(
                entry, scenery_dir=scratch, pack=pack, work=scratch,
                journal=journal, swap_lock=lock, px=px, ini=False,
                register=False)
            status = row["status"]
        except (OSError, ValueError, DSFC.CompressError) as error:
            status = f"failed: {error}"
        out.append((action, round(time.monotonic() - started, 2), status))
    return out


def _pick(rows, entries, sample: int) -> list:
    """Up to ``sample`` ``(entry, action)`` to time: the actions share the
    sample, each spread evenly over its entries."""
    groups: Dict[str, list] = {}
    for row, entry in zip(rows, entries, strict=False):
        if row["action"] in ("copy", "stage"):
            groups.setdefault(row["action"], []).append((entry, row["action"]))
    if not groups:
        return []
    per = max(1, sample // len(groups))
    picked = []
    for items in groups.values():
        picked += items[::max(1, len(items) // per)][:per]
    return picked[:sample]


def _estimate(rows, timed, workers: int) -> dict:
    means = {}
    for action in ("copy", "stage"):
        times = [s for a, s, status in timed
                 if a == action and status == "migrated"]
        if times:
            means[action] = round(sum(times) / len(times), 2)
    serial = sum(means.get("copy" if r["kind"] == "link" else "stage", 0.0)
                 for r in rows if r["action"] in _MOVES)
    return {"seconds_per_tile": means, "seconds_serial_est": round(serial),
            "seconds_est": round(serial / max(1, workers)),
            "sample": [{"action": a, "seconds": s, "status": st}
                       for a, s, st in timed]}


def dry_run(scenery_dir: str, names=None, *, px: int = CONVERT.DEFAULT_PX,
            workers: int = 8, sample: int = 6,
            sample_root: Optional[str] = None) -> Dict[str, Any]:
    """``{"rows", "totals"}`` of a migration of every entry (or
    ``names``) of ``scenery_dir``; see the module docstring.
    ``sample_root``: where the timing sample is written (default: the
    system's temporary folder)."""
    from . import world_commands as WORLD
    started = time.monotonic()
    pack = WORLD.pack_dir(scenery_dir)
    journal = MIGRATE.Journal(MIGRATE.work_dir_for(scenery_dir))
    found = MIGRATE.entries(scenery_dir, names)
    actions = [MIGRATE.classify(e, journal, pack) for e in found]
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        rows = list(pool.map(lambda pair: _size_row(pair[0], pair[1],
                                                    scenery_dir, px),
                             zip(found, actions, strict=False)))
    timed = []
    if sample > 0:
        if sample_root:
            os.makedirs(sample_root, exist_ok=True)
        scratch = tempfile.mkdtemp(prefix="o4_world_migrate_sample_",
                                   dir=sample_root)
        try:
            timed = _sample(_pick(rows, found, sample), scratch, px)
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
    totals: Dict[str, Any] = {
        "entries": len(rows),
        "by_kind": _tally(r["kind"] for r in rows),
        "by_action": _tally(r["action"] for r in rows)}
    for key in ("copy_bytes", "dsf_bytes", "linked_texture_bytes",
                "library_texture_bytes", "new_bytes"):
        totals[key] = sum(r.get(key, 0) for r in rows)
    totals["dsf_7z"] = sum(1 for r in rows if r.get("dsf_7z"))
    totals.update(_estimate(rows, timed, max(1, workers // 2)))
    totals["seconds"] = round(time.monotonic() - started, 1)
    return {"rows": rows, "totals": totals}


def _tally(values) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for value in values:
        out[value] = out.get(value, 0) + 1
    return dict(sorted(out.items()))
