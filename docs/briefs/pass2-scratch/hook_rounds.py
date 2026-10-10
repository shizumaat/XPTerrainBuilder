"""pass2 scratch hook: the QP's round ceiling raised (design_qp._ROUNDS_MAX 400 -> 4000) and every
QP solve's exit printed (status, rounds, grad norm)."""
import os


def install(ctx):
    from auto_patch_v2.solve import design_qp as Q
    Q._ROUNDS_MAX = int(os.environ.get('P2_ROUNDS', '4000'))
    orig = Q.solve_one_sided

    def traced(*a, **k):
        r = orig(*a, **k)
        print(f'    QP exit {r.status} rounds {r.rounds} solves {r.solves} F {r.objective:.6f} |g| {r.grad_norm:.3g} '
              f'wall {r.wall_s:.1f}s', flush=True)
        return r
    Q.solve_one_sided = traced
    import auto_patch_v2.solve.design as D
    if getattr(D, 'solve_one_sided', None) is orig:
        D.solve_one_sided = traced
    print(f'  hook: _ROUNDS_MAX = {Q._ROUNDS_MAX}', flush=True)
