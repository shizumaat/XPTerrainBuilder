"""THE BACK HALF'S RECORDS (stage-cache spec §4b, §4b.8, §6 back half;
issue #843 step 9): ONE read-or-run for every record after the shape stage.

A later stage calls :func:`record` with its stage name, the digests of what
it is a function of and ``fn()`` (no argument: the back half reads the real
law, keyed by the WHOLE law's digest — spec §5's first landing; the row
witness is a later landing).  The record's key is
``stage | its stage_code digest | environment | law | inputs``
(``airport/stage_cache.key_of``); a hit is served when the header's recipe
is the one asked for, the payload hashes to its header and the record's
witnesses still hold, else ``fn()`` runs and its output is written.  The
answer is a :class:`Got`: the value, the record's key (``None`` when not
cached), its output digest and the digest of its DEM questions.

THE DEM WITNESS.  The back half's key names the ``Airport`` by its fields,
the DEM by nothing (``pipeline/front_cache``): every record is run with the
build's DEM recorder open and stores the questions it asked (and the files
it opened); a read holds only when today's DEM answers them with the same
bits.  A caller that runs records in a sequence whose memos one fills and
a later one reads (the constraint generators) chains the earlier records'
DEM digests into the later ones' inputs (``dem_before``), so a record
never hides a question a memo asked for it.

A :class:`Codec` turns an output into the payload bytes and its output
digest: :data:`PICKLE` (the sha256 of the pickle), or the columnar
constraint codec (``pipeline/constraint_records``).  Each record's entry
in ``report["cache"]["stages"]`` is ``hit`` / ``miss`` / ``refused:
<reason>`` / ``bypass: <reason>`` with the key prefix, the bytes and the
miss arm's ``encode_s`` / ``digest_s`` / ``write_s`` (spec §4b.8)."""
from __future__ import annotations

import hashlib
import pickle
import time
import typing as _t

from ..airport import dem_record as _dem
from ..airport import file_witness as _files
from ..airport import stage_cache as _store

__all__ = ["Codec", "PICKLE", "Got", "record"]


class Codec(_t.NamedTuple):
    """``encode(out) -> (payload bytes, digest())`` — the digest is a thunk,
    so its cost is clocked apart from the encode — and ``decode(bytes)``."""

    encode: _t.Callable[[_t.Any], tuple[bytes, _t.Callable[[], str]]]
    decode: _t.Callable[[bytes], _t.Any]


def _pickle_encode(out: _t.Any) -> tuple[bytes, _t.Callable[[], str]]:
    blob = pickle.dumps(out, protocol=5)
    return blob, lambda: hashlib.sha256(blob).hexdigest()


#: A record stored as its pickle, named by the pickle's sha256.
PICKLE = Codec(_pickle_encode, pickle.loads)


class Got(_t.NamedTuple):
    """A record's answer: ``value``; ``key`` (``None``: not cached this
    build); ``digest`` (its output digest); ``dem`` (the digest of the DEM
    questions it asked, for a caller's ``dem_before`` chain)."""

    value: _t.Any
    key: str | None
    digest: str | None
    dem: str


def record(fc: _t.Any, stage: str, inputs: _t.Mapping[str, str | None],
           fn: _t.Callable[[], _t.Any], *, code: str | None = None,
           codec: Codec = PICKLE,
           check: _t.Callable[[_t.Any], str | None] | None = None,
           bypass: str | None = None) -> Got:
    """``fn()``'s output for ``stage`` through the build's cache ``fc``
    (``pipeline/front_cache.FrontCache``), keyed on ``inputs``, the
    ``stage_code`` entry ``code`` (default: ``stage``), the environment and
    the whole law (module doc).  An input or code with no digest, a cache
    that is off or ``fc`` ``None`` runs ``fn()`` uncached.  ``check(value)``
    is asked of a decoded record before it is served: a reason refuses it
    (a reference that no longer holds; the solve's certificate) and its
    seconds are the entry's ``check_s``.  ``bypass`` names why this call
    may not be cached (``time_limit``): reported, and ``fn()`` runs."""
    if fc is None:
        return Got(fn(), None, None, "")
    name = fc.report_name(stage)
    if not fc.active:
        fc.bypassed(stage)
        return Got(fn(), None, None, "")
    rep: dict[str, _t.Any] = {}
    fc.report["stages"][name] = rep
    if bypass:
        rep["state"] = f"bypass: {bypass}"
        return Got(fn(), None, None, "")
    code = code or stage
    digest = fc.code.get(code)
    full = {**inputs, "law": fc.law_digest()}
    if digest is None or any(v is None for v in full.values()):
        rep["state"] = "bypass: undigested " + ",".join(
            k for k, v in {code: digest, **full}.items() if v is None)
        return Got(fn(), None, None, "")
    recipe = {"inputs": full, "code": {code: digest}, "env": fc.env}
    key = _store.key_of(stage, recipe)
    path = _store.entry_path(fc.folder, fc.icao, stage, key)
    rep["key"] = key[:16]
    got = _serve(fc, key, path, recipe, codec, check, rep)
    if got is not None:
        return got
    return _run(fc, stage, key, path, recipe, fn, codec, rep)


def _serve(fc: _t.Any, key: str, path: str, recipe: dict, codec: Codec,
           check: _t.Callable[[_t.Any], str | None] | None, rep: dict) -> Got | None:
    t = time.perf_counter()
    try:
        head, wit, load = _store.read(path, key, recipe, codec.decode)
        why = _files.holds(wit.get("files")) or _dem.holds(fc.dem_rec, wit.get("dem"))
        if why:
            raise _store.Refused(why)
        out = load()
        why = None
        if check is not None:
            t_check = time.perf_counter()
            why = check(out)
            rep["check_s"] = round(time.perf_counter() - t_check, 4)
        if why:
            raise _store.Refused(why)
    except FileNotFoundError:
        rep["state"] = "miss"
        return None
    except _store.Refused as exc:
        rep["state"] = f"refused: {exc}"
        return None
    except Exception as exc:                     # a record that will not decode
        rep["state"] = f"refused: {type(exc).__name__}"
        return None
    fc.note_used(path)
    rep.update(state="hit", read_s=round(time.perf_counter() - t, 4),
               bytes=int(head.get("bytes") or 0))
    return Got(out, key, head["output_digest"], str(head.get("dem_digest") or ""))


def _run(fc: _t.Any, stage: str, key: str, path: str, recipe: dict,
         fn: _t.Callable[[], _t.Any], codec: Codec, rep: dict) -> Got:
    fc.dem_rec.reset()
    fc.file_rec = _files.FileRecorder()
    fc.window(True)
    try:
        out = fn()
    finally:
        fc.window(False)
    witness = {"dem": fc.dem_rec.record(), "files": fc.file_rec.record()}
    opaque = fc.dem_rec.opaque()
    dem_d = _store.digest_of(witness["dem"])
    t = time.perf_counter()
    try:
        blob, digest_fn = codec.encode(out)
    except Exception as exc:                     # an output the codec refuses
        rep["state"] += f"; not written: {type(exc).__name__}"
        return Got(out, None, None, dem_d)
    rep["encode_s"] = round(time.perf_counter() - t, 4)
    t = time.perf_counter()
    digest = digest_fn()
    rep["digest_s"] = round(time.perf_counter() - t, 4)
    if opaque:
        rep["state"] += f"; not written: dem {opaque}"
        return Got(out, key, digest, dem_d)
    fc.write_async(path, fc.header(stage, key, recipe, digest, len(blob), dem_digest=dem_d),
                   witness, blob, rep)
    return Got(out, key, digest, dem_d)
