"""THE MOUTH IS MEASURED FROM THE COVER (owner RULINGS 2026-10-28k, spec
``docs/specs/lfpg-cuts-tunnels-rules-spec.md`` R1/R4/R5; amends 2026-10-14f
and 2026-10-27g for a credible survey) — the ONE reading of an unauthored
OSM bore mouth's floor on a CREDIBLE inset.

A mouth's floor is the ground over it less ``mouth_depth_m`` (14f).  On a
lidar terrain model "the ground over the mouth" is two different things.
Where the survey's open approach trench reaches the mapped portal, the DEM
at the mouth's cap IS that trench's floor — the road — and 7.5 m under it
cut the road a second time (measured LFPG, 1.0.436: 14 of 30 auto ramps
deeper than 3 m stood in a survey cut of 3–7 m, portal depths to 17 m
against the owner's 6–9 m).  And where the survey reads the road THROUGH a
deck (it drops the structure as it drops a bridge), the DEM on the bore is
the road too.  So the depth is read from the COVER, never from ground
already inside the cut:

* ``cover`` — the higher of the SURROUNDING GROUND (226 a: "judged by
  depth below the surrounding ground": the upper quartile of the survey
  ``_RING_M`` around the portal — a dual carriageway's trench is wider than
  either side's reach) and the cover OVER THE BORE (the median, over the
  bore's first ``_COVER_M`` inside the portal, of the higher of the survey
  on the bore's axis and the lower of the two sides' highest ground within
  four ``mouth_depth_m`` — §45's ``channel_geometry._lidar_cut`` reading,
  ratified 2026-09-16g — which reads a deck the survey looks through);
* ``road`` — the survey's road at the portal: the least of §45's
  ``_lidar_floor`` (the minimum across the carriageway) over the portal and
  the approach's first ``_ROAD_M``;
* ``clearance = cover − road``.

THE RULES (2026-10-28k, read with the questions as asked):

* **No sign, no cut (232 a).**  ``clearance`` under ``[channel]
  object_min_depth_m``: neither the survey nor a ground rise shows a cut,
  and the mouth is refused by name.  (A coarse DEM never reads here: a 7 m
  trench is below its grid, so a missing rise is no evidence and 14f
  stands.)
* **The depth owed.**  UNDER AIRSIDE PAVEMENT — a runway, taxi or apron
  cell over the bore (an airside value role that is not a building pad) —
  every road goes to the 7.5 m mouth depth under the cover (231 b, read by
  the session as "every road under pavement goes to the 7.5 m mouth depth
  unless an object states another value"; measured against the owner's
  LFPG patch, his T1 and 2E/2F roads stand 7–9 m under the aprons where the
  survey reads 5.7–7.1).  Elsewhere (under ground, a building, a groundside
  road) a road already clearing ``[tunnel] clearance_m`` under its cover is
  kept and a shallower one is cut to it (232 a "no cut where the road
  already clears 5 m"; 27g's blend).  A RAIL bore is never deepened (233 a:
  rail follows the survey).
* ``floor = min(road, cover − owed)``.  Where that floor IS the surveyed
  road (within ``[placement] split_tol_m``), the survey already carries the
  road and nothing is cut a second time: the mouth is refused by name.
  Otherwise the mouth is built at the floor and the ramp closes the depth
  owed ALONG THE SURVEYED ROAD (R4, :func:`survey_design_grade`).

R2 — A SURVEYED OPEN CUT IS CARRIED INTO THE SURFACE (230 a "survey cuts
are kept").  A mouth the survey decides no longer builds the corridor whose
outer ring the adjacent-ground zones stopped at (``planar/zones.
zone_regions`` subtracts every structure keepout), so the zones would now
grade across the very trench the survey carries (measured CYXY
``tunnel:-725``: kept 6.2 m under its cover, and the strip zone took its
approach).  :func:`survey_trench` is that open approach trench — the
approach from the portal out to where the surveyed road has come up to
within ``[channel] object_min_depth_m`` of the cover — never longer than the
design ramp the old law built there (``clearance / ramp_grade``) — as wide
as the carriageway plus the rim stand-off plus a 1:1 bank — and it is a KEEPOUT
like a corridor's.  The other §4.2 "filled" sites at LFPG are not this
class (base replay, ``v2_solve_replay --why-at``): the Roissypole primary
road's open approach (49.0109, 2.5509; the bore's east end is "no portal",
#1028) and the 2A south service portal (49.0029, 2.5543) are held by a
taxiway's adjacent-ground zone (``graded_strip``, zone 1 / 2 — the
objective and ``zones.adjacent_ground``), and the A1 north portal
(49.0263, 2.5367) by the hard deck's datum (22n, R3); neither the road
grade cap nor any row of this module.

An object that states a value keeps it (231 b "except where an object
would indicate a different value"): a pack portal, a wall object, a door
well or a wall corridor never reaches this reading (the caller skips it),
and an object deck over the ramp keeps its ``bridge.clearance_m`` band.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import statistics
import typing as _t

from ..airport.dem import dem_z_at
from ..law import Law
from ..law.tables import is_value_role, role_family, role_side
from ..model.frame import XY
from .channel_geometry import _lidar_cut, _lidar_floor

__all__ = ["survey_mouth", "survey_design_grade", "under_airside_pavement",
           "is_rail_group", "survey_mouth_refusal", "survey_mouth_note", "survey_trench",
           "survey_road_trenches", "end_clearance"]

#: the station step along the bore (the §45 cut reading's own lateral step)
_STEP_M = 5.0
#: the cover is read over the bore's first this far inside the portal (the
#: spec's "first 10–40 m": past the cap's stand-off, before a long bore's
#: interior can stand for its mouth)
_COVER_M = 40.0
#: the surrounding ground's annulus around the portal (m) and its quantile
#: (the spec's §2 crest: the 75th percentile of the surface 25–60 m around)
_RING_M = (25.0, 60.0)
_RING_Q = 0.75
#: the annulus's sampling: radial step (m) and angular step (degrees)
_RING_STEP_M, _RING_DEG = 5.0, 10.0
#: the road is read at the portal and over the approach's first this far
#: (the spec's portal floor "within 12 m")
_ROAD_M = 12.0
#: the road's stations along the approach
_ROAD_STEP_M = 2.0
#: refusal verdicts
NO_SIGN, KEPT = "no_sign", "kept"


def _bore_fn(points: _t.Sequence[XY], portal: XY):
    """The bore's line as ``s -> xy`` from its end at ``portal`` inward."""
    from shapely.geometry import LineString, Point
    ln = LineString(points)
    head = Point(points[0]).distance(Point(portal)) <= Point(points[-1]).distance(Point(portal))
    length = ln.length

    def fn(s: float) -> XY:
        q = ln.interpolate(max(0.0, min(length, s if head else length - s)))
        return (q.x, q.y)
    return fn, length


def _cover_stations(length: float, start_m: float) -> list[float]:
    """The bore's stations from the cap's stand-off to ``_COVER_M`` in (a
    short bore: to its middle, so its two mouths read their own halves)."""
    hi = min(start_m + _COVER_M, max(start_m, length / 2.0))
    n = max(1, int((hi - start_m) // _STEP_M) + 1)
    return [start_m + (hi - start_m) * k / max(1, n - 1) for k in range(n)] if n > 1 \
        else [min(start_m, length / 2.0)]


@_dc.dataclass(frozen=True)
class SurveyMouth:
    """The credible survey's reading of one mouth (module doc): ``cover``
    the cover's level over the bore, ``road`` the surveyed road at the
    portal, ``owed`` the depth the road must stand under the cover
    (7.5 m under airside pavement, 5 m elsewhere, 0 for rail), ``floor``
    the mouth's floor, ``verdict`` ``""`` (built) / :data:`NO_SIGN` /
    :data:`KEPT`."""
    cover: float
    road: float
    owed: float
    floor: float
    paved: bool
    rail: bool
    verdict: str

    @property
    def clearance(self) -> float:
        return self.cover - self.road

    @property
    def extra(self) -> float:
        """The depth cut under the surveyed road at the mouth."""
        return max(0.0, self.road - self.floor)


def is_rail_group(members: _t.Sequence) -> bool:
    """A railway bore (233 a): any member way tagged ``railway``."""
    return any("railway" in (w.tags or {}) for m in members
               for w in getattr(getattr(m, "bore", None), "ways", ()))


def under_airside_pavement(members: _t.Sequence, cells, tree, law: Law,
                           odecks: _t.Sequence = ()) -> bool:
    """Whether a runway, taxi or apron cell (an airside value role of the
    runway, taxi or common family that is not a building pad) — or a pack
    HARD-DECK object (``basins.object_decks``: the deck carries the airside
    over a road; LFPG's A1 bores under 09R/27L run under the decks, under no
    cell) — stands over any member's bore (231 b's "a road under pavement":
    the bore passes under it anywhere — a portal stands off the runway
    strip, never under it)."""
    from shapely.geometry import LineString
    for m in members:
        bore = getattr(m, "bore", None)
        if bore is None or len(bore.points) < 2:
            continue
        line = LineString(bore.points)
        if any(dp.intersects(line) for _oid, dp, _top in odecks):
            return True
        if tree is None:
            continue
        for j in tree.query(line, predicate="intersects"):
            c = cells[int(j)]
            if c.role != "building" and role_side(law, c.role) == "airside" \
                    and is_value_role(law, c.role) \
                    and role_family(law, c.role) in ("runway", "taxi", "common"):
                return True
    return False


def _bore_cover(airport, law: Law, points: _t.Sequence[XY], end: XY, start_m: float
                ) -> list[float]:
    """The cover's levels over one bore's first stations inside ``end``: per
    station the higher of the axis survey and §45's lower-side top."""
    reach = 4.0 * float(law.tables.structures.tunnel.mouth_depth_m)
    fn, length = _bore_fn(points, end)
    rows: list = []
    ss = _cover_stations(length, start_m)
    _lidar_cut(airport, law, fn, ss, reach, rows)
    tops = {round(s, 6): top for s, _flr, top in rows}
    vals: list[float] = []
    for s in ss:
        z = dem_z_at(airport, fn(s))
        top = tops.get(round(s, 6), math.nan)
        got = [v for v in (z, top) if not math.isnan(v)]
        if got:
            vals.append(max(got))
    return vals


def _cover(airport, law: Law, members: _t.Sequence, start_m: float) -> float:
    """The cover's level over the group's bores (module doc)."""
    vals: list[float] = []
    for m in members:
        bore = getattr(m, "bore", None)
        if bore is None or len(bore.points) < 2:
            continue
        vals.extend(_bore_cover(airport, law, bore.points, m.xy, start_m))
    return statistics.median(vals) if vals else math.nan


def end_clearance(airport, law: Law, points: _t.Sequence[XY], end: XY, width: float,
                  start_m: float) -> float:
    """R1's clearance at one mapped END of a way chain (``points``): the
    cover (the over-bore reading and the surrounding ground, as
    :func:`survey_mouth`) less the surveyed road on the straight line out
    of ``end`` — the cut a covered road's end stands in (RULINGS
    2026-10-28s (5), ``planar/covered_bores``).  ``nan`` where the survey
    reads nothing."""
    if len(points) < 2:
        return math.nan
    vals = _bore_cover(airport, law, points, end, start_m)
    got = [v for v in (statistics.median(vals) if vals else math.nan,
                       _surround(airport, end)) if not math.isnan(v)]
    if not got:
        return math.nan
    a, b = (points[1], points[0]) if end == points[0] else (points[-2], points[-1])
    L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
    d = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
    road = _road(airport, lambda s: (end[0] + d[0] * s, end[1] + d[1] * s), width)
    return math.nan if math.isnan(road) else max(got) - road


def _surround(airport, xy: XY) -> float:
    """The surrounding ground: the upper quartile of the survey on the
    annulus ``_RING_M`` around the portal ``xy`` (module doc)."""
    zs: list[float] = []
    r = _RING_M[0]
    while r <= _RING_M[1] + 1e-9:
        for k in range(int(360.0 / _RING_DEG)):
            a = math.radians(k * _RING_DEG)
            z = dem_z_at(airport, (xy[0] + r * math.cos(a), xy[1] + r * math.sin(a)))
            if not math.isnan(z):
                zs.append(z)
        r += _RING_STEP_M
    if not zs:
        return math.nan
    zs.sort()
    return zs[min(len(zs) - 1, int(round(_RING_Q * (len(zs) - 1))))]


def _road(airport, axis_fn, width: float) -> float:
    """The surveyed road at the portal (module doc)."""
    zs = [_lidar_floor(airport, axis_fn, k * _ROAD_STEP_M, max(width, 1.0))
          for k in range(int(_ROAD_M // _ROAD_STEP_M) + 1)]
    zs = [z for z in zs if not math.isnan(z)]
    return min(zs) if zs else math.nan


def survey_mouth(airport, law: Law, members: _t.Sequence, axis_fn, width: float,
                 credible: bool, start_m: float, paved: bool) -> SurveyMouth | None:
    """The credible survey's reading of the group's mouth, or ``None`` on a
    coarse DEM / where the survey reads nothing (14f stands).  ``axis_fn``
    is the approach from the MAPPED portal outward, ``width`` the
    carriageway's, ``start_m`` the cap's stand-off inside the portal, and
    ``paved`` :func:`under_airside_pavement`'s verdict."""
    if not credible or not members:
        return None
    tn = law.tables.structures.tunnel
    over = _cover(airport, law, members, start_m)
    ring = _surround(airport, axis_fn(0.0))
    got = [v for v in (over, ring) if not math.isnan(v)]
    cover = max(got) if got else math.nan
    road = _road(airport, axis_fn, width)
    if math.isnan(cover) or math.isnan(road):
        return None
    rail = is_rail_group(members)
    owed = 0.0 if rail else float(tn.mouth_depth_m if paved else tn.clearance_m)
    floor = min(road, cover - owed)
    verdict = ""
    if cover - road < float(law.tables.structures.channel.object_min_depth_m):
        verdict = NO_SIGN
    elif road - floor <= float(law.tables.structures.placement.split_tol_m):
        verdict = KEPT
    return SurveyMouth(cover, road, owed, floor, paved, rail, verdict)


def survey_design_grade(airport, law: Law, axis_fn, sm: SurveyMouth, design: float,
                        cap: float) -> float:
    """R4 — THE RAMP LIES WHERE THE SURVEY DESCENDS: the design grade of a
    ramp built at a survey mouth's floor, ``extra`` under the surveyed road.
    The climb closes that depth at ``design`` RELATIVE TO THE SURVEYED ROAD:
    the road's own rise over the closing length plus ``design``, never
    above ``cap``.  On a flat approach it is ``design`` (unchanged); where
    the survey's trench descends to the mouth, the ramp follows it instead
    of cutting under it for a design ramp's length."""
    if sm.extra <= 0.0 or design <= 0.0:
        return design
    run = max(_ROAD_STEP_M, sm.extra / design)
    z0, z1 = dem_z_at(airport, axis_fn(0.0)), dem_z_at(airport, axis_fn(run))
    rise = 0.0 if math.isnan(z0) or math.isnan(z1) else max(0.0, (z1 - z0) / run)
    return min(cap, design + rise)


def survey_trench(airport, law: Law, sm: SurveyMouth, axis_line, width: float,
                  rim_off: float):
    """R2 — the open approach trench the survey shows at a mouth it decides
    (module doc), as a polygon, or ``None`` where the survey reads no cut
    (a :data:`NO_SIGN` mouth) or the trench is shorter than one station.
    ``axis_line`` is the approach from the MAPPED portal outward."""
    if sm.verdict == NO_SIGN or axis_line is None or axis_line.length <= 0.0:
        return None
    from shapely.ops import substring
    tn = law.tables.structures.tunnel
    top = sm.cover - float(law.tables.structures.channel.object_min_depth_m)
    # never longer than the design ramp the old law built there (the
    # corridor whose keepout this replaces): clearance / ramp_grade
    lim = min(axis_line.length, float(tn.max_ramp_length_m),
              max(0.0, sm.clearance) / float(tn.ramp_grade))
    s = 0.0
    while s + _ROAD_STEP_M <= lim:
        q = axis_line.interpolate(s + _ROAD_STEP_M)
        z = dem_z_at(airport, (q.x, q.y))
        if math.isnan(z) or z >= top:
            break
        s += _ROAD_STEP_M
    if s < _ROAD_STEP_M:
        return None
    bank = min(max(0.0, sm.clearance), 2.0 * float(tn.mouth_depth_m))
    g = substring(axis_line, 0.0, s).buffer(width / 2.0 + rim_off + bank, cap_style="flat")
    return g if g.geom_type == "Polygon" and not g.is_empty else None


def survey_road_trenches(airport, law: Law, carriageways, region) -> tuple:
    """Q245 (owner 2026-10-27, "Yes") — A TAXIWAY'S ZONE GIVES WAY TO A
    TRENCH THE SURVEY SHOWS INSIDE IT.  The open cuts of R2 that no mouth
    decides (a bore end with no portal, #1028; an approach the survey
    carries through a taxiway's graded strip): every stretch of a mapped
    road (``carriageways``: ``road_yield.road_carriageways``) inside
    ``region`` (the taxiway bands; read one cut reach beyond them) along
    which the credible survey reads a
    both-sides cut — §45's ``_lidar_cut`` reading, ratified 2026-09-16g,
    over at least two consecutive stations — as a polygon as wide as the
    carriageway plus the rim stand-off plus a 1:1 bank (capped as
    :func:`survey_trench` caps it).  ``()`` on a coarse DEM, where a 7 m
    trench is below the grid and no cut is evidence (14f stands)."""
    if airport is None or region is None or region.is_empty or not carriageways:
        return ()
    from ..law import inset_class
    if not inset_class.lidar_credible(airport, law):
        return ()
    from shapely.ops import substring
    tn = law.tables.structures.tunnel
    reach = 4.0 * float(tn.mouth_depth_m)
    rim_off = float(tn.wall_gap_m) + float(tn.wall_band_width_m)
    # the road is read across the band and one cut reading's reach beyond it:
    # a band is a few metres wide, and a trench crossing it is read where
    # it runs (the polygon cuts only the band it overlaps)
    near = region.buffer(reach)
    out: list = []
    for line, half in carriageways:
        if not line.intersects(region):
            continue
        piece = line.intersection(near)
        for seg in getattr(piece, "geoms", (piece,)):
            if seg.geom_type != "LineString" or seg.length < _STEP_M:
                continue
            n = int(seg.length // _STEP_M) + 1
            ss = [seg.length * k / (n - 1) for k in range(n)]

            def fn(s: float, _ln=seg) -> XY:
                q = _ln.interpolate(max(0.0, min(_ln.length, s)))
                return (q.x, q.y)
            run: list[tuple[float, float]] = []      # (station, depth) of the open run
            for s in ss + [math.inf]:
                rows: list = []
                cut = s != math.inf and _lidar_cut(airport, law, fn, [s], reach, rows)
                if cut:
                    run.append((s, rows[-1][2] - rows[-1][1]))
                    continue
                if len(run) >= 2:
                    bank = min(max(d for _s, d in run), 2.0 * float(tn.mouth_depth_m))
                    g = substring(seg, run[0][0], run[-1][0]).buffer(
                        float(half) + rim_off + bank, cap_style="flat")
                    if g.geom_type == "Polygon" and not g.is_empty:
                        out.append(g)
                run = []
    return tuple(out)


def survey_mouth_refusal(sm: SurveyMouth) -> str:
    """The refusal line of a mouth the survey decides (module doc)."""
    if sm.verdict == NO_SIGN:
        return (f"the credible survey shows no cut: the cover over the bore {sm.cover:.2f} "
                f"stands {sm.clearance:.2f} m over the road at the portal {sm.road:.2f} "
                f"(< [channel] object_min_depth_m) — neither the survey nor a ground rise "
                f"shows one, and nothing is cut (RULINGS 2026-10-28k (232 a))")
    what = ("rail follows the survey" if sm.rail else
            f"it clears the {sm.owed:.2f} m owed "
            f"({'under airside pavement, 231 b' if sm.paved else 'clearance_m, 232 a'})")
    return (f"the credible survey carries the road: {sm.road:.2f} at the portal, "
            f"{sm.clearance:.2f} m under the cover {sm.cover:.2f} over the bore — {what}; "
            f"nothing is cut a second time (RULINGS 2026-10-28k (226 a))")


def survey_mouth_note(sm: SurveyMouth, grade: float) -> str:
    """The tunnel note of a mouth built at a survey floor."""
    why = "under airside pavement (231 b)" if sm.paved else "clearance_m (232 a)"
    return (f"survey mouth: cover {sm.cover:.2f} over the bore, surveyed road {sm.road:.2f} "
            f"at the portal ({sm.clearance:.2f} m) — owed {sm.owed:.2f} m {why}: floor "
            f"{sm.floor:.2f}, {sm.extra:.2f} m under the surveyed road, closing along it at "
            f"{100.0 * grade:.1f} % (RULINGS 2026-10-28k R1/R4; never mouth_depth_m under "
            f"ground already inside the cut)")
