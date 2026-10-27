"""THE ``--witness`` READ of ``tools/v2_solve_replay.py`` (#1359; spec
``docs/specs/multi-source-terrain-spec.md`` §8): on a capture, every
terrain-witness question the engine asks, its votes, and — with a label
file — the pre-registered bars.

    venv/bin/python tools/v2_solve_replay.py --replay CAP.pkl --witness
        [--witness-labels LABELS.json] [--imagery-dir TILE_DIR ...] [--json OUT]

Imagery: ``--imagery-dir`` built tile folders (read-only), else the
capture's own ``Airport.imagery``, else the cfg's ``custom_scenery_dir``
built tiles (``airport/imagery_read.built_tile_paths``).  CIFP: the
capture's ``inputs.cifp_dir``.  The engine modules answer; this file only
prints and scores (helper of the replay tool; no engine logic here).
Read-only: writes nothing but ``--json``.
"""
from __future__ import annotations

import json
import math
import os
import pickle
import time
from pathlib import Path

__all__ = ["witness_run", "score_q1", "score_q4", "score_q5"]


def _textures(ap, dirs, root: Path):
    from auto_patch_v2.airport.imagery_read import TextureSet, built_tile_paths
    lat0, lon0 = ap.frame.origin
    if dirs:
        paths = []
        for d in dirs:
            paths.extend(r.path for r in TextureSet.from_built_tile(d, lat0, lon0).refs)
        return TextureSet.from_files(paths, lat0, lon0), "imagery-dir"
    if getattr(ap, "imagery", ()):
        return TextureSet.from_files(ap.imagery, lat0, lon0), "capture"
    scen = ""
    cfg = root / "XPTerrainBuilder.cfg"
    if cfg.is_file():
        for ln in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
            if ln.startswith("custom_scenery_dir="):
                scen = ln.split("=", 1)[1].strip()
    return TextureSet.from_files(built_tile_paths(scen, lat0, lon0), lat0, lon0), "built tiles"


def score_q1(records: list[dict], labels: list[dict]) -> dict:
    """Per labelled end: ``right`` when the record dropped CIFP exactly
    where the label says CIFP is not the threshold (``truth`` ``layout``),
    and kept it where the label says ``cifp``; ``neither`` (both sources
    off the visible threshold) and ``unclear`` are listed, not scored."""
    by = {(r["runway"], r["end"]): r for r in records}
    rows, right, n = [], 0, 0
    for lb in labels:
        r = by.get((lb["runway"], lb["end"]))
        if r is None or lb["truth"] not in ("layout", "cifp"):
            continue
        ok = r["dropped"] == (lb["truth"] == "layout")
        rows.append({**lb, "dropped": r["dropped"], "right": ok})
        n += 1
        right += ok
    return {"labelled": n, "right": right, "rows": rows}


def score_q4(reads, agree_m: float) -> dict:
    """Truth = the lidar break; the image edge within ``agree_m`` of it."""
    truth = img = ok = 0
    for er in reads:
        for d, i in zip(er.dem, er.image, strict=True):
            if d is None:
                continue
            truth += 1
            if i is None:
                continue
            img += 1
            ok += abs(d - i) <= agree_m
    return {"truth_stations": truth, "image_read": img,
            "abstain_rate": None if not truth else round(1 - img / truth, 3),
            "agree_rate": None if not img else round(ok / img, 3)}


def score_q5(rows: list[dict]) -> dict:
    """Precision / recall of the answer and of each source's own vote."""
    def pr(pairs):
        tp = sum(1 for a, t in pairs if a == 1 and t)
        fp = sum(1 for a, t in pairs if a == 1 and not t)
        fn = sum(1 for a, t in pairs if a != 1 and t)
        return {"n": len(pairs), "tp": tp, "fp": fp, "fn": fn,
                "precision": None if tp + fp == 0 else round(tp / (tp + fp), 3),
                "recall": None if tp + fn == 0 else round(tp / (tp + fn), 3)}
    lab = [r for r in rows if r.get("truth") is not None]
    out = {"answer": pr([(r["answer"], r["truth"]) for r in lab])}
    for src in ("dem", "imagery"):
        out[src] = pr([(v["value"], r["truth"]) for r in lab for v in r["votes"]
                       if v["source"] == src and "value" in v])
    return out


def witness_run(pkl: Path, labels: Path | None, dirs, json_out: Path | None, root: Path) -> int:
    from auto_patch_v2.airport import cifp as C
    from auto_patch_v2.airport import graded_edge_witness as G
    from auto_patch_v2.airport import portal_witness as P
    from auto_patch_v2.airport import runway_end_witness as W
    from auto_patch_v2.airport.load import _vector_to_xy
    from auto_patch_v2.law import Law
    from auto_patch_v2.planar.overlay import _runway_records
    with pkl.open("rb") as fh:
        cap = pickle.load(fh)
    ap, icao = cap["airport"], cap["icao"]
    law = Law.for_airport(icao)
    lab = json.loads(labels.read_text(encoding="utf-8")) if labels else {}
    cost: dict[str, float] = {}
    t = time.time()
    ts, whence = _textures(ap, dirs, root)
    cost["textures"] = time.time() - t
    print(f"[witness] {icao}: {len(ts)} textures ({whence})")
    cdir = getattr(cap.get("inputs"), "cifp_dir", "") or ""
    path = os.path.join(cdir, f"{icao}.dat")
    cifp = C.read_cifp_runways(path) if os.path.isfile(path) else {}
    t = time.time()
    _ap, q1, q1_lines = W.witness_runway_ends(ap, cifp, _vector_to_xy(ap.frame), ts, law)
    cost["q1"] = time.time() - t
    for r in q1:
        vs = "; ".join(f"{v['source']} {v.get('value', 'abstain: ' + v.get('abstain', ''))}"
                       for v in r["votes"])
        print(f"[witness] {icao} Q1 RWY {r['end']}: {r['status']} -> "
              f"{'CIFP DROPPED' if r['dropped'] else 'kept'} | {vs}")
    t = time.time()
    recs4 = _runway_records(ap, law)
    reads = G.read_edges(ap, law, recs4, ts)
    cost["q4"] = time.time() - t
    q4 = score_q4(reads, law.tables.terrain_witness.q4.agree_m)
    print(f"[witness] {icao} Q4: {q4}")
    # what the 26w / 26z / 27a rule would do with these reads (not wired)
    moves = G.decide_edges(ap, law, reads)
    for ln in moves.lines:
        print(ln)
    t = time.time()
    to_xy, to_ll = ap.frame.transformers()
    sites = [(xy, wid, kind) for xy, wid, kind in P.mapped_mouths(ap)]
    sites += [(to_xy(s["lon"], s["lat"]), "label", s.get("name", ""))
              for s in lab.get("q5_sites", ())]
    q5 = []
    for xy, wid, kind in sites:
        votes, dec, depth, floor = P.mouth_votes(ap, xy, ts, law)
        lat, lon = to_ll(*xy)
        q5.append({"lat": round(lat, 9), "lon": round(lon, 9), "way": wid, "kind": kind,
                   "answer": dec.answer, "status": dec.status,
                   "depth_m": None if depth is None else round(depth, 2),
                   "floor_m": None if floor is None else round(floor, 2),
                   "votes": dec.record(votes)["votes"], "truth": None})
    cost["q5"] = time.time() - t
    for lb in lab.get("q5", ()):
        best = min(q5, key=lambda r: math.hypot((r["lat"] - lb["lat"]) * 111e3,
                                                (r["lon"] - lb["lon"]) * 111e3
                                                * math.cos(math.radians(lb["lat"]))), default=None)
        if best is not None:
            best["truth"], best["whence"] = lb["truth"], lb.get("whence", "")
    for r in q5:
        print(f"[witness] {icao} Q5 {r['lat']:.7f},{r['lon']:.7f} {r['kind']}: answer "
              f"{r['answer']} ({r['status']}) depth {r['depth_m']} floor {r['floor_m']} "
              f"truth {r['truth']}")
    out = {"icao": icao, "imagery": whence, "textures": len(ts), "decodes": ts.decodes,
           "cost_s": {k: round(v, 2) for k, v in cost.items()}, "q1": q1, "q1_lines": q1_lines,
           "q4": q4, "q4_moves": moves.records,
           "q4_edges": [{"runway": e.ref, "side": e.side, "dem": e.dem, "image": e.image}
                        for e in reads], "q5": q5}
    if lab:
        out["score"] = {"q1": score_q1(q1, lab.get("q1", [])), "q5": score_q5(q5)}
        print(f"[witness] {icao} SCORE Q1 {out['score']['q1']['right']}/"
              f"{out['score']['q1']['labelled']} right; Q5 {out['score']['q5']}")
    print(f"[witness] {icao} cost {out['cost_s']} (decodes {ts.decodes})")
    if json_out:
        json_out.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    return 0
