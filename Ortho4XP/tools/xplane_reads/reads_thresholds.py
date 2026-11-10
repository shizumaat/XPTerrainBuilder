"""Step-up thresholds and frame time from a read log's loads (#1992 spec
section 2.5, the S rule; U10).

A STEP-UP is a load of a texture at a finer mip than its previous load: the
read model says every step up in resolution is a new open (a step down
happens in memory and reads nothing), so the camera distance at a step-up
open is where X-Plane starts wanting that level.  An ENTRY is a texture's
first load in the log, or a load coarser than its previous one (X-Plane had
dropped it while far away): the distance at which the coarsest level wanted
is first read.  Distances are reported in km and in units of S, the
``LOAD_CENTER`` size of the square's .ter, because the step-up distances fit
d_k ~ c_k * S at every zoom level.  Standard library only.
"""
from __future__ import annotations

import collections
import statistics

from reads_textures import load_center_of, parse_name


def pct(sorted_vals: list[float], q: float) -> float:
    """Nearest-rank percentile (index floor(q * (n - 1)))."""
    return sorted_vals[int(q * (len(sorted_vals) - 1))]


def classify_loads(loads: list[dict]) -> list[tuple[str, dict]]:
    """[("step_up" | "entry" | "same", load)] for loads with a known mip and
    distance, judged against the texture's previous load."""
    by_file: dict = collections.defaultdict(list)
    for L in sorted(loads, key=lambda L: L["t"]):
        by_file[L["file"]].append(L)
    out = []
    for ls in by_file.values():
        prev = None
        for L in ls:
            k = L.get("finest")
            if k is not None and L.get("dist") is not None:
                if prev is None or prev.get("finest") is None:
                    kind = "entry" if prev is None else None
                elif k < prev["finest"]:
                    kind = "step_up"
                elif k > prev["finest"]:
                    kind = "entry"
                else:
                    kind = "same"
                if kind:
                    out.append((kind, L))
            prev = L
    return out


def thresholds(loads: list[dict]) -> dict:
    """{(kind, zl, mip): {n, med, p10, p90, S, S_range, S_src, med_S}}
    over the loads' camera distances (km); S in metres (median and range
    over the loads' squares); med_S = the median of distance / own S."""
    groups: dict = collections.defaultdict(list)
    for kind, L in classify_loads(loads):
        sq = parse_name(L["file"])
        if not sq or "zl" not in sq:
            continue
        s, src = load_center_of(L.get("path", ""), sq)
        groups[(kind, sq["zl"], L["finest"])].append((L["dist"], s, src))
    out = {}
    for key, rows in groups.items():
        d = sorted(r[0] for r in rows)
        sizes = sorted(r[1] for r in rows if r[1])
        ratios = [r[0] * 1000 / r[1] for r in rows if r[1]]
        out[key] = {"n": len(d), "med": statistics.median(d),
                    "p10": pct(d, 0.1), "p90": pct(d, 0.9),
                    "S": statistics.median(sizes) if sizes else None,
                    "S_range": (sizes[0], sizes[-1]) if sizes else None,
                    "S_src": collections.Counter(r[2] for r in rows)
                    .most_common(1)[0][0],
                    "med_S": statistics.median(ratios) if ratios else None}
    return out


def print_thresholds(loads: list[dict]) -> dict:
    """Section 7: the step-up table per zoom level and mip."""
    th = thresholds(loads)
    print("\n7. thresholds: camera distance (to the square centre) at the "
          "loads that STEP UP\n   to a mip (finer than the texture's "
          "previous load), and at ENTRY loads\n   (first load, or coarser "
          "than the previous: re-read after a drop); median\n   km "
          "[p10-p90], n, and the median in units of S (the .ter "
          "LOAD_CENTER size)")
    if not th:
        print("   none (no loads with both a mip and a distance)")
        return th
    for zl in sorted({k[1] for k in th}):
        rng = [v["S_range"] for k, v in th.items()
               if k[1] == zl and v["S_range"]]
        src = next(v["S_src"] for k, v in th.items() if k[1] == zl)
        print(f"   ZL{zl}: S = {min(r[0] for r in rng):.0f}-"
              f"{max(r[1] for r in rng):.0f} m (from {src})"
              if rng else f"   ZL{zl}: S unknown")
        for kind in ("step_up", "entry"):
            for mip in sorted(m for (k, z, m) in th if k == kind and z == zl):
                v = th[(kind, zl, mip)]
                inS = f"{v['med_S']:5.2f} S" if v["med_S"] else "   ? S"
                print(f"      {kind:<7} mip {mip}: {v['med']:6.1f} km "
                      f"[{v['p10']:.1f}-{v['p90']:.1f}]  n={v['n']:<4} {inS}")
    rule = collections.defaultdict(list)
    for (kind, _zl, mip), v in th.items():
        if kind == "step_up" and v["med_S"]:
            rule[mip].append((v["n"], v["med_S"]))
    if rule:
        print("   rule d_k = c_k * S, step-ups (n-weighted over zoom levels): "
              + ", ".join(f"c_{m} = {sum(n * c for n, c in r) / sum(n for n, _ in r):.2f}"
                          for m, r in sorted(rule.items())))
    return th


def frame_stats(pos: list[dict], loads: list[dict], worst: int = 5) -> dict:
    """Frame period samples (s) -> summary + the worst samples with the test
    loads within +-1 s of each."""
    fr = [(p["t"], p["frame_s"]) for p in pos
          if isinstance(p.get("frame_s"), (int, float)) and p["frame_s"] > 0]
    if not fr:
        return {}
    v = sorted(f for _, f in fr)
    ts = sorted(L["t"] for L in loads)
    top = sorted(fr, key=lambda x: -x[1])[:worst]
    return {"n": len(v), "med": statistics.median(v), "p90": pct(v, 0.9),
            "max": v[-1],
            "worst": [(t, f, sum(1 for x in ts if abs(x - t) <= 1.0))
                      for t, f in top]}


def print_frames(pos: list[dict], loads: list[dict], hms) -> None:
    """Section 8: frame time (sim/time/framerate_period, 1 Hz samples)."""
    st = frame_stats(pos, loads)
    print("\n8. frame time (sim/time/framerate_period, one sample per "
          "position)")
    if not st:
        print("   not recorded (recorder before v3, or X-Plane did not "
              "publish it)")
        return
    print(f"   {st['n']} samples: median {st['med'] * 1e3:.1f} ms, p90 "
          f"{st['p90'] * 1e3:.1f} ms, max {st['max'] * 1e3:.1f} ms")
    for t, f, n in st["worst"]:
        print(f"      {hms(t)}  {f * 1e3:6.1f} ms  test loads within 1 s: {n}")
