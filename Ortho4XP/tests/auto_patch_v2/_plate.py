"""The PLATE-ONLY law for twins whose subject is the pad plate itself
(23a / 28b / 14ay / §30 (4)): ``[building_pad] frontage_hold`` off, so a
fixture pad is the plain §20 plate — no held block, no datum column (the
flat-pad hold's own twins are ``test_pad_blocks.py`` and
``test_unitplatform_platform.py``).  A unit pad is ONE face under every
law (spec §56 (3): the collar and its ``platform_collar`` knob are
deleted)."""
from __future__ import annotations

import dataclasses as _dc


def plate_law(law):
    """``law`` with the flat-pad hold off (:func:`contact_led_law` — the
    name the plate twins have always called it by)."""
    return contact_led_law(law)


def contact_led_law(law):
    """``law`` with ``[building_pad] frontage_hold = false`` — the plain
    plate (and, for a landing-shaped bank pair or a draped facade's plate,
    the 29s contact-led plane) for twins whose subject is THAT path; the
    hold's own twins are ``test_pad_blocks.py`` (flat-pad spec, RULINGS
    2026-09-30f/r)."""
    bp = _dc.replace(law.tables.structures.building_pad, frontage_hold=False)
    st = _dc.replace(law.tables.structures, building_pad=bp)
    return _dc.replace(law, tables=_dc.replace(law.tables, structures=st))
