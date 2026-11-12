"""PACKAGES A SCENERY PACK SHIPS (RULINGS 2026-11-11m (4)/(5)): the
``.xptb`` files in an installed airport pack's ``XPTerrainBuilder``
folder (:mod:`.pack_dev`), applied automatically, with a notice, when a
tile holding the airport builds.

Owner, verbatim (16:54Z): "we should support storing .xptb files in their
scenery package's folder, so read them and apply them as we build tiles
on the fly. Then a developer could also release an updated on with an
update their scenery package, next run XPTerrainBuilder on the users
machine would recognize that there's a new .xptb file from last time and
apply the updates."  (16:56Z) "Auto with notice".

* :func:`scan` — every enabled pack's shipped packages and the tiles
  their manifests name (one ``listdir`` per pack; a manifest is read only
  where a package is);
* :func:`apply_for_tile` — at the start of a tile's vector step (every
  build: Build mode, a World job, the flight manager, on the fly;
  ``o4_engine.session``): each package naming the tile is checked against
  the pack installed here and, when it changed since it was last applied
  to the tile (by sha256), installed through ``install.install`` with
  ``source="pack:<pack>"``.  Returns the NOTICES the build posts
  (``PackPackage``): ``applied`` ("Using <pack>'s XPTerrainBuilder data
  for <ICAO>"), ``fallback`` (the pack's signature no longer matches the
  one the package was made against: the airport is processed as usual,
  logged, noticed once per package) and ``conflict``.
* PRECEDENCE (11m (5)): the user's custom patch > the pack's package >
  the auto patch.  An installed package patch is a custom patch, so it
  wins over the auto patch by itself; ``install`` keeps the user's own
  patch (silently when it is the newer one).  When the pack's patch is
  the NEWER one, the user's is still kept and the build posts
  ``conflict`` ONCE per package: the apps open the install sheet on it
  (the 11l (3) question, "Keep my patch" / "Back up mine and use the
  package's").  A later package from the same pack replaces the patch
  the earlier one installed without asking (the developer's update).
* :func:`stale_rows` / :func:`stale_tiles` — a tile built with an older
  package from the pack, or before the pack shipped one, is STALE
  (``O4_Tile_Staleness`` reason ``package``; the flight manager rebuilds
  a stale departure or destination): the next build applies the new one.

THE RECORD of what was applied is per tile, in its patch folder
(:data:`RECORD`): one tile builds in one process, so two builds never
write one record.  Nothing here downloads; the object-stage products are
never shipped (the pack partition is a pickle keyed to the maker's paths;
re-planning costs 0.4 s, measured for 11m).
"""
from __future__ import annotations

import json
import os
import re
import time

import O4_File_Names as FNAMES
from auto_patch_v2.airport.file_hash import sha256_file as _sha256_file

from . import BundleRefused
from . import pack_dev as _dev

__all__ = ["RECORD", "SOURCE_PREFIX", "APPLIED", "FALLBACK", "CONFLICT",
           "scan", "apply_for_tile", "stale_rows", "stale_tiles"]

#: Per tile, in its patch folder: the pack packages applied to it.
RECORD = "o4_pack_packages.json"
#: ``install``'s ``source`` for a pack's package: ``pack:<pack name>``.
SOURCE_PREFIX = "pack:"
#: The notices' states.
APPLIED, FALLBACK, CONFLICT = "applied", "fallback", "conflict"

#: A record's ``utc`` stamp.
_STAMP = "%Y-%m-%dT%H:%M:%SZ"

#: Our own packs (the World pack, ``zOrtho4XP_*`` overlays): never scanned.
_OURS_RE = re.compile(r"^(z|y)?Ortho4XP_|^XPTerrainBuilder", re.IGNORECASE)


def _scenery_dir(scenery_dir) -> str:
    if scenery_dir is None:
        import O4_Config_Utils as CFG
        scenery_dir = getattr(CFG, "custom_scenery_dir", "") or ""
    return scenery_dir


def scan(scenery_dir=None) -> list:
    """``[{"pack", "pack_root", "path", "tiles": {tile key: {icao:
    {"pack", "signature", …}}}, "warning"}]``: every package an ENABLED pack of
    ``scenery_dir`` (default: the configured Custom Scenery) ships.  A
    package whose manifest cannot be read is left out (logged once per
    build by :func:`apply_for_tile`'s caller)."""
    import O4_Scenery_Packs as SP

    from .export import licence_marks
    from .install import read_manifest
    scenery_dir = _scenery_dir(scenery_dir)
    try:
        names = sorted(os.listdir(scenery_dir)) if scenery_dir else []
    except OSError:
        return []
    disabled = SP.disabled_pack_names(scenery_dir)
    out = []
    for name in names:
        root = os.path.join(scenery_dir, name)
        if name in disabled or _OURS_RE.match(name) or not os.path.isdir(root):
            continue
        for path in _dev.shipped_packages(os.path.realpath(root)):
            try:
                manifest = read_manifest(path)
            except BundleRefused:
                continue
            out.append({"pack": name, "pack_root": root, "path": path,
                        "tiles": {e.get("tile", ""): e.get("airports") or {}
                                  for e in manifest.get("tiles") or []},
                        "warning": licence_marks(manifest.get("sources") or [])["warning"]})
    return out


def _record_path(lat: int, lon: int) -> str:
    return os.path.join(FNAMES.patch_dir(lat, lon), RECORD)


def _read_record(lat: int, lon: int) -> dict:
    return FNAMES.read_json_dict(_record_path(lat, lon))


def _write_record(lat: int, lon: int, doc: dict) -> None:
    path = _record_path(lat, lon)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as handle:
        json.dump(doc, handle, indent=1, sort_keys=True)
    os.replace(path + ".tmp", path)


def _record_key(row: dict) -> str:
    """One package of one pack: ``<pack>/<file name>``."""
    return "%s/%s" % (row["pack"], os.path.basename(row["path"]))


def _mismatches(row: dict, airports: dict, tile) -> list:
    """The airports whose pack installed here is not the one the package
    was made against (by signature); ``[]`` when every one matches."""
    from .key import pack_signature, xplane_root
    root = xplane_root(tile)
    out = []
    for icao, made in sorted(airports.items()):
        theirs = (made or {}).get("signature") or ""
        if not theirs:
            continue
        try:
            ours = pack_signature(root, icao, tile.lat, tile.lon) if root else {}
        except Exception:                   # an unreadable pack reads as absent
            ours = {}
        if ours.get("signature") != theirs:
            out.append(icao)
    return out


def _notice(row: dict, airports, state: str, text: str, tile) -> dict:
    return {"pack": row["pack"], "pack_root": row["pack_root"], "path": row["path"],
            "icao": ", ".join(sorted(airports)), "state": state, "text": text,
            "lat": int(tile.lat), "lon": int(tile.lon)}


def _texts(pack: str, icaos: str, warning: str = "") -> dict:
    """The notices' texts; ``warning`` (a personal package's, owner
    2026-11-12) follows the APPLIED one, so both apps show it."""
    return {
        APPLIED: "Using %s's XPTerrainBuilder data for %s%s" % (
            pack, icaos, (". " + warning) if warning else ""),
        FALLBACK: ("%s's XPTerrainBuilder data for %s was made for another "
                   "version of the pack; %s is built as usual" % (pack, icaos, icaos)),
        CONFLICT: ("%s ships a newer patch for %s than yours; yours is kept "
                   "until you choose" % (pack, icaos)),
    }


def _set_aside_installed(row: dict, tile) -> list:
    """FALLBACK: the patches an earlier package of this pack installed on
    the tile, unchanged since, are set aside (``….disabled``, as "Use
    auto patch" does) so the airport is processed as usual; a patch the
    user edited since is theirs and stays."""
    import O4_Custom_Patches as CUSTOM

    from .install import REGISTRY
    folder = FNAMES.patch_dir(tile.lat, tile.lon)
    registry = FNAMES.read_json_dict(os.path.join(folder, REGISTRY))
    moved = []
    for entry in registry.values():
        if not isinstance(entry, dict) or entry.get("source") != SOURCE_PREFIX + row["pack"]:
            continue
        for base, sha in sorted((entry.get("files") or {}).items()):
            path = os.path.join(folder, base)
            if os.path.isfile(path) and _sha256_file(path) == sha:
                moved.append(CUSTOM.set_aside(path))
    return moved


def _apply_one(row: dict, tile, record: dict, say) -> list:
    """The notices of one package for ``tile``; ``record`` is updated."""
    key = FNAMES.short_latlon(tile.lat, tile.lon)
    airports = row["tiles"].get(key) or {}
    texts = _texts(row["pack"], ", ".join(sorted(airports)) or "its airport",
                   row.get("warning") or "")
    held = record.setdefault(_record_key(row), {})
    sha = _sha256_file(row["path"])
    if _mismatches(row, airports, tile):
        say(0, "  [pack package] " + texts[FALLBACK])
        _set_aside_installed(row, tile)
        held.pop("sha256", None)
        if held.get("fallback") == sha:
            return []
        held.update(fallback=sha, utc=time.strftime(_STAMP, time.gmtime()))
        return [_notice(row, airports, FALLBACK, texts[FALLBACK], tile)]
    held.pop("fallback", None)
    notices = []
    if held.get("sha256") != sha:
        from .install import install
        done = install(row["path"], getattr(tile, "custom_build_dir", "") or "",
                       None, SOURCE_PREFIX + row["pack"])
        held.update(sha256=sha, utc=time.strftime(_STAMP, time.gmtime()),
                    installed=done.get("installed", 0))
        if done.get("conflicts") and held.get("asked") != sha:
            held["asked"] = sha
            say(0, "  [pack package] " + texts[CONFLICT])
            notices.append(_notice(row, [c["icao"] for c in done["conflicts"]],
                                   CONFLICT, texts[CONFLICT], tile))
    say(0, "  [pack package] " + texts[APPLIED])
    return [_notice(row, airports, APPLIED, texts[APPLIED], tile)] + notices


def apply_for_tile(tile, scenery_dir=None, say=None) -> list:
    """Apply every package the installed packs ship for ``tile`` (module
    doc); returns the notices.  Never raises: a package that will not
    install is one log line and the tile builds as usual."""
    if say is None:
        import O4_UI_Utils as UI
        say = UI.vprint
    key = FNAMES.short_latlon(tile.lat, tile.lon)
    rows = [r for r in scan(scenery_dir) if key in r["tiles"]]
    if not rows:
        return []
    record = _read_record(tile.lat, tile.lon)
    notices = []
    for row in rows:
        try:
            notices += _apply_one(row, tile, record, say)
        except Exception as error:          # the tile builds as usual
            say(0, "  [pack package] %s's package %s was not applied (%s)" % (
                row["pack"], os.path.basename(row["path"]), error))
    _write_record(tile.lat, tile.lon, record)
    return notices


def stale_rows(lat: int, lon: int, rows) -> list:
    """Staleness rows (``O4_Tile_Staleness``'s shape, reason ``package``)
    of a BUILT tile for the packages ``rows`` (:func:`scan`) naming it
    whose file is not the one last applied to it."""
    key = FNAMES.short_latlon(lat, lon)
    record = _read_record(lat, lon)
    out = []
    for row in rows:
        if key not in row["tiles"]:
            continue
        held = record.get(_record_key(row)) or {}
        try:
            sha = _sha256_file(row["path"])
        except OSError:
            continue
        if sha in (held.get("sha256"), held.get("fallback")):
            continue
        icaos = ", ".join(sorted(row["tiles"][key])) or "its airport"
        out.append({"icao": icaos, "reason": "package", "pack": row["pack"],
                    "now_pack": row["pack"],
                    "text": "%s: its pack %s ships %s XPTerrainBuilder data" % (
                        icaos, row["pack"], "new" if held else "its own")})
    return out


def stale_tiles(scenery_dir=None, tiles=None) -> set:
    """The ``(lat, lon)`` of ``tiles`` (default: every tile a shipped
    package names) a package has changed for since it was applied."""
    rows = scan(scenery_dir)
    named = {FNAMES.parse_tile_key(k) for r in rows for k in r["tiles"]} - {None}
    wanted = named if tiles is None else named & {(int(a), int(b)) for a, b in tiles}
    return {t for t in wanted if stale_rows(t[0], t[1], rows)}
