"""lane flatvalley scratch: a v2_solve_replay run with NULL-CHANGE arms and a
per-stage instrument, by monkeypatching (no tree edit).

  FV_OUT=<dir>            where stages.json / z_<k>.npy land
  FV_ARM=a,b,...          lp_perm | ls_perm | nullband | force:<dir> | qp_tight:<rel>
  then the usual v2_solve_replay argv.
"""
import json, os, sys, time
from pathlib import Path

import numpy as np

TREE = Path("/Users/noah/XPTerrainBuilder/.claude/worktrees/flatvalley/Ortho4XP")


def install(arms, out: Path):
    from auto_patch_v2.solve import design, design_qp, feasibility
    from auto_patch_v2.solve.design_roles import ruling_head
    import auto_patch_v2.solve as solve_pkg
    log = {"arms": arms, "stages": []}
    cur = {}
    forced = None
    for a in arms:
        if a.startswith("force:"):
            forced = json.load(open(Path(a[6:]) / "stages.json"))["stages"]

    def ident(planar, one, k):
        terms, hi, row = one[int(k)]
        return [ruling_head(row), sorted(
            "%s,%s" % tuple(planar.vertices[int(v)].key) for v, _c in terms),
            round(float(hi), 6)]

    def keyof(i):
        return json.dumps(i[:2])

    chs = feasibility.check_hard_set

    def check_hard_set(planar, law, one, hard_i, A, b, *, stage="", verbose=False):
        hi_ = np.asarray(hard_i, dtype=np.int64)
        if "lp_perm" in arms:
            hi_ = hi_[np.random.default_rng(7).permutation(hi_.size)]
        demote, rep = chs(planar, law, one, hi_, A, b, stage=stage, verbose=verbose)
        k = len(log["stages"])
        if forced is not None and k < len(forced):
            want = {keyof(i) for i in forced[k].get("demote", [])}
            got = [int(q) for q in np.asarray(hard_i, dtype=np.int64)
                   if keyof(ident(planar, one, q)) in want]
            cur["forced"] = [len(want), len(got), int(demote.size)]
            demote = np.asarray(got, dtype=np.int64)
        cur["demote"] = [ident(planar, one, q) for q in demote]
        cur["lp"] = {"rows": rep.rows, "relaxed": rep.relaxed, "status": rep.status,
                     "by_tier": dict(rep.by_tier), "runway_conflict": rep.runway_conflict}
        return demote, rep
    feasibility.check_hard_set = check_hard_set

    pm_ = design.promote_missed

    def promote_missed(one, hard_i, A, b, lead, x, law, rep):
        miss, sc = pm_(one, hard_i, A, b, lead, x, law, rep)
        cur["promoted"] = int(miss.size)
        cur["_miss"] = (one, miss)
        return miss, sc
    design.promote_missed = promote_missed

    sos = design.solve_one_sided
    rel = None
    for a in arms:
        if a.startswith("qp_tight:"):
            rel = float(a[9:])
    if rel is not None:
        design_qp._REL_TOL = rel
        design_qp._ROUNDS_MAX = 4000

    dumpq = os.environ.get("FV_DUMPQP")
    asm = design.assemble

    tie = None
    tie1b = None
    last1 = {}
    for a_ in arms:
        if a_.startswith("tie:"):
            tie = float(a_[4:])
        if a_.startswith("tie1b:"):
            tie1b = float(a_[6:])
    mem = None
    for a_ in arms:
        if a_.startswith("mem:"):
            mem = float(a_[4:])

    def assemble(planar, cs, law, rep, **kw):
        bp = asm(planar, cs, law, rep, **kw)
        cur["_base"] = (planar, bp)
        _prev_ok = bool(tie1b) and last1.get("z") is not None and len(last1["z"]) == len(planar.vertices)
        if mem and kw.get("stage_roles") is not None and not _prev_ok:
            rows, red = bp.rows, bp.red
            n = int(red.n_cols)
            R, C, V = np.asarray(rows.r, int), np.asarray(rows.c, int), np.asarray(rows.v, float)
            ssum = np.zeros(rows.n); np.add.at(ssum, R, V)
            scale = np.zeros(rows.n); np.maximum.at(scale, R, np.abs(V))
            lev_row = np.abs(ssum) > 1e-9 * np.maximum(scale, 1e-300)
            lev = np.zeros(n, bool); lev[C[lev_row[R]]] = True
            if bp.body is not None and bp.body.n:
                lev[np.asarray(bp.body.c, int)] = True
            rep_v = {}
            for v in range(len(planar.vertices)):
                c_ = int(red.col[v])
                if c_ >= 0:
                    rep_v.setdefault(c_, v)
            isbend = np.array([bool(o) and o[0] == "bend" for o in rows.owner])
            order = np.argsort(R, kind="stable")
            Rs, Cs, Vs = R[order], C[order], V[order]
            cut = np.flatnonzero(np.diff(Rs)) + 1
            nb = {}
            for rr, cc, vv in zip(np.split(Rs, cut), np.split(Cs, cut), np.split(Vs, cut)):
                if not isbend[rr[0]] or cc.size < 2:
                    continue
                ctr = int(cc[np.argmax(np.abs(vv))])
                for u in cc:
                    if int(u) != ctr:
                        nb.setdefault(ctr, set()).add(int(u)); nb.setdefault(int(u), set()).add(ctr)
            added = 0
            for c_ in range(n):
                if lev[c_]:
                    continue
                for u in sorted(nb.get(c_, ())):
                    if not lev[u] and u < c_:
                        continue
                    added += bool(rows.add(((rep_v[c_], 1.0), (rep_v[u], -1.0)), 0.0, mem,
                                           ("free_membrane", rep_v[c_])))
            cur["free_membrane"] = added
            print(f"    [fv] free-column membrane: {int((~lev).sum())} of {n} columns carry no level term; "
                  f"{added} first-difference rows to their mesh neighbours at {mem}", flush=True)
        if (tie or _prev_ok) and kw.get("stage_roles") is not None:
            rows, red = bp.rows, bp.red
            n = int(red.n_cols)
            ssum = np.zeros(rows.n)
            np.add.at(ssum, np.asarray(rows.r, int), np.asarray(rows.v, float))
            scale = np.zeros(rows.n)
            np.maximum.at(scale, np.asarray(rows.r, int), np.abs(np.asarray(rows.v, float)))
            lev_row = np.abs(ssum) > 1e-9 * np.maximum(scale, 1e-300)
            lev = np.zeros(n, bool)
            lev[np.asarray(rows.c, int)[lev_row[np.asarray(rows.r, int)]]] = True
            if bp.body is not None and bp.body.n:
                lev[np.asarray(bp.body.c, int)] = True
            acc = {}
            for v in range(len(planar.vertices)):
                c_ = int(red.col[v])
                if c_ >= 0 and not lev[c_]:
                    dz = planar.vertices[v].dem_z
                    if dz is not None:
                        acc.setdefault(c_, []).append((v, float(dz)))
            added = 0
            prev = last1.get("z") if tie1b else None
            if prev is not None and len(prev) != len(planar.vertices):
                prev = None
            for c_, lst in sorted(acc.items()):
                if prev is not None:
                    tgt, w_ = sum(float(prev[v]) for v, _z in lst) / len(lst), tie1b
                else:
                    tgt, w_ = sum(z for _v, z in lst) / len(lst), tie
                added += bool(rows.add(((lst[0][0], 1.0),), tgt, w_, ("free_tie", lst[0][0])))
            cur["free_tie"] = added
            print(f"    [fv] free-column tie: {added} of {n} columns carry no level term; tied to "
                  + (f"the previous stage-1 pass's level at {tie1b}" if prev is not None else f"their own DEM at {tie}"), flush=True)
        return bp
    if dumpq or tie or mem:
        design.assemble = assemble

    def solve_one_sided(*a, **kw):
        res = sos(*a, **kw)
        if dumpq and "_base" in cur:
            import pickle
            planar, bp = cur["_base"]
            k = len(log["stages"]); j = len(cur.get("qp", []))
            with open(out / f"qp_{k}_{j}.pkl", "wb") as fh:
                pickle.dump({"A0": a[0], "b0": a[1], "A1": a[2], "b1": a[3], "w_row": a[4],
                             "shift": a[5].copy(), "x0": a[6], "U": a[7], "c": a[8], "x": res.x,
                             "col": np.asarray(bp.red.col), "owner": list(bp.rows.owner),
                             "gen": [r[2].source.generator for r in bp.one],
                             "hard": list(bp.hard),
                             "keys": np.array([planar.vertices[i].key for i in range(len(planar.vertices))], float),
                             "xy": np.array([planar.vertices[i].xy for i in range(len(planar.vertices))], float),
                             "kw": {q: kw[q] for q in ("method", "solver_tol", "solver_max_iter", "low_rank")}}, fh)
        cur.setdefault("qp", []).append(
            [res.status, res.rounds, res.solves, res.objective, res.grad_norm,
             round(res.wall_s, 2)])
        return res
    design.solve_one_sided = solve_one_sided

    if "ls_perm" in arms:
        ls = design_qp._linear_solve

        def _linear_solve(A, b, x0, *a, **kw):
            p = np.random.default_rng(11).permutation(A.shape[0])
            return ls(A[p], b[p], x0, *a, **kw)
        design_qp._linear_solve = _linear_solve

    ss = design._solve_stage

    def _solve_stage(planar, cs, law, options=None, **kw):
        cur.clear()
        t = time.perf_counter()
        sol, rep = ss(planar, cs, law, options, **kw)
        k = len(log["stages"])
        z = np.asarray(sol.z, float)
        np.save(out / f"z_{k}.npy", z)
        keys = np.array([planar.vertices[i].key for i in range(len(planar.vertices))], float)
        np.save(out / f"k_{k}.npy", keys)
        rec = {"k": k, "n": int(z.size), "drop": kw.get("drop") is not None,
               "fixed": len(kw.get("fixed") or ()), "unknowns": rep.unknowns,
               "rounds": rep.rounds, "hard_rounds": rep.hard_rounds,
               "hard_max": rep.hard_max_violation_m, "hard_settled": rep.hard_settled,
               "one_way_rounds": rep.one_way_rounds, "wall": round(time.perf_counter() - t, 2)}
        if "_miss" in cur:
            one, miss = cur.pop("_miss")
            rec["promote"] = [ident(planar, one, q) for q in miss]
        cur.pop('_base', None)
        if kw.get("stage_roles") is not None:
            last1["z"] = z
        rec.update(cur)
        log["stages"].append(rec)
        (out / "stages.json").write_text(json.dumps(log))
        print(f"    [fv] stage call {k}: unknowns {rep.unknowns} drop {rec['drop']} fixed "
              f"{rec['fixed']} lp {rec.get('lp')} demote {len(rec.get('demote', []))} "
              f"promoted {rec.get('promoted')} qp {[(q[0], q[1], '%.9g' % q[3], '%.3g' % q[4]) for q in rec.get('qp', [])]} "
              f"hard {rep.hard_max_violation_m:.4f} wall {rec['wall']}", flush=True)
        return sol, rep
    design._solve_stage = _solve_stage


    for a in arms:
        if a.startswith("slack:"):
            _, ctl, margin, count = a.split(":")
            from auto_patch_v2.solve import flex
            import dataclasses as dc
            from auto_patch_v2.model.constraints import Band, Source
            so = flex.stage_one

            def stage_one(planar, cs, law, hold, solve1, _ctl=Path(ctl),
                          _m=float(margin), _n=int(count)):
                z0, z1 = np.load(_ctl / "z_0.npy"), np.load(_ctl / "z_1.npy")
                k0 = np.load(_ctl / "k_0.npy")
                keys = np.array([planar.vertices[i].key
                                 for i in range(len(planar.vertices))], float)
                assert keys.shape == k0.shape and np.array_equal(keys, k0), "vertex ids differ"
                roles = {"apron", "junction", "primary_parallel", "stub", "cross_connector"}
                vs = sorted({v for f in planar.faces.values() if f.role in roles
                             for v in planar.ring_vertices(f.ring)})
                pick = np.random.default_rng(3).choice(len(vs), size=_n, replace=False)
                src = Source("null_probe", "lane flatvalley slack band", ())
                bands = tuple(Band(vs[i], None, float(max(z0[vs[i]], z1[vs[i]])) + _m, src)
                              for i in pick)
                print(f"    [fv] {len(bands)} slack ceilings {_m} m over the control's own "
                      f"pass-1a/1b surface, first at {planar.vertices[vs[pick[0]]].key}", flush=True)
                log["slack"] = [[int(b.v), float(b.hi)] for b in bands]
                return so(planar, dc.replace(cs, bands=tuple(cs.bands) + bands), law, hold, solve1)
            flex.stage_one = stage_one

    if "nullband" in arms:
        sd = solve_pkg.solve_design
        import dataclasses as dc
        from auto_patch_v2.model.constraints import Band, Source

        def solve_design(pm, cs, law, *a, **kw):
            vs = sorted({v for f in pm.faces.values() if f.role == "apron"
                         for v in pm.ring_vertices(f.ring)})
            v = vs[len(vs) // 2]
            src = Source("null_probe", "lane flatvalley null band", ())
            cs2 = dc.replace(cs, bands=tuple(cs.bands) + (Band(v, None, 1.0e5, src),))
            print(f"    [fv] null Band on v{v} at {pm.vertices[v].key}", flush=True)
            return sd(pm, cs2, law, *a, **kw)
        solve_pkg.solve_design = solve_design
        design.solve_design = solve_design


def main():
    out = Path(os.environ["FV_OUT"])
    out.mkdir(parents=True, exist_ok=True)
    arms = [a for a in os.environ.get("FV_ARM", "").split(",") if a]
    sys.path.insert(0, str(TREE / "tools"))
    sys.path.insert(0, str(TREE / "src"))
    import v2_solve_replay as R
    install(arms, out)
    print(f"[fv] arms {arms} -> {out}", flush=True)
    return R.main()


if __name__ == "__main__":
    sys.exit(main())
