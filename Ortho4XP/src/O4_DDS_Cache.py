"""The per-texture DDS cache, keyed on content (issue #839, spec
``docs/specs/step-reuse-content-keys-spec.md`` §2.5, plan id B3-07).

Before, a texture was converted whenever its ``.dds`` was not whole in THIS
build dir: a cleared ``textures/`` reconverted everything, and a neighbour
tile reconverted the grid-aligned textures it shares along its edge.  Now
``O4_Imagery_Utils.convert_texture`` asks this module first.

THE KEY (:func:`texture_key`) is what the converter is handed plus who
converts it, so every input that changes the bytes is in it:

* the SOURCE — the bytes of the file the converter reads (the orthophoto
  JPEG, or the temporary PNG of a filtered / harmonized / masked / combined
  texture), or, for the in-process encoder, the pixels themselves (shape,
  dtype and every byte).  The colour filter, the harmonization field, the
  mask and the sea fill are therefore in the key by construction: they are
  already applied to what is hashed, so no list of "inputs that matter" can
  go stale;
* the FORMAT — DXT1 or DXT5 (``bc1`` / ``bc3``);
* the CONVERTER (:func:`converter_identity`) — the in-process encoder's
  module sources, its mip filter and the numpy / Pillow / ``ispc_texcomp``
  versions; or the subprocess converter's binary (and the libraries beside
  it), its flags and the platform.  ``O4_DDS_ENCODER`` picks the converter,
  so it is in the key too, and a texture the in-process encoder fails and
  the tool converts (#900) is stored under the TOOL's key.

THE STORE.  ``<root>/<key[:2]>/<key>.dds`` (:func:`cache_root`: the data
root's ``DDS_cache``, or ``O4_DDS_CACHE_DIR``; the harness points it
lane-local).  A finished texture is HARDLINKED in (a copy across volumes);
a hit is hardlinked into ``textures/`` under a partial name and landed by
``O4_DDS_File.land``, so a reader never sees a short file.  Nothing in the
engine writes a ``.dds`` in place — every writer replaces the name — so a
link never lets a build dir change a cached texture.

THE CAP.  Least-recently-used entries go first once the store is over
the cap (:func:`max_bytes`): the ``dds`` entry of the Storage setting
``storage_cache_caps_gb``, default 20 GB (owner RULINGS 2026-10-17a Q1);
``O4_DDS_CACHE_MAX_GB`` overrides it.  A hit touches its entry's mtime.
``O4_DDS_CACHE=0`` turns the cache off.

BUILT TILES (#1725).  Every serve and store notes ``key -> texture name``
for its build dir under ``<root>/_tiles/``.  :func:`held_by_built_tiles`
names the entries every build dir that used them now holds itself, whole:
such an entry is a second copy (measured 2026-11-02: 1,833 entries,
20.5 GB, every one a copy -- the tiles live on another volume, so no entry
was a hard link -- and one of them served after its store).  The Storage
automatic cleanup removes them after a build, never during one, when a
neighbour in the same batch may still read a shared edge texture.

Standard library only, besides the versions it reads.
"""
from __future__ import annotations

import contextlib
import hashlib
import os
import re
import shutil
import sys
import threading
import uuid

import O4_DDS_File as DDS

__all__ = ["CACHE_ENV", "DIR_ENV", "MAX_GB_ENV", "DEFAULT_MAX_GB",
           "cache_root", "converter_identity", "enabled", "evict",
           "held_by_built_tiles", "forget_missing", "max_bytes", "serve",
           "store", "texture_key"]

#: ``0`` turns the cache off; anything else, unset included, is on.
CACHE_ENV = "O4_DDS_CACHE"
#: Where the cache lives, overriding the data root's ``DDS_cache``.
DIR_ENV = "O4_DDS_CACHE_DIR"
#: The size cap in GB (decimal).
MAX_GB_ENV = "O4_DDS_CACHE_MAX_GB"
#: Owner RULINGS 2026-10-17a Q1.
DEFAULT_MAX_GB = 20.0
#: Bumped when the key's recipe changes, so an old store is never read
#: under a new meaning.
_KEY_VERSION = b"o4-dds-cache 1"
#: The in-process encoder's modules: its code half of the key.
_ENCODER_MODULES = ("O4_DDS_Encode", "O4_DDS_Mips", "O4_DDS_Refine",
                    "O4_DDS_File")
#: Libraries a subprocess converter loads from beside its binary.
_LIBRARY_ENDINGS = (".dll", ".dylib", ".so")
#: A sweep runs on a process's first store and every this many after.
_SWEEP_EVERY = 64
_HERE = os.path.dirname(os.path.abspath(__file__))

_lock = threading.Lock()
_identities: dict[tuple, "str | None"] = {}
_stores_since_sweep = [_SWEEP_EVERY]


def enabled(environ=None) -> bool:
    """Is the cache on (``O4_DDS_CACHE`` is not ``0``)?"""
    env = os.environ if environ is None else environ
    return env.get(CACHE_ENV, "").strip().lower() not in ("0", "false", "off")


def cache_root(environ=None) -> str:
    """``O4_DDS_CACHE_DIR``, else the data root's ``DDS_cache``; read at
    call time, like the other derived-cache roots (``O4_File_Names``)."""
    env = os.environ if environ is None else environ
    override = env.get(DIR_ENV)
    if override:
        return override
    import O4_File_Names as FNAMES
    return FNAMES.data_path("DDS_cache")


#: The ``dds`` pair of the Storage setting ``storage_cache_caps_gb``
#: (``o4_engine.storage.parse_caps`` reads the whole setting; a build
#: process needs this one number and none of the Storage engine).
_SETTING_PAIR = re.compile(r"(?:^|[,;])\s*dds\s*=\s*([0-9]*\.?[0-9]+)\s*(?:[,;]|$)")


def _setting_cap() -> "int | None":
    """The ``dds`` limit of ``storage_cache_caps_gb`` in bytes, or None
    when it names none (or the setting cannot be read)."""
    try:
        import O4_Settings_Model as SM
        text = SM.read_global_raw().get("storage_cache_caps_gb", "") or ""
    except Exception:
        return None
    match = _SETTING_PAIR.search(text)
    gigabytes = float(match.group(1)) if match else 0.0
    return int(gigabytes * 1e9) if gigabytes > 0 else None


def max_bytes(environ=None, setting_cap: "int | None" = -1) -> int:
    """The cap in bytes: ``O4_DDS_CACHE_MAX_GB`` when set, else the
    Storage setting's ``dds`` limit (``setting_cap``; -1 reads it), else
    20 GB -- ONE cap for the sweep a build runs and the Storage cleanup."""
    env = os.environ if environ is None else environ
    if setting_cap == -1:
        setting_cap = _setting_cap()
    try:
        gb = float(env[MAX_GB_ENV]) if env.get(MAX_GB_ENV) else None
    except ValueError:
        gb = None
    if gb is None:
        return int(setting_cap) if setting_cap else int(DEFAULT_MAX_GB * 1e9)
    return int(max(gb, 0.0) * 1e9)


# ── the key ─────────────────────────────────────────────────────────────
def _file_digest(path: str) -> "str | None":
    h = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                h.update(block)
    except OSError:
        return None
    return h.hexdigest()


def _versions() -> str:
    import numpy
    import PIL
    try:
        import ispc_texcomp
        ispc = getattr(ispc_texcomp, "__version__", "unversioned")
    except ImportError:
        ispc = "absent"
    return f"numpy {numpy.__version__} pillow {PIL.__version__} ispc {ispc}"


def _inproc_identity() -> "str | None":
    import O4_Code_Closure as CLOSURE
    import O4_DDS_Encode as DDSENC
    code = CLOSURE.modules_digest(_HERE, _ENCODER_MODULES)
    if code is None:            # a frozen engine has no sources
        from auto_patch import provenance_code
        code = provenance_code.code_digest()
        if code == "absent":
            return None
    return (f"inproc {code} mips {DDSENC.DEFAULT_MIP_MODE} "
            f"{_versions()}")


def _tool_identity(binary: str, flags: tuple) -> "str | None":
    binary_digest = _file_digest(binary)
    if binary_digest is None:
        return None
    parts = [f"tool {binary_digest} {' '.join(flags)} {sys.platform}"]
    folder = os.path.dirname(binary)
    with contextlib.suppress(OSError):
        for name in sorted(os.listdir(folder)):
            if name.lower().endswith(_LIBRARY_ENDINGS):
                parts.append(f"{name} {_file_digest(os.path.join(folder, name))}")
    return "\n".join(parts)


def converter_identity(kind: str, binary: str = "",
                       flags: tuple = ()) -> "str | None":
    """Who converts: ``kind`` is ``'inproc'`` (the in-process encoder) or
    ``'tool'`` (``binary`` run with ``flags``, the arguments other than the
    two paths).  ``None`` when it cannot be known — the cache then stays
    out of the way.  Taken once per process for each ``(kind, binary,
    flags, size, mtime)``."""
    stamp = ()
    if kind == "tool":
        try:
            st = os.stat(binary)
            stamp = (st.st_size, st.st_mtime_ns)
        except OSError:
            return None
    memo = (kind, binary, tuple(flags), stamp)
    with _lock:
        if memo in _identities:
            return _identities[memo]
    identity = (_inproc_identity() if kind == "inproc"
                else _tool_identity(binary, tuple(flags)))
    with _lock:
        _identities[memo] = identity
    return identity


def texture_key(source, fmt: str, identity: "str | None") -> "str | None":
    """sha256 of the source (a path's bytes, or an array's shape, dtype and
    bytes), the format and the converter identity; ``None`` when any of them
    is unknown."""
    if identity is None:
        return None
    h = hashlib.sha256(_KEY_VERSION + b"\0" + fmt.encode() + b"\0"
                       + identity.encode() + b"\0")
    if isinstance(source, (str, os.PathLike)):
        digest = _file_digest(os.fspath(source))
        if digest is None:
            return None
        h.update(b"file\0" + digest.encode())
    else:
        import numpy
        array = numpy.ascontiguousarray(source)
        h.update(f"pixels {array.shape} {array.dtype.str}\0".encode())
        h.update(memoryview(array).cast("B"))
    return h.hexdigest()


# ── the store ───────────────────────────────────────────────────────────
def _entry(key: str, root: "str | None" = None) -> str:
    return os.path.join(root or cache_root(), key[:2], key + ".dds")


def _link_or_copy(source: str, target: str) -> bool:
    try:
        os.link(source, target)
        return True
    except OSError:
        pass
    try:
        shutil.copyfile(source, target)
        return True
    except OSError:
        with contextlib.suppress(OSError):
            os.remove(target)
        return False


#: Under the root: one note per build dir of the textures it took from or
#: gave to the store.
_TILES_DIR = "_tiles"


def _note_path(build_dir: str, root: str) -> str:
    digest = hashlib.sha1(build_dir.encode("utf-8")).hexdigest()[:16]
    return os.path.join(root, _TILES_DIR, digest + ".txt")


def _note_use(key: str, dds_final: str, root: "str | None" = None) -> None:
    """Note that the build dir of ``dds_final`` holds ``key``'s texture.
    A note that cannot be written only keeps an entry longer."""
    build_dir = os.path.dirname(os.path.dirname(os.path.abspath(dds_final)))
    note = _note_path(build_dir, root or cache_root())
    with _lock, contextlib.suppress(OSError):
        os.makedirs(os.path.dirname(note), exist_ok=True)
        fresh = not os.path.exists(note)
        with open(note, "a", encoding="utf-8", newline="\n") as handle:
            if fresh:
                handle.write("# %s\n" % build_dir)
            handle.write("%s\t%s\n" % (key, os.path.basename(dds_final)))


def _read_notes(root: str) -> dict:
    """``{note path: (build dir, {(key, texture name), ...})}``."""
    notes = {}
    folder = os.path.join(root, _TILES_DIR)
    with contextlib.suppress(OSError):
        for item in os.scandir(folder):
            if not item.name.endswith(".txt"):
                continue
            build_dir, uses = None, set()
            with contextlib.suppress(OSError, UnicodeDecodeError):
                with open(item.path, encoding="utf-8") as handle:
                    for line in handle:
                        line = line.rstrip("\n")
                        if line.startswith("# "):
                            build_dir = build_dir or line[2:]
                        elif "\t" in line:
                            uses.add(tuple(line.split("\t", 1)))
            if build_dir:
                notes[item.path] = (build_dir, uses)
    return notes


def _tile_holds(build_dir: str, name: str, size: int) -> bool:
    texture = os.path.join(build_dir, "textures", name)
    try:
        return os.path.getsize(texture) == size and DDS.is_whole(texture)
    except OSError:
        return False


def held_by_built_tiles(root: "str | None" = None) -> list[str]:
    """The entries of the store that every build dir noted as using them
    holds itself, whole and of the same size, and that are not hard
    links (a link shares its bytes with the tile: removing it frees
    nothing).  Deletes nothing."""
    root = root or cache_root()
    users: dict[str, list] = {}
    for build_dir, uses in _read_notes(root).values():
        for key, name in uses:
            users.setdefault(key, []).append((build_dir, name))
    held = []
    for key, where in sorted(users.items()):
        entry = _entry(key, root)
        try:
            st = os.lstat(entry)
        except OSError:
            continue
        if st.st_nlink == 1 and all(_tile_holds(build_dir, name, st.st_size)
                                    for (build_dir, name) in where):
            held.append(entry)
    return held


def forget_missing(root: "str | None" = None) -> None:
    """Drop the notes of entries no longer in the store (a note left
    with none is removed), so the notes never outgrow the store."""
    root = root or cache_root()
    with _lock:
        for note, (build_dir, uses) in _read_notes(root).items():
            kept = sorted(u for u in uses
                          if os.path.isfile(_entry(u[0], root)))
            with contextlib.suppress(OSError):
                if not kept:
                    os.remove(note)
                    continue
                if len(kept) == len(uses):
                    continue
                with open(note, "w", encoding="utf-8",
                          newline="\n") as handle:
                    handle.write("# %s\n" % build_dir)
                    handle.writelines("%s\t%s\n" % u for u in kept)


def serve(key: "str | None", dds_final: str) -> bool:
    """Put the cached texture of ``key`` at ``dds_final``; ``True`` when it
    is there whole.  A short entry is removed and is a miss."""
    if key is None or not enabled():
        return False
    entry = _entry(key)
    if not os.path.isfile(entry):
        return False
    if not DDS.is_whole(entry):
        with contextlib.suppress(OSError):
            os.remove(entry)
        return False
    partial = DDS.partial_name(dds_final)
    if not _link_or_copy(entry, partial) or not DDS.land(partial, dds_final):
        return False
    with contextlib.suppress(OSError):
        os.utime(entry)                     # least recently USED
    _note_use(key, dds_final)
    return True


def store(key: "str | None", dds_final: str) -> bool:
    """Keep the whole texture at ``dds_final`` under ``key``; ``True`` when
    it is in the store.  Never raises: a cache that cannot be written is a
    cache that misses."""
    if key is None or not enabled() or not DDS.is_whole(dds_final):
        return False
    root = cache_root()
    entry = _entry(key, root)
    temp = f"{entry}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp"
    try:
        os.makedirs(os.path.dirname(entry), exist_ok=True)
        if not _link_or_copy(dds_final, temp):
            return False
        os.replace(temp, entry)
    except OSError:
        with contextlib.suppress(OSError):
            os.remove(temp)
        return False
    _note_use(key, dds_final, root)
    with _lock:
        _stores_since_sweep[0] += 1
        due = _stores_since_sweep[0] >= _SWEEP_EVERY
        if due:
            _stores_since_sweep[0] = 0
    if due:
        evict(root)
    return True


def evict(root: "str | None" = None, cap: "int | None" = None) -> list[str]:
    """Remove the least recently used entries until the store is at most
    ``cap`` bytes (:func:`max_bytes`); returns the removed paths.  Racing
    another process's sweep is harmless: a vanished file is skipped."""
    root = root or cache_root()
    cap = max_bytes() if cap is None else cap
    entries = []
    with contextlib.suppress(OSError):
        for shard in os.scandir(root):
            if not shard.is_dir():
                continue
            with contextlib.suppress(OSError):
                for item in os.scandir(shard.path):
                    if item.name.endswith(".dds"):
                        with contextlib.suppress(OSError):
                            st = item.stat()
                            entries.append((st.st_mtime_ns, st.st_size,
                                            item.path))
    total = sum(size for (_t, size, _p) in entries)
    removed = []
    for (_mtime, size, path) in sorted(entries):
        if total <= cap:
            break
        with contextlib.suppress(OSError):
            os.remove(path)
            removed.append(path)
        total -= size
    return removed
