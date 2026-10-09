"""lane flatvalley scratch: a v2_solve_replay run with NULL-CHANGE arms and a
per-stage instrument, by monkeypatching (no tree edit).

  FV_OUT=<dir>            where stages.json / z_<k>.npy land
  FV_ARM=a,b,...          lp_perm | ls_perm | nullband | force:<dir> | qp_tight:<rel>
  then the usual v2_solve_replay argv.
"""
import json, os, sys, time
from pathlib import Path

import numpy as np

TREE = Path("/Users/noah/XPTerrainBuilder/.claude/worktrees/valleyspec/Ortho4XP")


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

    xsec = None          # lane valleyspec: THE CROSS-SECTION ROW (spec §61)
    xfall = None         # ... and the pavement membrane for what no chain reaches
    xreach = None        # override of taxi_trend_face_reach_m for the xsec row (None = the law's)
    for a_ in arms:
        if a_.startswith("xsec:"):
            xsec = float(a_[5:])
        if a_.startswith("xfall:"):
            xfall = float(a_[6:])
        if a_.startswith("xreach:"):
            xreach = float(a_[7:])

    def _lev_cols(bp):
        rows, red = bp.rows, bp.red
        n = int(red.n_cols)
        R, C, V = np.asarray(rows.r, int), np.asarray(rows.c, int), np.asarray(rows.v, float)
        ssum = np.zeros(rows.n); np.add.at(ssum, R, V)
        scale = np.zeros(rows.n); np.maximum.at(scale, R, np.abs(V))
        lev_row = np.abs(ssum) > 1e-9 * np.maximum(scale, 1e-300)
        lev = np.zeros(n, bool); lev[C[lev_row[R]]] = True
        if bp.body is not None and bp.body.n:
            lev[np.asarray(bp.body.c, int)] = True
        return lev

    def _xsec_rows(planar, law, bp, w):
        """§61 (2): every taxi-family vertex that is not itself on a centreline and
        carries no trend row takes ONE relational row to its own face's chain —
        z_v = (1-t) z_a + t z_b at the foot of its perpendicular — at weight w."""
        from auto_patch_v2.constraints import taxi_trend as TT
        from auto_patch_v2.law.tables import is_value_role
        rows, red = bp.rows, bp.red
        taxi = frozenset(law.tables.precedence.taxi_family.members)
        reach = float(xreach if xreach is not None else law.tables.emit.design.taxi_trend_face_reach_m)
        chains = TT._chains(planar, law)
        owner = TT.chain_of_face(planar, law, chains)
        on_chain = set()
        geo = []
        for c in chains:
            on_chain.update(c.vertices)
            xy = np.asarray([planar.vertices[u].xy for u in c.vertices], float)
            A, B = xy[:-1], xy[1:]
            D = B - A
            LL = np.einsum("ij,ij->i", D, D); LL = np.where(LL > 0, LL, 1.0)
            geo.append((A, D, LL))
        stat = {"cand": 0, "on_chain": 0, "shared_value": 0, "no_chain": 0, "far": 0, "added": 0, "fixed": 0,
                "pin_const": 0}
        pins_all = set()
        for c in chains:
            pins_all.update(c.pins)
        got = set()
        seen = set()
        for fid, f in planar.faces.items():
            if f.role not in taxi:
                continue
            vs = list(planar.ring_vertices(f.ring))
            for h in f.holes:
                vs += list(planar.ring_vertices(h))
            for v in vs:
                if v in seen:
                    continue
                seen.add(v)
                if red.col[v] < 0:
                    stat["fixed"] += 1; continue
                if v in on_chain or v in planar.taxi_trend_z:
                    stat["on_chain"] += 1; continue
                roles = planar.roles_at(v)
                if any(r not in taxi and is_value_role(law, r) for r in roles):
                    stat["shared_value"] += 1; continue
                owned = {owner[g] for g in planar.vertices[v].incident_faces
                         if planar.faces[g].role in taxi and g in owner}
                if not owned:
                    stat["no_chain"] += 1; continue
                stat["cand"] += 1
                p = np.asarray(planar.vertices[v].xy, float)
                best = None
                for i in owned:
                    A, D, LL = geo[i]
                    t = np.clip(((p - A) * D).sum(1) / LL, 0.0, 1.0)
                    rel = p - (A + t[:, None] * D)
                    d2 = (rel * rel).sum(1)
                    j = int(np.argmin(d2))
                    d = float(np.sqrt(d2[j]))
                    if best is None or d < best[0]:
                        best = (d, i, j, float(t[j]))
                d, i, j, t = best
                if d > reach:
                    stat["far"] += 1; continue
                a, b = chains[i].vertices[j], chains[i].vertices[j + 1]
                # A RUNWAY CONTACT (the chain's pin) enters as the runway's VALUE,
                # never as a column: the edge follows the runway, it does not pull
                # it (the trend's own `shift_through` reads the same preferred_z).
                # Arm v1 priced the pin's column and moved 165 runway vertices.
                terms = [(v, 1.0)]
                rhs = 0.0
                for u, cu in ((a, 1.0 - t), (b, t)):
                    if cu <= 0.0:
                        continue
                    if u in pins_all:
                        pz = planar.preferred_z.get(u)
                        if pz is None:
                            pz = planar.vertices[u].dem_z
                        rhs += cu * float(pz)
                        stat["pin_const"] += 1
                    else:
                        terms.append((u, -cu))
                if rows.add(tuple(terms), rhs, w, ("taxi_xsec", v)):
                    stat["added"] += 1; got.add(int(red.col[v]))
        return stat, got

    def _membrane(planar, bp, w, lev):
        rows, red = bp.rows, bp.red
        n = int(red.n_cols)
        R, C, V = np.asarray(rows.r, int), np.asarray(rows.c, int), np.asarray(rows.v, float)
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
                added += bool(rows.add(((rep_v[c_], 1.0), (rep_v[u], -1.0)), 0.0, w,
                                       ("free_membrane", rep_v[c_])))
        return added

    def assemble(planar, cs, law, rep, **kw):
        bp = asm(planar, cs, law, rep, **kw)
        cur["_base"] = (planar, bp)
        _prev_ok = bool(tie1b) and last1.get("z") is not None and len(last1["z"]) == len(planar.vertices)
        if xsec and kw.get("stage_roles") is not None:
            lev0 = _lev_cols(bp)
            st, got = _xsec_rows(planar, law, bp, xsec)
            lev1 = _lev_cols(bp)
            lev1[sorted(got)] = True      # a column given its cross-section row is NAMED
            st["free_before"] = int((~lev0).sum()); st["free_after"] = int((~lev1).sum())
            # the lane's reading of "free" (bend-only) is wider than "no level row":
            # a column reached only through a RELATIONAL row to a levelled column
            # counts as levelled by `_level_free_columns`' union-find, not here.
            if xfall:
                st["membrane"] = _membrane(planar, bp, xfall, lev1)
                st["free_after_membrane"] = int((~_lev_cols(bp)).sum())
            cur["xsec"] = st
            print(f"    [vs] taxi cross-section rows at {xsec}: {st}", flush=True)
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
    if dumpq or tie or mem or xsec:
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
