"""THE LIBRARY EQUIVALENTS "Optimise pack" may swap a pack's vehicles and
ground equipment for (issue #1707 D2).

Owner (2026-10-30): "if we're able to identify specific, highly repeated
objects, that have clear equivalents in laminar's library, which I think
all of these do, then we could offer to swap them with the more modern
and efficient objects from the laminar library."  And (2026-11-03): the
witness is the NAME TOKEN and the FOOTPRINT; a vehicle is swapped even
when its front cannot be proven.

Each class is the words an object's FILE NAME must carry (any one of the
word sets, every word of it — ``BaggageCar1`` reads ``baggage car``) and
the X-Plane library objects it may become; the footprint picks among
them and may refuse them all (``swap``).  The classes are tried in
order, so the more specific one (a baggage car) is read before the
general one (a car).  Every path is X-Plane's own library vocabulary;
none names a pack or an airport.
"""
from __future__ import annotations

__all__ = ["CLASSES"]

_R = "lib/airport/Ramp_Equipment/"
_V = "lib/airport/Common_Elements/Vehicles/"

#: ``(class, word sets, library objects)`` in reading order
CLASSES: tuple[tuple[str, tuple[frozenset[str], ...], tuple[str, ...]], ...] = (
    ("baggage cart",
     (frozenset({"baggage"}), frozenset({"luggage"}), frozenset({"lugg"}),
      frozenset({"bagg"})),
     (_R + "baggage/cart_8ft_1.obj", _R + "baggage/cart_10ft_1.obj")),
    ("cargo dolly",
     (frozenset({"dolly"}),),
     (_R + "cargo/dolly_LD3_1.obj", _R + "Cargo_Dolly_1.obj")),
    ("stairs",
     (frozenset({"stairs"}), frozenset({"stair"}), frozenset({"airportstairs"}),
      frozenset({"steps"})),
     (_R + "Stair_Maint_1.obj", _R + "PAX_stairs_1.obj")),
    ("fire truck",
     (frozenset({"firetruck"}), frozenset({"fire", "truck"}),
      frozenset({"fire", "engine"})),
     ("lib/airport/fire_department/striker_8x8_1.obj",)),
    ("fuel truck",
     (frozenset({"fuel", "truck"}), frozenset({"fueltruck"}),
      frozenset({"fuel", "bowser"})),
     (_V + "Fuel_Truck_Large.obj", _V + "Fuel_Truck_Small.obj")),
    ("belt loader",
     (frozenset({"belt", "loader"}), frozenset({"beltloader"})),
     (_R + "Belt_Loader.obj",)),
    ("tug",
     (frozenset({"tug"}), frozenset({"pushback"}), frozenset({"tractor"})),
     (_R + "Tug660_Dn_1.obj", _R + "Tow_Tractor_3.obj")),
    ("ground power unit",
     (frozenset({"gpu"}),),
     (_R + "GPU_1.obj", _R + "GPU_2.obj")),
    ("bus or van",
     (frozenset({"bus"}), frozenset({"cobus"}), frozenset({"minibus"}),
      frozenset({"van"}), frozenset({"shuttle"})),
     (_V + "airside_operations/van_01.obj", _V + "airside_operations/van_02.obj",
      _R + "PAX_bus_1.obj", _R + "PAX_bus_2.obj")),
    ("car",
     (frozenset({"car"}), frozenset({"sedan"}), frozenset({"suv"}),
      frozenset({"pickup"})),
     ("lib/cars/car_static_invar.obj",)),
)
