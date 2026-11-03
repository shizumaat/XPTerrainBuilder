"""THE CHECK WHEN THE APP OPENS, AND THE BUILD BOX'S MATCH LIST (#1699
phase 2).

:func:`check` — "Read the installed packs and their pack signatures …
download the library index … list, in one place, the airports with a
patch available, the ones with a newer version than the one built, and
the ones whose pack was updated so the patch no longer matches" (design,
"When the app opens").  The airports asked about are those of the
ENABLED custom airport packs and those graded in the built tiles of the
working folder; only their regions' indexes are fetched (once a day
unless forced), and only an airport the library has an entry for is
hashed (:func:`key.pack_now`, cached by file size and date).  Nothing
is applied: each row offers Build / Update / Ignore to the user
(decision 7).

:func:`matches` — the build box's list for the airports a build grades:
the match tiers of #1699 (exact; same pack, other version; other pack),
best first, from the cached index.
"""
from __future__ import annotations

import json
import os
import time

from . import LibraryRefused
from . import adoption as _adoption
from . import client as _client
from . import config as _config
from . import key as _key
from . import layout as L

__all__ = ["STATES", "TIERS", "IGNORED_NAME", "check", "ignore",
           "matches"]

#: A check row's state: an entry the user has not used; a newer version
#: of the one used; the pack changed under a used patch; an entry only
#: for another version of the pack or another pack.
STATES = ("available", "newer", "pack_changed", "other")

#: The build box's match tiers, best first.
TIERS = ("exact", "same_pack", "other_pack")

IGNORED_NAME = "ignored.json"


def _xplane_root() -> str | None:
    from tile_bundle.key import xplane_root
    return xplane_root(None)


def _candidates(working_dir: str = "") -> dict:
    """``{icao: (lat, lon)}`` — the enabled custom packs' airports and the
    airports graded in the working folder's built tiles."""
    import O4_Config_Utils as CFG
    import O4_Custom_Scenery as PACKS
    import O4_File_Names as FNAMES
    import O4_Tile_Info as TINFO
    out: dict = {}
    for _name, _path, _root, enabled, airports in PACKS.iter_airport_packs(
            CFG.custom_scenery_dir):
        if enabled:
            for apt in airports:
                code = (apt.icao or "").upper()
                if L.ICAO_RE.match(code) and apt.lat is not None and apt.lon is not None:
                    out.setdefault(code, (int(apt.lat // 1), int(apt.lon // 1)))
    for (lat, lon) in TINFO.scan_tiles(working_dir or FNAMES.Tile_dir):
        try:
            names = os.listdir(FNAMES.patch_dir(lat, lon))
        except OSError:
            continue
        for name in names:
            icao = FNAMES.patch_file_icao(name)
            if icao:
                out[icao] = (lat, lon)       # where it is built wins
    return out


def _ignored() -> dict:
    try:
        with open(os.path.join(_client.library_dir(), IGNORED_NAME), encoding="utf-8") as h:
            return json.load(h)
    except (OSError, ValueError):
        return {}


def ignore(icao: str, signature: str, version: int) -> dict:
    """ENGINE COMMAND ``library_ignore``: the check stops listing this
    entry version for ``icao`` (a newer version is listed again)."""
    doc = _ignored()
    doc[icao.upper()] = {"signature": signature, "version": int(version)}
    folder = _client.library_dir()
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, IGNORED_NAME), "w", encoding="utf-8", newline="\n") as h:
        json.dump(doc, h, indent=1, sort_keys=True)
    return {"icao": icao.upper(), "ignored": doc[icao.upper()]}


def _row(icao, lat, lon, rows, xp_root, law, ignored) -> dict | None:
    import O4_File_Names as FNAMES
    from tile_bundle.export import load_tile
    sig = _key.pack_now(xp_root, icao, lat, lon)
    patch_dir = FNAMES.patch_dir(lat, lon)
    record = _adoption.read(patch_dir, icao)
    best = next((r for r in rows if r["signature"] == sig.get("signature")), None)
    pick = best or rows[0]
    out = {"icao": icao, "tile": FNAMES.short_latlon(lat, lon),
           "pack": sig.get("pack", ""), "entry_pack": pick["pack"],
           "version": pick["latest"], "entry": "%s/v%d" % (pick["path"], pick["latest"]),
           "signature": pick["signature"], "verified": bool(pick.get("verified")),
           "publisher": pick.get("publisher", ""),
           "local_version": record["version"] if record else None,
           "solved_usable": False, "reason": "", "warning": ""}
    if record and record.get("signature") != sig.get("signature"):
        out["state"] = "pack_changed"
        out["reason"] = ("your %s pack changed since its library patch was "
                         "laid down; the next build solves it here" % icao)
    elif best is None:
        out["state"] = "other"
        out["reason"] = "the library has patches for another version of this pack, or another pack"
    elif record and record.get("signature") == best["signature"]:
        if best["latest"] <= int(record.get("version", 0)):
            return None                            # current
        out["state"] = "newer"
    else:
        out["state"] = "available"
    if best is not None:
        tile = load_tile(lat, lon)
        why = _key.first_difference(best, {"signature": sig.get("signature"),
                                           "law": law, "solve": _key.solve_now(tile)})
        out["solved_usable"] = why is None
        out["reason"] = out["reason"] or (why or "")
        if _key.engine_older(best.get("min_engine", "")):
            out["warning"] = ("This patch names engine %s or newer; update the "
                              "app to use it as solved." % best["min_engine"])
    skip = ignored.get(icao)
    if skip and skip.get("signature") == out["signature"] and \
            int(skip.get("version", 0)) >= out["version"]:
        return None
    return out


def check(working_dir: str = "", force: bool = False) -> dict:
    """ENGINE COMMAND ``library_check``: what the library has for this
    installation.

    :returns: ``{"configured", "rows": [row, ...], "regions", "checked"}``;
        a row is ``{"icao", "tile", "state", "pack", "entry_pack",
        "version", "local_version", "entry", "signature", "verified",
        "publisher", "solved_usable", "reason", "warning"}``, verified
        developers' first.
    """
    if not _config.configured():
        return {"configured": False, "rows": [], "regions": [], "checked": ""}
    xp_root = _xplane_root()
    if not xp_root:
        raise LibraryRefused("No X-Plane folder is set; installed packs cannot be read")
    import O4_File_Names as FNAMES
    wanted = _candidates(working_dir)
    regions = sorted({L.region_of(FNAMES.short_latlon(lat, lon))
                      for lat, lon in wanted.values()})
    indexes = {region: _client.region_index(region, force) for region in regions}
    law = _key.law_now(None)
    ignored = _ignored()
    out = []
    for icao, (lat, lon) in sorted(wanted.items()):
        rows = indexes[L.region_of(FNAMES.short_latlon(lat, lon))].get(icao)
        if rows:
            row = _row(icao, lat, lon, rows, xp_root, law, ignored)
            if row is not None:
                out.append(row)
    out.sort(key=lambda r: (not r["verified"], STATES.index(r["state"]), r["icao"]))
    return {"configured": True, "rows": out, "regions": regions,
            "checked": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def matches(cells, working_dir: str = "") -> dict:
    """ENGINE COMMAND ``library_matches``: for every airport a build of
    ``cells`` (``[[lat, lon], ...]``) grades, the library's entries in
    match-tier order (:data:`TIERS`).

    :returns: ``{"configured", "airports": {icao: [{"tier", "entry",
        "pack", "version", "verified", "publisher", "solved_usable",
        "reason"}, ...]}}`` — an airport with no entry is left out.
    """
    if not _config.configured():
        return {"configured": False, "airports": {}}
    import O4_File_Names as FNAMES
    from o4_engine.build_airports import tile_airports
    from tile_bundle.export import load_tile
    xp_root = _xplane_root()
    if not xp_root:
        raise LibraryRefused("No X-Plane folder is set; installed packs cannot be read")
    law = _key.law_now(None)
    out: dict = {}
    for lat, lon in [(int(c[0]), int(c[1])) for c in cells or []]:
        index = _client.region_index(L.region_of(FNAMES.short_latlon(lat, lon)))
        tile = load_tile(lat, lon)
        for apt in tile_airports(lat, lon, ""):
            icao = apt["icao"]
            rows = index.get(icao)
            if not rows or icao in out:
                continue
            sig = _key.pack_now(xp_root, icao, lat, lon)
            local = {"signature": sig.get("signature"), "law": law,
                     "solve": _key.solve_now(tile)}
            listed = []
            ours = L.pack_slug(sig.get("pack", ""))
            for row in rows:
                tier = ("exact" if row["signature"] == sig.get("signature")
                        else "same_pack" if L.pack_slug(row["pack"]) == ours
                        else "other_pack")
                why = _key.first_difference(row, local)
                listed.append({"tier": tier, "entry": "%s/v%d" % (row["path"], row["latest"]),
                               "pack": row["pack"], "version": row["latest"],
                               "verified": bool(row.get("verified")),
                               "publisher": row.get("publisher", ""),
                               "solved_usable": why is None, "reason": why or ""})
            listed.sort(key=lambda m: (TIERS.index(m["tier"]), not m["verified"]))
            out[icao] = listed
    return {"configured": True, "airports": out}
