"""gapapron4 ARM A (the rule OFF, on this tree): every apron-touching gap piece
is judged ROAD (the §55 build) — `gap_mint.judge` replaced; nothing else.
usage: arm_a.py <v2_solve_replay args...>"""
import sys
sys.path[:0] = ["src", ".", "tools"]
if __name__ == "__main__":
    from auto_patch_v2.classify import gap_mint as gm
    from auto_patch_v2.classify.gap_apron import Verdict
    gm.judge = lambda parts, *a, **k: [Verdict(False, True, None) for _ in parts]
    print(f"[arm_a] §59 class OFF: every touching piece ROAD")
    import v2_solve_replay as _r
    raise SystemExit(_r.main())
