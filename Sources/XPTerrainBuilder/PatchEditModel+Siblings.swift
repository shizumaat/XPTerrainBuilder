import Foundation
import SceneryKit

/// An airport whose patch spans several tiles has one patch file per tile
/// (#1646). The nearest one is the editable document; the same airport's
/// patches on the other tiles in view are loaded here and drawn read-only
/// beside it, so the map shows the whole airport.
extension PatchEditModel {
    /// Indices of `candidates` (tile, ICAO) that are `icao` on a tile
    /// other than `tile`.
    nonisolated static func siblingIndices(_ candidates: [(String, String)],
                                           tile: String, icao: String) -> [Int] {
        candidates.indices.filter { candidates[$0].1 == icao && candidates[$0].0 != tile }
    }

    func showSiblings(_ entries: [(tile: String, entry: O4PatchListEntry)],
                      client: OrthoEngineClient) {
        let wanted = Dictionary(entries.map { ("\($0.tile)|\($0.entry.path)", $0) },
                                uniquingKeysWith: { a, _ in a })
        if Set(wanted.keys) != Set(siblings.keys) {
            siblings = siblings.filter { wanted[$0.key] != nil }
            publishSiblings()
        }
        for (key, item) in wanted where siblings[key] == nil {
            siblings[key] = .some(nil) // loading
            Task { [weak self] in
                guard let reply = try? await client.patchLoad(tile: item.tile, icao: item.entry.icao) else {
                    return
                }
                let geometry = await Task.detached(priority: .userInitiated) {
                    PatchMapGeometry(document: PatchDocument(tile: item.tile, load: reply))
                }.value
                guard let self, self.siblings[key] != nil else { return }
                self.siblings[key] = geometry
                self.publishSiblings()
            }
        }
    }

    private func publishSiblings() {
        siblingGeometry = siblings.keys.sorted().compactMap { siblings[$0] ?? nil }
    }
}
