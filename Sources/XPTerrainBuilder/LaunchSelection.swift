import Foundation

/// The build map's selection at launch: EMPTY (owner 2026-11-17T15:55Z).
/// A selection restored from the last session was easy to miss, and a
/// tile the user then selected or searched for was ADDED to it, so a
/// build could take tiles the user never meant. The keys an earlier
/// version stored (`PrefKeys.selectedTiles`, `PrefKeys.activeTile`) are
/// removed so they never come back; the selection is session state.
enum LaunchSelection {
    /// Forgets any stored selection; the launch selection is empty.
    static func start(defaults: UserDefaults = .standard) {
        defaults.removeObject(forKey: PrefKeys.selectedTiles)
        defaults.removeObject(forKey: PrefKeys.activeTile)
    }
}
