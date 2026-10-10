"""holering scratch: PASS-1a ARMS on a pickled prelude (prelude.py) — the stage-1 problem with the
hold rows stripped, solved once and once more with the §61 (6) null ceilings; movers by vertex class
(apron HOLE RIM / pad-only / runway / other).  Never lands.

usage: p1a.py PROB.pkl ARM [--workers N] [--out DIR] [--rows V ...]
ARM: base | noRE | pinrim | <candidate name registered in CANDIDATES>
"""
import dataclasses as _dc
import importlib.util
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path('/Users/noah/XPTerrainBuilder/.claude/worktrees/holering/Ortho4XP')
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tools'))
_spec = importlib.util.spec_from_file_location('v2_solve_replay', ROOT / 'tools' / 'v2_solve_replay.py')
rep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rep)

import replay_null as N  # noqa: E402
import auto_patch_v2.solve.design as D  # noqa: E402
import auto_patch_v2.solve.design_assemble as DA  # noqa: E402
from auto_patch_v2.law.tables import design as design_law  # noqa: E402
from auto_patch_v2.model.constraints import ConstraintSet, Pin, Source  # noqa: E402
from auto_patch_v2.solve import Options  # noqa: E402
from auto_patch_v2.solve.design_report import DesignReport  # noqa: E402
from auto_patch_v2.solve.design_roles import airside_stage_roles  # noqa: E402
from auto_patch_v2.solve.design_stage import stage_split  # noqa: E402
from auto_patch_v2.solve.flex import yield_stage_one  # noqa: E402

CANDIDATES: dict = {}   # name -> hook(planar, law, rows, red, ctx) adding rows after the membrane


def load(p: Path) -> dict:
    with open(p, 'rb') as fh:
        return pickle.load(fh)


def solve1_factory(law):
    def _s1(pm_x, cs_x):
        d_x, f_x = stage_split(pm_x, cs_x, law)
        lv: dict = {}
        sz: dict = {}
        so, rp = D._solve_stage(pm_x, cs_x, law, Options(verbose=False), size_out=sz,
                                drop=d_x, fixed=f_x, levelled_out=lv,
                                stage_roles=airside_stage_roles(law))
        return so, rp, d_x, f_x, lv, sz
    return _s1


def cs_pass1a(prob) -> ConstraintSet:
    s1 = prob['stage1']
    return s1.hold.strip(s1.cs) or s1.cs


def pass1a(prob, cs1a: ConstraintSet, bands=()) -> tuple[np.ndarray, dict, object]:
    s1, law = prob['stage1'], prob['law']
    cs_x = N.with_bands(cs1a, bands)
    yield_heads = frozenset(getattr(design_law(law), 'yielding_pin_rulings', ()) or ())
    _s1 = solve1_factory(law)
    t = time.perf_counter()
    with s1.scope():
        _cs_y, got, y1 = yield_stage_one(s1.pm, cs_x, law, _s1(s1.pm, cs_x), _s1)
    sol, rp, _drop, _foreign, levels, _sz = got
    print(f'  pass 1a {time.perf_counter() - t:.0f} s: unknowns {rp.unknowns} rows {rp.rows} '
          f'hard {rp.hard_rows} settled {rp.hard_settled} exits {rp.settle_record().get("qp_exits")} '
          f'xsec {rp.taxi_xsec_rows} membrane {rp.free_membrane_rows} trend {rp.apron_trend_rows} '
          f'yielded {len(y1)}', flush=True)
    return np.asarray(sol.z, float), levels, rp


def classes(pm, law) -> dict[str, set[int]]:
    rw = set(law.tables.precedence.runway_family.members)
    air = set(airside_stage_roles(law))
    rim: set[int] = set()
    for f in pm.faces.values():
        if f.role == 'apron':
            for h in f.holes:
                rim.update(pm.ring_vertices(h))
    out = {'rim': set(), 'pad_only': set(), 'runway': set(), 'other': set()}
    for v in range(len(pm.vertices)):
        roles = {pm.faces[q].role for q in pm.vertices[v].incident_faces}
        if roles & rw:
            out['runway'].add(v)
        elif v in rim:
            out['rim'].add(v)
        elif 'building' in roles and not (roles & air):
            out['pad_only'].add(v)
        else:
            out['other'].add(v)
    return out


def movers_by_class(za, zb, levelled, cls) -> dict:
    among = np.fromiter(sorted(levelled), dtype=np.int64)
    res = {'all': N.movers(za, zb, among)}
    for k, vs in cls.items():
        a = np.fromiter(sorted(set(levelled) & vs), dtype=np.int64)
        res[k] = N.movers(za, zb, a) if a.size else [0, 0, 0.0]
        res[k + '_n'] = int(a.size)
    return res


def worst_of(pm, za, zb, among, top=8):
    return N.worst_sites(pm, za, zb, np.fromiter(sorted(among), dtype=np.int64), top=top)


def drop_re(cs: ConstraintSet) -> ConstraintSet:
    keep = [r for r in cs.rows() if 'spec §62 (4)' not in r.source.ruling]
    print(f'  noRE: dropped {len(cs.rows()) - len(keep)} cross-ring rows')
    return ConstraintSet.from_rows(keep)


def with_pins(cs: ConstraintSet, z: np.ndarray, vs) -> ConstraintSet:
    src = Source('probe_pin', 'holering PROBE: column pinned at its own pass-1a value', ())
    pins = [Pin(int(v), float(z[v]), src) for v in sorted(vs)]
    return ConstraintSet.from_rows([*cs.rows(), *pins])


def install_candidate(name: str, ctx: dict):
    hook = CANDIDATES[name]
    orig = DA.membrane_rows

    def membrane_plus(planar, law, rows, body, red, named, weight, airside_stage=False):
        n = orig(planar, law, rows, body, red, named, weight, airside_stage)
        k = hook(planar, law, rows, body, red, ctx)
        print(f'  candidate {name}: +{k} rows (membrane {n})', flush=True)
        return n
    DA.membrane_rows = membrane_plus


def rows_at(prob, cs1a: ConstraintSet, vs: list[int]) -> None:
    """Print every assembled pass-1a row touching the vertices."""
    s1, law = prob['stage1'], prob['law']
    with s1.scope():
        d_x, f_x = stage_split(s1.pm, cs1a, law)
        base = DA.assemble(s1.pm, cs1a, law, DesignReport(), drop=d_x, fixed=f_x,
                           stage_roles=airside_stage_roles(law))
    red = base.red
    cols = {int(red.col[v]): v for v in vs}
    print(f'columns {cols}; fixed {[v for v in vs if red.col[v] < 0]}')
    R = np.asarray(base.rows.r); C = np.asarray(base.rows.c); V = np.asarray(base.rows.v)
    hit = np.isin(C, list(cols))
    for k in sorted(set(R[hit].tolist())):
        sel = R == k
        own = base.rows.owner[k]
        w = float(np.max(np.abs(V[sel])))
        print(f'  ROW {k} owner={own!r:.80} cols={list(zip(C[sel].tolist(), np.round(V[sel], 3).tolist()))} b={base.rows.b[k]:.3f}')
    hard = set(base.hard)
    for i, (terms, hi, row) in enumerate(base.one):
        if any(v in vs for v, _c in terms):
            tag = 'HARD' if i in hard else ('PADFLAT' if i in set(base.pad_flat) else 'soft')
            ow = base.one_way.get(i)
            print(f'  ONE {i} {tag} ow={ow} {type(row).__name__} {row.source.ruling[:70]!r} terms={terms} hi={hi:.4f}'
                  f' soft={getattr(row, "soft", None)} cap={getattr(row, "cap", None)} d={getattr(row, "d", None)}')


def main(argv: list[str]) -> int:
    prob_p, arm = Path(argv[0]), argv[1]
    workers = int(argv[argv.index('--workers') + 1]) if '--workers' in argv else 6
    out = Path(argv[argv.index('--out') + 1]) if '--out' in argv else prob_p.parent / 'arms'
    out.mkdir(parents=True, exist_ok=True)
    rep.pool_budget(workers)
    prob = load(prob_p)
    s1, law = prob['stage1'], prob['law']
    pm = s1.pm
    cls = classes(pm, law)
    print(f'[{prob["icao"]}] stage-1 map {len(pm.vertices)} v; classes '
          + ', '.join(f'{k} {len(v)}' for k, v in cls.items()), flush=True)
    cs1a = cs_pass1a(prob)
    if '--rows' in argv or '--at' in argv:
        vs = [int(x) for x in argv[argv.index('--rows') + 1:] if x.isdigit()] if '--rows' in argv else []
        if '--at' in argv:
            for ll in argv[argv.index('--at') + 1:]:
                if ',' not in ll:
                    break
                la, lo = (float(x) for x in ll.split(','))
                v = min(range(len(pm.vertices)), key=lambda i: (pm.vertices[i].key[0] - la) ** 2 + (pm.vertices[i].key[1] - lo) ** 2)
                faces = [pm.faces[q] for q in pm.vertices[v].incident_faces]
                print(f'--at {ll}: v{v} key {pm.vertices[v].key} roles {[(f.id, f.role, str(f.ref)) for f in faces]}')
                vs.append(v)
                for f in faces:
                    if f.role == 'building':
                        ring_v = [u for u in pm.ring_vertices(f.ring) if u in cls['rim']]
                        print(f'   pad face {f.id} {f.ref}: {len(pm.ring_vertices(f.ring))} ring vertices, {len(ring_v)} on an apron hole ring: {ring_v[:6]}')
                        vs.extend(ring_v[:2])
        if arm == 'noRE':
            cs1a = drop_re(cs1a)
        rows_at(prob, cs1a, vs)
        return 0
    ctx: dict = {'cls': cls}
    if arm == 'noRE':
        cs1a = drop_re(cs1a)
    elif arm in CANDIDATES:
        install_candidate(arm, ctx)
        if arm == 'foreign1a':
            global stage_split
            stage_split = _foreign1a_split(law)
    elif arm != 'base' and arm != 'pinrim':
        raise SystemExit(f'unknown arm {arm}')
    za, lv_a, rp_a = pass1a(prob, cs1a)
    if arm == 'pinrim':
        pinned = (cls['rim'] | cls['pad_only']) & set(lv_a)
        print(f'  pinrim: {len(pinned)} columns pinned at their own pass-1a value')
        cs1a = with_pins(cs1a, za, pinned)
        za, lv_a, rp_a = pass1a(prob, cs1a)
    bands = N.ceilings(pm, law, [{'z': za}], 30)
    zb, lv_b, rp_b = pass1a(prob, cs1a, bands)
    res = movers_by_class(za, zb, lv_a, cls)
    res['worst'] = worst_of(pm, za, zb, set(lv_a))
    res['worst_rim'] = worst_of(pm, za, zb, set(lv_a) & (cls['rim'] | cls['pad_only']))
    print(f'[{prob["icao"]}] ARM {arm} NULL-1a all {res["all"]} rim {res["rim"]} pad_only {res["pad_only"]} '
          f'runway {res["runway"]} other {res["other"]}')
    for w in res['worst'][:6]:
        print('   ', w)
    np.savez(out / f'{arm}.npz', za=za, zb=zb, levelled=np.fromiter(sorted(lv_a), dtype=np.int64))
    with open(out / f'{arm}.json', 'w') as fh:
        json.dump(res, fh, indent=1)
    return 0



# ── candidates (hooks run after the membrane, inside assemble) ──────────────────────────────

def _datum_welds(planar, law):
    """{held ref: (datum vertex, weld contacts)} — model.platform.datum_vertices' own reading."""
    from auto_patch_v2.model.platform import HELD, datum_vertices, stage_air_vertices, structure_vertices
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


def cand_datum_weld(planar, law, rows, body, red, ctx):
    """C1: a held pad's DATUM column that no row levels takes one first-difference row to each of
    its own WELD contacts at [design] free_membrane (the §61 membrane, the block's frontage as the
    neighbourhood)."""
    from auto_patch_v2.law.tables import design as design_law
    from auto_patch_v2.solve.rows import _level_row_columns
    w = float(design_law(law).free_membrane)
    lev = _level_row_columns(rows, body, red.n_cols)
    k = 0
    skipped = 0
    for r, (d, welds) in _datum_welds(planar, law).items():
        col = int(red.col[d])
        if col < 0 or lev[col]:
            skipped += 1
            continue
        for u in welds:
            if red.col[u] >= 0:
                k += bool(rows.add(((d, 1.0), (u, -1.0)), 0.0, w, ('datum_membrane', d)))
    print(f'  C1 datum_weld: {k} rows; datum columns already levelled (belt) {skipped}')
    return k


CANDIDATES['datum_weld'] = cand_datum_weld


def _foreign1a_split(law):
    """C2: the held pads' datum columns are FOREIGN to pass 1a (fixed at their welds' DEM mean,
    every row touching them dropped) — the stage split with the datum vertices removed."""
    from auto_patch_v2.solve import design_stage as DS
    orig = DS.stage_split

    def split(pm_x, cs_x, law_x):
        drop, fixed = orig(pm_x, cs_x, law_x)
        fixed = dict(fixed)
        n = 0
        for r, (d, welds) in _datum_welds(pm_x, law_x).items():
            if d in fixed:
                continue
            zs = [pm_x.vertices[u].dem_z for u in welds if pm_x.vertices[u].dem_z is not None]
            fixed[d] = float(sum(zs) / len(zs)) if zs else float(pm_x.vertices[d].dem_z or 0.0)
            n += 1
        print(f'  C2 foreign1a: {n} datum columns made foreign')
        return frozenset(fixed), fixed
    return split


def cand_foreign1a(planar, law, rows, body, red, ctx):
    return 0


CANDIDATES['foreign1a'] = cand_foreign1a


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
