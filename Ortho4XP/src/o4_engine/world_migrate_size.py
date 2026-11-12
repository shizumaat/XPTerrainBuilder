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
  the workers;
* per CHOICE (``world_retire.CHOICES``: keep all, keep the custom airport
  tiles, make everything dynamic): ``choices``, each with its figures
  (``world_retire.choice_totals``) and its sentence.

Reads headers and ``stat`` only, besides the sample, and keeps what it
read per tile folder (``world_tile_facts``: a second Measure of the same
tiles reads ``stat`` only).  The sample is skipped when ``rates`` (the
last measure's seconds per tile) already time every action it would.
``progress(done, total, name, phase)`` counts each PHASE (owner
2026-11-12T19:08Z: a count for every phase): ``measure`` the packs read,
``sample`` the sample's tiles, ``adopt`` the journalled tiles read for
adopting again (``world_adopt.plan``).  Cancel (``world_migrate.stop``)
ends it with :data:`world_migrate.STOPPED_MEASURE`.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional

import O4_DSF_Compress as DSFC
import O4_Imagery_OnDemand_Convert as CONVERT
import O4_World_Pack as WP

from . import world_migrate as MIGRATE
from . import world_retire as RETIRE
from .world_tile_facts import TileFacts

__all__ = ["SEVEN_ZIP_RATIO", "READ_WORKERS", "dry_run"]

#: Packed / raw bytes of a 7z DSF, for sizing an unpack (P1c's ratio).
SEVEN_ZIP_RATIO = 0.6
_MOVES = ("copy", "stage", "resume")
#: Packs read at once (owner 2026-11-12T19:08Z: parallel reads bounded,
#: 2-4, at background priority while builds run).
READ_WORKERS = 4


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


def _dsf_facts(folder: str, lat: int, lon: int, facts: TileFacts) -> list:
    """``[uncompressed bytes, 7z?]`` of the tile DSF in ``folder``."""
    dsf = os.path.join(folder, WP.dsf_relpath(lat, lon))
    return facts.get(folder, lat, lon, "dsf", lambda: [_dsf_bytes(dsf),
                                                       DSFC.is_compressed(dsf)])


def _same_volume(a: str, b: str) -> bool:
    try:
        return os.stat(a).st_dev == os.stat(b).st_dev
    except OSError:
        return False


def _size_row(entry, action: str, scenery_dir: str, px: int,
              facts: TileFacts) -> dict:
    from .world_adopt import plan_copy_bytes
    row = {"name": entry.name, "kind": entry.kind, "action": action,
           "enabled": entry.enabled}
    if action not in _MOVES:
        return row
    source, lat, lon = entry.source, entry.lat, entry.lon
    row["dsf_bytes"], row["dsf_7z"] = _dsf_facts(source, lat, lon, facts)
    if entry.kind == "link":
        copy, full = plan_copy_bytes(source, lat, lon, px, facts)
        row["copy_bytes"] = copy
        row["library_texture_bytes"] = full
        row["linked_texture_bytes"] = 0     # the copy is beside the pack
    else:
        textures = facts.get(source, lat, lon, "texture_bytes", lambda: _tree_bytes(
            os.path.join(source, "textures")))
        row["copy_bytes"] = 0
        row["texture_bytes"] = textures
        row["linked_texture_bytes"] = (
            0 if _same_volume(source, scenery_dir) else textures)
    row["new_bytes"] = (row["copy_bytes"] + row["dsf_bytes"]
                        + row["linked_texture_bytes"])
    return row


def _sample(chosen, scratch: str, px: int, tick=None) -> list:
    """Migrate ``chosen`` into a scratch World pack under ``scratch``
    (no ini, no index); ``[(action, seconds, status)]``.  ``tick(name)``
    before each tile; Cancel ends it early."""
    pack = os.path.join(scratch, WP.PACK_NAME)
    os.makedirs(pack)
    journal, lock = MIGRATE.Journal(scratch), threading.Lock()
    out = []
    for entry, action in chosen:
        if MIGRATE.stopping():
            break
        if tick:
            tick(entry.name)
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


def _estimate(rows, timed, workers: int, rates: Optional[dict] = None) -> dict:
    """The time to move, from the sample ``timed`` (or, when no sample
    ran, the earlier ``rates``)."""
    means = dict(rates or {})
    for action in ("copy", "stage"):
        times = [s for a, s, status in timed or ()
                 if a == action and status == "migrated"]
        if times:
            means[action] = round(sum(times) / len(times), 2)
    serial = sum(means.get("copy" if r["kind"] == "link" else "stage", 0.0)
                 for r in rows if r["action"] in _MOVES)
    return {"seconds_per_tile": means, "seconds_serial_est": round(serial),
            "seconds_est": round(serial / max(1, workers)),
            "sample": [{"action": a, "seconds": s, "status": st}
                       for a, s, st in timed or ()]}


def _counter(progress, total: int, phase: Optional[str] = None):
    """``tick(name)``: one more of ``total`` done, told to ``progress``
    (with ``phase`` when one is given)."""
    done, lock = [0], threading.Lock()

    def tick(name: str) -> None:
        with lock:
            done[0] += 1
            now = done[0]
        if progress:
            if phase is None:
                progress(now, total, name)
            else:
                progress(now, total, name, phase)
    return tick


def _timed(rates: Optional[dict], actions) -> bool:
    """Do the last measure's ``rates`` time every action to move?"""
    wanted = {a for a in actions if a in ("copy", "stage")}
    return bool(rates) and wanted <= set(rates)


def dry_run(scenery_dir: str, names=None, *, px: int = CONVERT.DEFAULT_PX,
            workers: int = READ_WORKERS, move_workers: int = 4,
            sample: int = 6,
            sample_root: Optional[str] = None,
            progress: Optional[Callable[..., None]] = None,
            facts: Optional[TileFacts] = None,
            rates: Optional[dict] = None) -> Dict[str, Any]:
    """``{"rows", "totals", "choices"}`` of a migration of every entry
    (or ``names``) of ``scenery_dir``; see the module docstring.
    ``sample_root``: where the timing sample is written (default: the
    system's temporary folder); ``workers``: packs read at once (at most
    :data:`READ_WORKERS`); ``move_workers``: the migration's, for its
    time; ``facts``: the header cache (a fresh one,
    kept nowhere, when omitted); ``rates``: ``{action: seconds per tile}``
    of an earlier measure (no sample when they cover it)."""
    from . import world_commands as WORLD
    started = time.monotonic()
    MIGRATE._STOP.clear()
    facts = facts if facts is not None else TileFacts()
    pack = WORLD.pack_dir(scenery_dir)
    journal = MIGRATE.Journal(MIGRATE.work_dir_for(scenery_dir))
    found = MIGRATE.entries(scenery_dir, names)
    actions = [MIGRATE.classify(e, journal, pack) for e in found]
    tick = _counter(progress, len(found), "measure")
    if progress:
        progress(0, len(found), "", "measure")

    def size_one(pair) -> dict:
        if MIGRATE.stopping():
            return {}
        row = _size_row(pair[0], pair[1], scenery_dir, px, facts)
        tick(pair[0].name)
        return row
    workers = max(1, min(int(workers), READ_WORKERS))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(size_one, zip(found, actions, strict=False)))
    if MIGRATE.stopping():
        raise ValueError(MIGRATE.STOPPED_MEASURE)
    timed = _run_sample(found, actions, sample, sample_root, px, progress,
                        rates)
    totals: Dict[str, Any] = {
        "entries": len(rows),
        "by_kind": _tally(r["kind"] for r in rows),
        "by_action": _tally(r["action"] for r in rows)}
    for key in ("copy_bytes", "dsf_bytes", "linked_texture_bytes",
                "library_texture_bytes", "new_bytes"):
        totals[key] = sum(r.get(key, 0) for r in rows)
    totals["dsf_7z"] = sum(1 for r in rows if r.get("dsf_7z"))
    totals.update(_estimate(rows, timed, max(1, int(move_workers)),
                            rates if timed is None else None))
    choices = _choices(rows, found, scenery_dir, journal, px, names, facts,
                       progress)
    if MIGRATE.stopping():
        raise ValueError(MIGRATE.STOPPED_MEASURE)
    totals["seconds"] = round(time.monotonic() - started, 1)
    return {"rows": rows, "totals": totals, "choices": choices}


def _run_sample(found, actions, sample: int, sample_root, px: int,
                progress, rates) -> Optional[list]:
    """The timed sample (phase ``sample``); ``None`` when ``rates``
    already time every action (no sample run)."""
    if _timed(rates, actions):
        return None
    chosen = (_pick([{"action": a} for a in actions], found, sample)
              if sample > 0 else [])
    if not chosen:
        return []
    tick = _counter(progress, len(chosen), "sample")
    if progress:
        progress(0, len(chosen), "", "sample")
    if sample_root:
        os.makedirs(sample_root, exist_ok=True)
    scratch = tempfile.mkdtemp(prefix="o4_world_migrate_sample_",
                               dir=sample_root)
    try:
        timed = _sample(chosen, scratch, px, tick=tick)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    if MIGRATE.stopping():
        raise ValueError(MIGRATE.STOPPED_MEASURE)
    return timed


def _choices(rows, found, scenery_dir: str, journal, px: int,
             names=None, facts: Optional[TileFacts] = None,
             progress=None) -> list:
    """``[{"id", "line", **figures}]`` of every choice, in order; the
    tiles made dynamic before that a choice adopts again
    (``world_adopt.plan``, phase ``adopt``) counted in."""
    import O4_Custom_Scenery as SCENERY

    from . import world_adopt as ADOPT
    points = SCENERY.airport_points_by_tile(scenery_dir)
    adopt = ((lambda done, total, name: progress(done, total, name, "adopt"))
             if progress else None)
    figures = RETIRE.choice_totals(
        rows, found, RETIRE.custom_airport_tiles(scenery_dir),
        RETIRE.disabled_names(scenery_dir),
        again=ADOPT.plan(journal.records, points, px, names, facts=facts,
                         progress=adopt, stopping=MIGRATE.stopping))
    return [{"id": choice, "line": RETIRE.choice_line(choice, figures[choice]),
             **figures[choice]} for choice in RETIRE.CHOICES]


def _tally(values) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for value in values:
        out[value] = out.get(value, 0) + 1
    return dict(sorted(out.items()))
