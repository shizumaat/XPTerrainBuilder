import O4_OSM_Utils as OSM

servers = sorted(OSM.overpass_servers.keys())

cfg_app_vars = {
    "verbosity": {"module": "UI", "type": int, "default": 1,
                  "values": (0, 1, 2, 3), "hint": "Verbosity"},
}
cfg_tile_vars = {
    "default_website": {"type": str, "default": "", "hint": ""},
    "default_zl": {"type": int, "default": 16, "hint": ""},
    "curvature_tol": {"type": float, "default": 2.0, "hint": "curv"},
    "zone_list": {"type": list, "default": [], "hint": ""},
}
cfg_global_tile_vars = {"global_curvature_tol": dict(cfg_tile_vars["curvature_tol"])}
cfg_vars = {**cfg_app_vars, **cfg_tile_vars, **cfg_global_tile_vars}
list_app_vars = ["verbosity"]
list_vector_vars = []
list_mesh_vars = ["curvature_tol"]
list_mask_vars = []
list_dsf_vars = ["default_website", "default_zl", "zone_list"]
list_other_vars = []
