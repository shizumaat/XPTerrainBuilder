"""pass2 scratch: STAGE-1 NULL PAIR on a pickled prelude (prelude.py) with interventions on the twin.
Runs flex.stage_one (pass 1a -> interval -> pass 1b [-> re-widened pass]) twice: the arm, then the
arm + the 30 section-61 (6) ceilings.  Never lands.

usage: p1b.py PROB.pkl NAME [--workers N] [--iv lv1a] [--iv pin:FILE] [--arm noRE] [--save]
  --iv lv1a     : the twin's hold.derive reads the FIRST run's pass-1a levels (and its pass-1a answer
                  is replaced by the first run's) -> is pass 1b's difference the 1a -> 1b derivation?
  --arm noRE    : cross-ring rows dropped (both runs)
  --hook MOD    : python file defining install(ctx) run before the solves (candidate fixes)
"""
import copy
import importlib.util
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

if __name__ == '__main__':
    ROOT = Path.cwd()
    sys.path.insert(0, str(ROOT / 'src'))
    sys.path.insert(0, str(ROOT / 'tools'))
    _spec = importlib.util.spec_from_file_location('v2_solve_replay', ROOT / 'tools' / 'v2_solve_replay.py')
    rep = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(rep)

    import replay_null as N
    import auto_patch_v2.solve.design as D
    from auto_patch_v2.law.tables import design as design_law
    from auto_patch_v2.model.constraints import ConstraintSet
    from auto_patch_v2.solve import Options
    from auto_patch_v2.solve.design_roles import airside_stage_roles
    from auto_patch_v2.solve import design_stage as DS
    from auto_patch_v2.solve import flex

    argv = sys.argv[1:]
    prob_p, name = Path(argv[0]), argv[1]
    workers = int(argv[argv.index('--workers') + 1]) if '--workers' in argv else 9
    ivs = [argv[i + 1] for i, a in enumerate(argv) if a == '--iv']
    arm = argv[argv.index('--arm') + 1] if '--arm' in argv else 'base'
    hook = argv[argv.index('--hook') + 1] if '--hook' in argv else None
    out = prob_p.parent / 'arms'
    out.mkdir(exist_ok=True)
    rep.pool_budget(workers)
    with open(prob_p, 'rb') as fh:
        prob = pickle.load(fh)
    law = prob['law']
    icao = prob['icao']
    ctx = {'prob': prob, 'law': law, 'D': D, 'DS': DS, 'flex': flex}
    if hook:
        hs = importlib.util.spec_from_file_location('hook', hook)
        hm = importlib.util.module_from_spec(hs)
        hs.loader.exec_module(hm)
        hm.install(ctx)
        print(f'[{icao}] hook {hook} installed', flush=True)

    def _s1(pm_x, cs_x):
        d_x, f_x = DS.stage_split(pm_x, cs_x, law)
        lv, sz = {}, {}
        so, rp = D._solve_stage(pm_x, cs_x, law, Options(verbose=False), size_out=sz, drop=d_x,
                                fixed=f_x, levelled_out=lv, stage_roles=airside_stage_roles(law))
        return so, rp, d_x, f_x, lv, sz

    yh = frozenset(getattr(design_law(law), 'yielding_pin_rulings', ()) or ())

    def run(bands, tag, first=None):
        s1 = copy.deepcopy(prob['stage1'])
        if arm == 'noRE':
            keep = [r for r in s1.cs.rows() if 'spec §62 (4)' not in r.source.ruling]
            print(f'  noRE: dropped {len(s1.cs.rows()) - len(keep)} rows', flush=True)
            s1.cs = ConstraintSet.from_rows(keep)
        s1.cs = N.with_bands(s1.cs, bands)
        rec = {}
        orig_derive = type(s1.hold).derive
        orig_yield = flex.yield_stage_one
        if first is not None and 'lv1a' in ivs:
            def derive(self, cs1a, z1a, rw_cols):
                print('  IV lv1a: derive reads the FIRST run\'s pass-1a levels', flush=True)
                return orig_derive(self, cs1a, dict(first['lv1a']), rw_cols)
            type(s1.hold).derive = derive
        t = time.perf_counter()
        try:
            with N.PassTrace() as tr:
                # record pass-1a levels as stage_one hands them to derive
                od = type(s1.hold).derive

                def spy(self, cs1a, z1a, rw_cols):
                    rec['lv1a'] = dict(z1a)
                    r = od(self, cs1a, z1a, rw_cols)
                    res = self.result
                    rec['interval'] = None if res is None else {
                        'fronting': sorted(res.fronting or ()), 'widen': dict(res.widen),
                        'rows': len(res.rows),
                        'rowsig': sorted((type(x).__name__, x.source.ruling[:60], getattr(x, 'v', None),
                                          round(float(getattr(x, 'lo', 0) or 0), 4),
                                          round(float(getattr(x, 'hi', 0) or 0), 4))
                                         for x in res.rows if type(x).__name__ == 'Band')}
                    return r
                type(s1.hold).derive = spy
                got = DS.stage_one_on(s1, law, _s1, yh)
        finally:
            type(s1.hold).derive = orig_derive
        (sol, rp, drop, foreign, lv1, sz), pass1a, yielded, levels, _r, _sr = got
        print(f'[{icao}] {tag} stage 1 {time.perf_counter() - t:.0f} s passes {len(tr.passes)} '
              f'promoted {[p["promoted"] for p in tr.passes]} relaxed {[p["relaxed"] for p in tr.passes]} '
              f'exits {rp.settle_record() if hasattr(rp, "settle_record") else None} '
              f'hard_settled {rp.hard_settled} max {rp.hard_max_violation_m:.4f}', flush=True)
        rec.update(tr=tr, s1=s1, pass1a=pass1a, rp=rp)
        return rec

    A = run((), 'A')
    pm = A['s1'].pm
    bands = N.ceilings(pm, law, A['tr'].passes, 30)
    B = run(bands, 'B', first=A)
    res = {'name': name, 'ivs': ivs, 'arm': arm, 'passes': [len(A['tr'].passes), len(B['tr'].passes)]}
    for k, (pa, pb) in enumerate(zip(A['tr'].passes, B['tr'].passes)):
        m = N.movers(pa['z'], pb['z'], pa['levelled'])
        res[f'pass{k + 1}'] = m
        res[f'worst{k + 1}'] = N.worst_sites(pa['pm'], pa['z'], pb['z'], pa['levelled'], top=10)
        np.savez(out / f'{name}_p{k + 1}.npz', za=pa['z'], zb=pb['z'], levelled=pa['levelled'])
    ia, ib = A.get('interval'), B.get('interval')
    if ia and ib:
        sa, sb = set(map(tuple, ia['rowsig'])), set(map(tuple, ib['rowsig']))
        res['interval'] = {'fronting_only': [len(set(ia['fronting']) - set(ib['fronting'])),
                                              len(set(ib['fronting']) - set(ia['fronting']))],
                           'rows': [ia['rows'], ib['rows']],
                           'band_only': [len(sa - sb), len(sb - sa)],
                           'band_diff_sample': [list(map(str, x)) for x in sorted(sa - sb)[:8]],
                           'widen': [len(ia['widen']), len(ib['widen'])]}
    la, lb = A['lv1a'], B['lv1a']
    d = [abs(la[v] - lb[v]) for v in la if v in lb]
    res['lv1a_worst'] = round(max(d), 6) if d else None
    print(f'[{icao}] P1B {name} ' + ' '.join(f'pass{k + 1} {res[f"pass{k + 1}"]}' for k in range(len(A["tr"].passes)))
          + f' interval {res.get("interval")} lv1a_worst {res["lv1a_worst"]}', flush=True)
    for k in range(len(A['tr'].passes)):
        for w in res[f'worst{k + 1}'][:5]:
            print(f'   p{k + 1}', w)
    with open(out / f'{name}.json', 'w') as fh:
        json.dump(res, fh, indent=1)
    if '--save' in argv:
        with open(out / f'{name}_A.pkl', 'wb') as fh:
            pickle.dump({'lv1a': A['lv1a'], 'interval': A['interval']}, fh)
