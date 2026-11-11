"""COMBINE PACKAGES (#2014; owner 2026-11-11T15:35Z: "we need to be able
to merge/combine packages"): several ``.xptb`` files → one.

The same rules as installing them one after another (:mod:`.install`),
decided without a user: every member is checked against its package's
hash; a file several hold is kept once when identical, else the NEWER
data wins (its recorded time); the inset index is merged row by row; a
patch two packages hold differently is the newer app version's, and two
different patches of one app version refuse the merge (install them one
by one and choose).  The tiles' airports, the sources and the cache
schemas are unioned (two packages reading one cache at different
schemas refuse); the licence follows the sources (one non-commercial
source marks the whole result).
"""
from __future__ import annotations

import hashlib
import os
import tarfile
import time

from . import PACKAGE_FORMAT, BundleRefused, inputs
from . import install as _install
from . import key as _key
from . import package as _package

__all__ = ["merge_packages"]


def _members(path: str, manifest: dict):
    """``(name, bytes)`` of every member, hash-checked."""
    files = manifest.get("files") or {}
    with tarfile.open(path, "r:*") as tar:
        for member in tar:
            if member.name in ("manifest.json", "ATTRIBUTION.txt"):
                continue
            data = tar.extractfile(member).read()
            entry = files.get(member.name) or {}
            if hashlib.sha256(data).hexdigest() != entry.get("sha256"):
                raise BundleRefused("%s in %s does not match its hash: the "
                                    "package is damaged" % (member.name, path))
            yield member.name, data


class _Union:
    """The combined members, tiles, sources and schemas."""

    def __init__(self):
        self.blobs, self.files, self.version = {}, {}, {}
        self.tiles, self.sources, self.schemas = {}, {}, {}
        self.only, self.engine = set(), ()

    def add(self, path: str, manifest: dict) -> None:
        version = _install.version_tuple(manifest.get("engine_version"))
        self.engine = max(self.engine, version)
        for name, value in ((manifest.get("key_parts") or {}).get("schemas") or {}).items():
            if self.schemas.setdefault(name, value) != value:
                raise BundleRefused("the packages read %s data at different "
                                    "versions (%s, %s)" % (name, self.schemas[name], value))
        for entry in manifest.get("tiles") or []:
            mine = self.tiles.setdefault(entry["tile"], dict(entry, airports={}))
            mine["airports"].update(entry.get("airports") or {})
        for source in manifest.get("sources") or []:
            self.sources.setdefault((source["kind"], source["provider"]), source)
        self.only = None if self.only is None or not manifest.get("airports_only") \
            else self.only | set(manifest["airports_only"])
        for name, data in _members(path, manifest):
            self._member(name, data, dict(manifest["files"][name]), version)

    def _member(self, name, data, entry, version) -> None:
        held = self.files.get(name)
        if held is None or self.blobs[name] == data:
            pass
        elif name.endswith(inputs.INSET_INDEX):
            newer = int(entry.get("mtime_ns") or 0) > int(held.get("mtime_ns") or 0)
            data = _install.merge_index(self.blobs[name], data, newer)
            entry["sha256"] = hashlib.sha256(data).hexdigest()
            entry["bytes"] = len(data)
        elif name.startswith("patches/"):
            if version == self.version[name]:
                raise BundleRefused("two packages carry different %s made by "
                                    "the same app version; install them one by "
                                    "one and choose" % name.rsplit("/", 1)[-1])
            if version < self.version[name]:
                return
        elif int(entry.get("mtime_ns") or 0) <= int(held.get("mtime_ns") or 0):
            return
        self.blobs[name], self.files[name], self.version[name] = data, entry, version


def merge_packages(paths, out: str, **fields) -> dict:
    """ENGINE COMMAND ``package_merge``: combine the packages ``paths``
    into ``out`` (a ``.xptb`` path or a folder); ``fields``: the result's
    :data:`.package.BRANDING` fields.

    :returns: ``{"path", "bytes", "data_bytes", "key", "files", "tiles",
        "noncommercial", "seconds"}``
    """
    from patch_library import terms as _terms
    t0 = time.time()
    if len(paths or ()) < 2:
        raise BundleRefused("Choose two or more packages to combine.")
    union = _Union()
    for path in paths:
        manifest = _install.read_manifest(path)
        if manifest["format"] != PACKAGE_FORMAT:
            raise BundleRefused("%s is a tile bundle; only packages (.xptb) "
                                "combine" % path)
        union.add(path, manifest)
    found = [union.sources[k] for k in sorted(union.sources)]
    parts = {"format": PACKAGE_FORMAT, "schemas": dict(sorted(union.schemas.items()))}
    manifest = {"format": PACKAGE_FORMAT, **_package.branding(fields),
                "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "engine_version": ".".join(str(n) for n in union.engine),
                "key": _key.bundle_key(parts), "key_parts": parts,
                "airports_only": sorted(union.only) if union.only else None,
                "tiles": [union.tiles[k] for k in sorted(union.tiles)],
                "sources": found, "licence": _terms.entry_licence(found),
                "noncommercial": any(s.get("noncommercial") for s in found),
                "imagery": "not included", "files": union.files,
                "data_bytes": sum(f["bytes"] for f in union.files.values())}
    out_path = _package.write(_package.destination_path(out, union.tiles), manifest, union.blobs)
    return {"path": out_path, "bytes": os.path.getsize(out_path),
            "data_bytes": manifest["data_bytes"], "key": manifest["key"],
            "files": len(union.files), "tiles": sorted(union.tiles),
            "noncommercial": manifest["noncommercial"],
            "seconds": round(time.time() - t0, 1)}
