"""OURAIRPORTS ``runways.csv`` — a runway-end cross-check source (owner
RULINGS 2026-10-25a, 26a; issue #1342; ``airport/runway_refs``).

Public domain (OurAirports, https://ourairports.com/data/), about 3 MB,
refreshed nightly upstream.  Per runway it carries each end's elevation in
feet (``le_elevation_ft`` / ``he_elevation_ft``), coordinate and displaced
threshold length.  Sparse for small fields: an end with no elevation is
not a record.

THE CACHE is ``<mod cache>/_runway_refs/ourairports/runways.csv`` with a
stamp ``runways.json`` (URL, sha256, bytes, fetch time, licence).  The
build only READS it (:func:`lookup`).  :func:`refresh` is the download;
its only caller is the harness scope ``--refresh-data runway_refs``.
"""
from __future__ import annotations

import csv
import io
import json
import os
import time
import typing as _t

from .file_hash import sha256_file
from .runway_ref_record import REFS_DIR, RefEnd

__all__ = ["NAME", "URL", "ATTRIBUTION", "LICENCE", "cache_path", "lookup",
           "parse_rows", "refresh"]

NAME = "ourairports"
URL = "https://davidmegginson.github.io/ourairports-data/runways.csv"
LICENCE = "Public domain (OurAirports open data, https://ourairports.com/data/)"
ATTRIBUTION = ("Runway end elevations cross-checked against OurAirports data "
               "(public domain), ourairports.com")
FT_TO_M = 0.3048
_FILE = "runways.csv"


def cache_path(mod_cache_root: str) -> str:
    """Where the cached ``runways.csv`` lives under ``mod_cache_root``."""
    return os.path.join(mod_cache_root, REFS_DIR, NAME, _FILE)


def _num(s: str | None) -> float | None:
    try:
        v = float(s) if s not in (None, "") else None
    except ValueError:
        return None
    return v


def parse_rows(header: str, lines: _t.Iterable[str], icao: str) -> dict[str, RefEnd]:
    """``{designator: RefEnd}`` for airport ``icao`` from CSV ``lines``
    (``header`` is the file's first line).  A closed runway, or an end
    with no elevation, gives no record."""
    out: dict[str, RefEnd] = {}
    rows = csv.DictReader(io.StringIO(header + "".join(lines)))
    want = icao.strip().upper()
    for r in rows:
        if (r.get("airport_ident") or "").strip().upper() != want:
            continue
        if (r.get("closed") or "0").strip() == "1":
            continue
        for p in ("le", "he"):
            desig = (r.get(f"{p}_ident") or "").strip().upper()
            elev = _num(r.get(f"{p}_elevation_ft"))
            if not desig or elev is None:
                continue
            out[desig] = RefEnd(desig, elev * FT_TO_M,
                                _num(r.get(f"{p}_latitude_deg")),
                                _num(r.get(f"{p}_longitude_deg")),
                                (_num(r.get(f"{p}_displaced_threshold_ft")) or 0.0) * FT_TO_M,
                                NAME)
    return out


def lookup(icao: str, mod_cache_root: str) -> dict[str, RefEnd]:
    """This airport's ends from the cache, ``{}`` with no cache.  The
    file is scanned for the quoted ident first (a 3 MB scan, no CSV parse
    of the other 47,000 rows)."""
    path = cache_path(mod_cache_root)
    if not os.path.isfile(path):
        return {}
    key = f'"{icao.strip().upper()}"'
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as fh:
        header = fh.readline()
        hits = [ln for ln in fh if key in ln]
    return parse_rows(header, hits, icao) if hits else {}


def refresh(mod_cache_root: str, fetch: _t.Callable[[str], bytes] | None = None,
            url: str = URL) -> dict:
    """THE DOWNLOAD — called only by the harness scope ``--refresh-data
    runway_refs`` (never by a build).  Writes ``runways.csv`` atomically
    beside its stamp and returns the stamp.  ``fetch(url) -> bytes`` is
    the transport (tests pass a fake; the default is ``urllib``)."""
    if fetch is None:
        def fetch(u: str) -> bytes:
            import urllib.request
            with urllib.request.urlopen(u, timeout=120) as resp:   # noqa: S310
                return resp.read()
    body = fetch(url)
    head = body[:400].decode("utf-8", "replace")
    if "airport_ident" not in head or "le_elevation_ft" not in head:
        raise ValueError(f"{url}: not an OurAirports runways.csv (header {head[:120]!r})")
    path = cache_path(mod_cache_root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "wb") as fh:
        fh.write(body)
    os.replace(tmp, path)
    stamp = {"source": NAME, "url": url, "sha256": sha256_file(path),
             "bytes": len(body), "fetched": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "licence": LICENCE, "attribution": ATTRIBUTION}
    stamp_path = os.path.splitext(path)[0] + ".json"
    with open(stamp_path + ".part", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(stamp, fh, indent=1)
    os.replace(stamp_path + ".part", stamp_path)
    return stamp
