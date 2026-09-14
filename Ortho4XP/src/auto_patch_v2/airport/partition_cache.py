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

* the DSFTool text dump the placements are read from (path, size,
  mtime) — the same input the footprint cache keys on;
* every ``.obj`` under the pack root at its PRISTINE state — the
  ``.anchor_bak`` original where this engine's own y-bake moved the
  authored file aside, the live file otherwise (owner ruling
  2026-08-13, "AIRPORT DERIVED CACHES KEY ON PRISTINE INPUTS": the
  bake must not invalidate its own cache, and the pristine file IS
  what the reading parsed — ``airport/pack.authored_source`` is the
  same rule the loader reads through);
* the LAW TABLES (``law_tables_digest``'s sha256) and the ruleset key;
* the FRAME the geometry is placed in (its CRS and origin) — every
  coordinate in the result is in it;
* the placement window (``radius_deg``) and the airport;
* THE CODE that produced it: the source bytes of the modules the
  reading runs through.  A derived cache keyed only on data is a
  correctness hazard in a tree that changes every commit, and this one
  holds parsed geometry, a contact graph and a clustering that a dozen
  files decide.  In a FROZEN engine there are no source files and the
  engine's own version stands in — code there cannot change without it.

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
import typing as _t
import zlib

__all__ = ["CACHE_VERSION", "fingerprint", "cache_path", "read", "write"]

#: Bump when the SHAPE of the cached payload changes (the code digest
#: already covers a change in what the reading produces).
CACHE_VERSION = 2

#: The payload is DEFLATED at level 1 (owner RULINGS 2026-09-14v: the
#: file has a size bar).  Measured on the OTHH payload: 72.6 -> 31.3 MB,
#: 0.5 s to compress and 0.1 s to read back — lossless, so the pickle
#: bytes and therefore the revived reading are untouched.  A file written
#: before this (plain pickle) still reads: the deflate is tried first.
_ZLIB_LEVEL = 1

#: The modules the cached reading runs through — their source bytes are
#: the code half of the fingerprint.  Import paths inside the package.
_CODE_MODULES: tuple[str, ...] = (
    "auto_patch_v2.airport.pack_partition",
    "auto_patch_v2.airport.contact",
    "auto_patch_v2.airport.obj8",
    "auto_patch_v2.airport.obj8_clip",
    "auto_patch_v2.airport.skirt",
    "auto_patch_v2.airport.deck_signature",
    "auto_patch_v2.airport.line_object",
    "auto_patch_v2.airport.placement_boxes",
    "auto_patch_v2.airport.placement_contact",
    "auto_patch_v2.airport.placement_family",
    "auto_patch_v2.airport.pack",
    "auto_patch_v2.planar.basins",
    "auto_patch_v2.planar.cluster",
    "auto_patch_v2.model.rebake",
)

_CODE_DIGEST: str | None = None


def code_digest() -> str:
    """The source bytes of :data:`_CODE_MODULES`, hashed once per
    process; the engine's version when the sources are unavailable (a
    frozen build, where they cannot change without it)."""
    global _CODE_DIGEST
    if _CODE_DIGEST is not None:
        return _CODE_DIGEST
    import importlib
    h = hashlib.sha256()
    seen = 0
    for name in _CODE_MODULES:
        try:
            mod = importlib.import_module(name)
            src = getattr(mod, "__file__", None)
            if not src or not os.path.isfile(src):
                continue
            with open(src, "rb") as fh:
                h.update(name.encode()); h.update(b"\0")
                h.update(fh.read()); h.update(b"\0")
            seen += 1
        except Exception:
            continue
    if seen != len(_CODE_MODULES):
        # frozen (or a module missing): the engine version is the code
        h = hashlib.sha256()
        try:
            import O4_Version                      # type: ignore
            h.update(str(getattr(O4_Version, "version", "?")).encode())
        except Exception:
            h.update(b"unknown-engine")
        h.update(b"|frozen|")
        h.update(str(seen).encode())
    _CODE_DIGEST = h.hexdigest()
    return _CODE_DIGEST


def fingerprint(airport, law, *, dump_path: str | None,
                radius_deg: float | None) -> str | None:
    """The fingerprint of everything the cached reading is a function of
    (module doc), or ``None`` when it cannot be taken (no pack, no dump)
    — in which case nothing is cached."""
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
    try:
        st = os.stat(dump_path)
        h.update(f"dump:{os.path.basename(dump_path)}:{st.st_size}:{st.st_mtime}|".encode())
    except OSError:
        return None
    ents = _pristine_entries(pack_root)
    if ents is None:
        return None                     # no pristine reading: no cache
    for line in ents:
        h.update(line.encode()); h.update(b"\n")
    fr = getattr(airport, "frame", None)
    h.update(f"frame:{getattr(fr, 'crs', None)}:"
             f"{getattr(fr, 'lat0', None)}:{getattr(fr, 'lon0', None)}|".encode())
    h.update(f"icao:{getattr(airport, 'icao', '')}|radius:{radius_deg}|".encode())
    h.update(f"pack:{pack_root}|".encode())
    return h.hexdigest()


def _pristine_entries(pack_root: str) -> list[str] | None:
    """``relpath:size:mtime`` per pack ``.obj``, read at its PRISTINE
    state (module doc) — sorted, so the digest is order-stable.  ``None``
    when the pack cannot be walked (nothing is then cached)."""
    from .pack import AUTHORED_BACKUP_SUFFIX, authored_source
    out: list[str] = []
    try:
        for root, _dirs, files in os.walk(pack_root):
            for nm in files:
                if not nm.lower().endswith(".obj"):
                    continue
                live = os.path.join(root, nm)
                read, _restored = authored_source(live)
                st = os.stat(read or live)
                rel = os.path.relpath(live, pack_root)
                out.append(f"{rel}:{st.st_size}:{st.st_mtime}")
    except OSError:
        return None
    if not out:
        return None
    out.sort()
    out.append(f"suffix:{AUTHORED_BACKUP_SUFFIX}")
    return out


def _pack_root(airport) -> str:
    apt = getattr(getattr(airport, "pack", None), "apt_dat_path", None)
    if not apt:
        return ""
    return os.path.dirname(os.path.dirname(apt))


def cache_path(airport, mod_cache_root: str | None,
               dump_path: str | None) -> str | None:
    """``<mod cache>/<pack>/o4_v2_partition_<tile>.cache`` — beside the
    footprint cache, never inside the pack.  The tile token is the dump's
    own (``+25+051.dsf.<tag>.text`` -> ``+25+051``), so the cache is keyed
    where the placements came from and needs no second plumbing."""
    if not mod_cache_root or not dump_path:
        return None
    pack_name = getattr(getattr(airport, "pack", None), "name", None)
    if not pack_name:
        return None
    tile = os.path.basename(dump_path).split(".", 1)[0]
    if not tile:
        return None
    from . import dsf as _dsf
    return os.path.join(_dsf.mod_cache_dir(mod_cache_root, pack_name),
                        f"o4_v2_partition_{tile}.cache")


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
    return blob.get("result")


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
                pickle.dumps({"fingerprint": fp, "result": result},
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
