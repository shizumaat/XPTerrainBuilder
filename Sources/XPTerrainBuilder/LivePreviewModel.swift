import AppKit
import ImageIO
import SceneryKit

/// The map's "Live flight preview" (#2001): each visible texture square
/// drawn from the imagery installed for X-Plane, at the resolution the map
/// shows it, marked where X-Plane shows something else (owner
/// 2026-11-12T19:28Z). The engine lists the squares and reads their mips
/// (SceneryKit `LivePreviewWire`); this keeps them for
/// `LivePreviewDrawing`. The Qt window's `O4_Qt_Live_Preview.LivePreview`
/// is the same:
///
/// - the map moved: the squares are asked again after 0.2 s of quiet,
///   with the screen's backing scale (a square's mip is its size in
///   device pixels);
/// - `ImageryFollowStatus.landed` grew: a tier landed, asked again (a
///   square whose stamp changed is fetched again);
/// - `WorldStatus.lastSwap` changed: build-ahead put a tile in (#2020),
///   asked again;
/// - images are fetched in `LivePreviewCache.plan` order (coarse first,
///   then each square at its own size), a few requests in flight; a fine
///   level the engine is still reading (`pending`) is asked again shortly;
///   JPEG decoding happens off the main actor; at most
///   `LivePreviewCache.limitMB` of images are kept.
@MainActor
final class LivePreviewModel: ObservableObject {
    /// Nearest the view's centre first (the fetch order).
    @Published private(set) var squares: [O4LivePreviewSquare] = []
    /// `squares` coarse level first (the draw order, #2012).
    private(set) var drawn: [O4LivePreviewSquare] = []
    @Published private(set) var tiles: [O4LivePreviewTile] = []
    @Published private(set) var revision = 0
    private(set) var cache = LivePreviewCache<CGImage>()
    private(set) var enabled = false

    /// The engine and Custom Scenery folder, or nil without an engine.
    var context: () -> (client: OrthoEngineClient, sceneryDir: String)? = { nil }

    /// Requests sent at once (the engine answers them in turn).
    static let inFlightLimit = 4
    /// Wait before a `pending` level is asked again.
    static let retryNanoseconds: UInt64 = 150_000_000

    private var view: (south: Double, west: Double, north: Double, east: Double, pxPerDegree: Double)?
    private var queue: [(square: O4LivePreviewSquare, px: Int)] = []
    private var waiting: [(square: O4LivePreviewSquare, px: Int)] = []
    private var listed: [String: String] = [:]
    private var inFlight = 0
    private var generation = 0
    private var landed: Int?
    private var swap: [String]?
    private var settle: Task<Void, Never>?
    private var retry: Task<Void, Never>?

    func setEnabled(_ on: Bool) {
        guard on != enabled else { return }
        enabled = on
        generation += 1
        if on {
            refresh()
        } else {
            squares = []
            drawn = []
            tiles = []
            queue = []
            waiting = []
            listed = [:]
            cache.removeAll()
            revision += 1
        }
    }

    /// The map's viewport and points per degree of longitude.
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
        generation += 1
        let asked = generation
        let scale = Double(NSScreen.main?.backingScaleFactor ?? 1)
        context.client.livePreviewSquares(
            south: view.south, west: view.west, north: view.north, east: view.east,
            pxPerDegree: view.pxPerDegree, scale: scale, sceneryDir: context.sceneryDir
        ) { [weak self] rows, tiles in
            Task { @MainActor in self?.show(rows, tiles, asked) }
        }
    }

    private func show(_ rows: [O4LivePreviewSquare], _ marks: [O4LivePreviewTile], _ asked: Int) {
        guard enabled, asked == generation else { return }
        squares = rows
        drawn = O4LivePreviewSquare.drawOrder(rows)
        tiles = marks
        listed = Dictionary(rows.map { ($0.key, $0.stamp) }, uniquingKeysWith: { a, _ in a })
        cache.touch(rows.map(\.key))
        queue = cache.plan(rows)
        waiting = []
        revision += 1
        pump()
    }

    private func pump() {
        guard enabled, let context = context() else { return }
        while inFlight < Self.inFlightLimit, !queue.isEmpty {
            let job = queue.removeFirst()
            if let held = cache.held(job.square.key), held.stamp == job.square.stamp, held.px >= job.px {
                continue
            }
            inFlight += 1
            let asked = generation
            context.client.livePreviewMip(path: job.square.path, px: job.px) { [weak self] reply in
                let image = Self.decode(reply)
                Task { @MainActor in self?.arrived(job, reply, image, asked) }
            }
        }
        if queue.isEmpty, !waiting.isEmpty, retry == nil {
            retry = Task { @MainActor [weak self] in
                try? await Task.sleep(nanoseconds: Self.retryNanoseconds)
                guard let self else { return }
                self.retry = nil
                self.queue = self.waiting + self.queue
                self.waiting = []
                self.pump()
            }
        }
    }

    /// The JPEG/PNG decoded now, off the main actor.
    nonisolated private static func decode(_ reply: O4LivePreviewMip) -> CGImage? {
        guard case .image(let data) = reply,
              let source = CGImageSourceCreateWithData(data as CFData, nil) else { return nil }
        let options = [kCGImageSourceShouldCacheImmediately: true] as CFDictionary
        return CGImageSourceCreateImageAtIndex(source, 0, options)
    }

    private func arrived(_ job: (square: O4LivePreviewSquare, px: Int), _ reply: O4LivePreviewMip,
                         _ image: CGImage?, _ asked: Int) {
        inFlight -= 1
        guard enabled else { return }
        if reply == .pending, asked == generation {
            waiting.append(job)
        } else if let image, listed[job.square.key] == job.square.stamp {
            let held = cache.held(job.square.key)
            if held == nil || held!.stamp != job.square.stamp || held!.px < job.px {
                cache.insert(job.square, image, px: job.px, bytes: image.bytesPerRow * image.height)
                revision += 1
            }
        }
        pump()
    }
}
