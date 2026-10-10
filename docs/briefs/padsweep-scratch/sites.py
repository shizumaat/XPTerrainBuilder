"""sites.py ICAO R LABEL:LAT,LON ... — per site: nodes moved > 0.02 m within R (airside_value_delta's own join) and the
faces within R on main (sw10) and the merged head (sw11) with their level ranges (a read of the graded surfaces)."""
import collections, json, math, sys
from pathlib import Path

S = Path("/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/padsweep")


def faces(G, lat, lon, R):
    V = {v[0]: v for v in G["vertices"]}
    k = 111320.0 * math.cos(math.radians(lat))
    by = collections.defaultdict(list)
    for f in G["faces"]:
        for i in set(f["ring"]) | {i for h in f.get("holes", []) for i in h}:
            if math.hypot((V[i][2] - lon) * k, (V[i][1] - lat) * 110574.0) <= R:
                by[(f["role"], f["ref"])].append(V[i][3])
    return {k_: (len(z), min(z), max(z)) for k_, z in by.items()}


def main(icao, R, sites):
    Gb = json.load(open(f"/tmp/harness/sw10_{icao}.v2/{icao}.graded.json"))
    Ga = json.load(open(f"/tmp/harness/sw11_{icao}.v2/{icao}.graded.json"))
    mv = json.load(open(S / "m" / f"{icao}_avd.json"))["frames"]["row-side"]["moved"]
    for s in sites:
        lab, ll = s.split(":")
        lat, lon = (float(x) for x in ll.split(","))
        k = 111320.0 * math.cos(math.radians(lat))
        near = [m for m in mv if math.hypot((float(m["lon"]) - lon) * k, (float(m["lat"]) - lat) * 110574.0) <= R]
        print(f"== {lab} {lat}, {lon} (R {R} m): {len(near)} nodes moved > 0.02 m, worst {max((m['dz_m'] for m in near), default=0)}"
              f" {collections.Counter(m['family'] for m in near).most_common(4)}")
        fb, fa = faces(Gb, lat, lon, R), faces(Ga, lat, lon, R)
        for key in sorted(set(fb) | set(fa)):
            b, a = fb.get(key), fa.get(key)
            f = lambda t: f"n{t[0]:3d} {t[1]:7.2f}..{t[2]:7.2f}" if t else "       —            "
            print(f"   {key[0]:20s} {key[1][:40]:40s} {f(b)}  ->  {f(a)}")


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]), sys.argv[3:])
