"""THE DEM A CACHED STAGE READ — every question, not only the samples
(stage-cache spec §4 "DEM samples", issue #843).

``dem_witness.DemWitness`` records the pack reading's questions, which all
go through ``z`` / ``z_many``.  The front-half stages ask more: the planar
stage reads the sea polygons, the flat-site detector the posting, the
source pixel and the core's own verdict, the road profile which tiles are
warm (census 2026-10-18, CYXY: ``classify`` z; ``planar`` z, z_many,
sea_geometry; ``flat_site`` core_flat_site, posting_m, source_pixel_m,
water_geometry, z_many; ``road_profile`` tile_of_many, warm_tiles, z_many;
``shapes`` provenance).  So :class:`DemRecorder` stands in for the DEM for
the whole build and, while it is :meth:`~DemRecorder.recording`, keeps

* every SAMPLE (``z`` / ``z_many``) in ``dem_witness``'s own record shape;
* every other METHOD CALL — its name, its pickled arguments and a digest
  of its answer;
* every plain ATTRIBUTE read, with a digest of its value;
* the composed TILES (a digest of each raster) when anything reaches for
  them directly (``dem_shared.share`` handing them to a pool worker).

:func:`holds` asks today's DEM every question again and holds only when
every answer has the same bits.  A record that cannot say what it read (an
answer that would not digest) is OPAQUE and is never stored.  Outside a
recording window the recorder is a plain pass-through; it reports the
DEM's own class and pickles as the DEM, so nothing a stage stores carries
it into a cache file or a worker.
"""
from __future__ import annotations

import hashlib
import pickle
import typing as _t

import numpy as np

from . import dem_witness as _wit

__all__ = ["DemRecorder", "holds", "answer_digest"]


def answer_digest(value: _t.Any) -> str:
    """sha256 of an answer: arrays by dtype, shape and bytes; a set sorted
    (its order is the process's); anything else pickled."""
    if isinstance(getattr(value, "alt", None), np.ndarray):
        return _tile_digest(value)              # a composed tile: its raster
    h = hashlib.sha256()
    if isinstance(value, np.ndarray):
        a = np.ascontiguousarray(value)
        h.update(f"nd{a.dtype.str}{a.shape}".encode())
        h.update(a.tobytes())
        return h.hexdigest()
    if isinstance(value, (set, frozenset)):
        value = ("set", sorted(value, key=repr))
    h.update(pickle.dumps(value, protocol=5))
    return h.hexdigest()


def _tile_digest(tile: _t.Any) -> str:
    if tile is None:
        return "none"
    alt = getattr(tile, "alt", None)
    rest = tuple(getattr(tile, k, None) for k in ("lat", "lon", "x0", "x1", "y0", "y1"))
    return answer_digest(("tile", rest, answer_digest(alt) if alt is not None else None))


class DemRecorder:
    """A ``DemSample`` that answers exactly as ``dem`` does and, while
    recording, remembers every question (module doc)."""

    def __init__(self, dem: _t.Any) -> None:
        object.__setattr__(self, "_o4r_dem", dem)
        object.__setattr__(self, "_o4r_on", False)
        self.reset()

    # ── the window ──────────────────────────────────────────────────
    def reset(self) -> None:
        """Forget every question asked so far."""
        object.__setattr__(self, "_o4r_samples", _wit.DemWitness(self._o4r_dem))
        object.__setattr__(self, "_o4r_calls", {})
        object.__setattr__(self, "_o4r_attrs", {})
        object.__setattr__(self, "_o4r_tiles", None)
        object.__setattr__(self, "_o4r_opaque", None)

    def recording(self, on: bool) -> None:
        """Open (``True``) or close the recording window."""
        object.__setattr__(self, "_o4r_on", bool(on))

    def target(self) -> _t.Any:
        """The real DEM."""
        return self._o4r_dem

    @property                                  # type: ignore[misc]
    def __class__(self) -> type:               # isinstance sees the DEM's class
        return type(self._o4r_dem)

    # ── the samples ─────────────────────────────────────────────────
    def z(self, x: float, y: float) -> float:
        return self._o4r_samples.z(x, y) if self._o4r_on else self._o4r_dem.z(x, y)

    def z_many(self, xs: _t.Any, ys: _t.Any) -> np.ndarray:
        return self._o4r_samples.z_many(xs, ys) if self._o4r_on else self._o4r_dem.z_many(xs, ys)

    # ── everything else ─────────────────────────────────────────────
    def __getattr__(self, name: str) -> _t.Any:
        value = getattr(self._o4r_dem, name)
        if not self._o4r_on:
            return value
        if name == "_tiles":
            self._note_tiles()
            return value
        if callable(value):
            return _Call(self, name, value)
        try:
            self._o4r_attrs[name] = answer_digest(value)
        except Exception as exc:            # an attribute that will not digest
            self._mark_opaque(f"attribute {name}: {type(exc).__name__}")
        return value

    def _note_tiles(self) -> None:
        tiles = getattr(self._o4r_dem, "_tiles", None) or {}
        got = dict(self._o4r_tiles or {})
        for key, tile in tiles.items():
            got.setdefault(repr(key), _tile_digest(tile))
        object.__setattr__(self, "_o4r_tiles", got)

    def _mark_opaque(self, why: str) -> None:
        if self._o4r_opaque is None:
            object.__setattr__(self, "_o4r_opaque", why)

    def __setattr__(self, name: str, value: _t.Any) -> None:
        setattr(self._o4r_dem, name, value)

    def __reduce_ex__(self, protocol: int) -> _t.Any:
        if self._o4r_on:                            # a worker reads what we cannot see
            self._note_tiles()
            self._mark_opaque_unless_tiles()
        return _identity, (self._o4r_dem,)

    def _mark_opaque_unless_tiles(self) -> None:
        if not hasattr(self._o4r_dem, "_tiles"):
            self._mark_opaque("pickled to a worker")

    # ── the record ──────────────────────────────────────────────────
    def opaque(self) -> str | None:
        """Why this window's record cannot be stored, or ``None``."""
        return self._o4r_opaque

    def record(self) -> dict:
        """``{"samples", "calls", "attrs", "tiles"}`` of the questions asked
        since the last :meth:`reset` (``samples`` is ``dem_witness``'s)."""
        return {"samples": self._o4r_samples.record(),
                "calls": [(n, a, d) for (n, a), d in sorted(self._o4r_calls.items())],
                "attrs": dict(sorted(self._o4r_attrs.items())),
                "tiles": dict(sorted((self._o4r_tiles or {}).items()))}

    def replay(self, record: dict | None) -> None:
        """Merge a stored record into this window (a stage served from
        cache: the next stage's witness names what it read)."""
        if not record:
            return
        s = record.get("samples") or {}
        xy = np.asarray(s.get("xy", np.empty((0, 2))), dtype=np.float64).reshape(-1, 2)
        z = np.asarray(s.get("z", np.empty(0)), dtype=np.float64).ravel()
        self._o4r_samples._xs.extend(xy[:, 0].tolist())
        self._o4r_samples._ys.extend(xy[:, 1].tolist())
        self._o4r_samples._zs.extend(z.tolist())
        for n, a, d in record.get("calls") or ():
            self._o4r_calls.setdefault((n, a), d)
        for n, d in (record.get("attrs") or {}).items():
            self._o4r_attrs.setdefault(n, d)
        if record.get("tiles"):
            got = dict(self._o4r_tiles or {})
            for k, d in record["tiles"].items():
                got.setdefault(k, d)
            object.__setattr__(self, "_o4r_tiles", got)


class _Call:
    """A DEM method, called through and recorded."""

    __slots__ = ("_rec", "_name", "_fn")

    def __init__(self, rec: DemRecorder, name: str, fn: _t.Callable) -> None:
        self._rec, self._name, self._fn = rec, name, fn

    def __call__(self, *args: _t.Any, **kw: _t.Any) -> _t.Any:
        out = self._fn(*args, **kw)
        try:
            blob = pickle.dumps((args, sorted(kw.items())), protocol=5)
            self._rec._o4r_calls[(self._name, blob)] = answer_digest(out)
        except Exception as exc:
            self._rec._mark_opaque(f"call {self._name}: {type(exc).__name__}")
        return out


def holds(dem: _t.Any, record: dict | None) -> str | None:
    """``None`` when ``dem`` answers every question of ``record`` with the
    same bits; else the first that differs (the refusal's reason)."""
    if record is None:
        return None
    target = dem.target() if isinstance(dem, DemRecorder) else dem
    if not _wit.holds(target, record.get("samples")):
        return "dem:samples"
    for name, blob, digest in record.get("calls") or ():
        try:
            args, kw = pickle.loads(blob)
            if answer_digest(getattr(target, name)(*args, **dict(kw))) != digest:
                return f"dem:{name}"
        except Exception:
            return f"dem:{name}"
    for name, digest in (record.get("attrs") or {}).items():
        try:
            if answer_digest(getattr(target, name)) != digest:
                return f"dem:{name}"
        except Exception:
            return f"dem:{name}"
    tiles = record.get("tiles") or {}
    if tiles:
        have = {repr(k): v for k, v in (getattr(target, "_tiles", None) or {}).items()}
        for key, digest in tiles.items():
            if key not in have or _tile_digest(have[key]) != digest:
                return f"dem:tile {key}"
    return None


def _identity(value: _t.Any) -> _t.Any:
    return value
