"""padspec4 probe: per-platform post-solve record vs the collar's rim relief.

Usage: python platforms_probe.py SIDECAR.axes.json [...]
Prints every platform with released welds or rim relief > 0.02, plus the
refusal reasons, so the no-tilt design can be bounded without a replay.
"""
import json
import sys


def main(paths):
    for p in paths:
        d = json.load(open(p))
        plats = d.get("platforms") or []
        tag = p.split("/")[-1]
        n = len(plats)
        refused = [r for r in plats if r.get("refused") or r.get("refusal") or r.get("reason")]
        held = sum(1 for r in plats if r.get("hold_verdict") == "held")
        resid = sum(1 for r in plats if r.get("hold_verdict") == "residual")
        print(f"\n=== {tag}: platforms {n} held {held} residual {resid} refused {len(refused)}")
        for r in refused:
            print(f"  REFUSED {r.get('ref')}: {r.get('refused') or r.get('refusal') or r.get('reason')}"
                  f" area {r.get('area_m2')}")
        keys = ("hold_verdict", "released", "welded", "released_max_m", "released_spread_m",
                "held_miss_max_m", "held_over_margin", "unheld_contacts", "unheld_miss_max_m",
                "rim_relief_max_m", "collar_m", "collar_why", "needs_split",
                "reach_isect_empty", "reach_gap_m", "reach_lo_binding", "reach_hi_binding",
                "datum_minus_median_m", "conforming", "blocks")
        for r in sorted(plats, key=lambda r: -(r.get("released_max_m") or 0)):
            if (r.get("released") or 0) > 0 or (r.get("rim_relief_max_m") or 0) > 0.02 \
                    or r.get("hold_verdict") == "residual" or (r.get("held_over_margin") or 0):
                row = {k: r.get(k) for k in keys if r.get(k) not in (None, 0, False, [], {})}
                print(f"  {r.get('ref')}: {row}")
        # every key seen once, to know what the record can truthfully say
        if paths.index(p) == 0 and plats:
            ks = set()
            for r in plats:
                ks.update(r.keys())
            print("  KEYS:", sorted(ks))


if __name__ == "__main__":
    main(sys.argv[1:])
