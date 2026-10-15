import Foundation

/// The app's one copy of an airport pack's buildings (`pack_objects`,
/// spec §2, §4, §5): the map's footprints and the 3D window's massing ask
/// here, so one request serves both. A request whose box lies inside a
/// box already asked for (pending or answered) for the same tile and
/// airport shares that answer; a failed request is forgotten, so the next
/// ask retries. `invalidate(tile:)` drops a rebuilt tile's answers (the
/// rebuild may have re-seated the pack's objects).
@MainActor
public final class PackBuildingsStore {
    public typealias Fetch = @Sendable (O4LatLonBox) async throws -> O4PackObjects

    /// The app's store (both consumers reach it without a shared owner).
    public static let shared = PackBuildingsStore()

    private struct Entry {
        let id: Int
        let tile: String
        let icao: String
        let box: O4LatLonBox
        let task: Task<O4PackObjects, Error>
    }

    private var entries: [Entry] = []
    private var nextID = 0
    private let capacity: Int

    public init(capacity: Int = 4) { self.capacity = max(capacity, 1) }

    /// The buildings inside `box`: a shared answer when one covers it,
    /// else `fetch(box)` — called at most once per new box.
    public func objects(tile: String, icao: String, box: O4LatLonBox,
                        fetch: @escaping Fetch) async throws -> O4PackObjects {
        let icao = icao.uppercased()
        if let hit = entries.last(where: { $0.tile == tile && $0.icao == icao && $0.box.contains(box) }) {
            return try await hit.task.value
        }
        nextID += 1
        let id = nextID
        let task = Task { try await fetch(box) }
        entries.append(Entry(id: id, tile: tile, icao: icao, box: box, task: task))
        if entries.count > capacity { entries.removeFirst(entries.count - capacity) }
        do {
            return try await task.value
        } catch {
            entries.removeAll { $0.id == id }
            throw error
        }
    }

    public func invalidate(tile: String) {
        entries.removeAll { $0.tile == tile }
    }
}

extension PackBuildingsStore {
    /// Through the engine session's `pack_objects`.
    public func objects(client: OrthoEngineClient, tile: String, icao: String,
                        box: O4LatLonBox) async throws -> O4PackObjects {
        try await objects(tile: tile, icao: icao, box: box) { box in
            try await client.packObjects(tile: tile, icao: icao, bbox: box)
        }
    }
}
