"""Twin of ``tools/rebake_plan_diff.py`` (lane roads609, promoting kclt608's
scratch on its second use): the body key carries the PLACEMENT INDEX, and
the separations read pairs touching parts written at two zeros."""
from __future__ import annotations

import importlib.util
import pathlib

_TOOL = pathlib.Path(__file__).resolve().parents[1] / "tools" / "rebake_plan_diff.py"
_spec = importlib.util.spec_from_file_location("rebake_plan_diff", _TOOL)
rpd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rpd)


def _dump(zeros: dict[tuple[int, int], float], resource: str = "Terminals/sign.obj"):
    """One split per (placement index, body): a single-component body each."""
    splits: dict[int, dict] = {}
    for (idx, bid), z in zeros.items():
        s = splits.setdefault(idx, {"placement": {"resource": resource, "index": idx,
                                                  "id": f"dsf:obj{idx}"}, "bodies": []})
        s["bodies"].append({"body_id": bid, "components": [bid], "surface_z": z, "y_zero": 0.0,
                            "anchor_reason": f"seated on unit fu:1:{idx} ground", "plan_box": [1, 2, 3, 4],
                            "class": "footed", "merged_into": None, "ground_off": 0.0})
    return {"splits": list(splits.values()), "counts": {"off_pad_bodies": 2}}


def test_the_key_carries_the_placement_index():
    """Two placements of ONE resource, each a single-component body 0: a
    key without the index collides them (the −34.96 m sign_T2 artefact)."""
    base = _dump({(1, 0): 100.0, (2, 0): 66.0})
    arm = _dump({(1, 0): 100.0, (2, 0): 66.0})
    d = rpd.zero_changes(base, arm)
    assert d["movers"] == [] and d["changed"] == []
    assert len(rpd.load_bodies(base)) == 2
    arm2 = _dump({(1, 0): 100.0, (2, 0): 70.5})
    d = rpd.zero_changes(base, arm2)
    assert [(c["key"][1], round(c["dz"], 2)) for c in d["movers"]] == [(2, 4.5)]
    assert d["base_only"] == 0 and d["arm_only"] == 0
    assert d["counts"] == {"off_pad_bodies": 2}


def test_separations_read_touching_parts_at_two_zeros():
    osr = _dump({(7, 0): 10.0, (7, 1): 12.5, (7, 2): 10.2})
    plan = {"units": [{"members": [{"id": "dsf:obj7", "resource": "Terminals/sign.obj",
                                    "parts": [[100, 0, 1.0, 2.0, 0.0], [101, 1, 1.0, 2.0, 3.0],
                                              [102, 2, 1.0, 2.0, 0.1]]}]}],
            "contacts": [[100, 101], [100, 102], [101, 102]]}
    rows = rpd.separations(osr, plan, min_sep=0.3)
    assert [(r["keyA"][1], r["keyB"][1], round(r["sep"], 2)) for r in rows] == [(0, 1, 2.5), (1, 2, 2.3)]
    assert rows[0]["pairs"] == 1 and rows[0]["lat"] == 1.0
