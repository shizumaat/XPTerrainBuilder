"""holering PROBE ARM C2 (scratch; the landing form is a stage_split edit): a held pad's DATUM COLUMN is an
unknown of the airside problem ONLY while the hold's rows name it — in a set carrying no `frontage_hold datum`
Band on it (pass 1a, the holds stripped) the datum vertex is FOREIGN: fixed at its dummy value, every row touching
it dropped.  Wraps solve.design_stage.stage_split (and solve.design's import of it); runs v2_solve_replay's main()."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path('/Users/noah/XPTerrainBuilder/.claude/worktrees/holering/Ortho4XP')
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tools'))
_spec = importlib.util.spec_from_file_location('v2_solve_replay', ROOT / 'tools' / 'v2_solve_replay.py')
rep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rep)
import auto_patch_v2.solve.design as D  # noqa: E402
import auto_patch_v2.solve.design_stage as DS  # noqa: E402
from auto_patch_v2.solve.design_roles import ruling_head  # noqa: E402

HOLD_DATUM_RULING = "structures.building_pad frontage_hold datum"
N = {'calls': 0, 'foreign': 0, 'kept': 0}
_split = DS.stage_split


def split(planar, cs, law):
    drop, fixed = _split(planar, cs, law)
    from auto_patch_v2.model.platform import datum_vertices
    dv = set(datum_vertices(planar, law).values())
    named = {int(b.v) for b in cs.bands if ruling_head(b) == HOLD_DATUM_RULING}
    loose = sorted(v for v in dv if v not in named and v not in fixed)
    fixed = dict(fixed)
    for v in loose:
        dz = planar.vertices[v].dem_z
        fixed[v] = float(dz) if dz is not None else 0.0
    N['calls'] += 1
    N['foreign'] += len(loose)
    N['kept'] += len(dv & named)
    print(f'[PROBE C2] stage split: {len(loose)} datum columns foreign (no hold Band), {len(dv & named)} kept', flush=True)
    return frozenset(fixed), fixed


DS.stage_split = split
D.stage_split = split

if __name__ == '__main__':
    print('[PROBE C2] a datum column is airside only while a hold Band names it', flush=True)
    sys.argv = ['v2_solve_replay.py', *sys.argv[1:]]
    rc = rep.main()
    print(f'[PROBE C2] {N}', flush=True)
    sys.exit(rc)
