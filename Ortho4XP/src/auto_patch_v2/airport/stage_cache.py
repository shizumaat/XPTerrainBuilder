"""THE V2 STAGE CACHE'S STORE (stage-cache spec §4 key, §6 store, issue
#843) — content-keyed records of the airport build's stages, beside the
partition cache in the pack's mod-cache folder.

ONE FILE PER RECORD: ``o4_stage_<ICAO>_<stage>_<key[:16]>.cache``::

    MAGIC | u64 n | header (JSON, n bytes) | u64 m | witness (zlib pickle)
          | payload (zlib pickle)

The HEADER is readable without decompressing anything (§6: the #880 walk
reads headers only): ``stage``, ``key``, the ``recipe`` the key was taken
from (``inputs`` ``{name: digest}``, ``code``, ``env``, ``version``), the
``output_digest`` (the digest later stages chain on, spec §4c: for a
pickled record the sha256 of its pickle bytes, for a constraint record its
columnar digest), the ``payload_sha256`` (the payload bytes' own sha256,
checked on EVERY read — a mismatch is refused ``payload_sha256``),
``created``, ``last_used`` and ``bytes``.  The WITNESS block holds what the
stage read that its key does not name — the law paths (``law/witness``),
the DEM questions (``airport/dem_record``) and the files opened
(``airport/file_witness``) — checked by the caller before the payload is
used.  Write = temp file + ``os.replace``; a record that does not parse,
names another key or version, or whose payload does not hash to its
header is REFUSED, never repaired; a record whose stored recipe differs
from the one asked for is refused ``recipe:<field>`` (the first field that
differs, so a refusal says why).

THE CAP (RULINGS 2026-10-17a Q1, 18c (1)): 2 GB per mod-cache root,
oldest-``last_used`` first.  ``last_used`` lives in one small index file
per folder (``o4_stage.index.json``), so a hit does not rewrite its record;
the records one stage run wrote or read carry ONE ``last_used``
(:func:`touch_many`, spec §6 back half).

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
           "entry_path", "encode", "write", "read_header", "read", "touch", "touch_many",
           "sweep", "peek", "first_difference", "why_miss", "Refused"]

#: Bump when the SHAPE of a record changes (the code digests cover a change
#: in what a stage produces).
CACHE_VERSION = 3   # v3: the header carries ``payload_sha256`` beside
                    # ``output_digest`` (the back-half records, #843 step 9;
                    # v2: the classify record carries its side state)

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


def write(path: str, header: dict, witness: _t.Any, blob: bytes, *,
          used: bool = True) -> int:
    """Store a record (temp + ``os.replace``) and return its size in bytes;
    ``0`` (never an exception) when it could not be written.  The header
    gains ``payload_sha256`` (of ``blob``) unless it names one.  ``used``
    False leaves the index to the caller's :func:`touch_many`."""
    tmp = f"{path}.tmp{os.getpid()}"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        wit = zlib.compress(pickle.dumps(witness, protocol=5), _ZLIB_LEVEL)
        body = zlib.compress(blob, _ZLIB_LEVEL)
        header = {"payload_sha256": hashlib.sha256(blob).hexdigest(), **header}
        header.setdefault("last_used", header.get("created"))
        head = json.dumps(header, sort_keys=True, default=str).encode()
        with open(tmp, "wb") as fh:
            fh.write(MAGIC)
            fh.write(_U64.pack(len(head)))
            fh.write(head)
            fh.write(_U64.pack(len(wit)))
            fh.write(wit)
            fh.write(body)
        os.replace(tmp, path)
        if used:
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


def _recipe_field(stored: _t.Any, asked: _t.Any, at: str = "") -> str | None:
    """The first dotted field where two recipes differ, or ``None``."""
    if isinstance(stored, dict) and isinstance(asked, dict):
        for k in sorted(set(stored) | set(asked), key=str):
            got = _recipe_field(stored.get(k), asked.get(k), f"{at}.{k}" if at else str(k))
            if got is not None:
                return got
        return None
    return None if stored == asked else (at or "recipe")


def read(path: str, key: str, recipe: _t.Mapping[str, _t.Any] | None = None,
         decode: _t.Callable[[bytes], _t.Any] = pickle.loads
         ) -> tuple[dict, _t.Any, _t.Callable[[], _t.Any]]:
    """``(header, witness, load)`` of the record of ``key`` at ``path`` —
    ``load()`` returns ``decode(payload)``, checking the payload's sha256
    against the header's ``payload_sha256`` first.  ``recipe`` (the one the
    key was taken from) names the first differing field of a foreign
    record.  Raises :class:`Refused` (a stale, foreign or broken record) or
    ``FileNotFoundError`` (no record)."""
    with open(path, "rb") as fh:
        head = _head(fh)
        if head.get("version") != CACHE_VERSION:
            raise Refused(f"version {head.get('version')}")
        if recipe is not None:
            asked = json.loads(json.dumps(recipe, sort_keys=True, default=str))
            field = _recipe_field(head.get("recipe"), asked)
            if field is not None:
                raise Refused(f"recipe:{field}")
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
        if hashlib.sha256(blob).hexdigest() != head.get("payload_sha256"):
            raise Refused("payload_sha256")
        return decode(blob)
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
    _save_index(folder, idx)


def _save_index(folder: str, idx: dict) -> None:
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


def touch_many(paths: _t.Iterable[str], when: float | None = None) -> None:
    """Record every one of ``paths`` as used at ONE time (one stage run's
    records), one index write per folder."""
    now = float(when if when is not None else time.time())
    by_folder: dict[str, list[str]] = {}
    for p in paths:
        folder, name = os.path.split(p)
        by_folder.setdefault(folder, []).append(name)
    for folder, names in by_folder.items():
        idx = _load_index(folder)
        idx.update({n: now for n in names})
        _save_index(folder, idx)


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


#: the recipe's top-level fields in the order :func:`first_difference`
#: reads them (any other field after these, sorted)
_RECIPE_ORDER = ("stage", "version", "code", "env", "inputs")


def _flat(doc: _t.Mapping[str, _t.Any]) -> dict[str, _t.Any]:
    """``{dotted field: value}`` of a recipe, one level of nesting deep
    (``code.<stage>``, ``inputs.<name>``), in :data:`_RECIPE_ORDER`."""
    out: dict[str, _t.Any] = {}
    tops = [k for k in _RECIPE_ORDER if k in doc] + sorted(
        k for k in doc if k not in _RECIPE_ORDER)
    for top in tops:
        v = doc[top]
        if isinstance(v, _t.Mapping):
            for k in sorted(v):
                out[f"{top}.{k}"] = v[k]
        else:
            out[top] = v
    return out


def first_difference(header: _t.Mapping[str, _t.Any] | None, stage: str,
                     recipe: _t.Mapping[str, _t.Any]) -> str | None:
    """The FIRST recipe field in which the record ``header`` (a
    :func:`peek`) differs from the key a stage asked for (``stage`` +
    ``recipe`` as :func:`key_of` reads them) — ``version``, ``code.<s>``,
    ``env``, ``inputs.<name>`` … — or ``None`` when every field agrees
    (the same key: a record refused by its witnesses, not by its key).
    ``"format"`` for a header that is no record's."""
    if not isinstance(header, _t.Mapping):
        return "format"
    want = _flat({"stage": stage, "version": CACHE_VERSION, **recipe})
    had = _flat({"stage": header.get("stage"), "version": header.get("version"),
                 **dict(header.get("recipe") or {})})
    names = list(want) + [k for k in had if k not in want]
    for name in names:
        if json.dumps(want.get(name), sort_keys=True, default=str) != \
                json.dumps(had.get(name), sort_keys=True, default=str):
            return name
    return None


def why_miss(folder: str | None, icao: str, stage: str, key: str,
             recipe: _t.Mapping[str, _t.Any]) -> list[tuple[str, str | None]]:
    """``(record file name, first differing field)`` for every record of
    ``stage`` for ``icao`` in ``folder`` (headers only — nothing is
    decompressed); the field is ``None`` for the record of ``key`` itself
    (it exists and was refused by a witness or its payload)."""
    if not folder:
        return []
    head = f"{_PREFIX}{icao}_"
    try:
        names = sorted(e.name for e in os.scandir(folder)
                       if e.name.startswith(head) and e.name.endswith(_SUFFIX))
    except OSError:
        return []
    out: list[tuple[str, str | None]] = []
    for name in names:
        hd = peek(os.path.join(folder, name))
        if hd is not None and hd.get("stage") != stage:
            continue
        if hd is None and not name.startswith(f"{head}{stage}_"):
            continue
        same = hd is not None and hd.get("key") == key
        out.append((name, None if same else first_difference(hd, stage, recipe)))
    return out
