import SwiftUI
import SceneryKit

/// The Activity list's native selection, bound both ways to the map's tile
/// selection (#1537, RULINGS 2026-10-28n): the list shows selected every
/// row whose tile is selected on the map, and a selection the user makes
/// in the list becomes the map selection (`ActivityOrder.listEdit`). A
/// click on a row (an edit leaving one row selected) frames its tile
/// (#816). Qt twin:
/// `O4_Qt_Activity_List`.
enum ActivityListSelection {
    typealias Tile = BuildModel.TileCoord

    static func binding(rows: @escaping () -> [Tile],
                        selected: Binding<Set<Tile>>,
                        active: Binding<Tile?>,
                        frame: @escaping (Tile) -> Void) -> Binding<Set<Tile>> {
        Binding(
            get: { ActivityOrder.shownSelected(rows: rows(), selected: selected.wrappedValue) },
            set: { new in
                let shown = ActivityOrder.shownSelected(rows: rows(),
                                                        selected: selected.wrappedValue)
                guard new != shown else { return }
                let edit = ActivityOrder.listEdit(new: new, shown: shown,
                                                  active: active.wrappedValue)
                selected.wrappedValue = edit.selected
                active.wrappedValue = edit.active
                if edit.frame, let tile = edit.active { frame(tile) }
            })
    }
}
