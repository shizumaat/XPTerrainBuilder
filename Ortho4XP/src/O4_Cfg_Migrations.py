"""The global config's one-time migrations, run in one place.

Every one-time hand-over of the global ``XPTerrainBuilder.cfg`` runs
through :func:`migrate_global`, each recorded in the file's
``<cfg>.defaults`` register so it runs once and a value the user sets by
hand afterwards is never touched:

1. the airport Detail hand-over (#1985, ``O4_Airport_Detail.migrate_cfg``);
2. the preset imagery reach (:func:`_migrate_preset_extent`, below);
3. raised registry defaults (``O4_Cfg_Vars.migrate_changed_defaults``).

The app-facing readers call :func:`migrate_global` BEFORE they read: the
JSONL engine before its hello (the Mac app re-reads the global cfg on
that hello) and the Qt Settings window.  ``O4_Config_Utils`` keeps its own
two import-time migrations (Detail, raised defaults) and does NOT import
this module, so the build steps' code keys (``O4_Step_Code``,
``provenance_code``) do not grow: a preset's reach is a Settings matter.  Before 2026-11-10 the JSONL engine migrated lazily, at
the first command that imported ``O4_Config_Utils`` — after the Mac app
had read the file once and for good — so the app showed the
pre-migration values (Detail "Custom") for the whole session.
"""

from __future__ import annotations

import os

__all__ = ["PRESET_EXTENT_ENTRY", "OLD_PRESET_EXTENT",
           "migrate_global"]

#: The register entry of :func:`_migrate_preset_extent`.
PRESET_EXTENT_ENTRY = "preset_cover_extent"

#: Every preset wrote ``cover_extent=1.0`` until 2026-11-09; since then
#: every preset writes 0.0 (owner 2026-11-09T17:05Z, the approach
#: corridors add the reach).  The app keeps no record of which preset a
#: user picked, so the old value moves only when every OTHER preset key
#: in the file equals one preset's value: the config is a preset's, the
#: 1.0 is that preset's old reach, not the user's choice.
OLD_PRESET_EXTENT = "1.0"


def _preset_extent_change(raw):
    """``{"cover_extent": new}`` when ``raw`` (name -> literal, the global
    cfg) holds the old preset reach and every other preset cfg key
    matches one preset, else ``{}``."""
    import O4_Settings_Model as SM
    import O4_Settings_Presets as PRESETS

    def value(name):
        return str(raw[name]) if name in raw else \
            SM.global_effective_value(name, {})

    if not SM.values_equivalent("cover_extent", value("cover_extent"),
                                OLD_PRESET_EXTENT):
        return {}
    for entry in PRESETS.PRESETS:
        wanted = PRESETS.cfg_values(entry)
        if all(SM.values_equivalent(name, value(name), literal)
               for name, literal in wanted.items() if name != "cover_extent"):
            return {"cover_extent": wanted["cover_extent"]}
    return {}


def _migrate_preset_extent(cfg_path):
    """Apply :func:`_preset_extent_change` to the global cfg at
    ``cfg_path`` ONCE (register entry :data:`PRESET_EXTENT_ENTRY`).

    :returns: INFO lines for the caller to print.  Never raises.
    """
    try:
        if not cfg_path or not os.path.isfile(cfg_path):
            return []
        import O4_Cfg_Vars as CV
        import O4_Settings_Model as SM

        if PRESET_EXTENT_ENTRY in CV._read_register(cfg_path):
            return []
        data = SM._parse_cfg(cfg_path, strip_quotes=False)
        changes = _preset_extent_change(data)
        if changes:
            data.update(changes)
            SM._write_atomic_with_backup(cfg_path, data)
        with open(CV._register_path(cfg_path), "a", encoding="utf-8",
                  newline="\n") as f:
            f.write(PRESET_EXTENT_ENTRY + "\n")
        return ["set %s=%s (the presets' new airport imagery reach) in %s"
                % (name, value, cfg_path) for name, value in changes.items()]
    except Exception:
        return []


def migrate_global(cfg_path=None):
    """Run every one-time migration of the global cfg at ``cfg_path``
    (default: this data root's ``XPTerrainBuilder.cfg``), in order.

    :returns: INFO lines for the caller to print.  Never raises.
    """
    try:
        import O4_Airport_Detail as AIRPORT_DETAIL
        import O4_Cfg_Vars as CV

        if cfg_path is None:
            import O4_Config_Names as CN
            cfg_path = CN.global_cfg_path()
        return (AIRPORT_DETAIL.migrate_cfg(cfg_path)
                + _migrate_preset_extent(cfg_path)
                + CV.migrate_changed_defaults(cfg_path))
    except Exception:
        return []
