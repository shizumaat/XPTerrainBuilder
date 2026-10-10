"""holering PROBE ARM C1 (scratch, never lands as is): a held pad's DATUM COLUMN takes the §61 membrane to its own
WELD contacts — one first-difference row per contact at [design] free_membrane — added BEFORE the level belt (so no
datum column takes a DEM belt).  Wraps solve.design_assemble.apply_level_belt; runs v2_solve_replay's main()."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path('/Users/noah/XPTerrainBuilder/.claude/worktrees/holering/Ortho4XP')
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tools'))
_spec = importlib.util.spec_from_file_location('v2_solve_replay', ROOT / 'tools' / 'v2_solve_replay.py')
rep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rep)
import auto_patch_v2.solve.design_assemble as DA  # noqa: E402
from auto_patch_v2.law.tables import design as design_law  # noqa: E402

N = {'rows': 0, 'calls': 0}
_belt = DA.apply_level_belt


def _datum_welds(planar, law):
    from auto_patch_v2.model.platform import datum_vertices, stage_air_vertices
    air = stage_air_vertices(planar, law)
    dv = datum_vertices(planar, law, air)
    own: dict = {}
    for f in planar.faces.values():
        r = str(f.ref)
        if r in dv:
            vs = own.setdefault(r, set())
            for ring in (f.ring, *f.holes):
                vs.update(planar.ring_vertices(ring))
    return {r: (d, sorted(own[r] & air)) for r, d in dv.items()}


def belt_plus(pm, rows, body, red, one, weight):
    k = 0
    law = N.get('law')
    if law is not None:
        w = float(design_law(law).free_membrane)
        for r, (d, welds) in _datum_welds(pm, law).items():
            if red.col[d] < 0:
                continue
            for u in welds:
                if red.col[u] >= 0:
                    k += bool(rows.add(((d, 1.0), (u, -1.0)), 0.0, w, ('datum_membrane', d)))
    N['rows'] += k
    N['calls'] += 1
    print(f'[PROBE C1] datum membrane rows +{k} (call {N["calls"]})', flush=True)
    return _belt(pm, rows, body, red, one, weight)


DA.apply_level_belt = belt_plus

# the law is not an argument of apply_level_belt: catch it at assemble
_assemble = DA.assemble


def assemble_plus(planar, cs, law, rep_, **kw):
    N['law'] = law
    return _assemble(planar, cs, law, rep_, **kw)


DA.assemble = assemble_plus
import auto_patch_v2.solve.design as D  # noqa: E402
D.assemble = assemble_plus

if __name__ == '__main__':
    print('[PROBE C1] datum column membrane to its weld contacts', flush=True)
    sys.argv = ['v2_solve_replay.py', *sys.argv[1:]]
    rc = rep.main()
    print(f'[PROBE C1] {N["rows"]} datum membrane rows over {N["calls"]} assemblies', flush=True)
    sys.exit(rc)
