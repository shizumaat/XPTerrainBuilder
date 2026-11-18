"""Replay a flight from the on-demand log through the imagery PAGE-AHEAD
scheduler (#2109): does every square land before X-Plane pages it in?

    venv/bin/python tools/imagery_page_ahead_replay.py LOG INDEX.sqlite \
        --from 2026-11-16T07:42:00 --to 2026-11-16T07:54:00 \
        [--anchor LAT,LON] [--extend-s 1800] [--speed-kt 250] [--track-deg 270]
        [--fetch median|p90] [--slots 1] [--json OUT] [--track TRACK.json]

The track: the follow job's ``pos=`` lines (written since #2109) between
``--from`` and ``--to``; a log without them (every flight before #2109)
gets a track RECONSTRUCTED from its landings (:func:`fit_track`: a smooth
path, a knot every 30 s, that puts each landing's square at its planned
start distance -- ``CROSSING_S[k] * S`` plus the lead -- from the camera
when it started; ``--anchor`` pins the first knot, e.g. the departure
airport; the fit takes ~2 min, so ``--json`` saves the track as
``track_base`` and ``--track`` reads it back).  ``--extend-s`` flies on
straight from the track's last motion (``--speed-kt`` re-times that leg,
``--track-deg`` turns it), so a short flight that never left its first
window still shows the window's moves.

The replay loads X-Plane's DSF window at the first position
(``O4_World_Window``: a flight load), moves it along the track, plans the
page-ahead every 5 s (``O4_Imagery_Page_Ahead``) and lands its fetches
with ``--slots`` fetchers at the landing times measured at that many
slots (every download landing in the on-demand log to 2026-11-16, 1,650
of them; a slot shares the provider with the others, so four slots land
a tier-3 file in 5.7 s, not 2.6: :data:`FETCH_S`, ``--fetch median`` or
``p90``).  Squares start at the tier the log had landed for
them before ``--from`` (else the placeholder, tier 0).  It reports:

* PAGED: every square of a tile that ENTERED the window, the tier the
  flown track (after the entry) wants there, and whether that tier was on
  disk at the entry (the paging time) -- the claim is "none short";
* FIRST WINDOW: the squares of the window loaded at the first position
  that the flown track wants finer than they had at that load: what only
  a reload or a step-up re-read (local-imagery-cache spec §2.5) shows,
  and what a built tile's core ring must hold for a departure;
* the requests and MB per minute the page-ahead asked.

No sim, no network; reads the log and a COPY of the index.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sqlite3
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "src"))

import O4_Imagery_Page_Ahead as PAGE  # noqa: E402
import O4_Imagery_Tier_Plan as PLAN  # noqa: E402
import O4_World_Window as WINDOW  # noqa: E402
from O4_Imagery_Follow_Motion import MotionTracker  # noqa: E402

#: Measured landing seconds per tier at 1-4 slots: every download
#: landing of the on-demand log to 2026-11-16 (1,650; no source landings).
FETCH_S = {
    "median": {1: {1: 0.32, 2: 0.79, 3: 2.57}, 2: {1: 0.77, 2: 1.40, 3: 3.13},
               3: {1: 0.76, 2: 1.22, 3: 3.17}, 4: {1: 0.82, 2: 2.10, 3: 5.66}},
    "p90": {1: {1: 0.90, 2: 1.75, 3: 5.19}, 2: {1: 1.85, 2: 2.99, 3: 6.76},
            3: {1: 2.81, 2: 3.33, 3: 8.20}, 4: {1: 5.58, 2: 8.39, 3: 27.67}},
}
_M_PER_DEG = 111_320.0
_KV = re.compile(r"(\w+)=(\S+)")


def _stamp(text: str) -> float:
    return time.mktime(time.strptime(text, "%Y-%m-%dT%H:%M:%S"))


def read_log(path: str) -> list[tuple[float, dict]]:
    """``[(local time, {key: value})]`` of the on-demand log's lines."""
    out = []
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            head, _, rest = line.partition(" ")
            try:
                out.append((_stamp(head), dict(_KV.findall(rest))))
            except ValueError:
                continue
    return out


def pos_track(lines, t0: float, t1: float) -> list:
    """``[(t, lat, lon)]`` of the ``pos`` lines between ``t0`` and ``t1``."""
    out = []
    for stamp, kv in lines:
        if "pos" in kv and t0 <= stamp <= t1:
            lat, lon = (float(v) for v in kv["pos"].split(","))
            out.append((float(kv.get("t", stamp)), lat, lon))
    return out


def landings(lines, t0: float, t1: float) -> list:
    """The landings started between ``t0`` and ``t1``: ``(started,
    square, tier, crossing, late)``."""
    out = []
    for _t, kv in lines:
        if "square" in kv and "started" in kv:
            s = float(kv["started"])
            if t0 <= s <= t1:
                out.append((s, kv["square"], int(kv["tier"]),
                            int(kv.get("crossing", kv["tier"])),
                            kv.get("late") == "True"))
    return out


def tiers_before(lines, t: float) -> dict:
    """``{square: finest tier landed before t}``."""
    out: dict = {}
    for _t, kv in lines:
        if "square" in kv and "landed" in kv and float(kv["landed"]) < t:
            out[kv["square"]] = max(out.get(kv["square"], 0), int(kv["tier"]))
    return out


def read_squares(index: str) -> dict:
    """``{(lat, lon) tile: [Square]}`` of the index (keys ``tile/name``)."""
    conn = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
    out: dict = {}
    try:
        for tile, name, lat, lon, size in conn.execute(
                "SELECT tile, name, centre_lat, centre_lon, load_size_m "
                "FROM textures WHERE load_size_m > 0"):
            key = (int(tile[:3]), int(tile[3:]))
            out.setdefault(key, []).append(
                PLAN.Square(f"{tile}/{name}", lat, lon, size))
    finally:
        conn.close()
    return out


def fit_track(lands, squares: dict, t0: float, t1: float, anchor=None,
              knot_s: float = 30.0, lead_s: float = PLAN.DEFAULT_LEAD_S):
    """A track reconstructed from ``lands`` (see the module)."""
    import numpy as np
    from scipy.optimize import least_squares
    where = {sq.name: sq for tile in squares.values() for sq in tile}
    ev = [(s - t0, where[n], k, late) for s, n, _tier, k, late in lands
          if n in where and k > 0]
    knots = np.arange(0.0, t1 - t0 + knot_s, knot_s)
    n = len(knots)
    cos0 = math.cos(math.radians(ev[0][1].lat if ev else 45.0))

    def at(p, t):
        return np.interp(t, knots, p[:n]), np.interp(t, knots, p[n:])

    def resid(p):
        r = []
        for t, sq, k, late in ev:
            lat, lon = at(p, t)
            la2, lo2 = at(p, t + 10.0)
            v = math.hypot(la2 - lat, (lo2 - lon) * cos0) * _M_PER_DEG / 10.0
            d = math.hypot(sq.lat - lat, (sq.lon - lon) * cos0) * _M_PER_DEG
            aim = PLAN.CROSSING_S[k] * sq.size_m + (0.0 if late else v * lead_s)
            r.append(max(0.0, d - aim - 0.5 * sq.size_m) / 1000.0 * 3.0)
            r.append((d - aim) / 1000.0 * 0.3)
        lat, lon = p[:n], p[n:]
        r += list(np.diff(lat, 2) * _M_PER_DEG / 500.0)
        r += list(np.diff(lon, 2) * _M_PER_DEG * cos0 / 500.0)
        if anchor is not None:
            r += [(lat[0] - anchor[0]) * _M_PER_DEG / 200.0,
                  (lon[0] - anchor[1]) * _M_PER_DEG * cos0 / 200.0]
        return np.array(r)

    start = anchor or ((ev[0][1].lat, ev[0][1].lon) if ev else (0.0, 0.0))
    p0 = np.concatenate([np.full(n, start[0]), np.full(n, start[1])])
    sol = least_squares(resid, p0)
    return [(t0 + float(t), float(a), float(b))
            for t, a, b in zip(knots, sol.x[:n], sol.x[n:], strict=True)]


def resample(track, step_s: float = 1.0) -> list:
    """``track`` linearly interpolated every ``step_s``."""
    out, j = [], 0
    t = track[0][0]
    while t <= track[-1][0]:
        while j + 1 < len(track) - 1 and track[j + 1][0] < t:
            j += 1
        (ta, la, lo), (tb, lb, lob) = track[j], track[min(j + 1, len(track) - 1)]
        f = 0.0 if tb <= ta else (t - ta) / (tb - ta)
        out.append((t, la + f * (lb - la), lo + f * (lob - lo)))
        t += step_s
    return out


def extend(track, seconds: float, speed_ms: float | None = None,
           track_deg: float | None = None) -> list:
    """``track`` flown on straight for ``seconds`` from its last motion
    (at ``speed_ms`` and on ``track_deg`` when given)."""
    if seconds <= 0 or len(track) < 2:
        return track
    tracker = MotionTracker()
    for t, la, lo in track[-8:]:
        m = tracker.add(t, la, lo)
    v = m.groundspeed_ms if speed_ms is None else speed_ms
    trk = m.track_deg if track_deg is None else track_deg
    out, t, lat, lon = list(track), track[-1][0], m.lat, m.lon
    for _ in range(int(seconds)):
        t += 1.0
        lat += v * math.cos(math.radians(trk)) / _M_PER_DEG
        lon += (v * math.sin(math.radians(trk))
                / (_M_PER_DEG * math.cos(math.radians(lat))))
        out.append((t, lat, lon))
    return out


def _wanted(track, i: int, sq) -> int:
    """The tier the flown track from point ``i`` on wants at ``sq``."""
    return PAGE.target_tier(track[i::10] + track[-1:], sq)


def simulate(track, squares: dict, on_disk: dict, fetch_s: dict,
             slots: int = 1, lead_s: float = PLAN.DEFAULT_LEAD_S) -> dict:
    """Fly ``track`` (1 s steps) with the page-ahead (see the module)."""
    disk = dict(on_disk)
    window = WINDOW.WindowTracker()
    window.load(track[0][1], track[0][2])
    first = window.window()
    first_disk = dict(disk)
    motion, queue, busy = MotionTracker(), [], []   # busy: (end, Fetch)
    paged, asked = {}, {1: 0, 2: 0, 3: 0}
    for i, (t, lat, lon) in enumerate(track):
        m = motion.add(t, lat, lon)
        for tile in window.update(lat, lon):
            for sq in squares.get(tile, ()):
                paged.setdefault(sq.name, (t, i, tile, disk.get(sq.name, 0)))
        for end, f in list(busy):
            if end <= t:
                busy.remove((end, f))
                disk[f.square] = max(disk.get(f.square, 0), f.tier)
        if i % 5 == 0 and m.groundspeed_ms > 0.5:
            path = PAGE.straight_path(m, PAGE.PAGE_HORIZON_S + PAGE.PASS_S)
            near = [p for p in path if p[0] <= PAGE.PAGE_HORIZON_S]
            queue = [(t + f.start_in_s, f) for f in PAGE.plan_ahead(
                [path[0], path[-1]], PAGE.entries(window, near), squares, disk,
                m.groundspeed_ms, fetch_s=fetch_s, lead_s=lead_s)]
        running = {f.square for _e, f in busy}
        for due_at, f in sorted(queue, key=lambda q: q[1].deadline_s):
            if len(busy) >= slots:
                break
            if due_at <= t and f.square not in running and \
                    disk.get(f.square, 0) < f.tier:
                busy.append((t + fetch_s[f.tier], f))
                running.add(f.square)
                asked[f.tier] += 1
    where = {sq.name: sq for tile in squares.values() for sq in tile}
    judged = []
    for name, (t, i, tile, had) in sorted(paged.items(), key=lambda kv: kv[1][0]):
        want = _wanted(track, i, where[name])
        if want:
            judged.append({"square": name, "tile": list(tile), "t": t,
                           "want": want, "had": had, "ok": had >= want})
    stale = []
    for tile in first:
        for sq in squares.get(tile, ()):
            want = _wanted(track, 0, sq)
            if want > first_disk.get(sq.name, 0):
                stale.append({"square": sq.name, "want": want,
                              "had": first_disk.get(sq.name, 0)})
    minutes = max(1e-9, (track[-1][0] - track[0][0]) / 60.0)
    return {"paged": judged, "short": [j for j in judged if not j["ok"]],
            "first_window_stale": stale, "asked": asked,
            "req_per_min": sum(asked[k] * PLAN.TIER_REQUESTS[k] for k in asked)
            / minutes,
            "mb_per_min": sum(asked[k] * PLAN.TIER_BYTES[k] for k in asked)
            / 1e6 / minutes}


def report(sim: dict, track) -> str:
    entries = sorted({tuple(j["tile"]) for j in sim["paged"]})
    by_want = {k: sum(1 for s in sim["first_window_stale"] if s["want"] == k)
               for k in (1, 2, 3)}
    lines = [
        f"track: {len(track)} s, {track[0][1]:.4f},{track[0][2]:.4f} -> "
        f"{track[-1][1]:.4f},{track[-1][2]:.4f}",
        f"PAGED: {len(sim['paged'])} wanted squares in {len(entries)} "
        f"entering tiles {entries}; short at entry: {len(sim['short'])}",
        f"FIRST WINDOW: {len(sim['first_window_stale'])} squares wanted finer "
        f"than on disk at the load (tier 1/2/3: {by_want[1]}/{by_want[2]}/"
        f"{by_want[3]})",
        f"page-ahead asked {sim['asked']} = {sim['req_per_min']:.0f} "
        f"requests/min, {sim['mb_per_min']:.0f} MB/min"]
    for s in sim["short"][:20]:
        lines.append(f"  short: {s['square']} want {s['want']} had {s['had']}")
    return "\n".join(lines)


def main(argv=None) -> int:
    import O4_Console_Encoding
    O4_Console_Encoding.configure_console_streams()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("log")
    ap.add_argument("index")
    ap.add_argument("--from", dest="t0", required=True)
    ap.add_argument("--to", dest="t1", required=True)
    ap.add_argument("--anchor")
    ap.add_argument("--extend-s", type=float, default=0.0)
    ap.add_argument("--speed-kt", type=float)
    ap.add_argument("--track-deg", type=float)
    ap.add_argument("--fetch", choices=sorted(FETCH_S), default="median")
    ap.add_argument("--slots", type=int, default=1)
    ap.add_argument("--json")
    ap.add_argument("--track", help="a --json output: replay its "
                    "track_base instead of the log's")
    a = ap.parse_args(argv)
    t0, t1 = _stamp(a.t0), _stamp(a.t1)
    lines = read_log(a.log)
    squares = read_squares(a.index)
    track = pos_track(lines, t0, t1)
    source = "pos"
    if a.track:
        with open(a.track, encoding="utf-8") as handle:
            track = [tuple(p) for p in json.load(handle)["track_base"]]
        source = a.track
    elif len(track) < 2:
        anchor = tuple(float(v) for v in a.anchor.split(",")) if a.anchor else None
        track = fit_track(landings(lines, t0, t1), squares, t0, t1, anchor)
        source = "reconstructed from landings"
    track = resample(track)
    base = track
    speed = a.speed_kt * 0.514444 if a.speed_kt else None
    track = extend(track, a.extend_s, speed, a.track_deg)
    fetch_s = FETCH_S[a.fetch][min(4, max(1, a.slots))]
    sim = simulate(track, squares, tiers_before(lines, t0), fetch_s, a.slots)
    print(f"track source: {source}; fetch {a.fetch} {fetch_s}, "
          f"slots {a.slots}")
    print(report(sim, track))
    if a.json:
        with open(a.json, "w", encoding="utf-8", newline="\n") as handle:
            json.dump({"track_base": base, **sim}, handle)
    return 1 if sim["short"] else 0


if __name__ == "__main__":
    sys.exit(main())
