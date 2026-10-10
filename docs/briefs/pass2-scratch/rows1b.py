"""pass2 scratch: WHAT HOLDS THE MOVER COLUMNS in a given stage-1 pass.
Runs flex.stage_one once on the prelude, keeps each pass's (pm, cs, z), assembles pass K's problem and prints,
for the movers of a p1b.py pair (arms/NAME_pK.npz), the rows on their columns.

usage: rows1b.py PROB.pkl NAME PASS [--top N] [--workers N] [--hook MOD]
"""
import copy
import importlib.util
import pickle
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

if __name__ == '__main__':
    ROOT = Path.cwd()
    sys.path.insert(0, str(ROOT / 'src'))
    sys.path.insert(0, str(ROOT / 'tools'))
    _spec = importlib.util.spec_from_file_location('v2_solve_replay', ROOT / 'tools' / 'v2_solve_replay.py')
    rep = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(rep)
    import auto_patch_v2.solve.design as D
    import auto_patch_v2.solve.design_assemble as DA
    from auto_patch_v2.law.tables import design as design_law
    from auto_patch_v2.solve import Options
    from auto_patch_v2.solve.design_report import DesignReport
    from auto_patch_v2.solve.design_roles import airside_stage_roles
    from auto_patch_v2.solve import design_stage as DS
    from auto_patch_v2.solve.rows import _level_row_columns

    argv = sys.argv[1:]
    prob_p, name, K = Path(argv[0]), argv[1], int(argv[2])
    top = int(argv[argv.index('--top') + 1]) if '--top' in argv else 8
    workers = int(argv[argv.index('--workers') + 1]) if '--workers' in argv else 9
    rep.pool_budget(workers)
    with open(prob_p, 'rb') as fh:
        prob = pickle.load(fh)
    law, icao = prob['law'], prob['icao']
    if '--hook' in argv:
        hs = importlib.util.spec_from_file_location('hook', argv[argv.index('--hook') + 1])
        hm = importlib.util.module_from_spec(hs)
        hs.loader.exec_module(hm)
        hm.install({'prob': prob, 'law': law})
    calls = []

    def _s1(pm_x, cs_x):
        d_x, f_x = DS.stage_split(pm_x, cs_x, law)
        lv, sz = {}, {}
        so, rp = D._solve_stage(pm_x, cs_x, law, Options(verbose=False), size_out=sz, drop=d_x,
                                fixed=f_x, levelled_out=lv, stage_roles=airside_stage_roles(law))
        calls.append({'pm': pm_x, 'cs': cs_x, 'z': np.asarray(so.z, float), 'drop': d_x, 'fixed': f_x, 'lv': lv})
        return so, rp, d_x, f_x, lv, sz

    yh = frozenset(getattr(design_law(law), 'yielding_pin_rulings', ()) or ())
    s1 = copy.deepcopy(prob['stage1'])
    DS.stage_one_on(s1, law, _s1, yh)
    print(f'[{icao}] stage 1: {len(calls)} solve call(s)', flush=True)
    c = calls[K - 1]
    pm, cs, z = c['pm'], c['cs'], c['z']
    with s1.scope():
        base = DA.assemble(pm, cs, law, DesignReport(), drop=c['drop'], fixed=c['fixed'],
                           stage_roles=airside_stage_roles(law))
    red = base.red
    R = np.asarray(base.rows.r); C = np.asarray(base.rows.c); V = np.asarray(base.rows.v)
    Bv = np.asarray(base.rows.b)
    nrow = int(R.max()) + 1 if R.size else 0
    owners = base.rows.owner
    lev = _level_row_columns(base.rows, base.body, red.n_cols)
    # per-column: sum of squares of two-sided coefficients (the diagonal of A0'A0) by owner head
    diag = np.zeros(red.n_cols)
    np.add.at(diag, C, V * V)
    rows_of_col = defaultdict(list)
    for k, (r, cc) in enumerate(zip(R.tolist(), C.tolist())):
        rows_of_col[cc].append(k)
    one_of_v = defaultdict(list)
    hard = set(base.hard)
    for i, (terms, hi, row) in enumerate(base.one):
        for v, _c in terms:
            one_of_v[v].append(i)
    npz = np.load(prob_p.parent / 'arms' / f'{name}_p{K}.npz')
    za, zb, among = npz['za'], npz['zb'], npz['levelled']
    d = zb[among] - za[among]
    order = np.argsort(-np.abs(d))
    movers = [int(among[i]) for i in order if abs(d[i]) > 0.02]
    print(f'[{icao}] pass {K}: {len(movers)} movers > 0.02; columns {red.n_cols}; unlevelled columns {int((~lev).sum()) if lev.dtype == bool else "?"}')
    mcols = Counter(int(red.col[v]) for v in movers)
    print(f'  mover columns: {len(mcols)} distinct (fixed: {mcols.get(-1, 0)}); levelled {sum(1 for cc in mcols if cc >= 0 and lev[cc])}')
    # what kinds of rows hold the mover columns
    head_two = Counter()
    head_one = Counter()
    re_rows = Counter()
    for v in movers:
        cc = int(red.col[v])
        if cc < 0:
            continue
        for k in rows_of_col[cc]:
            ow = owners[R[k]]
            head_two[str(ow[0]) if isinstance(ow, tuple) else str(ow)[:30]] += 1
        for i in one_of_v[v]:
            terms, hi, row = base.one[i]
            val = sum(cf * z[t] for t, cf in terms) - hi
            tag = 'HARD' if i in hard else 'soft'
            act = 'active' if val > -1e-4 else 'slack'
            head_one[(tag, act, row.source.ruling.split(' (')[0][:60])] += 1
            if '§62 (4)' in row.source.ruling:
                re_rows[(tag, act)] += 1
    print('  two-sided row owners on mover columns:', dict(head_two.most_common(12)))
    print('  R-E (spec §62 (4)) rows on mover vertices:', dict(re_rows))
    print('  one-sided rows on mover vertices:')
    for kk, n in head_one.most_common(24):
        print('     ', n, kk)
    for v in movers[:top]:
        cc = int(red.col[v])
        faces = [pm.faces[q] for q in pm.vertices[v].incident_faces]
        print(f'  v{v} {pm.vertices[v].key} dz {zb[v] - za[v]:+.4f} z {z[v]:.3f} col {cc} levelled {bool(lev[cc]) if cc >= 0 else None} '
              f'diag {diag[cc] if cc >= 0 else 0:.3g} roles {[(f.role, str(f.ref)) for f in faces]}')
        seen = set()
        for k in rows_of_col.get(cc, ()):
            r = int(R[k])
            if r in seen:
                continue
            seen.add(r)
            sel = R == r
            cols = C[sel].tolist(); vals = np.round(V[sel], 3).tolist()
            print(f'     ROW {owners[r]!r:.70} n={len(cols)} coef@col={[x for q, x in zip(cols, vals) if q == cc]} sum={sum(vals):+.3f} b={Bv[r]:.3f}')
            if len(seen) > 14:
                print('     ...')
                break
        n1 = 0
        for i in one_of_v.get(v, ()):
            terms, hi, row = base.one[i]
            val = sum(cf * z[t] for t, cf in terms) - hi
            if val < -0.05:
                continue
            n1 += 1
            if n1 > 10:
                print('     ...')
                break
            print(f'     ONE {"HARD" if i in hard else "soft"} viol {val:+.4f} ow={base.one_way.get(i)} {type(row).__name__} '
                  f'{row.source.ruling[:80]!r} terms={[(t, round(cf, 3)) for t, cf in terms][:4]}')
    np.savez(prob_p.parent / 'arms' / f'{name}_p{K}_cols.npz', movers=np.asarray(movers), z=z)
