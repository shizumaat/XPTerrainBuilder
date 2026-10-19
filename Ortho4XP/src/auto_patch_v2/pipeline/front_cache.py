"""THE FRONT HALF THROUGH THE STAGE CACHE (stage-cache spec §4, §5, §6,
§10 step 4; issue #843): classify, planar, flat_site, road_profile and the
shape stage, each served from its record when its key and its witnesses
answer the same today, else run and recorded.

ONE OBJECT PER BUILD (:class:`FrontCache`).  ``pipeline/build.py`` hands
each stage to :meth:`FrontCache.run` as ``fn(law)`` with the digests of
what the stage is a function of; the cache composes the key (the stage's
``stage_code`` digest — plus the target channels' for the shape stage —,
the environment's digest, the input digests), reads the record and checks
its witnesses, or runs ``fn`` and writes one.  A stage's output is named
downstream by the digest its record stores (§4c output-digest chaining),
so a stage that re-runs and produces the same record leaves the next one a
hit.

THE WITNESSES ARE CUMULATIVE.  One law recorder (``law/witness``), one DEM
recorder (``airport/dem_record``, standing in for the airport's DEM for the
whole build) and one file recorder (``airport/file_witness``) are open from
the classify stage to the end of the shape stage, target channels
included; a stage's witness is everything they hold at its end, and a hit
replays its stored witness into them.  A memo one stage fills and a later
one reads therefore never hides a read (spec §5's memo rule, met by
construction for the front half).

THE PREFIX RE-RUNS (spec §4b.3) go through the same records: each run
:meth:`FrontCache.reopen` s the window (a fresh DEM and file record; the
law recorder stays one for the build, so a re-run's witness is cumulative
over every run before it — narrower, never wider) and names its stages in
the report under its own :attr:`FrontCache.tag`.  The back half's records
(``pipeline/back_cache.py``) share this object's folder, environment,
writer and report.

WHAT IS NEVER CACHED: a build with ``Config.xplat_dump`` (the release gate
measures the programme, §7), an airport whose pack reading has no
fingerprint while it places resolved objects (its ``ResourceCache`` reads
files no key names), and a stage whose code has no digest.  ``O4_V2_STAGE_
CACHE=0`` (read in ``auto_patch/engine_v2.py`` → ``Config.stage_cache``)
turns the whole cache off; off, the build runs exactly the uncached path.
"""
from __future__ import annotations

import concurrent.futures as _cf
import dataclasses as _dc
import hashlib
import json
import os
import pickle as _pickle
import time
import typing as _t

from ..airport import dem_record as _dem
from ..airport import file_witness as _files
from ..airport import partition_cache as _pcache
from ..airport import stage_cache as _store
from ..law import witness as _law
from . import stage_code as _code
from . import xplat as _xplat

__all__ = ["FrontCache", "stage_folder", "classify_side_state",
           "install_classify_side_state"]

#: The extra code a stage's key carries beyond its own closure.
_EXTRA_CODE: dict[str, tuple[str, ...]] = {"shapes": ("channels",)}

#: The airport fields named by something other than their pickle: the DEM
#: (witnessed by its answers) and the partition (by its reading digest).
_SPECIAL_FIELDS = ("dem", "partition")


def stage_folder(airport: _t.Any, mod_cache_root: str | None) -> str | None:
    """The folder the airport's records live in: the pack's mod-cache folder
    (beside the partition cache), the root itself for an airport with no
    pack name, ``None`` without a mod-cache root."""
    if not mod_cache_root:
        return None
    name = getattr(getattr(airport, "pack", None), "name", None)
    if not name:
        return mod_cache_root
    from ..airport import dsf as _dsf
    return _dsf.mod_cache_dir(mod_cache_root, name)


#: THE CLASSIFY STAGE'S SIDE STATE: module globals ``classify`` fills that
#: a LATER stage reads — ``pipeline/publication._pad_refusals`` writes them
#: into the sidecar's ``pad_refusals``.  (The spec's census, §3, ruled
#: ``CLUSTER_PADS`` "not carried, tools only"; the closing HECA build's hit
#: arm emptied ``pad_refusals`` and found the reader.)  Carried with the
#: classify record and installed on a hit and a miss alike.
_CLASSIFY_SIDE = ("CLUSTER_PADS", "PAD_REFUSED")


def classify_side_state() -> dict[str, _t.Any]:
    """A deep copy of :data:`_CLASSIFY_SIDE` as ``classify`` left them."""
    import copy

    from ..classify import evidence as _ev
    return {k: copy.deepcopy(getattr(_ev, k)) for k in _CLASSIFY_SIDE}


def install_classify_side_state(state: _t.Mapping[str, _t.Any]) -> None:
    """Put a recorded side state back into the module globals, in place."""
    import copy

    from ..classify import evidence as _ev
    for k in _CLASSIFY_SIDE:
        live = getattr(_ev, k)
        live.clear()
        live.update(copy.deepcopy(dict(state.get(k) or {})))


def _resource_stamps(airport: _t.Any) -> str:
    """sha256 of ``(path, size, mtime_ns)`` of every resource a placement of
    ``airport`` resolves to (``-1`` for one that is gone)."""
    seen: dict[str, tuple[int, int]] = {}
    for o in getattr(airport, "dsf_objects", None) or ():
        p = getattr(o, "resolved_path", None)
        if not p or str(p) in seen:
            continue
        try:
            st = os.stat(str(p))
            seen[str(p)] = (int(st.st_size), int(st.st_mtime_ns))
        except OSError:
            seen[str(p)] = (-1, 0)
    return _sha(*(f"{p}:{a}:{b}" for p, (a, b) in sorted(seen.items())))


def _sha(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode())
        h.update(b"\0")
    return h.hexdigest()


class FrontCache:
    """The front half's records for one build (module doc)."""

    def __init__(self, icao: str, airport: _t.Any, law: _t.Any, *, enabled: bool,
                 mod_cache_root: str | None, pack: _t.Any = None,
                 bypass: str | None = None) -> None:
        self.icao = icao
        self.real_law = law
        self.root = mod_cache_root
        self.folder = stage_folder(airport, mod_cache_root)
        self.report: dict[str, _t.Any] = {"stages": {}}
        self.digests: dict[str, str] = {}
        #: the prefix run this object is serving (``""``: the main pass);
        #: a re-run's stages are reported as ``<stage>@<tag>``
        self.tag = ""
        #: the records read or written this build (one ``last_used``)
        self._used: list[str] = []
        self._law_digest: str | None = None
        self._field_digests: dict[str, tuple[_t.Any, str]] = {}
        self._writer: _cf.ThreadPoolExecutor | None = None
        self._pending: list[_cf.Future] = []
        why = bypass or self._bypass(airport, enabled)
        self.active = why is None
        #: a bypass the caller named (``xplat``) is reported per record
        self.bypass = bypass
        self.report["state"] = "on" if self.active else f"bypass: {why}"
        if not self.active:
            return
        self.code = _code.runtime_digests()
        self.env = _sha(json.dumps(_xplat.environment(), sort_keys=True, default=str))
        self.law_rec = _law.LawRecorder(law)
        self.dem_rec = _dem.DemRecorder(airport.dem)
        self.file_rec = _files.FileRecorder()
        self.partition = _pcache.reading_digest(airport)
        # a pack reading with no fingerprint (no pristine pack file: every
        # placement resolves to the library) is named by what it read: the
        # placements as read (their ``anchor_z`` is the DEM's answer) and
        # the stamps of every resource they resolve to
        self.pack = (None if self.partition is not None
                     else _sha(_store.digest_of(pack), _resource_stamps(airport)))

    def _bypass(self, airport: _t.Any, enabled: bool) -> str | None:
        if not enabled:
            return "off"
        if not self.folder:
            return "no mod-cache root"
        return None

    # ── what the build hands the stages ─────────────────────────────
    def airport(self, airport: _t.Any) -> _t.Any:
        """``airport`` with the DEM recorder in place of its DEM (once)."""
        if not self.active or isinstance(getattr(airport, "dem", None), _dem.DemRecorder):
            return airport
        return _dc.replace(airport, dem=self.dem_rec)

    def window(self, on: bool) -> None:
        """Open or close the recording window (classify → shapes)."""
        if self.active:
            self.dem_rec.recording(on)
            self.file_rec.recording(on)

    def close(self) -> None:
        """The last front-half stage is done: close the window and let the
        recorders' records go (they are hundreds of MB of samples at a large
        airport, and the rest of the build never reads them)."""
        if self.active:
            self.window(False)
            self.dem_rec.reset()
            self.file_rec = _files.FileRecorder()

    def reopen(self, tag: str) -> None:
        """A prefix RE-RUN begins (spec §4b.3): a fresh DEM and file record,
        the window open, its stages reported under ``tag``."""
        self.tag = tag
        if self.active:
            self.close()
            self.window(True)

    def report_name(self, stage: str) -> str:
        """The report's name for ``stage`` in the current run."""
        return f"{stage}@{self.tag}" if self.tag else stage

    def law_digest(self) -> str:
        """The WHOLE law's digest — the back half's law key (spec §5's
        first landing; the row witness is a later one)."""
        if self._law_digest is None:
            self._law_digest = _law.value_digest(self.real_law)
        return self._law_digest

    def bypassed(self, stage: str) -> None:
        """Report ``stage`` as bypassed when the caller named the bypass."""
        if self.bypass:
            self.report["stages"][self.report_name(stage)] = {"state": f"bypass: {self.bypass}"}

    def stage_law(self) -> _t.Any:
        """The law a front-half call is handed: the recording proxy while
        the cache is on."""
        return self.law_rec.law() if self.active else self.real_law

    # ── the digests ─────────────────────────────────────────────────
    def airport_digest(self, airport: _t.Any, **named: str) -> str:
        """One digest of ``airport``: each field pickled (memoised by
        value identity), the DEM left to its witness, the partition by its
        reading digest and its connectors; ``named`` overrides a field by a
        digest already in hand (a stage output's; ``None`` is ignored).
        ``""`` while the cache is off."""
        if not self.active:
            return ""
        t = time.perf_counter()
        parts: list[str] = []
        for f in _dc.fields(airport):
            if named.get(f.name) is not None:
                parts.append(f"{f.name}={named[f.name]}")
                continue
            if f.name == "dem":
                continue
            value = getattr(airport, f.name)
            if f.name == "partition" and self.partition is not None:
                conn = getattr(value, "connectors", None)
                parts.append(f"partition={self.partition}|{self._field('connectors', conn)}")
                continue
            parts.append(f"{f.name}={self._field(f.name, value)}")
        self._clock("airport_digest_s", t)
        return _sha(*parts)

    def _field(self, name: str, value: _t.Any) -> str:
        got = self._field_digests.get(name)
        if got is not None and got[0] is value:
            return got[1]
        d = _store.digest_of(value)
        self._field_digests[name] = (value, d)
        return d

    def common_inputs(self, rules: _t.Any, ocache: _t.Any) -> dict[str, str]:
        """The inputs every front-half stage reads besides its own: the
        classify rules as loaded (the planar stage and the road ramps read
        them too) and the ``ResourceCache``'s own settings."""
        if not self.active:
            return {}
        extra = {} if self.pack is None else {"pack": self.pack}
        return {**extra, "rules": _store.digest_of(rules), "ocache": _sha(
            repr(getattr(ocache, "thickness_m", None)),
            repr(getattr(ocache, "input_quantum_m", None)))}

    def digest(self, value: _t.Any) -> str | None:
        """A fresh digest of a product the build derived between stages
        (``None`` while the cache is off)."""
        if not self.active:
            return None
        t = time.perf_counter()
        d = _store.canonical_digest(value)
        self._clock("digest_s", t)
        return d

    def _clock(self, key: str, t: float) -> None:
        self.report[key] = round(self.report.get(key, 0.0) + time.perf_counter() - t, 4)

    # ── one stage ───────────────────────────────────────────────────
    def run(self, stage: str, inputs: _t.Mapping[str, str | None],
            fn: _t.Callable[[_t.Any], _t.Any], *, as_served: bool = False) -> _t.Any:
        """``fn(law)``'s output for ``stage``: served from its record when
        the key and the witnesses hold, else computed (and recorded).

        ``as_served``: a miss hands on its output DECODED from the record,
        exactly as a hit would — for an output the build digests again
        afterwards (a pickle's bytes follow object identity, so the live
        object and its decoded copy need not digest alike)."""
        self.digests.pop(stage, None)        # never a previous run's digest
        if not self.active:
            self.bypassed(stage)
            return fn(self.real_law)
        codes = {s: self.code.get(s) for s in (stage,) + _EXTRA_CODE.get(stage, ())}
        rep: dict[str, _t.Any] = {}
        self.report["stages"][self.report_name(stage)] = rep
        if any(v is None for v in codes.values()) or any(v is None for v in inputs.values()):
            rep["state"] = "bypass: undigested " + ",".join(
                k for k, v in {**codes, **inputs}.items() if v is None)
            return fn(self.stage_law())
        recipe = {"inputs": dict(inputs), "code": codes, "env": self.env}
        key = _store.key_of(stage, recipe)
        path = _store.entry_path(self.folder, self.icao, stage, key)
        rep["key"] = key[:16]
        got = self._serve(stage, key, path, rep, recipe)
        if got is not None:
            return got[0]
        out = fn(self.stage_law())
        blob = self._record(stage, key, path, recipe, out, rep)
        return _pickle.loads(blob) if as_served and blob is not None else out

    def _serve(self, stage: str, key: str, path: str, rep: dict,
               recipe: dict) -> tuple[_t.Any] | None:
        t = time.perf_counter()
        try:
            head, wit, load = _store.read(path, key, recipe)
            why = (_files.holds(wit.get("files")) or _law.holds(self.real_law, wit.get("law"))
                   or _dem.holds(self.dem_rec, wit.get("dem")))
            if why:
                raise _store.Refused(why)
            out = load()
        except FileNotFoundError:
            rep["state"] = "miss"
            return None
        except _store.Refused as exc:
            rep["state"] = f"refused: {exc}"
            return None
        except Exception as exc:                 # a record that will not decode
            rep["state"] = f"refused: {type(exc).__name__}"
            return None
        self.law_rec.replay(wit.get("law"))
        self.dem_rec.replay(wit.get("dem"))
        self.file_rec.replay(wit.get("files"))
        self._used.append(path)
        self.digests[stage] = head["output_digest"]
        rep.update(state="hit", read_s=round(time.perf_counter() - t, 4),
                   bytes=int(head.get("bytes") or 0))
        return (out,)

    def _record(self, stage: str, key: str, path: str, recipe: dict, out: _t.Any,
                rep: dict) -> bytes | None:
        t = time.perf_counter()
        try:
            blob, digest = _store.encode(out)
        except Exception as exc:                 # an output that will not pickle
            rep["state"] = f"miss; not written: {type(exc).__name__}"
            return None
        rep["encode_s"] = round(time.perf_counter() - t, 4)
        self.digests[stage] = digest
        t = time.perf_counter()
        witness = {"law": self.law_rec.record(), "dem": self.dem_rec.record(),
                   "files": self.file_rec.record()}
        rep["witness_s"] = round(time.perf_counter() - t, 4)
        opaque = self.dem_rec.opaque()
        if opaque:
            rep["state"] += f"; not written: dem {opaque}"
            return blob
        self.write_async(path, self.header(stage, key, recipe, digest, len(blob)),
                         witness, blob, rep)
        return blob

    @staticmethod
    def header(stage: str, key: str, recipe: dict, digest: str, size: int,
               **extra: _t.Any) -> dict:
        """A record's header (``airport/stage_cache`` adds ``payload_sha256``)."""
        return {"stage": stage, "key": key, "version": _store.CACHE_VERSION,
                "recipe": recipe, "output_digest": digest, "created": time.time(),
                "bytes": size, **extra}

    def write_async(self, path: str, header: dict, witness: _t.Any, blob: bytes,
                    rep: dict) -> None:
        """Store a record on the writer thread; ``rep`` takes its
        ``written_bytes`` and ``write_s``."""
        if self._writer is None:
            self._writer = _cf.ThreadPoolExecutor(1, thread_name_prefix="o4-stage-cache")
        self._used.append(path)
        self._pending.append(self._writer.submit(self._write, path, header, witness,
                                                 blob, rep))

    def note_used(self, path: str) -> None:
        """A record served this build (its ``last_used`` is the build's)."""
        self._used.append(path)

    @staticmethod
    def _write(path: str, header: dict, witness: _t.Any, blob: bytes, rep: dict) -> None:
        t = time.perf_counter()
        rep["written_bytes"] = _store.write(path, header, witness, blob, used=False)
        rep["write_s"] = round(time.perf_counter() - t, 4)

    def output_digest(self, stage: str) -> str | None:
        """The digest a stage's record names its output by (``None``: the
        stage was not cached this build)."""
        return self.digests.get(stage)

    def finish(self) -> dict:
        """Wait for the writes, keep the root under its cap, return the
        report's ``cache`` block."""
        self.window(False)
        for fut in self._pending:
            try:
                fut.result()
            except Exception as exc:              # pragma: no cover - write never raises
                self.report.setdefault("errors", []).append(repr(exc))
        if self._writer is not None:
            self._writer.shutdown(wait=True)
            self._writer = None
        if self._used:
            _store.touch_many(self._used)
            self._used = []
        if self.active and self._pending:
            gone = _store.sweep(self.root)
            if gone:
                self.report["evicted"] = len(gone)
        self._pending = []
        return self.report
