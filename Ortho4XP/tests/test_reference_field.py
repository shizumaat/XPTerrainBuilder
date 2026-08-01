"""Unit tests for auto_patch.elevation_per_surface.reference_field.

Step R1 (plan step P2).  These pin the two things the field can silently
get wrong:

* **the split-source rule** (P2-CP1 ruling 2026-07-31) — layers 2/3/6
  read the pre-projection A-copy (``elev_entry``) while layer 4 reads
  the live assembly-moment state (``elev``).  Every fixture below gives
  the two lists DIFFERENT values at the same node, so a implementation
  that collapses them to one source fails rather than coincidentally
  passing; and
* **layer priority** (§4.1, higher wins): pads > pad-face weld shadow >
  spine strings > aprons > entry value.

★ SCOPE LIMIT — READ BEFORE TRUSTING A GREEN RUN.  These fixtures are
SYNTHETIC: a hand-built node space with a hand-built rod chain and NO
real airport geometry.  They prove the layering arithmetic and the
source split.  They CANNOT catch: whether the field is assembled at the
right moment in a real solve; whether ``apron_reference_values``
produces a sane R on real apron rings (``shapes`` is empty here, so
layer 5 is exercised only as a no-op); whether real rod chains split at
branch vertices as the string builder expects; or any interaction with
crown lift, the reach band, or the projection passes.  Only a real
HECA/CYXY replay closes those.  (S1's 62-piece synthetic acceptance
fixture passed against an implementation that could not assemble the
real chord — synthetic green is not evidence about real geometry.)

Pure in-memory: no DEM, no layout build, no X-Plane install.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

import pytest

from auto_patch.elevation_per_surface.node_space import store_of
from auto_patch.elevation_per_surface.reference_field import (
    FIELD_NAME,
    FIELD_PAD_NAME,
    build_reference_field,
)


class _CPS:
    """Minimal canonical-point registry stand-in."""

    def __init__(self) -> None:
        self._m: Dict[Tuple[float, float], int] = {}

    def get_or_add(self, x: float, y: float) -> int:
        return self._m.setdefault((float(x), float(y)), len(self._m))


class _Layout:
    """Minimal layout: a registry, no shapes (so layer 5 is a no-op)."""

    def __init__(self) -> None:
        self.canonical_points = _CPS()
        self.shapes: list = []


N = 7
B2I = {f"k{i}": i for i in range(N)}
KEY = {i: f"k{i}" for i in range(N)}

# entry (A-copy) vs live (assembly moment) DIFFER at every interesting node
ELEV_ENTRY = [5.0, 5.0, 5.0, 20.0, 20.0, 0.0, 7.0]
# node 2 is the SERVICE node: its live value (13.0) differs from BOTH the
# rod-string level (mean(10,10,13) = 11.0) and its entry value (5.0), so a
# service node taking the string, or falling through to layer 6, both fail.
ELEV_LIVE = [10.0, 10.0, 13.0, 33.0, 33.0, 0.0, 99.0]
# a flat 3-node rod chain over nodes 0,1,2 -> string level from LIVE elev
ROD = [(0, 1, 0.0, 0.0), (1, 2, 0.0, 0.0)]
STRING_LEVEL = 11.0     # mean(10,10,13) over the zero-width chain


def _build(**over: Any) -> Tuple[_Layout, Dict[int, float]]:
    """Build the field on the synthetic space; return (layout, index view)."""
    layout = _Layout()
    kw: Dict[str, Any] = dict(
        bucket_to_idx=B2I, n=N,
        elev=ELEV_LIVE, elev_entry=ELEV_ENTRY,
        hard=set(), pad_groups=[{3, 4}],
        pad_weld_idx={5: (99.0, 3)}, rod_edges=ROD,
        broken=set(),
        u_spine_nodes={0, 1, 2}, service_nodes={2},
    )
    kw.update(over)
    build_reference_field(layout, **kw)
    return layout, store_of(layout).view_scalar(FIELD_NAME, B2I, N)


def test_layer_4_reads_live_elev_not_the_entry_copy() -> None:
    """Strung nodes take the rod string built from LIVE elev, not entry.

    Entry-sourced would give mean(5,5,5) = 5.0; live gives 11.0.
    """
    _, field = _build()
    assert field[0] == pytest.approx(STRING_LEVEL)
    assert field[1] == pytest.approx(STRING_LEVEL)


def test_layer_6_reads_the_entry_copy_not_live() -> None:
    """Plain fabric takes the A-copy (7.0), never the live value (99.0)."""
    _, field = _build()
    assert field[6] == pytest.approx(7.0)


def test_layer_2_pads_read_the_entry_copy() -> None:
    """A pad group's level is the mean ENTRY value (20), not live (33)."""
    _, field = _build()
    assert field[3] == pytest.approx(20.0)
    assert field[4] == pytest.approx(20.0)


def test_weld_shadow_equals_the_pad_level() -> None:
    """A pad-face weld contact references the pad's own level, not its seat."""
    _, field = _build()
    assert field[5] == pytest.approx(20.0)


def test_service_nodes_take_the_live_follow_shape() -> None:
    """§4.1 layer 4b: service corridors take the LIVE follow shape.

    ★ CONFORMANCE REGRESSION GUARD (CP2b ruling 2026-07-31).  A ★ warning
    at the legacy site — lost in absorption — said a service reference from
    the pre-follow profile "minted the CYXY 8.95 % service pairs".  When
    this sub-domain fell through to layer 6 the field prescribed 6.03 %
    across a 5.0 %-cap CYXY service pair BEFORE the solve ran.  This
    asserts service takes neither the entry copy (5.0) nor the rod string
    (11.0), but the live follow value.
    """
    _, field = _build()
    assert field[2] == pytest.approx(13.0)
    assert field[2] != pytest.approx(5.0)            # not layer 6
    assert field[2] != pytest.approx(STRING_LEVEL)   # not layer 4a


def test_pad_beats_string_when_a_node_is_both() -> None:
    """Layer 2 outranks layer 4: a strung node inside a pad takes the pad."""
    _, field = _build(pad_groups=[{0, 1}])
    assert field[0] == pytest.approx(5.0)   # mean entry of {0,1}
    assert field[1] == pytest.approx(5.0)


def test_pad_field_artifact_carries_group_levels() -> None:
    """reference_field_pad maps each pad-ring key to its group's level."""
    layout, _ = _build()
    pad = store_of(layout).view_scalar(FIELD_PAD_NAME, B2I, N)
    assert pad == {3: pytest.approx(20.0), 4: pytest.approx(20.0)}


def test_field_is_minted_exactly_once_per_build() -> None:
    """The single-construction contract (§4.1 'built once')."""
    layout, _ = _build()
    store = store_of(layout)
    assert store.mint_count(FIELD_NAME) == 1
    assert store.mint_count(FIELD_PAD_NAME) == 1


def test_no_rod_edges_leaves_every_node_on_the_entry_value() -> None:
    """With no §10 slabs and no service ring, fabric falls through to entry."""
    _, field = _build(rod_edges=[], u_spine_nodes=set(), service_nodes=set())
    for i in (0, 1, 2, 6):
        assert field[i] == pytest.approx(ELEV_ENTRY[i])


def test_service_sub_domain_applies_without_any_rod_edges() -> None:
    """Layer 4b is independent of layer 4a: no slabs still means service
    takes the live follow shape, not the entry copy."""
    _, field = _build(rod_edges=[], u_spine_nodes=set())
    assert field[2] == pytest.approx(13.0)


def test_hard_anchors_keep_their_entry_value() -> None:
    """Detached pads / anchors are hard; they hold their own value."""
    _, field = _build(hard={6}, pad_groups=[], pad_weld_idx={})
    assert field[6] == pytest.approx(7.0)


def test_view_skips_keys_absent_from_the_pass_index_space() -> None:
    """A pass that does not carry a key simply does not see it (the
    consumer's entry-elev fallback covers late-minted nodes)."""
    layout, _ = _build()
    partial = store_of(layout).view_scalar(FIELD_NAME, {"k0": 0}, 1)
    assert set(partial) == {0}
