"""The elevation access strategies all exist, and exist in the frozen app.

A strategy registers itself when its module is imported, and the frozen
engine carries only modules reached by a STATIC import.  A strategy file
nobody imports is a provider silently lost (the issue #344 class): the
``.elv`` definition still parses, the registry lookup returns ``None``,
and the airport is cut from the base tier with one WARNING line.

``registry.EXPECTED_STRATEGIES`` is the registry as it stood at main ``01662c75``, the
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

if SRC not in sys.path:
    sys.path.insert(0, SRC)
from elevation_access.registry import EXPECTED_STRATEGIES  # noqa: E402

#: registry key -> class name, recorded at main 01662c75 BEFORE the move.
#: The ONE pinned list lives beside the registry (production reads it in
#: ``--import-selfcheck``); this twin pins its size and reads the rest.
EXPECTED_KEYS = EXPECTED_STRATEGIES

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


# ---------------------------------------------------------------------------
# The binary counts its own registry (``--import-selfcheck``)
# ---------------------------------------------------------------------------
def test_the_pinned_set_is_the_26_recorded_at_main():
    """The list itself lives in production code; its size and a spread of
    its entries are pinned here so an edit to it shows up in two diffs."""
    assert len(EXPECTED_STRATEGIES) == 26
    assert EXPECTED_STRATEGIES["tnm_cog"] == "TnmCloudOptimizedGeoTiffStrategy"
    assert EXPECTED_STRATEGIES["las_tile_index"] == "LasTileIndexStrategy"
    assert EXPECTED_STRATEGIES["viewfinder_zip"] == "ViewfinderZipStrategy"
    assert sorted(EXPECTED_STRATEGIES) == _strategy_module_names()


def test_the_selfcheck_counts_the_registry_from_the_engine_entry():
    """From source, through ``Ortho4XP.py`` exactly as the release
    workflow runs the frozen binary."""
    completed = subprocess.run(
        [sys.executable, os.path.join(ENGINE_DIR, "Ortho4XP.py"),
         "--import-selfcheck", "json"],
        capture_output=True, text=True, timeout=300, cwd=ENGINE_DIR)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "elevation_access registry: ok 26 keys" in completed.stdout


def test_the_selfcheck_fails_and_names_a_strategy_that_did_not_register(
        monkeypatch, capsys):
    import O4_Proj_Runtime as runtime
    from elevation_access import registry

    monkeypatch.setattr(registry, "ACCESS_STRATEGIES", {
        key: strategy for (key, strategy) in registry.ACCESS_STRATEGIES.items()
        if key in EXPECTED_STRATEGIES and key != "wcs_kvp"})
    (ok, line) = registry.registry_selfcheck()
    assert not ok
    assert line == ("elevation_access registry: FAIL 25 of 26 keys; "
                    "missing wcs_kvp")
    assert runtime.import_selfcheck_main(
        ["Ortho4XP", "--import-selfcheck", "json"]) == 1
    assert "missing wcs_kvp" in capsys.readouterr().out


def test_the_selfcheck_names_an_unexpected_key_and_a_wrong_class(monkeypatch):
    from elevation_access import registry

    table = {key: strategy
             for (key, strategy) in registry.ACCESS_STRATEGIES.items()
             if key in EXPECTED_STRATEGIES}
    table["not_pinned"] = table["wcs"]
    table["stac"] = table["wcs"]
    monkeypatch.setattr(registry, "ACCESS_STRATEGIES", table)
    (ok, line) = registry.registry_selfcheck()
    assert not ok
    assert "unexpected not_pinned" in line
    assert "wrong class stac=WcsStrategy" in line
