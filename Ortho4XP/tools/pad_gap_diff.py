#!/usr/bin/env python3
"""THE DRY RULE-2a ARM (issue #73 / owner RULINGS 2026-09-29c/g, promoted
from lane ``garagejoin``'s ``padgap.py`` on its second use — the instrument
the 29g ruling cites).

    venv/bin/python tools/pad_gap_diff.py CAPTURE.pkl [--a 1.0] [--b LAW] [--json OUT]

Over a capture's (``v2_solve_replay --capture``) or ``pack_stage_profile
--pickle``'s PARTITION, re-derive the clusters with THIS tree's code and
mint the derived-pad outlines exactly as ``classify/evidence._pads`` does
(``geom.cluster_outlines``: walled_only, ``cluster_pad_min_m2``, the welded
deck shades, airside=None under ``pad_airside_clip``) at two values of
``[placement] post_bridge_gap_m`` (``--b`` defaults to the shipped law).
Prints both arms' pad count / area / counters, every cluster whose pads
changed, and per merge the pieces joined and their pairwise PLAN GAPS (the
key is PER SIDE: it bridges plan gaps up to twice its value), a piece that
only grew, and a piece that is new (thin-dropped / under-min before).
Solves nothing, prices no law, counts no defects (defect counts come from
``harness/census.py``).  Twin: ``tests/auto_patch_v2/test_lacepad.py``
(``test_73b_*`` and ``test_pad_gap_diff_*``)."""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def mint(cl, ap, law, bridge_m: float):
    """The mint's own call (``classify/evidence._pads``) at one bridge value."""
    from auto_patch_v2.classify.evidence import deck_shades
    from auto_patch_v2.geom import cluster_outlines
    st = law.tables.structures.placement
    to_xy = ap.frame.entry()
    airside = None  # pad_airside_clip: the outline is not pre-cut (evidence._pads)
    return cluster_outlines(cl, to_xy, float(st.footprint_touch_m), airside=airside,
                            walled_only=True, min_m2=float(st.cluster_pad_min_m2),
                            shades=deck_shades(getattr(ap, "partition", None), to_xy),
                            bridge_m=float(bridge_m))


def diff(got_a, got_b, to_ll) -> dict:
    """Per base cluster id: pads and m2 in each arm, merges with their gaps."""
    def per(got):
        d: dict[str, list] = {}
        for pid, _c, poly in got:
            d.setdefault(str(pid).split("/")[0], []).append(poly)
        return d
    pa, pb = per(got_a), per(got_b)
    changed, events = [], []

    def ll(g):
        p = g.representative_point()
        lat, lon = to_ll(p.x, p.y)
        return [round(lat, 7), round(lon, 7)]
    for k in sorted(set(pa) | set(pb)):
        A, B = pa.get(k, []), pb.get(k, [])
        ar = sorted(round(p.area) for p in A)
        br = sorted(round(p.area) for p in B)
        if len(A) == len(B) and ar == br:
            continue
        changed.append({"cluster": k, "pads_a": len(A), "pads_b": len(B),
                        "m2_a": ar, "m2_b": br, "site": ll((B or A)[0])})
        for g in B:
            hit = [p for p in A if p.intersects(g.buffer(0.01))]
            row = {"cluster": k, "m2_b": round(g.area), "site": ll(g),
                   "pieces_m2_a": [round(p.area) for p in hit]}
            if len(hit) > 1:
                row["kind"] = "merge"
                row["gaps_m"] = sorted(round(hit[i].distance(hit[j]), 2)
                                       for i in range(len(hit))
                                       for j in range(i + 1, len(hit)))
            elif len(hit) == 1:
                if abs(g.area - hit[0].area) <= 1.0:
                    continue
                row["kind"] = "grew"
            else:
                row["kind"] = "new"
            events.append(row)
    return {"changed": changed, "events": events}


def run(pkl: Path, a: float, b: float | None) -> dict:
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from auto_patch_v2.law import Law
    from auto_patch_v2.planar.cluster import clusters
    with open(pkl, "rb") as fh:
        d = pickle.load(fh)
    ap, icao = d["airport"], d["icao"]
    law = Law.for_airport(icao)
    st = law.tables.structures.placement
    if b is None:
        b = float(st.post_bridge_gap_m)
    if not bool(st.pad_airside_clip):
        raise SystemExit("pad_gap_diff: pad_airside_clip is off — the mint pre-cuts "
                         "the outline with the airside; this dry arm does not")
    cl = clusters(ap, law)
    ga, ca = mint(cl, ap, law, a)
    gb, cb = mint(cl, ap, law, b)
    out = {"icao": icao, "capture": str(pkl), "a": a, "b": b,
           "arm_a": {"pads": len(ga), "area_m2": round(sum(g.area for *_x, g in ga), 1),
                     "counts": ca},
           "arm_b": {"pads": len(gb), "area_m2": round(sum(g.area for *_x, g in gb), 1),
                     "counts": cb}}
    out.update(diff(ga, gb, ap.frame.transformers()[1]))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("capture", type=Path)
    ap.add_argument("--a", type=float, default=1.0, help="first post_bridge_gap_m (default 1.0)")
    ap.add_argument("--b", type=float, default=None, help="second (default: the shipped law)")
    ap.add_argument("--json", type=Path)
    a = ap.parse_args(argv)
    r = run(a.capture, a.a, a.b)
    ic = r["icao"]
    for arm in ("a", "b"):
        x = r[f"arm_{arm}"]
        print(f"[{ic}] post_bridge_gap_m {r[arm]}: pads {x['pads']} area "
              f"{x['area_m2']:,.0f} m2  post_bridged {x['counts'].get('post_bridged')} "
              f"still_in_pieces {x['counts'].get('still_in_pieces')} "
              f"thin_dropped {x['counts'].get('thin_dropped')}")
    for c in r["changed"]:
        print(f"  CHANGED {c['cluster']}: {c['pads_a']} -> {c['pads_b']} pads, "
              f"m2 {c['m2_a']} -> {c['m2_b']} at {c['site'][0]},{c['site'][1]}")
    for e in r["events"]:
        tail = f" gaps {e['gaps_m']} m" if e["kind"] == "merge" else ""
        print(f"  {e['kind'].upper():5s} {e['cluster']}: {e['pieces_m2_a']} -> "
              f"{e['m2_b']} m2{tail} at {e['site'][0]},{e['site'][1]}")
    print(f"[{ic}] clusters whose pads changed: {len(r['changed'])}")
    if a.json:
        a.json.write_text(json.dumps(r, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
