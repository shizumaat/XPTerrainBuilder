"""THE LIBRARY'S REGIONAL INDEX (#1699 phase 2) — stdlib only; the
library's workflow rebuilds it on every merge (``library_template/
.github/workflows/index.yml``), and the app reads it when it opens.

``index/<region>.json`` (``layout.index_path``)::

    {"format": "xptl-index-1", "region": "+40-130",
     "airports": {"KPDX": [            # one row per pack signature
        {"pack": str, "custom": bool, "kind": str, "signature": str,
         "tile": "+45-123", "latest": 2, "versions": [1, 2],
         "path": "entries/KPDX/<pack>/<sig12>",   # + "/v<latest>"
         "law": {...}, "solve": str, "min_engine": str,
         "publisher": str, "verified": bool, "published": str,
         "noncommercial": bool}]}}       # owner Q319: the latest's NC mark

A region holds every airport whose TILE lies in it, so the app fetches
only the regions where the user has packs or tiles.  Rows of one airport
are verified developers' first (owner: "listed first"), then the newest.
The index is DATA the app trusts only as a pointer: every file it then
downloads is checked against the entry's own manifest.

    python -m patch_library.index --library DIR
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import INDEX_FORMAT
from . import layout as L
from .checks import load_json, verified_for

__all__ = ["rebuild", "main"]


def _manifests(root: str):
    def folders(path):
        return sorted(n for n in os.listdir(path)
                      if os.path.isdir(os.path.join(path, n)))

    top = os.path.join(root, L.ENTRIES)
    for icao in folders(top) if os.path.isdir(top) else []:
        for pack in folders(os.path.join(top, icao)):
            for sig in folders(os.path.join(top, icao, pack)):
                folder = os.path.join(top, icao, pack, sig)
                for version in folders(folder):
                    rel = "/".join((L.ENTRIES, icao, pack, sig, version))
                    if L.parse_entry_dir(rel) is None:
                        continue
                    doc = load_json(os.path.join(folder, version, L.MANIFEST))
                    if isinstance(doc, dict):
                        yield rel, doc


def _rows(root: str) -> dict:
    """``{region: {icao: [row, ...]}}`` over every entry of the checkout."""
    publishers = load_json(os.path.join(root, L.PUBLISHERS), {})
    found: dict = {}
    for rel, doc in _manifests(root):
        where = L.parse_entry_dir(rel)
        key = (doc["icao"], doc["signature"])
        row = found.get(key)
        if row is None or doc["version"] > row["latest"]:
            versions = (row or {}).get("versions", [])
            row = {"pack": doc["pack"]["name"], "custom": bool(doc["pack"].get("custom")),
                   "kind": doc["pack"].get("kind", ""), "signature": doc["signature"],
                   "tile": doc["tile"], "latest": doc["version"],
                   "versions": versions, "path": rel.rsplit("/", 1)[0],
                   "law": doc["law"], "solve": doc["solve"],
                   "min_engine": doc["min_engine"],
                   "publisher": doc["publisher"],
                   "verified": verified_for(publishers, doc["publisher"],
                                            doc["icao"], doc["pack"]["name"]),
                   "published": doc.get("published", ""),
                   "noncommercial": bool(doc.get("noncommercial"))}
            found[key] = row
        row["versions"] = sorted(set(row["versions"]) | {where["version"]})
    out: dict = {}
    for (icao, _sig), row in sorted(found.items()):
        out.setdefault(L.region_of(row["tile"]), {}).setdefault(icao, []).append(row)
    for region in out.values():
        for icao_rows in region.values():
            icao_rows.sort(key=lambda r: r["published"], reverse=True)
            icao_rows.sort(key=lambda r: not r["verified"])     # stable
    return out


def rebuild(root: str) -> list:
    """Write ``index/<region>.json`` for every region with an entry and
    remove a region file no entry needs any more; returns the paths
    written (``/``-separated, relative to ``root``)."""
    regions = _rows(root)
    folder = os.path.join(root, L.INDEX)
    os.makedirs(folder, exist_ok=True)
    written = []
    for region, airports in sorted(regions.items()):
        rel = L.index_path(region)
        doc = {"format": INDEX_FORMAT, "region": region, "airports": airports}
        with open(os.path.join(root, *rel.split("/")), "w", encoding="utf-8",
                  newline="\n") as handle:
            json.dump(doc, handle, indent=1, sort_keys=True)
            handle.write("\n")
        written.append(rel)
    for name in os.listdir(folder):
        if name.endswith(".json") and name[:-5] not in regions:
            os.remove(os.path.join(folder, name))
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Rebuild the library index.")
    parser.add_argument("--library", required=True)
    args = parser.parse_args(argv)
    for rel in rebuild(args.library):
        print(rel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
