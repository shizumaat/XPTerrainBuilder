"""reference_field — Z_ref, the airside reference field, built ONCE.

Step R1 of the taut-string consolidation (``docs/specs/
taut-string-model-spec.md`` §4.1; plan step P2).  Replaces the
per-pass ``z_ref`` snapshots and the per-pass apron-``R`` rebuild —
the "reference-snapshot ratchet" of spec §3.1(b), where each pass
referenced the previous pass's drift and a 1-2 m sag compounded to
5.5 m.

The law of this module
----------------------
The field is **minted once per build** into the node-space store, keyed
by canonical-point ID, and every projection pass (fp#8, final #1,
final #2) resolves the SAME field through ``view_scalar``.  No pass
re-snapshots.  Layered by priority, higher wins (§4.1):

1. anchors — their own values (hard; consumers filter them out)
2. pads — the merged flat-group seat level
3. pad-face weld shadow — the pad's own level
4. spine corridors — two sub-domains: taxi corridors take the
   rod-implied string (``_rod_string_values``), SERVICE corridors take
   the live ``apply_service_road_dem_follow`` shape (never the string,
   never ``elev_entry`` — see the ★ conformance obligation below)
5. aprons — ``R`` (``apron_reference_values``), built ONCE here and
   anchored on layers 1-4 *of this field*, never on live ``elev``
6. everything else airside — the phase-A/B solved value

Two source states, not one (P2-CP1 ruling 2026-07-31)
-----------------------------------------------------
Gate (iv) of the checkpoint measured that a layer-4 string built from
the pre-projection copy sits p50 0.628 m from the final surface, while
one built from the assembly-moment state sits p50 0.077 m — so the
sources decouple:

* ``elev_entry`` (the A-copy, captured before fp#8's feasibility
  projections) feeds layers 2/3/6.  It is the pre-drag fabric: 14.78 %
  of fabric nodes move between the two states, worst 19.2 m, and that
  projection drag is exactly what a reference must not inherit.
* ``elev`` (live, at the assembly moment) feeds layer 4 — the level
  the passes demonstrably enforce.

★ EXPRESS CAVEAT (anti-scope-sneak, Fable 2026-07-31): pre-S1 the
layer-4 read embeds chord-1's attributed sag level, and **that is
CORRECT for R1**.  R1's job is to read the string faithfully, sag
included; dissolving the sag is S1's job (it replaces the string
CONSTRUCTION, after which this same read carries the taut chord).
Nothing in this module may compensate for, special-case, or "improve"
chord 1.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence, Set

from .node_space import store_of

__all__ = ["build_reference_field"]

#: Store artifact names minted by :func:`build_reference_field`.
FIELD_NAME = "reference_field"
FIELD_PAD_NAME = "reference_field_pad"


def _pad_group_levels(
    pad_groups: Sequence[Set[int]],
    elev_entry: Sequence[float],
    n: int,
) -> list:
    """Per-group seat level: the mean entry value over the group's members.

    Mirrors the level today's fp#8 block computes for ``group_refs``, but
    from the A-copy (§4.1 layer 2).  A group with no in-range member has
    no level (``None``) and contributes nothing to the field.
    """
    levels: list = []
    for group in pad_groups:
        members = [i for i in group if 0 <= i < n]
        levels.append(
            sum(elev_entry[i] for i in members) / len(members)
            if members else None)
    return levels


def build_reference_field(
    layout: Any,
    *,
    bucket_to_idx: Mapping[Any, int],
    n: int,
    elev: Sequence[float],
    elev_entry: Sequence[float],
    hard: Set[int],
    pad_groups: Sequence[Set[int]],
    pad_weld_idx: Mapping[int, Any],
    rod_edges: Any,
    broken: Set[int],
    u_spine_nodes: Set[int],
    service_nodes: Set[int],
) -> None:
    """Mint the reference field ONCE per build into the node-space store.

    Mints two scalar artifacts, keyed by canonical-point ID:

    ``reference_field``      canonical key -> z_ref (uncrowned)
    ``reference_field_pad``  pad-ring key  -> its flat group's level

    ``elev`` is the LIVE assembly-moment state (layer 4 only);
    ``elev_entry`` is the pre-projection A-copy (layers 2/3/6).  See the
    module docstring for why they differ and for the chord-1 caveat.

    Values are UNCROWNED — the crown lift belongs to
    :meth:`NodeSpaceStore.view_scalar`, applied once per consuming pass.
    """
    # ── layer 6: everything else airside (the one legitimate snapshot) ──
    field: Dict[int, float] = {i: float(elev_entry[i]) for i in range(n)}

    # ``claimed`` tracks nodes owned by a layer ABOVE the apron surface,
    # so R (layer 5) is applied only where nothing higher speaks.
    claimed: Set[int] = set()

    # ── layer 4: spine corridors — TWO sub-domains (§4.1) ───────────────
    # 4a — taxi corridors: the rod-implied string, from LIVE elev per the
    #      split-source ruling.  A rod slab is a difference constraint, so
    #      the string's SHAPE survives the quarantine blend; its level is
    #      the least-displacement law-true level.
    # 4b — SERVICE corridors: "service corridors from
    #      ``apply_service_road_dem_follow``'s shape" — operationally the
    #      LIVE ``elev``, which carries that re-shape.  Service takes
    #      neither the rod string nor ``elev_entry``.
    #      ★ CONFORMANCE OBLIGATION (CP2b ruling 2026-07-31).  The legacy
    #      site carried a ★ warning that absorption lost: a service
    #      reference sourced from the pre-follow profile "minted the CYXY
    #      8.95 % service pairs".  Measured recurrence when this sub-domain
    #      fell through to layer 6: the field PRESCRIBED 6.03 % across a
    #      5.0 %-cap service pair pre-solve (legacy 4.48 %).  Do not
    #      re-route service through layer 6.
    if rod_edges:
        from .route_profile.solve import _rod_string_values
        string_value = _rod_string_values(rod_edges, elev, broken, n)
        for i, value in string_value.items():
            if not (0 <= i < n) or i in service_nodes:
                continue                      # 4b owns these, not 4a
            field[i] = float(value)
            claimed.add(i)
    else:
        string_value = {}
    for i in service_nodes:                   # 4b — the follow shape
        if 0 <= i < n:
            field[i] = float(elev[i])
            claimed.add(i)

    # ── layer 3: pad-face weld shadow ───────────────────────────────────
    group_levels = _pad_group_levels(pad_groups, elev_entry, n)
    group_of: Dict[int, int] = {
        member: gi for gi, group in enumerate(pad_groups) for member in group}
    for contact, ref in (pad_weld_idx or {}).items():
        if not (0 <= contact < n):
            continue
        seat, pad_node = (ref if isinstance(ref, tuple) else (None, ref))
        gi = group_of.get(pad_node)
        if gi is not None and group_levels[gi] is not None:
            level = group_levels[gi]
        elif pad_node is not None and 0 <= pad_node < n:
            level = elev_entry[pad_node]
        else:
            level = seat
        if level is not None:
            field[contact] = float(level)
            claimed.add(contact)

    # ── layer 2: pads — the merged flat-group seat level ────────────────
    pad_field: Dict[Any, float] = {}
    key_of = {i: k for k, i in bucket_to_idx.items()}
    for gi, group in enumerate(pad_groups):
        level = group_levels[gi]
        if level is None:
            continue
        for member in group:
            if not (0 <= member < n):
                continue
            field[member] = float(level)
            claimed.add(member)
            key = key_of.get(member)
            if key is not None:
                pad_field[key] = float(level)

    # ── layer 5: aprons — R, built ONCE, anchored on THIS field ─────────
    # R samples its anchor values from the ``elev`` list it is handed; we
    # hand it the field-so-far (layers 1-4 already applied) so that §4.1's
    # "never on live elev" holds.  R is BELOW layers 1-4, so its values
    # land only on nodes no higher layer claimed.
    # ``band_of=None``: the anchor-honesty ladder's rule 2 was the band's
    # only consumer here and §4.6 deletes it, which is why this module
    # takes NO band parameter (Fable API revision 2026-07-31 — a future
    # field-side consumer reads the band as a store view, not an argument).
    field_as_elev = [field.get(i, float(elev_entry[i])) for i in range(n)]
    from .apron_reference import apron_reference_values
    apron_ref = apron_reference_values(
        layout, bucket_to_idx, field_as_elev, n=n,
        hard_idx=hard, spine_idx=u_spine_nodes,
        pad_ref={c: field[c] for c in (pad_weld_idx or {}) if c in field},
        label="reference_field",
        broken_idx=(broken or None),
        string_value=string_value,
        band_of=None,
        stats_out=None)
    for i, value in apron_ref.items():
        if 0 <= i < n and i not in claimed:
            field[i] = float(value)

    # ── mint (once) ────────────────────────────────────────────────────
    keyed: Dict[Any, float] = {}
    for i, value in field.items():
        key = key_of.get(i)
        if key is not None:
            keyed[key] = value
    store = store_of(layout)
    store.mint(FIELD_NAME, "scalar", keyed, replace=True)
    store.mint(FIELD_PAD_NAME, "scalar", pad_field, replace=True)
