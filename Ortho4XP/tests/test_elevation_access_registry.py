"""The elevation access strategies all exist, and exist in the frozen app.

A strategy registers itself when its module is imported, and the frozen
engine carries only modules reached by a STATIC import.  A strategy file
nobody imports is a provider silently lost (the issue #344 class): the
``.elv`` definition still parses, the registry lookup returns ``None``,
and the airport is cut from the base tier with one WARNING line.

``EXPECTED_KEYS`` is the registry as it stood at main ``01662c75``, the
commit before the strategies left ``O4_Airport_Elevation_Insets.py`` for
one module each.  Every key is a string in ``Providers/Elevation/*.elv``
files, so none may be renamed or dropped.
"""

import ast
import glob
import inspect
import json
import os
import subprocess
import sys

ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ENGINE_DIR, "src")
PACKAGE_DIR = os.path.join(SRC, "elevation_access")
STRATEGY_DIR = os.path.join(PACKAGE_DIR, "strategies")
PIPELINE = os.path.join(SRC, "O4_Airport_Elevation_Insets.py")

#: registry key -> class name, recorded at main 01662c75 BEFORE the move.
EXPECTED_KEYS = {
    "aoi_zip_download": "AoiZipDownloadStrategy",
    "arcgis_export_image": "ArcgisExportImageStrategy",
    "arcgis_feature_tiles": "ArcgisFeatureTileStrategy",
    "arcgis_lerc_tiles": "ArcgisLercTileStrategy",
    "authenticated_token_search": "AuthenticatedTokenSearchStrategy",
    "coordinate_named_url_list": "CoordinateNamedUrlListStrategy",
    "coral_atlas_library": "CoralAtlasLibraryStrategy",
    "cwcb_lidar_api": "CwcbLidarApiStrategy",
    "degree_named_cog": "DegreeNamedCogStrategy",
    "direct_cog": "DirectCogStrategy",
    "geojson_tile_index": "GeojsonTileIndexStrategy",
    "hgt_archive_drop": "HgtArchiveDropStrategy",
    "las_tile_index": "LasTileIndexStrategy",
    "manual_download": "ManualDownloadStrategy",
    "os_grid_bucket": "OsGridBucketStrategy",
    "stac": "StacCloudOptimizedGeoTiffStrategy",
    "static_stac": "StaticStacCatalogStrategy",
    "tile_grid_http": "TileGridHttpStrategy",
    "tnm_cog": "TnmCloudOptimizedGeoTiffStrategy",
    "usgs_seamless": "UsgsSeamlessStrategy",
    "viewfinder_zip": "ViewfinderZipStrategy",
    "wcs": "WcsStrategy",
    "wcs_kvp": "WcsKvpStrategy",
    "wfs_tile_index": "WfsTileIndexStrategy",
    "xyz_archive_drop": "XyzArchiveDropStrategy",
    "xyz_text_tiles": "XyzTextTileStrategy",
}

#: The keys whose strategy supplies whole base tiles (``ensure_tile``).
BASE_TILE_KEYS = {"hgt_archive_drop", "manual_download", "usgs_seamless",
                  "viewfinder_zip"}

#: Signatures that differ from the protocol.  Reported, not papered over:
#: ``ArcgisFeatureTileStrategy.discover`` takes an extra ``resolve`` flag
#: its own ``fetch`` passes; the pipeline never does.
SIGNATURE_EXCEPTIONS = {
    ("arcgis_feature_tiles", "discover"):
        ["self", "definition", "bounding_box_wgs84", "resolve"],
}

#: A strategy module importing another strategy module (the package
#: docstring names these three; a fourth is a design question).
CROSS_STRATEGY_IMPORTS = {
    ("authenticated_token_search", "stac"),
    ("las_tile_index", "cwcb_lidar_api"),
    ("os_grid_bucket", "geojson_tile_index"),
}


def _strategy_module_names() -> list:
    return sorted(
        os.path.splitext(os.path.basename(path))[0]
        for path in glob.glob(os.path.join(STRATEGY_DIR, "*.py"))
        if os.path.basename(path) != "__init__.py")


def _parse(path: str) -> ast.Module:
    with open(path, encoding="utf-8") as handle:
        return ast.parse(handle.read())


def _registry_in_a_fresh_process(statement: str) -> dict:
    """``{key: [class name, module]}`` after running ``statement`` in a new
    interpreter -- no test has registered a dummy strategy there."""
    code = (
        "import json, sys\n"
        "sys.path.insert(0, %r)\n"
        "sys.path.insert(0, %r)\n"
        "%s\n"
        "from elevation_access.registry import ACCESS_STRATEGIES\n"
        "print(json.dumps({key: [cls.__name__, cls.__module__] "
        "for (key, cls) in ACCESS_STRATEGIES.items()}))\n"
    ) % (ENGINE_DIR, SRC, statement)
    completed = subprocess.run([sys.executable, "-c", code],
                               capture_output=True, text=True, timeout=300)
    assert completed.returncode == 0, completed.stderr[-2000:]
    return json.loads(completed.stdout.strip().splitlines()[-1])


def test_importing_the_package_alone_registers_every_key():
    registered = _registry_in_a_fresh_process("import elevation_access")
    assert {key: value[0] for (key, value) in registered.items()} \
        == EXPECTED_KEYS


def test_importing_the_pipeline_registers_the_same_keys():
    """The engine never imports the package by itself; it imports the
    pipeline.  Same keys, same classes."""
    registered = _registry_in_a_fresh_process(
        "import O4_Airport_Elevation_Insets")
    assert {key: value[0] for (key, value) in registered.items()} \
        == EXPECTED_KEYS


def test_each_strategy_lives_in_the_module_named_for_its_key():
    registered = _registry_in_a_fresh_process("import elevation_access")
    assert {key: value[1] for (key, value) in registered.items()} == {
        key: "elevation_access.strategies." + key for key in EXPECTED_KEYS}
    assert _strategy_module_names() == sorted(EXPECTED_KEYS)


def test_every_strategy_module_is_imported_statically_from_one_place():
    """THE FREEZER LINE: ``strategies/__init__.py`` names every strategy
    file in a plain ``from ... import`` statement."""
    tree = _parse(os.path.join(STRATEGY_DIR, "__init__.py"))
    imported = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) \
                and node.module == "elevation_access.strategies":
            imported |= {alias.name for alias in node.names}
    assert sorted(imported) == _strategy_module_names()


def test_the_static_chain_reaches_the_strategies_from_the_pipeline():
    """pipeline -> ``import elevation_access`` -> ``strategies``, each a
    module-level import statement the freezer's scan follows."""
    pipeline_imports = {
        alias.name for node in _parse(PIPELINE).body
        if isinstance(node, ast.Import) for alias in node.names}
    assert "elevation_access" in pipeline_imports
    package_imports = {
        (node.module, alias.name)
        for node in _parse(os.path.join(PACKAGE_DIR, "__init__.py")).body
        if isinstance(node, ast.ImportFrom) for alias in node.names}
    assert ("elevation_access", "strategies") in package_imports


def test_both_freezer_specs_name_the_package_modules():
    for spec in ("Ortho4XP.spec", "Ortho4XP_Qt.spec"):
        with open(os.path.join(ENGINE_DIR, spec), encoding="utf-8") as handle:
            text = handle.read()
        assert "+ elevation_access_hidden" in text, spec


def test_every_strategy_satisfies_exactly_one_interface():
    import elevation_access
    from elevation_access.base import (
        BaseTileAccessStrategy,
        InsetAccessStrategy,
    )

    for key in EXPECTED_KEYS:
        strategy = elevation_access.ACCESS_STRATEGIES[key]()
        is_base = isinstance(strategy, BaseTileAccessStrategy)
        is_inset = isinstance(strategy, InsetAccessStrategy)
        assert is_base == (key in BASE_TILE_KEYS), key
        assert is_inset == (key not in BASE_TILE_KEYS), key
        protocol = BaseTileAccessStrategy if is_base else InsetAccessStrategy
        for method in ("covers", "ensure_tile") if is_base \
                else ("discover", "fetch"):
            wanted = list(inspect.signature(
                getattr(protocol, method)).parameters)
            found = list(inspect.signature(
                getattr(type(strategy), method)).parameters)
            assert found == SIGNATURE_EXCEPTIONS.get((key, method), wanted), \
                (key, method, found)


def test_the_package_never_imports_the_pipeline_and_strategies_stay_apart():
    cross = set()
    for path in glob.glob(os.path.join(PACKAGE_DIR, "**", "*.py"),
                          recursive=True):
        name = os.path.splitext(os.path.basename(path))[0]
        in_strategies = os.path.dirname(path) == STRATEGY_DIR
        for node in ast.walk(_parse(path)):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            for module in modules:
                assert "O4_Airport_Elevation_Insets" not in module, path
                if in_strategies and name != "__init__" \
                        and module.startswith("elevation_access.strategies."):
                    cross.add((name, module.rsplit(".", 1)[1]))
                if not in_strategies and name != "__init__":
                    assert not module.startswith(
                        "elevation_access.strategies"), path
    assert cross == CROSS_STRATEGY_IMPORTS
