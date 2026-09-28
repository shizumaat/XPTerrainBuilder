"""THE CLOUD TEST CORPUS — hash-stamped per-airport snapshots of the shared
data repo (owner RULINGS 2026-09-28a (7), amending e9daef5 for cloud lanes).

    venv/bin/python tools/harness/corpus_snapshot.py cut ICAO [ICAO ...] \\
        --out DIR [--traces TDIR] [--release RDIR] [--allowlist FILE]
    venv/bin/python tools/harness/corpus_snapshot.py verify DIR

Run from ``Ortho4XP/`` in a lane worktree mounted on the SHARED corpus.

WHAT A SNAPSHOT IS.  A cloud lane has no ``/Users/noah/XPTerrainBuilderData``
and no X-Plane install.  A snapshot is the exact subset of both that
``build_airport.py ICAO`` READS, copied into one tree::

    DIR/snapshot.json          manifest: sha256 + size of every file, the
                               cut date, the source corpus stamp, per-airport
                               file lists; its ``hash`` names the snapshot
    DIR/data/<Elevation_data|OSM_data|Airport_mod_cache|...>/...
    DIR/data/Ortho4XP.cfg.in   the owner's app cfg, install paths templated
    DIR/xplane/<Custom Scenery|Custom Data|Global Scenery|...>/...

and one tarball per airport (``RDIR/<ICAO>.tar.gz``, every file that airport
needs, plus ``snapshot.json``), which is what the private release carries.
``build_airport.py --corpus snapshot:DIR`` (or env ``O4_CORPUS_SNAPSHOT=DIR``)
mounts it (:func:`mount`) and stamps ``corpus = snapshot@<hash12>`` into
frame.json and the artifact-ledger key.  THE COMPARABILITY RULE: numbers are
comparable only within ONE snapshot hash — never across two snapshots, never
between a snapshot and the shared corpus (the ledger keys them apart).

THE LIST IS THE HARNESS'S OWN RESOLUTION, NOT A HAND LIST.  ``cut`` runs (or
reuses) ``build_airport.py ICAO --trace-reads FILE``: a :class:`ReadTrace`
audit hook records every file the in-process build OPENED for reading and
every directory it listed.  Reads under the shared repo, the lane's
copy-on-write cache overlays (mapped back to the corpus file they mirror) or
the X-Plane install are the snapshot.  GDAL opens rasters in C, where no
Python audit hook sees them, so the DEM part is unioned with the harness's
own DEM resolution (:func:`build_airport.dem_cache_state` — the base rasters,
the WHOLE airport-inset directory, the airports layer), which is the same
record the ledger's corpus stamp is cut from.  The proof of completeness is
the mounted build: every write into the snapshot refuses (the snapshot IS
``DATA_REPO`` then, under the same guard), a read of the real shared repo or
install is recorded as a SNAPSHOT LEAK, and the census must match.

LICENCE GATE.  A file inside a scenery pack (``Custom Scenery/<pack>/…``) or
a pack's derived cache (``Airport_mod_cache/<pack>/…``) is copied only when
the pack is on the allowlist (``corpus_snapshot_allowlist.json``, the owner's
freeware packs).  A payware or unknown-licence pack REFUSES the airport.
OTHH is excluded by name (RULINGS 28a (7): OTHH stays local).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE_ROOT = HERE.parent.parent
DEFAULT_ALLOWLIST = HERE / "corpus_snapshot_allowlist.json"
#: The shared repo's DEFAULT location, independent of ``O4_DATA_REPO`` —
#: the path a snapshot build must never read (a leak).
SHARED_DATA_REPO_DEFAULT = Path("/Users/noah/XPTerrainBuilderData")
#: The corpus dirs (``shared_repo_guard.SHARED_DATA_DIRS``, repeated here so
#: this module imports without the guard — :func:`mount` runs BEFORE the
#: guard is imported, because the guard reads ``O4_DATA_REPO`` at import).
DATA_DIRS = ("OSM_data", "Elevation_data", "Airport_mod_cache",
             "Geotiffs", "Masks", "Default_DSF_cache", "Orthophotos")
#: The install-path cfg keys, templated in the snapshot's cfg.
XPLANE_KEYS = ("cifp_data_path", "custom_scenery_dir", "custom_overlay_src")
XPLANE_TOKEN = "@XPLANE@"
#: Overlay env roots the harness redirects derived caches to; a read there
#: is a read of the corpus file it mirrors (``redirect_engine_caches``).
OVERLAY_ENVS = {"O4_AIRPORT_MOD_CACHE_DIR": "Airport_mod_cache",
                "O4_MASKS_DIR": "Masks",
                "O4_DSF_CACHE_DIR": "Default_DSF_cache"}
SNAPSHOT_ENV = "O4_CORPUS_SNAPSHOT"


def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha_of(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def manifest_hash(files: dict) -> str:
    """THE snapshot's name: the hash of its file manifest (path → sha256)."""
    return _sha_of({rel: rec["sha256"] for rel, rec in files.items()})


# ══════════════════════════════════════════════════════════════════════
# THE READ TRACE
# ══════════════════════════════════════════════════════════════════════

_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND


class ReadTrace:
    """Record every file opened for READING and every directory listed, via
    ``sys.addaudithook`` (in-process only; hooks cannot be removed, so the
    hook checks :attr:`active`).  Cheap: one set insert per open."""

    def __init__(self):
        self.reads: set = set()
        self.listed: set = set()
        self.active = False
        self._cwd = os.getcwd()

    def _hook(self, event, args):
        if not self.active:
            return
        try:
            if event == "open":
                path, mode, flags = (tuple(args) + (None, None, None))[:3]
                if not isinstance(path, (str, bytes, os.PathLike)):
                    return
                if isinstance(mode, str):
                    if any(c in mode for c in "wax+"):
                        return
                elif isinstance(flags, int) and flags & _WRITE_FLAGS:
                    return
                self.reads.add(os.fsdecode(path) if not isinstance(path, str)
                               else path)
            elif event in ("os.listdir", "os.scandir"):
                path = args[0] if args else "."
                if isinstance(path, (str, bytes, os.PathLike)):
                    self.listed.add(os.fsdecode(path))
        except Exception:
            pass

    def start(self) -> "ReadTrace":
        self._cwd = os.getcwd()
        sys.addaudithook(self._hook)
        self.active = True
        return self

    def stop(self) -> None:
        self.active = False

    def record(self) -> dict:
        def _real(p):
            p = p if os.path.isabs(p) else os.path.join(self._cwd, p)
            try:
                return os.path.realpath(p)
            except OSError:
                return p
        return {
            "reads": sorted({_real(p) for p in self.reads}),
            "listed": sorted({_real(p) for p in self.listed}),
            "overlays": {env: os.path.realpath(os.environ[env])
                         for env in OVERLAY_ENVS if os.environ.get(env)},
        }

    def save(self, path, extra=None) -> dict:
        rec = self.record()
        rec.update(extra or {})
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(rec, indent=1))
        return rec


class LeakWatch:
    """Snapshot mode's belt: every open of the REAL shared repo or the REAL
    X-Plane install while a snapshot is mounted is a LEAK — the snapshot
    was incomplete and the build quietly read the owner's machine."""

    def __init__(self, roots):
        self.roots = tuple(str(r).rstrip("/") + "/" for r in roots if r)
        self.leaks: set = set()
        self.active = False

    def _hook(self, event, args):
        if not self.active or event not in ("open", "os.listdir",
                                             "os.scandir"):
            return
        try:
            path = args[0] if args else None
            if not isinstance(path, (str, bytes, os.PathLike)):
                return
            p = os.path.abspath(os.fsdecode(path))
            if p.startswith(self.roots):
                self.leaks.add(p)
        except Exception:
            pass

    def start(self) -> "LeakWatch":
        if self.roots:
            sys.addaudithook(self._hook)
            self.active = True
        return self

    def stop(self) -> None:
        self.active = False

    def record(self) -> dict:
        leaks = sorted(self.leaks)
        return {"roots": list(self.roots), "count": len(leaks),
                "first": leaks[:25]}


# ══════════════════════════════════════════════════════════════════════
# CLASSIFICATION + LICENCE GATE
# ══════════════════════════════════════════════════════════════════════

def load_allowlist(path=None) -> dict:
    return json.loads(Path(path or DEFAULT_ALLOWLIST).read_text())


def pack_of(rel: str):
    """The scenery pack a snapshot path belongs to, or None."""
    parts = rel.split("/")
    if len(parts) >= 3 and parts[0] == "xplane" and parts[1] == "Custom Scenery":
        return parts[2] if len(parts) >= 4 else None     # a top-level file
    if len(parts) >= 4 and parts[0] == "data" and parts[1] == "Airport_mod_cache":
        return parts[2]
    return None


def licence_verdict(rel: str, allow: dict):
    """``None`` when ``rel`` may be copied, else the reason it may not."""
    pack = pack_of(rel)
    excluded = [x.lower() for x in allow.get("excluded_substrings", [])]
    low = rel.lower()
    if any(x in low for x in excluded):
        return f"excluded by name ({rel})"
    if pack is not None:
        if pack in allow.get("packs", {}):
            return None
        return f"pack {pack!r} is not on the freeware allowlist"
    if rel.startswith("xplane/"):
        sub = rel[len("xplane/"):]
        if sub.startswith("Custom Scenery/") and sub.count("/") == 1:
            return None                  # scenery_packs.ini and kin
        if any(sub.startswith(p) for p in allow.get("install_prefixes", [])):
            return None
        return f"install path {sub!r} is not under an allowlisted prefix"
    return None


def classify(path: str, data_repo: Path, install_root, overlays: dict):
    """Map one traced real path to ``(snapshot relpath, source path)`` or
    ``None`` when it is not corpus (engine source, venv, lane products)."""
    p = str(path)
    dr = str(data_repo.resolve()).rstrip("/") + "/"
    if p.startswith(dr):
        rel = p[len(dr):]
        if rel.split("/")[0] in DATA_DIRS:
            return f"data/{rel}", p
        return None
    for env, name in OVERLAY_ENVS.items():
        root = overlays.get(env)
        if root and p.startswith(root.rstrip("/") + "/"):
            rel = p[len(root.rstrip("/")) + 1:]
            src = data_repo / name / rel
            # a file the build DERIVED lane-local is not corpus
            return (f"data/{name}/{rel}", str(src)) if src.is_file() else None
    if install_root:
        ir = str(Path(install_root).resolve()).rstrip("/") + "/"
        if p.startswith(ir):
            return f"xplane/{p[len(ir):]}", p
    return None


# ══════════════════════════════════════════════════════════════════════
# CUT
# ══════════════════════════════════════════════════════════════════════

def _read_cfg(path) -> dict:
    out = {}
    for line in Path(path).read_text(errors="replace").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def install_root_of(cfg: dict) -> str:
    custom = cfg.get("custom_scenery_dir", "")
    return (os.path.dirname(custom.rstrip("/")) if custom
            else os.path.expanduser("~/X-Plane 12"))


def templated_cfg(cfg_path, install_root: str) -> str:
    """The owner cfg with every install path re-rooted on ``@XPLANE@``."""
    out = []
    ir = install_root.rstrip("/")
    for line in Path(cfg_path).read_text(errors="replace").splitlines():
        k = line.split("=", 1)[0].strip() if "=" in line else ""
        if k in XPLANE_KEYS:
            v = line.split("=", 1)[1].strip()
            if v.startswith(ir):
                v = XPLANE_TOKEN + v[len(ir):]
            line = f"{k}={v}"
        out.append(line)
    return "\n".join(out) + "\n"


def trace_build(icao: str, trace_path: Path, out_dir: Path) -> None:
    """The harness build that names the read set (``--trace-reads``)."""
    cmd = [sys.executable, str(HERE / "build_airport.py"), icao,
           "--trace-reads", str(trace_path), "--out", str(out_dir),
           "--no-artifact-ledger"]
    print(f"  [snapshot] tracing {icao}: {' '.join(cmd)}", flush=True)
    rc = subprocess.run(cmd, cwd=str(Path.cwd())).returncode
    if rc != 0 or not trace_path.is_file():
        raise SystemExit(f"REFUSING: the traced build of {icao} failed "
                         f"(rc {rc}); no read set, no snapshot")


def airport_read_set(icao: str, trace: dict, data_repo: Path,
                     install_root: str, root: Path) -> dict:
    """``{snapshot rel: source path}`` for one airport: the trace, unioned
    with the harness's own DEM resolution (GDAL reads are invisible to the
    audit hook)."""
    sys.path.insert(0, str(HERE))
    import build_airport as BA                      # noqa: E402
    out = {}
    for p in trace.get("reads", []):
        hit = classify(p, data_repo, install_root, trace.get("overlays", {}))
        if hit and os.path.isfile(hit[1]):
            out[hit[0]] = hit[1]
    tile = trace.get("tile") or BA.resolve_tile_for(icao, root)
    if tile:
        state = BA.dem_cache_state(root, *tile)
        rels = list(state.get("base_raster_files") or []) + \
            list(state.get("airports_layer_files") or [])
        for d in state.get("airport_inset_dirs") or []:
            for dp, _dn, fn in os.walk(root / d):
                for f in fn:
                    rels.append(os.path.relpath(os.path.join(dp, f), root))
        for rel in rels:
            src = os.path.realpath(root / rel)
            hit = classify(src, data_repo, install_root, {})
            if hit and os.path.isfile(src):
                out[hit[0]] = src
    return out


def cut(icaos, out: Path, traces: Path, release: Path, allowlist=None,
        root: Path = None) -> dict:
    root = Path(root or Path.cwd())
    sys.path.insert(0, str(HERE))
    from shared_repo_guard import DATA_REPO, REFRESH_LEDGER   # noqa: E402
    import build_airport as BA                                # noqa: E402
    data_repo = Path(DATA_REPO)
    allow = load_allowlist(allowlist)
    owner_cfg = data_repo / "Ortho4XP.cfg"
    install_root = install_root_of(_read_cfg(owner_cfg))
    out.mkdir(parents=True, exist_ok=True)
    traces.mkdir(parents=True, exist_ok=True)

    per_airport, refusals = {}, {}
    for icao in icaos:
        tpath = traces / f"{icao}.reads.json"
        if not tpath.is_file():
            trace_build(icao, tpath, traces / "builds")
        trace = json.loads(tpath.read_text())
        rs = airport_read_set(icao, trace, data_repo, install_root, root)
        bad = sorted({why for rel in rs
                      if (why := licence_verdict(rel, allow))})
        if bad:
            refusals[icao] = bad
            continue
        per_airport[icao] = {"tile": list(BA.resolve_tile_for(icao, root) or []),
                             "sources": rs,
                             "packs": sorted({pk for r in rs
                                              if (pk := pack_of(r))})}
    if refusals:
        lines = "\n".join(f"  {i}: {'; '.join(w[:6])}"
                          for i, w in refusals.items())
        raise SystemExit(f"REFUSING: licence gate (payware/unknown packs "
                         f"are never copied):\n{lines}\nAdd a pack to "
                         f"{DEFAULT_ALLOWLIST.name} only on the owner's word.")

    files = {}
    cfg_rel = "data/Ortho4XP.cfg.in"
    (out / "data").mkdir(parents=True, exist_ok=True)
    (out / cfg_rel).write_text(templated_cfg(owner_cfg, install_root))
    files[cfg_rel] = {"sha256": _sha256(out / cfg_rel),
                      "size": (out / cfg_rel).stat().st_size}
    for icao, rec in per_airport.items():
        for rel, src in sorted(rec["sources"].items()):
            dst = out / rel
            if rel not in files:
                dst.parent.mkdir(parents=True, exist_ok=True)
                if not dst.is_file() or dst.stat().st_size != os.path.getsize(src):
                    shutil.copy2(src, dst)
                files[rel] = {"sha256": _sha256(dst), "size": dst.stat().st_size}
        rec["files"] = sorted(set(rec["sources"]) | {cfg_rel})
        rec["bytes"] = sum(files[r]["size"] for r in rec["files"])
        del rec["sources"]

    ledger_sha = _sha256(REFRESH_LEDGER) if Path(REFRESH_LEDGER).is_file() else None
    manifest = {
        "schema": 1,
        "cut_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_corpus": {
            "data_repo": str(data_repo), "install_root": install_root,
            "refresh_ledger_sha256": ledger_sha,
            "source_stamp": _sha_of({"ledger": ledger_sha,
                                     "files": {r: f["sha256"]
                                               for r, f in files.items()}}),
        },
        "airports": per_airport,
        "files": files,
    }
    manifest["hash"] = manifest_hash(files)
    (out / "snapshot.json").write_text(json.dumps(manifest, indent=1))

    release.mkdir(parents=True, exist_ok=True)
    (release / "snapshot.json").write_text(json.dumps(manifest, indent=1))
    for icao, rec in per_airport.items():
        tar = release / f"{icao}.tar.gz"
        with tarfile.open(tar, "w:gz") as tf:
            tf.add(out / "snapshot.json", arcname="snapshot.json")
            for rel in rec["files"]:
                tf.add(out / rel, arcname=rel)
        rec["tarball_bytes"] = tar.stat().st_size
    (out / "snapshot.json").write_text(json.dumps(manifest, indent=1))
    (release / "snapshot.json").write_text(json.dumps(manifest, indent=1))
    return manifest


# ══════════════════════════════════════════════════════════════════════
# VERIFY + MOUNT
# ══════════════════════════════════════════════════════════════════════

def verify(snap: Path, *, quiet=False) -> dict:
    """Re-hash every file the manifest names that is PRESENT; an airport is
    COMPLETE when all its files are present and match.  A mismatch, or a
    manifest whose hash does not re-derive, refuses."""
    snap = Path(snap)
    man = json.loads((snap / "snapshot.json").read_text())
    if manifest_hash(man["files"]) != man["hash"]:
        raise SystemExit(f"REFUSING: {snap}/snapshot.json does not re-derive "
                         f"its own hash — the manifest was edited")
    bad, present = [], set()
    for rel, rec in man["files"].items():
        p = snap / rel
        if not p.is_file():
            continue
        if p.stat().st_size != rec["size"] or _sha256(p) != rec["sha256"]:
            bad.append(rel)
        else:
            present.add(rel)
    if bad:
        raise SystemExit(f"REFUSING: {len(bad)} snapshot file(s) do not match "
                         f"snapshot.json (first: {bad[:5]}) — a mutated "
                         f"snapshot is not snapshot@{man['hash'][:12]}")
    complete = sorted(i for i, rec in man["airports"].items()
                      if set(rec["files"]) <= present)
    if not quiet:
        print(f"snapshot@{man['hash'][:12]}: {len(present)}/{len(man['files'])} "
              f"files present and verified; complete airports: {complete}")
    return {"hash": man["hash"], "complete": complete,
            "present": len(present), "files": len(man["files"])}


def snapshot_request(argv, environ=None):
    """The snapshot dir a build asked for (``--corpus snapshot:DIR`` wins
    over ``O4_CORPUS_SNAPSHOT``), or ``None`` for the shared corpus.  Read
    from argv BEFORE argparse because the guard module reads
    ``O4_DATA_REPO`` at import time."""
    environ = os.environ if environ is None else environ
    val = None
    argv = list(argv)
    for i, a in enumerate(argv):
        if a == "--corpus" and i + 1 < len(argv):
            val = argv[i + 1]
        elif a.startswith("--corpus="):
            val = a.split("=", 1)[1]
    if val is None:
        val = environ.get(SNAPSHOT_ENV) or None
        if val and not val.startswith("snapshot:"):
            val = "snapshot:" + val
    if val in (None, "", "shared"):
        return None
    if not val.startswith("snapshot:"):
        raise SystemExit(f"REFUSING: --corpus {val!r}: expected 'shared' or "
                         f"'snapshot:DIR'")
    return Path(val[len("snapshot:"):]).expanduser().resolve()


def arm_snapshot_env(argv, environ=None):
    """Point ``O4_DATA_REPO`` at the snapshot's data root (before the guard
    import).  Returns the snapshot dir or None."""
    environ = os.environ if environ is None else environ
    snap = snapshot_request(argv, environ)
    if snap is not None:
        environ["O4_DATA_REPO"] = str(snap / "data")
    return snap


def mount(root: Path, snap: Path, icao=None, prog=None) -> dict:
    """Mount a verified snapshot as the lane's data root: each corpus dir of
    ``root`` becomes a symlink into ``snap/data`` (a REAL directory there
    refuses — it is someone's private corpus), and the cfg is rendered with
    the install paths on ``snap/xplane``.  Returns the frame record."""
    root, snap = Path(root), Path(snap)
    v = verify(snap, quiet=True)
    if icao and icao.upper() not in v["complete"]:
        raise SystemExit(f"REFUSING: snapshot@{v['hash'][:12]} at {snap} does "
                         f"not carry a complete read set for {icao} "
                         f"(complete: {v['complete']}) — fetch its tarball")
    data = snap / "data"
    previous = {}
    for name in DATA_DIRS:
        target = data / name
        target.mkdir(parents=True, exist_ok=True)
        link = root / name
        if link.is_symlink():
            previous[name] = os.readlink(link)
            if Path(os.readlink(link)) != target:
                link.unlink()
                link.symlink_to(target)
        elif link.exists():
            raise SystemExit(f"REFUSING: {link} is a real directory — a "
                             f"private corpus cannot be re-mounted onto a "
                             f"snapshot; move it aside first")
        else:
            link.symlink_to(target)
    rendered = (data / "Ortho4XP.cfg.in").read_text().replace(
        XPLANE_TOKEN, str(snap / "xplane"))
    (data / "Ortho4XP.cfg").write_text(rendered)
    lane_cfg = root / "Ortho4XP.cfg"
    backup = root / "Ortho4XP.cfg.shared-corpus"
    if lane_cfg.is_file() and not backup.exists() and \
            lane_cfg.read_text(errors="replace") != rendered:
        shutil.copy2(lane_cfg, backup)
    lane_cfg.write_text(rendered)
    rec = {"corpus": f"snapshot@{v['hash'][:12]}", "hash": v["hash"],
           "dir": str(snap), "complete_airports": v["complete"],
           "files_present": v["present"], "previous_mounts": previous,
           "lane_cfg_backup": str(backup) if backup.exists() else None}
    if prog is not None:
        prog.note(f"CORPUS {rec['corpus']} mounted from {snap} "
                  f"({v['present']} files verified; airports {v['complete']})")
    return rec


def unmount(root: Path, record: dict) -> None:
    """Undo :func:`mount` on a local lane (re-point the previous symlinks,
    restore the cfg backup)."""
    root = Path(root)
    for name, target in (record.get("previous_mounts") or {}).items():
        link = root / name
        if link.is_symlink():
            link.unlink()
        link.symlink_to(target)
    backup = record.get("lane_cfg_backup")
    if backup and Path(backup).is_file():
        shutil.move(backup, root / "Ortho4XP.cfg")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("cut", help="cut a snapshot of the airports' read set")
    c.add_argument("icaos", nargs="+")
    c.add_argument("--out", required=True, type=Path)
    c.add_argument("--traces", type=Path, default=None,
                   help="read-trace dir (default OUT.traces); a missing "
                        "<ICAO>.reads.json is produced by a traced harness build")
    c.add_argument("--release", type=Path, default=None,
                   help="tarball dir (default OUT.release)")
    c.add_argument("--allowlist", type=Path, default=None)
    v = sub.add_parser("verify", help="re-hash a snapshot against its manifest")
    v.add_argument("dir", type=Path)
    u = sub.add_parser("unmount", help="restore a lane mounted by --corpus "
                                       "snapshot (reads FRAME.json's record)")
    u.add_argument("frame", type=Path)
    args = ap.parse_args(argv)
    if args.cmd == "cut":
        out = args.out.resolve()
        man = cut([i.upper() for i in args.icaos], out,
                  (args.traces or Path(str(out) + ".traces")).resolve(),
                  (args.release or Path(str(out) + ".release")).resolve(),
                  args.allowlist)
        total = 0
        for icao, rec in man["airports"].items():
            total += rec["bytes"]
            print(f"  {icao}: {len(rec['files'])} files, "
                  f"{rec['bytes'] / 1e6:.1f} MB (tarball "
                  f"{rec.get('tarball_bytes', 0) / 1e6:.1f} MB), packs {rec['packs']}")
        print(f"snapshot@{man['hash'][:12]} ({man['hash']}): "
              f"{len(man['files'])} files, "
              f"{sum(f['size'] for f in man['files'].values()) / 1e6:.1f} MB")
        return 0
    if args.cmd == "verify":
        verify(args.dir)
        return 0
    if args.cmd == "unmount":
        frame = json.loads(args.frame.read_text())
        unmount(Path.cwd(), frame.get("corpus_snapshot") or {})
        print("restored the lane's shared-corpus mounts")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
