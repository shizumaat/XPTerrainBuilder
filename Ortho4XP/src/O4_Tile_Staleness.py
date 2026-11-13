"""Is a built tile still fitted to the airport packs X-Plane draws? (#1958)

Each auto patch is fitted to ONE airport pack: the apt.dat the build
selected (``[pav-builder] ICAO: apt.dat <path>`` in the tile's build log)
and that pack's signature — apt.dat + DSF only (owner ruling, memory
``scenery-signature-apt-dsf-only``; ``auto_patch_v2.airport.pack_identity``
is the one derivation, read through the patch library's cache
``patch_library.key.pack_now``).  A build now records them in its build
record row (``airports``: ``{icao: {pack, custom, signature, apt_dat}}``,
:func:`record_airports`); a row written before that is read from its
log's ``[pav-builder]`` lines, which name the pack but not its signature.

A tile is STALE for an airport when its recorded pack

* ``gone``       — is no longer in Custom Scenery (deleted, moved, renamed);
* ``disabled``   — is disabled in ``scenery_packs.ini``;
* ``superseded`` — is not the pack X-Plane draws for that airport any more
  (``airport.pack.select_pack``, the selector the build runs);
* ``changed``    — has other content (its signature differs);
* ``package``    — ships XPTerrainBuilder data (a ``.xptb`` in its
  ``XPTerrainBuilder`` folder, RULINGS 2026-11-11m (4)) other than the one
  the tile was last built with (``tile_bundle.pack_shipped``, which the
  CALLER passes as ``packages``: the tile steps import this module, and
  an import of the package code here would put all of it in their code
  keys, #836).

A tile with no record of its packs (built before build logs, or by
another tool) is not checkable: ``checked`` is False and it is never
called stale.  The check only reads: X-Plane's folders, the tile's build
logs, and the signature cache in the data folder.

ENGINE COMMAND ``tile_staleness`` (capability ``tile_staleness``): both
apps run it after a tile scan and when Custom Scenery changes; it replies
``{"status": "started"}`` and completes with ``LibraryReady`` like the
Library commands.
"""
from __future__ import annotations

import os
import re

import O4_Scenery_Packs as SCENERY_PACKS
import O4_Tile_Build_Log as TILELOG

__all__ = ["REASONS", "record_airports",
           "check_tiles"]

#: Why a tile is stale for one airport, in the order they are judged.
REASONS = ("gone", "disabled", "superseded", "changed", "package")

#: A build's apt.dat choice (``auto_patch.build_support``).
_PAV = re.compile(r"\[pav-builder\] ([A-Z0-9]{3,7}): apt\.dat (.+?)\s*$")

#: The outcomes whose build left a tile on disk to judge.
_BUILT = ("ok", "warnings")


def _pack_of(apt_dat: str) -> str:
    """``Custom Scenery/<pack>/Earth nav data/apt.dat`` -> ``<pack>``."""
    return os.path.basename(os.path.dirname(os.path.dirname(apt_dat)))


def _custom_of(apt_dat: str) -> bool:
    """Whether ``apt_dat`` sits in a Custom Scenery pack other than
    Global Airports (which the ini does not govern on XP12)."""
    pack_root = os.path.dirname(os.path.dirname(apt_dat))
    return (os.path.basename(os.path.dirname(pack_root)) == "Custom Scenery"
            and _pack_of(apt_dat) != "Global Airports")


def _xplane_root_of(apt_dat: str) -> str:
    """The X-Plane folder an apt.dat path lies in (four levels up)."""
    path = apt_dat
    for _ in range(4):
        path = os.path.dirname(path)
    return path


def _log_airports(build_dir: str, log_name: str) -> dict:
    """``{icao: apt.dat path}`` a build log names, the last choice of each
    airport winning (a build may select twice)."""
    out: dict = {}
    for line in TILELOG.read_log(build_dir, log_name).splitlines():
        match = _PAV.search(line)
        if match:
            out[match.group(1).upper()] = match.group(2)
    return out


def _pack_now(xp_root: str, icao: str, lat: int, lon: int) -> dict:
    from patch_library.key import pack_now
    return pack_now(xp_root, icao, lat, lon)


def record_airports(build_dir: str, log_name: str, lat: int, lon: int) -> dict:
    """``{icao: {"pack", "custom", "signature", "apt_dat"}}`` of the
    airports a finished build's log names — what its record row keeps.
    A signature that cannot be taken is ``""`` (checked by pack only)."""
    out: dict = {}
    for icao, apt_dat in _log_airports(build_dir, log_name).items():
        entry = {"pack": _pack_of(apt_dat), "custom": _custom_of(apt_dat),
                 "signature": "", "apt_dat": apt_dat}
        try:
            sig = _pack_now(_xplane_root_of(apt_dat), icao, lat, lon)
            entry.update(pack=sig.get("pack") or entry["pack"],
                         custom=bool(sig.get("custom", entry["custom"])),
                         signature=sig.get("signature", ""))
        except Exception:
            pass
        out[icao] = entry
    return out


def _recorded_airports(build_dir: str, lat: int, lon: int):
    """``(row, {icao: entry})`` of the tile's newest finished build: its
    row's ``airports``, else its log's choices (no signatures).  ``(None,
    {})`` when the tile has no finished build on record."""
    for row in TILELOG.read_records(build_dir, lat, lon):
        if row.get("outcome") not in _BUILT:
            continue
        recorded = row.get("airports")
        if isinstance(recorded, dict):
            return row, recorded
        return row, {icao: {"pack": _pack_of(path), "custom": _custom_of(path),
                            "signature": "", "apt_dat": path}
                     for icao, path in _log_airports(
                         build_dir, row.get("log", "")).items()}
    return None, {}


def _text(icao: str, reason: str, pack: str, now: str) -> str:
    if reason == "gone":
        return "%s: its pack %s is no longer in Custom Scenery" % (icao, pack)
    if reason == "disabled":
        return "%s: its pack %s is disabled in scenery_packs.ini" % (icao, pack)
    if reason == "superseded":
        if not now:
            return "%s: no installed pack carries it any more" % icao
        return "%s: X-Plane now draws %s, not %s" % (icao, now, pack)
    return "%s: its pack %s has changed since the build" % (icao, pack)


def _airport_staleness(icao: str, entry: dict, xp_root: str, lat: int,
                      lon: int, disabled: set | None = None) -> dict | None:
    """``{"icao", "reason", "pack", "now_pack", "text"}`` when the tile is
    stale for ``icao`` (:data:`REASONS`), else ``None``."""
    from auto_patch_v2.airport.pack import select_pack
    pack = entry.get("pack") or _pack_of(entry.get("apt_dat", ""))
    custom_dir = os.path.join(xp_root, "Custom Scenery")
    now_pack, reason = "", None
    if entry.get("custom"):
        if disabled is None:
            disabled = SCENERY_PACKS.disabled_pack_names(custom_dir)
        if not os.path.isdir(os.path.join(custom_dir, pack)):
            reason = "gone"
        elif pack in disabled:
            reason = "disabled"
    if reason is None:
        sel = select_pack(xp_root, icao)
        if entry.get("signature"):
            now_pack = sel.name if sel else ""
        else:                           # a log's choice names the apt.dat's pack
            now_pack = _pack_of(sel.apt_dat_path) if sel else ""
        if now_pack != pack:
            reason = "superseded"
        elif entry.get("signature") and _pack_now(
                xp_root, icao, lat, lon).get("signature") != entry["signature"]:
            reason = "changed"
    if reason is None:
        return None
    return {"icao": icao, "reason": reason, "pack": pack, "now_pack": now_pack,
            "text": _text(icao, reason, pack, now_pack)}


def _tile_staleness(build_dir: str, lat: int, lon: int, custom_scenery_dir: str,
                   disabled: set | None = None, shipped=(), packages=None) -> dict:
    """One tile's verdict: ``{"lat", "lon", "checked", "stale",
    "airports": [stale airport, ...], "packs": {icao: pack}}``."""
    _row, recorded = _recorded_airports(build_dir, lat, lon)
    out = {"lat": lat, "lon": lon, "checked": bool(recorded), "stale": False,
           "airports": [], "packs": {icao: e.get("pack", "")
                                     for icao, e in sorted(recorded.items())}}
    xp_root = os.path.dirname(os.path.normpath(custom_scenery_dir or ""))
    if not recorded or not custom_scenery_dir:
        out["checked"] = False
        return out
    for icao, entry in sorted(recorded.items()):
        try:
            verdict = _airport_staleness(icao, entry, xp_root, lat, lon, disabled)
        except Exception:
            verdict = None
        if verdict is not None:
            out["airports"].append(verdict)
    if shipped and packages is not None:
        out["airports"] += packages[1](lat, lon, shipped)
    out["stale"] = bool(out["airports"])
    return out


def check_tiles(custom_scenery_dir: str, tiles=None, working_dir: str = "",
                packages=None) -> dict:
    """ENGINE COMMAND ``tile_staleness``: the verdict of every built tile —
    ``tiles`` (``[[lat, lon, build_dir], ...]``, what the app's scan
    already holds) or, without it, every tile of ``working_dir``.

    ``packages``: the shipped-package reader, ``(scan, stale_rows)`` of
    ``tile_bundle.pack_shipped`` — reason ``package`` is checked only when
    the caller passes it (``o4_engine.library.tile_staleness``, which both
    apps run).

    :returns: ``{"tiles": [verdict, ...], "stale": n, "checked": n}``,
        only the tiles whose packs are on record listed.
    """
    if tiles is None:
        import O4_Tile_Info as TINFO
        tiles = [(info.lat, info.lon, info.build_dir) for info in
                 TINFO.scan_tiles(working_dir).values()] if working_dir else []
    disabled = SCENERY_PACKS.disabled_pack_names(custom_scenery_dir or "")
    try:
        shipped = (packages[0](custom_scenery_dir)
                   if packages is not None and custom_scenery_dir else [])
    except Exception:                       # the pack check goes on without
        shipped = []
    rows = []
    with SCENERY_PACKS.listing_snapshot():
        for lat, lon, build_dir in tiles:
            if not build_dir or not os.path.isdir(build_dir):
                continue
            verdict = _tile_staleness(build_dir, int(lat), int(lon),
                                     custom_scenery_dir, disabled, shipped, packages)
            if verdict["checked"]:
                rows.append(verdict)
    rows.sort(key=lambda row: (row["lat"], row["lon"]))
    return {"tiles": rows, "stale": sum(row["stale"] for row in rows),
            "checked": len(rows)}

