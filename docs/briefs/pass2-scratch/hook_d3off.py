"""pass2 scratch hook (the MEMBRANE CLASS probe): a taxi-centreline vertex with no level row is IN the membrane's
class (section 61 (10) D3 switched off); QP exits printed."""


def install(ctx):
    from auto_patch_v2.solve import design_edge as E
    E.TAXI_CENTERLINE = '__no_such_kind__'
    from auto_patch_v2.solve import design_qp as Q
    orig = Q.solve_one_sided

    def traced(*a, **k):
        r = orig(*a, **k)
        print(f'    QP exit {r.status} rounds {r.rounds} solves {r.solves} F {r.objective:.6f} |g| {r.grad_norm:.3g} '
              f'wall {r.wall_s:.1f}s', flush=True)
        return r
    Q.solve_one_sided = traced
    import auto_patch_v2.solve.design as D
    D.solve_one_sided = traced
    print('  hook: D3 off (centreline vertices take the membrane)', flush=True)
