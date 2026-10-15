import Foundation
import Combine
import SceneryKit

/// The patch layer's state (patch-editor spec §4 "Display", issue #46):
/// which airport's patch the zoomed-in map shows, its document, and the
/// load state the "Patch · ICAO" box reports. Shared by `PatchOverlay`
/// and `PatchInspector`; owned by `BuildModel` (the engine session's owner).
///
/// View mode only (lane L2). `mode`, `selection` and the document's
/// mutation are L3's: its §3 ops edit `document`, then `documentChanged()`
/// rebuilds the derived grid and map geometry.
@MainActor
final class PatchEditModel: ObservableObject {
    enum Mode: String, CaseIterable { case view = "View", edit = "Edit" }

    enum LoadState: Equatable {
        /// Zoomed out, no airport in view, or an engine without the
        /// commands (protocol < 1.12): no layer, no box, no error.
        case hidden
        case loading(icao: String)
        case loaded
        case failed(icao: String, message: String)
        /// The airport nearest the view centre has no patch on disk.
        case noPatch(icao: String, tileBuilt: Bool)
    }

    /// The view must be narrower than this (degrees of longitude) before
    /// any patch is listed or drawn.
    static let maxViewSpanDegrees = 0.08

    @Published private(set) var state: LoadState = .hidden
    @Published private(set) var document: PatchDocument?
    /// Hit-testing for L3's selection and "+" handles.
    @Published private(set) var grid: PatchSpatialGrid?
    /// The document projected for drawing (one entry per shape).
    @Published private(set) var geometry: PatchMapGeometry?
    /// The patch file's modification date (the source line's "built …").
    @Published private(set) var fileDate: Date?
    /// L3: the View / Edit segmented control. Always `.view` in L2.
    @Published var mode: Mode = .view
    /// L3: selected node ids.
    @Published var selection: Set<Int64> = []

    /// Whether the map draws the layer now (loaded and zoomed in).
    var isShowing: Bool { state == .loaded && document != nil }

    private struct Viewport {
        let box: O4LatLonBox
        let centerLat: Double
        let centerLon: Double
        /// The map's airport marks, for "Build this tile first".
        let overlays: MapOverlays
    }

    /// One built tile's `patch_list` answer; `entries` nil while pending.
    private struct Listing {
        let info: O4TileInfo
        var entries: [O4PatchListEntry]?
    }

    private weak var build: BuildModel?
    private var viewport: Viewport?
    private var listings: [BuildModel.TileCoord: Listing] = [:]
    private var loadTask: Task<Void, Never>?
    private var loadingKey: String?
    private var reloadDocument = false
    private var evaluateScheduled = false
    private var subscriptions: Set<AnyCancellable> = []

    init(build: BuildModel) {
        self.build = build
        build.$built.dropFirst().sink { [weak self] _ in self?.scheduleEvaluate() }
            .store(in: &subscriptions)
        build.$protocolHello.dropFirst().sink { [weak self] _ in self?.scheduleEvaluate() }
            .store(in: &subscriptions)
    }

    // MARK: - Viewport

    /// The map moved. Cheap: the decision runs once per run-loop turn.
    func viewportChanged(camera: MapCamera, size: CGSize, overlays: MapOverlays) {
        guard size.width > 0, size.height > 0 else { return }
        let halfW = Double(size.width) / 2 / camera.scale
        let halfH = Double(size.height) / 2 / camera.scale
        guard halfW * 2 < Self.maxViewSpanDegrees else {
            viewport = nil
            scheduleEvaluate()
            return
        }
        let y = MapCamera.mercatorY(lat: camera.centerLat)
        let box = O4LatLonBox(minLat: MapCamera.latitude(mercatorY: y - halfH),
                              minLon: camera.centerLon - halfW,
                              maxLat: MapCamera.latitude(mercatorY: y + halfH),
                              maxLon: camera.centerLon + halfW)
        viewport = Viewport(box: box, centerLat: camera.centerLat, centerLon: camera.centerLon,
                            overlays: overlays)
        scheduleEvaluate()
    }

    private static func nearestAirport(in box: O4LatLonBox, overlays: MapOverlays,
                                       lat: Double, lon: Double) -> (icao: String, lat: Double, lon: Double)? {
        let k = cos(lat * .pi / 180)
        var best: (icao: String, lat: Double, lon: Double, d: Double)?
        for airport in overlays.airports + overlays.defaultAirports {
            let aLat = airport.info.latitude, aLon = airport.info.longitude
            guard aLat >= box.minLat, aLat <= box.maxLat, aLon >= box.minLon, aLon <= box.maxLon
            else { continue }
            let d = hypot(aLat - lat, (aLon - lon) * k)
            if best == nil || d < best!.d { best = (airport.icao, aLat, aLon, d) }
        }
        return best.map { ($0.icao, $0.lat, $0.lon) }
    }

    private func scheduleEvaluate() {
        guard !evaluateScheduled else { return }
        evaluateScheduled = true
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            self.evaluateScheduled = false
            self.evaluate()
        }
    }

    // MARK: - Choosing the airport

    private func evaluate() {
        guard let build, let viewport, let client = build.patchEditorClient() else {
            setState(.hidden)
            return
        }
        let tiles = tilesCovering(viewport.box)
        var pending = false
        for coord in tiles {
            guard let info = build.built[coord] else { continue }
            if listings[coord]?.info != info {
                if coord.key == document?.tile { reloadDocument = true }
                listings[coord] = Listing(info: info, entries: nil)
                list(coord, client: client)
            }
            if listings[coord]?.entries == nil { pending = true }
        }
        let candidates = tiles.flatMap { coord in
            (listings[coord]?.entries ?? []).map { (tile: coord.key, entry: $0) }
        }.filter { $0.entry.bbox.intersects(viewport.box) }
        if let chosen = nearest(candidates, to: viewport) {
            show(chosen.entry, tile: chosen.tile, client: client)
        } else if pending {
            return // decide once the listing lands
        } else if let airport = Self.nearestAirport(in: viewport.box, overlays: viewport.overlays,
                                                    lat: viewport.centerLat, lon: viewport.centerLon) {
            let coord = BuildModel.TileCoord(lat: Int(floor(airport.lat)), lon: Int(floor(airport.lon)))
            setState(.noPatch(icao: airport.icao, tileBuilt: build.built[coord] != nil))
        } else {
            setState(.hidden)
        }
    }

    private func tilesCovering(_ box: O4LatLonBox) -> [BuildModel.TileCoord] {
        var tiles: [BuildModel.TileCoord] = []
        for lat in Int(floor(box.minLat))...Int(floor(box.maxLat)) {
            for lon in Int(floor(box.minLon))...Int(floor(box.maxLon)) {
                tiles.append(BuildModel.TileCoord(lat: lat, lon: lon))
            }
        }
        return tiles
    }

    /// The airport whose bbox is nearest the view centre (0 inside it);
    /// ties go to the bbox whose centre is nearer, then to the ICAO.
    private func nearest(_ candidates: [(tile: String, entry: O4PatchListEntry)],
                         to viewport: Viewport) -> (tile: String, entry: O4PatchListEntry)? {
        let k = cos(viewport.centerLat * .pi / 180)
        func score(_ b: O4LatLonBox) -> (Double, Double) {
            let dLat = max(b.minLat - viewport.centerLat, 0, viewport.centerLat - b.maxLat)
            let dLon = max(b.minLon - viewport.centerLon, 0, viewport.centerLon - b.maxLon) * k
            let cLat = (b.minLat + b.maxLat) / 2 - viewport.centerLat
            let cLon = ((b.minLon + b.maxLon) / 2 - viewport.centerLon) * k
            return (hypot(dLat, dLon), hypot(cLat, cLon))
        }
        return candidates.min { a, b in
            let sa = score(a.entry.bbox), sb = score(b.entry.bbox)
            return sa != sb ? sa < sb : a.entry.icao < b.entry.icao
        }
    }

    // MARK: - Engine calls

    private func list(_ coord: BuildModel.TileCoord, client: OrthoEngineClient) {
        let info = listings[coord]?.info
        Task { [weak self] in
            // A refused listing (old file layout, unreadable patch) shows
            // as "no patch"; the load itself reports its own error.
            let entries = (try? await client.patchList(tile: coord.key))?.airports ?? []
            guard let self, self.listings[coord]?.info == info else { return }
            self.listings[coord]?.entries = entries
            self.scheduleEvaluate()
        }
    }

    private func show(_ entry: O4PatchListEntry, tile: String, client: OrthoEngineClient) {
        let key = "\(tile)|\(entry.icao)|\(entry.path)"
        if !reloadDocument, let document, document.tile == tile, document.icao == entry.icao,
           document.path == entry.path {
            loadTask?.cancel(); loadTask = nil; loadingKey = nil
            setState(.loaded)
            return
        }
        guard loadingKey != key else { return }
        reloadDocument = false
        loadTask?.cancel()
        loadingKey = key
        setState(.loading(icao: entry.icao))
        loadTask = Task { [weak self] in
            do {
                let reply = try await client.patchLoad(tile: tile, icao: entry.icao)
                let built = await Task.detached(priority: .userInitiated) {
                    let doc = PatchDocument(tile: tile, load: reply)
                    return (doc, PatchSpatialGrid(document: doc), PatchMapGeometry(document: doc))
                }.value
                guard let self, !Task.isCancelled, self.loadingKey == key else { return }
                self.document = built.0
                self.grid = built.1
                self.geometry = built.2
                self.fileDate = (try? FileManager.default.attributesOfItem(
                    atPath: reply.path))?[.modificationDate] as? Date
                self.selection = []
                self.loadingKey = nil
                self.setState(.loaded)
            } catch {
                guard let self, !Task.isCancelled, self.loadingKey == key else { return }
                self.loadingKey = nil
                self.setState(.failed(icao: entry.icao, message: "\(error)"))
            }
        }
    }

    /// L3: after an edit to `document`, rebuild what is derived from it.
    func documentChanged() {
        guard var doc = document else { return }
        doc.reindex()
        document = doc
        grid = PatchSpatialGrid(document: doc)
        geometry = PatchMapGeometry(document: doc)
    }

    private func setState(_ new: LoadState) {
        if state != new { state = new }
    }
}
