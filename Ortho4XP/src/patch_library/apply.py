"""DOWNLOAD AND LAY DOWN AN AIRPORT ENTRY (#1699 phase 2), or fall back.

1. The entry's manifest is fetched and its match key compared with this
   machine's (:mod:`.key`): the installed pack's signature, the
   auto-patch law and the tile's solve settings.
2. EXACT MATCH: every solved file is downloaded, checked against the
   manifest's hashes, decompressed, spelled with this machine's paths
   (``tile_bundle.paths``, a pack kept under another folder name renamed)
   and written into the tile's patch folder; the adoption record
   (:mod:`.adoption`) is written last.  The tile's next build reuses the
   patch and skips the airport's solve (the reuse gate reads the record).
3. ANY MISMATCH (design "Fallbacks", tier 3): no solved file is written,
   a stale adoption record is dropped, and the airport is solved locally
   at the next build — from the entry's edits when it has some.  The
   result says why in one sentence.
4. The user's own edits are never overwritten (#1699 decision 8): an
   entry's edited patch is laid down only where the user has none, and a
   conflict is reported; its hand-set pavement roles (#1697) likewise.

Nothing is applied without the user's choice (decision 7): this runs on
"Build" / "Update" in the app.  Downloading needs no account.
"""
from __future__ import annotations

import hashlib
import lzma
import os

from . import FORMAT, LibraryRefused
from . import adoption as _adoption
from . import client as _client
from . import key as _key
from . import layout as L

__all__ = ["apply_entry"]


def _local_key(tile, icao: str, xp_root: str) -> dict:
    """This machine's ``{"pack", "custom", "signature", "law", "solve"}``
    for ``icao`` built in ``tile``."""
    pack = _key.pack_now(xp_root, icao, tile.lat, tile.lon)
    return dict(pack, law=_key.law_now(tile), solve=_key.solve_now(tile))


def _member(manifest: dict, name: str, folder: str, pattern) -> str:
    """The plain file name an entry member ``name`` lands as; the
    library's checks are not trusted for it (a name that is not one an
    entry may carry, or not this airport's, refuses the apply)."""
    part, _sep, base = name.partition("/")
    stem = base[:-3] if base.endswith(".xz") else ""
    match = pattern.match(stem) if part == folder else None
    named = match and (match.groupdict().get("icao") or match.groupdict().get("plan"))
    if not named or named != manifest["icao"]:
        raise LibraryRefused("the entry holds %r, which no entry may carry" % name)
    return stem


def _download(rel: str, name: str, meta: dict) -> bytes:
    data = _client.fetch(rel + "/" + name)
    if data is None:
        raise LibraryRefused("the library has no %s for this entry" % name)
    if hashlib.sha256(data).hexdigest() != meta.get("sha256"):
        raise LibraryRefused("%s does not match the entry's hash" % name)
    raw = lzma.decompress(data)
    if hashlib.sha256(raw).hexdigest() != meta.get("raw_sha256"):
        raise LibraryRefused("%s's content does not match the entry" % name)
    return raw


def _write(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "wb") as handle:
        handle.write(data)
    os.replace(path + ".tmp", path)


def _lay_edits(rel, manifest, edits, patch_dir, change) -> dict:
    """The entry's edited patch, and its hand-set pavement roles (#1697,
    ``roles``: how many were laid), each where the user has none of their
    own."""
    import O4_File_Names as FNAMES
    from auto_patch_v2.airport import user_roles as _ur
    rows = (edits or {}).get("role_overrides") or ()
    roles = {"roles": _ur.lay_rows(patch_dir, manifest["icao"], rows)} if rows else {}
    name = (edits or {}).get("edited_patch")
    if not name:
        return {"edits": "none", **roles}
    target = os.path.join(patch_dir, FNAMES.edited_patch_name(manifest["icao"]))
    _member(manifest, name, L.EDITED, L.EDITED_NAME_RE)
    if os.path.isfile(target):
        return {"edits": "conflict", **roles,
                "conflict": "your own edits to %s stay; the library's edits "
                            "were not laid over them" % manifest["icao"]}
    from tile_bundle import paths as _paths
    raw = _download(rel, name, manifest["files"][name])
    _write(target, _paths.transform_file_bytes(target, raw, change))
    return {"edits": "laid", **roles}


def apply_entry(entry: str, working_dir: str = "") -> dict:
    """ENGINE COMMAND ``library_apply``: lay the library entry ``entry``
    (``entries/<ICAO>/<pack>/<sig>/v<N>``) into this installation.

    :returns: ``{"icao", "tile", "version", "mode": "solved" | "re-solve",
        "reason", "edits", "files", "bytes", "warning"}``
    """
    import O4_Config_Utils as CFG
    import O4_File_Names as FNAMES
    from tile_bundle import paths as _paths
    from tile_bundle.export import load_tile
    from tile_bundle.key import xplane_root
    where = L.parse_entry_dir(entry)
    if where is None:
        raise LibraryRefused("%r is not a library entry" % entry)
    manifest = _client.fetch_json(entry + "/" + L.MANIFEST)
    if not isinstance(manifest, dict) or manifest.get("format") != FORMAT:
        raise LibraryRefused("the library entry %s is missing or not one this "
                             "app reads" % entry)
    edits = _client.fetch_json(entry + "/" + L.EDITS) or {}
    lat, lon = FNAMES.parse_tile_key(manifest["tile"])
    custom = working_dir if working_dir and os.path.normpath(working_dir) != \
        os.path.normpath(FNAMES.Tile_dir) else ""
    tile = load_tile(lat, lon, os.path.join(custom, "") if custom else "")
    xp_root = xplane_root(tile)
    if not xp_root:
        raise LibraryRefused("No X-Plane folder is set; the pack cannot be read")
    icao = manifest["icao"]
    ours = _local_key(tile, icao, xp_root)
    why = _key.first_difference(manifest, ours)
    patch_dir = FNAMES.patch_dir(lat, lon)
    os.makedirs(patch_dir, exist_ok=True)
    pairs = _paths.roots(tile, CFG.custom_scenery_dir, xp_root)
    first: dict = {}
    for name, root in pairs:
        first.setdefault(name, root)
    renames = {manifest["pack"]["name"]: ours["pack"]} if (
        ours.get("pack") and manifest["pack"].get("custom")
        and manifest["pack"]["name"] != ours["pack"]) else {}

    def change(text: str) -> str:
        return _paths.detokenise_text(text, list(first.items()), renames)

    out = {"icao": icao, "tile": manifest["tile"], "version": manifest["version"],
           "entry": entry, "reason": why or "", "files": 0, "bytes": 0,
           "warning": ("This patch names engine %s or newer; update the app "
                       "to use it as solved." % manifest["min_engine"])
           if _key.engine_older(manifest.get("min_engine", "")) else ""}
    if why is not None:
        _adoption.remove(patch_dir, icao)
        out.update(mode="re-solve", **_lay_edits(entry, manifest, edits,
                                                 patch_dir, change))
        return out
    solved = sorted(n for n in manifest["files"] if n.startswith(L.SOLVED + "/"))
    names = {n: _member(manifest, n, L.SOLVED, L.SOLVED_NAME_RE) for n in solved}
    payload = {}
    for name in solved:                        # every hash before any write
        payload[name] = _download(entry, name, manifest["files"][name])
    for name in solved:
        target = os.path.join(patch_dir, names[name])
        data = _paths.transform_file_bytes(target, payload[name], change)
        _write(target, data)
        out["files"] += 1
        out["bytes"] += len(data)
    refused = os.path.join(patch_dir, "o4_v2_rebake_%s.screen.refused" % icao)
    if os.path.isfile(refused):
        os.remove(refused)
    index_rows = _client.region_index(L.region_of(manifest["tile"]))
    verified = any(r.get("signature") == manifest["signature"] and r.get("verified")
                   for r in index_rows.get(icao, []))
    _adoption.write(patch_dir, manifest, entry, verified)
    out.update(mode="solved", **_lay_edits(entry, manifest, edits, patch_dir, change))
    return out
