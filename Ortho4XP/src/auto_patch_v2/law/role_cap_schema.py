"""THE TIERED ROLE CAP's table form (owner RULINGS 2026-09-06w; the
``model.py`` 1,000-line law keeps it a sibling, like ``terrace_schema``).

A ``common.roles.<role>`` entry is either ONE tier, ``{ longitudinal,
transverse }``, or TWO, ``{ preferred = {…}, max = {…} }`` — the apron
and the pad: ``max`` is the HARD cap every row holds, ``preferred`` the
tier the solver charges as a preference (``constraints/apron.py``).  No
numeric value lives here; ``preferred`` may never exceed ``max``.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

__all__ = ["role_cap_from_table"]


def role_cap_from_table(path: str, name: str, raw: object, build: _t.Callable,
                        role_cap_cls: type, error: type) -> object:
    """Build a ``RoleCap`` from its TOML table (module docstring)."""
    if not isinstance(raw, dict):
        raise error(f"{path}.{name}: expected a table for RoleCap")
    if "preferred" not in raw and "max" not in raw:
        return build(role_cap_cls, raw, f"{path}.{name}")
    if set(raw) != {"preferred", "max"}:
        raise error(f"{path}.{name}: a tiered cap is exactly {{preferred, max}}")
    pref = build(role_cap_cls, raw["preferred"], f"{path}.{name}.preferred")
    hard = build(role_cap_cls, raw["max"], f"{path}.{name}.max")
    if pref.longitudinal > hard.longitudinal or pref.transverse > hard.transverse:
        raise error(f"{path}.{name}: preferred exceeds max")
    return _dc.replace(hard, preferred=pref)
