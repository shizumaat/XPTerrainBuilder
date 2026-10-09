"""lane valleyspec probe 0 (offline, no replay): WHO are the stage-1 columns no
level term names, by the law that COULD name them — their taxi face's own
centreline chain (short / long / none / out of reach / shared with a value
surface).  Joins the pass-1a QP dump (k_dump/qp_0_0.pkl: col, owner, U) to the
control's solved pickle (pm_s1) by vertex index (same capture, same tree).

  freeclass.py QPDUMP SOLVED.pkl ICAO
"""
import collections, pickle, sys
import numpy as np

sys.path.insert(0, "/Users/noah/XPTerrainBuilder/.claude/worktrees/valleyspec/Ortho4XP/src")
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import is_value_role
from auto_patch_v2.constraints import taxi_trend as TT


def free_columns(q):
    own = [o[0] if o else "other" for o in q["owner"]]
    A0 = q["A0"].tocoo()
    has = collections.defaultdict(set)
    for r, c in zip(A0.row, A0.col):
        has[int(c)].add(own[r])
    U = q["U"]
    in_u = set(U.tocoo().col.tolist()) if U is not None else set()
    n = q["A0"].shape[1]
    return [c for c in range(n) if has[c] <= {"bend"} and c not in in_u], n


def foot(pm, chain, v):
    xy = np.asarray([pm.vertices[u].xy for u in chain.vertices], float)
    A, B = xy[:-1], xy[1:]
    D = B - A
    LL = np.einsum("ij,ij->i", D, D); LL = np.where(LL > 0, LL, 1.0)
    p = np.asarray(pm.vertices[v].xy, float)
    t = np.clip(((p - A) * D).sum(1) / LL, 0, 1)
    rel = p - (A + t[:, None] * D)
    d2 = (rel * rel).sum(1)
    j = int(np.argmin(d2))
    return float(np.sqrt(d2[j])), j, float(t[j])


def main():
    qp, solved, icao = sys.argv[1:4]
    q = pickle.load(open(qp, "rb"))
    sv = pickle.load(open(solved, "rb"))
    pm = sv["pm_s1"] if sv.get("pm_s1") is not None else sv["pm"]
    law = Law.for_airport(icao)
    free, n = free_columns(q)
    col = q["col"]
    rep = {}
    for v, c in enumerate(col):
        if c >= 0:
            rep.setdefault(int(c), v)
    taxi = frozenset(law.tables.precedence.taxi_family.members)
    window = float(law.tables.emit.design.runway_profile_window_m)
    reach = float(law.tables.emit.design.taxi_trend_face_reach_m)
    chains = TT._chains(pm, law)
    owner = TT.chain_of_face(pm, law, chains)
    print(f"{icao}: stage-1 columns {n}; FREE (bend-only, no body datum) {len(free)}; chains {len(chains)} "
          f"(long >= {0.5*window:.0f} m: {sum(1 for c in chains if c.length_m >= 0.5*window)})")
    cls = collections.Counter(); roles_by = collections.defaultdict(collections.Counter)
    dist_short = []
    for c in free:
        v = rep[c]
        roles = pm.roles_at(v)
        rkey = "+".join(sorted(roles))
        tfaces = [f for f in pm.vertices[v].incident_faces if pm.faces[f].role in taxi]
        shared_value = any(r not in taxi and is_value_role(law, r) for r in roles)
        if not tfaces:
            k = "not taxi-family"
        elif shared_value:
            k = "taxi shared with a VALUE role (apron/runway): excluded by §8.6.1"
        else:
            owned = [owner[f] for f in tfaces if f in owner]
            if not owned:
                k = "taxi face with NO chain"
            else:
                best = None
                for i in set(owned):
                    d, j, t = foot(pm, chains[i], v)
                    if best is None or d < best[0]:
                        best = (d, i)
                d, i = best
                L = chains[i].length_m
                if d > reach:
                    k = f"owned face, foot beyond reach {reach:.0f} m"
                elif L >= 0.5 * window:
                    k = "LONG chain, foot in reach (why free? trend None / pin?)"
                else:
                    k = "SHORT chain (< half window), foot in reach"
                    dist_short.append(d)
        cls[k] += 1
        roles_by[k][rkey] += 1
    for k, nn in cls.most_common():
        print(f"  {nn:5d}  {k}")
        for r, m in roles_by[k].most_common(6):
            print(f"           {m:5d} {r}")
    if dist_short:
        a = np.array(dist_short)
        print(f"  short-chain feet: median {np.median(a):.1f} m, p90 {np.percentile(a, 90):.1f}, max {a.max():.1f}")


if __name__ == "__main__":
    main()
