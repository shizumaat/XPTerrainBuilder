"""row.py ICAO — the padsweep table row of one airport: sw12 (claude/padfix) against sw10 (main).  A READ of the harness
tools' own outputs (census / airside_value_delta / pad_edge_read JSON, the sidecars, result.json); prices no law."""
import collections
import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

S = Path("/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/padfix")
M, H = S / "m", Path("/tmp/harness")
GS_FAM = ("service_road", "groundside_pavement", "parking_lot", "road")


def jl(p):
    return json.loads(Path(p).read_text())


def adjudicated(rows):
    """{(family, side): n} over the rows the census adjudicates (no out_of_scope tag)."""
    c = collections.Counter()
    for r in rows["rows"]:
        if not r.get("out_of_scope") and r["family"] != "drainage_minimum":
            c[(r["family"], r["side"])] += 1
    return c


def edge_classes(p):
    n, m = collections.Counter(), collections.Counter()
    for r in jl(p)["runs"]:
        k = (r.get("source") or {}).get("cls") or ("BARE" if r["cls"] == "B" else "cls:" + r["cls"])
        n[k] += 1
        m[k] += r["length_m"]
    return n, m


def qp_exits(o, path=""):
    out = []
    if isinstance(o, dict):
        if "qp_exits" in o:
            out.append((path or "design", o["qp_exits"], o.get("rounds")))
        for k, v in o.items():
            if k in ("design", "stages", "passes") or path:
                out += qp_exits(v, f"{path}/{k}" if path else k)
    elif isinstance(o, list) and path:
        for i, v in enumerate(o):
            if isinstance(v, dict):
                out += qp_exits(v, f"{path}[{v.get('stage', v.get('name', i))}]")
    return out


def osm_nodes(p):
    """{(lat, lon) spelling: z}, {runway way ref: [node keys]}"""
    z, ways, nid = {}, collections.defaultdict(list), {}
    for ev, el in ET.iterparse(p, events=("end",)):
        if el.tag == "node":
            k = (el.get("lat"), el.get("lon"))
            nid[el.get("id")] = k
            for t in el.findall("tag"):
                if t.get("k") in ("alt_abs",):
                    z[k] = float(t.get("v"))
            if el.get("ele") is not None:
                z[k] = float(el.get("ele"))
            el.clear()
        elif el.tag == "way":
            tags = {t.get("k"): t.get("v") for t in el.findall("tag")}
            if tags.get("o4_role") == "runway" or tags.get("role") == "runway":
                ways[tags.get("o4_ref") or tags.get("ref") or el.get("id")] += [nid[n.get("ref")] for n in el.findall("nd")]
            el.clear()
    return z, ways


def runway_shape(icao, moved):
    """The largest change of the runway's level DELTA over 30 m along its axis, in percentage points, per runway way
    (the shape the move added to the profile); sites over 0.1 pp per 30 m."""
    za, _ = osm_nodes(H / f"sw10_{icao}.osm")
    zb, ways = osm_nodes(H / f"sw12_{icao}.osm")
    out = []
    for ref, keys in ways.items():
        pts = [(float(a), float(b), zb[(a, b)] - za[(a, b)]) for a, b in set(keys) if (a, b) in za and (a, b) in zb]
        if len(pts) < 4 or max(abs(p[2]) for p in pts) <= 0.02:
            continue
        lat0 = sum(p[0] for p in pts) / len(pts)
        lon0 = sum(p[1] for p in pts) / len(pts)
        k = 111320.0 * math.cos(math.radians(lat0))
        xy = [((p[1] - lon0) * k, (p[0] - lat0) * 110574.0, p[2], p[0], p[1]) for p in pts]
        sxx = sum(x * x for x, *_ in xy); syy = sum(y * y for _, y, *_ in xy); sxy = sum(x * y for x, y, *_ in xy)
        th = 0.5 * math.atan2(2 * sxy, sxx - syy)
        ax, ay = math.cos(th), math.sin(th)
        st = sorted((x * ax + y * ay, -x * ay + y * ax, dz, la, lo) for x, y, dz, la, lo in xy)
        worst, sites = 0.0, []
        for i, (s, t, dz, la, lo) in enumerate(st):
            for s2, t2, dz2, la2, lo2 in st[i + 1:]:
                if s2 - s > 35.0:
                    break
                if s2 - s >= 25.0 and abs(t2 - t) < 3.0:
                    g = abs(dz2 - dz) / (s2 - s) * 100.0
                    worst = max(worst, g)
                    if g > 0.1:
                        sites.append((round(g, 3), f"{la:.8f}, {lo:.8f}"))
        out.append((ref, len(pts), round(max(abs(p[2]) for p in pts), 3), round(worst, 3), sorted(sites, reverse=True)[:3], len(sites)))
    return out


def main(icao):
    rb, ra = jl(H / f"sw10_{icao}.result.json"), jl(H / f"sw12_{icao}.result.json")
    print(f"=== {icao}: body {rb['body_sha256'][:12]} -> {ra['body_sha256'][:12]}; status {ra['v2']['status']}; "
          f"patch wall {rb['build_seconds']} -> {ra['build_seconds']} s; rebake plan sha "
          f"{str(rb['v2']['rebake_plan'].get('sha256'))[:12]} -> {str(ra['v2']['rebake_plan'].get('sha256'))[:12]}")
    wa, wb = ra["v2"]["wall_s"], rb["v2"]["wall_s"]
    print("  wall by stage (base -> arm):", ", ".join(f"{k} {wb.get(k, 0):.0f}->{wa[k]:.0f}" for k in wa if abs(wa[k] - wb.get(k, 0)) > 3))
    avd = jl(M / f"{icao}_avd.json")
    for fr in ("row-side", "solve-owned", "structure"):
        f = avd["frames"][fr]
        fam = {k: (v["n"], v["worst_dz_m"]) for k, v in f["families"].items()}
        print(f"  MOVERS {fr}: {f['n_moved']} > 0.02 m, worst {f['worst_dz_m']}; A-only {f['a_only']} B-only {f['b_only']}; {fam}")
    rw = [m for m in avd["frames"]["row-side"]["moved"] if "runway" in m["roles"]]
    print(f"  RUNWAY nodes moved > 0.02 m: {len(rw)}, worst {max((m['dz_m'] for m in rw), default=0)}"
          + (f" @ {max(rw, key=lambda m: m['dz_m'])['lat']}, {max(rw, key=lambda m: m['dz_m'])['lon']}" if rw else ""))
    if rw:
        for r in runway_shape(icao, rw):
            print("    runway way %s: %d joined, worst |dz| %s m, worst shape %s pp / 30 m, sites > 0.1 pp: %d %s" % (r[0], r[1], r[2], r[3], r[5], r[4]))
    for role in ("building",) + GS_FAM:
        g = avd["by_ref"].get(role)
        if g and g["moved"]:
            n = sum(x["moved"] for x in g["moved"])
            print(f"  by-ref {role}: {len(g['moved'])} ref(s), {n} nodes, worst {max(x['worst_m'] for x in g['moved'])}; "
                  f"only in A {len(g['absent_in_b'])}, only in B {len(g['absent_in_a'])}")
    nb, mb = edge_classes(M / f"{icao}_base.edge.json")
    na, ma = edge_classes(M / f"{icao}_arm.edge.json")
    print("  PAD EDGES (runs / m) base -> arm: " + "; ".join(
        f"{k} {nb[k]}/{round(mb[k])} -> {na[k]}/{round(ma[k])}" for k in sorted(set(nb) | set(na))))
    xb, xa = jl(H / f"sw10_{icao}.osm.axes.json"), jl(H / f"sw12_{icao}.osm.axes.json")
    pb = {p["ref"]: p for p in xb.get("platforms", [])}
    pa = {p["ref"]: p for p in xa.get("platforms", [])}
    mv = sorted(((r, pb[r]["datum"], pa[r]["datum"]) for r in pb if r in pa and pb[r].get("datum") is not None
                 and pa[r].get("datum") is not None and abs(pb[r]["datum"] - pa[r]["datum"]) > 0.02), key=lambda t: -abs(t[1] - t[2]))
    held = [p for p in pa.values() if p.get("hold_verdict") == "held"]
    off = [(p["ref"], p.get("held_miss_max_m")) for p in held if (p.get("held_miss_max_m") or 0) > 0.02]
    hv = collections.Counter(p.get("hold_verdict") for p in pa.values())
    hvb = collections.Counter(p.get("hold_verdict") for p in pb.values())
    print(f"  PLATFORMS {len(pb)} -> {len(pa)}; hold verdicts {dict(hvb)} -> {dict(hv)}; datums moved > 0.02 m: {len(mv)}; "
          f"10 largest {[(r, round(a, 2), round(b, 2)) for r, a, b in mv[:10]]}")
    print(f"    held pads {len(held)}: datum off its held contact > 0.02 m: {len(off)} {sorted(off, key=lambda t: -t[1])[:6]}; "
          f"tilted (tilt_pct > 0.05): base {sum(1 for p in pb.values() if (p.get('tilt_pct') or 0) > 0.05)} -> arm "
          f"{[(p['ref'], p['tilt_pct']) for p in pa.values() if (p.get('tilt_pct') or 0) > 0.05][:8]}")
    hb = collections.Counter(r.get("tier") for r in xb.get("hard_conflict", []))
    ha = collections.Counter(r.get("tier") for r in xa.get("hard_conflict", []))
    print(f"  HARD_CONFLICT by tier: {dict(sorted(hb.items()))} -> {dict(sorted(ha.items()))}")
    cb, ca = jl(M / f"{icao}_base.census.json"), jl(M / f"{icao}_arm.census.json")
    print(f"  CENSUS law-true total {cb['lawtrue']['total']} -> {ca['lawtrue']['total']}; ADJUDICATED airside-for-acceptance "
          f"{cb['adjudicated_airside_for_acceptance']} -> {ca['adjudicated_airside_for_acceptance']}; by side "
          f"{cb['adjudication']['adjudicated_by_side']} -> {ca['adjudication']['adjudicated_by_side']}")
    ab, aa = adjudicated(jl(M / f"{icao}_base.rows.json")), adjudicated(jl(M / f"{icao}_arm.rows.json"))
    fams = sorted({k[0] for k in ab} | {k[0] for k in aa})
    for f in fams:
        b = [ab[(f, s)] for s in ("airside", "mixed", "groundside")]
        a = [aa[(f, s)] for s in ("airside", "mixed", "groundside")]
        if a != b:
            flag = "  RISES AIRSIDE" if a[0] + a[1] > b[0] + b[1] else ""
            print(f"    {f:28s} air/mixed/gs {b[0]}/{b[1]}/{b[2]} -> {a[0]}/{a[1]}/{a[2]}  (air+mixed {a[0] + a[1] - b[0] - b[1]:+d}, gs {a[2] - b[2]:+d}){flag}")
    for kind in ("critical_motion", "critical_visual"):
        kb, ka = cb["cockpit"][kind], ca["cockpit"][kind]
        d = {f: (kb["by_family"].get(f, 0), ka["by_family"].get(f, 0)) for f in sorted(set(kb["by_family"]) | set(ka["by_family"]))
             if kb["by_family"].get(f, 0) != ka["by_family"].get(f, 0)}
        hp = (kb["by_family"].get("hairline_pair", 0), ka["by_family"].get("hairline_pair", 0))
        print(f"  {kind.upper()}: {kb['n']} -> {ka['n']}; without hairline_pair {kb['n'] - hp[0]} -> {ka['n'] - hp[1]}; "
              f"hairline_pair {hp[0]} -> {hp[1]} ({hp[1] - hp[0]:+d}); families changed {d}")
    for nm, x in (("base", xb), ("arm", xa)):
        q = qp_exits(x)
        tot = collections.Counter()
        for _p, e, _r in q:
            tot.update(e)
        print(f"  QP exits {nm}: total {dict(tot)}; " + "; ".join(f"{p} {e}" for p, e, _r in q if "round_cap" in e or len(q) <= 6))
    nl = S / "null" / f"{icao}.log"
    if nl.is_file():
        for ln in nl.read_text().splitlines():
            if "NULL-CHANGE" in ln or "null-change" in ln:
                print("  ", ln.strip()[:400])


if __name__ == "__main__":
    for a in sys.argv[1:]:
        main(a)
