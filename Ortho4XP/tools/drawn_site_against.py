"""``drawn_site.py --clearance-only --against CTL.json`` (#2060 round 3):
each placement ROW's clearance against the same reading of a CONTROL.

A row is keyed by its written row number and its file STEM (a split
body's ``__b<N>_<hash>`` hash dropped, so a body that changed its baked
offset or tilt is the same row).  It is MOVED when its file, its
``lowest_z`` or its clearance changed by more than :data:`MOVE_TOL_M`.
A row whose file (hash included) and ``lowest_z`` equal the control's
is UNMOVED whatever its clearance reads: the object did not move, so a
change in its clearance belongs to the rows under it (HECA's sign row
5933: file, ``lowest_z`` and carrier frame identical across three
rounds, only the probe point moved 29 m) and is never counted worse.
WORSE is a moved row whose ``|clearance|`` grew by more than
:data:`WORSE_M`.  Read-only: it compares two ``--json`` reports."""
from __future__ import annotations

import re
import typing as _t

__all__ = ["MOVE_TOL_M", "WORSE_M", "compare", "print_against"]

#: a reading closer than this to the control's is the same (two decimals
#: are printed; mesh reads of one object agree to 0.01 m)
MOVE_TOL_M = 0.02
#: a moved row whose |clearance| grew by more than this is WORSE
WORSE_M = 0.1

_HASH = re.compile(r"_[0-9a-f]{8}\.obj$")


def _rows(rep: dict) -> dict[tuple, dict]:
    out: dict[tuple, dict] = {}
    for s in rep.get("sites", ()):
        for r in s.get("placements", ()):
            out[(r.get("tile"), r["row"], _HASH.sub("", r["def"]))] = r
    return out


def _same(a: "float | None", b: "float | None") -> bool:
    if a is None or b is None:
        return a is b
    return abs(float(a) - float(b)) <= MOVE_TOL_M


def compare(ctl: dict, rep: dict) -> dict[str, _t.Any]:
    """``{"changed": [...], "only_ctl": n, "only_new": n, "worse": n,
    "unmoved": n}`` — one record per row that MOVED or reads another
    clearance, with ``status`` MOVED / UNMOVED and ``worse``."""
    a, b = _rows(ctl), _rows(rep)
    changed = []
    for k in sorted(set(a) & set(b), key=lambda q: (q[2], q[1])):
        ra, rb = a[k], b[k]
        ca, cb = ra.get("clearance_m"), rb.get("clearance_m")
        same_obj = ra["def"] == rb["def"] and _same(ra.get("lowest_z"), rb.get("lowest_z"))
        if same_obj and _same(ca, cb):
            continue
        grew = (None if ca is None or cb is None else abs(float(cb)) - abs(float(ca)))
        changed.append(dict(row=k[1], tile=k[0], stem=k[2], def_ctl=ra["def"],
                            def_new=rb["def"], clearance_ctl=ca, clearance_new=cb,
                            lowest_z_ctl=ra.get("lowest_z"), lowest_z_new=rb.get("lowest_z"),
                            on_object_ctl=ra.get("on_object"), on_object_new=rb.get("on_object"),
                            status="UNMOVED" if same_obj else "MOVED",
                            worse=bool(not same_obj and grew is not None and grew > WORSE_M),
                            grew_m=grew))
    return dict(changed=changed, only_ctl=len(set(a) - set(b)), only_new=len(set(b) - set(a)),
                worse=sum(1 for c in changed if c["worse"]),
                unmoved=sum(1 for c in changed if c["status"] == "UNMOVED"))


def _hash(d: str) -> str:
    m = _HASH.search(d)
    return d[m.start() + 1:m.end() - 4] if m else "-"


def print_against(res: dict) -> None:
    """One line per changed row, then the totals."""
    print(f"\nAGAINST control: rows only in control {res['only_ctl']}, only here "
          f"{res['only_new']}")
    for c in res["changed"]:
        g = "" if c["grew_m"] is None else f" (|d| {c['grew_m']:+.2f})"
        print(f"  {c['status']:7s}{' WORSE' if c['worse'] else '      '} "
              f"{c['stem'].split('/')[-1]:36s} row{c['row']:6d} "
              f"{_hash(c['def_ctl'])}->{_hash(c['def_new'])} clr {c['clearance_ctl']} -> "
              f"{c['clearance_new']}{g} lowz {c['lowest_z_ctl']}->{c['lowest_z_new']} "
              f"on_obj={c['on_object_ctl']}->{c['on_object_new']}")
    print(f"AGAINST: changed {len(res['changed'])}, unmoved {res['unmoved']}, "
          f"worse by > {WORSE_M:g} m: {res['worse']}")
