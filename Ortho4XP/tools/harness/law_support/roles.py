"""The ROLE VOCABULARY and the authority order the census reads.

COPIED from ``layout.py, strips.py`` on 2026-09-17 (lane ``v1retire`` round 1, ruling (d)
of the stage-B brief: "the census stays engine-neutral BY IMPLEMENTATION").
`tools/check_grade.py` priced v2 patches with law machinery that lived in
modules the v1 deletion takes; what it USES is copied here ONCE, verbatim, and
the census reads it from the harness.  Values that are law live in
``auto_patch/config.py`` (KEEP) or ``auto_patch_v2/law/*.toml`` and are
IMPORTED, never re-spelled.

Do not edit to change behaviour: this is a transcription, and the acceptance
was a census A/B on the same HECA patch bytes reading IDENTICAL.
"""

from __future__ import annotations



SHARED_VERTEX_TOL_M = 0.5    # snap vertices closer than this together


ROLE_RUNWAY = "runway"


ROLE_BUILDING = "building"


ROLE_JUNCTION = "junction"


ROLE_RUNWAY_CROSSING = "runway_crossing"


ROLE_TUNNEL_RAMP = "tunnel_ramp"


ROLE_GROUNDSIDE_PAVEMENT = "groundside_pavement"


ROLE_SERVICE_ROAD = "service_road"


ROLE_SERVICE_JUNCTION = "service_junction"


GROUNDSIDE_ROLES: frozenset = frozenset({
    ROLE_GROUNDSIDE_PAVEMENT, ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION,
    ROLE_TUNNEL_RAMP,
})


ROLE_APRON = "apron"


ROLE_CROSS_CONNECTOR = "cross_connector"


ROLE_PRIMARY_PARALLEL = "primary_parallel"


ROLE_SECONDARY_PARALLEL = "secondary_parallel"


ROLE_STUB = "stub"


AUTHORITY_PRECEDENCE: tuple[str, ...] = (
    # runway family
    ROLE_RUNWAY, ROLE_RUNWAY_CROSSING,
    # taxi family
    ROLE_PRIMARY_PARALLEL, ROLE_SECONDARY_PARALLEL, ROLE_STUB,
    ROLE_CROSS_CONNECTOR, ROLE_JUNCTION, ROLE_TUNNEL_RAMP,
    # apron, then landside occupants
    ROLE_APRON, ROLE_BUILDING,
    ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION,
    ROLE_GROUNDSIDE_PAVEMENT,
)


AUTHORITY_RANK: dict[str, int] = {
    _r: _i for _i, _r in enumerate(AUTHORITY_PRECEDENCE)
}


_AUTHORITY_RANK_UNNAMED = len(AUTHORITY_PRECEDENCE)


def authority_rank(role: str) -> int:
    """Precedence rank of ``role`` (lower wins).  Unnamed roles tail."""
    return AUTHORITY_RANK.get(role, _AUTHORITY_RANK_UNNAMED)

