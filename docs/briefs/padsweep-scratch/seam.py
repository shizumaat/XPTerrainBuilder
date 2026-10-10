"""seam.py GRADED.json LAT LON [R] — the faces and vertex levels within R m of a site: per face role/ref, n vertices
in range, z range, and for each graded_strip vertex which non-strip faces carry it (a read)."""
import collections, json, math, sys


def main(gp, lat, lon, R=14.0):
    G = json.load(open(gp)); V = {v[0]: v for v in G["vertices"]}
    k = 111320.0 * math.cos(math.radians(lat))
    d = lambda i: math.hypot((V[i][2] - lon) * k, (V[i][1] - lat) * 110574.0)
    use = collections.defaultdict(list)
    for f in G["faces"]:
        for i in set(f["ring"]) | {i for h in f.get("holes", []) for i in h}:
            use[i].append(f)
    near = {i for i in V if d(i) <= R}
    by = collections.defaultdict(list)
    for i in near:
        for f in use[i]:
            by[(f["role"], f["ref"], f["id"])].append(i)
    for (role, ref, fid), vs in sorted(by.items(), key=lambda t: t[0]):
        zs = [V[i][3] for i in vs]
        print(f"  {role:18s} {ref:44s} face {fid:5d} n {len(vs):3d} z {min(zs):7.2f}..{max(zs):7.2f}")
    print("  strip vertices within range, nearest first: z, dist, the faces on it")
    for i in sorted((i for i in near if any(f["role"] == "graded_strip" for f in use[i])), key=d)[:22]:
        print(f"    {V[i][1]:.8f}, {V[i][2]:.8f} z {V[i][3]:7.2f} d {d(i):5.1f}  " + " | ".join(sorted(f"{f['role']}:{f['ref']}" for f in use[i]))[:150])


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), *(float(a) for a in sys.argv[4:5]))
