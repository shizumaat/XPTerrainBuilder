"""Contract tripwire for the DSF object integration (amendment A8).

The workstream-W1 contracts in ``docs/dsf_object_integration_spec.md``
(section 3, as amended by section 10 / A10) are frozen the moment W1
merges: seven modules, their signatures, their data-shape fields, and the
config flags.  Every downstream workstream (W2–W7) builds against them in
parallel, so silent drift in one agent's branch breaks a sibling's
integration two workstreams later — unless it breaks THIS file first.

Where this file and any prose section disagree, this file is the tiebreak
(amendment A10).  Changing a contract requires amending the spec, then
this file, in the same commit.

Pure hermetic: imports and ``inspect`` only — no X-Plane install, no
filesystem fixtures, no geometry.
"""

from __future__ import annotations

import dataclasses
import inspect

import pytest

from auto_patch import (
    config,
    mesh_sampler,
    obj8_partition,
    obj8_reader,
    object_anchor,
    object_footprints,
    object_rebake,
    post_mesh,
)


def _parameter_names(callable_object) -> list[str]:
    return list(inspect.signature(callable_object).parameters)


# ---------------------------------------------------------------------------
# config flags — name, type, default (spec section 4-W1 + amendment A10)
# ---------------------------------------------------------------------------

FLAG_EXPECTATIONS = [
    ("DSF_OBJECT_BUILDINGS", bool, True),
    ("DSF_OBJECT_FOOTPRINT_UNION", bool, False),
    ("DSF_OBJECT_REANCHOR", bool, True),
    # Default flipped on 2026-07-24 (owner): rigid one-offset-per-block
    # baking is trusted; I-11 still refuses blocks spanning offsets.
    ("DSF_OBJECT_ALLOW_ANIM", bool, True),
    ("DSF_OBJECT_MIN_REACH_M", float, 25.0),
    ("DSF_OBJECT_CONTACT_EPSILON_M", float, 0.25),
    ("DSF_OBJECT_FOOTPRINT_HEIGHT_M", float, 1.5),
    ("DSF_OBJECT_ELEVATED_BASE_M", float, 0.5),
    # Backstop enabled by default (was 0.0 = disabled) — defect 2026-07-17,
    # UK payware co-baked airports: an airport-sized chained hull would
    # otherwise cannibalise the real building pads it overlaps.
    ("DSF_OBJECT_MAX_FOOTPRINT_AREA_M2", float, 100000.0),
    ("DSF_OBJECT_MIN_BUILDING_HEIGHT_M", float, 2.5),
    ("DSF_OBJECT_PAD_FLAG_SPAN_M", float, 2.0),
    # Connector pre-filter + structure span gate (same defect).  Both are
    # refinements gated OFF by default (the area backstop is the shipping
    # fix); the connector flag is a bool, the span gate a 0-disabled cap.
    ("DSF_OBJECT_CONNECTOR_PREFILTER", bool, False),
    ("DSF_OBJECT_CONNECTOR_SPAN_M", float, 300.0),
    ("DSF_OBJECT_CONNECTOR_MAX_FILL", float, 0.20),
    ("DSF_OBJECT_MAX_STRUCTURE_SPAN_M", float, 0.0),
    # R18-2 building evidence (owner ruling 2026-08-11b).  ON by default:
    # it IS the law, not a refinement.  The two values are MEASURED, not
    # chosen (HECA Tai Models, tools/object_pad_evidence_report.py):
    # 6.0 m sits in the pack's own gap between the tallest non-building
    # structure (jet blast deflector, 5.87 m) and the shortest building
    # member (6.09 m); the coverage floor is 0 because a material-split
    # pack's REAL terminal shells measure the same 0.000-0.02 coverage
    # as the phantom slab class, so no floor separates them.
    # The same measurement ruled the two pending defences: neither is
    # armed.  The structure-span gate at HECA catches 6 rings of which
    # the evidence gate already refuses 3, and all 3 marginal ones are
    # real buildings (a 60,392 m² terminal shell with a 113 m member);
    # the connector pre-filter drops 192 of the 336 evidence-vouched
    # rings — the documented EGGW/EGLL failure reproduced, because in a
    # material-split pack every texture page spans the field.
    ("DSF_OBJECT_BUILDING_EVIDENCE", bool, True),
    ("DSF_OBJECT_EVIDENCE_MIN_HEIGHT_M", float, 6.0),
    ("DSF_OBJECT_EVIDENCE_MIN_COVERAGE", float, 0.0),
    # Per-cluster seating (docs/specs/per-cluster-object-seating-spec.md).
    # Phase C lands GATED OFF (spec section 7.1: default-on waits on the
    # owner's HECA in-sim verdict); T and the pad relief cap ship at
    # their measured/recommended values so flipping the gate is one flag.
    # Default ON since the owner ruling 2026-07-27 ("we have to find a
    # way to get them down") — HECA skipped structures 6,386 → 41.
    ("DSF_OBJECT_CLUSTER_SEATING", bool, True),
    ("DSF_OBJECT_CLUSTER_SEAT_TOLERANCE_M", float, 0.5),
    ("DSF_OBJECT_PAD_MAX_RELIEF_M", float, 3.0),
    # The pad CONSUMER gate.  DEFAULT ON per
    # docs/specs/object-reseat-threshold-spec.md §2.3: the parent spec held
    # it off pending an owner in-sim verdict, and the owner's 2026-08-09
    # charter ("adapt the terrain to the custom objects, rather than
    # reseating the objects") IS that verdict.  The env kill switch
    # (O4_DSF_OBJECT_OBJECT_PADS=0) stays.
    ("DSF_OBJECT_OBJECT_PADS", bool, True),
]


@pytest.mark.parametrize(
    "name, expected_type, expected_default",
    FLAG_EXPECTATIONS,
    ids=[name for name, _, _ in FLAG_EXPECTATIONS],
)
def test_config_flag(name, expected_type, expected_default, monkeypatch):
    value = getattr(config, name)
    assert isinstance(value, expected_type)
    # Defaults hold in a clean environment (the suite does not set O4_*
    # overrides; if a developer's shell does, this catches it loudly).
    assert value == expected_default, (
        f"{name} != documented default — is an O4_* environment override "
        f"set in this shell?"
    )
    assert name in config.__all__


def test_amendment_a10_retired_flags_do_not_exist():
    """A10: the contact graph retired the gap and anchor-proximity knobs.
    Reintroducing them means someone implemented the superseded section 3
    text instead of the amendments."""
    for retired in (
        "DSF_OBJECT_STRUCTURE_GAP_M",
        "DSF_OBJECT_ANCHOR_PROXIMITY_M",
        "DSF_OBJECT_HEADING_TOLERANCE_DEG",
    ):
        assert not hasattr(config, retired), retired


# ---------------------------------------------------------------------------
# obj8_reader (spec section 3.1)
# ---------------------------------------------------------------------------

def test_object_placement_fields():
    assert obj8_reader.ObjectPlacement._fields == (
        "definition_index",
        "resource_path",
        "longitude",
        "latitude",
        "heading_degrees",
        # Amendment A18: OBJECT_AGL placements carry the distant-anchor
        # disease with a constant vertical offset; plain OBJECT rows
        # default to zero.
        "above_ground_level_metres",
        # W-R1 (object-terrain-features spec): the source keyword and the
        # absolute elevation of opt-in OBJECT_MSL rows.
        "placement_kind",
        "mean_sea_level_elevation_m",
    )
    assert (
        obj8_reader.ObjectPlacement._field_defaults[
            "above_ground_level_metres"
        ]
        == 0.0
    )
    assert (
        obj8_reader.ObjectPlacement._field_defaults["placement_kind"]
        == "OBJECT"
    )
    assert (
        obj8_reader.ObjectPlacement._field_defaults[
            "mean_sea_level_elevation_m"
        ]
        is None
    )


def test_positional_command_fields():
    assert obj8_reader.PositionalCommand._fields == (
        "line_index",
        "keyword",
        "x",
        "y",
        "z",
        "y_token_index",
    )


def test_object_geometry_fields():
    assert obj8_reader.ObjectGeometry._fields == (
        "vertices",
        "solid_triangles",
        "draped_triangles",
        "positional_commands",
        "animation_block_count",
        "level_of_detail_count",
        "vertex_line_indices",
        # W-R3 (object-terrain-features spec, Part 1): per-solid-triangle
        # ATTR_hard / ATTR_hard_deck state, parallel to solid_triangles;
        # immutable "" default so pre-change callers are unaffected.
        "solid_triangle_hardness",
        # Object-pavement classifier: the draped draw layer declared by
        # ``ATTR_layer_group_draped <group> <offset>``, or None when the
        # file declares none.
        "draped_layer_group",
    )
    assert (
        obj8_reader.ObjectGeometry._field_defaults["solid_triangle_hardness"]
        == ()
    )
    assert (
        obj8_reader.ObjectGeometry._field_defaults["draped_layer_group"]
        is None
    )
    assert callable(obj8_reader.ObjectGeometry.hard_deck_solid_triangles)
    assert isinstance(
        inspect.getattr_static(
            obj8_reader.ObjectGeometry, "has_solid_geometry"
        ),
        property,
    )
    assert isinstance(
        inspect.getattr_static(
            obj8_reader.ObjectGeometry, "has_mixed_draped_solid_vertices"
        ),
        property,
    )
    assert callable(obj8_reader.ObjectGeometry.solid_reach_metres)


OBJ8_READER_SIGNATURES = [
    ("load_object_file", ["path"]),
    ("area_weighted_centroid", ["vertices", "triangles"]),
    ("horizontal_bounding_box", ["vertices", "triangles"]),
    (
        "local_offset_to_lonlat",
        [
            "anchor_latitude",
            "anchor_longitude",
            "heading_degrees",
            "local_x",
            "local_z",
        ],
    ),
    (
        "lonlat_to_local_offset",
        [
            "anchor_latitude",
            "anchor_longitude",
            "heading_degrees",
            "latitude",
            "longitude",
        ],
    ),
    (
        "read_dsf_object_placements",
        ["dsf_text_lines", "accept_resource", "include_object_msl"],
    ),
    (
        "resolve_object_resource",
        ["resource_path", "pack_root", "xplane_root"],
    ),
]


@pytest.mark.parametrize(
    "name, expected_parameters",
    OBJ8_READER_SIGNATURES,
    ids=[name for name, _ in OBJ8_READER_SIGNATURES],
)
def test_obj8_reader_signature(name, expected_parameters):
    assert _parameter_names(getattr(obj8_reader, name)) == expected_parameters


# ---------------------------------------------------------------------------
# obj8_partition (amendment A1)
# ---------------------------------------------------------------------------

#: ``(name, frozen_call_signature, declared_optional_extensions)``.
#:
#: STALE-FIXTURE REPAIR (beta hardening, H2).  This twin used to compare
#: ``list(inspect.signature(fn).parameters)`` against one flat list, so
#: commit 6045e6b6 ("perf P3 lane G: object partition -7.3 s CPU at HECA,
#: byte-identical to the frozen 1.0.245 baseline") turned it red by
#: adding ``vertex_array`` / ``part_geometries`` to ``contact_graph`` —
#: two KEYWORD-ONLY parameters with defaults, which let a caller hand in
#: derivations it already holds.  Amendment A1's contract is the CALL
#: SIGNATURE, and a keyword-only default extends it without changing it:
#: every existing call site is unaffected, and the lane's own acceptance
#: was byte-identity.
#:
#: So the guard is kept and sharpened rather than loosened.  The frozen
#: list is now exactly the REQUIRED (positional-or-keyword) parameters —
#: reorder, rename, add or remove one and this still fails — and any
#: optional keyword-only extension must be DECLARED here, so a new one
#: cannot arrive unnoticed either.
OBJ8_PARTITION_SIGNATURES = [
    ("weld_parts", ["vertices", "triangles"], []),
    ("contact_graph", ["vertices", "parts", "epsilon_metres"],
     ["vertex_array", "part_geometries"]),
    ("connected_structures", ["part_count", "contact_edges"], []),
]


@pytest.mark.parametrize(
    "name, expected_parameters, expected_optional",
    OBJ8_PARTITION_SIGNATURES,
    ids=[name for name, _, _ in OBJ8_PARTITION_SIGNATURES],
)
def test_obj8_partition_signature(name, expected_parameters,
                                  expected_optional):
    parameters = inspect.signature(
        getattr(obj8_partition, name)).parameters
    required = [
        pname for pname, p in parameters.items()
        if p.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        and p.default is inspect.Parameter.empty
    ]
    assert required == expected_parameters
    optional = [pname for pname, p in parameters.items()
                if pname not in required]
    assert optional == expected_optional, (
        f"{name} grew an undeclared optional parameter — an extension is "
        f"lawful, an undeclared one is not")
    for pname in optional:
        p = parameters[pname]
        assert p.kind is inspect.Parameter.KEYWORD_ONLY, (
            f"{name}'s {pname} is not keyword-only — that CHANGES the "
            f"frozen A1 call signature, it does not extend it")
        assert p.default is not inspect.Parameter.empty, (
            f"{name}'s {pname} has no default — existing call sites break")


def test_superseded_grouping_not_ported():
    """A10: ``group_components_into_structures`` (the 2 m bounding-box gap
    heuristic) is deliberately not ported; ``weld_parts`` subsumes
    ``connected_components``."""
    for module in (obj8_reader, obj8_partition):
        assert not hasattr(module, "group_components_into_structures")
        assert not hasattr(module, "connected_components")


# ---------------------------------------------------------------------------
# mesh_sampler (spec section 3.2)
# ---------------------------------------------------------------------------

def test_mesh_sampler_contract():
    assert issubclass(mesh_sampler.OutsideMeshError, Exception)
    init_parameters = _parameter_names(
        mesh_sampler.MeshElevationSampler.__init__
    )
    assert init_parameters == [
        "self",
        "mesh_path",
        "bounds",
        "margin_degrees",
    ]
    assert _parameter_names(
        mesh_sampler.MeshElevationSampler.elevation_at
    ) == ["self", "latitude", "longitude"]
    assert _parameter_names(
        mesh_sampler.MeshElevationSampler.elevation_at_or_none
    ) == ["self", "latitude", "longitude"]


# ---------------------------------------------------------------------------
# object_anchor (spec section 3.3, amended by A1/A3/A10)
# ---------------------------------------------------------------------------

def _dataclass_field_names(dataclass_type) -> tuple[str, ...]:
    return tuple(
        each_field.name for each_field in dataclasses.fields(dataclass_type)
    )


def test_object_pool_fields():
    assert _dataclass_field_names(object_anchor.ObjectPool) == (
        "placements",
        "resolved_paths",
    )


def test_structure_fields():
    assert _dataclass_field_names(object_anchor.Structure) == (
        "triangles_by_resource",
        "surface_area_square_metres",
        "centroid_latitude",
        "centroid_longitude",
        "minimum_base_y_by_resource",
        "is_ground_touching",
        "ground_span_metres",
        "needs_pad",
        "skip_reason",
        "inherited_from_structure_index",
        # Per-cluster seating
        # (docs/specs/per-cluster-object-seating-spec.md section 3.1):
        # the epsilon-contact edges among this structure's parts,
        # threaded through from partition_structures so structure_deltas
        # can cut them without recomputing the narrow phase.  Defaults
        # empty — an empty edge set means "fall back to the
        # per-STRUCTURE rigid seat", never a shredded cluster set.
        "contact_edges",
    )


def test_rebake_decision_fields():
    assert _dataclass_field_names(object_anchor.RebakeDecision) == (
        "structures",
        "delta_by_resource_and_vertex",
        "anchor_ground_by_resource",
        "skipped",
        # Amendment A13: per-resource anchors so the provenance sidecar
        # can record them on fresh bakes; defaults empty for
        # hand-constructed decisions.
        "anchor_by_resource",
        # Multi-ground-cluster foot re-anchor
        # (docs/multi_foot_object_reanchor.md): the per-structure foot
        # audit trail and the per-foot terrain-pad requests; both
        # default empty for hand-constructed decisions.
        "foot_clusters_by_structure_index",
        "foot_pad_requests",
        # Per-cluster seating
        # (docs/specs/per-cluster-object-seating-spec.md sections 4.5
        # and 5.3): the ClusterPadRequest sibling of the foot requests,
        # the tear audit's reported cut/bridge seams, and the run
        # record's cluster counts.  All empty when
        # DSF_OBJECT_CLUSTER_SEATING is off.
        "cluster_pad_requests",
        "cluster_seams",
        "cluster_counts",
        # Basin rim-flush seating
        # (docs/specs/basin-rim-flush-seating-spec.md section 2.2 item
        # 5): WHICH LAW seated each resource, recorded in the provenance
        # sidecar.  Empty for the generic seating law — which is what a
        # provenance entry without the key has always meant.
        "decision_kind_by_resource",
        # The basin GROUP seat (docs/specs/basin-group-seat-spec.md §2.5,
        # recon trap T6): the datum plane ``G`` a group member was seated
        # onto, written to the provenance beside the applied delta so a
        # restored pack can still be audited.  Empty for every law with
        # no group datum to name.
        "seat_datum_by_resource",
    )


OBJECT_ANCHOR_SIGNATURES = [
    (
        "discover_object_pools",
        [
            "placements",
            "resolved_paths",
            "geometry_by_resource",
            "epsilon_metres",
        ],
    ),
    (
        "partition_structures",
        ["pool", "geometry_by_resource", "epsilon_metres"],
    ),
    (
        "structure_deltas",
        [
            "pool",
            "geometry_by_resource",
            "structures",
            "sampler",
            # Reseat threshold (docs/specs/object-reseat-threshold-
            # spec.md section 2.3): keyword-only, defaults False, and
            # carries the tile's ``modify_custom_airports`` switch —
            # the pass runs, routes every unit as below-threshold and
            # writes nothing to the pack.
            "measure_only",
            # THE OBJECT PAD FRAME (RULINGS "OBJECT PADS: EMISSION-TIME
            # RELATIVE", owner 2026-08-14; Fable's R3 step 2):
            # keyword-only, defaults None, and carries the build's ONE
            # mesh-free frame so this function consumes the welding
            # instead of repeating it.  ``None`` is the pre-frame
            # behaviour byte for byte — it welds for itself.
            "pad_frame",
        ],
    ),
]


@pytest.mark.parametrize(
    "name, expected_parameters",
    OBJECT_ANCHOR_SIGNATURES,
    ids=[name for name, _ in OBJECT_ANCHOR_SIGNATURES],
)
def test_object_anchor_signature(name, expected_parameters):
    assert _parameter_names(getattr(object_anchor, name)) == (
        expected_parameters
    )


def test_amendment_a10_anchor_group_renamed():
    """A10: pooling is a world-geometry property, not an anchor property."""
    assert not hasattr(object_anchor, "AnchorGroup")
    assert not hasattr(object_anchor, "discover_anchor_groups")


# ---------------------------------------------------------------------------
# object_rebake (spec section 4-W5, amended by A2/A6)
# ---------------------------------------------------------------------------

def test_rebake_report_fields():
    assert _dataclass_field_names(object_rebake.RebakeReport) == (
        "objects_written",
        "vertices_offset_total",
        "structures_baked",
        "structures_needing_pad",
        "skipped",
        "orphaned_backups",
        "provenance_path",
        # Exclusion reversion pass (O4_OBJECT_REBAKE_REVERT_EXCLUDED):
        # excluded objects un-baked from their backups, and the ones
        # whose backup is missing (reported, never overwritten).
        "objects_reverted",
        "reversions_missing_backup",
        # Amendment A21: objects written with some structures left at
        # their authored y (per-structure partial bake).
        "partially_baked",
    )


def test_object_rebake_signatures():
    assert _parameter_names(object_rebake.apply) == [
        "decision",
        "pack_root",
        "mesh_path",
    ]
    assert _parameter_names(object_rebake.check) == [
        "pack_root",
        "mesh_path",
    ]
    assert _parameter_names(object_rebake.restore) == ["pack_root"]


# ---------------------------------------------------------------------------
# object_footprints (spec section 4-W6)
# ---------------------------------------------------------------------------

def test_object_footprints_signature():
    # ``evidence_out`` (R18-2) is an OPTIONAL out-parameter appended to
    # the frozen three: it never changes what the function returns, and
    # it is how the population table is read through production's own
    # code path instead of a second implementation.
    assert _parameter_names(object_footprints.structure_ring) == [
        "structure",
        "geometry_by_resource",
        "placements",
        "evidence_out",
    ]
    import inspect
    assert inspect.signature(
        object_footprints.structure_ring
    ).parameters["evidence_out"].default is None


# ---------------------------------------------------------------------------
# post_mesh (spec section 4-W7, amended by A4/A5)
# ---------------------------------------------------------------------------

def test_post_mesh_signature():
    assert _parameter_names(post_mesh.rebake_dsf_objects) == ["tile"]


# ---------------------------------------------------------------------------
# stubs stay stubs until their workstream lands
# ---------------------------------------------------------------------------
#
# Retired 2026-07-08: every workstream (W2-W7) has landed and each
# module's real test file has taken over — tests/test_obj8_reader.py,
# tests/test_obj8_partition.py, tests/test_mesh_sampler.py,
# tests/test_object_anchor.py, tests/test_object_rebake.py,
# tests/test_dsf_object_buildings.py, tests/test_post_mesh.py.  The
# signature and data-shape assertions above remain the permanent
# contract tripwire.
