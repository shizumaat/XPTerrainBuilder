"""THE PACK PARTITION, CACHED (lane ``v2cost2``, RULINGS 2026-09-14q
item 1) — beside ``o4_object_footprints_<tile>.cache`` in the pack's
Ortho4XP mod-cache folder, under the same fingerprint discipline.

WHAT IS CACHED AND WHY IT IS LAWFUL TO CACHE IT.  ``planar/basins.
read_objects`` and ``airport/pack_partition.partition_pack`` are a PURE
READING of the pack: the module doc of ``pack_partition`` states it
itself — "the pack, the law, and the DEM the loader already sampled at
every anchor.  No planar product, no solved surface, no environment."
``planar/cluster.clusters`` is a function of that partition and the law
alone.  At OTHH they are 298 of the patch stage's 841 s (14q).
``planar/group.derive`` is NOT cached: it reads ``dem_at``, so its
answer depends on the DEM frame, and it is 15 s.

THE FINGERPRINT covers everything the reading is a function of:

* the DSFTool text dump the placements are read from, BY CONTENT
  (:func:`dump_digest`, issue #362): its sha256 with the ``# file:``
  header line left out.  The name, size and mtime it was keyed on all
  move when the object stage sets the pristine DSF aside — the same DSF
  is then dumped again as ``<tile>.dsf.anchor_bak.<tag>.text``, 11 bytes
  longer for the one path in its header — so the SECOND build of every
  airport missed (OTHH: +500 s) on an input that had not changed;
* every ``.obj`` under the pack root at its PRISTINE state — the
  ``.anchor_bak`` original where this engine's own y-bake moved the
  authored file aside, the live file otherwise (owner ruling
  2026-08-13, "AIRPORT DERIVED CACHES KEY ON PRISTINE INPUTS": the
  bake must not invalidate its own cache, and the pristine file IS
  what the reading parsed — ``airport/pack.authored_source`` is the
  same rule the loader reads through).  THE ENGINE'S OWN SPLIT BODIES
  ARE NOT PACK CONTENT (issue #362): the object stage mints
  ``<stem>__b<k>[_<tag>].obj`` files into the pack AFTER the build that
  wrote the cache, and the walk then found ~1,900 new files at OTHH and
  moved the key.  A file is left out only when it carries the split
  NAME, the writer's ``CUT_MARK`` in its head, AND no placement of this
  run resolves to it (:func:`_pack_content`) — a body the reading does
  parse stays in the key like any authored file;
* the LAW TABLES (``law_tables_digest``'s sha256) and the ruleset key;
* the FRAME the geometry is placed in (its CRS and origin) — every
  coordinate in the result is in it;
* the placement window (``radius_deg``) and the airport;
* THE RESOLVED-PLACEMENT SET (issue #88): the count and a sha256 of the
  sorted ``(def_path, resolved_path)`` pairs of the airport's placements
  that resolved — pack-relative OR through the library index.  The pack
  walk above cannot see the index (``lib/`` resolves outside the pack),
  so a partition read while 3,354 of 3,585 ``lib/`` placements were
  unresolved was served to a run that resolved them all (SPJC, lane
  corpusspjc).  The resolved path is taken at its LIVE name (the
  ``.anchor_bak`` suffix stripped), so the engine's own y-bake does not
  invalidate its own cache (owner ruling 2026-08-13).  A miss on a file
  whose stored set differs is logged with both digests (:func:`peek`);
* THE CODE that produced it: the source bytes of the modules the
  reading runs through.  A derived cache keyed only on data is a
  correctness hazard in a tree that changes every commit, and this one
  holds parsed geometry, a contact graph and a clustering that a dozen
  files decide.  In a FROZEN engine there are no source files: the
  freeze writes the SAME digest of the same sources beside
  ``partition_code`` and the engine reads it (issue #362 — the app
  version stood in for the code, so every update cold-started every
  user's partition).  The version is the fallback only for an engine
  frozen without that file.

THE WRITE IS NOT A ``--refresh-data`` ACT.  It is the SAME CLASS as
``o4_object_footprints_<tile>.cache``: a derived, self-invalidating
Ortho4XP cache in the pack's mod-cache folder, never corpus data, never
a download, and never written into the pack itself (user ruling
2026-07-15).  Under a lane's ``O4_AIRPORT_MOD_CACHE_DIR`` overlay it
lands lane-local like every other mod-cache write; the app's own run
writes it to the shared mod cache exactly as the footprints cache does.
"""
from __future__ import annotations

import hashlib
import os
import pickle
import re
import typing as _t
import zlib
from . import partition_code as _code
from .file_hash import sha256_file_or_none

__all__ = ["CACHE_VERSION", "fingerprint", "cache_path", "read", "write",
           "pristine_stamps", "resolved_digest", "peek", "code_digest",
           "dump_digest"]

#: Bump when the SHAPE of the cached payload changes (the code digest
#: already covers a change in what the reading produces).
CACHE_VERSION = 9   # issue #222 (lane snap222, owner RULINGS 2026-10-02v
                    # (4)): every cached partition on disk was read through
                    # a cache WITHOUT the §51 (6) input quantum, because
                    # ``pipeline/build.pack_stage`` built it without one.
                    # ``pipeline.build`` is NOT in :data:`_CODE_MODULES`
                    # (the reading's own modules are), so the code digest
                    # cannot see that fix — the bump is what stops an
                    # unsnapped payload being served to a snapped build.
                    # A stale payload is refused, never repaired on read.
# was 8:            # issue #73 (lane courtyards): ``PlanCluster.bridges``
                    # (the posts' and flat lines' rings, which close a
                    # split outline); the frozen engine's digest is this.
# was 7:            # issue #73 (lane lacepad): ``PlanCluster.rings``
                    # (the cached clusters) omit POSTS and FLAT LINES
                    # (``placement_family.draws_outline``); the frozen
                    # engine's digest is this number.
# was 6:            # issue #69 (lane outlinebisect): ``Part.height_m``
                    # also reads the WALL CHORD of steep triangles
                    # (``contact.wall_chord_height``) — a leaning facade
                    # is a wall; the frozen engine's digest is this number.
# was 5:            # merge of two v4 bumps, BOTH reasons stand:
                    # (a) #27/#29 (lane packperf): per-airport path + pristine
                    # header, and the SCATTER class (parts / members / base
                    # index carry ``scatter``);
                    # (b) lane ``surfacesettle``: ``Part.height_m`` is the
                    # LOCAL solid height (``contact.solid_height``); a cached
                    # reading carries the whole-extent one.
                    # A v3 / v4 payload is refused, never repaired.
# was 3:            # §51 (4) row 17: every placed footprint in a cached
                    # reading was minted by the PRE-§51 entry path.  The
                    # bump INVALIDATES them; a stale payload is never
                    # repaired on read, because a repair-on-read is a
                    # second entry site.  The bump is also what covers the
                    # FROZEN engine, where the code digest is the version.

#: The payload is DEFLATED at level 1 (owner RULINGS 2026-09-14v: the
#: file has a size bar).  Measured on the OTHH payload: 72.6 -> 31.3 MB,
#: 0.5 s to compress and 0.1 s to read back — lossless, so the pickle
#: bytes and therefore the revived reading are untouched.  A file written
#: before this (plain pickle) still reads: the deflate is tried first.
_ZLIB_LEVEL = 1

#: The modules the cached reading runs through (``partition_code`` owns
#: the list and the digest; the freeze runs the same function).
_CODE_MODULES: tuple[str, ...] = _code.CODE_MODULES

_CODE_DIGEST: str | None = None


def code_digest() -> str:
    """The source bytes of :data:`_CODE_MODULES`, hashed once per
    process.  In a frozen build (no sources) the digest the FREEZE took
    of those same sources (``partition_code.frozen_digest``); the
    engine's version only when that file is missing too."""
    global _CODE_DIGEST
    if _CODE_DIGEST is not None:
        return _CODE_DIGEST
    import importlib

    def _sources():
        for name in _CODE_MODULES:
            try:
                yield name, getattr(importlib.import_module(name), "__file__", None)
            except Exception:
                yield name, None
    d = _code.digest_of(_sources()) or _code.frozen_digest()
    if d is None:
        # frozen by a spec that wrote no digest: the engine version is the code
        h = hashlib.sha256()
        try:
            import O4_Version                      # type: ignore
            h.update(str(getattr(O4_Version, "version", "?")).encode())
        except Exception:
            h.update(b"unknown-engine")
        h.update(b"|frozen|")
        d = h.hexdigest()
    _CODE_DIGEST = d
    return _CODE_DIGEST


#: DSFTool names the file it dumped in its header; nothing else in the
#: text depends on where the DSF stood.
_DUMP_FILE_LINE = re.compile(rb"^# file:[^\n]*\n", re.M)


def dump_digest(dump_path: str) -> str | None:
    """sha256 of the DSFTool text dump's CONTENT (module doc): every byte
    but the ``# file: <path>`` header line, sought in the first 4 KiB
    only.  ``None`` when the dump cannot be read."""
    try:
        with open(dump_path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return None
    head = _DUMP_FILE_LINE.sub(b"", raw[:4096], count=1)
    h = hashlib.sha256()
    h.update(head); h.update(raw[4096:])
    return h.hexdigest()


#: A split body's NAME (``obj8_split.body_resource_name``): the first of
#: the three witnesses :func:`_pack_content` asks for.
_BODY_NAME = re.compile(r"__b\d+(?:_[0-9a-f]{8})?\.obj$", re.I)


def _pack_content(ents: _t.Sequence[tuple[str, int, float, str]],
                  pack_root: str, airport) -> list[tuple[str, int, float, str]]:
    """``ents`` without the ENGINE-MINTED split bodies (module doc): a
    file is dropped only when its name is a split body's, its head carries
    the writer's ``CUT_MARK`` (the test ``placement_write.write_files``
    replaces a file on) and NO placement of ``airport`` resolves to it."""
    suspects = [e for e in ents if _BODY_NAME.search(e[0])]
    if not suspects:
        return list(ents)
    from ..model.placement import CUT_MARK
    from .pack import live_path_of

    def _norm(p: str) -> str:
        return os.path.normcase(os.path.abspath(p))
    read = {_norm(live_path_of(str(o.resolved_path)))
            for o in getattr(airport, "dsf_objects", None) or ()
            if getattr(o, "resolved_path", None)}
    minted: set[str] = set()
    for rel, _sz, _mt, src in suspects:
        if _norm(os.path.join(pack_root, rel)) in read:
            continue
        try:
            with open(src, "r", errors="replace") as fh:
                if CUT_MARK in fh.read(4096):
                    minted.add(rel)
        except OSError:
            continue
    return [e for e in ents if e[0] not in minted]


#: ``fingerprint -> pristine stamps`` of the fingerprints this process
#: took: :func:`write` stores them in the payload header and :func:`read`
#: checks them (§12a: size in the key, mtime + content hash in the header).
_STAMPS: dict[str, list[tuple[str, int, float, str]]] = {}

#: ``fingerprint -> resolved digest`` (:func:`resolved_digest`) of the
#: fingerprints this process took — stored in the payload so a later
#: miss can say whether the resolved set is what moved (issue #88).
_RESOLVED: dict[str, tuple[int, str]] = {}


def resolved_digest(airport) -> tuple[int, str]:
    """``(count, sha256)`` of the airport's RESOLVED placements (module
    doc, issue #88): the sorted ``(def_path, live resolved path)`` pairs
    of every ``dsf_objects`` entry with a ``resolved_path``.  An airport
    with no placements digests to ``(0, sha256(b""))``."""
    from .pack import AUTHORED_BACKUP_SUFFIX as _sfx
    pairs = []
    for o in getattr(airport, "dsf_objects", None) or ():
        rp = getattr(o, "resolved_path", None)
        if not rp:
            continue
        rp = str(rp)
        if rp.endswith(_sfx):
            rp = rp[:-len(_sfx)]
        pairs.append(f"{getattr(o, 'path', '')}\t{rp}")
    pairs.sort()
    h = hashlib.sha256()
    for ln in pairs:
        h.update(ln.encode("utf-8", "surrogateescape")); h.update(b"\n")
    return len(pairs), h.hexdigest()


def fingerprint(airport, law, *, dump_path: str | None,
                radius_deg: float | None,
                pristine: "dict[str, list] | None" = None) -> str | None:
    """The fingerprint of everything the cached reading is a function of
    (module doc), or ``None`` when it cannot be taken (no pack, no dump)
    — in which case nothing is cached.

    ``pristine`` maps a pack root to its walk (:func:`pristine_stamps`)
    ALREADY TAKEN by the tile build's parent (spec §B.4: once per tile
    build across children); a root it does not carry is walked here.  The key carries
    each pristine ``.obj``'s path and SIZE only — the mtime is checked
    against the payload header on read and, where only the mtime moved,
    the content hash decides (§12a: a pack restored from a backup must
    not invalidate every file's worth of reading)."""
    pack_root = _pack_root(airport)
    if not pack_root or not dump_path or not os.path.isfile(dump_path):
        return None
    h = hashlib.sha256()
    h.update(f"v{CACHE_VERSION}|{code_digest()}|".encode())
    try:
        from ..law.tables import law_tables_digest
        d = law_tables_digest()
        h.update(f"law:{d.get('sha256')}|ruleset:{law.ruleset_key}|".encode())
    except Exception:
        return None
    dd = dump_digest(dump_path)
    if dd is None:
        return None
    h.update(f"dump:{dd}|".encode())
    ents = (pristine or {}).get(pack_root) or pristine_stamps(pack_root)
    if not ents:
        return None                     # no pristine reading: no cache
    ents = _pack_content(ents, pack_root, airport)
    for rel, size, _mt, _read in ents:
        h.update(f"{rel}:{size}".encode()); h.update(b"\n")
    from .pack import AUTHORED_BACKUP_SUFFIX
    h.update(f"suffix:{AUTHORED_BACKUP_SUFFIX}|".encode())
    fr = getattr(airport, "frame", None)
    h.update(f"frame:{getattr(fr, 'crs', None)}:"
             f"{getattr(fr, 'lat0', None)}:{getattr(fr, 'lon0', None)}|".encode())
    h.update(f"icao:{getattr(airport, 'icao', '')}|radius:{radius_deg}|".encode())
    h.update(f"pack:{pack_root}|".encode())
    # §44 (4) (owner RULINGS 2026-09-15f): the BORROWED Global Airports
    # block, so a Global update invalidates the cached reading — the pack
    # walk above cannot see it (the block is not in the pack).
    pk = getattr(airport, "pack", None)
    h.update(f"borrowed:{getattr(pk, 'borrowed_apt_dat_path', '')}:"
             f"{getattr(pk, 'borrowed_block_sha256', '')}|".encode())
    # issue #88: the resolved-placement set (library-index resolution)
    rd = resolved_digest(airport)
    h.update(f"resolved:{rd[0]}:{rd[1]}|".encode())
    fp = h.hexdigest()
    _STAMPS[fp] = list(ents)
    _RESOLVED[fp] = rd
    return fp


def pristine_stamps(pack_root: str) -> list[tuple[str, int, float, str]] | None:
    """``(relpath, size, mtime, read path)`` per pack ``.obj``, read at its
    PRISTINE state (module doc) — sorted by path, so the digest is
    order-stable.  ``None`` when the pack cannot be walked (nothing is
    then cached).  A plain picklable list: the tile build's parent takes
    it ONCE per pack root and hands it to every child (spec §B.4)."""
    from .pack import authored_source
    out: list[tuple[str, int, float, str]] = []
    try:
        for root, _dirs, files in os.walk(pack_root):
            for nm in files:
                if not nm.lower().endswith(".obj"):
                    continue
                live = os.path.join(root, nm)
                read, _restored = authored_source(live, pack_root)
                src = read or live
                st = os.stat(src)
                rel = os.path.relpath(live, pack_root)
                out.append((rel, int(st.st_size), float(st.st_mtime), src))
    except OSError:
        return None
    if not out:
        return None
    out.sort()
    return out


def _header(fp: str) -> dict[str, tuple[float, str | None]]:
    """``relpath -> (mtime, sha256)`` of the pristine files under ``fp`` —
    what :func:`read` checks an mtime-only change against."""
    return {rel: (mt, sha256_file_or_none(src)) for rel, _sz, mt, src in _STAMPS.get(fp, ())}


def _stamps_hold(fp: str, header: _t.Any) -> bool:
    """Every pristine file's mtime equals the header's, or — where only the
    mtime moved (the size is in the key) — its content hash does."""
    if not isinstance(header, dict):
        return False
    for rel, _sz, mt, src in _STAMPS.get(fp, ()):
        got = header.get(rel)
        if got is None:
            return False
        if got[0] == mt:
            continue
        if got[1] is None or sha256_file_or_none(src) != got[1]:
            return False
    return True


def _pack_root(airport) -> str:
    apt = getattr(getattr(airport, "pack", None), "apt_dat_path", None)
    if not apt:
        return ""
    return os.path.dirname(os.path.dirname(apt))


def cache_path(airport, mod_cache_root: str | None,
               dump_path: str | None) -> str | None:
    """``<mod cache>/<pack>/o4_v2_partition_<tile>_<ICAO>.cache`` — beside
    the footprint cache, never inside the pack.  The tile token is the
    dump's own (``+25+051.dsf.<tag>.text`` -> ``+25+051``), so the cache is
    keyed where the placements came from and needs no second plumbing.

    PER AIRPORT (spec §B.4, issue #27): the payload is placed geometry in
    the airport's frame plus that airport's window, so it cannot be shared
    by two airports; named by tile alone, TNCM and TFFG (one tile, one
    pack) overwrote each other and no build ever hit.  The old
    un-suffixed file is never read and never deleted (a build never
    deletes a user-side cache file)."""
    if not mod_cache_root or not dump_path:
        return None
    pack_name = getattr(getattr(airport, "pack", None), "name", None)
    if not pack_name:
        return None
    tile = os.path.basename(dump_path).split(".", 1)[0]
    icao = str(getattr(airport, "icao", "") or "")
    if not tile or not icao:
        return None
    from . import dsf as _dsf
    return os.path.join(_dsf.mod_cache_dir(mod_cache_root, pack_name),
                        f"o4_v2_partition_{tile}_{icao}.cache")


def read(path: str | None, fp: str | None) -> _t.Any | None:
    """The cached payload when ``path`` holds one under ``fp``, else
    ``None``.  Never raises: a corrupt or foreign cache is a miss."""
    if not path or not fp or not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
        try:
            raw = zlib.decompress(raw)
        except zlib.error:
            pass                        # a pre-deflate file, read as it is
        blob = pickle.loads(raw)
    except Exception:
        return None
    if not isinstance(blob, dict) or blob.get("fingerprint") != fp:
        return None
    if fp in _STAMPS and not _stamps_hold(fp, blob.get("pristine")):
        return None
    return blob.get("result")


def peek(path: str | None) -> "tuple[int, str] | None":
    """The resolved digest a cache file was WRITTEN under (issue #88), or
    ``None`` (no file, unreadable, or written before the digest was
    stored).  Only read on a miss, to log what moved."""
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
        try:
            raw = zlib.decompress(raw)
        except zlib.error:
            pass
        blob = pickle.loads(raw)
    except Exception:
        return None
    rd = blob.get("resolved") if isinstance(blob, dict) else None
    if isinstance(rd, (tuple, list)) and len(rd) == 2:
        return int(rd[0]), str(rd[1])
    return None


def write(path: str | None, fp: str | None, result: _t.Any) -> bool:
    """Store ``result`` under ``fp``.  ``False`` (never an exception) when
    the write is refused or fails — a build never depends on it."""
    if not path or not fp:
        return False
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp%d" % os.getpid()
        with open(tmp, "wb") as fh:
            fh.write(zlib.compress(
                pickle.dumps({"fingerprint": fp, "pristine": _header(fp),
                              "resolved": _RESOLVED.get(fp),
                              "result": result},
                             protocol=pickle.HIGHEST_PROTOCOL), _ZLIB_LEVEL))
        os.replace(tmp, path)
        return True
    except Exception:
        try:
            if os.path.isfile(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return False
