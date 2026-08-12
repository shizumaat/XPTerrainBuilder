"""Pad-in-solved-pavement HOST LEVEL re-level (user 2026-07-10, round 6 site 3).

A building pad embedded in / abutting SOLVED pavement must sit FLAT at the level
the HOST pavement solved to at the contact — not at a raw-DEM frontage seat that
leaves the flat pad in a pit the apron humps around (CYXY apron #129 →
building8: a -333 %/1.1 m step, "a big hump in this apron").

Synthetic fixture (no airport build): an apron edge solved at a body level, a
flat pad abutting it seated at a PIT value (below the body), and a run of shared
"lip" apron nodes contaminated to the pit value.  The re-level must:

  * seat the pad FLAT at the host BODY level (adopt FROM the host);
  * lift the contaminated shared lip to the body level (no emit cliff);
  * leave the host BODY untouched (pad adopts from host, never the reverse);
  * leave a pad already agreeing with its host, and a pad far from any solved
    pavement, UNCHANGED;
  * honour the ``O4_PAD_HOST_PAVEMENT_LEVEL`` gate (off → no-op).
"""
import os

import pytest
from shapely.geometry import Polygon

from auto_patch.config import (
    PAD_HOST_LEVEL_TRIGGER_M, APRON_MAX_GRADE,
)
from auto_patch.layout import BuiltShape, ROLE_APRON, ROLE_BUILDING
from auto_patch.elevation_per_surface.route_profile.anchors import (
    relevel_pads_to_host_pavement,
)

BODY = 100.0                       # host apron solved (body) level
PIT = 96.5                         # DEM-low pad seat (a 3.5 m pit vs the body)


class _FakeLayout:
    def __init__(self, shapes):
        self.shapes = shapes


def _apron_with_lip():
    """An apron whose top edge (y=10) abuts the pad's bottom edge.

    Body vertices sit at ``BODY`` a couple of metres either side of the pad
    corners (so the pad has host BODY within the contact radius), and two
    vertices coincident with the pad corners are contaminated to ``PIT`` (the
    shared lip the old seat dragged down).
    """
    ring = [
        (0.0, 0.0), (40.0, 0.0), (40.0, 10.0),
        (32.0, 10.0),            # body, ~2 m right of the (30,10) pad corner
        (30.0, 10.0),            # shared lip @ pad corner  → PIT
        (28.0, 10.0),            # body, ~2 m left of (30,10)
        (22.0, 10.0),            # body, ~2 m right of (20,10)
        (20.0, 10.0),            # shared lip @ pad corner  → PIT
        (18.0, 10.0),            # body, ~2 m left of (20,10)
        (0.0, 10.0),
    ]
    alt = [BODY, BODY, BODY,
           BODY, PIT, BODY, BODY, PIT, BODY, BODY]
    poly = Polygon(ring)
    return BuiltShape(polygon=poly, role=ROLE_APRON,
                      node_altitudes=alt + [alt[0]])


def _pad(x0, y0, x1, y1, alt):
    return BuiltShape(polygon=Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]),
                      role=ROLE_BUILDING, altitude=alt)


def _pad_level(s):
    if s.altitude is not None:
        return s.altitude
    vals = [v for v in (s.node_altitudes or []) if v is not None]
    return sum(vals) / len(vals) if vals else None


def test_embedded_pit_pad_adopts_host_body(monkeypatch):
    monkeypatch.setenv("O4_PAD_HOST_PAVEMENT_LEVEL", "1")
    apron = _apron_with_lip()
    pad = _pad(20.0, 10.0, 30.0, 18.0, PIT)        # abuts the apron top edge
    layout = _FakeLayout([apron, pad])

    n = relevel_pads_to_host_pavement(layout)
    assert n == 1, "the embedded pit pad must be re-levelled"

    # (1) The pad seats FLAT at the host BODY level.
    assert pad.altitude == pytest.approx(BODY, abs=0.01)

    # (2) The contaminated shared lip is lifted to the body level (no cliff).
    lip_vals = [apron.node_altitudes[4], apron.node_altitudes[7]]
    assert all(abs(v - BODY) < 0.01 for v in lip_vals), (
        f"shared lip not lifted: {lip_vals}")

    # (3) The host BODY is untouched (pad adopts from host, never the reverse).
    body_idx = [0, 1, 2, 3, 5, 6, 8, 9]
    assert all(abs(apron.node_altitudes[i] - BODY) < 0.01 for i in body_idx)

    # (4) The step at the contact is gone — pad and host lip now agree, so the
    #     residual disagreement is within the apron grade cap over the contact.
    step = abs(_pad_level(pad) - max(lip_vals))
    assert step <= APRON_MAX_GRADE * 100.0 * 0.5, (
        f"a step of {step:.2f} m survives at the pad↔host contact")


def test_pad_already_agreeing_is_untouched(monkeypatch):
    monkeypatch.setenv("O4_PAD_HOST_PAVEMENT_LEVEL", "1")
    apron = _apron_with_lip()
    # Seat the pad already at the body level; its lip is not contaminated.
    for i in (4, 7):
        apron.node_altitudes[i] = BODY
    pad = _pad(20.0, 10.0, 30.0, 18.0, BODY)
    layout = _FakeLayout([apron, pad])

    n = relevel_pads_to_host_pavement(layout)
    assert n == 0
    assert pad.altitude == pytest.approx(BODY, abs=0.01)


def test_pad_far_from_pavement_is_untouched(monkeypatch):
    monkeypatch.setenv("O4_PAD_HOST_PAVEMENT_LEVEL", "1")
    apron = _apron_with_lip()
    pad = _pad(500.0, 500.0, 510.0, 510.0, PIT)    # nowhere near the apron
    layout = _FakeLayout([apron, pad])

    n = relevel_pads_to_host_pavement(layout)
    assert n == 0
    assert pad.altitude == pytest.approx(PIT, abs=0.01)


def test_gate_off_is_noop(monkeypatch):
    # The env override died 2026-08-05; ``config.PAD_HOST_PAVEMENT_LEVEL``
    # is the law's own switch and the function reads it at call time.
    import auto_patch.config as _cfg
    monkeypatch.setattr(_cfg, "PAD_HOST_PAVEMENT_LEVEL", False)
    apron = _apron_with_lip()
    pad = _pad(20.0, 10.0, 30.0, 18.0, PIT)
    layout = _FakeLayout([apron, pad])

    n = relevel_pads_to_host_pavement(layout)
    assert n == 0
    assert pad.altitude == pytest.approx(PIT, abs=0.01)
    # lip stays contaminated (byte-identical to the pre-fix behaviour)
    assert apron.node_altitudes[4] == pytest.approx(PIT, abs=0.01)


# ══════════════════════════════════════════════════════════════════════
# R19-1 — A PAD WELDED INTO A COARSE HOST RING FINDS ITS BODY
# ══════════════════════════════════════════════════════════════════════
#
# The class this removes: the host-body probe only ever looked within
# ``PAD_HOST_LEVEL_CONTACT_M`` (2.5 m) of the pad ring.  A pad WELDED INTO
# a coarse host ring has no differing host vertex there at all — every
# host node near it IS a pad node carrying the pad's own value — and the
# host's first body vertex sits one long ring edge away.  HECA
# building114: contacts -771/-772/-773/-774 all at the pad's 88.50, body
# -767 at 85.63 7.84 m off; the pad never re-levelled and the apron's
# 36.6 % edge and 14 building|building 2.87 m rows stood.  53 of HECA's
# 214 pads share the geometry.

WELD_BODY = 85.63                  # the host apron's body level
WELD_PAD = 88.50                   # building114's stranded pad level


def _welded_apron(body_arc_m=7.84, body=WELD_BODY, lip=WELD_PAD):
    """A host apron ring whose vertices at the pad corners ARE the pad's
    (welded lip run), with the first body vertex ``body_arc_m`` further
    along the ring — the building114 geometry."""
    ring = [
        (0.0, 0.0), (60.0, 0.0), (60.0, 10.0),
        (30.0 + body_arc_m, 10.0),   # first body vertex past the run
        (30.0, 10.0),                # welded lip @ pad corner
        (20.0, 10.0),                # welded lip @ pad corner
        (20.0 - body_arc_m, 10.0),   # first body vertex the other way
        (0.0, 10.0),
    ]
    alt = [body, body, body, body, lip, lip, body, body]
    return BuiltShape(polygon=Polygon(ring), role=ROLE_APRON,
                      node_altitudes=alt + [alt[0]])


def test_a_pad_welded_into_a_coarse_host_ring_finds_its_body(monkeypatch):
    monkeypatch.setenv("O4_PAD_HOST_PAVEMENT_LEVEL", "1")
    apron = _welded_apron()
    pad = _pad(20.0, 10.0, 30.0, 18.0, WELD_PAD)
    layout = _FakeLayout([apron, pad])

    assert relevel_pads_to_host_pavement(layout) == 1, (
        "the pad has NO differing host vertex within the contact radius — "
        "the lip-run walk is the only thing that can find its body")
    assert pad.altitude == pytest.approx(WELD_BODY, abs=0.01)
    # The host BODY is untouched (the pad adopts FROM the host).
    assert apron.node_altitudes[3] == pytest.approx(WELD_BODY, abs=0.01)
    assert apron.node_altitudes[6] == pytest.approx(WELD_BODY, abs=0.01)


def test_the_field_sample_has_no_reach(monkeypatch):
    """R19-1 RE-RULED (2026-08-12).  The pad adopts its HOST'S SOLVED
    SURFACE at its own ring — a surface has a value everywhere, so there
    is no radius to satisfy.  This twin used to assert the opposite (a
    bounded ring walk, ``PAD_HOST_BODY_REACH_M``), and the bound is
    exactly what missed HECA building114 twice: its host body sits
    16.59 m out.  Here the body is 30 m out and the pad still finds it.
    """
    monkeypatch.setenv("O4_PAD_HOST_PAVEMENT_LEVEL", "1")
    apron = _welded_apron(body_arc_m=30.0)
    pad = _pad(20.0, 10.0, 30.0, 18.0, WELD_PAD)
    layout = _FakeLayout([apron, pad])

    assert relevel_pads_to_host_pavement(layout) == 1, (
        "a host body 30 m out is still the host's surface at this pad — "
        "the reach cap is retired, not renamed")
    assert pad.altitude == pytest.approx(WELD_BODY, abs=0.01)


def test_a_neighbour_pads_lip_is_never_the_value(monkeypatch):
    """WHY THE REACH COULD BE RETIRED: neighbour-swap is impossible by
    construction.  A neighbouring pad's lip sits NEARER this pad than
    the host's own body does — the geometry that made the vertex-hunting
    mechanisms swap two pads (HECA 140↔141, 146↔151, 210↔211) — and it
    is still never the value read, because the field is ONE host
    polygon's own vertex set with this pad's lips removed by value.

    The family here is {this pad 88.50, the neighbour 120.00, the host's
    own body 85.63}: the host corroborates itself, so the coalition is
    the host's level and the two pads are its outliers.  A mechanism
    that reads "the nearest differing vertex" takes the neighbour's
    120.00 instead."""
    monkeypatch.setenv("O4_PAD_HOST_PAVEMENT_LEVEL", "1")
    NEIGHBOUR = 120.0
    ring = [
        (0.0, -40.0), (60.0, -40.0), (60.0, 10.0),
        (34.0, 10.0),                 # the NEIGHBOUR pad's lip, 4 m off
        (30.0, 10.0), (20.0, 10.0),   # this pad's welded lip run
        (-14.0, 10.0), (-30.0, 10.0),  # the host's OWN body, 34 m off
        (-60.0, 10.0), (-60.0, -40.0),
    ]
    alt = [WELD_BODY, WELD_BODY, WELD_BODY,
           NEIGHBOUR, WELD_PAD, WELD_PAD,
           WELD_BODY, WELD_BODY, WELD_BODY, WELD_BODY]
    apron = BuiltShape(polygon=Polygon(ring), role=ROLE_APRON,
                       node_altitudes=alt + [alt[0]])
    # The neighbour's lip is a WELD: the apron vertex at (34,10) is a
    # vertex of the neighbour pad's own ring, which is what makes it that
    # pad's value rather than the host's surface.
    neighbour = BuiltShape(
        polygon=Polygon([(30.0, 10.0), (34.0, 10.0), (38.0, 10.0),
                         (38.0, 18.0), (30.0, 18.0)]),
        role=ROLE_BUILDING, altitude=NEIGHBOUR)
    pad = _pad(20.0, 10.0, 30.0, 18.0, WELD_PAD)
    layout = _FakeLayout([apron, neighbour, pad])

    relevel_pads_to_host_pavement(layout)
    assert pad.altitude == pytest.approx(WELD_BODY, abs=0.6), (
        f"the pad took {pad.altitude} — the neighbour's lip is nearer "
        f"than the host body, and a vertex hunt would read it")
    assert abs(pad.altitude - NEIGHBOUR) > 5.0


def test_a_lawful_lip_run_on_a_flat_host_moves_nothing(monkeypatch):
    """LIPS STAY LIPS.  A pad welded into a host that agrees with it
    reads AGREEMENT through the walk too — the vertex past the run is
    within the trigger, so there is no body and no re-level."""
    monkeypatch.setenv("O4_PAD_HOST_PAVEMENT_LEVEL", "1")
    apron = _welded_apron(body=WELD_PAD + 0.2, lip=WELD_PAD)
    pad = _pad(20.0, 10.0, 30.0, 18.0, WELD_PAD)
    layout = _FakeLayout([apron, pad])

    assert relevel_pads_to_host_pavement(layout) == 0
    assert pad.altitude == pytest.approx(WELD_PAD, abs=0.01)


# ══════════════════════════════════════════════════════════════════════
# R19-3 — OBJECT PADS RECONCILE WITH THE HOST
# ══════════════════════════════════════════════════════════════════════
#
# An object pad's target is the OBJECT's rendered/draped ground
# (``object_anchor.target_ground_metres``) and NOTHING reconciled it with
# the pavement the solve produced: HECA's object_pad:56 sat at 105.51
# welded to an apron solved to ~93.5, and the apron ring carried its
# 106 m values into the airport's two worst edges (148.4 % over 8.49 m,
# 55.6 % over 22.39 m).  Same machinery, by role, at the pad's own relief
# budget (``DSF_OBJECT_PAD_MAX_RELIEF_M``).

OPAD_HOST = 93.45                  # the apron's solved body level
OPAD_TARGET = 105.51               # object_pad:56's draped target


def _object_pad_group(core_alt, blend_alts, x0=20.0, y0=10.0):
    """A pad REQUEST as the emitter writes it: a flat core plus one blend
    plate ramping out of it (``object_pad:7`` / ``object_pad_blend:7``)."""
    from auto_patch.layout import ROLE_OBJECT_PAD
    core = BuiltShape(
        polygon=Polygon([(x0, y0), (x0 + 8, y0), (x0 + 8, y0 + 8),
                         (x0, y0 + 8)]),
        role=ROLE_OBJECT_PAD, ref="object_pad:7",
        node_altitudes=[core_alt] * 5)
    blend = BuiltShape(
        polygon=Polygon([(x0 - 2, y0 - 2), (x0 + 10, y0 - 2),
                         (x0 + 10, y0 + 10), (x0 - 2, y0 + 10)]),
        role=ROLE_OBJECT_PAD, ref="object_pad_blend:7",
        node_altitudes=list(blend_alts) + [blend_alts[0]])
    return core, blend


def _welded_object_apron(contact_alt, body=OPAD_HOST, body_arc_m=8.49):
    """The apron ring at an object pad's contact: the welded nodes carry
    the PAD's value (the contamination), the body is one long ring edge
    further along."""
    ring = [
        (0.0, -30.0), (60.0, -30.0), (60.0, 8.0),
        (30.0 + body_arc_m, 8.0),
        (30.0, 8.0), (20.0, 8.0),
        (20.0 - body_arc_m, 8.0), (0.0, 8.0),
    ]
    alt = [body, body, body, body, contact_alt, contact_alt, body, body]
    return BuiltShape(polygon=Polygon(ring), role=ROLE_APRON,
                      node_altitudes=alt + [alt[0]])


def test_an_over_budget_object_pad_adopts_the_host_level(monkeypatch):
    from auto_patch.layout import ROLE_OBJECT_PAD
    monkeypatch.setenv("O4_PAD_HOST_PAVEMENT_LEVEL", "1")
    core, blend = _object_pad_group(OPAD_TARGET,
                                    [OPAD_TARGET + 0.5] * 4)
    apron = _welded_object_apron(OPAD_TARGET + 0.55)
    layout = _FakeLayout([apron, core, blend])

    n = relevel_pads_to_host_pavement(layout, pad_role=ROLE_OBJECT_PAD)
    assert n == 1, (
        "a pad 12 m above the pavement it welds to is exactly what "
        "nothing reconciled")
    assert core.node_altitudes[0] == pytest.approx(OPAD_HOST, abs=0.01)
    # PAD + BLEND: the blend moves by the SAME delta, keeping its ramp.
    delta = OPAD_HOST - OPAD_TARGET
    assert blend.node_altitudes[0] == pytest.approx(
        OPAD_TARGET + 0.5 + delta, abs=0.01)
    # The host BODY is untouched.
    assert apron.node_altitudes[3] == pytest.approx(OPAD_HOST, abs=0.01)


def test_an_object_pad_within_its_relief_budget_keeps_its_target(
        monkeypatch):
    """Within the budget the pad keeps its own value — an object seated a
    metre or two above its apron is the relief the pad exists to build."""
    from auto_patch.config import DSF_OBJECT_PAD_MAX_RELIEF_M
    from auto_patch.layout import ROLE_OBJECT_PAD
    monkeypatch.setenv("O4_PAD_HOST_PAVEMENT_LEVEL", "1")
    near = OPAD_HOST + float(DSF_OBJECT_PAD_MAX_RELIEF_M) - 0.5
    core, blend = _object_pad_group(near, [near + 0.2] * 4)
    apron = _welded_object_apron(near + 0.25)
    layout = _FakeLayout([apron, core, blend])

    assert relevel_pads_to_host_pavement(
        layout, pad_role=ROLE_OBJECT_PAD) == 0
    assert core.node_altitudes[0] == pytest.approx(near, abs=0.01)


def test_the_building_pass_never_touches_an_object_pad(monkeypatch):
    """ONE implementation, TWO roles — and each pass moves only its own.
    A building-role pass that swept object pads would re-level them at
    the 0.5 m trigger instead of their 3 m relief budget."""
    from auto_patch.layout import ROLE_OBJECT_PAD
    monkeypatch.setenv("O4_PAD_HOST_PAVEMENT_LEVEL", "1")
    core, blend = _object_pad_group(OPAD_TARGET, [OPAD_TARGET + 0.5] * 4)
    apron = _welded_object_apron(OPAD_TARGET + 0.55)
    layout = _FakeLayout([apron, core, blend])

    assert relevel_pads_to_host_pavement(layout) == 0
    assert core.node_altitudes[0] == pytest.approx(OPAD_TARGET, abs=0.01)
    assert relevel_pads_to_host_pavement(
        layout, pad_role=ROLE_OBJECT_PAD) == 1


def _dense_welded_apron(body=WELD_BODY, lip=WELD_PAD, body_arc_m=7.84):
    """The PRODUCTION geometry: the host ring is denser than the pad's
    contact radius, so the lip run continues past it — vertices still at
    the pad's value that are NOT contacts of the pad."""
    ring = [
        (0.0, 0.0), (60.0, 0.0), (60.0, 10.0),
        (30.0 + body_arc_m, 10.0),   # body
        (33.0, 10.0),                # lip value, OUTSIDE the contact radius
        (30.0, 10.0), (25.0, 10.0), (20.0, 10.0),   # welded lip run
        (17.0, 10.0),                # lip value, outside the radius
        (20.0 - body_arc_m, 10.0),   # body
        (0.0, 10.0),
    ]
    alt = [body, body, body, body, lip, lip, lip, lip, lip, body, body]
    return BuiltShape(polygon=Polygon(ring), role=ROLE_APRON,
                      node_altitudes=alt + [alt[0]])


def test_a_dense_host_ring_still_yields_one_family(monkeypatch):
    """The geometry that defeated the earlier mechanisms, under the
    LEVEL FAMILY law: a host ring denser than
    ``PAD_HOST_LEVEL_CONTACT_M`` carries the pad's value at vertices
    that are not the pad's own contacts.  Membership is structural — the
    lip run and the host body past it are on ONE chain — so the density
    of the ring cannot hide the host's body from the family."""
    monkeypatch.setenv("O4_PAD_HOST_PAVEMENT_LEVEL", "1")
    apron = _dense_welded_apron()
    pad = _pad(20.0, 10.0, 30.0, 18.0, WELD_PAD)
    layout = _FakeLayout([apron, pad])

    assert relevel_pads_to_host_pavement(layout) == 1, (
        "the walk stopped on a lip vertex that merely sat outside the "
        "contact radius — the HECA building114 class")
    assert pad.altitude == pytest.approx(WELD_BODY, abs=0.01)


# The HECA areas the lead ruling names, so the twin and the site are the
# same numbers: building114 = 181.3 m2, building112 = 15,298.4 m2.
SMALL_AREA_PAD_M = 13.5          # ~181 m2 square
BIG_AREA_PAD_M = 123.7           # ~15,298 m2 square


def _square(x0, y0, side, alt):
    return _pad(x0, y0, x0 + side, y0 + side, alt)


def _shared_host(small_alt, big_alt, host_alt):
    """One apron ring with TWO pads welded into it — a small pad and a
    big one — so both are on one chain and one family."""
    ring = [
        (-200.0, -60.0), (200.0, -60.0), (200.0, 0.0),
        (150.0, 0.0),                              # host body
        (20.0 + SMALL_AREA_PAD_M, 0.0), (20.0, 0.0),        # small lips
        (-10.0, 0.0),                                        # host body
        (-10.0 - BIG_AREA_PAD_M, 0.0),                       # big lips
        (-200.0, 0.0),
    ]
    alt = [host_alt, host_alt, host_alt, host_alt,
           small_alt, small_alt, host_alt, big_alt, host_alt]
    apron = BuiltShape(polygon=Polygon(ring), role=ROLE_APRON,
                       node_altitudes=alt + [alt[0]])
    small = _square(20.0, 0.0, SMALL_AREA_PAD_M, small_alt)
    big = _square(-10.0 - BIG_AREA_PAD_M, 0.0, BIG_AREA_PAD_M, big_alt)
    return apron, small, big


def test_a_small_pad_never_drags_a_big_one(monkeypatch):
    """THE SWAP-SAFETY THE RULING RESTS ON, in the ruling's own numbers.
    A 181 m² pad at 88.50 and a 15,298 m² pad at 85.63 are welded into
    one apron ring, so they are ONE level family.  The coalition is
    AREA-weighted: the big pad and the host's own corners carry it, the
    small pad is the outlier and conforms.  The big pad does not move by
    so much as a centimetre."""
    monkeypatch.setenv("O4_PAD_HOST_PAVEMENT_LEVEL", "1")
    apron, small, big = _shared_host(small_alt=WELD_PAD,
                                     big_alt=WELD_BODY,
                                     host_alt=WELD_BODY)
    layout = _FakeLayout([apron, small, big])

    n = relevel_pads_to_host_pavement(layout)
    assert n == 1, "exactly the outlier should have conformed"
    assert small.altitude == pytest.approx(WELD_BODY, abs=0.01), (
        "the 181 m2 outlier did not adopt its family's level")
    assert big.altitude == pytest.approx(WELD_BODY, abs=0.001), (
        "the 15,298 m2 pad MOVED — a small neighbour dragged it, which "
        "is the class the area weighting exists to make impossible")


def test_the_big_pad_wins_even_when_outnumbered(monkeypatch):
    """AREA, NOT HEADCOUNT — the one difference between this law and
    R12's own coalition.  EIGHT small pads (181 m² each, 1,450 m² all
    told) share one apron edge with a 15,298 m² pad, so all nine are ONE
    family (each pad's corner is its neighbour's corner).  A coalition
    that COUNTS members seats the eight and drags the big pad; one that
    weighs them by the ground they own seats the big pad and the eight
    conform."""
    monkeypatch.setenv("O4_PAD_HOST_PAVEMENT_LEVEL", "1")
    # A CONTIGUOUS run: pad k's right corner IS pad k+1's left corner,
    # which is the shared host-ring vertex that chains them.
    S = SMALL_AREA_PAD_M
    xs = [20.0 + S * k for k in range(8)]
    edge = [20.0 - BIG_AREA_PAD_M, 20.0] + [x + S for x in xs]
    ring = [(-400.0, -80.0), (400.0, -80.0), (400.0, 0.0)]
    alt = [WELD_BODY, WELD_BODY, WELD_BODY]
    for x in reversed(edge):
        ring.append((x, 0.0))
        alt.append(WELD_PAD if x > 20.0 - 0.001 else WELD_BODY)
    ring.append((-400.0, 0.0))
    alt.append(WELD_BODY)
    alt[3 + 0] = WELD_PAD          # the run's own corners carry the pads
    apron = BuiltShape(polygon=Polygon(ring), role=ROLE_APRON,
                       node_altitudes=alt + [alt[0]])
    smalls = [_square(x, 0.0, S, WELD_PAD) for x in xs]
    big = _square(20.0 - BIG_AREA_PAD_M, 0.0, BIG_AREA_PAD_M, WELD_BODY)
    layout = _FakeLayout([apron, big] + smalls)

    # Premises, so the twin cannot go vacuous.
    assert len(smalls) > 3
    assert sum(p.polygon.area for p in smalls) < big.polygon.area / 5.0

    relevel_pads_to_host_pavement(layout)
    assert big.altitude == pytest.approx(WELD_BODY, abs=0.001), (
        "the big pad moved — eight small neighbours out-VOTED 15,298 m², "
        "which is a headcount coalition, not an area-weighted one")
    for small in smalls:
        assert small.altitude == pytest.approx(WELD_BODY, abs=0.01), (
            "a small outlier did not conform to its family")


def test_two_families_on_separate_chains_never_merge(monkeypatch):
    """Membership is STRUCTURAL: a pad joins through host-ring vertices
    its own contact radius touches.  Two pads welded into DIFFERENT host
    shapes are two families however close they sit — the geometry that
    let every distance-based mechanism read a stranger's level."""
    monkeypatch.setenv("O4_PAD_HOST_PAVEMENT_LEVEL", "1")
    apron_a = BuiltShape(
        polygon=Polygon([(0.0, -40.0), (60.0, -40.0), (60.0, 0.0),
                         (30.0, 0.0), (20.0, 0.0), (0.0, 0.0)]),
        role=ROLE_APRON,
        node_altitudes=[WELD_BODY, WELD_BODY, WELD_BODY,
                        WELD_PAD, WELD_PAD, WELD_BODY, WELD_BODY])
    # A SECOND host, 3 m away — beyond the contact radius, so nothing of
    # family A touches it.
    # A SECOND host 3 m away, deliberately made the DOMINANT ground
    # nearby (10x the area of apron A): any membership rule that reaches
    # by DISTANCE rather than through this pad's own chain seats its
    # 120.00 over apron A's 85.63.
    apron_b = BuiltShape(
        # Its ring carries a VERTEX 3 m from the pad, so a rule that
        # reaches by distance has something to grab; the chain rule has
        # not, because nothing of this pad touches apron B.
        polygon=Polygon([(-200.0, 3.0), (25.0, 3.0), (200.0, 3.0),
                         (200.0, 203.0), (-200.0, 203.0)]),
        role=ROLE_APRON,
        node_altitudes=[120.0] * 6)
    pad = _pad(20.0, 0.0, 30.0, -8.0, WELD_PAD)
    layout = _FakeLayout([apron_a, apron_b, pad])

    relevel_pads_to_host_pavement(layout)
    assert pad.altitude == pytest.approx(WELD_BODY, abs=0.01), (
        f"the pad took {pad.altitude} — apron B is 3 m away and in no "
        f"chain of this pad's, so its 120.00 must be unreachable")


def test_the_family_itself_never_contains_a_stranger_host(monkeypatch):
    """The membership rule, asserted directly on the family builder — the
    end-to-end twin above can be satisfied by a coalition that merely
    out-weighs the stranger, and the LAW is that the stranger is not in
    the family at all.

    Apron B is 3 m away and ten times apron A's area; the pad is welded
    only into A.  A membership rule that reaches by DISTANCE puts B's
    120.00 in this list."""
    from auto_patch.elevation_per_surface.route_profile import (
        anchors as _A)
    monkeypatch.setenv("O4_PAD_HOST_PAVEMENT_LEVEL", "1")
    apron_a = BuiltShape(
        polygon=Polygon([(0.0, -40.0), (60.0, -40.0), (60.0, 0.0),
                         (30.0, 0.0), (20.0, 0.0), (0.0, 0.0)]),
        role=ROLE_APRON,
        node_altitudes=[WELD_BODY, WELD_BODY, WELD_BODY,
                        WELD_PAD, WELD_PAD, WELD_BODY, WELD_BODY])
    apron_b = BuiltShape(
        polygon=Polygon([(-200.0, 3.0), (25.0, 3.0), (200.0, 3.0),
                         (200.0, 203.0), (-200.0, 203.0)]),
        role=ROLE_APRON, node_altitudes=[120.0] * 6)
    pad = _pad(20.0, 0.0, 30.0, -8.0, WELD_PAD)
    layout = _FakeLayout([apron_a, apron_b, pad])

    host_rings = []
    areas = []
    for sh in (apron_a, apron_b):
        ring = _A._open_ring(list(sh.polygon.exterior.coords))
        n = len(ring)
        host_rings.append(
            ([(float(x), float(y)) for (x, y) in ring],
             [_A._shape_vertex_alt(sh, i, n) for i in range(n)]))
        areas.append(sh.polygon.area)
    lips = _A._pad_lip_index(layout, host_rings, 2.5, 6.25)
    host_lip = [[bool(lips.get(r, {}).get(i)) for i in range(len(pts))]
                for r, (pts, _a) in enumerate(host_rings)]
    members = _A._level_family_members(
        [pad], {id(pad): pad}, host_rings, areas, host_lip, lips,
        0.5, 36.0)

    assert members, "the pad is welded into apron A — it has a family"
    levels = sorted({round(e["delta_m"], 2) for e in members})
    assert 120.0 not in levels, (
        f"apron B's level is in the family ({levels}) — membership "
        f"reached by DISTANCE instead of through the pad's own chain")
    assert WELD_BODY in levels, "apron A's own body is missing"
