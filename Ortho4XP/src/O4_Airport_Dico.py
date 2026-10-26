"""The tile build's AIRPORT DICTIONARY: ``build_airports_dico`` — the
``O4_Airport_Utils`` chain (discovery, surfaces, runways, discards,
hangar / apron / taxiway areas, boundaries) over an already-loaded OSM
airport layer, each airport named by apt.dat where it knows it, else by
a stable identifier from its position (``O4_Airport_Apt_Identity``).

Moved out of ``O4_Vector_Map`` (#836): the vector step builds the tile's
own dictionary with it, the mesh step's approach rings build a
NEIGHBOUR's; a leaf here keeps the mesh step's code key off the vector
step.
"""
from __future__ import annotations

import O4_Airport_Apt_Identity as APT_IDENTITY
import O4_Airport_Utils as APT

__all__ = ["build_airports_dico"]


def build_airports_dico(tile, airport_layer, persist=True):
    """The tile build's airport-dictionary chain, exactly as
    ``load_airports_and_prepare_dem`` runs it (discovery, surfaces,
    runway reconstruction, discards, hangar/apron/taxiway areas,
    boundaries).  Factored out (2026-07-19, production-DEM parity v2)
    so the standalone DEM loader in ``auto_patch.elevation`` can build
    the same ``dico_airports`` the production airport smoothing uses.
    Pure compute over the already-loaded layer — no network.

    *persist* writes the dictionary to the tile's ``Data*.apt`` for Steps
    2 and 3; a NEIGHBOUR read passes False (#676: it wrote into a
    neighbour's build folder that did not exist)."""
    dico_airports = {}
    APT.discover_airport_names(airport_layer, dico_airports)
    # Identity and extent from apt.dat, OSM aerodromes the fallback
    # (owner 2026-10-19; O4_Airport_Apt_Identity).
    known_codes = set()
    APT_IDENTITY.adopt_apt_dat_identities(
        dico_airports, APT_IDENTITY.tile_apt_dat_airports(
            tile.lat, tile.lon, known_codes=known_codes))
    APT.attach_surfaces_to_airports(airport_layer, dico_airports)
    APT_IDENTITY.drop_unclaimed_seeds(dico_airports)
    # Every airport left without a code gets a stable one from its
    # position (owner 2026-10-26, #1353): no pass keyed by code skips it.
    APT_IDENTITY.assign_synthetic_ids(dico_airports, known_codes)
    APT.sort_and_reconstruct_runways(tile, airport_layer, dico_airports)
    APT.discard_unwanted_airports(tile, dico_airports)
    APT.build_hangar_areas(tile, airport_layer, dico_airports)
    APT.build_apron_areas(tile, airport_layer, dico_airports)
    APT.build_taxiway_areas(tile, airport_layer, dico_airports)
    APT.update_airport_boundaries(tile, dico_airports)
    if persist:
        APT.save_airport_info(tile, dico_airports)
    return dico_airports
