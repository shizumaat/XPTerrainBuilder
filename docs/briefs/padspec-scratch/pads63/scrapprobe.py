"""pads63 scratch: the surplus PAD pieces of an arrangement and what borders each — the read behind the scrap rule
(planar/pad_sliver.rerole_plateau_scraps).  Runs the replay's own planar prelude and stops at the re-role.
usage: (cd Ortho4XP &&) venv/bin/python ../docs/briefs/padspec-scratch/pads63/scrapprobe.py CAPTURE.pkl [BASEREF]"""
import sys, collections
from pathlib import Path
sys.path.insert(0, "tools"); sys.path.insert(0, "src")
import v2_solve_replay as R
from auto_patch_v2.planar import pad_sliver as PS
from auto_patch_v2.law.tables import is_structure_role, role_side
from auto_patch_v2.model.planar import pad_base_ref, plateau_block_of
from shapely.strtree import STRtree
want = sys.argv[2] if len(sys.argv) > 2 else None
orig = PS.rerole_plateau_scraps
class Done(Exception): pass
def probe(faces, law, counts=None):
    out = orig(faces, law, counts)
    rigid = {r for r, spec in law.tables.precedence.roles.items() if spec.rigid}
    big = {}
    for k, (g, r) in enumerate(out):
        if r.role in rigid and plateau_block_of(r.ref) is None:
            key = (r.role, pad_base_ref(r.ref))
            if key not in big or g.area > out[big[key]][0].area: big[key] = k
    tree = STRtree([g for g, _ in out]); cls = collections.Counter(); m2 = collections.Counter()
    for k, (g, r) in enumerate(out):
        if not (r.role in rigid and plateau_block_of(r.ref) is None) or big[(r.role, pad_base_ref(r.ref))] == k: continue
        base = pad_base_ref(r.ref); nb = collections.Counter(); cov = 0.0
        for j in tree.query(g, predicate="intersects"):
            j = int(j)
            if j == k: continue
            run = g.boundary.intersection(out[j][0].boundary).length
            if run <= 0: continue
            n = out[j][1]; cov += run
            kind = ("own" if pad_base_ref(n.ref) == base and n.role == r.role and plateau_block_of(n.ref) is None else
                    "plateau" if plateau_block_of(n.ref) == base else
                    "structure" if is_structure_role(law, n.role) else f"{role_side(law, n.role)}:{n.role}")
            nb[kind] += run
        sig = "+".join(sorted(nb)) or "nothing"
        cls[sig] += 1; m2[sig] += g.area
        if want is None or base == want:
            print(f"  {str(r.ref):18s} {g.area:8.1f} m2 w {2*g.area/g.length:5.2f} cov {100*cov/g.length:3.0f}% " + ", ".join(f"{a} {b:.1f}" for a, b in nb.most_common()))
    print("surplus pad pieces by what borders them:"); [print(f"   {n:4d}  {m2[s]:9.1f} m2  {s}") for s, n in cls.most_common()]
    raise Done
if __name__ == "__main__":      # pads64: REQUIRED — the work pool SPAWNS, and a spawned worker re-runs an unguarded
    PS.rerole_plateau_scraps = probe   # script top to bottom (pads63's run recursed for 5 h and died rc=1 on a broken pipe)
    try:
        R.replay_problem(Path(sys.argv[1]), "planar", [], None)
    except Done:
        pass
