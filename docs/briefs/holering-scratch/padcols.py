"""holering scratch: WHO are the pass-1a pad-only columns and what rows do they carry?
usage: padcols.py PROB.pkl ARMS_DIR/base.npz"""
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import p1a  # noqa: E402
from auto_patch_v2.solve import design_assemble as DA  # noqa: E402
from auto_patch_v2.solve.design_report import DesignReport  # noqa: E402
from auto_patch_v2.solve.design_roles import airside_stage_roles, ruling_head  # noqa: E402
from auto_patch_v2.solve.design_stage import stage_split  # noqa: E402


def main(prob_p: Path, npz: Path) -> None:
    p1a.rep.pool_budget(2)
    prob = p1a.load(prob_p)
    s1, law = prob['stage1'], prob['law']
    pm = s1.pm
    cls = p1a.classes(pm, law)
    d = np.load(npz)
    za, zb, lv = d['za'], d['zb'], set(d['levelled'].tolist())
    cs1a = p1a.cs_pass1a(prob)
    with s1.scope():
        d_x, f_x = stage_split(pm, cs1a, law)
        base = DA.assemble(pm, cs1a, law, DesignReport(), drop=d_x, fixed=f_x,
                           stage_roles=airside_stage_roles(law))
    red = base.red
    # column -> vertices of its class (the reduction's union-find)
    members: dict[int, list[int]] = {}
    for v in range(len(pm.vertices)):
        c = int(red.col[v])
        if c >= 0:
            members.setdefault(c, []).append(v)
    R = np.asarray(base.rows.r); C = np.asarray(base.rows.c)
    owners_by_col: dict[int, Counter] = {}
    for k, c in zip(R.tolist(), C.tolist()):
        o = base.rows.owner[k]
        owners_by_col.setdefault(c, Counter())[o[0] if isinstance(o, tuple) else str(o)] += 1
    one_by_v: dict[int, Counter] = {}
    hard = set(base.hard)
    for i, (terms, hi, row) in enumerate(base.one):
        for v, _c in terms:
            one_by_v.setdefault(v, Counter())[(ruling_head(row), 'HARD' if i in hard else 'soft')] += 1
    from auto_patch_v2.model.platform import datum_vertices
    with s1.scope():
        dv = datum_vertices(pm, law)
    dv_set = set(dv.values())
    pads_lv = sorted(set(lv) & cls['pad_only'])
    print(f'levelled pad-only vertices {len(pads_lv)}; datum vertices {len(dv_set)}')
    seen_cols = set()
    for v in pads_lv:
        c = int(red.col[v])
        mem = members.get(c, [])
        roles = Counter(r for u in mem for r in pm.roles_at(u))
        refs = sorted({str(pm.faces[q].ref) for u in mem for q in pm.vertices[u].incident_faces})[:4]
        tag = 'DATUM' if v in dv_set else ''
        print(f'v{v} col {c} dz {zb[v] - za[v]:+.3f} z {za[v]:.2f} dem {pm.vertices[v].dem_z} {tag} group {len(mem)} roles {dict(roles)} refs {refs}')
        if c in seen_cols:
            continue
        seen_cols.add(c)
        print(f'    always-on rows on col: {dict(owners_by_col.get(c, {}))}')
        ones = Counter()
        for u in mem:
            ones.update(one_by_v.get(u, {}))
        print(f'    one-sided rows on group: {dict(ones)}')


if __name__ == '__main__':
    main(Path(sys.argv[1]), Path(sys.argv[2]))
