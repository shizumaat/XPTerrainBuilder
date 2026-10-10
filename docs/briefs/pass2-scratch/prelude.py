"""holering scratch: the replay's PRELUDE once (capture -> classify -> planar -> constraints -> the
ribbon-free stage-1 problem), pickled so pass-1a arms re-solve without paying for it.
usage: prelude.py ICAO OUT.pkl [--workers N]"""
import importlib.util
import pickle
import sys
import time
from pathlib import Path

ROOT = Path('/Users/noah/XPTerrainBuilder/.claude/worktrees/pass2/Ortho4XP')
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tools'))
_spec = importlib.util.spec_from_file_location('v2_solve_replay', ROOT / 'tools' / 'v2_solve_replay.py')
rep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rep)

CAP = Path('/Users/noah/XPTerrainBuilderData/.harness/frames/pads67')


def main(icao: str, out: Path, workers: int) -> None:
    rep.pool_budget(workers)
    t = time.perf_counter()
    prob = rep.replay_problem(CAP / f'{icao}.pkl', 'classify', [], gap_free=True)
    print(f'[{icao}] prelude {time.perf_counter() - t:.0f} s; stage1 {prob["stage1"] is not None}')
    keep = {k: prob[k] for k in ('icao', 'airport', 'pm', 'law', 'cs', 'stage1')}
    with open(out, 'wb') as fh:
        pickle.dump(keep, fh, protocol=pickle.HIGHEST_PROTOCOL)
    print(f'[{icao}] wrote {out} ({out.stat().st_size / 1e6:.0f} MB)')


if __name__ == '__main__':
    a = sys.argv[1:]
    w = int(a[a.index('--workers') + 1]) if '--workers' in a else 4
    main(a[0], Path(a[1]), w)
