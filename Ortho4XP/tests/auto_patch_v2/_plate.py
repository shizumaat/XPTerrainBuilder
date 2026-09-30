"""The PLATE-ONLY law for twins whose subject is the pad plate itself
(23a / 28b / 14ay / §30 (4)): ``[building_pad] platform_collar`` off, so a
fixture pad stays ONE face (unit-platform spec §1 mints a platform + collar
inside every airside-fronting unit pad; its own twins are
``test_unitplatform_connector.py``)."""
from __future__ import annotations

import dataclasses as _dc


def plate_law(law):
    """``law`` with ``[building_pad] platform_collar = false``."""
    bp = _dc.replace(law.tables.structures.building_pad, platform_collar=False)
    st = _dc.replace(law.tables.structures, building_pad=bp)
    return _dc.replace(law, tables=_dc.replace(law.tables, structures=st))


def contact_led_law(law):
    """``law`` with ``[building_pad] frontage_hold = false`` — the 29s
    contact-led platform (the fallback every pad the flat-pad hold does not
    reach still takes) for twins whose subject is THAT path; the hold's own
    twins are ``test_pad_blocks.py`` (flat-pad spec, RULINGS 2026-09-30f/r)."""
    bp = _dc.replace(law.tables.structures.building_pad, frontage_hold=False)
    st = _dc.replace(law.tables.structures, building_pad=bp)
    return _dc.replace(law, tables=_dc.replace(law.tables, structures=st))
