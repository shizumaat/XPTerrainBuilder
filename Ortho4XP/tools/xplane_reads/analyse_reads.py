#!/usr/bin/env python3
"""analyse_reads.py: read a record_reads.py log and say what X-Plane loaded,
when, at which distance and at which resolution.  Standard library only.

    python3 analyse_reads.py flight.jsonl [--from camera|aircraft]
                                          [--by centre|edge] [--csv F]

The unit is a LOAD: X-Plane opens a DDS, maps it, touches the mip levels it
wants and closes it within milliseconds.  For each load the finest mip
level is taken, best evidence first, from
  resident  pages of the file resident right after the close (the recorder
            evicts the test packs' DDS after every load, so these are the
            pages this load touched)
  read      read()/pread() byte offsets
  disk      page-in disk blocks D= mapped back to file offsets through the
            file's disk extents
  bytes     the amount paged in during the load: a mip-k load of a file
            whose smaller mips are cached pages ~ the size of mip k
            (estimate; 0 bytes = all cached = unknown)
Mip 0 = full resolution (4096 px for a ZL16 photo square), mip 1 = 2048,
mip 2 = 1024, mip 3 = 512, mip 4 = 256, ...

Sections: 1 distance band x finest mip; 2 every texture's loads; 3 the
timeline per minute; 4 re-load gaps; 5 .ter / .dsf; 6 checks;
7 thresholds (step-up distance per mip per zoom level, in km and in units
of the .ter LOAD_CENTER size S); 8 frame time.
"""
from __future__ import annotations

import argparse
import bisect
import collections
import datetime as _dt
import gzip
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reads_page_cache import snapshot  # noqa: E402
from reads_textures import coverage_finest, mip_ranges, parse_name, resident_finest  # noqa: E402
from reads_thresholds import print_frames, print_thresholds  # noqa: E402

BANDS = [(0, 2), (2, 5), (5, 10), (10, 20), (20, 40), (40, 80),
         (80, float("inf"))]
M_PER_DEG = 111320.0


def band_label(i: int) -> str:
    if i >= len(BANDS):
        return "no pos"
    lo, hi = BANDS[i]
    return f"{lo:g}-{hi:g} km" if hi != float("inf") else f">{lo:g} km"


def band_of(d: float | None) -> int:
    if d is None:
        return len(BANDS)
    for i, (lo, hi) in enumerate(BANDS):
        if lo <= d < hi:
            return i
    return len(BANDS) - 1


def km(a, b) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = (math.sin((la2 - la1) / 2) ** 2
         + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2)
    return 2 * 6371.0 * math.asin(math.sqrt(min(1.0, h)))


def square_distance(sq: dict, at, by: str) -> float:
    if by == "centre":
        return km(at, ((sq["north"] + sq["south"]) / 2,
                       (sq["west"] + sq["east"]) / 2))
    lat = min(max(at[0], sq["south"]), sq["north"])
    lon = min(max(at[1], sq["west"]), sq["east"])
    return km(at, (lat, lon))


def hms(t: float) -> str:
    return _dt.datetime.fromtimestamp(t, _dt.timezone.utc).strftime("%H:%M:%S")


def camera_of(p: dict):
    """Camera lat/lon from the aircraft position + the view offset in
    X-Plane's local frame (+x east, +z south); None without view datarefs."""
    try:
        dx = p["view_x"] - p["local_x"]
        dz = p["view_z"] - p["local_z"]
    except (KeyError, TypeError):
        return None
    lat = p["lat"] - dz / M_PER_DEG
    lon = p["lon"] + dx / (M_PER_DEG * max(0.1, math.cos(math.radians(p["lat"]))))
    return lat, lon, p.get("view_y", 0) - p.get("local_y", 0) + p.get("elev_m", 0)


class Track:
    """Position at time t: linear between the 1 s samples."""

    def __init__(self, pos: list[dict], src: str):
        pts = []
        for p in sorted((p for p in pos if "lat" in p), key=lambda p: p["t"]):
            c = camera_of(p) if src == "camera" else None
            pts.append((p["t"], c or (p["lat"], p["lon"], p.get("elev_m", 0))))
        self.t = [t for t, _ in pts]
        self.p = [q for _, q in pts]
        self.camera = src == "camera" and any(camera_of(p) for p in pos
                                              if "lat" in p)

    def at(self, t: float, max_gap: float = 10.0):
        if not self.t:
            return None
        i = bisect.bisect_left(self.t, t)
        if 0 < i < len(self.t) and self.t[i] - self.t[i - 1] <= max_gap:
            a, b, ta, tb = self.p[i - 1], self.p[i], self.t[i - 1], self.t[i]
            f = (t - ta) / (tb - ta) if tb > ta else 0
            return tuple(x + f * (y - x) for x, y in zip(a, b))  # noqa: B905 (python 3.9)
        for j in (i - 1, i):
            if 0 <= j < len(self.t) and abs(self.t[j] - t) <= max_gap:
                return self.p[j]
        return None


def load(path: str) -> list[dict]:
    out = []
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        for n, ln in enumerate(f, 1):
            ln = ln.strip()
            if ln:
                try:
                    out.append(json.loads(ln))
                except json.JSONDecodeError:
                    print(f"warning: line {n} is not JSON (cut off?)",
                          file=sys.stderr)
    return out


# --------------------------------------------------------------------------
# loads (open -> close episodes) and their mip levels
# --------------------------------------------------------------------------


def bytes_finest(info: dict, nbytes: int):
    """Estimate: the coarsest-to-finest mip whose own size fits the bytes
    paged (smaller mips were cached)."""
    mips = mip_ranges(info) if info and "width" in info else []
    if not mips or not nbytes:
        return None
    best = None
    for lvl, s, e, _w, _h in mips:
        if e - s <= nbytes * 1.02:
            best = lvl if best is None else min(best, lvl)
    return best


class DiskMap:
    """D= disk block -> file offset, through the files' extents.  Finds the
    unit (512 or 4096 bytes) and any constant shift that put the page-ins
    inside their own file."""

    def __init__(self, disk: list[dict], info_of):
        self.unit, self.shift, self.fit = None, 0, 0.0
        samples = []
        for r in disk:
            info = info_of(r["path"], r["t"])
            ext = (info or {}).get("extents")
            if r.get("D") is not None and ext:
                samples.append((r["D"], ext))
        if not samples:
            return
        best = (0.0, None, 0)
        for unit in (512, 4096):
            shifts = collections.Counter(d * unit - ext[0][1]
                                         for d, ext in samples
                                         if d * unit - ext[0][1] >= 0)
            for shift in [0] + [s for s, _ in shifts.most_common(3)]:
                ok = sum(1 for d, ext in samples
                         if self._off(d * unit - shift, ext) is not None)
                fit = ok / len(samples)
                if fit > best[0]:
                    best = (fit, unit, shift)
        if best[0] >= 0.9:
            self.fit, self.unit, self.shift = best

    @staticmethod
    def _off(dev: int, ext):
        for fo, do, ln in ext:
            if do <= dev < do + ln:
                return fo + dev - do
        return None

    def span(self, r: dict, info):
        if self.unit is None or r.get("D") is None:
            return None
        ext = (info or {}).get("extents")
        off = self._off(r["D"] * self.unit - self.shift, ext) if ext else None
        return None if off is None else (off, off + (r.get("bytes") or 0))


def build_loads(ev: list[dict], tile_roots: tuple, info_of) -> list[dict]:
    """One dict per open->close of a DDS (plus the evidence inside it)."""
    open_by_fd: dict = {}
    last_by_path: dict[str, dict] = {}
    loads: list[dict] = []
    for e in ev:
        k = e.get("kind")
        f = e.get("file", "")
        if not str(f).lower().endswith(".dds"):
            continue
        path = e.get("path") or ""
        if k == "open":
            L = {"file": f, "path": path, "t": e["t"], "fd": e.get("fd"),
                 "tile": e.get("tile", path.startswith(tile_roots)),
                 "disk": [], "reads": [], "resident": None, "t_close": None}
            loads.append(L)
            open_by_fd[(e.get("proc"), e.get("fd"))] = L
            last_by_path[path] = L
        elif k == "close":
            L = open_by_fd.pop((e.get("proc"), e.get("fd")), None)
            if L:
                L["t_close"] = e["t"]
        elif k in ("disk", "other") and (k == "disk" or
                                         str(e.get("call", "")).startswith(
                                             ("PgIn", "RdData"))):
            L = last_by_path.get(path)
            if L and e["t"] - (L["t_close"] or e["t"]) <= 2.0:
                L["disk"].append(e)
        elif k == "read":
            L = (open_by_fd.get((e.get("proc"), e.get("fd")))
                 or last_by_path.get(path))
            if L:
                L["reads"].append(e)
        elif k == "resident":
            L = last_by_path.get(path)
            if L and L["resident"] is None:
                L["resident"] = e
    return loads


def judge(L: dict, info, dmap: DiskMap) -> None:
    L["bytes_paged"] = sum(r.get("bytes") or 0 for r in L["disk"])
    L["method"], L["finest"] = "-", None
    res = L["resident"]
    if res and res.get("pages") is not None:
        L["finest"] = resident_finest(info, res["pages"],
                                      res.get("page_size", 16384))
        L["method"] = "resident"
        if L["finest"] is not None:
            return
    spans = [(r["offset"], r["offset"] + (r.get("bytes") or 0))
             for r in L["reads"] if r.get("offset_known")
             and r.get("offset") is not None]
    if spans:
        L["finest"], L["method"] = coverage_finest(info, spans, 0.3), "read"
        if L["finest"] is not None:
            return
    spans = [s for s in (dmap.span(r, info) for r in L["disk"]) if s]
    if spans:
        L["finest"], L["method"] = coverage_finest(info, spans, 0.3), "disk"
        if L["finest"] is not None:
            return
    if L["bytes_paged"]:
        L["finest"], L["method"] = bytes_finest(info, L["bytes_paged"]), "bytes"
    else:
        L["method"] = "cached"


def info_lookup(ev: list[dict]):
    snaps: dict[str, list] = {}
    for e in ev:
        if e.get("kind") == "file" and "width" in e:
            snaps.setdefault(e["path"], []).append((e["t"], e))
    fallback: dict = {}

    def info(path: str, t: float):
        lst = snaps.get(path)
        if lst:
            best = lst[0][1]
            for tt, e in lst:
                if tt <= t:
                    best = e
            return best
        if path not in fallback:
            fallback[path] = snapshot(path) if os.path.exists(path) else None
        return fallback[path]
    return info


# --------------------------------------------------------------------------




def analyse(ev: list[dict], src: str, by: str) -> dict:
    """The log -> its loads (each judged: mip, distance, altitude)."""
    meta = next((e for e in ev if e.get("kind") == "meta"), {})
    roots = tuple(meta.get("tile_roots") or
                  [r.rstrip("/") + "/" for r in meta.get("packs", [])])
    pos = [e for e in ev if e.get("kind") == "pos"]
    track = Track(pos, src)
    info_of = info_lookup(ev)
    dmap = DiskMap([e for e in ev if e.get("kind") == "disk"], info_of)
    loads = build_loads(ev, roots, info_of)
    for L in loads:
        info = info_of(L["path"], L["t"])
        judge(L, info, dmap)
        sq = parse_name(L["file"])
        at = track.at(L["t"])
        L["dist"] = square_distance(sq, at[:2], by) if (sq and at) else None
        L["alt_m"] = at[2] if at else None
        L["width"] = (info or {}).get("width")
    t0 = min([e["t"] for e in ev if "t" in e and e.get("kind") != "meta"]
             or [0])
    return {"meta": meta, "roots": roots, "pos": pos, "track": track,
            "dmap": dmap, "loads": loads, "t0": t0,
            "summary": next((e for e in reversed(ev)
                             if e.get("kind") == "summary"), {})}


def band_table(sel: list[dict]) -> list[tuple[str, list[str], float]]:
    """Section 1's rows: (band, ["loads/textures" per mip column], MB)."""
    cols = sorted({L["finest"] for L in sel if L["finest"] is not None})
    cols += ["?"]
    rows = []
    for bi in range(len(BANDS) + 1):
        ls = [L for L in sel if band_of(L["dist"]) == bi]
        if not ls:
            continue
        cells = []
        for c in cols:
            cs = [L for L in ls if (L["finest"] if L["finest"] is not None
                                    else "?") == c]
            cells.append(f"{len(cs)}/{len({L['file'] for L in cs})}"
                         if cs else "")
        rows.append((band_label(bi), cells,
                     sum(L["bytes_paged"] for L in ls) / 1e6))
    return [("band", [f"mip {c}" if c != "?" else "? mip" for c in cols],
             0.0)] + rows


def print_header(log: str, A: dict, sel: list[dict], all_packs: bool,
                 by: str) -> None:
    meta, summ, track = A["meta"], A["summary"], A["track"]
    print(f"log {log}: recorder v{meta.get('version', 1)}, scope "
          f"{meta.get('scope')}, stopped {summ.get('stopped', '?')}")
    print(f"DDS loads (open->close): {len(A['loads'])} in all, {len(sel)} "
          f"{'in every pack' if all_packs else 'of the test packs'}; "
          f"distance from the {'camera' if track.camera else 'aircraft'} to "
          f"the square {by}")
    if track.t:
        p0 = track.p[0]
        print(f"positions {len(track.t)}: {hms(track.t[0])}-{hms(track.t[-1])}"
              f" UTC; farthest {max(km(p0[:2], q[:2]) for q in track.p):.1f} "
              f"km from the first; highest {max(q[2] for q in track.p):.0f} m")
    else:
        print("positions: NONE (distances unknown; see section 3 for time)")
    meth = collections.Counter(L["method"] for L in sel)
    print("mip evidence per load: " + ", ".join(f"{k} {v}"
                                                for k, v in meth.most_common()))


def print_bands(sel: list[dict]) -> None:
    print("\n1. loads by distance band x finest mip level "
          "(loads / distinct textures)")
    (_, heads, _), *rows = band_table(sel)
    hdr = (f"{'band':>10} | " + " | ".join(f"{h:>9}" for h in heads)
           + " |  MB paged")
    print(hdr + "\n" + "-" * len(hdr))
    for label, cells, mb in rows:
        print(f"{label:>10} | " + " | ".join(f"{c:>9}" for c in cells)
              + f" | {mb:9.1f}")


def by_texture(sel: list[dict]) -> dict:
    out: dict = collections.OrderedDict()
    for L in sorted(sel, key=lambda L: L["t"]):
        out.setdefault(L["file"], []).append(L)
    return out


def print_textures(by_file: dict, t0: float) -> None:
    def desc(L: dict) -> str:
        d = f"{L['dist']:.1f} km" if L["dist"] is not None else "? km"
        fin = L["finest"] if L["finest"] is not None else "?"
        return (f"{hms(L['t'])} (+{(L['t'] - t0) / 60:5.1f} min) at {d:>8}"
                f"  mip {fin!s:>2} [{L['method']}]"
                f"  {L['bytes_paged'] / 1e3:8.0f} kB paged")
    print(f"\n2. textures loaded: {len(by_file)}; loaded more than once: "
          f"{sum(len(v) > 1 for v in by_file.values())}")
    for f, ls in by_file.items():
        print(f"   {f}")
        for L in ls:
            print(f"      {desc(L)}")


def opens_of(ev: list[dict], ext: str) -> list[dict]:
    return [e for e in ev if e.get("kind") == "open"
            and str(e.get("file")).endswith(ext)]


def minute_row(m: int, ls: list[dict], new: int, A: dict, nt: int,
               nd: int) -> str:
    mc = collections.Counter(
        (min(L["finest"], 4) if L["finest"] is not None else "?") for L in ls)
    at = A["track"].at(m * 60 + 30, 40)
    fine = [parse_name(L["file"]) for L in ls
            if L["finest"] is not None and L["finest"] <= 1]
    fine = [s for s in fine if s]
    pos = f"{at[0]:.3f},{at[1]:.3f} {at[2]:.0f} m" if at else ""
    if fine:
        lat = sum((s["north"] + s["south"]) / 2 for s in fine) / len(fine)
        lon = sum((s["west"] + s["east"]) / 2 for s in fine) / len(fine)
        pos += f" | mip<=1 at {lat:.3f},{lon:.3f}"
    mb = sum(L["bytes_paged"] for L in ls) / 1e6
    return (f"   {hms(m * 60)[:5]} | {len(ls):5} {new:4} | {mc[0]:4} "
            f"{mc[1]:4} {mc[2]:4} {mc[3]:4} {mc[4]:5} {mc['?']:4} | "
            f"{mb:6.1f} | {nt:5} {nd:4} | {pos}")


def print_timeline(ev: list[dict], sel: list[dict], by_file: dict,
                   A: dict) -> None:
    print("\n3. timeline per minute (test-pack DDS loads; all-pack .ter/.dsf "
          "opens; MB paged; finest mip reached; position)")
    print(f"   {'UTC':>5} | {'loads':>5} {'new':>4} | {'mip0':>4} {'mip1':>4} "
          f"{'mip2':>4} {'mip3':>4} {'mip4+':>5} {'?':>4} | {'MB':>6} | "
          f"{'.ter':>5} {'.dsf':>4} | position / centre of mip<=1 loads")
    ters, dsfs = opens_of(ev, ".ter"), opens_of(ev, ".dsf")
    if sel or ters:
        ts = [L["t"] for L in sel] + [e["t"] for e in ters]
        seen: set = set()
        for m in range(int(min(ts) // 60), int(max(ts) // 60) + 1):
            ls = [L for L in sel if int(L["t"] // 60) == m]
            new = len({L["file"] for L in ls} - seen)
            seen.update(L["file"] for L in ls)
            print(minute_row(m, ls, new, A,
                             sum(1 for e in ters if int(e["t"] // 60) == m),
                             sum(1 for e in dsfs if int(e["t"] // 60) == m)))
    if by_file:
        print(f"   first squares loaded: {', '.join(list(by_file)[:8])}")
        last = sorted(by_file, key=lambda f: by_file[f][-1]["t"])
        print(f"   last squares loaded:  {', '.join(last[-8:])}")


def reload_steps(by_file: dict) -> collections.Counter:
    """Next load vs previous of the same texture: finer / coarser / same."""
    steps: collections.Counter = collections.Counter()
    for ls in by_file.values():
        seq = [L["finest"] for L in ls]
        for x, y in zip(seq, seq[1:]):  # noqa: B905 (python 3.9)
            if x is None or y is None:
                steps["unknown"] += 1
            else:
                steps["finer" if y < x else ("coarser" if y > x
                                             else "same")] += 1
    return steps


def print_reloads(by_file: dict) -> None:
    gaps = [b["t"] - a["t"] for ls in by_file.values()
            for a, b in zip(ls, ls[1:])]  # noqa: B905 (python 3.9)
    print(f"\n4. re-loads of the same texture: {len(gaps)}")
    if not gaps:
        return
    gb: collections.Counter = collections.Counter()
    for g in gaps:
        gb[next(lab for lim, lab in ((1, "<1 s"), (10, "1-10 s"),
                                     (60, "10-60 s"), (300, "1-5 min"),
                                     (900, "5-15 min"),
                                     (1e12, ">15 min")) if g < lim)] += 1
    print("   gap: " + ", ".join(f"{k} {v}" for k, v in gb.items()))
    print("   next load vs previous (finest mip): " + ", ".join(
        f"{k} {v}" for k, v in reload_steps(by_file).most_common()))
    seqs = collections.Counter(
        " > ".join(str(L["finest"]) if L["finest"] is not None else "?"
                   for L in ls) for ls in by_file.values())
    print("   commonest mip sequences per texture: " + "; ".join(
        f"[{k}] x{v}" for k, v in seqs.most_common(8)))


def print_ter_dsf(ev: list[dict], A: dict, by: str) -> None:
    roots, track = A["roots"], A["track"]
    ters, dsfs = opens_of(ev, ".ter"), opens_of(ev, ".dsf")
    tile_ters = [e for e in ters if e["path"].startswith(roots)]
    print(f"\n5. .ter opens: {len(ters)} ({len({e['path'] for e in ters})} "
          f"distinct files) in all packs; test packs {len(tile_ters)} "
          f"({len({e['path'] for e in tile_ters})} distinct)")
    tg: collections.Counter = collections.Counter()
    by_ter: dict = {}
    for e in ters:
        by_ter.setdefault(e["path"], []).append(e["t"])
    for ts in by_ter.values():
        ts.sort()
        tg[1 + sum(1 for x, y in zip(ts, ts[1:]) if y - x > 5)] += 1  # noqa: B905 (python 3.9)
    print("   open bursts (>5 s apart) per .ter file: " + ", ".join(
        f"{k}x: {v}" for k, v in sorted(tg.items())))
    print("   .dsf opens (grouped by second):")
    grp: dict = collections.OrderedDict()
    for e in dsfs:
        grp.setdefault((int(e["t"]), e["file"]), []).append(e)
    for (t, f), es in grp.items():
        at = track.at(t)
        sq = parse_name(f)
        d = square_distance(sq, at[:2], by) if (sq and at) else None
        tile = sum(1 for e in es if e["path"].startswith(roots))
        print(f"      {hms(t)} {f} in {len(es)} pack(s)"
              f"{' incl. a test pack' if tile else ''}"
              f"{'  %.1f km from the tile centre' % d if d is not None else ''}")


def print_checks(ev: list[dict], sel: list[dict], A: dict) -> None:
    summ, track, dmap = A["summary"], A["track"], A["dmap"]
    print("\n6. checks")
    print(f"   recorder counts: {summ.get('counts', {})}")
    if summ.get("read_unknown_fd_calls"):
        print(f"   reads on fds never seen opened: "
              f"{summ['read_unknown_fd_calls']}")
    errs = [e for e in ev if e.get("kind") == "pos_error"]
    res = [e for e in ev if e.get("kind") == "pos_resumed"]
    if errs:
        print(f"   position errors logged: {len(errs)} (first {hms(errs[0]['t'])}"
              f" {errs[0]['error'][:60]}; last {hms(errs[-1]['t'])} "
              f"{errs[-1]['error'][:60]}); resumed {len(res)} time(s)")
    pg = [(track.t[i - 1], track.t[i]) for i in range(1, len(track.t))
          if track.t[i] - track.t[i - 1] > 5]
    if pg:
        g = max(pg, key=lambda g: g[1] - g[0])
        print(f"   position gaps > 5 s: {len(pg)} (longest "
              f"{g[1] - g[0]:.0f} s from {hms(g[0])})")
    unk = sum(1 for L in sel if L["finest"] is None)
    print(f"   loads with unknown mip: {unk} (cached = no disk I/O: "
          f"{sum(L['method'] == 'cached' for L in sel)})")
    if dmap.unit:
        print(f"   page-in D= calibration: x{dmap.unit} bytes, shift "
              f"{dmap.shift}, fit {dmap.fit:.0%}")
    elif any(e.get("kind") == "disk" for e in ev):
        print("   page-in D= calibration: none fitted (disk method unused)")
    sc = [e for e in ev if e.get("kind") == "start_cache"]
    if sc:
        print(f"   test-pack DDS cached at start: "
              f"{sum(1 for e in sc if e['resident_pages'])} of {len(sc)} files "
              f"({'evicted' if sc[0].get('evicted') else 'NOT evicted'})")


def write_csv(path: str, loads: list[dict]) -> None:
    import csv
    keys = ["t", "file", "tile", "dist", "alt_m", "finest", "method",
            "bytes_paged", "width"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(loads)
    print(f"   wrote {len(loads)} rows to {path}")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("log", help="record_reads.py JSONL log (plain or .gz)")
    p.add_argument("--from", dest="src", choices=("camera", "aircraft"),
                   default="camera", help="distance from the camera "
                   "(default, when logged) or the aircraft")
    p.add_argument("--by", choices=("centre", "edge"), default="centre")
    p.add_argument("--all-packs", action="store_true",
                   help="tables over every pack's DDS, not just the test packs")
    p.add_argument("--csv", help="write one row per load here")
    a = p.parse_args(argv)

    ev = load(a.log)
    A = analyse(ev, a.src, a.by)
    sel = [L for L in A["loads"] if a.all_packs or L["tile"]]
    by_file = by_texture(sel)
    print_header(a.log, A, sel, a.all_packs, a.by)
    print_bands(sel)
    print_textures(by_file, A["t0"])
    print_timeline(ev, sel, by_file, A)
    print_reloads(by_file)
    print_ter_dsf(ev, A, a.by)
    print_checks(ev, sel, A)
    print_thresholds(sel)
    print_frames(A["pos"], sel, hms)
    if a.csv:
        write_csv(a.csv, A["loads"])


if __name__ == "__main__":
    main()
