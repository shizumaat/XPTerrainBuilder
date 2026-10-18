"""THE V2 STAGE CACHE'S STORE (stage-cache spec §4 key, §6 store, issue
#843) — content-keyed records of the airport build's stages, beside the
partition cache in the pack's mod-cache folder.

ONE FILE PER RECORD: ``o4_stage_<ICAO>_<stage>_<key[:16]>.cache``::

    MAGIC | u64 n | header (JSON, n bytes) | u64 m | witness (zlib pickle)
          | payload (zlib pickle)

The HEADER is readable without decompressing anything (§6: the #880 walk
reads headers only): ``stage``, ``key``, the ``recipe`` the key was taken
from (``inputs`` ``{name: digest}``, ``code``, ``env``, ``version``), the
``output_digest`` (the sha256 of the payload's pickle bytes — ONE hash is
both the payload's integrity check and the digest later stages chain on,
spec §4c), ``created`` and ``bytes``.  The WITNESS block holds what the
stage read that its key does not name — the law paths (``law/witness``),
the DEM questions (``airport/dem_record``) and the files opened
(``airport/file_witness``) — checked by the caller before the payload is
used.  Write = temp file + ``os.replace``; a record that does not parse,
names another key or version, or whose payload does not hash to its
header is REFUSED, never repaired.

THE CAP (RULINGS 2026-10-17a Q1, 18c (1)): 2 GB per mod-cache root,
oldest-``last_used`` first.  ``last_used`` lives in one small index file
per folder (``o4_stage.index.json``), so a hit does not rewrite its record.

The DIGEST every stage input is named by is :func:`digest_of` — the
sha256 of the object pickled at protocol 5.  It is stable across processes
for a product without a set of strings (dict order is insertion order; a
set of ints is ordered by its inserts).  The products digested FRESH on
every build (the ``Airport``'s fields) carry none; a stage output is named
by the digest its own record stores, never re-digested.  A product the
build derives BETWEEN stages is named by :func:`canonical_digest` (sets
sorted).  Neither is a value digest: the bytes follow object sharing, so
two equal products may digest apart — a miss, never a wrong hit.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import pickle
import struct
import time
import typing as _t
import zlib

__all__ = ["CACHE_VERSION", "CAP_BYTES", "MAGIC", "digest_of", "canonical_digest", "key_of",
           "entry_path", "encode", "write", "read_header", "read", "touch",
           "sweep", "peek", "Refused"]

#: Bump when the SHAPE of a record changes (the code digests cover a change
#: in what a stage produces).
CACHE_VERSION = 2   # the classify record carries its side state
                    # (``pipeline/front_cache.classify_side_state``); a v1
                    # record is a bare classification — refused, never repaired

#: RULINGS 2026-10-17a Q1 / 18c (1): the starting cap per mod-cache root.
CAP_BYTES = 2 * 1024 ** 3

MAGIC = b"O4V2STAGE\n"
_U64 = struct.Struct("<Q")
_ZLIB_LEVEL = 1
_INDEX = "o4_stage.index.json"
_PREFIX = "o4_stage_"
_SUFFIX = ".cache"


class Refused(Exception):
    """A record that exists and may not be served; ``str`` is the reason."""


def digest_of(obj: _t.Any) -> str:
    """sha256 of ``obj`` pickled at protocol 5 (module doc)."""
    return hashlib.sha256(pickle.dumps(obj, protocol=5)).hexdigest()


class _Canonical(pickle.Pickler):
    """A pickler that writes every set in sorted order (its own order is
    the process's hash seed's)."""

    def persistent_id(self, obj: _t.Any) -> _t.Any:
        if type(obj) in (set, frozenset):
            return ("set", tuple(sorted(obj, key=repr)))
        return None


def canonical_digest(obj: _t.Any) -> str:
    """:func:`digest_of` with every set sorted — stable across processes
    for any product, at ~4x the pickling cost (the build uses it for a
    product it derives between two stages, never for a stage output)."""
    buf = io.BytesIO()
    _Canonical(buf, protocol=5).dump(obj)
    return hashlib.sha256(buf.getvalue()).hexdigest()


def key_of(stage: str, recipe: _t.Mapping[str, _t.Any]) -> str:
    """The record key: sha256 over the canonical JSON of the stage name,
    :data:`CACHE_VERSION` and ``recipe`` (sorted keys, no whitespace)."""
    doc = {"stage": stage, "version": CACHE_VERSION, **recipe}
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":"),
                                     default=str).encode()).hexdigest()


def entry_path(folder: str, icao: str, stage: str, key: str) -> str:
    """Where the record of ``stage`` under ``key`` lives in ``folder``."""
    return os.path.join(folder, f"{_PREFIX}{icao}_{stage}_{key[:16]}{_SUFFIX}")


def encode(output: _t.Any) -> tuple[bytes, str]:
    """``(pickle bytes, output digest)`` of a stage's output — the one
    pickle the digest and the payload share."""
    blob = pickle.dumps(output, protocol=5)
    return blob, hashlib.sha256(blob).hexdigest()


def write(path: str, header: dict, witness: _t.Any, blob: bytes) -> int:
    """Store a record (temp + ``os.replace``) and return its size in bytes;
    ``0`` (never an exception) when it could not be written."""
    tmp = f"{path}.tmp{os.getpid()}"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        wit = zlib.compress(pickle.dumps(witness, protocol=5), _ZLIB_LEVEL)
        body = zlib.compress(blob, _ZLIB_LEVEL)
        head = json.dumps(header, sort_keys=True, default=str).encode()
        with open(tmp, "wb") as fh:
            fh.write(MAGIC)
            fh.write(_U64.pack(len(head)))
            fh.write(head)
            fh.write(_U64.pack(len(wit)))
            fh.write(wit)
            fh.write(body)
        os.replace(tmp, path)
        touch(path)
        return os.path.getsize(path)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return 0


def _head(fh: _t.BinaryIO) -> dict:
    if fh.read(len(MAGIC)) != MAGIC:
        raise Refused("format")
    (n,) = _U64.unpack(fh.read(_U64.size))
    head = json.loads(fh.read(n))
    if not isinstance(head, dict):
        raise Refused("format")
    return head


def read_header(path: str) -> dict | None:
    """The header of the record at ``path``, or ``None`` (absent,
    unreadable, not a record).  Decompresses nothing."""
    try:
        with open(path, "rb") as fh:
            return _head(fh)
    except Exception:
        return None


def read(path: str, key: str) -> tuple[dict, _t.Any, _t.Callable[[], _t.Any]]:
    """``(header, witness, load)`` of the record of ``key`` at ``path`` —
    ``load()`` decodes the payload, checking its sha256 against the
    header's ``output_digest`` first.  Raises :class:`Refused` (a stale,
    foreign or broken record) or ``FileNotFoundError`` (no record)."""
    with open(path, "rb") as fh:
        head = _head(fh)
        if head.get("version") != CACHE_VERSION:
            raise Refused(f"version {head.get('version')}")
        if head.get("key") != key:
            raise Refused("key")
        (m,) = _U64.unpack(fh.read(_U64.size))
        wit_raw = fh.read(m)
        body = fh.read()
    try:
        witness = pickle.loads(zlib.decompress(wit_raw))
    except Exception as exc:
        raise Refused(f"witness {type(exc).__name__}") from exc

    def load() -> _t.Any:
        try:
            blob = zlib.decompress(body)
        except zlib.error as exc:
            raise Refused("payload zlib") from exc
        if hashlib.sha256(blob).hexdigest() != head.get("output_digest"):
            raise Refused("payload_sha256")
        return pickle.loads(blob)
    return head, witness, load


def _index_path(folder: str) -> str:
    return os.path.join(folder, _INDEX)


def _load_index(folder: str) -> dict:
    try:
        with open(_index_path(folder), encoding="utf-8") as fh:
            got = json.load(fh)
        return got if isinstance(got, dict) else {}
    except Exception:
        return {}


def touch(path: str, when: float | None = None) -> None:
    """Record ``path`` as used now in its folder's index."""
    folder, name = os.path.split(path)
    idx = _load_index(folder)
    idx[name] = float(when if when is not None else time.time())
    tmp = f"{_index_path(folder)}.tmp{os.getpid()}"
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(idx, fh, sort_keys=True)
        os.replace(tmp, _index_path(folder))
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass


def _records(root: str) -> list[tuple[str, int, float]]:
    """``(path, bytes, last_used)`` of every record at most two levels
    under ``root`` (the root and its pack folders)."""
    out: list[tuple[str, int, float]] = []
    folders = [root]
    try:
        folders += [e.path for e in os.scandir(root) if e.is_dir()]
    except OSError:
        return out
    for folder in folders:
        try:
            names = [e for e in os.scandir(folder)
                     if e.name.startswith(_PREFIX) and e.name.endswith(_SUFFIX)]
        except OSError:
            continue
        if not names:
            continue
        idx = _load_index(folder)
        for e in names:
            try:
                st = e.stat()
            except OSError:
                continue
            out.append((e.path, int(st.st_size), float(idx.get(e.name, st.st_mtime))))
    return out


def sweep(root: str | None, cap: int = CAP_BYTES) -> list[str]:
    """Delete the oldest-used records under ``root`` until the rest fit in
    ``cap`` bytes; returns the paths deleted.  Only this cache's own files
    are ever touched."""
    if not root:
        return []
    recs = sorted(_records(root), key=lambda r: r[2])
    total = sum(r[1] for r in recs)
    gone: list[str] = []
    for path, size, _used in recs:
        if total <= cap:
            break
        try:
            os.remove(path)
            gone.append(path)
            total -= size
        except OSError:
            continue
    return gone


def peek(path: str) -> dict | None:
    """The header of a record (why a key missed, field by field), or ``None``."""
    return read_header(path)
