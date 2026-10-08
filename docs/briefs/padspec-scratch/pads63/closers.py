"""pads63 scratch (the read §57 (3) leaves owed): for each RELEASED frontage contact of a block, the hard rows that
stand between it and the block's datum — every row naming the contact that the solved surface would violate were the
contact AT the datum (first order: the other ends at their solved levels), by ruling head, with the other end's roles.
usage: closers.py SOLVED.pkl SIDECAR.axes.json [PADREF ...]"""
import pickle, json, sys, collections
sys.path.insert(0, "src")
from auto_patch_v2.model.constraints import Diff, Band, Pin
sv = pickle.load(open(sys.argv[1], "rb")); sc = json.load(open(sys.argv[2])); want = set(sys.argv[3:])
pm = sv.get("pm_s1") or sv["pm"]; cs = sv.get("cs_s1") or sv["cs"]; z = sv["z"]
pm_full = sv["pm"]
key2v = {tuple(round(float(x), 11) for x in v.key): i for i, v in (pm.vertices.items() if isinstance(pm.vertices, dict) else enumerate(pm.vertices))}
kf = {tuple(round(float(x), 11) for x in v.key): i for i, v in (pm_full.vertices.items() if isinstance(pm_full.vertices, dict) else enumerate(pm_full.vertices))}
def zof(v):
    k = tuple(round(float(x), 11) for x in pm.vertices[v].key); return float(z[kf[k]])
def roles(v):
    return sorted({pm.faces[f].role for f in pm.vertices[v].incident_faces})
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import design as _dl
HARD = frozenset(_dl(Law.for_airport(sv["icao"])).hard_rulings)
head = lambda r: r.source.ruling.split(" (")[0].strip()
inc = collections.defaultdict(list)
for d in cs.diffs:
    if head(d) not in HARD: continue
    inc[int(d.a)].append(d); inc[int(d.b)].append(d)
bands = collections.defaultdict(list)
for b in cs.bands:
    if head(b) in HARD: bands[int(b.v)].append(b)
pins = {int(p.v): p for p in cs.pins}
for p in sc["platforms"]:
    if not p.get("released") or (want and p["ref"] not in want): continue
    D = float(p["datum"]); tot = collections.Counter(); worst = {}
    print(f"== {p['ref']} datum {D} released {p['released']} max {p['released_max_m']}")
    for ll in p["released_ll"]:
        c = key2v.get(tuple(round(float(x), 11) for x in ll))
        if c is None: print("   contact not on the stage-1 map", ll); continue
        zc = zof(c); rows = []
        for d in inc[c]:
            q = int(d.b) if int(d.a) == c else int(d.a)
            if q == c: continue
            sgn = 1.0 if int(d.a) == c else -1.0
            ex = abs((D - zof(q)) * 1.0 - sgn * float(getattr(d, "rel", 0.0))) - float(d.cap) * float(d.d)
            if ex > 0.005: rows.append((ex, head(d), d.source.generator, q, float(d.d), float(d.cap)))
        for b in bands[c]:
            ex = max((b.lo - D) if b.lo is not None else -9, (D - b.hi) if b.hi is not None else -9)
            if ex > 0.005: rows.append((ex, head(b), b.source.generator, c, 0.0, 0.0))
        if c in pins and abs(pins[c].z - D) > 0.005: rows.append((abs(pins[c].z - D), head(pins[c]), pins[c].source.generator, c, 0.0, 0.0))
        rows.sort(reverse=True)
        print(f"   contact {ll} z {zc:.3f} (D{zc - D:+.3f}) roles {roles(c)}: {len(rows)} rows would break at D of {len(inc[c])} diffs")
        for ex, h, g, q, d, cap in rows[:4]:
            print(f"      +{ex:.3f} m  {g} | {h} | d {d:.1f} cap {100*cap:.2f}% -> other end z {zof(q):.3f} {roles(q)} {'PIN' if q in pins else ''} at {list(pm.vertices[q].key)}")
        for ex, h, g, q, d, cap in rows:
            tot[h] += 1; worst[h] = max(worst.get(h, 0.0), ex)
    print("   by head:", {h: (n, round(worst[h], 3)) for h, n in tot.most_common(10)})
