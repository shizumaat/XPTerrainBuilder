# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_submodules

# ---------------------------------------------------------------------------
# PROJ data: each bundled libproj gets the proj.db it shipped with
# (docs/specs/proj-runtime-robustness-spec.md).  pyproj's own wheel data is
# collected by PyInstaller's pyproj hook into pyproj/proj_dir/share/proj; the
# freeze machine's system proj.db is NEVER overlaid on it (a third, unrelated
# version).  GDAL's libproj is a SECOND runtime with its own database, so its
# data directory is resolved here, from the freeze venv, and bundled beside it.
# ---------------------------------------------------------------------------
def get_gdal_proj_dir():
    """Return GDAL's own PROJ data directory in the freeze venv, or None."""
    try:
        import osgeo
        import osgeo.osr
    except ImportError:
        return None
    wheel_dir = os.path.join(os.path.dirname(osgeo.__file__), "data", "proj")
    if os.path.isfile(os.path.join(wheel_dir, "proj.db")):
        return wheel_dir
    for path in osgeo.osr.GetPROJSearchPaths() or []:
        if path and os.path.isfile(os.path.join(path, "proj.db")):
            return path
    raise SystemExit(
        "ERROR: osgeo is installed in the freeze environment but no proj.db "
        "was found in osgeo/data/proj or osr.GetPROJSearchPaths() — refusing "
        "to ship a guessed PROJ database."
    )

gdal_proj_dir = get_gdal_proj_dir()
if gdal_proj_dir is None:
    print("NOTICE: no osgeo in the freeze environment — bundling no GDAL PROJ data.")
else:
    print(f"Bundling GDAL proj data from: {gdal_proj_dir}")

# Destination inside the bundle mirrors the path O4_Proj_Runtime expects:
#   sys._MEIPASS / osgeo / data / proj
gdal_proj_datas = (
    [(gdal_proj_dir, os.path.join("osgeo", "data", "proj"))]
    if gdal_proj_dir else []
)

a = Analysis(
    ['Ortho4XP.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('./Utils',               './Ortho4XP_Data/Utils'),
        ('./Extents',             './Ortho4XP_Data/Extents'),
        ('./Filters',             './Ortho4XP_Data/Filters'),
        ('./Licence',             './Ortho4XP_Data/Licence'),
        ('./Patches',             './Ortho4XP_Data/Patches'),
        ('./Previews',            './Ortho4XP_Data/Previews'),
        ('./Providers',           './Ortho4XP_Data/Providers'),
        ('community_server.txt',  './Ortho4XP_Data/'),
        ('overpass_servers.txt',  './Ortho4XP_Data/'),
    ] + gdal_proj_datas,
    hiddenimports=collect_submodules('PIL'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Ortho4XP',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Ortho4XP',
)
