"""THE EXTENSION'S PLAN ROWS (owner RULINGS 2026-09-12as (2)).

``pack_partition._parts_by_member`` builds its per-part foot count array
``nf`` POSITIONALLY over the parts it is handed, and used to index it by
``p.pid`` — the part's GLOBAL load-numbering id.  In the load pass the
two coincide; in ``extend_partition`` the ``fake`` Partition holds ONLY
the new parts, whose pids continue the numbering (OTHH: 2 parts with
pids 164,799 and 164,800), so the read was
``IndexError: index 164799 is out of bounds for axis 0 with size 2``
and the whole OTHH tile aborted.  This twin is that fake partition.
"""
from __future__ import annotations

import numpy as np

from auto_patch_v2.airport import contact as _contact
from auto_patch_v2.airport.pack_partition import _parts_by_member


def _part(pid: int, member: int, x: float, feet: np.ndarray) -> _contact.PlacedPart:
    pts = np.array([[x, 0.0, 0.0], [x + 1.0, 0.0, 0.0], [x, 3.0, 1.0]])
    return _contact.PlacedPart(
        pid=pid, member=member, comp=0, pts=pts,
        tris=np.array([[0, 1, 2]]), base_y=0.0, area_m2=1.5,
        centroid=(x + 0.5, 0.5),
        box_min=np.array([x, 0.0, 0.0]),
        box_max=np.array([x + 1.0, 3.0, 1.0]),
        feet=feet)


def _to_ll_batch(xs, ys):
    """A stand-in frame: metres straight through as degrees."""
    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float)
    return xs / 1000.0, ys / 1000.0


def test_the_extension_partition_rows_index_by_position_not_by_pid():
    # the OTHH shape: two NEW parts whose pids continue the load
    # numbering, each with feet, each its own member
    a = _part(164799, 512, 0.0, np.array([[0.0, 0.0, 1.25], [1.0, 0.0, 1.5]]))
    b = _part(164800, 513, 10.0, np.array([[10.0, 0.0, 2.0]]))
    fake = _contact.Partition((a, b), (), 0, 0, 0, 0, ())

    rows = _parts_by_member(fake, _to_ll_batch)

    assert sorted(rows) == [512, 513]
    ra, = rows[512]
    rb, = rows[513]
    assert ra.pid == 164799 and rb.pid == 164800
    # THE FEET land on the right row, in order, with their AUTHORED y
    assert [f[2] for f in ra.feet] == [1.25, 1.5]
    assert [f[2] for f in rb.feet] == [2.0]
    assert [round(f[0], 8) for f in ra.feet] == [0.0, 0.001]
    assert [round(f[0], 8) for f in rb.feet] == [0.01]


def test_the_load_order_is_unchanged_when_pid_equals_position():
    """The load pass hands parts whose pid IS their position: the
    positional read must give exactly what the pid read gave."""
    a = _part(0, 0, 0.0, np.array([[0.0, 0.0, 1.0]]))
    b = _part(1, 1, 10.0, np.array([[10.0, 0.0, 2.0], [11.0, 0.0, 2.5]]))
    rows = _parts_by_member(_contact.Partition((a, b), (), 0, 0, 0, 0, ()),
                            _to_ll_batch)
    assert [f[2] for f in rows[0][0].feet] == [1.0]
    assert [f[2] for f in rows[1][0].feet] == [2.0, 2.5]


def test_a_footless_extension_part_still_rows():
    a = _part(9001, 3, 0.0, np.zeros((0, 3)))
    rows = _parts_by_member(_contact.Partition((a,), (), 0, 0, 0, 0, ()),
                            _to_ll_batch)
    assert rows[3][0].feet == ()
