import SwiftUI
import SceneryKit

/// The map's Filter menu (#2097; Qt: `O4_Map_Filter` + `O4_Qt_Map_Filter`,
/// same keys, words and order): two sections of independent toggles, each
/// item on or off with a check mark, kept per user.
///
/// Airports — ICAO / Small is the airport's KIND (the engine index's
/// `icao_airport` category is ICAO, every other row Small; a custom pack's
/// airport takes the index's kind by code, Small when the index lacks it);
/// Custom Scenery / Global is its SOURCE. A mark draws when its kind AND
/// its source are on.
///
/// Ortho Tiles — Full (the World pack's full, mesh and placeholder tiles,
/// a built tile the World pack does not list, #2031, and other installed
/// ortho packages), Drape (the World pack's drapes), Favorites (a built
/// tile marked Favorite, #2033). A tile draws when ANY of its items is on.
///
/// Only the items turned OFF are stored, so a later item starts on.
enum MapFilterItem: String, CaseIterable {
    case icao, small, custom, global
    case favorites, full, drape

    var label: String {
        switch self {
        case .icao: return "ICAO"
        case .small: return "Small"
        case .custom: return "Custom Scenery"
        case .global: return "Global"
        case .favorites: return "Favorites"
        case .full: return "Full"
        case .drape: return "Drape"
        }
    }

    /// The menu's sections, top to bottom; the headers are not selectable.
    static let sections: [(header: String, items: [MapFilterItem])] = [
        ("Airports", [.icao, .small, .custom, .global]),
        ("Ortho Tiles", [.favorites, .full, .drape]),
    ]
}

/// The items turned off, and what they leave on the map.
struct MapFilter: Equatable {
    /// The `@AppStorage` key (Qt prefs: `map_filter_hidden`).
    static let storageKey = "MapFilterHidden"

    var hidden: Set<MapFilterItem>

    /// From the stored comma list; unknown keys are dropped.
    init(stored: String) {
        hidden = Set(stored.split(separator: ",").compactMap { MapFilterItem(rawValue: String($0)) })
    }

    /// The stored form: the off keys in menu order.
    var stored: String {
        MapFilterItem.allCases.filter(hidden.contains).map(\.rawValue).joined(separator: ",")
    }

    var isFiltering: Bool { !hidden.isEmpty }

    func showsAirport(icaoCoded: Bool, custom: Bool) -> Bool {
        !hidden.contains(icaoCoded ? .icao : .small) && !hidden.contains(custom ? .custom : .global)
    }

    /// A tile of World `state` (nil: a built tile the World pack does not
    /// list) draws when its item is on, or it is a Favorite and Favorites
    /// is on.
    func showsTile(state: O4WorldTile.State?, pinned: Bool) -> Bool {
        if pinned, !hidden.contains(.favorites) { return true }
        switch state {
        case nil, .full, .meshLowRes, .placeholder: return !hidden.contains(.full)
        case .drape: return !hidden.contains(.drape)
        case .nothing: return false
        }
    }

    /// Other installed ortho / mesh packages' outlines are Full ortho.
    var showsOtherOrtho: Bool { !hidden.contains(.full) }

    /// Any Ortho item on (the map key's build kinds).
    var showsAnyTile: Bool {
        !hidden.isSuperset(of: [.favorites, .full, .drape])
    }
}

/// The toolbar's Filter menu: a section per header, a check-marked toggle
/// per item (Qt: `O4_Qt_Map_Filter.FilterMenu`).
struct MapFilterMenu: View {
    @Binding var stored: String

    private var filter: MapFilter { MapFilter(stored: stored) }

    var body: some View {
        Menu {
            ForEach(MapFilterItem.sections, id: \.header) { section in
                Section(section.header) {
                    ForEach(section.items, id: \.self) { item in
                        Toggle(item.label, isOn: binding(item))
                    }
                }
            }
        } label: {
            Image(systemName: filter.isFiltering
                  ? "line.3.horizontal.decrease.circle.fill"
                  : "line.3.horizontal.decrease.circle")
        }
        .help("Choose which airports and ortho tiles the map shows")
    }

    private func binding(_ item: MapFilterItem) -> Binding<Bool> {
        Binding(get: { !filter.hidden.contains(item) },
                set: { on in
                    var next = filter
                    if on { next.hidden.remove(item) } else { next.hidden.insert(item) }
                    stored = next.stored
                })
    }
}
