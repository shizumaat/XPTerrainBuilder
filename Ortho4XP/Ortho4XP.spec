# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_submodules, collect_all

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

# ---------------------------------------------------------------------------
# auto_patch_v2 LAW TABLES (RULINGS 2026-09-03e): the law is DATA — TOML
# files beside the package, read through ``Path(__file__).parent``.  PyInstaller
# collects only Python modules into the PYZ, so the tables are bundled as
# datas at the SAME relative path (``_internal/auto_patch_v2/law/*.toml``,
# ``.../classify/rules.toml``); a bundle without them fails LOUDLY at first
# use (``law_tables_digest()['sha256'] is None`` → the v2 worker refuses,
# ``LawError("law table missing")`` in the loader) — v2 never falls back
# to v1.  ``collect_submodules`` pins every v2 module into the PYZ: the
# tile driver imports the package lazily, per engine selection.
# ---------------------------------------------------------------------------
import glob as _glob
v2_law_datas = (
    [(f, os.path.join("auto_patch_v2", "law"))
     for f in sorted(_glob.glob(os.path.join("src", "auto_patch_v2", "law", "*.toml")))]
    + [(f, os.path.join("auto_patch_v2", "classify"))
       for f in sorted(_glob.glob(os.path.join("src", "auto_patch_v2", "classify", "*.toml")))]
)
if len(v2_law_datas) < 9:
    raise SystemExit(
        f"ERROR: expected the eight auto_patch_v2 law tables (incl. airports.toml, "
        f"RULINGS 2026-09-10ap) + classify/rules.toml under src/auto_patch_v2, "
        f"found {len(v2_law_datas)} — refusing to freeze "
        f"an engine whose v2 cannot load its law.")

# highspy (the HiGHS QP behind the runway family's final projection,
# ``auto_patch_v2/solve/project.py``, RULINGS 2026-09-09ae) is imported
# lazily inside the solve, so the static import scan never sees it: the
# 1.0.298 engine froze without it and every v2 airport failed at
# "No module named 'highspy'" (HECA, LERM; owner 2026-09-10).  collect_all
# pins the package, its compiled core and libhighs.
highspy_datas, highspy_binaries, highspy_hidden = collect_all('highspy')

# THE LERC CODECS (owner RULINGS 2026-09-12as (3)).  ``src/O4_LERC_Decode.py``
# is reached only through the ``--lerc-decode`` argv branch, and tifffile
# delegates the LERC decode to imagecodecs' compiled ``_lerc`` extension —
# a codec the static scan cannot infer from ``tifffile`` alone (the highspy
# precedent: a package PyInstaller never sees is a package the engine ships
# without, and the failure shows up as silently degraded terrain, not a
# traceback).  collect_all pins each package, its data and its extensions.
tifffile_datas, tifffile_binaries, tifffile_hidden = collect_all('tifffile')
imagecodecs_datas, imagecodecs_binaries, imagecodecs_hidden = collect_all('imagecodecs')
for _codec in ('imagecodecs._lerc', 'imagecodecs._shared'):
    if _codec not in imagecodecs_hidden:
        imagecodecs_hidden.append(_codec)

a = Analysis(
    ['Ortho4XP.py'],
    pathex=['src'],
    binaries=highspy_binaries + tifffile_binaries + imagecodecs_binaries,
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
    ] + gdal_proj_datas + v2_law_datas + highspy_datas + tifffile_datas
      + imagecodecs_datas,
    hiddenimports=(collect_submodules('PIL') + collect_submodules('auto_patch_v2')
                   + highspy_hidden + tifffile_hidden + imagecodecs_hidden
                   + ['O4_LERC_Decode']),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
# Vendored *.whl files under Utils/ are INSTALL-TIME artifacts (they build the
# venv this freeze runs in); nothing at runtime opens one (grep 2026-09-17:
# zero references in src/).  Shipped inside a signed mac app they fail
# notarization: Apple's notary unpacks archives and found 23 unsigned Mach-Os
# inside Utils/mac/numpy-*.whl (submission 0e71fbdf, status Invalid), which no
# codesign pass can reach.  Dropped at the derivation site.
a.datas = [d for d in a.datas if not d[0].lower().endswith('.whl')]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    # hash_seed=0: the bootloader starts the embedded interpreter with a
    # pinned string-hash seed (same effect as PYTHONHASHSEED=0, which an
    # engine spawned by the app never receives from a shell).  BOTH frozen
    # engines carry the same belt — Ortho4XP_Qt.spec has had it since the
    # Qt bundle was first frozen, and this is the engine the mac app runs.
    # Deterministic builds are primarily guaranteed by source-level
    # ordering pins in auto_patch; this is defense in depth.
    [('hash_seed=0', None, 'OPTION')],
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
