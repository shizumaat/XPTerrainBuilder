"""GROUNDSIDE GRADES TO ITS LAW; THE DEM IS ONLY A SEED.

Fix cycle 2, item 2.  Owner law (docs/RULINGS.md 2026-08-05, "DEM's role,
and the constant-DEM invariant"): *DEM chooses WHERE in the lawful band a
thing seats.  It never shapes the band, never constrains, never blocks.*

WHAT WAS MEASURED (the mechanism, not a code reading).
``tools/harness/who_wrote.py HEAZ --dem 10000`` named the introducing
writer of every vertex sitting exactly on the constant DEM — 298 of them:

    168  service_junction     solve.py:_writeback  (LAW ISLANDS, below)
     92  groundside_pavement  groundside._merge_touching_groundside
     25  groundside_pavement  pipeline (the primary lot emit)
     13  groundside_pavement  groundside._separate_groundside_from_airside

All three groundside authors go through ``_dem_follow_polygon``, which
sampled the DEM at every vertex and ring-limited the result.  That is a
DEM DRAPE with a smoother on it: the terrain is the authority and the law
is a post-filter.  The welds are then overwritten at emit by the
higher-authority claimant (``to_osm``'s precedence resolution, which is
correct), so one lot ships with its weld vertices on the LAW and its
interior on the TERRAIN.

Measured in the emitted canyon patch, HEAZ way -10281 (63 nodes):

    17 weld nodes  ......  85.56 - 91.70 m   (service_junction values)
    47 interior nodes  ...  10 000.00 m      (raw constant DEM)
    within_shape step  ...  9 914.44 m       <- the campaign's worst row
                                                in BOTH flat worlds

A RING LIMITER CANNOT FIX THIS, and the arithmetic is the argument: at the
5 % lot cap over a 15 m densify step an edge may fall 0.75 m, so closing
9 914 m needs ~13 000 edges and the ring has 63.  Capping the SLOPE of a
surface whose DATUM is wrong only spreads the error out.  The datum must
come from the law — which is what this module's twins pin.

LAW ISLANDS ARE NOT FIXED BY THIS, deliberately.  A shape with NO weld to
any higher-authority surface (HEAZ canyon: ways -10033, -10034, -10066,
``sharedWithHigher=0``) has nothing to grade to.  Inventing a datum for it
would be minting.  Those shapes emit internally FLAT under a constant DEM
and produce no ``within_shape`` row, so they are not the worst-row class;
they are the separate law-island population and are attributed, not
papered over.
"""


_CAP = 0.05                      # GROUNDSIDE_MAX_GRADE (owner 2026-08-03)


# ══════════════════════════════════════════════════════════════════════
# THE DATUM
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# THE ANCHOR SOURCE — the emitter's own precedence order
# ══════════════════════════════════════════════════════════════════════


# ── R7b: A ROAD NEVER WELDS TO A BUILDING (owner 2026-08-15) ─────────


def test_the_near_miss_frontage_law_no_longer_names_a_ROAD():
    """The second pad→road channel: the near-miss law is a WELD across a
    sliver, so a road on its soft-role list is a road welded to a
    building at one remove."""
    from auto_patch import config as cfg
    assert "service_junction" not in cfg.NEAR_MISS_FRONTAGE_SOFT_ROLES
    assert "apron" in cfg.NEAR_MISS_FRONTAGE_SOFT_ROLES
    assert "junction" in cfg.NEAR_MISS_FRONTAGE_SOFT_ROLES


# ══════════════════════════════════════════════════════════════════════
# THE PINNED RING LIMITER
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# CYCLE-6 INGESTION — one identity, the ladder, and the named island
# ══════════════════════════════════════════════════════════════════════


