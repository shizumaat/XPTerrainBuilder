"""INSTALL PACKAGE (#2014): what a ``.xptb`` (or a ``.xptbundle``) holds,
checked, shown, and laid into this installation's data folder.

:func:`plan` reads the package once through: its format and
COMPATIBILITY KEY against this engine (``package.key_parts``: a package
whose cache schemas this engine does not read is refused, in words),
every member's sha256 against the manifest (a damaged package is
refused before anything is written), each member's destination (a name
that would leave its folder, or a kind no package carries, refuses it),
and, per airport, whether the pack the package was made against is the
one installed here.  It writes nothing.  :func:`install` makes the same
pass writing each file beside its destination and, only when every
member checked, moves them all into place with their recorded times
(the inset stamps are keyed on the OSM layers' size and time).

MERGING (owner 2026-11-11T15:35Z and 15:38Z): a second package for a
tile combines with what is there.  Data is unioned: a file both hold is
kept when identical, else the NEWER data wins (the package's recorded
time against the file's); the inset index is merged row by row.  An
airport that already has a patch: when a package installed it (and it is
unchanged since), the patch of the newer app version wins; when the
user made or edited it, theirs is kept unless the package's is newer.
In the two cases left — two packages of one app version, or a package
patch newer than the user's — the user is asked per airport
(``choices``: ``"keep"``, the default, or ``"replace"``, which backs the
installed patch up beside itself as ``….disabled``, :data:`SET_ASIDE`).
Which package installed which patch is the tile's :data:`REGISTRY`.

A ``.xptbundle`` (``xptb-1``) is still read: its plan is its manifest's
details and key check, and its install is ``importer.import_bundle``.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tarfile
import time

import O4_File_Names as FNAMES

from . import FORMAT, PACKAGE_FORMAT, BundleRefused, inputs
from . import key as _key
from . import kinds as _kinds
from . import package as _package
from . import paths as _paths
from .export import load_tile

__all__ = ["REGISTRY", "CONFLICT_CHOICES", "SET_ASIDE", "read_manifest", "plan",
           "install", "version_tuple", "merge_index"]

#: Per tile, in its patch folder: which package installed which patch.
REGISTRY = "o4_installed_packages.json"

#: The answers to "this airport already has a patch": keep the one
#: installed (the default) or back it up and use the package's.
CONFLICT_CHOICES = ("keep", "replace")

#: Where a replaced patch goes: beside itself, renamed
#: (``O4_Custom_Patches.set_aside``, the rename "Use auto patch" makes);
#: renaming it back restores it.
SET_ASIDE = ".disabled"

_PART = ".xptb-part"


def read_manifest(path: str) -> dict:
    """The manifest of a package or a tile bundle (only that member)."""
    try:
        with tarfile.open(path, "r:*") as tar:
            doc = json.loads(tar.extractfile("manifest.json").read().decode("utf-8"))
    except (OSError, KeyError, ValueError, AttributeError, tarfile.TarError) as error:
        raise BundleRefused("%s is not an XPTerrainBuilder package (%s)"
                            % (os.path.basename(path), error)) from error
    if doc.get("format") not in (PACKAGE_FORMAT, FORMAT):
        raise BundleRefused("the package is format %r; this app reads %s and %s"
                            % (doc.get("format"), PACKAGE_FORMAT, FORMAT))
    return doc


def _tiles(manifest: dict, custom_build_dir: str) -> dict:
    out = {}
    for entry in manifest.get("tiles") or []:
        pair = FNAMES.parse_tile_key(str(entry.get("tile", "")))
        if pair is None:
            raise BundleRefused("the package names tile %r" % entry.get("tile"))
        out[entry["tile"]] = load_tile(pair[0], pair[1], custom_build_dir)
    return out


def _check_key(manifest: dict, tiles: dict) -> None:
    """Refuse a package whose cache schemas this engine does not read."""
    theirs = (manifest.get("key_parts") or {}).get("schemas") or {}
    ours = _package.key_parts(list(tiles.values()))["schemas"]
    for name in sorted(set(theirs) & set(ours)):
        if theirs[name] != ours[name]:
            raise BundleRefused(
                "This package does not match this app: its %s data is "
                "version %s and this app reads %s. Ask its maker for a "
                "package saved with this version of XPTerrainBuilder."
                % (name, theirs[name], ours[name]))


def version_tuple(text) -> tuple:
    """``"1.50.1901"`` -> ``(1, 50, 1901)``: app versions compared."""
    return tuple(int(n) for n in re.findall(r"\d+", str(text or "")))


def _sha(data: bytes) -> str:
    """The sha256 the manifest and the registry record."""
    return hashlib.sha256(data).hexdigest() if data is not None else ""


def _on_disk(path: str):
    """The bytes at ``path``, or None when nothing (readable) is there."""
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as handle:
        return handle.read()


def _registry(tile_key: str) -> dict:
    lat, lon = FNAMES.parse_tile_key(tile_key)
    return FNAMES.read_json_dict(os.path.join(FNAMES.patch_dir(lat, lon), REGISTRY))


def _airport_rows(entry: dict, tile) -> list:
    """Per airport: the pack the package was made against and how it
    compares with the one installed here."""
    root = _key.xplane_root(tile)
    rows = []
    for icao, theirs in sorted((entry.get("airports") or {}).items()):
        try:
            ours = _key.pack_signature(root, icao, tile.lat, tile.lon) if root else {}
        except Exception:                     # an unreadable pack reads as absent
            ours = {}
        if ours.get("signature") == theirs.get("signature"):
            match = "same"
        elif ours.get("pack"):
            match = "different"
        else:
            match = "absent"
        rows.append({"icao": icao, "pack": theirs.get("pack", ""),
                     "installed_pack": ours.get("pack", ""), "match": match})
    return rows


def merge_index(existing: bytes, incoming: bytes, newer: bool) -> bytes:
    """The inset index both hold, row by row: rows only one holds are
    kept, a row both hold is the newer data's."""
    mine = json.loads(existing.decode("utf-8"))
    theirs = json.loads(incoming.decode("utf-8"))
    merged = dict(theirs, **mine) if not newer else dict(mine, **theirs)
    return (json.dumps(merged, indent=2, sort_keys=True) + "\n").encode("utf-8")


class _Pass:
    """One read of the package: each member checked and decided."""

    def __init__(self, manifest, tiles, choices, write):
        self.manifest, self.tiles, self.write = manifest, tiles, write
        self.choices = {str(k).upper(): v for k, v in (choices or {}).items()
                        if v in CONFLICT_CHOICES}
        self.rows, self.asks, self.decided = [], [], {}
        self.registries = {k: _registry(k) for k in tiles}
        self.pairs = {}
        import O4_Config_Utils as CFG
        for key, tile in tiles.items():
            first = {}
            for name, root in _paths.roots(tile, CFG.custom_scenery_dir,
                                           _key.xplane_root(tile)):
                first.setdefault(name, root)
            self.pairs[key] = list(first.items())

    def member(self, name: str, data: bytes) -> None:
        entry = (self.manifest.get("files") or {}).get(name)
        try:
            dest = inputs.destination(name)
        except ValueError as error:
            raise BundleRefused(str(error)) from error
        if entry is None or _sha(data) != entry.get("sha256"):
            raise BundleRefused("%s does not match the package's hash: the "
                                "package is damaged" % name)
        tile_key = entry.get("tile") or ""
        pairs = self.pairs.get(tile_key) or next(iter(self.pairs.values()))
        data = _paths.transform_file_bytes(
            name, data, lambda t: _paths.detokenise_text(t, pairs))
        action, data, why = self._decide(name, dest, data, entry, tile_key)
        row = {"name": name, "destination": dest, "action": action,
               "why": why, "tile": tile_key, "mtime_ns": entry.get("mtime_ns"),
               "sha256": _sha(data)}
        if self.write and action in ("new", "update", "merge", "replace"):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest + _PART, "wb") as out:
                out.write(data)
        self.rows.append(row)

    def _decide(self, name, dest, data, entry, tile_key) -> tuple:
        existing = _on_disk(dest)
        if existing is None:
            return "new", data, ""
        if existing == data:
            return "same", data, ""
        if name.startswith("patches/"):
            return self._patch(name, dest, existing, data, tile_key)
        newer = int(entry.get("mtime_ns") or 0) > os.stat(dest).st_mtime_ns
        if name.endswith(inputs.INSET_INDEX):
            return "merge", merge_index(existing, data, newer), ""
        return ("update", data, "newer data") if newer else (
            "keep", data, "the data here is newer")

    def _patch(self, name, dest, existing, data, tile_key) -> tuple:
        base = os.path.basename(name)
        patch = base[: -len(".axes.json")] if base.endswith(".axes.json") else base
        if (tile_key, patch) not in self.decided:
            self.decided[(tile_key, patch)] = self._patch_decision(
                tile_key, patch, os.path.join(os.path.dirname(dest), patch))
        action, why = self.decided[(tile_key, patch)]
        return action, data, why

    def _patch_decision(self, tile_key, patch, dest) -> tuple:
        """``(action, why)`` for a package patch where one already is."""
        icao = inputs.member_icao(patch)
        record = (self.registries.get(tile_key) or {}).get(icao) or {}
        existing = _on_disk(dest)
        if existing is None:
            return "new", ""
        if (record.get("files") or {}).get(patch) == _sha(existing):
            ours = version_tuple(record.get("engine_version"))
            theirs = version_tuple(self.manifest.get("engine_version"))
            if theirs != ours:          # two packages: the newer engine's wins
                return (("replace", "made by a newer app version") if theirs > ours
                        else ("keep", "the installed package's is newer"))
            kind, installed = "package", record.get("title") or "another package"
        else:
            entry = (self.manifest.get("files") or {}).get(
                "patches/%s/%s" % (tile_key, patch)) or {}
            if int(entry.get("mtime_ns") or 0) <= os.stat(dest).st_mtime_ns:
                return "keep", "your own patch is newer"
            kind, installed = "custom", "your own patch"
        choice = self.choices.get(icao)
        if not any((a["tile"], a["icao"]) == (tile_key, icao) for a in self.asks):
            self.asks.append({"tile": tile_key, "icao": icao, "kind": kind,
                              "installed": installed, "choice": choice or "keep",
                              "backup": dest + SET_ASIDE})
        if choice == "replace":
            return "replace", "your choice: backed up as %s" % (
                os.path.basename(dest) + SET_ASIDE)
        return "keep", "your choice" if choice else "kept (the default)"


def _scan(path: str, manifest: dict, tiles: dict, choices, write: bool) -> _Pass:
    run = _Pass(manifest, tiles, choices, write)
    names = set()
    try:
        with tarfile.open(path, "r:*") as tar:
            for member in tar:
                if member.name in ("manifest.json", "ATTRIBUTION.txt"):
                    continue
                if not member.isfile():
                    raise BundleRefused("the package holds %s, which is not "
                                        "a file" % member.name)
                names.add(member.name)
                run.member(member.name, tar.extractfile(member).read())
    except BundleRefused:
        _discard(run.rows)
        raise
    except (OSError, tarfile.TarError, ValueError) as error:
        _discard(run.rows)
        raise BundleRefused("the package could not be read (%s)" % error) from error
    if names != set(manifest.get("files") or {}):
        _discard(run.rows)
        raise BundleRefused("the package's files are not the ones its "
                            "manifest lists")
    return run


def _discard(rows) -> None:
    for row in rows:
        try:
            os.unlink(row["destination"] + _PART)
        except OSError:
            pass


def _kind_lines(details: dict) -> list:
    """What kind of package it is, what a build still downloads, and the
    maker's estimate of the build (:mod:`.kinds`, :mod:`.estimate`)."""
    kind = details.get("kind")
    if kind not in _kinds.TITLES:
        return []
    lines = ["%s: %s" % (_kinds.TITLES[kind], _kinds.EXPLANATIONS[kind])]
    needs = [n["text"] for n in details.get("still_needs") or []]
    if needs:
        lines.append("Building still downloads: " + "; ".join(needs) + ".")
    seconds = (details.get("estimate") or {}).get("build_seconds")
    if seconds:
        lines.append("Estimated build time (without imagery): about %d min."
                     % max(1, round(seconds / 60.0)))
    return lines


def _summary(details: dict) -> list:
    lines = ["%s%s" % (details["title"] or "XPTerrainBuilder package",
                       " by " + details["creator"] if details["creator"] else "")]
    lines += _kind_lines(details)
    for tile in details["tiles"]:
        airports = ", ".join("%s (%s)" % (a["icao"], {
            "same": "matches your installed pack",
            "different": "your pack differs; the build solves against yours",
            "absent": "made with %s, not installed here" % (a["pack"] or "Global Airports"),
        }[a["match"]]) for a in tile["airports"]) or "no airports"
        lines.append("Tile %s: %s" % (tile["tile"], airports))
    counts = details["counts"]
    lines.append("%d files, %s of map and elevation data (%d new, %d updated, "
                 "%d already here, %d kept)" % (
                     details["files"], _kinds.size_text(details["data_bytes"]),
                     counts.get("new", 0), counts.get("update", 0)
                     + counts.get("merge", 0) + counts.get("replace", 0),
                     counts.get("same", 0), counts.get("keep", 0)))
    lines += ["Kept: %s — %s" % (r["name"].rsplit("/", 1)[-1], r["why"])
              for r in details["kept_patches"]]
    lines += ["%s already has %s; the package's is newer. %s" % (
        a["icao"], a["installed"], "It will be backed up as %s and the "
        "package's used." % os.path.basename(a["backup"]) if a["choice"] == "replace"
        else "It is kept unless you choose the package's.")
        for a in details["conflicts"]]
    if details["noncommercial"]:
        lines.append("Non-commercial: a source allows non-commercial use only.")
    lines.append("Imagery is not included: building the tile downloads it.")
    return lines


def _details(path: str, manifest: dict, tiles: dict, run: _Pass) -> dict:
    counts: dict = {}
    for row in run.rows:
        counts[row["action"]] = counts.get(row["action"], 0) + 1
    out = {"path": path, "format": manifest["format"], "legacy": False,
           "key": manifest.get("key", ""),
           **{k: manifest.get(k) or "" for k in _package.BRANDING},
           "created": manifest.get("created", ""),
           "engine_version": manifest.get("engine_version", ""),
           "airports_only": manifest.get("airports_only"),
           "kind": manifest.get("kind") or "",
           "still_needs": manifest.get("still_needs") or [],
           "estimate": manifest.get("estimate") or {},
           "tiles": [{"tile": e["tile"], "airports": _airport_rows(e, tiles[e["tile"]])}
                     for e in manifest.get("tiles") or []],
           "sources": manifest.get("sources") or [],
           "licence": manifest.get("licence", ""),
           "noncommercial": bool(manifest.get("noncommercial")),
           "bytes": os.path.getsize(path),
           "data_bytes": int(manifest.get("data_bytes") or 0),
           "files": len(run.rows), "counts": counts,
           "kept_patches": [r for r in run.rows if r["action"] == "keep"
                            and r["name"].startswith("patches/")],
           "conflicts": run.asks}
    out["summary"] = _summary(out)
    return out


def _legacy_plan(path: str, manifest: dict, custom_build_dir: str) -> dict:
    tiles = _tiles(manifest, custom_build_dir)
    tile = tiles[manifest["tile"]] if manifest.get("tile") in tiles else load_tile(
        int(manifest["tile"][:3]), int(manifest["tile"][3:]), custom_build_dir)
    why = _key.first_difference(manifest.get("key_parts") or {}, _key.key_parts(tile))
    if why:
        raise BundleRefused("This bundle does not match your installation: " + why + ".")
    airports = sorted(manifest.get("airports") or {})
    return {"path": path, "format": FORMAT, "legacy": True,
            "key": manifest.get("key", ""), "title": "", "creator": "",
            "notes": "", "url": "", "tiles": [{"tile": manifest["tile"], "airports": [
                {"icao": a, "pack": (manifest["airports"][a] or {}).get("pack", ""),
                 "installed_pack": "", "match": "same"} for a in airports]}],
            "sources": manifest.get("sources") or [],
            "licence": manifest.get("licence", ""),
            "noncommercial": bool(manifest.get("noncommercial")),
            "bytes": os.path.getsize(path), "files": len(manifest.get("files") or {}),
            "conflicts": [], "summary": [
                "Tile bundle for %s (mesh, masks and solved airports)" % manifest["tile"],
                "Airports: " + (", ".join(airports) or "none"),
                "Imagery is not included: building the tile downloads it."]}


def plan(path: str, custom_build_dir: str = "", choices=None) -> dict:
    """ENGINE COMMAND ``package_plan``: what installing ``path`` would do.
    Writes nothing.

    :returns: ``{"path", "format", "legacy", "key", "title", "creator",
        "notes", "url", "tiles": [{"tile", "airports": [{"icao", "pack",
        "installed_pack", "match"}]}], "sources", "licence",
        "noncommercial", "bytes", "files", "conflicts": [{"tile", "icao",
        "kind" ("custom" or "package"), "installed", "choice", "backup"}],
        "summary", …}``.  ``choices`` (``{icao: "keep" | "replace"}``)
        answers the conflicts; an unanswered one keeps the installed patch.
    :raises BundleRefused: not a package, an incompatible key, or damage.
    """
    manifest = read_manifest(path)
    if manifest["format"] == FORMAT:
        manifest.setdefault("tiles", [{"tile": manifest.get("tile", "")}])
        return _legacy_plan(path, manifest, custom_build_dir)
    tiles = _tiles(manifest, custom_build_dir)
    _check_key(manifest, tiles)
    return _details(path, manifest, tiles, _scan(path, manifest, tiles, choices, False))


def _record(run: _Pass, manifest: dict) -> None:
    """The tiles' :data:`REGISTRY`: the patches this package installed."""
    for key in run.tiles:
        doc = run.registries.get(key) or {}
        for row in run.rows:
            if row["tile"] != key or not row["name"].startswith("patches/") \
                    or row["action"] not in ("new", "same", "replace"):
                continue
            base = row["name"].rsplit("/", 1)[-1]
            icao = inputs.member_icao(base)
            entry = doc.setdefault(icao, {"files": {}})
            entry.update(package=manifest.get("key", ""), title=manifest.get("title", ""),
                         engine_version=manifest.get("engine_version", ""),
                         created=manifest.get("created", ""))
            entry["files"][base] = row["sha256"]
        if doc:
            folder = FNAMES.patch_dir(*FNAMES.parse_tile_key(key))
            os.makedirs(folder, exist_ok=True)
            with open(os.path.join(folder, REGISTRY), "w", encoding="utf-8",
                      newline="\n") as handle:
                json.dump(doc, handle, indent=1, sort_keys=True)


def _place(rows) -> int:
    """Move every written file into place with its recorded time."""
    import O4_Custom_Patches as CUSTOM
    placed = 0
    for row in rows:
        part = row["destination"] + _PART
        if not os.path.exists(part):
            continue
        if row["action"] == "replace":
            CUSTOM.set_aside(row["destination"])
        os.replace(part, row["destination"])
        if row["mtime_ns"] and row["action"] != "merge":
            os.utime(row["destination"], ns=(row["mtime_ns"], row["mtime_ns"]))
        placed += 1
    return placed


def _downloads_left(tile) -> list:
    """The subsystems whose fetch-admission predicate says ``tile``'s
    vector step would still download (``o4_engine.parallel``)."""
    from o4_engine import parallel
    parallel.preload_cache_predicates()
    return parallel.uncached_subsystems(tile, "vector")


def install(path: str, custom_build_dir: str = "", choices=None) -> dict:
    """ENGINE COMMAND ``package_install``: install ``path`` (module doc).

    :returns: :func:`plan`'s details with ``"installed"`` (files placed),
        ``"downloads_left"`` (``{tile: [subsystem, …]}``, empty when the
        tiles' rebuild downloads nothing but imagery) and ``"seconds"``.
    :raises BundleRefused: as :func:`plan`.
    """
    t0 = time.time()
    manifest = read_manifest(path)
    if manifest["format"] == FORMAT:
        from . import importer
        details = plan(path, custom_build_dir)
        details.update(importer.import_bundle(path, custom_build_dir))
        return details
    tiles = _tiles(manifest, custom_build_dir)
    _check_key(manifest, tiles)
    run = _scan(path, manifest, tiles, choices, True)
    details = _details(path, manifest, tiles, run)
    details["installed"] = _place(run.rows)
    _record(run, manifest)
    details["downloads_left"] = {key: _downloads_left(tile) for key, tile in tiles.items()}
    details["seconds"] = round(time.time() - t0, 1)
    return details
