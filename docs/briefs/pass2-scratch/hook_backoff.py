"""pass2 scratch hook: the QP's backoff ladder lengthened (design_qp._BACKOFF_MAX 12 -> P2_BACKOFF) with the round
ceiling P2_ROUNDS; every QP exit printed."""
import os


def install(ctx):
    from auto_patch_v2.solve import design_qp as Q
    Q._ROUNDS_MAX = int(os.environ.get('P2_ROUNDS', '400'))
    Q._BACKOFF_MAX = int(os.environ.get('P2_BACKOFF', '40'))
    orig = Q.solve_one_sided

    def traced(*a, **k):
        r = orig(*a, **k)
        print(f'    QP exit {r.status} rounds {r.rounds} solves {r.solves} F {r.objective:.6f} |g| {r.grad_norm:.3g} '
              f'wall {r.wall_s:.1f}s', flush=True)
        return r
    Q.solve_one_sided = traced
    import auto_patch_v2.solve.design as D
    D.solve_one_sided = traced
    print(f'  hook: _ROUNDS_MAX = {Q._ROUNDS_MAX} _BACKOFF_MAX = {Q._BACKOFF_MAX}', flush=True)
