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
