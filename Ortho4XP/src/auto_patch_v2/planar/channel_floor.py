"""§45 (3) THE OPEN CHANNEL'S FLOOR DATUM — the ruled precedence, then
"Cut the road down" (spec §45 (3); owner RULINGS 2026-09-15i, amended
2026-09-15s/bo/16g) — lane ``v2channel``.

Its own module beside ``planar/channel.py`` for that file's 1,000-line
budget, and because the datum is one question with three answers the
ruling ORDERS: the pack's floor plates (i), a credible lidar inset that
reads the cut (ii), and the deck top less ``bridge.clearance_m`` with
the road's own law between the decks (iii).  ``planar/channel`` decides
who the channel IS; this decides how deep it runs.
"""
from __future__ import annotations

import math
import typing as _t

from ..law import Law
from ..model.airport import Airport
from ..model.structures import Deck
from ..airport.dem import dem_z_at
from .channel_geometry import _lidar_floor

__all__ = ["channel_floor", "visible_rejoined", "held_ends", "DATUM_PACK", "DATUM_LIDAR",
           "DATUM_CLEARANCE"]

#: §45 (3): the three floor DATUM sources, in the ruled precedence.
DATUM_PACK = "pack"            # (i)   the pack's floor plates along the axis
DATUM_LIDAR = "lidar"          # (ii)  a CREDIBLE lidar inset's DTM floor
DATUM_CLEARANCE = "clearance"  # (iii) deck top - bridge.clearance_m


def visible_rejoined(airport: Airport, law: Law, axis_ln, axis_fn, visible,
                     climbs: _t.Sequence = (), held: _t.Sequence = ()
                     ) -> tuple[tuple[float, float], ...]:
    """A visible cut's floor profile with its ends rejoined to the road
    running on (``planar/channel_depth.rejoin``, §45 (16)); an end that
    climbs out beyond a frame deck (#2127 R4 B3) takes its run-out first
    and the ``held`` stations under the deck are never raised."""
    from .channel_depth import climbed, rejoin
    return rejoin(climbed(tuple(visible), climbs), axis_ln.length,
                  lambda s: dem_z_at(airport, axis_fn(s)),
                  law.tables.structures.tunnel.ramp_max_grade,
                  law.tables.structures.channel.corridor_min_length_m, held)


def held_ends(airport: Airport, law: Law, cid: str, axis_ln, axis_fn,
              ends: tuple[float, float], vis, ss: _t.Sequence[float], step: float, stats):
    """#2127 R4 B3 (RULINGS 2026-11-17c), where the ends are set: ``(ends,
    climbs, held)`` — the axis stations under each deck piece of the cut's
    own frame (``VisibleFloor.decks``) widened by the wall band are HELD,
    and an end whose rejoin would climb into them climbs out beyond them
    instead (``planar/channel_depth.climb_out``) over the floor the visible
    cut states at that end.  Unchanged with no deck piece on the axis."""
    import numpy as np

    from .channel_depth import climb_out, held_intervals
    tn = law.tables.structures.tunnel
    held = held_intervals(axis_ln, getattr(vis, "decks", ()),
                          tn.wall_gap_m + tn.wall_band_width_m)
    pre = vis.profile(ss, step, tn.object.shell_flat_m) if held else None
    if not pre:
        return ends, (), held
    s_, z_ = [s for s, _z in pre], [z for _s, z in pre]
    end_z = (float(np.interp(ends[0], s_, z_)), float(np.interp(ends[1], s_, z_)))
    ends, climbs, notes = climb_out(ends, end_z, axis_ln.length,
                                    lambda s: dem_z_at(airport, axis_fn(s)), held, tn,
                                    law.tables.structures.channel.corridor_min_length_m)
    stats.notes.extend(f"{cid}: {n}" for n in notes)
    return ends, climbs, held


def channel_floor(airport: Airport, law: Law, cid: str, grp: _t.Sequence, axis_ln,
                  axis_fn, ss: list[float], decks: list[Deck], half: float,
                  objects: _t.Sequence, stats, packs: _t.Sequence[str] = (),
                  lidar: bool = False, visible=None, climbs: _t.Sequence = (),
                  held: _t.Sequence = ()):
    """§45 (3) THE FLOOR DATUM — precedence, then "Cut the road down".

    (i) the pack's floor plates along the axis; (ii) a CREDIBLE lidar
    inset (the DTM floor at each station); (iii) neither: under each deck
    the floor is the deck top − ``bridge.clearance_m`` and between decks
    the road's own longitudinal law clamped ≤ that datum and
    ≤ ``ramp_max_grade``.  Returns ``(profile, datum, wall shape, witness)``.

    (i) READ OFF A VISIBLE CUT (owner RULINGS 2026-11-06d (6)): where a
    hidden shell stood over the corridor, ``visible`` is the profile its
    visible members' bottoms state along the axis
    (``planar/channel_depth.VisibleFloor.profile``) and it IS the pack's floor — a
    profile, never one flat datum, and never the hidden shell's faces.

    The clamp is stated as ``min over decks of (z_d + grade·|s − s_d|)``,
    which IS "≤ that datum and ≤ ramp_max_grade" written once: two decks
    closer than ``2 × clearance / ramp_max_grade`` keep the floor down
    between them (KPHX's two stand 58 m apart against a 127.5 m reach, so
    the road never climbs between the terminals)."""
    ch = law.tables.structures.channel
    tn = law.tables.structures.tunnel
    br = law.tables.structures.bridge
    # the corridor's CREST estimate, used only to judge a pack witness's
    # depth and to report: the DEM along the axis outside the decks
    samples = [dem_z_at(airport, axis_fn(s)) for s in ss]
    good = [z for z in samples if not math.isnan(z)]
    crest_est = (sum(good) / len(good)) if good else float("nan")

    if visible:
        for c in grp:
            c.witnesses.add("pack")
        visible = visible_rejoined(airport, law, axis_ln, axis_fn, visible, climbs, held)
        zs = [z for _s, z in visible]
        stats.notes.append(f"{cid}: floor from the visible cut (§45 (3) (i), 2026-11-06d (6)) "
                           f"— the bottoms of the pack's members lying on it, "
                           f"{min(zs):.2f}..{max(zs):.2f} m over {len(visible)} station(s) "
                           f"against a crest of {crest_est:.2f}")
        return tuple(visible), DATUM_PACK, "face", "visible cut"
    # (i) THE PACK'S FLOOR PLATES — the SAME witness set the width (10)
    # (i) read, never a second read at a second radius
    packs = list(packs)
    floor_pack: float | None = None
    if packs:
        zs = [float(o.solid_min_z) for o in objects
              if str(getattr(o, "id", "")) in set(packs)
              and getattr(o, "solid_min_z", None) is not None]
        if zs:
            floor_pack = min(zs)
            for c in grp:
                c.witnesses.add("pack")
            profile = tuple((float(s), float(floor_pack)) for s in (ss[0], ss[-1]))
            stats.notes.append(f"{cid}: floor from the pack (§45 (3) (i)) — "
                               f"{len(set(packs))} placement(s), deepest genuine solid "
                               f"{floor_pack:.2f} m against a crest of {crest_est:.2f}")
            return profile, DATUM_PACK, "face", ",".join(sorted(set(packs))[:4])

    # (ii) A CREDIBLE LIDAR INSET **THAT READS THE CUT** (§45 (7): "Where
    # the DEM DOES see the cut (KDFW) it is the floor witness (3) (ii)")
    if lidar:
        prof = []
        for s in ss:
            z = _lidar_floor(airport, axis_fn, s, ch.lidar_floor_window_m)
            if not math.isnan(z):
                prof.append((float(s), float(z)))
        if len(prof) >= 2:
            stats.notes.append(f"{cid}: floor from a CREDIBLE lidar inset (§45 (3) (ii)) — "
                               f"{len(prof)} station(s), "
                               f"{min(z for _s, z in prof):.2f}..{max(z for _s, z in prof):.2f} m "
                               f"under a crest of {crest_est:.2f}")
            return tuple(prof), DATUM_LIDAR, "lidar", "lidar inset"

    # (iii) CUT THE ROAD DOWN
    anchors: list[tuple[float, float]] = []
    for d in decks:
        mid = (d.s0 + d.s1) / 2.0
        top = dem_z_at(airport, axis_fn(mid))
        if math.isnan(top):
            continue
        anchors.append((mid, top - br.clearance_m))
    if not anchors:
        stats.refused.append(f"{cid}: no deck top could be sampled — the DEM answers NaN "
                             f"at every crossing, so §45 (3) (iii) has no datum")
        return None, "", "bank", ""
    grade = tn.ramp_max_grade
    # THE DECK'S OWN STATION IS IN THE PROFILE.  Without it the datum
    # lands between two sampled stations and the floor reads the CLIMB's
    # value under the deck itself — measured on the twin: 95.30 against
    # the 94.90 the clearance states, one half-station of 8 % grade.
    stations = sorted(set(list(ss) + [sd for sd, _z in anchors]))
    prof = []
    # §45 (3) (iii) AS WRITTEN — "between decks the ROAD'S OWN
    # longitudinal law (§37) clamped ≤ that datum and ≤ ramp_max_grade"
    # (owner RULINGS 2026-09-17t, fix C; scout ``hecachannel``).  The
    # cone ``min over decks of (z_d + grade·|s − s_d|)`` is only the
    # ``≤ ramp_max_grade`` HALF of that sentence.  With the decks far
    # apart the two upward cones MEET in a Λ that climbs without limit,
    # and nothing in the code clamped it to where the road runs AT
    # GRADE: at LEMD ``channel:5`` the anchors (0, 583.90) and
    # (460, 580.90) peaked at s = 211.25, z = 600.80 — **11.90 m ABOVE**
    # a flat 5 m DTM (589 → 585) at the owner's read point, a "floor"
    # standing a four-storey building over the field.  The same Λ stands
    # in LEMD ``channel:1`` (603.9…625.1) and ``channel:2``; the shipped
    # tile carries 230 ``channel_floor_at_declaration`` rows.
    #
    # The road's own profile at a station where nothing cuts it down IS
    # the ground there, so the clamp is the DEM along the axis — the one
    # reading §37 (6)-(10) itself starts from, and the only one available
    # here without re-deriving the road pass.  A NaN sample clamps
    # nothing (the DEM is not a witness AGAINST a channel, §45 (7)); the
    # cone still holds under every deck, so the clearance under a
    # crossing is untouched and (d)'s "two decks 58 m apart keep the
    # floor down between them" is unchanged — that floor was already
    # under grade.
    capped = 0
    worst = 0.0
    for s in stations:
        z = float(min(zd + grade * abs(s - sd) for sd, zd in anchors))
        ground = dem_z_at(airport, axis_fn(s))
        if not math.isnan(ground) and z > ground:
            capped += 1
            worst = max(worst, z - ground)
            z = float(ground)
        prof.append((float(s), z))
    note = (f"{cid}: floor by §45 (3) (iii) \"Cut the road down\" — deck top − "
            f"bridge.clearance_m {br.clearance_m:.1f} m at {len(anchors)} crossing(s), the road's "
            f"own law between them clamped at ramp_max_grade {grade:.0%}; "
            f"{min(z for _s, z in prof):.2f}..{max(z for _s, z in prof):.2f} m")
    if capped:
        note += (f"; §45 (3) (iii) AMENDED (RULINGS 2026-09-17t) held "
                 f"{capped}/{len(stations)} station(s) at the road's own grade — "
                 f"the clearance cones would have stood {worst:.2f} m ABOVE it")
    stats.notes.append(note)
    return tuple(prof), DATUM_CLEARANCE, "bank", "bridge.clearance_m"
