"""THE BASE-ARM ARTIFACT LEDGER — build the reference side ONCE, ever.

Not a CLI.  The store behind ``build_airport.py --base-arm`` /
``--from-ledger`` (spec ``docs/specs/blast-sweep-and-artifact-ledger-spec.md``,
BS2), and the harness's other half of the cross-session run ledger.

THE MEASURED WASTE.  ``tools/run_with_ledger.py`` remembers whether a
command PASSED at a code state; it forgets what the command PRODUCED.  So a
base arm at an identical tree (7e6df36, 7c03dc4 this session) was rebuilt
2-4x across lanes at 7-10 min each, every time to obtain a patch byte-for-
byte identical to one that already existed on this machine.  This is
[[single-pass-principle]] applied to builds: build once, serve every later
consumer from the recorded artifact.

WHAT KEYS AN ARTIFACT (any difference is a MISS, and the miss says which
component moved):

* the **code tree hash** — the run ledger's own, uncommitted changes
  included, so a dirty tree never serves a clean tree's patch;
* the **ICAO**;
* the **O4_\\* environment** the run ledger already keys on, minus the
  variables that are per-run BY CONSTRUCTION (``O4_HARNESS_IN_LEDGER`` and
  the two lane-local engine cache redirects, which name the tag's own
  directory and would make every key unique);
* the **corpus stamp** — the shared data repo as THIS build reads it: which
  corpus each data dir mounts, the tile's base raster / inset / airports-layer
  cache state, a content stamp of the named base rasters, and the effective
  DEM-frame cfg keys.  A corpus-stamp mismatch is a MISS and never a hit:
  the KCLT road-feed refresh that ran inside a tile build on 2026-08-05 and
  silently changed campaign hashes is exactly the event this component
  exists to notice — a changed corpus is a different measurement;
* the **build variant** — the synthetic DEM constant and the knowingly-
  degrading flags.  A −500 m oracle patch is not a real-DEM patch, and a
  patch kept in spite of a missing sidecar is not a measurable one.

WHAT IT NEVER DOES.  It never writes the shared data repo (the store lives
under ``~/.ortho4xp/artifact_ledger``, gitignored, machine-local,
``O4_ARTIFACT_LEDGER_DIR`` to move it); it never serves a TIMING run (the
caller refuses the combination — a stored artifact has no wall time to
report); it changes no guard semantics, because a served arm runs no engine
code at all.

THE STORE-TIME RE-CHECK.  The key's tree component is captured at build
START; a build's code tree can MOVE before its store (measured 2026-08-28:
a worker-pool child that outlived its parent finished after source edits
landed and stored a LEMD plate under the clean PRE-EDIT tree hash — a
poisoned entry any later lane at that hash would be served).  So
``store_build`` re-checks the tree hash and dirty flag AT STORE TIME when
the caller passes ``code_state`` and refuses on any mismatch with
:class:`ContaminatedKeyError` — loudly, and it NEVER re-keys: a silent
re-key would store an artifact under a tree that never built it, the same
poison from the other side.

Eviction is a size-capped LRU (``O4_ARTIFACT_LEDGER_MAX_MB``, default 4096),
stamped into ``evictions.jsonl`` — an artifact that vanished silently would
turn into a rebuild nobody could explain.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: The store.  OUTSIDE the shared data repo on purpose (owner ruling
#: e9daef5): it is a lane-shared CACHE OF PRODUCTS, and products stay out of
#: the corpus every lane measures against.
DEFAULT_STORE = Path(os.environ.get(
    "O4_ARTIFACT_LEDGER_DIR",
    str(Path.home() / ".ortho4xp" / "artifact_ledger")))

#: Per-run by construction — including them would make every key unique and
#: the ledger a write-only directory.
VOLATILE_ENV = ("O4_HARNESS_IN_LEDGER", "O4_DSF_CACHE_DIR",
                "O4_AIRPORT_MOD_CACHE_DIR", "O4_RUN_LEDGER_PATH",
                "O4_ARTIFACT_LEDGER_DIR", "O4_ARTIFACT_LEDGER_MAX_MB")

#: The artifacts a patch build produces, and which of them a served arm must
#: reproduce byte-for-byte.  ``patch`` and ``sidecar`` are the measurement;
#: ``frame`` and ``env`` are what makes it quotable.
ARTIFACT_ROLES = ("patch", "sidecar", "frame", "env", "result")
REQUIRED_ROLES = ("patch", "sidecar", "frame")


def store_dir(store=None) -> Path:
    return Path(store) if store is not None else DEFAULT_STORE


def max_bytes() -> int:
    return int(os.environ.get("O4_ARTIFACT_LEDGER_MAX_MB", "4096")) * (1 << 20)


def _sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha_of(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


class ContaminatedKeyError(RuntimeError):
    """The code tree moved between key time and store time.

    Storing anyway would poison the PRE-move key with a post-move artifact
    (the 2026-08-28 LEMD plate: a worker-pool child survived its parent,
    finished after source edits landed, and keyed the entry by the clean
    pre-edit tree).  Re-keying to the CURRENT tree is the same poison from
    the other side — the current tree never ran this build.  The only
    lawful outcome is a loud refusal; the run is recorded CONTAMINATED-KEY
    by the caller and its artifacts stay on disk, un-served."""


def code_state_now(root=None) -> dict:
    """The code tree AS OF NOW — the run ledger's own tree hash
    (uncommitted changes included) plus the git dirty flag.  ONE
    implementation for the build-start snapshot and the store-time
    re-check; a second spelling of "what state is the code in" is the
    census-wrapper defect in a smaller costume."""
    root = Path(root or ROOT)
    tools = str(ROOT / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    from run_with_ledger import code_tree_hash
    dirty = bool(subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        capture_output=True, text=True, timeout=20, check=True
    ).stdout.strip())
    return {"code_tree_hash": code_tree_hash(str(root)), "git_dirty": dirty}


def key_env(environ=None) -> dict:
    """The O4_* env the RUN ledger keys on, minus the per-run variables.

    Deliberately routed through ``run_with_ledger.relevant_env`` rather than
    re-deriving the rule: two implementations of "what environment changes a
    result" is the census-wrapper defect in a smaller costume.
    """
    tools = str(ROOT / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    from run_with_ledger import relevant_env
    if environ is None:
        env = relevant_env()
    else:
        env = {k: v for k, v in environ.items()
               if (k.startswith("O4_") or k == "PYTEST_ADDOPTS")
               and k != "O4_RUN_LEDGER_PATH"}
    return {k: v for k, v in env.items() if k not in VOLATILE_ENV}


def corpus_stamp(frame: dict, root=None) -> dict:
    """The corpus this build reads, stamped — the component that makes a
    changed corpus a MISS instead of a silent cross-corpus comparison.

    Built from the FRAME RECORD (``data_mounts``, ``dem_cache_before``,
    ``dem_frame_effective``) plus a content hash of the named base rasters,
    so a raster refreshed in place — same path, new bytes — moves the stamp.
    Inset directories are stamped by listing (name, size, mtime): a
    regenerated inset cache is a different corpus, and hashing a directory
    of rasters on every build would cost more than it protects.
    """
    root = Path(root or ROOT)
    cache = frame.get("dem_cache_before") or {}
    files = []
    for rel in (cache.get("base_raster_files") or []) + \
            (cache.get("airports_layer_files") or []):
        p = root / rel
        try:
            files.append({"path": rel, "size": p.stat().st_size,
                          "sha256": _sha256_file(p)})
        except OSError:
            files.append({"path": rel, "missing": True})
    for rel in (cache.get("airport_inset_dirs") or []):
        d = root / rel
        listing = []
        if d.is_dir():
            for name in sorted(os.listdir(d)):
                try:
                    st = (d / name).stat()
                    listing.append([name, st.st_size, st.st_mtime_ns])
                except OSError:
                    listing.append([name, None, None])
        files.append({"path": rel, "dir_listing_sha": _sha_of(listing),
                      "entries": len(listing)})
    parts = {
        "data_repo": frame.get("data_repo"),
        "mounts": _sha_of({n: m.get("realpath")
                           for n, m in (frame.get("data_mounts") or {}).items()}),
        "dem_cache": _sha_of(cache),
        "dem_files": _sha_of(files),
        "dem_frame_cfg": _sha_of(frame.get("dem_frame_effective")),
    }
    return {"sha256": _sha_of(parts), "parts": parts}


def artifact_key(tree: str, icao: str, env: dict, corpus: dict,
                 variant: dict) -> str:
    return _sha_of({"tree": tree, "icao": icao, "env": env,
                    "corpus": corpus.get("sha256"), "variant": variant})


def build_variant(*, const_dem=None, allow_degraded_dem=False,
                  allow_no_sidecar=False, geometry_only=False,
                  solve_model=None, engine=None,
                  law_tables_sha256=None) -> dict:
    """The request shape that changes the ARTIFACT rather than the corpus.

    ``--dem`` is here because a −500 m oracle patch and a real-DEM patch are
    different objects; the two knowing-override flags are here because a
    patch kept in spite of a swallowed degradation or a missing sidecar is
    not the same artifact as one that passed both refusals.
    ``geometry_only`` is here because a patch built with
    ``compute_elevations=False`` (a visual-inspection artifact) is a
    different object from a solved patch — serving one for the other
    would hand a census a patch with no solved surface.
    ``solve_model`` is here for exactly the ``geometry_only`` reason, and
    the spec says so in as many words (``docs/specs/constructive-solve-
    spec.md``, section "Mode plumbing": "the harness passes/records it in
    frame.json and the artifact-ledger variant key (two models = two
    artifacts, never served for each other)").  The whole round is an A/B
    BETWEEN the two models at one tree and one corpus — every other key
    part is identical by construction — so without this the constructive
    arm would be served the iterative arm's patch and the comparison
    would report zero difference.  ``None`` keeps the key a MISS-free
    match for entries stored before the key existed only in the sense
    that it is spelled the same as the default: a caller that knows the
    mode always passes it (``build_airport.py`` does), and the resolver's
    default is ``iterative``, so an old iterative entry and a new
    explicitly-iterative request do NOT share a key.  That is deliberate
    — a stale entry re-earned by one rebuild is cheaper than a wrong
    serve.
    """
    variant = {"dem": const_dem, "allow_degraded_dem": bool(allow_degraded_dem),
               "allow_no_sidecar": bool(allow_no_sidecar),
               "geometry_only": bool(geometry_only),
               "solve_model": solve_model}
    # THE ENGINE (RULINGS 2026-09-03d): a v2 patch and a v1 patch of one
    # airport at one tree and corpus are two artifacts.  Keyed ONLY when
    # the engine is not v1, so every v1 key ever stored is unchanged — a
    # control that exists is never rebuilt (BUILD ECONOMY, CLAUDE.md).
    if engine and engine != "v1":
        variant["engine"] = engine
        variant["law_tables_sha256"] = law_tables_sha256
    return variant


# ══════════════════════════════════════════════════════════════════════
# THE STORE
# ══════════════════════════════════════════════════════════════════════

def _paths(store):
    store = store_dir(store)
    return store, store / "blobs", store / "entries", store / "evictions.jsonl"


class _StoreLock:
    """flock on the store, so two lanes storing at once cannot interleave a
    write with an eviction sweep."""

    def __init__(self, store):
        self.path = store_dir(store) / ".lock"

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(self.path, "a")
        fcntl.flock(self.fh, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        fcntl.flock(self.fh, fcntl.LOCK_UN)
        self.fh.close()
        return False


def load_entries(store=None) -> list:
    _s, _b, entries, _e = _paths(store)
    out = []
    if not entries.is_dir():
        return out
    for path in sorted(entries.glob("*.json")):
        try:
            out.append(json.loads(path.read_text()))
        except (OSError, ValueError):
            continue                     # a torn entry is a miss, never a crash
    return out


def store_build(key: str, key_parts: dict, artifacts: dict, meta: dict,
                store=None, code_state=None) -> dict:
    """Record one successful patch build.  ``artifacts`` is
    ``{role: path}``; every blob is content-addressed by its own sha256, so
    two keys that produced identical bytes cost one copy.

    ``code_state`` (``{"root", "code_tree_hash", "git_dirty"}``, the
    build-start snapshot) arms the STORE-TIME RE-CHECK: the tree hash and
    dirty flag are recomputed NOW and any mismatch — against the key's own
    tree or the snapshotted flag — raises :class:`ContaminatedKeyError`
    instead of storing.  Never re-keyed (see the class docstring)."""
    store_root, blobs, entries, _ev = _paths(store)
    missing = [r for r in REQUIRED_ROLES
               if not artifacts.get(r) or not Path(artifacts[r]).is_file()]
    if missing:
        raise ValueError(f"artifact ledger: refusing to store an incomplete "
                         f"build (missing {missing}) — a partial entry would "
                         f"serve a base arm that cannot be censused")
    if code_state is not None:
        try:
            now = code_state_now(code_state.get("root"))
        except Exception as exc:
            raise ContaminatedKeyError(
                f"CONTAMINATED-KEY: cannot re-verify the code tree at store "
                f"time ({exc!r}) — an entry whose key cannot be re-checked "
                f"is not stored") from exc
        moved = []
        if now["code_tree_hash"] != key_parts.get("tree"):
            moved.append(f"tree hash (keyed {str(key_parts.get('tree'))[:12]}"
                         f", now {str(now['code_tree_hash'])[:12]})")
        if now["git_dirty"] != code_state.get("git_dirty"):
            moved.append(f"dirty flag (snapshotted "
                         f"{code_state.get('git_dirty')}, now "
                         f"{now['git_dirty']})")
        if moved:
            raise ContaminatedKeyError(
                f"CONTAMINATED-KEY: the code tree MOVED between key time "
                f"and store time — {'; '.join(moved)}.  REFUSING to store "
                f"{key[:12]}: the entry would serve a post-edit artifact to "
                f"every later lane at the pre-edit hash (the 2026-08-28 "
                f"LEMD worker-pool-orphan precedent), and re-keying it to "
                f"the current tree would store an artifact that tree never "
                f"built.  The run's artifacts stay on disk; rebuild at a "
                f"stable tree to earn the ledger entry.")
    with _StoreLock(store_root):
        blobs.mkdir(parents=True, exist_ok=True)
        entries.mkdir(parents=True, exist_ok=True)
        files, total = {}, 0
        for role in ARTIFACT_ROLES:
            path = artifacts.get(role)
            if not path or not Path(path).is_file():
                continue
            sha = _sha256_file(path)
            blob = blobs / sha
            if not blob.exists():
                shutil.copyfile(path, blob)
            size = blob.stat().st_size
            files[role] = {"sha256": sha, "bytes": size,
                           "name": Path(path).name}
            total += size
        record = dict(meta)
        record.update({
            "key": key, "key_parts": key_parts, "files": files,
            "bytes": total,
            "stored_at": time.time(),
            "stored_at_iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "last_used": time.time(), "uses": 0,
        })
        (entries / f"{key}.json").write_text(json.dumps(record, indent=1,
                                                        default=str))
    evict(store=store_root)
    return record


def lookup(key: str, key_parts: dict, store=None):
    """``(record, why)``.  On a miss ``why`` NAMES the component that moved —
    a ledger that only says "miss" teaches nobody why they are rebuilding."""
    entries = load_entries(store)
    for rec in entries:
        if rec.get("key") == key:
            return rec, "hit"
    same_icao = [r for r in entries
                 if r.get("key_parts", {}).get("icao") == key_parts.get("icao")]
    if not same_icao:
        return None, (f"MISS: nothing stored for {key_parts.get('icao')} "
                      f"(the ledger has {len(entries)} entry/entries)")
    near = max(same_icao, key=lambda r: r.get("stored_at", 0))
    theirs = near.get("key_parts", {})
    diffs = []
    for name in ("tree", "env", "variant"):
        if theirs.get(name) != key_parts.get(name):
            diffs.append(name)
    ours_c = (key_parts.get("corpus") or {}).get("parts", {})
    their_c = (theirs.get("corpus") or {}).get("parts", {})
    moved = sorted(k for k in set(ours_c) | set(their_c)
                   if ours_c.get(k) != their_c.get(k))
    if moved:
        diffs.append("corpus[%s]" % ",".join(moved))
    return None, (f"MISS: {', '.join(diffs) or 'key material'} differ(s) from "
                  f"the newest stored {key_parts.get('icao')} arm "
                  f"({near.get('stored_at_iso')}, tag {near.get('tag')})"
                  + ("  — A CHANGED CORPUS IS A DIFFERENT MEASUREMENT, never "
                     "a hit (the KCLT road-feed precedent)"
                     if any(d.startswith("corpus") for d in diffs) else ""))


def serve(record: dict, out_dir, tag: str, store=None) -> dict:
    """Copy a stored arm into ``out_dir`` under ``tag``.  Byte-identity is
    VERIFIED on the way out: a corrupted store must fail loudly rather than
    hand back an artifact that no longer is what the record claims."""
    store_root, blobs, entries, _ev = _paths(store)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    names = {"patch": f"{tag}.osm", "sidecar": f"{tag}.osm.axes.json",
             "frame": f"{tag}.frame.json", "env": f"{tag}.env.json",
             "result": f"{tag}.result.json"}
    written = {}
    for role, info in record.get("files", {}).items():
        blob = blobs / info["sha256"]
        if not blob.is_file():
            raise SystemExit(
                f"REFUSING to serve from the artifact ledger: blob "
                f"{info['sha256'][:12]} for '{role}' is GONE from "
                f"{blobs} (evicted or corrupted).  Rebuild this arm.")
        if _sha256_file(blob) != info["sha256"]:
            raise SystemExit(
                f"REFUSING to serve from the artifact ledger: blob "
                f"{info['sha256'][:12]} does not hash to its own name — the "
                f"store is corrupt.  Rebuild this arm and delete {blob}.")
        dest = out_dir / names[role]
        shutil.copyfile(blob, dest)
        written[role] = str(dest)
    with _StoreLock(store_root):
        path = entries / f"{record['key']}.json"
        try:
            live = json.loads(path.read_text())
        except (OSError, ValueError):
            live = dict(record)
        live["last_used"] = time.time()
        live["uses"] = int(live.get("uses", 0)) + 1
        live.setdefault("served", []).append(
            {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "tag": tag,
             "out": str(out_dir)})
        live["served"] = live["served"][-20:]
        path.write_text(json.dumps(live, indent=1, default=str))
    return written


def provenance_line(record: dict, written: dict, store=None) -> str:
    """The loud line.  A served arm that read like a fresh build would be a
    measurement claim nobody could audit."""
    parts = record.get("key_parts", {})
    corpus = (parts.get("corpus") or {}).get("sha256", "?")
    return (
        "SERVED FROM THE ARTIFACT LEDGER — NO BUILD RAN.  "
        f"key={record.get('key', '?')[:12]} "
        f"[tree={str(parts.get('tree'))[:12]} icao={parts.get('icao')} "
        f"corpus={corpus[:12]} env={parts.get('env') or '{}'} "
        f"variant={parts.get('variant')}]; original build {record.get('tag')} "
        f"at {record.get('stored_at_iso')} took "
        f"{record.get('build_seconds')}s in lane {record.get('lane')}; "
        f"body_sha256={str(record.get('body_sha256'))[:16]}; served "
        f"{sorted(written)} from {store_dir(store)}.  Every number in it is "
        f"THAT build's, measured then, on the corpus stamped in its key.")


def evict(store=None) -> list:
    """Size-capped LRU, stamped.  An artifact that vanished silently is a
    rebuild nobody can explain, so every drop is recorded."""
    store_root, blobs, entries, ledger = _paths(store)
    cap = max_bytes()
    dropped = []
    with _StoreLock(store_root):
        recs = []
        for path in sorted(entries.glob("*.json")):
            try:
                recs.append((path, json.loads(path.read_text())))
            except (OSError, ValueError):
                continue
        total = sum(b.stat().st_size for b in blobs.glob("*")
                    if b.is_file()) if blobs.is_dir() else 0
        recs.sort(key=lambda pr: pr[1].get("last_used", 0))
        while total > cap and recs:
            path, rec = recs.pop(0)
            path.unlink(missing_ok=True)
            keep = set()
            for _p, other in recs:
                keep |= {f["sha256"] for f in other.get("files", {}).values()}
            freed = 0
            for info in rec.get("files", {}).values():
                if info["sha256"] in keep:
                    continue
                blob = blobs / info["sha256"]
                if blob.is_file():
                    freed += blob.stat().st_size
                    blob.unlink()
            total -= freed
            dropped.append({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                            "key": rec.get("key"), "tag": rec.get("tag"),
                            "icao": rec.get("key_parts", {}).get("icao"),
                            "freed_bytes": freed, "cap_bytes": cap,
                            "last_used": rec.get("last_used"),
                            "reason": "size-capped LRU"})
        if dropped:
            with open(ledger, "a") as fh:
                for rec in dropped:
                    fh.write(json.dumps(rec) + "\n")
    return dropped
