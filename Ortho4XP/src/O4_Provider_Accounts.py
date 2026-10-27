"""Every provider definition that declares an account (#1339): the one
enumeration the engine's ``auth_providers`` and the Qt Provider accounts
section read.  Its own module, not ``O4_Authenticated_Sessions``: the
tile steps import the sessions module (elevation downloads), and this
enumeration reads the imagery registry, which the vector and mesh step
code keys leave out (``O4_Step_Code``).
"""
from __future__ import annotations

__all__ = ["account_definitions"]


def account_definitions():
    """Every enabled provider definition that declares an account
    session, sorted by code: the elevation providers' parsed ``.elv``
    definitions and the imagery providers' ``.lay`` ones (#1339) — the
    one enumeration the engine's ``auth_providers`` and the Qt settings
    section both read, never a private re-parse."""
    import O4_Airport_Elevation_Insets as ELEVATION_PROVIDERS
    import O4_Imagery_Utils as IMG

    if not ELEVATION_PROVIDERS.elevation_providers_dict:
        ELEVATION_PROVIDERS.initialize_elevation_providers_dict()
    definitions = list(ELEVATION_PROVIDERS.elevation_providers_dict.values())
    definitions += list(IMG.providers_dict.values())
    return [
        definition
        for definition in sorted(definitions, key=lambda d: str(d.get("code")))
        if definition.get("session_name") and definition.get("enabled", True)
    ]
