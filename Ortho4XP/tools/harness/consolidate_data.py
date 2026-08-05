"""THE CORPUS CONSOLIDATION — union the fleet's private caches INTO the
shared data repo, once, before anything mounts it.

    venv/bin/python tools/harness/consolidate_data.py diff [--trees T,...]
    venv/bin/python tools/harness/consolidate_data.py merge [--apply]
    venv/bin/python tools/harness/consolidate_data.py migrate TREE [--apply]

ONE-OFF (owner ruling e9daef5's migration step).  It exists because the
fleet's corpora are DIFFERENT SETS, not stale copies of one another: the
main tree carries 161 Airport_mod_cache files and 450 Default_DSF_cache
files the shared repo has never seen, while the shared repo carries 673
Elevation_data files the main tree has never seen.  Mounting the shared
repo without this union would silently lose the main tree's half — and the
main tree is where most campaign builds ran.

It borrows every primitive from ``build_airport.py`` (the data repo, the
per-scope lock, the hash stamp, the refresh ledger) rather than growing a
second set: a consolidation that wrote to the shared repo through its own
private helpers would be the exact defect the harness exists to end.

SAFETY, in order of importance:

* **Nothing is ever deleted.**  A superseded file is MOVED to
  ``<repo>/.harness/archive/<stamp>/``, never removed.  The operation is
  reversible from the archive alone.
* **Dry run is the default.**  ``merge`` and ``migrate`` print exactly what
  they would do and change nothing until ``--apply``.
* **Every write is ledgered** into the shared repo's refresh ledger,
  sha256-stamped, one record per artifact class.
* **The whole merge holds every refresh lock** for the scopes it touches,
  so a lane cannot race a regeneration into a directory being unioned.
* **A tree with a live process is refused** for ``migrate``: moving a data
  directory out from under a running build breaks it.

CONFLICT POLICY (a file present on BOTH sides with different content):

* ``.hgt`` and other DEM RASTERS must be byte-identical — they are the same
  public source data.  A difference is a FINDING, not a merge decision:
  the shared copy is kept, the private copy is archived under
  ``conflict/``, and the pair is reported by name.  Nothing is resolved
  silently, because "two different elevation rasters for one tile" would
  explain a class of terrain discrepancy on its own.
* CACHE-STATE files (``complete.json``, ``*_road_feed.cache``, sidecar
  caches, indexes) are derived and self-describing: the NEWER wins, the
  older is archived, and the resolution is ledgered.
* Anything else keeps the SHARED copy and archives the private one.  A
  conservative default is right here: the archive makes any resolution
  reversible, and an unexpected class deserves a human read, not a guess.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_airport as HB                                # noqa: E402

DATA_REPO = HB.DATA_REPO
ARCHIVE_ROOT = HB.HARNESS_STATE / "archive"

#: Trees whose private caches are candidates for the union.  The LIVE lanes
#: are deliberately absent — they finish their A/Bs on their current
#: corpora and migrate at close.
DEFAULT_TREES = ("/Users/noah/XPTerrainBuilder/Ortho4XP",)

#: Derived, self-describing cache state: newest wins.
CACHE_STATE_SUFFIXES = (".json", ".cache", ".pkl", ".sidecar", ".index")
CACHE_STATE_NAMES = ("complete.json", "index.json", "provenance.json")
#: Public source rasters: must be byte-identical; a difference is a finding.
RASTER_SUFFIXES = (".hgt", ".tif", ".tiff", ".dem", ".img", ".zip")


def _index(root: Path, sub: str) -> dict:
    """``{relpath: (size, mtime_ns)}`` for one data dir of one tree.  A
    SYMLINKED dir indexes as empty: it is a mount, not a private corpus."""
    top = Path(root) / sub
    if top.is_symlink() or not top.is_dir():
        return {}
    out = {}
    for dirpath, _dirnames, filenames in os.walk(top):
        for fn in filenames:
            p = Path(dirpath) / fn
            try:
                st = p.stat()
            except OSError:
                continue
            out[str(p.relative_to(top))] = (st.st_size, st.st_mtime_ns)
    return out


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(4 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _kind(rel: str) -> str:
    name = Path(rel).name.lower()
    if name in CACHE_STATE_NAMES:
        return "cache_state"
    suffix = Path(rel).suffix.lower()
    if suffix in RASTER_SUFFIXES:
        return "raster"
    if suffix in CACHE_STATE_SUFFIXES:
        return "cache_state"
    return "other"


def diff_tree(tree: Path, dirs=HB.SHARED_DATA_DIRS, hash_overlap=True) -> dict:
    """Classify every file of one tree's private dirs against the shared
    repo.  Read-only; touches nothing."""
    report = {"tree": str(tree), "dirs": {}}
    for d in dirs:
        priv = _index(tree, d)
        shared = _index(DATA_REPO, d)
        only_priv = sorted(set(priv) - set(shared))
        only_shared = sorted(set(shared) - set(priv))
        both = sorted(set(priv) & set(shared))
        identical, conflicts = [], []
        for rel in both:
            if priv[rel][0] != shared[rel][0]:
                # Different SIZE is a conflict outright — no need to hash.
                conflicts.append({"path": rel, "kind": _kind(rel),
                                  "private": {"size": priv[rel][0],
                                              "mtime_ns": priv[rel][1]},
                                  "shared": {"size": shared[rel][0],
                                             "mtime_ns": shared[rel][1]},
                                  "reason": "size differs"})
                continue
            if not hash_overlap:
                identical.append(rel)
                continue
            ph = _sha256(Path(tree) / d / rel)
            sh = _sha256(DATA_REPO / d / rel)
            if ph == sh:
                identical.append(rel)
            else:
                conflicts.append({"path": rel, "kind": _kind(rel),
                                  "private": {"size": priv[rel][0],
                                              "mtime_ns": priv[rel][1],
                                              "sha256": ph},
                                  "shared": {"size": shared[rel][0],
                                             "mtime_ns": shared[rel][1],
                                             "sha256": sh},
                                  "reason": "same size, different content"})
        report["dirs"][d] = {
            "private_files": len(priv), "shared_files": len(shared),
            "merge": only_priv, "shared_only": len(only_shared),
            "identical": len(identical), "conflicts": conflicts,
            "merge_bytes": sum(priv[r][0] for r in only_priv),
        }
    return report


def resolve(conflict: dict) -> dict:
    """The decision for one BOTH-DIFFERENT file.  Never silent: every
    resolution carries the rule that produced it."""
    kind = conflict["kind"]
    if kind == "raster":
        return {**conflict, "resolution": "KEEP_SHARED_REPORT_FINDING",
                "rule": "DEM/source rasters are public source data and must "
                        "be byte-identical; a difference is a FINDING, not a "
                        "merge decision.  Shared copy kept, private copy "
                        "archived under conflict/ for inspection."}
    if kind == "cache_state":
        p_new = conflict["private"]["mtime_ns"] > conflict["shared"]["mtime_ns"]
        return {**conflict,
                "resolution": "TAKE_PRIVATE" if p_new else "KEEP_SHARED",
                "rule": "derived cache state: the NEWER wins, the older is "
                        "archived"}
    return {**conflict, "resolution": "KEEP_SHARED",
            "rule": "unrecognised class: the shared copy is kept and the "
                    "private one archived, so the decision is reversible and "
                    "a human can read it"}


def print_diff(report: dict) -> None:
    print(f"\n=== CORPUS DIFF: {report['tree']}  vs  {DATA_REPO} ===")
    print(f"  {'dir':<20}{'private':>9}{'shared':>9}{'MERGE':>8}"
          f"{'shr-only':>10}{'identical':>11}{'CONFLICT':>10}{'merge GB':>10}")
    print("  " + "-" * 87)
    tm = tc = 0
    tb = 0
    for d, r in report["dirs"].items():
        tm += len(r["merge"])
        tc += len(r["conflicts"])
        tb += r["merge_bytes"]
        print(f"  {d:<20}{r['private_files']:>9}{r['shared_files']:>9}"
              f"{len(r['merge']):>8}{r['shared_only']:>10}"
              f"{r['identical']:>11}{len(r['conflicts']):>10}"
              f"{r['merge_bytes'] / 1e9:>10.2f}")
    print("  " + "-" * 87)
    print(f"  {'TOTAL':<20}{'':>9}{'':>9}{tm:>8}{'':>10}{'':>11}{tc:>10}"
          f"{tb / 1e9:>10.2f}")
    for d, r in report["dirs"].items():
        if not r["conflicts"]:
            continue
        print(f"\n  --- BOTH-DIFFERENT in {d} ({len(r['conflicts'])}) ---")
        for c in r["conflicts"]:
            res = resolve(c)
            pm = time.strftime("%Y-%m-%d %H:%M",
                               time.localtime(c["private"]["mtime_ns"] / 1e9))
            sm = time.strftime("%Y-%m-%d %H:%M",
                               time.localtime(c["shared"]["mtime_ns"] / 1e9))
            print(f"    {c['path']}")
            print(f"      kind={c['kind']}  ({c['reason']})")
            print(f"      private  {c['private']['size']:>12,} B  {pm}"
                  + (f"  {c['private'].get('sha256', '')[:12]}"
                     if c["private"].get("sha256") else ""))
            print(f"      shared   {c['shared']['size']:>12,} B  {sm}"
                  + (f"  {c['shared'].get('sha256', '')[:12]}"
                     if c["shared"].get("sha256") else ""))
            print(f"      => {res['resolution']}")


def _archive_dir(stamp: str, sub: str = "") -> Path:
    p = ARCHIVE_ROOT / stamp / sub if sub else ARCHIVE_ROOT / stamp
    p.mkdir(parents=True, exist_ok=True)
    return p


def do_merge(report: dict, apply: bool, stamp: str,
             break_stale: bool = False) -> dict:
    """Union one tree's private-only files into the shared repo and resolve
    its conflicts.  Dry-run unless ``apply``."""
    tree = Path(report["tree"])
    scopes = sorted({HB.scope_of(d) or d for d in report["dirs"]
                     if report["dirs"][d]["merge"]
                     or report["dirs"][d]["conflicts"]})
    scopes = [s for s in scopes if s in {sc for sc, _p, _w in HB.REFRESH_SCOPES}]
    locks = []
    actions = {"merged": [], "resolved": [], "archived": [], "skipped": []}
    try:
        if apply and scopes:
            locks = [HB.RefreshLock(s, lane=f"consolidate:{tree}",
                                    break_stale=break_stale).acquire()
                     for s in scopes]
            print(f"  [consolidate] holding refresh lock(s): {scopes}")
        for d, r in report["dirs"].items():
            for rel in r["merge"]:
                src = tree / d / rel
                dst = DATA_REPO / d / rel
                if not src.exists():
                    actions["skipped"].append(f"{d}/{rel} (vanished)")
                    continue
                if dst.exists():
                    # A concurrent lane landed it between diff and merge.
                    actions["skipped"].append(f"{d}/{rel} (appeared in "
                                              f"shared since the diff)")
                    continue
                if apply:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    if _sha256(src) != _sha256(dst):
                        raise SystemExit(
                            f"ABORT: copy verification FAILED for {d}/{rel} "
                            f"— the shared repo may hold a partial file. "
                            f"Inspect {dst} before doing anything else.")
                actions["merged"].append(f"{d}/{rel}")
            for c in r["conflicts"]:
                res = resolve(c)
                rel = c["path"]
                src = tree / d / rel
                dst = DATA_REPO / d / rel
                sub = ("conflict" if res["resolution"].startswith("KEEP_SHARED")
                       else "superseded")
                arc = _archive_dir(stamp, f"{sub}/{d}") / rel.replace("/", "__")
                if apply:
                    arc.parent.mkdir(parents=True, exist_ok=True)
                if res["resolution"] == "TAKE_PRIVATE":
                    if apply:
                        shutil.copy2(dst, arc)          # archive the OLD shared
                        shutil.copy2(src, dst)
                        if _sha256(src) != _sha256(dst):
                            raise SystemExit(
                                f"ABORT: copy verification FAILED replacing "
                                f"{d}/{rel}; the archived original is at {arc}")
                    actions["resolved"].append(
                        # ``path`` LAST: ``res`` carries the conflict's own
                        # bare ``path`` key, and spreading it after would
                        # overwrite the dir-qualified one — which silently
                        # emptied the ledger's modified/conflicts lists on
                        # the first consolidation run.
                        {**res, "path": f"{d}/{rel}", "archived": str(arc)})
                else:
                    if apply:
                        shutil.copy2(src, arc)          # archive the PRIVATE
                    actions["resolved"].append(
                        {**res, "path": f"{d}/{rel}", "archived": str(arc)})
                actions["archived"].append(str(arc))
        if apply:
            for d, r in report["dirs"].items():
                merged = [x for x in actions["merged"] if x.startswith(d + "/")]
                res = [x for x in actions["resolved"]
                       if x["path"].startswith(d + "/")]
                if not merged and not res:
                    continue
                scope = HB.scope_of(d) or d
                rec = HB.record_refresh(
                    scope,
                    {"added": [m for m in merged],
                     "modified": [x["path"] for x in res
                                  if x["resolution"] == "TAKE_PRIVATE"],
                     "removed": []},
                    {"lane": f"consolidate:{tree}",
                     "operation": "corpus-consolidation",
                     "ruling": "e9daef5",
                     "archive": str(ARCHIVE_ROOT / stamp),
                     "conflicts": res})
                print(f"  [consolidate] LEDGERED [{scope}] +{rec['added']} "
                      f"~{rec['modified']}")
    finally:
        for lk in locks:
            lk.release()
    return actions


def tree_is_busy(tree: Path) -> list:
    try:
        out = subprocess.run(["pgrep", "-fl", str(tree)], capture_output=True,
                             text=True, timeout=10).stdout.strip()
    except Exception:
        return []
    return [ln for ln in out.splitlines()
            if "consolidate_data.py" not in ln and "pgrep" not in ln]


def dependents_of(tree: Path) -> list:
    """Trees whose data dirs SYMLINK into ``tree``.

    They inherit ``tree``'s corpus, so migrating ``tree`` migrates them too —
    silently, mid-A/B.  The migration must not proceed while any of them is
    a live lane that was told to finish on its current corpus.
    """
    out = []
    wt_root = Path("/Users/noah/XPTerrainBuilder/.claude/worktrees")
    for cand in sorted(wt_root.glob("*/Ortho4XP")):
        for d in HB.SHARED_DATA_DIRS:
            p = cand / d
            if p.is_symlink() and str(Path(os.readlink(p))).startswith(
                    str(tree)):
                out.append({"tree": str(cand), "dir": d,
                            "target": os.readlink(p)})
    return out


def do_migrate(tree: Path, apply: bool, stamp: str) -> dict:
    """Point one tree's data dirs at the shared repo, archiving the private
    directories rather than deleting them."""
    busy = tree_is_busy(tree)
    deps = dependents_of(tree)
    busy_deps = [d for d in deps if tree_is_busy(Path(d["tree"]))]
    plan = {"tree": str(tree), "busy": busy, "dependents": deps,
            "busy_dependents": busy_deps, "moves": []}
    for d in HB.SHARED_DATA_DIRS:
        p = tree / d
        if p.is_symlink() or not p.is_dir():
            continue
        plan["moves"].append({"from": str(p),
                              "archive": str(ARCHIVE_ROOT / stamp / d),
                              "to_symlink": str(DATA_REPO / d)})
    if not apply:
        return plan
    if busy:
        raise SystemExit(
            f"REFUSING to migrate {tree}: {len(busy)} live process(es) hold "
            f"it.  Moving a data directory out from under a running build "
            f"breaks it mid-write:\n  "
            + "\n  ".join(b[:160] for b in busy))
    if busy_deps:
        raise SystemExit(
            f"REFUSING to migrate {tree}: {len(busy_deps)} LIVE lane(s) "
            f"symlink their data INTO it and would silently change corpus "
            f"mid-A/B:\n  "
            + "\n  ".join(f"{d['tree']} ({d['dir']})" for d in busy_deps)
            + "\nThose lanes were told to finish on their current corpora. "
              "Migrate after they close.")
    for mv in plan["moves"]:
        src, arc = Path(mv["from"]), Path(mv["archive"])
        arc.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(arc))
        src.symlink_to(Path(mv["to_symlink"]))
        print(f"  [consolidate] {src.name}: archived -> {arc}, now mounts "
              f"{mv['to_symlink']}")
    return plan


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("diff", help="read-only classification")

    for p in (d,):
        p.add_argument("--trees", default=",".join(DEFAULT_TREES))
        p.add_argument("--json", type=Path, default=None)
        p.add_argument("--no-hash", action="store_true",
                       help="skip content hashing of same-size overlaps "
                            "(faster, and then 'identical' is an assumption)")
    m = sub.add_parser("merge", help="union private-only files into shared")
    m.add_argument("--trees", default=",".join(DEFAULT_TREES))
    m.add_argument("--apply", action="store_true")
    m.add_argument("--json", type=Path, default=None)
    m.add_argument("--break-stale-lock", action="store_true")
    g = sub.add_parser("migrate", help="point a tree's data dirs at shared")
    g.add_argument("tree")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    if args.cmd in ("diff", "merge"):
        reports = []
        for t in args.trees.split(","):
            rep = diff_tree(Path(t.strip()),
                            hash_overlap=not getattr(args, "no_hash", False))
            print_diff(rep)
            reports.append(rep)
        if args.cmd == "merge":
            for rep in reports:
                acts = do_merge(rep, args.apply, stamp,
                                getattr(args, "break_stale_lock", False))
                verb = "MERGED" if args.apply else "would merge"
                print(f"\n  [consolidate] {verb} {len(acts['merged'])} "
                      f"file(s); resolved {len(acts['resolved'])} conflict(s); "
                      f"skipped {len(acts['skipped'])}")
                if not args.apply:
                    print("  [consolidate] DRY RUN — nothing was written. "
                          "Re-run with --apply.")
                rep["actions"] = acts
        if getattr(args, "json", None):
            args.json.write_text(json.dumps(reports, indent=1, default=str))
            print(f"\n  [consolidate] JSON -> {args.json}")
        return 0

    plan = do_migrate(Path(args.tree), args.apply, stamp)
    print(json.dumps(plan, indent=1)[:4000])
    if not args.apply:
        print("  [consolidate] DRY RUN — nothing was moved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
