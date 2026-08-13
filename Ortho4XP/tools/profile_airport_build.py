"""Wall-clock sampling profiler for a single-airport auto_patch build.

Runs ``build_airport_pavement(ICAO)`` exactly like
``tools/full_airport_build.py`` while a background thread samples the
main thread's stack every ``--interval`` seconds (default 0.02 s).
Because it samples wall time rather than counting calls, it has none of
cProfile's per-call ``tottime`` inflation on hot small functions and
adds <1% overhead, so the attribution matches the production
``~/.ortho4xp/auto_patch_build_times`` phase numbers.

Reports written to ``--out`` (default /tmp/<ICAO>_profile.txt):
  1. Build phase (pipeline step 1-6) per sample, so phase totals can be
     cross-checked against the build-times JSON.
  2. Top call sites inside pipeline.py per phase — "which task is the
     main thread actually inside", attributed to the innermost
     pipeline.py frame.
  3. Top functions by inclusive (anywhere on stack) and leaf
     (top-of-stack) sample counts, project files only.

Usage:
    venv/bin/python tools/profile_airport_build.py ICAO [--interval 0.02]
        [--out /tmp/ICAO_profile.txt]
    venv/bin/python tools/profile_airport_build.py --replay CAPTURE_DIR
        [--count auto_patch.grade_graph:shape_constraints ...]

``--replay`` profiles a SOLVE-STAGE CAPTURE (``tools/solve_cut.py``)
instead of a whole build: the same sampler over the same reports, but
the target is ``pipeline.solve_and_finalize`` replayed from the capture,
so phases [5]+[6] are profiled in seconds-per-iteration rather than
minutes.  The capture's ``O4_*`` frame is restored and the replay's body
hash is printed — a profile of a run that did not reproduce the baseline
is not a profile of production.  Everything else (phase bucketing,
inclusive / leaf tables) is unchanged, so replay profiles and build
profiles are read the same way.

``--count MODULE:ATTR`` (repeatable) additionally wraps a named callable
with a call counter and an inclusive timer, for questions a sampler
cannot answer ("is this memo missing, or is the miss expensive?").  The
wrapper is installed for the profiled run only.
"""

import argparse
import collections
import os
import sys
import threading
import time

os.environ.setdefault("O4_LOG_VERBOSITY", "1")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for path in (os.path.join(ROOT, "src"), ROOT, os.path.join(ROOT, "tests"),
             os.path.join(ROOT, "tools")):
    if path not in sys.path:
        sys.path.insert(0, path)

# Phase boundaries = the `_progress.step()` call sites in pipeline.py.
# Samples are bucketed by the innermost pipeline.py line on the stack.
# These line numbers are the ``_progress.step()`` call sites in pipeline.py
# that begin each phase; a sample is attributed to the phase whose step()
# most recently preceded the innermost pipeline.py frame.  Keep them in sync
# with pipeline.py (they drifted from 486/562/1642/2972/3892/5590, which
# mis-attributed late phase-4 taxi-rect construction to the solve phase).
PHASE_STARTS = [
    (619, "1 Loading apt.dat & runway geometry"),
    (695, "2 Assembling pavement & runway shoulders"),
    (1991, "3 Building taxiways & terminals"),
    (3321, "4 Building taxi rects, junctions & service roads"),
    (4241, "5 Solving elevations (FAA grade compliance)"),
    (5951, "6 Emitting terrain features & finalizing"),
]


def _phase_for_line(lineno):
    name = "0 before step 1"
    for start, phase in PHASE_STARTS:
        if lineno >= start:
            name = phase
    return name


class StackSampler(threading.Thread):
    """Samples one target thread's stack until ``stop()`` is called."""

    def __init__(self, target_thread_id, interval):
        super().__init__(daemon=True)
        self.target_thread_id = target_thread_id
        self.interval = interval
        self.samples = 0
        self.leaf_counts = collections.Counter()
        self.inclusive_counts = collections.Counter()
        self.pipeline_site_counts = collections.Counter()  # (phase, "file:line fn")
        self.phase_counts = collections.Counter()
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        while not self._stop_event.is_set():
            frame = sys._current_frames().get(self.target_thread_id)
            if frame is not None:
                self._record(frame)
            time.sleep(self.interval)

    def _record(self, frame):
        self.samples += 1
        seen = set()
        leaf_key = None
        pipeline_site = None
        pipeline_line = None
        depth = 0
        while frame is not None and depth < 200:
            code = frame.f_code
            filename = code.co_filename
            short = os.path.relpath(filename, ROOT) if filename.startswith(ROOT) else filename
            key = f"{short}:{code.co_name}"
            if leaf_key is None:
                leaf_key = f"{short}:{frame.f_lineno} {code.co_name}"
            if key not in seen:
                seen.add(key)
                self.inclusive_counts[key] += 1
            # innermost pipeline.py frame = the pipeline task being executed
            if pipeline_site is None and short.endswith("auto_patch/pipeline.py"):
                pipeline_site = f"pipeline.py:{frame.f_lineno} in {code.co_name}"
                pipeline_line = frame.f_lineno
            frame = frame.f_back
            depth += 1
        self.leaf_counts[leaf_key] += 1
        if pipeline_line is not None:
            phase = _phase_for_line(pipeline_line)
            self.phase_counts[phase] += 1
            self.pipeline_site_counts[(phase, pipeline_site)] += 1
        else:
            self.phase_counts["(no pipeline.py frame)"] += 1


class CallCounter:
    """Call count + INCLUSIVE seconds for one named callable.

    Reentrancy is tracked with a depth counter so a recursive or
    mutually-nested target is not double-counted into its own inclusive
    total (the outermost activation owns the interval).
    """

    def __init__(self, label):
        self.label = label
        self.calls = 0
        self.seconds = 0.0
        self._depth = 0

    def wrap(self, fn):
        def wrapper(*a, **kw):
            self.calls += 1
            if self._depth:
                return fn(*a, **kw)
            self._depth = 1
            t0 = time.perf_counter()
            try:
                return fn(*a, **kw)
            finally:
                self._depth = 0
                self.seconds += time.perf_counter() - t0
        wrapper.__name__ = getattr(fn, "__name__", self.label)
        wrapper.__wrapped__ = fn
        return wrapper


def _install_counters(specs):
    """Wrap each ``MODULE:ATTR`` spec; return the counters (install order)."""
    import importlib
    counters = []
    for spec in specs:
        mod_name, _, attr = spec.partition(":")
        if not attr:
            raise SystemExit(f"--count wants MODULE:ATTR, got {spec!r}")
        module = importlib.import_module(mod_name)
        target = getattr(module, attr)
        counter = CallCounter(spec)
        setattr(module, attr, counter.wrap(target))
        counters.append(counter)
    return counters


def _run_replay(capture_dir):
    """Replay a solve capture in-process; return (icao, body_sha256)."""
    sys.path.insert(0, os.path.join(ROOT, "tools", "harness"))
    import solve_cut                                        # noqa: E402
    from auto_patch.solve_capture import (                  # noqa: E402
        read_manifest, load_capture, CAPTURE_ENV)
    from shared_repo_guard import SharedRepoWriteGuard      # noqa: E402
    import auto_patch.pipeline as pipeline                  # noqa: E402

    manifest = read_manifest(capture_dir)
    solve_cut.restore_env(manifest)
    os.environ.pop(CAPTURE_ENV, None)
    tail, _m = load_capture(capture_dir)
    out = os.path.join(capture_dir, "replay",
                       f"{manifest.get('icao')}.profile.osm")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with SharedRepoWriteGuard(requested=(), root=ROOT):
        layout = pipeline.solve_and_finalize(**tail)
    layout.to_osm(out)
    from build_airport import body_sha256                   # noqa: E402
    return manifest.get("icao"), body_sha256(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("icao", nargs="?")
    parser.add_argument("--replay", default=None, metavar="CAPTURE_DIR",
                        help="profile a solve-stage capture replay "
                             "(phases [5]+[6]) instead of a whole build")
    parser.add_argument("--count", action="append", default=[],
                        metavar="MODULE:ATTR",
                        help="also count calls + inclusive seconds of this "
                             "callable (repeatable)")
    parser.add_argument("--interval", type=float, default=0.02)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    if bool(args.icao) == bool(args.replay):
        parser.error("pass an ICAO to profile a build, or --replay "
                     "CAPTURE_DIR to profile a capture replay — not both")

    label = args.icao or os.path.basename(str(args.replay).rstrip("/"))
    out_path = args.out or f"/tmp/{label}_profile.txt"
    counters = _install_counters(args.count) if args.count else []
    replay_sha = None

    if args.replay:
        target = lambda: _run_replay(args.replay)           # noqa: E731
    else:
        from conftest import xplane_root                    # noqa: E402
        from auto_patch.pipeline import build_airport_pavement  # noqa: E402
        target = lambda: build_airport_pavement(            # noqa: E731
            args.icao, xplane_root(), compute_elevations=True)

    sampler = StackSampler(threading.get_ident(), args.interval)
    sampler.start()
    t0 = time.time()
    result = target()
    elapsed = time.time() - t0
    sampler.stop()
    sampler.join(timeout=2.0)
    if args.replay:
        label, replay_sha = result

    per_sample = elapsed / max(sampler.samples, 1)

    def secs(n):
        return n * per_sample

    lines = []
    what = "replay [5]+[6]" if args.replay else "build"
    lines.append(f"{label} {what}: {elapsed:.1f} s wall, "
                 f"{sampler.samples} samples ({per_sample * 1000:.1f} ms/sample)")
    if replay_sha is not None:
        lines.append(f"  replayed body_sha256={replay_sha}")

    if counters:
        lines.append("\n== Counted callables (inclusive) ==")
        for counter in counters:
            lines.append(f"  {counter.seconds:8.1f} s  {counter.calls:9d} "
                         f"call(s)  {counter.label}")

    lines.append("\n== Seconds per pipeline phase (sampled) ==")
    for phase, n in sorted(sampler.phase_counts.items()):
        lines.append(f"  {secs(n):8.1f} s  {phase}")

    lines.append("\n== Top pipeline.py call sites per phase ==")
    by_phase = collections.defaultdict(collections.Counter)
    for (phase, site), n in sampler.pipeline_site_counts.items():
        by_phase[phase][site] += n
    for phase in sorted(by_phase):
        lines.append(f"  -- {phase} --")
        for site, n in by_phase[phase].most_common(15):
            if secs(n) < 1.0:
                break
            lines.append(f"     {secs(n):8.1f} s  {site}")

    lines.append("\n== Top 60 functions by inclusive wall time ==")
    for key, n in sampler.inclusive_counts.most_common(60):
        lines.append(f"  {secs(n):8.1f} s  {key}")

    lines.append("\n== Top 40 leaf (self-time) sites ==")
    for key, n in sampler.leaf_counts.most_common(40):
        lines.append(f"  {secs(n):8.1f} s  {key}")

    report = "\n".join(lines) + "\n"
    with open(out_path, "w") as handle:
        handle.write(report)
    print(report)
    print(f"report written to {out_path}")


if __name__ == "__main__":
    main()
