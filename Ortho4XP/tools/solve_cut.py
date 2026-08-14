"""THE SOLVE CUTTER — replay an airport's solve stage without rebuilding it.

    venv/bin/python tools/harness/build_airport.py ICAO --tag T \
        --solve-capture DIR                       # 1. capture (the harness)
    venv/bin/python tools/solve_cut.py --replay DIR/ICAO [--out PATCH.osm] \
        [--baseline SHA|--baseline-manifest FILE --baseline-key NAME] \
        [--allow-env-drift] [--json OUT]          # 2. replay + verdict
    venv/bin/python tools/solve_cut.py --show DIR/ICAO

Run it from ``Ortho4XP/``.  Spec: ``docs/specs/perf-p2-instruments-and-
cache-spec.md`` Lane B item 1; charter ``docs/specs/perf-phase-charter.md``.

WHY.  P1 measured a HECA airport build at ~560 s, of which phases [5]
(elevation solve) + [6] (feature emit) are ~420 s.  Every solver
iteration re-ran phases 1-4 to arrive at the same input.  This cuts the
STAGE out: capture the phases-1-4 product once, then replay 5+6 alone.

THE VERDICT IS A BODY HASH, not a pin table.  The whole airport is kept,
so a replay owes an EQUALITY — the emitted patch body must be identical
to the build's, byte for byte (the perf phase's frozen 1.0.245 baseline,
RULINGS 2026-08-13).  ``--baseline`` states which hash it must be; the
run prints REPRODUCED or DIVERGED and exits non-zero on DIVERGED.

    SIBLING, NOT A FORK: ``tools/repro_cut.py`` cuts a defect SITE out
    of a shipped patch and rebuilds it as a small synthetic airport —
    seconds, but auto_patch is not local, so its honest verdict is a
    DIRECTION (see its INDEX row's measured limit).  This one cuts a
    STAGE and keeps the airport whole — minutes, and the verdict is an
    equality.  They share what fits and nothing else: the body hash is
    ``harness/build_airport.body_sha256`` (the ``tail -n +3`` rule the
    frozen manifest is written in), the write law is
    ``harness/shared_repo_guard`` armed exactly as a build arms it, and
    the census (``--census``) is ``harness/census.py``'s own
    ``census_one``.  Nothing here enumerates a law family or re-derives
    a grade.

THE FRAME TRAVELS WITH THE CAPTURE.  ``O4_*`` flags change what the
solve does, so the capture records them and a replay under a different
set REFUSES (``--allow-env-drift``, recorded in the report).  The
capture also carries a state sha, so a fixture edited after it was cut
refuses rather than replaying something else.

WHAT A REPLAY IS NOT.  It is not a timing arm: a replay is a partial
build, so its wall is comparable only to other replays.  It never
records the build-time model (``auto_patch.solve_capture`` nulls
``_build_features`` for exactly that reason), and it must never be
wrapped in ``run_with_ledger`` when its output is a time.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # Ortho4XP/
HARNESS = ROOT / "tools" / "harness"

for _p in (ROOT / "src", ROOT, ROOT / "tests", ROOT / "tools", HARNESS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def _body_sha256(path: Path) -> str:
    """THE body hash — the harness's own, never a second spelling."""
    from build_airport import body_sha256           # noqa: E402
    return body_sha256(Path(path))


def _baseline_from_manifest(manifest: Path, key: str) -> str:
    """Pull ``body_sha256`` for ``key`` out of a frozen baseline MANIFEST."""
    for line in Path(manifest).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, _, rest = line.partition(":")
        if name.strip() != key:
            continue
        for field in rest.split():
            k, _, v = field.partition("=")
            if k == "body_sha256":
                return v
    raise SystemExit(
        f"REFUSING: {manifest} has no body_sha256 for '{key}'.  A replay "
        f"verdict against a baseline nobody wrote down is not a verdict.")


def show(src: Path) -> int:
    from auto_patch.solve_capture import read_manifest, env_drift
    m = read_manifest(src)
    print(f"  [solve-cut] capture {src}")
    print(f"      airport      {m.get('icao')}   boundary {m.get('boundary')}")
    print(f"      captured     {m.get('created')}  "
          f"v{m.get('capture_version')}  in {m.get('capture_seconds')}s")
    c = m.get("counts") or {}
    print(f"      shapes       {c.get('shapes')}   osm nodes "
          f"{c.get('osm_nodes')}   ways {c.get('osm_ways')}   "
          f"apron candidates {c.get('apron_candidates')}")
    print(f"      state        {m.get('state_bytes')} bytes  "
          f"sha {str(m.get('state_sha256'))[:12]}  "
          f"tile_dem={m.get('tile_dem')}")
    print(f"      anchor       {m.get('anchor')}  "
          f"tile {m.get('current_tile_lat')},{m.get('current_tile_lon')}")
    drift = env_drift(m)
    if drift:
        print(f"      ENV DRIFT    {len(drift)} key(s) differ from this "
              f"shell — a replay would refuse:")
        for k, (was, now) in drift.items():
            print(f"          {k}: captured={was!r} live={now!r}")
    else:
        print("      env          matches this shell")
    return 0


def restore_env(manifest: dict) -> dict:
    """Re-export the capture's ``O4_*`` frame into this process.

    A harness build sets its own redirects (``O4_DSF_CACHE_DIR``,
    ``O4_AIRPORT_MOD_CACHE_DIR``, ``O4_MASKS_DIR``, …), so a bare replay
    ALWAYS drifts against a captured build.  Restoring is what "replay in
    the captured frame" means — but a PATH-valued key whose directory is
    gone would send the replay at a cache that no longer exists and give
    it a silently different surface, so those are checked and refused.
    """
    was = dict(manifest.get("env") or {})
    missing = [f"{k}={v}" for k, v in was.items()
               if ("/" in str(v) or "\\" in str(v)) and not Path(v).exists()]
    if missing:
        raise SystemExit(
            "REFUSING --restore-env: the capture's frame names "
            f"{len(missing)} path(s) that no longer exist:\n    "
            + "\n    ".join(missing)
            + "\nThose are engine cache roots the solve READS; replaying "
              "against a vanished cache is a cold frame wearing the "
              "capture's label (warm-vs-cold has moved terrain 12 m).  "
              "Re-capture, or point them at the real roots yourself.")
    for k, v in was.items():
        os.environ[k] = v
    return was


def replay(src: Path, out: Path | None, *, baseline: str | None,
           allow_env_drift: bool, want_census: bool,
           restore: bool, json_out: Path | None) -> int:
    from auto_patch.solve_capture import (
        read_manifest, env_drift, load_capture, CAPTURE_ENV)
    from shared_repo_guard import SharedRepoWriteGuard   # noqa: E402
    import auto_patch.pipeline as pipeline              # noqa: E402

    manifest = read_manifest(src)
    icao = manifest.get("icao")
    restored = restore_env(manifest) if restore else {}
    if restored:
        print(f"  [solve-cut] restored the capture's O4_* frame "
              f"({len(restored)} key(s))")
    drift = env_drift(manifest)
    if drift and not allow_env_drift:
        lines = "\n".join(f"    {k}: captured={w!r} live={n!r}"
                          for k, (w, n) in drift.items())
        raise SystemExit(
            f"REFUSING to replay {src}: {len(drift)} O4_* flag(s) moved "
            f"since the capture.  The solve READS these, so a replay under "
            f"a different set is a different law and its body hash means "
            f"nothing:\n{lines}\n"
            f"Match the environment, or pass --allow-env-drift knowingly "
            f"(recorded in the report).")

    # A capture that armed itself again would recurse a capture per replay.
    os.environ.pop(CAPTURE_ENV, None)

    out = Path(out) if out else (Path(src) / "replay" / f"{icao}.osm")
    out.parent.mkdir(parents=True, exist_ok=True)

    # THE WRITE LAW, armed exactly as a build arms it: a replay runs the
    # real DEM prep (the captured tile_dem is None on the airport path),
    # so it can reach the shared corpus like any build can.
    guard = SharedRepoWriteGuard(requested=(), root=ROOT)
    print(f"  [solve-cut] replaying {icao} phases [5]+[6] from {src}")
    t_load = time.time()
    tail, _m = load_capture(src)
    load_s = time.time() - t_load
    t0 = time.time()
    with guard:
        layout = pipeline.solve_and_finalize(**tail)
    solve_s = time.time() - t0
    layout.to_osm(str(out))
    side = Path(str(out) + ".axes.json")
    body = _body_sha256(out)

    report = {
        "capture": str(src), "icao": icao, "patch": str(out),
        "sidecar_present": side.exists(),
        "shapes": len(layout.shapes),
        "body_sha256": body,
        "load_seconds": round(load_s, 2),
        "replay_seconds": round(solve_s, 1),
        "write_guard_blocked": list(guard.blocked),
        "env_drift": {k: list(v) for k, v in drift.items()},
        "env_drift_allowed": bool(drift) and allow_env_drift,
        "env_restored": sorted(restored),
        "baseline_body_sha256": baseline,
        "verdict": None,
    }
    if want_census:
        raise SystemExit(
            "REFUSING: --census is not implemented in v1.  Census the "
            "replayed patch with the harness entry itself: "
            f"venv/bin/python tools/harness/census.py {out}")
    if baseline:
        report["verdict"] = "REPRODUCED" if body == baseline else "DIVERGED"

    print(f"      loaded capture in {load_s:.1f}s   "
          f"replayed [5]+[6] in {solve_s:.1f}s")
    print(f"      shapes {len(layout.shapes)}  sidecar="
          f"{'OK' if side.exists() else 'MISSING'}  body_sha={body[:12]}")
    if guard.blocked:
        print(f"      !! write guard BLOCKED {len(guard.blocked)} write(s) — "
              f"this replay is degraded, not a clean measurement")
    if baseline:
        print(f"      baseline {baseline[:12]}  ->  {report['verdict']}")
    if json_out:
        Path(json_out).write_text(json.dumps(report, indent=2) + "\n")
    return 0 if report["verdict"] in (None, "REPRODUCED") else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--replay", type=Path, metavar="CAPTURE_DIR",
                    help="replay phases [5]+[6] from a capture directory")
    ap.add_argument("--show", type=Path, metavar="CAPTURE_DIR",
                    help="print a capture's manifest and env drift")
    ap.add_argument("--out", type=Path, default=None,
                    help="where to write the replayed patch "
                         "(default CAPTURE_DIR/replay/<ICAO>.osm)")
    ap.add_argument("--baseline", default=None, metavar="SHA",
                    help="the body sha256 this replay must reproduce")
    ap.add_argument("--baseline-manifest", type=Path, default=None,
                    help="a frozen baselines MANIFEST.txt to read --baseline "
                         "from (with --baseline-key)")
    ap.add_argument("--baseline-key", default=None, metavar="NAME",
                    help="the manifest row name, e.g. consol3heca")
    ap.add_argument("--restore-env", action="store_true",
                    help="re-export the capture's O4_* frame into this "
                         "process before replaying — what a captured "
                         "HARNESS build needs (its cache redirects are part "
                         "of the frame); refuses if a captured path is gone")
    ap.add_argument("--allow-env-drift", action="store_true",
                    help="replay KNOWINGLY under a different O4_* frame "
                         "(recorded in the report)")
    ap.add_argument("--census", action="store_true",
                    help="also census the replayed patch (harness census)")
    ap.add_argument("--json", type=Path, default=None,
                    help="write the replay report as JSON")
    args = ap.parse_args(argv)

    if args.show:
        return show(args.show)
    if not args.replay:
        ap.error("one of --replay or --show is required")
    # THE CWD LAW APPLIES TO A REPLAY TOO (S1d 2026-08-14).  The engine
    # resolves its read-only resources with ``O4_File_Names.resource_path``
    # = ``os.path.abspath(".")``, so a replay launched from the wrong
    # directory silently loses them: measured at OTHH, the DEM prep's
    # production-parity path failed with FileNotFoundError, the run fell
    # back to the STANDALONE DEM ("no cached airports OSM layer"), and the
    # replay emitted 2,027 shapes against the build's 2,186 — then reported
    # a DIVERGED body hash, which reads as an engine defect rather than as
    # the operator error it is.  ``build_airport.require_build_cwd`` is the
    # SAME law the build entry enforces and the SAME implementation (never
    # a second spelling); a replay is a build's phases [5]+[6] and owes it
    # identically.  ``--show`` is exempt: it only reads a manifest.
    from build_airport import require_build_cwd     # noqa: E402
    require_build_cwd(Path.cwd())
    baseline = args.baseline
    if args.baseline_manifest or args.baseline_key:
        if not (args.baseline_manifest and args.baseline_key):
            ap.error("--baseline-manifest and --baseline-key go together")
        if baseline:
            ap.error("pass --baseline OR --baseline-manifest, not both")
        baseline = _baseline_from_manifest(args.baseline_manifest,
                                           args.baseline_key)
    return replay(args.replay, args.out, baseline=baseline,
                  allow_env_drift=args.allow_env_drift,
                  want_census=args.census, restore=args.restore_env,
                  json_out=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
