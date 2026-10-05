"""Lane ``perf412b`` twin, R7 memo (issue #412): ``solve/design_roles.
ruling_head`` answers from its per-string memo what the split of the string
answers.
"""
from __future__ import annotations

import types

from auto_patch_v2.solve import design_roles as DR


# ── R7: the ruling head ──────────────────────────────────────────────────

def test_ruling_head_memo_is_the_split():
    rulings = ["2026-09-08v", "runway_transverse (face 7)", "  pad_flat  (a) (b)",
               "apron (x)", "apron (y)", "", "no paren ", "a(b) (c)"]
    for _ in range(2):                       # cold, then from the memo
        for r in rulings:
            row = types.SimpleNamespace(source=types.SimpleNamespace(ruling=r))
            assert DR.ruling_head(row) == r.split(" (")[0].strip()
            assert DR.is_hard({"apron"}, row) == (r.split(" (")[0].strip() == "apron")
