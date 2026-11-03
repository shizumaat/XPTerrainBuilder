"""AN AIRPORT ENTRY'S MATCH KEY on this machine (#1699 phase 2; design,
"Matching the pack version").

An entry is used as solved when THREE things match (spec §3):

* the PACK SIGNATURE — the airport's apt.dat block, its pack's tile DSF
  as installed (the pristine ``.anchor_bak`` when a build rewrote it),
  a borrowed Global Airports block, the ``1302 flatten`` declaration
  (``auto_patch_v2.airport.pack_identity``, the one derivation, shared
  with the tile bundles).  A pack renamed in Custom Scenery still
  matches; a pack whose developer changed its DSF does not;
* the AUTO-PATCH LAW — the freshness schema, the auto-patch configuration
  digest (taken without the cache-location variables, which name a
  machine), the code digest of the patch build and the engine kind:
  ``o4_fresh_v`` / ``o4_cfg`` / ``o4_code`` / ``o4_ap_engine``, the
  stamps the reuse gate compares;
* the SOLVE SETTINGS — the tile settings the solve reads
  (``provenance.solve_settings_fingerprint``, ``o4_solve_cfg``).

Not matched: the publisher's elevation, OpenStreetMap and CIFP snapshot,
imagery and toolchain — what an entry exists to spare the receiver.

The signature hashes the pack's DSF (tens of MB), so it is CACHED by the
size and date of every file it read (``Library/signatures.json`` in the
data folder): only a changed pack is hashed again.
"""
from __future__ import annotations

import json
import os

__all__ = ["CACHE_NAME", "law_now", "solve_now",
           "pack_now", "first_difference", "engine_older"]

CACHE_NAME = "signatures.json"

def law_now(tile) -> dict:
    """This engine's auto-patch law, portable (no cache location in it)."""
    from auto_patch import engine_v2 as _engine
    from auto_patch import provenance as _prov
    from auto_patch import provenance_code as _code
    from auto_patch.provenance_env import without_cache_locations
    with without_cache_locations():
        cfg = _prov.config_digest()
    return {"fresh_v": str(_prov.FRESHNESS_SCHEMA_VERSION), "cfg": cfg,
            "code": _code.freshness_code_digest(),
            "ap_engine": _engine.resolved_auto_patch_engine(tile)}


def solve_now(tile) -> str:
    """The solve-settings fingerprint of ``tile`` (``o4_solve_cfg``)."""
    from auto_patch import provenance as _prov
    return _prov.solve_settings_fingerprint(tile)


def _cache_path() -> str:
    import O4_File_Names as FNAMES
    return os.path.join(FNAMES.current_data_root(), "Library", CACHE_NAME)


def _stats(paths) -> list:
    out = []
    for path in paths:
        try:
            st = os.stat(path) if path else None
        except OSError:
            st = None
        out.append([path, st.st_size if st else -1, st.st_mtime_ns if st else -1])
    return out


def _read_cache() -> dict:
    try:
        with open(_cache_path(), encoding="utf-8") as handle:
            doc = json.load(handle)
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_cache(doc: dict) -> None:
    path = _cache_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as handle:
            json.dump(doc, handle, indent=1, sort_keys=True)
        os.replace(path + ".tmp", path)
    except OSError:
        pass                        # a cache: the next call hashes again


def _ini(xp_root: str) -> str:
    return os.path.join(xp_root, "Custom Scenery", "scenery_packs.ini")


def pack_now(xp_root: str, icao: str, lat: int, lon: int) -> dict:
    """``{"pack", "custom", "signature"}`` of ``icao``'s pack in this
    install, from the cache while no file it read has moved and the pack
    order (``scenery_packs.ini``) is unchanged."""
    from auto_patch_v2.airport.pack_identity import pack_signature
    key = "%s|%d|%d|%s" % (icao.upper(), lat, lon, os.path.normpath(xp_root))
    cache = _read_cache()
    hit = cache.get(key)
    ini = _stats([_ini(xp_root)])
    if hit and hit.get("ini") == ini and hit.get("stats") == _stats(
            [row[0] for row in hit.get("stats", [])]):
        return dict(hit["signature"])
    files: list = []
    sig = pack_signature(xp_root, icao.upper(), lat, lon, files)
    cache[key] = {"ini": ini, "stats": _stats(files), "signature": sig}
    _write_cache(cache)
    return dict(sig)


def first_difference(entry: dict, local: dict) -> str | None:
    """Why the entry (``{"signature", "law", "solve"}``) is not this
    machine's (the same shape), in the user's words; ``None`` on a match."""
    if entry.get("signature") != local.get("signature"):
        return "your installed scenery pack is not the version the patch was made for"
    theirs, ours = entry.get("law") or {}, local.get("law") or {}
    if theirs.get("code") != ours.get("code") or theirs.get("ap_engine") != ours.get("ap_engine") \
            or theirs.get("fresh_v") != ours.get("fresh_v"):
        return "the patch was solved by another version of the auto-patch engine"
    if theirs.get("cfg") != ours.get("cfg"):
        return "the patch was solved under other auto-patch settings"
    if entry.get("solve") != local.get("solve"):
        return "your tile's road grade or lane width settings differ from the patch's"
    return None


def _version(text: str) -> tuple:
    out = []
    for part in str(text or "").split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        out.append(int(digits) if digits else 0)
    return tuple(out)


def engine_older(min_engine: str) -> bool:
    """Whether this engine is older than an entry's ``min_engine``
    (#1699 decision 11: the app warns and offers to update)."""
    import O4_Version
    return _version(getattr(O4_Version, "version", "")) < _version(min_engine)
