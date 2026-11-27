"""THE PER-FILE READINGS, KEPT ACROSS BUILDS (#2176 census recommendation 1,
lane ``lfilecache``) — beside the partition cache in the pack's mod-cache
folder.

WHY.  The partition cache (``partition_cache``) keys the WHOLE pack reading
on the source bytes of its ~220-module closure, so any edit to the pack code
— every release, every lane — re-reads every file: KMCI's skirt readings
(67 s), terrain-model shapes (29 s), base profiles (17 s) and the parts'
outlines and heights (133 s; serial-profiled) are paid again for files that
did not change.  Each of those readings is a function of ONE file's bytes,
of the law values its reader reads and of the reader's own code — read in
the file's own frame, or (kind ``part``, ``part_readings``) at a placement
named exactly in the entry's own key.  So each is kept here per FILE, keyed
by those things, and a pack-code edit elsewhere leaves it warm.

THE KEY.  One file per kind, ``o4_v2_file_<kind>.cache``: a deflated pickle
``{"version", "kind", "slots": {key: {"used", "entries": {sha256: reading}}}}``.
``key`` is the sha256 of the store version, the kind, the kind's CODE digest
(``file_readings_code``: the modules the reading runs) and its LAW digest
(:data:`KINDS`: the law paths its reader reads, each value by
``law.witness.value_digest``).  The entries are keyed by the file's CONTENT
(sha256 of the bytes the reader parsed — the pristine ``.anchor_bak`` where
the loader read one, which is the path the reader was handed).  A file keeps
at most :data:`SLOTS_MAX` keys (two engines or two rulesets sharing a pack
do not evict each other on every build), oldest-used first.

WHAT IS NEVER HERE: the parse (RULINGS 2026-09-14v refused the pack's
geometry in the shared mod cache: a size bar), and anything read off a
placement, the DEM or the airport.

READ / WRITE.  ``ResourceCache.files`` holds the build's store; the reading
sites ask it before deriving (``obj8.read_ahead``) and hand it what they
derived (``obj8.keep_reading``).  Writes happen only on :meth:`flush`, only
when the stage may write (the partition cache's ``write_cache``: a replay or
a tool writes nothing shared), as a temp file and ``os.replace``, merged
with whatever another build wrote meanwhile.  The write is the partition
cache's class: a derived, self-invalidating Ortho4XP cache, never corpus
data, never inside the pack.  Nothing here raises into a build: an
unreadable, foreign or corrupt file is a miss.
"""
from __future__ import annotations

import hashlib
import os
import pickle
import time
import typing as _t
import zlib

from .file_hash import sha256_file_or_none

__all__ = ["KINDS", "MISSING", "STORE_VERSION", "SLOTS_MAX", "FileReadings",
           "folder_for", "file_sha"]

#: Bump when the SHAPE of a stored reading or of the file changes.
STORE_VERSION = 1

#: Keys kept per kind file (module doc).
SLOTS_MAX = 4

#: Per kind, the law paths its reader reads (prefixes: a dataclass node is
#: digested whole).  The twin records every law read of each reader through
#: ``law.witness.LawRecorder`` and fails on one outside these.  The
#: ``ResourceCache``'s own thickness (``genuine``) is the basin's
#: ``min_solid_thickness_m`` (``pipeline/build.pack_stage``).
KINDS: dict[str, tuple[str, ...]] = {
    "skirt": ("tables.structures.skirt",
              "tables.structures.basin.min_solid_thickness_m"),
    "base": ("tables.structures.base_profile",
             "tables.structures.building_pad.min_area_m2",
             "tables.structures.placement.split_tol_m",
             "tables.structures.basin.contact_band_m",
             "tables.emit.terrace.pad_terrace_floor_m",
             "tables.emit.design.pad_frontage_m",
             "tables.emit.identity.min_distinct_spacing_m",
             "tables.emit.within_shape.pad_slope_max"),
    "deck": ("tables.structures.bridge",
             "tables.structures.basin.contact_band_m",
             "tables.structures.basin.min_solid_thickness_m"),
    "terrain_shape": (),
    # the foot numbers ``contact.part_attrs`` reads are in the entry's key
    "part": (),
}

#: A miss (a stored reading may itself be ``None``: no terrain shape).
MISSING = object()

_ZLIB_LEVEL = 1

#: ``(abs path, mtime_ns, size) -> sha256`` for this process
_SHAS: dict[tuple[str, int, int], "str | None"] = {}


def file_sha(path: str) -> "str | None":
    """sha256 of ``path``'s bytes, once per file version per process."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    key = (os.path.abspath(path), st.st_mtime_ns, st.st_size)
    if key not in _SHAS:
        _SHAS[key] = sha256_file_or_none(path)
    return _SHAS[key]


def folder_for(airport: _t.Any, mod_cache_root: "str | None") -> "str | None":
    """The pack's mod-cache folder (the partition cache's), or ``None``."""
    name = getattr(getattr(airport, "pack", None), "name", None)
    if not mod_cache_root or not name:
        return None
    from . import dsf as _dsf
    return _dsf.mod_cache_dir(mod_cache_root, name)


def _law_digest(law: _t.Any, paths: _t.Sequence[str]) -> "str | None":
    from ..law.witness import resolve, value_digest
    gone = resolve(None, ("_",))            # the witness's "no such path"
    h = hashlib.sha256()
    for p in paths:
        got = resolve(law, tuple(p.split(".")))
        if got is gone:
            return None
        h.update(p.encode()); h.update(b"\0")
        h.update(value_digest(got).encode()); h.update(b"\0")
    return h.hexdigest()


def _same(kept: _t.Any, reading: _t.Any) -> bool:
    """Whether ``reading`` is what is kept already (the same object, or an
    equal value — a cheap reading re-derived each build is not re-written)."""
    if kept is reading:
        return True
    if kept is MISSING:
        return False
    try:
        return bool(kept == reading)
    except Exception:                  # an array inside: compared by nothing
        return False


class FileReadings:
    """One build's store over one pack folder (module doc).  ``folder``
    ``None`` is a store that never hits and never writes."""

    def __init__(self, folder: "str | None", law: _t.Any, *, write: bool = True,
                 code: "_t.Mapping[str, str | None] | None" = None) -> None:
        self.folder = folder
        self.write = bool(write)
        if code is None:
            from .file_readings_code import runtime_digests
            code = runtime_digests()
        self._keys: dict[str, "str | None"] = {}
        for kind, paths in KINDS.items():
            c = code.get(kind) if folder else None
            ld = _law_digest(law, paths) if c else None
            self._keys[kind] = None if ld is None else hashlib.sha256(
                f"{STORE_VERSION}|{kind}|{c}|{ld}".encode()).hexdigest()
        self._loaded: dict[str, dict] = {}
        self._new: dict[str, dict] = {}
        self.hits: dict[str, int] = {}
        self.misses: dict[str, int] = {}

    # pickled with a capture or a partition: the copy is a store that is off
    def __getstate__(self) -> dict:
        return {"folder": None}

    def __setstate__(self, state: dict) -> None:
        self.folder, self.write = None, False
        self._keys = {k: None for k in KINDS}
        self._loaded, self._new, self.hits, self.misses = {}, {}, {}, {}

    def _path(self, kind: str) -> str:
        return os.path.join(str(self.folder), f"o4_v2_file_{kind}.cache")

    def _read_file(self, kind: str) -> dict:
        try:
            with open(self._path(kind), "rb") as fh:
                blob = pickle.loads(zlib.decompress(fh.read()))
        except Exception:
            return {}
        if (not isinstance(blob, dict) or blob.get("version") != STORE_VERSION
                or blob.get("kind") != kind or not isinstance(blob.get("slots"), dict)):
            return {}
        return blob["slots"]

    def _entries(self, kind: str) -> "dict | None":
        key = self._keys.get(kind)
        if key is None:
            return None
        got = self._loaded.get(kind)
        if got is None:
            slot = self._read_file(kind).get(key) or {}
            got = self._loaded[kind] = dict(slot.get("entries") or {})
        return got

    def get(self, kind: str, path: "str | None") -> _t.Any:
        """The reading of ``path`` kept for ``kind``, or :data:`MISSING`."""
        entries = self._entries(kind)
        sha = file_sha(path) if entries is not None and path else None
        if sha is None:
            return MISSING
        got = entries.get(sha, MISSING)
        tally = self.hits if got is not MISSING else self.misses
        tally[kind] = tally.get(kind, 0) + 1
        return got

    def has(self, kind: str, path: "str | None") -> bool:
        """Whether ``kind`` holds a reading of ``path`` (counts nothing)."""
        entries = self._entries(kind)
        sha = file_sha(path) if entries is not None and path else None
        return sha is not None and sha in entries

    def put(self, kind: str, path: "str | None", reading: _t.Any) -> None:
        """Keep ``reading`` of ``path`` (written on :meth:`flush`)."""
        entries = self._entries(kind)
        sha = file_sha(path) if entries is not None and path else None
        if sha is None or _same(entries.get(sha, MISSING), reading):
            return
        entries[sha] = reading
        self._new.setdefault(kind, {})[sha] = reading

    def flush(self) -> int:
        """Write every kind that took a new reading; returns how many
        readings were written (0 when the store may not write)."""
        if not (self.write and self.folder):
            return 0
        n = 0
        for kind, new in sorted(self._new.items()):
            if new and self._write_kind(kind, new):
                n += len(new)
        self._new.clear()
        return n

    def _write_kind(self, kind: str, new: dict) -> bool:
        key = self._keys[kind]
        tmp = self._path(kind) + ".tmp%d" % os.getpid()
        try:
            os.makedirs(str(self.folder), exist_ok=True)
            slots = self._read_file(kind)
            slot = slots.pop(key, None) or {}
            entries = dict(slot.get("entries") or {})
            entries.update(new)
            kept = sorted(slots.items(), key=lambda kv: -float(kv[1].get("used", 0.0)))
            slots = dict(kept[:SLOTS_MAX - 1])
            slots[key] = {"used": time.time(), "entries": entries}
            blob = {"version": STORE_VERSION, "kind": kind, "slots": slots}
            with open(tmp, "wb") as fh:
                fh.write(zlib.compress(pickle.dumps(blob, protocol=pickle.HIGHEST_PROTOCOL),
                                       _ZLIB_LEVEL))
            os.replace(tmp, self._path(kind))
            return True
        except Exception:
            try:
                if os.path.isfile(tmp):
                    os.remove(tmp)
            except OSError:
                pass
            return False

    def line(self) -> str:
        """``[file readings] skirt 461/0 base …`` — hits / misses per kind."""
        if not self.folder:
            return "[file readings] OFF (no pack or mod-cache root)"
        kinds = sorted(set(self.hits) | set(self.misses))
        body = ", ".join(f"{k} {self.hits.get(k, 0)} hit / {self.misses.get(k, 0)} miss"
                         for k in kinds) or "nothing asked"
        return f"[file readings] {body}"
