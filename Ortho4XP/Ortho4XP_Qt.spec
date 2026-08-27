# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the Qt (map-first) UI.
# On macOS this produces a double-clickable dist/Ortho4XP.app with a real
# application menu bar (no more "Python"). Build with:
#     ./build_mac_app.sh          (or: pyinstaller Ortho4XP_Qt.spec)
import os
import sys

from PyInstaller.utils.hooks import collect_submodules


# PROJ data: each bundled libproj gets the proj.db it shipped with
# (docs/specs/proj-runtime-robustness-spec.md).  pyproj's own wheel data is
# collected by PyInstaller's pyproj hook into pyproj/proj_dir/share/proj; the
# freeze machine's system proj.db is NEVER overlaid on it (a third, unrelated
# version).  GDAL's libproj is a SECOND runtime with its own database, so its
# data directory is resolved here, from the freeze venv, and bundled beside it.
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

# Single source of truth for the app version: src/O4_Version.py
# (parsed textually — spec files should not import project modules).
with open(os.path.join("src", "O4_Version.py"), encoding="utf-8") as f:
    o4_version = f.read().split("=", 1)[1].strip().strip("'\"")

a = Analysis(
    ['Ortho4XP_Qt.py'],
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
    hiddenimports=collect_submodules('PIL') + [
        # keyring picks its backend through entry points, which PyInstaller
        # does not follow — name every platform backend explicitly so the
        # frozen app can reach the secret store (O4_Authenticated_Sessions).
        'keyring.backends.macOS',
        'keyring.backends.Windows',
        'keyring.backends.SecretService',
        'keyring.backends.kwallet',
        'keyring.backends.chainer',
        'keyring.backends.fail',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Qt modules the app does not use — keeps the bundle smaller.
        'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
        'PySide6.Qt3DCore', 'PySide6.Qt3DRender', 'PySide6.QtCharts',
        'PySide6.QtMultimedia', 'PySide6.QtQuick', 'PySide6.QtQml',
        'PySide6.QtPdf', 'PySide6.QtDesigner', 'PySide6.QtTest',
        'tkinter',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    # hash_seed=0: the bootloader starts the embedded interpreter with a
    # pinned string-hash seed (same effect as PYTHONHASHSEED=0, which the
    # Finder-launched .app never receives from a shell).  Deterministic
    # builds are primarily guaranteed by source-level ordering pins in
    # auto_patch; this is defense in depth for the packaged application.
    [('hash_seed=0', None, 'OPTION')],
    exclude_binaries=True,
    name='Ortho4XP_Qt',
    icon=os.path.join('Utils', 'icons', 'Ortho4XP.ico')
    if os.name == 'nt' else None,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # windowed app: proper menu bar, no terminal
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
    name='Ortho4XP_Qt',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='Ortho4XP.app',
        icon=os.path.join('Utils', 'icons', 'Ortho4XP.icns'),
        bundle_identifier='org.ortho4xp.qt',
        info_plist={
            'CFBundleName': 'Ortho4XP',
            'CFBundleDisplayName': 'Ortho4XP',
            'CFBundleShortVersionString': o4_version,
            'CFBundleVersion': o4_version,
            'NSHighResolutionCapable': True,
            'NSRequiresAquaSystemAppearance': False,  # follow dark mode
        },
    )
