"""Replay a recorder flight through the imagery tier planner (#1992 P3a).

    venv/bin/python tools/imagery_tier_replay.py extract FLIGHT.jsonl \
        LOADS.csv PACK_DIR --out FLIGHT.replay.json [--window T0 T1]
    venv/bin/python tools/imagery_tier_replay.py replay FLIGHT.replay.json \
        [--req-rate 85] [--convert-full-s 2] [--slots 1] [--lead 30]
        [--spawn-s 60] [--core] [--sweep]

``extract`` turns a ``record_reads.py`` log (camera positions, ``pos``
rows), the per-load CSV of the kit's ``analyse_reads.py --csv`` (time,
texture, finest mip; P1b promotes that loader) and the pack's ``.ter``
files (``LOAD_CENTER``: centre and S) into one compact JSON:
``{"squares": [[name, lat, lon, S]], "pos": [[t, lat, lon, alt, gs]],
"loads": [[t, name, mip]]}`` (``gs``: the groundspeed dataref, m/s;
times in seconds from the log's start;
``--window`` keeps that slice, for a twin fixture).

``replay`` steps the positions, asks :func:`O4_Imagery_Tier_Plan.plan`
once per position for the fetch list, runs a simulated fetcher (``slots``
files in flight; a tier-k file takes ``requests_k / req_rate`` plus
``convert_full_s / 4**(3-k)`` seconds) and judges every recorded STEP-UP
open (a texture's first load, or a load finer than its previous one) as
served when a file at least as fine as the level loaded had landed by
then.  The camera's groundspeed and track come from the position deltas
(flight 2 flew with the ground-speed multiplier).  Loads in the first
``--spawn-s`` seconds are the flight-start window (spec §4.5, P5) and are
reported apart; ``--true-speed`` re-times the flight to the groundspeed
dataref (flight 2 flew with the ground-speed multiplier at up to ~8x);
``--core`` starts with the start position's planned tiers
already on disk (a built airport's kept core, §6.1).
"""
from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "src"))
import O4_Imagery_Tier_Plan as TP  # noqa: E402

_M_PER_DEG = 111_320.0


# --------------------------------------------------------------------------
# extract
# --------------------------------------------------------------------------
def read_squares(pack_dir: str) -> list[list]:
    """[[texture, lat, lon, S]] from the pack's terrain/*.ter LOAD_CENTER."""
    out, seen = [], set()
    ter_dir = os.path.join(pack_dir, "terrain")
    for name in sorted(os.listdir(ter_dir)):
        if not name.endswith(".ter"):
            continue
        centre = tex = None
        with open(os.path.join(ter_dir, name), encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if parts[:1] == ["LOAD_CENTER"]:
                    centre = (float(parts[1]), float(parts[2]), float(parts[3]))
                elif parts[:1] and parts[0].startswith("BASE_TEX"):
                    tex = os.path.basename(parts[1])
        if centre and tex and tex not in seen:
            seen.add(tex)
            out.append([tex, *centre])
    return out


def camera(p: dict) -> tuple[float, float, float]:
    """Camera lat/lon/alt: aircraft + view offset (local +x east, +z south)."""
    try:
        dx, dz = p["view_x"] - p["local_x"], p["view_z"] - p["local_z"]
    except (KeyError, TypeError):
        return p["lat"], p["lon"], p.get("elev_m", 0.0)
    lat = p["lat"] - dz / _M_PER_DEG
    lon = p["lon"] + dx / (_M_PER_DEG * max(0.1, math.cos(math.radians(p["lat"]))))
    return lat, lon, p.get("elev_m", 0.0) + p.get("view_y", 0.0) - p.get("local_y", 0.0)


def extract(log: str, loads_csv: str, pack_dir: str, window=None) -> dict:
    t0, pos = None, []
    with open(log, encoding="utf-8") as f:
        for line in f:
            if '"kind":"meta"' in line and t0 is None:
                t0 = json.loads(line)["t"]
            elif '"kind":"pos"' in line:
                p = json.loads(line)
                if "lat" in p:
                    lat, lon, alt = camera(p)
                    pos.append([round(p["t"] - t0, 2), round(lat, 6),
                                round(lon, 6), round(alt, 1),
                                round(p.get("gs_ms") or 0.0, 1)])
    loads = []
    with open(loads_csv, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["tile"] == "True" and r["finest"] not in ("", "None"):
                loads.append([round(float(r["t"]) - t0, 2), r["file"],
                              int(r["finest"])])
    if window:
        lo, hi = window
        pos = [p for p in pos if lo <= p[0] <= hi]
        loads = [x for x in loads if lo <= x[0] <= hi]
    return {"source": os.path.basename(log), "squares": read_squares(pack_dir),
            "pos": pos, "loads": sorted(loads)}


# --------------------------------------------------------------------------
# replay
# --------------------------------------------------------------------------
def fetch_seconds(req_rate: float, convert_full_s: float) -> dict[int, float]:
    """Simulated wall seconds to land one file of each tier (1..3)."""
    return {k: TP.TIER_REQUESTS[k] / req_rate + convert_full_s / 4 ** (3 - k)
            for k in (1, 2, 3)}


def motions(pos: list, back: int = 3) -> list[TP.Motion]:
    """One Motion per position; velocity from the position ``back`` samples
    earlier (the camera's real motion over the ground)."""
    out = []
    for i, (t, lat, lon, alt, *_) in enumerate(pos):
        j = max(0, i - back)
        tj, latj, lonj = pos[j][:3]
        dt = t - tj
        east = (lon - lonj) * _M_PER_DEG * math.cos(math.radians(lat))
        north = (lat - latj) * _M_PER_DEG
        v = math.hypot(east, north) / dt if dt > 0 else 0.0
        trk = math.degrees(math.atan2(east, north)) % 360.0 if v > 0 else 0.0
        out.append(TP.Motion(lat, lon, alt, trk, v))
    return out


def step_ups(loads: list) -> list[tuple[float, str, int]]:
    """(t, texture, tier wanted) of every step-up open."""
    last: dict[str, int] = {}
    out = []
    for t, name, mip in loads:
        if name not in last or mip < last[name]:
            out.append((t, name, TP.tier_for_mip(mip)))
        last[name] = mip
    return out


def at_true_speed(data: dict, max_factor: float = 16.0) -> dict:
    """The same flight re-timed so the camera moves at the groundspeed
    dataref: each position interval is stretched by observed speed / gs
    (the ground-speed multiplier, clamped to [1, max_factor]); loads are
    re-timed through the same map (they follow distance, not time)."""
    pos = data["pos"]
    if not pos:
        return data
    new_t = [pos[0][0]]
    for a, b in zip(pos, pos[1:], strict=False):
        dt = b[0] - a[0]
        d = math.hypot((b[2] - a[2]) * _M_PER_DEG * math.cos(math.radians(a[1])),
                       (b[1] - a[1]) * _M_PER_DEG)
        gs = b[4] if len(b) > 4 else 0.0
        f = d / (gs * dt) if gs > 5.0 and dt > 0 else 1.0
        new_t.append(new_t[-1] + dt * min(max_factor, max(1.0, f)))
    old_t = [p[0] for p in pos]

    def remap(t: float) -> float:
        i = bisect.bisect_left(old_t, t)
        if i <= 0:
            return new_t[0] + (t - old_t[0])
        if i >= len(old_t):
            return new_t[-1] + (t - old_t[-1])
        f = (t - old_t[i - 1]) / ((old_t[i] - old_t[i - 1]) or 1.0)
        return new_t[i - 1] + f * (new_t[i] - new_t[i - 1])
    return {**data, "pos": [[nt, *p[1:]] for nt, p in zip(new_t, pos, strict=True)],
            "loads": [[remap(t), n, m] for t, n, m in data["loads"]]}


def simulate(data: dict, *, req_rate=85.0, convert_full_s=2.0, slots=1,
             lead_s=TP.DEFAULT_LEAD_S, core=False) -> dict:
    """Run the planner + fetcher over the flight; landings and counters."""
    squares = [TP.Square(n, la, lo, s) for n, la, lo, s in data["squares"]]
    pos = data["pos"]
    mot = motions(pos)
    fs = fetch_seconds(req_rate, convert_full_s)
    on_disk: dict[str, int] = {}
    if core and mot:
        still = TP.Motion(mot[0].lat, mot[0].lon, mot[0].alt_m, 0.0, 0.0)
        for f in TP.plan(still, squares, {}, lead_s=lead_s):
            on_disk[f.square] = max(on_disk.get(f.square, 0), f.tier)
    landed = {n: [(-1e9, k)] for n, k in on_disk.items()}
    flying: list[tuple[float, str, int]] = []      # (done_t, square, tier)
    fetched = {1: 0, 2: 0, 3: 0}
    late_starts = 0
    for i, m in enumerate(mot):
        t = pos[i][0]
        t_next = pos[i + 1][0] if i + 1 < len(pos) else t + 1.0
        fl = TP.plan(m, squares, on_disk, lead_s=lead_s, fetch_s=fs)
        queue: list[TP.Fetch] = [f for f in fl if f.due]
        clock = t
        while True:
            flying.sort()
            while flying and flying[0][0] <= clock:
                done, n, k = flying.pop(0)
                if k > on_disk.get(n, 0):
                    on_disk[n] = k
                    landed.setdefault(n, [(-1e9, 0)]).append((done, k))
            if len(flying) >= slots:
                clock = flying[0][0]
                if clock >= t_next:
                    break
                continue
            pick = None
            while queue:
                f = queue.pop(0)
                busy = max([k for _, n, k in flying if n == f.square], default=0)
                if max(busy, on_disk.get(f.square, 0)) < f.tier:
                    pick = f
                    break
            if pick is None:
                break
            flying.append((clock + fs[pick.tier], pick.square, pick.tier))
            fetched[pick.tier] += 1
            late_starts += pick.late
    return {"landed": landed, "fetched": fetched, "late_starts": late_starts,
            "fetch_s": fs}


def tier_at(landed: dict, name: str, t: float) -> int:
    best = 0
    for tl, k in landed.get(name, ()):
        if tl <= t:
            best = max(best, k)
    return best


def judge(data: dict, sim: dict, spawn_s: float = 60.0) -> dict:
    """Served / missed step-up opens, split flight-start window vs flight."""
    out = {"window": [0, 0], "flight": [0, 0], "placeholder": 0,
           "by_tier": {k: [0, 0] for k in (1, 2, 3)}, "misses": []}
    t_start = data["pos"][0][0] if data["pos"] else 0.0
    for t, name, want in step_ups(data["loads"]):
        if want == 0:
            out["placeholder"] += 1
            continue
        ok = tier_at(sim["landed"], name, t) >= want
        part = out["window"] if t - t_start < spawn_s else out["flight"]
        part[0] += ok
        part[1] += 1
        if t - t_start >= spawn_s:
            out["by_tier"][want][0] += ok
            out["by_tier"][want][1] += 1
            if not ok:
                out["misses"].append((t, name, want,
                                      tier_at(sim["landed"], name, t)))
    return out


def flown_km(pos: list) -> float:
    d = 0.0
    for (_, la1, lo1, *_), (_, la2, lo2, *_) in zip(pos, pos[1:], strict=False):
        d += math.hypot((lo2 - lo1) * _M_PER_DEG * math.cos(math.radians(la1)),
                        (la2 - la1) * _M_PER_DEG)
    return d / 1000.0


def report(data: dict, sim: dict, j: dict, label: str = "") -> str:
    fl, win = j["flight"], j["window"]
    pct = 100.0 * fl[0] / fl[1] if fl[1] else 100.0
    minutes = (data["pos"][-1][0] - data["pos"][0][0]) / 60.0 if data["pos"] else 0
    req = sum(TP.TIER_REQUESTS[k] * n for k, n in sim["fetched"].items())
    mb = sum(TP.TIER_BYTES[k] * n for k, n in sim["fetched"].items()) / 1e6
    km = flown_km(data["pos"])
    tiers = " ".join(f"T{k} {a}/{b}" for k, (a, b) in j["by_tier"].items())
    fetched = " ".join(f"T{k} {n}" for k, n in sim["fetched"].items())
    times = " ".join(f"T{k} {s:.1f}s" for k, s in sim["fetch_s"].items())
    return (f"{label}step-up opens after the start window: {fl[0]}/{fl[1]} "
            f"served ({pct:.1f} %) [{tiers}]; start window {win[0]}/{win[1]}; "
            f"placeholder-only {j['placeholder']}\n"
            f"   fetched {fetched} (late starts {sim['late_starts']}); "
            f"{req} requests = {req / max(minutes, 1e-9) / 60:.1f} req/s, "
            f"{mb / max(minutes, 1e-9):.0f} MB/min; {km:.0f} km in "
            f"{minutes:.1f} min = {req / max(km, 1e-9):.0f} req/km, "
            f"{mb / max(km, 1e-9) * 100:.0f} MB/100 km; file times {times}")


def main(argv=None) -> int:
    import O4_Console_Encoding
    O4_Console_Encoding.configure_console_streams()
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("extract")
    ex.add_argument("log")
    ex.add_argument("loads_csv")
    ex.add_argument("pack_dir")
    ex.add_argument("--out", required=True)
    ex.add_argument("--window", nargs=2, type=float)
    rp = sub.add_parser("replay")
    rp.add_argument("replay_json")
    rp.add_argument("--req-rate", type=float, default=85.0)
    rp.add_argument("--convert-full-s", type=float, default=2.0)
    rp.add_argument("--slots", type=int, default=1)
    rp.add_argument("--lead", type=float, default=TP.DEFAULT_LEAD_S)
    rp.add_argument("--spawn-s", type=float, default=60.0)
    rp.add_argument("--core", action="store_true")
    rp.add_argument("--sweep", action="store_true",
                    help="a grid of req-rate x slots x lead x core")
    rp.add_argument("--misses", action="store_true")
    rp.add_argument("--true-speed", action="store_true",
                    help="re-time the flight to the groundspeed dataref "
                    "(undo X-Plane's ground-speed multiplier)")
    a = ap.parse_args(argv)
    if a.cmd == "extract":
        data = extract(a.log, a.loads_csv, a.pack_dir, a.window)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(data, f, separators=(",", ":"))
        print(f"{a.out}: {len(data['squares'])} squares, {len(data['pos'])} "
              f"positions, {len(data['loads'])} loads")
        return 0
    with open(a.replay_json, encoding="utf-8") as f:
        data = json.load(f)
    if a.true_speed:
        data = at_true_speed(data)
    grid = ([(r, s, ld, c) for c in (False, True) for ld in (30.0, 60.0)
             for s in (1, 2) for r in (17.6, 85.0, 187.0)] if a.sweep
            else [(a.req_rate, a.slots, a.lead, a.core)])
    for r, s, ld, c in grid:
        sim = simulate(data, req_rate=r, convert_full_s=a.convert_full_s,
                       slots=s, lead_s=ld, core=c)
        j = judge(data, sim, a.spawn_s)
        print(report(data, sim, j, f"[{r:g} req/s, {s} slot(s), lead {ld:g} s"
                     f"{', core' if c else ''}] "))
        if a.misses:
            for t, n, want, have in j["misses"]:
                print(f"   miss t={t:.1f} {n} wanted T{want} had T{have}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
