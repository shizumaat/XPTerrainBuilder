"""node_space — the single keyed artifact store over the canonical registry.

Step U1 of the taut-string consolidation
(``docs/specs/node-space-unification-spec.md``; owner answer 5,
2026-07-30: "node-space be unified FIRST").

The law of this module
----------------------
The canonical-point registry (``layout.canonical_points``) is THE node
identity — audited stable across every post-solve pass (single-space
audit phase 1: 0 % re-keyed).  Per-pass node lists are VIEWS of it.
Any artifact that must survive a node-list rebuild is therefore:

* **minted once**, keyed by canonical-point ID, into this store —
  never stashed as an ad-hoc ``layout._foo`` attribute;
* **resolved through one resolver** (the ``view_*`` methods) into a
  pass's index space, with crown lift applied HERE, identically for
  every artifact — never by per-site copy-paste;
* **filtered per consumer** (``build once, filter per consumer``):
  coverage differences between consumers are view arguments, never
  second builds of the artifact.

U1 is a pure transport refactor: every view reproduces the exact
values AND coverage its call site produced before the migration
(alias-collision semantics are per-site: seat boxes intersect
tightest-per-side; band views are last-write-wins in mint insertion
order).  Behavior changes belong to later steps (R1's field, S1's
string construction), which land ON this store.

Artifact kinds
--------------
* ``interval`` — key → ``(lo, hi)`` (seat boxes, reach band).
* ``scalar``   — key → value (reserved for the R1 reference field).
* ``keyset``   — set of keys (spine-crossing identity).
* ``relation`` — key → key (pad-face weld contact → pad node).

The §10 rod EDGE artifact (two-key slabs with compose-across-decimated-
runs) stays on its landed implementation this step — U1a migrates the
simple families; the edge family's store adoption rides R1 (see the U1
spec §3.1).
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Set, Tuple

Interval = Tuple[float, float]

_KINDS = ("scalar", "interval", "keyset", "relation")


class NodeSpaceStore:
    """Keyed artifact store; one instance per build (see :func:`store_of`).

    Keys are canonical-point IDs from ``layout.canonical_points``.
    Minting twice under one name raises unless ``replace=True`` (the
    per-solve re-mint that plain attribute assignment used to allow);
    ``mint_count`` exposes how often a name was (re)minted so tests can
    assert single-construction per build.
    """

    __slots__ = ("_data", "_kind", "_mints")

    def __init__(self) -> None:
        self._data: Dict[str, Any] = {}
        self._kind: Dict[str, str] = {}
        self._mints: Dict[str, int] = {}

    # ── minting ────────────────────────────────────────────────────────
    def mint(self, name: str, kind: str, payload: Any, *,
             replace: bool = False) -> Any:
        """Register ``payload`` under ``name``.  Returns the payload.

        ``replace=False`` (the default) raises on a second mint — the
        single-construction contract.  ``replace=True`` reproduces the
        legacy assignment semantics for artifacts a re-solve of the
        same layout legitimately rebuilds.
        """
        if kind not in _KINDS:
            raise ValueError(f"unknown artifact kind {kind!r}")
        if name in self._kind and self._kind[name] != kind:
            raise ValueError(
                f"artifact {name!r} kind mismatch: "
                f"{self._kind[name]!r} already minted, {kind!r} requested")
        if name in self._data and not replace:
            raise ValueError(f"artifact {name!r} already minted")
        self._data[name] = payload
        self._kind[name] = kind
        self._mints[name] = self._mints.get(name, 0) + 1
        return payload

    def open_map(self, name: str, kind: str, *, reset: bool = False) -> dict:
        """Get-or-create a MUTABLE dict payload for incremental writers.

        ``reset=True`` re-mints an empty dict (the first-producer-of-a-
        solve semantics, e.g. ``build_building_seats``); ``reset=False``
        returns the existing payload so later producers merge into it.
        """
        if reset or name not in self._data:
            return self.mint(name, kind, {}, replace=True)
        payload = self._data[name]
        if not isinstance(payload, dict):
            raise ValueError(f"artifact {name!r} is not a map payload")
        return payload

    # ── introspection ──────────────────────────────────────────────────
    def has(self, name: str) -> bool:
        return name in self._data

    def raw(self, name: str) -> Any:
        """The keyed payload as minted, or ``None`` if absent."""
        return self._data.get(name)

    def mint_count(self, name: str) -> int:
        return self._mints.get(name, 0)

    # ── the one resolver ───────────────────────────────────────────────
    def view_interval(self, name: str, b2i: Mapping[Any, int], n: int, *,
                      crown_of: Optional[Mapping[int, float]] = None,
                      combine: str = "last") -> Dict[int, Interval]:
        """Resolve an interval artifact into an index space.

        ``combine`` fixes alias-collision semantics (two keys resolving
        to one index): ``"intersect"`` keeps the tightest per side
        (``max lo, min hi`` — the seat-box rule), ``"last"`` overwrites
        in mint insertion order (the band rule).  ``crown_of`` lifts
        each interval into the pass's z′ = z + crown frame; the lift is
        per-index, so lift-then-combine equals combine-then-lift.
        Absent artifact → empty dict.
        """
        payload = self._data.get(name)
        out: Dict[int, Interval] = {}
        if not payload:
            return out
        if combine not in ("last", "intersect"):
            raise ValueError(f"unknown combine mode {combine!r}")
        for key, (lo, hi) in payload.items():
            i = b2i.get(key)
            if i is None or i >= n:
                continue
            c = crown_of.get(i, 0.0) if crown_of else 0.0
            box = (lo + c, hi + c)
            prev = out.get(i)
            if prev is not None and combine == "intersect":
                box = (max(prev[0], box[0]), min(prev[1], box[1]))
            out[i] = box
        return out

    def view_scalar(self, name: str, b2i: Mapping[Any, int], n: int, *,
                    crown_of: Optional[Mapping[int, float]] = None,
                    ) -> Dict[int, float]:
        """Resolve a scalar artifact into an index space.

        Same resolution semantics as :meth:`view_interval`: a key absent
        from ``b2i``, or resolving to an index ``>= n``, is skipped, and
        ``crown_of`` lifts each value into the pass's z′ = z + crown
        frame.  Alias collisions are last-write-wins in mint insertion
        order, which is immaterial for the R1 reference field: it mints
        one value per canonical key, so two keys never carry different
        values for one node.  Absent artifact → empty dict.
        """
        payload = self._data.get(name)
        out: Dict[int, float] = {}
        if not payload:
            return out
        for key, value in payload.items():
            i = b2i.get(key)
            if i is None or i >= n:
                continue
            c = crown_of.get(i, 0.0) if crown_of else 0.0
            out[i] = float(value) + c
        return out

    def view_positional_interval(
            self, name: str, b2i: Mapping[Any, int], n: int, *,
            crown_of: Optional[Mapping[int, float]] = None,
    ) -> Optional[List[Optional[Interval]]]:
        """Resolve an interval artifact to a positional list of length
        ``n`` (the envelope's shape), ``None`` where no key resolved.

        Absent OR EMPTY artifact → ``None`` (the "no carry ⇒ pair
        closure" contract at the envelope call site).  Alias collisions
        are last-write-wins in mint insertion order.
        """
        payload = self._data.get(name)
        if not payload:
            return None
        out: List[Optional[Interval]] = [None] * n
        for key, (lo, hi) in payload.items():
            i = b2i.get(key)
            if i is None or i >= n:
                continue
            c = crown_of.get(i, 0.0) if crown_of else 0.0
            out[i] = (lo + c, hi + c)
        return out

    def view_keyset(self, name: str, b2i: Mapping[Any, int],
                    n: int) -> Set[int]:
        """Resolve a keyset artifact into an index set (absent → empty)."""
        payload = self._data.get(name)
        if not payload:
            return set()
        out: Set[int] = set()
        for key in payload:
            i = b2i.get(key)
            if i is not None and i < n:
                out.add(i)
        return out

    def view_relation(self, name: str, b2i: Mapping[Any, int],
                      n: int) -> Dict[int, Optional[int]]:
        """Resolve a key→key relation into index space.

        The LEFT side must resolve (< ``n``) for the pair to appear;
        the RIGHT side resolves to an index or ``None`` (the consumer
        decides what an unresolved right side means — the pad-weld
        site's per-side guards).  Absent → empty dict.
        """
        payload = self._data.get(name)
        out: Dict[int, Optional[int]] = {}
        if not payload:
            return out
        for lk, rk in payload.items():
            li = b2i.get(lk)
            if li is None or li >= n:
                continue
            ri = b2i.get(rk)
            out[li] = ri if (ri is not None and ri < n) else None
        return out


def store_of(layout: Any) -> NodeSpaceStore:
    """The layout's store, created on first use (one per build)."""
    store = getattr(layout, "_node_space", None)
    if store is None:
        store = NodeSpaceStore()
        layout._node_space = store
    return store
