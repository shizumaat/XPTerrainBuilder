"""THE SHARED-REPO WRITE LAW — one implementation, two entries.

This module is THE single implementation of the shared data repo's write
law (owner ruling e9daef5, ``Ortho4XP/docs/RULINGS.md``): the write GUARD
that refuses an unauthorised write at the call site, its two allowances
(the engine's cross-process ``.lock`` files and the derived library-index
sidecar), the full before/after SNAPSHOT audit that backstops it, the
SWALLOWED-REFUSAL detector, and the ``--refresh-data`` scopes, per-scope
LOCK and hash-stamped LEDGER that make a cache regeneration an explicit,
recorded event instead of a build side effect.

``tools/harness/build_airport.py`` re-exports every public name here (so
``build_mod.SharedRepoWriteGuard`` is this class, not a copy) and
``tools/run_tile_mesh_only.py`` arms it.  A SECOND COPY OF ANY OF THIS IS
A DEFECT: two lanes each wrote their own census wrapper and each dropped a
different thing, and both wrappers looked right (root ``CLAUDE.md``, "The
standard test harness").  The measured precedent for this module's own
existence is 2026-08-08, when two unguarded ``run_tile_mesh_only.py`` runs
silently rewrote five inset/bathymetry manifests in the shared repo while
every guarded ``build_airport.py`` run the same session reported the repo
UNCHANGED.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import time
from pathlib import Path


#: THE shared data repo (owner ruling e9daef5).  Every lane mounts it; no
#: lane redownloads or regenerates a cache into a private corpus.
DATA_REPO = Path(os.environ.get("O4_DATA_REPO",
                                "/Users/noah/XPTerrainBuilderData"))
HARNESS_STATE = DATA_REPO / ".harness"
LOCK_DIR = HARNESS_STATE / "locks"
REFRESH_LEDGER = HARNESS_STATE / "refresh_ledger.jsonl"

#: The data directories a lane mounts from the shared repo.  Products
#: (Patches, Tiles, Previews, tmp) are deliberately NOT here — every tile
#: build writes its emitted patches into Patches/, so sharing it would put
#: one lane's geometry into another lane's build.
SHARED_DATA_DIRS = ("OSM_data", "Elevation_data", "Airport_mod_cache",
                    "Geotiffs", "Masks", "Default_DSF_cache", "Orthophotos")

#: The REGENERABLE artifact classes, most specific prefix first.  A build
#: may regenerate any of these implicitly today; under the ruling it may
#: not, so each one is a named ``--refresh-data`` scope instead.
REFRESH_SCOPES = (
    ("osm_roadfeed", "OSM_data/_airport_road_feed",
     "the per-airport ROAD FEED sidecar.  THE NAMED PRECEDENT: a KCLT "
     "road-feed refresh ran as a tile-build side effect on 2026-08-05 "
     "01:47-01:55 and silently changed campaign hashes — every later "
     "build read a different feed and nobody was told"),
    ("osm_layers", "OSM_data",
     "cached OSM layers and regional extracts (overpass downloads)"),
    ("dem", "Elevation_data",
     "base DEM rasters and airport elevation insets (provider downloads)"),
    ("airport_mod_cache", "Airport_mod_cache",
     "third-party apt.dat pack indexes and sidecars"),
    ("dsf_cache", "Default_DSF_cache",
     "DSFTool text dumps of X-Plane's default scenery"),
    ("masks", "Masks", "water/coastline mask rasters"),
    ("orthophotos", "Orthophotos", "downloaded imagery tiles"),
    ("geotiffs", "Geotiffs", "user-supplied geotiff sources"),
    # NOT in the data repo: the owner's X-Plane INSTALL.  The object
    # stage's write half (``auto_patch_v2.airport.placement_write.
    # apply_plan``) rewrites the serving pack's DSF, re-bakes its
    # ``.obj`` bodies and leaves ``.anchor_bak`` backups — in
    # ``<install>/Custom Scenery/<pack>/``, which no data-repo prefix
    # could ever match, so neither this guard nor the cache redirects
    # covered it until 2026-09-15.  THE MEASURED CASE: lane
    # v2vmmcshore's harness TILE build of +22+113 rewrote the OWNER'S
    # live VHHH pack (6,390 placements) at 11:49 and re-dumped it at
    # 11:52 (RULINGS 2026-09-15av).  The repo has no ``Custom Scenery``
    # directory, so this prefix can only ever match an install path —
    # ``_violation`` spells one that way deliberately.
    ("pack_rebake", "Custom Scenery",
     "the owner's X-Plane install: scenery-pack DSF rewrites, re-baked "
     ".obj bodies and .anchor_bak backups written by the object stage.  "
     "A LANE NEVER WRITES THE INSTALL — the app on the owner's machine "
     "is the only writer of his packs (owner ruling e9daef5 + the lane "
     "protocol); authorising this scope is HIS act"),
)


def install_relpath(path) -> str:
    """How an install write is NAMED in a refusal: ``Custom Scenery/...``
    when it is under one (so :func:`scope_of` maps it to ``pack_rebake``
    — the repo has no such directory, so the prefix cannot collide), and
    the absolute path otherwise, which belongs to no scope and is
    therefore unauthorisable."""
    p = os.path.abspath(os.fspath(path)).replace(os.sep, "/")
    marker = "/Custom Scenery/"
    i = p.find(marker)
    return ("Custom Scenery/" + p[i + len(marker):]) if i >= 0 else p


def scope_of(relpath: str):
    """The ``--refresh-data`` scope a shared-repo path belongs to, most
    specific prefix first.  ``None`` for a path outside every scope."""
    rel = str(relpath)
    for name, prefix, _why in REFRESH_SCOPES:
        if rel == prefix or rel.startswith(prefix + "/"):
            return name
    return None


def scope_description(name: str) -> str:
    for scope, _prefix, why in REFRESH_SCOPES:
        if scope == name:
            return why
    return "(unknown scope)"


def pack_roots_for_tile(lat, lon, install_root) -> tuple:
    """Every scenery pack under ``<install>/Custom Scenery`` that carries
    THIS tile's DSF — i.e. every pack a build of this tile reads, and so
    every pack its object stage could write.

    Cheap by construction: one ``isfile`` per pack directory, no walk.
    Measured on the owner's install — 18 packs carry ``+22+113``, 15
    carry ``+40-004``, and the probe costs 0.03 s.
    """
    block = f"{(int(lat) // 10) * 10:+03d}{(int(lon) // 10) * 10:+04d}"
    stem = f"{int(lat):+03d}{int(lon):+04d}.dsf"
    custom = Path(install_root) / "Custom Scenery"
    try:
        names = sorted(os.listdir(custom))
    except OSError:
        return ()
    out = []
    for name in names:
        pack = custom / name
        if (pack / "Earth nav data" / block / stem).is_file():
            out.append(str(pack))
    return tuple(out)


def install_snapshot(pack_roots) -> dict:
    """The before/after snapshot of the owner's PACKS, keyed the way
    :func:`install_relpath` names them (``Custom Scenery/<pack>/...``) so
    :func:`scope_of` maps every entry to ``pack_rebake``.

    WHY IT EXISTS (2026-09-15, RULINGS 2026-09-15av + 15bb).  TWO lane
    tile builds rewrote the owner's live packs — VHHH's DSF at 11:49:11,
    LEMD's DSF plus ``o4_placement_provenance.json`` plus 2,694 split
    body ``.obj`` files at 12:21:43 — and BOTH runs printed "shared repo
    UNCHANGED", because the snapshot walked the data repo only and the
    install is not in it.  The whole pack is walked, not just ``Earth
    nav data``: the split bodies land at the resource paths the plan
    names (``Airport/Cargo_Terminal/CG10__b0_….obj``), anywhere in the
    pack.  Measured on the owner's install: 108 k files across the 18
    packs carrying +22+113 in 0.13 s, 128 k across LEMD's 15 in 0.19 s.
    """
    snap = {}
    for root in pack_roots or ():
        for dirpath, _dirnames, filenames in os.walk(root):
            for fn in filenames:
                p = os.path.join(dirpath, fn)
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                snap[install_relpath(p)] = (st.st_size, st.st_mtime_ns)
    return snap


def shared_repo_snapshot(repo=None) -> dict:
    """``{relative path: (size, mtime_ns)}`` for every file in the shared
    repo's data directories.

    A FULL walk on purpose: the whole surface is ~2.7 k files and the walk
    costs ~10 ms, so there is no reason to sample and then argue about what
    a coarse tripwire missed.  Completeness is the point — the guarantee is
    "this build wrote nothing into the shared repo", and a partial snapshot
    cannot make it.

    The owner's INSTALL is snapshotted beside it, by the caller, through
    :func:`install_snapshot` — the two dicts merge, because their keys
    cannot collide (the repo has no ``Custom Scenery``).
    """
    repo = Path(repo or DATA_REPO)
    snap = {}
    for name in SHARED_DATA_DIRS:
        top = repo / name
        if not top.is_dir():
            continue
        for dirpath, _dirnames, filenames in os.walk(top):
            for fn in filenames:
                p = Path(dirpath) / fn
                try:
                    st = p.stat()
                except OSError:
                    continue
                snap[str(p.relative_to(repo))] = (st.st_size, st.st_mtime_ns)
    return snap


def snapshot_diff(before: dict, after: dict) -> dict:
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    modified = sorted(k for k in (set(after) & set(before))
                      if after[k] != before[k])
    return {"added": added, "modified": modified, "removed": removed}


def _file_stamp(repo: Path, rel: str, max_hash_bytes: int = 64 * 1024 * 1024):
    """Hash-stamp one file.  Small files get a sha256; a multi-gigabyte
    imagery tile gets size+mtime, because hashing it would cost more than
    the refresh did and the identity question it answers is the same."""
    p = repo / rel
    try:
        st = p.stat()
    except OSError:
        return {"path": rel, "missing": True}
    out = {"path": rel, "size": st.st_size, "mtime_ns": st.st_mtime_ns}
    if st.st_size <= max_hash_bytes:
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        out["sha256"] = h.hexdigest()
    else:
        out["sha256"] = None
        out["note"] = "too large to hash; size+mtime stamped instead"
    return out


def _clonefile(source: str, target: str) -> bool:
    """APFS ``clonefile(2)``: a REAL file at ``target`` sharing the source's
    data BLOCKS copy-on-write, in the FILESYSTEM.  True on success.

    This is the primitive the overlay law rests on.  A clone is not a link
    of any kind: it has its own inode, its own metadata and its own
    directory entry, and the first write to EITHER side privately copies
    the blocks it touches.  So a writer that truncates the clone in place —
    which is exactly what the engine's sidecar writers do — cannot reach
    the shared file, and no interception is needed to stop it.

    Measured 2026-08-12 on the real corpus: 1,131 files / 22 GB apparent
    cloned in 0.10 s for ~420 KB of actual disk.

    Total and quiet: any failure (a non-APFS or cross-volume target, an
    older kernel, a target that exists) returns False so the caller can
    fall back to a real copy.  It never raises.
    """
    try:
        import ctypes
        lib = _clonefile._lib                       # type: ignore[attr-defined]
        if lib is None:
            return False
    except AttributeError:
        import ctypes
        try:
            lib = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
            if not hasattr(lib, "clonefile"):
                lib = None
            else:
                lib.clonefile.argtypes = [ctypes.c_char_p, ctypes.c_char_p,
                                          ctypes.c_int]
                lib.clonefile.restype = ctypes.c_int
        except OSError:
            lib = None
        _clonefile._lib = lib                       # type: ignore[attr-defined]
        if lib is None:
            return False
    try:
        # flags=0 FOLLOWS a symlinked source, so a source that is itself a
        # link still yields a clone of the DATA rather than a copied link.
        return lib.clonefile(os.fsencode(source), os.fsencode(target), 0) == 0
    except Exception:
        return False


def mirror_tree_as_overlay(source_root: str, overlay_root: str) -> dict:
    """Mirror ``source_root``'s DIRECTORIES into ``overlay_root`` and seed
    every regular file into it COPY-ON-WRITE.  Returns
    ``{"dirs", "files", "cloned", "copied"}``.

    THE COPY-ON-WRITE OVERLAY.  Redirecting a warm derived cache to an
    empty directory would make every shared sidecar invisible and rebuild
    it per session — a different measurement, not a cleaner one.  So the
    overlay must give reads the warm corpus AND guarantee that a write
    lands lane-local with the shared file byte-untouched.

    WHY NOT SYMLINKS (the measured defect, 2026-08-12, three times in one
    session: two SQ2 classify runs, the r18 KMCI overlay, and the r20
    parallel arms, which rewrote SEVEN OTHH sidecars).  This function
    seeded FILE SYMLINKS into the shared repo and its docstring argued the
    writers ``os.replace`` a temp file onto the name, which replaces the
    link instead of following it.  Some do.  The ones that matter do not:
    ``auto_patch.dsf_reader`` (three sites), ``object_terrain_assembly``
    (two) and ``post_mesh`` open the sidecar path directly as
    ``open(path, "wb")`` — a TRUNCATE IN PLACE, which follows the symlink
    and empties the SHARED file.  And :class:`SharedRepoWriteGuard` was
    structurally blind to it: the open path was lane-local, so the guard
    saw nothing and every such run reported ``blocked: []``.

    WHY NOT HARDLINKS.  A hardlink is the same inode.  Truncate-in-place is
    precisely the write pattern a hardlink does NOT protect against — it
    would corrupt the shared file just as thoroughly, and silently.

    SO: ``clonefile(2)`` (:func:`_clonefile`), falling back to a real
    ``shutil.copyfile``.  Both leave a REAL lane-local file whose first
    write copies rather than follows; neither can be reached from the
    shared side.  There is deliberately NO symlink fallback — a seeding
    mode that cannot make the guarantee is not a cheaper overlay, it is
    the defect above.  The two counts come back separately so a corpus
    that fell back to real copies is a number in the build record rather
    than a surprise in the disk graph.

    Pure and total (no environment, no fixture state) so it has a
    known-answer twin — an instrument without one is not an instrument
    (RULINGS 2026-08-06).  A ``source_root`` that does not exist yields an
    empty overlay rather than an error: a corpus with no cache yet is a
    lawful state, not a failure.

    Moved here 2026-08-11 from ``tests/conftest.py`` (which now delegates)
    so the harness build entry's per-run engine-cache redirect and the
    suite overlay share ONE implementation — the census-wrapper precedent.
    """
    import shutil

    made = {"dirs": 0, "files": 0, "cloned": 0, "copied": 0}
    os.makedirs(overlay_root, exist_ok=True)
    if not os.path.isdir(source_root):
        return made
    for dirpath, _dirnames, filenames in os.walk(source_root):
        relative = os.path.relpath(dirpath, source_root)
        target_dir = (overlay_root if relative == os.curdir
                      else os.path.join(overlay_root, relative))
        if relative != os.curdir and not os.path.isdir(target_dir):
            os.makedirs(target_dir, exist_ok=True)
            made["dirs"] += 1
        for name in filenames:
            source = os.path.join(dirpath, name)
            entry = os.path.join(target_dir, name)
            if not os.path.isfile(source) or os.path.lexists(entry):
                continue
            if _clonefile(source, entry):
                made["cloned"] += 1
            else:
                shutil.copyfile(source, entry)      # lawful, just costlier
                made["copied"] += 1
            made["files"] += 1
    return made


#: DEPRECATED NAME, kept because ``tools/repro_cut.py`` still calls it.
#: It no longer symlinks anything (see :func:`mirror_tree_as_overlay`); the
#: name is a lie the moment you read it, which is why the truthful one is
#: the definition and this is one line of forwarding.
mirror_tree_as_symlinks = mirror_tree_as_overlay


class RefreshLock:
    """A shared-repo write lock, one per scope.

    REFUSE-AND-REPORT, never block (ruling e9daef5 §3).  A lane that waits
    silently on another lane's download looks like a hung build, and a lane
    that ignores the lock races a half-written cache into every other lane's
    next measurement.  A dead holder is reported with its lane and pid and
    needs ``--break-stale-lock`` — never broken automatically, because
    "the pid is gone" and "the write finished" are different facts.
    """

    def __init__(self, scope: str, lane: str, break_stale: bool = False):
        self.scope = scope
        self.lane = lane
        self.break_stale = break_stale
        self.path = LOCK_DIR / f"{scope}.lock"
        self.held = False

    def _payload(self) -> dict:
        return {"scope": self.scope, "lane": self.lane, "pid": os.getpid(),
                "host": os.uname().nodename,
                "started": time.strftime("%Y-%m-%dT%H:%M:%S")}

    @staticmethod
    def _alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def acquire(self) -> "RefreshLock":
        LOCK_DIR.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                         0o644)
        except FileExistsError:
            try:
                holder = json.loads(self.path.read_text())
            except Exception:
                holder = {}
            pid = int(holder.get("pid") or -1)
            alive = self._alive(pid) if pid > 0 else False
            if alive or not self.break_stale:
                raise SystemExit(
                    f"REFUSING: another lane holds the '{self.scope}' "
                    f"refresh lock on the shared repo.\n"
                    f"  holder: lane={holder.get('lane')!r} pid={pid} "
                    f"host={holder.get('host')!r} since "
                    f"{holder.get('started')} "
                    f"({'ALIVE' if alive else 'DEAD — stale lock'})\n"
                    f"  lock:   {self.path}\n"
                    + ("  Wait for it and re-run.  The harness never blocks "
                       "silently on a shared-repo write: a lane waiting on "
                       "another lane's download is indistinguishable from a "
                       "hung build."
                       if alive else
                       "  The holder is gone, but a dead pid does not mean "
                       "the write COMPLETED — the cache may be half-written. "
                       "Inspect it, then re-run with --break-stale-lock."))
            self.path.unlink()
            print(f"  [harness] broke STALE '{self.scope}' lock (holder pid "
                  f"{pid} is gone, --break-stale-lock given)")
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                         0o644)
        with os.fdopen(fd, "w") as fh:
            json.dump(self._payload(), fh)
        self.held = True
        return self

    def release(self) -> None:
        if self.held:
            try:
                self.path.unlink()
            except OSError:
                pass
            self.held = False

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *exc):
        self.release()
        return False


def record_refresh(scope: str, changes: dict, meta: dict,
                   repo=None) -> dict:
    """Append ONE hash-stamped refresh event to the shared repo's ledger.

    "Exactly once, as an explicit logged event" (ruling §2) needs a record
    that outlives the session: the ledger lives in the SHARED repo, so the
    next lane to wonder why a cache changed reads the answer there instead
    of reconstructing it from three lanes' scratchpads.
    """
    repo = Path(repo or DATA_REPO)
    stamps = [_file_stamp(repo, rel)
              for rel in (changes["added"] + changes["modified"])
              if not str(rel).startswith("Custom Scenery/")]
    record = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "scope": scope,
              "added": len(changes["added"]),
              "modified": len(changes["modified"]),
              "removed": changes["removed"], "files": stamps, **meta}
    REFRESH_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(REFRESH_LEDGER, "a") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        fh.write(json.dumps(record) + "\n")
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    return record


#: The timestamp format :func:`record_refresh` writes into every ledger
#: record.  Fixed-width and zero-padded, so a plain STRING comparison is a
#: chronological one — which is why the window test below needs no parsing.
REFRESH_TS_FORMAT = "%Y-%m-%dT%H:%M:%S"


def ledgered_refresh_paths(window_start: str, window_end: str,
                           *, ledger=None) -> dict:
    """Every shared-repo relpath an AUTHORISED ``--refresh-data`` wrote
    between ``window_start`` and ``window_end`` (both ``REFRESH_TS_FORMAT``
    stamps, both inclusive), as ``{relpath: {"ts", "scope"}}``.

    WHY (RULINGS 2026-09-15ay tail).  A concurrent session's authorised,
    ledgered refresh is a shared-repo delta that the observing process did
    not author — the same cross-attribution :func:`redirected_scopes` and
    :class:`BuildInputScope` answer for the build audit.  The suite's
    session detector had no such door, so on 2026-09-15 two ledgered
    ``osm_layers`` writes (13:26:13 and 13:29:27) turned every test of two
    suites into a teardown ERROR.  The ledger is the authorisation record:
    a path named in it inside the observation window was written by an
    explicit, locked, hash-stamped event, not by the observer.

    Pure and read-only: it opens the ledger, never writes it, tolerates a
    missing file (``{}``) and skips a malformed or record-shaped-wrong
    line rather than raising — a detector that crashes on a truncated
    concurrent append is worse than one that misses a downgrade.

    Both ``files[].path`` (added/modified) and ``removed[]`` entries count:
    a removal is a delta the snapshot diff reports exactly like a write.

    STATED RESIDUAL, not solved here: :func:`record_refresh` appends the
    record AFTER the refresh's own after-snapshot, so a refresh whose file
    write landed inside the window but which is still RUNNING at the
    observer's teardown has no record yet, and its delta is still judged
    unlawful.  That is the in-flight case only.
    """
    path = Path(ledger) if ledger is not None else REFRESH_LEDGER
    out: dict = {}
    try:
        text = path.read_text()
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
            ts = record["ts"]
            if not (window_start <= ts <= window_end):
                continue
            scope = record.get("scope")
            rels = [str(e["path"]) for e in record.get("files") or ()
                    if isinstance(e, dict) and e.get("path")]
            rels += [str(r) for r in record.get("removed") or () if r]
        except Exception:
            continue                     # malformed line: skip, never raise
        for rel in rels:
            out[rel] = {"ts": ts, "scope": scope}
    return out


#: THE LOCK-FILE ALLOWANCE (2026-08-07).
#:
#: ``O4_File_Lock.hold_file_lock`` is the engine's ONE cross-process lock
#: primitive: it creates a sibling ``<target>.lock`` with
#: ``os.open(O_CREAT | O_EXCL | O_WRONLY)``, writes ``<pid> <isoformat>``
#: into it through the file DESCRIPTOR, and removes it on exit (including
#: on a stale break).  ``O4_Airport_Elevation_Insets.ensure_base_tile``
#: takes one inside ``Elevation_data/<block>/`` around the
#: download-if-missing critical section — on EVERY base-tile resolution,
#: warm cache included, because the lock is what makes the cached
#: double-check safe between concurrent tile builds.
#:
#: A lock file is COORDINATION STATE, not corpus data: its contents are a
#: pid and a timestamp that nothing reads programmatically, it exists only
#: for the duration of one critical section, and no measurement is a
#: function of it.  Refusing it does not protect the corpus — it makes
#: concurrent-safe cache reads impossible, which is how a real-DEM HECA
#: build came back with no DEM at all (see ``build_airport.py``'s module
#: docstring, item 8 — the swallowed-degradation refusal).
#:
#: The allowance is deliberately the NARROWEST match that covers it: the
#: basename must end in ``.lock`` (the primitive's own naming convention),
#: and only the two operations the primitive performs on it are allowed —
#: an ``os.open`` create and an ``os.remove``/``os.unlink``.  A
#: ``builtins.open`` of a ``.lock`` path, a rename onto one, a directory
#: named ``*.lock``: none of those are lock handling, and all still refuse.
LOCK_ARTIFACT_SUFFIX = ".lock"

#: The guard's operation tokens for the calls
#: :func:`O4_File_Lock.hold_file_lock` makes on its lock file.
LOCK_FILE_OPS = frozenset({"os_open", "remove", "unlink"})


def ledger_lines(path=None) -> list:
    """Every refresh-ledger record, oldest first.  A malformed line is
    skipped rather than fatal: the ledger is append-only across sessions
    and a half-written line from a killed run must not blind the reader."""
    path = Path(path or REFRESH_LEDGER)
    out = []
    try:
        with open(path, "r") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        return []
    return out


def ledger_state(rel: str, mtime: float, records=None) -> str:
    """How the refresh ledger accounts for this artefact's CURRENT state:
    ``"explained"``, ``"stale-line"`` or ``"never-ledgered"``.

    ``explained``: some record NAMES the path and was written at or after
    the file's mtime.  Records carry ``ts`` as local
    ``%Y-%m-%dT%H:%M:%S`` (``record_refresh``), second-resolution, so the
    compare is generous by one second — a stamp written in the same
    second as the write explains it.

    ``never-ledgered`` is called out separately because it is the case
    the reconciliation exists for and the one round 6 got wrong: KPHX's
    +33-112_big_roads was re-derived at 13:48 and NO line named it at
    all (the 13:29:33 ``osm_layers`` line is +33-113's), so a predicate
    phrased only as "the newest line predates its mtime" excluded it.
    """
    records = ledger_lines() if records is None else records
    named_at_all = False
    for rec in records:
        named = [f.get("path") for f in (rec.get("files") or ())]
        if rel not in named and rel not in (rec.get("removed") or ()):
            continue
        named_at_all = True
        try:
            when = time.mktime(time.strptime(str(rec.get("ts", "")),
                                             "%Y-%m-%dT%H:%M:%S"))
        except ValueError:
            continue
        if when + 1.0 >= mtime:
            return "explained"
    return "stale-line" if named_at_all else "never-ledgered"


def ledger_explains(rel: str, mtime: float, records=None) -> bool:
    """True when :func:`ledger_state` says ``explained``.  Kept as the
    one-word question the readers ask."""
    return ledger_state(rel, mtime, records) == "explained"


def record_reconciliation(rels, meta: dict, repo=None) -> list:
    """Stamp the CURRENT hash of each artefact in ``rels`` whose newest
    ledger line predates its mtime.  Returns the paths recorded.

    ONE record per reconciliation run, marked ``reconciled`` so no reader
    mistakes it for a refresh that fetched something: it says "this is
    what is on disk NOW, and nothing in the ledger explained it".  The
    measured case is KPHX's +33-112_big_roads (2026-09-15 13:48) — the
    engine re-derived it and the run exited before the audit.
    """
    repo = Path(repo or DATA_REPO)
    records = ledger_lines()
    why_by_path: dict = {}
    for rel in rels:
        try:
            mtime = (repo / rel).stat().st_mtime
        except OSError:
            continue
        state = ledger_state(rel, mtime, records)
        if state != "explained":
            why_by_path[rel] = state
    if not why_by_path:
        return []
    by_scope: dict = {}
    for rel in sorted(why_by_path):
        by_scope.setdefault(scope_of(rel), []).append(rel)
    for scope, rels_in in sorted(by_scope.items(), key=lambda kv: str(kv[0])):
        record_refresh(scope or "<outside every scope>",
                       {"added": [], "modified": sorted(rels_in),
                        "removed": []},
                       {**meta, "reconciled": True,
                        "reconciled_paths": {r: why_by_path[r]
                                             for r in sorted(rels_in)},
                        "why": "NOTHING in this ledger accounts for these "
                               "artefacts as they stand: each is either "
                               "NEVER-LEDGERED or newer than the newest "
                               "line naming it (per path above).  This "
                               "record stamps their CURRENT hash and "
                               "claims nothing else — the write may have "
                               "been another lane's authorised refresh, "
                               "or a derivation a crash or a later "
                               "refusal put beyond the audit's reach"},
                       repo=repo)
    return sorted(why_by_path)


def is_lock_artifact(relpath) -> bool:
    """True for a cross-process LOCK FILE (never corpus data).

    Path-shape only, so it is the same predicate for the preventer (which
    sees an absolute path mid-build) and for the after-the-fact snapshot
    audit (which sees a repo-relative one): a leaked lock file left by a
    crashed holder is lock churn in both, never a corpus mutation.
    """
    return os.path.basename(str(relpath)).endswith(LOCK_ARTIFACT_SUFFIX)


#: THE LIBRARY-INDEX ALLOWANCE (2026-08-07).
#:
#: ``auto_patch.agp_reader._write_library_index_sidecar`` persists the
#: merged ``library.txt`` virtual→physical map for one X-Plane install to
#: ``Airport_mod_cache/o4_library_index_<sha1(root)[:16]>.cache``, written
#: to a ``.o4_library_index_*.tmp`` sibling and moved into place with
#: ``os.replace``.  It is DERIVED INSTALL-INDEX CACHE: a pure,
#: byte-deterministic function of ``scenery_packs.ini`` and every
#: ``library.txt``, fingerprinted by size and mtime_ns, so any writer
#: produces identical bytes for the same install state.  Nothing in it is
#: corpus data and no measurement is a function of which process wrote it.
#:
#: WHY IT MUST NOT REFUSE, from both ends.  The X-Plane install lives
#: OUTSIDE the guarded repo and is legitimately touched by X-Plane and by
#: the owner's app; the first engine process to consult the index
#: afterwards finds the sidecar stale and rewrites it.  That single write
#: lands inside EVERY concurrently-open harness snapshot window and is
#: cross-attributed to all of them — the nidrepair 2026-08-07 frames
#: (``nidctl_hi``, ``nidctl_lo``) each report ``write_guard_blocked: []``
#: and each name the same modified
#: ``o4_library_index_768a6b59d2781165.cache``, with the install's
#: ``scenery_packs.ini`` mtime inside both build windows: neither build's
#: guarded code wrote it, and both came back CONTAMINATED.  And when a
#: GUARDED build is itself the first reader, the refusal is swallowed by
#: ``agp_reader``'s ``except Exception``, ``guard.blocked`` fills, and
#: :func:`require_no_swallowed_write_block` rc=2s a good build.
#:
#: The allowance is the NARROWEST match that covers it, like the lock
#: one: the path must be DIRECTLY under ``Airport_mod_cache/`` (a matching
#: basename one directory deeper is a different file) and carry the
#: writer's own naming, and only the calls that writer makes are allowed.
#: A ``builtins.open`` of the cache name, a rename onto it, any other
#: file in that directory: none of those are this writer, and all still
#: refuse.
LIB_INDEX_ARTIFACT_RE = re.compile(
    r"Airport_mod_cache/(?:o4_library_index_[0-9a-f]{16}\.cache"
    r"|\.o4_library_index_[A-Za-z0-9_]+\.tmp)")

#: The guard's operation tokens for the calls
#: ``agp_reader._write_library_index_sidecar`` makes on the sidecar:
#: ``mkstemp``'s ``os.open`` of the ``.tmp``, the atomic ``os.replace`` of
#: tmp onto final (BOTH paths match the predicate), and the failure-path
#: unlink of the ``.tmp``.
LIB_INDEX_FILE_OPS = frozenset({"os_open", "replace", "remove", "unlink"})


def is_library_index_artifact(relpath) -> bool:
    """True for the DERIVED library-index sidecar (never corpus data).

    Path-shape only, so it is the same predicate for the preventer (whose
    ``_violation`` has already resolved the write to a repo-relative
    path) and for the after-the-fact snapshot audit (which sees a
    repo-relative one): a sidecar refreshed by a concurrent engine
    process is index churn in both, never a corpus mutation.  Matched
    against the WHOLE relative path, so the allowance cannot be reached
    from a subdirectory.
    """
    return bool(LIB_INDEX_ARTIFACT_RE.fullmatch(str(relpath)))


class SharedRepoWriteBlocked(RuntimeError):
    """A build tried to write the shared data repo outside an authorised
    ``--refresh-data`` scope, and the guard stopped it."""


class SharedRepoWriteGuard:
    """THE PREVENTER (fix cycle 2 item 4).

    The detector below is the backstop; this is the lock.  It refuses the
    write AT THE CALL, from inside the build process, naming the path, the
    scope, and the flag that would authorise it — so the offending write
    surfaces with a traceback pointing at the code that made it, instead of
    as a filename in an after-the-fact diff.

    WHY A PREVENTER WAS NEEDED.  ``report_unauthorised_writes`` used to
    carry the line "the harness cannot PREVENT a write inside the engine
    without touching ``src/``".  That was true of a *filesystem* lock and
    false of the interpreter: the harness calls ``build_airport_pavement``
    IN PROCESS, so it owns the same ``builtins.open`` and ``os`` the engine
    will use.  The re-baseline settled the question by catching two LIVE
    instances — ``OSM_data/_airport_road_feed/CYXY_road_feed.cache`` and
    ``SPLP_road_feed.cache``, written by the CYXY and SPLP builds — after
    the fact, from six concurrent runs whose before/after snapshots each
    saw BOTH writes.  Detection alone therefore produced a
    ``contaminated=True`` flag that was CROSS-ATTRIBUTED across lanes and a
    corpus that had already changed under everyone.  Only refusing at the
    call site attributes the write to its author and leaves the corpus
    intact.

    SCOPE, stated honestly.  This intercepts writes issued through the
    Python level: ``builtins.open`` in a writing mode, ``os.open`` with a
    writing flag, and the rename/replace/unlink/mkdir family.  A write
    performed inside a C extension's own file handling (GDAL, a bare
    ``numpy.memmap``) does not pass through these, which is exactly why the
    before/after snapshot audit STAYS: prevent what can be prevented,
    detect the remainder.  Defence in depth, not one mechanism claimed to
    be complete.  A stdlib module that CAPTURED ``builtins.open`` at import
    time is the same blindness in Python (``bz2``, and every ``.osm.bz2``
    layer cache with it — measured 2026-09-15); ``__enter__`` patches that
    binding too.

    THE PATH IT JUDGES IS THE RESOLVED ONE (2026-08-12).  A write is a
    shared-repo write when it REACHES the shared repo, whatever the string
    at the call site says: a lane-local overlay entry that is a symlink
    into the corpus is the measured case, and until this landed the guard
    compared the lane-local string, matched nothing and reported
    ``blocked: []`` while ``open(entry, "wb")`` truncated the shared file
    through the link.  See :func:`mirror_tree_as_overlay`, which removes
    the condition, and ``_violation``, which no longer depends on it
    having been removed.

    ALWAYS-ALLOWED: the harness's own state directory (``.harness/`` — the
    refresh ledger and the lock files), every path under an authorised
    scope, and — each for the calls that handle it — the engine's own
    cross-process ``.lock`` files (:data:`LOCK_ARTIFACT_SUFFIX`), which are
    coordination state, and the library-index sidecar
    (:data:`LIB_INDEX_ARTIFACT_RE`), which is derived cache determined by
    the X-Plane install.  Neither is corpus data.  Reads are never touched.
    """

    #: ``os.open`` flags that mean "this call can modify the file".
    _WRITE_FLAGS = (os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT
                    | os.O_TRUNC)

    def __init__(self, requested, root, repo=None, enabled: bool = True,
                 record_only: bool = False,
                 allow_library_index: bool = True,
                 install_roots=()):
        self.requested = set(requested or ())
        self.repo = Path(repo or DATA_REPO)
        self.enabled = bool(enabled)
        #: Observe instead of prevent (suite-corpus-clean spec).
        self.record_only = bool(record_only)
        #: Whether the library-index allowance applies — harness builds
        #: keep it; the suite's per-test guard turns it off
        #: (suite-corpus-clean spec §8.2 R-e).
        self.allow_library_index = bool(allow_library_index)
        #: ABSOLUTE roots of the owner's X-Plane install(s) this guard
        #: defends under scope ``pack_rebake``.  EMPTY by default, so a
        #: caller that names none behaves exactly as before — the suite's
        #: own install guard (``tests/conftest.py``, 2026-08-09) is a
        #: SUBCLASS that overrides ``_violation`` outright and is
        #: untouched either way.  The harness build entry passes the
        #: install it builds against.
        self._install_roots = tuple(sorted({
            p for r in (install_roots or ())
            for p in (os.path.abspath(os.fspath(r)),
                      os.path.realpath(os.fspath(r)))}))
        self.blocked: list = []
        #: Every lock-file operation the allowance let through, recorded so
        #: "the repo was untouched apart from the ruled lock churn" is a
        #: fact in the artifact rather than a claim in a report.
        self.lock_churn: list = []
        #: Every library-index sidecar operation the allowance let
        #: through, recorded for the same reason: a derived-cache refresh
        #: that is invisible is indistinguishable from one that never
        #: happened, and every harness build on 2026-08-07 was flagged on
        #: exactly that.
        self.library_index_churn: list = []
        # Cheap textual prefixes: the shared repo itself, and this lane's
        # mount points (which are SYMLINKS into it, so a relative
        # ``OSM_data/...`` write never mentions the repo path at all).
        # ABSOLUTE on both sides — the candidate path is abspath'd before
        # the compare, so a relative prefix would never match and the guard
        # would pass everything while looking installed.
        lane = Path(root).resolve()
        self._prefixes = tuple(
            str(p) for p in
            [self.repo.resolve() / d for d in SHARED_DATA_DIRS]
            + [lane / d for d in SHARED_DATA_DIRS])
        self._saved: dict = {}
        #: ``bz2._builtin_open`` as it was before arming — see the note in
        #: ``__enter__``; kept apart from ``_saved`` because that dict is
        #: restored onto the ``os`` module.
        self._saved_bz2 = None

    # ── the predicate ────────────────────────────────────────────────
    def _install_violation(self, abspath):
        """``(rel, scope)`` when ``abspath`` is a write into the owner's
        X-Plane install, else ``None``.

        THE HOLE THIS CLOSES (2026-09-15, RULINGS 2026-09-15av).  The
        object stage's write half rewrites the SERVING PACK — its DSF,
        its re-baked ``.obj`` bodies, its ``.anchor_bak`` backups — in
        ``<install>/Custom Scenery/<pack>/``, which is outside the data
        repo, so every prefix this class had missed it.  Lane
        v2vmmcshore's harness TILE build of +22+113 rewrote the OWNER'S
        live VHHH pack (6,390 placements) at 11:49; the contamination
        flag then surfaced on a DIFFERENT lane's concurrent build.

        A path under ``Custom Scenery`` is named that way so
        :func:`scope_of` maps it to ``pack_rebake`` (the data repo has no
        such directory, so the prefix cannot collide); anything else in
        the install belongs to no scope and is therefore unauthorisable
        — which is correct, since no ``--refresh-data`` flag should ever
        let a build write the user's CIFP or Global Scenery.
        """
        for root in self._install_roots:
            if abspath == root or abspath.startswith(root + os.sep):
                rel = install_relpath(abspath)
                scope = scope_of(rel)
                if scope is not None and scope in self.requested:
                    return None
                return rel, scope
        return None

    def _violation(self, path, op=None):
        """``(rel, scope)`` if writing ``path`` is forbidden, else None.

        ``op`` is the guard's own token for the call being made (``open``,
        ``os_open``, ``rename``, ``mkdir``, …).  It exists for ONE reason:
        each allowance is scoped to the operations its writer actually
        performs (:data:`LOCK_FILE_OPS`, :data:`LIB_INDEX_FILE_OPS`), so an
        allowed path reached by any other call still refuses.  The default
        (``None``) is the conservative one — no allowance.
        """
        try:
            s = os.fspath(path)
        except TypeError:
            return None                        # an fd, not a path
        if not isinstance(s, (str, bytes)):
            return None
        if isinstance(s, bytes):
            s = s.decode("utf-8", "replace")
        ap = s if os.path.isabs(s) else os.path.abspath(s)
        if not ap.startswith(self._prefixes):
            # THE WRITE-THROUGH HOLE (measured 2026-08-12, three times in
            # one session — see mirror_tree_as_overlay).  A lane-local
            # overlay entry that is a SYMLINK into the shared repo is a
            # shared-repo write: ``open(entry, "wb")`` follows the link and
            # truncates the shared file, while every string the guard was
            # comparing said "lane-local".  Every such run reported
            # ``blocked: []`` — the guard was not lenient, it was blind.
            #
            # So the cheap prefix test is a fast ACCEPT, never the whole
            # answer: on a miss, resolve and ask again.  What a write
            # REACHES is what it writes.  ``realpath`` resolves the parents
            # of a not-yet-existing file and leaves the tail, so a create
            # through a symlinked directory is caught too.  It costs a few
            # microseconds against a file write, and it is belt to the
            # overlay's braces: with copy-on-write seeding no lawful
            # overlay write can resolve into the repo at all.
            try:
                real_s = os.path.realpath(ap)
            except OSError:
                return None
            if real_s == ap or not real_s.startswith(self._prefixes):
                # THE OWNER'S X-PLANE INSTALL (2026-09-15, RULINGS
                # 2026-09-15av).  Outside the data repo by construction,
                # so every prefix above misses it — and the object
                # stage's write half rewrites packs THERE.  Judged with
                # the ENGINE's own live-install predicate and named
                # ``Custom Scenery/...`` so the scope resolves.
                hit = self._install_violation(real_s)
                if hit is not None:
                    return hit
                return None                    # genuinely outside the repo
            ap = real_s
        try:                                   # follow the lane's symlinks
            real = Path(ap).resolve()
            rel = str(real.relative_to(self.repo.resolve()))
        except (OSError, ValueError):
            return None                        # not in the shared repo
        if rel.startswith(".harness"):
            return None                        # the harness's own state
        if op in LOCK_FILE_OPS and is_lock_artifact(rel):
            # COORDINATION STATE, not corpus data — see
            # LOCK_ARTIFACT_SUFFIX.  Recorded, never silent.
            self.lock_churn.append({"path": rel, "op": op})
            return None
        if (self.allow_library_index and op in LIB_INDEX_FILE_OPS
                and is_library_index_artifact(rel)):
            # DERIVED INSTALL-INDEX CACHE, not corpus data — see
            # LIB_INDEX_ARTIFACT_RE.  Recorded, never silent.
            self.library_index_churn.append({"path": rel, "op": op})
            return None
        scope = scope_of(rel)
        if scope in self.requested:
            return None
        return rel, scope

    def _refuse(self, rel, scope, how):
        self.blocked.append({"path": rel, "scope": scope, "via": how})
        if self.record_only:
            return                             # observe, let the call run
        where = ("the OWNER'S X-PLANE INSTALL"
                 if scope == "pack_rebake" or not str(rel).startswith(SHARED_DATA_DIRS)
                 else f"the SHARED data repo ({self.repo})")
        raise SharedRepoWriteBlocked(
            f"BLOCKED: this build tried to {how} '{rel}' in {where}, "
            f"which no --refresh-data scope authorises.\n"
            f"  scope: {scope or '<outside every named scope>'}"
            + (f"\n  {scope_description(scope)}" if scope else "")
            + f"\nOwner ruling e9daef5: a cache regeneration is an EXPLICIT, "
              f"locked, hash-stamped event — never a build side effect. Every "
              f"other lane reads this corpus.\n"
              f"To do it deliberately, re-run with: --refresh-data "
              f"{scope or ','.join(sorted(s for s, _p, _w in REFRESH_SCOPES))}")

    # ── installation ─────────────────────────────────────────────────
    def __enter__(self):
        if not self.enabled:
            return self
        import builtins
        import shutil
        guard = self

        real_open, real_os_open = builtins.open, os.open
        self._saved = {"open": real_open, "os_open": real_os_open}

        def _open(file, mode="r", *a, **kw):
            if any(c in mode for c in "wxa+"):
                hit = guard._violation(file, op="open")
                if hit:
                    guard._refuse(hit[0], hit[1], "open for writing")
            return real_open(file, mode, *a, **kw)

        def _os_open(path, flags, *a, **kw):
            if flags & guard._WRITE_FLAGS:
                hit = guard._violation(path, op="os_open")
                if hit:
                    guard._refuse(hit[0], hit[1], "os.open for writing")
            return real_os_open(path, flags, *a, **kw)

        builtins.open, os.open = _open, _os_open

        # THE bz2 HOLE (measured 2026-09-15, lane v2schemarefuse).
        # ``bz2`` binds the builtin AT IMPORT TIME —
        # ``from builtins import open as _builtin_open`` — so every
        # ``bz2.open(path, "wt")`` calls the ORIGINAL open and never
        # reaches the wrapper above.  EVERY cached OSM layer in the repo
        # is a ``.osm.bz2``, so the whole ``osm_layers`` scope was
        # invisible to the preventer by construction: when v2roadtags
        # bumped ``ROAD_CACHE_TAG_SCHEMA`` the next guarded build
        # rewrote ``+40-004_big_roads.osm.bz2`` through
        # ``O4_OSM_Utils.OSM_layer.write_to_file`` and the guard could
        # only REPORT it afterwards, from the snapshot diff (RULINGS
        # 2026-09-15u).  Patching the module attribute closes it for
        # every bz2 writer at once — a road-layer special case would
        # leave the same hole open for the water and coastline caches.
        # ``gzip`` and ``lzma`` look ``builtins.open`` up at CALL time
        # (``builtins.open(...)``) and are already covered; verified
        # against the stdlib source, not assumed.
        import bz2
        if getattr(bz2, "_builtin_open", None) is not None:
            self._saved_bz2 = bz2._builtin_open
            bz2._builtin_open = _open

        # The mutating path operations.  ``src``-side arguments are checked
        # too for the two-path calls: a rename OUT of the repo destroys the
        # cached artifact just as surely as one into it.
        for name, n_paths in (("rename", 2), ("replace", 2), ("remove", 1),
                              ("unlink", 1), ("rmdir", 1), ("mkdir", 1),
                              ("makedirs", 1), ("truncate", 1)):
            real = getattr(os, name, None)
            if real is None:
                continue
            self._saved[name] = real

            def _wrap(*a, _real=real, _n=n_paths, _nm=name, **kw):
                for p in a[:_n]:
                    # mkdir/makedirs on a directory that ALREADY exists
                    # mutates nothing (makedirs(exist_ok=True) no-ops;
                    # os.mkdir raises FileExistsError before touching the
                    # repo) — the engine ensure-dirs its cache paths on
                    # every tile build, and refusing the no-op made warm
                    # tile builds impossible through a mounted repo.
                    if _nm in ("mkdir", "makedirs") and os.path.isdir(p):
                        continue
                    hit = guard._violation(p, op=_nm)
                    if hit:
                        guard._refuse(hit[0], hit[1], f"os.{_nm}")
                return _real(*a, **kw)

            setattr(os, name, _wrap)

        # shutil's copy family opens through ``builtins.open`` on CPython,
        # but ``move`` can fall through to ``os.rename`` on the same device
        # and ``copytree`` builds directories first — both already covered
        # above.  Nothing further to patch; recorded so the next reader does
        # not re-derive it.
        del shutil
        return self

    def __exit__(self, *exc):
        if not self.enabled:
            return False
        import builtins
        if self._saved_bz2 is not None:
            import bz2
            bz2._builtin_open = self._saved_bz2
            self._saved_bz2 = None
        if "open" in self._saved:
            builtins.open = self._saved.pop("open")
        if "os_open" in self._saved:
            os.open = self._saved.pop("os_open")
        for name, real in self._saved.items():
            setattr(os, name, real)
        self._saved = {}
        return False


# ══════════════════════════════════════════════════════════════════════
# THE WINDOW-ATTRIBUTION INSTRUMENT (2026-09-01, beta hardening H6 item 6)
# ══════════════════════════════════════════════════════════════════════
# THE MEASURED DEFECT, flagged independently by three lanes.  The audit
# below diffs the WHOLE shared repo across the build's wall-clock window
# and attributes every delta in it to THIS build.  A window is not an
# author: builds run concurrently by ruling ("Builds parallel when not
# timing"), an authorised ``--refresh-data`` in lane B lands inside lane
# A's window, and the owner's own app writes the corpus while a suite
# runs.  The library-index allowance above is the same defect solved once
# for one file — the nidrepair 2026-08-07 frames each reported
# ``write_guard_blocked: []`` and each named the same modified sidecar
# neither of them wrote.  Nothing generalised it.
#
# THE INSTRUMENT.  A delta is still NAMED, always — nothing is dropped —
# but it is labelled EXTERNAL-CANDIDATE instead of CONTAMINATED when BOTH
# hold:
#
#   1. the build's own guard blocked NOTHING (``write_guard_blocked`` is
#      empty).  A guard-blocked write says this build's code did try to
#      write the corpus and was stopped; anything that then appears is
#      this build's business and CONTAMINATES, whatever it names.  This
#      is deliberately a WHOLE-RUN veto and not a per-path one: the guard
#      records the path it blocked, but a build that swallowed one
#      refusal is not a build whose remaining writes can be trusted to
#      name themselves.
#   2. the path is provably OUTSIDE this build's INPUT SET — it names a
#      TILE, and not one of the tiles this build reads (see
#      :class:`BuildInputScope`).
#
# EXTERNAL-CANDIDATE, never EXTERNAL: the audit cannot prove another
# process wrote it, only that this build had no reason to.  It is a
# weaker claim and it is labelled as one.  Everything else — an in-scope
# path, an unscopable path, any path at all when the guard blocked
# something, and every delta when the caller names no input set —
# CONTAMINATES exactly as before.  The default is unchanged strictness:
# an entry that passes no ``input_scope`` gets the old behaviour to the
# letter.

#: A tile named in the ``+DD+DDD`` spelling (``O4_File_Names.short_latlon``
#: — ``OSM_data/+30+030/+30+031/…``, ``Masks/+30+030/+30+031/…``,
#: ``Airport_mod_cache/<pack>/+35-081.dsf.<hash>.text``,
#: ``Default_DSF_cache/<hash>/+50+010.dsf.tmp.text``).  Bounded by a
#: non-digit on both sides so a longer number never yields a phantom tile.
_TILE_SHORT_RE = re.compile(r"(?<![0-9])([+-][0-9]{2})([+-][0-9]{3})(?![0-9])")

#: The same tile in the SRTM spelling (``Elevation_data/+30+030/
#: N30E031.hgt``, ``N30E031_airport_insets/…``).
_TILE_STEM_RE = re.compile(r"(?<![A-Za-z0-9])([NS])([0-9]{2})([EW])([0-9]{3})"
                           r"(?![0-9])")


def tiles_named_in(relpath) -> set:
    """Every ``(lat, lon)`` tile this shared-repo path names, in either
    spelling.  Empty when the path names no tile at all.

    Path-shape only — the same predicate for a repo-relative audit path
    and for an absolute one, and it never touches the filesystem.  Both
    spellings are read because the corpus uses both: the DEM tree is
    ``N30E031.hgt`` and everything else is ``+30+031``, and a scoping
    rule that knew only one of them would call half the corpus unscopable
    and quietly keep contaminating on it.
    """
    rel = str(relpath)
    out = set()
    for a, b in _TILE_SHORT_RE.findall(rel):
        out.add((int(a), int(b)))
    for ns, la, ew, lo in _TILE_STEM_RE.findall(rel):
        lat = int(la) * (-1 if ns == "S" else 1)
        lon = int(lo) * (-1 if ew == "W" else 1)
        out.add((lat, lon))
    return out


def airports_named_in(relpath):
    """The ICAO a per-airport shared-repo artifact names, or ``None``.

    Today that is exactly the road-feed sidecar
    (``OSM_data/_airport_road_feed/<ICAO>_road_feed.cache``) — the KCLT
    precedent's own artifact class, and the one the write guard caught
    live at CYXY and SPLP.  It carries no tile in its name, so without
    this it would be unscopable and every concurrent lane's feed would
    contaminate every other lane.
    """
    m = re.fullmatch(r"OSM_data/_airport_road_feed/([A-Z0-9]{3,4})_road_feed"
                     r"\.cache", str(relpath))
    return m.group(1) if m else None


#: A per-pack derived-cache path: ``Airport_mod_cache/<pack folder name>/…``
#: (``auto_patch.dsf_reader.airport_mod_cache_dir``).  The pack name is
#: the X-Plane Custom Scenery folder's basename, spaces and all.
_MOD_CACHE_PACK_RE = re.compile(r"Airport_mod_cache/([^/]+)/.+")


def mod_cache_pack_of(relpath):
    """The scenery PACK a per-pack derived-cache path belongs to, or
    ``None`` for every other path.

    Most of a pack's cache dir names NO tile (measured 2026-09-13, the
    HECA pack during a +40-004 LEMD mesh-only run: 67
    ``o4_object_partition_<hash>.cache``, 60 ``o4_object_pad_frame_<hash>
    .cache``, 9 ``o4_object_exclusions_<hash>.cache`` — 117 paths keyed
    by content hash alone), so under the tile rule every one of them was
    unscopable, and a concurrent lane's object stage contaminated a run
    whose own guard had blocked nothing.  The pack name is the scope
    those paths DO carry.
    """
    m = _MOD_CACHE_PACK_RE.fullmatch(str(relpath))
    return m.group(1) if m else None


def mod_cache_packs_naming(tiles, repo=None) -> set:
    """The pack folders under the shared ``Airport_mod_cache`` whose cache
    dir holds at least one entry naming one of ``tiles``.

    The derivation of a build's PACK scope, read off the corpus ONCE at
    arm time (a directory listing, ~180 packs, no file is opened): a
    pack that has cached anything for a tile this build reads
    (``+40-004.dsf.text``, ``o4_object_footprints_+40-004.cache``) is a
    pack this build's object stage can rewrite hash-keyed sidecars for.
    ``tiles`` is the WITH-NEIGHBOURS set, so the seam packs count.  A
    pack that has cached nothing for those tiles is one this build has
    no reason to touch — and a pack that appears NEW inside the window
    writes its tile-named dump first, which the tile rule still holds in
    scope.  Filesystem state is read here and nowhere in
    :class:`BuildInputScope`, so ``covers`` stays path-shape only.
    """
    root = Path(repo) if repo is not None else DATA_REPO
    cache_root = root / "Airport_mod_cache"
    wanted = {(int(la), int(lo)) for la, lo in tiles}
    out = set()
    if not wanted or not cache_root.is_dir():
        return out
    for pack in cache_root.iterdir():
        if not pack.is_dir():
            continue
        try:
            names = os.listdir(pack)
        except OSError:
            continue
        if any(tiles_named_in(n) & wanted for n in names):
            out.add(pack.name)
    return out


class BuildInputScope:
    """WHICH shared-repo paths THIS build could have had a reason to touch.

    Constructed from what the harness already knows about a run — its
    tile(s) and its airport(s) — and used by
    :func:`report_unauthorised_writes` to separate a delta this build
    could plausibly have authored from one that merely landed in its
    window.

    THE NEIGHBOURS ARE IN SCOPE.  A build reads past its own tile at the
    seams (DEM insets, mask rasters, the tile_cut at integer boundaries),
    so the eight neighbours of every tile in scope are IN SCOPE too.
    That is the conservative direction on purpose: a wrongly-in-scope
    path stays CONTAMINATED, which costs a re-run, while a wrongly-out-of
    -scope path would downgrade a real corpus mutation, which costs the
    campaign.  Every widening of this class must go the same way.

    AN UNSCOPABLE PATH IS IN SCOPE.  A path naming neither a tile nor an
    airport (``Geotiffs/…``, ``OSM_data/_regional_extracts/…``) cannot be
    proven outside the input set, so it is not.  "Not provably external"
    is the whole predicate — the instrument downgrades only what it can
    positively exclude.
    """

    def __init__(self, tiles=(), icaos=(), *, packs=None, label=""):
        self.tiles = {(int(la), int(lo)) for la, lo in tiles or ()}
        # ``icaos=None`` means the caller could NOT enumerate its airports
        # (a tile entry with no cached airports layer): a road-feed path
        # is then unscopable, not external — the conservative direction.
        # ``()`` keeps its meaning: no airport is in scope.
        self.icaos_known = icaos is not None
        self.icaos = {str(i).upper() for i in icaos or () if i}
        # ``packs=None`` means the caller scoped NO packs (the pre-
        # 2026-09-14 behaviour: every hash-keyed pack sidecar is
        # unscopable and contaminates).  A set — derived through
        # :func:`mod_cache_packs_naming` — names the packs this build
        # can have reached; a pack outside it is positively external.
        self.packs = None if packs is None else {str(p) for p in packs}
        self.label = label
        self._with_neighbours = {
            (la + dla, lo + dlo)
            for la, lo in self.tiles
            for dla in (-1, 0, 1) for dlo in (-1, 0, 1)}

    def __bool__(self) -> bool:
        """False when the scope names nothing — an empty scope can exclude
        nothing, and must never be mistaken for one that excludes all."""
        return bool(self.tiles or self.icaos)

    def covers(self, relpath) -> bool:
        """True when this build could have had a reason to touch the path.

        The negation is the EXTERNAL-CANDIDATE test, so read it that way:
        a path is external only when it POSITIVELY names something this
        build does not read.
        """
        rel = str(relpath)
        icao = airports_named_in(rel)
        if icao is not None:
            return icao in self.icaos if self.icaos_known else True
        named = tiles_named_in(rel)
        if named:
            return bool(named & self._with_neighbours)
        # THE PACK RULE (2026-09-14): a hash-keyed sidecar under a pack
        # this build never cached for is external; the same sidecar under
        # a pack in scope, or under any pack when the caller scoped none,
        # stays in scope.
        pack = mod_cache_pack_of(rel)
        if pack is not None and self.packs is not None:
            return pack in self.packs
        return True                         # unscopable ⇒ not excludable

    def record(self) -> dict:
        """The scope as it rides in ``<tag>.frame.json``, so a later reader
        can re-derive every EXTERNAL-CANDIDATE verdict this run made."""
        return {
            "label": self.label,
            "tiles": sorted(map(list, self.tiles)),
            "tiles_with_neighbours": sorted(map(list, self._with_neighbours)),
            "icaos": sorted(self.icaos) if self.icaos_known else None,
            "packs": sorted(self.packs) if self.packs is not None else None,
        }


def tile_input_scope(lat, lon, icaos=None, *, label="", repo=None):
    """THE input set of a WHOLE-TILE run — the one derivation both tile
    entries share (``run_tile_mesh_only.py``; ``build_airport.py --tile``
    names its anchor airport the same way through :class:`BuildInputScope`).

    A tile run reads its own Elevation_data tile and insets, its OSM_data
    tile, the neighbours of both at the seams, the road feeds of the
    airports ON the tile (``icaos``, the engine's own per-tile airport
    dictionary; ``None`` when the caller could not enumerate them, which
    keeps every road feed in scope), and the mod-cache packs that have
    cached anything for those tiles (:func:`mod_cache_packs_naming`).
    Everything a concurrent lane writes for ANOTHER tile's packs is then
    positively outside this set — the 2026-09-13 class, 117 HECA-pack
    sidecars failing a +40-004 LEMD mesh-only run as CONTAMINATED with
    its own ``guard.blocked`` empty.
    """
    tiles = [(int(lat), int(lon))]
    with_neighbours = {(tiles[0][0] + dla, tiles[0][1] + dlo)
                       for dla in (-1, 0, 1) for dlo in (-1, 0, 1)}
    return BuildInputScope(
        tiles=tiles,
        icaos=None if icaos is None else list(icaos),
        packs=mod_cache_packs_naming(with_neighbours, repo=repo),
        label=label or f"tile {tiles[0][0]:+03d}{tiles[0][1]:+04d}")


def contaminating_writes(offenders) -> list:
    """The subset of an audit's offenders that CONTAMINATES the run.

    ONE reading of the label, shared by the frame stamp, the refusal and
    the twins — a second copy of ``not o["external_candidate"]`` anywhere
    is the census-wrapper shape.
    """
    return [o for o in offenders if not o.get("external_candidate")]


class _PrintNotes:
    """The ``prog=None`` note sink.

    :func:`report_unauthorised_writes` was written for
    ``build_airport.py``'s ``Progress`` record, which every note also
    lands in ``<tag>.progress``.  An entry with no such record — the
    mesh-only build (``tools/run_tile_mesh_only.py``) — passes none and
    the notes go to stdout instead.  Deliberately the smallest thing that
    satisfies the one call the function makes.
    """

    @staticmethod
    def note(msg: str) -> None:
        print("  [guard] " + msg)


#: The redirectable scopes and the ENGINE accessor that answers "where
#: does this family of files actually live for this process?".  Asked,
#: never re-derived: each accessor owns its own precedence rule
#: (``O4_*_DIR`` overrides the IMPLICIT root only — an explicitly chosen
#: data root, ``set_data_root`` / ``ORTHO4XP_DATA_ROOT``, wins and makes
#: the override INERT), and a copy of that rule here would answer
#: "redirected" for a process the engine is about to write SHARED from.
_REDIRECTABLE_SCOPES = (
    ("airport_mod_cache", "airport_mod_cache_root"),
    ("masks", "masks_root"),
    ("dsf_cache", "Default_dsf_cache_dir"),
)


def redirected_scopes(repo=None) -> set:
    """The scopes whose root THIS PROCESS has pointed OUTSIDE the shared
    repo — so no writer in it, Python or subprocess, can reach the shared
    copy of that family.

    WHY THE AUDIT NEEDS THIS (measured 2026-09-15, lane ``v2objcut``'s
    closing VHHH build).  That run was flagged CONTAMINATED on two
    ``airport_mod_cache`` paths — a new-hash DSFTool dump of the VHHH
    pack and its ``o4_dsf_object_positions`` companion, both stamped
    11:52:31 — while its own frame recorded
    ``airport_mod_cache -> <lane>/tmp/engine_caches/Airport_mod_cache``
    and its guard blocked NOTHING.  Both facts cannot be true of one
    author: a Python write of the shared path would have been REFUSED at
    the call (the guard resolves symlinks since 2026-08-12), and the
    DSFTool SUBPROCESS inherits the redirect environment, so it writes
    lane-local too.  The author was another process in the window — the
    same cross-attribution the ``library-index churn`` allowance was
    written for in 2026-08-07, and the same one ``input_scope`` fixed for
    paths OUTSIDE the build's input set; this build's input set names the
    VHHH pack, so that test could not fire.

    A REDIRECTED SCOPE IS A SECOND, INDEPENDENT REASON TO EXTERNALISE.
    It is not an excuse and nothing is hidden: the delta is still named,
    still in the returned list and still in the frame — only the
    attribution changes, exactly as for an out-of-scope path.

    The predicate is the ENGINE's own accessor per scope, asked at audit
    time in the process that did the building, so a redirect the engine
    considers INERT (an explicit data root outranks ``O4_*_DIR``) reads
    as NOT redirected and the contamination verdict stands.
    """
    repo = Path(repo or DATA_REPO).resolve()
    try:
        import O4_File_Names as FNAMES
    except Exception:
        return set()                     # engine not importable: no claim
    out = set()
    for scope, accessor in _REDIRECTABLE_SCOPES:
        try:
            value = getattr(FNAMES, accessor)
            root = value() if callable(value) else value
            if not root:
                continue
            Path(root).resolve().relative_to(repo)
        except ValueError:
            out.add(scope)               # resolves OUTSIDE the repo
        except Exception:
            continue
    return out


def report_unauthorised_writes(changes: dict, requested: set,
                               prog=None, *, blocked=(),
                               input_scope=None, redirected=None) -> list:
    """Every shared-repo write this build made outside an authorised scope.

    THE BACKSTOP.  :class:`SharedRepoWriteGuard` refuses these at the call
    site now; this still runs, because the guard covers the Python level
    and a C extension's own file handling does not pass through it.  A
    write that reaches here got past the lock, so it is named with its
    path, its scope, and a CONTAMINATED marker on the run — a corpus that
    changed mid-build is not the corpus the run started on, and its numbers
    are not comparable with the ones before it.

    LOCK CHURN is reported separately and never contaminates: a ``.lock``
    sibling is coordination state (see :data:`LOCK_ARTIFACT_SUFFIX`), and
    one visible in an after-snapshot means a holder died mid-section, not
    that the corpus changed.  It is named, because a lingering lock does
    block the next lane's critical section until it goes stale.

    LIBRARY-INDEX CHURN is reported the same way and also never
    contaminates: the ``Airport_mod_cache`` sidecar is derived cache (see
    :data:`LIB_INDEX_ARTIFACT_RE`), and one modified inside this build's
    window was rewritten by whichever engine process first noticed the
    X-Plane install had changed — usually not this one.  That
    cross-attribution is why every harness build on 2026-08-07 reported a
    side effect on a file none of them wrote.

    WINDOW ATTRIBUTION (2026-09-01, H6 item 6).  ``input_scope`` — a
    :class:`BuildInputScope` — generalises that one-file allowance into a
    label the audit can apply to any delta: an offender the caller's own
    guard did not block, on a path the build's input set positively
    excludes, is returned with ``external_candidate=True`` and REPORTED
    UNDER ITS OWN HEADING rather than as this build's contamination.  It
    is still in the returned list and still in the frame — the audit
    NAMES every delta, always; only the attribution changes.  Callers
    passing no ``input_scope`` (and every caller that passes an EMPTY
    one) get the pre-2026-09-01 behaviour to the letter: every offender
    contaminates.  Read the split with :func:`contaminating_writes`.
    """
    prog = _PrintNotes if prog is None else prog
    # A guard that blocked something is a whole-run veto on the label:
    # this build's code DID reach for the corpus, so nothing appearing in
    # its window may be handed to a hypothetical other process.
    any_blocked = bool(list(blocked or ()))
    may_externalise = bool(input_scope) and not any_blocked
    # THE SECOND, INDEPENDENT REASON (2026-09-15, the VHHH mis-attribution
    # — see :func:`redirected_scopes`): a scope this process pointed
    # OUTSIDE the repo has no writer that could reach the shared copy,
    # Python or subprocess.  ``None`` asks the engine now; pass an
    # explicit set (``()`` included) to fix the answer.
    redirected = (redirected_scopes() if redirected is None
                  else set(redirected))
    if any_blocked:
        redirected = set()
    offenders, lock_churn, index_churn = [], [], []
    for kind in ("added", "modified", "removed"):
        for rel in changes[kind]:
            if is_lock_artifact(rel):
                lock_churn.append({"path": rel, "kind": kind})
                continue
            if is_library_index_artifact(rel):
                index_churn.append({"path": rel, "kind": kind})
                continue
            scope = scope_of(rel)
            if scope in requested:
                continue
            off_scope = may_externalise and not input_scope.covers(rel)
            off_redirect = scope in redirected
            offenders.append({"path": rel, "kind": kind, "scope": scope,
                              "external_candidate": bool(off_scope
                                                         or off_redirect),
                              "external_reason": ("redirected"
                                                  if off_redirect else
                                                  "out_of_scope"
                                                  if off_scope else None)})
    for lc in lock_churn:
        prog.note(f"   lock churn (coordination state, NOT corpus data): "
                  f"{lc['kind']} {lc['path']} — a lock file outliving the "
                  f"build means its holder died inside the critical section")
    for ic in index_churn:
        prog.note(f"   library-index churn (derived cache, NOT corpus "
                  f"data): {ic['kind']} {ic['path']} — a concurrent engine "
                  f"process refreshed the shared install-index sidecar "
                  f"after the X-Plane install's scenery_packs.ini / "
                  f"library.txt changed")
    external = [o for o in offenders if o["external_candidate"]]
    mine = contaminating_writes(offenders)

    # THE EXTERNAL-CANDIDATE HEADING — printed whenever there is one, and
    # printed BEFORE the verdict, because a reader who sees "UNCHANGED"
    # under a list of paths must be able to see why the paths are there.
    for o in external:
        if o.get("external_reason") == "redirected":
            prog.note(
                f"   external-candidate delta (NAMED, not attributed to "
                f"this build): {o['kind']} {o['path']} — this run "
                f"REDIRECTED the '{o['scope']}' root outside the shared "
                f"repo, so no writer in this process could reach the "
                f"shared copy: a Python write would have been refused at "
                f"the call (the guard blocked nothing) and a subprocess "
                f"inherits the redirect.  Another process in this window "
                f"is the author; this run is NOT flagged CONTAMINATED on "
                f"it.  (Measured: the VHHH pack dump of 2026-09-15 "
                f"11:52:31, RULINGS 2026-09-15ar.)")
            continue
        prog.note(f"   external-candidate delta (NAMED, not attributed to "
                  f"this build): {o['kind']} {o['path']} — outside this "
                  f"build's input set {input_scope.record()['tiles'] or ''}"
                  f"{sorted(input_scope.icaos) or ''} and this build's write "
                  f"guard blocked nothing.  Another process in this window "
                  f"is the likely author; this run is NOT flagged "
                  f"CONTAMINATED on it.")
    if external:
        prog.note(f"   {len(external)} external-candidate path(s): the "
                  f"window is not the author (2026-09-01, H6 item 6).  If "
                  f"you need certainty, re-run with no concurrent lane.")

    if not mine:
        prog.note("shared repo UNCHANGED by this build (full-surface "
                  "before/after snapshot) — no side-effect mutation"
                  + (f"; {len(lock_churn)} lock file(s) left behind, which "
                     f"are not corpus data" if lock_churn else "")
                  + (f"; {len(index_churn)} library-index sidecar "
                     f"refresh(es), which are derived cache"
                     if index_churn else "")
                  + (f"; {len(external)} EXTERNAL-CANDIDATE delta(s) named "
                     f"above, outside this build's input set"
                     if external else ""))
        return offenders
    prog.note(f"!! SHARED-REPO SIDE EFFECT: this build wrote "
              f"{len(mine)} path(s) NOBODY authorised — owner ruling "
              f"e9daef5 forbids exactly this.  The run is CONTAMINATED: "
              f"every lane's next build reads the changed corpus.")
    by_scope: dict = {}
    for o in mine:
        by_scope.setdefault(o["scope"] or "<outside every scope>",
                            []).append(o)
    for scope, items in sorted(by_scope.items(), key=lambda kv: str(kv[0])):
        prog.note(f"   [{scope}] {len(items)} path(s); "
                  f"e.g. {items[0]['kind']} {items[0]['path']}")
        if scope in {s for s, _p, _w in REFRESH_SCOPES}:
            prog.note(f"      {scope_description(scope)}")
    prog.note(f"   Re-run with --refresh-data "
              f"{','.join(sorted({str(o['scope']) for o in mine}))} "
              f"to make this an EXPLICIT, locked, hash-stamped refresh.")
    return offenders


# ══════════════════════════════════════════════════════════════════════
# THE SWALLOWED-DEGRADATION REFUSALS (2026-08-07)
# ══════════════════════════════════════════════════════════════════════
# A refusal the build CATCHES is not a refusal.  Both of these close the
# same hole from opposite ends — one reads the guard's own record, the
# other reads the built layout — because a single detector here is a
# single point of silence, and this class of defect is invisible in a
# build log by construction (it exits 0).

#: What a lane may do about a blocked write, spelled out at the refusal:
#: the three acts are DIFFERENT and only one of them changes the corpus.
_DEGRADED_OPTIONS = (
    "Your options, and they are three DIFFERENT acts:\n"
    "  * If the blocked path is COORDINATION STATE rather than corpus data "
    "(a lock file is the ruled example — see is_lock_artifact in this "
    "file), the guard should allow that exact operation on that exact path "
    "shape, and the fix is here, in the harness.\n"
    "  * --refresh-data <scope> AUTHORISES the write deliberately: under a "
    "per-scope lock, hash-stamped into the shared refresh ledger.  It "
    "CHANGES THE CORPUS EVERY OTHER LANE READS, so it is an owner-level "
    "act, not a way past a red message.\n"
    "  * --allow-degraded-dem measures in the degraded frame KNOWINGLY.  It "
    "is recorded in <tag>.frame.json and it AUTHORISES NO WRITE — accepting "
    "a worse measurement and changing everyone's data are different acts.")


def require_no_unauthorised_writes(offenders, *, entry: str) -> None:
    """DETECTOR 2 — a write REACHED the corpus despite the armed guard.

    :func:`report_unauthorised_writes` names them; this is the refusal
    every non-``build_airport`` entry owes afterwards, spelled ONCE.  Two
    entries used to carry their own copy of this sentence
    (``run_tile_mesh_only.py`` inline, and the tile profiler not at all),
    which is the census-wrapper shape: the inconsistency, not the text.

    ``entry`` names the run in the message ("mesh-only", "tile profile")
    so the refusal says which tool must be re-run under what.

    An EXTERNAL-CANDIDATE offender (2026-09-01, H6 item 6) does not
    refuse: it is named by the report above and attributed to nobody.
    Read through :func:`contaminating_writes`, the one place that label
    is interpreted.
    """
    offenders = contaminating_writes(offenders)
    if not offenders:
        return
    raise SystemExit(
        f"REFUSING: this {entry} run mutated the shared data repo (paths "
        f"above). Owner ruling e9daef5: warm the cache deliberately with "
        f"tools/harness/build_airport.py --refresh-data <scope>.")


def require_no_swallowed_write_block(blocked, *, allow_degraded: bool = False,
                                     prog=None) -> None:
    """DETECTOR 1 — the guard blocked a write and the build carried on.

    :class:`SharedRepoWriteGuard` raises at the call site, but the engine
    catches: ``auto_patch.elevation._load_airport_dem`` wraps production's
    entire DEM prep in one ``except Exception`` that logs
    ``WARN: production-parity DEM prep failed`` and returns ``None``.  The
    build then grades with NO DEM and exits 0 — measured 2026-08-07 at
    HECA (``tmp/sliver_attrib``): 18.5 k nodes against production's
    34-36 k, whole roles (``retaining_wall``, ``ols_cut``, ``crown_spine``,
    ``gap_interior_ring``) absent, and nothing in the exit code to say so.

    So a blocked write that did NOT abort the build is itself the finding:
    whatever the caller wanted that path for, it did without.
    """
    if not blocked:
        return
    lines = "\n".join(
        f"  - BLOCKED {b.get('via', 'write')} '{b.get('path')}'"
        f"  [scope {b.get('scope') or '<outside every named scope>'}]"
        for b in blocked)
    msg = (f"the shared-repo write GUARD blocked {len(blocked)} write(s) "
           f"DURING this build and the build RETURNED ANYWAY — the engine "
           f"swallowed the refusal and fell back:\n{lines}\n"
           f"A caught refusal degrades the frame in SILENCE (the fallback "
           f"is a log line and rc=0).  No number from this build is "
           f"production's frame.")
    if not allow_degraded:
        if prog is not None:
            prog.note("EXIT rc=1 REFUSED: " + msg)
        raise SystemExit("REFUSING to report this build: " + msg + "\n"
                         + _DEGRADED_OPTIONS)
    if prog is not None:
        prog.note("DEGRADED (accepted by --allow-degraded-dem): " + msg)
    print("  [harness] DEGRADED BUILD (accepted by flag): " + msg)
