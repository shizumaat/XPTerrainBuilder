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

TIME.  The recipient builds the whole tile (every airport on it is graded
again, against the recipient's pack): the vector, mesh and masks steps
predicted by ``o4_engine.tile_time_model`` from this machine's recorded
builds (the tile's own, else every tile's, else its fixed ballpark),
plus the download of what the package leaves out at
:data:`DOWNLOAD_BYTES_PER_SECOND`.  Imagery is never included and never
counted.  Every number is an ESTIMATE and both apps say so.
"""
from __future__ import annotations

import lzma
import os

import O4_File_Names as FNAMES

from . import BundleRefused, inputs
from . import kinds as _kinds

__all__ = ["ESTIMATE_PRESET", "TEXT_PRESET", "TEXT", "WHOLE_BYTES",
           "SAMPLE_BYTES", "SAMPLE_WINDOWS", "MEMBER_OVERHEAD",
           "DOWNLOAD_BYTES_PER_SECOND", "BUILD_STEPS",
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

#: Advisory: elevation providers serve their rasters as windowed reads,
#: well under a line rate; 2 MB/s is the planning figure.
DOWNLOAD_BYTES_PER_SECOND = 2_000_000

#: The recipient's build steps counted (imagery is the recipient's own).
BUILD_STEPS = ("vector", "mesh", "masks")


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


def _rebuild_seconds(lat: int, lon: int) -> float:
    """The recipient's tile build without imagery (module doc)."""
    from o4_engine import tile_time_model
    steps = tile_time_model.predict_step_seconds(lat, lon, {}, list(BUILD_STEPS))
    return float(sum(steps.values()))


def _sizes(members) -> tuple:
    """``(raw bytes, estimated package bytes)`` of ``[(name, path)]``."""
    raw = packed = 0
    for _name, path in members:
        raw += os.path.getsize(path)
        packed += _compressed_bytes(path) + MEMBER_OVERHEAD
    return raw, packed


def _data_bytes(members) -> int:
    return sum(os.path.getsize(p) for n, p in members if n.startswith("data/"))


def _needs(kind: str, left: int) -> list:
    """The still-needs rows of ``kind`` leaving ``left`` bytes of data out."""
    if kind == _kinds.PATCH:
        return _kinds.still_needs(kind, data_bytes=left)
    if kind == _kinds.EXACT:
        return _kinds.still_needs(kind, other_airport_bytes=left)
    return _kinds.still_needs(kind)


def kind_figures(lat: int, lon: int, airports, kind: str, whole=None) -> dict:
    """One kind's row for tile (lat, lon): ``{"kind", "title",
    "explanation", "available", "why", "files", "data_bytes", "bytes",
    "download_bytes", "build_seconds", "still_needs", "figures"}``.  ``whole``: the
    tile's whole-tile members, when already listed."""
    members = inputs.files(lat, lon, airports, kind)
    whole = inputs.files(lat, lon) if whole is None else whole
    raw, packed = _sizes(members)
    carried = {n for n, _p in members}
    left = sum(os.path.getsize(p) for n, p in whole
               if n.startswith("data/") and n not in carried)
    needs = _needs(kind, left)
    download = sum(r["bytes"] or 0 for r in needs)
    why = ""
    if kind == _kinds.PATCH and not members:
        why = "%s has no custom patch or edits on this tile." % ", ".join(sorted(airports))
    elif kind != _kinds.PATCH and not any(n.startswith("data/OSM_data/") for n in carried):
        why = "The tile has no downloaded map data here; build it first."
    seconds = round(_rebuild_seconds(lat, lon) + download / DOWNLOAD_BYTES_PER_SECOND, 1)
    return {"kind": kind, "title": _kinds.TITLES[kind],
            "explanation": _kinds.EXPLANATIONS[kind], "available": not why,
            "why": why, "files": len(members), "data_bytes": raw, "bytes": packed,
            "download_bytes": download, "build_seconds": seconds,
            "still_needs": needs,
            "figures": _kinds.figures_text(packed, download, seconds)}


def sum_rows(rows: list) -> dict:
    """Several tiles' rows of one kind as one."""
    first = dict(rows[0])
    for key in ("files", "data_bytes", "bytes", "download_bytes", "build_seconds"):
        first[key] = sum(r[key] for r in rows)
    first["figures"] = _kinds.figures_text(first["bytes"], first["download_bytes"],
                                           first["build_seconds"])
    first["available"] = all(r["available"] for r in rows)
    first["why"] = next((r["why"] for r in rows if r["why"]), "")
    first["still_needs"] = _needs(first["kind"], first["download_bytes"])
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
    for lat, lon in pairs:
        whole = inputs.files(lat, lon)
        for kind in _kinds.KINDS:
            if kind in _kinds.AIRPORT_KINDS and chosen is None:
                continue
            per_kind[kind].append(kind_figures(
                lat, lon, None if kind == _kinds.TILE else chosen, kind, whole))
    return {"airport": icao, "tiles": [FNAMES.short_latlon(a, b) for a, b in pairs],
            "kinds": [sum_rows(per_kind[k]) for k in _kinds.KINDS if per_kind[k]]}
