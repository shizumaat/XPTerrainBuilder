"""EXPORT ESTIMATES (#2014 follow-up; owner 2026-11-11T16:10Z: "provide
options with explanations and estimated file sizes and rebuild times in
the export window"): for one airport, each package kind's size, what the
recipient still downloads, and how long the recipient's build takes —
computed before anything is saved, from the files that would go in.

SIZE.  The package is the members xz-compressed (``package.XZ_PRESET``).
Each member's compressed size is estimated from its own bytes at the fast
preset :data:`ESTIMATE_PRESET`.  A RASTER (or any binary file) up to
:data:`WHOLE_BYTES` is compressed whole, a larger one by
:data:`SAMPLE_WINDOWS` evenly spaced :data:`SAMPLE_BYTES` windows whose
ratio scales its size (measured on KLAX's tile, 2026-11-11: a lidar inset or ring cell is
already compressed, ratio 1.00 at every preset; a base ``.hgt`` 0.05
sampled against 0.031 whole at preset 9 — a sub-percent error of the
total).  A TEXT member (``.osm``, ``.json``: patches and their sidecars)
has long-range repeats no window or fast preset sees (KLAX's 20 MB axes
sidecar: preset 1 is 1.42x preset 9's size, a tuned fast filter 1.09x,
while a synthetic one came out 0.85x), so it is compressed whole at
:data:`TEXT_PRESET` (within 2 % of preset 9 on the axes sidecar, 4.2 s
against 4.9 s), once per file and change (:func:`_compressed_bytes`
remembers it).  Plus :data:`MEMBER_OVERHEAD` per
tar member.

TIME AND DOWNLOADS.  What the package leaves out of the tile's data is
priced at what its SOURCES cost to fetch (:mod:`.source_bytes`: Overpass
answers, provider windows, not our gridded products), and the
recipient's whole-tile build is priced step by step from this machine's
recorded builds (:mod:`.recipient_time`: map data and elevation for what
is left out, then map processing, every airport graded in parallel, the
mesh with its object stage, the masks), downloads included, with a
range.  The kinds differ by what they leave out: a whole tile leaves
nothing but imagery, an exact match the tile's other airports'
elevation, a patch-only package all the map and elevation data.
Imagery is never included and never counted.  Every number is an
ESTIMATE and both apps say so.
"""
from __future__ import annotations

import lzma
import os

import O4_File_Names as FNAMES

from . import BundleRefused, inputs
from . import kinds as _kinds
from . import recipient_time as _time
from . import source_bytes as _src

__all__ = ["ESTIMATE_PRESET", "TEXT_PRESET", "TEXT", "WHOLE_BYTES",
           "SAMPLE_BYTES", "SAMPLE_WINDOWS", "MEMBER_OVERHEAD",
           "kind_figures", "sum_rows", "estimate"]

ESTIMATE_PRESET = 1
TEXT_PRESET = 6
#: The members compressed whole as text (module doc).
TEXT = (".osm", ".json")
WHOLE_BYTES = 512 * 1024
SAMPLE_BYTES = 64 * 1024
SAMPLE_WINDOWS = 8
#: A tar header plus padding, on average.
MEMBER_OVERHEAD = 768


_KNOWN: dict = {}


def _compressed_bytes(path: str) -> int:
    """The estimated xz size of the file at ``path`` (module doc)."""
    stat = os.stat(path)
    key = (path, stat.st_size, stat.st_mtime_ns)
    if key not in _KNOWN:
        if len(_KNOWN) > 4096:
            _KNOWN.clear()
        _KNOWN[key] = _compressed(path, stat.st_size)
    return _KNOWN[key]


def _compressed(path: str, size: int) -> int:
    with open(path, "rb") as handle:
        if path.lower().endswith(TEXT):
            return len(lzma.compress(handle.read(), preset=TEXT_PRESET))
        if size <= WHOLE_BYTES:
            return len(lzma.compress(handle.read(), preset=ESTIMATE_PRESET))
        sample = b""
        step = (size - SAMPLE_BYTES) / (SAMPLE_WINDOWS - 1)
        for window in range(SAMPLE_WINDOWS):
            handle.seek(int(window * step))
            sample += handle.read(SAMPLE_BYTES)
    ratio = len(lzma.compress(sample, preset=ESTIMATE_PRESET)) / len(sample)
    return int(size * min(1.0, ratio))


def _processing(lat: int, lon: int) -> list:
    """The recipient's build rows of tile (lat, lon) (:mod:`.recipient_time`)."""
    return _time.processing_rows(lat, lon)


def _sizes(members) -> tuple:
    """``(raw bytes, estimated package bytes)`` of ``[(name, path)]``."""
    raw = packed = 0
    for _name, path in members:
        raw += os.path.getsize(path)
        packed += _compressed_bytes(path) + MEMBER_OVERHEAD
    return raw, packed


def _needs(kind: str, left: int) -> list:
    """The still-needs rows of ``kind`` leaving ``left`` bytes of data out."""
    if kind == _kinds.PATCH:
        return _kinds.still_needs(kind, data_bytes=left)
    if kind == _kinds.EXACT:
        return _kinds.still_needs(kind, other_airport_bytes=left)
    return _kinds.still_needs(kind)


def _figures(row: dict) -> str:
    return _kinds.figures_text(row["bytes"], row["download_bytes"], row["build_seconds"],
                               row["build_low"], row["build_high"],
                               row["download_seconds"],
                               _time.breakdown_text(row["breakdown"]))


def kind_figures(lat: int, lon: int, airports, kind: str, whole=None,
                 rate=None) -> dict:
    """One kind's row for tile (lat, lon): ``{"kind", "title",
    "explanation", "available", "why", "files", "data_bytes", "bytes",
    "download_bytes", "download_seconds", "build_seconds", "build_low",
    "build_high", "breakdown", "still_needs", "figures"}`` (``build_*``:
    until the tile is built, downloads included; ``breakdown``:
    :mod:`.recipient_time` rows).  ``whole``: the tile's whole-tile
    members, when already listed; ``rate``: ``recipient_time.grid_rate``,
    when already taken."""
    members = inputs.files(lat, lon, airports, kind)
    whole = inputs.files(lat, lon) if whole is None else whole
    raw, packed = _sizes(members)
    carried = {n for n, _p in members}
    left = _src.left_out([(n, p) for n, p in whole
                          if n.startswith("data/") and n not in carried])
    rows = _time.acquisition_rows(left, rate) + _processing(lat, lon)
    total = _time.totals(rows)
    why = ""
    if kind == _kinds.PATCH and not members:
        why = "%s has no custom patch or edits on this tile." % ", ".join(sorted(airports))
    elif kind != _kinds.PATCH and not any(n.startswith("data/OSM_data/") for n in carried):
        why = "The tile has no downloaded map data here; build it first."
    row = {"kind": kind, "title": _kinds.TITLES[kind],
           "explanation": _kinds.EXPLANATIONS[kind], "available": not why,
           "why": why, "files": len(members), "data_bytes": raw, "bytes": packed,
           "download_bytes": total["download_bytes"],
           "download_seconds": total["download_seconds"],
           "build_seconds": total["seconds"], "build_low": total["low"],
           "build_high": total["high"], "breakdown": rows,
           "still_needs": _needs(kind, total["download_bytes"])}
    row["figures"] = _figures(row)
    return row


def _merged(rows: list) -> list:
    """Several tiles' breakdown rows, one per step (summed)."""
    out: dict = {}
    for row in rows:
        for step in row["breakdown"]:
            if step["step"] not in out:
                out[step["step"]] = dict(step)
                continue
            for key in ("seconds", "low", "high", "download_bytes", "download_seconds"):
                out[step["step"]][key] += step[key]
    return list(out.values())


def sum_rows(rows: list) -> dict:
    """Several tiles' rows of one kind as one."""
    first = dict(rows[0])
    for key in ("files", "data_bytes", "bytes", "download_bytes", "download_seconds",
                "build_seconds", "build_low", "build_high"):
        first[key] = sum(r[key] for r in rows)
    first["breakdown"] = rows[0]["breakdown"] if len(rows) == 1 else _merged(rows)
    first["available"] = all(r["available"] for r in rows)
    first["why"] = next((r["why"] for r in rows if r["why"]), "")
    first["still_needs"] = _needs(first["kind"], first["download_bytes"])
    first["figures"] = _figures(first)
    return first


def estimate(tiles, airport: str = "") -> dict:
    """ENGINE COMMAND ``package_estimate`` (through ``o4_engine.library``):
    each kind's figures for exporting ``airport`` from ``tiles``
    (``[(lat, lon)]``; only the tiles that grade or hold it), or only the
    whole-tile row without an airport.

    :returns: ``{"airport", "tiles", "kinds": [row, …]}`` in
        :data:`.kinds.KINDS` order (rows of :func:`kind_figures`).
    """
    pairs = sorted({(int(a), int(b)) for a, b in tiles or ()})
    if not pairs:
        raise BundleRefused("Choose at least one tile to save in a package.")
    icao = str(airport or "").strip().upper()
    chosen = {icao} if icao else None
    per_kind: dict = {k: [] for k in _kinds.KINDS}
    rate = _time.grid_rate()
    for lat, lon in pairs:
        whole = inputs.files(lat, lon)
        for kind in _kinds.KINDS:
            if kind in _kinds.AIRPORT_KINDS and chosen is None:
                continue
            per_kind[kind].append(kind_figures(
                lat, lon, None if kind == _kinds.TILE else chosen, kind, whole,
                rate))
    return {"airport": icao, "tiles": [FNAMES.short_latlon(a, b) for a, b in pairs],
            "kinds": [sum_rows(per_kind[k]) for k in _kinds.KINDS if per_kind[k]]}
