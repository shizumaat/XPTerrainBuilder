import AppKit
import ImageIO
import SceneryKit

/// The map's "Live flight preview" (#2001): each visible texture square
/// drawn from the imagery installed for X-Plane. The engine lists the
/// squares and reads their small mips (SceneryKit `LivePreviewWire`);
/// this keeps them for `FlyMapOverlay`. The Qt window's
/// `O4_Qt_Live_Preview.LivePreview` is the same:
///
/// - the map moved: the squares are asked again after 0.2 s of quiet;
/// - `ImageryFollowStatus.landed` grew: a tier landed, asked again (a
///   square whose stamp changed is fetched again);
/// - `WorldStatus.lastSwap` changed: build-ahead put a tile in (a quick
///   photo, a parked aircraft's full-detail core, #2020), asked again;
/// - missing images are fetched one at a time; at most
///   `LivePreviewCache.limit` are kept.
@MainActor
final class LivePreviewModel: ObservableObject {
    @Published private(set) var squares: [O4LivePreviewSquare] = []
    @Published private(set) var revision = 0
    private(set) var cache = LivePreviewCache<CGImage>()
    private(set) var enabled = false

    /// The engine and Custom Scenery folder, or nil without an engine.
    var context: () -> (client: OrthoEngineClient, sceneryDir: String)? = { nil }

    private var view: (south: Double, west: Double, north: Double, east: Double, pxPerDegree: Double)?
    private var pending: [O4LivePreviewSquare] = []
    private var fetching = false
    private var landed: Int?
    private var swap: [String]?
    private var settle: Task<Void, Never>?

    func setEnabled(_ on: Bool) {
        guard on != enabled else { return }
        enabled = on
        if on {
            refresh()
        } else {
            squares = []
            pending = []
            cache.removeAll()
            revision += 1
        }
    }

    /// The map's viewport and pixels per degree of longitude.
    func setView(south: Double, west: Double, north: Double, east: Double, pxPerDegree: Double) {
        view = (south, west, north, east, pxPerDegree)
        guard enabled else { return }
        settle?.cancel()
        settle = Task { @MainActor [weak self] in
            try? await Task.sleep(nanoseconds: 200_000_000)
            guard !Task.isCancelled else { return }
            self?.refresh()
        }
    }

    /// An `ImageryFollowStatus`'s `landed` count.
    func followLanded(_ count: Int) {
        guard count != landed else { return }
        landed = count
        if enabled { refresh() }
    }

    /// A `WorldStatus`'s `lastSwap`.
    func worldSwapped(_ lastSwap: [String]) {
        guard lastSwap != swap else { return }
        swap = lastSwap
        if enabled { refresh() }
    }

    func image(_ square: O4LivePreviewSquare) -> CGImage? { cache.image(square.key) }

    func refresh() {
        guard enabled, let view, let context = context() else { return }
        context.client.livePreviewSquares(
            south: view.south, west: view.west, north: view.north, east: view.east,
            pxPerDegree: view.pxPerDegree, sceneryDir: context.sceneryDir
        ) { [weak self] rows in
            Task { @MainActor in self?.show(rows) }
        }
    }

    private func show(_ rows: [O4LivePreviewSquare]) {
        guard enabled else { return }
        squares = rows
        cache.touch(rows.map(\.key))
        pending = rows.filter { !cache.isCurrent($0) }
        revision += 1
        fetchNext()
    }

    private func fetchNext() {
        guard !fetching, enabled, !pending.isEmpty, let context = context() else { return }
        let square = pending.removeFirst()
        fetching = true
        context.client.livePreviewMip(path: square.path, px: square.px) { [weak self] data in
            Task { @MainActor in self?.arrived(square, data) }
        }
    }

    private func arrived(_ square: O4LivePreviewSquare, _ data: Data?) {
        fetching = false
        guard enabled else { return }
        if let data, let source = CGImageSourceCreateWithData(data as CFData, nil),
           let image = CGImageSourceCreateImageAtIndex(source, 0, nil) {
            cache.insert(square, image)
            revision += 1
        }
        fetchNext()
    }
}
