"""THE OSM-LEVEL CROSSING CLASSIFIER.

Redesign spec ``docs/specs/linear-transport-redesign-spec.md`` §4, last
clause; RULINGS 2026-08-31a ("the OSM-level crossing classifier
(layer/bridge/tunnel tags + shared-node same-level rule)") and the
2026-08-31 post-mortem's restatement of the owner's bridge/crossing
policy:

    *OSM carries crossing levels:* ``layer=*``, ``bridge=*``,
    ``tunnel=*``; *shared nodes = same-level intersection (our road feed
    preserves these — measured* ``bridge=yes layer=1`` *at the LEMD
    crossing).*

TWO RULES, IN ORDER, AND THE ORDER IS THE LAW:

1. **A SHARED NODE IS A JUNCTION.**  Two ways that share an OSM node
   meet AT GRADE there, whatever their tags say.  A motorway carrying
   ``bridge=yes layer=1`` for a kilometre still has an at-grade slip
   junction with the road it shares a node with; reading the tags first
   would call that junction a span and put a deck over a road the driver
   turns onto.  The rule is checked on IDENTITY — the feed's own node
   ids — never on proximity (memory ``canonical-identity-join``).
2. **OTHERWISE THE TAGS ORDER THE CROSSING.**  ``layer`` wins where it
   is present and parseable (it is the explicit statement); with no
   layer, ``bridge`` reads +1 and ``tunnel`` reads −1, which is the
   convention :func:`bridges._has_tunnel_tag_evidence` already applies to
   the below-grade half.  Equal levels ⇒ same level.

BUILT ON THE EXISTING TAG MACHINERY (census #42): the ``tunnel`` value
set and the layer parse come from :mod:`auto_patch.bridges`, and the
bridge test from :mod:`auto_patch.road_bridge_deck` — this module adds an
ORDERING over them, never a second spelling of "is this a tunnel".
"""
from __future__ import annotations

from typing import Iterable, Optional

#: The three verdicts.  ``SAME`` also covers "both at layer 0".
SAME = "same"
A_ABOVE = "a_above"
B_ABOVE = "b_above"


def parse_layer(tags: Optional[dict]) -> Optional[float]:
    """``layer`` as a number, or ``None`` when absent/unparseable.

    ONE parse, shared with ``bridges._has_tunnel_tag_evidence``'s own
    (``float(str(layer).split(";")[0])`` — OSM ways carry ``layer=0;1``
    on some multi-level ways and the FIRST value is this way's).
    """
    raw = (tags or {}).get("layer")
    if raw is None:
        return None
    try:
        return float(str(raw).split(";")[0])
    except (TypeError, ValueError):
        return None


def way_level(tags: Optional[dict]) -> float:
    """The way's OSM level.

    ``layer`` where it is stated; otherwise +1 for a bridge, −1 for a
    tunnel, 0 for ordinary ground.  A way tagged ``bridge=no`` /
    ``tunnel=no`` is ordinary ground — the same truthy-value reading the
    core's exclusion set and ``road_bridge_deck._way_is_bridge`` use, so
    "the key is present" is never mistaken for "the feature is there".
    """
    from .bridges import TUNNEL_VALUES
    from .road_bridge_deck import _way_is_bridge

    layer = parse_layer(tags)
    if layer is not None:
        return layer
    if _way_is_bridge(tags):
        return 1.0
    if (tags or {}).get("tunnel") in TUNNEL_VALUES:
        return -1.0
    return 0.0


def shares_a_node(nrefs_a: Iterable, nrefs_b: Iterable) -> bool:
    """Rule 1's test: do the two ways share an OSM node id?"""
    a = set(nrefs_a or ())
    if not a:
        return False
    return bool(a & set(nrefs_b or ()))


def classify(tags_a: Optional[dict], nrefs_a: Iterable,
             tags_b: Optional[dict], nrefs_b: Iterable) -> str:
    """Order a crossing: :data:`SAME`, :data:`A_ABOVE` or
    :data:`B_ABOVE`.

    Rule 1 first (a shared node is a junction), then rule 2 (the tags
    order it).  This function makes no geometric claim: the CALLER
    decides that two ways cross at all.
    """
    if shares_a_node(nrefs_a, nrefs_b):
        return SAME
    la, lb = way_level(tags_a), way_level(tags_b)
    if la > lb:
        return A_ABOVE
    if lb > la:
        return B_ABOVE
    return SAME


def spans_over(tags_a: Optional[dict], nrefs_a: Iterable,
               tags_b: Optional[dict], nrefs_b: Iterable) -> bool:
    """Does way A pass OVER way B — the question a deck candidate asks?"""
    return classify(tags_a, nrefs_a, tags_b, nrefs_b) == A_ABOVE
