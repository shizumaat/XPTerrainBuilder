"""S1f item 1 — canonical identity join of the +89 within_shape airside
delta between the S1e control (mid+late) and mid-only HECA arms.

Reads both patches through the harness library's own parser
(``check_grade._parse_osm``) — one reader, no private re-parse — and joins
by the 11-decimal lat/lon spelling (canonical identity join; never
proximity).  It DERIVES NO LAW and counts no defects: every row comes
verbatim out of ``census_rows_diff``'s dump.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import check_grade as CG  # noqa: E402


def key(lat, lon):
    return (f"{lat:.11f}", f"{lon:.11f}")


def load(path, anchor=None):
    nodes, ways = CG._parse_osm(Path(path))
    alt = {}
    for w in ways:
        for nid, a in zip(w.nids, w.elevs):
            if a is None:
                continue
            ll = nodes.get(nid)
            if ll is None:
                continue
            alt.setdefault(key(*ll), []).append((a, w.role, w.wid))
    ll_to_m = CG._ll_to_m_factory(nodes, anchor)
    m_of = {}
    for nid, ll in nodes.items():
        m_of[nid] = ll_to_m(ll[0], ll[1])
    return nodes, ways, alt, m_of


def main():
    ctl_p, mid_p, diff_p = sys.argv[1], sys.argv[2], sys.argv[3]
    fam = sys.argv[4] if len(sys.argv) > 4 else "within_shape"
    roles = sys.argv[5] if len(sys.argv) > 5 else "apron|apron"
    d = json.load(open(diff_p))
    rows = [r for r in d["new"]
            if r["family"] == fam and r["roles"] == roles]
    print(f"NEW rows in class {fam}::{roles}: {len(rows)}")

    import json as _j
    anchor = tuple(_j.load(open(mid_p + '.axes.json'))['anchor'])
    _, _, alt_ctl, _ = load(ctl_p, anchor)
    nodes_mid, ways_mid, alt_mid, m_mid = load(mid_p, anchor)
    # metre -> node id index for the mid arm (the arm the rows came from)
    by_m = {}
    for nid, (x, y) in m_mid.items():
        by_m.setdefault((round(x, 2), round(y, 2)), []).append(nid)

    out = []
    unmatched = 0
    for r in rows:
        (xa, ya), (xb, yb) = r["site_m"]
        rec = {"row": r, "ends": []}
        ok = True
        for (x, y) in ((xa, ya), (xb, yb)):
            nids = by_m.get((round(x, 2), round(y, 2)), [])
            if not nids:
                ok = False
                break
            ll = nodes_mid[nids[0]]
            k = key(*ll)
            mid_vals = alt_mid.get(k, [])
            ctl_vals = alt_ctl.get(k, [])
            rec["ends"].append({
                "lat": ll[0], "lon": ll[1],
                "mid": mid_vals[0][0] if mid_vals else None,
                "ctl": ctl_vals[0][0] if ctl_vals else None,
                "mid_n": len(mid_vals), "ctl_n": len(ctl_vals),
                "roles": sorted({v[1] for v in mid_vals}),
            })
        if not ok or len(rec["ends"]) != 2:
            unmatched += 1
            continue
        out.append(rec)
    print(f"joined {len(out)}  unmatched {unmatched}")

    moved_a = moved_b = both = neither = 0
    deltas = []
    for rec in out:
        ea, eb = rec["ends"]
        da = (None if ea["ctl"] is None or ea["mid"] is None
              else round(ea["ctl"] - ea["mid"], 4))
        db = (None if eb["ctl"] is None or eb["mid"] is None
              else round(eb["ctl"] - eb["mid"], 4))
        rec["d_ctl_minus_mid"] = [da, db]
        ma = da is not None and abs(da) > 0.005
        mb = db is not None and abs(db) > 0.005
        if ma and mb:
            both += 1
        elif ma:
            moved_a += 1
        elif mb:
            moved_b += 1
        else:
            neither += 1
        for dd in (da, db):
            if dd is not None and abs(dd) > 0.005:
                deltas.append(abs(dd))
    print(f"endpoint moves (|ctl-mid| > 0.005 m): both {both}  A only "
          f"{moved_a}  B only {moved_b}  neither {neither}")
    if deltas:
        deltas.sort()
        print(f"  moved-endpoint |delta| n={len(deltas)} "
              f"min {deltas[0]:.3f} p50 {deltas[len(deltas)//2]:.3f} "
              f"max {deltas[-1]:.3f}")
    json.dump(out, open(sys.argv[6] if len(sys.argv) > 6
                        else "tmp/s1f/join89_out.json", "w"), indent=1)


if __name__ == "__main__":
    main()
