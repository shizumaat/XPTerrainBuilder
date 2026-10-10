"""reverify scratch CONTROL ARM: this tree with C2 switched off (R-E alone on the merged base) —
solve.design_stage._unheld_datums returns the empty set, so stage_split is the pre-a4c2b6d9 one.
Runs tools/v2_solve_replay.py's main() from the cwd's tree (cd <tree>/Ortho4XP first)."""
import importlib.util
import sys
from pathlib import Path

if __name__ == '__main__':
    ROOT = Path.cwd()
    sys.path.insert(0, str(ROOT / 'src'))
    sys.path.insert(0, str(ROOT / 'tools'))
    spec = importlib.util.spec_from_file_location('v2_solve_replay', ROOT / 'tools' / 'v2_solve_replay.py')
    rep = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rep)
    import auto_patch_v2.solve.design_stage as DS
    N = {'calls': 0}

    def _none(planar, cs, law, red):
        N['calls'] += 1
        return set()

    DS._unheld_datums = _none
    print('[CONTROL noC2] _unheld_datums stubbed: no datum column is foreign', flush=True)
    sys.argv = ['v2_solve_replay.py', *sys.argv[1:]]
    rc = rep.main()
    print(f'[CONTROL noC2] {N}', flush=True)
    sys.exit(rc)
